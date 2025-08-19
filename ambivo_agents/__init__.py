# ambivo_agents/__init__.py
"""
Ambivo Agents Framework
A minimalistic agent framework for building AI applications.
"""

__version__ = "1.3.7"

# Agent imports
from .agents.analytics import AnalyticsAgent
from .agents.api_agent import APIAgent
from .agents.assistant import AssistantAgent
from .agents.code_executor import CodeExecutorAgent

# Database agent - optional import
try:
    from .agents.database_agent import DatabaseAgent

    _DATABASE_AGENT_AVAILABLE = True
except ImportError:
    _DATABASE_AGENT_AVAILABLE = False
    DatabaseAgent = None

from .agents.knowledge_base import KnowledgeBaseAgent
from .agents.media_editor import MediaEditorAgent
from .agents.moderator import ModeratorAgent
from .agents.web_scraper import WebScraperAgent
from .agents.web_search import WebSearchAgent
from .agents.youtube_download import YouTubeDownloadAgent

# Configuration
from .config.loader import ConfigurationError, load_config

# Core imports
from .core.base import (
    AgentMessage,
    AgentRole,
    AgentSession,
    AgentTool,
    BaseAgent,
    ExecutionContext,
    MessageType,
    ProviderConfig,
    ProviderTracker,
)
from .core.llm import (
    LLMServiceInterface,
    MultiProviderLLMService,
    create_multi_provider_llm_service,
)
from .core.memory import MemoryManagerInterface, RedisMemoryManager, create_redis_memory_manager
from .services.agent_service import AgentService, create_agent_service

# Service imports
from .services.factory import AgentFactory

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
    "AnalyticsAgent",
    "APIAgent",
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
    "ConfigurationError",
]

# Add DatabaseAgent to __all__ if available
if _DATABASE_AGENT_AVAILABLE:
    __all__.append("DatabaseAgent")
