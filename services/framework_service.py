"""
import logging


logger = logging.getLogger(__name__)
Asynchronous service for managing compliance frameworks.
"""

from typing import Dict, List, Optional
from uuid import UUID
from sqlalchemy import select
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession
from config.logging_config import get_logger
from core.exceptions import DatabaseException, NotFoundException
from database.business_profile import BusinessProfile
from database.compliance_framework import ComplianceFramework
from database.user import User

logger = get_logger(__name__)


async def get_all_frameworks(db: AsyncSession) -> List[ComplianceFramework]:
    """Get all available compliance frameworks."""
    try:
        result = await db.execute(
            select(ComplianceFramework)
            .where(ComplianceFramework.is_active)
            .order_by(ComplianceFramework.name)
        )
        return result.scalars().all()
    except SQLAlchemyError as e:
        logger.error("Database error while getting all frameworks: %s" % e, exc_info=True)
        raise DatabaseException("Failed to retrieve compliance frameworks.") from e


async def get_framework_by_id(
    db: AsyncSession, user: User, framework_id: UUID
) -> Optional[ComplianceFramework]:
    """Get a specific compliance framework by ID."""
    try:
        result = await db.execute(
            select(ComplianceFramework).where(ComplianceFramework.id == framework_id)
        )
        framework = result.scalars().first()
        if not framework:
            raise NotFoundException("Framework", framework_id)
        return framework
    except SQLAlchemyError as e:
        logger.error(
            "Database error while getting framework %s: %s" % (framework_id, e), exc_info=True
        )
        raise DatabaseException("Failed to retrieve framework by ID.") from e


async def get_framework_by_name(db: AsyncSession, name: str) -> Optional[ComplianceFramework]:
    """Get a specific compliance framework by name."""
    try:
        result = await db.execute(
            select(ComplianceFramework).where(ComplianceFramework.name == name)
        )
        return result.scalars().first()
    except SQLAlchemyError as e:
        logger.error(
            "Database error while getting framework by name '%s': %s" % (name, e), exc_info=True
        )
        raise DatabaseException("Failed to retrieve framework by name.") from e


def calculate_framework_relevance(
    profile: BusinessProfile, framework: ComplianceFramework
) -> float:
    """Calculate a relevance score for a framework based on a business profile."""
    score = 0.0
    if profile.industry in framework.applicable_indu:
        score += 50
    if framework.employee_thresh and profile.employee_count >= framework.employee_thresh:
        score += 25
    if profile.data_sensitivity in ["High", "Medium"] and framework.category == "Data Protection":
        score += 25
    return score


async def get_relevant_frameworks(db: AsyncSession, user: User) -> List[Dict]:
    """Get compliance frameworks relevant to the user's business profile with relevance scores."""
    try:
        profile_res = await db.execute(
            select(BusinessProfile).where(BusinessProfile.user_id == user.id)
        )
        profile = profile_res.scalars().first()
        if not profile:
            logger.warning(
                "No business profile found for user %s to determine relevant frameworks." % user.id
            )
            return []
        frameworks = await get_all_frameworks(db)
        relevant_frameworks = []
        for framework in frameworks:
            relevance_score = calculate_framework_relevance(profile, framework)
            if relevance_score > 0:
                relevant_frameworks.append(
                    {"framework": framework.to_dict(), "relevance_score": relevance_score}
                )
        return sorted(relevant_frameworks, key=lambda x: x["relevance_score"], reverse=True)
    except SQLAlchemyError as e:
        logger.error(
            "Database error while getting relevant frameworks for user %s: %s" % (user.id, e),
            exc_info=True,
        )
        raise DatabaseException("Failed to retrieve relevant frameworks.") from e


async def initialize_default_frameworks(db: AsyncSession) -> None:
    """Populate the database with a default set of compliance frameworks."""
    frameworks_data = [
        {
            "name": "GDPR",
            "display_name": "General Data Protection Regulation",
            "description": "EU regulation on data protection and privacy for individuals within the European Union and European Economic Area",
            "category": "Data Protection",
            "applicable_indu": ["All"],
            "employee_thresh": 1,
            "geographic_scop": ["EU", "UK"],
            "key_requirement": [
                "Lawful basis for processing",
                "Data subject rights",
                "Privacy by design and default",
                "Data protection impact assessments",
                "Breach notification",
            ],
            "control_domains": [
                "Data Processing",
                "Consent Management",
                "Data Subject Rights",
                "Privacy Impact Assessment",
                "Breach Management",
            ],
            "complexity_scor": 3,
            "implementation_": 16,
            "estimated_cost_": "£10,000-£50,000",
        },
        {
            "name": "Cyber Essentials",
            "display_name": "Cyber Essentials",
            "description": "A UK government-backed scheme to help organizations protect against common cyber attacks.",
            "category": "Cybersecurity",
            "applicable_indu": ["All"],
            "employee_thresh": 1,
            "geographic_scop": ["UK"],
            "key_requirement": [
                "Boundary firewalls and internet gateways",
                "Secure configuration",
                "Access control",
                "Malware protection",
                "Patch management",
            ],
            "control_domains": [
                "Network Security",
                "System Configuration",
                "Access Management",
                "Malware Protection",
                "Update Management",
            ],
            "complexity_scor": 2,
            "implementation_": 8,
            "estimated_cost_": "£5,000-£15,000",
        },
        {
            "name": "ISO 27001",
            "display_name": "ISO 27001 Information Security Management",
            "description": "International standard for information security management systems",
            "category": "Information Security",
            "applicable_indu": ["All"],
            "employee_thresh": 50,
            "geographic_scop": ["Global"],
            "key_requirement": [
                "Information Security Management System",
                "Risk Assessment and Treatment",
                "Security Controls Implementation",
                "Continuous Monitoring",
                "Management Review",
            ],
            "control_domains": [
                "ISMS Framework",
                "Risk Management",
                "Asset Management",
                "Access Control",
                "Cryptography",
                "Physical Security",
                "Incident Management",
            ],
            "complexity_scor": 4,
            "implementation_": 20,
            "estimated_cost_": "£20,000-£75,000",
        },
    ]
    try:
        for framework_data in frameworks_data:
            existing = await get_framework_by_name(db, framework_data["name"])
            if not existing:
                logger.info("Creating new framework: %s" % framework_data["name"])
                framework = ComplianceFramework(**framework_data)
                db.add(framework)
        await db.commit()
    except SQLAlchemyError as e:
        await db.rollback()
        logger.error("Database error while initializing default frameworks: %s" % e, exc_info=True)
        raise DatabaseException("Failed to initialize default frameworks.") from e
