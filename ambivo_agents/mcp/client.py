# ambivo_agents/mcp/client.py
"""
Complete MCP Client implementation for Ambivo Agents - FIXED VERSION
Properly handles session lifecycle and stdio transport
"""

import asyncio
import json
import logging
import subprocess
import uuid
from typing import Dict, List, Any, Optional, Union
from dataclasses import dataclass
from pathlib import Path
import sys

try:
    import mcp
    from mcp.client.session import ClientSession
    from mcp.client.stdio import StdioServerParameters, stdio_client
    from mcp.types import Resource, Tool, TextContent, ImageContent, EmbeddedResource

    MCP_AVAILABLE = True
except ImportError:
    MCP_AVAILABLE = False
    logging.warning("MCP not available. Install with: pip install mcp")


@dataclass
class MCPServerConfig:
    """Configuration for MCP server connection"""
    name: str
    command: str
    args: List[str]
    env: Dict[str, str] = None
    capabilities: List[str] = None
    timeout: int = 30


class MCPAgentClient:
    """MCP Client for Ambivo Agents with full protocol support and proper session management"""

    def __init__(self):
        if not MCP_AVAILABLE:
            raise ImportError("MCP package required but not available")

        self.connected_servers: Dict[str, ClientSession] = {}
        self.server_configs: Dict[str, MCPServerConfig] = {}
        self.cached_tools: Dict[str, List[Tool]] = {}
        self.cached_resources: Dict[str, List[Resource]] = {}
        self.logger = logging.getLogger("MCPAgentClient")
        self._transport_handles: Dict[str, Any] = {}  # Store transport handles

    async def connect_to_server(self, server_name: str, command: str, args: List[str] = None,
                                env: Dict[str, str] = None, timeout: int = 30) -> bool:
        """Connect to an MCP server with proper session management"""
        try:
            if server_name in self.connected_servers:
                self.logger.info(f"Already connected to {server_name}")
                return True

            # Store server config
            self.server_configs[server_name] = MCPServerConfig(
                name=server_name,
                command=command,
                args=args or [],
                env=env or {},
                timeout=timeout
            )

            # Create server parameters
            server_params = StdioServerParameters(
                command=command,
                args=args or [],
                env=env or {}
            )

            self.logger.info(f"Connecting to MCP server: {server_name}")
            self.logger.debug(f"Command: {command} {' '.join(args or [])}")

            # Connect to server with timeout
            try:
                stdio_transport = await asyncio.wait_for(
                    stdio_client(server_params),
                    timeout=timeout
                )

                read_stream, write_stream = stdio_transport

                # Store transport handles for cleanup
                self._transport_handles[server_name] = (read_stream, write_stream)

                # Create session
                session = ClientSession(read_stream, write_stream)

                # Initialize the session with timeout
                await asyncio.wait_for(
                    session.initialize(),
                    timeout=timeout
                )

                self.connected_servers[server_name] = session
                self.logger.info(f"Successfully connected to MCP server: {server_name}")

                # Cache initial tools and resources
                await self._cache_server_capabilities(server_name)

                return True

            except asyncio.TimeoutError:
                self.logger.error(f"Timeout connecting to MCP server {server_name}")
                return False

        except Exception as e:
            self.logger.error(f"Failed to connect to MCP server {server_name}: {e}")
            return False

    async def _cache_server_capabilities(self, server_name: str):
        """Cache tools and resources from a server with error handling"""
        try:
            session = self.connected_servers.get(server_name)
            if not session:
                return

            # Cache tools with timeout
            try:
                tools_result = await asyncio.wait_for(
                    session.list_tools(),
                    timeout=10
                )
                self.cached_tools[server_name] = tools_result.tools
                self.logger.debug(f"Cached {len(tools_result.tools)} tools from {server_name}")
            except asyncio.TimeoutError:
                self.logger.warning(f"Timeout caching tools from {server_name}")
                self.cached_tools[server_name] = []
            except Exception as e:
                self.logger.warning(f"Failed to cache tools from {server_name}: {e}")
                self.cached_tools[server_name] = []

            # Cache resources with timeout
            try:
                resources_result = await asyncio.wait_for(
                    session.list_resources(),
                    timeout=10
                )
                self.cached_resources[server_name] = resources_result.resources
                self.logger.debug(f"Cached {len(resources_result.resources)} resources from {server_name}")
            except asyncio.TimeoutError:
                self.logger.warning(f"Timeout caching resources from {server_name}")
                self.cached_resources[server_name] = []
            except Exception as e:
                self.logger.debug(f"Server {server_name} doesn't support resources or failed: {e}")
                self.cached_resources[server_name] = []

        except Exception as e:
            self.logger.error(f"Failed to cache capabilities for {server_name}: {e}")

    async def list_tools(self, server_name: str = None) -> List[Tool]:
        """List available tools from server(s)"""
        if server_name:
            return self.cached_tools.get(server_name, [])

        # Return tools from all servers
        all_tools = []
        for tools in self.cached_tools.values():
            all_tools.extend(tools)
        return all_tools

    async def call_tool(self, server_name: str, tool_name: str, arguments: Dict[str, Any] = None) -> Any:
        """Call a tool on a specific MCP server with proper error handling"""
        try:
            session = self.connected_servers.get(server_name)
            if not session:
                raise ValueError(f"Not connected to server: {server_name}")

            # Verify tool exists
            tools = self.cached_tools.get(server_name, [])
            tool = next((t for t in tools if t.name == tool_name), None)
            if not tool:
                # Refresh cache and try again
                await self._cache_server_capabilities(server_name)
                tools = self.cached_tools.get(server_name, [])
                tool = next((t for t in tools if t.name == tool_name), None)
                if not tool:
                    raise ValueError(f"Tool {tool_name} not found on server {server_name}")

            self.logger.info(f"Calling tool {tool_name} on {server_name}")

            # Call the tool with timeout
            result = await asyncio.wait_for(
                session.call_tool(tool_name, arguments or {}),
                timeout=30
            )

            return self._process_tool_result(result)

        except asyncio.TimeoutError:
            self.logger.error(f"Timeout calling tool {tool_name} on {server_name}")
            raise RuntimeError(f"Tool call timed out: {tool_name}")
        except Exception as e:
            self.logger.error(f"Error calling tool {tool_name} on {server_name}: {e}")
            raise e

    def _process_tool_result(self, result) -> Any:
        """Process MCP tool result into usable format"""
        try:
            if hasattr(result, 'content'):
                content_list = result.content
                if len(content_list) == 1:
                    content = content_list[0]
                    if isinstance(content, TextContent):
                        return content.text
                    elif isinstance(content, ImageContent):
                        return {
                            "type": "image",
                            "data": content.data,
                            "mimeType": content.mimeType
                        }
                else:
                    # Multiple content items
                    return [self._process_content_item(item) for item in content_list]

            return str(result)
        except Exception as e:
            self.logger.error(f"Error processing tool result: {e}")
            return f"Error processing result: {str(e)}"

    def _process_content_item(self, content) -> Any:
        """Process individual content item"""
        try:
            if isinstance(content, TextContent):
                return {"type": "text", "text": content.text}
            elif isinstance(content, ImageContent):
                return {
                    "type": "image",
                    "data": content.data,
                    "mimeType": content.mimeType
                }
            else:
                return {"type": "unknown", "data": str(content)}
        except Exception as e:
            return {"type": "error", "error": str(e)}

    async def read_resource(self, server_name: str, resource_uri: str) -> Any:
        """Read a resource from MCP server with proper error handling"""
        try:
            session = self.connected_servers.get(server_name)
            if not session:
                raise ValueError(f"Not connected to server: {server_name}")

            self.logger.info(f"Reading resource {resource_uri} from {server_name}")

            result = await asyncio.wait_for(
                session.read_resource(resource_uri),
                timeout=30
            )

            return self._process_tool_result(result)

        except asyncio.TimeoutError:
            self.logger.error(f"Timeout reading resource {resource_uri} from {server_name}")
            raise RuntimeError(f"Resource read timed out: {resource_uri}")
        except Exception as e:
            self.logger.error(f"Error reading resource {resource_uri} from {server_name}: {e}")
            raise e

    async def list_resources(self, server_name: str = None) -> List[Resource]:
        """List available resources"""
        if server_name:
            return self.cached_resources.get(server_name, [])

        # Return resources from all servers
        all_resources = []
        for resources in self.cached_resources.values():
            all_resources.extend(resources)
        return all_resources

    async def disconnect_server(self, server_name: str) -> bool:
        """Disconnect from an MCP server with proper cleanup"""
        try:
            if server_name in self.connected_servers:
                session = self.connected_servers[server_name]

                # Clean shutdown of session
                try:
                    # Close session if it has a close method
                    if hasattr(session, 'close'):
                        await session.close()
                except Exception as e:
                    self.logger.warning(f"Error closing session for {server_name}: {e}")

                # Clean up transport handles
                if server_name in self._transport_handles:
                    try:
                        read_stream, write_stream = self._transport_handles[server_name]

                        # Close streams if they have close methods
                        if hasattr(write_stream, 'close'):
                            write_stream.close()
                        if hasattr(read_stream, 'close'):
                            read_stream.close()

                        del self._transport_handles[server_name]
                    except Exception as e:
                        self.logger.warning(f"Error closing transport for {server_name}: {e}")

                # Remove from tracking
                del self.connected_servers[server_name]

                # Clear cached data
                self.cached_tools.pop(server_name, None)
                self.cached_resources.pop(server_name, None)

                self.logger.info(f"Disconnected from MCP server: {server_name}")
                return True
        except Exception as e:
            self.logger.error(f"Error disconnecting from {server_name}: {e}")

        return False

    async def disconnect_all(self):
        """Disconnect from all MCP servers"""
        for server_name in list(self.connected_servers.keys()):
            await self.disconnect_server(server_name)

    def get_server_status(self) -> Dict[str, Any]:
        """Get status of all connected servers"""
        status = {
            "connected_servers": list(self.connected_servers.keys()),
            "total_tools": sum(len(tools) for tools in self.cached_tools.values()),
            "total_resources": sum(len(resources) for resources in self.cached_resources.values()),
            "server_details": {}
        }

        for server_name in self.connected_servers.keys():
            config = self.server_configs.get(server_name)
            status["server_details"][server_name] = {
                "tools": len(self.cached_tools.get(server_name, [])),
                "resources": len(self.cached_resources.get(server_name, [])),
                "config": {
                    "command": config.command if config else "unknown",
                    "args": config.args if config else [],
                    "timeout": config.timeout if config else 30
                }
            }

        return status

    async def refresh_capabilities(self, server_name: str = None):
        """Refresh cached capabilities for server(s)"""
        if server_name:
            if server_name in self.connected_servers:
                await self._cache_server_capabilities(server_name)
        else:
            # Refresh all servers
            for name in self.connected_servers.keys():
                await self._cache_server_capabilities(name)

    async def health_check(self, server_name: str = None) -> Dict[str, Any]:
        """Perform health check on connected servers"""
        results = {}

        servers_to_check = [server_name] if server_name else list(self.connected_servers.keys())

        for name in servers_to_check:
            if name not in self.connected_servers:
                results[name] = {"status": "not_connected"}
                continue

            try:
                # Try to list tools as a simple health check
                await asyncio.wait_for(
                    self.connected_servers[name].list_tools(),
                    timeout=5
                )
                results[name] = {"status": "healthy"}
            except asyncio.TimeoutError:
                results[name] = {"status": "timeout"}
            except Exception as e:
                results[name] = {"status": "error", "error": str(e)}

        return results

    async def __aenter__(self):
        """Async context manager entry"""
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit with cleanup"""
        await self.disconnect_all()