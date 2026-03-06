"""
FastAPI dependency injection for database providers.

This module provides FastAPI dependency injection functions and container
management for database providers with proper lifespan management.
"""

import logging
from contextlib import asynccontextmanager
from typing import Dict, Any, Optional
from fastapi import Request, HTTPException
from fastapi.responses import JSONResponse

from database.providers import DatabaseProvider, PostgreSQLProvider, Neo4jProvider
from database.health import DatabaseHealthMonitor

logger = logging.getLogger(__name__)


class DatabaseContainer:
    """Container for managing database provider instances."""

    def __init__(self) -> None:
        self.providers: Dict[str, DatabaseProvider] = {}
        self.health_monitors: Dict[str, DatabaseHealthMonitor] = {}

    async def register_provider(self, name: str, provider: DatabaseProvider) -> None:
        """Register a database provider."""
        if not await provider.initialize():
            raise RuntimeError(f"Failed to initialize {name} provider")

        self.providers[name] = provider
        logger.info(f"Registered database provider: {name}")

    async def register_health_monitor(self, name: str, monitor: DatabaseHealthMonitor) -> None:
        """Register a health monitor for a provider."""
        self.health_monitors[name] = monitor
        logger.info(f"Registered health monitor: {name}")

    async def get_provider(self, name: str) -> DatabaseProvider:
        """Get a registered provider by name."""
        if name not in self.providers:
            raise ValueError(f"Provider '{name}' not registered")
        return self.providers[name]

    async def get_health_status(self, name: str) -> Dict[str, Any]:
        """Get health status for a provider."""
        if name not in self.health_monitors:
            raise ValueError(f"Health monitor '{name}' not registered")

        monitor = self.health_monitors[name]
        health_metrics = await monitor.check_health()

        return {
            "status": health_metrics.status.value,
            "response_time": health_metrics.response_time,
            "timestamp": health_metrics.timestamp,
            "details": health_metrics.details,
        }

    async def get_all_health_statuses(self) -> Dict[str, Any]:
        """Get health statuses for all registered monitors."""
        statuses = {}
        for name, monitor in self.health_monitors.items():
            try:
                health_metrics = await monitor.check_health()
                # Support both HealthMetrics objects and dict returns
                if hasattr(health_metrics, "to_dict"):
                    # It's a HealthMetrics object
                    statuses[name] = health_metrics.to_dict()
                elif isinstance(health_metrics, dict):
                    # It's already a dict (for backward compatibility with mocks)
                    statuses[name] = health_metrics
                else:
                    # Fallback: try to extract attributes
                    statuses[name] = {
                        "status": getattr(health_metrics, "status", "unknown"),
                        "response_time": getattr(health_metrics, "response_time", 0),
                        "timestamp": getattr(health_metrics, "timestamp", None),
                        "details": getattr(health_metrics, "details", {}),
                    }
            except Exception as e:
                logger.error(f"Error checking health for {name}: {e}")
                statuses[name] = {
                    "status": "unhealthy",
                    "error": str(e),
                    "timestamp": None,
                    "details": {},
                }
        return statuses

    async def close_all(self) -> None:
        """Close all registered providers."""
        for name, provider in self.providers.items():
            try:
                await provider.close()
                logger.info(f"Closed provider: {name}")
            except Exception as e:
                logger.error(f"Error closing provider {name}: {e}")

        self.providers.clear()
        self.health_monitors.clear()


class DependencyConfig:
    """Configuration for dependency injection."""

    def __init__(self) -> None:
        self.container = DatabaseContainer()

    async def initialize_providers(self) -> None:
        """Initialize all configured providers."""
        # Register PostgreSQL provider
        postgres_provider = PostgreSQLProvider()
        await self.container.register_provider("postgres", postgres_provider)

        # Register PostgreSQL health monitor
        from database.health import PostgreSQLHealthMonitor

        postgres_health = PostgreSQLHealthMonitor(postgres_provider)
        await self.container.register_health_monitor("postgres", postgres_health)

        # Register Neo4j provider
        neo4j_provider = Neo4jProvider()
        await self.container.register_provider("neo4j", neo4j_provider)

        # Register Neo4j health monitor
        from database.health import Neo4jHealthMonitor

        neo4j_health = Neo4jHealthMonitor(neo4j_provider)
        await self.container.register_health_monitor("neo4j", neo4j_health)

        logger.info("All database providers initialized")

    async def close_providers(self) -> None:
        """Close all providers."""
        await self.container.close_all()
        logger.info("All database providers closed")


# Global container instance
_container: Optional[DatabaseContainer] = None


async def get_container() -> DatabaseContainer:
    """Get the global database container."""
    global _container
    if _container is None:
        config = DependencyConfig()
        await config.initialize_providers()
        _container = config.container
    return _container


async def initialize_global_container() -> None:
    """Initialize the global container."""
    global _container
    if _container is None:
        config = DependencyConfig()
        await config.initialize_providers()
        _container = config.container


async def close_global_container() -> None:
    """Close the global container."""
    global _container
    if _container:
        await _container.close_all()
        _container = None


# FastAPI dependency functions


async def get_database_provider(provider_name: str, request: Request) -> DatabaseProvider:
    """
    FastAPI dependency to get a database provider by name.

    Args:
        provider_name: Name of the provider ("postgres" or "neo4j")
        request: FastAPI request object

    Returns:
        DatabaseProvider instance

    Raises:
        HTTPException: If provider is unavailable
    """
    try:
        container = await get_container()
        return await container.get_provider(provider_name)
    except Exception as e:
        logger.error(f"Database provider '{provider_name}' unavailable: {e}")
        raise HTTPException(
            status_code=503, detail=f"Database service '{provider_name}' unavailable"
        )


async def get_postgres_provider(request: Request) -> PostgreSQLProvider:
    """
    FastAPI dependency to get PostgreSQL provider.

    Args:
        request: FastAPI request object

    Returns:
        PostgreSQLProvider instance
    """
    provider = await get_database_provider("postgres", request)
    if not isinstance(provider, PostgreSQLProvider):
        raise HTTPException(status_code=503, detail="PostgreSQL provider unavailable")
    return provider


async def get_neo4j_provider(request: Request) -> Neo4jProvider:
    """
    FastAPI dependency to get Neo4j provider.

    Args:
        request: FastAPI request object

    Returns:
        Neo4jProvider instance
    """
    provider = await get_database_provider("neo4j", request)
    if not isinstance(provider, Neo4jProvider):
        raise HTTPException(status_code=503, detail="Neo4j provider unavailable")
    return provider


async def get_database_health(service: str, request: Request) -> Dict[str, Any]:
    """
    FastAPI dependency to get database health status.

    Args:
        service: Service name ("postgres" or "neo4j")
        request: FastAPI request object

    Returns:
        Health status dictionary
    """
    try:
        container = await get_container()
        return await container.get_health_status(service)
    except Exception as e:
        logger.error(f"Health check failed for service '{service}': {e}")
        raise HTTPException(
            status_code=503, detail=f"Health check unavailable for service '{service}'"
        )


# Lifespan management


@asynccontextmanager
async def lifespan(app=None):
    """
    FastAPI lifespan context manager for database initialization.

    This should be used in the FastAPI app lifespan parameter:
    app = FastAPI(lifespan=lifespan)
    """
    # Startup
    try:
        await initialize_global_container()
        logger.info("Database services initialized during app startup")
    except Exception as e:
        logger.error(f"Failed to initialize database services: {e}")
        # Continue startup even if database fails - services might be optional

    yield

    # Shutdown
    try:
        await close_global_container()
        logger.info("Database services closed during app shutdown")
    except Exception as e:
        logger.error(f"Error during database service shutdown: {e}")


# Health check endpoints


async def health_check_endpoint(service: Optional[str] = None) -> JSONResponse:
    """
    Health check endpoint for database services.

    Args:
        service: Optional service name to check. If None, checks all services.

    Returns:
        JSONResponse with health status
    """
    try:
        container = await get_container()

        if service:
            # Check specific service
            health = await container.get_health_status(service)
            status_code = 200 if health["status"] == "healthy" else 503
            return JSONResponse(content=health, status_code=status_code)
        else:
            # Check all services
            all_health = {}
            overall_status = "healthy"

            for service_name in container.providers:
                try:
                    health = await container.get_health_status(service_name)
                    all_health[service_name] = health
                    if health["status"] != "healthy":
                        overall_status = "degraded"
                except Exception as e:
                    all_health[service_name] = {
                        "status": "unhealthy",
                        "error": str(e),
                        "timestamp": None,
                        "details": {},
                    }
                    overall_status = "unhealthy"

            response = {
                "overall_status": overall_status,
                "services": all_health,
                "timestamp": None,  # Could add current timestamp
            }

            status_code = 200 if overall_status == "healthy" else 503
            return JSONResponse(content=response, status_code=status_code)

    except Exception as e:
        logger.error(f"Health check endpoint error: {e}")
        return JSONResponse(
            content={
                "overall_status": "unhealthy",
                "error": str(e),
                "services": {},
                "timestamp": None,
            },
            status_code=503,
        )


# Utility functions for testing


async def reset_container() -> None:
    """Reset the global container (for testing)."""
    global _container
    if _container:
        await _container.close_all()
    _container = None


def create_test_container() -> DatabaseContainer:
    """Create a test container with mock providers."""
    return DatabaseContainer()


# Backward compatibility aliases
get_db_provider = get_database_provider  # Legacy alias
get_postgres_db = get_postgres_provider  # Legacy alias
get_neo4j_db = get_neo4j_provider  # Legacy alias
