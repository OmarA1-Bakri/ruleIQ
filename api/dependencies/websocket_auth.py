"""
Enhanced WebSocket authentication using headers instead of query parameters.

This module provides secure WebSocket authentication that extracts JWT tokens
from headers, following security best practices.
import logging

logger = logging.getLogger(__name__)
"""

from typing import Optional
from uuid import UUID
import json
from fastapi import WebSocket, status
from jose import JWTError, ExpiredSignatureError
from sqlalchemy.future import select
from database.db_setup import get_async_db
from database.user import User
from config.logging_config import get_logger
from .auth import decode_token, is_token_blacklisted

logger = get_logger(__name__)


async def extract_token_from_headers(websocket: WebSocket) -> Optional[str]:
    """
    Extract JWT token from WebSocket headers.

    Looks for token in multiple header locations for compatibility:
    1. Authorization header (Bearer token)
    2. X-Auth-Token header
    3. Sec-WebSocket-Protocol header (for browser compatibility)

    Args:
        websocket: The WebSocket connection

    Returns:
        Optional[str]: The extracted token or None
    """
    headers = dict(websocket.headers)

    # Check Authorization header (preferred)
    auth_header = headers.get("authorization", "")
    if auth_header.startswith("Bearer "):
        return auth_header.replace("Bearer ", "", 1)

    # Check X-Auth-Token header
    if "x-auth-token" in headers:
        return headers["x-auth-token"]

    # Check Sec-WebSocket-Protocol for token (browser compatibility)
    # Some browsers allow passing auth info via subprotocol
    protocol = headers.get("sec-websocket-protocol", "")
    if protocol.startswith("token."):
        return protocol.replace("token.", "", 1)

    return None


async def verify_websocket_token_from_headers(
    websocket: WebSocket, accept_connection: bool = False
) -> Optional[User]:
    """
    Verify JWT token from WebSocket headers.

    This is a secure alternative to passing tokens in query parameters.

    Args:
        websocket: The WebSocket connection
        accept_connection: Whether to accept the connection before validation

    Returns:
        Optional[User]: The authenticated user or None if authentication fails

    Raises:
        WebSocketException: If authentication fails
    """
    try:
        # Extract token from headers
        token = await extract_token_from_headers(websocket)

        if not token:
            logger.warning("No authentication token found in WebSocket headers")
            if accept_connection and websocket.client_state.value == 0:
                await websocket.accept()
            await websocket.close(
                code=status.WS_1008_POLICY_VIOLATION, reason="Authentication required"
            )
            return None

        # Decode and verify the token
        try:
            payload = decode_token(token)
        except (JWTError, ExpiredSignatureError) as e:
            logger.warning(f"Invalid token in WebSocket connection: {e}")
            if accept_connection and websocket.client_state.value == 0:
                await websocket.accept()
            await websocket.close(
                code=status.WS_1008_POLICY_VIOLATION, reason="Invalid authentication token"
            )
            return None

        user_id = payload.get("sub")
        if not user_id:
            logger.warning("Token missing user ID")
            if accept_connection and websocket.client_state.value == 0:
                await websocket.accept()
            await websocket.close(
                code=status.WS_1008_POLICY_VIOLATION, reason="Invalid token payload"
            )
            return None

        # Check if token is blacklisted
        if await is_token_blacklisted(token):
            logger.warning(f"Blacklisted token used for WebSocket: user_id={user_id}")
            if accept_connection and websocket.client_state.value == 0:
                await websocket.accept()
            await websocket.close(
                code=status.WS_1008_POLICY_VIOLATION, reason="Token has been revoked"
            )
            return None

        # Get user from database
        async for session in get_async_db():
            result = await session.execute(select(User).where(User.id == UUID(user_id)))
            user = result.scalars().first()
            break

        if not user:
            logger.warning(f"User not found for WebSocket: user_id={user_id}")
            if accept_connection and websocket.client_state.value == 0:
                await websocket.accept()
            await websocket.close(code=status.WS_1008_POLICY_VIOLATION, reason="User not found")
            return None

        if not user.is_active:
            logger.warning(f"Inactive user attempted WebSocket connection: user_id={user_id}")
            if accept_connection and websocket.client_state.value == 0:
                await websocket.accept()
            await websocket.close(
                code=status.WS_1008_POLICY_VIOLATION, reason="Account is inactive"
            )
            return None

        logger.info(f"WebSocket authenticated successfully: user_id={user_id}")
        return user

    except Exception as e:
        logger.error(f"WebSocket authentication error: {e}")
        if accept_connection and websocket.client_state.value == 0:
            await websocket.accept()
        await websocket.close(code=status.WS_1011_INTERNAL_ERROR, reason="Authentication error")
        return None


async def send_auth_required_message(websocket: WebSocket) -> None:
    """
    Send authentication required message to WebSocket client.

    Args:
        websocket: The WebSocket connection
    """
    if websocket.client_state.value == 0:
        await websocket.accept()

    auth_message = {
        "type": "auth_required",
        "message": "Authentication required. Please provide JWT token in headers.",
        "headers_accepted": [
            "Authorization: Bearer <token>",
            "X-Auth-Token: <token>",
            "Sec-WebSocket-Protocol: token.<token>",
        ],
    }

    await websocket.send_text(json.dumps(auth_message))
    await websocket.close(code=status.WS_1008_POLICY_VIOLATION, reason="Authentication required")


class WebSocketAuthMiddleware:
    """
    Middleware for WebSocket authentication using headers.
    """

    def __init__(self, require_auth: bool = True) -> None:
        """
        Initialize the middleware.

        Args:
            require_auth: Whether authentication is required
        """
        self.require_auth = require_auth

    async def __call__(
        self, websocket: WebSocket, accept_connection: bool = False
    ) -> Optional[User]:
        """
        Authenticate WebSocket connection.

        Args:
            websocket: The WebSocket connection
            accept_connection: Whether to accept before validation

        Returns:
            Optional[User]: Authenticated user or None
        """
        if not self.require_auth:
            return None

        user = await verify_websocket_token_from_headers(
            websocket, accept_connection=accept_connection
        )

        if not user:
            logger.warning("WebSocket authentication failed")
            return None

        return user


# Backward compatibility function for gradual migration
async def verify_websocket_token_with_fallback(
    websocket: WebSocket, token_from_query: Optional[str] = None
) -> Optional[User]:
    """
    Verify WebSocket token with fallback to query parameter.

    This function first tries to get token from headers, then falls back
    to query parameter for backward compatibility during migration.

    Args:
        websocket: The WebSocket connection
        token_from_query: Optional token from query parameter (deprecated)

    Returns:
        Optional[User]: Authenticated user or None
    """
    # First try to get token from headers
    user = await verify_websocket_token_from_headers(websocket)

    if user:
        return user

    # Fallback to query parameter with deprecation warning
    if token_from_query:
        logger.warning(
            "DEPRECATED: JWT token passed in query parameter. "
            "Please update client to send token in headers."
        )

        try:
            from .auth import verify_websocket_token

            # Use the old function for backward compatibility
            user = await verify_websocket_token(websocket, token_from_query)
            return user
        except Exception as e:
            logger.error(f"Fallback authentication failed: {e}")

    return None
