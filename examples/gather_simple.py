"""
examples/gather_simple.py
A minimal example demonstrating the conversational GatherAgent.

This script simulates a short form-filling conversation:
1) Provide a small questionnaire (inline JSON)
2) Agent asks the first question
3) We answer
4) We finish and agent submits the collected answers

To keep the example self-contained and not require Redis/LLM, we:
- Use create_advanced with a tiny in-memory memory manager (LocalMemory)
- Patch the submission endpoint to a placeholder; tests monkeypatch _submit
"""
import asyncio
import json
from typing import List, Optional, Any, Dict

from ambivo_agents.agents.gather_agent import GatherAgent
from ambivo_agents.core.base import AgentMessage, MessageType


class LocalMemory:
    """Very small async in-memory key/value store implementing the subset
    of MemoryManagerInterface used by GatherAgent (store_context/get_context).
    """
    def __init__(self):
        self._ctx: Dict[str, Any] = {}

    async def store_context(self, key: str, value: Any, conversation_id: Optional[str] = None):
        self._ctx[key] = value

    async def get_context(self, key: str, conversation_id: Optional[str] = None):
        return self._ctx.get(key)

    async def clear_memory(self, conversation_id: Optional[str] = None):
        self._ctx.clear()


DEFAULT_QUESTIONNAIRE = {
    "questions": [
        {
            "question_id": "q1",
            "text": "Are antivirus tools used in your environment?",
            "type": "yes-no",
            "required": True,
            "answer_option_dict_list": [
                {"value": "Yes", "label": "Yes"},
                {"value": "No", "label": "No"},
            ],
        },
        {
            "question_id": "q2",
            "text": "Which antivirus vendor(s) do you use?",
            "type": "free-text",
            "is_conditional": True,
            "parent_question_id": "q1",
            "required": False,
        },
    ]
}


async def run_demo(questionnaire: dict | None = None) -> List[str]:
    """Run a short conversation with GatherAgent and return response texts."""
    qn = questionnaire or DEFAULT_QUESTIONNAIRE

    # Create agent with minimal config and local memory
    agent = GatherAgent.create_advanced(
        agent_id="gather_demo",
        memory_manager=LocalMemory(),
        llm_service=None,  # no LLM needed for deterministic prompts
        config={
            "gather": {
                # The test will monkeypatch _submit to avoid real network calls
                "submission_endpoint": "http://localhost/void",
                "submission_method": "POST",
                "submission_headers": {"Content-Type": "application/json"},
                "memory_ttl_seconds": 3600,
            }
        },
    )

    responses: List[str] = []

    # 1) Provide the questionnaire JSON to the agent
    msg1 = AgentMessage(
        id="m1",
        sender_id="user_demo",
        recipient_id=agent.agent_id,
        content=json.dumps(qn),
        message_type=MessageType.USER_INPUT,
        session_id=agent.context.session_id,
        conversation_id=agent.context.conversation_id,
    )
    r1 = await agent.process_message(msg1)
    responses.append(r1.content)

    # 2) Answer the first question with "Yes" so the conditional question is prompted
    msg2 = AgentMessage(
        id="m2",
        sender_id="user_demo",
        recipient_id=agent.agent_id,
        content="Yes",
        message_type=MessageType.USER_INPUT,
        session_id=agent.context.session_id,
        conversation_id=agent.context.conversation_id,
    )
    r2 = await agent.process_message(msg2)
    responses.append(r2.content)

    # 3) Instead of answering the conditional question, ask the agent to finish.
    #    This demonstrates the manual submission path with partial status.
    msg3 = AgentMessage(
        id="m3",
        sender_id="user_demo",
        recipient_id=agent.agent_id,
        content="finish",
        message_type=MessageType.USER_INPUT,
        session_id=agent.context.session_id,
        conversation_id=agent.context.conversation_id,
    )
    r3 = await agent.process_message(msg3)
    responses.append(r3.content)

    return responses


if __name__ == "__main__":
    out = asyncio.run(run_demo())
    print("\n".join(out))
