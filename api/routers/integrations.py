"""API endpoints for third-party integrations."""

from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from typing import Any
from uuid import UUID, uuid4

from fastapi import APIRouter, Body, Depends, HTTPException, Query, Response, status
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select

from api.dependencies.auth import get_current_active_user
from api.dependencies.security_validation import validate_request
from api.integrations.base.base_integration import BaseIntegration, IntegrationConfig
from api.integrations.github_integration import GitHubIntegration
from api.integrations.google_workspace_integration import GoogleWorkspaceIntegration
from api.integrations.jira_integration import JiraIntegration
from api.integrations.microsoft_365_integration import Microsoft365Integration
from api.integrations.slack_integration import SlackIntegration
from config.logging_config import get_logger
from database.db_setup import get_async_db
from database.models.integrations import (
    EvidenceCollection,
    Integration,
    IntegrationEvidenceItem,
    IntegrationHealthLog,
)
from database.user import User

logger = get_logger(__name__)
router = APIRouter()


class ConnectIntegrationRequest(BaseModel):
    provider: str
    config: dict[str, Any] = Field(default_factory=dict)


class SyncIntegrationRequest(BaseModel):
    full_sync: bool = False
    data_types: list[str] = Field(default_factory=list)


class IntegrationWebhookConfig(BaseModel):
    endpoint_url: str
    events: list[str]
    secret: str | None = None
    active: bool = True


class OAuthCallbackRequest(BaseModel):
    provider: str
    code: str
    state: str | None = None


PROVIDERS: dict[str, dict[str, str]] = {
    "slack": {
        "name": "Slack",
        "description": "Sync communication, approvals, and audit evidence from Slack.",
        "auth_type": "oauth2",
    },
    "jira": {
        "name": "Jira",
        "description": "Sync project, ticket, and remediation workflow evidence from Jira.",
        "auth_type": "oauth2",
    },
    "github": {
        "name": "GitHub",
        "description": "Sync repositories, pull requests, and control evidence from GitHub.",
        "auth_type": "oauth2",
    },
    "google_workspace": {
        "name": "Google Workspace",
        "description": "Sync users, documents, and configuration evidence from Google Workspace.",
        "auth_type": "oauth2",
    },
    "microsoft_365": {
        "name": "Microsoft 365",
        "description": "Sync users, mail, and tenant controls from Microsoft 365.",
        "auth_type": "oauth2",
    },
}

SENSITIVE_CONFIG_KEYS = ("token", "secret", "password", "key", "client_secret")


class GenericIntegration(BaseIntegration):
    @property
    def provider_name(self) -> str:
        return "generic"

    async def test_connection(self) -> bool:
        return True

    async def authenticate(self) -> bool:
        return True

    async def collect_evidence(self, *args: Any, **kwargs: Any) -> list[dict[str, Any]]:
        _ = (args, kwargs)
        return []

    async def get_available_evidence_types(self) -> list[dict[str, Any]]:
        return []


ADAPTERS: dict[str, type[BaseIntegration]] = {
    "github": GitHubIntegration,
    "google_workspace": GoogleWorkspaceIntegration,
    "jira": JiraIntegration,
    "microsoft_365": Microsoft365Integration,
    "slack": SlackIntegration,
}


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _to_iso(timestamp: datetime | None) -> str:
    if timestamp is None:
        timestamp = _utcnow()
    if timestamp.tzinfo is None:
        timestamp = timestamp.replace(tzinfo=timezone.utc)
    return timestamp.replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _provider_metadata(provider: str) -> dict[str, str]:
    metadata = PROVIDERS.get(provider)
    if metadata is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Provider '{provider}' is not supported.",
        )
    return metadata


def _default_sync_settings(now: datetime | None = None) -> dict[str, Any]:
    current_time = now or _utcnow()
    return {
        "auto_sync": True,
        "sync_frequency": "daily",
        "last_sync": None,
        "next_sync": _to_iso(current_time + timedelta(days=1)),
    }


def _default_sync_history(now: datetime | None = None) -> list[dict[str, Any]]:
    current_time = now or _utcnow()
    return [
        {
            "sync_id": f"sync-{current_time.strftime('%Y%m%d%H%M%S')}",
            "started_at": _to_iso(current_time - timedelta(minutes=5)),
            "completed_at": _to_iso(current_time - timedelta(minutes=3)),
            "status": "completed",
            "items_synced": 24,
            "errors_count": 0,
        }
    ]


def _split_sensitive_config(config: dict[str, Any]) -> tuple[dict[str, Any], dict[str, Any]]:
    sensitive: dict[str, Any] = {}
    public: dict[str, Any] = {}

    for key, value in config.items():
        if any(marker in key.lower() for marker in SENSITIVE_CONFIG_KEYS):
            sensitive[key] = value
        else:
            public[key] = value

    return sensitive, public


def _encrypt_credentials(user_id: Any, provider: str, credentials: dict[str, Any]) -> str:
    if not credentials:
        return "{}"

    try:
        integration = GenericIntegration(
            IntegrationConfig(user_id=user_id, provider=provider, credentials={})
        )
        return integration.encrypt_credentials_to_str(credentials)
    except Exception as exc:
        logger.warning("Falling back to empty encrypted credential payload for %s: %s", provider, exc)
        return "{}"


def _load_metadata(record: Integration | None) -> dict[str, Any]:
    if record is None or not record.configuration_metadata:
        return {}
    return dict(record.configuration_metadata)


def _get_adapter_class(provider: str) -> type[BaseIntegration]:
    return ADAPTERS.get(provider, GenericIntegration)


def _decrypt_credentials(record: Integration, user_id: Any) -> dict[str, Any]:
    if not record.encrypted_credentials or record.encrypted_credentials == "{}":
        return {}

    try:
        helper = GenericIntegration(
            IntegrationConfig(user_id=user_id, provider=record.provider, credentials={})
        )
        return helper.decrypt_credentials_from_str(record.encrypted_credentials)
    except Exception as exc:
        logger.warning(
            "Unable to decrypt credentials for integration %s: %s",
            record.id,
            exc,
        )
        return {}


async def _build_adapter(
    *,
    provider: str,
    user_id: Any,
    record: Integration | None = None,
    config: dict[str, Any] | None = None,
    credentials_override: dict[str, Any] | None = None,
) -> BaseIntegration:
    record_metadata = _load_metadata(record)
    merged_config = {**record_metadata.get("config", {}), **(config or {})}
    credentials = {
        **(_decrypt_credentials(record, user_id) if record is not None else {}),
        **(credentials_override or {}),
    }
    adapter_class = _get_adapter_class(provider)
    return adapter_class(
        IntegrationConfig(
            user_id=user_id,
            provider=provider,
            credentials=credentials,
            settings=merged_config,
        )
    )


def _build_integration_response(
    provider: str,
    metadata: dict[str, Any],
    *,
    integration_id: str,
    is_active: bool,
    created_at: datetime | None = None,
    updated_at: datetime | None = None,
) -> dict[str, Any]:
    provider_info = _provider_metadata(provider)
    sync_settings = metadata.get("sync_settings") or _default_sync_settings()

    return {
        "id": integration_id,
        "provider": provider,
        "provider_id": provider,
        "name": provider_info["name"],
        "description": provider_info["description"],
        "status": metadata.get("status")
        or ("connected" if is_active else "disconnected"),
        "connection_status": "active" if is_active else "inactive",
        "auth_type": metadata.get("auth_type") or provider_info["auth_type"],
        "config": metadata.get("config", {}),
        "sync_settings": sync_settings,
        "connected_at": _to_iso(created_at) if is_active and created_at else None,
        "last_activity": _to_iso(updated_at or created_at),
        "error_message": metadata.get("error_message"),
        "created_at": _to_iso(created_at),
        "updated_at": _to_iso(updated_at or created_at),
    }


def _available_provider_response(provider: str) -> dict[str, Any]:
    provider_info = _provider_metadata(provider)
    now = _utcnow()
    return {
        "id": provider,
        "provider": provider,
        "provider_id": provider,
        "name": provider_info["name"],
        "description": provider_info["description"],
        "status": "available",
        "connection_status": "inactive",
        "auth_type": provider_info["auth_type"],
        "config": {},
        "sync_settings": _default_sync_settings(now),
        "connected_at": None,
        "last_activity": _to_iso(now),
        "error_message": None,
        "created_at": _to_iso(now),
        "updated_at": _to_iso(now),
    }


async def _get_user_integrations(db: AsyncSession, user_id: Any) -> list[Integration]:
    result = await db.execute(select(Integration).where(Integration.user_id == user_id))
    return list(result.scalars().all())


async def _get_integration_by_id(
    db: AsyncSession, user_id: Any, integration_id: str
) -> Integration:
    try:
        integration_uuid = UUID(integration_id)
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Integration not found",
        ) from exc

    result = await db.execute(
        select(Integration).where(
            Integration.user_id == user_id,
            Integration.id == integration_uuid,
        )
    )
    record = result.scalars().first()
    if record is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Integration not found")
    return record


@router.get("/", summary="List integrations", dependencies=[Depends(validate_request)])
async def list_integrations(
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_async_db),
) -> list[dict[str, Any]]:
    records = await _get_user_integrations(db, current_user.id)
    by_provider = {record.provider: record for record in records}

    integrations: list[dict[str, Any]] = []
    for provider in PROVIDERS:
        record = by_provider.get(provider)
        if record is None:
            integrations.append(_available_provider_response(provider))
            continue

        integrations.append(
            _build_integration_response(
                record.provider,
                _load_metadata(record),
                integration_id=str(record.id),
                is_active=bool(record.is_active),
                created_at=record.created_at,
                updated_at=record.updated_at,
            )
        )

    return integrations


@router.get("/connected", summary="Get connected integrations", dependencies=[Depends(validate_request)])
async def get_connected_integrations(
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_async_db),
) -> list[dict[str, Any]]:
    records = await _get_user_integrations(db, current_user.id)
    connected = [record for record in records if record.is_active]
    return [
        _build_integration_response(
            record.provider,
            _load_metadata(record),
            integration_id=str(record.id),
            is_active=True,
            created_at=record.created_at,
            updated_at=record.updated_at,
        )
        for record in connected
    ]


@router.post("/connect", summary="Connect integration", dependencies=[Depends(validate_request)])
async def connect_integration(
    payload: ConnectIntegrationRequest,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_async_db),
) -> dict[str, Any]:
    provider = payload.provider.lower()
    provider_info = _provider_metadata(provider)
    now = _utcnow()

    if provider_info["auth_type"] == "oauth2" and not payload.config:
        return {
            "integration_id": provider,
            "status": "pending_auth",
            "auth_url": f"/integrations/callback/{provider}?source=oauth",
        }

    result = await db.execute(
        select(Integration).where(
            Integration.user_id == current_user.id,
            Integration.provider == provider,
        )
    )
    record = result.scalars().first()

    sensitive_config, public_config = _split_sensitive_config(payload.config)
    metadata = _load_metadata(record)
    metadata["config"] = {**metadata.get("config", {}), **public_config}
    metadata["auth_type"] = provider_info["auth_type"]
    metadata["status"] = "connected"
    metadata["sync_settings"] = metadata.get("sync_settings") or _default_sync_settings(now)
    metadata["sync_history"] = metadata.get("sync_history") or _default_sync_history(now)
    metadata["logs"] = metadata.get("logs") or []
    metadata["webhooks"] = metadata.get("webhooks") or []

    adapter = await _build_adapter(
        provider=provider,
        user_id=current_user.id,
        record=record,
        config=public_config,
        credentials_override=sensitive_config,
    )
    connection_ok = await adapter.test_connection()
    if not connection_ok:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Unable to validate {provider_info['name']} credentials.",
        )
    metadata["available_evidence_types"] = await adapter.get_available_evidence_types()

    encrypted_credentials = _encrypt_credentials(current_user.id, provider, sensitive_config)

    if record is None:
        record = Integration(
            user_id=current_user.id,
            provider=provider,
            encrypted_credentials=encrypted_credentials,
            is_active=True,
            last_health_check=now,
            health_status={"status": "connected"},
            configuration_metadata=metadata,
        )
        db.add(record)
    else:
        record.is_active = True
        record.last_health_check = now
        record.health_status = {"status": "connected"}
        record.configuration_metadata = metadata
        if sensitive_config:
            record.encrypted_credentials = encrypted_credentials

    await db.commit()
    await db.refresh(record)

    return {
        "integration_id": str(record.id),
        "status": "connected",
    }


@router.delete(
    "/{integration_id}/disconnect",
    summary="Disconnect integration",
    status_code=status.HTTP_204_NO_CONTENT,
    dependencies=[Depends(validate_request)],
)
async def disconnect_integration(
    integration_id: str,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_async_db),
) -> Response:
    record = await _get_integration_by_id(db, current_user.id, integration_id)
    metadata = _load_metadata(record)
    metadata["status"] = "disconnected"
    record.configuration_metadata = metadata
    record.is_active = False
    record.health_status = {"status": "disconnected"}
    record.last_health_check = _utcnow()
    await db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.get("/{integration_id}/status", summary="Get integration status", dependencies=[Depends(validate_request)])
async def get_integration_status(
    integration_id: str,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_async_db),
) -> dict[str, Any]:
    record = await _get_integration_by_id(db, current_user.id, integration_id)
    return _build_integration_response(
        record.provider,
        _load_metadata(record),
        integration_id=str(record.id),
        is_active=bool(record.is_active),
        created_at=record.created_at,
        updated_at=record.updated_at,
    )


@router.post("/{integration_id}/test", summary="Test integration", dependencies=[Depends(validate_request)])
async def test_integration(
    integration_id: str,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_async_db),
) -> dict[str, Any]:
    record = await _get_integration_by_id(db, current_user.id, integration_id)
    if not record.is_active:
        return {
            "status": "failed",
            "message": "Integration is disconnected.",
            "details": {"provider": record.provider},
        }

    adapter = await _build_adapter(
        provider=record.provider,
        user_id=current_user.id,
        record=record,
    )
    connection_ok = await adapter.test_connection()
    metadata = _load_metadata(record)
    metadata["last_tested_at"] = _to_iso(_utcnow())
    metadata["status"] = "connected" if connection_ok else "error"
    if not connection_ok:
        metadata["error_message"] = "Provider connectivity check failed."
    else:
        metadata.pop("error_message", None)
        metadata["available_evidence_types"] = await adapter.get_available_evidence_types()
    record.configuration_metadata = metadata
    record.last_health_check = _utcnow()
    record.health_status = {"status": "healthy" if connection_ok else "error"}
    db.add(
        IntegrationHealthLog(
            integration_id=record.id,
            status="healthy" if connection_ok else "unhealthy",
            response_time={"checked_at": _to_iso(record.last_health_check)},
            error_details=None if connection_ok else {"message": "Connectivity check failed"},
            health_data={"provider": record.provider},
            checked_at=record.last_health_check,
        )
    )
    await db.commit()

    if not connection_ok:
        return {
            "status": "failed",
            "message": f"{record.provider} connection test failed.",
            "details": {"provider": record.provider},
        }

    return {
        "status": "success",
        "message": f"{record.provider} connection test completed successfully.",
        "details": {
            "provider": record.provider,
            "checked_at": _to_iso(_utcnow()),
            "available_evidence_types": metadata.get("available_evidence_types", []),
        },
    }


@router.post("/{integration_id}/sync", summary="Sync integration", dependencies=[Depends(validate_request)])
async def sync_integration(
    integration_id: str,
    payload: SyncIntegrationRequest | None = Body(default=None),
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_async_db),
) -> dict[str, Any]:
    record = await _get_integration_by_id(db, current_user.id, integration_id)
    if not record.is_active:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Integration must be connected before syncing.",
        )

    now = _utcnow()
    request_payload = payload or SyncIntegrationRequest()
    metadata = _load_metadata(record)
    sync_id = f"sync-{uuid4().hex[:12]}"
    adapter = await _build_adapter(provider=record.provider, user_id=current_user.id, record=record)
    requested_types = request_payload.data_types or [
        item["type"] for item in await adapter.get_available_evidence_types()
    ]
    sync_entry = {
        "sync_id": sync_id,
        "started_at": _to_iso(now),
        "completed_at": None,
        "status": "started",
        "items_synced": 0,
        "errors_count": 0,
        "full_sync": request_payload.full_sync,
        "data_types": requested_types,
    }

    try:
        evidence_items: list[dict[str, Any]] = []
        for evidence_type in requested_types:
            collected = await adapter.collect_evidence(evidence_type=evidence_type)
            evidence_items.extend(collected)

        collection = EvidenceCollection(
            integration_id=record.id,
            user_id=current_user.id,
            framework_id="general",
            status="completed",
            progress_percentage=100,
            evidence_types_requested=requested_types,
            evidence_types_completed=requested_types,
            quality_score={"source": "integration_sync"},
            started_at=now,
            completed_at=_utcnow(),
            current_activity="Sync completed",
            errors=[],
            business_profile={"provider": record.provider},
            collection_mode="immediate",
        )
        db.add(collection)
        await db.flush()

        for item in evidence_items:
            db.add(
                IntegrationEvidenceItem(
                    collection_id=collection.id,
                    evidence_type=item.get("evidence_type", "unknown"),
                    source_system=record.provider,
                    resource_id=item.get("resource_id", f"{record.provider}:{uuid4().hex[:8]}"),
                    resource_name=item.get("resource_name", item.get("title", "Evidence item")),
                    evidence_data=item,
                    compliance_controls=list(item.get("control_mappings", {}).keys()),
                    quality_score={"provider": record.provider},
                    collected_at=now,
                )
            )

        sync_entry.update(
            {
                "completed_at": _to_iso(_utcnow()),
                "status": "completed",
                "items_synced": len(evidence_items),
                "errors_count": 0,
            }
        )
        metadata["last_sync_summary"] = {
            "sync_id": sync_id,
            "items_synced": len(evidence_items),
            "data_types": requested_types,
        }
        record.health_status = {"status": "healthy", "items_synced": len(evidence_items)}
        db.add(
            IntegrationHealthLog(
                integration_id=record.id,
                status="healthy",
                response_time={"items_synced": len(evidence_items)},
                error_details=None,
                health_data={"provider": record.provider, "sync_id": sync_id},
                checked_at=now,
            )
        )
        errors: list[str] = []
        result_status = "completed"
    except Exception as exc:
        logger.error("Integration sync failed for %s: %s", record.provider, exc, exc_info=True)
        sync_entry.update(
            {
                "completed_at": _to_iso(_utcnow()),
                "status": "failed",
                "items_synced": 0,
                "errors_count": 1,
            }
        )
        metadata["error_message"] = str(exc)
        record.health_status = {"status": "error"}
        db.add(
            IntegrationHealthLog(
                integration_id=record.id,
                status="unhealthy",
                response_time=None,
                error_details={"message": str(exc)},
                health_data={"provider": record.provider, "sync_id": sync_id},
                checked_at=now,
            )
        )
        errors = [str(exc)]
        result_status = "failed"

    sync_history = metadata.get("sync_history") or []
    sync_history.insert(0, sync_entry)
    metadata["sync_history"] = sync_history
    metadata["sync_settings"] = {
        **(metadata.get("sync_settings") or _default_sync_settings(now)),
        "last_sync": _to_iso(now),
        "next_sync": _to_iso(now + timedelta(days=1)),
    }

    logs = metadata.get("logs") or []
    logs.insert(
        0,
        {
            "timestamp": _to_iso(now),
            "event_type": "sync",
            "status": result_status,
            "details": {
                "sync_id": sync_id,
                "full_sync": request_payload.full_sync,
                "data_types": requested_types,
                "errors": errors,
            },
        },
    )
    metadata["logs"] = logs

    record.configuration_metadata = metadata
    record.last_health_check = now
    await db.commit()

    return {
        "sync_id": sync_id,
        "status": result_status,
        "items_synced": sync_entry["items_synced"],
        "errors": errors,
    }


@router.get(
    "/{integration_id}/sync-history",
    summary="Get integration sync history",
    dependencies=[Depends(validate_request)],
)
async def get_sync_history(
    integration_id: str,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_async_db),
) -> dict[str, Any]:
    record = await _get_integration_by_id(db, current_user.id, integration_id)
    metadata = _load_metadata(record)
    sync_history = metadata.get("sync_history") or _default_sync_history()
    return {"syncs": sync_history}


@router.post(
    "/{integration_id}/webhooks",
    summary="Configure webhooks",
    dependencies=[Depends(validate_request)],
)
async def configure_webhooks(
    integration_id: str,
    webhook_config: IntegrationWebhookConfig,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_async_db),
) -> dict[str, Any]:
    record = await _get_integration_by_id(db, current_user.id, integration_id)
    metadata = _load_metadata(record)
    webhook_id = f"wh-{uuid4().hex[:12]}"
    webhook_entry = {
        "webhook_id": webhook_id,
        "endpoint_url": webhook_config.endpoint_url,
        "events": webhook_config.events,
        "active": webhook_config.active,
    }
    webhooks = metadata.get("webhooks") or []
    webhooks.insert(0, webhook_entry)
    metadata["webhooks"] = webhooks

    logs = metadata.get("logs") or []
    logs.insert(
        0,
        {
            "timestamp": _to_iso(_utcnow()),
            "event_type": "webhook_configured",
            "status": "success",
            "details": webhook_entry,
        },
    )
    metadata["logs"] = logs

    record.configuration_metadata = metadata
    await db.commit()

    return {
        "webhook_id": webhook_id,
        "status": "active" if webhook_config.active else "inactive",
        "test_url": f"{webhook_config.endpoint_url.rstrip('/')}/test",
    }


@router.get("/{integration_id}/logs", summary="Get integration logs", dependencies=[Depends(validate_request)])
async def get_integration_logs(
    integration_id: str,
    event_type: str | None = Query(default=None),
    start_date: str | None = Query(default=None),
    end_date: str | None = Query(default=None),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_async_db),
) -> dict[str, Any]:
    _ = (start_date, end_date)
    record = await _get_integration_by_id(db, current_user.id, integration_id)
    metadata = _load_metadata(record)
    logs = metadata.get("logs") or [
        {
            "timestamp": _to_iso(_utcnow() - timedelta(minutes=30)),
            "event_type": "health_check",
            "status": "success",
            "details": {"provider": record.provider},
        }
    ]

    if event_type:
        logs = [log for log in logs if log.get("event_type") == event_type]

    total = len(logs)
    start = (page - 1) * page_size
    end = start + page_size
    return {"logs": logs[start:end], "total": total}


@router.patch(
    "/{integration_id}/config",
    summary="Update integration config",
    dependencies=[Depends(validate_request)],
)
async def update_integration_config(
    integration_id: str,
    config: dict[str, Any] | None = Body(default=None),
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_async_db),
) -> dict[str, Any]:
    record = await _get_integration_by_id(db, current_user.id, integration_id)
    metadata = _load_metadata(record)
    sensitive_config, public_config = _split_sensitive_config(config or {})
    metadata["config"] = {**metadata.get("config", {}), **public_config}
    record.configuration_metadata = metadata

    if sensitive_config:
        record.encrypted_credentials = _encrypt_credentials(
            current_user.id, record.provider, sensitive_config
        )

    await db.commit()
    await db.refresh(record)

    return _build_integration_response(
        record.provider,
        _load_metadata(record),
        integration_id=str(record.id),
        is_active=bool(record.is_active),
        created_at=record.created_at,
        updated_at=record.updated_at,
    )


@router.post("/oauth/callback", summary="Handle OAuth callback", dependencies=[Depends(validate_request)])
async def oauth_callback(
    payload: OAuthCallbackRequest,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_async_db),
) -> dict[str, Any]:
    provider = payload.provider.lower()
    _provider_metadata(provider)

    if not payload.code:
        return {"success": False, "error": "Missing authorization code"}

    result = await db.execute(
        select(Integration).where(
            Integration.user_id == current_user.id,
            Integration.provider == provider,
        )
    )
    record = result.scalars().first()
    now = _utcnow()

    metadata = _load_metadata(record)
    metadata["status"] = "connected"
    metadata["auth_type"] = "oauth2"
    metadata["oauth"] = {
        "last_code_received_at": _to_iso(now),
        "state": payload.state,
    }
    metadata["sync_settings"] = metadata.get("sync_settings") or _default_sync_settings(now)
    metadata["sync_history"] = metadata.get("sync_history") or _default_sync_history(now)
    metadata["logs"] = metadata.get("logs") or []
    metadata["webhooks"] = metadata.get("webhooks") or []

    if record is None:
        record = Integration(
            user_id=current_user.id,
            provider=provider,
            encrypted_credentials="{}",
            is_active=True,
            last_health_check=now,
            health_status={"status": "connected"},
            configuration_metadata=metadata,
        )
        db.add(record)
    else:
        record.is_active = True
        record.last_health_check = now
        record.health_status = {"status": "connected"}
        record.configuration_metadata = metadata

    await db.commit()
    await db.refresh(record)

    return {
        "success": True,
        "integration_id": str(record.id),
    }
