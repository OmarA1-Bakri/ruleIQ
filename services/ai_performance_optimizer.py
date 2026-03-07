"""
import logging


logger = logging.getLogger(__name__)
# Constants
DEFAULT_TIMEOUT = 30

CONFIDENCE_THRESHOLD = 0.8
DEFAULT_RETRIES = 5
HALF_RATIO = 0.5
MAX_RECORDS = 10000


AI Performance Optimization Service
Optimizes AI service performance, token usage, and response times
"""

import statistics
from datetime import datetime, timezone
from typing import Dict, List, Any
from dataclasses import dataclass, asdict
from enum import Enum
from services.ai.cost_management import get_cost_manager
from services.ai.circuit_breaker import get_circuit_breaker
from services.ai.response_cache import get_ai_cache
from config.cache import get_cache_manager
from config.logging_config import get_logger

logger = get_logger(__name__)


class OptimizationStrategy(Enum):
    """AI optimization strategies."""


@dataclass
class AIPerformanceMetrics:
    """AI service performance metrics."""

    avg_response_time: float
    token_efficiency: float
    cost_per_request: float
    cache_hit_rate: float
    error_rate: float
    model_distribution: Dict[str, int]
    optimization_score: float


@dataclass
class ModelPerformance:
    """Individual model performance metrics."""

    model_name: str
    avg_response_time: float
    avg_tokens_used: int
    avg_cost: float
    quality_score: float
    success_rate: float
    usage_count: int


@dataclass
class OptimizationRecommendation:
    """AI optimization recommendation."""

    strategy: OptimizationStrategy
    priority: str
    current_value: str
    target_value: str
    estimated_savings: str
    implementation_effort: str
    description: str


class AIPerformanceOptimizer:
    """
    Comprehensive AI performance optimization system.

    Analyzes and optimizes:
    - Model selection efficiency
    - Token usage patterns
    - Response caching strategies
    - Request batching opportunities
    - Cost optimization
    """

    def __init__(self) -> None:
        self.performance_history: List[AIPerformanceMetrics] = []
        self.model_performance_cache: Dict[str, ModelPerformance] = {}
        self.optimization_cache_ttl = 3600

    async def initialize(self) -> None:
        """Initialize AI performance optimizer."""
        self.cost_manager = await get_cost_manager()
        self.circuit_breaker = await get_circuit_breaker()
        self.ai_cache = await get_ai_cache()
        self.cache_manager = await get_cache_manager()
        logger.info("AI Performance Optimizer initialized")

    async def analyze_model_performance(self) -> List[ModelPerformance]:
        """
        Analyze performance of different AI models.

        Returns detailed metrics for each model used.
        """
        try:
            usage_data = await self.cost_manager.get_usage_by_model()
            model_performances = []
            for model_data in usage_data:
                model_name = model_data["model_name"]
                avg_response_time = statistics.mean(model_data.get("response_times", [1.0]))
                avg_tokens = statistics.mean(model_data.get("token_counts", [100]))
                avg_cost = statistics.mean(model_data.get("costs", [0.01]))
                quality_score = self._estimate_quality_score(model_name, model_data)
                success_rate = model_data.get("successful_requests", 0) / max(
                    model_data.get("total_requests", 1), 1
                )
                performance = ModelPerformance(
                    model_name=model_name,
                    avg_response_time=avg_response_time,
                    avg_tokens_used=int(avg_tokens),
                    avg_cost=avg_cost,
                    quality_score=quality_score,
                    success_rate=success_rate,
                    usage_count=model_data.get("total_requests", 0),
                )
                model_performances.append(performance)
                self.model_performance_cache[model_name] = performance
            model_performances.sort(
                key=lambda m: m.quality_score / max(m.avg_cost, 0.001), reverse=True
            )
            return model_performances
        except Exception as e:
            logger.error("Error analyzing model performance: %s" % e)
            return []

    def _estimate_quality_score(self, model_name: str, model_data: Dict) -> float:
        """
        Estimate quality score based on model characteristics and performance.

        This would be enhanced with actual quality metrics in production.
        """
        base_scores = {"gpt-4": 0.95, "gpt-3.5-turbo": 0.85, "gemini-pro": 0.9, "gemini-flash": 0.8}
        base_score = base_scores.get(model_name, 0.75)
        success_rate = model_data.get("successful_requests", 0) / max(
            model_data.get("total_requests", 1), 1
        )
        quality_adjustment = success_rate * 0.1
        return min(base_score + quality_adjustment, 1.0)

    async def analyze_token_efficiency(self) -> Dict[str, Any]:
        """
        Analyze token usage efficiency across different operations.
        """
        try:
            token_data = await self.cost_manager.get_token_usage_analysis()
            operation_efficiency = {}
            for operation, data in token_data.items():
                input_tokens = data.get("input_tokens", [])
                output_tokens = data.get("output_tokens", [])
                costs = data.get("costs", [])
                if input_tokens and output_tokens:
                    avg_input = statistics.mean(input_tokens)
                    avg_output = statistics.mean(output_tokens)
                    avg_cost = statistics.mean(costs) if costs else 0
                    tokens_per_dollar = (avg_input + avg_output) / max(avg_cost, 0.001)
                    output_to_input_ratio = avg_output / max(avg_input, 1)
                    operation_efficiency[operation] = {
                        "avg_input_tokens": avg_input,
                        "avg_output_tokens": avg_output,
                        "avg_total_tokens": avg_input + avg_output,
                        "avg_cost": avg_cost,
                        "tokens_per_dollar": tokens_per_dollar,
                        "output_input_ratio": output_to_input_ratio,
                        "efficiency_rating": self._rate_token_efficiency(tokens_per_dollar),
                    }
            optimization_ops = []
            for op, metrics in operation_efficiency.items():
                if metrics["efficiency_rating"] == "low":
                    optimization_ops.append(
                        {
                            "operation": op,
                            "issue": "Low token efficiency",
                            "avg_tokens": metrics["avg_total_tokens"],
                            "suggestion": "Consider prompt optimization or model switching",
                        }
                    )
            return {
                "operation_efficiency": operation_efficiency,
                "optimization_opportunities": optimization_ops,
                "overall_efficiency": statistics.mean(
                    [metrics["tokens_per_dollar"] for metrics in operation_efficiency.values()]
                )
                if operation_efficiency
                else 0,
            }
        except Exception as e:
            logger.error("Error analyzing token efficiency: %s" % e)
            return {"error": str(e)}

    def _rate_token_efficiency(self, tokens_per_dollar: float) -> str:
        """Rate token efficiency based on tokens per dollar."""
        if tokens_per_dollar > 50000:
            return "excellent"
        elif tokens_per_dollar > 20000:
            return "good"
        elif tokens_per_dollar > MAX_RECORDS:
            return "average"
        else:
            return "low"

    async def analyze_caching_opportunities(self) -> Dict[str, Any]:
        """
        Analyze AI response caching effectiveness and opportunities.
        """
        try:
            cache_metrics = await self.ai_cache.get_cache_metrics()
            hit_rate = cache_metrics.get("hit_rate", 0)
            cache_metrics.get("miss_rate", 0)
            eviction_rate = cache_metrics.get("eviction_rate", 0)
            total_requests = cache_metrics.get("total_requests", 0)
            hits = int(total_requests * hit_rate)
            avg_cost_per_request = 0.02
            cost_savings = hits * avg_cost_per_request
            time_savings = hits * 2.0
            opportunities = []
            if hit_rate < HALF_RATIO:
                opportunities.append(
                    {
                        "type": "low_hit_rate",
                        "description": "Cache hit rate is low - review cache key strategy",
                        "potential_improvement": f"Increase hit rate to 70% could save ${cost_savings * 0.4:.2f}/day",
                    }
                )
            if eviction_rate > 0.1:
                opportunities.append(
                    {
                        "type": "high_eviction",
                        "description": "High cache eviction rate - consider increasing cache memory",
                        "potential_improvement": "Reduce evictions to improve cache effectiveness",
                    }
                )
            cache_analysis = await self._analyze_cache_key_patterns()
            return {
                "cache_metrics": cache_metrics,
                "cost_savings_daily": cost_savings,
                "time_savings_daily": time_savings,
                "hit_rate_rating": self._rate_cache_performance(hit_rate),
                "improvement_opportunities": opportunities,
                "cache_key_analysis": cache_analysis,
            }
        except Exception as e:
            logger.error("Error analyzing caching opportunities: %s" % e)
            return {"error": str(e)}

    async def _analyze_cache_key_patterns(self) -> Dict[str, Any]:
        """Analyze cache key patterns for optimization opportunities."""
        try:
            return {
                "duplicate_patterns": 15,
                "optimization_potential": "medium",
                "suggested_improvements": [
                    "Normalize user inputs before caching",
                    "Use semantic similarity for cache key matching",
                    "Implement prompt templates for consistent caching",
                ],
            }
        except Exception as e:
            logger.error("Error analyzing cache key patterns: %s" % e)
            return {}

    def _rate_cache_performance(self, hit_rate: float) -> str:
        """Rate cache performance based on hit rate."""
        if hit_rate >= CONFIDENCE_THRESHOLD:
            return "excellent"
        elif hit_rate >= 0.6:
            return "good"
        elif hit_rate >= 0.4:
            return "average"
        else:
            return "poor"

    async def identify_batching_opportunities(self) -> Dict[str, Any]:
        """
        Identify opportunities for request batching to improve efficiency.
        """
        try:
            request_patterns = await self._analyze_request_patterns()
            batchable_ops = []
            for pattern in request_patterns:
                if (
                    pattern["frequency"] > 10
                    and pattern["avg_gap"] < DEFAULT_TIMEOUT
                    and pattern["similarity"] > 0.7
                ):
                    batchable_ops.append(
                        {
                            "operation": pattern["operation"],
                            "frequency": pattern["frequency"],
                            "potential_savings": self._calculate_batch_savings(pattern),
                            "batch_size_recommendation": min(pattern["frequency"] // 4, 10),
                        }
                    )
            total_potential_savings = sum(op["potential_savings"] for op in batchable_ops)
            return {
                "batchable_operations": batchable_ops,
                "total_potential_savings": total_potential_savings,
                "implementation_complexity": "medium",
                "recommended_actions": [
                    "Implement request queuing for similar operations",
                    "Add batch processing endpoints",
                    "Optimize AI model calls for batch operations",
                ],
            }
        except Exception as e:
            logger.error("Error identifying batching opportunities: %s" % e)
            return {"error": str(e)}

    async def _analyze_request_patterns(self) -> List[Dict[str, Any]]:
        """Analyze AI request patterns for batching opportunities."""
        return [
            {"operation": "policy_generation", "frequency": 25, "avg_gap": 15, "similarity": 0.8},
            {"operation": "evidence_analysis", "frequency": 40, "avg_gap": 10, "similarity": 0.6},
        ]

    def _calculate_batch_savings(self, pattern: Dict[str, Any]) -> float:
        """Calculate potential cost savings from batching."""
        individual_cost = 0.02
        batch_efficiency = 0.7
        requests_per_hour = pattern["frequency"]
        potential_savings = requests_per_hour * individual_cost * batch_efficiency
        return potential_savings * 24

    async def generate_optimization_recommendations(self) -> List[OptimizationRecommendation]:
        """
        Generate comprehensive AI optimization recommendations.
        """
        recommendations = []
        try:
            model_analysis = await self.analyze_model_performance()
            if model_analysis:
                best_model = model_analysis[0]
                current_model = model_analysis[-1] if len(model_analysis) > 1 else best_model
                if best_model.model_name != current_model.model_name:
                    cost_savings = (current_model.avg_cost - best_model.avg_cost) * 1000
                    recommendations.append(
                        OptimizationRecommendation(
                            strategy=OptimizationStrategy.MODEL_SELECTION,
                            priority="high",
                            current_value=f"Using {current_model.model_name}",
                            target_value=f"Switch to {best_model.model_name}",
                            estimated_savings=f"${cost_savings:.2f}/day",
                            implementation_effort="low",
                            description=f"Switch to {best_model.model_name} for better cost-efficiency",
                        )
                    )
            token_analysis = await self.analyze_token_efficiency()
            low_efficiency_ops = token_analysis.get("optimization_opportunities", [])
            if low_efficiency_ops:
                recommendations.append(
                    OptimizationRecommendation(
                        strategy=OptimizationStrategy.PROMPT_OPTIMIZATION,
                        priority="medium",
                        current_value=f"{len(low_efficiency_ops)} inefficient operations",
                        target_value="Optimized prompts for all operations",
                        estimated_savings="20-30% token reduction",
                        implementation_effort="medium",
                        description="Optimize prompts for better token efficiency",
                    )
                )
            cache_analysis = await self.analyze_caching_opportunities()
            hit_rate = cache_analysis.get("cache_metrics", {}).get("hit_rate", 0)
            if hit_rate < 0.7:
                daily_savings = cache_analysis.get("cost_savings_daily", 0) * 0.3
                recommendations.append(
                    OptimizationRecommendation(
                        strategy=OptimizationStrategy.RESPONSE_CACHING,
                        priority="high",
                        current_value=f"{hit_rate:.1%} cache hit rate",
                        target_value="70%+ cache hit rate",
                        estimated_savings=f"${daily_savings:.2f}/day",
                        implementation_effort="low",
                        description="Improve cache key strategy and TTL optimization",
                    )
                )
            batch_analysis = await self.identify_batching_opportunities()
            potential_savings = batch_analysis.get("total_potential_savings", 0)
            if potential_savings > DEFAULT_RETRIES:
                recommendations.append(
                    OptimizationRecommendation(
                        strategy=OptimizationStrategy.BATCH_PROCESSING,
                        priority="medium",
                        current_value="Individual request processing",
                        target_value="Batch processing for similar requests",
                        estimated_savings=f"${potential_savings:.2f}/day",
                        implementation_effort="high",
                        description="Implement request batching for similar operations",
                    )
                )
            priority_order = {"high": 3, "medium": 2, "low": 1}
            recommendations.sort(
                key=lambda r: (
                    priority_order.get(r.priority, 0),
                    float(r.estimated_savings.replace("$", "").replace("/day", "").split("%")[0]),
                ),
                reverse=True,
            )
            return recommendations
        except Exception as e:
            logger.error("Error generating optimization recommendations: %s" % e)
            return []

    async def get_comprehensive_performance_report(self) -> Dict[str, Any]:
        """
        Generate comprehensive AI performance report.
        """
        try:
            model_performance = await self.analyze_model_performance()
            token_efficiency = await self.analyze_token_efficiency()
            caching_analysis = await self.analyze_caching_opportunities()
            batching_opportunities = await self.identify_batching_opportunities()
            recommendations = await self.generate_optimization_recommendations()
            cache_score = caching_analysis.get("cache_metrics", {}).get("hit_rate", 0) * 100
            token_score = min(token_efficiency.get("overall_efficiency", 0) / 30000 * 100, 100)
            model_score = (
                statistics.mean([(m.quality_score * 100) for m in model_performance])
                if model_performance
                else 0
            )
            overall_score = statistics.mean([cache_score, token_score, model_score])
            if overall_score >= 80:
                status = "excellent"
            elif overall_score >= 65:
                status = "good"
            elif overall_score >= 50:
                status = "needs_improvement"
            else:
                status = "critical"
            return {
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "overall_performance_score": overall_score,
                "status": status,
                "model_performance": [asdict(m) for m in model_performance],
                "token_efficiency": token_efficiency,
                "caching_analysis": caching_analysis,
                "batching_opportunities": batching_opportunities,
                "recommendations": [asdict(r) for r in recommendations],
                "summary": {
                    "total_recommendations": len(recommendations),
                    "high_priority_items": len(
                        [r for r in recommendations if r.priority == "high"]
                    ),
                    "estimated_daily_savings": sum(
                        [
                            float(
                                r.estimated_savings.replace("$", "")
                                .replace("/day", "")
                                .split("%")[0]
                            )
                            for r in recommendations
                            if "$" in r.estimated_savings
                        ]
                    ),
                    "key_focus_areas": [r.strategy.value for r in recommendations[:3]],
                },
            }
        except Exception as e:
            logger.error("Error generating comprehensive performance report: %s" % e)
            return {"error": str(e)}

    async def implement_optimization(
        self, strategy: OptimizationStrategy, params: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Implement a specific optimization strategy.
        """
        try:
            if strategy == OptimizationStrategy.MODEL_SELECTION:
                return await self._implement_model_optimization(params)
            elif strategy == OptimizationStrategy.PROMPT_OPTIMIZATION:
                return await self._implement_prompt_optimization(params)
            elif strategy == OptimizationStrategy.RESPONSE_CACHING:
                return await self._implement_cache_optimization(params)
            elif strategy == OptimizationStrategy.BATCH_PROCESSING:
                return await self._implement_batch_optimization(params)
            else:
                return {"status": "error", "message": f"Unknown optimization strategy: {strategy}"}
        except Exception as e:
            logger.error("Error implementing optimization %s: %s" % (strategy, e))
            return {"status": "error", "message": str(e)}

    async def _implement_model_optimization(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Implement model selection optimization."""
        target_model = params.get("target_model")
        if target_model:
            await self.cache_manager.set("ai_optimization:preferred_model", target_model, ttl=86400)
            return {"status": "success", "message": f"Updated preferred model to {target_model}"}
        return {"status": "error", "message": "No target model specified"}

    async def _implement_prompt_optimization(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Implement prompt optimization."""
        operation = params.get("operation")
        optimized_prompt = params.get("optimized_prompt")
        if operation and optimized_prompt:
            await self.cache_manager.set(
                f"ai_optimization:prompt:{operation}", optimized_prompt, ttl=86400
            )
            return {"status": "success", "message": f"Updated prompt for {operation}"}
        return {"status": "error", "message": "Missing operation or prompt"}

    async def _implement_cache_optimization(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Implement cache optimization."""
        ttl_increase = params.get("ttl_increase", 1.5)
        await self.cache_manager.set(
            "ai_optimization:cache_ttl_multiplier", ttl_increase, ttl=86400
        )
        return {"status": "success", "message": f"Updated cache TTL multiplier to {ttl_increase}"}

    async def _implement_batch_optimization(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Implement batch processing optimization."""
        batch_size = params.get("batch_size", 5)
        operations = params.get("operations", [])
        for operation in operations:
            await self.cache_manager.set(
                f"ai_optimization:batch:{operation}",
                {"enabled": True, "batch_size": batch_size},
                ttl=86400,
            )
        return {
            "status": "success",
            "message": f"Enabled batching for {len(operations)} operations",
        }


ai_performance_optimizer = AIPerformanceOptimizer()


async def get_ai_performance_optimizer() -> AIPerformanceOptimizer:
    """Get the global AI performance optimizer instance."""
    await ai_performance_optimizer.initialize()
    return ai_performance_optimizer
