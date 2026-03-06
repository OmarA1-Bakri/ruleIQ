"""

Secure configuration management for sensitive values.
This module handles encryption keys, API keys, and other sensitive configuration.
"""

import os
import secrets
from typing import Optional
from cryptography.fernet import Fernet
import logging

logger = logging.getLogger(__name__)


class SecurityConfig:
    """Centralized security configuration management."""

    def __init__(self) -> None:
        self._validate_required_keys()

    def _validate_required_keys(self) -> None:
        """Validate that all required security keys are present."""
        required_keys = ["SECRET_KEY", "CREDENTIAL_MASTER_KEY", "FERNET_KEY"]
        missing_keys = [key for key in required_keys if not os.getenv(key)]
        if missing_keys:
            logger.warning("Missing security keys: %s" % missing_keys)
            logger.info("Generating fallback keys for development...")
            self._generate_fallback_keys()

    def _generate_fallback_keys(self) -> None:
        """Generate fallback keys for development environment."""
        if not os.getenv("SECRET_KEY"):
            os.environ["SECRET_KEY"] = secrets.token_urlsafe(32)
        if not os.getenv("CREDENTIAL_MASTER_KEY"):
            os.environ["CREDENTIAL_MASTER_KEY"] = secrets.token_urlsafe(32)
        if not os.getenv("FERNET_KEY"):
            os.environ["FERNET_KEY"] = Fernet.generate_key().decode()

    @property
    def secret_key(self) -> str:
        """Get the secret key for JWT signing."""
        key = os.getenv("SECRET_KEY")
        if not key:
            raise ValueError("SECRET_KEY environment variable is required")
        return key

    @property
    def credential_master_key(self) -> str:
        """Get the master key for credential encryption."""
        key = os.getenv("CREDENTIAL_MASTER_KEY")
        if not key:
            raise ValueError("CREDENTIAL_MASTER_KEY environment variable is required")
        return key

    @property
    def fernet_key(self) -> bytes:
        """Get the Fernet key for symmetric encryption."""
        key = os.getenv("FERNET_KEY")
        if not key:
            raise ValueError("FERNET_KEY environment variable is required")
        return key.encode()

    @property
    def google_api_key(self) -> Optional[str]:
        """Get Google API key."""
        return os.getenv("GOOGLE_API_KEY")

    @property
    def openai_api_key(self) -> Optional[str]:
        """Get OpenAI API key."""
        return os.getenv("OPENAI_API_KEY")

    @property
    def anthropic_api_key(self) -> Optional[str]:
        """Get Anthropic API key."""
        return os.getenv("ANTHROPIC_API_KEY")

    def validate_production_keys(self) -> bool:
        """Validate that production-ready keys are being used."""
        placeholder_values = [
            "your_secret_key_here",
            "your_credential_master_key_here",
            "your_fernet_key_here",
            "your_google_api_key_here",
            "your_openai_api_key_here",
            "your_anthropic_api_key_here",
        ]
        for key, value in os.environ.items():
            if key in [
                "SECRET_KEY",
                "CREDENTIAL_MASTER_KEY",
                "FERNET_KEY",
                "GOOGLE_API_KEY",
                "OPENAI_API_KEY",
                "ANTHROPIC_API_KEY",
            ]:
                if value in placeholder_values:
                    logger.error("Placeholder value detected for %s" % key)
                    return False
        return True


security_config = SecurityConfig()
