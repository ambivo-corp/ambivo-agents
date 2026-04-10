# Ambivo Agents v2.0.0

A lightweight AI agent framework for research synthesis with quality-gated multi-source knowledge gathering.

## What's Different

v2.0.0 is a focused rewrite. We removed 7 commodity agents and their heavy dependencies (Docker, Redis, Playwright) to focus on what's actually unique: **quality-gated knowledge synthesis** — iteratively consulting multiple sources, assessing response quality, and refining until a threshold is met.

| Metric | v1.x | v2.0.0 |
|--------|------|--------|
| Agents | 14 | 7 |
| Core deps | 12 (redis, docker, lz4...) | 9 (httpx, bs4, openai...) |
| Requires Redis | Yes | No (in-memory default) |
| Requires Docker | Yes (5 agents) | No |
| Requires Playwright | Yes (400MB browsers) | No (API-based scraping) |

## Quick Start

```bash
pip install ambivo-agents
```

```python
from ambivo_agents import AssistantAgent

agent = AssistantAgent.create_simple(user_id="demo")
response = await agent.chat("What is quantum computing?")
print(response)
await agent.cleanup_session()
```

No Redis. No Docker. No config files. Just works.

## Available Agents

| Agent | Purpose |
|-------|---------|
| **AssistantAgent** | General conversation and explanations |
| **ModeratorAgent** | Intelligent query routing to specialized agents |
| **KnowledgeSynthesisAgent** | Multi-source research with quality assessment loops |
| **WebSearchAgent** | Web search via Brave/AVES APIs |
| **WebScraperAgent** | Content extraction via Jina Reader/Firecrawl/requests+bs4 |
| **KnowledgeBaseAgent** | Document ingestion and semantic search (Qdrant + LlamaIndex) |
| **GatherAgent** | Conversational form filling with conditional logic |

## Core Differentiator: Quality-Gated Synthesis

```python
from ambivo_agents import KnowledgeSynthesisAgent

agent = KnowledgeSynthesisAgent.create_simple(user_id="researcher")
# Automatically: searches web -> scrapes pages -> queries KB -> assesses quality -> refines
response = await agent.chat("What are the latest advances in quantum error correction?")
```

The synthesis pipeline:
1. Analyzes query to select search strategy
2. Searches web (Brave API) + scrapes relevant pages (Jina Reader API)
3. Queries knowledge base if available
4. Assesses response quality (POOR/FAIR/GOOD/EXCELLENT)
5. If below threshold, gathers more sources and refines
6. Returns synthesized answer with confidence assessment

## Configuration

### Minimal (environment variables only)

```bash
# Required: at least one LLM provider
export AMBIVO_AGENTS_OPENAI_API_KEY="sk-..."
# or
export AMBIVO_AGENTS_ANTHROPIC_API_KEY="sk-ant-..."

# Optional: web search
export AMBIVO_AGENTS_BRAVE_API_KEY="..."

# Optional: scraping API (free Jina Reader works without key)
export AMBIVO_AGENTS_JINA_API_KEY="..."
export AMBIVO_AGENTS_FIRECRAWL_API_KEY="..."
```

### YAML config (agent_config.yaml)

```yaml
llm:
  preferred_provider: "anthropic"
  anthropic_api_key: "sk-ant-..."

agent_capabilities:
  enable_web_search: true
  enable_web_scraping: true
  enable_knowledge_base: false  # requires Qdrant

web_search:
  brave_api_key: "..."

web_scraping:
  scraping:
    provider: "jina"  # jina | firecrawl | requests
    jina_api_key: null  # optional, for higher rate limits
```

## Memory System

Default: **in-memory** (zero infrastructure). For distributed deployments:

```bash
pip install ambivo-agents[redis]
```

```bash
export AMBIVO_AGENTS_REDIS_HOST="localhost"
```

The framework automatically uses Redis when available, falls back to in-memory.

## Optional Extras

```bash
pip install ambivo-agents[redis]       # Distributed memory (Redis + lz4)
pip install ambivo-agents[aws]         # AWS Bedrock LLM support
pip install ambivo-agents[knowledge]   # Knowledge base (Qdrant + LlamaIndex, Python 3.11-3.12)
pip install ambivo-agents[documents]   # Document processing (PDF, DOCX, PPTX)
pip install ambivo-agents[async]       # Async utilities (aiohttp, aiofiles)
pip install ambivo-agents[full]        # All runtime extras
pip install ambivo-agents[all-ml]      # Everything including knowledge base
```

## Agent Creation Patterns

```python
# Simple (recommended)
agent = AssistantAgent.create_simple(user_id="user123")
response = await agent.chat("Hello!")
await agent.cleanup_session()

# With explicit context
agent, context = AssistantAgent.create(user_id="user123")
print(f"Session: {context.session_id}")

# ModeratorAgent auto-routes to the right agent
moderator = ModeratorAgent.create_simple(user_id="user123")
response = await moderator.chat("Search for AI news")  # -> WebSearchAgent
response = await moderator.chat("Scrape https://example.com")  # -> WebScraperAgent
```

## Web Scraping (API-Based)

No browsers, no Docker. Uses HTTP APIs:

| Provider | Cost | JS Support | Default |
|----------|------|-----------|---------|
| Jina Reader | Free tier | Yes | Yes |
| Firecrawl | Paid | Yes | No |
| requests+bs4 | Free | No | Fallback |

```python
from ambivo_agents import WebScraperAgent

scraper = WebScraperAgent.create_simple(user_id="demo")
response = await scraper.chat("scrape https://example.com")
```

## Migration from v1.x

### Removed agents (use alternatives)

| v1.x Agent | Alternative |
|-----------|-------------|
| CodeExecutorAgent | OpenAI code_interpreter, E2B |
| MediaEditorAgent | Direct FFmpeg, external service |
| YouTubeDownloadAgent | yt-dlp directly |
| DatabaseAgent | Direct DB drivers |
| AnalyticsAgent | pandas/DuckDB directly |
| APIAgent | LLM tool calling |
| WorkflowDeveloperAgent | Direct workflow API |

### Breaking changes

- `redis` and `docker` removed from core dependencies
- `create_redis_memory_manager()` still works but `create_memory_manager()` is preferred
- `InMemoryMemoryManager` is the new default when Redis is unavailable
- WebScraperAgent uses HTTP APIs instead of Playwright/Docker
- Many environment variables renamed/removed (see Configuration section)

## Development

```bash
# Install dev dependencies
pip install -e ".[dev]"

# Run tests
pytest tests/ -v

# Format code
black ambivo_agents/ --line-length=100
isort ambivo_agents/ --profile black --line-length=100
```

## License

MIT License - See LICENSE file for details.
