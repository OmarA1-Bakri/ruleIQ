"""
Rigorous A/B Testing Framework with Statistical Analysis

Implements statistical hypothesis testing for AI model comparisons,
feature experiments, and compliance effectiveness measurements.
Includes t-tests, chi-squared tests, and comprehensive experiment management.
"""

import hashlib
import asyncio
import threading
import numpy as np
from abc import ABC, abstractmethod
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional, Tuple, Union
from uuid import uuid4
from scipy import stats
from scipy.stats import ttest_ind, chi2_contingency, mannwhitneyu

from config.logging_config import get_logger
from .analytics_monitor import (
    MetricType as AnalyticsMetricType,
    analytics_monitor as _analytics_monitor,
)

logger = get_logger(__name__)


# Comment 10: Custom exception classes
class ExperimentNotFoundError(Exception):
    """Raised when an experiment is not found."""

    pass


class InvalidExperimentConfig(Exception):
    """Raised when experiment configuration is invalid."""

    pass


class ExperimentType(Enum):
    """Types of A/B experiments."""

    AI_MODEL_COMPARISON = "ai_model_comparison"
    PROMPT_OPTIMIZATION = "prompt_optimization"
    FEATURE_ROLLOUT = "feature_rollout"
    UI_OPTIMIZATION = "ui_optimization"
    COMPLIANCE_EFFECTIVENESS = "compliance_effectiveness"
    ASSESSMENT_METHODOLOGY = "assessment_methodology"

    # MetricType imported from analytics_monitor above


#     CATEGORICAL = "categorical"  # User preferences, status categories  # Unused variable
#     COUNT = "count"  # Number of actions, events  # Unused variable


class StatisticalTest(Enum):
    """Available statistical tests."""

    T_TEST = "t_test"  # Two-sample t-test for continuous metrics
    WELCH_T_TEST = "welch_t_test"  # Welch's t-test (unequal variances)
    CHI_SQUARED = "chi_squared"  # Chi-squared test for categorical data
    MANN_WHITNEY = "mann_whitney"  # Non-parametric alternative to t-test
    KOLMOGOROV_SMIRNOV = "ks_test"  # Distribution comparison
    FISHER_EXACT = "fisher_exact"  # Exact test for small samples


class ExperimentStatus(Enum):
    """Experiment lifecycle status."""

    DRAFT = "draft"
    RUNNING = "running"
    PAUSED = "paused"
    COMPLETED = "completed"
    CANCELLED = "cancelled"
    ARCHIVED = "archived"


# Comment 6: Renamed to ExperimentMetricType to avoid collision
class ExperimentMetricType(Enum):
    """Metric types specific to the AB testing framework.

    This is distinct from AnalyticsMetricType and specific to experiment metrics.
    """

    CONTINUOUS = "continuous"
    BINARY = "binary"
    CATEGORICAL = "categorical"
    COUNT = "count"


@dataclass
class ExperimentConfig:
    """Configuration for an A/B experiment."""

    name: str
    description: str
    experiment_type: ExperimentType
    metric_type: ExperimentMetricType
    primary_metric: str
    secondary_metrics: List[str] = field(default_factory=list)

    # Statistical parameters
    significance_level: float = 0.05  # Alpha (Type I error rate)
    power: float = 0.8  # 1 - Beta (Type II error rate)
    min_effect_size: float = 0.1  # Minimum detectable effect

    # Experiment design
    traffic_split: Dict[str, float] = field(
        default_factory=lambda: {"control": 0.5, "treatment": 0.5},
    )
    stratification_keys: List[str] = field(default_factory=list)  # User segments, regions, etc.

    # Duration and sample size
    min_sample_size: int = 100
    max_duration_days: int = 30
    early_stopping_enabled: bool = True

    # Metadata
    owner: str = "system"
    tags: List[str] = field(default_factory=list)


@dataclass
class StatisticalResult:
    """Results of statistical test analysis."""

    test_name: str
    statistic: float
    p_value: float
    confidence_interval: Optional[Tuple[float, float]]
    effect_size: float
    power: float

    # Interpretation
    is_significant: bool
    practical_significance: bool
    recommendation: str

    # Additional metrics
    sample_sizes: Dict[str, int]
    means: Dict[str, float]
    std_devs: Dict[str, float]

    # Metadata
    timestamp: datetime = field(default_factory=datetime.now)
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class ExperimentData:
    """Data point in an A/B experiment."""

    experiment_id: str
    variant: str  # "control", "treatment", "variant_a", etc.
    user_id: str
    session_id: Optional[str]
    timestamp: datetime

    # Metric values
    primary_metric_value: Union[float, int, str, bool]
    secondary_metrics: Dict[str, Union[float, int, str, bool]] = field(
        default_factory=dict,
    )

    # Context
    user_segments: Dict[str, str] = field(default_factory=dict)
    metadata: Dict[str, Any] = field(default_factory=dict)


# Comment 3: Storage backend interface
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
        # For in-memory, we return all data (filtering can be added if needed)
        return self.data[experiment_id]

    def count(self, experiment_id: str) -> int:
        return len(self.data.get(experiment_id, []))


# Comment 14: Analytics facade for dependency injection
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


class ABTestingFramework:
    """Comprehensive A/B Testing Framework with rigorous statistical analysis."""

    def __init__(
        self,
        storage_backend: Optional[StorageBackend] = None,
        analytics_facade: Optional[AnalyticsFacade] = None,
    ) -> None:
        """Initialize the A/B testing framework.

        Args:
            storage_backend: Backend for storing experiment data. Defaults to in-memory (testing only).
            analytics_facade: Facade for analytics operations. Defaults to global monitor wrapper.
        """
        self.experiments: Dict[str, ExperimentConfig] = {}
        self.experiment_status: Dict[str, ExperimentStatus] = {}
        self.experiment_results: Dict[str, List[StatisticalResult]] = {}

        # Comment 3: Use injected storage backend
        self.storage_backend = storage_backend or InMemoryStorageBackend()

        # Comment 14: Use injected analytics facade
        self.analytics_facade = analytics_facade or DefaultAnalyticsFacade()

        # Statistical configuration
        self.confidence_levels = [0.90, 0.95, 0.99]
        self.effect_size_thresholds = {"small": 0.2, "medium": 0.5, "large": 0.8}

    # Comment 2: Helper function for safe async task scheduling
    def _schedule_coro(self, coro: Any) -> None:
        """Schedule a coroutine safely, checking for active event loop.

        Args:
            coro: Coroutine to schedule
        """
        try:
            asyncio.get_running_loop()
            asyncio.create_task(coro)
        except RuntimeError:
            # No running event loop, run in background thread
            def run_in_thread():
                try:
                    asyncio.run(coro)
                except Exception as e:
                    logger.debug(f"Failed to run analytics coroutine: {e}")

            thread = threading.Thread(target=run_in_thread, daemon=True)
            thread.start()

    def _validate_metric_value(
        self, value: Union[float, int, str, bool], metric_type: ExperimentMetricType
    ) -> Union[float, int, str, bool]:
        """Validate and coerce metric value to match expected type.

        Args:
            value: The metric value to validate
            metric_type: Expected metric type

        Returns:
            Validated and possibly coerced value

        Raises:
            InvalidExperimentConfig: If value cannot be coerced to expected type
        """
        if metric_type == ExperimentMetricType.CONTINUOUS:
            try:
                return float(value)
            except (TypeError, ValueError):
                raise InvalidExperimentConfig(
                    f"Cannot convert value '{value}' to float for CONTINUOUS metric"
                )
        elif metric_type == ExperimentMetricType.BINARY:
            if isinstance(value, bool):
                return value
            if isinstance(value, (int, float)):
                return bool(value)
            if isinstance(value, str):
                return value.lower() in ("true", "1", "yes")
            raise InvalidExperimentConfig(
                f"Cannot convert value '{value}' to bool for BINARY metric"
            )
        elif metric_type == ExperimentMetricType.COUNT:
            try:
                return int(value)
            except (TypeError, ValueError):
                raise InvalidExperimentConfig(
                    f"Cannot convert value '{value}' to int for COUNT metric"
                )
        elif metric_type == ExperimentMetricType.CATEGORICAL:
            return str(value)
        else:
            return value

    def create_experiment(self, config: ExperimentConfig) -> Dict[str, Any]:
        """
        Create a new A/B experiment.

        Args:
            config: Experiment configuration

        Returns:
            Dict containing experiment_id and recommended_sample_size
        """
        experiment_id = str(uuid4())

        # Validate configuration
        self._validate_experiment_config(config)

        # Calculate required sample size
        required_sample_size = self._calculate_sample_size(config)
        if config.min_sample_size < required_sample_size:
            logger.warning(
                f"Configured sample size ({config.min_sample_size}) is below "
                f"statistically required size ({required_sample_size})",
            )

        # Store experiment
        self.experiments[experiment_id] = config
        self.experiment_status[experiment_id] = ExperimentStatus.DRAFT
        self.experiment_results[experiment_id] = []

        logger.info(f"Created experiment {experiment_id}: {config.name}")

        # Comment 2: Use safe coroutine scheduling
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

        # Comment 12: Return experiment ID and recommended sample size
        return {"experiment_id": experiment_id, "recommended_sample_size": required_sample_size}

    def start_experiment(self, experiment_id: str) -> bool:
        """
        Start an experiment.

        Args:
            experiment_id: ID of experiment to start

        Returns:
            True if started successfully
        """
        # Comment 10: Use custom exceptions
        if experiment_id not in self.experiments:
            raise ExperimentNotFoundError(f"Experiment {experiment_id} not found")

        if self.experiment_status[experiment_id] != ExperimentStatus.DRAFT:
            raise InvalidExperimentConfig(f"Experiment {experiment_id} is not in draft status")

        self.experiment_status[experiment_id] = ExperimentStatus.RUNNING

        logger.info(f"Started experiment {experiment_id}")

        # Comment 2: Use safe coroutine scheduling
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
        """
        Assign a user to an experiment variant.

        Args:
            experiment_id: ID of the experiment
            user_id: User identifier
            context: Additional context for stratification

        Returns:
            Assigned variant name
        """
        # Comment 10: Use custom exceptions
        if experiment_id not in self.experiments:
            raise ExperimentNotFoundError(f"Experiment {experiment_id} not found")

        if self.experiment_status[experiment_id] != ExperimentStatus.RUNNING:
            logger.warning(f"Experiment {experiment_id} is not running")
            return "control"  # Default to control if experiment not running

        config = self.experiments[experiment_id]

        # Deterministic assignment based on user ID and experiment ID
        hash_input = f"{experiment_id}:{user_id}"

        # Add stratification if configured
        if config.stratification_keys and context:
            strata_values = [str(context.get(key, "unknown")) for key in config.stratification_keys]
            hash_input += ":" + ":".join(strata_values)

        # Generate hash and convert to assignment
        hash_value = int(hashlib.md5(hash_input.encode(), usedforsecurity=False).hexdigest(), 16)
        assignment_ratio = (hash_value % 10000) / 10000.0

        # Comment 4: Explicit variant mapping with deterministic ordering
        # First check for standard keys, then fall back to sorted order
        variant_keys = list(config.traffic_split.keys())
        if "control" in variant_keys and "treatment" in variant_keys:
            # Use explicit control/treatment ordering
            ordered_variants = ["control"] + [k for k in variant_keys if k != "control"]
        else:
            # Deterministic ordering by sorting keys
            ordered_variants = sorted(variant_keys)
            logger.debug(f"Using deterministic variant ordering: {ordered_variants}")

        # Assign to variant based on traffic split
        cumulative_probability = 0.0
        for variant in ordered_variants:
            probability = config.traffic_split[variant]
            cumulative_probability += probability
            if assignment_ratio <= cumulative_probability:
                return variant

        # Fallback to first variant (typically control)
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
        """
        Record a metric observation for an experiment.

        Args:
            experiment_id: ID of the experiment
            variant: Variant the user was assigned to
            user_id: User identifier
            primary_metric_value: Value of the primary metric
            secondary_metrics: Values of secondary metrics
            context: Additional context information

        Returns:
            True if recorded successfully
        """
        # Comment 10: Use custom exceptions
        if experiment_id not in self.experiments:
            raise ExperimentNotFoundError(f"Experiment {experiment_id} not found")

        # Comment 7: Validate primary_metric_value against metric_type
        config = self.experiments[experiment_id]
        validated_value = self._validate_metric_value(primary_metric_value, config.metric_type)

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

        # Comment 3: Use storage backend
        self.storage_backend.append(experiment_id, data_point)

        # Comment 2: Use safe coroutine scheduling
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
        """
        Perform rigorous statistical analysis of an experiment.

        Args:
            experiment_id: ID of the experiment to analyze
            confidence_level: Confidence level for statistical tests

        Returns:
            Statistical analysis results
        """
        # Comment 10: Use custom exceptions
        if experiment_id not in self.experiments:
            raise ExperimentNotFoundError(f"Experiment {experiment_id} not found")

        config = self.experiments[experiment_id]
        # Comment 3: Use storage backend
        data = self.storage_backend.query(experiment_id)

        if len(data) < config.min_sample_size:
            logger.warning(
                f"Insufficient data for analysis: {len(data)} < {config.min_sample_size}",
            )

        # Group data by variant
        variant_data = self._group_data_by_variant(data)

        # Choose appropriate statistical test
        test_type = self._select_statistical_test(config.metric_type, variant_data)

        # Perform statistical analysis
        result = self._perform_statistical_test(
            test_type,
            variant_data,
            config,
            confidence_level,
        )

        # Store result
        self.experiment_results[experiment_id].append(result)

        # Comment 2: Use safe coroutine scheduling
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

    def _validate_experiment_config(self, config: ExperimentConfig) -> None:
        """Validate experiment configuration."""
        if config.significance_level <= 0 or config.significance_level >= 1:
            raise ValueError("Significance level must be between 0 and 1")

        if config.power <= 0 or config.power >= 1:
            raise ValueError("Power must be between 0 and 1")

        if abs(sum(config.traffic_split.values()) - 1.0) > 1e-6:
            raise ValueError("Traffic split probabilities must sum to 1.0")

        if config.min_sample_size < 10:
            raise ValueError("Minimum sample size should be at least 10")

    def _calculate_sample_size(self, config: ExperimentConfig) -> int:
        """
        Calculate required sample size for adequate statistical power.

        Args:
            config: Experiment configuration

        Returns:
            Required sample size per variant
        """
        alpha = config.significance_level
        beta = 1 - config.power
        effect_size = config.min_effect_size

        # Using Cohen's formula for two-sample t-test
        z_alpha = stats.norm.ppf(1 - alpha / 2)
        z_beta = stats.norm.ppf(1 - beta)

        # Sample size per group
        n = 2 * ((z_alpha + z_beta) / effect_size) ** 2

        return max(int(np.ceil(n)), config.min_sample_size)

    def _group_data_by_variant(
        self, data: List[ExperimentData]
    ) -> Dict[str, List[Union[float, int, str, bool]]]:
        """Group experiment data by variant."""
        variant_data = defaultdict(list)

        for data_point in data:
            variant_data[data_point.variant].append(data_point.primary_metric_value)

        return dict(variant_data)

    def _select_statistical_test(
        self, metric_type: ExperimentMetricType, variant_data: Dict[str, List]
    ) -> StatisticalTest:
        """
        Select appropriate statistical test based on data characteristics.

        Args:
            metric_type: Type of metric being analyzed
            variant_data: Data grouped by variant

        Returns:
            Recommended statistical test
        """
        if metric_type == ExperimentMetricType.CONTINUOUS:
            # Check for normality and equal variances
            variants = list(variant_data.keys())
            if len(variants) == 2:
                control_data = np.array(variant_data[variants[0]], dtype=float)
                treatment_data = np.array(variant_data[variants[1]], dtype=float)

                # Test for normality (Shapiro-Wilk for small samples, KS for large)
                if len(control_data) < 50 or len(treatment_data) < 50:
                    _, p_control = stats.shapiro(control_data)
                    _, p_treatment = stats.shapiro(treatment_data)
                else:
                    _, p_control = stats.kstest(control_data, "norm")
                    _, p_treatment = stats.kstest(treatment_data, "norm")

                # If data is not normal, use non-parametric test
                if p_control < 0.05 or p_treatment < 0.05:
                    return StatisticalTest.MANN_WHITNEY

                # Comment 9: Check for zero variance before testing
                control_var = np.var(control_data)
                treatment_var = np.var(treatment_data)

                if control_var == 0 or treatment_var == 0:
                    logger.info(
                        "Zero variance detected in one or both groups, using non-parametric test"
                    )
                    return StatisticalTest.MANN_WHITNEY

                # Test for equal variances
                _, p_var = stats.levene(control_data, treatment_data)

                if p_var < 0.05:
                    return StatisticalTest.WELCH_T_TEST  # Unequal variances
                else:
                    return StatisticalTest.T_TEST  # Equal variances

            return StatisticalTest.T_TEST

        elif metric_type in (ExperimentMetricType.BINARY, ExperimentMetricType.CATEGORICAL):
            # Use chi-squared for categorical data
            return StatisticalTest.CHI_SQUARED

        elif metric_type == ExperimentMetricType.COUNT:
            # Use Mann-Whitney U for count data (often not normally distributed)
            return StatisticalTest.MANN_WHITNEY

        return StatisticalTest.T_TEST  # Default

    # Comment 8: Split into smaller helper methods
    def _prepare_data_for_test(
        self, variant_data: Dict[str, List], test_type: StatisticalTest
    ) -> Tuple:
        """Prepare data for statistical testing based on test type.

        Args:
            variant_data: Data grouped by variant
            test_type: Type of test to prepare for

        Returns:
            Tuple of prepared data arrays
        """
        variants = list(variant_data.keys())

        # Comment 1: Delay conversion to float until we know the test type
        if test_type == StatisticalTest.CHI_SQUARED:
            # Keep raw data for categorical tests
            return variants, variant_data[variants[0]], variant_data[variants[1]]
        else:
            # Convert to float for numeric tests
            try:
                control_data = np.array(variant_data[variants[0]], dtype=float)
                treatment_data = np.array(variant_data[variants[1]], dtype=float)
            except (TypeError, ValueError) as e:
                raise InvalidExperimentConfig(
                    f"Failed to convert data to numeric format for {test_type.value}: {e}"
                )
            return variants, control_data, treatment_data

    def _calculate_effect_size(
        self,
        metric_type: ExperimentMetricType,
        control_data: Any,
        treatment_data: Any,
        test_type: StatisticalTest,
    ) -> float:
        """Calculate effect size based on metric type.

        Comment 5: Compute effect size conditionally based on metric type.

        Args:
            metric_type: Type of metric
            control_data: Control group data
            treatment_data: Treatment group data
            test_type: Statistical test being performed

        Returns:
            Effect size measure appropriate for the metric type
        """
        if metric_type == ExperimentMetricType.CONTINUOUS:
            # Cohen's d for continuous metrics
            control_mean = np.mean(control_data)
            treatment_mean = np.mean(treatment_data)
            control_std = np.std(control_data, ddof=1)
            treatment_std = np.std(treatment_data, ddof=1)

            pooled_std = np.sqrt((control_std**2 + treatment_std**2) / 2)
            if pooled_std == 0:
                return 0.0
            return (treatment_mean - control_mean) / pooled_std

        elif metric_type == ExperimentMetricType.BINARY:
            # Difference in proportions or odds ratio for binary metrics
            control_prop = np.mean(control_data)
            treatment_prop = np.mean(treatment_data)
            return treatment_prop - control_prop  # Simple difference in proportions

        elif metric_type == ExperimentMetricType.CATEGORICAL:
            # Cramér's V from chi-squared test
            if test_type == StatisticalTest.CHI_SQUARED:
                control_counts = self._get_category_counts(control_data)
                treatment_counts = self._get_category_counts(treatment_data)

                # Create contingency table
                all_categories = set(control_counts.keys()) | set(treatment_counts.keys())
                contingency_table = []
                for category in all_categories:
                    contingency_table.append(
                        [control_counts.get(category, 0), treatment_counts.get(category, 0)]
                    )

                chi2, _, _, _ = chi2_contingency(contingency_table)
                n = len(control_data) + len(treatment_data)
                k = min(2, len(all_categories))  # min of rows, cols
                cramers_v = np.sqrt(chi2 / (n * (k - 1)))
                return cramers_v
            return 0.0

        elif metric_type == ExperimentMetricType.COUNT:
            # Use standardized mean difference for count data
            control_mean = np.mean(control_data)
            treatment_mean = np.mean(treatment_data)
            control_std = np.std(control_data, ddof=1)
            treatment_std = np.std(treatment_data, ddof=1)

            pooled_std = np.sqrt((control_std**2 + treatment_std**2) / 2)
            if pooled_std == 0:
                return 0.0
            return (treatment_mean - control_mean) / pooled_std

        return 0.0

    def _run_t_test(
        self, control_data: np.ndarray, treatment_data: np.ndarray
    ) -> Tuple[float, float, str]:
        """Run two-sample t-test."""
        statistic, p_value = ttest_ind(control_data, treatment_data, equal_var=True)
        return statistic, p_value, "Two-sample t-test (equal variances)"

    def _run_welch(
        self, control_data: np.ndarray, treatment_data: np.ndarray
    ) -> Tuple[float, float, str]:
        """Run Welch's t-test."""
        statistic, p_value = ttest_ind(control_data, treatment_data, equal_var=False)
        return statistic, p_value, "Welch's t-test (unequal variances)"

    def _run_mann_whitney(
        self, control_data: np.ndarray, treatment_data: np.ndarray
    ) -> Tuple[float, float, str]:
        """Run Mann-Whitney U test."""
        statistic, p_value = mannwhitneyu(control_data, treatment_data, alternative="two-sided")
        return statistic, p_value, "Mann-Whitney U test"

    def _run_chi_squared(
        self, control_data: List, treatment_data: List
    ) -> Tuple[float, float, str]:
        """Run chi-squared test."""
        control_counts = self._get_category_counts(control_data)
        treatment_counts = self._get_category_counts(treatment_data)

        # Align categories
        all_categories = set(control_counts.keys()) | set(treatment_counts.keys())
        contingency_table = []
        for category in all_categories:
            contingency_table.append(
                [control_counts.get(category, 0), treatment_counts.get(category, 0)]
            )

        chi2, p_value, _, _ = chi2_contingency(contingency_table)
        return chi2, p_value, "Chi-squared test"

    def _compute_confidence_interval(
        self,
        test_type: StatisticalTest,
        control_data: np.ndarray,
        treatment_data: np.ndarray,
        alpha: float,
    ) -> Optional[Tuple[float, float]]:
        """Compute confidence interval for the test.

        Comment 11: Add numeric stability checks for Welch df calculation.
        """
        if test_type not in [StatisticalTest.T_TEST, StatisticalTest.WELCH_T_TEST]:
            return None

        control_mean = np.mean(control_data)
        treatment_mean = np.mean(treatment_data)
        control_std = np.std(control_data, ddof=1)
        treatment_std = np.std(treatment_data, ddof=1)

        mean_diff = treatment_mean - control_mean
        pooled_se = np.sqrt(
            control_std**2 / len(control_data) + treatment_std**2 / len(treatment_data)
        )

        if test_type == StatisticalTest.T_TEST:
            df = len(control_data) + len(treatment_data) - 2
        else:  # Welch's t-test
            # Comment 11: Check for numeric stability
            numerator = (
                control_std**2 / len(control_data) + treatment_std**2 / len(treatment_data)
            ) ** 2
            denominator = control_std**4 / (
                len(control_data) ** 2 * (len(control_data) - 1)
            ) + treatment_std**4 / (len(treatment_data) ** 2 * (len(treatment_data) - 1))

            if denominator == 0 or not np.isfinite(numerator / denominator):
                logger.warning("Welch df calculation unstable, using conservative df")
                df = min(len(control_data) - 1, len(treatment_data) - 1)
            else:
                df = numerator / denominator
                if df <= 0 or not np.isfinite(df):
                    logger.warning("Invalid df calculated, using conservative estimate")
                    df = min(len(control_data) - 1, len(treatment_data) - 1)

        t_critical = stats.t.ppf(1 - alpha / 2, df)
        margin_error = t_critical * pooled_se
        return (mean_diff - margin_error, mean_diff + margin_error)

    def _execute_statistical_test(
        self,
        test_type: StatisticalTest,
        variant_data: Dict[str, List],
        config: ExperimentConfig,
        confidence_level: float,
    ) -> StatisticalResult:
        """Orchestrate statistical test execution using helper methods.

        Comment 8: Refactored into smaller, focused helper methods.

        Args:
            test_type: Type of statistical test to perform
            variant_data: Data grouped by variant
            config: Experiment configuration
            confidence_level: Confidence level for the test

        Returns:
            Statistical test results
        """
        alpha = 1 - confidence_level
        variants = list(variant_data.keys())

        if len(variants) != 2:
            raise ValueError("Currently only supports two-variant experiments")

        # Prepare data based on test type
        variants, control_data, treatment_data = self._prepare_data_for_test(
            variant_data, test_type
        )

        # Run appropriate statistical test
        if test_type == StatisticalTest.T_TEST:
            statistic, p_value, test_name = self._run_t_test(control_data, treatment_data)
        elif test_type == StatisticalTest.WELCH_T_TEST:
            statistic, p_value, test_name = self._run_welch(control_data, treatment_data)
        elif test_type == StatisticalTest.MANN_WHITNEY:
            statistic, p_value, test_name = self._run_mann_whitney(control_data, treatment_data)
        elif test_type == StatisticalTest.CHI_SQUARED:
            statistic, p_value, test_name = self._run_chi_squared(control_data, treatment_data)
        else:
            raise ValueError(f"Unsupported test type: {test_type}")

        # Calculate effect size based on metric type
        effect_size = self._calculate_effect_size(
            config.metric_type, control_data, treatment_data, test_type
        )

        # Compute confidence interval if applicable
        confidence_interval = self._compute_confidence_interval(
            test_type, control_data, treatment_data, alpha
        )

        # Calculate statistical power
        if test_type != StatisticalTest.CHI_SQUARED:
            observed_effect_size = abs(effect_size)
            power = self._calculate_power(
                observed_effect_size, len(control_data), len(treatment_data), alpha
            )
        else:
            power = 0.8  # Default for categorical tests

        # Determine significance
        is_significant = p_value < alpha
        practical_significance = abs(effect_size) >= config.min_effect_size

        # Generate recommendation
        recommendation = self._generate_recommendation(
            is_significant, practical_significance, effect_size, p_value, power
        )

        # Calculate means and std devs for numeric data
        if test_type != StatisticalTest.CHI_SQUARED:
            control_mean = np.mean(control_data)
            treatment_mean = np.mean(treatment_data)
            control_std = np.std(control_data, ddof=1)
            treatment_std = np.std(treatment_data, ddof=1)
        else:
            # For categorical data, use mode as "mean" and 0 for std
            control_mean = 0.0
            treatment_mean = 0.0
            control_std = 0.0
            treatment_std = 0.0

        return StatisticalResult(
            test_name=test_name,
            statistic=statistic,
            p_value=p_value,
            confidence_interval=confidence_interval,
            effect_size=effect_size,
            power=power,
            is_significant=is_significant,
            practical_significance=practical_significance,
            recommendation=recommendation,
            sample_sizes={
                variants[0]: len(control_data),
                variants[1]: len(treatment_data),
            },
            means={variants[0]: control_mean, variants[1]: treatment_mean},
            std_devs={variants[0]: control_std, variants[1]: treatment_std},
            metadata={
                "confidence_level": confidence_level,
                "alpha": alpha,
                "test_type": test_type.value,
            },
        )

    def _get_category_counts(self, data: List) -> Dict[str, int]:
        """Get counts for each category in categorical data."""
        counts = defaultdict(int)
        for value in data:
            counts[str(value)] += 1
        return dict(counts)

    def _calculate_power(self, effect_size: float, n1: int, n2: int, alpha: float) -> float:
        """
        Calculate statistical power for the test.

        Args:
            effect_size: Observed effect size
            n1: Sample size for group 1
            n2: Sample size for group 2
            alpha: Significance level

        Returns:
            Statistical power (1 - beta)
        """
        # For two-sample t-test
        pooled_n = 2 / (1 / n1 + 1 / n2)
        ncp = effect_size * np.sqrt(pooled_n / 2)  # Non-centrality parameter

        t_critical = stats.t.ppf(1 - alpha / 2, n1 + n2 - 2)

        # Power calculation using non-central t-distribution
        power = (
            1
            - stats.nct.cdf(t_critical, n1 + n2 - 2, ncp)
            + stats.nct.cdf(-t_critical, n1 + n2 - 2, ncp),
        )

        return max(0.0, min(1.0, power))

    def _generate_recommendation(
        self,
        is_significant: bool,
        practical_significance: bool,
        effect_size: float,
        p_value: float,
        power: float,
    ) -> str:
        """Generate actionable recommendation based on statistical results."""
        if is_significant and practical_significance:
            if effect_size > 0:
                return (
                    f"IMPLEMENT: Treatment shows significant improvement "
                    f"(p={p_value:.4f}, effect size={effect_size:.3f})"
                )
            else:
                return (
                    f"REJECT: Treatment shows significant degradation "
                    f"(p={p_value:.4f}, effect size={effect_size:.3f})"
                )

        elif is_significant and not practical_significance:
            return f"INCONCLUSIVE: Statistically significant but effect too small (effect size={effect_size:.3f})"

        elif not is_significant and power < 0.8:
            return f"INSUFFICIENT DATA: Low power ({power:.2f}). Collect more data or increase effect size."

        elif not is_significant and power >= 0.8:
            return (
                f"NO EFFECT: Well-powered test shows no significant difference (power={power:.2f})"
            )

        else:
            return f"CONTINUE MONITORING: p={p_value:.4f}, effect size={effect_size:.3f}, power={power:.2f}"

    def get_experiment_summary(
        self,
        experiment_id: str,
        limit: Optional[int] = None,
        offset: int = 0,
        include_full_data: bool = False,
    ) -> Dict[str, Any]:
        """
        Get comprehensive summary of an experiment.

        Comment 13: Support pagination and limiting data for large datasets.

        Args:
            experiment_id: ID of the experiment
            limit: Maximum number of data points to include (None for all)
            offset: Offset for pagination
            include_full_data: If False, only include essential metadata and high-level results

        Returns:
            Experiment summary including config, data, and results
        """
        # Comment 10: Use custom exceptions
        if experiment_id not in self.experiments:
            raise ExperimentNotFoundError(f"Experiment {experiment_id} not found")

        config = self.experiments[experiment_id]
        # Comment 3 & 13: Use storage backend with pagination
        if include_full_data:
            data = self.storage_backend.query(experiment_id)
            if limit is not None:
                data = data[offset : offset + limit]
        else:
            # Only get count for metadata
            data = []  # Don't load full data
            total_count = self.storage_backend.count(experiment_id)
        results = self.experiment_results[experiment_id]
        status = self.experiment_status[experiment_id]

        # Calculate summary statistics efficiently
        if include_full_data and data:
            variant_counts = defaultdict(int)
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
                for r in results[-10:]  # Only include last 10 results for efficiency
            ],
        }

        return summary


# Global instance
_ab_testing_framework: Optional[ABTestingFramework] = None


def get_ab_testing_framework() -> ABTestingFramework:
    """Get global A/B testing framework instance."""
    global _ab_testing_framework
    if _ab_testing_framework is None:
        _ab_testing_framework = ABTestingFramework()
    return _ab_testing_framework


def create_ai_model_experiment(
    model_a: str,
    model_b: str,
    metric: str = "response_quality",
    min_effect_size: float = 0.1,
) -> Dict[str, Any]:
    """
    Create an A/B experiment for comparing AI models.

    Args:
        model_a: Name of control model
        model_b: Name of treatment model
        metric: Primary metric to compare
        min_effect_size: Minimum detectable effect size

    Returns:
        Experiment ID
    """
    framework = get_ab_testing_framework()

    config = ExperimentConfig(
        name=f"AI Model Comparison: {model_a} vs {model_b}",
        description=f"Compare performance of {model_a} (control) against {model_b} (treatment)",
        experiment_type=ExperimentType.AI_MODEL_COMPARISON,
        metric_type=ExperimentMetricType.CONTINUOUS,
        primary_metric=metric,
        secondary_metrics=["response_time", "cost_per_request"],
        min_effect_size=min_effect_size,
        traffic_split={"control": 0.5, "treatment": 0.5},
        min_sample_size=200,
        tags=["ai_model", "performance", model_a, model_b],
    )

    return framework.create_experiment(config)


def create_prompt_optimization_experiment(
    original_prompt: str, optimized_prompt: str, metric: str = "task_completion_rate"
) -> Dict[str, Any]:
    """
    Create an A/B experiment for prompt optimization.

    Args:
        original_prompt: Original prompt (control)
        optimized_prompt: Optimized prompt (treatment)
        metric: Primary metric to compare

    Returns:
        Experiment ID
    """
    framework = get_ab_testing_framework()

    config = ExperimentConfig(
        name="Prompt Optimization Experiment",
        description="Compare effectiveness of original vs optimized prompt",
        experiment_type=ExperimentType.PROMPT_OPTIMIZATION,
        metric_type=ExperimentMetricType.BINARY,
        primary_metric=metric,
        secondary_metrics=["user_satisfaction", "response_relevance"],
        min_effect_size=0.05,  # 5% improvement in completion rate
        traffic_split={"control": 0.5, "treatment": 0.5},
        min_sample_size=500,
        tags=["prompt", "optimization", "completion_rate"],
    )

    return framework.create_experiment(config)
