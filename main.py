"""
DEPRECATED: This file is kept for backward compatibility with existing tests.
The production entrypoint is api.main:app
To run the application, use: uvicorn api.main:app --host 0.0.0.0 --port 8080
"""

from typing import Any, AsyncGenerator, Dict
from contextlib import asynccontextmanager
import uvicorn
from fastapi import Depends, FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from middleware.cors_enhanced import EnhancedCORSMiddleware
from config.security_settings import get_security_settings
from api.dependencies.auth import get_current_active_user
from api.middleware.error_handler import error_handler_middleware
from api.request_id_middleware import RequestIDMiddleware
from api.routers import (
    auth,
    chat,
    compliance,
    evidence,
    frameworks,
    freemium,
    policies,
    readiness,
    reports,
    security,
    uk_compliance,
    users,
)
import logging

logger = logging.getLogger(__name__)
# Temporarily disabled: assessments, business_profiles (Pydantic forward reference issue)
# Temporarily disabled due to import errors: agentic_rag, ai_assessments, ai_cost_monitoring, ai_cost_websocket, ai_optimization, ai_policy, api_keys, dashboard, evidence_collection, feedback, foundation_evidence, google_auth, implementation, integrations, iq_agent, monitoring, payment, performance_monitoring, secrets_vault, test_utils, webhooks
from api.routers.admin import admin_router
from api.routers import rbac_auth
from api.schemas import APIInfoResponse, HealthCheckResponse
from config.logging_config import get_logger, setup_logging
from config.settings import settings
from database.db_setup import init_db, get_async_db
from database import User

setup_logging()
logger = get_logger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[Any, None]:
    logger.info("Starting ComplianceGPT API...")
    init_db()
    logger.info("Database tables created or verified.")
    from services.framework_service import initialize_default_frameworks

    try:
        async for db in get_async_db():
            await initialize_default_frameworks(db)
            break
        logger.info("Default frameworks initialized.")
    except Exception as e:
        logger.warning(f"Failed to initialize default frameworks: {e}")
    from config.cache import get_cache_manager

    cache_manager = await get_cache_manager()
    logger.info("Cache manager initialized.")

    # One-time cache migration from MD5 to SHA-256
    if settings.cache_migration_on_startup:
        try:
            from scripts.security_hash_migration import CacheMigrationManager

            # Create Redis client using cache manager's connection
            redis_client = cache_manager._redis  # Access the Redis client from cache manager

            # Create migration manager and invalidate old caches
            migration_manager = CacheMigrationManager(redis_client)
            result = await migration_manager.invalidate_md5_caches()

            logger.info(f"Cache migration completed: {result}")
            logger.info("Consider disabling cache_migration_on_startup after successful migration.")
        except Exception as e:
            logger.warning(f"Cache migration failed (non-critical): {e}")
    # Initialize agentic service
    from services.agentic_integration import initialize_agentic_service

    try:
        await initialize_agentic_service()
        logger.info("Agentic RAG service initialized.")
    except Exception as e:
        logger.warning(f"Failed to initialize agentic RAG service: {e}")
    from monitoring.database_monitor import get_database_monitor
    import asyncio

    try:
        monitor = get_database_monitor()
        monitoring_task = asyncio.create_task(monitor.start_monitoring_loop(interval_seconds=30))
        logger.info("Database monitoring service started with 30s interval")
        app.state.monitoring_task = monitoring_task
    except Exception as e:
        logger.warning(f"Failed to start database monitoring: {e}")
    logger.info(f"Environment: {settings.environment}")
    logger.info(f"Debug mode: {settings.debug}")
    yield
    logger.info("Shutting down ComplianceGPT API...")
    if hasattr(app.state, "monitoring_task"):
        try:
            app.state.monitoring_task.cancel()
            await app.state.monitoring_task
        except asyncio.CancelledError:
            logger.info("Database monitoring task cancelled successfully")
        except Exception as e:
            logger.warning(f"Error cancelling monitoring task: {e}")


app = FastAPI(
    title="ruleIQ Compliance Automation API",
    description="\n    **ruleIQ API** provides comprehensive compliance automation for UK Small and Medium Businesses (SMBs).\n\n    ## Features\n    - 🤖 **AI-Powered Assessments** with 6 specialized AI tools\n    - 📋 **Policy Generation** with 25+ compliance frameworks\n    - 📁 **Evidence Management** with automated validation\n    - 🔐 **RBAC Security** with JWT authentication\n    - 📊 **Real-time Analytics** and compliance scoring\n\n    ## Authentication\n    All endpoints require JWT bearer token authentication except `/api/auth/*` endpoints.\n\n    Get your access token via `/api/auth/token` endpoint.\n\n    ## Rate Limiting\n    - **General endpoints**: 100 requests/minute\n    - **AI endpoints**: 3-20 requests/minute (tiered)\n    - **Authentication**: 5 requests/minute\n\n    ## Support\n    - **Documentation**: See `/docs/api/` for detailed guides\n    - **Interactive Testing**: Use this Swagger UI to test endpoints\n    - **Status**: Production-ready (98% complete, 671+ tests)\n    ",
    version="2.0.0",
    docs_url="/docs",
    redoc_url="/redoc",
    openapi_url="/openapi.json",
    lifespan=lifespan,
    contact={
        "name": "ruleIQ API Support",
        "url": "https://docs.ruleiq.com",
        "email": "api-support@ruleiq.com",
    },
    license_info={"name": "Proprietary", "url": "https://ruleiq.com/license"},
    servers=[
        {"url": "http://localhost:8000", "description": "Development server"},
        {"url": "https://api.ruleiq.com", "description": "Production server"},
    ],
)
# Configure CORS based on environment
security_settings = get_security_settings()
if security_settings.is_production:
    # Use enhanced CORS middleware for production
    app.add_middleware(EnhancedCORSMiddleware)
    logger.info("Using enhanced CORS middleware with production settings")
else:
    # Use standard CORS for development/testing with explicit lists
    cors_config = security_settings.get_cors_config()
    app.add_middleware(
        CORSMiddleware,
        allow_origins=cors_config["allow_origins"],
        allow_credentials=cors_config["allow_credentials"],
        allow_methods=cors_config["allow_methods"],
        allow_headers=cors_config["allow_headers"],
        expose_headers=cors_config["expose_headers"],
        max_age=cors_config["max_age"],
    )
    logger.info(f"Using standard CORS middleware for {security_settings.environment}")
app.add_middleware(RequestIDMiddleware)
app.middleware("http")(error_handler_middleware)
from api.middleware.rbac_middleware import RBACMiddleware

app.add_middleware(RBACMiddleware, enable_audit_logging=True)
from api.middleware.rate_limiter import rate_limit_middleware

app.middleware("http")(rate_limit_middleware)

# Add JWT Authentication Middleware v2 (SEC-001 compliance)
# JWT middleware v2 enabled
from middleware.jwt_auth_v2 import JWTAuthMiddlewareV2

app.add_middleware(JWTAuthMiddlewareV2())

# Add Comprehensive Audit Logging Middleware
from middleware.audit_logging import setup_audit_logging

audit_logger = setup_audit_logging(app)

from middleware.security_middleware import SecurityMiddleware
from middleware.security_headers import SecurityHeadersMiddleware

app.add_middleware(
    SecurityHeadersMiddleware,
    csp_enabled=True,
    cors_enabled=False,
    nonce_enabled=True,
    report_uri="/api/security/csp-report",
)
# Note: SecurityMiddleware auth is disabled as JWT middleware handles authentication
security_middleware = SecurityMiddleware(
    app=app,
    enable_auth=False,
    enable_authz=False,
    enable_audit=True,
    enable_encryption=True,
    enable_sql_protection=True,
    public_paths=[
        "/docs",
        "/openapi.json",
        "/health",
        "/api/v1/auth/login",
        "/api/v1/auth/register",
        "/api/v1/freemium/leads",
        "/api/v1/freemium/sessions",
    ],
)
app.middleware("http")(security_middleware)


@app.middleware("http")
async def add_rate_limit_headers_middleware(request: Request, call_next) -> Dict[str, Any]:
    """Add rate limit headers from request.state to responses."""
    response = await call_next(request)
    if hasattr(request.state, "rate_limit_headers"):
        for header, value in request.state.rate_limit_headers.items():
            response.headers[header] = value
    return response


app.include_router(auth.router, prefix="/api/v1/auth", tags=["Authentication"])
app.include_router(google_auth.router, prefix="/api/v1/auth/google", tags=["Google OAuth"])
app.include_router(rbac_auth.router, prefix="/api/v1/auth", tags=["RBAC Authentication"])
app.include_router(users.router, prefix="/api/v1/users", tags=["Users"])
# app.include_router(business_profiles.router, prefix='/api/v1/business-profiles', tags=['Business Profiles'])  # Temporarily disabled
# app.include_router(assessments.router, prefix='/api/v1/assessments', tags=['Assessments'])  # Temporarily disabled
from api.routers import usage_dashboard, audit_export

app.include_router(usage_dashboard.router, prefix="/api/v1", tags=["Usage Dashboard"])
app.include_router(audit_export.router, prefix="/api/v1", tags=["Audit Export"])
app.include_router(freemium.router, prefix="/api/v1", tags=["Freemium Assessment"])
app.include_router(ai_assessments.router, prefix="/api/v1/ai", tags=["AI Assessment Assistant"])
app.include_router(
    ai_optimization.router, prefix="/api/v1/ai/optimization", tags=["AI Optimization"]
)
app.include_router(frameworks.router, prefix="/api/v1/frameworks", tags=["Compliance Frameworks"])
app.include_router(policies.router, prefix="/api/v1/policies", tags=["Policies"])
app.include_router(
    implementation.router, prefix="/api/v1/implementation", tags=["Implementation Plans"]
)
app.include_router(evidence.router, prefix="/api/v1/evidence", tags=["Evidence"])
app.include_router(
    evidence_collection.router, prefix="/api/v1/evidence-collection", tags=["Evidence Collection"]
)
app.include_router(compliance.router, prefix="/api/v1/compliance", tags=["Compliance Status"])
app.include_router(readiness.router, prefix="/api/v1/readiness", tags=["Readiness Assessment"])
app.include_router(reports.router, prefix="/api/v1/reports", tags=["Reports"])
app.include_router(integrations.router, prefix="/api/v1/integrations", tags=["Integrations"])
app.include_router(
    foundation_evidence.router,
    prefix="/api/v1/foundation/evidence",
    tags=["Foundation Evidence Collection"],
)
app.include_router(dashboard.router, prefix="/api/v1/dashboard", tags=["Dashboard"])
app.include_router(payment.router, prefix="/api/v1/payments", tags=["Payments"])
app.include_router(monitoring.router, prefix="/api/v1/monitoring", tags=["Monitoring"])
app.include_router(security.router, prefix="/api/v1/security", tags=["Security"])
app.include_router(api_keys.router, tags=["API Keys"])
app.include_router(webhooks.router, tags=["Webhooks"])
app.include_router(secrets_vault.router, tags=["🔐 Secrets Vault"])
app.include_router(chat.router, prefix="/api/v1/chat", tags=["AI Assistant"])
app.include_router(ai_cost_monitoring.router, prefix="/api/v1/ai/cost", tags=["AI Cost Monitoring"])
app.include_router(feedback.router, prefix="/api/v1/feedback", tags=["Human Feedback"])
app.include_router(
    ai_cost_websocket.router, prefix="/api/v1/ai/cost-websocket", tags=["AI Cost WebSocket"]
)
app.include_router(ai_policy.router, prefix="/api/v1/ai/policies", tags=["AI Policy Generation"])
app.include_router(
    performance_monitoring.router, prefix="/api/v1/performance", tags=["Performance Monitoring"]
)
app.include_router(uk_compliance.router, prefix="/api/v1/uk-compliance", tags=["UK Compliance"])
app.include_router(iq_agent.router, prefix="/api/v1/iq-agent", tags=["IQ Agent"])
app.include_router(agentic_rag.router, prefix="/api/v1/agentic-rag", tags=["Agentic RAG"])
app.include_router(admin_router)
import os

if os.getenv("ENVIRONMENT", "production").lower() in ["development", "test", "testing", "local"]:
    app.include_router(test_utils.router, prefix="/api/test-utils", tags=["Test Utilities"])


@app.get("/api/dashboard")
async def get_dashboard(current_user: User = Depends(get_current_active_user)) -> Dict[str, Any]:
    """Get user dashboard data"""
    return {
        "user": {
            "id": current_user["id"],
            "email": current_user["primaryEmail"],
            "name": current_user.get("displayName", ""),
        },
        "stats": {"assessments": 0, "policies": 0, "compliance_score": 0, "recent_activities": []},
    }


@app.get("/", response_model=APIInfoResponse, summary="API Information")
async def root() -> Any:
    """Get basic API information"""
    return APIInfoResponse(message="ComplianceGPT API", version="1.0.0", status="operational")


@app.get("/health", response_model=HealthCheckResponse, summary="Health Check")
async def health_check() -> Any:
    """Check API health status with database monitoring"""
    try:
        from datetime import datetime, timezone
        from database.db_setup import get_engine_info
        from monitoring.database_monitor import get_database_monitor

        monitor = get_database_monitor()
        monitoring_summary = monitor.get_monitoring_summary()
        engine_info = get_engine_info()
        current_metrics = monitoring_summary.get("current_metrics", {})
        alerts = monitoring_summary.get("alerts", [])
        critical_alerts = len([a for a in alerts if a.get("severity") == "critical"])
        warning_alerts = len([a for a in alerts if a.get("severity") == "warning"])
        if critical_alerts > 0:
            status = "degraded"
            message = f"Critical database issues detected ({critical_alerts} alerts)"
        elif warning_alerts > 0:
            status = "warning"
            message = f"Database warnings detected ({warning_alerts} alerts)"
        elif not engine_info.get("async_engine_initialized"):
            status = "degraded"
            message = "Database engine not properly initialized"
        else:
            status = "healthy"
            message = "All systems operational"
        pool_utilization = 0
        active_sessions = 0
        for _pool_type, metrics in current_metrics.items():
            if metrics:
                pool_utilization = max(pool_utilization, metrics.get("utilization_percent", 0))
        recent_averages = monitoring_summary.get("recent_averages", {})
        for key, value in recent_averages.items():
            if "active_sessions" in key:
                active_sessions = value
                break
        health_data = {
            "status": status,
            "message": message,
            "database": {
                "engine_initialized": engine_info.get("async_engine_initialized", False),
                "pool_utilization": pool_utilization,
                "active_sessions": active_sessions,
                "recent_alerts": {
                    "critical": critical_alerts,
                    "warning": warning_alerts,
                    "total": len(alerts),
                },
            },
            "timestamp": monitoring_summary.get(
                "timestamp", datetime.now(timezone.utc).isoformat()
            ),
        }
        return HealthCheckResponse(**health_data)
    except Exception as e:
        logger.error(f"Health check failed: {e}")
        return HealthCheckResponse(status="error", message=f"Health check failed: {e!s}")


@app.get("/debug-suite", include_in_schema=False)
async def serve_debug_suite() -> Any:
    """Serve the API debug suite HTML file"""
    import os
    from fastapi.responses import FileResponse

    debug_file_path = os.path.join(os.getcwd(), "debug-suite.html")
    if os.path.exists(debug_file_path):
        return FileResponse(debug_file_path, media_type="text/html")
    else:
        raise HTTPException(status_code=404, detail="Debug suite not found")


@app.get("/api/v1/health", response_model=HealthCheckResponse, summary="API v1 Health Check")
async def api_health_check() -> Any:
    """API v1 health check endpoint"""
    from datetime import datetime, timezone

    return HealthCheckResponse(
        status="healthy",
        message="API v1 operational",
        timestamp=datetime.now(timezone.utc).isoformat(),
        version="2.0.0",
    )


@app.get(
    "/api/v1/health/detailed",
    response_model=HealthCheckResponse,
    summary="Detailed API v1 Health Check",
)
async def api_detailed_health_check() -> Any:
    """API v1 detailed health check with comprehensive monitoring"""
    from datetime import datetime, timezone
    from database.db_setup import get_engine_info
    from monitoring.database_monitor import get_database_monitor
    from config.cache import get_cache_manager

    engine_info = get_engine_info()
    cache_health = {"status": "unknown", "connected": False, "message": "Cache not available"}
    try:
        cache_manager = await get_cache_manager()
        if cache_manager:
            await cache_manager.redis_client.ping()
            cache_health = {
                "status": "healthy",
                "connected": True,
                "message": "Redis cache operational",
            }
    except Exception as e:
        cache_health = {"status": "error", "connected": False, "message": f"Cache error: {e!s}"}
    monitor = get_database_monitor()
    monitoring_summary = monitor.get_monitoring_summary() if monitor else {}
    current_metrics = monitoring_summary.get("current_metrics", {})
    alerts = monitoring_summary.get("alerts", [])
    critical_alerts = len([a for a in alerts if a.get("severity") == "critical"])
    warning_alerts = len([a for a in alerts if a.get("severity") == "warning"])
    if critical_alerts > 0:
        overall_status = "degraded"
        overall_message = f"System degraded: {critical_alerts} critical issues"
    elif warning_alerts > 0:
        overall_status = "warning"
        overall_message = f"System operational with warnings: {warning_alerts} warnings"
    elif not engine_info.get("async_engine_initialized") or cache_health["status"] != "healthy":
        overall_status = "degraded"
        overall_message = "Some services not fully operational"
    else:
        overall_status = "healthy"
        overall_message = "All services operational"
    pool_utilization = 0
    active_sessions = 0
    for _pool_type, metrics in current_metrics.items():
        if metrics:
            pool_utilization = max(pool_utilization, metrics.get("utilization_percent", 0))
    recent_averages = monitoring_summary.get("recent_averages", {})
    for key, value in recent_averages.items():
        if "active_sessions" in key:
            active_sessions = value
            break
    detailed_health = {
        "status": overall_status,
        "message": overall_message,
        "version": "2.0.0",
        "environment": settings.environment,
        "database": {
            "status": "healthy" if engine_info.get("async_engine_initialized") else "degraded",
            "engine_initialized": engine_info.get("async_engine_initialized", False),
            "pool_utilization": pool_utilization,
            "active_sessions": active_sessions,
            "recent_alerts": {
                "critical": critical_alerts,
                "warning": warning_alerts,
                "total": len(alerts),
            },
        },
        "cache": cache_health,
        "monitoring": {
            "enabled": monitor is not None,
            "last_check": monitoring_summary.get(
                "timestamp", datetime.now(timezone.utc).isoformat()
            ),
            "metrics_available": bool(current_metrics),
        },
        "services": {
            "frameworks": {"status": "operational", "total": 25},
            "ai_assistant": {"status": "operational", "models": 6},
            "authentication": {"status": "operational", "method": "JWT + RBAC"},
        },
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }
    return HealthCheckResponse(**detailed_health)


@app.get("/api/v1/ping", summary="Simple Ping Endpoint")
async def ping() -> Dict[str, str]:
    """Simple ping endpoint for connectivity testing"""
    return {"status": "pong", "message": "API is responsive"}


if __name__ == "__main__":
    import sys

    host = "0.0.0.0"
    port = 8000
    reload = False
    for i, arg in enumerate(sys.argv[1:], 1):
        if arg == "--host" and i < len(sys.argv) - 1:
            host = sys.argv[i + 1]
        elif arg == "--port" and i < len(sys.argv) - 1:
            try:
                port = int(sys.argv[i + 1])
            except ValueError:
                logger.error(f"Invalid port: {sys.argv[i + 1]}")
                sys.exit(1)
        elif arg == "--reload":
            reload = True
    logger.info(f"Starting server on {host}:{port} (reload={reload})")
    uvicorn.run(
        "main:app" if reload else app,
        host=host,
        port=port,
        reload=reload,
        log_level="info" if settings.debug else "warning",
    )
