# ambivo_agents/__init__.py
"""
Ambivo Agents Framework
A minimalistic agent framework for building AI applications.
"""

__version__ = "1.0.0"

# Core imports
from .core.base import (
    AgentRole,
    MessageType,
    AgentMessage,
    AgentTool,
    ExecutionContext,
    BaseAgent,
    ProviderConfig,
    ProviderTracker,
    AgentSession
)

from .core.memory import (
    MemoryManagerInterface,
    RedisMemoryManager,
    create_redis_memory_manager
)

from .core.llm import (
    LLMServiceInterface,
    MultiProviderLLMService,
    create_multi_provider_llm_service
)

# Service imports
from .services.factory import AgentFactory
from .services.agent_service import AgentService, create_agent_service

# Agent imports
from .agents.assistant import AssistantAgent
from .agents.code_executor import CodeExecutorAgent
from .agents.knowledge_base import KnowledgeBaseAgent
from .agents.web_search import WebSearchAgent
from .agents.web_scraper import WebScraperAgent
from .agents.media_editor import MediaEditorAgent
from .agents.youtube_download import YouTubeDownloadAgent
from .agents.moderator import ModeratorAgent

# Configuration
from .config.loader import load_config, ConfigurationError

__all__ = [
    # Core
    "AgentRole",
    "MessageType",
    "AgentMessage",
    "AgentTool",
    "ExecutionContext",
    "BaseAgent",
    "ProviderConfig",
    "ProviderTracker",
    "AgentSession",

    # Memory
    "MemoryManagerInterface",
    "RedisMemoryManager",
    "create_redis_memory_manager",

    # LLM
    "LLMServiceInterface",
    "MultiProviderLLMService",
    "create_multi_provider_llm_service",

    # Services
    "AgentFactory",
    "AgentService",
    "create_agent_service",

    # Agents
    "AssistantAgent",
    "CodeExecutorAgent",
    "KnowledgeBaseAgent",
    "WebSearchAgent",
    "WebScraperAgent",
    "MediaEditorAgent",
    "YouTubeDownloadAgent",
    "ModeratorAgent",

    # Configuration
    "load_config",
    "ConfigurationError"
]