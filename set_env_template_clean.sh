#!/bin/bash
# Ambivo Agents v2.0.0 — Minimal Environment Variables
# Only set what you need. Everything else has sensible defaults.
# For full configuration, use agent_config.yaml instead.

# LLM Provider (required — at least one)
export AMBIVO_AGENTS_OPENAI_API_KEY="sk-your-openai-key"
export AMBIVO_AGENTS_ANTHROPIC_API_KEY="sk-ant-your-anthropic-key"

# Web Search (optional — enables WebSearchAgent)
export AMBIVO_AGENTS_BRAVE_API_KEY="your-brave-key"
export AMBIVO_AGENTS_ENABOK it works but tLE_WEB_SEARCH="true"

# Web Scraping works out of the box (Jina Reader, no key needed)
export AMBIVO_AGENTS_ENABLE_WEB_SCRAPING="true"

echo "Environment configured for ambivo-agents v2.0.0"
echo "For Redis, Qdrant, AWS, or advanced settings, use agent_config.yaml"
