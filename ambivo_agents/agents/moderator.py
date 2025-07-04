# ambivo_agents/agents/moderator.py
"""
ModeratorAgent: Complete intelligent orchestrator that routes queries to specialized agents
FIXED VERSION - All methods implemented correctly
"""

import asyncio
import json
import re
import uuid
import time
import logging
from typing import Dict, List, Any, Optional, Union, AsyncIterator
from datetime import datetime
from dataclasses import dataclass

from ..core.base import BaseAgent, AgentRole, AgentMessage, MessageType, ExecutionContext
from ..config.loader import load_config, get_config_section
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
    Complete moderator agent that intelligently routes queries to specialized agents
    Users only interact with this agent, which handles everything behind the scenes
    """

    def __init__(self, agent_id: str = None, memory_manager=None, llm_service=None,
                 enabled_agents: List[str] = None, **kwargs):
        if agent_id is None:
            agent_id = f"moderator_{str(uuid.uuid4())[:8]}"

        super().__init__(
            agent_id=agent_id,
            role=AgentRole.COORDINATOR,
            memory_manager=memory_manager,
            llm_service=llm_service,
            name="Moderator Agent",
            description="Intelligent orchestrator that routes queries to specialized agents",
            **kwargs
        )

        # Initialize history mixin
        self.setup_history_mixin()

        # Load configuration
        self.config = load_config()
        self.capabilities = self.config.get('agent_capabilities', {})
        self.moderator_config = self.config.get('moderator', {})

        # Initialize available agents based on config and enabled list
        self.enabled_agents = enabled_agents or self._get_default_enabled_agents()
        self.specialized_agents = {}
        self.agent_routing_patterns = {}


        # Setup routing intelligence
        self._setup_routing_patterns()

        logging.info(f"ModeratorAgent initialized with agents: {list(self.specialized_agents.keys())}")


    def _get_default_enabled_agents(self) -> List[str]:
        """Get default enabled agents from configuration"""
        # Check moderator config first
        if 'default_enabled_agents' in self.moderator_config:
            return self.moderator_config['default_enabled_agents']

        # Otherwise check capabilities config
        enabled = []

        if self.capabilities.get('enable_knowledge_base', False):
            enabled.append('knowledge_base')
        if self.capabilities.get('enable_web_search', False):
            enabled.append('web_search')
        if self.capabilities.get('enable_code_execution', False):
            enabled.append('code_executor')
        if self.capabilities.get('enable_media_editor', False):
            enabled.append('media_editor')
        if self.capabilities.get('enable_youtube_download', False):
            enabled.append('youtube_download')
        if self.capabilities.get('enable_web_scraping', False):
            enabled.append('web_scraper')

        # Always include assistant for general queries
        enabled.append('assistant')

        return enabled

    def _is_agent_enabled(self, agent_type: str) -> bool:
        """Check if an agent type is enabled"""
        if agent_type in self.enabled_agents:
            return True

        # Double-check against capabilities config
        capability_map = {
            'knowledge_base': 'enable_knowledge_base',
            'web_search': 'enable_web_search',
            'code_executor': 'enable_code_execution',
            'media_editor': 'enable_media_editor',
            'youtube_download': 'enable_youtube_download',
            'web_scraper': 'enable_web_scraping',
            'assistant': True  # Always enabled
        }

        if agent_type == 'assistant':
            return True

        capability_key = capability_map.get(agent_type)
        if capability_key and isinstance(capability_key, str):
            return self.capabilities.get(capability_key, False)

        return False

    def _get_agent_config(self, agent_type: str) -> Dict[str, Any]:
        """Get configuration for specific agent type"""
        agent_config = {}

        if agent_type == 'knowledge_base':
            agent_config = self.config.get('knowledge_base', {})
        elif agent_type == 'web_search':
            agent_config = self.config.get('web_search', {})
        elif agent_type == 'media_editor':
            agent_config = self.config.get('media_editor', {})
        elif agent_type == 'youtube_download':
            agent_config = self.config.get('youtube_download', {})
        elif agent_type == 'web_scraper':
            agent_config = self.config.get('web_scraping', {})
        elif agent_type == 'code_executor':
            agent_config = self.config.get('docker', {})

        return agent_config

    def _initialize_specialized_agents(self):
        """Initialize all enabled specialized agents"""
        # Import agents dynamically to avoid circular imports
        try:
            from . import (
                KnowledgeBaseAgent, WebSearchAgent, CodeExecutorAgent,
                MediaEditorAgent, YouTubeDownloadAgent, WebScraperAgent, AssistantAgent
            )
        except ImportError:
            # Fallback individual imports
            try:
                from .knowledge_base import KnowledgeBaseAgent
            except ImportError:
                KnowledgeBaseAgent = None
            try:
                from .web_search import WebSearchAgent
            except ImportError:
                WebSearchAgent = None
            try:
                from .code_executor import CodeExecutorAgent
            except ImportError:
                CodeExecutorAgent = None
            try:
                from .media_editor import MediaEditorAgent
            except ImportError:
                MediaEditorAgent = None
            try:
                from .youtube_download import YouTubeDownloadAgent
            except ImportError:
                YouTubeDownloadAgent = None
            try:
                from .web_scraper import WebScraperAgent
            except ImportError:
                WebScraperAgent = None
            try:
                from .assistant import AssistantAgent
            except ImportError:
                AssistantAgent = None

        agent_classes = {
            'knowledge_base': KnowledgeBaseAgent,
            'web_search': WebSearchAgent,
            'code_executor': CodeExecutorAgent,
            'media_editor': MediaEditorAgent,
            'youtube_download': YouTubeDownloadAgent,
            'web_scraper': WebScraperAgent,
            'assistant': AssistantAgent
        }

        for agent_type in self.enabled_agents:
            if not self._is_agent_enabled(agent_type):
                continue

            agent_class = agent_classes.get(agent_type)
            if agent_class is None:
                logging.warning(f"Agent class for {agent_type} not available")
                continue

            try:
                # Create agent with shared context
                agent_instance = agent_class.create_simple(
                    user_id=self.context.user_id,
                    tenant_id=self.context.tenant_id,
                    session_metadata={
                        'parent_moderator': self.agent_id,
                        'agent_type': agent_type
                    }
                )
                self.specialized_agents[agent_type] = agent_instance
                logging.info(f"Initialized {agent_type} agent: {agent_instance.agent_id}")

            except Exception as e:
                logging.error(f"Failed to initialize {agent_type} agent: {e}")

    def _setup_routing_patterns(self):
        """Setup intelligent routing patterns for different query types"""
        self.agent_routing_patterns = {
            'code_executor': {
                'keywords': ['run code', 'execute python', 'run script', 'code execution',
                             'write code', 'create code', 'python code', 'bash script',
                             'write a script', 'code to', 'program to',
                             # ADDED: Context reference keywords
                             'show code', 'that code', 'the code', 'previous code',
                             'code again', 'show me that', 'display code', 'see code'],
                'patterns': [r'(?:run|execute|write|create|show)\s+(?:code|script|python|program)',
                             r'code\s+to\s+\w+', r'write.*(?:function|script|program)',
                             r'```(?:python|bash)', r'can\s+you\s+(?:write|create).*code',
                             # ADDED: Context reference patterns
                             r'(?:show|display|see)\s+(?:me\s+)?(?:that\s+|the\s+)?code',
                             r'code\s+again', r'(?:previous|last|that)\s+code',
                             r'show\s+me\s+that'],
                'indicators': ['```', 'def ', 'import ', 'python', 'bash', 'function', 'script', 'code'],
                'priority': 1
            },

            'youtube_download': {
                'keywords': ['download youtube', 'youtube video', 'download video', 'get from youtube'],
                'patterns': [r'download\s+(?:from\s+)?youtube', r'youtube\.com/watch', r'youtu\.be/',
                             r'get\s+(?:video|audio)\s+from\s+youtube'],
                'indicators': ['youtube.com', 'youtu.be', 'download video', 'download audio'],
                'priority': 1
            },

            'media_editor': {
                'keywords': ['convert video', 'edit media', 'extract audio', 'resize video',
                             'media processing', 'ffmpeg'],
                'patterns': [r'convert\s+(?:video|audio)', r'extract\s+audio', r'resize\s+video',
                             r'trim\s+(?:video|audio)', r'media\s+(?:processing|editing)'],
                'indicators': ['.mp4', '.avi', '.mp3', '.wav', 'video', 'audio'],
                'priority': 1
            },

            'knowledge_base': {
                'keywords': ['search knowledge', 'query kb', 'knowledge base', 'find in documents',
                             'search documents', 'ingest document', 'add to kb'],
                'patterns': [r'(?:search|query|ingest|add)\s+(?:in\s+)?(?:kb|knowledge|documents?)',
                             r'find\s+(?:in\s+)?(?:my\s+)?(?:files|documents?)'],
                'indicators': ['kb_name', 'collection_table', 'document', 'file', 'ingest', 'query'],
                'priority': 2
            },

            'web_search': {
                'keywords': ['search web', 'google', 'find online', 'search for', 'look up',
                             'search internet', 'web search', 'find information'],
                'patterns': [r'search\s+(?:the\s+)?(?:web|internet|online)',
                             r'(?:google|look\s+up|find)\s+(?:information\s+)?(?:about|on)',
                             r'what\'s\s+happening\s+with', r'latest\s+news'],
                'indicators': ['search', 'web', 'online', 'internet', 'news'],
                'priority': 2
            },

            'web_scraper': {
                'keywords': ['scrape website', 'extract from site', 'crawl web', 'scrape data'],
                'patterns': [r'scrape\s+(?:website|site|web)', r'extract\s+(?:data\s+)?from\s+(?:website|site)',
                             r'crawl\s+(?:website|web)'],
                'indicators': ['scrape', 'crawl', 'extract data', 'website'],
                'priority': 2
            },

            'assistant': {
                'keywords': ['help', 'explain', 'how to', 'what is', 'tell me', 'can you', 'please'],
                'patterns': [r'(?:help|explain|tell)\s+me', r'what\s+is', r'how\s+(?:do\s+)?(?:I|to)',
                             r'can\s+you\s+(?:help|explain|tell|show)', r'please\s+(?:help|explain)'],
                'indicators': ['help', 'explain', 'question', 'general', 'can you', 'please'],
                'priority': 3  # Lower priority but should catch general requests
            }
        }

    async def _analyze_query_intent(self, user_message: str, conversation_context: str = "") -> Dict[str, Any]:
        """Enhanced intent analysis with better multi-agent detection"""

        # Try LLM analysis first
        if self.llm_service:
            try:
                return await self._llm_analyze_intent(user_message, conversation_context)
            except Exception as e:
                logging.warning(f"LLM analysis failed: {e}, falling back to keyword analysis")

        # Enhanced keyword analysis with multi-agent scenarios
        return self._keyword_based_analysis(user_message, conversation_context)

    # LLM-based context resolution methods

    async def _resolve_context_and_route(self, user_message: str, context_refs: List[str],
                                         context: ExecutionContext) -> str:
        """Use LLM to resolve context references and route appropriately"""

        if not self.llm_service:
            return await self._route_to_agent('assistant', user_message, context)

        # Get comprehensive context for LLM
        conversation_history = self._get_conversation_context_summary()
        session_context = self._get_session_context()

        resolution_prompt = f"""
        The user is making a request that references previous context. Help resolve what they're referring to and determine the appropriate action.

        User message: {user_message}
        Detected context references: {context_refs}

        Session context: {session_context}
        Recent conversation: {conversation_history}

        Based on the context, determine:
        1. What specifically the user is referring to
        2. What action they want to take
        3. Which agent should handle this request
        4. What additional context should be passed to the agent

        Available agents: code_executor, youtube_download, media_editor, knowledge_base, web_search, web_scraper, assistant

        Respond in JSON format:
        {{
            "resolved_reference": "what the user is referring to",
            "intended_action": "what the user wants to do",
            "target_agent": "agent_name", 
            "enriched_request": "complete request with resolved context",
            "confidence": 0.0-1.0
        }}
        """

        try:
            response = await self.llm_service.generate_response(resolution_prompt)
            import re
            json_match = re.search(r'\{.*\}', response, re.DOTALL)

            if json_match:
                resolution = json.loads(json_match.group())

                target_agent = resolution.get('target_agent', 'assistant')
                enriched_request = resolution.get('enriched_request', user_message)

                if target_agent in self.specialized_agents:
                    agent_response = await self._route_to_agent(target_agent, enriched_request, context)
                    return agent_response.content if hasattr(agent_response, 'content') else str(agent_response)
                else:
                    return f"Based on your reference to '{resolution.get('resolved_reference')}', I understand you want to {resolution.get('intended_action')}. However, the agent '{target_agent}' is not available."

        except Exception as e:
            logging.error(f"Context resolution failed: {e}")

        # Fallback to assistant
        return await self._route_to_agent('assistant', user_message, context)

    async def _elaborate_on_previous(self, user_message: str, session_context: Dict[str, Any]) -> str:
        """Elaborate on previous results using LLM analysis"""

        last_operation = self.memory.get_context('last_operation') if self.memory else {}

        if not last_operation or not self.llm_service:
            return "I'd be happy to provide more details. What specific aspect would you like me to elaborate on?"

        elaboration_prompt = f"""
        The user is asking for more details about a previous response.

        Previous operation: {last_operation.get('agent_used')} handled: {last_operation.get('user_request', '')}
        Previous response: {last_operation.get('response_preview', '')}

        User's request for elaboration: {user_message}

        Provide a detailed elaboration that addresses their specific request for more information.
        """

        try:
            elaboration = await self.llm_service.generate_response(elaboration_prompt)
            return elaboration

        except Exception as e:
            return f"I'd like to elaborate on the previous result, but encountered an error: {e}"

    async def _handle_additional_task(self, user_message: str, session_context: Dict[str, Any],
                                      intent_analysis: Dict[str, Any]) -> str:
        """Handle additional tasks related to previous operations"""

        last_operation = self.memory.get_context('last_operation') if self.memory else {}

        if not last_operation:
            # Treat as new request
            primary_agent = intent_analysis.get('primary_agent', 'assistant')
            return await self._route_to_agent(primary_agent, user_message, None)

        # Use LLM to determine if this should be a new workflow or extension
        if self.llm_service:
            workflow_prompt = f"""
            The user has completed this operation: {last_operation.get('user_request', '')}
            Using agent: {last_operation.get('agent_used', '')}

            Now they want: {user_message}

            Should this be:
            1. A new independent task
            2. An extension of the previous workflow  
            3. A related task that should use the previous result

            Respond with: "independent", "extension", or "related"
            """

            try:
                task_type = await self.llm_service.generate_response(workflow_prompt)
                task_type = task_type.strip().lower()

                if task_type == "extension":
                    # Add to existing workflow
                    agent_chain = intent_analysis.get('agent_chain', [intent_analysis.get('primary_agent')])
                    return await self._coordinate_sequential_workflow(agent_chain, user_message, None)

                elif task_type == "related":
                    # Pass previous context to new agent
                    enriched_message = f"""
                    Previous operation context: {last_operation.get('response_preview', '')}

                    New request: {user_message}
                    """
                    primary_agent = intent_analysis.get('primary_agent', 'assistant')
                    return await self._route_to_agent(primary_agent, enriched_message, None)

            except Exception as e:
                logging.error(f"Task type analysis failed: {e}")

        # Fallback: treat as independent task
        primary_agent = intent_analysis.get('primary_agent', 'assistant')
        return await self._route_to_agent(primary_agent, user_message, None)

    # ambivo_agents/agents/moderator.py - FIXED intent detection and routing

    def _keyword_based_analysis(self, user_message: str, conversation_context: str = "") -> Dict[str, Any]:
        """ENHANCED: Better keyword analysis with improved code and search detection"""
        message_lower = user_message.lower()

        # ENHANCED: Better code detection patterns
        code_indicators = [
            'write code', 'create code', 'generate code', 'code to', 'program to',
            'function to', 'script to', 'write python', 'create python',
            'then execute', 'and run', 'execute it', 'run it', 'show results',
            'write and execute', 'code and run', 'multiply', 'calculate', 'algorithm'
        ]

        # ENHANCED: Better web search detection
        search_indicators = [
            'search web', 'search for', 'find online', 'look up', 'google',
            'search the web', 'web search', 'find information', 'search about'
        ]

        # ENHANCED: YouTube detection
        youtube_indicators = [
            'youtube', 'youtu.be', 'download video', 'download audio',
            'youtube.com', 'get from youtube'
        ]

        # Detect workflows
        workflow_patterns = {
            'write_and_execute_code': {
                'keywords': code_indicators,
                'agents': ['code_executor'],
                'workflow_type': 'sequential',
                'priority': 1
            },
            'web_search': {
                'keywords': search_indicators,
                'agents': ['web_search'],
                'workflow_type': 'single',
                'priority': 1
            },
            'youtube_download': {
                'keywords': youtube_indicators,
                'agents': ['youtube_download'],
                'workflow_type': 'single',
                'priority': 1
            }
        }

        # Check for workflows first (higher priority)
        for workflow_name, pattern in workflow_patterns.items():
            if any(keyword in message_lower for keyword in pattern['keywords']):
                available_agents = [agent for agent in pattern['agents']
                                    if agent in self.specialized_agents]

                if available_agents:
                    return {
                        'primary_agent': available_agents[0],
                        'confidence': 0.9,  # High confidence for keyword matches
                        'requires_multiple_agents': len(available_agents) > 1,
                        'workflow_detected': pattern['workflow_type'] == 'sequential',
                        'workflow_type': pattern['workflow_type'],
                        'agent_chain': available_agents,
                        'is_follow_up': False,
                        'reasoning': f"Detected workflow: {workflow_name} (keyword match)"
                    }

        # ENHANCED: Force code execution for obvious code requests
        if self._is_obvious_code_request(user_message):
            if 'code_executor' in self.specialized_agents:
                return {
                    'primary_agent': 'code_executor',
                    'confidence': 0.95,
                    'requires_multiple_agents': False,
                    'workflow_detected': False,
                    'is_follow_up': False,
                    'reasoning': 'Forced routing to code_executor for obvious code request'
                }

        # ENHANCED: Force web search for obvious search requests
        if self._is_obvious_search_request(user_message):
            if 'web_search' in self.specialized_agents:
                return {
                    'primary_agent': 'web_search',
                    'confidence': 0.95,
                    'requires_multiple_agents': False,
                    'workflow_detected': False,
                    'is_follow_up': False,
                    'reasoning': 'Forced routing to web_search for search request'
                }

        # Continue with existing single agent analysis...
        agent_scores = {}
        for agent_type, patterns in self.agent_routing_patterns.items():
            if agent_type not in self.specialized_agents:
                continue

            score = 0
            score += sum(3 for keyword in patterns['keywords'] if keyword in message_lower)
            score += sum(5 for pattern in patterns['patterns'] if re.search(pattern, message_lower))
            score += sum(2 for indicator in patterns['indicators'] if indicator in message_lower)

            agent_scores[agent_type] = score

        primary_agent = max(agent_scores.items(), key=lambda x: x[1])[0] if agent_scores else 'assistant'
        confidence = agent_scores.get(primary_agent, 0) / sum(agent_scores.values()) if agent_scores else 0.5

        return {
            'primary_agent': primary_agent,
            'confidence': max(confidence, 0.5),
            'requires_multiple_agents': False,
            'workflow_detected': False,
            'is_follow_up': False,
            'agent_scores': agent_scores,
            'reasoning': f"Single agent routing to {primary_agent}"
        }

    def _is_obvious_code_request(self, user_message: str) -> bool:
        """Detect obvious code execution requests"""
        message_lower = user_message.lower()

        # Strong code execution indicators
        strong_indicators = [
            ('write code', ['execute', 'run', 'show', 'result']),
            ('create code', ['execute', 'run', 'show', 'result']),
            ('code to', ['execute', 'run', 'then', 'and']),
            ('then execute', []),
            ('and run', ['code', 'script', 'program']),
            ('execute it', []),
            ('run it', []),
            ('show results', ['code', 'execution']),
            ('write and execute', []),
            ('code and run', [])
        ]

        for main_phrase, context_words in strong_indicators:
            if main_phrase in message_lower:
                if not context_words:  # No context needed
                    return True
                if any(ctx in message_lower for ctx in context_words):
                    return True

        # Mathematical operations often indicate code requests
        math_with_execution = [
            'multiply', 'calculate', 'add', 'subtract', 'divide'
        ]
        execution_words = ['execute', 'run', 'show', 'result', 'output']

        has_math = any(word in message_lower for word in math_with_execution)
        has_execution = any(word in message_lower for word in execution_words)

        if has_math and has_execution:
            return True

        return False

    def _is_obvious_search_request(self, user_message: str) -> bool:
        """Detect obvious web search requests"""
        message_lower = user_message.lower()

        # Strong search indicators
        search_patterns = [
            r'search\s+(?:the\s+)?web\s+for',
            r'search\s+for.*(?:online|web)',
            r'find.*(?:online|web|internet)',
            r'look\s+up.*(?:online|web)',
            r'google\s+(?:for\s+)?',
            r'web\s+search\s+for',
            r'search\s+(?:about|for)\s+\w+'
        ]

        for pattern in search_patterns:
            if re.search(pattern, message_lower):
                return True

        # Check for search + provide results pattern
        if 'search' in message_lower and any(word in message_lower for word in ['provide', 'show', 'give', 'results']):
            return True

        return False

    async def _llm_analyze_intent(self, user_message: str, conversation_context: str = "") -> Dict[str, Any]:
        """ENHANCED: LLM analysis with better agent detection"""
        if not self.llm_service:
            return self._keyword_based_analysis(user_message, conversation_context)

        # Get session context for workflow continuity
        session_context = self._get_session_context() if hasattr(self, '_get_session_context') else {}

        # Build available agents list dynamically
        available_agents_list = list(self.specialized_agents.keys())
        available_agents_desc = []
        for agent_type in available_agents_list:
            if agent_type == 'code_executor':
                available_agents_desc.append(
                    "- code_executor: PROGRAMMING TASKS - Writing code, execution, debugging, mathematical calculations")
            elif agent_type == 'web_search':
                available_agents_desc.append(
                    "- web_search: WEB SEARCHES - Finding information online, researching topics")
            elif agent_type == 'youtube_download':
                available_agents_desc.append("- youtube_download: YouTube video/audio downloads")
            elif agent_type == 'media_editor':
                available_agents_desc.append("- media_editor: FFmpeg media processing, video/audio conversion")
            elif agent_type == 'knowledge_base':
                available_agents_desc.append("- knowledge_base: Document ingestion, semantic search, storage")
            elif agent_type == 'web_scraper':
                available_agents_desc.append("- web_scraper: Website data extraction, crawling")
            elif agent_type == 'assistant':
                available_agents_desc.append("- assistant: General conversation, explanations")

        prompt = f"""
        Analyze this user message to determine the correct agent to handle it.

        Available agents in this session:
        {chr(10).join(available_agents_desc)}

        Current User Message: {user_message}

        CRITICAL RULES:
        1. If user asks to "write code" AND "execute/run" it → use code_executor
        2. If user asks to "search web/online" for something → use web_search  
        3. If user mentions YouTube URLs or downloading → use youtube_download
        4. Mathematical calculations that need code → use code_executor
        5. General questions without execution → use assistant

        Examples:
        - "write code to multiply 3 numbers then execute it" → code_executor
        - "search the web for ambivo" → web_search
        - "download https://youtube.com/watch?v=abc" → youtube_download
        - "what is the capital of France?" → assistant

        Respond in JSON format:
        {{
            "primary_agent": "agent_name",
            "confidence": 0.0-1.0,
            "reasoning": "detailed analysis explaining why this agent was chosen",
            "requires_multiple_agents": false,
            "workflow_detected": false,
            "workflow_type": "single",
            "agent_chain": ["agent_name"],
            "is_follow_up": false
        }}
        """

        try:
            response = await self.llm_service.generate_response(prompt)
            import re
            json_match = re.search(r'\{.*\}', response, re.DOTALL)
            if json_match:
                analysis = json.loads(json_match.group())

                # Ensure primary agent is available
                primary_agent = analysis.get('primary_agent')
                if primary_agent not in self.specialized_agents:
                    # Fallback to keyword analysis
                    return self._keyword_based_analysis(user_message, conversation_context)

                return analysis
            else:
                # Fallback if no JSON
                return self._keyword_based_analysis(user_message, conversation_context)

        except Exception as e:
            logging.error(f"LLM workflow analysis failed: {e}")
            return self._keyword_based_analysis(user_message, conversation_context)
    async def _coordinate_multiple_agents_enhanced(self, agents: List[str], user_message: str,
                                                   context: ExecutionContext = None,
                                                   workflow_type: str = "sequential") -> str:
        """Enhanced coordination with workflow awareness"""

        if workflow_type == "parallel":
            # Run truly independent agents in parallel
            return await self._coordinate_parallel_agents(agents, user_message, context)
        else:
            # Run sequential workflow where later agents use earlier results
            return await self._coordinate_sequential_workflow(agents, user_message, context)


    async def _coordinate_parallel_agents(self, agents: List[str], user_message: str,
                                          context: ExecutionContext = None) -> str:
        """Run independent agents in parallel for faster processing"""

        # Execute agents concurrently
        tasks = [self._route_to_agent(agent_type, user_message, context) for agent_type in agents]
        agent_responses = await asyncio.gather(*tasks, return_exceptions=True)

        successful_responses = []
        for response in agent_responses:
            if isinstance(response, AgentResponse) and response.success:
                successful_responses.append(response)

        if not successful_responses:
            return "I wasn't able to process your request with any of the available agents."

        # Combine parallel results
        if len(successful_responses) == 1:
            return successful_responses[0].content

        combined_response = "🔀 **Multi-Agent Analysis Results**\n\n"

        for i, response in enumerate(successful_responses, 1):
            combined_response += f"**{i}. {response.agent_type.replace('_', ' ').title()}:**\n"
            combined_response += f"{response.content}\n\n"

        return combined_response.strip()

    # 🔧 EXAMPLE ENHANCED USAGE SCENARIOS:

    def _detect_workflow_scenarios(self, user_message: str) -> Dict[str, Any]:
        """Detect specific workflow scenarios that benefit from multi-agent coordination"""

        scenarios = {
            # Research workflows
            "research_and_save": {
                "triggers": ["research and save", "find and store", "search and add to kb"],
                "agents": ["web_search", "knowledge_base"],
                "workflow": "sequential",
                "description": "Research online then save findings to knowledge base"
            },

            # Content creation workflows
            "download_and_convert": {
                "triggers": ["download and convert", "get youtube and extract audio", "youtube to mp3"],
                "agents": ["youtube_download", "media_editor"],
                "workflow": "sequential",
                "description": "Download YouTube content then convert/process it"
            },

            # Analysis workflows
            "scrape_and_analyze": {
                "triggers": ["scrape and analyze", "extract data and search", "crawl and query"],
                "agents": ["web_scraper", "knowledge_base"],
                "workflow": "sequential",
                "description": "Scrape web data then analyze with knowledge base"
            },

            # Comparison workflows
            "multi_source_research": {
                "triggers": ["compare sources", "research from multiple", "find different perspectives"],
                "agents": ["web_search", "knowledge_base", "web_scraper"],
                "workflow": "parallel",
                "description": "Research from multiple independent sources"
            },

            # Development workflows
            "code_and_test": {
                "triggers": ["write and test", "create and execute", "code and run"],
                "agents": ["code_executor"],  # Single agent but clear workflow intent
                "workflow": "sequential",
                "description": "Write code and immediately test it"
            }
        }

        message_lower = user_message.lower()

        for scenario_name, scenario in scenarios.items():
            for trigger in scenario["triggers"]:
                if trigger in message_lower:
                    return {
                        "scenario": scenario_name,
                        "agents": scenario["agents"],
                        "workflow_type": scenario["workflow"],
                        "description": scenario["description"],
                        "detected": True
                    }

        return {"detected": False}

    # Enhanced agent chain validation in _llm_analyze_intent
    async def _llm_analyze_intent(self, user_message: str, conversation_context: str = "") -> Dict[str, Any]:
        """Use LLM to analyze user intent and determine multi-agent workflow requirements"""
        if not self.llm_service:
            return self._keyword_based_analysis(user_message, conversation_context)

        # Get session context for workflow continuity
        session_context = self._get_session_context() if hasattr(self, '_get_session_context') else {}

        # Build available agents list dynamically
        available_agents_list = list(self.specialized_agents.keys())
        available_agents_desc = []
        for agent_type in available_agents_list:
            if agent_type == 'code_executor':
                available_agents_desc.append("- code_executor: Code writing, execution, debugging, programming tasks")
            elif agent_type == 'youtube_download':
                available_agents_desc.append("- youtube_download: YouTube video/audio downloads")
            elif agent_type == 'media_editor':
                available_agents_desc.append("- media_editor: FFmpeg media processing, video/audio conversion")
            elif agent_type == 'knowledge_base':
                available_agents_desc.append("- knowledge_base: Document ingestion, semantic search, storage")
            elif agent_type == 'web_search':
                available_agents_desc.append("- web_search: Web searches, finding information online")
            elif agent_type == 'web_scraper':
                available_agents_desc.append("- web_scraper: Website data extraction, crawling")
            elif agent_type == 'assistant':
                available_agents_desc.append("- assistant: General conversation, explanations")

        prompt = f"""
        Analyze this user message to determine if it requires single or multiple agents and detect workflow patterns.

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

        IMPORTANT: Only suggest agents that are actually available in this session.

        Respond in JSON format:
        {{
            "primary_agent": "agent_name",
            "confidence": 0.0-1.0,
            "reasoning": "detailed analysis",
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
            response = await self.llm_service.generate_response(prompt)
            import re
            json_match = re.search(r'\{.*\}', response, re.DOTALL)
            if json_match:
                analysis = json.loads(json_match.group())

                # Enhanced validation - only include available agents
                if analysis.get('workflow_detected', False):
                    suggested_chain = analysis.get('agent_chain', [])
                    # Filter to only include agents that are actually available and enabled
                    valid_chain = [
                        agent for agent in suggested_chain
                        if agent in self.specialized_agents
                    ]

                    # If LLM suggested unavailable agents, provide feedback
                    if len(valid_chain) != len(suggested_chain):
                        unavailable = [a for a in suggested_chain if a not in self.specialized_agents]
                        logging.warning(f"LLM suggested unavailable agents: {unavailable}")

                        # Fallback logic for missing agents
                        if 'web_search' in unavailable and 'knowledge_base' in self.specialized_agents:
                            # Substitute knowledge_base for web_search if available
                            valid_chain = [a if a != 'web_search' else 'knowledge_base' for a in valid_chain]
                        elif 'knowledge_base' in unavailable and 'web_search' in self.specialized_agents:
                            # Substitute web_search for knowledge_base if available
                            valid_chain = [a if a != 'knowledge_base' else 'web_search' for a in valid_chain]

                    analysis['agent_chain'] = valid_chain

                    # Adjust workflow detection based on available agents
                    if len(valid_chain) < 2:
                        analysis['workflow_detected'] = False
                        analysis['requires_multiple_agents'] = False

                # Ensure primary agent is available
                primary_agent = analysis.get('primary_agent')
                if primary_agent not in self.specialized_agents:
                    # Fallback to assistant or first available agent
                    analysis['primary_agent'] = 'assistant' if 'assistant' in self.specialized_agents else \
                    list(self.specialized_agents.keys())[0]
                    analysis['confidence'] = max(0.3, analysis.get('confidence', 0.5) - 0.2)

                # Add agent scores for compatibility
                agent_scores = {}
                if analysis.get('workflow_detected'):
                    for i, agent in enumerate(analysis.get('agent_chain', [])):
                        agent_scores[agent] = 10 - i  # Descending priority
                else:
                    primary = analysis.get('primary_agent')
                    if primary in self.specialized_agents:
                        agent_scores[primary] = 10

                analysis['agent_scores'] = agent_scores
                analysis['context_detected'] = bool(conversation_context)
                analysis['available_agents'] = available_agents_list

                return analysis
            else:
                raise ValueError("No valid JSON in LLM response")

        except Exception as e:
            logging.error(f"LLM workflow analysis failed: {e}")
            return self._keyword_based_analysis(user_message, conversation_context)
    # Update _route_with_llm_analysis to handle LLM-detected workflows
    async def _route_with_llm_analysis(self, intent_analysis: Dict[str, Any], user_message: str,
                                       context: ExecutionContext) -> str:
        """Route request based on LLM workflow analysis"""

        # Handle follow-up requests first
        if intent_analysis.get('is_follow_up', False):
            return await self._handle_follow_up_request(intent_analysis, user_message, context)

        # Handle multi-agent workflows
        if intent_analysis.get('workflow_detected', False):
            workflow_type = intent_analysis.get('workflow_type', 'sequential')
            agent_chain = intent_analysis.get('agent_chain', [])

            if len(agent_chain) > 1:
                self._store_workflow_context(intent_analysis, user_message)

                if workflow_type == 'sequential':
                    return await self._coordinate_sequential_workflow(agent_chain, user_message, context)
                elif workflow_type == 'parallel':
                    return await self._coordinate_multiple_agents(agent_chain, user_message, context)

        # Single agent routing
        primary_agent = intent_analysis.get('primary_agent', 'assistant')
        primary_response = await self._route_to_agent(primary_agent, user_message, context)

        if primary_response.success:
            self._store_single_agent_context(primary_agent, user_message, primary_response.content)
            return primary_response.content
        else:
            # Fallback logic
            if primary_agent != 'assistant' and 'assistant' in self.specialized_agents:
                fallback_response = await self._route_to_agent('assistant', user_message, context)
                return fallback_response.content
            else:
                return f"I encountered an error: {primary_response.error}"

    # Add follow-up request handling
    async def _handle_follow_up_request(self, intent_analysis: Dict[str, Any], user_message: str,
                                        context: ExecutionContext) -> str:
        """Handle follow-up requests using LLM analysis"""

        follow_up_type = intent_analysis.get('follow_up_type', 'none')
        session_context = self._get_session_context()

        if follow_up_type == 'continue_workflow':
            return await self._continue_interrupted_workflow(user_message, session_context)

        elif follow_up_type == 'modify_previous':
            return await self._modify_last_operation(user_message, session_context, intent_analysis)

        elif follow_up_type == 'repeat_with_variation':
            return await self._repeat_with_modifications(user_message, session_context, intent_analysis)

        elif follow_up_type == 'elaborate':
            return await self._elaborate_on_previous(user_message, session_context)

        elif follow_up_type == 'related_task':
            return await self._handle_additional_task(user_message, session_context, intent_analysis)

        else:
            # Generic follow-up handling
            context_refs = intent_analysis.get('context_references', [])
            if context_refs:
                return await self._resolve_context_and_route(user_message, context_refs, context)

        return await self._route_to_agent('assistant', user_message, context)

    # Context storage methods for session continuity
    def _store_workflow_context(self, intent_analysis: Dict[str, Any], user_message: str):
        """Store workflow context in session memory"""
        if hasattr(self, 'memory') and self.memory:
            workflow_context = {
                'type': 'workflow',
                'workflow_type': intent_analysis.get('workflow_type'),
                'agent_chain': intent_analysis.get('agent_chain', []),
                'original_request': user_message,
                'workflow_description': intent_analysis.get('workflow_description'),
                'started_at': datetime.now().isoformat(),
                'current_step': 0,
                'status': 'in_progress'
            }
            self.memory.store_context('current_workflow', workflow_context)

    def _store_single_agent_context(self, agent_name: str, request: str, response: str):
        """Store single agent operation context"""
        if hasattr(self, 'memory') and self.memory:
            operation_context = {
                'type': 'single_operation',
                'agent_used': agent_name,
                'user_request': request,
                'response_preview': response[:200] + '...' if len(response) > 200 else response,
                'completed_at': datetime.now().isoformat()
            }
            self.memory.store_context('last_operation', operation_context)

    def _get_session_context(self) -> Dict[str, Any]:
        """Get current session context for LLM analysis"""
        if not hasattr(self, 'memory') or not self.memory:
            return {}

        try:
            current_workflow = self.memory.get_context('current_workflow') or {}
            last_operation = self.memory.get_context('last_operation') or {}

            context_summary = []

            if current_workflow:
                context_summary.append(f"Active workflow: {current_workflow.get('workflow_description', 'Unknown')}")
                context_summary.append(
                    f"Workflow step: {current_workflow.get('current_step', 0)} of {len(current_workflow.get('agent_chain', []))}")

            if last_operation:
                context_summary.append(
                    f"Last operation: {last_operation.get('agent_used')} - {last_operation.get('user_request', '')[:50]}")

            return {
                'workflow_active': bool(current_workflow.get('status') == 'in_progress'),
                'last_agent': last_operation.get('agent_used'),
                'context_summary': ' | '.join(context_summary)
            }
        except Exception as e:
            logging.error(f"Error getting session context: {e}")
            return {}

    # Enhanced workflow recovery and error handling

    async def _continue_interrupted_workflow(self, user_message: str, session_context: Dict[str, Any]) -> str:
        """Continue an interrupted multi-agent workflow with error recovery"""
        current_workflow = self.memory.get_context('current_workflow') if self.memory else {}

        if not current_workflow or current_workflow.get('status') != 'in_progress':
            # Check if there's a completed workflow that could be extended
            if current_workflow.get('status') == 'completed':
                return await self._handle_workflow_extension(user_message, current_workflow)
            return "No active workflow to continue. How can I help you start a new task?"

        agent_chain = current_workflow.get('agent_chain', [])
        current_step = current_workflow.get('current_step', 0)

        # Validate that remaining agents are still available
        remaining_agents = agent_chain[current_step:]
        available_remaining = [agent for agent in remaining_agents if agent in self.specialized_agents]

        if not available_remaining:
            # All remaining agents are unavailable
            if self.memory:
                current_workflow['status'] = 'failed'
                current_workflow['failure_reason'] = 'remaining_agents_unavailable'
                self.memory.store_context('current_workflow', current_workflow)

            return f"Cannot continue workflow - the remaining agents ({', '.join(remaining_agents)}) are not available. How else can I help?"

        if len(available_remaining) != len(remaining_agents):
            # Some agents unavailable, ask user for guidance
            unavailable = [a for a in remaining_agents if a not in self.specialized_agents]
            return f"The workflow had these remaining steps: {', '.join(remaining_agents)}. However, these agents are not available: {', '.join(unavailable)}. Would you like me to continue with the available agents ({', '.join(available_remaining)}) or modify the workflow?"

        if current_step < len(agent_chain):
            # Update workflow context
            current_workflow['current_step'] = current_step + 1
            current_workflow['resumed_at'] = datetime.now().isoformat()
            if self.memory:
                self.memory.store_context('current_workflow', current_workflow)

            return await self._coordinate_sequential_workflow(available_remaining, user_message, None)
        else:
            # Workflow complete
            if self.memory:
                current_workflow['status'] = 'completed'
                current_workflow['completed_at'] = datetime.now().isoformat()
                self.memory.store_context('current_workflow', current_workflow)
            return "The workflow has been completed. How else can I help you?"

    async def _handle_workflow_extension(self, user_message: str, completed_workflow: Dict[str, Any]) -> str:
        """Handle requests to extend a completed workflow"""
        if not self.llm_service:
            return "The previous workflow is complete. What new task would you like to start?"

        extension_prompt = f"""
        The user had a completed workflow: {completed_workflow.get('workflow_description', 'Unknown')}
        Original agents used: {completed_workflow.get('agent_chain', [])}

        Now they want: {user_message}

        Should this be:
        1. A continuation/extension of the previous workflow
        2. A new independent workflow
        3. A modification of the previous workflow results

        If it's a continuation, suggest which additional agents should be used.
        Available agents: {list(self.specialized_agents.keys())}

        Respond with: "continue", "independent", or "modify"
        If "continue", also specify: additional_agents=["agent1", "agent2"]
        """

        try:
            response = await self.llm_service.generate_response(extension_prompt)

            if "continue" in response.lower():
                # Extract additional agents from response
                import re
                agents_match = re.search(r'additional_agents=\[(.*?)\]', response)
                if agents_match:
                    additional_agents = [a.strip().strip('"\'') for a in agents_match.group(1).split(',')]
                    # Filter to available agents
                    additional_agents = [a for a in additional_agents if a in self.specialized_agents]

                    if additional_agents:
                        # Start new workflow with additional agents
                        return await self._coordinate_sequential_workflow(additional_agents, user_message, None)

            elif "modify" in response.lower():
                # Route to modify previous results
                return await self._modify_workflow_results(user_message, completed_workflow)

        except Exception as e:
            logging.error(f"Workflow extension analysis failed: {e}")

        # Default: treat as new request
        return "Starting a new task. How can I help you?"

    async def _modify_workflow_results(self, user_message: str, completed_workflow: Dict[str, Any]) -> str:
        """Modify results from a completed workflow"""
        last_agent = completed_workflow.get('agent_chain', [])[-1] if completed_workflow.get('agent_chain') else None

        if last_agent and last_agent in self.specialized_agents:
            modification_request = f"""
            Previous workflow: {completed_workflow.get('workflow_description', '')}
            Modification needed: {user_message}

            Please modify or build upon the previous workflow results.
            """

            response = await self._route_to_agent(last_agent, modification_request, None)
            return response.content if hasattr(response, 'content') else str(response)

        return f"I can't modify the previous workflow results. The last agent ({last_agent}) is not available."

    # Enhanced error handling in workflow coordination
    async def _coordinate_sequential_workflow(self, agents: List[str], user_message: str,
                                              context: ExecutionContext = None) -> str:
        """Coordinate agents in a workflow with enhanced error handling"""

        workflow_results = []
        current_context = user_message
        failed_agents = []

        for i, agent_type in enumerate(agents):
            try:
                logging.info(f"Workflow step {i + 1}: Running {agent_type}")

                # Double-check agent availability at runtime
                if agent_type not in self.specialized_agents:
                    failed_agents.append(agent_type)
                    logging.warning(f"Agent {agent_type} not available at step {i + 1}")
                    continue

                # Modify the message for subsequent agents to include previous results
                if i > 0:
                    previous_result = workflow_results[-1]
                    current_context = f"""Based on the previous step result:
    {previous_result['content'][:200]}...

    Original request: {user_message}

    Please continue with the next step for {agent_type} processing."""

                response = await self._route_to_agent(agent_type, current_context, context)

                workflow_results.append({
                    'agent': agent_type,
                    'content': response.content,
                    'success': response.success,
                    'step': i + 1,
                    'execution_time': response.execution_time
                })

                if not response.success:
                    logging.warning(f"Workflow step {i + 1} failed for {agent_type}: {response.error}")
                    failed_agents.append(agent_type)
                    # Continue with remaining agents unless it's a critical failure
                    if "not available" in str(response.error).lower():
                        continue

            except Exception as e:
                logging.error(f"Workflow error at step {i + 1} ({agent_type}): {e}")
                failed_agents.append(agent_type)
                continue

        # Format workflow results with error summary
        if not workflow_results:
            return f"I wasn't able to complete the workflow. Failed agents: {', '.join(failed_agents)}"

        response = f"🔄 **Multi-Agent Workflow Completed** ({len(workflow_results)} steps"
        if failed_agents:
            response += f", {len(failed_agents)} failed"
        response += ")\n\n"

        for result in workflow_results:
            status_emoji = "✅" if result['success'] else "❌"
            response += f"**Step {result['step']} - {result['agent'].replace('_', ' ').title()}:** {status_emoji}\n"
            response += f"{result['content']}\n\n"
            response += "─" * 50 + "\n\n"

        if failed_agents:
            response += f"\n⚠️ **Note:** Some agents failed or were unavailable: {', '.join(set(failed_agents))}"

        return response.strip()
    async def _modify_last_operation(self, user_message: str, session_context: Dict[str, Any],
                                     intent_analysis: Dict[str, Any]) -> str:
        """Modify the result of the last operation"""
        last_operation = self.memory.get_context('last_operation') if self.memory else {}

        if not last_operation:
            return "I don't see a previous operation to modify. Could you provide more details?"

        last_agent = last_operation.get('agent_used')
        if last_agent and last_agent in self.specialized_agents:
            # Create modification request with context
            modification_request = f"""
            Previous request: {last_operation.get('user_request', '')}
            Previous result: {last_operation.get('response_preview', '')}

            Modification needed: {user_message}

            Please modify the previous result based on this feedback.
            """

            response = await self._route_to_agent(last_agent, modification_request, None)
            return response.content if hasattr(response, 'content') else str(response)

        return f"Cannot modify the previous operation. Last agent used: {last_agent or 'unknown'}"

    async def _repeat_with_modifications(self, user_message: str, session_context: Dict[str, Any],
                                         intent_analysis: Dict[str, Any]) -> str:
        """Repeat the last operation with variations"""
        last_operation = self.memory.get_context('last_operation') if self.memory else {}

        if not last_operation:
            return "No previous operation to repeat. What would you like me to do?"

        # Extract the variation from user message using LLM
        variation_prompt = f"""
        User wants to repeat this operation: {last_operation.get('user_request', '')}
        With this variation: {user_message}

        Create a new request that applies the same operation with the user's variation.
        """

        try:
            if self.llm_service:
                new_request = await self.llm_service.generate_response(variation_prompt)

                # Route to the same agent as before
                last_agent = last_operation.get('agent_used')
                if last_agent and last_agent in self.specialized_agents:
                    response = await self._route_to_agent(last_agent, new_request, None)
                    return response.content if hasattr(response, 'content') else str(response)

            return f"I'll repeat the operation with your variations: {user_message}"

        except Exception as e:
            return f"I understand you want to repeat the operation with modifications, but I encountered an error: {e}"

    async def _route_to_agent(self, agent_type: str, user_message: str,
                              context: ExecutionContext = None) -> AgentResponse:
        """Enhanced agent routing with validation"""

        # 🔍 DEBUGGING: Log routing attempt
        logging.info(f"🚀 Attempting to route to: {agent_type}")
        logging.info(f"📋 Available agents: {list(self.specialized_agents.keys())}")

        if agent_type not in self.specialized_agents:
            logging.error(f"❌ Agent {agent_type} not in specialized_agents")
            return AgentResponse(
                agent_type=agent_type,
                content=f"Agent {agent_type} not available. Available agents: {list(self.specialized_agents.keys())}",
                success=False,
                execution_time=0.0,
                metadata={},
                error=f"Agent {agent_type} not initialized"
            )

        start_time = time.time()

        try:
            agent = self.specialized_agents[agent_type]
            logging.info(f"✅ Found agent: {agent.__class__.__name__} (ID: {agent.agent_id})")

            # 🔧 FIX: Ensure agent has chat method
            if not hasattr(agent, 'chat'):
                logging.error(f"❌ Agent {agent_type} does not have chat method")
                return AgentResponse(
                    agent_type=agent_type,
                    content=f"Agent {agent_type} does not support chat interface",
                    success=False,
                    execution_time=time.time() - start_time,
                    metadata={},
                    error="No chat method available"
                )

            # Use the agent's chat interface
            logging.info(f"🗨️ Calling chat method for {agent_type}")
            response_content = await agent.chat(user_message)

            execution_time = time.time() - start_time
            logging.info(f"✅ Agent {agent_type} responded successfully in {execution_time:.2f}s")

            return AgentResponse(
                agent_type=agent_type,
                content=response_content,
                success=True,
                execution_time=execution_time,
                metadata={
                    'agent_id': agent.agent_id,
                    'agent_class': agent.__class__.__name__,
                    'session_id': getattr(agent.context, 'session_id', 'unknown') if hasattr(agent,
                                                                                             'context') else 'unknown'
                }
            )

        except Exception as e:
            execution_time = time.time() - start_time
            logging.error(f"❌ Error routing to {agent_type} agent: {e}")

            # 🔧 FIX: Provide more detailed error info
            import traceback
            logging.error(f"Full traceback: {traceback.format_exc()}")

            return AgentResponse(
                agent_type=agent_type,
                content=f"Error processing request with {agent_type} agent: {str(e)}",
                success=False,
                execution_time=execution_time,
                metadata={'error_type': type(e).__name__},
                error=str(e)
            )

    async def _coordinate_multiple_agents(self, agents: List[str], user_message: str,
                                          context: ExecutionContext = None) -> str:
        """Coordinate multiple agents for complex queries"""
        responses = []

        # Execute agents concurrently
        tasks = [self._route_to_agent(agent_type, user_message, context)
                 for agent_type in agents]

        agent_responses = await asyncio.gather(*tasks, return_exceptions=True)

        successful_responses = []
        for response in agent_responses:
            if isinstance(response, AgentResponse) and response.success:
                successful_responses.append(response)

        if not successful_responses:
            return "I wasn't able to process your request with any of the available agents."

        # Combine multiple responses intelligently
        if len(successful_responses) == 1:
            return successful_responses[0].content

        combined_response = "Here's what I found from multiple sources:\n\n"

        for i, response in enumerate(successful_responses, 1):
            combined_response += f"**From {response.agent_type.replace('_', ' ').title()}:**\n"
            combined_response += f"{response.content}\n\n"

        return combined_response.strip()

    def _get_conversation_context_summary(self) -> str:
        """Get conversation context summary (simplified for now)"""
        try:
            recent_history = self.get_conversation_history_with_context(limit=3)
            context_summary = []

            for msg in recent_history:
                if msg.get('message_type') == 'user_input':
                    content = msg.get('content', '')
                    context_summary.append(content[:50])

            return " ".join(context_summary) if context_summary else ""
        except:
            return ""

    async def get_agent_status(self) -> Dict[str, Any]:
        """Get status of all managed agents - FIXED METHOD"""
        status = {
            'moderator_id': self.agent_id,
            'enabled_agents': self.enabled_agents,
            'active_agents': {},
            'total_agents': len(self.specialized_agents),
            'routing_patterns': len(self.agent_routing_patterns)
        }

        for agent_type, agent in self.specialized_agents.items():
            try:
                # Simple status check
                status['active_agents'][agent_type] = {
                    'agent_id': agent.agent_id,
                    'status': 'active',
                    'session_id': agent.context.session_id if hasattr(agent, 'context') else 'unknown'
                }
            except Exception as e:
                status['active_agents'][agent_type] = {
                    'agent_id': getattr(agent, 'agent_id', 'unknown'),
                    'status': 'error',
                    'error': str(e)
                }

        return status

    async def cleanup_session(self) -> bool:
        """Cleanup all managed agents"""
        success = True

        # Cleanup all specialized agents
        for agent_type, agent in self.specialized_agents.items():
            try:
                await agent.cleanup_session()
                logging.info(f"Cleaned up {agent_type} agent")
            except Exception as e:
                logging.error(f"Error cleaning up {agent_type} agent: {e}")
                success = False

        # Cleanup moderator itself
        moderator_cleanup = await super().cleanup_session()

        return success and moderator_cleanup

    async def process_message(self, message: AgentMessage, context: ExecutionContext = None) -> AgentMessage:
        """Main processing method - FIXED: Preserves context across LLM provider switches"""
        self.memory.store_message(message)

        try:
            user_message = message.content
            self.update_conversation_state(user_message)

            # 🔥 FIX: Get conversation history for LLM context
            conversation_context = self._get_conversation_context_summary()
            conversation_history = []

            # Get conversation history if memory available
            if hasattr(self, 'memory') and self.memory:
                try:
                    recent_messages = self.memory.get_recent_messages(
                        limit=5,
                        conversation_id=message.conversation_id
                    )
                    conversation_history = recent_messages
                except Exception as e:
                    logging.warning(f"Could not get conversation history: {e}")

            # 🔥 FIX: Analyze intent to determine routing WITH CONTEXT
            intent_analysis = await self._analyze_query_intent(user_message, conversation_context)

            logging.info(f"Intent analysis: Primary={intent_analysis['primary_agent']}, "
                         f"Confidence={intent_analysis['confidence']:.2f}, "
                         f"Multi-agent={intent_analysis.get('requires_multiple_agents', False)}")

            # 🔥 FIX: Build LLM context for agent routing
            llm_context = {
                'conversation_id': message.conversation_id,
                'user_id': message.sender_id,
                'conversation_history': conversation_history,  # 🔥 KEY: Preserve context
                'session_id': message.session_id,
                'intent_analysis': intent_analysis
            }

            # Process with enhanced context preservation
            if intent_analysis.get('requires_multiple_agents', False):
                workflow_type = intent_analysis.get('workflow_type', 'sequential')

                if workflow_type == "sequential":
                    response_content = await self._coordinate_sequential_workflow(
                        intent_analysis['high_scoring_agents'],
                        user_message,
                        context,
                        llm_context  # 🔥 FIX: Pass context to workflow
                    )
                else:
                    response_content = await self._coordinate_multiple_agents(
                        intent_analysis['high_scoring_agents'],
                        user_message,
                        context,
                        llm_context  # 🔥 FIX: Pass context to workflow
                    )
            else:
                # Single agent routing with context
                primary_response = await self._route_to_agent_with_context(
                    intent_analysis['primary_agent'],
                    user_message,
                    context,
                    llm_context  # 🔥 FIX: Pass context
                )

                if primary_response.success:
                    response_content = primary_response.content
                else:
                    # Fallback with context preservation
                    if intent_analysis['primary_agent'] != 'assistant' and 'assistant' in self.specialized_agents:
                        fallback_response = await self._route_to_agent_with_context('assistant', user_message, context,
                                                                                    llm_context)
                        response_content = fallback_response.content
                    else:
                        response_content = f"I encountered an error: {primary_response.error}"

            # Create response
            response = self.create_response(
                content=response_content,
                metadata={
                    "routing_analysis": intent_analysis,
                    "agent_scores": intent_analysis.get('agent_scores', {}),
                    "workflow_type": intent_analysis.get('workflow_type', 'single'),
                    "context_preserved": len(conversation_history) > 0  # 🔥 FIX: Track context preservation
                },
                recipient_id=message.sender_id,
                session_id=message.session_id,
                conversation_id=message.conversation_id
            )

            self.memory.store_message(response)
            return response

        except Exception as e:
            logging.error(f"ModeratorAgent error: {e}")
            error_response = self.create_response(
                content=f"I encountered an error processing your request: {str(e)}",
                recipient_id=message.sender_id,
                message_type=MessageType.ERROR,
                session_id=message.session_id,
                conversation_id=message.conversation_id
            )
            return error_response

    async def _route_to_agent_with_context(self, agent_type: str, user_message: str,
                                           context: ExecutionContext = None,
                                           llm_context: Dict[str, Any] = None) -> AgentResponse:
        """Enhanced agent routing WITH context preservation"""

        if agent_type not in self.specialized_agents:
            return AgentResponse(
                agent_type=agent_type,
                content=f"Agent {agent_type} not available",
                success=False,
                execution_time=0.0,
                metadata={},
                error=f"Agent {agent_type} not initialized"
            )

        start_time = time.time()

        try:
            agent = self.specialized_agents[agent_type]

            # 🔥 FIX: Create message with LLM context for context preservation
            agent_message = AgentMessage(
                id=f"msg_{str(uuid.uuid4())[:8]}",
                sender_id="moderator_user",
                recipient_id=agent.agent_id,
                content=user_message,
                message_type=MessageType.USER_INPUT,
                session_id=context.session_id if context else None,
                conversation_id=context.conversation_id if context else None,
                metadata={'llm_context': llm_context}  # 🔥 FIX: Pass LLM context through metadata
            )

            # 🔥 FIX: Enhanced context for agent processing
            if context:
                context.metadata.update(llm_context or {})

            response_message = await agent.process_message(agent_message, context)

            execution_time = time.time() - start_time

            return AgentResponse(
                agent_type=agent_type,
                content=response_message.content,
                success=True,
                execution_time=execution_time,
                metadata={
                    'agent_id': agent.agent_id,
                    'agent_class': agent.__class__.__name__,
                    'context_preserved': bool(llm_context and llm_context.get('conversation_history'))
                }
            )

        except Exception as e:
            execution_time = time.time() - start_time
            logging.error(f"❌ Error routing to {agent_type} agent: {e}")

            return AgentResponse(
                agent_type=agent_type,
                content=f"Error processing request with {agent_type} agent: {str(e)}",
                success=False,
                execution_time=execution_time,
                metadata={'error_type': type(e).__name__},
                error=str(e)
            )

    async def process_message_stream(self, message: AgentMessage, context: ExecutionContext = None) -> AsyncIterator[
        str]:
        """Stream processing with enhanced coordination - FIXED: Context preserved across provider switches"""
        self.memory.store_message(message)

        try:
            user_message = message.content

            # 🔥 FIX: Get conversation history for streaming
            conversation_context = self._get_conversation_context_summary()
            conversation_history = []

            if hasattr(self, 'memory') and self.memory:
                try:
                    conversation_history = self.memory.get_recent_messages(
                        limit=5,
                        conversation_id=message.conversation_id
                    )
                except Exception as e:
                    logging.warning(f"Could not get conversation history for streaming: {e}")

            # 🔍 PHASE 1: Analysis Phase with Progress
            yield "🔍 **Analyzing your request...**\n\n"
            self.update_conversation_state(user_message)

            yield "🧠 Checking conversation context...\n"
            yield "🎯 Determining the best approach...\n\n"

            # 🔥 FIX: Analyze intent with conversation context
            intent_analysis = await self._analyze_query_intent(user_message, conversation_context)

            # 📋 PHASE 2: Routing Phase with Agent Selection
            agent_name = intent_analysis['primary_agent'].replace('_', ' ').title()
            confidence = intent_analysis.get('confidence', 0)
            workflow_type = intent_analysis.get('workflow_type', 'single')

            yield f"📋 **Routing to {agent_name}** (confidence: {confidence:.1f})\n"
            yield f"🔄 **Workflow:** {workflow_type.title()}\n\n"

            await asyncio.sleep(0.1)

            # 🔥 FIX: Build LLM context for streaming
            llm_context = {
                'conversation_id': message.conversation_id,
                'user_id': message.sender_id,
                'conversation_history': conversation_history,  # 🔥 KEY FIX
                'session_id': message.session_id,
                'intent_analysis': intent_analysis,
                'streaming': True
            }

            # 🚀 PHASE 3: Stream Actual Processing with Context
            if intent_analysis.get('requires_multiple_agents', False):
                if workflow_type == 'sequential':
                    yield "🔄 **Sequential Workflow Coordination...**\n\n"
                    async for chunk in self._coordinate_multiple_agents_stream_with_context(
                            intent_analysis['high_scoring_agents'],
                            user_message,
                            context,
                            llm_context  # 🔥 FIX: Pass context to streaming workflow
                    ):
                        yield chunk
                else:
                    yield "🔀 **Parallel Agent Coordination...**\n\n"
                    async for chunk in self._coordinate_multiple_agents_stream_with_context(
                            intent_analysis['high_scoring_agents'],
                            user_message,
                            context,
                            llm_context  # 🔥 FIX: Pass context
                    ):
                        yield chunk
            else:
                # Single agent processing with context
                async for chunk in self._route_to_agent_stream_with_context(
                        intent_analysis['primary_agent'],
                        user_message,
                        context,
                        llm_context  # 🔥 FIX: Pass context
                ):
                    yield chunk

            # 📊 PHASE 4: Completion Summary
            reasoning = intent_analysis.get('reasoning', 'Standard routing')
            context_preserved = len(conversation_history) > 0
            yield f"\n\n*✅ Completed by: {agent_name}*\n*🧠 Reasoning: {reasoning}*"
            if context_preserved:
                yield f"\n*💾 Context: {len(conversation_history)} messages preserved*"

        except Exception as e:
            logging.error(f"ModeratorAgent streaming error: {e}")
            yield f"\n\n❌ **Error:** {str(e)}"

    async def _stream_sequential_workflow(self, agents: List[str], user_message: str,
                                          context: ExecutionContext = None) -> AsyncIterator[str]:
        """Stream sequential workflow processing"""

        workflow_results = []
        current_context = user_message

        for i, agent_type in enumerate(agents):
            try:
                yield f"**🤖 Step {i + 1}: {agent_type.replace('_', ' ').title()}**\n"
                yield "─" * 50 + "\n"

                # Modify the message for subsequent agents to include previous results
                if i > 0:
                    previous_result = workflow_results[-1]
                    current_context = f"""Based on the previous step result:
    {previous_result['content'][:200]}...

    Original request: {user_message}

    Please continue with the next step for {agent_type} processing."""

                # Stream the agent's response
                agent_content = ""
                async for chunk in self._route_to_agent_stream(agent_type, current_context, context):
                    yield chunk
                    agent_content += chunk

                workflow_results.append({
                    'agent': agent_type,
                    'content': agent_content,
                    'step': i + 1
                })

                yield "\n" + "─" * 50 + "\n\n"

                # Brief pause between agents
                await asyncio.sleep(0.1)

            except Exception as e:
                yield f"❌ Error with {agent_type}: {str(e)}\n\n"
                break

        yield f"✅ **Workflow completed with {len(workflow_results)} steps**"

    async def _route_to_agent_stream_with_context(self, agent_type: str, user_message: str,
                                                  context: ExecutionContext = None,
                                                  llm_context: Dict[str, Any] = None) -> AsyncIterator[str]:
        """Stream routing to a specific agent - FIXED: With context preservation"""
        if agent_type not in self.specialized_agents:
            yield f"❌ Agent {agent_type} not available"
            return

        try:
            agent = self.specialized_agents[agent_type]

            # Check if agent supports streaming
            if hasattr(agent, 'process_message_stream'):
                # 🔥 FIX: Create message with LLM context for streaming
                agent_message = AgentMessage(
                    id=str(uuid.uuid4()),
                    sender_id=f"moderator_{self.agent_id}",
                    recipient_id=agent.agent_id,
                    content=user_message,
                    message_type=MessageType.USER_INPUT,
                    session_id=context.session_id if context else None,
                    conversation_id=context.conversation_id if context else None,
                    metadata={'llm_context': llm_context}  # 🔥 FIX: Pass context through metadata
                )

                # 🔥 FIX: Enhanced context for streaming
                if context and llm_context:
                    context.metadata.update(llm_context)

                # Stream from the agent with context
                async for chunk in agent.process_message_stream(agent_message, context):
                    yield chunk
            else:
                # Fallback to non-streaming with context
                yield f"⚠️ {agent_type} doesn't support streaming, using standard processing...\n\n"

                # 🔥 FIX: Use context-aware routing for fallback
                response = await self._route_to_agent_with_context(agent_type, user_message, context, llm_context)
                yield response.content

        except Exception as e:
            yield f"❌ Error routing to {agent_type}: {str(e)}"

    async def _coordinate_multiple_agents_stream_with_context(self, agents: List[str], user_message: str,
                                                              context: ExecutionContext = None,
                                                              llm_context: Dict[str, Any] = None) -> AsyncIterator[str]:
        """Stream coordination of multiple agents - FIXED: With context preservation"""
        successful_responses = 0

        for i, agent_type in enumerate(agents, 1):
            try:
                yield f"**🤖 Agent {i}: {agent_type.replace('_', ' ').title()}**\n"
                yield "─" * 50 + "\n"

                # 🔥 FIX: Stream with context preservation
                async for chunk in self._route_to_agent_stream_with_context(agent_type, user_message, context,
                                                                            llm_context):
                    yield chunk

                yield "\n" + "─" * 50 + "\n\n"
                successful_responses += 1
                await asyncio.sleep(0.1)

            except Exception as e:
                yield f"❌ Error with {agent_type}: {str(e)}\n\n"

        yield f"✅ {successful_responses}/{len(agents)} agents completed with context preserved"

    async def _route_to_agent_stream(self, agent_type: str, user_message: str, context: ExecutionContext = None) -> \
    AsyncIterator[str]:
        """Stream routing to a specific agent"""
        if agent_type not in self.specialized_agents:
            yield f"❌ Agent {agent_type} not available"
            return

        try:
            agent = self.specialized_agents[agent_type]

            # Check if agent supports streaming
            if hasattr(agent, 'process_message_stream'):
                # Create message for the agent
                agent_message = AgentMessage(
                    id=str(uuid.uuid4()),
                    sender_id=f"moderator_{self.agent_id}",
                    recipient_id=agent.agent_id,
                    content=user_message,
                    message_type=MessageType.USER_INPUT,
                    session_id=context.session_id if context else None,
                    conversation_id=context.conversation_id if context else None
                )

                # Stream from the agent
                async for chunk in agent.process_message_stream(agent_message, context):
                    yield chunk
            else:
                # Fallback to non-streaming
                yield f"⚠️ {agent_type} doesn't support streaming, using standard processing...\n\n"
                response = await agent.chat(user_message)
                yield response

        except Exception as e:
            yield f"❌ Error routing to {agent_type}: {str(e)}"

    async def _coordinate_multiple_agents_stream(self, agents: List[str], user_message: str,
                                                 context: ExecutionContext = None) -> AsyncIterator[str]:
        """Stream coordination of multiple agents"""
        successful_responses = 0

        for i, agent_type in enumerate(agents, 1):
            try:
                yield f"**🤖 Agent {i}: {agent_type.replace('_', ' ').title()}**\n"
                yield "─" * 50 + "\n"

                async for chunk in self._route_to_agent_stream(agent_type, user_message, context):
                    yield chunk

                yield "\n" + "─" * 50 + "\n\n"
                successful_responses += 1

                # Brief pause between agents
                await asyncio.sleep(0.1)

            except Exception as e:
                yield f"❌ Error with {agent_type}: {str(e)}\n\n"

        yield f"{successful_responses}/{len(agents)}"

    @classmethod
    def create(cls,
               agent_id: str = None,
               user_id: str = None,
               tenant_id: str = "default",
               enabled_agents: List[str] = None,
               session_metadata: Dict[str, Any] = None,
               **kwargs):
        """
        Create ModeratorAgent with specified enabled agents

        Args:
            agent_id: Optional agent ID
            user_id: User ID for context
            tenant_id: Tenant ID for context
            enabled_agents: List of agent types to enable. If None, uses config defaults
            session_metadata: Additional session metadata
            **kwargs: Additional arguments

        Returns:
            Tuple of (ModeratorAgent, AgentContext)
        """
        if agent_id is None:
            agent_id = f"moderator_{str(uuid.uuid4())[:8]}"

        agent = cls(
            agent_id=agent_id,
            user_id=user_id,
            tenant_id=tenant_id,
            enabled_agents=enabled_agents,
            session_metadata=session_metadata,
            auto_configure=True,
            **kwargs
        )

        return agent, agent.context

    @classmethod
    def create_simple(cls,
                      user_id: str = None,
                      tenant_id: str = "default",
                      enabled_agents: List[str] = None,
                      **kwargs):
        """
        Simple factory method for ModeratorAgent

        Args:
            user_id: User ID for context
            tenant_id: Tenant ID for context
            enabled_agents: List of agent types to enable
            **kwargs: Additional arguments

        Returns:
            ModeratorAgent instance
        """
        agent_id = f"moderator_{str(uuid.uuid4())[:8]}"

        return cls(
            agent_id=agent_id,
            user_id=user_id,
            tenant_id=tenant_id,
            enabled_agents=enabled_agents,
            auto_configure=True,
            **kwargs
        )

    async def _force_code_execution_if_needed(self, user_message: str, intent_analysis: Dict[str, Any]) -> Dict[
        str, Any]:
        """Force routing to code executor for obvious code requests"""

        if self._is_code_request(user_message) and 'code_executor' in self.specialized_agents:
            # Override LLM analysis for obvious code requests
            logging.info("🔧 OVERRIDING: Forcing code_executor for obvious code request")

            intent_analysis.update({
                'primary_agent': 'code_executor',
                'confidence': 0.95,
                'requires_multiple_agents': False,
                'workflow_detected': False,
                'is_follow_up': False,
                'reasoning': 'Forced routing to code_executor for code request'
            })

        elif self._is_search_request(user_message) and 'web_search' in self.specialized_agents:
            # Override for search requests
            logging.info("🔧 OVERRIDING: Forcing web_search for search request")

            intent_analysis.update({
                'primary_agent': 'web_search',
                'confidence': 0.95,
                'requires_multiple_agents': False,
                'workflow_detected': False,
                'is_follow_up': False,
                'reasoning': 'Forced routing to web_search for search request'
            })

        return intent_analysis