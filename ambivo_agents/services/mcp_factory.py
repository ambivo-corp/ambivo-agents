from typing import Union, TypeVar, Protocol, runtime_checkable
from ambivo_agents.agents.assistant import AssistantAgent
from ambivo_agents.agents.code_executor import CodeExecutorAgent


# Better return type annotations
class MCPAgentFactory:
    """Factory for creating MCP-enabled agent types with proper typing"""

    @staticmethod
    async def create_assistant_with_filesystem(user_id: str = None,
                                               filesystem_path: str = "/tmp") -> AssistantAgent:
        """
        CORRECTED: Return AssistantAgent (more specific than BaseAgent)
        The hybrid class inherits from AssistantAgent, so this is accurate
        """
        agent = AssistantAgent.create_with_mcp(user_id=user_id)

        # Execute MCP setup
        if hasattr(agent, '_mcp_setup_task'):
            await agent._mcp_setup_task()

        # Connect filesystem
        if agent.has_mcp_capabilities():
            await agent.connect_mcp_server(
                "filesystem",
                "npx",
                ["@modelcontextprotocol/server-filesystem", filesystem_path]
            )
            #logging.info(f"✅ Assistant with filesystem MCP ready: {filesystem_path}")

        return agent  # This is actually AssistantAgent + MCPIntegratedAgent

    @staticmethod
    async def create_code_executor_with_filesystem(user_id: str = None,
                                                   filesystem_path: str = "/tmp") -> CodeExecutorAgent:
        """Return CodeExecutorAgent with MCP capabilities"""
        agent = CodeExecutorAgent.create_with_mcp(user_id=user_id)

        if hasattr(agent, '_mcp_setup_task'):
            await agent._mcp_setup_task()

        if agent.has_mcp_capabilities():
            await agent.connect_mcp_server(
                "filesystem",
                "npx",
                ["@modelcontextprotocol/server-filesystem", filesystem_path]
            )

        return agent