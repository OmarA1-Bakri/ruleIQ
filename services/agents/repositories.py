"""
Repository pattern implementation for agent database access.

This module provides abstraction layers for database operations,
separating business logic from data access concerns.
"""

from typing import Optional, List, Dict, Any, Generic, TypeVar
from abc import ABC, abstractmethod
from datetime import datetime
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, update, delete, and_, or_
from neo4j import AsyncGraphDatabase

from database.business_profile import BusinessProfile
from database.models.evidence import Evidence
from database.assessment_session import AssessmentSession
from config.logging_config import get_logger

logger = get_logger(__name__)

T = TypeVar('T')


class BaseRepository(ABC, Generic[T]):
    """Base repository interface."""
    
    @abstractmethod
    async def get_by_id(self, entity_id: Any) -> Optional[T]:
        """Get entity by ID."""
        pass
    
    @abstractmethod
    async def get_all(self, limit: int = 100, offset: int = 0) -> List[T]:
        """Get all entities with pagination."""
        pass
    
    @abstractmethod
    async def create(self, entity: T) -> T:
        """Create new entity."""
        pass
    
    @abstractmethod
    async def update(self, entity_id: Any, entity: T) -> Optional[T]:
        """Update existing entity."""
        pass
    
    @abstractmethod
    async def delete(self, entity_id: Any) -> bool:
        """Delete entity."""
        pass
    
    @abstractmethod
    async def exists(self, entity_id: Any) -> bool:
        """Check if entity exists."""
        pass


class BusinessProfileRepository(BaseRepository[BusinessProfile]):
    """Repository for business profile operations."""
    
    def __init__(self, session: AsyncSession):
        self.session = session
    
    async def get_by_id(self, profile_id: str) -> Optional[BusinessProfile]:
        """Get business profile by ID."""
        try:
            stmt = select(BusinessProfile).where(
                BusinessProfile.id == profile_id
            )
            result = await self.session.execute(stmt)
            return result.scalars().first()
        except Exception as e:
            logger.error(f"Error fetching business profile: {e}")
            return None
    
    async def get_all(
        self,
        limit: int = 100,
        offset: int = 0
    ) -> List[BusinessProfile]:
        """Get all business profiles with pagination."""
        try:
            stmt = select(BusinessProfile).limit(limit).offset(offset)
            result = await self.session.execute(stmt)
            return result.scalars().all()
        except Exception as e:
            logger.error(f"Error fetching business profiles: {e}")
            return []
    
    async def get_by_company_name(
        self,
        company_name: str
    ) -> Optional[BusinessProfile]:
        """Get business profile by company name."""
        try:
            stmt = select(BusinessProfile).where(
                BusinessProfile.company_name == company_name
            )
            result = await self.session.execute(stmt)
            return result.scalars().first()
        except Exception as e:
            logger.error(f"Error fetching by company name: {e}")
            return None
    
    async def get_by_industry(
        self,
        industry: str,
        limit: int = 100
    ) -> List[BusinessProfile]:
        """Get business profiles by industry."""
        try:
            stmt = select(BusinessProfile).where(
                BusinessProfile.industry == industry
            ).limit(limit)
            result = await self.session.execute(stmt)
            return result.scalars().all()
        except Exception as e:
            logger.error(f"Error fetching by industry: {e}")
            return []
    
    async def create(self, profile: BusinessProfile) -> BusinessProfile:
        """Create new business profile."""
        try:
            self.session.add(profile)
            await self.session.commit()
            await self.session.refresh(profile)
            return profile
        except Exception as e:
            await self.session.rollback()
            logger.error(f"Error creating business profile: {e}")
            raise
    
    async def update(
        self,
        profile_id: str,
        updates: Dict[str, Any]
    ) -> Optional[BusinessProfile]:
        """Update business profile."""
        try:
            stmt = update(BusinessProfile).where(
                BusinessProfile.id == profile_id
            ).values(**updates)
            await self.session.execute(stmt)
            await self.session.commit()
            return await self.get_by_id(profile_id)
        except Exception as e:
            await self.session.rollback()
            logger.error(f"Error updating business profile: {e}")
            return None
    
    async def delete(self, profile_id: str) -> bool:
        """Delete business profile."""
        try:
            stmt = delete(BusinessProfile).where(
                BusinessProfile.id == profile_id
            )
            result = await self.session.execute(stmt)
            await self.session.commit()
            return result.rowcount > 0
        except Exception as e:
            await self.session.rollback()
            logger.error(f"Error deleting business profile: {e}")
            return False
    
    async def exists(self, profile_id: str) -> bool:
        """Check if business profile exists."""
        try:
            stmt = select(BusinessProfile.id).where(
                BusinessProfile.id == profile_id
            )
            result = await self.session.execute(stmt)
            return result.first() is not None
        except Exception as e:
            logger.error(f"Error checking existence: {e}")
            return False


class EvidenceRepository(BaseRepository[Evidence]):
    """Repository for evidence operations."""
    
    def __init__(self, session: AsyncSession):
        self.session = session
    
    async def get_by_id(self, evidence_id: str) -> Optional[Evidence]:
        """Get evidence by ID."""
        try:
            stmt = select(Evidence).where(Evidence.id == evidence_id)
            result = await self.session.execute(stmt)
            return result.scalars().first()
        except Exception as e:
            logger.error(f"Error fetching evidence: {e}")
            return None
    
    async def get_by_business_profile(
        self,
        profile_id: str,
        limit: int = 100
    ) -> List[Evidence]:
        """Get all evidence for a business profile."""
        try:
            stmt = select(Evidence).where(
                Evidence.business_profile_id == profile_id
            ).limit(limit)
            result = await self.session.execute(stmt)
            return result.scalars().all()
        except Exception as e:
            logger.error(f"Error fetching evidence by profile: {e}")
            return []
    
    async def get_by_type(
        self,
        profile_id: str,
        evidence_type: str
    ) -> List[Evidence]:
        """Get evidence by type for a business profile."""
        try:
            stmt = select(Evidence).where(
                and_(
                    Evidence.business_profile_id == profile_id,
                    Evidence.evidence_type == evidence_type
                )
            )
            result = await self.session.execute(stmt)
            return result.scalars().all()
        except Exception as e:
            logger.error(f"Error fetching evidence by type: {e}")
            return []
    
    async def search_by_title(
        self,
        profile_id: str,
        search_term: str
    ) -> List[Evidence]:
        """Search evidence by title."""
        try:
            stmt = select(Evidence).where(
                and_(
                    Evidence.business_profile_id == profile_id,
                    Evidence.title.contains(search_term)
                )
            )
            result = await self.session.execute(stmt)
            return result.scalars().all()
        except Exception as e:
            logger.error(f"Error searching evidence: {e}")
            return []
    
    async def count_by_profile(self, profile_id: str) -> int:
        """Count evidence items for a profile."""
        try:
            from sqlalchemy import func
            stmt = select(func.count(Evidence.id)).where(
                Evidence.business_profile_id == profile_id
            )
            result = await self.session.execute(stmt)
            return result.scalar() or 0
        except Exception as e:
            logger.error(f"Error counting evidence: {e}")
            return 0
    
    async def get_all(
        self,
        limit: int = 100,
        offset: int = 0
    ) -> List[Evidence]:
        """Get all evidence with pagination."""
        try:
            stmt = select(Evidence).limit(limit).offset(offset)
            result = await self.session.execute(stmt)
            return result.scalars().all()
        except Exception as e:
            logger.error(f"Error fetching all evidence: {e}")
            return []
    
    async def create(self, evidence: Evidence) -> Evidence:
        """Create new evidence."""
        try:
            self.session.add(evidence)
            await self.session.commit()
            await self.session.refresh(evidence)
            return evidence
        except Exception as e:
            await self.session.rollback()
            logger.error(f"Error creating evidence: {e}")
            raise
    
    async def update(
        self,
        evidence_id: str,
        updates: Dict[str, Any]
    ) -> Optional[Evidence]:
        """Update evidence."""
        try:
            stmt = update(Evidence).where(
                Evidence.id == evidence_id
            ).values(**updates)
            await self.session.execute(stmt)
            await self.session.commit()
            return await self.get_by_id(evidence_id)
        except Exception as e:
            await self.session.rollback()
            logger.error(f"Error updating evidence: {e}")
            return None
    
    async def delete(self, evidence_id: str) -> bool:
        """Delete evidence."""
        try:
            stmt = delete(Evidence).where(Evidence.id == evidence_id)
            result = await self.session.execute(stmt)
            await self.session.commit()
            return result.rowcount > 0
        except Exception as e:
            await self.session.rollback()
            logger.error(f"Error deleting evidence: {e}")
            return False
    
    async def exists(self, evidence_id: str) -> bool:
        """Check if evidence exists."""
        try:
            stmt = select(Evidence.id).where(Evidence.id == evidence_id)
            result = await self.session.execute(stmt)
            return result.first() is not None
        except Exception as e:
            logger.error(f"Error checking existence: {e}")
            return False


class ComplianceRepository:
    """Repository for Neo4j compliance data operations."""
    
    def __init__(self, neo4j_service):
        self.neo4j = neo4j_service
    
    async def get_regulations(
        self,
        jurisdiction: Optional[str] = None,
        industry: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """Get regulations filtered by jurisdiction and industry."""
        try:
            query = """
            MATCH (r:Regulation)
            WHERE ($jurisdiction IS NULL OR r.jurisdiction = $jurisdiction)
            AND ($industry IS NULL OR r.industry = $industry OR r.industry = 'All')
            RETURN r.code as code, r.name as name, r.jurisdiction as jurisdiction
            """
            result = await self.neo4j.execute_query(
                query,
                {
                    "jurisdiction": jurisdiction,
                    "industry": industry
                }
            )
            return result.get("data", [])
        except Exception as e:
            logger.error(f"Error fetching regulations: {e}")
            return []
    
    async def get_requirements_for_regulation(
        self,
        regulation_code: str
    ) -> List[Dict[str, Any]]:
        """Get all requirements for a specific regulation."""
        try:
            query = """
            MATCH (r:Regulation {code: $code})-[:HAS_REQUIREMENT]->(req:Requirement)
            RETURN req.id as id, req.title as title, 
                   req.description as description, req.risk_level as risk_level
            ORDER BY req.risk_level DESC
            """
            result = await self.neo4j.execute_query(
                query,
                {"code": regulation_code}
            )
            return result.get("data", [])
        except Exception as e:
            logger.error(f"Error fetching requirements: {e}")
            return []
    
    async def search_compliance_resources(
        self,
        search_term: str,
        resource_type: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """Search compliance resources by term."""
        try:
            query = """
            MATCH (n)
            WHERE (n.name CONTAINS $term OR n.title CONTAINS $term 
                   OR n.description CONTAINS $term)
            AND ($type IS NULL OR labels(n)[0] = $type)
            RETURN labels(n)[0] as type, n.name as name, 
                   n.title as title, n.description as description
            LIMIT 50
            """
            result = await self.neo4j.execute_query(
                query,
                {
                    "term": search_term,
                    "type": resource_type
                }
            )
            return result.get("data", [])
        except Exception as e:
            logger.error(f"Error searching resources: {e}")
            return []
    
    async def get_compliance_gaps(
        self,
        business_profile: Dict[str, Any],
        regulations: List[str]
    ) -> List[Dict[str, Any]]:
        """Identify compliance gaps for a business."""
        try:
            query = """
            MATCH (r:Regulation)-[:HAS_REQUIREMENT]->(req:Requirement)
            WHERE r.code IN $regulations
            AND NOT EXISTS {
                MATCH (bp:BusinessProfile {id: $profile_id})-[:HAS_EVIDENCE]->(e:Evidence)
                WHERE e.requirement_id = req.id
            }
            RETURN r.code as regulation, req.id as requirement_id,
                   req.title as requirement, req.risk_level as risk_level
            ORDER BY req.risk_level DESC
            """
            result = await self.neo4j.execute_query(
                query,
                {
                    "regulations": regulations,
                    "profile_id": business_profile.get("id")
                }
            )
            return result.get("data", [])
        except Exception as e:
            logger.error(f"Error identifying gaps: {e}")
            return []
    
    async def get_control_mappings(
        self,
        requirement_id: str
    ) -> List[Dict[str, Any]]:
        """Get control mappings for a requirement."""
        try:
            query = """
            MATCH (req:Requirement {id: $req_id})-[:MAPS_TO_CONTROL]->(c:Control)
            RETURN c.id as control_id, c.name as control_name,
                   c.description as description, c.category as category
            """
            result = await self.neo4j.execute_query(
                query,
                {"req_id": requirement_id}
            )
            return result.get("data", [])
        except Exception as e:
            logger.error(f"Error fetching control mappings: {e}")
            return []


class AssessmentSessionRepository(BaseRepository[AssessmentSession]):
    """Repository for assessment session operations."""
    
    def __init__(self, session: AsyncSession):
        self.session = session
    
    async def get_by_id(self, session_id: str) -> Optional[AssessmentSession]:
        """Get assessment session by ID."""
        try:
            stmt = select(AssessmentSession).where(
                AssessmentSession.id == session_id
            )
            result = await self.session.execute(stmt)
            return result.scalars().first()
        except Exception as e:
            logger.error(f"Error fetching assessment session: {e}")
            return None
    
    async def get_by_business_profile(
        self,
        profile_id: str,
        limit: int = 10
    ) -> List[AssessmentSession]:
        """Get assessment sessions for a business profile."""
        try:
            stmt = select(AssessmentSession).where(
                AssessmentSession.business_profile_id == profile_id
            ).order_by(
                AssessmentSession.created_at.desc()
            ).limit(limit)
            result = await self.session.execute(stmt)
            return result.scalars().all()
        except Exception as e:
            logger.error(f"Error fetching sessions by profile: {e}")
            return []
    
    async def get_active_sessions(
        self,
        profile_id: Optional[str] = None
    ) -> List[AssessmentSession]:
        """Get active assessment sessions."""
        try:
            stmt = select(AssessmentSession).where(
                AssessmentSession.status == "in_progress"
            )
            if profile_id:
                stmt = stmt.where(
                    AssessmentSession.business_profile_id == profile_id
                )
            result = await self.session.execute(stmt)
            return result.scalars().all()
        except Exception as e:
            logger.error(f"Error fetching active sessions: {e}")
            return []
    
    async def update_progress(
        self,
        session_id: str,
        questions_answered: int,
        compliance_score: Optional[float] = None
    ) -> Optional[AssessmentSession]:
        """Update assessment progress."""
        try:
            updates = {
                "questions_answered": questions_answered,
                "updated_at": datetime.utcnow()
            }
            if compliance_score is not None:
                updates["compliance_score"] = compliance_score
            
            stmt = update(AssessmentSession).where(
                AssessmentSession.id == session_id
            ).values(**updates)
            await self.session.execute(stmt)
            await self.session.commit()
            return await self.get_by_id(session_id)
        except Exception as e:
            await self.session.rollback()
            logger.error(f"Error updating progress: {e}")
            return None
    
    async def complete_session(
        self,
        session_id: str,
        final_score: float,
        risk_level: str,
        recommendations: List[Dict[str, Any]]
    ) -> Optional[AssessmentSession]:
        """Complete an assessment session."""
        try:
            stmt = update(AssessmentSession).where(
                AssessmentSession.id == session_id
            ).values(
                status="completed",
                compliance_score=final_score,
                risk_level=risk_level,
                recommendations=recommendations,
                completed_at=datetime.utcnow(),
                updated_at=datetime.utcnow()
            )
            await self.session.execute(stmt)
            await self.session.commit()
            return await self.get_by_id(session_id)
        except Exception as e:
            await self.session.rollback()
            logger.error(f"Error completing session: {e}")
            return None
    
    async def get_all(
        self,
        limit: int = 100,
        offset: int = 0
    ) -> List[AssessmentSession]:
        """Get all assessment sessions."""
        try:
            stmt = select(AssessmentSession).limit(limit).offset(offset)
            result = await self.session.execute(stmt)
            return result.scalars().all()
        except Exception as e:
            logger.error(f"Error fetching all sessions: {e}")
            return []
    
    async def create(
        self,
        session: AssessmentSession
    ) -> AssessmentSession:
        """Create new assessment session."""
        try:
            self.session.add(session)
            await self.session.commit()
            await self.session.refresh(session)
            return session
        except Exception as e:
            await self.session.rollback()
            logger.error(f"Error creating session: {e}")
            raise
    
    async def update(
        self,
        session_id: str,
        updates: Dict[str, Any]
    ) -> Optional[AssessmentSession]:
        """Update assessment session."""
        try:
            stmt = update(AssessmentSession).where(
                AssessmentSession.id == session_id
            ).values(**updates)
            await self.session.execute(stmt)
            await self.session.commit()
            return await self.get_by_id(session_id)
        except Exception as e:
            await self.session.rollback()
            logger.error(f"Error updating session: {e}")
            return None
    
    async def delete(self, session_id: str) -> bool:
        """Delete assessment session."""
        try:
            stmt = delete(AssessmentSession).where(
                AssessmentSession.id == session_id
            )
            result = await self.session.execute(stmt)
            await self.session.commit()
            return result.rowcount > 0
        except Exception as e:
            await self.session.rollback()
            logger.error(f"Error deleting session: {e}")
            return False
    
    async def exists(self, session_id: str) -> bool:
        """Check if session exists."""
        try:
            stmt = select(AssessmentSession.id).where(
                AssessmentSession.id == session_id
            )
            result = await self.session.execute(stmt)
            return result.first() is not None
        except Exception as e:
            logger.error(f"Error checking existence: {e}")
            return False