#!/usr/bin/env python3
"""
Unit tests for WebSearchServiceAdapter parallel-provider behavior.

Verifies the v2.0.8 behavior:
  - search_web fans out to all configured providers in parallel
  - results are merged, deduped by canonicalized URL, and interleaved
  - a single provider failure does not kill the merged result
  - the 3-result format cap is gone
  - _canonicalize_url normalizes host case, www prefix, trailing slashes,
    and strips common tracking params

Tests avoid hitting any real HTTP endpoint by patching the provider-level
search helpers directly.
"""

from datetime import datetime
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from ambivo_agents.agents.web_search import (
    SearchResponse,
    SearchResult,
    WebSearchServiceAdapter,
)


# ---------------------------------------------------------------------------
# URL canonicalization
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "url_a,url_b",
    [
        # Case-insensitive host
        ("https://example.com/page", "https://EXAMPLE.COM/page"),
        # www. prefix
        ("https://example.com/page", "https://www.example.com/page"),
        # Trailing slash
        ("https://example.com/page", "https://example.com/page/"),
        # Tracking param stripping
        (
            "https://example.com/page?q=foo",
            "https://example.com/page?q=foo&utm_source=twitter&fbclid=abc",
        ),
        # All combined
        (
            "https://example.com/path",
            "https://WWW.Example.com/path/?utm_campaign=x&gclid=y",
        ),
    ],
)
def test_canonicalize_url_treats_variants_as_same(url_a, url_b):
    assert WebSearchServiceAdapter._canonicalize_url(url_a) == \
        WebSearchServiceAdapter._canonicalize_url(url_b), \
        f"{url_a!r} and {url_b!r} should canonicalize to the same value"


def test_canonicalize_url_preserves_distinct_paths():
    a = WebSearchServiceAdapter._canonicalize_url("https://example.com/a")
    b = WebSearchServiceAdapter._canonicalize_url("https://example.com/b")
    assert a != b


def test_canonicalize_url_handles_empty_and_garbage():
    assert WebSearchServiceAdapter._canonicalize_url("") == ""
    # Garbage input should not raise, even if the result isn't pretty
    result = WebSearchServiceAdapter._canonicalize_url("not a url")
    assert isinstance(result, str)


# ---------------------------------------------------------------------------
# _merge_search_responses — dedup and interleaving
# ---------------------------------------------------------------------------


def _make_result(title: str, url: str, rank: int, score: float = 1.0) -> SearchResult:
    return SearchResult(
        title=title,
        url=url,
        snippet=f"snippet for {title}",
        source="test",
        rank=rank,
        score=score,
        timestamp=datetime.now(),
    )


def _make_response(provider: str, results: list, status: str = "success") -> SearchResponse:
    return SearchResponse(
        query="test",
        results=results,
        total_results=len(results),
        search_time=0.1,
        provider=provider,
        status=status,
    )


def _adapter_stub():
    """Build a WebSearchServiceAdapter without calling __init__ (which needs config)."""
    return WebSearchServiceAdapter.__new__(WebSearchServiceAdapter)


def test_merge_dedupes_overlapping_urls_between_providers():
    adapter = _adapter_stub()

    brave = _make_response("brave", [
        _make_result("Paper A", "https://example.com/a", rank=1),
        _make_result("Paper B", "https://example.com/b", rank=2),
    ])
    aves = _make_response("aves", [
        _make_result("Paper A alt", "https://www.example.com/a/", rank=1),  # dupe of brave #1
        _make_result("Paper C", "https://example.com/c", rank=2),
    ])

    merged = adapter._merge_search_responses([brave, aves], max_results=10)

    # Should be 3 unique: A (brave won), B (brave), C (aves)
    assert len(merged) == 3
    urls = [r.url for r in merged]
    assert "https://example.com/a" in urls
    assert "https://example.com/b" in urls
    assert "https://example.com/c" in urls


def test_merge_interleaves_providers_round_robin():
    """Ensure both providers get early-position representation in the merged list."""
    adapter = _adapter_stub()

    brave = _make_response("brave", [
        _make_result(f"brave{i}", f"https://brave.example/{i}", rank=i + 1)
        for i in range(5)
    ])
    aves = _make_response("aves", [
        _make_result(f"aves{i}", f"https://aves.example/{i}", rank=i + 1)
        for i in range(5)
    ])

    merged = adapter._merge_search_responses([brave, aves], max_results=10)

    # Round-robin: brave0, aves0, brave1, aves1, ...
    assert merged[0].url == "https://brave.example/0"
    assert merged[1].url == "https://aves.example/0"
    assert merged[2].url == "https://brave.example/1"
    assert merged[3].url == "https://aves.example/1"


def test_merge_respects_max_results():
    adapter = _adapter_stub()

    brave = _make_response("brave", [
        _make_result(f"b{i}", f"https://b.example/{i}", rank=i + 1)
        for i in range(20)
    ])
    aves = _make_response("aves", [
        _make_result(f"a{i}", f"https://a.example/{i}", rank=i + 1)
        for i in range(20)
    ])

    merged = adapter._merge_search_responses([brave, aves], max_results=7)
    assert len(merged) == 7


def test_merge_skips_failed_providers():
    adapter = _adapter_stub()

    success = _make_response("brave", [
        _make_result("ok", "https://example.com/ok", rank=1)
    ])
    failed = SearchResponse(
        query="test",
        results=[],
        total_results=0,
        search_time=0.0,
        provider="aves",
        status="error",
        error="rate limited",
    )

    merged = adapter._merge_search_responses([success, failed], max_results=10)
    assert len(merged) == 1
    assert merged[0].url == "https://example.com/ok"


def test_merge_returns_empty_when_all_providers_failed():
    adapter = _adapter_stub()

    failed_a = SearchResponse(
        query="test", results=[], total_results=0, search_time=0.0,
        provider="brave", status="error", error="network",
    )
    failed_b = SearchResponse(
        query="test", results=[], total_results=0, search_time=0.0,
        provider="aves", status="error", error="auth",
    )

    merged = adapter._merge_search_responses([failed_a, failed_b], max_results=10)
    assert merged == []


# ---------------------------------------------------------------------------
# search_web fan-out — verify parallel dispatch to all providers
# ---------------------------------------------------------------------------


async def test_search_web_fans_out_to_all_providers():
    """Both brave and aves safe-wrappers should be invoked for each search."""
    adapter = _adapter_stub()
    adapter.providers = {
        "brave": {
            "name": "brave", "api_key": "x", "base_url": "https://brave",
            "priority": 2, "available": True, "rate_limit_delay": 0,
        },
        "aves": {
            "name": "aves", "api_key": "x", "base_url": "https://aves",
            "priority": 1, "available": True, "rate_limit_delay": 0,
        },
    }

    brave_resp = _make_response("brave", [
        _make_result("brave_result", "https://brave.example/1", rank=1)
    ])
    aves_resp = _make_response("aves", [
        _make_result("aves_result", "https://aves.example/1", rank=1)
    ])

    brave_mock = AsyncMock(return_value=brave_resp)
    aves_mock = AsyncMock(return_value=aves_resp)

    with patch.object(adapter, "_search_brave_safe", brave_mock), \
         patch.object(adapter, "_search_aves_safe", aves_mock):
        result = await adapter.search_web("test query", max_results=10)

    assert brave_mock.called, "brave was not called"
    assert aves_mock.called, "aves was not called"
    assert result.status == "success"
    assert len(result.results) == 2
    assert "brave" in result.provider and "aves" in result.provider


async def test_search_web_succeeds_with_one_provider_failing():
    """If brave fails and aves succeeds, the merged response should still be successful."""
    adapter = _adapter_stub()
    adapter.providers = {
        "brave": {"name": "brave", "api_key": "x", "priority": 2, "available": True, "rate_limit_delay": 0},
        "aves": {"name": "aves", "api_key": "x", "priority": 1, "available": True, "rate_limit_delay": 0},
    }

    brave_failed = SearchResponse(
        query="test", results=[], total_results=0, search_time=0.0,
        provider="brave", status="error", error="network",
    )
    aves_ok = _make_response("aves", [
        _make_result("ok", "https://aves.example/ok", rank=1)
    ])

    with patch.object(adapter, "_search_brave_safe", AsyncMock(return_value=brave_failed)), \
         patch.object(adapter, "_search_aves_safe", AsyncMock(return_value=aves_ok)):
        result = await adapter.search_web("q", max_results=10)

    assert result.status == "success"
    assert len(result.results) == 1
    assert result.results[0].url == "https://aves.example/ok"


async def test_search_web_returns_error_when_all_providers_fail():
    adapter = _adapter_stub()
    adapter.providers = {
        "brave": {"name": "brave", "api_key": "x", "priority": 2, "available": True, "rate_limit_delay": 0},
        "aves": {"name": "aves", "api_key": "x", "priority": 1, "available": True, "rate_limit_delay": 0},
    }

    err_a = SearchResponse(
        query="q", results=[], total_results=0, search_time=0.0,
        provider="brave", status="error", error="network",
    )
    err_b = SearchResponse(
        query="q", results=[], total_results=0, search_time=0.0,
        provider="aves", status="error", error="auth",
    )

    with patch.object(adapter, "_search_brave_safe", AsyncMock(return_value=err_a)), \
         patch.object(adapter, "_search_aves_safe", AsyncMock(return_value=err_b)):
        result = await adapter.search_web("q", max_results=10)

    assert result.status == "error"
    assert result.results == []


async def test_search_web_empty_providers_returns_error():
    adapter = _adapter_stub()
    adapter.providers = {}

    result = await adapter.search_web("q", max_results=10)
    assert result.status == "error"
    assert "No search provider configured" in (result.error or "")


async def test_search_web_skips_providers_in_cooldown():
    adapter = _adapter_stub()
    import time
    adapter.providers = {
        "brave": {
            "name": "brave", "api_key": "x", "priority": 2,
            "available": False,
            "cooldown_until": time.time() + 600,  # cooldown active
            "rate_limit_delay": 0,
        },
        "aves": {
            "name": "aves", "api_key": "x", "priority": 1,
            "available": True, "rate_limit_delay": 0,
        },
    }

    aves_ok = _make_response("aves", [_make_result("ok", "https://aves.example/ok", rank=1)])

    brave_mock = AsyncMock()  # should NOT be called
    with patch.object(adapter, "_search_brave_safe", brave_mock), \
         patch.object(adapter, "_search_aves_safe", AsyncMock(return_value=aves_ok)):
        result = await adapter.search_web("q", max_results=10)

    assert not brave_mock.called, "brave should be skipped due to cooldown"
    assert result.status == "success"
    assert len(result.results) == 1


# ---------------------------------------------------------------------------
# _format_search_results — the 3-result cap is gone
# ---------------------------------------------------------------------------


def test_format_search_results_shows_all_results_not_just_three():
    """v2.0.8 removes the hardcoded top-3 cap in _format_search_results."""
    from ambivo_agents.agents.web_search import WebSearchAgent

    # Build a mock that has enough attributes for _format_search_results
    # (it's a pure method that only touches the result dict).
    mock = MagicMock(spec=WebSearchAgent)

    result_dict = {
        "success": True,
        "query": "test",
        "results": [
            {"title": f"Result {i}", "url": f"https://example.com/{i}",
             "snippet": f"snippet {i}"}
            for i in range(10)
        ],
        "provider": "multi",
        "search_time": 0.5,
    }

    formatted = WebSearchAgent._format_search_results(mock, result_dict, "General Search")

    # All 10 results should appear in the formatted output
    for i in range(10):
        assert f"Result {i}" in formatted, f"Result {i} missing from formatted output"
        assert f"https://example.com/{i}" in formatted

    # The header should reflect the count
    assert "Found 10 results" in formatted


def test_format_search_results_snippet_preview_length_is_400():
    from ambivo_agents.agents.web_search import WebSearchAgent

    mock = MagicMock(spec=WebSearchAgent)
    long_snippet = "x" * 500  # over the 400-char cap
    result_dict = {
        "success": True,
        "query": "test",
        "results": [
            {"title": "T", "url": "https://example.com/",
             "snippet": long_snippet},
        ],
        "provider": "brave",
        "search_time": 0.1,
    }

    formatted = WebSearchAgent._format_search_results(mock, result_dict, "General Search")

    # The truncated preview should be exactly 400 chars + "..." (since original > 400)
    # The old behavior was 150 chars.
    snippet_line = [line for line in formatted.split("\n") if "xxx" in line][0]
    # Count the actual 'x' characters on that line
    x_count = snippet_line.count("x")
    assert x_count == 400, f"expected 400 x chars, got {x_count} (old cap was 150)"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
