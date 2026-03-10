"""
Rigorous A/B Testing Framework with Statistical Analysis

REFACTORED: This file is now a thin facade re-exporting from the
services.ai.ab_testing package. All implementation has been split into
focused modules:
  - ab_testing/models.py        — Enums, dataclasses, exceptions
  - ab_testing/storage.py       — StorageBackend, InMemoryStorageBackend
  - ab_testing/analytics.py     — AnalyticsFacade, DefaultAnalyticsFacade
  - ab_testing/statistical_tests.py — Pure statistical functions
  - ab_testing/framework.py     — ABTestingFramework class
  - ab_testing/factory.py       — Global instance + convenience creators
"""

# Re-export everything from the package for backward compatibility
from .ab_testing import (  # noqa: F401
    ABTestingFramework,
    AnalyticsFacade,
    DefaultAnalyticsFacade,
    ExperimentConfig,
    ExperimentData,
    ExperimentMetricType,
    ExperimentNotFoundError,
    ExperimentStatus,
    ExperimentType,
    InMemoryStorageBackend,
    InvalidExperimentConfig,
    MetricType,
    StatisticalResult,
    StatisticalTest,
    StorageBackend,
    create_ai_model_experiment,
    create_prompt_optimization_experiment,
    get_ab_testing_framework,
)
