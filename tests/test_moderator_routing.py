#!/usr/bin/env python3
"""
Unit tests for ModeratorAgent._fast_route_check.

These tests exercise the deterministic fast-path routing in isolation without
requiring an LLM service, Redis, or any infrastructure. The method only reads
self.specialized_agents (a dict) and the user message, so we can call it on a
minimal mock.
"""

from unittest.mock import MagicMock

import pytest

from ambivo_agents.agents.moderator import ModeratorAgent


def _mock(specialized_agents):
    """Return a mock that exposes `specialized_agents` — enough for _fast_route_check."""
    m = MagicMock(spec=ModeratorAgent)
    m.specialized_agents = {name: object() for name in specialized_agents}
    return m


# ---------------------------------------------------------------------------
# Existing web_scraper fast-path
# ---------------------------------------------------------------------------

def test_scrape_with_url_routes_to_web_scraper():
    m = _mock(["web_scraper", "assistant"])
    result = ModeratorAgent._fast_route_check(m, "scrape https://example.com and summarize")
    assert result is not None
    assert result["primary_agent"] == "web_scraper"
    assert result["confidence"] >= 0.9


def test_scrape_without_url_falls_through():
    m = _mock(["web_scraper", "assistant"])
    result = ModeratorAgent._fast_route_check(m, "scrape the content of that site")
    assert result is None


def test_scrape_with_url_but_no_scraper_agent_falls_through():
    m = _mock(["assistant"])
    result = ModeratorAgent._fast_route_check(m, "scrape https://example.com")
    assert result is None


# ---------------------------------------------------------------------------
# New knowledge_synthesis fast-path
# ---------------------------------------------------------------------------

@pytest.mark.parametrize(
    "message",
    [
        "Synthesize a comprehensive overview of recent advances in quantum error correction from multiple sources",
        "synthesize the findings from my notes",
        "Please synthesize the research on transformer scaling",
        "Give me a comprehensive research report on RLHF",
        "Provide a comprehensive overview of graph neural networks",
        "I need a multi-source analysis of climate policy trends",
        "Pull this together from multiple sources please",
        "research thoroughly the history of CRISPR",
        "research comprehensively the state of quantum computing",
    ],
)
def test_synthesis_signals_route_to_knowledge_synthesis(message):
    m = _mock(["knowledge_synthesis", "web_search", "assistant"])
    result = ModeratorAgent._fast_route_check(m, message)
    assert result is not None, f"expected fast-path match for: {message!r}"
    assert result["primary_agent"] == "knowledge_synthesis"
    assert result["confidence"] >= 0.9


@pytest.mark.parametrize(
    "message",
    [
        "What is quantum error correction?",
        "Tell me about the latest news",
        "Find information about transformers",
        "Look up the release date of Python 3.13",
    ],
)
def test_non_synthesis_queries_fall_through(message):
    """Ambiguous / non-synthesis queries should return None so the LLM can decide."""
    m = _mock(["knowledge_synthesis", "web_search", "assistant"])
    result = ModeratorAgent._fast_route_check(m, message)
    assert result is None, f"expected fall-through for: {message!r}"


def test_synthesis_signal_without_synthesis_agent_falls_through():
    """If knowledge_synthesis isn't wired into this session, don't pretend it is."""
    m = _mock(["web_search", "assistant"])
    result = ModeratorAgent._fast_route_check(m, "synthesize the findings from multiple sources")
    assert result is None


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
