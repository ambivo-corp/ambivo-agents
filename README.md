# Ambivo Agents - Multi-Agent AI System

A minimalistic toolkit for AI-powered automation including media processing, knowledge base operations, web scraping, YouTube downloads, and more.

## ⚠️ Alpha Release Disclaimer

**This library is currently in alpha stage.** While functional, it may contain bugs, undergo breaking changes, and lack complete documentation. **Developers should thoroughly evaluate and test the library before considering it for production use.** Use in production environments is at your own risk.

For production scenarios, we recommend:
- Extensive testing in your specific environment
- Implementing proper error handling and monitoring
- Having rollback plans in place
- Staying updated with releases for critical fixes

**Development Roadmap**: We are actively working toward a stable 1.0 release. Breaking changes may occur during the alpha phase as we refine the API and improve stability.

## Table of Contents

- [Quick Start](#quick-start)
- [Simple ModeratorAgent Example](#simple-moderatoragent-example)
- [Agent Creation](#agent-creation)
- [Features](#features)
- [Available Agents](#available-agents)
- [Prerequisites](#prerequisites)
- [Installation](#installation)
- [Configuration](#configuration)
- [Usage Examples](#usage-examples)
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

### Simple ModeratorAgent Example

The **ModeratorAgent** is the easiest way to get started. It automatically routes your queries to the right specialized agents:

```python
from ambivo_agents import ModeratorAgent
import asyncio

async def main():
    # Create the moderator (one agent to rule them all!)
    moderator, context = ModeratorAgent.create(user_id="john")
    
    print(f"✅ Moderator: {moderator.agent_id}")
    print(f"📋 Session: {context.session_id}")
    
    # Just chat! The moderator routes automatically:
    
    # This will go to YouTubeDownloadAgent
    response1 = await moderator.chat("Download audio from https://youtube.com/watch?v=dQw4w9WgXcQ")
    print(f"🎵 {response1}")
    
    # This will go to WebSearchAgent  
    response2 = await moderator.chat("Search for latest AI trends")
    print(f"🔍 {response2}")
    
    # This will go to MediaEditorAgent
    response3 = await moderator.chat("Extract audio from video.mp4 as MP3")
    print(f"🎬 {response3}")
    
    # This will go to AssistantAgent
    response4 = await moderator.chat("What is machine learning?")
    print(f"💬 {response4}")
    
    # Check what agents are available
    status = await moderator.get_agent_status()
    print(f"🤖 Available agents: {list(status['active_agents'].keys())}")
    
    # Cleanup when done
    await moderator.cleanup_session()

# Run it
asyncio.run(main())
```

**That's it!** The ModeratorAgent automatically:
- ✅ **Routes** your queries to the right specialist
- ✅ **Maintains** conversation context
- ✅ **Manages** all the underlying agents
- ✅ **Handles** configuration and setup

### Even Simpler - Command Line

```bash
# Install and run
pip install ambivo-agents

# Interactive mode (auto-routing)
ambivo-agents

# Or single commands
ambivo-agents -q "Download audio from https://youtube.com/watch?v=example"
ambivo-agents -q "Search for Python tutorials"
ambivo-agents -q "Extract audio from video.mp4"
```

## Simple ModeratorAgent Example



### Basic ModeratorAgent Usage

```python
from ambivo_agents import ModeratorAgent
import asyncio

async def simple_example():
    # Create moderator with auto-configuration
    moderator, context = ModeratorAgent.create(user_id="alice")
    
    print(f"🚀 Session {context.session_id} started")
    
    # The moderator routes these automatically:
    tasks = [
        "Download https://youtube.com/watch?v=example",           # → YouTube Agent
        "Search for latest Python frameworks",                   # → Web Search Agent  
        "Convert video.mp4 to audio",                           # → Media Editor Agent
        "What's the capital of France?",                        # → Assistant Agent
        "Scrape https://example.com for content",               # → Web Scraper Agent
    ]
    
    for task in tasks:
        print(f"\n👤 User: {task}")
        response = await moderator.chat(task)
        print(f"🤖 Bot: {response[:100]}...")  # First 100 chars
    
    # Check routing info
    status = await moderator.get_agent_status()
    print(f"\n📊 Processed via {status['total_agents']} specialized agents")
    
    await moderator.cleanup_session()

asyncio.run(simple_example())
```

### Context-Aware Conversations

The ModeratorAgent maintains conversation context:

```python
async def context_example():
    moderator, context = ModeratorAgent.create(user_id="bob")
    
    # Initial request
    response1 = await moderator.chat("Download audio from https://youtube.com/watch?v=example")
    print(response1)
    
    # Follow-up (moderator remembers the YouTube URL)
    response2 = await moderator.chat("Actually, download the video instead")
    print(response2)
    
    # Another follow-up (still remembers context)
    response3 = await moderator.chat("Get information about that video")
    print(response3)
    
    await moderator.cleanup_session()
```

### Custom Agent Configuration using enabled_agents

```python
async def custom_moderator():
    # Enable only specific agents
    moderator, context = ModeratorAgent.create(
        user_id="charlie",
        enabled_agents=['youtube_download', 'web_search', 'assistant']
    )
    
    # Only these agents will be available for routing
    status = await moderator.get_agent_status()
    print(f"Enabled: {list(status['active_agents'].keys())}")
    
    await moderator.cleanup_session()
```

### Integration with Existing Code

```python
class ChatBot:
    def __init__(self):
        self.moderator = None
        self.context = None
    
    async def start_session(self, user_id: str):
        self.moderator, self.context = ModeratorAgent.create(user_id=user_id)
        return self.context.session_id
    
    async def process_message(self, message: str) -> str:
        if not self.moderator:
            raise ValueError("Session not started")
        
        return await self.moderator.chat(message)
    
    async def end_session(self):
        if self.moderator:
            await self.moderator.cleanup_session()

# Usage
bot = ChatBot()
session_id = await bot.start_session("user123")
response = await bot.process_message("Download audio from YouTube")
await bot.end_session()
```

## Agent Creation

### ModeratorAgent 



```python
from ambivo_agents import ModeratorAgent

# Create moderator with auto-routing to specialized agents
moderator, context = ModeratorAgent.create(user_id="john")
print(f"Session: {context.session_id}")

# Just chat - moderator handles the routing!
result = await moderator.chat("Download audio from https://youtube.com/watch?v=example")
print(result)

# Cleanup when done
await moderator.cleanup_session()
```

**When to use ModeratorAgent:**
- ✅ **Most applications** (recommended default)
- ✅ **Multi-purpose chatbots** and assistants
- ✅ **Intelligent routing** between different capabilities
- ✅ **Context-aware** conversations
- ✅ **Simplified development** - one agent does everything

### Direct Agent Creation

Use direct creation for specific, single-purpose applications:

```python
from ambivo_agents import YouTubeDownloadAgent

# Create agent with explicit context
agent, context = YouTubeDownloadAgent.create(user_id="john")
print(f"Session: {context.session_id}")

# Use agent directly for specific task
result = await agent._download_youtube_audio("https://youtube.com/watch?v=example")

# Cleanup when done
await agent.cleanup_session()
```

**When to use Direct Creation:**
- ✅ **Single-purpose** applications (only YouTube, only search, etc.)
- ✅ **Specific workflows** with known agent requirements
- ✅ **Performance-critical** applications (no routing overhead)
- ✅ **Custom integrations** with existing systems

### Service-Based Creation

Use the service method for production multi-user systems:

```python
from ambivo_agents.services import create_agent_service

service = create_agent_service()
session_id = service.create_session()

# Service automatically routes to the appropriate agent
result = await service.process_message(
    message="download audio from youtube.com/watch?v=example",
    session_id=session_id,
    user_id="user123"
)
```

**When to use Service:**
- ✅ **Production systems** with multiple users - manage sessions
- ✅ **Session management** across users
- ✅ **Scalable architectures** with load balancing
- ✅ **Advanced monitoring** and analytics

## Features

### Core Capabilities
- **🤖 ModeratorAgent**: Intelligent multi-agent orchestrator with automatic routing
- **🔄 Smart Routing**: Automatically routes queries to the most appropriate specialized agent
- **🧠 Context Memory**: Maintains conversation history and context across interactions
- **🐳 Docker Integration**: Secure, isolated execution environment for code and media processing
- **📦 Redis Memory**: Persistent conversation memory with compression and caching
- **🔀 Multi-Provider LLM**: Automatic failover between OpenAI, Anthropic, and AWS Bedrock
- **⚙️ Configuration-Driven**: All features controlled via `agent_config.yaml`

## Available Agents

### 🎛️ **ModeratorAgent** 
- **Intelligent orchestrator** that routes to specialized agents
- **Context-aware** multi-turn conversations
- **Automatic agent selection** based on query analysis
- **Session management** and cleanup

### 🤖 Assistant Agent
- General purpose conversational AI
- Context-aware responses
- Multi-turn conversations

### 💻 Code Executor Agent
- Secure Python and Bash execution in Docker
- Isolated environment with resource limits
- Real-time output streaming

### 🔍 Web Search Agent
- Multi-provider search (Brave, AVES APIs)
- Academic search capabilities
- Automatic provider failover

### 🕷️ Web Scraper Agent
- Proxy-enabled scraping (ScraperAPI compatible)
- Playwright and requests-based scraping
- Batch URL processing with rate limiting

### 📚 Knowledge Base Agent
- Document ingestion (PDF, DOCX, TXT, web URLs)
- Vector similarity search with Qdrant
- Semantic question answering

### 🎥 Media Editor Agent
- Audio/video processing with FFmpeg
- Format conversion, resizing, trimming
- Audio extraction and volume adjustment

### 🎬 YouTube Download Agent
- Download videos and audio from YouTube
- Docker-based execution with pytubefix
- Automatic title sanitization and metadata extraction

## Prerequisites

### Required
- **Python 3.11+**
- **Docker** (for code execution, media processing, YouTube downloads)
- **Redis** (Cloud Redis recommended: Redis Cloud)

### Recommended Cloud Services
- **Redis Cloud** 
- **Qdrant Cloud** for knowledge base operations
- **AWS Bedrock**, **OpenAI**, or **Anthropic** for LLM services

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

# Install requirements
pip install -r requirements.txt
```

### 2. Setup Docker Images
```bash
# Pull the multi-purpose container image
docker pull sgosain/amb-ubuntu-python-public-pod
```

### 3. Setup Redis

**Recommended: Cloud Redis **
```yaml
# In agent_config.yaml
redis:
  host: "your-redis-cloud-endpoint.redis.cloud"
  port: 6379
  password: "your-redis-password"
```

**Alternative: Local Redis**
```bash
# Using Docker (for development)
docker run -d --name redis -p 6379:6379 redis:latest

# Or install locally
# sudo apt-get install redis-server  # Ubuntu/Debian
# brew install redis                 # macOS
```

## Configuration

Create `agent_config.yaml` in your project root:

```yaml
# Redis Configuration (Required)
redis:
  host: "your-redis-cloud-endpoint.redis.cloud"  # Recommended: Cloud Redis
  port: 6379
  db: 0
  password: "your-redis-password"  # Required for cloud
  # Alternative local: host: "localhost", password: null

# LLM Configuration (Required - at least one provider)
llm:
  preferred_provider: "openai"  # openai, anthropic, or bedrock
  temperature: 0.7
  
  # Provider API Keys
  openai_api_key: "your-openai-key"
  anthropic_api_key: "your-anthropic-key"
  
  # AWS Bedrock (optional)
  aws_access_key_id: "your-aws-key"
  aws_secret_access_key: "your-aws-secret"
  aws_region: "us-east-1"

# Agent Capabilities (Enable/disable features)
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

# used by the ModeratorAgent to determine which agents to enable if not explicitly specified in code
# by default all agents are enabled
moderator:
  default_enabled_agents:
    - knowledge_base
    - web_search
    - assistant
    - media_editor
    - youtube_download
    - code_executor  # Enable only if needed for security
    - web_scraper    # Enable only if needed

# Web Search Configuration (if enabled)
web_search:
  brave_api_key: "your-brave-api-key"
  avesapi_api_key: "your-aves-api-key"

# Web Scraping Configuration (if enabled)
web_scraping:
  proxy_enabled: true
  proxy_config:
    http_proxy: "http://scraperapi:your-key@proxy-server.scraperapi.com:8001"
  default_headers:
    User-Agent: "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
  timeout: 60
  max_links_per_page: 100

# Knowledge Base Configuration (if enabled)
knowledge_base:
  qdrant_url: "https://your-cluster.qdrant.tech"  # Recommended: Qdrant Cloud
  qdrant_api_key: "your-qdrant-api-key"           # Required for cloud
  # Alternative local: "http://localhost:6333"
  chunk_size: 1024
  chunk_overlap: 20
  similarity_top_k: 5

# Media Editor Configuration (if enabled)
media_editor:
  docker_image: "sgosain/amb-ubuntu-python-public-pod"
  input_dir: "./media_input"
  output_dir: "./media_output" 
  timeout: 300
  memory_limit: "2g"

# YouTube Download Configuration (if enabled)
youtube_download:
  docker_image: "sgosain/amb-ubuntu-python-public-pod"
  download_dir: "./youtube_downloads"
  timeout: 600
  memory_limit: "1g"
  default_audio_only: true

# Docker Configuration
docker:
  timeout: 60
  memory_limit: "512m"
  images: ["sgosain/amb-ubuntu-python-public-pod"]

# Service Configuration
service:
  max_sessions: 100
  session_timeout: 3600
  log_level: "INFO"
  log_to_file: false

# Memory Management
memory_management:
  compression:
    enabled: true
    algorithm: "lz4"
  cache:
    enabled: true
    max_size: 1000
    ttl_seconds: 300
```

## Project Structure

```
ambivo_agents/
├── agents/          # Agent implementations
│   ├── assistant.py
│   ├── code_executor.py
│   ├── knowledge_base.py
│   ├── media_editor.py
│   ├── moderator.py     # 🎛️ ModeratorAgent (main orchestrator)
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

### 🎛️ ModeratorAgent Examples

#### Basic Usage with Auto-Routing
```python
from ambivo_agents import ModeratorAgent
import asyncio

async def basic_moderator():
    # Create the moderator
    moderator, context = ModeratorAgent.create(user_id="demo_user")
    
    print(f"✅ Session: {context.session_id}")
    
    # Auto-routing examples
    examples = [
        "Download audio from https://youtube.com/watch?v=dQw4w9WgXcQ",
        "Search for latest artificial intelligence news",  
        "Extract audio from video.mp4 as high quality MP3",
        "What is machine learning and how does it work?",
        "Scrape https://example.com for content"
    ]
    
    for query in examples:
        print(f"\n👤 User: {query}")
        response = await moderator.chat(query)
        print(f"🤖 Bot: {response[:150]}...")
    
    # Check which agents handled the requests
    status = await moderator.get_agent_status()
    print(f"\n📊 Used {status['total_agents']} specialized agents")
    for agent_type in status['active_agents']:
        print(f"   • {agent_type}")
    
    await moderator.cleanup_session()

asyncio.run(basic_moderator())
```

#### Context-Aware Conversations
```python
async def context_conversation():
    moderator, context = ModeratorAgent.create(user_id="context_demo")
    
    # Initial request  
    response1 = await moderator.chat("Download audio from https://youtube.com/watch?v=example")
    print(f"🎵 {response1}")
    
    # Follow-up using context (moderator remembers the YouTube URL)
    response2 = await moderator.chat("Actually, download the video instead of just audio")
    print(f"🎬 {response2}")
    
    # Another follow-up
    response3 = await moderator.chat("Get information about that video")
    print(f"📊 {response3}")
    
    await moderator.cleanup_session()
```

#### Custom Agent Selection
```python
async def custom_agents():
    # Only enable specific capabilities
    moderator, context = ModeratorAgent.create(
        user_id="custom_user",
        enabled_agents=['youtube_download', 'web_search', 'assistant']
    )
    
    # Only these agents will be available
    status = await moderator.get_agent_status()
    print(f"Available agents: {list(status['active_agents'].keys())}")
    
    response = await moderator.chat("Download https://youtube.com/watch?v=example")
    print(response)
    
    await moderator.cleanup_session()
```

### 🎬 YouTube Downloads
```python
from ambivo_agents import YouTubeDownloadAgent

async def download_youtube():
    agent, context = YouTubeDownloadAgent.create(user_id="media_user")
    
    # Download audio
    result = await agent._download_youtube_audio(
        "https://youtube.com/watch?v=example"
    )
    
    if result['success']:
        print(f"✅ Audio downloaded: {result['filename']}")
        print(f"📍 Path: {result['file_path']}")
        print(f"📊 Size: {result['file_size_bytes']:,} bytes")
    
    # Get video info
    info = await agent._get_youtube_info(
        "https://youtube.com/watch?v=example"
    )
    
    if info['success']:
        video_info = info['video_info']
        print(f"📹 Title: {video_info['title']}")
        print(f"⏱️ Duration: {video_info['duration']} seconds")
    
    await agent.cleanup_session()
```

### 📚 Knowledge Base Operations
```python
from ambivo_agents import KnowledgeBaseAgent

async def knowledge_base_demo():
    agent, context = KnowledgeBaseAgent.create(
        user_id="kb_user",
        session_metadata={"project": "company_docs"}
    )
    
    print(f"Session: {context.session_id}")
    
    # Ingest document
    result = await agent._ingest_document(
        kb_name="company_kb",
        doc_path="/path/to/document.pdf",
        custom_meta={"department": "HR", "type": "policy"}
    )
    
    if result['success']:
        print("✅ Document ingested")
        
        # Query the knowledge base
        answer = await agent._query_knowledge_base(
            kb_name="company_kb",
            query="What is the remote work policy?"
        )
        
        if answer['success']:
            print(f"📝 Answer: {answer['answer']}")
    
    # View conversation history
    history = await agent.get_conversation_history(limit=5)
    print(f"💬 Messages in session: {len(history)}")
    
    await agent.cleanup_session()
```

### 🔍 Web Search
```python
from ambivo_agents import WebSearchAgent

async def search_demo():
    agent, context = WebSearchAgent.create(user_id="search_user")
    
    # Search the web
    results = await agent._search_web(
        "artificial intelligence trends 2024",
        max_results=5
    )
    
    if results['success']:
        print(f"🔍 Found {len(results['results'])} results")
        
        for i, result in enumerate(results['results'], 1):
            print(f"{i}. {result['title']}")
            print(f"   {result['url']}")
            print(f"   {result['snippet'][:100]}...")
    
    await agent.cleanup_session()
```

### 🎵 Media Processing
```python
from ambivo_agents import MediaEditorAgent

async def media_demo():
    agent, context = MediaEditorAgent.create(user_id="media_user")
    
    # Extract audio from video
    result = await agent._extract_audio_from_video(
        input_video="/path/to/video.mp4",
        output_format="mp3",
        audio_quality="high"
    )
    
    if result['success']:
        print(f"✅ Audio extracted: {result['output_file']}")
    
    await agent.cleanup_session()
```

### Context Manager Pattern (Auto-Cleanup)

```python
from ambivo_agents import ModeratorAgent, AgentSession
import asyncio

async def main():
    # Auto-cleanup with context manager
    async with AgentSession(ModeratorAgent, user_id="sarah") as moderator:
        print(f"Session: {moderator.context.session_id}")
        
        # Use moderator - cleanup happens automatically
        response = await moderator.chat("Download audio from https://youtube.com/watch?v=example")
        print(response)
        
        # Check agent status
        status = await moderator.get_agent_status()
        print(f"Active agents: {list(status['active_agents'].keys())}")
    # Moderator automatically cleaned up here

asyncio.run(main())
```

## Command Line Interface

The CLI provides full command line access to all agent capabilities, 
allowing you to interact with the system without writing code. reads from the `agent_config.yaml` file for configuration.:

```bash
# Install the CLI
pip install ambivo-agents

# Interactive mode with auto-routing
ambivo-agents

# Single queries (auto-routed)
ambivo-agents -q "Download audio from https://youtube.com/watch?v=example"
ambivo-agents -q "Search for latest AI trends"
ambivo-agents -q "Extract audio from video.mp4"

# Check agent status
ambivo-agents status

# Test all agents
ambivo-agents --test
```

### Command Line Examples
```bash
# ModeratorAgent routes these automatically:

# YouTube downloads
ambivo-agents -q "Download https://youtube.com/watch?v=example --audio-only"
ambivo-agents -q "Get info about https://youtube.com/watch?v=example"

# Web search
ambivo-agents -q "Search for latest Python frameworks"
ambivo-agents -q "Find news about artificial intelligence"

# Media processing  
ambivo-agents -q "Extract audio from video.mp4 as high quality mp3"
ambivo-agents -q "Convert video.avi to mp4"

# General assistance
ambivo-agents -q "What is machine learning?"
ambivo-agents -q "Explain quantum computing"

# Interactive mode with smart routing
ambivo-agents
> Download audio from YouTube
> Search for AI news
> Extract audio from my video file
> What's the weather like?
```

### CLI Status and Debugging

```bash
# Check agent status
ambivo-agents status

# View configuration
ambivo-agents config  

# Debug mode
ambivo-agents --debug -q "test query"

# Test all capabilities
ambivo-agents --test
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

### Agent Capabilities
Each agent provides specialized functionality:

- **🎛️ ModeratorAgent** → Intelligent routing and orchestration
- **🎬 YouTube Download Agent** → Video/audio downloads with pytubefix
- **🎥 Media Editor Agent** → FFmpeg-based processing
- **📚 Knowledge Base Agent** → Qdrant vector search
- **🔍 Web Search Agent** → Multi-provider search
- **🕷️ Web Scraper Agent** → Proxy-enabled scraping
- **💻 Code Executor Agent** → Docker-based execution

### Memory System
- **Redis-based persistence** with compression and caching
- **Built-in conversation history** for every agent
- **Session-aware context** with automatic cleanup
- **Multi-session support** with isolation

### LLM Provider Management
- **Automatic failover** between OpenAI, Anthropic, AWS Bedrock
- **Rate limiting** and error handling
- **Provider rotation** based on availability and performance

## Docker Setup

### Custom Docker Image
If you need additional dependencies, extend the base image:

```dockerfile
FROM sgosain/amb-ubuntu-python-public-pod

# Install additional packages
RUN pip install your-additional-packages

# Add custom scripts
COPY your-scripts/ /opt/scripts/
```

### Volume Mounting
The agents automatically handle volume mounting for:
- Media input/output directories
- YouTube download directories  
- Code execution workspaces

## Troubleshooting

### Common Issues

1. **ModeratorAgent Routing Issues**
   ```python
   # Check available agents
   status = await moderator.get_agent_status()
   print(f"Available: {list(status['active_agents'].keys())}")
   
   # Check configuration
   print(f"Enabled: {moderator.enabled_agents}")
   ```

2. **Redis Connection Failed**
   ```bash
   # For cloud Redis: Check connection details in agent_config.yaml
   # For local Redis: Check if running
   redis-cli ping  # Should return "PONG"
   ```

3. **Docker Not Available**
   ```bash
   # Check Docker is running
   docker ps
   # Install if missing: https://docs.docker.com/get-docker/
   ```

4. **Agent Creation Errors**
   ```python
   # Check moderator can be created
   from ambivo_agents import ModeratorAgent
   try:
       moderator, context = ModeratorAgent.create(user_id="test")
       print(f"✅ Success: {context.session_id}")
       await moderator.cleanup_session()
   except Exception as e:
       print(f"❌ Error: {e}")
   ```

5. **Import Errors**
   ```bash
   # Ensure clean imports work
   python -c "from ambivo_agents import ModeratorAgent; print('✅ Import success')"
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

**Alpha Release**: This software is provided "as is" without warranty. Users assume all risks associated with its use, particularly in production environments.

## Author

**Hemant Gosain 'Sunny'**
- Company: [Ambivo](https://www.ambivo.com)
- Email: info@ambivo.com

## Support

- 📧 Email: info@ambivo.com
- 🌐 Website: https://www.ambivo.com
- 📖 Documentation: [Coming Soon]
- 🐛 Issues: [GitHub Issues](https://github.com/ambivo-corp/ambivo-agents/issues)

**Alpha Support**: As an alpha release, support is provided on a best-effort basis. Response times may vary, and some issues may require significant investigation.

---

*Developed by the Ambivo team.*