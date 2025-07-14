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

### API Agent
- Comprehensive HTTP/REST API integration
- Multiple authentication methods (Bearer, API Key, Basic, OAuth2)
- Pre-fetch authentication with automatic token refresh
- Built-in retry logic with exponential backoff
- Security features (domain filtering, SSL verification)
- Support for all HTTP methods (GET, POST, PUT, DELETE, etc.)

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
```bash
pip install -r requirements.txt
```

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

### Custom Docker Image

```dockerfile
FROM sgosain/amb-ubuntu-python-public-pod

# Install additional packages
RUN pip install your-additional-packages

# Add custom scripts
COPY your-scripts/ /opt/scripts/
```

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