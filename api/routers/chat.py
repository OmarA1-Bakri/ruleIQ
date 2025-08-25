"""
FastAPI router for chat functionality with the AI assistant.
"""

import asyncio
import logging
from datetime import datetime
from typing import List, Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import desc, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import Session

from api.dependencies.auth import get_current_active_user
from database.user import User
from api.schemas.chat import (
    ComplianceAnalysisRequest,
    ComplianceAnalysisResponse,
    ConversationListResponse,
    ConversationResponse,
    ConversationSummary,
    CreateConversationRequest,
    EvidenceRecommendationRequest,
    EvidenceRecommendationResponse,
    MessageResponse,
    SendMessageRequest,
)
from database.business_profile import BusinessProfile
from database.chat_conversation import ChatConversation, ConversationStatus
from database.chat_message import ChatMessage
from database.db_setup import get_async_db, get_db
from services.ai import ComplianceAssistant

# Set up logging
logger = logging.getLogger(__name__)

router = APIRouter(tags=["Chat Assistant"])


@router.post("/conversations", response_model=dict)
async def create_conversation(
    request: CreateConversationRequest,
    db: AsyncSession = Depends(get_async_db),
    current_user: User = Depends(get_current_active_user),
):
    """Create a new chat conversation with optimized database queries."""
    try:
        from sqlalchemy import func, select

        # Optimized: Single query to get both business profile and conversation count
        user_id_str = str(current_user.id)

        # Use a single query with subquery for better performance
        profile_stmt = select(BusinessProfile).where(BusinessProfile.user_id == user_id_str)
        count_stmt = select(func.count(ChatConversation.id)).where(ChatConversation.user_id == user_id_str)

        # Execute both queries concurrently
        profile_task = asyncio.create_task(db.execute(profile_stmt))
        count_task = asyncio.create_task(db.execute(count_stmt))

        try:
            profile_result, count_result = await asyncio.gather(profile_task, count_task)
        except Exception as e:
            logger.error(f"Database query failed: {e}")
            raise HTTPException(status_code=500, detail="Database query failed")

        business_profile = profile_result.scalars().first()
        conversation_count = count_result.scalar() or 0

        if not business_profile:
            raise HTTPException(
                status_code=400,
                detail="No business profile found. Please complete your profile setup first.",
            )

        # Create new conversation
        conversation = ChatConversation(
            user_id=user_id_str,
            business_profile_id=business_profile.id,
            title=request.title or f"Chat {conversation_count + 1}",
            status=ConversationStatus.ACTIVE,
        )

        db.add(conversation)
        await db.flush()  # Get the conversation ID

        messages = []

        # If there's an initial message, process it with optimizations
        if request.initial_message:
            try:
                # Use optimized assistant initialization
                assistant = ComplianceAssistant(db)

                # Add user message
                user_message = ChatMessage(
                    conversation_id=conversation.id,
                    role="user",
                    content=request.initial_message,
                    sequence_number=1,
                )
                db.add(user_message)

                # Generate assistant response with enhanced error handling and timeout
                logger.info(f"Processing initial message for conversation {conversation.id}")

                # Use asyncio timeout to prevent hanging
                try:
                    response_task = asyncio.create_task(
                        assistant.process_message(
                            conversation_id=conversation.id,
                            user=current_user,
                            message=request.initial_message,
                            business_profile_id=business_profile.id,
                        )
                    )

                    # Aggressive timeout for conversation creation
                    response_text, metadata = await asyncio.wait_for(response_task, timeout=12.0)

                except asyncio.TimeoutError:
                    logger.warning(f"AI processing timed out for conversation {conversation.id}")
                    # Use fallback response
                    response_text = """I understand you'd like to discuss compliance matters. Due to high demand, I'm providing a quick response:

I'm here to help with compliance questions about GDPR, ISO 27001, and other frameworks. Please feel free to ask specific questions about:
• Data protection requirements
• Security controls and policies  
• Risk assessments
• Audit preparations

What specific compliance topic would you like to explore?"""

                    metadata = {
                        "timestamp": datetime.utcnow().isoformat(),
                        "fallback_used": True,
                        "timeout_occurred": True,
                        "intent": "general",
                        "processing_time_ms": 12000
                    }

                # Add assistant message
                assistant_message = ChatMessage(
                    conversation_id=conversation.id,
                    role="assistant",
                    content=response_text,
                    message_metadata=metadata,
                    sequence_number=2,
                )
                db.add(assistant_message)

                messages = [user_message, assistant_message]

            except Exception as ai_error:
                logger.error(f"AI processing failed for conversation {conversation.id}: {ai_error}", exc_info=True)

                # Still add the user message but provide a fallback response
                user_message = ChatMessage(
                    conversation_id=conversation.id,
                    role="user",
                    content=request.initial_message,
                    sequence_number=1,
                )
                db.add(user_message)

                # Provide fallback assistant response
                fallback_response = """Thank you for your message. I'm currently experiencing high demand but I'm here to help with your compliance questions.

Please feel free to ask about:
• GDPR and data protection
• ISO 27001 and security frameworks
• Risk assessments and audits
• Policy development

What specific compliance area can I assist you with?"""

                assistant_message = ChatMessage(
                    conversation_id=conversation.id,
                    role="assistant",
                    content=fallback_response,
                    message_metadata={
                        "timestamp": datetime.utcnow().isoformat(),
                        "fallback_used": True,
                        "ai_error": str(ai_error),
                        "intent": "fallback"
                    },
                    sequence_number=2,
                )
                db.add(assistant_message)

                messages = [user_message, assistant_message]

        # Commit all changes
        await db.commit()

        # Return conversation with messages
        return {
            "id": conversation.id,
            "title": conversation.title,
            "status": conversation.status.value,
            "created_at": conversation.created_at.isoformat(),
            "updated_at": conversation.updated_at.isoformat(),
            "messages": [
                {
                    "id": msg.id,
                    "role": msg.role,
                    "content": msg.content,
                    "metadata": msg.message_metadata or {},
                    "created_at": msg.created_at.isoformat(),
                    "sequence_number": msg.sequence_number,
                }
                for msg in messages
            ],
        }

    except HTTPException:
        raise
    except Exception as e:
        await db.rollback()
        logger.error(f"Unexpected error creating conversation: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Failed to create conversation")


@router.get("/conversations", response_model=ConversationListResponse)
async def list_conversations(
    page: int = Query(1, ge=1),
    per_page: int = Query(20, ge=1, le=100),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    """List user's chat conversations."""
    try:
        # Get total count
        total = (
            db.query(ChatConversation)
            .filter(
                ChatConversation.user_id == str(current_user.id),
                ChatConversation.status != ConversationStatus.DELETED,
            )
            .count()
        )

        # Get conversations with pagination
        conversations = (
            db.query(ChatConversation)
            .filter(
                ChatConversation.user_id == str(current_user.id),
                ChatConversation.status != ConversationStatus.DELETED,
            )
            .order_by(desc(ChatConversation.updated_at))
            .offset((page - 1) * per_page)
            .limit(per_page)
            .all()
        )

        # Get message counts and last message times
        conversation_summaries = []
        for conv in conversations:
            message_count = (
                db.query(ChatMessage).filter(ChatMessage.conversation_id == conv.id).count()
            )

            last_message = (
                db.query(ChatMessage)
                .filter(ChatMessage.conversation_id == conv.id)
                .order_by(desc(ChatMessage.created_at))
                .first()
            )

            conversation_summaries.append(
                ConversationSummary(
                    id=conv.id,
                    title=conv.title,
                    status=conv.status.value,
                    message_count=message_count,
                    last_message_at=last_message.created_at if last_message else None,
                    created_at=conv.created_at,
                )
            )

        return ConversationListResponse(
            conversations=conversation_summaries, total=total, page=page, per_page=per_page
        )

    except Exception as e:
        logger.error(f"Error listing conversations: {e}")
        raise HTTPException(status_code=500, detail="Failed to list conversations")


@router.get("/conversations/{conversation_id}", response_model=ConversationResponse)
async def get_conversation(
    conversation_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    """Get a specific conversation with all messages."""
    try:
        conversation = (
            db.query(ChatConversation)
            .filter(
                ChatConversation["id"] == conversation_id, ChatConversation.user_id == str(current_user.id)
            )
            .first()
        )

        if not conversation:
            raise HTTPException(status_code=404, detail="Conversation not found")

        messages = (
            db.query(ChatMessage)
            .filter(ChatMessage.conversation_id == conversation_id)
            .order_by(ChatMessage.sequence_number)
            .all()
        )

        return ConversationResponse(
            id=conversation.id,
            title=conversation.title,
            status=conversation.status.value,
            messages=[MessageResponse.from_orm(msg) for msg in messages],
            created_at=conversation.created_at,
            updated_at=conversation.updated_at,
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting conversation: {e}")
        raise HTTPException(status_code=500, detail="Failed to get conversation")


@router.post("/conversations/{conversation_id}/messages", response_model=MessageResponse)
async def send_message(
    conversation_id: UUID,
    request: SendMessageRequest,
    db: AsyncSession = Depends(get_async_db),
    current_user: User = Depends(get_current_active_user),
):
    """Send a message in a conversation."""
    try:
        from sqlalchemy import desc, select

        # Verify conversation exists and belongs to user
        conv_stmt = select(ChatConversation).where(
            ChatConversation.id == conversation_id,
            ChatConversation.user_id == str(current_user.id),
            ChatConversation.status == ConversationStatus.ACTIVE,
        )
        conv_result = await db.execute(conv_stmt)
        conversation = conv_result.scalars().first()

        if not conversation:
            raise HTTPException(status_code=404, detail="Conversation not found or inactive")

        # Get business profile
        bp_stmt = select(BusinessProfile).where(BusinessProfile.user_id == str(str(current_user.id)))
        bp_result = await db.execute(bp_stmt)
        business_profile = bp_result.scalars().first()

        if not business_profile:
            raise HTTPException(status_code=400, detail="Business profile not found")

        # Get next sequence number
        msg_stmt = (
            select(ChatMessage)
            .where(ChatMessage.conversation_id == conversation_id)
            .order_by(desc(ChatMessage.sequence_number))
        )
        msg_result = await db.execute(msg_stmt)
        last_message = msg_result.scalars().first()

        next_sequence = (last_message.sequence_number + 1) if last_message else 1

        # Add user message
        user_message = ChatMessage(
            conversation_id=conversation_id,
            role="user",
            content=request.message,
            sequence_number=next_sequence,
        )
        db.add(user_message)
        await db.flush()

        # Generate assistant response
        assistant = ComplianceAssistant(db)
        response_text, metadata = await assistant.process_message(
            conversation_id=conversation_id,
            user=current_user,
            message=request.message,
            business_profile_id=business_profile.id,
        )

        # Add assistant message
        assistant_message = ChatMessage(
            conversation_id=conversation_id,
            role="assistant",
            content=response_text,
            metadata=metadata,
            sequence_number=next_sequence + 1,
        )
        db.add(assistant_message)

        # Update conversation timestamp
        from datetime import datetime

        conversation.updated_at = datetime.utcnow()

        await db.commit()

        return MessageResponse.from_orm(assistant_message)

    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        logger.error(f"Error sending message: {e}")
        raise HTTPException(status_code=500, detail="Failed to send message")


@router.delete("/conversations/{conversation_id}")
async def delete_conversation(
    conversation_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    """Delete (archive) a conversation."""
    try:
        conversation = (
            db.query(ChatConversation)
            .filter(
                ChatConversation["id"] == conversation_id, ChatConversation.user_id == str(current_user.id)
            )
            .first()
        )

        if not conversation:
            raise HTTPException(status_code=404, detail="Conversation not found")

        conversation.status = ConversationStatus.DELETED
        db.commit()

        return {"message": "Conversation deleted successfully"}

    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        logger.error(f"Error deleting conversation: {e}")
        raise HTTPException(status_code=500, detail="Failed to delete conversation")


@router.post("/evidence-recommendations", response_model=List[EvidenceRecommendationResponse])
async def get_evidence_recommendations(
    request: EvidenceRecommendationRequest,
    db: AsyncSession = Depends(get_async_db),
    current_user: User = Depends(get_current_active_user),
):
    """Get AI-powered evidence collection recommendations."""
    try:
        # Use async query for business profile
        stmt = select(BusinessProfile).where(BusinessProfile.user_id == str(str(current_user.id)))
        result = await db.execute(stmt)
        business_profile = result.scalars().first()

        if not business_profile:
            raise HTTPException(status_code=400, detail="Business profile not found")

        assistant = ComplianceAssistant(db)
        recommendations = await assistant.get_evidence_recommendations(
            user=current_user,
            business_profile_id=UUID(str(business_profile.id)),
            target_framework=request.framework or "unknown",
        )

        return [EvidenceRecommendationResponse(**rec) for rec in recommendations]

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting evidence recommendations: {e}")
        raise HTTPException(status_code=500, detail="Failed to get recommendations")


@router.post("/compliance-analysis", response_model=ComplianceAnalysisResponse)
async def analyze_compliance_gap(
    request: ComplianceAnalysisRequest,
    db: AsyncSession = Depends(get_async_db),
    current_user: User = Depends(get_current_active_user),
):
    """Analyze compliance gaps for a specific framework."""
    try:
        from sqlalchemy import select

        # Use async query for business profile
        stmt = select(BusinessProfile).where(BusinessProfile.user_id == str(str(current_user.id)))
        result = await db.execute(stmt)
        business_profile = result.scalars().first()

        if not business_profile:
            raise HTTPException(status_code=400, detail="Business profile not found")

        assistant = ComplianceAssistant(db)
        analysis = await assistant.analyze_evidence_gap(
            business_profile_id=UUID(str(business_profile.id)), framework=request.framework
        )

        return ComplianceAnalysisResponse(**analysis)

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error analyzing compliance gap: {e}")
        raise HTTPException(status_code=500, detail="Failed to analyze compliance gap")


@router.post("/context-aware-recommendations")
async def get_context_aware_recommendations(
    framework: str = Query(..., min_length=1, description="Framework to get recommendations for"),
    context_type: str = Query(default="comprehensive", description="Type of context analysis"),
    db: AsyncSession = Depends(get_async_db),
    current_user: User = Depends(get_current_active_user),
):
    """
    Get enhanced context-aware evidence recommendations that consider:
    - Business profile and industry specifics
    - Existing evidence and gaps
    - User behavior patterns
    - Compliance maturity level
    - Risk assessment
    """
    try:
        # Use async query for business profile
        stmt = select(BusinessProfile).where(BusinessProfile.user_id == str(str(current_user.id)))
        result = await db.execute(stmt)
        business_profile = result.scalars().first()

        if not business_profile:
            raise HTTPException(status_code=400, detail="Business profile not found")

        assistant = ComplianceAssistant(db)
        recommendations = await assistant.get_context_aware_recommendations(
            user=current_user,
            business_profile_id=UUID(str(business_profile.id)),
            framework=framework,
            context_type=context_type,
        )

        return recommendations

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting context-aware recommendations: {e}")
        raise HTTPException(status_code=500, detail="Failed to get context-aware recommendations")


@router.post("/evidence-collection-workflow")
async def generate_evidence_collection_workflow(
    framework: str = Query(..., min_length=1, description="Framework for workflow generation"),
    control_id: Optional[str] = Query(None, description="Specific control ID (optional)"),
    workflow_type: str = Query(default="comprehensive", description="Type of workflow"),
    db: AsyncSession = Depends(get_async_db),
    current_user: User = Depends(get_current_active_user),
):
    """
    Generate intelligent, step-by-step evidence collection workflows
    tailored to specific frameworks, controls, and business contexts.
    """
    try:
        # Use async query for business profile
        stmt = select(BusinessProfile).where(BusinessProfile.user_id == str(str(current_user.id)))
        result = await db.execute(stmt)
        business_profile = result.scalars().first()

        if not business_profile:
            raise HTTPException(status_code=400, detail="Business profile not found")

        assistant = ComplianceAssistant(db)
        workflow = await assistant.generate_evidence_collection_workflow(
            user=current_user,
            business_profile_id=UUID(str(business_profile.id)),
            framework=framework,
            control_id=control_id or "general",
            workflow_type=workflow_type,
        )

        return workflow

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error generating evidence collection workflow: {e}")
        raise HTTPException(
            status_code=500, detail="Failed to generate evidence collection workflow"
        )


@router.post("/generate-policy")
async def generate_customized_policy(
    framework: str = Query(..., description="Framework for policy generation"),
    policy_type: str = Query(..., description="Type of policy to generate"),
    tone: str = Query(default="Professional", description="Policy tone"),
    detail_level: str = Query(default="Standard", description="Level of detail"),
    include_templates: bool = Query(default=True, description="Include implementation templates"),
    geographic_scope: str = Query(default="Single location", description="Geographic scope"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    """
    Generate AI-powered, customized compliance policies based on:
    - Business profile and industry specifics
    - Framework requirements
    - Organizational size and maturity
    - Industry best practices
    - Regulatory requirements
    """
    try:
        business_profile = (
            db.query(BusinessProfile)
            .filter(BusinessProfile.user_id == str(str(current_user.id)))
            .first()
        )

        if not business_profile:
            raise HTTPException(status_code=400, detail="Business profile not found")

        customization_options = {
            "tone": tone,
            "detail_level": detail_level,
            "include_templates": include_templates,
            "geographic_scope": geographic_scope,
            "industry_focus": business_profile.industry,
        }

        assistant = ComplianceAssistant(db)
        policy = await assistant.generate_customized_policy(
            user=current_user,
            business_profile_id=business_profile.id,
            framework=framework,
            policy_type=policy_type,
            customization_options=customization_options,
        )

        return policy

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error generating customized policy: {e}")
        raise HTTPException(status_code=500, detail="Failed to generate customized policy")


@router.get("/smart-guidance/{framework}")
async def get_smart_compliance_guidance(
    framework: str,
    guidance_type: str = Query(default="getting_started", description="Type of guidance needed"),
    db: AsyncSession = Depends(get_async_db),
    current_user: User = Depends(get_current_active_user),
):
    """
    Get intelligent, context-aware compliance guidance based on:
    - Current compliance status
    - Business maturity level
    - Industry requirements
    - Best practices
    """
    try:
        # Use async query for business profile
        stmt = select(BusinessProfile).where(BusinessProfile.user_id == str(str(current_user.id)))
        result = await db.execute(stmt)
        business_profile = result.scalars().first()

        if not business_profile:
            raise HTTPException(status_code=400, detail="Business profile not found")

        assistant = ComplianceAssistant(db)

        # Get comprehensive analysis
        recommendations = await assistant.get_context_aware_recommendations(
            user=current_user,
            business_profile_id=business_profile.id,
            framework=framework,
            context_type="guidance",
        )

        # Get gap analysis
        gap_analysis = await assistant.analyze_evidence_gap(
            business_profile_id=business_profile.id, framework=framework
        )

        # Combine into smart guidance
        guidance = {
            "framework": framework,
            "guidance_type": guidance_type,
            "current_status": {
                "completion_percentage": gap_analysis.get("completion_percentage", 0),
                "maturity_level": recommendations.get("business_context", {}).get(
                    "maturity_level", "Basic"
                ),
                "critical_gaps_count": len(gap_analysis.get("critical_gaps", [])),
            },
            "personalized_roadmap": recommendations.get("recommendations", [])[:5],
            "next_immediate_steps": recommendations.get("next_steps", []),
            "effort_estimation": recommendations.get("estimated_effort", {}),
            "quick_wins": [
                rec
                for rec in recommendations.get("recommendations", [])
                if rec.get("effort_hours", 4) <= 2
            ][:3],
            "automation_opportunities": [
                rec
                for rec in recommendations.get("recommendations", [])
                if rec.get("automation_possible", False)
            ][:3],
            "generated_at": datetime.utcnow().isoformat(),
        }

        return guidance

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting smart compliance guidance: {e}")
        raise HTTPException(status_code=500, detail="Failed to get smart compliance guidance")


# REMOVED: Duplicate endpoint
# REMOVED: Duplicate endpoint
# # @router.get("/cache/metrics")
# # async def get_ai_cache_metrics(current_user: User = Depends(get_current_active_user)):
# #     """
# #     Get AI response cache performance metrics including:
# #     - Cache hit rate and performance statistics
# #     - Cost savings estimates
# #     - Cache size and efficiency metrics
# #     """
# #     try:
# #         from services.ai.response_cache import get_ai_cache
# #
#

        ai_cache = await get_ai_cache()
        metrics = await ai_cache.get_cache_metrics()

        return {
            "cache_performance": metrics,
            "status": "active",
            "generated_at": datetime.utcnow().isoformat(),
        }

    except Exception as e:
        logger.error(f"Error getting cache metrics: {e}")
        raise HTTPException(status_code=500, detail="Failed to get cache metrics")


@router.delete("/cache/clear")
async def clear_ai_cache(
    pattern: str = Query(default="*", description="Cache pattern to clear"),
    current_user: User = Depends(get_current_active_user),
):
    """
    Clear AI response cache entries matching a pattern.
    Requires appropriate permissions for cache management.
    """
    try:
        from services.ai.response_cache import get_ai_cache

        ai_cache = await get_ai_cache()
        cleared_count = await ai_cache.clear_cache_pattern(pattern)

        return {
            "cleared_entries": cleared_count,
            "pattern": pattern,
            "cleared_at": datetime.utcnow().isoformat(),
        }

    except Exception as e:
        logger.error(f"Error clearing cache: {e}")
        raise HTTPException(status_code=500, detail="Failed to clear cache")


@router.get("/performance/metrics")
async def get_ai_performance_metrics(current_user: User = Depends(get_current_active_user)):
    """
    Get comprehensive AI performance metrics including:
    - Response time statistics
    - Optimization effectiveness
    - Cost analysis and savings
    - System health indicators
    """
    try:
        from services.ai.performance_optimizer import get_performance_optimizer
        from services.ai.response_cache import get_ai_cache

        # Get performance metrics
        optimizer = await get_performance_optimizer()
        performance_metrics = await optimizer.get_performance_metrics()

        # Get cache metrics
        ai_cache = await get_ai_cache()
        cache_metrics = await ai_cache.get_cache_metrics()

        return {
            "performance_metrics": performance_metrics,
            "cache_metrics": cache_metrics,
            "system_status": "optimal",
            "generated_at": datetime.utcnow().isoformat(),
        }

    except Exception as e:
        logger.error(f"Error getting performance metrics: {e}")
        raise HTTPException(status_code=500, detail="Failed to get performance metrics")


@router.post("/performance/optimize")
async def optimize_ai_performance(
    enable_batching: bool = Query(default=True, description="Enable request batching"),
    enable_compression: bool = Query(default=True, description="Enable prompt compression"),
    max_concurrent: int = Query(default=10, description="Maximum concurrent requests"),
    current_user: User = Depends(get_current_active_user),
):
    """
    Configure AI performance optimization settings.
    Allows fine-tuning of performance parameters for optimal system operation.
    """
    try:
        from services.ai.performance_optimizer import get_performance_optimizer

        optimizer = await get_performance_optimizer()

        # Update optimization settings
        optimizer.enable_batching = enable_batching
        optimizer.enable_compression = enable_compression
        optimizer.max_concurrent_requests = max_concurrent

        # Update semaphore if concurrent limit changed
        if max_concurrent != optimizer.request_semaphore._value:
            optimizer.request_semaphore = asyncio.Semaphore(max_concurrent)

        return {
            "optimization_settings": {
                "batching_enabled": enable_batching,
                "compression_enabled": enable_compression,
                "max_concurrent_requests": max_concurrent,
            },
            "status": "updated",
            "updated_at": datetime.utcnow().isoformat(),
        }

    except Exception as e:
        logger.error(f"Error updating performance settings: {e}")
        raise HTTPException(status_code=500, detail="Failed to update performance settings")


@router.get("/analytics/dashboard")
async def get_analytics_dashboard(current_user: User = Depends(get_current_active_user)):
    """
    Get comprehensive analytics dashboard data including:
    - Real-time performance metrics
    - Usage analytics and trends
    - Cost analysis and optimization insights
    - Quality metrics and feedback
    - System alerts and health status
    """
    try:
        from services.ai.analytics_monitor import get_analytics_monitor

        monitor = await get_analytics_monitor()
        dashboard_data = await monitor.get_dashboard_data()

        return dashboard_data

    except Exception as e:
        logger.error(f"Error getting analytics dashboard: {e}")
        raise HTTPException(status_code=500, detail="Failed to get analytics dashboard")


@router.get("/analytics/usage")
async def get_usage_analytics(
    days: int = Query(default=7, description="Number of days to analyze"),
    current_user: User = Depends(get_current_active_user),
):
    """
    Get detailed usage analytics including:
    - Framework usage patterns
    - Content type distribution
    - User activity trends
    - Daily usage patterns
    """
    try:
        from services.ai.analytics_monitor import get_analytics_monitor

        monitor = await get_analytics_monitor()
        usage_data = await monitor.get_usage_analytics(days)

        return usage_data

    except Exception as e:
        logger.error(f"Error getting usage analytics: {e}")
        raise HTTPException(status_code=500, detail="Failed to get usage analytics")


@router.get("/analytics/cost")
async def get_cost_analytics(
    days: int = Query(default=30, description="Number of days to analyze"),
    current_user: User = Depends(get_current_active_user),
):
    """
    Get comprehensive cost analytics including:
    - Total cost breakdown
    - Cost trends and patterns
    - Optimization opportunities
    - ROI analysis
    """
    try:
        from services.ai.analytics_monitor import get_analytics_monitor

        monitor = await get_analytics_monitor()
        cost_data = await monitor.get_cost_analytics(days)

        return cost_data

    except Exception as e:
        logger.error(f"Error getting cost analytics: {e}")
        raise HTTPException(status_code=500, detail="Failed to get cost analytics")


@router.get("/analytics/alerts")
async def get_system_alerts(
    resolved: Optional[bool] = Query(default=None, description="Filter by resolution status"),
    current_user: User = Depends(get_current_active_user),
):
    """
    Get system alerts and notifications.
    Optionally filter by resolution status.
    """
    try:
        from services.ai.analytics_monitor import get_analytics_monitor

        monitor = await get_analytics_monitor()
        alerts = await monitor.get_alerts(resolved)

        return {
            "alerts": alerts,
            "total_count": len(alerts),
            "filter_applied": {"resolved": resolved} if resolved is not None else None,
        }

    except Exception as e:
        logger.error(f"Error getting system alerts: {e}")
        raise HTTPException(status_code=500, detail="Failed to get system alerts")


@router.post("/analytics/alerts/{alert_id}/resolve")
async def resolve_system_alert(alert_id: str, current_user: User = Depends(get_current_active_user)):
    """
    Mark a system alert as resolved.
    """
    try:
        from services.ai.analytics_monitor import get_analytics_monitor

        monitor = await get_analytics_monitor()
        success = await monitor.resolve_alert(alert_id)

        if success:
            return {
                "alert_id": alert_id,
                "status": "resolved",
                "resolved_at": datetime.utcnow().isoformat(),
            }
        else:
            raise HTTPException(status_code=404, detail="Alert not found")

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error resolving alert: {e}")
        raise HTTPException(status_code=500, detail="Failed to resolve alert")


@router.post("/smart-evidence/create-plan")
async def create_smart_evidence_plan(
    framework: str = Query(..., description="Compliance framework"),
    target_weeks: int = Query(default=12, description="Target completion weeks"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    """
    Create an intelligent evidence collection plan with AI-driven prioritization.

    Features:
    - AI-powered task prioritization
    - Automation opportunity identification
    - Intelligent scheduling and resource allocation
    - Business context-aware planning
    """
    try:
        business_profile = (
            db.query(BusinessProfile)
            .filter(BusinessProfile.user_id == str(str(current_user.id)))
            .first()
        )

        if not business_profile:
            raise HTTPException(status_code=400, detail="Business profile not found")

        from services.ai.smart_evidence_collector import get_smart_evidence_collector

        # Get business context
        business_context = {
            "company_name": business_profile.company_name,
            "industry": business_profile.industry,
            "employee_count": business_profile.employee_count or 0,
            "description": business_profile.description,
        }

        # Get existing evidence (simplified - would integrate with actual evidence database)
        existing_evidence = []  # This would query the actual evidence database

        collector = await get_smart_evidence_collector()
        plan = await collector.create_collection_plan(
            business_profile_id=str(business_profile.id),
            framework=framework,
            business_context=business_context,
            existing_evidence=existing_evidence,
            target_completion_weeks=target_weeks,
        )

        return {
            "plan_id": plan.plan_id,
            "framework": plan.framework,
            "total_tasks": plan.total_tasks,
            "estimated_total_hours": plan.estimated_total_hours,
            "completion_target_date": plan.completion_target_date.isoformat(),
            "automation_opportunities": plan.automation_opportunities,
            "next_priority_tasks": [
                {
                    "task_id": task.task_id,
                    "title": task.title,
                    "priority": task.priority.value,
                    "automation_level": task.automation_level.value,
                    "estimated_effort_hours": task.estimated_effort_hours,
                    "due_date": task.due_date.isoformat() if task.due_date else None,
                }
                for task in plan.tasks[:5]  # First 5 tasks
            ],
            "created_at": plan.created_at.isoformat(),
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error creating smart evidence plan: {e}")
        raise HTTPException(status_code=500, detail="Failed to create smart evidence plan")


@router.get("/smart-evidence/plan/{plan_id}")
async def get_smart_evidence_plan(plan_id: str, current_user: User = Depends(get_current_active_user)):
    """
    Get details of a smart evidence collection plan.
    """
    try:
        from services.ai.smart_evidence_collector import get_smart_evidence_collector

        collector = await get_smart_evidence_collector()
        plan = await collector.get_collection_plan(plan_id)

        if not plan:
            raise HTTPException(status_code=404, detail="Collection plan not found")

        return {
            "plan_id": plan.plan_id,
            "framework": plan.framework,
            "total_tasks": plan.total_tasks,
            "estimated_total_hours": plan.estimated_total_hours,
            "completion_target_date": plan.completion_target_date.isoformat(),
            "tasks": [
                {
                    "task_id": task.task_id,
                    "control_id": task.control_id,
                    "title": task.title,
                    "description": task.description,
                    "priority": task.priority.value,
                    "automation_level": task.automation_level.value,
                    "estimated_effort_hours": task.estimated_effort_hours,
                    "status": task.status.value,
                    "due_date": task.due_date.isoformat() if task.due_date else None,
                    "automation_tools": task.metadata.get("automation_tools", []),
                }
                for task in plan.tasks
            ],
            "automation_opportunities": plan.automation_opportunities,
            "created_at": plan.created_at.isoformat(),
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting smart evidence plan: {e}")
        raise HTTPException(status_code=500, detail="Failed to get smart evidence plan")


@router.get("/smart-evidence/next-tasks/{plan_id}")
async def get_next_priority_tasks(
    plan_id: str,
    limit: int = Query(default=5, description="Number of tasks to return"),
    current_user: User = Depends(get_current_active_user),
):
    """
    Get the next priority tasks for execution from a collection plan.
    """
    try:
        from services.ai.smart_evidence_collector import get_smart_evidence_collector

        collector = await get_smart_evidence_collector()
        tasks = await collector.get_next_priority_tasks(plan_id, limit)

        return {
            "plan_id": plan_id,
            "next_tasks": [
                {
                    "task_id": task.task_id,
                    "control_id": task.control_id,
                    "title": task.title,
                    "description": task.description,
                    "priority": task.priority.value,
                    "automation_level": task.automation_level.value,
                    "estimated_effort_hours": task.estimated_effort_hours,
                    "due_date": task.due_date.isoformat() if task.due_date else None,
                    "automation_tools": task.metadata.get("automation_tools", []),
                    "success_rate": task.metadata.get("success_rate", 0.5),
                }
                for task in tasks
            ],
            "total_pending_tasks": len(tasks),
        }

    except Exception as e:
        logger.error(f"Error getting next priority tasks: {e}")
        raise HTTPException(status_code=500, detail="Failed to get next priority tasks")


@router.post("/smart-evidence/update-task/{plan_id}/{task_id}")
async def update_evidence_task_status(
    plan_id: str,
    task_id: str,
    status: str = Query(..., description="New task status"),
    completion_notes: Optional[str] = Query(None, description="Completion notes"),
    current_user: User = Depends(get_current_active_user),
):
    """
    Update the status of an evidence collection task.
    """
    try:
        from services.ai.smart_evidence_collector import (
            CollectionStatus,
            get_smart_evidence_collector,
        )

        # Validate status
        try:
            task_status = CollectionStatus(status)
        except ValueError:
            raise HTTPException(status_code=400, detail=f"Invalid status: {status}")

        collector = await get_smart_evidence_collector()
        success = await collector.update_task_status(
            plan_id, task_id, task_status, completion_notes
        )

        if not success:
            raise HTTPException(status_code=404, detail="Plan or task not found")

        return {
            "plan_id": plan_id,
            "task_id": task_id,
            "status": status,
            "completion_notes": completion_notes,
            "updated_at": datetime.utcnow().isoformat(),
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error updating task status: {e}")
        raise HTTPException(status_code=500, detail="Failed to update task status")


# REMOVED: Duplicate endpoint
# REMOVED: Duplicate endpoint
# # @router.get("/quality/trends")
# # async def get_quality_trends(
# #     days: int = Query(default=30, description="Number of days to analyze"),
# #     current_user: User = Depends(get_current_active_user),
# # ):
# #     """
# #     Get AI response quality trends and analytics.
# #
#

    Provides insights into:
    - Overall quality score trends
    - Quality distribution across responses
    - Improvement areas and recommendations
    - Performance benchmarks
    """
    try:
        from services.ai.quality_monitor import get_quality_monitor

        monitor = await get_quality_monitor()
        trends = await monitor.get_quality_trends(days)

        return trends

    except Exception as e:
        logger.error(f"Error getting quality trends: {e}")
        raise HTTPException(status_code=500, detail="Failed to get quality trends")


@router.post("/quality/feedback")
async def submit_quality_feedback(
    response_id: str = Query(..., description="Response ID to provide feedback for"),
    feedback_type: str = Query(..., description="Type of feedback"),
    rating: Optional[float] = Query(None, description="Rating (1-5 scale)"),
    text_feedback: Optional[str] = Query(None, description="Text feedback"),
    current_user: User = Depends(get_current_active_user),
):
    """
    Submit user feedback for AI response quality improvement.

    Feedback types:
    - thumbs_up: Positive feedback
    - thumbs_down: Negative feedback
    - detailed_rating: Numerical rating with optional text
    - text_feedback: Detailed text feedback
    - improvement_suggestion: Specific improvement suggestions
    """
    try:
        from services.ai.quality_monitor import FeedbackType, ResponseFeedback, get_quality_monitor

        # Validate feedback type
        try:
            feedback_type_enum = FeedbackType(feedback_type)
        except ValueError:
            raise HTTPException(status_code=400, detail=f"Invalid feedback type: {feedback_type}")

        # Validate rating if provided
        if rating is not None and not (1.0 <= rating <= 5.0):
            raise HTTPException(status_code=400, detail="Rating must be between 1.0 and 5.0")

        # Create feedback object
        feedback = ResponseFeedback(
            feedback_id=f"fb_{response_id}_{int(datetime.utcnow().timestamp())}",
            response_id=response_id,
            user_id=str(str(current_user.id)),
            feedback_type=feedback_type_enum,
            rating=rating,
            text_feedback=text_feedback,
            metadata={"user_email": current_user.get("primaryEmail", current_user.get("email", "")), "submitted_via": "api"},
        )

        monitor = await get_quality_monitor()
        await monitor.record_user_feedback(feedback)

        return {
            "feedback_id": feedback.feedback_id,
            "response_id": response_id,
            "feedback_type": feedback_type,
            "status": "recorded",
            "submitted_at": feedback.timestamp.isoformat(),
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error submitting quality feedback: {e}")
        raise HTTPException(status_code=500, detail="Failed to submit quality feedback")


@router.get("/quality/assessment/{response_id}")
async def get_quality_assessment(response_id: str, current_user: User = Depends(get_current_active_user)):
    """
    Get detailed quality assessment for a specific AI response.
    """
    try:
        from services.ai.quality_monitor import get_quality_monitor

        monitor = await get_quality_monitor()

        if response_id not in monitor.quality_assessments:
            raise HTTPException(status_code=404, detail="Quality assessment not found")

        assessment = monitor.quality_assessments[response_id]

        return {
            "assessment_id": assessment.assessment_id,
            "response_id": assessment.response_id,
            "overall_score": assessment.overall_score,
            "quality_level": assessment.quality_level.value,
            "dimension_scores": {
                dimension.value: {
                    "score": score.score,
                    "confidence": score.confidence,
                    "explanation": score.explanation,
                    "automated": score.automated,
                }
                for dimension, score in assessment.dimension_scores.items()
            },
            "feedback_count": assessment.feedback_count,
            "improvement_suggestions": assessment.improvement_suggestions,
            "timestamp": assessment.timestamp.isoformat(),
            "metadata": assessment.metadata,
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting quality assessment: {e}")
        raise HTTPException(status_code=500, detail="Failed to get quality assessment")


@router.get("/quality/metrics")
async def get_quality_metrics(current_user: User = Depends(get_current_active_user)):
    """
    Get comprehensive quality metrics and performance indicators.
    """
    try:
        from services.ai.quality_monitor import get_quality_monitor

        monitor = await get_quality_monitor()

        return {
            "overall_metrics": monitor.metrics,
            "quality_thresholds": {
                level.value: threshold for level, threshold in monitor.quality_thresholds.items()
            },
            "total_assessments": len(monitor.quality_assessments),
            "total_feedback_items": len(monitor.feedback_history),
            "recent_trends": await monitor.get_quality_trends(7),  # Last 7 days
            "generated_at": datetime.utcnow().isoformat(),
        }

    except Exception as e:
        logger.error(f"Error getting quality metrics: {e}")
        raise HTTPException(status_code=500, detail="Failed to get quality metrics")
