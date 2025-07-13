# ambivo_agents/agents/web_search.py - Complete and Corrected LLM-Aware Web Search Agent
"""
LLM-Aware Web Search Agent with conversation history and intelligent intent detection
"""

import asyncio
import json
import time
import uuid
from dataclasses import dataclass
from datetime import datetime
from typing import Any, AsyncIterator, Dict, List, Optional

import requests

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


@dataclass
class SearchResult:
    """Single search result data structure"""

    title: str
    url: str
    snippet: str
    source: str = ""
    rank: int = 0
    score: float = 0.0
    timestamp: Optional[datetime] = None


@dataclass
class SearchResponse:
    """Search response containing multiple results"""

    query: str
    results: List[SearchResult]
    total_results: int
    search_time: float
    provider: str
    status: str = "success"
    error: Optional[str] = None


class WebSearchServiceAdapter:
    """Web Search Service Adapter supporting multiple search providers"""

    def __init__(self):
        # Load configuration from YAML
        config = load_config()
        self.search_config = get_config_section("web_search", config)

        self.providers = {}
        self.current_provider = None

        # Initialize available providers
        self._initialize_providers()

        # Set default provider
        self.current_provider = self._get_best_provider()

    def _initialize_providers(self):
        """Initialize available search providers"""

        # Brave Search API
        if self.search_config.get("brave_api_key"):
            self.providers["brave"] = {
                "name": "brave",
                "api_key": self.search_config["brave_api_key"],
                "base_url": "https://api.search.brave.com/res/v1/web/search",
                "priority": 2,
                "available": True,
                "rate_limit_delay": 2.0,
            }

        # AVES API
        if self.search_config.get("avesapi_api_key"):
            self.providers["aves"] = {
                "name": "aves",
                "api_key": self.search_config["avesapi_api_key"],
                "base_url": "https://api.avesapi.com/search",
                "priority": 1,
                "available": True,
                "rate_limit_delay": 1.5,
            }

        if not self.providers:
            raise ValueError("No search providers configured in web_search section")

    def _get_best_provider(self) -> Optional[str]:
        """Get the best available provider"""
        available_providers = [
            (name, config)
            for name, config in self.providers.items()
            if config.get("available", False)
        ]

        if not available_providers:
            return None

        available_providers.sort(key=lambda x: x[1]["priority"])
        return available_providers[0][0]

    async def search_web(
        self, query: str, max_results: int = 10, country: str = "US", language: str = "en"
    ) -> SearchResponse:
        """Perform web search using the current provider with rate limiting"""
        start_time = time.time()

        if not self.current_provider:
            return SearchResponse(
                query=query,
                results=[],
                total_results=0,
                search_time=0.0,
                provider="none",
                status="error",
                error="No search provider available",
            )

        # Rate limiting
        provider_config = self.providers[self.current_provider]
        if "last_request_time" in provider_config:
            last_request_time = provider_config["last_request_time"]
            if last_request_time is not None:
                elapsed = time.time() - last_request_time
                delay = provider_config.get("rate_limit_delay", 1.0)
                if delay is None or not isinstance(delay, (int, float)):
                    delay = 1.0
                if isinstance(elapsed, (int, float)) and elapsed < delay:
                    await asyncio.sleep(delay - elapsed)

        provider_config["last_request_time"] = time.time()

        try:
            if self.current_provider == "brave":
                return await self._search_brave(query, max_results, country)
            elif self.current_provider == "aves":
                return await self._search_aves(query, max_results)
            else:
                raise ValueError(f"Unknown provider: {self.current_provider}")

        except Exception as e:
            search_time = time.time() - start_time

            # Mark provider as temporarily unavailable on certain errors
            error_str = str(e).lower()
            if any(keyword in error_str for keyword in ["429", "rate limit", "quota exceeded"]):
                self.providers[self.current_provider]["available"] = False
                self.providers[self.current_provider]["cooldown_until"] = time.time() + 300

            # Try fallback provider
            fallback = self._try_fallback_provider()
            if fallback:
                return await self.search_web(query, max_results, country, language)

            return SearchResponse(
                query=query,
                results=[],
                total_results=0,
                search_time=search_time,
                provider=self.current_provider,
                status="error",
                error=str(e),
            )

    async def _search_brave(self, query: str, max_results: int, country: str) -> SearchResponse:
        """Search using Brave Search API"""
        start_time = time.time()

        provider_config = self.providers["brave"]

        headers = {
            "Accept": "application/json",
            "Accept-Encoding": "gzip",
            "X-Subscription-Token": provider_config["api_key"],
        }

        params = {
            "q": query,
            "count": min(max_results, 20),
            "country": country,
            "search_lang": "en",
            "ui_lang": "en-US",
            "freshness": "pd",
        }

        try:
            response = requests.get(
                provider_config["base_url"], headers=headers, params=params, timeout=15
            )

            if response.status_code == 429:
                retry_after = response.headers.get("Retry-After", "300")
                raise Exception(f"Rate limit exceeded. Retry after {retry_after} seconds")
            elif response.status_code == 401:
                raise Exception(f"Authentication failed - check Brave API key")
            elif response.status_code == 403:
                raise Exception(f"Brave API access forbidden - check subscription")

            response.raise_for_status()

            data = response.json()
            search_time = time.time() - start_time

            results = []
            web_results = data.get("web", {}).get("results", [])

            for i, result in enumerate(web_results[:max_results]):
                results.append(
                    SearchResult(
                        title=result.get("title", ""),
                        url=result.get("url", ""),
                        snippet=result.get("description", ""),
                        source="brave",
                        rank=i + 1,
                        score=1.0 - (i * 0.1),
                        timestamp=datetime.now(),
                    )
                )

            return SearchResponse(
                query=query,
                results=results,
                total_results=len(results),
                search_time=search_time,
                provider="brave",
                status="success",
            )

        except Exception as e:
            search_time = time.time() - start_time
            raise Exception(f"Brave Search API error: {e}")

    async def _search_aves(self, query: str, max_results: int) -> SearchResponse:
        """Search using AVES API"""
        start_time = time.time()

        provider_config = self.providers["aves"]

        headers = {"User-Agent": "AmbivoAgentSystem/1.0"}

        params = {
            "apikey": provider_config["api_key"],
            "type": "web",
            "query": query,
            "device": "desktop",
            "output": "json",
            "num": min(max_results, 10),
        }

        try:
            response = requests.get(
                provider_config["base_url"], headers=headers, params=params, timeout=15
            )

            if response.status_code == 403:
                raise Exception(f"AVES API access forbidden - check API key or quota")
            elif response.status_code == 401:
                raise Exception(f"AVES API authentication failed - invalid API key")
            elif response.status_code == 429:
                raise Exception(f"AVES API rate limit exceeded")

            response.raise_for_status()

            data = response.json()
            search_time = time.time() - start_time

            results = []

            result_section = data.get("result", {})
            search_results = result_section.get("organic_results", [])

            if not search_results:
                search_results = data.get(
                    "organic_results", data.get("results", data.get("items", data.get("data", [])))
                )

            for i, result in enumerate(search_results[:max_results]):
                title = result.get("title", "No Title")
                url = result.get("url", result.get("link", result.get("href", "")))
                snippet = result.get(
                    "description", result.get("snippet", result.get("summary", ""))
                )
                position = result.get("position", i + 1)

                results.append(
                    SearchResult(
                        title=title,
                        url=url,
                        snippet=snippet,
                        source="aves",
                        rank=position,
                        score=result.get("score", 1.0 - (i * 0.1)),
                        timestamp=datetime.now(),
                    )
                )

            total_results_count = result_section.get("total_results", len(results))

            return SearchResponse(
                query=query,
                results=results,
                total_results=total_results_count,
                search_time=search_time,
                provider="aves",
                status="success",
            )

        except Exception as e:
            search_time = time.time() - start_time
            raise Exception(f"AVES Search API error: {e}")

    def _try_fallback_provider(self) -> bool:
        """Try to switch to a fallback provider"""
        current_priority = self.providers[self.current_provider]["priority"]

        fallback_providers = [
            (name, config)
            for name, config in self.providers.items()
            if config["priority"] > current_priority and config.get("available", False)
        ]

        if fallback_providers:
            fallback_providers.sort(key=lambda x: x[1]["priority"])
            self.current_provider = fallback_providers[0][0]
            return True

        return False

    async def search_news(
        self, query: str, max_results: int = 10, days_back: int = 7
    ) -> SearchResponse:
        """Search for news articles"""
        news_query = f"{query} news latest recent"
        return await self.search_web(news_query, max_results)

    async def search_academic(self, query: str, max_results: int = 10) -> SearchResponse:
        """Search for academic content"""
        academic_query = f"{query} research paper study academic"
        return await self.search_web(academic_query, max_results)


class WebSearchAgent(BaseAgent, WebAgentHistoryMixin):
    """LLM-Aware Web Search Agent with conversation context and intelligent routing"""

    def __init__(
        self,
        agent_id: str = None,
        memory_manager=None,
        llm_service=None,
        system_message: str = None,
        **kwargs,
    ):
        if agent_id is None:
            agent_id = f"search_{str(uuid.uuid4())[:8]}"

        default_system = """You are a specialized web search agent with the following capabilities:
            - Perform comprehensive web searches using multiple search engines and APIs
            - Provide accurate, current information from reliable sources
            - Remember search queries and results from previous conversations
            - Understand context references like "search for more about that" or "find recent news on this topic"
            - Synthesize information from multiple sources into coherent responses
            - Cite sources appropriately and indicate information freshness"""

        super().__init__(
            agent_id=agent_id,
            role=AgentRole.RESEARCHER,
            memory_manager=memory_manager,
            llm_service=llm_service,
            name="Web Search Agent",
            description="LLM-aware web search agent with conversation history",
            system_message=system_message or default_system,
            **kwargs,
        )

        # Initialize history mixin
        self.setup_history_mixin()

        # Initialize search service
        try:
            self.search_service = WebSearchServiceAdapter()
        except Exception as e:
            raise RuntimeError(f"Failed to initialize Web Search Service: {e}")

        # Add web search tools
        self._add_search_tools()

    async def _llm_analyze_intent(
        self, user_message: str, conversation_context: str = ""
    ) -> Dict[str, Any]:
        """Use LLM to analyze user intent and extract relevant information"""
        if not self.llm_service:
            # Fallback to keyword-based analysis
            return self._keyword_based_analysis(user_message)

        prompt = f"""
        Analyze this user message in the context of a web search conversation and extract:
        1. Primary intent (search_general, search_news, search_academic, refine_search, help_request)
        2. Search query/terms (clean and optimized for search)
        3. Search type preferences (web, news, academic, images)
        4. Context references (referring to previous searches, "this", "that", "more about")
        5. Specific requirements (time range, source type, country, etc.)

        Conversation Context:
        {conversation_context}

        Current User Message: {user_message}

        Respond in JSON format:
        {{
            "primary_intent": "search_general|search_news|search_academic|refine_search|help_request",
            "search_query": "optimized search terms",
            "search_type": "web|news|academic",
            "uses_context_reference": true/false,
            "context_type": "previous_search|previous_result|general",
            "requirements": {{
                "time_range": "recent|specific_date|any",
                "max_results": number,
                "country": "country_code",
                "language": "language_code"
            }},
            "confidence": 0.0-1.0
        }}
        """

        try:
            response = await self.llm_service.generate_response(prompt)
            # Try to parse JSON response
            import re

            json_match = re.search(r"\{.*\}", response, re.DOTALL)
            if json_match:
                return json.loads(json_match.group())
            else:
                # If LLM doesn't return JSON, extract key information
                return self._extract_intent_from_llm_response(response, user_message)
        except Exception as e:
            # Fallback to keyword analysis
            return self._keyword_based_analysis(user_message)

    def _keyword_based_analysis(self, user_message: str) -> Dict[str, Any]:
        """Fallback keyword-based intent analysis"""
        content_lower = user_message.lower()

        # Determine intent
        if any(word in content_lower for word in ["news", "latest", "recent", "breaking"]):
            intent = "search_news"
            search_type = "news"
        elif any(
            word in content_lower for word in ["research", "academic", "paper", "study", "journal"]
        ):
            intent = "search_academic"
            search_type = "academic"
        elif any(word in content_lower for word in ["search", "find", "look up", "google"]):
            intent = "search_general"
            search_type = "web"
        elif any(word in content_lower for word in ["help", "how to", "what can"]):
            intent = "help_request"
            search_type = "web"
        else:
            intent = "search_general"
            search_type = "web"

        # Extract query
        query = self._extract_query_from_message(user_message)

        # Check for context references
        context_words = ["this", "that", "it", "them", "more", "similar", "related"]
        uses_context = any(word in content_lower for word in context_words)

        return {
            "primary_intent": intent,
            "search_query": query,
            "search_type": search_type,
            "uses_context_reference": uses_context,
            "context_type": "previous_search" if uses_context else "none",
            "requirements": {
                "time_range": "recent" if "recent" in content_lower else "any",
                "max_results": 5,
                "country": "US",
                "language": "en",
            },
            "confidence": 0.7,
        }

    def _extract_intent_from_llm_response(
        self, llm_response: str, user_message: str
    ) -> Dict[str, Any]:
        """Extract intent from LLM response that isn't JSON"""
        # Simple extraction from LLM text response
        content_lower = llm_response.lower()

        if "news" in content_lower:
            intent = "search_news"
            search_type = "news"
        elif "academic" in content_lower or "research" in content_lower:
            intent = "search_academic"
            search_type = "academic"
        else:
            intent = "search_general"
            search_type = "web"

        return {
            "primary_intent": intent,
            "search_query": self._extract_query_from_message(user_message),
            "search_type": search_type,
            "uses_context_reference": False,
            "context_type": "none",
            "requirements": {"max_results": 5, "country": "US", "language": "en"},
            "confidence": 0.6,
        }

    async def process_message(
        self, message: AgentMessage, context: ExecutionContext = None
    ) -> AgentMessage:
        """Process message with LLM-based intent detection - FIXED: Context preserved across provider switches"""
        self.memory.store_message(message)

        try:
            user_message = message.content

            # Update conversation state
            self.update_conversation_state(user_message)

            # 🔥 FIX: Get conversation context AND conversation history
            conversation_context = self._get_conversation_context_summary()
            conversation_history = []

            try:
                conversation_history = await self.get_conversation_history(
                    limit=5, include_metadata=True
                )
            except Exception as e:
                print(f"Could not get conversation history: {e}")

            # 🔥 FIX: Build LLM context with conversation history
            llm_context = {
                "conversation_history": conversation_history,  # 🔥 KEY FIX
                "conversation_id": message.conversation_id,
                "user_id": message.sender_id,
                "agent_type": "web_search",
            }

            # 🔥 FIX: Use LLM to analyze intent WITH CONTEXT
            intent_analysis = await self._llm_analyze_intent_with_context(
                user_message, conversation_context, llm_context
            )

            # Route request based on LLM analysis with context
            response_content = await self._route_with_llm_analysis_with_context(
                intent_analysis, user_message, context, llm_context
            )

            response = self.create_response(
                content=response_content,
                recipient_id=message.sender_id,
                session_id=message.session_id,
                conversation_id=message.conversation_id,
            )

            self.memory.store_message(response)
            return response

        except Exception as e:
            error_response = self.create_response(
                content=f"Web Search Agent error: {str(e)}",
                recipient_id=message.sender_id,
                message_type=MessageType.ERROR,
                session_id=message.session_id,
                conversation_id=message.conversation_id,
            )
            return error_response

    async def _llm_analyze_intent_with_context(
        self, user_message: str, conversation_context: str = "", llm_context: Dict[str, Any] = None
    ) -> Dict[str, Any]:
        """Use LLM to analyze user intent - FIXED: With conversation context"""
        if not self.llm_service:
            return self._keyword_based_analysis(user_message)

        prompt = f"""
        Analyze this user message in the context of a web search conversation and extract:
        1. Primary intent (search_general, search_news, search_academic, refine_search, help_request)
        2. Search query/terms (clean and optimized for search)
        3. Search type preferences (web, news, academic, images)
        4. Context references (referring to previous searches, "this", "that", "more about")
        5. Specific requirements (time range, source type, country, etc.)

        Conversation Context:
        {conversation_context}

        Current User Message: {user_message}

        Respond in JSON format:
        {{
            "primary_intent": "search_general|search_news|search_academic|refine_search|help_request",
            "search_query": "optimized search terms",
            "search_type": "web|news|academic",
            "uses_context_reference": true/false,
            "context_type": "previous_search|previous_result|general",
            "requirements": {{
                "time_range": "recent|specific_date|any",
                "max_results": number,
                "country": "country_code",
                "language": "language_code"
            }},
            "confidence": 0.0-1.0
        }}
        """

        try:
            enhanced_system_message = self.get_system_message_for_llm(llm_context)
            response = await self.llm_service.generate_response(
                prompt=prompt, context=llm_context, system_message=enhanced_system_message
            )

            import re

            json_match = re.search(r"\{.*\}", response, re.DOTALL)
            if json_match:
                return json.loads(json_match.group())
            else:
                return self._extract_intent_from_llm_response(response, user_message)
        except Exception as e:
            print(f"LLM intent analysis failed: {e}")
            return self._keyword_based_analysis(user_message)

    async def _route_with_llm_analysis_with_context(
        self,
        intent_analysis: Dict[str, Any],
        user_message: str,
        context: ExecutionContext,
        llm_context: Dict[str, Any],
    ) -> str:
        """Route request based on LLM intent analysis - FIXED: With context preservation"""

        primary_intent = intent_analysis.get("primary_intent", "search_general")
        search_query = intent_analysis.get("search_query", "")
        search_type = intent_analysis.get("search_type", "web")
        uses_context = intent_analysis.get("uses_context_reference", False)
        requirements = intent_analysis.get("requirements", {})

        # Handle context references
        if uses_context and not search_query:
            search_query = self._resolve_contextual_query(user_message)

        # Route based on intent
        if primary_intent == "help_request":
            return await self._handle_help_request_with_context(user_message, llm_context)
        elif primary_intent == "search_news":
            return await self._handle_news_search(search_query, requirements)
        elif primary_intent == "search_academic":
            return await self._handle_academic_search(search_query, requirements)
        elif primary_intent == "refine_search":
            return await self._handle_search_refinement(search_query, user_message)
        else:  # search_general
            return await self._handle_general_search(search_query, requirements)

    async def _handle_help_request_with_context(
        self, user_message: str, llm_context: Dict[str, Any]
    ) -> str:
        """Handle help requests with conversation context - FIXED: Context preserved"""

        # Use LLM for more intelligent help if available
        if self.llm_service and llm_context.get("conversation_history"):
            help_prompt = f"""As a web search assistant, provide helpful guidance for: {user_message}

    Consider the user's previous search queries and provide contextual assistance."""

            try:
                enhanced_system_message = self.get_system_message_for_llm(llm_context)
                intelligent_help = await self.llm_service.generate_response(
                    prompt=help_prompt, context=llm_context, system_message=enhanced_system_message
                )
                return intelligent_help
            except Exception as e:
                print(f"LLM help generation failed: {e}")

        # Fallback to standard help message
        recent_search = self.get_recent_search_term()

        base_message = (
            "I'm your Web Search Agent! I can help you with:\n\n"
            "🔍 **Web Search** - General information search\n"
            "📰 **News Search** - Latest news and current events  \n"
            "🎓 **Academic Search** - Research papers and studies\n\n"
            "💡 **Examples:**\n"
            "• 'Search for AI trends in 2025'\n"
            "• 'Find latest news about quantum computing'\n"
            "• 'Look up machine learning research papers'\n"
        )

        if recent_search:
            base_message += f"\n🎯 **Your last search:** {recent_search}\n"
            base_message += "You can say things like 'more about this' or 'find similar topics'"

        return base_message

    def _get_conversation_context_summary(self) -> str:
        """Get a summary of recent conversation for LLM context"""
        try:
            recent_history = self.get_conversation_history_with_context(
                limit=3, context_types=[ContextType.SEARCH_TERM]
            )

            context_summary = []
            for msg in recent_history:
                if msg.get("message_type") == "user_input":
                    content = msg.get("content", "")
                    extracted_context = msg.get("extracted_context", {})
                    search_terms = extracted_context.get("search_term", [])

                    if search_terms:
                        context_summary.append(f"Previous search: {search_terms[0]}")
                    else:
                        context_summary.append(f"Previous message: {content[:50]}...")

            return "\n".join(context_summary) if context_summary else "No previous context"
        except:
            return "No previous context"

    async def _route_with_llm_analysis(
        self, intent_analysis: Dict[str, Any], user_message: str, context: ExecutionContext
    ) -> str:
        """Route request based on LLM intent analysis"""

        primary_intent = intent_analysis.get("primary_intent", "search_general")
        search_query = intent_analysis.get("search_query", "")
        search_type = intent_analysis.get("search_type", "web")
        uses_context = intent_analysis.get("uses_context_reference", False)
        requirements = intent_analysis.get("requirements", {})

        # Handle context references
        if uses_context and not search_query:
            search_query = self._resolve_contextual_query(user_message)

        # Route based on intent
        if primary_intent == "help_request":
            return await self._handle_help_request(user_message)
        elif primary_intent == "search_news":
            return await self._handle_news_search(search_query, requirements)
        elif primary_intent == "search_academic":
            return await self._handle_academic_search(search_query, requirements)
        elif primary_intent == "refine_search":
            return await self._handle_search_refinement(search_query, user_message)
        else:  # search_general
            return await self._handle_general_search(search_query, requirements)

    def _resolve_contextual_query(self, user_message: str) -> str:
        """Resolve contextual references to create a search query"""
        recent_search = self.get_recent_search_term()

        if recent_search:
            # Check for refinement patterns
            refinement_words = ["more", "additional", "other", "similar", "related", "about this"]
            if any(word in user_message.lower() for word in refinement_words):
                return f"{recent_search} {user_message.replace('this', '').replace('that', '').strip()}"
            else:
                return recent_search

        return self._extract_query_from_message(user_message)

    async def _handle_general_search_old(self, query: str, requirements: Dict[str, Any]) -> str:
        """Handle general web search"""
        if not query:
            return self._get_search_help_message()

        try:
            max_results = requirements.get("max_results", 5)
            result = await self._search_web(query, max_results=max_results)

            if result["success"]:
                return self._format_search_results(result, "General Search")
            else:
                return f"❌ **Search failed:** {result['error']}"

        except Exception as e:
            return f"❌ **Error during search:** {str(e)}"

    async def _handle_news_search(self, query: str, requirements: Dict[str, Any]) -> str:
        """Handle news search"""
        if not query:
            return "I can search for news articles. What news topic are you interested in?"

        try:
            max_results = requirements.get("max_results", 5)
            result = await self._search_news(query, max_results=max_results)

            if result["success"]:
                return self._format_search_results(result, "News Search")
            else:
                return f"❌ **News search failed:** {result['error']}"

        except Exception as e:
            return f"❌ **Error during news search:** {str(e)}"

    async def _handle_academic_search(self, query: str, requirements: Dict[str, Any]) -> str:
        """Handle academic search"""
        if not query:
            return "I can search for academic papers and research. What research topic are you looking for?"

        try:
            max_results = requirements.get("max_results", 5)
            result = await self._search_academic(query, max_results=max_results)

            if result["success"]:
                return self._format_search_results(result, "Academic Search")
            else:
                return f"❌ **Academic search failed:** {result['error']}"

        except Exception as e:
            return f"❌ **Error during academic search:** {str(e)}"

    async def _handle_search_refinement(self, query: str, user_message: str) -> str:
        """Handle search refinement requests"""
        recent_search = self.get_recent_search_term()

        if recent_search:
            refined_query = f"{recent_search} {query}".strip()
            result = await self._search_web(refined_query, max_results=5)

            if result["success"]:
                return (
                    f"🔍 **Refined Search Results**\n\n"
                    f"**Original:** {recent_search}\n"
                    f"**Refined:** {refined_query}\n\n"
                    + self._format_search_results(result, "Refined Search", show_header=False)
                )
            else:
                return f"❌ **Refined search failed:** {result['error']}"
        else:
            return await self._handle_general_search(query, {"max_results": 5})

    async def _handle_help_request(self, user_message: str) -> str:
        """Handle help requests"""
        return self._get_search_help_message()

    def _format_search_results_old(
        self, result: Dict[str, Any], search_type: str, show_header: bool = True
    ) -> str:
        """Format search results consistently"""
        results = result.get("results", [])
        query = result.get("query", "")

        if show_header:
            response = f"🔍 **{search_type} Results for:** {query}\n\n"
        else:
            response = ""

        if results:
            response += f"📊 **Found {len(results)} results:**\n\n"
            for i, res in enumerate(results[:3], 1):
                response += f"**{i}. {res['title']}**\n"
                response += f"🔗 {res['url']}\n"
                response += f"📝 {res['snippet'][:150]}...\n\n"

            provider = result.get("provider", "search engine")
            search_time = result.get("search_time", 0)
            response += f"⏱️ **Search completed in {search_time:.2f}s using {provider}**"
        else:
            response += "No results found. Try a different search term."

        return response

    def _format_search_results(
        self, result: Dict[str, Any], search_type: str, show_header: bool = True
    ) -> str:
        """Format search results consistently - FIXED VERSION"""
        results = result.get("results", [])
        query = result.get("query", "")

        if show_header:
            response = f"🔍 **{search_type} Results for:** {query}\n\n"
        else:
            response = ""

        if results:
            response += f"📊 **Found {len(results)} results:**\n\n"

            # FIXED: Safe iteration over results
            for i, res in enumerate(results):
                if i >= 3:  # Limit to 3 results
                    break

                # FIXED: Safe access to result properties
                title = res.get("title", "No title") or "No title"
                url = res.get("url", "No URL") or "No URL"
                snippet = res.get("snippet", "No description") or "No description"

                # FIXED: Safe string slicing
                snippet_preview = str(snippet)[:150]
                if len(str(snippet)) > 150:
                    snippet_preview += "..."

                response += f"**{i + 1}. {title}**\n"
                response += f"🔗 {url}\n"
                response += f"📝 {snippet_preview}\n\n"

            # FIXED: Safe access to result metadata
            provider = result.get("provider", "search engine")
            search_time = result.get("search_time", 0)

            # FIXED: Ensure search_time is a number
            if not isinstance(search_time, (int, float)):
                search_time = 0

            response += f"⏱️ **Search completed in {search_time:.2f}s using {provider}**"
        else:
            response += "No results found. Try a different search term."

        return response

    async def _handle_general_search(self, query: str, requirements: Dict[str, Any]) -> str:
        """Handle general web search - FIXED VERSION"""
        if not query:
            return self._get_search_help_message()

        try:
            # FIXED: Safe access to requirements
            max_results = requirements.get("max_results", 5)
            if not isinstance(max_results, int) or max_results is None:
                max_results = 5

            result = await self._search_web(query, max_results=max_results)

            if result["success"]:
                return self._format_search_results(result, "General Search")
            else:
                error_msg = result.get("error", "Unknown error")
                return f"❌ **Search failed:** {error_msg}"

        except Exception as e:
            return f"❌ **Error during search:** {str(e)}"

    def _get_search_help_message(self) -> str:
        """Get contextual help message"""
        recent_search = self.get_recent_search_term()

        base_message = (
            "I'm your Web Search Agent! I can help you with:\n\n"
            "🔍 **Web Search** - General information search\n"
            "📰 **News Search** - Latest news and current events  \n"
            "🎓 **Academic Search** - Research papers and studies\n\n"
            "💡 **Examples:**\n"
            "• 'Search for AI trends in 2025'\n"
            "• 'Find latest news about quantum computing'\n"
            "• 'Look up machine learning research papers'\n"
        )

        if recent_search:
            base_message += f"\n🎯 **Your last search:** {recent_search}\n"
            base_message += "You can say things like 'more about this' or 'find similar topics'"

        return base_message

    def _extract_query_from_message(self, message: str) -> str:
        """Extract clean search query from message"""
        # Remove common search prefixes
        prefixes = [
            "search for",
            "find",
            "look up",
            "search",
            "find me",
            "look for",
            "google",
            "search about",
            "tell me about",
        ]

        query = message.strip()
        for prefix in prefixes:
            if query.lower().startswith(prefix):
                query = query[len(prefix) :].strip()
                break

        return query

    # Tool implementations
    def _add_search_tools(self):
        """Add web search related tools"""

        # General web search tool
        self.add_tool(
            AgentTool(
                name="search_web",
                description="Search the web for information",
                function=self._search_web,
                parameters_schema={
                    "type": "object",
                    "properties": {
                        "query": {"type": "string", "description": "Search query"},
                        "max_results": {
                            "type": "integer",
                            "default": 10,
                            "description": "Maximum number of results",
                        },
                        "country": {
                            "type": "string",
                            "default": "US",
                            "description": "Country for search results",
                        },
                        "language": {
                            "type": "string",
                            "default": "en",
                            "description": "Language for search results",
                        },
                    },
                    "required": ["query"],
                },
            )
        )

        # News search tool
        self.add_tool(
            AgentTool(
                name="search_news",
                description="Search for recent news articles",
                function=self._search_news,
                parameters_schema={
                    "type": "object",
                    "properties": {
                        "query": {"type": "string", "description": "News search query"},
                        "max_results": {
                            "type": "integer",
                            "default": 10,
                            "description": "Maximum number of results",
                        },
                        "days_back": {
                            "type": "integer",
                            "default": 7,
                            "description": "How many days back to search",
                        },
                    },
                    "required": ["query"],
                },
            )
        )

        # Academic search tool
        self.add_tool(
            AgentTool(
                name="search_academic",
                description="Search for academic papers and research",
                function=self._search_academic,
                parameters_schema={
                    "type": "object",
                    "properties": {
                        "query": {"type": "string", "description": "Academic search query"},
                        "max_results": {
                            "type": "integer",
                            "default": 10,
                            "description": "Maximum number of results",
                        },
                    },
                    "required": ["query"],
                },
            )
        )

    async def _search_web(
        self, query: str, max_results: int = 10, country: str = "US", language: str = "en"
    ) -> Dict[str, Any]:
        """Perform web search"""
        try:
            search_response = await self.search_service.search_web(
                query=query, max_results=max_results, country=country, language=language
            )

            if search_response.status == "success":
                results_data = []
                for result in search_response.results:
                    results_data.append(
                        {
                            "title": result.title,
                            "url": result.url,
                            "snippet": result.snippet,
                            "rank": result.rank,
                            "score": result.score,
                        }
                    )

                return {
                    "success": True,
                    "query": query,
                    "results": results_data,
                    "total_results": search_response.total_results,
                    "search_time": search_response.search_time,
                    "provider": search_response.provider,
                }
            else:
                return {
                    "success": False,
                    "error": search_response.error,
                    "provider": search_response.provider,
                }

        except Exception as e:
            return {"success": False, "error": str(e)}

    async def _search_news(
        self, query: str, max_results: int = 10, days_back: int = 7
    ) -> Dict[str, Any]:
        """Search for news articles"""
        try:
            search_response = await self.search_service.search_news(
                query=query, max_results=max_results, days_back=days_back
            )

            return await self._format_search_response(search_response, "news")

        except Exception as e:
            return {"success": False, "error": str(e)}

    async def _search_academic(self, query: str, max_results: int = 10) -> Dict[str, Any]:
        """Search for academic content"""
        try:
            search_response = await self.search_service.search_academic(
                query=query, max_results=max_results
            )

            return await self._format_search_response(search_response, "academic")

        except Exception as e:
            return {"success": False, "error": str(e)}

    async def _format_search_response(self, search_response, search_type: str) -> Dict[str, Any]:
        """Format search response for consistent output"""
        if search_response.status == "success":
            results_data = []
            for result in search_response.results:
                results_data.append(
                    {
                        "title": result.title,
                        "url": result.url,
                        "snippet": result.snippet,
                        "rank": result.rank,
                        "score": result.score,
                        "source": result.source,
                    }
                )

            return {
                "success": True,
                "search_type": search_type,
                "query": search_response.query,
                "results": results_data,
                "total_results": search_response.total_results,
                "search_time": search_response.search_time,
                "provider": search_response.provider,
            }
        else:
            return {
                "success": False,
                "search_type": search_type,
                "error": search_response.error,
                "provider": search_response.provider,
            }

    async def process_message_stream(
        self, message: AgentMessage, context: ExecutionContext = None
    ) -> AsyncIterator[StreamChunk]:
        """Stream web search operations - FIXED: Context preserved across provider switches"""
        self.memory.store_message(message)

        try:
            user_message = message.content
            self.update_conversation_state(user_message)

            yield StreamChunk(
                text="**Web Search Agent**\n\n",
                sub_type=StreamSubType.STATUS,
                metadata={"agent": "web_search", "phase": "initialization"},
            )

            # 🔥 FIX: Get conversation context for streaming
            conversation_context = self._get_conversation_context_summary()
            conversation_history = await self.get_conversation_history(
                limit=5, include_metadata=True
            )

            yield StreamChunk(
                text="Analyzing search request...\n",
                sub_type=StreamSubType.STATUS,
                metadata={"agent": "web_search", "phase": "analysis"},
            )

            # 🔥 FIX: Build LLM context for streaming
            llm_context = {
                "conversation_history": conversation_history,  # 🔥 KEY FIX
                "conversation_id": message.conversation_id,
                "streaming": True,
            }

            intent_analysis = await self._llm_analyze_intent(user_message, conversation_context)

            primary_intent = intent_analysis.get("primary_intent", "search_general")
            search_query = intent_analysis.get("search_query", "")
            search_type = intent_analysis.get("search_type", "web")

            if primary_intent == "search_news":
                yield StreamChunk(
                    text="**News Search**\n\n",
                    sub_type=StreamSubType.STATUS,
                    metadata={"search_type": "news", "query": search_query},
                )
                async for chunk in self._stream_news_search_with_context(
                    search_query, intent_analysis.get("requirements", {}), llm_context
                ):
                    yield chunk

            elif primary_intent == "search_academic":
                yield StreamChunk(
                    text="**Academic Search**\n\n",
                    sub_type=StreamSubType.STATUS,
                    metadata={"search_type": "academic", "query": search_query},
                )
                async for chunk in self._stream_academic_search_with_context(
                    search_query, intent_analysis.get("requirements", {}), llm_context
                ):
                    yield chunk

            else:
                yield StreamChunk(
                    text="**Web Search**\n\n",
                    sub_type=StreamSubType.STATUS,
                    metadata={"search_type": "general", "query": search_query},
                )
                async for chunk in self._stream_general_search_with_context(
                    search_query, intent_analysis.get("requirements", {}), llm_context
                ):
                    yield chunk

        except Exception as e:
            yield StreamChunk(
                text=f"**Web Search Error:** {str(e)}",
                sub_type=StreamSubType.ERROR,
                metadata={"error": True, "error_message": str(e)},
            )

    async def _stream_general_search_with_context(
        self, query: str, requirements: dict, llm_context: Dict[str, Any]
    ) -> AsyncIterator[StreamChunk]:
        """Stream general web search with context preservation"""
        try:
            if not query:
                yield StreamChunk(
                    text="Please provide a search query.\n", sub_type=StreamSubType.ERROR
                )
                return

            yield StreamChunk(
                text=f"**Searching for:** {query}\n\n",
                sub_type=StreamSubType.STATUS,
                metadata={"query": query},
            )
            yield StreamChunk(
                text="Contacting search providers...\n", sub_type=StreamSubType.STATUS
            )

            max_results = requirements.get("max_results", 5)
            provider_info = self.search_service.providers.get(
                self.search_service.current_provider, {}
            )
            provider_name = provider_info.get("name", self.search_service.current_provider)
            yield StreamChunk(
                text=f"**Using:** {provider_name}\n",
                sub_type=StreamSubType.STATUS,
                metadata={"provider": provider_name},
            )

            yield StreamChunk(text="Executing search...\n\n", sub_type=StreamSubType.STATUS)

            # Perform the search
            result = await self._search_web(query, max_results=max_results)

            if result["success"]:
                results = result.get("results", [])
                search_time = result.get("search_time", 0)

                yield StreamChunk(
                    text=f"**Found {len(results)} results in {search_time:.2f}s**\n\n",
                    sub_type=StreamSubType.RESULT,
                    metadata={"result_count": len(results), "search_time": search_time},
                )

                # Stream results one by one
                for i, res in enumerate(results, 1):
                    yield StreamChunk(
                        text=f"{i}. {res.get('title', 'No title')}**\n",
                        sub_type=StreamSubType.RESULT,
                        metadata={"result_index": i, "title": res.get("title")},
                    )
                    yield StreamChunk(
                        text=f"{res.get('url', 'No URL')}\n",
                        sub_type=StreamSubType.RESULT,
                        metadata={"url": res.get("url")},
                    )

                    snippet = res.get("snippet", "No description")
                    if len(snippet) > 150:
                        snippet = snippet[:150] + "..."
                    yield StreamChunk(
                        text=f"{snippet}\n\n",
                        sub_type=StreamSubType.RESULT,
                        metadata={"snippet": snippet},
                    )

                    if i < len(results):
                        await asyncio.sleep(0.2)

                conversation_history = llm_context.get("conversation_history", [])
                if conversation_history and self.llm_service:
                    yield StreamChunk(
                        text="**Related to your search:**\n", sub_type=StreamSubType.STATUS
                    )

                    context_prompt = f"""Based on the search results for "{query}" and our conversation history, suggest 2-3 helpful follow-up search queries that the user might find interesting."""

                    try:
                        suggestions = await self.llm_service.generate_response(
                            prompt=context_prompt, context=llm_context
                        )
                        yield StreamChunk(
                            text=f"{suggestions}\n\n",
                            sub_type=StreamSubType.CONTENT,
                            metadata={"type": "suggestions"},
                        )
                    except:
                        pass

                yield StreamChunk(
                    text=f"**Search completed using {provider_name}**\n",
                    sub_type=StreamSubType.STATUS,
                    metadata={"completed": True, "provider": provider_name},
                )
            else:
                yield StreamChunk(
                    text=f"❌ **Search failed:** {result.get('error', 'Unknown error')}\n",
                    sub_type=StreamSubType.ERROR,
                    metadata={"error": result.get("error")},
                )

        except Exception as e:
            yield StreamChunk(
                text=f"❌ **Error during search:** {str(e)}",
                sub_type=StreamSubType.ERROR,
                metadata={"error": str(e)},
            )

    async def _stream_general_search(
        self, query: str, requirements: dict
    ) -> AsyncIterator[StreamChunk]:
        """Stream general web search with incremental results"""
        try:
            if not query:
                yield StreamChunk(
                    text="⚠️ Please provide a search query.\n", sub_type=StreamSubType.ERROR
                )
                return

            yield StreamChunk(
                text=f"**Searching for:** {query}\n\n",
                sub_type=StreamSubType.STATUS,
                metadata={"query": query},
            )
            yield StreamChunk(
                text="Contacting search providers...\n", sub_type=StreamSubType.STATUS
            )

            max_results = requirements.get("max_results", 5)

            # Show which provider we're using
            provider_info = self.search_service.providers.get(
                self.search_service.current_provider, {}
            )
            provider_name = provider_info.get("name", self.search_service.current_provider)
            # yield StreamChunk(text=f"**Using:** {provider_name}\n", sub_type=StreamSubType.STATUS)

            yield StreamChunk(text="Executing search...\n\n", sub_type=StreamSubType.STATUS)

            # Perform the search
            result = await self._search_web(query, max_results=max_results)

            if result["success"]:
                results = result.get("results", [])
                search_time = result.get("search_time", 0)

                yield StreamChunk(
                    text=f"**Found {len(results)} results in {search_time:.2f}s**\n\n",
                    sub_type=StreamSubType.RESULT,
                    metadata={"result_count": len(results), "search_time": search_time},
                )

                # Stream results one by one
                for i, res in enumerate(results, 1):
                    yield StreamChunk(
                        text=f"**{i}. {res.get('title', 'No title')}**\n",
                        sub_type=StreamSubType.RESULT,
                        metadata={"result_index": i, "title": res.get("title")},
                    )
                    yield StreamChunk(
                        text=f"🔗 {res.get('url', 'No URL')}\n",
                        sub_type=StreamSubType.RESULT,
                        metadata={"url": res.get("url")},
                    )

                    snippet = res.get("snippet", "No description")
                    if len(snippet) > 150:
                        snippet = snippet[:150] + "..."
                    yield StreamChunk(
                        text=f"📝 {snippet}\n\n",
                        sub_type=StreamSubType.RESULT,
                        metadata={"snippet": snippet},
                    )

                    # Small delay between results for streaming effect
                    if i < len(results):
                        await asyncio.sleep(0.2)

                yield StreamChunk(
                    text=f"**Search completed using {provider_name}**\n",
                    sub_type=StreamSubType.STATUS,
                    metadata={"completed": True, "provider": provider_name},
                )
            else:
                yield StreamChunk(
                    text=f"❌ **Search failed:** {result.get('error', 'Unknown error')}\n",
                    sub_type=StreamSubType.ERROR,
                    metadata={"error": result.get("error")},
                )

        except Exception as e:
            yield StreamChunk(
                text=f"❌ **Error during search:** {str(e)}",
                sub_type=StreamSubType.ERROR,
                metadata={"error": str(e)},
            )

    async def _stream_news_search(
        self, query: str, requirements: dict
    ) -> AsyncIterator[StreamChunk]:
        """Stream news search with progress"""
        try:
            if not query:
                yield StreamChunk(
                    text="⚠️ Please provide a news topic to search for.\n",
                    sub_type=StreamSubType.ERROR,
                )
                return

            yield StreamChunk(
                text=f"📰 **Searching news for:** {query}\n\n",
                sub_type=StreamSubType.STATUS,
                metadata={"query": query, "search_type": "news"},
            )
            yield StreamChunk(
                text="⏳ Finding latest news articles...\n", sub_type=StreamSubType.STATUS
            )

            max_results = requirements.get("max_results", 5)

            result = await self._search_news(query, max_results=max_results)

            if result["success"]:
                results = result.get("results", [])
                yield StreamChunk(
                    text=f"📊 **Found {len(results)} news articles**\n\n",
                    sub_type=StreamSubType.RESULT,
                    metadata={"result_count": len(results), "search_type": "news"},
                )

                # Stream news results
                for i, res in enumerate(results, 1):
                    yield StreamChunk(
                        text=f"📰 **{i}. {res.get('title', 'No title')}**\n",
                        sub_type=StreamSubType.RESULT,
                        metadata={"result_index": i, "title": res.get("title")},
                    )
                    yield StreamChunk(
                        text=f"🔗 {res.get('url', 'No URL')}\n",
                        sub_type=StreamSubType.RESULT,
                        metadata={"url": res.get("url")},
                    )
                    yield StreamChunk(
                        text=f"📝 {res.get('snippet', 'No description')[:150]}...\n\n",
                        sub_type=StreamSubType.RESULT,
                        metadata={"snippet": res.get("snippet", "")[:150]},
                    )

                    if i < len(results):
                        await asyncio.sleep(0.3)

                yield StreamChunk(
                    text="**News search completed**\n",
                    sub_type=StreamSubType.STATUS,
                    metadata={"completed": True, "search_type": "news"},
                )
            else:
                yield StreamChunk(
                    text=f"❌ **News search failed:** {result.get('error', 'Unknown error')}\n",
                    sub_type=StreamSubType.ERROR,
                    metadata={"error": result.get("error")},
                )

        except Exception as e:
            yield StreamChunk(
                text=f"❌ **Error during news search:** {str(e)}",
                sub_type=StreamSubType.ERROR,
                metadata={"error": str(e)},
            )

    async def _stream_academic_search(
        self, query: str, requirements: dict
    ) -> AsyncIterator[StreamChunk]:
        """Stream academic search with progress"""
        try:
            if not query:
                yield StreamChunk(
                    text="⚠️ Please provide an academic topic to search for.\n",
                    sub_type=StreamSubType.ERROR,
                )
                return

            yield StreamChunk(
                text=f"🎓 **Searching academic content for:** {query}\n\n",
                sub_type=StreamSubType.STATUS,
                metadata={"query": query, "search_type": "academic"},
            )
            yield StreamChunk(
                text="⏳ Finding research papers and studies...\n", sub_type=StreamSubType.STATUS
            )

            max_results = requirements.get("max_results", 5)

            result = await self._search_academic(query, max_results=max_results)

            if result["success"]:
                results = result.get("results", [])
                yield StreamChunk(
                    text=f"📊 **Found {len(results)} academic sources**\n\n",
                    sub_type=StreamSubType.RESULT,
                    metadata={"result_count": len(results), "search_type": "academic"},
                )

                # Stream academic results
                for i, res in enumerate(results, 1):
                    yield StreamChunk(
                        text=f"🎓 **{i}. {res.get('title', 'No title')}**\n",
                        sub_type=StreamSubType.RESULT,
                        metadata={"result_index": i, "title": res.get("title")},
                    )
                    yield StreamChunk(
                        text=f"🔗 {res.get('url', 'No URL')}\n",
                        sub_type=StreamSubType.RESULT,
                        metadata={"url": res.get("url")},
                    )
                    yield StreamChunk(
                        text=f"📝 {res.get('snippet', 'No description')[:150]}...\n\n",
                        sub_type=StreamSubType.RESULT,
                        metadata={"snippet": res.get("snippet", "")[:150]},
                    )

                    if i < len(results):
                        await asyncio.sleep(0.3)

                yield StreamChunk(
                    text="**Academic search completed**\n",
                    sub_type=StreamSubType.STATUS,
                    metadata={"completed": True, "search_type": "academic"},
                )
            else:
                yield StreamChunk(
                    text=f"❌ **Academic search failed:** {result.get('error', 'Unknown error')}\n",
                    sub_type=StreamSubType.ERROR,
                    metadata={"error": result.get("error")},
                )

        except Exception as e:
            yield StreamChunk(
                text=f"❌ **Error during academic search:** {str(e)}",
                sub_type=StreamSubType.ERROR,
                metadata={"error": str(e)},
            )

    async def _stream_news_search_with_context(
        self, query: str, requirements: dict, llm_context: Dict[str, Any]
    ) -> AsyncIterator[StreamChunk]:
        """Stream news search with context preservation"""
        try:
            if not query:
                yield StreamChunk(
                    text="Please provide a news topic to search for.\n",
                    sub_type=StreamSubType.ERROR,
                )
                return

            yield StreamChunk(
                text=f"**Searching news for:** {query}\n\n",
                sub_type=StreamSubType.STATUS,
                metadata={"query": query, "search_type": "news"},
            )
            yield StreamChunk(
                text="Finding latest news articles...\n", sub_type=StreamSubType.STATUS
            )

            max_results = requirements.get("max_results", 5)

            result = await self._search_news(query, max_results=max_results)

            if result["success"]:
                results = result.get("results", [])
                search_time = result.get("search_time", 0)

                yield StreamChunk(
                    text=f"**Found {len(results)} news articles in {search_time:.2f}s**\n\n",
                    sub_type=StreamSubType.RESULT,
                    metadata={"result_count": len(results), "search_time": search_time},
                )

                # Stream news results one by one
                for i, res in enumerate(results, 1):
                    yield StreamChunk(
                        text=f"{i}. **{res.get('title', 'No title')}**\n",
                        sub_type=StreamSubType.RESULT,
                        metadata={"result_index": i, "title": res.get("title")},
                    )
                    yield StreamChunk(
                        text=f"{res.get('url', 'No URL')}\n",
                        sub_type=StreamSubType.RESULT,
                        metadata={"url": res.get("url")},
                    )

                    snippet = res.get("snippet", "No description")
                    if len(snippet) > 150:
                        snippet = snippet[:150] + "..."
                    yield StreamChunk(
                        text=f"{snippet}\n\n",
                        sub_type=StreamSubType.RESULT,
                        metadata={"snippet": snippet},
                    )

                    if i < len(results):
                        await asyncio.sleep(0.2)

                # Context-aware follow-up suggestions
                conversation_history = llm_context.get("conversation_history", [])
                if conversation_history and self.llm_service:
                    yield StreamChunk(
                        text="**Related news you might find interesting:**\n",
                        sub_type=StreamSubType.STATUS,
                    )

                    context_prompt = f"""Based on the news search results for "{query}" and our conversation history, suggest 2-3 related news topics or follow-up searches that the user might find interesting."""

                    try:
                        suggestions = await self.llm_service.generate_response(
                            prompt=context_prompt, context=llm_context
                        )
                        yield StreamChunk(
                            text=f"{suggestions}\n\n",
                            sub_type=StreamSubType.CONTENT,
                            metadata={"type": "suggestions"},
                        )
                    except:
                        pass

                yield StreamChunk(
                    text="**News search completed**\n",
                    sub_type=StreamSubType.STATUS,
                    metadata={"completed": True, "search_type": "news"},
                )
            else:
                yield StreamChunk(
                    text=f"❌ **News search failed:** {result.get('error', 'Unknown error')}\n",
                    sub_type=StreamSubType.ERROR,
                    metadata={"error": result.get("error")},
                )

        except Exception as e:
            yield StreamChunk(
                text=f"❌ **Error during news search:** {str(e)}",
                sub_type=StreamSubType.ERROR,
                metadata={"error": str(e)},
            )

    async def _stream_academic_search_with_context(
        self, query: str, requirements: dict, llm_context: Dict[str, Any]
    ) -> AsyncIterator[StreamChunk]:
        """Stream academic search with context preservation"""
        try:
            if not query:
                yield StreamChunk(
                    text="Please provide an academic topic to search for.\n",
                    sub_type=StreamSubType.ERROR,
                )
                return

            yield StreamChunk(
                text=f"**Searching academic content for:** {query}\n\n",
                sub_type=StreamSubType.STATUS,
                metadata={"query": query, "search_type": "academic"},
            )
            yield StreamChunk(
                text="Finding research papers and studies...\n", sub_type=StreamSubType.STATUS
            )

            max_results = requirements.get("max_results", 5)

            result = await self._search_academic(query, max_results=max_results)

            if result["success"]:
                results = result.get("results", [])
                search_time = result.get("search_time", 0)

                yield StreamChunk(
                    text=f"**Found {len(results)} academic sources in {search_time:.2f}s**\n\n",
                    sub_type=StreamSubType.RESULT,
                    metadata={"result_count": len(results), "search_time": search_time},
                )

                # Stream academic results one by one
                for i, res in enumerate(results, 1):
                    yield StreamChunk(
                        text=f"{i}. {res.get('title', 'No title')}**\n",
                        sub_type=StreamSubType.RESULT,
                        metadata={"result_index": i, "title": res.get("title")},
                    )
                    yield StreamChunk(
                        text=f"{res.get('url', 'No URL')}\n",
                        sub_type=StreamSubType.RESULT,
                        metadata={"url": res.get("url")},
                    )

                    snippet = res.get("snippet", "No description")
                    if len(snippet) > 150:
                        snippet = snippet[:150] + "..."
                    yield StreamChunk(
                        text=f"{snippet}\n\n",
                        sub_type=StreamSubType.RESULT,
                        metadata={"snippet": snippet},
                    )

                    if i < len(results):
                        await asyncio.sleep(0.2)

                # Context-aware academic follow-up suggestions
                conversation_history = llm_context.get("conversation_history", [])
                if conversation_history and self.llm_service:
                    yield StreamChunk(
                        text="**Related research areas you might explore:**\n",
                        sub_type=StreamSubType.STATUS,
                    )

                    context_prompt = f"""Based on the academic search results for "{query}" and our conversation history, suggest 2-3 related research topics, methodologies, or follow-up academic searches that would be valuable."""

                    try:
                        suggestions = await self.llm_service.generate_response(
                            prompt=context_prompt, context=llm_context
                        )
                        yield StreamChunk(
                            text=f"{suggestions}\n\n",
                            sub_type=StreamSubType.CONTENT,
                            metadata={"type": "suggestions"},
                        )
                    except:
                        pass

                yield StreamChunk(
                    text="**Academic search completed**\n",
                    sub_type=StreamSubType.STATUS,
                    metadata={"completed": True, "search_type": "academic"},
                )
            else:
                yield StreamChunk(
                    text=f"❌ **Academic search failed:** {result.get('error', 'Unknown error')}\n",
                    sub_type=StreamSubType.ERROR,
                    metadata={"error": result.get("error")},
                )

        except Exception as e:
            yield StreamChunk(
                text=f"❌ **Error during academic search:** {str(e)}",
                sub_type=StreamSubType.ERROR,
                metadata={"error": str(e)},
            )
