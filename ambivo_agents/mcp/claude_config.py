# ambivo_agents/mcp/claude_config.py
"""
Claude Desktop Configuration Generator for Ambivo Agents MCP Integration

This generates the proper configuration for Claude Desktop to connect to Ambivo Agents MCP server.
"""

import json
import os
import sys
from pathlib import Path
from typing import Dict, Any, Optional


class ClaudeDesktopConfigGenerator:
    """Generate Claude Desktop configuration for Ambivo Agents MCP integration"""

    def __init__(self):
        self.config_data = {}

    def generate_config(self,
                        python_path: Optional[str] = None,
                        env_vars: Optional[Dict[str, str]] = None,
                        working_dir: Optional[str] = None) -> Dict[str, Any]:
        """
        Generate Claude Desktop configuration for Ambivo Agents

        Args:
            python_path: Path to Python executable (auto-detected if None)
            env_vars: Environment variables to pass to the server
            working_dir: Working directory for the server

        Returns:
            Dict containing the Claude Desktop configuration
        """

        # Auto-detect Python path if not provided
        if python_path is None:
            python_path = sys.executable

        # Set up default environment variables
        default_env = {
            "AMBIVO_AGENTS_REDIS_HOST": "localhost",
            "AMBIVO_AGENTS_REDIS_PORT": "6379",
            "AMBIVO_AGENTS_REDIS_DB": "0",
        }

        # Merge with provided env vars
        if env_vars:
            default_env.update(env_vars)

        # Generate the configuration
        config = {
            "mcpServers": {
                "ambivo-agents": {
                    "command": python_path,
                    "args": ["-m", "ambivo_agents.mcp.mcp_server"],
                    "env": default_env
                }
            }
        }

        # Add working directory if specified
        if working_dir:
            config["mcpServers"]["ambivo-agents"]["cwd"] = working_dir

        return config

    def get_config_paths(self) -> Dict[str, Path]:
        """Get Claude Desktop configuration file paths for different platforms"""
        paths = {}

        if sys.platform == "darwin":  # macOS
            paths["primary"] = Path.home() / ".claude_desktop_config.json"
            paths["alternative"] = Path.home() / "Library/Application Support/Claude/claude_desktop_config.json"
        elif sys.platform == "win32":  # Windows
            appdata = os.getenv("APPDATA", "")
            if appdata:
                paths["primary"] = Path(appdata) / "Claude" / "claude_desktop_config.json"
            paths["alternative"] = Path.home() / ".claude_desktop_config.json"
        else:  # Linux and others
            paths["primary"] = Path.home() / ".claude_desktop_config.json"
            paths["alternative"] = Path.home() / ".config" / "claude" / "claude_desktop_config.json"

        return paths

    def save_config(self, config: Dict[str, Any], config_path: Optional[Path] = None) -> bool:
        """
        Save configuration to Claude Desktop config file

        Args:
            config: Configuration dictionary
            config_path: Path to save config (auto-detected if None)

        Returns:
            True if successful, False otherwise
        """
        try:
            if config_path is None:
                paths = self.get_config_paths()
                config_path = paths["primary"]

            # Create directory if it doesn't exist
            config_path.parent.mkdir(parents=True, exist_ok=True)

            # Load existing config if it exists
            existing_config = {}
            if config_path.exists():
                try:
                    with open(config_path, 'r') as f:
                        existing_config = json.load(f)
                except (json.JSONDecodeError, IOError):
                    # If existing config is invalid, start fresh
                    existing_config = {}

            # Merge configurations
            if "mcpServers" not in existing_config:
                existing_config["mcpServers"] = {}

            existing_config["mcpServers"].update(config["mcpServers"])

            # Save the merged configuration
            with open(config_path, 'w') as f:
                json.dump(existing_config, f, indent=2)

            return True

        except Exception as e:
            print(f"Error saving Claude Desktop config: {e}")
            return False

    def generate_installation_instructions(self, config: Dict[str, Any]) -> str:
        """Generate installation instructions for users"""

        config_json = json.dumps(config, indent=2)
        paths = self.get_config_paths()

        instructions = f"""
# Ambivo Agents MCP Integration for Claude Desktop

## Installation Steps:

### 1. Install Ambivo Agents with MCP support:
```bash
pip install ambivo-agents[mcp]
```

### 2. Set up environment variables (choose one method):

#### Option A: Environment Variables
```bash
export AMBIVO_AGENTS_REDIS_HOST=localhost
export AMBIVO_AGENTS_REDIS_PORT=6379
export AMBIVO_AGENTS_OPENAI_API_KEY=your_openai_key_here
export AMBIVO_AGENTS_ENABLE_CODE_EXECUTION=true
export AMBIVO_AGENTS_ENABLE_WEB_SEARCH=true
```

#### Option B: Create agent_config.yaml:
```yaml
redis:
  host: localhost
  port: 6379
  db: 0

llm:
  openai_api_key: your_openai_key_here
  preferred_provider: openai

agent_capabilities:
  enable_code_execution: true
  enable_web_search: true
  enable_knowledge_base: true
```

### 3. Add to Claude Desktop configuration:

#### Location: {paths.get('primary', 'claude_desktop_config.json')}

Add this to your Claude Desktop config file:

```json
{config_json}
```

### 4. Restart Claude Desktop

### 5. Test the integration:

In Claude Desktop, you should now see Ambivo Agents tools available. Try:
- "Execute this Python code: print('Hello from Ambivo Agents!')"
- "Search the web for latest AI news"

## Troubleshooting:

### Check MCP server is working:
```bash
# Test the MCP server directly
ambivo-mcp-server

# Check agent status
ambivo status
```

### Verify configuration:
```bash
# Generate fresh config
ambivo mcp claude-config

# Check environment variables
ambivo env-check
```

### Common Issues:

1. **"MCP server not found"**
   - Ensure `ambivo-agents[mcp]` is installed
   - Check Python path in config matches your environment

2. **"Connection failed"**
   - Verify Redis is running (`redis-server`)
   - Check environment variables are set correctly

3. **"Tools not appearing"**
   - Restart Claude Desktop after config changes
   - Check config file syntax is valid JSON

## Advanced Configuration:

### Enable more capabilities:
```bash
export AMBIVO_AGENTS_ENABLE_YOUTUBE_DOWNLOAD=true
export AMBIVO_AGENTS_ENABLE_MEDIA_EDITOR=true
export AMBIVO_AGENTS_ENABLE_WEB_SCRAPING=true
```

### Custom working directory:
Modify the config to include a working directory:
```json
{{
  "mcpServers": {{
    "ambivo-agents": {{
      "command": "{sys.executable}",
      "args": ["-m", "ambivo_agents.mcp.mcp_server"],
      "cwd": "/path/to/your/working/directory",
      "env": {{ ... }}
    }}
  }}
}}
```

For more information, visit: https://github.com/ambivo-corp/ambivo-agents
"""
        return instructions

    def validate_config(self, config: Dict[str, Any]) -> Dict[str, Any]:
        """
        Validate the Claude Desktop configuration

        Returns:
            Dict with validation results
        """
        results = {
            "valid": True,
            "errors": [],
            "warnings": []
        }

        try:
            # Check required structure
            if "mcpServers" not in config:
                results["errors"].append("Missing 'mcpServers' section")
                results["valid"] = False

            if "ambivo-agents" not in config.get("mcpServers", {}):
                results["errors"].append("Missing 'ambivo-agents' server configuration")
                results["valid"] = False

            server_config = config.get("mcpServers", {}).get("ambivo-agents", {})

            # Check required fields
            if "command" not in server_config:
                results["errors"].append("Missing 'command' field")
                results["valid"] = False
            elif not Path(server_config["command"]).exists():
                results["warnings"].append(f"Python executable not found: {server_config['command']}")

            if "args" not in server_config:
                results["errors"].append("Missing 'args' field")
                results["valid"] = False
            elif server_config["args"] != ["-m", "ambivo_agents.mcp.mcp_server"]:
                results["warnings"].append("Non-standard args configuration")

            # Check environment variables
            env = server_config.get("env", {})
            required_env = ["AMBIVO_AGENTS_REDIS_HOST", "AMBIVO_AGENTS_REDIS_PORT"]

            for var in required_env:
                if var not in env and not os.getenv(var):
                    results["warnings"].append(f"Missing environment variable: {var}")

            # Check for API keys
            api_key_vars = [
                "AMBIVO_AGENTS_OPENAI_API_KEY",
                "AMBIVO_AGENTS_ANTHROPIC_API_KEY",
                "OPENAI_API_KEY",
                "ANTHROPIC_API_KEY"
            ]

            has_api_key = any(
                var in env or os.getenv(var)
                for var in api_key_vars
            )

            if not has_api_key:
                results["warnings"].append("No API keys found - some features may not work")

        except Exception as e:
            results["errors"].append(f"Validation error: {str(e)}")
            results["valid"] = False

        return results

    def get_sample_configs(self) -> Dict[str, Dict[str, Any]]:
        """Get sample configurations for different use cases"""

        python_exe = sys.executable

        configs = {
            "minimal": {
                "mcpServers": {
                    "ambivo-agents": {
                        "command": python_exe,
                        "args": ["-m", "ambivo_agents.mcp.mcp_server"],
                        "env": {
                            "AMBIVO_AGENTS_REDIS_HOST": "localhost",
                            "AMBIVO_AGENTS_REDIS_PORT": "6379"
                        }
                    }
                }
            },

            "development": {
                "mcpServers": {
                    "ambivo-agents": {
                        "command": python_exe,
                        "args": ["-m", "ambivo_agents.mcp.mcp_server"],
                        "env": {
                            "AMBIVO_AGENTS_REDIS_HOST": "localhost",
                            "AMBIVO_AGENTS_REDIS_PORT": "6379",
                            "AMBIVO_AGENTS_ENABLE_CODE_EXECUTION": "true",
                            "AMBIVO_AGENTS_ENABLE_WEB_SEARCH": "true",
                            "AMBIVO_AGENTS_ENABLE_KNOWLEDGE_BASE": "true",
                            "AMBIVO_AGENTS_OPENAI_API_KEY": "${OPENAI_API_KEY}"
                        }
                    }
                }
            },

            "full_features": {
                "mcpServers": {
                    "ambivo-agents": {
                        "command": python_exe,
                        "args": ["-m", "ambivo_agents.mcp.mcp_server"],
                        "env": {
                            "AMBIVO_AGENTS_REDIS_HOST": "localhost",
                            "AMBIVO_AGENTS_REDIS_PORT": "6379",
                            "AMBIVO_AGENTS_ENABLE_CODE_EXECUTION": "true",
                            "AMBIVO_AGENTS_ENABLE_WEB_SEARCH": "true",
                            "AMBIVO_AGENTS_ENABLE_KNOWLEDGE_BASE": "true",
                            "AMBIVO_AGENTS_ENABLE_YOUTUBE_DOWNLOAD": "true",
                            "AMBIVO_AGENTS_ENABLE_MEDIA_EDITOR": "true",
                            "AMBIVO_AGENTS_ENABLE_WEB_SCRAPING": "true",
                            "AMBIVO_AGENTS_OPENAI_API_KEY": "${OPENAI_API_KEY}",
                            "AMBIVO_AGENTS_BRAVE_API_KEY": "${BRAVE_API_KEY}",
                            "AMBIVO_AGENTS_QDRANT_URL": "${QDRANT_URL}"
                        }
                    }
                }
            }
        }

        return configs


def generate_claude_config(
        config_type: str = "development",
        save_to_file: bool = False,
        python_path: Optional[str] = None,
        env_vars: Optional[Dict[str, str]] = None
) -> str:
    """
    Convenience function to generate Claude Desktop configuration

    Args:
        config_type: Type of config ("minimal", "development", "full_features")
        save_to_file: Whether to save to Claude Desktop config file
        python_path: Custom Python executable path
        env_vars: Additional environment variables

    Returns:
        JSON configuration string
    """
    generator = ClaudeDesktopConfigGenerator()

    if config_type in ["minimal", "development", "full_features"]:
        configs = generator.get_sample_configs()
        config = configs[config_type]

        # Override Python path if provided
        if python_path:
            config["mcpServers"]["ambivo-agents"]["command"] = python_path

        # Add additional env vars if provided
        if env_vars:
            config["mcpServers"]["ambivo-agents"]["env"].update(env_vars)
    else:
        # Generate custom config
        config = generator.generate_config(python_path, env_vars)

    if save_to_file:
        success = generator.save_config(config)
        if success:
            print("✅ Configuration saved to Claude Desktop config file")
        else:
            print("❌ Failed to save configuration")

    return json.dumps(config, indent=2)


# CLI usage functions
def print_claude_config():
    """Print Claude Desktop configuration to stdout"""
    print(generate_claude_config("development"))


def print_installation_instructions():
    """Print full installation instructions"""
    generator = ClaudeDesktopConfigGenerator()
    config = generator.generate_config()
    instructions = generator.generate_installation_instructions(config)
    print(instructions)


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Generate Claude Desktop configuration for Ambivo Agents")
    parser.add_argument("--type", choices=["minimal", "development", "full_features"],
                        default="development", help="Configuration type")
    parser.add_argument("--save", action="store_true", help="Save to Claude Desktop config file")
    parser.add_argument("--instructions", action="store_true", help="Show installation instructions")
    parser.add_argument("--python-path", help="Custom Python executable path")

    args = parser.parse_args()

    if args.instructions:
        print_installation_instructions()
    else:
        config_json = generate_claude_config(
            config_type=args.type,
            save_to_file=args.save,
            python_path=args.python_path
        )
        print(config_json)