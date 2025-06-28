# examples/health_monitoring.py
"""
Health checking and monitoring example
"""

import asyncio
import time
from ambivo_agents import create_agent_service


async def main():
    """Health monitoring example"""

    service = create_agent_service()

    # Health check
    print("🏥 Health Check:")
    health = service.health_check()

    print(f"   Service Available: {health['service_available']}")
    print(f"   Redis Available: {health.get('redis_available', 'Unknown')}")
    print(f"   LLM Available: {health.get('llm_service_available', 'Unknown')}")
    print(f"   Current LLM Provider: {health.get('llm_current_provider', 'Unknown')}")

    # Service statistics
    print(f"\n📊 Service Statistics:")
    stats = service.get_service_stats()

    print(f"   Status: {stats['service_status']}")
    print(f"   Uptime: {stats['uptime_seconds']:.2f} seconds")
    print(f"   Active Sessions: {stats['active_sessions']}")
    print(f"   Total Sessions: {stats['total_sessions_created']}")
    print(f"   Messages Processed: {stats['total_messages_processed']}")

    print(f"\n🔧 Available Agent Types:")
    for agent_type, available in stats['available_agent_types'].items():
        status = "✅" if available else "❌"
        print(f"   {status} {agent_type}")

    # Process some messages to generate activity
    print(f"\n🔄 Processing test messages...")

    test_messages = [
        "Hello!",
        "What's 2 + 2?",
        "```python\nprint('Test')\n```"
    ]

    for i, msg in enumerate(test_messages):
        result = await service.process_message(
            message=msg,
            session_id=f"test-session-{i}",
            user_id="test-user"
        )
        print(f"   Message {i + 1}: {'✅' if result['success'] else '❌'}")
        time.sleep(0.5)  # Small delay

    # Updated statistics
    print(f"\n📊 Updated Statistics:")
    updated_stats = service.get_service_stats()
    print(f"   Active Sessions: {updated_stats['active_sessions']}")
    print(f"   Total Sessions: {updated_stats['total_sessions_created']}")
    print(f"   Messages Processed: {updated_stats['total_messages_processed']}")


if __name__ == "__main__":
    asyncio.run(main())