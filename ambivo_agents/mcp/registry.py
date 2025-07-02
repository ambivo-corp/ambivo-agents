# ============================================================================
# FILE: ambivo_agents/mcp/registry.py
# ============================================================================

"""
MCP Server Registry and Discovery - SEPARATE FILE
"""

import json
import os
from typing import Dict, List, Any, Optional
from pathlib import Path
from datetime import datetime


class MCPServerRegistry:
    """Registry for MCP servers and their capabilities"""

    def __init__(self, registry_path: str = None):
        self.registry_path = registry_path or os.path.expanduser("~/.mcp/servers.json")
        self.servers: Dict[str, Dict[str, Any]] = {}
        self.load_registry()

    def load_registry(self):
        """Load server registry from file"""
        registry_file = Path(self.registry_path)
        if registry_file.exists():
            try:
                with open(registry_file, 'r') as f:
                    self.servers = json.load(f)
            except Exception as e:
                print(f"Failed to load MCP registry: {e}")
                self.servers = {}

    def register_server(self, name: str, command: str, args: List[str] = None,
                        description: str = "", capabilities: List[str] = None):
        """Register an MCP server"""
        self.servers[name] = {
            "command": command,
            "args": args or [],
            "description": description,
            "capabilities": capabilities or [],
            "registered_at": datetime.now().isoformat()
        }
        self.save_registry()

    def save_registry(self):
        """Save server registry to file"""
        registry_file = Path(self.registry_path)
        registry_file.parent.mkdir(parents=True, exist_ok=True)

        try:
            with open(registry_file, 'w') as f:
                json.dump(self.servers, f, indent=2)
        except Exception as e:
            print(f"Failed to save MCP registry: {e}")