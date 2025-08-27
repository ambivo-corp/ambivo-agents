"""
Knowledge Synthesis Agent with Multi-Source Orchestration and Quality Assessment

This agent intelligently routes queries to knowledge base, web search, and web scraping agents,
synthesizes information from multiple sources, assesses response quality, and ensures the 
best possible answer is provided to users.
"""

import asyncio
import json
from typing import Dict, Any, List, Optional, Tuple, Union
from dataclasses import dataclass
from enum import Enum

from ambivo_agents.agents.moderator import ModeratorAgent
from ambivo_agents.agents.response_quality_assessor import (
    ResponseQualityAssessor,
    ResponseSource,
    SourceResponse,
    ResponseAssessment,
    QualityLevel
)
from ambivo_agents.core import AgentContext, AgentSession
from ambivo_agents.core.memory import RedisMemoryManager
from ambivo_agents.core.llm import MultiProviderLLMService


class SearchStrategy(Enum):
    """Search strategies for information gathering"""
    KNOWLEDGE_FIRST = "knowledge_first"    # Check KB first, then web if needed
    WEB_FIRST = "web_first"                # Prioritize web search
    PARALLEL = "parallel"                   # Query all sources simultaneously
    ADAPTIVE = "adaptive"                   # Adapt based on query analysis


@dataclass
class QueryAnalysis:
    """Analysis of user query to determine search strategy"""
    query_type: str  # factual, current_events, technical, opinion, etc.
    requires_current_info: bool
    complexity_level: str  # simple, moderate, complex
    suggested_sources: List[ResponseSource]
    search_strategy: SearchStrategy
    keywords: List[str]
    time_sensitivity: str  # historical, recent, current, future


class KnowledgeSynthesisAgent(ModeratorAgent):
    """
    Knowledge Synthesis Agent that orchestrates multiple information sources,
    synthesizes knowledge from various sources, and ensures response quality
    through comprehensive assessment.
    """
    
    DEFAULT_SYSTEM_MESSAGE = """You are an Intelligent Knowledge Synthesis Agent that orchestrates multiple information sources 
to synthesize and provide the best possible answers. Your role is to:

1. Analyze user queries to determine the best search strategy
2. Orchestrate knowledge base, web search, and web scraping agents
3. Assess response quality and gather additional information if needed
4. Synthesize information from multiple sources into comprehensive answers
5. Ensure responses meet quality standards before returning to users

Query Analysis Guidelines:
- Factual/Technical queries: Prioritize knowledge base
- Current events/News: Prioritize web search with scraping
- Complex queries: Use parallel search across all sources
- Time-sensitive queries: Always include web search

Quality Standards:
- Responses must be accurate, complete, and relevant
- Multiple sources should be consulted for important queries
- Quality assessment determines if additional gathering is needed
- Final responses should synthesize the best information available"""
    
    def __init__(self, **kwargs):
        # Extract our specific parameters
        self.max_iterations = kwargs.pop('max_iterations', 3)
        self.quality_threshold = kwargs.pop('quality_threshold', QualityLevel.GOOD)
        self.enable_auto_scraping = kwargs.pop('enable_auto_scraping', True) 
        self.max_scrape_urls = kwargs.pop('max_scrape_urls', 3)
        self.source_timeouts = kwargs.pop('source_timeouts', {
            'knowledge_base': 10,
            'web_search': 15,
            'web_scrape': 30
        })
        
        # Initialize parent ModeratorAgent
        super().__init__(**kwargs)
        
        # Initialize response quality assessor
        self.assessor = None
        self.assessor_initialized = False
    
    async def _ensure_assessor(self):
        """Ensure the response assessor is initialized"""
        if not self.assessor_initialized:
            self.assessor = ResponseQualityAssessor(
                agent_id=f"{self.agent_id}_assessor",
                memory_manager=self.memory,  # Use self.memory instead of memory_manager
                llm_service=self.llm_service,
                context=self.context
            )
            self.assessor_initialized = True
    
    async def analyze_query(self, query: str) -> QueryAnalysis:
        """Analyze user query to determine optimal search strategy"""
        analysis_prompt = f"""Analyze the following user query and determine the optimal search strategy.

Query: {query}

Please provide analysis in JSON format:
{{
    "query_type": "factual|current_events|technical|opinion|research|other",
    "requires_current_info": true/false,
    "complexity_level": "simple|moderate|complex",
    "suggested_sources": ["knowledge_base", "web_search", "web_scrape"],
    "search_strategy": "knowledge_first|web_first|parallel|adaptive",
    "keywords": ["keyword1", "keyword2"],
    "time_sensitivity": "historical|recent|current|future",
    "reasoning": "Brief explanation of strategy choice"
}}"""
        
        response = await self.llm_service.generate_response(
            prompt=analysis_prompt,
            system_message="You are a query analyzer. Analyze queries to determine optimal search strategies."
        )
        
        try:
            analysis_data = json.loads(response)
        except:
            # Fallback to adaptive strategy
            analysis_data = {
                "query_type": "other",
                "requires_current_info": True,
                "complexity_level": "moderate",
                "suggested_sources": ["knowledge_base", "web_search"],
                "search_strategy": "adaptive",
                "keywords": query.split()[:5],
                "time_sensitivity": "current"
            }
        
        # Convert to QueryAnalysis object
        return QueryAnalysis(
            query_type=analysis_data.get('query_type', 'other'),
            requires_current_info=analysis_data.get('requires_current_info', True),
            complexity_level=analysis_data.get('complexity_level', 'moderate'),
            suggested_sources=[ResponseSource[s.upper()] for s in analysis_data.get('suggested_sources', ['knowledge_base'])],
            search_strategy=SearchStrategy[analysis_data.get('search_strategy', 'adaptive').upper()],
            keywords=analysis_data.get('keywords', []),
            time_sensitivity=analysis_data.get('time_sensitivity', 'current')
        )
    
    async def gather_from_knowledge_base(self, query: str) -> Optional[SourceResponse]:
        """Gather information from knowledge base"""
        try:
            # Check if the query should target a specific collection
            # For tech market queries, use the research trends collection
            if any(term in query.lower() for term in ['tech market', 'technology trend', 'market trend', 'significant trend']):
                kb_query = f"collection:research_trends_in_tech_market_2025_20250814_172410 {query}"
            else:
                kb_query = query
            
            # Route to knowledge base agent
            kb_response = await self._route_to_agent_with_context('knowledge_base', kb_query)
            
            if kb_response.success and kb_response.content and kb_response.content.strip():
                return SourceResponse(
                    source=ResponseSource.KNOWLEDGE_BASE,
                    content=kb_response.content,
                    confidence=0.9,  # High confidence for KB
                    metadata={
                        'agent_response': kb_response,
                        'collection_used': 'research_trends_in_tech_market_2025_20250814_172410' if 'collection:' in kb_query else 'default',
                        'original_query': query,
                        'kb_query_used': kb_query,
                        'content_length': len(kb_response.content)
                    }
                )
            else:
                self.logger.warning(f"Knowledge base returned no useful content for query: {query}")
                if kb_response.content:
                    self.logger.warning(f"Content preview: {kb_response.content[:100]}...")
        except Exception as e:
            self.logger.error(f"Error querying knowledge base: {e}")
            import traceback
            self.logger.error(f"Full traceback: {traceback.format_exc()}")
        
        return None
    
    async def gather_from_web_search(self, query: str) -> Optional[SourceResponse]:
        """Gather information from web search"""
        try:
            # Route to web search agent
            search_response = await self._route_to_agent_with_context('web_search', query)
            
            if search_response.success:
                # Ensure we have content
                content = search_response.content or ""
                
                # Clean up the content - handle cases where it might contain "No results found"
                if content and not any(phrase in content.lower() for phrase in [
                    "no results found", 
                    "no results", 
                    "try a different search term",
                    "search returned no results"
                ]):
                    return SourceResponse(
                        source=ResponseSource.WEB_SEARCH,
                        content=content,
                        confidence=0.75,  # Moderate confidence for search
                        metadata={
                            'agent_response': search_response,
                            'urls': search_response.metadata.get('urls', []),
                            'raw_content': search_response.content,
                            'content_length': len(content)
                        }
                    )
                else:
                    self.logger.warning(f"Web search returned no useful results for query: {query}")
                    self.logger.warning(f"Content preview: {content[:200]}...")
                    
        except Exception as e:
            self.logger.error(f"Error performing web search: {e}")
            import traceback
            self.logger.error(f"Full traceback: {traceback.format_exc()}")
        
        return None
    
    async def gather_from_web_scraping(self, query: str, urls: Optional[List[str]] = None) -> Optional[SourceResponse]:
        """Gather information from web scraping"""
        try:
            # If no URLs provided, get from web search first
            if not urls and self.enable_auto_scraping:
                search_response = await self.gather_from_web_search(query)
                if search_response and search_response.metadata.get('urls'):
                    urls = search_response.metadata['urls'][:self.max_scrape_urls]
            
            if not urls:
                return None
            
            # Scrape URLs
            scrape_results = []
            for url in urls:
                scrape_query = f"scrape {url} for information about: {query}"
                scrape_response = await self._route_to_agent_with_context('web_scraper', scrape_query)
                if scrape_response.success:
                    scrape_results.append(scrape_response.content)
            
            if scrape_results:
                combined_content = "\n\n".join(scrape_results)
                return SourceResponse(
                    source=ResponseSource.WEB_SCRAPE,
                    content=combined_content,
                    confidence=0.8,  # Good confidence for direct scraping
                    metadata={'urls_scraped': urls, 'results': scrape_results}
                )
        except Exception as e:
            self.logger.error(f"Error scraping web content: {e}")
        
        return None
    
    async def gather_responses_parallel(self, query: str) -> List[SourceResponse]:
        """Gather responses from all sources in parallel"""
        tasks = [
            self.gather_from_knowledge_base(query),
            self.gather_from_web_search(query),
        ]
        
        # Add scraping if enabled
        if self.enable_auto_scraping:
            tasks.append(self.gather_from_web_scraping(query))
        
        # Execute in parallel with timeout
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        # Filter out None and exceptions
        responses = []
        for result in results:
            if isinstance(result, SourceResponse):
                responses.append(result)
            elif isinstance(result, Exception):
                self.logger.error(f"Error in parallel gathering: {result}")
        
        return responses
    
    async def gather_responses_sequential(
        self,
        query: str,
        strategy: SearchStrategy,
        sources: List[ResponseSource]
    ) -> List[SourceResponse]:
        """Gather responses sequentially based on strategy"""
        responses = []
        
        # Determine order based on strategy
        if strategy == SearchStrategy.KNOWLEDGE_FIRST:
            ordered_sources = [ResponseSource.KNOWLEDGE_BASE, ResponseSource.WEB_SEARCH, ResponseSource.WEB_SCRAPE]
        elif strategy == SearchStrategy.WEB_FIRST:
            ordered_sources = [ResponseSource.WEB_SEARCH, ResponseSource.WEB_SCRAPE, ResponseSource.KNOWLEDGE_BASE]
        else:
            ordered_sources = sources
        
        for source in ordered_sources:
            if source not in sources:
                continue
            
            response = None
            if source == ResponseSource.KNOWLEDGE_BASE:
                response = await self.gather_from_knowledge_base(query)
            elif source == ResponseSource.WEB_SEARCH:
                response = await self.gather_from_web_search(query)
            elif source == ResponseSource.WEB_SCRAPE:
                # Use URLs from previous search if available
                urls = None
                for r in responses:
                    if r.source == ResponseSource.WEB_SEARCH and r.metadata.get('urls'):
                        urls = r.metadata['urls']
                        break
                response = await self.gather_from_web_scraping(query, urls)
            
            if response:
                responses.append(response)
                
                # Early exit if we have excellent response (for efficiency)
                if strategy != SearchStrategy.PARALLEL and len(responses) >= 1:
                    # Quick quality check
                    if response.confidence >= 0.85 and len(response.content) > 500:
                        break
        
        return responses
    
    async def process_with_quality_assessment(
        self,
        query: str,
        user_preferences: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Process query with quality assessment and iterative improvement.
        
        Args:
            query: User's question
            user_preferences: Optional preferences (e.g., {"prioritize": "web_search"})
            
        Returns:
            Final response with quality assessment metadata
        """
        await self._ensure_assessor()
        
        # Analyze query
        query_analysis = await self.analyze_query(query)
        
        # Apply user preferences to analysis
        if user_preferences:
            if user_preferences.get('prioritize') == 'web_search':
                query_analysis.search_strategy = SearchStrategy.WEB_FIRST
            elif user_preferences.get('prioritize') == 'knowledge_base':
                query_analysis.search_strategy = SearchStrategy.KNOWLEDGE_FIRST
        
        best_assessment = None
        all_responses = []
        
        for iteration in range(self.max_iterations):
            # Gather responses based on strategy
            if query_analysis.search_strategy == SearchStrategy.PARALLEL:
                responses = await self.gather_responses_parallel(query)
            else:
                responses = await self.gather_responses_sequential(
                    query,
                    query_analysis.search_strategy,
                    query_analysis.suggested_sources
                )
            
            # Add to all responses
            all_responses.extend(responses)
            
            # Assess response quality
            if responses:
                assessment = await self.assessor.assess_response(
                    query,
                    responses,
                    user_preferences
                )
                
                # Check if quality is acceptable
                if assessment.quality_level.value >= self.quality_threshold.value:
                    best_assessment = assessment
                    break
                
                # If not acceptable, try additional sources
                if assessment.needs_additional_sources and iteration < self.max_iterations - 1:
                    # Gather from suggested additional sources
                    for source in assessment.suggested_sources:
                        if source == ResponseSource.KNOWLEDGE_BASE:
                            kb_resp = await self.gather_from_knowledge_base(query)
                            if kb_resp:
                                responses.append(kb_resp)
                        elif source == ResponseSource.WEB_SEARCH:
                            search_resp = await self.gather_from_web_search(query)
                            if search_resp:
                                responses.append(search_resp)
                        elif source == ResponseSource.WEB_SCRAPE:
                            scrape_resp = await self.gather_from_web_scraping(query)
                            if scrape_resp:
                                responses.append(scrape_resp)
                
                best_assessment = assessment
        
        # Prepare final response with robust fallback mechanisms
        final_response = ""
        
        if best_assessment and best_assessment.final_response:
            final_response = best_assessment.final_response
        elif all_responses:
            # Fallback to best available response
            best_response = max(all_responses, key=lambda r: r.confidence)
            final_response = best_response.content
        else:
            # Ultimate fallback: route to assistant agent if no sources provided results
            self.logger.warning(f"No responses from specialized agents for query: {query}")
            try:
                fallback_response = await self._route_to_agent_with_context('assistant', query)
                if fallback_response and fallback_response.success:
                    final_response = fallback_response.content
                    self.logger.info("Successfully used assistant agent as fallback")
                else:
                    final_response = "I apologize, but I'm having difficulty accessing information sources right now. Please try your query again in a moment."
            except Exception as e:
                self.logger.error(f"Fallback to assistant agent failed: {e}")
                final_response = "I couldn't find sufficient information to answer your question. Please try rephrasing or providing more context."
        
        return {
            'success': True,
            'response': final_response,
            'quality_assessment': {
                'quality_level': best_assessment.quality_level.value if best_assessment else 'unknown',
                'confidence_score': best_assessment.confidence_score if best_assessment else 0.0,
                'sources_used': [s.value for s in (best_assessment.sources_used if best_assessment else [])],
                'strengths': best_assessment.strengths if best_assessment else [],
                'weaknesses': best_assessment.weaknesses if best_assessment else [],
            } if best_assessment else {},
            'query_analysis': {
                'query_type': query_analysis.query_type,
                'strategy_used': query_analysis.search_strategy.value,
                'sources_consulted': len(all_responses)
            },
            'metadata': {
                'iterations': iteration + 1,
                'total_sources_consulted': len(all_responses),
                'user_preferences': user_preferences
            }
        }
    
    async def process_message(self, message: str, **kwargs) -> Dict[str, Any]:
        """
        Process user message with enhanced multi-source orchestration.
        
        Args:
            message: User's message/query
            **kwargs: Additional arguments including user_preferences
            
        Returns:
            Response with quality assessment and metadata
        """
        # Check for user preferences in message
        user_preferences = kwargs.get('user_preferences', {})
        
        # Check for explicit prioritization in message
        message_lower = message.lower()
        if 'prioritize web search' in message_lower or 'search the web' in message_lower:
            user_preferences['prioritize'] = 'web_search'
        elif 'prioritize knowledge base' in message_lower or 'check knowledge base' in message_lower:
            user_preferences['prioritize'] = 'knowledge_base'
        elif 'check all sources' in message_lower or 'comprehensive search' in message_lower:
            user_preferences['search_all'] = True
        
        # Process with quality assessment
        result = await self.process_with_quality_assessment(message, user_preferences)
        
        # Add conversation history
        await self.add_to_conversation_history(message, 'user')
        await self.add_to_conversation_history(result['response'], 'assistant')
        
        return result
    
    async def process_message_stream(self, message: str, **kwargs):
        """
        Stream processing with quality assessment.
        Note: Quality assessment happens before streaming begins.
        """
        # First, get the complete assessed response
        result = await self.process_message(message, **kwargs)
        
        # Stream the final response
        response_text = result.get('response', '')
        
        # Stream quality info first
        quality_info = result.get('quality_assessment', {})
        if quality_info:
            yield {
                'type': 'quality_assessment',
                'data': quality_info
            }
        
        # Stream the response in chunks
        chunk_size = 50  # characters per chunk
        for i in range(0, len(response_text), chunk_size):
            chunk = response_text[i:i+chunk_size]
            yield {
                'type': 'content',
                'data': chunk
            }
            await asyncio.sleep(0.01)  # Small delay for streaming effect
        
        # Stream final metadata
        yield {
            'type': 'complete',
            'data': {
                'metadata': result.get('metadata', {}),
                'query_analysis': result.get('query_analysis', {})
            }
        }