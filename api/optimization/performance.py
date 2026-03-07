"""
API Performance Optimization Module for RuleIQ.
Implements response caching, compression, pagination, and async processing.
"""

import gzip
import json
import hashlib
from typing import Dict, Any, Optional, List, Callable
from datetime import datetime
from functools import wraps
import asyncio

from fastapi import Request, Response
from fastapi.responses import StreamingResponse
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.middleware.gzip import GZipMiddleware
import orjson
import msgpack

import redis
from redis import ConnectionPool

from core.config import settings

import logging

logger = logging.getLogger(__name__)


class APIOptimizer:
    """Main API performance optimization handler."""

    def __init__(self) -> None:
        self.cache_ttl = 300  # 5 minutes default
        self.compression_threshold = 1024  # Compress responses > 1KB
        self.batch_size = 100  # Default batch size for pagination
        self.redis_client = None
        self._init_redis()

    def _init_redis(self):
        """Initialize Redis for response caching."""
        try:
            pool = ConnectionPool(
                host=settings.REDIS_HOST if hasattr(settings, "REDIS_HOST") else "localhost",
                port=settings.REDIS_PORT if hasattr(settings, "REDIS_PORT") else 6379,
                db=1,  # Use DB 1 for API cache
                max_connections=100,
                socket_keepalive=True,
            )
            self.redis_client = redis.Redis(connection_pool=pool)
            self.redis_client.ping()
            logger.info("Redis initialized for API caching")
        except Exception as e:
            logger.warning(f"Redis not available for API caching: {e}")
            self.redis_client = None


class ResponseCacheMiddleware(BaseHTTPMiddleware):
    """Middleware for caching API responses."""

    # Endpoints to cache
    CACHEABLE_PATHS = {
        "/api/frameworks",
        "/api/compliance/status",
        "/api/dashboard",
        "/api/reports",
        "/api/evidence/stats",
    }

    # Patterns for cacheable paths
    CACHEABLE_PATTERNS = [
        r"^/api/frameworks/\w+$",
        r"^/api/assessments/\w+/results$",
        r"^/api/evidence/\w+/quality$",
    ]

    def __init__(self, app, optimizer: APIOptimizer) -> None:
        super().__init__(app)
        self.optimizer = optimizer

    async def dispatch(self, request: Request, call_next):
        """Process request with caching."""

        # Only cache GET requests
        if request.method != "GET":
            return await call_next(request)

        # Check if path is cacheable
        if not self._is_cacheable(request.url.path):
            return await call_next(request)

        # Generate cache key
        cache_key = self._generate_cache_key(request)

        # Try to get from cache
        if self.optimizer.redis_client:
            cached_response = self._get_cached_response(cache_key)
            if cached_response:
                return Response(
                    content=cached_response["content"],
                    status_code=cached_response["status_code"],
                    headers=cached_response["headers"],
                    media_type=cached_response["media_type"],
                )

        # Process request
        response = await call_next(request)

        # Cache successful responses
        if response.status_code == 200 and self.optimizer.redis_client:
            await self._cache_response(cache_key, response)

        return response

    def _is_cacheable(self, path: str) -> bool:
        """Check if path should be cached."""
        import re

        # Check exact matches
        if path in self.CACHEABLE_PATHS:
            return True

        # Check patterns
        return any(re.match(pattern, path) for pattern in self.CACHEABLE_PATTERNS)

    def _generate_cache_key(self, request: Request) -> str:
        """Generate cache key for request."""
        # Include user ID if authenticated
        user_id = getattr(request.state, "user_id", "anonymous")

        # Create key from path, query params, and user
        key_parts = [request.url.path, str(request.query_params), user_id]

        key_str = ":".join(key_parts)
        # Use SHA-256 instead of MD5 for security compliance, truncated for cache key optimization
        return f"api_cache:{hashlib.sha256(key_str.encode()).hexdigest()[:32]}"

    def _get_cached_response(self, cache_key: str) -> Optional[Dict]:
        """Get cached response from Redis."""
        try:
            cached = self.optimizer.redis_client.get(cache_key)
            if cached:
                return msgpack.unpackb(cached, raw=False)
        except Exception as e:
            logger.warning(f"Cache retrieval error: {e}")
        return None

    async def _cache_response(self, cache_key: str, response: Response):
        """Cache response in Redis."""
        try:
            # Read response body
            body = b""
            async for chunk in response.body_iterator:
                body += chunk

            # Prepare cache data
            cache_data = {
                "content": body,
                "status_code": response.status_code,
                "headers": dict(response.headers),
                "media_type": response.media_type,
            }

            # Store in cache
            self.optimizer.redis_client.setex(
                cache_key, self.optimizer.cache_ttl, msgpack.packb(cache_data)
            )

            # Reset response body
            response.body_iterator = self._iterate_body(body)

        except Exception as e:
            logger.warning(f"Cache storage error: {e}")

    async def _iterate_body(self, body: bytes):
        """Iterate over body bytes."""
        yield body


class CompressionOptimizer:
    """Optimize response compression."""

    @staticmethod
    def compress_response(content: bytes, encoding: str = "gzip") -> bytes:
        """Compress response content."""
        if encoding == "gzip":
            return gzip.compress(content, compresslevel=6)
        return content

    @staticmethod
    def should_compress(content: bytes, content_type: str) -> bool:
        """Check if content should be compressed."""
        # Don't compress small responses
        if len(content) < 1024:
            return False

        # Don't compress already compressed formats
        compressed_types = {"image/", "video/", "audio/", "application/zip"}
        return not any(content_type.startswith(ct) for ct in compressed_types)


class PaginationOptimizer:
    """Optimize pagination for large datasets."""

    @staticmethod
    def paginate_query(query, page: int = 1, per_page: int = 100):
        """Apply pagination to SQLAlchemy query."""
        offset = (page - 1) * per_page
        return query.limit(per_page).offset(offset)

    @staticmethod
    def paginate_list(items: List, page: int = 1, per_page: int = 100) -> Dict:
        """Paginate a list of items."""
        total = len(items)
        start = (page - 1) * per_page
        end = start + per_page

        return {
            "items": items[start:end],
            "total": total,
            "page": page,
            "per_page": per_page,
            "pages": (total + per_page - 1) // per_page,
        }

    @staticmethod
    def cursor_paginate(query, cursor: Optional[str] = None, limit: int = 100):
        """Apply cursor-based pagination."""
        if cursor:
            # Decode cursor and apply filter
            decoded_cursor = json.loads(cursor)
            query = query.filter(decoded_cursor)

        # Get results
        results = query.limit(limit + 1).all()

        # Check if there are more results
        has_next = len(results) > limit
        if has_next:
            results = results[:-1]

        # Generate next cursor
        next_cursor = None
        if has_next and results:
            last_item = results[-1]
            next_cursor = json.dumps({"id": last_item.id})

        return {"items": results, "next_cursor": next_cursor, "has_next": has_next}


class AsyncProcessingOptimizer:
    """Optimize async processing for long-running operations."""

    def __init__(self) -> None:
        self.task_queue: Dict[str, asyncio.Task] = {}
        self.results_cache: Dict[str, Any] = {}

    async def process_async(self, task_id: str, coroutine: Callable) -> str:
        """Process a task asynchronously."""
        # Create task
        task = asyncio.create_task(coroutine())
        self.task_queue[task_id] = task

        # Store result when complete
        async def store_result():
            try:
                result = await task
                self.results_cache[task_id] = {
                    "status": "completed",
                    "result": result,
                    "completed_at": datetime.utcnow(),
                }
            except Exception as e:
                self.results_cache[task_id] = {
                    "status": "failed",
                    "error": str(e),
                    "completed_at": datetime.utcnow(),
                }

        asyncio.create_task(store_result())

        return task_id

    def get_task_status(self, task_id: str) -> Dict:
        """Get status of an async task."""
        if task_id in self.results_cache:
            return self.results_cache[task_id]

        if task_id in self.task_queue:
            task = self.task_queue[task_id]
            if task.done():
                return {"status": "completed"}
            return {"status": "processing"}

        return {"status": "not_found"}


class ResponseOptimizer:
    """Optimize API responses."""

    @staticmethod
    def optimize_json_response(data: Any) -> Response:
        """Create optimized JSON response using orjson."""
        content = orjson.dumps(data, option=orjson.OPT_NON_STR_KEYS | orjson.OPT_SERIALIZE_NUMPY)

        return Response(
            content=content,
            media_type="application/json",
            headers={"Cache-Control": "public, max-age=300", "X-Content-Type-Options": "nosniff"},
        )

    @staticmethod
    def stream_large_response(data_generator):
        """Stream large responses to avoid memory issues."""

        async def generate():
            yield b"["
            first = True
            async for item in data_generator:
                if not first:
                    yield b","
                yield orjson.dumps(item)
                first = False
            yield b"]"

        return StreamingResponse(generate(), media_type="application/json")


# Decorators for optimization
def cache_response(ttl: int = 300):
    """Decorator to cache function responses."""

    def decorator(func):
        @wraps(func)
        async def wrapper(*args, **kwargs):
            # Generate cache key
            cache_key = f"func_cache:{func.__name__}:{str(args)}:{str(kwargs)}"
            # Use SHA-256 instead of MD5 for security compliance, truncated for cache key optimization
            cache_key = hashlib.sha256(cache_key.encode()).hexdigest()[:32]

            # Try to get from cache
            optimizer = get_api_optimizer()
            if optimizer.redis_client:
                try:
                    cached = optimizer.redis_client.get(cache_key)
                    if cached:
                        return msgpack.unpackb(cached, raw=False)
                except Exception as e:
                    logger.warning(f"Cache retrieval error: {e}")

            # Execute function
            result = await func(*args, **kwargs)

            # Cache result
            if optimizer.redis_client:
                try:
                    optimizer.redis_client.setex(cache_key, ttl, msgpack.packb(result))
                except Exception as e:
                    logger.warning(f"Cache storage error: {e}")

            return result

        return wrapper

    return decorator


def batch_process(batch_size: int = 100):
    """Decorator for batch processing of large datasets."""

    def decorator(func):
        @wraps(func)
        async def wrapper(items: List, *args, **kwargs):
            results = []

            for i in range(0, len(items), batch_size):
                batch = items[i : i + batch_size]
                batch_results = await func(batch, *args, **kwargs)
                results.extend(batch_results)

                # Small delay between batches to avoid overwhelming the system
                if i + batch_size < len(items):
                    await asyncio.sleep(0.1)

            return results

        return wrapper

    return decorator


# Singleton instance
_optimizer_instance = None


def get_api_optimizer() -> APIOptimizer:
    """Get singleton API optimizer instance."""
    global _optimizer_instance
    if _optimizer_instance is None:
        _optimizer_instance = APIOptimizer()
    return _optimizer_instance


def setup_api_optimization(app):
    """Setup API optimization on FastAPI app."""
    optimizer = get_api_optimizer()

    # Add compression middleware
    app.add_middleware(GZipMiddleware, minimum_size=1000)

    # Add response cache middleware
    app.add_middleware(ResponseCacheMiddleware, optimizer=optimizer)

    logger.info("API optimization configured")
    return optimizer
