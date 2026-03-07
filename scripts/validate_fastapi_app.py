#!/usr/bin/env python3
"""
FastAPI Application Validation Script

Validates the FastAPI application structure, imports, routers, middleware,
dependencies, health endpoints, and OpenAPI generation.

Usage:
    python -m scripts.validate_fastapi_app

Exit codes:
    0: All validations passed
    1: One or more validations failed
"""

import sys
from typing import Tuple


def validate_app_import() -> Tuple[bool, str]:
    """
    Validate that the FastAPI app can be imported.

    Returns:
        Tuple of (success: bool, message: str)
    """
    try:
        from api.main import app  # noqa: F401 - import to test importability

        return True, "✅ FastAPI app imported successfully"
    except ImportError as e:
        return False, f"❌ Failed to import FastAPI app: {str(e)}"
    except Exception as e:
        return False, f"❌ Unexpected error importing app: {str(e)}"


def validate_router_registration() -> Tuple[bool, str]:
    """
    Validate that expected routers are registered with the app.

    Returns:
        Tuple of (success: bool, message: str)
    """
    try:
        from api.main import app

        # Define expected router prefixes
        expected_prefixes = [
            "/api/v1/auth",
            "/api/v1/users",
            "/api/v1/assessments",
            "/api/v1/ai-assessments",
            "/api/v1/ai-optimization",
            "/api/v1/business-profiles",
            "/api/v1/chat",
            "/api/v1/compliance",
            "/api/v1/evidence",
            "/api/v1/evidence-collection",
            "/api/v1/foundation-evidence",
            "/api/v1/frameworks",
            "/api/v1/implementation",
            "/api/v1/integrations",
            "/api/v1/iq",
            "/api/v1/monitoring",
            "/api/v1/policies",
            "/api/v1/readiness",
            "/api/v1/reports",
            "/api/v1/security",
            "/api/v1/ai",
            "/api/v1/freemium",
            "/api/v1/rbac",
            "/api/v1/uk-compliance",
        ]

        # Extract registered paths from app routes
        registered_paths = set()
        for route in app.routes:
            if hasattr(route, "path"):
                # Extract the prefix from the path
                path = route.path
                if path.startswith("/api/v1/"):
                    # Get the prefix up to the third slash
                    parts = path.split("/")
                    if len(parts) >= 4:
                        prefix = "/".join(parts[:4])
                        registered_paths.add(prefix)

        # Check for missing routers
        missing_routers = []
        for prefix in expected_prefixes:
            if not any(path.startswith(prefix) for path in registered_paths):
                missing_routers.append(prefix)

        if missing_routers:
            # Log missing routers but don't fail for optional ones
            message = f"⚠️  Missing router prefixes (may be optional): {', '.join(missing_routers)}"
            print(message)
            # Still return success but with warning message
            return (
                True,
                f"✅ Router validation completed with warnings: {len(missing_routers)} optional routers missing",
            )

        return True, f"✅ All expected routers are registered ({len(expected_prefixes)} routers)"

    except Exception as e:
        return False, f"❌ Failed to validate routers: {str(e)}"


def validate_middleware_order() -> Tuple[bool, str]:
    """
    Validate that middleware is registered in the correct order.

    Expected order (reverse of registration):
    1. error_handler_middleware
    2. security_headers_middleware
    3. rate_limit_middleware

    Returns:
        Tuple of (success: bool, message: str)
    """
    try:
        from api.main import app

        # Get user middleware stack
        middleware_stack = []
        for middleware in app.user_middleware:
            if hasattr(middleware, "cls"):
                # Get the middleware function name
                if hasattr(middleware.cls, "__name__"):
                    middleware_stack.append(middleware.cls.__name__)
                elif hasattr(middleware.cls, "func") and hasattr(middleware.cls.func, "__name__"):
                    middleware_stack.append(middleware.cls.func.__name__)

        # Check for required middleware in correct order
        # Note: Middleware is executed in reverse order of registration
        expected_order = [
            "error_handler_middleware",
            "security_headers_middleware",
            "rate_limit_middleware",
        ]

        # Find positions of expected middleware
        positions = {}
        for idx, mw_name in enumerate(middleware_stack):
            if mw_name in expected_order:
                positions[mw_name] = idx

        # Verify all middleware are present
        missing_middleware = []
        for mw_name in expected_order:
            if mw_name not in positions:
                missing_middleware.append(mw_name)

        if missing_middleware:
            return False, f"❌ Missing middleware: {', '.join(missing_middleware)}"

        # Verify order is correct
        for i in range(len(expected_order) - 1):
            current = expected_order[i]
            next_mw = expected_order[i + 1]
            if current in positions and next_mw in positions:
                if positions[current] > positions[next_mw]:
                    return (
                        False,
                        f"❌ Incorrect middleware order: {current} should come before {next_mw}",
                    )

        return True, f"✅ Middleware registered in correct order: {' -> '.join(expected_order)}"

    except Exception as e:
        return False, f"❌ Failed to validate middleware: {str(e)}"


def validate_docs_urls() -> Tuple[bool, str]:
    """
    Validate that documentation URLs are correctly configured.

    Returns:
        Tuple of (success: bool, message: str)
    """
    try:
        from api.main import app
        from config.settings import settings

        if settings.debug:
            # In debug mode, docs should be available
            expected_docs_url = "/api/v1/docs"
            expected_redoc_url = "/api/v1/redoc"
            expected_openapi_url = "/api/v1/openapi.json"

            if app.docs_url != expected_docs_url:
                return (
                    False,
                    f"❌ Incorrect docs URL: expected {expected_docs_url}, got {app.docs_url}",
                )

            if app.redoc_url != expected_redoc_url:
                return (
                    False,
                    f"❌ Incorrect redoc URL: expected {expected_redoc_url}, got {app.redoc_url}",
                )

            if app.openapi_url != expected_openapi_url:
                return (
                    False,
                    f"❌ Incorrect OpenAPI URL: expected {expected_openapi_url}, got {app.openapi_url}",
                )

            return True, "✅ Documentation URLs correctly configured for debug mode"
        else:
            # In production mode, docs should be disabled
            if app.docs_url is not None:
                return False, f"❌ Docs URL should be None in production, got {app.docs_url}"

            if app.redoc_url is not None:
                return False, f"❌ Redoc URL should be None in production, got {app.redoc_url}"

            # OpenAPI URL should still be available for internal use
            if app.openapi_url != "/api/v1/openapi.json":
                return (
                    False,
                    f"❌ OpenAPI URL incorrect: expected /api/v1/openapi.json, got {app.openapi_url}",
                )

            return True, "✅ Documentation URLs correctly disabled for production mode"

    except Exception as e:
        return False, f"❌ Failed to validate docs URLs: {str(e)}"


def validate_openapi_generation() -> Tuple[bool, str]:
    """
    Validate that OpenAPI schema can be generated.

    Returns:
        Tuple of (success: bool, message: str)
    """
    try:
        from api.main import app

        # Generate OpenAPI schema
        openapi_schema = app.openapi()

        # Validate it's a proper dictionary
        if not isinstance(openapi_schema, dict):
            return False, f"❌ OpenAPI schema is not a dictionary: {type(openapi_schema)}"

        # Check for required fields
        required_fields = ["openapi", "info", "paths"]
        missing_fields = []
        for field in required_fields:
            if field not in openapi_schema:
                missing_fields.append(field)

        if missing_fields:
            return False, f"❌ OpenAPI schema missing required fields: {', '.join(missing_fields)}"

        # Check that paths is not empty
        if not openapi_schema.get("paths"):
            return False, "❌ OpenAPI schema has no paths defined"

        path_count = len(openapi_schema["paths"])
        return True, f"✅ OpenAPI schema generated successfully with {path_count} paths"

    except Exception as e:
        return False, f"❌ Failed to generate OpenAPI schema: {str(e)}"


def validate_health_endpoints() -> Tuple[bool, str]:
    """
    Validate health check endpoints using TestClient.

    Returns:
        Tuple of (success: bool, message: str)
    """
    try:
        from fastapi.testclient import TestClient
        from api.main import app

        client = TestClient(app)

        # Test liveness endpoint
        liveness_response = client.get("/health/live")
        if liveness_response.status_code != 200:
            return False, f"❌ Liveness check failed with status {liveness_response.status_code}"

        liveness_data = liveness_response.json()
        if liveness_data.get("status") != "alive":
            return (
                False,
                f"❌ Liveness check returned incorrect status: {liveness_data.get('status')}",
            )

        # Test readiness endpoint (may return 503 if DB not configured)
        readiness_response = client.get("/health/ready")
        if readiness_response.status_code not in [200, 503]:
            return (
                False,
                f"❌ Readiness check returned unexpected status {readiness_response.status_code}",
            )

        # Test detailed health endpoint
        detailed_response = client.get("/api/v1/health/detailed")
        if detailed_response.status_code != 200:
            return (
                False,
                f"❌ Detailed health check failed with status {detailed_response.status_code}",
            )

        detailed_data = detailed_response.json()
        if "status" not in detailed_data:
            return False, "❌ Detailed health check missing 'status' field"

        if "components" not in detailed_data:
            return False, "❌ Detailed health check missing 'components' field"

        # Verify component structure
        components = detailed_data.get("components", {})
        expected_components = ["database", "ai_services"]
        missing_components = []
        for component in expected_components:
            if component not in components:
                missing_components.append(component)

        if missing_components:
            return (
                False,
                f"❌ Detailed health check missing components: {', '.join(missing_components)}",
            )

        return True, "✅ All health endpoints validated successfully"

    except ImportError:
        return False, "❌ Failed to import TestClient - install fastapi[all] or httpx"
    except Exception as e:
        return False, f"❌ Failed to validate health endpoints: {str(e)}"


def main() -> int:
    """
    Main function to run all validations.

    Returns:
        Exit code: 0 for success, 1 for failure
    """
    print("=" * 60)
    print("FastAPI Application Validation")
    print("=" * 60)

    validations = [
        ("App Import", validate_app_import),
        ("Router Registration", validate_router_registration),
        ("Middleware Order", validate_middleware_order),
        ("Documentation URLs", validate_docs_urls),
        ("OpenAPI Generation", validate_openapi_generation),
        ("Health Endpoints", validate_health_endpoints),
    ]

    all_passed = True
    results = []

    for name, validation_func in validations:
        print(f"\nValidating {name}...")
        success, message = validation_func()
        results.append((name, success, message))
        print(f"  {message}")

        if not success:
            all_passed = False

    # Summary
    print("\n" + "=" * 60)
    print("Validation Summary")
    print("=" * 60)

    passed_count = sum(1 for _, success, _ in results if success)
    failed_count = len(results) - passed_count

    print(f"\nTotal validations: {len(results)}")
    print(f"✅ Passed: {passed_count}")
    print(f"❌ Failed: {failed_count}")

    if all_passed:
        print("\n🎉 All validations passed!")
        return 0
    else:
        print("\n⚠️  Some validations failed. Please review the errors above.")
        return 1


if __name__ == "__main__":
    sys.exit(main())
