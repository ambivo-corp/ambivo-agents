# ambivo_agents/agents/simple_web_search.py
"""
Simple Web Search Agent - Focused and Direct
Reports search provider information clearly
"""

import asyncio
import json
import time
import uuid

import requests
import logging
from typing import Dict, List, Any, Optional
from datetime import datetime
from dataclasses import dataclass

from ..core.base import BaseAgent, AgentRole, AgentMessage, MessageType, ExecutionContext, AgentTool
from ..config.loader import load_config, get_config_section


@dataclass
class SearchResult:
    """Simple search result structure"""
    title: str
    url: str
    snippet: str
    rank: int
    provider: str
    search_time: float


class SimpleWebSearchAgent(BaseAgent):
    """Simple, targeted web search agent with clear provider reporting"""

    def __init__(self, agent_id: str=None, memory_manager=None, llm_service=None, **kwargs):
        if agent_id is None:
            agent_id = f"search_{str(uuid.uuid4())[:8]}"

        super().__init__(
            agent_id=agent_id,
            role=AgentRole.RESEARCHER,
            memory_manager=memory_manager,
            llm_service=llm_service,
            name="Simple Web Search Agent",
            description="Direct web search with clear provider reporting",
            **kwargs
        )

        # Load search configuration
        try:
            config = load_config()
            self.search_config = get_config_section('web_search', config)
        except Exception as e:
            raise ValueError(f"web_search configuration not found: {e}")

        self.logger = logging.getLogger(f"SimpleWebSearch-{agent_id}")
        # Initialize providers
        self.providers = {}
        self.current_provider = None
        self._initialize_providers()



    def _initialize_providers(self):
        """Initialize available search providers"""

        # Brave Search
        if self.search_config.get('brave_api_key'):
            self.providers['brave'] = {
                'name': 'Brave Search',
                'api_key': self.search_config['brave_api_key'],
                'url': 'https://api.search.brave.com/res/v1/web/search',
                'priority': 1,
                'available': True,
                'rate_limit': 2.0
            }

        # AVES API
        if self.search_config.get('avesapi_api_key'):
            self.providers['aves'] = {
                'name': 'AVES Search',
                'api_key': self.search_config['avesapi_api_key'],
                'url': 'https://api.avesapi.com/search',
                'priority': 2,
                'available': True,
                'rate_limit': 1.5
            }

        if not self.providers:
            raise ValueError("No search providers configured")

        # Set current provider (highest priority available)
        available_providers = [(name, config) for name, config in self.providers.items()
                               if config['available']]
        if available_providers:
            available_providers.sort(key=lambda x: x[1]['priority'])
            self.current_provider = available_providers[0][0]

        self.logger.info(f"Initialized with providers: {list(self.providers.keys())}")
        self.logger.info(f"Current provider: {self.current_provider}")

    async def search_web(self, query: str, max_results: int = 10) -> Dict[str, Any]:
        """Perform web search and return results with provider info"""

        if not self.current_provider:
            return {
                'success': False,
                'error': 'No search provider available',
                'provider': None,
                'query': query
            }

        provider_info = self.providers[self.current_provider]
        self.logger.info(f"Searching with {provider_info['name']} for: {query}")

        start_time = time.time()

        try:
            # Rate limiting
            await asyncio.sleep(provider_info['rate_limit'])

            if self.current_provider == 'brave':
                results = await self._search_brave(query, max_results)
            elif self.current_provider == 'aves':
                results = await self._search_aves(query, max_results)
            else:
                raise ValueError(f"Unknown provider: {self.current_provider}")

            search_time = time.time() - start_time

            return {
                'success': True,
                'query': query,
                'results': results,
                'total_results': len(results),
                'provider': {
                    'name': provider_info['name'],
                    'code': self.current_provider,
                    'api_endpoint': provider_info['url']
                },
                'search_time': search_time,
                'timestamp': datetime.now().isoformat()
            }

        except Exception as e:
            search_time = time.time() - start_time
            self.logger.error(f"Search failed with {provider_info['name']}: {e}")

            # Try fallback provider
            fallback_result = await self._try_fallback_provider(query, max_results)
            if fallback_result:
                return fallback_result

            return {
                'success': False,
                'error': str(e),
                'provider': {
                    'name': provider_info['name'],
                    'code': self.current_provider,
                    'api_endpoint': provider_info['url']
                },
                'query': query,
                'search_time': search_time
            }

    async def _search_brave(self, query: str, max_results: int) -> List[SearchResult]:
        """Search using Brave API"""

        provider = self.providers['brave']

        headers = {
            'Accept': 'application/json',
            'Accept-Encoding': 'gzip',
            'X-Subscription-Token': provider['api_key']
        }

        params = {
            'q': query,
            'count': min(max_results, 20),
            'country': 'US',
            'search_lang': 'en'
        }

        response = requests.get(provider['url'], headers=headers, params=params, timeout=15)

        if response.status_code == 429:
            raise Exception("Brave API rate limit exceeded")
        elif response.status_code == 401:
            raise Exception("Brave API authentication failed")

        response.raise_for_status()
        data = response.json()

        results = []
        web_results = data.get('web', {}).get('results', [])

        for i, result in enumerate(web_results[:max_results]):
            results.append(SearchResult(
                title=result.get('title', ''),
                url=result.get('url', ''),
                snippet=result.get('description', ''),
                rank=i + 1,
                provider='brave',
                search_time=0.0  # Will be set by caller
            ))

        return results

    async def _search_aves(self, query: str, max_results: int) -> List[SearchResult]:
        """Search using AVES API"""

        provider = self.providers['aves']

        params = {
            'apikey': provider['api_key'],
            'type': 'web',
            'query': query,
            'device': 'desktop',
            'output': 'json',
            'num': min(max_results, 10)
        }

        response = requests.get(provider['url'], params=params, timeout=15)

        if response.status_code == 429:
            raise Exception("AVES API rate limit exceeded")
        elif response.status_code == 401:
            raise Exception("AVES API authentication failed")

        response.raise_for_status()
        data = response.json()

        results = []

        # AVES has different response structures, handle both
        search_results = data.get('result', {}).get('organic_results', [])
        if not search_results:
            search_results = data.get('organic_results', [])

        for i, result in enumerate(search_results[:max_results]):
            results.append(SearchResult(
                title=result.get('title', ''),
                url=result.get('url', result.get('link', '')),
                snippet=result.get('description', result.get('snippet', '')),
                rank=i + 1,
                provider='aves',
                search_time=0.0  # Will be set by caller
            ))

        return results

    async def _try_fallback_provider(self, query: str, max_results: int) -> Optional[Dict[str, Any]]:
        """Try fallback provider if current one fails"""

        # Mark current provider as temporarily unavailable
        self.providers[self.current_provider]['available'] = False

        # Find next available provider
        available_providers = [(name, config) for name, config in self.providers.items()
                               if config['available']]

        if not available_providers:
            return None

        available_providers.sort(key=lambda x: x[1]['priority'])
        fallback_provider = available_providers[0][0]

        self.logger.info(f"Falling back from {self.current_provider} to {fallback_provider}")
        self.current_provider = fallback_provider

        # Try search with fallback provider
        try:
            return await self.search_web(query, max_results)
        except Exception as e:
            self.logger.error(f"Fallback provider {fallback_provider} also failed: {e}")
            return None

    def format_search_response(self, search_data: Dict[str, Any]) -> str:
        """Format search results into a readable response"""

        if not search_data['success']:
            provider_name = search_data.get('provider', {}).get('name', 'Unknown')
            return f"""❌ **Search Failed**

**Provider**: {provider_name}
**Error**: {search_data['error']}
**Query**: {search_data['query']}

Please try again in a few moments."""

        provider = search_data['provider']
        results = search_data['results']

        response = f"""✅ **Search Results**

**🔍 Query**: {search_data['query']}
**📡 Provider**: {provider['name']} ({provider['code'].upper()})
**⏱️ Search Time**: {search_data['search_time']:.2f}s
**📊 Results**: {len(results)} found

"""

        if results:
            response += "**🔗 Top Results**:\n\n"

            for result in results[:5]:  # Show top 5 results
                response += f"**{result.rank}. {result.title}**\n"
                response += f"🔗 {result.url}\n"
                response += f"📝 {result.snippet[:150]}...\n\n"
        else:
            response += "**No results found for this query.**\n"

        response += f"*Powered by {provider['name']} Search API*"

        return response

    async def process_message(self, message: AgentMessage, context: ExecutionContext=None) -> AgentMessage:
        """Process web search requests"""

        self.memory.store_message(message)

        try:
            content = message.content

            # Extract search query from message
            query = self._extract_query_from_message(content)

            if not query:
                response_content = """I'm a web search agent. Please provide a search query like:

• "search for what is ambivo"
• "find information about AI trends"
• "search web for Python tutorials"

I'll search the web and show you which provider (Brave or AVES) was used."""
            else:
                # Perform the search
                search_data = await self.search_web(query, max_results=5)

                # Format the response
                response_content = self.format_search_response(search_data)

                # Store search data in memory for debugging
                self.memory.store_context('last_search', search_data, message.conversation_id)

            response = self.create_response(
                content=response_content,
                recipient_id=message.sender_id,
                session_id=message.session_id,
                conversation_id=message.conversation_id
            )

            self.memory.store_message(response)
            return response

        except Exception as e:
            self.logger.error(f"Search processing error: {e}")
            error_response = self.create_response(
                content=f"🔧 **Search Error**: {str(e)}\n\nPlease check your search configuration and try again.",
                recipient_id=message.sender_id,
                message_type=MessageType.ERROR,
                session_id=message.session_id,
                conversation_id=message.conversation_id
            )
            return error_response

    def _extract_query_from_message(self, content: str) -> Optional[str]:
        """Extract search query from user message"""

        content_lower = content.lower()

        # Remove common search prefixes
        prefixes_to_remove = [
            'search for ', 'search the web for ', 'find ', 'look up ',
            'search web for ', 'web search for ', 'google ', 'find information about '
        ]

        query = content
        for prefix in prefixes_to_remove:
            if content_lower.startswith(prefix):
                query = content[len(prefix):].strip()
                break

        # If no prefix found, check if it's a search-like message
        search_indicators = ['search', 'find', 'what is', 'who is', 'how to', 'where is']
        if not any(indicator in content_lower for indicator in search_indicators):
            return None

        return query.strip() if query.strip() else None

    def get_provider_status(self) -> Dict[str, Any]:
        """Get current provider status"""
        return {
            'current_provider': self.current_provider,
            'providers': {
                name: {
                    'name': config['name'],
                    'available': config['available'],
                    'priority': config['priority']
                }
                for name, config in self.providers.items()
            }
        }