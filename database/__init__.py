"""
Database models package.
Import all models to ensure they are registered with SQLAlchemy.
Provides database initialization utilities.
"""

# Import database setup and initialization
from .db_setup import (
    Base,
    init_db,
    test_database_connection,
    test_async_database_connection,
    cleanup_db_connections,
    get_engine_info,
    get_db,
    get_async_db,
    get_async_session_maker,
    get_db_context,
    DatabaseConfig,
    _ASYNC_SESSION_LOCAL as _AsyncSessionLocal,
    _SESSION_LOCAL,
)

# Import all models to ensure they're registered with SQLAlchemy
from .user import User
from .business_profile import BusinessProfile
from .compliance_framework import ComplianceFramework
from .evidence_item import EvidenceItem
from .assessment_session import AssessmentSession
from .assessment_question import AssessmentQuestion
from .implementation_plan import ImplementationPlan
from .readiness_assessment import ReadinessAssessment
from .generated_policy import GeneratedPolicy
from .chat_conversation import ChatConversation
from .chat_message import ChatMessage
from .report_schedule import ReportSchedule

# Freemium models
from .assessment_lead import AssessmentLead
from .freemium_assessment_session import FreemiumAssessmentSession
from .ai_question_bank import AIQuestionBank
from .lead_scoring_event import LeadScoringEvent
from .conversion_event import ConversionEvent
from .models.policy import Policy
from .models.evidence import Evidence
from .models.integrations import (
    Integration,
    EvidenceCollection,
    IntegrationEvidenceItem,
    IntegrationHealthLog,
    EvidenceAuditLog,
)
from .rbac import (
    Role,
    Permission,
    UserRole,
    RolePermission,
    FrameworkAccess,
    UserSession,
    AuditLog,
    DataAccess,
)


__all__ = [
    # Database setup and utilities
    "Base",
    "init_db",
    "test_database_connection",
    "test_async_database_connection",
    "cleanup_db_connections",
    "get_engine_info",
    "get_db",
    "get_async_db",
    "get_async_session_maker",
    "get_db_context",
    "DatabaseConfig",
    # Legacy exports for backward compatibility
    "_AsyncSessionLocal",
    "_SESSION_LOCAL",
    # Models
    "User",
    "BusinessProfile",
    "ComplianceFramework",
    "EvidenceItem",
    "AssessmentSession",
    "AssessmentQuestion",
    "ImplementationPlan",
    "ReadinessAssessment",
    "GeneratedPolicy",
    "ChatConversation",
    "ChatMessage",
    "ReportSchedule",
    # Freemium models
    "AssessmentLead",
    "FreemiumAssessmentSession",
    "AIQuestionBank",
    "LeadScoringEvent",
    "ConversionEvent",
    "Policy",
    "Evidence",
    "Integration",
    "EvidenceCollection",
    "IntegrationEvidenceItem",
    "IntegrationHealthLog",
    "EvidenceAuditLog",
    # RBAC models
    "Role",
    "Permission",
    "UserRole",
    "RolePermission",
    "FrameworkAccess",
    "UserSession",
    "AuditLog",
    "DataAccess",
]
