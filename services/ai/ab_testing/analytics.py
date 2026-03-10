"""
A/B Testing Analytics — Facade for analytics operations.
"""

import asyncio
from abc import ABC, abstractmethod
from typing import Any, Dict

from ..analytics_monitor import (
    analytics_monitor as _analytics_monitor,
)


class AnalyticsFacade(ABC):
    """Abstract facade for analytics operations."""

    @abstractmethod
    async def record_metric(
        self, metric_type: Any, name: str, value: float, metadata: Dict[str, Any]
    ) -> None:
        """Record a metric asynchronously."""
        pass


class DefaultAnalyticsFacade(AnalyticsFacade):
    """Default analytics facade using the global analytics monitor."""

    def __init__(self, monitor=None) -> None:
        self.monitor = monitor or _analytics_monitor

    async def record_metric(
        self, metric_type: Any, name: str, value: float, metadata: Dict[str, Any]
    ) -> None:
        if hasattr(self.monitor, "record_metric") and asyncio.iscoroutinefunction(
            self.monitor.record_metric
        ):
            await self.monitor.record_metric(metric_type, name, value, metadata)
