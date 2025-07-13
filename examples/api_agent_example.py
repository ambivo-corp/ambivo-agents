#!/usr/bin/env python3
"""
API Agent Examples - Comprehensive HTTP/REST API Integration

This example demonstrates the APIAgent's capabilities including:
- Basic HTTP requests (GET, POST, PUT, DELETE)
- Authentication methods (Bearer, API Key, Basic, OAuth2)
- Pre-fetch authentication with token caching
- Error handling and retry logic
- Security features and domain filtering
"""

import asyncio
import json
from typing import Dict, Any

from ambivo_agents.agents.api_agent import (
    APIAgent, APIRequest, AuthConfig, HTTPMethod, AuthType
)


async def example_basic_api_calls():
    """Example 1: Basic API calls without authentication"""
    print("🔧 Example 1: Basic API Calls")
    print("=" * 50)
    
    # Create API agent
    agent = APIAgent.create_simple(user_id="example_user")
    
    try:
        # Simple GET request
        request = APIRequest(
            url="https://jsonplaceholder.typicode.com/posts/1",
            method=HTTPMethod.GET
        )
        
        response = await agent.make_api_request(request)
        
        if response.error:
            print(f"❌ Request failed: {response.error}")
        else:
            print(f"✅ GET Request successful!")
            print(f"Status: {response.status_code}")
            print(f"Duration: {response.duration_ms:.0f}ms")
            if response.json_data:
                print(f"Response: {json.dumps(response.json_data, indent=2)}")
        
        # POST request with JSON data
        print("\n" + "-" * 30)
        
        post_request = APIRequest(
            url="https://jsonplaceholder.typicode.com/posts",
            method=HTTPMethod.POST,
            headers={"Content-Type": "application/json"},
            json_data={
                "title": "Test Post",
                "body": "This is a test post from APIAgent",
                "userId": 1
            }
        )
        
        post_response = await agent.make_api_request(post_request)
        
        if post_response.error:
            print(f"❌ POST failed: {post_response.error}")
        else:
            print(f"✅ POST Request successful!")
            print(f"Status: {post_response.status_code}")
            if post_response.json_data:
                print(f"Created: {json.dumps(post_response.json_data, indent=2)}")
    
    finally:
        await agent.cleanup_session()


async def example_api_key_authentication():
    """Example 2: API Key authentication"""
    print("\n🔐 Example 2: API Key Authentication")
    print("=" * 50)
    
    agent = APIAgent.create_simple(user_id="example_user")
    
    try:
        # API Key authentication example
        auth_config = AuthConfig(
            auth_type=AuthType.API_KEY,
            api_key="your-api-key-here",
            api_key_header="X-API-Key"
        )
        
        request = APIRequest(
            url="https://api.example.com/data",  # Replace with actual API
            method=HTTPMethod.GET,
            auth_config=auth_config
        )
        
        # Note: This will fail since it's a dummy API, but shows the pattern
        response = await agent.make_api_request(request)
        print(f"API Key request attempted - Status: {response.status_code}")
        if response.error:
            print(f"Expected error (dummy API): {response.error}")
    
    finally:
        await agent.cleanup_session()


async def example_bearer_token_authentication():
    """Example 3: Bearer token authentication"""
    print("\n🎫 Example 3: Bearer Token Authentication")
    print("=" * 50)
    
    agent = APIAgent.create_simple(user_id="example_user")
    
    try:
        # Bearer token authentication
        auth_config = AuthConfig(
            auth_type=AuthType.BEARER,
            token="your-bearer-token-here",
            token_prefix="Bearer"
        )
        
        request = APIRequest(
            url="https://api.github.com/user",  # GitHub API example
            method=HTTPMethod.GET,
            auth_config=auth_config
        )
        
        response = await agent.make_api_request(request)
        print(f"Bearer token request attempted - Status: {response.status_code}")
        if response.error:
            print(f"Expected error (invalid token): {response.error}")
    
    finally:
        await agent.cleanup_session()


async def example_google_oauth_prefetch():
    """Example 4: Google OAuth2 with pre-fetch authentication"""
    print("\n🔄 Example 4: Google OAuth2 Pre-fetch Authentication")
    print("=" * 50)
    
    agent = APIAgent.create_simple(user_id="example_user")
    
    try:
        # Google OAuth2 with pre-fetch configuration
        # Note: Replace with your actual Google OAuth credentials
        google_auth = AuthConfig(
            auth_type=AuthType.BEARER,
            
            # Pre-auth configuration for Google OAuth2
            pre_auth_url="https://www.googleapis.com/oauth2/v4/token",
            pre_auth_method=HTTPMethod.POST,
            pre_auth_headers={"Content-Type": "application/x-www-form-urlencoded"},
            pre_auth_payload={
                "client_id": "your-google-client-id.apps.googleusercontent.com",
                "client_secret": "your-google-client-secret",
                "refresh_token": "your-google-refresh-token",
                "grant_type": "refresh_token"
            },
            
            # Token extraction configuration
            token_path="access_token",  # Extract 'access_token' from JSON response
            token_prefix="Bearer"
        )
        
        # Example: Access Google Sheets API
        sheets_request = APIRequest(
            url="https://sheets.googleapis.com/v4/spreadsheets/your-sheet-id/values/Sheet1!A1:B10",
            method=HTTPMethod.GET,
            auth_config=google_auth
        )
        
        print("📡 Making request to Google Sheets API...")
        print("   - First, APIAgent will automatically call OAuth2 token endpoint")
        print("   - Then, it will use the fetched access_token for the actual request")
        print("   - Token will be cached for subsequent requests")
        
        response = await agent.make_api_request(sheets_request)
        print(f"Google API request attempted - Status: {response.status_code}")
        
        if response.error:
            print(f"Expected error (dummy credentials): {response.error}")
        else:
            print("✅ Successfully authenticated and accessed Google API!")
            if response.json_data:
                print(f"Response: {json.dumps(response.json_data, indent=2)}")
    
    finally:
        await agent.cleanup_session()


async def example_complex_workflow():
    """Example 5: Complex multi-step API workflow"""
    print("\n🔀 Example 5: Complex Multi-Step API Workflow")
    print("=" * 50)
    
    agent = APIAgent.create_simple(user_id="example_user")
    
    try:
        # Step 1: Get a list of posts
        print("Step 1: Fetching posts list...")
        posts_request = APIRequest(
            url="https://jsonplaceholder.typicode.com/posts",
            method=HTTPMethod.GET,
            params={"_limit": "5"}  # Limit to 5 posts
        )
        
        posts_response = await agent.make_api_request(posts_request)
        
        if posts_response.error:
            print(f"❌ Failed to fetch posts: {posts_response.error}")
            return
        
        posts = posts_response.json_data
        print(f"✅ Fetched {len(posts)} posts")
        
        # Step 2: Get details for each post's user
        print("\nStep 2: Fetching user details for each post...")
        
        for i, post in enumerate(posts[:3]):  # Process first 3 posts
            user_request = APIRequest(
                url=f"https://jsonplaceholder.typicode.com/users/{post['userId']}",
                method=HTTPMethod.GET
            )
            
            user_response = await agent.make_api_request(user_request)
            
            if user_response.error:
                print(f"❌ Failed to fetch user {post['userId']}: {user_response.error}")
            else:
                user = user_response.json_data
                print(f"   Post {i+1}: '{post['title'][:30]}...' by {user['name']}")
        
        # Step 3: Create a new post
        print("\nStep 3: Creating a new post...")
        
        new_post_request = APIRequest(
            url="https://jsonplaceholder.typicode.com/posts",
            method=HTTPMethod.POST,
            headers={"Content-Type": "application/json"},
            json_data={
                "title": "APIAgent Test Post",
                "body": "This post was created using the APIAgent's complex workflow example.",
                "userId": 1
            }
        )
        
        create_response = await agent.make_api_request(new_post_request)
        
        if create_response.error:
            print(f"❌ Failed to create post: {create_response.error}")
        else:
            new_post = create_response.json_data
            print(f"✅ Created new post with ID: {new_post['id']}")
    
    finally:
        await agent.cleanup_session()


async def example_conversational_api_usage():
    """Example 6: Using APIAgent through conversational interface"""
    print("\n💬 Example 6: Conversational API Usage")
    print("=" * 50)
    
    agent = APIAgent.create_simple(user_id="example_user")
    
    try:
        # Example of using the agent's chat interface for API requests
        test_messages = [
            "GET https://jsonplaceholder.typicode.com/posts/1",
            "POST https://jsonplaceholder.typicode.com/posts with data: {\"title\": \"Test\", \"body\": \"Hello\", \"userId\": 1}",
            "Please fetch user information from https://jsonplaceholder.typicode.com/users/1"
        ]
        
        for message in test_messages:
            print(f"\n📩 User: {message}")
            
            response = await agent.chat(message)
            print(f"🤖 APIAgent: {response[:200]}{'...' if len(response) > 200 else ''}")
    
    finally:
        await agent.cleanup_session()


async def example_error_handling_and_retries():
    """Example 7: Error handling and retry mechanisms"""
    print("\n🔁 Example 7: Error Handling and Retries")
    print("=" * 50)
    
    agent = APIAgent.create_simple(user_id="example_user")
    
    try:
        # Test with a non-existent endpoint (will trigger retries)
        print("Testing retry mechanism with non-existent endpoint...")
        
        retry_request = APIRequest(
            url="https://httpstat.us/500",  # Returns HTTP 500 (triggers retry)
            method=HTTPMethod.GET
        )
        
        response = await agent.make_api_request(retry_request)
        
        print(f"Request completed after {response.attempt_number} attempts")
        print(f"Status: {response.status_code}")
        if response.error:
            print(f"Final error: {response.error}")
        
        # Test with invalid URL (immediate failure)
        print("\nTesting invalid URL handling...")
        
        invalid_request = APIRequest(
            url="not-a-valid-url",
            method=HTTPMethod.GET
        )
        
        invalid_response = await agent.make_api_request(invalid_request)
        print(f"Invalid URL error: {invalid_response.error}")
        
    finally:
        await agent.cleanup_session()


async def main():
    """Run all API agent examples"""
    print("🚀 APIAgent Comprehensive Examples")
    print("=" * 60)
    print("This demonstrates the APIAgent's full capabilities including:")
    print("- Basic HTTP operations (GET, POST, PUT, DELETE)")
    print("- Authentication methods (Bearer, API Key, Basic, OAuth2)")
    print("- Pre-fetch authentication with token caching")
    print("- Error handling and retry logic")
    print("- Security features and validation")
    print("- Conversational interface")
    print("=" * 60)
    
    try:
        await example_basic_api_calls()
        await example_api_key_authentication()
        await example_bearer_token_authentication()
        await example_google_oauth_prefetch()
        await example_complex_workflow()
        await example_conversational_api_usage()
        await example_error_handling_and_retries()
        
        print("\n" + "=" * 60)
        print("✅ All examples completed successfully!")
        print("\n💡 Key Takeaways:")
        print("- APIAgent supports all major HTTP methods and auth types")
        print("- Pre-fetch authentication automatically handles token refresh")
        print("- Built-in retry logic with exponential backoff")
        print("- Security features prevent access to blocked domains/methods")
        print("- Can be used programmatically or through chat interface")
        print("- Comprehensive error handling and logging")
        
    except Exception as e:
        print(f"\n❌ Example execution failed: {str(e)}")


if __name__ == "__main__":
    # Run the examples
    asyncio.run(main())