# examples/debug_basic_chat.py
"""
Debug version of basic chat example
"""

import asyncio
import sys
import traceback


def main():
    """Debug version of basic chat - not async to catch import errors"""

    print("🔍 Starting debug chat example...")

    try:
        print("📦 Attempting to import ambivo_agents...")
        from ambivo_agents import create_agent_service
        print("✅ Import successful!")

        print("📋 Checking configuration...")
        from ambivo_agents.config.loader import load_config
        config = load_config()
        print("✅ Configuration loaded!")

        print("🚀 Creating agent service...")
        service = create_agent_service()
        print("✅ Agent service created!")

        print("📊 Getting service stats...")
        stats = service.get_service_stats()
        print(f"✅ Service status: {stats['service_status']}")
        print(f"📈 Available capabilities: {stats['enabled_capabilities']}")

        print("🏥 Running health check...")
        health = service.health_check()
        print(f"✅ Service available: {health['service_available']}")
        print(f"🔌 Redis available: {health.get('redis_available', 'Unknown')}")
        print(f"🧠 LLM available: {health.get('llm_service_available', 'Unknown')}")

        if health.get('llm_service_available'):
            print(f"🤖 LLM Provider: {health.get('llm_current_provider', 'Unknown')}")
        else:
            print(f"❌ LLM Error: {health.get('llm_error', 'Unknown')}")

        # Try async part
        print("\n🔄 Testing async message processing...")
        asyncio.run(test_async_chat(service))

    except Exception as e:
        print(f"❌ Error occurred: {e}")
        print(f"🔍 Error type: {type(e).__name__}")
        print("📋 Full traceback:")
        traceback.print_exc()


async def test_async_chat(service):
    """Test async chat functionality"""
    try:
        print("💬 Processing test message...")

        result = await service.process_message(
            message="Hello, are you working?",
            session_id="debug-session",
            user_id="debug-user"
        )

        if result['success']:
            print(f"✅ Chat successful!")
            print(f"🤖 Response: {result['response'][:100]}...")
        else:
            print(f"❌ Chat failed: {result['error']}")

    except Exception as e:
        print(f"❌ Async error: {e}")
        traceback.print_exc()


if __name__ == "__main__":
    main()