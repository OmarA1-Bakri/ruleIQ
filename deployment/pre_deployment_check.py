#!/usr/bin/env python3
"""
Pre-deployment validation script for ruleIQ.
Performs comprehensive checks before deployment to ensure system readiness.
"""

import argparse
import json
import os
import subprocess
import sys
from pathlib import Path
from typing import Dict, List

import psycopg2
import redis
from dotenv import load_dotenv


class PreDeploymentChecker:
    """Pre-deployment validation for ruleIQ application."""

    def __init__(self, environment: str = "staging") -> None:
        """Initialize pre-deployment checker.

        Args:
            environment: Target deployment environment
        """
        self.environment = environment
        self.results: Dict[str, Dict] = {}
        self.errors: List[str] = []
        self.warnings: List[str] = []

        # Load environment variables
        env_file = f".env.{environment}" if Path(f".env.{environment}").exists() else ".env"
        load_dotenv(env_file)

    def log(self, message: str, level: str = "info"):
        """Log messages with appropriate formatting.

        Args:
            message: Message to log
            level: Log level (info, success, warning, error)
        """
        symbols = {"info": "ℹ️", "success": "✅", "warning": "⚠️", "error": "❌"}

        colors = {
            "info": "\033[94m",
            "success": "\033[92m",
            "warning": "\033[93m",
            "error": "\033[91m",
            "reset": "\033[0m",
        }

        symbol = symbols.get(level, "ℹ️")
        color = colors.get(level, colors["info"])
        print(f"{color}{symbol} {message}{colors['reset']}")

    def check_environment_variables(self) -> bool:
        """Validate required environment variables."""
        self.log("Checking environment variables...")

        required_vars = [
            "DATABASE_URL",
            "REDIS_URL",
            "JWT_SECRET",
            "API_KEY",
            "OPENAI_API_KEY",
            "FRONTEND_URL",
            "BACKEND_URL",
        ]

        optional_vars = [
            "SENTRY_DSN",
            "AWS_ACCESS_KEY_ID",
            "AWS_SECRET_ACCESS_KEY",
            "SMTP_HOST",
            "SMTP_PORT",
        ]

        missing_required = []
        missing_optional = []

        # Check required variables
        for var in required_vars:
            if not os.getenv(var):
                missing_required.append(var)
                self.errors.append(f"Required environment variable '{var}' is not set")

        # Check optional variables
        for var in optional_vars:
            if not os.getenv(var):
                missing_optional.append(var)
                self.warnings.append(f"Optional environment variable '{var}' is not set")

        # Load .env.example to check for any additional variables
        env_example = Path(".env.example")
        if env_example.exists():
            with open(env_example, "r") as f:
                for line in f:
                    if "=" in line and not line.startswith("#"):
                        var_name = line.split("=")[0].strip()
                        if var_name and not os.getenv(var_name):
                            if (
                                var_name not in missing_required
                                and var_name not in missing_optional
                            ):
                                self.warnings.append(
                                    f"Variable '{var_name}' from .env.example is not set"
                                )

        self.results["environment_variables"] = {
            "status": len(missing_required) == 0,
            "missing_required": missing_required,
            "missing_optional": missing_optional,
        }

        if missing_required:
            self.log(f"Missing required variables: {', '.join(missing_required)}", "error")
            return False

        if missing_optional:
            self.log(f"Missing optional variables: {', '.join(missing_optional)}", "warning")

        self.log("Environment variables validated", "success")
        return True

    def check_database_connectivity(self) -> bool:
        """Check database connectivity and migrations."""
        self.log("Checking database connectivity...")

        try:
            database_url = os.getenv("DATABASE_URL")
            if not database_url:
                self.errors.append("DATABASE_URL not configured")
                return False

            # Parse database URL
            if database_url.startswith("postgresql://"):
                conn_params = psycopg2.extensions.parse_dsn(database_url)
            else:
                self.errors.append("Invalid DATABASE_URL format")
                return False

            # Test connection
            conn = psycopg2.connect(**conn_params)
            cursor = conn.cursor()

            # Check database version
            cursor.execute("SELECT version()")
            version = cursor.fetchone()[0]
            self.log(f"Database version: {version.split(',')[0]}", "info")

            # Check if migrations table exists
            cursor.execute("""
                SELECT EXISTS (
                    SELECT FROM information_schema.tables
                    WHERE table_schema = 'public'
                    AND table_name = 'alembic_version'
                )
            """)
            has_migrations = cursor.fetchone()[0]

            if not has_migrations:
                self.warnings.append("Migrations table not found - database may not be initialized")

            # Check table count
            cursor.execute("""
                SELECT COUNT(*)
                FROM information_schema.tables
                WHERE table_schema = 'public'
            """)
            table_count = cursor.fetchone()[0]
            self.log(f"Found {table_count} tables in database", "info")

            cursor.close()
            conn.close()

            self.results["database"] = {
                "status": True,
                "version": version.split(",")[0],
                "table_count": table_count,
                "migrations_initialized": has_migrations,
            }

            self.log("Database connectivity verified", "success")
            return True

        except psycopg2.OperationalError as e:
            self.errors.append(f"Database connection failed: {str(e)}")
            self.results["database"] = {"status": False, "error": str(e)}
            self.log(f"Database connection failed: {str(e)}", "error")
            return False

        except Exception as e:
            self.errors.append(f"Database check error: {str(e)}")
            self.results["database"] = {"status": False, "error": str(e)}
            self.log(f"Database check error: {str(e)}", "error")
            return False

    def check_redis_connectivity(self) -> bool:
        """Check Redis connectivity."""
        self.log("Checking Redis connectivity...")

        try:
            redis_url = os.getenv("REDIS_URL", "redis://localhost:6379/0")

            # Parse Redis URL
            if redis_url.startswith("redis://"):
                parts = redis_url.replace("redis://", "").split(":")
                host = parts[0]
                port = int(parts[1].split("/")[0]) if len(parts) > 1 else 6379
                db = int(parts[1].split("/")[1]) if "/" in parts[1] else 0
            else:
                host, port, db = "localhost", 6379, 0

            # Test connection
            r = redis.Redis(host=host, port=port, db=db)
            r.ping()

            # Get Redis info
            info = r.info()
            redis_version = info.get("redis_version", "unknown")
            used_memory = info.get("used_memory_human", "unknown")

            self.log(f"Redis version: {redis_version}, Memory: {used_memory}", "info")

            self.results["redis"] = {
                "status": True,
                "version": redis_version,
                "memory_usage": used_memory,
            }

            self.log("Redis connectivity verified", "success")
            return True

        except redis.ConnectionError as e:
            self.warnings.append(f"Redis connection failed: {str(e)}")
            self.results["redis"] = {"status": False, "error": str(e)}
            self.log(f"Redis connection failed (non-critical): {str(e)}", "warning")
            return True  # Redis is optional for basic operation

        except Exception as e:
            self.warnings.append(f"Redis check error: {str(e)}")
            self.results["redis"] = {"status": False, "error": str(e)}
            self.log(f"Redis check error: {str(e)}", "warning")
            return True  # Redis is optional

    def check_file_structure(self) -> bool:
        """Validate required files and directories exist."""
        self.log("Checking file structure...")

        required_files = [
            "api/main.py",
            "Makefile",
            "requirements.txt",
            "docker-compose.yml",
            "frontend/package.json",
            "frontend/next.config.js",
        ]

        required_dirs = ["api", "frontend", "database", "services", "models", "tests", "deployment"]

        missing_files = []
        missing_dirs = []

        for file_path in required_files:
            if not Path(file_path).exists():
                missing_files.append(file_path)
                self.errors.append(f"Required file missing: {file_path}")

        for dir_path in required_dirs:
            if not Path(dir_path).exists():
                missing_dirs.append(dir_path)
                self.errors.append(f"Required directory missing: {dir_path}")

        self.results["file_structure"] = {
            "status": len(missing_files) == 0 and len(missing_dirs) == 0,
            "missing_files": missing_files,
            "missing_dirs": missing_dirs,
        }

        if missing_files or missing_dirs:
            self.log("Missing files/directories found", "error")
            return False

        self.log("File structure validated", "success")
        return True

    def check_docker_configuration(self) -> bool:
        """Validate Docker configuration and daemon."""
        self.log("Checking Docker configuration...")

        try:
            # Check Docker daemon
            result = subprocess.run(["docker", "version"], capture_output=True, text=True)

            if result.returncode != 0:
                self.errors.append("Docker daemon not running")
                self.results["docker"] = {"status": False, "error": "Docker daemon not running"}
                return False

            # Check Docker Compose
            result = subprocess.run(["docker-compose", "--version"], capture_output=True, text=True)

            if result.returncode != 0:
                self.errors.append("Docker Compose not installed")
                self.results["docker"] = {"status": False, "error": "Docker Compose not installed"}
                return False

            # Validate Docker Compose files
            compose_files = ["docker-compose.yml", "docker-compose.prod.yml"]
            for compose_file in compose_files:
                if Path(compose_file).exists():
                    result = subprocess.run(
                        ["docker-compose", "-f", compose_file, "config"],
                        capture_output=True,
                        text=True,
                    )
                    if result.returncode != 0:
                        self.warnings.append(
                            f"Docker Compose file {compose_file} validation failed"
                        )

            # Check Dockerfile existence
            dockerfiles = ["Dockerfile", "frontend/Dockerfile"]
            for dockerfile in dockerfiles:
                if not Path(dockerfile).exists():
                    self.warnings.append(f"Dockerfile missing: {dockerfile}")

            self.results["docker"] = {"status": True}
            self.log("Docker configuration validated", "success")
            return True

        except FileNotFoundError:
            self.errors.append("Docker not installed")
            self.results["docker"] = {"status": False, "error": "Docker not installed"}
            self.log("Docker not installed", "error")
            return False

        except Exception as e:
            self.errors.append(f"Docker check error: {str(e)}")
            self.results["docker"] = {"status": False, "error": str(e)}
            self.log(f"Docker check error: {str(e)}", "error")
            return False

    def check_dependencies(self) -> bool:
        """Check Python and Node.js dependencies."""
        self.log("Checking dependencies...")

        issues = []

        # Check Python dependencies
        if Path("requirements.txt").exists():
            result = subprocess.run(["pip", "check"], capture_output=True, text=True)
            if result.returncode != 0:
                self.warnings.append("Python dependency conflicts detected")
                issues.append("Python dependency conflicts")

        # Check Node.js dependencies (frontend)
        if Path("frontend/package.json").exists():
            result = subprocess.run(
                ["pnpm", "audit", "--audit-level=high"],
                capture_output=True,
                text=True,
                cwd="frontend",
            )
            if result.returncode != 0 and "vulnerabilities" in result.stdout:
                self.warnings.append("Frontend dependency vulnerabilities detected")
                issues.append("Frontend vulnerabilities")

        self.results["dependencies"] = {"status": len(issues) == 0, "issues": issues}

        if issues:
            self.log("Dependency issues found (non-critical)", "warning")
        else:
            self.log("Dependencies validated", "success")

        return True  # Dependencies are warnings, not errors

    def check_api_endpoints(self) -> bool:
        """Validate API endpoints are properly configured."""
        self.log("Checking API endpoints...")

        try:
            # Run the validate_endpoints.py script if it exists
            if Path("validate_endpoints.py").exists():
                result = subprocess.run(
                    ["python", "validate_endpoints.py"], capture_output=True, text=True
                )

                if result.returncode == 0:
                    self.log("API endpoints validated", "success")
                    self.results["api_endpoints"] = {"status": True}
                    return True
                else:
                    self.warnings.append("API endpoint validation had issues")
                    self.results["api_endpoints"] = {
                        "status": False,
                        "error": result.stderr[:500] if result.stderr else "Validation failed",
                    }
                    return True  # Non-critical

            # If script doesn't exist, perform basic validation
            if Path("api/main.py").exists():
                result = subprocess.run(
                    ["python", "-c", "from api.main import app; print('API imports OK')"],
                    capture_output=True,
                    text=True,
                )

                if result.returncode == 0:
                    self.log("API structure validated", "success")
                    self.results["api_endpoints"] = {"status": True}
                    return True
                else:
                    self.errors.append("API import validation failed")
                    self.results["api_endpoints"] = {"status": False, "error": result.stderr[:500]}
                    return False

        except Exception as e:
            self.warnings.append(f"API endpoint check error: {str(e)}")
            self.results["api_endpoints"] = {"status": False, "error": str(e)}
            return True  # Non-critical

        return True

    def check_security_configuration(self) -> bool:
        """Validate security configurations."""
        self.log("Checking security configuration...")

        security_checks = {
            "jwt_secret": bool(os.getenv("JWT_SECRET")),
            "cors_configured": bool(os.getenv("FRONTEND_URL")),
            "ssl_configured": self.environment == "production",
            "api_key_set": bool(os.getenv("API_KEY")),
        }

        # Check for sensitive data in code
        sensitive_patterns = ["password=", "secret=", "token=", "api_key="]
        sensitive_files = []

        for pattern in sensitive_patterns:
            result = subprocess.run(
                ["grep", "-r", "--include=*.py", pattern, "api/", "services/"],
                capture_output=True,
                text=True,
            )
            if result.returncode == 0:
                lines = result.stdout.strip().split("\n")
                for line in lines:
                    if not line.startswith("#") and "os.getenv" not in line:
                        sensitive_files.append(line.split(":")[0])

        if sensitive_files:
            self.warnings.append(
                f"Potential hardcoded secrets found in: {', '.join(set(sensitive_files))}"
            )

        self.results["security"] = {
            "status": all(security_checks.values()),
            "checks": security_checks,
            "sensitive_files": list(set(sensitive_files)),
        }

        if not all(security_checks.values()):
            self.log("Security configuration incomplete", "warning")
        else:
            self.log("Security configuration validated", "success")

        return True  # Security warnings don't block deployment

    def generate_report(self) -> Dict:
        """Generate comprehensive pre-deployment report."""
        passed_checks = sum(1 for r in self.results.values() if r.get("status", False))
        total_checks = len(self.results)

        report = {
            "environment": self.environment,
            "status": "ready" if len(self.errors) == 0 else "not_ready",
            "checks_passed": f"{passed_checks}/{total_checks}",
            "results": self.results,
            "errors": self.errors,
            "warnings": self.warnings,
            "recommendations": self.get_recommendations(),
        }

        return report

    def get_recommendations(self) -> List[str]:
        """Get deployment recommendations based on check results."""
        recommendations = []

        if self.errors:
            recommendations.append("❌ Fix all errors before proceeding with deployment")

        if self.warnings:
            recommendations.append("⚠️ Review warnings and address if necessary")

        if not self.results.get("database", {}).get("migrations_initialized"):
            recommendations.append("📝 Run database migrations: 'alembic upgrade head'")

        if not self.results.get("redis", {}).get("status"):
            recommendations.append("🔧 Ensure Redis is running for caching functionality")

        if self.results.get("dependencies", {}).get("issues"):
            recommendations.append("📦 Update dependencies to resolve conflicts/vulnerabilities")

        if not recommendations:
            recommendations.append("✅ System is ready for deployment")

        return recommendations

    def run(self) -> bool:
        """Execute all pre-deployment checks.

        Returns:
            Boolean indicating if deployment can proceed
        """
        print("\n" + "=" * 60)
        print("🔍 PRE-DEPLOYMENT VALIDATION")
        print(f"Environment: {self.environment}")
        print("=" * 60 + "\n")

        # Run all checks
        checks = [
            self.check_environment_variables,
            self.check_database_connectivity,
            self.check_redis_connectivity,
            self.check_file_structure,
            self.check_docker_configuration,
            self.check_dependencies,
            self.check_api_endpoints,
            self.check_security_configuration,
        ]

        for check in checks:
            try:
                check()
            except Exception as e:
                self.log(f"Check failed with error: {str(e)}", "error")
                self.errors.append(f"Check {check.__name__} failed: {str(e)}")

        # Generate and display report
        report = self.generate_report()

        print("\n" + "=" * 60)
        print("📊 PRE-DEPLOYMENT REPORT")
        print("=" * 60)
        print(f"Status: {report['status'].upper()}")
        print(f"Checks Passed: {report['checks_passed']}")

        if self.errors:
            print("\n❌ ERRORS (must fix):")
            for error in self.errors:
                print(f"  • {error}")

        if self.warnings:
            print("\n⚠️ WARNINGS (review):")
            for warning in self.warnings:
                print(f"  • {warning}")

        print("\n📝 RECOMMENDATIONS:")
        for rec in report["recommendations"]:
            print(f"  {rec}")

        # Save report to file
        report_file = Path("deployment/reports/pre_deployment_report.json")
        report_file.parent.mkdir(parents=True, exist_ok=True)
        with open(report_file, "w") as f:
            json.dump(report, f, indent=2, default=str)
        print(f"\n📁 Full report saved to: {report_file}")

        print("=" * 60)

        # Return success if no critical errors
        return len(self.errors) == 0


def main():
    """Main entry point for pre-deployment checks."""
    parser = argparse.ArgumentParser(description="Pre-deployment validation for ruleIQ")
    parser.add_argument(
        "--env",
        choices=["staging", "production"],
        default="staging",
        help="Target deployment environment",
    )

    args = parser.parse_args()

    checker = PreDeploymentChecker(environment=args.env)
    success = checker.run()

    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()
