"""

Production Configuration
Settings optimized for production environment
"""

from config.base import BaseConfig, Environment
import os


class ProductionConfig(BaseConfig):
    """Production-specific configuration"""

    # Override environment
    ENVIRONMENT: Environment = Environment.PRODUCTION

    # Production settings
    DEBUG: bool = False

    # Production server
    HOST: str = "0.0.0.0"
    PORT: int = int(os.getenv("PORT", 8000))  # Often set by hosting platform
    WORKERS: int = int(os.getenv("WEB_CONCURRENCY", 4))  # Multi-worker for production
    RELOAD: bool = False  # Never auto-reload in production

    # Security - Strict for production
    JWT_EXPIRATION_DELTA_SECONDS: int = 3600  # 1 hour for production
    SECURE_SSL_REDIRECT: bool = True
    SESSION_COOKIE_SECURE: bool = True
    SESSION_COOKIE_HTTPONLY: bool = True
    SESSION_COOKIE_SAMESITE: str = "Strict"

    # Database - Optimized for production
    DB_POOL_SIZE: int = 20
    DB_MAX_OVERFLOW: int = 40
    DB_POOL_TIMEOUT: int = 30
    DB_POOL_RECYCLE: int = 3600  # Recycle connections after 1 hour
    DB_ECHO: bool = False  # Never log SQL in production

    # Redis - Production settings
    REDIS_MAX_CONNECTIONS: int = 100
    REDIS_CONNECTION_TIMEOUT: int = 20
    REDIS_SOCKET_KEEPALIVE: bool = True

    # Logging - Production appropriate
    LOG_LEVEL: str = "WARNING"
    LOG_FILE: str = "/var/log/ruleiq/app.log"
    LOG_MAX_BYTES: int = 10 * 1024 * 1024  # 10MB
    LOG_BACKUP_COUNT: int = 5

    # CORS - Restrictive for production (populated by CORS_ORIGINS property below)
    CORS_ALLOW_CREDENTIALS: bool = True
    CORS_ALLOW_METHODS: list = ["GET", "POST", "PUT", "DELETE", "OPTIONS"]
    CORS_ALLOW_HEADERS: list = ["Content-Type", "Authorization"]

    # Rate Limiting - Enabled for production
    RATE_LIMIT_ENABLED: bool = True
    RATE_LIMIT_REQUESTS: int = 100
    RATE_LIMIT_WINDOW: int = 60

    # Production features
    ENABLE_DEBUG_TOOLBAR: bool = False
    ENABLE_PROFILING: bool = False
    ENABLE_SQL_ECHO: bool = False
    ENABLE_MONITORING: bool = True
    ENABLE_ERROR_TRACKING: bool = True

    # AI Services - Production limits
    OPENAI_MAX_TOKENS: int = 4000
    OPENAI_TIMEOUT: int = 30
    OPENAI_MAX_RETRIES: int = 3

    # File uploads - Production limits
    MAX_FILE_SIZE: int = 50 * 1024 * 1024  # 50MB

    # Performance
    CACHE_TTL: int = 3600  # 1 hour cache TTL
    ENABLE_COMPRESSION: bool = True
    COMPRESSION_LEVEL: int = 6

    # Health checks
    HEALTH_CHECK_PATH: str = "/health"
    READINESS_CHECK_PATH: str = "/ready"

    class Config:
        """Pydantic configuration"""

        env_file = ".env.production"
        env_file_encoding = "utf-8"
        case_sensitive = True

    @property
    def CORS_ORIGINS(self) -> list:
        """Get CORS origins from environment"""
        origins = os.getenv("CORS_ORIGINS", "")
        if origins:
            return [origin.strip() for origin in origins.split(",")]
        return []

    def validate_production_config(self) -> None:
        """Additional validation for production config"""
        # Ensure critical secrets are not defaults
        if self.SECRET_KEY == "dev-secret-key-change-in-production":
            raise ValueError("SECRET_KEY must be set for production")

        if self.JWT_SECRET_KEY == "dev-jwt-secret-key-change-in-production":
            raise ValueError("JWT_SECRET_KEY must be set for production")

        # Ensure database URL is not localhost
        if "localhost" in self.DATABASE_URL or "127.0.0.1" in self.DATABASE_URL:
            raise ValueError("DATABASE_URL should not use localhost in production")

        # Ensure Redis URL is not localhost
        if "localhost" in self.REDIS_URL or "127.0.0.1" in self.REDIS_URL:
            raise ValueError("REDIS_URL should not use localhost in production")

        # Ensure API keys are set
        if not self.OPENAI_API_KEY and self.ENABLE_AI_PROCESSING:
            raise ValueError("OPENAI_API_KEY must be set when AI processing is enabled")

    def __init__(self, **kwargs) -> None:
        """Initialize production config with validation"""
        super().__init__(**kwargs)
        self.validate_production_config()
