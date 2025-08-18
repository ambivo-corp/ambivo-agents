#!/usr/bin/env python3
"""
Skill Assignment Demo - Shows how to assign API, Database, and Knowledge Base skills to agents

This example demonstrates the new skill assignment feature where:
1. AssistantAgent and ModeratorAgent can be "assigned" skills like API specs, DB connections, etc.
2. They intelligently detect when to use these skills based on user intent
3. They internally spawn specialized agents (APIAgent, DatabaseAgent, etc.) on demand
4. Responses are translated to natural language for the end user

Example Usage:
    python examples/skill_assignment_demo.py
"""

import asyncio
import logging
from pathlib import Path

from ambivo_agents import AssistantAgent, ModeratorAgent

# Set up logging to see what's happening
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)


async def demo_assistant_with_api_skill():
    """Demo AssistantAgent with assigned API skill"""
    print("\n" + "="*80)
    print("🎯 DEMO 1: AssistantAgent with API Skill Assignment")
    print("="*80)
    
    # Create AssistantAgent
    assistant = AssistantAgent.create_simple(user_id="demo_user")
    
    # Assign API skill using the provided OpenAPI spec
    api_spec_path = "/Users/hemantgosain/Development/ai_workflow_system/docs/api_documentation.yaml"
    
    result = await assistant.assign_api_skill(
        api_spec_path=api_spec_path,
        base_url="https://api.aiworkflowsystem.com/v1",
        api_token="demo-token-12345",
        skill_name="workflow_api"
    )
    
    if result['success']:
        print(f"✅ Assigned API skill: {result['skill_name']}")
        print(f"   - API Title: {result['api_title']}")
        print(f"   - Endpoints: {result['endpoints_count']}")
        print(f"   - Base URL: {result['base_url']}")
    else:
        print(f"❌ Failed to assign API skill: {result['error']}")
        return
    
    # List assigned skills
    skills = assistant.list_assigned_skills()
    print(f"\n📋 Assigned Skills Summary: {skills}")
    
    # Now test with various user requests
    test_requests = [
        "Create a lead for John Doe with email john@example.com",
        "List all current leads in the system",
        "Send an email to user@example.com about our new service",
        "What's the weather like today?",  # Should fall back to normal processing
    ]
    
    for request in test_requests:
        print(f"\n👤 User: {request}")
        response = await assistant.chat(request)
        print(f"🤖 Assistant: {response}")
    
    await assistant.cleanup_session()
    print("\n✅ Demo 1 completed!")


async def demo_moderator_with_multiple_skills():
    """Demo ModeratorAgent with multiple assigned skills"""
    print("\n" + "="*80)
    print("🎯 DEMO 2: ModeratorAgent with Multiple Skills")
    print("="*80)
    
    # Create ModeratorAgent
    moderator = ModeratorAgent.create_simple(
        user_id="demo_user_2",
        enabled_agents=["assistant", "api_agent", "database_agent", "knowledge_base"]
    )
    
    # Assign multiple skills
    
    # 1. API Skill
    api_result = await moderator.assign_api_skill(
        api_spec_path="/Users/hemantgosain/Development/ai_workflow_system/docs/api_documentation.yaml",
        base_url="https://api.aiworkflowsystem.com/v1",
        api_token="demo-token-12345",
        skill_name="workflow_api"
    )
    
    # 2. Database Skill (example connection string)
    db_result = await moderator.assign_database_skill(
        connection_string="postgresql://user:pass@localhost:5432/crm_database",
        skill_name="crm_db",
        description="Customer relationship management database"
    )
    
    # 3. Knowledge Base Skill
    kb_result = await moderator.assign_kb_skill(
        documents_path="/Users/hemantgosain/Development/ai_workflow_system/docs/",
        collection_name="ai_workflow_docs",
        skill_name="company_docs"
    )
    
    print(f"API Skill: {'✅' if api_result['success'] else '❌'} {api_result.get('skill_name', api_result.get('error'))}")
    print(f"DB Skill: {'✅' if db_result['success'] else '❌'} {db_result.get('skill_name', db_result.get('error'))}")
    print(f"KB Skill: {'✅' if kb_result['success'] else '❌'} {kb_result.get('skill_name', kb_result.get('error'))}")
    
    # List all assigned skills
    all_skills = moderator.list_assigned_skills()
    print(f"\n📋 All Assigned Skills: {all_skills}")
    
    # Test various requests that should use different skills
    test_scenarios = [
        # API skill scenarios
        ("create lead for Sarah Smith", "Should use API skill"),
        ("send email to client@company.com", "Should use API skill"),
        
        # Database skill scenarios  
        ("show me recent sales data", "Should use database skill"),
        ("count total customers in database", "Should use database skill"),
        
        # Knowledge base scenarios
        ("what do our docs say about pricing?", "Should use knowledge base skill"),
        ("search our documentation for API usage", "Should use knowledge base skill"),
        
        # Should fall back to normal routing
        ("what's the current time?", "Should use normal agent routing"),
        ("hello, how are you?", "Should use normal agent routing"),
    ]
    
    for request, expected in test_scenarios:
        print(f"\n👤 User: {request}")
        print(f"🎯 Expected: {expected}")
        response = await moderator.chat(request)
        print(f"🤖 Moderator: {response}")
    
    await moderator.cleanup_session()
    print("\n✅ Demo 2 completed!")


async def demo_skill_priority_and_fallback():
    """Demo how skills work with agent priority and fallback"""
    print("\n" + "="*80)
    print("🎯 DEMO 3: Skill Priority and Fallback Behavior")
    print("="*80)
    
    assistant = AssistantAgent.create_simple(user_id="demo_user_3")
    
    # Assign API skill
    await assistant.assign_api_skill(
        api_spec_path="/Users/hemantgosain/Development/ai_workflow_system/docs/api_documentation.yaml",
        base_url="https://api.aiworkflowsystem.com/v1",
        api_token="demo-token-12345"
    )
    
    # Test edge cases and priority
    edge_cases = [
        # Clear skill intent
        "create a new lead",
        
        # Ambiguous intent - could be API or general
        "how do I create a lead?",
        
        # Clear non-skill intent
        "explain machine learning to me",
        
        # Skill-related but general question
        "what APIs do you have access to?",
    ]
    
    for case in edge_cases:
        print(f"\n👤 User: {case}")
        response = await assistant.chat(case)
        print(f"🤖 Assistant: {response}")
    
    await assistant.cleanup_session()
    print("\n✅ Demo 3 completed!")


async def demo_skill_configuration_and_management():
    """Demo skill configuration and management features"""
    print("\n" + "="*80)
    print("🎯 DEMO 4: Skill Configuration and Management")
    print("="*80)
    
    assistant = AssistantAgent.create_simple(user_id="demo_user_4")
    
    # Show initial state (no skills)
    print("📊 Initial agent capabilities:")
    status = assistant.get_agent_status()
    print(f"   Agent Type: {status['agent_type']}")
    print(f"   Capabilities: {status['capabilities']}")
    print(f"   Assigned Skills: {status.get('assigned_skills', 'None')}")
    
    # Assign multiple skills and show how they're managed
    print("\n🔧 Assigning skills...")
    
    # API skill
    await assistant.assign_api_skill(
        api_spec_path="/Users/hemantgosain/Development/ai_workflow_system/docs/api_documentation.yaml",
        base_url="https://api.aiworkflowsystem.com/v1",
        skill_name="workflow_api"
    )
    
    # Database skill  
    await assistant.assign_database_skill(
        connection_string="mysql://user:pass@localhost:3306/sales_db",
        skill_name="sales_db"
    )
    
    # Show updated capabilities
    print("\n📊 Updated agent capabilities:")
    status = assistant.get_agent_status()
    print(f"   Agent Type: {status['agent_type']}")
    print(f"   Capabilities: {status['capabilities']}")
    print(f"   Assigned Skills: {status.get('assigned_skills')}")
    
    # Test a complex request that could use multiple skills
    print("\n🧪 Testing complex request...")
    complex_request = "Get sales data from database and then create a lead based on the top customer"
    response = await assistant.chat(complex_request)
    print(f"👤 User: {complex_request}")
    print(f"🤖 Assistant: {response}")
    
    await assistant.cleanup_session()
    print("\n✅ Demo 4 completed!")


async def main():
    """Run all demos"""
    print("🚀 Starting Skill Assignment Demos")
    print("This demo shows how agents can be assigned external skills (APIs, databases, etc.)")
    print("and intelligently use them based on user intent.")
    
    try:
        # Run all demos
        await demo_assistant_with_api_skill()
        await demo_moderator_with_multiple_skills() 
        await demo_skill_priority_and_fallback()
        await demo_skill_configuration_and_management()
        
        print("\n" + "="*80)
        print("🎉 ALL DEMOS COMPLETED SUCCESSFULLY!")
        print("="*80)
        print("\nKey Features Demonstrated:")
        print("✅ API skill assignment from OpenAPI specs")
        print("✅ Database skill assignment with connection strings")  
        print("✅ Knowledge base skill assignment with document paths")
        print("✅ Intelligent intent detection and skill routing")
        print("✅ Natural language response translation")
        print("✅ Graceful fallback to normal agent behavior")
        print("✅ Multiple skills on single agent")
        print("✅ Skill management and configuration")
        
    except Exception as e:
        print(f"\n❌ Demo failed: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    asyncio.run(main())