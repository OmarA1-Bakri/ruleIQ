"""

Data Access Control Service

Implements data visibility controls based on user roles and organizational context.
Provides centralized management of data access permissions for UK compliance requirements.
"""

import logging
from typing import List, Any
from uuid import UUID
from sqlalchemy.orm import Session
from sqlalchemy import and_
from database.rbac import DataAccess, Role, UserRole
from database.business_profile import BusinessProfile
from api.dependencies.rbac_auth import UserWithRoles

logger = logging.getLogger(__name__)


class DataAccessService:
    """
    Service for managing data visibility and access controls.

    Implements hierarchical data access patterns:
    - own_data: User can only see their own data
    - organization_data: User can see data within their organization
    - all_data: User can see all data (admin level)
    """

    def __init__(self, db: Session) -> None:
        self.db = db

    def get_user_data_access_level(self, user_id: UUID) -> str:
        """
        Get the highest data access level for a user.

        Args:
            user_id: User ID to check

        Returns:
            Access level: 'own_data', 'organization_data', or 'all_data'
        """
        user_roles = (
            self.db.query(UserRole)
            .join(Role)
            .filter(and_(UserRole.user_id == user_id, UserRole.is_active, Role.is_active))
            .all()
        )
        if not user_roles:
            return "own_data"
        for user_role in user_roles:
            if user_role.role.name == "admin":
                return "all_data"
        for user_role in user_roles:
            if user_role.role.name in ["framework_manager", "assessor"]:
                return "organization_data"
        return "own_data"

    def can_access_business_profile(
        self, user: UserWithRoles, profile_id: UUID, profile_owner_id: UUID = None
    ) -> bool:
        """
        Check if user can access a specific business profile.

        Args:
            user: User with roles
            profile_id: Business profile ID
            profile_owner_id: Optional profile owner ID (for performance)

        Returns:
            True if user can access the profile
        """
        access_level = self.get_user_data_access_level(user.id)
        if access_level == "all_data":
            return True
        if profile_owner_id is None:
            profile = (
                self.db.query(BusinessProfile).filter(BusinessProfile.id == profile_id).first()
            )
            if not profile:
                return False
            profile_owner_id = profile.user_id
        if access_level == "own_data":
            return profile_owner_id == user.id
        return access_level == "organization_data"

    def filter_business_profiles_query(self, user: UserWithRoles, base_query) -> Any:
        """
        Filter a business profiles query based on user's data access level.

        Args:
            user: User with roles
            base_query: SQLAlchemy query to filter

        Returns:
            Filtered query
        """
        access_level = self.get_user_data_access_level(user.id)
        if access_level == "all_data":
            return base_query
        if access_level == "own_data":
            return base_query.filter(BusinessProfile.user_id == user.id)
        if access_level == "organization_data":
            return base_query
        return base_query.filter(BusinessProfile.user_id == user.id)

    def can_access_assessment(self, user: UserWithRoles, assessment_owner_id: UUID) -> bool:
        """
        Check if user can access a specific assessment.

        Args:
            user: User with roles
            assessment_owner_id: Assessment owner user ID

        Returns:
            True if user can access the assessment
        """
        access_level = self.get_user_data_access_level(user.id)
        if access_level == "all_data":
            return True
        if access_level == "own_data":
            return assessment_owner_id == user.id
        return access_level == "organization_data"

    def grant_data_access(
        self,
        user_id: UUID,
        access_type: str,
        business_profile_id: UUID = None,
        granted_by: UUID = None,
    ) -> DataAccess:
        """
        Grant specific data access to a user.

        Args:
            user_id: User to grant access to
            access_type: Access type ('own_data', 'organization_data', 'all_data')
            business_profile_id: Optional specific business profile
            granted_by: User who granted the access

        Returns:
            DataAccess instance
        """
        if access_type not in ["own_data", "organization_data", "all_data"]:
            raise ValueError("Invalid access type")
        existing = (
            self.db.query(DataAccess)
            .filter(
                and_(
                    DataAccess.user_id == user_id,
                    DataAccess.business_profile_id == business_profile_id,
                    DataAccess.is_active,
                )
            )
            .first()
        )
        if existing:
            existing.access_type = access_type
            existing.granted_by = granted_by
            self.db.commit()
            data_access = existing
        else:
            data_access = DataAccess(
                user_id=user_id,
                business_profile_id=business_profile_id,
                access_type=access_type,
                granted_by=granted_by,
            )
            self.db.add(data_access)
            self.db.commit()
            self.db.refresh(data_access)
        logger.info("Data access granted: user %s, type %s" % (user_id, access_type))
        return data_access

    def revoke_data_access(self, user_id: UUID, business_profile_id: UUID = None) -> bool:
        """
        Revoke data access from a user.

        Args:
            user_id: User to revoke access from
            business_profile_id: Optional specific business profile

        Returns:
            True if access was revoked
        """
        data_access = (
            self.db.query(DataAccess)
            .filter(
                and_(
                    DataAccess.user_id == user_id,
                    DataAccess.business_profile_id == business_profile_id,
                    DataAccess.is_active,
                )
            )
            .first()
        )
        if not data_access:
            return False
        data_access.is_active = False
        self.db.commit()
        logger.info("Data access revoked: user %s" % user_id)
        return True

    def get_accessible_business_profiles(self, user: UserWithRoles) -> List[UUID]:
        """
        Get list of business profile IDs accessible to a user.

        Args:
            user: User with roles

        Returns:
            List of accessible business profile IDs
        """
        access_level = self.get_user_data_access_level(user.id)
        if access_level == "all_data":
            profiles = self.db.query(BusinessProfile.id).all()
            return [profile.id for profile in profiles]
        if access_level == "own_data":
            profiles = (
                self.db.query(BusinessProfile.id).filter(BusinessProfile.user_id == user.id).all()
            )
            return [profile.id for profile in profiles]
        if access_level == "organization_data":
            profiles = self.db.query(BusinessProfile.id).all()
            return [profile.id for profile in profiles]
        return []


async def get_data_access_service(db: Session) -> DataAccessService:
    """
    Dependency for getting DataAccessService instance.
    """
    return DataAccessService(db)
