"""

Shared types and enums for AI services

This module contains common types, enums, and data structures used across
AI service modules to prevent circular import dependencies.
"""

from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from typing import Any, Dict, Optional


class CircuitState(Enum):
    """Circuit breaker states"""

    CLOSED = "closed"  # Normal operation
    OPEN = "open"  # Circuit tripped, failing fast
    HALF_OPEN = "half_open"  # Testing if service recovered


class ServiceStatus(Enum):
    """Service health status levels"""

    HEALTHY = "healthy"
    DEGRADED = "degraded"
    UNHEALTHY = "unhealthy"
    UNKNOWN = "unknown"
    MAINTENANCE = "maintenance"


class RetryStrategy(Enum):
    """Available retry strategies"""

    EXPONENTIAL_BACKOFF = "exponential_backoff"
    LINEAR_BACKOFF = "linear_backoff"
    FIXED_DELAY = "fixed_delay"
    FIBONACCI_BACKOFF = "fibonacci_backoff"


class FallbackLevel(Enum):
    """Levels of fallback degradation"""

    NONE = "none"  # No fallback, fail immediately
    BASIC = "basic"  # Basic static responses
    CACHED = "cached"  # Use cached responses
    TEMPLATE = "template"  # Use response templates
    COMPREHENSIVE = "comprehensive"  # Full fallback system


class OfflineMode(Enum):
    """Offline operating modes"""

    DISABLED = "disabled"  # No offline capabilities
    BASIC = "basic"  # Basic offline responses only
    ENHANCED = "enhanced"  # Offline templates and cached responses
    FULL = "full"  # Complete offline functionality


class HealthCheckType(Enum):
    """Types of health checks"""

    PING = "ping"  # Basic connectivity
    FUNCTIONAL = "functional"  # Service functionality test
    PERFORMANCE = "performance"  # Response time and throughput
    COMPREHENSIVE = "comprehensive"  # Full health assessment


class AlertSeverity(Enum):
    """Alert severity levels"""

    INFO = "info"
    WARNING = "warning"
    ERROR = "error"
    CRITICAL = "critical"


@dataclass
class FailureRecord:
    """Record of a service failure"""

    timestamp: datetime
    model_name: str
    error_type: str
    error_message: str
    context: Optional[Dict[str, Any]] = None


@dataclass
class RetryAttempt:
    """Information about a retry attempt"""

    attempt_number: int
    model_name: str
    delay: float
    exception: Optional[Exception] = None
    start_time: Optional[float] = None
    end_time: Optional[float] = None
    success: bool = False

    @property
    def duration(self) -> Optional[float]:
        if self.start_time and self.end_time:
            return self.end_time - self.start_time
        return None


@dataclass
class OfflineRequest:
    """Represents a request made while offline"""

    id: str
    operation: str
    context: Dict[str, Any]
    timestamp: datetime
    user_id: Optional[str] = None
    status: str = "pending"  # pending, synced, failed
    priority: int = 1  # 1-5, higher is more important


# Common type aliases for consistency
AIContext = Dict[str, Any]
ModelName = str
OperationName = str
ErrorCode = str
