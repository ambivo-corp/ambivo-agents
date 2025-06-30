# ambivo_agents/services/agent_service.py
"""
Agent Service for managing agent sessions and message processing - UPDATED WITH YOUTUBE SUPPORT.
"""

import asyncio
import uuid
import time
import logging
from typing import Dict, List, Any, Optional
from datetime import datetime, timedelta

from ..core.base import AgentRole, AgentMessage, MessageType, ExecutionContext
from ..core.memory import create_redis_memory_manager
from ..core.llm import create_multi_provider_llm_service
from ..config.loader import (
    load_config,
    get_config_section,
    validate_agent_capabilities,
    get_available_agent_types,
    get_enabled_capabilities,
    get_available_agent_type_names
)
from .factory import AgentFactory


class AgentSession:
    """Manages a single agent session - UPDATED WITH YOUTUBE SUPPORT"""

    def __init__(self, session_id: str, preferred_llm_provider: str = None):
        # Load configuration from YAML
        self.config = load_config()
        self.session_id = session_id
        self.redis_config = get_config_section('redis', self.config)
        self.llm_config = get_config_section('llm', self.config)
        self.service_config = self.config.get('service', {})

        # Use centralized capability checking
        self.capabilities = validate_agent_capabilities(self.config)
        self.available_agent_types = get_available_agent_types(self.config)

        self.preferred_llm_provider = preferred_llm_provider or self.llm_config.get('preferred_provider', 'openai')
        self.agents = {}
        self.proxy_agent = None
        self.created_at = datetime.now()
        self.last_activity = datetime.now()
        self.message_count = 0

        # Setup logging
        log_level = self.service_config.get('log_level', 'INFO')
        self.logger = logging.getLogger(f"AgentSession-{session_id[:8]}")
        self.logger.setLevel(getattr(logging, log_level))

        # Initialize LLM service
        self._initialize_llm_service()

        # Initialize agents for this session
        self._initialize_agents()

    def _initialize_llm_service(self):
        """Initialize the LLM service"""
        try:
            self.llm_service = create_multi_provider_llm_service(
                config_data=self.llm_config,
                preferred_provider=self.preferred_llm_provider
            )
            self.logger.info(f"LLM service initialized with provider: {self.llm_service.get_current_provider()}")
        except Exception as e:
            self.logger.error(f"Failed to initialize LLM service: {e}")
            raise e

    def _initialize_agents(self):
        """Initialize all agents based on configuration - UPDATED WITH YOUTUBE SUPPORT"""

        # Core Assistant Agent
        assistant_id = f"assistant_{self.session_id}"
        assistant_memory = create_redis_memory_manager(assistant_id, self.redis_config)

        self.agents['assistant'] = AgentFactory.create_agent(
            role=AgentRole.ASSISTANT,
            agent_id=assistant_id,
            memory_manager=assistant_memory,
            llm_service=self.llm_service,
            config=self.config
        )

        # Code Executor Agent (if enabled)
        if self.capabilities.get('code_execution', False):
            executor_id = f"executor_{self.session_id}"
            executor_memory = create_redis_memory_manager(executor_id, self.redis_config)

            self.agents['executor'] = AgentFactory.create_agent(
                role=AgentRole.CODE_EXECUTOR,
                agent_id=executor_id,
                memory_manager=executor_memory,
                llm_service=self.llm_service,
                config=self.config
            )

        # Create specialized agents based on enabled capabilities

        # Web Search Agent (if enabled)
        if self.capabilities.get('web_search', False):
            search_id = f"websearch_{self.session_id}"
            search_memory = create_redis_memory_manager(search_id, self.redis_config)

            try:
                from ..agents.web_search import WebSearchAgent
                self.agents['web_search'] = WebSearchAgent(
                    agent_id=search_id,
                    memory_manager=search_memory,
                    llm_service=self.llm_service
                )
                self.logger.info("Created WebSearchAgent")
            except Exception as e:
                self.logger.error(f"Failed to create WebSearchAgent: {e}")

        # Knowledge Base Agent (if enabled)
        if self.capabilities.get('knowledge_base', False):
            kb_id = f"knowledge_{self.session_id}"
            kb_memory = create_redis_memory_manager(kb_id, self.redis_config)

            try:
                from ..agents.knowledge_base import KnowledgeBaseAgent
                self.agents['knowledge_base'] = KnowledgeBaseAgent(
                    agent_id=kb_id,
                    memory_manager=kb_memory,
                    llm_service=self.llm_service
                )
                self.logger.info("Created KnowledgeBaseAgent")
            except Exception as e:
                self.logger.error(f"Failed to create KnowledgeBaseAgent: {e}")

        # Web Scraper Agent (if enabled)
        if self.capabilities.get('web_scraping', False):
            scraper_id = f"webscraper_{self.session_id}"
            scraper_memory = create_redis_memory_manager(scraper_id, self.redis_config)

            try:
                from ..agents.web_scraper import WebScraperAgent
                self.agents['web_scraper'] = WebScraperAgent(
                    agent_id=scraper_id,
                    memory_manager=scraper_memory,
                    llm_service=self.llm_service
                )
                self.logger.info("Created WebScraperAgent")
            except Exception as e:
                self.logger.error(f"Failed to create WebScraperAgent: {e}")

        # Media Editor Agent (if enabled)
        if self.capabilities.get('media_editor', False):
            media_id = f"mediaeditor_{self.session_id}"
            media_memory = create_redis_memory_manager(media_id, self.redis_config)

            try:
                from ..agents.media_editor import MediaEditorAgent
                self.agents['media_editor'] = MediaEditorAgent(
                    agent_id=media_id,
                    memory_manager=media_memory,
                    llm_service=self.llm_service
                )
                self.logger.info("Created MediaEditorAgent")
            except Exception as e:
                self.logger.error(f"Failed to create MediaEditorAgent: {e}")

        # YouTube Download Agent (if enabled)
        if self.capabilities.get('youtube_download', False):
            youtube_id = f"youtube_{self.session_id}"
            youtube_memory = create_redis_memory_manager(youtube_id, self.redis_config)

            try:
                from ..agents.youtube_download import YouTubeDownloadAgent
                self.agents['youtube_download'] = YouTubeDownloadAgent(
                    agent_id=youtube_id,
                    memory_manager=youtube_memory,
                    llm_service=self.llm_service
                )
                self.logger.info("Created YouTubeDownloadAgent")
            except Exception as e:
                self.logger.error(f"Failed to create YouTubeDownloadAgent: {e}")

        if self.capabilities.get('moderator', False):
            moderator_id = f"moderator_{self.session_id}"
            moderator_memory = create_redis_memory_manager(moderator_id, self.redis_config)

            try:
                from ..agents.moderator import ModeratorAgent
                self.agents['moderator'] = ModeratorAgent(
                    agent_id=moderator_id,
                    memory_manager=moderator_memory,
                    llm_service=self.llm_service
                )
                self.logger.info("Created ModeratorAgent")
            except Exception as e:
                self.logger.error(f"Failed to create ModeratorAgent: {e}")

        # Fallback: Create a general researcher agent if no specialized agents were created
        specialized_agents = ['web_search', 'knowledge_base', 'web_scraper', 'media_editor', 'youtube_download']
        if not any(key in self.agents for key in specialized_agents):
            researcher_id = f"researcher_{self.session_id}"
            researcher_memory = create_redis_memory_manager(researcher_id, self.redis_config)

            self.agents['researcher'] = AgentFactory.create_agent(
                role=AgentRole.RESEARCHER,
                agent_id=researcher_id,
                memory_manager=researcher_memory,
                llm_service=self.llm_service,
                config=self.config
            )
            self.logger.info("Created fallback researcher agent")

        # Proxy Agent (if enabled)
        if self.capabilities.get('proxy', True):
            proxy_id = f"proxy_{self.session_id}"
            proxy_memory = create_redis_memory_manager(proxy_id, self.redis_config)

            self.proxy_agent = AgentFactory.create_agent(
                role=AgentRole.PROXY,
                agent_id=proxy_id,
                memory_manager=proxy_memory,
                llm_service=self.llm_service,
                config=self.config
            )

            # Register all agents with proxy
            for agent in self.agents.values():
                self.proxy_agent.register_agent(agent)

            self.agents['proxy'] = self.proxy_agent

        enabled_capabilities = get_enabled_capabilities(self.config)
        self.logger.info(f"Initialized session with capabilities: {enabled_capabilities}")

    async def process_message(self,
                              message_content: str,
                              user_id: str,
                              tenant_id: str = "",
                              conversation_id: str = None,
                              metadata: Dict[str, Any] = None) -> AgentMessage:
        """Process a user message through the agent system"""

        self.last_activity = datetime.now()
        self.message_count += 1

        if not conversation_id:
            conversation_id = str(uuid.uuid4())

        # Create user message
        user_message = AgentMessage(
            id=str(uuid.uuid4()),
            sender_id=f"user_{user_id}",
            recipient_id=self.proxy_agent.agent_id if self.proxy_agent else list(self.agents.values())[0].agent_id,
            content=message_content,
            message_type=MessageType.USER_INPUT,
            session_id=self.session_id,
            conversation_id=conversation_id,
            metadata=metadata or {}
        )

        # Create execution context
        context = ExecutionContext(
            session_id=self.session_id,
            conversation_id=conversation_id,
            user_id=user_id,
            tenant_id=tenant_id,
            metadata={
                'message_count': self.message_count,
                'session_age': (datetime.now() - self.created_at).total_seconds(),
                'enabled_capabilities': get_enabled_capabilities(self.config),
                'available_agent_types': get_available_agent_type_names(self.config),
                'config_source': 'agent_config.yaml',
                **(metadata or {})
            }
        )

        try:
            # Process through proxy agent if available, otherwise use assistant
            target_agent = self.proxy_agent or self.agents.get('assistant')

            if not target_agent:
                raise RuntimeError("No available agents to process message")

            response = await target_agent.process_message(user_message, context)

            # Add session metadata
            response.metadata.update({
                'session_id': self.session_id,
                'message_count': self.message_count,
                'processing_time': (datetime.now() - self.last_activity).total_seconds(),
                'enabled_capabilities': get_enabled_capabilities(self.config),
                'available_agent_types': get_available_agent_type_names(self.config),
                'config_source': 'agent_config.yaml'
            })

            self.logger.debug(f"Processed message {self.message_count} in conversation {conversation_id}")
            return response

        except Exception as e:
            self.logger.error(f"Error processing message: {e}")
            error_response = AgentMessage(
                id=str(uuid.uuid4()),
                sender_id=target_agent.agent_id if 'target_agent' in locals() else "system",
                recipient_id=user_message.sender_id,
                content=f"I encountered an error processing your request: {str(e)}",
                message_type=MessageType.ERROR,
                session_id=self.session_id,
                conversation_id=conversation_id,
                metadata={'error': str(e), 'message_count': self.message_count, 'config_source': 'agent_config.yaml'}
            )
            return error_response

    def get_session_stats(self) -> Dict[str, Any]:
        """Get session statistics"""
        return {
            'session_id': self.session_id,
            'created_at': self.created_at.isoformat(),
            'last_activity': self.last_activity.isoformat(),
            'message_count': self.message_count,
            'session_age_seconds': (datetime.now() - self.created_at).total_seconds(),
            'agent_count': len(self.agents),
            'available_agents': list(self.agents.keys()),
            'enabled_capabilities': get_enabled_capabilities(self.config),
            'available_agent_types': get_available_agent_type_names(self.config),
            'llm_provider': self.llm_service.get_current_provider() if self.llm_service else None,
            'config_source': 'agent_config.yaml',
            'redis_config': {
                'host': self.redis_config.get('host'),
                'port': self.redis_config.get('port'),
                'db': self.redis_config.get('db')
            }
        }


class AgentService:
    """Agent Service for managing multiple agent sessions - UPDATED WITH YOUTUBE SUPPORT"""

    def __init__(self, preferred_llm_provider: str = None):
        """Initialize the Agent Service"""

        # Load configuration from YAML
        self.config = load_config()
        self.redis_config = get_config_section('redis', self.config)
        self.llm_config = get_config_section('llm', self.config)
        self.service_config = self.config.get('service', {})

        # Use centralized capability checking
        self.capabilities = validate_agent_capabilities(self.config)
        self.available_agent_types = get_available_agent_types(self.config)

        self.preferred_llm_provider = preferred_llm_provider or self.llm_config.get('preferred_provider', 'openai')
        self.sessions: Dict[str, AgentSession] = {}
        self.session_timeout = self.service_config.get('session_timeout', 3600)
        self.max_sessions = self.service_config.get('max_sessions', 100)

        # Setup logging
        self.logger = logging.getLogger("AgentService")
        self._setup_logging()

        # Performance tracking
        self.total_messages_processed = 0
        self.total_sessions_created = 0
        self.start_time = datetime.now()

        self.logger.info("Agent Service initialized from agent_config.yaml with YouTube support")

    def _setup_logging(self):
        """Setup logging configuration"""
        log_level = self.service_config.get('log_level', 'INFO')
        log_to_file = self.service_config.get('log_to_file', False)

        handlers = [logging.StreamHandler()]
        if log_to_file:
            handlers.append(logging.FileHandler('agent_service.log'))

        logging.basicConfig(
            level=getattr(logging, log_level),
            format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
            handlers=handlers
        )

    def create_session(self, session_id: str = None, preferred_llm_provider: str = None) -> str:
        """Create a new agent session"""
        if not session_id:
            session_id = str(uuid.uuid4())

        if session_id in self.sessions:
            self.logger.warning(f"Session {session_id} already exists")
            return session_id

        # Check session limit
        if len(self.sessions) >= self.max_sessions:
            self.cleanup_expired_sessions()
            if len(self.sessions) >= self.max_sessions:
                oldest_session = min(self.sessions.values(), key=lambda s: s.last_activity)
                self.delete_session(oldest_session.session_id)

        try:
            session = AgentSession(
                session_id=session_id,
                preferred_llm_provider=preferred_llm_provider or self.preferred_llm_provider
            )

            self.sessions[session_id] = session
            self.total_sessions_created += 1

            self.logger.info(f"Created session {session_id} (total: {len(self.sessions)})")
            return session_id

        except Exception as e:
            self.logger.error(f"Failed to create session {session_id}: {e}")
            raise

    async def process_message(self,
                              message: str,
                              session_id: str,
                              user_id: str,
                              tenant_id: str = "",
                              conversation_id: str = None,
                              metadata: Dict[str, Any] = None) -> Dict[str, Any]:
        """Process a user message through the agent system"""

        start_time = time.time()

        try:
            # Get or create session
            if session_id not in self.sessions:
                self.create_session(session_id)

            session = self.sessions[session_id]

            # Process message
            response = await session.process_message(
                message_content=message,
                user_id=user_id,
                tenant_id=tenant_id,
                conversation_id=conversation_id,
                metadata=metadata
            )

            self.total_messages_processed += 1
            processing_time = time.time() - start_time

            return {
                'success': True,
                'response': response.content,
                'agent_id': response.sender_id,
                'message_id': response.id,
                'conversation_id': response.conversation_id,
                'session_id': session_id,
                'metadata': response.metadata,
                'timestamp': response.timestamp.isoformat(),
                'processing_time': processing_time,
                'message_count': session.message_count,
                'enabled_capabilities': get_enabled_capabilities(self.config),
                'available_agent_types': get_available_agent_type_names(self.config),
                'config_source': 'agent_config.yaml'
            }

        except Exception as e:
            processing_time = time.time() - start_time
            self.logger.error(f"Error processing message: {e}")

            return {
                'success': False,
                'error': str(e),
                'session_id': session_id,
                'timestamp': datetime.now().isoformat(),
                'processing_time': processing_time,
                'config_source': 'agent_config.yaml'
            }

    def get_service_stats(self) -> Dict[str, Any]:
        """Get comprehensive service statistics"""
        current_time = datetime.now()
        uptime = current_time - self.start_time

        return {
            'service_status': 'healthy',
            'uptime_seconds': uptime.total_seconds(),
            'active_sessions': len(self.sessions),
            'total_sessions_created': self.total_sessions_created,
            'total_messages_processed': self.total_messages_processed,
            'enabled_capabilities': get_enabled_capabilities(self.config),
            'available_agent_types': self.available_agent_types,
            'available_agent_type_names': get_available_agent_type_names(self.config),
            'config_source': 'agent_config.yaml',
            'configuration_summary': {
                'redis_host': self.redis_config.get('host'),
                'redis_port': self.redis_config.get('port'),
                'llm_provider': self.preferred_llm_provider,
                'max_sessions': self.max_sessions,
                'session_timeout': self.session_timeout,
                'log_level': self.service_config.get('log_level', 'INFO')
            },
            'timestamp': current_time.isoformat()
        }

    def health_check(self) -> dict[str, Any]:
        """Comprehensive health check - UPDATED WITH YOUTUBE SUPPORT"""
        health_status: dict[str, Any] = {
            'service_available': True,
            'timestamp': datetime.now().isoformat(),
            'config_source': 'agent_config.yaml'
        }

        try:
            # Test Redis connectivity
            test_memory = create_redis_memory_manager("health_check", self.redis_config)
            health_status['redis_available'] = True

            # Test LLM service
            try:
                test_llm = create_multi_provider_llm_service(self.llm_config, self.preferred_llm_provider)
                health_status['llm_service_available'] = True
                health_status['llm_current_provider'] = test_llm.get_current_provider()
                health_status['llm_available_providers'] = test_llm.get_available_providers()
            except Exception as e:
                health_status['llm_service_available'] = False
                health_status['llm_error'] = str(e)

            # Agent capabilities using centralized checking
            health_status['enabled_capabilities'] = get_enabled_capabilities(self.config)
            health_status['available_agent_types'] = self.available_agent_types
            health_status['available_agent_type_names'] = get_available_agent_type_names(self.config)

            # Session health
            health_status.update({
                'active_sessions': len(self.sessions),
                'max_sessions': self.max_sessions,
                'session_capacity_used': len(self.sessions) / self.max_sessions if self.max_sessions > 0 else 0
            })

        except Exception as e:
            health_status.update({
                'service_available': False,
                'error': str(e),
                'overall_health': 'unhealthy'
            })

        return health_status

    def cleanup_expired_sessions(self):
        """Remove expired sessions"""
        current_time = time.time()
        expired_sessions = []

        for session_id, session in self.sessions.items():
            session_age = current_time - session.created_at.timestamp()
            last_activity_age = current_time - session.last_activity.timestamp()

            if (session_age > self.session_timeout or
                    last_activity_age > self.session_timeout):
                expired_sessions.append(session_id)

        for session_id in expired_sessions:
            self.delete_session(session_id)

        if expired_sessions:
            self.logger.info(f"Cleaned up {len(expired_sessions)} expired sessions")

    def delete_session(self, session_id: str) -> bool:
        """Delete a session"""
        if session_id in self.sessions:
            try:
                del self.sessions[session_id]
                self.logger.info(f"Deleted session {session_id}")
                return True
            except Exception as e:
                self.logger.error(f"Error deleting session {session_id}: {e}")
                return False
        return False

    def get_session_info(self, session_id: str) -> Optional[Dict[str, Any]]:
        """Get detailed information about a session"""
        session = self.sessions.get(session_id)
        if session:
            return session.get_session_stats()
        return None


def create_agent_service(preferred_llm_provider: str = None) -> AgentService:
    """Create agent service using YAML configuration exclusively - UPDATED WITH YOUTUBE SUPPORT"""
    return AgentService(preferred_llm_provider=preferred_llm_provider)


async def quick_chat(agent_service: AgentService,
                     message: str,
                     user_id: str,
                     session_id: str = None,
                     **kwargs) -> str:
    """Quick chat interface"""
    if not session_id:
        session_id = str(uuid.uuid4())

    result = await agent_service.process_message(
        message=message,
        session_id=session_id,
        user_id=user_id,
        **kwargs
    )

    if result['success']:
        return result['response']
    else:
        return f"Error: {result['error']}"