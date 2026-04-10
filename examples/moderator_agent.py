#!/usr/bin/env python3
"""
Simple ModeratorAgent Test Example

This script demonstrates how to use the ModeratorAgent to orchestrate multiple agents.
The ModeratorAgent intelligently routes queries to appropriate specialized agents.

Requirements:
- agent_config.yaml should be in the same directory
- Redis should be running (configured in agent_config.yaml)
- At least some agents should be enabled in the configuration

Author: Hemant Gosain 'Sunny'
Company: Ambivo
Email: sgosain@ambivo.com
"""

import asyncio
import time
from typing import List, Dict, Any

# Import the ModeratorAgent
try:
    from ambivo_agents.agents.moderator import ModeratorAgent

    MODERATOR_AVAILABLE = True
except ImportError as e:
    print(f"[ERROR] ModeratorAgent not available: {e}")
    print("Make sure ambivo_agents package is installed and ModeratorAgent is exported")
    MODERATOR_AVAILABLE = False


class SimpleModeratorTest:
    """Simple test class for ModeratorAgent"""

    def __init__(self, enabled_agents: List[str] = None):
        """Initialize the test with specific enabled agents"""
        if not MODERATOR_AVAILABLE:
            raise RuntimeError("ModeratorAgent not available")

        # Default enabled agents for testing
        if enabled_agents is None:
            enabled_agents = [
                'assistant',
                'knowledge_base',
                'knowledge_synthesis',
                'web_search',
                'web_scraper',
            ]

        self.enabled_agents = enabled_agents
        self.moderator: ModeratorAgent | None = None  # Type hint for IDE
        self.context = None

    async def setup(self):
        """Setup the ModeratorAgent"""
        print("Setting up ModeratorAgent...")
        print(f"Enabled agents: {', '.join(self.enabled_agents)}")

        try:
            # Create moderator with enabled agents
            self.moderator, self.context = ModeratorAgent.create(
                user_id="test_user",
                tenant_id="test_tenant",
                enabled_agents=self.enabled_agents
            )

            print(f"[OK] ModeratorAgent created successfully!")
            print(f"Agent ID: {self.moderator.agent_id}")
            print(f"Session ID: {self.context.session_id}")
            print(f"User ID: {self.context.user_id}")

            # Get and display agent status
            status = await self.moderator.get_agent_status()
            print(f"Active agents: {status['total_agents']}")

            for agent_type, agent_info in status['active_agents'].items():
                print(f"   • {agent_type}: {agent_info['status']}")

        except Exception as e:
            print(f"[ERROR] Failed to setup ModeratorAgent: {e}")
            raise

    async def test_query(self, message: str, description: str = None) -> str:
        """Test a single query with the moderator"""
        if description:
            print(f"\n{description}")

        print(f"Query: '{message}'")

        start_time = time.time()

        try:
            # Use the simple chat interface
            response = await self.moderator.chat(message)

            processing_time = time.time() - start_time

            print(f"Response: {response}")
            print(f"Processing time: {processing_time:.2f}s")

            return response

        except Exception as e:
            processing_time = time.time() - start_time
            error_msg = f"[ERROR] Error: {e}"
            print(error_msg)
            print(f"Processing time: {processing_time:.2f}s")
            return error_msg

    async def run_test_suite(self):
        """Run a comprehensive test suite"""
        print("Running ModeratorAgent Test Suite")
        print("=" * 50)

        # Test queries that should route to different agents
        test_cases = [
            {
                "message": "Hello, I need help with something",
                "description": "General assistance (should route to AssistantAgent)"
            },
            {
                "message": "Search for latest AI trends in 2025",
                "description": "Web search query (should route to WebSearchAgent)"
            },
            {
                "message": "Using the knowledge base ambivo_demo_kb, answer the question 'What Product and services are offered?'",
                "description": "Knowledge base operation (should route to KnowledgeBaseAgent)"
            },
            {
                "message": "Scrape https://ambivo.com for content",
                "description": "Web scraping (should route to WebScraperAgent)"
            },
            {
                "message": "What is machine learning and how does it work?",
                "description": "Complex question (should route to AssistantAgent or use multiple agents)"
            }
        ]

        results = []

        for i, test_case in enumerate(test_cases, 1):
            print(f"\nTest {i}/{len(test_cases)}")
            print("-" * 30)

            response = await self.test_query(
                test_case["message"],
                test_case["description"]
            )

            results.append({
                "test_number": i,
                "message": test_case["message"],
                "description": test_case["description"],
                "response": response,
                "success": not response.startswith("[ERROR]")
            })

        # Print summary
        print("\nTest Summary")
        print("=" * 50)

        successful_tests = sum(1 for r in results if r["success"])
        total_tests = len(results)

        print(f"[OK] Successful: {successful_tests}/{total_tests}")
        print(f"[ERROR] Failed: {total_tests - successful_tests}/{total_tests}")

        if successful_tests == total_tests:
            print("All tests passed!")
        else:
            print("[WARN]Some tests failed - check agent configuration and availability")

        return results

    async def interactive_mode(self):
        """Run in interactive mode for manual testing"""
        print("\nInteractive Mode")
        print("=" * 30)
        print("Type your queries to test the ModeratorAgent")
        print("Type 'quit', 'exit', or 'bye' to exit")
        print("Type 'status' to see agent status")

        while True:
            try:
                user_input = input("\n You: ").strip()

                if not user_input:
                    continue

                if user_input.lower() in ['quit', 'exit', 'bye']:
                    print("Goodbye!")
                    break

                if user_input.lower() == 'status':
                    status = await self.moderator.get_agent_status()
                    print(f"ModeratorAgent Status:")
                    print(f"   • Total agents: {status['total_agents']}")
                    print(f"   • Enabled agents: {', '.join(self.enabled_agents)}")
                    for agent_type, agent_info in status['active_agents'].items():
                        print(f"   • {agent_type}: {agent_info['status']}")
                    continue

                # Process the query
                await self.test_query(user_input)

            except KeyboardInterrupt:
                print("\nGoodbye!")
                break
            except EOFError:
                print("\nGoodbye!")
                break

    async def cleanup(self):
        """Cleanup resources"""
        if self.moderator:
            print("\nCleaning up...")
            try:
                await self.moderator.cleanup_session()
                print("[OK] Cleanup completed")
            except Exception as e:
                print(f"[WARN]Cleanup warning: {e}")


async def main():
    """Main function to run the test"""
    print("ModeratorAgent Simple Test")
    print("=" * 40)

    if not MODERATOR_AVAILABLE:
        print("[ERROR] ModeratorAgent not available. Please check installation.")
        return

    # You can customize which agents to enable for testing
    enabled_agents = [
        'assistant',  # Core agent
        'web_search',
        'knowledge_base',
        'knowledge_synthesis',
        'web_scraper',
    ]

    # Create test instance
    test = SimpleModeratorTest(enabled_agents)

    try:
        # Setup the moderator
        await test.setup()

        # Ask user what they want to do
        print("\nWhat would you like to do?")
        print("1. Run automated test suite")
        print("2. Interactive mode (manual testing)")
        print("3. Both")

        choice = input("\nEnter choice (1/2/3): ").strip()

        if choice in ['1', '3']:
            print("\nRunning automated test suite...")
            await test.run_test_suite()

        if choice in ['2', '3']:
            await test.interactive_mode()

        if choice not in ['1', '2', '3']:
            print("[ERROR] Invalid choice, running automated test suite...")
            await test.run_test_suite()

    except Exception as e:
        print(f"[ERROR] Test failed: {e}")
        import traceback
        traceback.print_exc()

    finally:
        # Always cleanup
        await test.cleanup()


if __name__ == "__main__":
    """Run the test script"""
    print("Starting ModeratorAgent test...")

    # Check if agent_config.yaml exists
    import os

    if not os.path.exists("agent_config.yaml"):
        print("[WARN]Warning: agent_config.yaml not found in current directory")
        print("Make sure you have a valid configuration file")
        print("You can create one using the CLI: ambivo-agents config save-sample agent_config.yaml")

    # Run the test
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\nTest interrupted by user")
    except Exception as e:
        print(f"[ERROR] Test failed with error: {e}")
        import traceback

        traceback.print_exc()