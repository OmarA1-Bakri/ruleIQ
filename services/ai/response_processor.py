"""
import logging


logger = logging.getLogger(__name__)
AI Response Processing with Schema Validation

This module provides structured response processing and validation for AI responses,
integrating Pydantic models with Google Gemini's structured output capabilities.

Part of Phase 6: Response Schema Validation implementation.
"""

import json
import traceback
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple, Union
from uuid import uuid4
from config.logging_config import get_logger
from .validation_models import validate_ai_response

logger = get_logger(__name__)


class AIResponseProcessor:
    """Processes and validates AI responses with comprehensive schema validation."""

    def __init__(self) -> None:
        self.validation_stats = {
            "total_processed": 0,
            "validation_successes": 0,
            "validation_failures": 0,
            "fallback_uses": 0,
            "error_recoveries": 0,
        }

    def process_structured_response(
        self,
        raw_response: str,
        response_type: str,
        model_used: str,
        processing_start_time: datetime,
        fallback_data: Optional[Dict[str, Any]] = None,
    ) -> Tuple[bool, Union[Dict[str, Any], None], List[str]]:
        """
        Process and validate structured AI response with comprehensive error handling.

        Args:
            raw_response: Raw AI response text
            response_type: Expected response type (gap_analysis, recommendations, etc.)
            model_used: AI model that generated the response
            processing_start_time: When processing started
            fallback_data: Fallback data if validation fails

        Returns:
            Tuple of (validation_success, validated_data, errors)
        """
        self.validation_stats["total_processed"] += 1
        errors = []
        try:
            processing_time_ms = int(
                (datetime.now(timezone.utc) - processing_start_time).total_seconds() * 1000
            )
            try:
                response_data = json.loads(raw_response)
            except json.JSONDecodeError as e:
                errors.append(f"JSON parsing failed: {e!s}")
                return self._handle_parsing_failure(
                    raw_response,
                    response_type,
                    model_used,
                    processing_time_ms,
                    fallback_data,
                    errors,
                )
            is_valid, validation_errors, validated_model = validate_ai_response(
                response_data, response_type
            )
            if validation_errors:
                errors.extend(validation_errors)
            if is_valid and validated_model:
                self.validation_stats["validation_successes"] += 1
                structured_response = self._create_structured_response(
                    validated_model.dict(),
                    response_type,
                    model_used,
                    processing_time_ms,
                    is_valid,
                    errors,
                )
                logger.info(
                    "Successfully validated %s response" % response_type,
                    extra={
                        "response_type": response_type,
                        "model_used": model_used,
                        "processing_time_ms": processing_time_ms,
                        "validation_success": True,
                    },
                )
                return True, structured_response, errors
            else:
                self.validation_stats["validation_failures"] += 1
                return self._handle_validation_failure(
                    response_data,
                    response_type,
                    model_used,
                    processing_time_ms,
                    fallback_data,
                    errors,
                )
        except Exception as e:
            errors.append(f"Unexpected processing error: {e!s}")
            logger.error(
                "Unexpected error processing %s response" % response_type,
                extra={
                    "error": str(e),
                    "response_type": response_type,
                    "model_used": model_used,
                    "traceback": traceback.format_exc(),
                },
            )
            return self._handle_processing_exception(
                raw_response, response_type, model_used, fallback_data, errors
            )

    def _handle_parsing_failure(
        self,
        raw_response: str,
        response_type: str,
        model_used: str,
        processing_time_ms: int,
        fallback_data: Optional[Dict[str, Any]],
        errors: List[str],
    ) -> Tuple[bool, Union[Dict[str, Any], None], List[str]]:
        """Handle JSON parsing failures with intelligent recovery."""
        extracted_json = self._extract_json_from_text(raw_response)
        if extracted_json:
            try:
                response_data = json.loads(extracted_json)
                is_valid, validation_errors, validated_model = validate_ai_response(
                    response_data, response_type
                )
                if is_valid and validated_model:
                    self.validation_stats["error_recoveries"] += 1
                    errors.append("Recovered from JSON parsing error")
                    structured_response = self._create_structured_response(
                        validated_model.dict(),
                        response_type,
                        model_used,
                        processing_time_ms,
                        True,
                        errors,
                    )
                    logger.warning(
                        "Recovered from JSON parsing failure for %s" % response_type,
                        extra={
                            "response_type": response_type,
                            "model_used": model_used,
                            "recovery_successful": True,
                        },
                    )
                    return True, structured_response, errors
            except Exception as e:
                errors.append(f"JSON extraction recovery failed: {e!s}")
        if fallback_data:
            return self._use_fallback_response(
                fallback_data, response_type, model_used, processing_time_ms, errors
            )
        logger.error(
            "Failed to parse %s response" % response_type,
            extra={
                "response_type": response_type,
                "model_used": model_used,
                "errors": errors,
                "raw_response_preview": raw_response[:200] if raw_response else None,
            },
        )
        return False, None, errors

    def _handle_validation_failure(
        self,
        response_data: Dict[str, Any],
        response_type: str,
        model_used: str,
        processing_time_ms: int,
        fallback_data: Optional[Dict[str, Any]],
        errors: List[str],
    ) -> Tuple[bool, Union[Dict[str, Any], None], List[str]]:
        """Handle schema validation failures with graceful degradation."""
        partial_response = self._create_partial_response(response_data, response_type, errors)
        if partial_response:
            self.validation_stats["error_recoveries"] += 1
            structured_response = self._create_structured_response(
                partial_response, response_type, model_used, processing_time_ms, False, errors
            )
            logger.warning(
                "Created partial response for %s after validation failure" % response_type,
                extra={
                    "response_type": response_type,
                    "model_used": model_used,
                    "validation_errors": len(errors),
                    "partial_recovery": True,
                },
            )
            return False, structured_response, errors
        if fallback_data:
            return self._use_fallback_response(
                fallback_data, response_type, model_used, processing_time_ms, errors
            )
        logger.error(
            "Complete validation failure for %s" % response_type,
            extra={
                "response_type": response_type,
                "model_used": model_used,
                "validation_errors": errors,
            },
        )
        return False, None, errors

    def _handle_processing_exception(
        self,
        raw_response: str,
        response_type: str,
        model_used: str,
        fallback_data: Optional[Dict[str, Any]],
        errors: List[str],
    ) -> Tuple[bool, Union[Dict[str, Any], None], List[str]]:
        """Handle unexpected processing exceptions."""
        if fallback_data:
            return self._use_fallback_response(fallback_data, response_type, model_used, 0, errors)
        return False, None, errors

    def _use_fallback_response(
        self,
        fallback_data: Dict[str, Any],
        response_type: str,
        model_used: str,
        processing_time_ms: int,
        errors: List[str],
    ) -> Tuple[bool, Dict[str, Any], List[str]]:
        """Use fallback response data when validation fails."""
        self.validation_stats["fallback_uses"] += 1
        structured_response = self._create_structured_response(
            fallback_data,
            response_type,
            model_used,
            processing_time_ms,
            False,
            errors,
            fallback_used=True,
        )
        logger.info(
            "Using fallback response for %s" % response_type,
            extra={"response_type": response_type, "model_used": model_used, "fallback_used": True},
        )
        return False, structured_response, errors

    def _create_structured_response(
        self,
        payload: Dict[str, Any],
        response_type: str,
        model_used: str,
        processing_time_ms: int,
        validation_passed: bool,
        errors: List[str],
        fallback_used: bool = False,
    ) -> Dict[str, Any]:
        """Create a structured response with metadata."""
        metadata = {
            "response_id": str(uuid4()),
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "model_used": model_used,
            "processing_time_ms": processing_time_ms,
            "confidence_score": payload.get("confidence_score", 0.8 if validation_passed else 0.5),
            "schema_version": "1.0.0",
            "validation_status": "valid"
            if validation_passed and not errors
            else "invalid"
            if errors
            else "partially_valid",
            "validation_errors": errors,
        }
        return {
            "metadata": metadata,
            "response_type": response_type,
            "payload": payload,
            "validation_passed": validation_passed,
            "fallback_used": fallback_used,
        }

    def _extract_json_from_text(self, text: str) -> Optional[str]:
        """Extract JSON content from text using various strategies."""
        if not text:
            return None
        json_markers = ["```json", "```JSON", "```", "{", "["]
        for marker in json_markers:
            start_idx = text.find(marker)
            if start_idx >= 0:
                if marker.startswith("```"):
                    start_idx = text.find("\n", start_idx) + 1
                    end_idx = text.find("```", start_idx)
                    if end_idx > start_idx:
                        return text[start_idx:end_idx].strip()
                elif marker in ["{", "["]:
                    bracket_count = 0
                    start_char = marker
                    end_char = "}" if marker == "{" else "]"
                    for i, char in enumerate(text[start_idx:], start_idx):
                        if char == start_char:
                            bracket_count += 1
                        elif char == end_char:
                            bracket_count -= 1
                            if bracket_count == 0:
                                return text[start_idx : i + 1]
        return None

    def _create_partial_response(
        self, response_data: Dict[str, Any], response_type: str, errors: List[str]
    ) -> Optional[Dict[str, Any]]:
        """Create a partial response from available data."""
        try:
            if response_type == "gap_analysis":
                return {
                    "gaps": response_data.get("gaps", []),
                    "overall_risk_level": response_data.get("overall_risk_level", "medium"),
                    "priority_order": response_data.get("priority_order", []),
                    "estimated_total_effort": response_data.get(
                        "estimated_total_effort", "Unknown"
                    ),
                    "critical_gap_count": response_data.get("critical_gap_count", 0),
                    "medium_high_gap_count": response_data.get("medium_high_gap_count", 0),
                    "compliance_percentage": response_data.get("compliance_percentage", 0.0),
                    "summary": response_data.get("summary", "Analysis partially available"),
                    "next_steps": response_data.get("next_steps", []),
                }
            elif response_type == "recommendations":
                return {
                    "recommendations": response_data.get("recommendations", []),
                    "implementation_plan": response_data.get(
                        "implementation_plan",
                        {"total_duration_weeks": 12, "phases": [], "success_metrics": []},
                    ),
                    "prioritization_rationale": response_data.get(
                        "prioritization_rationale", "Partial analysis available"
                    ),
                    "timeline_overview": response_data.get(
                        "timeline_overview", "Timeline needs refinement"
                    ),
                    "success_metrics": response_data.get("success_metrics", []),
                }
            elif response_type == "guidance":
                return {
                    "guidance": response_data.get("guidance", "Guidance partially available"),
                    "confidence_score": response_data.get("confidence_score", 0.5),
                    "related_topics": response_data.get("related_topics", []),
                    "follow_up_suggestions": response_data.get("follow_up_suggestions", []),
                    "source_references": response_data.get("source_references", []),
                }
        except Exception as e:
            errors.append(f"Failed to create partial response: {e!s}")
        return None

    def get_validation_stats(self) -> Dict[str, Any]:
        """Get validation statistics."""
        total = self.validation_stats["total_processed"]
        return {
            **self.validation_stats,
            "success_rate": self.validation_stats["validation_successes"] / total
            if total > 0
            else 0.0,
            "failure_rate": self.validation_stats["validation_failures"] / total
            if total > 0
            else 0.0,
            "recovery_rate": self.validation_stats["error_recoveries"] / total
            if total > 0
            else 0.0,
            "fallback_rate": self.validation_stats["fallback_uses"] / total if total > 0 else 0.0,
        }

    def reset_stats(self) -> None:
        """Reset validation statistics."""
        self.validation_stats = {
            "total_processed": 0,
            "validation_successes": 0,
            "validation_failures": 0,
            "fallback_uses": 0,
            "error_recoveries": 0,
        }


response_processor = AIResponseProcessor()


def process_ai_response(
    raw_response: str,
    response_type: str,
    model_used: str,
    processing_start_time: datetime,
    fallback_data: Optional[Dict[str, Any]] = None,
) -> Tuple[bool, Union[Dict[str, Any], None], List[str]]:
    """
    Convenience function to process AI responses with validation.

    Args:
        raw_response: Raw AI response text
        response_type: Expected response type
        model_used: AI model that generated the response
        processing_start_time: Processing start time
        fallback_data: Optional fallback data

    Returns:
        Tuple of (success, validated_response, errors)
    """
    return response_processor.process_structured_response(
        raw_response, response_type, model_used, processing_start_time, fallback_data
    )
