"""Jira integration for remediation and workflow compliance evidence."""

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


class JiraIntegration(BaseIntegration):
    @property
    def provider_name(self) -> str:
        return "jira"

    def _base_url(self) -> str:
        base_url = (self.config.settings or {}).get("base_url") or self.config.credentials.get(
            "base_url"
        )
        if not base_url:
            raise AuthenticationError("Jira base_url is required.")
        return str(base_url).rstrip("/")

    def _auth(self) -> tuple[str, str]:
        email = self.config.credentials.get("email")
        token = self.config.credentials.get("api_token") or self.config.credentials.get("token")
        if not email or not token:
            raise AuthenticationError("Jira email and api_token are required.")
        return str(email), str(token)

    async def _get(self, path: str, **params: Any) -> Any:
        email, token = self._auth()
        async with httpx.AsyncClient(timeout=15.0, auth=(email, token)) as client:
            response = await client.get(
                f"{self._base_url()}{path}",
                params={k: v for k, v in params.items() if v is not None},
                headers={"Accept": "application/json"},
            )
            response.raise_for_status()
            return response.json()

    async def test_connection(self) -> bool:
        try:
            await self._get("/rest/api/3/myself")
            return True
        except Exception as exc:
            logger.warning("Jira connection test failed: %s", exc)
            return False

    async def authenticate(self) -> bool:
        return await self.test_connection()

    async def collect_evidence(
        self, evidence_type: str | None = None, since: Any = None
    ) -> list[dict[str, Any]]:
        _ = since
        try:
            if not await self.authenticate():
                raise AuthenticationError("Jira authentication failed.")

            evidence: list[dict[str, Any]] = []
            requested = evidence_type or "all"
            profile = await self._get("/rest/api/3/myself")
            projects = await self._get("/rest/api/3/project/search", maxResults=20)
            issues = await self._get(
                "/rest/api/3/search/jql",
                jql="ORDER BY updated DESC",
                maxResults=25,
                fields="summary,status,priority,assignee,project,updated",
            )

            if requested in {"all", "project_inventory"}:
                evidence.append(
                    self.format_evidence(
                        evidence_type="project_inventory",
                        title="Jira Project Inventory",
                        description="Jira project inventory and remediation workspace evidence.",
                        raw_data={
                            "account": {"email": profile.get("emailAddress")},
                            "projects": [
                                {
                                    "id": project.get("id"),
                                    "key": project.get("key"),
                                    "name": project.get("name"),
                                    "project_type": project.get("projectTypeKey"),
                                }
                                for project in projects.get("values", [])
                            ],
                        },
                        compliance_frameworks=["SOC2", "ISO27001"],
                        control_mappings={"SOC2": "CC7.3", "ISO27001": "A.5.36"},
                        resource_name="Jira projects",
                    )
                )

            if requested in {"all", "remediation_workflow"}:
                evidence.append(
                    self.format_evidence(
                        evidence_type="remediation_workflow",
                        title="Jira Remediation Workflow",
                        description="Remediation and action-tracking evidence from Jira issues.",
                        raw_data={
                            "issues": [
                                {
                                    "key": issue.get("key"),
                                    "summary": issue.get("fields", {}).get("summary"),
                                    "status": issue.get("fields", {}).get("status", {}).get("name"),
                                    "priority": issue.get("fields", {}).get("priority", {}).get("name"),
                                    "project": issue.get("fields", {}).get("project", {}).get("key"),
                                    "updated": issue.get("fields", {}).get("updated"),
                                }
                                for issue in issues.get("issues", [])
                            ]
                        },
                        compliance_frameworks=["SOC2", "ISO27001"],
                        control_mappings={"SOC2": "CC7.4", "ISO27001": "A.5.37"},
                        resource_name="Jira remediation workflow",
                    )
                )

            return evidence
        except Exception as exc:
            logger.error("Jira evidence collection failed: %s", exc, exc_info=True)
            raise EvidenceCollectionError(f"Failed to collect Jira evidence: {exc}") from exc

    async def get_available_evidence_types(self) -> list[dict[str, Any]]:
        return [
            {
                "type": "project_inventory",
                "title": "Project Inventory",
                "description": "Project and workflow configuration evidence.",
            },
            {
                "type": "remediation_workflow",
                "title": "Remediation Workflow",
                "description": "Ticket workflow, remediation tracking, and audit trail evidence.",
            },
        ]
