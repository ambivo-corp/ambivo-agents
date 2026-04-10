# ambivo_agents/agents/web_scraper.py
"""
Lightweight Web Scraper Agent using HTTP-based scraping APIs.

Supports Jina Reader (default, free), Firecrawl (premium), and
requests+BeautifulSoup (offline fallback). Provides single-URL scraping,
batch scraping with rate limiting, and URL accessibility checks.
"""

import asyncio
import json
import logging
import re
import time
import uuid
from datetime import datetime
from typing import Any, AsyncIterator, Dict, List, Optional

from ..config.loader import get_config_section, load_config
from ..core.base import (
    AgentMessage,
    AgentRole,
    AgentTool,
    BaseAgent,
    ExecutionContext,
    MessageType,
    StreamChunk,
    StreamSubType,
)
from ..core.history import ContextType, WebAgentHistoryMixin

try:
    import httpx

    HTTPX_AVAILABLE = True
except ImportError:
    HTTPX_AVAILABLE = False

try:
    import requests
    from bs4 import BeautifulSoup

    REQUESTS_AVAILABLE = True
except ImportError:
    REQUESTS_AVAILABLE = False


class WebScraperAgent(BaseAgent, WebAgentHistoryMixin):
    """Web scraper agent using HTTP-based scraping APIs.

    Scrapes web pages via Jina Reader (free), Firecrawl (premium), or
    requests+BeautifulSoup (offline fallback). Supports single-URL scraping,
    batch scraping with configurable rate limiting, URL accessibility checks,
    and context-aware conversation (remembers recently scraped URLs).

    Configuration is loaded from the ``web_scraping`` section of
    ``agent_config.yaml``. The scraping provider, API keys, timeout, and
    rate limit are all configurable.
    """

    def __init__(
        self,
        agent_id: str = None,
        memory_manager=None,
        llm_service=None,
        system_message: str = None,
        **kwargs,
    ):
        if agent_id is None:
            agent_id = f"scraper_{str(uuid.uuid4())[:8]}"

        default_system = (
            "You are a web scraping agent that extracts content from websites. "
            "You can scrape single URLs, batch scrape multiple URLs, and check URL accessibility. "
            "You remember URLs from previous conversations and understand context references."
        )

        super().__init__(
            agent_id=agent_id,
            role=AgentRole.RESEARCHER,
            memory_manager=memory_manager,
            llm_service=llm_service,
            name="Web Scraper Agent",
            description="Web scraper using Jina Reader, Firecrawl, and requests+bs4",
            system_message=system_message or default_system,
            **kwargs,
        )

        self.setup_history_mixin()
        self.logger = logging.getLogger(f"WebScraperAgent-{agent_id}")

        # Load scraping config
        try:
            config = load_config()
            self.scraper_config = get_config_section("web_scraping", config) or {}
        except Exception:
            self.scraper_config = {}

        # Scraping provider config
        scraping_config = self.scraper_config.get("scraping", {})
        self.provider = scraping_config.get("provider", "jina")
        self.jina_api_key = scraping_config.get("jina_api_key") or self.scraper_config.get("jina_api_key")
        self.firecrawl_api_key = scraping_config.get("firecrawl_api_key") or self.scraper_config.get("firecrawl_api_key")
        self.timeout = self.scraper_config.get("timeout", 60)
        self.rate_limit = self.scraper_config.get("rate_limit_seconds", 1.0)

        # Register tools
        self.add_tool(AgentTool(
            name="scrape_url",
            description="Scrape content from a single URL",
            function=self._scrape_url,
            parameters_schema={
                "type": "object",
                "properties": {
                    "url": {"type": "string", "description": "URL to scrape"},
                    "method": {"type": "string", "enum": ["auto", "jina", "firecrawl", "requests"]},
                },
                "required": ["url"],
            },
        ))
        self.add_tool(AgentTool(
            name="batch_scrape",
            description="Scrape multiple URLs",
            function=self._batch_scrape,
            parameters_schema={
                "type": "object",
                "properties": {
                    "urls": {"type": "array", "items": {"type": "string"}},
                    "method": {"type": "string", "enum": ["auto", "jina", "firecrawl", "requests"]},
                },
                "required": ["urls"],
            },
        ))
        self.add_tool(AgentTool(
            name="check_accessibility",
            description="Check if a URL is accessible",
            function=self._check_accessibility,
            parameters_schema={
                "type": "object",
                "properties": {"url": {"type": "string"}},
                "required": ["url"],
            },
        ))

    async def process_message(
        self, message: AgentMessage, context: ExecutionContext = None
    ) -> AgentMessage:
        """Process a scraping request by detecting intent and routing.

        Extracts URLs from the message, detects intent (scrape, batch,
        accessibility check, or help), and dispatches accordingly. Falls
        back to the most recently scraped URL when no URL is found.

        Args:
            message: Incoming agent message containing the user request.
            context: Optional execution context.

        Returns:
            AgentMessage with the scraping results or help text.
        """
        self.memory.store_message(message)

        try:
            user_message = message.content
            self.update_conversation_state(user_message)

            # Detect intent and extract URLs
            urls = self._extract_urls_from_text(user_message)
            intent = self._detect_intent(user_message, urls)

            # Resolve context references
            if not urls:
                recent_url = self.get_recent_url()
                if recent_url:
                    urls = [recent_url]

            # Route based on intent
            if intent == "help_request" or not urls:
                response_content = await self._handle_help(user_message)
            elif intent == "check_accessibility":
                result = await self._check_accessibility(urls[0])
                response_content = self._format_accessibility_result(result)
            elif intent == "scrape_batch" or len(urls) > 1:
                result = await self._batch_scrape(urls)
                response_content = self._format_batch_result(result)
            else:
                result = await self._scrape_url(urls[0])
                response_content = self._format_scrape_result(result)

            response = self.create_response(
                content=response_content,
                recipient_id=message.sender_id,
                session_id=message.session_id,
                conversation_id=message.conversation_id,
            )
            self.memory.store_message(response)
            return response

        except Exception as e:
            return self.create_response(
                content=f"Web Scraper Agent error: {str(e)}",
                recipient_id=message.sender_id,
                message_type=MessageType.ERROR,
                session_id=message.session_id,
                conversation_id=message.conversation_id,
            )

    async def process_message_stream(
        self, message: AgentMessage, context: ExecutionContext = None
    ) -> AsyncIterator[StreamChunk]:
        """Stream scraping results with incremental status updates.

        Yields status chunks during initialization and content chunks
        as each URL is scraped.

        Args:
            message: Incoming agent message.
            context: Optional execution context.

        Yields:
            StreamChunk objects with status or content sub-types.
        """
        self.memory.store_message(message)

        try:
            user_message = message.content
            self.update_conversation_state(user_message)

            yield StreamChunk(
                text="**Web Scraper Agent**\n\n",
                sub_type=StreamSubType.STATUS,
                metadata={"agent": "web_scraper", "phase": "initialization"},
            )

            urls = self._extract_urls_from_text(user_message)
            if not urls:
                recent_url = self.get_recent_url()
                if recent_url:
                    urls = [recent_url]

            if urls:
                yield StreamChunk(
                    text=f"Scraping {len(urls)} URL(s)...\n",
                    sub_type=StreamSubType.STATUS,
                )
                for url in urls:
                    result = await self._scrape_url(url)
                    yield StreamChunk(
                        text=self._format_scrape_result(result),
                        sub_type=StreamSubType.CONTENT,
                    )
            else:
                response = await self._handle_help(user_message)
                yield StreamChunk(text=response, sub_type=StreamSubType.CONTENT)

        except Exception as e:
            yield StreamChunk(
                text=f"Error: {str(e)}",
                sub_type=StreamSubType.CONTENT,
                metadata={"error": True},
            )

    # --- URL validation ---

    _BLOCKED_HOSTS = {"localhost", "metadata.google.internal"}
    _ALLOWED_SCHEMES = {"http", "https"}

    def _validate_url(self, url: str) -> None:
        """Validate a URL to prevent SSRF attacks.

        Blocks non-HTTP(S) schemes, localhost, and any hostname that resolves
        to a private, loopback, link-local, or reserved IP address (including
        cloud metadata services like 169.254.169.254).

        Args:
            url: URL to validate.

        Raises:
            ValueError: If the URL uses a blocked scheme, host, or IP range.
        """
        import ipaddress
        import socket
        from urllib.parse import urlparse

        parsed = urlparse(url)
        if parsed.scheme not in self._ALLOWED_SCHEMES:
            raise ValueError(f"Unsupported URL scheme: {parsed.scheme}")
        hostname = (parsed.hostname or "").lower()
        if not hostname:
            raise ValueError("URL missing hostname")
        if hostname in self._BLOCKED_HOSTS:
            raise ValueError(f"Blocked host: {hostname}")

        # Resolve hostname to IP(s) and check each one
        try:
            addrinfo = socket.getaddrinfo(hostname, None)
        except socket.gaierror as e:
            raise ValueError(f"Could not resolve hostname {hostname}: {e}")

        for family, _, _, _, sockaddr in addrinfo:
            ip_str = sockaddr[0]
            try:
                ip = ipaddress.ip_address(ip_str)
            except ValueError:
                continue
            if (
                ip.is_private
                or ip.is_loopback
                or ip.is_link_local
                or ip.is_reserved
                or ip.is_multicast
                or ip.is_unspecified
            ):
                raise ValueError(f"Blocked IP {ip_str} for host {hostname}")

    # --- Core scraping methods ---

    async def _scrape_url(
        self,
        url: str,
        method: str = "auto",
        extract_links: bool = True,
        extract_images: bool = True,
        take_screenshot: bool = False,
        topic: str = "web_scraping",
        external_handoff_dir: str = None,
        **kwargs,
    ) -> Dict[str, Any]:
        """Scrape a single URL using the configured or specified provider.

        Validates the URL, then attempts the requested method with automatic
        fallback to requests+BeautifulSoup on failure.

        Args:
            url: URL to scrape.
            method: Scraping backend (``"auto"``, ``"jina"``, ``"firecrawl"``,
                or ``"requests"``). ``"auto"`` uses the configured default.

        Returns:
            Dict with ``success``, ``url``, ``content``, ``title``,
            ``status_code``, ``response_time``, ``method``, and
            ``content_length`` keys.
        """
        self._validate_url(url)

        if method == "auto":
            method = self.provider

        try:
            if method == "jina" and HTTPX_AVAILABLE:
                return await self._scrape_with_jina(url)
            elif method == "firecrawl" and HTTPX_AVAILABLE and self.firecrawl_api_key:
                return await self._scrape_with_firecrawl(url)
            elif REQUESTS_AVAILABLE:
                return self._scrape_with_requests(url)
            elif HTTPX_AVAILABLE:
                return await self._scrape_with_jina(url)
            else:
                return {"success": False, "url": url, "error": "No scraping backend available"}
        except Exception as e:
            self.logger.warning(f"Scraping failed with {method}, trying fallback: {e}")
            # Fallback chain: jina -> requests -> error
            if method != "requests" and REQUESTS_AVAILABLE:
                try:
                    return self._scrape_with_requests(url)
                except Exception as fallback_error:
                    return {"success": False, "url": url, "error": str(fallback_error)}
            return {"success": False, "url": url, "error": str(e)}

    async def _scrape_with_jina(self, url: str) -> Dict[str, Any]:
        """Scrape a URL using the Jina Reader API.

        Args:
            url: URL to scrape.

        Returns:
            Result dict with scraped content in markdown format.
        """
        start_time = time.time()
        headers = {"Accept": "application/json"}
        if self.jina_api_key:
            headers["Authorization"] = f"Bearer {self.jina_api_key}"

        async with httpx.AsyncClient(timeout=self.timeout) as client:
            response = await client.get(f"https://r.jina.ai/{url}", headers=headers)
            response_time = time.time() - start_time

            if response.status_code == 200:
                try:
                    data = response.json()
                    content = data.get("data", {}).get("content", "") or data.get("content", "")
                    title = data.get("data", {}).get("title", "") or data.get("title", "No title")
                except (json.JSONDecodeError, KeyError):
                    content = response.text
                    title = "No title"

                return {
                    "success": True,
                    "url": url,
                    "title": title,
                    "content": content,
                    "content_length": len(content),
                    "status_code": response.status_code,
                    "response_time": response_time,
                    "method": "jina",
                    "execution_mode": "api",
                }
            else:
                return {
                    "success": False,
                    "url": url,
                    "error": f"Jina Reader returned status {response.status_code}",
                    "status_code": response.status_code,
                    "response_time": response_time,
                    "method": "jina",
                }

    async def _scrape_with_firecrawl(self, url: str) -> Dict[str, Any]:
        """Scrape a URL using the Firecrawl API (premium).

        Args:
            url: URL to scrape.

        Returns:
            Result dict with scraped content in markdown format.
        """
        start_time = time.time()
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self.firecrawl_api_key}",
        }
        payload = {"url": url, "formats": ["markdown"]}

        async with httpx.AsyncClient(timeout=self.timeout) as client:
            response = await client.post(
                "https://api.firecrawl.dev/v1/scrape",
                json=payload,
                headers=headers,
            )
            response_time = time.time() - start_time

            if response.status_code == 200:
                data = response.json()
                result_data = data.get("data", {})
                content = result_data.get("markdown", "") or result_data.get("content", "")
                title = result_data.get("metadata", {}).get("title", "No title")

                return {
                    "success": True,
                    "url": url,
                    "title": title,
                    "content": content,
                    "content_length": len(content),
                    "status_code": response.status_code,
                    "response_time": response_time,
                    "method": "firecrawl",
                    "execution_mode": "api",
                }
            else:
                return {
                    "success": False,
                    "url": url,
                    "error": f"Firecrawl returned status {response.status_code}",
                    "status_code": response.status_code,
                    "response_time": response_time,
                    "method": "firecrawl",
                }

    def _scrape_with_requests(self, url: str) -> Dict[str, Any]:
        """Scrape a URL using requests + BeautifulSoup (offline fallback).

        Strips script, style, nav, footer, and header tags before extracting
        text content.

        Args:
            url: URL to scrape.

        Returns:
            Result dict with plain-text content.
        """
        headers = self.scraper_config.get(
            "default_headers",
            {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"},
        )

        start_time = time.time()
        response = requests.get(url, headers=headers, timeout=self.timeout)
        response_time = time.time() - start_time

        if response.status_code >= 400:
            return {
                "success": False,
                "url": url,
                "error": f"HTTP {response.status_code}",
                "status_code": response.status_code,
                "response_time": response_time,
                "method": "requests",
            }

        soup = BeautifulSoup(response.content, "html.parser")
        title = soup.find("title")
        title = title.get_text().strip() if title else "No title"

        for tag in soup(["script", "style", "nav", "footer", "header"]):
            tag.decompose()

        content = soup.get_text()
        content = " ".join(content.split())

        return {
            "success": True,
            "url": url,
            "title": title,
            "content": content,
            "content_length": len(content),
            "status_code": response.status_code,
            "response_time": response_time,
            "method": "requests",
            "execution_mode": "local",
        }

    async def _batch_scrape(
        self, urls: List[str], method: str = "auto", **kwargs
    ) -> Dict[str, Any]:
        """Scrape multiple URLs sequentially with rate limiting.

        Args:
            urls: List of URLs to scrape.
            method: Scraping backend to use for each URL.

        Returns:
            Dict with ``total_urls``, ``successful``, ``failed`` counts
            and a ``results`` list of individual scrape results.
        """
        results = []
        for i, url in enumerate(urls):
            try:
                result = await self._scrape_url(url, method, **kwargs)
                results.append(result)
                if i < len(urls) - 1:
                    await asyncio.sleep(self.rate_limit)
            except Exception as e:
                results.append({"success": False, "url": url, "error": str(e)})

        successful = sum(1 for r in results if r.get("success", False))
        return {
            "success": True,
            "total_urls": len(urls),
            "successful": successful,
            "failed": len(urls) - successful,
            "results": results,
            "execution_mode": "api",
        }

    async def _check_accessibility(self, url: str) -> Dict[str, Any]:
        """Check whether a URL is accessible via a HEAD request.

        Args:
            url: URL to check.

        Returns:
            Dict with ``accessible`` bool, ``status_code``, and
            ``response_time``.
        """
        try:
            start_time = time.time()
            if HTTPX_AVAILABLE:
                async with httpx.AsyncClient(timeout=10) as client:
                    response = await client.head(url, follow_redirects=True)
                    return {
                        "success": True,
                        "url": url,
                        "accessible": response.status_code < 400,
                        "status_code": response.status_code,
                        "response_time": time.time() - start_time,
                        "timestamp": datetime.now().isoformat(),
                    }
            elif REQUESTS_AVAILABLE:
                response = requests.head(url, timeout=10, allow_redirects=True)
                return {
                    "success": True,
                    "url": url,
                    "accessible": response.status_code < 400,
                    "status_code": response.status_code,
                    "response_time": time.time() - start_time,
                    "timestamp": datetime.now().isoformat(),
                }
            else:
                return {"success": False, "url": url, "error": "No HTTP client available"}
        except Exception as e:
            return {
                "success": False,
                "url": url,
                "error": str(e),
                "timestamp": datetime.now().isoformat(),
            }

    # --- Helpers ---

    def _extract_urls_from_text(self, text: str) -> List[str]:
        """Extract HTTP/HTTPS URLs from free-form text using regex."""
        url_pattern = r'https?://[^\s<>"{}|\\^`\[\]]+'
        return re.findall(url_pattern, text)

    def _detect_intent(self, message: str, urls: List[str]) -> str:
        """Detect user intent from message keywords and URL count.

        Returns:
            One of ``"check_accessibility"``, ``"help_request"``,
            ``"scrape_batch"``, or ``"scrape_single"``.
        """
        lower = message.lower()
        if any(w in lower for w in ["accessible", "reachable", "alive", "up", "status"]):
            return "check_accessibility"
        if any(w in lower for w in ["help", "what can you", "how do"]):
            return "help_request"
        if len(urls) > 1 or any(w in lower for w in ["batch", "multiple", "all"]):
            return "scrape_batch"
        if urls:
            return "scrape_single"
        return "help_request"

    def _format_scrape_result(self, result: Dict[str, Any]) -> str:
        """Format a single scrape result as human-readable markdown text."""
        if not result.get("success"):
            return f"Failed to scrape: {result.get('error', 'Unknown error')}"

        content = result.get("content", "")
        # Truncate for display but keep full content in result
        preview = content[:2000] + "..." if len(content) > 2000 else content

        return (
            f"**{result.get('title', 'No title')}**\n"
            f"URL: {result.get('url')}\n"
            f"Method: {result.get('method')} | Status: {result.get('status_code')} | "
            f"Time: {result.get('response_time', 0):.2f}s | Length: {result.get('content_length', 0)}\n\n"
            f"{preview}"
        )

    def _format_batch_result(self, result: Dict[str, Any]) -> str:
        """Format batch scrape results as a summary with per-URL status."""
        lines = [
            f"**Batch Scrape Results**: {result['successful']}/{result['total_urls']} successful\n"
        ]
        for r in result.get("results", []):
            if r.get("success"):
                lines.append(f"- {r['url']}: {r.get('content_length', 0)} chars")
            else:
                lines.append(f"- {r['url']}: FAILED - {r.get('error', 'Unknown')}")
        return "\n".join(lines)

    def _format_accessibility_result(self, result: Dict[str, Any]) -> str:
        """Format an accessibility check result as a one-line status string."""
        if result.get("accessible"):
            return f"{result['url']} is accessible (status {result.get('status_code')}, {result.get('response_time', 0):.2f}s)"
        error = result.get('error') or f"status {result.get('status_code')}"
        return f"{result['url']} is not accessible: {error}"

    async def _handle_help(self, user_message: str) -> str:
        """Generate a help response, using LLM if available.

        Falls back to a static help message if the LLM service is
        unavailable or fails.
        """
        if self.llm_service:
            try:
                response = await self.llm_service.generate_response(
                    prompt=f"As a web scraping assistant, help with: {user_message}",
                    system_message=self.system_message,
                )
                return response
            except Exception as e:
                self.logger.warning(f"LLM help generation failed: {e}")

        return (
            "**Web Scraper Agent**\n\n"
            "I can scrape web pages and extract content. Examples:\n"
            "- `scrape https://example.com`\n"
            "- `scrape https://a.com https://b.com` (batch)\n"
            "- `is https://example.com accessible?`\n\n"
            f"Provider: {self.provider} | Timeout: {self.timeout}s"
        )
