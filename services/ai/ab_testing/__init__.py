"""
A/B Testing Package — Rigorous statistical testing for AI model comparisons,
feature experiments, and compliance effectiveness measurements.

All public API is re-exported here for backward compatibility.
"""

# Models
from .models import (
    ExperimentConfig,
    ExperimentData,
    ExperimentMetricType,
    ExperimentNotFoundError,
    ExperimentStatus,
    ExperimentType,
    InvalidExperimentConfig,
    StatisticalResult,
    StatisticalTest,
)

# Storage
from .storage import InMemoryStorageBackend, StorageBackend

# Analytics
from .analytics import AnalyticsFacade, DefaultAnalyticsFacade

# Framework
from .framework import ABTestingFramework

# Factory functions
from .factory import (
    create_ai_model_experiment,
    create_prompt_optimization_experiment,
    get_ab_testing_framework,
)

# Backward-compat alias used by ab_testing_utils.py
MetricType = ExperimentMetricType

__all__ = [
    # Models
    "ExperimentConfig",
    "ExperimentData",
    "ExperimentMetricType",
    "ExperimentNotFoundError",
    "ExperimentStatus",
    "ExperimentType",
    "InvalidExperimentConfig",
    "StatisticalResult",
    "StatisticalTest",
    # Storage
    "InMemoryStorageBackend",
    "StorageBackend",
    # Analytics
    "AnalyticsFacade",
    "DefaultAnalyticsFacade",
    # Framework
    "ABTestingFramework",
    # Factory
    "create_ai_model_experiment",
    "create_prompt_optimization_experiment",
    "get_ab_testing_framework",
    # Backward-compat alias
    "MetricType",
]
