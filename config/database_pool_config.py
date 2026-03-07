"""
Enhanced database connection pooling configuration.

This module provides optimized connection pooling settings for PostgreSQL
with both synchronous and asynchronous connections.
"""

import os
from typing import Dict, Any
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class ConnectionPoolConfig:
    """
    Database connection pool configuration with production-ready defaults.

    Connection pooling reduces the overhead of creating new database connections
    by maintaining a pool of reusable connections.
    """

    @staticmethod
    def get_pool_settings(is_production: bool = None) -> Dict[str, Any]:
        """
        Get optimized connection pool settings based on environment.

        Args:
            is_production: Override environment detection

        Returns:
            Dict with pool configuration settings
        """
        if is_production is None:
            is_production = os.getenv("ENVIRONMENT", "development").lower() == "production"

        if is_production:
            # Production settings - optimized for high load
            return {
                # Core pool settings
                "pool_size": int(os.getenv("DB_POOL_SIZE", "20")),  # Initial pool size
                "max_overflow": int(
                    os.getenv("DB_MAX_OVERFLOW", "40")
                ),  # Max additional connections
                "pool_timeout": int(
                    os.getenv("DB_POOL_TIMEOUT", "30")
                ),  # Timeout to get connection
                "pool_recycle": int(
                    os.getenv("DB_POOL_RECYCLE", "3600")
                ),  # Recycle connections after 1 hour
                "pool_pre_ping": True,  # Test connections before using
                # Connection health checks
                "pool_reset_on_return": "rollback",  # Reset on return (rollback any uncommitted transactions)
                "echo_pool": False,  # Don't log pool checkouts/checkins
                # Query optimization
                "connect_args": {
                    "keepalives": 1,
                    "keepalives_idle": 30,
                    "keepalives_interval": 10,
                    "keepalives_count": 5,
                    "connect_timeout": 10,
                    "application_name": "ruleiq_production",
                    "options": "-c statement_timeout=30000",  # 30 second statement timeout
                },
            }
        else:
            # Development settings - balanced for debugging
            return {
                "pool_size": int(os.getenv("DB_POOL_SIZE", "5")),
                "max_overflow": int(os.getenv("DB_MAX_OVERFLOW", "10")),
                "pool_timeout": int(os.getenv("DB_POOL_TIMEOUT", "30")),
                "pool_recycle": int(os.getenv("DB_POOL_RECYCLE", "1800")),  # 30 minutes
                "pool_pre_ping": True,
                "pool_reset_on_return": "rollback",
                "echo_pool": os.getenv("DEBUG_POOL", "false").lower() == "true",
                "connect_args": {
                    "keepalives": 1,
                    "keepalives_idle": 30,
                    "keepalives_interval": 10,
                    "keepalives_count": 5,
                    "connect_timeout": 10,
                    "application_name": "ruleiq_development",
                },
            }

    @staticmethod
    def get_async_pool_settings(is_production: bool = None) -> Dict[str, Any]:
        """
        Get optimized async connection pool settings.

        Args:
            is_production: Override environment detection

        Returns:
            Dict with async pool configuration
        """
        base_settings = ConnectionPoolConfig.get_pool_settings(is_production)

        # Async-specific adjustments
        async_settings = base_settings.copy()
        async_settings["pool_reset_on_return"] = "commit"  # Commit on return for async

        # AsyncPG specific connection args
        async_settings["connect_args"] = {
            "server_settings": {
                "jit": "off",  # Disable JIT for more predictable performance
                "application_name": base_settings["connect_args"]["application_name"],
            },
            "command_timeout": 30,
            "timeout": 10,
        }

        # Add SSL if required
        db_url = os.getenv("DATABASE_URL", "")
        if "sslmode=require" in db_url or is_production:
            async_settings["connect_args"]["ssl"] = True

        return async_settings

    @staticmethod
    def get_connection_limits() -> Dict[str, int]:
        """
        Get database connection limits based on available resources.

        Returns:
            Dict with connection limit recommendations
        """
        try:
            # Try to detect system resources
            import multiprocessing

            cpu_count = multiprocessing.cpu_count()
        except:
            cpu_count = 4  # Default assumption

        # PostgreSQL connection formula: connections = (cpu_cores * 2) + effective_spindle_count
        # For SSD, effective_spindle_count = 1
        recommended_connections = (cpu_count * 2) + 1

        # Account for multiple services
        per_service_connections = max(5, recommended_connections // 3)

        return {
            "total_max_connections": recommended_connections * 3,  # For all services
            "per_service_pool_size": per_service_connections,
            "per_service_max_overflow": per_service_connections * 2,
            "warning_threshold": recommended_connections * 2,  # Warn if approaching limit
        }

    @staticmethod
    def validate_pool_config() -> Dict[str, bool]:
        """
        Validate current pool configuration.

        Returns:
            Dict with validation results
        """
        results = {
            "pool_size_valid": True,
            "max_overflow_valid": True,
            "timeout_valid": True,
            "total_connections_valid": True,
        }

        limits = ConnectionPoolConfig.get_connection_limits()
        current_pool_size = int(os.getenv("DB_POOL_SIZE", "10"))
        current_max_overflow = int(os.getenv("DB_MAX_OVERFLOW", "20"))
        current_timeout = int(os.getenv("DB_POOL_TIMEOUT", "30"))

        # Validate pool size
        if current_pool_size < 1:
            results["pool_size_valid"] = False
            logger.error("Pool size must be at least 1")
        elif current_pool_size > limits["per_service_pool_size"]:
            logger.warning(
                f"Pool size {current_pool_size} exceeds recommended {limits['per_service_pool_size']}"
            )

        # Validate max overflow
        if current_max_overflow < current_pool_size:
            results["max_overflow_valid"] = False
            logger.error("Max overflow should be >= pool size")

        # Validate timeout
        if current_timeout < 5:
            results["timeout_valid"] = False
            logger.error("Pool timeout should be at least 5 seconds")

        # Validate total connections
        total = current_pool_size + current_max_overflow
        if total > limits["warning_threshold"]:
            logger.warning(f"Total connections {total} approaching system limit")

        return results

    @staticmethod
    def generate_pool_env_file(filepath: str = ".env.db_pool") -> None:
        """
        Generate database pool configuration file.

        Args:
            filepath: Path to save the configuration
        """
        is_production = os.getenv("ENVIRONMENT", "development").lower() == "production"
        limits = ConnectionPoolConfig.get_connection_limits()

        env_content = f"""# Database Connection Pool Configuration
# Generated automatically - Adjust based on your infrastructure

# Connection Pool Settings
DB_POOL_SIZE={limits["per_service_pool_size"]}
DB_MAX_OVERFLOW={limits["per_service_max_overflow"]}
DB_POOL_TIMEOUT=30
DB_POOL_RECYCLE={"3600" if is_production else "1800"}

# Connection Health
DB_POOL_PRE_PING=true
DB_POOL_RESET_ON_RETURN=rollback

# Query Timeouts (milliseconds)
DB_STATEMENT_TIMEOUT=30000
DB_QUERY_TIMEOUT=30000
DB_CONNECT_TIMEOUT=10

# Connection Keep-Alive
DB_KEEPALIVES=1
DB_KEEPALIVES_IDLE=30
DB_KEEPALIVES_INTERVAL=10
DB_KEEPALIVES_COUNT=5

# Monitoring
DB_ECHO_POOL={"false" if is_production else "true"}
SQLALCHEMY_ECHO={"false" if is_production else "false"}

# System Limits (for reference)
# Total Max Connections: {limits["total_max_connections"]}
# Warning Threshold: {limits["warning_threshold"]}
# Recommended Pool Size: {limits["per_service_pool_size"]}
"""

        with open(filepath, "w") as f:
            f.write(env_content)

        logger.info(f"Database pool configuration saved to {filepath}")

    @staticmethod
    def get_monitoring_queries() -> Dict[str, str]:
        """
        Get PostgreSQL queries for monitoring connection pool health.

        Returns:
            Dict with monitoring SQL queries
        """
        return {
            "active_connections": """
                SELECT count(*) as active_connections
                FROM pg_stat_activity
                WHERE state != 'idle'
                AND application_name LIKE 'ruleiq%';
            """,
            "idle_connections": """
                SELECT count(*) as idle_connections
                FROM pg_stat_activity
                WHERE state = 'idle'
                AND application_name LIKE 'ruleiq%';
            """,
            "long_running_queries": """
                SELECT pid, age(clock_timestamp(), query_start) as duration,
                       state, query
                FROM pg_stat_activity
                WHERE state != 'idle'
                AND query_start < clock_timestamp() - interval '5 minutes'
                AND application_name LIKE 'ruleiq%'
                ORDER BY duration DESC;
            """,
            "connection_stats": """
                SELECT application_name,
                       count(*) as connections,
                       count(*) filter (where state = 'active') as active,
                       count(*) filter (where state = 'idle') as idle,
                       count(*) filter (where state = 'idle in transaction') as idle_in_transaction,
                       max(age(clock_timestamp(), state_change)) as oldest_connection_age
                FROM pg_stat_activity
                WHERE application_name LIKE 'ruleiq%'
                GROUP BY application_name;
            """,
            "database_size": """
                SELECT pg_database_size(current_database()) as size_bytes,
                       pg_size_pretty(pg_database_size(current_database())) as size_pretty;
            """,
            "table_sizes": """
                SELECT schemaname, tablename,
                       pg_size_pretty(pg_total_relation_size(schemaname||'.'||tablename)) as size
                FROM pg_tables
                WHERE schemaname NOT IN ('pg_catalog', 'information_schema')
                ORDER BY pg_total_relation_size(schemaname||'.'||tablename) DESC
                LIMIT 10;
            """,
        }


if __name__ == "__main__":
    # Generate configuration and validate
    print("Generating database pool configuration...")
    ConnectionPoolConfig.generate_pool_env_file()

    print("\nValidating pool configuration...")
    validation = ConnectionPoolConfig.validate_pool_config()

    for check, passed in validation.items():
        status = "✓" if passed else "✗"
        print(f"{status} {check}: {passed}")

    print("\nConnection limits for this system:")
    limits = ConnectionPoolConfig.get_connection_limits()
    for key, value in limits.items():
        print(f"  {key}: {value}")

    print("\nProduction pool settings:")
    prod_settings = ConnectionPoolConfig.get_pool_settings(is_production=True)
    for key, value in prod_settings.items():
        if key != "connect_args":
            print(f"  {key}: {value}")

    print("\nMonitoring queries available:")
    queries = ConnectionPoolConfig.get_monitoring_queries()
    for name in queries:
        print(f"  - {name}")
