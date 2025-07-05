#!/usr/bin/env python3
"""
Improved Basic Streaming Example
Demonstrates proper usage of ModeratorAgent with system message and context preservation
"""

import asyncio
from ambivo_agents import ModeratorAgent


async def basic_streaming_demo():
    """Demonstrates basic streaming with proper context handling"""
    print("🌟 Basic Streaming Example with Context Preservation")
    print("=" * 60)

    # ✅ BEST PRACTICE: Create agent with custom system message
    agent, context = ModeratorAgent.create(
        user_id="john",
        system_message="""You are an intelligent coordinator that routes requests to specialized agents.
        Always explain your routing decisions and maintain conversation context."""
    )

    print(f"✅ Created ModeratorAgent for user: {context.user_id}")
    print(f"📋 Session ID: {context.session_id}")
    print(f"🎯 Conversation ID: {context.conversation_id}")
    print()

    # ✅ BEST PRACTICE: Show streaming with proper formatting
    print("🤖 Assistant: ", end='', flush=True)

    try:
        async for chunk in agent.chat_stream("Download https://youtube.com/watch?v=C0DPdy98e4c"):
            print(chunk, end='', flush=True)
        print()  # New line after streaming

        # ✅ BEST PRACTICE: Demonstrate conversation history preservation
        print("\n🧠 Demonstrating Context Preservation:")
        print("🤖 Assistant: ", end='', flush=True)

        # This should reference the previous YouTube URL due to context preservation
        async for chunk in agent.chat_stream("What format should I download that in?"):
            print(chunk, end='', flush=True)
        print()

        # ✅ BEST PRACTICE: Show conversation summary
        summary = await agent.get_conversation_summary()
        print(f"\n📊 Conversation Summary:")
        print(f"   Total messages: {summary['total_messages']}")
        print(f"   Duration: {summary['session_duration']}")
        print(f"   Session: {summary['session_id']}")

    except Exception as e:
        print(f"\n❌ Error: {e}")

    finally:
        # ✅ BEST PRACTICE: Always cleanup
        await agent.cleanup_session()
        print("\n🧹 Session cleaned up")


async def multi_turn_conversation():
    """Demonstrates multi-turn conversation with context"""
    print("\n🔄 Multi-Turn Conversation Example")
    print("=" * 40)

    agent, context = ModeratorAgent.create(
        user_id="alice",
        system_message="You are a helpful assistant with perfect memory. Always reference previous context."
    )

    print(f"✅ Starting conversation for user: {context.user_id}")

    # Turn 1: Initial request
    print("\n👤 User: I'm working on a Python data science project")
    print("🤖 Assistant: ", end='', flush=True)
    async for chunk in agent.chat_stream("I'm working on a Python data science project"):
        print(chunk, end='', flush=True)
    print()

    # Turn 2: Follow-up (should reference previous context)
    print("\n👤 User: What libraries should I use?")
    print("🤖 Assistant: ", end='', flush=True)
    async for chunk in agent.chat_stream("What libraries should I use?"):
        print(chunk, end='', flush=True)
    print()

    # Turn 3: Continuation (should maintain full context)
    print("\n👤 User: Show me a code example")
    print("🤖 Assistant: ", end='', flush=True)
    async for chunk in agent.chat_stream("Show me a code example"):
        print(chunk, end='', flush=True)
    print()

    # Show how conversation history is preserved
    history = await agent.get_conversation_history(limit=10)
    print(f"\n📚 Conversation History: {len(history)} messages preserved")

    await agent.cleanup_session()


async def error_handling_example():
    """Demonstrates proper error handling with streaming"""
    print("\n🛡️ Error Handling Example")
    print("=" * 30)

    agent, context = ModeratorAgent.create(
        user_id="bob",
        system_message="You are a resilient assistant that handles errors gracefully."
    )

    try:
        # Test with potentially problematic input
        print("🤖 Testing error resilience: ", end='', flush=True)
        async for chunk in agent.chat_stream("Process this: " + "x" * 10000):  # Very long input
            print(chunk, end='', flush=True)
        print()

    except Exception as e:
        print(f"\n⚠️ Handled error gracefully: {e}")

    finally:
        await agent.cleanup_session()


async def main():
    """Run all streaming examples"""
    print("🌊 STREAMING EXAMPLES WITH BEST PRACTICES")
    print("=" * 50)
    print("Demonstrates proper memory retention, context preservation, and error handling")
    print("=" * 50)

    await basic_streaming_demo()
    await multi_turn_conversation()
    await error_handling_example()

    print(f"\n🎉 All Streaming Examples Completed!")
    print(f"\n💡 Key Best Practices Demonstrated:")
    print(f"   ✅ Custom system messages for agent behavior")
    print(f"   ✅ Proper context creation and tracking")
    print(f"   ✅ Conversation history preservation")
    print(f"   ✅ Multi-turn conversation handling")
    print(f"   ✅ Graceful error handling")
    print(f"   ✅ Session cleanup")


if __name__ == "__main__":
    asyncio.run(main())