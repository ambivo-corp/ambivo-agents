#!/bin/bash
# set_env_template.sh - Template for Ambivo Agents Environment Variables
# INSTRUCTIONS: Replace placeholder values with your actual API keys and configuration

echo "🔧 Setting up environment variables for Ambivo Agents..."
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

# AWS Credentials (if using Bedrock)
# export AMBIVO_AGENTS_LLM_AWS_ACCESS_KEY_ID="your-aws-access-key"
# export AMBIVO_AGENTS_LLM_AWS_SECRET_ACCESS_KEY="your-aws-secret-key"
# export AMBIVO_AGENTS_LLM_AWS_REGION="us-east-1"

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
export AMBIVO_AGENTS_AGENT_CAPABILITIES_ENABLE_ANALYTICS="true"
export AMBIVO_AGENTS_AGENT_CAPABILITIES_ENABLE_API_AGENT="true"
export AMBIVO_AGENTS_AGENT_CAPABILITIES_ENABLE_DATABASE_AGENT="true"

# ================================
# ANALYTICS AGENT CONFIGURATION (Optional)
# ================================
# Uses consolidated Docker structure
export AMBIVO_AGENTS_ANALYTICS_DOCKER_IMAGE="sgosain/amb-ubuntu-python-public-pod"
export AMBIVO_AGENTS_ANALYTICS_INPUT_SUBDIR="analytics"
export AMBIVO_AGENTS_ANALYTICS_OUTPUT_SUBDIR="analytics"
export AMBIVO_AGENTS_ANALYTICS_TEMP_SUBDIR="analytics"
export AMBIVO_AGENTS_ANALYTICS_HANDOFF_SUBDIR="analytics"
export AMBIVO_AGENTS_ANALYTICS_DATABASE_HANDOFF_SOURCE="database"
export AMBIVO_AGENTS_ANALYTICS_TIMEOUT="120"
export AMBIVO_AGENTS_ANALYTICS_MEMORY_LIMIT="2g"
export AMBIVO_AGENTS_ANALYTICS_MAX_FILE_SIZE_MB="100"
export AMBIVO_AGENTS_ANALYTICS_MAX_ROWS_PREVIEW="1000"
export AMBIVO_AGENTS_ANALYTICS_ENABLE_VISUALIZATIONS="true"
export AMBIVO_AGENTS_ANALYTICS_ENABLE_SQL_QUERIES="true"

# ================================
# API AGENT CONFIGURATION (Optional)
# ================================
# Domain filtering - comma-separated lists
# export AMBIVO_AGENTS_API_AGENT_ALLOWED_DOMAINS="api.example.com,*.googleapis.com"
export AMBIVO_AGENTS_API_AGENT_BLOCKED_DOMAINS="localhost,127.0.0.1,0.0.0.0,169.254.169.254"
export AMBIVO_AGENTS_API_AGENT_ALLOWED_METHODS="GET,POST,PUT,PATCH,DELETE"
export AMBIVO_AGENTS_API_AGENT_VERIFY_SSL="true"
export AMBIVO_AGENTS_API_AGENT_TIMEOUT_SECONDS="30"
export AMBIVO_AGENTS_API_AGENT_MAX_SAFE_TIMEOUT="8"
export AMBIVO_AGENTS_API_AGENT_FORCE_DOCKER_ABOVE_TIMEOUT="true"

# ================================
# DATABASE AGENT CONFIGURATION (Optional)
# ================================
export AMBIVO_AGENTS_DATABASE_AGENT_STRICT_MODE="true"
export AMBIVO_AGENTS_DATABASE_AGENT_MAX_RESULT_ROWS="1000"
export AMBIVO_AGENTS_DATABASE_AGENT_QUERY_TIMEOUT="30"
export AMBIVO_AGENTS_DATABASE_AGENT_LOCAL_EXPORT_DIR="./database_exports"
export AMBIVO_AGENTS_DATABASE_AGENT_HANDOFF_SUBDIR="database"
export AMBIVO_AGENTS_DATABASE_AGENT_ENABLE_ANALYTICS_HANDOFF="true"
export AMBIVO_AGENTS_DATABASE_AGENT_AUTO_COPY_TO_SHARED="true"
export AMBIVO_AGENTS_DATABASE_AGENT_SUPPORTED_TYPES="mongodb,mysql,postgresql"

# ================================
# WEB SEARCH CONFIGURATION (Optional)
# ================================
# Uncomment and configure if you want web search functionality
# Get Brave API key from: https://api.search.brave.com/app/keys
export AMBIVO_AGENTS_WEB_SEARCH_BRAVE_API_KEY="your-brave-search-api-key"

# Alternative: AVES API (uncomment if using instead of Brave)
# export AMBIVO_AGENTS_WEB_SEARCH_AVESAPI_API_KEY="your-aves-api-key"

export AMBIVO_AGENTS_WEB_SEARCH_DEFAULT_MAX_RESULTS="10"
export AMBIVO_AGENTS_WEB_SEARCH_ENABLE_CACHING="true"

# ================================
# KNOWLEDGE BASE CONFIGURATION (Optional)
# ================================
# Uncomment and configure if you want knowledge base functionality
# Get Qdrant Cloud account from: https://cloud.qdrant.io/
export AMBIVO_AGENTS_KNOWLEDGE_BASE_QDRANT_URL="https://your-cluster-id.qdrant.tech:6333"
export AMBIVO_AGENTS_KNOWLEDGE_BASE_QDRANT_API_KEY="your-qdrant-api-key"
export AMBIVO_AGENTS_KNOWLEDGE_BASE_VECTOR_SIZE="1536"
export AMBIVO_AGENTS_KNOWLEDGE_BASE_SIMILARITY_TOP_K="5"
export AMBIVO_AGENTS_KNOWLEDGE_BASE_CHUNK_SIZE="1024"
export AMBIVO_AGENTS_KNOWLEDGE_BASE_CHUNK_OVERLAP="20"
export AMBIVO_AGENTS_DEFAULT_COLLECTION_PREFIX=""

# ================================
# WEB SCRAPING CONFIGURATION (Optional)
# ================================
# Uses consolidated Docker structure
# Get ScraperAPI account from: https://www.scraperapi.com/
export AMBIVO_AGENTS_WEB_SCRAPING_DOCKER_IMAGE="sgosain/amb-ubuntu-python-public-pod"
export AMBIVO_AGENTS_WEB_SCRAPING_OUTPUT_SUBDIR="scraper"
export AMBIVO_AGENTS_WEB_SCRAPING_TEMP_SUBDIR="scraper"
export AMBIVO_AGENTS_WEB_SCRAPING_HANDOFF_SUBDIR="scraper"
export AMBIVO_AGENTS_WEB_SCRAPING_PROXY_ENABLED="true"
export AMBIVO_AGENTS_WEB_SCRAPING_PROXY_CONFIG_HTTP_PROXY="http://scraperapi:your-scraperapi-key@proxy-server.scraperapi.com:8001"
export AMBIVO_AGENTS_WEB_SCRAPING_TIMEOUT="120"
export AMBIVO_AGENTS_WEB_SCRAPING_DOCKER_MEMORY_LIMIT="2g"
export AMBIVO_AGENTS_WEB_SCRAPING_DOCKER_CLEANUP="true"

# ================================
# CODE EXECUTOR AGENT CONFIGURATION (Enhanced Fallback)
# ================================
# Uses consolidated Docker structure
export AMBIVO_AGENTS_CODE_EXECUTOR_DOCKER_IMAGE="sgosain/amb-ubuntu-python-public-pod"
export AMBIVO_AGENTS_CODE_EXECUTOR_INPUT_SUBDIR="code"
export AMBIVO_AGENTS_CODE_EXECUTOR_OUTPUT_SUBDIR="code"
export AMBIVO_AGENTS_CODE_EXECUTOR_TEMP_SUBDIR="code"
export AMBIVO_AGENTS_CODE_EXECUTOR_HANDOFF_SUBDIR="code"
export AMBIVO_AGENTS_CODE_EXECUTOR_ENHANCED_FALLBACK_ENABLED="true"
export AMBIVO_AGENTS_CODE_EXECUTOR_AUTO_DETECT_FILE_OPERATIONS="true"
export AMBIVO_AGENTS_CODE_EXECUTOR_FALLBACK_TIMEOUT="120"
export AMBIVO_AGENTS_CODE_EXECUTOR_TIMEOUT="120"
export AMBIVO_AGENTS_CODE_EXECUTOR_MEMORY_LIMIT="2g"
export AMBIVO_AGENTS_CODE_EXECUTOR_MAX_OUTPUT_SIZE_MB="50"
export AMBIVO_AGENTS_CODE_EXECUTOR_RESTRICTED_IMPORTS="true"
export AMBIVO_AGENTS_CODE_EXECUTOR_SANDBOX_MODE="true"
export AMBIVO_AGENTS_CODE_EXECUTOR_ALLOW_NETWORK="false"

# ================================
# CONSOLIDATED DOCKER CONFIGURATION
# ================================
# Consolidated Docker-shared directory structure for all agents
export AMBIVO_AGENTS_DOCKER_IMAGES="sgosain/amb-ubuntu-python-public-pod"
export AMBIVO_AGENTS_DOCKER_MEMORY_LIMIT="512m"
export AMBIVO_AGENTS_DOCKER_TIMEOUT="60"

# Consolidated Docker Directory Structure
export AMBIVO_AGENTS_DOCKER_SHARED_BASE_DIR="./docker_shared"
export AMBIVO_AGENTS_DOCKER_CONTAINER_MOUNTS_INPUT="/docker_shared/input"
export AMBIVO_AGENTS_DOCKER_CONTAINER_MOUNTS_OUTPUT="/docker_shared/output"
export AMBIVO_AGENTS_DOCKER_CONTAINER_MOUNTS_TEMP="/docker_shared/temp"
export AMBIVO_AGENTS_DOCKER_CONTAINER_MOUNTS_HANDOFF="/docker_shared/handoff"
export AMBIVO_AGENTS_DOCKER_CONTAINER_MOUNTS_WORK="/docker_shared/work"

# Security settings for all Docker containers
export AMBIVO_AGENTS_DOCKER_NETWORK_DISABLED="true"
export AMBIVO_AGENTS_DOCKER_AUTO_REMOVE="true"

# Agent subdirectories (comma-separated lists)
export AMBIVO_AGENTS_DOCKER_AGENT_SUBDIRS_ANALYTICS="input/analytics,output/analytics,temp/analytics,handoff/analytics"
export AMBIVO_AGENTS_DOCKER_AGENT_SUBDIRS_MEDIA="input/media,output/media,temp/media,handoff/media"
export AMBIVO_AGENTS_DOCKER_AGENT_SUBDIRS_CODE="input/code,output/code,temp/code,handoff/code"
export AMBIVO_AGENTS_DOCKER_AGENT_SUBDIRS_DATABASE="handoff/database"
export AMBIVO_AGENTS_DOCKER_AGENT_SUBDIRS_SCRAPER="output/scraper,temp/scraper,handoff/scraper"

# ================================
# YOUTUBE DOWNLOAD CONFIGURATION
# ================================
export AMBIVO_AGENTS_YOUTUBE_DOWNLOAD_DOCKER_IMAGE="sgosain/amb-ubuntu-python-public-pod"
export AMBIVO_AGENTS_YOUTUBE_DOWNLOAD_DOWNLOAD_DIR="./youtube_downloads"
export AMBIVO_AGENTS_YOUTUBE_DOWNLOAD_TIMEOUT="600"
export AMBIVO_AGENTS_YOUTUBE_DOWNLOAD_DEFAULT_AUDIO_ONLY="true"

# ================================
# MEDIA EDITOR CONFIGURATION
# ================================
# Uses consolidated Docker structure
export AMBIVO_AGENTS_MEDIA_EDITOR_DOCKER_IMAGE="sgosain/amb-ubuntu-python-public-pod"
export AMBIVO_AGENTS_MEDIA_EDITOR_INPUT_SUBDIR="media"
export AMBIVO_AGENTS_MEDIA_EDITOR_OUTPUT_SUBDIR="media"
export AMBIVO_AGENTS_MEDIA_EDITOR_TEMP_SUBDIR="media"
export AMBIVO_AGENTS_MEDIA_EDITOR_HANDOFF_SUBDIR="media"
export AMBIVO_AGENTS_MEDIA_EDITOR_TIMEOUT="300"
export AMBIVO_AGENTS_MEDIA_EDITOR_MAX_FILE_SIZE_GB="5"
export AMBIVO_AGENTS_MEDIA_EDITOR_MAX_CONCURRENT_JOBS="3"
export AMBIVO_AGENTS_MEDIA_EDITOR_FFMPEG_THREADS="4"
export AMBIVO_AGENTS_MEDIA_EDITOR_ENABLE_GPU_ACCELERATION="false"
export AMBIVO_AGENTS_MEDIA_EDITOR_MEMORY_LIMIT="2g"

# ================================
# MEMORY MANAGEMENT CONFIGURATION (Optional)
# ================================
export AMBIVO_AGENTS_MEMORY_MANAGEMENT_COMPRESSION_ENABLED="true"
export AMBIVO_AGENTS_MEMORY_MANAGEMENT_COMPRESSION_ALGORITHM="lz4"
export AMBIVO_AGENTS_MEMORY_MANAGEMENT_COMPRESSION_LEVEL="1"
export AMBIVO_AGENTS_MEMORY_MANAGEMENT_CACHE_ENABLED="true"
export AMBIVO_AGENTS_MEMORY_MANAGEMENT_CACHE_MAX_SIZE="100"
export AMBIVO_AGENTS_MEMORY_MANAGEMENT_CACHE_TTL_SECONDS="3600"
export AMBIVO_AGENTS_MEMORY_MANAGEMENT_BACKUP_ENABLED="false"
export AMBIVO_AGENTS_MEMORY_MANAGEMENT_BACKUP_INTERVAL_MINUTES="60"
export AMBIVO_AGENTS_MEMORY_MANAGEMENT_BACKUP_DIRECTORY="./memory_backups"

# ================================
# CROSS-AGENT WORKFLOW CONFIGURATIONS
# ================================
# Database → Analytics handoff
export AMBIVO_AGENTS_WORKFLOWS_DATABASE_TO_ANALYTICS_ENABLED="true"
export AMBIVO_AGENTS_WORKFLOWS_DATABASE_TO_ANALYTICS_SOURCE_PATH="database"
export AMBIVO_AGENTS_WORKFLOWS_DATABASE_TO_ANALYTICS_TARGET_PATH="database"
export AMBIVO_AGENTS_WORKFLOWS_DATABASE_TO_ANALYTICS_AUTO_TRIGGER="true"
export AMBIVO_AGENTS_WORKFLOWS_DATABASE_TO_ANALYTICS_FILE_FORMATS=".csv,.xlsx,.json"

# Media → Host handoff
export AMBIVO_AGENTS_WORKFLOWS_MEDIA_TO_HOST_ENABLED="true"
export AMBIVO_AGENTS_WORKFLOWS_MEDIA_TO_HOST_SOURCE_PATH="media"
export AMBIVO_AGENTS_WORKFLOWS_MEDIA_TO_HOST_TARGET_PATH="."
export AMBIVO_AGENTS_WORKFLOWS_MEDIA_TO_HOST_AUTO_COPY="true"
export AMBIVO_AGENTS_WORKFLOWS_MEDIA_TO_HOST_FILE_FORMATS=".mp4,.mp3,.wav,.avi,.mov"

# Code Executor enhanced fallback
export AMBIVO_AGENTS_WORKFLOWS_CODE_EXECUTOR_FALLBACK_ENABLED="true"
export AMBIVO_AGENTS_WORKFLOWS_CODE_EXECUTOR_FALLBACK_INPUT_DETECTION="true"
export AMBIVO_AGENTS_WORKFLOWS_CODE_EXECUTOR_FALLBACK_OUTPUT_ORGANIZATION="true"
export AMBIVO_AGENTS_WORKFLOWS_CODE_EXECUTOR_FALLBACK_CLEANUP_TEMP="true"
export AMBIVO_AGENTS_WORKFLOWS_CODE_EXECUTOR_FALLBACK_PRESERVE_LOGS="true"

# Scraper → Analytics handoff
export AMBIVO_AGENTS_WORKFLOWS_SCRAPER_TO_ANALYTICS_ENABLED="true"
export AMBIVO_AGENTS_WORKFLOWS_SCRAPER_TO_ANALYTICS_SOURCE_PATH="scraper"
export AMBIVO_AGENTS_WORKFLOWS_SCRAPER_TO_ANALYTICS_TARGET_PATH="scraper"
export AMBIVO_AGENTS_WORKFLOWS_SCRAPER_TO_ANALYTICS_AUTO_CONVERT="true"
export AMBIVO_AGENTS_WORKFLOWS_SCRAPER_TO_ANALYTICS_FILE_FORMATS=".json,.csv,.html"

# ================================
# DOCKER DIRECTORY MANAGEMENT
# ================================
# Auto-creates and manages the consolidated directory structure
export AMBIVO_AGENTS_DOCKER_DIRECTORY_MANAGEMENT_AUTO_CREATE_STRUCTURE="true"
export AMBIVO_AGENTS_DOCKER_DIRECTORY_MANAGEMENT_CLEANUP_ON_EXIT="false"
export AMBIVO_AGENTS_DOCKER_DIRECTORY_MANAGEMENT_BACKUP_BEFORE_CLEANUP="true"
export AMBIVO_AGENTS_DOCKER_DIRECTORY_MANAGEMENT_MAX_TEMP_FILE_AGE_HOURS="24"
export AMBIVO_AGENTS_DOCKER_DIRECTORY_MANAGEMENT_DIRECTORY_PERMISSIONS="755"
export AMBIVO_AGENTS_DOCKER_DIRECTORY_MANAGEMENT_FILE_PERMISSIONS="644"
export AMBIVO_AGENTS_DOCKER_DIRECTORY_MANAGEMENT_LOG_FILE_OPERATIONS="true"
export AMBIVO_AGENTS_DOCKER_DIRECTORY_MANAGEMENT_TRACK_DISK_USAGE="true"
export AMBIVO_AGENTS_DOCKER_DIRECTORY_MANAGEMENT_MAX_SHARED_SIZE_GB="10"

# ================================
# SERVICE CONFIGURATION (Optional)
# ================================
export AMBIVO_AGENTS_SERVICE_MAX_SESSIONS="100"
export AMBIVO_AGENTS_SERVICE_LOG_LEVEL="INFO"
export AMBIVO_AGENTS_SERVICE_SESSION_TIMEOUT="3600"
export AMBIVO_AGENTS_SERVICE_ENABLE_METRICS="true"
export AMBIVO_AGENTS_SERVICE_LOG_TO_FILE="true"

# ================================
# MODERATOR CONFIGURATION (CRITICAL!)
# ================================
# List of agents the ModeratorAgent should initialize and manage
export AMBIVO_AGENTS_MODERATOR_DEFAULT_ENABLED_AGENTS="assistant,web_search,youtube_download,knowledge_base,media_editor,web_scraper,analytics,api_agent,database_agent"
export AMBIVO_AGENTS_MODERATOR_ROUTING_CONFIDENCE_THRESHOLD="0.6"

echo "✅ Environment variables configured!"
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