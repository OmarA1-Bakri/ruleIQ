#!/usr/bin/env python3
"""Validate required environment variables for RuleIQ application.

This script checks that all required environment variables are set before
the application starts, preventing runtime errors and security issues.

Usage:
    python scripts/validate_required_env_vars.py [--environment ENVIRONMENT] [--no-fail]

Examples:
    # Validate all required variables (fails on missing vars)
    python scripts/validate_required_env_vars.py

    # Validate for production environment
    python scripts/validate_required_env_vars.py --environment production

    # Validate without failing (report only)
    python scripts/validate_required_env_vars.py --no-fail
"""

import argparse
import os
import sys
from typing import Any, Dict, List, Literal, Tuple

# Required environment variables with descriptions
REQUIRED_ENV_VARS: Dict[str, str] = {
    # Database
    "DATABASE_URL": "PostgreSQL database connection URL",
    "REDIS_URL": "Redis connection URL for caching and sessions",
    # Neo4j
    "NEO4J_URI": "Neo4j database URI (e.g., neo4j+s://xxx.databases.neo4j.io)",
    "NEO4J_USERNAME": "Neo4j database username",
    "NEO4J_PASSWORD": "Neo4j database password",
    # Authentication
    "JWT_SECRET": "Secret key for JWT token signing",
    "FERNET_KEY": "Encryption key for sensitive data",
    # Application
    "SECRET_KEY": "Application secret key",
}

# At least one AI service API key is required
AI_SERVICE_VARS: Dict[str, str] = {
    "OPENAI_API_KEY": "OpenAI API key for AI features",
    "ANTHROPIC_API_KEY": "Anthropic API key (optional, for Claude models)",
    "GOOGLE_AI_API_KEY": "Google AI API key (optional, for Gemini models)",
}

# Optional environment variables
OPTIONAL_ENV_VARS: Dict[str, str] = {
    "NEO4J_DATABASE": "Neo4j database name (default: neo4j)",
    "ENVIRONMENT": "Environment name (development/staging/production)",
    "LOG_LEVEL": "Logging level (DEBUG/INFO/WARNING/ERROR)",
    "PORT": "Application port (default: 8000)",
}

# Development environment may have relaxed requirements
DEVELOPMENT_EXEMPTIONS = {
    "FERNET_KEY",  # Can be generated automatically in development
}


def check_environment_variable(
    var_name: str,
    description: str,
) -> Tuple[Literal["valid", "missing", "invalid"], str]:
    """Check if an environment variable is set.

    Args:
        var_name: Name of the environment variable
        description: Human-readable description

    Returns:
        Tuple of (status, message)
    """
    value = os.getenv(var_name)

    if not value:
        return "missing", f"❌ {var_name} is not set"

    # Check for placeholder values
    placeholder_patterns = [
        "changeme",
        "your-",
        "-here",
        "example",
        "placeholder",
        "dummy",
        "test" if "password" in var_name.lower() else None,
    ]

    value_lower = value.lower()
    for pattern in placeholder_patterns:
        if pattern and pattern in value_lower:
            return "invalid", f"❌ {var_name} contains placeholder value: {value[:20]}..."

    # Warn about insecure default passwords
    insecure_passwords = ["password", "ruleiq123", "admin", "123456"]
    if "password" in var_name.lower() and value.lower() in insecure_passwords:
        return "invalid", f"❌ {var_name} uses insecure password (NEVER use default passwords)"

    return "valid", f"✅ {var_name} is set"


def validate_environment(
    fail_fast: bool = True,
    environment: str | None = None,
    verbose: bool = True,
) -> Dict[str, Any]:
    """Validate required environment variables are set.

    Args:
        fail_fast: If True, raise exception on first missing variable
        environment: Target environment (development/staging/production)

    Returns:
        Dictionary with validation results
    """
    missing: List[str] = []
    invalid: List[str] = []
    present: List[str] = []
    warnings: List[str] = []

    environment_name = environment or os.getenv("ENVIRONMENT") or "development"
    is_development = environment_name.lower() == "development"

    if verbose:
        print(f"\n🔍 Validating environment variables for: {environment_name}\n")
        print("=" * 70)

    # Check required variables
    for var_name, description in REQUIRED_ENV_VARS.items():
        # Skip development exemptions
        if is_development and var_name in DEVELOPMENT_EXEMPTIONS:
            warnings.append(f"⚠️  {var_name} skipped (development exemption)")
            continue

        status, message = check_environment_variable(var_name, description)

        if verbose:
            print(f"{message}")
            print(f"   {description}")

        if status == "valid":
            present.append(var_name)
        elif status == "invalid":
            invalid.append(var_name)
        else:
            missing.append(var_name)

    if verbose:
        print("\n" + "=" * 70)
        print("\n🤖 AI Services (at least one required):\n")

    # Check AI service variables (at least one must be set)
    ai_services_set = []
    for var_name, description in AI_SERVICE_VARS.items():
        value = os.getenv(var_name)
        if value:
            ai_services_set.append(var_name)
            if verbose:
                print(f"✅ {var_name} is set")
                print(f"   {description}")

    if not ai_services_set:
        error_msg = "At least one AI service API key is required"
        missing.append("AI_SERVICE_KEY")
        if verbose:
            print(f"❌ {error_msg}")
            print(f"   Set one of: {', '.join(AI_SERVICE_VARS.keys())}")

    # Show optional variables
    if verbose:
        print("\n" + "=" * 70)
        print("\n📝 Optional variables:\n")
        for var_name, description in OPTIONAL_ENV_VARS.items():
            value = os.getenv(var_name)
            if value:
                print(f"✅ {var_name} = {value}")
            else:
                print(f"⚪ {var_name} (not set, using default)")
            print(f"   {description}")

    # Print summary
    if verbose:
        print("\n" + "=" * 70)
        print("\n📊 Summary:\n")
        print(f"✅ Required variables present: {len(present)}/{len(REQUIRED_ENV_VARS)}")
        print(f"🤖 AI services configured: {len(ai_services_set)}/{len(AI_SERVICE_VARS)}")

        if warnings:
            print(f"\n⚠️  Warnings: {len(warnings)}")
            for warning in warnings:
                print(f"   {warning}")

        if missing:
            print(f"\n❌ Missing variables: {len(missing)}")
            for var in missing:
                print(f"   - {var}")

        if invalid:
            print(f"\n❌ Invalid variables: {len(invalid)}")
            for var in invalid:
                print(f"   - {var}")

    # Provide guidance
    if (missing or invalid) and verbose:
        print("\n" + "=" * 70)
        print("\n💡 How to fix:\n")
        print("Option 1: Use Doppler (recommended for teams)")
        print("  doppler login")
        print("  doppler setup")
        print("  doppler run -- python main.py")
        print("\nOption 2: Set environment variables manually")
        print("  export NEO4J_URI='your-uri'")
        print("  export NEO4J_PASSWORD='your-password'")
        print("  # ... etc")
        print("\nOption 3: Use .env.local file")
        print("  cp env.template .env.local")
        print("  # Edit .env.local with your credentials")
        print("  # Application will load it automatically")
        print("\nSee docs/ENVIRONMENT_SETUP.md for detailed instructions.")
        print("=" * 70 + "\n")

    result = {
        "valid": len(missing) == 0 and len(invalid) == 0,
        "missing": missing,
        "invalid": invalid,
        "present": present,
        "ai_services": ai_services_set,
        "warnings": warnings,
        "environment": environment_name,
    }

    return result


def main() -> None:
    """Main entry point for CLI usage."""
    parser = argparse.ArgumentParser(
        description="Validate required environment variables for RuleIQ",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument(
        "--environment",
        "-e",
        help="Target environment (development/staging/production)",
        default=None,
    )
    parser.add_argument(
        "--no-fail",
        action="store_true",
        help="Don't fail on missing variables (report only)",
    )
    parser.add_argument(
        "--quiet",
        "-q",
        action="store_true",
        help="Minimal output (only errors)",
    )

    args = parser.parse_args()

    result = validate_environment(
        fail_fast=not args.no_fail,
        environment=args.environment,
        verbose=not args.quiet,
    )

    if not result["valid"]:
        if not args.no_fail:
            sys.exit(1)
        else:
            print("\n⚠️  Validation failed but --no-fail was specified")
            sys.exit(0)
    else:
        if not args.quiet:
            print("\n✅ All required environment variables are properly configured!\n")
        sys.exit(0)


if __name__ == "__main__":
    main()
