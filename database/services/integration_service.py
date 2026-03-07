"""
import logging


logger = logging.getLogger(__name__)
Database service layer for integration management
Handles all database operations for enterprise integrations
"""

import hashlib
import json
from typing import Dict, List, Any, Optional, Tuple
from datetime import datetime, timezone
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_, func
from sqlalchemy.orm import selectinload
from database.models.integrations import (
    Integration,
    EvidenceCollection,
    IntegrationEvidenceItem,
    IntegrationHealthLog,
    EvidenceAuditLog,
)
from api.clients.base_api_client import APICredentials, AuthType
from core.security.credential_encryption import get_credential_encryption, CredentialDecryptionError
from config.logging_config import get_logger

logger = get_logger(__name__)


class IntegrationService:
    """Service for managing enterprise integrations"""

    def __init__(self, db: AsyncSession) -> None:
        self.db = db
        self.encryption = get_credential_encryption()

    async def store_integration_config(
        self,
        user_id: str,
        provider: str,
        credentials: APICredentials,
        health_info: Dict[str, Any],
        configuration_metadata: Optional[Dict[str, Any]] = None,
    ) -> Integration:
        """
        Store or update integration configuration with encrypted credentials

        Args:
            user_id: User ID who owns this integration
            provider: Integration provider (aws, okta, google_workspace, microsoft_365)
            credentials: API credentials to encrypt and store
            health_info: Initial health check information
            configuration_metadata: Additional provider-specific configuration

        Returns:
            Integration model instance
        """
        try:
            if not user_id or not isinstance(user_id, str):
                raise ValueError("user_id must be a non-empty string")
            if not provider or not isinstance(provider, str):
                raise ValueError("provider must be a non-empty string")
            if provider not in ["aws", "okta", "google_workspace", "microsoft_365"]:
                raise ValueError(f"Invalid provider: {provider}")
            if not credentials or not isinstance(credentials, APICredentials):
                raise ValueError("credentials must be an APICredentials instance")
            if not health_info or not isinstance(health_info, dict):
                raise ValueError("health_info must be a non-empty dictionary")
            encrypted_creds = self.encryption.encrypt_credentials(credentials.credentials)
            async with self.db.begin():
                stmt = select(Integration).where(
                    and_(Integration.user_id == user_id, Integration.provider == provider)
                )
                result = await self.db.execute(stmt)
                existing_integration = result.scalar_one_or_none()
                if existing_integration:
                    existing_integration.encrypted_credentials = encrypted_creds
                    existing_integration.health_status = health_info
                    existing_integration.configuration_metadata = configuration_metadata or {}
                    existing_integration.updated_at = datetime.now(
                        timezone.utc,
                    )
                    existing_integration.is_active = True
                    integration = existing_integration
                    logger.info("Updated integration %s for user %s" % (provider, user_id))
                else:
                    integration = Integration(
                        user_id=user_id,
                        provider=provider,
                        encrypted_credentials=encrypted_creds,
                        health_status=health_info,
                        configuration_metadata=configuration_metadata or {},
                        is_active=True,
                    )
                    self.db.add(integration)
                    logger.info("Created new integration %s for user %s" % (provider, user_id))
                await self.db.flush()
                await self._log_health_check(integration.id, health_info)
            await self.db.refresh(integration)
            await self._create_audit_log(
                user_id=user_id,
                integration_id=integration.id,
                action="create" if not existing_integration else "update",
                resource_type="integration",
                resource_id=str(integration.id),
                details={"provider": provider, "health_status": health_info.get("status")},
            )
            return integration
        except Exception as e:
            logger.error("Failed to store integration config for %s: %s" % (provider, e))
            raise

    async def get_user_integrations(
        self, user_id: str, active_only: bool = True, include_health: bool = False
    ) -> List[Integration]:
        """
        Get all integrations for a user

        Args:
            user_id: User ID to get integrations for
            active_only: Only return active integrations
            include_health: Include recent health logs

        Returns:
            List of Integration instances
        """
        try:
            stmt = select(Integration).where(Integration.user_id == user_id)
            if active_only:
                stmt = stmt.where(Integration.is_active)
            if include_health:
                stmt = stmt.options(selectinload(Integration.evidence_collections))
            stmt = stmt.order_by(Integration.created_at.desc())
            result = await self.db.execute(stmt)
            integrations = result.scalars().all()
            logger.debug("Retrieved %s integrations for user %s" % (len(integrations), user_id))
            return list(integrations)
        except Exception as e:
            logger.error("Failed to get user integrations: %s" % e)
            raise

    async def get_integration_by_id(
        self, integration_id: str, user_id: Optional[str] = None
    ) -> Optional[Integration]:
        """
        Get integration by ID, optionally filtered by user

        Args:
            integration_id: Integration ID to retrieve
            user_id: Optional user ID for access control

        Returns:
            Integration instance or None if not found
        """
        try:
            stmt = select(Integration).where(Integration.id == integration_id)
            if user_id:
                stmt = stmt.where(Integration.user_id == user_id)
            result = await self.db.execute(stmt)
            integration = result.scalar_one_or_none()
            if integration:
                logger.debug("Retrieved integration %s" % integration_id)
            else:
                logger.warning("Integration %s not found" % integration_id)
            return integration
        except Exception as e:
            logger.error("Failed to get integration by ID: %s" % e)
            raise

    async def decrypt_integration_credentials(self, integration: Integration) -> APICredentials:
        """
        Decrypt stored integration credentials

        Args:
            integration: Integration instance with encrypted credentials

        Returns:
            APICredentials instance with decrypted data
        """
        try:
            decrypted_creds = self.encryption.decrypt_credentials(integration.encrypted_credentials)
            api_credentials = APICredentials(
                provider=integration.provider,
                auth_type=AuthType(decrypted_creds.get("auth_type", "api_key")),
                credentials=decrypted_creds,
                region=decrypted_creds.get("region"),
            )
            logger.debug("Decrypted credentials for integration %s" % integration.id)
            return api_credentials
        except CredentialDecryptionError as e:
            logger.error(
                "Failed to decrypt credentials for integration %s: %s" % (integration.id, e)
            )
            raise
        except Exception as e:
            logger.error("Unexpected error decrypting credentials: %s" % e)
            raise

    async def update_integration_health(
        self, integration_id: str, health_data: Dict[str, Any], user_id: Optional[str] = None
    ) -> bool:
        """
        Update integration health status

        Args:
            integration_id: Integration ID to update
            health_data: Health check result data
            user_id: Optional user ID for access control

        Returns:
            True if updated successfully
        """
        try:
            integration = await self.get_integration_by_id(integration_id, user_id)
            if not integration:
                logger.warning("Integration %s not found for health update" % integration_id)
                return False
            integration.health_status = health_data
            integration.last_health_check = datetime.now(timezone.utc)
            integration.updated_at = datetime.now(timezone.utc)
            await self._log_health_check(integration_id, health_data)
            await self.db.commit()
            logger.debug("Updated health for integration %s" % integration_id)
            return True
        except Exception as e:
            await self.db.rollback()
            logger.error("Failed to update integration health: %s" % e)
            raise

    async def delete_integration(self, integration_id: str, user_id: str) -> bool:
        """
        Delete (deactivate) an integration

        Args:
            integration_id: Integration ID to delete
            user_id: User ID for access control

        Returns:
            True if deleted successfully
        """
        try:
            integration = await self.get_integration_by_id(integration_id, user_id)
            if not integration:
                logger.warning("Integration %s not found for deletion" % integration_id)
                return False
            integration.is_active = False
            integration.updated_at = datetime.now(timezone.utc)
            await self._create_audit_log(
                user_id=user_id,
                integration_id=integration_id,
                action="delete",
                resource_type="integration",
                resource_id=integration_id,
                details={"provider": integration.provider},
            )
            await self.db.commit()
            logger.info("Deactivated integration %s" % integration_id)
            return True
        except Exception as e:
            await self.db.rollback()
            logger.error("Failed to delete integration: %s" % e)
            raise

    async def _log_health_check(self, integration_id: str, health_data: Dict[str, Any]) -> None:
        """Log health check result"""
        try:
            health_log = IntegrationHealthLog(
                integration_id=integration_id,
                status=health_data.get("status", "unknown"),
                response_time=health_data.get("response_time"),
                error_details=health_data.get("error"),
                health_data=health_data,
            )
            self.db.add(health_log)
        except Exception as e:
            logger.warning("Failed to log health check: %s" % e)

    async def _create_audit_log(
        self,
        user_id: str,
        action: str,
        resource_type: str,
        resource_id: str,
        integration_id: Optional[str] = None,
        collection_id: Optional[str] = None,
        evidence_item_id: Optional[str] = None,
        details: Optional[Dict[str, Any]] = None,
        ip_address: Optional[str] = None,
        user_agent: Optional[str] = None,
        request_id: Optional[str] = None,
    ) -> None:
        """Create audit log entry"""
        try:
            audit_log = EvidenceAuditLog(
                user_id=user_id,
                integration_id=integration_id,
                collection_id=collection_id,
                evidence_item_id=evidence_item_id,
                action=action,
                resource_type=resource_type,
                resource_id=resource_id,
                details=details or {},
                ip_address=ip_address,
                user_agent=user_agent,
                request_id=request_id,
            )
            self.db.add(audit_log)
        except Exception as e:
            logger.warning("Failed to create audit log: %s" % e)


class EvidenceCollectionService:
    """Service for managing evidence collections"""

    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    async def create_evidence_collection(
        self,
        integration_id: str,
        user_id: str,
        framework_id: str,
        evidence_types_requested: List[str],
        business_profile: Dict[str, Any],
        collection_mode: str = "immediate",
    ) -> EvidenceCollection:
        """
        Create a new evidence collection request

        Args:
            integration_id: Integration to collect evidence from
            user_id: User requesting the collection
            framework_id: Compliance framework (soc2_type2, iso27001, etc.)
            evidence_types_requested: List of evidence types to collect
            business_profile: Business context for collection
            collection_mode: Collection mode (immediate, scheduled, streaming)

        Returns:
            EvidenceCollection instance
        """
        try:
            collection = EvidenceCollection(
                integration_id=integration_id,
                user_id=user_id,
                framework_id=framework_id,
                evidence_types_requested=evidence_types_requested,
                business_profile=business_profile,
                collection_mode=collection_mode,
                status="pending",
            )
            self.db.add(collection)
            await self.db.commit()
            await self.db.refresh(collection)
            logger.info("Created evidence collection %s" % collection.id)
            return collection
        except Exception as e:
            await self.db.rollback()
            logger.error("Failed to create evidence collection: %s" % e)
            raise

    async def update_collection_status(
        self,
        collection_id: str,
        status: str,
        progress_percentage: Optional[int] = None,
        current_activity: Optional[str] = None,
        errors: Optional[List[str]] = None,
        quality_score: Optional[Dict[str, float]] = None,
    ) -> bool:
        """Update evidence collection status"""
        try:
            stmt = select(EvidenceCollection).where(EvidenceCollection.id == collection_id)
            result = await self.db.execute(stmt)
            collection = result.scalar_one_or_none()
            if not collection:
                return False
            collection.status = status
            if progress_percentage is not None:
                collection.progress_percentage = progress_percentage
            if current_activity:
                collection.current_activity = current_activity
            if errors:
                collection.errors = errors
            if quality_score:
                collection.quality_score = quality_score
            if status == "running" and not collection.started_at:
                collection.started_at = datetime.now(timezone.utc)
            elif status in ["completed", "failed"]:
                collection.completed_at = datetime.now(timezone.utc)
            collection.updated_at = datetime.now(timezone.utc)
            await self.db.commit()
            return True
        except Exception as e:
            await self.db.rollback()
            logger.error("Failed to update collection status: %s" % e)
            raise

    async def store_evidence_item(
        self,
        collection_id: str,
        evidence_type: str,
        source_system: str,
        resource_id: str,
        resource_name: str,
        evidence_data: Dict[str, Any],
        compliance_controls: List[str],
        quality_score: Dict[str, Any],
        collected_at: datetime,
        data_classification: str = "internal",
    ) -> IntegrationEvidenceItem:
        """Store individual evidence item"""
        try:
            data_json = json.dumps(evidence_data, sort_keys=True, separators=(",", ":"))
            checksum = hashlib.sha256(data_json.encode()).hexdigest()
            evidence_item = IntegrationEvidenceItem(
                collection_id=collection_id,
                evidence_type=evidence_type,
                source_system=source_system,
                resource_id=resource_id,
                resource_name=resource_name,
                evidence_data=evidence_data,
                compliance_controls=compliance_controls,
                quality_score=quality_score,
                collected_at=collected_at,
                data_classification=data_classification,
                checksum=checksum,
            )
            self.db.add(evidence_item)
            await self.db.commit()
            await self.db.refresh(evidence_item)
            return evidence_item
        except Exception as e:
            await self.db.rollback()
            logger.error("Failed to store evidence item: %s" % e)
            raise

    async def get_collection_status(
        self, collection_id: str, user_id: Optional[str] = None
    ) -> Optional[EvidenceCollection]:
        """Get evidence collection status"""
        try:
            stmt = select(EvidenceCollection).where(EvidenceCollection.id == collection_id)
            if user_id:
                stmt = stmt.where(EvidenceCollection.user_id == user_id)
            result = await self.db.execute(stmt)
            return result.scalar_one_or_none()
        except Exception as e:
            logger.error("Failed to get collection status: %s" % e)
            raise

    async def get_collection_evidence(
        self,
        collection_id: str,
        evidence_type: Optional[str] = None,
        page: int = 1,
        page_size: int = 100,
    ) -> Tuple[List[IntegrationEvidenceItem], int]:
        """Get evidence items for a collection with pagination"""
        try:
            stmt = select(IntegrationEvidenceItem).where(
                IntegrationEvidenceItem.collection_id == collection_id
            )
            if evidence_type:
                stmt = stmt.where(IntegrationEvidenceItem.evidence_type == evidence_type)
            count_stmt = select(func.count()).select_from(stmt.subquery())
            count_result = await self.db.execute(count_stmt)
            total_count = count_result.scalar()
            offset = (page - 1) * page_size
            stmt = stmt.offset(offset).limit(page_size)
            stmt = stmt.order_by(IntegrationEvidenceItem.collected_at.desc())
            result = await self.db.execute(stmt)
            evidence_items = result.scalars().all()
            return list(evidence_items), total_count
        except Exception as e:
            logger.error("Failed to get collection evidence: %s" % e)
            raise


async def store_integration_config(
    user_id: str,
    provider: str,
    credentials: APICredentials,
    health_info: Dict[str, Any],
    db: AsyncSession,
    configuration_metadata: Optional[Dict[str, Any]] = None,
) -> Integration:
    """Store integration configuration"""
    service = IntegrationService(db)
    return await service.store_integration_config(
        user_id, provider, credentials, health_info, configuration_metadata
    )


async def get_user_integrations(user_id: str, db: AsyncSession) -> List[Integration]:
    """Get user integrations"""
    service = IntegrationService(db)
    return await service.get_user_integrations(user_id)


async def get_integration_by_id(
    integration_id: str, db: AsyncSession, user_id: Optional[str] = None
) -> Optional[Integration]:
    """Get integration by ID"""
    service = IntegrationService(db)
    return await service.get_integration_by_id(integration_id, user_id)


async def decrypt_integration_credentials(integration: Integration) -> APICredentials:
    """Decrypt integration credentials"""
    encryption = get_credential_encryption()
    try:
        decrypted_creds = encryption.decrypt_credentials(integration.encrypted_credentials)
        return APICredentials(
            provider=integration.provider,
            auth_type=AuthType(decrypted_creds.get("auth_type", "api_key")),
            credentials=decrypted_creds,
            region=decrypted_creds.get("region"),
        )
    except Exception as e:
        logger.error("Failed to decrypt credentials for integration %s: %s" % (integration.id, e))
        raise


async def update_integration_health(
    integration_id: str,
    health_data: Dict[str, Any],
    db: AsyncSession,
    user_id: Optional[str] = None,
) -> bool:
    """Update integration health"""
    service = IntegrationService(db)
    return await service.update_integration_health(integration_id, health_data, user_id)
