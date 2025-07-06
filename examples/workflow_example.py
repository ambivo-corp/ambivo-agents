# examples/workflow_examples.py
"""
Examples of how to create and use workflows with ambivo_agents
Demonstrates patterns similar to AutoGen's GraphFlow
"""

import asyncio
import uuid
from dataclasses import dataclass, field
from typing import List, Optional, Dict, Any

from ambivo_agents import BaseAgent, ExecutionContext, AgentMessage, MessageType
from ambivo_agents.core.workflow import WorkflowBuilder, WorkflowPatterns, WorkflowModerator, WorkflowResult
from ambivo_agents.agents import (
    WebSearchAgent, WebScraperAgent, KnowledgeBaseAgent,
    YouTubeDownloadAgent, MediaEditorAgent, AssistantAgent,
    CodeExecutorAgent
)


async def example_1_search_scrape_ingest():
    """
    Example 1: Search -> Scrape -> Ingest Workflow
    Similar to the AutoGen example you shared
    """
    print("🔄 Example 1: Search -> Scrape -> Ingest Workflow")

    # Create agents with auto-context
    search_agent = WebSearchAgent.create_simple(user_id="workflow_user")
    scraper_agent = WebScraperAgent.create_simple(user_id="workflow_user")
    kb_agent = KnowledgeBaseAgent.create_simple(user_id="workflow_user")

    # Create workflow using pattern
    workflow = WorkflowPatterns.create_search_scrape_ingest_workflow(
        search_agent, scraper_agent, kb_agent
    )

    # Execute workflow
    result = await workflow.execute(
        initial_message="Search for information about quantum computing, scrape the top results, and ingest into a knowledge base called 'quantum_research'",
        execution_context=search_agent.get_execution_context()
    )

    # Display results
    print(f"✅ Workflow completed: {result.success}")
    print(f"⏱️ Execution time: {result.execution_time:.2f}s")
    print(f"🔧 Nodes executed: {', '.join(result.nodes_executed)}")
    print(f"💬 Messages: {len(result.messages)}")

    if result.success and result.messages:
        print(f"\n📄 Final result:\n{result.messages[-1].content[:200]}...")

    if result.errors:
        print(f"\n❌ Errors: {result.errors}")


async def example_2_parallel_research():
    """
    Example 2: Parallel Research and Analysis
    Search feeds both storage and analysis simultaneously
    """
    print("\n🔄 Example 2: Parallel Research and Analysis")

    # Create agents
    search_agent = WebSearchAgent.create_simple(user_id="workflow_user")
    kb_agent = KnowledgeBaseAgent.create_simple(user_id="workflow_user")
    assistant_agent = AssistantAgent.create_simple(user_id="workflow_user")

    # Create workflow
    workflow = WorkflowPatterns.create_research_analysis_workflow(
        search_agent, kb_agent, assistant_agent
    )

    # Execute with parallel processing
    result = await workflow.execute_parallel(
        initial_message="Research machine learning trends and provide analysis",
        execution_context=search_agent.get_execution_context()
    )

    print(f"✅ Parallel workflow completed: {result.success}")
    print(f"⏱️ Execution time: {result.execution_time:.2f}s")
    print(f"🔧 Nodes executed: {', '.join(result.nodes_executed)}")


async def example_3_custom_workflow():
    """
    Example 3: Custom Multi-Step Workflow
    Code generation -> Execution -> Documentation
    """
    print("\n🔄 Example 3: Custom Multi-Step Workflow")

    # Create agents
    assistant_agent = AssistantAgent.create_simple(user_id="workflow_user")
    code_agent = CodeExecutorAgent.create_simple(user_id="workflow_user")
    doc_agent = AssistantAgent.create_simple(user_id="workflow_user")

    # Build custom workflow
    builder = WorkflowBuilder()
    builder.add_agent(assistant_agent, "generate")
    builder.add_agent(code_agent, "execute")
    builder.add_agent(doc_agent, "document")

    # Define edges
    builder.add_edge("generate", "execute")
    builder.add_edge("execute", "document")

    # Set endpoints
    builder.set_start_node("generate")
    builder.set_end_node("document")

    # Build workflow
    workflow = builder.build()

    # Execute
    result = await workflow.execute(
        initial_message="Generate Python code to calculate fibonacci numbers, execute it, then create documentation",
        execution_context=assistant_agent.get_execution_context()
    )

    print(f"✅ Custom workflow completed: {result.success}")
    print(f"⏱️ Execution time: {result.execution_time:.2f}s")
    print(f"🔧 Nodes executed: {', '.join(result.nodes_executed)}")


async def example_4_media_workflow():
    """
    Example 4: Media Processing Workflow
    YouTube Download -> Media Processing
    """
    print("\n🔄 Example 4: Media Processing Workflow")

    # Create media agents
    youtube_agent = YouTubeDownloadAgent.create_simple(user_id="workflow_user")
    media_agent = MediaEditorAgent.create_simple(user_id="workflow_user")

    # Create workflow
    workflow = WorkflowPatterns.create_media_processing_workflow(
        youtube_agent, media_agent
    )

    # Execute
    result = await workflow.execute(
        initial_message="Download audio from https://youtube.com/watch?v=example and convert to high quality MP3",
        execution_context=youtube_agent.get_execution_context()
    )

    print(f"✅ Media workflow completed: {result.success}")
    print(f"⏱️ Execution time: {result.execution_time:.2f}s")
    print(f"🔧 Nodes executed: {', '.join(result.nodes_executed)}")


async def example_5_workflow_moderator():
    """
    Example 5: Using WorkflowModerator for intelligent workflow detection
    """
    print("\n🔄 Example 5: Workflow Moderator with Auto-Detection")

    # Create moderator
    moderator = WorkflowModerator.create_simple(user_id="workflow_user")

    # Create and register workflows
    search_agent = WebSearchAgent.create_simple(user_id="workflow_user")
    scraper_agent = WebScraperAgent.create_simple(user_id="workflow_user")
    kb_agent = KnowledgeBaseAgent.create_simple(user_id="workflow_user")

    # Register workflows
    workflow1 = WorkflowPatterns.create_search_scrape_ingest_workflow(
        search_agent, scraper_agent, kb_agent
    )
    moderator.register_workflow("search_scrape_ingest", workflow1)

    # Test workflow detection
    response = await moderator.chat("I need to search scrape ingest information about AI safety")
    print(f"📝 Moderator response: {response[:200]}...")


async def example_6_streaming_workflow():
    """
    Example 6: Streaming Workflow Execution
    Shows real-time progress of workflow execution
    """
    print("\n🔄 Example 6: Streaming Workflow with Progress")

    # Create agents
    search_agent = WebSearchAgent.create_simple(user_id="workflow_user")
    assistant_agent = AssistantAgent.create_simple(user_id="workflow_user")

    # Build workflow
    builder = WorkflowBuilder()
    builder.add_agent(search_agent, "search")
    builder.add_agent(assistant_agent, "analyze")
    builder.add_edge("search", "analyze")
    workflow = builder.build()

    # Simulate streaming execution with progress updates
    print("🚀 Starting workflow execution...")

    start_time = asyncio.get_event_loop().time()

    # Execute with progress tracking
    result = await workflow.execute(
        initial_message="Search for latest developments in renewable energy and analyze the findings",
        execution_context=search_agent.get_execution_context()
    )

    end_time = asyncio.get_event_loop().time()

    print(f"⏱️ Total execution time: {end_time - start_time:.2f}s")
    print(f"📊 Workflow result: {'Success' if result.success else 'Failed'}")

    # Show message flow
    print("\n📨 Message Flow:")
    for i, message in enumerate(result.messages):
        sender = message.sender_id
        preview = message.content[:50] + "..." if len(message.content) > 50 else message.content
        print(f"  {i + 1}. {sender}: {preview}")


async def example_7_conditional_workflow():
    """
    Example 7: Conditional Workflow with Branching Logic
    """
    print("\n🔄 Example 7: Conditional Workflow")

    # Create agents
    search_agent = WebSearchAgent.create_simple(user_id="workflow_user")
    code_agent = CodeExecutorAgent.create_simple(user_id="workflow_user")
    assistant_agent = AssistantAgent.create_simple(user_id="workflow_user")

    # Define condition function
    def contains_code(message):
        """Check if message contains code-related content"""
        content = message.content.lower()
        return any(keyword in content for keyword in ['code', 'programming', 'python', 'function'])

    # Build conditional workflow
    builder = WorkflowBuilder()
    builder.add_agent(search_agent, "search")
    builder.add_agent(code_agent, "code")
    builder.add_agent(assistant_agent, "text")

    # Conditional edges
    builder.add_edge("search", "code", condition=contains_code)
    builder.add_edge("search", "text", condition=lambda msg: not contains_code(msg))

    workflow = builder.build()

    # Test with code-related query
    result = await workflow.execute(
        initial_message="Search for Python sorting algorithms and show examples",
        execution_context=search_agent.get_execution_context()
    )

    print(f"✅ Conditional workflow completed: {result.success}")
    print(f"🔀 Execution path: {' -> '.join(result.nodes_executed)}")


# Two-Agent Conversation Examples

async def example_8_two_agent_conversation():
    """
    Example 8: Two-Agent Conversation System
    Implements back-and-forth conversation between agents
    """
    print("\n🔄 Example 8: Two-Agent Conversation")

    # Create two agents with different roles
    researcher = AssistantAgent.create_simple(user_id="workflow_user")
    reviewer = AssistantAgent.create_simple(user_id="workflow_user")

    # Override system messages for specific roles
    researcher.system_message = "You are a research specialist. Research topics thoroughly and present findings clearly."
    reviewer.system_message = "You are a critical reviewer. Analyze research and ask probing questions or suggest improvements."

    # Create conversation workflow
    conversation = TwoAgentConversation(researcher, reviewer, max_rounds=3)

    # Start conversation
    result = await conversation.run(
        initial_message="Research the current state of artificial general intelligence (AGI) development",
        execution_context=researcher.get_execution_context()
    )

    print(f"💬 Conversation completed after {len(result.messages)} messages")
    print(f"⏱️ Total time: {result.execution_time:.2f}s")

    # Show conversation flow
    print("\n📝 Conversation Flow:")
    for i, message in enumerate(result.messages):
        role = "👨‍🔬 Researcher" if "researcher" in message.sender_id else "👩‍💼 Reviewer"
        preview = message.content[:100] + "..." if len(message.content) > 100 else message.content
        print(f"  {i + 1}. {role}: {preview}")


async def example_9_agent_collaboration():
    """
    Example 9: Multi-Agent Collaboration
    Multiple agents working together on a complex task
    """
    print("\n🔄 Example 9: Multi-Agent Collaboration")

    # Create specialized agents
    search_agent = WebSearchAgent.create_simple(user_id="collaboration")
    code_agent = CodeExecutorAgent.create_simple(user_id="collaboration")
    kb_agent = KnowledgeBaseAgent.create_simple(user_id="collaboration")
    assistant_agent = AssistantAgent.create_simple(user_id="collaboration")

    # Create collaboration workflow
    collaboration = AgentCollaboration([search_agent, code_agent, kb_agent, assistant_agent])

    # Execute collaborative task
    result = await collaboration.execute_task(
        "Create a comprehensive analysis of machine learning algorithms, including code examples and store findings in a knowledge base"
    )

    print(f"🤝 Collaboration completed: {result.success}")
    print(f"👥 Agents participated: {len(result.participating_agents)}")
    print(f"📊 Total interactions: {len(result.interactions)}")


class TwoAgentConversation:
    """Implements conversation between two agents with turn-taking"""

    def __init__(self, agent1: BaseAgent, agent2: BaseAgent, max_rounds: int = 5):
        self.agent1 = agent1
        self.agent2 = agent2
        self.max_rounds = max_rounds
        self.conversation_history = []

    async def run(self, initial_message: str, execution_context: ExecutionContext = None) -> WorkflowResult:
        """Run the two-agent conversation"""
        start_time = asyncio.get_event_loop().time()
        messages = []

        # Create initial message
        current_message = AgentMessage(
            id=str(uuid.uuid4()),
            sender_id="conversation_starter",
            recipient_id=self.agent1.agent_id,
            content=initial_message,
            message_type=MessageType.USER_INPUT,
            session_id=execution_context.session_id if execution_context else "conv_session",
            conversation_id=execution_context.conversation_id if execution_context else "conv_id"
        )
        messages.append(current_message)

        # Alternate between agents
        current_agent = self.agent1
        other_agent = self.agent2

        for round_num in range(self.max_rounds):
            try:
                # Agent processes message
                response = await current_agent.process_message(current_message, execution_context)
                messages.append(response)

                # Check if conversation should end
                if self._should_end_conversation(response):
                    break

                # Switch agents and continue
                current_agent, other_agent = other_agent, current_agent
                current_message = response

            except Exception as e:
                print(f"Error in conversation round {round_num}: {e}")
                break

        execution_time = asyncio.get_event_loop().time() - start_time

        return WorkflowResult(
            success=True,
            messages=messages,
            execution_time=execution_time,
            nodes_executed=[self.agent1.agent_id, self.agent2.agent_id],
            metadata={"rounds": round_num + 1, "conversation_type": "two_agent"}
        )

    def _should_end_conversation(self, message: AgentMessage) -> bool:
        """Determine if conversation should end"""
        content = message.content.lower()
        end_phrases = ["conversation complete", "thank you", "that concludes", "final thoughts"]
        return any(phrase in content for phrase in end_phrases)


class AgentCollaboration:
    """Multi-agent collaboration system"""

    def __init__(self, agents: List[BaseAgent]):
        self.agents = {agent.agent_id: agent for agent in agents}
        self.coordinator = self._create_coordinator()

    def _create_coordinator(self) -> BaseAgent:
        """Create a coordinator agent to manage collaboration"""
        coordinator = AssistantAgent.create_simple(user_id="coordinator")
        coordinator.system_message = """You are a collaboration coordinator. Your job is to:
        1. Break down complex tasks into subtasks
        2. Assign subtasks to appropriate agents
        3. Coordinate the flow of information between agents
        4. Synthesize results into a coherent final output

        Available agents and their specialties:
        - WebSearchAgent: Web search and information gathering
        - CodeExecutorAgent: Code writing and execution
        - KnowledgeBaseAgent: Document storage and retrieval
        - AssistantAgent: General assistance and analysis"""

        return coordinator

    async def execute_task(self, task_description: str) -> 'CollaborationResult':
        """Execute a task using multiple agents in collaboration"""
        start_time = asyncio.get_event_loop().time()

        # Coordinator plans the task
        plan_message = await self.coordinator.chat(
            f"Break down this task for our agent team: {task_description}"
        )

        interactions = []
        participating_agents = set()

        # Parse plan and execute subtasks (simplified)
        subtasks = self._extract_subtasks(plan_message)

        for subtask in subtasks:
            agent = self._select_agent_for_task(subtask)
            if agent:
                try:
                    result = await agent.chat(subtask)
                    interactions.append({
                        'agent': agent.agent_id,
                        'task': subtask,
                        'result': result,
                        'timestamp': asyncio.get_event_loop().time()
                    })
                    participating_agents.add(agent.agent_id)
                except Exception as e:
                    interactions.append({
                        'agent': agent.agent_id,
                        'task': subtask,
                        'error': str(e),
                        'timestamp': asyncio.get_event_loop().time()
                    })

        # Coordinator synthesizes results
        synthesis_prompt = "Synthesize the following agent results into a comprehensive response:\n\n"
        for interaction in interactions:
            if 'result' in interaction:
                synthesis_prompt += f"{interaction['agent']}: {interaction['result'][:200]}...\n\n"

        final_result = await self.coordinator.chat(synthesis_prompt)

        execution_time = asyncio.get_event_loop().time() - start_time

        return CollaborationResult(
            success=True,
            final_result=final_result,
            interactions=interactions,
            participating_agents=list(participating_agents),
            execution_time=execution_time
        )

    def _extract_subtasks(self, plan_text: str) -> List[str]:
        """Extract subtasks from coordinator's plan"""
        # Simple implementation - could be enhanced with NLP
        lines = plan_text.split('\n')
        subtasks = []
        for line in lines:
            line = line.strip()
            if (line.startswith('-') or line.startswith('*') or
                    line.startswith('1.') or line.startswith('2.') or
                    'search' in line.lower() or 'code' in line.lower() or
                    'analyze' in line.lower()):
                subtasks.append(line.lstrip('-*123456789. '))
        return subtasks[:5]  # Limit to 5 subtasks

    def _select_agent_for_task(self, task: str) -> Optional[BaseAgent]:
        """Select most appropriate agent for a task"""
        task_lower = task.lower()

        if any(word in task_lower for word in ['search', 'find', 'web', 'google']):
            return self.agents.get('web_search_agent') or self._get_agent_by_type('WebSearchAgent')
        elif any(word in task_lower for word in ['code', 'program', 'script', 'execute']):
            return self.agents.get('code_executor_agent') or self._get_agent_by_type('CodeExecutorAgent')
        elif any(word in task_lower for word in ['store', 'knowledge', 'document', 'ingest']):
            return self.agents.get('knowledge_base_agent') or self._get_agent_by_type('KnowledgeBaseAgent')
        else:
            return self.agents.get('assistant_agent') or self._get_agent_by_type('AssistantAgent')

    def _get_agent_by_type(self, agent_type: str) -> Optional[BaseAgent]:
        """Get agent by class type"""
        for agent in self.agents.values():
            if agent.__class__.__name__ == agent_type:
                return agent
        return None


@dataclass
class CollaborationResult:
    """Result of multi-agent collaboration"""
    success: bool
    final_result: str
    interactions: List[Dict[str, Any]]
    participating_agents: List[str]
    execution_time: float
    errors: List[str] = field(default_factory=list)


# Advanced Workflow Patterns

async def example_10_feedback_loop():
    """
    Example 10: Feedback Loop Workflow
    Implements iterative improvement through agent feedback
    """
    print("\n🔄 Example 10: Feedback Loop Workflow")

    # Create agents for feedback loop
    writer = AssistantAgent.create_simple(user_id="feedback_user")
    reviewer = AssistantAgent.create_simple(user_id="feedback_user")

    writer.system_message = "You are a technical writer. Write clear, concise content."
    reviewer.system_message = "You are an editor. Provide constructive feedback and suggest improvements."

    # Create feedback loop
    feedback_loop = FeedbackLoopWorkflow(writer, reviewer, max_iterations=3)

    result = await feedback_loop.run(
        "Write a brief explanation of quantum computing for beginners"
    )

    print(f"🔄 Feedback loop completed after {result.iterations} iterations")
    print(f"📈 Improvement score: {result.final_score}")


class FeedbackLoopWorkflow:
    """Implements iterative improvement through feedback"""

    def __init__(self, creator: BaseAgent, reviewer: BaseAgent, max_iterations: int = 3):
        self.creator = creator
        self.reviewer = reviewer
        self.max_iterations = max_iterations

    async def run(self, initial_prompt: str) -> 'FeedbackResult':
        """Run the feedback loop"""
        current_content = initial_prompt
        iteration = 0
        improvements = []

        for iteration in range(self.max_iterations):
            # Creator produces content
            creation_response = await self.creator.chat(
                f"{'Create initial content for' if iteration == 0 else 'Improve this content based on feedback'}: {current_content}"
            )

            # Reviewer provides feedback
            review_response = await self.reviewer.chat(
                f"Review and score this content (1-10) and provide specific improvement suggestions: {creation_response}"
            )

            # Extract score (simplified)
            score = self._extract_score(review_response)
            improvements.append({
                'iteration': iteration + 1,
                'content': creation_response,
                'feedback': review_response,
                'score': score
            })

            # Check if content is good enough
            if score >= 8:
                break

            current_content = f"Content: {creation_response}\nFeedback: {review_response}"

        return FeedbackResult(
            iterations=iteration + 1,
            improvements=improvements,
            final_content=improvements[-1]['content'],
            final_score=improvements[-1]['score']
        )

    def _extract_score(self, review_text: str) -> float:
        """Extract numerical score from review"""
        import re
        # Look for patterns like "8/10", "score: 7", "rating of 6"
        patterns = [r'(\d+)/10', r'score:?\s*(\d+)', r'rating:?\s*of\s*(\d+)', r'(\d+)\s*out\s*of\s*10']
        for pattern in patterns:
            match = re.search(pattern, review_text, re.IGNORECASE)
            if match:
                return float(match.group(1))
        return 5.0  # Default score


@dataclass
class FeedbackResult:
    """Result of feedback loop workflow"""
    iterations: int
    improvements: List[Dict[str, Any]]
    final_content: str
    final_score: float


# Main execution function
async def main():
    """Run all workflow examples"""
    print("🚀 Ambivo Agents Workflow Examples\n")
    print("=" * 50)

    try:
        await example_1_search_scrape_ingest()
        await example_2_parallel_research()
        await example_3_custom_workflow()
        await example_4_media_workflow()
        await example_5_workflow_moderator()
        await example_6_streaming_workflow()
        await example_7_conditional_workflow()
        await example_8_two_agent_conversation()
        await example_9_agent_collaboration()
        await example_10_feedback_loop()

        print("\n🎉 All workflow examples completed successfully!")

    except Exception as e:
        print(f"\n❌ Error running examples: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    # Run the examples
    asyncio.run(main())