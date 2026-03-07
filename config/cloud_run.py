"""
Cloud Run Configuration
Minimal configuration for Cloud Run deployment without external dependencies
"""

import os
from pathlib import Path
from config.base import BaseConfig, Environment


class CloudRunConfig(BaseConfig):
    """Cloud Run configuration with minimal dependencies"""

    ENVIRONMENT = Environment.PRODUCTION
    DEBUG = False
    TESTING = False

    # Basic security - use Secret Manager in production
    SECRET_KEY = os.getenv("SECRET_KEY", "temporary-secret-key-replace-in-production")
    JWT_SECRET_KEY = os.getenv("JWT_SECRET_KEY", "temporary-jwt-key-replace-in-production")

    # Database - Neon PostgreSQL (required from environment)
    DATABASE_URL = os.getenv("DATABASE_URL")

    # Redis (required from environment)
    REDIS_URL = os.getenv("REDIS_URL")

    # Neo4j (required from environment)
    NEO4J_URI = os.getenv("NEO4J_URI")
    NEO4J_USERNAME = os.getenv("NEO4J_USERNAME")
    NEO4J_PASSWORD = os.getenv("NEO4J_PASSWORD")

    # API Configuration
    API_HOST = "0.0.0.0"
    API_PORT = int(os.getenv("PORT", "8080"))  # Cloud Run sets PORT env var
    API_WORKERS = 1  # Cloud Run manages scaling

    # CORS - allow all for testing (restrict in production)
    CORS_ORIGINS = ["*"]
    ALLOWED_HOSTS = ["*"]

    # Disable features that require external services
    ENABLE_AI_FEATURES = False
    ENABLE_EMAIL_NOTIFICATIONS = False
    ENABLE_CACHING = False
    ENABLE_MONITORING = False

    # File storage
    UPLOAD_DIR = Path("/tmp/uploads")  # Cloud Run only allows /tmp for writes
    TEMP_DIR = Path("/tmp")

    # Logging
    LOG_LEVEL = "INFO"
    LOG_FORMAT = "%(asctime)s - %(name)s - %(levelname)s - %(message)s"

    # Disable AI processing initially
    ENABLE_AI_PROCESSING = False
    OPENAI_API_KEY = None
    GOOGLE_API_KEY = None
    ANTHROPIC_API_KEY = None

    def __init__(self) -> None:
        super().__init__()
        # Create directories if they don't exist
        self.UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
