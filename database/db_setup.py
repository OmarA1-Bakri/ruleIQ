"""

Database setup for ruleIQ, including synchronous and asynchronous
configurations. Provides comprehensive database initialization and
management utilities.
"""

import os
import logging
from typing import AsyncGenerator, Dict, Any, Generator
from contextlib import contextmanager
from dotenv import load_dotenv
from sqlalchemy import create_engine, text, MetaData, Engine
from sqlalchemy.ext.asyncio import (
    AsyncSession,
    create_async_engine,
    async_sessionmaker,
    AsyncEngine,
)
from sqlalchemy.orm import declarative_base, sessionmaker, Session

load_dotenv(".env.local", override=True)
load_dotenv(".env", override=False)
logger = logging.getLogger(__name__)
_ENGINE: Engine | None = None
_SESSION_LOCAL: sessionmaker[Session] | None = None
_ASYNC_ENGINE: AsyncEngine | None = None
_ASYNC_SESSION_LOCAL: async_sessionmaker[AsyncSession] | None = None
naming_convention = {
    "ix": "ix_%(column_0_label)s",
    "uq": "uq_%(table_name)s_%(column_0_name)s",
    "ck": "ck_%(table_name)s_%(constraint_name)s",
    "fk": "fk_%(table_name)s_%(column_0_name)s_%(referred_table_name)s",
    "pk": "pk_%(table_name)s",
}
metadata = MetaData(naming_convention=naming_convention)
Base = declarative_base(metadata=metadata)


class DatabaseConfig:
    """Database configuration class for managing connection settings."""

    @staticmethod
    def validate_environment() -> None:
        """Validate that required environment variables are set."""
        required_vars = ["DATABASE_URL"]
        missing_vars = []
        for var in required_vars:
            if not os.getenv(var):
                missing_vars.append(var)
        if missing_vars:
            error_msg = f"""Missing required environment variables: {", ".join(missing_vars)}
Please copy env.template to .env.local and configure the variables."""
            logger.error(error_msg)
            raise OSError(error_msg)
        if os.path.exists(".env.local"):
            logger.info("Loaded configuration from .env.local")
        elif os.path.exists(".env"):
            logger.info("Loaded configuration from .env")
        else:
            logger.info("Using system environment variables")

    @staticmethod
    def get_database_urls() -> tuple[str, str, str]:
        """
        Retrieves and processes DATABASE_URL from environment variables.
        Returns tuple of (original_url, sync_url, async_url)
        """
        DatabaseConfig.validate_environment()
        db_url = os.getenv("DATABASE_URL")
        if not db_url:
            error_msg = (
                "DATABASE_URL environment variable not set. Please set it in your .env file or environment.",
            )
            logger.error(error_msg)
            raise OSError(error_msg)
        safe_url = db_url.split("@")[1] if "@" in db_url else db_url
        logger.info("Connecting to database: %s" % safe_url)
        sync_db_url = db_url
        if "+asyncpg" in sync_db_url:
            sync_db_url = sync_db_url.replace("+asyncpg", "+psycopg2")
        elif "postgresql://" in sync_db_url and "+psycopg2" not in sync_db_url:
            sync_db_url = sync_db_url.replace("postgresql://", "postgresql+psycopg2://", 1)
        async_db_url = db_url
        if "+asyncpg" not in async_db_url:
            async_db_url_candidate = async_db_url.replace("+psycopg2", "+asyncpg")
            if (
                "postgresql://" in async_db_url_candidate
                and "+asyncpg" not in async_db_url_candidate
            ):
                async_db_url = async_db_url_candidate.replace(
                    "postgresql://", "postgresql+asyncpg://", 1
                )
            elif "+asyncpg" in async_db_url_candidate:
                async_db_url = async_db_url_candidate
            elif (
                "postgresql://" in async_db_url
                and "+psycopg2" not in async_db_url
                and "+asyncpg" not in async_db_url
            ):
                async_db_url = async_db_url.replace("postgresql://", "postgresql+asyncpg://", 1)
        if "sslmode=require" in async_db_url:
            from urllib.parse import urlparse, urlunparse, parse_qs, urlencode

            parts = urlparse(async_db_url)
            query_params = parse_qs(parts.query)
            query_params.pop("sslmode", None)
            query_params.pop("channel_binding", None)
            new_query = urlencode(query_params, doseq=True)
            async_db_url = urlunparse(parts._replace(query=new_query))
        return db_url, sync_db_url, async_db_url

    @staticmethod
    def get_engine_kwargs(is_async: bool = False) -> Dict[str, Any]:
        """Get optimized engine configuration based on sync/async mode."""
        # Import the enhanced pool configuration
        try:
            from config.database_pool_config import ConnectionPoolConfig

            is_production = os.getenv("ENVIRONMENT", "development").lower() == "production"

            if is_async:
                return ConnectionPoolConfig.get_async_pool_settings(is_production)
            else:
                return ConnectionPoolConfig.get_pool_settings(is_production)
        except ImportError:
            # Fallback to original configuration if new config not available
            logger.warning("Using fallback database pool configuration")
            try:
                base_kwargs = {
                    "echo": os.getenv("SQLALCHEMY_ECHO", "false").lower() == "true",
                    "pool_size": int(os.getenv("DB_POOL_SIZE", "10")),
                    "max_overflow": int(os.getenv("DB_MAX_OVERFLOW", "20")),
                    "pool_pre_ping": True,
                    "pool_recycle": int(os.getenv("DB_POOL_RECYCLE", "1800")),
                    "pool_timeout": int(os.getenv("DB_POOL_TIMEOUT", "30")),
                }
            except ValueError as e:
                logger.error("Invalid database configuration value: %s" % e)
                raise ValueError(f"Invalid database configuration: {e}")
            if is_async:
                async_kwargs = {**base_kwargs, "pool_reset_on_return": "commit"}
                db_url = os.getenv("DATABASE_URL", "")
                connect_args = {
                    "server_settings": {"jit": "off", "application_name": "ruleIQ_backend"}
                }
                if "sslmode=require" in db_url:
                    connect_args["ssl"] = True
                async_kwargs["connect_args"] = connect_args
                return async_kwargs
            else:
                sync_kwargs = {
                    **base_kwargs,
                    "connect_args": {
                        "keepalives": 1,
                        "keepalives_idle": 30,
                        "keepalives_interval": 10,
                        "keepalives_count": 5,
                        "connect_timeout": 10,
                    },
                }
                return sync_kwargs


def _init_sync_db() -> None:
    """Initializes synchronous database engine and session maker if not already initialized."""
    global _ENGINE, _SESSION_LOCAL
    if _ENGINE is None:
        try:
            _, sync_db_url, _ = DatabaseConfig.get_database_urls()
            engine_kwargs = DatabaseConfig.get_engine_kwargs(is_async=False)
            _ENGINE = create_engine(sync_db_url, **engine_kwargs)
            _SESSION_LOCAL = sessionmaker(autocommit=False, autoflush=False, bind=_ENGINE)
            logger.info("Synchronous database engine initialized successfully")
        except Exception as e:
            logger.error("Failed to initialize synchronous database engine: %s" % e)
            raise


def _init_async_db() -> None:
    """Initializes asynchronous database engine and session maker if not already initialized."""
    global _ASYNC_ENGINE, _ASYNC_SESSION_LOCAL
    if _ASYNC_ENGINE is None:
        try:
            _, _, async_db_url = DatabaseConfig.get_database_urls()
            engine_kwargs = DatabaseConfig.get_engine_kwargs(is_async=True)
            _ASYNC_ENGINE = create_async_engine(async_db_url, **engine_kwargs)
            _ASYNC_SESSION_LOCAL = async_sessionmaker(
                bind=_ASYNC_ENGINE,
                class_=AsyncSession,
                expire_on_commit=False,
                autocommit=False,
                autoflush=False,
            )
            logger.info(
                "Asynchronous database engine initialized successfully",
            )
        except Exception as e:
            logger.error("Failed to initialize asynchronous database engine: %s" % e)
            raise


def init_db() -> bool:
    """
    Initialize database with proper error handling and logging.
    This function can be called during application startup.

    Returns:
        bool: True if initialization successful, False otherwise
    """
    try:
        logger.info("Initializing database...")
        _init_sync_db()
        _init_async_db()

        # Create all tables if they don't exist
        if _ENGINE is not None:
            Base.metadata.create_all(bind=_ENGINE)
            logger.info("Database tables created/verified")

        if not test_database_connection():
            return False
        logger.info("Database initialization completed successfully")
        return True
    except Exception as e:
        logger.error("Database initialization failed: %s" % e, exc_info=True)
        return False


def test_database_connection() -> bool:
    """Test database connection synchronously."""
    try:
        _init_sync_db()
        from database.db_setup import _ENGINE

        with _ENGINE.connect() as conn:
            conn.execute(text("SELECT 1"))
            logger.info("Database connection test successful")
            return True
    except Exception as e:
        logger.error("Database connection test failed: %s" % e)
        return False


async def test_async_database_connection() -> bool:
    """Test database connection asynchronously."""
    try:
        _init_async_db()
        from database.db_setup import _ASYNC_ENGINE

        async with _ASYNC_ENGINE.connect() as conn:
            await conn.execute(text("SELECT 1"))
            logger.info("Async database connection test successful")
            return True
    except Exception as e:
        logger.error("Async database connection test failed: %s" % e)
        return False


def get_db() -> Generator[Any, None, None]:
    """
    Provides a synchronous database session and ensures it's closed afterwards.
    Marked for deprecation.
    """
    _init_sync_db()
    db = _SESSION_LOCAL()
    try:
        yield db
    finally:
        db.close()


def get_db_session() -> Generator[Any, None, None]:
    """
    Generator function for database sessions.
    Provides a synchronous database session and ensures it's closed afterwards.
    """
    _init_sync_db()
    db = _SESSION_LOCAL()
    try:
        yield db
    finally:
        db.close()


async def get_async_db() -> AsyncGenerator[AsyncSession, None]:
    """
    Provides an asynchronous database session and ensures it's closed afterwards.
    """
    _init_async_db()
    async with _ASYNC_SESSION_LOCAL() as session:
        try:
            yield session
        except (ValueError, TypeError):
            await session.rollback()
            raise


@contextmanager
def get_db_context() -> Generator[Any, None, None]:
    """Context manager for synchronous database sessions."""
    _init_sync_db()
    db = _SESSION_LOCAL()
    try:
        yield db
        db.commit()
    except (ValueError, TypeError):
        db.rollback()
        raise
    finally:
        db.close()


async def cleanup_db_connections() -> None:
    """Cleanup database connections and dispose engines."""
    global _ENGINE, _ASYNC_ENGINE
    if _ASYNC_ENGINE:
        await _ASYNC_ENGINE.dispose()
        _ASYNC_ENGINE = None
        logger.info("Async database engine disposed")
    if _ENGINE:
        _ENGINE.dispose()
        _ENGINE = None
        logger.info("Sync database engine disposed")


def get_engine_info() -> Dict[str, Any]:
    """Get information about current database engines for debugging."""
    info = {
        "sync_engine_initialized": _ENGINE is not None,
        "async_engine_initialized": _ASYNC_ENGINE is not None,
    }
    if _ASYNC_ENGINE:
        pool = _ASYNC_ENGINE.pool
        info.update(
            {
                "async_pool_size": pool.size(),
                "async_pool_checked_in": pool.checkedin(),
                "async_pool_checked_out": pool.checkedout(),
                "async_pool_overflow": pool.overflow(),
            }
        )
    if _ENGINE:
        pool = _ENGINE.pool
        info.update(
            {
                "sync_pool_size": pool.size(),
                "sync_pool_checked_in": pool.checkedin(),
                "sync_pool_checked_out": pool.checkedout(),
                "sync_pool_overflow": pool.overflow(),
            }
        )
    return info


_get_configured_database_urls = DatabaseConfig.get_database_urls
_init_sync_db = _init_sync_db
_init_async_db = _init_async_db


def get_async_session_maker():
    """Get the async session maker, initializing if needed."""
    if _ASYNC_SESSION_LOCAL is None:
        _init_async_db()
    return _ASYNC_SESSION_LOCAL


# For backward compatibility - use a callable that does lazy initialization
def async_session_maker():
    """Lazy initialization wrapper for async session maker."""
    session_maker = get_async_session_maker()
    return session_maker()
