#!/usr/bin/env python3
"""
Enhanced Realtor-Renter Multi-Agent Chat System

This example demonstrates how to build sophisticated multi-agent conversation systems
using the NEW enhanced workflow capabilities. This version focuses on:

1. Custom agent classes with specialized behaviors
2. Property matching algorithms with scoring logic
3. Educational workflow patterns for learning
4. Flexible agent orchestration without database dependency
5. Advanced conversation management techniques

Updated Features:
- Uses enhanced ConversationOrchestrator from workflow_orchestrator.py
- Maintains custom agent logic and property scoring algorithms
- Shows advanced workflow patterns for educational purposes
- Demonstrates multi-agent collaboration techniques
- Provides template for building complex agent interactions

This example complements realtor_database_workflow.py by focusing on:
- Algorithm development (property matching, scoring)
- Custom agent behavior patterns
- Educational workflow construction
- Multi-agent conversation techniques
"""

import asyncio
import json
import os
from typing import Dict, List, Any, Optional
from dataclasses import dataclass, field
from enum import Enum

from ambivo_agents import ModeratorAgent, AssistantAgent, DatabaseAgent
from ambivo_agents.core.base import AgentMessage, AgentRole, BaseAgent
from ambivo_agents.core.workflow_orchestrator import (
    ConversationOrchestrator,
    ConversationFlow,
    ConversationStep,
    ConversationPattern
)


class ConversationStage(Enum):
    """Stages of the realtor-renter conversation"""
    INITIAL_GREETING = "initial_greeting"
    GATHERING_REQUIREMENTS = "gathering_requirements" 
    SEARCHING_PROPERTIES = "searching_properties"
    PRESENTING_OPTIONS = "presenting_options"
    CLARIFYING_DETAILS = "clarifying_details"
    FINALIZING_SELECTION = "finalizing_selection"
    COMPLETED = "completed"


@dataclass
class RenterPreferences:
    """Data structure to track renter preferences"""
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
        return {
            "bedrooms": self.bedrooms,
            "bathrooms": self.bathrooms, 
            "budget_min": self.budget_min,
            "budget_max": self.budget_max,
            "property_type": self.property_type,
            "location": self.location,
            "amenities": self.amenities,
            "move_in_date": self.move_in_date,
            "additional_requirements": self.additional_requirements
        }
    
    def is_complete(self) -> bool:
        """Check if we have enough information to search"""
        return (self.bedrooms is not None and 
                self.budget_max is not None and 
                self.property_type is not None)


class RealtorAgent(BaseAgent):
    """Realtor agent that asks questions and presents properties"""
    
    def __init__(self, agent_id: str, **kwargs):
        system_message = """You are a helpful and professional realtor agent. Your role is to:

1. GATHER REQUIREMENTS: Ask about housing preferences in a conversational way
   - Number of bedrooms and bathrooms
   - Budget range
   - Property type (apartment, house, condo, studio)
   - Location preferences
   - Desired amenities
   - Move-in timeline

2. PRESENT PROPERTIES: When you receive property search results, present them clearly
   - Highlight key features that match their criteria
   - Mention any tradeoffs or alternatives
   - Ask if they want more details about specific properties

3. COMMUNICATION STYLE:
   - Be friendly and professional
   - Ask one or two questions at a time (don't overwhelm)
   - Use natural language, not forms or lists
   - Acknowledge their preferences as you gather them
   - Be helpful in explaining options

4. FLEXIBILITY: 
   - If their budget is tight, suggest alternatives
   - If requirements are too specific, ask about flexibility
   - Always try to be helpful and solution-oriented

Remember: You're building a relationship, not just collecting data."""

        super().__init__(
            agent_id=agent_id,
            role=AgentRole.ASSISTANT,
            system_message=system_message,
            **kwargs
        )


class RenterAgent(BaseAgent):
    """Renter agent that responds with preferences and asks questions"""
    
    def __init__(self, agent_id: str, **kwargs):
        system_message = """You are a prospective renter looking for housing. Your role is to:

1. RESPOND TO QUESTIONS: Answer the realtor's questions about your housing needs
   - Be realistic about your preferences and budget
   - Mention specific needs or dealbreakers when relevant
   - Ask clarifying questions if you need more information

2. EVALUATE PROPERTIES: When shown properties, provide genuine feedback
   - Express interest in properties that fit your needs
   - Ask questions about specific features or concerns
   - Request more details or alternatives when appropriate

3. COMMUNICATION STYLE:
   - Be conversational and natural
   - Share relevant context about your situation
   - Be honest about budget constraints or specific needs
   - Show appreciation for good suggestions

4. YOUR PROFILE (customize as needed):
   - Budget: $800-1400/month
   - Looking for: 1-2 bedrooms
   - Priority: Good location, reasonable commute
   - Nice to have: Parking, laundry, modern amenities
   - Timeline: Move in within 2 months

Feel free to adapt this profile or create your own preferences during the conversation."""

        super().__init__(
            agent_id=agent_id,
            role=AgentRole.ASSISTANT, 
            system_message=system_message,
            **kwargs
        )


class PropertySearchAgent(BaseAgent):
    """Agent that handles property database operations and search logic"""
    
    def __init__(self, agent_id: str, properties_data: List[Dict], **kwargs):
        system_message = """You are a property search specialist. Your role is to:

1. SEARCH PROPERTIES: Find properties that match renter criteria
2. RANK RESULTS: Sort by best fit for their requirements  
3. PROVIDE CONTEXT: Explain why properties match or don't match
4. SUGGEST ALTERNATIVES: When exact matches aren't available

You have access to a property database and should provide structured search results."""

        super().__init__(
            agent_id=agent_id,
            role=AgentRole.ANALYST,
            system_message=system_message,
            **kwargs
        )
        self.properties = properties_data
    
    def search_properties(self, preferences: RenterPreferences) -> List[Dict[str, Any]]:
        """Search properties based on renter preferences"""
        matches = []
        
        for prop in self.properties:
            score = 0
            reasons = []
            
            # Bedroom match
            if preferences.bedrooms and prop["bedrooms"] == preferences.bedrooms:
                score += 10
                reasons.append(f"Exact bedroom match ({prop['bedrooms']} bedrooms)")
            elif preferences.bedrooms and abs(prop["bedrooms"] - preferences.bedrooms) <= 1:
                score += 5
                reasons.append(f"Close bedroom match ({prop['bedrooms']} vs {preferences.bedrooms} requested)")
            
            # Budget match
            if preferences.budget_max and prop["rent"] <= preferences.budget_max:
                if preferences.budget_min and prop["rent"] >= preferences.budget_min:
                    score += 10
                    reasons.append(f"Within budget (${prop['rent']}/month)")
                else:
                    score += 8
                    reasons.append(f"Within max budget (${prop['rent']}/month)")
            elif preferences.budget_max and prop["rent"] <= preferences.budget_max * 1.1:
                score += 3
                reasons.append(f"Slightly over budget (${prop['rent']}/month)")
            
            # Property type match
            if preferences.property_type and prop["property_type"] == preferences.property_type:
                score += 8
                reasons.append(f"Preferred property type ({prop['property_type']})")
            
            # Location match
            if preferences.location and prop["location"] == preferences.location:
                score += 6
                reasons.append(f"Preferred location ({prop['location']})")
            
            # Amenities match
            if preferences.amenities:
                matching_amenities = set(preferences.amenities) & set(prop["amenities"])
                if matching_amenities:
                    score += len(matching_amenities) * 2
                    reasons.append(f"Has amenities: {', '.join(matching_amenities)}")
            
            # Only include properties with some relevance
            if score > 0:
                matches.append({
                    "property": prop,
                    "score": score,
                    "match_reasons": reasons
                })
        
        # Sort by score (best matches first)
        matches.sort(key=lambda x: x["score"], reverse=True)
        return matches


class EducationalRealtorOrchestrator:
    """
    Educational orchestrator demonstrating advanced multi-agent patterns using enhanced workflows.
    
    This class showcases:
    1. How to build custom workflows using the new orchestration system
    2. Advanced property matching algorithms with scoring
    3. Multi-agent collaboration patterns
    4. Educational workflow construction techniques
    """
    
    def __init__(self):
        # Load property data for algorithm demonstration
        properties_file = os.path.join(os.path.dirname(__file__), "sample_properties.json")
        with open(properties_file, 'r') as f:
            self.properties_data = json.load(f)
        
        # Initialize custom agents with specialized behaviors
        self.realtor = RealtorAgent.create_simple(user_id="educational_realtor")
        self.renter = RenterAgent.create_simple(user_id="educational_renter") 
        self.property_search = PropertySearchAgent.create_simple(
            user_id="educational_search",
            properties_data=self.properties_data
        )
        
        # Initialize enhanced workflow orchestrator
        self.workflow_orchestrator = ConversationOrchestrator()
        
        # Educational state tracking
        self.preferences = RenterPreferences()
        self.search_results = []
        self.algorithm_demonstrations = []
        
        # Create educational workflows
        self._setup_educational_workflows()
    
    def _setup_educational_workflows(self):
        """Setup educational workflows demonstrating different patterns"""
        
        # 1. Multi-agent debate workflow (educational pattern)
        debate_flow = self.workflow_orchestrator.create_multi_agent_flow(
            "property_debate",
            {
                "realtor_perspective": self.realtor,
                "renter_perspective": self.renter
            },
            ["realtor_perspective", "renter_perspective"],
            coordination_style="debate"
        )
        
        # 2. Information gathering with custom scoring
        scoring_questions = [
            {
                "text": "How many bedrooms do you need?", 
                "schema": {"type": "choice", "options": ["1", "2", "3", "4+"]}
            },
            {
                "text": "What's your maximum monthly budget?",
                "schema": {"type": "text", "validation": "numeric"}
            },
            {
                "text": "Which location do you prefer?",
                "schema": {"type": "choice", "options": ["downtown", "midtown", "suburbs", "uptown"]}
            },
            {
                "text": "What amenities are most important to you?",
                "schema": {"type": "text"}
            }
        ]
        
        scoring_flow = self.workflow_orchestrator.create_information_gathering_flow(
            "property_scoring_flow",
            self.realtor,
            scoring_questions,
            final_action="demonstrate_scoring_algorithm"
        )
        
        # Register educational workflows
        self.workflow_orchestrator.registered_flows["educational_debate"] = debate_flow
        self.workflow_orchestrator.registered_flows["educational_scoring"] = scoring_flow
    
    async def demonstrate_property_scoring_algorithm(self):
        """Educational demonstration of the property scoring algorithm"""
        print("\n🧮 Property Scoring Algorithm Demonstration")
        print("=" * 60)
        
        # Use the custom PropertySearchAgent scoring logic
        matches = self.property_search.search_properties(self.preferences)
        
        print(f"📊 Scored {len(self.properties_data)} properties:")
        print(f"✅ Found {len(matches)} matching properties")
        
        if matches:
            print("\n🏆 Top 3 Matches with Scoring Breakdown:")
            for i, match in enumerate(matches[:3], 1):
                prop = match["property"]
                score = match["score"]
                reasons = match["match_reasons"]
                
                print(f"\n{i}. {prop['address']} (Score: {score})")
                print(f"   📍 {prop['bedrooms']}BR/{prop['bathrooms']}BA - ${prop['rent']}/month")
                print(f"   🎯 Match reasons: {', '.join(reasons)}")
                
                # Educational: Show scoring breakdown
                print(f"   📈 Scoring algorithm details:")
                print(f"      • Base relevance: Property matched search criteria")
                print(f"      • Bedroom match: +10 points for exact match, +5 for close match")
                print(f"      • Budget match: +10 points within budget, +8 under max")
                print(f"      • Property type: +8 points for preferred type")
                print(f"      • Location: +6 points for preferred location")
                print(f"      • Amenities: +2 points per matching amenity")
        
        self.algorithm_demonstrations.append({
            "algorithm": "property_scoring",
            "input_properties": len(self.properties_data),
            "matches_found": len(matches),
            "top_score": matches[0]["score"] if matches else 0,
            "preferences_used": self.preferences.to_dict()
        })
        
        return matches
    
    async def demonstrate_multi_agent_collaboration(self):
        """Educational demonstration of multi-agent collaboration patterns"""
        print("\n🤝 Multi-Agent Collaboration Patterns Demo")
        print("=" * 60)
        
        print("🎭 Pattern 1: Agent Debate (Different Perspectives)")
        
        # Start debate workflow
        session_id = "educational_debate_session"
        execution_id, result = await self.workflow_orchestrator.start_conversation(
            "educational_debate",
            session_id,
            "Should this renter prioritize location convenience or budget savings?"
        )
        
        print(f"🔄 Debate workflow executed: {execution_id}")
        print(f"📊 Result: {result['success']}")
        
        print("\n🎭 Pattern 2: Sequential Information Processing")
        
        # Demonstrate sequential agent processing
        steps = [
            ("Realtor", "Initial assessment of renter needs"),
            ("PropertySearch", "Algorithm-based property matching"),
            ("Realtor", "Presentation of curated results")
        ]
        
        for i, (agent_name, task) in enumerate(steps, 1):
            print(f"   Step {i}: {agent_name} - {task}")
        
        return {
            "patterns_demonstrated": ["debate", "sequential_processing"],
            "agents_involved": ["realtor", "renter", "property_search"],
            "educational_value": "Shows different coordination patterns"
        }
    
    async def run_educational_demo(self, demo_type: str = "full"):
        """Run educational demonstrations of different workflow patterns"""
        print("🎓 Educational Realtor-Renter Workflow Demonstration")
        print("📚 This demo teaches advanced multi-agent conversation patterns")
        print("=" * 70)
        
        if demo_type in ["full", "scoring"]:
            # Demo 1: Property Scoring Algorithm
            print("\n📖 LESSON 1: Advanced Property Scoring Algorithms")
            
            # Simulate gathering preferences for demonstration
            self.preferences.bedrooms = 2
            self.preferences.budget_max = 1300
            self.preferences.property_type = "apartment"
            self.preferences.location = "downtown"
            self.preferences.amenities = ["parking", "gym"]
            
            scoring_results = await self.demonstrate_property_scoring_algorithm()
        
        if demo_type in ["full", "collaboration"]:
            # Demo 2: Multi-Agent Collaboration
            print("\n📖 LESSON 2: Multi-Agent Collaboration Patterns")
            collaboration_results = await self.demonstrate_multi_agent_collaboration()
        
        if demo_type in ["full", "workflows"]:
            # Demo 3: Workflow Construction
            print("\n📖 LESSON 3: Custom Workflow Construction")
            await self.demonstrate_workflow_construction()
        
        # Summary
        print("\n🎯 Educational Demo Summary")
        print("=" * 40)
        print("✅ Property scoring algorithm demonstrated")
        print("✅ Multi-agent collaboration patterns shown")
        print("✅ Workflow construction techniques explained")
        print(f"📊 Algorithm demonstrations logged: {len(self.algorithm_demonstrations)}")
        
        return {
            "demos_completed": demo_type,
            "algorithms_demonstrated": self.algorithm_demonstrations,
            "educational_value": "Comprehensive multi-agent workflow education"
        }
    
    async def demonstrate_workflow_construction(self):
        """Educational demonstration of how to construct custom workflows"""
        print("\n🏗️ Custom Workflow Construction Tutorial")
        print("-" * 50)
        
        print("1️⃣ Creating a Simple Information Gathering Flow:")
        print("   • Define conversation steps")
        print("   • Set up agent roles")
        print("   • Configure user input schemas")
        print("   • Link steps with next_steps")
        
        print("\n2️⃣ Creating Multi-Agent Collaboration:")
        print("   • Sequential: Agents pass results to next agent")
        print("   • Parallel: Multiple agents work simultaneously")
        print("   • Debate: Agents present different perspectives")
        print("   • Consensus: Agents work toward agreement")
        
        print("\n3️⃣ Advanced Patterns:")
        print("   • Conditional branching based on responses")
        print("   • Dynamic workflow modification")
        print("   • State persistence and recovery")
        print("   • Error handling and fallback strategies")
        
        # Show code example
        print("\n💻 Code Example - Custom Workflow:")
        print("""
        # Create custom workflow
        orchestrator = ConversationOrchestrator()
        
        # Method 1: Use factory patterns
        flow = WorkflowFactory.create_realtor_renter_workflow(realtor, database)
        
        # Method 2: Build custom flow
        custom_flow = orchestrator.create_information_gathering_flow(
            "custom_flow", agent, questions, final_action="custom_processing"
        )
        
        # Method 3: Multi-agent patterns
        debate_flow = orchestrator.create_multi_agent_flow(
            "agent_debate", agents_dict, agent_sequence, "debate"
        )
        """)
        
        return {
            "tutorial_completed": True,
            "patterns_explained": ["information_gathering", "multi_agent", "advanced"],
            "code_examples_shown": True
        }
    
    async def start_conversation(self):
        """Start the enhanced realtor-renter conversation with educational features"""
        print("🏠 Enhanced Realtor-Renter Chat System Starting...")
        print("🎓 Educational Features: Property algorithms, Multi-agent patterns")
        print("=" * 70)
        
        # Show available educational demos
        print("\n📚 Available Educational Demonstrations:")
        print("1. Property Scoring Algorithm Demo")
        print("2. Multi-Agent Collaboration Patterns") 
        print("3. Custom Workflow Construction Tutorial")
        print("4. Full Educational Experience")
        
        choice = input("\nChoose demo (1-4) or Enter for full experience: ").strip()
        
        demo_map = {
            "1": "scoring",
            "2": "collaboration", 
            "3": "workflows",
            "4": "full",
            "": "full"
        }
        
        demo_type = demo_map.get(choice, "full")
        
        return await self.run_educational_demo(demo_type)
    
    async def cleanup(self):
        """Cleanup all agents"""
        await self.realtor.cleanup_session()
        await self.renter.cleanup_session()
        await self.property_search.cleanup_session()


# Updated main function to run educational demo
async def run_enhanced_realtor_renter_demo():
    """Run the enhanced realtor-renter conversation demo with educational features"""
    orchestrator = EducationalRealtorOrchestrator()
    
    try:
        result = await orchestrator.start_conversation()
        
        print("\n" + "=" * 70)
        print("🎉 Educational Demo Complete!")
        print(f"📚 Educational value: {result.get('educational_value', 'N/A')}")
        print(f"🧮 Algorithms demonstrated: {len(result.get('algorithms_demonstrated', []))}")
        
    except KeyboardInterrupt:
        print("\n\n👋 Demo interrupted by user")
    except Exception as e:
        print(f"\n❌ Demo error: {e}")
    finally:
        await orchestrator.cleanup()


# Example of how third-party developers can customize the system
class CustomRealtorAgent(RealtorAgent):
    """Example of customizing the realtor for specific use cases"""
    
    def __init__(self, agent_id: str, specialization: str = "luxury", **kwargs):
        # Customize system message based on specialization
        if specialization == "luxury":
            custom_system = """You are a luxury real estate specialist. Focus on:
            - High-end amenities and features
            - Premium locations and neighborhoods  
            - Concierge services and exclusive access
            - Investment potential and property value
            Be sophisticated in your presentation while remaining approachable."""
        elif specialization == "budget":
            custom_system = """You are a budget-friendly housing specialist. Focus on:
            - Value for money and cost-effectiveness
            - Hidden gems and upcoming neighborhoods
            - Creative financing and rental options
            - Practical needs over luxury features
            Be understanding of budget constraints and helpful with alternatives."""
        else:
            custom_system = None
        
        super().__init__(agent_id, **kwargs)
        if custom_system:
            self.system_message = custom_system


async def demonstrate_customization_patterns():
    """Demonstrate how third-party developers can customize the system"""
    print("🛠️ Customization Patterns for Third-Party Developers")
    print("=" * 60)
    
    # Example 1: Custom agent specializations
    luxury_realtor = CustomRealtorAgent.create_simple(
        user_id="luxury_specialist",
        specialization="luxury"
    )
    
    budget_realtor = CustomRealtorAgent.create_simple(
        user_id="budget_specialist", 
        specialization="budget"
    )
    
    print("✅ Created specialized realtor agents")
    
    # Example 2: Custom workflow patterns
    orchestrator = ConversationOrchestrator()
    
    # Custom luxury consultation flow
    luxury_questions = [
        {"text": "What's your investment budget range?", "schema": {"type": "text"}},
        {"text": "Are you looking for luxury amenities?", "schema": {"type": "choice", "options": ["Essential", "Preferred", "Not important"]}},
        {"text": "Do you need concierge services?", "schema": {"type": "choice", "options": ["Yes", "No", "Maybe"]}}
    ]
    
    luxury_flow = orchestrator.create_information_gathering_flow(
        "luxury_consultation",
        luxury_realtor,
        luxury_questions
    )
    
    print("✅ Created custom luxury consultation workflow")
    
    # Example 3: Multi-agent collaboration with custom roles
    agents = {
        "luxury_specialist": luxury_realtor,
        "budget_advisor": budget_realtor
    }
    
    consultation_flow = orchestrator.create_multi_agent_flow(
        "dual_consultation",
        agents,
        ["luxury_specialist", "budget_advisor"],
        coordination_style="sequential"
    )
    
    print("✅ Created multi-agent consultation flow")
    
    print("\n📖 Customization Techniques Demonstrated:")
    print("   1. Custom agent specializations with tailored system messages")
    print("   2. Workflow factory methods for rapid development")
    print("   3. Multi-agent collaboration patterns")
    print("   4. Flexible conversation flow construction")
    
    # Cleanup
    await luxury_realtor.cleanup_session()
    await budget_realtor.cleanup_session()
    
    return {
        "customization_patterns": ["agent_specialization", "custom_workflows", "multi_agent_flows"],
        "developer_friendly": True,
        "extensibility": "High"
    }


if __name__ == "__main__":
    print("🏠 Enhanced Multi-Agent Realtor-Renter Chat System")
    print("🎓 Educational Features: Property algorithms, Multi-agent patterns, Workflow construction")
    print("💎 Built with enhanced ambivo_agents workflow orchestration")
    print()
    
    print("📚 Available Demonstrations:")
    print("1. Enhanced Educational Demo (default)")
    print("2. Customization Patterns Demo")
    
    choice = input("\nChoose demo (1-2) or Enter for educational demo: ").strip()
    
    if choice == "2":
        asyncio.run(demonstrate_customization_patterns())
    else:
        asyncio.run(run_enhanced_realtor_renter_demo())