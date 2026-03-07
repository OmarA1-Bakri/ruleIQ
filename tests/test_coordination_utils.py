"""Unit tests for multi-agent coordination utilities."""

import json
import os
import tempfile
import pytest
from pathlib import Path
from unittest.mock import patch, MagicMock

from utils.coordination_utils import (
    CoordinationManager,
    TaskStatus,
    CoordinationError,
    create_coordination_session,
    update_task_status,
    aggregate_results,
    wait_for_task_completion,
)


class TestCoordinationManager:
    """Test cases for CoordinationManager class."""

    def setup_method(self):
        """Set up test fixtures."""
        self.temp_dir = tempfile.mkdtemp()
        self.session_id = "test_session_123"
        self.manager = CoordinationManager(self.session_id, base_dir=self.temp_dir)

    def teardown_method(self):
        """Clean up test fixtures."""
        import shutil

        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_initialization(self):
        """Test CoordinationManager initialization."""
        assert self.manager.session_id == self.session_id
        assert self.manager.base_dir == Path(self.temp_dir)
        assert self.manager.session_dir.exists()
        assert self.manager.status_file.exists()
        assert self.manager.results_file.exists()

    def test_create_task(self):
        """Test task creation."""
        task_id = "task_1"
        task_config = {"mode": "code", "description": "Test task", "dependencies": []}

        self.manager.create_task(task_id, task_config)

        # Verify task was added to status
        status = self.manager.get_status()
        assert task_id in status["tasks"]
        assert status["tasks"][task_id]["status"] == TaskStatus.PENDING
        assert status["tasks"][task_id]["config"] == task_config

    def test_update_task_status(self):
        """Test task status updates."""
        task_id = "task_1"
        self.manager.create_task(task_id, {"mode": "code"})

        # Update to running
        self.manager.update_task_status(task_id, TaskStatus.RUNNING)
        status = self.manager.get_status()
        assert status["tasks"][task_id]["status"] == TaskStatus.RUNNING

        # Update to completed with result
        result = {"output": "test result"}
        self.manager.update_task_status(task_id, TaskStatus.COMPLETED, result)
        status = self.manager.get_status()
        assert status["tasks"][task_id]["status"] == TaskStatus.COMPLETED
        assert status["tasks"][task_id]["result"] == result

    def test_task_dependencies(self):
        """Test task dependency management."""
        # Create dependent tasks
        task1_id = "task_1"
        task2_id = "task_2"

        self.manager.create_task(task1_id, {"mode": "code"})
        self.manager.create_task(task2_id, {"mode": "test", "dependencies": [task1_id]})

        # Check if task2 can start (should be blocked by task1)
        assert not self.manager.can_task_start(task2_id)

        # Complete task1
        self.manager.update_task_status(task1_id, TaskStatus.COMPLETED)

        # Now task2 should be able to start
        assert self.manager.can_task_start(task2_id)

    def test_error_handling(self):
        """Test error handling in task execution."""
        task_id = "task_1"
        self.manager.create_task(task_id, {"mode": "code"})

        error_msg = "Task failed"
        self.manager.update_task_status(task_id, TaskStatus.FAILED, error=error_msg)

        status = self.manager.get_status()
        assert status["tasks"][task_id]["status"] == TaskStatus.FAILED
        assert status["tasks"][task_id]["error"] == error_msg

    def test_result_aggregation(self):
        """Test result aggregation from multiple tasks."""
        # Create and complete multiple tasks
        tasks = ["task_1", "task_2", "task_3"]
        for i, task_id in enumerate(tasks):
            self.manager.create_task(task_id, {"mode": "code"})
            self.manager.update_task_status(
                task_id, TaskStatus.COMPLETED, result={"output": f"result_{i}"}
            )

        # Aggregate results
        aggregated = self.manager.aggregate_results()
        assert len(aggregated) == 3
        assert aggregated[0]["output"] == "result_0"
        assert aggregated[1]["output"] == "result_1"
        assert aggregated[2]["output"] == "result_2"


class TestCoordinationUtilities:
    """Test cases for coordination utility functions."""

    def setup_method(self):
        """Set up test fixtures."""
        self.temp_dir = tempfile.mkdtemp()

    def teardown_method(self):
        """Clean up test fixtures."""
        import shutil

        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_create_coordination_session(self):
        """Test session creation utility."""
        session_id = "test_session"
        tasks_config = {
            "task_1": {"mode": "code", "description": "First task"},
            "task_2": {"mode": "test", "description": "Second task", "dependencies": ["task_1"]},
        }

        manager = create_coordination_session(session_id, tasks_config, base_dir=self.temp_dir)

        assert manager.session_id == session_id
        status = manager.get_status()
        assert len(status["tasks"]) == 2
        assert "task_1" in status["tasks"]
        assert "task_2" in status["tasks"]

    def test_update_task_status_utility(self):
        """Test update_task_status utility function."""
        session_id = "test_session"
        manager = CoordinationManager(session_id, base_dir=self.temp_dir)
        manager.create_task("task_1", {"mode": "code"})

        # Test utility function
        update_task_status(session_id, "task_1", TaskStatus.RUNNING, base_dir=self.temp_dir)

        status = manager.get_status()
        assert status["tasks"]["task_1"]["status"] == TaskStatus.RUNNING

    def test_wait_for_task_completion(self):
        """Test waiting for task completion."""
        session_id = "test_session"
        manager = CoordinationManager(session_id, base_dir=self.temp_dir)
        manager.create_task("task_1", {"mode": "code"})

        # Task should timeout since it's not completed
        with pytest.raises(TimeoutError):
            wait_for_task_completion(session_id, "task_1", timeout=0.1, base_dir=self.temp_dir)

        # Complete the task
        manager.update_task_status("task_1", TaskStatus.COMPLETED)

        # Now wait should succeed
        result = wait_for_task_completion(session_id, "task_1", timeout=1.0, base_dir=self.temp_dir)
        assert result["status"] == TaskStatus.COMPLETED

    def test_aggregate_results_utility(self):
        """Test aggregate_results utility function."""
        session_id = "test_session"
        manager = CoordinationManager(session_id, base_dir=self.temp_dir)

        # Create and complete tasks
        for i in range(3):
            task_id = f"task_{i}"
            manager.create_task(task_id, {"mode": "code"})
            manager.update_task_status(task_id, TaskStatus.COMPLETED, result={"data": f"value_{i}"})

        # Test utility function
        results = aggregate_results(session_id, base_dir=self.temp_dir)
        assert len(results) == 3
        assert results[0]["data"] == "value_0"
        assert results[1]["data"] == "value_1"
        assert results[2]["data"] == "value_2"


class TestErrorConditions:
    """Test error conditions and edge cases."""

    def setup_method(self):
        """Set up test fixtures."""
        self.temp_dir = tempfile.mkdtemp()

    def teardown_method(self):
        """Clean up test fixtures."""
        import shutil

        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_invalid_session(self):
        """Test handling of invalid session IDs."""
        with pytest.raises(CoordinationError):
            CoordinationManager("invalid_session", base_dir=self.temp_dir)

    def test_duplicate_task_creation(self):
        """Test handling of duplicate task creation."""
        manager = CoordinationManager("test_session", base_dir=self.temp_dir)
        manager.create_task("task_1", {"mode": "code"})

        with pytest.raises(CoordinationError):
            manager.create_task("task_1", {"mode": "test"})

    def test_invalid_task_status_update(self):
        """Test handling of invalid task status updates."""
        manager = CoordinationManager("test_session", base_dir=self.temp_dir)

        with pytest.raises(CoordinationError):
            manager.update_task_status("nonexistent_task", TaskStatus.RUNNING)

    def test_circular_dependencies(self):
        """Test detection of circular dependencies."""
        manager = CoordinationManager("test_session", base_dir=self.temp_dir)

        # Create tasks with circular dependency
        manager.create_task("task_1", {"mode": "code", "dependencies": ["task_2"]})
        manager.create_task("task_2", {"mode": "test", "dependencies": ["task_1"]})

        # Should detect circular dependency
        assert not manager.can_task_start("task_1")
        assert not manager.can_task_start("task_2")
