"""
Agent Coordinator Service - Manages multi-agent coordination and task distribution.

Handles task allocation, conflict resolution, and deadlock prevention.
"""

from typing import Dict, List, Optional, Any, Set
from uuid import UUID, uuid4
from datetime import datetime, timedelta
from dataclasses import dataclass, field
from enum import Enum
import asyncio
import logging
from collections import deque, defaultdict

logger = logging.getLogger(__name__)


class TaskStatus(Enum):
    """Status of coordinated tasks."""

    PENDING = "pending"
    ASSIGNED = "assigned"
    IN_PROGRESS = "in_progress"
    BLOCKED = "blocked"
    COMPLETED = "completed"
    FAILED = "failed"


class ConflictResolutionStrategy(Enum):
    """Strategies for resolving conflicts."""

    PRIORITY = "priority"
    FIRST_COME = "first_come"
    LOAD_BALANCE = "load_balance"
    EXPERTISE = "expertise"
    CONSENSUS = "consensus"


@dataclass
class CoordinatedTask:
    """Represents a task that needs coordination."""

    task_id: UUID = field(default_factory=uuid4)
    name: str = ""
    description: str = ""
    required_capabilities: Set[str] = field(default_factory=set)
    assigned_agents: List[UUID] = field(default_factory=list)
    dependencies: List[UUID] = field(default_factory=list)
    priority: int = 1
    status: TaskStatus = TaskStatus.PENDING
    created_at: datetime = field(default_factory=datetime.utcnow)
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    result: Optional[Dict[str, Any]] = None
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class AgentWorkload:
    """Tracks agent workload for load balancing."""

    agent_id: UUID
    current_tasks: List[UUID] = field(default_factory=list)
    completed_tasks: int = 0
    failed_tasks: int = 0
    avg_completion_time: float = 0.0
    capabilities: Set[str] = field(default_factory=set)
    availability: float = 1.0  # 0-1 scale


class Coordinator:
    """Coordinates multiple agents for complex tasks."""

    def __init__(
        self, max_concurrent_tasks: int = 10, task_timeout: timedelta = timedelta(hours=1)
    ) -> None:
        """Initialize coordinator."""
        self.max_concurrent_tasks = max_concurrent_tasks
        self.task_timeout = task_timeout
        self.task_queue: deque[CoordinatedTask] = deque()
        self.active_tasks: Dict[UUID, CoordinatedTask] = {}
        self.completed_tasks: Dict[UUID, CoordinatedTask] = {}
        self.agent_workloads: Dict[UUID, AgentWorkload] = {}
        self.task_dependencies: Dict[UUID, Set[UUID]] = defaultdict(set)
        self.resource_locks: Dict[str, UUID] = {}  # resource -> agent_id
        self._coordination_loop_task = None

    async def submit_task(self, task: CoordinatedTask) -> UUID:
        """Submit a task for coordination."""
        # Validate task
        if not task.name:
            raise ValueError("Task must have a name")

        # Add to queue
        self.task_queue.append(task)

        # Track dependencies
        if task.dependencies:
            self.task_dependencies[task.task_id] = set(task.dependencies)

        logger.info(f"Submitted task {task.task_id}: {task.name}")

        # Start coordination loop if not running
        if not self._coordination_loop_task:
            self._coordination_loop_task = asyncio.create_task(self._coordination_loop())

        return task.task_id

    async def assign_task(
        self,
        task: CoordinatedTask,
        strategy: ConflictResolutionStrategy = ConflictResolutionStrategy.LOAD_BALANCE,
    ) -> List[UUID]:
        """Assign task to agents based on strategy."""
        eligible_agents = self._find_eligible_agents(task)

        if not eligible_agents:
            logger.warning(f"No eligible agents for task {task.task_id}")
            task.status = TaskStatus.BLOCKED
            return []

        # Apply assignment strategy
        if strategy == ConflictResolutionStrategy.PRIORITY:
            assigned = self._assign_by_priority(task, eligible_agents)
        elif strategy == ConflictResolutionStrategy.FIRST_COME:
            assigned = self._assign_first_available(task, eligible_agents)
        elif strategy == ConflictResolutionStrategy.LOAD_BALANCE:
            assigned = self._assign_by_load_balance(task, eligible_agents)
        elif strategy == ConflictResolutionStrategy.EXPERTISE:
            assigned = self._assign_by_expertise(task, eligible_agents)
        else:
            assigned = self._assign_by_consensus(task, eligible_agents)

        task.assigned_agents = assigned
        task.status = TaskStatus.ASSIGNED
        task.started_at = datetime.utcnow()

        # Update workloads
        for agent_id in assigned:
            if agent_id in self.agent_workloads:
                self.agent_workloads[agent_id].current_tasks.append(task.task_id)

        self.active_tasks[task.task_id] = task

        logger.info(f"Assigned task {task.task_id} to agents: {assigned}")
        return assigned

    def _find_eligible_agents(self, task: CoordinatedTask) -> List[UUID]:
        """Find agents eligible for a task."""
        eligible = []

        for agent_id, workload in self.agent_workloads.items():
            # Check capabilities
            if task.required_capabilities:
                if not task.required_capabilities.issubset(workload.capabilities):
                    continue

            # Check availability
            if workload.availability < 0.2:
                continue

            # Check workload
            if len(workload.current_tasks) >= self.max_concurrent_tasks:
                continue

            eligible.append(agent_id)

        return eligible

    def _assign_by_priority(self, task: CoordinatedTask, eligible_agents: List[UUID]) -> List[UUID]:
        """Assign based on task priority."""
        # Sort by agent performance
        sorted_agents = sorted(
            eligible_agents,
            key=lambda a: (
                self.agent_workloads[a].completed_tasks
                / max(1, self.agent_workloads[a].failed_tasks)
            ),
            reverse=True,
        )

        # Assign to best performer for high priority
        if task.priority > 3:
            return sorted_agents[:1]
        else:
            return sorted_agents[:2]

    def _assign_first_available(
        self, task: CoordinatedTask, eligible_agents: List[UUID]
    ) -> List[UUID]:
        """Assign to first available agent."""
        return eligible_agents[:1] if eligible_agents else []

    def _assign_by_load_balance(
        self, task: CoordinatedTask, eligible_agents: List[UUID]
    ) -> List[UUID]:
        """Assign based on load balancing."""
        # Sort by current workload (ascending)
        sorted_agents = sorted(
            eligible_agents, key=lambda a: len(self.agent_workloads[a].current_tasks)
        )

        return sorted_agents[:1] if sorted_agents else []

    def _assign_by_expertise(
        self, task: CoordinatedTask, eligible_agents: List[UUID]
    ) -> List[UUID]:
        """Assign based on agent expertise."""
        # Score agents by capability match
        agent_scores = {}

        for agent_id in eligible_agents:
            workload = self.agent_workloads[agent_id]
            score = len(task.required_capabilities & workload.capabilities)
            agent_scores[agent_id] = score

        # Sort by score (descending)
        sorted_agents = sorted(agent_scores.keys(), key=lambda a: agent_scores[a], reverse=True)

        return sorted_agents[:1] if sorted_agents else []

    def _assign_by_consensus(
        self, task: CoordinatedTask, eligible_agents: List[UUID]
    ) -> List[UUID]:
        """Assign requiring consensus (multiple agents)."""
        # For consensus, assign to multiple agents
        num_agents = min(3, len(eligible_agents))
        return eligible_agents[:num_agents]

    async def complete_task(self, task_id: UUID, result: Dict[str, Any]) -> bool:
        """Mark a task as completed."""
        if task_id not in self.active_tasks:
            logger.warning(f"Task {task_id} not found in active tasks")
            return False

        task = self.active_tasks[task_id]
        task.status = TaskStatus.COMPLETED
        task.completed_at = datetime.utcnow()
        task.result = result

        # Update workloads
        for agent_id in task.assigned_agents:
            if agent_id in self.agent_workloads:
                workload = self.agent_workloads[agent_id]
                if task_id in workload.current_tasks:
                    workload.current_tasks.remove(task_id)
                workload.completed_tasks += 1

                # Update average completion time
                if task.started_at:
                    completion_time = (task.completed_at - task.started_at).total_seconds()
                    workload.avg_completion_time = (
                        workload.avg_completion_time * (workload.completed_tasks - 1)
                        + completion_time
                    ) / workload.completed_tasks

        # Move to completed
        self.completed_tasks[task_id] = task
        del self.active_tasks[task_id]

        # Unblock dependent tasks
        self._unblock_dependent_tasks(task_id)

        logger.info(f"Completed task {task_id}")
        return True

    def _unblock_dependent_tasks(self, completed_task_id: UUID):
        """Unblock tasks dependent on completed task."""
        for task_id, dependencies in list(self.task_dependencies.items()):
            if completed_task_id in dependencies:
                dependencies.remove(completed_task_id)
                if not dependencies:
                    del self.task_dependencies[task_id]
                    logger.info(f"Unblocked task {task_id}")

    async def fail_task(self, task_id: UUID, error: str) -> bool:
        """Mark a task as failed."""
        if task_id not in self.active_tasks:
            return False

        task = self.active_tasks[task_id]
        task.status = TaskStatus.FAILED
        task.completed_at = datetime.utcnow()
        task.result = {"error": error}

        # Update workloads
        for agent_id in task.assigned_agents:
            if agent_id in self.agent_workloads:
                workload = self.agent_workloads[agent_id]
                if task_id in workload.current_tasks:
                    workload.current_tasks.remove(task_id)
                workload.failed_tasks += 1

        # Move to completed (with failed status)
        self.completed_tasks[task_id] = task
        del self.active_tasks[task_id]

        logger.error(f"Failed task {task_id}: {error}")
        return True

    def detect_deadlock(self) -> List[UUID]:
        """Detect circular dependencies (deadlock)."""
        visited = set()
        rec_stack = set()
        deadlocked = []

        def has_cycle(task_id: UUID) -> bool:
            visited.add(task_id)
            rec_stack.add(task_id)

            for dep in self.task_dependencies.get(task_id, []):
                if dep not in visited:
                    if has_cycle(dep):
                        return True
                elif dep in rec_stack:
                    return True

            rec_stack.remove(task_id)
            return False

        for task_id in self.task_dependencies:
            if task_id not in visited and has_cycle(task_id):
                deadlocked.append(task_id)

        if deadlocked:
            logger.warning(f"Deadlock detected in tasks: {deadlocked}")

        return deadlocked

    async def resolve_conflict(
        self,
        resource: str,
        requesting_agents: List[UUID],
        strategy: ConflictResolutionStrategy = ConflictResolutionStrategy.PRIORITY,
    ) -> UUID:
        """Resolve resource conflict between agents."""
        if not requesting_agents:
            return None

        # Check if resource is already locked
        if resource in self.resource_locks:
            current_owner = self.resource_locks[resource]
            if current_owner in requesting_agents:
                return current_owner

        # Apply resolution strategy
        if strategy == ConflictResolutionStrategy.PRIORITY:
            # Choose agent with highest priority task
            winner = max(
                requesting_agents,
                key=lambda a: max(
                    (
                        self.active_tasks[t].priority
                        for t in self.agent_workloads[a].current_tasks
                        if t in self.active_tasks
                    ),
                    default=0,
                ),
            )
        else:
            # Default to first requester
            winner = requesting_agents[0]

        # Lock resource
        self.resource_locks[resource] = winner
        logger.info(f"Resolved conflict for resource {resource}: assigned to {winner}")

        return winner

    def release_resource(self, resource: str, agent_id: UUID) -> bool:
        """Release a resource lock."""
        if resource in self.resource_locks and self.resource_locks[resource] == agent_id:
            del self.resource_locks[resource]
            logger.info(f"Released resource {resource} from agent {agent_id}")
            return True
        return False

    def register_agent(self, agent_id: UUID, capabilities: Set[str]):
        """Register an agent with the coordinator."""
        if agent_id not in self.agent_workloads:
            self.agent_workloads[agent_id] = AgentWorkload(
                agent_id=agent_id, capabilities=capabilities
            )
            logger.info(f"Registered agent {agent_id} with capabilities: {capabilities}")

    def unregister_agent(self, agent_id: UUID):
        """Unregister an agent from the coordinator."""
        if agent_id in self.agent_workloads:
            workload = self.agent_workloads[agent_id]

            # Reassign active tasks
            for task_id in workload.current_tasks:
                if task_id in self.active_tasks:
                    task = self.active_tasks[task_id]
                    task.assigned_agents.remove(agent_id)
                    if not task.assigned_agents:
                        task.status = TaskStatus.PENDING
                        self.task_queue.append(task)

            del self.agent_workloads[agent_id]
            logger.info(f"Unregistered agent {agent_id}")

    async def _coordination_loop(self):
        """Main coordination loop."""
        while True:
            try:
                # Process pending tasks
                if self.task_queue:
                    task = self.task_queue.popleft()

                    # Check dependencies
                    if task.task_id in self.task_dependencies:
                        if self.task_dependencies[task.task_id]:
                            # Still has dependencies, requeue
                            self.task_queue.append(task)
                        else:
                            # Dependencies met, assign task
                            await self.assign_task(task)
                    else:
                        # No dependencies, assign immediately
                        await self.assign_task(task)

                # Check for deadlocks
                deadlocked = self.detect_deadlock()
                if deadlocked:
                    # Break deadlock by failing one task
                    await self.fail_task(deadlocked[0], "Deadlock detected")

                # Check for timeouts
                now = datetime.utcnow()
                for task_id, task in list(self.active_tasks.items()):
                    if task.started_at:
                        elapsed = now - task.started_at
                        if elapsed > self.task_timeout:
                            await self.fail_task(task_id, "Task timeout")

                await asyncio.sleep(1)

            except Exception as e:
                logger.error(f"Error in coordination loop: {e}")
                await asyncio.sleep(5)
