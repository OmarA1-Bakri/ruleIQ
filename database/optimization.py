"""
Database Performance Optimization Module for RuleIQ.
Implements connection pooling, query optimization, caching, and monitoring.
"""

import time
import logging
from typing import Dict, Any
from datetime import datetime
from functools import wraps
import asyncio
from contextlib import asynccontextmanager

from sqlalchemy import create_engine, event, Index, inspect
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy.orm import sessionmaker, Query
from sqlalchemy.pool import QueuePool, NullPool, StaticPool
from sqlalchemy.sql import Select
import redis
from redis import ConnectionPool

from core.config import settings

logger = logging.getLogger(__name__)


class DatabaseOptimizer:
    """Main database optimization handler."""

    def __init__(self) -> None:
        self.pool_size = settings.DB_POOL_SIZE if hasattr(settings, "DB_POOL_SIZE") else 20
        self.max_overflow = settings.DB_MAX_OVERFLOW if hasattr(settings, "DB_MAX_OVERFLOW") else 10
        self.pool_timeout = 30
        self.pool_recycle = 3600  # Recycle connections after 1 hour
        self.query_cache = {}
        self.slow_query_threshold = 1.0  # seconds
        self.redis_client = None
        self._init_redis()

    def _init_redis(self):
        """Initialize Redis connection for caching."""
        try:
            pool = ConnectionPool(
                host=settings.REDIS_HOST if hasattr(settings, "REDIS_HOST") else "localhost",
                port=settings.REDIS_PORT if hasattr(settings, "REDIS_PORT") else 6379,
                db=0,
                max_connections=50,
                socket_keepalive=True,
                socket_keepalive_options={
                    1: 1,  # TCP_KEEPIDLE
                    2: 1,  # TCP_KEEPINTVL
                    3: 5,  # TCP_KEEPCNT
                },
            )
            self.redis_client = redis.Redis(connection_pool=pool)
            self.redis_client.ping()
            logger.info("Redis cache initialized for database optimization")
        except Exception as e:
            logger.warning(f"Redis not available for caching: {e}")
            self.redis_client = None

    def create_optimized_engine(self, database_url: str, is_async: bool = False):
        """Create optimized database engine with connection pooling."""

        # Determine pool class based on database type
        if "sqlite" in database_url:
            pool_class = StaticPool if ":memory:" in database_url else NullPool
        else:
            pool_class = QueuePool

        engine_params = {
            "poolclass": pool_class,
            "pool_size": self.pool_size,
            "max_overflow": self.max_overflow,
            "pool_timeout": self.pool_timeout,
            "pool_recycle": self.pool_recycle,
            "pool_pre_ping": True,  # Verify connections before using
            "echo_pool": settings.DEBUG if hasattr(settings, "DEBUG") else False,
            "connect_args": {
                "connect_timeout": 10,
                "application_name": "ruleiq_optimized",
            },
        }

        # PostgreSQL specific optimizations
        if "postgresql" in database_url:
            engine_params["connect_args"].update(
                {
                    "server_settings": {
                        "jit": "off",  # Disable JIT for consistent performance
                        "random_page_cost": "1.1",  # Optimize for SSD
                        "effective_cache_size": "4GB",
                        "shared_buffers": "256MB",
                        "work_mem": "4MB",
                        "maintenance_work_mem": "64MB",
                    },
                    "options": "-c statement_timeout=30000",  # 30 second timeout
                }
            )

        if is_async:
            engine = create_async_engine(database_url, **engine_params)
        else:
            engine = create_engine(database_url, **engine_params)

        # Add event listeners for monitoring
        self._add_engine_listeners(engine)

        return engine

    def _add_engine_listeners(self, engine):
        """Add event listeners for query monitoring and optimization."""

        @event.listens_for(engine, "before_execute")
        def receive_before_execute(conn, clauseelement, multiparams, params, execution_options):
            conn.info.setdefault("query_start_time", []).append(time.time())
            conn.info.setdefault("query_text", []).append(str(clauseelement))

        @event.listens_for(engine, "after_execute")
        def receive_after_execute(
            conn, clauseelement, multiparams, params, execution_options, result
        ):
            total_time = time.time() - conn.info["query_start_time"].pop(-1)
            query_text = conn.info["query_text"].pop(-1)

            # Log slow queries
            if total_time > self.slow_query_threshold:
                logger.warning(f"Slow query detected ({total_time:.2f}s): {query_text[:200]}")
                self._analyze_slow_query(query_text, total_time)

    def _analyze_slow_query(self, query: str, execution_time: float):
        """Analyze and log slow queries for optimization."""
        analysis = {
            "query": query[:500],
            "execution_time": execution_time,
            "timestamp": datetime.utcnow().isoformat(),
            "suggestions": [],
        }

        # Basic query analysis
        query_lower = query.lower()

        if "select *" in query_lower:
            analysis["suggestions"].append("Avoid SELECT *, specify needed columns")

        if "not in" in query_lower or "not exists" in query_lower:
            analysis["suggestions"].append("Consider using LEFT JOIN with NULL check")

        if query_lower.count("join") > 3:
            analysis["suggestions"].append("Many JOINs detected, consider denormalization")

        if "like" in query_lower and "% " in query:
            analysis["suggestions"].append("Leading wildcard in LIKE may prevent index use")

        logger.info(f"Query analysis: {analysis}")

    def create_indexes(self, engine):
        """Create optimized indexes for common queries."""

        indexes = [
            # User and authentication indexes
            Index("ix_users_email_active", "users", "email", "is_active"),
            Index("ix_users_created_at", "users", "created_at"),
            # Assessment indexes
            Index("ix_assessments_user_framework", "assessments", "user_id", "framework_id"),
            Index("ix_assessments_status_created", "assessments", "status", "created_at"),
            # Evidence indexes
            Index("ix_evidence_user_framework", "evidence", "user_id", "framework_id"),
            Index("ix_evidence_status", "evidence", "status"),
            # Audit log indexes
            Index("ix_audit_logs_user_timestamp", "audit_logs", "user_id", "timestamp"),
            Index("ix_audit_logs_event_type", "audit_logs", "event_type"),
            # Session indexes
            Index("ix_sessions_token", "sessions", "token"),
            Index("ix_sessions_expires_at", "sessions", "expires_at"),
        ]

        inspector = inspect(engine)
        existing_indexes = set()

        for table_name in inspector.get_table_names():
            for index in inspector.get_indexes(table_name):
                existing_indexes.add(index["name"])

        created_count = 0
        for index in indexes:
            if index.name not in existing_indexes:
                try:
                    index.create(engine)
                    created_count += 1
                    logger.info(f"Created index: {index.name}")
                except Exception as e:
                    logger.warning(f"Failed to create index {index.name}: {e}")

        logger.info(f"Index optimization complete. Created {created_count} new indexes")

    def optimize_query(self, query: Query) -> Query:
        """Apply query optimizations."""

        # Add query hints
        query = query.execution_options(
            synchronize_session=False, populate_existing=True, autoflush=False
        )

        # Enable query result caching
        if self.redis_client:
            query = query.execution_options(cache_key=self._generate_cache_key(str(query)))

        return query

    def _generate_cache_key(self, query_str: str) -> str:
        """Generate cache key for query results."""
        import hashlib

        return f"query_cache:{hashlib.md5(query_str.encode()).hexdigest()}"

    async def cached_query(self, session: AsyncSession, query: Select, cache_ttl: int = 300):
        """Execute query with caching."""

        if not self.redis_client:
            # No cache available, execute directly
            result = await session.execute(query)
            return result.scalars().all()

        # Generate cache key
        cache_key = self._generate_cache_key(str(query))

        # Check cache
        cached_result = self.redis_client.get(cache_key)
        if cached_result:
            import json

            return json.loads(cached_result.decode("utf-8"))

        # Execute query
        result = await session.execute(query)
        data = result.scalars().all()

        # Cache result
        import json

        # Convert SQLAlchemy objects to dictionaries for JSON serialization
        serializable_data = [obj.__dict__ if hasattr(obj, "__dict__") else str(obj) for obj in data]
        self.redis_client.setex(cache_key, cache_ttl, json.dumps(serializable_data).encode("utf-8"))

        return data

    def invalidate_cache(self, pattern: str = "*"):
        """Invalidate cached query results."""
        if self.redis_client:
            keys = self.redis_client.keys(f"query_cache:{pattern}")
            if keys:
                self.redis_client.delete(*keys)
                logger.info(f"Invalidated {len(keys)} cache entries")


class ConnectionPoolManager:
    """Manage database connection pools efficiently."""

    def __init__(self, optimizer: DatabaseOptimizer) -> None:
        self.optimizer = optimizer
        self.pools: Dict[str, Any] = {}
        self.pool_stats: Dict[str, Dict] = {}
        self._monitor_task = None

    def get_pool(self, name: str = "default") -> Any:
        """Get or create a connection pool."""
        if name not in self.pools:
            self.pools[name] = self._create_pool(name)
            self.pool_stats[name] = {"created_at": datetime.utcnow(), "connections": 0, "errors": 0}
        return self.pools[name]

    def _create_pool(self, name: str) -> Any:
        """Create a new connection pool."""
        database_url = getattr(settings, f"DATABASE_URL_{name.upper()}", settings.DATABASE_URL)
        engine = self.optimizer.create_optimized_engine(database_url)
        return sessionmaker(bind=engine)

    async def monitor_pools(self):
        """Monitor connection pool health."""
        while True:
            for name, pool in self.pools.items():
                try:
                    # Get pool statistics
                    engine = pool.kw["bind"]
                    pool_impl = engine.pool

                    stats = {
                        "size": pool_impl.size(),
                        "checked_in": pool_impl.checkedin(),
                        "checked_out": pool_impl.checkedout(),
                        "overflow": pool_impl.overflow(),
                        "total": pool_impl.total(),
                    }

                    self.pool_stats[name].update(stats)

                    # Log if pool is exhausted
                    if stats["checked_out"] >= self.optimizer.pool_size:
                        logger.warning(f"Connection pool '{name}' is exhausted: {stats}")

                except Exception as e:
                    logger.error(f"Error monitoring pool '{name}': {e}")

            await asyncio.sleep(60)  # Check every minute

    def start_monitoring(self):
        """Start pool monitoring task."""
        if not self._monitor_task:
            self._monitor_task = asyncio.create_task(self.monitor_pools())

    def get_stats(self) -> Dict[str, Dict]:
        """Get current pool statistics."""
        return self.pool_stats


class QueryOptimizationDecorator:
    """Decorators for query optimization."""

    @staticmethod
    def with_retry(max_attempts: int = 3, delay: float = 1.0):
        """Retry database operations on failure."""

        def decorator(func):
            @wraps(func)
            async def async_wrapper(*args, **kwargs):
                last_exception = None
                for attempt in range(max_attempts):
                    try:
                        return await func(*args, **kwargs)
                    except Exception as e:
                        last_exception = e
                        if attempt < max_attempts - 1:
                            await asyncio.sleep(delay * (attempt + 1))
                        else:
                            logger.error(f"Failed after {max_attempts} attempts: {e}")
                raise last_exception

            @wraps(func)
            def sync_wrapper(*args, **kwargs):
                last_exception = None
                for attempt in range(max_attempts):
                    try:
                        return func(*args, **kwargs)
                    except Exception as e:
                        last_exception = e
                        if attempt < max_attempts - 1:
                            time.sleep(delay * (attempt + 1))
                        else:
                            logger.error(f"Failed after {max_attempts} attempts: {e}")
                raise last_exception

            return async_wrapper if asyncio.iscoroutinefunction(func) else sync_wrapper

        return decorator

    @staticmethod
    def with_timeout(timeout: float = 30.0):
        """Add timeout to database operations."""

        def decorator(func):
            @wraps(func)
            async def wrapper(*args, **kwargs):
                try:
                    return await asyncio.wait_for(func(*args, **kwargs), timeout=timeout)
                except asyncio.TimeoutError:
                    logger.error(f"Database operation timed out after {timeout}s")
                    raise

            return wrapper

        return decorator


# Singleton instance
_optimizer_instance = None


def get_database_optimizer() -> DatabaseOptimizer:
    """Get singleton database optimizer instance."""
    global _optimizer_instance
    if _optimizer_instance is None:
        _optimizer_instance = DatabaseOptimizer()
    return _optimizer_instance


# Export optimized session makers
optimizer = get_database_optimizer()
OptimizedEngine = optimizer.create_optimized_engine(settings.DATABASE_URL)
OptimizedAsyncEngine = optimizer.create_optimized_engine(
    settings.DATABASE_URL.replace("postgresql://", "postgresql+asyncpg://"), is_async=True
)

OptimizedSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=OptimizedEngine)

OptimizedAsyncSessionLocal = async_sessionmaker(
    OptimizedAsyncEngine, class_=AsyncSession, expire_on_commit=False
)


@asynccontextmanager
async def get_optimized_db():
    """Get optimized async database session."""
    async with OptimizedAsyncSessionLocal() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()
