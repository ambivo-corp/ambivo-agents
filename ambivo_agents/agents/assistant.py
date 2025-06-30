# AssistantAgent with BaseAgentHistoryMixin
import json
import uuid
from typing import Dict, Any

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
                             context: ExecutionContext) -> str:
        """Route request based on intent analysis"""
        primary_intent = intent_analysis.get("primary_intent", "question")
        requires_context = intent_analysis.get("requires_context", False)

        # Route based on primary intent
        if primary_intent == "greeting":
            return "Hello! How can I assist you today?"

        elif primary_intent == "farewell":
            return "Thank you for using the assistant. Have a great day!"

        elif primary_intent == "continuation":
            # Handle context references
            conversation_context = self._get_conversation_context_summary()
            if self.llm_service:
                prompt = f"""The user is referring to our previous conversation. Provide a helpful response based on the context.

Previous conversation:
{conversation_context}

Current user message: {user_message}

Please provide a helpful, contextual response."""
                return await self.llm_service.generate_response(prompt)
            else:
                return f"I understand you're referring to our previous conversation. Could you provide more specific details about what you'd like help with?"

        elif primary_intent in ["question", "request"]:
            # Build context-aware prompt for LLM
            if requires_context:
                conversation_context = self._get_conversation_context_summary()
                context_prompt = f"\n\nConversation context:\n{conversation_context}\n\n"
            else:
                context_prompt = ""

            if self.llm_service:
                prompt = f"""You are a helpful assistant. Respond to this user message appropriately.{context_prompt}User message: {user_message}

Please provide a helpful, accurate, and contextual response."""
                return await self.llm_service.generate_response(prompt)
            else:
                if requires_context:
                    return f"I understand you're asking about something related to our previous conversation. How can I help you with '{user_message}'?"
                else:
                    return f"I understand you said: '{user_message}'. How can I help you with that?"

        else:
            # Default handling
            if self.llm_service:
                prompt = f"""You are a helpful assistant. Respond to this user message: {user_message}"""
                return await self.llm_service.generate_response(prompt)
            else:
                return f"I understand you said: '{user_message}'. How can I help you with that?"

    async def process_message(self, message: AgentMessage, context: ExecutionContext = None) -> AgentMessage:
        """Process user requests with conversation history"""
        self.memory.store_message(message)

        try:
            user_message = message.content

            # Update conversation state
            self.update_conversation_state(user_message)

            # Get conversation context for LLM analysis
            conversation_context = self._get_conversation_context_summary()

            # Use LLM to analyze intent
            intent_analysis = await self._analyze_intent(user_message, conversation_context)

            # Route request based on LLM analysis
            response_content = await self._route_request(intent_analysis, user_message, context)

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


