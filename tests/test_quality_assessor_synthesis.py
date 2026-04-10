#!/usr/bin/env python3
"""
Unit tests for ResponseQualityAssessor._synthesize_response.

Verifies the fix for the bug where the assessor would return raw sub-agent
content verbatim (e.g. "**Academic Search Results for:**") instead of calling
the LLM to synthesize a clean answer. The fix removes the short-circuit on
`len(responses) == 1` and `should_combine_responses == False` so the LLM
synthesis path always runs when responses exist.

Tests use mocks — no LLM, Redis, or infrastructure required.
"""

from unittest.mock import AsyncMock, MagicMock

import pytest

from ambivo_agents.agents.response_quality_assessor import (
    ResponseQualityAssessor,
    ResponseSource,
    SourceResponse,
)


def _make_assessor(llm_return=None, llm_raises=None):
    """Build a mock ResponseQualityAssessor with a stubbed llm_service.

    Either `llm_return` (the string the LLM returns) or `llm_raises` (an
    exception the LLM call raises) can be supplied, not both.
    """
    mock = MagicMock(spec=ResponseQualityAssessor)
    mock.llm_service = MagicMock()
    mock.logger = MagicMock()
    if llm_raises is not None:
        mock.llm_service.generate_response = AsyncMock(side_effect=llm_raises)
    else:
        mock.llm_service.generate_response = AsyncMock(return_value=llm_return)
    return mock


# ---------------------------------------------------------------------------
# Zero responses
# ---------------------------------------------------------------------------

async def test_synthesize_empty_returns_empty_string():
    mock = _make_assessor(llm_return="should not be called")
    result = await ResponseQualityAssessor._synthesize_response(mock, "Q?", [], {})
    assert result == ""
    assert not mock.llm_service.generate_response.called


# ---------------------------------------------------------------------------
# Single response — must still synthesize via LLM (core regression)
# ---------------------------------------------------------------------------

async def test_synthesize_single_response_calls_llm_and_returns_llm_output():
    """A single response must still go through the LLM, not be returned verbatim.

    This is the core regression test. Before the fix, len(responses) == 1 would
    short-circuit to `responses[0].content`, returning raw formatted
    web_search output like '**Academic Search Results for:**' as the final
    user-facing answer.
    """
    mock = _make_assessor(llm_return="Clean synthesized answer about quantum computing.")

    raw_search_output = (
        "**Academic Search Results for:** quantum error correction\n\n"
        "**Found 2 results:**\n\n"
        "**1. Some paper**\n https://example.com/paper\n Abstract text...\n\n"
        "**Search completed in 0.14s using brave**"
    )
    responses = [
        SourceResponse(
            source=ResponseSource.WEB_SEARCH,
            content=raw_search_output,
            confidence=0.75,
            metadata={},
        )
    ]

    result = await ResponseQualityAssessor._synthesize_response(
        mock,
        "What is quantum error correction?",
        responses,
        # Simulate the LLM assessor saying "don't combine" and "best is 1" — the
        # exact flags that triggered the bug's short-circuit.
        {"should_combine_responses": False, "best_response_index": 1},
    )

    assert mock.llm_service.generate_response.called, \
        "LLM synthesis must run even for a single source"
    assert result == "Clean synthesized answer about quantum computing."
    assert "**Academic Search Results for:**" not in result, \
        "Result must not echo raw web_search formatting"
    assert "**Found" not in result
    assert "**Search completed" not in result


async def test_synthesize_single_response_prompt_contains_single_source_hint():
    """The LLM prompt for a single source should adapt its intro language."""
    mock = _make_assessor(llm_return="answer")
    responses = [
        SourceResponse(
            source=ResponseSource.KNOWLEDGE_BASE,
            content="Some KB chunk",
            confidence=0.9,
            metadata={},
        )
    ]
    await ResponseQualityAssessor._synthesize_response(mock, "Q?", responses, {})

    call_kwargs = mock.llm_service.generate_response.call_args.kwargs
    prompt = call_kwargs["prompt"]
    assert "single source" in prompt.lower()
    assert "Some KB chunk" in prompt
    assert "Q?" in prompt


# ---------------------------------------------------------------------------
# Multiple responses — must synthesize via LLM
# ---------------------------------------------------------------------------

async def test_synthesize_multiple_responses_calls_llm_with_all_sources():
    mock = _make_assessor(llm_return="Combined synthesized answer.")

    responses = [
        SourceResponse(
            source=ResponseSource.WEB_SEARCH,
            content="Web search says X",
            confidence=0.75,
            metadata={},
        ),
        SourceResponse(
            source=ResponseSource.KNOWLEDGE_BASE,
            content="KB says Y",
            confidence=0.9,
            metadata={},
        ),
        SourceResponse(
            source=ResponseSource.WEB_SCRAPE,
            content="Scraped page says Z",
            confidence=0.8,
            metadata={},
        ),
    ]

    result = await ResponseQualityAssessor._synthesize_response(
        mock, "Question?", responses, {"should_combine_responses": True}
    )

    assert result == "Combined synthesized answer."
    assert mock.llm_service.generate_response.called

    # All source contents must appear in the synthesis prompt
    prompt = mock.llm_service.generate_response.call_args.kwargs["prompt"]
    assert "Web search says X" in prompt
    assert "KB says Y" in prompt
    assert "Scraped page says Z" in prompt
    assert f"{len(responses)} sources" in prompt


async def test_synthesize_multiple_responses_ignores_should_combine_false():
    """Even when the LLM assessor says should_combine_responses=False, the
    synthesis LLM call must still run. This flag was part of the old
    short-circuit and is now purely advisory."""
    mock = _make_assessor(llm_return="Synthesized anyway.")

    responses = [
        SourceResponse(source=ResponseSource.WEB_SEARCH, content="A", confidence=0.7, metadata={}),
        SourceResponse(source=ResponseSource.KNOWLEDGE_BASE, content="B", confidence=0.8, metadata={}),
    ]

    result = await ResponseQualityAssessor._synthesize_response(
        mock, "Q?", responses, {"should_combine_responses": False, "best_response_index": 2}
    )

    assert mock.llm_service.generate_response.called
    assert result == "Synthesized anyway."


# ---------------------------------------------------------------------------
# LLM failure fallback
# ---------------------------------------------------------------------------

async def test_synthesize_llm_failure_falls_back_to_best_confidence_content():
    """If the LLM call raises, fall back to the highest-confidence source's
    raw content — the user still gets something."""
    mock = _make_assessor(llm_raises=RuntimeError("LLM timed out"))

    responses = [
        SourceResponse(
            source=ResponseSource.WEB_SEARCH,
            content="lower-confidence content",
            confidence=0.5,
            metadata={},
        ),
        SourceResponse(
            source=ResponseSource.KNOWLEDGE_BASE,
            content="higher-confidence content",
            confidence=0.95,
            metadata={},
        ),
    ]

    result = await ResponseQualityAssessor._synthesize_response(
        mock, "Q?", responses, {}
    )

    assert mock.llm_service.generate_response.called
    assert result == "higher-confidence content"
    # The error should have been logged
    assert mock.logger.error.called


async def test_synthesize_llm_empty_response_falls_back():
    """If the LLM returns an empty string, fall back to best-confidence content."""
    mock = _make_assessor(llm_return="   \n\n  ")  # whitespace-only

    responses = [
        SourceResponse(
            source=ResponseSource.WEB_SEARCH,
            content="raw content here",
            confidence=0.7,
            metadata={},
        )
    ]

    result = await ResponseQualityAssessor._synthesize_response(
        mock, "Q?", responses, {}
    )

    assert result == "raw content here"
    assert mock.logger.warning.called


# ---------------------------------------------------------------------------
# Whitespace stripping
# ---------------------------------------------------------------------------

async def test_synthesize_strips_surrounding_whitespace_from_llm_output():
    mock = _make_assessor(llm_return="\n\n  Answer with surrounding whitespace.  \n\n")
    responses = [
        SourceResponse(source=ResponseSource.WEB_SEARCH, content="x", confidence=0.5, metadata={})
    ]

    result = await ResponseQualityAssessor._synthesize_response(mock, "Q?", responses, {})

    assert result == "Answer with surrounding whitespace."


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
