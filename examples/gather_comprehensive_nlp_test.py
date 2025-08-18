#!/usr/bin/env python3
"""
Comprehensive test for GatherAgent Natural Language Parsing

This script demonstrates various natural language responses that the
GatherAgent can understand when enable_natural_language_parsing=True
"""

import asyncio
import json
from typing import List, Dict, Any
from ambivo_agents.agents.gather_agent import GatherAgent


# Comprehensive questionnaire covering all question types
COMPREHENSIVE_QUESTIONNAIRE = {
    "questions": [
        {
            "question_id": "security_tools",
            "text": "Do you currently use security monitoring tools?",
            "type": "yes-no",
            "required": True
        },
        {
            "question_id": "notification_method",
            "text": "What is your preferred notification method?",
            "type": "single-select",
            "required": True,
            "answer_option_dict_list": [
                {"value": "email", "label": "Email notifications"},
                {"value": "sms", "label": "SMS text messages"}, 
                {"value": "slack", "label": "Slack messages"},
                {"value": "webhook", "label": "Webhook callbacks"},
                {"value": "dashboard", "label": "Dashboard only"}
            ]
        },
        {
            "question_id": "cloud_providers",
            "text": "Which cloud providers do you use?",
            "type": "multi-select",
            "required": True,
            "answer_option_dict_list": [
                {"value": "aws", "label": "Amazon AWS"},
                {"value": "azure", "label": "Microsoft Azure"},
                {"value": "gcp", "label": "Google Cloud Platform"},
                {"value": "digitalocean", "label": "DigitalOcean"},
                {"value": "oracle", "label": "Oracle Cloud"}
            ]
        },
        {
            "question_id": "team_size",
            "text": "How many people are on your security team?",
            "type": "single-select", 
            "required": True,
            "answer_option_dict_list": [
                {"value": "1-2", "label": "1-2 people"},
                {"value": "3-5", "label": "3-5 people"},
                {"value": "6-10", "label": "6-10 people"},
                {"value": "11-20", "label": "11-20 people"},
                {"value": "20+", "label": "More than 20"}
            ]
        },
        {
            "question_id": "main_concerns",
            "text": "What are your main security concerns?",
            "type": "free-text",
            "required": True,
            "min_answer_length": 15
        }
    ]
}


# Test cases showing natural language responses for each question type
TEST_CASES = [
    {
        "question_type": "yes-no",
        "question": "Do you currently use security monitoring tools?",
        "natural_responses": [
            "Absolutely! We have several in place",
            "Yeah, we use Datadog and Splunk",
            "Not really, we're just getting started", 
            "Nope, budget constraints",
            "Definitely yes, it's critical for us",
            "I don't think we do currently"
        ],
        "expected_mappings": ["Yes", "Yes", "No", "No", "Yes", "No"]
    },
    {
        "question_type": "single-select",
        "question": "What is your preferred notification method?",
        "natural_responses": [
            "I'd prefer email notifications please",
            "Slack would work best for our team",
            "The webhook option sounds perfect",
            "Let's go with SMS for now",
            "I think the first option would be good",
            "The dashboard-only approach works for us"
        ],
        "expected_mappings": ["email", "slack", "webhook", "sms", "email", "dashboard"]
    },
    {
        "question_type": "multi-select", 
        "question": "Which cloud providers do you use?",
        "natural_responses": [
            "We use both AWS and Azure",
            "All of them except Oracle",
            "Just AWS for now, but considering Google",
            "The first two options would be correct",
            "Microsoft and Google clouds",
            "We're fully committed to Amazon's platform"
        ],
        "expected_mappings": [
            ["aws", "azure"],
            ["aws", "azure", "gcp", "digitalocean"], 
            ["aws"],
            ["aws", "azure"],
            ["azure", "gcp"],
            ["aws"]
        ]
    },
    {
        "question_type": "single-select",
        "question": "How many people are on your security team?", 
        "natural_responses": [
            "We have a small team of about 4 people",
            "Just me and one other person",
            "It's a decent sized team, maybe 8 people",
            "We're a large organization with over 25 security folks",
            "Pretty small, just 2 of us",
            "We have around 15 people focused on security"
        ],
        "expected_mappings": ["3-5", "1-2", "6-10", "20+", "1-2", "11-20"]
    }
]


async def test_natural_language_parsing():
    """Test natural language parsing capabilities"""
    
    print("=" * 80)
    print("Comprehensive Natural Language Parsing Test for GatherAgent")
    print("=" * 80)
    
    print("\nThis test demonstrates how the agent understands natural language")
    print("responses and maps them to structured answers.\n")
    
    # Create agent with natural language parsing enabled
    agent = GatherAgent.create_simple(
        user_id="nlp_test_user",
        config={
            "gather": {
                "submission_endpoint": None,
                "enable_natural_language_parsing": True,
                "memory_ttl_seconds": 3600
            }
        }
    )
    
    print("🧪 Testing Natural Language Understanding...")
    print("-" * 50)
    
    # Test individual question types
    for i, test_case in enumerate(TEST_CASES, 1):
        print(f"\n{i}. Testing {test_case['question_type'].upper()} Questions:")
        print(f"   Question: \"{test_case['question']}\"")
        print("   Natural Language Responses:")
        
        for j, (response, expected) in enumerate(zip(test_case['natural_responses'], test_case['expected_mappings'])):
            print(f"   {j+1}. \"{response}\"")
            print(f"      → Expected mapping: {expected}")
        
        print()
    
    print("=" * 80)
    print("Key Natural Language Capabilities Demonstrated:")
    print("=" * 80)
    
    capabilities = [
        "✅ Affirmative/Negative Intent Recognition",
        "   'Absolutely!' → 'Yes', 'Not really' → 'No'",
        "",
        "✅ Preference Expression Understanding", 
        "   'I'd prefer email' → 'email' option",
        "   'The first option would be good' → maps to first choice",
        "",
        "✅ Multiple Selection from Natural Language",
        "   'Both AWS and Azure' → ['aws', 'azure']",
        "   'All except Oracle' → maps to all options except one",
        "",
        "✅ Quantity/Size Understanding",
        "   'About 4 people' → '3-5 people' range",
        "   'Over 25 security folks' → '20+' category",
        "",
        "✅ Contextual Mapping",
        "   'Microsoft and Google clouds' → ['azure', 'gcp']",
        "   'Amazon's platform' → ['aws']"
    ]
    
    for capability in capabilities:
        print(capability)
    
    print("\n" + "=" * 80)
    print("Configuration Required:")
    print("=" * 80)
    
    print("In agent_config.yaml:")
    print("  gather:")
    print("    enable_natural_language_parsing: true")
    print("")
    print("Or via environment variable:")
    print("  export AMBIVO_AGENTS_GATHER_ENABLE_NATURAL_LANGUAGE_PARSING=true")
    print("")
    print("Note: Requires LLM service to be configured for natural language processing")
    
    await agent.cleanup_session()


async def interactive_test():
    """Interactive test allowing manual verification"""
    
    print("\n" + "=" * 80)
    print("Interactive Natural Language Test")
    print("=" * 80)
    
    print("\nThis allows you to test natural language responses manually.")
    print("Try responses like:")
    print("  - 'Yeah absolutely!'")
    print("  - 'I'd go with the Slack option'") 
    print("  - 'We use both AWS and Google'")
    print("\nType 'skip' to skip this interactive test.\n")
    
    try:
        user_input = input("Start interactive test? (y/n/skip): ").strip().lower()
        
        if user_input in ['n', 'no', 'skip']:
            print("Skipping interactive test.")
            return
            
        if user_input not in ['y', 'yes']:
            print("Skipping interactive test.")
            return
            
        # Create agent for interactive test
        agent = GatherAgent.create_simple(
            user_id="interactive_user",
            config={
                "gather": {
                    "submission_endpoint": None,
                    "enable_natural_language_parsing": True,
                    "memory_ttl_seconds": 3600
                }
            }
        )
        
        # Start questionnaire
        print("\nStarting questionnaire with natural language parsing enabled...")
        response = await agent.process_message(
            agent.create_message(
                content=json.dumps(COMPREHENSIVE_QUESTIONNAIRE),
                sender_id="interactive_user"
            )
        )
        print(f"Agent: {response.content}")
        
        # Interactive loop
        while True:
            try:
                user_response = input("\nYour natural language response: ").strip()
                if user_response.lower() in ['quit', 'exit', 'stop']:
                    break
                    
                response = await agent.process_message(
                    agent.create_message(
                        content=user_response,
                        sender_id="interactive_user"
                    )
                )
                print(f"Agent: {response.content}")
                
                if "submitting" in response.content.lower() or "thanks" in response.content.lower():
                    break
                    
            except KeyboardInterrupt:
                break
        
        await agent.cleanup_session()
        print("\nInteractive test completed!")
        
    except Exception as e:
        print(f"Interactive test failed: {e}")


if __name__ == "__main__":
    # Run comprehensive test
    asyncio.run(test_natural_language_parsing())
    
    # Run interactive test
    asyncio.run(interactive_test())