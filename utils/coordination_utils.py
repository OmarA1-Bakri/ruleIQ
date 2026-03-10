"""Multi-agent coordination utilities for parallel task execution.

This module provides file-based coordination mechanisms for managing
parallel execution of multiple Kilo Code modes working together on
complex tasks.
"""

import json
import time
import uuid
from dataclasses import dataclass, asdict
from enum import Enum
from pathlib import Path
from typing import Dict, List, Any, Optional, Union
from datetime import datetime


class TaskStatus(Enum):
    """Enumeration of possible task states."""

    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class CoordinationError(Exception):
    """Exception raised for coordination-related errors."""

    pass


@dataclass
class TaskInfo:
    """Information about a coordination task."""

    task_id: str
    config: Dict[str, Any]
    status: TaskStatus
    created_at: datetime
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    result: Optional[Any] = None
    error: Optional[str] = None
    dependencies: Optional[List[str]] = None

    def __post_init__(self):
        """Initialize dependencies list if not provided."""
        if self.dependencies is None:
            self.dependencies = []

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        data = asdict(self)
        # Convert enums and datetime to serializable format
        data["status"] = self.status.value
        data["created_at"] = self.created_at.isoformat()
        if self.started_at:
            data["started_at"] = self.started_at.isoformat()
        if self.completed_at:
            data["completed_at"] = self.completed_at.isoformat()
        return data

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "TaskInfo":
        """Create TaskInfo from dictionary."""
        # Convert back from serialized format
        data["status"] = TaskStatus(data["status"])
        data["created_at"] = datetime.fromisoformat(data["created_at"])
        if data.get("started_at"):
            data["started_at"] = datetime.fromisoformat(data["started_at"])
        if data.get("completed_at"):
            data["completed_at"] = datetime.fromisoformat(data["completed_at"])
        return cls(**data)


@dataclass
class CoordinationStatus:
    """Overall status of a coordination session."""

    session_id: str
    tasks: Dict[str, TaskInfo]
    created_at: datetime
    updated_at: datetime

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return {
            "session_id": self.session_id,
            "tasks": {task_id: task.to_dict() for task_id, task in self.tasks.items()},
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat(),
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "CoordinationStatus":
        """Create CoordinationStatus from dictionary."""
        return cls(
            session_id=data["session_id"],
            tasks={
                task_id: TaskInfo.from_dict(task_data)
                for task_id, task_data in data["tasks"].items()
            },
            created_at=datetime.fromisoformat(data["created_at"]),
            updated_at=datetime.fromisoformat(data["updated_at"]),
        )


class CoordinationManager:
    """Manages coordination of parallel tasks using file-based communication."""

    def __init__(self, session_id: str, base_dir: Union[str, Path] = ".coordination") -> None:
        """Initialize coordination manager.

        Args:
            session_id: Unique identifier for the coordination session
            base_dir: Base directory for coordination files
        """
        self.session_id = session_id
        self.base_dir = Path(base_dir)
        self.session_dir = self.base_dir / session_id
        self.status_file = self.session_dir / "status.json"
        self.results_file = self.session_dir / "results.json"

        # Create session directory if it doesn't exist
        self.session_dir.mkdir(parents=True, exist_ok=True)

        # Initialize or load status
        if self.status_file.exists():
            self._load_status()
        else:
            self.status = CoordinationStatus(
                session_id=session_id,
                tasks={},
                created_at=datetime.now(),
                updated_at=datetime.now(),
            )
            self._save_status()

        # Initialize results file if it doesn't exist
        if not self.results_file.exists():
            self._save_results([])

    def _load_status(self) -> None:
        """Load coordination status from file."""
        try:
            with open(self.status_file, "r") as f:
                data = json.load(f)
            self.status = CoordinationStatus.from_dict(data)
        except (json.JSONDecodeError, KeyError) as e:
            raise CoordinationError(f"Failed to load coordination status: {e}")

    def _save_status(self) -> None:
        """Save coordination status to file."""
        try:
            self.status.updated_at = datetime.now()
            with open(self.status_file, "w") as f:
                json.dump(self.status.to_dict(), f, indent=2)
        except Exception as e:
            raise CoordinationError(f"Failed to save coordination status: {e}")

    def _load_results(self) -> List[Dict[str, Any]]:
        """Load results from file."""
        try:
            with open(self.results_file, "r") as f:
                return json.load(f)
        except (json.JSONDecodeError, FileNotFoundError):
            return []

    def _save_results(self, results: List[Dict[str, Any]]) -> None:
        """Save results to file."""
        try:
            with open(self.results_file, "w") as f:
                json.dump(results, f, indent=2)
        except Exception as e:
            raise CoordinationError(f"Failed to save results: {e}")

    def create_task(self, task_id: str, config: Dict[str, Any]) -> None:
        """Create a new task in the coordination session.

        Args:
            task_id: Unique identifier for the task
            config: Task configuration including mode, description, dependencies, etc.
        """
        if task_id in self.status.tasks:
            raise CoordinationError(f"Task {task_id} already exists")

        dependencies = config.get("dependencies", [])

        task = TaskInfo(
            task_id=task_id,
            config=config,
            status=TaskStatus.PENDING,
            created_at=datetime.now(),
            dependencies=dependencies,
        )

        self.status.tasks[task_id] = task
        self._save_status()

    def update_task_status(
        self,
        task_id: str,
        status: TaskStatus,
        result: Optional[Any] = None,
        error: Optional[str] = None,
    ) -> None:
        """Update the status of a task.

        Args:
            task_id: ID of the task to update
            status: New status for the task
            result: Result data if task completed successfully
            error: Error message if task failed
        """
        if task_id not in self.status.tasks:
            raise CoordinationError(f"Task {task_id} does not exist")

        task = self.status.tasks[task_id]
        task.status = status

        if status == TaskStatus.RUNNING and not task.started_at:
            task.started_at = datetime.now()
        elif status in (TaskStatus.COMPLETED, TaskStatus.FAILED, TaskStatus.CANCELLED):
            task.completed_at = datetime.now()
            if result is not None:
                task.result = result
            if error is not None:
                task.error = error

        self._save_status()

    def get_status(self) -> Dict[str, Any]:
        """Get current coordination status."""
        return self.status.to_dict()

    def can_task_start(self, task_id: str) -> bool:
        """Check if a task can start based on its dependencies.

        Args:
            task_id: ID of the task to check

        Returns:
            True if all dependencies are completed successfully
        """
        if task_id not in self.status.tasks:
            return False

        task = self.status.tasks[task_id]

        # Check if all dependencies are completed
        for dep_id in task.dependencies:
            if dep_id not in self.status.tasks:
                return False
            dep_task = self.status.tasks[dep_id]
            if dep_task.status != TaskStatus.COMPLETED:
                return False

        return True

    def get_ready_tasks(self) -> List[str]:
        """Get list of tasks that are ready to start.

        Returns:
            List of task IDs that can start execution
        """
        return [
            task_id
            for task_id in self.status.tasks
            if (
                self.status.tasks[task_id].status == TaskStatus.PENDING
                and self.can_task_start(task_id)
            )
        ]

    def aggregate_results(self) -> List[Dict[str, Any]]:
        """Aggregate results from all completed tasks.

        Returns:
            List of task results in dependency order
        """
        completed_tasks = [
            (task_id, task)
            for task_id, task in self.status.tasks.items()
            if task.status == TaskStatus.COMPLETED
        ]

        # Sort by completion time to maintain some ordering
        completed_tasks.sort(key=lambda x: x[1].completed_at or datetime.min)

        results = []
        for task_id, task in completed_tasks:
            result_entry = {
                "task_id": task_id,
                "config": task.config,
                "result": task.result,
                "completed_at": task.completed_at.isoformat() if task.completed_at else None,
            }
            results.append(result_entry)

        # Save aggregated results
        self._save_results(results)

        return results

    def is_session_complete(self) -> bool:
        """Check if the coordination session is complete.

        Returns:
            True if all tasks are either completed or failed
        """
        for task in self.status.tasks.values():
            if task.status not in (TaskStatus.COMPLETED, TaskStatus.FAILED, TaskStatus.CANCELLED):
                return False
        return True


# Utility functions for easier usage


def create_coordination_session(
    session_id: Optional[str] = None,
    tasks_config: Optional[Union[Dict[str, Dict[str, Any]], List[Dict[str, Any]]]] = None,
    base_dir: Union[str, Path] = ".coordination",
) -> CoordinationManager:
    """Create a new coordination session with initial tasks.

    Args:
        session_id: Session ID (generated if not provided)
        tasks_config: Dictionary of task_id -> task_config or a list of
            {"task_id": ..., "config": ...} entries
        base_dir: Base directory for coordination files

    Returns:
        CoordinationManager instance
    """
    if session_id is None:
        session_id = f"session_{uuid.uuid4().hex[:8]}"

    manager = CoordinationManager(session_id, base_dir)

    if tasks_config:
        if isinstance(tasks_config, dict):
            for task_id, config in tasks_config.items():
                manager.create_task(task_id, config)
        else:
            for task in tasks_config:
                task_id = task.get("task_id")
                if not task_id:
                    raise CoordinationError("Each task entry must include a task_id")
                manager.create_task(task_id, task.get("config", {}))

    return manager


def update_task_status(
    session_id: str,
    task_id: str,
    status: TaskStatus,
    result: Optional[Any] = None,
    error: Optional[str] = None,
    base_dir: Union[str, Path] = ".coordination",
) -> None:
    """Update task status in a coordination session.

    Args:
        session_id: ID of the coordination session
        task_id: ID of the task to update
        status: New status
        result: Result data (for completed tasks)
        error: Error message (for failed tasks)
        base_dir: Base directory for coordination files
    """
    manager = CoordinationManager(session_id, base_dir)
    manager.update_task_status(task_id, status, result, error)


def aggregate_results(
    session_id: str, base_dir: Union[str, Path] = ".coordination"
) -> List[Dict[str, Any]]:
    """Aggregate results from a coordination session.

    Args:
        session_id: ID of the coordination session
        base_dir: Base directory for coordination files

    Returns:
        List of aggregated results
    """
    manager = CoordinationManager(session_id, base_dir)
    return manager.aggregate_results()


def wait_for_task_completion(
    session_id: str,
    task_id: str,
    timeout: float = 300.0,
    poll_interval: float = 1.0,
    base_dir: Union[str, Path] = ".coordination",
) -> Dict[str, Any]:
    """Wait for a task to complete.

    Args:
        session_id: ID of the coordination session
        task_id: ID of the task to wait for
        timeout: Maximum time to wait in seconds
        poll_interval: How often to check status in seconds
        base_dir: Base directory for coordination files

    Returns:
        Task completion information

    Raises:
        TimeoutError: If task doesn't complete within timeout
    """
    manager = CoordinationManager(session_id, base_dir)
    start_time = time.time()

    while time.time() - start_time < timeout:
        if task_id not in manager.status.tasks:
            raise CoordinationError(f"Task {task_id} does not exist")

        task = manager.status.tasks[task_id]
        if task.status in (TaskStatus.COMPLETED, TaskStatus.FAILED, TaskStatus.CANCELLED):
            return {
                "task_id": task_id,
                "status": task.status.value,
                "result": task.result,
                "error": task.error,
                "completed_at": task.completed_at.isoformat() if task.completed_at else None,
            }

        time.sleep(poll_interval)
        manager._load_status()  # Refresh status

    raise TimeoutError(f"Task {task_id} did not complete within {timeout} seconds")
