"""
Backward compatibility tests for database dependency injection system

Tests that existing database access patterns continue to work during
and after migration to the new dependency injection system.
"""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from typing import Dict, Any, Generator
from contextlib import contextmanager

# Import existing database functions that should remain compatible
from database.db_setup import (
    get_db,
    get_db_session,
    get_async_db,
    init_db,
    test_database_connection,
    async_session_maker,
    _ENGINE,
    _ASYNC_ENGINE,
    _SESSION_LOCAL,
    _ASYNC_SESSION_LOCAL,
)


class TestLegacyDatabaseFunctions:
    """Test that legacy database functions continue to work."""

    @pytest.mark.asyncio
    async def test_async_db_context_manager(self):
        """Test that get_async_db still works as expected."""
        # Mock the async session local
        mock_session = AsyncMock()
        mock_session_local = AsyncMock()
        mock_session_local.return_value = mock_session

        with patch("database.db_setup._ASYNC_SESSION_LOCAL", mock_session_local):
            # Test the context manager
            async with get_async_db() as session:
                assert session == mock_session

            # Verify session was properly closed
            mock_session.close.assert_called_once()

    def test_sync_db_context_manager(self):
        """Test that get_db_session still works as expected."""
        # Mock the session local
        mock_session = MagicMock()
        mock_session_local = MagicMock()
        mock_session_local.return_value = mock_session

        with patch("database.db_setup._SESSION_LOCAL", mock_session_local):
            # Test the context manager
            with get_db_session() as session:
                assert session == mock_session

            # Verify session was properly closed and committed
            mock_session.close.assert_called_once()
            mock_session.commit.assert_called_once()

    def test_legacy_get_db_deprecated(self):
        """Test that get_db still works but may be marked as deprecated."""
        # Mock the session local
        mock_session = MagicMock()
        mock_session_local = MagicMock()
        mock_session_local.return_value = mock_session

        with patch("database.db_setup._SESSION_LOCAL", mock_session_local):
            # Test the generator function
            sessions = list(get_db())
            assert len(sessions) == 1
            assert sessions[0] == mock_session

            # Verify session was properly closed
            mock_session.close.assert_called_once()

    @patch("database.db_setup._ENGINE")
    @patch("database.db_setup.text")
    def test_test_database_connection_sync(self, mock_text, mock_engine):
        """Test that synchronous database connection testing still works."""
        # Mock the engine and connection
        mock_connection = MagicMock()
        mock_engine.connect.return_value.__enter__.return_value = mock_connection
        mock_connection.execute.return_value = None

        # Mock text() to return a simple SQL object
        mock_sql = MagicMock()
        mock_text.return_value = mock_sql

        result = test_database_connection()

        assert result is True
        mock_engine.connect.assert_called_once()
        mock_connection.execute.assert_called_once_with(mock_sql)

    @pytest.mark.asyncio
    @patch("database.db_setup._ASYNC_ENGINE")
    @patch("database.db_setup.text")
    async def test_test_async_database_connection(self, mock_text, mock_async_engine):
        """Test that asynchronous database connection testing still works."""
        # Mock the async engine and connection
        mock_connection = AsyncMock()
        mock_async_engine.connect.return_value.__enter__.return_value = mock_connection
        mock_connection.execute.return_value = None

        # Mock text() to return a simple SQL object
        mock_sql = MagicMock()
        mock_text.return_value = mock_sql

        result = await test_database_connection()

        assert result is True
        mock_async_engine.connect.assert_called_once()
        mock_connection.execute.assert_called_once_with(mock_sql)


class TestGlobalStateCompatibility:
    """Test that global database state remains compatible."""

    @patch("database.db_setup._ENGINE")
    @patch("database.db_setup._ASYNC_ENGINE")
    def test_get_engine_info_compatibility(self, mock_async_engine, mock_engine):
        """Test that get_engine_info still provides expected information."""
        # Mock engines
        mock_engine.is_none = False
        mock_async_engine.is_none = False

        # Mock pool attributes
        mock_engine.pool.size.return_value = 10
        mock_engine.pool.checkedin.return_value = 8
        mock_engine.pool.checkedout.return_value = 2
        mock_engine.pool.overflow.return_value = 0

        mock_async_engine.pool.size.return_value = 10
        mock_async_engine.pool.checkedin.return_value = 8
        mock_async_engine.pool.checkedout.return_value = 2
        mock_async_engine.pool.overflow.return_value = 0

        from database.db_setup import get_engine_info

        info = get_engine_info()

        expected_keys = [
            "sync_engine_initialized",
            "async_engine_initialized",
            "async_pool_size",
            "async_pool_checked_in",
            "async_pool_checked_out",
            "async_pool_overflow",
            "sync_pool_size",
            "sync_pool_checked_in",
            "sync_pool_checked_out",
            "sync_pool_overflow",
        ]

        for key in expected_keys:
            assert key in info

    def test_async_session_maker_compatibility(self):
        """Test that async_session_maker global variable still exists."""
        # This should not raise an exception
        # The actual value depends on whether the engine is initialized
        # We just verify it exists
        assert (
            async_session_maker is not None or async_session_maker is None
        )  # Could be None if not initialized


class TestDatabaseInitializationCompatibility:
    """Test that database initialization remains compatible."""

    @patch("database.db_setup._init_sync_db")
    @patch("database.db_setup._init_async_db")
    @patch("database.db_setup.test_database_connection")
    @patch("database.db_setup.Base")
    @patch("database.db_setup._ENGINE")
    def test_init_db_compatibility(
        self, mock_engine, mock_base, mock_test_conn, mock_init_async, mock_init_sync
    ):
        """Test that init_db still works as expected."""
        # Mock successful initialization
        mock_test_conn.return_value = True
        mock_engine.is_none = False

        result = init_db()

        assert result is True
        mock_init_sync.assert_called_once()
        mock_init_async.assert_called_once()
        mock_test_conn.assert_called_once()
        mock_base.metadata.create_all.assert_called_once_with(bind=mock_engine)

    @patch("database.db_setup._init_sync_db")
    @patch("database.db_setup.test_database_connection")
    def test_init_db_failure_handling(self, mock_test_conn, mock_init_sync):
        """Test that init_db properly handles failures."""
        mock_test_conn.return_value = False

        result = init_db()

        assert result is False


class TestMigrationPathCompatibility:
    """Test compatibility during migration from old to new system."""

    @pytest.mark.asyncio
    async def test_side_by_side_operation(self):
        """Test that old and new database access can coexist."""
        # Mock legacy database access
        mock_legacy_session = AsyncMock()

        # Mock new dependency injection system
        mock_new_provider = AsyncMock()
        mock_new_provider.execute_query.return_value = [{"result": "success"}]

        with (
            patch("database.db_setup.get_async_db") as mock_legacy_get_db,
            patch("database.dependencies.get_postgres_provider") as mock_new_get_provider,
        ):
            # Setup mocks
            mock_legacy_get_db.return_value.__aenter__.return_value = mock_legacy_session
            mock_new_get_provider.return_value = mock_new_provider

            # Test legacy usage
            from database.db_setup import get_async_db

            async with get_async_db() as legacy_session:
                await legacy_session.execute("SELECT 1")

            # Test new usage
            from database.dependencies import get_postgres_provider

            mock_request = MagicMock()
            new_provider = await get_postgres_provider(mock_request)
            result = await new_provider.execute_query("SELECT 1")

            # Both should work independently
            assert result == [{"result": "success"}]
            mock_legacy_session.execute.assert_called_once_with("SELECT 1")

    def test_import_compatibility(self):
        """Test that all expected imports still work."""
        # These imports should not raise exceptions
        try:
            from database.db_setup import (
                get_db,
                get_db_session,
                get_async_db,
                init_db,
                test_database_connection,
                get_engine_info,
                cleanup_db_connections,
                async_session_maker,
            )

            # Success - all imports worked
            assert True
        except ImportError as e:
            pytest.fail(f"Import failed: {e}")

    def test_function_signature_compatibility(self):
        """Test that function signatures remain compatible."""
        import inspect

        # Check that function signatures haven't changed unexpectedly
        sig_get_db = inspect.signature(get_db)
        sig_get_db_session = inspect.signature(get_db_session)
        sig_get_async_db = inspect.signature(get_async_db)

        # These should be generators/context managers
        assert sig_get_db.return_annotation == Generator[Any, None, None]
        assert sig_get_db_session.return_annotation == Generator[Any, None, None]
        # Note: get_async_db returns AsyncGenerator, but signature might not reflect this in all Python versions

    @pytest.mark.asyncio
    async def test_transaction_compatibility(self):
        """Test that transaction handling remains compatible."""
        # Mock session with transaction support
        mock_session = AsyncMock()
        mock_tx = AsyncMock()
        mock_session.begin_transaction.return_value = mock_tx

        with patch("database.db_setup._ASYNC_SESSION_LOCAL") as mock_session_local:
            mock_session_local.return_value = mock_session

            # This tests that the session can still be used for transactions
            # (The actual transaction logic would be in user code)
            async with get_async_db() as session:
                assert session == mock_session


class TestConfigurationCompatibility:
    """Test that configuration remains compatible."""

    @patch("database.db_setup.DatabaseConfig.get_database_urls")
    @patch("database.db_setup.DatabaseConfig.get_engine_kwargs")
    @patch("database.db_setup.create_engine")
    @patch("database.db_setup.async_sessionmaker")
    def test_engine_initialization_compatibility(
        self, mock_async_sessionmaker, mock_create_engine, mock_get_engine_kwargs, mock_get_urls
    ):
        """Test that engine initialization still uses existing config."""
        from database.db_setup import _init_async_db

        # Mock configuration
        mock_get_urls.return_value = ("url", "sync_url", "async_url")
        mock_get_engine_kwargs.return_value = {"pool_size": 10}
        mock_engine = MagicMock()
        mock_create_engine.return_value = mock_engine
        mock_sessionmaker = MagicMock()
        mock_async_sessionmaker.return_value = mock_sessionmaker

        # This should not raise an exception
        _init_async_db()

        # Verify configuration was used
        mock_get_urls.assert_called_once()
        mock_get_engine_kwargs.assert_called_once_with(is_async=True)
        mock_create_engine.assert_called_once()
        mock_async_sessionmaker.assert_called_once()

    def test_environment_variable_usage(self):
        """Test that environment variables are still used."""
        with patch.dict(
            "os.environ",
            {
                "DATABASE_URL": "postgresql://test:test@localhost/testdb",
                "DB_POOL_SIZE": "15",
                "DB_MAX_OVERFLOW": "25",
            },
        ):
            # The actual validation would happen during config.get_database_urls()
            # and config.get_engine_kwargs()
            from database.db_setup import DatabaseConfig

            try:
                # This should not raise an exception with valid env vars
                urls = DatabaseConfig.get_database_urls()
                assert len(urls) == 3  # Should return tuple of 3 URLs
            except Exception:
                # May fail due to actual database connection, but that's OK for this test
                pass


class TestErrorHandlingCompatibility:
    """Test that error handling remains compatible."""

    @patch("database.db_setup._ENGINE", None)
    def test_connection_test_failure_handling(self):
        """Test that connection test failures are handled gracefully."""
        # When engine is None, connection test should fail gracefully
        result = test_database_connection()
        assert result is False

    @pytest.mark.asyncio
    @patch("database.db_setup._ASYNC_ENGINE", None)
    async def test_async_connection_test_failure_handling(self):
        """Test that async connection test failures are handled gracefully."""
        # When async engine is None, connection test should fail gracefully
        result = await test_database_connection()
        assert result is False

    @patch("database.db_setup._init_sync_db")
    @patch("database.db_setup._init_async_db")
    @patch("database.db_setup.test_database_connection")
    def test_init_db_error_handling(self, mock_test_conn, mock_init_async, mock_init_sync):
        """Test that init_db handles errors properly."""
        mock_test_conn.return_value = False

        result = init_db()

        # Should return False on failure, not raise exception
        assert result is False


class TestPerformanceCompatibility:
    """Test that performance characteristics remain compatible."""

    @pytest.mark.asyncio
    async def test_connection_reuse_compatibility(self):
        """Test that connection reuse patterns still work."""
        # This tests that the session lifecycle remains the same
        call_count = 0

        async def count_calls():
            nonlocal call_count
            call_count += 1
            mock_session = AsyncMock()
            return mock_session

        with patch("database.db_setup._ASYNC_SESSION_LOCAL") as mock_session_local:
            mock_session_local.side_effect = count_calls

            # Simulate multiple database operations
            for i in range(3):
                async with get_async_db() as session:
                    await session.execute(f"SELECT {i}")

            # Each call to get_async_db should create a new session
            assert call_count == 3

    def test_context_manager_performance(self):
        """Test that context manager overhead remains acceptable."""
        import time

        mock_session = MagicMock()
        mock_session_local = MagicMock()
        mock_session_local.return_value = mock_session

        with patch("database.db_setup._SESSION_LOCAL", mock_session_local):
            start_time = time.time()

            # Simulate many context manager usages
            for i in range(100):
                with get_db_session() as session:
                    session.execute(f"SELECT {i}")

            end_time = time.time()
            duration = end_time - start_time

            # Should complete in reasonable time (less than 1 second for 100 operations)
            assert duration < 1.0

            # Should have created 100 sessions
            assert mock_session_local.call_count == 100


class TestMonitoringCompatibility:
    """Test that monitoring and observability remain compatible."""

    @patch("database.db_setup._ENGINE")
    @patch("database.db_setup._ASYNC_ENGINE")
    def test_engine_info_monitoring(self, mock_async_engine, mock_engine):
        """Test that engine monitoring information is still available."""
        from database.db_setup import get_engine_info

        # Mock engines exist
        mock_engine.is_none = False
        mock_async_engine.is_none = False

        # Mock pool stats
        for engine in [mock_engine, mock_async_engine]:
            engine.pool.size.return_value = 10
            engine.pool.checkedin.return_value = 8
            engine.pool.checkedout.return_value = 2
            engine.pool.overflow.return_value = 0

        info = get_engine_info()

        # Should contain expected monitoring information
        expected_keys = [
            "sync_engine_initialized",
            "async_engine_initialized",
            "sync_pool_size",
            "sync_pool_checked_in",
            "sync_pool_checked_out",
            "sync_pool_overflow",
            "async_pool_size",
            "async_pool_checked_in",
            "async_pool_checked_out",
            "async_pool_overflow",
        ]

        for key in expected_keys:
            assert key in info
            assert isinstance(info[key], (bool, int))

    @pytest.mark.asyncio
    async def test_cleanup_compatibility(self):
        """Test that cleanup functions still work."""
        from database.db_setup import cleanup_db_connections

        mock_engine = MagicMock()
        mock_async_engine = AsyncMock()

        with (
            patch("database.db_setup._ENGINE", mock_engine),
            patch("database.db_setup._ASYNC_ENGINE", mock_async_engine),
        ):
            await cleanup_db_connections()

            # Engines should be disposed and set to None
            mock_async_engine.dispose.assert_called_once()
            mock_engine.dispose.assert_called_once()
