#!/usr/bin/env python3
"""
Enhanced API Agent Examples - Postman Collections and Safety Features

This example demonstrates the latest API Agent enhancements:
- Postman collection parsing and endpoint extraction
- 8-second default timeout safety enforcement
- Docker execution for longer timeout requests
- Enhanced security and safety features
"""

import asyncio
import json
from typing import Dict, Any

from ambivo_agents.agents.api_agent import (
    APIAgent, APIRequest, AuthConfig, HTTPMethod, AuthType, SecurityConfig
)


async def example_postman_collection_parsing():
    """Example 1: Parse Postman collection and make intelligent API calls"""
    print("Example 1: Postman Collection Parsing")
    print("=" * 60)
    
    agent = APIAgent.create_simple(user_id="postman_user")
    
    try:
        # Example Postman collection URL (replace with actual collection)
        postman_url = "https://api.postman.com/collections/12345-abcde"  # Example
        
        print(f"Parsing Postman collection from: {postman_url}")
        
        # The agent will automatically detect and parse Postman collections
        user_request = f"Read Postman collection at {postman_url} and use token abc123 to get user data"
        
        print(f"User Request: '{user_request}'")
        print("Processing...")
        
        # The agent will:
        # 1. Detect this is a Postman collection
        # 2. Parse endpoints, auth, and examples
        # 3. Find the appropriate endpoint
        # 4. Make authenticated API call
        response = await agent.chat(user_request)
        
        print(f"[OK] Response: {response[:300]}{'...' if len(response) > 300 else ''}")
        
    except Exception as e:
        print(f"[ERROR] Error: {str(e)}")
    
    finally:
        await agent.cleanup_session()


async def example_manual_postman_parsing():
    """Example 2: Manual Postman collection parsing"""
    print("\nExample 2: Manual Postman Collection Parsing")
    print("=" * 60)
    
    agent = APIAgent.create_simple(user_id="manual_postman")
    
    try:
        # Sample Postman collection JSON (simplified)
        sample_postman_collection = {
            "info": {
                "name": "Sample API Collection",
                "description": "A sample Postman collection for testing",
                "schema": "https://schema.getpostman.com/json/collection/v2.1.0/collection.json"
            },
            "auth": {
                "type": "bearer",
                "bearer": [
                    {"key": "token", "value": "{{auth_token}}", "type": "string"}
                ]
            },
            "variable": [
                {"key": "baseUrl", "value": "https://jsonplaceholder.typicode.com"},
                {"key": "auth_token", "value": "sample_token_123"}
            ],
            "item": [
                {
                    "name": "Get All Posts",
                    "request": {
                        "method": "GET",
                        "url": {
                            "raw": "{{baseUrl}}/posts",
                            "host": ["{{baseUrl}}"],
                            "path": ["posts"]
                        },
                        "header": [
                            {"key": "Content-Type", "value": "application/json"}
                        ]
                    }
                },
                {
                    "name": "Get User by ID",
                    "request": {
                        "method": "GET",
                        "url": {
                            "raw": "{{baseUrl}}/users/{{userId}}",
                            "host": ["{{baseUrl}}"],
                            "path": ["users", "{{userId}}"],
                            "query": [
                                {"key": "fields", "value": "id,name,email"}
                            ]
                        }
                    }
                },
                {
                    "name": "Create Post",
                    "request": {
                        "method": "POST",
                        "url": {
                            "raw": "{{baseUrl}}/posts",
                            "host": ["{{baseUrl}}"],
                            "path": ["posts"]
                        },
                        "body": {
                            "mode": "raw",
                            "raw": "{\n  \"title\": \"Sample Post\",\n  \"body\": \"This is a sample post\",\n  \"userId\": 1\n}",
                            "options": {
                                "raw": {"language": "json"}
                            }
                        }
                    }
                }
            ]
        }
        
        # Save to temporary file and parse
        import tempfile
        import os
        
        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
            json.dump(sample_postman_collection, f)
            temp_file = f.name
        
        try:
            # Parse the collection
            print("Parsing sample Postman collection...")
            api_doc = await agent.parse_api_documentation(f"file://{temp_file}")
            
            print(f"[OK] Collection parsed successfully!")
            print(f"   Name: {api_doc.title}")
            print(f"   Base URL: {api_doc.base_url}")
            print(f"   Description: {api_doc.description}")
            print(f"   Auth Type: {api_doc.auth_info.get('type', 'None')}")
            print(f"   Endpoints found: {len(api_doc.endpoints)}")
            
            # Show endpoints
            print(f"\nParsed Endpoints:")
            for i, endpoint in enumerate(api_doc.endpoints, 1):
                print(f"   {i}. {endpoint.method.value} {endpoint.path}")
                print(f"      {endpoint.description}")
                if endpoint.parameters:
                    params = ", ".join(endpoint.parameters.keys())
                    print(f"      Parameters: {params}")
                if endpoint.example_request:
                    print(f"      Has example request data")
            
            # Test endpoint matching
            print(f"\nTesting Endpoint Matching:")
            test_requests = ["get all posts", "get user info", "create new post"]
            
            for request in test_requests:
                endpoint = await agent.find_endpoint_for_request(api_doc, request)
                if endpoint:
                    print(f"   [OK] '{request}' → {endpoint.method.value} {endpoint.path}")
                else:
                    print(f"   [ERROR] '{request}' → No match found")
        
        finally:
            os.unlink(temp_file)
        
    except Exception as e:
        print(f"[ERROR] Error: {str(e)}")
    
    finally:
        await agent.cleanup_session()


async def example_timeout_safety_features():
    """Example 3: Timeout safety and Docker execution"""
    print("\nExample 3: Timeout Safety and Docker Execution")
    print("=" * 60)
    
    # Create agent with custom security config for testing
    security_config = SecurityConfig(
        default_timeout_seconds=8,
        max_safe_timeout=8,
        force_docker_above_timeout=True,
        docker_image="sgosain/amb-ubuntu-python-public-pod"
    )
    
    agent = APIAgent.create_simple(
        user_id="safety_user",
        security_config=security_config
    )
    
    try:
        print("Testing timeout safety features...")
        
        # Test 1: Normal request (should use 8-second timeout)
        print("\n1. Testing normal request (8s timeout):")
        normal_request = APIRequest(
            url="https://jsonplaceholder.typicode.com/posts/1",
            method=HTTPMethod.GET
        )
        
        response = await agent.make_api_request(normal_request)
        if not response.error:
            print(f"   [OK] Success: {response.status_code} in {response.duration_ms:.0f}ms")
        else:
            print(f"   [ERROR] Error: {response.error}")
        
        # Test 2: Request with longer timeout (should trigger Docker)
        print("\n2. Testing long timeout request (15s - should use Docker):")
        long_timeout_request = APIRequest(
            url="https://httpbin.org/delay/5",  # 5-second delay endpoint
            method=HTTPMethod.GET,
            timeout=15  # Exceeds 8-second limit
        )
        
        print("   [WARN] This will execute in Docker for safety...")
        long_response = await agent.make_api_request(long_timeout_request)
        
        if not long_response.error:
            print(f"   [OK] Docker execution success: {long_response.status_code}")
            print(f"   Duration: {long_response.duration_ms:.0f}ms")
        else:
            print(f"   [ERROR] Docker execution error: {long_response.error}")
        
        # Test 3: Configuration-based timeout enforcement
        print("\n3. Testing configuration-based timeout enforcement:")
        
        # Show current config
        print(f"   Default timeout: {agent.security_config.default_timeout_seconds}s")
        print(f"   Max safe timeout: {agent.security_config.max_safe_timeout}s")
        print(f"   Force Docker above: {agent.security_config.force_docker_above_timeout}")
        
        # Test with different timeout scenarios
        test_scenarios = [
            {"timeout": 5, "description": "Short timeout (safe)"},
            {"timeout": 8, "description": "Max safe timeout"},
            {"timeout": 12, "description": "Above safe limit (Docker)"},
            {"timeout": 30, "description": "Long timeout (Docker)"}
        ]
        
        for scenario in test_scenarios:
            timeout = scenario["timeout"]
            desc = scenario["description"]
            
            print(f"\n   {desc} - {timeout}s:")
            
            test_request = APIRequest(
                url="https://jsonplaceholder.typicode.com/posts/1",
                method=HTTPMethod.GET,
                timeout=timeout
            )
            
            # Check if it would use Docker
            would_use_docker = (
                timeout > agent.security_config.max_safe_timeout and 
                agent.security_config.force_docker_above_timeout
            )
            
            print(f"      Would use Docker: {would_use_docker}")
            print(f"      Effective timeout: {min(timeout, agent.security_config.default_timeout_seconds)}s")
        
    except Exception as e:
        print(f"[ERROR] Error: {str(e)}")
    
    finally:
        await agent.cleanup_session()


async def example_comprehensive_safety_demo():
    """Example 4: Comprehensive safety and security demo"""
    print("\nExample 4: Comprehensive Safety and Security Demo")
    print("=" * 60)
    
    agent = APIAgent.create_simple(user_id="security_demo")
    
    try:
        print("Demonstrating security and safety features...")
        
        # Test various safety scenarios
        safety_tests = [
            {
                "name": "Valid API call",
                "request": "GET https://jsonplaceholder.typicode.com/posts/1",
                "expected": "success"
            },
            {
                "name": "Blocked domain (localhost)",
                "request": "GET http://localhost:8080/api",
                "expected": "blocked"
            },
            {
                "name": "Long timeout request",
                "request": "GET https://httpbin.org/delay/3 with timeout 15 seconds",
                "expected": "docker_execution"
            },
            {
                "name": "Postman collection parsing",
                "request": "Read Postman collection at https://example.com/collection.json and call users API",
                "expected": "intelligent_parsing"
            }
        ]
        
        for i, test in enumerate(safety_tests, 1):
            print(f"\n{i}. {test['name']}:")
            print(f"   Request: {test['request']}")
            print(f"   Expected: {test['expected']}")
            
            try:
                response = await agent.chat(test['request'])
                
                # Analyze response to determine outcome
                if "blocked" in response.lower() or "security validation failed" in response.lower():
                    print(f"   BLOCKED: Security measures working")
                elif "docker" in response.lower():
                    print(f"   DOCKER: Long timeout safely executed in container")
                elif "endpoints found" in response.lower() or "postman" in response.lower():
                    print(f"   INTELLIGENT: Successfully parsed documentation")
                elif "[OK]" in response:
                    print(f"   [OK] SUCCESS: API call completed safely")
                else:
                    print(f"   RESULT: {response[:100]}...")
                    
            except Exception as e:
                print(f"   [ERROR] ERROR: {str(e)}")
        
    finally:
        await agent.cleanup_session()


async def main():
    """Run all enhanced API agent examples"""
    print("Enhanced API Agent - Postman Collections & Safety Features")
    print("=" * 80)
    print("New capabilities demonstrated:")
    print("- Postman collection parsing and endpoint extraction")
    print("- 8-second default timeout safety enforcement")
    print("- Docker execution for longer timeout requests")
    print("- Enhanced security and safety features")
    print("- Intelligent documentation parsing (OpenAPI, HTML, Postman)")
    print("=" * 80)
    
    try:
        await example_postman_collection_parsing()
        await example_manual_postman_parsing()
        await example_timeout_safety_features()
        await example_comprehensive_safety_demo()
        
        print("\n" + "=" * 80)
        print("[OK] All enhanced examples completed!")
        print("\nKey Safety Features:")
        print("   8-second default timeout for all API calls")
        print("   Docker isolation for longer timeout requests")
        print("   Domain filtering and security validation")
        print("   Postman collection parsing and understanding")
        print("   Multi-format documentation intelligence")
        print("   Comprehensive safety and security enforcement")
        
    except Exception as e:
        print(f"\n[ERROR] Example execution failed: {str(e)}")


if __name__ == "__main__":
    # Run the enhanced examples
    asyncio.run(main())