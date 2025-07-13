# ambivo_agents/agents/assistant.py
"""
Complete AssistantAgent with System Message, LLM Context, and Memory Preservation
"""

import json
import logging
import uuid
from datetime import datetime
from typing import Any, AsyncIterator, Dict

from ..core.base import AgentMessage, AgentRole, BaseAgent, ExecutionContext, MessageType, StreamChunk, StreamSubType
from ..core.history import BaseAgentHistoryMixin


class AssistantAgent(BaseAgent, BaseAgentHistoryMixin):
    """
    General purpose assistant agent with complete system message support,
    conversation history, and memory preservation across routing.
    """

    def __init__(
        self,
        agent_id: str = None,
        memory_manager=None,
        llm_service=None,
        system_message: str = None,
        **kwargs,
    ):
        if agent_id is None:
            agent_id = f"assistant_{str(uuid.uuid4())[:8]}"

        # Enhanced default system message for AssistantAgent
        default_system = """You are a helpful AI assistant with the following capabilities:
        - Maintain conversation context and reference previous discussions naturally
        - Provide accurate, thoughtful responses tailored to the user's needs
        - Ask clarifying questions when information is incomplete
        - Acknowledge limitations and uncertainties honestly
        - Be conversational but professional in tone
        - Structure responses clearly with examples when helpful
        - Remember and reference previous parts of our conversation when relevant
        - Adapt your communication style to the user's preferences and context
        - When routed from other agents, maintain conversation continuity
        - Use conversation history to provide more relevant and personalized responses"""

        super().__init__(
            agent_id=agent_id,
            role=AgentRole.ASSISTANT,
            memory_manager=memory_manager,
            llm_service=llm_service,
            name="Assistant Agent",
            description="General purpose assistant for user interactions",
            system_message=system_message or default_system,
            **kwargs,
        )

        # Initialize history mixin
        self.setup_history_mixin()
        self.connected_servers = {}

        # Logging
        self.logger = logging.getLogger(f"AssistantAgent-{agent_id[:8]}")

    def _extract_file_path(self, text: str) -> str:
        """Extract file path from text"""
        import re

        file_match = re.search(
            r'(?:read file|open file|show file)\s+["\']?([^"\']+)["\']?', text, re.IGNORECASE
        )
        if file_match:
            return file_match.group(1)
        return None

    async def _analyze_intent(
        self, user_message: str, conversation_context: str = ""
    ) -> Dict[str, Any]:
        """Analyze user intent with conversation context and system message support"""
        if not self.llm_service:
            return self._keyword_based_analysis(user_message)

        # Enhanced system message for intent analysis
        intent_system_message = f"""
        {self.system_message}

        ADDITIONAL INSTRUCTION: You are analyzing user intent. Consider the conversation context
        and respond in the specified JSON format only. Be precise and analytical.
        """

        prompt = f"""
        Analyze this user message in the context of general assistance:

        Conversation Context:
        {conversation_context}

        Current User Message: {user_message}

        Respond in JSON format:
        {{
            "primary_intent": "question|request|clarification|continuation|greeting|farewell|contextual_reference",
            "requires_context": true/false,
            "context_reference": "what user is referring to if any",
            "topic": "main subject area",
            "confidence": 0.0-1.0,
            "conversation_aware": true/false
        }}
        """

        try:
            response = await self.llm_service.generate_response(
                prompt=prompt, system_message=intent_system_message
            )

            import re

            json_match = re.search(r"\{.*\}", response, re.DOTALL)
            if json_match:
                analysis = json.loads(json_match.group())
                self.logger.debug(f"Intent analysis: {analysis}")
                return analysis
            else:
                self.logger.warning("LLM didn't return valid JSON, using keyword analysis")
                return self._keyword_based_analysis(user_message)

        except Exception as e:
            self.logger.error(f"Intent analysis failed: {e}")
            return self._keyword_based_analysis(user_message)

    def _keyword_based_analysis(self, user_message: str) -> Dict[str, Any]:
        """Fallback keyword-based analysis"""
        content_lower = user_message.lower()

        # Detect intent
        if any(
            word in content_lower
            for word in ["hello", "hi", "hey", "good morning", "good afternoon"]
        ):
            intent = "greeting"
        elif any(
            word in content_lower for word in ["bye", "goodbye", "thanks", "thank you", "see you"]
        ):
            intent = "farewell"
        elif any(word in content_lower for word in ["what", "how", "why", "when", "where", "who"]):
            intent = "question"
        elif any(word in content_lower for word in ["can you", "please", "help me", "could you"]):
            intent = "request"
        elif any(
            word in content_lower
            for word in ["that", "this", "it", "previous", "earlier", "before"]
        ):
            intent = "contextual_reference"
        elif any(word in content_lower for word in ["explain", "clarify", "what do you mean"]):
            intent = "clarification"
        else:
            intent = "question"

        # Check if context is needed
        requires_context = any(
            word in content_lower
            for word in [
                "that",
                "this",
                "it",
                "previous",
                "earlier",
                "before",
                "again",
                "continue",
                "more",
                "also",
                "additionally",
            ]
        )

        return {
            "primary_intent": intent,
            "requires_context": requires_context,
            "context_reference": "previous conversation" if requires_context else None,
            "topic": "general",
            "confidence": 0.7,
            "conversation_aware": requires_context,
        }

    def _build_context_summary(self, conversation_history: list) -> str:
        """Build conversation context summary from history"""
        try:
            if not conversation_history:
                return "No previous conversation"

            context_summary = []
            for msg in conversation_history[-5:]:  # Last 5 messages
                if msg.get("message_type") == "user_input":
                    content = msg.get("content", "")
                    context_summary.append(f"User: {content[:80]}...")
                elif msg.get("message_type") == "agent_response":
                    content = msg.get("content", "")
                    sender = msg.get("sender_id", "Assistant")
                    # Clean sender ID for display
                    if "assistant" in sender.lower():
                        sender = "Assistant"
                    context_summary.append(f"{sender}: {content[:80]}...")

            return "\n".join(context_summary) if context_summary else "No previous conversation"

        except Exception as e:
            self.logger.error(f"Error building context summary: {e}")
            return "Error retrieving conversation context"

    def _get_conversation_context_summary(self) -> str:
        """Get conversation context summary using history mixin"""
        try:
            recent_history = self.get_conversation_history_with_context(limit=5)
            return self._build_context_summary(recent_history)
        except Exception as e:
            self.logger.error(f"Error getting conversation context: {e}")
            return "No previous conversation available"

    async def _route_request(
        self,
        intent_analysis: Dict[str, Any],
        user_message: str,
        context: ExecutionContext,
        llm_context: Dict[str, Any],
    ) -> str:
        """Route request based on intent analysis with full system message support"""

        primary_intent = intent_analysis.get("primary_intent", "question")

        # Handle simple intents
        if primary_intent == "greeting":
            if llm_context.get("conversation_history"):
                return "Hello again! How can I assist you today?"
            else:
                return "Hello! How can I assist you today?"

        elif primary_intent == "farewell":
            return "Thank you for our conversation. Feel free to return anytime if you need help!"

        # For complex intents, use LLM with enhanced system message
        if self.llm_service:
            # Get enhanced system message with full context
            enhanced_system_message = self.get_system_message_for_llm(llm_context)

            # Check if this is a contextual reference that needs conversation history
            if intent_analysis.get("requires_context") and llm_context.get("conversation_history"):
                self.logger.info("Processing contextual reference with conversation history")

                # Build context-aware prompt
                conversation_summary = self._build_context_summary(
                    llm_context["conversation_history"]
                )

                context_prompt = f"""
                Previous conversation context:
                {conversation_summary}

                Current user message: {user_message}

                Please respond considering the conversation history above. Reference previous topics naturally when relevant.
                """

                return await self.llm_service.generate_response(
                    prompt=context_prompt,
                    context=llm_context,
                    system_message=enhanced_system_message,
                )
            else:
                # Standard response with system message
                return await self.llm_service.generate_response(
                    prompt=user_message, context=llm_context, system_message=enhanced_system_message
                )
        else:
            # Fallback when no LLM service available
            if intent_analysis.get("requires_context"):
                return f"I understand you're referring to something from our previous conversation about '{user_message}'. However, I need an LLM service to provide context-aware responses. How else can I help you?"
            else:
                return f"I understand you said: '{user_message}'. How can I help you with that? (Note: LLM service not available for enhanced responses)"

    async def process_message(
        self, message: AgentMessage, context: ExecutionContext = None
    ) -> AgentMessage:
        """Process user requests with complete conversation history and system message support"""

        # Store incoming message
        if self.memory:
            self.memory.store_message(message)

        try:
            user_message = message.content
            self.update_conversation_state(user_message)

            # Check if this is a routed message with existing context from ModeratorAgent
            llm_context_from_routing = message.metadata.get("llm_context", {})
            conversation_history_from_routing = llm_context_from_routing.get(
                "conversation_history", []
            )

            if conversation_history_from_routing:
                # Use the conversation history provided by moderator routing
                conversation_history = conversation_history_from_routing
                self.logger.info(
                    f"🔄 Using {len(conversation_history)} messages from moderator routing"
                )
                conversation_context = self._build_context_summary(conversation_history)
            else:
                # Get our own conversation history as fallback
                conversation_history = await self.get_conversation_history(
                    limit=8, include_metadata=True
                )
                self.logger.info(f"📝 Using {len(conversation_history)} messages from local memory")
                conversation_context = self._get_conversation_context_summary()

            # Analyze intent with full context
            intent_analysis = await self._analyze_intent(user_message, conversation_context)

            # Build comprehensive LLM context
            llm_context = {
                "conversation_id": message.conversation_id,
                "user_id": message.sender_id,
                "session_id": message.session_id,
                "conversation_history": conversation_history,  # Full history
                "conversation_context_summary": conversation_context,
                "intent_analysis": intent_analysis,
                "agent_role": self.role.value,
                "agent_name": self.name,
                "agent_id": self.agent_id,
                "routed_from_moderator": bool(llm_context_from_routing),
                "context_source": "moderator" if conversation_history_from_routing else "local",
                "timestamp": datetime.now().isoformat(),
            }

            # Merge any additional context from routing (without overwriting core context)
            if llm_context_from_routing:
                for key, value in llm_context_from_routing.items():
                    if key not in llm_context:
                        llm_context[key] = value

            # Route request with full context and system message support
            response_content = await self._route_request(
                intent_analysis, user_message, context, llm_context
            )

            # Create response with comprehensive metadata
            response = self.create_response(
                content=response_content,
                recipient_id=message.sender_id,
                session_id=message.session_id,
                conversation_id=message.conversation_id,
                metadata={
                    "intent_analysis": intent_analysis,
                    "system_message_used": True,
                    "context_preserved": len(conversation_history) > 0,
                    "context_source": "moderator" if conversation_history_from_routing else "local",
                    "routed_from_moderator": bool(llm_context_from_routing),
                    "conversation_history_count": len(conversation_history),
                    "processing_timestamp": datetime.now().isoformat(),
                    "agent_type": "assistant",
                },
            )

            # Store response
            if self.memory:
                self.memory.store_message(response)

            self.logger.info(
                f"✅ Processed message with {len(conversation_history)} context messages"
            )
            return response

        except Exception as e:
            self.logger.error(f"Error processing message: {e}")
            import traceback

            self.logger.error(f"Full traceback: {traceback.format_exc()}")

            error_response = self.create_response(
                content=f"I encountered an error processing your request: {str(e)}",
                recipient_id=message.sender_id,
                message_type=MessageType.ERROR,
                session_id=message.session_id,
                conversation_id=message.conversation_id,
                metadata={"error": str(e), "agent_type": "assistant"},
            )
            return error_response

    async def process_message_stream(
        self, message: AgentMessage, context: ExecutionContext = None
    ) -> AsyncIterator[StreamChunk]:
        """Stream processing with complete system message and context support"""

        # Store incoming message
        if self.memory:
            self.memory.store_message(message)

        try:
            user_message = message.content
            self.update_conversation_state(user_message)

            # Get conversation history for streaming context
            llm_context_from_routing = message.metadata.get("llm_context", {})
            conversation_history_from_routing = llm_context_from_routing.get(
                "conversation_history", []
            )

            if conversation_history_from_routing:
                conversation_history = conversation_history_from_routing
                conversation_context = self._build_context_summary(conversation_history)
                self.logger.info(
                    f"🔄 Streaming with {len(conversation_history)} messages from routing"
                )
            else:
                conversation_history = await self.get_conversation_history(
                    limit=8, include_metadata=True
                )
                conversation_context = self._get_conversation_context_summary()
                self.logger.info(
                    f"📝 Streaming with {len(conversation_history)} messages from local memory"
                )

            # Analyze intent
            intent_analysis = await self._analyze_intent(user_message, conversation_context)

            # Build comprehensive LLM context for streaming
            llm_context = {
                "conversation_id": message.conversation_id,
                "user_id": message.sender_id,
                "session_id": message.session_id,
                "conversation_history": conversation_history,
                "conversation_context_summary": conversation_context,
                "intent_analysis": intent_analysis,
                "streaming": True,
                "agent_role": self.role.value,
                "agent_name": self.name,
                "agent_id": self.agent_id,
                "routed_from_moderator": bool(llm_context_from_routing),
                "context_source": "moderator" if conversation_history_from_routing else "local",
            }

            # Merge routing context
            if llm_context_from_routing:
                for key, value in llm_context_from_routing.items():
                    if key not in llm_context:
                        llm_context[key] = value

            # Handle simple intents quickly
            primary_intent = intent_analysis.get("primary_intent", "question")

            if primary_intent == "greeting":
                if llm_context.get("conversation_history"):
                    yield StreamChunk(
                        text="Hello again! How can I assist you today?",
                        sub_type=StreamSubType.CONTENT,
                        metadata={"intent": "greeting", "returning_user": True},
                    )
                else:
                    yield StreamChunk(
                        text="Hello! How can I assist you today?",
                        sub_type=StreamSubType.CONTENT,
                        metadata={"intent": "greeting", "returning_user": False},
                    )
                return

            elif primary_intent == "farewell":
                yield StreamChunk(
                    text="Thank you for our conversation. Feel free to return anytime if you need help!",
                    sub_type=StreamSubType.CONTENT,
                    metadata={"intent": "farewell"},
                )
                return

            # Stream complex responses with system message
            if self.llm_service:
                enhanced_system_message = self.get_system_message_for_llm(llm_context)

                # Handle contextual references
                if intent_analysis.get("requires_context") and conversation_history:
                    conversation_summary = self._build_context_summary(conversation_history)

                    context_prompt = f"""
                    Previous conversation context:
                    {conversation_summary}

                    Current user message: {user_message}

                    Please respond considering the conversation history above. Reference previous topics naturally when relevant.
                    """

                    async for chunk in self.llm_service.generate_response_stream(
                        prompt=context_prompt,
                        context=llm_context,
                        system_message=enhanced_system_message,
                    ):
                        yield StreamChunk(
                            text=chunk,
                            sub_type=StreamSubType.CONTENT,
                            metadata={"with_context": True, "intent": primary_intent},
                        )
                else:
                    # Standard streaming with system message
                    async for chunk in self.llm_service.generate_response_stream(
                        prompt=user_message,
                        context=llm_context,
                        system_message=enhanced_system_message,
                    ):
                        yield StreamChunk(
                            text=chunk,
                            sub_type=StreamSubType.CONTENT,
                            metadata={"with_context": False, "intent": primary_intent},
                        )
            else:
                # Fallback for no LLM service
                if intent_analysis.get("requires_context"):
                    yield StreamChunk(
                        text="I understand you're referring to something from our previous conversation. However, I need an LLM service for context-aware responses. How else can I help?",
                        sub_type=StreamSubType.ERROR,
                        metadata={"error": "no_llm_service", "requires_context": True},
                    )
                else:
                    yield StreamChunk(
                        text=f"I understand you said: '{user_message}'. How can I help you with that?",
                        sub_type=StreamSubType.CONTENT,
                        metadata={"fallback": True, "requires_context": False},
                    )

        except Exception as e:
            self.logger.error(f"Streaming error: {e}")
            yield StreamChunk(
                text=f"I encountered an error while processing your request: {str(e)}",
                sub_type=StreamSubType.ERROR,
                metadata={"error": str(e)},
            )

    def get_agent_status(self) -> Dict[str, Any]:
        """Get current agent status and configuration"""
        return {
            "agent_id": self.agent_id,
            "agent_type": "assistant",
            "role": self.role.value,
            "name": self.name,
            "description": self.description,
            "session_id": self.context.session_id,
            "conversation_id": self.context.conversation_id,
            "user_id": self.context.user_id,
            "has_memory": bool(self.memory),
            "has_llm_service": bool(self.llm_service),
            "system_message_enabled": bool(self.system_message),
            "system_message_preview": (
                self.system_message[:100] + "..."
                if self.system_message and len(self.system_message) > 100
                else self.system_message
            ),
            "conversation_state": (
                {
                    "current_resource": self.conversation_state.current_resource,
                    "current_operation": self.conversation_state.current_operation,
                    "last_intent": self.conversation_state.last_intent,
                }
                if hasattr(self, "conversation_state")
                else None
            ),
            "capabilities": [
                "conversation_history",
                "intent_analysis",
                "context_awareness",
                "system_message_support",
                "streaming_responses",
            ],
        }

    async def debug_conversation_state(self) -> Dict[str, Any]:
        """Debug method to inspect conversation state and memory"""
        try:
            # Get conversation history
            history = await self.get_conversation_history(limit=10, include_metadata=True)

            # Get conversation state
            conv_state = (
                self.get_conversation_state() if hasattr(self, "get_conversation_state") else None
            )

            # Get memory info
            memory_info = {}
            if self.memory and hasattr(self.memory, "debug_session_keys"):
                memory_info = self.memory.debug_session_keys(
                    session_id=self.context.session_id, conversation_id=self.context.conversation_id
                )

            return {
                "agent_info": {
                    "agent_id": self.agent_id,
                    "session_id": self.context.session_id,
                    "conversation_id": self.context.conversation_id,
                    "user_id": self.context.user_id,
                },
                "conversation_history": {
                    "total_messages": len(history),
                    "recent_messages": [
                        {
                            "type": msg.get("message_type"),
                            "content_preview": msg.get("content", "")[:50] + "...",
                            "timestamp": msg.get("timestamp"),
                        }
                        for msg in history[-5:]
                    ],
                },
                "conversation_state": conv_state.__dict__ if conv_state else None,
                "memory_info": memory_info,
                "system_message_active": bool(self.system_message),
                "llm_service_available": bool(self.llm_service),
            }

        except Exception as e:
            return {
                "error": str(e),
                "agent_id": self.agent_id,
                "session_id": self.context.session_id,
            }
