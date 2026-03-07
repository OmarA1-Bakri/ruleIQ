"""

Production-grade evaluation metrics for LangGraph compliance agent.
Includes recall@k, citation exactness, link precision, and performance metrics.
"""

import time
import logging
from typing import Dict, List, Any, Optional
from dataclasses import dataclass, field
from datetime import datetime, timezone
from statistics import mean, stdev
from collections import Counter

import numpy as np

logger = logging.getLogger(__name__)


@dataclass
class EvaluationResult:
    """Container for evaluation results."""

    metric_name: str
    score: float
    details: Dict[str, Any] = field(default_factory=dict)
    timestamp: datetime = field(default_factory=datetime.utcnow)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "metric_name": self.metric_name,
            "score": self.score,
            "details": self.details,
            "timestamp": self.timestamp.isoformat(),
        }


@dataclass
class LatencyMetrics:
    """Container for latency measurements."""

    p50_ms: float
    p95_ms: float
    p99_ms: float
    mean_ms: float
    max_ms: float
    min_ms: float
    samples: int

    def meets_slo(self, p95_threshold_ms: float = 2500) -> bool:
        """Check if P95 latency meets SLO requirement."""
        return self.p95_ms <= p95_threshold_ms


class RecallAtKEvaluator:
    """Evaluates recall@k for compliance recommendation systems."""

    def __init__(self, k_values: List[int] = None) -> None:
        self.k_values = k_values or [1, 3, 5, 10]

    def evaluate(
        self, predicted_items: List[List[str]], relevant_items: List[List[str]]
    ) -> Dict[str, EvaluationResult]:
        """
        Calculate recall@k for each k value.

        Args:
            predicted_items: List of prediction lists for each query
            relevant_items: List of relevant item lists for each query

        Returns:
            Dictionary mapping k values to evaluation results
        """
        if len(predicted_items) != len(relevant_items):
            raise ValueError("Predicted and relevant items must have same length")

        results = {}

        for k in self.k_values:
            recall_scores = []

            for pred, rel in zip(predicted_items, relevant_items):
                if not rel:  # Skip queries with no relevant items
                    continue

                # Take top k predictions
                top_k_pred = pred[:k]

                # Calculate recall@k for this query
                relevant_set = set(rel)
                predicted_set = set(top_k_pred)

                intersection = relevant_set.intersection(predicted_set)
                recall_k = len(intersection) / len(relevant_set)
                recall_scores.append(recall_k)

            if recall_scores:
                avg_recall = mean(recall_scores)
                results[f"recall@{k}"] = EvaluationResult(
                    metric_name=f"recall@{k}",
                    score=avg_recall,
                    details={
                        "k": k,
                        "num_queries": len(recall_scores),
                        "individual_scores": recall_scores,
                        "std_dev": (stdev(recall_scores) if len(recall_scores) > 1 else 0.0),
                    },
                )

        return results


class CitationExactnessEvaluator:
    """Evaluates citation exactness for compliance responses."""

    def evaluate(
        self,
        responses: List[str],
        expected_citations: List[List[str]],
        extracted_citations: List[List[str]],
    ) -> EvaluationResult:
        """
        Evaluate citation exactness comparing extracted vs expected citations.

        Args:
            responses: List of agent responses
            expected_citations: Expected citations for each response
            extracted_citations: Actually extracted citations from responses

        Returns:
            Citation exactness evaluation result
        """
        if not (len(responses) == len(expected_citations) == len(extracted_citations)):
            raise ValueError("All input lists must have same length")

        exactness_scores = []
        details = {
            "total_responses": len(responses),
            "perfect_matches": 0,
            "partial_matches": 0,
            "no_matches": 0,
            "citation_precision": [],
            "citation_recall": [],
        }

        for expected, extracted in zip(expected_citations, extracted_citations):
            expected_set = set(expected)
            extracted_set = set(extracted)

            if not expected_set and not extracted_set:
                # Both empty - perfect match
                exactness_scores.append(1.0)
                details["perfect_matches"] += 1
                continue

            if not expected_set or not extracted_set:
                # One empty, one not - no match
                exactness_scores.append(0.0)
                details["no_matches"] += 1
                continue

            # Calculate precision and recall for citations
            intersection = expected_set.intersection(extracted_set)

            precision = len(intersection) / len(extracted_set) if extracted_set else 0.0
            recall = len(intersection) / len(expected_set) if expected_set else 0.0

            details["citation_precision"].append(precision)
            details["citation_recall"].append(recall)

            # F1 score as exactness measure
            if precision + recall > 0:
                f1_score = 2 * (precision * recall) / (precision + recall)
                exactness_scores.append(f1_score)

                if f1_score == 1.0:
                    details["perfect_matches"] += 1
                else:
                    details["partial_matches"] += 1
            else:
                exactness_scores.append(0.0)
                details["no_matches"] += 1

        # Calculate aggregate metrics
        avg_exactness = mean(exactness_scores) if exactness_scores else 0.0
        details["avg_precision"] = (
            mean(details["citation_precision"]) if details["citation_precision"] else 0.0
        )
        details["avg_recall"] = (
            mean(details["citation_recall"]) if details["citation_recall"] else 0.0
        )

        return EvaluationResult(
            metric_name="citation_exactness", score=avg_exactness, details=details
        )


class LinkPrecisionEvaluator:
    """Evaluates precision of legal/regulatory links in responses."""

    def __init__(self, valid_domains: List[str] = None) -> None:
        """
        Initialize with valid regulatory domains.

        Args:
            valid_domains: List of valid legal/regulatory domains
        """
        self.valid_domains = valid_domains or [
            "ico.org.uk",  # UK Information Commissioner's Office
            "gov.uk",  # UK Government
            "eur-lex.europa.eu",  # EU Legal Database
            "gdpr.eu",  # GDPR Info
            "legislation.gov.uk",  # UK Legislation
        ]

    def extract_links(self, text: str) -> List[str]:
        """Extract URLs from text using basic regex."""
        import re

        url_pattern = (
            r"http[s]?://(?:[a-zA-Z]|[0-9]|[$-_@.&+]|[!*\\(\\),]|(?:%[0-9a-fA-F][0-9a-fA-F]))+"
        )
        return re.findall(url_pattern, text)

    def is_valid_link(self, url: str) -> bool:
        """Check if URL is from a valid regulatory domain."""
        from urllib.parse import urlparse

        try:
            domain = urlparse(url).netloc.lower()
            return any(valid_domain in domain for valid_domain in self.valid_domains)
        except ValueError:
            return False

    def evaluate(self, responses: List[str]) -> EvaluationResult:
        """
        Evaluate link precision across responses.

        Args:
            responses: List of agent responses containing links

        Returns:
            Link precision evaluation result
        """
        total_links = 0
        valid_links = 0
        invalid_links = []
        valid_link_examples = []

        for response in responses:
            links = self.extract_links(response)
            total_links += len(links)

            for link in links:
                if self.is_valid_link(link):
                    valid_links += 1
                    valid_link_examples.append(link)
                else:
                    invalid_links.append(link)

        precision = valid_links / total_links if total_links > 0 else 1.0

        details = {
            "total_links": total_links,
            "valid_links": valid_links,
            "invalid_links_count": len(invalid_links),
            "precision": precision,
            "invalid_link_examples": invalid_links[:5],  # First 5 examples
            "valid_link_examples": valid_link_examples[:5],  # First 5 examples
            "valid_domains": self.valid_domains,
        }

        return EvaluationResult(metric_name="link_precision", score=precision, details=details)


class CounselFPREvaluator:
    """Evaluates False Positive Rate for legal counsel recommendations."""

    def __init__(self, counsel_triggers: List[str] = None) -> None:
        """
        Initialize with phrases that should trigger counsel recommendations.

        Args:
            counsel_triggers: Phrases that should trigger legal counsel advice
        """
        self.counsel_triggers = counsel_triggers or [
            "legal review required",
            "consult legal counsel",
            "seek legal advice",
            "lawyer consultation",
            "legal professional",
            "attorney review",
        ]

    def should_recommend_counsel(self, context: Dict[str, Any]) -> bool:
        """
        Determine if context should trigger counsel recommendation.

        Args:
            context: Context including query complexity, risk level, etc.

        Returns:
            True if counsel should be recommended
        """
        # High-risk scenarios that should trigger counsel
        risk_level = context.get("risk_level", "low")
        complexity = context.get("complexity", "low")
        legal_uncertainty = context.get("legal_uncertainty", False)

        return (
            risk_level in ["high", "critical"]
            or complexity == "high"
            or legal_uncertainty
            or context.get("requires_legal_review", False)
        )

    def contains_counsel_recommendation(self, response: str) -> bool:
        """Check if response contains counsel recommendation."""
        response_lower = response.lower()
        return any(trigger in response_lower for trigger in self.counsel_triggers)

    def evaluate(self, responses: List[str], contexts: List[Dict[str, Any]]) -> EvaluationResult:
        """
        Evaluate False Positive Rate for counsel recommendations.

        Args:
            responses: Agent responses
            contexts: Context for each response

        Returns:
            Counsel FPR evaluation result
        """
        if len(responses) != len(contexts):
            raise ValueError("Responses and contexts must have same length")

        true_positives = 0  # Should recommend and did recommend
        false_positives = 0  # Shouldn't recommend but did recommend
        true_negatives = 0  # Shouldn't recommend and didn't recommend
        false_negatives = 0  # Should recommend but didn't recommend

        for response, context in zip(responses, contexts):
            should_recommend = self.should_recommend_counsel(context)
            did_recommend = self.contains_counsel_recommendation(response)

            if should_recommend and did_recommend:
                true_positives += 1
            elif not should_recommend and did_recommend:
                false_positives += 1
            elif not should_recommend and not did_recommend:
                true_negatives += 1
            else:  # should_recommend and not did_recommend
                false_negatives += 1

        # Calculate metrics
        total = len(responses)
        fpr = (
            false_positives / (false_positives + true_negatives)
            if (false_positives + true_negatives) > 0
            else 0.0
        )
        precision = (
            true_positives / (true_positives + false_positives)
            if (true_positives + false_positives) > 0
            else 0.0
        )
        recall = (
            true_positives / (true_positives + false_negatives)
            if (true_positives + false_negatives) > 0
            else 0.0
        )

        details = {
            "total_cases": total,
            "true_positives": true_positives,
            "false_positives": false_positives,
            "true_negatives": true_negatives,
            "false_negatives": false_negatives,
            "false_positive_rate": fpr,
            "precision": precision,
            "recall": recall,
            "accuracy": (true_positives + true_negatives) / total if total > 0 else 0.0,
        }

        return EvaluationResult(
            metric_name="counsel_fpr",
            score=1.0 - fpr,  # Score is 1 - FPR (higher is better)
            details=details,
        )


class LatencyEvaluator:
    """Evaluates agent response latency and SLO compliance."""

    def __init__(self, slo_p95_ms: float = 2500) -> None:
        """
        Initialize with SLO threshold.

        Args:
            slo_p95_ms: P95 latency SLO threshold in milliseconds
        """
        self.slo_p95_ms = slo_p95_ms
        self.latency_samples: List[float] = []

    def add_sample(self, latency_ms: float) -> None:
        """Add a latency sample."""
        self.latency_samples.append(latency_ms)

    def clear_samples(self) -> None:
        """Clear all latency samples."""
        self.latency_samples.clear()

    def calculate_percentiles(self) -> LatencyMetrics:
        """Calculate latency percentiles from samples."""
        if not self.latency_samples:
            return LatencyMetrics(0, 0, 0, 0, 0, 0, 0)

        sorted_samples = sorted(self.latency_samples)
        n = len(sorted_samples)

        p50_ms = np.percentile(sorted_samples, 50)
        p95_ms = np.percentile(sorted_samples, 95)
        p99_ms = np.percentile(sorted_samples, 99)
        mean_ms = mean(sorted_samples)
        max_ms = max(sorted_samples)
        min_ms = min(sorted_samples)

        return LatencyMetrics(
            p50_ms=float(p50_ms),
            p95_ms=float(p95_ms),
            p99_ms=float(p99_ms),
            mean_ms=mean_ms,
            max_ms=max_ms,
            min_ms=min_ms,
            samples=n,
        )

    def evaluate(self) -> EvaluationResult:
        """Evaluate current latency metrics."""
        metrics = self.calculate_percentiles()

        # Score based on SLO compliance (1.0 if P95 meets SLO, scaled down if not)
        if metrics.p95_ms <= self.slo_p95_ms:
            score = 1.0
        else:
            # Gradual degradation up to 2x SLO threshold
            score = max(0.0, 1.0 - (metrics.p95_ms - self.slo_p95_ms) / self.slo_p95_ms)

        details = {
            "p50_ms": metrics.p50_ms,
            "p95_ms": metrics.p95_ms,
            "p99_ms": metrics.p99_ms,
            "mean_ms": metrics.mean_ms,
            "max_ms": metrics.max_ms,
            "min_ms": metrics.min_ms,
            "samples": metrics.samples,
            "slo_p95_ms": self.slo_p95_ms,
            "meets_slo": metrics.meets_slo(self.slo_p95_ms),
            "slo_violation_ratio": max(0, metrics.p95_ms / self.slo_p95_ms - 1.0),
        }

        return EvaluationResult(metric_name="latency_slo", score=score, details=details)


class AgentPerformanceEvaluator:
    """Evaluates overall agent performance including success rates and error handling."""

    def __init__(self) -> None:
        self.interaction_results: List[Dict[str, Any]] = []

    def add_interaction_result(
        self,
        success: bool,
        error_type: Optional[str] = None,
        latency_ms: float = 0.0,
        user_satisfaction: Optional[float] = None,
        task_completion: bool = True,
    ) -> None:
        """
        Add an interaction result for evaluation.

        Args:
            success: Whether the interaction was successful
            error_type: Type of error if failed
            latency_ms: Response latency in milliseconds
            user_satisfaction: User satisfaction score (0-1)
            task_completion: Whether the task was completed
        """
        self.interaction_results.append(
            {
                "success": success,
                "error_type": error_type,
                "latency_ms": latency_ms,
                "user_satisfaction": user_satisfaction,
                "task_completion": task_completion,
                "timestamp": datetime.now(timezone.utc),
            }
        )

    def evaluate(self) -> Dict[str, EvaluationResult]:
        """Evaluate agent performance across multiple dimensions."""
        if not self.interaction_results:
            return {}

        results = {}
        total_interactions = len(self.interaction_results)

        # Success Rate
        successful_interactions = sum(1 for r in self.interaction_results if r["success"])
        success_rate = successful_interactions / total_interactions

        results["success_rate"] = EvaluationResult(
            metric_name="success_rate",
            score=success_rate,
            details={
                "successful_interactions": successful_interactions,
                "total_interactions": total_interactions,
                "failure_rate": 1.0 - success_rate,
            },
        )

        # Error Analysis
        error_counts = Counter(
            r["error_type"] for r in self.interaction_results if r["error_type"] is not None
        )

        results["error_analysis"] = EvaluationResult(
            metric_name="error_analysis",
            score=1.0
            - len(error_counts) / max(total_interactions, 1),  # Fewer error types is better
            details={
                "error_counts": dict(error_counts),
                "unique_error_types": len(error_counts),
                "most_common_errors": error_counts.most_common(5),
            },
        )

        # Task Completion Rate
        completed_tasks = sum(1 for r in self.interaction_results if r["task_completion"])
        completion_rate = completed_tasks / total_interactions

        results["task_completion_rate"] = EvaluationResult(
            metric_name="task_completion_rate",
            score=completion_rate,
            details={
                "completed_tasks": completed_tasks,
                "total_tasks": total_interactions,
                "incomplete_rate": 1.0 - completion_rate,
            },
        )

        # User Satisfaction (if available)
        satisfaction_scores = [
            r["user_satisfaction"]
            for r in self.interaction_results
            if r["user_satisfaction"] is not None
        ]

        if satisfaction_scores:
            avg_satisfaction = mean(satisfaction_scores)
            results["user_satisfaction"] = EvaluationResult(
                metric_name="user_satisfaction",
                score=avg_satisfaction,
                details={
                    "average_satisfaction": avg_satisfaction,
                    "satisfaction_samples": len(satisfaction_scores),
                    "satisfaction_std": (
                        stdev(satisfaction_scores) if len(satisfaction_scores) > 1 else 0.0
                    ),
                },
            )

        return results

    def clear_results(self) -> None:
        """Clear all interaction results."""
        self.interaction_results.clear()


class ComprehensiveEvaluator:
    """Comprehensive evaluator that orchestrates all evaluation metrics."""

    def __init__(self, slo_p95_ms: float = 2500) -> None:
        """
        Initialize comprehensive evaluator.

        Args:
            slo_p95_ms: P95 latency SLO threshold in milliseconds
        """
        self.recall_evaluator = RecallAtKEvaluator()
        self.citation_evaluator = CitationExactnessEvaluator()
        self.link_evaluator = LinkPrecisionEvaluator()
        self.counsel_evaluator = CounselFPREvaluator()
        self.latency_evaluator = LatencyEvaluator(slo_p95_ms)
        self.performance_evaluator = AgentPerformanceEvaluator()

    def evaluate_all(self, evaluation_data: Dict[str, Any]) -> Dict[str, EvaluationResult]:
        """
        Run comprehensive evaluation across all metrics.

        Args:
            evaluation_data: Dictionary containing all evaluation data

        Returns:
            Dictionary of evaluation results by metric name
        """
        results = {}

        # Recall@K evaluation
        if "recall_data" in evaluation_data:
            recall_data = evaluation_data["recall_data"]
            recall_results = self.recall_evaluator.evaluate(
                recall_data["predicted_items"], recall_data["relevant_items"]
            )
            results.update(recall_results)

        # Citation exactness evaluation
        if "citation_data" in evaluation_data:
            citation_data = evaluation_data["citation_data"]
            citation_result = self.citation_evaluator.evaluate(
                citation_data["responses"],
                citation_data["expected_citations"],
                citation_data["extracted_citations"],
            )
            results[citation_result.metric_name] = citation_result

        # Link precision evaluation
        if "responses" in evaluation_data:
            link_result = self.link_evaluator.evaluate(evaluation_data["responses"])
            results[link_result.metric_name] = link_result

        # Counsel FPR evaluation
        if "counsel_data" in evaluation_data:
            counsel_data = evaluation_data["counsel_data"]
            counsel_result = self.counsel_evaluator.evaluate(
                counsel_data["responses"], counsel_data["contexts"]
            )
            results[counsel_result.metric_name] = counsel_result

        # Latency evaluation
        latency_result = self.latency_evaluator.evaluate()
        results[latency_result.metric_name] = latency_result

        # Performance evaluation
        performance_results = self.performance_evaluator.evaluate()
        results.update(performance_results)

        return results

    def generate_evaluation_report(self, results: Dict[str, EvaluationResult]) -> Dict[str, Any]:
        """
        Generate comprehensive evaluation report.

        Args:
            results: Dictionary of evaluation results

        Returns:
            Comprehensive evaluation report
        """
        report = {
            "evaluation_timestamp": datetime.now(timezone.utc).isoformat(),
            "overall_score": 0.0,
            "metric_scores": {},
            "slo_compliance": {},
            "recommendations": [],
            "details": {},
        }

        # Calculate overall score (weighted average)
        metric_weights = {
            "success_rate": 0.25,
            "latency_slo": 0.20,
            "citation_exactness": 0.15,
            "task_completion_rate": 0.15,
            "recall@5": 0.10,
            "link_precision": 0.10,
            "counsel_fpr": 0.05,
        }

        weighted_scores = []
        for metric_name, result in results.items():
            weight = metric_weights.get(metric_name, 0.05)  # Default weight for unlisted metrics
            weighted_scores.append(result.score * weight)
            report["metric_scores"][metric_name] = result.score
            report["details"][metric_name] = result.details

        report["overall_score"] = sum(weighted_scores)

        # SLO compliance analysis
        if "latency_slo" in results:
            latency_details = results["latency_slo"].details
            report["slo_compliance"] = {
                "p95_latency_ms": latency_details["p95_ms"],
                "slo_threshold_ms": latency_details["slo_p95_ms"],
                "meets_slo": latency_details["meets_slo"],
                "violation_ratio": latency_details.get("slo_violation_ratio", 0.0),
            }

        # Generate recommendations
        recommendations = []

        if report["overall_score"] < 0.8:
            recommendations.append(
                "Overall performance below target (80%). Review individual metrics."
            )

        if "success_rate" in results and results["success_rate"].score < 0.95:
            recommendations.append(
                "Success rate below 95%. Investigate error patterns and improve error handling."
            )

        if "latency_slo" in results and not results["latency_slo"].details["meets_slo"]:
            recommendations.append(
                "P95 latency exceeds SLO. Optimize critical paths and consider caching."
            )

        if "citation_exactness" in results and results["citation_exactness"].score < 0.8:
            recommendations.append(
                "Citation exactness below 80%. Improve source attribution and validation."
            )

        report["recommendations"] = recommendations

        return report


# Utility functions for evaluation data preparation


def prepare_recall_evaluation_data(
    predictions: List[List[str]], ground_truth: List[List[str]]
) -> Dict[str, Any]:
    """Prepare data for recall@k evaluation."""
    return {"predicted_items": predictions, "relevant_items": ground_truth}


def prepare_citation_evaluation_data(
    responses: List[str],
    expected_citations: List[List[str]],
    extracted_citations: List[List[str]],
) -> Dict[str, Any]:
    """Prepare data for citation exactness evaluation."""
    return {
        "responses": responses,
        "expected_citations": expected_citations,
        "extracted_citations": extracted_citations,
    }


def prepare_counsel_evaluation_data(
    responses: List[str], contexts: List[Dict[str, Any]]
) -> Dict[str, Any]:
    """Prepare data for counsel FPR evaluation."""
    return {"responses": responses, "contexts": contexts}


async def run_latency_smoke_test(
    graph_function,
    test_inputs: List[Dict[str, Any]],
    target_p95_ms: float = 2500,
    num_iterations: int = 10,
) -> LatencyMetrics:
    """
    Run latency smoke test on graph function.

    Args:
        graph_function: Async function to test
        test_inputs: List of test input dictionaries
        target_p95_ms: Target P95 latency in milliseconds
        num_iterations: Number of test iterations

    Returns:
        LatencyMetrics with test results
    """
    latency_evaluator = LatencyEvaluator(target_p95_ms)

    logger.info(f"Starting latency smoke test with {num_iterations} iterations")

    for i in range(num_iterations):
        for test_input in test_inputs:
            start_time = time.time()

            try:
                await graph_function(**test_input)
                end_time = time.time()
                latency_ms = (end_time - start_time) * 1000
                latency_evaluator.add_sample(latency_ms)

            except (ValueError, TypeError) as e:
                logger.error(f"Test iteration {i} failed: {e}")
                # Still record the time taken until failure
                end_time = time.time()
                latency_ms = (end_time - start_time) * 1000
                latency_evaluator.add_sample(latency_ms)

    metrics = latency_evaluator.calculate_percentiles()

    logger.info("Latency smoke test completed:")
    logger.info(f"  P50: {metrics.p50_ms:.1f}ms")
    logger.info(f"  P95: {metrics.p95_ms:.1f}ms")
    logger.info(f"  P99: {metrics.p99_ms:.1f}ms")
    logger.info(f"  SLO compliance: {metrics.meets_slo(target_p95_ms)}")

    return metrics
