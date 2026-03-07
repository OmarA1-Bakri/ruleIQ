"""
import logging


logger = logging.getLogger(__name__)
Database initialization script for ComplianceGPT (Asynchronous)

This script creates all database tables and optionally populates them with default data.
Run this script after setting up your DATABASE_URL environment variable.
"""

import asyncio
import os
import sys
from dotenv import load_dotenv
from sqlalchemy import select

load_dotenv()
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from config.logging_config import get_logger, setup_logging
from database.db_setup import get_async_db
from services.framework_service import initialize_default_frameworks
from typing import Optional

setup_logging()
logger = get_logger(__name__)


async def create_tables() -> Optional[bool]:
    """Run Alembic migrations to create/update database tables."""
    logger.info("Running database migrations...")
    try:
        import subprocess
        import sys

        result = subprocess.run(
            [sys.executable, "-m", "alembic", "upgrade", "head"], capture_output=True, text=True
        )
        if result.returncode != 0:
            logger.error("Alembic migration failed: %s" % result.stderr)
            return False
        logger.info("Database migrations applied successfully.")
        return True
    except Exception as e:
        logger.error("Error running migrations: %s" % e, exc_info=True)
        return False


async def populate_default_data() -> Optional[bool]:
    """Populate database with default frameworks and data asynchronously."""
    logger.info("Populating default data...")
    try:
        async for db in get_async_db():
            await initialize_default_frameworks(db)
        logger.info("Default frameworks initialized successfully.")
        return True
    except Exception as e:
        logger.error("Error populating default data: %s" % e, exc_info=True)
        return False


async def test_connection() -> Optional[bool]:
    """Test database connection asynchronously."""
    logger.info("Testing database connection...")
    try:
        async for db in get_async_db():
            await db.execute(select(1))
        logger.info("Database connection successful.")
        return True
    except Exception as e:
        logger.error("Database connection failed: %s" % e, exc_info=True)
        return False


async def main() -> bool:
    """Main asynchronous initialization function."""
    logger.info("ComplianceGPT Database Initialization")
    logger.info("========================================")
    database_url = os.getenv("DATABASE_URL")
    if not database_url:
        logger.error(
            "DATABASE_URL environment variable not set. Please set it in your .env file.",
        )
        return False
    logger.info("Database URL: %s" % database_url)
    if not await test_connection():
        return False
    if not await create_tables():
        return False
    if not await populate_default_data():
        return False
    logger.info("Database initialization completed successfully!")
    return True


if __name__ == "__main__":
    success = asyncio.run(main())
    sys.exit(0 if success else 1)
