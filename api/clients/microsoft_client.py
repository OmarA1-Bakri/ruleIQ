"""
Microsoft 365/Azure AD API Client for compliance evidence collection.
Follows the foundation architecture pattern for enterprise API integrations.
"""

import requests
import json

# Constants
HTTP_OK = 200
DEFAULT_TIMEOUT = 30

# Time Constants
DEFAULT_SESSION_DURATION = 3600

# Threshold Constants
CONFIDENCE_THRESHOLD = 0.8
DEFAULT_LIMIT = 100
HALF_RATIO = 0.5
HIGH_CONFIDENCE_THRESHOLD = 0.95
HIGH_MFA_THRESHOLD = 0.9
MEDIUM_MFA_THRESHOLD = 0.7
HIGH_COMPLIANCE_THRESHOLD = 0.8
MEDIUM_COMPLIANCE_THRESHOLD = 0.5
ACTIVITY_THRESHOLD = 0.6
LOW_ACTIVITY_PENALTY = 0.3
MEDIUM_SECURITY_THRESHOLD = 0.3
LOG_VOLUME_THRESHOLD = 50
import logging
from datetime import datetime, timedelta, timezone
from typing import Dict, List, Optional, Tuple
import aiohttp
from pydantic import BaseModel, Field
from .base_api_client import (
    BaseAPIClient,
    APICredentials,
    AuthType,
    CollectionResult,
    EvidenceQuality,
)

logger = logging.getLogger(__name__)


class MicrosoftCredentials(BaseModel):
    """Microsoft 365/Azure AD OAuth2 credentials."""

    client_id: str = Field(..., description="Azure AD application client ID")
    client_secret: str = Field(..., description="Azure AD application client secret")
    tenant_id: str = Field(..., description="Azure AD tenant ID")
    refresh_token: Optional[str] = Field(None, description="OAuth2 refresh token")
    access_token: Optional[str] = Field(None, description="Current access token")

    class Config:
        extra = "allow"


class MicrosoftGraphAPIClient(BaseAPIClient):
    """Microsoft 365/Azure AD Graph API client for compliance evidence collection."""

    SCOPES = ["https://graph.microsoft.com/.default"]

    def __init__(self, credentials: APICredentials) -> None:
        super().__init__(credentials)
        self.access_token: Optional[str] = None
        self.token_expires_at: Optional[datetime] = None

    def get_base_url(self) -> str:
        """Microsoft Graph API base URL."""
        return "https://graph.microsoft.com/v1.0"

    async def authenticate(self) -> bool:
        """Authenticate with Microsoft Graph using OAuth2."""
        try:
            if self.credentials.auth_type != AuthType.OAUTH2:
                raise ValueError("Microsoft Graph requires OAuth2 authentication")
            creds_data = self.credentials.credentials
            ms_creds = MicrosoftCredentials(**creds_data)
            if (
                self.access_token
                and self.token_expires_at
                and datetime.now(timezone.utc) < self.token_expires_at - timedelta(minutes=5)
            ):
                self.authenticated = True
                return True
            if ms_creds.refresh_token:
                success = await self._refresh_access_token(ms_creds)
                if success:
                    self.authenticated = True
                    return True
            success = await self._client_credentials_flow(ms_creds)
            self.authenticated = success
            return success
        except (ValueError, TypeError) as e:
            logger.error("Microsoft Graph authentication failed: %s" % e)
            self.authenticated = False
            return False

    async def _refresh_access_token(self, creds: MicrosoftCredentials) -> bool:
        """Refresh access token using refresh token."""
        try:
            token_url = (f"https://login.microsoftonline.com/{creds.tenant_id}/oauth2/v2.0/token",)
            data = {
                "grant_type": "refresh_token",
                "refresh_token": creds.refresh_token,
                "client_id": creds.client_id,
                "client_secret": creds.client_secret,
                "scope": " ".join(self.SCOPES),
            }
            async with aiohttp.ClientSession() as session:
                async with session.post(token_url, data=data) as response:
                    if response.status == HTTP_OK:
                        token_data = await response.json()
                        self.access_token = token_data["access_token"]
                        expires_in = token_data.get("expires_in", DEFAULT_SESSION_DURATION)
                        self.token_expires_at = datetime.now(timezone.utc) + timedelta(
                            seconds=expires_in
                        )
                        logger.info("Microsoft Graph access token refreshed")
                        return True
                    else:
                        error_text = await response.text()
                        logger.error("Token refresh failed: %s" % error_text)
                        return False
        except (json.JSONDecodeError, requests.RequestException, KeyError) as e:
            logger.error("Failed to refresh Microsoft Graph token: %s" % e)
            return False

    async def _client_credentials_flow(self, creds: MicrosoftCredentials) -> bool:
        """Get access token using client credentials flow."""
        try:
            token_url = (f"https://login.microsoftonline.com/{creds.tenant_id}/oauth2/v2.0/token",)
            data = {
                "grant_type": "client_credentials",
                "client_id": creds.client_id,
                "client_secret": creds.client_secret,
                "scope": " ".join(self.SCOPES),
            }
            async with aiohttp.ClientSession() as session:
                async with session.post(token_url, data=data) as response:
                    if response.status == HTTP_OK:
                        token_data = await response.json()
                        self.access_token = token_data["access_token"]
                        expires_in = token_data.get("expires_in", DEFAULT_SESSION_DURATION)
                        self.token_expires_at = datetime.now(timezone.utc) + timedelta(
                            seconds=expires_in
                        )
                        logger.info("Microsoft Graph access token obtained")
                        return True
                    else:
                        error_text = await response.text()
                        logger.error("Client credentials flow failed: %s" % error_text)
                        return False
        except (json.JSONDecodeError, requests.RequestException, KeyError) as e:
            logger.error("Failed to get Microsoft Graph token: %s" % e)
            return False

    async def test_connection(self) -> Tuple[bool, str]:
        """Test connection to Microsoft Graph."""
        try:
            if not await self.authenticate():
                return False, "Authentication failed"
            headers = {
                "Authorization": f"Bearer {self.access_token}",
                "Content-Type": "application/json",
            }
            async with aiohttp.ClientSession() as session:
                async with session.get(
                    f"{self.get_base_url()}/organization", headers=headers
                ) as response:
                    if response.status == HTTP_OK:
                        return True, "Connection successful"
                    else:
                        error_text = await response.text()
                        return False, f"Connection test failed: {error_text}"
        except (json.JSONDecodeError, requests.RequestException) as e:
            logger.error("Microsoft Graph connection test failed: %s" % e)
            return False, str(e)

    async def _make_graph_request(self, endpoint: str, params: Optional[Dict] = None) -> Dict:
        """Make an authenticated request to Microsoft Graph API."""
        if not await self.authenticate():
            raise Exception("Authentication failed")
        headers = {
            "Authorization": f"Bearer {self.access_token}",
            "Content-Type": "application/json",
        }
        url = f"{self.get_base_url()}/{endpoint}"
        async with aiohttp.ClientSession() as session:
            async with session.get(url, headers=headers, params=params) as response:
                if response.status == HTTP_OK:
                    return await response.json()
                else:
                    error_text = await response.text()
                    logger.error("Graph API request failed: %s" % error_text)
                    raise Exception(f"Graph API request failed: {response.status}")

    async def collect_users_evidence(self) -> CollectionResult:
        """Collect Azure AD users evidence."""
        try:
            users_data = await self._make_graph_request(
                "users",
                params={
                    "$select": "id,displayName,userPrincipalName,accountEnabled,createdDateTime,lastSignInDateTime,mfaDetail",
                    "$top": 999,
                },
            )
            users = users_data.get("value", [])
            total_users = len(users)
            enabled_users = sum(1 for user in users if user.get("accountEnabled", False))
            users_with_recent_signin = sum(
                1
                for user in users
                if user.get("lastSignInDateTime")
                and (
                    datetime.now(timezone.utc)
                    - datetime.fromisoformat(user["lastSignInDateTime"].replace("Z", "+00:00"))
                ).days
                < DEFAULT_TIMEOUT
            )
            quality_score = self._calculate_users_quality(
                total_users, enabled_users, users_with_recent_signin
            )
            evidence_data = {
                "users": users,
                "summary": {
                    "total_users": total_users,
                    "enabled_users": enabled_users,
                    "disabled_users": total_users - enabled_users,
                    "users_with_recent_signin": users_with_recent_signin,
                    "activity_rate": users_with_recent_signin / total_users * 100
                    if total_users > 0
                    else 0,
                },
            }
            return CollectionResult(
                success=True,
                evidence_items=[
                    self.create_evidence_item(
                        evidence_type="user_directory",
                        resource_id="users",
                        resource_name="Azure AD Users",
                        data=evidence_data,
                        compliance_controls=["CC6.1", "CC6.2", "CC6.7"],
                        quality_score=quality_score,
                        metadata={"source_system": "microsoft_365"},
                    )
                ],
                quality_score=quality_score,
                total_collected=total_users,
                collection_metadata={"evidence_type": "user_directory"},
            )
        except (requests.RequestException, KeyError, IndexError) as e:
            logger.error("Failed to collect users evidence: %s" % e)
            raise

    async def collect_groups_evidence(self) -> CollectionResult:
        """Collect Azure AD groups evidence."""
        try:
            groups_data = await self._make_graph_request(
                "groups",
                params={
                    "$select": "id,displayName,groupTypes,securityEnabled,mailEnabled,createdDateTime,membershipRule",
                    "$top": 999,
                },
            )
            groups = groups_data.get("value", [])
            security_groups = [g for g in groups if g.get("securityEnabled", False)]
            dynamic_groups = [g for g in groups if g.get("membershipRule")]
            quality_score = self._calculate_groups_quality(groups, security_groups)
            evidence_data = {
                "groups": groups,
                "summary": {
                    "total_groups": len(groups),
                    "security_groups": len(security_groups),
                    "dynamic_groups": len(dynamic_groups),
                    "distribution_groups": len([g for g in groups if g.get("mailEnabled", False)]),
                    "security_group_ratio": len(security_groups) / len(groups) * 100
                    if groups
                    else 0,
                },
            }
            return CollectionResult(
                success=True,
                evidence_items=[
                    self.create_evidence_item(
                        evidence_type="access_groups",
                        resource_id="groups",
                        resource_name="Azure AD Groups",
                        data=evidence_data,
                        compliance_controls=["CC6.1", "CC6.2", "CC6.3"],
                        quality_score=quality_score,
                        metadata={"source_system": "microsoft_365"},
                    )
                ],
                quality_score=quality_score,
                total_collected=len(groups),
                collection_metadata={"evidence_type": "access_groups"},
            )
        except (requests.RequestException, KeyError, IndexError) as e:
            logger.error("Failed to collect groups evidence: %s" % e)
            raise

    async def collect_applications_evidence(self) -> CollectionResult:
        """Collect Azure AD applications evidence."""
        try:
            apps_data = await self._make_graph_request(
                "applications",
                params={
                    "$select": "id,displayName,createdDateTime,signInAudience,requiredResourceAccess",
                    "$top": 999,
                },
            )
            applications = apps_data.get("value", [])
            sp_data = await self._make_graph_request(
                "servicePrincipals",
                params={
                    "$select": "id,displayName,servicePrincipalType,accountEnabled,createdDateTime",
                    "$top": 999,
                },
            )
            service_principals = sp_data.get("value", [])
            quality_score = self._calculate_applications_quality(applications, service_principals)
            evidence_data = {
                "applications": applications,
                "service_principals": service_principals,
                "summary": {
                    "total_applications": len(applications),
                    "total_service_principals": len(service_principals),
                    "enabled_service_principals": len(
                        [sp for sp in service_principals if sp.get("accountEnabled", False)]
                    ),
                    "multi_tenant_apps": len(
                        [
                            app
                            for app in applications
                            if app.get("signInAudience") == "AzureADMultipleOrgs"
                        ]
                    ),
                },
            }
            return CollectionResult(
                success=True,
                evidence_items=[
                    self.create_evidence_item(
                        evidence_type="applications",
                        resource_id="applications",
                        resource_name="Azure AD Applications",
                        data=evidence_data,
                        compliance_controls=["CC6.1", "CC6.2", "CC6.8"],
                        quality_score=quality_score,
                        metadata={"source_system": "microsoft_365"},
                    )
                ],
                quality_score=quality_score,
                total_collected=len(applications),
                collection_metadata={"evidence_type": "applications"},
            )
        except (requests.RequestException, KeyError, IndexError) as e:
            logger.error("Failed to collect applications evidence: %s" % e)
            raise

    async def collect_signin_logs_evidence(self) -> CollectionResult:
        """Collect Azure AD sign-in logs evidence."""
        try:
            start_date = (datetime.now(timezone.utc) - timedelta(days=7)).strftime(
                "%Y-%m-%dT%H:%M:%S.%fZ"
            )
            logs_data = await self._make_graph_request(
                "auditLogs/signIns",
                params={
                    "$filter": f"createdDateTime ge {start_date}",
                    "$select": "id,createdDateTime,userDisplayName,userPrincipalName,appDisplayName,status,riskLevel,clientAppUsed",
                    "$top": 1000,
                },
            )
            sign_ins = logs_data.get("value", [])
            successful_signins = [s for s in sign_ins if s.get("status", {}).get("errorCode") == 0]
            failed_signins = [s for s in sign_ins if s.get("status", {}).get("errorCode") != 0]
            risky_signins = [s for s in sign_ins if s.get("riskLevel") not in ["none", "low"]]
            quality_score = self._calculate_signin_logs_quality(
                sign_ins, successful_signins, failed_signins
            )
            evidence_data = {
                "sign_ins": sign_ins,
                "summary": {
                    "total_signins": len(sign_ins),
                    "successful_signins": len(successful_signins),
                    "failed_signins": len(failed_signins),
                    "risky_signins": len(risky_signins),
                    "success_rate": len(successful_signins) / len(sign_ins) * 100
                    if sign_ins
                    else 0,
                    "unique_users": len(set(s.get("userPrincipalName", "") for s in sign_ins)),
                    "unique_apps": len(set(s.get("appDisplayName", "") for s in sign_ins)),
                },
            }
            return CollectionResult(
                success=True,
                evidence_items=[
                    self.create_evidence_item(
                        evidence_type="user_access_logs",
                        resource_id="signin_logs",
                        resource_name="Azure AD Sign-in Logs",
                        data=evidence_data,
                        compliance_controls=["CC6.1", "CC6.2", "CC7.2"],
                        quality_score=quality_score,
                        metadata={"source_system": "microsoft_365"},
                    )
                ],
                quality_score=quality_score,
                total_collected=len(sign_ins),
                collection_metadata={"evidence_type": "user_access_logs"},
            )
        except (requests.RequestException, KeyError, IndexError) as e:
            logger.error("Failed to collect sign-in logs evidence: %s" % e)
            raise

    async def collect_audit_logs_evidence(self) -> CollectionResult:
        """Collect Azure AD audit logs evidence."""
        try:
            start_date = (datetime.now(timezone.utc) - timedelta(days=7)).strftime(
                "%Y-%m-%dT%H:%M:%S.%fZ"
            )
            logs_data = await self._make_graph_request(
                "auditLogs/directoryAudits",
                params={
                    "$filter": f"activityDateTime ge {start_date}",
                    "$select": "id,activityDateTime,activityDisplayName,category,result,initiatedBy,targetResources",
                    "$top": 1000,
                },
            )
            audit_logs = logs_data.get("value", [])
            user_activities = [log for log in audit_logs if log.get("category") == "UserManagement"]
            role_activities = [log for log in audit_logs if log.get("category") == "RoleManagement"]
            policy_activities = [log for log in audit_logs if log.get("category") == "Policy"]
            quality_score = self._calculate_audit_logs_quality(audit_logs)
            evidence_data = {
                "audit_logs": audit_logs,
                "summary": {
                    "total_events": len(audit_logs),
                    "user_management_events": len(user_activities),
                    "role_management_events": len(role_activities),
                    "policy_events": len(policy_activities),
                    "unique_initiators": len(
                        set(
                            log.get("initiatedBy", {}).get("user", {}).get("userPrincipalName", "")
                            for log in audit_logs
                        )
                    ),
                    "activity_types": list(
                        set(log.get("activityDisplayName", "") for log in audit_logs)
                    ),
                },
            }
            return CollectionResult(
                success=True,
                evidence_items=[
                    self.create_evidence_item(
                        evidence_type="admin_activity_logs",
                        resource_id="audit_logs",
                        resource_name="Azure AD Audit Logs",
                        data=evidence_data,
                        compliance_controls=["CC7.1", "CC7.2", "CC7.3"],
                        quality_score=quality_score,
                        metadata={"source_system": "microsoft_365"},
                    )
                ],
                quality_score=quality_score,
                total_collected=len(audit_logs),
                collection_metadata={"evidence_type": "admin_activity_logs"},
            )
        except (requests.RequestException, KeyError, IndexError) as e:
            logger.error("Failed to collect audit logs evidence: %s" % e)
            raise

    async def collect_organization_evidence(self) -> CollectionResult:
        """Collect Azure AD organization/tenant evidence."""
        try:
            org_data = await self._make_graph_request("organization")
            organization = org_data.get("value", [{}])[0]
            try:
                directory_data = await self._make_graph_request("directory")
                directory = directory_data
            except requests.RequestException:
                directory = {}
            quality_score = self._calculate_organization_quality(organization)
            evidence_data = {
                "organization": organization,
                "directory": directory,
                "summary": {
                    "tenant_id": organization.get("id"),
                    "display_name": organization.get("displayName"),
                    "verified_domains": len(organization.get("verifiedDomains", [])),
                    "created_datetime": organization.get("createdDateTime"),
                    "security_defaults_enabled": organization.get("securityDefaultsEnabled", False),
                },
            }
            return CollectionResult(
                success=True,
                evidence_items=[
                    self.create_evidence_item(
                        evidence_type="organization_configuration",
                        resource_id="organization",
                        resource_name="Azure AD Organization",
                        data=evidence_data,
                        compliance_controls=["CC6.1", "CC6.6"],
                        quality_score=quality_score,
                        metadata={"source_system": "microsoft_365"},
                    )
                ],
                quality_score=quality_score,
                total_collected=1,
                collection_metadata={"evidence_type": "organization_configuration"},
            )
        except (requests.RequestException, KeyError, IndexError) as e:
            logger.error("Failed to collect organization evidence: %s" % e)
            raise

    def _calculate_users_quality(self, total: int, enabled: int, active: int) -> EvidenceQuality:
        """Calculate quality score for users evidence."""
        if total == 0:
            return EvidenceQuality.LOW
        enabled_rate = enabled / total
        activity_rate = active / total
        if enabled_rate > HIGH_MFA_THRESHOLD and activity_rate > MEDIUM_MFA_THRESHOLD:
            return EvidenceQuality.HIGH
        elif enabled_rate > CONFIDENCE_THRESHOLD and activity_rate > HALF_RATIO:
            return EvidenceQuality.MEDIUM
        else:
            return EvidenceQuality.LOW

    def _calculate_groups_quality(
        self, groups: List[Dict], security_groups: List[Dict]
    ) -> EvidenceQuality:
        """Calculate quality score for groups evidence."""
        if not groups:
            return EvidenceQuality.LOW
        security_ratio = len(security_groups) / len(groups)
        if security_ratio > ACTIVITY_THRESHOLD:
            return EvidenceQuality.HIGH
        elif security_ratio > MEDIUM_SECURITY_THRESHOLD:
            return EvidenceQuality.MEDIUM
        else:
            return EvidenceQuality.LOW

    def _calculate_applications_quality(
        self, apps: List[Dict], service_principals: List[Dict]
    ) -> EvidenceQuality:
        """Calculate quality score for applications evidence."""
        if not apps and not service_principals:
            return EvidenceQuality.LOW
        total_apps = len(apps) + len(service_principals)
        enabled_sps = sum(1 for sp in service_principals if sp.get("accountEnabled", False))
        if total_apps > 0 and enabled_sps / len(service_principals) > CONFIDENCE_THRESHOLD:
            return EvidenceQuality.HIGH
        elif total_apps > 0:
            return EvidenceQuality.MEDIUM
        else:
            return EvidenceQuality.LOW

    def _calculate_signin_logs_quality(
        self, all_logs: List[Dict], successful: List[Dict], failed: List[Dict]
    ) -> EvidenceQuality:
        """Calculate quality score for sign-in logs evidence."""
        if not all_logs:
            return EvidenceQuality.LOW
        success_rate = len(successful) / len(all_logs)
        log_volume = len(all_logs)
        if success_rate > HIGH_CONFIDENCE_THRESHOLD and log_volume > DEFAULT_LIMIT:
            return EvidenceQuality.HIGH
        elif success_rate > HIGH_MFA_THRESHOLD and log_volume > LOG_VOLUME_THRESHOLD:
            return EvidenceQuality.MEDIUM
        else:
            return EvidenceQuality.LOW

    def _calculate_audit_logs_quality(self, audit_logs: List[Dict]) -> EvidenceQuality:
        """Calculate quality score for audit logs evidence."""
        if not audit_logs:
            return EvidenceQuality.LOW
        if len(audit_logs) > 50:
            return EvidenceQuality.HIGH
        elif len(audit_logs) > 20:
            return EvidenceQuality.MEDIUM
        else:
            return EvidenceQuality.LOW

    def _calculate_organization_quality(self, organization: Dict) -> EvidenceQuality:
        """Calculate quality score for organization evidence."""
        if not organization:
            return EvidenceQuality.LOW
        has_verified_domains = len(organization.get("verifiedDomains", [])) > 0
        has_security_defaults = organization.get("securityDefaultsEnabled", False)
        if has_verified_domains and has_security_defaults:
            return EvidenceQuality.HIGH
        elif has_verified_domains:
            return EvidenceQuality.MEDIUM
        else:
            return EvidenceQuality.LOW

    def get_supported_evidence_types(self) -> List[str]:
        """Get list of supported evidence types."""
        return [
            "user_directory",
            "access_groups",
            "applications",
            "user_access_logs",
            "admin_activity_logs",
            "organization_configuration",
        ]

    async def collect_all_evidence(self) -> List[CollectionResult]:
        """Collect all available evidence types."""
        results = []
        evidence_collectors = [
            self.collect_users_evidence,
            self.collect_groups_evidence,
            self.collect_applications_evidence,
            self.collect_signin_logs_evidence,
            self.collect_audit_logs_evidence,
            self.collect_organization_evidence,
        ]
        for collector in evidence_collectors:
            try:
                result = await collector()
                results.append(result)
            except (ValueError, TypeError) as e:
                logger.error("Failed to collect evidence with %s: %s" % (collector.__name__, e))
                continue
        return results
