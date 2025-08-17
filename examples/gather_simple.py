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
            "text": "What is your preferred security vendor?",
            "type": "single-select",
            "is_conditional": True,
            "parent_question_id": "q1",
            "required": False,
            "answer_option_dict_list": [
                {"value": "crowdstrike", "label": "CrowdStrike"},
                {"value": "microsoft", "label": "Microsoft Defender"},
                {"value": "symantec", "label": "Symantec"},
                {"value": "other", "label": "Other"},
            ],
        },
        {
            "question_id": "q3",
            "text": "Which compliance standards do you follow?",
            "type": "multi-select",
            "required": True,
            "answer_option_dict_list": [
                {"value": "soc2", "label": "SOC 2"},
                {"value": "iso27001", "label": "ISO 27001"},
                {"value": "pci", "label": "PCI DSS"},
                {"value": "hipaa", "label": "HIPAA"},
            ],
        },
    ]
}


async def run_demo(questionnaire: dict | None = None, enable_nlp: bool = False) -> List[str]:
    """Run a short conversation with GatherAgent and return response texts.
    
    Args:
        questionnaire: Optional custom questionnaire
        enable_nlp: Whether to enable natural language parsing
    """
    qn = questionnaire or DEFAULT_QUESTIONNAIRE

    # Create agent with optional natural language parsing
    if enable_nlp:
        # Use create_simple for auto-configured LLM when NLP is enabled
        agent = GatherAgent.create_simple(
            user_id="gather_demo",
            config={
                "gather": {
                    "submission_endpoint": "http://localhost/void",
                    "submission_method": "POST",
                    "submission_headers": {"Content-Type": "application/json"},
                    "memory_ttl_seconds": 3600,
                    "enable_natural_language_parsing": True,  # Enable NLP
                }
            },
        )
    else:
        # Create agent with minimal config and local memory
        agent = GatherAgent.create_advanced(
            agent_id="gather_demo",
            memory_manager=LocalMemory(),
            llm_service=None,  # no LLM needed for deterministic prompts
            config={
                "gather": {
                    "submission_endpoint": "http://localhost/void",
                    "submission_method": "POST",
                    "submission_headers": {"Content-Type": "application/json"},
                    "memory_ttl_seconds": 3600,
                    "enable_natural_language_parsing": False,
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

    # 2) Answer the first question - use natural language if enabled
    answer_content = "Absolutely, we have multiple tools!" if enable_nlp else "Yes"
    msg2 = AgentMessage(
        id="m2",
        sender_id="user_demo",
        recipient_id=agent.agent_id,
        content=answer_content,
        message_type=MessageType.USER_INPUT,
        session_id=agent.context.session_id,
        conversation_id=agent.context.conversation_id,
    )
    r2 = await agent.process_message(msg2)
    responses.append(r2.content)

    # 3) Answer the conditional question (single-select) - natural language if enabled
    if "preferred security vendor" in r2.content:
        answer_content = "I'd go with Microsoft Defender" if enable_nlp else "microsoft"
        msg3 = AgentMessage(
            id="m3",
            sender_id="user_demo",
            recipient_id=agent.agent_id,
            content=answer_content,
            message_type=MessageType.USER_INPUT,
            session_id=agent.context.session_id,
            conversation_id=agent.context.conversation_id,
        )
        r3 = await agent.process_message(msg3)
        responses.append(r3.content)
    
    # 4) Answer the multi-select question - natural language if enabled
    answer_content = "We need both SOC 2 and ISO certification" if enable_nlp else "soc2, iso27001"
    msg4 = AgentMessage(
        id="m4",
        sender_id="user_demo",
        recipient_id=agent.agent_id,
        content=answer_content,
        message_type=MessageType.USER_INPUT,
        session_id=agent.context.session_id,
        conversation_id=agent.context.conversation_id,
    )
    r4 = await agent.process_message(msg4)
    responses.append(r4.content)

    return responses


async def demo_comparison():
    """Show the difference between strict and natural language modes"""
    print("=" * 70)
    print("GatherAgent Demo: Strict vs Natural Language Modes")
    print("=" * 70)
    
    print("\n1. STRICT MODE (Default):")
    print("-" * 30)
    strict_responses = await run_demo(enable_nlp=False)
    print("User answers: 'Yes', 'microsoft', 'soc2, iso27001'")
    print("Agent accepts exact matches only.\n")
    
    print("\n2. NATURAL LANGUAGE MODE:")
    print("-" * 30)
    print("User answers: 'Absolutely, we have multiple tools!', ")
    print("              'I'd go with Microsoft Defender',")
    print("              'We need both SOC 2 and ISO certification'")
    
    # Only run NLP demo if LLM is configured
    try:
        nlp_responses = await run_demo(enable_nlp=True)
        print("Agent understands conversational responses!\n")
    except Exception as e:
        print(f"Note: Natural language mode requires LLM configuration: {e}\n")
    
    print("=" * 70)
    print("Configuration:")
    print("  gather:")
    print("    enable_natural_language_parsing: true  # or false")
    print("\nOr via environment variable:")
    print("  export AMBIVO_AGENTS_GATHER_ENABLE_NATURAL_LANGUAGE_PARSING=true")
    print("=" * 70)


if __name__ == "__main__":
    # Run comparison demo
    asyncio.run(demo_comparison())
