# ambivo_agents/agents/assistant.py
"""
Assistant Agent for general purpose assistance.
"""

import logging
import uuid
from typing import Dict, Any

from ..core.base import BaseAgent, AgentRole, AgentMessage, MessageType, ExecutionContext


class AssistantAgent(BaseAgent):
    """General purpose assistant agent"""

    def __init__(self, agent_id: str| None = None, memory_manager=None, llm_service=None, **kwargs):
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

    async def process_message(self, message: AgentMessage, context: ExecutionContext) -> AgentMessage:
        """Process user requests and provide assistance"""
        self.memory.store_message(message)

        try:
            history = self.memory.get_recent_messages(limit=10, conversation_id=message.conversation_id)

            conversation_context = "\n".join([
                f"{msg.get('sender_id', 'unknown')}: {msg.get('content', '')}"
                for msg in reversed(history[-5:]) if isinstance(msg, dict)
            ])

            if self.llm_service:
                prompt = f"""You are an AI assistant. Based on the conversation context below, provide a helpful response.

Conversation context:
{conversation_context}

Current user message: {message.content}

Please provide a helpful, accurate, and contextual response."""

                response_content = await self.llm_service.generate_response(
                    prompt=prompt,
                    context={'conversation_id': message.conversation_id, 'user_id': context.user_id}
                )
            else:
                response_content = f"I understand you said: '{message.content}'. How can I help you with that?"

            response = self.create_response(
                content=response_content,
                recipient_id=message.sender_id,
                session_id=message.session_id,
                conversation_id=message.conversation_id
            )

            self.memory.store_message(response)
            return response

        except Exception as e:
            logging.error(f"Assistant agent error: {e}")
            error_response = self.create_response(
                content=f"I encountered an error processing your request: {str(e)}",
                recipient_id=message.sender_id,
                message_type=MessageType.ERROR,
                session_id=message.session_id,
                conversation_id=message.conversation_id
            )
            return error_response

