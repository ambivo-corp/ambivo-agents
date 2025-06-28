# examples/specialized_agents.py
"""
Example using specialized agents directly
"""

import asyncio
from ambivo_agents import (
    AgentFactory,
    create_redis_memory_manager,
    create_multi_provider_llm_service
)
from ambivo_agents.core.base import AgentRole, AgentMessage, MessageType, ExecutionContext


async def main():
    """Specialized agents example"""

    # Create shared components
    memory = create_redis_memory_manager("demo-agent")
    llm_service = create_multi_provider_llm_service()

    # Create different agent types
    assistant = AgentFactory.create_agent(
        role=AgentRole.ASSISTANT,
        agent_id="assistant-demo",
        memory_manager=memory,
        llm_service=llm_service
    )

    code_executor = AgentFactory.create_agent(
        role=AgentRole.CODE_EXECUTOR,
        agent_id="executor-demo",
        memory_manager=memory,
        llm_service=llm_service
    )

    # Create message and context
    message = AgentMessage(
        id="msg-1",
        sender_id="user-demo",
        recipient_id="assistant-demo",
        content="Hello! Can you explain what you do?",
        message_type=MessageType.USER_INPUT
    )

    context = ExecutionContext(
        session_id="demo-session",
        conversation_id="demo-conv",
        user_id="user-demo",
        tenant_id="demo-tenant"
    )

    # Process with assistant
    print("🤖 Assistant Agent:")
    response = await assistant.process_message(message, context)
    print(f"   {response.content}")

    # Process code with executor
    code_message = AgentMessage(
        id="msg-2",
        sender_id="user-demo",
        recipient_id="executor-demo",
        content="```python\nimport math\nprint(f'Pi is approximately {math.pi:.2f}')\n```",
        message_type=MessageType.USER_INPUT
    )

    print("\n⚙️ Code Executor Agent:")
    code_response = await code_executor.process_message(code_message, context)
    print(f"   {code_response.content}")


if __name__ == "__main__":
    asyncio.run(main())
