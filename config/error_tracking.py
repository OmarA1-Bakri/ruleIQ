"""

# Constants
MAX_RETRIES = 3


Comprehensive Error Tracking and Monitoring System for ruleIQ

Provides error tracking, alerting, and automated debugging
for both backend and frontend systems.
"""

import traceback
import asyncio
import time
from typing import Dict, List, Any, Optional, Callable
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from collections import defaultdict, Counter
from enum import Enum
import logging
import threading
from functools import wraps

logger = logging.getLogger(__name__)


class ErrorSeverity(Enum):
    """Error severity levels"""

    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class ErrorCategory(Enum):
    """Error categories for classification"""

    API = "api"
    DATABASE = "database"
    AI_SERVICE = "ai_service"
    AUTHENTICATION = "authentication"
    EXTERNAL_SERVICE = "external_service"
    VALIDATION = "validation"
    SECURITY = "security"
    PERFORMANCE = "performance"
    UNKNOWN = "unknown"


@dataclass
class ErrorReport:
    """Individual error report"""

    id: str
    timestamp: datetime
    severity: ErrorSeverity
    category: ErrorCategory
    error_type: str
    message: str
    stack_trace: str
    context: Dict[str, Any] = field(default_factory=dict)
    user_id: Optional[str] = None
    session_id: Optional[str] = None
    request_id: Optional[str] = None
    endpoint: Optional[str] = None
    resolved: bool = False
    resolution_notes: Optional[str] = None


@dataclass
class ErrorPattern:
    """Pattern of recurring errors"""

    signature: str
    count: int
    first_seen: datetime
    last_seen: datetime
    error_type: str
    category: ErrorCategory
    severity: ErrorSeverity
    examples: List[str] = field(default_factory=list)
    affected_endpoints: List[str] = field(default_factory=list)
    affected_users: List[str] = field(default_factory=list)


class ErrorTracker:
    """Comprehensive error tracking system"""

    def __init__(self, max_errors: int = 10000, pattern_threshold: int = 3) -> None:
        self.max_errors = max_errors
        self.pattern_threshold = pattern_threshold
        self.errors: List[ErrorReport] = []
        self.error_patterns: Dict[str, ErrorPattern] = {}
        self.error_counts_by_category: Counter = Counter()
        self.error_counts_by_severity: Counter = Counter()
        self.error_rates: Dict[str, List[float]] = defaultdict(list)
        self._lock = threading.Lock()

    def generate_error_id(self) -> str:
        """Generate unique error ID"""
        import uuid

        return f"err_{int(time.time())}_{str(uuid.uuid4())[:8]}"

    def get_error_signature(
        self, error_type: str, message: str, endpoint: Optional[str] = None
    ) -> str:
        """Generate error signature for pattern matching"""
        normalized_message = self._normalize_error_message(message)
        endpoint_part = f":{endpoint}" if endpoint else ""
        return f"{error_type}:{normalized_message}{endpoint_part}"

    def _normalize_error_message(self, message: str) -> str:
        """Normalize error messages by removing dynamic content"""
        import re

        normalized = re.sub(
            "\\b[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}\\b", "<UUID>", message
        )
        normalized = re.sub("\\d{4}-\\d{2}-\\d{2}T\\d{2}:\\d{2}:\\d{2}", "<TIMESTAMP>", normalized)
        normalized = re.sub("\\d+", "<NUMBER>", normalized)
        normalized = re.sub("/[a-zA-Z0-9_/]+\\.py", "<FILE>", normalized)
        return normalized[:200]

    def categorize_error(
        self, error_type: str, message: str, context: Dict[str, Any]
    ) -> ErrorCategory:
        """Automatically categorize errors based on type and context"""
        error_lower = error_type.lower()
        message_lower = message.lower()
        if "http" in error_lower or "request" in error_lower or context.get("endpoint"):
            return ErrorCategory.API
        if any(
            db_term in error_lower for db_term in ["sql", "database", "connection", "postgresql"]
        ):
            return ErrorCategory.DATABASE
        if any(
            auth_term in message_lower
            for auth_term in ["auth", "token", "permission", "unauthorized"]
        ):
            return ErrorCategory.AUTHENTICATION
        if any(
            ai_term in message_lower for ai_term in ["ai", "model", "openai", "google", "gemini"]
        ):
            return ErrorCategory.AI_SERVICE
        if any(val_term in error_lower for val_term in ["validation", "schema", "pydantic"]):
            return ErrorCategory.VALIDATION
        if any(sec_term in message_lower for sec_term in ["security", "csrf", "xss", "injection"]):
            return ErrorCategory.SECURITY
        if any(
            perf_term in message_lower for perf_term in ["timeout", "memory", "performance", "slow"]
        ):
            return ErrorCategory.PERFORMANCE
        return ErrorCategory.UNKNOWN

    def determine_severity(
        self, error_type: str, message: str, context: Dict[str, Any]
    ) -> ErrorSeverity:
        """Automatically determine error severity"""
        error_type.lower()
        message_lower = message.lower()
        if any(
            critical_term in message_lower
            for critical_term in [
                "database",
                "connection",
                "authentication",
                "security",
                "critical",
            ]
        ):
            return ErrorSeverity.CRITICAL
        if any(
            high_term in message_lower
            for high_term in ["server error", "500", "failed", "exception"]
        ):
            return ErrorSeverity.HIGH
        if any(
            medium_term in message_lower
            for medium_term in ["warning", "404", "validation", "timeout"]
        ):
            return ErrorSeverity.MEDIUM
        return ErrorSeverity.LOW

    def track_error(
        self,
        error: Exception,
        context: Optional[Dict[str, Any]] = None,
        user_id: Optional[str] = None,
        session_id: Optional[str] = None,
        request_id: Optional[str] = None,
        endpoint: Optional[str] = None,
        severity: Optional[ErrorSeverity] = None,
        category: Optional[ErrorCategory] = None,
    ) -> ErrorReport:
        """Track a new error"""
        with self._lock:
            error_context = context or {}
            error_type = type(error).__name__
            message = str(error)
            stack_trace = traceback.format_exc()
            if not category:
                category = self.categorize_error(error_type, message, error_context)
            if not severity:
                severity = self.determine_severity(error_type, message, error_context)
            error_report = ErrorReport(
                id=self.generate_error_id(),
                timestamp=datetime.now(timezone.utc),
                severity=severity,
                category=category,
                error_type=error_type,
                message=message,
                stack_trace=stack_trace,
                context=error_context,
                user_id=user_id,
                session_id=session_id,
                request_id=request_id,
                endpoint=endpoint,
            )
            self.errors.append(error_report)
            if len(self.errors) > self.max_errors:
                self.errors = self.errors[-self.max_errors :]
            self.error_counts_by_category[category] += 1
            self.error_counts_by_severity[severity] += 1
            signature = self.get_error_signature(error_type, message, endpoint)
            self._update_error_pattern(signature, error_report)
            logger.error(
                "Error tracked: %s - %s: %s" % (error_report.id, error_type, message),
                extra={
                    "error_id": error_report.id,
                    "error_category": category.value,
                    "error_severity": severity.value,
                    "context": error_context,
                },
            )
            return error_report

    def _update_error_pattern(self, signature: str, error_report: ErrorReport):
        """Update error pattern tracking"""
        now = datetime.now(timezone.utc)
        if signature in self.error_patterns:
            pattern = self.error_patterns[signature]
            pattern.count += 1
            pattern.last_seen = now
            if len(pattern.examples) < MAX_RETRIES:
                pattern.examples.append(error_report.id)
            if error_report.endpoint and error_report.endpoint not in pattern.affected_endpoints:
                pattern.affected_endpoints.append(error_report.endpoint)
            if error_report.user_id and error_report.user_id not in pattern.affected_users:
                pattern.affected_users.append(error_report.user_id)
        else:
            self.error_patterns[signature] = ErrorPattern(
                signature=signature,
                count=1,
                first_seen=now,
                last_seen=now,
                error_type=error_report.error_type,
                category=error_report.category,
                severity=error_report.severity,
                examples=[error_report.id],
                affected_endpoints=[error_report.endpoint] if error_report.endpoint else [],
                affected_users=[error_report.user_id] if error_report.user_id else [],
            )

    def get_error_patterns(self, min_count: Optional[int] = None) -> List[ErrorPattern]:
        """Get error patterns, optionally filtered by minimum count"""
        with self._lock:
            patterns = list(self.error_patterns.values())
            if min_count:
                patterns = [p for p in patterns if p.count >= min_count]
            return sorted(patterns, key=lambda p: p.count, reverse=True)

    def get_recent_errors(
        self, hours: int = 24, severity: Optional[ErrorSeverity] = None
    ) -> List[ErrorReport]:
        """Get recent errors within specified time window"""
        with self._lock:
            cutoff = datetime.now(timezone.utc) - timedelta(hours=hours)
            recent = [e for e in self.errors if e.timestamp > cutoff]
            if severity:
                recent = [e for e in recent if e.severity == severity]
            return sorted(recent, key=lambda e: e.timestamp, reverse=True)

    def get_error_summary(self, hours: int = 24) -> Dict[str, Any]:
        """Get comprehensive error summary"""
        recent_errors = self.get_recent_errors(hours)
        return {
            "summary": {
                "total_errors": len(recent_errors),
                "critical_errors": len(
                    [e for e in recent_errors if e.severity == ErrorSeverity.CRITICAL]
                ),
                "high_errors": len([e for e in recent_errors if e.severity == ErrorSeverity.HIGH]),
                "error_rate": len(recent_errors) / hours if hours > 0 else 0,
                "time_window_hours": hours,
            },
            "by_category": dict(Counter(e.category.value for e in recent_errors)),
            "by_severity": dict(Counter(e.severity.value for e in recent_errors)),
            "top_endpoints": dict(
                Counter(e.endpoint for e in recent_errors if e.endpoint).most_common(10)
            ),
            "affected_users": len(set(e.user_id for e in recent_errors if e.user_id)),
            "top_patterns": [
                {
                    "signature": p.signature,
                    "count": p.count,
                    "error_type": p.error_type,
                    "category": p.category.value,
                    "severity": p.severity.value,
                }
                for p in self.get_error_patterns(min_count=2)[:10]
            ],
        }

    def resolve_error(self, error_id: str, resolution_notes: str) -> None:
        """Mark an error as resolved"""
        with self._lock:
            for error in self.errors:
                if error.id == error_id:
                    error.resolved = True
                    error.resolution_notes = resolution_notes
                    break

    def clear_old_errors(self, days: int = 7) -> None:
        """Clear errors older than specified days"""
        with self._lock:
            cutoff = datetime.now(timezone.utc) - timedelta(days=days)
            self.errors = [e for e in self.errors if e.timestamp > cutoff]


class ErrorAlertingSystem:
    """Alert system for critical errors"""

    def __init__(self, error_tracker: ErrorTracker) -> None:
        self.error_tracker = error_tracker
        self.alert_thresholds = {
            ErrorSeverity.CRITICAL: 1,
            ErrorSeverity.HIGH: 5,
            ErrorSeverity.MEDIUM: 20,
        }
        self.alert_callbacks: List[Callable] = []

    def add_alert_callback(self, callback: Callable) -> None:
        """Add callback function for alerts"""
        self.alert_callbacks.append(callback)

    def check_for_alerts(self) -> None:
        """Check for conditions that should trigger alerts"""
        recent_errors = self.error_tracker.get_recent_errors(hours=1)
        for severity, threshold in self.alert_thresholds.items():
            count = len([e for e in recent_errors if e.severity == severity])
            if count >= threshold:
                self._trigger_alert(
                    f"High error rate: {count} {severity.value} errors in the last hour"
                )
        patterns = self.error_tracker.get_error_patterns(min_count=3)
        for pattern in patterns:
            if pattern.severity == ErrorSeverity.CRITICAL:
                self._trigger_alert(
                    f"Critical error pattern detected: {pattern.signature} ({pattern.count} occurrences)"
                )

    def _trigger_alert(self, message: str):
        """Trigger alert to all registered callbacks"""
        alert_data = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "message": message,
            "source": "ruleiq-error-tracker",
        }
        for callback in self.alert_callbacks:
            try:
                callback(alert_data)
            except Exception as e:
                logger.error("Alert callback failed: %s" % e)


global_error_tracker = ErrorTracker()
error_alerting = ErrorAlertingSystem(global_error_tracker)


def track_errors(
    category: Optional[ErrorCategory] = None,
    severity: Optional[ErrorSeverity] = None,
    context: Optional[Dict[str, Any]] = None,
) -> Any:
    """Decorator to automatically track errors in functions"""

    def decorator(func) -> Any:
        if asyncio.iscoroutinefunction(func):

            @wraps(func)
            async def async_wrapper(*args, **kwargs) -> Any:
                try:
                    return await func(*args, **kwargs)
                except Exception as e:
                    global_error_tracker.track_error(
                        error=e, context=context, category=category, severity=severity
                    )
                    raise

            return async_wrapper
        else:

            @wraps(func)
            def sync_wrapper(*args, **kwargs) -> Any:
                try:
                    return func(*args, **kwargs)
                except Exception as e:
                    global_error_tracker.track_error(
                        error=e, context=context, category=category, severity=severity
                    )
                    raise

            return sync_wrapper

    return decorator


def track_api_errors(endpoint: str) -> Any:
    """Decorator specifically for API endpoint error tracking"""
    return track_errors(category=ErrorCategory.API, context={"endpoint": endpoint})


def track_db_errors(operation: str, table: str = "unknown") -> Any:
    """Decorator specifically for database operation error tracking"""
    return track_errors(
        category=ErrorCategory.DATABASE, context={"operation": operation, "table": table}
    )


def get_error_dashboard_data() -> Dict[str, Any]:
    """Get comprehensive error data for dashboard display"""
    return {
        "recent_summary": global_error_tracker.get_error_summary(hours=24),
        "critical_errors": global_error_tracker.get_recent_errors(
            hours=24, severity=ErrorSeverity.CRITICAL
        ),
        "top_patterns": global_error_tracker.get_error_patterns(min_count=2)[:10],
        "error_trends": {
            "last_hour": len(global_error_tracker.get_recent_errors(hours=1)),
            "last_6_hours": len(global_error_tracker.get_recent_errors(hours=6)),
            "last_24_hours": len(global_error_tracker.get_recent_errors(hours=24)),
        },
    }


def setup_basic_alerting() -> None:
    """Set up basic console alerting"""

    def console_alert(alert_data) -> None:
        logger.info("🚨 ALERT: %s at %s" % (alert_data["message"], alert_data["timestamp"]))

    error_alerting.add_alert_callback(console_alert)
