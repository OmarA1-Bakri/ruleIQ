"""Slack integration for workspace and communication workflow evidence."""

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


class SlackIntegration(BaseIntegration):
    api_base_url = "https://slack.com/api"

    @property
    def provider_name(self) -> str:
        return "slack"

    def _headers(self) -> dict[str, str]:
        token = self.config.credentials.get("bot_token") or self.config.credentials.get("access_token")
        if not token:
            raise AuthenticationError("Slack bot_token or access_token is required.")
        return {"Authorization": f"Bearer {token}"}

    async def _get(self, path: str, **params: Any) -> Any:
        async with httpx.AsyncClient(timeout=15.0) as client:
            response = await client.get(
                f"{self.api_base_url}{path}",
                headers=self._headers(),
                params={k: v for k, v in params.items() if v is not None},
            )
            response.raise_for_status()
            payload = response.json()
            if not payload.get("ok", False):
                raise AuthenticationError(payload.get("error", "Slack API error"))
            return payload

    async def test_connection(self) -> bool:
        try:
            await self._get("/auth.test")
            return True
        except Exception as exc:
            logger.warning("Slack connection test failed: %s", exc)
            return False

    async def authenticate(self) -> bool:
        return await self.test_connection()

    async def collect_evidence(
        self, evidence_type: str | None = None, since: Any = None
    ) -> list[dict[str, Any]]:
        _ = since
        try:
            if not await self.authenticate():
                raise AuthenticationError("Slack authentication failed.")

            requested = evidence_type or "all"
            auth_info = await self._get("/auth.test")
            team_info = await self._get("/team.info")
            channels = await self._get("/conversations.list", types="public_channel,private_channel", limit=100)
            evidence: list[dict[str, Any]] = []

            if requested in {"all", "workspace_identity"}:
                evidence.append(
                    self.format_evidence(
                        evidence_type="workspace_identity",
                        title="Slack Workspace Identity",
                        description="Workspace identity and ownership evidence from Slack.",
                        raw_data={"auth": auth_info, "team": team_info.get("team", {})},
                        compliance_frameworks=["SOC2", "ISO27001"],
                        control_mappings={"SOC2": "CC6.2", "ISO27001": "A.5.15"},
                        resource_name="Slack workspace",
                    )
                )

            if requested in {"all", "channel_inventory"}:
                evidence.append(
                    self.format_evidence(
                        evidence_type="channel_inventory",
                        title="Slack Channel Inventory",
                        description="Channel inventory and collaboration footprint evidence.",
                        raw_data={"channels": channels.get("channels", [])},
                        compliance_frameworks=["SOC2"],
                        control_mappings={"SOC2": "CC7.2"},
                        resource_name="Slack channels",
                    )
                )

            return evidence
        except Exception as exc:
            logger.error("Slack evidence collection failed: %s", exc, exc_info=True)
            raise EvidenceCollectionError(f"Failed to collect Slack evidence: {exc}") from exc

    async def get_available_evidence_types(self) -> list[dict[str, Any]]:
        return [
            {
                "type": "workspace_identity",
                "title": "Workspace Identity",
                "description": "Workspace ownership and identity evidence.",
            },
            {
                "type": "channel_inventory",
                "title": "Channel Inventory",
                "description": "Channel inventory and collaboration footprint evidence.",
            },
        ]
