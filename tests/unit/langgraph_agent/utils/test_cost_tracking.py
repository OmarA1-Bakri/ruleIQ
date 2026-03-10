"""Tests for langgraph_agent/utils/cost_tracking.py."""

from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest

from langgraph_agent.utils import cost_tracking


@pytest.mark.asyncio
async def test_track_node_cost_async_tracks_tokens_and_injects_metadata(monkeypatch):
    mock_manager = SimpleNamespace(track_ai_request=AsyncMock())
    monkeypatch.setattr(cost_tracking, "get_cost_manager", lambda: mock_manager)

    @cost_tracking.track_node_cost(node_name="planner", service_name="langgraph", model_name="gpt-4")
    async def run_node(_state):
        return {
            "usage": {"input_tokens": 12, "output_tokens": 8},
            "total_cost": 0.42,
        }

    result = await run_node(SimpleNamespace(user_id="user-123"))

    mock_manager.track_ai_request.assert_awaited_once()
    call_kwargs = mock_manager.track_ai_request.await_args.kwargs
    assert call_kwargs["model"] == "gpt-4"
    assert call_kwargs["input_tokens"] == 12
    assert call_kwargs["output_tokens"] == 8
    assert call_kwargs["user_id"] == "user-123"
    assert call_kwargs["service_name"] == "langgraph.planner"
    assert result["cost_tracking"]["node_name"] == "planner"
    assert result["cost_tracking"]["total_cost"] == 0.42


@pytest.mark.asyncio
async def test_track_node_cost_async_skips_tracking_when_no_tokens(monkeypatch):
    mock_manager = SimpleNamespace(track_ai_request=AsyncMock())
    monkeypatch.setattr(cost_tracking, "get_cost_manager", lambda: mock_manager)

    @cost_tracking.track_node_cost(node_name="validator")
    async def run_node(_state):
        return {"result": "ok"}

    result = await run_node(SimpleNamespace(user_id="user-123"))

    mock_manager.track_ai_request.assert_not_awaited()
    assert result["cost_tracking"]["input_tokens"] == 0
    assert result["cost_tracking"]["output_tokens"] == 0


def test_track_node_cost_sync_schedules_background_tracking(monkeypatch):
    mock_manager = SimpleNamespace(track_ai_request=AsyncMock())
    scheduled = []

    def create_task(coroutine):
        scheduled.append(coroutine)
        coroutine.close()
        return MagicMock()

    monkeypatch.setattr(cost_tracking, "get_cost_manager", lambda: mock_manager)
    monkeypatch.setattr(cost_tracking.asyncio, "create_task", create_task)

    @cost_tracking.track_node_cost(node_name="sync-node", service_name="graph", model_name="claude")
    def run_node(_state):
        return {"input_tokens": 3, "output_tokens": 2, "total_cost": 0.05}

    result = run_node(SimpleNamespace(user_id="user-456"))

    assert len(scheduled) == 1
    assert result["cost_tracking"] == {
        "node_name": "sync-node",
        "input_tokens": 3,
        "output_tokens": 2,
        "total_cost": 0.05,
        "execution_time": result["cost_tracking"]["execution_time"],
    }


def test_aggregate_node_costs_combines_state_values():
    summary = cost_tracking.aggregate_node_costs(
        {
            "cost_tracking": {
                "node_name": "collector",
                "input_tokens": 10,
                "output_tokens": 4,
                "total_cost": 0.3,
                "execution_time": 1.2,
            },
            "accumulated_costs": {"planner": 0.4, "writer": 0.2},
        }
    )

    assert summary["total_input_tokens"] == 10
    assert summary["total_output_tokens"] == 4
    assert round(summary["total_cost"], 2) == 0.9
    assert summary["total_execution_time"] == 1.2
    assert summary["node_costs"] == {"collector": 0.3, "planner": 0.4, "writer": 0.2}


def test_cost_tracking_context_accumulates_tokens_and_operations():
    with cost_tracking.CostTrackingContext("assessment", user_id="user-1") as context:
        context.add_tokens(100, 40, cost=0.15)
        context.add_tokens(50, 20)
        context.add_operation("draft", {"step": 1})

    assert context.context_name == "assessment"
    assert context.user_id == "user-1"
    assert context.input_tokens == 150
    assert context.output_tokens == 60
    assert context.total_cost == 0.15
    assert len(context.operations) == 1
    assert context.operations[0]["name"] == "draft"
