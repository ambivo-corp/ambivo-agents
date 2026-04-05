# ambivo_agents/agents/__init__.py
import logging

_logger = logging.getLogger(__name__)

from .assistant import AssistantAgent
from .code_executor import CodeExecutorAgent
from .knowledge_base import KnowledgeBaseAgent
from .media_editor import MediaEditorAgent
from .moderator import ModeratorAgent
from .web_search import WebSearchAgent
from .youtube_download import YouTubeDownloadAgent
from .workflow_developer import WorkflowDeveloperAgent
from .gather_agent import GatherAgent
from .knowledge_synthesis import KnowledgeSynthesisAgent

# Optional agents - depend on extras that may not be installed
try:
    from .analytics import AnalyticsAgent
except ImportError:
    AnalyticsAgent = None
    _logger.debug("AnalyticsAgent not available - install ambivo-agents[analytics]")

try:
    from .api_agent import APIAgent
except ImportError:
    APIAgent = None
    _logger.debug("APIAgent not available - install ambivo-agents[web]")

try:
    from .database_agent import DatabaseAgent
except ImportError:
    DatabaseAgent = None
    _logger.debug("DatabaseAgent not available - install ambivo-agents[database]")

try:
    from .web_scraper import WebScraperAgent
except ImportError:
    WebScraperAgent = None
    _logger.debug("WebScraperAgent not available - install ambivo-agents[web]")

__all__ = [
    "AssistantAgent",
    "CodeExecutorAgent",
    "KnowledgeBaseAgent",
    "WebSearchAgent",
    "MediaEditorAgent",
    "YouTubeDownloadAgent",
    "ModeratorAgent",
    "WorkflowDeveloperAgent",
    "GatherAgent",
    "KnowledgeSynthesisAgent",
]

# Conditionally export optional agents
if AnalyticsAgent is not None:
    __all__.append("AnalyticsAgent")
if APIAgent is not None:
    __all__.append("APIAgent")
if DatabaseAgent is not None:
    __all__.append("DatabaseAgent")
if WebScraperAgent is not None:
    __all__.append("WebScraperAgent")
