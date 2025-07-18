# ambivo_agents/core/workflow_orchestrator.py
"""
Production Workflow Orchestrator for Third-Party Developers

This module provides a high-level orchestration layer that makes it easy for 
third-party developers to create interactive chat systems and multi-agent workflows.

Key Features:
- Simple API for creating conversational workflows
- Built-in patterns for common use cases
- Real-time state management and persistence
- Human-in-the-loop interactions
- Automatic error recovery and rollback
- Resource management and scaling
"""

import asyncio
import json
import logging
from datetime import datetime
from typing import Any, Dict, List, Optional, Callable, Union, Tuple
from dataclasses import dataclass, field
from enum import Enum

from .interactive_workflow import (
    InteractiveWorkflowBuilder, 
    InteractiveWorkflowExecutor,
    EnhancedWorkflowState,
    UserInteraction,
    InteractionType,
    NodeExecutionState
)
from .base import BaseAgent, AgentMessage, ExecutionContext, MessageType


class ConversationPattern(Enum):
    """Pre-built conversation patterns for common use cases"""
    SIMPLE_CHAT = "simple_chat"
    INFORMATION_GATHERING = "information_gathering"
    DECISION_TREE = "decision_tree"
    APPROVAL_WORKFLOW = "approval_workflow"
    MULTI_AGENT_COLLABORATION = "multi_agent_collaboration"
    DATABASE_INTERACTION = "database_interaction"
    STEP_BY_STEP_PROCESS = "step_by_step_process"


@dataclass
class ConversationStep:
    """Individual step in a conversation workflow"""
    step_id: str
    step_type: str  # "agent_response", "user_input", "approval", "decision", "database_query"
    agent: Optional[BaseAgent] = None
    prompt: Optional[str] = None
    input_schema: Optional[Dict[str, Any]] = None
    conditions: Optional[Dict[str, Any]] = None
    next_steps: List[str] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class ConversationFlow:
    """Complete conversation flow definition"""
    flow_id: str
    name: str
    description: str
    pattern: ConversationPattern
    steps: List[ConversationStep] = field(default_factory=list)
    start_step: Optional[str] = None
    end_steps: List[str] = field(default_factory=list)
    variables: Dict[str, Any] = field(default_factory=dict)
    settings: Dict[str, Any] = field(default_factory=dict)


class ConversationOrchestrator:
    """High-level orchestrator for creating and managing conversational workflows"""
    
    def __init__(self, memory_manager=None):
        self.memory_manager = memory_manager
        self.executor = InteractiveWorkflowExecutor(memory_manager)
        self.registered_flows: Dict[str, ConversationFlow] = {}
        self.active_conversations: Dict[str, str] = {}  # session_id -> execution_id
        self.logger = logging.getLogger("ConversationOrchestrator")
        
        # Built-in conversation patterns
        self._setup_builtin_patterns()
    
    def _setup_builtin_patterns(self):
        """Setup built-in conversation patterns for common use cases"""
        
        # Pattern 1: Simple Information Gathering
        self.register_pattern(
            "customer_support_flow",
            ConversationPattern.INFORMATION_GATHERING,
            "Customer support information gathering workflow",
            [
                ConversationStep(
                    step_id="greeting",
                    step_type="agent_response",
                    prompt="Greet the customer and ask how you can help them today.",
                    next_steps=["gather_issue"]
                ),
                ConversationStep(
                    step_id="gather_issue",
                    step_type="user_input",
                    prompt="Please describe your issue in detail:",
                    input_schema={"type": "text", "required": True, "max_length": 500},
                    next_steps=["categorize_issue"]
                ),
                ConversationStep(
                    step_id="categorize_issue",
                    step_type="agent_response",
                    prompt="Analyze the customer's issue and categorize it. Ask follow-up questions if needed.",
                    next_steps=["provide_solution"]
                ),
                ConversationStep(
                    step_id="provide_solution",
                    step_type="agent_response",
                    prompt="Provide a solution or next steps based on the categorized issue.",
                    next_steps=["satisfaction_check"]
                ),
                ConversationStep(
                    step_id="satisfaction_check",
                    step_type="user_input",
                    prompt="Are you satisfied with this solution? (Yes/No)",
                    input_schema={"type": "choice", "options": ["Yes", "No"]},
                    next_steps=["end"]
                )
            ]
        )
        
        # Pattern 2: Decision Tree
        self.register_pattern(
            "product_recommendation_flow",
            ConversationPattern.DECISION_TREE,
            "Product recommendation based on user preferences",
            [
                ConversationStep(
                    step_id="welcome",
                    step_type="agent_response",
                    prompt="Welcome! I'll help you find the perfect product. Let's start with some questions.",
                    next_steps=["budget_question"]
                ),
                ConversationStep(
                    step_id="budget_question",
                    step_type="user_input",
                    prompt="What's your budget range?",
                    input_schema={"type": "choice", "options": ["Under $100", "$100-$500", "$500-$1000", "Over $1000"]},
                    next_steps=["category_question"]
                ),
                ConversationStep(
                    step_id="category_question",
                    step_type="user_input",
                    prompt="What category of product are you looking for?",
                    input_schema={"type": "choice", "options": ["Electronics", "Clothing", "Home & Garden", "Sports", "Other"]},
                    next_steps=["generate_recommendations"]
                ),
                ConversationStep(
                    step_id="generate_recommendations",
                    step_type="agent_response",
                    prompt="Based on your budget and category preferences, here are my recommendations...",
                    next_steps=["feedback"]
                ),
                ConversationStep(
                    step_id="feedback",
                    step_type="user_input",
                    prompt="Which recommendation interests you most?",
                    input_schema={"type": "text"},
                    next_steps=["end"]
                )
            ]
        )
    
    def register_pattern(
        self, 
        flow_id: str, 
        pattern: ConversationPattern, 
        description: str, 
        steps: List[ConversationStep]
    ):
        """Register a conversation pattern"""
        flow = ConversationFlow(
            flow_id=flow_id,
            name=flow_id.replace("_", " ").title(),
            description=description,
            pattern=pattern,
            steps=steps,
            start_step=steps[0].step_id if steps else None,
            end_steps=["end"]
        )
        self.registered_flows[flow_id] = flow
    
    def create_simple_chat_flow(
        self,
        flow_id: str,
        agent: BaseAgent,
        system_prompt: str = None,
        max_turns: int = 10
    ) -> ConversationFlow:
        """Create a simple back-and-forth chat flow"""
        
        steps = []
        
        # Initial agent response
        steps.append(ConversationStep(
            step_id="initial_response",
            step_type="agent_response",
            agent=agent,
            prompt=system_prompt or "Start a helpful conversation with the user.",
            next_steps=["user_turn_1"]
        ))
        
        # Create alternating turns
        for i in range(1, max_turns + 1):
            # User turn
            steps.append(ConversationStep(
                step_id=f"user_turn_{i}",
                step_type="user_input",
                prompt="Your response:",
                input_schema={"type": "text", "required": True},
                next_steps=[f"agent_turn_{i}"] if i < max_turns else ["end"]
            ))
            
            # Agent turn
            if i < max_turns:
                steps.append(ConversationStep(
                    step_id=f"agent_turn_{i}",
                    step_type="agent_response",
                    agent=agent,
                    prompt="Continue the conversation naturally based on the user's response.",
                    next_steps=[f"user_turn_{i+1}"]
                ))
        
        flow = ConversationFlow(
            flow_id=flow_id,
            name="Simple Chat Flow",
            description=f"Simple chat conversation with {agent.agent_id}",
            pattern=ConversationPattern.SIMPLE_CHAT,
            steps=steps,
            start_step="initial_response",
            end_steps=["end"]
        )
        
        self.registered_flows[flow_id] = flow
        return flow
    
    def create_information_gathering_flow(
        self,
        flow_id: str,
        agent: BaseAgent,
        questions: List[Dict[str, Any]],
        final_action: str = "provide_summary"
    ) -> ConversationFlow:
        """Create an information gathering flow with specified questions"""
        
        steps = []
        
        # Greeting
        steps.append(ConversationStep(
            step_id="greeting",
            step_type="agent_response",
            agent=agent,
            prompt="Greet the user and explain that you'll be gathering some information.",
            next_steps=["question_0"] if questions else ["end"]
        ))
        
        # Question steps
        for i, question in enumerate(questions):
            # Question step
            steps.append(ConversationStep(
                step_id=f"question_{i}",
                step_type="user_input",
                prompt=question.get("text", f"Question {i+1}"),
                input_schema=question.get("schema", {"type": "text"}),
                next_steps=[f"question_{i+1}"] if i < len(questions) - 1 else [final_action]
            ))
        
        # Final action
        steps.append(ConversationStep(
            step_id=final_action,
            step_type="agent_response",
            agent=agent,
            prompt="Thank the user and provide a summary of the information gathered.",
            next_steps=["end"]
        ))
        
        flow = ConversationFlow(
            flow_id=flow_id,
            name="Information Gathering Flow",
            description=f"Structured information gathering with {len(questions)} questions",
            pattern=ConversationPattern.INFORMATION_GATHERING,
            steps=steps,
            start_step="greeting",
            end_steps=["end"]
        )
        
        self.registered_flows[flow_id] = flow
        return flow
    
    def create_multi_agent_flow(
        self,
        flow_id: str,
        agents: Dict[str, BaseAgent],
        agent_sequence: List[str],
        coordination_style: str = "sequential"
    ) -> ConversationFlow:
        """Create a multi-agent collaboration flow"""
        
        steps = []
        
        if coordination_style == "sequential":
            # Sequential execution
            for i, agent_key in enumerate(agent_sequence):
                agent = agents[agent_key]
                step_id = f"{agent_key}_turn"
                
                steps.append(ConversationStep(
                    step_id=step_id,
                    step_type="agent_response",
                    agent=agent,
                    prompt=f"Perform your role in this multi-agent workflow. Agent: {agent_key}",
                    next_steps=[f"{agent_sequence[i+1]}_turn"] if i < len(agent_sequence) - 1 else ["end"]
                ))
        
        elif coordination_style == "debate":
            # Debate style: agents take turns responding to each other
            steps.append(ConversationStep(
                step_id="initial_topic",
                step_type="user_input",
                prompt="What topic would you like the agents to discuss?",
                input_schema={"type": "text"},
                next_steps=[f"{agent_sequence[0]}_position"]
            ))
            
            for round_num in range(3):  # 3 rounds of debate
                for i, agent_key in enumerate(agent_sequence):
                    agent = agents[agent_key]
                    step_id = f"{agent_key}_position_round_{round_num}"
                    
                    next_step = None
                    if i < len(agent_sequence) - 1:
                        next_step = f"{agent_sequence[i+1]}_position_round_{round_num}"
                    elif round_num < 2:
                        next_step = f"{agent_sequence[0]}_position_round_{round_num + 1}"
                    else:
                        next_step = "summary"
                    
                    steps.append(ConversationStep(
                        step_id=step_id,
                        step_type="agent_response",
                        agent=agent,
                        prompt=f"Present your position on the topic. Round {round_num + 1}.",
                        next_steps=[next_step] if next_step else ["end"]
                    ))
            
            # Summary step
            summary_agent = agents[agent_sequence[0]]  # Use first agent for summary
            steps.append(ConversationStep(
                step_id="summary",
                step_type="agent_response",
                agent=summary_agent,
                prompt="Provide a summary of the debate and key points from all agents.",
                next_steps=["end"]
            ))
        
        flow = ConversationFlow(
            flow_id=flow_id,
            name="Multi-Agent Flow",
            description=f"Multi-agent collaboration with {len(agents)} agents",
            pattern=ConversationPattern.MULTI_AGENT_COLLABORATION,
            steps=steps,
            start_step=steps[0].step_id if steps else None,
            end_steps=["end"]
        )
        
        self.registered_flows[flow_id] = flow
        return flow
    
    def create_database_interaction_flow(
        self,
        flow_id: str,
        chat_agent: BaseAgent,
        database_agent: BaseAgent,
        interaction_pattern: str = "search_and_present"
    ) -> ConversationFlow:
        """Create a database interaction flow"""
        
        steps = []
        
        if interaction_pattern == "search_and_present":
            steps = [
                ConversationStep(
                    step_id="initial_greeting",
                    step_type="agent_response",
                    agent=chat_agent,
                    prompt="Greet the user and ask what information they're looking for.",
                    next_steps=["user_query"]
                ),
                ConversationStep(
                    step_id="user_query",
                    step_type="user_input",
                    prompt="What would you like to search for?",
                    input_schema={"type": "text", "required": True},
                    next_steps=["database_search"]
                ),
                ConversationStep(
                    step_id="database_search",
                    step_type="agent_response",
                    agent=database_agent,
                    prompt="Search the database based on the user's query and return relevant results.",
                    next_steps=["present_results"]
                ),
                ConversationStep(
                    step_id="present_results",
                    step_type="agent_response",
                    agent=chat_agent,
                    prompt="Present the database search results to the user in a friendly way.",
                    next_steps=["follow_up"]
                ),
                ConversationStep(
                    step_id="follow_up",
                    step_type="user_input",
                    prompt="Would you like to search for anything else? (Yes/No)",
                    input_schema={"type": "choice", "options": ["Yes", "No"]},
                    next_steps=["end"]
                )
            ]
        
        flow = ConversationFlow(
            flow_id=flow_id,
            name="Database Interaction Flow",
            description="Interactive database search and presentation",
            pattern=ConversationPattern.DATABASE_INTERACTION,
            steps=steps,
            start_step="initial_greeting",
            end_steps=["end"]
        )
        
        self.registered_flows[flow_id] = flow
        return flow
    
    async def start_conversation(
        self,
        flow_id: str,
        session_id: str,
        initial_message: str = None,
        context: ExecutionContext = None,
        interaction_handler: Callable = None
    ) -> Tuple[str, Dict[str, Any]]:
        """Start a conversation using a registered flow"""
        
        if flow_id not in self.registered_flows:
            raise ValueError(f"Flow '{flow_id}' not found")
        
        flow = self.registered_flows[flow_id]
        
        # Convert flow to workflow
        workflow = await self._convert_flow_to_workflow(flow)
        
        # Create interaction handler if not provided
        if not interaction_handler:
            interaction_handler = self._create_default_interaction_handler()
        
        # Execute workflow
        result = await self.executor.execute_interactive_workflow(
            workflow,
            initial_message or "Start conversation",
            context,
            interaction_handler
        )
        
        # Track active conversation
        execution_id = result.metadata.get('execution_id')
        if execution_id:
            self.active_conversations[session_id] = execution_id
        
        return execution_id, {
            'success': result.success,
            'flow_id': flow_id,
            'session_id': session_id,
            'execution_time': result.execution_time,
            'messages': len(result.messages),
            'metadata': result.metadata
        }
    
    async def continue_conversation(
        self,
        session_id: str,
        user_input: str
    ) -> Dict[str, Any]:
        """Continue an existing conversation"""
        
        if session_id not in self.active_conversations:
            return {'error': 'No active conversation found for this session'}
        
        execution_id = self.active_conversations[session_id]
        
        # Handle user input for the workflow
        # This would integrate with the interaction system
        # For now, return a placeholder response
        
        return {
            'success': True,
            'session_id': session_id,
            'execution_id': execution_id,
            'response': 'Conversation continued (placeholder)'
        }
    
    async def pause_conversation(self, session_id: str) -> bool:
        """Pause an active conversation"""
        if session_id in self.active_conversations:
            execution_id = self.active_conversations[session_id]
            return await self.executor.pause_workflow(execution_id)
        return False
    
    async def resume_conversation(self, session_id: str) -> bool:
        """Resume a paused conversation"""
        if session_id in self.active_conversations:
            execution_id = self.active_conversations[session_id]
            return await self.executor.resume_workflow(execution_id)
        return False
    
    async def get_conversation_status(self, session_id: str) -> Optional[Dict[str, Any]]:
        """Get status of a conversation"""
        if session_id not in self.active_conversations:
            return None
        
        execution_id = self.active_conversations[session_id]
        
        if execution_id in self.executor.active_workflows:
            state = self.executor.active_workflows[execution_id]
            return {
                'session_id': session_id,
                'execution_id': execution_id,
                'status': state.status,
                'current_step': state.current_node,
                'progress': len(state.execution_order) / len(state.node_states) if state.node_states else 0,
                'pending_interactions': len(state.pending_interactions),
                'last_updated': state.last_updated.isoformat()
            }
        
        return None
    
    def list_available_flows(self) -> Dict[str, Dict[str, Any]]:
        """List all available conversation flows"""
        return {
            flow_id: {
                'name': flow.name,
                'description': flow.description,
                'pattern': flow.pattern.value,
                'steps': len(flow.steps),
                'estimated_duration': self._estimate_flow_duration(flow)
            }
            for flow_id, flow in self.registered_flows.items()
        }
    
    def _estimate_flow_duration(self, flow: ConversationFlow) -> str:
        """Estimate conversation duration based on flow complexity"""
        step_count = len(flow.steps)
        if step_count <= 3:
            return "2-5 minutes"
        elif step_count <= 6:
            return "5-10 minutes"
        elif step_count <= 10:
            return "10-15 minutes"
        else:
            return "15+ minutes"
    
    async def _convert_flow_to_workflow(self, flow: ConversationFlow):
        """Convert a ConversationFlow to an executable workflow"""
        builder = InteractiveWorkflowBuilder()
        
        # Add steps as workflow nodes
        for step in flow.steps:
            if step.step_type == "agent_response" and step.agent:
                builder.add_agent(step.agent, step.step_id)
            elif step.step_type == "user_input":
                builder.add_user_input_node(
                    step.step_id,
                    step.prompt or "Please provide input:",
                    input_type=step.input_schema.get("type", "text") if step.input_schema else "text",
                    options=step.input_schema.get("options", []) if step.input_schema else [],
                    timeout_seconds=step.metadata.get("timeout", 300)
                )
            elif step.step_type == "approval":
                builder.add_approval_node(
                    step.step_id,
                    step.prompt or "Please approve to continue:",
                    timeout_seconds=step.metadata.get("timeout", 60)
                )
        
        # Add edges based on next_steps
        for step in flow.steps:
            for next_step in step.next_steps:
                if next_step != "end":
                    builder.add_edge(step.step_id, next_step)
        
        # Set start and end nodes
        if flow.start_step:
            builder.set_start_node(flow.start_step)
        
        for end_step in flow.end_steps:
            if end_step in [step.step_id for step in flow.steps]:
                builder.set_end_node(end_step)
        
        return builder.build()
    
    def _create_default_interaction_handler(self) -> Callable:
        """Create a default interaction handler for testing"""
        async def handler(interaction: UserInteraction) -> Optional[str]:
            print(f"\n🔔 Interaction Required: {interaction.prompt}")
            if interaction.options:
                print(f"Options: {', '.join(interaction.options)}")
            
            # Return default responses for different interaction types
            if interaction.interaction_type == InteractionType.INPUT_REQUEST:
                if interaction.options:
                    return interaction.options[0]  # Select first option
                return "Default response"
            elif interaction.interaction_type == InteractionType.APPROVAL_REQUEST:
                return "approve"
            elif interaction.interaction_type == InteractionType.CHOICE_SELECTION:
                return interaction.options[0] if interaction.options else "default"
            
            return "Default response"
        
        return handler


# Production-ready factory for common patterns
class WorkflowFactory:
    """Factory for creating common workflow patterns"""
    
    @staticmethod
    def create_realtor_renter_workflow(
        realtor_agent: BaseAgent,
        database_agent: BaseAgent,
        search_agent: Optional[BaseAgent] = None
    ) -> ConversationFlow:
        """Create a complete realtor-renter interaction workflow"""
        
        orchestrator = ConversationOrchestrator()
        
        # Define the realtor-renter conversation steps
        steps = [
            ConversationStep(
                step_id="realtor_greeting",
                step_type="agent_response",
                agent=realtor_agent,
                prompt="Greet the potential renter and start gathering their housing requirements.",
                next_steps=["collect_budget"]
            ),
            ConversationStep(
                step_id="collect_budget",
                step_type="user_input",
                prompt="What is your monthly budget for rent?",
                input_schema={"type": "text", "validation": "numeric"},
                next_steps=["collect_bedrooms"]
            ),
            ConversationStep(
                step_id="collect_bedrooms",
                step_type="user_input",
                prompt="How many bedrooms do you need?",
                input_schema={"type": "choice", "options": ["Studio", "1", "2", "3", "4+"]},
                next_steps=["collect_location"]
            ),
            ConversationStep(
                step_id="collect_location",
                step_type="user_input",
                prompt="Which area or neighborhood do you prefer?",
                input_schema={"type": "text"},
                next_steps=["collect_amenities"]
            ),
            ConversationStep(
                step_id="collect_amenities",
                step_type="user_input",
                prompt="What amenities are important to you? (parking, gym, pool, etc.)",
                input_schema={"type": "text"},
                next_steps=["database_search"]
            ),
            ConversationStep(
                step_id="database_search",
                step_type="agent_response",
                agent=database_agent,
                prompt="Search for properties matching the renter's criteria and return available options.",
                next_steps=["present_options"]
            ),
            ConversationStep(
                step_id="present_options",
                step_type="agent_response",
                agent=realtor_agent,
                prompt="Present the search results to the renter in an engaging way, highlighting matches.",
                next_steps=["get_feedback"]
            ),
            ConversationStep(
                step_id="get_feedback",
                step_type="user_input",
                prompt="Which properties interest you most? Any questions about the options?",
                input_schema={"type": "text"},
                next_steps=["schedule_viewing"]
            ),
            ConversationStep(
                step_id="schedule_viewing",
                step_type="agent_response",
                agent=realtor_agent,
                prompt="Respond to their feedback and offer to schedule viewings or provide more information.",
                next_steps=["end"]
            )
        ]
        
        flow = ConversationFlow(
            flow_id="realtor_renter_workflow",
            name="Realtor-Renter Property Search",
            description="Complete workflow for helping renters find suitable properties",
            pattern=ConversationPattern.STEP_BY_STEP_PROCESS,
            steps=steps,
            start_step="realtor_greeting",
            end_steps=["schedule_viewing"]
        )
        
        return flow
    
    @staticmethod
    def create_customer_service_workflow(
        primary_agent: BaseAgent,
        escalation_agent: Optional[BaseAgent] = None
    ) -> ConversationFlow:
        """Create a customer service workflow with escalation"""
        
        steps = [
            ConversationStep(
                step_id="welcome",
                step_type="agent_response",
                agent=primary_agent,
                prompt="Welcome the customer and ask how you can help them today.",
                next_steps=["describe_issue"]
            ),
            ConversationStep(
                step_id="describe_issue",
                step_type="user_input",
                prompt="Please describe your issue or question:",
                input_schema={"type": "text", "required": True, "max_length": 1000},
                next_steps=["initial_response"]
            ),
            ConversationStep(
                step_id="initial_response",
                step_type="agent_response",
                agent=primary_agent,
                prompt="Analyze the customer's issue and provide initial assistance or ask clarifying questions.",
                next_steps=["satisfaction_check"]
            ),
            ConversationStep(
                step_id="satisfaction_check",
                step_type="user_input",
                prompt="Does this help resolve your issue? (Yes/No/Need more help)",
                input_schema={"type": "choice", "options": ["Yes", "No", "Need more help"]},
                next_steps=["resolution_path"]
            ),
            ConversationStep(
                step_id="resolution_path",
                step_type="agent_response",
                agent=escalation_agent or primary_agent,
                prompt="Based on the customer's response, either close the issue or escalate for additional support.",
                next_steps=["end"]
            )
        ]
        
        return ConversationFlow(
            flow_id="customer_service_workflow",
            name="Customer Service Flow",
            description="Customer service workflow with escalation support",
            pattern=ConversationPattern.STEP_BY_STEP_PROCESS,
            steps=steps,
            start_step="welcome",
            end_steps=["resolution_path"]
        )


# Example usage and quick start guide
async def quick_start_example():
    """Example showing how third-party developers can quickly create workflows"""
    
    from ambivo_agents import AssistantAgent, DatabaseAgent
    
    # 1. Create your agents
    realtor = AssistantAgent.create_simple(user_id="realtor")
    renter = AssistantAgent.create_simple(user_id="renter")
    database = DatabaseAgent.create_simple(user_id="property_db")
    
    # 2. Create orchestrator
    orchestrator = ConversationOrchestrator()
    
    # 3. Option A: Use pre-built patterns
    simple_flow = orchestrator.create_simple_chat_flow(
        "simple_chat",
        realtor,
        "You are a helpful real estate agent",
        max_turns=5
    )
    
    # 4. Option B: Use factory patterns
    realtor_flow = WorkflowFactory.create_realtor_renter_workflow(
        realtor, database
    )
    orchestrator.registered_flows["realtor_renter"] = realtor_flow
    
    # 5. Option C: Create custom information gathering
    questions = [
        {"text": "What's your name?", "schema": {"type": "text", "required": True}},
        {"text": "What's your budget?", "schema": {"type": "text", "validation": "numeric"}},
        {"text": "Preferred location?", "schema": {"type": "text"}}
    ]
    
    info_flow = orchestrator.create_information_gathering_flow(
        "gather_info",
        realtor,
        questions
    )
    
    # 6. Start conversations
    print("Available flows:", orchestrator.list_available_flows())
    
    # Start a conversation
    execution_id, result = await orchestrator.start_conversation(
        "simple_chat",
        "user_session_123",
        "Hi, I'm looking for a rental property"
    )
    
    print(f"Conversation started: {execution_id}")
    print(f"Result: {result}")
    
    return orchestrator


if __name__ == "__main__":
    # Quick demo
    import asyncio
    
    async def demo():
        print("🚀 Workflow Orchestrator Demo")
        orchestrator = await quick_start_example()
        print("✅ Demo completed!")
    
    asyncio.run(demo())