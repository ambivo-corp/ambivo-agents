# ambivo_agents/agents/web_scraper.py
"""
Web Scraper Agent with proxy, Docker, and local execution modes.
Updated with LLM-aware intent detection and conversation history integration.
"""

import asyncio
import json
import re
import time
import random
import uuid
import logging
import ssl
import urllib3
from datetime import datetime
from typing import Dict, Any, List, Optional
from urllib.parse import urlparse, urljoin
from dataclasses import dataclass
from pathlib import Path

from ..core.base import BaseAgent, AgentRole, AgentMessage, MessageType, ExecutionContext, AgentTool
from ..config.loader import load_config, get_config_section
from ..core.history import WebAgentHistoryMixin, ContextType

# Conditional imports for different execution modes
try:
    from playwright.async_api import async_playwright

    PLAYWRIGHT_AVAILABLE = True
except ImportError:
    PLAYWRIGHT_AVAILABLE = False

try:
    import requests
    from bs4 import BeautifulSoup

    urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
    REQUESTS_AVAILABLE = True
except ImportError:
    REQUESTS_AVAILABLE = False

try:
    import docker

    DOCKER_AVAILABLE = True
except ImportError:
    DOCKER_AVAILABLE = False


@dataclass
class ScrapingTask:
    """Simple scraping task data structure"""
    url: str
    method: str = "playwright"
    extract_links: bool = True
    extract_images: bool = True
    take_screenshot: bool = False
    timeout: int = 45


class SimpleDockerExecutor:
    """Simple Docker executor for scraping tasks"""

    def __init__(self, config: Dict[str, Any] = None):
        self.config = config or {}
        self.docker_image = self.config.get('docker_image', 'sgosain/amb-ubuntu-python-public-pod')
        self.timeout = self.config.get('timeout', 60)

        if DOCKER_AVAILABLE:
            try:
                self.docker_client = docker.from_env()
                self.docker_client.ping()
                self.available = True
            except Exception as e:
                logging.warning(f"Docker initialization failed: {e}")
                self.available = False
        else:
            self.available = False

    def execute_scraping_task(self, task: ScrapingTask) -> Dict[str, Any]:
        """Execute a scraping task in Docker"""
        if not self.available:
            return {
                'success': False,
                'error': 'Docker not available',
                'url': task.url
            }

        try:
            # Create scraping script for Docker
            script_content = f"""
import asyncio
from playwright.async_api import async_playwright
import json

async def scrape_url():
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        page = await browser.new_page()

        try:
            response = await page.goto('{task.url}', timeout={task.timeout * 1000})
            title = await page.title()
            content = await page.inner_text('body')

            # Extract links if requested
            links = []
            if {task.extract_links}:
                link_elements = await page.query_selector_all('a[href]')
                for link in link_elements[:50]:  # Limit to 50 links
                    href = await link.get_attribute('href')
                    text = await link.inner_text()
                    if href and text:
                        links.append({{'url': href, 'text': text[:100]}})

            # Extract images if requested
            images = []
            if {task.extract_images}:
                img_elements = await page.query_selector_all('img[src]')
                for img in img_elements[:25]:  # Limit to 25 images
                    src = await img.get_attribute('src')
                    alt = await img.get_attribute('alt') or ''
                    if src:
                        images.append({{'url': src, 'alt': alt}})

            result = {{
                'success': True,
                'url': '{task.url}',
                'title': title,
                'content': content[:5000],  # Limit content
                'content_length': len(content),
                'links': links,
                'images': images,
                'status_code': response.status if response else None,
                'method': 'docker_playwright',
                'execution_mode': 'docker'
            }}

            print(json.dumps(result))

        except Exception as e:
            error_result = {{
                'success': False,
                'error': str(e),
                'url': '{task.url}',
                'execution_mode': 'docker'
            }}
            print(json.dumps(error_result))

        finally:
            await browser.close()

asyncio.run(scrape_url())
"""

            # Execute in Docker container
            container = self.docker_client.containers.run(
                image=self.docker_image,
                command=['python', '-c', script_content],
                remove=True,
                mem_limit='512m',
                network_disabled=False,  # Need network for scraping
                stdout=True,
                stderr=True,
                timeout=self.timeout
            )

            # Parse result
            output = container.decode('utf-8') if isinstance(container, bytes) else str(container)
            return json.loads(output.strip().split('\n')[-1])

        except Exception as e:
            return {
                'success': False,
                'error': str(e),
                'url': task.url,
                'execution_mode': 'docker'
            }


class WebScraperAgent(BaseAgent, WebAgentHistoryMixin):
    """Unified web scraper agent with proxy, Docker, and local execution modes"""

    def __init__(self, agent_id: str = None, memory_manager=None, llm_service=None, **kwargs):

        if agent_id is None:
            agent_id = f"scraper_{str(uuid.uuid4())[:8]}"

        super().__init__(
            agent_id=agent_id,
            role=AgentRole.RESEARCHER,
            memory_manager=memory_manager,
            llm_service=llm_service,
            name="Web Scraper Agent",
            description="Unified web scraper with proxy, Docker, and local execution modes",
            **kwargs
        )

        # Initialize history mixin
        self.setup_history_mixin()

        self.logger = logging.getLogger(f"WebScraperAgent-{agent_id}")

        # Load configuration from YAML
        try:
            config = load_config()
            self.scraper_config = get_config_section('web_scraping', config)
        except Exception as e:
            raise ValueError(f"web_scraping configuration not found in agent_config.yaml: {e}")

        # Initialize execution mode based on config
        self.execution_mode = self._determine_execution_mode()

        # Initialize executors based on availability and config
        self.docker_executor = None
        self.proxy_config = None

        # Initialize Docker executor if configured
        if self.execution_mode in ["docker", "auto"]:
            try:
                docker_config = {
                    **self.scraper_config,
                    'docker_image': self.scraper_config.get('docker_image'),
                    'timeout': self.scraper_config.get('timeout', 60)
                }
                self.docker_executor = SimpleDockerExecutor(docker_config)
            except Exception as e:
                self.logger.warning(f"Docker executor initialization failed: {e}")

        # Initialize proxy configuration if enabled
        if self.scraper_config.get('proxy_enabled', False):
            proxy_url = self.scraper_config.get('proxy_config', {}).get('http_proxy')
            if proxy_url:
                self.proxy_config = self._parse_proxy_url(proxy_url)
                self._configure_ssl_for_proxy()

        # Add tools
        self._add_scraping_tools()

        self.logger.info(f"WebScraperAgent initialized (Mode: {self.execution_mode})")

    async def _llm_analyze_scraping_intent(self, user_message: str, conversation_context: str = "") -> Dict[str, Any]:
        """Use LLM to analyze web scraping intent"""
        if not self.llm_service:
            return self._keyword_based_scraping_analysis(user_message)

        prompt = f"""
        Analyze this user message in the context of web scraping and extract:
        1. Primary intent (scrape_single, scrape_batch, check_accessibility, help_request)
        2. URLs to scrape
        3. Extraction preferences (links, images, content)
        4. Context references (referring to previous scraping operations)
        5. Technical specifications (method, timeout, etc.)

        Conversation Context:
        {conversation_context}

        Current User Message: {user_message}

        Respond in JSON format:
        {{
            "primary_intent": "scrape_single|scrape_batch|check_accessibility|help_request",
            "urls": ["http://example.com"],
            "extraction_preferences": {{
                "extract_links": true,
                "extract_images": true,
                "take_screenshot": false
            }},
            "uses_context_reference": true/false,
            "context_type": "previous_url|previous_operation",
            "technical_specs": {{
                "method": "playwright|requests|auto",
                "timeout": 60
            }},
            "confidence": 0.0-1.0
        }}
        """

        try:
            response = await self.llm_service.generate_response(prompt)
            import re
            json_match = re.search(r'\{.*\}', response, re.DOTALL)
            if json_match:
                return json.loads(json_match.group())
            else:
                return self._extract_scraping_intent_from_llm_response(response, user_message)
        except Exception as e:
            return self._keyword_based_scraping_analysis(user_message)

    def _keyword_based_scraping_analysis(self, user_message: str) -> Dict[str, Any]:
        """Fallback keyword-based scraping intent analysis"""
        content_lower = user_message.lower()

        # Determine intent
        if any(word in content_lower for word in ['batch', 'multiple', 'several']):
            intent = 'scrape_batch'
        elif any(word in content_lower for word in ['check', 'test', 'accessible']):
            intent = 'check_accessibility'
        elif any(word in content_lower for word in ['scrape', 'extract', 'crawl']):
            intent = 'scrape_single'
        else:
            intent = 'help_request'

        # Extract URLs
        urls = self.extract_context_from_text(user_message, ContextType.URL)

        return {
            "primary_intent": intent,
            "urls": urls,
            "extraction_preferences": {
                "extract_links": True,
                "extract_images": True,
                "take_screenshot": False
            },
            "uses_context_reference": any(word in content_lower for word in ['this', 'that', 'it']),
            "context_type": "previous_url",
            "technical_specs": {
                "method": "auto",
                "timeout": 60
            },
            "confidence": 0.7
        }

    async def process_message(self, message: AgentMessage, context: ExecutionContext = None) -> AgentMessage:
        """Process message with LLM-based scraping intent detection and history context"""
        self.memory.store_message(message)

        try:
            user_message = message.content

            # Update conversation state
            self.update_conversation_state(user_message)

            # Get conversation context for LLM analysis
            conversation_context = self._get_scraping_conversation_context_summary()

            # Use LLM to analyze intent
            intent_analysis = await self._llm_analyze_scraping_intent(user_message, conversation_context)

            # Route request based on LLM analysis
            response_content = await self._route_scraping_with_llm_analysis(intent_analysis, user_message, context)

            response = self.create_response(
                content=response_content,
                recipient_id=message.sender_id,
                session_id=message.session_id,
                conversation_id=message.conversation_id
            )

            self.memory.store_message(response)
            return response

        except Exception as e:
            error_response = self.create_response(
                content=f"Web Scraper Agent error: {str(e)}",
                recipient_id=message.sender_id,
                message_type=MessageType.ERROR,
                session_id=message.session_id,
                conversation_id=message.conversation_id
            )
            return error_response

    def _get_scraping_conversation_context_summary(self) -> str:
        """Get scraping conversation context summary"""
        try:
            recent_history = self.get_conversation_history_with_context(
                limit=3,
                context_types=[ContextType.URL]
            )

            context_summary = []
            for msg in recent_history:
                if msg.get('message_type') == 'user_input':
                    extracted_context = msg.get('extracted_context', {})
                    urls = extracted_context.get('url', [])

                    if urls:
                        context_summary.append(f"Previous URL: {urls[0]}")

            return "\n".join(context_summary) if context_summary else "No previous scraping context"
        except:
            return "No previous scraping context"

    async def _route_scraping_with_llm_analysis(self, intent_analysis: Dict[str, Any], user_message: str,
                                                context: ExecutionContext) -> str:
        """Route scraping request based on LLM intent analysis"""

        primary_intent = intent_analysis.get("primary_intent", "help_request")
        urls = intent_analysis.get("urls", [])
        extraction_prefs = intent_analysis.get("extraction_preferences", {})
        uses_context = intent_analysis.get("uses_context_reference", False)

        # Resolve context references if needed
        if uses_context and not urls:
            recent_url = self.get_recent_url()
            if recent_url:
                urls = [recent_url]

        # Route based on intent
        if primary_intent == "help_request":
            return await self._handle_scraping_help_request(user_message)
        elif primary_intent == "scrape_single":
            return await self._handle_single_scrape(urls, extraction_prefs, user_message)
        elif primary_intent == "scrape_batch":
            return await self._handle_batch_scrape(urls, extraction_prefs, user_message)
        elif primary_intent == "check_accessibility":
            return await self._handle_accessibility_check(urls, user_message)
        else:
            return await self._handle_scraping_help_request(user_message)

    async def _handle_single_scrape(self, urls: List[str], extraction_prefs: Dict[str, Any], user_message: str) -> str:
        """Handle single URL scraping"""
        if not urls:
            recent_url = self.get_recent_url()
            if recent_url:
                return f"I can scrape web pages. Did you mean to scrape **{recent_url}**? Please confirm."
            else:
                return "I can scrape web pages. Please provide a URL to scrape.\n\n" \
                       "Example: 'scrape https://example.com'"

        url = urls[0]

        try:
            result = await self._scrape_url(
                url=url,
                extract_links=extraction_prefs.get("extract_links", True),
                extract_images=extraction_prefs.get("extract_images", True),
                take_screenshot=extraction_prefs.get("take_screenshot", False)
            )

            if result['success']:
                return f"""✅ **Web Scraping Completed**

🌐 **URL:** {result['url']}
🔧 **Method:** {result.get('method', 'unknown')}
🏃 **Mode:** {result['execution_mode']}
📊 **Status:** {result.get('status_code', 'N/A')}
📄 **Content:** {result['content_length']:,} characters
⏱️ **Time:** {result['response_time']:.2f}s

**Title:** {result.get('title', 'No title')}

**Content Preview:**
{result.get('content', '')[:300]}{'...' if len(result.get('content', '')) > 300 else ''}

**Links Found:** {len(result.get('links', []))}
**Images Found:** {len(result.get('images', []))}"""
            else:
                return f"❌ **Scraping failed:** {result['error']}"

        except Exception as e:
            return f"❌ **Error during scraping:** {str(e)}"

    async def _handle_batch_scrape(self, urls: List[str], extraction_prefs: Dict[str, Any], user_message: str) -> str:
        """Handle batch URL scraping"""
        if not urls:
            return "I can scrape multiple web pages. Please provide URLs to scrape.\n\n" \
                   "Example: 'scrape https://example1.com and https://example2.com'"

        try:
            result = await self._batch_scrape(
                urls=urls,
                method="auto"
            )

            if result['success']:
                successful = result['successful']
                failed = result['failed']
                total = result['total_urls']

                response = f"""📦 **Batch Web Scraping Completed**

📊 **Summary:**
- **Total URLs:** {total}
- **Successful:** {successful}
- **Failed:** {failed}
- **Mode:** {result['execution_mode']}

"""

                if successful > 0:
                    response += "✅ **Successfully Scraped:**\n"
                    for i, scrape_result in enumerate(result['results'], 1):
                        if scrape_result.get('success', False):
                            response += f"{i}. {scrape_result.get('url', 'Unknown')}\n"

                if failed > 0:
                    response += f"\n❌ **Failed Scrapes:** {failed}\n"
                    for i, scrape_result in enumerate(result['results'], 1):
                        if not scrape_result.get('success', False):
                            response += f"{i}. {scrape_result.get('url', 'Unknown')}: {scrape_result.get('error', 'Unknown error')}\n"

                response += f"\n🎉 Batch scraping completed with {successful}/{total} successful scrapes!"
                return response
            else:
                return f"❌ **Batch scraping failed:** {result['error']}"

        except Exception as e:
            return f"❌ **Error during batch scraping:** {str(e)}"

    async def _handle_accessibility_check(self, urls: List[str], user_message: str) -> str:
        """Handle accessibility check"""
        if not urls:
            recent_url = self.get_recent_url()
            if recent_url:
                return f"I can check if websites are accessible. Did you mean to check **{recent_url}**?"
            else:
                return "I can check if websites are accessible. Please provide a URL to check."

        url = urls[0]

        try:
            result = await self._check_accessibility(url)

            if result['success']:
                status = "✅ Accessible" if result.get('accessible', False) else "❌ Not Accessible"
                return f"""🔍 **Accessibility Check Results**

🌐 **URL:** {result['url']}
🚦 **Status:** {status}
📊 **HTTP Status:** {result.get('status_code', 'Unknown')}
⏱️ **Response Time:** {result.get('response_time', 0):.2f}s
📅 **Checked:** {result.get('timestamp', 'Unknown')}

{'The website is accessible and responding normally.' if result.get('accessible', False) else 'The website is not accessible or not responding.'}"""
            else:
                return f"❌ **Accessibility check failed:** {result['error']}"

        except Exception as e:
            return f"❌ **Error during accessibility check:** {str(e)}"

    async def _handle_scraping_help_request(self, user_message: str) -> str:
        """Handle scraping help requests with conversation context"""
        state = self.get_conversation_state()

        response = ("I'm your Web Scraper Agent! I can help you with:\n\n"
                    "🕷️ **Web Scraping**\n"
                    "- Extract content from web pages\n"
                    "- Scrape multiple URLs at once\n"
                    "- Extract links and images\n"
                    "- Take screenshots\n\n"
                    "🔧 **Multiple Execution Modes**\n"
                    "- Proxy support (ScraperAPI compatible)\n"
                    "- Docker-based secure execution\n"
                    "- Local fallback methods\n\n"
                    "🧠 **Smart Context Features**\n"
                    "- Remembers URLs from previous messages\n"
                    "- Understands 'that website' and 'this page'\n"
                    "- Maintains conversation state\n\n")

        # Add current context information
        if state.current_resource:
            response += f"🎯 **Current URL:** {state.current_resource}\n"

        response += f"\n🔧 **Current Mode:** {self.execution_mode.upper()}\n"
        response += f"📡 **Proxy Enabled:** {'✅' if self.proxy_config else '❌'}\n"
        response += f"🐳 **Docker Available:** {'✅' if self.docker_executor and self.docker_executor.available else '❌'}\n"

        response += "\n💡 **Examples:**\n"
        response += "• 'scrape https://example.com'\n"
        response += "• 'batch scrape https://site1.com https://site2.com'\n"
        response += "• 'check if https://example.com is accessible'\n"
        response += "\nI understand context from our conversation! 🚀"

        return response

    def _extract_scraping_intent_from_llm_response(self, llm_response: str, user_message: str) -> Dict[str, Any]:
        """Extract scraping intent from non-JSON LLM response"""
        content_lower = llm_response.lower()

        if 'batch' in content_lower or 'multiple' in content_lower:
            intent = 'scrape_batch'
        elif 'scrape' in content_lower:
            intent = 'scrape_single'
        elif 'check' in content_lower or 'accessible' in content_lower:
            intent = 'check_accessibility'
        else:
            intent = 'help_request'

        return {
            "primary_intent": intent,
            "urls": [],
            "extraction_preferences": {"extract_links": True, "extract_images": True},
            "uses_context_reference": False,
            "context_type": "none",
            "technical_specs": {"method": "auto"},
            "confidence": 0.6
        }

    def _configure_ssl_for_proxy(self):
        """Configure SSL settings for proxy usage"""
        if REQUESTS_AVAILABLE:
            try:
                ssl_context = ssl.create_default_context()
                ssl_context.check_hostname = False
                ssl_context.verify_mode = ssl.CERT_NONE

                import requests.packages.urllib3.util.ssl_
                requests.packages.urllib3.util.ssl_.DEFAULT_CIPHERS = 'ALL'
            except Exception as e:
                self.logger.warning(f"SSL configuration warning: {e}")

        self.logger.info("SSL verification disabled for proxy usage")

    def _determine_execution_mode(self) -> str:
        """Determine execution mode from configuration"""
        # Check if proxy is enabled in config
        if self.scraper_config.get('proxy_enabled', False):
            proxy_url = self.scraper_config.get('proxy_config', {}).get('http_proxy')
            if proxy_url:
                return "proxy"

        # Check if Docker should be used
        if self.scraper_config.get('docker_image'):
            return "docker"

        # Fall back to local execution
        if PLAYWRIGHT_AVAILABLE or REQUESTS_AVAILABLE:
            return "local"

        raise RuntimeError("No scraping execution methods available")

    def _parse_proxy_url(self, proxy_url: str) -> Dict[str, Any]:
        """Parse proxy URL for different usage formats"""
        try:
            parsed = urlparse(proxy_url)
            return {
                'server': f"{parsed.scheme}://{parsed.hostname}:{parsed.port}",
                'username': parsed.username,
                'password': parsed.password,
                'host': parsed.hostname,
                'port': parsed.port,
                'full_url': proxy_url
            }
        except Exception as e:
            self.logger.error(f"Failed to parse proxy URL: {e}")
            return {}

    def _add_scraping_tools(self):
        """Add scraping tools"""
        self.add_tool(AgentTool(
            name="scrape_url",
            description="Scrape a single URL",
            function=self._scrape_url,
            parameters_schema={
                "type": "object",
                "properties": {
                    "url": {"type": "string", "description": "URL to scrape"},
                    "method": {"type": "string", "enum": ["auto", "playwright", "requests"], "default": "auto"},
                    "extract_links": {"type": "boolean", "default": True},
                    "extract_images": {"type": "boolean", "default": True},
                    "take_screenshot": {"type": "boolean", "default": False}
                },
                "required": ["url"]
            }
        ))

        self.add_tool(AgentTool(
            name="batch_scrape",
            description="Scrape multiple URLs",
            function=self._batch_scrape,
            parameters_schema={
                "type": "object",
                "properties": {
                    "urls": {"type": "array", "items": {"type": "string"}},
                    "method": {"type": "string", "default": "auto"}
                },
                "required": ["urls"]
            }
        ))

        self.add_tool(AgentTool(
            name="check_accessibility",
            description="Quick check if URL is accessible",
            function=self._check_accessibility,
            parameters_schema={
                "type": "object",
                "properties": {
                    "url": {"type": "string", "description": "URL to check"}
                },
                "required": ["url"]
            }
        ))

    async def _scrape_url(self, url: str, method: str = "auto", **kwargs) -> Dict[str, Any]:
        """Unified URL scraping method"""
        try:
            if self.execution_mode == "docker" and self.docker_executor and self.docker_executor.available:
                return await self._scrape_with_docker(url, method, **kwargs)
            elif self.execution_mode == "proxy" and self.proxy_config:
                return await self._scrape_with_proxy(url, method, **kwargs)
            else:
                return await self._scrape_locally(url, method, **kwargs)

        except Exception as e:
            self.logger.error(f"Scraping error for {url}: {e}")
            return {
                "success": False,
                "error": str(e),
                "url": url,
                "method": method,
                "execution_mode": self.execution_mode
            }

    async def _scrape_with_docker(self, url: str, method: str, **kwargs) -> Dict[str, Any]:
        """Scrape using Docker executor"""
        task = ScrapingTask(
            url=url,
            method=method if method != "auto" else "playwright",
            extract_links=kwargs.get('extract_links', True),
            extract_images=kwargs.get('extract_images', True),
            take_screenshot=kwargs.get('take_screenshot', False),
            timeout=kwargs.get('timeout', self.scraper_config.get('timeout', 60))
        )

        result = self.docker_executor.execute_scraping_task(task)
        result['execution_mode'] = 'docker'
        return result

    async def _scrape_with_proxy(self, url: str, method: str, **kwargs) -> Dict[str, Any]:
        """Scrape using proxy (ScraperAPI style) with SSL verification disabled"""
        if method == "auto":
            method = "playwright" if PLAYWRIGHT_AVAILABLE else "requests"

        if method == "playwright" and PLAYWRIGHT_AVAILABLE:
            return await self._scrape_proxy_playwright(url, **kwargs)
        elif REQUESTS_AVAILABLE:
            return self._scrape_proxy_requests(url, **kwargs)
        else:
            raise RuntimeError("No proxy scraping methods available")

    async def _scrape_proxy_playwright(self, url: str, **kwargs) -> Dict[str, Any]:
        """Scrape using Playwright with proxy and SSL verification disabled"""
        async with async_playwright() as p:
            browser = None
            try:
                browser = await p.chromium.launch(
                    headless=True,
                    proxy={
                        "server": self.proxy_config['server'],
                        "username": self.proxy_config['username'],
                        "password": self.proxy_config['password']
                    },
                    args=[
                        '--no-sandbox',
                        '--disable-dev-shm-usage',
                        '--disable-web-security',
                        '--disable-features=VizDisplayCompositor',
                        '--ignore-certificate-errors',
                        '--ignore-ssl-errors',
                        '--ignore-certificate-errors-spki-list',
                        '--allow-running-insecure-content'
                    ]
                )

                context = await browser.new_context(
                    viewport={"width": 1920, "height": 1080},
                    user_agent=self.scraper_config.get('default_headers', {}).get('User-Agent',
                                                                                  'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'),
                    ignore_https_errors=True
                )

                page = await context.new_page()
                start_time = time.time()

                timeout_ms = self.scraper_config.get('timeout', 60) * 1000
                response = await page.goto(url, wait_until="domcontentloaded", timeout=timeout_ms)
                await page.wait_for_timeout(3000)

                response_time = time.time() - start_time

                # Extract content
                title = await page.title()
                content = await page.inner_text("body")

                # Extract links
                links = []
                if kwargs.get('extract_links', True):
                    link_elements = await page.query_selector_all("a[href]")
                    max_links = self.scraper_config.get('max_links_per_page', 100)
                    for link in link_elements[:max_links]:
                        href = await link.get_attribute("href")
                        text = await link.inner_text()
                        if href and text:
                            links.append({
                                "url": urljoin(url, href),
                                "text": text.strip()[:100]
                            })

                # Extract images
                images = []
                if kwargs.get('extract_images', True):
                    img_elements = await page.query_selector_all("img[src]")
                    max_images = self.scraper_config.get('max_images_per_page', 50)
                    for img in img_elements[:max_images]:
                        src = await img.get_attribute("src")
                        alt = await img.get_attribute("alt") or ""
                        if src:
                            images.append({
                                "url": urljoin(url, src),
                                "alt": alt
                            })

                await browser.close()

                return {
                    "success": True,
                    "url": url,
                    "title": title,
                    "content": content[:5000],
                    "content_length": len(content),
                    "links": links,
                    "images": images,
                    "status_code": response.status if response else None,
                    "response_time": response_time,
                    "method": "proxy_playwright",
                    "execution_mode": "proxy"
                }

            except Exception as e:
                if browser:
                    await browser.close()
                raise e

    def _scrape_proxy_requests(self, url: str, **kwargs) -> Dict[str, Any]:
        """Scrape using requests with proxy and SSL verification disabled"""
        proxies = {
            'http': self.proxy_config['full_url'],
            'https': self.proxy_config['full_url']
        }

        headers = self.scraper_config.get('default_headers', {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
        })

        start_time = time.time()

        response = requests.get(
            url,
            headers=headers,
            proxies=proxies,
            timeout=self.scraper_config.get('timeout', 60),
            verify=False,
            allow_redirects=True
        )
        response_time = time.time() - start_time

        soup = BeautifulSoup(response.content, 'html.parser')

        # Extract content
        title = soup.find('title')
        title = title.get_text().strip() if title else "No title"

        for script in soup(["script", "style"]):
            script.decompose()

        content = soup.get_text()
        content = ' '.join(content.split())

        # Extract links and images based on config
        links = []
        images = []

        if kwargs.get('extract_links', True):
            max_links = self.scraper_config.get('max_links_per_page', 100)
            for link in soup.find_all('a', href=True)[:max_links]:
                links.append({
                    "url": urljoin(url, link['href']),
                    "text": link.get_text().strip()[:100]
                })

        if kwargs.get('extract_images', True):
            max_images = self.scraper_config.get('max_images_per_page', 50)
            for img in soup.find_all('img', src=True)[:max_images]:
                images.append({
                    "url": urljoin(url, img['src']),
                    "alt": img.get('alt', '')
                })

        return {
            "success": True,
            "url": url,
            "title": title,
            "content": content[:5000],
            "content_length": len(content),
            "links": links,
            "images": images,
            "status_code": response.status_code,
            "response_time": response_time,
            "method": "proxy_requests",
            "execution_mode": "proxy"
        }

    async def _scrape_locally(self, url: str, method: str, **kwargs) -> Dict[str, Any]:
        """Scrape using local methods (no proxy, no Docker)"""
        if method == "auto":
            method = "playwright" if PLAYWRIGHT_AVAILABLE else "requests"

        if method == "playwright" and PLAYWRIGHT_AVAILABLE:
            return await self._scrape_local_playwright(url, **kwargs)
        elif REQUESTS_AVAILABLE:
            return self._scrape_local_requests(url, **kwargs)
        else:
            raise RuntimeError("No local scraping methods available")

    async def _scrape_local_playwright(self, url: str, **kwargs) -> Dict[str, Any]:
        """Local Playwright scraping"""
        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=True)
            context = await browser.new_context(
                user_agent=self.scraper_config.get('default_headers', {}).get('User-Agent',
                                                                              'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36')
            )
            page = await context.new_page()

            start_time = time.time()
            timeout_ms = self.scraper_config.get('timeout', 60) * 1000
            response = await page.goto(url, timeout=timeout_ms)
            response_time = time.time() - start_time

            title = await page.title()
            content = await page.inner_text("body")

            await browser.close()

            return {
                "success": True,
                "url": url,
                "title": title,
                "content": content[:5000],
                "content_length": len(content),
                "status_code": response.status if response else None,
                "response_time": response_time,
                "method": "local_playwright",
                "execution_mode": "local"
            }

    def _scrape_local_requests(self, url: str, **kwargs) -> Dict[str, Any]:
        """Local requests scraping"""
        headers = self.scraper_config.get('default_headers', {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
        })

        start_time = time.time()
        response = requests.get(url, headers=headers, timeout=self.scraper_config.get('timeout', 60))
        response_time = time.time() - start_time

        soup = BeautifulSoup(response.content, 'html.parser')
        title = soup.find('title')
        title = title.get_text().strip() if title else "No title"

        for script in soup(["script", "style"]):
            script.decompose()

        content = soup.get_text()
        content = ' '.join(content.split())

        return {
            "success": True,
            "url": url,
            "title": title,
            "content": content[:5000],
            "content_length": len(content),
            "status_code": response.status_code,
            "response_time": response_time,
            "method": "local_requests",
            "execution_mode": "local"
        }

    async def _batch_scrape(self, urls: List[str], method: str = "auto") -> Dict[str, Any]:
        """Batch scraping with rate limiting from config"""
        results = []
        rate_limit = self.scraper_config.get('rate_limit_seconds', 1.0)

        for i, url in enumerate(urls):
            try:
                result = await self._scrape_url(url, method)
                results.append(result)

                if i < len(urls) - 1:
                    await asyncio.sleep(rate_limit)

            except Exception as e:
                results.append({
                    "success": False,
                    "url": url,
                    "error": str(e)
                })

        successful = sum(1 for r in results if r.get('success', False))

        return {
            "success": True,
            "total_urls": len(urls),
            "successful": successful,
            "failed": len(urls) - successful,
            "results": results,
            "execution_mode": self.execution_mode
        }

    async def _check_accessibility(self, url: str) -> Dict[str, Any]:
        """Check URL accessibility"""
        try:
            result = await self._scrape_url(url, extract_links=False, extract_images=False)
            return {
                "success": True,
                "url": url,
                "accessible": result.get('success', False),
                "status_code": result.get('status_code'),
                "response_time": result.get('response_time', 0),
                "error": result.get('error'),
                "timestamp": datetime.now().isoformat()
            }
        except Exception as e:
            return {
                "success": False,
                "error": str(e),
                "url": url,
                "timestamp": datetime.now().isoformat()
            }

    def _extract_urls_from_text(self, text: str) -> List[str]:
        """Extract URLs from text"""
        url_pattern = r'https?://[^\s<>"{}|\\^`\[\]]+'
        return re.findall(url_pattern, text)