"""

Enhanced Rate Limiting Configuration for AI Assessment Freemium Strategy
Implements multi-tier rate limiting for public and authenticated endpoints
"""

from enum import Enum


class RateLimitTier(Enum):
    """Rate limiting tiers for different user types and endpoints"""

    PUBLIC = "public"
    FREEMIUM = "freemium"
    AUTHENTICATED = "authenticated"
    PREMIUM = "premium"
    ADMIN = "admin"


class FreemiumRateLimits:
    """Rate limiting configuration for freemium endpoints"""

    # Public endpoint limits (per IP address)
    PUBLIC_LIMITS = {
        # Email capture - very restrictive to prevent spam
        "/api/v1/freemium/capture-email": {
            "requests": 5,
            "window": 300,  # 5 minutes
            "burst": 2,
            "block_duration": 3600,  # 1 hour block after limit exceeded,
        },
        # Assessment start - moderate restriction
        "/api/v1/freemium/start-assessment": {
            "requests": 10,
            "window": 300,  # 5 minutes
            "burst": 3,
            "block_duration": 1800,  # 30 minutes,
        },
        # Answer questions - allow more for legitimate users
        "/api/v1/freemium/answer-question": {
            "requests": 50,
            "window": 300,  # 5 minutes
            "burst": 10,
            "block_duration": 900,  # 15 minutes,
        },
        # Results viewing - cached, so can be more permissive
        "/api/v1/freemium/results": {
            "requests": 20,
            "window": 300,  # 5 minutes
            "burst": 5,
            "block_duration": 600,  # 10 minutes,
        },
        # Conversion tracking - moderate limits
        "/api/v1/freemium/track-conversion": {
            "requests": 30,
            "window": 300,  # 5 minutes
            "burst": 5,
            "block_duration": 900,  # 15 minutes,
        },
    }

    # AI service specific limits (separate from HTTP limits)
    AI_SERVICE_LIMITS = {
        "question_generation": {
            "requests": 20,
            "window": 3600,  # 1 hour
            "tier": RateLimitTier.FREEMIUM,
            "cost_threshold": 0.50,  # $0.50 per hour per IP,
        },
        "assessment_analysis": {
            "requests": 10,
            "window": 3600,  # 1 hour
            "tier": RateLimitTier.FREEMIUM,
            "cost_threshold": 2.00,  # $2.00 per hour per IP,
        },
        "results_generation": {
            "requests": 15,
            "window": 3600,  # 1 hour
            "tier": RateLimitTier.FREEMIUM,
            "cost_threshold": 1.00,  # $1.00 per hour per IP,
        },
    }

    # Global limits per IP to prevent abuse
    GLOBAL_IP_LIMITS = {
        "requests_per_minute": 100,
        "requests_per_hour": 1000,
        "requests_per_day": 5000,
        "concurrent_connections": 10,
        "max_assessment_sessions": 3,  # Max concurrent assessment sessions per IP,
    }

    # User-agent based limits (bot detection)
    BOT_DETECTION = {
        "suspicious_patterns": [
            r"bot|crawler|spider|scraper",
            r"curl|wget|python-requests",
            r"headless|phantom|selenium",
        ],
        "bot_limits": {
            "requests": 10,
            "window": 3600,  # 1 hour
            "block_duration": 86400,  # 24 hours,
        },
    }

    # Geographic rate limiting (optional)
    GEO_LIMITS = {
        "high_risk_countries": {
            "countries": ["CN", "RU", "KP"],  # ISO country codes
            "multiplier": 0.1,  # 10% of normal limits,
        },
        "premium_regions": {
            "countries": ["US", "GB", "DE", "FR", "CA", "AU"],
            "multiplier": 1.5,  # 150% of normal limits,
        },
    }


class RateLimitRedisKeys:
    """Redis key patterns for rate limiting storage"""

    @staticmethod
    def ip_endpoint_key(ip: str, endpoint: str) -> str:
        """Key for IP + endpoint specific limits"""
        return f"rate_limit:ip:{ip}:endpoint:{endpoint}"

    @staticmethod
    def ip_global_key(ip: str, window: str) -> str:
        """Key for global IP limits"""
        return f"rate_limit:ip:{ip}:global:{window}"

    @staticmethod
    def ai_service_key(ip: str, service: str) -> str:
        """Key for AI service limits"""
        return f"rate_limit:ai:{service}:ip:{ip}"

    @staticmethod
    def session_key(ip: str) -> str:
        """Key for concurrent session tracking"""
        return f"rate_limit:sessions:ip:{ip}"

    @staticmethod
    def bot_detection_key(ip: str) -> str:
        """Key for bot detection tracking"""
        return f"rate_limit:bot:ip:{ip}"

    @staticmethod
    def cost_tracking_key(ip: str, service: str) -> str:
        """Key for AI cost tracking per IP"""
        return f"cost_tracking:ai:{service}:ip:{ip}"


class RateLimitExceptions:
    """IP addresses and patterns exempt from rate limiting"""

    WHITELIST_IPS = [
        "127.0.0.1",  # Localhost
        "::1",  # IPv6 localhost
        "10.0.0.0/8",  # Private networks
        "172.16.0.0/12",  # Private networks
        "192.168.0.0/16",  # Private networks,
    ]

    # Health check and monitoring services
    MONITORING_USER_AGENTS = [
        "GoogleHC/1.0",  # Google Health Check
        "Amazon CloudFront",  # CloudFront health checks
        "UptimeRobot/2.0",  # UptimeRobot monitoring
        "Pingdom.com_bot",  # Pingdom monitoring,
    ]

    # Trusted partners and integrations
    PARTNER_API_KEYS = {
        # Format: "api_key": {"name": "Partner Name", "limits": "multiplier"}
        # These would be actual API keys in production
    }


class RateLimitResponses:
    """Standard responses for rate limit violations"""

    RATE_LIMIT_EXCEEDED = {
        "error": "rate_limit_exceeded",
        "message": "Too many requests. Please try again later.",
        "status_code": 429,
        "retry_after": None,  # Will be populated dynamically,
    }

    COST_LIMIT_EXCEEDED = {
        "error": "cost_limit_exceeded",
        "message": "AI service cost limit exceeded. Please try again later.",
        "status_code": 429,
        "retry_after": 3600,  # 1 hour,
    }

    BOT_DETECTED = {
        "error": "bot_detected",
        "message": "Automated requests are not allowed on this endpoint.",
        "status_code": 403,
    }

    SUSPICIOUS_ACTIVITY = {
        "error": "suspicious_activity",
        "message": "Unusual activity detected. Please contact support if you believe this is an error.",
        "status_code": 403,
    }


# Configuration for different environments
ENVIRONMENT_CONFIGS = {
    "development": {
        "enabled": False,  # Disable rate limiting in development
        "multiplier": 10,  # 10x higher limits for testing,
    },
    "staging": {
        "enabled": True,
        "multiplier": 2,  # 2x higher limits for testing
        "logging_level": "DEBUG",
    },
    "production": {
        "enabled": True,
        "multiplier": 1,  # Standard limits
        "logging_level": "INFO",
        "alert_on_abuse": True,
        "auto_block_enabled": True,
    },
}

# Metrics collection for rate limiting
RATE_LIMIT_METRICS = {
    "track_blocked_requests": True,
    "track_cost_per_ip": True,
    "track_geographical_usage": True,
    "track_user_agent_patterns": True,
    "alert_thresholds": {
        "blocked_requests_per_hour": 100,
        "cost_per_hour": 50.0,  # $50/hour across all IPs
        "suspicious_ips_per_hour": 10,
    },
}
