
import json
import uuid
from typing import Dict, Any, AsyncIterator

from ambivo_agents import BaseAgent, AgentRole, ExecutionContext, AgentMessage, MessageType
from ambivo_agents.core.history import BaseAgentHistoryMixin


class AssistantAgent(BaseAgent, BaseAgentHistoryMixin):
    """General purpose assistant agent with conversation history"""

    def __init__(self, agent_id: str = None, memory_manager=None, llm_service=None, **kwargs):
        if agent_id is None:
            agent_id = f"assistant_{str(uuid.uuid4())[:8]}"

        super().__init__(
            agent_id=agent_id,
            role=AgentRole.ASSISTANT,
            memory_manager=memory_manager,
            llm_service=llm_service,
            name="Assistant Agent",
            description="General purpose assistant for user interactions",
            **kwargs
        )

        # Initialize history mixin
        self.setup_history_mixin()


        self.connected_servers = {}



    def _extract_file_path(self, text: str) -> str:
        """Extract file path from text"""
        import re
        # Simple file path extraction
        file_match = re.search(r'(?:read file|open file|show file)\s+["\']?([^"\']+)["\']?', text, re.IGNORECASE)
        if file_match:
            return file_match.group(1)
        return None

    async def _analyze_intent(self, user_message: str, conversation_context: str = "") -> Dict[str, Any]:
        """Analyze user intent with conversation context"""
        if not self.llm_service:
            return self._keyword_based_analysis(user_message)

        prompt = f"""
        Analyze this user message in the context of general assistance:

        Conversation Context:
        {conversation_context}

        Current User Message: {user_message}

        Respond in JSON format:
        {{
            "primary_intent": "question|request|clarification|continuation|greeting|farewell",
            "requires_context": true/false,
            "context_reference": "what user is referring to",
            "topic": "main subject area",
            "confidence": 0.0-1.0
        }}
        """

        try:
            response = await self.llm_service.generate_response(prompt)
            import re
            json_match = re.search(r'\{.*\}', response, re.DOTALL)
            if json_match:
                return json.loads(json_match.group())
            else:
                # Fallback if LLM doesn't return JSON
                return self._keyword_based_analysis(user_message)
        except Exception as e:
            return self._keyword_based_analysis(user_message)

    def _keyword_based_analysis(self, user_message: str) -> Dict[str, Any]:
        """Fallback keyword-based analysis"""
        content_lower = user_message.lower()

        if any(word in content_lower for word in ['hello', 'hi', 'hey']):
            intent = 'greeting'
        elif any(word in content_lower for word in ['bye', 'goodbye', 'thanks']):
            intent = 'farewell'
        elif any(word in content_lower for word in ['what', 'how', 'why', 'when', 'where']):
            intent = 'question'
        elif any(word in content_lower for word in ['can you', 'please', 'help me']):
            intent = 'request'
        elif any(word in content_lower for word in ['that', 'this', 'it', 'previous']):
            intent = 'continuation'
        else:
            intent = 'question'

        return {
            "primary_intent": intent,
            "requires_context": any(word in content_lower for word in ['that', 'this', 'it', 'previous']),
            "context_reference": None,
            "topic": "general",
            "confidence": 0.7
        }

    def _get_conversation_context_summary(self) -> str:
        """Get conversation context summary"""
        try:
            recent_history = self.get_conversation_history_with_context(limit=3)
            context_summary = []

            for msg in recent_history:
                if msg.get('message_type') == 'user_input':
                    content = msg.get('content', '')
                    context_summary.append(f"User said: {content[:50]}...")
                elif msg.get('message_type') == 'agent_response':
                    content = msg.get('content', '')
                    context_summary.append(f"I responded: {content[:50]}...")

            return "\n".join(context_summary) if context_summary else "No previous conversation"
        except:
            return "No previous conversation"

    async def _route_request(self, intent_analysis: Dict[str, Any], user_message: str,
                             context: ExecutionContext, llm_context: Dict[str, Any]) -> str:
        """Route request based on intent analysis - FIXED: Preserves context + MCP integration"""



        # Handle different intent types
        primary_intent = intent_analysis.get("primary_intent", "question")

        if primary_intent == "greeting":
            return "Hello! How can I assist you today?"
        elif primary_intent == "farewell":
            return "Thank you for using the assistant. Have a great day!"

        # For all other intents, use LLM with enhanced context
        if self.llm_service:
            # 🔥 FIX: Enhanced prompt that works with context-aware LLM service
            if intent_analysis.get('requires_context', False):
                context_prompt = f"""You are a helpful assistant. The user has asked: {user_message}

This request references previous conversation. Please provide a helpful, contextual response that acknowledges and builds upon our previous discussion."""
            else:
                context_prompt = f"""You are a helpful assistant. Please respond to: {user_message}

Provide a helpful, accurate response."""

            # 🔥 FIX: Pass conversation history through context - THIS IS THE KEY
            return await self.llm_service.generate_response(
                prompt=context_prompt,
                context=llm_context
                # 🔥 FIX: Context with conversation_history preserves memory across provider switches
            )
        else:
            return f"I understand you said: '{user_message}'. How can I help you with that?"

    async def process_message(self, message: AgentMessage, context: ExecutionContext = None) -> AgentMessage:
        """Process user requests with conversation history - FIXED: Context preserved across LLM provider switches"""
        self.memory.store_message(message)

        try:
            user_message = message.content
            self.update_conversation_state(user_message)

            # 🔥 FIX: Get conversation history for LLM context
            conversation_context = self._get_conversation_context_summary()
            conversation_history = await self.get_conversation_history(limit=5, include_metadata=True)

            # 🔥 FIX: Use LLM to analyze intent WITH CONTEXT
            intent_analysis = await self._analyze_intent(user_message, conversation_context)

            # 🔥 FIX: Build LLM context with conversation history
            llm_context = {
                'conversation_id': message.conversation_id,
                'user_id': message.sender_id,
                'conversation_history': conversation_history,  # 🔥 KEY FIX: Include history
                'intent_analysis': intent_analysis,

            }

            # 🔥 FIX: Route request with preserved context
            response_content = await self._route_request(intent_analysis, user_message, context, llm_context)

            response = self.create_response(
                content=response_content,
                recipient_id=message.sender_id,
                session_id=message.session_id,
                conversation_id=message.conversation_id
            )

            self.memory.store_message(response)
            return response

        except Exception as e:
            error_response = self.create_response(
                content=f"I encountered an error processing your request: {str(e)}",
                recipient_id=message.sender_id,
                message_type=MessageType.ERROR,
                session_id=message.session_id,
                conversation_id=message.conversation_id
            )
            return error_response

    async def process_message_stream(self, message: AgentMessage, context: ExecutionContext = None) -> AsyncIterator[
        str]:
        """Stream processing for AssistantAgent - FIXED: Context preserved across LLM provider switches"""
        self.memory.store_message(message)

        try:
            user_message = message.content
            self.update_conversation_state(user_message)

            # 🔥 FIX: Get conversation history for streaming context
            conversation_context = self._get_conversation_context_summary()
            conversation_history = await self.get_conversation_history(limit=5, include_metadata=True)

            intent_analysis = await self._analyze_intent(user_message, conversation_context)

            # 🔥 FIX: Build LLM context with conversation history for streaming
            llm_context = {
                'conversation_id': message.conversation_id,
                'user_id': message.sender_id,
                'conversation_history': conversation_history,  # 🔥 KEY FIX
                'intent_analysis': intent_analysis,
                'streaming': True,

            }

            # Route and stream response with context
            if self.llm_service:
                # Build context-aware prompt
                if intent_analysis.get('requires_context', False):
                    context_prompt = f"""You are a helpful assistant. The user has asked: {user_message}

This request references previous conversation. Please provide a helpful, contextual response that acknowledges and builds upon our previous discussion."""
                else:
                    context_prompt = f"""You are a helpful assistant. Please respond to: {user_message}

Provide a helpful, accurate response."""

                # 🔥 FIX: Stream with conversation context preserved
                async for chunk in self.llm_service.generate_response_stream(
                        prompt=context_prompt,
                        context=llm_context  # 🔥 CRITICAL: Context preserves memory across provider switches
                ):
                    yield chunk
            else:
                # Fallback for no LLM service
                yield f"I understand you said: '{user_message}'. How can I help you with that?"

        except Exception as e:
            yield f"Assistant error: {str(e)}"