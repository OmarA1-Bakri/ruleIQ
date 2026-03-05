#!/usr/bin/env python3
"""
Production startup script for RuleIQ
Uses the working simple_start app with health endpoints
"""
import os
import sys
from concurrent.futures import ThreadPoolExecutor, TimeoutError as FutureTimeoutError
from pathlib import Path
from sqlalchemy import text

# Add project root to Python path
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

def create_production_app():
    """Create production FastAPI app with all necessary endpoints"""
    from fastapi import FastAPI, HTTPException
    from fastapi.middleware.cors import CORSMiddleware
    from fastapi.middleware.gzip import GZipMiddleware
    from database.session import SessionLocal

    def check_db_connection() -> None:
        db = SessionLocal()
        try:
            db.execute(text("SELECT 1"))
        finally:
            db.close()

    def check_external_service() -> None:
        redis_url = os.getenv("REDIS_URL")
        if not redis_url:
            return
        try:
            import redis
        except ImportError as exc:
            raise RuntimeError(
                "Redis health check failed: redis package is not installed"
            ) from exc
        try:
            client = redis.from_url(redis_url, socket_connect_timeout=1, socket_timeout=1)
            client.ping()
        except Exception as exc:
            raise RuntimeError(f"Redis health check failed: {exc}") from exc

    app = FastAPI(
        title="RuleIQ Production API",
        version="1.0.0",
        description="AI-powered compliance platform"
    )

    # Add middleware — CORS origins from env or restrictive default
    allowed_origins = os.getenv("CORS_ALLOWED_ORIGINS", "").split(",")
    allowed_origins = [o.strip() for o in allowed_origins if o.strip()]
    if not allowed_origins:
        allowed_origins = ["https://ruleiq.com", "https://app.ruleiq.com"]

    app.add_middleware(
        CORSMiddleware,
        allow_origins=allowed_origins,
        allow_credentials=True,
        allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
        allow_headers=["*"],
    )
    app.add_middleware(GZipMiddleware, minimum_size=1000)

    # Health endpoints
    @app.get("/health")
    def health_check():
        return {"status": "healthy", "service": "ruleiq-api"}

    @app.get("/health/live")
    def liveness_check():
        return {"status": "alive", "service": "ruleiq-api"}

    @app.get("/health/ready")
    def readiness_check():
        checks = {
            "database": "unknown",
            "external": "skipped" if not os.getenv("REDIS_URL") else "unknown",
        }
        failures = []

        try:
            with ThreadPoolExecutor(max_workers=2) as executor:
                futures = {
                    "database": executor.submit(check_db_connection),
                    "external": executor.submit(check_external_service),
                }

                for service_name, future in futures.items():
                    try:
                        future.result(timeout=2)
                        if service_name == "external" and not os.getenv("REDIS_URL"):
                            checks[service_name] = "skipped"
                        else:
                            checks[service_name] = "ok"
                    except FutureTimeoutError:
                        checks[service_name] = "failed"
                        failures.append(f"{service_name}: health check timed out")
                    except Exception as exc:
                        checks[service_name] = "failed"
                        failures.append(f"{service_name}: {exc}")
        except Exception as exc:
            failures.append(str(exc))

        if failures:
            raise HTTPException(
                status_code=503,
                detail={
                    "status": "not_ready",
                    "service": "ruleiq-api",
                    "checks": checks,
                    "errors": failures,
                },
            )

        return {
            "status": "ready",
            "service": "ruleiq-api",
            "checks": checks,
        }

    @app.get("/")
    def root():
        return {"message": "RuleIQ API - Production", "version": "1.0.0"}

    # Add a simple API endpoint to test functionality
    @app.get("/api/v1/status")
    def api_status():
        return {
            "status": "operational",
            "service": "ruleiq-api",
            "version": "1.0.0",
            "environment": os.getenv("ENVIRONMENT", "production")
        }

    return app

# Create the app for uvicorn
app = create_production_app()

if __name__ == "__main__":
    import uvicorn
    port = int(os.getenv("PORT", 8080))
    print(f"🚀 Starting RuleIQ Production API on port {port}")
    uvicorn.run(
        "production_start:app",
        host="0.0.0.0",
        port=port,
        workers=1,
        log_level="info"
    )
