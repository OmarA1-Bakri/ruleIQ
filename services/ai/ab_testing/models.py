"""
A/B Testing Models — Enums, dataclasses, and custom exceptions.
"""

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional, Tuple, Union


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


class StatisticalTest(Enum):
    """Available statistical tests."""

    T_TEST = "t_test"
    WELCH_T_TEST = "welch_t_test"
    CHI_SQUARED = "chi_squared"
    MANN_WHITNEY = "mann_whitney"
    KOLMOGOROV_SMIRNOV = "ks_test"
    FISHER_EXACT = "fisher_exact"


class ExperimentStatus(Enum):
    """Experiment lifecycle status."""

    DRAFT = "draft"
    RUNNING = "running"
    PAUSED = "paused"
    COMPLETED = "completed"
    CANCELLED = "cancelled"
    ARCHIVED = "archived"


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
    significance_level: float = 0.05
    power: float = 0.8
    min_effect_size: float = 0.1

    # Experiment design
    traffic_split: Dict[str, float] = field(
        default_factory=lambda: {"control": 0.5, "treatment": 0.5},
    )
    stratification_keys: List[str] = field(default_factory=list)

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
    variant: str
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
