"""

LangSmith Run Evaluators for RuleIQ
Provides custom evaluation metrics for traced runs
"""

from typing import Dict, Any, Optional, List
from dataclasses import dataclass
import logging

logger = logging.getLogger(__name__)


@dataclass
class EvaluationMetrics:
    """Container for evaluation metrics."""

    accuracy: Optional[float] = None
    latency_ms: Optional[float] = None
    token_count: Optional[int] = None
    cost_usd: Optional[float] = None
    error_rate: Optional[float] = None
    compliance_score: Optional[float] = None
    evidence_quality: Optional[float] = None

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary, excluding None values."""
        return {k: v for k, v in self.__dict__.items() if v is not None}


class LangSmithEvaluator:
    """Custom evaluator for LangSmith runs."""

    MODEL_PRICING = {
        "gpt-4": {"input": 0.03, "output": 0.06},
        "gpt-4-turbo": {"input": 0.01, "output": 0.03},
        "gpt-3.5-turbo": {"input": 0.0015, "output": 0.002},
        "claude-3-opus": {"input": 0.015, "output": 0.075},
        "claude-3-sonnet": {"input": 0.003, "output": 0.015},
    }

    @classmethod
    def evaluate_compliance_run(cls, run_data: Dict[str, Any]) -> EvaluationMetrics:
        """
        Evaluate a compliance checking run.

        Args:
            run_data: Run data from LangSmith

        Returns:
            EvaluationMetrics with compliance-specific scores
        """
        metrics = EvaluationMetrics()
        metadata = run_data.get("metadata", {})
        outputs = run_data.get("outputs", {})
        if "execution_time_seconds" in metadata:
            metrics.latency_ms = metadata["execution_time_seconds"] * 1000
        if "compliance_results" in outputs:
            results = outputs["compliance_results"]
            if isinstance(results, list):
                passed = sum((1 for r in results if r.get("status") == "passed"))
                total = len(results)
                metrics.compliance_score = passed / total * 100 if total > 0 else 0
        if metadata.get("status") == "error":
            metrics.error_rate = 1.0
        else:
            metrics.error_rate = 0.0
        return metrics

    @classmethod
    def evaluate_evidence_run(cls, run_data: Dict[str, Any]) -> EvaluationMetrics:
        """
        Evaluate an evidence processing run.

        Args:
            run_data: Run data from LangSmith

        Returns:
            EvaluationMetrics with evidence-specific scores
        """
        metrics = EvaluationMetrics()
        metadata = run_data.get("metadata", {})
        outputs = run_data.get("outputs", {})
        if "execution_time_seconds" in metadata:
            metrics.latency_ms = metadata["execution_time_seconds"] * 1000
        if "evidence_items" in outputs:
            items = outputs["evidence_items"]
            if isinstance(items, list):
                quality_scores = []
                for item in items:
                    score = 0
                    if item.get("source"):
                        score += 25
                    if item.get("verification_status"):
                        score += 25
                    if item.get("confidence_score"):
                        score += 25
                    if item.get("timestamp"):
                        score += 25
                    quality_scores.append(score)
                metrics.evidence_quality = (
                    sum(quality_scores) / len(quality_scores) if quality_scores else 0
                )
        metrics.error_rate = 1.0 if metadata.get("status") == "error" else 0.0
        return metrics

    @classmethod
    def evaluate_rag_run(cls, run_data: Dict[str, Any]) -> EvaluationMetrics:
        """
        Evaluate a RAG (Retrieval-Augmented Generation) run.

        Args:
            run_data: Run data from LangSmith

        Returns:
            EvaluationMetrics with RAG-specific scores
        """
        metrics = EvaluationMetrics()
        metadata = run_data.get("metadata", {})
        outputs = run_data.get("outputs", {})
        if "execution_time_seconds" in metadata:
            metrics.latency_ms = metadata["execution_time_seconds"] * 1000
        if "llm_output" in outputs:
            llm_output = outputs["llm_output"]
            if isinstance(llm_output, str):
                estimated_tokens = len(llm_output) // 4
                metrics.token_count = estimated_tokens
                model = metadata.get("model", "gpt-3.5-turbo")
                if model in cls.MODEL_PRICING:
                    cost_per_token = cls.MODEL_PRICING[model]["output"] / 1000
                    metrics.cost_usd = estimated_tokens * cost_per_token
        if "expected_output" in metadata and "actual_output" in outputs:
            expected = metadata["expected_output"]
            actual = outputs["actual_output"]
            if expected == actual:
                metrics.accuracy = 1.0
            else:
                metrics.accuracy = 0.5
        metrics.error_rate = 1.0 if metadata.get("status") == "error" else 0.0
        return metrics

    @classmethod
    def evaluate_run(cls, run_data: Dict[str, Any]) -> EvaluationMetrics:
        """
        Main evaluation method that routes to specific evaluators.

        Args:
            run_data: Run data from LangSmith

        Returns:
            EvaluationMetrics based on run type
        """
        tags = run_data.get("tags", [])
        operation = run_data.get("metadata", {}).get("operation", "")
        if "compliance" in operation.lower() or any(("compliance" in tag for tag in tags)):
            return cls.evaluate_compliance_run(run_data)
        elif "evidence" in operation.lower() or any(("evidence" in tag for tag in tags)):
            return cls.evaluate_evidence_run(run_data)
        elif "rag" in operation.lower() or any(("rag" in tag for tag in tags)):
            return cls.evaluate_rag_run(run_data)
        else:
            metrics = EvaluationMetrics()
            metadata = run_data.get("metadata", {})
            if "execution_time_seconds" in metadata:
                metrics.latency_ms = metadata["execution_time_seconds"] * 1000
            metrics.error_rate = 1.0 if metadata.get("status") == "error" else 0.0
            return metrics

    @classmethod
    def aggregate_metrics(cls, metrics_list: List[EvaluationMetrics]) -> Dict[str, Any]:
        """
        Aggregate multiple evaluation metrics.

        Args:
            metrics_list: List of EvaluationMetrics

        Returns:
            Aggregated statistics
        """
        if not metrics_list:
            return {}
        aggregated = {
            "total_runs": len(metrics_list),
            "avg_latency_ms": None,
            "total_tokens": 0,
            "total_cost_usd": 0,
            "avg_accuracy": None,
            "error_rate": None,
            "avg_compliance_score": None,
            "avg_evidence_quality": None,
        }
        latencies = [m.latency_ms for m in metrics_list if m.latency_ms is not None]
        accuracies = [m.accuracy for m in metrics_list if m.accuracy is not None]
        error_rates = [m.error_rate for m in metrics_list if m.error_rate is not None]
        compliance_scores = [
            m.compliance_score for m in metrics_list if m.compliance_score is not None
        ]
        evidence_qualities = [
            m.evidence_quality for m in metrics_list if m.evidence_quality is not None
        ]
        if latencies:
            aggregated["avg_latency_ms"] = sum(latencies) / len(latencies)
        if accuracies:
            aggregated["avg_accuracy"] = sum(accuracies) / len(accuracies)
        if error_rates:
            aggregated["error_rate"] = sum(error_rates) / len(error_rates)
        if compliance_scores:
            aggregated["avg_compliance_score"] = sum(compliance_scores) / len(compliance_scores)
        if evidence_qualities:
            aggregated["avg_evidence_quality"] = sum(evidence_qualities) / len(evidence_qualities)
        for m in metrics_list:
            if m.token_count:
                aggregated["total_tokens"] += m.token_count
            if m.cost_usd:
                aggregated["total_cost_usd"] += m.cost_usd
        return aggregated


class PerformanceBenchmark:
    """Utilities for performance benchmarking with LangSmith."""

    def __init__(self) -> None:
        self.baseline_metrics: Dict[str, EvaluationMetrics] = {}

    def set_baseline(self, operation: str, metrics: EvaluationMetrics) -> None:
        """Set baseline metrics for an operation."""
        self.baseline_metrics[operation] = metrics

    def compare_to_baseline(
        self, operation: str, current_metrics: EvaluationMetrics
    ) -> Dict[str, Any]:
        """
        Compare current metrics to baseline.

        Returns:
            Comparison results with percentage changes
        """
        if operation not in self.baseline_metrics:
            return {"error": f"No baseline found for operation: {operation}"}
        baseline = self.baseline_metrics[operation]
        comparison = {"operation": operation}
        if baseline.latency_ms and current_metrics.latency_ms:
            latency_change = (
                (current_metrics.latency_ms - baseline.latency_ms) / baseline.latency_ms * 100
            )
            comparison["latency_change_percent"] = latency_change
            comparison["latency_status"] = "improved" if latency_change < 0 else "degraded"
        if baseline.accuracy and current_metrics.accuracy:
            accuracy_change = (
                (current_metrics.accuracy - baseline.accuracy) / baseline.accuracy * 100
            )
            comparison["accuracy_change_percent"] = accuracy_change
            comparison["accuracy_status"] = "improved" if accuracy_change > 0 else "degraded"
        if baseline.error_rate is not None and current_metrics.error_rate is not None:
            error_change = current_metrics.error_rate - baseline.error_rate
            comparison["error_rate_change"] = error_change
            comparison["error_status"] = "improved" if error_change < 0 else "degraded"
        if baseline.cost_usd and current_metrics.cost_usd:
            cost_change = (current_metrics.cost_usd - baseline.cost_usd) / baseline.cost_usd * 100
            comparison["cost_change_percent"] = cost_change
            comparison["cost_status"] = "improved" if cost_change < 0 else "increased"
        return comparison

    def generate_report(self, recent_metrics: List[EvaluationMetrics], operation: str) -> str:
        """
        Generate a performance report.

        Args:
            recent_metrics: Recent evaluation metrics
            operation: Operation name

        Returns:
            Formatted report string
        """
        report = [f"Performance Report for {operation}"]
        report.append("=" * 50)
        aggregated = LangSmithEvaluator.aggregate_metrics(recent_metrics)
        report.append(f"Total Runs: {aggregated.get('total_runs', 0)}")
        if aggregated.get("avg_latency_ms"):
            report.append(f"Average Latency: {aggregated['avg_latency_ms']:.2f}ms")
        if aggregated.get("error_rate") is not None:
            report.append(f"Error Rate: {aggregated['error_rate']:.2%}")
        if aggregated.get("total_cost_usd"):
            report.append(f"Total Cost: ${aggregated['total_cost_usd']:.4f}")
        if aggregated.get("avg_accuracy") is not None:
            report.append(f"Average Accuracy: {aggregated['avg_accuracy']:.2%}")
        if operation in self.baseline_metrics and recent_metrics:
            avg_current = EvaluationMetrics(
                latency_ms=aggregated.get("avg_latency_ms"),
                accuracy=aggregated.get("avg_accuracy"),
                error_rate=aggregated.get("error_rate"),
                cost_usd=aggregated.get("total_cost_usd", 0) / len(recent_metrics)
                if recent_metrics
                else 0,
            )
            comparison = self.compare_to_baseline(operation, avg_current)
            report.append("\nComparison to Baseline:")
            report.append("-" * 30)
            if "latency_change_percent" in comparison:
                report.append(
                    f"Latency: {comparison['latency_change_percent']:+.1f}% ({comparison['latency_status']})"
                )
            if "accuracy_change_percent" in comparison:
                report.append(
                    f"Accuracy: {comparison['accuracy_change_percent']:+.1f}% ({comparison['accuracy_status']})"
                )
            if "error_rate_change" in comparison:
                report.append(
                    f"Error Rate: {comparison['error_rate_change']:+.2f} ({comparison['error_status']})"
                )
        return "\n".join(report)
