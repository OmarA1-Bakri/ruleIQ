"""
Vercel serverless handler for RuleIQ API
"""

import os
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

# Runtime override for serverless DB sessions on Vercel
IS_VERCEL = os.getenv('VERCEL') == '1' or os.getenv('VERCEL_ENV') is not None
if IS_VERCEL:
    from database import db_setup as pooled_db
    from database.serverless_db import get_db_session as serverless_get_db_session
    # Route all legacy imports to serverless sessions when on Vercel
    pooled_db.get_db_session = serverless_get_db_session

from api.routers import (
    assessments,
    auth,
    business_profiles,
    chat,
    compliance,
    evidence,
    frameworks,
    freemium,
    policies,
    rbac_auth,
    readiness,
    reports,
    security,
    uk_compliance,
    users,
)
from api.routers.admin import admin_router
from database.serverless_db import (
    test_database_connection,
    cleanup_connections,
)

# Create FastAPI app
app = FastAPI(title="RuleIQ API", version="1.0.0", description="Compliance automation platform API")

# Configure CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Configure based on your needs
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Add security headers middleware
@app.middleware("http")
async def add_security_headers(request, call_next):
    response = await call_next(request)
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
    response.headers["X-XSS-Protection"] = "1; mode=block"
    return response


# Add cleanup middleware for serverless DB connections
@app.middleware("http")
async def cleanup_db_after_request(request, call_next):
    """Cleanup database connections after each request in serverless environment."""
    try:
        response = await call_next(request)
        return response
    finally:
        # Always cleanup connections at the end of request
        cleanup_connections()

# Include routers with /api/v1/* prefix to match existing API contract
app.include_router(auth.router, prefix="/api/v1/auth", tags=["Authentication"])
app.include_router(users.router, prefix="/api/v1/users", tags=["Users"])
app.include_router(assessments.router, prefix="/api/v1/assessments", tags=["Assessments"])
app.include_router(frameworks.router, prefix="/api/v1/frameworks", tags=["Frameworks"])
app.include_router(compliance.router, prefix="/api/v1/compliance", tags=["Compliance"])
app.include_router(policies.router, prefix="/api/v1/policies", tags=["Policies"])
app.include_router(evidence.router, prefix="/api/v1/evidence", tags=["Evidence"])
app.include_router(reports.router, prefix="/api/v1/reports", tags=["Reports"])
app.include_router(chat.router, prefix="/api/v1/chat", tags=["Chat"])
app.include_router(freemium.router, prefix="/api/v1/freemium", tags=["Freemium"])
app.include_router(business_profiles.router, prefix="/api/v1/business-profiles", tags=["Business Profiles"])
app.include_router(readiness.router, prefix="/api/v1/readiness", tags=["Readiness"])
app.include_router(security.router, prefix="/api/v1/security", tags=["Security"])
app.include_router(uk_compliance.router, prefix="/api/v1/uk-compliance", tags=["UK Compliance"])
app.include_router(rbac_auth.router, prefix="/api/v1/rbac", tags=["RBAC"])
app.include_router(admin_router, prefix="/api/v1/admin", tags=["Admin"])


@app.get("/")
def read_root():
    return {"message": "RuleIQ API is running on Vercel"}


@app.get("/health")
def health_check():
    """Health check endpoint with database connectivity check."""
    checks = {
        "status": "healthy",
        "database": "connected" if test_database_connection() else "unavailable"
    }
    return checks


@app.get("/api/v1/health/database")
def database_health():
    from database.serverless_db import test_database_connection
    ok = test_database_connection()
    return {"database": "connected" if ok else "unavailable"}


# Vercel expects 'app' as the handler
handler = app
