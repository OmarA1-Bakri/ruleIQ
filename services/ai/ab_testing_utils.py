"""
import logging


logger = logging.getLogger(__name__)
# Constants
DEFAULT_TIMEOUT = 30

CONFIDENCE_THRESHOLD = 0.8


A/B Testing Utilities and Integration Helpers

Provides convenient utilities for integrating A/B testing into the ruleIQ
compliance system, including AI model testing, prompt optimization,
and compliance effectiveness measurement.
"""

from typing import Any, Dict, List, Optional
from enum import Enum
from .ab_testing_framework import (
    ExperimentConfig,
    ExperimentType,
    MetricType,
    StatisticalResult,
    get_ab_testing_framework,
    create_ai_model_experiment,
)
from .analytics_monitor import get_analytics_monitor
from config.logging_config import get_logger

logger = get_logger(__name__)


class ComplianceMetric(Enum):
    """Compliance-specific metrics for A/B testing."""

    ASSESSMENT_ACCURACY = "assessment_accuracy"
    COMPLIANCE_SCORE_IMPROVEMENT = "compliance_score_improvement"
    EVIDENCE_COLLECTION_RATE = "evidence_collection_rate"
    USER_SATISFACTION = "user_satisfaction"
    TASK_COMPLETION_TIME = "task_completion_time"
    ERROR_RATE = "error_rate"
    RECOMMENDATION_RELEVANCE = "recommendation_relevance"


class AIModelTester:
    """A/B testing utilities for AI model comparisons."""

    def __init__(self) -> None:
        self.framework = get_ab_testing_framework()
        self.analytics = get_analytics_monitor()
        self.active_experiments: Dict[str, str] = {}

    def setup_model_comparison(
        self,
        control_model: str,
        treatment_model: str,
        metric: ComplianceMetric = ComplianceMetric.ASSESSMENT_ACCURACY,
        min_effect_size: float = 0.05,
    ) -> str:
        """
        Set up A/B test for comparing two AI models.

        Args:
            control_model: Current/baseline model
            treatment_model: New model to test
            metric: Primary metric to compare
            min_effect_size: Minimum meaningful difference

        Returns:
            Experiment ID
        """
        experiment_id = create_ai_model_experiment(
            model_a=control_model,
            model_b=treatment_model,
            metric=metric.value,
            min_effect_size=min_effect_size,
        )
        model_pair = f"{control_model}_vs_{treatment_model}"
        self.active_experiments[model_pair] = experiment_id
        logger.info(
            "Set up model comparison: %s vs %s (exp: %s)"
            % (control_model, treatment_model, experiment_id)
        )
        return experiment_id

    def record_model_performance(
        self,
        experiment_id: str,
        model_name: str,
        user_id: str,
        metric_value: float,
        context: Optional[Dict[str, Any]] = None,
    ) -> bool:
        """
        Record performance metric for a model in an experiment.

        Args:
            experiment_id: ID of the experiment
            model_name: Name of the model (determines variant)
            user_id: User who triggered the evaluation
            metric_value: Performance metric value
            context: Additional context

        Returns:
            True if recorded successfully
        """
        variant = "treatment" if "treatment" in model_name.lower() else "control"
        return self.framework.record_metric(
            experiment_id=experiment_id,
            variant=variant,
            user_id=user_id,
            primary_metric_value=metric_value,
            context=context or {},
        )

    def analyze_model_performance(self, experiment_id: str) -> StatisticalResult:
        """
        Analyze A/B test results for model comparison.

        Args:
            experiment_id: ID of the experiment to analyze

        Returns:
            Statistical analysis results
        """
        result = self.framework.analyze_experiment(experiment_id)
        if result.is_significant:
            logger.info(
                "Model experiment %s shows significant difference: p=%s, effect size=%s"
                % (experiment_id, result.p_value, result.effect_size)
            )
        return result


class PromptOptimizationTester:
    """A/B testing utilities for prompt optimization."""

    def __init__(self) -> None:
        self.framework = get_ab_testing_framework()
        self.analytics = get_analytics_monitor()

    def setup_prompt_test(
        self,
        original_prompt: str,
        optimized_prompt: str,
        task_type: str,
        metric: ComplianceMetric = ComplianceMetric.TASK_COMPLETION_TIME,
    ) -> str:
        """
        Set up A/B test for prompt optimization.

        Args:
            original_prompt: Current prompt (control)
            optimized_prompt: New prompt to test (treatment)
            task_type: Type of task (assessment, evidence, etc.)
            metric: Primary metric to compare

        Returns:
            Experiment ID
        """
        config = ExperimentConfig(
            name=f"Prompt Optimization: {task_type}",
            description=f"Compare prompt effectiveness for {task_type} tasks",
            experiment_type=ExperimentType.PROMPT_OPTIMIZATION,
            metric_type=MetricType.CONTINUOUS
            if metric
            in [ComplianceMetric.TASK_COMPLETION_TIME, ComplianceMetric.ASSESSMENT_ACCURACY]
            else MetricType.BINARY,
            primary_metric=metric.value,
            secondary_metrics=["user_satisfaction", "response_relevance"],
            min_effect_size=0.1,
            traffic_split={"control": 0.5, "treatment": 0.5},
            min_sample_size=100,
            tags=["prompt", "optimization", task_type],
        )
        experiment_id = self.framework.create_experiment(config)
        logger.info("Set up prompt optimization test for %s (exp: %s)" % (task_type, experiment_id))
        return experiment_id

    def get_prompt_variant(self, experiment_id: str, user_id: str) -> str:
        """
        Get which prompt variant to use for a user.

        Args:
            experiment_id: ID of the experiment
            user_id: User identifier

        Returns:
            Variant name ("control" or "treatment")
        """
        return self.framework.assign_variant(experiment_id, user_id)

    def record_prompt_result(
        self,
        experiment_id: str,
        variant: str,
        user_id: str,
        metric_value: float,
        task_context: Optional[Dict[str, Any]] = None,
    ) -> bool:
        """
        Record result of using a prompt variant.

        Args:
            experiment_id: ID of the experiment
            variant: Which prompt variant was used
            user_id: User who completed the task
            metric_value: Task performance metric
            task_context: Additional task context

        Returns:
            True if recorded successfully
        """
        return self.framework.record_metric(
            experiment_id=experiment_id,
            variant=variant,
            user_id=user_id,
            primary_metric_value=metric_value,
            context=task_context or {},
        )


class ComplianceEffectivenessTester:
    """A/B testing for compliance methodology effectiveness."""

    def __init__(self) -> None:
        self.framework = get_ab_testing_framework()
        self.analytics = get_analytics_monitor()

    def setup_methodology_test(
        self,
        methodology_name: str,
        control_approach: str,
        treatment_approach: str,
        metric: ComplianceMetric = ComplianceMetric.COMPLIANCE_SCORE_IMPROVEMENT,
    ) -> str:
        """
        Set up A/B test for compliance methodology effectiveness.

        Args:
            methodology_name: Name of the methodology being tested
            control_approach: Current approach
            treatment_approach: New approach to test
            metric: Primary effectiveness metric

        Returns:
            Experiment ID
        """
        config = ExperimentConfig(
            name=f"Compliance Methodology: {methodology_name}",
            description=f"Compare {control_approach} vs {treatment_approach}",
            experiment_type=ExperimentType.COMPLIANCE_EFFECTIVENESS,
            metric_type=MetricType.CONTINUOUS,
            primary_metric=metric.value,
            secondary_metrics=[
                "evidence_collection_rate",
                "user_satisfaction",
                "task_completion_time",
            ],
            min_effect_size=0.15,
            traffic_split={"control": 0.5, "treatment": 0.5},
            min_sample_size=50,
            max_duration_days=60,
            tags=["compliance", "methodology", methodology_name],
        )
        experiment_id = self.framework.create_experiment(config)
        logger.info(
            "Set up compliance methodology test: %s (exp: %s)" % (methodology_name, experiment_id)
        )
        return experiment_id

    def record_compliance_outcome(
        self,
        experiment_id: str,
        variant: str,
        organization_id: str,
        improvement_score: float,
        baseline_score: float,
        context: Optional[Dict[str, Any]] = None,
    ) -> bool:
        """
        Record compliance improvement outcome.

        Args:
            experiment_id: ID of the experiment
            variant: Which methodology was used
            organization_id: Organization identifier
            improvement_score: Final compliance score
            baseline_score: Starting compliance score
            context: Additional context

        Returns:
            True if recorded successfully
        """
        improvement_percentage = (improvement_score - baseline_score) / baseline_score * 100
        enhanced_context = context or {}
        enhanced_context.update(
            {
                "baseline_score": baseline_score,
                "final_score": improvement_score,
                "improvement_percentage": improvement_percentage,
            }
        )
        return self.framework.record_metric(
            experiment_id=experiment_id,
            variant=variant,
            user_id=organization_id,
            primary_metric_value=improvement_percentage,
            context=enhanced_context,
        )


class ABTestingManager:
    """Central manager for all A/B testing activities in ruleIQ."""

    def __init__(self) -> None:
        self.framework = get_ab_testing_framework()
        self.model_tester = AIModelTester()
        self.prompt_tester = PromptOptimizationTester()
        self.compliance_tester = ComplianceEffectivenessTester()
        self.active_experiments: Dict[str, List[str]] = {
            "model_comparison": [],
            "prompt_optimization": [],
            "compliance_effectiveness": [],
            "feature_rollout": [],
        }

    def start_ai_model_experiment(
        self,
        control_model: str,
        treatment_model: str,
        metric: ComplianceMetric = ComplianceMetric.ASSESSMENT_ACCURACY,
    ) -> str:
        """Start an AI model comparison experiment."""
        experiment_id = self.model_tester.setup_model_comparison(
            control_model, treatment_model, metric
        )
        self.framework.start_experiment(experiment_id)
        self.active_experiments["model_comparison"].append(experiment_id)
        return experiment_id

    def start_prompt_experiment(
        self, original_prompt: str, optimized_prompt: str, task_type: str
    ) -> str:
        """Start a prompt optimization experiment."""
        experiment_id = self.prompt_tester.setup_prompt_test(
            original_prompt, optimized_prompt, task_type
        )
        self.framework.start_experiment(experiment_id)
        self.active_experiments["prompt_optimization"].append(experiment_id)
        return experiment_id

    def start_compliance_experiment(
        self, methodology_name: str, control_approach: str, treatment_approach: str
    ) -> str:
        """Start a compliance methodology experiment."""
        experiment_id = self.compliance_tester.setup_methodology_test(
            methodology_name, control_approach, treatment_approach
        )
        self.framework.start_experiment(experiment_id)
        self.active_experiments["compliance_effectiveness"].append(experiment_id)
        return experiment_id

    def get_experiment_results(self, experiment_type: Optional[str] = None) -> List[Dict[str, Any]]:
        """Get results for all experiments of a given type."""
        experiments_to_analyze = []
        if experiment_type and experiment_type in self.active_experiments:
            experiments_to_analyze = self.active_experiments[experiment_type]
        else:
            for exp_list in self.active_experiments.values():
                experiments_to_analyze.extend(exp_list)
        results = []
        for experiment_id in experiments_to_analyze:
            try:
                summary = self.framework.get_experiment_summary(experiment_id)
                if summary["data_summary"]["total_observations"] >= DEFAULT_TIMEOUT:
                    latest_result = self.framework.analyze_experiment(experiment_id)
                    summary["latest_analysis"] = {
                        "p_value": latest_result.p_value,
                        "effect_size": latest_result.effect_size,
                        "is_significant": latest_result.is_significant,
                        "recommendation": latest_result.recommendation,
                        "confidence_interval": latest_result.confidence_interval,
                    }
                results.append(summary)
            except Exception as e:
                logger.error("Error analyzing experiment %s: %s" % (experiment_id, e))
        return results

    def get_statistical_power_analysis(self, experiment_id: str) -> Dict[str, Any]:
        """Get detailed statistical power analysis for an experiment."""
        summary = self.framework.get_experiment_summary(experiment_id)
        if not summary["results"]:
            return {"error": "No analysis results available"}
        latest_result = summary["results"][-1]
        power_analysis = {
            "current_power": latest_result["power"],
            "sample_size": sum(summary["data_summary"]["variant_counts"].values()),
            "effect_size": latest_result["effect_size"],
            "p_value": latest_result["p_value"],
            "recommendation": latest_result["recommendation"],
            "statistical_significance": latest_result["is_significant"],
            "practical_significance": latest_result["practical_significance"],
        }
        if latest_result["power"] < CONFIDENCE_THRESHOLD:
            required_additional_samples = self._estimate_additional_samples_needed(
                latest_result["power"], latest_result["effect_size"]
            )
            power_analysis["additional_samples_needed"] = required_additional_samples
        return power_analysis

    def _estimate_additional_samples_needed(self, current_power: float, effect_size: float) -> int:
        """Estimate additional samples needed to reach 80% power."""
        if current_power >= CONFIDENCE_THRESHOLD:
            return 0
        current_total = sum(
            summary["data_summary"]["variant_counts"].values()
            for summary in [
                self.framework.get_experiment_summary(exp_id)
                for exp_list in self.active_experiments.values()
                for exp_id in exp_list
            ]
            if summary["data_summary"]["total_observations"] > 0
        )
        return max(100, int(current_total * (0.8 - current_power) / current_power))


_ab_testing_manager: Optional[ABTestingManager] = None


def get_ab_testing_manager() -> ABTestingManager:
    """Get global A/B testing manager instance."""
    global _ab_testing_manager
    if _ab_testing_manager is None:
        _ab_testing_manager = ABTestingManager()
    return _ab_testing_manager


def start_model_comparison(control_model: str, treatment_model: str) -> str:
    """Quick start for AI model A/B testing."""
    manager = get_ab_testing_manager()
    return manager.start_ai_model_experiment(control_model, treatment_model)


def record_ai_performance(
    experiment_id: str, model_name: str, user_id: str, accuracy_score: float
) -> bool:
    """Quick record for AI model performance."""
    manager = get_ab_testing_manager()
    return manager.model_tester.record_model_performance(
        experiment_id, model_name, user_id, accuracy_score
    )


def analyze_experiment_results(experiment_id: str) -> Dict[str, Any]:
    """Quick analysis for any experiment."""
    manager = get_ab_testing_manager()
    return manager.framework.get_experiment_summary(experiment_id)
