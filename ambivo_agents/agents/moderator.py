# ambivo_agents/agents/moderator.py
"""
ModeratorAgent: Complete intelligent orchestrator that routes queries to specialized agents
FIXED VERSION - All methods implemented correctly
"""

import asyncio
import json
import uuid
import time
import logging
from typing import Dict, List, Any, Optional, Union
from datetime import datetime
from dataclasses import dataclass

from ..core.base import BaseAgent, AgentRole, AgentMessage, MessageType, ExecutionContext
from ..config.loader import load_config, get_config_section
from ..core.history import BaseAgentHistoryMixin, ContextType


@dataclass
class AgentResponse:
    """Response from an individual agent"""
    agent_type: str
    content: str
    success: bool
    execution_time: float
    metadata: Dict[str, Any]
    error: Optional[str] = None


class ModeratorAgent(BaseAgent, BaseAgentHistoryMixin):
    """
    Complete moderator agent that intelligently routes queries to specialized agents
    Users only interact with this agent, which handles everything behind the scenes
    """

    def __init__(self, agent_id: str = None, memory_manager=None, llm_service=None,
                 enabled_agents: List[str] = None, **kwargs):
        if agent_id is None:
            agent_id = f"moderator_{str(uuid.uuid4())[:8]}"

        super().__init__(
            agent_id=agent_id,
            role=AgentRole.COORDINATOR,
            memory_manager=memory_manager,
            llm_service=llm_service,
            name="Moderator Agent",
            description="Intelligent orchestrator that routes queries to specialized agents",
            **kwargs
        )

        # Initialize history mixin
        self.setup_history_mixin()

        # Load configuration
        self.config = load_config()
        self.capabilities = self.config.get('agent_capabilities', {})
        self.moderator_config = self.config.get('moderator', {})

        # Initialize available agents based on config and enabled list
        self.enabled_agents = enabled_agents or self._get_default_enabled_agents()
        self.specialized_agents = {}
        self.agent_routing_patterns = {}

        # Initialize specialized agents
        self._initialize_specialized_agents()

        # Setup routing intelligence
        self._setup_routing_patterns()

        logging.info(f"ModeratorAgent initialized with agents: {list(self.specialized_agents.keys())}")

    def _get_default_enabled_agents(self) -> List[str]:
        """Get default enabled agents from configuration"""
        # Check moderator config first
        if 'default_enabled_agents' in self.moderator_config:
            return self.moderator_config['default_enabled_agents']

        # Otherwise check capabilities config
        enabled = []

        if self.capabilities.get('enable_knowledge_base', False):
            enabled.append('knowledge_base')
        if self.capabilities.get('enable_web_search', False):
            enabled.append('web_search')
        if self.capabilities.get('enable_code_execution', False):
            enabled.append('code_executor')
        if self.capabilities.get('enable_media_editor', False):
            enabled.append('media_editor')
        if self.capabilities.get('enable_youtube_download', False):
            enabled.append('youtube_download')
        if self.capabilities.get('enable_web_scraping', False):
            enabled.append('web_scraper')

        # Always include assistant for general queries
        enabled.append('assistant')

        return enabled

    def _is_agent_enabled(self, agent_type: str) -> bool:
        """Check if an agent type is enabled"""
        if agent_type in self.enabled_agents:
            return True

        # Double-check against capabilities config
        capability_map = {
            'knowledge_base': 'enable_knowledge_base',
            'web_search': 'enable_web_search',
            'code_executor': 'enable_code_execution',
            'media_editor': 'enable_media_editor',
            'youtube_download': 'enable_youtube_download',
            'web_scraper': 'enable_web_scraping',
            'assistant': True  # Always enabled
        }

        if agent_type == 'assistant':
            return True

        capability_key = capability_map.get(agent_type)
        if capability_key and isinstance(capability_key, str):
            return self.capabilities.get(capability_key, False)

        return False

    def _get_agent_config(self, agent_type: str) -> Dict[str, Any]:
        """Get configuration for specific agent type"""
        agent_config = {}

        if agent_type == 'knowledge_base':
            agent_config = self.config.get('knowledge_base', {})
        elif agent_type == 'web_search':
            agent_config = self.config.get('web_search', {})
        elif agent_type == 'media_editor':
            agent_config = self.config.get('media_editor', {})
        elif agent_type == 'youtube_download':
            agent_config = self.config.get('youtube_download', {})
        elif agent_type == 'web_scraper':
            agent_config = self.config.get('web_scraping', {})
        elif agent_type == 'code_executor':
            agent_config = self.config.get('docker', {})

        return agent_config

    def _initialize_specialized_agents(self):
        """Initialize all enabled specialized agents"""
        # Import agents dynamically to avoid circular imports
        try:
            from . import (
                KnowledgeBaseAgent, WebSearchAgent, CodeExecutorAgent,
                MediaEditorAgent, YouTubeDownloadAgent, WebScraperAgent, AssistantAgent
            )
        except ImportError:
            # Fallback individual imports
            try:
                from .knowledge_base import KnowledgeBaseAgent
            except ImportError:
                KnowledgeBaseAgent = None
            try:
                from .web_search import WebSearchAgent
            except ImportError:
                WebSearchAgent = None
            try:
                from .code_executor import CodeExecutorAgent
            except ImportError:
                CodeExecutorAgent = None
            try:
                from .media_editor import MediaEditorAgent
            except ImportError:
                MediaEditorAgent = None
            try:
                from .youtube_download import YouTubeDownloadAgent
            except ImportError:
                YouTubeDownloadAgent = None
            try:
                from .web_scraper import WebScraperAgent
            except ImportError:
                WebScraperAgent = None
            try:
                from .assistant import AssistantAgent
            except ImportError:
                AssistantAgent = None

        agent_classes = {
            'knowledge_base': KnowledgeBaseAgent,
            'web_search': WebSearchAgent,
            'code_executor': CodeExecutorAgent,
            'media_editor': MediaEditorAgent,
            'youtube_download': YouTubeDownloadAgent,
            'web_scraper': WebScraperAgent,
            'assistant': AssistantAgent
        }

        for agent_type in self.enabled_agents:
            if not self._is_agent_enabled(agent_type):
                continue

            agent_class = agent_classes.get(agent_type)
            if agent_class is None:
                logging.warning(f"Agent class for {agent_type} not available")
                continue

            try:
                # Create agent with shared context
                agent_instance = agent_class.create_simple(
                    user_id=self.context.user_id,
                    tenant_id=self.context.tenant_id,
                    session_metadata={
                        'parent_moderator': self.agent_id,
                        'agent_type': agent_type
                    }
                )
                self.specialized_agents[agent_type] = agent_instance
                logging.info(f"Initialized {agent_type} agent: {agent_instance.agent_id}")

            except Exception as e:
                logging.error(f"Failed to initialize {agent_type} agent: {e}")

    def _setup_routing_patterns(self):
        """Setup intelligent routing patterns for different query types"""
        self.agent_routing_patterns = {
            'knowledge_base': {
                'keywords': ['search knowledge', 'query kb', 'knowledge base', 'find in documents',
                             'search documents', 'what do you know about', 'from my files'],
                'patterns': [r'search\s+(?:in\s+)?(?:kb|knowledge|documents?)',
                             r'query\s+(?:the\s+)?(?:kb|knowledge|database)',
                             r'find\s+(?:in\s+)?(?:my\s+)?(?:files|documents?)'],
                'indicators': ['kb_name', 'collection_table', 'document', 'file'],
                'priority': 1
            },

            'web_search': {
                'keywords': ['search web', 'google', 'find online', 'search for', 'look up',
                             'search internet', 'web search', 'find information'],
                'patterns': [r'search\s+(?:the\s+)?(?:web|internet|online)',
                             r'(?:google|look\s+up|find)\s+(?:information\s+)?(?:about|on)',
                             r'what\'s\s+happening\s+with', r'latest\s+news'],
                'indicators': ['search', 'web', 'online', 'internet', 'news'],
                'priority': 2
            },

            'youtube_download': {
                'keywords': ['download youtube', 'youtube video', 'download video', 'get from youtube'],
                'patterns': [r'download\s+(?:from\s+)?youtube', r'youtube\.com/watch', r'youtu\.be/',
                             r'get\s+(?:video|audio)\s+from\s+youtube'],
                'indicators': ['youtube.com', 'youtu.be', 'download video', 'download audio'],
                'priority': 1
            },

            'media_editor': {
                'keywords': ['convert video', 'edit media', 'extract audio', 'resize video',
                             'media processing', 'ffmpeg'],
                'patterns': [r'convert\s+(?:video|audio)', r'extract\s+audio', r'resize\s+video',
                             r'trim\s+(?:video|audio)', r'media\s+(?:processing|editing)'],
                'indicators': ['.mp4', '.avi', '.mp3', '.wav', 'video', 'audio'],
                'priority': 1
            },

            'web_scraper': {
                'keywords': ['scrape website', 'extract from site', 'crawl web', 'scrape data'],
                'patterns': [r'scrape\s+(?:website|site|web)', r'extract\s+(?:data\s+)?from\s+(?:website|site)',
                             r'crawl\s+(?:website|web)'],
                'indicators': ['scrape', 'crawl', 'extract data', 'website'],
                'priority': 1
            },

            'code_executor': {
                'keywords': ['run code', 'execute python', 'run script', 'code execution'],
                'patterns': [r'run\s+(?:this\s+)?(?:code|script|python)', r'execute\s+(?:code|script)',
                             r'```(?:python|bash)'],
                'indicators': ['```', 'def ', 'import ', 'python', 'bash'],
                'priority': 1
            },

            'assistant': {
                'keywords': ['help', 'explain', 'how to', 'what is', 'tell me'],
                'patterns': [r'(?:help|explain|tell)\s+me', r'what\s+is', r'how\s+(?:do\s+)?(?:I|to)',
                             r'can\s+you\s+(?:help|explain)'],
                'indicators': ['help', 'explain', 'question', 'general'],
                'priority': 3  # Lowest priority - fallback
            }
        }

    async def _analyze_query_intent(self, user_message: str) -> Dict[str, Any]:
        """Analyze user query to determine which agent(s) should handle it"""
        message_lower = user_message.lower()

        # Extract context from conversation history
        conversation_context = self._get_conversation_context_summary()

        # Score each agent type
        agent_scores = {}

        for agent_type, patterns in self.agent_routing_patterns.items():
            if agent_type not in self.specialized_agents:
                continue

            score = 0

            # Keyword matching
            keyword_matches = sum(1 for keyword in patterns['keywords']
                                  if keyword in message_lower)
            score += keyword_matches * 2

            # Pattern matching
            import re
            pattern_matches = sum(1 for pattern in patterns['patterns']
                                  if re.search(pattern, message_lower))
            score += pattern_matches * 3

            # Indicator matching
            indicator_matches = sum(1 for indicator in patterns['indicators']
                                    if indicator in message_lower)
            score += indicator_matches * 1

            # Context matching from conversation history
            if conversation_context and agent_type in conversation_context.lower():
                score += 2

            # Apply priority weighting (lower priority number = higher weight)
            priority_weight = 4 - patterns.get('priority', 3)
            score *= priority_weight

            agent_scores[agent_type] = score

        # Determine primary agent (highest score)
        if agent_scores:
            primary_agent = max(agent_scores.items(), key=lambda x: x[1])[0]
            confidence = agent_scores[primary_agent] / sum(agent_scores.values()) if sum(
                agent_scores.values()) > 0 else 0
        else:
            primary_agent = 'assistant'  # fallback
            confidence = 0.5

        # Determine if multiple agents needed
        high_scoring_agents = [agent for agent, score in agent_scores.items() if score > 3]
        requires_multiple = len(high_scoring_agents) > 1

        return {
            'primary_agent': primary_agent,
            'confidence': confidence,
            'agent_scores': agent_scores,
            'requires_multiple_agents': requires_multiple,
            'high_scoring_agents': high_scoring_agents,
            'context_detected': bool(conversation_context)
        }

    async def _route_to_agent(self, agent_type: str, user_message: str,
                              context: ExecutionContext = None) -> AgentResponse:
        """Route query to specific agent and get response"""
        if agent_type not in self.specialized_agents:
            return AgentResponse(
                agent_type=agent_type,
                content=f"Agent {agent_type} not available",
                success=False,
                execution_time=0.0,
                metadata={},
                error=f"Agent {agent_type} not initialized"
            )

        start_time = time.time()

        try:
            agent = self.specialized_agents[agent_type]

            # Use the agent's chat interface
            response_content = await agent.chat(user_message)

            execution_time = time.time() - start_time

            return AgentResponse(
                agent_type=agent_type,
                content=response_content,
                success=True,
                execution_time=execution_time,
                metadata={
                    'agent_id': agent.agent_id,
                    'session_id': agent.context.session_id
                }
            )

        except Exception as e:
            execution_time = time.time() - start_time
            logging.error(f"Error routing to {agent_type} agent: {e}")

            return AgentResponse(
                agent_type=agent_type,
                content=f"Error processing request with {agent_type} agent",
                success=False,
                execution_time=execution_time,
                metadata={},
                error=str(e)
            )

    async def _coordinate_multiple_agents(self, agents: List[str], user_message: str,
                                          context: ExecutionContext = None) -> str:
        """Coordinate multiple agents for complex queries"""
        responses = []

        # Execute agents concurrently
        tasks = [self._route_to_agent(agent_type, user_message, context)
                 for agent_type in agents]

        agent_responses = await asyncio.gather(*tasks, return_exceptions=True)

        successful_responses = []
        for response in agent_responses:
            if isinstance(response, AgentResponse) and response.success:
                successful_responses.append(response)

        if not successful_responses:
            return "I wasn't able to process your request with any of the available agents."

        # Combine multiple responses intelligently
        if len(successful_responses) == 1:
            return successful_responses[0].content

        combined_response = "Here's what I found from multiple sources:\n\n"

        for i, response in enumerate(successful_responses, 1):
            combined_response += f"**From {response.agent_type.replace('_', ' ').title()}:**\n"
            combined_response += f"{response.content}\n\n"

        return combined_response.strip()

    def _get_conversation_context_summary(self) -> str:
        """Get conversation context summary (simplified for now)"""
        try:
            recent_history = self.get_conversation_history_with_context(limit=3)
            context_summary = []

            for msg in recent_history:
                if msg.get('message_type') == 'user_input':
                    content = msg.get('content', '')
                    context_summary.append(content[:50])

            return " ".join(context_summary) if context_summary else ""
        except:
            return ""

    async def process_message(self, message: AgentMessage, context: ExecutionContext = None) -> AgentMessage:
        """Main processing method - routes to appropriate agents"""
        self.memory.store_message(message)

        try:
            user_message = message.content

            # Update conversation state
            self.update_conversation_state(user_message)

            # Analyze intent to determine routing
            intent_analysis = await self._analyze_query_intent(user_message)

            logging.info(f"Intent analysis: Primary={intent_analysis['primary_agent']}, "
                         f"Confidence={intent_analysis['confidence']:.2f}")

            # Route based on analysis
            if intent_analysis['requires_multiple_agents'] and len(intent_analysis['high_scoring_agents']) > 1:
                # Use multiple agents
                response_content = await self._coordinate_multiple_agents(
                    intent_analysis['high_scoring_agents'],
                    user_message,
                    context
                )
            else:
                # Use single primary agent
                primary_response = await self._route_to_agent(
                    intent_analysis['primary_agent'],
                    user_message,
                    context
                )

                if primary_response.success:
                    response_content = primary_response.content
                else:
                    # Fallback to assistant if primary agent fails
                    if intent_analysis['primary_agent'] != 'assistant' and 'assistant' in self.specialized_agents:
                        fallback_response = await self._route_to_agent('assistant', user_message, context)
                        response_content = fallback_response.content
                    else:
                        response_content = f"I encountered an error processing your request: {primary_response.error}"

            # Add routing metadata to response
            agent_name = intent_analysis['primary_agent'].replace('_', ' ').title()
            processed_by = f"\n\n*Processed by: {agent_name} (confidence: {intent_analysis['confidence']:.2f})*"

            response = self.create_response(
                content=response_content,
                metadata = {"processed_by": processed_by},
                recipient_id=message.sender_id,
                session_id=message.session_id,
                conversation_id=message.conversation_id
            )

            self.memory.store_message(response)
            return response

        except Exception as e:
            logging.error(f"ModeratorAgent error: {e}")
            error_response = self.create_response(
                content=f"I encountered an error processing your request: {str(e)}",
                recipient_id=message.sender_id,
                message_type=MessageType.ERROR,
                session_id=message.session_id,
                conversation_id=message.conversation_id
            )
            return error_response

    async def get_agent_status(self) -> Dict[str, Any]:
        """Get status of all managed agents - FIXED METHOD"""
        status = {
            'moderator_id': self.agent_id,
            'enabled_agents': self.enabled_agents,
            'active_agents': {},
            'total_agents': len(self.specialized_agents),
            'routing_patterns': len(self.agent_routing_patterns)
        }

        for agent_type, agent in self.specialized_agents.items():
            try:
                # Simple status check
                status['active_agents'][agent_type] = {
                    'agent_id': agent.agent_id,
                    'status': 'active',
                    'session_id': agent.context.session_id if hasattr(agent, 'context') else 'unknown'
                }
            except Exception as e:
                status['active_agents'][agent_type] = {
                    'agent_id': getattr(agent, 'agent_id', 'unknown'),
                    'status': 'error',
                    'error': str(e)
                }

        return status

    async def cleanup_session(self) -> bool:
        """Cleanup all managed agents"""
        success = True

        # Cleanup all specialized agents
        for agent_type, agent in self.specialized_agents.items():
            try:
                await agent.cleanup_session()
                logging.info(f"Cleaned up {agent_type} agent")
            except Exception as e:
                logging.error(f"Error cleaning up {agent_type} agent: {e}")
                success = False

        # Cleanup moderator itself
        moderator_cleanup = await super().cleanup_session()

        return success and moderator_cleanup

    @classmethod
    def create(cls,
               agent_id: str = None,
               user_id: str = None,
               tenant_id: str = "default",
               enabled_agents: List[str] = None,
               session_metadata: Dict[str, Any] = None,
               **kwargs):
        """
        Create ModeratorAgent with specified enabled agents

        Args:
            agent_id: Optional agent ID
            user_id: User ID for context
            tenant_id: Tenant ID for context
            enabled_agents: List of agent types to enable. If None, uses config defaults
            session_metadata: Additional session metadata
            **kwargs: Additional arguments

        Returns:
            Tuple of (ModeratorAgent, AgentContext)
        """
        if agent_id is None:
            agent_id = f"moderator_{str(uuid.uuid4())[:8]}"

        agent = cls(
            agent_id=agent_id,
            user_id=user_id,
            tenant_id=tenant_id,
            enabled_agents=enabled_agents,
            session_metadata=session_metadata,
            auto_configure=True,
            **kwargs
        )

        return agent, agent.context

    @classmethod
    def create_simple(cls,
                      user_id: str = None,
                      tenant_id: str = "default",
                      enabled_agents: List[str] = None,
                      **kwargs):
        """
        Simple factory method for ModeratorAgent

        Args:
            user_id: User ID for context
            tenant_id: Tenant ID for context
            enabled_agents: List of agent types to enable
            **kwargs: Additional arguments

        Returns:
            ModeratorAgent instance
        """
        agent_id = f"moderator_{str(uuid.uuid4())[:8]}"

        return cls(
            agent_id=agent_id,
            user_id=user_id,
            tenant_id=tenant_id,
            enabled_agents=enabled_agents,
            auto_configure=True,
            **kwargs
        )