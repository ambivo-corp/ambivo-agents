#!/usr/bin/env python3
"""
Basic integration test for Ambivo Agents.
Requires Qdrant and knowledge extras — skips gracefully if unavailable.
"""

import pytest

try:
    from ambivo_agents import KnowledgeBaseAgent
except ImportError:
    pytest.skip("ambivo_agents not available", allow_module_level=True)


class TestBasicIntegration:
    """Integration tests using real agents and cloud services."""

    @pytest.mark.asyncio
    @pytest.mark.integration
    async def test_agent_creation(self):
        """Test that we can create a KnowledgeBaseAgent with real config."""
        try:
            agent, context = KnowledgeBaseAgent.create(user_id="test_user")
        except RuntimeError as e:
            pytest.skip(f"KnowledgeBase infrastructure not available: {e}")

        assert context.user_id == "test_user"
        assert context.session_id is not None
        assert agent.agent_id is not None

        await agent.cleanup_session()


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
