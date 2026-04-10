#!/bin/bash
# set_env_template_clean.sh - Environment Variables for Ambivo Agents v2.0.0
# Replace placeholder values with your actual API keys

# ================================
# LLM PROVIDER (required - at least one)
# ================================
export AMBIVO_AGENTS_OPENAI_API_KEY="sk-your-openai-key"
# or
export AMBIVO_AGENTS_ANTHROPIC_API_KEY="sk-ant-your-anthropic-key"

# Optional: AWS Bedrock
export AMBIVO_AGENTS_AWS_ACCESS_KEY_ID="your-aws-key"
export AMBIVO_AGENTS_AWS_SECRET_ACCESS_KEY="your-aws-secret"
export AMBIVO_AGENTS_AWS_REGION="us-east-1"

# LLM settings
export AMBIVO_AGENTS_LLM_PREFERRED_PROVIDER="anthropic"
export AMBIVO_AGENTS_LLM_TEMPERATURE="0.5"

# ================================
# AGENT CAPABILITIES
# ================================
export AMBIVO_AGENTS_ENABLE_WEB_SEARCH="true"
export AMBIVO_AGENTS_ENABLE_WEB_SCRAPING="true"
export AMBIVO_AGENTS_ENABLE_KNOWLEDGE_BASE="false"  # requires Qdrant

# ================================
# WEB SEARCH (optional)
# ================================
export AMBIVO_AGENTS_BRAVE_API_KEY="your-brave-key"

# ================================
# WEB SCRAPING (optional - Jina Reader works without key)
# ================================
export AMBIVO_AGENTS_SCRAPING_PROVIDER="jina"  # jina | firecrawl | requests
export AMBIVO_AGENTS_JINA_API_KEY=""  # optional, for higher rate limits
export AMBIVO_AGENTS_FIRECRAWL_API_KEY=""  # if using firecrawl
export AMBIVO_AGENTS_SCRAPING_TIMEOUT="60"

# ================================
# KNOWLEDGE BASE (optional - requires Qdrant)
# ================================
export AMBIVO_AGENTS_QDRANT_URL="https://your-cluster.qdrant.tech:6333"
export AMBIVO_AGENTS_QDRANT_API_KEY="your-qdrant-key"

# ================================
# REDIS (optional - in-memory is default)
# ================================
export AMBIVO_AGENTS_REDIS_HOST="localhost"
export AMBIVO_AGENTS_REDIS_PORT="6379"
export AMBIVO_AGENTS_REDIS_PASSWORD=""

# ================================
# SERVICE
# ================================
export AMBIVO_AGENTS_LOG_LEVEL="INFO"

echo "Environment configured for ambivo-agents v2.0.0"
