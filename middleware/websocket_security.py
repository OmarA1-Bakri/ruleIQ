"""
WebSocket Security Middleware for RuleIQ API

Implements rate limiting, origin validation, and JWT authentication for WebSocket connections.
"""

import time
from typing import Dict, Optional, Set
from datetime import datetime, timedelta
from collections import defaultdict
import logging

from fastapi import WebSocket, status
from config.settings import settings
from config.logging_config import get_logger


logger = logging.getLogger(__name__)
logger = get_logger(__name__)


class WebSocketRateLimiter:
    """Rate limiter for WebSocket connections."""

    def __init__(self, max_connections_per_ip: int = 10, max_messages_per_minute: int = 60) -> None:
        self.max_connections_per_ip = max_connections_per_ip
        self.max_messages_per_minute = max_messages_per_minute
        self.connections_by_ip: Dict[str, Set[str]] = defaultdict(set)
        self.message_counts: Dict[str, list] = defaultdict(list)
        self.blocked_ips: Dict[str, datetime] = {}

    def check_connection_limit(self, client_ip: str, connection_id: str) -> bool:
        """Check if IP has reached connection limit."""
        # Check if IP is temporarily blocked
        if client_ip in self.blocked_ips:
            if datetime.now() < self.blocked_ips[client_ip]:
                logger.warning(f"Blocked IP {client_ip} attempted WebSocket connection")
                return False
            else:
                del self.blocked_ips[client_ip]

        # Check connection limit
        if len(self.connections_by_ip[client_ip]) >= self.max_connections_per_ip:
            logger.warning(f"IP {client_ip} exceeded max WebSocket connections")
            # Block IP for 5 minutes
            self.blocked_ips[client_ip] = datetime.now() + timedelta(minutes=5)
            return False

        self.connections_by_ip[client_ip].add(connection_id)
        return True

    def check_message_rate(self, client_ip: str) -> bool:
        """Check if IP has exceeded message rate limit."""
        now = time.time()
        minute_ago = now - 60

        # Clean old timestamps
        self.message_counts[client_ip] = [
            ts for ts in self.message_counts[client_ip] if ts > minute_ago
        ]

        # Check rate limit
        if len(self.message_counts[client_ip]) >= self.max_messages_per_minute:
            logger.warning(f"IP {client_ip} exceeded WebSocket message rate limit")
            return False

        self.message_counts[client_ip].append(now)
        return True

    def remove_connection(self, client_ip: str, connection_id: str):
        """Remove connection from tracking."""
        if client_ip in self.connections_by_ip:
            self.connections_by_ip[client_ip].discard(connection_id)
            if not self.connections_by_ip[client_ip]:
                del self.connections_by_ip[client_ip]


class WebSocketOriginValidator:
    """Validates WebSocket connection origins."""

    def __init__(self) -> None:
        # Get allowed origins from settings
        self.allowed_origins = self._get_allowed_origins()

    def _get_allowed_origins(self) -> Set[str]:
        """Get list of allowed origins based on environment."""
        allowed = set()

        if settings.is_production:
            # Production origins
            allowed.update(
                [
                    "https://ruleiq.com",
                    "https://www.ruleiq.com",
                    "https://app.ruleiq.com",
                    "https://api.ruleiq.com",
                ]
            )
        else:
            # Development origins
            allowed.update(
                [
                    "http://localhost:3000",
                    "http://localhost:3001",
                    "http://localhost:8000",
                    "http://127.0.0.1:3000",
                    "http://127.0.0.1:8000",
                ]
            )

        # Add any custom origins from environment
        custom_origins = settings.cors_origins
        if custom_origins:
            if isinstance(custom_origins, str):
                allowed.update(custom_origins.split(","))
            elif isinstance(custom_origins, list):
                allowed.update(custom_origins)

        return allowed

    def validate_origin(self, origin: Optional[str]) -> bool:
        """Validate WebSocket connection origin."""
        if not origin:
            # Reject connections without origin in production
            if settings.is_production:
                logger.warning("WebSocket connection rejected: no origin header")
                return False
            return True

        # Check if origin is allowed
        if origin not in self.allowed_origins:
            logger.warning(f"WebSocket connection rejected from origin: {origin}")
            return False

        return True


class WebSocketSecurityMiddleware:
    """
    Comprehensive WebSocket security middleware.

    Features:
    - Rate limiting per IP
    - Origin validation
    - JWT authentication (handled separately)
    - Connection tracking
    """

    def __init__(self) -> None:
        self.rate_limiter = WebSocketRateLimiter()
        self.origin_validator = WebSocketOriginValidator()

    async def validate_connection(self, websocket: WebSocket, connection_id: str) -> bool:
        """
        Validate WebSocket connection before accepting.

        Returns True if connection should be accepted, False otherwise.
        """
        # Get client IP
        client_ip = None
        if websocket.client:
            client_ip = websocket.client.host

        if not client_ip:
            logger.warning("WebSocket connection rejected: no client IP")
            return False

        # Check rate limit
        if not self.rate_limiter.check_connection_limit(client_ip, connection_id):
            await websocket.close(code=status.WS_1008_POLICY_VIOLATION)
            return False

        # Validate origin
        origin = websocket.headers.get("origin")
        if not self.origin_validator.validate_origin(origin):
            await websocket.close(code=status.WS_1008_POLICY_VIOLATION)
            return False

        logger.info(f"WebSocket connection validated: {connection_id} from {client_ip}")
        return True

    async def validate_message(self, websocket: WebSocket, connection_id: str) -> bool:
        """
        Validate incoming WebSocket message rate.

        Returns True if message should be processed, False otherwise.
        """
        client_ip = None
        if websocket.client:
            client_ip = websocket.client.host

        if not client_ip:
            return False

        # Check message rate
        if not self.rate_limiter.check_message_rate(client_ip):
            # Send rate limit warning
            await websocket.send_json(
                {
                    "type": "error",
                    "message": "Rate limit exceeded. Please slow down.",
                    "code": "RATE_LIMIT_EXCEEDED",
                }
            )
            return False

        return True

    def cleanup_connection(self, websocket: WebSocket, connection_id: str):
        """Clean up after WebSocket disconnection."""
        if websocket.client:
            client_ip = websocket.client.host
            self.rate_limiter.remove_connection(client_ip, connection_id)


# Global instance
websocket_security = WebSocketSecurityMiddleware()
