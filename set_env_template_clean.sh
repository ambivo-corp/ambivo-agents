#!/bin/bash
# set_env_template_clean.sh - Template for Ambivo Agents Environment Variables (cleaned version)
# INSTRUCTIONS: Replace placeholder values with your actual API keys and configuration
# Reduced from 157 to 89 actually used environment variables

echo "🔧 Setting up environment variables for Ambivo Agents (cleaned template)..."
echo "⚠️  Make sure to replace all placeholder values with your actual keys!"

# ================================
# CORE REQUIRED VARIABLES
# ================================

# Redis Configuration (REQUIRED)
# Replace with your Redis connection details
export AMBIVO_AGENTS_REDIS_HOST="your-redis-host.com"
export AMBIVO_AGENTS_REDIS_PORT="6379"
export AMBIVO_AGENTS_REDIS_DB="0"
export AMBIVO_AGENTS_REDIS_PASSWORD="your-redis-password"

# LLM Configuration (REQUIRED - at least one)
export AMBIVO_AGENTS_LLM_PREFERRED_PROVIDER="openai"  # or "anthropic"
export AMBIVO_AGENTS_LLM_TEMPERATURE="0.5"
export AMBIVO_AGENTS_LLM_MAX_TOKENS="4000"

# OpenAI API Key (if using OpenAI)
export AMBIVO_AGENTS_LLM_OPENAI_API_KEY="sk-your-openai-api-key-here"

# Anthropic API Key (if using Claude)
export AMBIVO_AGENTS_LLM_ANTHROPIC_API_KEY="sk-ant-your-anthropic-api-key-here"

# Voyage API Key (for embeddings)
export AMBIVO_AGENTS_LLM_VOYAGE_API_KEY="pa-your-voyage-api-key-here"

# AWS Credentials (if using Bedrock)
export AMBIVO_AGENTS_LLM_AWS_ACCESS_KEY_ID="your-aws-access-key"
export AMBIVO_AGENTS_LLM_AWS_SECRET_ACCESS_KEY="your-aws-secret-key"
export AMBIVO_AGENTS_LLM_AWS_REGION="us-east-1"

# ================================
# AGENT CAPABILITIES (REQUIRED!)
# ================================
# Enable the agents you want to use
export AMBIVO_AGENTS_AGENT_CAPABILITIES_ENABLE_KNOWLEDGE_BASE="true"
export AMBIVO_AGENTS_AGENT_CAPABILITIES_ENABLE_WEB_SEARCH="true"
export AMBIVO_AGENTS_AGENT_CAPABILITIES_ENABLE_CODE_EXECUTION="true"
export AMBIVO_AGENTS_AGENT_CAPABILITIES_ENABLE_FILE_PROCESSING="true"
export AMBIVO_AGENTS_AGENT_CAPABILITIES_ENABLE_WEB_INGESTION="true"
export AMBIVO_AGENTS_AGENT_CAPABILITIES_ENABLE_API_CALLS="true"
export AMBIVO_AGENTS_AGENT_CAPABILITIES_ENABLE_WEB_SCRAPING="true"
export AMBIVO_AGENTS_AGENT_CAPABILITIES_ENABLE_PROXY_MODE="true"
export AMBIVO_AGENTS_AGENT_CAPABILITIES_ENABLE_MEDIA_EDITOR="true"
export AMBIVO_AGENTS_AGENT_CAPABILITIES_ENABLE_YOUTUBE_DOWNLOAD="true"
export AMBIVO_AGENTS_AGENT_CAPABILITIES_ENABLE_API_AGENT="true"
export AMBIVO_AGENTS_AGENT_CAPABILITIES_ENABLE_ANALYTICS="true"
export AMBIVO_AGENTS_AGENT_CAPABILITIES_ENABLE_DATABASE_AGENT="true"

# ================================
# AGENT ENABLEMENT CONFIGURATION
# ================================
export AMBIVO_AGENTS_MODERATOR_ENABLED="true"
export AMBIVO_AGENTS_ANALYTICS_ENABLED="true"
export AMBIVO_AGENTS_CODE_EXECUTOR_ENABLED="true"
export AMBIVO_AGENTS_YOUTUBE_DOWNLOAD_ENABLED="true"
export AMBIVO_AGENTS_MEDIA_EDITOR_ENABLED="true"
export AMBIVO_AGENTS_WEB_SCRAPER_ENABLED="true"

# ================================
# WEB SEARCH CONFIGURATION (Optional)
# ================================
# Get Brave API key from: https://api.search.brave.com/app/keys
export AMBIVO_AGENTS_WEB_SEARCH_BRAVE_API_KEY="your-brave-search-api-key"

# Alternative: AVES API (if using instead of Brave)
export AMBIVO_AGENTS_WEB_SEARCH_AVESAPI_API_KEY="your-aves-api-key"

export AMBIVO_AGENTS_WEB_SEARCH_DEFAULT_MAX_RESULTS="10"

# ================================
# KNOWLEDGE BASE CONFIGURATION (Optional)
# ================================
# Get Qdrant Cloud account from: https://cloud.qdrant.io/
export AMBIVO_AGENTS_KNOWLEDGE_BASE_QDRANT_URL="https://your-cluster-id.qdrant.tech:6333"
export AMBIVO_AGENTS_KNOWLEDGE_BASE_QDRANT_API_KEY="your-qdrant-api-key"
export AMBIVO_AGENTS_KNOWLEDGE_BASE_CHUNK_SIZE="1024"
export AMBIVO_AGENTS_KNOWLEDGE_BASE_CHUNK_OVERLAP="20"
export AMBIVO_AGENTS_KNOWLEDGE_BASE_SIMILARITY_TOP_K="5"
export AMBIVO_AGENTS_KNOWLEDGE_BASE_VECTOR_SIZE="1536"
export AMBIVO_AGENTS_KNOWLEDGE_BASE_DISTANCE_METRIC="cosine"
export AMBIVO_AGENTS_KNOWLEDGE_BASE_DEFAULT_COLLECTION_PREFIX=""
export AMBIVO_AGENTS_DEFAULT_COLLECTION_PREFIX=""

# ================================
# YOUTUBE DOWNLOAD CONFIGURATION (Optional)
# ================================
export AMBIVO_AGENTS_YOUTUBE_DOWNLOAD_DOCKER_IMAGE="sgosain/amb-ubuntu-python-public-pod"
export AMBIVO_AGENTS_YOUTUBE_DOWNLOAD_DOWNLOAD_DIR="./youtube_downloads"
export AMBIVO_AGENTS_YOUTUBE_DOWNLOAD_TIMEOUT="600"
export AMBIVO_AGENTS_YOUTUBE_DOWNLOAD_DEFAULT_AUDIO_ONLY="true"
export AMBIVO_AGENTS_YOUTUBE_DOWNLOAD_MEMORY_LIMIT="512m"

# ================================
# MEDIA EDITOR CONFIGURATION (Optional)
# ================================
export AMBIVO_AGENTS_MEDIA_EDITOR_DOCKER_IMAGE="sgosain/amb-ubuntu-python-public-pod"
export AMBIVO_AGENTS_MEDIA_EDITOR_INPUT_DIR="./examples/media_input"
export AMBIVO_AGENTS_MEDIA_EDITOR_OUTPUT_DIR="./examples/media_output"
export AMBIVO_AGENTS_MEDIA_EDITOR_TIMEOUT="300"
export AMBIVO_AGENTS_MEDIA_EDITOR_MEMORY_LIMIT="2g"
export AMBIVO_AGENTS_MEDIA_EDITOR_MAX_FILE_SIZE_GB="5"
export AMBIVO_AGENTS_MEDIA_EDITOR_MAX_CONCURRENT_JOBS="3"

# ================================
# CODE EXECUTOR CONFIGURATION (Optional)
# ================================
export AMBIVO_AGENTS_CODE_EXECUTOR_DOCKER_IMAGE="sgosain/amb-ubuntu-python-public-pod"
export AMBIVO_AGENTS_CODE_EXECUTOR_TIMEOUT="120"
export AMBIVO_AGENTS_CODE_EXECUTOR_MEMORY_LIMIT="2g"
export AMBIVO_AGENTS_CODE_EXECUTOR_SANDBOX_MODE="true"
export AMBIVO_AGENTS_CODE_EXECUTOR_ALLOW_NETWORK="false"

# ================================
# ANALYTICS CONFIGURATION (Optional)
# ================================
export AMBIVO_AGENTS_ANALYTICS_DOCKER_IMAGE="sgosain/amb-ubuntu-python-public-pod"
export AMBIVO_AGENTS_ANALYTICS_TIMEOUT="120"
export AMBIVO_AGENTS_ANALYTICS_MEMORY_LIMIT="2g"

# ================================
# API AGENT CONFIGURATION (Optional)
# ================================
# Domain filtering - Leave ALLOWED_DOMAINS empty to allow all external domains
export AMBIVO_AGENTS_API_AGENT_ALLOWED_DOMAINS=""
export AMBIVO_AGENTS_API_AGENT_BLOCKED_DOMAINS="localhost,127.0.0.1,0.0.0.0,169.254.169.254"
export AMBIVO_AGENTS_API_AGENT_ALLOWED_METHODS="GET,POST,PUT,PATCH,DELETE"
export AMBIVO_AGENTS_API_AGENT_VERIFY_SSL="true"
export AMBIVO_AGENTS_API_AGENT_TIMEOUT_SECONDS="30"
export AMBIVO_AGENTS_API_AGENT_MAX_SAFE_TIMEOUT="8"
export AMBIVO_AGENTS_API_AGENT_FORCE_DOCKER_ABOVE_TIMEOUT="true"
export AMBIVO_AGENTS_API_AGENT_DOCKER_IMAGE="sgosain/amb-ubuntu-python-public-pod"

# ================================
# WEB SCRAPING CONFIGURATION (Optional)
# ================================
export AMBIVO_AGENTS_WEB_SCRAPING_DOCKER_IMAGE="sgosain/amb-ubuntu-python-public-pod"
export AMBIVO_AGENTS_WEB_SCRAPING_PROXY_ENABLED="true"
export AMBIVO_AGENTS_WEB_SCRAPING_TIMEOUT="120"
export AMBIVO_AGENTS_WEB_SCRAPING_DOCKER_MEMORY_LIMIT="2g"

# ================================
# DATABASE AGENT CONFIGURATION (Optional)
# ================================
export AMBIVO_AGENTS_DATABASE_AGENT_STRICT_MODE="true"
export AMBIVO_AGENTS_DATABASE_AGENT_MAX_RESULT_ROWS="1000"
export AMBIVO_AGENTS_DATABASE_AGENT_QUERY_TIMEOUT="30"
export AMBIVO_AGENTS_DATABASE_AGENT_LOCAL_EXPORT_DIR="./database_exports"
export AMBIVO_AGENTS_DATABASE_AGENT_ENABLE_ANALYTICS_HANDOFF="true"
export AMBIVO_AGENTS_DATABASE_AGENT_AUTO_COPY_TO_SHARED="true"
export AMBIVO_AGENTS_DATABASE_AGENT_SUPPORTED_TYPES="mongodb,mysql,postgresql"

# ================================
# DOCKER CONFIGURATION (Required)
# ================================
export AMBIVO_AGENTS_DOCKER_IMAGES="sgosain/amb-ubuntu-python-public-pod"
export AMBIVO_AGENTS_DOCKER_MEMORY_LIMIT="512m"
export AMBIVO_AGENTS_DOCKER_TIMEOUT="60"
export AMBIVO_AGENTS_DOCKER_WORK_DIR="/opt/ambivo/work_dir"

# ================================
# SERVICE CONFIGURATION (Optional)
# ================================
export AMBIVO_AGENTS_SERVICE_MAX_SESSIONS="100"
export AMBIVO_AGENTS_SERVICE_LOG_LEVEL="INFO"
export AMBIVO_AGENTS_SERVICE_SESSION_TIMEOUT="3600"
export AMBIVO_AGENTS_SERVICE_LOG_TO_FILE="true"

# ================================
# FILE ACCESS SECURITY (Optional)
# ================================
# Comma-separated list of directories to restrict file access
export AMBIVO_AGENTS_FILE_ACCESS_RESTRICTED_DIRS="/etc,/var/log,/sys,/proc,/dev"

echo "✅ Environment variables configured (89 used variables only)!"
echo ""
echo "🔍 Checking configuration..."

# Check for placeholder values
check_placeholders() {
    local has_placeholders=false

    # Check Redis
    if [[ "$AMBIVO_AGENTS_REDIS_HOST" == "your-redis-host.com" ]]; then
        echo "❌ Please replace Redis host placeholder with your actual Redis host"
        has_placeholders=true
    fi

    if [[ "$AMBIVO_AGENTS_REDIS_PASSWORD" == "your-redis-password" ]]; then
        echo "❌ Please replace Redis password placeholder with your actual Redis password"
        has_placeholders=true
    fi

    # Check LLM keys
    if [[ "$AMBIVO_AGENTS_LLM_OPENAI_API_KEY" == "sk-your-openai-api-key-here" ]]; then
        echo "⚠️  OpenAI API key is still a placeholder"
        has_placeholders=true
    fi

    if [[ "$AMBIVO_AGENTS_LLM_ANTHROPIC_API_KEY" == "sk-ant-your-anthropic-api-key-here" ]]; then
        echo "⚠️  Anthropic API key is still a placeholder"
        has_placeholders=true
    fi

    # Check web search
    if [[ "$AMBIVO_AGENTS_WEB_SEARCH_BRAVE_API_KEY" == "your-brave-search-api-key" ]]; then
        echo "⚠️  Brave Search API key is still a placeholder (web search won't work)"
    fi

    # Check knowledge base
    if [[ "$AMBIVO_AGENTS_KNOWLEDGE_BASE_QDRANT_URL" == "https://your-cluster-id.qdrant.tech:6333" ]]; then
        echo "⚠️  Qdrant URL is still a placeholder (knowledge base won't work)"
    fi

    if [[ "$AMBIVO_AGENTS_KNOWLEDGE_BASE_QDRANT_API_KEY" == "your-qdrant-api-key" ]]; then
        echo "⚠️  Qdrant API key is still a placeholder (knowledge base won't work)"
    fi

    if [[ "$has_placeholders" == "true" ]]; then
        echo ""
        echo "🚨 CRITICAL: You have placeholder values that need to be replaced!"
        echo "📝 Please edit this script and replace placeholder values with your actual:"
        echo "   • Redis connection details"
        echo "   • API keys (OpenAI or Anthropic)"
        echo "   • Optional service credentials"
        echo ""
        return 1
    fi

    return 0
}

if check_placeholders; then
    echo "🧪 Testing configuration loading..."

    # Test if Python can load the config
    python3 -c "
try:
    from ambivo_agents.config.loader import load_config, check_config_health
    config = load_config()
    print('✅ Config loaded successfully')
    print('📊 Available sections:', list(config.keys()))

    # Health check
    health = check_config_health()
    print(f'🏥 Config source: {health[\"config_source\"]}')
    print(f'🔴 Redis configured: {health[\"redis_configured\"]}')
    print(f'🤖 LLM configured: {health[\"llm_configured\"]}')
    print(f'🎯 Enabled agents: {health[\"agents_enabled\"]}')

    if health['errors']:
        print('⚠️  Warnings:')
        for error in health['errors']:
            print(f'   • {error}')

except Exception as e:
    print(f'❌ Config loading failed: {e}')
    print('💡 Make sure you have replaced all placeholder values')
"

    echo ""
    echo "🚀 Ready to run your test script!"
    echo "💡 Usage: python examples/moderator_agent.py"
else
    echo ""
    echo "❌ Configuration incomplete - please fix placeholder values first"
    echo "💡 Edit this script and replace all 'your-*' placeholders with actual values"
fi

echo ""
echo "📋 Summary of cleaned template:"
echo "• Reduced from 157 to 89 environment variables"
echo "• Only includes variables actually used in the codebase"
echo "• Added FILE_ACCESS_RESTRICTED_DIRS security setting"
echo "• Organized logically by agent functionality"