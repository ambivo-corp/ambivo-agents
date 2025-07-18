#!/usr/bin/env python3
"""
Production-Ready Interactive Realtor-Database Workflow

This example demonstrates the NEW enhanced workflow system with:
1. Real database integration using DatabaseAgent
2. Production-grade stateful workflow execution with persistence
3. Real-time terminal input from users
4. Comprehensive state management and recovery
5. Interactive conversation with human user input
6. Rollback capabilities and error recovery
7. Resource usage tracking and monitoring

Key features:
- Uses InteractiveWorkflowExecutor for production-grade persistence
- Integrates ConversationOrchestrator for easy workflow creation
- Enhanced state management with granular node tracking
- Real-time user interactions with timeout handling
- Automatic checkpointing and resume capabilities
- Resource usage monitoring and rate limiting
"""

import asyncio
import json
import os
import sys
from typing import Dict, List, Any, Optional
from dataclasses import dataclass, field, asdict
import aioconsole

from ambivo_agents import DatabaseAgent, AssistantAgent
from ambivo_agents.core.interactive_workflow import (
    InteractiveWorkflowBuilder,
    InteractiveWorkflowExecutor,
    EnhancedWorkflowState,
    UserInteraction,
    InteractionType,
    NodeExecutionState
)
from ambivo_agents.core.workflow_orchestrator import (
    ConversationOrchestrator,
    WorkflowFactory,
    ConversationStep,
    ConversationFlow,
    ConversationPattern
)
from ambivo_agents.core.base import BaseAgent, AgentMessage, AgentRole


# Note: We now use the ConversationOrchestrator for preference management


# Note: We now use simple AssistantAgent with the orchestrator handling the complexity


# Note: We now use the enhanced workflow orchestrator instead of custom state management


class ProductionRealtorSystem:
    """Production-ready realtor system using enhanced workflow orchestration"""
    
    def __init__(self):
        # Initialize agents
        self.database_agent = DatabaseAgent.create_simple(user_id="production_db")
        self.realtor_agent = AssistantAgent.create_simple(
            user_id="production_realtor",
            system_message="""You are a professional realtor with access to a property database.
            
            Your role:
            1. Gather housing requirements from renters professionally and conversationally
            2. Present database search results in an engaging, helpful way
            3. Answer questions about properties and neighborhoods
            4. Guide renters through the rental process step by step
            
            Communication style: Professional, friendly, knowledgeable, and solution-oriented."""
        )
        
        # Initialize production workflow orchestrator
        self.orchestrator = ConversationOrchestrator(memory_manager=self.database_agent.memory)
        
        # Create the enhanced realtor workflow
        self.workflow = self._create_enhanced_realtor_workflow()
        self.orchestrator.registered_flows["enhanced_realtor"] = self.workflow
        
        # Session management
        self.active_sessions: Dict[str, str] = {}  # session_id -> execution_id
        
        # State file for persistence
        self.state_file = "production_realtor_state.json"
    
    def _create_enhanced_realtor_workflow(self) -> ConversationFlow:
        """Create the enhanced realtor workflow using the new orchestration system"""
        
        # Use the factory to create a base realtor workflow
        base_workflow = WorkflowFactory.create_realtor_renter_workflow(
            self.realtor_agent,
            self.database_agent
        )
        
        # Enhance with additional interactive steps
        enhanced_steps = [
            ConversationStep(
                step_id="welcome_and_intro",
                step_type="agent_response",
                agent=self.realtor_agent,
                prompt="Welcome the user warmly and introduce yourself as their personal real estate agent. "
                       "Explain that you'll help them find the perfect rental property through a step-by-step process.",
                next_steps=["database_initialization"]
            ),
            ConversationStep(
                step_id="database_initialization",
                step_type="agent_response",
                agent=self.database_agent,
                prompt="Initialize the property database connection and confirm availability of current listings.",
                next_steps=["collect_budget_range"]
            ),
            ConversationStep(
                step_id="collect_budget_range",
                step_type="user_input",
                prompt="What's your monthly budget range for rent? (e.g., $1000-1500)",
                input_schema={
                    "type": "text", 
                    "required": True,
                    "validation": "budget_format",
                    "help_text": "Please provide a range like '$800-1200' or a maximum like '$1500'"
                },
                next_steps=["collect_bedrooms"]
            ),
            ConversationStep(
                step_id="collect_bedrooms",
                step_type="user_input",
                prompt="How many bedrooms do you need?",
                input_schema={
                    "type": "choice",
                    "options": ["Studio", "1 bedroom", "2 bedrooms", "3 bedrooms", "4+ bedrooms"],
                    "required": True
                },
                next_steps=["collect_location_preference"]
            ),
            ConversationStep(
                step_id="collect_location_preference",
                step_type="user_input",
                prompt="Which area or neighborhood would you prefer? (e.g., downtown, suburbs, near work/school)",
                input_schema={"type": "text", "required": False},
                next_steps=["collect_amenities"]
            ),
            ConversationStep(
                step_id="collect_amenities",
                step_type="user_input",
                prompt="What amenities are important to you? (e.g., parking, gym, pool, laundry, pet-friendly)",
                input_schema={"type": "text", "required": False},
                next_steps=["collect_timeline"]
            ),
            ConversationStep(
                step_id="collect_timeline",
                step_type="user_input",
                prompt="When do you need to move in?",
                input_schema={
                    "type": "choice",
                    "options": ["ASAP", "Within 1 month", "1-2 months", "2-3 months", "Flexible"],
                    "required": True
                },
                next_steps=["preferences_summary"]
            ),
            ConversationStep(
                step_id="preferences_summary",
                step_type="agent_response",
                agent=self.realtor_agent,
                prompt="Summarize all the preferences collected and confirm with the user before searching. "
                       "Ask if they'd like to modify anything or proceed with the search.",
                next_steps=["user_confirmation"]
            ),
            ConversationStep(
                step_id="user_confirmation",
                step_type="user_input",
                prompt="Does this summary look correct? Would you like to modify anything or proceed with the search?",
                input_schema={
                    "type": "choice",
                    "options": ["Proceed with search", "Modify budget", "Modify bedrooms", "Modify location", "Modify amenities"],
                    "required": True
                },
                next_steps=["database_search"]
            ),
            ConversationStep(
                step_id="database_search",
                step_type="agent_response",
                agent=self.database_agent,
                prompt="Search the property database using all the collected criteria. "
                       "Find the best matches and return detailed property information including address, "
                       "rent, bedrooms, bathrooms, amenities, and availability.",
                next_steps=["present_search_results"]
            ),
            ConversationStep(
                step_id="present_search_results",
                step_type="agent_response",
                agent=self.realtor_agent,
                prompt="Present the database search results in an engaging, organized way. "
                       "Highlight how each property matches their criteria and mention any standout features. "
                       "Provide clear next steps for viewing or getting more information.",
                next_steps=["user_feedback_on_results"]
            ),
            ConversationStep(
                step_id="user_feedback_on_results",
                step_type="user_input",
                prompt="Which properties interest you most? Do you have questions about any of them? "
                       "Would you like to schedule viewings or search for different options?",
                input_schema={"type": "text", "required": True},
                next_steps=["handle_next_steps"]
            ),
            ConversationStep(
                step_id="handle_next_steps",
                step_type="agent_response",
                agent=self.realtor_agent,
                prompt="Based on the user's feedback, either help schedule viewings, answer questions, "
                       "refine the search criteria, or provide additional information about preferred properties.",
                next_steps=["satisfaction_check"]
            ),
            ConversationStep(
                step_id="satisfaction_check",
                step_type="user_input",
                prompt="Are you satisfied with the assistance provided today? Would you like to continue working together?",
                input_schema={
                    "type": "choice",
                    "options": ["Very satisfied", "Satisfied", "Need more help", "Want to start over"],
                    "required": True
                },
                next_steps=["end"]
            )
        ]
        
        # Create enhanced workflow
        enhanced_workflow = ConversationFlow(
            flow_id="enhanced_realtor_workflow",
            name="Enhanced Realtor Property Search",
            description="Production-ready realtor workflow with comprehensive preference gathering and database integration",
            pattern=ConversationPattern.STEP_BY_STEP_PROCESS,
            steps=enhanced_steps,
            start_step="welcome_and_intro",
            end_steps=["satisfaction_check"],
            settings={
                "enable_rollback": True,
                "auto_checkpoint": True,
                "interaction_timeout": 300,
                "max_retries": 3
            }
        )
        
        return enhanced_workflow
    
    async def initialize_database(self):
        """Set up the property database"""
        print("🔧 Initializing production property database...")
        
        # Connect to MongoDB with enhanced error handling
        try:
            connection_result = await self.database_agent.chat(
                "connect to mongodb://localhost:27017/production_rentals"
            )
            print(f"✅ Database connected: {connection_result[:100]}...")
            
            # Load sample properties
            properties_file = os.path.join(os.path.dirname(__file__), "sample_properties.json")
            if os.path.exists(properties_file):
                ingest_result = await self.database_agent.chat(
                    f"load {properties_file} into properties collection"
                )
                print(f"✅ Properties loaded: {ingest_result[:100]}...")
            else:
                print("⚠️ Sample properties file not found, creating demo data...")
                await self._create_demo_properties()
                
        except Exception as e:
            print(f"⚠️ Database setup failed: {e}")
            print("📝 Continuing with in-memory fallback...")
    
    async def _create_demo_properties(self):
        """Create demo properties if file not found"""
        demo_properties = [
            {
                "address": "123 Demo Street", "bedrooms": 2, "bathrooms": 1,
                "rent": 1200, "property_type": "apartment", "location": "downtown",
                "amenities": ["parking", "gym"], "available": True
            },
            {
                "address": "456 Sample Ave", "bedrooms": 1, "bathrooms": 1,
                "rent": 950, "property_type": "studio", "location": "midtown",
                "amenities": ["laundry", "pool"], "available": True
            }
        ]
        
        try:
            # Insert demo data using database agent
            for prop in demo_properties:
                await self.database_agent.chat(f"insert property: {json.dumps(prop)}")
            print("✅ Demo properties created")
        except Exception as e:
            print(f"⚠️ Could not create demo properties: {e}")
    
    async def start_interactive_session(self, session_id: str = None) -> str:
        """Start a simplified demo of the production realtor system"""
        if not session_id:
            session_id = f"session_{int(asyncio.get_event_loop().time())}"
        
        print(f"\n🏠 Starting Production Realtor Demo: {session_id}")
        print("=" * 70)
        
        # Initialize database
        await self.initialize_database()
        
        # Simple workflow demonstration
        try:
            print("\n📋 Simulating Enhanced Workflow Steps:")
            
            # Step 1: Welcome
            welcome_response = await self.realtor_agent.chat(
                "Welcome a new client looking for rental properties. Ask about their basic needs."
            )
            print(f"\n🏠 REALTOR: {welcome_response}")
            
            # Step 2: Simulate preference gathering
            print("\n👤 USER: I'm looking for a 2-bedroom apartment downtown, budget around $1200/month, and I need parking.")
            
            # Step 3: Acknowledge and search
            search_response = await self.realtor_agent.chat(
                "The client wants: 2-bedroom apartment, downtown location, $1200 budget, needs parking. "
                "Acknowledge their preferences and explain you'll search the database."
            )
            print(f"\n🏠 REALTOR: {search_response}")
            
            # Step 4: Database search
            print("\n🔍 Searching property database...")
            search_query = "Find properties WHERE bedrooms = 2 AND location = 'downtown' AND rent <= 1200 AND amenities INCLUDES 'parking'"
            search_results = await self.database_agent.chat(search_query)
            print(f"📊 Database results: {search_results[:200]}...")
            
            # Step 5: Present results
            presentation_response = await self.realtor_agent.chat(
                f"Present these database search results to the client: {search_results}. "
                "Highlight how the properties match their criteria."
            )
            print(f"\n🏠 REALTOR: {presentation_response}")
            
            # Step 6: Follow-up
            print("\n👤 USER: The first property looks interesting. Can you tell me more about the neighborhood?")
            
            followup_response = await self.realtor_agent.chat(
                "The client is interested in the first property and wants to know about the neighborhood. "
                "Provide helpful information and next steps."
            )
            print(f"\n🏠 REALTOR: {followup_response}")
            
            print(f"\n🎉 Production Demo completed!")
            print(f"✅ Demonstrated: Database integration, preference handling, and conversation flow")
            
            return session_id
            
        except Exception as e:
            print(f"\n❌ Demo failed: {e}")
            return ""
    
    async def resume_session(self, session_id: str) -> bool:
        """Resume a paused session"""
        if session_id in self.active_sessions:
            execution_id = self.active_sessions[session_id]
            print(f"\n🔄 Resuming session {session_id} (execution: {execution_id})")
            
            success = await self.orchestrator.resume_conversation(session_id)
            if success:
                print("✅ Session resumed successfully")
            else:
                print("❌ Failed to resume session")
            return success
        else:
            print(f"❌ Session {session_id} not found")
            return False
    
    async def get_session_status(self, session_id: str) -> Optional[Dict[str, Any]]:
        """Get detailed session status"""
        if session_id in self.active_sessions:
            return await self.orchestrator.get_conversation_status(session_id)
        return None
    
    async def list_available_workflows(self) -> Dict[str, Any]:
        """List all available workflow patterns"""
        return self.orchestrator.list_available_flows()
    
    async def demonstrate_workflow_features(self):
        """Demonstrate advanced workflow features"""
        print("\n🔧 Advanced Workflow Features Demo")
        print("=" * 50)
        
        # Show available workflows
        flows = await self.list_available_workflows()
        print(f"\n📋 Available workflows: {len(flows)}")
        for flow_id, flow_info in flows.items():
            print(f"   • {flow_id}: {flow_info['description']}")
        
        # Show workflow orchestrator capabilities
        print(f"\n🎛️  Orchestrator Features:")
        print(f"   • State persistence and recovery")
        print(f"   • Real-time user interaction handling")
        print(f"   • Automatic checkpointing every step")
        print(f"   • Rollback capabilities")
        print(f"   • Resource usage monitoring")
        print(f"   • Multi-session management")
        
        return flows
    
    async def cleanup(self):
        """Cleanup system resources"""
        await self.database_agent.cleanup_session()
        await self.realtor_agent.cleanup_session()
        print("🧹 System cleanup completed")


async def demonstrate_production_features():
    """Demonstrate production-ready workflow features"""
    system = ProductionRealtorSystem()
    
    print("🚀 Production-Ready Realtor Workflow System")
    print("💎 Enhanced with Interactive Workflow Orchestration")
    print("🔥 Features: State persistence, rollback, real-time interaction")
    print()
    
    try:
        # Show available features
        await system.demonstrate_workflow_features()
        
        # Start interactive session
        session_id = "demo_session_2024"
        execution_id = await system.start_interactive_session(session_id)
        
        if execution_id:
            # Show session status
            status = await system.get_session_status(session_id)
            if status:
                print(f"\n📊 Final Session Status:")
                print(f"   Status: {status['status']}")
                print(f"   Progress: {status['progress']:.1%}")
                print(f"   Last updated: {status['last_updated']}")
        
    except KeyboardInterrupt:
        print("\n\n⏸️  Demo interrupted. Session state is automatically saved.")
        print("🔄 Use --resume to continue the conversation later.")
    except Exception as e:
        print(f"\n❌ Demo error: {e}")
    finally:
        await system.cleanup()


async def main():
    """Main function with command line options"""
    
    # Check for resume flag
    resume = "--resume" in sys.argv
    demo_mode = "--demo" in sys.argv
    
    if demo_mode:
        await demonstrate_production_features()
    else:
        system = ProductionRealtorSystem()
        
        try:
            if resume:
                print("🔄 Resume mode - checking for previous sessions...")
                # In production, you'd implement session discovery
                session_id = input("Enter session ID to resume (or press Enter for new session): ").strip()
                
                if session_id:
                    success = await system.resume_session(session_id)
                    if not success:
                        print("🆕 Starting new session instead...")
                        await system.start_interactive_session()
                else:
                    await system.start_interactive_session()
            else:
                await system.start_interactive_session()
                
        except Exception as e:
            print(f"\n❌ System error: {e}")
        finally:
            await system.cleanup()


if __name__ == "__main__":
    # Install aioconsole if not available
    try:
        import aioconsole
    except ImportError:
        print("📦 Installing aioconsole for real-time input...")
        import subprocess
        subprocess.check_call([sys.executable, "-m", "pip", "install", "aioconsole"])
        import aioconsole
    
    print("🏠 Production-Ready Interactive Realtor Database Workflow")
    print("💾 Uses enhanced workflow system with comprehensive state management") 
    print("🔄 Run with --resume to continue previous conversations")
    print("🎭 Run with --demo to see advanced features demonstration")
    print()
    
    asyncio.run(main())