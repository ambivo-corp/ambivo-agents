# ambivo_agents/mcp/agent_integration.py
"""
Integration between MCP and Ambivo Agents
"""

import logging
from typing import Dict, Any, Optional

# Import MCP availability check and client
try:
    from . import MCP_AVAILABLE

    if MCP_AVAILABLE:
        from .client import MCPAgentClient
    else:
        MCPAgentClient = None
except ImportError:
    MCP_AVAILABLE = False
    MCPAgentClient = None

from ..core.base import BaseAgent, AgentMessage, MessageType, ExecutionContext


class MCPIntegratedAgent(BaseAgent):
    """Agent that can use MCP tools and resources"""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        # Initialize MCP client if available
        if MCP_AVAILABLE and MCPAgentClient:
            try:
                self.mcp_client = MCPAgentClient()
                self.mcp_enabled = True
            except Exception as e:
                self.logger.warning(f"Failed to initialize MCP client: {e}")
                self.mcp_client = None
                self.mcp_enabled = False
        else:
            self.mcp_client = None
            self.mcp_enabled = False

        self.connected_servers: Dict[str, Dict[str, Any]] = {}

        if not self.mcp_enabled:
            self.logger.info("MCP not available - agent will work without MCP features")

    async def connect_mcp_server(self, server_name: str, command: str, args: list = None) -> bool:
        """Connect to an external MCP server"""
        if not self.mcp_client:
            self.logger.warning("MCP not available")
            return False

        try:
            success = await self.mcp_client.connect_to_server(server_name, command, args)
            if success:
                # Cache server capabilities
                tools = await self.mcp_client.list_tools(server_name)

                # Check if client has list_resources method (not all MCP clients do)
                resources = []
                if hasattr(self.mcp_client, 'list_resources'):
                    try:
                        resources = await self.mcp_client.list_resources(server_name)
                    except Exception as e:
                        self.logger.warning(f"Could not list resources from {server_name}: {e}")

                self.connected_servers[server_name] = {
                    "tools": tools,
                    "resources": resources
                }

                self.logger.info(
                    f"Connected to MCP server {server_name} with {len(tools)} tools and {len(resources)} resources"
                )

            return success

        except Exception as e:
            self.logger.error(f"Failed to connect to MCP server {server_name}: {e}")
            return False

    async def use_mcp_tool(self, server_name: str, tool_name: str, arguments: Dict[str, Any]) -> str:
        """Use a tool from a connected MCP server"""
        if not self.mcp_client or server_name not in self.connected_servers:
            raise ValueError(f"Not connected to MCP server: {server_name}")

        try:
            return await self.mcp_client.call_tool(server_name, tool_name, arguments)
        except Exception as e:
            self.logger.error(f"Failed to call MCP tool {tool_name} on {server_name}: {e}")
            raise

    async def get_mcp_resource(self, server_name: str, uri: str) -> str:
        """Get a resource from a connected MCP server"""
        if not self.mcp_client or server_name not in self.connected_servers:
            raise ValueError(f"Not connected to MCP server: {server_name}")

        # Check if client has read_resource method
        if not hasattr(self.mcp_client, 'read_resource'):
            raise ValueError(f"MCP client does not support resource reading")

        try:
            return await self.mcp_client.read_resource(server_name, uri)
        except Exception as e:
            self.logger.error(f"Failed to read MCP resource {uri} from {server_name}: {e}")
            raise

    def list_mcp_capabilities(self) -> Dict[str, Any]:
        """List all available MCP capabilities"""
        capabilities = {}
        for server_name, server_info in self.connected_servers.items():
            capabilities[server_name] = {
                "tools": [tool["name"] for tool in server_info["tools"]],
                "resources": [resource["uri"] for resource in server_info["resources"]] if server_info[
                    "resources"] else []
            }
        return capabilities

    def is_mcp_enabled(self) -> bool:
        """Check if MCP is enabled for this agent"""
        return self.mcp_enabled

    def get_mcp_status(self) -> Dict[str, Any]:
        """Get detailed MCP status for this agent"""
        return {
            "mcp_available": MCP_AVAILABLE,
            "mcp_enabled": self.mcp_enabled,
            "mcp_client_initialized": self.mcp_client is not None,
            "connected_servers": list(self.connected_servers.keys()),
            "total_tools": sum(len(info["tools"]) for info in self.connected_servers.values()),
            "total_resources": sum(len(info["resources"]) for info in self.connected_servers.values()),
        }

    async def disconnect_mcp_server(self, server_name: str) -> bool:
        """Disconnect from an MCP server"""
        if not self.mcp_client or server_name not in self.connected_servers:
            return False

        try:
            if hasattr(self.mcp_client, 'disconnect'):
                await self.mcp_client.disconnect(server_name)

            del self.connected_servers[server_name]
            self.logger.info(f"Disconnected from MCP server: {server_name}")
            return True

        except Exception as e:
            self.logger.error(f"Failed to disconnect from MCP server {server_name}: {e}")
            return False

    async def disconnect_all_mcp_servers(self):
        """Disconnect from all MCP servers"""
        for server_name in list(self.connected_servers.keys()):
            await self.disconnect_mcp_server(server_name)


# ============================================================================
# Enhanced Agent Classes with MCP Integration
# ============================================================================

class MCPEnabledAssistantAgent(MCPIntegratedAgent):
    """Assistant Agent with MCP capabilities"""

    async def process_message(self, message: AgentMessage, context: ExecutionContext = None) -> AgentMessage:
        """Process message with potential MCP tool usage"""

        # Try to handle with MCP tools first if available
        if self.mcp_enabled and self.connected_servers:
            mcp_response = await self._try_mcp_handling(message)
            if mcp_response:
                return mcp_response

        # Fall back to regular processing
        # This would call the parent class process_message
        # You'd need to import and inherit from your actual AssistantAgent
        from ..agents.assistant import AssistantAgent
        return await super(AssistantAgent, self).process_message(message, context)

    async def _try_mcp_handling(self, message: AgentMessage) -> Optional[AgentMessage]:
        """Try to handle message using MCP tools"""
        content = message.content.lower()

        # File operations
        if any(keyword in content for keyword in ['read file', 'open file', 'show file']):
            if 'filesystem' in self.connected_servers:
                return await self._handle_file_request(message)

        # GitHub operations
        if any(keyword in content for keyword in ['github', 'repository', 'repo']):
            if 'github' in self.connected_servers:
                return await self._handle_github_request(message)

        return None

    async def _handle_file_request(self, message: AgentMessage) -> AgentMessage:
        """Handle file operations via MCP"""
        try:
            # Simple file path extraction (you'd want more sophisticated parsing)
            import re
            file_match = re.search(r'(?:read|open|show)\s+(?:file\s+)?["\']?([^"\']+)["\']?', message.content)

            if file_match:
                file_path = file_match.group(1)
                result = await self.use_mcp_tool('filesystem', 'read_file', {'path': file_path})

                return self.create_response(
                    content=f"File content:\n\n```\n{result}\n```",
                    recipient_id=message.sender_id,
                    session_id=message.session_id,
                    conversation_id=message.conversation_id
                )

        except Exception as e:
            return self.create_response(
                content=f"Failed to read file: {str(e)}",
                recipient_id=message.sender_id,
                message_type=MessageType.ERROR,
                session_id=message.session_id,
                conversation_id=message.conversation_id
            )

        return None

    # Complete the missing methods in agent_integration.py

    async def _handle_github_request(self, message: AgentMessage) -> AgentMessage:
        """Handle GitHub operations via MCP - COMPLETED"""
        try:
            content = message.content.lower()

            # Extract GitHub-specific information
            import re

            # Handle different GitHub operations
            if 'list repositories' in content or 'list repos' in content:
                result = await self.use_mcp_tool('github', 'list_repositories', {})

            elif 'get repository' in content or 'repo info' in content:
                # Extract repo name from message
                repo_match = re.search(r'(?:repository|repo)\s+([^\s]+)', message.content)
                if repo_match:
                    repo_name = repo_match.group(1)
                    result = await self.use_mcp_tool('github', 'get_repository', {'name': repo_name})
                else:
                    return self.create_response(
                        content="Please specify the repository name",
                        recipient_id=message.sender_id,
                        session_id=message.session_id,
                        conversation_id=message.conversation_id
                    )

            elif 'create issue' in content:
                # Extract title and body (simplified)
                title_match = re.search(r'title[:\s]+([^\n]+)', message.content, re.IGNORECASE)
                body_match = re.search(r'(?:body|description)[:\s]+([^\n]+)', message.content, re.IGNORECASE)

                if title_match:
                    title = title_match.group(1).strip()
                    body = body_match.group(1).strip() if body_match else ""
                    result = await self.use_mcp_tool('github', 'create_issue', {
                        'title': title,
                        'body': body
                    })
                else:
                    return self.create_response(
                        content="Please specify issue title and description",
                        recipient_id=message.sender_id,
                        session_id=message.session_id,
                        conversation_id=message.conversation_id
                    )
            else:
                # List available GitHub tools
                tools = self.connected_servers.get('github', {}).get('tools', {})
                tool_names = list(tools.keys())
                result = f"Available GitHub operations: {', '.join(tool_names)}"

            return self.create_response(
                content=f"GitHub operation result:\n\n{result}",
                recipient_id=message.sender_id,
                session_id=message.session_id,
                conversation_id=message.conversation_id
            )

        except Exception as e:
            return self.create_response(
                content=f"GitHub operation failed: {str(e)}",
                recipient_id=message.sender_id,
                message_type=MessageType.ERROR,
                session_id=message.session_id,
                conversation_id=message.conversation_id
            )

    async def _handle_database_request(self, user_message: str) -> str:
        """Handle database operations via MCP - NEW METHOD"""
        message_lower = user_message.lower()

        try:
            if 'query' in message_lower or 'select' in message_lower:
                # Extract SQL query (simple pattern)
                import re
                sql_match = re.search(r'(?:query|sql)[:\s]+(.+)', user_message, re.IGNORECASE | re.DOTALL)
                if sql_match:
                    query = sql_match.group(1).strip()
                    result = await self.use_mcp_tool('sqlite', 'execute_query', {'query': query})
                    return f"Query result:\n\n{result}"
                else:
                    return "Please provide the SQL query to execute."

            elif 'schema' in message_lower or 'tables' in message_lower:
                result = await self.use_mcp_tool('sqlite', 'get_schema', {})
                return f"Database schema:\n\n{result}"

            else:
                available_tools = list(self.connected_servers['sqlite']['tools'].keys())
                return f"Database tools available: {', '.join(available_tools)}"

        except Exception as e:
            return f"Database operation failed: {str(e)}"

    def _extract_file_path(self, text: str) -> Optional[str]:
        """Extract file path from text - UTILITY METHOD"""
        import re

        # Look for quoted file paths
        quoted_match = re.search(r'["\']([^"\']+)["\']', text)
        if quoted_match:
            return quoted_match.group(1)

        # Look for common file patterns
        file_patterns = [
            r'(?:file|path)[:\s]+([^\s]+)',
            r'([^\s]+\.(?:txt|py|js|md|json|csv|log))',
            r'(?:/[^\s]+)',  # Unix paths
            r'(?:[A-Z]:\\[^\s]+)'  # Windows paths
        ]

        for pattern in file_patterns:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                return match.group(1)

        return None

    def _extract_directory_path(self, text: str) -> Optional[str]:
        """Extract directory path from text - UTILITY METHOD"""
        import re

        # Look for directory indicators
        dir_patterns = [
            r'(?:directory|dir|folder)[:\s]+([^\s]+)',
            r'(?:list|show)(?:\s+(?:files\s+)?(?:in\s+)?)?([^\s]+)',
            r'([^\s]+/)$'  # Ends with slash
        ]

        for pattern in dir_patterns:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                return match.group(1)

        return None

    # Enhanced auto-routing with better patterns
    async def auto_route_to_mcp(self, user_message: str) -> Optional[str]:
        """Enhanced auto-routing with better pattern matching"""
        if not self.connected_servers:
            return None

        message_lower = user_message.lower()

        # File operations with better patterns
        file_operations = {
            'read': ['read file', 'open file', 'show file', 'cat ', 'view file'],
            'write': ['write file', 'save file', 'create file'],
            'list': ['list files', 'show files', 'ls ', 'dir ', 'list directory'],
            'exists': ['file exists', 'check file', 'does file exist']
        }

        for operation, patterns in file_operations.items():
            if any(pattern in message_lower for pattern in patterns):
                if 'filesystem' in self.connected_servers:
                    return await self._handle_filesystem_request(user_message)

        # GitHub operations with better patterns
        github_patterns = [
            'github', 'repository', 'repo ', 'pull request', 'pr ', 'issue',
            'commit', 'branch', 'fork', 'clone', 'git '
        ]
        if any(pattern in message_lower for pattern in github_patterns):
            if 'github' in self.connected_servers:
                return await self._handle_github_request_direct(user_message)

        # Database operations
        db_patterns = [
            'database', 'sql', 'query', 'table', 'sqlite', 'select',
            'insert', 'update', 'delete', 'schema'
        ]
        if any(pattern in message_lower for pattern in db_patterns):
            if 'sqlite' in self.connected_servers:
                return await self._handle_database_request(user_message)

        return None

    async def _handle_github_request_direct(self, user_message: str) -> str:
        """Direct GitHub request handler for auto-routing"""
        # This would be similar to _handle_github_request but return string directly
        # Implementation would mirror the AgentMessage version but simpler
        try:
            content = user_message.lower()

            if 'list repositories' in content:
                result = await self.use_mcp_tool('github', 'list_repositories', {})
                return f"Repositories:\n{result}"
            elif 'repository info' in content:
                # Extract repo name and get info
                import re
                repo_match = re.search(r'(?:repository|repo)\s+([^\s]+)', user_message)
                if repo_match:
                    repo_name = repo_match.group(1)
                    result = await self.use_mcp_tool('github', 'get_repository', {'name': repo_name})
                    return f"Repository {repo_name}:\n{result}"
                else:
                    return "Please specify the repository name"
            else:
                tools = self.connected_servers.get('github', {}).get('tools', {})
                return f"GitHub tools available: {', '.join(tools.keys())}"

        except Exception as e:
            return f"GitHub operation failed: {str(e)}"

"""
CORRECTED DIRECTORY STRUCTURE:

ambivo_agents/mcp/
├── __init__.py                  # Simple imports only
├── client.py                    # MCPAgentClient implementation
├── server.py                    # MCPAgentServer implementation
├── registry.py                  # MCPServerRegistry implementation
├── agent_integration.py         # THIS FILE - MCPIntegratedAgent classes
├── templates.py                 # Configuration templates (optional)
└── cli.py                      # CLI entry point

Usage:
------

# Basic MCP integration
from ambivo_agents.mcp.agent_integration import MCPIntegratedAgent

class MyAgent(MCPIntegratedAgent):
    async def process_message(self, message, context=None):
        # Can use self.use_mcp_tool(), self.connect_mcp_server(), etc.
        pass

# Pre-built MCP-enabled assistant
from ambivo_agents.mcp.agent_integration import MCPEnabledAssistantAgent

agent = MCPEnabledAssistantAgent(agent_id="mcp_assistant")
await agent.connect_mcp_server("filesystem", "npx", ["@modelcontextprotocol/server-filesystem", "/path"])
"""
