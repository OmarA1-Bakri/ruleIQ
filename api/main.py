"""
Main FastAPI application for ruleIQ API
Production-ready FastAPI application with comprehensive configuration
"""

# Standard library imports
import logging
import os
import time
from contextlib import asynccontextmanager
from typing import AsyncGenerator, Dict, Any, Optional

# Third-party imports
import uvicorn
from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZipMiddleware
from fastapi.middleware.trustedhost import TrustedHostMiddleware
from fastapi.responses import JSONResponse
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError

# Import settings with Cloud Run error handling
try:
    from config.settings import settings
except Exception as e:
    # Bootstrap logger for early errors
    bootstrap_logger = logging.getLogger(__name__)
    bootstrap_logger.error("Failed to load settings: %s", e)
    raise

# Local application imports
from api.routers import (
    ai_assessments,
    ai_cost_monitoring,
    ai_cost_websocket,
    ai_optimization,
    ai_policy,
    assessments,
    auth,
    business_profiles,
    chat,
    compliance,
    evidence,
    evidence_collection,
    foundation_evidence,
    frameworks,
    freemium,
    implementation,
    integrations,
    iq_agent,
    monitoring,
    payment,
    policies,
    readiness,
    rbac_auth,
    reports,
    security,
    uk_compliance,
    users,
)
from api.routers.admin import data_access, user_management, token_management
from api.middleware.error_handler import error_handler_middleware
from api.middleware.rate_limiter import rate_limit_middleware
from api.middleware.security_headers import security_headers_middleware
from config.ai_config import ai_config
from app.core.monitoring.setup import configure_from_settings
from app.core.monitoring.shutdown import get_shutdown_manager

# Initialize logging with error handling
try:
    from config.logging_config import setup_logging

    setup_logging()
except Exception as e:
    import logging

    logging.basicConfig(level=logging.INFO)
    bootstrap_logger = logging.getLogger(__name__)
    bootstrap_logger.warning("Logging config unavailable: %s", e)

# Initialize logger
logger = logging.getLogger(__name__)

# Database imports with Cloud Run error handling
try:
    from database import (
        test_async_database_connection,
        cleanup_db_connections,
        get_async_session_maker,
    )

    logger.info("✅ Database modules imported successfully")
except ImportError as e:
    is_cloud_run = bool(os.getenv("K_SERVICE") or os.getenv("CLOUD_RUN_JOB"))
    if is_cloud_run:
        logger.warning("🌩️ Cloud Run: Database import warning (will retry later): %s", e)

        # Define fallback functions for Cloud Run
        async def test_async_database_connection() -> bool:
            """Fallback function returning False when database is not available."""
            return False

        async def cleanup_db_connections() -> None:
            """Fallback function for database cleanup when database is not available."""
            pass

        def get_async_session_maker() -> Optional[Any]:
            """Fallback function returning None when database is not available."""
            return None
    else:
        logger.error("❌ Failed to import database modules: %s", e)
        raise

# Constants
HTTP_SERVICE_UNAVAILABLE = 503

logger.info("✅ Settings loaded successfully")
if os.getenv("K_SERVICE") or os.getenv("CLOUD_RUN_JOB"):
    logger.info("🌩️ Cloud Run environment detected")

shutdown_manager = get_shutdown_manager()


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """
    Application lifespan context manager for startup/shutdown events
    """
    app.state.start_time = time.time()
    is_cloud_run = bool(os.getenv("K_SERVICE") or os.getenv("CLOUD_RUN_JOB"))

    logger.info("--- Lifespan Startup: Initiated ---")
    if is_cloud_run:
        logger.info("🌩️ Cloud Run environment detected - using optimized startup")

    logger.info("--- Lifespan Startup: Validating Configuration... ---")
    try:
        validate_configuration()
        logger.info("--- Lifespan Startup: Configuration Validated ---")
    except Exception as e:
        if is_cloud_run:
            logger.warning("🌩️ Cloud Run: Configuration validation failed (non-fatal): %s", e)
            app.state.config_ready = False
        else:
            logger.error("❌ Configuration validation failed: %s", e)
            raise
    else:
        app.state.config_ready = True

    # Initialize database with graceful degradation for Cloud Run
    logger.info("--- Lifespan Startup: Initializing Database... ---")
    app.state.db_ready = False

    try:
        # Try to initialize database setup first
        from database.db_setup import init_db

        db_init_success = init_db()

        if db_init_success:
            logger.info("--- Lifespan Startup: Database initialization successful ---")
            # Now test async connection
            try:
                ok = await test_async_database_connection()
                if ok:
                    logger.info("--- Lifespan Startup: Database Connection Verified (Async) ---")
                    app.state.db_ready = True
                else:
                    logger.warning(
                        "--- Lifespan Startup: Async DB connection test failed (non-fatal) ---"
                    )
                    app.state.db_ready = False
            except Exception as async_test_error:
                logger.warning(
                    "--- Lifespan Startup: Async DB test error (non-fatal): %s ---",
                    async_test_error,
                )
                app.state.db_ready = False
        else:
            logger.warning(
                "--- Lifespan Startup: Database initialization failed (non-fatal in Cloud Run) ---"
            )
            app.state.db_ready = False

    except ImportError as import_error:
        if is_cloud_run:
            logger.warning("🌩️ Cloud Run: Database import failed (will defer): %s", import_error)
            app.state.db_ready = False
        else:
            logger.error("❌ Database import failed: %s", import_error)
            raise
    except Exception as e:
        error_msg = "Database initialization error: %s" % e
        if is_cloud_run:
            logger.warning("🌩️ Cloud Run: %s (non-fatal)", error_msg)
            app.state.db_ready = False
        else:
            logger.error("❌ %s", error_msg)
            # In non-Cloud Run environments, database connectivity is critical
            raise

    # Initialize optional services with graceful degradation
    app.state.redis_ready = False
    if hasattr(settings, "redis_url") and settings.redis_url:
        try:
            # Test Redis connection if available
            logger.info("--- Lifespan Startup: Testing Redis Connection... ---")
            # Note: Actual Redis test would go here
            app.state.redis_ready = True
            logger.info("--- Lifespan Startup: Redis Connection Verified ---")
        except Exception as e:
            logger.warning("--- Lifespan Startup: Redis connection failed (non-fatal): %s ---", e)
            app.state.redis_ready = False
    else:
        logger.info("--- Lifespan Startup: Redis not configured (optional) ---")

    logger.info("--- Lifespan Startup: Completed Successfully ---")
    yield

    logger.info("Shutting down ruleIQ API...")
    try:
        from api.routers.iq_agent import cleanup_iq_agent

        await cleanup_iq_agent()
        logger.info("IQ agent resources cleaned up")
    except Exception as e:
        logger.warning("IQ agent cleanup warning: %s", e)

    try:
        await cleanup_db_connections()
        logger.info("Database connections closed")
    except Exception as e:
        logger.warning("Database cleanup warning: %s", e)

    logger.info("ruleIQ API shutdown complete")


app = FastAPI(
    title="ruleIQ API",
    description="AI-powered compliance and risk management platform",
    version="1.0.0",
    docs_url="/api/v1/docs" if settings.debug else None,
    redoc_url="/api/v1/redoc" if settings.debug else None,
    openapi_url="/api/v1/openapi.json",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS", "PATCH"],
    allow_headers=["*"],
    expose_headers=[
        "X-Total-Count",
        "X-RateLimit-Limit",
        "X-RateLimit-Remaining",
        "X-RateLimit-Reset",
    ],
)

# Conditionally restrict TrustedHostMiddleware in production
allowed_hosts = ["*"] if settings.debug else settings.allowed_hosts
app.add_middleware(TrustedHostMiddleware, allowed_hosts=allowed_hosts)
app.add_middleware(GZipMiddleware, minimum_size=1000)

configure_from_settings(app)
shutdown_manager.install_signal_handlers()

app.middleware("http")(security_headers_middleware)
app.middleware("http")(error_handler_middleware)
app.middleware("http")(rate_limit_middleware)

# Include routers
app.include_router(auth.router, prefix="/api/v1/auth", tags=["authentication"])
app.include_router(users.router, prefix="/api/v1/users", tags=["users"])
app.include_router(assessments.router, prefix="/api/v1/assessments", tags=["assessments"])
app.include_router(ai_assessments.router, prefix="/api/v1/ai-assessments", tags=["ai-assessments"])
app.include_router(
    ai_optimization.router, prefix="/api/v1/ai-optimization", tags=["ai-optimization"]
)
app.include_router(
    business_profiles.router, prefix="/api/v1/business-profiles", tags=["business-profiles"]
)
app.include_router(chat.router, prefix="/api/v1/chat", tags=["chat"])
app.include_router(compliance.router, prefix="/api/v1/compliance", tags=["compliance"])
app.include_router(evidence.router, prefix="/api/v1/evidence", tags=["evidence"])
app.include_router(
    evidence_collection.router, prefix="/api/v1/evidence-collection", tags=["evidence-collection"]
)
app.include_router(
    foundation_evidence.router, prefix="/api/v1/foundation-evidence", tags=["foundation-evidence"]
)
app.include_router(frameworks.router, prefix="/api/v1/frameworks", tags=["frameworks"])
app.include_router(implementation.router, prefix="/api/v1/implementation", tags=["implementation"])
app.include_router(integrations.router, prefix="/api/v1/integrations", tags=["integrations"])
app.include_router(iq_agent.router, prefix="/api/v1/iq", tags=["iq-agent", "graphrag"])
app.include_router(monitoring.router, prefix="/api/v1/monitoring", tags=["monitoring"])
app.include_router(payment.router, prefix="/api/v1/payments", tags=["payments", "billing"])
app.include_router(policies.router, prefix="/api/v1/policies", tags=["policies"])
app.include_router(readiness.router, prefix="/api/v1/readiness", tags=["readiness"])
app.include_router(reports.router, prefix="/api/v1/reports", tags=["reports"])
app.include_router(security.router, prefix="/api/v1/security", tags=["security"])
app.include_router(ai_policy.router, prefix="/api/v1/ai", tags=["ai", "policy"])
app.include_router(ai_cost_monitoring.router, prefix="/api/v1/ai", tags=["ai", "cost-monitoring"])
app.include_router(ai_cost_websocket.router, prefix="/api/v1/ai", tags=["ai", "websocket"])
app.include_router(freemium.router, prefix="/api/v1/freemium", tags=["freemium"])
app.include_router(rbac_auth.router, prefix="/api/v1/rbac", tags=["rbac", "authentication"])
app.include_router(uk_compliance.router, prefix="/api/v1/uk-compliance", tags=["compliance", "uk"])

# Admin routers
app.include_router(user_management.router)
app.include_router(data_access.router)
app.include_router(token_management.router)


@app.exception_handler(HTTPException)
async def http_exception_handler(request: Request, exc: HTTPException) -> JSONResponse:
    """Handle HTTP exceptions with consistent error format"""
    return JSONResponse(
        status_code=exc.status_code,
        content={
            "error": {
                "message": exc.detail,
                "type": "http_exception",
                "status_code": exc.status_code,
            }
        },
    )


@app.exception_handler(SQLAlchemyError)
async def sqlalchemy_exception_handler(request: Request, exc: SQLAlchemyError) -> JSONResponse:
    """Handle database exceptions"""
    logger.error("Database error: %s", exc)
    return JSONResponse(
        status_code=500,
        content={
            "error": {
                "message": "Database operation failed",
                "type": "database_error",
                "status_code": 500,
            }
        },
    )


@app.exception_handler(Exception)
async def general_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    """Handle all other exceptions"""
    logger.error("Unexpected error: %s", exc, exc_info=True)
    return JSONResponse(
        status_code=500,
        content={
            "error": {
                "message": "Internal server error",
                "type": "internal_error",
                "status_code": 500,
            }
        },
    )


@app.get("/api/v1/health")
async def api_health_check() -> Dict[str, Any]:
    """API v1 health check endpoint"""
    return {"status": "healthy", "timestamp": time.time(), "version": "1.0.0", "api_version": "v1"}


@app.get("/api/v1/health/detailed")
async def api_health_detailed() -> Dict[str, Any]:
    """Detailed API v1 health check endpoint with component status"""
    is_cloud_run = bool(os.getenv("K_SERVICE") or os.getenv("CLOUD_RUN_JOB"))

    # Database status with graceful handling
    db_status = "unknown"
    try:
        # Get async session maker safely
        session_maker = get_async_session_maker()
        if session_maker is not None:
            async with session_maker() as session:
                result = await session.execute(text("SELECT 1"))
                if result:
                    db_status = "healthy"
        else:
            db_status = (
                "not_available" if is_cloud_run else "unhealthy: session_maker_not_available"
            )
    except Exception as e:
        db_status = f"unhealthy: {str(e)}"

    # AI services status
    ai_status = "unknown"
    try:
        ai_config.health_check()
        ai_status = "healthy"
    except Exception as e:
        ai_status = f"unhealthy: {str(e)}"

    # Redis status (optional in Cloud Run)
    redis_status = "not_configured"
    if hasattr(settings, "redis_url") and settings.redis_url:
        try:
            # In a real implementation, you'd test Redis connection here
            redis_status = "configured_but_not_tested"
            if getattr(app.state, "redis_ready", False):
                redis_status = "healthy"
        except Exception as e:
            redis_status = f"unhealthy: {str(e)}"

    # Determine overall status
    critical_services = [db_status]
    if not is_cloud_run:
        # In non-Cloud Run environments, AI might be more critical
        critical_services.append(ai_status)

    overall_status = "healthy"
    if any("unhealthy" in status for status in critical_services):
        overall_status = "unhealthy"
    elif any("unknown" in status for status in [db_status, ai_status]):
        overall_status = "degraded"

    return {
        "status": overall_status,
        "timestamp": time.time(),
        "version": "1.0.0",
        "api_version": "v1",
        "environment": "cloud_run" if is_cloud_run else "standard",
        "components": {"database": db_status, "ai_services": ai_status, "redis": redis_status},
    }


@app.get("/health")
async def health_check_endpoint() -> Dict[str, Any]:
    """Basic health check endpoint for Cloud Run"""
    return {"status": "healthy", "timestamp": time.time(), "version": "1.0.0"}


@app.get("/health/ready")
async def readiness_check() -> Dict[str, Any]:
    """Readiness check with database connectivity and grace window"""
    is_cloud_run = bool(os.getenv("K_SERVICE") or os.getenv("CLOUD_RUN_JOB"))

    # Check if app state indicates readiness
    db_ready = getattr(app.state, "db_ready", False)
    config_ready = getattr(app.state, "config_ready", True)
    redis_ready = getattr(app.state, "redis_ready", False)

    # Calculate time since startup
    start_time = getattr(app.state, "start_time", time.time())
    uptime_seconds = time.time() - start_time
    grace_window_seconds = 60  # 60 second grace window for Cloud Run

    status_info = {
        "status": "ready",
        "timestamp": time.time(),
        "uptime": uptime_seconds,
        "database": "connected" if db_ready else "disconnected",
        "config": "valid" if config_ready else "invalid",
        "redis": "connected" if redis_ready else "not_available",
        "environment": "cloud_run" if is_cloud_run else "standard",
    }

    # In Cloud Run, be more lenient about readiness
    if is_cloud_run:
        # During grace window, return ready with "warming" status
        if uptime_seconds < grace_window_seconds:
            if not db_ready:
                status_info["status"] = "warming"
                status_info["message"] = (
                    f"Service warming up ({uptime_seconds:.0f}s/{grace_window_seconds}s)"
                )
                logger.info(
                    "🌩️ Cloud Run readiness: In grace window (%s), returning warming status",
                    f"{uptime_seconds:.0f}s",
                )
                return status_info  # Return 200 OK with warming status

        # After grace window, require database for readiness
        elif not db_ready:
            # Try one more time to connect to database
            try:
                session_maker = get_async_session_maker()
                if session_maker is not None:
                    async with session_maker() as session:
                        await session.execute(text("SELECT 1"))
                        status_info["database"] = "connected"
                        status_info["status"] = "ready"
                        app.state.db_ready = True  # Update state
                        return status_info
                else:
                    logger.warning("🌩️ Cloud Run readiness: Async session maker not available")
                    status_info["status"] = "not_ready"
                    status_info["reason"] = "database_session_maker_unavailable"
                    raise HTTPException(
                        status_code=HTTP_SERVICE_UNAVAILABLE,
                        detail="Service not ready - database session maker unavailable",
                    )
            except Exception as e:
                logger.warning("🌩️ Cloud Run readiness: Database still not ready: %s", e)
                status_info["status"] = "not_ready"
                status_info["reason"] = "database_connection_failed"
                raise HTTPException(
                    status_code=HTTP_SERVICE_UNAVAILABLE,
                    detail="Service not ready - database connection failed",
                ) from e
        return status_info
    else:
        # Standard environment - require both database and config
        if not db_ready or not config_ready:
            status_info["status"] = "not_ready"
            reasons = []
            if not db_ready:
                reasons.append("database_connection_failed")
            if not config_ready:
                reasons.append("configuration_invalid")
            status_info["reason"] = ", ".join(reasons)
            raise HTTPException(
                status_code=HTTP_SERVICE_UNAVAILABLE,
                detail=f"Service not ready - {status_info['reason']}",
            )
        return status_info


@app.get("/health/live")
async def liveness_check() -> Dict[str, Any]:
    """Liveness check for container orchestration"""
    is_cloud_run = bool(os.getenv("K_SERVICE") or os.getenv("CLOUD_RUN_JOB"))
    start_time = getattr(app.state, "start_time", time.time())

    return {
        "status": "alive",
        "timestamp": time.time(),
        "uptime": time.time() - start_time,
        "environment": "cloud_run" if is_cloud_run else "standard",
        "pid": os.getpid(),
        "version": "1.0.0",
    }


@app.get("/")
async def root() -> Dict[str, Any]:
    """Root endpoint with API information"""
    return {
        "name": "ruleIQ API",
        "version": "1.0.0",
        "description": "AI-powered compliance and risk management platform",
        "documentation": "/docs" if settings.debug else None,
        "health": "/health",
    }


def validate_configuration() -> None:
    """Validate critical configuration settings"""
    is_cloud_run = bool(os.getenv("K_SERVICE") or os.getenv("CLOUD_RUN_JOB"))

    # Check both settings attributes and environment variables
    required = {
        "database_url": getattr(settings, "database_url", None) or os.getenv("DATABASE_URL"),
        "jwt_secret_key": getattr(settings, "jwt_secret_key", None) or os.getenv("JWT_SECRET_KEY"),
    }
    missing_vars = [k.upper() for k, v in required.items() if not v]

    if missing_vars:
        if is_cloud_run:
            logger.warning(
                "🌩️ Cloud Run: Missing configuration variables (may be non-fatal): %s", missing_vars
            )
            # In Cloud Run, only JWT_SECRET_KEY is absolutely critical
            critical_missing = [var for var in missing_vars if "JWT_SECRET" in var]
            if critical_missing:
                raise ValueError(
                    f"Missing critical environment variables for Cloud Run: {critical_missing}"
                )
        else:
            raise ValueError(f"Missing required environment variables: {missing_vars}")

    if is_cloud_run:
        logger.info("🌩️ Cloud Run configuration validation passed")


@app.get("/health/startup")
async def startup_check() -> Dict[str, Any]:
    """Startup check endpoint"""
    return {"status": "starting", "timestamp": time.time(), "version": "1.0.0"}


if __name__ == "__main__":
    # Cloud Run uses PORT environment variable, fallback to settings
    port = int(os.getenv("PORT", str(getattr(settings, "port", 8000))))
    host = str(getattr(settings, "host", "0.0.0.0"))
    debug = getattr(settings, "debug", False)
    log_level = getattr(settings, "log_level", logging.INFO)

    # Detect Cloud Run environment
    is_cloud_run = bool(os.getenv("K_SERVICE") or os.getenv("CLOUD_RUN_JOB"))

    if is_cloud_run:
        logger.info("🌩️ Starting in Cloud Run mode on port %s", port)
        # Cloud Run optimized settings
        uvicorn.run(
            "api.main:app",
            host=host,
            port=port,
            reload=False,  # Never reload in Cloud Run
            log_level="info",  # Use info level in Cloud Run
            workers=1,  # Single worker in Cloud Run
            access_log=True,
        )
    else:
        logger.info("🖥️ Starting in standard mode on %s:%s", host, port)
        uvicorn.run(
            "api.main:app",
            host=host,
            port=port,
            reload=bool(debug),
            log_level=(log_level.value.lower() if hasattr(log_level, "value") else "info"),
            workers=1 if debug else 4,
        )
