"""
Error metrics collection and analysis for LangGraph workflows.
"""

import time
from collections import defaultdict, deque
from datetime import datetime
from typing import Any, Deque, Dict, List


class ErrorAnalysisTracker:
    """Collects and analyzes error metrics for LangGraph."""

    def __init__(self, window_size: int = 1000) -> None:
        """Initialize error metrics collector.

        Args:
            window_size: Size of the sliding window for error tracking
        """
        self.window_size = window_size
        self._errors: Deque[Dict[str, Any]] = deque(maxlen=window_size)
        self._error_counts: Dict[str, int] = defaultdict(int)
        self._error_rates: Dict[str, List[float]] = defaultdict(list)
        self._recovery_times: List[float] = []
        self._severity_counts: Dict[str, int] = defaultdict(int)
        self._component_errors: Dict[str, List[Dict[str, Any]]] = defaultdict(list)
        self._successes: List[Dict[str, Any]] = []
        self._success_count: int = 0

    def record_error(
        self,
        error_type: str,
        error_message: str = None,
        component: str = None,
        message: str = None,
        workflow_id: str = None,
        node_name: str = None,
        severity: str = 'error',
        retry_count: int = 0,
        metadata: Dict[str, Any] = None,
        timestamp: float = None
    ) -> None:
        """Record an error occurrence.

        Args:
            error_type: Type of error
            error_message: Error message (preferred over 'message')
            component: Component where error occurred
            message: Error message (deprecated, use error_message)
            workflow_id: Workflow ID where error occurred
            node_name: Node name where error occurred
            severity: Error severity level
            retry_count: Number of retries attempted
            metadata: Additional metadata
            timestamp: Optional timestamp
        """
        final_message = error_message or message or ''

        if timestamp is not None:
            if isinstance(timestamp, datetime):
                timestamp = timestamp.timestamp()
        else:
            timestamp = time.time()

        error = {
            'timestamp': timestamp,
            'error_type': error_type,
            'component': component,
            'message': final_message,
            'workflow_id': workflow_id,
            'node_name': node_name,
            'severity': severity,
            'retry_count': retry_count,
            'metadata': metadata or {}
        }

        self._errors.append(error)
        self._error_counts[error_type] += 1
        self._severity_counts[severity] += 1

        if component:
            self._component_errors[component].append(error)

    def record_success(
        self,
        component: str = None,
        operation: str = None,
        timestamp: float = None
    ) -> None:
        """Record a successful operation.

        Args:
            component: Component that succeeded
            operation: Operation that succeeded
            timestamp: Custom timestamp
        """
        if timestamp is not None:
            if isinstance(timestamp, datetime):
                timestamp = timestamp.timestamp()
        else:
            timestamp = time.time()

        success_record = {
            'timestamp': timestamp,
            'component': component,
            'operation': operation
        }

        self._successes.append(success_record)
        self._success_count += 1

    def get_error_stats(self) -> Dict[str, Any]:
        """Get comprehensive error statistics.

        Returns:
            Dictionary with error statistics
        """
        if not self._errors:
            return {
                'total_errors': 0,
                'by_type': {},
                'by_severity': {},
                'by_component': {},
                'error_rate_per_minute': 0.0,
                'most_common_error': None
            }

        timestamps = [e['timestamp'] for e in self._errors]
        time_window = max(timestamps) - min(timestamps) if len(timestamps) > 1 else 1
        time_window_minutes = time_window / 60.0

        by_severity = defaultdict(int)
        for error in self._errors:
            by_severity[error.get('severity', 'error')] += 1

        by_component = defaultdict(int)
        for error in self._errors:
            if error.get('component'):
                by_component[error['component']] += 1

        most_common_error = None
        if self._error_counts:
            most_common_error = max(self._error_counts.items(), key=lambda x: x[1])[0]

        return {
            'total_errors': len(self._errors),
            'by_type': dict(self._error_counts),
            'by_severity': dict(by_severity),
            'by_component': dict(by_component),
            'error_rate_per_minute': len(self._errors) / time_window_minutes if time_window_minutes > 0 else 0,
            'most_common_error': most_common_error
        }

    def calculate_error_rate(
        self,
        time_window_seconds: int = 60,
        window_seconds: int = None
    ) -> Dict[str, float]:
        """Calculate overall error rate.

        Args:
            time_window_seconds: Time window in seconds
            window_seconds: Deprecated parameter for backwards compatibility

        Returns:
            Dictionary with error rate metrics
        """
        actual_window = time_window_seconds if window_seconds is None else window_seconds
        cutoff_time = time.time() - actual_window

        recent_errors = [e for e in self._errors if e['timestamp'] >= cutoff_time]
        recent_successes = len([s for s in self._successes if s['timestamp'] >= cutoff_time])

        total_operations = recent_successes
        error_rate = len(recent_errors) / total_operations if total_operations > 0 else 0.0
        success_rate = (total_operations - len(recent_errors)) / total_operations if total_operations > 0 else 1.0

        return {
            'error_rate': error_rate,
            'errors_per_minute': len(recent_errors) * 60 / actual_window if actual_window > 0 else 0,
            'success_rate': success_rate,
            'total_errors': len(recent_errors),
            'total_successes': recent_successes,
            'total_operations': total_operations
        }

    def get_error_distribution(self) -> Dict[str, float]:
        """Get error distribution by type.

        Returns:
            Percentage distribution of errors
        """
        total_errors = sum(self._error_counts.values())
        if total_errors == 0:
            return {}

        return {
            error_type: count / total_errors
            for error_type, count in self._error_counts.items()
        }

    def detect_error_patterns(self) -> List[Dict[str, Any]]:
        """Detect recurring error patterns.

        Returns:
            List of detected patterns
        """
        patterns = []
        error_groups = defaultdict(list)

        for error in self._errors:
            key = (error['error_type'], error['component'])
            error_groups[key].append(error)

        for (error_type, component), errors in error_groups.items():
            if len(errors) >= 3:
                intervals = []
                for i in range(1, len(errors)):
                    intervals.append(errors[i]['timestamp'] - errors[i - 1]['timestamp'])

                if intervals:
                    avg_interval = sum(intervals) / len(intervals)
                    std_interval = (sum((i - avg_interval) ** 2 for i in intervals) / len(intervals)) ** 0.5

                    # Pattern is periodic if standard deviation is low relative to average
                    if std_interval < avg_interval * 0.3:
                        patterns.append({
                            'error_type': error_type,
                            'component': component,
                            'frequency': len(errors),
                            'avg_interval_seconds': avg_interval,
                            'pattern_type': 'periodic'
                        })

        return patterns

    def record_recovery(self, recovery_time: float) -> None:
        """Record error recovery time.

        Args:
            recovery_time: Time taken to recover in seconds
        """
        self._recovery_times.append(recovery_time)

    def get_recovery_stats(self) -> Dict[str, float]:
        """Get recovery time statistics.

        Returns:
            Recovery statistics
        """
        if not self._recovery_times:
            return {}

        return {
            'avg_recovery_seconds': sum(self._recovery_times) / len(self._recovery_times),
            'min_recovery_seconds': min(self._recovery_times),
            'max_recovery_seconds': max(self._recovery_times),
            'total_recoveries': len(self._recovery_times)
        }


# Alias for backward compatibility
ErrorMetricsCollector = ErrorAnalysisTracker
