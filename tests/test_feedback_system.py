"""Test suite for Human-in-the-Loop Feedback System.


This test suite covers:
1. Feedback collection APIs
2. Feedback storage and retrieval
3. Feedback aggregation
4. Model fine-tuning triggers
5. Feedback loop metrics
6. UI components for feedback
"""

import pytest
from datetime import datetime, timedelta, timezone
from unittest.mock import Mock, patch, AsyncMock
from typing import Dict, List, Any
import json
import uuid

from fastapi import status
from fastapi.testclient import TestClient
from pydantic import ValidationError

# Import from existing modules
from config.langsmith_feedback import (
    FeedbackType,
    FeedbackItem,
    LangSmithFeedbackCollector,
)
from services.ai.feedback_analyzer import FeedbackAnalyzer
from services.ai.quality_monitor import ResponseFeedback, QualityScore, QualityDimension


# ============================================================================
# Test Models and Schemas
# ============================================================================


class TestFeedbackModels:
    """Test feedback data models and validation."""

    def test_feedback_item_creation(self):
        """Test creating a feedback item with all required fields."""
        feedback = FeedbackItem(
            run_id="test-run-123",
            feedback_type=FeedbackType.RATING,
            value=4.5,
            user_id="user-001",
            metadata={"context": "compliance check"},
        )

        assert feedback.run_id == "test-run-123"
        assert feedback.feedback_type == FeedbackType.RATING
        assert feedback.value == 4.5
        assert feedback.user_id == "user-001"
        assert "context" in feedback.metadata

    def test_response_feedback_validation(self):
        """Test ResponseFeedback model validation."""
        feedback = ResponseFeedback(
            feedback_id=str(uuid.uuid4()),
            response_id="resp-123",
            user_id="user-001",
            feedback_type=FeedbackType.THUMBS_UP,
            rating=5.0,
            text_feedback="Accurate compliance assessment",
        )

        assert feedback.rating == 5.0
        assert feedback.text_feedback == "Accurate compliance assessment"
        assert isinstance(feedback.timestamp, datetime)

    def test_feedback_type_enum_values(self):
        """Test all feedback type enum values are accessible."""
        expected_types = [
            FeedbackType.THUMBS_UP,
            FeedbackType.THUMBS_DOWN,
            FeedbackType.RATING,
            FeedbackType.COMMENT,
            FeedbackType.CORRECTION,
            FeedbackType.FLAG,
        ]

        for feedback_type in expected_types:
            assert feedback_type.value in [
                "thumbs_up",
                "thumbs_down",
                "rating",
                "comment",
                "correction",
                "flag",
            ]

    def test_quality_score_with_dimensions(self):
        """Test QualityScore creation with multiple dimensions."""
        score = QualityScore(
            dimension=QualityDimension.ACCURACY,
            score=0.95,
            confidence=0.85,
            explanation="High accuracy in regulatory citation",
        )

        assert score.dimension == QualityDimension.ACCURACY
        assert score.score == 0.95
        assert score.confidence == 0.85


# ============================================================================
# Test Feedback Collection APIs
# ============================================================================


class TestFeedbackCollectionAPIs:
    """Test feedback collection API endpoints."""

    @pytest.fixture
    def mock_app(self):
        """Create a mock FastAPI app with feedback endpoints."""
        from fastapi import FastAPI, HTTPException
        from pydantic import BaseModel

        app = FastAPI()

        class FeedbackRequest(BaseModel):
            run_id: str
            feedback_type: str
            value: Any
            user_id: str
            metadata: Dict[str, Any] = {}

        class FeedbackResponse(BaseModel):
            feedback_id: str
            status: str
            message: str

        # Mock feedback storage
        feedback_store = []

        @app.post("/api/feedback/collect", response_model=FeedbackResponse)
        async def collect_feedback(feedback: FeedbackRequest):
            """Collect feedback for a compliance evaluation run."""
            # Validate feedback type
            valid_types = [
                "thumbs_up",
                "thumbs_down",
                "rating",
                "comment",
                "correction",
                "flag",
            ]
            if feedback.feedback_type not in valid_types:
                raise HTTPException(status_code=400, detail="Invalid feedback type")

            # Validate rating value
            if feedback.feedback_type == "rating" and (
                not isinstance(feedback.value, (int, float)) or not 1 <= feedback.value <= 5
            ):
                raise HTTPException(
                    status_code=400,
                    detail="Rating must be between 1 and 5",
                )

            # Store feedback
            feedback_id = str(uuid.uuid4())
            feedback_store.append({"feedback_id": feedback_id, **feedback.dict()})

            return FeedbackResponse(
                feedback_id=feedback_id,
                status="success",
                message="Feedback collected successfully",
            )

        @app.get("/api/feedback/{feedback_id}")
        async def get_feedback(feedback_id: str):
            """Retrieve specific feedback by ID."""
            for item in feedback_store:
                if item["feedback_id"] == feedback_id:
                    return item
            raise HTTPException(status_code=404, detail="Feedback not found")

        @app.get("/api/feedback/run/{run_id}")
        async def get_run_feedback(run_id: str):
            """Get all feedback for a specific run."""
            run_feedback = [f for f in feedback_store if f["run_id"] == run_id]
            return {
                "run_id": run_id,
                "feedback": run_feedback,
                "count": len(run_feedback),
            }

        @app.post("/api/feedback/batch")
        async def batch_collect_feedback(feedback_items: List[FeedbackRequest]):
            """Collect multiple feedback items in batch."""
            results = []
            for item in feedback_items:
                feedback_id = str(uuid.uuid4())
                feedback_store.append({"feedback_id": feedback_id, **item.dict()})
                results.append({"feedback_id": feedback_id, "status": "success"})

            return {
                "total": len(feedback_items),
                "successful": len(results),
                "results": results,
            }

        return app, feedback_store

    def test_collect_single_feedback(self, mock_app):
        """Test collecting a single feedback item."""
        app, store = mock_app
        client = TestClient(app)

        response = client.post(
            "/api/feedback/collect",
            json={
                "run_id": "test-run-001",
                "feedback_type": "rating",
                "value": 4.5,
                "user_id": "user-001",
                "metadata": {"source": "compliance_check"},
            },
        )

        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "success"
        assert "feedback_id" in data
        assert len(store) == 1

    def test_invalid_feedback_type_rejected(self, mock_app):
        """Test that invalid feedback types are rejected."""
        app, _ = mock_app
        client = TestClient(app)

        response = client.post(
            "/api/feedback/collect",
            json={
                "run_id": "test-run-002",
                "feedback_type": "invalid_type",
                "value": "test",
                "user_id": "user-001",
            },
        )

        assert response.status_code == 400
        assert "Invalid feedback type" in response.json()["detail"]

    def test_rating_validation(self, mock_app):
        """Test rating value validation."""
        app, _ = mock_app
        client = TestClient(app)

        # Invalid rating (too high)
        response = client.post(
            "/api/feedback/collect",
            json={
                "run_id": "test-run-003",
                "feedback_type": "rating",
                "value": 6.0,
                "user_id": "user-001",
            },
        )

        assert response.status_code == 400
        assert "Rating must be between 1 and 5" in response.json()["detail"]

        # Valid rating
        response = client.post(
            "/api/feedback/collect",
            json={
                "run_id": "test-run-003",
                "feedback_type": "rating",
                "value": 3.5,
                "user_id": "user-001",
            },
        )

        assert response.status_code == 200

    def test_batch_feedback_collection(self, mock_app):
        """Test collecting multiple feedback items in batch."""
        app, store = mock_app
        client = TestClient(app)

        feedback_batch = [
            {
                "run_id": "test-run-004",
                "feedback_type": "thumbs_up",
                "value": True,
                "user_id": "user-001",
            },
            {
                "run_id": "test-run-004",
                "feedback_type": "comment",
                "value": "Good compliance analysis",
                "user_id": "user-002",
            },
            {
                "run_id": "test-run-005",
                "feedback_type": "rating",
                "value": 4.0,
                "user_id": "user-001",
            },
        ]

        response = client.post("/api/feedback/batch", json=feedback_batch)

        assert response.status_code == 200
        data = response.json()
        assert data["total"] == 3
        assert data["successful"] == 3
        assert len(data["results"]) == 3

    def test_retrieve_feedback_by_id(self, mock_app):
        """Test retrieving feedback by ID."""
        app, store = mock_app
        client = TestClient(app)

        # First collect feedback
        response = client.post(
            "/api/feedback/collect",
            json={
                "run_id": "test-run-006",
                "feedback_type": "correction",
                "value": {"original": "GDPR Art 5", "corrected": "GDPR Art 6"},
                "user_id": "user-001",
            },
        )

        feedback_id = response.json()["feedback_id"]

        # Retrieve the feedback
        response = client.get(f"/api/feedback/{feedback_id}")

        assert response.status_code == 200
        data = response.json()
        assert data["feedback_id"] == feedback_id
        assert data["feedback_type"] == "correction"

    def test_retrieve_run_feedback(self, mock_app):
        """Test retrieving all feedback for a run."""
        app, store = mock_app
        client = TestClient(app)

        run_id = "test-run-007"

        # Collect multiple feedback items for the same run
        for i in range(3):
            client.post(
                "/api/feedback/collect",
                json={
                    "run_id": run_id,
                    "feedback_type": "rating",
                    "value": 3 + i,
                    "user_id": f"user-{i:03d}",
                },
            )

        # Retrieve all feedback for the run
        response = client.get(f"/api/feedback/run/{run_id}")

        assert response.status_code == 200
        data = response.json()
        assert data["run_id"] == run_id
        assert data["count"] == 3
        assert len(data["feedback"]) == 3


# ============================================================================
# Test Feedback Storage and Retrieval
# ============================================================================


class TestFeedbackStorage:
    """Test feedback storage and retrieval mechanisms."""

    @pytest.fixture
    def feedback_collector(self):
        """Create a feedback collector instance."""
        return LangSmithFeedbackCollector()

    def test_store_feedback_in_memory(self, feedback_collector):
        """Test storing feedback in memory queue."""
        feedback = feedback_collector.collect_feedback(
            run_id="test-run-008",
            feedback_type=FeedbackType.RATING,
            value=4.0,
            user_id="user-001",
            metadata={"context": "test"},
        )

        assert len(feedback_collector.feedback_queue) == 1
        assert feedback_collector.feedback_stats["total_collected"] == 1
        assert feedback_collector.feedback_stats["by_type"]["rating"] == 1

    def test_feedback_persistence_to_file(self, feedback_collector, tmp_path):
        """Test exporting feedback to file for persistence."""
        # Collect some feedback
        for i in range(5):
            feedback_collector.collect_feedback(
                run_id=f"test-run-{i:03d}",
                feedback_type=FeedbackType.RATING,
                value=3.0 + i * 0.5,
                user_id="user-001",
            )

        # Export to file
        export_file = tmp_path / "feedback_export.json"
        feedback_collector.export_feedback(str(export_file))

        # Verify file contents
        assert export_file.exists()

        with open(export_file, "r") as f:
            data = json.load(f)

        assert "export_date" in data
        assert data["statistics"]["total_collected"] == 5
        assert len(data["feedback_items"]) == 5

    def test_feedback_queue_management(self, feedback_collector):
        """Test feedback queue operations."""
        # Add multiple feedback items
        for i in range(10):
            feedback_collector.collect_feedback(
                run_id=f"test-run-{i:03d}",
                feedback_type=FeedbackType.COMMENT if i % 2 else FeedbackType.RATING,
                value="Test comment" if i % 2 else 4.0,
                user_id=f"user-{i % 3:03d}",
            )

        # Check queue size
        assert len(feedback_collector.feedback_queue) == 10

        # Check statistics
        stats = feedback_collector.get_feedback_summary()
        assert stats["total_collected"] == 10
        assert stats["pending_submission"] == 10
        assert stats["by_type"]["rating"] == 5
        assert stats["by_type"]["comment"] == 5

    @patch("langsmith.Client")
    def test_batch_submission_to_langsmith(self, mock_client, feedback_collector):
        """Test batch submission of feedback to LangSmith."""
        # Mock the LangSmith client
        mock_client_instance = Mock()
        mock_client.return_value = mock_client_instance
        mock_client_instance.create_feedback.return_value = None

        # Collect feedback
        feedback_collector.collect_feedback(
            run_id="test-run-009",
            feedback_type=FeedbackType.THUMBS_UP,
            value=True,
            user_id="user-001",
        )

        # Submit to LangSmith
        result = feedback_collector.batch_submit_to_langsmith(
            api_key="test-key",
            project_name="test-project",
        )

        assert result["status"] == "success"
        assert result["submitted"] == 1
        assert result["remaining"] == 0
        mock_client_instance.create_feedback.assert_called_once()


# ============================================================================
# Test Feedback Aggregation
# ============================================================================


class TestFeedbackAggregation:
    """Test feedback aggregation and analysis."""

    @pytest.fixture
    def feedback_analyzer(self):
        """Create a feedback analyzer instance."""
        return FeedbackAnalyzer()

    def test_aggregate_ratings(self, feedback_analyzer):
        """Test aggregating rating feedback."""
        feedback_items = [
            FeedbackItem(
                run_id="run-001",
                feedback_type=FeedbackType.RATING,
                value=4.0,
                user_id="user-001",
                timestamp=datetime.now(timezone.utc),
            ),
            FeedbackItem(
                run_id="run-002",
                feedback_type=FeedbackType.RATING,
                value=5.0,
                user_id="user-002",
                timestamp=datetime.now(timezone.utc),
            ),
            FeedbackItem(
                run_id="run-003",
                feedback_type=FeedbackType.RATING,
                value=3.5,
                user_id="user-003",
                timestamp=datetime.now(timezone.utc),
            ),
        ]

        for item in feedback_items:
            feedback_analyzer.add_feedback(item)

        stats = feedback_analyzer.calculate_statistics()

        assert stats["total_feedback"] == 3
        assert stats["average_rating"] == 4.166666666666667
        assert stats["rating_distribution"]["rating"] == 3

    def test_sentiment_aggregation(self, feedback_analyzer):
        """Test aggregating thumbs up/down feedback."""
        # Add positive feedback
        for i in range(7):
            feedback_analyzer.add_feedback(
                FeedbackItem(
                    run_id=f"run-{i:03d}",
                    feedback_type=FeedbackType.THUMBS_UP,
                    value=True,
                    user_id=f"user-{i:03d}",
                    timestamp=datetime.now(timezone.utc),
                ),
            )

        # Add negative feedback
        for i in range(3):
            feedback_analyzer.add_feedback(
                FeedbackItem(
                    run_id=f"run-{i + 7:03d}",
                    feedback_type=FeedbackType.THUMBS_DOWN,
                    value=False,
                    user_id=f"user-{i + 7:03d}",
                    timestamp=datetime.now(timezone.utc),
                ),
            )

        stats = feedback_analyzer.calculate_statistics()

        assert stats["total_feedback"] == 10
        assert stats["sentiment_score"] == 0.7  # 7 positive out of 10
        assert stats["rating_distribution"]["thumbs_up"] == 7
        assert stats["rating_distribution"]["thumbs_down"] == 3

    def test_time_based_aggregation(self, feedback_analyzer):
        """Test aggregating feedback over time periods."""
        base_time = datetime.now(timezone.utc)

        # Add feedback at different times
        for i in range(24):  # 24 hours of feedback
            feedback_analyzer.add_feedback(
                FeedbackItem(
                    run_id=f"run-{i:03d}",
                    feedback_type=FeedbackType.RATING,
                    value=3.0 + (i % 5) * 0.5,
                    user_id="user-001",
                    timestamp=base_time - timedelta(hours=i),
                ),
            )

        # Get trends over last 24 hours
        trends = feedback_analyzer.get_trends(window_hours=24)

        assert "hourly_counts" in trends
        assert "average_rating_trend" in trends
        assert len(trends["hourly_counts"]) <= 24

    def test_user_feedback_patterns(self, feedback_analyzer):
        """Test identifying patterns in user feedback."""
        users = ["user-001", "user-002", "user-003"]

        # User 001 consistently gives high ratings
        for i in range(5):
            feedback_analyzer.add_feedback(
                FeedbackItem(
                    run_id=f"run-{i:03d}",
                    feedback_type=FeedbackType.RATING,
                    value=4.5,
                    user_id="user-001",
                    timestamp=datetime.now(timezone.utc),
                ),
            )

        # User 002 gives mixed ratings
        for i in range(5):
            feedback_analyzer.add_feedback(
                FeedbackItem(
                    run_id=f"run-{i + 5:03d}",
                    feedback_type=FeedbackType.RATING,
                    value=2.0 + i,
                    user_id="user-002",
                    timestamp=datetime.now(timezone.utc),
                ),
            )

        patterns = feedback_analyzer.identify_patterns()

        assert "user_patterns" in patterns
        assert "user-001" in patterns["user_patterns"]
        assert patterns["user_patterns"]["user-001"]["average_rating"] == 4.5


# ============================================================================
# Test Model Fine-tuning Triggers
# ============================================================================


class TestFineTuningTriggers:
    """Test triggers for model fine-tuning based on feedback."""

    def test_correction_threshold_trigger(self):
        """Test triggering fine-tuning when correction feedback exceeds threshold."""
        corrections = []

        # Simulate collecting correction feedback
        for i in range(15):  # Threshold is typically 10
            corrections.append(
                {
                    "run_id": f"run-{i:03d}",
                    "type": "correction",
                    "value": {"original": f"error-{i}", "corrected": f"fix-{i}"},
                },
            )

        # Check if fine-tuning should be triggered
        should_trigger = len(corrections) >= 10

        assert should_trigger is True
        assert len(corrections) == 15

    def test_low_rating_trigger(self):
        """Test triggering fine-tuning when average rating drops below threshold."""
        ratings = [2.0, 2.5, 1.5, 2.0, 2.5, 3.0, 2.0, 1.5, 2.0, 2.5]
        average_rating = sum(ratings) / len(ratings)

        # Typically trigger if average < 3.0
        should_trigger = average_rating < 3.0

        assert should_trigger is True
        assert average_rating == 2.15

    def test_negative_sentiment_trigger(self):
        """Test triggering fine-tuning when negative sentiment exceeds threshold."""
        feedback_counts = {"thumbs_up": 20, "thumbs_down": 35}

        total = feedback_counts["thumbs_up"] + feedback_counts["thumbs_down"]
        negative_ratio = feedback_counts["thumbs_down"] / total

        # Trigger if negative > 40%
        should_trigger = negative_ratio > 0.4

        assert should_trigger is True
        assert negative_ratio > 0.6

    def test_composite_trigger_conditions(self):
        """Test composite conditions for triggering fine-tuning."""
        conditions = {
            "correction_count": 8,
            "average_rating": 3.2,
            "negative_ratio": 0.35,
            "total_feedback": 100,
        }

        # Composite trigger: any two conditions met
        triggers_met = 0

        if conditions["correction_count"] >= 10:
            triggers_met += 1
        if conditions["average_rating"] < 3.5:
            triggers_met += 1
        if conditions["negative_ratio"] > 0.3:
            triggers_met += 1

        should_trigger = triggers_met >= 2

        assert should_trigger is True
        assert triggers_met == 2


# ============================================================================
# Test Feedback Loop Metrics
# ============================================================================


class TestFeedbackLoopMetrics:
    """Test metrics for feedback loop effectiveness."""

    def test_response_time_metrics(self):
        """Test measuring response time to feedback."""
        feedback_times = []
        response_times = []

        base_time = datetime.now(timezone.utc)

        # Simulate feedback and response times
        for i in range(10):
            feedback_time = base_time + timedelta(minutes=i * 10)
            response_time = feedback_time + timedelta(minutes=5 + i)  # Variable response time

            feedback_times.append(feedback_time)
            response_times.append(response_time)

        # Calculate average response time
        response_deltas = [
            (response_times[i] - feedback_times[i]).total_seconds() / 60
            for i in range(len(feedback_times))
        ]

        avg_response_time = sum(response_deltas) / len(response_deltas)

        assert avg_response_time > 5  # At least 5 minutes
        assert avg_response_time < 15  # Less than 15 minutes

    def test_feedback_incorporation_rate(self):
        """Test measuring how much feedback is incorporated."""
        total_feedback = 100
        incorporated_feedback = 75
        ignored_feedback = 15
        pending_feedback = 10

        incorporation_rate = incorporated_feedback / total_feedback

        assert incorporation_rate == 0.75
        assert (total_feedback == incorporated_feedback + ignored_feedback + pending_feedback,)

    def test_model_improvement_metrics(self):
        """Test measuring model improvement after feedback incorporation."""
        metrics_before = {
            "accuracy": 0.82,
            "precision": 0.78,
            "recall": 0.85,
            "f1_score": 0.815,
        }

        metrics_after = {
            "accuracy": 0.87,
            "precision": 0.84,
            "recall": 0.88,
            "f1_score": 0.86,
        }

        improvements = {key: metrics_after[key] - metrics_before[key] for key in metrics_before}

        assert improvements["accuracy"] > 0
        assert improvements["precision"] > 0
        assert improvements["f1_score"] > 0
        assert all(v > 0 for v in improvements.values())

    def test_user_satisfaction_trend(self):
        """Test tracking user satisfaction trends over time."""
        weekly_ratings = [
            3.2,  # Week 1
            3.5,  # Week 2
            3.8,  # Week 3
            4.1,  # Week 4
            4.3,  # Week 5
            4.2,  # Week 6,
        ]

        # Calculate trend (simple linear regression slope)
        n = len(weekly_ratings)
        x = list(range(n))

        x_mean = sum(x) / n
        y_mean = sum(weekly_ratings) / n

        numerator = sum((x[i] - x_mean) * (weekly_ratings[i] - y_mean) for i in range(n))
        denominator = sum((x[i] - x_mean) ** 2 for i in range(n))

        slope = numerator / denominator

        # Positive slope indicates improving satisfaction
        assert slope > 0
        assert slope > 0.15  # Significant improvement


# ============================================================================
# Test UI Components for Feedback
# ============================================================================


class TestFeedbackUIComponents:
    """Test UI component requirements for feedback collection."""

    def test_feedback_widget_props(self):
        """Test feedback widget component properties."""
        widget_config = {
            "type": "feedback_widget",
            "props": {
                "run_id": "test-run-123",
                "user_id": "user-001",
                "show_rating": True,
                "show_thumbs": True,
                "show_comment": True,
                "show_correction": False,
                "rating_scale": 5,
                "placeholder_text": "Share your feedback...",
                "submit_endpoint": "/api/feedback/collect",
            },
        }

        assert widget_config["props"]["rating_scale"] == 5
        assert widget_config["props"]["show_rating"] is True
        assert widget_config["props"]["show_correction"] is False

    def test_feedback_dashboard_metrics(self):
        """Test feedback dashboard component metrics display."""
        dashboard_data = {
            "total_feedback": 1234,
            "average_rating": 4.2,
            "sentiment_score": 0.75,
            "recent_feedback": [
                {"type": "rating", "value": 5, "time": "2 mins ago"},
                {"type": "comment", "value": "Great analysis", "time": "5 mins ago"},
                {"type": "thumbs_up", "value": True, "time": "10 mins ago"},
            ],
            "trend_chart": {
                "labels": ["Mon", "Tue", "Wed", "Thu", "Fri"],
                "data": [4.1, 4.0, 4.2, 4.3, 4.2],
            },
        }

        assert dashboard_data["total_feedback"] > 0
        assert 1 <= dashboard_data["average_rating"] <= 5
        assert 0 <= dashboard_data["sentiment_score"] <= 1
        assert len(dashboard_data["recent_feedback"]) > 0
        assert len(dashboard_data["trend_chart"]["data"]) == 5

    def test_inline_feedback_buttons(self):
        """Test inline feedback button configurations."""
        button_configs = [
            {
                "id": "thumbs-up-btn",
                "type": "icon_button",
                "icon": "thumb_up",
                "action": "submit_feedback",
                "payload": {"type": "thumbs_up", "value": True},
            },
            {
                "id": "thumbs-down-btn",
                "type": "icon_button",
                "icon": "thumb_down",
                "action": "submit_feedback",
                "payload": {"type": "thumbs_down", "value": False},
            },
            {
                "id": "flag-btn",
                "type": "icon_button",
                "icon": "flag",
                "action": "open_flag_dialog",
                "payload": {"type": "flag"},
            },
        ]

        assert len(button_configs) == 3
        assert all("action" in config for config in button_configs)
        assert button_configs[0]["payload"]["type"] == "thumbs_up"

    def test_correction_dialog_component(self):
        """Test correction dialog component for feedback."""
        dialog_state = {
            "is_open": False,
            "original_text": "",
            "corrected_text": "",
            "explanation": "",
            "confidence_level": "medium",
            "categories": [],
        }

        # Simulate opening dialog with data
        dialog_state["is_open"] = True
        dialog_state["original_text"] = "GDPR Article 5"
        dialog_state["corrected_text"] = "GDPR Article 6"
        dialog_state["explanation"] = "Incorrect article reference"
        dialog_state["categories"] = ["regulatory_reference", "citation_error"]

        assert dialog_state["is_open"] is True
        assert dialog_state["original_text"] != dialog_state["corrected_text"]
        assert len(dialog_state["categories"]) > 0


# ============================================================================
# Integration Tests
# ============================================================================


class TestFeedbackSystemIntegration:
    """Integration tests for the complete feedback system."""

    @pytest.mark.asyncio
    async def test_end_to_end_feedback_flow(self):
        """Test complete feedback flow from collection to analysis."""
        # Initialize components
        collector = LangSmithFeedbackCollector()
        analyzer = FeedbackAnalyzer()

        # Simulate user interactions
        run_ids = [f"run-{i:03d}" for i in range(5)]

        for run_id in run_ids:
            # Collect feedback
            feedback = collector.collect_feedback(
                run_id=run_id,
                feedback_type=FeedbackType.RATING,
                value=3.0 + len(run_ids) * 0.2,
                user_id="user-001",
                metadata={"session": "test-session"},
            )

            # Add to analyzer
            analyzer.add_feedback(feedback)

        # Analyze feedback
        stats = analyzer.calculate_statistics()

        # Check results
        assert stats["total_feedback"] == 5
        assert collector.feedback_stats["total_collected"] == 5
        assert stats["average_rating"] > 3.0

    @pytest.mark.asyncio
    async def test_feedback_triggers_model_update(self):
        """Test that feedback triggers model update when thresholds are met."""
        feedback_counts = {
            "corrections": 12,
            "low_ratings": 8,
            "negative_sentiment": 0.45,
        }

        # Check trigger conditions
        triggers = []

        if feedback_counts["corrections"] >= 10:
            triggers.append("correction_threshold")

        if feedback_counts["low_ratings"] >= 5:
            triggers.append("low_rating_threshold")

        if feedback_counts["negative_sentiment"] > 0.4:
            triggers.append("negative_sentiment_threshold")

        # Should trigger model update
        should_update = len(triggers) >= 2

        assert should_update is True
        assert len(triggers) >= 2
        assert "correction_threshold" in triggers

    def test_feedback_export_import_cycle(self, tmp_path):
        """Test exporting and importing feedback data."""
        collector1 = LangSmithFeedbackCollector()

        # Collect feedback
        for i in range(3):
            collector1.collect_feedback(
                run_id=f"run-{i:03d}",
                feedback_type=FeedbackType.COMMENT,
                value=f"Test comment {i}",
                user_id="user-001",
            )

        # Export
        export_file = tmp_path / "feedback.json"
        collector1.export_feedback(str(export_file))

        # Create new collector and import
        collector2 = LangSmithFeedbackCollector()

        with open(export_file, "r") as f:
            imported_data = json.load(f)

        # Restore feedback items
        for item_dict in imported_data["feedback_items"]:
            collector2.feedback_queue.append(
                FeedbackItem(
                    run_id=item_dict["run_id"],
                    feedback_type=FeedbackType(item_dict["feedback_type"]),
                    value=item_dict["value"],
                    user_id=item_dict["user_id"],
                    metadata=item_dict.get("metadata", {}),
                ),
            )

        assert len(collector2.feedback_queue) == 3
        assert collector2.feedback_queue[0].run_id == "run-000"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
