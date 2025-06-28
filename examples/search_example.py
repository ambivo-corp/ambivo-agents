#!/usr/bin/env python3
"""
simple_web_search_demo.py
Production-ready Web Search Demo using Ambivo Agents
Based on the reference script pattern with real API testing and rate limiting

Author: Hemant Gosain 'Sunny'
Company: Ambivo
Email: sgosain@ambivo.com
License: MIT
"""

import asyncio
import os
import sys
import time
import json
from pathlib import Path
from datetime import datetime

# Add the ambivo_agents package to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from ambivo_agents.services import create_agent_service


class SimpleWebSearchDemo:
    """Simple, production-ready web search demonstration"""

    def __init__(self):
        print("🔍 Simple Web Search Demo - Production Ready")
        print("=" * 55)

        # Create agent service
        self.agent_service = create_agent_service()

        # Create session
        self.session_id = self.agent_service.create_session()
        self.user_id = "web_search_user"

        # Setup output directory
        self.output_dir = Path("./search_results")
        self.output_dir.mkdir(exist_ok=True)

        print(f"📁 Output directory: {self.output_dir.absolute()}")

    async def check_web_search_availability(self):
        """Check if web search agent is available and working"""
        print("\n🔍 Checking Web Search Agent Availability...")

        health = self.agent_service.health_check()
        available_agents = health.get('available_agent_types', {})
        enabled_capabilities = health.get('enabled_capabilities', [])

        print(f"🤖 Available Agents: {available_agents}")
        print(f"⚡ Enabled Capabilities: {enabled_capabilities}")

        if available_agents.get('web_search', False):
            print("✅ Web Search Agent is available")
            return True
        else:
            print("❌ Web Search Agent is not available")
            print("Please ensure web_search is enabled in agent_config.yaml")
            print("Check your search API keys (Brave, AVES) are configured")
            return False

    async def test_single_search(self, query: str, search_type: str = "web", max_results: int = 5):
        """Test a single search query with proper error handling"""
        print(f"\n🔍 Testing {search_type} search: '{query}'")
        print("-" * 50)

        # Construct the message based on search type
        if search_type == "web":
            message = f"""Search the web for: {query}

Use the search_web tool with these parameters:
- query: {query}
- max_results: {max_results}
- country: US
- language: en

Please provide detailed results with titles, URLs, and snippets."""

        elif search_type == "news":
            message = f"""Search for recent news about: {query}

Use the search_news tool with these parameters:
- query: {query}
- max_results: {max_results}
- days_back: 7

Find recent news articles and developments."""

        elif search_type == "academic":
            message = f"""Search for academic content about: {query}

Use the search_academic tool with these parameters:
- query: {query}
- max_results: {max_results}

Find research papers and scholarly articles."""

        start_time = time.time()

        try:
            result = await self.agent_service.process_message(
                message=message,
                session_id=self.session_id,
                user_id=self.user_id,
                conversation_id=f"{search_type}_search_test"
            )

            search_time = time.time() - start_time

            if result['success']:
                print(f"✅ {search_type.title()} search successful in {search_time:.2f}s")

                response_content = result['response']
                print(f"📝 Response length: {len(response_content)} characters")

                # Display key parts of the response
                print(f"\n📄 Search Results Preview:")
                print("-" * 30)
                print(response_content[:800] + "..." if len(response_content) > 800 else response_content)

                # Save results
                await self.save_search_result(query, search_type, response_content, search_time)

                return {
                    'success': True,
                    'query': query,
                    'search_type': search_type,
                    'response': response_content,
                    'search_time': search_time,
                    'provider_info': result.get('metadata', {})
                }
            else:
                print(f"❌ {search_type.title()} search failed: {result['error']}")

                # Provide specific guidance based on error type
                error_str = str(result['error']).lower()
                if '429' in error_str or 'rate limit' in error_str:
                    print("🕒 Rate limit detected - try again in a few minutes")
                elif '401' in error_str or 'authentication' in error_str:
                    print("🔑 Authentication issue - check API keys in agent_config.yaml")
                elif 'timeout' in error_str:
                    print("⏰ Request timeout - try again or increase timeout settings")
                else:
                    print("🔧 Check logs for more details")

                return {
                    'success': False,
                    'query': query,
                    'search_type': search_type,
                    'error': result['error'],
                    'search_time': search_time
                }

        except Exception as e:
            search_time = time.time() - start_time
            print(f"❌ Exception during {search_type} search: {str(e)}")
            return {
                'success': False,
                'query': query,
                'search_type': search_type,
                'error': str(e),
                'search_time': search_time
            }

    async def search_about_ambivo(self):
        """Comprehensive search about Ambivo with different query variations"""
        print("\n🏢 Searching for Information About Ambivo")
        print("=" * 45)

        ambivo_queries = [
            ("what is ambivo", "web"),
            ("ambivo company AI platform", "web"),
            ("ambivo artificial intelligence", "news"),
            ("ambivo technology solutions", "web")
        ]

        all_results = []

        for i, (query, search_type) in enumerate(ambivo_queries, 1):
            print(f"\n--- Ambivo Search {i}/{len(ambivo_queries)} ---")

            # Add delay between searches to respect rate limits
            if i > 1:
                print("⏳ Waiting to respect rate limits...")
                await asyncio.sleep(3)

            result = await self.test_single_search(query, search_type, max_results=5)
            all_results.append(result)

        # Analyze Ambivo search results
        print(f"\n📊 Ambivo Search Summary")
        print("-" * 30)

        successful_searches = [r for r in all_results if r['success']]
        failed_searches = [r for r in all_results if not r['success']]

        print(f"✅ Successful searches: {len(successful_searches)}/{len(all_results)}")
        print(f"❌ Failed searches: {len(failed_searches)}")

        if successful_searches:
            avg_time = sum(r['search_time'] for r in successful_searches) / len(successful_searches)
            print(f"⏱️  Average search time: {avg_time:.2f}s")

            # Save consolidated Ambivo results
            await self.save_ambivo_research(all_results)

        return all_results

    async def test_search_providers(self):
        """Test different search types with sample queries"""
        print("\n🧪 Testing Different Search Types")
        print("=" * 35)

        test_cases = [
            ("Python programming best practices", "web"),
            ("artificial intelligence latest news", "news"),
            ("machine learning research papers", "academic")
        ]

        results = []

        for i, (query, search_type) in enumerate(test_cases, 1):
            print(f"\n--- Test Case {i}/{len(test_cases)} ---")

            # Add delay between different search types
            if i > 1:
                print("⏳ Waiting between search types...")
                await asyncio.sleep(4)

            result = await self.test_single_search(query, search_type, max_results=3)
            results.append(result)

        # Test summary
        print(f"\n📊 Provider Test Summary")
        print("-" * 25)

        for search_type in ["web", "news", "academic"]:
            type_results = [r for r in results if r.get('search_type') == search_type]
            if type_results:
                success_rate = len([r for r in type_results if r['success']]) / len(type_results)
                print(f"{search_type.title()}: {success_rate:.0%} success rate")

        return results

    async def save_search_result(self, query: str, search_type: str, response: str, search_time: float):
        """Save individual search result to file"""
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")

        # Create result data
        result_data = {
            'query': query,
            'search_type': search_type,
            'response': response,
            'search_time': search_time,
            'timestamp': timestamp,
            'searched_at': datetime.now().isoformat()
        }

        # Save as JSON
        filename = f"{search_type}_{query.replace(' ', '_')[:20]}_{timestamp}.json"
        filepath = self.output_dir / filename

        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump(result_data, f, indent=2, ensure_ascii=False)

        print(f"💾 Saved result: {filepath.name}")

    async def save_ambivo_research(self, results: list):
        """Save consolidated Ambivo research results"""
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")

        # Create comprehensive Ambivo research file
        research_data = {
            'research_topic': 'Ambivo Company Information',
            'total_searches': len(results),
            'successful_searches': len([r for r in results if r['success']]),
            'timestamp': timestamp,
            'results': results
        }

        # Save JSON data
        json_file = self.output_dir / f"ambivo_research_{timestamp}.json"
        with open(json_file, 'w', encoding='utf-8') as f:
            json.dump(research_data, f, indent=2, ensure_ascii=False)

        # Save readable summary
        summary_file = self.output_dir / f"ambivo_research_summary_{timestamp}.txt"
        with open(summary_file, 'w', encoding='utf-8') as f:
            f.write("AMBIVO COMPANY RESEARCH SUMMARY\n")
            f.write("=" * 40 + "\n\n")
            f.write(f"Generated on: {datetime.now().isoformat()}\n")
            f.write(f"Total searches performed: {len(results)}\n")
            f.write(f"Successful searches: {len([r for r in results if r['success']])}\n\n")

            for i, result in enumerate(results, 1):
                f.write(f"\nSEARCH {i}: {result['query']} ({result['search_type']})\n")
                f.write("-" * 50 + "\n")

                if result['success']:
                    f.write(f"Status: ✅ Success\n")
                    f.write(f"Time: {result['search_time']:.2f}s\n")
                    f.write(f"Response: {result['response'][:500]}...\n")
                else:
                    f.write(f"Status: ❌ Failed\n")
                    f.write(f"Error: {result['error']}\n")

                f.write("\n")

        print(f"📝 Saved Ambivo research: {json_file.name}")
        print(f"📄 Saved summary: {summary_file.name}")

    async def run_demo(self, demo_type: str = "ambivo"):
        """Run the demonstration based on type"""

        # Check if web search is available
        if not await self.check_web_search_availability():
            print("❌ Cannot proceed - Web Search agent not available")
            return False

        try:
            if demo_type == "ambivo":
                print("\n🎯 Running Ambivo-focused search demo...")
                results = await self.search_about_ambivo()

            elif demo_type == "providers":
                print("\n🧪 Running search provider testing...")
                results = await self.test_search_providers()

            elif demo_type == "comprehensive":
                print("\n🚀 Running comprehensive demo...")
                ambivo_results = await self.search_about_ambivo()
                provider_results = await self.test_search_providers()
                results = ambivo_results + provider_results

            else:
                print(f"❌ Unknown demo type: {demo_type}")
                return False

            # Final summary
            print(f"\n🎉 Demo Completed Successfully!")
            print(f"📊 Total searches: {len(results)}")
            print(f"✅ Successful: {len([r for r in results if r['success']])}")
            print(f"❌ Failed: {len([r for r in results if not r['success']])}")
            print(f"📁 Results saved to: {self.output_dir}")

            return True

        except Exception as e:
            print(f"\n❌ Demo failed with error: {e}")
            import traceback
            traceback.print_exc()
            return False

    async def cleanup(self):
        """Clean up demo resources"""
        print("\n🧹 Cleaning up demo resources...")

        if self.session_id:
            success = self.agent_service.delete_session(self.session_id)
            if success:
                print(f"✅ Deleted demo session: {self.session_id}")

        print("✅ Cleanup completed")


async def main():
    """Main function to run the web search demo"""
    import argparse

    parser = argparse.ArgumentParser(description="Simple Web Search Demo")
    parser.add_argument("--demo", choices=["ambivo", "providers", "comprehensive"],
                        default="ambivo", help="Type of demo to run")
    parser.add_argument("--query", help="Single query to search")
    parser.add_argument("--type", choices=["web", "news", "academic"],
                        default="web", help="Search type for single query")

    args = parser.parse_args()

    try:
        demo = SimpleWebSearchDemo()

        if args.query:
            # Run single query test
            print(f"🎯 Testing single query: '{args.query}' (type: {args.type})")

            if await demo.check_web_search_availability():
                result = await demo.test_single_search(args.query, args.type, max_results=5)

                if result['success']:
                    print(f"\n✅ Query successful!")
                else:
                    print(f"\n❌ Query failed: {result['error']}")
        else:
            # Run selected demo type
            success = await demo.run_demo(args.demo)

            if success:
                print("\n💡 Next steps:")
                print("  - Check the search_results/ directory for saved data")
                print("  - Review agent_config.yaml for rate limiting settings")
                print("  - Monitor API usage and quotas")
            else:
                print("\n🔧 Troubleshooting:")
                print("  - Verify API keys in agent_config.yaml")
                print("  - Check internet connectivity")
                print("  - Wait a few minutes if rate limited")

        await demo.cleanup()

    except KeyboardInterrupt:
        print("\n\n⚠️  Demo interrupted by user")
    except Exception as e:
        print(f"\n\n❌ Demo failed with error: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    asyncio.run(main())