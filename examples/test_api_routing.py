#!/usr/bin/env python3
"""
Test API Agent Routing via ModeratorAgent

This script tests whether the ModeratorAgent correctly routes API-related requests 
to the APIAgent using LLM-based intent analysis.
"""

import asyncio
import json
from ambivo_agents import ModeratorAgent


async def test_api_routing():
    """Test various API-related requests to verify routing to APIAgent"""
    print("🧪 Testing API Agent Routing via ModeratorAgent")
    print("=" * 60)
    
    # Create moderator with API agent enabled
    moderator = ModeratorAgent.create_simple(
        user_id="test_user",
        enabled_agents=['assistant', 'api_agent', 'web_search']
    )
    
    # Test cases that should route to APIAgent
    api_test_cases = [
        "GET https://jsonplaceholder.typicode.com/posts/1",
        "POST https://api.example.com/users with data {\"name\": \"John\"}",
        "Call the GitHub API to get user information",
        "Make an HTTP request to fetch weather data",
        "Send a POST request with authentication headers",
        "I need to integrate with a REST API",
        "Can you call this API endpoint for me?",
        "Authenticate with Google API and fetch my sheets",
        "PUT request to update user profile via API",
        "DELETE https://api.example.com/posts/123"
    ]
    
    # Test cases that should NOT route to APIAgent
    non_api_test_cases = [
        "What is machine learning?",
        "Search for Python tutorials",
        "Tell me a joke",
        "Explain how neural networks work"
    ]
    
    try:
        print("🔍 Testing API-related requests (should route to api_agent):")
        print("-" * 50)
        
        for i, test_case in enumerate(api_test_cases[:5]):  # Test first 5
            print(f"\n{i+1}. Testing: '{test_case}'")
            
            # Analyze intent to see routing decision
            try:
                analysis = await moderator._analyze_user_intent(test_case)
                primary_agent = analysis.get('primary_agent', 'unknown')
                confidence = analysis.get('confidence', 0.0)
                reasoning = analysis.get('reasoning', 'No reasoning provided')
                
                if primary_agent == 'api_agent':
                    print(f"   ✅ CORRECT: Routed to {primary_agent} (confidence: {confidence:.2f})")
                else:
                    print(f"   ❌ INCORRECT: Routed to {primary_agent} instead of api_agent")
                
                print(f"   💭 Reasoning: {reasoning[:100]}...")
                
            except Exception as e:
                print(f"   ❌ ERROR: Failed to analyze intent: {str(e)}")
        
        print("\n" + "=" * 60)
        print("🔍 Testing non-API requests (should NOT route to api_agent):")
        print("-" * 50)
        
        for i, test_case in enumerate(non_api_test_cases):
            print(f"\n{i+1}. Testing: '{test_case}'")
            
            try:
                analysis = await moderator._analyze_user_intent(test_case)
                primary_agent = analysis.get('primary_agent', 'unknown')
                confidence = analysis.get('confidence', 0.0)
                
                if primary_agent != 'api_agent':
                    print(f"   ✅ CORRECT: Routed to {primary_agent} (not api_agent)")
                else:
                    print(f"   ❌ INCORRECT: Incorrectly routed to api_agent")
                    
            except Exception as e:
                print(f"   ❌ ERROR: Failed to analyze intent: {str(e)}")
        
        print("\n" + "=" * 60)
        print("🧪 Testing actual conversation routing:")
        print("-" * 50)
        
        # Test actual conversation routing
        test_api_request = "GET https://jsonplaceholder.typicode.com/posts/1"
        print(f"\nSending: '{test_api_request}'")
        
        response = await moderator.chat(test_api_request)
        print(f"Response: {response[:200]}{'...' if len(response) > 200 else ''}")
        
        # Check if it actually used the API agent
        if "API" in response or "HTTP" in response or "200" in response:
            print("✅ Response indicates API agent was likely used")
        else:
            print("❓ Response doesn't clearly indicate API agent usage")
            
    except Exception as e:
        print(f"❌ Test failed with error: {str(e)}")
        
    finally:
        await moderator.cleanup_session()


async def test_api_workflow_detection():
    """Test if moderator can detect complex API workflows"""
    print("\n🔗 Testing API Workflow Detection")
    print("=" * 60)
    
    moderator = ModeratorAgent.create_simple(
        user_id="workflow_user",
        enabled_agents=['assistant', 'api_agent', 'web_search']
    )
    
    try:
        # Complex workflow examples
        workflow_cases = [
            "First authenticate with Google OAuth, then fetch my Google Sheets data",
            "Call the GitHub API to get user repos, then for each repo get the commit history",
            "Get access token from auth endpoint, then use it to call the main API",
            "POST user data to API, wait for response, then GET the created resource"
        ]
        
        for i, test_case in enumerate(workflow_cases[:2]):  # Test first 2
            print(f"\n{i+1}. Testing workflow: '{test_case}'")
            
            try:
                analysis = await moderator._analyze_user_intent(test_case)
                
                workflow_detected = analysis.get('workflow_detected', False)
                requires_multiple = analysis.get('requires_multiple_agents', False)
                agent_chain = analysis.get('agent_chain', [])
                
                print(f"   Workflow detected: {workflow_detected}")
                print(f"   Multiple agents required: {requires_multiple}")
                print(f"   Agent chain: {agent_chain}")
                
                if 'api_agent' in agent_chain:
                    print("   ✅ API agent included in workflow")
                else:
                    print("   ❌ API agent missing from workflow")
                    
            except Exception as e:
                print(f"   ❌ ERROR: {str(e)}")
                
    finally:
        await moderator.cleanup_session()


async def main():
    """Run all routing tests"""
    print("🚀 API Agent Routing Tests")
    print("Testing whether ModeratorAgent correctly routes API requests to APIAgent")
    print("\n")
    
    await test_api_routing()
    await test_api_workflow_detection()
    
    print("\n" + "=" * 60)
    print("✅ All routing tests completed!")
    print("\n💡 Key Points:")
    print("- ModeratorAgent uses LLM-based intent analysis for routing")
    print("- API-related requests should be routed to api_agent")
    print("- Complex workflows can involve multiple agents including api_agent")
    print("- The system provides detailed reasoning for routing decisions")


if __name__ == "__main__":
    asyncio.run(main())