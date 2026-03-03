"""

# Constants
DEFAULT_LIMIT = 100


Audit Log Export API for SMB compliance tracking.
Provides audit trail exports for compliance and security auditing.
"""
from typing import Dict, List, Optional, Any
from datetime import datetime, timedelta, timezone
from fastapi import APIRouter, Depends, HTTPException, status, Response
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_, or_
from pydantic import BaseModel
import csv
import io
import json
from api.dependencies.auth import get_current_active_user, require_auth
from api.dependencies.database import get_async_db
from database.user import User
from database.rbac import AuditLog
router = APIRouter(tags=['Audit Export'])


class AuditLogEntry(BaseModel):
    """Single audit log entry."""
    timestamp: datetime
    user_email: str
    action: str
    resource_type: Optional[str] = None
    resource_id: Optional[str] = None
    ip_address: Optional[str] = None
    user_agent: Optional[str] = None
    status: str
    metadata: Optional[Dict] = None


class AuditExportRequest(BaseModel):
    """Request parameters for audit log export."""
    start_date: datetime
    end_date: datetime
    format: str = 'csv'
    action_filter: Optional[List[str]] = None
    include_system: bool = False


@router.post('/audit/export')
@require_auth
async def export_audit_logs(request: AuditExportRequest, current_user: User
    =Depends(get_current_active_user), db: AsyncSession=Depends(get_async_db)
    ) ->Any:
    """
    Export audit logs for the current user's organization.

    Supports CSV, JSON, and TXT formats for compliance reporting.
    SMB owners can only export logs related to their own organization.
    """
    query = select(AuditLog).where(and_(AuditLog.user_id == current_user.id,
        AuditLog.timestamp >= request.start_date, AuditLog.timestamp <=
        request.end_date))
    if request.action_filter:
        query = query.where(AuditLog.action.in_(request.action_filter))
    if not request.include_system:
        query = query.where(~AuditLog.action.startswith('system:'))
    query = query.order_by(AuditLog.timestamp.desc())
    result = await db.execute(query)
    logs = result.scalars().all()
    if request.format == 'csv':
        return _export_csv(logs, current_user)
    elif request.format == 'json':
        return _export_json(logs, current_user)
    elif request.format == 'txt':
        return _export_txt(logs, current_user)
    else:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail
            =f'Unsupported export format: {request.format}')


@router.get('/audit/recent')
@require_auth
async def get_recent_audit_logs(current_user: User=Depends(
    get_current_active_user), db: AsyncSession=Depends(get_async_db), days:
    int=7, limit: int=100) ->Dict[str, Any]:
    """
    Get recent audit logs for the current user.

    Shows activity from the last N days for security monitoring.
    """
    cutoff_date = datetime.now(timezone.utc) - timedelta(days=days)
    query = select(AuditLog).where(and_(AuditLog.user_id == current_user.id,
        AuditLog.timestamp >= cutoff_date)).order_by(AuditLog.timestamp.desc()
        ).limit(limit)
    result = await db.execute(query)
    logs = result.scalars().all()
    entries = []
    for log in logs:
        try:
            metadata = json.loads(log.metadata) if log.metadata else {}
        except json.JSONDecodeError:
            metadata = {}
        entry = AuditLogEntry(timestamp=log.timestamp, user_email=
            current_user.email, action=log.action, resource_type=log.
            resource_type, resource_id=log.resource_id, ip_address=log.
            ip_address, user_agent=log.user_agent, status=log.status,
            metadata=metadata)
        entries.append(entry)
    return {'total': len(entries), 'period_days': days, 'entries': entries}


@router.get('/audit/security-events')
@require_auth
async def get_security_events(current_user: User=Depends(
    get_current_active_user), db: AsyncSession=Depends(get_async_db), days:
    int=30) ->Dict[str, Any]:
    """
    Get security-related audit events.

    Focuses on login attempts, permission changes, and data access.
    """
    cutoff_date = datetime.now(timezone.utc) - timedelta(days=days)
    security_actions = ['login_attempt', 'login_success', 'login_failure',
        'logout', 'password_change', 'password_reset', 'mfa_enabled',
        'mfa_disabled', 'mfa_challenge', 'permission_granted',
        'permission_revoked', 'api_key_created', 'api_key_revoked',
        'suspicious_activity', 'rate_limit_exceeded']
    query = select(AuditLog).where(and_(AuditLog.user_id == current_user.id,
        AuditLog.timestamp >= cutoff_date, or_(*[AuditLog.action.contains(
        action) for action in security_actions]))).order_by(AuditLog.
        timestamp.desc())
    result = await db.execute(query)
    logs = result.scalars().all()
    events_by_type = {}
    for log in logs:
        event_type = _categorize_security_event(log.action)
        if event_type not in events_by_type:
            events_by_type[event_type] = []
        events_by_type[event_type].append({'timestamp': log.timestamp.
            isoformat(), 'action': log.action, 'ip_address': log.ip_address,
            'status': log.status, 'details': json.loads(log.metadata) if
            log.metadata else {}})
    failed_logins = len([log for log in logs if 'login_failure' in log.action])
    successful_logins = len([log for log in logs if 'login_success' in log.
        action])
    return {'period_days': days, 'total_events': len(logs),
        'failed_login_attempts': failed_logins, 'successful_logins':
        successful_logins, 'events_by_type': events_by_type,
        'recommendation': _get_security_recommendation(failed_logins,
        successful_logins)}


@router.get('/audit/compliance-report')
@require_auth
async def generate_compliance_report(current_user: User=Depends(
    get_current_active_user), db: AsyncSession=Depends(get_async_db),
    framework: Optional[str]=None) ->Any:
    """
    Generate a compliance-focused audit report.

    Summarizes audit trail for compliance documentation.
    """
    cutoff_date = datetime.now(timezone.utc) - timedelta(days=90)
    query = select(AuditLog).where(and_(AuditLog.user_id == current_user.id,
        AuditLog.timestamp >= cutoff_date))
    result = await db.execute(query)
    logs = result.scalars().all()
    data_access_logs = [log for log in logs if _is_data_access(log.action)]
    modification_logs = [log for log in logs if _is_modification(log.action)]
    security_logs = [log for log in logs if _is_security_event(log.action)]
    report = {'report_date': datetime.now(timezone.utc).isoformat(),
        'period': {'start': cutoff_date.isoformat(), 'end': datetime.now(
        timezone.utc).isoformat(), 'days': 90}, 'summary': {'total_events':
        len(logs), 'data_access_events': len(data_access_logs),
        'data_modifications': len(modification_logs), 'security_events':
        len(security_logs)}, 'compliance_checks': {'audit_trail_maintained':
        len(logs) > 0, 'user_activity_tracked': True, 'data_access_logged':
        len(data_access_logs) > 0, 'modifications_tracked': len(
        modification_logs) > 0, 'security_events_monitored': len(
        security_logs) > 0}, 'recommendations':
        _get_compliance_recommendations(logs)}
    if framework:
        report['framework_specific'] = _get_framework_specific_report(framework
            , logs)
    return report


def _export_csv(logs: List[AuditLog], user: User) ->StreamingResponse:
    """Export logs as CSV."""
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(['Timestamp', 'User', 'Action', 'Resource Type',
        'Resource ID', 'IP Address', 'User Agent', 'Status', 'Details'])
    for log in logs:
        writer.writerow([log.timestamp.isoformat(), user.email, log.action,
            log.resource_type or '', log.resource_id or '', log.ip_address or
            '', log.user_agent or '', log.status, log.metadata or ''])
    output.seek(0)
    filename = (
        f"audit_log_{datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S')}.csv"
        )
    return StreamingResponse(io.BytesIO(output.getvalue().encode()),
        media_type='text/csv', headers={'Content-Disposition':
        f'attachment; filename={filename}'})


def _export_json(logs: List[AuditLog], user: User) ->Response:
    """Export logs as JSON."""
    data = []
    for log in logs:
        try:
            metadata = json.loads(log.metadata) if log.metadata else {}
        except json.JSONDecodeError:
            metadata = {}
        data.append({'timestamp': log.timestamp.isoformat(), 'user': user.
            email, 'action': log.action, 'resource_type': log.resource_type,
            'resource_id': log.resource_id, 'ip_address': log.ip_address,
            'user_agent': log.user_agent, 'status': log.status, 'metadata':
            metadata})
    filename = (
        f"audit_log_{datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S')}.json"
        )
    return Response(content=json.dumps(data, indent=2), media_type=
        'application/json', headers={'Content-Disposition':
        f'attachment; filename={filename}'})


def _export_txt(logs: List[AuditLog], user: User) ->StreamingResponse:
    """Export logs as plain text."""
    output = io.StringIO()
    output.write(
        f'Audit Log Export - {datetime.now(timezone.utc).isoformat()}\n')
    output.write(f'User: {user.email}\n')
    output.write('=' * 80 + '\n\n')
    for log in logs:
        output.write(f'[{log.timestamp.isoformat()}] {log.action}\n')
        output.write(f'  Status: {log.status}\n')
        if log.resource_type:
            output.write(f'  Resource: {log.resource_type}/{log.resource_id}\n'
                )
        if log.ip_address:
            output.write(f'  IP: {log.ip_address}\n')
        if log.metadata:
            output.write(f'  Details: {log.metadata}\n')
        output.write('\n')
    output.seek(0)
    filename = (
        f"audit_log_{datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S')}.txt"
        )
    return StreamingResponse(io.BytesIO(output.getvalue().encode()),
        media_type='text/plain', headers={'Content-Disposition':
        f'attachment; filename={filename}'})


def _categorize_security_event(action: str) ->str:
    """Categorize security event type."""
    if 'login' in action or 'logout' in action:
        return 'authentication'
    elif 'password' in action:
        return 'password_management'
    elif 'mfa' in action:
        return 'multi_factor_auth'
    elif 'permission' in action or 'role' in action:
        return 'access_control'
    elif 'api_key' in action:
        return 'api_security'
    elif 'rate_limit' in action or 'suspicious' in action:
        return 'threat_detection'
    else:
        return 'other'


def _get_security_recommendation(failed_logins: int, successful_logins: int
    ) ->str:
    """Generate security recommendation based on events."""
    if failed_logins > successful_logins * 0.5:
        return (
            'High number of failed login attempts detected. Consider enabling MFA.'
            )
    elif failed_logins > 10:
        return (
            'Multiple failed login attempts detected. Review account security.'
            )
    else:
        return 'Security events within normal parameters.'


def _is_data_access(action: str) ->bool:
    """Check if action is data access related."""
    access_keywords = ['view', 'read', 'get', 'list', 'search', 'export']
    return any(keyword in action.lower() for keyword in access_keywords)


def _is_modification(action: str) ->bool:
    """Check if action is data modification related."""
    modify_keywords = ['create', 'update', 'delete', 'edit', 'change', 'modify'
        ]
    return any(keyword in action.lower() for keyword in modify_keywords)


def _is_security_event(action: str) ->bool:
    """Check if action is security related."""
    security_keywords = ['login', 'logout', 'password', 'permission',
        'role', 'mfa', 'auth']
    return any(keyword in action.lower() for keyword in security_keywords)


def _get_compliance_recommendations(logs: List[AuditLog]) ->List[str]:
    """Generate compliance recommendations."""
    recommendations = []
    if len(logs) < DEFAULT_LIMIT:
        recommendations.append(
            'Low audit activity - ensure all significant actions are being logged'
            )
    backup_logs = [log for log in logs if 'backup' in log.action.lower()]
    if not backup_logs:
        recommendations.append(
            'No backup activity detected - implement regular data backups')
    review_logs = [log for log in logs if 'review' in log.action.lower() or
        'audit' in log.action.lower()]
    if not review_logs:
        recommendations.append('Consider performing regular security audits')
    if not recommendations:
        recommendations.append('Audit logging appears to be functioning well')
    return recommendations


def _get_framework_specific_report(framework: str, logs: List[AuditLog]
    ) ->Dict:
    """Generate framework-specific compliance report section."""
    if framework.upper() == 'GDPR':
        return {'data_access_requests': len([log for log in logs if
            'data_access_request' in log.action]), 'data_deletion_requests':
            len([log for log in logs if 'data_deletion' in log.action]),
            'consent_updates': len([log for log in logs if 'consent' in log
            .action]), 'breach_notifications': len([log for log in logs if
            'breach' in log.action])}
    elif framework.upper() == 'ISO27001':
        return {'access_control_events': len([log for log in logs if
            _is_security_event(log.action)]), 'change_management': len([log for
            log in logs if _is_modification(log.action)]),
            'incident_responses': len([log for log in logs if 'incident' in
            log.action]), 'risk_assessments': len([log for log in logs if
            'risk' in log.action])}
    else:
        return {'message': f'No specific report format for {framework}'}
