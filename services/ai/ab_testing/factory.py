"""
A/B Testing Factory — Global instance and convenience experiment creators.
"""

from typing import Any, Dict, Optional

from .framework import ABTestingFramework
from .models import (
    ExperimentConfig,
    ExperimentMetricType,
    ExperimentType,
)

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
    """Create an A/B experiment for comparing AI models."""
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
    """Create an A/B experiment for prompt optimization."""
    framework = get_ab_testing_framework()

    config = ExperimentConfig(
        name="Prompt Optimization Experiment",
        description="Compare effectiveness of original vs optimized prompt",
        experiment_type=ExperimentType.PROMPT_OPTIMIZATION,
        metric_type=ExperimentMetricType.BINARY,
        primary_metric=metric,
        secondary_metrics=["user_satisfaction", "response_relevance"],
        min_effect_size=0.05,
        traffic_split={"control": 0.5, "treatment": 0.5},
        min_sample_size=500,
        tags=["prompt", "optimization", "completion_rate"],
    )

    return framework.create_experiment(config)
