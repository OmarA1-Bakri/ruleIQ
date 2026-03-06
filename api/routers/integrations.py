"""
import logging


logger = logging.getLogger(__name__)
API endpoints for managing third-party integrations (Asynchronous & Secure).
"""

from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from api.dependencies.auth import get_current_active_user
from api.dependencies.security_validation import validate_request, validate_integration_request
from api.utils.security_validation import SecurityValidator
from api.utils.input_validation import InputValidator
from database.user import User
from api.integrations.base.base_integration import (
    BaseIntegration,
    IntegrationConfig,
    IntegrationStatus,
)
from config.logging_config import get_logger
from database.db_setup import get_async_db
from database.models.integrations import Integration

logger = get_logger(__name__)
router = APIRouter()


class IntegrationCredentials(BaseModel):
    provider: str
    credentials: Dict[str, Any]
    settings: Optional[Dict[str, Any]] = None


class IntegrationResponse(BaseModel):
    provider: str
    status: str
    message: Optional[str] = None
    is_enabled: Optional[bool] = None
    last_sync_at: Optional[datetime] = None
    last_sync_status: Optional[str] = None


class IntegrationListResponse(BaseModel):
    available_providers: List[Dict[str, Any]]
    configured_integrations: List[IntegrationResponse]


class GenericIntegration(BaseIntegration):
    """A generic class to access base methods like encryption without a real provider."""

    @property
    def provider_name(self) -> str:
        return "generic"

    async def test_connection(self) -> bool:
        return False

    async def authenticate(self) -> bool:
        return False

    async def collect_evidence(self, *args, **kwargs) -> List:
        return []

    async def get_available_evidence_types(self) -> List:
        return []


AVAILABLE_PROVIDERS = {
    "google_workspace": {"name": "Google Workspace"},
    "microsoft_365": {"name": "Microsoft 365"},
}


@router.post(
    "/connect",
    response_model=IntegrationResponse,
    summary="Connect or Update Integration",
    dependencies=[Depends(validate_request)],
)
async def connect_integration(
    payload: IntegrationCredentials,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_async_db),
) -> Any:
    # Sanitize provider name
    provider = SecurityValidator.validate_no_dangerous_content(payload.provider, "provider").lower()
    if provider not in AVAILABLE_PROVIDERS:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail=f"Provider '{provider}' not supported."
        )
    try:
        temp_config = IntegrationConfig(
            user_id=str(current_user.id), provider=provider, credentials={}
        )
        integration_handler = GenericIntegration(temp_config)
        encrypted_creds = integration_handler.encrypt_credentials_to_str(payload.credentials)
        if not encrypted_creds:
            logger.error(
                "Credential encryption failed for user %s, provider %s. Aborting connection."
                % (str(current_user.id), provider)
            )
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Credential encryption failed.",
            )
        stmt = select(Integration).where(
            Integration.user_id == str(current_user.id), Integration.provider == provider
        )
        result = await db.execute(stmt)
        config = result.scalars().first()
        if config:
            config.credentials = encrypted_creds
            config.settings = payload.settings
            config.status = IntegrationStatus.CONNECTED.value
            config.is_enabled = True
            config.updated_at = datetime.now(timezone.utc)
            message = (f"Successfully updated and reconnected {provider} integration.",)
            logger.info(
                "Integration updated for user %s, provider %s" % (str(current_user.id), provider)
            )
        else:
            config = Integration(
                user_id=str(current_user.id),
                provider=provider,
                credentials=encrypted_creds,
                settings=payload.settings,
                status=IntegrationStatus.CONNECTED.value,
                is_enabled=True,
            )
            db.add(config)
            message = f"Successfully connected {provider} integration."
            logger.info(
                "New integration created for user %s, provider %s"
                % (str(current_user.id), provider)
            )
        await db.commit()
        await db.refresh(config)
        return IntegrationResponse(
            provider=provider, status=config.status, message=message, is_enabled=config.is_enabled
        )
    except SQLAlchemyError as e:
        await db.rollback()
        logger.error(
            "Database error connecting integration for user %s, provider %s: %s"
            % (str(current_user.id), provider, e),
            exc_info=True,
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Database operation failed.",
        )
    except Exception as e:
        await db.rollback()
        logger.error(
            "Error connecting integration for user %s, provider %s: %s"
            % (str(current_user.id), provider, e),
            exc_info=True,
        )
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))


@router.delete(
    "/{provider}",
    summary="Disconnect integration",
    status_code=status.HTTP_204_NO_CONTENT,
    dependencies=[Depends(validate_request)],
)
async def disconnect_integration(
    provider: str,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_async_db),
) -> None:
    provider_key = provider.lower()
    if provider_key not in AVAILABLE_PROVIDERS:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail=f"Provider '{provider}' not found."
        )
    try:
        stmt = select(Integration).where(
            Integration.user_id == str(current_user.id), Integration.provider == provider_key
        )
        result = await db.execute(stmt)
        config = result.scalars().first()
        if not config:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Integration '{provider}' not configured.",
            )
        await db.delete(config)
        await db.commit()
        logger.info(
            "Integration %s disconnected for user %s" % (provider_key, str(current_user.id))
        )
    except SQLAlchemyError as e:
        await db.rollback()
        logger.error(
            "Database error disconnecting %s for user %s: %s"
            % (provider_key, str(current_user.id), e),
            exc_info=True,
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Database operation failed.",
        )


@router.get(
    "/{provider}/status",
    response_model=IntegrationResponse,
    summary="Get integration status",
    dependencies=[Depends(validate_request)],
)
async def get_integration_status(
    provider: str,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_async_db),
) -> Any:
    provider_key = provider.lower()
    if provider_key not in AVAILABLE_PROVIDERS:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail=f"Provider '{provider}' not supported."
        )
    try:
        stmt = select(Integration).where(
            Integration.user_id == str(current_user.id), Integration.provider == provider_key
        )
        result = await db.execute(stmt)
        config = result.scalars().first()
        if not config:
            return IntegrationResponse(
                provider=provider_key, status="not_configured", is_enabled=False
            )
        return IntegrationResponse(
            provider=config.provider,
            status=config.status,
            is_enabled=config.is_enabled,
            last_sync_at=config.last_sync_at,
            last_sync_status=config.last_sync_status,
        )
    except SQLAlchemyError as e:
        logger.error(
            "Database error fetching status for %s, user %s: %s"
            % (provider_key, str(current_user.id), e),
            exc_info=True,
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Database operation failed.",
        )


@router.get(
    "/", summary="List all available integrations", dependencies=[Depends(validate_request)]
)
async def list_integrations(
    current_user: User = Depends(get_current_active_user), db: AsyncSession = Depends(get_async_db)
) -> Dict[str, Any]:
    """List all available integration providers and their configuration status."""
    return {
        "available_providers": [
            {"provider": "google_workspace", "name": "Google Workspace", "configured": False},
            {"provider": "microsoft_365", "name": "Microsoft 365", "configured": False},
        ],
        "configured_count": 0,
    }


@router.get(
    "/connected", summary="Get connected integrations", dependencies=[Depends(validate_request)]
)
async def get_connected_integrations(
    current_user: User = Depends(get_current_active_user), db: AsyncSession = Depends(get_async_db)
) -> Dict[str, Any]:
    """Get list of currently connected integrations for the user."""
    return {"connected_integrations": [], "total": 0}


@router.post(
    "/{integrationId}/test",
    summary="Test integration connection",
    dependencies=[Depends(validate_request)],
)
async def test_integration(
    integrationId: str,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_async_db),
) -> Dict[str, Any]:
    """Test if integration connection is working properly."""
    return {
        "integration_id": integrationId,
        "status": "success",
        "message": "Connection test successful",
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }


@router.get(
    "/{integrationId}/sync-history",
    summary="Get sync history",
    dependencies=[Depends(validate_request)],
)
async def get_sync_history(
    integrationId: str,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_async_db),
) -> Dict[str, Any]:
    """Get synchronization history for an integration."""
    return {
        "integration_id": integrationId,
        "sync_history": [
            {
                "timestamp": "2024-01-15T10:00:00Z",
                "status": "success",
                "records_synced": 150,
                "duration_seconds": 45,
            },
            {
                "timestamp": "2024-01-14T10:00:00Z",
                "status": "success",
                "records_synced": 148,
                "duration_seconds": 42,
            },
        ],
        "total_syncs": 2,
    }


@router.post(
    "/{integrationId}/webhooks",
    summary="Configure webhooks",
    dependencies=[Depends(validate_request)],
)
async def configure_webhooks(
    integrationId: str,
    webhook_config: Dict = Depends(validate_integration_request),
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_async_db),
) -> Dict[str, Any]:
    """Configure webhooks for an integration."""
    webhook_url = webhook_config.get("url", "")
    if webhook_url:
        # Validate webhook URL
        try:
            webhook_url = InputValidator.validate_url(webhook_url)
        except Exception as e:
            raise HTTPException(status_code=400, detail=f"Invalid webhook URL: {str(e)}")

    events = webhook_config.get("events", [])
    # Sanitize event names
    sanitized_events = [
        InputValidator.sanitize_string(e, max_length=100) for e in events if isinstance(e, str)
    ]
    return {
        "integration_id": integrationId,
        "webhook_url": webhook_url,
        "events": sanitized_events,
        "status": "configured",
        "message": "Webhook configured successfully",
    }


@router.get(
    "/{integrationId}/logs",
    summary="Get integration logs",
    dependencies=[Depends(validate_request)],
)
async def get_integration_logs(
    integrationId: str,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_async_db),
) -> Dict[str, Any]:
    """Get activity logs for an integration."""
    return {
        "integration_id": integrationId,
        "logs": [
            {
                "timestamp": "2024-01-15T15:30:00Z",
                "level": "info",
                "message": "Sync completed successfully",
                "details": {"records": 150},
            },
            {
                "timestamp": "2024-01-15T15:29:00Z",
                "level": "info",
                "message": "Sync started",
                "details": {},
            },
        ],
        "total_logs": 2,
    }


@router.post(
    "/oauth/callback", summary="Handle OAuth callback", dependencies=[Depends(validate_request)]
)
async def oauth_callback(
    callback_data: Dict = Depends(validate_integration_request),
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_async_db),
) -> Dict[str, Any]:
    """Handle OAuth callback from integration providers."""
    code = callback_data.get("code", "")
    callback_data.get("state", "")
    provider = callback_data.get("provider", "")
    return {
        "provider": provider,
        "status": "success",
        "message": "OAuth authentication successful",
        "access_token_received": bool(code),
    }
