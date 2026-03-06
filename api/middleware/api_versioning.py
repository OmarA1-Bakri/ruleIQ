"""API versioning middleware for ruleIQ."""

from fastapi import Request
from fastapi.responses import JSONResponse
from typing import Dict, Any, Optional, List
import re
import logging

logger = logging.getLogger(__name__)


class APIVersioning:
    """API versioning support for backward compatibility."""

    SUPPORTED_VERSIONS = ["v1", "v2"]
    DEFAULT_VERSION = "v1"
    LATEST_VERSION = "v2"

    def __init__(self) -> None:
        self.version_routes = {}
        self.deprecated_endpoints = {}
        self.version_headers = {}

    def register_version(self, version: str, routes: Dict[str, Any]) -> None:
        """Register routes for a specific API version."""
        if version not in self.SUPPORTED_VERSIONS:
            raise ValueError(f"Unsupported version: {version}")
        self.version_routes[version] = routes

    def mark_deprecated(
        self, endpoint: str, version: str, replacement: Optional[str] = None
    ) -> None:
        """Mark an endpoint as deprecated."""
        self.deprecated_endpoints[endpoint] = {
            "version": version,
            "replacement": replacement,
            "deprecated_at": "2024-01-01",
        }

    def get_version_from_request(self, request: Request) -> str:
        """Extract API version from request."""
        path = request.url.path
        version_match = re.match("^/api/(v\\d+)/", path)
        if version_match:
            return version_match.group(1)
        version_header = request.headers.get("X-API-Version")
        if version_header and version_header in self.SUPPORTED_VERSIONS:
            return version_header
        version_param = request.query_params.get("api_version")
        if version_param and version_param in self.SUPPORTED_VERSIONS:
            return version_param
        return self.DEFAULT_VERSION

    def validate_version(self, version: str) -> bool:
        """Validate if version is supported."""
        return version in self.SUPPORTED_VERSIONS

    def get_version_info(self, version: str) -> Dict[str, Any]:
        """Get information about API version."""
        return {
            "version": version,
            "supported": version in self.SUPPORTED_VERSIONS,
            "latest": version == self.LATEST_VERSION,
            "deprecated": version != self.LATEST_VERSION,
        }

    def create_version_response(self, version: str, data: Any) -> Dict[str, Any]:
        """Create response with version information."""
        response = {
            "data": data,
            "meta": {
                "api_version": version,
                "supported_versions": self.SUPPORTED_VERSIONS,
                "latest_version": self.LATEST_VERSION,
            },
        }
        if version != self.LATEST_VERSION:
            response["meta"]["warning"] = (
                f"API version {version} is deprecated. Use {self.LATEST_VERSION} instead."
            )
        return response

    def check_deprecation_warning(self, endpoint: str, version: str) -> Optional[Dict[str, str]]:
        """Check if endpoint is deprecated."""
        if endpoint in self.deprecated_endpoints:
            deprecation = self.deprecated_endpoints[endpoint]
            return {
                "warning": f"Endpoint {endpoint} is deprecated since {deprecation['version']}",
                "replacement": deprecation.get("replacement", "Use latest version"),
            }
        return None


class VersionMiddleware:
    """FastAPI middleware for API versioning."""

    def __init__(self, versioning: APIVersioning) -> None:
        self.versioning = versioning

    async def __call__(self, request: Request, call_next) -> Any:
        """Process request with versioning."""
        version = self.versioning.get_version_from_request(request)
        if not self.versioning.validate_version(version):
            return JSONResponse(
                status_code=400,
                content={
                    "error": {
                        "code": "INVALID_API_VERSION",
                        "message": f"Unsupported API version: {version}",
                        "supported_versions": self.versioning.SUPPORTED_VERSIONS,
                    }
                },
            )
        request.state.api_version = version
        response = await call_next(request)
        response.headers["X-API-Version"] = version
        response.headers["X-API-Latest-Version"] = self.versioning.LATEST_VERSION
        deprecation = self.versioning.check_deprecation_warning(request.url.path, version)
        if deprecation:
            response.headers["X-API-Deprecation-Warning"] = deprecation["warning"]
        return response


api_versioning = APIVersioning()
api_versioning.register_version("v1", {"description": "Initial API version", "status": "stable"})
api_versioning.register_version(
    "v2", {"description": "Enhanced API with improved performance", "status": "latest"}
)
api_versioning.mark_deprecated("/api/v1/evidence/bulk-upload", "v1", "/api/v2/evidence/upload")
api_versioning.mark_deprecated("/api/v1/assessments/create", "v1", "/api/v2/assessments")


def version_route(version: str) -> Any:
    """Decorator for version-specific routes."""

    def decorator(func) -> Any:
        func._api_version = version
        return func

    return decorator


class VersionRouter:
    """Router that handles version-specific endpoints."""

    def __init__(self, prefix: str = "/api") -> None:
        self.prefix = prefix
        self.routes = {}

    def add_route(self, path: str, endpoint: Any, version: str, **kwargs) -> None:
        """Add a version-specific route."""
        version_path = f"{self.prefix}/{version}{path}"
        if version not in self.routes:
            self.routes[version] = []
        self.routes[version].append({"path": version_path, "endpoint": endpoint, "kwargs": kwargs})

    def get_routes(self, version: str) -> List[Dict[str, Any]]:
        """Get all routes for a specific version."""
        return self.routes.get(version, [])


VERSION_RESPONSE_SCHEMAS = {
    "v1": {
        "evidence": {"id": "uuid", "name": "string", "status": "string", "created_at": "datetime"},
        "assessment": {"id": "uuid", "title": "string", "status": "string", "progress": "integer"},
    },
    "v2": {
        "evidence": {
            "id": "uuid",
            "name": "string",
            "status": "string",
            "created_at": "datetime",
            "metadata": "object",
            "tags": "array",
        },
        "assessment": {
            "id": "uuid",
            "title": "string",
            "status": "string",
            "progress": "integer",
            "ai_insights": "object",
            "recommendations": "array",
        },
    },
}


def get_response_schema(version: str, resource_type: str) -> Dict[str, str]:
    """Get response schema for specific version and resource."""
    return VERSION_RESPONSE_SCHEMAS.get(version, {}).get(resource_type, {})


class MigrationHelper:
    """Helper for migrating between API versions."""

    @staticmethod
    def v1_to_v2_evidence(v1_data: Dict[str, Any]) -> Dict[str, Any]:
        """Convert v1 evidence format to v2."""
        return {**v1_data, "metadata": {}, "tags": [], "ai_analysis": None}

    @staticmethod
    def v1_to_v2_assessment(v1_data: Dict[str, Any]) -> Dict[str, Any]:
        """Convert v1 assessment format to v2."""
        return {**v1_data, "ai_insights": {}, "recommendations": [], "risk_score": None}
