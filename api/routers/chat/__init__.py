"""
Chat Assistant API Router

This module aggregates all chat-related endpoints into a unified router.
The original monolithic chat.py (1,606 lines) has been refactored into
focused domain modules:

- conversations.py (377 lines): Conversation CRUD operations
- messages.py (110 lines): Message sending and retrieval
- evidence.py (583 lines): Evidence recommendations and workflows
- analytics.py (244 lines): Analytics, metrics, and monitoring
- iq_agent.py (223 lines): IQ Agent (GraphRAG) integration
- placeholder_endpoints.py (103 lines): Temporary placeholder endpoints

Total: 1,640 lines (preserved all functionality)

Usage:
    from api.routers.chat import router
    app.include_router(router, prefix='/api/v1/chat', tags=['chat'])

This maintains backward compatibility with existing code.
"""

from fastapi import APIRouter

# Import individual routers
from .analytics import router as analytics_router
from .conversations import router as conversations_router
from .evidence import router as evidence_router
from .iq_agent import router as iq_agent_router
from .messages import router as messages_router
from .placeholder_endpoints import router as placeholder_router

# Create unified router
router = APIRouter(tags=["Chat Assistant"])

# Include all sub-routers
router.include_router(conversations_router)
router.include_router(messages_router)
router.include_router(evidence_router)
router.include_router(analytics_router)
router.include_router(iq_agent_router)
router.include_router(placeholder_router)

__all__ = ['router']
