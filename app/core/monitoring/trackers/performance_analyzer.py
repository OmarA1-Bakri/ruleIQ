"""
Performance analysis for LangGraph workflows.
"""

import time
from typing import Any, Dict, List, Optional

from .error_tracker import ErrorAnalysisTracker
from .memory_tracker import MemoryUsageTracker
from .node_tracker import NodeExecutionTracker
from .workflow_tracker import WorkflowMetricsTracker


class PerformanceAnalyzer:
    """Analyzes performance metrics for LangGraph workflows."""

    def __init__(self) -> None:
        """Initialize performance analyzer."""
        self._node_tracker = NodeExecutionTracker()
        self._workflow_tracker = WorkflowMetricsTracker()
        self._memory_tracker = MemoryUsageTracker()
        self._error_tracker = ErrorAnalysisTracker()
        self._baselines: Dict[str, Dict[str, float]] = {}

    def set_baseline(self, metric_name: str, value: float) -> None:
        """Set performance baseline for comparison.

        Args:
            metric_name: Name of the metric
            value: Baseline value
        """
        self._baselines[metric_name] = {"value": value, "timestamp": time.time()}

    def detect_bottlenecks(self) -> List[Dict[str, Any]]:
        """Detect performance bottlenecks.

        Returns:
            List of detected bottlenecks
        """
        bottlenecks = []

        # Check for slow nodes
        node_stats = self._node_tracker.get_node_stats()
        for node_name, stats in node_stats.items():
            if stats["avg_duration"] > 1.0:  # More than 1 second average
                bottlenecks.append(
                    {
                        "type": "slow_node",
                        "component": node_name,
                        "avg_duration": stats["avg_duration"],
                        "severity": "high" if stats["avg_duration"] > 5.0 else "medium",
                    }
                )

        # Check for low throughput workflows
        workflow_stats = self._workflow_tracker.get_workflow_stats()
        if isinstance(workflow_stats, dict) and "workflows" in workflow_stats:
            for workflow_type, stats in workflow_stats["workflows"].items():
                if stats.get("throughput_per_minute", 0) < 1.0:
                    bottlenecks.append(
                        {
                            "type": "low_throughput",
                            "component": workflow_type,
                            "throughput": stats["throughput_per_minute"],
                            "severity": "medium",
                        }
                    )

        # Check for memory leaks
        if self._memory_tracker.detect_memory_leak():
            bottlenecks.append({"type": "memory_leak", "component": "system", "severity": "high"})

        return bottlenecks

    def check_regression(self, metric_name: str, current_value: float) -> Optional[Dict[str, Any]]:
        """Check for performance regression.

        Args:
            metric_name: Name of the metric
            current_value: Current value to check

        Returns:
            Regression details if detected, None otherwise
        """
        if metric_name not in self._baselines:
            return None

        baseline = self._baselines[metric_name]["value"]

        if baseline > 0:
            change_percent = (current_value - baseline) / baseline * 100
        else:
            change_percent = 100 if current_value > 0 else 0

        # Consider it a regression if performance degraded by more than 20%
        if change_percent > 20:
            return {
                "metric": metric_name,
                "baseline": baseline,
                "current": current_value,
                "change_percent": change_percent,
                "severity": "high" if change_percent > 50 else "medium",
            }

        return None

    def generate_recommendations(self) -> List[str]:
        """Generate performance optimization recommendations.

        Returns:
            List of recommendations
        """
        recommendations = []

        # Analyze bottlenecks
        bottlenecks = self.detect_bottlenecks()
        for bottleneck in bottlenecks:
            if bottleneck["type"] == "slow_node":
                recommendations.append(
                    f"Optimize node '{bottleneck['component']}' - "
                    f"average duration {bottleneck['avg_duration']:.2f}s"
                )
            elif bottleneck["type"] == "low_throughput":
                recommendations.append(
                    f"Improve throughput for workflow '{bottleneck['component']}' - "
                    f"currently {bottleneck['throughput']:.2f}/min"
                )
            elif bottleneck["type"] == "memory_leak":
                recommendations.append(
                    "Investigate potential memory leak - consistent memory growth detected"
                )

        # Analyze node failure rates
        node_stats = self._node_tracker.get_node_stats()
        for node_name, stats in node_stats.items():
            total_executions = stats.get("total_executions", 0)
            if total_executions > 0:
                failure_rate = stats.get("failed", 0) / total_executions
                if failure_rate > 0.5:  # More than 50% failure rate
                    recommendations.append(
                        f"Fix errors in node '{node_name}' - failure rate {failure_rate * 100:.1f}%"
                    )

        # Check for high retry rates
        for node_name, stats in node_stats.items():
            retry_stats = self._node_tracker.get_retry_stats(node_name)
            if retry_stats["total_retries"] > 10:
                recommendations.append(
                    f"Reduce retries for node '{node_name}' - "
                    f"{retry_stats['total_retries']} retries recorded"
                )

        # Memory recommendations
        memory_trends = self._memory_tracker.get_memory_trends()
        if memory_trends.get("growth_rate", 0) > 0.1:  # More than 10% growth
            recommendations.append(
                f"Monitor memory usage - {memory_trends['growth_rate'] * 100:.1f}% growth detected"
            )

        # Error rate recommendations
        error_stats = self._error_tracker.get_error_stats()
        if error_stats.get("error_rate_per_minute", 0) > 1:
            recommendations.append(
                f"Reduce error rate - {error_stats['error_rate_per_minute']:.1f} errors per minute"
            )

        return recommendations

    def analyze_trends(self, window_hours: int = 24) -> Dict[str, Any]:
        """Analyze performance trends over time.

        Args:
            window_hours: Time window in hours

        Returns:
            Trend analysis results
        """
        return {
            "node_performance": self._node_tracker.get_node_stats(),
            "workflow_performance": self._workflow_tracker.get_workflow_stats(),
            "memory_trends": self._memory_tracker.get_memory_trends(),
            "error_stats": self._error_tracker.get_error_stats(),
            "recommendations": self.generate_recommendations(),
        }

    def get_performance_summary(self) -> Dict[str, Any]:
        """Get a comprehensive performance summary.

        Returns:
            Dictionary with performance metrics
        """
        node_stats = self._node_tracker.get_execution_stats()
        workflow_stats = self._workflow_tracker.get_workflow_stats()
        memory_usage = self._memory_tracker.get_total_memory_usage()
        error_rates = self._error_tracker.calculate_error_rate()

        return {
            "nodes": {
                "total_executions": node_stats.get("completed", 0),
                "success_rate": (
                    node_stats.get("successful", 0) / max(1, node_stats.get("completed", 1))
                ),
                "executing": node_stats.get("executing", 0),
            },
            "workflows": {
                "total": workflow_stats.get("total_started", 0),
                "active": workflow_stats.get("total_active", 0),
                "completed": workflow_stats.get("total_completed", 0),
                "failed": workflow_stats.get("total_failed", 0),
            },
            "memory": {
                "total_mb": memory_usage.get("total_used_mb", 0),
                "usage_ratio": memory_usage.get("usage_ratio", 0),
            },
            "errors": {
                "error_rate": error_rates.get("error_rate", 0),
                "errors_per_minute": error_rates.get("errors_per_minute", 0),
            },
            "bottlenecks": self.detect_bottlenecks(),
            "recommendations": self.generate_recommendations(),
        }

    def compare_performance(self, metric_name: str, current_value: float) -> Dict[str, Any]:
        """Compare current performance against baseline.

        Args:
            metric_name: Name of the metric to compare
            current_value: Current value of the metric

        Returns:
            Comparison results
        """
        if metric_name not in self._baselines:
            return {
                "metric": metric_name,
                "current": current_value,
                "baseline": None,
                "status": "no_baseline",
            }

        baseline = self._baselines[metric_name]["value"]
        change = current_value - baseline
        change_percent = (change / baseline * 100) if baseline != 0 else 0

        status = "normal"
        if change_percent > 20:
            status = "degraded"
        elif change_percent < -20:
            status = "improved"

        return {
            "metric": metric_name,
            "current": current_value,
            "baseline": baseline,
            "change": change,
            "change_percent": change_percent,
            "status": status,
        }
