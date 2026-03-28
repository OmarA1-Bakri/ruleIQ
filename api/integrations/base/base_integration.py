"""Base integration contract and shared helpers for provider adapters."""

from __future__ import annotations

import json
from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import datetime, timezone
from enum import Enum
from typing import Any
from uuid import UUID

from cryptography.fernet import InvalidToken

from config.app_config import get_cipher_suite
from config.logging_config import get_logger

logger = get_logger(__name__)


class IntegrationStatus(str, Enum):
    CONNECTED = "connected"
    DISCONNECTED = "disconnected"
    ERROR = "error"
    NEEDS_REAUTH = "needs_reauth"
    PENDING_VERIFICATION = "pending_verification"


@dataclass
class IntegrationConfig:
    user_id: UUID
    provider: str
    credentials: dict[str, Any]
    settings: dict[str, Any] | None = None
    status: IntegrationStatus = IntegrationStatus.DISCONNECTED
    last_sync: datetime | None = None


class BaseIntegration(ABC):
    """Abstract provider adapter with shared evidence formatting helpers."""

    def __init__(self, config: IntegrationConfig) -> None:
        self.config = config
        self.cipher = get_cipher_suite()
        if not self.cipher:
            logger.error(
                "Fernet cipher not available for integration %s for user %s. Cannot proceed without encryption.",
                self.config.provider,
                self.config.user_id,
            )
            raise IntegrationError(
                "Encryption cipher not available. Cannot create integration without secure credential storage."
            )

    @property
    @abstractmethod
    def provider_name(self) -> str:
        """Provider identifier used by the integration registry."""

    @abstractmethod
    async def test_connection(self) -> bool:
        """Validate that the configured credentials can reach the provider."""

    @abstractmethod
    async def authenticate(self) -> bool:
        """Refresh or validate credentials before evidence collection."""

    @abstractmethod
    async def collect_evidence(
        self, evidence_type: str | None = None, since: datetime | None = None
    ) -> list[dict[str, Any]]:
        """Collect evidence items for the provider."""

    @abstractmethod
    async def get_available_evidence_types(self) -> list[dict[str, Any]]:
        """List supported evidence types for this adapter."""

    async def get_supported_evidence_types(self) -> list[dict[str, Any]]:
        """Backward-compatible alias used by older adapters."""
        return await self.get_available_evidence_types()

    async def validate_credentials(self, credentials_to_test: dict[str, Any]) -> bool:
        original_creds = self.config.credentials
        self.config.credentials = credentials_to_test
        try:
            return await self.test_connection()
        except Exception as exc:
            logger.error(
                "Error validating credentials for %s: %s",
                self.provider_name,
                exc,
                exc_info=True,
            )
            return False
        finally:
            self.config.credentials = original_creds

    def encrypt_credentials_to_str(self, credentials_dict: dict[str, Any]) -> str:
        if not self.cipher:
            logger.error("Cannot encrypt credentials: Fernet cipher is not initialized.")
            raise IntegrationError(
                "Encryption cipher not available. Cannot save credentials securely."
            )
        try:
            credentials_json = json.dumps(credentials_dict)
            encrypted_bytes = self.cipher.encrypt(credentials_json.encode("utf-8"))
            return encrypted_bytes.decode("utf-8")
        except Exception as exc:
            logger.error("Failed to encrypt credentials: %s", exc, exc_info=True)
            raise IntegrationError(f"Failed to encrypt credentials: {exc}") from exc

    def decrypt_credentials_from_str(self, encrypted_credentials_str: str) -> dict[str, Any]:
        if not self.cipher:
            logger.error("Cannot decrypt credentials: Fernet cipher is not initialized.")
            raise IntegrationError(
                "Decryption cipher not available. Cannot load credentials securely."
            )
        try:
            encrypted_bytes = encrypted_credentials_str.encode("utf-8")
            decrypted_bytes = self.cipher.decrypt(encrypted_bytes)
            return json.loads(decrypted_bytes.decode("utf-8"))
        except InvalidToken as exc:
            logger.error(
                "Failed to decrypt credentials: Invalid Fernet token. Key might be wrong or data corrupted."
            )
            raise IntegrationError("Invalid credentials token") from exc
        except Exception as exc:
            logger.error("Failed to decrypt credentials: %s", exc, exc_info=True)
            raise IntegrationError(f"Failed to decrypt credentials: {exc}") from exc

    def format_evidence(
        self,
        *,
        evidence_type: str,
        title: str,
        description: str,
        raw_data: dict[str, Any],
        compliance_frameworks: list[str] | None = None,
        control_mappings: dict[str, Any] | None = None,
        resource_id: str | None = None,
        resource_name: str | None = None,
        collected_at: datetime | None = None,
    ) -> dict[str, Any]:
        """Create a normalized evidence payload for persistence and UI use."""
        timestamp = collected_at or datetime.now(timezone.utc)
        return {
            "provider": self.provider_name,
            "evidence_type": evidence_type,
            "title": title,
            "description": description,
            "raw_data": raw_data,
            "compliance_frameworks": compliance_frameworks or [],
            "control_mappings": control_mappings or {},
            "resource_id": resource_id or f"{self.provider_name}:{evidence_type}:{int(timestamp.timestamp())}",
            "resource_name": resource_name or title,
            "collected_at": timestamp.isoformat(),
        }


class IntegrationError(Exception):
    """Base integration failure."""


class AuthenticationError(IntegrationError):
    """Authentication failure for an external provider."""


class ConnectionError(IntegrationError):
    """Connectivity failure for an external provider."""


class EvidenceCollectionError(IntegrationError):
    """Evidence collection failure for an external provider."""
