# ambivo_agents/core/enhanced_workflow.py
"""
Enhanced Workflow System with Visual Builder, State Management, and Advanced Patterns
Building on the existing workflow.py foundation
"""

import asyncio
import json
import logging
import time
import uuid
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, AsyncIterator, Callable, Dict, List, Optional, Union

from .base import AgentMessage, BaseAgent, ExecutionContext, MessageType

# Import your existing workflow components
from .workflow import (
    AmbivoWorkflow,
    WorkflowBuilder,
    WorkflowEdge,
    WorkflowExecutionType,
    WorkflowNode,
    WorkflowNodeType,
    WorkflowResult,
)


class AdvancedWorkflowBuilder(WorkflowBuilder):
    """Enhanced workflow builder with conditional logic and validation"""

    def __init__(self):
        super().__init__()
        self.conditions: Dict[str, Callable] = {}
        self.variables: Dict[str, Any] = {}
        self.workflows_metadata = {}

    def add_conditional_agent(
        self,
        agent: BaseAgent,
        condition_func: Callable,
        true_path: str = None,
        false_path: str = None,
        node_id: str = None,
    ) -> "AdvancedWorkflowBuilder":
        """Add agent with conditional execution"""
        if node_id is None:
            node_id = agent.agent_id

        # Add the agent node
        self.add_agent(agent, node_id)

        # Add condition metadata
        self.workflows_metadata[node_id] = {
            "type": "conditional",
            "condition": condition_func,
            "true_path": true_path,
            "false_path": false_path,
        }

        return self

    def add_map_reduce_pattern(
        self,
        mapper_agents: List[BaseAgent],
        reducer_agent: BaseAgent,
        data_splitter: Callable = None,
    ) -> "AdvancedWorkflowBuilder":
        """Add map-reduce pattern to workflow"""

        # Add mapper agents in parallel
        map_nodes = []
        for i, agent in enumerate(mapper_agents):
            node_id = f"mapper_{i}_{agent.agent_id}"
            self.add_agent(agent, node_id)
            map_nodes.append(node_id)

        # Add reducer agent
        reducer_id = f"reducer_{reducer_agent.agent_id}"
        self.add_agent(reducer_agent, reducer_id)

        # Connect all mappers to reducer
        for map_node in map_nodes:
            self.add_edge(map_node, reducer_id)

        # Store metadata
        self.workflows_metadata["map_reduce"] = {
            "mappers": map_nodes,
            "reducer": reducer_id,
            "data_splitter": data_splitter,
        }

        return self

    def add_loop_pattern(
        self, agents: List[BaseAgent], loop_condition: Callable, max_iterations: int = 10
    ) -> "AdvancedWorkflowBuilder":
        """Add loop pattern with condition"""

        loop_start = f"loop_start_{uuid.uuid4().hex[:8]}"
        loop_end = f"loop_end_{uuid.uuid4().hex[:8]}"

        # Create loop structure
        for i, agent in enumerate(agents):
            node_id = f"loop_{i}_{agent.agent_id}"
            self.add_agent(agent, node_id)

            if i == 0:
                # Connect start to first agent
                self.add_edge(loop_start, node_id)
            else:
                # Connect previous to current
                prev_id = f"loop_{i - 1}_{agents[i - 1].agent_id}"
                self.add_edge(prev_id, node_id)

        # Add loop condition
        last_agent_id = f"loop_{len(agents) - 1}_{agents[-1].agent_id}"
        self.add_edge(last_agent_id, loop_end, condition=loop_condition)

        # Loop back edge
        self.add_edge(
            last_agent_id, f"loop_0_{agents[0].agent_id}", condition=lambda x: not loop_condition(x)
        )

        self.workflows_metadata["loop"] = {
            "agents": agents,
            "condition": loop_condition,
            "max_iterations": max_iterations,
            "start": loop_start,
            "end": loop_end,
        }

        return self

    def validate_workflow(self) -> Dict[str, Any]:
        """Validate workflow structure and detect issues"""
        issues = []
        warnings = []

        # Check for cycles (except intentional loops)
        cycles = self._detect_cycles()
        if cycles:
            issues.append(f"Detected cycles: {cycles}")

        # Check for unreachable nodes
        unreachable = self._find_unreachable_nodes()
        if unreachable:
            warnings.append(f"Unreachable nodes: {unreachable}")

        # Check for missing agents
        missing_agents = [
            node_id
            for node_id, node in self.nodes.items()
            if node.node_type == WorkflowNodeType.AGENT and node.agent is None
        ]
        if missing_agents:
            issues.append(f"Nodes missing agents: {missing_agents}")

        return {
            "valid": len(issues) == 0,
            "issues": issues,
            "warnings": warnings,
            "node_count": len(self.nodes),
            "edge_count": len(self.edges),
        }

    def _detect_cycles(self) -> List[List[str]]:
        """Detect cycles in workflow graph"""
        visited = set()
        rec_stack = set()
        cycles = []

        def dfs(node, path):
            if node in rec_stack:
                cycle_start = path.index(node)
                cycles.append(path[cycle_start:] + [node])
                return

            if node in visited:
                return

            visited.add(node)
            rec_stack.add(node)

            # Visit neighbors
            for edge in self.adjacency.get(node, []):
                dfs(edge.to_node, path + [edge.to_node])

            rec_stack.remove(node)

        # Start DFS from all start nodes
        for start_node in self.start_nodes:
            dfs(start_node, [start_node])

        return cycles

    def _find_unreachable_nodes(self) -> List[str]:
        """Find nodes unreachable from start nodes"""
        reachable = set()

        def dfs(node):
            if node in reachable:
                return
            reachable.add(node)

            for edge in self.adjacency.get(node, []):
                dfs(edge.to_node)

        # Mark all reachable nodes
        for start_node in self.start_nodes:
            dfs(start_node)

        # Find unreachable
        all_nodes = set(self.nodes.keys())
        return list(all_nodes - reachable)


@dataclass
class WorkflowState:
    """Persistent workflow execution state"""

    workflow_id: str
    execution_id: str
    current_node: str
    completed_nodes: List[str]
    failed_nodes: List[str]
    node_results: Dict[str, Any]
    variables: Dict[str, Any]
    start_time: datetime
    last_update: datetime
    status: str = "running"  # running, completed, failed, paused
    error_message: Optional[str] = None


class StatefulWorkflowExecutor:
    """Workflow executor with state persistence and resume capability"""

    def __init__(self, memory_manager=None):
        self.memory_manager = memory_manager
        self.active_workflows: Dict[str, WorkflowState] = {}
        self.logger = logging.getLogger("StatefulWorkflowExecutor")

    async def execute_workflow(
        self,
        workflow: AmbivoWorkflow,
        initial_message: str,
        execution_context: ExecutionContext = None,
        workflow_id: str = None,
    ) -> WorkflowResult:
        """Execute workflow with state persistence"""

        execution_id = str(uuid.uuid4())
        workflow_id = workflow_id or f"workflow_{execution_id[:8]}"

        # Initialize workflow state
        state = WorkflowState(
            workflow_id=workflow_id,
            execution_id=execution_id,
            current_node="",
            completed_nodes=[],
            failed_nodes=[],
            node_results={},
            variables={},
            start_time=datetime.now(),
            last_update=datetime.now(),
        )

        self.active_workflows[execution_id] = state

        try:
            # Execute with checkpointing
            result = await self._execute_with_checkpoints(
                workflow, initial_message, execution_context, state
            )

            state.status = "completed" if result.success else "failed"
            state.last_update = datetime.now()

            # Save final state
            await self._save_workflow_state(state)

            return result

        except Exception as e:
            state.status = "failed"
            state.error_message = str(e)
            state.last_update = datetime.now()
            await self._save_workflow_state(state)
            raise

    async def resume_workflow(self, execution_id: str) -> WorkflowResult:
        """Resume a paused or failed workflow"""

        state = await self._load_workflow_state(execution_id)
        if not state:
            raise ValueError(f"Workflow state not found: {execution_id}")

        if state.status == "completed":
            raise ValueError("Cannot resume completed workflow")

        # Resume from current node
        self.logger.info(f"Resuming workflow {execution_id} from node {state.current_node}")

        # Implementation depends on your specific workflow structure
        # This is a simplified version
        return await self._resume_from_state(state)

    async def _resume_from_state(self, state: WorkflowState) -> WorkflowResult:
        """Resume workflow from saved state"""
        # Simplified implementation - in practice would need to reconstruct workflow
        return WorkflowResult(
            success=False,
            messages=[],
            execution_time=0.0,
            nodes_executed=state.completed_nodes,
            errors=["Resume not fully implemented"],
        )

    async def _execute_with_checkpoints(
        self,
        workflow: AmbivoWorkflow,
        initial_message: str,
        context: ExecutionContext,
        state: WorkflowState,
    ) -> WorkflowResult:
        """Execute workflow with regular checkpointing"""

        start_time = time.time()
        messages = []
        errors = []

        try:
            # Create initial message
            user_message = AgentMessage(
                id=str(uuid.uuid4()),
                sender_id="workflow_user",
                recipient_id="workflow",
                content=initial_message,
                message_type=MessageType.USER_INPUT,
                session_id=context.session_id if context else "workflow_session",
                conversation_id=context.conversation_id if context else "workflow_conv",
            )
            messages.append(user_message)

            current_message = user_message

            # Execute nodes with checkpointing
            execution_order = workflow._get_execution_order()

            for node_id in execution_order:
                if node_id in state.completed_nodes:
                    continue  # Skip already completed nodes

                state.current_node = node_id
                state.last_update = datetime.now()

                # Checkpoint before each node
                await self._save_workflow_state(state)

                node = workflow.nodes[node_id]

                if node.node_type == WorkflowNodeType.AGENT and node.agent:
                    try:
                        self.logger.info(f"Executing node: {node_id}")

                        response = await node.agent.process_message(current_message, context)
                        messages.append(response)

                        # Store node result
                        state.node_results[node_id] = {
                            "response": response.content,
                            "success": True,
                            "timestamp": datetime.now().isoformat(),
                        }

                        state.completed_nodes.append(node_id)
                        current_message = response

                    except Exception as e:
                        error_msg = f"Error executing {node_id}: {str(e)}"
                        errors.append(error_msg)
                        state.failed_nodes.append(node_id)
                        state.node_results[node_id] = {
                            "error": str(e),
                            "success": False,
                            "timestamp": datetime.now().isoformat(),
                        }
                        self.logger.error(error_msg)

            execution_time = time.time() - start_time

            return WorkflowResult(
                success=len(errors) == 0,
                messages=messages,
                execution_time=execution_time,
                nodes_executed=state.completed_nodes,
                errors=errors,
                metadata={
                    "workflow_id": state.workflow_id,
                    "execution_id": state.execution_id,
                    "checkpoints": len(state.completed_nodes),
                    "state_saved": True,
                },
            )

        except Exception as e:
            execution_time = time.time() - start_time
            return WorkflowResult(
                success=False,
                messages=messages,
                execution_time=execution_time,
                nodes_executed=state.completed_nodes,
                errors=[f"Workflow execution failed: {str(e)}"],
            )

    async def _save_workflow_state(self, state: WorkflowState):
        """Save workflow state to persistent storage"""
        if self.memory_manager:
            try:
                state_data = {
                    "workflow_id": state.workflow_id,
                    "execution_id": state.execution_id,
                    "current_node": state.current_node,
                    "completed_nodes": state.completed_nodes,
                    "failed_nodes": state.failed_nodes,
                    "node_results": state.node_results,
                    "variables": state.variables,
                    "start_time": state.start_time.isoformat(),
                    "last_update": state.last_update.isoformat(),
                    "status": state.status,
                    "error_message": state.error_message,
                }

                self.memory_manager.store_context(
                    f"workflow_state:{state.execution_id}", state_data
                )

            except Exception as e:
                self.logger.error(f"Failed to save workflow state: {e}")

    async def _load_workflow_state(self, execution_id: str) -> Optional[WorkflowState]:
        """Load workflow state from persistent storage"""
        if not self.memory_manager:
            return None

        try:
            state_data = self.memory_manager.get_context(f"workflow_state:{execution_id}")
            if not state_data:
                return None

            return WorkflowState(
                workflow_id=state_data["workflow_id"],
                execution_id=state_data["execution_id"],
                current_node=state_data["current_node"],
                completed_nodes=state_data["completed_nodes"],
                failed_nodes=state_data["failed_nodes"],
                node_results=state_data["node_results"],
                variables=state_data["variables"],
                start_time=datetime.fromisoformat(state_data["start_time"]),
                last_update=datetime.fromisoformat(state_data["last_update"]),
                status=state_data["status"],
                error_message=state_data.get("error_message"),
            )

        except Exception as e:
            self.logger.error(f"Failed to load workflow state: {e}")
            return None


class WorkflowModerator(BaseAgent):
    """Enhanced WorkflowModerator that integrates with your existing ModeratorAgent"""

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.workflow_executor = StatefulWorkflowExecutor(self.memory)
        self.registered_workflows: Dict[str, AmbivoWorkflow] = {}
        self.active_executions: Dict[str, str] = {}  # user_session -> execution_id

    def register_workflow(self, name: str, workflow: AmbivoWorkflow):
        """Register a named workflow"""
        self.registered_workflows[name] = workflow

    async def execute_named_workflow(
        self, workflow_name: str, initial_message: str, context: ExecutionContext = None
    ) -> WorkflowResult:
        """Execute a registered workflow by name"""
        if workflow_name not in self.registered_workflows:
            raise ValueError(f"Workflow '{workflow_name}' not found")

        workflow = self.registered_workflows[workflow_name]

        return await self.workflow_executor.execute_workflow(
            workflow, initial_message, context or self.get_execution_context()
        )

    async def process_message(
        self, message: AgentMessage, context: ExecutionContext = None
    ) -> AgentMessage:
        """Process message with workflow detection and execution"""

        content = message.content.lower()

        # Check for workflow commands
        if content.startswith("workflow "):
            return await self._handle_workflow_command(message, context)

        # Check for registered workflow patterns
        for workflow_name in self.registered_workflows:
            if workflow_name.replace("_", " ") in content:
                return await self._execute_workflow_from_message(workflow_name, message, context)

        # Default response
        return self.create_response(
            content="I can execute workflows. Available workflows: "
            + ", ".join(self.registered_workflows.keys()),
            recipient_id=message.sender_id,
            session_id=message.session_id,
            conversation_id=message.conversation_id,
        )

    async def _handle_workflow_command(
        self, message: AgentMessage, context: ExecutionContext
    ) -> AgentMessage:
        """Handle workflow-specific commands"""

        parts = message.content.split()
        if len(parts) < 2:
            return self.create_response(
                content="Usage: workflow <command> [args]",
                recipient_id=message.sender_id,
                session_id=message.session_id,
                conversation_id=message.conversation_id,
            )

        command = parts[1].lower()

        if command == "list":
            workflows = list(self.registered_workflows.keys())
            return self.create_response(
                content=f"Available workflows: {', '.join(workflows)}",
                recipient_id=message.sender_id,
                session_id=message.session_id,
                conversation_id=message.conversation_id,
            )

        elif command == "status":
            if len(parts) > 2:
                execution_id = parts[2]
                # Get status of specific execution
                state = await self.workflow_executor._load_workflow_state(execution_id)
                if state:
                    return self.create_response(
                        content=f"Workflow {execution_id}: {state.status} "
                        f"({len(state.completed_nodes)} nodes completed)",
                        recipient_id=message.sender_id,
                        session_id=message.session_id,
                        conversation_id=message.conversation_id,
                    )
                else:
                    return self.create_response(
                        content=f"Workflow {execution_id} not found",
                        recipient_id=message.sender_id,
                        session_id=message.session_id,
                        conversation_id=message.conversation_id,
                    )

        elif command == "resume":
            if len(parts) > 2:
                execution_id = parts[2]
                try:
                    result = await self.workflow_executor.resume_workflow(execution_id)
                    return self.create_response(
                        content=f"Workflow resumed. Success: {result.success}",
                        recipient_id=message.sender_id,
                        session_id=message.session_id,
                        conversation_id=message.conversation_id,
                    )
                except Exception as e:
                    return self.create_response(
                        content=f"Failed to resume workflow: {str(e)}",
                        recipient_id=message.sender_id,
                        message_type=MessageType.ERROR,
                        session_id=message.session_id,
                        conversation_id=message.conversation_id,
                    )

        return self.create_response(
            content=f"Unknown workflow command: {command}",
            recipient_id=message.sender_id,
            session_id=message.session_id,
            conversation_id=message.conversation_id,
        )

    async def process_message_stream(
        self, message: AgentMessage, context: ExecutionContext = None
    ) -> AsyncIterator[str]:
        """Stream processing for WorkflowModerator"""

        content = message.content.lower()

        # Check for workflow commands
        if content.startswith("workflow "):
            response = await self._handle_workflow_command(message, context)
            yield response.content
            # Don't use return in async generator, just end the function

        else:
            # Check for registered workflow patterns
            workflow_found = False
            for workflow_name in self.registered_workflows:
                if workflow_name.replace("_", " ") in content:
                    workflow_found = True
                    yield f"x-amb-info:Executing workflow: {workflow_name}\n"
                    yield f"x-amb-info:Starting workflow execution...\n\n"

                    try:
                        result = await self.execute_named_workflow(
                            workflow_name, message.content, context or self.get_execution_context()
                        )

                        if result.success:
                            yield f"x-amb-info:Workflow '{workflow_name}' completed successfully!\n\n"
                            yield f"x-amb-info:Execution time: {result.execution_time:.2f}s\n"
                            yield f"x-amb-info:Nodes executed: {', '.join(result.nodes_executed)}\n"
                            yield f"x-amb-info:Messages generated: {len(result.messages)}\n\n"

                            if result.messages:
                                final_message = result.messages[-1]
                                yield f"x-amb-info:Final result:**\n{final_message.content}"
                        else:
                            yield f"x-amb-info:Workflow '{workflow_name}' failed:\n"
                            yield "\n".join(result.errors)

                    except Exception as e:
                        yield f"x-amb-info:Error executing workflow: {str(e)}"

                    break  # Exit the loop, don't use return

            # If no workflow found, provide default response
            if not workflow_found:
                yield "x-amb-info:**Workflow Moderator**\n\n"
                yield f"Available workflows: {', '.join(self.registered_workflows.keys())}\n\n"
                yield "💡 **Commands:**\n"
                yield "• `workflow list` - List available workflows\n"
                yield "• `workflow status <id>` - Check workflow status\n"
                yield "• `workflow resume <id>` - Resume paused workflow\n"
                yield "• Or describe what you want to do naturally!"

    async def _execute_workflow_from_message(
        self, workflow_name: str, message: AgentMessage, context: ExecutionContext
    ) -> AgentMessage:
        """Execute workflow based on message content"""

        try:
            result = await self.execute_named_workflow(workflow_name, message.content, context)

            if result.success:
                response_content = f"✅ Workflow '{workflow_name}' completed successfully!\n\n"
                response_content += f"⏱️ Execution time: {result.execution_time:.2f}s\n"
                response_content += f"🔧 Nodes executed: {', '.join(result.nodes_executed)}\n"
                response_content += f"💬 Messages generated: {len(result.messages)}\n\n"

                if result.messages:
                    final_message = result.messages[-1]
                    response_content += f"**Final result:**\n{final_message.content}"

                return self.create_response(
                    content=response_content,
                    recipient_id=message.sender_id,
                    session_id=message.session_id,
                    conversation_id=message.conversation_id,
                )
            else:
                error_content = f"❌ Workflow '{workflow_name}' failed:\n"
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


# Enhanced workflow patterns
class AdvancedWorkflowPatterns:
    """Advanced workflow patterns beyond the basic ones"""

    @staticmethod
    def create_debate_workflow(
        debater_agents: List[BaseAgent], moderator_agent: BaseAgent, rounds: int = 3
    ) -> AmbivoWorkflow:
        """Create a debate workflow between multiple agents"""

        builder = AdvancedWorkflowBuilder()

        # Add moderator to start
        builder.add_agent(moderator_agent, "moderator_start")

        # Add debaters
        for i, agent in enumerate(debater_agents):
            builder.add_agent(agent, f"debater_{i}")

        # Create debate rounds
        for round_num in range(rounds):
            for i, agent in enumerate(debater_agents):
                current_id = f"debater_{i}_round_{round_num}"
                builder.add_agent(agent, current_id)

                if round_num == 0:
                    # First round: moderator starts
                    if i == 0:
                        builder.add_edge("moderator_start", current_id)
                    else:
                        prev_id = f"debater_{i - 1}_round_{round_num}"
                        builder.add_edge(prev_id, current_id)
                else:
                    # Subsequent rounds: continue from previous round
                    prev_round_id = f"debater_{i}_round_{round_num - 1}"
                    builder.add_edge(prev_round_id, current_id)

        # Add final moderator summary
        builder.add_agent(moderator_agent, "moderator_end")
        last_debater = f"debater_{len(debater_agents) - 1}_round_{rounds - 1}"
        builder.add_edge(last_debater, "moderator_end")

        builder.set_start_node("moderator_start")
        builder.set_end_node("moderator_end")

        return builder.build()

    @staticmethod
    def create_consensus_workflow(
        agents: List[BaseAgent], consensus_threshold: float = 0.8
    ) -> AmbivoWorkflow:
        """Create a consensus-building workflow"""

        builder = AdvancedWorkflowBuilder()

        # Add all agents
        for i, agent in enumerate(agents):
            builder.add_agent(agent, f"agent_{i}")

        # Create consensus checking logic
        def check_consensus(message: AgentMessage) -> bool:
            # Simple consensus check - in practice this would be more sophisticated
            content = message.content.lower()
            agreement_words = ["agree", "yes", "correct", "consensus", "aligned"]
            disagreement_words = ["disagree", "no", "wrong", "different"]

            agreement_score = sum(1 for word in agreement_words if word in content)
            disagreement_score = sum(1 for word in disagreement_words if word in content)

            total_score = agreement_score + disagreement_score
            if total_score == 0:
                return False

            return (agreement_score / total_score) >= consensus_threshold

        # Add consensus loop
        builder.add_loop_pattern(agents, check_consensus, max_iterations=5)

        return builder.build()

    @staticmethod
    def create_error_recovery_workflow(
        primary_agent: BaseAgent, backup_agents: List[BaseAgent]
    ) -> AmbivoWorkflow:
        """Create workflow with error recovery and fallback agents"""

        builder = AdvancedWorkflowBuilder()

        # Add primary agent
        builder.add_agent(primary_agent, "primary")

        # Add backup agents
        for i, agent in enumerate(backup_agents):
            builder.add_agent(agent, f"backup_{i}")

        # Create error detection condition
        def has_error(message: AgentMessage) -> bool:
            return (
                message.message_type == MessageType.ERROR
                or "error" in message.content.lower()
                or "failed" in message.content.lower()
            )

        # Add conditional routing to backup agents
        builder.add_conditional_agent(
            primary_agent,
            condition_func=lambda msg: not has_error(msg),
            true_path="success_end",
            false_path="backup_0",
            node_id="primary",
        )

        # Chain backup agents
        for i, agent in enumerate(backup_agents):
            if i < len(backup_agents) - 1:
                builder.add_conditional_agent(
                    agent,
                    condition_func=lambda msg: not has_error(msg),
                    true_path="success_end",
                    false_path=f"backup_{i + 1}",
                    node_id=f"backup_{i}",
                )
            else:
                # Last backup agent
                builder.add_agent(agent, f"backup_{i}")
                builder.add_edge(f"backup_{i}", "final_error")

        builder.set_start_node("primary")
        builder.set_end_node("success_end")

        return builder.build()


# Integration with your existing ModeratorAgent
class EnhancedModeratorAgent:
    """Enhanced ModeratorAgent that integrates advanced workflows"""

    def __init__(self, base_moderator):
        self.base_moderator = base_moderator
        self.workflow_moderator = WorkflowModerator(
            agent_id=f"workflow_{base_moderator.agent_id}",
            memory_manager=base_moderator.memory,
            llm_service=base_moderator.llm_service,
        )
        self.advanced_workflows = {}
        self._setup_advanced_workflows()

    def _setup_advanced_workflows(self):
        """Setup advanced workflow patterns"""

        # Get available agents from base moderator
        agents = self.base_moderator.specialized_agents

        # 1. Research Consensus Workflow
        if all(agent_type in agents for agent_type in ["web_search", "assistant"]):
            research_agents = [agents["web_search"], agents["assistant"]]

            consensus_workflow = AdvancedWorkflowPatterns.create_consensus_workflow(
                research_agents, consensus_threshold=0.7
            )
            self.workflow_moderator.register_workflow("research_consensus", consensus_workflow)
            self.advanced_workflows["research_consensus"] = consensus_workflow

        # 2. Multi-Agent Debate Workflow
        if "assistant" in agents:
            # Create multiple assistant instances for debate
            debater_1 = agents["assistant"]
            debater_2 = agents["assistant"]  # In practice, you'd want different perspectives
            moderator = agents["assistant"]

            debate_workflow = AdvancedWorkflowPatterns.create_debate_workflow(
                [debater_1, debater_2], moderator, rounds=2
            )
            self.workflow_moderator.register_workflow("multi_agent_debate", debate_workflow)
            self.advanced_workflows["multi_agent_debate"] = debate_workflow

        # 3. Error Recovery Workflow
        if len(agents) >= 2:
            primary = list(agents.values())[0]
            backups = list(agents.values())[1:3]  # Take first 2 as backups

            error_recovery_workflow = AdvancedWorkflowPatterns.create_error_recovery_workflow(
                primary, backups
            )
            self.workflow_moderator.register_workflow("error_recovery", error_recovery_workflow)
            self.advanced_workflows["error_recovery"] = error_recovery_workflow

        # 4. Map-Reduce Analysis Workflow
        if "web_search" in agents and "assistant" in agents:
            mappers = [agents["web_search"]] * 3  # 3 parallel searches
            reducer = agents["assistant"]

            builder = AdvancedWorkflowBuilder()
            map_reduce_workflow = builder.add_map_reduce_pattern(mappers, reducer).build()

            self.workflow_moderator.register_workflow("map_reduce_analysis", map_reduce_workflow)
            self.advanced_workflows["map_reduce_analysis"] = map_reduce_workflow

    async def process_message_with_workflows(
        self, message: AgentMessage, context: ExecutionContext = None
    ) -> AgentMessage:
        """Enhanced message processing with advanced workflow detection"""

        content = message.content.lower()

        # Check for advanced workflow patterns
        if any(
            phrase in content
            for phrase in ["consensus", "agreement", "collaborate", "all agents agree"]
        ):
            if "research_consensus" in self.advanced_workflows:
                return await self.workflow_moderator._execute_workflow_from_message(
                    "research_consensus", message, context
                )

        elif any(
            phrase in content
            for phrase in ["debate", "argue", "different perspectives", "pros and cons"]
        ):
            if "multi_agent_debate" in self.advanced_workflows:
                return await self.workflow_moderator._execute_workflow_from_message(
                    "multi_agent_debate", message, context
                )

        elif any(
            phrase in content
            for phrase in ["backup plan", "fallback", "error recovery", "if this fails"]
        ):
            if "error_recovery" in self.advanced_workflows:
                return await self.workflow_moderator._execute_workflow_from_message(
                    "error_recovery", message, context
                )

        elif any(
            phrase in content
            for phrase in [
                "parallel analysis",
                "map reduce",
                "distribute work",
                "divide and analyze",
            ]
        ):
            if "map_reduce_analysis" in self.advanced_workflows:
                return await self.workflow_moderator._execute_workflow_from_message(
                    "map_reduce_analysis", message, context
                )

        # Fall back to base moderator
        return await self.base_moderator.process_message(message, context)

    async def get_workflow_status(self) -> Dict[str, Any]:
        """Get comprehensive workflow status"""

        base_status = await self.base_moderator.get_agent_status()

        workflow_status = {
            "base_moderator": base_status,
            "advanced_workflows": {
                "registered": list(self.advanced_workflows.keys()),
                "count": len(self.advanced_workflows),
            },
            "workflow_moderator": {
                "active_executions": len(self.workflow_moderator.active_executions),
                "registered_workflows": list(self.workflow_moderator.registered_workflows.keys()),
            },
        }

        return workflow_status


# Workflow Visualization and Monitoring
class WorkflowVisualizer:
    """Generate visual representations of workflows"""

    @staticmethod
    def generate_mermaid_diagram(workflow: AmbivoWorkflow) -> str:
        """Generate Mermaid diagram for workflow visualization"""

        lines = ["graph TD"]

        # Add nodes
        for node_id, node in workflow.nodes.items():
            if node.node_type == WorkflowNodeType.AGENT:
                agent_name = node.agent.name if node.agent else node_id
                lines.append(f'    {node_id}["{agent_name}"]')
            else:
                lines.append(f"    {node_id}{{{node_id}}}")

        # Add edges
        for edge in workflow.edges:
            if edge.condition:
                lines.append(f"    {edge.from_node} -->|condition| {edge.to_node}")
            else:
                lines.append(f"    {edge.from_node} --> {edge.to_node}")

        # Style start and end nodes
        for start_node in workflow.start_nodes:
            lines.append(f"    classDef startNode fill:#90EE90")
            lines.append(f"    class {start_node} startNode")

        for end_node in workflow.end_nodes:
            lines.append(f"    classDef endNode fill:#FFB6C1")
            lines.append(f"    class {end_node} endNode")

        return "\n".join(lines)

    @staticmethod
    def generate_execution_report(
        result: WorkflowResult, state: WorkflowState = None
    ) -> Dict[str, Any]:
        """Generate comprehensive execution report"""

        report = {
            "execution_summary": {
                "success": result.success,
                "execution_time": result.execution_time,
                "nodes_executed": len(result.nodes_executed),
                "total_messages": len(result.messages),
                "errors": len(result.errors),
            },
            "execution_timeline": [],
            "node_performance": {},
            "message_flow": [],
        }

        # Add execution timeline
        if state:
            for node_id in result.nodes_executed:
                node_result = state.node_results.get(node_id, {})
                report["execution_timeline"].append(
                    {
                        "node": node_id,
                        "timestamp": node_result.get("timestamp"),
                        "success": node_result.get("success", True),
                        "duration": node_result.get("duration", 0),
                    }
                )

        # Add message flow
        for i, message in enumerate(result.messages):
            report["message_flow"].append(
                {
                    "step": i,
                    "sender": message.sender_id,
                    "recipient": message.recipient_id,
                    "type": message.message_type.value,
                    "content_preview": (
                        message.content[:100] + "..."
                        if len(message.content) > 100
                        else message.content
                    ),
                }
            )

        return report


# Usage Examples and Integration Guide
async def setup_enhanced_workflow_system():
    """Complete setup example for enhanced workflow system"""

    # Import your existing moderator
    from ambivo_agents.agents import ModeratorAgent

    # Create base moderator
    base_moderator = ModeratorAgent.create_simple(
        user_id="workflow_admin",
        enabled_agents=["web_search", "assistant", "code_executor", "knowledge_base"],
    )

    # Enhance with advanced workflows
    enhanced_moderator = EnhancedModeratorAgent(base_moderator)

    # Test advanced workflow
    test_message = AgentMessage(
        id=str(uuid.uuid4()),
        sender_id="test_user",
        recipient_id=enhanced_moderator.base_moderator.agent_id,
        content="I need multiple agents to debate the pros and cons of renewable energy",
        message_type=MessageType.USER_INPUT,
        session_id="test_session",
        conversation_id="test_conv",
    )

    # Execute with advanced workflow detection
    response = await enhanced_moderator.process_message_with_workflows(test_message)

    print("Enhanced workflow system ready!")
    print(f"Response: {response.content[:200]}...")

    # Get workflow status
    status = await enhanced_moderator.get_workflow_status()
    print(f"Advanced workflows available: {status['advanced_workflows']['registered']}")

    return enhanced_moderator


# Quick Integration Script
async def integrate_with_existing_system():
    """Quick integration script for your existing system"""

    print("🚀 Integrating Advanced Workflows with Existing System...")

    # Step 1: Import your existing moderator
    try:
        from ambivo_agents.agents.moderator import ModeratorAgent

        print("✅ Found existing ModeratorAgent")
    except ImportError:
        print("❌ Could not import ModeratorAgent")
        return None

    # Step 2: Create enhanced version
    base_moderator = ModeratorAgent.create_simple(user_id="integration_test")
    enhanced_moderator = EnhancedModeratorAgent(base_moderator)

    # Step 3: Test workflow patterns
    test_patterns = [
        "I need agents to reach consensus on climate change solutions",
        "Create a debate between agents about AI ethics",
        "Analyze this data with parallel processing and error recovery",
        "Use map-reduce to research multiple topics simultaneously",
    ]

    print("\n🔧 Testing Advanced Workflow Patterns:")

    for pattern in test_patterns:
        print(f"\n📝 Testing: {pattern[:50]}...")

        test_message = AgentMessage(
            id=str(uuid.uuid4()),
            sender_id="test_user",
            recipient_id=enhanced_moderator.base_moderator.agent_id,
            content=pattern,
            message_type=MessageType.USER_INPUT,
            session_id="integration_test",
            conversation_id="integration_test",
        )

        try:
            response = await enhanced_moderator.process_message_with_workflows(test_message)
            print(f"✅ Response received: {len(response.content)} characters")
        except Exception as e:
            print(f"❌ Error: {str(e)}")

    print("\n🎉 Integration complete!")

    # Step 4: Show available workflows
    status = await enhanced_moderator.get_workflow_status()
    print(f"\n📊 Available advanced workflows: {status['advanced_workflows']['registered']}")

    return enhanced_moderator


if __name__ == "__main__":
    # Run integration example
    import asyncio

    asyncio.run(integrate_with_existing_system())
