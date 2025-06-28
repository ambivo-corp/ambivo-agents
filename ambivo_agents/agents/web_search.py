# ambivo_agents/agents/web_search.py
"""
Web Search Agent with Multiple Search Provider Support
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


class WebSearchAgent(BaseAgent):
    """Web Search Agent that provides web search capabilities"""

    def __init__(self, agent_id: str=None, memory_manager=None, llm_service=None, **kwargs):
        if agent_id is None:
            agent_id = f"search_{str(uuid.uuid4())[:8]}"
        super().__init__(
            agent_id=agent_id,
            role=AgentRole.RESEARCHER,
            memory_manager=memory_manager,
            llm_service=llm_service,
            name="Web Search Agent",
            description="Agent for web search operations and information retrieval",
            **kwargs
        )

        # Initialize search service
        try:
            self.search_service = WebSearchServiceAdapter()
        except Exception as e:
            raise RuntimeError(f"Failed to initialize Web Search Service: {e}")

        # Add web search tools
        self._add_search_tools()

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

    async def _format_search_response(self, search_response: SearchResponse, search_type: str) -> Dict[str, Any]:
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

    async def process_message(self, message: AgentMessage, context: ExecutionContext) -> AgentMessage:
        """Process incoming message and route to appropriate search operations"""
        self.memory.store_message(message)

        try:
            content = message.content.lower()
            user_message = message.content

            # Determine the appropriate action based on message content
            if any(keyword in content for keyword in ['search', 'find', 'look up', 'what is', 'who is']):
                response_content = await self._handle_search_request(user_message, context)
            elif any(keyword in content for keyword in ['news', 'latest', 'recent', 'current']):
                response_content = await self._handle_news_search_request(user_message, context)
            elif any(keyword in content for keyword in ['research', 'academic', 'paper', 'study']):
                response_content = await self._handle_academic_search_request(user_message, context)
            else:
                response_content = await self._handle_general_search_request(user_message, context)

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

    async def _handle_search_request(self, user_message: str, context: ExecutionContext) -> str:
        """Handle general search requests"""
        # Extract search query from message
        query = user_message.replace("search for", "").replace("find", "").replace("look up", "").strip()

        if len(query) < 3:
            return "Please provide a more specific search query. What would you like me to search for?"

        # Perform search
        search_result = await self._search_web(query, max_results=5)

        if search_result['success']:
            results = search_result['results']
            if results:
                response = f"🔍 **Search Results for: {query}**\n\n"

                for i, result in enumerate(results[:3], 1):
                    response += f"**{i}. {result['title']}**\n"
                    response += f"🔗 {result['url']}\n"
                    response += f"📝 {result['snippet'][:200]}...\n\n"

                response += f"Found {search_result['total_results']} results in {search_result['search_time']:.2f}s using {search_result['provider']}"
                return response
            else:
                return f"No results found for '{query}'. Try rephrasing your search query."
        else:
            return f"Search failed: {search_result['error']}"

    async def _handle_news_search_request(self, user_message: str, context: ExecutionContext) -> str:
        """Handle news search requests"""
        query = user_message.replace("news", "").replace("latest", "").replace("recent", "").strip()

        if len(query) < 3:
            return "What news topic would you like me to search for?"

        search_result = await self._search_news(query, max_results=5)

        if search_result['success']:
            results = search_result['results']
            if results:
                response = f"📰 **Latest News for: {query}**\n\n"

                for i, result in enumerate(results[:3], 1):
                    response += f"**{i}. {result['title']}**\n"
                    response += f"🔗 {result['url']}\n"
                    response += f"📝 {result['snippet'][:200]}...\n\n"

                return response
            else:
                return f"No recent news found for '{query}'."
        else:
            return f"News search failed: {search_result['error']}"

    async def _handle_academic_search_request(self, user_message: str, context: ExecutionContext) -> str:
        """Handle academic search requests"""
        query = user_message.replace("research", "").replace("academic", "").replace("paper", "").strip()

        if len(query) < 3:
            return "What academic topic would you like me to research?"

        search_result = await self._search_academic(query, max_results=5)

        if search_result['success']:
            results = search_result['results']
            if results:
                response = f"🎓 **Academic Results for: {query}**\n\n"

                for i, result in enumerate(results[:3], 1):
                    response += f"**{i}. {result['title']}**\n"
                    response += f"🔗 {result['url']}\n"
                    response += f"📝 {result['snippet'][:200]}...\n\n"

                return response
            else:
                return f"No academic results found for '{query}'."
        else:
            return f"Academic search failed: {search_result['error']}"

    async def _handle_general_search_request(self, user_message: str, context: ExecutionContext) -> str:
        """Handle general search assistance"""
        if self.llm_service:
            prompt = f"""
            You are a Web Search Agent that helps users find information on the internet.

            Your capabilities include:
            - General web search across multiple search engines
            - News search for current events and recent articles
            - Academic search for research papers and scholarly content
            - Search result summarization and analysis

            User message: {user_message}

            Provide a helpful response about how you can assist with their search needs.
            """

            response = await self.llm_service.generate_response(prompt, context.metadata)
            return response
        else:
            return ("I'm your Web Search Agent! I can help you with:\n\n"
                    "🔍 **Web Search**\n"
                    "- Search the internet for information\n"
                    "- Find websites, articles, and resources\n"
                    "- Multiple search engine support\n\n"
                    "📰 **News Search**\n"
                    "- Find latest news and current events\n"
                    "- Search across news sources\n"
                    "- Filter by recency\n\n"
                    "🎓 **Academic Search**\n"
                    "- Find research papers and studies\n"
                    "- Search academic databases\n"
                    "- Scholarly content retrieval\n\n"
                    "What would you like me to search for?")