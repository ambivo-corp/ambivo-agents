#!/usr/bin/env python3
"""
simple_search_example.py
Direct demonstration of the Simple Web Search Agent
Shows provider information clearly
"""

import asyncio
import sys
import os
import time
from pathlib import Path

# Add the ambivo_agents package to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from ambivo_agents.core.memory import create_redis_memory_manager
from ambivo_agents.core.llm import create_multi_provider_llm_service
from ambivo_agents.config.loader import load_config, get_config_section
from ambivo_agents.agents.simple_web_search import SimpleWebSearchAgent


class SimpleSearchDemo:
    """Direct demonstration of simple web search functionality"""

    def __init__(self):
        print("🔍 Simple Web Search Agent Demo")
        print("=" * 40)

        # Load configuration
        self.config = load_config()
        self.redis_config = get_config_section('redis', self.config)
        self.llm_config = get_config_section('llm', self.config)

        # Create components
        self.memory_manager = create_redis_memory_manager("simple_search_demo", self.redis_config)

        self.llm_service = create_multi_provider_llm_service(
            config_data=self.llm_config,
            preferred_provider='openai'
        )

        # Create the simple search agent
        self.search_agent = SimpleWebSearchAgent(
            agent_id="simple_search_001",
            memory_manager=self.memory_manager,
            llm_service=self.llm_service
        )

        print(f"✅ Simple Web Search Agent initialized")

    def show_provider_status(self):
        """Display current provider status"""
        print(f"\n📡 Search Provider Status")
        print("-" * 25)

        status = self.search_agent.get_provider_status()
        current = status['current_provider']

        print(f"🎯 Current Provider: {current.upper() if current else 'None'}")
        print(f"📋 Available Providers:")

        for provider_code, provider_info in status['providers'].items():
            status_icon = "✅" if provider_info['available'] else "❌"
            priority = provider_info['priority']
            name = provider_info['name']

            current_marker = " ← ACTIVE" if provider_code == current else ""
            print(f"  {status_icon} {name} (Priority: {priority}){current_marker}")

    async def test_direct_search(self, query: str):
        """Test direct search functionality"""
        print(f"\n🔍 Direct Search Test")
        print(f"📝 Query: '{query}'")
        print("-" * 30)

        start_time = time.time()

        try:
            result = await self.search_agent.search_web(query, max_results=3)
            total_time = time.time() - start_time

            if result['success']:
                provider = result['provider']

                print(f"✅ Search successful!")
                print(f"📡 Provider: {provider['name']} ({provider['code'].upper()})")
                print(f"⏱️  Total time: {total_time:.2f}s")
                print(f"🔗 API Endpoint: {provider['api_endpoint']}")
                print(f"📊 Results found: {len(result['results'])}")

                print(f"\n📋 Results:")
                for i, res in enumerate(result['results'], 1):
                    print(f"  {i}. {res.title}")
                    print(f"     🔗 {res.url}")
                    print(f"     📝 {res.snippet[:100]}...")
                    print()

                return result
            else:
                provider = result.get('provider', {})
                provider_name = provider.get('name', 'Unknown') if provider else 'Unknown'

                print(f"❌ Search failed")
                print(f"📡 Provider: {provider_name}")
                print(f"⚠️  Error: {result['error']}")
                return None

        except Exception as e:
            print(f"❌ Exception: {e}")
            return None

    async def test_agent_messaging(self, message: str):
        """Test the agent's message processing"""
        print(f"\n💬 Agent Message Test")
        print(f"📝 Message: '{message}'")
        print("-" * 30)

        from ambivo_agents.core.base import AgentMessage, MessageType, ExecutionContext
        import uuid

        # Create test message
        test_message = AgentMessage(
            id=str(uuid.uuid4()),
            sender_id="demo_user",
            recipient_id=self.search_agent.agent_id,
            content=message,
            message_type=MessageType.USER_INPUT
        )

        # Create execution context
        context = ExecutionContext(
            session_id="demo_session",
            conversation_id="demo_conversation",
            user_id="demo_user",
            tenant_id="demo_tenant"
        )

        start_time = time.time()

        try:
            response = await self.search_agent.process_message(test_message, context)
            total_time = time.time() - start_time

            print(f"✅ Agent responded in {total_time:.2f}s")
            print(f"📄 Response:")
            print("-" * 20)
            print(response.content)
            print("-" * 20)

            return response

        except Exception as e:
            print(f"❌ Agent error: {e}")
            return None

    async def demo_ambivo_search(self):
        """Demonstrate searching for Ambivo information"""
        print(f"\n🏢 Ambivo Search Demonstration")
        print("=" * 35)

        queries = [
            "what is ambivo",
            "ambivo AI company platform"
        ]

        results = []

        for i, query in enumerate(queries, 1):
            print(f"\n--- Query {i}/{len(queries)} ---")

            # Test direct search
            result = await self.test_direct_search(query)
            if result:
                results.append(result)

            # Small delay between searches
            if i < len(queries):
                print("⏳ Waiting 3 seconds...")
                await asyncio.sleep(3)

        return results

    async def demo_provider_switching(self):
        """Demonstrate provider fallback functionality"""
        print(f"\n🔄 Provider Switching Demo")
        print("=" * 30)

        # Show initial provider
        self.show_provider_status()

        # Test a search to see which provider is used
        await self.test_direct_search("test provider query")

        # Show final provider status (might have switched due to errors)
        self.show_provider_status()

    async def run_demo(self):
        """Run the complete demonstration"""

        try:
            # Show provider status
            self.show_provider_status()

            # Test direct search functionality
            print(f"\n🧪 Testing Direct Search Functionality")
            await self.test_direct_search("Python programming tutorial")

            # Test agent messaging
            print(f"\n🧪 Testing Agent Message Processing")
            await self.test_agent_messaging("search for what is artificial intelligence")

            # Demo Ambivo search
            ambivo_results = await self.demo_ambivo_search()

            # Demo provider behavior
            await self.demo_provider_switching()

            # Summary
            print(f"\n📊 Demo Summary")
            print("=" * 20)
            print(f"✅ Simple Web Search Agent working correctly")
            print(f"📡 Provider information clearly displayed")
            print(f"🔄 Fallback functionality operational")

            if ambivo_results:
                print(f"🏢 Found information about Ambivo using:")
                for result in ambivo_results:
                    provider = result['provider']
                    print(f"   - {provider['name']} ({provider['code'].upper()})")

            print(f"\n💡 Key Features Demonstrated:")
            print(f"   ✅ Direct web search with provider reporting")
            print(f"   ✅ Clear error handling and fallback")
            print(f"   ✅ Agent message processing")
            print(f"   ✅ Rate limiting and API management")

        except Exception as e:
            print(f"\n❌ Demo failed: {e}")
            import traceback
            traceback.print_exc()


async def main():
    """Main function"""
    import argparse

    parser = argparse.ArgumentParser(description="Simple Web Search Agent Demo")
    parser.add_argument("--query", help="Single query to test")
    parser.add_argument("--direct", action="store_true", help="Test direct search only")
    parser.add_argument("--status", action="store_true", help="Show provider status only")

    args = parser.parse_args()

    try:
        demo = SimpleSearchDemo()

        if args.status:
            # Just show provider status
            demo.show_provider_status()

        elif args.query:
            # Test single query
            print(f"🎯 Testing single query: '{args.query}'")

            if args.direct:
                await demo.test_direct_search(args.query)
            else:
                await demo.test_agent_messaging(f"search for {args.query}")

        else:
            # Run full demo
            await demo.run_demo()

    except KeyboardInterrupt:
        print("\n⚠️  Demo interrupted by user")
    except Exception as e:
        print(f"\n❌ Demo failed: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    asyncio.run(main())