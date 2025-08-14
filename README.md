# Ambivo Agents - Multi-Agent AI System

A toolkit for AI-powered automation including data analytics with DuckDB, media processing, knowledge base operations, web scraping, YouTube downloads, HTTP/REST API integration, and more.

## Alpha Release Disclaimer

**This library is currently in alpha stage.** While functional, it may contain bugs, undergo breaking changes, and lack complete documentation. Developers should thoroughly evaluate and test the library before considering it for production use.

For production scenarios, we recommend:
- Extensive testing in your specific environment
- Implementing proper error handling and monitoring
- Having rollback plans in place
- Staying updated with releases for critical fixes

## Table of Contents

- [Quick Start](#quick-start)
- [Agent Creation](#agent-creation)
- [Features](#features)
- [Available Agents](#available-agents)
- [Workflow System](#workflow-system)
- [System Messages](#system-messages)
- [Prerequisites](#prerequisites)
- [Installation](#installation)
- [Configuration](#configuration)
- [Configuration Methods](#configuration-methods)
- [Project Structure](#project-structure)
- [Usage Examples](#usage-examples)
- [Streaming System](#streaming-system)
- [Session Management](#session-management)
- [Web API Integration](#web-api-integration)
- [Command Line Interface](#command-line-interface)
- [Architecture](#architecture)
- [Docker Setup](#docker-setup)
  - [Agent Handoff Mechanism](#agent-handoff-mechanism)
  - [File Access Security Configuration](#file-access-security-configuration)
- [Troubleshooting](#troubleshooting)
- [Security Considerations](#security-considerations)
- [Contributing](#contributing)
- [License](#license)
- [Author](#author)
- [Support](#support)

## Quick Start

### ModeratorAgent Example

The **ModeratorAgent** automatically routes queries to specialized agents:

```python
from ambivo_agents import ModeratorAgent
import asyncio

async def main():
    # Create the moderator
    moderator, context = ModeratorAgent.create(user_id="john")
    
    print(f"Session: {context.session_id}")
    
    # Auto-routing examples
    response1 = await moderator.chat("Download audio from https://youtube.com/watch?v=example")
    response2 = await moderator.chat("Search for latest AI trends")
    response3 = await moderator.chat("Extract audio from video.mp4 as MP3")
    response4 = await moderator.chat("GET https://api.github.com/users/octocat")
    response5 = await moderator.chat("Load data from sales.csv and analyze it")
    response6 = await moderator.chat("What is machine learning?")
    
    # Check available agents
    status = await moderator.get_agent_status()
    print(f"Available agents: {list(status['active_agents'].keys())}")
    
    # Cleanup
    await moderator.cleanup_session()

asyncio.run(main())
```

### Command Line Usage

```bash
# Install and run
pip install ambivo-agents

# Interactive mode
ambivo-agents

# Single commands
ambivo-agents -q "Download audio from https://youtube.com/watch?v=example"
ambivo-agents -q "Search for Python tutorials"
ambivo-agents -q "Load data from sales.csv and analyze it"
ambivo-agents -q "GET https://jsonplaceholder.typicode.com/posts/1"
```

## Agent Creation

### ModeratorAgent (Recommended)

```python
from ambivo_agents import ModeratorAgent

# Create moderator with auto-routing
moderator, context = ModeratorAgent.create(user_id="john")

# Chat with automatic agent selection
result = await moderator.chat("Download audio from https://youtube.com/watch?v=example")

# Cleanup
await moderator.cleanup_session()
```

**Use ModeratorAgent for:**
- Multi-purpose applications
- Intelligent routing between capabilities
- Context-aware conversations
- Simplified development

### Direct Agent Creation

```python
from ambivo_agents import YouTubeDownloadAgent

# Create specific agent
agent, context = YouTubeDownloadAgent.create(user_id="john")

# Use agent directly
result = await agent._download_youtube_audio("https://youtube.com/watch?v=example")

# Cleanup
await agent.cleanup_session()
```

**Use Direct Creation for:**
- Single-purpose applications
- Specific workflows with known requirements
- Performance-critical applications
- Custom integrations

## Features

### Core Capabilities
- **ModeratorAgent**: Intelligent multi-agent orchestrator with automatic routing
- **Smart Routing**: Automatically routes queries to appropriate specialized agents
- **Data Analytics**: In-memory DuckDB integration with CSV/XLS ingestion and text-based visualizations
- **File Ingestion & Processing**: All agents can read/parse JSON, CSV, XML, YAML files and insert into databases
- **Context Memory**: Maintains conversation history across interactions
- **Docker Integration**: Secure, isolated execution environment
- **Redis Memory**: Persistent conversation memory with compression
- **Multi-Provider LLM**: Automatic failover between OpenAI, Anthropic, and AWS Bedrock
- **Configuration-Driven**: All features controlled via `agent_config.yaml`
- **Workflow System**: Multi-agent workflows with parallel and sequential execution
- **System Messages**: Customizable system prompts for agent behavior control

## Available Agents

### ModeratorAgent 
- Intelligent orchestrator that routes to specialized agents
- Context-aware multi-turn conversations
- Automatic agent selection based on query analysis
- Session management and cleanup
- Workflow execution and coordination

### Database Agent (Optional)
- Secure connections to MongoDB, MySQL, and PostgreSQL databases
- Schema inspection and table structure exploration
- Natural language to SQL/MongoDB query conversion
- Safe query execution with read-only mode by default
- **File ingestion support**: Insert JSON/CSV files directly into database tables
- Data export to CSV for analytics handoff
- Automatic integration with Analytics Agent for visualization
- Query result formatting with tables and statistics
- **Note**: Requires installation with `pip install ambivo-agents[database]`

### Analytics Agent
- CSV/XLS file ingestion into in-memory DuckDB
- Schema exploration and data quality assessment  
- Natural language to SQL query conversion
- Text-based chart generation (bar charts, line charts, tables)
- Chart recommendations based on data characteristics
- Docker-only execution for security
- Business intelligence and data insights

### Assistant Agent
- General purpose conversational AI
- Context-aware responses
- Multi-turn conversations
- Customizable system messages

### Code Executor Agent
- Secure Python and Bash execution in Docker
- Isolated environment with resource limits
- Real-time output streaming

### Web Search Agent
- Multi-provider search (Brave, AVES APIs)
- Academic search capabilities
- Automatic provider failover

### Web Scraper Agent
- Proxy-enabled scraping (ScraperAPI compatible)
- Playwright and requests-based scraping
- Batch URL processing with rate limiting

### Knowledge Base Agent
- Document ingestion (PDF, DOCX, TXT, web URLs)
- Vector similarity search with Qdrant
- Semantic question answering

### Media Editor Agent
- Audio/video processing with FFmpeg
- Format conversion, resizing, trimming
- Audio extraction and volume adjustment

### YouTube Download Agent
- Download videos and audio from YouTube
- Docker-based execution with pytubefix
- Automatic title sanitization and metadata extraction

### Gather Agent
- Conversational form-filling assistant that asks one question at a time and validates answers.
- Ingest questionnaire from JSON/YAML pasted into chat, a local file path, or a URL.
- Supported types: free-text, yes-no, single-select, multi-select. Prompts include available options for yes-no/single/multi.
- Conditional Dependent Question Logic:
  - Yes–No: dependent question shown when parent is affirmative (Yes/Y/True) unless specific trigger values are configured.
  - Single-Select: shown when selected value is in trigger list; default is any value except explicit "No" if no triggers.
  - Multi-Select: shown when at least one selected value is in trigger list; default is non-empty selection if no triggers.
  - Free-Text: shown when parent answer is non-empty (optional yes/no interpretation if triggers include yes/no terms).
- Submission to a configured endpoint with statuses: successfully_collected, partially_collected, conversation_aborted.
- Session memory persists for ~1 hour by default (configurable).
- Optional LLM-based validation for free‑text answers and optional LLM prompt rephrasing.

Usage
```bash
# Interactive CLI demo (waits for your input after each question)
python examples/gather_cli.py

# Load questionnaire from a file path or URL
python examples/gather_cli.py --path ./questionnaire.yaml
python examples/gather_cli.py --path https://example.com/questionnaire.json

# Do a real HTTP submission (configure endpoint in agent_config.yaml)
python examples/gather_cli.py --real-submit

# Minimal scripted example
python examples/gather_simple.py
```

Configuration
```yaml
agent_capabilities:
  enable_gather: true

gather:
  submission_endpoint: "https://your-api.example.com/submit"
  submission_method: "POST"
  submission_headers:
    Authorization: "Bearer your-api-token"
    Content-Type: "application/json"
  memory_ttl_seconds: 3600
  # Optional: Validate free-text answers with LLM before proceeding
  enable_llm_answer_validation: false
  answer_validation:
    default_min_length: 1
  # Optional: Let LLM rewrite prompts (off by default for predictability)
  enable_llm_prompt_rewrite: false
```

See also: examples/gather_cli.py and examples/gather_simple.py for end-to-end demos. You can also wrap GatherAgent behind a small REST API for chatbot UIs (start/reply/finish/abort pattern).

### API Agent
- Comprehensive HTTP/REST API integration
- Multiple authentication methods (Bearer, API Key, Basic, OAuth2)
- Pre-fetch authentication with automatic token refresh
- Built-in retry logic with exponential backoff
- Security features (domain filtering, SSL verification)
- Support for all HTTP methods (GET, POST, PUT, DELETE, etc.)

#### API Agent Configuration

**Timeout Settings:**

The API Agent supports configurable timeout settings for different use cases:

```bash
# Environment variable configuration
export AMBIVO_AGENTS_API_AGENT_TIMEOUT_SECONDS=46  # Custom timeout in seconds

# Or in agent_config.yaml
api_agent:
  timeout_seconds: 46                    # Request timeout
  max_safe_timeout: 8                    # Requests above this use Docker for safety
  force_docker_above_timeout: true       # Enable Docker for long-running requests
```

**Localhost and Domain Access:**

For testing with local services or specific domain restrictions:

```bash
# Allow localhost access (disabled by default for security)
export AMBIVO_AGENTS_API_AGENT_ALLOWED_DOMAINS="127.0.0.1,localhost,api.example.com"
export AMBIVO_AGENTS_API_AGENT_BLOCKED_DOMAINS=""  # Clear default blocks

# Or in agent_config.yaml
api_agent:
  allowed_domains:
    - "127.0.0.1"
    - "localhost" 
    - "api.example.com"
    - "*.trusted-domain.com"     # Wildcards supported
  blocked_domains: []            # Override default localhost blocks
  
  # Default security settings (recommended for production)
  # allowed_domains: null        # Allows all except blocked
  # blocked_domains:
  #   - "localhost"
  #   - "127.0.0.1"
  #   - "0.0.0.0"
  #   - "169.254.169.254"        # AWS metadata service
```

**Usage Examples:**

```python
from ambivo_agents import APIAgent

# Test with local transcription service
async def test_local_api():
    agent = APIAgent.create_simple(user_id="tester")
    
    # Natural language API call
    response = await agent.chat("""
    Make a POST request to http://127.0.0.1:8002/kh/transcribe with:
    - Authorization: Bearer your-jwt-token
    - Content-Type: application/json  
    - Body: {"s3_url": "https://your-bucket.s3.amazonaws.com/audio.wav"}
    """)
    
    await agent.cleanup_session()

# Direct API request with custom timeout
async def direct_api_call():
    from ambivo_agents.agents.api_agent import APIRequest, HTTPMethod
    
    agent = APIAgent.create_simple(user_id="api_user")
    
    request = APIRequest(
        url="http://127.0.0.1:8002/kh/transcribe",
        method=HTTPMethod.POST,
        headers={
            "Authorization": "Bearer your-jwt-token",
            "Content-Type": "application/json"
        },
        json_data={"s3_url": "https://your-bucket.s3.amazonaws.com/audio.wav"},
        timeout=46  # Custom timeout in seconds
    )
    
    response = await agent.make_api_request(request)
    print(f"Status: {response.status_code}")
    print(f"Duration: {response.duration_ms}ms")
    
    await agent.cleanup_session()
```

**Security Notes:**
- Localhost access is blocked by default for security
- Always use `allowed_domains` in production to restrict API access
- Set appropriate timeouts to prevent long-running requests
- Consider using `max_safe_timeout` for requests that might take longer

## Workflow System

The workflow system enables multi-agent orchestration with sequential and parallel execution patterns:

### Basic Workflow Usage

```python
from ambivo_agents.core.workflow import WorkflowBuilder, WorkflowPatterns
from ambivo_agents import ModeratorAgent

async def workflow_example():
    # Create moderator with agents
    moderator, context = ModeratorAgent.create(
        user_id="workflow_user",
        enabled_agents=['web_search', 'web_scraper', 'knowledge_base']
    )
    
    # Create search -> scrape -> ingest workflow
    workflow = WorkflowPatterns.create_search_scrape_ingest_workflow(
        moderator.specialized_agents['web_search'],
        moderator.specialized_agents['web_scraper'], 
        moderator.specialized_agents['knowledge_base']
    )
    
    # Execute workflow
    result = await workflow.execute(
        "Research renewable energy trends and store in knowledge base",
        context.to_execution_context()
    )
    
    if result.success:
        print(f"Workflow completed in {result.execution_time:.2f}s")
        print(f"Nodes executed: {result.nodes_executed}")
    
    await moderator.cleanup_session()
```

### Advanced Workflow Features

```python
from ambivo_agents.core.enhanced_workflow import (
    AdvancedWorkflowBuilder, EnhancedModeratorAgent
)

async def advanced_workflow():
    # Create enhanced moderator
    base_moderator, context = ModeratorAgent.create(user_id="advanced_user")
    enhanced_moderator = EnhancedModeratorAgent(base_moderator)
    
    # Natural language workflow triggers
    response1 = await enhanced_moderator.process_message_with_workflows(
        "I need agents to reach consensus on climate solutions"
    )
    
    response2 = await enhanced_moderator.process_message_with_workflows(
        "Create a debate between agents about AI ethics"
    )
    
    # Check workflow status
    status = await enhanced_moderator.get_workflow_status()
    print(f"Available workflows: {status['advanced_workflows']['registered']}")
```

### Workflow Patterns

- **Sequential Workflows**: Execute agents in order, passing results between them
- **Parallel Workflows**: Execute multiple agents simultaneously
- **Consensus Workflows**: Agents collaborate to reach agreement
- **Debate Workflows**: Structured multi-agent discussions
- **Error Recovery**: Automatic fallback to backup agents
- **Map-Reduce**: Parallel processing with result aggregation

## System Messages

System messages control agent behavior and responses. Each agent supports custom system prompts:

### Default System Messages

```python
# Agents come with role-specific system messages
assistant_agent = AssistantAgent.create_simple(user_id="user")
# Default: "You are a helpful AI assistant. Provide accurate, thoughtful responses..."

code_agent = CodeExecutorAgent.create_simple(user_id="user") 
# Default: "You are a code execution specialist. Write clean, well-commented code..."
```

### Custom System Messages

```python
from ambivo_agents import AssistantAgent

# Create agent with custom system message
custom_system = """You are a technical documentation specialist. 
Always provide detailed explanations with code examples. 
Use professional terminology and structured responses."""

agent, context = AssistantAgent.create(
    user_id="doc_specialist",
    system_message=custom_system
)

response = await agent.chat("Explain REST API design principles")
```

### Moderator System Messages

```python
from ambivo_agents import ModeratorAgent

# Custom moderator behavior
moderator_system = """You are a project management assistant.
Route technical queries to appropriate agents and provide 
executive summaries of complex multi-agent interactions."""

moderator, context = ModeratorAgent.create(
    user_id="pm_user",
    system_message=moderator_system
)
```

### System Message Features

- **Context Integration**: System messages work with conversation history
- **Agent-Specific**: Each agent type has optimized default prompts
- **Workflow Aware**: System messages adapt to workflow contexts
- **Provider Compatibility**: Works with all LLM providers (OpenAI, Anthropic, Bedrock)

## Prerequisites

### Required
- **Python 3.11+**
- **Docker** (for code execution, media processing, YouTube downloads)
- **Redis** (Cloud Redis recommended)

### API Keys (Optional - based on enabled features)
- **OpenAI API Key** (for GPT models)
- **Anthropic API Key** (for Claude models)
- **AWS Credentials** (for Bedrock models)
- **Brave Search API Key** (for web search)
- **AVES API Key** (for web search)
- **ScraperAPI/Proxy credentials** (for web scraping)
- **Qdrant Cloud API Key** (for Knowledge Base operations)
- **Redis Cloud credentials** (for memory management)

## Installation

### 1. Install Dependencies

**Core Installation (without database support):**
```bash
pip install -r requirements.txt
```

**With Optional Database Support:**
```bash
# Install with database capabilities (MongoDB, MySQL, PostgreSQL)
pip install ambivo-agents[database]

# Or install all optional features including database support
pip install ambivo-agents[all]
```

The database agents are optional and require additional dependencies:
- **MongoDB**: `pymongo>=4.0.0`
- **MySQL**: `mysql-connector-python>=8.0.0`
- **PostgreSQL**: `psycopg2-binary>=2.9.0`

### 2. Setup Docker Images
```bash
docker pull sgosain/amb-ubuntu-python-public-pod
```

### 3. Setup Redis

**Recommended: Cloud Redis**
```yaml
# In agent_config.yaml
redis:
  host: "your-redis-cloud-endpoint.redis.cloud"
  port: 6379
  password: "your-redis-password"
```

**Alternative: Local Redis**
```bash
# Using Docker
docker run -d --name redis -p 6379:6379 redis:latest
```

## Configuration

Create `agent_config.yaml` in your project root:

```yaml
# Redis Configuration (Required)
redis:
  host: "your-redis-cloud-endpoint.redis.cloud"
  port: 6379
  db: 0
  password: "your-redis-password"

# LLM Configuration (Required - at least one provider)
llm:
  preferred_provider: "openai"
  temperature: 0.7
  openai_api_key: "your-openai-key"
  anthropic_api_key: "your-anthropic-key"
  aws_access_key_id: "your-aws-key"
  aws_secret_access_key: "your-aws-secret"
  aws_region: "us-east-1"

# Agent Capabilities
agent_capabilities:
  enable_knowledge_base: true
  enable_web_search: true
  enable_code_execution: true
  enable_file_processing: true
  enable_web_ingestion: true
  enable_api_calls: true
  enable_web_scraping: true
  enable_proxy_mode: true
  enable_media_editor: true
  enable_youtube_download: true
  enable_analytics: true

# ModeratorAgent default agents
moderator:
  default_enabled_agents:
    - knowledge_base
    - web_search
    - assistant
    - media_editor
    - youtube_download
    - code_executor
    - web_scraper
    - analytics

# Service-specific configurations
web_search:
  brave_api_key: "your-brave-api-key"
  avesapi_api_key: "your-aves-api-key"

knowledge_base:
  qdrant_url: "https://your-cluster.qdrant.tech"
  qdrant_api_key: "your-qdrant-api-key"
  chunk_size: 1024
  chunk_overlap: 20
  similarity_top_k: 5

youtube_download:
  docker_image: "sgosain/amb-ubuntu-python-public-pod"
  download_dir: "./youtube_downloads"
  timeout: 600
  memory_limit: "1g"
  default_audio_only: true

analytics:
  docker_image: "sgosain/amb-ubuntu-python-public-pod"
  timeout: 300
  memory_limit: "1g"
  enable_url_ingestion: true
  max_file_size_mb: 100

docker:
  timeout: 60
  memory_limit: "512m"
  images: ["sgosain/amb-ubuntu-python-public-pod"]
```

## Configuration Methods

The library supports two configuration methods:

### 1. Environment Variables (Recommended for Production)

**Quick Start with Environment Variables:**

```bash
# Download and edit the full template
curl -o set_env.sh https://github.com/ambivo-corp/ambivo-agents/raw/main/set_env_template.sh
chmod +x set_env.sh

# Edit the template with your credentials, then source it
source set_env.sh
```

**Replace ALL placeholder values** with your actual credentials:
- Redis connection details
- LLM API keys (OpenAI/Anthropic)
- Web Search API keys (Brave/AVES)
- Knowledge Base credentials (Qdrant)
- Web Scraping proxy (ScraperAPI)

**Minimal Environment Setup:**
```bash
# Required - Redis
export AMBIVO_AGENTS_REDIS_HOST="your-redis-host.redis.cloud"
export AMBIVO_AGENTS_REDIS_PORT="6379"
export AMBIVO_AGENTS_REDIS_PASSWORD="your-redis-password"

# Required - At least one LLM provider
export AMBIVO_AGENTS_OPENAI_API_KEY="sk-your-openai-key"

# Optional - Enable specific agents
export AMBIVO_AGENTS_ENABLE_YOUTUBE_DOWNLOAD="true"
export AMBIVO_AGENTS_ENABLE_WEB_SEARCH="true"
export AMBIVO_AGENTS_ENABLE_ANALYTICS="true"
export AMBIVO_AGENTS_MODERATOR_ENABLED_AGENTS="youtube_download,web_search,analytics,assistant"

# Run your application
python your_app.py
```

### 2. YAML Configuration (Traditional)

**Use the full YAML template:**

```bash
# Download and edit the full template
curl -o agent_config_sample.yaml https://github.com/ambivo-corp/ambivo-agents/raw/main/agent_config_sample.yaml

# Copy to your config file and edit with your credentials
cp agent_config_sample.yaml agent_config.yaml
```

**Replace ALL placeholder values** with your actual credentials, then create `agent_config.yaml` in your project root.

### Docker Deployment with Environment Variables

```yaml
# docker-compose.yml
version: '3.8'
services:
  ambivo-app:
    image: your-app:latest
    environment:
      - AMBIVO_AGENTS_REDIS_HOST=redis
      - AMBIVO_AGENTS_REDIS_PORT=6379
      - AMBIVO_AGENTS_OPENAI_API_KEY=${OPENAI_API_KEY}
      - AMBIVO_AGENTS_ENABLE_YOUTUBE_DOWNLOAD=true
      - AMBIVO_AGENTS_ENABLE_ANALYTICS=true
    volumes:
      - ./downloads:/app/downloads
      - /var/run/docker.sock:/var/run/docker.sock
    depends_on:
      - redis
  
  redis:
    image: redis:latest
    ports:
      - "6379:6379"
```

**Note:** Environment variables take precedence over YAML configuration. The `agent_config.yaml` file is optional when using environment variables.

## Project Structure

```
ambivo_agents/
├── agents/          # Agent implementations
│   ├── analytics.py     # Analytics Agent (DuckDB data analysis)
│   ├── api_agent.py     # API Agent (HTTP/REST integration)
│   ├── assistant.py     # Assistant Agent (general conversation)
│   ├── code_executor.py # Code Executor Agent (Docker-based execution)
│   ├── database_agent.py # Database Agent (MongoDB, MySQL, PostgreSQL)
│   ├── knowledge_base.py # Knowledge Base Agent (Qdrant vector search)
│   ├── media_editor.py  # Media Editor Agent (FFmpeg processing)
│   ├── moderator.py     # ModeratorAgent (main orchestrator)
│   ├── web_scraper.py   # Web Scraper Agent (Playwright-based)
│   ├── web_search.py    # Web Search Agent (Brave/AVES search)
│   └── youtube_download.py # YouTube Download Agent (pytubefix)
├── config/          # Configuration management
├── core/            # Core functionality
│   ├── base.py
│   ├── llm.py
│   ├── memory.py
│   ├── workflow.py       # Basic workflow system
│   └── enhanced_workflow.py  # Advanced workflow patterns
├── executors/       # Execution environments
├── services/        # Service layer
├── __init__.py      # Package initialization
└── cli.py          # Command line interface
```

## Usage Examples

### ModeratorAgent with Auto-Routing

```python
from ambivo_agents import ModeratorAgent
import asyncio

async def basic_moderator():
    moderator, context = ModeratorAgent.create(user_id="demo_user")
    
    # Auto-routing examples
    examples = [
        "Download audio from https://youtube.com/watch?v=example",
        "Search for latest artificial intelligence news",  
        "Load data from sales.csv and analyze trends",
        "Extract audio from video.mp4 as high quality MP3",
        "What is machine learning and how does it work?",
    ]
    
    for query in examples:
        response = await moderator.chat(query)
        print(f"Response: {response[:100]}...")
    
    await moderator.cleanup_session()

asyncio.run(basic_moderator())
```

### Context-Aware Conversations

```python
async def context_conversation():
    moderator, context = ModeratorAgent.create(user_id="context_demo")
    
    # Initial request  
    response1 = await moderator.chat("Download audio from https://youtube.com/watch?v=example")
    
    # Follow-up using context
    response2 = await moderator.chat("Actually, download the video instead of just audio")
    
    # Another follow-up
    response3 = await moderator.chat("Get information about that video")
    
    await moderator.cleanup_session()
```

### YouTube Downloads

```python
from ambivo_agents import YouTubeDownloadAgent

async def download_youtube():
    agent, context = YouTubeDownloadAgent.create(user_id="media_user")
    
    # Download audio
    result = await agent._download_youtube_audio(
        "https://youtube.com/watch?v=example"
    )
    
    if result['success']:
        print(f"Audio downloaded: {result['filename']}")
        print(f"Path: {result['file_path']}")
    
    await agent.cleanup_session()
```

### Database Operations

```python
from ambivo_agents import DatabaseAgent

async def database_demo():
    agent, context = DatabaseAgent.create(user_id="db_user")
    
    # Connect to MySQL database
    response = await agent.chat("Connect to MySQL database at localhost:3306, database: mydb, username: user, password: pass")
    print(f"Connection: {response}")
    
    # Explore database schema
    schema = await agent.chat("show me the database schema")
    print(f"Schema: {schema}")
    
    # Natural language queries
    result = await agent.chat("show me all users from the users table")
    print(f"Users: {result}")
    
    # Query with analytics handoff
    analytics_result = await agent.chat("get sales data and create visualizations")
    print(f"Analytics: {analytics_result}")
    
    await agent.cleanup_session()

# Database to Analytics Workflow
async def database_analytics_workflow():
    from ambivo_agents import ModeratorAgent
    
    # Use ModeratorAgent for automatic routing
    moderator, context = ModeratorAgent.create(
        user_id="workflow_user",
        enabled_agents=["database_agent", "analytics", "assistant"]
    )
    
    # Connect and query database
    await moderator.chat("Connect to MySQL localhost:3306 database mydb user admin password secret")
    
    # Query data with automatic analytics handoff
    response = await moderator.chat("Get sales data from orders table and create charts showing trends")
    print(response)
    
    await moderator.cleanup_session()
```

### File Reading and Database Ingestion

All agents have built-in file reading capabilities for JSON, CSV, XML, and YAML files. Database insertion requires the optional database package.

```python
from ambivo_agents import AssistantAgent

async def read_file_and_insert_to_database():
    """Reads a JSON file and attempts database insertion with graceful fallback"""
    
    # Step 1: Read and parse file (always available)
    agent = AssistantAgent.create_simple(user_id="file_user")
    
    result = await agent.read_and_parse_file("./data/users.json")
    if not result['success']:
        print(f"❌ Failed to read file: {result.get('error', 'Unknown error')}")
        await agent.cleanup_session()
        return
    
    json_data = result['parse_result']['data']
    print(f"✅ Successfully loaded {len(json_data)} records from users.json")
    
    # Step 2: Attempt database insertion
    try:
        from ambivo_agents import DatabaseAgent
        
        # DatabaseAgent is available - proceed with insertion
        db_agent = DatabaseAgent.create_simple(user_id="db_user")
        
        # Connect to MongoDB
        await db_agent.chat("connect to mongodb://localhost:27017 database myapp")
        
        # Insert the data
        response = await db_agent.chat(f"insert this data into users collection: {json_data}")
        print(f"✅ Successfully inserted data into MongoDB: {response}")
        
        await db_agent.cleanup_session()
        
    except ImportError:
        # DatabaseAgent not available - provide polite warning and alternatives
        print("\n⚠️  Database insertion not available")
        print("💡 To enable database features, install with: pip install ambivo-agents[database]")
        print("\n📁 Available alternatives:")
        print("   • File successfully read and parsed")
        print("   • Data can be transformed to other formats")
        
        # Show what we can still do
        csv_result = await agent.convert_json_to_csv(json_data)
        if csv_result['success']:
            print("   • ✅ Converted to CSV format (available for export)")
    
    await agent.cleanup_session()

# Alternative: Natural language approach with graceful handling
async def natural_language_file_ingestion():
    """Uses natural language commands with automatic fallback"""
    
    try:
        from ambivo_agents import DatabaseAgent
        agent = DatabaseAgent.create_simple(user_id="user")
        
        # Full database workflow available
        await agent.chat("connect to mongodb://localhost:27017 database myapp")
        response = await agent.chat("read users.json file and insert all records into users collection")
        print(f"✅ Database ingestion completed: {response}")
        
        await agent.cleanup_session()
        
    except ImportError:
        # Fallback to file reading only
        from ambivo_agents import AssistantAgent
        agent = AssistantAgent.create_simple(user_id="user")
        
        print("⚠️  DatabaseAgent not installed. Reading file only...")
        response = await agent.chat("read and analyze the users.json file structure")
        print(f"📁 File analysis: {response}")
        print("💡 Install database support with: pip install ambivo-agents[database]")
        
        await agent.cleanup_session()
```

### Data Analytics

```python
from ambivo_agents import AnalyticsAgent

async def analytics_demo():
    agent, context = AnalyticsAgent.create(user_id="analyst_user")
    
    # Load and analyze CSV data
    response = await agent.chat("load data from sales.csv and analyze it")
    print(f"Analysis: {response}")
    
    # Schema exploration
    schema = await agent.chat("show me the schema of the current dataset")
    print(f"Schema: {schema}")
    
    # Natural language queries
    top_sales = await agent.chat("what are the top 5 products by sales?")
    print(f"Top Sales: {top_sales}")
    
    # SQL queries
    sql_result = await agent.chat("SELECT region, SUM(sales) as total FROM data GROUP BY region")
    print(f"SQL Result: {sql_result}")
    
    # Visualizations
    chart = await agent.chat("create a bar chart showing sales by region")
    print(f"Chart: {chart}")
    
    await agent.cleanup_session()

# Context Preservation Example
async def context_preservation_demo():
    """Demonstrates context/state preservation between chat messages"""
    agent = AnalyticsAgent.create_simple(user_id="user123")
    
    try:
        # Load data once
        await agent.chat("load data from transactions.xlsx and analyze it")
        
        # Multiple queries without reload - uses cached context
        schema = await agent.chat("show schema")          # ✅ Uses cached data
        top_items = await agent.chat("what are the top 5 amounts?")  # ✅ Uses cached data
        summary = await agent.chat("summary statistics")   # ✅ Uses cached data
        counts = await agent.chat("count by category")     # ✅ Uses cached data
        
        print("All queries executed using cached dataset - no reload needed!")
        
    finally:
        await agent.cleanup_session()  # Clean up resources
```

### Knowledge Base Operations

```python
from ambivo_agents import KnowledgeBaseAgent

async def knowledge_base_demo():
    agent, context = KnowledgeBaseAgent.create(user_id="kb_user")
    
    # Ingest document
    result = await agent._ingest_document(
        kb_name="company_kb",
        doc_path="/path/to/document.pdf",
        custom_meta={"department": "HR", "type": "policy"}
    )
    
    if result['success']:
        # Query the knowledge base
        answer = await agent._query_knowledge_base(
            kb_name="company_kb",
            query="What is the remote work policy?"
        )
        
        if answer['success']:
            print(f"Answer: {answer['answer']}")
    
    await agent.cleanup_session()
```

### API Integration

```python
from ambivo_agents import APIAgent
from ambivo_agents.agents.api_agent import APIRequest, AuthConfig, HTTPMethod, AuthType

async def api_integration_demo():
    agent, context = APIAgent.create(user_id="api_user")
    
    # Basic GET request
    request = APIRequest(
        url="https://jsonplaceholder.typicode.com/posts/1",
        method=HTTPMethod.GET
    )
    
    response = await agent.make_api_request(request)
    if not response.error:
        print(f"Status: {response.status_code}")
        print(f"Data: {response.json_data}")
    
    # POST with authentication
    auth_config = AuthConfig(
        auth_type=AuthType.BEARER,
        token="your-api-token"
    )
    
    post_request = APIRequest(
        url="https://api.example.com/data",
        method=HTTPMethod.POST,
        auth_config=auth_config,
        json_data={"name": "test", "value": "123"}
    )
    
    post_response = await agent.make_api_request(post_request)
    
    # Google OAuth2 with pre-fetch
    google_auth = AuthConfig(
        auth_type=AuthType.BEARER,
        pre_auth_url="https://www.googleapis.com/oauth2/v4/token",
        pre_auth_method=HTTPMethod.POST,
        pre_auth_payload={
            "client_id": "your-client-id",
            "client_secret": "your-secret",
            "refresh_token": "your-refresh-token",
            "grant_type": "refresh_token"
        },
        token_path="access_token"
    )
    
    sheets_request = APIRequest(
        url="https://sheets.googleapis.com/v4/spreadsheets/sheet-id/values/A1:B10",
        method=HTTPMethod.GET,
        auth_config=google_auth
    )
    
    # APIAgent will automatically fetch access_token first, then make the request
    sheets_response = await agent.make_api_request(sheets_request)
    
    await agent.cleanup_session()

# Conversational API usage
async def conversational_api():
    agent = APIAgent.create_simple(user_id="chat_user")
    
    # Use natural language for API requests
    response = await agent.chat("GET https://jsonplaceholder.typicode.com/users/1")
    print(response)
    
    response = await agent.chat(
        "POST https://api.example.com/data with headers: {\"Authorization\": \"Bearer token\"} "
        "and data: {\"message\": \"Hello API\"}"
    )
    print(response)
    
    await agent.cleanup_session()
```

### Context Manager Pattern

```python
from ambivo_agents import ModeratorAgent, AgentSession
import asyncio

async def main():
    # Auto-cleanup with context manager
    async with AgentSession(ModeratorAgent, user_id="sarah") as moderator:
        response = await moderator.chat("Download audio from https://youtube.com/watch?v=example")
        print(response)
    # Moderator automatically cleaned up

asyncio.run(main())
```

### Workflow Examples

```python
from ambivo_agents.core.workflow import WorkflowBuilder

async def custom_workflow():
    # Create agents
    moderator, context = ModeratorAgent.create(user_id="workflow_demo")
    
    # Build custom workflow
    builder = WorkflowBuilder()
    builder.add_agent(moderator.specialized_agents['web_search'], "search")
    builder.add_agent(moderator.specialized_agents['assistant'], "analyze")
    builder.add_edge("search", "analyze")
    builder.set_start_node("search")
    builder.set_end_node("analyze")
    
    workflow = builder.build()
    
    # Execute workflow
    result = await workflow.execute(
        "Research AI safety and provide analysis",
        context.to_execution_context()
    )
    
    print(f"Workflow result: {result.success}")
    await moderator.cleanup_session()
```

## Streaming System

The library features a modern **StreamChunk** system that provides structured, type-safe streaming responses with rich metadata.

### StreamChunk Overview

All agents now return `StreamChunk` objects instead of raw strings, enabling:
- **Type-safe content classification** with `StreamSubType` enum
- **Rich metadata** for debugging, analytics, and context
- **Programmatic filtering** without string parsing
- **Consistent interface** across all agents

### StreamSubType Categories

```python
from ambivo_agents.core.base import StreamSubType

# Available sub-types:
StreamSubType.CONTENT    # Actual response content from LLMs
StreamSubType.STATUS     # Progress updates, thinking, interim info  
StreamSubType.RESULT     # Search results, processing outputs
StreamSubType.ERROR      # Error messages and failures
StreamSubType.METADATA   # Additional context and metadata
```

### Basic Streaming Usage

```python
from ambivo_agents import ModeratorAgent
from ambivo_agents.core.base import StreamSubType

async def streaming_example():
    moderator, context = ModeratorAgent.create(user_id="stream_user")
    
    # Stream with filtering
    print("🤖 Assistant: ", end='', flush=True)
    
    async for chunk in moderator.chat_stream("Search for Python tutorials"):
        # Filter by content type
        if chunk.sub_type == StreamSubType.CONTENT:
            print(chunk.text, end='', flush=True)
        elif chunk.sub_type == StreamSubType.STATUS:
            print(f"\n[{chunk.text.strip()}]", end='', flush=True)
        elif chunk.sub_type == StreamSubType.ERROR:
            print(f"\n[ERROR: {chunk.text}]", end='', flush=True)
    
    await moderator.cleanup_session()
```

### Advanced Streaming with Metadata

```python
async def advanced_streaming():
    moderator, context = ModeratorAgent.create(user_id="advanced_user")
    
    # Collect and analyze stream
    content_chunks = []
    status_chunks = []
    result_chunks = []
    
    async for chunk in moderator.chat_stream("Download audio from YouTube"):
        # Categorize by type
        if chunk.sub_type == StreamSubType.CONTENT:
            content_chunks.append(chunk)
        elif chunk.sub_type == StreamSubType.STATUS:
            status_chunks.append(chunk)
        elif chunk.sub_type == StreamSubType.RESULT:
            result_chunks.append(chunk)
        
        # Access metadata
        agent_info = chunk.metadata.get('agent')
        operation = chunk.metadata.get('operation')
        phase = chunk.metadata.get('phase')
        
        print(f"[{chunk.sub_type.value}] {chunk.text[:50]}...")
        if agent_info:
            print(f"  Agent: {agent_info}")
        if operation:
            print(f"  Operation: {operation}")
    
    # Analysis
    print(f"\nStream Analysis:")
    print(f"Content chunks: {len(content_chunks)}")
    print(f"Status updates: {len(status_chunks)}")
    print(f"Results: {len(result_chunks)}")
    
    await moderator.cleanup_session()
```

### Streaming in Web APIs

```python
from fastapi import FastAPI
from fastapi.responses import StreamingResponse
import json

app = FastAPI()

@app.post("/chat/stream")
async def chat_stream(request: ChatRequest):
    moderator, context = ModeratorAgent.create(user_id=request.user_id)
    
    async def generate_stream():
        async for chunk in moderator.chat_stream(request.message):
            # Convert StreamChunk to JSON
            chunk_data = {
                'type': 'chunk',
                'sub_type': chunk.sub_type.value,
                'text': chunk.text,
                'metadata': chunk.metadata,
                'timestamp': chunk.timestamp.isoformat()
            }
            yield f"data: {json.dumps(chunk_data)}\n\n"
        
        yield "data: {\"type\": \"done\"}\n\n"
    
    return StreamingResponse(generate_stream(), media_type="text/stream")
```

### Real-time UI Integration

```javascript
// Frontend streaming handler
const eventSource = new EventSource('/chat/stream');

eventSource.onmessage = function(event) {
    const data = JSON.parse(event.data);
    
    if (data.type === 'chunk') {
        switch(data.sub_type) {
            case 'content':
                // Display main response content
                appendToChat(data.text);
                break;
            case 'status':
                // Show progress indicator
                updateStatus(data.text);
                break;
            case 'result':
                // Display search results/outputs
                addResult(data.text, data.metadata);
                break;
            case 'error':
                // Handle errors
                showError(data.text);
                break;
        }
    }
};
```

### StreamChunk Benefits

**For Developers:**
- **Type Safety** - No string parsing for content classification
- **Rich Context** - Access agent info, operation details, timing
- **Easy Filtering** - Filter streams by content type programmatically
- **Debugging** - Detailed metadata for troubleshooting

**For Applications:**
- **Smart UIs** - Show different content types appropriately
- **Progress Tracking** - Real-time operation status updates
- **Error Handling** - Structured error information
- **Analytics** - Performance metrics and usage tracking


## Session Management

### Understanding Session vs Conversation IDs

The library uses two identifiers for context management:

- **session_id**: Represents a broader user session or application context
- **conversation_id**: Represents a specific conversation thread within a session

```python
# Single conversation (most common)
moderator, context = ModeratorAgent.create(
    user_id="john",
    session_id="user_john_main", 
    conversation_id="user_john_main"  # Same as session_id
)

# Multiple conversations per session
session_key = "user_john_tenant_abc"

# Conversation 1: Data Analysis
moderator1, context1 = ModeratorAgent.create(
    user_id="john",
    session_id=session_key,
    conversation_id="john_data_analysis_conv"
)

# Conversation 2: YouTube Downloads  
moderator2, context2 = ModeratorAgent.create(
    user_id="john", 
    session_id=session_key,
    conversation_id="john_youtube_downloads_conv"
)
```

## Web API Integration

```python
from ambivo_agents import ModeratorAgent
import asyncio
import time

class ChatAPI:
    def __init__(self):
        self.active_moderators = {}
    
    async def chat_endpoint(self, request_data):
        user_message = request_data.get('message', '')
        user_id = request_data.get('user_id', f"user_{uuid.uuid4()}")
        session_id = request_data.get('session_id', f"session_{user_id}_{int(time.time())}")
        
        try:
            if session_id not in self.active_moderators:
                moderator, context = ModeratorAgent.create(
                    user_id=user_id,
                    session_id=session_id
                )
                self.active_moderators[session_id] = moderator
            else:
                moderator = self.active_moderators[session_id]
            
            response_content = await moderator.chat(user_message)
            
            return {
                'success': True,
                'response': response_content,
                'session_id': session_id,
                'timestamp': time.time()
            }
            
        except Exception as e:
            return {
                'success': False,
                'error': str(e),
                'timestamp': time.time()
            }
    
    async def cleanup_session(self, session_id):
        if session_id in self.active_moderators:
            await self.active_moderators[session_id].cleanup_session()
            del self.active_moderators[session_id]
```

## Command Line Interface

```bash
# Interactive mode with auto-routing
ambivo-agents

# Single queries
ambivo-agents -q "Download audio from https://youtube.com/watch?v=example"
ambivo-agents -q "Search for latest AI trends"
ambivo-agents -q "Load data from sales.csv and show top products"
ambivo-agents -q "Extract audio from video.mp4"

# Check agent status
ambivo-agents status

# Test all agents
ambivo-agents --test

# Debug mode
ambivo-agents --debug -q "test query"
```

## Architecture

### ModeratorAgent Architecture

The **ModeratorAgent** acts as an intelligent orchestrator:

```
[User Query] 
     ↓
[ModeratorAgent] ← Analyzes intent and context
     ↓
[Intent Analysis] ← Uses LLM + patterns + keywords
     ↓
[Route Selection] ← Chooses best agent(s)
     ↓
[Specialized Agent] ← YouTubeAgent, SearchAgent, etc.
     ↓
[Response] ← Combined and contextualized
     ↓
[User]
```

### Workflow Architecture

```
[WorkflowBuilder] → [Workflow Definition]
        ↓                    ↓
[Workflow Executor] → [Sequential/Parallel Execution]
        ↓                    ↓
[State Management] → [Persistent Checkpoints]
        ↓                    ↓
[Result Aggregation] → [Final Response]
```

### Memory System
- Redis-based persistence with compression and caching
- Built-in conversation history for every agent
- Session-aware context with automatic cleanup
- Multi-session support with isolation

### LLM Provider Management
- Automatic failover between OpenAI, Anthropic, AWS Bedrock
- Rate limiting and error handling
- Provider rotation based on availability and performance

## Docker Setup

### Consolidated Docker File Sharing System

Ambivo Agents uses a **consolidated Docker-shared directory structure** for all file operations across agents. This provides consistent, secure, and efficient file sharing between your host filesystem and Docker containers.

#### Consolidated Directory Structure

All Docker-based agents (AnalyticsAgent, MediaEditorAgent, CodeExecutorAgent, WebScraperAgent, APIAgent) use the same base structure:

```
Your Project Directory/
└── docker_shared/                           # Consolidated base directory
    ├── input/                              # Read-only input files
    │   ├── analytics/     →  /docker_shared/input/analytics     (AnalyticsAgent)
    │   ├── media/         →  /docker_shared/input/media         (MediaEditorAgent)
    │   ├── code/          →  /docker_shared/input/code          (CodeExecutorAgent)
    │   └── scraper/       →  /docker_shared/input/scraper       (WebScraperAgent)
    ├── output/                             # Read-write output files
    │   ├── analytics/     →  /docker_shared/output/analytics    (Analysis results)
    │   ├── media/         →  /docker_shared/output/media        (Processed media)
    │   ├── code/          →  /docker_shared/output/code         (Code execution results)
    │   └── scraper/       →  /docker_shared/output/scraper      (Scraped data)
    ├── temp/                               # Read-write temporary workspace
    │   ├── analytics/     →  /docker_shared/temp/analytics      (Analytics temp files)
    │   ├── media/         →  /docker_shared/temp/media          (Media processing temp)
    │   └── code/          →  /docker_shared/temp/code           (Code execution temp)
    ├── handoff/                            # Read-write inter-agent file sharing
    │   ├── database/      →  /docker_shared/handoff/database    (Database exports)
    │   ├── analytics/     →  /docker_shared/handoff/analytics   (Analytics results)
    │   └── media/         →  /docker_shared/handoff/media       (Media for processing)
    └── work/              →  /docker_shared/work                # General workspace
```

#### How the System Works

When you request operations like "convert data.csv to xlsx" or "process video.mp4":

1. **File Detection**: System detects file paths in your request
2. **Directory Setup**: Auto-creates agent-specific subdirectories in `./docker_shared/`
3. **File Copying**: Copies your files to appropriate input directories
4. **Docker Execution**: Runs containers with consistent `/docker_shared/` mount points
5. **Result Retrieval**: Outputs appear in agent-specific output directories

#### Inter-Agent Workflows

The consolidated structure enables seamless workflows between agents:

**Database → Analytics Workflow:**
```
1. DatabaseAgent exports data     →  ./docker_shared/handoff/database/export.csv
2. AnalyticsAgent automatically  →  reads from /docker_shared/handoff/database/
3. AnalyticsAgent processes data  →  outputs to /docker_shared/output/analytics/
4. Results available at           →  ./docker_shared/output/analytics/results.json
```

#### Agent Handoff Mechanism

**Output vs Handoff Directory Logic:**

The system uses two distinct destination directories based on the agent's role in the workflow:

- **`output/` directories**: For **final deliverables** - when an agent produces end results for user consumption
  - MediaEditorAgent image/video processing → `docker_shared/output/media/`
  - AnalyticsAgent charts and reports → `docker_shared/output/analytics/`
  - CodeExecutorAgent script results → `docker_shared/output/code/`
  
- **`handoff/` directories**: For **inter-agent communication** - when one agent needs to pass data to another agent
  - DatabaseAgent exports for AnalyticsAgent → `docker_shared/handoff/database/`
  - WebScraperAgent data for KnowledgeBaseAgent → `docker_shared/handoff/scraper/`
  - MediaEditorAgent processed files for further processing → `docker_shared/handoff/media/`

**Decision Logic:**
- **Terminal operations** (user-requested, final results) → `output/`
- **Workflow operations** (agent-to-agent data passing) → `handoff/`

The handoff system uses the `handoff_subdir` parameter to enable seamless file transfers between agents:

**DatabaseAgent → AnalyticsAgent Handoff:**
```python
# DatabaseAgent automatically exports to handoff directory
result = await db_agent.chat("export sales data for analytics", 
                            handoff_subdir="sales_analysis_2024")
# Creates: ./docker_shared/handoff/database/sales_analysis_2024/

# AnalyticsAgent automatically detects handoff files
analytics_result = await analytics_agent.chat("analyze sales data",
                                              handoff_subdir="sales_analysis_2024")
# Reads from: ./docker_shared/handoff/database/sales_analysis_2024/
```

**Handoff Directory Management:**
- **Automatic creation**: Subdirectories created based on `handoff_subdir` parameter
- **File naming**: `{agent_type}_{timestamp}_{operation}.{ext}`
- **Cleanup**: Handoff files older than 24 hours automatically removed
- **Thread-safe**: Multiple concurrent handoffs supported
- **Cross-platform**: Works consistently across Windows, macOS, and Linux

**Configuration in `agent_config.yaml`:**
```yaml
docker:
  container_mounts:
    handoff: "/docker_shared/handoff"
  
  agent_subdirs:
    database: ["handoff/database"]
    analytics: ["input/analytics", "output/analytics", "handoff/analytics"]
    media: ["input/media", "output/media", "handoff/media"]
```

**Enhanced Fallback (CSV→XLSX Conversion):**
```
1. User: "convert sales.csv to xlsx"
2. ModeratorAgent detects file operation need
3. Copies sales.csv               →  ./docker_shared/input/code/sales.csv
4. CodeExecutorAgent processes    →  from /docker_shared/input/code/sales.csv
5. Outputs converted file         →  to /docker_shared/output/code/sales.xlsx
6. User accesses result at        →  ./docker_shared/output/code/sales.xlsx
```

**Media Processing Workflow:**
```
1. User places video              →  ./docker_shared/input/media/input.mp4
2. MediaEditorAgent processes     →  from /docker_shared/input/media/input.mp4
3. Outputs processed file         →  to /docker_shared/output/media/output.mp3
4. User gets result from          →  ./docker_shared/output/media/output.mp3
```

#### Third-Party Developer Integration

For developers building custom agents:

```python
from ambivo_agents.core import get_shared_manager

# Get the consolidated shared manager
shared_manager = get_shared_manager()

# Prepare environment for your custom agent
input_path, output_path = shared_manager.prepare_agent_environment(
    agent="my_custom_agent",
    input_files=["./my_data.csv"]
)

# Get Docker volume configuration
volumes = shared_manager.get_docker_volumes()
# volumes = {
#     '/path/to/docker_shared/input': {'bind': '/docker_shared/input', 'mode': 'ro'},
#     '/path/to/docker_shared/output': {'bind': '/docker_shared/output', 'mode': 'rw'},
#     # ... other mounts
# }

# In your Docker container, access files at:
# - Input:   /docker_shared/input/my_custom_agent/
# - Output:  /docker_shared/output/my_custom_agent/
# - Temp:    /docker_shared/temp/my_custom_agent/
# - Handoff: /docker_shared/handoff/my_custom_agent/

# After processing, check results:
output_files = shared_manager.list_outputs("my_custom_agent")
latest_output = shared_manager.get_latest_output("my_custom_agent", ".xlsx")
```

#### Example Usage

```python
import asyncio
from ambivo_agents import ModeratorAgent

async def process_files_with_consolidated_structure():
    # Create moderator with auto-routing
    moderator, context = ModeratorAgent.create(user_id="file_processor")
    
    # File operations use consolidated Docker structure
    await moderator.chat("convert sales_data.csv to xlsx format")  # → ./docker_shared/output/code/
    await moderator.chat("extract audio from video.mp4 as MP3")     # → ./docker_shared/output/media/
    await moderator.chat("analyze customer_data.csv and chart")     # → ./docker_shared/output/analytics/
    
    # All results organized by agent type in docker_shared/output/
    await moderator.cleanup_session()

# Run the example
asyncio.run(process_files_with_consolidated_structure())
```

#### File Locations After Operations

```bash
# Directory structure after various operations
your-project/
├── sales_data.csv              # Your original files
├── video.mp4
├── customer_data.csv
└── docker_shared/              # Consolidated results
    └── output/
        ├── code/
        │   └── sales_data.xlsx         # CSV→XLSX conversion
        ├── media/
        │   └── video_audio.mp3         # Audio extraction
        └── analytics/
            ├── analysis_report.json    # Data analysis
            └── customer_charts.png     # Generated charts
```

#### Configuration

The consolidated structure is configured in `agent_config.yaml`:

```yaml
docker:
  shared_base_dir: "./docker_shared"     # Host base directory
  container_mounts:
    input: "/docker_shared/input"        # Read-only input
    output: "/docker_shared/output"      # Read-write output
    temp: "/docker_shared/temp"          # Read-write temp
    handoff: "/docker_shared/handoff"    # Read-write handoffs
    work: "/docker_shared/work"          # Read-write workspace
  agent_subdirs:
    analytics: ["input/analytics", "output/analytics", "temp/analytics", "handoff/analytics"]
    media: ["input/media", "output/media", "temp/media", "handoff/media"]
    code: ["input/code", "output/code", "temp/code", "handoff/code"]
    # ... other agents
```

#### Third-Party Developer Project Structure

When developers install `ambivo-agents` via `pip install ambivo-agents`, the Docker shared directory is created relative to their project root. Here's how the directory structure would look:

```
my-ai-project/                          # Third-party developer's project
├── main.py                             # Their application code
├── requirements.txt                    # Including ambivo-agents
├── agent_config.yaml                   # Their configuration file
├── data/                               # Their project data
│   ├── input_files.csv
│   └── documents.pdf
├── docker_shared/                      # Auto-created by ambivo-agents
│   ├── input/                          # Container read-only mounts
│   │   ├── analytics/                  # For data analysis tasks
│   │   │   └── uploaded_data.csv
│   │   ├── media/                      # For media processing
│   │   │   └── video_to_process.mp4
│   │   └── code/                       # For code execution
│   │       └── user_script.py
│   ├── output/                         # Container write-enabled results
│   │   ├── analytics/                  # Analysis results
│   │   │   ├── report.json
│   │   │   └── charts.png
│   │   ├── media/                      # Processed media
│   │   │   ├── audio_extracted.mp3
│   │   │   └── compressed_video.mp4
│   │   └── code/                       # Code execution results
│   │       └── execution_results.txt
│   ├── temp/                           # Temporary files during processing
│   │   ├── analytics/
│   │   ├── media/
│   │   └── code/
│   ├── handoff/                        # Cross-agent file sharing
│   │   ├── analytics/                  # Database → Analytics
│   │   ├── database/                   # Database exports
│   │   ├── media/                      # Media processing handoffs
│   │   └── scraper/                    # Web scraper results
│   └── work/                           # Container workspace
└── venv/                               # Their virtual environment
    └── lib/python3.x/site-packages/
        └── ambivo_agents/              # Installed package
```

**Environment Variable Configuration:**

Developers can customize the shared directory location:

```bash
# In their .env or environment
export AMBIVO_AGENTS_DOCKER_SHARED_BASE_DIR="/custom/path/shared"
```

**Example Usage in Developer's Code:**

```python
# my-ai-project/main.py
from ambivo_agents.agents.analytics import AnalyticsAgent
from ambivo_agents.agents.moderator import ModeratorAgent

# Create agents - they automatically use configured shared directory
moderator = ModeratorAgent.create_simple(user_id="developer123")

# Process data - files are managed in docker_shared/
response = await moderator.chat("analyze the sales data in my CSV file")

# The docker_shared/ directory is automatically created and managed
# Input files are accessible at docker_shared/input/analytics/
# Results appear in docker_shared/output/analytics/
```

**Benefits for Third-Party Developers:**

- **Isolated**: Each project gets its own `docker_shared/` directory
- **Portable**: Directory structure is relative to project root
- **Configurable**: Can be customized via environment variables
- **Auto-managed**: Created and organized automatically
- **Secure**: Container access is properly restricted

#### Security & Permissions

- **Input Security**: All input directories mounted read-only (`ro`)
- **Output Isolation**: Each agent has isolated output directories
- **Network Isolation**: Docker containers run with `network_disabled=True`
- **Memory Limits**: Configurable memory restrictions per agent
- **Auto-Cleanup**: Temporary files cleaned based on age (configurable)
- **Permission Control**: Directory permissions managed automatically

#### File Access Security Configuration

**Restricted Directories Protection:**

The system includes built-in protection against accessing sensitive system directories:

```yaml
# agent_config.yaml
security:
  file_access:
    restricted_directories:
      - "/etc"           # System configuration
      - "/root"          # Root user directory
      - "/var/log"       # System logs
      - "/proc"          # Process information
      - "/sys"           # System information
      - "/dev"           # Device files
      - "/boot"          # Boot files
      - "~/.ssh"         # SSH keys
      - "~/.aws"         # AWS credentials
      - "~/.config"      # User configuration
      - "/usr/bin"       # System binaries
      - "/usr/sbin"      # System admin binaries
```

**Environment Variable Configuration:**
```bash
# Alternative to YAML configuration
export AMBIVO_AGENTS_FILE_ACCESS_RESTRICTED_DIRS="/etc,/var/log,/sys,/proc,/dev"
```

**How Restricted Directories Work:**
- **Path Resolution**: Uses `Path.expanduser().resolve()` for proper path handling
- **Security by Default**: Common sensitive directories blocked by default
- **Symbolic Link Protection**: Resolves symbolic links to prevent bypass attempts
- **Cross-Platform**: Works on Windows, macOS, and Linux
- **Agent Coverage**: Protects both `BaseAgent.read_file()` and `DatabaseAgent.ingest_file_to_mongodb()`

**Example Usage:**
```python
from ambivo_agents import DatabaseAgent

# This will be blocked by default security settings
result = await db_agent.chat("ingest data from /etc/passwd")
# Returns: {"success": False, "error": "Access denied: File path '/etc/passwd' is in a restricted directory"}

# This works normally (assuming file exists)
result = await db_agent.chat("ingest data from ./data/users.csv")
# Returns: {"success": True, ...}
```

**Security Best Practices:**
- **Always use** the default restricted directories in production
- **Add custom** restricted paths for your specific environment
- **Test security** settings before deployment
- **Monitor access** attempts to restricted directories
- **Regular audits** of file access patterns

#### Monitoring & Maintenance

```python
from ambivo_agents.core import get_shared_manager

shared_manager = get_shared_manager()

# Monitor disk usage
usage = shared_manager.get_disk_usage()
print(f"Total usage: {usage['total_bytes'] / (1024**3):.2f} GB")

# Cleanup old temporary files
cleaned_count = shared_manager.cleanup_temp_files(max_age_hours=24)
print(f"Cleaned {cleaned_count} temporary files")

# List outputs for specific agent
output_files = shared_manager.list_outputs("analytics")
print(f"Analytics outputs: {output_files}")
```

#### Supported File Types & Detection

The system automatically detects file paths in natural language and supports:

**Data Files**: `.csv`, `.xlsx`, `.xls`, `.json`, `.xml`, `.parquet`  
**Media Files**: `.mp4`, `.avi`, `.mov`, `.mp3`, `.wav`, `.flac`  
**Text Files**: `.txt`, `.md`, `.log`, `.py`, `.js`, `.sql`  
**Documents**: `.pdf` (read-only)

```
# These requests automatically trigger file sharing:
"convert data.csv to xlsx"                    → Detects: data.csv → ./docker_shared/input/code/
"extract audio from video.mp4"               → Detects: video.mp4 → ./docker_shared/input/media/
"analyze quarterly_report.xlsx"              → Detects: quarterly_report.xlsx → ./docker_shared/input/analytics/
"scrape data from website"                   → No file detected → ./docker_shared/output/scraper/
```

#### Docker Image Configuration

**Default Image**: `sgosain/amb-ubuntu-python-public-pod`

**Custom Docker Image for Consolidated Structure**:

```dockerfile
FROM sgosain/amb-ubuntu-python-public-pod

# Install additional packages for your use case
RUN pip install openpyxl xlsxwriter plotly seaborn

# Create consolidated mount points
RUN mkdir -p /docker_shared/{input,output,temp,handoff,work}

# Add custom scripts that work with consolidated structure
COPY your-scripts/ /opt/scripts/

# Set working directory
WORKDIR /docker_shared/work

# Example script that uses consolidated paths
RUN echo '#!/bin/bash\n\
echo "Input files: $(ls -la /docker_shared/input/)"\n\
echo "Output directory: /docker_shared/output/"\n\
echo "Temp directory: /docker_shared/temp/"\n\
echo "Handoff directory: /docker_shared/handoff/"' > /opt/scripts/show_structure.sh

RUN chmod +x /opt/scripts/show_structure.sh
```

#### Troubleshooting

**Directory Issues:**
```bash
# Check if docker_shared structure exists
ls -la docker_shared/

# Verify agent subdirectories
ls -la docker_shared/output/
```

**File Access Issues:**
```bash
# Check permissions
chmod 755 docker_shared/
find docker_shared/ -type d -exec chmod 755 {} \;

# Verify Docker can access the directory
docker run --rm -v $(pwd)/docker_shared:/docker_shared alpine ls -la /docker_shared
```

**Volume Mount Issues:**
```bash
# Test consolidated volume mounting
docker run --rm \
  -v $(pwd)/docker_shared/input:/docker_shared/input:ro \
  -v $(pwd)/docker_shared/output:/docker_shared/output:rw \
  alpine ls -la /docker_shared/
```

#### Benefits of Consolidated Structure

✅ **Consistency**: All agents use the same directory structure  
✅ **Inter-Agent Workflows**: Seamless file handoffs between agents  
✅ **Security**: Proper read-only/read-write permissions  
✅ **Organization**: Files organized by agent and purpose  
✅ **Monitoring**: Centralized disk usage and cleanup  
✅ **Third-Party Integration**: Easy for custom agent development  
✅ **Auto-Management**: Directories created and managed automatically

## Troubleshooting

### Common Issues

1. **Redis Connection Failed**
   ```bash
   # Check if Redis is running
   redis-cli ping  # Should return "PONG"
   ```

2. **Docker Not Available**
   ```bash
   # Check Docker is running
   docker ps
   ```

3. **Agent Creation Errors**
   ```python
   from ambivo_agents import ModeratorAgent
   try:
       moderator, context = ModeratorAgent.create(user_id="test")
       print(f"Success: {context.session_id}")
       await moderator.cleanup_session()
   except Exception as e:
       print(f"Error: {e}")
   ```

4. **Import Errors**
   ```bash
   python -c "from ambivo_agents import ModeratorAgent; print('Import success')"
   ```

### Debug Mode

Enable verbose logging:
```yaml
service:
  log_level: "DEBUG"
  log_to_file: true
```

## Security Considerations

- **Docker Isolation**: All code execution happens in isolated containers
- **Network Restrictions**: Containers run with `network_disabled=True` by default
- **Resource Limits**: Memory and CPU limits prevent resource exhaustion  
- **API Key Management**: Store sensitive keys in environment variables
- **Input Sanitization**: All user inputs are validated and sanitized
- **Session Isolation**: Each agent session is completely isolated

## Contributing

We welcome contributions! Please see our [Contributing Guidelines](CONTRIBUTING.md) for details.

### Development Setup

```bash
# Clone repository
git clone https://github.com/ambivo-corp/ambivo-agents.git
cd ambivo-agents

# Install in development mode
pip install -e .

# Test ModeratorAgent
python -c "
from ambivo_agents import ModeratorAgent
import asyncio

async def test():
    moderator, context = ModeratorAgent.create(user_id='test')
    response = await moderator.chat('Hello!')
    print(f'Response: {response}')
    await moderator.cleanup_session()

asyncio.run(test())
"
```

## License

MIT License - see [LICENSE](LICENSE) file for details.

## Author

**Hemant Gosain 'Sunny'**
- Company: [Ambivo](https://www.ambivo.com)
- Email: info@ambivo.com

## Support

- Email: info@ambivo.com
- Website: https://www.ambivo.com
- Issues: [GitHub Issues](https://github.com/ambivo-corp/ambivo-agents/issues)

## Attributions & Third-Party Technologies

This project leverages several open-source libraries and commercial services:

### Core Technologies
- **Docker**: Container runtime for secure code execution
- **Redis**: In-memory data store for session management
- **Python**: Core programming language

### AI/ML Frameworks
- **OpenAI**: GPT models and API services
- **Anthropic**: Claude models and API services  
- **AWS Bedrock**: Cloud-based AI model access
- **LangChain**: Framework for building AI applications (by LangChain, Inc.)
- **LlamaIndex**: Data framework for LLM applications (by Jerry Liu)
- **Hugging Face**: Model hub and transformers library

### Data Processing
- **pandas**: Data analysis and manipulation library
- **DuckDB**: In-process SQL OLAP database
- **Qdrant**: Vector database for semantic search
- **tabulate**: ASCII table formatting library

### Media & Web
- **FFmpeg**: Multimedia processing framework
- **YouTube**: Video platform (via public APIs)
- **pytubefix**: YouTube video downloader library
- **Brave Search**: Web search API service
- **Beautiful Soup**: HTML/XML parsing library

### Development Tools
- **pytest**: Testing framework
- **black**: Code formatting tool
- **Docker Hub**: Container image repository

## Legal Disclaimer

**IMPORTANT**: This software is provided "as is" without warranty of any kind. Users are responsible for:

1. **API Compliance**: Ensuring compliance with all third-party service terms (OpenAI, Anthropic, AWS, YouTube, etc.)
2. **Data Privacy**: Protecting user data and complying with applicable privacy laws
3. **Usage Limits**: Respecting rate limits and usage policies of external services
4. **Security**: Implementing appropriate security measures for production use
5. **Licensing**: Ensuring compliance with all third-party library licenses

The authors and contributors are not liable for any damages arising from the use of this software. Users should thoroughly test and validate the software before production deployment.

**Third-Party Services**: This library integrates with external services that have their own terms of service, privacy policies, and usage limitations. Users must comply with all applicable terms.

**Web Scraping & Content Access**: Users must practice ethical web scraping by respecting robots.txt, rate limits, and website terms of service. YouTube content access must comply with YouTube's Terms of Service and API policies - downloading copyrighted content without permission is prohibited.

---

*Developed by the Ambivo team.*


### Query Across Multiple Knowledge Bases

You can query multiple knowledge bases by passing kb_names via metadata on either the ExecutionContext or the AgentMessage. The agent accepts kb_names as a list of strings, a list of dicts ({kb_name, description}), or a JSON string.

```python
from ambivo_agents.agents.knowledge_base import KnowledgeBaseAgent
from ambivo_agents.core.base import ExecutionContext, AgentMessage
import asyncio

async def demo():
    agent = KnowledgeBaseAgent()

    # 1) Via ExecutionContext.metadata — list of strings
    ctx = ExecutionContext(
        user_id="u",
        session_id="s",
        conversation_id="c",
        metadata={"kb_names": ["product_docs", "engineering_wiki"]},
    )
    resp = await agent.process_message("What changed in v2.0 API?", context=ctx)
    print(resp.content)
    print(resp.metadata)  # includes used_kbs, primary_kb, sources_dict

    # 2) Via AgentMessage.metadata — list of dicts
    msg = AgentMessage(
        id="m1",
        sender_id="u",
        recipient_id=agent.agent_id,
        content="Summarize PTO policy.",
        metadata={
            "kb_names": [
                {"kb_name": "hr_policies", "description": "HR docs"},
                {"kb_name": "employee_handbook"},
            ]
        },
    )
    resp2 = await agent.process_message(msg)
    print(resp2.content)
    print(resp2.metadata)

asyncio.run(demo())
```

See examples/knowledge_base_multiple.py for a more complete example, including passing kb_names as a JSON string.
