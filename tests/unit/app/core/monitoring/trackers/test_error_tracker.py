"""Tests for app/core/monitoring/trackers/error_tracker.py."""

from app.core.monitoring.trackers.error_tracker import ErrorAnalysisTracker


def test_record_error_and_get_stats_aggregates_counts_and_rate():
    tracker = ErrorAnalysisTracker()

    tracker.record_error(
        "TimeoutError",
        error_message="node timed out",
        component="collector",
        severity="critical",
        timestamp=0.0,
    )
    tracker.record_error(
        "TimeoutError",
        error_message="node timed out again",
        component="collector",
        severity="critical",
        timestamp=60.0,
    )
    tracker.record_error(
        "ValidationError",
        message="bad payload",
        component="parser",
        severity="warning",
        timestamp=120.0,
    )

    stats = tracker.get_error_stats()

    assert stats["total_errors"] == 3
    assert stats["by_type"] == {"TimeoutError": 2, "ValidationError": 1}
    assert stats["by_severity"] == {"critical": 2, "warning": 1}
    assert stats["by_component"] == {"collector": 2, "parser": 1}
    assert stats["most_common_error"] == "TimeoutError"
    assert stats["error_rate_per_minute"] == 1.5


def test_calculate_error_rate_distribution_and_recovery_stats(monkeypatch):
    tracker = ErrorAnalysisTracker()
    now = 1000.0
    monkeypatch.setattr("app.core.monitoring.trackers.error_tracker.time.time", lambda: now)

    tracker.record_success(component="collector", operation="fetch", timestamp=now - 30)
    tracker.record_success(component="collector", operation="fetch", timestamp=now - 20)
    tracker.record_success(component="collector", operation="fetch", timestamp=now - 10)
    tracker.record_success(component="collector", operation="fetch", timestamp=now - 5)
    tracker.record_error("TimeoutError", component="collector", timestamp=now - 25)
    tracker.record_error("ValidationError", component="parser", timestamp=now - 15)
    tracker.record_recovery(2.5)
    tracker.record_recovery(7.5)

    rate = tracker.calculate_error_rate(time_window_seconds=60)
    distribution = tracker.get_error_distribution()
    recovery = tracker.get_recovery_stats()

    assert rate == {
        "error_rate": 0.5,
        "errors_per_minute": 2.0,
        "success_rate": 0.5,
        "total_errors": 2,
        "total_successes": 4,
        "total_operations": 4,
    }
    assert distribution == {"TimeoutError": 0.5, "ValidationError": 0.5}
    assert recovery == {
        "avg_recovery_seconds": 5.0,
        "min_recovery_seconds": 2.5,
        "max_recovery_seconds": 7.5,
        "total_recoveries": 2,
    }


def test_detect_error_patterns_flags_periodic_recurring_failures():
    tracker = ErrorAnalysisTracker()

    for timestamp in (10.0, 20.0, 30.0):
        tracker.record_error(
            "NetworkError",
            component="gateway",
            error_message="upstream unavailable",
            timestamp=timestamp,
        )

    patterns = tracker.detect_error_patterns()

    assert patterns == [
        {
            "error_type": "NetworkError",
            "component": "gateway",
            "frequency": 3,
            "avg_interval_seconds": 10.0,
            "pattern_type": "periodic",
        }
    ]
