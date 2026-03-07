"""

Setup monitoring for FastAPI application.
"""

import logging
from typing import Optional
from fastapi import FastAPI
from .middleware import setup_middleware
from .error_handler import setup_error_handling
from .logger import setup_logging
from .sentry_integration import setup_sentry, SentryConfig
from .metrics import get_metrics_collector


def setup_monitoring(
    app: FastAPI,
    environment: str = "development",
    sentry_dsn: Optional[str] = None,
    log_level: str = "INFO",
    enable_sentry: bool = True,
    enable_metrics: bool = True,
    enable_health_checks: bool = True,
    slow_request_threshold: float = 1.0,
) -> None:
    """
    Setup comprehensive monitoring for FastAPI application.

    Args:
        app: FastAPI application instance
        environment: Environment name (development, staging, production)
        sentry_dsn: Sentry DSN for error tracking
        log_level: Logging level
        enable_sentry: Whether to enable Sentry integration
        enable_metrics: Whether to enable metrics collection
        enable_health_checks: Whether to enable health checks
        slow_request_threshold: Threshold for slow request warnings (seconds)
    """
    setup_logging(log_level=log_level, json_logs=environment != "development")
    logger = logging.getLogger(__name__)
    logger.info(f"Setting up monitoring for {environment} environment")
    if enable_sentry and sentry_dsn:
        config = SentryConfig(
            dsn=sentry_dsn,
            environment=environment,
            traces_sample_rate=0.1 if environment == "production" else 1.0,
            profiles_sample_rate=0.1 if environment == "production" else 0.5,
            debug=environment == "development",
        )
        if setup_sentry(config):
            logger.info("Sentry integration enabled")
        else:
            logger.warning("Sentry integration failed or skipped")
    setup_error_handling(app)
    logger.info("Error handling configured")
    setup_middleware(
        app,
        enable_cors=True,
        enable_request_id=True,
        enable_logging=True,
        enable_metrics=enable_metrics,
        enable_performance=True,
        enable_security_headers=True,
        slow_request_threshold=slow_request_threshold,
    )
    logger.info("Middleware stack configured")
    if enable_metrics:
        collector = get_metrics_collector()
        logger.info(f"Metrics collector initialized with {len(collector.metrics)} default metrics")
    if enable_health_checks or enable_metrics:
        try:
            from api.routers.monitoring import router as monitoring_router

            app.include_router(monitoring_router, prefix="/monitoring", tags=["monitoring"])
            logger.info("Monitoring endpoints registered")
        except ImportError:
            logger.warning(
                "Monitoring router not found, skipping monitoring endpoints registration"
            )
    logger.info("Monitoring setup completed successfully")

    @app.on_event("startup")
    async def monitoring_startup() -> None:
        """Initialize monitoring on application startup."""
        logger.info("Application starting up")
        if enable_metrics:
            import asyncio
            from .metrics import get_metrics_collector

            async def collect_system_metrics() -> None:
                """Periodically collect system metrics."""
                collector = get_metrics_collector()
                while True:
                    try:
                        collector.collect_system_metrics()
                        await asyncio.sleep(30)
                    except Exception as e:
                        logger.error(f"Error collecting system metrics: {e}")
                        await asyncio.sleep(60)

            asyncio.create_task(collect_system_metrics())
            logger.info("System metrics collection started")

    @app.on_event("shutdown")
    async def monitoring_shutdown() -> None:
        """Cleanup monitoring on application shutdown."""
        logger.info("Application shutting down")
        for handler in logger.handlers:
            handler.flush()
        if enable_sentry:
            import sentry_sdk

            client = sentry_sdk.get_client()
            if client:
                client.flush(timeout=2.0)
                logger.info("Sentry events flushed")
        logger.info("Monitoring cleanup completed")


def configure_from_settings(app: FastAPI) -> None:
    """
    Configure monitoring from application settings.

    Args:
        app: FastAPI application instance
    """
    from config.settings import settings

    setup_monitoring(
        app=app,
        environment=getattr(settings, "environment", "development"),
        sentry_dsn=getattr(settings, "sentry_dsn", None),
        log_level=getattr(settings, "log_level", "INFO"),
        enable_sentry=getattr(settings, "enable_sentry", True),
        enable_metrics=getattr(settings, "enable_metrics", True),
        enable_health_checks=getattr(settings, "enable_health_checks", True),
        slow_request_threshold=getattr(settings, "slow_request_threshold", 1.0),
    )
