#!/usr/bin/env python3
"""
Corrected One-Liner Examples - Fixed Event Loop Issues
Demonstrates proper memory retention, context preservation, and system messages
"""

import asyncio
from datetime import datetime
from ambivo_agents import (
    KnowledgeBaseAgent, WebSearchAgent,
    ModeratorAgent, AssistantAgent
)


# =============================================================================
# ASYNC-SAFE ULTRA-SIMPLE EXAMPLES
# =============================================================================

async def ultra_simple_examples():
    """FIXED: Async-safe ultra-simple examples"""
    print("ULTRA-SIMPLE ONE-LINERS")
    print("=" * 30)

    # [OK] FIXED: Use async chat() instead of sync version in async context
    agent = AssistantAgent.create_simple()
    response = await agent.chat("What is Python?")
    print(f"Python explanation: {response[:100]}...")
    await agent.cleanup_session()


    agent = AssistantAgent.create_simple(
        system_message="You are a friendly teacher. Use simple analogies."
    )
    response = await agent.chat("Explain machine learning")
    print(f"ML explanation: {response[:100]}...")
    await agent.cleanup_session()

    print("[OK] Ultra-simple examples completed!\n")


# =============================================================================
# CONTEXT-AWARE EXAMPLES (WORKING VERSION)
# =============================================================================

async def context_aware_examples():
    """[OK] WORKING: Context-aware examples with proper session management"""
    print("CONTEXT-AWARE EXAMPLES")
    print("=" * 30)

    # [OK] BEST PRACTICE: Create with context for session management
    agent, context = AssistantAgent.create(
        user_id="john_doe",
        system_message="You are John's personal AI assistant. Remember our conversation history."
    )

    print(f"[OK] Created agent for {context.user_id} in session {context.session_id}")

    # [OK] Multi-turn conversation demonstrating memory
    response1 = await agent.chat("My name is John and I'm a data scientist")
    print(f"Introduction: {response1[:80]}...")

    response2 = await agent.chat("What's my profession?")  # Should remember from context
    print(f"Memory test: {response2[:80]}...")

    response3 = await agent.chat("Recommend Python libraries for my work")  # Should use both context
    print(f"Contextual advice: {response3[:80]}...")

    # [OK] Show conversation history
    history = await agent.get_conversation_history()
    print(f"Conversation history: {len(history)} messages preserved")

    await agent.cleanup_session()
    print("[OK] Context-aware examples completed!\n")


# =============================================================================
# SPECIALIZED AGENT EXAMPLES (WORKING VERSION)
# =============================================================================

async def specialized_agent_examples():
    """[OK] WORKING: Specialized agents with proper async handling"""
    print("SPECIALIZED AGENT EXAMPLES")
    print("=" * 35)

    # [OK] Knowledge Base with proper error handling
    print("Knowledge Base Example:")
    agent, context = KnowledgeBaseAgent.create(
        user_id="researcher",
        system_message="You are a research assistant. Always cite sources and explain methodology."
    )

    try:
        # [OK] Proper knowledge base workflow
        result = await agent._ingest_text(
            kb_name="ai_research_kb",
            input_text="Artificial Intelligence is transforming industries through machine learning, natural language processing, and computer vision technologies.",
            custom_meta={"source": "research_summary", "date": datetime.now().isoformat()}
        )

        if result['success']:
            print(f"   [OK] Knowledge ingested into {result['kb_name']}")

            # Query with context
            query_result = await agent._query_knowledge_base(
                kb_name="ai_research_kb",
                query="What technologies are mentioned in AI research?"
            )

            if query_result['success']:
                print(f"   Query result: {query_result['answer'][:100]}...")
                print(f"   Sources found: {len(query_result.get('source_details', []))}")

    except Exception as e:
        print(f"   [WARN]KB error handled gracefully: {e}")

    finally:
        await agent.cleanup_session()

    # [OK] Web Search with error handling
    print("\nWeb Search Example:")
    agent, context = WebSearchAgent.create(
        user_id="searcher",
        system_message="You are a research specialist. Provide accurate, well-sourced information."
    )

    try:
        result = await agent._search_web("latest AI developments 2024", max_results=3)

        if result['success'] and result['results']:
            print(f"   [OK] Found {len(result['results'])} results")
            print(f"   Top result: {result['results'][0].get('title', 'No title')[:60]}...")
            print(f"   Provider: {result.get('provider', 'Unknown')}")
        else:
            print("   [WARN]No results found or search failed")

    except Exception as e:
        print(f"   [WARN]Search error handled: {e}")

    finally:
        await agent.cleanup_session()

    print("[OK] Specialized agent examples completed!\n")


# =============================================================================
# SYSTEM MESSAGE EXAMPLES (WORKING VERSION)
# =============================================================================

async def system_message_examples():
    """[OK] WORKING: System message examples with different personalities"""
    print("SYSTEM MESSAGE EXAMPLES")
    print("=" * 30)

    # [OK] Different personalities for the same agent type
    personalities = [
        ("Professional",
         "You are a formal business consultant. Use professional language and provide structured advice."),
        ("Casual", "You are a friendly coding buddy. Use casual language and encourage experimentation."),
        ("Academic", "You are a university professor. Provide detailed explanations with theoretical background.")
    ]

    question = "How should I learn Python programming?"

    for name, system_msg in personalities:
        print(f"\n{name} Assistant:")
        agent, context = AssistantAgent.create(
            user_id=f"user_{name.lower()}",
            system_message=system_msg
        )

        response = await agent.chat(question)
        print(f"   Response: {response[:120]}...")

        await agent.cleanup_session()

    print("[OK] System message examples completed!\n")


# =============================================================================
# STREAMING EXAMPLES (FIXED VERSION)
# =============================================================================

async def streaming_examples():
    """FIXED: Streaming examples with proper ModeratorAgent usage"""
    print("STREAMING EXAMPLES")
    print("=" * 25)

    # [OK] FIXED: Don't pass system_message as separate parameter to ModeratorAgent
    agent, context = ModeratorAgent.create(user_id="streamer")

    print("Streaming response: ", end='', flush=True)
    async for chunk in agent.chat_stream("Help me understand how AI agents work"):
        print(chunk, end='', flush=True)
    print()

    # [OK] Follow-up with context preservation
    print("\nFollow-up (with context): ", end='', flush=True)
    async for chunk in agent.chat_stream("Can you give me a practical example?"):
        print(chunk, end='', flush=True)
    print()

    await agent.cleanup_session()
    print("[OK] Streaming examples completed!\n")


# =============================================================================
# ERROR HANDLING EXAMPLES (WORKING VERSION)
# =============================================================================

async def error_handling_examples():
    """[OK] WORKING: Error handling with async safety"""
    print("ERROR HANDLING EXAMPLES")
    print("=" * 30)

    agent, context = AssistantAgent.create(
        user_id="error_tester",
        system_message="You are a resilient assistant that handles any situation gracefully."
    )

    # [OK] Test edge cases with async safety
    test_cases = [
        "",  # Empty input
        "x" * 500,  # Long input (reduced to avoid timeout)
        "" * 50,  # Unicode stress test (reduced)
        "Handle this gracefully"  # Normal case
    ]

    for i, test_input in enumerate(test_cases, 1):
        try:
            print(f"Test {i}: ", end='')

            response = await agent.chat(str(test_input))
            print(f"[OK] Handled successfully: {len(response)} chars")

        except Exception as e:
            print(f"[WARN]Error handled: {type(e).__name__}")

    await agent.cleanup_session()
    print("[OK] Error handling examples completed!\n")


# =============================================================================
# BEST PRACTICES SUMMARY (WORKING VERSION)
# =============================================================================

async def best_practices_summary():
    """[OK] WORKING: Comprehensive best practices demonstration"""
    print("BEST PRACTICES SUMMARY")
    print("=" * 30)

    agent, context = AssistantAgent.create(
        user_id="best_practices_demo",
        system_message="You are demonstrating best practices. Be comprehensive and helpful."
    )

    # [OK] Demonstrate all features in one workflow
    print("Comprehensive workflow demonstration:")

    # 1. Initial conversation
    response1 = await agent.chat("I want to learn about AI agent best practices")
    print(f"1⃣ Initial: {response1[:80]}...")

    # 2. Context-aware follow-up
    response2 = await agent.chat("What about memory management?")
    print(f"2⃣ Context: {response2[:80]}...")

    # 3. Get conversation history
    history = await agent.get_conversation_history()
    print(f"3⃣ History: {len(history)} messages preserved")

    # 4. Add custom context
    await agent.add_to_conversation_history("Key insight: Context preservation is crucial", "system")

    # 5. Final summary
    summary = await agent.get_conversation_summary()
    print(f"4⃣ Summary: {summary['total_messages']} total messages")
    print(f"   User: {summary['user_messages']}, Agent: {summary['agent_messages']}")
    print(f"   Duration: {summary['session_duration']}")

    await agent.cleanup_session()
    print("[OK] Best practices summary completed!\n")


# =============================================================================
# MAIN EXECUTION (ASYNC-SAFE)
# =============================================================================

async def main():
    """[OK] FIXED: Properly async main function"""
    print("CORRECTED ONE-LINER EXAMPLES WITH BEST PRACTICES")
    print("=" * 60)
    print("Fixed event loop issues and ModeratorAgent constructor conflicts")
    print("Demonstrates memory retention, context preservation, and proper error handling")
    print("Perfect for training new developers on the Ambivo Agent system")
    print("=" * 60)

    # Run all examples with proper async handling
    await ultra_simple_examples()
    await context_aware_examples()
    await specialized_agent_examples()
    await system_message_examples()
    await streaming_examples()
    await error_handling_examples()
    await best_practices_summary()

    print("ALL EXAMPLES COMPLETED SUCCESSFULLY!")
    print("\nKEY TAKEAWAYS FOR NEW DEVELOPERS:")
    print("   [OK] Always use .create() to get both agent and context")
    print("   [OK] Use system messages to customize agent behavior")
    print("   [OK] Context is automatically preserved across conversations")
    print("   [OK] Always cleanup sessions with await agent.cleanup_session()")
    print("   [OK] Handle errors gracefully with try/except blocks")
    print("   [OK] Use await agent.chat() in async contexts")
    print("   [OK] Use agent.chat_sync() only in non-async contexts")
    print("   [OK] Leverage conversation history for context-aware interactions")
    print("\nYou're ready to build amazing AI agent applications!")


# =============================================================================
# SYNC ENTRY POINT FOR NON-ASYNC ENVIRONMENTS
# =============================================================================

def sync_main():
    """Entry point for non-async environments"""
    try:
        asyncio.run(main())
    except Exception as e:
        print(f"[ERROR] Error running examples: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":

    sync_main()