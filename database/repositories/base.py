"""Base repository pattern implementation."""

from typing import TypeVar, Generic, List, Optional, Type
from uuid import UUID
from sqlalchemy.orm import Session

T = TypeVar("T")


class BaseRepository(Generic[T]):
    """Base repository class providing common CRUD operations."""

    def __init__(self, model_class: Type[T], session: Session) -> None:
        self.model_class = model_class
        self.session = session

    def get(self, id: UUID) -> Optional[T]:
        """Get entity by ID."""
        return (
            self.session.query(self.model_class)
            .filter(getattr(self.model_class, "id", None) == id)
            .first()
        )

    def get_all(self) -> List[T]:
        """Get all entities."""
        return self.session.query(self.model_class).all()

    def create(self, entity: T) -> T:
        """Create new entity."""
        self.session.add(entity)
        self.session.commit()
        self.session.refresh(entity)
        return entity

    def update(self, entity: T) -> T:
        """Update existing entity."""
        self.session.commit()
        self.session.refresh(entity)
        return entity

    def delete(self, entity: T) -> None:
        """Delete entity."""
        self.session.delete(entity)
        self.session.commit()

    def exists(self, id: UUID) -> bool:
        """Check if entity exists."""
        return self.session.query(
            self.session.query(self.model_class)
            .filter(getattr(self.model_class, "id", None) == id)
            .exists()
        ).scalar()

    def count(self) -> int:
        """Count total entities."""
        return self.session.query(self.model_class).count()

    def save_changes(self) -> None:
        """Commit current transaction."""
        self.session.commit()
