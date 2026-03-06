"""

Test Metrics and Observability

Tests for monitoring test execution metrics, performance tracking,
and observability of the testing infrastructure itself.
"""

import json
import time
from pathlib import Path
from typing import Any, Dict

import psutil
import pytest


# Create a standalone metrics collector class (not a test class)
class MetricsCollector:
    """Collects metrics during test execution"""

    def __init__(self):
        self.metrics = {
            "test_executions": [],
            "performance_data": {},
            "resource_usage": [],
            "error_rates": {},
            "coverage_trends": [],
        }
        self.start_time = None

    def start_collection(self):
        """Start collecting metrics"""
        self.start_time = time.time()
        self.collect_system_metrics()

    def stop_collection(self):
        """Stop collecting metrics and finalize data"""
        if self.start_time:
            duration = time.time() - self.start_time
            self.metrics["total_duration"] = duration
        self.collect_system_metrics()
        return self.metrics

    def collect_system_metrics(self):
        """Collect current system metrics"""
        cpu_percent = psutil.cpu_percent(interval=1)
        memory = psutil.virtual_memory()
        disk = psutil.disk_usage("/")

        metric_point = {
            "timestamp": time.time(),
            "cpu_percent": cpu_percent,
            "memory_percent": memory.percent,
            "memory_available_gb": memory.available / (1024**3),
            "disk_free_gb": disk.free / (1024**3),
        }

        self.metrics["resource_usage"].append(metric_point)

    def record_test_execution(self, test_name: str, duration: float, status: str, test_type: str):
        """Record individual test execution metrics"""
        execution_record = {
            "test_name": test_name,
            "duration": duration,
            "status": status,
            "test_type": test_type,
            "timestamp": time.time(),
        }

        self.metrics["test_executions"].append(execution_record)

    def record_performance_metric(self, metric_name: str, value: float, unit: str = "ms"):
        """Record performance metrics"""
        if metric_name not in self.metrics["performance_data"]:
            self.metrics["performance_data"][metric_name] = []

        self.metrics["performance_data"][metric_name].append(
            {"value": value, "unit": unit, "timestamp": time.time()},
        )

    def calculate_test_statistics(self) -> Dict[str, Any]:
        """Calculate test execution statistics"""
        executions = self.metrics["test_executions"]

        if not executions:
            return {"total_tests": 0}

        total_tests = len(executions)
        passed_tests = len([e for e in executions if e["status"] == "passed"])
        failed_tests = len([e for e in executions if e["status"] == "failed"])

        durations = [e["duration"] for e in executions]
        avg_duration = sum(durations) / len(durations)
        max_duration = max(durations)
        min_duration = min(durations)

        # Group by test type
        by_type = {}
        for execution in executions:
            test_type = execution["test_type"]
            if test_type not in by_type:
                by_type[test_type] = {"count": 0, "avg_duration": 0}
            by_type[test_type]["count"] += 1

        # Calculate average duration by type
        for test_type in by_type:
            type_durations = [e["duration"] for e in executions if e["test_type"] == test_type]
            by_type[test_type]["avg_duration"] = sum(type_durations) / len(type_durations)

        return {
            "total_tests": total_tests,
            "passed_tests": passed_tests,
            "failed_tests": failed_tests,
            "pass_rate": passed_tests / total_tests,
            "avg_duration": avg_duration,
            "max_duration": max_duration,
            "min_duration": min_duration,
            "by_type": by_type,
        }


# Global metrics collector instance
metrics_collector = MetricsCollector()


# Create proper test class that uses fixtures instead of __init__
class TestMetricsCollector:
    """Test class for MetricsCollector functionality"""

    @pytest.fixture(autouse=True)
    def setup_method(self):
        """Set up a fresh metrics collector for each test"""
        self.collector = MetricsCollector()

    def test_basic_functionality(self):
        """Test basic metrics collection functionality"""
        # Test that the collector was properly initialized
        assert isinstance(self.collector.metrics, dict)
        assert "test_executions" in self.collector.metrics
        assert "performance_data" in self.collector.metrics
        assert "resource_usage" in self.collector.metrics

    def test_system_metrics_collection(self):
        """Test system metrics collection"""
        self.collector.collect_system_metrics()
        assert len(self.collector.metrics["resource_usage"]) == 1

        resource_metric = self.collector.metrics["resource_usage"][0]
        assert "cpu_percent" in resource_metric
        assert "memory_percent" in resource_metric
        assert "timestamp" in resource_metric


@pytest.fixture(scope="session", autouse=True)
def test_session_metrics():
    """Automatically collect metrics for entire test session"""
    metrics_collector.start_collection()
    yield metrics_collector

    # Finalize metrics collection
    final_metrics = metrics_collector.stop_collection()

    # Save metrics to file
    metrics_file = Path("test_session_metrics.json")
    with open(metrics_file, "w") as f:
        json.dump(final_metrics, f, indent=2, default=str)

    # Print summary
    stats = metrics_collector.calculate_test_statistics()
    print("\n📊 Test Session Metrics Summary:")
    print(f"   Total Tests: {stats.get('total_tests', 0)}")
    print(f"   Pass Rate: {stats.get('pass_rate', 0):.1%}")
    print(f"   Avg Duration: {stats.get('avg_duration', 0):.2f}s")


@pytest.fixture(autouse=True)
def test_execution_tracker(request):
    """Track individual test execution metrics"""
    test_name = request.node.name
    test_type = "unit"  # Default

    # Determine test type from path
    test_path = str(request.fspath)
    if "integration" in test_path:
        test_type = "integration"
    elif "e2e" in test_path:
        test_type = "e2e"
    elif "performance" in test_path:
        test_type = "performance"
    elif "security" in test_path:
        test_type = "security"
    elif "ai" in test_path:
        test_type = "ai"

    start_time = time.time()

    yield

    # Record execution after test completes
    duration = time.time() - start_time
    # Use a safer approach to determine test status
    status = "passed"  # Default to passed
    if hasattr(request.node, "rep_call") and request.node.rep_call.failed:
        status = "failed"

    metrics_collector.record_test_execution(test_name, duration, status, test_type)


@pytest.hookimpl(tryfirst=True, hookwrapper=True)
def pytest_runtest_makereport(item, call):
    """Hook to capture test results"""
    outcome = yield
    rep = outcome.get_result()
    setattr(item, "rep_" + rep.when, rep)

    # Record error metrics
    if rep.failed:
        str(item.fspath)
        error_category = "unknown"

        if "assertion" in str(rep.longrepr).lower():
            error_category = "assertion_error"
        elif "timeout" in str(rep.longrepr).lower():
            error_category = "timeout"
        elif "connection" in str(rep.longrepr).lower():
            error_category = "connection_error"
        elif "import" in str(rep.longrepr).lower():
            error_category = "import_error"

        if error_category not in metrics_collector.metrics["error_rates"]:
            metrics_collector.metrics["error_rates"][error_category] = 0
        metrics_collector.metrics["error_rates"][error_category] += 1


@pytest.mark.monitoring
class TestObservability:
    """Tests for testing infrastructure observability"""

    def test_metrics_collection_functionality(self):
        """Test that metrics collection is working properly"""
        # Test metrics collector functionality
        collector = MetricsCollector()

        # Test system metrics collection
        collector.collect_system_metrics()
        assert len(collector.metrics["resource_usage"]) == 1

        resource_metric = collector.metrics["resource_usage"][0]
        assert "cpu_percent" in resource_metric
        assert "memory_percent" in resource_metric
        assert "timestamp" in resource_metric

        # Test performance metric recording
        collector.record_performance_metric("api_response_time", 250.5, "ms")
        assert "api_response_time" in collector.metrics["performance_data"]
        assert len(collector.metrics["performance_data"]["api_response_time"]) == 1

        # Test test execution recording
        collector.record_test_execution("test_example", 1.5, "passed", "unit")
        assert len(collector.metrics["test_executions"]) == 1

        execution = collector.metrics["test_executions"][0]
        assert execution["test_name"] == "test_example"
        assert execution["duration"] == 1.5
        assert execution["status"] == "passed"
        assert execution["test_type"] == "unit"

    def test_test_statistics_calculation(self):
        """Test calculation of test execution statistics"""
        collector = MetricsCollector()

        # Add sample test executions
        test_data = [
            ("test_a", 1.0, "passed", "unit"),
            ("test_b", 2.0, "failed", "unit"),
            ("test_c", 0.5, "passed", "integration"),
            ("test_d", 3.0, "passed", "e2e"),
            ("test_e", 1.5, "passed", "unit"),
        ]

        for test_name, duration, status, test_type in test_data:
            collector.record_test_execution(test_name, duration, status, test_type)

        stats = collector.calculate_test_statistics()

        assert stats["total_tests"] == 5
        assert stats["passed_tests"] == 4
        assert stats["failed_tests"] == 1
        assert stats["pass_rate"] == 0.8
        assert stats["avg_duration"] == 1.6  # (1.0 + 2.0 + 0.5 + 3.0 + 1.5) / 5
        assert stats["max_duration"] == 3.0
        assert stats["min_duration"] == 0.5

        # Check by-type statistics
        assert "unit" in stats["by_type"]
        assert stats["by_type"]["unit"]["count"] == 3
        assert "integration" in stats["by_type"]
        assert stats["by_type"]["integration"]["count"] == 1

    def test_resource_monitoring_during_test(self):
        """Test resource monitoring during test execution"""
        initial_metrics = len(metrics_collector.metrics["resource_usage"])

        # Simulate some work that uses resources
        data = []
        for i in range(1000):
            data.append(f"test_data_{i}" * 100)

        # Collect metrics during execution
        metrics_collector.collect_system_metrics()

        # Verify metrics were collected
        final_metrics = len(metrics_collector.metrics["resource_usage"])
        assert final_metrics > initial_metrics

        # Verify metric structure
        latest_metric = metrics_collector.metrics["resource_usage"][-1]
        assert latest_metric["cpu_percent"] >= 0
        assert latest_metric["memory_percent"] >= 0
        assert latest_metric["memory_available_gb"] > 0
        assert latest_metric["disk_free_gb"] > 0

    def test_performance_metric_tracking(self):
        """Test performance metric tracking functionality"""
        # Record various performance metrics
        metrics_collector.record_performance_metric("database_query_time", 125.3, "ms")
        metrics_collector.record_performance_metric("api_response_time", 89.7, "ms")
        metrics_collector.record_performance_metric("file_processing_time", 2.5, "s")

        # Add multiple measurements for same metric
        metrics_collector.record_performance_metric("api_response_time", 95.2, "ms")
        metrics_collector.record_performance_metric("api_response_time", 78.9, "ms")

        performance_data = metrics_collector.metrics["performance_data"]

        # Verify metrics were recorded
        assert "database_query_time" in performance_data
        assert "api_response_time" in performance_data
        assert "file_processing_time" in performance_data

        # Verify multiple measurements
        api_metrics = performance_data["api_response_time"]
        assert len(api_metrics) == 3  # 3 measurements recorded

        # Verify metric structure
        for metric in api_metrics:
            assert "value" in metric
            assert "unit" in metric
            assert "timestamp" in metric
            assert metric["unit"] == "ms"

    def test_error_rate_tracking(self):
        """Test error rate tracking functionality"""
        metrics_collector.metrics["error_rates"].copy()

        # Simulate different types of errors
        # This would normally be captured by the pytest hook
        metrics_collector.metrics["error_rates"]["assertion_error"] = 2
        metrics_collector.metrics["error_rates"]["timeout"] = 1
        metrics_collector.metrics["error_rates"]["connection_error"] = 1

        error_rates = metrics_collector.metrics["error_rates"]

        assert error_rates["assertion_error"] == 2
        assert error_rates["timeout"] == 1
        assert error_rates["connection_error"] == 1

    def test_test_duration_trends(self):
        """Test tracking of test duration trends"""
        # Record tests with varying durations
        durations = [0.5, 1.2, 0.8, 2.1, 1.0, 0.9, 1.5]

        for i, duration in enumerate(durations):
            metrics_collector.record_test_execution(
                f"trend_test_{i}",
                duration,
                "passed",
                "unit",
            )

        executions = metrics_collector.metrics["test_executions"]

        # Filter executions for trend tests
        trend_executions = [e for e in executions if e["test_name"].startswith("trend_test_")]

        assert len(trend_executions) == 7

        # Calculate trend statistics
        trend_durations = [e["duration"] for e in trend_executions]
        avg_duration = sum(trend_durations) / len(trend_durations)

        # Verify reasonable duration tracking
        assert 0.5 <= min(trend_durations) <= 0.5
        assert 2.1 <= max(trend_durations) <= 2.1
        assert 1.0 <= avg_duration <= 1.5


@pytest.mark.monitoring
class TestMetricsReporting:
    """Tests for metrics reporting and analysis"""

    def test_generate_test_report(self):
        """Test generation of comprehensive test report"""
        collector = MetricsCollector()

        # Add sample data
        collector.record_test_execution("unit_test_1", 0.5, "passed", "unit")
        collector.record_test_execution("unit_test_2", 1.2, "failed", "unit")
        collector.record_test_execution(
            "integration_test_1",
            2.5,
            "passed",
            "integration",
        )
        collector.record_performance_metric("response_time", 150.0, "ms")
        collector.collect_system_metrics()

        # Generate statistics
        stats = collector.calculate_test_statistics()

        # Test report structure
        assert "total_tests" in stats
        assert "pass_rate" in stats
        assert "by_type" in stats

        # Verify calculated values
        assert stats["total_tests"] == 3
        assert stats["passed_tests"] == 2
        assert stats["failed_tests"] == 1
        assert abs(stats["pass_rate"] - 0.6667) < 0.001

    def test_metrics_export_format(self):
        """Test that metrics can be exported in proper format"""
        collector = MetricsCollector()

        # Add comprehensive test data
        collector.record_test_execution("export_test", 1.0, "passed", "unit")
        collector.record_performance_metric("export_metric", 100.0, "ms")
        collector.collect_system_metrics()

        # Export metrics
        exported_metrics = collector.metrics

        # Verify export structure
        required_keys = [
            "test_executions",
            "performance_data",
            "resource_usage",
            "error_rates",
        ]

        for key in required_keys:
            assert key in exported_metrics

        # Verify data can be serialized to JSON
        try:
            json_data = json.dumps(exported_metrics, default=str)
            parsed_data = json.loads(json_data)
            assert parsed_data is not None
        except (TypeError, ValueError) as e:
            pytest.fail(f"Metrics cannot be serialized to JSON: {e}")

    def test_performance_threshold_detection(self):
        """Test detection of performance threshold violations"""
        collector = MetricsCollector()

        # Define performance thresholds
        thresholds = {
            "api_response_time": {"max": 200.0, "unit": "ms"},
            "database_query_time": {"max": 100.0, "unit": "ms"},
            "memory_usage": {"max": 80.0, "unit": "percent"},
        }

        # Record metrics that violate thresholds
        collector.record_performance_metric("api_response_time", 250.0, "ms")  # Violation
        collector.record_performance_metric("database_query_time", 75.0, "ms")  # OK

        violations = []

        # Check for threshold violations
        for metric_name, threshold in thresholds.items():
            if metric_name in collector.metrics["performance_data"]:
                metric_values = collector.metrics["performance_data"][metric_name]

                for metric_point in metric_values:
                    if (
                        metric_point["unit"] == threshold["unit"]
                        and metric_point["value"] > threshold["max"]
                    ):
                        violations.append(
                            {
                                "metric": metric_name,
                                "value": metric_point["value"],
                                "threshold": threshold["max"],
                                "unit": threshold["unit"],
                            },
                        )

        # Verify violation detection
        assert len(violations) == 1
        assert violations[0]["metric"] == "api_response_time"
        assert violations[0]["value"] == 250.0
        assert violations[0]["threshold"] == 200.0

    def test_trend_analysis(self):
        """Test trend analysis of test metrics over time"""
        collector = MetricsCollector()

        # Simulate test executions over time with improving performance
        base_time = time.time()
        durations = [2.0, 1.8, 1.6, 1.4, 1.2, 1.0, 0.9, 0.8]  # Improving trend

        for i, duration in enumerate(durations):
            # Simulate time progression
            timestamp = base_time + (i * 60)  # 1 minute intervals

            collector.record_test_execution("trend_test", duration, "passed", "unit")
            # Manually set timestamp for trend analysis
            collector.metrics["test_executions"][-1]["timestamp"] = timestamp

        # Analyze trend
        trend_executions = [
            e for e in collector.metrics["test_executions"] if e["test_name"] == "trend_test"
        ]

        # Sort by timestamp
        trend_executions.sort(key=lambda x: x["timestamp"])

        # Calculate trend (simple linear regression slope)
        n = len(trend_executions)
        sum_x = sum(range(n))
        sum_y = sum(e["duration"] for e in trend_executions)
        sum_xy = sum(i * e["duration"] for i, e in enumerate(trend_executions))
        sum_x2 = sum(i * i for i in range(n))

        slope = (n * sum_xy - sum_x * sum_y) / (n * sum_x2 - sum_x * sum_x)

        # Verify improving trend (negative slope)
        assert slope < 0, "Test duration should be improving (decreasing) over time"
        assert slope < -0.1, "Trend should show significant improvement"


@pytest.mark.monitoring
class TestCoverageTracking:
    """Tests for test coverage tracking and reporting"""

    def test_coverage_metric_structure(self):
        """Test structure of coverage metrics"""
        # This would typically integrate with pytest-cov
        coverage_data = {
            "overall_coverage": 85.5,
            "by_module": {
                "services.evidence_service": 92.3,
                "services.ai.assistant": 78.9,
                "api.routers.evidence": 88.1,
                "database.evidence_item": 95.2,
            },
            "missing_lines": {
                "services.evidence_service": [45, 67, 89],
                "services.ai.assistant": [23, 145, 167, 189, 201],
            },
            "branch_coverage": 79.2,
        }

        # Verify coverage data structure
        assert "overall_coverage" in coverage_data
        assert "by_module" in coverage_data
        assert "missing_lines" in coverage_data
        assert "branch_coverage" in coverage_data

        # Verify coverage percentages are valid
        assert 0 <= coverage_data["overall_coverage"] <= 100
        assert 0 <= coverage_data["branch_coverage"] <= 100

        for module, coverage in coverage_data["by_module"].items():
            assert 0 <= coverage <= 100
            assert isinstance(module, str)

    def test_coverage_trend_tracking(self):
        """Test tracking of coverage trends over time"""
        # Simulate coverage data over multiple test runs
        coverage_history = [
            {"timestamp": time.time() - 86400 * 7, "coverage": 78.5},  # 7 days ago
            {"timestamp": time.time() - 86400 * 5, "coverage": 80.2},  # 5 days ago
            {"timestamp": time.time() - 86400 * 3, "coverage": 82.1},  # 3 days ago
            {"timestamp": time.time() - 86400 * 1, "coverage": 83.7},  # 1 day ago
            {"timestamp": time.time(), "coverage": 85.5},  # Today,
        ]

        # Add to metrics collector
        metrics_collector.metrics["coverage_trends"] = coverage_history

        # Analyze trend
        coverages = [entry["coverage"] for entry in coverage_history]

        # Calculate improvement
        initial_coverage = coverages[0]
        final_coverage = coverages[-1]
        improvement = final_coverage - initial_coverage

        assert improvement > 0, "Coverage should be improving over time"
        assert improvement >= 5.0, "Coverage improvement should be significant"

        # Verify no regression (each entry should be >= previous)
        for i in range(1, len(coverages)):
            assert coverages[i] >= coverages[i - 1], f"Coverage regression detected at index {i}"

    def test_coverage_threshold_compliance(self):
        """Test compliance with coverage thresholds"""
        # Define coverage thresholds by component
        coverage_thresholds = {
            "critical_services": 95.0,
            "high_priority": 85.0,
            "medium_priority": 75.0,
            "low_priority": 65.0,
        }

        # Sample coverage data
        module_coverage = {
            "services.evidence_service": {
                "coverage": 96.2,
                "priority": "critical_services",
            },
            "services.ai.assistant": {"coverage": 87.5, "priority": "high_priority"},
            "api.routers.evidence": {"coverage": 78.9, "priority": "medium_priority"},
            "utils.helpers": {"coverage": 68.3, "priority": "low_priority"},
            "services.authentication": {
                "coverage": 82.1,
                "priority": "high_priority",
            },  # Below threshold,
        }

        violations = []

        # Check threshold compliance
        for module, data in module_coverage.items():
            priority = data["priority"]
            coverage = data["coverage"]
            threshold = coverage_thresholds[priority]

            if coverage < threshold:
                violations.append(
                    {
                        "module": module,
                        "coverage": coverage,
                        "threshold": threshold,
                        "priority": priority,
                        "deficit": threshold - coverage,
                    },
                )

        # Verify violation detection
        assert len(violations) == 1
        assert violations[0]["module"] == "services.authentication"
        assert violations[0]["deficit"] == pytest.approx(2.9, rel=1e-2)


# Utility functions for metrics analysis
def analyze_test_performance_trends(metrics_data: Dict[str, Any]) -> Dict[str, Any]:
    """Analyze performance trends from metrics data"""
    executions = metrics_data.get("test_executions", [])

    if not executions:
        return {"trend": "no_data"}

    # Group by test type
    by_type = {}
    for execution in executions:
        test_type = execution["test_type"]
        if test_type not in by_type:
            by_type[test_type] = []
        by_type[test_type].append(execution)

    trends = {}
    for test_type, type_executions in by_type.items():
        if len(type_executions) < 2:
            trends[test_type] = "insufficient_data"
            continue

        # Sort by timestamp
        type_executions.sort(key=lambda x: x["timestamp"])

        # Calculate simple trend
        durations = [e["duration"] for e in type_executions]

        first_half = durations[: len(durations) // 2]
        second_half = durations[len(durations) // 2 :]

        first_avg = sum(first_half) / len(first_half)
        second_avg = sum(second_half) / len(second_half)

        if second_avg < first_avg * 0.9:  # 10% improvement
            trends[test_type] = "improving"
        elif second_avg > first_avg * 1.1:  # 10% degradation
            trends[test_type] = "degrading"
        else:
            trends[test_type] = "stable"

    return trends


def generate_metrics_dashboard_data(metrics_data: Dict[str, Any]) -> Dict[str, Any]:
    """Generate data for metrics dashboard visualization"""
    executions = metrics_data.get("test_executions", [])
    performance_data = metrics_data.get("performance_data", {})
    resource_usage = metrics_data.get("resource_usage", [])

    dashboard_data = {
        "summary": {
            "total_tests": len(executions),
            "avg_test_duration": (
                sum(e["duration"] for e in executions) / len(executions) if executions else 0,
            ),
            "pass_rate": (
                len([e for e in executions if e["status"] == "passed"]) / len(executions)
                if executions
                else 0,
            ),
            "performance_metrics_count": sum(len(metrics) for metrics in performance_data.values()),
        },
        "charts": {
            "test_duration_over_time": [
                {"timestamp": e["timestamp"], "duration": e["duration"]}
                for e in sorted(executions, key=lambda x: x["timestamp"])
            ],
            "resource_usage_over_time": resource_usage,
            "test_status_distribution": {
                "passed": len([e for e in executions if e["status"] == "passed"]),
                "failed": len([e for e in executions if e["status"] == "failed"]),
            },
        },
        "alerts": [],
    }

    # Generate alerts based on metrics
    if dashboard_data["summary"]["pass_rate"] < 0.9:
        dashboard_data["alerts"].append(
            {
                "severity": "high",
                "message": f"Low pass rate: {dashboard_data['summary']['pass_rate']:.1%}",
            },
        )

    if dashboard_data["summary"]["avg_test_duration"] > 5.0:
        dashboard_data["alerts"].append(
            {
                "severity": "medium",
                "message": f"High average test duration: {dashboard_data['summary']['avg_test_duration']:.1f}s",
            },
        )

    return dashboard_data
