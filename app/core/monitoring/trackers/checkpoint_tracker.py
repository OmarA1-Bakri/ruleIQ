"""
Checkpoint metrics tracking for LangGraph workflows.
"""

import time
from contextlib import contextmanager
from datetime import datetime, timedelta
from typing import Any, Dict, Generator, List, Optional


class CheckpointMetricsTracker:
    """Tracks checkpoint operations in LangGraph."""

    def __init__(self) -> None:
        """Initialize checkpoint metrics."""
        self._save_times: List[float] = []
        self._load_times: List[float] = []
        self._checkpoint_sizes: Dict[str, int] = {}
        self._save_failures = 0
        self._load_failures = 0
        self._total_saves = 0
        self._total_loads = 0
        self._save_error_types: List[str] = []
        self._load_error_types: List[str] = []
        self._active_saves: Dict[str, Dict[str, Any]] = {}
        self._active_loads: Dict[str, Dict[str, Any]] = {}
        self._checkpoint_timestamps: Dict[str, datetime] = {}

    @contextmanager
    def track_save(self, checkpoint_id: str) -> Generator[Any, None, None]:
        """Track checkpoint save operation.

        Args:
            checkpoint_id: Checkpoint identifier
        """
        start_time = time.time()
        self._total_saves += 1
        try:
            yield
            duration = time.time() - start_time
            self._save_times.append(duration)
        except (ValueError, TypeError):
            self._save_failures += 1
            raise

    @contextmanager
    def track_load(self, checkpoint_id: str) -> Generator[Any, None, None]:
        """Track checkpoint load operation.

        Args:
            checkpoint_id: Checkpoint identifier
        """
        start_time = time.time()
        self._total_loads += 1
        try:
            yield
            duration = time.time() - start_time
            self._load_times.append(duration)
        except (ValueError, TypeError):
            self._load_failures += 1
            raise

    def record_checkpoint_size(self, checkpoint_id: str, size_bytes: int) -> None:
        """Record checkpoint size.

        Args:
            checkpoint_id: Checkpoint identifier
            size_bytes: Size in bytes
        """
        self._checkpoint_sizes[checkpoint_id] = size_bytes

    def get_statistics(self) -> Dict[str, Any]:
        """Get checkpoint statistics.

        Returns:
            Statistics dictionary
        """
        stats = {
            "total_saves": self._total_saves,
            "total_loads": self._total_loads,
            "save_failures": self._save_failures,
            "load_failures": self._load_failures,
            "save_failure_rate": self._save_failures / max(1, self._total_saves),
            "load_failure_rate": self._load_failures / max(1, self._total_loads),
        }

        if self._save_times:
            stats["save_time_avg"] = sum(self._save_times) / len(self._save_times)
            stats["save_time_min"] = min(self._save_times)
            stats["save_time_max"] = max(self._save_times)

        if self._load_times:
            stats["load_time_avg"] = sum(self._load_times) / len(self._load_times)
            stats["load_time_min"] = min(self._load_times)
            stats["load_time_max"] = max(self._load_times)

        if self._checkpoint_sizes:
            sizes = list(self._checkpoint_sizes.values())
            stats["checkpoint_size_avg"] = sum(sizes) / len(sizes)
            stats["checkpoint_size_min"] = min(sizes)
            stats["checkpoint_size_max"] = max(sizes)
            stats["total_storage_bytes"] = sum(sizes)

        return stats

    def get_retention_metrics(self, retention_days: int = 7) -> Dict[str, Any]:
        """Get metrics for checkpoint retention.

        Args:
            retention_days: Retention period in days

        Returns:
            Retention metrics
        """
        total_checkpoints = len(self._checkpoint_sizes)
        total_size = sum(self._checkpoint_sizes.values())

        return {
            "total_checkpoints": total_checkpoints,
            "total_size_bytes": total_size,
            "retention_days": retention_days,
            "estimated_daily_growth": total_size / max(1, retention_days),
            "checkpoints_per_day": total_checkpoints / max(1, retention_days),
        }

    def record_checkpoint_save(
        self,
        workflow_id: str,
        checkpoint_size_bytes: int,
        storage_backend: str = "memory",
        compression_ratio: float = 1.0,
    ) -> str:
        """Record the start of a checkpoint save operation.

        Args:
            workflow_id: ID of the workflow being checkpointed
            checkpoint_size_bytes: Size of the checkpoint in bytes
            storage_backend: Storage backend being used
            compression_ratio: Compression ratio achieved

        Returns:
            Checkpoint ID for tracking
        """
        checkpoint_id = f"ckpt-{workflow_id}-{int(time.time() * 1000)}"

        self._active_saves[checkpoint_id] = {
            "workflow_id": workflow_id,
            "size_bytes": checkpoint_size_bytes,
            "storage_backend": storage_backend,
            "compression_ratio": compression_ratio,
            "start_time": time.time(),
        }

        self.record_checkpoint_size(checkpoint_id, checkpoint_size_bytes)
        return checkpoint_id

    def complete_checkpoint_save(
        self,
        checkpoint_id: str,
        success: bool = True,
        error_type: Optional[str] = None,
        error_message: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Complete a checkpoint save operation.

        Args:
            checkpoint_id: ID of the checkpoint operation
            success: Whether the save was successful
            error_type: Type of error if failed
            error_message: Error message if failed

        Returns:
            Save metrics
        """
        if checkpoint_id not in self._active_saves:
            return {"error": "Unknown checkpoint ID"}

        save_info = self._active_saves.pop(checkpoint_id)
        duration = time.time() - save_info["start_time"]

        if success:
            self._save_times.append(duration)
            self._total_saves += 1
        else:
            self._save_failures += 1
            if error_type:
                self._save_error_types.append(error_type)

        return {
            "checkpoint_id": checkpoint_id,
            "workflow_id": save_info["workflow_id"],
            "duration_ms": duration * 1000,
            "size_bytes": save_info["size_bytes"],
            "storage_backend": save_info["storage_backend"],
            "compression_ratio": save_info["compression_ratio"],
            "success": success,
            "error_type": error_type,
            "error_message": error_message,
        }

    def record_checkpoint_load(
        self, workflow_id: str, checkpoint_id: str, storage_backend: str = "memory"
    ) -> str:
        """Record the start of a checkpoint load operation.

        Args:
            workflow_id: ID of the workflow being loaded
            checkpoint_id: ID of the checkpoint being loaded
            storage_backend: Storage backend being used

        Returns:
            Load operation ID for tracking
        """
        load_id = f"load-{workflow_id}-{int(time.time() * 1000)}"

        self._active_loads[load_id] = {
            "workflow_id": workflow_id,
            "checkpoint_id": checkpoint_id,
            "storage_backend": storage_backend,
            "start_time": time.time(),
        }

        return load_id

    def complete_checkpoint_load(
        self,
        load_id: str,
        success: bool = True,
        checkpoint_size_bytes: Optional[int] = None,
        error_type: Optional[str] = None,
        error_message: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Complete a checkpoint load operation.

        Args:
            load_id: ID of the load operation
            success: Whether the load was successful
            checkpoint_size_bytes: Size of loaded checkpoint in bytes
            error_type: Type of error if failed
            error_message: Error message if failed

        Returns:
            Load metrics
        """
        if load_id not in self._active_loads:
            return {"error": "Unknown load ID"}

        load_info = self._active_loads.pop(load_id)
        duration = time.time() - load_info["start_time"]

        if success:
            self._load_times.append(duration)
            self._total_loads += 1
        else:
            self._load_failures += 1
            if error_type:
                self._load_error_types.append(error_type)

        return {
            "load_id": load_id,
            "workflow_id": load_info["workflow_id"],
            "checkpoint_id": load_info["checkpoint_id"],
            "duration_ms": duration * 1000,
            "size_bytes": checkpoint_size_bytes,
            "storage_backend": load_info["storage_backend"],
            "success": success,
            "error_type": error_type,
            "error_message": error_message,
        }

    def get_failure_stats(self) -> Dict[str, Any]:
        """Get statistics about checkpoint failures.

        Returns:
            Dictionary with failure statistics
        """
        return {
            "save_failures": self._save_failures,
            "load_failures": self._load_failures,
            "save_error_types": self._save_error_types,
            "load_error_types": self._load_error_types,
            "total_failures": self._save_failures + self._load_failures,
        }

    def get_storage_stats(self) -> Dict[str, Any]:
        """Get statistics about checkpoint storage usage.

        Returns:
            Dictionary with storage statistics
        """
        if not self._checkpoint_sizes:
            return {
                "total_checkpoints": 0,
                "total_size_bytes": 0,
                "average_size_bytes": 0,
                "largest_checkpoint_bytes": 0,
                "smallest_checkpoint_bytes": 0,
            }

        sizes = list(self._checkpoint_sizes.values())
        total_size = sum(sizes)

        return {
            "total_checkpoints": len(self._checkpoint_sizes),
            "total_size_bytes": total_size,
            "average_size_bytes": total_size / len(sizes) if sizes else 0,
            "largest_checkpoint_bytes": max(sizes) if sizes else 0,
            "smallest_checkpoint_bytes": min(sizes) if sizes else 0,
        }

    def record_checkpoint_with_timestamp(
        self, workflow_id: str, checkpoint_size_bytes: int, timestamp: datetime = None
    ) -> str:
        """Record a checkpoint with a specific timestamp.

        Args:
            workflow_id: ID of the workflow
            checkpoint_size_bytes: Size of the checkpoint in bytes
            timestamp: Timestamp for the checkpoint (defaults to now)

        Returns:
            Checkpoint ID
        """
        if timestamp is None:
            timestamp = datetime.now()

        checkpoint_id = f"ckpt-{workflow_id}-{int(timestamp.timestamp() * 1000)}"
        self._checkpoint_timestamps[checkpoint_id] = timestamp
        self._checkpoint_sizes[checkpoint_id] = checkpoint_size_bytes

        return checkpoint_id

    def cleanup_old_checkpoints(self, retention_hours: int) -> Dict[str, Any]:
        """Clean up checkpoints older than the retention period.

        Args:
            retention_hours: Number of hours to retain checkpoints

        Returns:
            Cleanup metrics
        """
        if not self._checkpoint_timestamps:
            return {
                "removed_count": 0,
                "removed_size_bytes": 0,
                "retained_count": 0,
                "retained_size_bytes": 0,
            }

        cutoff_time = datetime.now() - timedelta(hours=retention_hours)
        removed_count = 0
        removed_size = 0
        retained_count = 0
        retained_size = 0

        checkpoints_to_remove = []
        for checkpoint_id, timestamp in self._checkpoint_timestamps.items():
            size = self._checkpoint_sizes.get(checkpoint_id, 0)
            if timestamp < cutoff_time:
                checkpoints_to_remove.append(checkpoint_id)
                removed_count += 1
                removed_size += size
            else:
                retained_count += 1
                retained_size += size

        # Remove old checkpoints
        for checkpoint_id in checkpoints_to_remove:
            del self._checkpoint_timestamps[checkpoint_id]
            if checkpoint_id in self._checkpoint_sizes:
                del self._checkpoint_sizes[checkpoint_id]

        return {
            "removed_count": removed_count,
            "freed_bytes": removed_size,
            "remaining_count": retained_count,
            "retained_size_bytes": retained_size,
        }


# Alias for backward compatibility
CheckpointMetrics = CheckpointMetricsTracker
