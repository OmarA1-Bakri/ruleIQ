"""

Asynchronous service to manage report schedule configurations in the database.
"""

from datetime import datetime, timezone
from typing import Any, Dict, List
from uuid import UUID

from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from sqlalchemy.orm import selectinload

from core.exceptions import DatabaseException, NotFoundException
from database.report_schedule import ReportSchedule


class ReportScheduler:
    """Service to create, manage, and delete report schedules from the database."""

    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    async def create_schedule(
        self,
        user_id: UUID,
        business_profile_id: UUID,
        report_type: str,
        frequency: str,
        parameters: Dict[str, Any],
        recipients: List[str],
        active: bool = True,
    ) -> ReportSchedule:
        """Creates a new report schedule in the database."""
        try:
            new_schedule = ReportSchedule(
                user_id=user_id,
                business_profile_id=business_profile_id,
                report_type=report_type,
                frequency=frequency,
                parameters=parameters,
                recipients=recipients,
                active=active,
            )
            self.db.add(new_schedule)
            await self.db.commit()
            await self.db.refresh(new_schedule)
            return new_schedule
        except SQLAlchemyError as e:
            await self.db.rollback()
            raise DatabaseException("Failed to create report schedule.") from e

    async def get_schedule(self, schedule_id: UUID) -> ReportSchedule:
        """Retrieves a single report schedule by its ID."""
        try:
            res = await self.db.execute(
                select(ReportSchedule)
                .where(ReportSchedule.id == schedule_id)
                .options(selectinload(ReportSchedule.owner)),
            )
            schedule = res.scalars().first()
            if not schedule:
                raise NotFoundException(
                    f"Report schedule with ID {schedule_id} not found.",
                )
            return schedule
        except SQLAlchemyError as e:
            raise DatabaseException("Failed to retrieve report schedule.") from e

    async def get_active_schedules(self) -> List[ReportSchedule]:
        """Retrieves all active report schedules."""
        try:
            res = await self.db.execute(
                select(ReportSchedule)
                .where(ReportSchedule.active)
                .options(selectinload(ReportSchedule.owner)),
            )
            return res.scalars().all()
        except SQLAlchemyError as e:
            raise DatabaseException("Failed to retrieve active schedules.") from e

    async def update_schedule_status(
        self, schedule_id: UUID, status: str, distribution_successful: bool = False
    ) -> None:
        """Updates the status of a schedule after a run."""
        schedule = await self.get_schedule(schedule_id)
        if status == "success":
            schedule.last_run_at = datetime.now(timezone.utc)
        # In a real app, you might store more detailed status or logs
        self.db.add(schedule)
        await self.db.commit()

    async def update_schedule(self, schedule_id: UUID, updates: Dict[str, Any]) -> ReportSchedule:
        """Updates an existing report schedule."""
        schedule = await self.get_schedule(schedule_id)
        try:
            for key, value in updates.items():
                if hasattr(schedule, key):
                    setattr(schedule, key, value)

            self.db.add(schedule)
            await self.db.commit()
            await self.db.refresh(schedule)
            return schedule
        except SQLAlchemyError as e:
            await self.db.rollback()
            raise DatabaseException(f"Failed to update schedule {schedule_id}.") from e

    async def delete_schedule(self, schedule_id: UUID) -> None:
        """Deletes a report schedule."""
        schedule = await self.get_schedule(schedule_id)
        try:
            await self.db.delete(schedule)
            await self.db.commit()
        except SQLAlchemyError as e:
            await self.db.rollback()
            raise DatabaseException(f"Failed to delete schedule {schedule_id}.") from e
