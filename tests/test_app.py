"""Test app creation for isolated testing."""

from contextlib import asynccontextmanager
from fastapi import FastAPI, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from api.dependencies.auth import get_current_active_user
from database.db_setup import get_async_db
from database import User


@asynccontextmanager
async def test_lifespan(app: FastAPI):
    """Test lifespan - no database initialization."""
    print("Test app started")
    yield
    print("Test app shutdown")


def create_test_app() -> FastAPI:
    """Create a test-specific FastAPI app without lifespan issues."""
    app = FastAPI(
        title="ComplianceGPT Test API",
        lifespan=test_lifespan,
    )

    # Add error handler middleware
    from api.middleware.error_handler import error_handler_middleware

    app.middleware("http")(error_handler_middleware)

    # Add security headers middleware
    from api.middleware.security_headers import security_headers_middleware

    app.middleware("http")(security_headers_middleware)

    # Import routers after app creation to avoid circular imports
    from api.routers import (
        ai_assessments,
        ai_optimization,
        assessments,
        auth,
        business_profiles,
        chat,
        compliance,
        evidence,
        evidence_collection,
        foundation_evidence,
        frameworks,
        implementation,
        integrations,
        monitoring,
        policies,
        readiness,
        reporting,
        security,
        users,
    )

    # Include routers
    app.include_router(auth.router, prefix="/api/auth", tags=["Authentication"])
    app.include_router(users.router, prefix="/api/users", tags=["Users"])
    app.include_router(
        business_profiles.router,
        prefix="/api/business-profiles",
        tags=["Business Profiles"],
    )
    app.include_router(
        frameworks.router,
        prefix="/api/frameworks",
        tags=["Compliance Frameworks"],
    )
    app.include_router(
        assessments.router,
        prefix="/api/assessments",
        tags=["Assessments"],
    )
    app.include_router(
        readiness.router,
        prefix="/api/readiness",
        tags=["Readiness Assessment"],
    )
    app.include_router(policies.router, prefix="/api/policies", tags=["Policies"])
    app.include_router(
        implementation.router,
        prefix="/api/implementation",
        tags=["Implementation"],
    )
    app.include_router(evidence.router, prefix="/api/evidence", tags=["Evidence"])
    app.include_router(compliance.router, prefix="/api/compliance", tags=["Compliance"])
    app.include_router(reporting.router, prefix="/api/reports", tags=["Reporting"])
    app.include_router(security.router, prefix="/api/security", tags=["Security"])
    app.include_router(monitoring.router, prefix="/api/monitoring", tags=["Monitoring"])
    app.include_router(
        integrations.router,
        prefix="/api/integrations",
        tags=["Integrations"],
    )
    app.include_router(
        evidence_collection.router,
        prefix="/api/evidence-collection",
        tags=["Evidence Collection"],
    )
    app.include_router(
        foundation_evidence.router,
        prefix="/api/foundation-evidence",
        tags=["Foundation Evidence"],
    )
    app.include_router(ai_assessments.router, prefix="/api", tags=["AI Assessments"])
    app.include_router(
        ai_optimization.router,
        prefix="/api/ai-optimization",
        tags=["AI Optimization"],
    )
    app.include_router(chat.router, prefix="/api", tags=["Chat"])

    # Add health check
    @app.get("/api/health")
    async def health_check():
        return {"status": "healthy", "service": "ComplianceGPT Test API"}

    return app
