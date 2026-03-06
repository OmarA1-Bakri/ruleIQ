"""

Simple data access layer for SMB-focused ownership model.
No complex RBAC - just owner-based access control.
"""

from typing import Any
from typing import List

from uuid import UUID
from sqlalchemy.orm import Session
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from fastapi import HTTPException, status
from database.user import User


class DataAccess:
    """Simple data access patterns for SMB users (1-5 users typically)."""

    @staticmethod
    def ensure_owner(
        db: Session,
        model: Any,
        resource_id: UUID,
        user: User,
        resource_name: str = "resource",
    ) -> Any:
        """
        Ensure user owns the resource or raise 403.
        For SMBs, ownership is simple: user_id must match.
        """
        resource = db.query(model).filter(model.id == resource_id).first()

        if not resource:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"{resource_name.capitalize()} not found",
            )

        # Simple ownership check - no complex roles
        if hasattr(resource, "user_id") and resource.user_id != user.id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"You don't have access to this {resource_name}",
            )

        # For resources with organization_id (future enhancement)
        if hasattr(resource, "organization_id") and hasattr(user, "organization_id"):
            if resource.organization_id != user.organization_id:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail=f"You don't have access to this {resource_name}",
                )

        return resource

    @staticmethod
    async def ensure_owner_async(
        db: AsyncSession,
        model: Any,
        resource_id: UUID,
        user: User,
        resource_name: str = "resource",
    ) -> Any:
        """
        Async version of ensure_owner for async endpoints.
        """
        stmt = select(model).where(model.id == resource_id)
        result = await db.execute(stmt)
        resource = result.scalars().first()

        if not resource:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"{resource_name.capitalize()} not found",
            )

        # Simple ownership check - no complex roles
        if hasattr(resource, "user_id") and resource.user_id != user.id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"You don't have access to this {resource_name}",
            )

        # For resources with organization_id (future enhancement)
        if hasattr(resource, "organization_id") and hasattr(user, "organization_id"):
            if resource.organization_id != user.organization_id:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail=f"You don't have access to this {resource_name}",
                )

        return resource

    @staticmethod
    def list_owned(
        db: Session, model: Any, user: User, limit: int = 100, offset: int = 0
    ) -> List[Any]:
        """
        List all resources owned by the user.
        For SMBs, this is typically a small list.
        """
        query = db.query(model)

        # Filter by user_id if the model has it
        if hasattr(model, "user_id"):
            query = query.filter(model.user_id == user.id)

        # Filter by organization_id if both have it (future)
        elif hasattr(model, "organization_id") and hasattr(user, "organization_id"):
            query = query.filter(model.organization_id == user.organization_id)

        return query.limit(limit).offset(offset).all()

    @staticmethod
    async def list_owned_async(
        db: AsyncSession, model: Any, user: User, limit: int = 100, offset: int = 0
    ) -> List[Any]:
        """
        Async version of list_owned.
        """
        stmt = select(model)

        # Filter by user_id if the model has it
        if hasattr(model, "user_id"):
            stmt = stmt.where(model.user_id == user.id)

        # Filter by organization_id if both have it (future)
        elif hasattr(model, "organization_id") and hasattr(user, "organization_id"):
            stmt = stmt.where(model.organization_id == user.organization_id)

        stmt = stmt.limit(limit).offset(offset)
        result = await db.execute(stmt)
        return result.scalars().all()

    @staticmethod
    def create_owned(db: Session, model: Any, user: User, **data) -> Any:
        """
        Create a resource owned by the user.
        Automatically sets user_id.
        """
        # Ensure user_id is set
        if hasattr(model, "user_id"):
            data["user_id"] = user.id

        # Set organization_id if applicable (future)
        if hasattr(model, "organization_id") and hasattr(user, "organization_id"):
            data["organization_id"] = user.organization_id

        resource = model(**data)
        db.add(resource)
        db.commit()
        db.refresh(resource)
        return resource

    @staticmethod
    async def create_owned_async(db: AsyncSession, model: Any, user: User, **data) -> Any:
        """
        Async version of create_owned.
        """
        # Ensure user_id is set
        if hasattr(model, "user_id"):
            data["user_id"] = user.id

        # Set organization_id if applicable (future)
        if hasattr(model, "organization_id") and hasattr(user, "organization_id"):
            data["organization_id"] = user.organization_id

        resource = model(**data)
        db.add(resource)
        await db.commit()
        await db.refresh(resource)
        return resource

    @staticmethod
    def delete_owned(
        db: Session,
        model: Any,
        resource_id: UUID,
        user: User,
        resource_name: str = "resource",
    ) -> bool:
        """
        Delete a resource if owned by the user.
        """
        resource = DataAccess.ensure_owner(db, model, resource_id, user, resource_name)
        db.delete(resource)
        db.commit()
        return True

    @staticmethod
    async def delete_owned_async(
        db: AsyncSession,
        model: Any,
        resource_id: UUID,
        user: User,
        resource_name: str = "resource",
    ) -> bool:
        """
        Async version of delete_owned.
        """
        resource = await DataAccess.ensure_owner_async(
            db,
            model,
            resource_id,
            user,
            resource_name,
        )
        await db.delete(resource)
        await db.commit()
        return True

    @staticmethod
    def count_owned(db: Session, model: Any, user: User) -> int:
        """
        Count resources owned by the user.
        Useful for subscription limits.
        """
        query = db.query(model)

        if hasattr(model, "user_id"):
            query = query.filter(model.user_id == user.id)
        elif hasattr(model, "organization_id") and hasattr(user, "organization_id"):
            query = query.filter(model.organization_id == user.organization_id)

        return query.count()

    @staticmethod
    async def count_owned_async(db: AsyncSession, model: Any, user: User) -> int:
        """
        Async version of count_owned.
        """
        from sqlalchemy import func

        stmt = select(func.count()).select_from(model)

        if hasattr(model, "user_id"):
            stmt = stmt.where(model.user_id == user.id)
        elif hasattr(model, "organization_id") and hasattr(user, "organization_id"):
            stmt = stmt.where(model.organization_id == user.organization_id)

        result = await db.execute(stmt)
        return result.scalar()
