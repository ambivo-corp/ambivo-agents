# ambivo_agents/core/workflow.py
"""
Workflow orchestration system for ambivo_agents
Implements GraphFlow-like capabilities for agent-to-agent workflows
"""

import asyncio
import logging
import time
import uuid
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, AsyncIterator, Callable, Dict, List, Optional, Union

from .base import AgentMessage, BaseAgent, ExecutionContext, MessageType


class WorkflowExecutionType(Enum):
    """Types of workflow execution patterns"""

    SEQUENTIAL = "sequential"
    PARALLEL = "parallel"
    CONDITIONAL = "conditional"
    LOOP = "loop"


class WorkflowNodeType(Enum):
    """Types of nodes in a workflow"""

    AGENT = "agent"
    CONDITION = "condition"
    JOIN = "join"
    FORK = "fork"


@dataclass
class WorkflowEdge:
    """Represents an edge between workflow nodes"""

    from_node: str
    to_node: str
    condition: Optional[Callable[[AgentMessage], bool]] = None
    weight: int = 1
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class WorkflowNode:
    """Represents a node in the workflow"""

    id: str
    agent: Optional[BaseAgent] = None
    node_type: WorkflowNodeType = WorkflowNodeType.AGENT
    condition_func: Optional[Callable[[AgentMessage], bool]] = None
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class WorkflowResult:
    """Result of workflow execution"""

    success: bool
    messages: List[AgentMessage]
    execution_time: float
    nodes_executed: List[str]
    errors: List[str] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)


class WorkflowBuilder:
    """Fluent builder for creating agent workflows"""

    def __init__(self):
        self.nodes: Dict[str, WorkflowNode] = {}
        self.edges: List[WorkflowEdge] = []
        self.start_nodes: List[str] = []
        self.end_nodes: List[str] = []

    def add_agent(self, agent: BaseAgent, node_id: str = None) -> "WorkflowBuilder":
        """Add an agent to the workflow"""
        if node_id is None:
            node_id = agent.agent_id

        self.nodes[node_id] = WorkflowNode(
            id=node_id, agent=agent, node_type=WorkflowNodeType.AGENT
        )
        return self

    def add_condition(
        self, node_id: str, condition_func: Callable[[AgentMessage], bool]
    ) -> "WorkflowBuilder":
        """Add a conditional node"""
        self.nodes[node_id] = WorkflowNode(
            id=node_id, node_type=WorkflowNodeType.CONDITION, condition_func=condition_func
        )
        return self

    def add_edge(
        self,
        from_node: str,
        to_node: str,
        condition: Optional[Callable[[AgentMessage], bool]] = None,
    ) -> "WorkflowBuilder":
        """Add an edge between nodes"""
        self.edges.append(WorkflowEdge(from_node=from_node, to_node=to_node, condition=condition))
        return self

    def set_start_node(self, node_id: str) -> "WorkflowBuilder":
        """Set a start node for the workflow"""
        if node_id not in self.start_nodes:
            self.start_nodes.append(node_id)
        return self

    def set_end_node(self, node_id: str) -> "WorkflowBuilder":
        """Set an end node for the workflow"""
        if node_id not in self.end_nodes:
            self.end_nodes.append(node_id)
        return self

    def build(self) -> "AmbivoWorkflow":
        """Build the workflow"""
        # Auto-detect start and end nodes if not explicitly set
        if not self.start_nodes:
            self.start_nodes = self._find_start_nodes()
        if not self.end_nodes:
            self.end_nodes = self._find_end_nodes()

        return AmbivoWorkflow(
            nodes=self.nodes.copy(),
            edges=self.edges.copy(),
            start_nodes=self.start_nodes.copy(),
            end_nodes=self.end_nodes.copy(),
        )

    def _find_start_nodes(self) -> List[str]:
        """Find nodes with no incoming edges"""
        incoming = set(edge.to_node for edge in self.edges)
        return [node_id for node_id in self.nodes.keys() if node_id not in incoming]

    def _find_end_nodes(self) -> List[str]:
        """Find nodes with no outgoing edges"""
        outgoing = set(edge.from_node for edge in self.edges)
        return [node_id for node_id in self.nodes.keys() if node_id not in outgoing]


class AmbivoWorkflow:
    """Main workflow executor for agent-to-agent workflows"""

    def __init__(
        self,
        nodes: Dict[str, WorkflowNode],
        edges: List[WorkflowEdge],
        start_nodes: List[str],
        end_nodes: List[str],
    ):
        self.nodes = nodes
        self.edges = edges
        self.start_nodes = start_nodes
        self.end_nodes = end_nodes
        self.logger = logging.getLogger("AmbivoWorkflow")

        # Create adjacency list for faster lookup
        self.adjacency: Dict[str, List[WorkflowEdge]] = {}
        for edge in edges:
            if edge.from_node not in self.adjacency:
                self.adjacency[edge.from_node] = []
            self.adjacency[edge.from_node].append(edge)

    async def execute(
        self, initial_message: str, execution_context: ExecutionContext = None
    ) -> WorkflowResult:
        """Execute the workflow sequentially"""
        start_time = time.time()
        messages = []
        nodes_executed = []
        errors = []

        try:
            # Create initial message
            user_message = AgentMessage(
                id=str(uuid.uuid4()),
                sender_id="workflow_user",
                recipient_id="workflow",
                content=initial_message,
                message_type=MessageType.USER_INPUT,
                session_id=(
                    execution_context.session_id if execution_context else "workflow_session"
                ),
                conversation_id=(
                    execution_context.conversation_id if execution_context else "workflow_conv"
                ),
            )
            messages.append(user_message)

            # Execute workflow starting from start nodes
            current_message = user_message
            executed_nodes = set()

            # Simple sequential execution for now
            nodes_to_execute = self._get_execution_order()

            for node_id in nodes_to_execute:
                if node_id in executed_nodes:
                    continue

                node = self.nodes[node_id]

                if node.node_type == WorkflowNodeType.AGENT and node.agent:
                    try:
                        self.logger.info(f"Executing agent: {node_id}")

                        # Route message to agent
                        response = await node.agent.process_message(
                            current_message, execution_context
                        )
                        messages.append(response)
                        nodes_executed.append(node_id)
                        executed_nodes.add(node_id)

                        # Use this response as input for next agent
                        current_message = response

                    except Exception as e:
                        error_msg = f"Error executing {node_id}: {str(e)}"
                        errors.append(error_msg)
                        self.logger.error(error_msg)

            execution_time = time.time() - start_time

            return WorkflowResult(
                success=len(errors) == 0,
                messages=messages,
                execution_time=execution_time,
                nodes_executed=nodes_executed,
                errors=errors,
            )

        except Exception as e:
            execution_time = time.time() - start_time
            return WorkflowResult(
                success=False,
                messages=messages,
                execution_time=execution_time,
                nodes_executed=nodes_executed,
                errors=[f"Workflow execution failed: {str(e)}"],
            )

    async def execute_parallel(
        self, initial_message: str, execution_context: ExecutionContext = None
    ) -> WorkflowResult:
        """Execute workflow with parallel execution where possible"""
        start_time = time.time()
        messages = []
        nodes_executed = []
        errors = []

        try:
            # Create initial message
            user_message = AgentMessage(
                id=str(uuid.uuid4()),
                sender_id="workflow_user",
                recipient_id="workflow",
                content=initial_message,
                message_type=MessageType.USER_INPUT,
                session_id=(
                    execution_context.session_id if execution_context else "workflow_session"
                ),
                conversation_id=(
                    execution_context.conversation_id if execution_context else "workflow_conv"
                ),
            )
            messages.append(user_message)

            # Execute in levels (topological sort)
            execution_levels = self._get_execution_levels()
            current_message = user_message

            for level_nodes in execution_levels:
                if len(level_nodes) == 1:
                    # Single node - execute sequentially
                    node_id = level_nodes[0]
                    node = self.nodes[node_id]

                    if node.node_type == WorkflowNodeType.AGENT and node.agent:
                        try:
                            response = await node.agent.process_message(
                                current_message, execution_context
                            )
                            messages.append(response)
                            nodes_executed.append(node_id)
                            current_message = response
                        except Exception as e:
                            errors.append(f"Error executing {node_id}: {str(e)}")

                else:
                    # Multiple nodes - execute in parallel
                    tasks = []
                    for node_id in level_nodes:
                        node = self.nodes[node_id]
                        if node.node_type == WorkflowNodeType.AGENT and node.agent:
                            task = node.agent.process_message(current_message, execution_context)
                            tasks.append((node_id, task))

                    # Wait for all parallel tasks
                    if tasks:
                        results = await asyncio.gather(
                            *[task for _, task in tasks], return_exceptions=True
                        )

                        parallel_responses = []
                        for i, (node_id, _) in enumerate(tasks):
                            result = results[i]
                            if isinstance(result, Exception):
                                errors.append(f"Error executing {node_id}: {str(result)}")
                            else:
                                messages.append(result)
                                nodes_executed.append(node_id)
                                parallel_responses.append(result)

                        # For next level, use the last response or combine them
                        if parallel_responses:
                            current_message = parallel_responses[-1]

            execution_time = time.time() - start_time

            return WorkflowResult(
                success=len(errors) == 0,
                messages=messages,
                execution_time=execution_time,
                nodes_executed=nodes_executed,
                errors=errors,
            )

        except Exception as e:
            execution_time = time.time() - start_time
            return WorkflowResult(
                success=False,
                messages=messages,
                execution_time=execution_time,
                nodes_executed=nodes_executed,
                errors=[f"Parallel workflow execution failed: {str(e)}"],
            )

    def _get_execution_order(self) -> List[str]:
        """Get a simple execution order (topological sort)"""
        # Simple implementation - can be enhanced with proper topological sort
        visited = set()
        order = []

        def dfs(node_id):
            if node_id in visited or node_id not in self.nodes:
                return
            visited.add(node_id)

            # Visit children first
            if node_id in self.adjacency:
                for edge in self.adjacency[node_id]:
                    dfs(edge.to_node)

            order.append(node_id)

        # Start from start nodes
        for start_node in self.start_nodes:
            dfs(start_node)

        return list(reversed(order))

    def _get_execution_levels(self) -> List[List[str]]:
        """Get execution levels for parallel execution"""
        # Simple level-based execution
        levels = []
        remaining_nodes = set(self.nodes.keys())
        current_level = self.start_nodes.copy()

        while current_level and remaining_nodes:
            levels.append(current_level)
            remaining_nodes -= set(current_level)

            # Find next level
            next_level = []
            for node_id in current_level:
                if node_id in self.adjacency:
                    for edge in self.adjacency[node_id]:
                        if edge.to_node in remaining_nodes:
                            next_level.append(edge.to_node)

            current_level = list(set(next_level))

        return levels


# Example workflow patterns that work with your existing agents


class WorkflowPatterns:
    """Common workflow patterns using ambivo agents"""

    @staticmethod
    def create_search_scrape_ingest_workflow(
        web_search_agent, web_scraper_agent, knowledge_base_agent
    ) -> AmbivoWorkflow:
        """
        Creates a workflow that:
        1. Searches the web for information
        2. Scrapes the found URLs
        3. Ingests the content into knowledge base
        """
        builder = WorkflowBuilder()

        # Add agents to workflow
        builder.add_agent(web_search_agent, "search")
        builder.add_agent(web_scraper_agent, "scrape")
        builder.add_agent(knowledge_base_agent, "ingest")

        # Define the flow: search -> scrape -> ingest
        builder.add_edge("search", "scrape")
        builder.add_edge("scrape", "ingest")

        # Set start and end points
        builder.set_start_node("search")
        builder.set_end_node("ingest")

        return builder.build()

    @staticmethod
    def create_research_analysis_workflow(
        web_search_agent, knowledge_base_agent, assistant_agent
    ) -> AmbivoWorkflow:
        """
        Creates a workflow that:
        1. Searches for information
        2. Stores findings in knowledge base (parallel)
        3. Assistant analyzes and summarizes (join)
        """
        builder = WorkflowBuilder()

        builder.add_agent(web_search_agent, "search")
        builder.add_agent(knowledge_base_agent, "store")
        builder.add_agent(assistant_agent, "analyze")

        # Parallel: search feeds both store and analyze
        builder.add_edge("search", "store")
        builder.add_edge("search", "analyze")

        builder.set_start_node("search")
        builder.set_end_node("store")
        builder.set_end_node("analyze")

        return builder.build()

    @staticmethod
    def create_media_processing_workflow(youtube_agent, media_editor_agent) -> AmbivoWorkflow:
        """
        Creates a workflow that:
        1. Downloads video from YouTube
        2. Processes/converts the media
        """
        builder = WorkflowBuilder()

        builder.add_agent(youtube_agent, "download")
        builder.add_agent(media_editor_agent, "process")

        builder.add_edge("download", "process")

        builder.set_start_node("download")
        builder.set_end_node("process")

        return builder.build()


# Integration with existing ModeratorAgent


class WorkflowModerator(BaseAgent):
    """Enhanced moderator that can execute workflows"""

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.workflows: Dict[str, AmbivoWorkflow] = {}

    def register_workflow(self, name: str, workflow: AmbivoWorkflow):
        """Register a named workflow"""
        self.workflows[name] = workflow

    async def execute_workflow(
        self, workflow_name: str, initial_message: str, execution_context: ExecutionContext = None
    ) -> WorkflowResult:
        """Execute a registered workflow"""
        if workflow_name not in self.workflows:
            raise ValueError(f"Workflow '{workflow_name}' not found")

        workflow = self.workflows[workflow_name]

        if execution_context is None:
            execution_context = self.get_execution_context()

        return await workflow.execute(initial_message, execution_context)

    async def process_message(
        self, message: AgentMessage, context: ExecutionContext = None
    ) -> AgentMessage:
        """Process message - can detect and execute workflows"""
        content = message.content.lower()

        # Simple workflow detection
        if "search scrape ingest" in content:
            return await self._handle_workflow_execution("search_scrape_ingest", message, context)
        elif "research and analyze" in content:
            return await self._handle_workflow_execution("research_analysis", message, context)
        else:
            # Default assistant behavior
            return self.create_response(
                content="I can execute workflows like 'search scrape ingest' or 'research and analyze'. What would you like to do?",
                recipient_id=message.sender_id,
                session_id=message.session_id,
                conversation_id=message.conversation_id,
            )

    async def _handle_workflow_execution(
        self, workflow_name: str, message: AgentMessage, context: ExecutionContext
    ) -> AgentMessage:
        """Handle workflow execution"""
        try:
            result = await self.execute_workflow(workflow_name, message.content, context)

            if result.success:
                # Format workflow results
                response_content = f"Workflow '{workflow_name}' completed successfully!\n\n"
                response_content += f"Execution time: {result.execution_time:.2f}s\n"
                response_content += f"Nodes executed: {', '.join(result.nodes_executed)}\n"
                response_content += f"Messages generated: {len(result.messages)}\n\n"

                # Include final message content
                if result.messages:
                    final_message = result.messages[-1]
                    response_content += f"Final result:\n{final_message.content}"

                return self.create_response(
                    content=response_content,
                    recipient_id=message.sender_id,
                    session_id=message.session_id,
                    conversation_id=message.conversation_id,
                )
            else:
                error_content = f"Workflow '{workflow_name}' failed:\n"
                error_content += "\n".join(result.errors)

                return self.create_response(
                    content=error_content,
                    recipient_id=message.sender_id,
                    message_type=MessageType.ERROR,
                    session_id=message.session_id,
                    conversation_id=message.conversation_id,
                )

        except Exception as e:
            return self.create_response(
                content=f"Error executing workflow: {str(e)}",
                recipient_id=message.sender_id,
                message_type=MessageType.ERROR,
                session_id=message.session_id,
                conversation_id=message.conversation_id,
            )

    # Add this to ambivo_agents/core/workflow.py WorkflowModerator class
    async def process_message_stream(
        self, message: AgentMessage, context: ExecutionContext = None
    ) -> AsyncIterator[str]:
        """Simple streaming implementation"""
        response = await self.process_message(message, context)
        yield response.content
