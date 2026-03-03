from __future__ import annotations
import time
from typing import Dict, Tuple, Any
from fastapi import HTTPException, Request, status
from fastapi.responses import JSONResponse

class RateLimiter:

    def __init__(self, requests_per_minute: int=60) -> None:
        self.requests_per_minute = requests_per_minute
        self.requests: Dict[str, list] = {}
        self.cleanup_interval = 300
        self._last_cleanup = time.time()

    async def check_rate_limit(self, identifier: str) -> Tuple[bool, int]:
        """Check if request is within rate limit. Returns (allowed, retry_after_seconds)"""
        current_time = time.time()
        minute_ago = current_time - 60
        if current_time - self._last_cleanup > self.cleanup_interval:
            await self._cleanup_old_entries()
        if identifier not in self.requests:
            self.requests[identifier] = []
        self.requests[identifier] = [req_time for req_time in self.requests[identifier] if req_time > minute_ago]
        if len(self.requests[identifier]) >= self.requests_per_minute:
            retry_after = int(60 - (current_time - self.requests[identifier][0]))
            return (False, retry_after)
        self.requests[identifier].append(current_time)
        return (True, 0)

    async def _cleanup_old_entries(self) -> None:
        """Remove entries with no recent requests"""
        current_time = time.time()
        minute_ago = current_time - 60
        self.requests = {k: [t for t in v if t > minute_ago] for k, v in self.requests.items() if any((t > minute_ago for t in v))}
        self._last_cleanup = current_time
from config.settings import get_settings
settings = get_settings()
if settings.is_testing:
    general_limiter = RateLimiter(requests_per_minute=100)
    auth_limiter = RateLimiter(requests_per_minute=50)
else:
    general_limiter = RateLimiter(requests_per_minute=getattr(settings, 'rate_limit_requests', 60))
    auth_limiter = RateLimiter(requests_per_minute=10)
strict_test_limiter = RateLimiter(requests_per_minute=4)

async def rate_limit_middleware(request: Request, call_next) -> Any:
    """General rate limiting middleware"""
    if request.url.path in ['/docs', '/redoc', '/openapi.json', '/api/v1/docs', '/api/v1/redoc', '/api/v1/openapi.json'] or settings.is_testing:
        return await call_next(request)
    client_ip = request.client.host if request.client else 'unknown'
    if client_ip in ['127.0.0.1', '::1', 'localhost'] and settings.is_testing:
        return await call_next(request)
    allowed, retry_after = await general_limiter.check_rate_limit(client_ip)
    if not allowed:
        return JSONResponse(status_code=status.HTTP_429_TOO_MANY_REQUESTS, content={'error': {'message': 'Rate limit exceeded', 'code': 'RATE_LIMIT_EXCEEDED', 'retry_after': retry_after}}, headers={'Retry-After': str(retry_after), 'X-RateLimit-Limit': str(general_limiter.requests_per_minute), 'X-RateLimit-Remaining': '0', 'X-RateLimit-Reset': str(int(time.time()) + retry_after)})
    response = await call_next(request)
    remaining = general_limiter.requests_per_minute - len(general_limiter.requests.get(client_ip, []))
    response.headers['X-RateLimit-Limit'] = str(general_limiter.requests_per_minute)
    response.headers['X-RateLimit-Remaining'] = str(max(0, remaining))
    response.headers['X-RateLimit-Reset'] = str(int(time.time()) + 60)
    return response

def auth_rate_limit() -> Any:
    """Dependency for auth endpoint rate limiting"""

    async def check_limit(request: "Request") -> None:
        if settings.is_testing:
            return
        client_ip = request.client.host if request.client else 'unknown'
        if client_ip in ['127.0.0.1', '::1', 'localhost'] and settings.is_testing:
            return
        allowed, retry_after = await auth_limiter.check_rate_limit(client_ip)
        if not allowed:
            raise HTTPException(status_code=status.HTTP_429_TOO_MANY_REQUESTS, detail=f'Too many authentication attempts. Try again in {retry_after} seconds', headers={'Retry-After': str(retry_after), 'X-RateLimit-Limit': str(auth_limiter.requests_per_minute), 'X-RateLimit-Remaining': '0', 'X-RateLimit-Reset': str(int(time.time()) + retry_after)})
        remaining = auth_limiter.requests_per_minute - len(auth_limiter.requests.get(client_ip, []))
        request.state.rate_limit_headers = {'X-RateLimit-Limit': str(auth_limiter.requests_per_minute), 'X-RateLimit-Remaining': str(max(0, remaining)), 'X-RateLimit-Reset': str(int(time.time()) + 60)}
    return check_limit

def rate_limit(requests_per_minute: int=60) -> Any:
    """Create a custom rate limit dependency with specified limit."""
    custom_limiter = RateLimiter(requests_per_minute=requests_per_minute)

    async def check_custom_limit(request: "Request") -> None:
        if settings.is_testing and requests_per_minute > 10:
            return
        client_ip = request.client.host if request.client else 'unknown'
        allowed, retry_after = await custom_limiter.check_rate_limit(client_ip)
        if not allowed:
            raise HTTPException(status_code=status.HTTP_429_TOO_MANY_REQUESTS, detail=f'Rate limit exceeded: {requests_per_minute} requests per minute. Try again in {retry_after} seconds', headers={'Retry-After': str(retry_after), 'X-RateLimit-Limit': str(requests_per_minute), 'X-RateLimit-Remaining': '0', 'X-RateLimit-Reset': str(int(time.time()) + retry_after)})
        remaining = requests_per_minute - len(custom_limiter.requests.get(client_ip, []))
        request.state.rate_limit_headers = {'X-RateLimit-Limit': str(requests_per_minute), 'X-RateLimit-Remaining': str(max(0, remaining)), 'X-RateLimit-Reset': str(int(time.time()) + 60)}
    return check_custom_limit

class RateLimited:
    """Rate limiting dependency class for FastAPI endpoints"""

    def __init__(self, requests: int, window: int=60) -> None:
        """
        Initialize rate limiter

        Args:
            requests: Number of requests allowed per window
            window: Time window in seconds (default: 60)
        """
        self.requests_per_minute = requests
        self.limiter = RateLimiter(requests_per_minute=requests)

    async def __call__(self, request) -> None:
        """FastAPI dependency that checks rate limits"""
        if settings.is_testing and self.requests_per_minute > 10:
            return
        client_ip = request.client.host if request.client else 'unknown'
        allowed, retry_after = await self.limiter.check_rate_limit(client_ip)
        if not allowed:
            raise HTTPException(status_code=status.HTTP_429_TOO_MANY_REQUESTS, detail=f'Rate limit exceeded: {self.requests_per_minute} requests per minute. Try again in {retry_after} seconds', headers={'Retry-After': str(retry_after)})
