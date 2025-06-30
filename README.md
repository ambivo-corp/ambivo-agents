# Ambivo Agents - Multi-Agent AI System

A toolkit for AI-powered automation including media processing, knowledge base operations, web scraping, YouTube downloads, and more.

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
- [Prerequisites](#prerequisites)
- [Installation](#installation)
- [Configuration](#configuration)
- [Configuration Methods](#configuration-methods)
- [Project Structure](#project-structure)
- [Usage Examples](#usage-examples)
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
    response1 = await moderator.chat("Download audio from https://youtube.com/watch?v=dQw4w9WgXcQ")
    response2 = await moderator.chat("Search for latest AI trends")
    response3 = await moderator.chat("Extract audio from video.mp4 as MP3")
    response4 = await moderator.chat("What is machine learning?")
    
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
- **Context Memory**: Maintains conversation history across interactions
- **Docker Integration**: Secure, isolated execution environment
- **Redis Memory**: Persistent conversation memory with compression
- **Multi-Provider LLM**: Automatic failover between OpenAI, Anthropic, and AWS Bedrock
- **Configuration-Driven**: All features controlled via `agent_config.yaml`

## Available Agents

### ModeratorAgent 
- Intelligent orchestrator that routes to specialized agents
- Context-aware multi-turn conversations
- Automatic agent selection based on query analysis
- Session management and cleanup

### Assistant Agent
- General purpose conversational AI
- Context-aware responses
- Multi-turn conversations

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

docker:
  timeout: 60
  memory_limit: "512m"
  images: ["sgosain/amb-ubuntu-python-public-pod"]
```

## Configuration

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
export AMBIVO_AGENTS_MODERATOR_ENABLED_AGENTS="youtube_download,web_search,assistant"

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

**Replace ALL placeholder values** with your actual credentials, then create `agent_config.yaml` in your project root:

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

docker:
  timeout: 60
  memory_limit: "512m"
  images: ["sgosain/amb-ubuntu-python-public-pod"]
```

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

**Note:** Environment variables take precedence over YAML configuration. The `agent_config.yaml` file is  optional when using environment variables.

## Project Structure

```
ambivo_agents/
├── agents/          # Agent implementations
│   ├── assistant.py
│   ├── code_executor.py
│   ├── knowledge_base.py
│   ├── media_editor.py
│   ├── moderator.py     # ModeratorAgent (main orchestrator)
│   ├── simple_web_search.py
│   ├── web_scraper.py
│   ├── web_search.py
│   └── youtube_download.py
├── config/          # Configuration management
├── core/            # Core functionality
│   ├── base.py
│   ├── llm.py
│   └── memory.py
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
        "Download audio from https://youtube.com/watch?v=dQw4w9WgXcQ",
        "Search for latest artificial intelligence news",  
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

---

*Developed by the Ambivo team.*