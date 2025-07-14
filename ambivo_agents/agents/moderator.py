# ambivo_agents/agents/moderator.py
"""
Complete ModeratorAgent with System Message, LLM Context, and Memory Preservation
Intelligent orchestrator that routes queries to specialized agents with full context preservation
"""

import asyncio
import json
import logging
import re
import time
import uuid
from dataclasses import dataclass
from datetime import datetime
from typing import Any, AsyncIterator, Dict, List, Optional, Union

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
        - Route to web_search for: "search", "find information", "look up", research queries
        - Route to youtube_download for: YouTube URLs, video/audio downloads
        - Route to media_editor for: video/audio processing, conversion, editing
        - Route to knowledge_base for: document storage, semantic search, Q&A
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
            enhanced_user_message = f"{user_message}\n\n**Formatting Instruction:** Please format your response using proper Markdown syntax with appropriate headers, bold text, code blocks, and lists for maximum readability."

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

            # Analyze intent with complete context
            intent_analysis = await self._analyze_query_intent(user_message, conversation_context)

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
                    response_content = primary_response.content
                else:
                    # Fallback with context preservation
                    if (
                        intent_analysis["primary_agent"] != "assistant"
                        and "assistant" in self.specialized_agents
                    ):
                        fallback_response = await self._route_to_agent_with_context(
                            "assistant", user_message, context, llm_context
                        )
                        response_content = fallback_response.content
                    else:
                        response_content = f"I encountered an error: {primary_response.error}"

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
                # Single agent processing with context
                async for chunk in self._route_to_agent_stream_with_context(
                    intent_analysis["primary_agent"], user_message, context, llm_context
                ):
                    yield chunk

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
