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
        # STRONG signals — explicit imperatives fire alone.
        "Synthesize a comprehensive overview of recent advances in quantum error correction from multiple sources",
        "synthesize the findings from my notes",
        "Please synthesize the research on transformer scaling",
        "synthesis: what's the history of neural network architectures",
        "/synthesis find me key findings on LLM evaluation",
        # MEDIUM signals — these must ALSO have a research-flavor indicator
        # (advances / history / analysis / trends / overview / review / etc.)
        # for the fast-path to fire.
        "Give me a comprehensive research report on RLHF",         # comprehensive research + research report
        "Provide a comprehensive overview of graph neural networks",  # comprehensive overview + overview
        "I need a multi-source analysis of climate policy trends",  # multi-source + analysis/trends
        "research thoroughly the history of CRISPR",                # research thoroughly + history
        "research comprehensively the state of quantum computing",  # research comprehensively + state of
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
        # Trivial / off-topic queries — must NOT steal the synthesis route.
        "What is quantum error correction?",
        "Tell me about the latest news",
        "Find information about transformers",
        "Look up the release date of Python 3.13",
        # Regression: the "sky discriminator" query was used earlier in
        # development to verify the fast-path was firing at all, but it's
        # not actually a legitimate synthesis use case. After tightening
        # the fast-path, medium signals ("from multiple sources") alone
        # should no longer route to synthesis without a research indicator.
        "from multiple sources tell me what color the sky is",
        # Other medium-signal phrases without a research indicator — fall
        # through to LLM routing so the assistant can handle general Q&A.
        "Pull this together from multiple sources please",
        "compare multiple sources on this",
        "give me info from multiple sources",
    ],
)
def test_non_synthesis_queries_fall_through(message):
    """Trivial / ambiguous queries should return None so the LLM can decide."""
    m = _mock(["knowledge_synthesis", "web_search", "assistant"])
    result = ModeratorAgent._fast_route_check(m, message)
    assert result is None, f"expected fall-through for: {message!r}"


def test_synthesis_signal_without_synthesis_agent_falls_through():
    """If knowledge_synthesis isn't wired into this session, don't pretend it is."""
    m = _mock(["web_search", "assistant"])
    result = ModeratorAgent._fast_route_check(m, "synthesize the findings from multiple sources")
    assert result is None


def test_synthesis_prefix_strong_signal_fires_without_research_indicator():
    """Explicit 'synthesis:' prefix is a strong signal and should fire even
    on a query that doesn't otherwise look research-like."""
    m = _mock(["knowledge_synthesis", "assistant"])
    result = ModeratorAgent._fast_route_check(m, "synthesis: what are your favorite colors")
    assert result is not None
    assert result["primary_agent"] == "knowledge_synthesis"


def test_slash_synthesis_prefix_strong_signal_fires():
    """/synthesis prefix is an escape hatch for deterministic routing."""
    m = _mock(["knowledge_synthesis", "assistant"])
    result = ModeratorAgent._fast_route_check(m, "/synthesis tell me something")
    assert result is not None
    assert result["primary_agent"] == "knowledge_synthesis"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
