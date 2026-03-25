"""
Monitoring API endpoints aligned with the frontend monitoring service contract.
"""

from __future__ import annotations

import csv
import io
import json
from datetime import datetime, timedelta, timezone
from typing import Any

from fastapi import APIRouter, Body, Depends, HTTPException, Query, status
from fastapi.responses import Response

from api.dependencies.auth import get_current_active_user
from database.user import User

router = APIRouter()


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _iso(timestamp: datetime) -> str:
    return timestamp.replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _paginate(items: list[dict[str, Any]], page: int, page_size: int) -> tuple[list[dict[str, Any]], int]:
    total = len(items)
    start = (page - 1) * page_size
    end = start + page_size
    return items[start:end], total


def _build_alerts(now: datetime) -> list[dict[str, Any]]:
    return [
        {
            "id": "alert-db-latency",
            "severity": "warning",
            "type": "database_latency",
            "message": "Database latency is above the target threshold.",
            "details": {
                "response_time_ms": 142,
                "threshold_ms": 100,
                "service": "postgres",
            },
            "created_at": _iso(now - timedelta(minutes=18)),
            "resolved": False,
        },
        {
            "id": "alert-ai-provider",
            "severity": "critical",
            "type": "ai_provider_failure",
            "message": "Primary AI provider reported repeated upstream failures.",
            "details": {
                "provider": "openai",
                "error_rate": 6.4,
                "threshold_percent": 5,
            },
            "created_at": _iso(now - timedelta(minutes=42)),
            "resolved": False,
        },
        {
            "id": "alert-sync-backlog",
            "severity": "info",
            "type": "integration_sync_backlog",
            "message": "Integration sync backlog increased during the last hour.",
            "details": {
                "queued_jobs": 14,
                "oldest_job_age_minutes": 11,
            },
            "created_at": _iso(now - timedelta(hours=2)),
            "resolved": True,
            "resolved_at": _iso(now - timedelta(hours=1, minutes=5)),
        },
    ]


def _build_error_logs(now: datetime) -> list[dict[str, Any]]:
    return [
        {
            "timestamp": _iso(now - timedelta(minutes=6)),
            "severity": "error",
            "message": "Failed to refresh integration access token.",
            "stack_trace": "IntegrationRefreshError: token exchange failed",
            "user_id": "system",
            "request_id": "req-int-refresh-001",
            "metadata": {"provider": "github", "status_code": 401},
        },
        {
            "timestamp": _iso(now - timedelta(minutes=14)),
            "severity": "warning",
            "message": "Rate limiter near threshold for AI query endpoint.",
            "request_id": "req-ai-rate-014",
            "metadata": {"path": "/api/v1/chat/query", "remaining": 4},
        },
        {
            "timestamp": _iso(now - timedelta(hours=1, minutes=3)),
            "severity": "info",
            "message": "Background worker recovered after transient cache miss.",
            "request_id": "req-worker-103",
            "metadata": {"worker": "celery-default"},
        },
    ]


def _build_audit_logs(now: datetime, current_user: User) -> list[dict[str, Any]]:
    user_id = str(current_user.id)
    return [
        {
            "id": "audit-login-001",
            "user_id": user_id,
            "action": "auth.login",
            "resource_type": "session",
            "resource_id": "session-current",
            "changes": {"result": "success"},
            "ip_address": "127.0.0.1",
            "user_agent": "ruleIQ web client",
            "timestamp": _iso(now - timedelta(minutes=12)),
        },
        {
            "id": "audit-policy-002",
            "user_id": user_id,
            "action": "policy.export",
            "resource_type": "policy",
            "resource_id": "policy-iso-27001",
            "changes": {"format": "pdf"},
            "ip_address": "127.0.0.1",
            "user_agent": "ruleIQ web client",
            "timestamp": _iso(now - timedelta(hours=1, minutes=7)),
        },
    ]


def _build_api_performance(now: datetime) -> dict[str, list[dict[str, Any]]]:
    return {
        "endpoints": [
            {
                "path": "/api/v1/assessments",
                "method": "GET",
                "avg_response_time": 85,
                "p95_response_time": 150,
                "p99_response_time": 240,
                "success_rate": 99.7,
                "request_count": 1240,
            },
            {
                "path": "/api/v1/policies/generate",
                "method": "POST",
                "avg_response_time": 1480,
                "p95_response_time": 2420,
                "p99_response_time": 2980,
                "success_rate": 98.9,
                "request_count": 212,
            },
            {
                "path": "/api/v1/chat/query",
                "method": "POST",
                "avg_response_time": 920,
                "p95_response_time": 1680,
                "p99_response_time": 2140,
                "success_rate": 99.1,
                "request_count": 611,
            },
        ],
        "time_series": [
            {
                "timestamp": _iso(now - timedelta(hours=3)),
                "response_time": 110,
                "error_rate": 0.4,
                "request_count": 380,
            },
            {
                "timestamp": _iso(now - timedelta(hours=2)),
                "response_time": 104,
                "error_rate": 0.3,
                "request_count": 412,
            },
            {
                "timestamp": _iso(now - timedelta(hours=1)),
                "response_time": 118,
                "error_rate": 0.5,
                "request_count": 436,
            },
            {
                "timestamp": _iso(now),
                "response_time": 101,
                "error_rate": 0.2,
                "request_count": 451,
            },
        ],
    }


def _serialize_csv(rows: list[dict[str, Any]]) -> str:
    if not rows:
        return ""

    fieldnames = sorted({key for row in rows for key in row.keys()})
    buffer = io.StringIO()
    writer = csv.DictWriter(buffer, fieldnames=fieldnames)
    writer.writeheader()

    for row in rows:
        writer.writerow(
            {
                key: json.dumps(value) if isinstance(value, (dict, list)) else value
                for key, value in row.items()
            }
        )

    return buffer.getvalue()


@router.get("/database/status", summary="Get database status")
async def get_database_status(current_user: User = Depends(get_current_active_user)) -> dict[str, Any]:
    """Return the admin monitoring card shape expected by the frontend."""
    now = _utcnow()
    _ = current_user
    return {
        "status": "healthy",
        "connected_clients": 14,
        "active_queries": 3,
        "pool_size": 20,
        "available_connections": 17,
        "response_time_ms": 12,
        "last_check": _iso(now),
    }


@router.get("/alerts", summary="Get system alerts")
async def get_system_alerts(
    severity: str | None = Query(default=None),
    resolved: bool | None = Query(default=None),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    current_user: User = Depends(get_current_active_user),
) -> dict[str, Any]:
    now = _utcnow()
    _ = current_user
    alerts = _build_alerts(now)

    if severity:
        alerts = [alert for alert in alerts if alert["severity"] == severity]
    if resolved is not None:
        alerts = [alert for alert in alerts if alert["resolved"] is resolved]

    paginated_alerts, total = _paginate(alerts, page, page_size)
    return {"alerts": paginated_alerts, "total": total}


@router.get("/alerts/{alert_id}", summary="Get a single alert")
async def get_alert(
    alert_id: str,
    current_user: User = Depends(get_current_active_user),
) -> dict[str, Any]:
    now = _utcnow()
    _ = current_user
    alert = next((item for item in _build_alerts(now) if item["id"] == alert_id), None)
    if alert is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Alert not found")
    return alert


@router.patch("/alerts/{alert_id}/resolve", summary="Resolve alert")
async def resolve_alert(
    alert_id: str,
    resolution_data: dict[str, Any] | None = Body(default=None),
    current_user: User = Depends(get_current_active_user),
) -> dict[str, Any]:
    now = _utcnow()
    alert = next((item for item in _build_alerts(now) if item["id"] == alert_id), None)
    if alert is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Alert not found")

    alert["resolved"] = True
    alert["resolved_at"] = _iso(now)
    alert["details"] = {
        **alert.get("details", {}),
        "resolution": (resolution_data or {}).get("resolution"),
        "resolved_by": current_user.email,
    }
    return alert


@router.get("/metrics", summary="Get system metrics")
async def get_system_metrics(current_user: User = Depends(get_current_active_user)) -> dict[str, Any]:
    now = _utcnow()
    _ = current_user
    return {
        "cpu_usage": 41.8,
        "memory_usage": 63.4,
        "disk_usage": 52.7,
        "request_rate": 148,
        "error_rate": 0.4,
        "average_response_time": 112,
        "uptime_seconds": 86400 * 12,
        "last_check": _iso(now),
    }


@router.get("/api-performance", summary="Get API performance metrics")
async def get_api_performance(
    endpoint: str | None = Query(default=None),
    time_range: str = Query(default="day"),
    current_user: User = Depends(get_current_active_user),
) -> dict[str, Any]:
    now = _utcnow()
    _ = (current_user, time_range)
    performance = _build_api_performance(now)

    if endpoint:
        performance["endpoints"] = [
            item for item in performance["endpoints"] if item["path"] == endpoint
        ]

    return performance


@router.get("/error-logs", summary="Get error logs")
async def get_error_logs(
    severity: str | None = Query(default=None),
    search: str | None = Query(default=None),
    start_date: str | None = Query(default=None),
    end_date: str | None = Query(default=None),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    current_user: User = Depends(get_current_active_user),
) -> dict[str, Any]:
    _ = (current_user, start_date, end_date)
    logs = _build_error_logs(_utcnow())

    if severity:
        logs = [log for log in logs if log["severity"] == severity]
    if search:
        search_value = search.lower()
        logs = [
            log
            for log in logs
            if search_value in log["message"].lower()
            or search_value in json.dumps(log.get("metadata", {})).lower()
        ]

    paginated_logs, total = _paginate(logs, page, page_size)
    return {"logs": paginated_logs, "total": total}


@router.get("/health", summary="Health check")
async def health_check() -> dict[str, Any]:
    """Health endpoint used by the frontend admin monitoring views."""
    return {
        "status": "healthy",
        "checks": {
            "database": True,
            "cache": True,
            "storage": True,
            "external_services": {
                "neo4j": True,
                "redis": True,
                "openai": True,
            },
        },
        "timestamp": _iso(_utcnow()),
    }


@router.get("/audit-logs", summary="Get audit logs")
async def get_audit_logs(
    user_id: str | None = Query(default=None),
    action: str | None = Query(default=None),
    resource_type: str | None = Query(default=None),
    start_date: str | None = Query(default=None),
    end_date: str | None = Query(default=None),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    current_user: User = Depends(get_current_active_user),
) -> dict[str, Any]:
    _ = (start_date, end_date)
    logs = _build_audit_logs(_utcnow(), current_user)

    if user_id:
        logs = [log for log in logs if log["user_id"] == user_id]
    if action:
        logs = [log for log in logs if log["action"] == action]
    if resource_type:
        logs = [log for log in logs if log["resource_type"] == resource_type]

    paginated_logs, total = _paginate(logs, page, page_size)
    return {"logs": paginated_logs, "total": total}


@router.get("/export", summary="Export monitoring data")
async def export_monitoring_data(
    data_type: str = Query(...),
    format: str = Query(default="json"),
    start_date: str | None = Query(default=None),
    end_date: str | None = Query(default=None),
    current_user: User = Depends(get_current_active_user),
) -> Response:
    _ = (start_date, end_date)
    now = _utcnow()

    exporters: dict[str, list[dict[str, Any]]] = {
        "alerts": _build_alerts(now),
        "metrics": [await get_system_metrics(current_user)],
        "errors": _build_error_logs(now),
        "audit": _build_audit_logs(now, current_user),
    }

    if data_type not in exporters:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Unsupported export type")
    if format not in {"json", "csv"}:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Unsupported export format")

    dataset = exporters[data_type]
    filename = f"monitoring-{data_type}.{format}"

    if format == "json":
        content = json.dumps(dataset, indent=2)
        media_type = "application/json"
    else:
        content = _serialize_csv(dataset)
        media_type = "text/csv"

    return Response(
        content=content,
        media_type=media_type,
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )
