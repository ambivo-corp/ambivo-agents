# Ambivo Agents - Multi-Agent AI System

A minimalistic toolkit for AI-powered automation including media processing, knowledge base operations, web scraping, YouTube downloads, and more.

## 🌟  Direct Agent Creation Paradigm


```python
# 🌟 RECOMMENDED APPROACH
from ambivo_agents import YouTubeDownloadAgent, KnowledgeBaseAgent

# Create agent with explicit context
agent, context = YouTubeDownloadAgent.create(user_id="john")
print(f"Session: {context.session_id}")
print(f"User: {context.user_id}")

# Use agent directly
result = await agent._download_youtube_audio("https://youtube.com/watch?v=example")

# Cleanup when done
await agent.cleanup_session()
```

**Benefits of the approach:**
- ✅ **Explicit Context**: Session IDs, user IDs, and metadata are always visible
- ✅ **Better Control**: Full lifecycle management of agents and sessions
- ✅ **Built-in Memory**: Conversation history built into every agent

## 🚀 Features

### Core Capabilities
- **Multi-Agent Architecture**: Specialized agents for different tasks with intelligent routing
- **Docker-Based Execution**: Secure, isolated execution environment for code and media processing
- **Redis Memory Management**: Persistent conversation memory with compression and caching
- **Multi-Provider LLM Support**: Automatic failover between OpenAI, Anthropic, and AWS Bedrock
- **Configuration-Driven**: All features controlled via `agent_config.yaml`


### Available Agents

#### 🤖 Assistant Agent
- General purpose conversational AI
- Context-aware responses
- Multi-turn conversations

#### 💻 Code Executor Agent  
- Secure Python and Bash execution in Docker
- Isolated environment with resource limits
- Real-time output streaming

#### 🔍 Web Search Agent
- Multi-provider search (Brave, AVES APIs)
- s and academic search capabilities
- Automatic provider failover

#### 🕷️ Web Scraper Agent
- Proxy-enabled scraping (ScraperAPI compatible)
- Playwright and requests-based scraping
- Batch URL processing with rate limiting

#### 📚 Knowledge Base Agent
- Document ingestion (PDF, DOCX, TXT, web URLs)
- Vector similarity search with Qdrant
- Semantic question answering

#### 🎥 Media Editor Agent
- Audio/video processing with FFmpeg
- Format conversion, resizing, trimming
- Audio extraction and volume adjustment

#### 🎬 YouTube Download Agent
- Download videos and audio from YouTube
- Docker-based execution with pytubefix
- Automatic title sanitization and metadata extraction

## 📋 Prerequisites

### Required
- **Python 3.11+**
- **Docker** (for code execution, media processing, YouTube downloads)
- **Redis** (for memory management)

### API Keys (Optional - based on enabled features)
- **OpenAI API Key** (for GPT models)
- **Anthropic API Key** (for Claude models)
- **AWS Credentials** (for Bedrock models)
- **Brave Search API Key** (for web search)
- **AVES API Key** (for web search)
- **ScraperAPI/Proxy credentials** (for web scraping)

## 🛠️ Installation

### 1. Install Dependencies
```bash
# Core dependencies
pip install redis python-dotenv pyyaml click

# LLM providers (choose based on your needs)
pip install openai anthropic boto3 langchain-openai langchain-anthropic langchain-aws

# Knowledge base (if using)
pip install qdrant-client llama-index langchain-unstructured

# Web capabilities (if using)
pip install requests beautifulsoup4 playwright

# Media processing (if using) 
pip install docker

# YouTube downloads (if using)
pip install pytubefix pydantic

# Optional: Install all at once
pip install -r requirements.txt
```

### 2. Setup Docker Images
```bash
# Pull the multi-purpose container image
docker pull sgosain/amb-ubuntu-python-public-pod
```

### 3. Setup Redis
```bash
# Using Docker
docker run -d --name redis -p 6379:6379 redis:latest

# Or install locally
# sudo apt-get install redis-server  # Ubuntu/Debian
# brew install redis                 # macOS
```

## ⚙️ Configuration

Create `agent_config.yaml` in your project root:

```yaml
# Redis Configuration (Required)
redis:
  host: "localhost"
  port: 6379
  db: 0
  password: null  # Set if using Redis AUTH

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
  qdrant_url: "http://localhost:6333"
  qdrant_api_key: null  # Set if using Qdrant Cloud
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

## 🚀 Quick Start

### 🌟  Python API (RECOMMENDED)

```python
from ambivo_agents import YouTubeDownloadAgent, KnowledgeBaseAgent, WebSearchAgent
import asyncio

async def main():
    # 🌟  Direct agent creation with explicit context
    agent, context = YouTubeDownloadAgent.create(user_id="john")
    
    print(f"✅ Agent: {agent.agent_id}")
    print(f"📋 Session: {context.session_id}")
    print(f"👤 User: {context.user_id}")
    
    # Download audio from YouTube
    result = await agent._download_youtube_audio(
        "https://youtube.com/watch?v=dQw4w9WgXcQ"
    )
    
    if result['success']:
        print(f"✅ Downloaded: {result['filename']}")
    
    # Cleanup when done
    await agent.cleanup_session()

# Run
asyncio.run(main())
```

### Context Manager Pattern (Auto-Cleanup)

```python
from ambivo_agents import KnowledgeBaseAgent, AgentSession
import asyncio

async def main():
    # 🔄 Auto-cleanup with context manager
    async with AgentSession(KnowledgeBaseAgent, user_id="sarah") as agent:
        print(f"Session: {agent.context.session_id}")
        
        # Use agent - cleanup happens automatically
        result = await agent._query_knowledge_base(
            kb_name="company_docs",
            query="What is our return policy?"
        )
        
        print(result['answer'])
    # Agent automatically cleaned up here

asyncio.run(main())
```

### Command Line Interface

```bash
# Install the CLI
pip install ambivo-agents

# Health check using  paradigm
ambivo-agents health

# Interactive chat mode with smart routing
ambivo-agents interactive

# Direct YouTube download
ambivo-agents youtube download "https://youtube.com/watch?v=dQw4w9WgXcQ"

# Smart message routing
ambivo-agents chat "download audio from https://youtube.com/watch?v=example"
ambivo-agents chat "search for latest AI trends"
ambivo-agents chat "extract audio from video.mp4"
```

## 📖 Usage Examples

### 🎬 YouTube Downloads ( Direct Approach)
```python
from ambivo_agents import YouTubeDownloadAgent

async def download_youtube():
    agent, context = YouTubeDownloadAgent.create(user_id="media_user")
    
    # Download audio
    result = await agent._download_youtube_audio(
        "https://youtube.com/watch?v=dQw4w9WgXcQ"
    )
    
    if result['success']:
        print(f"✅ Audio downloaded: {result['filename']}")
        print(f"📍 Path: {result['file_path']}")
        print(f"📊 Size: {result['file_size_bytes']:,} bytes")
    
    # Get video info
    info = await agent._get_youtube_info(
        "https://youtube.com/watch?v=dQw4w9WgXcQ"
    )
    
    if info['success']:
        video_info = info['video_info']
        print(f"📹 Title: {video_info['title']}")
        print(f"⏱️ Duration: {video_info['duration']} seconds")
    
    await agent.cleanup_session()
```

### 📚 Knowledge Base Operations ( Direct Approach)
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

### 🔍 Web Search ( Direct Approach)
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

### 🎵 Media Processing ( Direct Approach)
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

### Command Line Examples
```bash
# YouTube Downloads
ambivo-agents youtube download "https://youtube.com/watch?v=dQw4w9WgXcQ" --audio-only
ambivo-agents youtube download "https://youtube.com/watch?v=dQw4w9WgXcQ" --video
ambivo-agents youtube info "https://youtube.com/watch?v=dQw4w9WgXcQ"

# Smart Chat (automatically routes to appropriate agent)
ambivo-agents chat "download audio from https://youtube.com/watch?v=dQw4w9WgXcQ"
ambivo-agents chat "search for latest AI developments"
ambivo-agents chat "extract audio from video.mp4 as high quality mp3"

# Interactive mode with smart routing
ambivo-agents interactive
```

## 🔧 Architecture

### 🌟  Direct Agent Creation
The  paradigm eliminates the service layer and creates agents directly:

```python
# 🌟  Direct creation with explicit context
agent, context = YouTubeDownloadAgent.create(user_id="john")

# Service-based approach
service = create_agent_service()
result = await service.process_message(...)
```

### Agent Capabilities
Each agent provides specialized functionality:

- **YouTube Download Agent** → Video/audio downloads with pytubefix
- **Media Editor Agent** → FFmpeg-based processing
- **Knowledge Base Agent** → Qdrant vector search
- **Web Search Agent** → Multi-provider search
- **Web Scraper Agent** → Proxy-enabled scraping
- **Code Executor Agent** → Docker-based execution

### Memory System
- **Redis-based persistence** with compression and caching
- **Built-in conversation history** for every agent
- **Session-aware context** with automatic cleanup
- **Multi-session support** with isolation

### LLM Provider Management
- **Automatic failover** between OpenAI, Anthropic, AWS Bedrock
- **Rate limiting** and error handling
- **Provider rotation** based on availability and performance

## 🐳 Docker Setup

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

## 🔍 Troubleshooting

### Common Issues

1. **Redis Connection Failed**
   ```bash
   # Check Redis is running
   redis-cli ping
   # Should return "PONG"
   ```

2. **Docker Not Available**
   ```bash
   # Check Docker is running
   docker ps
   # Install if missing: https://docs.docker.com/get-docker/
   ```

3. **Agent Creation Errors**
   ```python
   # Check agent can be created
   from ambivo_agents import YouTubeDownloadAgent
   try:
       agent, context = YouTubeDownloadAgent.create(user_id="test")
       print(f"✅ Success: {context.session_id}")
       await agent.cleanup_session()
   except Exception as e:
       print(f"❌ Error: {e}")
   ```

4. **Import Errors**
   ```bash
   # Ensure clean imports work
   python -c "from ambivo_agents import YouTubeDownloadAgent; print('✅ Import success')"
   ```

### Debug Mode
Enable verbose logging:
```yaml
service:
  log_level: "DEBUG"
  log_to_file: true
```



### Service-Based
```python
from ambivo_agents.services import create_agent_service

service = create_agent_service()
session_id = service.create_session()

result = await service.process_message(
    message="download audio from youtube.com/watch?v=example",
    session_id=session_id,
    user_id="user123"
)
```

### Direct Agent Creation
```python
from ambivo_agents import YouTubeDownloadAgent

agent, context = YouTubeDownloadAgent.create(user_id="user123")

result = await agent._download_youtube_audio(
    "https://youtube.com/watch?v=example"
)

await agent.cleanup_session()
```

### Benefits of Migration
- ✅ **Explicit Context**: Always know your session ID and user context
- ✅ **Direct Control**: No hidden service layer
- ✅ **Better Debugging**: Clear error messages and stack traces
- ✅ **Type Safety**: Direct method calls with proper typing
- ✅ **Performance**: No routing overhead

## 🔐 Security Considerations

- **Docker Isolation**: All code execution happens in isolated containers
- **Network Restrictions**: Containers run with `network_disabled=True` by default
- **Resource Limits**: Memory and CPU limits prevent resource exhaustion  
- **API Key Management**: Store sensitive keys in environment variables
- **Input Sanitization**: All user inputs are validated and sanitized
- **Session Isolation**: Each agent session is completely isolated

## 🤝 Contributing

We welcome contributions! Please see our [Contributing Guidelines](CONTRIBUTING.md) for details.

### Development Setup
```bash
# Clone repository
git clone https://github.com/ambivo-corp/ambivo-agents.git
cd ambivo-agents # project root
# make sure you have ambivo-agents.yaml with the relevant keys/secrets in the project root.

# Install in development mode
pip install -e .


python examples/<example.py>  # Run any example script


```

## 📄 License

MIT License - see [LICENSE](LICENSE) file for details.

## 👨‍💻 Author

**Hemant Gosain 'Sunny'**
- Company: [Ambivo](https://www.ambivo.com)
- Email: sgosain@ambivo.com

## 🆘 Support

- 📧 Email: sgosain@ambivo.com
- 🌐 Website: https://www.ambivo.com
- 📖 Documentation: [Coming Soon]
- 🐛 Issues: [GitHub Issues](https://github.com/ambivo-corp/ambivo-agents.git)

---

*Built with 🛡️ by the Ambivo team.