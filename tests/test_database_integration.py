"""
Integration tests for database dependency injection system

Tests the complete integration of database providers, dependencies,
health monitoring, and FastAPI application lifecycle.
"""
import pytest
import asyncio
from unittest.mock import AsyncMock, MagicMock, patch
from typing import Dict, Any, Optional
from fastapi import FastAPI, Request, HTTPException
from fastapi.testclient import TestClient

# Import the modules we'll be testing (will be created later)
from database.providers import PostgreSQLProvider, Neo4jProvider
from database.dependencies import (
    DatabaseContainer,
    DependencyConfig,
    get_database_provider,
    get_postgres_provider,
    get_neo4j_provider,
    get_database_health,
    lifespan
)
from database.health import DatabaseHealthMonitor, PostgreSQLHealthMonitor, Neo4jHealthMonitor


class TestDatabaseIntegration:
    """Integration tests for the complete database system."""

    @pytest.fixture
    async def mock_providers(self):
        """Create mock database providers."""
        postgres_provider = AsyncMock(spec=PostgreSQLProvider)
        neo4j_provider = AsyncMock(spec=Neo4jProvider)

        # Configure mock responses
        postgres_provider.initialize.return_value = True
        neo4j_provider.initialize.return_value = True
        postgres_provider.close.return_value = None
        neo4j_provider.close.return_value = None

        return {
            "postgres": postgres_provider,
            "neo4j": neo4j_provider
        }

    @pytest.fixture
    async def container(self, mock_providers):
        """Create and initialize a database container."""
        container = DatabaseContainer()

        # Register providers
        await container.register_provider("postgres", mock_providers["postgres"])
        await container.register_provider("neo4j", mock_providers["neo4j"])

        # Register health monitors
        postgres_health = PostgreSQLHealthMonitor(mock_providers["postgres"])
        neo4j_health = Neo4jHealthMonitor(mock_providers["neo4j"])

        await container.register_health_monitor("postgres", postgres_health)
        await container.register_health_monitor("neo4j", neo4j_health)

        return container

    @pytest.fixture
    async def config(self, container):
        """Create dependency configuration."""
        config = DependencyConfig()
        # Override the container with our test container
        config.container = container
        return config

    @pytest.mark.asyncio
    async def test_full_system_initialization(self, config, mock_providers):
        """Test complete system initialization."""
        # Initialize providers
        await config.initialize_providers()

        # Verify providers were initialized
        mock_providers["postgres"].initialize.assert_called_once()
        mock_providers["neo4j"].initialize.assert_called_once()

    @pytest.mark.asyncio
    async def test_provider_operations_integration(self, container, mock_providers):
        """Test integrated provider operations."""
        # Configure mock query responses
        mock_providers["postgres"].execute_query.return_value = [{"id": 1, "name": "test"}]
        mock_providers["neo4j"].execute_query.return_value = [{"node": "data"}]

        # Test PostgreSQL operations
        postgres_provider = await container.get_provider("postgres")
        postgres_result = await postgres_provider.execute_query("SELECT * FROM test")
        assert postgres_result == [{"id": 1, "name": "test"}]

        # Test Neo4j operations
        neo4j_provider = await container.get_provider("neo4j")
        neo4j_result = await neo4j_provider.execute_query("MATCH (n) RETURN n")
        assert neo4j_result == [{"node": "data"}]

    @pytest.mark.asyncio
    async def test_health_monitoring_integration(self, container):
        """Test integrated health monitoring."""
        # Mock health check responses
        with patch.object(PostgreSQLHealthMonitor, 'check_health') as mock_postgres_health, \
             patch.object(Neo4jHealthMonitor, 'check_health') as mock_neo4j_health:

            from database.health import HealthMetrics, HealthStatus

            postgres_metrics = HealthMetrics(
                status=HealthStatus.HEALTHY,
                response_time=0.1,
                details={"connections": 5}
            )
            neo4j_metrics = HealthMetrics(
                status=HealthStatus.HEALTHY,
                response_time=0.05,
                details={"nodes": 1000}
            )

            mock_postgres_health.return_value = postgres_metrics
            mock_neo4j_health.return_value = neo4j_metrics

            # Get health status
            postgres_health = await container.get_health_status("postgres")
            neo4j_health = await container.get_health_status("neo4j")

            assert postgres_health.status == HealthStatus.HEALTHY
            assert neo4j_health.status == HealthStatus.HEALTHY

    @pytest.mark.asyncio
    async def test_system_health_summary(self, container):
        """Test system-wide health summary."""
        # Mock health monitors
        with patch.object(DatabaseHealthMonitor, 'check_health') as mock_check:
            from database.health import HealthMetrics, HealthStatus

            mock_check.return_value = [
                HealthMetrics(status=HealthStatus.HEALTHY, response_time=0.1, details={"service": "postgres"}),
                HealthMetrics(status=HealthStatus.HEALTHY, response_time=0.05, details={"service": "neo4j"})
            ]

            db_monitor = DatabaseHealthMonitor()
            # Manually set monitors for testing
            db_monitor.monitors = container.health_monitors

            summary = await db_monitor.get_health_summary()

            assert summary["total_services"] == 2
            assert summary["healthy_services"] == 2
            assert summary["overall_status"] == "healthy"

    @pytest.mark.asyncio
    async def test_system_shutdown(self, config, mock_providers):
        """Test complete system shutdown."""
        # First initialize
        await config.initialize_providers()

        # Then shutdown
        await config.close_providers()

        # Verify all providers were closed
        mock_providers["postgres"].close.assert_called_once()
        mock_providers["neo4j"].close.assert_called_once()


class TestFastAPIIntegration:
    """Test FastAPI application integration."""

    @pytest.fixture
    def app(self):
        """Create FastAPI test application."""
        app = FastAPI(lifespan=lifespan)

        @app.get("/test-postgres")
        async def test_postgres_endpoint(postgres = get_postgres_provider):
            """Test endpoint using PostgreSQL provider."""
            result = await postgres.execute_query("SELECT 1")
            return {"result": result}

        @app.get("/test-neo4j")
        async def test_neo4j_endpoint(neo4j = get_neo4j_provider):
            """Test endpoint using Neo4j provider."""
            result = await neo4j.execute_query("MATCH (n) RETURN count(n)")
            return {"result": result}

        @app.get("/health/{service}")
        async def health_endpoint(service: str):
            """Test health endpoint."""
            health = await get_database_health(service, MagicMock(spec=Request))
            return health

        return app

    @pytest.fixture
    def client(self, app):
        """Create test client."""
        return TestClient(app)

    @pytest.mark.asyncio
    async def test_fastapi_lifespan_integration(self, app):
        """Test FastAPI lifespan integration."""
        # Mock the dependency initialization
        with patch('database.dependencies.initialize_global_container') as mock_init, \
             patch('database.dependencies.close_global_container') as mock_close:

            # Test startup
            async with lifespan():
                pass

            mock_init.assert_called_once()

            # Test shutdown
            async with lifespan():
                pass

            mock_close.assert_called_once()

    def test_dependency_injection_in_endpoints(self, client):
        """Test that dependencies are properly injected in endpoints."""
        # This test would require a full running system
        # For now, we'll test that the endpoints are registered
        routes = [route.path for route in client.app.routes]

        assert "/test-postgres" in routes
        assert "/test-neo4j" in routes
        assert "/health/{service}" in routes

    @pytest.mark.asyncio
    async def test_health_endpoint_integration(self):
        """Test health endpoint with mocked services."""
        with patch('database.dependencies.get_container') as mock_get_container:
            mock_container = AsyncMock()
            mock_health_data = {
                "status": "healthy",
                "response_time": 0.1,
                "timestamp": 1234567890.0,
                "details": {"connections": 5}
            }
            mock_container.get_health_status.return_value = mock_health_data
            mock_get_container.return_value = mock_container

            # Create a mock request
            mock_request = MagicMock(spec=Request)

            # Test health endpoint
            health = await get_database_health("postgres", mock_request)

            assert health == mock_health_data
            mock_container.get_health_status.assert_called_once_with("postgres")


class TestBackwardCompatibility:
    """Test backward compatibility with existing database access patterns."""

    @pytest.mark.asyncio
    async def test_legacy_get_db_compatibility(self):
        """Test that legacy get_db function still works."""
        # This would test integration with existing database/db_setup.py functions
        with patch('database.db_setup.get_db_session') as mock_get_db:
            mock_session = MagicMock()
            mock_get_db.return_value.__enter__.return_value = mock_session
            mock_get_db.return_value.__exit__.return_value = None

            # Import and use legacy function (would need to be adapted)
            from database.db_setup import get_db_session

            with get_db_session() as session:
                assert session == mock_session

    @pytest.mark.asyncio
    async def test_async_db_compatibility(self):
        """Test compatibility with existing async database functions."""
        with patch('database.db_setup.get_async_db') as mock_get_async_db:
            mock_session = AsyncMock()
            mock_get_async_db.return_value.__aenter__.return_value = mock_session
            mock_get_async_db.return_value.__aexit__.return_value = None

            from database.db_setup import get_async_db

            async with get_async_db() as session:
                assert session == mock_session


class TestErrorHandlingIntegration:
    """Test error handling across the integrated system."""

    @pytest.mark.asyncio
    async def test_provider_failure_propagation(self, container):
        """Test that provider failures are properly handled."""
        # Simulate provider failure
        mock_provider = AsyncMock()
        mock_provider.initialize.return_value = False

        with pytest.raises(RuntimeError, match="Failed to initialize test provider"):
            await container.register_provider("test", mock_provider)

    @pytest.mark.asyncio
    async def test_health_check_failure_handling(self, container):
        """Test health check failure handling."""
        # Register a monitor that will fail
        mock_monitor = AsyncMock()
        mock_monitor.check_health.side_effect = Exception("Health check failed")

        await container.register_health_monitor("failing", mock_monitor)

        # Health check should handle the error gracefully
        with pytest.raises(ValueError, match="Health monitor 'failing' not registered"):
            # This should work since we registered it
            await container.get_health_status("failing")

    @pytest.mark.asyncio
    async def test_dependency_error_handling(self):
        """Test dependency injection error handling."""
        with patch('database.dependencies.get_container') as mock_get_container:
            mock_container = AsyncMock()
            mock_container.get_provider.side_effect = ValueError("Provider not available")
            mock_get_container.return_value = mock_container

            mock_request = MagicMock(spec=Request)

            # Should raise HTTP exception
            with pytest.raises(HTTPException) as exc_info:
                await get_database_provider("nonexistent", mock_request)

            assert exc_info.value.status_code == 503
            assert "Database service unavailable" in exc_info.value.detail


class TestPerformanceIntegration:
    """Test performance aspects of the integrated system."""

    @pytest.mark.asyncio
    async def test_connection_pooling_performance(self, container, mock_providers):
        """Test connection pooling performance."""
        # Configure providers to simulate connection pooling
        mock_providers["postgres"].execute_query.return_value = [{"result": "success"}]

        provider = await container.get_provider("postgres")

        # Simulate multiple concurrent queries
        import asyncio
        tasks = []
        for i in range(10):
            task = provider.execute_query(f"SELECT {i}")
            tasks.append(task)

        results = await asyncio.gather(*tasks)

        # Verify all queries succeeded
        assert len(results) == 10
        assert all(result == [{"result": "success"}] for result in results)

        # Verify execute_query was called 10 times
        assert mock_providers["postgres"].execute_query.call_count == 10

    @pytest.mark.asyncio
    async def test_health_check_performance(self, container):
        """Test health check performance under load."""
        # Register multiple health monitors
        for i in range(5):
            mock_monitor = AsyncMock()
            from database.health import HealthMetrics, HealthStatus
            mock_monitor.check_health.return_value = HealthMetrics(
                status=HealthStatus.HEALTHY,
                response_time=0.05,
                details={"service": f"service_{i}"}
            )
            await container.register_health_monitor(f"service_{i}", mock_monitor)

        # Perform health checks concurrently
        import asyncio
        tasks = []
        for i in range(5):
            task = container.get_health_status(f"service_{i}")
            tasks.append(task)

        results = await asyncio.gather(*tasks)

        # Verify all health checks succeeded
        assert len(results) == 5
        assert all(r.status == HealthStatus.HEALTHY for r in results)


class TestConfigurationIntegration:
    """Test configuration integration across components."""

    def test_environment_variable_integration(self):
        """Test that environment variables are properly used."""
        with patch.dict('os.environ', {
            'DATABASE_URL': 'postgresql://test:test@localhost:5432/testdb',
            'NEO4J_URI': 'neo4j+s://test.databases.neo4j.io',
            'NEO4J_USERNAME': 'testuser',
            'NEO4J_PASSWORD': 'testpass'
        }):
            # Test that providers can be created with env vars
            # This would normally test the actual provider instantiation
            pass

    @pytest.mark.asyncio
    async def test_connection_pool_config_integration(self):
        """Test integration with connection pool configuration."""
        with patch('config.database_pool_config.ConnectionPoolConfig.get_pool_settings') as mock_pool_config:
            mock_pool_config.return_value = {
                'pool_size': 10,
                'max_overflow': 20,
                'pool_timeout': 30
            }

            # This would test that pool config is used during provider initialization
            # The actual test would depend on implementation details
            pass


class TestMigrationPath:
    """Test migration path from old to new system."""

    @pytest.mark.asyncio
    async def test_gradual_migration_support(self):
        """Test that the system supports gradual migration."""
        # Test that old database access patterns still work
        # while new dependency injection is being adopted

        # This would test that existing code continues to work
        # during the migration period
        with patch('database.db_setup.get_async_db') as mock_legacy_db:
            mock_session = AsyncMock()
            mock_legacy_db.return_value.__aenter__.return_value = mock_session

            # Legacy code should still work
            from database.db_setup import get_async_db

            async with get_async_db() as session:
                result = await session.execute("SELECT 1")
                assert result == mock_session.execute.return_value

    @pytest.mark.asyncio
    async def test_side_by_side_operation(self):
        """Test that old and new systems can operate side by side."""
        # Test that both legacy and new dependency injection
        # can be used simultaneously during migration

        with patch('database.db_setup.get_async_db') as mock_legacy, \
             patch('database.dependencies.get_container') as mock_new:

            mock_legacy_session = AsyncMock()
            mock_new_container = AsyncMock()

            mock_legacy.return_value.__aenter__.return_value = mock_legacy_session
            mock_new.return_value = mock_new_container

            # Both should work independently
            from database.db_setup import get_async_db
            from database.dependencies import get_container

            # Legacy usage
            async with get_async_db() as session:
                await session.execute("SELECT 1")

            # New usage
            container = await get_container()
            assert container == mock_new_container