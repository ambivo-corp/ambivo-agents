#!/usr/bin/env python3
"""
Ambivo Agents Setup Script - UPDATED WITH PROPER MCP SUPPORT

Author: Hemant Gosain 'Sunny'
Company: Ambivo
Email: sgosain@ambivo.com
"""

from setuptools import setup, find_packages
import os


def read_readme():
    """Read README for long description"""
    try:
        with open("README.md", "r", encoding="utf-8") as fh:
            return fh.read()
    except FileNotFoundError:
        return "Ambivo Agents - Multi-Agent AI System with MCP Support"


def read_requirements():
    """Read requirements from requirements.txt"""
    try:
        with open("requirements.txt", "r", encoding="utf-8") as fh:
            return [line.strip() for line in fh if line.strip() and not line.startswith("#")]
    except FileNotFoundError:
        return [
            # Core dependencies
            "redis>=6.2.0",
            "redis[asyncio]",
            "docker>=6.0.0",
            "asyncio-mqtt>=0.11.0",
            "cachetools",
            "lz4",
            "requests>=2.32.4",
            "click>=8.2.1",

            # LangChain and LLM
            "openai>=1.84.0",
            "langchain>=0.3.25",
            "langchain-community>=0.3.24",
            "langchain-core>=0.3.63",
            "langchain-openai>=0.3.19",
            "langchainhub>=0.1.21",
            "langchain-text-splitters>=0.3.8",
            "langchain-anthropic>=0.3.15",
            "langchain-aws",
            "langchain-voyageai",

            # LlamaIndex
            "llama-index-core",
            "llama-index-embeddings-langchain",
            "llama-index-llms-langchain",
            "llama-index-llms-openai",
            "llama-index-vector-stores-qdrant",
            "llama-index-readers-smart-pdf-loader",

            # Core utilities
            "pydantic>=2.11.7",
            "boto3>=1.38.42",
            "python-dotenv>=1.1.1",
            "pyyaml>=6.0.2",
            "psutil>=7.0.0",
            "qdrant-client",
            "numexpr",

            # Development
            "pytest>=8.4.1",
            "pytest-asyncio>=1.0.0",
            "black>=25.1.0",
            "isort>=6.0.1",

            # Document processing
            "unstructured",
            "langchain-unstructured",
        ]


setup(
    name="ambivo-agents",
    version="1.0.8",
    author="Hemant Gosain 'Sunny'",
    author_email="sgosain@ambivo.com",
    description="Multi-Agent AI System with MCP (Model Context Protocol) support for automation",
    long_description=read_readme(),
    long_description_content_type="text/markdown",
    url="https://github.com/ambivo-corp/ambivo-agents",
    packages=find_packages(),
    classifiers=[
        "Development Status :: 4 - Beta",
        "Intended Audience :: Developers",
        "License :: OSI Approved :: MIT License",
        "Operating System :: OS Independent",
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.11",
        "Programming Language :: Python :: 3.12",
        "Programming Language :: Python :: 3.13",
        "Topic :: Software Development :: Libraries :: Python Modules",
        "Topic :: Scientific/Engineering :: Artificial Intelligence",
        "Topic :: Software Development :: Libraries :: Application Frameworks",
        "Topic :: System :: Distributed Computing",
        "Topic :: Communications",
        "Framework :: AsyncIO",
    ],
    python_requires=">=3.11",
    install_requires=read_requirements(),

    # UPDATED: Proper optional dependencies with MCP support
    extras_require={
        # MCP Protocol Support
        "mcp": [
            "mcp>=1.0.0",
        ],

        # Web capabilities
        "web": [
            "beautifulsoup4>=4.13.4",
            "playwright>=1.40.0",
        ],

        # Media processing
        "media": [
            "pytubefix>=6.0.0",
        ],

        # Additional LLM providers
        "anthropic": [
            "anthropic>=0.55.0",
        ],

        # Development tools
        "dev": [
            "pytest>=8.4.1",
            "pytest-asyncio>=1.0.0",
            "black>=25.1.0",
            "isort>=6.0.1",
            "pytest-timeout>=2.1.0",
            "pre-commit>=3.0.0",
        ],

        # Testing
        "test": [
            "pytest>=8.4.1",
            "pytest-asyncio>=1.0.0",
            "pytest-timeout>=2.1.0",
        ],

        # Convenience combinations
        "full": [
            "mcp>=1.0.0",
            "beautifulsoup4>=4.13.4",
            "playwright>=1.40.0",
            "pytubefix>=6.0.0",
            "anthropic>=0.55.0",
        ],

        # Everything
        "all": [
            "pytest>=8.4.1",
            "pytest-asyncio>=1.0.0",
            "black>=25.1.0",
            "isort>=6.0.1",
            "pytest-timeout>=2.1.0",
            "pre-commit>=3.0.0",
            "beautifulsoup4>=4.13.4",
            "playwright>=1.40.0",
            "pytubefix>=6.0.0",
            "anthropic>=0.55.0",
            "mcp>=1.0.0",
        ]
    },

    # UPDATED: Entry points with proper MCP support
    entry_points={
        "console_scripts": [
            # Main CLI commands
            "ambivo-agents=ambivo_agents.cli:main",
            "ambivo=ambivo_agents.cli:main",

            # MCP server entry point (for direct stdio usage)
            "ambivo-mcp-server=ambivo_agents.mcp.mcp_server:main",
        ],

        # MCP server registration (for MCP client discovery)
        "mcp.servers": [
            "ambivo-agents=ambivo_agents.mcp.server:main",
        ],
    },

    include_package_data=True,
    package_data={
        "ambivo_agents": [
            "*.yaml",
            "*.yml",
            "*.json",
            "*.md",
            "mcp/*.py",
            "mcp/*.yaml",
            "mcp/*.yml",
            "mcp/templates/*",
        ],
    },

    keywords=[
        "ai", "automation", "agents", "mcp", "model-context-protocol",
        "youtube", "media", "processing", "knowledge-base", "web-scraping",
        "claude", "openai", "anthropic", "langchain", "llama-index"
    ],

    project_urls={
        "Bug Reports": "https://github.com/ambivo-corp/ambivo-agents/issues",
        "Source": "https://github.com/ambivo-corp/ambivo-agents",
        "Documentation": "https://github.com/ambivo-corp/ambivo-agents/blob/main/README.md",
        "Company": "https://www.ambivo.com",
        "MCP Documentation": "https://spec.modelcontextprotocol.io/",
    },
)

# ============================================================================
# INSTALLATION INSTRUCTIONS FOR USERS
# ============================================================================

if __name__ == "__main__":
    print("""
    ============================================================================
    AMBIVO AGENTS - MCP-COMPLIANT INSTALLATION
    ============================================================================

    INSTALLATION OPTIONS:

    # Basic installation (no MCP)
    pip install ambivo-agents

    # With MCP support for Claude Desktop integration
    pip install ambivo-agents[mcp]

    # With web capabilities
    pip install ambivo-agents[web]

    # With media processing
    pip install ambivo-agents[media]

    # Full installation with all features
    pip install ambivo-agents[full]

    # Everything including development tools
    pip install ambivo-agents[all]

    ============================================================================
    MCP INTEGRATION USAGE:
    ============================================================================

    # Start MCP server for Claude Desktop
    ambivo-mcp-server

    # Or via main CLI
    ambivo mcp server

    # Generate Claude Desktop configuration
    ambivo mcp claude-config

    ============================================================================
    CLAUDE DESKTOP SETUP:
    ============================================================================

    1. Install with MCP support:
       pip install ambivo-agents[mcp]

    2. Generate config:
       ambivo mcp claude-config

    3. Add the output to your Claude Desktop config:
       ~/.claude_desktop_config.json (macOS/Linux)
       %APPDATA%/Claude/claude_desktop_config.json (Windows)

    4. Restart Claude Desktop

    5. Your Ambivo agents will appear as available tools in Claude!

    ============================================================================
    EXAMPLE CLAUDE DESKTOP CONFIG:
    ============================================================================

    {
      "mcpServers": {
        "ambivo-agents": {
          "command": "ambivo-mcp-server",
          "args": [],
          "env": {
            "AMBIVO_AGENTS_REDIS_HOST": "localhost",
            "AMBIVO_AGENTS_OPENAI_API_KEY": "your_key_here"
          }
        }
      }
    }

    ============================================================================
    """)