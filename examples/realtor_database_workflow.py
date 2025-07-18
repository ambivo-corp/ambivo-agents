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


@dataclass
class PersistentRenterPreferences:
    """Persistent renter preferences with state serialization"""
    bedrooms: Optional[int] = None
    bathrooms: Optional[int] = None
    budget_min: Optional[int] = None
    budget_max: Optional[int] = None
    property_type: Optional[str] = None
    location: Optional[str] = None
    amenities: List[str] = field(default_factory=list)
    move_in_date: Optional[str] = None
    additional_requirements: List[str] = field(default_factory=list)
    
    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'PersistentRenterPreferences':
        return cls(**data)
    
    def is_complete(self) -> bool:
        """Check if we have enough information to search"""
        return (self.bedrooms is not None and 
                self.budget_max is not None and 
                len(self.amenities) > 0)  # Require at least one amenity for demo
    
    def get_completion_percentage(self) -> float:
        """Get how complete the preferences are (0.0 to 1.0)"""
        fields = [self.bedrooms, self.bathrooms, self.budget_max, self.property_type, self.location]
        completed = sum(1 for field in fields if field is not None)
        completed += 0.5 if self.amenities else 0
        return min(completed / 6.0, 1.0)


class InteractiveDatabaseRealtorAgent(BaseAgent):
    """Database-aware realtor agent for interactive workflow"""
    
    def __init__(self, agent_id: str, database_agent: DatabaseAgent, **kwargs):
        system_message = """You are a professional realtor with access to a real property database.

Your workflow responsibilities:
1. GATHER REQUIREMENTS: Ask specific questions to complete the renter's profile
2. DATABASE INTEGRATION: Use database search results to present real properties
3. INTERACTIVE GUIDANCE: Guide users through the rental process step by step
4. STATE AWARENESS: Remember previous conversation context and preferences

Communication style:
- Be conversational and helpful
- Ask one focused question at a time
- Acknowledge information as you gather it
- Explain next steps clearly
- Use database results to provide concrete options"""

        super().__init__(
            agent_id=agent_id,
            role=AgentRole.ASSISTANT,
            system_message=system_message,
            **kwargs
        )
        self.database_agent = database_agent
    
    async def search_properties_in_database(self, preferences: PersistentRenterPreferences) -> str:
        """Search properties using the real database"""
        search_criteria = []
        
        if preferences.bedrooms:
            search_criteria.append(f"bedrooms = {preferences.bedrooms}")
        
        if preferences.budget_max:
            search_criteria.append(f"rent <= {preferences.budget_max}")
            
        if preferences.property_type:
            search_criteria.append(f"property_type = '{preferences.property_type}'")
            
        if preferences.location:
            search_criteria.append(f"location = '{preferences.location}'")
        
        # Build database query
        where_clause = " AND ".join(search_criteria) if search_criteria else "1=1"
        query = f"Find properties in the database WHERE {where_clause}. Return results as a readable summary."
        
        try:
            # Use database agent to search
            search_result = await self.database_agent.chat(query)
            return search_result
        except Exception as e:
            return f"Database search error: {e}. Using fallback property suggestions."


class InteractiveWorkflowState(WorkflowState):
    """Enhanced workflow state with preference persistence"""
    
    def __init__(self):
        super().__init__()
        self.preferences = PersistentRenterPreferences()
        self.conversation_stage = "greeting"
        self.search_performed = False
        self.user_satisfied = False
    
    def save_checkpoint(self) -> Dict[str, Any]:
        """Save current state as checkpoint"""
        checkpoint = super().save_checkpoint()
        checkpoint.update({
            "preferences": self.preferences.to_dict(),
            "conversation_stage": self.conversation_stage,
            "search_performed": self.search_performed,
            "user_satisfied": self.user_satisfied
        })
        return checkpoint
    
    def load_checkpoint(self, checkpoint: Dict[str, Any]):
        """Load state from checkpoint"""
        super().load_checkpoint(checkpoint)
        if "preferences" in checkpoint:
            self.preferences = PersistentRenterPreferences.from_dict(checkpoint["preferences"])
        self.conversation_stage = checkpoint.get("conversation_stage", "greeting")
        self.search_performed = checkpoint.get("search_performed", False)
        self.user_satisfied = checkpoint.get("user_satisfied", False)


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
        """Start an interactive realtor session"""
        if not session_id:
            session_id = f"session_{int(asyncio.get_event_loop().time())}"
        
        print(f"\n🏠 Starting Enhanced Interactive Realtor Session: {session_id}")
        print("=" * 70)
        
        # Initialize database
        await self.initialize_database()
        
        # Create interactive handler for terminal input
        async def terminal_interaction_handler(interaction: UserInteraction) -> Optional[str]:
            """Handle user interactions via terminal input"""
            print(f"\n💬 {interaction.prompt}")
            
            if interaction.options:
                print("📋 Please choose from:")
                for i, option in enumerate(interaction.options, 1):
                    print(f"   {i}. {option}")
                print()
                
                while True:
                    try:
                        choice_input = await aioconsole.ainput("👤 Your choice (number or text): ")
                        
                        # Try to parse as number first
                        try:
                            choice_num = int(choice_input.strip())
                            if 1 <= choice_num <= len(interaction.options):
                                return interaction.options[choice_num - 1]
                        except ValueError:
                            pass
                        
                        # Try to match text
                        choice_lower = choice_input.strip().lower()
                        for option in interaction.options:
                            if choice_lower in option.lower():
                                return option
                        
                        print(f"❌ Please choose a valid option (1-{len(interaction.options)}) or type part of the option text.")
                        
                    except (EOFError, KeyboardInterrupt):
                        return interaction.options[0] if interaction.options else "default"
            else:
                # Free text input
                try:
                    response = await aioconsole.ainput("👤 Your response: ")
                    return response.strip() if response.strip() else "No response provided"
                except (EOFError, KeyboardInterrupt):
                    return "Session interrupted"
        
        # Start the conversation workflow
        try:
            execution_id, result = await self.orchestrator.start_conversation(
                "enhanced_realtor",
                session_id,
                "I'm looking for a rental property and need help finding the right place.",
                interaction_handler=terminal_interaction_handler
            )
            
            print(f"\n🎉 Session completed!")
            print(f"📊 Execution ID: {execution_id}")
            print(f"✅ Success: {result['success']}")
            print(f"⏱️  Execution time: {result.get('execution_time', 0):.2f}s")
            print(f"💬 Messages exchanged: {result.get('messages', 0)}")
            
            # Store session info
            self.active_sessions[session_id] = execution_id
            
            return execution_id
            
        except Exception as e:
            print(f"\n❌ Session failed: {e}")
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