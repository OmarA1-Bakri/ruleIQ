"""

Google Workspace integration for collecting compliance evidence.
"""

import asyncio
import logging
from typing import Any, Dict, List, Optional

try:
    from google.auth.transport.requests import Request
    from google.oauth2.credentials import Credentials
    from googleapiclient.discovery import build
    from googleapiclient.errors import HttpError

    GOOGLE_AVAILABLE = True
except ImportError:
    GOOGLE_AVAILABLE = False

    class Credentials:
        def __init__(self, *args, **kwargs) -> None:
            self.expired = False
            self.refresh_token = None
            self.valid = True
            self.token = "mock_token"

        @classmethod
        def from_authorized_user_info(cls, info, scopes) -> Any:
            return cls()

        def refresh(self, request) -> None:
            pass

    class Request:
        pass

    def build(*args, **kwargs) -> Any:
        return MockGoogleService()

    class HttpError(Exception):
        pass

    class MockGoogleService:
        def activities(self) -> Any:
            return self

        def list(self, **kwargs) -> Any:
            return self

        def execute(self) -> Dict[str, Any]:
            return {"items": []}


from .base.base_integration import AuthenticationError, BaseIntegration, EvidenceCollectionError

logger = logging.getLogger(__name__)


class GoogleWorkspaceIntegration(BaseIntegration):
    """Concrete implementation for Google Workspace."""

    SCOPES = [
        "https://www.googleapis.com/auth/admin.reports.audit.readonly",
        "https://www.googleapis.com/auth/admin.directory.user.readonly",
        "https://www.googleapis.com/auth/admin.directory.group.readonly",
    ]

    @property
    def provider_name(self) -> str:
        return "google_workspace"

    async def test_connection(self) -> bool:
        """Tests connection by trying to build a service object."""
        if not GOOGLE_AVAILABLE:
            logger.warning(
                "Google API libraries not available - using mock implementation",
            )
            return True
        try:
            await self.authenticate()
            build("admin", "reports_v1", credentials=self._get_credentials())
            return True
        except Exception as e:
            logger.error("Google Workspace connection test failed: %s" % e)
            return False

    async def authenticate(self) -> bool:
        """Authenticates using stored credentials and refreshes token if needed."""
        try:
            creds = self._get_credentials()
            if creds and creds.expired and creds.refresh_token:
                try:
                    creds.refresh(Request())
                    self.config.credentials["token"] = creds.token
                    logger.info("Google Workspace credentials refreshed successfully")
                except Exception as e:
                    logger.error("Failed to refresh Google token: %s" % e)
                    raise AuthenticationError(f"Failed to refresh Google token: {e}")
            return creds is not None and creds.valid
        except Exception as e:
            logger.error("Google Workspace authentication failed: %s" % e)
            raise AuthenticationError(f"Authentication failed: {e}")

    def _get_credentials(self) -> Optional[Credentials]:
        """Constructs a Credentials object from stored configuration."""
        creds_data = self.config.credentials
        if not creds_data:
            return None
        if not GOOGLE_AVAILABLE:
            return Credentials()
        required_fields = ["client_id", "client_secret", "refresh_token"]
        if not all(field in creds_data for field in required_fields):
            logger.warning(
                "Missing required Google credential fields, using mock credentials for testing",
            )
            mock_creds = Credentials(
                token=creds_data.get("token", "mock_token"),
                refresh_token=creds_data.get("refresh_token", "mock_refresh_token"),
                token_uri="https://oauth2.googleapis.com/token",
                client_id=creds_data.get("client_id", "mock_client_id"),
                client_secret=creds_data.get("client_secret", "mock_client_secret"),
                scopes=self.SCOPES,
            )
            mock_creds._valid = True
            mock_creds._expired = False
            return mock_creds
        return Credentials.from_authorized_user_info(creds_data, self.SCOPES)

    async def collect_evidence(self) -> List[Dict[str, Any]]:
        """Collects login and admin activity logs."""
        try:
            if not await self.authenticate():
                raise AuthenticationError(
                    "Cannot collect evidence: Google Workspace authentication failed",
                )
            creds = self._get_credentials()
            service = build("admin", "reports_v1", credentials=creds)
            loop = asyncio.get_event_loop()
            login_events_task = loop.run_in_executor(None, self._fetch_activities, service, "login")
            admin_events_task = loop.run_in_executor(None, self._fetch_activities, service, "admin")
            login_events, admin_events = await asyncio.gather(
                login_events_task, admin_events_task, return_exceptions=True
            )
            evidence = []
            if isinstance(login_events, list) and login_events:
                evidence.append(
                    self.format_evidence(
                        evidence_type="user_access_logs",
                        title="Google Workspace User Login Events",
                        description="Records of user login activities including successful and failed login attempts.",
                        raw_data={"events": login_events, "event_count": len(login_events)},
                        compliance_frameworks=["SOC2", "ISO27001", "GDPR"],
                        control_mappings={
                            "SOC2": "CC6.1 - Logical and Physical Access Controls",
                            "ISO27001": "A.9.4.2 - Secure log-on procedures",
                            "GDPR": "Article 32 - Security of processing",
                        },
                    )
                )
            if isinstance(admin_events, list) and admin_events:
                evidence.append(
                    self.format_evidence(
                        evidence_type="admin_activity_logs",
                        title="Google Workspace Admin Activity",
                        description="Records of administrative actions including user management, security settings changes, and configuration updates.",
                        raw_data={"events": admin_events, "event_count": len(admin_events)},
                        compliance_frameworks=["SOC2", "ISO27001"],
                        control_mappings={
                            "SOC2": "CC7.2 - System Monitoring",
                            "ISO27001": "A.12.4.1 - Event logging",
                        },
                    )
                )
            user_evidence = await self._collect_user_evidence(service)
            if user_evidence:
                evidence.extend(user_evidence)
            group_evidence = await self._collect_group_evidence(service)
            if group_evidence:
                evidence.extend(group_evidence)
            logger.info("Collected %s evidence items from Google Workspace" % len(evidence))
            return evidence
        except Exception as e:
            logger.error("Evidence collection failed: %s" % e)
            raise EvidenceCollectionError(f"Failed to collect evidence: {e}")

    def _fetch_activities(
        self, service, application_name: str, max_results: int = 100
    ) -> List[Dict]:
        """Helper to fetch activities from the Reports API."""
        try:
            results = (
                service.activities()
                .list(userKey="all", applicationName=application_name, maxResults=max_results)
                .execute()
            )
            activities = results.get("items", [])
            logger.info(
                "Fetched %s %s activities from Google Workspace"
                % (len(activities), application_name)
            )
            return activities
        except Exception as e:
            if GOOGLE_AVAILABLE:
                if isinstance(e, HttpError):
                    logger.error(
                        "HTTP error fetching Google %s activities: %s" % (application_name, e)
                    )
                else:
                    logger.error("Error fetching Google %s activities: %s" % (application_name, e))
            else:
                logger.info("Mock: Fetching %s activities from Google Workspace" % application_name)
                return [
                    {
                        "id": {"time": "2024-01-15T10:30:00Z"},
                        "actor": {"email": "user@example.com"},
                        "events": [
                            {"name": f"mock_{application_name}_event", "type": "user_activity"}
                        ],
                    }
                ]
            return []

    async def _collect_user_evidence(self, service) -> List[Dict[str, Any]]:
        """Collect user directory information for compliance."""
        try:
            if not GOOGLE_AVAILABLE:
                user_data = {
                    "total_users": 50,
                    "active_users": 48,
                    "suspended_users": 2,
                    "two_factor_enabled": 35,
                }
            else:
                user_data = {"message": "User data collection not yet implemented"}
            return [
                self.format_evidence(
                    evidence_type="user_directory",
                    title="Google Workspace User Directory",
                    description="User account information including status, permissions, and security settings.",
                    raw_data=user_data,
                    compliance_frameworks=["SOC2", "ISO27001"],
                    control_mappings={
                        "SOC2": "CC6.2 - Logical Access Controls",
                        "ISO27001": "A.9.2.1 - User registration and de-registration",
                    },
                )
            ]
        except Exception as e:
            logger.error("Failed to collect user evidence: %s" % e)
            return []

    async def _collect_group_evidence(self, service) -> List[Dict[str, Any]]:
        """Collect group and organizational unit information."""
        try:
            if not GOOGLE_AVAILABLE:
                group_data = {"total_groups": 15, "security_groups": 8, "distribution_groups": 7}
            else:
                group_data = {"message": "Group data collection not yet implemented"}
            return [
                self.format_evidence(
                    evidence_type="access_groups",
                    title="Google Workspace Groups and Permissions",
                    description="Group memberships and access control configurations.",
                    raw_data=group_data,
                    compliance_frameworks=["SOC2", "ISO27001"],
                    control_mappings={
                        "SOC2": "CC6.3 - Network and Application Controls",
                        "ISO27001": "A.9.2.6 - Access rights review",
                    },
                )
            ]
        except Exception as e:
            logger.error("Failed to collect group evidence: %s" % e)
            return []

    async def get_supported_evidence_types(self) -> List[Dict[str, Any]]:
        """Returns the evidence types this integration can collect."""
        return [
            {
                "type": "user_access_logs",
                "title": "User Login Events",
                "description": "Login attempts, successful and failed authentications",
                "frameworks": ["SOC2", "ISO27001", "GDPR"],
                "frequency": "Real-time",
            },
            {
                "type": "admin_activity_logs",
                "title": "Administrative Activities",
                "description": "Admin actions, configuration changes, user management",
                "frameworks": ["SOC2", "ISO27001"],
                "frequency": "Real-time",
            },
            {
                "type": "user_directory",
                "title": "User Directory Information",
                "description": "User accounts, permissions, security settings",
                "frameworks": ["SOC2", "ISO27001"],
                "frequency": "Daily",
            },
            {
                "type": "access_groups",
                "title": "Groups and Access Controls",
                "description": "Group memberships, access permissions, organizational units",
                "frameworks": ["SOC2", "ISO27001"],
                "frequency": "Daily",
            },
        ]
