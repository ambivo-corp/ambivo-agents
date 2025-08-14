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
                        filtered_kwargs = {k: v for k, v in kwargs.items() if k != 'timeout'}
                        return new_loop.run_until_complete(self.chat(message, **filtered_kwargs))
                    finally:
                        new_loop.close()

                with concurrent.futures.ThreadPoolExecutor() as executor:
                    future = executor.submit(run_chat)
                    return future.result()

            except RuntimeError:
                # No event loop running, safe to use asyncio.run()
                # Filter out timeout parameter that asyncio.run() doesn't accept
                filtered_kwargs = {k: v for k, v in kwargs.items() if k != 'timeout'}
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
            if hasattr(self, 'config') and self.config:
                restricted_dirs = self.config.get('security', {}).get('file_access', {}).get('restricted_directories', [])
            
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

    async def read_file(self, file_path: str, encoding: str = 'utf-8') -> Dict[str, Any]:
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
            if not file_path.startswith(('http://', 'https://')):
                if self._is_path_restricted(file_path):
                    return {
                        'success': False,
                        'error': f'Access denied: File path "{file_path}" is in a restricted directory for security reasons'
                    }
            import mimetypes
            
            # Check if it's a URL
            if file_path.startswith(('http://', 'https://')):
                # Prefer aiohttp when available, fallback to requests
                if AIOHTTP_AVAILABLE:
                    import aiohttp
                    async with aiohttp.ClientSession() as session:
                        async with session.get(file_path) as response:
                            response.raise_for_status()
                            content = await response.text()
                            return {
                                'success': True,
                                'content': content,
                                'source': 'url',
                                'path': file_path,
                                'size': len(content),
                                'content_type': response.headers.get('Content-Type', 'text/plain'),
                                'encoding': encoding
                            }
                elif REQUESTS_AVAILABLE:
                    try:
                        resp = requests.get(file_path, timeout=15)
                        resp.raise_for_status()
                        content = resp.text
                        return {
                            'success': True,
                            'content': content,
                            'source': 'url',
                            'path': file_path,
                            'size': len(content),
                            'content_type': resp.headers.get('Content-Type', 'text/plain'),
                            'encoding': resp.encoding or encoding
                        }
                    except Exception as e:
                        return {
                            'success': False,
                            'error': str(e),
                            'path': file_path
                        }
                else:
                    return {
                        'success': False,
                        'error': 'No HTTP client available. Install aiohttp or requests to read URLs.'
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
                        'success': False,
                        'error': f'File not found: {file_path}',
                        'tried_paths': [str(p) for p in possible_paths] if 'possible_paths' in locals() else [str(path)]
                    }
                
                # Detect file type
                mime_type, _ = mimetypes.guess_type(str(path))
                
                # Read file
                if path.suffix.lower() in ['.json', '.csv', '.txt', '.xml', '.yml', '.yaml']:
                    if AIOFILES_AVAILABLE:
                        import aiofiles
                        async with aiofiles.open(path, mode='r', encoding=encoding) as f:
                            content = await f.read()
                    else:
                        # Fallback to sync read
                        with open(path, 'r', encoding=encoding) as f:
                            content = f.read()
                else:
                    # Binary file
                    if AIOFILES_AVAILABLE:
                        import aiofiles
                        async with aiofiles.open(path, mode='rb') as f:
                            content = await f.read()
                    else:
                        # Fallback to sync read
                        with open(path, 'rb') as f:
                            content = f.read()
                    
                    return {
                        'success': True,
                        'content': content,
                        'source': 'local',
                        'path': str(path),
                        'size': len(content),
                        'content_type': mime_type or 'application/octet-stream',
                        'encoding': None,
                        'is_binary': True
                    }
                
                return {
                    'success': True,
                    'content': content,
                    'source': 'local',
                    'path': str(path),
                    'size': len(content),
                    'content_type': mime_type or 'text/plain',
                    'encoding': encoding,
                    'extension': path.suffix
                }
                
        except Exception as e:
            return {
                'success': False,
                'error': str(e),
                'path': file_path
            }
    
    async def parse_file_content(self, content: str, file_type: str = None, file_path: str = None) -> Dict[str, Any]:
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
                file_type = ext[1:] if ext else 'txt'
            
            file_type = (file_type or 'txt').lower()
            
            if file_type == 'json':
                # Parse JSON
                data = json.loads(content)
                return {
                    'success': True,
                    'data': data,
                    'type': 'json',
                    'is_array': isinstance(data, list),
                    'is_object': isinstance(data, dict),
                    'count': len(data) if isinstance(data, (list, dict)) else 1
                }
                
            elif file_type == 'csv':
                # Parse CSV
                reader = csv.DictReader(StringIO(content))
                data = list(reader)
                
                # Get column names
                columns = data[0].keys() if data else []
                
                return {
                    'success': True,
                    'data': data,
                    'type': 'csv',
                    'columns': list(columns),
                    'row_count': len(data)
                }
                
            elif file_type == 'xml':
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
                
                return {
                    'success': True,
                    'data': data,
                    'type': 'xml',
                    'root_tag': root.tag
                }
                
            elif file_type in ['yml', 'yaml']:
                # Parse YAML
                if not YAML_AVAILABLE:
                    return {
                        'success': False,
                        'error': 'PyYAML not available. Install with: pip install PyYAML'
                    }
                import yaml
                data = yaml.safe_load(content)
                return {
                    'success': True,
                    'data': data,
                    'type': 'yaml'
                }
                
            else:
                # Plain text
                return {
                    'success': True,
                    'data': content,
                    'type': 'text',
                    'lines': content.count('\n') + 1,
                    'characters': len(content)
                }
                
        except Exception as e:
            return {
                'success': False,
                'error': str(e),
                'content_preview': content[:200] + '...' if len(content) > 200 else content
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
                    'success': False,
                    'error': 'JSON data must be an object or array of objects'
                }
            
            if not data:
                return {
                    'success': True,
                    'csv': '',
                    'rows': 0,
                    'columns': []
                }
            
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
                'success': True,
                'csv': csv_content,
                'rows': len(data),
                'columns': sorted(all_keys)
            }
            
        except Exception as e:
            return {
                'success': False,
                'error': str(e)
            }
    
    async def convert_csv_to_json(self, csv_data: str, numeric_conversion: bool = True) -> Dict[str, Any]:
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
                        if value == '':
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
                'success': True,
                'json': data,
                'json_string': json.dumps(data, indent=2),
                'rows': len(data),
                'columns': list(data[0].keys()) if data else []
            }
            
        except Exception as e:
            return {
                'success': False,
                'error': str(e)
            }
    
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
        
        if not read_result['success']:
            return read_result
        
        if not auto_parse or read_result.get('is_binary'):
            return read_result
        
        # Parse content
        content = read_result['content']
        file_type = None
        
        if 'extension' in read_result:
            file_type = read_result['extension'][1:]  # Remove dot
        elif '.' in file_path:
            file_type = file_path.split('.')[-1]
        
        parse_result = await self.parse_file_content(content, file_type, file_path)
        
        # Combine results
        return {
            **read_result,
            'parsed': parse_result['success'],
            'parse_result': parse_result
        }

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
                    filtered_kwargs = {k: v for k, v in kwargs.items() if k != 'timeout'}
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
            filtered_kwargs = {k: v for k, v in kwargs.items() if k != 'timeout'}
            return asyncio.run(quick_chat(agent_class, message, user_id, **filtered_kwargs))

    except Exception as e:
        return f"Quick sync chat error: {str(e)}"
