#!/usr/bin/env python3
"""
MCP Server entry point for Ambivo Agents - FIXED VERSION
This is the main entry point that Claude Desktop will call

Usage:
- Direct: python -m ambivo_agents.mcp.mcp_server
- Via CLI: ambivo-mcp-server
- Claude Desktop: Configured in claude_desktop_config.json

Author: Hemant Gosain 'Sunny'
"""

import asyncio
import sys
import logging
import os
from pathlib import Path

# Set up logging for MCP server
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(sys.stderr)  # MCP uses stderr for logging
    ]
)

logger = logging.getLogger("ambivo-mcp-server")


def setup_environment():
    """Setup environment for MCP server"""
    # Add current directory to Python path if needed
    current_dir = Path(__file__).parent.parent.parent
    if str(current_dir) not in sys.path:
        sys.path.insert(0, str(current_dir))

    # Set default environment variables if not set
    env_defaults = {
        'AMBIVO_AGENTS_REDIS_HOST': 'localhost',
        'AMBIVO_AGENTS_REDIS_PORT': '6379',
        'AMBIVO_AGENTS_REDIS_DB': '0',
    }

    for key, default_value in env_defaults.items():
        if not os.getenv(key):
            os.environ[key] = default_value
            logger.info(f"Set default environment variable: {key}={default_value}")


async def main():
    """Main entry point for MCP server"""
    try:
        logger.info("Starting Ambivo Agents MCP Server...")

        # Setup environment
        setup_environment()

        # Check MCP availability
        try:
            import mcp
            logger.info(f"MCP package available: {mcp.__version__}")
        except ImportError:
            logger.error("MCP package not available. Install with: pip install ambivo-agents[mcp]")
            sys.exit(1)

        # Import and start the MCP server
        try:
            from ambivo_agents.mcp.server import MCPAgentServer
            logger.info("Imported MCPAgentServer successfully")
        except ImportError as e:
            logger.error(f"Failed to import MCPAgentServer: {e}")
            sys.exit(1)

        # Create and run server
        try:
            server = MCPAgentServer()
            logger.info("MCPAgentServer created successfully")

            logger.info("Starting MCP server with stdio transport...")
            await server.run_stdio()

        except Exception as e:
            logger.error(f"Failed to start MCP server: {e}")
            raise

    except KeyboardInterrupt:
        logger.info("MCP server interrupted by user")
    except Exception as e:
        logger.error(f"MCP server error: {e}")
        sys.exit(1)
    finally:
        logger.info("MCP server shutdown complete")


def cli_main():
    """CLI entry point for console script"""
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("MCP server interrupted")
        sys.exit(0)
    except Exception as e:
        logger.error(f"MCP server failed: {e}")
        sys.exit(1)


if __name__ == "__main__":
    cli_main()