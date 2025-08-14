#!/usr/bin/env python3
"""
Tests for LLM-based answer sufficiency validation in GatherAgent.
"""
import json
import pytest

from ambivo_agents.agents.gather_agent import GatherAgent


class LocalMemory:
    def __init__(self):
        self._ctx = {}

    async def store_context(self, key, value, conversation_id=None):
        self._ctx[key] = value

    async def get_context(self, key, conversation_id=None):
        return self._ctx.get(key)

    async def clear_memory(self, conversation_id=None):
        self._ctx.clear()


class FakeLLM:
    """Simple stateful fake LLM that returns pre-seeded responses."""

    def __init__(self, outputs):
        # outputs: list of strings to return on successive calls
        self.outputs = list(outputs)

    async def generate_response(self, prompt: str, context=None, system_message: str = None):
        if self.outputs:
            return self.outputs.pop(0)
        # default: sufficient
        return '{"sufficient": true, "feedback": "ok"}'


@pytest.mark.asyncio
async def test_llm_validation_blocks_then_allows(monkeypatch):
    async def fake_submit(self, payload):
        return {"success": True, "status": 200, "response": "ok"}

    monkeypatch.setattr(GatherAgent, "_submit", fake_submit, raising=True)

    # Questionnaire with free-text that requires both email and phone
    questionnaire = {
        "questions": [
            {
                "question_id": "q1",
                "text": "Please provide your contact details.",
                "type": "free-text",
                "required": True,
                "answer_requirements": "Include both your email address and a phone number.",
                "min_answer_length": 5,
            },
            {
                "question_id": "q2",
                "text": "Company size?",
                "type": "single-select",
                "required": True,
                "answer_option_dict_list": [
                    {"value": "1-50", "label": "1-50"},
                    {"value": "51-200", "label": "51-200"},
                ],
            },
        ]
    }

    # Fake LLM will first say insufficient, then sufficient
    fake_llm = FakeLLM([
        '{"sufficient": false, "feedback": "Please include both email and phone."}',
        '{"sufficient": true, "feedback": "Looks good."}',
    ])

    agent = GatherAgent.create_advanced(
        agent_id="gather_llm_check",
        memory_manager=LocalMemory(),
        llm_service=fake_llm,
        config={
            "gather": {
                "submission_endpoint": "http://localhost/void",
                "submission_method": "POST",
                "submission_headers": {"Content-Type": "application/json"},
                "memory_ttl_seconds": 3600,
                "enable_llm_answer_validation": True,
                "answer_validation": {"default_min_length": 3},
            }
        },
    )

    # 1) Provide questionnaire
    r1 = await agent.chat(json.dumps(questionnaire))
    assert "Please provide your contact details" in r1

    # 2) Provide too short answer -> heuristic should block
    r2 = await agent.chat("hi")
    assert "too short" in r2.lower()
    assert "Please provide your contact details" in r2

    # 3) Provide adequate length but missing details -> LLM should block (first fake response)
    r3 = await agent.chat("john@example.com")
    assert "please include both email and phone" in r3.lower()
    assert "Please provide your contact details" in r3

    # 4) Provide both items -> LLM now allows (second fake response), proceed to next question
    r4 = await agent.chat("john@example.com, +1 555 0100")
    assert "Company size?" in r4

    # 5) Finish remaining questions and submit
    r5 = await agent.chat("1-50")
    r6 = await agent.chat("finish")
    assert "Submitting your responses now" in r6
    assert "Status: successfully_collected" in r6
