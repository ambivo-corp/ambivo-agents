#!/usr/bin/env python3
"""
Test that GatherAgent can load a questionnaire from a URL (using requests fallback when aiohttp is unavailable)
"""
import json
import pytest

from ambivo_agents.agents.gather_agent import GatherAgent
import ambivo_agents.core.base as base_mod


class LocalMemory:
    def __init__(self):
        self._ctx = {}

    async def store_context(self, key, value, conversation_id=None):
        self._ctx[key] = value

    async def get_context(self, key, conversation_id=None):
        return self._ctx.get(key)

    async def clear_memory(self, conversation_id=None):
        self._ctx.clear()


@pytest.mark.asyncio
async def test_gather_loads_questionnaire_from_url(monkeypatch):
    # Force aiohttp-unavailable path to exercise requests fallback
    monkeypatch.setattr(base_mod, "AIOHTTP_AVAILABLE", False, raising=False)

    # Patch submission to avoid network
    async def fake_submit(self, payload):
        return {"success": True, "status": 200, "response": "ok"}

    monkeypatch.setattr(GatherAgent, "_submit", fake_submit, raising=True)

    # Sample questionnaire to be returned by requests.get
    questionnaire = {
        "questions": [
            {
                "question_id": "q1",
                "text": "Do you use any cloud providers?",
                "type": "yes-no",
                "required": True,
                "answer_option_dict_list": [
                    {"value": "Yes", "label": "Yes"},
                    {"value": "No", "label": "No"},
                ],
            },
            {
                "question_id": "q2",
                "text": "What is your company size?",
                "type": "single-select",
                "required": True,
                "answer_option_dict_list": [
                    {"value": "1-50", "label": "1-50"},
                    {"value": "51-200", "label": "51-200"},
                ],
            },
        ]
    }

    class FakeResp:
        def __init__(self, text, status_code=200, headers=None, encoding="utf-8"):
            self.text = text
            self.status_code = status_code
            self.headers = headers or {"Content-Type": "application/json"}
            self.encoding = encoding

        def raise_for_status(self):
            if not (200 <= self.status_code < 300):
                raise RuntimeError(f"HTTP {self.status_code}")

        @property
        def ok(self):
            return 200 <= self.status_code < 300

    # Monkeypatch requests.get to return our fake JSON
    def fake_requests_get(url, timeout=15):
        return FakeResp(json.dumps(questionnaire))

    # Patch in the requests module in base module scope
    import types
    fake_requests_mod = types.SimpleNamespace(get=fake_requests_get)
    monkeypatch.setattr(base_mod, "requests", fake_requests_mod, raising=False)
    # Ensure REQUESTS_AVAILABLE is True
    monkeypatch.setattr(base_mod, "REQUESTS_AVAILABLE", True, raising=False)

    # Create agent
    agent = GatherAgent.create_advanced(
        agent_id="gather_url_test",
        memory_manager=LocalMemory(),
        llm_service=None,
        config={
            "gather": {
                "submission_endpoint": "http://localhost/void",
                "submission_method": "POST",
                "submission_headers": {"Content-Type": "application/json"},
                "memory_ttl_seconds": 3600,
            }
        },
    )

    # Provide a URL; agent should fetch and ask first question
    url = "http://example.invalid/q.json"
    first_prompt = await agent.chat(url)
    assert "Do you use any cloud providers?" in first_prompt
