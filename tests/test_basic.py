#!/usr/bin/env python3
"""
Simple integration test for Ambivo Agents
Uses dynamic agent_config.yaml created by GitHub Actions
"""

import pytest
import asyncio
import sys
import os

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

try:
    from ambivo_agents import KnowledgeBaseAgent
except ImportError as e:
    pytest.skip(f"ambivo_agents not available: {e}", allow_module_level=True)


class TestBasicIntegration:
    """Simple integration tests using real agents and cloud services"""

    @pytest.mark.asyncio
    async def test_agent_creation(self):
        """Test that we can create a real agent"""
        # Create agent using dynamic config (agent_config.yaml created by GitHub Actions)
        agent, context = KnowledgeBaseAgent.create(user_id="test_user")

        # Basic assertions
        assert context.user_id == "test_user"
        assert context.session_id is not None
        assert agent.agent_id is not None

        print(f"✅ Created agent {agent.agent_id} for user {context.user_id}")
        print(f"📋 Session: {context.session_id}")

        # Cleanup
        await agent.cleanup_session()

    @pytest.mark.asyncio
    async def test_knowledge_base_workflow(self):
        """Test basic knowledge base workflow (based on one_liner_examples.py)"""
        agent, context = KnowledgeBaseAgent.create(user_id="kb_test_user")

        try:
            # Ingest some text
            result = await agent._ingest_text(
                kb_name="simple_test_kb",
                input_text="Ambivo is an AI company that builds intelligent automation platforms.",
                custom_meta={"source": "simple_test"}
            )

            assert result['success'] is True
            print("✅ Text ingested successfully")

            # Query the knowledge base
            answer = await agent._query_knowledge_base(
                kb_name="simple_test_kb",
                query="What does Ambivo do?"
            )

            assert answer['success'] is True
            assert "Ambivo" in answer['answer']
            print(f"💬 Answer: {answer['answer']}")

        finally:
            # Always cleanup
            await agent.cleanup_session()


if __name__ == "__main__":
    # Run tests directly
    pytest.main([__file__, "-v"])