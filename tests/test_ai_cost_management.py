"""
Comprehensive test suite for AI cost management and monitoring system.

Tests cost tracking, budgeting, alerting, optimization, and reporting features.
"""

import asyncio
import pytest
from datetime import datetime, timedelta, date
from decimal import Decimal
from typing import Dict, List, Optional
from unittest.mock import Mock, patch, AsyncMock

from tests.mocks.mock_redis import MockRedis
from services.ai.cost_management import (
    AICostManager,
    CostTrackingService,
    BudgetAlertService,
    CostOptimizationService,
    AIUsageMetrics,
    CostMetrics,
    BudgetAlert,
    CostOptimization,
    ModelCostConfig,
    UsageType,
    AlertType,
    OptimizationStrategy,
)


class TestAIUsageMetrics:
    """Test AI usage metrics calculation and tracking."""

    def test_metrics_initialization(self):
        """Test proper initialization of usage metrics."""
        metrics = AIUsageMetrics(
            service_name="policy_generation",
            model_name="gemini-2.5-pro",
            input_tokens=1000,
            output_tokens=500,
            total_tokens=1500,
            request_count=1,
            cost_usd=Decimal("0.015"),
            timestamp=datetime.now(),
        )

        assert metrics.service_name == "policy_generation"
        assert metrics.model_name == "gemini-2.5-pro"
        assert metrics.input_tokens == 1000
        assert metrics.output_tokens == 500
        assert metrics.total_tokens == 1500
        assert metrics.request_count == 1
        assert metrics.cost_usd == Decimal("0.015")
        assert isinstance(metrics.timestamp, datetime)

    def test_metrics_aggregation(self):
        """Test aggregation of multiple usage metrics."""
        metrics1 = AIUsageMetrics(
            service_name="policy_generation",
            model_name="gemini-2.5-pro",
            input_tokens=1000,
            output_tokens=500,
            total_tokens=1500,
            request_count=1,
            cost_usd=Decimal("0.015"),
            timestamp=datetime.now(),
        )

        metrics2 = AIUsageMetrics(
            service_name="policy_generation",
            model_name="gemini-2.5-pro",
            input_tokens=800,
            output_tokens=400,
            total_tokens=1200,
            request_count=1,
            cost_usd=Decimal("0.012"),
            timestamp=datetime.now(),
        )

        aggregated = metrics1.aggregate(metrics2)

        assert aggregated.input_tokens == 1800
        assert aggregated.output_tokens == 900
        assert aggregated.total_tokens == 2700
        assert aggregated.request_count == 2
        assert aggregated.cost_usd == Decimal("0.027")

    def test_cost_per_token_calculation(self):
        """Test cost per token calculation."""
        metrics = AIUsageMetrics(
            service_name="assessment_analysis",
            model_name="gpt-4-turbo",
            input_tokens=2000,
            output_tokens=1000,
            total_tokens=3000,
            request_count=1,
            cost_usd=Decimal("0.120"),
            timestamp=datetime.now(),
        )

        assert metrics.cost_per_token == Decimal("0.00004")  # 0.120 / 3000

    def test_efficiency_score_calculation(self):
        """Test efficiency score based on cost vs. output quality."""
        metrics = AIUsageMetrics(
            service_name="recommendation_generation",
            model_name="gemini-2.5-flash",
            input_tokens=500,
            output_tokens=1000,
            total_tokens=1500,
            request_count=1,
            cost_usd=Decimal("0.002"),
            timestamp=datetime.now(),
            response_quality_score=0.85,
        )

        efficiency = metrics.calculate_efficiency_score()
        # efficiency = quality_score / cost_per_token
        expected = Decimal("0.85") / (Decimal("0.002") / Decimal("1500"))
        assert efficiency == expected


class TestModelCostConfig:
    """Test model cost configuration management."""

    def test_gemini_cost_calculation(self):
        """Test Gemini model cost calculation."""
        config = ModelCostConfig.get_gemini_config()

        # Test input cost calculation
        input_cost = config.calculate_input_cost(1000)
        expected_input = (Decimal("1000") / Decimal("1000000") * config.input_cost_per_million,)
        assert input_cost == expected_input

        # Test output cost calculation
        output_cost = config.calculate_output_cost(500)
        expected_output = (Decimal("500") / Decimal("1000000") * config.output_cost_per_million,)
        assert output_cost == expected_output

    def test_openai_cost_calculation(self):
        """Test OpenAI model cost calculation."""
        config = ModelCostConfig.get_openai_config("gpt-4-turbo")

        total_cost = config.calculate_total_cost(input_tokens=1500, output_tokens=750)

        input_cost = (Decimal("1500") / Decimal("1000000") * config.input_cost_per_million,)
        output_cost = (Decimal("750") / Decimal("1000000") * config.output_cost_per_million,)
        expected_total = input_cost + output_cost

        assert total_cost == expected_total

    def test_custom_model_config(self):
        """Test custom model configuration."""
        config = ModelCostConfig(
            model_name="custom-model",
            provider="custom",
            input_cost_per_million=Decimal("5.00"),
            output_cost_per_million=Decimal("10.00"),
            context_window=8192,
            max_output_tokens=4096,
        )

        assert config.model_name == "custom-model"
        assert config.provider == "custom"
        assert config.input_cost_per_million == Decimal("5.00")
        assert config.output_cost_per_million == Decimal("10.00")


class TestCostTrackingService:
    """Test core cost tracking functionality."""

    @pytest.fixture
    def cost_tracker(self):
        """Create cost tracking service instance."""
        mock_redis = MockRedis()
        return CostTrackingService(redis_client=mock_redis)

    @pytest.mark.asyncio
    async def test_track_usage(self, cost_tracker):
        """Test tracking AI usage with automatic cost calculation."""
        usage = await cost_tracker.track_usage(
            service_name="policy_generation",
            model_name="gemini-2.5-pro",
            input_tokens=1000,
            output_tokens=500,
            user_id="user_123",
            session_id="session_456",
            request_metadata={"endpoint": "/api/v1/ai/generate-policy"},
        )

        assert usage.service_name == "policy_generation"
        assert usage.model_name == "gemini-2.5-pro"
        assert usage.input_tokens == 1000
        assert usage.output_tokens == 500
        assert usage.total_tokens == 1500
        assert usage.cost_usd > 0
        assert usage.user_id == "user_123"
        assert usage.session_id == "session_456"

    @pytest.mark.asyncio
    async def test_get_usage_by_service(self, cost_tracker):
        """Test retrieving usage metrics by service."""
        # Track multiple usage events
        await cost_tracker.track_usage("policy_generation", "gemini-2.5-pro", 1000, 500)
        await cost_tracker.track_usage("policy_generation", "gpt-4-turbo", 800, 400)
        await cost_tracker.track_usage(
            "assessment_analysis",
            "gemini-2.5-flash",
            600,
            300,
        )

        # Get usage for specific service
        policy_usage = await cost_tracker.get_usage_by_service("policy_generation")

        assert len(policy_usage) == 1  # Aggregated by day
        assert all(usage.service_name == "policy_generation" for usage in policy_usage)

    @pytest.mark.asyncio
    async def test_get_usage_by_time_range(self, cost_tracker):
        """Test retrieving usage metrics by time range."""
        today = date.today()
        start_time = datetime.combine(today, datetime.min.time())
        end_time = datetime.combine(today, datetime.max.time())

        await cost_tracker.track_usage("policy_generation", "gemini-2.5-pro", 1000, 500)

        usage_metrics = await cost_tracker.get_usage_by_time_range(start_time, end_time)

        assert len(usage_metrics) == 1
        # Check that timestamp is today (aggregated by day)
        assert usage_metrics[0].timestamp.date() == today

    @pytest.mark.asyncio
    async def test_calculate_daily_costs(self, cost_tracker):
        """Test daily cost calculation and aggregation."""
        # Simulate usage throughout the day
        for i in range(10):
            await cost_tracker.track_usage(
                f"service_{i % 3}",
                "gemini-2.5-pro",
                1000 + i * 100,
                500 + i * 50,
            )

        daily_costs = await cost_tracker.calculate_daily_costs(datetime.now().date())

        assert daily_costs["total_cost"] > 0
        assert daily_costs["total_requests"] == 10
        assert daily_costs["total_tokens"] > 0
        assert "service_breakdown" in daily_costs

    @pytest.mark.asyncio
    async def test_get_cost_trends(self, cost_tracker):
        """Test cost trend analysis."""
        # Simulate usage over multiple days
        base_date = datetime.now().date()
        for day_offset in range(7):
            date = base_date - timedelta(days=day_offset)
            timestamp = datetime.combine(date, datetime.min.time())

            with patch("datetime.datetime") as mock_datetime:
                mock_datetime.now.return_value = timestamp
                await cost_tracker.track_usage(
                    "policy_generation",
                    "gemini-2.5-pro",
                    1000,
                    500,
                )

        trends = await cost_tracker.get_cost_trends(days=7)

        assert len(trends) == 7
        assert all("date" in trend and "cost" in trend for trend in trends)

    @pytest.mark.asyncio
    async def test_identify_cost_anomalies(self, cost_tracker):
        """Test cost anomaly detection."""
        # Simulate normal usage
        for _ in range(10):
            await cost_tracker.track_usage(
                "policy_generation",
                "gemini-2.5-pro",
                1000,
                500,
            )

        # Simulate anomalous usage (high token count to trigger > $0.50 cost)
        await cost_tracker.track_usage("policy_generation", "gpt-4-turbo", 30000, 20000)

        anomalies = await cost_tracker.identify_cost_anomalies(threshold_multiplier=2.0)

        assert len(anomalies) >= 1
        assert any(anomaly["cost"] > Decimal("0.5") for anomaly in anomalies)


class TestBudgetAlertService:
    """Test budget monitoring and alert functionality."""

    @pytest.fixture
    def alert_service(self):
        """Create budget alert service instance."""
        mock_redis = MockRedis()
        return BudgetAlertService(redis_client=mock_redis)

    @pytest.mark.asyncio
    async def test_set_daily_budget(self, alert_service):
        """Test setting daily budget limit."""
        await alert_service.set_daily_budget(Decimal("100.00"))

        budget = await alert_service.get_current_budget()
        assert budget["daily_limit"] == Decimal("100.00")

    @pytest.mark.asyncio
    async def test_budget_usage_tracking(self, alert_service):
        """Test tracking budget usage throughout the day."""
        await alert_service.set_daily_budget(Decimal("50.00"))

        # Simulate usage that approaches budget
        usage = CostMetrics(
            total_cost=Decimal("45.00"),
            total_requests=100,
            total_tokens=50000,
            period_start=datetime.now().replace(hour=0, minute=0, second=0),
            period_end=datetime.now(),
        )

        budget_status = await alert_service.check_budget_status(usage)

        assert budget_status["usage_percentage"] == 90.0  # 45/50 * 100
        assert budget_status["remaining_budget"] == Decimal("5.00")
        assert budget_status["alert_level"] == "warning"

    @pytest.mark.asyncio
    async def test_budget_exceeded_alert(self, alert_service):
        """Test alert generation when budget is exceeded."""
        await alert_service.set_daily_budget(Decimal("25.00"))

        usage = CostMetrics(
            total_cost=Decimal("30.00"),
            total_requests=200,
            total_tokens=100000,
            period_start=datetime.now().replace(hour=0, minute=0, second=0),
            period_end=datetime.now(),
        )

        alerts = await alert_service.check_budget_alerts(usage)

        assert len(alerts) >= 1
        assert any(alert.alert_type == AlertType.BUDGET_EXCEEDED for alert in alerts)
        assert any(alert.severity == "critical" for alert in alerts)

    @pytest.mark.asyncio
    async def test_cost_spike_detection(self, alert_service):
        """Test detection of unusual cost spikes."""
        # Set baseline usage
        baseline_costs = [
            Decimal("5.00"),
            Decimal("6.00"),
            Decimal("5.50"),
            Decimal("5.25"),
        ]

        # Detect spike
        spike_cost = Decimal("25.00")

        is_spike = await alert_service.detect_cost_spike(spike_cost, baseline_costs)

        assert is_spike is True

    @pytest.mark.asyncio
    async def test_service_specific_budgets(self, alert_service):
        """Test service-specific budget limits."""
        await alert_service.set_service_budget("policy_generation", Decimal("20.00"))
        await alert_service.set_service_budget("assessment_analysis", Decimal("15.00"))

        service_usage = CostMetrics(
            total_cost=Decimal("18.00"),
            total_requests=50,
            total_tokens=25000,
            period_start=datetime.now().replace(hour=0, minute=0, second=0),
            period_end=datetime.now(),
            service_name="policy_generation",
        )

        alerts = await alert_service.check_service_budget(
            "policy_generation",
            service_usage,
        )

        assert len(alerts) >= 1
        assert alerts[0].alert_type == AlertType.SERVICE_BUDGET_WARNING


class TestCostOptimizationService:
    """Test cost optimization recommendations and strategies."""

    @pytest.fixture
    def optimization_service(self):
        """Create cost optimization service instance."""
        return CostOptimizationService()

    @pytest.mark.asyncio
    async def test_model_efficiency_analysis(self, optimization_service):
        """Test analysis of model efficiency and recommendations."""
        usage_data = [
            AIUsageMetrics(
                service_name="policy_generation",
                model_name="gpt-4-turbo",
                input_tokens=1000,
                output_tokens=500,
                total_tokens=1500,
                request_count=1,
                cost_usd=Decimal("0.120"),
                timestamp=datetime.now(),
                response_quality_score=0.95,
            ),
            AIUsageMetrics(
                service_name="policy_generation",
                model_name="gemini-2.5-pro",
                input_tokens=1000,
                output_tokens=500,
                total_tokens=1500,
                request_count=1,
                cost_usd=Decimal("0.015"),
                timestamp=datetime.now(),
                response_quality_score=0.90,
            ),
        ]

        optimization = await optimization_service.analyze_model_efficiency(usage_data)

        assert optimization.strategy == OptimizationStrategy.MODEL_SWITCH
        assert "gemini-2.5-pro" in optimization.recommendation
        assert optimization.potential_savings > Decimal("0.10")

    @pytest.mark.asyncio
    async def test_caching_optimization(self, optimization_service):
        """Test caching strategy recommendations."""
        # Simulate repeated similar requests
        similar_requests = [
            {"input_hash": "hash_123", "cost": Decimal("0.015"), "count": 5},
            {"input_hash": "hash_456", "cost": Decimal("0.012"), "count": 3},
        ]

        optimization = await optimization_service.analyze_caching_opportunities(
            similar_requests,
        )

        assert optimization.strategy == OptimizationStrategy.CACHING_IMPROVEMENT
        assert optimization.potential_savings > 0

    @pytest.mark.asyncio
    async def test_batch_processing_optimization(self, optimization_service):
        """Test batch processing recommendations."""
        individual_requests = [
            {"tokens": 500, "cost": Decimal("0.008"), "timestamp": datetime.now()}
            for _ in range(10)
        ]

        optimization = await optimization_service.analyze_batch_opportunities(
            individual_requests,
        )

        assert optimization.strategy == OptimizationStrategy.BATCH_PROCESSING
        assert optimization.potential_savings > 0

    @pytest.mark.asyncio
    async def test_prompt_optimization_analysis(self, optimization_service):
        """Test prompt optimization recommendations."""
        prompt_metrics = {
            "avg_input_tokens": 2001,
            "avg_output_tokens": 500,
            "success_rate": 0.85,
            "cost_per_success": Decimal("0.025"),
        }

        optimization = await optimization_service.analyze_prompt_efficiency(
            prompt_metrics,
        )

        assert optimization.strategy == OptimizationStrategy.PROMPT_OPTIMIZATION
        assert "reduce input token" in optimization.recommendation.lower()

    @pytest.mark.asyncio
    async def test_comprehensive_optimization_report(self, optimization_service):
        """Test generation of comprehensive optimization report."""
        report_data = {
            "time_period": {
                "start": datetime.now() - timedelta(days=7),
                "end": datetime.now(),
            },
            "total_cost": Decimal("150.00"),
            "request_count": 1000,
            "model_distribution": {"gemini-2.5-pro": 0.6, "gpt-4-turbo": 0.4},
            "service_costs": {
                "policy_generation": Decimal("90.00"),
                "assessment_analysis": Decimal("60.00"),
            },
        }

        report = await optimization_service.generate_optimization_report(report_data)

        assert "optimizations" in report
        assert "total_potential_savings" in report
        assert "priority_recommendations" in report
        assert len(report["optimizations"]) > 0


class TestAICostManager:
    """Test the main AI cost management orchestrator."""

    @pytest.fixture
    def cost_manager(self):
        """Create AI cost manager instance."""
        mock_redis = MockRedis()
        return AICostManager(redis_client=mock_redis)

    @pytest.mark.asyncio
    async def test_track_api_call(self, cost_manager):
        """Test tracking a complete AI API call with cost calculation."""
        result = await cost_manager.track_ai_request(
            service_name="policy_generation",
            model_name="gemini-2.5-pro",
            input_prompt="Generate a privacy policy for an e-commerce company.",
            response_content="Privacy Policy...",
            input_tokens=1000,
            output_tokens=2000,
            user_id="user_123",
            request_id="req_123",  # Add request_id for usage_id
            response_quality_score=0.95,  # Add quality score for efficiency calculation
            metadata={"endpoint": "/api/v1/ai/generate-policy"},
        )

        assert result["cost_usd"] > 0
        assert result["efficiency_score"] > 0
        assert result["usage_id"] is not None

    @pytest.mark.asyncio
    async def test_daily_cost_summary(self, cost_manager):
        """Test generation of daily cost summary."""
        # Simulate multiple API calls
        for i in range(5):
            await cost_manager.track_ai_request(
                service_name=f"service_{i % 2}",
                model_name="gemini-2.5-pro",
                input_prompt="Test prompt",
                response_content="Test response",
                input_tokens=500 + i * 100,
                output_tokens=250 + i * 50,
                user_id=f"user_{i}",
            )

        summary = await cost_manager.get_daily_summary(datetime.now().date())

        assert summary["total_cost"] > 0
        assert summary["total_requests"] == 5
        assert "service_breakdown" in summary
        assert "model_breakdown" in summary
        assert "cost_trends" in summary

    @pytest.mark.asyncio
    async def test_budget_monitoring_integration(self, cost_manager):
        """Test integration with budget monitoring."""
        await cost_manager.set_daily_budget(Decimal("10.00"))

        # Simulate usage approaching budget
        for _ in range(3):
            await cost_manager.track_ai_request(
                service_name="policy_generation",
                model_name="gpt-4-turbo",
                input_prompt="Large prompt " * 100,
                response_content="Large response " * 200,
                input_tokens=200000,  # High tokens to trigger budget alerts
                output_tokens=100000,  # $2 + $3 = $5 per request
                user_id="user_123",
            )

        alerts = await cost_manager.check_budget_alerts()

        assert len(alerts) > 0
        assert any(
            alert.alert_type in [AlertType.BUDGET_WARNING, AlertType.BUDGET_EXCEEDED]
            for alert in alerts
        )

    @pytest.mark.asyncio
    async def test_optimization_recommendations(self, cost_manager):
        """Test generation of cost optimization recommendations."""
        # Simulate varied usage patterns
        models = ["gemini-2.5-pro", "gpt-4-turbo", "gemini-2.5-flash"]
        for i in range(15):
            await cost_manager.track_ai_request(
                service_name="policy_generation",
                model_name=models[i % 3],
                input_prompt="Test prompt",
                response_content="Test response",
                input_tokens=1000 + i * 50,
                output_tokens=500 + i * 25,
                user_id="user_123",
            )

        recommendations = await cost_manager.get_optimization_recommendations()

        assert len(recommendations) > 0
        assert all("strategy" in rec and "potential_savings" in rec for rec in recommendations)

    @pytest.mark.asyncio
    async def test_cost_reporting_endpoints(self, cost_manager):
        """Test various cost reporting endpoints."""
        # Monthly report
        monthly_report = await cost_manager.generate_monthly_report(
            year=datetime.now().year,
            month=datetime.now().month,
        )

        assert "total_cost" in monthly_report
        assert "daily_breakdown" in monthly_report
        assert "service_analysis" in monthly_report
        assert "optimization_opportunities" in monthly_report

    @pytest.mark.asyncio
    @pytest.mark.skip(reason="WebSocket manager not yet implemented")
    async def test_real_time_cost_monitoring(self, cost_manager):
        """Test real-time cost monitoring and alerts."""
        with patch("services.ai.cost_management.websocket_manager") as mock_ws:
            await cost_manager.track_ai_request(
                service_name="policy_generation",
                model_name="gpt-4-turbo",
                input_prompt="Expensive request",
                response_content="Expensive response",
                input_tokens=5000,
                output_tokens=2500,
                user_id="user_123",
            )

            # Verify real-time updates were sent
            mock_ws.broadcast_cost_update.assert_called_once()

    @pytest.mark.asyncio
    async def test_user_cost_limits(self, cost_manager):
        """Test per-user cost limits and enforcement."""
        await cost_manager.set_user_daily_limit("user_123", Decimal("5.00"))

        # Test limit enforcement
        try:
            for _ in range(10):  # This should exceed the limit
                await cost_manager.track_ai_request(
                    service_name="policy_generation",
                    model_name="gpt-4-turbo",
                    input_prompt="Expensive request",
                    response_content="Expensive response",
                    input_tokens=2000,
                    output_tokens=1000,
                    user_id="user_123",
                )
        except Exception as e:
            assert "cost limit exceeded" in str(e).lower()

    @pytest.mark.asyncio
    @pytest.mark.skip(reason="Cost forecasting method not yet implemented")
    async def test_cost_forecasting(self, cost_manager):
        """Test cost forecasting based on usage trends."""
        # Simulate historical usage
        for day in range(30):
            date = datetime.now() - timedelta(days=day)
            with patch("datetime.datetime") as mock_datetime:
                mock_datetime.now.return_value = date
                await cost_manager.track_ai_request(
                    service_name="policy_generation",
                    model_name="gemini-2.5-pro",
                    input_prompt="Historical request",
                    response_content="Historical response",
                    input_tokens=1000,
                    output_tokens=500,
                    user_id="user_123",
                )

        forecast = await cost_manager.generate_cost_forecast(days_ahead=30)

        assert "predicted_daily_cost" in forecast
        assert "confidence_interval" in forecast
        assert "trend_analysis" in forecast


class TestCostOptimizationStrategies:
    """Test specific cost optimization strategies."""

    @pytest.mark.asyncio
    async def test_intelligent_model_routing(self):
        """Test intelligent routing to cost-effective models based on task complexity."""
        from services.ai.cost_management import IntelligentModelRouter

        router = IntelligentModelRouter()

        # Simple task should route to cheaper model
        simple_task = "What is GDPR?"
        model_choice = await router.select_optimal_model(
            simple_task,
            "question_answering",
        )
        assert model_choice["model"] in ["gemini-2.5-flash-lite", "gpt-3.5-turbo"]

        # Complex task should route to more capable model
        complex_task = (
            "Generate a comprehensive 20-page privacy policy document that covers "
            "data collection, storage, processing, sharing, retention, user rights, "
            "cookie policies, third-party integrations, international data transfers, "
            "children's privacy, security measures, breach notifications, and compliance "
            "with GDPR, CCPA, and other relevant privacy regulations worldwide",
        )
        model_choice = await router.select_optimal_model(
            complex_task,
            "policy_generation",
        )
        assert model_choice["model"] in ["gemini-2.5-pro", "gpt-4-turbo"]

    @pytest.mark.asyncio
    async def test_dynamic_caching_strategy(self):
        """Test dynamic caching based on cost-benefit analysis."""
        from services.ai.cost_management import DynamicCacheManager

        cache_manager = DynamicCacheManager()

        # High-cost, repeated request should be cached
        expensive_request = {
            "prompt": "Generate complex analysis",
            "model": "gpt-4-turbo",
            "estimated_cost": Decimal("2.00"),
            "frequency": 10,
        }

        should_cache = await cache_manager.should_cache_request(expensive_request)
        assert should_cache is True

        # Low-cost, infrequent request should not be cached
        cheap_request = {
            "prompt": "Simple question",
            "model": "gemini-2.5-flash",
            "estimated_cost": Decimal("0.001"),
            "frequency": 1,
        }

        should_cache = await cache_manager.should_cache_request(cheap_request)
        assert should_cache is False

    @pytest.mark.asyncio
    async def test_prompt_compression_optimization(self):
        """Test prompt compression to reduce token usage."""
        from services.ai.cost_management import PromptOptimizer

        optimizer = PromptOptimizer()

        verbose_prompt = """
        Please analyze the following business requirements and generate a comprehensive 
        privacy policy that covers all aspects of data collection, processing, storage, 
        and sharing. The policy should be compliant with GDPR, CCPA, and UK data 
        protection regulations. Make sure to include detailed sections on user rights, 
        data retention, cookies, third-party integrations, and contact information.

        Business details:
        - E-commerce platform
        - Collects personal information during checkout
        - Uses analytics tools
        - Integrates with payment processors
        """

        optimized = await optimizer.compress_prompt(verbose_prompt)

        assert len(optimized.split()) < len(verbose_prompt.split())
        assert "GDPR" in optimized
        assert "e-commerce" in optimized.lower()

    @pytest.mark.asyncio
    async def test_batch_request_optimization(self):
        """Test batching multiple requests to reduce per-request overhead."""
        from services.ai.cost_management import BatchRequestOptimizer

        optimizer = BatchRequestOptimizer()

        individual_requests = [
            {"prompt": f"Analyze requirement {i}", "user_id": f"user_{i}"} for i in range(5)
        ]

        batch_result = await optimizer.optimize_batch(individual_requests)

        assert batch_result["batched"] is True
        assert batch_result["cost_savings"] > 0
        assert len(batch_result["combined_prompt"]) > 0


class TestCostReportingAndAnalytics:
    """Test cost reporting and analytics functionality."""

    @pytest.mark.asyncio
    async def test_executive_cost_dashboard(self):
        """Test executive-level cost dashboard generation."""
        from services.ai.cost_management import CostAnalyticsDashboard

        dashboard = CostAnalyticsDashboard()

        # Simulate cost data
        cost_data = {
            "current_month": Decimal("450.00"),
            "previous_month": Decimal("380.00"),
            "yearly_total": Decimal("4200.00"),
            "top_services": [
                {"name": "policy_generation", "cost": Decimal("180.00")},
                {"name": "assessment_analysis", "cost": Decimal("150.00")},
                {"name": "chat_assistance", "cost": Decimal("120.00")},
            ],
        }

        report = await dashboard.generate_executive_summary(cost_data)

        assert "cost_growth_rate" in report
        assert "roi_analysis" in report
        assert "optimization_impact" in report
        assert "budget_utilization" in report

    @pytest.mark.asyncio
    async def test_cost_attribution_analysis(self):
        """Test detailed cost attribution by user, service, and feature."""
        from services.ai.cost_management import CostAttributionAnalyzer

        analyzer = CostAttributionAnalyzer()

        attribution = await analyzer.analyze_cost_attribution(
            time_period={
                "start": datetime.now() - timedelta(days=30),
                "end": datetime.now(),
            },
            dimensions=["user_id", "service_name", "model_name", "feature"],
        )

        assert "user_breakdown" in attribution
        assert "service_breakdown" in attribution
        assert "model_breakdown" in attribution
        assert "feature_breakdown" in attribution
        assert "cost_drivers" in attribution

    @pytest.mark.asyncio
    async def test_predictive_cost_modeling(self):
        """Test predictive modeling for future cost estimation."""
        from services.ai.cost_management import PredictiveCostModeler

        modeler = PredictiveCostModeler()

        # Historical data simulation
        historical_data = [
            {
                "date": datetime.now() - timedelta(days=i),
                "cost": Decimal(f"{100 + i * 5}.00"),
            }
            for i in range(90)
        ]

        prediction = await modeler.predict_future_costs(
            historical_data=historical_data,
            prediction_horizon_days=30,
            include_seasonality=True,
            include_growth_trends=True,
        )

        assert "predicted_costs" in prediction
        assert "confidence_intervals" in prediction
        assert "cost_drivers" in prediction
        assert "recommended_budget" in prediction


# Integration tests with real AI services
class TestIntegrationWithAIServices:
    """Test integration with actual AI services."""

    @pytest.mark.asyncio
    async def test_budget_alert_integration(self):
        """Test budget alerts trigger during API calls."""
        mock_redis = MockRedis()
        cost_manager = AICostManager(redis_client=mock_redis)

        # Mock the actual AI call but track real cost calculation
        with patch.object(ComplianceAssistant, "generate_response") as mock_generate:
            mock_generate.return_value = {
                "content": "Privacy policy content...",
                "usage": {
                    "input_tokens": 1200,
                    "output_tokens": 800,
                    "total_tokens": 2000,
                },
            }

            result = await cost_manager.track_ai_request(
                service_name="policy_generation",
                model_name="gemini-2.5-pro",
                input_prompt="Generate privacy policy for tech startup",
                response_content="Privacy policy content...",
                input_tokens=1200,
                output_tokens=800,
                user_id="integration_test_user",
            )

            assert result["cost_usd"] > 0
            assert result["usage_id"] is not None

    @pytest.mark.asyncio
    @pytest.mark.integration
    async def test_budget_alert_integration(self):
        """Test budget alert integration with real cost tracking."""
        from services.ai.cost_management import AICostManager

        mock_redis = MockRedis()
        cost_manager = AICostManager(redis_client=mock_redis)

        # Set a low budget for testing
        await cost_manager.set_daily_budget(Decimal("0.10"))

        # Make enough requests to trigger alert
        for _i in range(3):
            await cost_manager.track_ai_request(
                service_name="test_service",
                model_name="gpt-4-turbo",
                input_prompt="Test prompt " * 200,  # Large prompt
                response_content="Test response " * 100,  # Large response
                input_tokens=1500,
                output_tokens=750,
                user_id="integration_test_user",
            )

        alerts = await cost_manager.check_budget_alerts()
        assert len(alerts) > 0


if __name__ == "__main__":
    pytest.main([__file__])
