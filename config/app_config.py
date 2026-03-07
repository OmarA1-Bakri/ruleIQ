"""
import logging


logger = logging.getLogger(__name__)
Application configuration settings.

This module loads critical configuration values from environment variables
and initializes services like the Fernet cipher for encryption.
"""

import os
from cryptography.fernet import Fernet
from config.logging_config import get_logger

logger = get_logger(__name__)
FERNET_KEY_ENV_VAR = "FERNET_KEY"
FERNET_KEY = os.getenv(FERNET_KEY_ENV_VAR)
if not FERNET_KEY:
    logger.critical(
        "%s environment variable not set. This is required for encrypting credentials. Please generate a key using 'python scripts/generate_fernet_key.py' and set it."
        % FERNET_KEY_ENV_VAR
    )
    cipher_suite = None
elif len(FERNET_KEY.encode()) != 44:
    logger.critical(
        "%s is invalid. It must be a valid Fernet key (44 bytes, base64 encoded). Please regenerate the key using 'python scripts/generate_fernet_key.py'."
        % FERNET_KEY_ENV_VAR
    )
    cipher_suite = None
else:
    try:
        cipher_suite = Fernet(FERNET_KEY.encode())
        logger.info(
            "Fernet cipher suite initialized successfully for credential encryption.",
        )
    except Exception as e:
        logger.critical(
            "Failed to initialize Fernet cipher suite with the provided FERNET_KEY: %s" % e,
            exc_info=True,
        )
        cipher_suite = None


def get_cipher_suite() -> Fernet | None:
    """Returns the initialized Fernet cipher suite."""
    if cipher_suite is None:
        logger.error(
            "Fernet cipher suite is not available. Encryption/decryption will fail.",
        )
    return cipher_suite
