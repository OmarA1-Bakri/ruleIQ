"""
Prometheus Metrics Collection for RuleIQ

Comprehensive application metrics for monitoring user experience,
performance, and system health.
"""

import time
from typing import Optional
from functools import wraps
from contextlib import contextmanager

from prometheus_client import (
    Counter,
    Histogram,
    Gauge,
    Info,
    CollectorRegistry,
    generate_latest,
    CONTENT_TYPE_LATEST,
)
from fastapi import Response
import logging

logger = logging.getLogger(__name__)

# Create a custom registry for our metrics
REGISTRY = CollectorRegistry()

# Request Metrics
REQUEST_COUNT = Counter(
    "ruleiq_requests_total",
    "Total number of requests",
    ["method", "endpoint", "status"],
    registry=REGISTRY,
)

REQUEST_LATENCY = Histogram(
    "ruleiq_request_duration_seconds",
    "Request latency in seconds",
    ["method", "endpoint"],
    registry=REGISTRY,
    buckets=(0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0, 10.0),
)

ERROR_RATE = Counter(
    "ruleiq_errors_total", "Total number of errors", ["error_type", "endpoint"], registry=REGISTRY
)

# User Session Metrics
ACTIVE_SESSIONS = Gauge(
    "ruleiq_active_sessions", "Number of active user sessions", registry=REGISTRY
)

SESSION_DURATION = Histogram(
    "ruleiq_session_duration_seconds",
    "User session duration",
    registry=REGISTRY,
    buckets=(60, 300, 600, 1800, 3600, 7200, 14400),
)

# Database Metrics
DB_CONNECTIONS_ACTIVE = Gauge(
    "ruleiq_db_connections_active", "Active database connections", ["pool_type"], registry=REGISTRY
)

DB_CONNECTIONS_TOTAL = Gauge(
    "ruleiq_db_connections_total", "Total database connections", ["pool_type"], registry=REGISTRY
)

DB_QUERY_DURATION = Histogram(
    "ruleiq_db_query_duration_seconds",
    "Database query duration",
    ["query_type"],
    registry=REGISTRY,
    buckets=(0.001, 0.005, 0.01, 0.05, 0.1, 0.5, 1.0, 5.0),
)

# Redis Cache Metrics
CACHE_HITS = Counter(
    "ruleiq_cache_hits_total", "Total cache hits", ["cache_type"], registry=REGISTRY
)

CACHE_MISSES = Counter(
    "ruleiq_cache_misses_total", "Total cache misses", ["cache_type"], registry=REGISTRY
)

REDIS_CONNECTIONS = Gauge(
    "ruleiq_redis_connections", "Redis connection pool status", ["status"], registry=REGISTRY
)

# AI/ML Metrics
AI_TOKEN_USAGE = Counter(
    "ruleiq_ai_tokens_total", "Total AI tokens consumed", ["model", "operation"], registry=REGISTRY
)

AI_COST_TOTAL = Counter(
    "ruleiq_ai_cost_usd_total", "Total AI cost in USD", ["model", "operation"], registry=REGISTRY
)

AI_REQUEST_DURATION = Histogram(
    "ruleiq_ai_request_duration_seconds",
    "AI request duration",
    ["model", "operation"],
    registry=REGISTRY,
    buckets=(0.1, 0.5, 1.0, 2.5, 5.0, 10.0, 30.0),
)

# Feature Flag Metrics
FEATURE_FLAG_EVALUATIONS = Counter(
    "ruleiq_feature_flag_evaluations_total",
    "Feature flag evaluations",
    ["flag_name", "result"],
    registry=REGISTRY,
)

FEATURE_FLAG_CACHE_HIT_RATE = Gauge(
    "ruleiq_feature_flag_cache_hit_rate", "Feature flag cache hit rate", registry=REGISTRY
)

# Security Metrics
AUTH_ATTEMPTS = Counter(
    "ruleiq_auth_attempts_total", "Authentication attempts", ["result", "method"], registry=REGISTRY
)

AUTH_FAILURES = Counter(
    "ruleiq_auth_failures_total", "Authentication failures", ["reason"], registry=REGISTRY
)

JWT_VALIDATION_ERRORS = Counter(
    "ruleiq_jwt_validation_errors_total", "JWT validation errors", ["error_type"], registry=REGISTRY
)

SUSPICIOUS_REQUESTS = Counter(
    "ruleiq_suspicious_requests_total",
    "Suspicious request patterns detected",
    ["pattern_type"],
    registry=REGISTRY,
)

# System Health Metrics
SYSTEM_HEALTH = Gauge(
    "ruleiq_system_health_score", "Overall system health score (0-100)", registry=REGISTRY
)

SERVICE_AVAILABILITY = Gauge(
    "ruleiq_service_availability",
    "Service availability status",
    ["service_name"],
    registry=REGISTRY,
)

# Application Info
APP_INFO = Info("ruleiq_app", "Application information", registry=REGISTRY)


class MetricsCollector:
    """Central metrics collection and management."""

    def __init__(self) -> None:
        self.start_time = time.time()
        self._update_app_info()

    def _update_app_info(self):
        """Update application info metrics."""
        from config.settings import settings

        APP_INFO.info(
            {
                "version": getattr(settings, "APP_VERSION", "1.0.0"),
                "environment": getattr(settings, "ENVIRONMENT", "production"),
                "deployed_at": str(int(self.start_time)),
            }
        )

    @contextmanager
    def track_request(self, method: str, endpoint: str):
        """Track request metrics."""
        start_time = time.time()
        try:
            yield
            status = "success"
        except Exception as e:
            status = "error"
            ERROR_RATE.labels(error_type=type(e).__name__, endpoint=endpoint).inc()
            raise
        finally:
            duration = time.time() - start_time
            REQUEST_COUNT.labels(method=method, endpoint=endpoint, status=status).inc()
            REQUEST_LATENCY.labels(method=method, endpoint=endpoint).observe(duration)

    @contextmanager
    def track_db_query(self, query_type: str):
        """Track database query metrics."""
        start_time = time.time()
        try:
            yield
        finally:
            duration = time.time() - start_time
            DB_QUERY_DURATION.labels(query_type=query_type).observe(duration)

    def track_cache_access(self, cache_type: str, hit: bool):
        """Track cache access metrics."""
        if hit:
            CACHE_HITS.labels(cache_type=cache_type).inc()
        else:
            CACHE_MISSES.labels(cache_type=cache_type).inc()

    def track_ai_usage(self, model: str, operation: str, tokens: int, cost: float, duration: float):
        """Track AI/ML usage metrics."""
        AI_TOKEN_USAGE.labels(model=model, operation=operation).inc(tokens)
        AI_COST_TOTAL.labels(model=model, operation=operation).inc(cost)
        AI_REQUEST_DURATION.labels(model=model, operation=operation).observe(duration)

    def track_feature_flag(self, flag_name: str, result: str):
        """Track feature flag evaluation."""
        FEATURE_FLAG_EVALUATIONS.labels(flag_name=flag_name, result=result).inc()

    def track_auth_attempt(self, result: str, method: str = "jwt"):
        """Track authentication attempt."""
        AUTH_ATTEMPTS.labels(result=result, method=method).inc()
        if result == "failure":
            AUTH_FAILURES.labels(reason="invalid_credentials").inc()

    def track_jwt_error(self, error_type: str):
        """Track JWT validation error."""
        JWT_VALIDATION_ERRORS.labels(error_type=error_type).inc()

    def track_suspicious_request(self, pattern_type: str):
        """Track suspicious request pattern."""
        SUSPICIOUS_REQUESTS.labels(pattern_type=pattern_type).inc()

    def update_session_count(self, count: int):
        """Update active session count."""
        ACTIVE_SESSIONS.set(count)

    def update_db_connections(self, active: int, total: int, pool_type: str = "main"):
        """Update database connection metrics."""
        DB_CONNECTIONS_ACTIVE.labels(pool_type=pool_type).set(active)
        DB_CONNECTIONS_TOTAL.labels(pool_type=pool_type).set(total)

    def update_redis_connections(self, active: int, idle: int):
        """Update Redis connection metrics."""
        REDIS_CONNECTIONS.labels(status="active").set(active)
        REDIS_CONNECTIONS.labels(status="idle").set(idle)

    def update_system_health(self, score: float):
        """Update system health score (0-100)."""
        SYSTEM_HEALTH.set(min(100, max(0, score)))

    def update_service_availability(self, service_name: str, available: bool):
        """Update service availability status."""
        SERVICE_AVAILABILITY.labels(service_name=service_name).set(1.0 if available else 0.0)

    def calculate_health_score(self) -> float:
        """Calculate overall system health score."""
        factors = []

        # Error rate factor (lower is better)
        try:
            total_requests = REQUEST_COUNT._value.sum()
            total_errors = ERROR_RATE._value.sum()
            if total_requests > 0:
                error_rate = total_errors / total_requests
                factors.append(max(0, 100 - (error_rate * 1000)))
        except:
            factors.append(100)

        # DB connection utilization (optimal at 50-80%)
        try:
            active = DB_CONNECTIONS_ACTIVE._value.sum()
            total = DB_CONNECTIONS_TOTAL._value.sum()
            if total > 0:
                util = active / total
                if util < 0.5:
                    factors.append(100)
                elif util < 0.8:
                    factors.append(90)
                else:
                    factors.append(max(0, 100 - ((util - 0.8) * 500)))
        except:
            factors.append(100)

        # Cache hit rate (higher is better)
        try:
            hits = CACHE_HITS._value.sum()
            misses = CACHE_MISSES._value.sum()
            total = hits + misses
            if total > 0:
                hit_rate = hits / total
                factors.append(hit_rate * 100)
        except:
            factors.append(50)

        # Calculate average
        if factors:
            return sum(factors) / len(factors)
        return 100.0

    def get_metrics(self) -> bytes:
        """Generate Prometheus metrics output."""
        # Update system health before generating metrics
        self.update_system_health(self.calculate_health_score())
        return generate_latest(REGISTRY)


# Global metrics collector instance
_metrics_collector: Optional[MetricsCollector] = None


def get_metrics_collector() -> MetricsCollector:
    """Get or create the global metrics collector."""
    global _metrics_collector
    if _metrics_collector is None:
        _metrics_collector = MetricsCollector()
    return _metrics_collector


def track_request_metrics(func):
    """Decorator to track request metrics."""

    @wraps(func)
    async def wrapper(*args, **kwargs):
        request = kwargs.get("request")
        if request:
            method = request.method
            endpoint = request.url.path
            collector = get_metrics_collector()
            with collector.track_request(method, endpoint):
                return await func(*args, **kwargs)
        return await func(*args, **kwargs)

    return wrapper


async def metrics_endpoint() -> Response:
    """Prometheus metrics endpoint."""
    collector = get_metrics_collector()
    return Response(content=collector.get_metrics(), media_type=CONTENT_TYPE_LATEST)
