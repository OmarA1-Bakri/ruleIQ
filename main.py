from contextlib import asynccontextmanager

import uvicorn
from fastapi import Depends, FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware

from api.dependencies.auth import get_current_active_user

from api.middleware.error_handler import error_handler_middleware
from api.request_id_middleware import RequestIDMiddleware
from api.routers import (
    # agentic_assessments,
    agentic_rag,
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
    google_auth,
    implementation,
    integrations,
    iq_agent,  # Added missing IQ Agent import
    monitoring,
    performance_monitoring,
    policies,
    readiness,
    reporting,
    security,
    secrets_vault,
    test_utils,
    uk_compliance,
    users,
)
from api.routers.admin import admin_router
from api.routers import rbac_auth
from api.schemas import APIInfoResponse, HealthCheckResponse
from config.logging_config import get_logger, setup_logging
from config.settings import settings
from database.db_setup import init_db, get_async_db
from database import User  # Import all models through the database package

# Setup logging
setup_logging()
logger = get_logger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    logger.info("Starting ComplianceGPT API...")
    init_db()
    logger.info("Database tables created or verified.")

    # Initialize default frameworks
    from services.framework_service import initialize_default_frameworks

    try:
        async for db in get_async_db():
            await initialize_default_frameworks(db)
            break  # Only need one iteration
        logger.info("Default frameworks initialized.")
    except Exception as e:
        logger.warning(f"Failed to initialize default frameworks: {e}")

    # Initialize cache manager
    from config.cache import get_cache_manager
    await get_cache_manager()
    logger.info("Cache manager initialized.")

    # Initialize agentic integration service
    from services.agentic_integration import initialize_agentic_service
    try:
        await initialize_agentic_service()
        logger.info("Agentic RAG service initialized.")
    except Exception as e:
        logger.warning(f"Failed to initialize agentic RAG service: {e}")

    # Initialize database monitoring service
    from monitoring.database_monitor import get_database_monitor
    import asyncio

    try:
        # Start the database monitoring background task
        monitor = get_database_monitor()
        monitoring_task = asyncio.create_task(monitor.start_monitoring_loop(interval_seconds=30))
        logger.info("Database monitoring service started with 30s interval")

        # Store the task reference for cleanup
        app.state.monitoring_task = monitoring_task
    except Exception as e:
        logger.warning(f"Failed to start database monitoring: {e}")

    logger.info(f"Environment: {settings.environment}")
    logger.info(f"Debug mode: {settings.debug}")
    yield

    # Shutdown
    logger.info("Shutting down ComplianceGPT API...")

    # Cancel monitoring task if it exists
    if hasattr(app.state, 'monitoring_task'):
        try:
            app.state.monitoring_task.cancel()
            await app.state.monitoring_task
        except asyncio.CancelledError:
            logger.info("Database monitoring task cancelled successfully")
        except Exception as e:
            logger.warning(f"Error cancelling monitoring task: {e}")


app = FastAPI(
    title="ruleIQ Compliance Automation API",
    description="""
    **ruleIQ API** provides comprehensive compliance automation for UK Small and Medium Businesses (SMBs).

    ## Features
    - 🤖 **AI-Powered Assessments** with 6 specialized AI tools
    - 📋 **Policy Generation** with 25+ compliance frameworks
    - 📁 **Evidence Management** with automated validation
    - 🔐 **RBAC Security** with JWT authentication
    - 📊 **Real-time Analytics** and compliance scoring

    ## Authentication
    All endpoints require JWT bearer token authentication except `/api/auth/*` endpoints.

    Get your access token via `/api/auth/token` endpoint.

    ## Rate Limiting
    - **General endpoints**: 100 requests/minute
    - **AI endpoints**: 3-20 requests/minute (tiered)
    - **Authentication**: 5 requests/minute

    ## Support
    - **Documentation**: See `/docs/api/` for detailed guides
    - **Interactive Testing**: Use this Swagger UI to test endpoints
    - **Status**: Production-ready (98% complete, 671+ tests)
    """,
    version="2.0.0",
    docs_url="/docs",
    redoc_url="/redoc",
    openapi_url="/openapi.json",
    lifespan=lifespan,
    contact={
        "name": "ruleIQ API Support",
        "url": "https://docs.ruleiq.com",
        "email": "api-support@ruleiq.com"
    },
    license_info={
        "name": "Proprietary",
        "url": "https://ruleiq.com/license"
    },
    servers=[
        {
            "url": "http://localhost:8000",
            "description": "Development server"
        },
        {
            "url": "https://api.ruleiq.com",
            "description": "Production server"
        }
    ]
)


# CORS configuration
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_allowed_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Custom middleware
app.add_middleware(RequestIDMiddleware)
app.middleware("http")(error_handler_middleware)


# RBAC middleware for role-based access control
from api.middleware.rbac_middleware import RBACMiddleware

app.add_middleware(RBACMiddleware, enable_audit_logging=True)

# Rate limiting
from api.middleware.rate_limiter import rate_limit_middleware

app.middleware("http")(rate_limit_middleware)

# Security headers
from api.middleware.security_headers import security_headers_middleware

app.middleware("http")(security_headers_middleware)

# Include routers
app.include_router(auth.router, prefix="/api/v1/auth", tags=["Authentication"])
app.include_router(google_auth.router, prefix="/api/v1/auth", tags=["Google OAuth"])
app.include_router(rbac_auth.router, tags=["RBAC Authentication"])
app.include_router(users.router, prefix="/api/v1/users", tags=["Users"])
app.include_router(
    business_profiles.router, prefix="/api/v1/business-profiles", tags=["Business Profiles"]
)
app.include_router(assessments.router, prefix="/api/v1/assessments", tags=["Assessments"])
app.include_router(freemium.router, prefix="/api/v1", tags=["Freemium Assessment"])
# DEPRECATED: app.include_router(ai_assessments.router, prefix="/api/v1/ai-assessments", tags=["AI Assessment Assistant"])
# Backward compatibility for legacy tests - old /api/ai/assessments structure  
# DEPRECATED: app.include_router(ai_assessments.router, prefix="/api/ai/assessments", tags=["AI Assessment Assistant (Legacy)"])
app.include_router(ai_optimization.router, prefix="/api/v1/ai/optimization", tags=["AI Optimization"])
app.include_router(frameworks.router, prefix="/api/v1/frameworks", tags=["Compliance Frameworks"])
app.include_router(policies.router, prefix="/api/v1/policies", tags=["Policies"])
app.include_router(
    implementation.router, prefix="/api/v1/implementation", tags=["Implementation Plans"]
)
app.include_router(evidence.router, prefix="/api/v1/evidence", tags=["Evidence"])
app.include_router(evidence_collection.router, prefix="/api/v1/evidence-collection", tags=["Evidence Collection"])
app.include_router(compliance.router, prefix="/api/v1/compliance", tags=["Compliance Status"])
app.include_router(readiness.router, prefix="/api/v1/readiness", tags=["Readiness Assessment"])
app.include_router(reporting.router, prefix="/api/v1/reports", tags=["Reports"])
app.include_router(integrations.router, prefix="/api/v1/integrations", tags=["Integrations"])
app.include_router(
    foundation_evidence.router, prefix="/api/v1/foundation-evidence", tags=["Foundation Evidence Collection"]
)
app.include_router(monitoring.router, prefix="/api/v1/monitoring", tags=["Monitoring"])
app.include_router(security.router, prefix="/api/v1/security", tags=["Security"])
app.include_router(secrets_vault.router, tags=["🔐 Secrets Vault"])
app.include_router(chat.router, prefix="/api/v1/chat", tags=["AI Assistant"])
app.include_router(ai_cost_monitoring.router, prefix="/api/v1/ai/cost", tags=["AI Cost Monitoring"])
app.include_router(ai_cost_websocket.router, prefix="/api/v1/ai/cost-websocket", tags=["AI Cost WebSocket"])
app.include_router(ai_policy.router, prefix="/api/v1/ai/policies", tags=["AI Policy Generation"])
app.include_router(performance_monitoring.router, prefix="/api/v1/performance", tags=["Performance Monitoring"])
app.include_router(uk_compliance.router, prefix="/api/v1/uk-compliance", tags=["UK Compliance"])
app.include_router(iq_agent.router, prefix="/api/v1/iq-agent", tags=["IQ Agent"])
# app.include_router(agentic_assessments.router, prefix="/api", tags=["Agentic Assessments"])
app.include_router(agentic_rag.router, prefix="/api/v1", tags=["Agentic RAG"])
app.include_router(admin_router)

# Test utilities (only in development/test environments)
import os
if os.getenv("ENVIRONMENT", "production").lower() in ["development", "test", "testing", "local"]:
    app.include_router(test_utils.router, prefix="/api/test-utils", tags=["Test Utilities"])


@app.get("/api/dashboard")
async def get_dashboard(
    current_user: User = Depends(get_current_active_user)
):
    """Get user dashboard data"""
    # For now, return a simple response
    # In production, you'd fetch real data based on the user
    return {
        "user": {
            "id": current_user["id"],
            "email": current_user["primaryEmail"],
            "name": current_user.get("displayName", "")
        },
        "stats": {
            "assessments": 0,
            "policies": 0,
            "compliance_score": 0,
            "recent_activities": []
        }
    }


@app.get("/", response_model=APIInfoResponse, summary="API Information")
async def root():
    """Get basic API information"""
    return APIInfoResponse(message="ComplianceGPT API", version="1.0.0", status="operational")


@app.get("/health", response_model=HealthCheckResponse, summary="Health Check")
async def health_check():
    """Check API health status with database monitoring"""
    try:
        from datetime import datetime
        from database.db_setup import get_engine_info
        from monitoring.database_monitor import get_database_monitor

        # Get database monitoring status from the new enhanced monitor
        monitor = get_database_monitor()
        monitoring_summary = monitor.get_monitoring_summary()

        # Get basic database engine info
        engine_info = get_engine_info()

        # Extract key metrics from monitoring summary
        current_metrics = monitoring_summary.get("current_metrics", {})
        alerts = monitoring_summary.get("alerts", [])

        # Count alerts by severity
        critical_alerts = len([a for a in alerts if a.get("severity") == "critical"])
        warning_alerts = len([a for a in alerts if a.get("severity") == "warning"])

        # Determine overall health based on new monitoring system
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

        # Get pool utilization from either sync or async pool
        pool_utilization = 0
        active_sessions = 0

        for pool_type, metrics in current_metrics.items():
            if metrics:
                pool_utilization = max(pool_utilization, metrics.get("utilization_percent", 0))

        # Get session metrics if available
        recent_averages = monitoring_summary.get("recent_averages", {})
        for key, value in recent_averages.items():
            if "active_sessions" in key:
                active_sessions = value
                break

        # Include enhanced monitoring data in health response
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
                    "total": len(alerts)
                },
            },
            "timestamp": monitoring_summary.get("timestamp", datetime.utcnow().isoformat()),
        }

        return HealthCheckResponse(**health_data)

    except Exception as e:
        logger.error(f"Health check failed: {e}")
        return HealthCheckResponse(status="error", message=f"Health check failed: {e!s}")


@app.get("/debug-suite", include_in_schema=False)
async def serve_debug_suite():
    """Serve the API debug suite HTML file"""
    import os
    from fastapi.responses import FileResponse

    debug_file_path = os.path.join(os.getcwd(), "debug-suite.html")
    if os.path.exists(debug_file_path):
        return FileResponse(debug_file_path, media_type="text/html")
    else:
        raise HTTPException(status_code=404, detail="Debug suite not found")


@app.get("/api/v1/health", response_model=HealthCheckResponse, summary="API v1 Health Check")
async def api_health_check():
    """API v1 health check endpoint"""
    from datetime import datetime
    return HealthCheckResponse(
        status="healthy",
        message="API v1 operational",
        timestamp=datetime.utcnow().isoformat(),
        version="2.0.0"
    )


@app.get("/api/v1/health/detailed", response_model=HealthCheckResponse, summary="Detailed API v1 Health Check")
async def api_detailed_health_check():
    """Detailed API v1 health check with component status"""
    try:
        from datetime import datetime
        from database.db_setup import get_engine_info
        from monitoring.database_monitor import get_database_monitor

        # Get database monitoring status
        monitor = get_database_monitor()
        monitoring_summary = monitor.get_monitoring_summary()

        # Get basic database engine info
        engine_info = get_engine_info()

        # Extract key metrics from monitoring summary
        current_metrics = monitoring_summary.get("current_metrics", {})
        alerts = monitoring_summary.get("alerts", [])

        # Count alerts by severity
        critical_alerts = len([a for a in alerts if a.get("severity") == "critical"])
        warning_alerts = len([a for a in alerts if a.get("severity") == "warning"])

        # 🔐 Check SecretsVault health status
        vault_health = settings.get_secrets_vault_health()
        vault_healthy = vault_health.get("status") == "healthy"

        # Determine overall status
        if critical_alerts > 0:
            status = "degraded"
            message = f"Critical database issues detected ({critical_alerts} alerts)"
        elif warning_alerts > 0:
            status = "warning"
            message = f"Database warnings detected ({warning_alerts} alerts)"
        elif not engine_info.get("async_engine_initialized"):
            status = "degraded"
            message = "Database engine not properly initialized"
        elif not vault_healthy and vault_health.get("status") != "disabled":
            status = "warning"
            message = f"SecretsVault health issue: {vault_health.get('message', 'Unknown vault error')}"
        else:
            status = "healthy"
            message = "All API v1 components operational"

        health_data = {
            "status": status,
            "message": message,
            "timestamp": datetime.utcnow().isoformat(),
            "version": "2.0.0",
            "api_version": "v1",
            "database": {
                "engine_initialized": engine_info.get("async_engine_initialized", False),
                "recent_alerts": {
                    "critical": critical_alerts,
                    "warning": warning_alerts,
                    "total": len(alerts)
                },
            },
            # 🔐 SecretsVault status in health check - easily identifiable
            "secrets_vault": {
                "status": vault_health.get("status", "unknown"),
                "enabled": vault_health.get("enabled", False),
                "vault_type": vault_health.get("vault_type", "None"),
                "region": vault_health.get("region", settings.secrets_vault_region),
                "message": vault_health.get("message", "No vault information available")
            },
        }

        return HealthCheckResponse(**health_data)

    except Exception as e:
        logger.error(f"API v1 detailed health check failed: {e}")
        return HealthCheckResponse(
            status="error",
            message=f"API v1 health check failed: {e!s}",
            timestamp=datetime.utcnow().isoformat(),
            version="2.0.0"
        )


if __name__ == "__main__":
    uvicorn.run("main:app", host=settings.host, port=settings.port, reload=settings.is_development)
