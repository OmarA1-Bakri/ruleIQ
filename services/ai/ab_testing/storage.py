"""
A/B Testing Storage — Abstract backend and in-memory implementation.
"""

from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional

from .models import ExperimentData


class StorageBackend(ABC):
    """Abstract base class for experiment data storage."""

    @abstractmethod
    def append(self, experiment_id: str, data: ExperimentData) -> None:
        """Append data to an experiment."""
        pass

    @abstractmethod
    def query(
        self, experiment_id: str, filters: Optional[Dict[str, Any]] = None
    ) -> List[ExperimentData]:
        """Query experiment data."""
        pass

    @abstractmethod
    def count(self, experiment_id: str) -> int:
        """Count data points for an experiment."""
        pass


class InMemoryStorageBackend(StorageBackend):
    """In-memory storage backend for testing only.

    WARNING: This backend stores all data in memory and is NOT suitable for production use.
    For production, use persistent backends such as SQL databases or cloud storage (Parquet/S3).
    """

    def __init__(self) -> None:
        self.data: Dict[str, List[ExperimentData]] = {}

    def append(self, experiment_id: str, data: ExperimentData) -> None:
        if experiment_id not in self.data:
            self.data[experiment_id] = []
        self.data[experiment_id].append(data)

    def query(
        self, experiment_id: str, filters: Optional[Dict[str, Any]] = None
    ) -> List[ExperimentData]:
        if experiment_id not in self.data:
            return []
        return self.data[experiment_id]

    def count(self, experiment_id: str) -> int:
        return len(self.data.get(experiment_id, []))
