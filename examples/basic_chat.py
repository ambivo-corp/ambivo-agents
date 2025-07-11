#!/usr/bin/env python3
"""
Improved Basic Chat Example with Comprehensive Debugging
Follows all best practices for production deployment
"""

import asyncio
import sys
import traceback
import logging
from datetime import datetime

from ambivo_agents import ModeratorAgent

# ✅ BEST PRACTICE: Configure logging for debugging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def main():
    """Production-ready chat example with comprehensive error handling"""

    print("🔍 COMPREHENSIVE CHAT EXAMPLE WITH DEBUGGING")
    print("=" * 55)
    print(f"🕐 Started at: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print()

    try:
        # ✅ STEP 1: Import and basic checks
        print("📦 Step 1: Importing ambivo_agents...")
        from ambivo_agents import create_agent_service, ModeratorAgent
        print("✅ Import successful!")

        # ✅ STEP 2: Configuration validation
        print("\n📋 Step 2: Validating configuration...")
        from ambivo_agents.config.loader import load_config, validate_agent_capabilities
        config = load_config()
        capabilities = validate_agent_capabilities(config)

        print("✅ Configuration loaded successfully!")
        print(f"🎯 Available capabilities: {list(capabilities.keys())}")
        print(f"🔌 Enabled capabilities: {[k for k, v in capabilities.items() if v]}")

        # ✅ STEP 3: Service creation with error handling
        print("\n🚀 Step 3: Creating agent service...")
        service = create_agent_service()
        print("✅ Agent service created successfully!")

        # ✅ STEP 4: Health check
        print("\n🏥 Step 4: Running comprehensive health check...")
        health = service.health_check()

        print(f"✅ Service available: {health['service_available']}")
        print(f"🔌 Redis available: {health.get('redis_available', 'Unknown')}")
        print(f"🧠 LLM available: {health.get('llm_service_available', 'Unknown')}")

        if health.get('llm_service_available'):
            print(f"🤖 LLM Provider: {health.get('llm_current_provider', 'Unknown')}")
            available_providers = health.get('llm_available_providers', [])
            print(f"🔄 Available Providers: {available_providers}")
        else:
            print(f"❌ LLM Error: {health.get('llm_error', 'Unknown')}")

        # ✅ STEP 5: Direct agent testing (recommended approach)
        print("\n🎯 Step 5: Testing direct agent interaction...")
        asyncio.run(test_direct_agent_interaction())

        # ✅ STEP 6: Service-based testing
        print("\n🔄 Step 6: Testing service-based interaction...")
        asyncio.run(test_service_interaction(service))

        print("\n🎉 All tests completed successfully!")

    except ImportError as e:
        print(f"❌ Import Error: {e}")
        print("💡 Check if ambivo_agents is properly installed")
        return 1

    except Exception as e:
        print(f"❌ Unexpected error: {e}")
        print(f"🔍 Error type: {type(e).__name__}")
        print("📋 Full traceback:")
        traceback.print_exc()
        return 1

    return 0


async def test_direct_agent_interaction():
    """✅ BEST PRACTICE: Test direct agent interaction with context preservation"""

    print("   🤖 Creating ModeratorAgent with custom system message...")

    # ✅ Create agent with context and custom system message
    agent, context = ModeratorAgent.create(
        user_id="test_user",
        tenant_id="test_company",
        system_message="""You are a helpful debugging assistant. 
        Always provide clear, concise responses and remember our conversation context."""
    )

    print(f"   ✅ Agent created: {agent.agent_id}")
    print(f"   👤 User: {context.user_id}")
    print(f"   📋 Session: {context.session_id}")
    print(f"   🎯 Conversation: {context.conversation_id}")

    try:
        # ✅ Test 1: Basic chat
        print("\n   💬 Test 1: Basic chat functionality...")
        response = agent.chat_sync("Hello! Are you working correctly?")
        print(f"   ✅ Response received: {response[:100]}...")

        # ✅ Test 2: Context preservation
        print("\n   🧠 Test 2: Testing context preservation...")
        response2 = agent.chat_sync("What did I just ask you?")
        print(f"   ✅ Context response: {response2[:100]}...")

        # ✅ Test 3: Conversation history
        print("\nx-amb-info:Test 3: Checking conversation history...")
        history = await agent.get_conversation_history()
        print(f"x-amb-info:History retrieved: {len(history)} messages")

        # ✅ Test 4: Conversation summary
        print("\n   📊 Test 4: Getting conversation summary...")
        summary = await agent.get_conversation_summary()
        print(f"   ✅ Summary: {summary['total_messages']} messages, {summary['session_duration']}")

    except Exception as e:
        print(f"   ❌ Direct agent test failed: {e}")

    finally:
        # ✅ BEST PRACTICE: Always cleanup
        await agent.cleanup_session()
        print("   🧹 Agent session cleaned up")


async def test_service_interaction(service):
    """Test service-based interaction (alternative approach)"""

    print("   🏢 Testing service-based message processing...")

    try:
        # ✅ Test service processing
        result = await service.process_message(
            message="Hello from the service test! Please confirm you're working.",
            session_id="service-test-session",
            user_id="service-test-user",
            metadata={"test_type": "service_validation", "timestamp": datetime.now().isoformat()}
        )

        if result['success']:
            print(f"   ✅ Service test successful!")
            print(f"   🤖 Response: {result['response'][:100]}...")
            print(f"   📊 Processing time: {result['processing_time']:.2f}s")
            print(f"   🎯 Agent used: {result['agent_id']}")
        else:
            print(f"   ❌ Service test failed: {result['error']}")

        # ✅ Get service statistics
        stats = service.get_service_stats()
        print(f"   📈 Service stats: {stats['active_sessions']} sessions, {stats['total_messages_processed']} messages")

    except Exception as e:
        print(f"   ❌ Service test error: {e}")


async def demonstrate_best_practices():
    """Demonstrate all best practices in one example"""

    print("\n🌟 BEST PRACTICES DEMONSTRATION")
    print("=" * 40)

    # ✅ BEST PRACTICE: Comprehensive agent setup
    agent, context = ModeratorAgent.create(
        user_id="demo_user",
        tenant_id="demo_company",
        session_metadata={
            "app_version": "1.0.0",
            "feature_flags": {"debug": True},
            "user_preferences": {"language": "en", "verbose": True}
        },
        system_message="""You are a demonstration assistant showcasing best practices.
        Always be helpful, maintain context, and explain your reasoning."""
    )

    print(f"✅ Agent setup complete:")
    print(f"   Agent ID: {agent.agent_id}")
    print(f"   User: {context.user_id}")
    print(f"   Tenant: {context.tenant_id}")
    print(f"   Session: {context.session_id}")
    print(f"   Metadata: {context.metadata}")

    try:
        # ✅ Multi-turn conversation
        conversations = [
            "I'm working on a machine learning project",
            "What libraries would you recommend?",
            "Can you help me with data preprocessing?",
            "What about model selection?"
        ]

        for i, msg in enumerate(conversations, 1):
            print(f"\n💬 Turn {i}: {msg}")
            response = agent.chat_sync(msg)
            print(f"🤖 Response: {response[:150]}...")

        # ✅ Final conversation analysis
        summary = await agent.get_conversation_summary()
        print(f"\n📊 Final Analysis:")
        print(f"   Total messages: {summary['total_messages']}")
        print(f"   User messages: {summary['user_messages']}")
        print(f"   Agent messages: {summary['agent_messages']}")
        print(f"   Session duration: {summary['session_duration']}")

    finally:
        await agent.cleanup_session()
        print("\n🧹 Session properly cleaned up")


if __name__ == "__main__":
    # Run main debugging
    exit_code = main()

    # Run best practices demo if main succeeded
    if exit_code == 0:
        print("\n" + "=" * 60)
        asyncio.run(demonstrate_best_practices())

    sys.exit(exit_code)