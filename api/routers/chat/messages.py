"""
Message sending and management endpoints.
"""

import logging
from datetime import datetime, timezone
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from api.dependencies.auth import get_current_active_user
from api.dependencies.security_validation import validate_request
from api.utils.security_validation import SecurityValidator
from database.user import User
from api.schemas.chat import MessageResponse, SendMessageRequest
from database.business_profile import BusinessProfile
from database.chat_conversation import ChatConversation, ConversationStatus
from database.chat_message import ChatMessage
from database.db_setup import get_async_db
from services.ai import ComplianceAssistant

logger = logging.getLogger(__name__)

router = APIRouter()


@router.post("/conversations/{conversation_id}/messages", response_model=MessageResponse, dependencies=[Depends(validate_request)])
async def send_message(
    conversation_id: UUID,
    request: SendMessageRequest,
    db: AsyncSession = Depends(get_async_db),
    current_user: User = Depends(get_current_active_user),
):
    """Send a message in a conversation."""
    try:
        from sqlalchemy import desc, select

        # Sanitize message content
        request.message = SecurityValidator.validate_no_dangerous_content(request.message, "message")

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
        bp_stmt = select(BusinessProfile).where(
            BusinessProfile.user_id == str(str(current_user.id)),
        )
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
        conversation.updated_at = datetime.now(timezone.utc)

        await db.commit()

        return MessageResponse.from_orm(assistant_message)

    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        logger.error(f"Error sending message: {e}")
        raise HTTPException(status_code=500, detail="Failed to send message")
