"""
Unit Tests for AI Caching and Performance Features

Tests the AI response caching, performance optimization, and analytics
monitoring systems for the intelligent compliance platform.
"""

import asyncio
from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock

import pytest

from services.ai.analytics_monitor import AIAnalyticsMonitor, AlertLevel, MetricType
from services.ai.performance_optimizer import (
    AIPerformanceOptimizer,
    OptimizationStrategy,
)
from services.ai.response_cache import AIResponseCache, ContentType


@pytest.mark.unit
@pytest.mark.ai
class TestAIResponseCache:
    """Test AI response caching functionality"""

    @pytest.fixture
    def cache_instance(self):
        """Create a cache instance for testing"""
        cache = AIResponseCache()
        cache.cache_manager = AsyncMock()
        return cache

    @pytest.mark.asyncio
    async def test_cache_key_generation(self, cache_instance):
        """Test cache key generation with different inputs"""

        prompt = "Generate ISO27001 recommendations"
        context = {
            "framework": "ISO27001",
            "business_context": {"industry": "Technology", "employee_count": 150},
        }

        key1 = cache_instance._generate_cache_key(prompt, context)
        key2 = cache_instance._generate_cache_key(prompt, context)

        # Same inputs should generate same key
        assert key1 == key2
        assert key1.startswith("ai_response:")
        assert len(key1.split(":")[1]) == 16  # 16-character hash

    @pytest.mark.asyncio
    async def test_content_type_classification(self, cache_instance):
        """Test content type classification for different responses"""

        # Test recommendation classification
        rec_response = "I recommend implementing access control policies"
        rec_type = cache_instance._classify_content_type(rec_response)
        assert rec_type == ContentType.RECOMMENDATION

        # Test policy classification
        policy_response = "This policy establishes governance procedures"
        policy_type = cache_instance._classify_content_type(policy_response)
        assert policy_type == ContentType.POLICY

        # Test workflow classification
        workflow_response = "Step 1: Define scope and objectives"
        workflow_type = cache_instance._classify_content_type(workflow_response)
        assert workflow_type == ContentType.WORKFLOW

    @pytest.mark.asyncio
    async def test_intelligent_ttl_calculation(self, cache_instance):
        """Test intelligent TTL calculation based on content characteristics"""

        # Test policy TTL (should be longer)
        policy_ttl = cache_instance._calculate_intelligent_ttl(
            ContentType.POLICY,
            "A" * 3000,
            {"framework": "GDPR"},
        )

        # Test general TTL (should be shorter)
        general_ttl = cache_instance._calculate_intelligent_ttl(
            ContentType.GENERAL,
            "A" * 500,
            {},
        )

        assert policy_ttl > general_ttl
        assert cache_instance.min_ttl <= policy_ttl <= cache_instance.max_ttl
        assert cache_instance.min_ttl <= general_ttl <= cache_instance.max_ttl

    @pytest.mark.asyncio
    async def test_cache_response_success(self, cache_instance):
        """Test successful response caching"""

        cache_instance.cache_manager.set.return_value = True

        prompt = "Test prompt"
        response = "Test response"
        context = {"content_type": "recommendation"}

        success = await cache_instance.cache_response(prompt, response, context)

        assert success is True
        cache_instance.cache_manager.set.assert_called_once()

    @pytest.mark.asyncio
    async def test_get_cached_response_hit(self, cache_instance):
        """Test cache hit scenario"""

        cached_data = {
            "response": "Cached response",
            "content_type": "recommendation",
            "cached_at": datetime.now(timezone.utc).isoformat(),
        }
        cache_instance.cache_manager.get.return_value = cached_data

        result = await cache_instance.get_cached_response("test prompt")

        assert result == cached_data
        assert cache_instance.metrics["hits"] == 1

    @pytest.mark.asyncio
    async def test_get_cached_response_miss(self, cache_instance):
        """Test cache miss scenario"""

        cache_instance.cache_manager.get.return_value = None

        result = await cache_instance.get_cached_response("test prompt")

        assert result is None
        assert cache_instance.metrics["misses"] == 1

    @pytest.mark.asyncio
    async def test_cache_metrics(self, cache_instance):
        """Test cache metrics calculation"""

        # Simulate some cache activity
        cache_instance.metrics["hits"] = 75
        cache_instance.metrics["misses"] = 25
        cache_instance.metrics["total_requests"] = 100

        metrics = await cache_instance.get_cache_metrics()

        assert metrics["hit_rate_percentage"] == 75.0
        assert metrics["total_hits"] == 75
        assert metrics["total_misses"] == 25


@pytest.mark.unit
@pytest.mark.ai
class TestAIPerformanceOptimizer:
    """Test AI performance optimization functionality"""

    @pytest.fixture
    def optimizer_instance(self):
        """Create an optimizer instance for testing"""
        return AIPerformanceOptimizer()

    @pytest.mark.asyncio
    async def test_prompt_optimization(self, optimizer_instance):
        """Test prompt optimization functionality"""

        long_prompt = (
            "Generate ISO 27001 recommendations with lots of redundant information " * 50,
        )
        context = {"framework": "ISO27001"}

        optimized = await optimizer_instance._optimize_prompt(long_prompt, context)

        # Optimized prompt should be shorter or equal
        assert len(optimized) <= len(long_prompt)
        # Should contain framework-specific optimizations (ISO 27001 -> ISO27001)
        assert "ISO27001" in optimized

    def test_optimization_strategy_selection(self, optimizer_instance):
        """Test optimization strategy selection logic"""

        # High priority should get parallel execution
        strategy = optimizer_instance._select_optimization_strategy(
            "test prompt",
            {"priority": 9},
            9,
        )
        assert strategy == OptimizationStrategy.PARALLEL_EXECUTION

        # Long prompts should get compression
        long_prompt = "A" * 3000
        strategy = optimizer_instance._select_optimization_strategy(long_prompt, {}, 1)
        assert strategy == OptimizationStrategy.PROMPT_COMPRESSION

    @pytest.mark.asyncio
    async def test_rate_limiting(self, optimizer_instance):
        """Test rate limiting functionality"""

        # First request should succeed immediately
        start_time = asyncio.get_event_loop().time()
        success = await optimizer_instance.apply_rate_limiting()
        end_time = asyncio.get_event_loop().time()

        assert success is True
        assert (end_time - start_time) < 0.1  # Should be very fast

        # Clean up
        optimizer_instance.release_rate_limit()

    @pytest.mark.asyncio
    async def test_performance_metrics_update(self, optimizer_instance):
        """Test performance metrics tracking"""

        initial_count = optimizer_instance.performance_metrics.request_count

        optimizer_instance.update_performance_metrics(1.5, 1000)

        assert optimizer_instance.performance_metrics.request_count == initial_count + 1
        assert optimizer_instance.performance_metrics.total_response_time == 1.5
        assert optimizer_instance.performance_metrics.token_usage == 1000

    @pytest.mark.asyncio
    async def test_concurrent_request_optimization(self, optimizer_instance):
        """Test concurrent request processing"""

        requests = [{"id": f"req_{i}", "prompt": f"test prompt {i}"} for i in range(5)]

        results = await optimizer_instance.optimize_concurrent_requests(requests)

        assert len(results) == 5
        assert all("status" in result for result in results)


@pytest.mark.unit
@pytest.mark.ai
class TestAIAnalyticsMonitor:
    """Test AI analytics and monitoring functionality"""

    @pytest.fixture
    def monitor_instance(self):
        """Create a monitor instance for testing"""
        return AIAnalyticsMonitor()

    @pytest.mark.asyncio
    async def test_metric_recording(self, monitor_instance):
        """Test metric recording functionality"""

        initial_count = len(monitor_instance.metrics)

        await monitor_instance.record_metric(
            MetricType.PERFORMANCE,
            "response_time_ms",
            1500.0,
            metadata={"framework": "ISO27001"},
        )

        assert len(monitor_instance.metrics) == initial_count + 1

        latest_metric = monitor_instance.metrics[-1]
        assert latest_metric.metric_type == MetricType.PERFORMANCE
        assert latest_metric.name == "response_time_ms"
        assert latest_metric.value == 1500.0

    @pytest.mark.asyncio
    async def test_alert_creation(self, monitor_instance):
        """Test alert creation for threshold violations"""

        initial_alerts = len(monitor_instance.alerts)

        # Record a high response time that should trigger an alert
        await monitor_instance.record_metric(
            MetricType.PERFORMANCE,
            "response_time_ms",
            6000.0,  # Above 5000ms threshold,
        )

        # Should have created an alert
        assert len(monitor_instance.alerts) > initial_alerts

        latest_alert = monitor_instance.alerts[-1]
        assert latest_alert.level == AlertLevel.WARNING
        assert "High Response Time" in latest_alert.title

    @pytest.mark.asyncio
    async def test_real_time_metrics(self, monitor_instance):
        """Test real-time metrics calculation"""

        # Add some test metrics
        datetime.now(timezone.utc)
        for i in range(10):
            await monitor_instance.record_metric(
                MetricType.PERFORMANCE,
                "response_time_ms",
                1000.0 + i * 100,
            )

        metrics = await monitor_instance.get_real_time_metrics()

        assert "metrics" in metrics
        assert "total_requests" in metrics["metrics"]
        assert metrics["metrics"]["total_requests"] >= 10

    @pytest.mark.asyncio
    async def test_usage_analytics(self, monitor_instance):
        """Test usage analytics generation"""

        # Add some test usage data
        frameworks = ["ISO27001", "GDPR", "SOC2"]
        for framework in frameworks:
            for _i in range(5):
                await monitor_instance.record_metric(
                    MetricType.USAGE,
                    "request",
                    1,
                    metadata={"framework": framework},
                )

        analytics = await monitor_instance.get_usage_analytics(7)

        assert "framework_usage" in analytics
        assert "total_requests" in analytics
        assert analytics["total_requests"] >= 15

    @pytest.mark.asyncio
    async def test_cost_analytics(self, monitor_instance):
        """Test cost analytics calculation"""

        # Add some cost metrics
        for i in range(10):
            await monitor_instance.record_metric(
                MetricType.COST,
                "cost_estimate",
                0.01 * (i + 1),
            )

        cost_analytics = await monitor_instance.get_cost_analytics(30)

        assert "cost_summary" in cost_analytics
        assert "total_cost" in cost_analytics["cost_summary"]
        assert cost_analytics["cost_summary"]["total_cost"] > 0

    @pytest.mark.asyncio
    async def test_alert_resolution(self, monitor_instance):
        """Test alert resolution functionality"""

        # Create an alert
        await monitor_instance._create_alert(
            AlertLevel.WARNING,
            "Test Alert",
            "Test description",
        )

        alert_id = monitor_instance.alerts[-1].id

        # Resolve the alert
        success = await monitor_instance.resolve_alert(alert_id)

        assert success is True
        assert monitor_instance.alerts[-1].resolved is True

    @pytest.mark.asyncio
    async def test_dashboard_data_compilation(self, monitor_instance):
        """Test comprehensive dashboard data generation"""

        # Add some test data
        await monitor_instance.record_metric(
            MetricType.PERFORMANCE,
            "response_time_ms",
            1200.0,
        )
        await monitor_instance.record_metric(MetricType.COST, "cost_estimate", 0.05)

        dashboard = await monitor_instance.get_dashboard_data()

        assert "real_time" in dashboard
        assert "usage_analytics" in dashboard
        assert "cost_analytics" in dashboard
        assert "quality_metrics" in dashboard
        assert "system_health" in dashboard

    def test_health_status_calculation(self, monitor_instance):
        """Test system health status calculation"""

        # Test excellent health
        status = monitor_instance._calculate_health_status(1000, 0.5, 80.0)
        assert status == "excellent"

        # Test poor health
        status = monitor_instance._calculate_health_status(3000, 10.0, 30.0)
        assert status == "poor"

        # Test good health
        status = monitor_instance._calculate_health_status(2000, 0.5, 80.0)
        assert status == "good"


@pytest.mark.unit
@pytest.mark.ai
class TestSmartEvidenceCollector:
    """Test smart evidence collection functionality"""

    @pytest.fixture
    def collector_instance(self):
        from services.ai.smart_evidence_collector import SmartEvidenceCollector

        return SmartEvidenceCollector()

    @pytest.mark.asyncio
    async def test_evidence_requirements_generation(self, collector_instance):
        """Test evidence requirements generation for different frameworks"""

        business_context = {"industry": "Technology", "employee_count": 150}

        # Test ISO27001 requirements
        iso_requirements = await collector_instance._generate_evidence_requirements(
            "ISO27001",
            business_context,
        )

        assert len(iso_requirements) > 0
        assert any(req["control_id"] == "A.5.1.1" for req in iso_requirements)
        assert any(req["evidence_type"] == "policy_document" for req in iso_requirements)

    def test_evidence_gap_analysis(self, collector_instance):
        """Test evidence gap analysis"""

        requirements = [
            {"control_id": "A.5.1.1", "evidence_type": "policy_document"},
            {"control_id": "A.9.1.1", "evidence_type": "policy_document"},
            {"control_id": "A.12.4.1", "evidence_type": "log_analysis"},
        ]

        existing_evidence = [
            {"control_id": "A.5.1.1", "evidence_type": "policy_document"},
        ]

        gaps = collector_instance._analyze_evidence_gaps(
            requirements,
            existing_evidence,
        )

        assert len(gaps) == 2
        assert any(gap["control_id"] == "A.9.1.1" for gap in gaps)
        assert any(gap["control_id"] == "A.12.4.1" for gap in gaps)

    def test_task_priority_calculation(self, collector_instance):
        """Test task priority calculation"""

        from services.ai.smart_evidence_collector import EvidencePriority

        business_context = {"employee_count": 100}

        # High priority control
        high_priority_gap = {
            "control_id": "A.5.1.1",
            "evidence_type": "policy_document",
        }
        priority = collector_instance._calculate_task_priority(
            high_priority_gap,
            business_context,
            "ISO27001",
        )
        assert priority == EvidencePriority.CRITICAL

        # Training record (lower priority)
        low_priority_gap = {"control_id": "A.7.2.2", "evidence_type": "training_record"}
        priority = collector_instance._calculate_task_priority(
            low_priority_gap,
            business_context,
            "ISO27001",
        )
        assert priority == EvidencePriority.LOW

    def test_effort_estimation(self, collector_instance):
        """Test effort estimation for different evidence types"""

        business_context = {"employee_count": 50}  # Small organization

        # Policy document effort
        policy_effort = collector_instance._estimate_base_effort(
            "policy_document",
            business_context,
        )
        assert policy_effort > 0

        # System configuration effort
        config_effort = collector_instance._estimate_base_effort(
            "system_configuration",
            business_context,
        )
        assert config_effort > 0

        # Small org should have reduced effort
        large_org_context = {"employee_count": 1500}
        large_org_effort = collector_instance._estimate_base_effort(
            "policy_document",
            large_org_context,
        )
        assert large_org_effort > policy_effort

    @pytest.mark.asyncio
    async def test_collection_plan_creation(self, collector_instance):
        """Test complete collection plan creation"""

        business_context = {
            "company_name": "Test Corp",
            "industry": "Technology",
            "employee_count": 100,
        }

        plan = await collector_instance.create_collection_plan(
            business_profile_id="test_profile",
            framework="ISO27001",
            business_context=business_context,
            target_completion_weeks=8,
        )

        assert plan.framework == "ISO27001"
        assert plan.total_tasks > 0
        assert plan.estimated_total_hours > 0
        assert len(plan.tasks) > 0
        assert "automation_percentage" in plan.automation_opportunities

    @pytest.mark.asyncio
    async def test_task_status_update(self, collector_instance):
        """Test task status updates"""

        from services.ai.smart_evidence_collector import CollectionStatus

        # Create a plan first
        business_context = {"industry": "Technology", "employee_count": 100}
        plan = await collector_instance.create_collection_plan(
            "test_profile",
            "ISO27001",
            business_context,
        )

        # Update first task status
        if plan.tasks:
            task_id = plan.tasks[0].task_id
            success = await collector_instance.update_task_status(
                plan.plan_id,
                task_id,
                CollectionStatus.COMPLETED,
                "Task completed successfully",
            )

            assert success is True
            assert plan.tasks[0].status == CollectionStatus.COMPLETED


@pytest.mark.unit
@pytest.mark.ai
class TestQualityMonitor:
    """Test AI quality monitoring functionality"""

    @pytest.fixture
    def monitor_instance(self):
        from services.ai.quality_monitor import AIQualityMonitor

        return AIQualityMonitor()

    @pytest.mark.asyncio
    async def test_response_quality_assessment(self, monitor_instance):
        """Test comprehensive response quality assessment"""

        response_text = """
        To implement ISO 27001 access control policy, you should:
        1. Establish clear access control procedures
        2. Define user roles and responsibilities
        3. Implement regular access reviews
        4. Monitor access control effectiveness

        This policy should align with Annex A.9.1.1 requirements and include
        specific controls for user access management.
        """

        prompt = "How do I implement ISO 27001 access control policy?"
        context = {"framework": "ISO27001", "content_type": "recommendation"}

        assessment = await monitor_instance.assess_response_quality(
            response_id="test_response_001",
            response_text=response_text,
            prompt=prompt,
            context=context,
        )

        assert assessment.response_id == "test_response_001"
        assert assessment.overall_score > 0
        assert len(assessment.dimension_scores) == 6  # All quality dimensions
        assert assessment.quality_level is not None

    def test_accuracy_scoring(self, monitor_instance):
        """Test accuracy scoring for different response types"""

        # High accuracy response with framework keywords
        accurate_response = (
            "ISO 27001 requires implementing ISMS controls for information security management"
        )
        context = {"framework": "ISO27001"}

        accuracy_score = monitor_instance._score_accuracy(
            accurate_response,
            "What is ISO 27001?",
            context,
        )
        assert accuracy_score >= 7.0

        # Low accuracy response without framework alignment
        inaccurate_response = "Just use antivirus software"
        low_score = monitor_instance._score_accuracy(
            inaccurate_response,
            "What is ISO 27001?",
            context,
        )
        assert low_score < accuracy_score

    def test_relevance_scoring(self, monitor_instance):
        """Test relevance scoring based on prompt-response alignment"""

        prompt = "How to implement access control policy?"
        relevant_response = "To implement access control policy, define user roles, establish procedures, and monitor access"

        relevance_score = monitor_instance._score_relevance(relevant_response, prompt)
        assert relevance_score >= 7.0

        # Irrelevant response
        irrelevant_response = "The weather is nice today"
        low_score = monitor_instance._score_relevance(irrelevant_response, prompt)
        assert low_score < relevance_score

    def test_user_feedback_incorporation(self, monitor_instance):
        """Test incorporation of user feedback into quality scores"""

        from services.ai.quality_monitor import (
            FeedbackType,
            QualityDimension,
            QualityScore,
            ResponseFeedback,
        )

        # Create initial dimension scores
        dimension_scores = {
            QualityDimension.ACCURACY: QualityScore(
                QualityDimension.ACCURACY,
                7.0,
                0.8,
            ),
            QualityDimension.RELEVANCE: QualityScore(
                QualityDimension.RELEVANCE,
                6.0,
                0.8,
            ),
        }

        # Create positive feedback
        positive_feedback = ResponseFeedback(
            feedback_id="fb_001",
            response_id="resp_001",
            user_id="user_001",
            feedback_type=FeedbackType.DETAILED_RATING,
            rating=4.5,  # High rating,
        )

        # Incorporate feedback
        updated_scores = monitor_instance._incorporate_user_feedback(
            dimension_scores,
            positive_feedback,
        )

        # Scores should be adjusted upward
        assert updated_scores[QualityDimension.ACCURACY].score > 7.0
        assert updated_scores[QualityDimension.RELEVANCE].score > 6.0

    def test_quality_level_determination(self, monitor_instance):
        """Test quality level determination from scores"""

        from services.ai.quality_monitor import QualityLevel

        # Excellent quality
        excellent_level = monitor_instance._determine_quality_level(9.0)
        assert excellent_level == QualityLevel.EXCELLENT

        # Good quality
        good_level = monitor_instance._determine_quality_level(7.5)
        assert good_level == QualityLevel.GOOD

        # Poor quality
        poor_level = monitor_instance._determine_quality_level(2.0)
        assert poor_level == QualityLevel.POOR

    def test_improvement_suggestions_generation(self, monitor_instance):
        """Test generation of improvement suggestions"""

        from services.ai.quality_monitor import QualityDimension, QualityScore

        # Create low scores for testing
        low_dimension_scores = {
            QualityDimension.ACCURACY: QualityScore(
                QualityDimension.ACCURACY,
                4.0,
                0.8,
            ),
            QualityDimension.CLARITY: QualityScore(QualityDimension.CLARITY, 3.0, 0.8),
        }

        suggestions = monitor_instance._generate_improvement_suggestions(
            low_dimension_scores,
            "test response",
            {},
        )

        assert len(suggestions) >= 2
        assert any("framework-specific" in suggestion.lower() for suggestion in suggestions)
        assert any("clearer language" in suggestion.lower() for suggestion in suggestions)

    @pytest.mark.asyncio
    async def test_quality_trends_calculation(self, monitor_instance):
        """Test quality trends calculation over time"""

        # Add some mock assessments
        from datetime import datetime

        from services.ai.quality_monitor import QualityAssessment, QualityLevel

        # Create assessments over different days
        for i in range(5):
            assessment = QualityAssessment(
                assessment_id=f"assessment_{i}",
                response_id=f"response_{i}",
                overall_score=7.0 + i * 0.5,
                quality_level=QualityLevel.GOOD,
                dimension_scores={},
                feedback_count=1,
                improvement_suggestions=[],
                timestamp=datetime.now(timezone.utc) - timedelta(days=i),
            )
            monitor_instance.quality_assessments[f"response_{i}"] = assessment

        trends = await monitor_instance.get_quality_trends(7)

        assert "total_assessments" in trends
        assert "average_quality_score" in trends
        assert trends["total_assessments"] == 5
