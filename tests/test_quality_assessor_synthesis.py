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


# ---------------------------------------------------------------------------
# assess_response integration — ensures LOW-quality responses still go through
# the LLM synthesis path (the second short-circuit fix shipped in v2.0.7)
# ---------------------------------------------------------------------------

async def test_assess_response_poor_quality_still_calls_synthesis():
    """Regression test for the second short-circuit bug: when the assessor
    scores responses as POOR/UNACCEPTABLE, assess_response used to skip
    _synthesize_response entirely and return raw best-response content.

    This caused technical queries against /kh/chat to return raw
    '**Academic Search Results for:**' output because brave's mixed-quality
    results triggered a low assessor score. This test simulates that exact
    scenario and verifies the LLM synthesis is still called.
    """
    # Build a concrete ResponseQualityAssessor without hitting BaseAgent.__init__
    # (which requires Redis, etc.). Instead, mock everything and call
    # assess_response via the unbound method.
    mock = MagicMock(spec=ResponseQualityAssessor)
    mock.llm_service = MagicMock()
    mock.logger = MagicMock()
    mock.system_message = "assessor system message"

    # Quality thresholds — same defaults as ResponseQualityAssessor.__init__
    mock.quality_thresholds = {
        'excellent': 0.9,
        'good': 0.75,
        'fair': 0.6,
        'poor': 0.4,
    }
    mock.source_weights = {
        ResponseSource.KNOWLEDGE_BASE: 0.9,
        ResponseSource.WEB_SEARCH: 0.7,
        ResponseSource.WEB_SCRAPE: 0.8,
        ResponseSource.COMBINED: 1.0,
    }

    # First LLM call: assessment (returns JSON scoring the response as POOR).
    # Second LLM call: the synthesis call we want to verify happens.
    assessment_json = (
        '{"overall_assessment": "Mixed-quality search results", '
        '"relevance_score": 0.3, "completeness_score": 0.2, '
        '"accuracy_score": 0.3, "clarity_score": 0.4, '
        '"strengths": [], "weaknesses": ["off-topic result"], '
        '"recommendations": [], "missing_information": [], '
        '"best_response_index": 1, "should_combine_responses": false, '
        '"suggested_improvements": "gather more sources"}'
    )
    synthesis_output = "Clean synthesized prose answer about the topic."

    mock.llm_service.generate_response = AsyncMock(
        side_effect=[assessment_json, synthesis_output]
    )

    # Delegate helper methods to their real implementations via bound method
    # wrappers so _calculate_confidence etc. work as intended.
    mock._build_assessment_prompt = lambda q, r, p: (
        ResponseQualityAssessor._build_assessment_prompt(mock, q, r, p)
    )
    mock._parse_assessment = lambda c: (
        ResponseQualityAssessor._parse_assessment(mock, c)
    )
    mock._calculate_confidence = lambda r, a: (
        ResponseQualityAssessor._calculate_confidence(mock, r, a)
    )
    mock._determine_quality_level = lambda c: (
        ResponseQualityAssessor._determine_quality_level(mock, c)
    )
    mock._suggest_additional_sources = lambda r, a: (
        ResponseQualityAssessor._suggest_additional_sources(mock, r, a)
    )

    # _synthesize_response is the thing we want to verify runs. Use a real
    # AsyncMock so we can assert it was called.
    real_synthesize = AsyncMock(return_value=synthesis_output)
    mock._synthesize_response = real_synthesize

    responses = [
        SourceResponse(
            source=ResponseSource.WEB_SEARCH,
            content=(
                "**Academic Search Results for:** quantum error correction\n"
                "**Found 2 results:**\n"
                "... raw web search output ..."
            ),
            confidence=0.75,
            metadata={},
        )
    ]

    result = await ResponseQualityAssessor.assess_response(
        mock, "What are recent advances in quantum error correction?", responses
    )

    # Confirm the quality was POOR (sanity check that we hit the old
    # short-circuit's trigger condition)
    from ambivo_agents.agents.response_quality_assessor import QualityLevel
    assert result.quality_level in (QualityLevel.POOR, QualityLevel.UNACCEPTABLE), (
        f"Expected POOR/UNACCEPTABLE to exercise the fix, got {result.quality_level}"
    )

    # The critical assertion: _synthesize_response MUST have been called
    assert real_synthesize.called, (
        "_synthesize_response must be called even when quality_level is POOR"
    )

    # And the returned final_response must be the synthesis output, NOT the
    # raw web_search content
    assert result.final_response == synthesis_output
    assert "**Academic Search Results for:**" not in result.final_response


async def test_assess_response_empty_responses_returns_apology():
    """When there are no responses at all, _synthesize_response is not called
    and we return the stock 'couldn't find' message."""
    mock = MagicMock(spec=ResponseQualityAssessor)
    mock.llm_service = MagicMock()
    mock.logger = MagicMock()
    mock.system_message = "assessor system message"
    mock.quality_thresholds = {
        'excellent': 0.9, 'good': 0.75, 'fair': 0.6, 'poor': 0.4,
    }
    mock.source_weights = {
        ResponseSource.KNOWLEDGE_BASE: 0.9,
        ResponseSource.WEB_SEARCH: 0.7,
        ResponseSource.WEB_SCRAPE: 0.8,
        ResponseSource.COMBINED: 1.0,
    }

    # Only the assessment LLM call happens (synthesis is not called for empty)
    mock.llm_service.generate_response = AsyncMock(
        return_value='{"relevance_score": 0.0, "completeness_score": 0.0, '
                     '"accuracy_score": 0.0, "clarity_score": 0.0, '
                     '"should_combine_responses": false, "best_response_index": 1}'
    )

    mock._build_assessment_prompt = lambda q, r, p: (
        ResponseQualityAssessor._build_assessment_prompt(mock, q, r, p)
    )
    mock._parse_assessment = lambda c: (
        ResponseQualityAssessor._parse_assessment(mock, c)
    )
    mock._calculate_confidence = lambda r, a: (
        ResponseQualityAssessor._calculate_confidence(mock, r, a)
    )
    mock._determine_quality_level = lambda c: (
        ResponseQualityAssessor._determine_quality_level(mock, c)
    )
    mock._suggest_additional_sources = lambda r, a: (
        ResponseQualityAssessor._suggest_additional_sources(mock, r, a)
    )
    mock._synthesize_response = AsyncMock(return_value="should not be called")

    result = await ResponseQualityAssessor.assess_response(mock, "Q?", [])

    assert not mock._synthesize_response.called
    assert "couldn't find" in result.final_response.lower()


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
