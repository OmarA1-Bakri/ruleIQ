"""
Conversation management endpoints.
"""

import asyncio
import logging
from datetime import datetime, timezone
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import desc, select, func
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import Session

from api.dependencies.auth import get_current_active_user
from api.dependencies.security_validation import validate_request
from api.utils.security_validation import SecurityValidator
from database.user import User
from api.schemas.chat import (
    ConversationListResponse,
    ConversationResponse,
    ConversationSummary,
    CreateConversationRequest,
    MessageResponse,
)
from database.business_profile import BusinessProfile
from database.chat_conversation import ChatConversation, ConversationStatus
from database.chat_message import ChatMessage
from database.db_setup import get_async_db, get_db
from services.ai import ComplianceAssistant

logger = logging.getLogger(__name__)

router = APIRouter()


@router.post("/conversations", response_model=dict, dependencies=[Depends(validate_request)])
async def create_conversation(
    request: CreateConversationRequest,
    db: AsyncSession = Depends(get_async_db),
    current_user: User = Depends(get_current_active_user),
):
    """Create a new chat conversation with optimized database queries."""
    try:
        # Sanitize input fields
        if request.title:
            request.title = SecurityValidator.validate_no_dangerous_content(request.title, "title")
        if request.initial_message:
            request.initial_message = SecurityValidator.validate_no_dangerous_content(
                request.initial_message, "message"
            )

        # Optimized: Single query to get both business profile and conversation count
        user_id_str = str(current_user.id)

        # Use a single query with subquery for better performance
        profile_stmt = select(BusinessProfile).where(BusinessProfile.user_id == user_id_str)
        count_stmt = select(func.count(ChatConversation.id)).where(
            ChatConversation.user_id == user_id_str,
        )

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
                        ),
                    )

                    # Aggressive timeout for conversation creation
                    response_text, metadata = await asyncio.wait_for(response_task, timeout=12.0)

                except asyncio.TimeoutError:
                    logger.warning(f"AI processing timed out for conversation {conversation.id}")
                    # Use fallback response
                    response_text = (
                        "I understand you'd like to discuss compliance matters. Due to high "
                        "demand, I'm providing a quick response. "
                        "I'm here to help with compliance questions about GDPR, ISO 27001, and other frameworks. "
                        "Please feel free to ask specific questions about: "
                        "• Data protection requirements "
                        "• Security controls and policies "
                        "• Risk assessments "
                        "• Audit preparations "
                        "What specific compliance topic would you like to explore?"
                    )

                    metadata = {
                        "timestamp": datetime.now(timezone.utc).isoformat(),
                        "fallback_used": True,
                        "timeout_occurred": True,
                        "intent": "general",
                        "processing_time_ms": 12000,
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
                logger.error(
                    f"AI processing failed for conversation {conversation.id}: {ai_error}",
                    exc_info=True,
                )

                # Still add the user message but provide a fallback response
                user_message = ChatMessage(
                    conversation_id=conversation.id,
                    role="user",
                    content=request.initial_message,
                    sequence_number=1,
                )
                db.add(user_message)

                # Provide fallback assistant response
                fallback_response = (
                    "Thank you for your message. I'm currently experiencing high demand but "
                    "I'm here to help with your compliance questions. "
                    "Please feel free to ask about: "
                    "• GDPR and data protection "
                    "• ISO 27001 and security frameworks "
                    "• Risk assessments and audits "
                    "• Policy development "
                    "What specific compliance area can I assist you with?"
                )

                assistant_message = ChatMessage(
                    conversation_id=conversation.id,
                    role="assistant",
                    content=fallback_response,
                    message_metadata={
                        "timestamp": datetime.now(timezone.utc).isoformat(),
                        "fallback_used": True,
                        "ai_error": str(ai_error),
                        "intent": "fallback",
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


@router.get(
    "/conversations",
    response_model=ConversationListResponse,
    dependencies=[Depends(validate_request)],
)
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
            .count(),
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
            .all(),
        )

        # Get message counts and last message times
        conversation_summaries = []
        for conv in conversations:
            message_count = (
                db.query(ChatMessage).filter(ChatMessage.conversation_id == conv.id).count(),
            )

            last_message = (
                db.query(ChatMessage)
                .filter(ChatMessage.conversation_id == conv.id)
                .order_by(desc(ChatMessage.created_at))
                .first(),
            )

            conversation_summaries.append(
                ConversationSummary(
                    id=conv.id,
                    title=conv.title,
                    status=conv.status.value,
                    message_count=message_count,
                    last_message_at=last_message.created_at if last_message else None,
                    created_at=conv.created_at,
                ),
            )

        return ConversationListResponse(
            conversations=conversation_summaries,
            total=total,
            page=page,
            per_page=per_page,
        )

    except Exception as e:
        logger.error(f"Error listing conversations: {e}")
        raise HTTPException(status_code=500, detail="Failed to list conversations")


@router.get(
    "/conversations/{conversation_id}",
    response_model=ConversationResponse,
    dependencies=[Depends(validate_request)],
)
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
                ChatConversation.id == conversation_id,
                ChatConversation.user_id == str(current_user.id),
            )
            .first(),
        )

        if not conversation:
            raise HTTPException(status_code=404, detail="Conversation not found")

        messages = (
            db.query(ChatMessage)
            .filter(ChatMessage.conversation_id == conversation_id)
            .order_by(ChatMessage.sequence_number)
            .all(),
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


@router.delete("/conversations/{conversation_id}", dependencies=[Depends(validate_request)])
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
                ChatConversation["id"] == conversation_id,
                ChatConversation.user_id == str(current_user.id),
            )
            .first(),
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
