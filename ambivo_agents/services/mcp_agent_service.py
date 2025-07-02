#== == == == == == == == == == == == == == == == == == == == == == == == == == == == == == == == == == == == == ==
# FILE: ambivo_agents/services/mcp_agent_service.py - FIXED IMPORTS
# ============================================================================

"""
Enhanced Agent Service with MCP integration - FIXED VERSION
"""

import asyncio
import logging
from typing import Dict, List, Any, Optional

# Import from the base agent service
from .agent_service import AgentService as BaseAgentService

# FIXED: Import MCP components from correct locations
try:
    from ..mcp.client import MCPAgentClient
    from ..mcp.registry import MCPServerRegistry

    MCP_AVAILABLE = True
except ImportError:
    MCP_AVAILABLE = False

from ..config.loader import load_config, get_config_section


class MCPEnabledAgentService(BaseAgentService):
    """Agent Service with MCP client capabilities - FIXED VERSION"""

    def __init__(self, preferred_llm_provider: str = None, enable_mcp: bool = True):
        super().__init__(preferred_llm_provider)

        self.enable_mcp = enable_mcp and MCP_AVAILABLE
        self.mcp_client = None
        self.mcp_registry = None
        self.connected_mcp_servers: Dict[str, Dict[str, Any]] = {}

        if self.enable_mcp:
            self._initialize_mcp()
        else:
            if enable_mcp and not MCP_AVAILABLE:
                self.logger.warning("MCP requested but not available. Install with: pip install ambivo-agents[mcp]")

    def _initialize_mcp(self):
        """Initialize MCP client and connections"""
        try:
            self.mcp_client = MCPAgentClient()
            self.mcp_registry = MCPServerRegistry()

            # Load MCP configuration
            mcp_config = get_config_section('mcp', self.config)

            if mcp_config.get('client', {}).get('enabled', True):
                # Auto-connect to configured servers
                asyncio.create_task(self._auto_connect_servers(mcp_config))

        except Exception as e:
            self.logger.error(f"Failed to initialize MCP: {e}")
            self.enable_mcp = False

    async def _auto_connect_servers(self, mcp_config: Dict[str, Any]):
        """Auto-connect to configured MCP servers"""
        external_servers = mcp_config.get('external_servers', {})
        auto_connect = mcp_config.get('client', {}).get('auto_connect_servers', [])

        for server_name in auto_connect:
            if server_name in external_servers:
                server_config = external_servers[server_name]

                try:
                    success = await self.mcp_client.connect_to_server(
                        server_name=server_name,
                        command=server_config['command'],
                        args=server_config.get('args', [])
                    )

                    if success:
                        # Cache server capabilities
                        tools = await self.mcp_client.list_tools(server_name)

                        self.connected_mcp_servers[server_name] = {
                            'tools': {tool['name']: tool for tool in tools},
                            'capabilities': server_config.get('capabilities', [])
                        }

                        self.logger.info(f"Connected to MCP server: {server_name}")

                except Exception as e:
                    self.logger.error(f"Failed to connect to MCP server {server_name}: {e}")

    def get_mcp_status(self) -> Dict[str, Any]:
        """Get MCP integration status"""
        return {
            'mcp_available': MCP_AVAILABLE,
            'mcp_enabled': self.enable_mcp,
            'mcp_client_available': self.mcp_client is not None,
            'connected_servers': list(self.connected_mcp_servers.keys()),
            'server_details': {
                name: {
                    'tools': list(info['tools'].keys()),
                    'capabilities': info['capabilities']
                }
                for name, info in self.connected_mcp_servers.items()
            }
        }


def create_mcp_agent_service(preferred_llm_provider: str = None, enable_mcp: bool = True) -> MCPEnabledAgentService:
    """Create MCP-enabled agent service"""
    return MCPEnabledAgentService(preferred_llm_provider, enable_mcp)
