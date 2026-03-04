"""
Unit tests for database/providers.py

Tests the DatabaseProvider interface and concrete implementations
for PostgreSQL and Neo4j database services.
"""
import pytest
import asyncio
from unittest.mock import AsyncMock, MagicMock, patch
from abc import ABC
from typing import Dict, Any, Optional, List

# Import the modules we'll be testing (will be created later)
from database.providers import (
    DatabaseProvider,
    PostgreSQLProvider,
    Neo4jProvider,
    DatabaseConfig,
    ConnectionHealth,
    DatabaseError
)


class TestDatabaseProvider:
    """Test the abstract DatabaseProvider interface."""

    def test_abstract_methods(self):
        """Test that DatabaseProvider defines required abstract methods."""
        # This should raise TypeError since we can't instantiate abstract class
        with pytest.raises(TypeError):
            DatabaseProvider()

    @pytest.mark.asyncio
    async def test_abstract_method_signatures(self):
        """Test that abstract methods have correct signatures."""
        # Create a concrete implementation for testing
        class ConcreteProvider(DatabaseProvider):
            async def initialize(self) -> bool:
                return True

            async def close(self) -> None:
                pass

            async def health_check(self) -> ConnectionHealth:
                return ConnectionHealth(status="healthy", details={})

            async def execute_query(self, query: str, params: Optional[Dict[str, Any]] = None) -> List[Dict[str, Any]]:
                return []

            async def execute_transaction(self, queries: List[Dict[str, Any]]) -> bool:
                return True

        provider = ConcreteProvider()
        assert await provider.initialize() is True
        assert await provider.health_check() == ConnectionHealth(status="healthy", details={})
        assert await provider.execute_query("SELECT 1") == []
        assert await provider.execute_transaction([]) is True


class TestPostgreSQLProvider:
    """Test the PostgreSQL database provider implementation."""

    @pytest.fixture
    def mock_session(self):
        """Create a mock async session."""
        session = AsyncMock()
        session.execute = AsyncMock()
        session.commit = AsyncMock()
        session.rollback = AsyncMock()
        session.close = AsyncMock()
        return session

    @pytest.fixture
    def mock_engine(self):
        """Create a mock async engine."""
        engine = AsyncMock()
        engine.connect = AsyncMock()
        return engine

    @pytest.fixture
    def provider(self, mock_engine):
        """Create PostgreSQL provider with mocked engine."""
        with patch('database.providers.create_async_engine', return_value=mock_engine):
            provider = PostgreSQLProvider()
            return provider

    def test_initialization(self, provider):
        """Test provider initialization."""
        assert provider.engine is not None
        assert provider.session_factory is not None

    @pytest.mark.asyncio
    async def test_initialize_success(self, provider, mock_engine):
        """Test successful initialization."""
        mock_connection = AsyncMock()
        mock_engine.connect.return_value.__aenter__.return_value = mock_connection
        mock_connection.execute.return_value = None

        result = await provider.initialize()
        assert result is True
        mock_engine.connect.assert_called_once()

    @pytest.mark.asyncio
    async def test_initialize_failure(self, provider, mock_engine):
        """Test initialization failure."""
        mock_engine.connect.side_effect = Exception("Connection failed")

        result = await provider.initialize()
        assert result is False

    @pytest.mark.asyncio
    async def test_health_check_healthy(self, provider, mock_session):
        """Test health check when database is healthy."""
        # Mock the session context manager
        provider.session_factory = MagicMock()
        provider.session_factory.return_value.__aenter__.return_value = mock_session

        # Mock successful query execution
        mock_result = MagicMock()
        mock_result.fetchall.return_value = [(1,)]
        mock_session.execute.return_value = mock_result

        health = await provider.health_check()

        assert health.status == "healthy"
        assert "response_time" in health.details
        assert health.details["connection_count"] >= 0

    @pytest.mark.asyncio
    async def test_health_check_unhealthy(self, provider, mock_session):
        """Test health check when database is unhealthy."""
        provider.session_factory = MagicMock()
        provider.session_factory.return_value.__aenter__.side_effect = Exception("Connection failed")

        health = await provider.health_check()

        assert health.status == "unhealthy"
        assert "error" in health.details

    @pytest.mark.asyncio
    async def test_execute_query_success(self, provider, mock_session):
        """Test successful query execution."""
        provider.session_factory = MagicMock()
        provider.session_factory.return_value.__aenter__.return_value = mock_session

        mock_result = MagicMock()
        mock_result.fetchall.return_value = [{"id": 1, "name": "test"}]
        mock_session.execute.return_value = mock_result

        result = await provider.execute_query("SELECT * FROM test_table")

        assert result == [{"id": 1, "name": "test"}]
        mock_session.execute.assert_called_once()

    @pytest.mark.asyncio
    async def test_execute_query_with_params(self, provider, mock_session):
        """Test query execution with parameters."""
        provider.session_factory = MagicMock()
        provider.session_factory.return_value.__aenter__.return_value = mock_session

        mock_result = MagicMock()
        mock_result.fetchall.return_value = [{"id": 1}]
        mock_session.execute.return_value = mock_result

        params = {"user_id": 123}
        result = await provider.execute_query("SELECT * FROM users WHERE id = :user_id", params)

        assert result == [{"id": 1}]
        # Verify params were passed correctly
        call_args = mock_session.execute.call_args
        assert call_args[1]["user_id"] == 123

    @pytest.mark.asyncio
    async def test_execute_transaction_success(self, provider, mock_session):
        """Test successful transaction execution."""
        provider.session_factory = MagicMock()
        provider.session_factory.return_value.__aenter__.return_value = mock_session

        queries = [
            {"query": "INSERT INTO test (name) VALUES (:name)", "params": {"name": "test1"}},
            {"query": "UPDATE test SET name = :name WHERE id = :id", "params": {"name": "test2", "id": 1}}
        ]

        result = await provider.execute_transaction(queries)

        assert result is True
        assert mock_session.execute.call_count == 2
        mock_session.commit.assert_called_once()

    @pytest.mark.asyncio
    async def test_execute_transaction_failure(self, provider, mock_session):
        """Test transaction execution failure."""
        provider.session_factory = MagicMock()
        provider.session_factory.return_value.__aenter__.return_value = mock_session

        mock_session.execute.side_effect = Exception("Query failed")

        queries = [{"query": "INSERT INTO test (name) VALUES (:name)", "params": {"name": "test"}}]

        result = await provider.execute_transaction(queries)

        assert result is False
        mock_session.rollback.assert_called_once()

    @pytest.mark.asyncio
    async def test_close(self, provider, mock_engine):
        """Test provider cleanup."""
        await provider.close()

        mock_engine.dispose.assert_called_once()


class TestNeo4jProvider:
    """Test the Neo4j database provider implementation."""

    @pytest.fixture
    def mock_driver(self):
        """Create a mock Neo4j driver."""
        driver = MagicMock()
        driver.session.return_value.__enter__.return_value = MagicMock()
        driver.session.return_value.__exit__.return_value = None
        return driver

    @pytest.fixture
    def provider(self, mock_driver):
        """Create Neo4j provider with mocked driver."""
        with patch('database.providers.GraphDatabase.driver', return_value=mock_driver):
            provider = Neo4jProvider()
            return provider

    def test_initialization(self, provider):
        """Test provider initialization."""
        assert provider.driver is not None
        assert provider.executor is not None

    @pytest.mark.asyncio
    async def test_initialize_success(self, provider, mock_driver):
        """Test successful initialization."""
        # Mock successful connection test
        with patch.object(provider, '_verify_connection', return_value=True):
            with patch.object(provider, '_initialize_schema'):
                result = await provider.initialize()
                assert result is True

    @pytest.mark.asyncio
    async def test_initialize_connection_failure(self, provider):
        """Test initialization failure due to connection issues."""
        with patch.object(provider, '_verify_connection', return_value=False):
            result = await provider.initialize()
            assert result is False

    @pytest.mark.asyncio
    async def test_verify_connection_success(self, provider, mock_driver):
        """Test successful connection verification."""
        mock_session = MagicMock()
        mock_driver.session.return_value.__enter__.return_value = mock_session

        mock_result = MagicMock()
        mock_result.single.return_value = MagicMock()
        mock_result.single.return_value.__getitem__.return_value = 1
        mock_session.run.return_value = mock_result

        result = await provider._verify_connection()
        assert result is True

    @pytest.mark.asyncio
    async def test_verify_connection_failure(self, provider, mock_driver):
        """Test connection verification failure."""
        mock_driver.session.side_effect = Exception("Connection failed")

        result = await provider._verify_connection()
        assert result is False

    @pytest.mark.asyncio
    async def test_health_check_healthy(self, provider, mock_driver):
        """Test health check when Neo4j is healthy."""
        mock_session = MagicMock()
        mock_driver.session.return_value.__enter__.return_value = mock_session

        mock_result = MagicMock()
        mock_result.single.return_value = MagicMock()
        mock_result.single.return_value.__getitem__.return_value = 1
        mock_session.run.return_value = mock_result

        health = await provider.health_check()

        assert health.status == "healthy"
        assert "node_count" in health.details

    @pytest.mark.asyncio
    async def test_execute_query_success(self, provider, mock_driver):
        """Test successful Cypher query execution."""
        mock_session = MagicMock()
        mock_driver.session.return_value.__enter__.return_value = mock_session

        mock_result = MagicMock()
        mock_record = MagicMock()
        mock_record.data.return_value = {"name": "test", "value": 42}
        mock_result.__iter__.return_value = [mock_record]
        mock_session.run.return_value = mock_result

        result = await provider.execute_query("MATCH (n) RETURN n.name as name, n.value as value")

        assert result == [{"name": "test", "value": 42}]

    @pytest.mark.asyncio
    async def test_execute_transaction_success(self, provider, mock_driver):
        """Test successful transaction execution."""
        mock_session = MagicMock()
        mock_driver.session.return_value.__enter__.return_value = mock_session

        mock_tx = MagicMock()
        mock_session.begin_transaction.return_value.__enter__.return_value = mock_tx

        queries = [
            {"query": "CREATE (n:Test {name: $name})", "params": {"name": "test1"}},
            {"query": "MATCH (n:Test {name: $name}) SET n.value = $value", "params": {"name": "test1", "value": 100}}
        ]

        result = await provider.execute_transaction(queries)

        assert result is True
        assert mock_tx.run.call_count == 2
        mock_tx.commit.assert_called_once()

    @pytest.mark.asyncio
    async def test_close(self, provider, mock_driver):
        """Test provider cleanup."""
        await provider.close()

        mock_driver.close.assert_called_once()


class TestDatabaseConfig:
    """Test the database configuration class."""

    def test_config_initialization(self):
        """Test DatabaseConfig initialization."""
        config = DatabaseConfig()
        assert config.postgres_config is not None
        assert config.neo4j_config is not None

    @pytest.mark.asyncio
    async def test_get_provider_postgres(self):
        """Test getting PostgreSQL provider."""
        config = DatabaseConfig()

        with patch('database.providers.PostgreSQLProvider') as mock_provider_class:
            mock_provider = AsyncMock()
            mock_provider_class.return_value = mock_provider
            mock_provider.initialize.return_value = True

            provider = await config.get_provider("postgres")

            assert provider == mock_provider
            mock_provider.initialize.assert_called_once()

    @pytest.mark.asyncio
    async def test_get_provider_neo4j(self):
        """Test getting Neo4j provider."""
        config = DatabaseConfig()

        with patch('database.providers.Neo4jProvider') as mock_provider_class:
            mock_provider = AsyncMock()
            mock_provider_class.return_value = mock_provider
            mock_provider.initialize.return_value = True

            provider = await config.get_provider("neo4j")

            assert provider == mock_provider
            mock_provider.initialize.assert_called_once()

    @pytest.mark.asyncio
    async def test_get_provider_invalid_type(self):
        """Test getting provider with invalid type."""
        config = DatabaseConfig()

        with pytest.raises(ValueError, match="Unsupported database type"):
            await config.get_provider("invalid_db")

    @pytest.mark.asyncio
    async def test_get_provider_initialization_failure(self):
        """Test provider initialization failure."""
        config = DatabaseConfig()

        with patch('database.providers.PostgreSQLProvider') as mock_provider_class:
            mock_provider = AsyncMock()
            mock_provider_class.return_value = mock_provider
            mock_provider.initialize.return_value = False

            with pytest.raises(RuntimeError, match="Failed to initialize postgres provider"):
                await config.get_provider("postgres")


class TestConnectionHealth:
    """Test the ConnectionHealth data class."""

    def test_health_creation(self):
        """Test ConnectionHealth creation."""
        health = ConnectionHealth(status="healthy", details={"response_time": 0.1})

        assert health.status == "healthy"
        assert health.details == {"response_time": 0.1}

    def test_health_with_timestamp(self):
        """Test ConnectionHealth with timestamp."""
        import time
        timestamp = time.time()

        health = ConnectionHealth(
            status="healthy",
            details={"response_time": 0.1},
            timestamp=timestamp
        )

        assert health.timestamp == timestamp

    def test_health_string_representation(self):
        """Test ConnectionHealth string representation."""
        health = ConnectionHealth(status="healthy", details={"response_time": 0.1})

        str_repr = str(health)
        assert "healthy" in str_repr
        assert "response_time" in str_repr


class TestDatabaseError:
    """Test the DatabaseError exception class."""

    def test_error_creation(self):
        """Test DatabaseError creation."""
        error = DatabaseError("Connection failed", {"code": "CONNECTION_ERROR"})

        assert str(error) == "Connection failed"
        assert error.details == {"code": "CONNECTION_ERROR"}

    def test_error_with_cause(self):
        """Test DatabaseError with underlying cause."""
        cause = ValueError("Invalid value")
        error = DatabaseError("Database operation failed", cause=cause)

        assert error.cause == cause
        assert isinstance(error.cause, ValueError)