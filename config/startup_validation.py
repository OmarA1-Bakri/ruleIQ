"""

# Constants
MINUTE_SECONDS = 60


Startup Configuration Validation
Validates configuration on application startup
"""

import sys
import os
import logging
from typing import List, Tuple, Optional
from pathlib import Path
from . import get_current_config, validate_config, ConfigurationError, BaseConfig

logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


class StartupValidator:
    """Validates configuration and environment on startup"""

    def __init__(self, config: Optional[BaseConfig] = None) -> None:
        """Initialize validator with optional config"""
        self.config = config or get_current_config()
        self.errors: List[str] = []
        self.warnings: List[str] = []

    def validate_all(self) -> Tuple[bool, List[str], List[str]]:
        """
        Run all validation checks

        Returns:
            Tuple of (success, errors, warnings)
        """
        logger.info("Starting validation for environment: %s" % self.config.ENVIRONMENT)
        self._validate_environment()
        self._validate_secrets()
        self._validate_database_connectivity()
        self._validate_redis_connectivity()
        self._validate_neo4j_connectivity()
        self._validate_ai_services()
        self._validate_file_system()
        self._validate_security_settings()
        self._validate_performance_settings()
        if self.errors:
            logger.error("Validation failed with %s errors" % len(self.errors))
            for error in self.errors:
                logger.error("  - %s" % error)
        if self.warnings:
            logger.warning("Validation completed with %s warnings" % len(self.warnings))
            for warning in self.warnings:
                logger.warning("  - %s" % warning)
        if not self.errors and not self.warnings:
            logger.info("Configuration validation passed successfully")
        return len(self.errors) == 0, self.errors, self.warnings

    def _validate_environment(self) -> None:
        """Validate environment settings"""
        logger.debug("Validating environment settings...")
        if self.config.ENVIRONMENT not in ["development", "staging", "production", "testing"]:
            self.errors.append(f"Invalid environment: {self.config.ENVIRONMENT}")
        if self.config.is_production():
            if self.config.DEBUG:
                self.errors.append("DEBUG mode is enabled in production")
            if not self.config.SECURE_SSL_REDIRECT:
                self.warnings.append("SSL redirect is not enabled in production")

    def _validate_secrets(self) -> None:
        """Validate secret keys and tokens"""
        logger.debug("Validating secrets...")
        if len(self.config.SECRET_KEY) < 32:
            self.warnings.append("SECRET_KEY should be at least 32 characters")
        if len(self.config.JWT_SECRET_KEY) < 32:
            self.warnings.append("JWT_SECRET_KEY should be at least 32 characters")
        weak_patterns = ["dev-", "test-", "change-me", "secret", "password", "123"]
        for pattern in weak_patterns:
            if pattern in self.config.SECRET_KEY.lower():
                severity = "error" if self.config.is_production() else "warning"
                message = f"SECRET_KEY contains weak pattern: {pattern}"
                if severity == "error":
                    self.errors.append(message)
                else:
                    self.warnings.append(message)
            if pattern in self.config.JWT_SECRET_KEY.lower():
                severity = "error" if self.config.is_production() else "warning"
                message = f"JWT_SECRET_KEY contains weak pattern: {pattern}"
                if severity == "error":
                    self.errors.append(message)
                else:
                    self.warnings.append(message)

    def _validate_database_connectivity(self) -> None:
        """Validate database configuration and connectivity"""
        logger.debug("Validating database configuration...")
        if not self.config.DATABASE_URL:
            self.errors.append("DATABASE_URL is not set")
            return
        try:
            from sqlalchemy import create_engine
            from sqlalchemy.exc import OperationalError

            engine = create_engine(self.config.DATABASE_URL, connect_args={"connect_timeout": 5})
            with engine.connect() as conn:
                conn.execute("SELECT 1")
                logger.debug("Database connection successful")
        except ImportError:
            self.warnings.append("SQLAlchemy not installed, skipping database connectivity check")
        except OperationalError as e:
            if self.config.is_production():
                self.errors.append(f"Cannot connect to database: {str(e)}")
            else:
                self.warnings.append(f"Cannot connect to database: {str(e)}")
        except Exception as e:
            self.warnings.append(f"Database validation error: {str(e)}")

    def _validate_redis_connectivity(self) -> None:
        """Validate Redis configuration and connectivity"""
        logger.debug("Validating Redis configuration...")
        if not self.config.REDIS_URL:
            self.errors.append("REDIS_URL is not set")
            return
        try:
            import redis

            r = redis.from_url(
                self.config.REDIS_URL, socket_connect_timeout=5, decode_responses=True
            )
            r.ping()
            logger.debug("Redis connection successful")
        except ImportError:
            self.warnings.append("Redis not installed, skipping Redis connectivity check")
        except redis.ConnectionError as e:
            if self.config.is_production():
                self.errors.append(f"Cannot connect to Redis: {str(e)}")
            else:
                self.warnings.append(f"Cannot connect to Redis: {str(e)}")
        except Exception as e:
            self.warnings.append(f"Redis validation error: {str(e)}")

    def _validate_neo4j_connectivity(self) -> None:
        """Validate Neo4j configuration and connectivity"""
        logger.debug("Validating Neo4j configuration...")
        if not all([self.config.NEO4J_URI, self.config.NEO4J_USERNAME, self.config.NEO4J_PASSWORD]):
            self.errors.append("Neo4j configuration incomplete")
            return
        try:
            from neo4j import GraphDatabase

            driver = GraphDatabase.driver(
                self.config.NEO4J_URI,
                auth=(self.config.NEO4J_USERNAME, self.config.NEO4J_PASSWORD),
                connection_timeout=5,
            )
            with driver.session() as session:
                result = session.run("RETURN 1 AS test")
                result.single()
            driver.close()
            logger.debug("Neo4j connection successful")
        except ImportError:
            self.warnings.append("Neo4j driver not installed, skipping Neo4j connectivity check")
        except Exception as e:
            if self.config.is_production():
                self.errors.append(f"Cannot connect to Neo4j: {str(e)}")
            else:
                self.warnings.append(f"Cannot connect to Neo4j: {str(e)}")

    def _validate_ai_services(self) -> None:
        """Validate AI service configurations"""
        logger.debug("Validating AI service configurations...")
        if not self.config.ENABLE_AI_PROCESSING:
            logger.debug("AI processing disabled, skipping AI service validation")
            return
        services = {
            "OpenAI": self.config.OPENAI_API_KEY,
            "Google": self.config.GOOGLE_API_KEY or self.config.GOOGLE_AI_API_KEY,
            "Anthropic": self.config.ANTHROPIC_API_KEY,
        }
        configured_services = [name for name, key in services.items() if key]
        if not configured_services:
            self.errors.append("AI processing enabled but no AI service API keys configured")
        else:
            logger.debug("AI services configured: %s" % ", ".join(configured_services))
        if self.config.OPENAI_API_KEY and not self.config.OPENAI_API_KEY.startswith("sk-"):
            self.warnings.append("OPENAI_API_KEY doesn't match expected format")

    def _validate_file_system(self) -> None:
        """Validate file system configurations"""
        logger.debug("Validating file system configurations...")
        if self.config.UPLOAD_DIR:
            upload_path = Path(self.config.UPLOAD_DIR)
            if not upload_path.exists():
                try:
                    upload_path.mkdir(parents=True, exist_ok=True)
                    logger.debug("Created upload directory: %s" % upload_path)
                except Exception as e:
                    self.errors.append(f"Cannot create upload directory: {e}")
            elif not upload_path.is_dir():
                self.errors.append(f"Upload path exists but is not a directory: {upload_path}")
            elif not os.access(upload_path, os.W_OK):
                self.errors.append(f"Upload directory is not writable: {upload_path}")
        if self.config.LOG_FILE:
            log_path = Path(self.config.LOG_FILE).parent
            if not log_path.exists():
                try:
                    log_path.mkdir(parents=True, exist_ok=True)
                    logger.debug("Created log directory: %s" % log_path)
                except Exception as e:
                    self.warnings.append(f"Cannot create log directory: {e}")

    def _validate_security_settings(self) -> None:
        """Validate security configurations"""
        logger.debug("Validating security settings...")
        if self.config.is_production():
            if "*" in self.config.CORS_ORIGINS:
                self.errors.append("CORS allows all origins in production")
            if not self.config.SESSION_COOKIE_SECURE:
                self.warnings.append("Session cookies are not secure in production")
            if not self.config.SESSION_COOKIE_HTTPONLY:
                self.warnings.append("Session cookies are not HTTP-only in production")
            if not self.config.RATE_LIMIT_ENABLED:
                self.warnings.append("Rate limiting is disabled in production")

    def _validate_performance_settings(self) -> None:
        """Validate performance configurations"""
        logger.debug("Validating performance settings...")
        if self.config.is_production():
            if self.config.WORKERS < 2:
                self.warnings.append("Low worker count for production")
            if self.config.DB_POOL_SIZE < 10:
                self.warnings.append("Small database pool size for production")
            if self.config.REDIS_MAX_CONNECTIONS < 50:
                self.warnings.append("Low Redis max connections for production")
        if self.config.DB_POOL_TIMEOUT > MINUTE_SECONDS:
            self.warnings.append("Database pool timeout is very high")


def run_startup_validation(exit_on_error: bool = True) -> bool:
    """
    Run startup validation

    Args:
        exit_on_error: Whether to exit the application on validation errors

    Returns:
        True if validation passed
    """
    try:
        config = get_current_config()
        validate_config(config)
        validator = StartupValidator(config)
        success, errors, warnings = validator.validate_all()
        if not success and exit_on_error:
            logger.critical("Configuration validation failed. Exiting...")
            sys.exit(1)
        return success
    except ConfigurationError as e:
        logger.critical("Configuration error: %s" % e)
        if exit_on_error:
            sys.exit(1)
        return False
    except Exception as e:
        logger.critical("Unexpected error during validation: %s" % e)
        if exit_on_error:
            sys.exit(1)
        return False


if __name__ == "__main__":
    """Run validation when executed directly"""
    import os

    if len(sys.argv) > 1:
        os.environ["ENVIRONMENT"] = sys.argv[1]
    success = run_startup_validation(exit_on_error=False)
    if success:
        logger.info("\n✅ Configuration validation successful!")
        sys.exit(0)
    else:
        logger.error("\n❌ Configuration validation failed!")
        sys.exit(1)
