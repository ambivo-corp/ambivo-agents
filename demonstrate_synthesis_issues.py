#!/usr/bin/env python3
"""
Demonstration Script: Knowledge Synthesis Agent Issues

This script provides clear, focused demonstrations of the three main issues:
1. Knowledge Base Query Format Problems
2. Search Term Optimization Issues  
3. KB Collection Targeting Problems

Each issue is demonstrated with before/after examples and timing data.
"""

import asyncio
import time
from datetime import datetime
import sys
import os

# Add the parent directory to the path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from ambivo_agents.agents.knowledge_synthesis import KnowledgeSynthesisAgent
from ambivo_agents.agents.response_quality_assessor import QualityLevel
from ambivo_agents.agents.knowledge_base import KnowledgeBaseAgent

class SynthesisIssuesDemonstrator:
    """Demonstrates the three main Knowledge Synthesis issues clearly"""
    
    def __init__(self):
        self.synthesis_agent = None
        self.kb_agent = None
        self.context = None
        
    async def setup(self):
        """Setup agents for demonstration"""
        print("Setting up agents for issue demonstration...")
        
        # Create Knowledge Synthesis Agent
        self.synthesis_agent, self.context = KnowledgeSynthesisAgent.create(
            user_id="demo_issues",
            quality_threshold=QualityLevel.GOOD,
            max_iterations=2,  # Limit for faster demos
            enable_auto_scraping=False,  # Disable for cleaner demos
            max_scrape_urls=1
        )
        
        # Create standalone KB agent for comparison
        self.kb_agent = KnowledgeBaseAgent.create_simple(user_id="kb_demo")
        
        print(f"[OK] Setup complete - Session: {self.context.session_id}")
        print()

    async def demonstrate_issue_1_kb_format_problems(self):
        """Demonstrate Issue 1: KB Query Format Problems"""
        print("=" * 80)
        print("ISSUE 1: KNOWLEDGE BASE QUERY FORMAT PROBLEMS")
        print("=" * 80)
        print()
        
        test_queries = [
            "What are cryptocurrency trends?",
            "Tell me about robotics developments",
            "What's happening with blockchain technology?"
        ]
        
        print("**Problem**: Natural language queries fail with KB agent")
        print("**Expected**: Automatic collection detection and content retrieval")
        print("**Actual**: Format requirement messages")
        print()
        
        for i, query in enumerate(test_queries, 1):
            print(f"--- Test {i}: {query} ---")
            
            # Test direct KB agent
            print("Direct KnowledgeBaseAgent:")
            start_time = time.time()
            try:
                kb_response = await self.kb_agent.chat(query)
                kb_time = time.time() - start_time
                
                print(f"   Time: {kb_time:.2f}s")
                print(f"   Response: {kb_response[:100]}...")
                
                if "Please specify: `Query [kb_name]:" in kb_response:
                    print("   [ERROR] Issue Confirmed: Format requirement instead of content")
                else:
                    print("   [OK] Working: Returned actual content")
                    
            except Exception as e:
                print(f"   [ERROR] Error: {e}")
            
            print()
            
        print("**Root Cause**: KnowledgeBaseAgent lacks automatic collection detection")
        print("**Solution Needed**: Implement query-to-collection mapping logic")
        print()

    async def demonstrate_issue_2_search_optimization(self):
        """Demonstrate Issue 2: Search Term Optimization Problems"""
        print("=" * 80)
        print("ISSUE 2: SEARCH TERM OPTIMIZATION PROBLEMS")
        print("=" * 80)
        print()
        
        problematic_queries = [
            {
                'query': 'emerging trends cryptocurrency robotics',
                'problem': 'Too broad - combines unrelated topics',
                'better': 'cryptocurrency market trends 2025'
            },
            {
                'query': 'AI developments 2025 latest',
                'problem': 'Generic terms with redundant words',
                'better': 'artificial intelligence breakthroughs 2025'
            },
            {
                'query': 'blockchain applications sustainability',
                'problem': 'Multiple competing concepts',
                'better': 'sustainable blockchain technology'
            }
        ]
        
        print("**Problem**: Poor search query optimization leads to no results")
        print("**Expected**: Smart query transformation for better results")
        print("**Actual**: Generic transformations with poor results")
        print()
        
        for i, test_case in enumerate(problematic_queries, 1):
            print(f"--- Test {i}: Search Optimization ---")
            print(f"Problematic Query: '{test_case['query']}'")
            print(f"Problem: {test_case['problem']}")
            print(f"Better Query: '{test_case['better']}'")
            print()
            
            # Test current behavior
            print("Current KnowledgeSynthesisAgent behavior:")
            start_time = time.time()
            try:
                # Force web search priority to focus on search optimization
                web_query = f"prioritize web search - {test_case['query']}"
                result = await self.synthesis_agent.process_with_quality_assessment(web_query)
                
                processing_time = time.time() - start_time
                response = result.get('response', '')
                quality = result.get('quality_assessment', {})
                
                print(f"   Time: {processing_time:.2f}s")
                print(f"   Quality: {quality.get('quality_level', 'unknown')}")
                print(f"   Result Count: {self._count_results(response)}")
                
                if self._count_results(response) == 0:
                    print("   [ERROR] Issue Confirmed: No results found")
                elif self._count_results(response) < 3:
                    print("   [WARN]Issue Confirmed: Poor result count")
                else:
                    print("   [OK] Working: Good result count")
                    
            except Exception as e:
                print(f"   [ERROR] Error: {e}")
            
            print()
            
        print("**Root Cause**: No intelligent query optimization before web search")
        print("**Solution Needed**: Implement query analysis and term optimization")
        print()

    def _count_results(self, response: str) -> int:
        """Count search results in response"""
        import re
        pattern = r'\*\*\d+\.\s+.*?\*\*'
        matches = re.findall(pattern, response)
        
        # Also check for "Found X results"
        found_pattern = r'Found\s+(\d+)\s+results?:'
        found_match = re.search(found_pattern, response, re.IGNORECASE)
        if found_match:
            return int(found_match.group(1))
            
        return len(matches)

    async def demonstrate_issue_3_collection_targeting(self):
        """Demonstrate Issue 3: KB Collection Targeting Problems"""
        print("=" * 80)
        print("ISSUE 3: KB COLLECTION TARGETING PROBLEMS")
        print("=" * 80)
        print()
        
        available_collections = [
            "research_trends_in_cryptocurrency_20250816_193439",
            "research_trends_in_robotics_tech_2025_20250812_172007"
        ]
        
        targeting_tests = [
            {
                'query': 'cryptocurrency market analysis',
                'keywords': ['cryptocurrency', 'crypto', 'bitcoin', 'blockchain'],
                'expected_collection': 'research_trends_in_cryptocurrency_20250816_193439'
            },
            {
                'query': 'robotics and AI automation trends',
                'keywords': ['robotics', 'robot', 'AI', 'automation'],
                'expected_collection': 'research_trends_in_robotics_tech_2025_20250812_172007'
            }
        ]
        
        print("**Problem**: No automatic collection detection for domain-specific queries")
        print("**Expected**: Smart routing to relevant collections")
        print("**Actual**: Manual format specification required")
        print()
        print(f"Available Collections:")
        for collection in available_collections:
            print(f"   • {collection}")
        print()
        
        for i, test_case in enumerate(targeting_tests, 1):
            print(f"--- Test {i}: Collection Targeting ---")
            print(f"Query: '{test_case['query']}'")
            print(f"Keywords: {test_case['keywords']}")
            print(f"Expected Collection: {test_case['expected_collection'].split('_')[3]}")
            print()
            
            # Test automatic targeting
            print("Automatic Collection Targeting:")
            start_time = time.time()
            try:
                result = await self.synthesis_agent.process_with_quality_assessment(test_case['query'])
                processing_time = time.time() - start_time
                
                response = result.get('response', '')
                quality = result.get('quality_assessment', {})
                sources_used = quality.get('sources_used', [])
                
                print(f"   Time: {processing_time:.2f}s")
                print(f"   Quality: {quality.get('quality_level', 'unknown')}")
                print(f"   Sources Used: {sources_used}")
                
                # Check if KB was accessed successfully
                if 'knowledge_base' in sources_used and "Please specify: `Query [kb_name]:" not in response:
                    print("   [OK] Working: KB successfully accessed")
                    # Check if content matches expected domain
                    content_matches = sum(1 for keyword in test_case['keywords'] 
                                        if keyword.lower() in response.lower())
                    print(f"   Domain Relevance: {content_matches}/{len(test_case['keywords'])} keywords found")
                elif 'knowledge_base' in sources_used:
                    print("   [ERROR] Issue Confirmed: KB access failed (format requirement)")
                else:
                    print("   [ERROR] Issue Confirmed: KB not consulted (web search only)")
                    
            except Exception as e:
                print(f"   [ERROR] Error: {e}")
            
            print()
            
            # Test explicit targeting
            print("Explicit Collection Targeting:")
            explicit_query = f"Query {test_case['expected_collection']}: {test_case['query']}"
            start_time = time.time()
            try:
                result = await self.synthesis_agent.process_with_quality_assessment(explicit_query)
                processing_time = time.time() - start_time
                
                response = result.get('response', '')
                quality = result.get('quality_assessment', {})
                
                print(f"   Time: {processing_time:.2f}s")
                print(f"   Quality: {quality.get('quality_level', 'unknown')}")
                
                if "Please specify: `Query [kb_name]:" not in response and len(response) > 100:
                    print("   [OK] Explicit Format Works: KB content retrieved")
                else:
                    print("   [ERROR] Even Explicit Format Failed")
                    
            except Exception as e:
                print(f"   [ERROR] Error: {e}")
            
            print()
            
        print("**Root Cause**: No semantic analysis for collection targeting")
        print("**Solution Needed**: Implement keyword-to-collection mapping system")
        print()

    async def run_comprehensive_demonstration(self):
        """Run all issue demonstrations"""
        print("KNOWLEDGE SYNTHESIS AGENT ISSUES DEMONSTRATION")
        print("=" * 80)
        print(f"Session Date: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        print("Purpose: Demonstrate three critical issues affecting user experience")
        print()
        
        try:
            await self.setup()
            
            # Run all demonstrations
            await self.demonstrate_issue_1_kb_format_problems()
            await self.demonstrate_issue_2_search_optimization()
            await self.demonstrate_issue_3_collection_targeting()
            
            # Summary
            print("=" * 80)
            print("ISSUES SUMMARY")
            print("=" * 80)
            print("[ERROR] **Issue 1**: KB queries require manual format specification")
            print("[ERROR] **Issue 2**: Search optimization produces poor/no results")
            print("[ERROR] **Issue 3**: No automatic collection targeting based on query content")
            print()
            print("**Impact**: Users experience technical barriers and poor-quality responses")
            print("**Next Steps**: Implement intelligent query routing and optimization")
            print()
            
        except Exception as e:
            print(f"[ERROR] Demonstration failed: {e}")
            import traceback
            traceback.print_exc()
            
        finally:
            await self.cleanup()

    async def cleanup(self):
        """Clean up resources"""
        print("Cleaning up demonstration resources...")
        try:
            if self.synthesis_agent:
                await self.synthesis_agent.cleanup_session()
            if self.kb_agent:
                await self.kb_agent.cleanup_session()
        except Exception as e:
            print(f"[WARN]Cleanup warning: {e}")
        print("[OK] Cleanup complete")

async def main():
    """Run the comprehensive demonstration"""
    demonstrator = SynthesisIssuesDemonstrator()
    await demonstrator.run_comprehensive_demonstration()

if __name__ == "__main__":
    asyncio.run(main())