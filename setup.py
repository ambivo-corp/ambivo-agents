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
            "redis>=4.5.0",
            "python-dotenv>=1.0.0",
            "pyyaml>=6.0",
            "click>=8.0.0",
            "openai>=1.0.0",
            "anthropic>=0.8.0",
            "docker>=6.0.0",
            "requests>=2.31.0",
        ]

setup(
    name="ambivo-agents",
    version="1.3.1",
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
        "Programming Language :: Python :: 3.8",
        "Programming Language :: Python :: 3.9",
        "Programming Language :: Python :: 3.10",
        "Programming Language :: Python :: 3.11",
        "Programming Language :: Python :: 3.12",
        "Topic :: Software Development :: Libraries :: Python Modules",
        "Topic :: Internet :: WWW/HTTP :: Indexing/Search",
        "Topic :: Multimedia :: Video",
        "Topic :: Scientific/Engineering :: Artificial Intelligence",
    ],
    python_requires=">=3.8",
    install_requires=read_requirements(),
    extras_require={
        "dev": [
            "pytest>=7.0.0",
            "pytest-asyncio>=0.21.0",
            "black>=23.0.0",
            "flake8>=6.0.0",
            "mypy>=1.0.0",
        ],
        "all": [
            "qdrant-client>=1.6.0",
            "llama-index>=0.9.0",
            "langchain-unstructured>=0.1.0",
            "beautifulsoup4>=4.12.0",
            "playwright>=1.40.0",
            "pytubefix>=6.0.0",
            "pydantic>=2.0.0",
            "boto3>=1.34.0",
            "langchain-openai>=0.0.5",
            "langchain-anthropic>=0.1.0",
            "langchain-aws>=0.1.0",
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