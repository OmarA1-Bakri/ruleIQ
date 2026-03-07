"""

Doppler Secrets Management Integration
======================================
Centralized configuration management using Doppler for secure secret handling.
"""

import os
import sys
import logging
from typing import Dict, Optional, Any
from functools import lru_cache
import subprocess
import json

logger = logging.getLogger(__name__)


class DopplerConfig:
    """Doppler configuration manager with fallback mechanisms."""

    def __init__(self, project: str = "ruleiq", config: str = None) -> None:
        """
        Initialize Doppler configuration.

        Args:
            project: Doppler project name
            config: Environment config (dev, staging, production)
        """
        self.project = project
        self.config = config or os.getenv("DOPPLER_CONFIG", "dev")
        self._secrets_cache = {}
        self._initialized = False

    def _run_doppler_command(self, args: list) -> tuple[bool, str]:
        """Execute Doppler CLI command."""
        try:
            result = subprocess.run(["doppler"] + args, capture_output=True, text=True, check=True)
            return True, result.stdout
        except subprocess.CalledProcessError as e:
            logger.error(f"Doppler command failed: {e.stderr}")
            return False, e.stderr
        except FileNotFoundError:
            logger.error("Doppler CLI not found. Please install Doppler CLI.")
            return False, "Doppler CLI not installed"

    def initialize(self) -> bool:
        """Initialize Doppler configuration and verify connectivity."""
        if self._initialized:
            return True

        # Verify Doppler CLI is available
        success, _ = self._run_doppler_command(["--version"])
        if not success:
            logger.warning("Doppler CLI not available, falling back to environment variables")
            return False

        # Verify project and config exist
        success, output = self._run_doppler_command(
            [
                "secrets",
                "--project",
                self.project,
                "--config",
                self.config,
                "--only-names",
                "--json",
            ]
        )

        if success:
            try:
                secrets = json.loads(output)
                logger.info(f"Doppler initialized: {len(secrets)} secrets available")
                self._initialized = True
                return True
            except json.JSONDecodeError:
                logger.error("Failed to parse Doppler response")

        return False

    @lru_cache(maxsize=128)
    def get_secret(self, key: str, default: Optional[str] = None) -> Optional[str]:
        """
        Retrieve a secret from Doppler with fallback to environment variables.

        Args:
            key: Secret name
            default: Default value if secret not found

        Returns:
            Secret value or default
        """
        # Try cache first
        if key in self._secrets_cache:
            return self._secrets_cache[key]

        # Try Doppler if initialized
        if self._initialized:
            success, value = self._run_doppler_command(
                [
                    "secrets",
                    "get",
                    key,
                    "--plain",
                    "--project",
                    self.project,
                    "--config",
                    self.config,
                ]
            )

            if success:
                self._secrets_cache[key] = value.strip()
                return value.strip()

        # Fallback to environment variable
        env_value = os.getenv(key, default)
        if env_value:
            self._secrets_cache[key] = env_value

        return env_value

    def get_all_secrets(self) -> Dict[str, str]:
        """Retrieve all secrets as a dictionary."""
        secrets = {}

        if self._initialized:
            success, output = self._run_doppler_command(
                [
                    "secrets",
                    "download",
                    "--no-file",
                    "--format",
                    "json",
                    "--project",
                    self.project,
                    "--config",
                    self.config,
                ]
            )

            if success:
                try:
                    secrets = json.loads(output)
                    self._secrets_cache.update(secrets)
                    return secrets
                except json.JSONDecodeError:
                    logger.error("Failed to parse Doppler secrets")

        # Fallback to environment variables
        for key in os.environ:
            if key.startswith(
                (
                    "DATABASE_",
                    "JWT_",
                    "API_",
                    "REDIS_",
                    "CELERY_",
                    "NEO4J_",
                    "OPENAI_",
                    "GOOGLE_",
                )
            ):
                secrets[key] = os.environ[key]

        return secrets

    def inject_to_environment(self) -> bool:
        """Inject all Doppler secrets into environment variables."""
        secrets = self.get_all_secrets()

        for key, value in secrets.items():
            os.environ[key] = str(value)

        logger.info(f"Injected {len(secrets)} secrets into environment")
        return bool(secrets)

    def get_database_url(self, test: bool = False) -> str:
        """Get database URL with test environment support."""
        key = "TEST_DATABASE_URL" if test else "DATABASE_URL"
        return self.get_secret(key, "postgresql://localhost/ruleiq")

    def get_redis_url(self) -> str:
        """Get Redis URL."""
        return self.get_secret("REDIS_URL", "redis://localhost:6379/0")

    def get_jwt_config(self) -> Dict[str, Any]:
        """Get JWT configuration."""
        return {
            "secret_key": self.get_secret("JWT_SECRET_KEY"),
            "algorithm": self.get_secret("JWT_ALGORITHM", "HS256"),
            "access_token_expire_minutes": int(
                self.get_secret("JWT_ACCESS_TOKEN_EXPIRE_MINUTES", "30")
            ),
            "refresh_token_expire_days": int(self.get_secret("JWT_REFRESH_TOKEN_EXPIRE_DAYS", "7")),
        }

    def get_ai_config(self) -> Dict[str, str]:
        """Get AI service configuration."""
        return {
            "openai_api_key": self.get_secret("OPENAI_API_KEY"),
            "google_api_key": self.get_secret("GOOGLE_AI_API_KEY"),
            "langchain_api_key": self.get_secret("LANGCHAIN_API_KEY"),
        }

    def get_neo4j_config(self) -> Dict[str, str]:
        """Get Neo4j configuration."""
        return {
            "uri": self.get_secret("NEO4J_URI", "neo4j+s://12e71bc4.databases.neo4j.io"),
            "username": self.get_secret("NEO4J_USERNAME", "neo4j"),
            "password": self.get_secret("NEO4J_PASSWORD"),
            "database": self.get_secret("NEO4J_DATABASE", "neo4j"),
        }

    def rotate_secret(self, key: str, new_value: str) -> bool:
        """
        Rotate a secret value in Doppler.

        Args:
            key: Secret name
            new_value: New secret value

        Returns:
            Success status
        """
        if not self._initialized:
            logger.error("Doppler not initialized for secret rotation")
            return False

        success, _ = self._run_doppler_command(
            [
                "secrets",
                "set",
                key,
                new_value,
                "--project",
                self.project,
                "--config",
                self.config,
            ]
        )

        if success:
            # Clear cache
            self._secrets_cache.pop(key, None)
            self.get_secret.cache_clear()
            logger.info(f"Successfully rotated secret: {key}")

        return success

    def validate_required_secrets(self, required: list) -> tuple[bool, list]:
        """
        Validate that required secrets are present.

        Args:
            required: List of required secret names

        Returns:
            Tuple of (all_present, missing_secrets)
        """
        missing = []

        for key in required:
            value = self.get_secret(key)
            if not value:
                missing.append(key)

        return len(missing) == 0, missing


# Global instance
_doppler_config = None


def get_doppler_config() -> DopplerConfig:
    """Get or create global Doppler configuration instance."""
    global _doppler_config

    if _doppler_config is None:
        _doppler_config = DopplerConfig()
        _doppler_config.initialize()

        # Auto-inject to environment in development
        if os.getenv("ENVIRONMENT", "dev") == "dev":
            _doppler_config.inject_to_environment()

    return _doppler_config


# Convenience functions
def get_secret(key: str, default: Optional[str] = None) -> Optional[str]:
    """Get a secret value from Doppler."""
    return get_doppler_config().get_secret(key, default)


def get_database_url(test: bool = False) -> str:
    """Get database URL."""
    return get_doppler_config().get_database_url(test)


def get_redis_url() -> str:
    """Get Redis URL."""
    return get_doppler_config().get_redis_url()


def validate_startup_secrets() -> None:
    """Validate required secrets on application startup."""
    required_secrets = ["DATABASE_URL", "JWT_SECRET_KEY", "SECRET_KEY", "REDIS_URL"]

    config = get_doppler_config()
    valid, missing = config.validate_required_secrets(required_secrets)

    if not valid:
        logger.error(f"Missing required secrets: {', '.join(missing)}")
        logger.error("Please configure these secrets in Doppler or environment variables")
        sys.exit(1)

    logger.info("All required secrets validated successfully")
