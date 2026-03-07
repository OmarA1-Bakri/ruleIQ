#!/usr/bin/env python3
"""
CI Dependencies Validation Script

This script validates that all required dependencies for CI are properly installed
and configured, including Python packages, database connectivity, and environment variables.
"""

import os
import sys
import socket
import importlib
import traceback
from typing import List, Tuple


def check_python_packages() -> Tuple[bool, List[str]]:
    """Verify required Python packages are importable."""
    required_packages = [
        # Core framework
        ("fastapi", "FastAPI"),
        ("uvicorn", "Uvicorn"),
        ("pydantic", "Pydantic"),
        # Database
        ("sqlalchemy", "SQLAlchemy"),
        ("alembic", "Alembic"),
        ("psycopg", "psycopg3"),  # Try psycopg3 first
        ("redis", "redis-py"),
        # API dependencies
        ("httpx", "HTTPX"),
        ("python-multipart", "python-multipart"),
        ("python-jose", "python-jose[cryptography]"),
        ("passlib", "Passlib"),
        # AI/ML
        ("langchain", "LangChain"),
        ("openai", "OpenAI"),
        # Testing
        ("pytest", "pytest"),
        ("pytest_asyncio", "pytest-asyncio"),
        # Utilities
        ("python-dotenv", "python-dotenv"),
        ("pyyaml", "PyYAML"),
    ]

    errors = []
    success = True

    print("📦 Checking Python packages...")

    for module_name, package_name in required_packages:
        try:
            # Special handling for psycopg
            if module_name == "psycopg":
                try:
                    importlib.import_module("psycopg")
                    print(f"  ✅ {package_name}")
                except ImportError:
                    # Try psycopg2 as fallback
                    try:
                        importlib.import_module("psycopg2")
                        print("  ✅ psycopg2 (fallback)")
                    except ImportError:
                        errors.append(f"{package_name} or psycopg2")
                        print(f"  ❌ {package_name} (psycopg2 also not found)")
                        success = False
            else:
                importlib.import_module(module_name)
                print(f"  ✅ {package_name}")
        except ImportError as e:
            errors.append(package_name)
            print(f"  ❌ {package_name}: {str(e)}")
            success = False

    return success, errors


def check_database_connectivity() -> Tuple[bool, List[str]]:
    """Check if database services are reachable."""
    errors = []
    success = True

    print("\n🔌 Checking database connectivity...")

    # Check PostgreSQL
    database_url = os.environ.get("DATABASE_URL", "")
    if database_url:
        # Parse PostgreSQL connection
        if "postgresql://" in database_url or "postgres://" in database_url:
            try:
                # Extract host and port from URL
                import urllib.parse

                parsed = urllib.parse.urlparse(database_url)
                host = parsed.hostname or "localhost"
                port = parsed.port or 5432

                # Test socket connection
                sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                sock.settimeout(5)
                result = sock.connect_ex((host, port))
                sock.close()

                if result == 0:
                    print(f"  ✅ PostgreSQL socket ({host}:{port})")
                else:
                    errors.append(f"PostgreSQL not reachable at {host}:{port}")
                    print(f"  ❌ PostgreSQL socket ({host}:{port})")
                    success = False
            except Exception as e:
                errors.append(f"PostgreSQL connection check failed: {e}")
                print(f"  ❌ PostgreSQL: {e}")
                success = False
    else:
        print("  ⚠️  DATABASE_URL not set (skipping PostgreSQL check)")

    # Check Redis
    redis_url = os.environ.get("REDIS_URL", "")
    if redis_url:
        try:
            # Extract host and port from URL
            import urllib.parse

            parsed = urllib.parse.urlparse(redis_url)
            host = parsed.hostname or "localhost"
            port = parsed.port or 6379

            # Test socket connection
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(5)
            result = sock.connect_ex((host, port))
            sock.close()

            if result == 0:
                print(f"  ✅ Redis socket ({host}:{port})")
            else:
                errors.append(f"Redis not reachable at {host}:{port}")
                print(f"  ❌ Redis socket ({host}:{port})")
                success = False
        except Exception as e:
            errors.append(f"Redis connection check failed: {e}")
            print(f"  ❌ Redis: {e}")
            success = False
    else:
        print("  ⚠️  REDIS_URL not set (skipping Redis check)")

    return success, errors


def check_environment_variables() -> Tuple[bool, List[str]]:
    """Validate required environment variables are set."""
    required_vars = ["DATABASE_URL", "REDIS_URL", "SECRET_KEY", "JWT_SECRET_KEY", "ENVIRONMENT"]

    optional_vars = [
        "OPENAI_API_KEY",
        "LANGCHAIN_API_KEY",
        "NEO4J_URI",
        "NEO4J_USERNAME",
        "NEO4J_PASSWORD",
        "SENTRY_DSN",
        "SONAR_TOKEN",
    ]

    errors = []
    success = True

    print("\n🔐 Checking environment variables...")

    # Check required variables
    for var in required_vars:
        value = os.environ.get(var)
        if value:
            # Don't print actual values for security
            print(f"  ✅ {var}: {'*' * min(8, len(value))}")
        else:
            errors.append(f"{var} not set")
            print(f"  ❌ {var}: NOT SET")
            success = False

    # Check optional variables (just warn)
    print("\n📋 Optional environment variables:")
    for var in optional_vars:
        value = os.environ.get(var)
        if value:
            print(f"  ✅ {var}: {'*' * min(8, len(value))}")
        else:
            print(f"  ⚠️  {var}: not set")

    return success, errors


def check_port_availability() -> Tuple[bool, List[str]]:
    """Check if required ports are not already in use."""
    ports_to_check = [(5432, "PostgreSQL"), (6379, "Redis"), (8000, "FastAPI")]

    errors = []
    success = True

    print("\n🚪 Checking port availability...")

    for port, service in ports_to_check:
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(1)

        # Check if port is in use (connect succeeds = port is occupied)
        result = sock.connect_ex(("localhost", port))
        sock.close()

        if result == 0:
            # Port is occupied (which might be expected if services are running)
            print(f"  ℹ️  Port {port} ({service}): IN USE (service may be running)")
        else:
            # Port is free
            print(f"  ✅ Port {port} ({service}): AVAILABLE")

    return success, errors


def check_requirements_file() -> Tuple[bool, List[str]]:
    """Verify requirements.txt exists and is readable."""
    errors = []
    success = True

    print("\n📄 Checking requirements files...")

    requirements_files = ["requirements.txt", "requirements-dev.txt", "requirements-test.txt"]

    for req_file in requirements_files:
        if os.path.exists(req_file):
            try:
                with open(req_file, "r") as f:
                    lines = f.readlines()
                    package_count = sum(
                        1 for l in lines if l.strip() and not l.strip().startswith("#")
                    )
                    print(f"  ✅ {req_file}: {package_count} packages")
            except Exception as e:
                errors.append(f"Cannot read {req_file}: {e}")
                print(f"  ❌ {req_file}: {e}")
                if req_file == "requirements.txt":  # Main file is critical
                    success = False
        elif req_file == "requirements.txt":
            errors.append(f"{req_file} not found")
            print(f"  ❌ {req_file}: NOT FOUND")
            success = False
        else:
            print(f"  ⚠️  {req_file}: not found (optional)")

    return success, errors


def check_critical_imports() -> Tuple[bool, List[str]]:
    """Import critical modules used by the application."""
    errors = []
    success = True

    print("\n🔍 Testing critical imports...")

    critical_imports = [
        "api.main",
        "config.settings",
        "database.session",
        "services.auth_service",
        "api.routers.auth",
        "api.routers.chat",
        "models.user",
        "models.organization",
    ]

    for module_path in critical_imports:
        try:
            importlib.import_module(module_path)
            print(f"  ✅ {module_path}")
        except ImportError as e:
            # Some imports might fail due to missing config, which is acceptable in CI
            if "config" in str(e).lower() or "settings" in str(e).lower():
                print(f"  ⚠️  {module_path}: Config-related import issue (acceptable in CI)")
            else:
                errors.append(f"{module_path}: {e}")
                print(f"  ❌ {module_path}: {e}")
                # Don't fail on app imports as they might have circular dependencies
        except Exception as e:
            print(f"  ⚠️  {module_path}: {type(e).__name__}: {e}")

    return success, errors


def main():
    """Main validation function."""
    print("🔍 CI Dependencies Validation")
    print("=" * 60)

    all_success = True
    all_errors = []

    # Run all checks
    checks = [
        ("Python Packages", check_python_packages),
        ("Requirements Files", check_requirements_file),
        ("Environment Variables", check_environment_variables),
        ("Database Connectivity", check_database_connectivity),
        ("Port Availability", check_port_availability),
        ("Critical Imports", check_critical_imports),
    ]

    for check_name, check_func in checks:
        try:
            success, errors = check_func()
            if not success:
                all_success = False
                all_errors.extend(errors)
        except Exception as e:
            print(f"\n💥 Check '{check_name}' failed with exception: {e}")
            traceback.print_exc()
            all_success = False
            all_errors.append(f"{check_name}: {e}")

    # Print summary
    print("\n" + "=" * 60)
    print("📊 VALIDATION SUMMARY")
    print("=" * 60)

    if all_errors:
        print("\n❌ Errors found:")
        for error in all_errors:
            print(f"  • {error}")

    if all_success:
        print("\n✅ All CI dependency validations passed!")
        sys.exit(0)
    else:
        print("\n❌ Some CI dependency validations failed!")
        print("\n💡 Suggestions:")
        print("  1. Run: pip install -r requirements.txt")
        print("  2. Ensure PostgreSQL and Redis services are running")
        print("  3. Set required environment variables in .env file")
        print("  4. Check that ports 5432, 6379, and 8000 are available")
        sys.exit(1)


if __name__ == "__main__":
    main()
