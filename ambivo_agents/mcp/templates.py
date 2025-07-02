
# Configuration file for MCP integration
MCP_CONFIG_TEMPLATE = """# MCP Server Configuration for Ambivo Agents

# Default MCP servers to connect to
mcp_servers:
  # Example: Claude Desktop MCP servers
  filesystem:
    command: "npx"
    args: ["@modelcontextprotocol/server-filesystem", "/path/to/allowed/directory"]
    description: "File system access"
    capabilities: ["file_read", "file_write", "directory_list"]

  sqlite:
    command: "npx"
    args: ["@modelcontextprotocol/server-sqlite", "/path/to/database.db"]
    description: "SQLite database access"
    capabilities: ["database_query", "database_schema"]

  github:
    command: "npx"
    args: ["@modelcontextprotocol/server-github"]
    description: "GitHub repository access"
    capabilities: ["repo_read", "issue_management"]

# MCP client settings
mcp_client:
  auto_connect: true
  connection_timeout: 30
  max_retries: 3

# MCP server settings (for exposing Ambivo Agents)
mcp_server:
  name: "ambivo-agents"
  version: "1.0.0"
  description: "Ambivo Agents MCP Server"
  capabilities:
    - "code_execution"
    - "web_search"
    - "knowledge_base"
    - "media_processing"
    - "youtube_download"
    - "web_scraping"
"""

def get_config_template() -> str:
    return MCP_CONFIG_TEMPLATE