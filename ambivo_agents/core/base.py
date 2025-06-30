# ambivo_agents/core/base.py - ENHANCED with chat() method
"""
Enhanced BaseAgent with built-in auto-context session management and simplified chat interface
"""

import asyncio
import uuid
import time
import tempfile
import os
from pathlib import Path
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from typing import Dict, List, Any, Optional, Callable, Tuple, Union
from concurrent.futures import ThreadPoolExecutor
import logging

# Docker imports
try:
    import docker

    DOCKER_AVAILABLE = True
except ImportError:
    DOCKER_AVAILABLE = False


class AgentRole(Enum):
    ASSISTANT = "assistant"
    PROXY = "proxy"
    ANALYST = "analyst"
    RESEARCHER = "researcher"
    COORDINATOR = "coordinator"
    VALIDATOR = "validator"
    CODE_EXECUTOR = "code_executor"


class MessageType(Enum):
    USER_INPUT = "user_input"
    AGENT_RESPONSE = "agent_response"
    SYSTEM_MESSAGE = "system_message"
    TOOL_CALL = "tool_call"
    TOOL_RESPONSE = "tool_response"
    ERROR = "error"
    STATUS_UPDATE = "status_update"


@dataclass
class AgentMessage:
    id: str
    sender_id: str
    recipient_id: Optional[str]
    content: str
    message_type: MessageType
    metadata: Dict[str, Any] = field(default_factory=dict)
    timestamp: datetime = field(default_factory=datetime.now)
    session_id: Optional[str] = None
    conversation_id: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization"""
        return {
            'id': self.id,
            'sender_id': self.sender_id,
            'recipient_id': self.recipient_id,
            'content': self.content,
            'message_type': self.message_type.value,
            'metadata': self.metadata,
            'timestamp': self.timestamp.isoformat(),
            'session_id': self.session_id,
            'conversation_id': self.conversation_id
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'AgentMessage':
        """Create from dictionary"""
        return cls(
            id=data['id'],
            sender_id=data['sender_id'],
            recipient_id=data.get('recipient_id'),
            content=data['content'],
            message_type=MessageType(data['message_type']),
            metadata=data.get('metadata', {}),
            timestamp=datetime.fromisoformat(data['timestamp']),
            session_id=data.get('session_id'),
            conversation_id=data.get('conversation_id')
        )


@dataclass
class AgentTool:
    name: str
    description: str
    function: Callable
    parameters_schema: Dict[str, Any]
    requires_approval: bool = False
    timeout: int = 30


@dataclass
class ExecutionContext:
    session_id: str
    conversation_id: str
    user_id: str
    tenant_id: str
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class AgentContext:
    """
    Built-in context for every BaseAgent instance
    Automatically created when agent is instantiated
    """
    session_id: str
    conversation_id: str
    user_id: str
    tenant_id: str
    agent_id: str
    created_at: datetime = field(default_factory=datetime.now)
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_execution_context(self) -> ExecutionContext:
        """Convert to ExecutionContext for operations"""
        return ExecutionContext(
            session_id=self.session_id,
            conversation_id=self.conversation_id,
            user_id=self.user_id,
            tenant_id=self.tenant_id,
            metadata=self.metadata
        )

    def update_metadata(self, **kwargs):
        """Update context metadata"""
        self.metadata.update(kwargs)

    def __str__(self):
        return f"AgentContext(session={self.session_id}, user={self.user_id})"


@dataclass
class ProviderConfig:
    """Configuration for LLM providers"""
    name: str
    model_name: str
    priority: int
    max_requests_per_minute: int = 60
    max_requests_per_hour: int = 3600
    cooldown_minutes: int = 5
    request_count: int = 0
    error_count: int = 0
    last_request_time: Optional[datetime] = None
    last_error_time: Optional[datetime] = None
    is_available: bool = True

    def __post_init__(self):
        """Ensure no None values for numeric fields"""
        if self.max_requests_per_minute is None:
            self.max_requests_per_minute = 60
        if self.max_requests_per_hour is None:
            self.max_requests_per_hour = 3600
        if self.request_count is None:
            self.request_count = 0
        if self.error_count is None:
            self.error_count = 0
        if self.priority is None:
            self.priority = 999


class ProviderTracker:
    """Tracks provider usage and availability"""

    def __init__(self):
        self.providers: Dict[str, ProviderConfig] = {}
        self.current_provider: Optional[str] = None
        self.last_rotation_time: Optional[datetime] = None
        self.rotation_interval_minutes: int = 30

    def record_request(self, provider_name: str):
        """Record a request to a provider"""
        if provider_name in self.providers:
            provider = self.providers[provider_name]
            provider.request_count += 1
            provider.last_request_time = datetime.now()

    def record_error(self, provider_name: str, error_message: str):
        """Record an error for a provider"""
        if provider_name in self.providers:
            provider = self.providers[provider_name]
            provider.error_count += 1
            provider.last_error_time = datetime.now()

            if provider.error_count >= 3:
                provider.is_available = False

    def is_provider_available(self, provider_name: str) -> bool:
        """Check if a provider is available"""
        if provider_name not in self.providers:
            return False

        provider = self.providers[provider_name]

        if not provider.is_available:
            if (provider.last_error_time and
                    datetime.now() - provider.last_error_time > timedelta(minutes=provider.cooldown_minutes)):
                provider.is_available = True
                provider.error_count = 0
            else:
                return False

        now = datetime.now()
        # FIXED: Check for None before arithmetic operations
        if provider.last_request_time is not None:
            time_since_last = (now - provider.last_request_time).total_seconds()
            if time_since_last > 3600:
                provider.request_count = 0

        # FIXED: Ensure max_requests_per_hour is not None
        max_requests = provider.max_requests_per_hour or 3600
        if provider.request_count >= max_requests:
            return False

        return True

    def get_best_available_provider(self) -> Optional[str]:
        """Get the best available provider"""
        available_providers = [
            (name, config) for name, config in self.providers.items()
            if self.is_provider_available(name)
        ]

        if not available_providers:
            return None

        def sort_key(provider_tuple):
            name, config = provider_tuple
            priority = config.priority or 999
            error_count = config.error_count or 0
            return (priority, error_count)

        available_providers.sort(key=lambda x: (x[1].priority, x[1].error_count))
        return available_providers[0][0]


class DockerCodeExecutor:
    """Secure code execution using Docker containers"""

    def __init__(self, config: Dict[str, Any]):
        self.config = config
        self.work_dir = config.get("work_dir", '/opt/ambivo/work_dir')
        self.docker_images = config.get("docker_images", ["sgosain/amb-ubuntu-python-public-pod"])
        self.timeout = config.get("timeout", 60)
        self.default_image = self.docker_images[0] if self.docker_images else "sgosain/amb-ubuntu-python-public-pod"

        if DOCKER_AVAILABLE:
            try:
                self.docker_client = docker.from_env()
                self.docker_client.ping()
                self.available = True
            except Exception as e:
                self.available = False
        else:
            self.available = False

    def execute_code(self, code: str, language: str = "python", files: Dict[str, str] = None) -> Dict[str, Any]:
        """Execute code in Docker container"""
        if not self.available:
            return {
                'success': False,
                'error': 'Docker not available',
                'language': language
            }

        try:
            with tempfile.TemporaryDirectory() as temp_dir:
                temp_path = Path(temp_dir)

                if language == "python":
                    code_file = temp_path / "code.py"
                    code_file.write_text(code)
                    cmd = ["python", "/workspace/code.py"]
                elif language == "bash":
                    code_file = temp_path / "script.sh"
                    code_file.write_text(code)
                    cmd = ["bash", "/workspace/script.sh"]
                else:
                    raise ValueError(f"Unsupported language: {language}")

                if files:
                    for filename, content in files.items():
                        file_path = temp_path / filename
                        file_path.write_text(content)

                container_config = {
                    'image': self.default_image,
                    'command': cmd,
                    'volumes': {str(temp_path): {'bind': '/workspace', 'mode': 'rw'}},
                    'working_dir': '/workspace',
                    'mem_limit': '512m',
                    'network_disabled': True,
                    'remove': True,
                    'stdout': True,
                    'stderr': True
                }

                start_time = time.time()
                container = self.docker_client.containers.run(**container_config)
                execution_time = time.time() - start_time

                output = container.decode('utf-8') if isinstance(container, bytes) else str(container)

                return {
                    'success': True,
                    'output': output,
                    'execution_time': execution_time,
                    'language': language
                }

        except docker.errors.ContainerError as e:
            return {
                'success': False,
                'error': f"Container error: {e.stderr.decode('utf-8') if e.stderr else 'Unknown error'}",
                'exit_code': e.exit_status,
                'language': language
            }
        except Exception as e:
            return {
                'success': False,
                'error': str(e),
                'language': language
            }


class BaseAgent(ABC):
    """
    Enhanced BaseAgent with built-in auto-context session management and simplified chat interface
    Every agent automatically gets a context with session_id, user_id, etc.
    """

    def __init__(self,
                 agent_id: str = None,
                 role: AgentRole = AgentRole.ASSISTANT,
                 user_id: str = None,
                 tenant_id: str = "default",
                 session_metadata: Dict[str, Any] = None,
                 memory_manager=None,
                 llm_service=None,
                 config: Dict[str, Any] = None,
                 name: str = None,
                 description: str = None,
                 auto_configure: bool = True,
                 session_id: str = None,
                 conversation_id: str = None,
                 **kwargs):

        # Auto-generate agent_id if not provided
        if agent_id is None:
            agent_id = f"agent_{str(uuid.uuid4())[:8]}"

        self.agent_id = agent_id
        self.role = role
        self.name = name or f"{role.value}_{agent_id[:8]}"
        self.description = description or f"Agent with role: {role.value}"

        # Load config if not provided and auto-configure is enabled
        if config is None and auto_configure:
            try:
                from ..config.loader import load_config
                config = load_config()
            except Exception as e:
                logging.warning(f"Could not load config for auto-configuration: {e}")
                config = {}

        self.config = config or {}

        self.context = self._create_agent_context(user_id, tenant_id,
                                                  session_metadata,
                                                  session_id,
                                                  conversation_id)

        # Auto-configure memory if not provided and auto-configure is enabled
        if memory_manager is None and auto_configure:
            try:
                from ..core.memory import create_redis_memory_manager
                self.memory = create_redis_memory_manager(
                    agent_id=agent_id,
                    redis_config=None  # Will load from config automatically
                )
                logging.info(f"Auto-configured memory for agent {agent_id}")
            except Exception as e:
                logging.error(f"Failed to auto-configure memory for {agent_id}: {e}")
                self.memory = None
        else:
            self.memory = memory_manager

        # Auto-configure LLM service if not provided and auto-configure is enabled
        if llm_service is None and auto_configure:
            try:
                from ..core.llm import create_multi_provider_llm_service
                self.llm_service = create_multi_provider_llm_service()
                logging.info(f"Auto-configured LLM service for agent {agent_id}")
            except Exception as e:
                logging.warning(f"Could not auto-configure LLM for {agent_id}: {e}")
                self.llm_service = None
        else:
            self.llm_service = llm_service

        self.tools = kwargs.get('tools', [])
        self.active = True

        # Initialize executor
        self.executor = ThreadPoolExecutor(max_workers=4)

        logging.info(f"🚀 BaseAgent created with auto-context:")
        logging.info(f"   🤖 Agent: {self.agent_id}")
        logging.info(f"   📋 Session: {self.context.session_id}")
        logging.info(f"   👤 User: {self.context.user_id}")

    def _create_agent_context(self,
                              user_id: str = None,
                              tenant_id: str = "default",
                              session_metadata: Dict[str, Any] = None,
                              session_id: str = None,
                              conversation_id: str = None
                              ) -> AgentContext:
        """Create auto-context for this agent instance"""

        # Auto-generate user_id if not provided
        if user_id is None:
            user_id = f"user_{str(uuid.uuid4())[:8]}"

        if session_id and conversation_id:
            final_session_id = session_id
            final_conversation_id = conversation_id
        else:
            final_session_id = f"session_{str(uuid.uuid4())[:8]}"
            final_conversation_id = f"conv_{str(uuid.uuid4())[:8]}"

        return AgentContext(
            session_id=final_session_id,
            conversation_id=final_conversation_id,
            user_id=user_id,
            tenant_id=tenant_id,
            agent_id=self.agent_id,
            metadata=session_metadata or {}
        )

    @classmethod
    def create(cls,
               agent_id: str = None,
               user_id: str = None,
               tenant_id: str = "default",
               session_metadata: Dict[str, Any] = None,
               session_id: str = None,
               conversation_id: str = None,
               **kwargs) -> Tuple['BaseAgent', AgentContext]:
        """
        🌟 DEFAULT: Create agent and return both agent and context
        This is the RECOMMENDED way to create agents with auto-context

        Usage:
            agent, context = KnowledgeBaseAgent.create(user_id="john")
            print(f"Session: {context.session_id}")
            print(f"User: {context.user_id}")
        """
        if agent_id is None:
            agent_id = f"{cls.__name__.lower()}_{str(uuid.uuid4())[:8]}"

        agent = cls(
            agent_id=agent_id,
            user_id=user_id,
            tenant_id=tenant_id,
            session_metadata=session_metadata,
            session_id=session_id,
            conversation_id=conversation_id,
            auto_configure=True,
            **kwargs
        )

        return agent, agent.context

    @classmethod
    def create_simple(cls,
                      agent_id: str = None,
                      user_id: str = None,
                      tenant_id: str = "default",
                      session_metadata: Dict[str, Any] = None,
                      **kwargs) -> 'BaseAgent':
        """
        Create agent with auto-context (returns agent only)

        ⚠️  LEGACY: Use create() instead for explicit context handling

        Usage:
            agent = KnowledgeBaseAgent.create_simple(user_id="john")
            print(f"Session: {agent.context.session_id}")  # Context still available
        """
        if agent_id is None:
            agent_id = f"{cls.__name__.lower()}_{str(uuid.uuid4())[:8]}"

        return cls(
            agent_id=agent_id,
            user_id=user_id,
            tenant_id=tenant_id,
            session_metadata=session_metadata,
            auto_configure=True,
            **kwargs
        )

    @classmethod
    def create_advanced(cls,
                        agent_id: str,
                        memory_manager,
                        llm_service=None,
                        config: Dict[str, Any] = None,
                        user_id: str = None,
                        tenant_id: str = "default",
                        **kwargs):
        """
        Advanced factory method for explicit dependency injection

        Usage:
            memory = create_redis_memory_manager("custom_agent")
            llm = create_multi_provider_llm_service()
            agent = YouTubeDownloadAgent.create_advanced("my_id", memory, llm)
        """
        return cls(
            agent_id=agent_id,
            memory_manager=memory_manager,
            llm_service=llm_service,
            config=config,
            user_id=user_id,
            tenant_id=tenant_id,
            auto_configure=False,  # Disable auto-config when using advanced mode
            **kwargs
        )

    # 🎯 NEW: SIMPLIFIED CHAT INTERFACE

    async def chat(self, message: str, **kwargs) -> str:
        """
        🌟 NEW: Simplified chat interface that converts string to full AgentMessage

        This is the easiest way to interact with agents created via .create()
        since they already have auto-context (session_id, user_id, etc.)

        Args:
            message: User message as string
            **kwargs: Optional metadata to add to the message

        Returns:
            Agent response as string

        Usage:
            agent, context = YouTubeDownloadAgent.create(user_id="john")
            response = await agent.chat("Download https://youtube.com/watch?v=abc123")
            print(response)
        """
        try:
            # Create AgentMessage from string using auto-context
            user_message = AgentMessage(
                id=str(uuid.uuid4()),
                sender_id=self.context.user_id,  # 🎯 Use auto-context user_id
                recipient_id=self.agent_id,
                content=message,
                message_type=MessageType.USER_INPUT,
                session_id=self.context.session_id,  # 🎯 Use auto-context session_id
                conversation_id=self.context.conversation_id,  # 🎯 Use auto-context conversation_id
                metadata={
                    'chat_interface': True,
                    'simplified_call': True,
                    **kwargs  # Allow additional metadata
                }
            )

            # Get execution context from auto-context
            execution_context = self.context.to_execution_context()

            # Add any additional metadata passed via kwargs
            execution_context.metadata.update(kwargs)

            # Call the full process_message method
            agent_response = await self.process_message(user_message, execution_context)

            # Return just the content string (simplified interface)
            return agent_response.content

        except Exception as e:
            # Handle errors gracefully
            error_msg = f"Chat error: {str(e)}"
            logging.error(f"Agent {self.agent_id} chat error: {e}")
            return error_msg

    def chat_sync(self, message: str, **kwargs) -> str:
        """
        🌟 NEW: Synchronous version of chat() for easier use in non-async contexts

        Args:
            message: User message as string
            **kwargs: Optional metadata to add to the message

        Returns:
            Agent response as string

        Usage:
            agent, context = YouTubeDownloadAgent.create(user_id="john")
            response = agent.chat_sync("Download https://youtube.com/watch?v=abc123")
            print(response)
        """
        try:
            # Get or create event loop
            try:
                loop = asyncio.get_event_loop()
                if loop.is_running():
                    # If loop is already running, we need to use run_in_executor
                    import concurrent.futures
                    with concurrent.futures.ThreadPoolExecutor() as executor:
                        future = executor.submit(asyncio.run, self.chat(message, **kwargs))
                        return future.result()
                else:
                    # Loop exists but not running
                    return loop.run_until_complete(self.chat(message, **kwargs))
            except RuntimeError:
                # No event loop exists, create one
                return asyncio.run(self.chat(message, **kwargs))

        except Exception as e:
            error_msg = f"Sync chat error: {str(e)}"
            logging.error(f"Agent {self.agent_id} sync chat error: {e}")
            return error_msg

    # 🔧 CONTEXT MANAGEMENT METHODS

    def get_context(self) -> AgentContext:
        """Get the agent's auto-generated context"""
        return self.context

    def get_execution_context(self) -> ExecutionContext:
        """Get ExecutionContext for operations that need it"""
        return self.context.to_execution_context()

    def update_context_metadata(self, **kwargs):
        """Update context metadata"""
        self.context.update_metadata(**kwargs)

    # 🧠 CONVERSATION HISTORY METHODS (Built into BaseAgent)

    async def get_conversation_history(self,
                                       limit: int = None,
                                       include_metadata: bool = True) -> List[Dict[str, Any]]:
        """
        Get conversation history for this agent's session

        Args:
            limit: Maximum number of messages to return (None = all)
            include_metadata: Whether to include message metadata

        Returns:
            List of conversation messages with context
        """
        try:
            if not self.memory:
                logging.warning(f"No memory available for agent {self.agent_id}")
                return []

            # Get history using session_id from auto-context
            history = self.memory.get_recent_messages(
                limit=limit or 10,
                conversation_id=self.context.conversation_id
            )

            # Add context information to each message
            enriched_history = []
            for msg in history:
                if include_metadata:
                    msg_with_context = {
                        **msg,
                        'session_id': self.context.session_id,
                        'user_id': self.context.user_id,
                        'agent_id': self.agent_id,
                        'conversation_id': self.context.conversation_id
                    }
                else:
                    msg_with_context = msg

                enriched_history.append(msg_with_context)

            return enriched_history

        except Exception as e:
            logging.error(f"Failed to get conversation history for {self.agent_id}: {e}")
            return []

    async def add_to_conversation_history(self,
                                          message: str,
                                          message_type: str = "user",
                                          metadata: Dict[str, Any] = None) -> bool:
        """
        Add a message to conversation history

        Args:
            message: The message content
            message_type: Type of message ("user", "agent", "system")
            metadata: Additional metadata for the message

        Returns:
            True if successfully added, False otherwise
        """
        try:
            if not self.memory:
                logging.warning(f"No memory available for agent {self.agent_id}")
                return False

            # Create AgentMessage for storage
            agent_message = AgentMessage(
                id=str(uuid.uuid4()),
                sender_id=self.agent_id if message_type == "agent" else f"{message_type}_sender",
                recipient_id=None,
                content=message,
                message_type=MessageType.AGENT_RESPONSE if message_type == "agent" else MessageType.USER_INPUT,
                session_id=self.context.session_id,
                conversation_id=self.context.conversation_id,
                metadata={
                    'type': message_type,
                    'user_id': self.context.user_id,
                    'agent_id': self.agent_id,
                    **(metadata or {})
                }
            )

            # Store in memory
            self.memory.store_message(agent_message)
            return True

        except Exception as e:
            logging.error(f"Failed to add to conversation history for {self.agent_id}: {e}")
            return False

    async def clear_conversation_history(self) -> bool:
        """
        Clear conversation history for this agent's session

        Returns:
            True if successfully cleared, False otherwise
        """
        try:
            if not self.memory:
                logging.warning(f"No memory available for agent {self.agent_id}")
                return False

            self.memory.clear_memory(self.context.conversation_id)
            logging.info(f"Cleared conversation history for session {self.context.session_id}")
            return True

        except Exception as e:
            logging.error(f"Failed to clear conversation history for {self.agent_id}: {e}")
            return False

    async def get_conversation_summary(self) -> Dict[str, Any]:
        """
        Get a summary of the current conversation

        Returns:
            Dictionary with conversation statistics and summary
        """
        try:
            history = await self.get_conversation_history(include_metadata=True)

            if not history:
                return {
                    'total_messages': 0,
                    'user_messages': 0,
                    'agent_messages': 0,
                    'session_duration': '0 minutes',
                    'first_message': None,
                    'last_message': None,
                    'session_id': self.context.session_id
                }

            # Analyze conversation
            total_messages = len(history)
            user_messages = len([msg for msg in history if msg.get('message_type') == 'user_input'])
            agent_messages = len([msg for msg in history if msg.get('message_type') == 'agent_response'])

            # Calculate session duration
            first_msg_time = self.context.created_at
            last_msg_time = datetime.now()
            duration = last_msg_time - first_msg_time
            duration_minutes = int(duration.total_seconds() / 60)

            return {
                'total_messages': total_messages,
                'user_messages': user_messages,
                'agent_messages': agent_messages,
                'session_duration': f"{duration_minutes} minutes",
                'first_message': history[0].get('content', '')[:100] + "..." if len(
                    history[0].get('content', '')) > 100 else history[0].get('content', '') if history else None,
                'last_message': history[-1].get('content', '')[:100] + "..." if len(
                    history[-1].get('content', '')) > 100 else history[-1].get('content', '') if history else None,
                'session_id': self.context.session_id,
                'conversation_id': self.context.conversation_id,
                'user_id': self.context.user_id
            }

        except Exception as e:
            logging.error(f"Failed to get conversation summary for {self.agent_id}: {e}")
            return {
                'error': str(e),
                'session_id': self.context.session_id
            }

    async def _with_auto_context(self, operation_name: str, **kwargs) -> Dict[str, Any]:
        """
        Internal method that automatically applies context to operations
        All agent operations should use this to ensure context is applied
        """
        execution_context = self.get_execution_context()

        # Add context info to operation metadata
        operation_metadata = {
            'session_id': self.context.session_id,
            'user_id': self.context.user_id,
            'tenant_id': self.context.tenant_id,
            'operation': operation_name,
            'timestamp': datetime.now().isoformat(),
            **kwargs
        }

        # Update context metadata
        self.context.update_metadata(**operation_metadata)

        return {
            'execution_context': execution_context,
            'operation_metadata': operation_metadata
        }

    # 🧹 SESSION CLEANUP

    async def cleanup_session(self) -> bool:
        """Cleanup the agent's session and resources"""
        try:
            session_id = self.context.session_id

            # Clear memory for this session
            if hasattr(self, 'memory') and self.memory:
                try:
                    # Commented out temporarily as noted in original
                    # self.memory.clear_memory(self.context.conversation_id)
                    logging.info(f"🧹 Cleared memory for session {session_id}")
                except Exception as e:
                    logging.warning(f"⚠️  Could not clear memory: {e}")

            # Shutdown executor
            if hasattr(self, 'executor') and self.executor:
                try:
                    self.executor.shutdown(wait=True)
                    logging.info(f"🛑 Shutdown executor for session {session_id}")
                except Exception as e:
                    logging.warning(f"⚠️  Could not shutdown executor: {e}")

            logging.info(f"✅ Session {session_id} cleaned up successfully")
            return True

        except Exception as e:
            logging.error(f"❌ Error cleaning up session: {e}")
            return False

    # 🛠️ TOOL MANAGEMENT

    def add_tool(self, tool: AgentTool):
        """Add a tool to the agent"""
        self.tools.append(tool)

    def get_tool(self, tool_name: str) -> Optional[AgentTool]:
        """Get a tool by name"""
        return next((tool for tool in self.tools if tool.name == tool_name), None)

    async def execute_tool(self, tool_name: str, parameters: Dict[str, Any]) -> Dict[str, Any]:
        """Execute a tool with auto-context"""
        tool = self.get_tool(tool_name)
        if not tool:
            raise ValueError(f"Tool {tool_name} not found")

        # Apply auto-context to tool execution
        context_data = await self._with_auto_context("tool_execution",
                                                     tool_name=tool_name,
                                                     parameters=parameters)

        try:
            if asyncio.iscoroutinefunction(tool.function):
                result = await tool.function(**parameters)
            else:
                result = await asyncio.get_event_loop().run_in_executor(
                    self.executor, tool.function, **parameters
                )

            return {
                'success': True,
                'result': result,
                'session_id': self.context.session_id,
                'context': context_data
            }
        except Exception as e:
            return {
                'success': False,
                'error': str(e),
                'session_id': self.context.session_id
            }

    def create_response(self,
                        content: str,
                        recipient_id: str,
                        message_type: MessageType = MessageType.AGENT_RESPONSE,
                        metadata: Dict[str, Any] = None,
                        session_id: str = None,
                        conversation_id: str = None) -> AgentMessage:
        """
        Create a response message with auto-context
        Uses agent's context if session_id/conversation_id not provided
        """
        return AgentMessage(
            id=str(uuid.uuid4()),
            sender_id=self.agent_id,
            recipient_id=recipient_id,
            content=content,
            message_type=message_type,
            metadata=metadata or {},
            session_id=session_id or self.context.session_id,  # 🎯 Auto-context!
            conversation_id=conversation_id or self.context.conversation_id  # 🎯 Auto-context!
        )

    # 📨 ABSTRACT METHOD (must be implemented by subclasses)

    @abstractmethod
    async def process_message(self, message: AgentMessage, context: ExecutionContext = None) -> AgentMessage:
        """
        Process incoming message and return response
        Uses agent's auto-context if context not provided
        """
        if context is None:
            context = self.get_execution_context()

        # Subclasses must implement this
        pass

    def register_agent(self, agent: 'BaseAgent'):
        """Default implementation - only ProxyAgent should override this"""
        return False


# 🎯 CONTEXT MANAGER FOR AUTO-CONTEXT AGENTS

class AgentSession:
    """
    Context manager for BaseAgent instances with automatic cleanup

    Usage:
        async with AgentSession(KnowledgeBaseAgent, user_id="john") as agent:
            result = await agent.chat("What is machine learning?")
            print(f"Session: {agent.context.session_id}")
        # Agent automatically cleaned up
    """

    def __init__(self,
                 agent_class,
                 user_id: str = None,
                 tenant_id: str = "default",
                 session_metadata: Dict[str, Any] = None,
                 **agent_kwargs):
        self.agent_class = agent_class
        self.user_id = user_id
        self.tenant_id = tenant_id
        self.session_metadata = session_metadata
        self.agent_kwargs = agent_kwargs
        self.agent = None

    async def __aenter__(self):
        """Create agent when entering context"""
        self.agent = self.agent_class.create_simple(
            user_id=self.user_id,
            tenant_id=self.tenant_id,
            session_metadata=self.session_metadata,
            **self.agent_kwargs
        )
        return self.agent

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Cleanup agent when exiting context"""
        if self.agent:
            await self.agent.cleanup_session()


# 🚀 CONVENIENCE FUNCTIONS FOR QUICK AGENT USAGE

async def quick_chat(agent_class, message: str, user_id: str = None, **kwargs) -> str:
    """
    🌟 ULTRA-SIMPLIFIED: One-liner agent chat

    Usage:
        response = await quick_chat(YouTubeDownloadAgent, "Download https://youtube.com/watch?v=abc")
        print(response)
    """
    try:
        agent = agent_class.create_simple(user_id=user_id, **kwargs)
        response = await agent.chat(message)
        await agent.cleanup_session()
        return response
    except Exception as e:
        return f"Quick chat error: {str(e)}"


def quick_chat_sync(agent_class, message: str, user_id: str = None, **kwargs) -> str:
    """
    🌟 ULTRA-SIMPLIFIED: One-liner synchronous agent chat

    Usage:
        response = quick_chat_sync(YouTubeDownloadAgent, "Download https://youtube.com/watch?v=abc")
        print(response)
    """
    try:
        return asyncio.run(quick_chat(agent_class, message, user_id, **kwargs))
    except Exception as e:
        return f"Quick sync chat error: {str(e)}"