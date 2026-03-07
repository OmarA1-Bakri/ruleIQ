"""
import logging


logger = logging.getLogger(__name__)
Manual migration script to create integration and evidence tables
Run this script to create the required database tables for the integration system
"""

import asyncio
from config.logging_config import get_logger
from typing import Optional

logger = get_logger(__name__)


async def create_integration_tables() -> Optional[bool]:
    """Create all integration-related tables"""
    try:
        logger.warning(
            "create_integration_tables is deprecated. Use 'alembic upgrade head' instead.",
        )
        return True
    except Exception as e:
        logger.error("Failed to create integration tables: %s" % e)
        raise


if __name__ == "__main__":
    asyncio.run(create_integration_tables())
