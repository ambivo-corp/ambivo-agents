#!/usr/bin/env python3
"""
Improved Basic Streaming Example
Demonstrates proper usage of ModeratorAgent with StreamChunk system and context preservation
"""

import asyncio
from ambivo_agents import ModeratorAgent
from ambivo_agents.core.base import StreamSubType


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

    # ✅ BEST PRACTICE: Show streaming with StreamChunk filtering
    print("🤖 Assistant: ", end='', flush=True)

    try:
        async for chunk in agent.chat_stream("Download https://youtube.com/watch?v=C0DPdy98e4c"):
            # Handle both StreamChunk objects and legacy string responses
            if hasattr(chunk, 'sub_type'):
                # New StreamChunk system
                if chunk.sub_type == StreamSubType.CONTENT:
                    print(chunk.text, end='', flush=True)
                elif chunk.sub_type == StreamSubType.STATUS:
                    # Optionally show status in a different format
                    print(f"\n[{chunk.text.strip()}]", end='', flush=True)
            else:
                # Legacy string response - print as-is
                if chunk.strip():  # Only print non-empty strings
                    print(chunk, end='', flush=True)
        print()  # New line after streaming

        # ✅ BEST PRACTICE: Demonstrate conversation history preservation
        print("\n🧠 Demonstrating Context Preservation:")
        print("🤖 Assistant: ", end='', flush=True)

        # This should reference the previous YouTube URL due to context preservation
        async for chunk in agent.chat_stream("What format should I download that in?"):
            # Handle both StreamChunk objects and legacy string responses
            if hasattr(chunk, 'sub_type'):
                # New StreamChunk system
                if chunk.sub_type == StreamSubType.CONTENT:
                    print(chunk.text, end='', flush=True)
                elif chunk.sub_type == StreamSubType.STATUS:
                    print(f"\n[Status: {chunk.text.strip()}]", end='', flush=True)
                elif chunk.sub_type == StreamSubType.ERROR:
                    print(f"\n[Error: {chunk.text.strip()}]", end='', flush=True)
            else:
                # Legacy string response - print as-is
                if chunk.strip():  # Only print non-empty strings
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
        if hasattr(chunk, 'sub_type'):
            if chunk.sub_type in [StreamSubType.CONTENT, StreamSubType.RESULT]:
                print(chunk.text, end='', flush=True)
        else:
            if chunk.strip():
                print(chunk, end='', flush=True)
    print()

    # Turn 2: Follow-up (should reference previous context)
    print("\n👤 User: What libraries should I use?")
    print("🤖 Assistant: ", end='', flush=True)
    async for chunk in agent.chat_stream("What libraries should I use?"):
        if hasattr(chunk, 'sub_type'):
            if chunk.sub_type in [StreamSubType.CONTENT, StreamSubType.RESULT]:
                print(chunk.text, end='', flush=True)
        else:
            if chunk.strip():
                print(chunk, end='', flush=True)
    print()

    # Turn 3: Continuation (should maintain full context)
    print("\n👤 User: Show me a code example")
    print("🤖 Assistant: ", end='', flush=True)
    async for chunk in agent.chat_stream("Show me a code example"):
        if hasattr(chunk, 'sub_type'):
            if chunk.sub_type in [StreamSubType.CONTENT, StreamSubType.RESULT]:
                print(chunk.text, end='', flush=True)
        else:
            if chunk.strip():
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
            if hasattr(chunk, 'sub_type'):
                if chunk.sub_type == StreamSubType.ERROR:
                    print(f"\n[ERROR: {chunk.text}]", end='', flush=True)
                elif chunk.sub_type == StreamSubType.CONTENT:
                    print(chunk.text, end='', flush=True)
            else:
                if chunk.strip():
                    print(chunk, end='', flush=True)
        print()

    except Exception as e:
        print(f"\n⚠️ Handled error gracefully: {e}")

    finally:
        await agent.cleanup_session()


async def advanced_streamchunk_example():
    """Demonstrates advanced StreamChunk filtering and metadata usage"""
    print("\n🔬 Advanced StreamChunk Example")
    print("=" * 40)

    agent, context = ModeratorAgent.create(
        user_id="developer",
        system_message="You are a developer assistant that provides detailed responses."
    )

    print("🤖 Demonstrating StreamChunk types and metadata:")
    print("=" * 50)

    try:
        # Collect different types of chunks
        content_chunks = []
        status_chunks = []
        result_chunks = []
        error_chunks = []
        
        async for chunk in agent.chat_stream("Search for Python web frameworks and tell me about them"):
            # Handle both StreamChunk objects and legacy string responses
            if hasattr(chunk, 'sub_type'):
                # Categorize chunks by type
                if chunk.sub_type == StreamSubType.CONTENT:
                    content_chunks.append(chunk)
                    print(chunk.text, end='', flush=True)
                elif chunk.sub_type == StreamSubType.STATUS:
                    status_chunks.append(chunk)
                    print(f"\n[STATUS: {chunk.text.strip()}]", flush=True)
                elif chunk.sub_type == StreamSubType.RESULT:
                    result_chunks.append(chunk)
                    print(f"\n[RESULT: {chunk.text.strip()}]", flush=True)
                elif chunk.sub_type == StreamSubType.ERROR:
                    error_chunks.append(chunk)
                    print(f"\n[ERROR: {chunk.text.strip()}]", flush=True)
            else:
                # Legacy string response - treat as content if non-empty
                if chunk.strip():
                    print(chunk, end='', flush=True)

        print("\n\n📊 Stream Analysis:")
        print(f"   Content chunks: {len(content_chunks)}")
        print(f"   Status chunks: {len(status_chunks)}")
        print(f"   Result chunks: {len(result_chunks)}")
        print(f"   Error chunks: {len(error_chunks)}")

        # Show metadata examples
        if status_chunks:
            print(f"\n🔍 Sample Status Metadata:")
            sample_status = status_chunks[0]
            print(f"   Text: {sample_status.text[:50]}...")
            print(f"   Metadata: {sample_status.metadata}")
            print(f"   Timestamp: {sample_status.timestamp}")

        if result_chunks:
            print(f"\n🔍 Sample Result Metadata:")
            sample_result = result_chunks[0]
            print(f"   Text: {sample_result.text[:50]}...")
            print(f"   Metadata: {sample_result.metadata}")

    except Exception as e:
        print(f"\n❌ Error in advanced example: {e}")

    finally:
        await agent.cleanup_session()


async def main():
    """Run all streaming examples"""
    print("🌊 STREAMING EXAMPLES WITH STREAMCHUNK SYSTEM")
    print("=" * 55)
    print("Demonstrates StreamChunk filtering, metadata usage, and context preservation")
    print("=" * 55)

    await basic_streaming_demo()
    await multi_turn_conversation()
    await error_handling_example()
    await advanced_streamchunk_example()

    print(f"\n🎉 All Streaming Examples Completed!")
    print(f"\n💡 Key Features Demonstrated:")
    print(f"   ✅ StreamChunk filtering by sub_type")
    print(f"   ✅ Rich metadata access and analysis")
    print(f"   ✅ Custom system messages for agent behavior")
    print(f"   ✅ Proper context creation and tracking")
    print(f"   ✅ Conversation history preservation")
    print(f"   ✅ Multi-turn conversation handling")
    print(f"   ✅ Graceful error handling")
    print(f"   ✅ Session cleanup")
    print(f"\n🔧 StreamChunk Benefits:")
    print(f"   • Type-safe content classification")
    print(f"   • Rich metadata for debugging and analytics")
    print(f"   • Programmatic filtering (no string parsing)")
    print(f"   • Consistent interface across all agents")


if __name__ == "__main__":
    asyncio.run(main())