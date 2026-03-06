"""API endpoints for AI response validation."""

from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks, status
from typing import List, Optional, Dict, Any
from datetime import datetime
import asyncio
import logging

from services.rag_validator import RAGValidator, ValidationResult
from models.validation import (
    ValidationRequest,
    BatchValidationRequest,
    BatchValidationResult,
    ReviewPriority,
)
from middleware.circuit_breaker import CircuitBreaker
from middleware.jwt_auth_v2 import jwt_required, get_current_user
from database.connection import get_db
from sqlalchemy.orm import Session

# Configure logging
logger = logging.getLogger(__name__)

# Initialize router
router = APIRouter(prefix="/api/v1/ai", tags=["AI Validation"])

# Initialize validator (singleton)
_validator_instance = None


def get_validator() -> RAGValidator:
    """Get or create validator instance."""
    global _validator_instance
    if _validator_instance is None:
        _validator_instance = RAGValidator(cache_enabled=True)
    return _validator_instance


# Initialize circuit breaker for validation service
validation_circuit_breaker = CircuitBreaker(
    failure_threshold=5, recovery_timeout=60, expected_exception=Exception
)


@router.post("/validate", response_model=ValidationResult)
@jwt_required
async def validate_response(
    request: ValidationRequest,
    background_tasks: BackgroundTasks,
    current_user: dict = Depends(get_current_user),
    validator: RAGValidator = Depends(get_validator),
    db: Session = Depends(get_db),
) -> ValidationResult:
    """
    Validate a single AI response against the knowledge base.

    Returns confidence scores and validation status.
    """
    try:
        # Apply circuit breaker
        with validation_circuit_breaker:
            # Add user context
            context = request.context or {}
            context["user_id"] = current_user.get("user_id")
            context["session_id"] = request.session_id

            # Perform validation
            result = await validator.validate_response(
                response=request.response_text, context=context, response_id=str(request.request_id)
            )

            # Schedule audit logging in background
            background_tasks.add_task(log_validation_audit, db, request, result, current_user)

            # Schedule human review if needed
            if result.requires_human_review:
                background_tasks.add_task(create_review_request, db, request, result)

            return result

    except Exception as e:
        logger.error(f"Validation error: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Validation service error: {str(e)}",
        )


@router.post("/validate-batch", response_model=BatchValidationResult)
@jwt_required
async def validate_batch(
    batch_request: BatchValidationRequest,
    background_tasks: BackgroundTasks,
    current_user: dict = Depends(get_current_user),
    validator: RAGValidator = Depends(get_validator),
    db: Session = Depends(get_db),
) -> BatchValidationResult:
    """
    Validate multiple AI responses in batch.

    Maximum 10 responses per batch.
    """
    try:
        # Validate batch size
        if len(batch_request.responses) > 10:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST, detail="Maximum 10 responses per batch"
            )

        # Prepare responses and contexts
        responses = [req.response_text for req in batch_request.responses]
        contexts = []
        for req in batch_request.responses:
            context = req.context or {}
            context["user_id"] = current_user.get("user_id")
            context["session_id"] = req.session_id
            context["batch_id"] = str(batch_request.batch_id)
            contexts.append(context)

        # Perform batch validation with timeout
        try:
            results = await asyncio.wait_for(
                validator.validate_batch(
                    responses=responses, contexts=contexts, max_parallel=batch_request.max_parallel
                ),
                timeout=batch_request.timeout_seconds,
            )
        except asyncio.TimeoutError:
            raise HTTPException(
                status_code=status.HTTP_408_REQUEST_TIMEOUT,
                detail=f"Batch validation timeout after {batch_request.timeout_seconds} seconds",
            )

        # Calculate batch statistics
        total_confidence = sum(r.confidence_score for r in results)
        successful = sum(1 for r in results if r.is_valid)
        failed = sum(1 for r in results if not r.is_valid)
        requiring_review = sum(1 for r in results if r.requires_human_review)
        total_time = sum(r.processing_time_ms for r in results)

        batch_result = BatchValidationResult(
            batch_id=batch_request.batch_id,
            total_responses=len(results),
            successful_validations=successful,
            failed_validations=failed,
            requiring_review=requiring_review,
            average_confidence=total_confidence / len(results) if results else 0,
            total_processing_time_ms=total_time,
            results=[r.model_dump() for r in results],
        )

        # Schedule batch audit logging
        background_tasks.add_task(
            log_batch_validation_audit, db, batch_request, batch_result, results, current_user
        )

        return batch_result

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Batch validation error: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Batch validation error: {str(e)}",
        )


@router.get("/validation-metrics")
@jwt_required
async def get_validation_metrics(
    current_user: dict = Depends(get_current_user), validator: RAGValidator = Depends(get_validator)
) -> Dict[str, Any]:
    """Get current validation service metrics."""
    try:
        metrics = validator.get_metrics()
        health = await validator.health_check()

        return {
            "metrics": metrics.model_dump(),
            "health": health,
            "timestamp": datetime.utcnow().isoformat(),
        }
    except Exception as e:
        logger.error(f"Error getting metrics: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error retrieving metrics: {str(e)}",
        )


@router.get("/review-queue")
@jwt_required
async def get_review_queue(
    priority: Optional[ReviewPriority] = None,
    status: Optional[str] = "pending",
    limit: int = 20,
    current_user: dict = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> List[Dict[str, Any]]:
    """Get items from human review queue."""
    try:
        # Query review queue from database
        from models.validation_audit import HumanReviewQueue

        query = db.query(HumanReviewQueue)

        if priority:
            query = query.filter(HumanReviewQueue.priority == priority)
        if status:
            query = query.filter(HumanReviewQueue.status == status)

        # Order by priority score and creation time
        items = (
            query.order_by(HumanReviewQueue.priority_score.desc(), HumanReviewQueue.created_at)
            .limit(limit)
            .all()
        )

        return [
            {
                "review_id": str(item.review_id),
                "validation_id": str(item.validation_id),
                "priority": item.priority,
                "confidence_score": item.confidence_score,
                "failure_reasons": item.failure_reasons,
                "status": item.status,
                "created_at": item.created_at.isoformat(),
                "assigned_to": item.assigned_to,
            }
            for item in items
        ]

    except Exception as e:
        logger.error(f"Error getting review queue: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error retrieving review queue: {str(e)}",
        )


@router.post("/review/{review_id}/complete")
@jwt_required
async def complete_review(
    review_id: str,
    decision: str,
    notes: Optional[str] = None,
    corrections: Optional[List[str]] = None,
    current_user: dict = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """Complete a human review of validation."""
    try:
        from models.validation_audit import HumanReviewQueue
        import uuid

        # Find review item
        review = (
            db.query(HumanReviewQueue)
            .filter(HumanReviewQueue.review_id == uuid.UUID(review_id))
            .first()
        )

        if not review:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail="Review item not found"
            )

        # Update review
        review.status = "completed"
        review.review_decision = decision
        review.reviewer_notes = notes
        review.corrections_applied = corrections
        review.completed_at = datetime.utcnow()
        review.assigned_to = current_user.get("user_id")

        db.commit()

        return {
            "review_id": review_id,
            "status": "completed",
            "decision": decision,
            "completed_at": review.completed_at.isoformat(),
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error completing review: {str(e)}")
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error completing review: {str(e)}",
        )


# Background task functions
async def log_validation_audit(
    db: Session, request: ValidationRequest, result: ValidationResult, user: dict
):
    """Log validation to audit table."""
    try:
        from models.validation_audit import ValidationAudit
        import hashlib

        audit_entry = ValidationAudit(
            validation_id=result.response_id,
            request_id=request.request_id,
            user_id=user.get("user_id"),
            session_id=request.session_id,
            assessment_id=request.assessment_id,
            original_response=request.response_text,
            response_hash=hashlib.sha256(request.response_text.encode()).hexdigest(),
            context=request.context,
            confidence_score=result.confidence_score,
            is_valid=result.is_valid,
            requires_review=result.requires_human_review,
            failure_reasons=[r.value for r in result.failure_reasons],
            semantic_similarity_score=result.semantic_similarity_score,
            citation_coverage_score=result.citation_coverage_score,
            fact_consistency_score=result.fact_consistency_score,
            processing_time_ms=result.processing_time_ms,
            cache_hit=result.metadata.get("cache_hit", False),
            matched_regulations=result.matched_regulations,
            regulation_count=len(result.matched_regulations),
            metadata=result.metadata,
        )

        db.add(audit_entry)
        db.commit()

    except Exception as e:
        logger.error(f"Error logging audit: {str(e)}")
        db.rollback()


async def create_review_request(db: Session, request: ValidationRequest, result: ValidationResult):
    """Create human review request for low confidence validation."""
    try:
        from models.validation_audit import HumanReviewQueue

        # Calculate priority based on confidence
        if result.confidence_score < 30:
            priority = "critical"
            priority_score = 100
        elif result.confidence_score < 50:
            priority = "high"
            priority_score = 75
        elif result.confidence_score < 65:
            priority = "medium"
            priority_score = 50
        else:
            priority = "low"
            priority_score = 25

        review_request = HumanReviewQueue(
            validation_id=result.response_id,
            audit_id=request.request_id,
            priority=priority,
            priority_score=priority_score,
            confidence_score=result.confidence_score,
            failure_reasons=[
                {"reason": r.value, "description": f"Validation failed: {r.value}"}
                for r in result.failure_reasons
            ],
            response_text=request.response_text,
            suggested_corrections=[],
        )

        db.add(review_request)
        db.commit()

    except Exception as e:
        logger.error(f"Error creating review request: {str(e)}")
        db.rollback()


async def log_batch_validation_audit(
    db: Session,
    batch_request: BatchValidationRequest,
    batch_result: BatchValidationResult,
    results: List[ValidationResult],
    user: dict,
):
    """Log batch validation to audit table."""
    for i, result in enumerate(results):
        request = batch_request.responses[i]
        await log_validation_audit(db, request, result, user)
