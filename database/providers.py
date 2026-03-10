"""
Database provider interface and implementations.

This module provides the core database provider abstractions and concrete
implementations for PostgreSQL and Neo4j databases with dependency injection support.
"""

import asyncio
import concurrent.futures
import logging
import os
import time
from abc import ABC, abstractmethod
from typing import Dict, Any, List, Optional, cast
from dataclasses import dataclass

from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker
from sqlalchemy import text
import neo4j
from neo4j import GraphDatabase


logger = logging.getLogger(__name__)


@dataclass
class ConnectionHealth:
    """Represents the health status of a database connection."""

    status: str  # "healthy", "unhealthy", "degraded"
    details: Dict[str, Any]
    timestamp: Optional[float] = None

    def __post_init__(self):
        if self.timestamp is None:
            self.timestamp = time.time()


class DatabaseError(Exception):
    """Custom exception for database operations."""

    def __init__(
        self,
        message: str,
        details: Optional[Dict[str, Any]] = None,
        cause: Optional[Exception] = None,
    ) -> None:
        super().__init__(message)
        self.details = details or {}
        self.cause = cause


class DatabaseProvider(ABC):
    """Abstract base class for database providers."""

    @abstractmethod
    async def initialize(self) -> bool:
        """Initialize the database connection."""
        raise NotImplementedError

    @abstractmethod
    async def close(self) -> None:
        """Close the database connection."""
        raise NotImplementedError

    @abstractmethod
    async def health_check(self) -> ConnectionHealth:
        """Check the health of the database connection."""
        raise NotImplementedError

    @abstractmethod
    async def execute_query(
        self, query: str, params: Optional[Dict[str, Any]] = None
    ) -> List[Dict[str, Any]]:
        """Execute a query and return results."""
        raise NotImplementedError

    @abstractmethod
    async def execute_transaction(self, queries: List[Dict[str, Any]]) -> bool:
        """Execute multiple queries in a transaction."""
        raise NotImplementedError


class DatabaseConfig:
    """Configuration for database providers."""

    @staticmethod
    def get_provider(provider_type: str) -> DatabaseProvider:
        """Factory method to create database providers."""
        if provider_type == "postgres":
            return PostgreSQLProvider()
        elif provider_type == "neo4j":
            return Neo4jProvider()
        else:
            raise ValueError("Unsupported provider type: %s" % provider_type)


class PostgreSQLProvider(DatabaseProvider):
    """PostgreSQL database provider implementation."""

    def __init__(self) -> None:
        self.engine: Any = None
        self.session_maker: Any = None
        self._initialized = False

    async def initialize(self) -> bool:
        """Initialize PostgreSQL connection using existing pool config."""
        try:
            if self._initialized:
                return True

            # Use existing database setup configuration
            from database.db_setup import DatabaseConfig as ExistingConfig

            # Get database URLs
            _, _, async_db_url = ExistingConfig.get_database_urls()

            # Get optimized pool settings
            pool_kwargs = ExistingConfig.get_engine_kwargs(is_async=True)

            # Create async engine
            self.engine = create_async_engine(async_db_url, **pool_kwargs)

            # Create session maker
            self.session_maker = async_sessionmaker(
                bind=self.engine,
                class_=AsyncSession,
                expire_on_commit=False,
                autocommit=False,
                autoflush=False,
            )

            self._initialized = True
            logger.info("PostgreSQL provider initialized successfully")
            return True

        except (ImportError, ConnectionError, ValueError):
            logger.exception("Failed to initialize PostgreSQL provider")
            return False

    async def close(self) -> None:
        """Close PostgreSQL connection."""
        if self.engine:
            await self.engine.dispose()
            self.engine = None
            self.session_maker = None
            self._initialized = False
            logger.info("PostgreSQL provider closed")

    async def health_check(self) -> ConnectionHealth:
        """Check PostgreSQL connection health."""
        if not self._initialized:
            return ConnectionHealth(status="unhealthy", details={"error": "Not initialized"})

        start_time = time.time()
        try:
            assert self.session_maker is not None
            async with self.session_maker() as session:
                # Simple health check query
                result = await session.execute(text("SELECT 1 as health_check"))
                row = result.first()
                response_time = time.time() - start_time

                if row and row.health_check == 1:
                    # Check connection pool stats
                    pool_details = {}
                    if self.engine is not None and hasattr(self.engine, "pool"):
                        pool = self.engine.pool
                        pool_details = {
                            "pool_size": getattr(pool, "size", lambda: 0)(),
                            "checked_in": getattr(pool, "checkedin", lambda: 0)(),
                            "checked_out": getattr(pool, "checkedout", lambda: 0)(),
                            "overflow": getattr(pool, "overflow", lambda: 0)(),
                        }

                    return ConnectionHealth(
                        status="healthy",
                        details={"response_time": response_time, "pool_stats": pool_details},
                    )
                else:
                    return ConnectionHealth(
                        status="unhealthy", details={"error": "Health check query failed"}
                    )

        except (ConnectionError, TimeoutError, ValueError) as e:
            response_time = time.time() - start_time
            return ConnectionHealth(
                status="unhealthy", details={"error": str(e), "response_time": response_time}
            )

    async def execute_query(
        self, query: str, params: Optional[Dict[str, Any]] = None
    ) -> List[Dict[str, Any]]:
        """Execute a PostgreSQL query."""
        if not self._initialized:
            raise DatabaseError("PostgreSQL provider not initialized")

        try:
            assert self.session_maker is not None
            async with self.session_maker() as session:
                result = await session.execute(text(query), params or {})
                return [dict(row) for row in result.mappings().all()]

        except (ConnectionError, TimeoutError, ValueError) as e:
            logger.exception("PostgreSQL query execution failed: %s", e)
            raise DatabaseError(
                "Query execution failed: %s" % e, {"query": query, "params": params}, e
            ) from e

    async def execute_transaction(self, queries: List[Dict[str, Any]]) -> bool:
        """Execute multiple PostgreSQL queries in a transaction."""
        if not self._initialized:
            raise DatabaseError("PostgreSQL provider not initialized")

        try:
            assert self.session_maker is not None
            async with self.session_maker() as session:
                async with session.begin():
                    for query_data in queries:
                        query = query_data["query"]
                        params = query_data.get("params", {})
                        await session.execute(text(query), params)

                await session.commit()
                return True

        except (ConnectionError, TimeoutError, ValueError) as e:
            logger.exception("PostgreSQL transaction failed: %s", e)
            raise DatabaseError("Transaction failed: %s" % e, {"queries": queries}, e) from e


class Neo4jProvider(DatabaseProvider):
    """Neo4j graph database provider implementation."""

    def __init__(self) -> None:
        self.driver: Any = None
        self._initialized = False
        self._executor: Optional[concurrent.futures.ThreadPoolExecutor] = None
        self._database = os.getenv("NEO4J_DATABASE", "neo4j")

    async def initialize(self) -> bool:
        """Initialize Neo4j connection."""
        try:
            if self._initialized:
                return True

            # Get Neo4j configuration from environment
            uri = os.getenv("NEO4J_URI")
            username = os.getenv("NEO4J_USERNAME")
            password = os.getenv("NEO4J_PASSWORD")

            if not uri or not username or not password:
                raise ValueError(
                    "Neo4j credentials required: NEO4J_URI, NEO4J_USERNAME, NEO4J_PASSWORD. "
                    "Set via Doppler or environment."
                )

            # Create Neo4j driver with optimized settings
            self.driver = GraphDatabase.driver(
                uri,
                auth=(username, password),
                max_connection_lifetime=3600,
                max_connection_pool_size=50,
                connection_acquisition_timeout=60,
            )

            self._executor = concurrent.futures.ThreadPoolExecutor(max_workers=10)

            # Test connection
            if not await self._test_connection():
                raise ConnectionError("Neo4j connection test failed")

            self._initialized = True
            logger.info("Neo4j provider initialized successfully")
            return True

        except (ImportError, ConnectionError, neo4j.exceptions.Neo4jError):
            logger.exception("Failed to initialize Neo4j provider")
            return False

    async def _test_connection(self) -> bool:
        """Test Neo4j connection."""
        if not self.driver or not self._executor:
            return False

        try:
            assert self.driver is not None
            assert self._executor is not None

            def _test():
                with self.driver.session(database=self._database) as session:
                    result = session.run("RETURN 1 as test")
                    record = result.single()
                    return record and record["test"] == 1

            return await asyncio.get_event_loop().run_in_executor(self._executor, _test)

        except (neo4j.exceptions.Neo4jError, ConnectionError):
            logger.exception("Neo4j connection test failed")
            return False

    async def close(self) -> None:
        """Close Neo4j connection."""
        if self.driver:
            self.driver.close()
            self.driver = None

        if self._executor:
            self._executor.shutdown(wait=True)
            self._executor = None

        self._initialized = False
        logger.info("Neo4j provider closed")

    async def health_check(self) -> ConnectionHealth:
        """Check Neo4j connection health."""
        if not self._initialized:
            return ConnectionHealth(status="unhealthy", details={"error": "Not initialized"})

        start_time = time.time()
        try:
            assert self.driver is not None
            assert self._executor is not None

            def _health_check():
                with self.driver.session(database=self._database) as session:
                    result = session.run("RETURN 1 as health_check")
                    record = result.single()
                    return record and record["health_check"] == 1

            success = await asyncio.get_event_loop().run_in_executor(self._executor, _health_check)
            response_time = time.time() - start_time

            if success:
                return ConnectionHealth(status="healthy", details={"response_time": response_time})
            else:
                return ConnectionHealth(
                    status="unhealthy", details={"error": "Health check query failed"}
                )

        except (ConnectionError, TimeoutError, ValueError) as e:
            response_time = time.time() - start_time
            return ConnectionHealth(
                status="unhealthy", details={"error": str(e), "response_time": response_time}
            )

    async def execute_query(
        self, query: str, params: Optional[Dict[str, Any]] = None
    ) -> List[Dict[str, Any]]:
        """Execute a Neo4j Cypher query."""
        if not self._initialized:
            raise DatabaseError("Neo4j provider not initialized")

        try:
            assert self.driver is not None
            assert self._executor is not None

            def _execute():
                with self.driver.session(database=self._database) as session:
                    result = session.run(query, params or {})
                    return [record.data() for record in result]

            return await asyncio.get_event_loop().run_in_executor(self._executor, _execute)

        except (neo4j.exceptions.Neo4jError, ConnectionError) as e:
            logger.exception("Neo4j query execution failed: %s", e)
            raise DatabaseError(
                "Query execution failed: %s" % e, {"query": query, "params": params}, e
            ) from e

    async def execute_transaction(self, queries: List[Dict[str, Any]]) -> bool:
        """Execute multiple Neo4j queries in a transaction."""
        if not self._initialized:
            raise DatabaseError("Neo4j provider not initialized")

        try:
            assert self.driver is not None
            assert self._executor is not None

            def _execute_transaction():
                with self.driver.session(database=self._database) as session:
                    with session.begin_transaction() as tx:
                        for query_data in queries:
                            query = query_data["query"]
                            params = query_data.get("params", {})
                            tx.run(query, params)
                        tx.commit()
                        return True

            return await asyncio.get_event_loop().run_in_executor(
                self._executor, _execute_transaction
            )

        except (neo4j.exceptions.Neo4jError, ConnectionError) as e:
            logger.exception("Neo4j transaction failed: %s", e)
            raise DatabaseError("Transaction failed: %s" % e, {"queries": queries}, e) from e


# Global provider instances for backward compatibility
_provider_state: Dict[str, Optional[DatabaseProvider]] = {
    "postgres": None,
    "neo4j": None,
}


async def get_postgres_provider() -> PostgreSQLProvider:
    """Get or create global PostgreSQL provider instance."""
    provider = _provider_state["postgres"]
    if provider is None:
        provider = PostgreSQLProvider()
        await provider.initialize()
        _provider_state["postgres"] = provider
    return cast(PostgreSQLProvider, provider)


async def get_neo4j_provider() -> Neo4jProvider:
    """Get or create global Neo4j provider instance."""
    provider = _provider_state["neo4j"]
    if provider is None:
        provider = Neo4jProvider()
        await provider.initialize()
        _provider_state["neo4j"] = provider
    return cast(Neo4jProvider, provider)


async def initialize_providers() -> None:
    """Initialize all database providers."""
    await get_postgres_provider()
    await get_neo4j_provider()


async def close_providers() -> None:
    """Close all database providers."""
    postgres_provider = _provider_state["postgres"]
    if postgres_provider:
        await postgres_provider.close()
        _provider_state["postgres"] = None

    neo4j_provider = _provider_state["neo4j"]
    if neo4j_provider:
        await neo4j_provider.close()
        _provider_state["neo4j"] = None
