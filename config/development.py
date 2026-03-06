"""

Development Configuration
Settings specific to development environment
"""

from config.base import BaseConfig, Environment


class DevelopmentConfig(BaseConfig):
    """Development-specific configuration"""

    # Override environment
    ENVIRONMENT: Environment = Environment.DEVELOPMENT

    # Development overrides
    DEBUG: bool = True

    # Development server
    HOST: str = "127.0.0.1"
    PORT: int = 8000
    WORKERS: int = 1
    RELOAD: bool = True  # Auto-reload on code changes

    # Security - Less strict for development
    JWT_EXPIRATION_DELTA_SECONDS: int = 86400 * 7  # 7 days for development

    # Database - Smaller pools for development
    DB_POOL_SIZE: int = 5
    DB_MAX_OVERFLOW: int = 10

    # Redis - Fewer connections for development
    REDIS_MAX_CONNECTIONS: int = 10

    # Logging - More verbose for development
    LOG_LEVEL: str = "DEBUG"
    LOG_FILE: None = None  # Log to console only in development

    # CORS - More permissive for development
    CORS_ORIGINS: list = ["*"]

    # Rate Limiting - Disabled for development
    RATE_LIMIT_ENABLED: bool = False

    # Development features
    ENABLE_DEBUG_TOOLBAR: bool = True
    ENABLE_PROFILING: bool = True
    ENABLE_SQL_ECHO: bool = True  # Log SQL queries

    # AI Services - Lower limits for development
    OPENAI_MAX_TOKENS: int = 1000

    # File uploads - Smaller limits for development
    MAX_FILE_SIZE: int = 5 * 1024 * 1024  # 5MB

    class Config:
        """Pydantic configuration"""

        env_file = ".env.development"
        env_file_encoding = "utf-8"
        case_sensitive = True

    def __init__(self, **kwargs) -> None:
        """Initialize development config with defaults"""
        # Set development defaults if not provided
        defaults = {
            "SECRET_KEY": kwargs.get(
                "SECRET_KEY",
                "dev-secret-key-change-in-production",
            ),
            "JWT_SECRET_KEY": kwargs.get(
                "JWT_SECRET_KEY",
                "dev-jwt-secret-key-change-in-production",
            ),
            "DATABASE_URL": kwargs.get(
                "DATABASE_URL",
                "postgresql://localhost/ruleiq_dev",
            ),
            "REDIS_URL": kwargs.get("REDIS_URL", "redis://localhost:6379/0"),
            "NEO4J_URI": kwargs.get("NEO4J_URI", "neo4j+s://12e71bc4.databases.neo4j.io"),
            "NEO4J_USERNAME": kwargs.get("NEO4J_USERNAME", "neo4j"),
            "NEO4J_PASSWORD": kwargs.get("NEO4J_PASSWORD", "ruleiq123"),
        }
        kwargs.update(defaults)
        super().__init__(**kwargs)
