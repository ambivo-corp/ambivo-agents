# ambivo_agents/agents/moderator.py
"""
Complete ModeratorAgent with System Message, LLM Context, and Memory Preservation
Intelligent orchestrator that routes queries to specialized agents with full context preservation
"""

import asyncio
import json
import logging
import os
import re
import time
import uuid
from dataclasses import dataclass
from datetime import datetime
from typing import Any, AsyncIterator, Dict, List, Optional, Union, Tuple

from ambivo_agents.core import WorkflowPatterns

from ..config.loader import get_config_section, load_config
from ..core.base import (
    AgentMessage,
    AgentRole,
    BaseAgent,
    ExecutionContext,
    MessageType,
    StreamChunk,
    StreamSubType,
)
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
    Complete moderator agent with intelligent routing, system message support,
    and full conversation context preservation across agent switches
    """

    # Fix for ambivo_agents/agents/moderator.py
    # Replace the __init__ method with this corrected version:

    def __init__(
        self,
        agent_id: str = None,
        memory_manager=None,
        llm_service=None,
        enabled_agents: List[str] = None,
        **kwargs,
    ):
        """
        🔧 FIXED: Constructor that properly handles system_message parameter
        """
        if agent_id is None:
            agent_id = f"moderator_{str(uuid.uuid4())[:8]}"

        # Extract system_message from kwargs to avoid conflict
        system_message = kwargs.pop("system_message", None)

        # Enhanced system message for ModeratorAgent with context awareness and Markdown formatting
        moderator_system = (
            system_message
            or """You are an intelligent request coordinator and conversation orchestrator with these responsibilities:

    CORE RESPONSIBILITIES:
    - Analyze user requests to understand intent, complexity, and requirements
    - Route requests to the most appropriate specialized agent based on their capabilities  
    - Consider conversation context and history when making routing decisions
    - Provide helpful responses when no specific agent is needed
    - Maintain conversation flow and context across agent interactions
    - Use conversation history to make better routing decisions
    - Explain your routing choices when helpful to the user
    - Preserve conversation continuity across agent switches

    AVAILABLE AGENT TYPES AND SPECIALIZATIONS:
    - assistant: General conversation, questions, explanations, help, follow-up discussions
    - code_executor: Writing and executing Python/bash code, programming tasks, debugging
    - web_search: Finding information online, research queries, current events, fact-checking
    - knowledge_base: Document storage, retrieval, semantic search, document ingestion
    - media_editor: Video/audio processing and conversion using FFmpeg tools
    - youtube_download: Downloading content from YouTube (video/audio formats)
    - web_scraper: Extracting data from websites and web crawling operations
    - api_agent: Making HTTP/REST API calls with authentication, retries, and security features
    - analytics: Data analysis with DuckDB, CSV/Excel ingestion, SQL queries, chart generation
    - database_agent: Database operations with MongoDB, MySQL, PostgreSQL connections and safe query execution

    ROUTING PRINCIPLES:
    - Choose the most appropriate agent based on user's specific needs and conversation context
    - Consider previous conversation when routing follow-up requests
    - Route to assistant for general questions or when no specialized agent is needed
    - Use conversation history to understand context references like "that", "this", "continue"
    - Maintain context when switching between agents
    - Provide helpful explanations when routing decisions might not be obvious

    CONTEXT AWARENESS:
    - Remember previous interactions and reference them when relevant
    - Understand when users are referring to previous responses or asking follow-up questions
    - Maintain conversation flow even when switching between different specialized agents
    - Use conversation history to provide better routing decisions

    FORMATTING REQUIREMENTS:
    - ALWAYS format your responses using proper Markdown syntax
    - Use **bold** for important information, headings, and emphasis
    - Use `code blocks` for technical terms, file names, and commands
    - Use numbered lists (1. 2. 3.) and bullet points (- •) for organized information
    - Use > blockquotes for highlighting key information or quotes
    - Use headers (## ###) to structure long responses
    - When delegating to other agents, explicitly instruct them to use Markdown formatting
    - Ensure all agent responses maintain consistent professional Markdown formatting

    AGENT DELEGATION INSTRUCTIONS:
    When routing to specialized agents, always include this instruction: "Please format your response using proper Markdown syntax with appropriate headers, bold text, code blocks, and lists for maximum readability."

    OUTPUT STYLE:
    - Professional, well-structured Markdown formatting
    - Clear visual hierarchy using headers and emphasis
    - Organized information with lists and code blocks
    - Consistent formatting across all interactions"""
        )

        super().__init__(
            agent_id=agent_id,
            role=AgentRole.COORDINATOR,
            memory_manager=memory_manager,
            llm_service=llm_service,
            name="Moderator Agent",
            description="Intelligent orchestrator that routes queries to specialized agents",
            system_message=moderator_system,
            **kwargs,  # Pass remaining kwargs to parent
        )

        # Rest of the initialization code remains the same...
        self.setup_history_mixin()

        # Load configuration
        self.config = load_config()
        self.capabilities = self.config.get("agent_capabilities", {})
        self.moderator_config = self.config.get("moderator", {})

        # Initialize available agents based on config and enabled list
        self.enabled_agents = enabled_agents or self._get_default_enabled_agents()
        self.specialized_agents = {}
        self.agent_routing_patterns = {}

        # Setup logging
        self.logger = logging.getLogger(f"ModeratorAgent-{agent_id[:8]}")

        # Setup routing intelligence
        self._setup_routing_patterns()
        self._initialize_specialized_agents()

        self.logger.info(
            f"ModeratorAgent initialized with agents: {list(self.specialized_agents.keys())}"
        )

    def _get_default_enabled_agents(self) -> List[str]:
        """Get default enabled agents from configuration - Always includes assistant"""
        # Check moderator config first
        if "default_enabled_agents" in self.moderator_config:
            enabled = self.moderator_config["default_enabled_agents"].copy()
        else:
            # Build from capabilities config
            enabled = []

            if self.capabilities.get("enable_knowledge_base", False):
                enabled.append("knowledge_base")
            if self.capabilities.get("enable_web_search", False):
                enabled.append("web_search")
            if self.capabilities.get("enable_code_execution", False):
                enabled.append("code_executor")
            if self.capabilities.get("enable_media_editor", False):
                enabled.append("media_editor")
            if self.capabilities.get("enable_youtube_download", False):
                enabled.append("youtube_download")
            if self.capabilities.get("enable_web_scraping", False):
                enabled.append("web_scraper")
            if self.capabilities.get("enable_analytics", False):
                enabled.append("analytics")
            if self.capabilities.get("enable_database_agent", False):
                enabled.append("database_agent")

        # CRITICAL: Always ensure assistant is included
        if "assistant" not in enabled:
            enabled.append("assistant")
            self.logger.info("✅ Assistant agent added to enabled agents list")

        self.logger.info(f"Enabled agents: {enabled}")
        return enabled

    def _is_agent_enabled(self, agent_type: str) -> bool:
        """Check if an agent type is enabled"""
        if agent_type in self.enabled_agents:
            return True

        # Double-check against capabilities config
        capability_map = {
            "knowledge_base": "enable_knowledge_base",
            "web_search": "enable_web_search",
            "code_executor": "enable_code_execution",
            "media_editor": "enable_media_editor",
            "youtube_download": "enable_youtube_download",
            "web_scraper": "enable_web_scraping",
            "analytics": "enable_analytics",
            "database_agent": "enable_database_agent",
            "assistant": True,  # Always enabled
        }

        if agent_type == "assistant":
            return True

        capability_key = capability_map.get(agent_type)
        if capability_key and isinstance(capability_key, str):
            return self.capabilities.get(capability_key, False)

        return False

    def _initialize_specialized_agents(self):
        """Initialize specialized agents with SHARED memory and context - COMPLETE VERSION"""

        # Try importing all agents
        try:
            from . import (
                AnalyticsAgent,
                APIAgent,
                AssistantAgent,
                CodeExecutorAgent,
                KnowledgeBaseAgent,
                MediaEditorAgent,
                WebScraperAgent,
                WebSearchAgent,
                YouTubeDownloadAgent,
            )

            # Import DatabaseAgent separately due to optional dependencies
            try:
                from .database_agent import DatabaseAgent
            except ImportError:
                DatabaseAgent = None

            self.logger.info("Successfully imported all agent classes")
        except ImportError as e:
            self.logger.warning(f"Bulk import failed: {e}, trying individual imports")

            # Individual imports with fallbacks
            agent_imports = {}

            # Try importing each agent individually
            for agent_type, module_path in [
                ("assistant", ".assistant"),
                ("knowledge_base", ".knowledge_base"),
                ("web_search", ".web_search"),
                ("code_executor", ".code_executor"),
                ("media_editor", ".media_editor"),
                ("youtube_download", ".youtube_download"),
                ("web_scraper", ".web_scraper"),
                ("api_agent", ".api_agent"),
                ("analytics", ".analytics"),
                ("database_agent", ".database_agent"),
            ]:
                try:
                    if agent_type == "assistant":
                        from .assistant import AssistantAgent

                        agent_imports["assistant"] = AssistantAgent
                    elif agent_type == "knowledge_base":
                        from .knowledge_base import KnowledgeBaseAgent

                        agent_imports["knowledge_base"] = KnowledgeBaseAgent
                    elif agent_type == "web_search":
                        from .web_search import WebSearchAgent

                        agent_imports["web_search"] = WebSearchAgent
                    elif agent_type == "code_executor":
                        from .code_executor import CodeExecutorAgent

                        agent_imports["code_executor"] = CodeExecutorAgent
                    elif agent_type == "media_editor":
                        from .media_editor import MediaEditorAgent

                        agent_imports["media_editor"] = MediaEditorAgent
                    elif agent_type == "youtube_download":
                        from .youtube_download import YouTubeDownloadAgent

                        agent_imports["youtube_download"] = YouTubeDownloadAgent
                    elif agent_type == "web_scraper":
                        from .web_scraper import WebScraperAgent

                        agent_imports["web_scraper"] = WebScraperAgent
                    elif agent_type == "api_agent":
                        from .api_agent import APIAgent

                        agent_imports["api_agent"] = APIAgent
                    elif agent_type == "analytics":
                        from .analytics import AnalyticsAgent

                        agent_imports["analytics"] = AnalyticsAgent
                    elif agent_type == "database_agent":
                        from .database_agent import DatabaseAgent

                        agent_imports["database_agent"] = DatabaseAgent

                    self.logger.info(f"✅ Imported {agent_type}")
                except ImportError as import_error:
                    self.logger.warning(f"❌ Failed to import {agent_type}: {import_error}")
                    agent_imports[agent_type] = None

            # Use the imported classes
            AssistantAgent = agent_imports.get("assistant")
            KnowledgeBaseAgent = agent_imports.get("knowledge_base")
            WebSearchAgent = agent_imports.get("web_search")
            CodeExecutorAgent = agent_imports.get("code_executor")
            MediaEditorAgent = agent_imports.get("media_editor")
            YouTubeDownloadAgent = agent_imports.get("youtube_download")
            WebScraperAgent = agent_imports.get("web_scraper")
            APIAgent = agent_imports.get("api_agent")
            AnalyticsAgent = agent_imports.get("analytics")
            DatabaseAgent = agent_imports.get("database_agent")

        # CRITICAL: Ensure AssistantAgent is available
        if not AssistantAgent:
            self.logger.error("❌ CRITICAL: AssistantAgent not available")
            AssistantAgent = self._create_fallback_assistant_agent()
            self.logger.warning("🔧 Created fallback AssistantAgent")

        agent_classes = {
            "knowledge_base": KnowledgeBaseAgent,
            "web_search": WebSearchAgent,
            "code_executor": CodeExecutorAgent,
            "media_editor": MediaEditorAgent,
            "youtube_download": YouTubeDownloadAgent,
            "web_scraper": WebScraperAgent,
            "api_agent": APIAgent,
            "analytics": AnalyticsAgent,
            "database_agent": DatabaseAgent,
            "assistant": AssistantAgent,  # This should never be None now
        }

        # Initialize agents with SHARED context and memory
        for agent_type in self.enabled_agents:
            if not self._is_agent_enabled(agent_type):
                self.logger.info(f"Skipping disabled agent: {agent_type}")
                continue

            agent_class = agent_classes.get(agent_type)
            if agent_class is None:
                self.logger.warning(f"Agent class for {agent_type} not available")
                continue

            try:
                self.logger.info(f"Creating {agent_type} agent with shared context...")

                # 🔥 CRITICAL: Create agent with MODERATOR's session context
                if hasattr(agent_class, "create_simple"):
                    # Use create_simple but with moderator's context
                    agent_instance = agent_class.create_simple(
                        agent_id=f"{agent_type}_{self.agent_id}",
                        user_id=self.context.user_id,
                        tenant_id=self.context.tenant_id,
                        session_metadata={
                            "parent_moderator": self.agent_id,
                            "agent_type": agent_type,
                            "shared_context": True,
                            "moderator_session_id": self.context.session_id,
                            "moderator_conversation_id": self.context.conversation_id,
                        },
                    )

                    # 🔥 CRITICAL: Override agent's context to match moderator
                    agent_instance.context.session_id = self.context.session_id
                    agent_instance.context.conversation_id = self.context.conversation_id
                    agent_instance.context.user_id = self.context.user_id
                    agent_instance.context.tenant_id = self.context.tenant_id

                    # 🔥 CRITICAL: Replace agent's memory with moderator's memory for consistency
                    agent_instance.memory = self.memory
                    agent_instance.llm_service = self.llm_service

                else:
                    # Fallback to direct instantiation
                    agent_instance = agent_class(
                        agent_id=f"{agent_type}_{self.agent_id}",
                        memory_manager=self.memory,  # 🔥 SHARED MEMORY
                        llm_service=self.llm_service,  # 🔥 SHARED LLM
                        user_id=self.context.user_id,
                        tenant_id=self.context.tenant_id,
                        session_id=self.context.session_id,  # 🔥 SAME SESSION
                        conversation_id=self.context.conversation_id,  # 🔥 SAME CONVERSATION
                        session_metadata={
                            "parent_moderator": self.agent_id,
                            "agent_type": agent_type,
                            "shared_context": True,
                        },
                    )

                self.specialized_agents[agent_type] = agent_instance
                self.logger.info(
                    f"✅ Initialized {agent_type} with shared context (session: {self.context.session_id})"
                )

            except Exception as e:
                self.logger.error(f"❌ Failed to initialize {agent_type} agent: {e}")

                # Special handling for assistant agent failure
                if agent_type == "assistant":
                    self.logger.error(
                        "❌ CRITICAL: Assistant agent initialization failed, creating minimal fallback"
                    )
                    try:
                        fallback_assistant = self._create_minimal_assistant_agent()
                        self.specialized_agents[agent_type] = fallback_assistant
                        self.logger.warning("🔧 Emergency fallback assistant created")
                    except Exception as fallback_error:
                        self.logger.error(f"❌ Even fallback assistant failed: {fallback_error}")

    def _create_fallback_assistant_agent(self):
        """Create a fallback AssistantAgent class when import fails"""
        from typing import AsyncIterator

        from ..core.base import AgentMessage, AgentRole, BaseAgent, ExecutionContext, MessageType

        class FallbackAssistantAgent(BaseAgent):
            """Minimal fallback assistant agent"""

            def __init__(self, **kwargs):
                super().__init__(
                    role=AgentRole.ASSISTANT,
                    name="Fallback Assistant",
                    description="Emergency fallback assistant agent",
                    **kwargs,
                )

            async def process_message(
                self, message: AgentMessage, context: ExecutionContext = None
            ) -> AgentMessage:
                """Process message with basic response"""
                response_content = (
                    f"I'm a basic assistant. You said: '{message.content}'. How can I help you?"
                )

                return self.create_response(
                    content=response_content,
                    recipient_id=message.sender_id,
                    session_id=message.session_id,
                    conversation_id=message.conversation_id,
                )

            async def process_message_stream(
                self, message: AgentMessage, context: ExecutionContext = None
            ) -> AsyncIterator[StreamChunk]:
                """Stream processing fallback"""
                yield StreamChunk(
                    text=f"I'm a basic assistant. You said: '{message.content}'. How can I help you?",
                    sub_type=StreamSubType.CONTENT,
                    metadata={"fallback_agent": True},
                )

        return FallbackAssistantAgent

    def _create_minimal_assistant_agent(self):
        """Create a minimal assistant agent instance as emergency fallback"""
        FallbackAssistantClass = self._create_fallback_assistant_agent()

        return FallbackAssistantClass.create_simple(
            user_id=self.context.user_id,
            tenant_id=self.context.tenant_id,
            session_metadata={
                "parent_moderator": self.agent_id,
                "agent_type": "assistant",
                "fallback": True,
            },
        )

    def _setup_routing_patterns(self):
        """Setup intelligent routing patterns for different query types"""
        self.agent_routing_patterns = {
            "code_executor": {
                "keywords": [
                    "run code",
                    "execute python",
                    "run script",
                    "code execution",
                    "write code",
                    "create code",
                    "python code",
                    "bash script",
                    "write a script",
                    "code to",
                    "program to",
                    "function to",
                    "show code",
                    "that code",
                    "the code",
                    "previous code",
                    "code again",
                    "show me that",
                    "display code",
                    "see code",
                ],
                "patterns": [
                    r"(?:run|execute|write|create|show)\s+(?:code|script|python|program)",
                    r"code\s+to\s+\w+",
                    r"write.*(?:function|script|program)",
                    r"```(?:python|bash)",
                    r"can\s+you\s+(?:write|create).*code",
                    r"(?:show|display|see)\s+(?:me\s+)?(?:that\s+|the\s+)?code",
                    r"code\s+again",
                    r"(?:previous|last|that)\s+code",
                ],
                "indicators": [
                    "```",
                    "def ",
                    "import ",
                    "python",
                    "bash",
                    "function",
                    "script",
                    "code",
                ],
                "priority": 1,
            },
            "youtube_download": {
                "keywords": [
                    "download youtube",
                    "youtube video",
                    "download video",
                    "get from youtube",
                    "youtube.com",
                    "youtu.be",
                ],
                "patterns": [
                    r"download\s+(?:from\s+)?youtube",
                    r"youtube\.com/watch",
                    r"youtu\.be/",
                    r"get\s+(?:video|audio)\s+from\s+youtube",
                ],
                "indicators": ["youtube.com", "youtu.be", "download video", "download audio"],
                "priority": 1,
            },
            "media_editor": {
                "keywords": [
                    "convert video",
                    "edit media",
                    "extract audio",
                    "resize video",
                    "media processing",
                    "ffmpeg",
                    "video format",
                    "audio format",
                ],
                "patterns": [
                    r"convert\s+(?:video|audio)",
                    r"extract\s+audio",
                    r"resize\s+video",
                    r"trim\s+(?:video|audio)",
                    r"media\s+(?:processing|editing)",
                ],
                "indicators": [".mp4", ".avi", ".mp3", ".wav", "video", "audio"],
                "priority": 1,
            },
            "knowledge_base": {
                "keywords": [
                    "search knowledge",
                    "query kb",
                    "knowledge base",
                    "find in documents",
                    "search documents",
                    "ingest document",
                    "add to kb",
                    "semantic search",
                ],
                "patterns": [
                    r"(?:search|query|ingest|add)\s+(?:in\s+)?(?:kb|knowledge|documents?)",
                    r"find\s+(?:in\s+)?(?:my\s+)?(?:files|documents?)",
                    r"(?:ingest|import|load)\s+.*\.(?:csv|json|pdf|txt)\s+(?:into|to)\s+(?:knowledge\s*base|kb)",
                    r"(?:ingest|add)\s+.*\s+(?:into|to)\s+(?:the\s+)?knowledge\s*base",
                    r"(?:ingest|add)\s+.*\s+into\s+.*knowledge",
                ],
                "indicators": [
                    "kb_name",
                    "collection_table",
                    "document",
                    "file",
                    "ingest",
                    "query",
                ],
                "priority": 2,
            },
            "web_search": {
                "keywords": [
                    "search web",
                    "google",
                    "find online",
                    "search for",
                    "look up",
                    "search internet",
                    "web search",
                    "find information",
                    "search about",
                ],
                "patterns": [
                    r"search\s+(?:the\s+)?(?:web|internet|online)",
                    r"(?:google|look\s+up|find)\s+(?:information\s+)?(?:about|on)",
                    r"what\'s\s+happening\s+with",
                    r"latest\s+news",
                ],
                "indicators": ["search", "web", "online", "internet", "news"],
                "priority": 2,
            },
            "web_scraper": {
                "keywords": ["scrape website", "extract from site", "crawl web", "scrape data"],
                "patterns": [
                    r"scrape\s+(?:website|site|web)",
                    r"extract\s+(?:data\s+)?from\s+(?:website|site)",
                    r"crawl\s+(?:website|web)",
                ],
                "indicators": ["scrape", "crawl", "extract data", "website"],
                "priority": 2,
            },
            "api_agent": {
                "keywords": [
                    "api call",
                    "make request",
                    "http request",
                    "rest api",
                    "api endpoint",
                    "post request",
                    "get request",
                    "patch request",
                    "delete request",
                    "put request",
                    "call api",
                    "invoke api",
                    "api test",
                    "test endpoint",
                    "curl request",
                    "authenticate",
                    "bearer token",
                    "api key",
                    "oauth",
                    "webhook",
                    "send post",
                    "make get",
                    "api integration",
                    "http method",
                ],
                "patterns": [
                    r"(?:make|send|call)\s+(?:api|http|rest)\s+(?:call|request)",
                    r"(?:get|post|put|patch|delete)\s+(?:request\s+)?(?:to|from|https?://)",
                    r"api\s+(?:call|request|endpoint)",
                    r"test\s+(?:api|endpoint)",
                    r"http\s+(?:get|post|put|patch|delete)",
                    r"rest\s+api",
                    r"invoke\s+(?:api|endpoint)",
                    r"curl\s+request",
                    r"(?:get|post|put|patch|delete)\s+https?://",
                    r"authenticate.*(?:api|oauth|bearer)",
                    r"(?:bearer|api\s+key|oauth).*(?:token|auth)",
                    r"webhook.*(?:call|send|invoke)",
                ],
                "indicators": [
                    "api",
                    "http",
                    "rest",
                    "endpoint",
                    "curl",
                    "json",
                    "authorization",
                    "bearer",
                    "https://",
                    "http://",
                    "GET",
                    "POST",
                    "PUT",
                    "PATCH",
                    "DELETE",
                    "oauth",
                    "webhook",
                    "token",
                    "auth",
                ],
                "priority": 1,
            },
            "database_agent": {
                "keywords": [
                    "database",
                    "sql query",
                    "mongodb",
                    "mysql",
                    "postgresql",
                    "connect database",
                    "table schema",
                    "show tables",
                    "database connection",
                    "select from",
                    "count rows",
                    "describe table",
                    "database query",
                    "sql statement",
                    "query database",
                    "database operations",
                    "run sql",
                    "execute query",
                    "database info",
                    "table structure",
                    "database schema",
                    "db connection",
                    "data query",
                    "sql select",
                    # File ingestion keywords
                    "ingest file",
                    "ingest json",
                    "ingest csv",
                    "load file to mongodb",
                    "import file to database",
                    "insert file",
                    "load csv to mongodb",
                    "load json to mongodb",
                    "file to database",
                    "import data",
                    # Academic data queries that need database access first
                    "faculty data",
                    "faculty members",
                    "faculty distribution",
                    "researchers",
                    "publication data",
                    "publication venues",
                    "top researchers",
                    "research profiles",
                    "academic data",
                    "university data",
                    "professor data",
                    "citation data",
                    "h-index",
                    "research interest",
                ],
                "patterns": [
                    r"(?:connect|connection)\s+(?:to\s+)?(?:database|db|mongodb|mysql|postgresql)",
                    r"(?:sql|database)\s+(?:query|statement|select)",
                    r"(?:select|count|show|describe)\s+(?:from\s+|tables?|rows?|schema)",
                    r"(?:mongodb|mysql|postgresql|database)\s+(?:connection|query|operations)",
                    r"(?:run|execute)\s+(?:sql|query|database)",
                    r"(?:table|database)\s+(?:schema|structure|info)",
                    r"(?:show|list)\s+tables?",
                    r"describe\s+table",
                    r"count\s+rows?",
                    r"database\s+(?:info|operations|management)",
                    # File ingestion patterns - only for explicit database mentions
                    r"(?:ingest|import|load)\s+.*\.(?:json|csv)\s+(?:into|to)\s+(?:mongodb|database|collection)",
                    r"(?:read|load|import)\s+(?:file|data)\s+(?:to|into)\s+(?:mongodb|database|collection)",
                    r"(?:insert|add)\s+(?:file|json|csv)\s+(?:to|into)\s+(?:mongodb|database)",
                    r"(?:file|csv|json)\s+(?:to|into)\s+mongodb",
                    r"(?:ingest|load)\s+.*\.(?:json|csv)\s+(?:into|to)\s+database",
                    # Academic query patterns that should go to database first
                    r"(?:faculty|researcher|professor)\s+(?:data|members|distribution|profiles)",
                    r"(?:publication|research)\s+(?:data|venues|trends|analysis)",
                    r"(?:top|best)\s+(?:researchers|faculty|professors)",
                    r"(?:find|get|show|query)\s+(?:faculty|publication|university)\s+(?:data|members|information)",
                    r"(?:academic|university|research)\s+(?:data|database|information)",
                    r"h-index|citation\s+(?:data|analysis)",
                ],
                "indicators": [
                    "database",
                    "sql",
                    "mongodb",
                    "mysql",
                    "postgresql",
                    "table",
                    "schema",
                    "query",
                    "select",
                    "connect",
                    "connection",
                    "db",
                    # File ingestion indicators
                    "ingest",
                    "import",
                    ".json",
                    ".csv",
                    "load file",
                    "insert file",
                    # Academic data indicators
                    "faculty",
                    "researchers",
                    "publications",
                    "academic",
                    "university",
                    "research",
                ],
                "priority": 2,  # Higher priority for academic data queries
            },
            "assistant": {
                "keywords": [
                    "help",
                    "explain",
                    "how to",
                    "what is",
                    "tell me",
                    "can you",
                    "please",
                    "general question",
                    "conversation",
                    "chat",
                ],
                "patterns": [
                    r"(?:help|explain|tell)\s+me",
                    r"what\s+is",
                    r"how\s+(?:do\s+)?(?:I|to)",
                    r"can\s+you\s+(?:help|explain|tell|show)",
                    r"please\s+(?:help|explain)",
                ],
                "indicators": ["help", "explain", "question", "general", "can you", "please"],
                "priority": 3,  # Lower priority but catches general requests
            },
        }

    async def _analyze_query_intent(
        self, user_message: str, conversation_context: str = ""
    ) -> Dict[str, Any]:
        """Enhanced intent analysis with conversation context and system message support"""

        # Try LLM analysis first
        if self.llm_service:
            try:
                return await self._llm_analyze_intent(user_message, conversation_context)
            except Exception as e:
                self.logger.warning(f"LLM analysis failed: {e}, falling back to keyword analysis")

        # Enhanced keyword analysis as fallback
        return self._keyword_based_analysis(user_message, conversation_context)

    async def _llm_analyze_intent(
        self, user_message: str, conversation_context: str = ""
    ) -> Dict[str, Any]:
        """Use LLM to analyze user intent with system message support"""
        if not self.llm_service:
            return self._keyword_based_analysis(user_message, conversation_context)

        # Get session context for workflow continuity
        try:
            session_context = self._get_session_context()
        except Exception as e:
            self.logger.error(f"Failed to get session context: {e}")
            session_context = {}

        # Build available agents list dynamically
        available_agents_list = list(self.specialized_agents.keys())
        available_agents_desc = []
        for agent_type in available_agents_list:
            if agent_type == "code_executor":
                available_agents_desc.append(
                    "- code_executor: Code writing, execution, debugging, programming tasks"
                )
            elif agent_type == "youtube_download":
                available_agents_desc.append("- youtube_download: YouTube video/audio downloads")
            elif agent_type == "media_editor":
                available_agents_desc.append(
                    "- media_editor: FFmpeg media processing, video/audio conversion"
                )
            elif agent_type == "knowledge_base":
                available_agents_desc.append(
                    "- knowledge_base: Document ingestion, semantic search, storage"
                )
            elif agent_type == "web_search":
                available_agents_desc.append(
                    "- web_search: Web searches, finding information online"
                )
            elif agent_type == "web_scraper":
                available_agents_desc.append("- web_scraper: Website data extraction, crawling")
            elif agent_type == "api_agent":
                available_agents_desc.append(
                    "- api_agent: HTTP/REST API calls, authentication, API integration"
                )
            elif agent_type == "analytics":
                available_agents_desc.append(
                    "- analytics: Data analysis, CSV/Excel files, SQL queries, charts"
                )
            elif agent_type == "database_agent":
                available_agents_desc.append(
                    "- database_agent: Database connections, SQL queries, MongoDB/MySQL/PostgreSQL operations, academic data queries, file ingestion (JSON/CSV to MongoDB)"
                )
            elif agent_type == "assistant":
                available_agents_desc.append("- assistant: General conversation, explanations")

        # Enhanced system message for intent analysis
        analysis_system_message = f"""
        {self.system_message}

        CURRENT SESSION INFO:
        Available agents in this session: {', '.join(available_agents_list)}

        ANALYSIS TASK: Analyze the user message and respond ONLY in the specified JSON format.
        Consider conversation context when determining routing decisions.
        """

        prompt = f"""
        Analyze this user message to determine routing and workflow requirements.

        Available agents in this session:
        {chr(10).join(available_agents_desc)}

        Previous Session Context:
        {session_context}

        Conversation History:
        {conversation_context}

        Current User Message: {user_message}

        Analyze for:
        1. Multi-step workflows that need agent chaining
        2. Follow-up requests referencing previous operations
        3. Complex tasks requiring parallel or sequential coordination
        4. Context references ("that", "this", "continue", "also do")
        5. HTTP/API requests (GET, POST, PUT, DELETE, etc.)
        6. API integration tasks (authentication, REST calls, webhooks)

        ROUTING GUIDELINES:
        - Route to api_agent for: HTTP method calls (GET/POST/PUT/DELETE), API endpoints, REST API requests, webhook calls, authentication requests, API integration tasks
        - Route to database_agent for: database connections, SQL queries, MongoDB/MySQL/PostgreSQL operations, table schemas, database operations, academic data queries (faculty, publications, researchers, universities) even when analysis is requested, file ingestion specifically to database/MongoDB (only when "database" or "mongodb" is explicitly mentioned)
        - Route to web_search for: "search", "find information", "look up", research queries
        - Route to youtube_download for: YouTube URLs, video/audio downloads
        - Route to media_editor for: video/audio processing, conversion, editing
        - Route to knowledge_base for: document storage, semantic search, Q&A, file ingestion to knowledge base (when "knowledge base", "knowledgebase", or "kb" is mentioned)
        - Route to web_scraper for: data extraction, crawling websites
        - Route to analytics for: CSV/Excel files, data analysis, SQL queries, charts, DuckDB, statistics
        - Route to code_executor for: code execution, programming tasks
        - Route to assistant for: general conversation, explanations

        IMPORTANT: Only suggest agents that are actually available in this session.

        Respond in JSON format:
        {{
            "primary_agent": "agent_name",
            "confidence": 0.0-1.0,
            "reasoning": "detailed analysis with context consideration",
            "requires_multiple_agents": true/false,
            "workflow_detected": true/false,
            "workflow_type": "sequential|parallel|follow_up|none",
            "agent_chain": ["agent1", "agent2", "agent3"],
            "is_follow_up": true/false,
            "follow_up_type": "continue_workflow|modify_previous|repeat_with_variation|elaborate|related_task|none",
            "context_references": ["specific context items"],
            "workflow_description": "description of detected workflow"
        }}
        """

        try:
            # Use system message in LLM call
            response = await self.llm_service.generate_response(
                prompt=prompt, system_message=analysis_system_message
            )

            import re

            json_match = re.search(r"\{.*\}", response, re.DOTALL)
            if json_match:
                analysis = json.loads(json_match.group())

                # Enhanced validation - only include available agents
                if analysis.get("workflow_detected", False):
                    suggested_chain = analysis.get("agent_chain", [])
                    valid_chain = [
                        agent for agent in suggested_chain if agent in self.specialized_agents
                    ]

                    if len(valid_chain) != len(suggested_chain):
                        unavailable = [
                            a for a in suggested_chain if a not in self.specialized_agents
                        ]
                        self.logger.warning(f"LLM suggested unavailable agents: {unavailable}")

                    analysis["agent_chain"] = valid_chain

                    if len(valid_chain) < 2:
                        analysis["workflow_detected"] = False
                        analysis["requires_multiple_agents"] = False

                # Ensure primary agent is available
                primary_agent = analysis.get("primary_agent")
                if primary_agent not in self.specialized_agents:
                    analysis["primary_agent"] = (
                        "assistant"
                        if "assistant" in self.specialized_agents
                        else list(self.specialized_agents.keys())[0]
                    )
                    analysis["confidence"] = max(0.3, analysis.get("confidence", 0.5) - 0.2)

                # Add agent scores for compatibility
                agent_scores = {}
                if analysis.get("workflow_detected"):
                    for i, agent in enumerate(analysis.get("agent_chain", [])):
                        agent_scores[agent] = 10 - i
                else:
                    primary = analysis.get("primary_agent")
                    if primary in self.specialized_agents:
                        agent_scores[primary] = 10

                analysis["agent_scores"] = agent_scores
                analysis["context_detected"] = bool(conversation_context)
                analysis["available_agents"] = available_agents_list

                return analysis
            else:
                raise ValueError("No valid JSON in LLM response")

        except Exception as e:
            self.logger.error(f"LLM workflow analysis failed: {e}")
            return self._keyword_based_analysis(user_message, conversation_context)

    def _keyword_based_analysis(
        self, user_message: str, conversation_context: str = ""
    ) -> Dict[str, Any]:
        """Enhanced keyword analysis with context awareness"""
        message_lower = user_message.lower()

        # Enhanced code detection patterns
        code_indicators = [
            "write code",
            "create code",
            "generate code",
            "code to",
            "program to",
            "function to",
            "script to",
            "write python",
            "create python",
            "then execute",
            "and run",
            "execute it",
            "run it",
            "show results",
            "write and execute",
            "code and run",
            "multiply",
            "calculate",
            "algorithm",
        ]

        # Enhanced web search detection
        search_indicators = [
            "search web",
            "search for",
            "find online",
            "look up",
            "google",
            "search the web",
            "web search",
            "find information",
            "search about",
        ]

        # YouTube detection
        youtube_indicators = [
            "youtube",
            "youtu.be",
            "download video",
            "download audio",
            "youtube.com",
            "get from youtube",
        ]

        # Check for obvious patterns first
        if self._is_obvious_code_request(user_message):
            if "code_executor" in self.specialized_agents:
                return {
                    "primary_agent": "code_executor",
                    "confidence": 0.95,
                    "requires_multiple_agents": False,
                    "workflow_detected": False,
                    "is_follow_up": False,
                    "reasoning": "Forced routing to code_executor for obvious code request",
                }

        if self._is_obvious_search_request(user_message):
            if "web_search" in self.specialized_agents:
                return {
                    "primary_agent": "web_search",
                    "confidence": 0.95,
                    "requires_multiple_agents": False,
                    "workflow_detected": False,
                    "is_follow_up": False,
                    "reasoning": "Forced routing to web_search for search request",
                }

        # Continue with pattern matching
        agent_scores = {}
        for agent_type, patterns in self.agent_routing_patterns.items():
            if agent_type not in self.specialized_agents:
                continue

            score = 0
            score += sum(3 for keyword in patterns["keywords"] if keyword in message_lower)
            score += sum(5 for pattern in patterns["patterns"] if re.search(pattern, message_lower))
            score += sum(2 for indicator in patterns["indicators"] if indicator in message_lower)

            agent_scores[agent_type] = score

        # Check for ambiguous ingestion commands that need clarification
        clarification_needed = self._check_ingestion_ambiguity(user_message, agent_scores)
        if clarification_needed:
            return clarification_needed

        primary_agent = (
            max(agent_scores.items(), key=lambda x: x[1])[0] if agent_scores else "assistant"
        )
        confidence = (
            agent_scores.get(primary_agent, 0) / sum(agent_scores.values()) if agent_scores else 0.5
        )

        return {
            "primary_agent": primary_agent,
            "confidence": max(confidence, 0.5),
            "requires_multiple_agents": False,
            "workflow_detected": False,
            "is_follow_up": False,
            "agent_scores": agent_scores,
            "reasoning": f"Single agent routing to {primary_agent}",
        }

    def _check_ingestion_ambiguity(self, message: str, agent_scores: dict) -> Optional[dict]:
        """Check if ingestion command is ambiguous and needs clarification"""
        message_lower = message.lower()

        # Check if this is an ingestion command
        is_ingestion = any(
            keyword in message_lower for keyword in ["ingest", "import", "load into", "add to"]
        )
        if not is_ingestion:
            return None

        # Get scores for relevant agents
        db_score = agent_scores.get("database_agent", 0)
        kb_score = agent_scores.get("knowledge_base", 0)

        # Check for ambiguous cases where scores are close or both are viable
        if db_score > 0 and kb_score > 0:
            score_diff = abs(db_score - kb_score)

            # If scores are very close (within 3 points), ask for clarification
            if score_diff <= 3:
                return {
                    "primary_agent": "assistant",
                    "confidence": 0.9,
                    "requires_multiple_agents": False,
                    "workflow_detected": False,
                    "is_follow_up": False,
                    "agent_scores": agent_scores,
                    "reasoning": "Ingestion destination ambiguous - requesting clarification",
                    "clarification_request": {
                        "type": "ingestion_destination",
                        "message": self._generate_ingestion_clarification(
                            message, db_score, kb_score
                        ),
                    },
                }

        # Check for ambiguous ingestion without clear destination
        ambiguous_patterns = [
            r"ingest\s+.*\.(?:csv|json|txt)\s*$",  # Just "ingest file.csv" with no destination
            r"(?:load|import)\s+.*\.(?:csv|json|txt)\s*$",  # "load file.csv" with no destination
        ]

        if any(re.search(pattern, message_lower) for pattern in ambiguous_patterns):
            # No clear destination specified
            return {
                "primary_agent": "assistant",
                "confidence": 0.9,
                "requires_multiple_agents": False,
                "workflow_detected": False,
                "is_follow_up": False,
                "agent_scores": agent_scores,
                "reasoning": "Ingestion destination not specified - requesting clarification",
                "clarification_request": {
                    "type": "ingestion_destination",
                    "message": self._generate_ingestion_clarification(message, db_score, kb_score),
                },
            }

        return None

    def _generate_ingestion_clarification(
        self, original_message: str, db_score: int, kb_score: int
    ) -> str:
        """Generate clarification message for ingestion commands"""
        return f"""I can help you ingest data, but I need clarification on the destination:

**Your request**: "{original_message}"

**Available options**:
1. **Database Ingestion** (MongoDB/MySQL/PostgreSQL) - For structured data storage and SQL queries
2. **Knowledge Base Ingestion** (Vector Database) - For document search and semantic retrieval

**Please specify**:
- "ingest [file] into **database**" (for MongoDB/SQL database)
- "ingest [file] into **knowledge base** [name]" (for semantic search)

Which type of ingestion would you like?"""

    def _is_obvious_code_request(self, user_message: str) -> bool:
        """Detect obvious code execution requests"""
        message_lower = user_message.lower()

        strong_indicators = [
            ("write code", ["execute", "run", "show", "result"]),
            ("create code", ["execute", "run", "show", "result"]),
            ("code to", ["execute", "run", "then", "and"]),
            ("then execute", []),
            ("and run", ["code", "script", "program"]),
            ("execute it", []),
            ("run it", []),
            ("show results", ["code", "execution"]),
            ("write and execute", []),
            ("code and run", []),
        ]

        for main_phrase, context_words in strong_indicators:
            if main_phrase in message_lower:
                if not context_words:
                    return True
                if any(ctx in message_lower for ctx in context_words):
                    return True

        return False

    def _is_obvious_search_request(self, user_message: str) -> bool:
        """Detect obvious web search requests"""
        message_lower = user_message.lower()

        search_patterns = [
            r"search\s+(?:the\s+)?web\s+for",
            r"search\s+for.*(?:online|web)",
            r"find.*(?:online|web|internet)",
            r"look\s+up.*(?:online|web)",
            r"google\s+(?:for\s+)?",
            r"web\s+search\s+for",
            r"search\s+(?:about|for)\s+\w+",
        ]

        for pattern in search_patterns:
            if re.search(pattern, message_lower):
                return True

        return False

    async def _enhanced_fallback_routing(
        self,
        intent_analysis: Dict[str, Any],
        user_message: str,
        context: ExecutionContext = None,
        llm_context: Dict[str, Any] = None,
        primary_response: AgentResponse = None,
    ) -> str:
        """Enhanced fallback with intelligent code execution for unhandled tasks"""

        # Check if this is a low-confidence routing or failed primary agent
        confidence = intent_analysis.get("confidence", 0.0)
        primary_agent = intent_analysis.get("primary_agent", "assistant")

        self.logger.info(
            f"🔄 Enhanced fallback triggered for {primary_agent} (confidence: {confidence:.2f})"
        )

        # First try assistant agent if it's not the primary agent and it's available
        if (
            primary_agent != "assistant"
            and "assistant" in self.specialized_agents
            and confidence < 0.7
        ):

            self.logger.info("🎯 Trying assistant agent as first fallback")

            assistant_response = await self._route_to_agent_with_context(
                "assistant", user_message, context, llm_context
            )

            if assistant_response.success:
                return assistant_response.content

        # Check if task could be solved with code execution
        if self._is_programmable_task(user_message):
            self.logger.info("💻 Task appears programmable, attempting code execution fallback")

            if "code_executor" in self.specialized_agents:
                # Setup file sharing for Docker execution
                input_dir, output_dir = self._setup_docker_file_sharing(user_message)

                # Create enhanced prompt for code execution with file sharing instructions
                enhanced_code_prompt = await self._create_code_execution_prompt(
                    user_message, intent_analysis, llm_context
                )

                # Add file sharing context to llm_context
                if llm_context:
                    llm_context.update(
                        {
                            "docker_input_dir": input_dir,
                            "docker_output_dir": output_dir,
                            "enhanced_fallback": True,
                        }
                    )

                code_response = await self._route_to_agent_with_context_and_files(
                    "code_executor",
                    enhanced_code_prompt,
                    context,
                    llm_context,
                    input_dir,
                    output_dir,
                )

                if code_response.success:
                    # Check if output files were created
                    output_files = self._check_output_files(output_dir) if output_dir else []
                    output_summary = ""
                    if output_files:
                        output_summary = f"\n\n**📁 Generated Files:**\n" + "\n".join(
                            [f"- {file}" for file in output_files]
                        )

                    return f"""**✅ Task completed using code execution:**

{code_response.content}{output_summary}

*Note: This task was automatically solved by writing and executing code since no specialized agent could handle it directly.*"""
                else:
                    self.logger.warning(f"Code execution fallback failed: {code_response.error}")

        # Final fallback - try assistant with enhanced context or return error
        if "assistant" in self.specialized_agents:
            enhanced_assistant_prompt = f"""I need help with this request, but no specialized agent seems capable of handling it directly:

**Original Request:** {user_message}

**Analysis Result:** {intent_analysis.get('reasoning', 'No clear routing path found')}

**Available Agents:** {', '.join(self.specialized_agents.keys())}

Could you help me understand what's needed and provide guidance, or suggest an alternative approach?"""

            fallback_response = await self._route_to_agent_with_context(
                "assistant", enhanced_assistant_prompt, context, llm_context
            )

            if fallback_response.success:
                return fallback_response.content

        # Ultimate fallback - error message
        error_details = primary_response.error if primary_response else "Agent routing failed"
        return f"""**❌ Unable to Process Request**

I apologize, but I couldn't find an appropriate way to handle your request:

**Request:** {user_message}

**Primary Agent Attempted:** {primary_agent}
**Error:** {error_details}

**Available Agents:** {', '.join(self.specialized_agents.keys())}

**Suggestions:**
- Try rephrasing your request more specifically
- Check if you're asking for a capability that requires additional setup
- Contact support if this seems like it should work

Please try a different approach or rephrase your request."""

    def _is_programmable_task(self, user_message: str) -> bool:
        """Determine if a task could potentially be solved with code"""
        message_lower = user_message.lower()

        # Data conversion and file manipulation tasks
        file_conversion_indicators = [
            "convert csv to xlsx",
            "convert xlsx to csv",
            "csv to excel",
            "excel to csv",
            "convert json to csv",
            "csv to json",
            "xml to csv",
            "csv to xml",
            "convert file",
            "file conversion",
            "change format",
            "transform data",
            "parse file",
            "process file",
            "read file",
            "write file",
            "extract data from",
            "combine files",
            "merge files",
            "split file",
            "rename files",
            "organize files",
            "batch process",
        ]

        # Mathematical and calculation tasks
        calculation_indicators = [
            "calculate",
            "compute",
            "solve",
            "find result",
            "math",
            "equation",
            "formula",
            "statistics",
            "average",
            "sum",
            "count",
            "percentage",
            "total",
            "multiply",
            "divide",
            "add",
            "subtract",
            "algorithm",
        ]

        # Text processing tasks
        text_processing_indicators = [
            "parse text",
            "extract text",
            "clean text",
            "format text",
            "find pattern",
            "replace text",
            "regular expression",
            "regex",
            "word count",
            "character count",
            "text analysis",
            "string manipulation",
        ]

        # Data analysis tasks
        analysis_indicators = [
            "analyze data",
            "data analysis",
            "find trends",
            "pattern analysis",
            "compare data",
            "sort data",
            "filter data",
            "group data",
            "unique values",
            "duplicate values",
            "missing values",
        ]

        # API/web tasks that can be coded
        api_indicators = [
            "fetch data",
            "http request",
            "api call",
            "download from url",
            "scrape",
            "parse html",
            "xml parsing",
            "json parsing",
        ]

        # Automation tasks
        automation_indicators = [
            "automate",
            "batch",
            "process multiple",
            "loop through",
            "repeat for",
            "do for each",
            "bulk operation",
        ]

        all_indicators = (
            file_conversion_indicators
            + calculation_indicators
            + text_processing_indicators
            + analysis_indicators
            + api_indicators
            + automation_indicators
        )

        # Check if message contains any programmable task indicators
        contains_programmable_task = any(indicator in message_lower for indicator in all_indicators)

        # Additional heuristics
        has_specific_format_mention = any(
            fmt in message_lower for fmt in [".csv", ".xlsx", ".json", ".xml", ".txt", ".pdf"]
        )

        has_action_words = any(
            word in message_lower
            for word in ["convert", "transform", "process", "analyze", "calculate", "generate"]
        )

        return contains_programmable_task or (has_specific_format_mention and has_action_words)

    async def _create_code_execution_prompt(
        self,
        user_message: str,
        intent_analysis: Dict[str, Any],
        llm_context: Dict[str, Any] = None,
    ) -> str:
        """Create an enhanced prompt for code execution to solve the user's task"""

        # Analyze what type of task this might be
        task_type = self._identify_task_type(user_message)

        # Detect file paths in the user message for Docker volume mounting
        file_paths = self._extract_file_paths_from_message(user_message)
        file_sharing_instructions = ""

        if file_paths or task_type == "File Format Conversion":
            file_sharing_instructions = f"""

**🔗 File Access Instructions:**
- Input files are available in the `/host_input/` directory inside Docker
- Output files should be created in the `/host_output/` directory 
- Use absolute paths like `/host_input/filename.csv` to read files
- Use absolute paths like `/host_output/converted_file.xlsx` to save output files
- The Docker container has access to the host file system through these mounted volumes

**Detected File Paths:** {', '.join(file_paths) if file_paths else 'Will auto-detect from current directory'}

**File Access Example:**
```python
# Read input file
input_file = '/host_input/data.csv'
# Save output file  
output_file = '/host_output/converted_data.xlsx'
```"""

        enhanced_prompt = f"""I need you to write and execute code to solve this task that no specialized agent could handle:

**User Request:** {user_message}

**Task Analysis:** 
- Routing Confidence: {intent_analysis.get('confidence', 0.0):.2f}
- Primary Agent Attempted: {intent_analysis.get('primary_agent', 'unknown')}
- Reasoning: {intent_analysis.get('reasoning', 'No clear routing found')}
- Identified Task Type: {task_type}

**Instructions:**
1. Write clear, well-documented code to accomplish the user's request
2. Include comprehensive error handling and validation
3. Provide informative output showing what was accomplished
4. If you need to install packages, use appropriate installation commands
5. Explain your approach and any assumptions you make
6. For file operations, use the mounted volume paths as specified below

{file_sharing_instructions}

**Additional Context:**
{llm_context.get('conversation_context_summary', 'No previous context') if llm_context else 'No context available'}

Please write and execute the code to solve this task, explaining each step clearly."""

        return enhanced_prompt

    def _identify_task_type(self, user_message: str) -> str:
        """Identify the type of task for better code generation"""
        message_lower = user_message.lower()

        if any(term in message_lower for term in ["csv", "xlsx", "excel", "convert file"]):
            return "File Format Conversion"
        elif any(term in message_lower for term in ["calculate", "math", "formula", "compute"]):
            return "Mathematical Calculation"
        elif any(term in message_lower for term in ["parse", "extract", "text processing"]):
            return "Text Processing"
        elif any(term in message_lower for term in ["analyze", "statistics", "data analysis"]):
            return "Data Analysis"
        elif any(term in message_lower for term in ["api", "http", "fetch", "download"]):
            return "API/Web Request"
        elif any(term in message_lower for term in ["automate", "batch", "bulk"]):
            return "Automation/Batch Processing"
        else:
            return "General Programming Task"

    def _extract_file_paths_from_message(self, user_message: str) -> List[str]:
        """Extract file paths from the user message"""
        import re

        # Common file path patterns
        file_patterns = [
            r'["\']([^"\']+\.[a-zA-Z]{2,5})["\']',  # Quoted file paths
            r"([^\s]+\.[a-zA-Z]{2,5})(?:\s|$)",  # Unquoted file paths
            r"([./]+[^\s]*\.[a-zA-Z]{2,5})",  # Relative/absolute paths
        ]

        file_paths = []
        for pattern in file_patterns:
            matches = re.findall(pattern, user_message)
            file_paths.extend(matches)

        # Filter for common file extensions
        valid_extensions = {
            ".csv",
            ".xlsx",
            ".xls",
            ".json",
            ".txt",
            ".xml",
            ".pdf",
            ".py",
            ".js",
            ".md",
        }
        filtered_paths = []

        for path in file_paths:
            if any(path.lower().endswith(ext) for ext in valid_extensions):
                filtered_paths.append(path)

        return list(set(filtered_paths))  # Remove duplicates

    def _setup_docker_file_sharing(self, user_message: str) -> Tuple[Optional[str], Optional[str]]:
        """Setup Docker input/output directories for file sharing"""
        import os

        # Extract file paths from the message
        file_paths = self._extract_file_paths_from_message(user_message)

        # Determine input directory based on file paths or current working directory
        input_dir = None
        output_dir = None

        if file_paths:
            # Use directory of the first file found
            first_file = file_paths[0]
            if os.path.isabs(first_file):
                input_dir = os.path.dirname(first_file)
            else:
                # Relative path - use current working directory
                input_dir = os.getcwd()
        else:
            # No specific files mentioned, use current working directory
            input_dir = os.getcwd()

        # Create output directory for generated files
        output_dir = os.path.join(input_dir, "docker_output")
        os.makedirs(output_dir, exist_ok=True)

        self.logger.info(f"🔗 Docker file sharing setup - Input: {input_dir}, Output: {output_dir}")

        return input_dir, output_dir

    def _check_output_files(self, output_dir: str) -> List[str]:
        """Check what files were created in the output directory"""
        import os

        if not output_dir or not os.path.exists(output_dir):
            return []

        try:
            files = [
                f for f in os.listdir(output_dir) if os.path.isfile(os.path.join(output_dir, f))
            ]
            return sorted(files)
        except Exception as e:
            self.logger.warning(f"Error checking output files: {e}")
            return []

    async def _route_to_agent_with_context_and_files(
        self,
        agent_type: str,
        user_message: str,
        context: ExecutionContext = None,
        llm_context: Dict[str, Any] = None,
        input_dir: Optional[str] = None,
        output_dir: Optional[str] = None,
    ) -> AgentResponse:
        """Enhanced agent routing with file sharing support for Docker-based agents"""

        if agent_type == "code_executor" and input_dir and output_dir:
            # Special handling for code executor with file sharing
            agent = self.specialized_agents.get(agent_type)
            if not agent:
                return AgentResponse(
                    agent_type=agent_type,
                    content=f"Agent {agent_type} not available",
                    success=False,
                    execution_time=0.0,
                    metadata={},
                    error=f"Agent {agent_type} not initialized",
                )

            # Modify the agent's Docker executor to use enhanced file sharing
            if hasattr(agent, "docker_executor"):
                # Store original execute method
                original_execute = agent.docker_executor.execute_code

                # Create wrapper that uses file sharing
                def enhanced_execute(
                    code: str, language: str = "python", files: Dict[str, str] = None
                ):
                    return agent.docker_executor.execute_code_with_host_files(
                        code, language, input_dir, output_dir, files
                    )

                # Temporarily replace execute method
                agent.docker_executor.execute_code = enhanced_execute

                try:
                    # Route normally, but with enhanced Docker execution
                    response = await self._route_to_agent_with_context(
                        agent_type, user_message, context, llm_context
                    )

                    # Add file sharing metadata
                    if response.success:
                        response.metadata.update(
                            {
                                "docker_input_dir": input_dir,
                                "docker_output_dir": output_dir,
                                "enhanced_file_sharing": True,
                            }
                        )

                    return response

                finally:
                    # Restore original execute method
                    agent.docker_executor.execute_code = original_execute

        # Fallback to normal routing
        return await self._route_to_agent_with_context(
            agent_type, user_message, context, llm_context
        )

    def _should_trigger_enhanced_fallback(
        self, agent_response: str, user_message: str, intent_analysis: Dict[str, Any]
    ) -> bool:
        """Check if agent response suggests it couldn't handle the task properly"""

        # Check confidence level first
        confidence = intent_analysis.get("confidence", 1.0)
        if confidence < 0.7 and self._is_programmable_task(user_message):
            return True

        # Check for specific response patterns that suggest the agent couldn't handle the task
        response_lower = agent_response.lower()
        user_lower = user_message.lower()

        # Indicators that the agent couldn't handle the request properly
        failure_indicators = [
            "no dataset loaded",
            "please load data first",
            "file not found",
            "cannot find",
            "not available",
            "requires installation",
            "missing dependency",
            "configuration required",
            "please configure",
            "authentication required",
            "access denied",
            "permission denied",
            "invalid format",
            "unsupported format",
            "not supported",
            "feature not available",
        ]

        # Check if response contains failure indicators
        response_suggests_failure = any(
            indicator in response_lower for indicator in failure_indicators
        )

        # Check if the user request was for file conversion but the agent is asking for data loading
        is_conversion_request = any(
            term in user_lower for term in ["convert", "transform", "change format"]
        )
        response_asks_for_loading = "load data" in response_lower

        # Special case: Analytics agent responding to file conversion with "load data first"
        if is_conversion_request and response_asks_for_loading:
            return True

        # Check if response is much shorter than expected for the complexity of the request
        complex_request = len(user_message.split()) > 8
        short_response = len(agent_response.split()) < 20

        if complex_request and short_response and response_suggests_failure:
            return True

        return response_suggests_failure

    async def _route_to_agent_with_context(
        self,
        agent_type: str,
        user_message: str,
        context: ExecutionContext = None,
        llm_context: Dict[str, Any] = None,
    ) -> AgentResponse:
        """Enhanced agent routing with complete context and memory preservation"""

        if agent_type not in self.specialized_agents:
            return AgentResponse(
                agent_type=agent_type,
                content=f"Agent {agent_type} not available",
                success=False,
                execution_time=0.0,
                metadata={},
                error=f"Agent {agent_type} not initialized",
            )

        start_time = time.time()

        try:
            agent = self.specialized_agents[agent_type]

            # Use MODERATOR's session info for absolute consistency
            session_id = self.context.session_id
            conversation_id = self.context.conversation_id
            user_id = self.context.user_id

            # Get COMPLETE conversation history from moderator's memory
            full_conversation_history = []
            conversation_context_summary = ""

            if self.memory:
                try:
                    full_conversation_history = self.memory.get_recent_messages(
                        limit=15, conversation_id=conversation_id
                    )

                    if full_conversation_history:
                        context_parts = []
                        for msg in full_conversation_history[-5:]:
                            msg_type = msg.get("message_type", "unknown")
                            content = msg.get("content", "")[:100]
                            if msg_type == "user_input":
                                context_parts.append(f"User: {content}")
                            elif msg_type == "agent_response":
                                context_parts.append(f"Assistant: {content}")
                        conversation_context_summary = "\n".join(context_parts)

                    self.logger.info(
                        f"🧠 Retrieved {len(full_conversation_history)} messages for {agent_type}"
                    )

                except Exception as e:
                    self.logger.warning(f"Could not get conversation history: {e}")

            # Build COMPREHENSIVE LLM context with full history
            enhanced_llm_context = {
                # Preserve original context
                **(llm_context or {}),
                # Add complete conversation data
                "conversation_history": full_conversation_history,
                "conversation_context_summary": conversation_context_summary,
                "session_id": session_id,
                "conversation_id": conversation_id,
                "user_id": user_id,
                # Routing metadata
                "moderator_context": True,
                "routing_agent": self.agent_id,
                "target_agent": agent_type,
                "target_agent_class": agent.__class__.__name__,
                "routing_timestamp": datetime.now().isoformat(),
                # Context preservation flags
                "context_preserved": len(full_conversation_history) > 0,
                "memory_shared": True,
                "session_synced": True,
            }

            # Create message with COMPLETE context package and Markdown formatting instruction
            enhanced_user_message = user_message

            # Check if this is a database→analytics workflow
            if (
                llm_context
                and llm_context.get("intent_analysis", {}).get("workflow_type")
                == "database_to_analytics"
            ):

                # Use enhanced message from workflow analysis
                enhanced_user_message = llm_context["intent_analysis"].get(
                    "enhanced_message", user_message
                )
                self.logger.info(f"🔄 Using enhanced message for database→analytics workflow")

            # Add markdown formatting instruction
            enhanced_user_message = f"{enhanced_user_message}\n\n**Formatting Instruction:** Please format your response using proper Markdown syntax with appropriate headers, bold text, code blocks, and lists for maximum readability."

            agent_message = AgentMessage(
                id=f"msg_{str(uuid.uuid4())[:8]}",
                sender_id=user_id,
                recipient_id=agent.agent_id,
                content=enhanced_user_message,
                message_type=MessageType.USER_INPUT,
                session_id=session_id,
                conversation_id=conversation_id,
                metadata={
                    "llm_context": enhanced_llm_context,
                    "routed_by": self.agent_id,
                    "routing_reason": f"Moderator analysis selected {agent_type}",
                    "conversation_history_count": len(full_conversation_history),
                    "context_transfer": True,
                    "memory_shared": True,
                    "formatting_requested": "markdown",
                },
            )

            # Verify agent context is synced
            if hasattr(agent, "context"):
                if (
                    agent.context.session_id != session_id
                    or agent.context.conversation_id != conversation_id
                ):
                    self.logger.warning(f"🔧 Syncing {agent_type} context with moderator")
                    agent.context.session_id = session_id
                    agent.context.conversation_id = conversation_id
                    agent.context.user_id = user_id

            # Ensure execution context has complete information
            execution_context = context or ExecutionContext(
                session_id=session_id,
                conversation_id=conversation_id,
                user_id=user_id,
                tenant_id=self.context.tenant_id,
                metadata=enhanced_llm_context,
            )

            if context:
                context.metadata.update(enhanced_llm_context)

            # Store the routing message in shared memory BEFORE processing
            if self.memory:
                self.memory.store_message(agent_message)
                self.logger.info(f"📝 Stored routing message in shared memory")

            # Process the message with the target agent
            response_message = await agent.process_message(agent_message, execution_context)

            # Ensure response is stored in shared memory with consistent session info
            if self.memory and response_message:
                if (
                    response_message.session_id != session_id
                    or response_message.conversation_id != conversation_id
                ):

                    self.logger.info(f"🔧 Correcting response session info for continuity")

                    corrected_response = AgentMessage(
                        id=response_message.id,
                        sender_id=response_message.sender_id,
                        recipient_id=response_message.recipient_id,
                        content=response_message.content,
                        message_type=response_message.message_type,
                        session_id=session_id,
                        conversation_id=conversation_id,
                        timestamp=response_message.timestamp,
                        metadata={
                            **response_message.metadata,
                            "session_corrected_by_moderator": True,
                            "original_session_id": response_message.session_id,
                            "original_conversation_id": response_message.conversation_id,
                            "stored_by_moderator": True,
                            "agent_type": agent_type,
                        },
                    )

                    self.memory.store_message(corrected_response)
                    self.logger.info(f"📝 Stored corrected {agent_type} response in shared memory")
                else:
                    response_message.metadata.update(
                        {
                            "stored_by_moderator": True,
                            "agent_type": agent_type,
                            "context_preserved": True,
                        }
                    )
                    self.logger.info(
                        f"✅ {agent_type} response properly stored with correct session info"
                    )

            execution_time = time.time() - start_time

            return AgentResponse(
                agent_type=agent_type,
                content=response_message.content,
                success=True,
                execution_time=execution_time,
                metadata={
                    "agent_id": agent.agent_id,
                    "agent_class": agent.__class__.__name__,
                    "context_preserved": len(full_conversation_history) > 0,
                    "system_message_used": True,
                    "session_synced": True,
                    "memory_shared": True,
                    "conversation_history_count": len(full_conversation_history),
                    "routing_successful": True,
                },
            )

        except Exception as e:
            execution_time = time.time() - start_time
            self.logger.error(f"❌ Error routing to {agent_type} agent: {e}")
            import traceback

            self.logger.error(f"Full traceback: {traceback.format_exc()}")
            
            return AgentResponse(
                agent_type=agent_type,
                content=f"Error processing request with {agent_type} agent: {str(e)}",
                success=False,
                execution_time=execution_time,
                metadata={
                    "error": str(e),
                    "agent_type": agent_type,
                    "routing_failed": True,
                },
            )

    def _get_session_context(self) -> Dict[str, Any]:
        """Enhanced session context with memory verification"""
        if not hasattr(self, "memory") or not self.memory:
            return {"error": "No memory available"}

        try:
            current_workflow = self.memory.get_context("current_workflow") if self.memory else None
            last_operation = self.memory.get_context("last_operation") if self.memory else None

            conversation_history = (
                self.memory.get_recent_messages(
                    limit=5, conversation_id=self.context.conversation_id
                )
                if self.memory
                else []
            )

            context_summary = []

            if current_workflow and isinstance(current_workflow, dict):
                context_summary.append(
                    f"Active workflow: {current_workflow.get('workflow_description', 'Unknown')}"
                )
                context_summary.append(
                    f"Workflow step: {current_workflow.get('current_step', 0)} of {len(current_workflow.get('agent_chain', []))}"
                )

            if last_operation and isinstance(last_operation, dict):
                context_summary.append(
                    f"Last operation: {last_operation.get('agent_used')} - {last_operation.get('user_request', '')[:50]}"
                )

            return {
                "workflow_active": bool(
                    current_workflow
                    and isinstance(current_workflow, dict)
                    and current_workflow.get("status") == "in_progress"
                ),
                "last_agent": (
                    last_operation.get("agent_used")
                    if last_operation and isinstance(last_operation, dict)
                    else None
                ),
                "context_summary": " | ".join(context_summary),
                "conversation_length": len(conversation_history),
                "session_id": self.context.session_id,
                "conversation_id": self.context.conversation_id,
                "memory_available": True,
                "specialized_agents_count": len(self.specialized_agents),
            }
        except Exception as e:
            self.logger.error(f"Error getting session context: {e}")
            return {
                "error": str(e),
                "session_id": self.context.session_id,
                "conversation_id": self.context.conversation_id,
                "memory_available": False,
            }

    async def process_message(
        self, message: AgentMessage, context: ExecutionContext = None
    ) -> AgentMessage:
        """Main processing method with complete memory preservation and system message support"""

        # Ensure message uses moderator's session context
        if message.session_id != self.context.session_id:
            self.logger.info(
                f"🔧 Correcting message session ID: {message.session_id} → {self.context.session_id}"
            )
            message.session_id = self.context.session_id

        if message.conversation_id != self.context.conversation_id:
            self.logger.info(
                f"🔧 Correcting message conversation ID: {message.conversation_id} → {self.context.conversation_id}"
            )
            message.conversation_id = self.context.conversation_id

        # Store message with corrected session info
        if self.memory:
            self.memory.store_message(message)

        try:
            user_message = message.content
            self.update_conversation_state(user_message)

            # Get COMPLETE conversation history for context
            conversation_context = ""
            conversation_history = []

            if self.memory:
                try:
                    conversation_history = self.memory.get_recent_messages(
                        limit=10, conversation_id=self.context.conversation_id
                    )

                    if conversation_history:
                        context_parts = []
                        for msg in conversation_history[-5:]:
                            msg_type = msg.get("message_type", "unknown")
                            content = msg.get("content", "")
                            if msg_type == "user_input":
                                context_parts.append(f"User: {content[:100]}")
                            elif msg_type == "agent_response":
                                sender = msg.get("sender_id", "Assistant")
                                context_parts.append(f"{sender}: {content[:100]}")
                        conversation_context = "\n".join(context_parts)

                    self.logger.info(
                        f"🧠 Moderator retrieved {len(conversation_history)} messages for analysis"
                    )

                except Exception as e:
                    self.logger.warning(f"Could not get conversation history: {e}")

            # 🆕 Check if assigned skills should handle this request BEFORE agent routing
            skill_result = await self._should_use_assigned_skills(user_message)

            if skill_result.get("should_use_skills"):
                self.logger.info(
                    f"🔧 ModeratorAgent using assigned skill: {skill_result['used_skill']}"
                )

                # Translate technical response to natural language
                execution_result = skill_result["execution_result"]
                if execution_result.get("success"):
                    natural_response = await self._translate_technical_response(
                        execution_result, user_message
                    )

                    # Create response with skill metadata
                    response = self.create_response(
                        content=natural_response,
                        recipient_id=message.sender_id,
                        session_id=message.session_id,
                        conversation_id=message.conversation_id,
                        metadata={
                            "used_assigned_skill": True,
                            "skill_type": skill_result["intent"]["skill_type"],
                            "skill_name": skill_result["intent"]["skill_name"],
                            "skill_confidence": skill_result["intent"]["confidence"],
                            "agent_type": "moderator_with_skills",
                            "underlying_agent": execution_result.get("agent_type"),
                            "processing_timestamp": datetime.now().isoformat(),
                            "routing_bypassed": True,
                        },
                    )

                    # Store response
                    if self.memory:
                        self.memory.store_message(response)

                    self.logger.info(f"✅ ModeratorAgent skill response completed successfully")
                    return response
                else:
                    # Skill execution failed, continue with normal routing but add context
                    self.logger.warning(
                        f"Assigned skill failed: {execution_result.get('error')}, falling back to agent routing"
                    )
                    # Don't modify user_message here - let normal routing handle it

            # Check for database→analytics handoff in conversation history
            database_handoff_detected = await self._check_for_database_analytics_handoff(
                conversation_history
            )

            # Check if this requires academic database access first
            academic_data_required = self._needs_academic_database_access(user_message)

            # Analyze intent with complete context
            intent_analysis = await self._analyze_query_intent(user_message, conversation_context)

            # Override intent if academic data is required and no connection exists
            if academic_data_required and not database_handoff_detected:
                self.logger.info(
                    "🎓 Academic data query detected, creating database→analytics workflow"
                )
                intent_analysis = {
                    "primary_agent": "database_agent",
                    "confidence": 0.95,
                    "requires_multiple_agents": True,
                    "workflow_type": "academic_data_analysis",
                    "enhanced_message": f"First, query the database for: {user_message}\nThen export the results for analysis and visualization.",
                    "agent_scores": {"database_agent": 0.95, "analytics": 0.85, "assistant": 0.1},
                }

            # Override intent if database→analytics workflow is detected
            elif database_handoff_detected:
                self.logger.info(
                    "🔄 Database→Analytics handoff detected, routing to analytics workflow"
                )
                intent_analysis = await self._create_database_analytics_workflow(
                    user_message, database_handoff_detected, intent_analysis
                )

            self.logger.info(
                f"Intent analysis: Primary={intent_analysis['primary_agent']}, "
                f"Confidence={intent_analysis['confidence']:.2f}, "
                f"Multi-agent={intent_analysis.get('requires_multiple_agents', False)}"
            )

            # Build COMPREHENSIVE LLM context for routing decisions
            llm_context = {
                "conversation_id": self.context.conversation_id,
                "user_id": self.context.user_id,
                "session_id": self.context.session_id,
                "conversation_history": conversation_history,
                "conversation_context_summary": conversation_context,
                "intent_analysis": intent_analysis,
                "agent_role": self.role.value,
                "agent_name": self.name,
                "moderator_agent_id": self.agent_id,
                "available_agents": list(self.specialized_agents.keys()),
                "memory_preserved": len(conversation_history) > 0,
                "context_source": "moderator_memory",
            }

            # Process with enhanced context preservation
            response_content = ""

            if intent_analysis.get("requires_multiple_agents", False):
                workflow_type = intent_analysis.get("workflow_type", "sequential")
                agent_chain = intent_analysis.get("agent_chain", [intent_analysis["primary_agent"]])

                if workflow_type == "sequential":
                    response_content = await self._coordinate_sequential_workflow_with_context(
                        agent_chain, user_message, context, llm_context
                    )
                else:
                    response_content = await self._coordinate_multiple_agents_with_context(
                        agent_chain, user_message, context, llm_context
                    )
            else:
                # Single agent routing with complete context
                primary_response = await self._route_to_agent_with_context(
                    intent_analysis["primary_agent"], user_message, context, llm_context
                )

                if primary_response.success:
                    # Check if response suggests agent couldn't handle the task properly
                    should_fallback = self._should_trigger_enhanced_fallback(
                        primary_response.content, user_message, intent_analysis
                    )

                    if should_fallback:
                        # Enhanced fallback with intelligent code execution
                        response_content = await self._enhanced_fallback_routing(
                            intent_analysis, user_message, context, llm_context, primary_response
                        )
                    else:
                        response_content = primary_response.content
                else:
                    # Enhanced fallback with intelligent code execution
                    response_content = await self._enhanced_fallback_routing(
                        intent_analysis, user_message, context, llm_context, primary_response
                    )

            # Create response with consistent session info
            response = self.create_response(
                content=response_content,
                metadata={
                    "routing_analysis": intent_analysis,
                    "agent_scores": intent_analysis.get("agent_scores", {}),
                    "workflow_type": intent_analysis.get("workflow_type", "single"),
                    "context_preserved": len(conversation_history) > 0,
                    "conversation_history_count": len(conversation_history),
                    "system_message_used": True,
                    "memory_consistent": True,
                    "session_id": self.context.session_id,
                    "conversation_id": self.context.conversation_id,
                },
                recipient_id=message.sender_id,
                session_id=self.context.session_id,
                conversation_id=self.context.conversation_id,
            )

            # Store response in shared memory
            if self.memory:
                self.memory.store_message(response)
                self.logger.info(f"📝 Stored moderator response in shared memory")

            return response

        except Exception as e:
            self.logger.error(f"ModeratorAgent error: {e}")
            import traceback

            self.logger.error(f"Full traceback: {traceback.format_exc()}")

            error_response = self.create_response(
                content=f"I encountered an error processing your request: {str(e)}",
                recipient_id=message.sender_id,
                message_type=MessageType.ERROR,
                session_id=self.context.session_id,
                conversation_id=self.context.conversation_id,
            )
            return error_response

    async def _coordinate_multiple_agents_with_context(
        self,
        agents: List[str],
        user_message: str,
        context: ExecutionContext = None,
        llm_context: Dict[str, Any] = None,
    ) -> str:
        """Coordinate multiple agents with context preservation"""
        successful_responses = 0
        response_parts = ["🔀 **Multi-Agent Analysis Results**\n\n"]

        for i, agent_type in enumerate(agents, 1):
            try:
                agent_response = await self._route_to_agent_with_context(
                    agent_type, user_message, context, llm_context
                )

                if agent_response.success:
                    response_parts.append(f"**{i}. {agent_type.replace('_', ' ').title()}:**\n")
                    response_parts.append(f"{agent_response.content}\n\n")
                    successful_responses += 1
                else:
                    response_parts.append(
                        f"**{i}. {agent_type.replace('_', ' ').title()} (Error):**\n"
                    )
                    response_parts.append(f"Error: {agent_response.error}\n\n")

            except Exception as e:
                response_parts.append(
                    f"**{i}. {agent_type.replace('_', ' ').title()} (Failed):**\n"
                )
                response_parts.append(f"Failed: {str(e)}\n\n")

        if successful_responses == 0:
            return "I wasn't able to process your request with any of the available agents."

        return "".join(response_parts).strip()

    async def _coordinate_sequential_workflow_with_context(
        self,
        agents: List[str],
        user_message: str,
        context: ExecutionContext = None,
        llm_context: Dict[str, Any] = None,
    ) -> str:
        """Sequential workflow with complete context preservation"""

        workflow_results = []
        current_context = user_message
        failed_agents = []

        for i, agent_type in enumerate(agents):
            try:
                self.logger.info(f"Workflow step {i + 1}: Running {agent_type} with full context")

                if agent_type not in self.specialized_agents:
                    failed_agents.append(agent_type)
                    self.logger.warning(f"Agent {agent_type} not available at step {i + 1}")
                    continue

                # Build cumulative context for each step
                if i > 0:
                    previous_results = "\n".join(
                        [
                            f"Step {r['step']} ({r['agent']}): {r['content'][:200]}..."
                            for r in workflow_results[-2:]
                        ]
                    )

                    current_context = f"""Based on previous workflow steps:
{previous_results}

Original request: {user_message}

Please continue with the next step for {agent_type} processing."""

                    if llm_context:
                        llm_context.update(
                            {
                                "workflow_step": i + 1,
                                "workflow_progress": workflow_results,
                                "previous_results": previous_results,
                            }
                        )

                response = await self._route_to_agent_with_context(
                    agent_type, current_context, context, llm_context
                )

                workflow_results.append(
                    {
                        "agent": agent_type,
                        "content": response.content,
                        "success": response.success,
                        "step": i + 1,
                        "execution_time": response.execution_time,
                        "context_preserved": response.metadata.get("context_preserved", False),
                    }
                )

                if not response.success:
                    self.logger.warning(
                        f"Workflow step {i + 1} failed for {agent_type}: {response.error}"
                    )
                    failed_agents.append(agent_type)

            except Exception as e:
                self.logger.error(f"Workflow error at step {i + 1} ({agent_type}): {e}")
                failed_agents.append(agent_type)
                continue

        # Format comprehensive workflow results
        if not workflow_results:
            return (
                f"I wasn't able to complete the workflow. Failed agents: {', '.join(failed_agents)}"
            )

        response_parts = [f"🔄 **Multi-Step Workflow Completed** ({len(workflow_results)} steps"]
        if failed_agents:
            response_parts[0] += f", {len(failed_agents)} failed"
        response_parts[0] += ")\n\n"

        for result in workflow_results:
            status_emoji = "✅" if result["success"] else "❌"
            context_emoji = "🧠" if result.get("context_preserved") else "⚠️"

            response_parts.append(
                f"**Step {result['step']} - {result['agent'].replace('_', ' ').title()}:** {status_emoji} {context_emoji}\n"
            )
            response_parts.append(f"{result['content']}\n\n")
            response_parts.append("─" * 50 + "\n\n")

        if failed_agents:
            response_parts.append(
                f"\n⚠️ **Note:** Some agents failed: {', '.join(set(failed_agents))}"
            )

        response_parts.append(f"\n💾 **Context preserved throughout workflow**")

        return "".join(response_parts).strip()

    async def process_message_stream(
        self, message: AgentMessage, context: ExecutionContext = None
    ) -> AsyncIterator[StreamChunk]:
        """Stream processing with system message support and memory preservation"""

        # Ensure message uses moderator's session context
        if message.session_id != self.context.session_id:
            message.session_id = self.context.session_id
        if message.conversation_id != self.context.conversation_id:
            message.conversation_id = self.context.conversation_id

        if self.memory:
            self.memory.store_message(message)

        try:
            user_message = message.content

            # Get conversation history for streaming
            conversation_context = ""
            conversation_history = []

            if self.memory:
                try:
                    conversation_history = self.memory.get_recent_messages(
                        limit=5, conversation_id=self.context.conversation_id
                    )
                    if conversation_history:
                        context_parts = []
                        for msg in conversation_history[-3:]:
                            msg_type = msg.get("message_type", "unknown")
                            content = msg.get("content", "")
                            if msg_type == "user_input":
                                context_parts.append(f"User: {content[:80]}")
                            elif msg_type == "agent_response":
                                context_parts.append(f"Assistant: {content[:80]}")
                        conversation_context = "\n".join(context_parts)
                except Exception as e:
                    self.logger.warning(f"Could not get conversation history for streaming: {e}")

            # PHASE 1: Analysis Phase with Progress
            yield StreamChunk(
                text="**Analyzing your request...**\n\n",
                sub_type=StreamSubType.STATUS,
                metadata={"agent": "moderator", "phase": "analysis"},
            )
            self.update_conversation_state(user_message)

            yield StreamChunk(
                text="Checking conversation context...\n",
                sub_type=StreamSubType.STATUS,
                metadata={"phase": "context_check"},
            )
            yield StreamChunk(
                text="Determining the best approach...\n\n",
                sub_type=StreamSubType.STATUS,
                metadata={"phase": "route_determination"},
            )

            # Analyze intent with conversation context
            intent_analysis = await self._analyze_query_intent(user_message, conversation_context)

            # PHASE 2: Routing Phase with Agent Selection
            agent_name = intent_analysis["primary_agent"].replace("_", " ").title()
            confidence = intent_analysis.get("confidence", 0)
            workflow_type = intent_analysis.get("workflow_type", "single")

            yield StreamChunk(
                text=f"**Routing to {agent_name}** (confidence: {confidence:.1f})\n",
                sub_type=StreamSubType.STATUS,
                metadata={"routing_to": intent_analysis["primary_agent"], "confidence": confidence},
            )
            yield StreamChunk(
                text=f"**Workflow:** {workflow_type.title()}\n\n",
                sub_type=StreamSubType.STATUS,
                metadata={"workflow_type": workflow_type},
            )

            await asyncio.sleep(0.1)

            # Build LLM context for streaming
            llm_context = {
                "conversation_id": self.context.conversation_id,
                "user_id": self.context.user_id,
                "session_id": self.context.session_id,
                "conversation_history": conversation_history,
                "conversation_context_summary": conversation_context,
                "intent_analysis": intent_analysis,
                "streaming": True,
                "agent_role": self.role.value,
                "agent_name": self.name,
                "moderator_agent_id": self.agent_id,
            }

            # PHASE 3: Stream Actual Processing with Context
            if intent_analysis.get("requires_multiple_agents", False):
                if workflow_type == "sequential":
                    yield "🔄 **Sequential Workflow Coordination...**\n\n"
                    async for chunk in self._coordinate_multiple_agents_stream_with_context(
                        intent_analysis.get("agent_chain", [intent_analysis["primary_agent"]]),
                        user_message,
                        context,
                        llm_context,
                    ):
                        yield chunk
                else:
                    yield "🔀 **Parallel Agent Coordination...**\n\n"
                    async for chunk in self._coordinate_multiple_agents_stream_with_context(
                        intent_analysis.get("agent_chain", [intent_analysis["primary_agent"]]),
                        user_message,
                        context,
                        llm_context,
                    ):
                        yield chunk
            else:
                # Single agent processing with context and fallback support
                try:
                    async for chunk in self._route_to_agent_stream_with_context(
                        intent_analysis["primary_agent"], user_message, context, llm_context
                    ):
                        yield chunk
                except Exception as e:
                    # Check if we should try enhanced fallback for streaming
                    self.logger.warning(f"Primary agent streaming failed: {e}")

                    # Try fallback for streaming if applicable
                    confidence = intent_analysis.get("confidence", 0.0)
                    if (
                        confidence < 0.7
                        and self._is_programmable_task(user_message)
                        and "code_executor" in self.specialized_agents
                    ):

                        yield StreamChunk(
                            text="**Primary agent failed. Attempting code execution fallback...**\n\n",
                            sub_type=StreamSubType.STATUS,
                            metadata={
                                "fallback_triggered": True,
                                "fallback_type": "code_execution",
                            },
                        )

                        enhanced_code_prompt = await self._create_code_execution_prompt(
                            user_message, intent_analysis, llm_context
                        )

                        async for chunk in self._route_to_agent_stream_with_context(
                            "code_executor", enhanced_code_prompt, context, llm_context
                        ):
                            yield chunk

                        yield StreamChunk(
                            text="\n*Note: This task was automatically solved by writing and executing code since no specialized agent could handle it directly.*",
                            sub_type=StreamSubType.STATUS,
                            metadata={"fallback_completed": True},
                        )
                    else:
                        yield StreamChunk(
                            text=f"❌ Error: {str(e)}",
                            sub_type=StreamSubType.ERROR,
                            metadata={"error": str(e)},
                        )

            # PHASE 4: Completion Summary
            reasoning = intent_analysis.get("reasoning", "Standard routing")
            context_preserved = len(conversation_history) > 0
            # yield f"\n\n*✅ Completed by: {agent_name}*\n*🧠 Reasoning: {reasoning}*"
            # if context_preserved:
            #     yield f"\n*💾 Context: {len(conversation_history)} messages preserved*"
            yield f"\n"

        except Exception as e:
            self.logger.error(f"ModeratorAgent streaming error: {e}")
            yield f"\n\n❌ **Error:** {str(e)}"

    async def _route_to_agent_stream_with_context(
        self,
        agent_type: str,
        user_message: str,
        context: ExecutionContext = None,
        llm_context: Dict[str, Any] = None,
    ) -> AsyncIterator[StreamChunk]:
        """Stream routing to a specific agent with context preservation"""
        if agent_type not in self.specialized_agents:
            yield f"❌ Agent {agent_type} not available"
            return

        try:
            agent = self.specialized_agents[agent_type]

            if hasattr(agent, "process_message_stream"):
                # Add Markdown formatting instruction for streaming
                enhanced_user_message = f"{user_message}\n\n**Formatting Instruction:** Please format your response using proper Markdown syntax with appropriate headers, bold text, code blocks, and lists for maximum readability."

                agent_message = AgentMessage(
                    id=str(uuid.uuid4()),
                    sender_id=self.context.user_id,
                    recipient_id=agent.agent_id,
                    content=enhanced_user_message,
                    message_type=MessageType.USER_INPUT,
                    session_id=self.context.session_id,
                    conversation_id=self.context.conversation_id,
                    metadata={
                        "llm_context": llm_context,
                        "routed_by": self.agent_id,
                        "streaming": True,
                        "formatting_requested": "markdown",
                    },
                )

                if context and llm_context:
                    context.metadata.update(llm_context)
                else:
                    context = ExecutionContext(
                        session_id=self.context.session_id,
                        conversation_id=self.context.conversation_id,
                        user_id=self.context.user_id,
                        tenant_id=self.context.tenant_id,
                        metadata=llm_context or {},
                    )

                async for chunk in agent.process_message_stream(agent_message, context):
                    yield chunk
            else:
                yield StreamChunk(
                    text=f"⚠️ {agent_type} doesn't support streaming, using standard processing...\n\n",
                    sub_type=StreamSubType.STATUS,
                    metadata={"agent_type": agent_type, "fallback": True},
                )
                response = await self._route_to_agent_with_context(
                    agent_type, user_message, context, llm_context
                )
                yield StreamChunk(
                    text=response.content,
                    sub_type=StreamSubType.CONTENT,
                    metadata={"agent_type": agent_type, "non_streaming_response": True},
                )

        except Exception as e:
            yield StreamChunk(
                text=f"❌ Error routing to {agent_type}: {str(e)}",
                sub_type=StreamSubType.ERROR,
                metadata={"error": str(e), "agent_type": agent_type},
            )

    async def _coordinate_multiple_agents_stream_with_context(
        self,
        agents: List[str],
        user_message: str,
        context: ExecutionContext = None,
        llm_context: Dict[str, Any] = None,
    ) -> AsyncIterator[StreamChunk]:
        """Stream coordination of multiple agents with context preservation"""
        successful_responses = 0

        for i, agent_type in enumerate(agents, 1):
            try:
                yield StreamChunk(
                    text=f"**🤖 Agent {i}: {agent_type.replace('_', ' ').title()}**\n",
                    sub_type=StreamSubType.STATUS,
                    metadata={"agent_sequence": i, "agent_type": agent_type},
                )
                yield StreamChunk(
                    text="─" * 50 + "\n",
                    sub_type=StreamSubType.STATUS,
                    metadata={"separator": True},
                )

                async for chunk in self._route_to_agent_stream_with_context(
                    agent_type, user_message, context, llm_context
                ):
                    yield chunk

                yield StreamChunk(
                    text="\n" + "─" * 50 + "\n\n",
                    sub_type=StreamSubType.STATUS,
                    metadata={"separator": True, "agent_completed": agent_type},
                )
                successful_responses += 1
                await asyncio.sleep(0.1)

            except Exception as e:
                yield StreamChunk(
                    text=f"❌ Error with {agent_type}: {str(e)}\n\n",
                    sub_type=StreamSubType.ERROR,
                    metadata={"agent_type": agent_type, "error": str(e)},
                )

        yield StreamChunk(
            text=f"✅ {successful_responses}/{len(agents)} agents completed with context preserved",
            sub_type=StreamSubType.STATUS,
            metadata={
                "summary": True,
                "successful_agents": successful_responses,
                "total_agents": len(agents),
            },
        )

    async def get_agent_status(self) -> Dict[str, Any]:
        """Get status of all managed agents"""
        status = {
            "moderator_id": self.agent_id,
            "session_id": self.context.session_id,
            "conversation_id": self.context.conversation_id,
            "user_id": self.context.user_id,
            "enabled_agents": self.enabled_agents,
            "active_agents": {},
            "total_agents": len(self.specialized_agents),
            "routing_patterns": len(self.agent_routing_patterns),
            "system_message_enabled": bool(self.system_message),
            "memory_available": bool(self.memory),
            "llm_service_available": bool(self.llm_service),
        }

        for agent_type, agent in self.specialized_agents.items():
            try:
                status["active_agents"][agent_type] = {
                    "agent_id": agent.agent_id,
                    "status": "active",
                    "session_id": (
                        agent.context.session_id if hasattr(agent, "context") else "unknown"
                    ),
                    "conversation_id": (
                        agent.context.conversation_id if hasattr(agent, "context") else "unknown"
                    ),
                    "session_synced": (
                        hasattr(agent, "context")
                        and agent.context.session_id == self.context.session_id
                    ),
                    "conversation_synced": (
                        hasattr(agent, "context")
                        and agent.context.conversation_id == self.context.conversation_id
                    ),
                }
            except Exception as e:
                status["active_agents"][agent_type] = {
                    "agent_id": getattr(agent, "agent_id", "unknown"),
                    "status": "error",
                    "error": str(e),
                }

        return status

    async def debug_memory_consistency(self) -> Dict[str, Any]:
        """Debug method to verify memory consistency across agents"""
        try:
            debug_info = {
                "moderator_info": {
                    "agent_id": self.agent_id,
                    "session_id": self.context.session_id,
                    "conversation_id": self.context.conversation_id,
                    "user_id": self.context.user_id,
                },
                "specialized_agents": {},
                "memory_consistency": {},
                "conversation_history": {},
            }

            # Check each specialized agent's context
            for agent_type, agent in self.specialized_agents.items():
                agent_info = {
                    "agent_id": agent.agent_id,
                    "class_name": agent.__class__.__name__,
                    "has_context": hasattr(agent, "context"),
                    "has_memory": hasattr(agent, "memory"),
                }

                if hasattr(agent, "context"):
                    agent_info.update(
                        {
                            "session_id": agent.context.session_id,
                            "conversation_id": agent.context.conversation_id,
                            "user_id": agent.context.user_id,
                            "session_matches": agent.context.session_id == self.context.session_id,
                            "conversation_matches": agent.context.conversation_id
                            == self.context.conversation_id,
                        }
                    )

                debug_info["specialized_agents"][agent_type] = agent_info

            # Check memory consistency
            if self.memory:
                try:
                    messages = self.memory.get_recent_messages(
                        limit=10, conversation_id=self.context.conversation_id
                    )

                    debug_info["conversation_history"] = {
                        "total_messages": len(messages),
                        "session_id_used": self.context.conversation_id,
                        "message_types": [msg.get("message_type") for msg in messages[-5:]],
                        "recent_senders": [msg.get("sender_id") for msg in messages[-5:]],
                    }

                    if hasattr(self.memory, "debug_session_keys"):
                        key_debug = self.memory.debug_session_keys(
                            session_id=self.context.session_id,
                            conversation_id=self.context.conversation_id,
                        )
                        debug_info["memory_consistency"] = key_debug

                except Exception as e:
                    debug_info["memory_consistency"] = {"error": str(e)}

            return debug_info

        except Exception as e:
            return {"error": f"Debug failed: {str(e)}"}

    async def cleanup_session(self) -> bool:
        """Cleanup all managed agents and session resources"""
        success = True

        # Cleanup all specialized agents
        for agent_type, agent in self.specialized_agents.items():
            try:
                if hasattr(agent, "cleanup_session"):
                    await agent.cleanup_session()
                self.logger.info(f"Cleaned up {agent_type} agent")
            except Exception as e:
                self.logger.error(f"Error cleaning up {agent_type} agent: {e}")
                success = False

        # Cleanup moderator itself
        moderator_cleanup = await super().cleanup_session()

        return success and moderator_cleanup

    async def _check_for_database_analytics_handoff(
        self, conversation_history: List[Dict[str, Any]]
    ) -> Optional[str]:
        """Check if recent conversation contains database handoff for analytics"""
        if not conversation_history:
            return None

        # Look for ANALYTICS_HANDOFF messages in recent history
        for message in conversation_history[-5:]:  # Check last 5 messages
            content = message.get("content", "")
            if "ANALYTICS_HANDOFF:" in content:
                # Extract CSV path from handoff message
                try:
                    csv_path = content.split("ANALYTICS_HANDOFF:")[1].strip()
                    # Verify file exists
                    if os.path.exists(csv_path):
                        return csv_path
                except (IndexError, AttributeError):
                    continue

        return None

    def _needs_academic_database_access(self, user_message: str) -> bool:
        """Check if query requires academic data from database first"""
        message_lower = user_message.lower()

        # Academic data keywords
        academic_keywords = [
            "faculty",
            "professors",
            "researchers",
            "academic",
            "university",
            "publication",
            "research",
            "citation",
            "h-index",
            "department",
            "venue",
            "academic data",
            "research data",
            "university data",
        ]

        # Analysis keywords that suggest processing after data retrieval
        analysis_keywords = [
            "analyze",
            "analysis",
            "distribution",
            "trends",
            "insights",
            "visualize",
            "visualization",
            "visualizations",
            "chart",
            "graph",
            "statistics",
            "compare",
            "top",
            "best",
            "ranking",
            "summary",
            "show",
            "display",
            "create",
            "generate",
            "plot",
            "analytics",
            "get",
            "retrieve",
            "find",
            "list",
            "view",
            "explore",
        ]

        # Check if message contains both academic data and analysis requests
        has_academic_data = any(keyword in message_lower for keyword in academic_keywords)
        has_analysis_request = any(keyword in message_lower for keyword in analysis_keywords)

        return has_academic_data and has_analysis_request

    async def _create_database_analytics_workflow(
        self, user_message: str, csv_path: str, original_intent: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Create workflow configuration for database→analytics handoff"""

        # Check if user is asking for analytics/visualization
        analytics_request = any(
            word in user_message.lower()
            for word in [
                "analyze",
                "chart",
                "graph",
                "visualize",
                "plot",
                "statistics",
                "summary",
                "insights",
                "trends",
                "correlation",
                "dashboard",
            ]
        )

        if analytics_request:
            # Create enhanced analytics prompt with CSV path and load command
            rel_path = os.path.relpath(csv_path)
            enhanced_message = f"""Database query results have been exported. 

First, load the data using: load data from {rel_path}

Then proceed with the user's request: {user_message}

The CSV file contains database query results and is ready for analysis and visualization."""

            return {
                "primary_agent": "analytics",
                "confidence": 0.95,
                "requires_multiple_agents": False,
                "workflow_type": "database_to_analytics",
                "enhanced_message": enhanced_message,
                "csv_path": csv_path,
                "original_intent": original_intent,
                "agent_scores": {"analytics": 0.95, "database_agent": 0.1, "assistant": 0.1},
            }
        else:
            # User might be asking about the data or something else
            return original_intent


# integration_guide.py
"""
Integration Guide: How to add workflow capabilities to your existing ambivo_agents system
"""


# 1. Simple Integration with Existing ModeratorAgent
# Add this to your ambivo_agents/agents/moderator.py


class EnhancedModeratorAgent(ModeratorAgent):
    """ModeratorAgent enhanced with workflow capabilities"""

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        from ..core.workflow import WorkflowPatterns

        # Initialize workflows when agents are available
        self.workflows = {}
        self._setup_default_workflows()

    def _setup_default_workflows(self):
        """Setup default workflows using available specialized agents"""
        try:
            # Only create workflows for available agents
            available_agents = list(self.specialized_agents.keys())

            # Search -> Scrape -> Ingest workflow
            if all(
                agent in available_agents
                for agent in ["web_search", "web_scraper", "knowledge_base"]
            ):
                workflow = WorkflowPatterns.create_search_scrape_ingest_workflow(
                    self.specialized_agents["web_search"],
                    self.specialized_agents["web_scraper"],
                    self.specialized_agents["knowledge_base"],
                )
                self.workflows["search_scrape_ingest"] = workflow
                self.logger.info("✅ Registered search_scrape_ingest workflow")

            # Media processing workflow
            if all(agent in available_agents for agent in ["youtube_download", "media_editor"]):
                workflow = WorkflowPatterns.create_media_processing_workflow(
                    self.specialized_agents["youtube_download"],
                    self.specialized_agents["media_editor"],
                )
                self.workflows["media_processing"] = workflow
                self.logger.info("✅ Registered media_processing workflow")

        except Exception as e:
            self.logger.warning(f"Could not setup all workflows: {e}")

    async def process_message(
        self, message: AgentMessage, context: ExecutionContext = None
    ) -> AgentMessage:
        """Enhanced message processing with workflow detection"""

        # Check for workflow patterns in user message
        content = message.content.lower()

        # Detect workflow requests
        if self._is_workflow_request(content):
            return await self._handle_workflow_request(message, context)

        # Fall back to standard moderator behavior
        return await super().process_message(message, context)

    def _is_workflow_request(self, content: str) -> bool:
        """Detect if message requests a workflow"""
        workflow_patterns = [
            "search scrape ingest",
            "search and scrape and ingest",
            "find scrape store",
            "research and store",
            "download and process",
            "youtube download convert",
            "get video and edit",
        ]

        return any(pattern in content for pattern in workflow_patterns)

    async def _handle_workflow_request(
        self, message: AgentMessage, context: ExecutionContext
    ) -> AgentMessage:
        """Handle workflow execution requests"""
        content = message.content.lower()

        try:
            # Determine which workflow to run
            if any(phrase in content for phrase in ["search scrape ingest", "research and store"]):
                if "search_scrape_ingest" in self.workflows:
                    result = await self.workflows["search_scrape_ingest"].execute(
                        message.content, context or self.get_execution_context()
                    )
                    return self._format_workflow_response(
                        result, message, "Search → Scrape → Ingest"
                    )
                else:
                    return self.create_response(
                        content="Search-Scrape-Ingest workflow not available. Missing required agents.",
                        recipient_id=message.sender_id,
                        session_id=message.session_id,
                        conversation_id=message.conversation_id,
                    )

            elif any(phrase in content for phrase in ["download and process", "youtube download"]):
                if "media_processing" in self.workflows:
                    result = await self.workflows["media_processing"].execute(
                        message.content, context or self.get_execution_context()
                    )
                    return self._format_workflow_response(result, message, "Download → Process")
                else:
                    return self.create_response(
                        content="Media processing workflow not available. Missing required agents.",
                        recipient_id=message.sender_id,
                        session_id=message.session_id,
                        conversation_id=message.conversation_id,
                    )

            else:
                # Generic workflow help
                return self.create_response(
                    content=self._get_workflow_help(),
                    recipient_id=message.sender_id,
                    session_id=message.session_id,
                    conversation_id=message.conversation_id,
                )

        except Exception as e:
            return self.create_response(
                content=f"Workflow execution failed: {str(e)}",
                recipient_id=message.sender_id,
                message_type=MessageType.ERROR,
                session_id=message.session_id,
                conversation_id=message.conversation_id,
            )

    def _format_workflow_response(self, result, original_message, workflow_name):
        """Format workflow result into response message"""
        if result.success:
            content = f"🎉 **{workflow_name} Workflow Completed**\n\n"
            content += f"⏱️ **Execution Time:** {result.execution_time:.2f} seconds\n"
            content += f"🔧 **Steps Executed:** {' → '.join(result.nodes_executed)}\n"
            content += f"💬 **Messages Generated:** {len(result.messages)}\n\n"

            # Include final result
            if result.messages:
                final_msg = result.messages[-1]
                content += f"**Final Result:**\n{final_msg.content[:500]}"
                if len(final_msg.content) > 500:
                    content += "... (truncated)"

            return self.create_response(
                content=content,
                recipient_id=original_message.sender_id,
                session_id=original_message.session_id,
                conversation_id=original_message.conversation_id,
            )
        else:
            error_content = f"❌ **{workflow_name} Workflow Failed**\n\n"
            error_content += f"**Errors:**\n" + "\n".join(result.errors)

            return self.create_response(
                content=error_content,
                recipient_id=original_message.sender_id,
                message_type=MessageType.ERROR,
                session_id=original_message.session_id,
                conversation_id=original_message.conversation_id,
            )

    def _get_workflow_help(self) -> str:
        """Get help text for available workflows"""
        help_text = "🔄 **Available Workflows**\n\n"

        if "search_scrape_ingest" in self.workflows:
            help_text += "🔍 **Search → Scrape → Ingest**\n"
            help_text += "   Searches web, scrapes results, stores in knowledge base\n"
            help_text += "   *Example: 'Search scrape ingest information about quantum computing into my_kb'*\n\n"

        if "media_processing" in self.workflows:
            help_text += "🎬 **Download → Process**\n"
            help_text += "   Downloads from YouTube and processes media\n"
            help_text += (
                "   *Example: 'Download and process https://youtube.com/watch?v=abc123 as MP3'*\n\n"
            )

        if not self.workflows:
            help_text += "⚠️ No workflows available. Required agents may not be configured.\n\n"

        help_text += "💡 **How to use:**\n"
        help_text += "Simply describe what you want to do using natural language!\n"
        help_text += "The moderator will detect workflow patterns and execute them automatically."

        return help_text


# 2. Easy Setup Script for Your Existing System


async def setup_workflow_system():
    """Easy setup script to add workflows to existing ambivo_agents"""

    print("🚀 Setting up Ambivo Agents Workflow System...")

    # Create enhanced moderator with all available agents
    from ambivo_agents.agents import ModeratorAgent
    from ambivo_agents.core.workflow import WorkflowPatterns

    # Create moderator with auto-configuration
    moderator = ModeratorAgent.create_simple(
        user_id="workflow_setup",
        enabled_agents=[
            "web_search",
            "web_scraper",
            "knowledge_base",
            "youtube_download",
            "media_editor",
            "assistant",
            "code_executor",
            "api_agent",
        ],
    )

    # Setup workflows if agents are available
    workflows = {}

    # Search-Scrape-Ingest workflow
    if all(
        agent in moderator.specialized_agents
        for agent in ["web_search", "web_scraper", "knowledge_base"]
    ):
        workflows["research"] = WorkflowPatterns.create_search_scrape_ingest_workflow(
            moderator.specialized_agents["web_search"],
            moderator.specialized_agents["web_scraper"],
            moderator.specialized_agents["knowledge_base"],
        )
        print("✅ Research workflow ready")

    # Media processing workflow
    if all(agent in moderator.specialized_agents for agent in ["youtube_download", "media_editor"]):
        workflows["media"] = WorkflowPatterns.create_media_processing_workflow(
            moderator.specialized_agents["youtube_download"],
            moderator.specialized_agents["media_editor"],
        )
        print("✅ Media workflow ready")

    print(f"\n🎉 Workflow system ready with {len(workflows)} workflows!")
    return moderator, workflows


# 3. Simple Usage Examples


async def quick_workflow_examples():
    """Quick examples of using workflows"""

    # Setup
    moderator, workflows = await setup_workflow_system()

    # Example 1: Research workflow
    if "research" in workflows:
        print("\n🔍 Testing Research Workflow...")
        response = await moderator.chat(
            "Search scrape ingest information about renewable energy trends into energy_research knowledge base"
        )
        print(f"Response: {response[:200]}...")

    # Example 2: Media workflow
    if "media" in workflows:
        print("\n🎬 Testing Media Workflow...")
        response = await moderator.chat(
            "Download and process https://youtube.com/watch?v=example as high quality MP3"
        )
        print(f"Response: {response[:200]}...")

    # Example 3: Two-agent conversation
    print("\n💬 Testing Two-Agent Conversation...")

    # Create two agents for conversation
    researcher = moderator.specialized_agents.get("assistant")
    if researcher:
        # Simple back-and-forth
        researcher.system_message = "You are a researcher. Ask questions and gather information."

        response1 = await researcher.chat("What are the latest trends in AI safety?")
        print(f"Researcher: {response1[:100]}...")

        # Could continue conversation with another agent

    print("\n✅ All examples completed!")


# 4. Integration with Your Existing Chat Interface


class WorkflowEnabledChat:
    """Chat interface with workflow capabilities"""

    def __init__(self):
        self.moderator = None
        self.workflows = {}
        self.is_initialized = False

    async def initialize(self):
        """Initialize the workflow system"""
        if not self.is_initialized:
            self.moderator, self.workflows = await setup_workflow_system()
            self.is_initialized = True

    async def chat(self, message: str) -> str:
        """Enhanced chat with workflow detection"""
        await self.initialize()

        # Check if this is a workflow request
        if self._detect_workflow_intent(message):
            # Use workflow-enabled moderator
            return await self.moderator.chat(message)
        else:
            # Use regular agent behavior
            assistant = self.moderator.specialized_agents.get("assistant")
            if assistant:
                return await assistant.chat(message)
            else:
                return await self.moderator.chat(message)

    def _detect_workflow_intent(self, message: str) -> bool:
        """Simple workflow intent detection"""
        workflow_keywords = [
            "search scrape ingest",
            "research and store",
            "find and save",
            "download and process",
            "youtube download",
            "get video",
            "workflow",
            "multi-step",
            "pipeline",
        ]

        content_lower = message.lower()
        return any(keyword in content_lower for keyword in workflow_keywords)

    async def list_workflows(self) -> str:
        """List available workflows"""
        await self.initialize()

        if not self.workflows:
            return "No workflows available. Check agent configuration."

        response = "🔄 **Available Workflows:**\n\n"
        for name, workflow in self.workflows.items():
            response += f"• **{name.title()}**: {len(workflow.nodes)} steps\n"

        response += "\n💡 Just describe what you want to do naturally!"
        return response


# 5. Example Usage in Your Application


async def example_application_usage():
    """Example of how to use workflows in your application"""

    # Initialize workflow-enabled chat
    chat = WorkflowEnabledChat()

    # Example conversations
    examples = [
        "Search scrape ingest information about climate change into research_db",
        "Download and convert https://youtube.com/watch?v=abc123 to MP3",
        "What workflows are available?",
        "How is quantum computing advancing?",  # Regular chat
    ]

    print("🎯 Example Application Usage:\n")

    for i, example in enumerate(examples, 1):
        print(f"👤 User: {example}")
        response = await chat.chat(example)
        print(f"🤖 Agent: {response[:150]}...\n")

        if i < len(examples):
            print("-" * 50)


# Main demo
if __name__ == "__main__":
    import asyncio

    print("🚀 Ambivo Agents Workflow Integration Demo\n")

    async def main():
        # Run quick examples
        await quick_workflow_examples()

        print("\n" + "=" * 60 + "\n")

        # Run application example
        await example_application_usage()

    asyncio.run(main())
