"""
Brief examples of invoking KnowledgeBaseAgent with multiple knowledge bases.

Note: To actually run cross-KB queries, ensure your knowledge base backend (e.g., Qdrant)
      is configured in agent_config.yaml and that documents have been ingested into
      the target KB collections. These snippets focus on how to pass multiple KBs.
"""
from ambivo_agents.agents.knowledge_base import KnowledgeBaseAgent
from ambivo_agents.core.base import AgentMessage, ExecutionContext

import asyncio


async def demo_with_execution_context():
    """
    Pass multiple KBs via ExecutionContext.metadata using a list of strings.
    """
    kb_agent = KnowledgeBaseAgent()

    # Provide multiple KBs through the ExecutionContext metadata
    context = ExecutionContext(
        user_id="user_123",
        session_id="sess_abc",
        conversation_id="conv_xyz",
        metadata={
            # Supported formats for kb_names:
            # 1) List of strings
            "kb_names": ["product_docs", "engineering_wiki", "hr_policies"],
        },
    )

    # Ask a question across the provided KBs
    user_question = "What is our PTO policy and how does it differ for contractors?"
    response = await kb_agent.process_message(user_question, context=context)
    print("[ExecutionContext] Agent response:\n", response.content)
    if response.metadata:
        print("[ExecutionContext] Metadata:", response.metadata)


async def demo_with_message_metadata():
    """
    Pass multiple KBs via AgentMessage.metadata using a list of dicts
    {kb_name, description}. Description is optional but can help routing.
    """
    kb_agent = KnowledgeBaseAgent()

    # Construct an AgentMessage with kb_names in metadata
    message = AgentMessage(
        id="msg_1",
        sender_id="user_456",
        recipient_id=kb_agent.agent_id,
        content="Summarize our Q3 revenue trends and forecast for Q4.",
        metadata={
            "kb_names": [
                {"kb_name": "finance_reports", "description": "Quarterly and annual financials"},
                {"kb_name": "sales_insights", "description": "Sales KPIs and pipeline analytics"},
                {"kb_name": "exec_briefs"},  # description optional
            ]
        },
    )

    response = await kb_agent.process_message(message)
    print("[Message metadata] Agent response:\n", response.content)
    if response.metadata:
        print("[Message metadata] Metadata:", response.metadata)


async def demo_with_json_string():
    """
    Pass multiple KBs as a JSON string (also supported by the agent's normalizer).
    """
    kb_agent = KnowledgeBaseAgent()

    # JSON string with list of KB objects
    kb_json = (
        "[\n"
        "  {\"kb_name\": \"legal_policies\", \"description\": \"Compliance and contracts\"},\n"
        "  {\"kb_name\": \"vendor_docs\"}\n"
        "]"
    )

    message = AgentMessage(
        id="msg_2",
        sender_id="user_789",
        recipient_id=kb_agent.agent_id,
        content="List key compliance requirements for vendor onboarding.",
        metadata={"kb_names": kb_json},
    )

    response = await kb_agent.process_message(message)
    print("[JSON string] Agent response:\n", response.content)
    if response.metadata:
        print("[JSON string] Metadata:", response.metadata)


if __name__ == "__main__":
    # Run any of the demos as needed. They will work as long as your KB backend is configured
    # and collections exist with ingested documents.
    asyncio.run(demo_with_execution_context())
    # asyncio.run(demo_with_message_metadata())
    # asyncio.run(demo_with_json_string())
