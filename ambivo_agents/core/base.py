# ambivo_agents/core/base.py - ENHANCED with chat() method
"""
Enhanced BaseAgent with built-in auto-context session management and simplified chat interface
"""

import asyncio
import logging
import os
import tempfile
import time
import uuid
from abc import ABC, abstractmethod
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from pathlib import Path
from typing import Any, AsyncIterator, Callable, Dict, List, Optional, Tuple, Union

# Additional imports for file operations
try:
    import aiohttp

    AIOHTTP_AVAILABLE = True
except ImportError:
    AIOHTTP_AVAILABLE = False

try:
    import aiofiles

    AIOFILES_AVAILABLE = True
except ImportError:
    AIOFILES_AVAILABLE = False

try:
    import yaml

    YAML_AVAILABLE = True
except ImportError:
    YAML_AVAILABLE = False

# Optional requests import for URL fallback
try:
    import requests

    REQUESTS_AVAILABLE = True
except ImportError:
    REQUESTS_AVAILABLE = False

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
            "id": self.id,
            "sender_id": self.sender_id,
            "recipient_id": self.recipient_id,
            "content": self.content,
            "message_type": self.message_type.value,
            "metadata": self.metadata,
            "timestamp": self.timestamp.isoformat(),
            "session_id": self.session_id,
            "conversation_id": self.conversation_id,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "AgentMessage":
        """Create from dictionary"""
        return cls(
            id=data["id"],
            sender_id=data["sender_id"],
            recipient_id=data.get("recipient_id"),
            content=data["content"],
            message_type=MessageType(data["message_type"]),
            metadata=data.get("metadata", {}),
            timestamp=datetime.fromisoformat(data["timestamp"]),
            session_id=data.get("session_id"),
            conversation_id=data.get("conversation_id"),
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
            metadata=self.metadata,
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
            if provider.last_error_time and datetime.now() - provider.last_error_time > timedelta(
                minutes=provider.cooldown_minutes
            ):
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
            (name, config)
            for name, config in self.providers.items()
            if self.is_provider_available(name)
        ]

        if not available_providers:
            return None

        def sort_key(provider_tuple):
            name, config = provider_tuple
            priority = config.priority or 999
            error_count = config.error_count or 0
            return (priority, error_count)

        available_providers.sort(key=sort_key)
        return available_providers[0][0]


class DockerCodeExecutor:
    """Secure code execution using Docker containers"""

    def __init__(self, config: Dict[str, Any]):
        self.config = config
        self.work_dir = config.get("work_dir", "/opt/ambivo/work_dir")
        self.docker_images = config.get("docker_images", ["sgosain/amb-ubuntu-python-public-pod"])
        self.timeout = config.get("timeout", 60)
        self.default_image = (
            self.docker_images[0] if self.docker_images else "sgosain/amb-ubuntu-python-public-pod"
        )

        if DOCKER_AVAILABLE:
            try:
                self.docker_client = docker.from_env()
                self.docker_client.ping()
                self.available = True
            except Exception as e:
                self.available = False
        else:
            self.available = False

    def execute_code(
        self, code: str, language: str = "python", files: Dict[str, str] = None
    ) -> Dict[str, Any]:
        """Execute code in Docker container"""
        if not self.available:
            return {"success": False, "error": "Docker not available", "language": language}

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
                    "image": self.default_image,
                    "command": cmd,
                    "volumes": {str(temp_path): {"bind": "/workspace", "mode": "rw"}},
                    "working_dir": "/workspace",
                    "mem_limit": "512m",
                    "network_disabled": True,
                    "remove": True,
                    "stdout": True,
                    "stderr": True,
                }

                start_time = time.time()
                container = self.docker_client.containers.run(**container_config)
                execution_time = time.time() - start_time

                output = (
                    container.decode("utf-8") if isinstance(container, bytes) else str(container)
                )

                return {
                    "success": True,
                    "output": output,
                    "execution_time": execution_time,
                    "language": language,
                }

        except docker.errors.ContainerError as e:
            return {
                "success": False,
                "error": f"Container error: {e.stderr.decode('utf-8') if e.stderr else 'Unknown error'}",
                "exit_code": e.exit_status,
                "language": language,
            }
        except Exception as e:
            return {"success": False, "error": str(e), "language": language}


class StreamSubType(Enum):
    """Types of streaming content to distinguish between actual results vs interim status"""

    CONTENT = "content"  # Actual response content
    STATUS = "status"  # Status updates, thinking, interim info
    RESULT = "result"  # Search results, data outputs
    ERROR = "error"  # Error messages
    METADATA = "metadata"  # Additional metadata or context


@dataclass
class StreamChunk:
    """Structured streaming chunk with sub-type information"""

    text: str
    sub_type: StreamSubType = StreamSubType.CONTENT
    metadata: Dict[str, Any] = field(default_factory=dict)
    timestamp: datetime = field(default_factory=datetime.now)

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary format for JSON serialization"""
        return {
            "type": "stream_chunk",
            "text": self.text,
            "sub_type": self.sub_type.value,
            "metadata": self.metadata,
            "timestamp": self.timestamp.isoformat(),
        }


class BaseAgent(ABC):
    """
    Enhanced BaseAgent with built-in auto-context session management and simplified chat interface
    Every agent automatically gets a context with session_id, user_id, etc.
    """

    def __init__(
        self,
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
        system_message: str = None,
        **kwargs,
    ):

        # Auto-generate agent_id if not provided
        if agent_id is None:
            agent_id = f"agent_{str(uuid.uuid4())[:8]}"

        self.agent_id = agent_id
        self.role = role
        self.name = name or f"{role.value}_{agent_id[:8]}"
        self.description = description or f"Agent with role: {role.value}"
        self.system_message = system_message or self._get_default_system_message()

        # Load config if not provided and auto-configure is enabled
        if config is None and auto_configure:
            try:
                from ..config.loader import load_config

                config = load_config()
            except Exception as e:
                logging.warning(f"Could not load config for auto-configuration: {e}")
                config = {}

        self.config = config or {}

        self.context = self._create_agent_context(
            user_id, tenant_id, session_metadata, session_id, conversation_id
        )

        # Auto-configure memory if not provided and auto-configure is enabled
        if memory_manager is None and auto_configure:
            try:
                from ..core.memory import create_redis_memory_manager

                self.memory = create_redis_memory_manager(
                    agent_id=agent_id, redis_config=None  # Will load from config automatically
                )
                # logging.info(f"Auto-configured memory for agent {agent_id}")
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

        self.tools = kwargs.get("tools", [])
        self.active = True

        # Initialize executor
        self.executor = ThreadPoolExecutor(max_workers=4)

        # Initialize logger if not already set
        if not hasattr(self, "logger"):
            self.logger = logging.getLogger(f"{self.__class__.__name__}.{self.agent_id}")

        # Initialize skill assignment system
        self.__init_skills__()

    def _get_default_system_message(self) -> str:
        """Get role-specific default system message"""
        role_messages = {
            AgentRole.ASSISTANT: """You are a helpful AI assistant. Provide accurate, thoughtful responses to user queries. 
            Maintain conversation context and reference previous discussions when relevant. 
            Be concise but thorough in explanations.""",
            AgentRole.CODE_EXECUTOR: """You are a code execution specialist. Write clean, well-commented code. 
            Always explain what the code does before execution. Handle errors gracefully and suggest fixes. 
            Use best practices for security and efficiency.""",
            AgentRole.RESEARCHER: """You are a research specialist. Provide thorough, well-sourced information. 
            Verify facts when possible and clearly distinguish between verified information and analysis. 
            Structure your research logically.""",
            AgentRole.COORDINATOR: """You are an intelligent coordinator. Analyze user requests carefully and 
            route them to the most appropriate specialized agent. Consider context, complexity, and agent 
            capabilities when making routing decisions.""",
        }
        return role_messages.get(self.role, "You are a helpful AI agent.")

    def get_system_message_for_llm(self, context: Dict[str, Any] = None) -> str:
        """🆕 Get context-enhanced system message for LLM calls"""
        base_message = self.system_message

        # Add context-specific instructions
        if context:
            conversation_history = context.get("conversation_history", [])
            if conversation_history:
                base_message += "\n\nIMPORTANT: This conversation has history. Consider previous messages when responding and maintain conversational continuity."

            # Add agent-specific context
            if self.role == AgentRole.CODE_EXECUTOR and context.get("streaming"):
                base_message += (
                    "\n\nYou are in streaming mode. Provide step-by-step progress updates."
                )

            elif self.role == AgentRole.COORDINATOR:
                available_agents = context.get("available_agents", [])
                if available_agents:
                    base_message += (
                        f"\n\nAvailable specialized agents: {', '.join(available_agents)}"
                    )

        return base_message

    def _create_agent_context(
        self,
        user_id: str = None,
        tenant_id: str = "default",
        session_metadata: Dict[str, Any] = None,
        session_id: str = None,
        conversation_id: str = None,
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
            metadata=session_metadata or {},
        )

    @classmethod
    def create(
        cls,
        agent_id: str = None,
        user_id: str = None,
        tenant_id: str = "default",
        session_metadata: Dict[str, Any] = None,
        session_id: str = None,
        conversation_id: str = None,
        **kwargs,
    ) -> Tuple["BaseAgent", AgentContext]:
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
            **kwargs,
        )

        return agent, agent.context

    @classmethod
    def create_simple(
        cls,
        agent_id: str = None,
        user_id: str = None,
        tenant_id: str = "default",
        session_metadata: Dict[str, Any] = None,
        **kwargs,
    ) -> "BaseAgent":
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
            **kwargs,
        )

    @classmethod
    def create_advanced(
        cls,
        agent_id: str,
        memory_manager,
        llm_service=None,
        config: Dict[str, Any] = None,
        user_id: str = None,
        tenant_id: str = "default",
        **kwargs,
    ):
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
            **kwargs,
        )

    async def chat(self, message: str, **kwargs) -> str:
        """ """
        try:

            user_message = AgentMessage(
                id=str(uuid.uuid4()),
                sender_id=self.context.user_id,
                recipient_id=self.agent_id,
                content=message,
                message_type=MessageType.USER_INPUT,
                session_id=self.context.session_id,
                conversation_id=self.context.conversation_id,
                metadata={"chat_interface": True, "simplified_call": True, **kwargs},
            )

            execution_context = self.context.to_execution_context()
            execution_context.metadata.update(kwargs)
            agent_response = await self.process_message(user_message, execution_context)
            return agent_response.content

        except Exception as e:
            error_msg = f"Chat error: {str(e)}"
            logging.error(f"Agent {self.agent_id} chat error: {e}")
            return error_msg

    def chat_sync(self, message: str, **kwargs) -> str:
        """
        Synchronous version of chat() that properly handles event loops

        Args:
            message: User message as string
            **kwargs: Optional metadata to add to the message

        Returns:
            Agent response as string
        """
        try:
            # Check if we're already in an async context
            try:
                # Try to get the current event loop
                loop = asyncio.get_running_loop()
                # If we get here, we're in an async context - use run_in_executor
                import concurrent.futures
                import threading

                def run_chat():
                    # Create new event loop in thread
                    new_loop = asyncio.new_event_loop()
                    asyncio.set_event_loop(new_loop)
                    try:
                        # Filter out timeout parameter for async chat call
                        filtered_kwargs = {k: v for k, v in kwargs.items() if k != "timeout"}
                        return new_loop.run_until_complete(self.chat(message, **filtered_kwargs))
                    finally:
                        new_loop.close()

                with concurrent.futures.ThreadPoolExecutor() as executor:
                    future = executor.submit(run_chat)
                    return future.result()

            except RuntimeError:
                # No event loop running, safe to use asyncio.run()
                # Filter out timeout parameter that asyncio.run() doesn't accept
                filtered_kwargs = {k: v for k, v in kwargs.items() if k != "timeout"}
                return asyncio.run(self.chat(message, **filtered_kwargs))

        except Exception as e:
            error_msg = f"Sync chat error: {str(e)}"
            logging.error(f"Agent {self.agent_id} sync chat error: {e}")
            return error_msg

    async def chat_stream(self, message: str, **kwargs) -> AsyncIterator[StreamChunk]:
        """
        🌟 NEW: Streaming chat interface that yields response chunks

        Args:
            message: User message as string
            **kwargs: Optional metadata to add to the message

        Yields:
            StreamChunk objects with structured data and sub_type information

        Usage:
            agent, context = YouTubeDownloadAgent.create(user_id="john")
            async for chunk in agent.chat_stream("Download https://youtube.com/watch?v=abc123"):
                print(chunk.text, end='', flush=True)
                print(f"Sub-type: {chunk.sub_type.value}")
        """
        try:
            # Create AgentMessage from string using auto-context
            user_message = AgentMessage(
                id=str(uuid.uuid4()),
                sender_id=self.context.user_id,
                recipient_id=self.agent_id,
                content=message,
                message_type=MessageType.USER_INPUT,
                session_id=self.context.session_id,
                conversation_id=self.context.conversation_id,
                metadata={"chat_interface": True, "streaming_call": True, **kwargs},
            )

            # Get execution context from auto-context
            execution_context = self.context.to_execution_context()
            execution_context.metadata.update(kwargs)

            # Stream the response
            async for chunk in self.process_message_stream(user_message, execution_context):
                yield chunk

        except Exception as e:
            error_msg = f"Streaming chat error: {str(e)}"
            logging.error(f"Agent {self.agent_id} streaming chat error: {e}")
            yield StreamChunk(
                text=error_msg,
                sub_type=StreamSubType.ERROR,
                metadata={"error": True, "agent_id": self.agent_id},
            )

    @abstractmethod
    async def process_message_stream(
        self, message: AgentMessage, context: ExecutionContext = None
    ) -> AsyncIterator[StreamChunk]:
        """
        🌟 NEW: Stream processing method - must be implemented by subclasses

        Args:
            message: The user message to process
            context: Execution context (uses auto-context if None)

        Yields:
            StreamChunk objects with structured data and sub_type information
        """
        if context is None:
            context = self.get_execution_context()

        # Subclasses must implement this
        raise NotImplementedError("Subclasses must implement process_message_stream")

    def get_context(self) -> AgentContext:
        """Get the agent's auto-generated context"""
        return self.context

    def get_execution_context(self) -> ExecutionContext:
        """Get ExecutionContext for operations that need it"""
        return self.context.to_execution_context()

    def update_context_metadata(self, **kwargs):
        """Update context metadata"""
        self.context.update_metadata(**kwargs)

    async def get_conversation_history(
        self, limit: int = None, include_metadata: bool = True
    ) -> List[Dict[str, Any]]:
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
                limit=limit or 10, conversation_id=self.context.conversation_id
            )

            # Add context information to each message
            enriched_history = []
            for msg in history:
                if include_metadata:
                    msg_with_context = {
                        **msg,
                        "session_id": self.context.session_id,
                        "user_id": self.context.user_id,
                        "agent_id": self.agent_id,
                        "conversation_id": self.context.conversation_id,
                    }
                else:
                    msg_with_context = msg

                enriched_history.append(msg_with_context)

            return enriched_history

        except Exception as e:
            logging.error(f"Failed to get conversation history for {self.agent_id}: {e}")
            return []

    async def add_to_conversation_history(
        self, message: str, message_type: str = "user", metadata: Dict[str, Any] = None
    ) -> bool:
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
                message_type=(
                    MessageType.AGENT_RESPONSE
                    if message_type == "agent"
                    else MessageType.USER_INPUT
                ),
                session_id=self.context.session_id,
                conversation_id=self.context.conversation_id,
                metadata={
                    "type": message_type,
                    "user_id": self.context.user_id,
                    "agent_id": self.agent_id,
                    **(metadata or {}),
                },
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
                    "total_messages": 0,
                    "user_messages": 0,
                    "agent_messages": 0,
                    "session_duration": "0 minutes",
                    "first_message": None,
                    "last_message": None,
                    "session_id": self.context.session_id,
                }

            # Analyze conversation
            total_messages = len(history)
            user_messages = len([msg for msg in history if msg.get("message_type") == "user_input"])
            agent_messages = len(
                [msg for msg in history if msg.get("message_type") == "agent_response"]
            )

            # Calculate session duration
            first_msg_time = self.context.created_at
            last_msg_time = datetime.now()
            duration = last_msg_time - first_msg_time
            duration_minutes = int(duration.total_seconds() / 60)

            return {
                "total_messages": total_messages,
                "user_messages": user_messages,
                "agent_messages": agent_messages,
                "session_duration": f"{duration_minutes} minutes",
                "first_message": (
                    history[0].get("content", "")[:100] + "..."
                    if len(history[0].get("content", "")) > 100
                    else history[0].get("content", "") if history else None
                ),
                "last_message": (
                    history[-1].get("content", "")[:100] + "..."
                    if len(history[-1].get("content", "")) > 100
                    else history[-1].get("content", "") if history else None
                ),
                "session_id": self.context.session_id,
                "conversation_id": self.context.conversation_id,
                "user_id": self.context.user_id,
            }

        except Exception as e:
            logging.error(f"Failed to get conversation summary for {self.agent_id}: {e}")
            return {"error": str(e), "session_id": self.context.session_id}

    async def _with_auto_context(self, operation_name: str, **kwargs) -> Dict[str, Any]:
        """
        Internal method that automatically applies context to operations
        All agent operations should use this to ensure context is applied
        """
        execution_context = self.get_execution_context()

        # Add context info to operation metadata
        operation_metadata = {
            "session_id": self.context.session_id,
            "user_id": self.context.user_id,
            "tenant_id": self.context.tenant_id,
            "operation": operation_name,
            "timestamp": datetime.now().isoformat(),
            **kwargs,
        }

        # Update context metadata
        self.context.update_metadata(**operation_metadata)

        return {"execution_context": execution_context, "operation_metadata": operation_metadata}

    # 🧹 SESSION CLEANUP

    async def cleanup_session(self) -> bool:
        """Cleanup the agent's session and resources"""
        try:
            session_id = self.context.session_id

            # Clear memory for this session
            if hasattr(self, "memory") and self.memory:
                try:
                    # Commented out temporarily as noted in original
                    # self.memory.clear_memory(self.context.conversation_id)
                    logging.info(f"🧹 Cleared memory for session {session_id}")
                except Exception as e:
                    logging.warning(f"⚠️  Could not clear memory: {e}")

            # Cleanup skill agents
            if hasattr(self, "_skill_agents"):
                try:
                    await self.cleanup_skill_agents()
                    logging.info(f"🔧 Cleaned up skill agents for session {session_id}")
                except Exception as e:
                    logging.warning(f"⚠️  Could not cleanup skill agents: {e}")

            # Shutdown executor
            if hasattr(self, "executor") and self.executor:
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
        context_data = await self._with_auto_context(
            "tool_execution", tool_name=tool_name, parameters=parameters
        )

        try:
            if asyncio.iscoroutinefunction(tool.function):
                result = await tool.function(**parameters)
            else:
                result = await asyncio.get_event_loop().run_in_executor(
                    self.executor, tool.function, **parameters
                )

            return {
                "success": True,
                "result": result,
                "session_id": self.context.session_id,
                "context": context_data,
            }
        except Exception as e:
            return {"success": False, "error": str(e), "session_id": self.context.session_id}

    def create_response(
        self,
        content: str,
        recipient_id: str,
        message_type: MessageType = MessageType.AGENT_RESPONSE,
        metadata: Dict[str, Any] = None,
        session_id: str = None,
        conversation_id: str = None,
    ) -> AgentMessage:
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
            conversation_id=conversation_id or self.context.conversation_id,  # 🎯 Auto-context!
        )

    # 📨 ABSTRACT METHOD (must be implemented by subclasses)

    @abstractmethod
    async def process_message(
        self, message: AgentMessage, context: ExecutionContext = None
    ) -> AgentMessage:
        """
        Process incoming message and return response
        Uses agent's auto-context if context not provided
        """
        if context is None:
            context = self.get_execution_context()

        # Subclasses must implement this
        pass

    # 📁 FILE OPERATIONS (Available to all agents)

    def _is_path_restricted(self, file_path: str) -> bool:
        """
        Check if a file path is in a restricted directory

        Args:
            file_path: File path to check

        Returns:
            True if the path is restricted, False otherwise
        """
        try:
            from pathlib import Path
            import os

            # Get restricted directories from config
            restricted_dirs = []
            if hasattr(self, "config") and self.config:
                restricted_dirs = (
                    self.config.get("security", {})
                    .get("file_access", {})
                    .get("restricted_directories", [])
                )

            if not restricted_dirs:
                return False

            # Resolve the file path to absolute path
            resolved_path = Path(file_path).expanduser().resolve()

            # Check each restricted directory
            for restricted_dir in restricted_dirs:
                # Expand user home directory (~) and resolve to absolute path
                restricted_path = Path(restricted_dir).expanduser().resolve()

                # Check if the file path is within this restricted directory
                try:
                    resolved_path.relative_to(restricted_path)
                    return True  # Path is within restricted directory
                except ValueError:
                    # Not within this restricted directory, continue checking
                    continue

            return False

        except Exception:
            # If any error occurs in checking, err on the side of caution
            return True

    async def read_file(self, file_path: str, encoding: str = "utf-8") -> Dict[str, Any]:
        """
        Read a file from local filesystem or URL

        Args:
            file_path: Local file path or URL (http/https)
            encoding: Text encoding (default: utf-8)

        Returns:
            Dict with success status, content, and metadata
        """
        try:
            # Check for restricted paths first (only for local files)
            if not file_path.startswith(("http://", "https://")):
                if self._is_path_restricted(file_path):
                    return {
                        "success": False,
                        "error": f'Access denied: File path "{file_path}" is in a restricted directory for security reasons',
                    }
            import mimetypes

            # Check if it's a URL
            if file_path.startswith(("http://", "https://")):
                # Prefer aiohttp when available, fallback to requests
                if AIOHTTP_AVAILABLE:
                    import aiohttp

                    async with aiohttp.ClientSession() as session:
                        async with session.get(file_path) as response:
                            response.raise_for_status()
                            content = await response.text()
                            return {
                                "success": True,
                                "content": content,
                                "source": "url",
                                "path": file_path,
                                "size": len(content),
                                "content_type": response.headers.get("Content-Type", "text/plain"),
                                "encoding": encoding,
                            }
                elif REQUESTS_AVAILABLE:
                    try:
                        resp = requests.get(file_path, timeout=15)
                        resp.raise_for_status()
                        content = resp.text
                        return {
                            "success": True,
                            "content": content,
                            "source": "url",
                            "path": file_path,
                            "size": len(content),
                            "content_type": resp.headers.get("Content-Type", "text/plain"),
                            "encoding": resp.encoding or encoding,
                        }
                    except Exception as e:
                        return {"success": False, "error": str(e), "path": file_path}
                else:
                    return {
                        "success": False,
                        "error": "No HTTP client available. Install aiohttp or requests to read URLs.",
                    }
            else:
                # Read from local file
                path = Path(file_path)

                # Try multiple path resolutions
                if not path.is_absolute():
                    # Try relative to current directory
                    if not path.exists():
                        # Try relative to project root or common directories
                        possible_paths = [
                            Path.cwd() / path,
                            Path.home() / path,
                        ]
                        for p in possible_paths:
                            if p.exists():
                                path = p
                                break

                if not path.exists():
                    return {
                        "success": False,
                        "error": f"File not found: {file_path}",
                        "tried_paths": (
                            [str(p) for p in possible_paths]
                            if "possible_paths" in locals()
                            else [str(path)]
                        ),
                    }

                # Detect file type
                mime_type, _ = mimetypes.guess_type(str(path))

                # Read file
                if path.suffix.lower() in [".json", ".csv", ".txt", ".xml", ".yml", ".yaml"]:
                    if AIOFILES_AVAILABLE:
                        import aiofiles

                        async with aiofiles.open(path, mode="r", encoding=encoding) as f:
                            content = await f.read()
                    else:
                        # Fallback to sync read
                        with open(path, "r", encoding=encoding) as f:
                            content = f.read()
                else:
                    # Binary file
                    if AIOFILES_AVAILABLE:
                        import aiofiles

                        async with aiofiles.open(path, mode="rb") as f:
                            content = await f.read()
                    else:
                        # Fallback to sync read
                        with open(path, "rb") as f:
                            content = f.read()

                    return {
                        "success": True,
                        "content": content,
                        "source": "local",
                        "path": str(path),
                        "size": len(content),
                        "content_type": mime_type or "application/octet-stream",
                        "encoding": None,
                        "is_binary": True,
                    }

                return {
                    "success": True,
                    "content": content,
                    "source": "local",
                    "path": str(path),
                    "size": len(content),
                    "content_type": mime_type or "text/plain",
                    "encoding": encoding,
                    "extension": path.suffix,
                }

        except Exception as e:
            return {"success": False, "error": str(e), "path": file_path}

    async def parse_file_content(
        self, content: str, file_type: str = None, file_path: str = None
    ) -> Dict[str, Any]:
        """
        Parse file content based on type

        Args:
            content: File content as string
            file_type: Type of file (json, csv, xml, txt)
            file_path: Optional file path to infer type

        Returns:
            Parsed content as appropriate data structure
        """
        try:
            import json
            import csv
            import xml.etree.ElementTree as ET
            import yaml
            from io import StringIO

            # Infer file type from path if not provided
            if not file_type and file_path:
                ext = Path(file_path).suffix.lower()
                file_type = ext[1:] if ext else "txt"

            file_type = (file_type or "txt").lower()

            if file_type == "json":
                # Parse JSON
                data = json.loads(content)
                return {
                    "success": True,
                    "data": data,
                    "type": "json",
                    "is_array": isinstance(data, list),
                    "is_object": isinstance(data, dict),
                    "count": len(data) if isinstance(data, (list, dict)) else 1,
                }

            elif file_type == "csv":
                # Parse CSV
                reader = csv.DictReader(StringIO(content))
                data = list(reader)

                # Get column names
                columns = data[0].keys() if data else []

                return {
                    "success": True,
                    "data": data,
                    "type": "csv",
                    "columns": list(columns),
                    "row_count": len(data),
                }

            elif file_type == "xml":
                # Parse XML
                root = ET.fromstring(content)

                def xml_to_dict(element):
                    result = {}
                    for child in element:
                        if len(child) == 0:
                            result[child.tag] = child.text
                        else:
                            result[child.tag] = xml_to_dict(child)
                    return result

                data = {root.tag: xml_to_dict(root)}

                return {"success": True, "data": data, "type": "xml", "root_tag": root.tag}

            elif file_type in ["yml", "yaml"]:
                # Parse YAML
                if not YAML_AVAILABLE:
                    return {
                        "success": False,
                        "error": "PyYAML not available. Install with: pip install PyYAML",
                    }
                import yaml

                data = yaml.safe_load(content)
                return {"success": True, "data": data, "type": "yaml"}

            else:
                # Plain text
                return {
                    "success": True,
                    "data": content,
                    "type": "text",
                    "lines": content.count("\n") + 1,
                    "characters": len(content),
                }

        except Exception as e:
            return {
                "success": False,
                "error": str(e),
                "content_preview": content[:200] + "..." if len(content) > 200 else content,
            }

    async def convert_json_to_csv(self, json_data: Union[str, list, dict]) -> Dict[str, Any]:
        """
        Convert JSON data to CSV format

        Args:
            json_data: JSON string, list of dicts, or single dict

        Returns:
            Dict with CSV content and metadata
        """
        try:
            import json
            import csv
            from io import StringIO

            # Parse JSON if string
            if isinstance(json_data, str):
                data = json.loads(json_data)
            else:
                data = json_data

            # Ensure data is a list
            if isinstance(data, dict):
                data = [data]
            elif not isinstance(data, list):
                return {
                    "success": False,
                    "error": "JSON data must be an object or array of objects",
                }

            if not data:
                return {"success": True, "csv": "", "rows": 0, "columns": []}

            # Get all unique keys
            all_keys = set()
            for item in data:
                if isinstance(item, dict):
                    all_keys.update(item.keys())

            # Create CSV
            output = StringIO()
            writer = csv.DictWriter(output, fieldnames=sorted(all_keys))
            writer.writeheader()
            writer.writerows(data)

            csv_content = output.getvalue()

            return {
                "success": True,
                "csv": csv_content,
                "rows": len(data),
                "columns": sorted(all_keys),
            }

        except Exception as e:
            return {"success": False, "error": str(e)}

    async def convert_csv_to_json(
        self, csv_data: str, numeric_conversion: bool = True
    ) -> Dict[str, Any]:
        """
        Convert CSV data to JSON format

        Args:
            csv_data: CSV content as string
            numeric_conversion: Convert numeric strings to numbers

        Returns:
            Dict with JSON data and metadata
        """
        try:
            import csv
            import json
            from io import StringIO

            # Parse CSV
            reader = csv.DictReader(StringIO(csv_data))
            data = []

            for row in reader:
                if numeric_conversion:
                    # Convert numeric strings
                    converted_row = {}
                    for key, value in row.items():
                        if value == "":
                            converted_row[key] = None
                        elif value.isdigit():
                            converted_row[key] = int(value)
                        else:
                            try:
                                converted_row[key] = float(value)
                            except ValueError:
                                converted_row[key] = value
                    data.append(converted_row)
                else:
                    data.append(row)

            return {
                "success": True,
                "json": data,
                "json_string": json.dumps(data, indent=2),
                "rows": len(data),
                "columns": list(data[0].keys()) if data else [],
            }

        except Exception as e:
            return {"success": False, "error": str(e)}

    async def read_and_parse_file(self, file_path: str, auto_parse: bool = True) -> Dict[str, Any]:
        """
        Convenience method to read and parse a file in one operation

        Args:
            file_path: Local path or URL
            auto_parse: Automatically parse based on file type

        Returns:
            Combined result with content and parsed data
        """
        # Read file
        read_result = await self.read_file(file_path)

        if not read_result["success"]:
            return read_result

        if not auto_parse or read_result.get("is_binary"):
            return read_result

        # Parse content
        content = read_result["content"]
        file_type = None

        if "extension" in read_result:
            file_type = read_result["extension"][1:]  # Remove dot
        elif "." in file_path:
            file_type = file_path.split(".")[-1]

        parse_result = await self.parse_file_content(content, file_type, file_path)

        # Combine results
        return {**read_result, "parsed": parse_result["success"], "parse_result": parse_result}

    def register_agent(self, agent: "BaseAgent"):
        """Default implementation - only ProxyAgent should override this"""
        return False

    def resolve_file_path(self, filename: str, agent_type: Optional[str] = None) -> Optional[Path]:
        """
        Universal file resolution for all agents using shared_base_dir configuration.

        Args:
            filename: Name or relative path of file to find
            agent_type: Agent type override (analytics, media, code, database, scraper)
                       If None, will auto-detect from class name

        Returns:
            Resolved Path object if file exists, None otherwise
        """
        try:
            # Import here to avoid circular import
            from .file_resolution import resolve_agent_file_path, get_agent_type_from_config

            # Auto-detect agent type if not provided
            if agent_type is None:
                agent_type = get_agent_type_from_config(self.__class__.__name__)

            return resolve_agent_file_path(filename, agent_type)
        except Exception:
            # Fallback to simple path check
            if Path(filename).exists():
                return Path(filename)
            return None

    # 🛠️ SKILL ASSIGNMENT SYSTEM

    def __init_skills__(self):
        """Initialize skill assignment system (called during __init__)"""
        if not hasattr(self, "_assigned_skills"):
            self._assigned_skills = {
                "api_skills": {},  # API specs and configs
                "database_skills": {},  # Database connections
                "kb_skills": {},  # Knowledge base configs
            }
            self._skill_agents = {}  # Cache for instantiated skill agents

    async def assign_api_skill(
        self,
        api_spec_path: str,
        base_url: str = None,
        api_token: str = None,
        skill_name: str = None,
    ) -> Dict[str, Any]:
        """
        Assign an API skill to this agent by providing an OpenAPI spec

        Args:
            api_spec_path: Path to OpenAPI spec (YAML or JSON) or URL
            base_url: Base URL for API calls (overrides spec servers)
            api_token: Authentication token for API
            skill_name: Optional name for this skill (defaults to API title)

        Returns:
            Dict with success status and skill details
        """
        try:
            if not hasattr(self, "_assigned_skills"):
                self.__init_skills__()

            # Read and parse API spec
            spec_result = await self.read_and_parse_file(api_spec_path)
            if not spec_result["success"]:
                return {
                    "success": False,
                    "error": f"Failed to read API spec: {spec_result['error']}",
                }

            if not spec_result.get("parsed"):
                return {"success": False, "error": "Could not parse API specification"}

            api_spec = spec_result["parse_result"]["data"]

            # Extract skill name from spec if not provided
            if not skill_name:
                skill_name = api_spec.get("info", {}).get(
                    "title", f"api_skill_{len(self._assigned_skills['api_skills'])}"
                )

            # Extract base URL from spec if not provided
            if not base_url and "servers" in api_spec:
                base_url = api_spec["servers"][0]["url"]

            # Store skill configuration
            skill_config = {
                "spec": api_spec,
                "base_url": base_url,
                "api_token": api_token,
                "spec_path": api_spec_path,
                "assigned_at": datetime.now().isoformat(),
                "endpoints": self._extract_api_endpoints(api_spec),
            }

            self._assigned_skills["api_skills"][skill_name] = skill_config

            self.logger.info(
                f"Assigned API skill '{skill_name}' with {len(skill_config['endpoints'])} endpoints"
            )

            return {
                "success": True,
                "skill_name": skill_name,
                "endpoints_count": len(skill_config["endpoints"]),
                "base_url": base_url,
                "api_title": api_spec.get("info", {}).get("title", "Unknown"),
            }

        except Exception as e:
            return {"success": False, "error": f"Failed to assign API skill: {str(e)}"}

    async def assign_database_skill(
        self, connection_string: str, skill_name: str = None, description: str = None
    ) -> Dict[str, Any]:
        """
        Assign a database skill to this agent

        Args:
            connection_string: Database connection string or config dict
            skill_name: Optional name for this skill
            description: Optional description of the database

        Returns:
            Dict with success status and skill details
        """
        try:
            if not hasattr(self, "_assigned_skills"):
                self.__init_skills__()

            # Generate skill name if not provided
            if not skill_name:
                # Extract database name from connection string
                if "database=" in connection_string:
                    db_name = connection_string.split("database=")[1].split(";")[0].split("&")[0]
                    skill_name = f"db_{db_name}"
                else:
                    skill_name = f"database_skill_{len(self._assigned_skills['database_skills'])}"

            # Store skill configuration
            skill_config = {
                "connection_string": connection_string,
                "description": description,
                "assigned_at": datetime.now().isoformat(),
                "type": self._detect_database_type(connection_string),
            }

            self._assigned_skills["database_skills"][skill_name] = skill_config

            self.logger.info(f"Assigned database skill '{skill_name}' ({skill_config['type']})")

            return {
                "success": True,
                "skill_name": skill_name,
                "database_type": skill_config["type"],
                "description": description,
            }

        except Exception as e:
            return {"success": False, "error": f"Failed to assign database skill: {str(e)}"}

    async def assign_kb_skill(
        self, documents_path: str, collection_name: str = None, skill_name: str = None
    ) -> Dict[str, Any]:
        """
        Assign a knowledge base skill to this agent

        Args:
            documents_path: Path to documents or directory to ingest
            collection_name: Qdrant collection name
            skill_name: Optional name for this skill

        Returns:
            Dict with success status and skill details
        """
        try:
            if not hasattr(self, "_assigned_skills"):
                self.__init_skills__()

            # Generate names if not provided
            if not skill_name:
                path_name = Path(documents_path).stem
                skill_name = f"kb_{path_name}"

            if not collection_name:
                collection_name = f"collection_{skill_name}"

            # Store skill configuration
            skill_config = {
                "documents_path": documents_path,
                "collection_name": collection_name,
                "assigned_at": datetime.now().isoformat(),
            }

            self._assigned_skills["kb_skills"][skill_name] = skill_config

            self.logger.info(
                f"Assigned knowledge base skill '{skill_name}' for collection '{collection_name}'"
            )

            return {
                "success": True,
                "skill_name": skill_name,
                "collection_name": collection_name,
                "documents_path": documents_path,
            }

        except Exception as e:
            return {"success": False, "error": f"Failed to assign KB skill: {str(e)}"}

    def list_assigned_skills(self) -> Dict[str, Any]:
        """List all assigned skills"""
        if not hasattr(self, "_assigned_skills"):
            self.__init_skills__()

        summary = {
            "api_skills": list(self._assigned_skills["api_skills"].keys()),
            "database_skills": list(self._assigned_skills["database_skills"].keys()),
            "kb_skills": list(self._assigned_skills["kb_skills"].keys()),
            "total_skills": (
                len(self._assigned_skills["api_skills"])
                + len(self._assigned_skills["database_skills"])
                + len(self._assigned_skills["kb_skills"])
            ),
        }

        return summary

    def _extract_api_endpoints(self, api_spec: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Extract endpoint information from OpenAPI spec"""
        endpoints = []

        for path, methods in api_spec.get("paths", {}).items():
            for method, details in methods.items():
                if method.upper() in ["GET", "POST", "PUT", "DELETE", "PATCH"]:
                    endpoints.append(
                        {
                            "path": path,
                            "method": method.upper(),
                            "operation_id": details.get("operationId"),
                            "summary": details.get("summary"),
                            "description": details.get("description"),
                            "tags": details.get("tags", []),
                        }
                    )

        return endpoints

    def _detect_database_type(self, connection_string: str) -> str:
        """Detect database type from connection string"""
        connection_lower = connection_string.lower()

        if connection_lower.startswith("mongodb://") or connection_lower.startswith(
            "mongodb+srv://"
        ):
            return "mongodb"
        elif "postgresql://" in connection_lower or "postgres://" in connection_lower:
            return "postgresql"
        elif "mysql://" in connection_lower or "mysql+" in connection_lower:
            return "mysql"
        elif "sqlite:///" in connection_lower:
            return "sqlite"
        else:
            return "unknown"

    # 🎯 INTENT CLASSIFICATION FOR SKILLS

    async def _classify_intent_for_skills(self, message: str) -> Dict[str, Any]:
        """
        Classify user intent to determine if assigned skills should be used

        Args:
            message: User message content

        Returns:
            Dict with intent classification and skill routing information
        """
        if not hasattr(self, "_assigned_skills"):
            return {"should_use_skills": False, "reason": "no_skills_assigned"}

        message_lower = message.lower()
        intent_result = {
            "should_use_skills": False,
            "skill_type": None,
            "skill_name": None,
            "confidence": 0.0,
            "reasoning": [],
        }

        # API Skills Detection
        api_keywords = [
            "create lead",
            "make lead",
            "add lead",
            "new lead",
            "list leads",
            "show leads",
            "get leads",
            "find leads",
            "send email",
            "send message",
            "email to",
            "send sms",
            "text message",
            "sms to",
            "call api",
            "api call",
            "make request",
            "post to",
            "get from",
            "create contact",
            "add contact",
            "new contact",
            "list contacts",
            "show contacts",
            "get contacts",
        ]

        for keyword in api_keywords:
            if keyword in message_lower:
                # Find best matching API skill
                best_skill = self._find_best_api_skill_for_intent(message_lower, keyword)
                if best_skill:
                    intent_result.update(
                        {
                            "should_use_skills": True,
                            "skill_type": "api",
                            "skill_name": best_skill,
                            "confidence": 0.8,
                            "reasoning": [f"Matched API keyword: '{keyword}'"],
                        }
                    )
                    break

        # Database Skills Detection
        if not intent_result["should_use_skills"]:
            db_keywords = [
                "query database",
                "database query",
                "select from",
                "sql query",
                "show tables",
                "describe table",
                "table structure",
                "count records",
                "show data",
                "database data",
                "recent sales",
                "sales data",
                "customer data",
                "order data",
                "database",
                "sql",
                "select",
                "from table",
            ]

            for keyword in db_keywords:
                if keyword in message_lower:
                    # Use first database skill if multiple available
                    if self._assigned_skills["database_skills"]:
                        skill_name = list(self._assigned_skills["database_skills"].keys())[0]
                        intent_result.update(
                            {
                                "should_use_skills": True,
                                "skill_type": "database",
                                "skill_name": skill_name,
                                "confidence": 0.7,
                                "reasoning": [f"Matched database keyword: '{keyword}'"],
                            }
                        )
                        break

        # Knowledge Base Skills Detection
        if not intent_result["should_use_skills"]:
            kb_keywords = [
                "what do our docs say",
                "according to documentation",
                "in our documents",
                "search documents",
                "find in docs",
                "knowledge base",
                "what does the manual say",
                "company policy",
                "documentation",
                "search knowledge",
                "find information about",
            ]

            for keyword in kb_keywords:
                if keyword in message_lower:
                    # Use first KB skill if multiple available
                    if self._assigned_skills["kb_skills"]:
                        skill_name = list(self._assigned_skills["kb_skills"].keys())[0]
                        intent_result.update(
                            {
                                "should_use_skills": True,
                                "skill_type": "kb",
                                "skill_name": skill_name,
                                "confidence": 0.7,
                                "reasoning": [f"Matched KB keyword: '{keyword}'"],
                            }
                        )
                        break

        # Enhanced LLM-based intent classification (if LLM available)
        if not intent_result["should_use_skills"] and self.llm_service:
            llm_intent = await self._llm_based_intent_classification(message)
            if llm_intent["should_use_skills"]:
                intent_result.update(llm_intent)

        return intent_result

    def _find_best_api_skill_for_intent(self, message: str, matched_keyword: str) -> Optional[str]:
        """Find the best API skill for a given intent"""
        if not self._assigned_skills["api_skills"]:
            return None

        # Simple matching - could be enhanced with more sophisticated logic
        for skill_name, skill_config in self._assigned_skills["api_skills"].items():
            endpoints = skill_config.get("endpoints", [])

            # Check if any endpoint matches the intent
            for endpoint in endpoints:
                summary = (endpoint.get("summary") or "").lower()
                description = (endpoint.get("description") or "").lower()
                operation_id = (endpoint.get("operation_id") or "").lower()

                # Match keywords to endpoint descriptions
                if "lead" in matched_keyword and (
                    "lead" in summary or "lead" in description or "lead" in operation_id
                ):
                    return skill_name
                elif "email" in matched_keyword and ("email" in summary or "email" in description):
                    return skill_name
                elif "sms" in matched_keyword and ("sms" in summary or "sms" in description):
                    return skill_name
                elif "contact" in matched_keyword and (
                    "contact" in summary or "contact" in description
                ):
                    return skill_name

        # Return first API skill as fallback
        return list(self._assigned_skills["api_skills"].keys())[0]

    async def _llm_based_intent_classification(self, message: str) -> Dict[str, Any]:
        """Use LLM to classify intent for skill usage"""
        try:
            # Build skills context for LLM
            skills_context = []

            for skill_name, skill_config in self._assigned_skills["api_skills"].items():
                api_info = skill_config["spec"].get("info", {})
                skills_context.append(
                    f"API Skill '{skill_name}': {api_info.get('title', 'Unknown')} - {api_info.get('description', 'No description')}"
                )

            for skill_name, skill_config in self._assigned_skills["database_skills"].items():
                skills_context.append(
                    f"Database Skill '{skill_name}': {skill_config['type']} database - {skill_config.get('description', 'No description')}"
                )

            for skill_name, skill_config in self._assigned_skills["kb_skills"].items():
                skills_context.append(
                    f"Knowledge Base Skill '{skill_name}': Documents from {skill_config['documents_path']}"
                )

            if not skills_context:
                return {"should_use_skills": False, "reason": "no_skills_available"}

            prompt = f"""Analyze this user message and determine if it should use one of the assigned skills:

User message: "{message}"

Available skills:
{chr(10).join(skills_context)}

Respond with JSON only:
{{
    "should_use_skills": true/false,
    "skill_type": "api/database/kb" or null,
    "skill_name": "exact_skill_name" or null,
    "confidence": 0.0-1.0,
    "reasoning": ["explanation of why this skill matches"]
}}

Only return JSON, no other text."""

            response = await self.llm_service.generate_response(
                prompt,
                context={"conversation_history": []},
                system_message="You are a precise intent classifier. Respond only with valid JSON.",
            )

            if response:
                import json

                # Extract JSON from response
                response_str = str(response)
                start = response_str.find("{")
                end = response_str.rfind("}")
                if start != -1 and end != -1:
                    result = json.loads(response_str[start : end + 1])

                    # Validate the skill exists
                    if result.get("should_use_skills") and result.get("skill_name"):
                        skill_type = result.get("skill_type")
                        skill_name = result.get("skill_name")

                        if (
                            skill_type in self._assigned_skills
                            and skill_name in self._assigned_skills[skill_type + "_skills"]
                        ):
                            return result

            return {"should_use_skills": False, "reason": "llm_classification_failed"}

        except Exception as e:
            self.logger.warning(f"LLM-based intent classification failed: {e}")
            return {"should_use_skills": False, "reason": f"llm_error: {str(e)}"}

    # 🚀 DYNAMIC AGENT INSTANTIATION

    async def _get_or_create_skill_agent(self, skill_type: str, skill_name: str) -> Optional[Any]:
        """
        Get or create a specialized agent for the given skill

        Args:
            skill_type: Type of skill (api, database, kb)
            skill_name: Name of the specific skill

        Returns:
            Instantiated specialized agent or None if failed
        """
        try:
            # Check cache first
            cache_key = f"{skill_type}_{skill_name}"
            if cache_key in self._skill_agents:
                return self._skill_agents[cache_key]

            # Import agents dynamically to avoid circular imports
            if skill_type == "api":
                from ..agents.api_agent import APIAgent

                skill_config = self._assigned_skills["api_skills"][skill_name]

                # Configure APIAgent with the API spec
                agent_config = {
                    "api_agent": {
                        "allowed_domains": (
                            [skill_config["base_url"]] if skill_config["base_url"] else None
                        ),
                        "verify_ssl": True,
                        "timeout_seconds": 30,
                    }
                }

                agent = APIAgent.create_simple(
                    user_id=self.context.user_id,
                    config=agent_config,
                    session_id=self.context.session_id,
                    conversation_id=self.context.conversation_id,
                )

                # Store API spec and config in agent for easy access
                agent._assigned_api_spec = skill_config["spec"]
                agent._assigned_base_url = skill_config["base_url"]
                agent._assigned_api_token = skill_config["api_token"]

            elif skill_type == "database":
                try:
                    from ..agents.database_agent import DatabaseAgent
                except ImportError:
                    self.logger.error(
                        "DatabaseAgent not available. Install with: pip install ambivo-agents[database]"
                    )
                    return None

                skill_config = self._assigned_skills["database_skills"][skill_name]

                agent = DatabaseAgent.create_simple(
                    user_id=self.context.user_id,
                    session_id=self.context.session_id,
                    conversation_id=self.context.conversation_id,
                )

                # Store connection info
                agent._assigned_connection_string = skill_config["connection_string"]
                agent._assigned_db_type = skill_config["type"]

            elif skill_type == "kb":
                from ..agents.knowledge_base import KnowledgeBaseAgent

                skill_config = self._assigned_skills["kb_skills"][skill_name]

                agent = KnowledgeBaseAgent.create_simple(
                    user_id=self.context.user_id,
                    session_id=self.context.session_id,
                    conversation_id=self.context.conversation_id,
                )

                # Store KB config
                agent._assigned_documents_path = skill_config["documents_path"]
                agent._assigned_collection_name = skill_config["collection_name"]

            else:
                self.logger.error(f"Unknown skill type: {skill_type}")
                return None

            # Cache the agent
            self._skill_agents[cache_key] = agent

            self.logger.info(f"Created {skill_type} agent for skill '{skill_name}'")
            return agent

        except Exception as e:
            self.logger.error(f"Failed to create skill agent {skill_type}/{skill_name}: {e}")
            return None

    async def _execute_skill_request(
        self, skill_type: str, skill_name: str, user_message: str
    ) -> Dict[str, Any]:
        """
        Execute a request using the specified skill

        Args:
            skill_type: Type of skill (api, database, kb)
            skill_name: Name of the specific skill
            user_message: Original user message

        Returns:
            Dict with execution result and metadata
        """
        try:
            # Get or create the specialized agent
            skill_agent = await self._get_or_create_skill_agent(skill_type, skill_name)
            if not skill_agent:
                return {
                    "success": False,
                    "error": f"Could not create {skill_type} agent for skill '{skill_name}'",
                }

            # Execute based on skill type
            if skill_type == "api":
                return await self._execute_api_skill(skill_agent, skill_name, user_message)
            elif skill_type == "database":
                return await self._execute_database_skill(skill_agent, skill_name, user_message)
            elif skill_type == "kb":
                return await self._execute_kb_skill(skill_agent, skill_name, user_message)
            else:
                return {"success": False, "error": f"Unknown skill type: {skill_type}"}

        except Exception as e:
            return {"success": False, "error": f"Skill execution failed: {str(e)}"}

    async def _execute_api_skill(
        self, api_agent: Any, skill_name: str, user_message: str
    ) -> Dict[str, Any]:
        """Execute API skill request"""
        try:
            # Get skill configuration
            skill_config = self._assigned_skills["api_skills"][skill_name]

            # Use the APIAgent's natural language processing
            # Add context about the available API spec
            enhanced_message = f"""Using the assigned API specification for '{skill_name}':
            
{user_message}

Available endpoints include:
{chr(10).join([f"- {ep['method']} {ep['path']}: {ep.get('summary', 'No description')}" for ep in skill_config['endpoints'][:5]])}

Base URL: {skill_config['base_url']}
"""

            response = await api_agent.chat(enhanced_message)

            return {
                "success": True,
                "response": response,
                "skill_type": "api",
                "skill_name": skill_name,
                "agent_type": "APIAgent",
            }

        except Exception as e:
            return {"success": False, "error": f"API skill execution failed: {str(e)}"}

    async def _execute_database_skill(
        self, db_agent: Any, skill_name: str, user_message: str
    ) -> Dict[str, Any]:
        """Execute database skill request"""
        try:
            # Connect to database if not already connected
            skill_config = self._assigned_skills["database_skills"][skill_name]

            # Add connection context to the message
            enhanced_message = f"""Connect to the assigned {skill_config['type']} database and then: {user_message}
            
Connection: {skill_config['connection_string']}
"""

            response = await db_agent.chat(enhanced_message)

            return {
                "success": True,
                "response": response,
                "skill_type": "database",
                "skill_name": skill_name,
                "agent_type": "DatabaseAgent",
            }

        except Exception as e:
            return {"success": False, "error": f"Database skill execution failed: {str(e)}"}

    async def _execute_kb_skill(
        self, kb_agent: Any, skill_name: str, user_message: str
    ) -> Dict[str, Any]:
        """Execute knowledge base skill request"""
        try:
            skill_config = self._assigned_skills["kb_skills"][skill_name]

            # Add context about the knowledge base
            enhanced_message = f"""Search in the assigned knowledge base '{skill_name}' for: {user_message}
            
Knowledge base collection: {skill_config['collection_name']}
Documents source: {skill_config['documents_path']}
"""

            response = await kb_agent.chat(enhanced_message)

            return {
                "success": True,
                "response": response,
                "skill_type": "kb",
                "skill_name": skill_name,
                "agent_type": "KnowledgeBaseAgent",
            }

        except Exception as e:
            return {"success": False, "error": f"KB skill execution failed: {str(e)}"}

    async def _should_use_assigned_skills(self, message: str) -> Dict[str, Any]:
        """
        Main method to determine if and how to use assigned skills

        Args:
            message: User message

        Returns:
            Dict with routing decision and execution result if applicable
        """
        # Classify intent
        intent = await self._classify_intent_for_skills(message)

        if not intent["should_use_skills"]:
            return {
                "should_use_skills": False,
                "intent": intent,
                "reason": intent.get("reason", "No matching skills found"),
            }

        # Execute the identified skill
        execution_result = await self._execute_skill_request(
            intent["skill_type"], intent["skill_name"], message
        )

        return {
            "should_use_skills": True,
            "intent": intent,
            "execution_result": execution_result,
            "used_skill": f"{intent['skill_type']}/{intent['skill_name']}",
        }

    # 🌟 RESPONSE TRANSLATION TO NATURAL LANGUAGE

    async def _translate_technical_response(
        self, execution_result: Dict[str, Any], original_message: str
    ) -> str:
        """
        Translate technical agent responses to natural language

        Args:
            execution_result: Result from skill execution
            original_message: Original user message for context

        Returns:
            Natural language response string
        """
        if not execution_result.get("success"):
            return f"I encountered an error while processing your request: {execution_result.get('error', 'Unknown error')}"

        raw_response = execution_result.get("response", "")
        skill_type = execution_result.get("skill_type")
        skill_name = execution_result.get("skill_name")
        agent_type = execution_result.get("agent_type")

        # If LLM service is available, use it for intelligent translation
        if self.llm_service:
            return await self._llm_translate_response(
                raw_response, skill_type, skill_name, original_message
            )

        # Fallback to simple template-based translation
        return self._template_translate_response(raw_response, skill_type, skill_name, agent_type)

    async def _llm_translate_response(
        self, raw_response: str, skill_type: str, skill_name: str, original_message: str
    ) -> str:
        """Use LLM to translate technical response to natural language"""
        try:
            prompt = f"""You are a helpful assistant that translates technical responses into natural, conversational language.

Original user request: "{original_message}"

Technical response from {skill_type} skill '{skill_name}':
{raw_response}

Please provide a natural, helpful response that:
1. Answers the user's original question
2. Explains what was done using the {skill_type} skill
3. Summarizes key information in an easy-to-understand way
4. Maintains a conversational tone

Response:"""

            translated = await self.llm_service.generate_response(
                prompt,
                context={"conversation_history": []},
                system_message="You are a helpful assistant that makes technical information accessible to users.",
            )

            if translated:
                return str(translated)
            else:
                return self._template_translate_response(raw_response, skill_type, skill_name, None)

        except Exception as e:
            self.logger.warning(f"LLM translation failed: {e}")
            return self._template_translate_response(raw_response, skill_type, skill_name, None)

    def _template_translate_response(
        self, raw_response: str, skill_type: str, skill_name: str, agent_type: str = None
    ) -> str:
        """Fallback template-based response translation"""

        # Truncate very long responses for readability
        if len(raw_response) > 1000:
            summary = raw_response[:500] + "..."
        else:
            summary = raw_response

        skill_descriptions = {
            "api": f"API service '{skill_name}'",
            "database": f"database '{skill_name}'",
            "kb": f"knowledge base '{skill_name}'",
        }

        skill_desc = skill_descriptions.get(skill_type, f"{skill_type} skill '{skill_name}'")

        return f"""✅ I've completed your request using the {skill_desc}.

**Response:**
{summary}

*This response was generated using the {agent_type or 'specialized agent'} with the assigned {skill_type} skill.*"""

    async def cleanup_skill_agents(self) -> bool:
        """
        Cleanup all instantiated skill agents

        Returns:
            True if cleanup successful, False otherwise
        """
        try:
            cleanup_count = 0
            for cache_key, agent in list(self._skill_agents.items()):
                try:
                    if hasattr(agent, "cleanup_session"):
                        await agent.cleanup_session()
                    cleanup_count += 1
                except Exception as e:
                    self.logger.warning(f"Failed to cleanup skill agent {cache_key}: {e}")

            self._skill_agents.clear()

            if cleanup_count > 0:
                self.logger.info(f"Cleaned up {cleanup_count} skill agents")

            return True

        except Exception as e:
            self.logger.error(f"Failed to cleanup skill agents: {e}")
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

    def __init__(
        self,
        agent_class,
        user_id: str = None,
        tenant_id: str = "default",
        session_metadata: Dict[str, Any] = None,
        **agent_kwargs,
    ):
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
            **self.agent_kwargs,
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
    🌟 FIXED: One-liner synchronous agent chat that properly handles event loops

    Usage:
        response = quick_chat_sync(YouTubeDownloadAgent, "Download https://youtube.com/watch?v=abc")
        print(response)
    """
    try:
        # Check if we're in an async context
        try:
            loop = asyncio.get_running_loop()
            # We're in an async context - use thread executor
            import concurrent.futures

            def run_quick_chat():
                new_loop = asyncio.new_event_loop()
                asyncio.set_event_loop(new_loop)
                try:
                    # Filter out timeout parameter for async quick_chat call
                    filtered_kwargs = {k: v for k, v in kwargs.items() if k != "timeout"}
                    return new_loop.run_until_complete(
                        quick_chat(agent_class, message, user_id, **filtered_kwargs)
                    )
                finally:
                    new_loop.close()

            with concurrent.futures.ThreadPoolExecutor() as executor:
                future = executor.submit(run_quick_chat)
                return future.result()

        except RuntimeError:
            # No event loop, safe to use asyncio.run
            # Filter out timeout parameter that asyncio.run() doesn't accept
            filtered_kwargs = {k: v for k, v in kwargs.items() if k != "timeout"}
            return asyncio.run(quick_chat(agent_class, message, user_id, **filtered_kwargs))

    except Exception as e:
        return f"Quick sync chat error: {str(e)}"
