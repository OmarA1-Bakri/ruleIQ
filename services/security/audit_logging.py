"""

Audit Logging Service for comprehensive security event tracking
"""

import hashlib
import json
from datetime import datetime, timedelta, timezone
from typing import Dict, List, Any, Optional
from enum import Enum
import uuid
from sqlalchemy.orm import Session
from database.rbac import AuditLog
from services.cache_service import CacheService
from config.settings import settings
import logging

logger = logging.getLogger(__name__)


class AuditEventType(Enum):
    """Types of audit events"""

    AUTHENTICATION = "authentication"
    AUTHORIZATION = "authorization"
    DATA_ACCESS = "data_access"
    DATA_MODIFICATION = "data_modification"
    CONFIGURATION_CHANGE = "configuration_change"
    SECURITY_ALERT = "security_alert"
    SYSTEM = "system"


class AuditEventAction(Enum):
    """Audit event actions"""

    LOGIN = "login"
    LOGOUT = "logout"
    LOGIN_FAILED = "login_failed"
    PASSWORD_CHANGE = "password_change"
    MFA_ENABLED = "mfa_enabled"
    MFA_DISABLED = "mfa_disabled"
    PERMISSION_GRANTED = "permission_granted"
    PERMISSION_DENIED = "permission_denied"
    ROLE_ASSIGNED = "role_assigned"
    ROLE_REMOVED = "role_removed"
    CREATE = "create"
    READ = "read"
    UPDATE = "update"
    DELETE = "delete"
    EXPORT = "export"
    IMPORT = "import"
    CONFIG_CHANGE = "config_change"
    SERVICE_START = "service_start"
    SERVICE_STOP = "service_stop"
    BACKUP = "backup"
    RESTORE = "restore"


class AuditLoggingService:
    """Service for comprehensive audit logging"""

    def __init__(self, cache_service: Optional[CacheService] = None) -> None:
        """Initialize audit logging service"""
        self.cache = cache_service or CacheService()
        self.retention_days = settings.audit_log_retention_days or 90
        self.real_time_alerts_enabled = settings.real_time_security_alerts or True
        self.previous_hash = None

    async def log_event(
        self,
        event_type: AuditEventType,
        action: AuditEventAction,
        user_id: Optional[str] = None,
        resource: Optional[str] = None,
        resource_id: Optional[str] = None,
        ip_address: Optional[str] = None,
        user_agent: Optional[str] = None,
        result: str = "SUCCESS",
        error_message: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
        db: Optional[Session] = None,
    ) -> str:
        """
        Log an audit event

        Returns:
            Event ID
        """
        event_id = self._generate_event_id()
        truncated_resource = resource[:50] if resource and len(resource) > 50 else resource
        audit_log = {
            "user_id": user_id,
            "action": f"{event_type.value}:{action.value}",
            "resource_type": truncated_resource,
            "resource_id": resource_id,
            "ip_address": ip_address,
            "user_agent": user_agent,
            "severity": "error" if result == "FAILURE" else "info",
            "details": json.dumps(
                {
                    "event_id": event_id,
                    "event_type": event_type.value,
                    "action": action.value,
                    "result": result,
                    "error_message": error_message,
                    "metadata": metadata or {},
                }
            ),
        }
        if db:
            db_log = AuditLog(**audit_log)
            db.add(db_log)
            db.commit()
        await self._cache_event(audit_log)
        await self._check_security_alerts(audit_log)
        logger.info("Audit Event: %s by %s" % (action.value, user_id or "system"))
        return event_id

    async def log_authentication(
        self,
        user_id: str,
        action: str,
        success: bool,
        ip_address: str,
        user_agent: str = None,
        metadata: Dict[str, Any] = None,
        db: Session = None,
    ) -> str:
        """Log authentication events"""
        return await self.log_event(
            event_type=AuditEventType.AUTHENTICATION,
            action=AuditEventAction.LOGIN if success else AuditEventAction.LOGIN_FAILED,
            user_id=user_id,
            ip_address=ip_address,
            user_agent=user_agent,
            result="SUCCESS" if success else "FAILURE",
            metadata=metadata,
            db=db,
        )

    async def log_authorization(
        self,
        user_id: str,
        resource: str,
        permission: str,
        granted: bool,
        metadata: Dict[str, Any] = None,
        db: Session = None,
    ) -> str:
        """Log authorization events"""
        return await self.log_event(
            event_type=AuditEventType.AUTHORIZATION,
            action=AuditEventAction.PERMISSION_GRANTED
            if granted
            else AuditEventAction.PERMISSION_DENIED,
            user_id=user_id,
            resource=resource,
            result="SUCCESS" if granted else "DENIED",
            metadata={**{"permission": permission}, **(metadata or {})},
            db=db,
        )

    async def log_data_access(
        self,
        user_id: str,
        resource: str,
        resource_id: str,
        action: str,
        metadata: Dict[str, Any] = None,
        db: Session = None,
    ) -> str:
        """Log data access events"""
        action_map = {
            "create": AuditEventAction.CREATE,
            "read": AuditEventAction.READ,
            "update": AuditEventAction.UPDATE,
            "delete": AuditEventAction.DELETE,
            "export": AuditEventAction.EXPORT,
        }
        return await self.log_event(
            event_type=AuditEventType.DATA_ACCESS,
            action=action_map.get(action.lower(), AuditEventAction.READ),
            user_id=user_id,
            resource=resource,
            resource_id=resource_id,
            metadata=metadata,
            db=db,
        )

    async def log_configuration_change(
        self,
        user_id: str,
        setting_name: str,
        old_value: Any,
        new_value: Any,
        metadata: Dict[str, Any] = None,
        db: Session = None,
    ) -> str:
        """Log configuration changes"""
        return await self.log_event(
            event_type=AuditEventType.CONFIGURATION_CHANGE,
            action=AuditEventAction.CONFIG_CHANGE,
            user_id=user_id,
            resource=setting_name,
            metadata={"old_value": old_value, "new_value": new_value, **(metadata or {})},
            db=db,
        )

    async def get_user_events(
        self, user_id: str, limit: int = 100, db: Session = None
    ) -> List[Dict[str, Any]]:
        """Get audit events for a specific user"""
        if db:
            events = (
                db.query(AuditLog)
                .filter(AuditLog.user_id == user_id)
                .order_by(AuditLog.timestamp.desc())
                .limit(limit)
                .all()
            )
            return [self._log_to_dict(event) for event in events]
        cached_events = await self.cache.get(f"audit:user:{user_id}")
        return cached_events or []

    async def get_failed_logins(
        self, user_id: Optional[str] = None, hours: int = 24, db: Session = None
    ) -> List[Dict[str, Any]]:
        """Get failed login attempts"""
        since = datetime.now(timezone.utc) - timedelta(hours=hours)
        if db:
            query = db.query(AuditLog).filter(
                AuditLog.action == AuditEventAction.LOGIN_FAILED.value, AuditLog.timestamp >= since
            )
            if user_id:
                query = query.filter(AuditLog.user_id == user_id)
            events = query.all()
            return [self._log_to_dict(event) for event in events]
        return []

    async def get_security_events(
        self, hours: int = 24, db: Session = None
    ) -> List[Dict[str, Any]]:
        """Get security-related events"""
        since = datetime.now(timezone.utc) - timedelta(hours=hours)
        security_actions = [
            AuditEventAction.LOGIN_FAILED.value,
            AuditEventAction.PERMISSION_DENIED.value,
            AuditEventAction.MFA_DISABLED.value,
        ]
        if db:
            events = (
                db.query(AuditLog)
                .filter(AuditLog.action.in_(security_actions), AuditLog.timestamp >= since)
                .all()
            )
            return [self._log_to_dict(event) for event in events]
        return []

    async def verify_log_integrity(self, event_id: str, db: Session) -> bool:
        """Verify audit log hasn't been tampered with"""
        log = db.query(AuditLog).filter(AuditLog.event_id == event_id).first()
        if not log:
            return False
        log_dict = self._log_to_dict(log)
        expected_hash = self._calculate_hash(log_dict)
        return expected_hash == log.hash_chain

    async def cleanup_old_logs(self, db: Session) -> int:
        """Clean up logs older than retention period"""
        cutoff_date = datetime.now(timezone.utc) - timedelta(days=self.retention_days)
        old_logs = db.query(AuditLog).filter(AuditLog.timestamp < cutoff_date).all()
        count = len(old_logs)
        db.query(AuditLog).filter(AuditLog.timestamp < cutoff_date).delete()
        db.commit()
        logger.info("Cleaned up %s audit logs older than %s days" % (count, self.retention_days))
        return count

    def _generate_event_id(self) -> str:
        """Generate unique event ID"""
        return f"evt_{uuid.uuid4().hex[:16]}"

    def _generate_hash_chain(self, log_entry: Dict[str, Any]) -> str:
        """Generate hash for tamper detection"""
        if self.previous_hash:
            log_entry["previous_hash"] = self.previous_hash
        hash_value = self._calculate_hash(log_entry)
        self.previous_hash = hash_value
        return hash_value

    def _calculate_hash(self, log_entry: Dict[str, Any]) -> str:
        """Calculate SHA256 hash of log entry"""
        content = json.dumps(log_entry, sort_keys=True, default=str)
        return hashlib.sha256(content.encode()).hexdigest()

    async def _cache_event(self, log_entry: Dict[str, Any]) -> None:
        """Cache event for real-time access"""
        if log_entry.get("user_id"):
            user_key = f"audit:user:{log_entry['user_id']}"
            user_events = await self.cache.get(user_key) or []
            user_events.insert(0, log_entry)
            user_events = user_events[:100]
            await self.cache.set(user_key, user_events, expire_seconds=3600)
        if log_entry["action"] in [
            AuditEventAction.LOGIN_FAILED.value,
            AuditEventAction.PERMISSION_DENIED.value,
        ]:
            security_key = "audit:security:recent"
            security_events = await self.cache.get(security_key) or []
            security_events.insert(0, log_entry)
            security_events = security_events[:50]
            await self.cache.set(security_key, security_events, expire_seconds=3600)

    async def _check_security_alerts(self, log_entry: Dict[str, Any]) -> None:
        """Check if event triggers security alerts"""
        if not self.real_time_alerts_enabled:
            return
        alerts = []
        if log_entry["action"] == AuditEventAction.LOGIN_FAILED.value:
            user_id = log_entry.get("user_id")
            if user_id:
                recent_failures = await self.get_failed_logins(
                    user_id,
                    hours=1,
                )
                if len(recent_failures) >= 5:
                    alerts.append(
                        {
                            "type": "MULTIPLE_FAILED_LOGINS",
                            "user_id": user_id,
                            "count": len(recent_failures),
                        }
                    )
        if log_entry["action"] == AuditEventAction.PERMISSION_DENIED.value:
            if "admin" in str(log_entry.get("event_metadata", {})).lower():
                alerts.append(
                    {
                        "type": "PRIVILEGE_ESCALATION_ATTEMPT",
                        "user_id": log_entry.get("user_id"),
                        "resource": log_entry.get("resource"),
                    }
                )
        for alert in alerts:
            await self._send_security_alert(alert)

    async def _send_security_alert(self, alert: Dict[str, Any]) -> None:
        """Send security alert notification"""
        logger.warning("SECURITY ALERT: %s" % alert)
        alerts_key = "audit:alerts:active"
        alerts = await self.cache.get(alerts_key) or []
        alerts.append({**alert, "timestamp": datetime.now(timezone.utc).isoformat()})
        await self.cache.set(alerts_key, alerts, expire_seconds=3600)

    def _log_to_dict(self, log: AuditLog) -> Dict[str, Any]:
        """Convert database log to dictionary"""
        details = json.loads(log.details) if log.details else {}
        return {
            "event_id": details.get("event_id"),
            "timestamp": log.timestamp.isoformat() if log.timestamp else None,
            "event_type": details.get("event_type"),
            "action": log.action,
            "user_id": str(log.user_id) if log.user_id else None,
            "resource": log.resource_type,
            "resource_id": log.resource_id,
            "ip_address": log.ip_address,
            "user_agent": log.user_agent,
            "result": details.get("result"),
            "error_message": details.get("error_message"),
            "metadata": details.get("metadata"),
            "severity": log.severity,
        }


_audit_service: Optional[AuditLoggingService] = None


def get_audit_service() -> AuditLoggingService:
    """Get audit logging service instance"""
    global _audit_service
    if _audit_service is None:
        _audit_service = AuditLoggingService()
    return _audit_service
