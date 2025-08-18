#!/usr/bin/env python3
"""
Quick Skill Assignment Demo - Simple example showing the new skill assignment feature
"""

import asyncio
from ambivo_agents import AssistantAgent

async def main():
    # Create an AssistantAgent
    assistant = AssistantAgent.create_simple(user_id="demo_user")
    
    # Assign an API skill using your OpenAPI spec
    result = await assistant.assign_api_skill(
        api_spec_path="/Users/hemantgosain/Development/ai_workflow_system/docs/api_documentation.yaml",
        base_url="https://api.aiworkflowsystem.com/v1",
        api_token="your-api-token",
        skill_name="workflow_api"
    )
    
    print(f"API Skill Assignment: {'✅ Success' if result['success'] else '❌ Failed'}")
    if result['success']:
        print(f"Skill Name: {result['skill_name']}")
        print(f"Endpoints Available: {result['endpoints_count']}")
    
    # Now the assistant can understand and execute API requests naturally!
    print("\n🧪 Testing natural language API requests:")
    
    # These requests will automatically:
    # 1. Detect the intent to use the API skill
    # 2. Spawn an APIAgent internally 
    # 3. Make the actual API call
    # 4. Translate the response to natural language
    
    requests = [
        "create a lead for John Doe with email john@example.com",
        "list all leads in the system", 
        "send an email to client@company.com about our new product"
    ]
    
    for request in requests:
        print(f"\n👤 User: {request}")
        response = await assistant.chat(request)
        print(f"🤖 Assistant: {response}")
    
    # Check what skills are assigned
    skills = assistant.list_assigned_skills()
    print(f"\n📋 Current Skills: {skills}")
    
    await assistant.cleanup_session()

if __name__ == "__main__":
    asyncio.run(main())