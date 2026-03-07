"""
Health check endpoints for Cloud Run
"""

from fastapi import APIRouter, Response
from typing import Dict

router = APIRouter(tags=["Health"])


@router.get("/")
async def root() -> Dict[str, str]:
    """Root endpoint"""
    return {"message": "RuleIQ API is running", "status": "healthy"}


@router.get("/health")
async def health_check() -> Dict[str, str]:
    """Simple health check for Cloud Run"""
    return {"status": "healthy"}


@router.get("/ready")
async def readiness_check() -> Dict[str, str]:
    """Readiness check for Cloud Run"""
    # In production, this would check database connectivity
    # For now, just return ready
    return {"status": "ready"}


@router.get("/_ah/health")
async def gcp_health_check() -> Response:
    """Google Cloud Platform health check endpoint"""
    return Response(content="OK", media_type="text/plain")
