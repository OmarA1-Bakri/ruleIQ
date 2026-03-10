"""Tests for utils/coordination_utils.py - Multi-agent coordination utilities."""

import os
import json
import pytest
import shutil
import tempfile
from datetime import datetime
from pathlib import Path

from utils.coordination_utils import (
    TaskStatus,
    CoordinationError,
    TaskInfo,
    CoordinationStatus,
    CoordinationManager,
    create_coordination_session,
    update_task_status,
    aggregate_results,
)


# --- TaskStatus Enum ---
class TestTaskStatus:
    def test_all_values(self):
        expected = {"PENDING", "RUNNING", "COMPLETED", "FAILED", "CANCELLED"}
        assert {ts.name for ts in TaskStatus} == expected


# --- TaskInfo Dataclass ---
class TestTaskInfo:
    def test_creation(self):
        now = datetime.now()
        ti = TaskInfo(
            task_id="t1",
            config={"key": "value"},
            status=TaskStatus.PENDING,
            created_at=now,
        )
        assert ti.task_id == "t1"
        assert ti.status == TaskStatus.PENDING
        assert ti.dependencies == [] or ti.dependencies is not None

    def test_to_dict(self):
        ti = TaskInfo(
            task_id="t2",
            config={"a": 1},
            status=TaskStatus.RUNNING,
            created_at=datetime.now(),
        )
        d = ti.to_dict()
        assert d["task_id"] == "t2"
        assert "status" in d
        assert "created_at" in d

    def test_from_dict(self):
        now = datetime.now()
        original = TaskInfo(
            task_id="t3",
            config={"b": 2},
            status=TaskStatus.COMPLETED,
            created_at=now,
            result={"output": "done"},
        )
        d = original.to_dict()
        restored = TaskInfo.from_dict(d)
        assert restored.task_id == "t3"
        assert restored.result == {"output": "done"}


# --- CoordinationStatus Dataclass ---
class TestCoordinationStatus:
    def test_creation(self):
        now = datetime.now()
        cs = CoordinationStatus(
            session_id="s1",
            tasks={},
            created_at=now,
            updated_at=now,
        )
        assert cs.session_id == "s1"

    def test_to_dict(self):
        now = datetime.now()
        cs = CoordinationStatus(
            session_id="s2",
            tasks={},
            created_at=now,
            updated_at=now,
        )
        d = cs.to_dict()
        assert d["session_id"] == "s2"

    def test_from_dict(self):
        now = datetime.now()
        cs = CoordinationStatus(
            session_id="s3",
            tasks={},
            created_at=now,
            updated_at=now,
        )
        d = cs.to_dict()
        restored = CoordinationStatus.from_dict(d)
        assert restored.session_id == "s3"


# --- CoordinationManager ---
class TestCoordinationManager:
    @pytest.fixture
    def tmp_dir(self, tmp_path):
        """Provide a clean temp directory for coordination files."""
        return str(tmp_path / "coordination")

    def test_create_manager(self, tmp_dir):
        cm = CoordinationManager(session_id="test_sess", base_dir=tmp_dir)
        assert cm.session_id == "test_sess"

    def test_create_task(self, tmp_dir):
        cm = CoordinationManager(session_id="s1", base_dir=tmp_dir)
        cm.create_task("task_a", {"type": "analysis"})
        status = cm.get_status()
        assert "task_a" in str(status)

    def test_update_task_status(self, tmp_dir):
        cm = CoordinationManager(session_id="s2", base_dir=tmp_dir)
        cm.create_task("task_b", {"type": "test"})
        cm.update_task_status("task_b", TaskStatus.RUNNING)
        cm.update_task_status("task_b", TaskStatus.COMPLETED, result={"ok": True})

    def test_get_status(self, tmp_dir):
        cm = CoordinationManager(session_id="s3", base_dir=tmp_dir)
        cm.create_task("task_c", {})
        status = cm.get_status()
        assert isinstance(status, dict)

    def test_is_session_complete_empty(self, tmp_dir):
        cm = CoordinationManager(session_id="s4", base_dir=tmp_dir)
        assert cm.is_session_complete() is True

    def test_is_session_complete_pending(self, tmp_dir):
        cm = CoordinationManager(session_id="s5", base_dir=tmp_dir)
        cm.create_task("task_d", {})
        assert cm.is_session_complete() is False

    def test_is_session_complete_all_done(self, tmp_dir):
        cm = CoordinationManager(session_id="s6", base_dir=tmp_dir)
        cm.create_task("task_e", {})
        cm.update_task_status("task_e", TaskStatus.COMPLETED)
        assert cm.is_session_complete() is True

    def test_aggregate_results(self, tmp_dir):
        cm = CoordinationManager(session_id="s7", base_dir=tmp_dir)
        cm.create_task("task_f", {})
        cm.update_task_status("task_f", TaskStatus.COMPLETED, result={"data": "ok"})
        results = cm.aggregate_results()
        assert isinstance(results, list)

    def test_can_task_start_no_deps(self, tmp_dir):
        cm = CoordinationManager(session_id="s8", base_dir=tmp_dir)
        cm.create_task("task_g", {})
        assert cm.can_task_start("task_g") is True

    def test_get_ready_tasks(self, tmp_dir):
        cm = CoordinationManager(session_id="s9", base_dir=tmp_dir)
        cm.create_task("task_h", {})
        ready = cm.get_ready_tasks()
        assert isinstance(ready, list)


# --- Module-level functions ---
class TestModuleFunctions:
    @pytest.fixture
    def tmp_dir(self, tmp_path):
        return str(tmp_path / "coord")

    def test_create_coordination_session(self, tmp_dir):
        tasks = [
            {"task_id": "t1", "config": {"op": "scan"}},
            {"task_id": "t2", "config": {"op": "analyze"}},
        ]
        cm = create_coordination_session(
            session_id="func_test",
            tasks_config=tasks,
            base_dir=tmp_dir,
        )
        assert cm.session_id == "func_test"

    def test_update_task_status_func(self, tmp_dir):
        cm = create_coordination_session(
            session_id="func_upd",
            tasks_config=[{"task_id": "t1", "config": {}}],
            base_dir=tmp_dir,
        )
        update_task_status(
            "func_upd", "t1", TaskStatus.COMPLETED,
            result={"done": True},
            base_dir=tmp_dir,
        )

    def test_aggregate_results_func(self, tmp_dir):
        cm = create_coordination_session(
            session_id="func_agg",
            tasks_config=[{"task_id": "t1", "config": {}}],
            base_dir=tmp_dir,
        )
        cm.update_task_status("t1", TaskStatus.COMPLETED, result={"r": 1})
        results = aggregate_results("func_agg", base_dir=tmp_dir)
        assert isinstance(results, list)
