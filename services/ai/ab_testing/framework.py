"""
A/B Testing Framework — Core experiment management class.
"""

import asyncio
import hashlib
import threading
from collections import defaultdict
from datetime import datetime
from typing import Any, Dict, List, Optional, Union

from config.logging_config import get_logger

from ..analytics_monitor import MetricType as AnalyticsMetricType
from .analytics import AnalyticsFacade, DefaultAnalyticsFacade
from .models import (
    ExperimentConfig,
    ExperimentData,
    ExperimentNotFoundError,
    ExperimentStatus,
    InvalidExperimentConfig,
    StatisticalResult,
)
from .statistical_tests import (
    calculate_sample_size,
    execute_statistical_test,
    group_data_by_variant,
    select_statistical_test,
    validate_experiment_config,
    validate_metric_value,
)
from .storage import InMemoryStorageBackend, StorageBackend

logger = get_logger(__name__)


class ABTestingFramework:
    """Comprehensive A/B Testing Framework with rigorous statistical analysis."""

    def __init__(
        self,
        storage_backend: Optional[StorageBackend] = None,
        analytics_facade: Optional[AnalyticsFacade] = None,
    ) -> None:
        self.experiments: Dict[str, ExperimentConfig] = {}
        self.experiment_status: Dict[str, ExperimentStatus] = {}
        self.experiment_results: Dict[str, List[StatisticalResult]] = {}

        self.storage_backend = storage_backend or InMemoryStorageBackend()
        self.analytics_facade = analytics_facade or DefaultAnalyticsFacade()

        self.confidence_levels = [0.90, 0.95, 0.99]
        self.effect_size_thresholds = {"small": 0.2, "medium": 0.5, "large": 0.8}

    def _schedule_coro(self, coro: Any) -> None:
        """Schedule a coroutine safely, checking for active event loop."""
        try:
            asyncio.get_running_loop()
            asyncio.create_task(coro)
        except RuntimeError:
            def run_in_thread():
                try:
                    asyncio.run(coro)
                except Exception as e:
                    logger.debug(f"Failed to run analytics coroutine: {e}")

            thread = threading.Thread(target=run_in_thread, daemon=True)
            thread.start()

    def _validate_metric_value(
        self, value: Union[float, int, str, bool], metric_type: "ExperimentMetricType"
    ) -> Union[float, int, str, bool]:
        """Validate and coerce metric value. Delegates to statistical_tests module."""
        return validate_metric_value(value, metric_type)

    def create_experiment(self, config: ExperimentConfig) -> Dict[str, Any]:
        """Create a new A/B experiment."""
        from uuid import uuid4

        experiment_id = str(uuid4())

        validate_experiment_config(config)

        required_sample_size = calculate_sample_size(config)
        if config.min_sample_size < required_sample_size:
            logger.warning(
                f"Configured sample size ({config.min_sample_size}) is below "
                f"statistically required size ({required_sample_size})",
            )

        self.experiments[experiment_id] = config
        self.experiment_status[experiment_id] = ExperimentStatus.DRAFT
        self.experiment_results[experiment_id] = []

        logger.info(f"Created experiment {experiment_id}: {config.name}")

        self._schedule_coro(
            self.analytics_facade.record_metric(
                AnalyticsMetricType.ERROR,
                "experiment_created",
                1.0,
                {
                    "experiment_id": experiment_id,
                    "experiment_type": config.experiment_type.value,
                    "metric_type": config.metric_type.value,
                },
            )
        )

        return {"experiment_id": experiment_id, "recommended_sample_size": required_sample_size}

    def start_experiment(self, experiment_id: str) -> bool:
        """Start an experiment."""
        if experiment_id not in self.experiments:
            raise ExperimentNotFoundError(f"Experiment {experiment_id} not found")

        if self.experiment_status[experiment_id] != ExperimentStatus.DRAFT:
            raise InvalidExperimentConfig(f"Experiment {experiment_id} is not in draft status")

        self.experiment_status[experiment_id] = ExperimentStatus.RUNNING

        logger.info(f"Started experiment {experiment_id}")

        self._schedule_coro(
            self.analytics_facade.record_metric(
                AnalyticsMetricType.ERROR,
                "experiment_started",
                1.0,
                {"experiment_id": experiment_id},
            )
        )

        return True

    def assign_variant(
        self, experiment_id: str, user_id: str, context: Optional[Dict[str, Any]] = None
    ) -> str:
        """Assign a user to an experiment variant."""
        if experiment_id not in self.experiments:
            raise ExperimentNotFoundError(f"Experiment {experiment_id} not found")

        if self.experiment_status[experiment_id] != ExperimentStatus.RUNNING:
            logger.warning(f"Experiment {experiment_id} is not running")
            return "control"

        config = self.experiments[experiment_id]

        hash_input = f"{experiment_id}:{user_id}"

        if config.stratification_keys and context:
            strata_values = [str(context.get(key, "unknown")) for key in config.stratification_keys]
            hash_input += ":" + ":".join(strata_values)

        hash_value = int(hashlib.md5(hash_input.encode(), usedforsecurity=False).hexdigest(), 16)
        assignment_ratio = (hash_value % 10000) / 10000.0

        variant_keys = list(config.traffic_split.keys())
        if "control" in variant_keys and "treatment" in variant_keys:
            ordered_variants = ["control"] + [k for k in variant_keys if k != "control"]
        else:
            ordered_variants = sorted(variant_keys)
            logger.debug(f"Using deterministic variant ordering: {ordered_variants}")

        cumulative_probability = 0.0
        for variant in ordered_variants:
            probability = config.traffic_split[variant]
            cumulative_probability += probability
            if assignment_ratio <= cumulative_probability:
                return variant

        return ordered_variants[0] if ordered_variants else "control"

    def record_metric(
        self,
        experiment_id: str,
        variant: str,
        user_id: str,
        primary_metric_value: Union[float, int, str, bool],
        secondary_metrics: Optional[Dict[str, Union[float, int, str, bool]]] = None,
        context: Optional[Dict[str, Any]] = None,
    ) -> bool:
        """Record a metric observation for an experiment."""
        if experiment_id not in self.experiments:
            raise ExperimentNotFoundError(f"Experiment {experiment_id} not found")

        config = self.experiments[experiment_id]
        validated_value = validate_metric_value(primary_metric_value, config.metric_type)

        data_point = ExperimentData(
            experiment_id=experiment_id,
            variant=variant,
            user_id=user_id,
            session_id=context.get("session_id") if context else None,
            timestamp=datetime.now(),
            primary_metric_value=validated_value,
            secondary_metrics=secondary_metrics or {},
            user_segments=context.get("user_segments", {}) if context else {},
            metadata=context or {},
        )

        self.storage_backend.append(experiment_id, data_point)

        self._schedule_coro(
            self.analytics_facade.record_metric(
                AnalyticsMetricType.ERROR,
                "experiment_metric_recorded",
                1.0,
                {
                    "experiment_id": experiment_id,
                    "variant": variant,
                    "metric_value": str(validated_value),
                },
            )
        )

        return True

    def analyze_experiment(
        self, experiment_id: str, confidence_level: float = 0.95
    ) -> StatisticalResult:
        """Perform rigorous statistical analysis of an experiment."""
        if experiment_id not in self.experiments:
            raise ExperimentNotFoundError(f"Experiment {experiment_id} not found")

        config = self.experiments[experiment_id]
        data = self.storage_backend.query(experiment_id)

        if len(data) < config.min_sample_size:
            logger.warning(
                f"Insufficient data for analysis: {len(data)} < {config.min_sample_size}",
            )

        variant_data = group_data_by_variant(data)
        test_type = select_statistical_test(config.metric_type, variant_data)

        result = execute_statistical_test(
            test_type,
            variant_data,
            config,
            confidence_level,
        )

        self.experiment_results[experiment_id].append(result)

        self._schedule_coro(
            self.analytics_facade.record_metric(
                AnalyticsMetricType.ERROR,
                "experiment_analyzed",
                float(result.p_value),
                {
                    "experiment_id": experiment_id,
                    "test_type": result.test_name,
                    "is_significant": result.is_significant,
                    "effect_size": float(result.effect_size),
                },
            )
        )

        return result

    def get_experiment_summary(
        self,
        experiment_id: str,
        limit: Optional[int] = None,
        offset: int = 0,
        include_full_data: bool = False,
    ) -> Dict[str, Any]:
        """Get comprehensive summary of an experiment."""
        if experiment_id not in self.experiments:
            raise ExperimentNotFoundError(f"Experiment {experiment_id} not found")

        config = self.experiments[experiment_id]
        if include_full_data:
            data = self.storage_backend.query(experiment_id)
            if limit is not None:
                data = data[offset : offset + limit]
        else:
            data = []
            total_count = self.storage_backend.count(experiment_id)
        results = self.experiment_results[experiment_id]
        status = self.experiment_status[experiment_id]

        if include_full_data and data:
            variant_counts: Dict[str, int] = defaultdict(int)
            for data_point in data:
                variant_counts[data_point.variant] += 1

            start_time = min(d.timestamp for d in data) if data else None
            end_time = max(d.timestamp for d in data) if data else None
        else:
            variant_counts = {}
            start_time = None
            end_time = None

        summary = {
            "experiment_id": experiment_id,
            "config": {
                "name": config.name,
                "description": config.description,
                "type": config.experiment_type.value,
                "metric_type": config.metric_type.value,
                "primary_metric": config.primary_metric,
                "significance_level": config.significance_level,
                "power": config.power,
                "min_effect_size": config.min_effect_size,
                "traffic_split": config.traffic_split,
            },
            "status": status.value,
            "data_summary": {
                "total_observations": len(data) if include_full_data else total_count,
                "variant_counts": dict(variant_counts),
                "start_time": start_time,
                "end_time": end_time,
                "pagination": {
                    "offset": offset,
                    "limit": limit,
                    "include_full_data": include_full_data,
                    "returned": len(data) if include_full_data else 0,
                },
            },
            "results": [
                {
                    "test_name": r.test_name,
                    "p_value": r.p_value,
                    "effect_size": r.effect_size,
                    "is_significant": r.is_significant,
                    "practical_significance": r.practical_significance,
                    "recommendation": r.recommendation,
                    "power": r.power,
                    "timestamp": r.timestamp.isoformat(),
                }
                for r in results[-10:]
            ],
        }

        return summary
