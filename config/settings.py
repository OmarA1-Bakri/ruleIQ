"""
Environment Configuration Management for RuleIQ

This module handles all environment variables and configuration settings
using Pydantic for validation and type safety.
"""
from __future__ import annotations

# Constants
DEFAULT_LIMIT = 100

"""
🔐 SECURE SECRETS VAULT INTEGRATION:
Uses AWS Secrets Manager for production secrets with environment fallback.
All sensitive configuration is retrieved through the SecretsVault class.
"""
import logging
logger = logging.getLogger(__name__)

# Load environment variables early
import os
from dotenv import load_dotenv

# Determine environment and load appropriate env file
env = os.getenv('ENVIRONMENT', 'development')
if env == 'testing' or os.getenv('TESTING', '').lower() == 'true':
    # Load test environment variables
    if os.path.exists('.env.test'):
        load_dotenv('.env.test', override=True)
    env = 'testing'
elif os.path.exists('.env.local'):
    load_dotenv('.env.local')

import json
import warnings
from enum import Enum
from typing import Dict, List, Optional, Union
from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

try:
    from .secrets_vault import get_secrets_vault, SecretKeys
    SECRETS_VAULT_AVAILABLE = True
except ImportError:
    logger.warning(
        '⚠️ SecretsVault not available, falling back to environment variables')
    SECRETS_VAULT_AVAILABLE = False


def get_secret_or_env(secret_key: str, env_key: Optional[str]=None) ->Optional[
    str]:
    """
    🔐 Get secret from SecretsVault or environment variable fallback

    Args:
        secret_key: Key used in SecretsVault (e.g., 'database_url')
        env_key: Environment variable key (defaults to secret_key.upper())

    Returns:
        Secret value or None if not found
    """
    # Skip vault in testing environment
    if os.getenv('ENVIRONMENT') == 'testing' or os.getenv('TESTING', '').lower() == 'true':
        env_key = env_key or secret_key.upper()
        value = os.getenv(env_key)
        if value:
            logger.debug("🔐 Retrieved '%s' from test environment (%s)" % (secret_key, env_key))
        return value

    if SECRETS_VAULT_AVAILABLE:
        try:
            vault = get_secrets_vault()
            value = vault.get_secret(secret_key)
            if value:
                logger.debug("🔐 Retrieved '%s' from SecretsVault" % secret_key)
                return value
        except Exception as e:
            logger.warning("⚠️ Failed to get '%s' from vault: %s" % (secret_key, e))

    env_key = env_key or secret_key.upper()
    value = os.getenv(env_key)
    if value:
        logger.debug("🔐 Retrieved '%s' from environment (%s)" % (secret_key,
            env_key))
        return value
    logger.warning("⚠️ Secret '%s' not found in vault or environment" %
        secret_key)
    return None


def parse_list_from_string(v: Union[str, list]) ->list:
    """Parse a list from string or return as-is if already a list."""
    if isinstance(v, list):
        return v
    if isinstance(v, str):
        if v.startswith('[') and v.endswith(']'):
            try:
                return json.loads(v)
            except json.JSONDecodeError:
                pass
        return [item.strip() for item in v.split(',') if item.strip()]
    return []


class Environment(str, Enum):
    """Environment types"""
    DEVELOPMENT = 'development'
    STAGING = 'staging'
    PRODUCTION = 'production'
    TESTING = 'testing'


class LogLevel(str, Enum):
    """Log levels"""
    DEBUG = 'DEBUG'
    INFO = 'INFO'
    WARNING = 'WARNING'
    ERROR = 'ERROR'
    CRITICAL = 'CRITICAL'


class Settings(BaseSettings):
    """Application settings with environment variable support."""

    model_config = SettingsConfigDict(
        env_file='.env.test' if os.getenv('TESTING', '').lower() == 'true' else '.env',
        env_file_encoding='utf-8',
        case_sensitive=False,
        extra='ignore'
    )

    # Core application settings
    app_name: str = Field(default='RuleIQ API', description='Application name')
    environment: Environment = Field(
        default_factory=lambda: Environment(os.getenv('ENVIRONMENT', 'development').lower()),
        description='Environment'
    )
    debug: bool = Field(
        default_factory=lambda: os.getenv('DEBUG', 'true').lower() == 'true',
        description='Debug mode'
    )
    version: str = Field(default='1.0.0', description='API version')
    host: str = Field(default='0.0.0.0', description='Host to bind')
    port: int = Field(default_factory=lambda: int(os.getenv('PORT', 8000)), description='Port to bind')

    @property
    def is_development(self) ->bool:
        return self.environment == Environment.DEVELOPMENT

    @property
    def is_production(self) ->bool:
        return self.environment == Environment.PRODUCTION

    @property
    def is_testing(self) ->bool:
        return self.environment == Environment.TESTING or os.getenv('TESTING', '').lower() == 'true'

    @property
    def is_cloud_run(self) -> bool:
        """Check if running in Google Cloud Run environment."""
        return os.getenv('K_SERVICE') is not None or os.getenv('CLOUD_RUN_JOB') is not None

    # Database configuration
    database_url: str = Field(
        default_factory=lambda: (
            os.getenv('TEST_DATABASE_URL')
            if os.getenv('TESTING', '').lower() == 'true'
            else get_secret_or_env(
                SecretKeys.DATABASE_URL if SECRETS_VAULT_AVAILABLE else 'database_url',
                'DATABASE_URL'
            ) or ''
        ),
        description='Primary database URL'
    )

    @property
    def async_database_url(self) -> str:
        """Convert database URL to async format for asyncpg"""
        url = self.database_url
        if url.startswith('postgresql://'):
            return url.replace('postgresql://', 'postgresql+asyncpg://')
        elif url.startswith('postgres://'):
            return url.replace('postgres://', 'postgresql+asyncpg://')
        return url
    database_pool_size: int = Field(default=10, description='Database connection pool size')
    database_max_overflow: int = Field(default=20, description='Database max overflow connections')
    database_pool_timeout: int = Field(default=30, description='Database connection timeout (seconds)')
    database_pool_recycle: int = Field(default=3600, description='Database connection recycle time')

    # Redis configuration
    redis_url: str = Field(
        default_factory=lambda: (
            os.getenv('REDIS_URL')
            if os.getenv('TESTING', '').lower() == 'true'
            else get_secret_or_env(
                SecretKeys.REDIS_URL if SECRETS_VAULT_AVAILABLE else 'redis_url',
                'REDIS_URL'
            ) or ''
        ),
        description='Redis URL for caching'
    )
    redis_max_connections: int = Field(default=20, description='Max Redis connections')
    redis_socket_keepalive: bool = Field(default=True, description='Redis socket keepalive')
    redis_socket_keepalive_options: Dict[str, int] = Field(default_factory=lambda: {}, description='Redis keepalive options')

    # JWT configuration
    jwt_secret_key: str = Field(
        default_factory=lambda: (
            os.getenv('JWT_SECRET_KEY', '')
            if os.getenv('TESTING', '').lower() == 'true'
            else get_secret_or_env(
                SecretKeys.JWT_SECRET if SECRETS_VAULT_AVAILABLE else 'jwt_secret',
                'JWT_SECRET_KEY'
            ) or ''
        ),
        description='JWT secret key'
    )
    jwt_algorithm: str = Field(default='HS256', description='JWT algorithm')
    jwt_access_token_expire_minutes: int = Field(default=30, description='JWT access token expiration (minutes)')
    jwt_refresh_token_expire_days: int = Field(default=30, description='JWT refresh token expiration (days)')

    # Google OAuth configuration
    google_client_id: Optional[str] = Field(
        default_factory=lambda: get_secret_or_env(
            SecretKeys.GOOGLE_CLIENT_ID if SECRETS_VAULT_AVAILABLE else 'google_client_id',
            'GOOGLE_CLIENT_ID'
        ),
        description='Google OAuth client ID'
    )
    google_client_secret: Optional[str] = Field(
        default_factory=lambda: get_secret_or_env(
            SecretKeys.GOOGLE_CLIENT_SECRET if SECRETS_VAULT_AVAILABLE else 'google_client_secret',
            'GOOGLE_CLIENT_SECRET'
        ),
        description='Google OAuth client secret'
    )
    google_redirect_uri: str = Field(default='http://localhost:8000/api/v1/auth/google/callback', description='Google OAuth redirect URI')

    # Google AI configuration
    google_api_key: str = Field(
        default_factory=lambda: get_secret_or_env(
            SecretKeys.GOOGLE_AI_API_KEY if SECRETS_VAULT_AVAILABLE else 'google_ai_api_key',
            'GOOGLE_AI_API_KEY'
        ) or '',
        description='Google AI API key'
    )
    gemini_model: str = Field(default='gemini-1.5-flash', description='Gemini model')
    gemini_temperature: float = Field(default=0.1, description='Gemini temperature')
    gemini_max_tokens: int = Field(default=4096, description='Gemini max tokens')
    gemini_timeout: int = Field(default=60, description='Gemini request timeout')

    # AI rate limiting
    ai_rate_limit_tier_1: int = Field(default=20, description='AI Tier 1 requests per minute')
    ai_rate_limit_tier_2: int = Field(default=10, description='AI Tier 2 requests per minute')
    ai_rate_limit_tier_3: int = Field(default=3, description='AI Tier 3 requests per minute')
    ai_cost_tracking_enabled: bool = Field(default=True, description='Enable AI cost tracking')
    ai_monthly_budget_limit: float = Field(default=500.0, description='Monthly AI budget limit (USD)')
    ai_cost_alert_threshold: float = Field(default=0.8, description='Alert threshold (80% of budget)')

    # File upload configuration
    max_file_size_mb: int = Field(default=10, description='Max file upload size (MB)')
    upload_directory: str = Field(default='./uploads', description='File upload directory')
    data_dir: str = Field(default='./data', description='Data directory for application files')
    report_directory: str = Field(default='./reports', description='Directory for generated reports')
    allowed_file_types: Union[List[str], str] = Field(
        default=['pdf', 'docx', 'doc', 'txt', 'csv', 'xlsx', 'json'],
        description='Allowed file extensions'
    )

    # Security configuration
    password_min_length: int = Field(default=8, description='Minimum password length')
    bcrypt_rounds: int = Field(default=12, description='Bcrypt hashing rounds')
    session_timeout_minutes: int = Field(default=60, description='Session timeout (minutes)')
    force_https: bool = Field(default=False, description='Force HTTPS in production')
    secure_cookies: bool = Field(default=False, description='Use secure cookies')
    csrf_protection_enabled: bool = Field(default=True, description='Enable CSRF protection')

    # CORS configuration
    cors_origins: Union[List[str], str] = Field(default=['http://localhost:3000'])
    cors_allowed_origins: Union[List[str], str] = Field(
        default=['http://localhost:3000', 'http://127.0.0.1:8080', 'http://localhost:8080']
    )
    allowed_hosts: Union[List[str], str] = Field(default=['localhost', '127.0.0.1'])

    @field_validator('cors_origins', 'cors_allowed_origins', 'allowed_hosts', 'allowed_file_types', mode='before')
    @classmethod
    def parse_list_fields(cls, v: Union[str, List[str]]) ->List[str]:
        """Parse list fields from string or return as-is"""
        if isinstance(v, list):
            return v
        if isinstance(v, str):
            if v.startswith('[') and v.endswith(']'):
                try:
                    return json.loads(v)
                except json.JSONDecodeError:
                    pass
            return [item.strip() for item in v.split(',') if item.strip()]
        return []

    # Rate limiting
    rate_limit_enabled: bool = Field(default=True, description='Enable rate limiting')
    rate_limit_per_minute: int = Field(default=100, description='General rate limit per minute')
    auth_rate_limit_per_minute: int = Field(default=5, description='Auth rate limit per minute')

    # Logging configuration
    log_level: LogLevel = Field(default=LogLevel.INFO, description='Logging level')
    log_file_enabled: bool = Field(default=True, description='Enable file logging')
    log_file_path: str = Field(default='./logs/app.log', description='Log file path')
    log_file_max_bytes: int = Field(default=10000000, description='Max log file size (bytes)')
    log_file_backup_count: int = Field(default=5, description='Log file backup count')

    # Monitoring configuration
    monitoring_enabled: bool = Field(default=True, description='Enable monitoring')
    performance_monitoring_enabled: bool = Field(default=True, description='Enable performance monitoring')
    error_monitoring_enabled: bool = Field(default=True, description='Enable error monitoring')

    # Cache configuration
    cache_migration_on_startup: bool = Field(
        default=False,
        description='Invalidate MD5-based caches on startup (one-time migration)'
    )

    # Celery configuration (DEPRECATED — replaced by LangGraph orchestration)
    celery_broker_url: Optional[str] = Field(
        default=None,
        description='DEPRECATED: Celery broker URL — LangGraph is now used for task orchestration'
    )
    celery_result_backend: Optional[str] = Field(
        default=None,
        description='DEPRECATED: Celery result backend — LangGraph is now used for task orchestration'
    )
    celery_task_timeout: int = Field(default=300, description='DEPRECATED: Celery task timeout (seconds)')

    @field_validator('celery_broker_url', 'celery_result_backend', 'celery_task_timeout', mode='after')
    @classmethod
    def warn_celery_deprecated(cls, value):
        if value:
            warnings.warn(
                "Celery configuration is deprecated. Migrate to LangGraph orchestration.",
                DeprecationWarning,
                stacklevel=2,
            )
        return value

    # AWS configuration
    aws_access_key_id: Optional[str] = Field(default=None, description='AWS access key')
    aws_secret_access_key: Optional[str] = Field(default=None, description='AWS secret key')
    aws_region: str = Field(default='eu-west-2', description='AWS region')
    s3_bucket_name: Optional[str] = Field(default=None, description='S3 bucket name')

    # Stripe configuration
    stripe_publishable_key: Optional[str] = Field(default=None, description='Stripe publishable key')
    stripe_secret_key: Optional[str] = Field(default=None, description='Stripe secret key')
    stripe_webhook_secret: Optional[str] = Field(default=None, description='Stripe webhook secret')

    # Secrets vault configuration
    secrets_vault_enabled: bool = Field(
        default_factory=lambda: (
            False if os.getenv('TESTING', '').lower() == 'true'
            else os.getenv('SECRETS_MANAGER_ENABLED', 'false').lower() == 'true'
        ),
        description='Enable AWS Secrets Manager vault integration'
    )
    secrets_vault_region: str = Field(
        default_factory=lambda: os.getenv('SECRETS_MANAGER_REGION', 'us-east-1'),
        description='AWS Secrets Manager region'
    )
    secrets_vault_name: str = Field(
        default_factory=lambda: os.getenv('SECRETS_MANAGER_SECRET_NAME', 'ruleiq-production-secrets'),
        description='AWS Secrets Manager secret name'
    )

    # Sentry configuration
    sentry_dsn: Optional[str] = Field(
        default_factory=lambda: (
            None if os.getenv('TESTING', '').lower() == 'true'
            else get_secret_or_env(
                SecretKeys.SENTRY_DSN if SECRETS_VAULT_AVAILABLE else 'sentry_dsn',
                'SENTRY_DSN'
            )
        ),
        description='Sentry DSN for error tracking'
    )
    enable_sentry: bool = Field(
        default_factory=lambda: os.getenv('TESTING', '').lower() != 'true',
        description='Enable Sentry integration'
    )
    enable_metrics: bool = Field(default=True, description='Enable metrics collection')
    enable_health_checks: bool = Field(default=True, description='Enable health check endpoints')
    slow_request_threshold: float = Field(default=1.0, description='Slow request warning threshold (seconds)')
    enable_performance_monitoring: bool = Field(default=True, description='Enable performance monitoring')
    traces_sample_rate: float = Field(default=0.1, description='Sentry traces sample rate (0.0-1.0)')
    profiles_sample_rate: float = Field(default=0.1, description='Sentry profiles sample rate (0.0-1.0)')

    # Resource thresholds
    disk_warning_threshold: float = Field(default=80.0, description='Disk usage warning threshold (%)')
    disk_critical_threshold: float = Field(default=90.0, description='Disk usage critical threshold (%)')
    memory_warning_threshold: float = Field(default=85.0, description='Memory usage warning threshold (%)')
    memory_critical_threshold: float = Field(default=95.0, description='Memory usage critical threshold (%)')

    # Debug configuration
    enable_debug_endpoints: bool = Field(
        default_factory=lambda: (
            os.getenv('ENVIRONMENT', 'development') == 'development' or
            os.getenv('TESTING', '').lower() == 'true'
        ),
        description='Enable debug endpoints'
    )
    metrics_endpoint_enabled: bool = Field(default=True, description='Enable Prometheus metrics endpoint')

    # Feature flags
    agentic_assessments_enabled: bool = Field(default=False, description='Enable agentic assessments')
    ai_policy_generation_enabled: bool = Field(default=True, description='Enable AI policy generation')
    advanced_analytics_enabled: bool = Field(default=True, description='Enable advanced analytics')
    integration_sync_enabled: bool = Field(default=True, description='Enable integration sync')
    audit_log_retention_days: int = Field(default=90, description='Number of days to retain audit logs')
    real_time_security_alerts: bool = Field(default=True, description='Enable real-time security alerts')

    @field_validator('database_url')
    @classmethod
    def validate_database_url(cls, v: str) ->str:
        """Validate database URL format"""
        if not v or not v.startswith(('postgresql://', 'postgresql+asyncpg://', 'sqlite:///')):
            if os.getenv('TESTING', '').lower() == 'true':
                # In testing, use environment variable or fail
                test_url = os.getenv('TEST_DATABASE_URL', '')
                if test_url:
                    return test_url
            raise ValueError('Database URL must be provided and start with postgresql:// or sqlite:///')
        return v

    @field_validator('redis_url')
    @classmethod
    def validate_redis_url(cls, v: str) ->str:
        """Validate Redis URL format"""
        if not v or not v.startswith('redis://'):
            if os.getenv('TESTING', '').lower() == 'true':
                # In testing, use environment variable or fail
                test_url = os.getenv('REDIS_URL', '')
                if test_url:
                    return test_url
            raise ValueError('Redis URL must be provided and start with redis://')
        return v

    @field_validator('jwt_secret_key')
    @classmethod
    def validate_jwt_secret(cls, v: str) ->str:
        """Validate JWT secret key strength"""
        if not v or len(v) < 32:
            raise ValueError('JWT secret key must be at least 32 characters long and provided via environment')
        return v

    @field_validator('google_api_key')
    @classmethod
    def validate_google_api_key(cls, v: str) ->str:
        """Validate Google API key format"""
        if v and not v.startswith('AIza'):
            logger.warning(
                "Google API key may not be in the correct format (should start with 'AIza')"
            )
        return v or ''

    @field_validator('max_file_size_mb')
    @classmethod
    def validate_max_file_size(cls, v: int) ->int:
        """Validate file size limits"""
        if v > DEFAULT_LIMIT:
            raise ValueError('Max file size cannot exceed 100MB')
        return v

    @field_validator('bcrypt_rounds')
    @classmethod
    def validate_bcrypt_rounds(cls, v: int) ->int:
        """Validate bcrypt rounds"""
        if v < 10 or v > 16:
            raise ValueError('Bcrypt rounds must be between 10 and 16')
        return v

    def get_secrets_vault_health(self) ->Dict[str, Union[str, bool]]:
        """
        🔐 Get SecretsVault health status for monitoring

        Returns:
            Dict containing vault health information
        """
        if self.is_testing:
            return {
                'status': 'disabled',
                'enabled': False,
                'message': 'SecretsVault disabled in testing environment',
                'vault_type': 'None'
            }

        if not SECRETS_VAULT_AVAILABLE:
            return {
                'status': 'unavailable',
                'enabled': False,
                'message': 'SecretsVault module not available',
                'vault_type': 'None'
            }

        try:
            from .secrets_vault import vault_health_check
            return vault_health_check()
        except Exception as e:
            logger.error('❌ SecretsVault health check failed: %s' % e)
            return {
                'status': 'error',
                'enabled': self.secrets_vault_enabled,
                'message': f'Health check failed: {str(e)}',
                'vault_type': 'AWS Secrets Manager'
            }

    def log_vault_status(self) ->None:
        """🔐 Log SecretsVault status at application startup"""
        if self.is_testing:
            logger.info('🧪 Testing environment: SecretsVault disabled, using test configuration')
            return

        health = self.get_secrets_vault_health()
        if health['status'] == 'healthy':
            logger.info('✅ SecretsVault: AWS Secrets Manager connected and healthy')
        elif health['status'] == 'disabled':
            logger.info('🔐 SecretsVault: Disabled, using environment variables')
        elif health['status'] == 'unavailable':
            logger.warning('⚠️ SecretsVault: Module unavailable, using environment fallback')
        else:
            logger.error('❌ SecretsVault: %s' % health['message'])

        logger.info('🔐 Vault Configuration: enabled=%s, region=%s' % (
            self.secrets_vault_enabled, self.secrets_vault_region
        ))

    @property
    def is_secrets_vault_healthy(self) ->bool:
        """🔐 Quick check if SecretsVault is healthy"""
        if self.is_testing:
            return False
        return self.get_secrets_vault_health()['status'] == 'healthy'


# Singleton instance management
_settings: Optional[Settings] = None


def get_settings() ->Settings:
    """Get application settings"""
    return _get_or_create_settings()


def reload_settings() ->Settings:
    """Reload settings from environment variables"""
    return _create_new_settings()


def _get_or_create_settings() ->Settings:
    """Get existing settings or create new ones"""
    global _settings
    if _settings is None:
        _settings = Settings()
        if not _settings.is_testing:
            _settings.log_vault_status()
    return _settings


def _create_new_settings() ->Settings:
    """Create new settings instance"""
    global _settings
    _settings = Settings()
    return _settings


# Export the settings instance
settings = get_settings()
