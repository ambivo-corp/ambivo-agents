# Ambivo Agents

A lightweight AI agent framework for research synthesis with quality-gated multi-source knowledge gathering.

[![PyPI version](https://img.shields.io/pypi/v/ambivo-agents.svg)](https://pypi.org/project/ambivo-agents/)
[![Python](https://img.shields.io/pypi/pyversions/ambivo-agents.svg)](https://pypi.org/project/ambivo-agents/)

## Why v2.x

v2 is a focused rewrite. We cut commodity agents and their heavy dependencies (Docker, Redis, Playwright) to focus on what's actually unique: **quality-gated knowledge synthesis** — iteratively consulting multiple sources, assessing response quality, and refining until a threshold is met.

| Metric | v1.x | v2.x |
|--------|------|------|
| Agents | 14 | 7 |
| Core dependencies | 12 | 9 |
| Requires Redis | Yes | No (in-memory default) |
| Requires Docker | Yes | No |
| Requires Playwright | Yes (~400 MB browsers) | No (API-based scraping) |
| Install size | ~500 MB | ~15 MB |

## Quick Start

```bash
pip install ambivo-agents
```

```python
import asyncio
from ambivo_agents import AssistantAgent

async def main():
    agent = AssistantAgent.create_simple(user_id="demo")
    response = await agent.chat("Explain quantum computing in 3 sentences.")
    print(response)
    await agent.cleanup_session()

asyncio.run(main())
```

No Redis. No Docker. No config file. Just works.

## Available Agents

| Agent | Purpose |
|-------|---------|
| `AssistantAgent` | General conversation and explanations |
| `ModeratorAgent` | Intelligent query routing to specialized agents |
| `KnowledgeSynthesisAgent` | Multi-source research with quality assessment loops |
| `WebSearchAgent` | Web search via Brave/AVES APIs |
| `WebScraperAgent` | Content extraction via Jina Reader / Firecrawl / requests+bs4 |
| `KnowledgeBaseAgent` | Document ingestion and semantic search (Qdrant) |
| `GatherAgent` | Conversational form filling with conditional logic |

## Minimal Configuration

The only **required** variable is one LLM provider API key. Everything else has sensible defaults.

```bash
# Required — at least one
export AMBIVO_AGENTS_OPENAI_API_KEY="sk-..."
export AMBIVO_AGENTS_ANTHROPIC_API_KEY="sk-ant-..."
```

That's it. You can now create any agent and call `.chat()`.

### Optional: Enable web search and scraping

```bash
# Web search (optional — enables WebSearchAgent)
export AMBIVO_AGENTS_BRAVE_API_KEY="..."
export AMBIVO_AGENTS_ENABLE_WEB_SEARCH="true"

# Web scraping (optional — Jina Reader works without a key)
export AMBIVO_AGENTS_ENABLE_WEB_SCRAPING="true"
export AMBIVO_AGENTS_JINA_API_KEY="..."        # optional, higher rate limits
export AMBIVO_AGENTS_FIRECRAWL_API_KEY="..."   # optional, premium scraping
```

### Optional: Knowledge base (requires Qdrant)

```bash
pip install ambivo-agents[knowledge]
```

```bash
export AMBIVO_AGENTS_ENABLE_KNOWLEDGE_BASE="true"
export AMBIVO_AGENTS_QDRANT_URL="https://your-cluster.qdrant.tech:6333"
export AMBIVO_AGENTS_QDRANT_API_KEY="..."
```

### Optional: Distributed memory via Redis

```bash
pip install ambivo-agents[redis]
```

```bash
export AMBIVO_AGENTS_REDIS_HOST="localhost"
export AMBIVO_AGENTS_REDIS_PORT="6379"
export AMBIVO_AGENTS_REDIS_PASSWORD=""
```

By default the framework uses an in-memory store. Set Redis variables only for multi-process or distributed deployments.

### YAML config alternative (`agent_config.yaml`)

```yaml
llm:
  preferred_provider: anthropic
  anthropic_api_key: sk-ant-...
  openai_api_key: sk-...

agent_capabilities:
  enable_web_search: true
  enable_web_scraping: true
  enable_knowledge_base: false

web_search:
  brave_api_key: ...

web_scraping:
  scraping:
    provider: jina   # jina | firecrawl | requests
```

## Core Differentiator: Quality-Gated Synthesis

```python
from ambivo_agents import KnowledgeSynthesisAgent

agent = KnowledgeSynthesisAgent.create_simple(user_id="researcher")
response = await agent.chat("What are the latest advances in quantum error correction?")
```

The synthesis pipeline:
1. Analyzes the query to select a search strategy
2. Searches the web (Brave) and scrapes relevant pages (Jina Reader)
3. Queries the knowledge base if available
4. Assesses response quality (POOR → FAIR → GOOD → EXCELLENT)
5. If below threshold, gathers more sources and refines
6. Returns a synthesized answer with a confidence score

No other mainstream agent framework ships this out of the box.

## Agent Creation Patterns

```python
# Simple — recommended
agent = AssistantAgent.create_simple(user_id="user123")
response = await agent.chat("Hello!")
await agent.cleanup_session()

# With explicit context
agent, context = AssistantAgent.create(user_id="user123")
print(f"Session: {context.session_id}")

# ModeratorAgent auto-routes to the best agent
moderator = ModeratorAgent.create_simple(user_id="user123")
response = await moderator.chat("Search for AI news")          # → WebSearchAgent
response = await moderator.chat("Scrape https://example.com")  # → WebScraperAgent
```

## Web Scraping (API-Based)

No browsers, no Docker. Just HTTP APIs with SSRF protection:

| Provider | Cost | JS rendering | Default |
|----------|------|-------------|---------|
| Jina Reader | Free tier | Yes | Yes |
| Firecrawl | Paid | Yes | No |
| requests+bs4 | Free | No | Offline fallback |

```python
from ambivo_agents import WebScraperAgent

scraper = WebScraperAgent.create_simple(user_id="demo")
response = await scraper.chat("scrape https://example.com")
```

All scraped URLs are validated to block SSRF attacks against private IPs, loopback addresses, and cloud metadata services.

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

## All Environment Variables

Only set what you need:

| Variable | Purpose |
|----------|---------|
| `AMBIVO_AGENTS_OPENAI_API_KEY` | OpenAI API key |
| `AMBIVO_AGENTS_ANTHROPIC_API_KEY` | Anthropic API key |
| `AMBIVO_AGENTS_AWS_ACCESS_KEY_ID` | AWS Bedrock access key |
| `AMBIVO_AGENTS_AWS_SECRET_ACCESS_KEY` | AWS Bedrock secret |
| `AMBIVO_AGENTS_AWS_REGION` | AWS region (default: us-east-1) |
| `AMBIVO_AGENTS_LLM_PREFERRED_PROVIDER` | `openai`, `anthropic`, or `bedrock` |
| `AMBIVO_AGENTS_LLM_TEMPERATURE` | LLM temperature (default: 0.5) |
| `AMBIVO_AGENTS_ENABLE_WEB_SEARCH` | Enable WebSearchAgent |
| `AMBIVO_AGENTS_ENABLE_WEB_SCRAPING` | Enable WebScraperAgent |
| `AMBIVO_AGENTS_ENABLE_KNOWLEDGE_BASE` | Enable KnowledgeBaseAgent |
| `AMBIVO_AGENTS_BRAVE_API_KEY` | Brave Search API key |
| `AMBIVO_AGENTS_AVESAPI_API_KEY` | AVES Search API key |
| `AMBIVO_AGENTS_SCRAPING_PROVIDER` | `jina` (default), `firecrawl`, or `requests` |
| `AMBIVO_AGENTS_JINA_API_KEY` | Jina Reader API key (optional) |
| `AMBIVO_AGENTS_FIRECRAWL_API_KEY` | Firecrawl API key (optional) |
| `AMBIVO_AGENTS_QDRANT_URL` | Qdrant vector DB URL |
| `AMBIVO_AGENTS_QDRANT_API_KEY` | Qdrant API key |
| `AMBIVO_AGENTS_REDIS_HOST` | Redis host (optional) |
| `AMBIVO_AGENTS_REDIS_PORT` | Redis port (default: 6379) |
| `AMBIVO_AGENTS_REDIS_PASSWORD` | Redis password |
| `AMBIVO_AGENTS_LOG_LEVEL` | Log level (default: INFO) |

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

MIT License — see [LICENSE](LICENSE) file.
