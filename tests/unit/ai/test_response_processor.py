"""Tests for services.ai.response_processor."""

from datetime import datetime, timedelta, timezone
from unittest.mock import Mock, patch

from services.ai.response_processor import AIResponseProcessor, process_ai_response


class TestAIResponseProcessor:
    def test_process_structured_response_success(self):
        processor = AIResponseProcessor()
        validated_model = Mock()
        validated_model.dict.return_value = {
            "guidance": "Use MFA for privileged access.",
            "confidence_score": 0.91,
        }

        with patch(
            "services.ai.response_processor.validate_ai_response",
            return_value=(True, [], validated_model),
        ), patch("services.ai.response_processor.uuid4", return_value="resp-123"):
            success, data, errors = processor.process_structured_response(
                raw_response='{"guidance": "Use MFA for privileged access."}',
                response_type="guidance",
                model_used="gemini-2.5-flash",
                processing_start_time=datetime.now(timezone.utc) - timedelta(milliseconds=5),
            )

        assert success is True
        assert errors == []
        assert data["response_type"] == "guidance"
        assert data["validation_passed"] is True
        assert data["fallback_used"] is False
        assert data["payload"]["guidance"] == "Use MFA for privileged access."
        assert data["metadata"]["response_id"] == "resp-123"
        assert data["metadata"]["confidence_score"] == 0.91
        assert data["metadata"]["validation_status"] == "valid"
        assert processor.validation_stats["total_processed"] == 1
        assert processor.validation_stats["validation_successes"] == 1

    def test_process_structured_response_recovers_from_markdown_json(self):
        processor = AIResponseProcessor()
        validated_model = Mock()
        validated_model.dict.return_value = {
            "guidance": "Recovered guidance",
            "confidence_score": 0.8,
        }

        with patch(
            "services.ai.response_processor.validate_ai_response",
            return_value=(True, [], validated_model),
        ):
            success, data, errors = processor.process_structured_response(
                raw_response='prefix```json\n{"guidance": "Recovered guidance"}\n```suffix',
                response_type="guidance",
                model_used="gemini-2.5-flash",
                processing_start_time=datetime.now(timezone.utc),
            )

        assert success is True
        assert "Recovered from JSON parsing error" in errors
        assert data["payload"]["guidance"] == "Recovered guidance"
        assert processor.validation_stats["error_recoveries"] == 1

    def test_process_structured_response_uses_fallback_after_parsing_failure(self):
        processor = AIResponseProcessor()
        fallback_data = {"guidance": "Fallback guidance", "confidence_score": 0.3}

        success, data, errors = processor.process_structured_response(
            raw_response="this is not json",
            response_type="guidance",
            model_used="gemini-2.5-flash",
            processing_start_time=datetime.now(timezone.utc),
            fallback_data=fallback_data,
        )

        assert success is False
        assert data["fallback_used"] is True
        assert data["payload"] == fallback_data
        assert any("JSON parsing failed" in error for error in errors)
        assert processor.validation_stats["fallback_uses"] == 1

    def test_process_structured_response_creates_partial_response_on_validation_failure(self):
        processor = AIResponseProcessor()

        with patch(
            "services.ai.response_processor.validate_ai_response",
            return_value=(False, ["guidance too short"], None),
        ):
            success, data, errors = processor.process_structured_response(
                raw_response='{"guidance": "Partial guidance", "related_topics": ["gdpr"]}',
                response_type="guidance",
                model_used="gemini-2.5-flash",
                processing_start_time=datetime.now(timezone.utc),
            )

        assert success is False
        assert data["fallback_used"] is False
        assert data["validation_passed"] is False
        assert data["payload"]["guidance"] == "Partial guidance"
        assert data["payload"]["related_topics"] == ["gdpr"]
        assert "guidance too short" in errors
        assert processor.validation_stats["validation_failures"] == 1
        assert processor.validation_stats["error_recoveries"] == 1

    def test_process_structured_response_falls_back_when_partial_response_unavailable(self):
        processor = AIResponseProcessor()
        fallback_data = {"summary": "Fallback summary"}

        with patch(
            "services.ai.response_processor.validate_ai_response",
            return_value=(False, ["schema mismatch"], None),
        ):
            success, data, errors = processor.process_structured_response(
                raw_response='{"unexpected": "shape"}',
                response_type="unknown_response_type",
                model_used="gemini-2.5-flash",
                processing_start_time=datetime.now(timezone.utc),
                fallback_data=fallback_data,
            )

        assert success is False
        assert data["fallback_used"] is True
        assert data["payload"] == fallback_data
        assert "schema mismatch" in errors
        assert processor.validation_stats["fallback_uses"] == 1

    def test_process_structured_response_handles_unexpected_exception_with_fallback(self):
        processor = AIResponseProcessor()
        fallback_data = {"guidance": "Recovered from exception"}

        with patch(
            "services.ai.response_processor.validate_ai_response",
            side_effect=RuntimeError("validator crashed"),
        ):
            success, data, errors = processor.process_structured_response(
                raw_response='{"guidance": "hello"}',
                response_type="guidance",
                model_used="gemini-2.5-flash",
                processing_start_time=datetime.now(timezone.utc),
                fallback_data=fallback_data,
            )

        assert success is False
        assert data["fallback_used"] is True
        assert data["payload"] == fallback_data
        assert any("Unexpected processing error: validator crashed" in error for error in errors)
        assert processor.validation_stats["fallback_uses"] == 1

    def test_extract_json_from_text_handles_nested_objects(self):
        processor = AIResponseProcessor()
        extract_json = getattr(processor, "_extract_json_from_text")

        extracted = extract_json(
            'noise before {"outer": {"inner": [1, 2, {"deep": true}]}} noise after'
        )

        assert extracted == '{"outer": {"inner": [1, 2, {"deep": true}]}}'

    def test_create_partial_response_for_gap_analysis_uses_defaults(self):
        processor = AIResponseProcessor()
        create_partial_response = getattr(processor, "_create_partial_response")

        partial = create_partial_response(
            {"gaps": [{"id": "gap_1"}], "summary": "Some gaps found"},
            "gap_analysis",
            [],
        )

        assert partial == {
            "gaps": [{"id": "gap_1"}],
            "overall_risk_level": "medium",
            "priority_order": [],
            "estimated_total_effort": "Unknown",
            "critical_gap_count": 0,
            "medium_high_gap_count": 0,
            "compliance_percentage": 0.0,
            "summary": "Some gaps found",
            "next_steps": [],
        }

    def test_get_validation_stats_and_reset_stats(self):
        processor = AIResponseProcessor()
        processor.validation_stats = {
            "total_processed": 4,
            "validation_successes": 2,
            "validation_failures": 1,
            "fallback_uses": 1,
            "error_recoveries": 2,
        }

        stats = processor.get_validation_stats()

        assert stats["success_rate"] == 0.5
        assert stats["failure_rate"] == 0.25
        assert stats["recovery_rate"] == 0.5
        assert stats["fallback_rate"] == 0.25

        processor.reset_stats()

        assert processor.validation_stats == {
            "total_processed": 0,
            "validation_successes": 0,
            "validation_failures": 0,
            "fallback_uses": 0,
            "error_recoveries": 0,
        }


def test_process_ai_response_delegates_to_module_processor():
    with patch(
        "services.ai.response_processor.response_processor.process_structured_response",
        return_value=(True, {"payload": {}}, []),
    ) as mock_process:
        result = process_ai_response(
            raw_response='{"guidance": "hello"}',
            response_type="guidance",
            model_used="gemini-2.5-flash",
            processing_start_time=datetime.now(timezone.utc),
            fallback_data={"guidance": "fallback"},
        )

    assert result == (True, {"payload": {}}, [])
    mock_process.assert_called_once()