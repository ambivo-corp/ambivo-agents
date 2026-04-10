#!/usr/bin/env python3
"""
Ambivo Agents v2.0.0 — Quickstart

Demonstrates every agent in the framework with minimal setup.
Requires: pip install ambivo-agents + at least one LLM API key configured.
"""

import asyncio

from ambivo_agents import (
    AssistantAgent,
    GatherAgent,
    KnowledgeSynthesisAgent,
    ModeratorAgent,
    WebScraperAgent,
    WebSearchAgent,
)


# ---------------------------------------------------------------------------
# 1. AssistantAgent — General conversation
# ---------------------------------------------------------------------------
async def demo_assistant():
    print("\n" + "=" * 60)
    print("1. AssistantAgent — General Conversation")
    print("=" * 60)

    agent = AssistantAgent.create_simple(user_id="demo")
    response = await agent.chat("Explain quantum computing in 3 sentences.")
    print(response)
    await agent.cleanup_session()


# ---------------------------------------------------------------------------
# 2. ModeratorAgent — Intelligent routing
# ---------------------------------------------------------------------------
async def demo_moderator():
    print("\n" + "=" * 60)
    print("2. ModeratorAgent — Intelligent Routing")
    print("=" * 60)

    agent = ModeratorAgent.create_simple(user_id="demo")

    # The moderator auto-routes each query to the best agent
    queries = [
        "What is machine learning?",           # -> AssistantAgent
        "Search the web for latest AI news",   # -> WebSearchAgent
    ]
    for q in queries:
        print(f"\nQuery: {q}")
        response = await agent.chat(q)
        print(f"Response: {response[:200]}...")

    await agent.cleanup_session()


# ---------------------------------------------------------------------------
# 3. WebSearchAgent — Web search via Brave/AVES APIs
# ---------------------------------------------------------------------------
async def demo_web_search():
    print("\n" + "=" * 60)
    print("3. WebSearchAgent — API-Based Web Search")
    print("=" * 60)

    try:
        agent = WebSearchAgent.create_simple(user_id="demo")
        response = await agent.chat("Search for recent advances in renewable energy")
        print(response[:500])
        await agent.cleanup_session()
    except RuntimeError as e:
        print(f"Skipped (no search API key configured): {e}")


# ---------------------------------------------------------------------------
# 4. WebScraperAgent — Content extraction via Jina/Firecrawl/requests
# ---------------------------------------------------------------------------
async def demo_web_scraper():
    print("\n" + "=" * 60)
    print("4. WebScraperAgent — API-Based Web Scraping")
    print("=" * 60)

    agent = WebScraperAgent.create_simple(user_id="demo")
    response = await agent.chat("Scrape https://example.com")
    print(response[:500])
    await agent.cleanup_session()


# ---------------------------------------------------------------------------
# 5. KnowledgeSynthesisAgent — Multi-source research with quality gates
# ---------------------------------------------------------------------------
async def demo_knowledge_synthesis():
    print("\n" + "=" * 60)
    print("5. KnowledgeSynthesisAgent — Quality-Gated Research")
    print("=" * 60)

    try:
        agent = KnowledgeSynthesisAgent.create_simple(user_id="demo")
        # This agent searches web + scrapes pages + checks quality + refines
        response = await agent.chat(
            "What are the main challenges in quantum error correction?"
        )
        print(response[:500])
        await agent.cleanup_session()
    except Exception as e:
        print(f"Skipped: {e}")


# ---------------------------------------------------------------------------
# 6. GatherAgent — Conversational form filling
# ---------------------------------------------------------------------------
async def demo_gather():
    print("\n" + "=" * 60)
    print("6. GatherAgent — Conversational Forms")
    print("=" * 60)

    import json

    questionnaire = {
        "questions": [
            {
                "question_id": "name",
                "text": "What is your name?",
                "type": "free-text",
                "required": True,
            },
            {
                "question_id": "role",
                "text": "What is your role?",
                "type": "single-select",
                "required": True,
                "answer_option_dict_list": [
                    {"value": "developer", "label": "Developer"},
                    {"value": "manager", "label": "Manager"},
                    {"value": "designer", "label": "Designer"},
                ],
            },
        ]
    }

    agent = GatherAgent.create_advanced(
        agent_id="gather_demo",
        memory_manager=None,
        llm_service=None,
        config={
            "gather": {
                "submission_endpoint": None,
                "submission_method": "POST",
                "submission_headers": {},
                "memory_ttl_seconds": 3600,
            }
        },
    )

    # Simulate a conversation
    r1 = await agent.chat(json.dumps(questionnaire))
    print(f"Agent: {r1}")

    r2 = await agent.chat("Alice")
    print(f"Agent: {r2}")

    r3 = await agent.chat("Developer")
    print(f"Agent: {r3}")


# ---------------------------------------------------------------------------
# 7. KnowledgeBaseAgent — Document ingestion & semantic search
# ---------------------------------------------------------------------------
async def demo_knowledge_base():
    print("\n" + "=" * 60)
    print("7. KnowledgeBaseAgent — Semantic Search (requires Qdrant)")
    print("=" * 60)

    try:
        from ambivo_agents import KnowledgeBaseAgent

        agent = KnowledgeBaseAgent.create_simple(user_id="demo")
        response = await agent.chat("List available knowledge bases")
        print(response[:300])
        await agent.cleanup_session()
    except Exception as e:
        print(f"Skipped (requires Qdrant + knowledge extras): {e}")


# ---------------------------------------------------------------------------
# Run all demos
# ---------------------------------------------------------------------------
async def main():
    print("Ambivo Agents v2.0.0 — Quickstart Demo")
    print("=" * 60)

    demos = [
        ("AssistantAgent", demo_assistant),
        ("ModeratorAgent", demo_moderator),
        ("WebSearchAgent", demo_web_search),
        ("WebScraperAgent", demo_web_scraper),
        ("KnowledgeSynthesis", demo_knowledge_synthesis),
        ("GatherAgent", demo_gather),
        ("KnowledgeBaseAgent", demo_knowledge_base),
    ]

    for name, demo_fn in demos:
        try:
            await demo_fn()
        except Exception as e:
            print(f"\n[{name}] Error: {e}")

    print("\n" + "=" * 60)
    print("All demos complete.")


if __name__ == "__main__":
    asyncio.run(main())
