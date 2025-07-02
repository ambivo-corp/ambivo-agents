# ambivo_agents/mcp/__init__.py
"""
MCP Integration for Ambivo Agents
Fixed import structure to avoid circular dependencies
"""

# Import order matters to avoid circular imports
try:
    # Check if MCP is available
    import mcp

    MCP_AVAILABLE = True
except ImportError:
    MCP_AVAILABLE = False

if MCP_AVAILABLE:
    from .client import MCPAgentClient
    from .server import MCPAgentServer
    from .registry import MCPServerRegistry

    __all__ = ["MCPAgentClient", "MCPAgentServer", "MCPServerRegistry", "MCP_AVAILABLE"]
else:
    __all__ = ["MCP_AVAILABLE"]


