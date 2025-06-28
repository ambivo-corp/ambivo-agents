#!/usr/bin/env python3
"""
Simple One-Liner Examples with the  .create() Pattern
The absolute simplest way to get started with Ambivo Agents
"""

import asyncio
from ambivo_agents import KnowledgeBaseAgent, WebSearchAgent, YouTubeDownloadAgent


# 🌟 ONE-LINER KNOWLEDGE BASE
async def oneliner_knowledge_base():
    """One-liner knowledge base example"""
    print("📚 One-Liner Knowledge Base")
    print("=" * 30)

    # 🎯 ONE LINE: Create agent with context
    agent, context = KnowledgeBaseAgent.create(user_id="john")

    print(f"✅ Created agent {agent.agent_id} for user {context.user_id}")
    print(f"📋 Session: {context.session_id}")

    # Use the agent
    result = await agent._ingest_text(
        kb_name="ambivo_demo_kb",
        input_text="Ambivo is an AI company that builds intelligent automation platforms.",
        custom_meta={"source": "company_info"}
    )

    if result['success']:
        print("✅ Text ingested")

        # Query it
        answer = await agent._query_knowledge_base(
            kb_name="ambivo_demo_kb",
            query="What does Ambivo do?"
        )

        if answer['success']:
            print(f"💬 Answer: {answer['answer']}")

    await agent.cleanup_session()


# 🌟 ONE-LINER WEB SEARCH
async def oneliner_web_search():
    """One-liner web search example"""
    print("\n🔍 One-Liner Web Search")
    print("=" * 25)

    # 🎯 ONE LINE: Create agent with context
    agent, context = WebSearchAgent.create(user_id="sarah")

    print(f"✅ Created search agent for user {context.user_id}")

    # Search the web
    try:
        result = await agent._search_web("What is artificial intelligence?", max_results=3)

        if result['success']:
            print(f"🔍 Found {len(result['results'])} results")
            if result['results']:
                first_result = result['results'][0]
                print(f"📄 Top result: {first_result.get('title', 'No title')}")
    except Exception as e:
        print(f"❌ Search failed: {e}")

    await agent.cleanup_session()


# 🌟 ONE-LINER YOUTUBE DOWNLOAD
async def oneliner_youtube():
    """One-liner YouTube download example"""
    print("\n🎬 One-Liner YouTube Download")
    print("=" * 30)

    # 🎯 ONE LINE: Create agent with context
    agent, context = YouTubeDownloadAgent.create(user_id="mike")

    print(f"✅ Created YouTube agent for user {context.user_id}")

    # Get video info (safer than downloading)
    test_url = "https://www.youtube.com/watch?v=C0DPdy98e4c"  # Big Buck Bunny

    try:
        result = await agent._get_youtube_info(test_url)

        if result['success']:
            video_info = result['video_info']
            print(f"📹 Video: {video_info.get('title', 'Unknown')}")
            print(f"⏱️  Duration: {video_info.get('duration', 'Unknown')} seconds")
    except Exception as e:
        print(f"❌ YouTube info failed: {e}")

    await agent.cleanup_session()


# 🌟 SIMPLEST POSSIBLE EXAMPLE
async def absolute_simplest():
    """The absolute simplest example possible"""
    print("\n⭐ ABSOLUTE SIMPLEST EXAMPLE")
    print("=" * 30)

    # 🎯 Two lines: Create and use
    agent, context = KnowledgeBaseAgent.create(user_id="demo_user")
    print(f"Agent {agent.agent_id} ready for user {context.user_id} in session {context.session_id}")

    await agent.cleanup_session()


# 🌟 CONTEXT-AWARE EXAMPLE
async def context_aware_example():
    """Example showing context awareness"""
    print("\n🧠 Context-Aware Example")
    print("=" * 25)

    # Create with custom metadata
    agent, context = KnowledgeBaseAgent.create(
        user_id="context_user",
        tenant_id="my_company",
        session_metadata={"project": "demo", "version": "1.0"}
    )

    print(f"✅ Agent: {agent.agent_id}")
    print(f"👤 User: {context.user_id}")
    print(f"🏢 Tenant: {context.tenant_id}")
    print(f"📋 Session: {context.session_id}")
    print(f"🏷️  Metadata: {context.metadata}")

    # Add some conversation history
    await agent.add_to_conversation_history("Hello from the demo", "user")
    await agent.add_to_conversation_history("Hi! I'm ready to help", "agent")

    # Get conversation summary
    summary = await agent.get_conversation_summary()
    print(f"💬 Total messages: {summary['total_messages']}")
    print(f"⏱️  Session duration: {summary['session_duration']}")

    await agent.cleanup_session()


async def main():
    """Run all simple examples"""
    print("🌟 SIMPLE ONE-LINER EXAMPLES WITH .create()")
    print("=" * 50)
    print("These show the EASIEST way to get started with Ambivo Agents")
    print("Every agent now returns (agent, context) with .create()")
    print("=" * 50)

    await oneliner_knowledge_base()
    await oneliner_web_search()
    await oneliner_youtube()
    await absolute_simplest()
    await context_aware_example()

    print(f"\n🎉 All Simple Examples Completed!")
    print(f"\n💡 Remember the pattern:")
    print(f"   agent, context = AnyAgent.create(user_id='your_user')")
    print(f"   # Use agent...")
    print(f"   await agent.cleanup_session()")
    print(f"\n✨ Context gives you session_id, user_id, conversation history, and more!")


if __name__ == "__main__":
    asyncio.run(main())