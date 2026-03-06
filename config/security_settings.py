"""
Security Settings Module
Centralized security configuration for production-ready deployment
"""

import os
from typing import List, Dict, Any, Optional
from enum import Enum
from pydantic import BaseModel, Field


class SecurityEnvironment(str, Enum):
    """Security environment levels"""

    DEVELOPMENT = "development"
    STAGING = "staging"
    PRODUCTION = "production"
    TESTING = "testing"


class CORSConfig(BaseModel):
    """CORS configuration with production-ready defaults"""

    # Allowed origins - explicit list, no wildcards in production
    allowed_origins: List[str] = Field(
        default_factory=lambda: [
            "https://app.ruleiq.com",
            "https://www.ruleiq.com",
            "https://staging.ruleiq.com",
        ]
    )

    # Allowed methods - explicit list
    allowed_methods: List[str] = Field(
        default_factory=lambda: ["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"]
    )

    # Allowed headers - explicit list
    allowed_headers: List[str] = Field(
        default_factory=lambda: [
            "Authorization",
            "Content-Type",
            "X-Request-ID",
            "X-CSRF-Token",
            "X-Requested-With",
            "Accept",
            "Accept-Language",
            "Content-Language",
            "Origin",
        ]
    )

    # Exposed headers for client access
    exposed_headers: List[str] = Field(
        default_factory=lambda: [
            "X-Request-ID",
            "X-RateLimit-Limit",
            "X-RateLimit-Remaining",
            "X-RateLimit-Reset",
            "Content-Length",
            "Content-Type",
        ]
    )

    # Security settings
    allow_credentials: bool = True
    max_age: int = 3600  # 1 hour

    # WebSocket CORS configuration
    websocket_origins: List[str] = Field(
        default_factory=lambda: [
            "wss://app.ruleiq.com",
            "wss://www.ruleiq.com",
            "wss://staging.ruleiq.com",
        ]
    )

    def get_config_for_environment(self, env: SecurityEnvironment) -> Dict[str, Any]:
        """Get environment-specific CORS configuration"""
        if env == SecurityEnvironment.DEVELOPMENT:
            return {
                "allow_origins": [
                    "http://localhost:3000",
                    "http://localhost:8000",
                    "http://127.0.0.1:3000",
                ],
                "allow_methods": self.allowed_methods,
                "allow_headers": self.allowed_headers,
                "expose_headers": self.exposed_headers,
                "allow_credentials": True,
                "max_age": 3600,
            }
        elif env == SecurityEnvironment.TESTING:
            return {
                "allow_origins": ["http://localhost:3000", "http://testserver"],
                "allow_methods": self.allowed_methods,
                "allow_headers": self.allowed_headers,
                "expose_headers": self.exposed_headers,
                "allow_credentials": True,
                "max_age": 3600,
            }
        else:  # Production and Staging
            return {
                "allow_origins": self.allowed_origins,
                "allow_methods": self.allowed_methods,
                "allow_headers": self.allowed_headers,
                "expose_headers": self.exposed_headers,
                "allow_credentials": self.allow_credentials,
                "max_age": self.max_age,
            }


class JWTConfig(BaseModel):
    """JWT configuration with security best practices"""

    # Token settings
    access_token_expire_minutes: int = 15
    refresh_token_expire_days: int = 7
    algorithm: str = "HS256"

    # HttpOnly cookie settings
    use_httponly_cookies: bool = True
    cookie_secure: bool = True  # HTTPS only
    cookie_samesite: str = "strict"  # strict, lax, or none
    cookie_domain: Optional[str] = None
    cookie_path: str = "/"

    # Security features
    enable_refresh_rotation: bool = True
    enable_jti_validation: bool = True  # JWT ID for revocation
    enable_audience_validation: bool = True
    issuer: str = "ruleiq.com"
    audience: List[str] = Field(default_factory=lambda: ["ruleiq-api"])

    # Rate limiting for auth endpoints
    refresh_rate_limit: int = 5  # requests per 5 minutes
    refresh_rate_window: int = 300  # 5 minutes in seconds

    # Secret rotation
    enable_secret_rotation: bool = True
    rotation_interval_days: int = 30
    rotation_overlap_hours: int = 24  # Accept both old and new during rotation


class RedisFailureStrategy(str, Enum):
    """Redis failure handling strategies"""

    FAIL_OPEN = "fail_open"  # Allow access when Redis is down
    FAIL_CLOSED = "fail_closed"  # Deny access when Redis is down
    DEGRADED = "degraded"  # Limited functionality when Redis is down


class RedisConfig(BaseModel):
    """Redis configuration with circuit breaker pattern"""

    # Connection settings
    host: str = Field(default="localhost")
    port: int = Field(default=6379)
    db: int = Field(default=0)
    password: Optional[str] = None

    # Connection pool settings
    max_connections: int = 50
    socket_timeout: int = 5
    socket_connect_timeout: int = 5
    socket_keepalive: bool = True
    socket_keepalive_options: Dict[int, int] = Field(
        default_factory=lambda: {
            1: 1,  # TCP_KEEPIDLE
            2: 5,  # TCP_KEEPINTVL
            3: 5,  # TCP_KEEPCNT
        }
    )

    # Circuit breaker settings
    failure_strategy: RedisFailureStrategy = RedisFailureStrategy.DEGRADED
    circuit_breaker_threshold: int = 5  # failures before opening
    circuit_breaker_timeout: int = 60  # seconds before retry
    circuit_breaker_half_open_requests: int = 3  # test requests in half-open state

    # Fallback cache settings (for degraded mode)
    enable_local_cache: bool = True
    local_cache_ttl: int = 300  # 5 minutes
    local_cache_max_size: int = 1000  # max items

    # Health check settings
    health_check_interval: int = 30  # seconds
    health_check_timeout: int = 5  # seconds


class RateLimitConfig(BaseModel):
    """Rate limiting configuration with burst allowance"""

    # General rate limits
    default_rate_limit: int = 100  # requests per minute
    default_burst_size: int = 20  # burst allowance

    # Endpoint-specific limits (requests per minute)
    endpoint_limits: Dict[str, Dict[str, int]] = Field(
        default_factory=lambda: {
            "/api/v1/auth/login": {"limit": 5, "burst": 2},
            "/api/v1/auth/refresh": {"limit": 5, "burst": 1},
            "/api/v1/auth/register": {"limit": 3, "burst": 1},
            "/api/v1/auth/forgot-password": {"limit": 3, "burst": 1},
            "/api/v1/ai/*": {"limit": 20, "burst": 5},
            "/api/v1/assessments/*": {"limit": 30, "burst": 10},
            "/api/v1/reports/generate": {"limit": 10, "burst": 3},
        }
    )

    # Rate limiting strategy
    use_ip_based: bool = True  # IP-based for anonymous
    use_user_based: bool = True  # User-based for authenticated
    combine_limits: bool = False  # Apply both IP and user limits

    # Token bucket algorithm settings
    refill_rate: float = 1.0  # tokens per second
    bucket_capacity: int = 100  # max tokens

    # Configuration hot-reload
    enable_hot_reload: bool = True
    config_refresh_interval: int = 60  # seconds

    # Response headers
    include_headers: bool = True
    header_prefix: str = "X-RateLimit"


class SecuritySettings(BaseModel):
    """Master security configuration"""

    environment: SecurityEnvironment = Field(
        default_factory=lambda: SecurityEnvironment(os.getenv("ENVIRONMENT", "development").lower())
    )

    # Sub-configurations
    cors: CORSConfig = Field(default_factory=CORSConfig)
    jwt: JWTConfig = Field(default_factory=JWTConfig)
    redis: RedisConfig = Field(default_factory=RedisConfig)
    rate_limit: RateLimitConfig = Field(default_factory=RateLimitConfig)

    # General security settings
    enable_security_headers: bool = True
    enable_csrf_protection: bool = True
    enable_xss_protection: bool = True
    enable_content_type_sniffing_protection: bool = True
    enable_frame_options: bool = True
    frame_options_value: str = "DENY"

    # CSP (Content Security Policy)
    enable_csp: bool = True
    csp_directives: Dict[str, str] = Field(
        default_factory=lambda: {
            "default-src": "'self'",
            "script-src": "'self' 'unsafe-inline' https://cdn.jsdelivr.net",
            "style-src": "'self' 'unsafe-inline' https://fonts.googleapis.com",
            "font-src": "'self' https://fonts.gstatic.com",
            "img-src": "'self' data: https:",
            "connect-src": "'self' wss://app.ruleiq.com",
            "frame-ancestors": "'none'",
            "base-uri": "'self'",
            "form-action": "'self'",
        }
    )

    @property
    def is_production(self) -> bool:
        """Check if running in production"""
        return self.environment == SecurityEnvironment.PRODUCTION

    @property
    def is_development(self) -> bool:
        """Check if running in development"""
        return self.environment == SecurityEnvironment.DEVELOPMENT

    def get_cors_config(self) -> Dict[str, Any]:
        """Get CORS configuration for current environment"""
        return self.cors.get_config_for_environment(self.environment)


# Singleton instance
_security_settings: Optional[SecuritySettings] = None


def get_security_settings() -> SecuritySettings:
    """Get or create security configuration singleton"""
    global _security_settings
    if _security_settings is None:
        _security_settings = SecuritySettings()
    return _security_settings


# Export for convenience
security_settings = get_security_settings()
