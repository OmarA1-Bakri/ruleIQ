"""

Feedback Collection API Router

Endpoints for collecting and managing user feedback including:
- Single and batch feedback submission
- Feedback retrieval and aggregation
- Analytics and pattern detection
- Model fine-tuning triggers
"""

import logging
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
from uuid import UUID
from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession
from api.dependencies.auth import get_current_active_user
from api.dependencies.database import get_async_db
from database.user import User
from services.ai.feedback_analyzer import FeedbackAnalyzer, FeedbackItem, FeedbackType
from services.ai.feedback_storage import FeedbackStorage
logger = logging.getLogger(__name__)
router = APIRouter()
feedback_storage = FeedbackStorage()


class FeedbackSubmissionRequest(BaseModel):
    """Request model for submitting feedback."""
    run_id: str = Field(..., description='LangSmith run ID')
    feedback_type: FeedbackType = Field(..., description='Type of feedback')
    value: Optional[Any] = Field(None, description=
        'Feedback value (rating, correction, etc.)')
    comment: Optional[str] = Field(None, description='Optional comment')
    metadata: Dict[str, Any] = Field(default_factory=dict, description=
        'Additional metadata')


class BatchFeedbackRequest(BaseModel):
    """Request model for batch feedback submission."""
    feedback_items: List[FeedbackSubmissionRequest] = Field(...,
        description='List of feedback items to submit')


class FeedbackResponse(BaseModel):
    """Response model for feedback submission."""
    feedback_id: str = Field(..., description='Unique feedback ID')
    status: str = Field(..., description='Submission status')
    message: str = Field(..., description='Status message')


class FeedbackRetrievalResponse(BaseModel):
    """Response model for feedback retrieval."""
    feedback_items: List[Dict[str, Any]] = Field(..., description=
        'Retrieved feedback items')
    total_count: int = Field(..., description='Total number of items')
    page: int = Field(1, description='Current page')
    page_size: int = Field(50, description='Items per page')


class FeedbackAggregationResponse(BaseModel):
    """Response model for feedback aggregation."""
    statistics: Dict[str, Any] = Field(..., description='Aggregated statistics',
        )
    patterns: Dict[str, Any] = Field(..., description='Detected patterns')
    triggers: List[str] = Field(default_factory=list, description=
        'Triggered model updates')
    recommendations: List[str] = Field(default_factory=list, description=
        'Improvement recommendations')


class FeedbackMetricsResponse(BaseModel):
    """Response model for feedback metrics."""
    response_time_p50: float = Field(..., description='Median response time')
    response_time_p95: float = Field(..., description=
        '95th percentile response time')
    incorporation_rate: float = Field(..., description=
        'Feedback incorporation rate')
    satisfaction_trend: str = Field(..., description='User satisfaction trend')
    active_users: int = Field(..., description=
        'Number of active feedback providers')


@router.post('/submit', response_model=FeedbackResponse)
async def submit_feedback(request: FeedbackSubmissionRequest, current_user:
    User=Depends(get_current_active_user), db: AsyncSession=Depends(
    get_async_db)) ->FeedbackResponse:
    """
    Submit a single feedback item.

    Args:
        request: Feedback submission request
        current_user: Currently authenticated user
        db: Database session

    Returns:
        FeedbackResponse with submission status
    """
    try:
        feedback_item = FeedbackItem(feedback_id=str(UUID.uuid4()), run_id=
            request.run_id, user_id=str(current_user.id), feedback_type=
            request.feedback_type, value=request.value, comment=request.
            comment, metadata={**request.metadata, 'user_email':
            current_user.email, 'submission_time': datetime.now(timezone.
            utc).isoformat()})
        success = await feedback_storage.store_feedback(feedback_item)
        if success:
            logger.info('Feedback submitted successfully: %s' %
                feedback_item.feedback_id)
            return FeedbackResponse(feedback_id=feedback_item.feedback_id,
                status='success', message='Feedback submitted successfully')
        else:
            raise HTTPException(status_code=status.
                HTTP_500_INTERNAL_SERVER_ERROR, detail=
                'Failed to store feedback')
    except Exception as e:
        logger.error('Error submitting feedback: %s' % str(e))
        raise HTTPException(status_code=status.
            HTTP_500_INTERNAL_SERVER_ERROR, detail=
            f'Error submitting feedback: {str(e)}')


@router.post('/batch', response_model=List[FeedbackResponse])
async def submit_batch_feedback(request: BatchFeedbackRequest, current_user:
    User=Depends(get_current_active_user), db: AsyncSession=Depends(
    get_async_db)) ->List[FeedbackResponse]:
    """
    Submit multiple feedback items in batch.

    Args:
        request: Batch feedback submission request
        current_user: Currently authenticated user
        db: Database session

    Returns:
        List of FeedbackResponse for each item
    """
    responses = []
    for feedback_request in request.feedback_items:
        try:
            feedback_item = FeedbackItem(feedback_id=str(UUID.uuid4()),
                run_id=feedback_request.run_id, user_id=str(current_user.id
                ), feedback_type=feedback_request.feedback_type, value=
                feedback_request.value, comment=feedback_request.comment,
                metadata={**feedback_request.metadata, 'user_email':
                current_user.email, 'submission_time': datetime.now(
                timezone.utc).isoformat(), 'batch_submission': True})
            success = await feedback_storage.store_feedback(feedback_item)
            if success:
                responses.append(FeedbackResponse(feedback_id=feedback_item
                    .feedback_id, status='success', message=
                    'Feedback submitted successfully'))
            else:
                responses.append(FeedbackResponse(feedback_id='', status=
                    'failed', message='Failed to store feedback'))
        except Exception as e:
            logger.error('Error in batch submission: %s' % str(e))
            responses.append(FeedbackResponse(feedback_id='', status=
                'error', message=str(e)))
    return responses


@router.get('/retrieve/{feedback_id}', response_model=Dict[str, Any])
async def retrieve_feedback_by_id(feedback_id: str, current_user: User=
    Depends(get_current_active_user), db: AsyncSession=Depends(get_async_db)
    ) ->Dict[str, Any]:
    """
    Retrieve a specific feedback item by ID.

    Args:
        feedback_id: Unique feedback identifier
        current_user: Currently authenticated user
        db: Database session

    Returns:
        Feedback item details
    """
    try:
        feedback = await feedback_storage.get_feedback_by_id(feedback_id)
        if not feedback:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND,
                detail=f'Feedback {feedback_id} not found')
        if feedback.get('user_id') != str(current_user.id
            ) and not current_user.is_admin:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN,
                detail='Not authorized to view this feedback')
        return feedback
    except HTTPException:
        raise
    except Exception as e:
        logger.error('Error retrieving feedback: %s' % str(e))
        raise HTTPException(status_code=status.
            HTTP_500_INTERNAL_SERVER_ERROR, detail=
            f'Error retrieving feedback: {str(e)}')


@router.get('/run/{run_id}', response_model=FeedbackRetrievalResponse)
async def retrieve_run_feedback(run_id: str, page: int=Query(1, ge=1,
    description='Page number'), page_size: int=Query(50, ge=1, le=100,
    description='Items per page'), current_user: User=Depends(
    get_current_active_user), db: AsyncSession=Depends(get_async_db)
    ) ->FeedbackRetrievalResponse:
    """
    Retrieve all feedback for a specific run.

    Args:
        run_id: LangSmith run ID
        page: Page number for pagination
        page_size: Number of items per page
        current_user: Currently authenticated user
        db: Database session

    Returns:
        Paginated feedback items for the run
    """
    try:
        all_feedback = await feedback_storage.get_feedback_by_run(run_id)
        start_idx = (page - 1) * page_size
        end_idx = start_idx + page_size
        paginated_feedback = all_feedback[start_idx:end_idx]
        return FeedbackRetrievalResponse(feedback_items=paginated_feedback,
            total_count=len(all_feedback), page=page, page_size=page_size)
    except Exception as e:
        logger.error('Error retrieving run feedback: %s' % str(e))
        raise HTTPException(status_code=status.
            HTTP_500_INTERNAL_SERVER_ERROR, detail=
            f'Error retrieving run feedback: {str(e)}')


@router.get('/aggregate', response_model=FeedbackAggregationResponse)
async def get_feedback_aggregation(start_date: Optional[datetime]=Query(
    None, description='Start date for aggregation'), end_date: Optional[
    datetime]=Query(None, description='End date for aggregation'), user_id:
    Optional[str]=Query(None, description='Filter by user ID'),
    current_user: User=Depends(get_current_active_user), db: AsyncSession=
    Depends(get_async_db)) ->FeedbackAggregationResponse:
    """
    Get aggregated feedback statistics and patterns.

    Args:
        start_date: Optional start date filter
        end_date: Optional end date filter
        user_id: Optional user ID filter
        current_user: Currently authenticated user
        db: Database session

    Returns:
        Aggregated feedback statistics and patterns
    """
    try:
        all_feedback = await feedback_storage.get_all_feedback()
        if start_date or end_date:
            filtered_feedback = []
            for item in all_feedback:
                item_date = datetime.fromisoformat(item.get('timestamp',
                    datetime.now(timezone.utc).isoformat()))
                if start_date and item_date < start_date:
                    continue
                if end_date and item_date > end_date:
                    continue
                filtered_feedback.append(item)
            all_feedback = filtered_feedback
        if user_id:
            if user_id != str(current_user.id) and not current_user.is_admin:
                raise HTTPException(status_code=status.HTTP_403_FORBIDDEN,
                    detail="Not authorized to view other users' feedback")
            all_feedback = [f for f in all_feedback if f.get('user_id') ==
                user_id]
        feedback_items = []
        for item in all_feedback:
            try:
                feedback_items.append(FeedbackItem(**item))
            except Exception as e:
                logger.warning('Skipping invalid feedback item: %s' % e)
                continue
        analyzer = FeedbackAnalyzer(feedback_items)
        statistics = analyzer.calculate_statistics()
        patterns = analyzer.identify_patterns()
        triggers = []
        trigger_results = analyzer.check_fine_tuning_triggers()
        if trigger_results.get('correction_threshold', False):
            triggers.append(
                'High correction rate detected - consider model fine-tuning')
        if trigger_results.get('low_ratings', False):
            triggers.append(
                'Low average ratings detected - review model performance')
        if trigger_results.get('negative_sentiment', False):
            triggers.append(
                'High negative sentiment detected - investigate user concerns')
        recommendations = patterns.get('recommendations', [])
        return FeedbackAggregationResponse(statistics=statistics, patterns=
            patterns, triggers=triggers, recommendations=recommendations)
    except HTTPException:
        raise
    except Exception as e:
        logger.error('Error aggregating feedback: %s' % str(e))
        raise HTTPException(status_code=status.
            HTTP_500_INTERNAL_SERVER_ERROR, detail=
            f'Error aggregating feedback: {str(e)}')


@router.get('/metrics', response_model=FeedbackMetricsResponse)
async def get_feedback_metrics(window_days: int=Query(30, ge=1, le=365,
    description='Time window in days'), current_user: User=Depends(
    get_current_active_user), db: AsyncSession=Depends(get_async_db)
    ) ->FeedbackMetricsResponse:
    """
    Get feedback loop performance metrics.

    Args:
        window_days: Time window for metrics calculation
        current_user: Currently authenticated user
        db: Database session

    Returns:
        Feedback loop performance metrics
    """
    try:
        cutoff_date = datetime.now(timezone.utc) - timedelta(days=window_days)
        all_feedback = await feedback_storage.get_all_feedback()
        recent_feedback = []
        for item in all_feedback:
            item_date = datetime.fromisoformat(item.get('timestamp',
                datetime.now(timezone.utc).isoformat()))
            if item_date >= cutoff_date:
                recent_feedback.append(item)
        feedback_items = []
        for item in recent_feedback:
            try:
                feedback_items.append(FeedbackItem(**item))
            except Exception as e:
                logger.warning('Skipping invalid feedback item: %s' % e)
                continue
        analyzer = FeedbackAnalyzer(feedback_items)
        metrics = analyzer.calculate_loop_metrics()
        trend_data = analyzer.analyze_trends(window_days=window_days)
        if trend_data.get('rating_trend', 0) > 0:
            satisfaction_trend = 'improving'
        elif trend_data.get('rating_trend', 0) < 0:
            satisfaction_trend = 'declining'
        else:
            satisfaction_trend = 'stable'
        active_users = len(set(item.user_id for item in feedback_items))
        return FeedbackMetricsResponse(response_time_p50=metrics.get(
            'response_time_p50', 0.0), response_time_p95=metrics.get(
            'response_time_p95', 0.0), incorporation_rate=metrics.get(
            'incorporation_rate', 0.0), satisfaction_trend=
            satisfaction_trend, active_users=active_users)
    except Exception as e:
        logger.error('Error calculating metrics: %s' % str(e))
        raise HTTPException(status_code=status.
            HTTP_500_INTERNAL_SERVER_ERROR, detail=
            f'Error calculating metrics: {str(e)}')


@router.post('/export')
async def export_feedback(format: str=Query('json', regex='^(json|csv)$',
    description='Export format'), start_date: Optional[datetime]=Query(None,
    description='Start date for export'), end_date: Optional[datetime]=
    Query(None, description='End date for export'), current_user: User=
    Depends(get_current_active_user), db: AsyncSession=Depends(get_async_db)
    ) ->Dict[str, Any]:
    """
    Export feedback data for analysis or backup.

    Args:
        format: Export format (json or csv)
        start_date: Optional start date filter
        end_date: Optional end date filter
        current_user: Currently authenticated user (must be admin)
        db: Database session

    Returns:
        Export status and file location
    """
    if not current_user.is_admin:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=
            'Admin permission required for export')
    try:
        result = await feedback_storage.export_feedback(format=format,
            start_date=start_date, end_date=end_date)
        return {'status': 'success', 'message':
            'Feedback exported successfully', 'file_path': result.get(
            'file_path'), 'record_count': result.get('record_count'),
            'export_date': datetime.now(timezone.utc).isoformat()}
    except Exception as e:
        logger.error('Error exporting feedback: %s' % str(e))
        raise HTTPException(status_code=status.
            HTTP_500_INTERNAL_SERVER_ERROR, detail=
            f'Error exporting feedback: {str(e)}')


from datetime import timedelta
