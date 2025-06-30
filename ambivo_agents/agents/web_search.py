# ambivo_agents/agents/web_search.py - Complete and Corrected LLM-Aware Web Search Agent
"""
LLM-Aware Web Search Agent with conversation history and intelligent intent detection
"""

import asyncio
import json
import uuid
import time
import requests
from typing import Dict, List, Any, Optional
from datetime import datetime
from dataclasses import dataclass

from ..core.base import BaseAgent, AgentRole, AgentMessage, MessageType, ExecutionContext, AgentTool
from ..config.loader import load_config, get_config_section
from ..core.history import WebAgentHistoryMixin, ContextType


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
        self.search_config = get_config_section('web_search', config)

        self.providers = {}
        self.current_provider = None

        # Initialize available providers
        self._initialize_providers()

        # Set default provider
        self.current_provider = self._get_best_provider()

    def _initialize_providers(self):
        """Initialize available search providers"""

        # Brave Search API
        if self.search_config.get('brave_api_key'):
            self.providers['brave'] = {
                'name': 'brave',
                'api_key': self.search_config['brave_api_key'],
                'base_url': 'https://api.search.brave.com/res/v1/web/search',
                'priority': 2,
                'available': True,
                'rate_limit_delay': 2.0
            }

        # AVES API
        if self.search_config.get('avesapi_api_key'):
            self.providers['aves'] = {
                'name': 'aves',
                'api_key': self.search_config['avesapi_api_key'],
                'base_url': 'https://api.avesapi.com/search',
                'priority': 1,
                'available': True,
                'rate_limit_delay': 1.5
            }

        if not self.providers:
            raise ValueError("No search providers configured in web_search section")

    def _get_best_provider(self) -> Optional[str]:
        """Get the best available provider"""
        available_providers = [
            (name, config) for name, config in self.providers.items()
            if config.get('available', False)
        ]

        if not available_providers:
            return None

        available_providers.sort(key=lambda x: x[1]['priority'])
        return available_providers[0][0]

    async def search_web(self,
                         query: str,
                         max_results: int = 10,
                         country: str = "US",
                         language: str = "en") -> SearchResponse:
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
                error="No search provider available"
            )

        # Rate limiting
        provider_config = self.providers[self.current_provider]
        if 'last_request_time' in provider_config:
            elapsed = time.time() - provider_config['last_request_time']
            delay = provider_config.get('rate_limit_delay', 1.0)
            if elapsed < delay:
                await asyncio.sleep(delay - elapsed)

        provider_config['last_request_time'] = time.time()

        try:
            if self.current_provider == 'brave':
                return await self._search_brave(query, max_results, country)
            elif self.current_provider == 'aves':
                return await self._search_aves(query, max_results)
            else:
                raise ValueError(f"Unknown provider: {self.current_provider}")

        except Exception as e:
            search_time = time.time() - start_time

            # Mark provider as temporarily unavailable on certain errors
            error_str = str(e).lower()
            if any(keyword in error_str for keyword in ['429', 'rate limit', 'quota exceeded']):
                self.providers[self.current_provider]['available'] = False
                self.providers[self.current_provider]['cooldown_until'] = time.time() + 300

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
                error=str(e)
            )

    async def _search_brave(self, query: str, max_results: int, country: str) -> SearchResponse:
        """Search using Brave Search API"""
        start_time = time.time()

        provider_config = self.providers['brave']

        headers = {
            'Accept': 'application/json',
            'Accept-Encoding': 'gzip',
            'X-Subscription-Token': provider_config['api_key']
        }

        params = {
            'q': query,
            'count': min(max_results, 20),
            'country': country,
            'search_lang': 'en',
            'ui_lang': 'en-US',
            'freshness': 'pd'
        }

        try:
            response = requests.get(
                provider_config['base_url'],
                headers=headers,
                params=params,
                timeout=15
            )

            if response.status_code == 429:
                retry_after = response.headers.get('Retry-After', '300')
                raise Exception(f"Rate limit exceeded. Retry after {retry_after} seconds")
            elif response.status_code == 401:
                raise Exception(f"Authentication failed - check Brave API key")
            elif response.status_code == 403:
                raise Exception(f"Brave API access forbidden - check subscription")

            response.raise_for_status()

            data = response.json()
            search_time = time.time() - start_time

            results = []
            web_results = data.get('web', {}).get('results', [])

            for i, result in enumerate(web_results[:max_results]):
                results.append(SearchResult(
                    title=result.get('title', ''),
                    url=result.get('url', ''),
                    snippet=result.get('description', ''),
                    source='brave',
                    rank=i + 1,
                    score=1.0 - (i * 0.1),
                    timestamp=datetime.now()
                ))

            return SearchResponse(
                query=query,
                results=results,
                total_results=len(results),
                search_time=search_time,
                provider='brave',
                status='success'
            )

        except Exception as e:
            search_time = time.time() - start_time
            raise Exception(f"Brave Search API error: {e}")

    async def _search_aves(self, query: str, max_results: int) -> SearchResponse:
        """Search using AVES API"""
        start_time = time.time()

        provider_config = self.providers['aves']

        headers = {
            'User-Agent': 'AmbivoAgentSystem/1.0'
        }

        params = {
            'apikey': provider_config['api_key'],
            'type': 'web',
            'query': query,
            'device': 'desktop',
            'output': 'json',
            'num': min(max_results, 10)
        }

        try:
            response = requests.get(
                provider_config['base_url'],
                headers=headers,
                params=params,
                timeout=15
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

            result_section = data.get('result', {})
            search_results = result_section.get('organic_results', [])

            if not search_results:
                search_results = data.get('organic_results',
                                          data.get('results', data.get('items', data.get('data', []))))

            for i, result in enumerate(search_results[:max_results]):
                title = result.get('title', 'No Title')
                url = result.get('url', result.get('link', result.get('href', '')))
                snippet = result.get('description', result.get('snippet', result.get('summary', '')))
                position = result.get('position', i + 1)

                results.append(SearchResult(
                    title=title,
                    url=url,
                    snippet=snippet,
                    source='aves',
                    rank=position,
                    score=result.get('score', 1.0 - (i * 0.1)),
                    timestamp=datetime.now()
                ))

            total_results_count = result_section.get('total_results', len(results))

            return SearchResponse(
                query=query,
                results=results,
                total_results=total_results_count,
                search_time=search_time,
                provider='aves',
                status='success'
            )

        except Exception as e:
            search_time = time.time() - start_time
            raise Exception(f"AVES Search API error: {e}")

    def _try_fallback_provider(self) -> bool:
        """Try to switch to a fallback provider"""
        current_priority = self.providers[self.current_provider]['priority']

        fallback_providers = [
            (name, config) for name, config in self.providers.items()
            if config['priority'] > current_priority and config.get('available', False)
        ]

        if fallback_providers:
            fallback_providers.sort(key=lambda x: x[1]['priority'])
            self.current_provider = fallback_providers[0][0]
            return True

        return False

    async def search_news(self, query: str, max_results: int = 10, days_back: int = 7) -> SearchResponse:
        """Search for news articles"""
        news_query = f"{query} news latest recent"
        return await self.search_web(news_query, max_results)

    async def search_academic(self, query: str, max_results: int = 10) -> SearchResponse:
        """Search for academic content"""
        academic_query = f"{query} research paper study academic"
        return await self.search_web(academic_query, max_results)


class WebSearchAgent(BaseAgent, WebAgentHistoryMixin):
    """LLM-Aware Web Search Agent with conversation context and intelligent routing"""

    def __init__(self, agent_id: str = None, memory_manager=None, llm_service=None, **kwargs):
        if agent_id is None:
            agent_id = f"search_{str(uuid.uuid4())[:8]}"

        super().__init__(
            agent_id=agent_id,
            role=AgentRole.RESEARCHER,
            memory_manager=memory_manager,
            llm_service=llm_service,
            name="Web Search Agent",
            description="LLM-aware web search agent with conversation history",
            **kwargs
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

    async def _llm_analyze_intent(self, user_message: str, conversation_context: str = "") -> Dict[str, Any]:
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
            json_match = re.search(r'\{.*\}', response, re.DOTALL)
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
        if any(word in content_lower for word in ['news', 'latest', 'recent', 'breaking']):
            intent = 'search_news'
            search_type = 'news'
        elif any(word in content_lower for word in ['research', 'academic', 'paper', 'study', 'journal']):
            intent = 'search_academic'
            search_type = 'academic'
        elif any(word in content_lower for word in ['search', 'find', 'look up', 'google']):
            intent = 'search_general'
            search_type = 'web'
        elif any(word in content_lower for word in ['help', 'how to', 'what can']):
            intent = 'help_request'
            search_type = 'web'
        else:
            intent = 'search_general'
            search_type = 'web'

        # Extract query
        query = self._extract_query_from_message(user_message)

        # Check for context references
        context_words = ['this', 'that', 'it', 'them', 'more', 'similar', 'related']
        uses_context = any(word in content_lower for word in context_words)

        return {
            "primary_intent": intent,
            "search_query": query,
            "search_type": search_type,
            "uses_context_reference": uses_context,
            "context_type": "previous_search" if uses_context else "none",
            "requirements": {
                "time_range": "recent" if 'recent' in content_lower else "any",
                "max_results": 5,
                "country": "US",
                "language": "en"
            },
            "confidence": 0.7
        }

    def _extract_intent_from_llm_response(self, llm_response: str, user_message: str) -> Dict[str, Any]:
        """Extract intent from LLM response that isn't JSON"""
        # Simple extraction from LLM text response
        content_lower = llm_response.lower()

        if 'news' in content_lower:
            intent = 'search_news'
            search_type = 'news'
        elif 'academic' in content_lower or 'research' in content_lower:
            intent = 'search_academic'
            search_type = 'academic'
        else:
            intent = 'search_general'
            search_type = 'web'

        return {
            "primary_intent": intent,
            "search_query": self._extract_query_from_message(user_message),
            "search_type": search_type,
            "uses_context_reference": False,
            "context_type": "none",
            "requirements": {"max_results": 5, "country": "US", "language": "en"},
            "confidence": 0.6
        }

    async def process_message(self, message: AgentMessage, context: ExecutionContext = None) -> AgentMessage:
        """Process message with LLM-based intent detection and history context"""
        self.memory.store_message(message)

        try:
            user_message = message.content

            # Update conversation state
            self.update_conversation_state(user_message)

            # Get conversation context for LLM analysis
            conversation_context = self._get_conversation_context_summary()

            # Use LLM to analyze intent
            intent_analysis = await self._llm_analyze_intent(user_message, conversation_context)

            # Route request based on LLM analysis
            response_content = await self._route_with_llm_analysis(intent_analysis, user_message, context)

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
                content=f"Web Search Agent error: {str(e)}",
                recipient_id=message.sender_id,
                message_type=MessageType.ERROR,
                session_id=message.session_id,
                conversation_id=message.conversation_id
            )
            return error_response

    def _get_conversation_context_summary(self) -> str:
        """Get a summary of recent conversation for LLM context"""
        try:
            recent_history = self.get_conversation_history_with_context(limit=3,
                                                                        context_types=[ContextType.SEARCH_TERM])

            context_summary = []
            for msg in recent_history:
                if msg.get('message_type') == 'user_input':
                    content = msg.get('content', '')
                    extracted_context = msg.get('extracted_context', {})
                    search_terms = extracted_context.get('search_term', [])

                    if search_terms:
                        context_summary.append(f"Previous search: {search_terms[0]}")
                    else:
                        context_summary.append(f"Previous message: {content[:50]}...")

            return "\n".join(context_summary) if context_summary else "No previous context"
        except:
            return "No previous context"

    async def _route_with_llm_analysis(self, intent_analysis: Dict[str, Any], user_message: str,
                                       context: ExecutionContext) -> str:
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
            refinement_words = ['more', 'additional', 'other', 'similar', 'related', 'about this']
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

            if result['success']:
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

            if result['success']:
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

            if result['success']:
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

            if result['success']:
                return f"🔍 **Refined Search Results**\n\n" \
                       f"**Original:** {recent_search}\n" \
                       f"**Refined:** {refined_query}\n\n" + \
                    self._format_search_results(result, "Refined Search", show_header=False)
            else:
                return f"❌ **Refined search failed:** {result['error']}"
        else:
            return await self._handle_general_search(query, {"max_results": 5})

    async def _handle_help_request(self, user_message: str) -> str:
        """Handle help requests"""
        return self._get_search_help_message()

    def _format_search_results_old(self, result: Dict[str, Any], search_type: str, show_header: bool = True) -> str:
        """Format search results consistently"""
        results = result.get('results', [])
        query = result.get('query', '')

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

            provider = result.get('provider', 'search engine')
            search_time = result.get('search_time', 0)
            response += f"⏱️ **Search completed in {search_time:.2f}s using {provider}**"
        else:
            response += "No results found. Try a different search term."

        return response

    def _format_search_results(self, result: Dict[str, Any], search_type: str, show_header: bool = True) -> str:
        """Format search results consistently - FIXED VERSION"""
        results = result.get('results', [])
        query = result.get('query', '')

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
                title = res.get('title', 'No title') or 'No title'
                url = res.get('url', 'No URL') or 'No URL'
                snippet = res.get('snippet', 'No description') or 'No description'

                # FIXED: Safe string slicing
                snippet_preview = str(snippet)[:150]
                if len(str(snippet)) > 150:
                    snippet_preview += "..."

                response += f"**{i + 1}. {title}**\n"
                response += f"🔗 {url}\n"
                response += f"📝 {snippet_preview}\n\n"

            # FIXED: Safe access to result metadata
            provider = result.get('provider', 'search engine')
            search_time = result.get('search_time', 0)

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

            if result['success']:
                return self._format_search_results(result, "General Search")
            else:
                error_msg = result.get('error', 'Unknown error')
                return f"❌ **Search failed:** {error_msg}"

        except Exception as e:
            return f"❌ **Error during search:** {str(e)}"
    def _get_search_help_message(self) -> str:
        """Get contextual help message"""
        recent_search = self.get_recent_search_term()

        base_message = ("I'm your Web Search Agent! I can help you with:\n\n"
                        "🔍 **Web Search** - General information search\n"
                        "📰 **News Search** - Latest news and current events  \n"
                        "🎓 **Academic Search** - Research papers and studies\n\n"
                        "💡 **Examples:**\n"
                        "• 'Search for AI trends in 2025'\n"
                        "• 'Find latest news about quantum computing'\n"
                        "• 'Look up machine learning research papers'\n")

        if recent_search:
            base_message += f"\n🎯 **Your last search:** {recent_search}\n"
            base_message += "You can say things like 'more about this' or 'find similar topics'"

        return base_message

    def _extract_query_from_message(self, message: str) -> str:
        """Extract clean search query from message"""
        # Remove common search prefixes
        prefixes = ['search for', 'find', 'look up', 'search', 'find me', 'look for',
                    'google', 'search about', 'tell me about']

        query = message.strip()
        for prefix in prefixes:
            if query.lower().startswith(prefix):
                query = query[len(prefix):].strip()
                break

        return query

    # Tool implementations
    def _add_search_tools(self):
        """Add web search related tools"""

        # General web search tool
        self.add_tool(AgentTool(
            name="search_web",
            description="Search the web for information",
            function=self._search_web,
            parameters_schema={
                "type": "object",
                "properties": {
                    "query": {"type": "string", "description": "Search query"},
                    "max_results": {"type": "integer", "default": 10, "description": "Maximum number of results"},
                    "country": {"type": "string", "default": "US", "description": "Country for search results"},
                    "language": {"type": "string", "default": "en", "description": "Language for search results"}
                },
                "required": ["query"]
            }
        ))

        # News search tool
        self.add_tool(AgentTool(
            name="search_news",
            description="Search for recent news articles",
            function=self._search_news,
            parameters_schema={
                "type": "object",
                "properties": {
                    "query": {"type": "string", "description": "News search query"},
                    "max_results": {"type": "integer", "default": 10, "description": "Maximum number of results"},
                    "days_back": {"type": "integer", "default": 7, "description": "How many days back to search"}
                },
                "required": ["query"]
            }
        ))

        # Academic search tool
        self.add_tool(AgentTool(
            name="search_academic",
            description="Search for academic papers and research",
            function=self._search_academic,
            parameters_schema={
                "type": "object",
                "properties": {
                    "query": {"type": "string", "description": "Academic search query"},
                    "max_results": {"type": "integer", "default": 10, "description": "Maximum number of results"}
                },
                "required": ["query"]
            }
        ))

    async def _search_web(self, query: str, max_results: int = 10, country: str = "US", language: str = "en") -> Dict[
        str, Any]:
        """Perform web search"""
        try:
            search_response = await self.search_service.search_web(
                query=query,
                max_results=max_results,
                country=country,
                language=language
            )

            if search_response.status == "success":
                results_data = []
                for result in search_response.results:
                    results_data.append({
                        "title": result.title,
                        "url": result.url,
                        "snippet": result.snippet,
                        "rank": result.rank,
                        "score": result.score
                    })

                return {
                    "success": True,
                    "query": query,
                    "results": results_data,
                    "total_results": search_response.total_results,
                    "search_time": search_response.search_time,
                    "provider": search_response.provider
                }
            else:
                return {
                    "success": False,
                    "error": search_response.error,
                    "provider": search_response.provider
                }

        except Exception as e:
            return {"success": False, "error": str(e)}

    async def _search_news(self, query: str, max_results: int = 10, days_back: int = 7) -> Dict[str, Any]:
        """Search for news articles"""
        try:
            search_response = await self.search_service.search_news(
                query=query,
                max_results=max_results,
                days_back=days_back
            )

            return await self._format_search_response(search_response, "news")

        except Exception as e:
            return {"success": False, "error": str(e)}

    async def _search_academic(self, query: str, max_results: int = 10) -> Dict[str, Any]:
        """Search for academic content"""
        try:
            search_response = await self.search_service.search_academic(
                query=query,
                max_results=max_results
            )

            return await self._format_search_response(search_response, "academic")

        except Exception as e:
            return {"success": False, "error": str(e)}

    async def _format_search_response(self, search_response, search_type: str) -> Dict[str, Any]:
        """Format search response for consistent output"""
        if search_response.status == "success":
            results_data = []
            for result in search_response.results:
                results_data.append({
                    "title": result.title,
                    "url": result.url,
                    "snippet": result.snippet,
                    "rank": result.rank,
                    "score": result.score,
                    "source": result.source
                })

            return {
                "success": True,
                "search_type": search_type,
                "query": search_response.query,
                "results": results_data,
                "total_results": search_response.total_results,
                "search_time": search_response.search_time,
                "provider": search_response.provider
            }
        else:
            return {
                "success": False,
                "search_type": search_type,
                "error": search_response.error,
                "provider": search_response.provider
            }

