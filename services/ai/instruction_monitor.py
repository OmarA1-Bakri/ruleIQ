"""
import logging


logger = logging.getLogger(__name__)
# Constants
DEFAULT_TIMEOUT = 30.0

DEFAULT_RETRIES = 5
HIGH_CONFIDENCE_THRESHOLD = 0.95


Instruction Performance Monitoring and A/B Testing Framework

This module provides comprehensive monitoring, analytics, and A/B testing capabilities
for system instructions to optimize AI response quality and effectiveness.
"""

import abc
import json
import os
import statistics
from collections import deque
from dataclasses import asdict, dataclass
from datetime import datetime, timedelta
from enum import Enum
from typing import Any, Dict, List, Optional
from uuid import uuid4
from config.logging_config import get_logger

logger = get_logger(__name__)


class InstructionPersistence(abc.ABC):
    """Abstract interface for instruction data persistence"""

    @abc.abstractmethod
    def save_metrics(self, metrics: List["InstructionMetric"]) -> None:
        """Save metrics to persistent storage"""
        pass

    @abc.abstractmethod
    def load_metrics(self) -> List["InstructionMetric"]:
        """Load metrics from persistent storage"""
        pass

    @abc.abstractmethod
    def save_performance_data(self, data: Dict[str, "InstructionPerformanceData"]) -> None:
        """Save performance data to persistent storage"""
        pass

    @abc.abstractmethod
    def load_performance_data(self) -> Dict[str, "InstructionPerformanceData"]:
        """Load performance data from persistent storage"""
        pass


class MemoryPersistence(InstructionPersistence):
    """Development/testing persistence - in memory only"""

    def save_metrics(self, metrics: List["InstructionMetric"]) -> None:
        pass

    def load_metrics(self) -> List["InstructionMetric"]:
        return []

    def save_performance_data(self, data: Dict[str, "InstructionPerformanceData"]) -> None:
        pass

    def load_performance_data(self) -> Dict[str, "InstructionPerformanceData"]:
        return {}


class FilePersistence(InstructionPersistence):
    """Production-ready file-based persistence"""

    def __init__(self, data_dir: str = "./data/instructions") -> None:
        self.data_dir = data_dir
        os.makedirs(data_dir, exist_ok=True)
        self.metrics_file = os.path.join(data_dir, "metrics.json")
        self.performance_file = os.path.join(data_dir, "performance.json")

    def save_metrics(self, metrics: List["InstructionMetric"]) -> None:
        try:
            with open(self.metrics_file, "w") as f:
                json.dump([asdict(m) for m in metrics], f, indent=4)
        except Exception as e:
            logger.error("Failed to save metrics: %s" % e)

    def load_metrics(self) -> List["InstructionMetric"]:
        try:
            if os.path.exists(self.metrics_file):
                with open(self.metrics_file, "r") as f:
                    data = json.load(f)
                    return [InstructionMetric(**m) for m in data]
        except Exception as e:
            logger.error("Failed to load metrics: %s" % e)
        return []

    def save_performance_data(self, data: Dict[str, "InstructionPerformanceData"]) -> None:
        try:
            with open(self.performance_file, "w") as f:
                json.dump({k: asdict(v) for k, v in data.items()}, f, indent=4)
        except Exception as e:
            logger.error("Failed to save performance data: %s" % e)

    def load_performance_data(self) -> Dict[str, "InstructionPerformanceData"]:
        try:
            if os.path.exists(self.performance_file):
                with open(self.performance_file, "r") as f:
                    data = json.load(f)
                    return {k: InstructionPerformanceData(**v) for k, v in data.items()}
        except Exception as e:
            logger.error("Failed to load performance data: %s" % e)
        return {}


class InstructionMetricType(Enum):
    """Types of instruction performance metrics"""

    RESPONSE_QUALITY = "response_quality"
    USER_SATISFACTION = "user_satisfaction"
    TASK_COMPLETION = "task_completion"
    RESPONSE_TIME = "response_time"
    TOKEN_EFFICIENCY = "token_efficiency"
    ERROR_RATE = "error_rate"
    INSTRUCTION_EFFECTIVENESS = "instruction_effectiveness"


class ABTestStatus(Enum):
    """A/B test status values"""

    PLANNING = "planning"
    ACTIVE = "active"
    PAUSED = "paused"
    COMPLETED = "completed"
    CANCELLED = "cancelled"


@dataclass
class InstructionMetric:
    """Individual instruction performance metric"""

    metric_id: str
    instruction_id: str
    metric_type: InstructionMetricType
    value: float
    timestamp: datetime
    context: Dict[str, Any]
    session_id: Optional[str] = None
    user_id: Optional[str] = None
    framework: Optional[str] = None
    task_type: Optional[str] = None


@dataclass
class InstructionPerformanceData:
    """Aggregated performance data for an instruction"""

    instruction_id: str
    instruction_hash: str
    total_uses: int
    avg_response_quality: float
    avg_user_satisfaction: float
    avg_response_time: float
    avg_token_efficiency: float
    error_rate: float
    effectiveness_score: float
    last_updated: datetime
    sample_size: int


@dataclass
class ABTestConfig:
    """Configuration for instruction A/B test"""

    test_id: str
    test_name: str
    instruction_a_id: str
    instruction_b_id: str
    traffic_split: float
    start_date: datetime
    end_date: Optional[datetime]
    minimum_sample_size: int
    confidence_threshold: float
    success_metrics: List[InstructionMetricType]
    target_improvement: float
    status: ABTestStatus
    metadata: Dict[str, Any]


@dataclass
class ABTestResult:
    """Results from an A/B test"""

    test_id: str
    instruction_a_performance: InstructionPerformanceData
    instruction_b_performance: InstructionPerformanceData
    statistical_significance: bool
    confidence_level: float
    improvement_percentage: float
    winner: Optional[str]
    recommendation: str
    detailed_analysis: Dict[str, Any]


class InstructionPerformanceMonitor:
    """Monitors and analyzes instruction performance"""

    def __init__(
        self, max_metrics_history: int = 10000, persistence: Optional[InstructionPersistence] = None
    ) -> None:
        self.persistence = persistence or MemoryPersistence()
        self.metrics_history: deque = deque(maxlen=max_metrics_history)
        self.performance_cache: Dict[str, InstructionPerformanceData] = {}
        self.active_ab_tests: Dict[str, ABTestConfig] = {}
        self.ab_test_results: Dict[str, ABTestResult] = {}
        self.instruction_registry: Dict[str, Dict[str, Any]] = {}
        self.short_term_window = timedelta(hours=1)
        self.medium_term_window = timedelta(days=1)
        self.long_term_window = timedelta(days=7)
        self._load_data()

    def register_instruction(
        self,
        instruction_id: str,
        instruction_content: str,
        instruction_type: str,
        framework: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> str:
        """
        Register an instruction for monitoring

        Args:
            instruction_id: Unique identifier for the instruction
            instruction_content: The actual instruction content
            instruction_type: Type of instruction (assessment, evidence, etc.)
            framework: Associated framework if any
            metadata: Additional metadata

        Returns:
            Instruction hash for tracking variations
        """
        instruction_hash = self._hash_instruction(instruction_content)
        self.instruction_registry[instruction_id] = {
            "content": instruction_content,
            "hash": instruction_hash,
            "type": instruction_type,
            "framework": framework,
            "metadata": metadata or {},
            "created_at": datetime.now(),
            "version": 1,
        }
        logger.info("Registered instruction %s with hash %s" % (instruction_id, instruction_hash))
        return instruction_hash

    def record_metric(
        self,
        instruction_id: str,
        metric_type: InstructionMetricType,
        value: float,
        context: Dict[str, Any],
        session_id: Optional[str] = None,
        user_id: Optional[str] = None,
    ) -> None:
        """
        Record a performance metric for an instruction

        Args:
            instruction_id: ID of the instruction being measured
            metric_type: Type of metric being recorded
            value: Metric value
            context: Additional context information
            session_id: Session identifier
            user_id: User identifier
        """
        metric = InstructionMetric(
            metric_id=str(uuid4()),
            instruction_id=instruction_id,
            metric_type=metric_type,
            value=value,
            timestamp=datetime.now(),
            context=context,
            session_id=session_id,
            user_id=user_id,
            framework=context.get("framework"),
            task_type=context.get("task_type"),
        )
        self.metrics_history.append(metric)
        self._update_performance_cache(instruction_id)
        self._update_ab_test_metrics(metric)

    def get_instruction_performance(
        self, instruction_id: str, time_window: Optional[timedelta] = None
    ) -> Optional[InstructionPerformanceData]:
        """
        Get performance data for a specific instruction

        Args:
            instruction_id: Instruction to analyze
            time_window: Time window for analysis (default: all time)

        Returns:
            Performance data or None if not found
        """
        if time_window:
            return self._calculate_performance_for_window(instruction_id, time_window)
        return self.performance_cache.get(instruction_id)

    def compare_instructions(
        self, instruction_a_id: str, instruction_b_id: str, time_window: Optional[timedelta] = None
    ) -> Dict[str, Any]:
        """
        Compare performance between two instructions

        Args:
            instruction_a_id: First instruction to compare
            instruction_b_id: Second instruction to compare
            time_window: Time window for comparison

        Returns:
            Comparison analysis
        """
        perf_a = self.get_instruction_performance(instruction_a_id, time_window)
        perf_b = self.get_instruction_performance(instruction_b_id, time_window)
        if not perf_a or not perf_b:
            return {"error": "Insufficient data for comparison"}
        comparison = {
            "instruction_a": asdict(perf_a),
            "instruction_b": asdict(perf_b),
            "differences": {
                "response_quality": perf_b.avg_response_quality - perf_a.avg_response_quality,
                "user_satisfaction": perf_b.avg_user_satisfaction - perf_a.avg_user_satisfaction,
                "response_time": perf_b.avg_response_time - perf_a.avg_response_time,
                "token_efficiency": perf_b.avg_token_efficiency - perf_a.avg_token_efficiency,
                "error_rate": perf_b.error_rate - perf_a.error_rate,
                "effectiveness": perf_b.effectiveness_score - perf_a.effectiveness_score,
            },
            "statistical_significance": self._calculate_statistical_significance(perf_a, perf_b),
            "recommendation": self._generate_comparison_recommendation(perf_a, perf_b),
        }
        return comparison

    def _generate_comparison_recommendation(
        self, perf_a: InstructionPerformanceData, perf_b: InstructionPerformanceData
    ) -> str:
        """Generate a recommendation based on performance comparison."""
        if perf_b.effectiveness_score > perf_a.effectiveness_score:
            return (
                f"Instruction B shows better overall effectiveness ({perf_b.effectiveness_score:.2f} vs {perf_a.effectiveness_score:.2f}).",
            )
        elif perf_a.effectiveness_score > perf_b.effectiveness_score:
            return (
                f"Instruction A shows better overall effectiveness ({perf_a.effectiveness_score:.2f} vs {perf_b.effectiveness_score:.2f}).",
            )
        else:
            return "Both instructions have similar performance."

    def start_ab_test(
        self,
        test_name: str,
        instruction_a_id: str,
        instruction_b_id: str,
        traffic_split: float = 0.5,
        duration_days: int = 7,
        minimum_sample_size: int = 100,
        confidence_threshold: float = 0.95,
        success_metrics: Optional[List[InstructionMetricType]] = None,
        target_improvement: float = 0.05,
    ) -> str:
        """
        Start an A/B test between two instructions

        Args:
            test_name: Name for the test
            instruction_a_id: Control instruction
            instruction_b_id: Variant instruction
            traffic_split: Percentage of traffic for instruction A
            duration_days: Test duration in days
            minimum_sample_size: Minimum samples needed
            confidence_threshold: Statistical confidence required
            success_metrics: Metrics to optimize for
            target_improvement: Minimum improvement threshold

        Returns:
            Test ID
        """
        test_id = str(uuid4())
        if success_metrics is None:
            success_metrics = [
                InstructionMetricType.RESPONSE_QUALITY,
                InstructionMetricType.USER_SATISFACTION,
                InstructionMetricType.INSTRUCTION_EFFECTIVENESS,
            ]
        test_config = ABTestConfig(
            test_id=test_id,
            test_name=test_name,
            instruction_a_id=instruction_a_id,
            instruction_b_id=instruction_b_id,
            traffic_split=traffic_split,
            start_date=datetime.now(),
            end_date=datetime.now() + timedelta(days=duration_days),
            minimum_sample_size=minimum_sample_size,
            confidence_threshold=confidence_threshold,
            success_metrics=success_metrics,
            target_improvement=target_improvement,
            status=ABTestStatus.ACTIVE,
            metadata={},
        )
        self.active_ab_tests[test_id] = test_config
        logger.info("Started A/B test %s: %s" % (test_id, test_name))
        return test_id

    def get_ab_test_results(self, test_id: str) -> Optional[ABTestResult]:
        """
        Get results for a specific A/B test

        Args:
            test_id: Test identifier

        Returns:
            Test results or None if not found
        """
        return self.ab_test_results.get(test_id)

    def get_instruction_recommendations(
        self,
        instruction_type: str,
        framework: Optional[str] = None,
        task_complexity: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        """
        Get recommendations for instruction optimization

        Args:
            instruction_type: Type of instruction
            framework: Framework context
            task_complexity: Task complexity level

        Returns:
            List of optimization recommendations
        """
        recommendations = []
        matching_instructions = self._find_matching_instructions(
            instruction_type, framework, task_complexity
        )
        for instruction_id in matching_instructions:
            perf = self.get_instruction_performance(instruction_id)
            if perf and perf.sample_size >= 10:
                if perf.avg_response_quality < 0.7:
                    recommendations.append(
                        {
                            "instruction_id": instruction_id,
                            "type": "quality_improvement",
                            "priority": "high",
                            "recommendation": "Consider enhancing instruction clarity and specificity",
                            "current_score": perf.avg_response_quality,
                            "target_score": 0.8,
                        }
                    )
                if perf.avg_response_time > DEFAULT_TIMEOUT:
                    recommendations.append(
                        {
                            "instruction_id": instruction_id,
                            "type": "performance_optimization",
                            "priority": "medium",
                            "recommendation": "Optimize instruction for faster response times",
                            "current_time": perf.avg_response_time,
                            "target_time": 20.0,
                        }
                    )
                if perf.error_rate > 0.05:
                    recommendations.append(
                        {
                            "instruction_id": instruction_id,
                            "type": "error_reduction",
                            "priority": "high",
                            "recommendation": "Review instruction for error-prone patterns",
                            "current_error_rate": perf.error_rate,
                            "target_error_rate": 0.02,
                        }
                    )
        return recommendations

    def generate_performance_report(
        self, time_window: Optional[timedelta] = None, include_ab_tests: bool = True
    ) -> Dict[str, Any]:
        """
        Generate comprehensive performance report

        Args:
            time_window: Time period for report
            include_ab_tests: Whether to include A/B test data

        Returns:
            Performance report
        """
        if time_window is None:
            time_window = self.long_term_window
        report = {
            "report_timestamp": datetime.now().isoformat(),
            "time_window": str(time_window),
            "summary": self._generate_summary_stats(time_window),
            "top_performing_instructions": self._get_top_performers(time_window),
            "underperforming_instructions": self._get_underperformers(time_window),
            "recommendations": self.get_instruction_recommendations("all"),
            "trends": self._analyze_performance_trends(time_window),
        }
        if include_ab_tests:
            report["ab_tests"] = {
                "active_tests": len(self.active_ab_tests),
                "completed_tests": len(self.ab_test_results),
                "recent_results": self._get_recent_ab_results(),
            }
        return report

    def _hash_instruction(self, content: str) -> str:
        """Generate hash for instruction content"""
        import hashlib

        return hashlib.sha256(content.encode()).hexdigest()[:16]

    def _update_performance_cache(self, instruction_id: str) -> None:
        """Update cached performance data for an instruction"""
        metrics = [m for m in self.metrics_history if m.instruction_id == instruction_id]
        if not metrics:
            return
        quality_scores = [
            m.value for m in metrics if m.metric_type == InstructionMetricType.RESPONSE_QUALITY
        ]
        satisfaction_scores = [
            m.value for m in metrics if m.metric_type == InstructionMetricType.USER_SATISFACTION
        ]
        response_times = [
            m.value for m in metrics if m.metric_type == InstructionMetricType.RESPONSE_TIME
        ]
        token_efficiency = [
            m.value for m in metrics if m.metric_type == InstructionMetricType.TOKEN_EFFICIENCY
        ]
        error_metrics = [
            m.value for m in metrics if m.metric_type == InstructionMetricType.ERROR_RATE
        ]
        effectiveness = [
            m.value
            for m in metrics
            if m.metric_type == InstructionMetricType.INSTRUCTION_EFFECTIVENESS
        ]
        instruction_info = self.instruction_registry.get(instruction_id, {})
        performance = InstructionPerformanceData(
            instruction_id=instruction_id,
            instruction_hash=instruction_info.get("hash", "unknown"),
            total_uses=len(metrics),
            avg_response_quality=statistics.mean(quality_scores) if quality_scores else 0.0,
            avg_user_satisfaction=statistics.mean(satisfaction_scores)
            if satisfaction_scores
            else 0.0,
            avg_response_time=statistics.mean(response_times) if response_times else 0.0,
            avg_token_efficiency=statistics.mean(token_efficiency) if token_efficiency else 0.0,
            error_rate=statistics.mean(error_metrics) if error_metrics else 0.0,
            effectiveness_score=statistics.mean(effectiveness) if effectiveness else 0.0,
            last_updated=datetime.now(),
            sample_size=len(metrics),
        )
        self.performance_cache[instruction_id] = performance

    def _update_ab_test_metrics(self, metric: InstructionMetric) -> None:
        """Update A/B test data with new metric"""
        for test_id, test_config in self.active_ab_tests.items():
            if metric.instruction_id in [
                test_config.instruction_a_id,
                test_config.instruction_b_id,
            ] and self._should_complete_ab_test(test_config):
                self._complete_ab_test(test_id)

    def _should_complete_ab_test(self, test_config: ABTestConfig) -> bool:
        """Check if A/B test should be completed"""
        if test_config.end_date and datetime.now() > test_config.end_date:
            return True
        perf_a = self.get_instruction_performance(test_config.instruction_a_id)
        perf_b = self.get_instruction_performance(test_config.instruction_b_id)
        if perf_a and perf_b:
            min_samples = min(perf_a.sample_size, perf_b.sample_size)
            return min_samples >= test_config.minimum_sample_size
        return False

    def _complete_ab_test(self, test_id: str) -> None:
        """Complete an A/B test and generate results"""
        test_config = self.active_ab_tests.get(test_id)
        if not test_config:
            return
        perf_a = self.get_instruction_performance(test_config.instruction_a_id)
        perf_b = self.get_instruction_performance(test_config.instruction_b_id)
        if not perf_a or not perf_b:
            logger.error("Insufficient data to complete A/B test %s" % test_id)
            return
        significance = self._calculate_statistical_significance(perf_a, perf_b)
        winner = None
        improvement = 0.0
        if significance["significant"]:
            primary_metric = test_config.success_metrics[0]
            if primary_metric == InstructionMetricType.RESPONSE_QUALITY:
                improvement = (
                    perf_b.avg_response_quality - perf_a.avg_response_quality
                ) / perf_a.avg_response_quality
                winner = "B" if perf_b.avg_response_quality > perf_a.avg_response_quality else "A"
            elif primary_metric == InstructionMetricType.USER_SATISFACTION:
                improvement = (
                    perf_b.avg_user_satisfaction - perf_a.avg_user_satisfaction
                ) / perf_a.avg_user_satisfaction
                winner = "B" if perf_b.avg_user_satisfaction > perf_a.avg_user_satisfaction else "A"
        result = ABTestResult(
            test_id=test_id,
            instruction_a_performance=perf_a,
            instruction_b_performance=perf_b,
            statistical_significance=significance["significant"],
            confidence_level=significance["confidence"],
            improvement_percentage=improvement * 100,
            winner=winner,
            recommendation=self._generate_ab_test_recommendation(
                winner, improvement, test_config.target_improvement
            ),
            detailed_analysis=significance,
        )
        self.ab_test_results[test_id] = result
        test_config.status = ABTestStatus.COMPLETED
        logger.info("Completed A/B test %s with winner: %s" % (test_id, winner))

    def _calculate_statistical_significance(
        self, perf_a: InstructionPerformanceData, perf_b: InstructionPerformanceData
    ) -> Dict[str, Any]:
        """Calculate statistical significance between two performance datasets"""
        sample_size_a = perf_a.sample_size
        sample_size_b = perf_b.sample_size
        min_sample_size = 30
        if sample_size_a < min_sample_size or sample_size_b < min_sample_size:
            return {
                "significant": False,
                "confidence": 0.0,
                "reason": "Insufficient sample size",
                "required_samples": min_sample_size,
            }
        quality_diff = abs(perf_b.avg_response_quality - perf_a.avg_response_quality)
        satisfaction_diff = abs(perf_b.avg_user_satisfaction - perf_a.avg_user_satisfaction)
        combined_samples = sample_size_a + sample_size_b
        confidence = min(0.99, (quality_diff + satisfaction_diff) * (combined_samples / 200))
        return {
            "significant": confidence > HIGH_CONFIDENCE_THRESHOLD,
            "confidence": confidence,
            "quality_difference": quality_diff,
            "satisfaction_difference": satisfaction_diff,
            "sample_sizes": {"a": sample_size_a, "b": sample_size_b},
        }

    def _generate_ab_test_recommendation(
        self, winner: Optional[str], improvement: float, target_improvement: float
    ) -> str:
        """Generate recommendation based on A/B test results"""
        if not winner:
            return (
                "No statistically significant difference found. Consider running test longer or with larger sample size.",
            )
        if improvement >= target_improvement:
            return (
                f"Instruction {winner} shows significant improvement ({improvement:.1%}). Recommend implementing.",
            )
        else:
            return (
                f"Instruction {winner} shows improvement ({improvement:.1%}) but below target ({target_improvement:.1%}). Consider further optimization.",
            )

    def _calculate_performance_for_window(
        self, instruction_id: str, time_window: timedelta
    ) -> Optional[InstructionPerformanceData]:
        """Calculate performance metrics for a specific time window"""
        cutoff_time = datetime.now() - time_window
        metrics = [
            m
            for m in self.metrics_history
            if m.instruction_id == instruction_id and m.timestamp >= cutoff_time
        ]
        if not metrics:
            return None
        quality_scores = [
            m.value for m in metrics if m.metric_type == InstructionMetricType.RESPONSE_QUALITY
        ]
        satisfaction_scores = [
            m.value for m in metrics if m.metric_type == InstructionMetricType.USER_SATISFACTION
        ]
        response_times = [
            m.value for m in metrics if m.metric_type == InstructionMetricType.RESPONSE_TIME
        ]
        token_efficiency = [
            m.value for m in metrics if m.metric_type == InstructionMetricType.TOKEN_EFFICIENCY
        ]
        error_metrics = [
            m.value for m in metrics if m.metric_type == InstructionMetricType.ERROR_RATE
        ]
        effectiveness = [
            m.value
            for m in metrics
            if m.metric_type == InstructionMetricType.INSTRUCTION_EFFECTIVENESS
        ]
        instruction_info = self.instruction_registry.get(instruction_id, {})
        return InstructionPerformanceData(
            instruction_id=instruction_id,
            instruction_hash=instruction_info.get("hash", "unknown"),
            total_uses=len(metrics),
            avg_response_quality=statistics.mean(quality_scores) if quality_scores else 0.0,
            avg_user_satisfaction=statistics.mean(satisfaction_scores)
            if satisfaction_scores
            else 0.0,
            avg_response_time=statistics.mean(response_times) if response_times else 0.0,
            avg_token_efficiency=statistics.mean(token_efficiency) if token_efficiency else 0.0,
            error_rate=statistics.mean(error_metrics) if error_metrics else 0.0,
            effectiveness_score=statistics.mean(effectiveness) if effectiveness else 0.0,
            last_updated=datetime.now(),
            sample_size=len(metrics),
        )

    def _find_matching_instructions(
        self, instruction_type: str, framework: Optional[str], task_complexity: Optional[str]
    ) -> List[str]:
        """Find instructions matching the given criteria"""
        matching = []
        for instruction_id, info in self.instruction_registry.items():
            if (instruction_type == "all" or info.get("type") == instruction_type) and (
                not framework or info.get("framework") == framework
            ):
                matching.append(instruction_id)
        return matching

    def _generate_summary_stats(self, time_window: timedelta) -> Dict[str, Any]:
        """Generate summary statistics for the time window"""
        cutoff_time = datetime.now() - time_window
        recent_metrics = [m for m in self.metrics_history if m.timestamp >= cutoff_time]
        if not recent_metrics:
            return {"no_data": True}
        return {
            "total_interactions": len(recent_metrics),
            "unique_instructions": len({m.instruction_id for m in recent_metrics}),
            "avg_response_quality": statistics.mean(
                [
                    m.value
                    for m in recent_metrics
                    if m.metric_type == InstructionMetricType.RESPONSE_QUALITY
                ]
            )
            if any(m.metric_type == InstructionMetricType.RESPONSE_QUALITY for m in recent_metrics)
            else 0,
            "avg_user_satisfaction": statistics.mean(
                [
                    m.value
                    for m in recent_metrics
                    if m.metric_type == InstructionMetricType.USER_SATISFACTION
                ]
            )
            if any(m.metric_type == InstructionMetricType.USER_SATISFACTION for m in recent_metrics)
            else 0,
            "overall_error_rate": len(
                [
                    m
                    for m in recent_metrics
                    if m.metric_type == InstructionMetricType.ERROR_RATE and m.value > 0
                ]
            )
            / len(recent_metrics)
            if recent_metrics
            else 0,
        }

    def _get_top_performers(self, time_window: timedelta, limit: int = 5) -> List[Dict[str, Any]]:
        """Get top performing instructions"""
        performers = []
        for instruction_id in self.instruction_registry:
            perf = self._calculate_performance_for_window(instruction_id, time_window)
            if perf and perf.sample_size >= DEFAULT_RETRIES:
                performers.append(
                    {
                        "instruction_id": instruction_id,
                        "effectiveness_score": perf.effectiveness_score,
                        "response_quality": perf.avg_response_quality,
                        "user_satisfaction": perf.avg_user_satisfaction,
                        "sample_size": perf.sample_size,
                    }
                )
        return sorted(performers, key=lambda x: x["effectiveness_score"], reverse=True)[:limit]

    def _get_underperformers(self, time_window: timedelta, limit: int = 5) -> List[Dict[str, Any]]:
        """Get underperforming instructions"""
        performers = []
        for instruction_id in self.instruction_registry:
            perf = self._calculate_performance_for_window(instruction_id, time_window)
            if perf and perf.sample_size >= DEFAULT_RETRIES:
                performers.append(
                    {
                        "instruction_id": instruction_id,
                        "effectiveness_score": perf.effectiveness_score,
                        "response_quality": perf.avg_response_quality,
                        "user_satisfaction": perf.avg_user_satisfaction,
                        "error_rate": perf.error_rate,
                        "sample_size": perf.sample_size,
                    }
                )
        return sorted(performers, key=lambda x: x["effectiveness_score"])[:limit]

    def _analyze_performance_trends(self, time_window: timedelta) -> Dict[str, Any]:
        """Analyze performance trends over time"""
        cutoff_time = datetime.now() - time_window
        recent_metrics = [m for m in self.metrics_history if m.timestamp >= cutoff_time]
        if len(recent_metrics) < 10:
            return {"insufficient_data": True}
        time_buckets = 5
        bucket_size = time_window / time_buckets
        buckets = []
        for i in range(time_buckets):
            bucket_start = cutoff_time + bucket_size * i
            bucket_end = bucket_start + bucket_size
            bucket_metrics = [m for m in recent_metrics if bucket_start <= m.timestamp < bucket_end]
            if bucket_metrics:
                quality_scores = [
                    m.value
                    for m in bucket_metrics
                    if m.metric_type == InstructionMetricType.RESPONSE_QUALITY
                ]
                buckets.append(
                    {
                        "period": f"bucket_{i}",
                        "avg_quality": statistics.mean(quality_scores) if quality_scores else 0,
                        "sample_size": len(bucket_metrics),
                    }
                )
        return {
            "trend_buckets": buckets,
            "overall_trend": "improving"
            if len(buckets) >= 2 and buckets[-1]["avg_quality"] > buckets[0]["avg_quality"]
            else "stable",
        }

    def _get_recent_ab_results(self, limit: int = 3) -> List[Dict[str, Any]]:
        """Get recent A/B test results"""
        recent_results = []
        for test_id, result in self.ab_test_results.items():
            recent_results.append(
                {
                    "test_id": test_id,
                    "winner": result.winner,
                    "improvement": result.improvement_percentage,
                    "confidence": result.confidence_level,
                    "recommendation": result.recommendation,
                }
            )
        return recent_results[:limit]

    def _load_data(self) -> None:
        """Load existing data from persistence"""
        try:
            metrics = self.persistence.load_metrics()
            self.metrics_history.extend(metrics)
            self.performance_cache = self.persistence.load_performance_data()
            logger.info(
                "Loaded %s metrics and %s performance records"
                % (len(metrics), len(self.performance_cache))
            )
        except Exception as e:
            logger.error("Failed to load instruction data: %s" % e)

    def _save_data(self) -> None:
        """Save current data to persistence"""
        try:
            self.persistence.save_metrics(list(self.metrics_history))
            self.persistence.save_performance_data(self.performance_cache)
            logger.debug("Saved instruction monitoring data")
        except Exception as e:
            logger.error("Failed to save instruction data: %s" % e)


instruction_monitor = InstructionPerformanceMonitor(
    persistence=FilePersistence()
    if os.getenv("ENVIRONMENT") == "production"
    else MemoryPersistence()
)


def get_instruction_monitor() -> InstructionPerformanceMonitor:
    """Get the global instruction performance monitor instance"""
    return instruction_monitor
