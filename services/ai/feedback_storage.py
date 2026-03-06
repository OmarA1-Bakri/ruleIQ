"""

Feedback Storage Service

Handles persistent storage and retrieval of feedback data.
Integrates with LangSmith for feedback submission and local storage for caching.
"""

import json
import logging
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional
import asyncio
from collections import deque
import csv
from services.ai.feedback_analyzer import FeedbackItem

logger = logging.getLogger(__name__)


class FeedbackStorage:
    """
    Manages feedback storage, retrieval, and synchronization with LangSmith.
    """

    def __init__(self, storage_path: Optional[str] = None) -> None:
        """
        Initialize feedback storage.

        Args:
            storage_path: Path to storage directory (defaults to data/feedback)
        """
        self.storage_path = Path(storage_path or "data/feedback")
        self.storage_path.mkdir(parents=True, exist_ok=True)
        self._feedback_cache: Dict[str, FeedbackItem] = {}
        self._submission_queue: deque = deque(maxlen=1000)
        self._load_feedback_from_disk()
        logger.info("Feedback storage initialized at %s" % self.storage_path)

    def _load_feedback_from_disk(self) -> None:
        """Load previously stored feedback from disk into memory cache."""
        feedback_file = self.storage_path / "feedback.json"
        if feedback_file.exists():
            try:
                with open(feedback_file, "r") as f:
                    data = json.load(f)
                    for item_data in data:
                        try:
                            feedback_item = FeedbackItem(**item_data)
                            self._feedback_cache[feedback_item.feedback_id] = feedback_item
                        except Exception as e:
                            logger.warning("Skipping invalid feedback item: %s" % e)
                logger.info("Loaded %s feedback items from disk" % len(self._feedback_cache))
            except Exception as e:
                logger.error("Error loading feedback from disk: %s" % e)

    async def store_feedback(self, feedback: FeedbackItem) -> bool:
        """
        Store feedback item in memory and persist to disk.

        Args:
            feedback: FeedbackItem to store

        Returns:
            True if successfully stored, False otherwise
        """
        try:
            self._feedback_cache[feedback.feedback_id] = feedback
            self._submission_queue.append(feedback)
            await self._persist_to_disk()
            if len(self._submission_queue) >= 10:
                await self._process_submission_queue()
            logger.debug("Stored feedback %s" % feedback.feedback_id)
            return True
        except Exception as e:
            logger.error("Error storing feedback: %s" % e)
            return False

    async def _persist_to_disk(self) -> None:
        """Persist current feedback cache to disk."""
        try:
            feedback_file = self.storage_path / "feedback.json"
            feedback_data = []
            for feedback in self._feedback_cache.values():
                feedback_data.append(
                    feedback.to_dict() if hasattr(feedback, "to_dict") else feedback.__dict__
                )
            temp_file = feedback_file.with_suffix(".tmp")
            with open(temp_file, "w") as f:
                json.dump(feedback_data, f, indent=2, default=str)
            temp_file.replace(feedback_file)
            logger.debug("Persisted %s items to disk" % len(feedback_data))
        except Exception as e:
            logger.error("Error persisting feedback to disk: %s" % e)

    async def _process_submission_queue(self) -> None:
        """Process queued feedback for submission to LangSmith."""
        if not self._submission_queue:
            return
        batch = []
        while self._submission_queue and len(batch) < 50:
            batch.append(self._submission_queue.popleft())
        if batch:
            await self._submit_to_langsmith(batch)

    async def _submit_to_langsmith(self, feedback_items: List[FeedbackItem]) -> bool:
        """
        Submit feedback batch to LangSmith.

        Args:
            feedback_items: List of feedback items to submit

        Returns:
            True if successful, False otherwise
        """
        try:
            logger.info("Would submit %s items to LangSmith" % len(feedback_items))
            await asyncio.sleep(0.1)
            return True
        except Exception as e:
            logger.error("Error submitting to LangSmith: %s" % e)
            for item in feedback_items:
                self._submission_queue.append(item)
            return False

    async def get_feedback_by_id(self, feedback_id: str) -> Optional[Dict[str, Any]]:
        """
        Retrieve a specific feedback item by ID.

        Args:
            feedback_id: Unique feedback identifier

        Returns:
            Feedback item as dictionary or None if not found
        """
        feedback = self._feedback_cache.get(feedback_id)
        if feedback:
            return feedback.to_dict() if hasattr(feedback, "to_dict") else feedback.__dict__
        return None

    async def get_feedback_by_run(self, run_id: str) -> List[Dict[str, Any]]:
        """
        Retrieve all feedback for a specific run.

        Args:
            run_id: LangSmith run ID

        Returns:
            List of feedback items as dictionaries
        """
        feedback_items = []
        for feedback in self._feedback_cache.values():
            if feedback.run_id == run_id:
                feedback_items.append(
                    feedback.to_dict() if hasattr(feedback, "to_dict") else feedback.__dict__
                )
        return feedback_items

    async def get_feedback_by_user(self, user_id: str) -> List[Dict[str, Any]]:
        """
        Retrieve all feedback from a specific user.

        Args:
            user_id: User identifier

        Returns:
            List of feedback items as dictionaries
        """
        feedback_items = []
        for feedback in self._feedback_cache.values():
            if feedback.user_id == user_id:
                feedback_items.append(
                    feedback.to_dict() if hasattr(feedback, "to_dict") else feedback.__dict__
                )
        return feedback_items

    async def get_all_feedback(self) -> List[Dict[str, Any]]:
        """
        Retrieve all stored feedback.

        Returns:
            List of all feedback items as dictionaries
        """
        return [f.model_dump() for f in self._feedback_cache.values()]

    async def export_feedback(
        self,
        format: str = "json",
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
    ) -> Dict[str, Any]:
        """
        Export feedback data to file.

        Args:
            format: Export format (json or csv)
            start_date: Optional start date filter
            end_date: Optional end date filter

        Returns:
            Export result with file path and record count
        """
        try:
            feedback_items = []
            for feedback in self._feedback_cache.values():
                feedback_dict = (
                    feedback.to_dict() if hasattr(feedback, "to_dict") else feedback.__dict__
                )
                item_date = datetime.fromisoformat(
                    feedback_dict.get("timestamp", datetime.now(timezone.utc).isoformat())
                )
                if start_date and item_date < start_date:
                    continue
                if end_date and item_date > end_date:
                    continue
                feedback_items.append(feedback_dict)
            timestamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
            filename = f"feedback_export_{timestamp}.{format}"
            export_path = self.storage_path / "exports"
            export_path.mkdir(exist_ok=True)
            file_path = export_path / filename
            if format == "json":
                with open(file_path, "w") as f:
                    json.dump(feedback_items, f, indent=2, default=str)
            elif format == "csv":
                if feedback_items:
                    all_keys = set()
                    for item in feedback_items:
                        all_keys.update(item.keys())
                    with open(file_path, "w", newline="") as f:
                        writer = csv.DictWriter(f, fieldnames=sorted(all_keys))
                        writer.writeheader()
                        writer.writerows(feedback_items)
                else:
                    with open(file_path, "w", newline="") as f:
                        f.write(
                            """feedback_id,run_id,user_id,feedback_type,value,comment,timestamp
""",
                        )
            logger.info("Exported %s feedback items to %s" % (len(feedback_items), file_path))
            return {"file_path": str(file_path), "record_count": len(feedback_items)}
        except Exception as e:
            logger.error("Error exporting feedback: %s" % e)
            raise

    async def import_feedback(self, file_path: str) -> Dict[str, Any]:
        """
        Import feedback data from file.

        Args:
            file_path: Path to import file

        Returns:
            Import result with record count and status
        """
        try:
            imported_count = 0
            skipped_count = 0
            file_path = Path(file_path)
            if not file_path.exists():
                raise FileNotFoundError(f"File not found: {file_path}")
            if file_path.suffix == ".json":
                with open(file_path, "r") as f:
                    data = json.load(f)
                for item_data in data:
                    try:
                        feedback = FeedbackItem(**item_data)
                        if feedback.feedback_id not in self._feedback_cache:
                            self._feedback_cache[feedback.feedback_id] = feedback
                            imported_count += 1
                        else:
                            skipped_count += 1
                    except Exception as e:
                        logger.warning("Skipping invalid item: %s" % e)
                        skipped_count += 1
            elif file_path.suffix == ".csv":
                with open(file_path, "r") as f:
                    reader = csv.DictReader(f)
                    for row in reader:
                        try:
                            feedback = FeedbackItem(**row)
                            if feedback.feedback_id not in self._feedback_cache:
                                self._feedback_cache[feedback.feedback_id] = feedback
                                imported_count += 1
                            else:
                                skipped_count += 1
                        except Exception as e:
                            logger.warning("Skipping invalid CSV row: %s" % e)
                            skipped_count += 1
            else:
                raise ValueError(
                    f"Unsupported file format: {file_path.suffix}",
                )
            await self._persist_to_disk()
            logger.info("Imported %s items, skipped %s" % (imported_count, skipped_count))
            return {
                "imported": imported_count,
                "skipped": skipped_count,
                "total": imported_count + skipped_count,
            }
        except Exception as e:
            logger.error("Error importing feedback: %s" % e)
            raise

    async def cleanup_old_feedback(self, days: int = 90) -> int:
        """
        Remove feedback older than specified days.

        Args:
            days: Number of days to keep feedback

        Returns:
            Number of items removed
        """
        try:
            cutoff_date = datetime.now(timezone.utc) - timedelta(days=days)
            removed_count = 0
            items_to_remove = []
            for feedback_id, feedback in self._feedback_cache.items():
                feedback_dict = (
                    feedback.to_dict() if hasattr(feedback, "to_dict") else feedback.__dict__
                )
                item_date = datetime.fromisoformat(
                    feedback_dict.get("timestamp", datetime.now(timezone.utc).isoformat())
                )
                if item_date < cutoff_date:
                    items_to_remove.append(feedback_id)
            for feedback_id in items_to_remove:
                del self._feedback_cache[feedback_id]
                removed_count += 1
            if removed_count > 0:
                await self._persist_to_disk()
            logger.info("Removed %s old feedback items" % removed_count)
            return removed_count
        except Exception as e:
            logger.error("Error cleaning up old feedback: %s" % e)
            return 0
