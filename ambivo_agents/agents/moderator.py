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
        FIXED: Constructor that properly handles system_message parameter
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
    - web_search: Finding information online, research queries, current events, fact-checking
    - knowledge_base: Document storage, retrieval, semantic search, document ingestion
    - knowledge_synthesis: Multi-source information synthesis for comprehensive answers
    - web_scraper: Extracting content from websites using scraping APIs
    - gather_agent: Conversational form filling with conditional logic and validation

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
            **kwargs, # Pass remaining kwargs to parent
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
        if "default_enabled_agents" in self.moderator_config:
            enabled = self.moderator_config["default_enabled_agents"].copy()
        else:
            enabled = []

            if self.capabilities.get("enable_knowledge_base", False):
                enabled.append("knowledge_base")
            enabled.append("knowledge_synthesis")
            if self.capabilities.get("enable_web_search", False):
                enabled.append("web_search")
            if self.capabilities.get("enable_web_scraping", False):
                enabled.append("web_scraper")

        if "assistant" not in enabled:
            enabled.append("assistant")

        self.logger.info(f"Enabled agents: {enabled}")
        return enabled

    def _is_agent_enabled(self, agent_type: str) -> bool:
        """Check if an agent type is enabled"""
        if agent_type in self.enabled_agents:
            return True

        if agent_type == "assistant":
            return True

        capability_map = {
            "knowledge_base": "enable_knowledge_base",
            "knowledge_synthesis": "enable_knowledge_synthesis",
            "web_search": "enable_web_search",
            "web_scraper": "enable_web_scraping",
        }

        capability_key = capability_map.get(agent_type)
        if capability_key and isinstance(capability_key, str):
            return self.capabilities.get(capability_key, False)

        return False

    def _initialize_specialized_agents(self):
        """Initialize specialized agents with SHARED memory and context"""

        # Import available agents
        from .assistant import AssistantAgent
        from .knowledge_base import KnowledgeBaseAgent
        from .knowledge_synthesis import KnowledgeSynthesisAgent
        from .web_scraper import WebScraperAgent
        from .web_search import WebSearchAgent

        GatherAgent = None
        try:
            from .gather_agent import GatherAgent
        except ImportError:
            self.logger.debug("GatherAgent not available")

        agent_classes = {
            "knowledge_base": KnowledgeBaseAgent,
            "knowledge_synthesis": KnowledgeSynthesisAgent,
            "web_search": WebSearchAgent,
            "web_scraper": WebScraperAgent,
            "gather_agent": GatherAgent,
            "assistant": AssistantAgent,
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

                # CRITICAL: Create agent with MODERATOR's session context
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

                    # CRITICAL: Override agent's context to match moderator
                    agent_instance.context.session_id = self.context.session_id
                    agent_instance.context.conversation_id = self.context.conversation_id
                    agent_instance.context.user_id = self.context.user_id
                    agent_instance.context.tenant_id = self.context.tenant_id

                    # CRITICAL: Replace agent's memory with moderator's memory for consistency
                    if self.memory:
                        agent_instance.memory = self.memory
                    agent_instance.llm_service = self.llm_service

                else:
                    # Fallback to direct instantiation
                    agent_instance = agent_class(
                        agent_id=f"{agent_type}_{self.agent_id}",
                        memory_manager=self.memory, # SHARED MEMORY
                        llm_service=self.llm_service, # SHARED LLM
                        user_id=self.context.user_id,
                        tenant_id=self.context.tenant_id,
                        session_id=self.context.session_id, # SAME SESSION
                        conversation_id=self.context.conversation_id, # SAME CONVERSATION
                        session_metadata={
                            "parent_moderator": self.agent_id,
                            "agent_type": agent_type,
                            "shared_context": True,
                        },
                    )

                self.specialized_agents[agent_type] = agent_instance
                self.logger.info(
                    f"Initialized {agent_type} with shared context (session: {self.context.session_id})"
                )

            except Exception as e:
                self.logger.error(f"Failed to initialize {agent_type} agent: {e}", exc_info=True)

                # Special handling for assistant agent failure
                if agent_type == "assistant":
                    self.logger.error(
                        "CRITICAL: Assistant agent initialization failed, creating minimal fallback"
                    )
                    try:
                        fallback_assistant = self._create_minimal_assistant_agent()
                        self.specialized_agents[agent_type] = fallback_assistant
                        self.logger.warning("Emergency fallback assistant created")
                    except Exception as fallback_error:
                        self.logger.error(f"Even fallback assistant failed: {fallback_error}", exc_info=True)

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
            "knowledge_synthesis": {
                "keywords": [
                    "synthesize",
                    "combine information",
                    "multiple sources",
                    "comprehensive answer",
                    "research thoroughly",
                ],
                "patterns": [
                    r"(?:synthesize|combine|gather)\s+(?:information|data|knowledge)",
                    r"(?:research|investigate)\s+(?:thoroughly|comprehensively)",
                    r"(?:get|provide)\s+(?:comprehensive|detailed)\s+(?:information|answer)",
                    r"(?:check|search)\s+(?:multiple|all)\s+sources",
                ],
                "indicators": [
                    "comprehensive",
                    "thorough",
                    "multiple",
                    "synthesis",
                    "detailed",
                ],
                "priority": 3,
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
                "priority": 3, # Lower priority but catches general requests
            },
        }

    def _fast_route_check(self, user_message: str) -> Optional[Dict[str, Any]]:
        """Deterministic fast-path routing for unambiguous patterns.

        Skips the LLM entirely when the user intent is obvious from the message.
        Returns None if no fast-path match, letting the LLM decide.
        """
        msg = user_message.lower()

        # Scraping: message contains "scrape" + URL
        if "scrape" in msg and ("http://" in msg or "https://" in msg) and "web_scraper" in self.specialized_agents:
            return {
                "primary_agent": "web_scraper",
                "confidence": 0.95,
                "requires_multiple_agents": False,
                "workflow_detected": False,
                "is_follow_up": False,
                "reasoning": "Fast-path: explicit scrape request with URL",
            }

        return None

    async def _analyze_query_intent(
        self, user_message: str, conversation_context: str = ""
    ) -> Dict[str, Any]:
        """Enhanced intent analysis with conversation context and system message support"""

        # Fast-path: deterministic routing for unambiguous patterns (skip LLM)
        fast_route = self._fast_route_check(user_message)
        if fast_route:
            return fast_route

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
        agent_descriptions = {
            "knowledge_base": "- knowledge_base: Document ingestion, semantic search, storage",
            "knowledge_synthesis": "- knowledge_synthesis: Multi-source research synthesis with quality assessment",
            "web_search": "- web_search: Web searches, finding information online",
            "web_scraper": "- web_scraper: Website content extraction via scraping APIs",
            "gather_agent": "- gather_agent: Conversational form filling with conditional logic",
            "assistant": "- assistant: General conversation, explanations",
        }
        for agent_type in available_agents_list:
            desc = agent_descriptions.get(agent_type)
            if desc:
                available_agents_desc.append(desc)

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
        - Route to web_search for: "search", "find information", "look up", research queries
        - Route to knowledge_base for: document storage, semantic search, Q&A, file ingestion to knowledge base
        - Route to knowledge_synthesis for: queries needing comprehensive multi-source answers or synthesis
        - Route to web_scraper for: data extraction from websites, crawling
        - Route to gather_agent for: form filling, questionnaires, data collection
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
        score_total = sum(agent_scores.values()) if agent_scores else 0
        confidence = (
            agent_scores.get(primary_agent, 0) / score_total if score_total > 0 else 0.5
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
        kb_score = agent_scores.get("knowledge_base", 0)

        # If knowledge base score is high, route there
        if kb_score > 0:
            return None  # Let normal routing handle it

        # Check for ambiguous ingestion without clear destination
        ambiguous_patterns = [
            r"ingest\s+.*\.(?:csv|json|txt)\s*$", # Just "ingest file.csv" with no destination
            r"(?:load|import)\s+.*\.(?:csv|json|txt)\s*$", # "load file.csv" with no destination
        ]

        if any(re.search(pattern, message_lower) for pattern in ambiguous_patterns):
            # No clear destination specified — ask the user for a KB name
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
                    "message": self._generate_ingestion_clarification(message),
                },
            }

        return None

    def _generate_ingestion_clarification(self, original_message: str) -> str:
        """Generate clarification message for ingestion commands."""
        return f"""I can help you ingest data, but I need clarification on the destination:

**Your request**: "{original_message}"

Please specify the knowledge base name:
- "ingest [file] into knowledge base [name]"

Which knowledge base would you like to ingest into?"""

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
            f"Enhanced fallback triggered for {primary_agent} (confidence: {confidence:.2f})"
        )

        # First try assistant agent if it's not the primary agent and it's available
        if (
            primary_agent != "assistant"
            and "assistant" in self.specialized_agents
            and confidence < 0.7
        ):

            self.logger.info("Trying assistant agent as first fallback")

            assistant_response = await self._route_to_agent_with_context(
                "assistant", user_message, context, llm_context
            )

            if assistant_response.success:
                return assistant_response.content

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
        return f"""**Unable to Process Request**

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

    def _should_trigger_enhanced_fallback(
        self, agent_response: str, user_message: str, intent_analysis: Dict[str, Any]
    ) -> bool:
        """Check if agent response suggests it couldn't handle the task properly"""

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
                        f"Retrieved {len(full_conversation_history)} messages for {agent_type}"
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
                    self.logger.warning(f"Syncing {agent_type} context with moderator")
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
                self.logger.info(f"Stored routing message in shared memory")

            # Process the message with the target agent
            response_message = await agent.process_message(agent_message, execution_context)

            # Ensure response is stored in shared memory with consistent session info
            if self.memory and response_message:
                if (
                    response_message.session_id != session_id
                    or response_message.conversation_id != conversation_id
                ):

                    self.logger.info(f"Correcting response session info for continuity")

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
                    self.logger.info(f"Stored corrected {agent_type} response in shared memory")
                else:
                    response_message.metadata.update(
                        {
                            "stored_by_moderator": True,
                            "agent_type": agent_type,
                            "context_preserved": True,
                        }
                    )
                    self.logger.info(
                        f"{agent_type} response properly stored with correct session info"
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
            self.logger.error(f"Error routing to {agent_type} agent: {e}")
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
                f"Correcting message session ID: {message.session_id} → {self.context.session_id}"
            )
            message.session_id = self.context.session_id

        if message.conversation_id != self.context.conversation_id:
            self.logger.info(
                f"Correcting message conversation ID: {message.conversation_id} → {self.context.conversation_id}"
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
                        f"Moderator retrieved {len(conversation_history)} messages for analysis"
                    )

                except Exception as e:
                    self.logger.warning(f"Could not get conversation history: {e}")

            # Check if assigned skills should handle this request BEFORE agent routing
            skill_result = await self._should_use_assigned_skills(user_message)

            if skill_result.get("should_use_skills"):
                self.logger.info(
                    f"ModeratorAgent using assigned skill: {skill_result['used_skill']}"
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

                    self.logger.info(f"ModeratorAgent skill response completed successfully")
                    return response
                else:
                    # Skill execution failed, continue with normal routing but add context
                    self.logger.warning(
                        f"Assigned skill failed: {execution_result.get('error')}, falling back to agent routing"
                    )
                    # Don't modify user_message here - let normal routing handle it

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
                self.logger.info(f"Stored moderator response in shared memory")

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
        response_parts = ["**Multi-Agent Analysis Results**\n\n"]

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

        response_parts = [f"**Multi-Step Workflow Completed** ({len(workflow_results)} steps"]
        if failed_agents:
            response_parts[0] += f", {len(failed_agents)} failed"
        response_parts[0] += ")\n\n"

        for result in workflow_results:
            status_emoji = "[OK]" if result["success"] else "[FAIL]"
            context_emoji = "[CTX]" if result.get("context_preserved") else "[WARN]"

            response_parts.append(
                f"**Step {result['step']} - {result['agent'].replace('_', ' ').title()}:** {status_emoji} {context_emoji}\n"
            )
            response_parts.append(f"{result['content']}\n\n")
            response_parts.append("-" * 50 + "\n\n")

        if failed_agents:
            response_parts.append(
                f"\n**Note:** Some agents failed: {', '.join(set(failed_agents))}"
            )

        response_parts.append(f"\n**Context preserved throughout workflow**")

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
                    yield StreamChunk(
                        text="**Sequential Workflow Coordination...**\n\n",
                        sub_type=StreamSubType.STATUS,
                        metadata={"phase": "coordination"},
                    )
                else:
                    yield StreamChunk(
                        text="**Parallel Agent Coordination...**\n\n",
                        sub_type=StreamSubType.STATUS,
                        metadata={"phase": "coordination"},
                    )
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
                    self.logger.warning(f"Primary agent streaming failed: {e}")
                    yield StreamChunk(
                        text=f"Error: {str(e)}",
                        sub_type=StreamSubType.ERROR,
                        metadata={"error": str(e)},
                    )

            # PHASE 4: Completion newline
            yield StreamChunk(
                text="\n",
                sub_type=StreamSubType.STATUS,
                metadata={"phase": "complete"},
            )

        except Exception as e:
            self.logger.error(f"ModeratorAgent streaming error: {e}")
            yield StreamChunk(
                text=f"\n\n**Error:** {str(e)}",
                sub_type=StreamSubType.ERROR,
                metadata={"error": str(e)},
            )

    async def _route_to_agent_stream_with_context(
        self,
        agent_type: str,
        user_message: str,
        context: ExecutionContext = None,
        llm_context: Dict[str, Any] = None,
    ) -> AsyncIterator[StreamChunk]:
        """Stream routing to a specific agent with context preservation"""
        if agent_type not in self.specialized_agents:
            yield StreamChunk(
                text=f"Agent {agent_type} not available",
                sub_type=StreamSubType.ERROR,
                metadata={"error": "agent_unavailable", "agent_type": agent_type},
            )
            return

        try:
            agent = self.specialized_agents[agent_type]

            if hasattr(agent, "process_message_stream"):
                agent_message = AgentMessage(
                    id=str(uuid.uuid4()),
                    sender_id=self.context.user_id,
                    recipient_id=agent.agent_id,
                    content=user_message,
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
                    text=f"{agent_type} doesn't support streaming, using standard processing...\n\n",
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
                text=f"Error routing to {agent_type}: {str(e)}",
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
                    text=f"**Agent {i}: {agent_type.replace('_', ' ').title()}**\n",
                    sub_type=StreamSubType.STATUS,
                    metadata={"agent_sequence": i, "agent_type": agent_type},
                )
                yield StreamChunk(
                    text="-" * 50 + "\n",
                    sub_type=StreamSubType.STATUS,
                    metadata={"separator": True},
                )

                async for chunk in self._route_to_agent_stream_with_context(
                    agent_type, user_message, context, llm_context
                ):
                    yield chunk

                yield StreamChunk(
                    text="\n" + "-" * 50 + "\n\n",
                    sub_type=StreamSubType.STATUS,
                    metadata={"separator": True, "agent_completed": agent_type},
                )
                successful_responses += 1
                await asyncio.sleep(0.1)

            except Exception as e:
                yield StreamChunk(
                    text=f"Error with {agent_type}: {str(e)}\n\n",
                    sub_type=StreamSubType.ERROR,
                    metadata={"agent_type": agent_type, "error": str(e)},
                )

        yield StreamChunk(
            text=f"{successful_responses}/{len(agents)} agents completed with context preserved",
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


