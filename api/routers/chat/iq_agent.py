"""
IQ Agent (GraphRAG) integration endpoints.
"""

import logging
from datetime import datetime, timezone
from typing import Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from api.dependencies.auth import get_current_active_user
from api.dependencies.security_validation import validate_request
from database.user import User
from api.schemas.chat import MessageResponse, SendMessageRequest
from database.chat_conversation import ChatConversation
from database.chat_message import ChatMessage
from database.db_setup import get_async_db
from services.ai import ComplianceAssistant
from services.iq_agent import IQComplianceAgent
from services.neo4j_service import Neo4jGraphRAGService

logger = logging.getLogger(__name__)

router = APIRouter()

# Global IQ agent instance (shared across requests)
_iq_agent: Optional[IQComplianceAgent] = None
_neo4j_service: Optional[Neo4jGraphRAGService] = None


async def get_iq_agent_for_chat(db: AsyncSession) -> IQComplianceAgent:
    """Get or create IQ agent instance for chat"""
    global _iq_agent, _neo4j_service

    if _iq_agent is None:
        try:
            # Initialize Neo4j service
            _neo4j_service = Neo4jGraphRAGService()
            await _neo4j_service.connect()

            # Create IQ agent with PostgreSQL session
            _iq_agent = IQComplianceAgent(neo4j_service=_neo4j_service, postgres_session=db)
            logger.info("IQ Agent initialized successfully for chat")

        except Exception as e:
            logger.error(f"Failed to initialize IQ Agent: {str(e)}")
            # Fallback to regular assistant if IQ Agent fails
            return None

    return _iq_agent


@router.post(
    "/iq-chat/{conversation_id}/messages",
    response_model=MessageResponse,
    dependencies=[Depends(validate_request)],
)
async def send_iq_message(
    conversation_id: UUID,
    request: SendMessageRequest,
    db: AsyncSession = Depends(get_async_db),
    current_user: User = Depends(get_current_active_user),
):
    """Send a message using IQ Agent with GraphRAG intelligence"""
    try:
        # Get conversation
        result = await db.execute(
            select(ChatConversation).where(
                ChatConversation.id == conversation_id,
                ChatConversation.user_id == str(current_user.id),
            ),
        )
        conversation = result.scalars().first()

        if not conversation:
            raise HTTPException(status_code=404, detail="Conversation not found")

        # Get next sequence number
        seq_result = await db.execute(
            select(func.max(ChatMessage.sequence_number)).where(
                ChatMessage.conversation_id == conversation_id,
            ),
        )
        max_seq = seq_result.scalar() or 0

        # Add user message
        user_message = ChatMessage(
            conversation_id=conversation_id,
            role="user",
            content=request.message,
            sequence_number=max_seq + 1,
        )
        db.add(user_message)
        await db.flush()

        # Try to get IQ Agent
        iq_agent = await get_iq_agent_for_chat(db)

        if iq_agent:
            try:
                # Process with IQ Agent's GraphRAG capabilities
                logger.info(f"Processing message with IQ Agent for conversation {conversation_id}")

                # Build context from business profile
                business_context = await iq_agent.retrieve_business_context(str(current_user.id))

                # Process query through IQ Agent
                result = await iq_agent.process_query(
                    user_query=request.message,
                    context={
                        "user_id": str(current_user.id),
                        "conversation_id": str(conversation_id),
                        "business_context": business_context,
                    },
                )

                # Extract response text
                response_text = result.get("llm_response", "")

                # Add metadata from IQ processing
                metadata = {
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                    "iq_agent": True,
                    "graph_nodes_traversed": result.get("graph_context", {}).get(
                        "nodes_traversed",
                        0,
                    ),
                    "graph_relationships": result.get("graph_context", {}).get(
                        "relationships_explored",
                        0,
                    ),
                    "evidence_found": len(result.get("evidence", [])),
                    "artifacts_generated": len(result.get("artifacts", [])),
                    "processing_time_ms": result.get("processing_time_ms", 0),
                }

                # Add next actions as part of response if available
                if result.get("next_actions"):
                    response_text += "\n\n**Recommended Next Steps:**\n"
                    for action in result["next_actions"]:
                        response_text += f"• {action}\n"

            except Exception as iq_error:
                logger.warning(
                    f"IQ Agent processing failed, falling back to regular assistant: {iq_error}",
                )
                # Fallback to regular assistant
                assistant = ComplianceAssistant(db)

                # Handle case where conversation has no business profile
                if conversation.business_profile_id:
                    response_text, metadata = await assistant.process_message(
                        conversation_id=conversation_id,
                        user=current_user,
                        message=request.message,
                        business_profile_id=conversation.business_profile_id,
                    )
                else:
                    # Create a generic response without business profile context
                    response_text = (
                        "I can help you with compliance and regulatory questions. "
                        "For more personalized assistance, please set up a business profile "
                        "for this conversation."
                    )
                    metadata = {
                        "timestamp": datetime.now(timezone.utc).isoformat(),
                        "no_business_profile": True,
                    }
                metadata["iq_agent_fallback"] = True
        else:
            # Use regular assistant if IQ Agent not available
            assistant = ComplianceAssistant(db)

            # Handle case where conversation has no business profile
            if conversation.business_profile_id:
                response_text, metadata = await assistant.process_message(
                    conversation_id=conversation_id,
                    user=current_user,
                    message=request.message,
                    business_profile_id=conversation.business_profile_id,
                )
            else:
                # Create a generic response without business profile context
                response_text = (
                    "I can help you with compliance and regulatory questions. "
                    "For more personalized assistance, please set up a business profile "
                    "for this conversation."
                )
                metadata = {
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                    "no_business_profile": True,
                }
            metadata["iq_agent"] = False

        # Add assistant message
        assistant_message = ChatMessage(
            conversation_id=conversation_id,
            role="assistant",
            content=response_text,
            message_metadata=metadata,
            sequence_number=max_seq + 2,
        )
        db.add(assistant_message)

        # Update conversation timestamp
        conversation.updated_at = datetime.now(timezone.utc)

        await db.commit()

        return MessageResponse.from_orm(assistant_message)

    except HTTPException:
        raise
    except Exception as e:
        await db.rollback()
        logger.error(f"Error sending IQ message: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Failed to send message")


@router.get("/iq-agent/status", dependencies=[Depends(validate_request)])
async def get_iq_agent_status(
    current_user: User = Depends(get_current_active_user),
):
    """Check IQ Agent availability and status"""
    global _iq_agent, _neo4j_service

    status = {
        "iq_agent_available": _iq_agent is not None,
        "neo4j_connected": False,
        "graph_initialized": False,
        "nodes_count": 0,
        "relationships_count": 0,
        "message": "IQ Agent not initialized",
    }

    if _neo4j_service:
        try:
            # Check Neo4j connection
            stats = await _neo4j_service.get_graph_statistics()
            status.update(
                {
                    "neo4j_connected": True,
                    "graph_initialized": stats.get("nodes", 0) > 0,
                    "nodes_count": stats.get("nodes", 0),
                    "relationships_count": stats.get("relationships", 0),
                    "message": (
                        "IQ Agent operational" if _iq_agent else "IQ Agent not initialized"
                    ),
                }
            )
        except Exception as e:
            status["message"] = f"Neo4j connection error: {str(e)}"

    return status
