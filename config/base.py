"""

Base Configuration Module
Shared configuration settings across all environments
"""

from pathlib import Path
from typing import Optional, Dict, Any
from pydantic import Field, field_validator
from pydantic_settings import BaseSettings
from enum import Enum


class Environment(str, Enum):
    """Environment types"""

    DEVELOPMENT = "development"
    STAGING = "staging"
    PRODUCTION = "production"
    TESTING = "testing"


class BaseConfig(BaseSettings):
    """Base configuration with validation using Pydantic"""

    ENVIRONMENT: Environment = Field(
        default=Environment.DEVELOPMENT, description="Current environment"
    )
    APP_NAME: str = Field(default="RuleIQ", description="Application name")
    APP_VERSION: str = Field(default="1.0.0", description="Application version")
    DEBUG: bool = Field(default=False, description="Debug mode")
    HOST: str = Field(default="0.0.0.0", description="Server host")
    PORT: int = Field(default=8000, description="Server port")
    WORKERS: int = Field(default=1, description="Number of workers")
    SECRET_KEY: str = Field(..., description="Application secret key")
    JWT_SECRET_KEY: str = Field(..., description="JWT secret key")
    JWT_ALGORITHM: str = Field(default="HS256", description="JWT algorithm")
    JWT_EXPIRATION_DELTA_SECONDS: int = Field(
        default=86400, description="JWT expiration time in seconds"
    )
    DATABASE_URL: str = Field(..., description="PostgreSQL database URL")
    DB_POOL_SIZE: int = Field(default=10, description="Database pool size")
    DB_MAX_OVERFLOW: int = Field(default=20, description="Max overflow connections")
    DB_POOL_TIMEOUT: int = Field(default=30, description="Pool timeout in seconds")
    REDIS_URL: str = Field(..., description="Redis connection URL")
    REDIS_MAX_CONNECTIONS: int = Field(default=50, description="Max Redis connections")
    REDIS_DECODE_RESPONSES: bool = Field(default=True, description="Decode Redis responses")
    NEO4J_URI: str = Field(..., description="Neo4j connection URI")
    NEO4J_USERNAME: str = Field(..., description="Neo4j username")
    NEO4J_PASSWORD: str = Field(..., description="Neo4j password")
    OPENAI_API_KEY: Optional[str] = Field(None, description="OpenAI API key")
    OPENAI_MODEL: str = Field(default="gpt-4-turbo", description="Default OpenAI model")
    OPENAI_TEMPERATURE: float = Field(default=0.7, description="OpenAI temperature")
    OPENAI_MAX_TOKENS: int = Field(default=2000, description="Max tokens for OpenAI")
    GOOGLE_API_KEY: Optional[str] = Field(None, description="Google API key")
    GOOGLE_AI_API_KEY: Optional[str] = Field(None, description="Google AI API key")
    ANTHROPIC_API_KEY: Optional[str] = Field(None, description="Anthropic API key")
    CLAUDE_MODEL: str = Field(default="claude-3-opus-20240229", description="Claude model")
    UPLOAD_DIR: Path = Field(default=Path("uploads"), description="Upload directory")
    MAX_FILE_SIZE: int = Field(default=10 * 1024 * 1024, description="Max file size (10MB)")
    ALLOWED_EXTENSIONS: set = Field(
        default={"pdf", "txt", "doc", "docx", "csv"}, description="Allowed file extensions"
    )
    LOG_LEVEL: str = Field(default="INFO", description="Logging level")
    LOG_FORMAT: str = Field(
        default="%(asctime)s - %(name)s - %(levelname)s - %(message)s", description="Log format"
    )
    LOG_FILE: Optional[Path] = Field(None, description="Log file path")
    CORS_ORIGINS: list = Field(default=["*"], description="CORS allowed origins")
    CORS_ALLOW_CREDENTIALS: bool = Field(default=True, description="Allow credentials")
    CORS_ALLOW_METHODS: list = Field(default=["*"], description="Allowed methods")
    CORS_ALLOW_HEADERS: list = Field(default=["*"], description="Allowed headers")
    RATE_LIMIT_ENABLED: bool = Field(default=True, description="Enable rate limiting")
    RATE_LIMIT_REQUESTS: int = Field(default=100, description="Requests per window")
    RATE_LIMIT_WINDOW: int = Field(default=60, description="Time window in seconds")
    ENABLE_AI_PROCESSING: bool = Field(default=True, description="Enable AI processing")
    ENABLE_CACHING: bool = Field(default=True, description="Enable caching")
    ENABLE_MONITORING: bool = Field(default=False, description="Enable monitoring")

    class Config:
        """Pydantic configuration"""

        env_file = ".env"
        env_file_encoding = "utf-8"
        case_sensitive = True

    @field_validator("ENVIRONMENT", mode="before")
    @classmethod
    def validate_environment(cls, v) -> Any:
        """Validate environment value"""
        if isinstance(v, str):
            v = v.lower()
            if v not in [e.value for e in Environment]:
                raise ValueError(f"Invalid environment: {v}")
        return v

    @field_validator("DATABASE_URL")
    @classmethod
    def validate_database_url(cls, v) -> Any:
        """Validate database URL format"""
        if not v.startswith(("postgresql://", "postgresql+asyncpg://")):
            raise ValueError("DATABASE_URL must be a PostgreSQL URL")
        return v

    @field_validator("REDIS_URL")
    @classmethod
    def validate_redis_url(cls, v) -> Any:
        """Validate Redis URL format"""
        if not v.startswith(("redis://", "rediss://")):
            raise ValueError("REDIS_URL must be a Redis URL")
        return v

    @field_validator("LOG_LEVEL")
    @classmethod
    def validate_log_level(cls, v) -> Any:
        """Validate log level"""
        valid_levels = ["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"]
        if v.upper() not in valid_levels:
            raise ValueError(f"LOG_LEVEL must be one of {valid_levels}")
        return v.upper()

    def get_db_config(self) -> Dict[str, Any]:
        """Get database configuration dict"""
        return {
            "url": self.DATABASE_URL,
            "pool_size": self.DB_POOL_SIZE,
            "max_overflow": self.DB_MAX_OVERFLOW,
            "pool_timeout": self.DB_POOL_TIMEOUT,
        }

    def get_redis_config(self) -> Dict[str, Any]:
        """Get Redis configuration dict"""
        return {
            "url": self.REDIS_URL,
            "max_connections": self.REDIS_MAX_CONNECTIONS,
            "decode_responses": self.REDIS_DECODE_RESPONSES,
        }

    def get_ai_config(self) -> Dict[str, Any]:
        """Get AI services configuration"""
        return {
            "openai": {
                "api_key": self.OPENAI_API_KEY,
                "model": self.OPENAI_MODEL,
                "temperature": self.OPENAI_TEMPERATURE,
                "max_tokens": self.OPENAI_MAX_TOKENS,
            },
            "google": {"api_key": self.GOOGLE_API_KEY, "ai_api_key": self.GOOGLE_AI_API_KEY},
            "anthropic": {"api_key": self.ANTHROPIC_API_KEY, "model": self.CLAUDE_MODEL},
        }

    def is_development(self) -> bool:
        """Check if in development environment"""
        return self.ENVIRONMENT == Environment.DEVELOPMENT

    def is_production(self) -> bool:
        """Check if in production environment"""
        return self.ENVIRONMENT == Environment.PRODUCTION

    def is_testing(self) -> bool:
        """Check if in testing environment"""
        return self.ENVIRONMENT == Environment.TESTING
