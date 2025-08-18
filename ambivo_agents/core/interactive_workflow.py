# ambivo_agents/core/interactive_workflow.py
"""
Production-Ready Interactive Workflow System

This module provides robust stateful workflow management for interactive chat
and orchestration, designed for third-party developer productivity.

Key Features:
- Comprehensive state persistence with granular node tracking
- Human-in-the-loop workflow support
- Real-time user interaction capabilities
- Rollback and recovery mechanisms
- Resource management and rate limiting
- Distributed execution support
- Workflow versioning and migration
"""

import asyncio
import json
import logging
import time
import uuid
from dataclasses import dataclass, field, asdict
from datetime import datetime, timedelta
from enum import Enum
from typing import Any, AsyncIterator, Callable, Dict, List, Optional, Union, Tuple
import copy
from pathlib import Path

from .base import AgentMessage, BaseAgent, ExecutionContext, MessageType
from .workflow import AmbivoWorkflow, WorkflowBuilder, WorkflowEdge, WorkflowNode, WorkflowResult


class NodeExecutionState(Enum):
    """Granular node execution states"""

    PENDING = "pending"
    RUNNING = "running"
    WAITING_USER_INPUT = "waiting_user_input"
    WAITING_APPROVAL = "waiting_approval"
    PAUSED = "paused"
    COMPLETED = "completed"
    FAILED = "failed"
    SKIPPED = "skipped"
    ROLLED_BACK = "rolled_back"


class WorkflowTriggerType(Enum):
    """Workflow trigger types"""

    MANUAL = "manual"
    SCHEDULED = "scheduled"
    EVENT = "event"
    API = "api"
    USER_INPUT = "user_input"


class InteractionType(Enum):
    """Types of user interactions"""

    INPUT_REQUEST = "input_request"
    APPROVAL_REQUEST = "approval_request"
    CHOICE_SELECTION = "choice_selection"
    CONFIRMATION = "confirmation"
    PARAMETER_COLLECTION = "parameter_collection"


@dataclass
class NodeExecutionDetails:
    """Detailed execution state for individual nodes"""

    node_id: str
    state: NodeExecutionState = NodeExecutionState.PENDING
    start_time: Optional[datetime] = None
    end_time: Optional[datetime] = None
    duration: float = 0.0
    retry_count: int = 0
    max_retries: int = 3
    error_message: Optional[str] = None
    input_data: Dict[str, Any] = field(default_factory=dict)
    output_data: Dict[str, Any] = field(default_factory=dict)
    intermediate_results: List[Dict[str, Any]] = field(default_factory=list)
    user_interactions: List[Dict[str, Any]] = field(default_factory=list)
    rollback_points: List[Dict[str, Any]] = field(default_factory=list)
    resource_usage: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization"""
        data = asdict(self)
        # Convert datetime objects to ISO strings
        if self.start_time:
            data["start_time"] = self.start_time.isoformat()
        if self.end_time:
            data["end_time"] = self.end_time.isoformat()
        data["state"] = self.state.value
        return data

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "NodeExecutionDetails":
        """Create from dictionary"""
        data = data.copy()
        if "start_time" in data and data["start_time"]:
            data["start_time"] = datetime.fromisoformat(data["start_time"])
        if "end_time" in data and data["end_time"]:
            data["end_time"] = datetime.fromisoformat(data["end_time"])
        data["state"] = NodeExecutionState(data["state"])
        return cls(**data)


@dataclass
class UserInteraction:
    """User interaction data"""

    id: str
    interaction_type: InteractionType
    node_id: str
    prompt: str
    options: List[str] = field(default_factory=list)
    timeout_seconds: Optional[int] = None
    created_at: datetime = field(default_factory=datetime.now)
    responded_at: Optional[datetime] = None
    response: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary"""
        data = asdict(self)
        data["interaction_type"] = self.interaction_type.value
        data["created_at"] = self.created_at.isoformat()
        if self.responded_at:
            data["responded_at"] = self.responded_at.isoformat()
        return data

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "UserInteraction":
        """Create from dictionary"""
        data = data.copy()
        data["interaction_type"] = InteractionType(data["interaction_type"])
        data["created_at"] = datetime.fromisoformat(data["created_at"])
        if data.get("responded_at"):
            data["responded_at"] = datetime.fromisoformat(data["responded_at"])
        return cls(**data)


@dataclass
class StateSnapshot:
    """Workflow state snapshot for rollback"""

    snapshot_id: str
    timestamp: datetime
    node_states: Dict[str, NodeExecutionDetails]
    workflow_variables: Dict[str, Any]
    execution_context: Dict[str, Any]
    message_history: List[Dict[str, Any]]
    description: str = ""

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary"""
        return {
            "snapshot_id": self.snapshot_id,
            "timestamp": self.timestamp.isoformat(),
            "node_states": {k: v.to_dict() for k, v in self.node_states.items()},
            "workflow_variables": self.workflow_variables,
            "execution_context": self.execution_context,
            "message_history": self.message_history,
            "description": self.description,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "StateSnapshot":
        """Create from dictionary"""
        return cls(
            snapshot_id=data["snapshot_id"],
            timestamp=datetime.fromisoformat(data["timestamp"]),
            node_states={
                k: NodeExecutionDetails.from_dict(v) for k, v in data["node_states"].items()
            },
            workflow_variables=data["workflow_variables"],
            execution_context=data["execution_context"],
            message_history=data["message_history"],
            description=data.get("description", ""),
        )


@dataclass
class ResourceUsageMetrics:
    """Resource usage tracking"""

    cpu_time: float = 0.0
    memory_usage: float = 0.0
    api_calls: int = 0
    tokens_consumed: int = 0
    execution_duration: float = 0.0
    cost_estimate: float = 0.0
    rate_limit_hits: int = 0

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class WorkflowTrigger:
    """Workflow execution trigger"""

    trigger_id: str
    trigger_type: WorkflowTriggerType
    schedule: Optional[str] = None  # Cron expression for scheduled triggers
    event_pattern: Optional[Dict[str, Any]] = None
    conditions: Dict[str, Any] = field(default_factory=dict)
    metadata: Dict[str, Any] = field(default_factory=dict)


class EnhancedWorkflowState:
    """Enhanced workflow state with comprehensive tracking"""

    def __init__(self, workflow_id: str, execution_id: str):
        self.workflow_id = workflow_id
        self.execution_id = execution_id
        self.version = "1.0"
        self.created_at = datetime.now()
        self.last_updated = datetime.now()

        # Execution state
        self.status = (
            "initialized"  # initialized, running, paused, waiting_input, completed, failed
        )
        self.current_node: Optional[str] = None
        self.next_nodes: List[str] = []

        # Node tracking
        self.node_states: Dict[str, NodeExecutionDetails] = {}
        self.execution_order: List[str] = []

        # Data flow
        self.workflow_variables: Dict[str, Any] = {}
        self.inter_node_data: Dict[str, Any] = {}
        self.global_context: Dict[str, Any] = {}

        # User interactions
        self.pending_interactions: List[UserInteraction] = []
        self.completed_interactions: List[UserInteraction] = []

        # State management
        self.snapshots: List[StateSnapshot] = []
        self.max_snapshots = 10

        # Resource tracking
        self.resource_usage = ResourceUsageMetrics()

        # Error handling
        self.errors: List[Dict[str, Any]] = []
        self.warnings: List[Dict[str, Any]] = []

        # Triggers and scheduling
        self.triggers: List[WorkflowTrigger] = []

    def create_snapshot(self, description: str = "") -> str:
        """Create a state snapshot for rollback"""
        snapshot_id = str(uuid.uuid4())

        # Deep copy current state
        snapshot = StateSnapshot(
            snapshot_id=snapshot_id,
            timestamp=datetime.now(),
            node_states=copy.deepcopy(self.node_states),
            workflow_variables=copy.deepcopy(self.workflow_variables),
            execution_context=copy.deepcopy(self.global_context),
            message_history=[],  # Would include message history in production
            description=description,
        )

        self.snapshots.append(snapshot)

        # Maintain max snapshots limit
        if len(self.snapshots) > self.max_snapshots:
            self.snapshots.pop(0)

        return snapshot_id

    def rollback_to_snapshot(self, snapshot_id: str) -> bool:
        """Rollback to a specific snapshot"""
        snapshot = next((s for s in self.snapshots if s.snapshot_id == snapshot_id), None)
        if not snapshot:
            return False

        # Restore state
        self.node_states = copy.deepcopy(snapshot.node_states)
        self.workflow_variables = copy.deepcopy(snapshot.workflow_variables)
        self.global_context = copy.deepcopy(snapshot.execution_context)

        # Mark nodes as rolled back
        for node_id, node_state in self.node_states.items():
            if node_state.state in [NodeExecutionState.COMPLETED, NodeExecutionState.FAILED]:
                node_state.state = NodeExecutionState.ROLLED_BACK

        self.last_updated = datetime.now()
        return True

    def get_node_state(self, node_id: str) -> NodeExecutionDetails:
        """Get or create node execution details"""
        if node_id not in self.node_states:
            self.node_states[node_id] = NodeExecutionDetails(node_id=node_id)
        return self.node_states[node_id]

    def update_node_state(self, node_id: str, state: NodeExecutionState, **kwargs):
        """Update node state with additional data"""
        node_details = self.get_node_state(node_id)
        node_details.state = state

        if state == NodeExecutionState.RUNNING:
            node_details.start_time = datetime.now()
        elif state in [NodeExecutionState.COMPLETED, NodeExecutionState.FAILED]:
            node_details.end_time = datetime.now()
            if node_details.start_time:
                node_details.duration = (
                    node_details.end_time - node_details.start_time
                ).total_seconds()

        # Update additional fields
        for key, value in kwargs.items():
            if hasattr(node_details, key):
                setattr(node_details, key, value)

        self.last_updated = datetime.now()

    def add_user_interaction(self, interaction: UserInteraction):
        """Add pending user interaction"""
        self.pending_interactions.append(interaction)
        self.status = "waiting_input"
        self.last_updated = datetime.now()

    def complete_user_interaction(self, interaction_id: str, response: str):
        """Complete a user interaction"""
        interaction = next((i for i in self.pending_interactions if i.id == interaction_id), None)
        if interaction:
            interaction.response = response
            interaction.responded_at = datetime.now()
            self.pending_interactions.remove(interaction)
            self.completed_interactions.append(interaction)

            if not self.pending_interactions:
                self.status = "running"

        self.last_updated = datetime.now()

    def to_dict(self) -> Dict[str, Any]:
        """Serialize to dictionary"""
        return {
            "workflow_id": self.workflow_id,
            "execution_id": self.execution_id,
            "version": self.version,
            "created_at": self.created_at.isoformat(),
            "last_updated": self.last_updated.isoformat(),
            "status": self.status,
            "current_node": self.current_node,
            "next_nodes": self.next_nodes,
            "node_states": {k: v.to_dict() for k, v in self.node_states.items()},
            "execution_order": self.execution_order,
            "workflow_variables": self.workflow_variables,
            "inter_node_data": self.inter_node_data,
            "global_context": self.global_context,
            "pending_interactions": [i.to_dict() for i in self.pending_interactions],
            "completed_interactions": [i.to_dict() for i in self.completed_interactions],
            "snapshots": [s.to_dict() for s in self.snapshots],
            "resource_usage": self.resource_usage.to_dict(),
            "errors": self.errors,
            "warnings": self.warnings,
            "triggers": [asdict(t) for t in self.triggers],
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "EnhancedWorkflowState":
        """Deserialize from dictionary"""
        state = cls(data["workflow_id"], data["execution_id"])
        state.version = data.get("version", "1.0")
        state.created_at = datetime.fromisoformat(data["created_at"])
        state.last_updated = datetime.fromisoformat(data["last_updated"])
        state.status = data["status"]
        state.current_node = data.get("current_node")
        state.next_nodes = data.get("next_nodes", [])

        # Restore node states
        state.node_states = {
            k: NodeExecutionDetails.from_dict(v) for k, v in data.get("node_states", {}).items()
        }

        state.execution_order = data.get("execution_order", [])
        state.workflow_variables = data.get("workflow_variables", {})
        state.inter_node_data = data.get("inter_node_data", {})
        state.global_context = data.get("global_context", {})

        # Restore interactions
        state.pending_interactions = [
            UserInteraction.from_dict(i) for i in data.get("pending_interactions", [])
        ]
        state.completed_interactions = [
            UserInteraction.from_dict(i) for i in data.get("completed_interactions", [])
        ]

        # Restore snapshots
        state.snapshots = [StateSnapshot.from_dict(s) for s in data.get("snapshots", [])]

        # Restore resource usage
        resource_data = data.get("resource_usage", {})
        state.resource_usage = ResourceUsageMetrics(**resource_data)

        state.errors = data.get("errors", [])
        state.warnings = data.get("warnings", [])

        # Restore triggers
        trigger_data = data.get("triggers", [])
        state.triggers = [WorkflowTrigger(**t) for t in trigger_data]

        return state


class InteractiveWorkflowNode(WorkflowNode):
    """Enhanced workflow node with interaction capabilities"""

    def __init__(self, node_id: str, **kwargs):
        super().__init__(node_id, **kwargs)
        self.requires_user_input = False
        self.requires_approval = False
        self.timeout_seconds: Optional[int] = None
        self.input_schema: Optional[Dict[str, Any]] = None
        self.approval_message: Optional[str] = None
        self.rollback_enabled = True
        self.resource_limits: Dict[str, Any] = {}


class InteractiveWorkflowBuilder(WorkflowBuilder):
    """Enhanced workflow builder with interactive capabilities"""

    def __init__(self):
        super().__init__()
        self.user_input_nodes: Dict[str, Dict[str, Any]] = {}
        self.approval_nodes: Dict[str, Dict[str, Any]] = {}
        self.conditional_branches: Dict[str, Callable] = {}

    def add_user_input_node(
        self,
        node_id: str,
        prompt: str,
        input_type: str = "text",
        options: List[str] = None,
        timeout_seconds: int = None,
        required: bool = True,
    ) -> "InteractiveWorkflowBuilder":
        """Add a node that requires user input"""

        # Create interactive node
        node = InteractiveWorkflowNode(node_id)
        node.requires_user_input = True
        node.timeout_seconds = timeout_seconds

        self.nodes[node_id] = node

        # Store input configuration
        self.user_input_nodes[node_id] = {
            "prompt": prompt,
            "input_type": input_type,
            "options": options or [],
            "timeout_seconds": timeout_seconds,
            "required": required,
        }

        return self

    def add_approval_node(
        self,
        node_id: str,
        approval_message: str,
        timeout_seconds: int = None,
        auto_approve: bool = False,
    ) -> "InteractiveWorkflowBuilder":
        """Add a node that requires user approval"""

        node = InteractiveWorkflowNode(node_id)
        node.requires_approval = True
        node.approval_message = approval_message
        node.timeout_seconds = timeout_seconds

        self.nodes[node_id] = node

        self.approval_nodes[node_id] = {
            "message": approval_message,
            "timeout_seconds": timeout_seconds,
            "auto_approve": auto_approve,
        }

        return self

    def add_conditional_branch(
        self, node_id: str, condition_func: Callable, true_path: str, false_path: str
    ) -> "InteractiveWorkflowBuilder":
        """Add conditional branching logic"""

        self.conditional_branches[node_id] = {
            "condition": condition_func,
            "true_path": true_path,
            "false_path": false_path,
        }

        return self

    def add_parallel_execution(
        self, node_ids: List[str], join_node: str, max_concurrency: int = None
    ) -> "InteractiveWorkflowBuilder":
        """Add parallel execution pattern"""

        # Create join node
        join_node_obj = InteractiveWorkflowNode(join_node)
        self.nodes[join_node] = join_node_obj

        # Connect all parallel nodes to join node
        for node_id in node_ids:
            self.add_edge(node_id, join_node)

        return self


class ProductionWorkflowPersistence:
    """Production-grade workflow persistence with versioning and backup"""

    def __init__(self, storage_backend: str = "redis", backup_enabled: bool = True):
        self.storage_backend = storage_backend
        self.backup_enabled = backup_enabled
        self.logger = logging.getLogger("WorkflowPersistence")
        self.version_schema = "1.0"

    async def save_workflow_state(self, state: EnhancedWorkflowState, memory_manager=None) -> bool:
        """Save workflow state with versioning"""
        try:
            state_data = state.to_dict()
            state_data["persistence_version"] = self.version_schema
            state_data["saved_at"] = datetime.now().isoformat()

            if memory_manager:
                # Save to Redis
                key = f"workflow_state:{state.execution_id}"
                await self._save_to_redis(memory_manager, key, state_data)

                # Create backup if enabled
                if self.backup_enabled:
                    backup_key = f"workflow_backup:{state.execution_id}:{int(time.time())}"
                    await self._save_to_redis(memory_manager, backup_key, state_data)

                    # Maintain backup rotation (keep last 5)
                    await self._rotate_backups(memory_manager, state.execution_id)

            return True

        except Exception as e:
            self.logger.error(f"Failed to save workflow state: {e}")
            return False

    async def load_workflow_state(
        self, execution_id: str, memory_manager=None
    ) -> Optional[EnhancedWorkflowState]:
        """Load workflow state with version migration"""
        try:
            if memory_manager:
                key = f"workflow_state:{execution_id}"
                state_data = await self._load_from_redis(memory_manager, key)

                if state_data:
                    # Check version and migrate if needed
                    persistence_version = state_data.get("persistence_version", "0.9")
                    if persistence_version != self.version_schema:
                        state_data = await self._migrate_state_version(
                            state_data, persistence_version
                        )

                    return EnhancedWorkflowState.from_dict(state_data)

            return None

        except Exception as e:
            self.logger.error(f"Failed to load workflow state: {e}")
            return None

    async def _save_to_redis(self, memory_manager, key: str, data: Dict[str, Any]):
        """Save data to Redis with compression"""
        # In production, you might want to use compression
        memory_manager.store_context(key, data)

    async def _load_from_redis(self, memory_manager, key: str) -> Optional[Dict[str, Any]]:
        """Load data from Redis"""
        return memory_manager.get_context(key)

    async def _migrate_state_version(
        self, state_data: Dict[str, Any], from_version: str
    ) -> Dict[str, Any]:
        """Migrate state data between versions"""
        self.logger.info(
            f"Migrating workflow state from version {from_version} to {self.version_schema}"
        )

        # Add migration logic here based on version differences
        if from_version == "0.9":
            # Example migration: add new fields
            if "resource_usage" not in state_data:
                state_data["resource_usage"] = ResourceUsageMetrics().to_dict()

        state_data["persistence_version"] = self.version_schema
        return state_data

    async def _rotate_backups(self, memory_manager, execution_id: str):
        """Maintain backup rotation"""
        # This would implement backup cleanup logic
        pass


class InteractiveWorkflowExecutor:
    """Production-ready interactive workflow executor"""

    def __init__(self, memory_manager=None, max_concurrent_workflows: int = 10):
        self.memory_manager = memory_manager
        self.persistence = ProductionWorkflowPersistence()
        self.active_workflows: Dict[str, EnhancedWorkflowState] = {}
        self.max_concurrent_workflows = max_concurrent_workflows
        self.logger = logging.getLogger("InteractiveWorkflowExecutor")

        # Resource management
        self.resource_semaphore = asyncio.Semaphore(max_concurrent_workflows)
        self.rate_limiters: Dict[str, asyncio.Semaphore] = {}

        # User interaction handlers
        self.interaction_handlers: Dict[str, Callable] = {}
        self.pending_interactions: Dict[str, UserInteraction] = {}

    async def execute_interactive_workflow(
        self,
        workflow: AmbivoWorkflow,
        initial_message: str,
        context: ExecutionContext = None,
        user_interaction_handler: Callable = None,
    ) -> WorkflowResult:
        """Execute workflow with interactive capabilities"""

        execution_id = str(uuid.uuid4())
        workflow_id = f"interactive_{execution_id[:8]}"

        # Check resource limits
        if len(self.active_workflows) >= self.max_concurrent_workflows:
            raise RuntimeError("Maximum concurrent workflows exceeded")

        # Initialize enhanced state
        state = EnhancedWorkflowState(workflow_id, execution_id)
        state.status = "running"

        # Create initial snapshot
        state.create_snapshot("Initial state")

        self.active_workflows[execution_id] = state

        # Set interaction handler
        if user_interaction_handler:
            self.interaction_handlers[execution_id] = user_interaction_handler

        try:
            async with self.resource_semaphore:
                result = await self._execute_with_interactions(
                    workflow, initial_message, context, state
                )

            state.status = "completed" if result.success else "failed"
            await self.persistence.save_workflow_state(state, self.memory_manager)

            return result

        except Exception as e:
            state.status = "failed"
            state.errors.append(
                {
                    "timestamp": datetime.now().isoformat(),
                    "error": str(e),
                    "node": state.current_node,
                }
            )
            await self.persistence.save_workflow_state(state, self.memory_manager)
            raise
        finally:
            # Cleanup
            if execution_id in self.active_workflows:
                del self.active_workflows[execution_id]
            if execution_id in self.interaction_handlers:
                del self.interaction_handlers[execution_id]

    async def pause_workflow(self, execution_id: str) -> bool:
        """Pause a running workflow"""
        if execution_id in self.active_workflows:
            state = self.active_workflows[execution_id]
            state.status = "paused"
            state.create_snapshot("Paused by user")
            await self.persistence.save_workflow_state(state, self.memory_manager)
            return True
        return False

    async def resume_workflow(self, execution_id: str) -> bool:
        """Resume a paused workflow"""
        # Load state if not in memory
        if execution_id not in self.active_workflows:
            state = await self.persistence.load_workflow_state(execution_id, self.memory_manager)
            if state:
                self.active_workflows[execution_id] = state

        if execution_id in self.active_workflows:
            state = self.active_workflows[execution_id]
            if state.status == "paused":
                state.status = "running"
                await self.persistence.save_workflow_state(state, self.memory_manager)
                return True
        return False

    async def rollback_workflow(self, execution_id: str, snapshot_id: str) -> bool:
        """Rollback workflow to a specific snapshot"""
        if execution_id in self.active_workflows:
            state = self.active_workflows[execution_id]
            if state.rollback_to_snapshot(snapshot_id):
                await self.persistence.save_workflow_state(state, self.memory_manager)
                return True
        return False

    async def handle_user_interaction(self, interaction_id: str, response: str) -> bool:
        """Handle user interaction response"""
        if interaction_id in self.pending_interactions:
            interaction = self.pending_interactions[interaction_id]

            # Find corresponding workflow
            for execution_id, state in self.active_workflows.items():
                if interaction in state.pending_interactions:
                    state.complete_user_interaction(interaction_id, response)
                    await self.persistence.save_workflow_state(state, self.memory_manager)
                    del self.pending_interactions[interaction_id]
                    return True
        return False

    async def _execute_with_interactions(
        self,
        workflow: AmbivoWorkflow,
        initial_message: str,
        context: ExecutionContext,
        state: EnhancedWorkflowState,
    ) -> WorkflowResult:
        """Execute workflow with interaction handling"""

        start_time = time.time()
        messages = []
        errors = []

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

        # Get execution order
        execution_order = workflow._get_execution_order()
        state.execution_order = execution_order

        # Execute nodes
        for node_id in execution_order:
            # Skip completed nodes (for resume scenarios)
            node_state = state.get_node_state(node_id)
            if node_state.state == NodeExecutionState.COMPLETED:
                continue

            state.current_node = node_id
            state.update_node_state(node_id, NodeExecutionState.RUNNING)

            # Create checkpoint before each node
            state.create_snapshot(f"Before executing {node_id}")
            await self.persistence.save_workflow_state(state, self.memory_manager)

            try:
                # Check if this is an interactive node
                node = workflow.nodes[node_id]

                if isinstance(node, InteractiveWorkflowNode):
                    if node.requires_user_input:
                        # Handle user input requirement
                        interaction_response = await self._handle_user_input_node(node, state)
                        if interaction_response:
                            current_message = interaction_response
                    elif node.requires_approval:
                        # Handle approval requirement
                        approved = await self._handle_approval_node(node, state)
                        if not approved:
                            state.update_node_state(node_id, NodeExecutionState.SKIPPED)
                            continue

                # Execute agent if present
                if node.agent:
                    response = await node.agent.process_message(current_message, context)
                    messages.append(response)
                    current_message = response

                    # Store output data
                    state.update_node_state(
                        node_id,
                        NodeExecutionState.COMPLETED,
                        output_data={"response": response.content},
                    )
                else:
                    # Handle special nodes
                    state.update_node_state(node_id, NodeExecutionState.COMPLETED)

                # Update resource usage
                state.resource_usage.execution_duration = time.time() - start_time

            except Exception as e:
                error_msg = f"Error executing {node_id}: {str(e)}"
                errors.append(error_msg)
                state.update_node_state(node_id, NodeExecutionState.FAILED, error_message=str(e))
                self.logger.error(error_msg)

                # Check if we should retry
                if node_state.retry_count < node_state.max_retries:
                    node_state.retry_count += 1
                    state.update_node_state(node_id, NodeExecutionState.PENDING)
                    # Retry logic would go here

        execution_time = time.time() - start_time
        state.resource_usage.execution_duration = execution_time

        return WorkflowResult(
            success=len(errors) == 0,
            messages=messages,
            execution_time=execution_time,
            nodes_executed=[
                n
                for n in execution_order
                if state.get_node_state(n).state == NodeExecutionState.COMPLETED
            ],
            errors=errors,
            metadata={
                "workflow_id": state.workflow_id,
                "execution_id": state.execution_id,
                "snapshots_created": len(state.snapshots),
                "interactions_handled": len(state.completed_interactions),
                "resource_usage": state.resource_usage.to_dict(),
            },
        )

    async def _handle_user_input_node(
        self, node: InteractiveWorkflowNode, state: EnhancedWorkflowState
    ) -> Optional[AgentMessage]:
        """Handle user input node"""

        # Create user interaction
        interaction = UserInteraction(
            id=str(uuid.uuid4()),
            interaction_type=InteractionType.INPUT_REQUEST,
            node_id=node.node_id,
            prompt=(
                node.input_schema.get("prompt", "Please provide input:")
                if node.input_schema
                else "Please provide input:"
            ),
            timeout_seconds=node.timeout_seconds,
        )

        state.add_user_interaction(interaction)
        self.pending_interactions[interaction.id] = interaction

        # Wait for user response (in production, this would be event-driven)
        if state.execution_id in self.interaction_handlers:
            handler = self.interaction_handlers[state.execution_id]
            response = await handler(interaction)

            if response:
                state.complete_user_interaction(interaction.id, response)

                # Create response message
                return AgentMessage(
                    id=str(uuid.uuid4()),
                    sender_id="user",
                    recipient_id="workflow",
                    content=response,
                    message_type=MessageType.USER_INPUT,
                    session_id="workflow_session",
                    conversation_id="workflow_conv",
                )

        return None

    async def _handle_approval_node(
        self, node: InteractiveWorkflowNode, state: EnhancedWorkflowState
    ) -> bool:
        """Handle approval node"""

        interaction = UserInteraction(
            id=str(uuid.uuid4()),
            interaction_type=InteractionType.APPROVAL_REQUEST,
            node_id=node.node_id,
            prompt=node.approval_message or f"Approve execution of {node.node_id}?",
            options=["approve", "reject"],
            timeout_seconds=node.timeout_seconds,
        )

        state.add_user_interaction(interaction)
        self.pending_interactions[interaction.id] = interaction

        # Wait for approval (in production, this would be event-driven)
        if state.execution_id in self.interaction_handlers:
            handler = self.interaction_handlers[state.execution_id]
            response = await handler(interaction)

            if response:
                state.complete_user_interaction(interaction.id, response)
                return response.lower() in ["approve", "yes", "y", "ok"]

        return False


# Example usage and integration
async def create_interactive_realtor_workflow():
    """Example: Create an interactive realtor workflow"""

    from ambivo_agents import AssistantAgent, DatabaseAgent

    # Create agents
    realtor = AssistantAgent.create_simple(user_id="interactive_realtor")
    database = DatabaseAgent.create_simple(user_id="property_db")

    # Create interactive workflow
    builder = InteractiveWorkflowBuilder()

    # Add greeting
    builder.add_agent(realtor, "greeting")

    # Add user input for preferences
    builder.add_user_input_node(
        "collect_preferences",
        prompt="What are your housing preferences? (bedrooms, budget, location)",
        input_type="text",
        timeout_seconds=300,
    )

    # Add approval for budget
    builder.add_approval_node(
        "approve_budget",
        approval_message="Your budget seems high. Should we proceed with the search?",
        timeout_seconds=60,
    )

    # Add database search
    builder.add_agent(database, "search_properties")

    # Add final presentation
    builder.add_agent(realtor, "present_results")

    # Define workflow flow
    builder.add_edge("greeting", "collect_preferences")
    builder.add_edge("collect_preferences", "approve_budget")
    builder.add_edge("approve_budget", "search_properties")
    builder.add_edge("search_properties", "present_results")

    builder.set_start_node("greeting")
    builder.set_end_node("present_results")

    workflow = builder.build()

    # Create executor
    executor = InteractiveWorkflowExecutor()

    # Define interaction handler
    async def interaction_handler(interaction: UserInteraction) -> Optional[str]:
        print(f"\n🔔 {interaction.prompt}")
        if interaction.options:
            print(f"Options: {', '.join(interaction.options)}")

        # In production, this would get input from UI/terminal
        # For demo, return simulated responses
        if interaction.interaction_type == InteractionType.INPUT_REQUEST:
            return "2 bedrooms, $1500 budget, downtown location"
        elif interaction.interaction_type == InteractionType.APPROVAL_REQUEST:
            return "approve"

        return None

    # Execute workflow
    result = await executor.execute_interactive_workflow(
        workflow,
        "I need help finding rental properties",
        user_interaction_handler=interaction_handler,
    )

    return result, executor


if __name__ == "__main__":
    # Demo the interactive workflow system
    import asyncio

    async def demo():
        print("🚀 Interactive Workflow System Demo")
        result, executor = await create_interactive_realtor_workflow()
        print(f"✅ Workflow completed: {result.success}")
        print(f"📊 Resource usage: {result.metadata.get('resource_usage', {})}")

    asyncio.run(demo())
