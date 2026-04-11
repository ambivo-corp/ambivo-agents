# ambivo_agents/__init__.py
"""
Ambivo Agents Framework
A lightweight agent framework for AI-powered research synthesis.
"""

__version__ = "2.0.9"

# Agent imports
from .agents.assistant import AssistantAgent
from .agents.gather_agent import GatherAgent
from .agents.knowledge_base import KnowledgeBaseAgent
from .agents.knowledge_synthesis import KnowledgeSynthesisAgent
from .agents.moderator import ModeratorAgent
from .agents.web_scraper import WebScraperAgent
from .agents.web_search import WebSearchAgent

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
from .core.memory import (
    InMemoryMemoryManager,
    MemoryManagerInterface,
    RedisMemoryManager,
    create_memory_manager,
    create_redis_memory_manager,
)
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
    "InMemoryMemoryManager",
    "create_memory_manager",
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
    "KnowledgeBaseAgent",
    "WebSearchAgent",
    "WebScraperAgent",
    "ModeratorAgent",
    "GatherAgent",
    "KnowledgeSynthesisAgent",
    # Configuration
    "load_config",
    "ConfigurationError",
]
