"""Microsoft 365 integration for identity and tenant posture evidence."""

from __future__ import annotations

from typing import Any

import httpx

from api.integrations.base.base_integration import (
    AuthenticationError,
    BaseIntegration,
    EvidenceCollectionError,
)
from config.logging_config import get_logger

logger = get_logger(__name__)


class Microsoft365Integration(BaseIntegration):
    api_base_url = "https://graph.microsoft.com/v1.0"

    @property
    def provider_name(self) -> str:
        return "microsoft_365"

    def _headers(self) -> dict[str, str]:
        token = self.config.credentials.get("access_token") or self.config.credentials.get("token")
        if not token:
            raise AuthenticationError("Microsoft 365 access_token is required.")
        return {"Authorization": f"Bearer {token}", "Accept": "application/json"}

    async def _get(self, path: str, **params: Any) -> Any:
        async with httpx.AsyncClient(timeout=15.0) as client:
            response = await client.get(
                f"{self.api_base_url}{path}",
                headers=self._headers(),
                params={k: v for k, v in params.items() if v is not None},
            )
            response.raise_for_status()
            return response.json()

    async def test_connection(self) -> bool:
        try:
            await self._get("/organization")
            return True
        except Exception as exc:
            logger.warning("Microsoft 365 connection test failed: %s", exc)
            return False

    async def authenticate(self) -> bool:
        return await self.test_connection()

    async def collect_evidence(
        self, evidence_type: str | None = None, since: Any = None
    ) -> list[dict[str, Any]]:
        _ = since
        try:
            if not await self.authenticate():
                raise AuthenticationError("Microsoft 365 authentication failed.")

            requested = evidence_type or "all"
            organization = await self._get("/organization")
            users = await self._get("/users", top=25, select="id,displayName,userPrincipalName,accountEnabled")
            groups = await self._get("/groups", top=25, select="id,displayName,mailEnabled,securityEnabled")
            evidence: list[dict[str, Any]] = []

            if requested in {"all", "tenant_identity"}:
                evidence.append(
                    self.format_evidence(
                        evidence_type="tenant_identity",
                        title="Microsoft 365 Tenant Identity Posture",
                        description="Tenant and organization identity posture evidence from Microsoft Graph.",
                        raw_data={"organization": organization.get("value", [])},
                        compliance_frameworks=["SOC2", "ISO27001"],
                        control_mappings={"SOC2": "CC6.2", "ISO27001": "A.5.15"},
                        resource_name="Microsoft 365 tenant",
                    )
                )

            if requested in {"all", "user_directory"}:
                evidence.append(
                    self.format_evidence(
                        evidence_type="user_directory",
                        title="Microsoft 365 User Directory",
                        description="User directory evidence including account status and principal names.",
                        raw_data={"users": users.get("value", [])},
                        compliance_frameworks=["SOC2", "ISO27001"],
                        control_mappings={"SOC2": "CC6.3", "ISO27001": "A.5.18"},
                        resource_name="Microsoft 365 users",
                    )
                )

            if requested in {"all", "group_access"}:
                evidence.append(
                    self.format_evidence(
                        evidence_type="group_access",
                        title="Microsoft 365 Groups and Access",
                        description="Group and access-control evidence from Microsoft Graph.",
                        raw_data={"groups": groups.get("value", [])},
                        compliance_frameworks=["SOC2", "ISO27001"],
                        control_mappings={"SOC2": "CC6.6", "ISO27001": "A.5.18"},
                        resource_name="Microsoft 365 groups",
                    )
                )

            return evidence
        except Exception as exc:
            logger.error("Microsoft 365 evidence collection failed: %s", exc, exc_info=True)
            raise EvidenceCollectionError(
                f"Failed to collect Microsoft 365 evidence: {exc}"
            ) from exc

    async def get_available_evidence_types(self) -> list[dict[str, Any]]:
        return [
            {
                "type": "tenant_identity",
                "title": "Tenant Identity",
                "description": "Tenant organization and identity posture evidence.",
            },
            {
                "type": "user_directory",
                "title": "User Directory",
                "description": "User account inventory and account state evidence.",
            },
            {
                "type": "group_access",
                "title": "Group Access",
                "description": "Groups and access-control evidence.",
            },
        ]
