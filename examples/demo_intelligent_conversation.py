"""
Demo Script for Intelligent Conversation System

This script demonstrates the multi-agent conversation system with various example queries
to showcase the intelligent orchestration of knowledge base, web search, and web scraping.
"""

import asyncio
import sys
import os
from datetime import datetime

# Add the parent directory to the path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from ambivo_agents.agents.knowledge_synthesis import KnowledgeSynthesisAgent
from ambivo_agents.agents.response_quality_assessor import QualityLevel
from ambivo_agents.core import AgentSession
import logging


class ConversationDemo:
    """Demo class for intelligent conversation system"""
    
    def __init__(self, user_id: str = "demo_user"):
        self.user_id = user_id
        self.moderator = None
        self.context = None
        
        # Setup logging
        logging.basicConfig(
            level=logging.INFO,
            format='%(asctime)s - %(levelname)s - %(message)s'
        )
        self.logger = logging.getLogger(__name__)
        
        # Demo queries showcasing different scenarios
        self.demo_queries = [
            {
                'query': 'What is quantum computing and how does it work?',
                'description': 'Technical query - should prioritize knowledge base',
                'expected_sources': ['knowledge_base']
            },
            {
                'query': 'What are the latest developments in AI in 2025?',
                'description': 'Current events query - should prioritize web search',
                'expected_sources': ['web_search', 'web_scrape']
            },
            {
                'query': 'prioritize web search over knowledge base - tell me about the current stock market trends',
                'description': 'User explicitly requests web search priority',
                'expected_sources': ['web_search']
            },
            {
                'query': 'What is the history of machine learning and what are the current trends?',
                'description': 'Complex query needing both historical and current info',
                'expected_sources': ['knowledge_base', 'web_search', 'web_scrape']
            },
            {
                'query': 'check knowledge base first - explain the fundamentals of blockchain technology',
                'description': 'User explicitly requests knowledge base priority',
                'expected_sources': ['knowledge_base']
            },
            {
                'query': 'comprehensive search - tell me everything about renewable energy trends, policies and market outlook',
                'description': 'Comprehensive query requiring all sources',
                'expected_sources': ['knowledge_base', 'web_search', 'web_scrape']
            }
        ]
    
    async def initialize(self):
        """Initialize the demo system"""
        print("\n" + "="*100)
        print("Intelligent Conversation System Demo")
        print("="*100)
        print("This demo showcases:")
        print("• Multi-source information gathering (Knowledge Base, Web Search, Web Scraping)")
        print("• Automatic response quality assessment")
        print("• Intelligent source prioritization based on query analysis")
        print("• User preference handling (explicit source prioritization)")
        print("• Iterative improvement until quality threshold is met")
        print("="*100)
        
        # Create enhanced moderator
        self.moderator, self.context = KnowledgeSynthesisAgent.create(
            user_id=self.user_id,
            quality_threshold=QualityLevel.GOOD,
            max_iterations=3,
            enable_auto_scraping=True,
            max_scrape_urls=2
        )
        
        print(f"\n[OK] System initialized with session ID: {self.context.session_id}")
        print(f"Quality threshold: {QualityLevel.GOOD.value}")
        print(f"User ID: {self.user_id}")
    
    async def run_demo_query(self, query_info: dict, query_index: int):
        """Run a single demo query and display results"""
        query = query_info['query']
        description = query_info['description']
        expected_sources = query_info['expected_sources']
        
        print(f"\n" + "="*80)
        print(f"Demo Query #{query_index}")
        print("="*80)
        print(f"Description: {description}")
        print(f"Query: {query}")
        print(f"Expected sources: {', '.join(expected_sources)}")
        print("\nProcessing...")
        
        # Detect user preferences from query
        user_preferences = {}
        query_lower = query.lower()
        if 'prioritize web search' in query_lower:
            user_preferences['prioritize'] = 'web_search'
        elif 'prioritize knowledge base' in query_lower or 'check knowledge base' in query_lower:
            user_preferences['prioritize'] = 'knowledge_base'
        elif 'comprehensive search' in query_lower or 'check all sources' in query_lower:
            user_preferences['search_all'] = True
        
        start_time = datetime.now()
        
        try:
            # Process the query using the process_with_quality_assessment method directly
            result = await self.moderator.process_with_quality_assessment(query, user_preferences)
            
            end_time = datetime.now()
            processing_time = (end_time - start_time).total_seconds()
            
            # Display results
            print("\n" + "RESULTS".center(60, "-"))
            
            # Response content (truncated for demo)
            response = result.get('response', 'No response generated')
            print(f"\nResponse: {response[:300]}...")
            
            # Quality assessment
            if 'quality_assessment' in result:
                qa = result['quality_assessment']
                quality_level = qa.get('quality_level', 'unknown')
                confidence = qa.get('confidence_score', 0)
                sources_used = qa.get('sources_used', [])
                
                # Quality indicator
                quality_emoji = {
                    'excellent': '',
                    'good': '[OK]',
                    'fair': '[WARN]',
                    'poor': '[ERROR]',
                    'unacceptable': ''
                }.get(quality_level, '')
                
                print(f"\n{quality_emoji} Quality: {quality_level} (confidence: {confidence:.1%})")
                print(f"Sources used: {', '.join(sources_used) if sources_used else 'None'}")
                
                # Check if expected sources were used
                expected_set = set(expected_sources)
                actual_set = set(sources_used)
                if expected_set.intersection(actual_set):
                    print("[OK] Expected sources were consulted")
                else:
                    print("[WARN]Expected sources may not have been fully consulted")
                
                # Show strengths and weaknesses
                if qa.get('strengths'):
                    print(f"\nStrengths:")
                    for strength in qa['strengths']:
                        print(f"   • {strength}")
                
                if qa.get('weaknesses'):
                    print(f"\n[WARN]Areas for improvement:")
                    for weakness in qa['weaknesses']:
                        print(f"   • {weakness}")
            
            # Query analysis
            if 'query_analysis' in result:
                analysis = result['query_analysis']
                print(f"\nQuery Analysis:")
                print(f"   • Query type: {analysis.get('query_type', 'unknown')}")
                print(f"   • Strategy used: {analysis.get('strategy_used', 'unknown')}")
                print(f"   • Sources consulted: {analysis.get('sources_consulted', 0)}")
            
            # Processing metadata
            metadata = result.get('metadata', {})
            print(f"\nProcessing Statistics:")
            print(f"   • Processing time: {processing_time:.2f} seconds")
            print(f"   • Iterations: {metadata.get('iterations', 1)}")
            print(f"   • Total sources consulted: {metadata.get('total_sources_consulted', 0)}")
            
            # Success indicator
            success_emoji = "" if quality_level in ['excellent', 'good'] else ""
            print(f"\n{success_emoji} Query processing {'completed successfully' if success_emoji == '' else 'completed with room for improvement'}")
            
        except Exception as e:
            print(f"\n[ERROR] Error processing query: {str(e)}")
            self.logger.error(f"Error in demo query {query_index}: {e}")
            import traceback
            traceback.print_exc()
    
    async def run_interactive_demo(self):
        """Run interactive demo where user can input custom queries"""
        print("\n" + "="*80)
        print("Interactive Demo Mode")
        print("="*80)
        print("Now you can test the system with your own queries!")
        print("Tips:")
        print("• Try 'prioritize web search - <your query>' for web-first strategy")
        print("• Try 'check knowledge base first - <your query>' for KB-first strategy")
        print("• Try 'comprehensive search - <your query>' for all sources")
        print("• Type 'exit' to end the demo")
        print("="*80)
        
        while True:
            try:
                user_query = input("\nYour query: ").strip()
                
                if user_query.lower() in ['exit', 'quit', 'done']:
                    break
                
                if not user_query:
                    continue
                
                # Process custom query
                await self.run_demo_query({
                    'query': user_query,
                    'description': 'Custom user query',
                    'expected_sources': ['varies']
                }, 'custom')
                
            except (EOFError, KeyboardInterrupt):
                break
    
    async def run_full_demo(self):
        """Run the complete demo"""
        await self.initialize()
        
        # Run predefined demo queries
        for i, query_info in enumerate(self.demo_queries, 1):
            await self.run_demo_query(query_info, i)
            
            # Small pause between queries
            if i < len(self.demo_queries):
                input("\nPress Enter to continue to next demo query...")
        
        # Ask if user wants interactive demo
        print("\n" + "="*80)
        print("Predefined demo completed!")
        
        try:
            run_interactive = input("\nWould you like to try the interactive demo? (y/n): ").strip().lower()
            if run_interactive in ['y', 'yes']:
                await self.run_interactive_demo()
        except (EOFError, KeyboardInterrupt):
            pass
        
        # Summary
        print("\n" + "="*80)
        print("Demo Summary")
        print("="*80)
        print(f"[OK] Completed {len(self.demo_queries)} predefined demo queries")
        print("Demonstrated multi-source information gathering")
        print("Showed automatic quality assessment and improvement")
        print("Showcased intelligent query analysis and source selection")
        print("Highlighted user preference handling")
        
        # Cleanup
        await self.cleanup()
    
    async def cleanup(self):
        """Clean up resources"""
        print("\nCleaning up demo resources...")
        if self.moderator:
            await self.moderator.cleanup_session()
        print("[OK] Demo cleanup completed")


async def main():
    """Main entry point for the demo"""
    print("Starting Intelligent Conversation System Demo...")
    
    demo = ConversationDemo("demo_user_" + datetime.now().strftime("%Y%m%d_%H%M%S"))
    
    try:
        await demo.run_full_demo()
        print("\nThank you for trying the Intelligent Conversation System Demo!")
        
    except KeyboardInterrupt:
        print("\n\nDemo interrupted by user")
        await demo.cleanup()
        
    except Exception as e:
        print(f"\n[ERROR] Demo failed with error: {e}")
        import traceback
        traceback.print_exc()
        await demo.cleanup()


if __name__ == "__main__":
    asyncio.run(main())