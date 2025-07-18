#!/usr/bin/env python3
"""
Workflow Developer Agent Example

This example demonstrates how to use the WorkflowDeveloperAgent to automatically
generate workflow code by answering a series of questions.

The agent will:
1. Ask about your domain (e.g., "E-commerce customer service")
2. Suggest agents you need
3. Help design workflow steps  
4. Configure persistence (SQLite by default)
5. Generate complete Python files with all boilerplate code

Generated files include:
- Complete workflow system following WORKFLOW.md patterns
- Test file with examples
- All imports and configuration
- Helpful comments for customization

Output location:
- Files are generated in docker_shared/output/generated_workflows/
- This follows the consistent input/output directory structure used by all agents
"""

import asyncio
from ambivo_agents.agents.workflow_developer import WorkflowDeveloperAgent


async def interactive_workflow_generation():
    """
    Interactive workflow generation session.
    The agent will guide you through creating a custom workflow.
    """
    print("🏗️ Workflow Developer Agent - Interactive Session")
    print("=" * 60)
    print("I'll help you create a complete workflow system!")
    print("Just answer my questions and I'll generate all the code.\n")
    
    # Create the workflow developer agent
    developer_agent = WorkflowDeveloperAgent.create_simple(
        user_id="workflow_developer_demo"
    )
    
    try:
        # Start the conversation
        response = await developer_agent.chat("Hello, I want to create a new workflow system")
        print(f"🤖 Agent: {response}")
        
        # Interactive loop
        while True:
            try:
                user_input = input("\n👤 You: ").strip()
                
                if user_input.lower() in ['exit', 'quit', 'bye']:
                    print("\n👋 Thanks for using the Workflow Developer Agent!")
                    break
                
                if not user_input:
                    continue
                
                # Get response from agent
                response = await developer_agent.chat(user_input)
                print(f"\n🤖 Agent: {response}")
                
                # Check if code generation is complete
                if "Generated workflow files" in response or "Workflow Code Generated Successfully" in response:
                    print("\n🎉 Your workflow code has been generated!")
                    print("Check the docker_shared/output/generated_workflows/ directory for your files.")
                    break
                    
            except KeyboardInterrupt:
                print("\n\n⏸️ Session interrupted. Your progress is saved!")
                break
            except EOFError:
                print("\n\n👋 Session ended.")
                break
                
    except Exception as e:
        print(f"\n❌ Error: {e}")
        
    finally:
        await developer_agent.cleanup_session()


async def automated_workflow_generation_demo():
    """
    Automated demo showing the complete workflow generation process.
    This simulates a developer answering all the questions automatically.
    """
    print("🚀 Automated Workflow Generation Demo")
    print("=" * 50)
    print("Simulating a developer creating an e-commerce workflow...\n")
    
    developer_agent = WorkflowDeveloperAgent.create_simple(
        user_id="automated_demo"
    )
    
    try:
        # Predefined responses for demo
        demo_conversation = [
            ("Hello, I want to create a new workflow", "Starting workflow creation"),
            ("E-commerce customer service", "Domain specification"),
            ("suggested", "Using suggested agents"),
            ("1. Welcome customer and understand their needs\n2. Collect product preferences and budget\n3. Search product database\n4. Present product options\n5. Handle questions and finalize order", "Defining workflow steps"),
            ("SQLite", "Configuring persistence"),
            ("web search, api calls", "Adding additional features"),
            ("generate", "Generating code")
        ]
        
        for user_input, stage in demo_conversation:
            print(f"📝 {stage}...")
            print(f"👤 User: {user_input}")
            
            response = await developer_agent.chat(user_input)
            print(f"🤖 Agent: {response[:200]}...")
            print()
            
            # Small delay for demo effect
            await asyncio.sleep(1)
            
            if "Generated workflow files" in response or "Workflow Code Generated Successfully" in response:
                print("🎉 Demo completed! E-commerce workflow generated successfully!")
                break
                
    except Exception as e:
        print(f"❌ Demo error: {e}")
        
    finally:
        await developer_agent.cleanup_session()


async def quick_workflow_test():
    """
    Quick test to verify the WorkflowDeveloperAgent is working correctly.
    """
    print("🧪 Quick Workflow Developer Agent Test")
    print("=" * 40)
    
    try:
        # Create agent
        agent = WorkflowDeveloperAgent.create_simple(user_id="test_agent")
        
        # Test basic functionality
        response = await agent.chat("Hello")
        assert "Welcome to the Workflow Developer Agent" in response
        print("✅ Agent initialization: PASSED")
        
        # Test domain collection
        response = await agent.chat("Healthcare patient intake")
        assert "HealthcarePatientIntakeWorkflowSystem" in response or "class name" in response.lower()
        print("✅ Domain processing: PASSED")
        
        # Cleanup
        await agent.cleanup_session()
        print("✅ Cleanup: PASSED")
        
        print("\n🎉 All tests passed! WorkflowDeveloperAgent is working correctly.")
        
    except Exception as e:
        print(f"❌ Test failed: {e}")


async def main():
    """Main function with different usage options"""
    print("🏗️ Workflow Developer Agent Examples")
    print("=" * 50)
    print("Choose an option:")
    print("1. Interactive workflow generation (recommended)")
    print("2. Automated demo")
    print("3. Quick test")
    print()
    
    try:
        choice = input("Enter your choice (1-3) or press Enter for interactive: ").strip()
    except (EOFError, KeyboardInterrupt):
        choice = "1"  # Default to interactive
    
    if choice == "2":
        await automated_workflow_generation_demo()
    elif choice == "3":
        await quick_workflow_test()
    else:
        await interactive_workflow_generation()


if __name__ == "__main__":
    asyncio.run(main())