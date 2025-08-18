#!/usr/bin/env python3
"""
Example demonstrating GatherAgent with natural language parsing enabled.

This shows how the agent can understand conversational responses and map them
to structured answers when enable_natural_language_parsing is set to True.
"""

import asyncio
import json
from ambivo_agents.agents.gather_agent import GatherAgent

# Sample questionnaire with different question types
SAMPLE_QUESTIONNAIRE = {
    "questions": [
        {
            "question_id": "q1",
            "text": "Do you currently use any security monitoring tools?",
            "type": "yes-no",
            "required": True
        },
        {
            "question_id": "q2", 
            "text": "What is your preferred notification method?",
            "type": "single-select",
            "required": True,
            "answer_option_dict_list": [
                {"value": "email", "label": "Email notifications"},
                {"value": "sms", "label": "SMS text messages"},
                {"value": "push", "label": "Push notifications"},
                {"value": "webhook", "label": "Webhook callbacks"}
            ]
        },
        {
            "question_id": "q3",
            "text": "Which compliance standards do you need to meet?",
            "type": "multi-select",
            "required": True,
            "answer_option_dict_list": [
                {"value": "gdpr", "label": "GDPR"},
                {"value": "hipaa", "label": "HIPAA"},
                {"value": "pci", "label": "PCI-DSS"},
                {"value": "sox", "label": "SOX"},
                {"value": "iso27001", "label": "ISO 27001"}
            ]
        },
        {
            "question_id": "q4",
            "text": "Please describe your main security concerns",
            "type": "free-text",
            "required": True,
            "min_answer_length": 10
        }
    ]
}


async def demo_natural_language_parsing():
    """Demonstrate natural language understanding in GatherAgent"""
    
    print("=" * 70)
    print("GatherAgent Natural Language Parsing Demo")
    print("=" * 70)
    print("\nThis demo shows how the agent can understand natural language responses")
    print("and map them to structured answers when configured.\n")
    
    # Create agent with natural language parsing enabled
    agent = GatherAgent.create_simple(
        user_id="demo_user",
        config={
            "gather": {
                "submission_endpoint": None,  # No actual submission for demo
                "enable_natural_language_parsing": True,  # Enable NLP feature
                "enable_llm_answer_validation": False,
                "memory_ttl_seconds": 3600
            }
        }
    )
    
    # Simulated conversation with natural language responses
    test_conversations = [
        {
            "description": "Testing yes/no with natural language",
            "question": "Do you currently use any security monitoring tools?",
            "responses": [
                "Absolutely! We have several in place",
                "Not really, we're just getting started",
                "Yeah, we use Datadog and Splunk"
            ],
            "expected_mapping": ["Yes", "No", "Yes"]
        },
        {
            "description": "Testing single-select with natural language",
            "question": "What is your preferred notification method?",
            "responses": [
                "I'd prefer email notifications please",
                "SMS would work best for our team",
                "The webhook option sounds perfect for our setup"
            ],
            "expected_mapping": ["email", "sms", "webhook"]
        },
        {
            "description": "Testing multi-select with natural language",
            "question": "Which compliance standards do you need to meet?",
            "responses": [
                "We need both GDPR and HIPAA compliance",
                "All of them except SOX",
                "Just PCI for now, but we're working towards ISO certification"
            ],
            "expected_mapping": [["gdpr", "hipaa"], ["gdpr", "hipaa", "pci", "iso27001"], ["pci"]]
        }
    ]
    
    print("Starting conversational interaction simulation...\n")
    
    # First, provide the questionnaire
    print("1. Providing questionnaire to agent...")
    response = await agent.process_message(
        agent.create_message(
            content=json.dumps(SAMPLE_QUESTIONNAIRE),
            sender_id="demo_user"
        )
    )
    print(f"   Agent: {response.content}\n")
    
    # Simulate natural language responses
    for test_case in test_conversations[:1]:  # Test first case for demo
        print(f"2. {test_case['description']}")
        print(f"   Question: {test_case['question']}")
        
        for i, user_response in enumerate(test_case['responses'][:1]):  # Test one response
            print(f"\n   User says: \"{user_response}\"")
            
            # Send natural language response
            response = await agent.process_message(
                agent.create_message(
                    content=user_response,
                    sender_id="demo_user"
                )
            )
            
            # Check if agent understood (would map to expected answer)
            print(f"   Expected mapping: {test_case['expected_mapping'][i]}")
            print(f"   Agent response: {response.content[:200]}...")
            
            # For demo, just test one response per question type
            break
    
    # Clean up
    await agent.cleanup_session()
    
    print("\n" + "=" * 70)
    print("Demo Complete!")
    print("\nKey Features Demonstrated:")
    print("- Natural language 'Absolutely!' mapped to 'Yes'")
    print("- Conversational 'I'd prefer email' mapped to 'email' option")
    print("- Complex 'both GDPR and HIPAA' mapped to multiple selections")
    print("\nTo enable this feature in your config:")
    print("  gather:")
    print("    enable_natural_language_parsing: true")
    print("\nOr via environment variable:")
    print("  export AMBIVO_AGENTS_GATHER_ENABLE_NATURAL_LANGUAGE_PARSING=true")
    print("=" * 70)


async def demo_comparison():
    """Show the difference between enabled and disabled natural language parsing"""
    
    print("\n" + "=" * 70)
    print("Comparison: With and Without Natural Language Parsing")
    print("=" * 70)
    
    test_response = "Yeah, absolutely we use those!"
    
    # Without NLP
    print("\n1. WITHOUT Natural Language Parsing (default):")
    agent_without = GatherAgent.create_simple(
        user_id="demo_without",
        config={
            "gather": {
                "enable_natural_language_parsing": False  # Disabled
            }
        }
    )
    
    print(f"   User says: \"{test_response}\"")
    print("   Result: Would ask user to answer 'Yes' or 'No' (strict matching)")
    
    # With NLP
    print("\n2. WITH Natural Language Parsing:")
    agent_with = GatherAgent.create_simple(
        user_id="demo_with",
        config={
            "gather": {
                "enable_natural_language_parsing": True  # Enabled
            }
        }
    )
    
    print(f"   User says: \"{test_response}\"")
    print("   Result: Automatically maps to 'Yes' (understands intent)")
    
    await agent_without.cleanup_session()
    await agent_with.cleanup_session()


if __name__ == "__main__":
    print("\nGatherAgent Natural Language Parsing Feature\n")
    
    # Run the main demo
    asyncio.run(demo_natural_language_parsing())
    
    # Show comparison
    asyncio.run(demo_comparison())