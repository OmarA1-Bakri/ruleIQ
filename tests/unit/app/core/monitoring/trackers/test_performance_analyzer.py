"""Tests for app/core/monitoring/trackers/performance_analyzer.py."""

from typing import Any, cast

from app.core.monitoring.trackers.performance_analyzer import PerformanceAnalyzer


class StubNodeTracker:
    def __init__(self) -> None:
        self._node_stats = {
            "slow-node": {"avg_duration": 6.2, "total_executions": 20, "failed": 12},
            "retry-node": {"avg_duration": 0.4, "total_executions": 30, "failed": 1},
        }

    def get_node_stats(self):
        return self._node_stats

    def get_retry_stats(self, node_name: str):
        if node_name == "retry-node":
            return {"total_retries": 12}
        return {"total_retries": 0}

    def get_execution_stats(self):
        return {"completed": 50, "successful": 38, "executing": 2}


class StubWorkflowTracker:
    def get_workflow_stats(self):
        return {
            "workflows": {"monthly-audit": {"throughput_per_minute": 0.5}},
            "total_started": 12,
            "total_active": 1,
            "total_completed": 9,
            "total_failed": 2,
        }


class StubMemoryTracker:
    def detect_memory_leak(self):
        return True

    def get_memory_trends(self):
        return {"growth_rate": 0.15}

    def get_total_memory_usage(self):
        return {"total_used_mb": 512, "usage_ratio": 0.64}


class StubErrorTracker:
    def get_error_stats(self):
        return {"error_rate_per_minute": 1.7}

    def calculate_error_rate(self):
        return {"error_rate": 0.12, "errors_per_minute": 1.7}


def _build_analyzer() -> PerformanceAnalyzer:
    analyzer = PerformanceAnalyzer()
    analyzer._node_tracker = cast(Any, StubNodeTracker())  # pylint: disable=protected-access
    analyzer._workflow_tracker = cast(Any, StubWorkflowTracker())  # pylint: disable=protected-access
    analyzer._memory_tracker = cast(Any, StubMemoryTracker())  # pylint: disable=protected-access
    analyzer._error_tracker = cast(Any, StubErrorTracker())  # pylint: disable=protected-access
    return analyzer


def test_detect_bottlenecks_finds_slow_low_throughput_and_memory_issues():
    analyzer = _build_analyzer()

    bottlenecks = analyzer.detect_bottlenecks()

    assert {item["type"] for item in bottlenecks} == {
        "slow_node",
        "low_throughput",
        "memory_leak",
    }
    assert any(item["severity"] == "high" for item in bottlenecks)


def test_generate_recommendations_covers_failures_retries_memory_and_errors():
    analyzer = _build_analyzer()

    recommendations = analyzer.generate_recommendations()

    assert any("Optimize node 'slow-node'" in item for item in recommendations)
    assert any("Improve throughput for workflow 'monthly-audit'" in item for item in recommendations)
    assert any("Fix errors in node 'slow-node'" in item for item in recommendations)
    assert any("Reduce retries for node 'retry-node'" in item for item in recommendations)
    assert any("Monitor memory usage" in item for item in recommendations)
    assert any("Reduce error rate" in item for item in recommendations)


def test_check_regression_and_compare_performance_handle_baselines():
    analyzer = _build_analyzer()
    analyzer.set_baseline("latency", 100.0)

    regression = analyzer.check_regression("latency", 170.0)
    comparison = analyzer.compare_performance("latency", 70.0)
    no_baseline = analyzer.compare_performance("throughput", 9.0)

    assert regression is not None
    assert regression["severity"] == "high"
    assert round(regression["change_percent"], 1) == 70.0
    assert comparison["status"] == "improved"
    assert comparison["baseline"] == 100.0
    assert no_baseline["status"] == "no_baseline"


def test_analyze_trends_and_summary_return_expected_shape():
    analyzer = _build_analyzer()

    trends = analyzer.analyze_trends(window_hours=48)
    summary = analyzer.get_performance_summary()

    assert "node_performance" in trends
    assert "recommendations" in trends
    assert summary["nodes"]["total_executions"] == 50
    assert summary["workflows"]["completed"] == 9
    assert summary["memory"]["total_mb"] == 512
    assert summary["errors"]["errors_per_minute"] == 1.7
