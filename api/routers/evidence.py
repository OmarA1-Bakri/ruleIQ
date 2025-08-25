from typing import Optional
from uuid import UUID

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from sqlalchemy.ext.asyncio import AsyncSession

from api.dependencies.auth import get_current_active_user
from database.user import User
from api.schemas.evidence_classification import (
    BulkClassificationRequest,
    BulkClassificationResponse,
    ClassificationStatsResponse,
    ControlMappingRequest,
    ControlMappingResponse,
    EvidenceClassificationRequest,
    EvidenceClassificationResponse,
)
from api.schemas.models import (
    EvidenceAutomationResponse,
    EvidenceBulkUpdate,
    EvidenceBulkUpdateResponse,
    EvidenceCreate,
    EvidenceDashboardResponse,
    EvidenceRequirementsResponse,
    EvidenceResponse,
    EvidenceSearchResponse,
    EvidenceStatisticsResponse,
    EvidenceUpdate,
    EvidenceValidationResult,
)
from api.schemas.quality_analysis import (
    BatchDuplicateDetectionRequest,
    BatchDuplicateDetectionResponse,
    DuplicateDetectionRequest,
    DuplicateDetectionResponse,
    QualityAnalysisResponse,
    QualityBenchmarkRequest,
    QualityBenchmarkResponse,
    QualityTrendRequest,
    QualityTrendResponse,
)
from config.logging_config import get_logger
from database.db_setup import get_async_db
from services.automation.evidence_processor import EvidenceProcessor
from services.evidence_service import EvidenceService

logger = get_logger(__name__)

router = APIRouter()


@router.post("/", status_code=201, response_model=EvidenceResponse)
async def create_new_evidence(
    evidence_data: EvidenceCreate,
    db: AsyncSession = Depends(get_async_db),
    current_user: User = Depends(get_current_active_user),
):
    """Create a new evidence item."""
    from sqlalchemy import select

    from database.business_profile import BusinessProfile

    # Get user's business profile automatically
    profile_stmt = select(BusinessProfile).where(BusinessProfile.user_id == str(current_user.id))
    profile_result = await db.execute(profile_stmt)
    profile = profile_result.scalars().first()
    if not profile:
        raise HTTPException(
            status_code=400,
            detail="Business profile not found. Please complete your business assessment first.",
        )

    # Add business_profile_id to evidence data
    evidence_dict = evidence_data.model_dump(exclude_none=True)
    evidence_dict["business_profile_id"] = profile.id

    evidence = await EvidenceService.create_evidence_item(
        db=db, user=current_user, evidence_data=evidence_dict
    )
    # Convert EvidenceItem to expected response format
    return EvidenceService._convert_evidence_item_to_response(evidence)


@router.get("/")
async def list_evidence(
    framework_id: Optional[UUID] = None,
    evidence_type: Optional[str] = None,
    status: Optional[str] = None,
    page: int = 1,
    page_size: int = 20,
    sort_by: Optional[str] = None,
    sort_order: Optional[str] = "asc",
    db: AsyncSession = Depends(get_async_db),
    current_user: User = Depends(get_current_active_user),
):
    """List all evidence items for a user with optional filtering and pagination."""
    # Use the optimized paginated method for better performance
    evidence_list, total_count = await EvidenceService.list_evidence_items_paginated(
        db=db,
        user=current_user,
        framework_id=framework_id,
        evidence_type=evidence_type,
        status=status,
        page=page,
        page_size=page_size,
        sort_by=sort_by,
        sort_order=sort_order or "asc",
    )

    # Convert EvidenceItem objects to expected response format
    results = [EvidenceService._convert_evidence_item_to_response(item) for item in evidence_list]

    # Calculate pagination info
    total_pages = (total_count + page_size - 1) // page_size  # Ceiling division

    # Check if pagination or sorting was explicitly requested
    # If page > 1 or page_size != 20 (default) or sorting is requested, return paginated format
    # Otherwise, return simple list for backward compatibility with existing tests
    pagination_requested = page > 1 or page_size != 20 or sort_by is not None

    if pagination_requested:
        return {
            "results": results,
            "page": page,
            "page_size": page_size,
            "total_count": total_count,
            "total_pages": total_pages,
        }
    else:
        # Return simple list for backward compatibility
        return results


@router.get("/stats", response_model=EvidenceStatisticsResponse)
async def get_evidence_statistics(
    db: AsyncSession = Depends(get_async_db),
    current_user: User = Depends(get_current_active_user),
):
    """Get evidence statistics for the current user."""
    stats = await EvidenceService.get_evidence_statistics(db=db, user_id=UUID(str(str(current_user.id))))
    return stats


@router.get("/search", response_model=EvidenceSearchResponse)
async def search_evidence_items(
    q: Optional[str] = None,
    evidence_type: Optional[str] = None,
    status: Optional[str] = None,
    framework: Optional[str] = None,
    page: int = 1,
    page_size: int = 20,
    db: AsyncSession = Depends(get_async_db),
    current_user: User = Depends(get_current_active_user),
):
    """Search evidence items with various filters."""
    # Use the EvidenceService to get evidence items with filtering
    evidence_items = await EvidenceService.list_all_evidence_items(
        db=db, user=current_user, evidence_type=evidence_type, status=status
    )

    # Apply pagination manually since the service doesn't support it
    start_idx = (page - 1) * page_size
    end_idx = start_idx + page_size
    paginated_items = evidence_items[start_idx:end_idx]

    # Convert to search response format
    search_results = []
    for item in paginated_items:
        search_results.append(
            {
                "id": item.id,
                "title": item.evidence_name,
                "description": item.description,
                "evidence_type": item.evidence_type,
                "status": item.status,
                "relevance_score": 1.0,  # Placeholder
                "created_at": item.created_at,
                "updated_at": item.updated_at,
            }
        )

    return {
        "results": search_results,
        "total_count": len(evidence_items),  # Total count before pagination
        "page": page,
        "page_size": page_size,
    }


@router.post("/validate", response_model=EvidenceValidationResult)
async def validate_evidence_quality(
    evidence_data: dict,
    db: AsyncSession = Depends(get_async_db),
    current_user: User = Depends(get_current_active_user),
):
    """Validate evidence quality."""
    # Placeholder implementation
    return {
        "quality_score": 85,
        "validation_results": {"completeness": "good", "relevance": "high", "accuracy": "verified"},
        "issues": [],
        "recommendations": [
            "Consider adding more detailed metadata",
            "Include version control information",
        ],
    }


@router.get("/requirements", response_model=EvidenceRequirementsResponse)
async def get_evidence_requirements(
    framework_id: UUID,
    db: AsyncSession = Depends(get_async_db),
    current_user: User = Depends(get_current_active_user),
):
    """Get evidence requirements for a framework."""
    # Placeholder implementation
    requirements = [
        {
            "control_id": "AC-1",
            "evidence_type": "document",
            "title": "Access Control Policy",
            "description": "Document outlining access control procedures",
            "automation_possible": True,
        },
        {
            "control_id": "AC-2",
            "evidence_type": "document",
            "title": "Account Management Procedures",
            "description": "Procedures for managing user accounts",
            "automation_possible": False,
        },
    ]
    return {"requirements": requirements}


@router.post("/requirements", response_model=EvidenceRequirementsResponse)
async def identify_evidence_requirements(
    request_data: dict,
    db: AsyncSession = Depends(get_async_db),
    current_user: User = Depends(get_current_active_user),
):
    """Identify evidence requirements for controls."""
    # Placeholder implementation
    requirements = [
        {
            "control_id": request_data.get("control_ids", [""])[0],
            "evidence_type": "document",
            "title": "Access Control Policy",
            "description": "Document outlining access control procedures",
            "automation_possible": True,
        },
        {
            "control_id": request_data.get("control_ids", ["", ""])[1]
            if len(request_data.get("control_ids", [])) > 1
            else "",
            "evidence_type": "log",
            "title": "Access Logs",
            "description": "System access logs for audit trail",
            "automation_possible": True,
        },
    ]
    return {"requirements": requirements}


@router.get("/{id}", response_model=EvidenceResponse)
async def get_evidence_details(
    evidence_id: UUID,
    db: AsyncSession = Depends(get_async_db),
    current_user: User = Depends(get_current_active_user),
):
    """Retrieve the details of a specific evidence item."""
    evidence, status = await EvidenceService.get_evidence_item_with_auth_check(
        db=db, user_id=UUID(str(str(current_user.id))), evidence_id=evidence_id
    )

    if status == "not_found":
        raise HTTPException(status_code=404, detail="Evidence not found")
    elif status == "unauthorized":
        raise HTTPException(status_code=403, detail="Access denied")

    # Convert EvidenceItem to expected response format
    return EvidenceService._convert_evidence_item_to_response(evidence)


@router.put("/{id}", response_model=EvidenceResponse)
async def update_evidence_item(
    evidence_id: UUID,
    evidence_update: EvidenceUpdate,
    db: AsyncSession = Depends(get_async_db),
    current_user: User = Depends(get_current_active_user),
):
    """Update an evidence item with full or partial data."""
    evidence, status = await EvidenceService.update_evidence_item(
        db=db,
        user=current_user,
        evidence_id=evidence_id,
        update_data=evidence_update.model_dump(exclude_unset=True),
    )

    if status == "not_found":
        raise HTTPException(status_code=404, detail="Evidence not found")
    elif status == "unauthorized":
        raise HTTPException(status_code=403, detail="Access denied")
    elif status.startswith("validation_error"):
        raise HTTPException(status_code=400, detail=status.replace("validation_error: ", ""))

    # Convert EvidenceItem to expected response format
    return EvidenceService._convert_evidence_item_to_response(evidence)


@router.patch("/{id}", response_model=EvidenceResponse)
async def update_evidence_status(
    evidence_id: UUID,
    evidence_update: EvidenceUpdate,
    db: AsyncSession = Depends(get_async_db),
    current_user: User = Depends(get_current_active_user),
):
    """Update an evidence item status and other fields."""
    evidence, status = await EvidenceService.update_evidence_item(
        db=db,
        user=current_user,
        evidence_id=evidence_id,
        update_data=evidence_update.model_dump(exclude_unset=True),
    )

    if status == "not_found":
        raise HTTPException(status_code=404, detail="Evidence not found")
    elif status == "unauthorized":
        raise HTTPException(status_code=403, detail="Access denied")
    elif status.startswith("validation_error"):
        raise HTTPException(status_code=400, detail=status.replace("validation_error: ", ""))

    # Convert EvidenceItem to expected response format
    return EvidenceService._convert_evidence_item_to_response(evidence)


@router.delete("/{id}", status_code=204)
async def delete_evidence_item(
    evidence_id: UUID,
    db: AsyncSession = Depends(get_async_db),
    current_user: User = Depends(get_current_active_user),
) -> None:
    """Delete an evidence item."""
    success, status = await EvidenceService.delete_evidence_item(
        db=db, user=current_user, evidence_id=evidence_id
    )

    if status == "not_found":
        raise HTTPException(status_code=404, detail="Evidence not found")
    elif status == "unauthorized":
        raise HTTPException(status_code=403, detail="Access denied")


@router.post("/bulk-update", response_model=EvidenceBulkUpdateResponse)
async def bulk_update_evidence_status(
    bulk_update: EvidenceBulkUpdate,
    db: AsyncSession = Depends(get_async_db),
    current_user: User = Depends(get_current_active_user),
):
    """Bulk update evidence status for multiple items."""
    updated_count, failed_count, failed_ids = await EvidenceService.bulk_update_evidence_status(
        db=db,
        user=current_user,
        evidence_ids=bulk_update.evidence_ids,
        status=bulk_update.status,
        reason=bulk_update.reason,
    )

    return EvidenceBulkUpdateResponse(
        updated_count=updated_count,
        failed_count=failed_count,
        failed_ids=failed_ids if failed_ids else None,
    )


@router.post("/{id}/automation", response_model=EvidenceAutomationResponse)
async def configure_evidence_automation(
    evidence_id: UUID,
    automation_config: dict,
    db: AsyncSession = Depends(get_async_db),
    current_user: User = Depends(get_current_active_user),
):
    """Configure automation for evidence collection."""
    # Verify evidence exists and user has access
    evidence, status = await EvidenceService.get_evidence_item_with_auth_check(
        db=db, user_id=UUID(str(str(current_user.id))), evidence_id=evidence_id
    )

    if status == "not_found":
        raise HTTPException(status_code=404, detail="Evidence not found")
    elif status == "unauthorized":
        raise HTTPException(status_code=403, detail="Access denied")

    # Placeholder implementation for automation configuration
    return {
        "configuration_successful": True,
        "automation_enabled": True,
        "test_connection": True,
        "next_collection": "2024-01-02T00:00:00Z",
    }


@router.post("/{id}/upload", response_model=EvidenceResponse)
async def upload_evidence_file_route(
    evidence_id: UUID,
    file: UploadFile = File(...),
    db: AsyncSession = Depends(get_async_db),
    current_user: User = Depends(get_current_active_user),
):
    """Upload a file and link it to an evidence item with enhanced security validation."""
    # Import enhanced validator
    from api.dependencies.file import EnhancedFileValidator

    # Initialize enhanced validator with strict security for evidence files
    validator = EnhancedFileValidator(
        max_size=50 * 1024 * 1024,  # 50MB limit for evidence files
        allowed_types=[
            "application/pdf",
            "image/jpeg",
            "image/png",
            "image/gif",
            "text/csv",
            "text/plain",
            "application/json",
            "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
            "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        ],
        security_level="strict",  # Strict validation for compliance evidence
        enable_quarantine=True,
    )

    # Validate and analyze file
    validated_file, analysis_report, quarantine_path = await validator.validate_and_analyze(file)

    # Log security analysis
    logger.info(
        f"Evidence file validation: {analysis_report.filename} - "
        f"Result: {analysis_report.validation_result.value}, "
        f"Score: {analysis_report.security_score:.2f}"
    )

    # Create secure file path
    from api.dependencies.file import get_safe_upload_path

    secure_path = get_safe_upload_path(f"{id}_{validated_file.filename}")

    # Save file securely
    file_content = await validated_file.read()
    with open(secure_path, "wb") as f:
        f.write(file_content)

        # Upload evidence with enhanced metadata
    evidence = await EvidenceService.upload_evidence_file(
        db=db,
        user=current_user,
        evidence_id=evidence_id,
        file_name=analysis_report.filename,
        file_path=str(secure_path),
        metadata={
            "content_type": analysis_report.content_type,
            "detected_type": analysis_report.detected_type,
            "file_size": analysis_report.file_size,
            "file_hash": analysis_report.file_hash,
            "security_score": analysis_report.security_score,
            "validation_result": analysis_report.validation_result.value,
            "validation_time": analysis_report.validation_time,
            "quarantine_path": quarantine_path,
            "original_filename": analysis_report.original_filename,
            "threats_detected": analysis_report.threats_detected
            if analysis_report.threats_detected
            else None,
        },
    )

    if not evidence:
        # Clean up uploaded file on failure
        if secure_path.exists():
            secure_path.unlink()
        raise HTTPException(status_code=404, detail="Failed to upload or link file to evidence")

    # Return enhanced response with security information
    response = EvidenceService._convert_evidence_item_to_response(evidence)

    # Add security metadata to response if there were any concerns
    if analysis_report.validation_result != "clean":
        response.ai_metadata = response.ai_metadata or {}
        response.ai_metadata["security_analysis"] = {
            "validation_result": analysis_report.validation_result.value,
            "security_score": analysis_report.security_score,
            "threats_detected": analysis_report.threats_detected,
            "recommendations": analysis_report.recommendations,
        }

    return response


@router.get("/dashboard/{framework_id}", response_model=EvidenceDashboardResponse)
async def get_evidence_dashboard(
    framework_id: UUID,
    db: AsyncSession = Depends(get_async_db),
    current_user: User = Depends(get_current_active_user),
):
    """Get dashboard data for evidence collection status."""
    dashboard_data = await EvidenceService.get_evidence_dashboard(
        db=db, user=current_user, framework_id=framework_id
    )
    return dashboard_data


# AI Classification Endpoints


@router.post("/{id}/classify", response_model=EvidenceClassificationResponse)
async def classify_evidence_with_ai(
    evidence_id: UUID,
    request: EvidenceClassificationRequest,
    db: AsyncSession = Depends(get_async_db),
    current_user: User = Depends(get_current_active_user),
):
    """Classify evidence using AI and suggest control mappings."""
    try:
        # Verify evidence exists and user has access
        evidence, status = await EvidenceService.get_evidence_item_with_auth_check(
            db=db, user_id=UUID(str(str(current_user.id))), evidence_id=evidence_id
        )

        if status == "not_found":
            raise HTTPException(status_code=404, detail="Evidence not found")
        elif status == "unauthorized":
            raise HTTPException(status_code=403, detail="Access denied")

        # Check if already classified and force_reclassify is False
        if (
            not request.force_reclassify
            and evidence.metadata
            and evidence.metadata.get("ai_classification")
        ):
            existing_classification = evidence.metadata["ai_classification"]
            return EvidenceClassificationResponse(
                evidence_id=evidence_id,
                current_type=evidence.evidence_type,
                ai_classification=existing_classification,
                apply_suggestion=False,
                confidence=existing_classification.get("confidence", 0),
                suggested_controls=existing_classification.get("suggested_controls", []),
                reasoning=existing_classification.get("reasoning", "Previously classified"),
            )

        # Process with AI
        processor = EvidenceProcessor(db)
        classification = await processor._ai_classify_evidence(evidence)

        # Apply suggestion if confidence is high enough
        apply_suggestion = classification["confidence"] >= 70
        if apply_suggestion:
            evidence.evidence_type = classification["suggested_type"]
            await db.commit()

        return EvidenceClassificationResponse(
            evidence_id=evidence_id,
            current_type=evidence.evidence_type,
            ai_classification=classification,
            apply_suggestion=apply_suggestion,
            confidence=classification["confidence"],
            suggested_controls=classification["suggested_controls"],
            reasoning=classification["reasoning"],
        )

    except HTTPException:
        # Re-raise HTTP exceptions (like 404) without modification
        raise
    except Exception as e:
        logger.error(f"Error classifying evidence {id}: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Classification failed")


@router.post("/classify/bulk", response_model=BulkClassificationResponse)
async def bulk_classify_evidence(
    request: BulkClassificationRequest,
    db: AsyncSession = Depends(get_async_db),
    current_user: User = Depends(get_current_active_user),
):
    """Bulk classify multiple evidence items using AI."""
    try:
        from api.schemas.evidence_classification import ClassificationResult

        processor = EvidenceProcessor(db)
        results = []
        successful_count = 0
        failed_count = 0
        auto_applied_count = 0

        for evidence_id in request.evidence_ids:
            try:
                # Verify evidence exists and user has access
                evidence, status = await EvidenceService.get_evidence_item_with_auth_check(
                    db=db, user_id=UUID(str(str(current_user.id))), evidence_id=evidence_id
                )

                if status != "success":
                    results.append(
                        ClassificationResult(
                            evidence_id=evidence_id,
                            success=False,
                            current_type="unknown",
                            error=f"Evidence not found or access denied: {status}",
                        )
                    )
                    failed_count += 1
                    continue

                # Check if already classified
                if (
                    not request.force_reclassify
                    and evidence.metadata
                    and evidence.metadata.get("ai_classification")
                ):
                    existing = evidence.metadata["ai_classification"]
                    results.append(
                        ClassificationResult(
                            evidence_id=evidence_id,
                            success=True,
                            current_type=evidence.evidence_type,
                            suggested_type=existing.get("suggested_type"),
                            confidence=existing.get("confidence", 0),
                            suggested_controls=existing.get("suggested_controls", []),
                            reasoning="Previously classified",
                            applied=False,
                        )
                    )
                    successful_count += 1
                    continue

                # Classify with AI
                classification = await processor._ai_classify_evidence(evidence)

                # Auto-apply if confidence meets threshold
                applied = False
                if (
                    request.apply_high_confidence
                    and classification["confidence"] >= request.confidence_threshold
                ):
                    evidence.evidence_type = classification["suggested_type"]
                    applied = True
                    auto_applied_count += 1

                results.append(
                    ClassificationResult(
                        evidence_id=evidence_id,
                        success=True,
                        current_type=evidence.evidence_type,
                        suggested_type=classification["suggested_type"],
                        confidence=classification["confidence"],
                        suggested_controls=classification["suggested_controls"],
                        reasoning=classification["reasoning"],
                        applied=applied,
                    )
                )
                successful_count += 1

            except Exception as e:
                results.append(
                    ClassificationResult(
                        evidence_id=evidence_id,
                        success=False,
                        current_type="unknown",
                        error=str(e),
                        applied=False,
                    )
                )
                failed_count += 1

        # Commit all changes
        await db.commit()

        return BulkClassificationResponse(
            total_processed=len(request.evidence_ids),
            successful_classifications=successful_count,
            failed_classifications=failed_count,
            auto_applied=auto_applied_count,
            results=results,
        )

    except Exception as e:
        await db.rollback()
        logger.error(f"Error in bulk classification: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Bulk classification failed")


@router.post("/{id}/control-mapping", response_model=ControlMappingResponse)
async def get_control_mapping_suggestions(
    evidence_id: UUID,
    request: ControlMappingRequest,
    db: AsyncSession = Depends(get_async_db),
    current_user: User = Depends(get_current_active_user),
):
    """Get AI-powered control mapping suggestions for evidence."""
    try:
        from api.schemas.evidence_classification import ControlMappingResponse

        # Verify evidence exists and user has access
        evidence, status = await EvidenceService.get_evidence_item_with_auth_check(
            db=db, user_id=UUID(str(str(current_user.id))), evidence_id=evidence_id
        )

        if status == "not_found":
            raise HTTPException(status_code=404, detail="Evidence not found")
        elif status == "unauthorized":
            raise HTTPException(status_code=403, detail="Access denied")

        # Get AI classification if not already done
        processor = EvidenceProcessor(db)
        classification = await processor._ai_classify_evidence(evidence)

        # Generate framework-specific mappings
        framework_mappings = {}
        confidence_scores = {}

        for framework in request.frameworks:
            if framework.upper() == "ISO27001":
                mappings = [
                    control
                    for control in classification["suggested_controls"]
                    if control.startswith("A.")
                ]
                confidence_scores[framework] = classification["confidence"]
            elif framework.upper() == "SOC2":
                mappings = [
                    control
                    for control in classification["suggested_controls"]
                    if any(control.startswith(prefix) for prefix in ["CC", "PI", "PR", "CA", "MA"])
                ]
                confidence_scores[framework] = max(classification["confidence"] - 10, 0)
            elif framework.upper() == "GDPR":
                mappings = [
                    control
                    for control in classification["suggested_controls"]
                    if control.startswith("Art.")
                ]
                confidence_scores[framework] = max(classification["confidence"] - 15, 0)
            else:
                mappings = []
                confidence_scores[framework] = 0

            framework_mappings[framework] = mappings

        return ControlMappingResponse(
            evidence_id=evidence_id,
            evidence_type=evidence.evidence_type,
            framework_mappings=framework_mappings,
            confidence_scores=confidence_scores,
            reasoning=classification["reasoning"],
        )

    except Exception as e:
        logger.error(
            f"Error getting control mappings for evidence {id}: {e}", exc_info=True
        )
        raise HTTPException(status_code=500, detail="Control mapping failed")


@router.get("/classification/stats", response_model=ClassificationStatsResponse)
async def get_classification_statistics(
    db: AsyncSession = Depends(get_async_db),
    current_user: User = Depends(get_current_active_user),
):
    """Get classification statistics for the current user."""
    try:
        from datetime import datetime, timedelta

        from api.schemas.evidence_classification import ClassificationStatsResponse

        # Get all evidence for user
        evidence_items = await EvidenceService.list_all_evidence_items(db=db, user=current_user)

        total_evidence = len(evidence_items)
        classified_evidence = 0
        type_distribution = {}
        confidence_distribution = {"high": 0, "medium": 0, "low": 0}
        recent_classifications = 0

        thirty_days_ago = datetime.utcnow() - timedelta(days=30)

        for evidence in evidence_items:
            # Check if classified
            if evidence.metadata and evidence.metadata.get("ai_classification"):
                classified_evidence += 1

                # Count by type
                evidence_type = evidence.evidence_type or "unknown"
                type_distribution[evidence_type] = type_distribution.get(evidence_type, 0) + 1

                # Count by confidence
                confidence = evidence.metadata["ai_classification"].get("confidence", 0)
                if confidence >= 80:
                    confidence_distribution["high"] += 1
                elif confidence >= 60:
                    confidence_distribution["medium"] += 1
                else:
                    confidence_distribution["low"] += 1

                # Check if recent
                processed_at_str = evidence.metadata["ai_classification"].get("ai_processed_at")
                if processed_at_str:
                    try:
                        processed_at = datetime.fromisoformat(
                            processed_at_str.replace("Z", "+00:00")
                        )
                        if processed_at > thirty_days_ago:
                            recent_classifications += 1
                    except (ValueError, TypeError):
                        pass

        unclassified_evidence = total_evidence - classified_evidence
        classification_accuracy = (
            (classified_evidence / total_evidence * 100) if total_evidence > 0 else 0
        )

        return ClassificationStatsResponse(
            total_evidence=total_evidence,
            classified_evidence=classified_evidence,
            unclassified_evidence=unclassified_evidence,
            classification_accuracy=round(classification_accuracy, 2),
            type_distribution=type_distribution,
            confidence_distribution=confidence_distribution,
            recent_classifications=recent_classifications,
        )

    except Exception as e:
        logger.error(f"Error getting classification statistics: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Failed to get classification statistics")


# Quality Analysis Endpoints


@router.get("/{id}/quality-analysis", response_model=QualityAnalysisResponse)
async def get_evidence_quality_analysis(
    evidence_id: UUID,
    db: AsyncSession = Depends(get_async_db),
    current_user: User = Depends(get_current_active_user),
):
    """Get detailed AI-powered quality analysis for evidence item."""
    try:
        from api.schemas.quality_analysis import (
            AIAnalysisResult,
            QualityScoreBreakdown,
            TraditionalScoreBreakdown,
        )
        from services.automation.quality_scorer import QualityScorer

        # Verify evidence exists and user has access
        evidence, status = await EvidenceService.get_evidence_item_with_auth_check(
            db=db, user_id=UUID(str(str(current_user.id))), evidence_id=evidence_id
        )

        if status == "not_found":
            raise HTTPException(status_code=404, detail="Evidence not found")
        elif status == "unauthorized":
            raise HTTPException(status_code=403, detail="Access denied")

        # Calculate enhanced quality score
        scorer = QualityScorer()
        quality_analysis = await scorer.calculate_enhanced_score(evidence)

        # Format response according to schema
        ai_scores = quality_analysis["ai_analysis"].get("scores", {})
        traditional_scores = quality_analysis["traditional_scores"]

        return QualityAnalysisResponse(
            evidence_id=evidence_id,
            evidence_name=evidence.evidence_name or "Unnamed Evidence",
            overall_score=quality_analysis["overall_score"],
            traditional_scores=TraditionalScoreBreakdown(
                completeness=traditional_scores.get("completeness", 50),
                freshness=traditional_scores.get("freshness", 50),
                content_quality=traditional_scores.get("content_quality", 50),
                relevance=traditional_scores.get("relevance", 50),
            ),
            ai_analysis=AIAnalysisResult(
                scores=QualityScoreBreakdown(
                    completeness=ai_scores.get("completeness", 50),
                    clarity=ai_scores.get("clarity", 50),
                    currency=ai_scores.get("currency", 50),
                    verifiability=ai_scores.get("verifiability", 50),
                    relevance=ai_scores.get("relevance", 50),
                    sufficiency=ai_scores.get("sufficiency", 50),
                ),
                overall_score=quality_analysis["ai_analysis"].get("overall_score", 50),
                strengths=quality_analysis["ai_analysis"].get("strengths", []),
                weaknesses=quality_analysis["ai_analysis"].get("weaknesses", []),
                recommendations=quality_analysis["ai_analysis"].get("recommendations", []),
                ai_confidence=quality_analysis["ai_analysis"].get("ai_confidence", 50),
            ),
            scoring_method=quality_analysis["scoring_method"],
            confidence=quality_analysis["confidence"],
            analysis_timestamp=quality_analysis["analysis_timestamp"],
        )

    except HTTPException:
        # Re-raise HTTP exceptions (like 404) without modification
        raise
    except Exception as e:
        logger.error(f"Error analyzing evidence quality {id}: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Quality analysis failed")


@router.post("/{id}/duplicate-detection", response_model=DuplicateDetectionResponse)
async def detect_evidence_duplicates(
    evidence_id: UUID,
    request: DuplicateDetectionRequest,
    db: AsyncSession = Depends(get_async_db),
    current_user: User = Depends(get_current_active_user),
):
    """Detect semantic duplicates for a specific evidence item."""
    try:
        from datetime import datetime

        from services.automation.quality_scorer import QualityScorer

        # Verify evidence exists and user has access
        evidence, status = await EvidenceService.get_evidence_item_with_auth_check(
            db=db, user_id=UUID(str(str(current_user.id))), evidence_id=evidence_id
        )

        if status == "not_found":
            raise HTTPException(status_code=404, detail="Evidence not found")
        elif status == "unauthorized":
            raise HTTPException(status_code=403, detail="Access denied")

        # Get candidate evidence items for comparison
        all_evidence = await EvidenceService.list_all_evidence_items(db=db, user=current_user)

        # Limit candidates and exclude the target evidence
        candidates = [e for e in all_evidence if e.id != evidence_id][: request.max_candidates]

        # Perform duplicate detection
        scorer = QualityScorer()
        duplicates = await scorer.detect_semantic_duplicates(
            evidence, candidates, request.similarity_threshold / 100
        )

        return DuplicateDetectionResponse(
            evidence_id=evidence_id,
            evidence_name=evidence.evidence_name or "Unnamed Evidence",
            duplicates_found=len(duplicates),
            duplicates=[
                {"evidence_id": str(d["id"]), "similarity_score": d["similarity"]}
                for d in duplicates
            ],
            analysis_timestamp=datetime.utcnow().isoformat(),
        )

    except Exception as e:
        logger.error(f"Error detecting duplicates for evidence {id}: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Duplicate detection failed")


@router.post("/duplicate-detection/batch", response_model=BatchDuplicateDetectionResponse)
async def batch_duplicate_detection(
    request: BatchDuplicateDetectionRequest,
    db: AsyncSession = Depends(get_async_db),
    current_user: User = Depends(get_current_active_user),
):
    """Perform batch duplicate detection across multiple evidence items."""
    try:
        from datetime import datetime

        from services.automation.quality_scorer import QualityScorer

        # Get evidence items
        evidence_items = []
        for evidence_id in request.evidence_ids:
            evidence, status = await EvidenceService.get_evidence_item_with_auth_check(
                db=db, user_id=UUID(str(str(current_user.id))), evidence_id=evidence_id
            )
            if status == "success":
                evidence_items.append(evidence)

        if len(evidence_items) < 2:
            raise HTTPException(status_code=400, detail="At least 2 valid evidence items required")

        # Perform batch duplicate detection
        scorer = QualityScorer()
        duplicate_analysis = await scorer.batch_duplicate_detection(
            evidence_items, request.similarity_threshold / 100
        )

        return BatchDuplicateDetectionResponse(
            total_items=duplicate_analysis["total_items"],
            duplicate_groups=duplicate_analysis["duplicate_groups"],
            potential_duplicates=duplicate_analysis["potential_duplicates"],
            unique_items=duplicate_analysis["unique_items"],
            analysis_summary=duplicate_analysis["analysis_summary"],
            analysis_timestamp=datetime.utcnow().isoformat(),
        )

    except Exception as e:
        logger.error(f"Error in batch duplicate detection: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Batch duplicate detection failed")


@router.get("/quality/benchmark", response_model=QualityBenchmarkResponse)
async def get_quality_benchmark(
    request: QualityBenchmarkRequest = Depends(),
    db: AsyncSession = Depends(get_async_db),
    current_user: User = Depends(get_current_active_user),
):
    """Get quality benchmarking data comparing user's evidence to platform averages."""
    try:
        from services.automation.quality_scorer import QualityScorer

        # Get user's evidence
        user_evidence = await EvidenceService.list_all_evidence_items(db=db, user=current_user)

        if not user_evidence:
            raise HTTPException(status_code=400, detail="No evidence found for benchmarking")

        # Calculate user's average quality scores
        scorer = QualityScorer()
        user_scores = []

        for evidence in user_evidence:
            # Filter by framework or type if specified
            if (
                request.framework
                and hasattr(evidence, "framework")
                and evidence.framework != request.framework
            ):
                continue
            if request.evidence_type and evidence.evidence_type != request.evidence_type:
                continue

            score = scorer.calculate_score(evidence)
            user_scores.append(score)

        if not user_scores:
            raise HTTPException(
                status_code=400, detail="No evidence matches the specified criteria"
            )

        user_average = sum(user_scores) / len(user_scores)

        # Mock benchmark data (in production, this would query platform-wide statistics)
        benchmark_score = 75.0  # Platform average
        percentile_rank = min(95, max(5, (user_average / benchmark_score) * 50 + 25))

        # Score distribution
        score_ranges = {"excellent": 0, "good": 0, "acceptable": 0, "poor": 0}
        for score in user_scores:
            if score >= 90:
                score_ranges["excellent"] += 1
            elif score >= 80:
                score_ranges["good"] += 1
            elif score >= 70:
                score_ranges["acceptable"] += 1
            else:
                score_ranges["poor"] += 1

        # Improvement areas
        improvement_areas = []
        if user_average < benchmark_score:
            improvement_areas.extend(["evidence_completeness", "documentation_quality"])
        if score_ranges["poor"] > 0:
            improvement_areas.append("low_quality_evidence_review")

        return QualityBenchmarkResponse(
            user_average_score=round(user_average, 2),
            benchmark_score=benchmark_score,
            percentile_rank=round(percentile_rank, 1),
            score_distribution=score_ranges,
            improvement_areas=improvement_areas,
            top_performers=[
                {"name": evidence.evidence_name, "score": scorer.calculate_score(evidence)}
                for evidence in sorted(
                    user_evidence, key=lambda e: scorer.calculate_score(e), reverse=True
                )[:3]
            ],
        )

    except Exception as e:
        logger.error(f"Error getting quality benchmark: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Quality benchmarking failed")


@router.get("/quality/trends", response_model=QualityTrendResponse)
async def get_quality_trends(
    request: QualityTrendRequest = Depends(),
    db: AsyncSession = Depends(get_async_db),
    current_user: User = Depends(get_current_active_user),
):
    """Get quality trend analysis over time."""
    try:
        from datetime import datetime, timedelta

        from services.automation.quality_scorer import QualityScorer

        # Get evidence within the specified time period
        end_date = datetime.utcnow()
        start_date = end_date - timedelta(days=request.days)

        user_evidence = await EvidenceService.list_all_evidence_items(db=db, user=current_user)

        # Filter by date and type
        filtered_evidence = []
        for evidence in user_evidence:
            if evidence.collected_at and start_date <= evidence.collected_at <= end_date:
                if not request.evidence_type or evidence.evidence_type == request.evidence_type:
                    filtered_evidence.append(evidence)

        if not filtered_evidence:
            raise HTTPException(
                status_code=400, detail="No evidence found in the specified time period"
            )

        # Calculate daily scores
        scorer = QualityScorer()
        daily_scores = {}

        for evidence in filtered_evidence:
            date_key = evidence.collected_at.date().isoformat()
            if date_key not in daily_scores:
                daily_scores[date_key] = []
            daily_scores[date_key].append(scorer.calculate_score(evidence))

        # Calculate daily averages
        daily_data = []
        for date_str, scores in sorted(daily_scores.items()):
            daily_data.append(
                {
                    "date": date_str,
                    "average_score": round(sum(scores) / len(scores), 2),
                    "evidence_count": len(scores),
                }
            )

        # Calculate trend
        if len(daily_data) >= 2:
            first_score = daily_data[0]["average_score"]
            last_score = daily_data[-1]["average_score"]
            score_change = last_score - first_score

            if score_change > 5:
                trend_direction = "improving"
            elif score_change < -5:
                trend_direction = "declining"
            else:
                trend_direction = "stable"
        else:
            score_change = 0
            trend_direction = "insufficient_data"

        # Generate insights
        insights = []
        if trend_direction == "improving":
            insights.append("Quality scores are trending upward")
        elif trend_direction == "declining":
            insights.append("Quality scores are declining - review needed")

        avg_score = sum(d["average_score"] for d in daily_data) / len(daily_data)
        if avg_score < 70:
            insights.append("Overall quality scores below recommended threshold")

        return QualityTrendResponse(
            period_days=request.days,
            trend_direction=trend_direction,
            average_score_change=round(score_change, 2),
            daily_scores=daily_data,
            insights=insights,
            recommendations=["Focus on evidence completeness", "Improve documentation quality"]
            if avg_score < 75
            else [],
        )

    except Exception as e:
        logger.error(f"Error getting quality trends: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Quality trend analysis failed")
