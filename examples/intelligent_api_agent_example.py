#!/usr/bin/env python3
"""
Intelligent API Agent Examples - Documentation Parsing and Smart API Calls

This example demonstrates the enhanced APIAgent's intelligent capabilities:
- Parse API documentation (OpenAPI/Swagger, HTML, any format)
- Automatically discover and understand endpoints
- Match user requests to appropriate API endpoints
- Construct and execute API calls based on documentation
- Handle authentication automatically
"""

import asyncio
import json
from typing import Dict, Any

from ambivo_agents.agents.api_agent import (
    APIAgent, APIRequest, AuthConfig, HTTPMethod, AuthType, APIDocumentation
)


async def example_parse_openapi_documentation():
    """Example 1: Parse OpenAPI/Swagger documentation and make intelligent API calls"""
    print("Example 1: Intelligent OpenAPI Documentation Parsing")
    print("=" * 70)
    
    agent = APIAgent.create_simple(user_id="intelligent_user")
    
    try:
        # Example: Parse JSONPlaceholder API docs and make calls
        doc_url = "https://jsonplaceholder.typicode.com"  # This would be an actual OpenAPI spec URL
        
        # Simulate the intelligent request your user case
        user_request = f"Please read documentation at {doc_url} and then call the get posts API"
        
        print(f"User Request: '{user_request}'")
        print("\nProcessing intelligent API request...")
        
        # The agent will automatically:
        # 1. Parse the documentation
        # 2. Find the appropriate endpoint
        # 3. Construct and execute the API call
        response = await agent.chat(user_request)
        
        print(f"\n[OK] Agent Response:")
        print(response)
        
    except Exception as e:
        print(f"[ERROR] Error: {str(e)}")
    
    finally:
        await agent.cleanup_session()


async def example_parse_html_documentation():
    """Example 2: Parse HTML documentation using LLM intelligence"""
    print("\nExample 2: HTML Documentation Parsing with LLM")
    print("=" * 70)
    
    agent = APIAgent.create_simple(user_id="html_parser")
    
    try:
        # Example with HTML documentation
        doc_url = "https://docs.github.com/en/rest"
        token = "ghp_example_token_12345"
        
        user_request = f"Read docs at {doc_url} and use token {token} to get user information"
        
        print(f"User Request: '{user_request}'")
        print("\nThe agent will:")
        print("   1. Fetch and parse HTML documentation")
        print("   2. Use LLM to extract API endpoints")
        print("   3. Find the user info endpoint")
        print("   4. Make authenticated API call")
        
        response = await agent.chat(user_request)
        print(f"\n[OK] Agent Response:")
        print(response[:500] + "..." if len(response) > 500 else response)
        
    except Exception as e:
        print(f"[ERROR] Error: {str(e)}")
    
    finally:
        await agent.cleanup_session()


async def example_ambivo_api_documentation():
    """Example 3: Your specific use case - Ambivo API documentation"""
    print("\nExample 3: Ambivo API Documentation Parsing")
    print("=" * 70)
    
    agent = APIAgent.create_simple(user_id="ambivo_user")
    
    try:
        # Your exact use case
        doc_url = "https://fapi.ambivo.com/docs"
        token = "your_actual_token_here"
        
        user_requests = [
            f"Please read documentation at {doc_url} and then use token {token} to call the get contacts API",
            f"Parse docs at {doc_url} and with token {token} get user profile",
            f"Read docs from {doc_url} and call the create contact endpoint with token {token}",
            f"Documentation at {doc_url} - use auth {token} to fetch all users"
        ]
        
        for i, request in enumerate(user_requests, 1):
            print(f"\nTest {i}: '{request}'")
            print("Processing...")
            
            try:
                response = await agent.chat(request)
                print(f"[OK] Response: {response[:200]}{'...' if len(response) > 200 else ''}")
            except Exception as e:
                print(f"[ERROR] Error: {str(e)}")
        
    finally:
        await agent.cleanup_session()


async def example_manual_documentation_parsing():
    """Example 4: Manual documentation parsing and endpoint discovery"""
    print("\nExample 4: Manual Documentation Parsing Methods")
    print("=" * 70)
    
    agent = APIAgent.create_simple(user_id="manual_user")
    
    try:
        # Example: Manually parse documentation
        doc_url = "https://jsonplaceholder.typicode.com"
        
        print(f"Parsing documentation from: {doc_url}")
        
        # Step 1: Parse documentation
        api_doc = await agent.parse_api_documentation(doc_url)
        
        print(f"[OK] Documentation parsed successfully!")
        print(f"   Title: {api_doc.title}")
        print(f"   Base URL: {api_doc.base_url}")
        print(f"   Description: {api_doc.description}")
        print(f"   Auth Info: {api_doc.auth_info}")
        print(f"   Endpoints found: {len(api_doc.endpoints)}")
        
        # Step 2: Show available endpoints
        print(f"\nAvailable Endpoints:")
        for i, endpoint in enumerate(api_doc.endpoints[:5]):  # Show first 5
            print(f"   {i+1}. {endpoint.method.value} {endpoint.path} - {endpoint.description}")
            if endpoint.parameters:
                params = ", ".join(endpoint.parameters.keys())
                print(f"      Parameters: {params}")
        
        if len(api_doc.endpoints) > 5:
            print(f"   ... and {len(api_doc.endpoints) - 5} more endpoints")
        
        # Step 3: Find specific endpoint
        user_requests = ["get all posts", "fetch users", "create new post"]
        
        for request in user_requests:
            print(f"\nFinding endpoint for: '{request}'")
            endpoint = await agent.find_endpoint_for_request(api_doc, request)
            
            if endpoint:
                print(f"   [OK] Found: {endpoint.method.value} {endpoint.path}")
                print(f"   Description: {endpoint.description}")
                
                # Step 4: Construct and make API request
                api_request = await agent.construct_api_request_from_docs(
                    api_doc, endpoint, request
                )
                
                print(f"   Making API call to: {api_request.url}")
                response = await agent.make_api_request(api_request)
                
                if not response.error:
                    print(f"   [OK] Success! Status: {response.status_code}")
                    if response.json_data:
                        # Show first item if it's a list
                        data = response.json_data
                        if isinstance(data, list) and data:
                            print(f"   Sample data: {json.dumps(data[0], indent=2)[:200]}...")
                        else:
                            print(f"   Data: {json.dumps(data, indent=2)[:200]}...")
                else:
                    print(f"   [ERROR] Error: {response.error}")
            else:
                print(f"   [ERROR] No matching endpoint found")
        
    except Exception as e:
        print(f"[ERROR] Error: {str(e)}")
    
    finally:
        await agent.cleanup_session()


async def example_complex_workflow():
    """Example 5: Complex multi-step API workflow with documentation"""
    print("\nExample 5: Complex Multi-Step API Workflow")
    print("=" * 70)
    
    agent = APIAgent.create_simple(user_id="workflow_user")
    
    try:
        print("Scenario: E-commerce API workflow")
        print("   1. Parse API documentation")
        print("   2. Authenticate and get token")
        print("   3. Get user profile")
        print("   4. List products")
        print("   5. Create order")
        
        # Simulated e-commerce API workflow
        doc_url = "https://api.example-ecommerce.com/docs"
        initial_token = "temp_token_12345"
        
        workflows = [
            f"Read docs at {doc_url} and get auth token using {initial_token}",
            f"Using docs at {doc_url} with token {initial_token}, get my user profile",
            f"Parse {doc_url} and list all products with token {initial_token}",
            f"Documentation {doc_url} - create new order using token {initial_token}"
        ]
        
        for i, workflow in enumerate(workflows, 1):
            print(f"\nStep {i}: {workflow}")
            print("Processing workflow step...")
            
            try:
                response = await agent.chat(workflow)
                print(f"[OK] Step {i} completed")
                # In a real scenario, we might extract tokens or IDs from responses
                # and use them in subsequent requests
            except Exception as e:
                print(f"[ERROR] Step {i} failed: {str(e)}")
        
    finally:
        await agent.cleanup_session()


async def example_different_documentation_formats():
    """Example 6: Handling different documentation formats"""
    print("\nExample 6: Different Documentation Formats")
    print("=" * 70)
    
    agent = APIAgent.create_simple(user_id="format_user")
    
    # Test different documentation formats
    doc_examples = [
        {
            "format": "OpenAPI JSON",
            "url": "https://petstore.swagger.io/v2/swagger.json",
            "request": "get pet information"
        },
        {
            "format": "OpenAPI YAML", 
            "url": "https://api.example.com/openapi.yaml",
            "request": "list users"
        },
        {
            "format": "HTML Documentation",
            "url": "https://docs.github.com/en/rest",
            "request": "get repository info"
        }
    ]
    
    for example in doc_examples:
        print(f"\nTesting {example['format']} format:")
        print(f"   URL: {example['url']}")
        print(f"   Request: {example['request']}")
        
        try:
            # Test documentation parsing
            user_message = f"Read docs at {example['url']} and {example['request']}"
            response = await agent.chat(user_message)
            
            print(f"   [OK] {example['format']} parsing successful")
            print(f"   Response: {response[:150]}...")
            
        except Exception as e:
            print(f"   [ERROR] {example['format']} parsing failed: {str(e)}")
    
    await agent.cleanup_session()


async def main():
    """Run all intelligent API agent examples"""
    print("Intelligent API Agent - Documentation Parsing Examples")
    print("=" * 80)
    print("Demonstrating advanced capabilities:")
    print("- Automatic API documentation parsing (OpenAPI, HTML, any format)")
    print("- LLM-powered endpoint discovery and matching")
    print("- Intelligent API request construction")
    print("- Seamless authentication handling")
    print("- Natural language to API call translation")
    print("=" * 80)
    
    try:
        await example_parse_openapi_documentation()
        await example_parse_html_documentation()
        await example_ambivo_api_documentation()
        await example_manual_documentation_parsing()
        await example_complex_workflow()
        await example_different_documentation_formats()
        
        print("\n" + "=" * 80)
        print("[OK] All intelligent API examples completed!")
        print("\nKey Capabilities Demonstrated:")
        print("   LLM-powered documentation parsing")
        print("   Intelligent endpoint discovery")
        print("   Smart request-to-endpoint matching")
        print("   Automatic authentication handling")
        print("   End-to-end: Docs → Understanding → API Call")
        print("   Natural language API interaction")
        
    except Exception as e:
        print(f"\n[ERROR] Example execution failed: {str(e)}")


if __name__ == "__main__":
    # Run the intelligent examples
    asyncio.run(main())