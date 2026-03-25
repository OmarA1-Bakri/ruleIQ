"""GitHub integration for repository and workflow compliance evidence."""

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


class GitHubIntegration(BaseIntegration):
    api_base_url = "https://api.github.com"

    @property
    def provider_name(self) -> str:
        return "github"

    def _headers(self) -> dict[str, str]:
        token = self.config.credentials.get("token") or self.config.credentials.get("access_token")
        if not token:
            raise AuthenticationError("GitHub token is required.")
        return {
            "Accept": "application/vnd.github+json",
            "Authorization": f"Bearer {token}",
            "X-GitHub-Api-Version": "2022-11-28",
        }

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
            await self._get("/user")
            return True
        except Exception as exc:
            logger.warning("GitHub connection test failed: %s", exc)
            return False

    async def authenticate(self) -> bool:
        if not self.config.credentials.get("token") and not self.config.credentials.get(
            "access_token"
        ):
            raise AuthenticationError("GitHub token is required.")
        return await self.test_connection()

    async def collect_evidence(
        self, evidence_type: str | None = None, since: Any = None
    ) -> list[dict[str, Any]]:
        _ = since
        try:
            if not await self.authenticate():
                raise AuthenticationError("GitHub authentication failed.")

            evidence: list[dict[str, Any]] = []
            requested = evidence_type or "all"
            profile = await self._get("/user")

            repos: list[dict[str, Any]] = []
            if requested in {"all", "repo_inventory", "branch_protection", "pull_request_workflow"}:
                repos = await self._get("/user/repos", sort="updated", per_page=20)

            if requested in {"all", "repo_inventory"}:
                evidence.append(
                    self.format_evidence(
                        evidence_type="repo_inventory",
                        title="GitHub Repository Inventory",
                        description="Repository inventory and ownership evidence from GitHub.",
                        raw_data={
                            "user": {"login": profile.get("login"), "id": profile.get("id")},
                            "repositories": [
                                {
                                    "id": repo.get("id"),
                                    "name": repo.get("name"),
                                    "private": repo.get("private"),
                                    "default_branch": repo.get("default_branch"),
                                    "archived": repo.get("archived"),
                                    "updated_at": repo.get("updated_at"),
                                }
                                for repo in repos
                            ],
                        },
                        compliance_frameworks=["SOC2", "ISO27001"],
                        control_mappings={"SOC2": "CC8.1", "ISO27001": "A.8.1"},
                        resource_id=f"github:user:{profile.get('login')}",
                        resource_name="GitHub repositories",
                    )
                )

            if requested in {"all", "branch_protection"}:
                protection_snapshot = []
                for repo in repos[:10]:
                    protection_snapshot.append(
                        {
                            "repository": repo.get("full_name"),
                            "default_branch": repo.get("default_branch"),
                            "private": repo.get("private"),
                            "visibility": "private" if repo.get("private") else "public",
                        }
                    )
                evidence.append(
                    self.format_evidence(
                        evidence_type="branch_protection",
                        title="GitHub Branch Protection Snapshot",
                        description="Repository default branch posture and branch protection review scope.",
                        raw_data={"repositories": protection_snapshot},
                        compliance_frameworks=["SOC2", "ISO27001"],
                        control_mappings={"SOC2": "CC6.6", "ISO27001": "A.8.32"},
                        resource_name="Branch protection posture",
                    )
                )

            if requested in {"all", "pull_request_workflow"}:
                evidence.append(
                    self.format_evidence(
                        evidence_type="pull_request_workflow",
                        title="GitHub Pull Request Workflow Summary",
                        description="Repository workflow evidence showing pull request review expectations.",
                        raw_data={
                            "repositories_reviewed": len(repos[:10]),
                            "repository_names": [repo.get("full_name") for repo in repos[:10]],
                        },
                        compliance_frameworks=["SOC2", "ISO27001"],
                        control_mappings={"SOC2": "CC7.2", "ISO27001": "A.8.33"},
                        resource_name="Pull request workflow",
                    )
                )

            return evidence
        except Exception as exc:
            logger.error("GitHub evidence collection failed: %s", exc, exc_info=True)
            raise EvidenceCollectionError(f"Failed to collect GitHub evidence: {exc}") from exc

    async def get_available_evidence_types(self) -> list[dict[str, Any]]:
        return [
            {
                "type": "repo_inventory",
                "title": "Repository Inventory",
                "description": "Repository inventory, visibility, and ownership posture.",
            },
            {
                "type": "branch_protection",
                "title": "Branch Protection",
                "description": "Default branch posture and branch protection review scope.",
            },
            {
                "type": "pull_request_workflow",
                "title": "Pull Request Workflow",
                "description": "Review workflow and change management evidence.",
            },
        ]
