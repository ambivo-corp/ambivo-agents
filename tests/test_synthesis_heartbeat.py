#!/usr/bin/env python3
"""
Unit tests for KnowledgeSynthesisAgent.process_message_stream heartbeat behavior.

Verifies that long-running synthesis (60-120s+ in production) emits periodic
status heartbeats on the SSE stream so intermediate proxies with idle-based
timeouts don't kill the connection. Tests use mocks with a controlled synthesis
latency so the heartbeat interval can be driven to produce observable ticks
without waiting 20s in real time.
"""

import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from ambivo_agents.agents.knowledge_synthesis import KnowledgeSynthesisAgent
from ambivo_agents.core.base import StreamSubType


async def _consume_stream(gen):
    """Collect all StreamChunks from an async generator."""
    chunks = []
    async for chunk in gen:
        chunks.append(chunk)
    return chunks


async def _delayed_result(delay_seconds, result):
    """Helper: return `result` after awaiting a small sleep."""
    await asyncio.sleep(delay_seconds)
    return result


async def test_stream_fast_synthesis_no_heartbeats():
    """When synthesis finishes before the first heartbeat interval, no
    heartbeat chunks should be emitted — just the normal START, CONTENT,
    COMPLETE flow."""
    mock = MagicMock(spec=KnowledgeSynthesisAgent)
    mock.agent_id = "test_agent"

    # Fast synthesis — returns immediately
    mock.process_with_quality_assessment = AsyncMock(return_value={
        'response': 'fast answer',
        'quality_assessment': {},
        'query_analysis': {},
        'metadata': {},
    })

    gen = KnowledgeSynthesisAgent.process_message_stream(mock, "query")
    chunks = await _consume_stream(gen)

    # Should have START + content chunks + COMPLETE — no heartbeats
    heartbeats = [c for c in chunks if c.metadata.get("heartbeat") is True]
    assert not heartbeats, f"expected no heartbeats for fast synthesis, got {len(heartbeats)}"

    # Should still have the normal chunks: START + CONTENT + COMPLETE
    from ambivo_agents.core.base import SSEEventType
    event_types = [c.event_type for c in chunks]
    assert SSEEventType.START in event_types
    assert SSEEventType.COMPLETE in event_types


async def test_stream_slow_synthesis_emits_heartbeats():
    """When synthesis exceeds the heartbeat interval, status chunks with
    heartbeat=True should be emitted at each tick. We patch the module-level
    heartbeat logic by using a short synthesis delay and a low asyncio.wait
    timeout override."""
    mock = MagicMock(spec=KnowledgeSynthesisAgent)
    mock.agent_id = "test_agent"

    synthesis_result = {
        'response': 'delayed answer',
        'quality_assessment': {},
        'query_analysis': {},
        'metadata': {},
    }

    # Synthesis takes ~0.25s
    async def slow_synthesis(*args, **kwargs):
        await asyncio.sleep(0.25)
        return synthesis_result

    mock.process_with_quality_assessment = AsyncMock(side_effect=slow_synthesis)

    # Patch asyncio.wait so the timeout parameter is effectively shortened.
    # This forces the heartbeat loop to tick at ~0.1s intervals without
    # changing the production heartbeat_interval constant.
    import ambivo_agents.agents.knowledge_synthesis as ks_mod
    original_wait = asyncio.wait

    async def fast_wait(aws, *, timeout=None, **kwargs):
        # Cap the timeout to 0.1s for the test
        if timeout is not None and timeout > 0.1:
            timeout = 0.1
        return await original_wait(aws, timeout=timeout, **kwargs)

    with patch.object(ks_mod.asyncio, "wait", side_effect=fast_wait):
        gen = KnowledgeSynthesisAgent.process_message_stream(mock, "query")
        chunks = await _consume_stream(gen)

    heartbeats = [c for c in chunks if c.metadata.get("heartbeat") is True]
    assert len(heartbeats) >= 1, \
        f"expected at least 1 heartbeat for 0.25s synthesis at 0.1s interval, got {len(heartbeats)}"

    # Each heartbeat should have a stage and elapsed_seconds
    for hb in heartbeats:
        assert hb.metadata.get("stage") == "synthesizing"
        assert isinstance(hb.metadata.get("elapsed_seconds"), (int, float))
        assert hb.sub_type == StreamSubType.STATUS


async def test_stream_synthesis_exception_propagates():
    """If synthesis raises, the exception should propagate out of the stream
    generator — not silently hang or return empty."""
    mock = MagicMock(spec=KnowledgeSynthesisAgent)
    mock.agent_id = "test_agent"
    mock.process_with_quality_assessment = AsyncMock(
        side_effect=RuntimeError("synthesis failure")
    )

    gen = KnowledgeSynthesisAgent.process_message_stream(mock, "query")

    with pytest.raises(RuntimeError, match="synthesis failure"):
        await _consume_stream(gen)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
