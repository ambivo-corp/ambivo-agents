#!/usr/bin/env python3
"""
Ambivo Agents Setup Script

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
        return "Ambivo Agents - Multi-Agent AI System"


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
    version="1.1.5",
    author="Hemant Gosain 'Sunny'",
    author_email="info@ambivo.com",
    description="Multi-Agent AI System for automation",
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

    # Optional dependencies
    extras_require={
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
        ]
    },

    # Entry points
    entry_points={
        "console_scripts": [
            # Main CLI commands
            "ambivo-agents=ambivo_agents.cli:main",
            "ambivo=ambivo_agents.cli:main",
        ],
    },

    include_package_data=True,
    package_data={
        "ambivo_agents": [
            "*.yaml",
            "*.yml",
            "*.json",
            "*.md",
        ],
    },

    keywords=[
        "ai", "automation", "agents",
        "youtube", "media", "processing", "knowledge-base", "web-scraping",
        "claude", "openai", "anthropic", "langchain", "llama-index"
    ],

    project_urls={
        "Bug Reports": "https://github.com/ambivo-corp/ambivo-agents/issues",
        "Source": "https://github.com/ambivo-corp/ambivo-agents",
        "Documentation": "https://github.com/ambivo-corp/ambivo-agents/blob/main/README.md",
        "Company": "https://www.ambivo.com",
    },
)

# ============================================================================
# INSTALLATION INSTRUCTIONS FOR USERS
# ============================================================================

if __name__ == "__main__":
    print("""
    ============================================================================
    AMBIVO AGENTS INSTALLATION
    ============================================================================

    INSTALLATION OPTIONS:

    # Basic installation
    pip install ambivo-agents

    # With web capabilities
    pip install ambivo-agents[web]

    # With media processing
    pip install ambivo-agents[media]

    # Full installation with all features
    pip install ambivo-agents[full]

    # Everything including development tools
    pip install ambivo-agents[all]

    ============================================================================
    QUICK START:
    ============================================================================

    from ambivo_agents.agents.youtube_download import YouTubeDownloadAgent
    from ambivo_agents.agents.knowledge_base import KnowledgeBaseAgent

    # Create agent with auto-context
    agent, context = YouTubeDownloadAgent.create(user_id="your_user")
    response = agent.chat_sync("Download https://youtube.com/watch?v=example")
    print(response)

    ============================================================================
    """)