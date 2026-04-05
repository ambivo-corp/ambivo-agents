# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Git Commit Rules

- NEVER include "Claude", "Anthropic", "AI-generated", "AI-assisted", or any similar attribution in commit messages, branch names, PR titles, PR descriptions, or code comments.
- Write commit messages as if a human developer authored the changes.
- Do not add "Co-authored-by" trailers referencing Claude or Anthropic.
- Do not mention AI tooling in any git metadata.

## Development Commands

### Testing
```bash
# Run all tests
pytest tests/

# Run tests with specific markers
pytest tests/ -m "integration" 
pytest tests/ -m "real_api"
pytest tests/ -m "redis"

# Run tests with verbose output and short traceback
pytest tests/ -v -s --tb=short --timeout=300

# Run specific test file
pytest tests/test_basic.py -v
```

### Code Quality
```bash
# Format code with black
black ambivo_agents/ --line-length=100

# Sort imports
isort ambivo_agents/ --profile black --line-length=100

# Lint core package (strict)
flake8 ambivo_agents/ --count --select=E9,F63,F7,F82 --show-source --statistics

# Lint examples (lenient) 
flake8 examples/ --count --exit-zero --max-complexity=10 --max-line-length=127 --statistics
```

### Package Management
```bash
# Install in development mode (all deps including dev tools)
pip install -r requirements.txt

# Install base only
pip install -e .

# Install with specific extras
pip install -e ".[web]"        # Web capabilities (APIAgent, WebScraperAgent)
pip install -e ".[media]"      # Media processing (YouTubeDownloadAgent)
pip install -e ".[knowledge]"  # Knowledge base (LlamaIndex, Qdrant, LangChain)
pip install -e ".[aws]"        # AWS Bedrock LLM support (boto3, langchain-aws)
pip install -e ".[database]"   # Database support (DatabaseAgent)
pip install -e ".[documents]"  # Document processing (PDF, DOCX, PPTX, unstructured)
pip install -e ".[analytics]"  # Data analytics (AnalyticsAgent - pandas)
pip install -e ".[async]"      # Async utilities (aiohttp, aiofiles, aiosqlite)
pip install -e ".[full]"       # All runtime extras (Python 3.11-3.13)
pip install -e ".[all]"        # Everything including dev tools (Python 3.11-3.13)
pip install -e ".[all-ml]"    # Full + knowledge base (Python 3.11-3.12 only)
pip install -e ".[test]"       # Testing dependencies only
```

### CLI Usage
```bash
# Interactive mode
ambivo-agents

# Single query
ambivo-agents -q "Your question here"

# Check agent status
ambivo-agents status

# Test all agents
ambivo-agents --test

# Debug mode
ambivo-agents --debug -q "test query"
```

## Architecture Overview

### Core Components

**BaseAgent** (`ambivo_agents/core/base.py`):
- Foundation class for all agents with auto-context session management
- Provides `.create()`, `.create_simple()`, and `.create_advanced()` factory methods
- Built-in `chat()` and `chat_sync()` methods for easy interaction
- Automatic memory and LLM service integration
- Session cleanup and resource management

**ModeratorAgent** (`ambivo_agents/agents/moderator.py`):
- Intelligent orchestrator that routes queries to specialized agents
- Auto-routing based on intent analysis using both LLM and keyword patterns
- Maintains conversation context across agent switches
- Supports workflow execution and multi-agent coordination
- Primary entry point for most use cases

**Memory System** (`ambivo_agents/core/memory.py`):
- Redis-based persistent conversation history
- Compression using LZ4 for efficient storage
- Session-aware context management with automatic cleanup
- Shared memory across all agents in a session

**LLM Service** (`ambivo_agents/core/llm.py`):
- Multi-provider support: OpenAI, Anthropic, AWS Bedrock
- Automatic failover and provider rotation
- Rate limiting and error handling
- Provider tracking and availability management

### Agent Architecture

All agents inherit from `BaseAgent` and implement:
- `process_message()`: Core message processing logic
- `process_message_stream()`: Streaming response support
- Agent-specific functionality while maintaining consistent interface

**Specialized Agents**:
- **AssistantAgent**: General conversation and explanations
- **CodeExecutorAgent**: Secure Python/Bash execution in Docker
- **WebSearchAgent**: Multi-provider web search (Brave, AVES)
- **KnowledgeBaseAgent**: Document ingestion and semantic search with Qdrant
- **MediaEditorAgent**: FFmpeg-based audio/video processing
- **YouTubeDownloadAgent**: YouTube content downloading via Docker
- **WebScraperAgent**: Website data extraction with proxy support

### Configuration System

**Primary Configuration** (`agent_config.yaml`):
- Centralized YAML-based configuration for all components
- Auto-loaded by agents when using `auto_configure=True`
- Supports environment variable substitution
- Alternative: Environment variables with `AMBIVO_AGENTS_` prefix

**Configuration Sections**:
- `redis`: Redis connection settings for memory management
- `llm`: LLM provider configurations and API keys
- `agent_capabilities`: Enable/disable specific agent features
- `knowledge_base`: Qdrant vector database settings
- `web_search`: Search provider API keys and settings
- `docker`: Container execution parameters
- Service-specific configurations for each agent type

### Workflow System

**Basic Workflows** (`ambivo_agents/core/workflow.py`):
- Agent-to-agent workflow orchestration
- Sequential and parallel execution patterns
- Built-in patterns for common multi-agent tasks

**Enhanced Workflows** (`ambivo_agents/core/enhanced_workflow.py`):
- Advanced workflow patterns: consensus, debate, map-reduce
- Natural language workflow triggers
- Stateful execution with persistent checkpoints
- Error recovery and fallback mechanisms

**Common Workflow Patterns**:
- Search → Scrape → Ingest: Web research into knowledge base
- Download → Process: YouTube content to processed media
- Consensus: Multiple agents reach agreement
- Debate: Structured multi-agent discussions

### Session Management

**Auto-Context System**:
- Every agent automatically gets session context (session_id, user_id, etc.)
- Shared memory and conversation history across all agents in a session
- Consistent session IDs for proper context preservation

**Context Hierarchy**:
- `session_id`: Broader user session or application context
- `conversation_id`: Specific conversation thread within session
- Multiple conversations can exist within one session

**Resource Cleanup**:
- `await agent.cleanup_session()`: Cleanup agent resources
- `AgentSession` context manager: Automatic cleanup
- Proper executor shutdown and memory clearing

### Docker Integration

**Secure Execution**:
- All code execution happens in isolated Docker containers
- Default image: `sgosain/amb-ubuntu-python-public-pod`
- Network isolation, memory limits, and timeout controls
- Automatic container cleanup after execution

**Usage in Agents**:
- CodeExecutorAgent: Python/Bash script execution
- YouTubeDownloadAgent: pytubefix-based downloads
- MediaEditorAgent: FFmpeg media processing
- WebScraperAgent: Playwright-based scraping

### File Operations (Available to All Agents)

**BaseAgent File Capabilities**:
All agents inherit comprehensive file operations from the BaseAgent class:

**File Reading**:
- Local files: `await agent.read_file("path/to/file.txt")`
- Remote URLs: `await agent.read_file("https://example.com/data.json")`
- Supports: TXT, JSON, CSV, XML, YAML files
- Automatic encoding detection and binary file handling
- Multiple path resolution strategies for local files

**File Parsing**:
- `await agent.parse_file_content(content, file_type)` - Parse content by type
- JSON: Returns structured data with metadata
- CSV: Returns list of dictionaries with column info
- XML: Converts to nested dictionary structure
- YAML: Full YAML parsing support
- Text: Returns content with line/character counts

**Format Conversion**:
- JSON ↔ CSV: `await agent.convert_json_to_csv(data)` / `await agent.convert_csv_to_json(csv_data)`
- Automatic type inference for CSV to JSON conversion
- Handles nested structures and arrays
- Preserves data types (strings, numbers, nulls)

**Combined Operations**:
- `await agent.read_and_parse_file("file.json")` - Read and parse in one call
- Returns both raw content and parsed data
- Automatic format detection from file extension

**Usage Examples**:
```python
# Read and parse a data file
agent = AssistantAgent.create_simple(user_id="user123")

# Local file
result = await agent.read_and_parse_file("data/users.csv")
if result['success'] and result['parsed']:
    data = result['parse_result']['data']  # List of user dictionaries
    
# Remote file
result = await agent.read_file("https://api.example.com/data.json")
if result['success']:
    parsed = await agent.parse_file_content(result['content'], 'json')
    
# Convert formats
csv_result = await agent.convert_json_to_csv(json_data)
json_result = await agent.convert_csv_to_json(csv_content)

await agent.cleanup_session()
```

**Dependencies**:
- Core functionality works with standard library
- Enhanced features require: `aiohttp`, `aiofiles`, `PyYAML`
- Graceful fallbacks when optional dependencies missing

## Development Patterns

### Agent Creation Patterns

**Recommended (with context)**:
```python
# Returns both agent and context for explicit handling
agent, context = KnowledgeBaseAgent.create(user_id="user123")
print(f"Session: {context.session_id}")
response = await agent.chat("Your question")
await agent.cleanup_session()
```

**Simple (context auto-managed)**:
```python
# Agent manages context internally
agent = KnowledgeBaseAgent.create_simple(user_id="user123")
response = await agent.chat("Your question")
await agent.cleanup_session()
```

**Advanced (explicit dependencies)**:
```python
# Full control over dependencies
memory = create_redis_memory_manager("agent_id")
llm = create_multi_provider_llm_service()
agent = KnowledgeBaseAgent.create_advanced("agent_id", memory, llm)
```

### ModeratorAgent Usage

**Primary Recommended Pattern**:
```python
# ModeratorAgent with auto-routing
moderator, context = ModeratorAgent.create(user_id="user123")

# Automatically routes to appropriate agent
response = await moderator.chat("Download audio from https://youtube.com/...")
response = await moderator.chat("Search for AI news")
response = await moderator.chat("What is machine learning?")

await moderator.cleanup_session()
```

### AnalyticsAgent Configuration and Usage

**Basic Data Analysis**:
```python
# Simple analytics with auto-configuration
agent = AnalyticsAgent.create_simple(user_id="user123")

# Load and analyze data
response = await agent.chat("load data from sample.csv and analyze it")
response = await agent.chat("show schema") 
response = await agent.chat("what are the top 10 sales by revenue?")

await agent.cleanup_session()
```

**Configuration via agent_config.yaml**:
```yaml
analytics:
  # Data Processing Settings
  input_dir: "./docker_shared/input/analytics"  # Default directory for data files
  output_dir: "./docker_shared/output/analytics"  # Output directory for results
  temp_dir: "/tmp/analytics"                 # Temporary files directory
  
  # Docker Configuration  
  docker_image: "sgosain/amb-ubuntu-python-public-pod"
  work_dir: "/opt/ambivo/work_dir"
  timeout: 120                               # Processing timeout (2 minutes)
  memory_limit: "2g"                         # Docker memory limit
  
  # File Processing Limits
  max_file_size_mb: 100                      # Maximum file size
  supported_file_types:
    - ".csv"
    - ".xlsx" 
    - ".xls"
    - ".json"
    - ".parquet"
  
  # Analysis Settings
  max_rows_preview: 1000                     # Max rows for data preview
  enable_visualizations: true                # Enable chart recommendations
  enable_sql_queries: true                   # Enable SQL query generation
```

**Usage Examples**:
- `"load data from sales.csv and analyze it"` - Loads and provides file summary
- `"show schema"` - Displays data structure and types
- `"what are the top 10 products by revenue?"` - Natural language queries
- `"create a bar chart of sales by region"` - Visualization requests

**File Path Resolution**:
- Relative paths (e.g., `sample.csv`) are resolved against docker_shared structure:
  1. `docker_shared/input/analytics/` (highest priority)
  2. `docker_shared/handoff/analytics/` (for workflow handoffs)
  3. Current working directory
  4. Legacy fallback: `docker_shared/input/` and `docker_shared/`
- Absolute paths are used as-is if they exist
- The agent lists available files when no path is specified

### APIAgent Usage and Security Configuration

**Basic API Calls**:
```python
# Simple API call with natural language
agent = APIAgent.create_simple(user_id="user123")

# Natural language parsing (recommended)
response = await agent.chat("call this API POST api.example.com/users with Bearer token abc123")

# Direct API request
from ambivo_agents.agents.api_agent import APIRequest, HTTPMethod, AuthConfig, AuthType
request = APIRequest(
    url="https://api.example.com/users",
    method=HTTPMethod.POST,
    auth_config=AuthConfig(auth_type=AuthType.BEARER, token="abc123"),
    timeout=8  # Use safe timeout
)
response = await agent.make_api_request(request)
```

**Security Configuration**:

The APIAgent has configurable security settings to control which domains and HTTP methods are allowed:

**Default Behavior** (most permissive):
- `allowed_domains = None` → Allows ALL domains except those in blocked list
- `blocked_domains = ["localhost", "127.0.0.1", "0.0.0.0"]` → Blocks local network access

**Configuration via agent_config.yaml**:
```yaml
api_agent:
  # Option 1: Allow all domains except blocked ones (recommended for most use cases)
  allowed_domains: null  # or omit this line entirely
  blocked_domains:
    - "localhost"
    - "127.0.0.1" 
    - "0.0.0.0"
    - "169.254.169.254"  # AWS metadata service
    - "internal.company.com"  # Add your internal domains
  
  # Option 2: Restrict to specific allowed domains (more secure)
  allowed_domains:
    - "api.example.com"
    - "*.googleapis.com"  # Wildcards supported
    - "*.github.com"
    - "your-api.ambivo.com"
  blocked_domains:
    - "localhost"
    - "127.0.0.1"
    - "0.0.0.0"
  
  # HTTP Method restrictions
  allowed_methods:
    - "GET"
    - "POST" 
    - "PUT"
    - "PATCH"
    - "DELETE"
  blocked_methods: []  # Block specific methods if needed
  
  # Security options
  verify_ssl: true
  timeout_seconds: 30
  max_safe_timeout: 8  # Requests exceeding this use Docker for safety
  force_docker_above_timeout: true
```

**Security Best Practices**:
1. **Default Configuration**: Use `allowed_domains: null` to allow all external domains while blocking localhost access
2. **Restricted Environments**: Set specific `allowed_domains` list for production environments
3. **Timeouts**: Keep `max_safe_timeout: 8` to prevent long-running requests outside Docker
4. **SSL Verification**: Always keep `verify_ssl: true` in production
5. **Method Restrictions**: Use `blocked_methods` to disable dangerous HTTP methods if needed

**Environment Variable Override**:
```bash
# Alternative to YAML configuration
export AMBIVO_AGENTS_API_AGENT_ALLOWED_DOMAINS="api.example.com,*.safe-domain.com"
export AMBIVO_AGENTS_API_AGENT_BLOCKED_DOMAINS="localhost,127.0.0.1,internal.company.com"
```

### Memory and Context

**Conversation History**:
```python
# Get conversation history
history = await agent.get_conversation_history(limit=10)

# Add to conversation manually
await agent.add_to_conversation_history("message", "user")

# Clear conversation
await agent.clear_conversation_history()
```

**Session Context**:
```python
# Access agent context
context = agent.get_context()
print(f"Session: {context.session_id}")
print(f"User: {context.user_id}")

# Update context metadata
agent.update_context_metadata(key="value")
```

### Configuration Access

**Loading Configuration**:
```python
from ambivo_agents.config.loader import load_config
config = load_config()  # Loads from agent_config.yaml
```

**Environment Variables**:
```bash
# Alternative to YAML configuration
export AMBIVO_AGENTS_REDIS_HOST="redis-host"
export AMBIVO_AGENTS_OPENAI_API_KEY="sk-..."
export AMBIVO_AGENTS_ENABLE_WEB_SEARCH="true"
```

## Important Implementation Notes

### Error Handling
- All agents include comprehensive error handling and fallback mechanisms
- ModeratorAgent automatically falls back to AssistantAgent when specialist agents fail
- Docker execution includes timeout and resource limit protection

### Memory Consistency
- All agents in a session share the same Redis memory instance
- Session IDs must be consistent across agents for proper context preservation
- ModeratorAgent automatically synchronizes context across specialized agents

### System Messages
- Each agent has role-specific default system messages
- Custom system messages can be provided during agent creation
- System messages integrate with conversation history for context-aware responses

### Security Considerations
- Docker containers run with network isolation and resource limits
- API keys managed through configuration files, not hardcoded
- Input sanitization and validation throughout the system
- Session isolation prevents cross-user data leakage

### Performance
- Redis compression reduces memory usage
- LLM provider failover ensures service availability
- Agent initialization is optimized for quick startup
- Connection pooling for external services

## Testing Strategy

The repository uses pytest with several test categories:
- **Unit Tests**: Individual component testing
- **Integration Tests**: Real API integration with services
- **Performance Tests**: Benchmark critical operations
- **End-to-End Tests**: Complete workflow validation

Tests are configured in `tests/pytest.ini` with markers for different test types, async support, and proper timeout handling.