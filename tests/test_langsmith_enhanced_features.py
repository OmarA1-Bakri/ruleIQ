"""

# Constants

FIVE_MINUTES_SECONDS = 300

DEFAULT_RETRIES = 5


Test enhanced LangSmith features including evaluation, feedback, and performance benchmarking.
"""

import pytest
import asyncio
from unittest.mock import Mock, patch, AsyncMock
from typing import Dict, Any
from datetime import datetime
from config.langsmith_config import LangSmithConfig, with_langsmith_tracing
from config.langsmith_evaluators import LangSmithEvaluator, EvaluationMetrics, PerformanceBenchmark
from config.langsmith_feedback import (
    LangSmithFeedbackCollector,
    FeedbackItem,
    FeedbackType,
    FeedbackAnalyzer,
)

from tests.test_constants import HTTP_INTERNAL_SERVER_ERROR, MAX_RETRIES


class TestEnhancedTracing:
    """Test enhanced tracing features with custom naming and metadata."""

    @pytest.mark.asyncio
    async def test_custom_run_naming(self, monkeypatch):
        """Test that custom run names are properly set."""
        monkeypatch.setenv("LANGCHAIN_TRACING_V2", "true")
        monkeypatch.setenv("LANGCHAIN_API_KEY", "test_key")
        traced_runs = []

        @with_langsmith_tracing("test_operation", custom_name="Custom Test Run")
        async def test_function(state: Dict[str, Any]):
            return {"result": "success"}

        with patch("langchain_core.tracers.context.tracing_v2_enabled") as mock_tracing:

            def capture_run(*args, **kwargs):
                traced_runs.append(
                    {
                        "run_name": kwargs.get("run_name"),
                        "tags": kwargs.get("tags", []),
                        "metadata": kwargs.get("metadata", {}),
                    }
                )
                mock_context = Mock()
                mock_context.__enter__ = Mock(return_value=None)
                mock_context.__exit__ = Mock(return_value=None)
                return mock_context

            mock_tracing.side_effect = capture_run
            result = await test_function(state={"session_id": "test123"})
            assert len(traced_runs) == 1
            assert "Custom Test Run:test123" in traced_runs[0]["run_name"]
            assert "test_operation" in traced_runs[0]["tags"]

    @pytest.mark.asyncio
    async def test_enhanced_metadata_collection(self, monkeypatch):
        """Test that enhanced metadata is properly collected."""
        monkeypatch.setenv("LANGCHAIN_TRACING_V2", "true")
        monkeypatch.setenv("LANGCHAIN_API_KEY", "test_key")
        monkeypatch.setenv("ENVIRONMENT", "production")
        monkeypatch.setenv("APP_VERSION", "1.2.0")
        traced_metadata = {}

        @with_langsmith_tracing("test_operation")
        async def test_function(state: Dict[str, Any]):
            return {"result": "success"}

        with patch("langchain_core.tracers.context.tracing_v2_enabled") as mock_tracing:

            def capture_metadata(*args, **kwargs):
                traced_metadata.update(kwargs.get("metadata", {}))
                mock_context = Mock()
                mock_context.__enter__ = Mock(return_value=None)
                mock_context.__exit__ = Mock(return_value=None)
                return mock_context

            mock_tracing.side_effect = capture_metadata
            state = {
                "session_id": "sess123",
                "user_id": "user456",
                "business_profile_id": "prof789",
                "current_phase": "testing",
            }
            result = await test_function(state=state)
            assert traced_metadata["session_id"] == "sess123"
            assert traced_metadata["user_id"] == "user456"
            assert traced_metadata["business_profile_id"] == "prof789"
            assert traced_metadata["phase"] == "testing"
            assert "timestamp" in traced_metadata
            assert traced_metadata["status"] == "success"

    @pytest.mark.asyncio
    async def test_performance_tracking(self, monkeypatch):
        """Test that performance metrics are tracked."""
        monkeypatch.setenv("LANGCHAIN_TRACING_V2", "true")
        monkeypatch.setenv("LANGCHAIN_API_KEY", "test_key")
        traced_metadata = {}

        @with_langsmith_tracing("test_operation")
        async def slow_function():
            await asyncio.sleep(0.1)
            return {"result": "done"}

        with patch("langchain_core.tracers.context.tracing_v2_enabled") as mock_tracing:

            def capture_metadata(*args, **kwargs):
                traced_metadata.update(kwargs.get("metadata", {}))
                mock_context = Mock()
                mock_context.__enter__ = Mock(return_value=None)
                mock_context.__exit__ = Mock(return_value=None)
                return mock_context

            mock_tracing.side_effect = capture_metadata
            result = await slow_function()
            assert "execution_time_seconds" in traced_metadata
            assert traced_metadata["execution_time_seconds"] >= 0.1
            assert traced_metadata["status"] == "success"

    @pytest.mark.asyncio
    async def test_error_tracking(self, monkeypatch):
        """Test that errors are properly tracked in metadata."""
        monkeypatch.setenv("LANGCHAIN_TRACING_V2", "true")
        monkeypatch.setenv("LANGCHAIN_API_KEY", "test_key")
        traced_metadata = {}
        traced_tags = []

        @with_langsmith_tracing("test_operation")
        async def failing_function():
            raise ValueError("Test error")

        with patch("langchain_core.tracers.context.tracing_v2_enabled") as mock_tracing:

            def capture_trace(*args, **kwargs):
                traced_metadata.update(kwargs.get("metadata", {}))
                traced_tags.extend(kwargs.get("tags", []))
                mock_context = Mock()
                mock_context.__enter__ = Mock(return_value=None)
                mock_context.__exit__ = Mock(return_value=None)
                return mock_context

            mock_tracing.side_effect = capture_trace
            with pytest.raises(ValueError, match="Test error"):
                await failing_function()
            assert traced_metadata.get("status") == "error"
            assert traced_metadata.get("error_type") == "ValueError"
            assert "Test error" in traced_metadata.get("error_message", "")
            assert "error" in traced_tags


class TestEvaluationMetrics:
    """Test evaluation metrics functionality."""

    def test_compliance_evaluation(self):
        """Test compliance run evaluation."""
        run_data = {
            "metadata": {"execution_time_seconds": 0.5, "status": "success"},
            "outputs": {
                "compliance_results": [
                    {"status": "passed"},
                    {"status": "passed"},
                    {"status": "failed"},
                    {"status": "passed"},
                ]
            },
        }
        metrics = LangSmithEvaluator.evaluate_compliance_run(run_data)
        assert metrics.latency_ms == HTTP_INTERNAL_SERVER_ERROR
        assert metrics.compliance_score == 75.0
        assert metrics.error_rate == 0.0

    def test_evidence_evaluation(self):
        """Test evidence run evaluation."""
        run_data = {
            "metadata": {"execution_time_seconds": 0.3},
            "outputs": {
                "evidence_items": [
                    {
                        "source": "doc1",
                        "verification_status": "verified",
                        "confidence_score": 0.9,
                        "timestamp": "2024-01-01",
                    },
                    {"source": "doc2", "verification_status": "pending"},
                ]
            },
        }
        metrics = LangSmithEvaluator.evaluate_evidence_run(run_data)
        assert metrics.latency_ms == FIVE_MINUTES_SECONDS
        assert metrics.evidence_quality == 62.5
        assert metrics.error_rate == 0.0

    def test_rag_evaluation(self):
        """Test RAG run evaluation with cost calculation."""
        run_data = {
            "metadata": {"execution_time_seconds": 1.2, "model": "gpt-3.5-turbo"},
            "outputs": {"llm_output": "A" * 1000},
        }
        metrics = LangSmithEvaluator.evaluate_rag_run(run_data)
        assert metrics.latency_ms == 1200
        assert metrics.token_count == 250
        assert metrics.cost_usd > 0
        assert metrics.error_rate == 0.0

    def test_metrics_aggregation(self):
        """Test aggregation of multiple metrics."""
        metrics_list = [
            EvaluationMetrics(latency_ms=100, accuracy=0.9, error_rate=0.0),
            EvaluationMetrics(latency_ms=150, accuracy=0.85, error_rate=0.1),
            EvaluationMetrics(latency_ms=120, accuracy=0.95, error_rate=0.0),
        ]
        aggregated = LangSmithEvaluator.aggregate_metrics(metrics_list)
        assert aggregated["total_runs"] == MAX_RETRIES
        assert aggregated["avg_latency_ms"] == pytest.approx(123.33, rel=0.01)
        assert aggregated["avg_accuracy"] == pytest.approx(0.9, rel=0.01)
        assert aggregated["error_rate"] == pytest.approx(0.033, rel=0.01)

    def test_performance_benchmark(self):
        """Test performance benchmarking."""
        benchmark = PerformanceBenchmark()
        baseline = EvaluationMetrics(latency_ms=100, accuracy=0.9, error_rate=0.05, cost_usd=0.01)
        benchmark.set_baseline("test_op", baseline)
        current = EvaluationMetrics(latency_ms=90, accuracy=0.95, error_rate=0.03, cost_usd=0.008)
        comparison = benchmark.compare_to_baseline("test_op", current)
        assert comparison["latency_change_percent"] == pytest.approx(-10.0)
        assert comparison["latency_status"] == "improved"
        assert comparison["accuracy_change_percent"] == pytest.approx(5.55, rel=0.01)
        assert comparison["accuracy_status"] == "improved"
        assert comparison["error_rate_change"] == -0.02
        assert comparison["error_status"] == "improved"
        assert comparison["cost_change_percent"] == pytest.approx(-20.0)
        assert comparison["cost_status"] == "improved"


class TestFeedbackCollection:
    """Test feedback collection system."""

    def test_feedback_collection(self):
        """Test basic feedback collection."""
        collector = LangSmithFeedbackCollector()
        feedback1 = collector.collect_feedback(
            run_id="run1", feedback_type=FeedbackType.THUMBS_UP, value=True, user_id="user1"
        )
        feedback2 = collector.collect_feedback(
            run_id="run2", feedback_type=FeedbackType.RATING, value=4, user_id="user1"
        )
        feedback3 = collector.collect_feedback(
            run_id="run3",
            feedback_type=FeedbackType.CORRECTION,
            value="Corrected output text",
            user_id="user2",
        )
        assert len(collector.feedback_queue) == MAX_RETRIES
        assert collector.feedback_stats["total_collected"] == MAX_RETRIES
        assert collector.feedback_stats["by_type"]["thumbs_up"] == 1
        assert collector.feedback_stats["by_type"]["rating"] == 1
        assert collector.feedback_stats["by_type"]["correction"] == 1
        assert collector.feedback_stats["by_user"]["user1"] == 2
        assert collector.feedback_stats["by_user"]["user2"] == 1

    def test_invalid_rating_feedback(self):
        """Test validation of rating feedback."""
        collector = LangSmithFeedbackCollector()
        collector.collect_feedback(
            run_id="run1", feedback_type=FeedbackType.RATING, value=3, user_id="user1"
        )
        with pytest.raises(ValueError, match="Rating must be between 1 and 5"):
            collector.collect_feedback(
                run_id="run2", feedback_type=FeedbackType.RATING, value=6, user_id="user1"
            )
        with pytest.raises(ValueError, match="Rating must be between 1 and 5"):
            collector.collect_feedback(
                run_id="run3", feedback_type=FeedbackType.RATING, value=0, user_id="user1"
            )

    def test_feedback_summary(self):
        """Test feedback summary generation."""
        collector = LangSmithFeedbackCollector()
        for i in range(5):
            collector.collect_feedback(
                run_id=f"run{i}", feedback_type=FeedbackType.THUMBS_UP, value=True, user_id="user1"
            )
        for i in range(3):
            collector.collect_feedback(
                run_id=f"run{i + 5}", feedback_type=FeedbackType.RATING, value=4, user_id="user2"
            )
        summary = collector.get_feedback_summary()
        assert summary["total_collected"] == 8
        assert summary["pending_submission"] == 8
        assert summary["by_type"]["thumbs_up"] == DEFAULT_RETRIES
        assert summary["by_type"]["rating"] == MAX_RETRIES
        assert summary["top_contributors"][0] == ("user1", 5)
        assert summary["top_contributors"][1] == ("user2", 3)

    def test_feedback_analysis(self):
        """Test feedback trend analysis."""
        feedback_items = [
            FeedbackItem(
                run_id="run1", feedback_type=FeedbackType.THUMBS_UP, value=True, user_id="user1"
            ),
            FeedbackItem(
                run_id="run2", feedback_type=FeedbackType.THUMBS_DOWN, value=False, user_id="user2"
            ),
            FeedbackItem(
                run_id="run3", feedback_type=FeedbackType.RATING, value=4, user_id="user3"
            ),
            FeedbackItem(
                run_id="run4", feedback_type=FeedbackType.RATING, value=2, user_id="user4"
            ),
            FeedbackItem(
                run_id="run5",
                feedback_type=FeedbackType.CORRECTION,
                value="Fixed output",
                user_id="user5",
            ),
        ]
        analysis = FeedbackAnalyzer.analyze_feedback_trends(feedback_items)
        assert analysis["total_feedback"] == DEFAULT_RETRIES
        assert analysis["sentiment"]["positive"] == 2
        assert analysis["sentiment"]["negative"] == 2
        assert analysis["average_rating"] == MAX_RETRIES
        assert analysis["correction_rate"] == 20.0

    def test_improvement_recommendations(self):
        """Test generation of improvement recommendations."""
        analysis1 = {
            "sentiment": {"positive": 10, "negative": 20},
            "average_rating": 2.5,
            "correction_rate": 15,
            "flag_rate": 8,
        }
        recommendations1 = FeedbackAnalyzer.generate_improvement_recommendations(analysis1)
        assert any("negative feedback" in r for r in recommendations1)
        assert any("Low average rating" in r for r in recommendations1)
        assert any("correction rate" in r for r in recommendations1)
        assert any("flagged" in r for r in recommendations1)
        analysis2 = {
            "sentiment": {"positive": 30, "negative": 5},
            "average_rating": 4.5,
            "correction_rate": 2,
            "flag_rate": 1,
        }
        recommendations2 = FeedbackAnalyzer.generate_improvement_recommendations(analysis2)
        assert any("performing well" in r for r in recommendations2)


class TestCustomTagging:
    """Test custom tagging functionality."""

    def test_custom_tag_addition(self, monkeypatch):
        """Test adding custom tags for filtering."""
        monkeypatch.setenv("ENVIRONMENT", "production")
        monkeypatch.setenv("APP_VERSION", "1.2.0")
        base_tags = ["operation:test"]
        enhanced_tags = LangSmithConfig.add_custom_tags(
            base_tags, environment="production", customer="enterprise", priority="high"
        )
        assert "operation:test" in enhanced_tags
        assert "environment:production" in enhanced_tags
        assert "customer:enterprise" in enhanced_tags
        assert "priority:high" in enhanced_tags
        assert "env:production" in enhanced_tags
        assert "version:1.2.0" in enhanced_tags
        assert "tier:critical" in enhanced_tags

    def test_filter_query_creation(self):
        """Test creation of filter queries for LangSmith."""
        from datetime import timedelta

        start_date = datetime(2024, 1, 1)
        end_date = datetime(2024, 1, 31)
        query = LangSmithConfig.create_filter_query(
            session_id="sess123",
            user_id="user456",
            phase="compliance_check",
            status="success",
            date_range=(start_date, end_date),
        )
        assert "session:sess123" in query["tags"]
        assert "user:user456" in query["tags"]
        assert "phase:compliance_check" in query["tags"]
        assert query["metadata.status"] == "success"
        assert query["date_range"]["start"] == "2024-01-01T00:00:00"
        assert query["date_range"]["end"] == "2024-01-31T00:00:00"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
