"""
from __future__ import annotations

# Constants
HOUR_SECONDS = 3600


AI-specific rate limiting middleware for ruleIQ API endpoints.

Implements tiered rate limiting for different AI operations:
- AI Help: 10 requests/minute per user
- AI Follow-up: 5 requests/minute per user
- AI Analysis: 3 requests/minute per user
- AI Recommendations: 3 requests/minute per user
"""
import asyncio
import time
from collections import defaultdict, deque
from typing import Dict, Tuple, Any
from fastapi import Depends, HTTPException, Request
from starlette import status
from api.dependencies.auth import get_current_active_user
from config.settings import get_settings
from database.user import User
settings = get_settings()


class AIRateLimiter:
    """Advanced rate limiter specifically designed for AI endpoints."""

    def __init__(self, requests_per_minute: int, burst_allowance: int=2
        ) ->None:
        self.requests_per_minute = requests_per_minute
        self.burst_allowance = burst_allowance
        self.window_size = 60
        self.user_requests: Dict[str, deque] = defaultdict(lambda : deque())
        self.burst_usage: Dict[str, int] = defaultdict(int)
        self.burst_reset_time: Dict[str, float] = defaultdict(float)
        self._lock = asyncio.Lock()

    async def check_rate_limit(self, user_id: str) ->Tuple[bool, int]:
        """
        Check if user is within rate limits.

        Returns:
            Tuple of (allowed: bool, retry_after_seconds: int)
        """
        async with self._lock:
            current_time = time.time()
            user_requests = self.user_requests[user_id]
            cutoff_time = current_time - self.window_size
            while user_requests and user_requests[0] < cutoff_time:
                user_requests.popleft()
            if current_time - self.burst_reset_time[user_id] > HOUR_SECONDS:
                self.burst_usage[user_id] = 0
                self.burst_reset_time[user_id] = current_time
            if len(user_requests) < self.requests_per_minute:
                user_requests.append(current_time)
                return True, 0
            if self.burst_usage[user_id] < self.burst_allowance:
                self.burst_usage[user_id] += 1
                user_requests.append(current_time)
                return True, 0
            oldest_request = user_requests[0]
            retry_after = int(oldest_request + self.window_size - current_time
                ) + 1
            return False, max(1, retry_after)

    async def record_request(self, user_id: str) ->None:
        """Record a successful request for the user."""
        pass

    def get_remaining_requests(self, user_id: str) ->int:
        """Get remaining requests for user in current window."""
        current_time = time.time()
        user_requests = self.user_requests[user_id]
        cutoff_time = current_time - self.window_size
        while user_requests and user_requests[0] < cutoff_time:
            user_requests.popleft()
        remaining = self.requests_per_minute - len(user_requests)
        return max(0, remaining)


ai_help_limiter = AIRateLimiter(requests_per_minute=10, burst_allowance=2)
ai_followup_limiter = AIRateLimiter(requests_per_minute=5, burst_allowance=1)
ai_analysis_limiter = AIRateLimiter(requests_per_minute=3, burst_allowance=1)
ai_recommendations_limiter = AIRateLimiter(requests_per_minute=3,
    burst_allowance=1)


def create_ai_rate_limit_dependency(limiter: AIRateLimiter, operation_name: str
    ) ->Any:
    """Create a FastAPI dependency for AI rate limiting."""

    async def ai_rate_limit_check(request: Request, current_user: User=
        Depends(get_current_active_user)) ->None:
        if settings.is_testing:
            return
        user_id = str(current_user.id)
        allowed, retry_after = await limiter.check_rate_limit(user_id)
        if not allowed:
            remaining = limiter.get_remaining_requests(user_id)
            error_detail = {'error': {'message':
                f'AI {operation_name} rate limit exceeded', 'code':
                'AI_RATE_LIMIT_EXCEEDED', 'operation': operation_name,
                'limit': limiter.requests_per_minute, 'window': '1 minute',
                'retry_after': retry_after, 'burst_allowance': limiter.
                burst_allowance}, 'suggestion':
                f'Please wait {retry_after} seconds before making another {operation_name} request.'
                }
            raise HTTPException(status_code=status.
                HTTP_429_TOO_MANY_REQUESTS, detail=error_detail, headers={
                'Retry-After': str(retry_after), 'X-RateLimit-Limit': str(
                limiter.requests_per_minute), 'X-RateLimit-Remaining': str(
                remaining), 'X-RateLimit-Reset': str(int(time.time()) +
                retry_after), 'X-RateLimit-Operation': operation_name})
        remaining = limiter.get_remaining_requests(user_id)
        request.state.rate_limit_headers = {'X-RateLimit-Limit': str(
            limiter.requests_per_minute), 'X-RateLimit-Remaining': str(
            remaining), 'X-RateLimit-Reset': str(int(time.time()) + 60),
            'X-RateLimit-Operation': operation_name}
    return ai_rate_limit_check


ai_help_rate_limit = create_ai_rate_limit_dependency(ai_help_limiter, 'help')
ai_followup_rate_limit = create_ai_rate_limit_dependency(ai_followup_limiter,
    'followup')
ai_analysis_rate_limit = create_ai_rate_limit_dependency(ai_analysis_limiter,
    'analysis')
ai_recommendations_rate_limit = create_ai_rate_limit_dependency(
    ai_recommendations_limiter, 'recommendations')


async def add_rate_limit_headers(request: Request, response) ->Dict[str, Any]:
    """Middleware to add rate limit headers to responses."""
    if hasattr(request.state, 'rate_limit_headers'):
        for header, value in request.state.rate_limit_headers.items():
            response.headers[header] = value
    return response


class AIRateLimitStats:
    """Statistics and monitoring for AI rate limiting."""

    def __init__(self) ->None:
        self.total_requests = 0
        self.rate_limited_requests = 0
        self.requests_by_operation: Dict[str, int] = defaultdict(int)
        self.rate_limits_by_operation: Dict[str, int] = defaultdict(int)
        self.start_time = time.time()

    def record_request(self, operation: str, rate_limited: bool=False) ->None:
        """Record a request for statistics."""
        self.total_requests += 1
        self.requests_by_operation[operation] += 1
        if rate_limited:
            self.rate_limited_requests += 1
            self.rate_limits_by_operation[operation] += 1

    def get_stats(self) ->Dict:
        """Get current rate limiting statistics."""
        uptime = time.time() - self.start_time
        return {'uptime_seconds': uptime, 'total_requests': self.
            total_requests, 'rate_limited_requests': self.
            rate_limited_requests, 'rate_limit_percentage': self.
            rate_limited_requests / self.total_requests * 100 if self.
            total_requests > 0 else 0, 'requests_by_operation': dict(self.
            requests_by_operation), 'rate_limits_by_operation': dict(self.
            rate_limits_by_operation), 'requests_per_minute': self.
            total_requests / uptime * 60 if uptime > 0 else 0}


ai_rate_limit_stats = AIRateLimitStats()


def get_ai_rate_limit_stats() ->Dict:
    """Get AI rate limiting statistics."""
    return ai_rate_limit_stats.get_stats()
