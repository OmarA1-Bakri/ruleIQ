#!/usr/bin/env python3
"""
Test script to verify database initialization works correctly.
"""

import asyncio
import logging
import sys
import os

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from database import (
    init_db,
    test_database_connection,
    get_engine_info,
    cleanup_db_connections,
)

# Configure logging for testing
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)

logger = logging.getLogger(__name__)


def test_sync_initialization():
    """Test synchronous database initialization."""
    print("=" * 50)
    print("Testing Database Initialization")
    print("=" * 50)

    try:
        # Test init_db function
        logger.info("Testing init_db() function...")
        success = init_db()

        if success:
            logger.info("✅ init_db() completed successfully")

            # Test database connection
            logger.info("Testing database connection...")
            conn_success = test_database_connection()

            if conn_success:
                logger.info("✅ Database connection test passed")
            else:
                logger.error("❌ Database connection test failed")
                return False

            # Show engine info
            logger.info("Engine info: %s", get_engine_info())
            return True
        else:
            logger.error("❌ init_db() failed")
            return False

    except Exception as e:
        logger.error("❌ Error during initialization: %s", e, exc_info=True)
        return False


async def test_async_operations():
    """Test async database operations."""
    print("=" * 50)
    print("Testing Async Database Operations")
    print("=" * 50)

    try:
        from database.init_db import create_tables

        # Test Alembic migration-based table creation
        logger.info("Testing Alembic table creation...")
        async_table_success = await create_tables()

        if async_table_success:
            logger.info("✅ Async table creation test passed")
        else:
            logger.error("❌ Async table creation test failed")
            return False

        return True

    except Exception as e:
        logger.error("❌ Error during async testing: %s", e, exc_info=True)
        return False


async def main():
    """Main test function."""
    print("ruleIQ Database Initialization Test")
    print("====================================")

    # Check if DATABASE_URL is set
    db_url = os.getenv("DATABASE_URL")
    if not db_url:
        print("❌ DATABASE_URL environment variable not set")
        print("Please set DATABASE_URL in your .env file or environment")
        return False

    print(f"Using database: {db_url}")

    # Test sync initialization
    sync_success = test_sync_initialization()

    # Test async operations
    async_success = await test_async_operations()

    # Cleanup
    logger.info("Cleaning up database connections...")
    await cleanup_db_connections()

    # Final result
    print("=" * 50)
    print("Test Results")
    print("=" * 50)

    if sync_success and async_success:
        print("✅ All tests passed! Database initialization is working correctly.")
        return True
    else:
        print("❌ Some tests failed. Check the logs above for details.")
        return False


if __name__ == "__main__":
    success = asyncio.run(main())
    sys.exit(0 if success else 1)
