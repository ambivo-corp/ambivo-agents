#!/usr/bin/env python3
"""
Ambivo Agents Setup Script

Author: Hemant Gosain 'Sunny'
Company: Ambivo
Email: sgosain@ambivo.com
"""

from setuptools import setup, find_packages
import os

# Read README for long description
def read_readme():
    try:
        with open("README.md", "r", encoding="utf-8") as fh:
            return fh.read()
    except FileNotFoundError:
        return "Ambivo Agents - Multi-Agent AI System"

# Read requirements
def read_requirements():
    try:
        with open("requirements.txt", "r", encoding="utf-8") as fh:
            return [line.strip() for line in fh if line.strip() and not line.startswith("#")]
    except FileNotFoundError:
        return [
            "redis>=6.2.0",
            "redis[asyncio]",
            "docker>=6.0.0",
            "asyncio-mqtt>=0.11.0",
            "cachetools",
            "lz4",
            "requests>=2.32.4",
            "click>=8.2.1",
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
            "huggingface-hub",
            "llama-index-core",
            "llama-index-embeddings-langchain",
            "llama-index-llms-langchain",
            "llama-index-llms-openai",
            "llama-index-vector-stores-qdrant",
            "llama-index-readers-smart-pdf-loader",
            #"fastapi>=0.115.13",
            #"uvicorn[standard]>=0.34.3",
            "pydantic>=2.11.7",
            "boto3>=1.38.42",
            "python-dotenv>=1.1.1",
            "pyyaml>=6.0.2",
            "psutil>=7.0.0",
            "qdrant-client",
            "numexpr",
            "pytest>=8.4.1",
            "pytest-asyncio>=1.0.0",
            "black>=25.1.0",
            "isort>=6.0.1",
            "unstructured",
            "langchain-unstructured",
        ]

setup(
    name="ambivo-agents",
    version="1.0.3",
    author="Hemant Gosain 'Sunny'",
    author_email="sgosain@ambivo.com",
    description="Multi-Agent AI System for automation including YouTube downloads, media processing, knowledge base operations, and more",
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
    ],
    python_requires=">=3.11",
    install_requires=read_requirements(),
    extras_require={
        "dev": [
            "pytest>=8.4.1",
            "pytest-asyncio>=1.0.0",
            "black>=25.1.0",
            "isort>=6.0.1",
            "pytest-timeout>=2.1.0",
        ],
        "test": [
            "pytest>=8.4.1",
            "pytest-asyncio>=1.0.0",
            "pytest-timeout>=2.1.0",
        ],
        "all": [
            "pytest>=8.4.1",
            "pytest-asyncio>=1.0.0",
            "black>=25.1.0",
            "isort>=6.0.1",
            "pytest-timeout>=2.1.0",
            "beautifulsoup4>=4.13.4",
            "playwright>=1.40.0",
            "pytubefix>=6.0.0",
            "anthropic>=0.55.0",
        ]
    },
    entry_points={
        "console_scripts": [
            "ambivo-agents=ambivo_agents.cli:cli",
            "ambivo=ambivo_agents.cli:cli",  # Short alias
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
    keywords="ai, automation, agents, youtube, media, processing, knowledge-base, web-scraping",
    project_urls={
        "Bug Reports": "https://github.com/ambivo-corp/ambivo-agents",
        "Source": "https://github.com/ambivo-corp/ambivo-agents.git",
        "Documentation": "https://github.com/ambivo-corp/ambivo-agents.git/blob/main/README.md",
        "Company": "https://www.ambivo.com",
    },
)