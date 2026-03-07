"""Evaluation pipeline for AI quality assessment."""

import asyncio
from datetime import datetime, timezone
from typing import List, Dict, Any, Optional, Callable, Tuple
from dataclasses import dataclass, field
from enum import Enum
import hashlib
from pathlib import Path
import numpy as np
from scipy import stats
import logging

logger = logging.getLogger(__name__)


class TaskStatus(Enum):
    """Task execution status."""

    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    TIMEOUT = "timeout"


@dataclass
class PipelineConfig:
    """Pipeline configuration."""

    parallel_tasks: int = 4
    timeout_seconds: int = 300
    retry_attempts: int = 3
    cache_results: bool = True
    regression_threshold: float = 0.1
    cache_dir: Optional[Path] = None

    def __post_init__(self) -> None:
        """Validate configuration."""
        if self.parallel_tasks <= 0:
            raise ValueError("parallel_tasks must be positive")
        if self.timeout_seconds < 0:
            raise ValueError("timeout_seconds must be non-negative")
        if not 0 <= self.regression_threshold <= 1:
            raise ValueError("regression_threshold must be between 0 and 1")
        if self.cache_dir is None:
            self.cache_dir = Path(".evaluation_cache")


@dataclass
class EvaluationTask:
    """Individual evaluation task."""

    task_id: str
    task_type: str
    dataset_id: str
    metrics: List[str] = field(default_factory=list)
    priority: int = 0
    status: str = field(default="pending")
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    result: Optional[Dict[str, Any]] = None
    error: Optional[str] = None

    def start(self) -> None:
        """Mark task as started."""
        self.status = TaskStatus.RUNNING.value
        self.started_at = datetime.now(timezone.utc)

    def complete(self, result: Dict[str, Any]) -> None:
        """Mark task as completed."""
        self.status = TaskStatus.COMPLETED.value
        self.completed_at = datetime.now(timezone.utc)
        self.result = result

    def fail(self, error: str) -> None:
        """Mark task as failed."""
        self.status = TaskStatus.FAILED.value
        self.completed_at = datetime.now(timezone.utc)
        self.error = error


@dataclass
class EvaluationResult:
    """Result of an evaluation task."""

    task_id: str
    success: bool
    metrics: Dict[str, float] = field(default_factory=dict)
    error: Optional[str] = None
    duration: float = 0.0
    timestamp: datetime = field(default_factory=datetime.utcnow)
    weight: float = 1.0


class EvaluationPipeline:
    """Core evaluation pipeline."""

    def __init__(self, config: PipelineConfig) -> None:
        self.config = config
        self.evaluators: Dict[str, Callable] = {}
        self._cache: Dict[str, EvaluationResult] = {}
        self._semaphore = asyncio.Semaphore(config.parallel_tasks)

    def register_evaluator(self, task_type: str, evaluator: Callable) -> None:
        """Register an evaluator function for a task type."""
        self.evaluators[task_type] = evaluator

    async def execute_task(self, task: EvaluationTask) -> EvaluationResult:
        """Execute a single evaluation task."""
        start_time = datetime.now(timezone.utc)
        cache_key = self._get_cache_key(task)
        if self.config.cache_results and cache_key in self._cache:
            logger.info("Using cached result for task %s" % task.task_id)
            return self._cache[cache_key]
        task.start()
        try:
            if task.task_type not in self.evaluators:
                raise ValueError(f"No evaluator registered for type: {task.task_type}")
            evaluator = self.evaluators[task.task_type]
            result_metrics = await self._execute_with_retry(
                evaluator, task, self.config.retry_attempts
            )
            task.complete(result_metrics)
            result = EvaluationResult(
                task_id=task.task_id,
                success=True,
                metrics=result_metrics,
                duration=(datetime.now(timezone.utc) - start_time).total_seconds(),
            )
            if self.config.cache_results:
                self._cache[cache_key] = result
            return result
        except asyncio.TimeoutError:
            error_msg = (f"Task {task.task_id} exceeded timeout of {self.config.timeout_seconds}s",)
            task.fail(error_msg)
            return EvaluationResult(
                task_id=task.task_id,
                success=False,
                error=error_msg,
                duration=(datetime.now(timezone.utc) - start_time).total_seconds(),
            )
        except Exception as e:
            error_msg = f"Task {task.task_id} failed: {str(e)}"
            task.fail(error_msg)
            return EvaluationResult(
                task_id=task.task_id,
                success=False,
                error=error_msg,
                duration=(datetime.now(timezone.utc) - start_time).total_seconds(),
            )

    async def _execute_with_retry(
        self, evaluator: Callable, task: EvaluationTask, attempts: int
    ) -> Dict[str, Any]:
        """Execute evaluator with retry logic."""
        last_error = None
        for attempt in range(attempts):
            try:
                result = await asyncio.wait_for(
                    evaluator(task), timeout=self.config.timeout_seconds
                )
                return result
            except asyncio.TimeoutError:
                raise
            except Exception as e:
                last_error = e
                if attempt < attempts - 1:
                    logger.warning(
                        "Attempt %s failed for task %s: %s" % (attempt + 1, task.task_id, e)
                    )
                    await asyncio.sleep(2**attempt)
        raise last_error

    async def execute_parallel(self, tasks: List[EvaluationTask]) -> List[EvaluationResult]:
        """Execute multiple tasks in parallel."""

        async def _execute_with_semaphore(task):
            async with self._semaphore:
                return await self.execute_task(task)

        results = await asyncio.gather(
            *[_execute_with_semaphore(task) for task in tasks], return_exceptions=True
        )
        final_results = []
        for i, result in enumerate(results):
            if isinstance(result, Exception):
                final_results.append(
                    EvaluationResult(task_id=tasks[i].task_id, success=False, error=str(result))
                )
            else:
                final_results.append(result)
        return final_results

    def _get_cache_key(self, task: EvaluationTask) -> str:
        """Generate cache key for task."""
        key_data = f"{task.task_type}:{task.dataset_id}:{sorted(task.metrics)}"
        # Use SHA-256 instead of MD5 for security compliance, truncated for cache key compatibility
        return hashlib.sha256(key_data.encode()).hexdigest()[:32]

    def clear_cache(self) -> None:
        """Clear result cache."""
        self._cache.clear()


class MetricAggregator:
    """Aggregates metrics from multiple evaluation results."""

    def aggregate(self, results: List[EvaluationResult], weighted: bool = False) -> Dict[str, Any]:
        """Aggregate metrics from evaluation results."""
        if not results:
            return {}
        successful = [r for r in results if r.success]
        failed = [r for r in results if not r.success]
        aggregated = {
            "_success_rate": len(successful) / len(results) if results else 0,
            "_total_results": len(results),
            "_successful_results": len(successful),
            "_failed_results": len(failed),
        }
        if not successful:
            return aggregated
        metric_values = {}
        metric_weights = {}
        for result in successful:
            for metric, value in result.metrics.items():
                if metric not in metric_values:
                    metric_values[metric] = []
                    metric_weights[metric] = []
                metric_values[metric].append(value)
                metric_weights[metric].append(result.weight)
        for metric, values in metric_values.items():
            values_array = np.array(values)
            weights_array = np.array(metric_weights[metric])
            aggregated[metric] = {
                "mean": float(np.mean(values_array)),
                "std": float(np.std(values_array)),
                "min": float(np.min(values_array)),
                "max": float(np.max(values_array)),
                "median": float(np.median(values_array)),
                "count": len(values),
            }
            if weighted and len(values) > 1:
                weighted_mean = np.average(values_array, weights=weights_array)
                aggregated[metric]["weighted_mean"] = float(weighted_mean)
        return aggregated


class RegressionDetector:
    """Detects performance regressions."""

    def __init__(self, threshold: float = 0.1) -> None:
        self.threshold = threshold

    def detect(self, baseline: Dict[str, float], current: Dict[str, float]) -> List[Dict[str, Any]]:
        """Detect regressions between baseline and current metrics."""
        regressions = []
        for metric, baseline_value in baseline.items():
            if metric in current:
                current_value = current[metric]
                if baseline_value != 0:
                    change = (current_value - baseline_value) / baseline_value
                else:
                    change = float("inf") if current_value != 0 else 0
                if change < -self.threshold:
                    regressions.append(
                        {
                            "metric": metric,
                            "baseline": baseline_value,
                            "current": current_value,
                            "change": change,
                            "threshold": self.threshold,
                        }
                    )
        return regressions

    def analyze_trend(self, history: List[Dict[str, Any]], metric: str) -> Dict[str, Any]:
        """Analyze trend for a specific metric over time."""
        if len(history) < 2:
            return {"direction": "insufficient_data"}
        values = []
        timestamps = []
        for entry in history:
            if metric in entry:
                values.append(entry[metric])
                timestamps.append(entry.get("timestamp", datetime.now(timezone.utc)))
        if len(values) < 2:
            return {"direction": "insufficient_data"}
        x = np.arange(len(values))
        slope, intercept, r_value, p_value, std_err = stats.linregress(x, values)
        if slope > 0.01:
            direction = "improving"
        elif slope < -0.01:
            direction = "declining"
        else:
            direction = "stable"
        consecutive_declines = 0
        for i in range(1, len(values)):
            if values[i] < values[i - 1]:
                consecutive_declines += 1
        return {
            "direction": direction,
            "slope": float(slope),
            "r_squared": float(r_value**2),
            "p_value": float(p_value),
            "consistent": consecutive_declines == len(values) - 1
            if direction == "declining"
            else False,
        }


class BaselineComparator:
    """Compares evaluation results against baselines."""

    def compare(
        self,
        baseline: Dict[str, Dict[str, float]],
        current: Dict[str, Dict[str, float]],
        test_significance: bool = False,
        confidence_level: float = 0.95,
    ) -> Dict[str, Any]:
        """Compare current results against baseline."""
        comparison = {}
        for metric in baseline:
            if metric not in current:
                continue
            baseline_stats = baseline[metric]
            current_stats = current[metric]
            baseline_mean = baseline_stats.get("mean", 0)
            current_mean = current_stats.get("mean", 0)
            if baseline_mean != 0:
                change_pct = (current_mean - baseline_mean) / baseline_mean * 100
            else:
                change_pct = float("inf") if current_mean != 0 else 0
            comparison[metric] = {
                "baseline": baseline_mean,
                "current": current_mean,
                "change": current_mean - baseline_mean,
                "change_pct": change_pct,
                "improved": current_mean > baseline_mean,
            }
            if test_significance:
                p_value = self._test_significance(
                    baseline_stats,
                    current_stats,
                )
                comparison[metric]["p_value"] = p_value
                comparison[metric]["significant"] = p_value < 1 - confidence_level
            if confidence_level and "std" in current_stats and "n" in current_stats:
                ci_lower, ci_upper = self._confidence_interval(
                    current_mean - baseline_mean,
                    baseline_stats.get("std", 0),
                    current_stats["std"],
                    baseline_stats.get("n", 1),
                    current_stats["n"],
                    confidence_level,
                )
                comparison[metric]["ci_lower"] = ci_lower
                comparison[metric]["ci_upper"] = ci_upper
        return comparison

    def _test_significance(self, baseline: Dict[str, float], current: Dict[str, float]) -> float:
        """Perform statistical significance test."""
        baseline_mean = baseline.get("mean", 0)
        baseline_std = baseline.get("std", 0)
        baseline_n = baseline.get("n", 1)
        current_mean = current.get("mean", 0)
        current_std = current.get("std", 0)
        current_n = current.get("n", 1)
        se = np.sqrt(baseline_std**2 / baseline_n + current_std**2 / current_n)
        if se == 0:
            return 1.0
        t_stat = (current_mean - baseline_mean) / se
        df = (baseline_std**2 / baseline_n + current_std**2 / current_n) ** 2 / (
            (baseline_std**2 / baseline_n) ** 2 / (baseline_n - 1)
            + (current_std**2 / current_n) ** 2 / (current_n - 1)
        )
        p_value = 2 * (1 - stats.t.cdf(abs(t_stat), df))
        return float(p_value)

    def _confidence_interval(
        self, diff: float, std1: float, std2: float, n1: int, n2: int, confidence: float
    ) -> Tuple[float, float]:
        """Calculate confidence interval for difference."""
        se = np.sqrt(std1**2 / n1 + std2**2 / n2)
        alpha = 1 - confidence
        df = n1 + n2 - 2
        t_critical = stats.t.ppf(1 - alpha / 2, df)
        margin = t_critical * se
        return diff - margin, diff + margin


class PipelineOrchestrator:
    """Orchestrates the evaluation pipeline."""

    def __init__(self, config: PipelineConfig) -> None:
        self.config = config
        self.pipeline = EvaluationPipeline(config)
        self.aggregator = MetricAggregator()
        self.regression_detector = RegressionDetector(config.regression_threshold)
        self.comparator = BaselineComparator()
        self.baseline: Optional[Dict[str, Any]] = None
        self._scheduled_tasks: List[asyncio.Task] = []

    def set_baseline(self, baseline: Dict[str, Any]) -> None:
        """Set baseline metrics for comparison."""
        self.baseline = baseline

    async def run_evaluation(self, tasks: List[EvaluationTask]) -> Dict[str, Any]:
        """Run complete evaluation workflow."""
        start_time = datetime.now(timezone.utc)
        results = await self.pipeline.execute_parallel(tasks)
        aggregated = self.aggregator.aggregate(results)
        evaluation_result = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "summary": {
                "total_tasks": len(tasks),
                "successful_tasks": sum(1 for r in results if r.success),
                "failed_tasks": sum(1 for r in results if not r.success),
                "duration": (datetime.now(timezone.utc) - start_time).total_seconds(),
            },
            "metrics": aggregated,
            "details": results,
        }
        if self.baseline:
            evaluation_result["comparison"] = self.comparator.compare(
                self.baseline, aggregated, test_significance=True
            )
            current_metrics = {
                k: v["mean"] for k, v in aggregated.items() if isinstance(v, dict) and "mean" in v
            }
            baseline_metrics = {
                k: v["mean"]
                for k, v in self.baseline.items()
                if isinstance(v, dict) and "mean" in v
            }
            regressions = self.regression_detector.detect(baseline_metrics, current_metrics)
            evaluation_result["regressions"] = regressions
        return evaluation_result

    async def schedule_evaluation(
        self, tasks: List[EvaluationTask], interval_seconds: float, max_runs: Optional[int] = None
    ) -> None:
        """Schedule periodic evaluation."""

        async def _run_scheduled():
            runs = 0
            while max_runs is None or runs < max_runs:
                await self.run_evaluation(tasks)
                runs += 1
                if max_runs is None or runs < max_runs:
                    await asyncio.sleep(interval_seconds)

        task = asyncio.create_task(_run_scheduled())
        self._scheduled_tasks.append(task)
        if max_runs:
            await task

    def stop_scheduled_evaluations(self) -> None:
        """Stop all scheduled evaluations."""
        for task in self._scheduled_tasks:
            task.cancel()
        self._scheduled_tasks.clear()
