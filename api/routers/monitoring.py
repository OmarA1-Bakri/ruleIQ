"""
Monitoring API endpoints aligned with the frontend monitoring service contract.
"""

from __future__ import annotations

import csv
import io
import json
import os
import time
from datetime import datetime, timedelta, timezone
from typing import Any

import psutil
from fastapi import APIRouter, Body, Depends, HTTPException, Query, status
from fastapi.responses import Response
from sqlalchemy import desc, func, select, text
from sqlalchemy.ext.asyncio import AsyncSession

from api.dependencies.auth import get_current_active_user
from api.dependencies.token_blacklist import get_token_blacklist
from app.core.monitoring.metrics import get_metrics
from config.cache import get_cache_manager
from database.db_setup import get_async_db, get_engine_info
from database.models.integrations import (
    EvidenceAuditLog,
    EvidenceCollection,
    Integration,
    IntegrationHealthLog,
)
from database.user import User

router = APIRouter()

PROCESS = psutil.Process()
ALERT_RESOLUTIONS_KEY = "monitoring:resolved_alerts"
ERROR_LOG_LOOKBACK_DAYS = 14
SEVERITY_ORDER = {"critical": 0, "warning": 1, "info": 2}


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _ensure_aware(timestamp: datetime) -> datetime:
    if timestamp.tzinfo is None:
        return timestamp.replace(tzinfo=timezone.utc)
    return timestamp.astimezone(timezone.utc)


def _iso(timestamp: datetime) -> str:
    return _ensure_aware(timestamp).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _parse_datetime(value: str | None, field_name: str) -> datetime | None:
    if not value:
        return None
    try:
        return _ensure_aware(datetime.fromisoformat(value.replace("Z", "+00:00")))
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid {field_name}; expected ISO-8601 timestamp.",
        ) from exc


def _decode_cache_payload(value: Any) -> Any:
    if isinstance(value, str):
        try:
            return json.loads(value)
        except json.JSONDecodeError:
            return value
    return value


def _coerce_mapping(value: Any) -> dict[str, Any]:
    decoded = _decode_cache_payload(value)
    return decoded if isinstance(decoded, dict) else {}


def _coerce_list(value: Any) -> list[Any]:
    decoded = _decode_cache_payload(value)
    return decoded if isinstance(decoded, list) else []


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


def _paginate(items: list[dict[str, Any]], page: int, page_size: int) -> tuple[list[dict[str, Any]], int]:
    total = len(items)
    start = (page - 1) * page_size
    end = start + page_size
    return items[start:end], total


def _build_time_buckets(now: datetime, time_range: str) -> tuple[list[datetime], timedelta]:
    range_map = {
        "hour": (timedelta(hours=1), 6),
        "day": (timedelta(days=1), 6),
        "week": (timedelta(days=7), 7),
        "month": (timedelta(days=30), 6),
    }
    duration, bucket_count = range_map.get(time_range, range_map["day"])
    bucket_size = duration / bucket_count
    start = now - duration
    buckets = [start + (bucket_size * index) for index in range(bucket_count)]
    return buckets, bucket_size


def _bucket_index(timestamp: datetime, buckets: list[datetime], bucket_size: timedelta) -> int | None:
    if not buckets or timestamp < buckets[0]:
        return None
    seconds = (timestamp - buckets[0]).total_seconds()
    bucket_seconds = max(bucket_size.total_seconds(), 1)
    index = int(seconds // bucket_seconds)
    return min(index, len(buckets) - 1)


def _collection_timestamp(collection: EvidenceCollection) -> datetime:
    for candidate in (
        collection.updated_at,
        collection.completed_at,
        collection.started_at,
        collection.created_at,
    ):
        if candidate is not None:
            return _ensure_aware(candidate)
    return _utcnow()


async def _load_alert_resolutions() -> dict[str, dict[str, Any]]:
    cache_manager = await get_cache_manager()
    payload = _decode_cache_payload(await cache_manager.get(ALERT_RESOLUTIONS_KEY))
    return payload if isinstance(payload, dict) else {}


async def _save_alert_resolution(
    alert_id: str, resolution: str | None, resolved_by: str, resolved_at: datetime
) -> None:
    cache_manager = await get_cache_manager()
    resolutions = await _load_alert_resolutions()
    resolutions[alert_id] = {
        "resolution": resolution,
        "resolved_by": resolved_by,
        "resolved_at": _iso(resolved_at),
    }
    await cache_manager.set(ALERT_RESOLUTIONS_KEY, resolutions, ttl=30 * 24 * 3600)


def _apply_alert_resolutions(
    alerts: list[dict[str, Any]], resolutions: dict[str, dict[str, Any]]
) -> list[dict[str, Any]]:
    resolved_alerts: list[dict[str, Any]] = []
    for alert in alerts:
        resolution = resolutions.get(alert["id"])
        resolved_alert = {**alert}
        if resolution:
            resolved_alert["resolved"] = True
            resolved_alert["resolved_at"] = resolution.get("resolved_at")
            resolved_alert["details"] = {
                **resolved_alert.get("details", {}),
                "resolution": resolution.get("resolution"),
                "resolved_by": resolution.get("resolved_by"),
            }
        else:
            resolved_alert["resolved"] = False
            resolved_alert.pop("resolved_at", None)
        resolved_alerts.append(resolved_alert)

    resolved_alerts.sort(
        key=lambda item: (
            item["resolved"],
            SEVERITY_ORDER.get(item["severity"], 99),
            item["created_at"],
        )
    )
    return resolved_alerts


async def _get_cache_snapshot() -> dict[str, Any]:
    cache_manager = await get_cache_manager()
    redis_configured = bool(os.getenv("REDIS_URL"))
    redis_ok = False
    cache_mode = "memory"

    if not cache_manager.cache_enabled:
        return {"cache_ok": False, "redis_ok": False, "cache_mode": "disabled"}

    if cache_manager.redis_client:
        try:
            await cache_manager.redis_client.ping()
            redis_ok = True
            cache_mode = "redis"
        except Exception:
            cache_mode = "memory_fallback" if redis_configured else "memory"
    elif redis_configured:
        cache_mode = "memory_fallback"

    return {"cache_ok": True, "redis_ok": redis_ok, "cache_mode": cache_mode}


async def _get_database_status_payload(session: AsyncSession) -> dict[str, Any]:
    now = _utcnow()
    engine_info = get_engine_info()
    pool_size = int(engine_info.get("async_pool_size") or engine_info.get("sync_pool_size") or 0)
    checked_in = int(
        engine_info.get("async_pool_checked_in") or engine_info.get("sync_pool_checked_in") or 0
    )
    checked_out = int(
        engine_info.get("async_pool_checked_out") or engine_info.get("sync_pool_checked_out") or 0
    )
    connected_clients = checked_in + checked_out
    active_queries = checked_out

    started = time.perf_counter()
    status_value = "healthy"
    try:
        await session.execute(text("SELECT 1"))
    except Exception:
        status_value = "down"
    response_time_ms = round((time.perf_counter() - started) * 1000, 2)

    if status_value != "down":
        try:
            result = await session.execute(
                text(
                    """
                    SELECT
                        count(*) FILTER (WHERE state <> 'idle') AS active_queries,
                        count(*) AS connected_clients
                    FROM pg_stat_activity
                    WHERE datname = current_database()
                    """
                )
            )
            row = result.mappings().first()
            if row:
                connected_clients = int(row.get("connected_clients") or connected_clients)
                active_queries = int(row.get("active_queries") or active_queries)
        except Exception:
            pass

        if response_time_ms > 200 or (pool_size and checked_out / pool_size >= 0.8):
            status_value = "degraded"

    available_connections = max(pool_size - checked_out, 0) if pool_size else 0
    return {
        "status": status_value,
        "connected_clients": connected_clients,
        "active_queries": active_queries,
        "pool_size": pool_size,
        "available_connections": available_connections,
        "response_time_ms": response_time_ms,
        "last_check": _iso(now),
    }


async def _get_system_metrics_payload(session: AsyncSession) -> dict[str, Any]:
    now = _utcnow()
    metrics_snapshot = get_metrics()
    requests_total = 0.0
    failed_requests_total = 0.0
    request_duration_sum = 0.0
    request_duration_count = 0.0

    for metric in metrics_snapshot.get("metrics", []):
        name = metric.get("name")
        if name == "http_requests_total":
            requests_total += float(metric.get("value") or 0)
        elif name == "http_requests_failed_total":
            failed_requests_total += float(metric.get("value") or 0)
        elif name == "http_request_duration_seconds":
            request_duration_sum += float(metric.get("sum") or 0)
            request_duration_count += float(metric.get("count") or 0)

    db_status = await _get_database_status_payload(session)
    memory = psutil.virtual_memory()
    disk = psutil.disk_usage(os.getcwd())
    uptime_seconds = max(int(time.time() - PROCESS.create_time()), 0)
    average_response_time = (
        round((request_duration_sum / request_duration_count) * 1000, 2)
        if request_duration_count
        else float(db_status["response_time_ms"])
    )

    return {
        "cpu_usage": round(psutil.cpu_percent(interval=0.1), 2),
        "memory_usage": round(memory.percent, 2),
        "disk_usage": round(disk.percent, 2),
        "request_rate": round(requests_total / max(uptime_seconds, 1), 2),
        "error_rate": round((failed_requests_total / requests_total) * 100, 2)
        if requests_total
        else 0.0,
        "average_response_time": average_response_time,
        "uptime_seconds": uptime_seconds,
        "last_check": _iso(now),
    }


async def _build_live_alerts(now: datetime, session: AsyncSession) -> list[dict[str, Any]]:
    alerts: list[dict[str, Any]] = []
    database_status = await _get_database_status_payload(session)
    cache_snapshot = await _get_cache_snapshot()

    if database_status["status"] != "healthy":
        alerts.append(
            {
                "id": "alert-database-health",
                "severity": "critical" if database_status["status"] == "down" else "warning",
                "type": "database_health",
                "message": "Database connectivity is degraded on the canonical API runtime.",
                "details": {
                    "status": database_status["status"],
                    "response_time_ms": database_status["response_time_ms"],
                    "active_queries": database_status["active_queries"],
                    "available_connections": database_status["available_connections"],
                },
                "created_at": database_status["last_check"],
            }
        )

    if cache_snapshot["cache_mode"] != "redis":
        alerts.append(
            {
                "id": "alert-cache-fallback",
                "severity": "warning" if os.getenv("REDIS_URL") else "info",
                "type": "cache_degraded",
                "message": "Redis cache is unavailable and the app is using the in-memory cache path.",
                "details": {
                    "cache_mode": cache_snapshot["cache_mode"],
                    "redis_configured": bool(os.getenv("REDIS_URL")),
                },
                "created_at": _iso(now),
            }
        )

    failed_sync_result = await session.execute(
        select(EvidenceCollection, Integration.provider)
        .join(Integration, Integration.id == EvidenceCollection.integration_id)
        .where(EvidenceCollection.status == "failed")
        .order_by(desc(EvidenceCollection.updated_at), desc(EvidenceCollection.created_at))
        .limit(25)
    )
    failed_sync_rows = failed_sync_result.all()
    if failed_sync_rows:
        providers = sorted({provider for _, provider in failed_sync_rows})
        latest_failure = max(_collection_timestamp(collection) for collection, _ in failed_sync_rows)
        alerts.append(
            {
                "id": "alert-evidence-sync-failures",
                "severity": "critical" if len(failed_sync_rows) >= 3 else "warning",
                "type": "integration_sync_failures",
                "message": f"{len(failed_sync_rows)} evidence sync job(s) have failed on the launch path.",
                "details": {
                    "providers": providers,
                    "failed_jobs": len(failed_sync_rows),
                    "latest_failure": _iso(latest_failure),
                },
                "created_at": _iso(latest_failure),
            }
        )

    backlog_result = await session.execute(
        select(EvidenceCollection, Integration.provider)
        .join(Integration, Integration.id == EvidenceCollection.integration_id)
        .where(EvidenceCollection.status.in_(["pending", "running"]))
        .order_by(EvidenceCollection.created_at.asc())
        .limit(50)
    )
    backlog_rows = backlog_result.all()
    if backlog_rows:
        oldest_collection = backlog_rows[0][0]
        oldest_timestamp = _collection_timestamp(oldest_collection)
        oldest_age_minutes = max(int((now - oldest_timestamp).total_seconds() // 60), 0)
        alerts.append(
            {
                "id": "alert-integration-sync-backlog",
                "severity": "warning" if oldest_age_minutes >= 30 or len(backlog_rows) >= 5 else "info",
                "type": "integration_sync_backlog",
                "message": "Integration sync backlog is building on the evidence ingestion queue.",
                "details": {
                    "queued_jobs": len(backlog_rows),
                    "oldest_job_age_minutes": oldest_age_minutes,
                    "providers": sorted({provider for _, provider in backlog_rows}),
                },
                "created_at": _iso(oldest_timestamp),
            }
        )

    health_log_result = await session.execute(
        select(IntegrationHealthLog, Integration.provider)
        .join(Integration, Integration.id == IntegrationHealthLog.integration_id)
        .where(IntegrationHealthLog.status.in_(["unhealthy", "degraded"]))
        .order_by(desc(IntegrationHealthLog.checked_at))
        .limit(25)
    )
    health_rows = health_log_result.all()
    if health_rows:
        unhealthy_providers = sorted(
            {provider for log, provider in health_rows if log.status == "unhealthy"}
        )
        degraded_providers = sorted(
            {provider for log, provider in health_rows if log.status == "degraded"}
        )
        latest_check = max(_ensure_aware(log.checked_at) for log, _ in health_rows)
        alerts.append(
            {
                "id": "alert-integration-health",
                "severity": "critical" if unhealthy_providers else "warning",
                "type": "integration_health",
                "message": "One or more launch integrations are reporting degraded health.",
                "details": {
                    "unhealthy_providers": unhealthy_providers,
                    "degraded_providers": degraded_providers,
                    "events": len(health_rows),
                },
                "created_at": _iso(latest_check),
            }
        )

    blacklist = await get_token_blacklist()
    blacklist_stats = await blacklist.get_blacklist_statistics()
    suspicious_patterns = int(blacklist_stats.get("suspicious_patterns_detected") or 0)
    blacklisted_today = int(blacklist_stats.get("blacklisted_today") or 0)
    if suspicious_patterns or blacklisted_today >= 25:
        alerts.append(
            {
                "id": "alert-token-patterns",
                "severity": "warning",
                "type": "token_blacklist_patterns",
                "message": "Token blacklist activity is elevated and warrants admin review.",
                "details": {
                    "blacklisted_today": blacklisted_today,
                    "suspicious_patterns_detected": suspicious_patterns,
                },
                "created_at": _iso(now),
            }
        )

    resolutions = await _load_alert_resolutions()
    return _apply_alert_resolutions(alerts, resolutions)


async def _build_error_logs(now: datetime, session: AsyncSession) -> list[dict[str, Any]]:
    logs: list[dict[str, Any]] = []
    since = now - timedelta(days=ERROR_LOG_LOOKBACK_DAYS)

    health_log_result = await session.execute(
        select(IntegrationHealthLog, Integration.provider)
        .join(Integration, Integration.id == IntegrationHealthLog.integration_id)
        .where(
            IntegrationHealthLog.checked_at >= since,
            IntegrationHealthLog.status.in_(["unhealthy", "degraded"]),
        )
        .order_by(desc(IntegrationHealthLog.checked_at))
        .limit(50)
    )
    for health_log, provider in health_log_result.all():
        error_details = _coerce_mapping(health_log.error_details)
        health_data = _coerce_mapping(health_log.health_data)
        response_time = _coerce_mapping(health_log.response_time)
        timestamp = _ensure_aware(health_log.checked_at)
        message = error_details.get(
            "message",
            f"{provider} integration health check reported {health_log.status}.",
        )
        logs.append(
            {
                "timestamp": _iso(timestamp),
                "severity": "error" if health_log.status == "unhealthy" else "warning",
                "message": message,
                "stack_trace": error_details.get("stack_trace") or error_details.get("error"),
                "request_id": error_details.get("request_id") or health_data.get("request_id"),
                "metadata": {
                    "provider": provider,
                    "status": health_log.status,
                    "health_data": health_data,
                    "response_time": response_time,
                },
            }
        )

    failed_collection_result = await session.execute(
        select(EvidenceCollection, Integration.provider)
        .join(Integration, Integration.id == EvidenceCollection.integration_id)
        .where(EvidenceCollection.updated_at >= since, EvidenceCollection.status == "failed")
        .order_by(desc(EvidenceCollection.updated_at), desc(EvidenceCollection.created_at))
        .limit(50)
    )
    for collection, provider in failed_collection_result.all():
        errors = _coerce_list(collection.errors)
        first_error = errors[0] if errors else None
        if isinstance(first_error, dict):
            error_message = first_error.get("message") or first_error.get("error")
            stack_trace = first_error.get("stack_trace")
        else:
            error_message = str(first_error) if first_error is not None else None
            stack_trace = None
        logs.append(
            {
                "timestamp": _iso(_collection_timestamp(collection)),
                "severity": "error",
                "message": error_message
                or collection.current_activity
                or "Evidence collection failed before completing the requested sync.",
                "stack_trace": stack_trace,
                "user_id": str(collection.user_id),
                "metadata": {
                    "provider": provider,
                    "framework_id": collection.framework_id,
                    "collection_mode": collection.collection_mode,
                    "progress_percentage": collection.progress_percentage,
                },
            }
        )

    cache_snapshot = await _get_cache_snapshot()
    if cache_snapshot["cache_mode"] != "redis" and os.getenv("REDIS_URL"):
        logs.append(
            {
                "timestamp": _iso(now),
                "severity": "warning",
                "message": "Redis is unavailable; monitoring is operating on the in-memory cache fallback.",
                "metadata": {"cache_mode": cache_snapshot["cache_mode"]},
            }
        )

    blacklist = await get_token_blacklist()
    blacklist_stats = await blacklist.get_blacklist_statistics()
    suspicious_patterns = int(blacklist_stats.get("suspicious_patterns_detected") or 0)
    if suspicious_patterns:
        logs.append(
            {
                "timestamp": _iso(now),
                "severity": "warning",
                "message": "Suspicious token blacklist patterns were detected by the auth cache monitor.",
                "metadata": {
                    "suspicious_patterns_detected": suspicious_patterns,
                    "blacklisted_today": blacklist_stats.get("blacklisted_today", 0),
                },
            }
        )

    logs.sort(key=lambda item: item["timestamp"], reverse=True)
    return logs


async def _build_audit_logs(
    session: AsyncSession,
    user_id: str | None,
    action: str | None,
    resource_type: str | None,
    start_date: str | None,
    end_date: str | None,
    page: int,
    page_size: int,
) -> dict[str, Any]:
    start_dt = _parse_datetime(start_date, "start_date")
    end_dt = _parse_datetime(end_date, "end_date")

    filters = []
    if user_id:
        filters.append(EvidenceAuditLog.user_id == user_id)
    if action:
        filters.append(EvidenceAuditLog.action == action)
    if resource_type:
        filters.append(EvidenceAuditLog.resource_type == resource_type)
    if start_dt:
        filters.append(EvidenceAuditLog.timestamp >= start_dt)
    if end_dt:
        filters.append(EvidenceAuditLog.timestamp <= end_dt)

    total = int(
        await session.scalar(select(func.count()).select_from(EvidenceAuditLog).where(*filters)) or 0
    )
    result = await session.execute(
        select(EvidenceAuditLog)
        .where(*filters)
        .order_by(desc(EvidenceAuditLog.timestamp))
        .offset((page - 1) * page_size)
        .limit(page_size)
    )

    logs = [
        {
            "id": str(log.id),
            "user_id": str(log.user_id),
            "action": log.action,
            "resource_type": log.resource_type,
            "resource_id": log.resource_id,
            "changes": _coerce_mapping(log.details),
            "ip_address": log.ip_address or "",
            "user_agent": log.user_agent or "",
            "timestamp": _iso(_ensure_aware(log.timestamp)),
        }
        for log in result.scalars().all()
    ]
    return {"logs": logs, "total": total}


async def _build_api_performance_payload(
    session: AsyncSession, now: datetime, endpoint: str | None, time_range: str
) -> dict[str, Any]:
    metrics_snapshot = get_metrics()
    endpoint_stats: dict[tuple[str, str], dict[str, float]] = {}

    for metric in metrics_snapshot.get("metrics", []):
        labels = metric.get("labels") or {}
        path = labels.get("path")
        method = labels.get("method")
        if not path or not method:
            continue
        key = (path, method)
        stats = endpoint_stats.setdefault(
            key,
            {
                "request_count": 0.0,
                "failed_count": 0.0,
                "duration_sum": 0.0,
                "duration_count": 0.0,
                "p95_ms": 0.0,
                "p99_ms": 0.0,
            },
        )
        if metric.get("name") == "http_requests_total":
            stats["request_count"] += float(metric.get("value") or 0)
        elif metric.get("name") == "http_requests_failed_total":
            stats["failed_count"] += float(metric.get("value") or 0)
        elif metric.get("name") == "http_request_duration_seconds":
            stats["duration_sum"] += float(metric.get("sum") or 0)
            stats["duration_count"] += float(metric.get("count") or 0)
            stats["p95_ms"] = max(stats["p95_ms"], float(metric.get("p95") or 0) * 1000)
            stats["p99_ms"] = max(stats["p99_ms"], float(metric.get("p99") or 0) * 1000)

    endpoints = []
    for (path, method), stats in endpoint_stats.items():
        if endpoint and path != endpoint:
            continue
        request_count = int(stats["request_count"])
        failed_count = int(stats["failed_count"])
        success_count = max(request_count - failed_count, 0)
        endpoints.append(
            {
                "path": path,
                "method": method,
                "avg_response_time": round(
                    (stats["duration_sum"] / stats["duration_count"]) * 1000, 2
                )
                if stats["duration_count"]
                else 0.0,
                "p95_response_time": round(stats["p95_ms"], 2),
                "p99_response_time": round(stats["p99_ms"], 2),
                "success_rate": round((success_count / request_count) * 100, 2)
                if request_count
                else 100.0,
                "request_count": request_count,
            }
        )

    if not endpoints:
        database_status = await _get_database_status_payload(session)
        endpoints = [
            {
                "path": endpoint or "/api/v1",
                "method": "ALL",
                "avg_response_time": float(database_status["response_time_ms"]),
                "p95_response_time": float(database_status["response_time_ms"]),
                "p99_response_time": float(database_status["response_time_ms"]),
                "success_rate": 100.0 if database_status["status"] != "down" else 0.0,
                "request_count": 0,
            }
        ]

    average_response_time = sum(item["avg_response_time"] for item in endpoints) / max(len(endpoints), 1)
    buckets, bucket_size = _build_time_buckets(now, time_range)
    time_series = [
        {
            "timestamp": _iso(bucket),
            "response_time": round(average_response_time, 2),
            "error_rate": 0.0,
            "request_count": 0,
        }
        for bucket in buckets
    ]

    since = buckets[0] if buckets else now
    audit_timestamps = (
        await session.execute(
            select(EvidenceAuditLog.timestamp).where(EvidenceAuditLog.timestamp >= since)
        )
    ).scalars().all()
    for timestamp in audit_timestamps:
        index = _bucket_index(_ensure_aware(timestamp), buckets, bucket_size)
        if index is not None:
            time_series[index]["request_count"] += 1

    health_rows = (
        await session.execute(
            select(IntegrationHealthLog.checked_at, IntegrationHealthLog.status).where(
                IntegrationHealthLog.checked_at >= since
            )
        )
    ).all()
    failed_rows = (
        await session.execute(
            select(EvidenceCollection.updated_at).where(
                EvidenceCollection.updated_at >= since,
                EvidenceCollection.status == "failed",
            )
        )
    ).scalars().all()

    bucket_errors: dict[int, int] = {}
    for checked_at, status_value in health_rows:
        if status_value not in {"unhealthy", "degraded"}:
            continue
        index = _bucket_index(_ensure_aware(checked_at), buckets, bucket_size)
        if index is not None:
            bucket_errors[index] = bucket_errors.get(index, 0) + 1
    for updated_at in failed_rows:
        if updated_at is None:
            continue
        index = _bucket_index(_ensure_aware(updated_at), buckets, bucket_size)
        if index is not None:
            bucket_errors[index] = bucket_errors.get(index, 0) + 1

    for index, series_point in enumerate(time_series):
        errors = bucket_errors.get(index, 0)
        requests = series_point["request_count"]
        if requests:
            series_point["error_rate"] = round((errors / requests) * 100, 2)
        elif errors:
            series_point["error_rate"] = 100.0
            series_point["request_count"] = errors

    return {"endpoints": endpoints, "time_series": time_series}


@router.get("/database/status", summary="Get database status")
async def get_database_status(
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_async_db),
) -> dict[str, Any]:
    """Return the admin monitoring card shape expected by the frontend."""
    _ = current_user
    return await _get_database_status_payload(db)


@router.get("/alerts", summary="Get system alerts")
async def get_system_alerts(
    severity: str | None = Query(default=None),
    resolved: bool | None = Query(default=None),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_async_db),
) -> dict[str, Any]:
    _ = current_user
    alerts = await _build_live_alerts(_utcnow(), db)

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
    db: AsyncSession = Depends(get_async_db),
) -> dict[str, Any]:
    _ = current_user
    alert = next((item for item in await _build_live_alerts(_utcnow(), db) if item["id"] == alert_id), None)
    if alert is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Alert not found")
    return alert


@router.patch("/alerts/{alert_id}/resolve", summary="Resolve alert")
async def resolve_alert(
    alert_id: str,
    resolution_data: dict[str, Any] | None = Body(default=None),
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_async_db),
) -> dict[str, Any]:
    alert = next((item for item in await _build_live_alerts(_utcnow(), db) if item["id"] == alert_id), None)
    if alert is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Alert not found")

    resolved_at = _utcnow()
    await _save_alert_resolution(
        alert_id=alert_id,
        resolution=(resolution_data or {}).get("resolution"),
        resolved_by=current_user.email,
        resolved_at=resolved_at,
    )
    resolutions = await _load_alert_resolutions()
    return next(item for item in _apply_alert_resolutions([alert], resolutions) if item["id"] == alert_id)


@router.get("/metrics", summary="Get system metrics")
async def get_system_metrics(
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_async_db),
) -> dict[str, Any]:
    _ = current_user
    return await _get_system_metrics_payload(db)


@router.get("/api-performance", summary="Get API performance metrics")
async def get_api_performance(
    endpoint: str | None = Query(default=None),
    time_range: str = Query(default="day"),
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_async_db),
) -> dict[str, Any]:
    _ = current_user
    return await _build_api_performance_payload(db, _utcnow(), endpoint, time_range)


@router.get("/error-logs", summary="Get error logs")
async def get_error_logs(
    severity: str | None = Query(default=None),
    search: str | None = Query(default=None),
    start_date: str | None = Query(default=None),
    end_date: str | None = Query(default=None),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_async_db),
) -> dict[str, Any]:
    _ = current_user
    start_dt = _parse_datetime(start_date, "start_date")
    end_dt = _parse_datetime(end_date, "end_date")
    logs = await _build_error_logs(_utcnow(), db)

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
    if start_dt:
        logs = [log for log in logs if _parse_datetime(log["timestamp"], "timestamp") >= start_dt]
    if end_dt:
        logs = [log for log in logs if _parse_datetime(log["timestamp"], "timestamp") <= end_dt]

    paginated_logs, total = _paginate(logs, page, page_size)
    return {"logs": paginated_logs, "total": total}


@router.get("/health", summary="Health check")
async def health_check(
    db: AsyncSession = Depends(get_async_db),
) -> dict[str, Any]:
    """Health endpoint used by the frontend admin monitoring views."""
    now = _utcnow()
    database_status = await _get_database_status_payload(db)
    cache_snapshot = await _get_cache_snapshot()
    disk = psutil.disk_usage(os.getcwd())

    external_services = {
        "neo4j": bool(os.getenv("NEO4J_URI") or os.getenv("NEO4J_URL")),
        "redis": cache_snapshot["redis_ok"],
        "openai": bool(
            os.getenv("GOOGLE_API_KEY")
            or os.getenv("OPENAI_API_KEY")
            or os.getenv("USE_MOCK_AI", "false").lower() == "true"
        ),
    }
    checks = {
        "database": database_status["status"] != "down",
        "cache": cache_snapshot["cache_ok"],
        "storage": disk.percent < 95,
        "external_services": external_services,
    }

    overall_status = "healthy"
    if not checks["database"] or not checks["storage"]:
        overall_status = "unhealthy"
    elif not cache_snapshot["redis_ok"] or not all(external_services.values()):
        overall_status = "degraded"

    return {
        "status": overall_status,
        "checks": checks,
        "timestamp": _iso(now),
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
    db: AsyncSession = Depends(get_async_db),
) -> dict[str, Any]:
    _ = current_user
    return await _build_audit_logs(
        session=db,
        user_id=user_id,
        action=action,
        resource_type=resource_type,
        start_date=start_date,
        end_date=end_date,
        page=page,
        page_size=page_size,
    )


@router.get("/export", summary="Export monitoring data")
async def export_monitoring_data(
    data_type: str = Query(...),
    format: str = Query(default="json"),
    start_date: str | None = Query(default=None),
    end_date: str | None = Query(default=None),
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_async_db),
) -> Response:
    _ = current_user
    now = _utcnow()

    exporters: dict[str, list[dict[str, Any]]] = {
        "alerts": await _build_live_alerts(now, db),
        "metrics": [await _get_system_metrics_payload(db)],
        "errors": await _build_error_logs(now, db),
        "audit": (
            await _build_audit_logs(
                session=db,
                user_id=None,
                action=None,
                resource_type=None,
                start_date=start_date,
                end_date=end_date,
                page=1,
                page_size=1000,
            )
        )["logs"],
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
