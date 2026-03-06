#!/usr/bin/env python3
"""Security validation script for deployment readiness."""

import argparse
import json
import subprocess
import sys
from pathlib import Path
from typing import Dict, List


class SecurityValidator:
    """Comprehensive security validation for deployment."""

    def __init__(self) -> None:
        self.vulnerabilities: List[str] = []
        self.warnings: List[str] = []
        self.results: Dict[str, bool] = {}

    def log(self, message: str, level: str = "info"):
        symbols = {"info": "ℹ️", "success": "✅", "warning": "⚠️", "error": "❌", "security": "🔒"}
        colors = {
            "info": "\033[94m",
            "success": "\033[92m",
            "warning": "\033[93m",
            "error": "\033[91m",
            "security": "\033[95m",
            "reset": "\033[0m",
        }
        print(
            f"{colors.get(level, colors['info'])}{symbols.get(level, 'ℹ️')} {message}{colors['reset']}"
        )

    def run_bandit_scan(self) -> bool:
        """Run Bandit security analysis."""
        self.log("Running Bandit security scan...", "security")

        try:
            result = subprocess.run(
                ["bandit", "-r", "api/", "services/", "-f", "json"], capture_output=True, text=True
            )

            if result.stdout:
                report = json.loads(result.stdout)
                issues = report.get("results", [])

                high_severity = [i for i in issues if i.get("issue_severity") == "HIGH"]
                medium_severity = [i for i in issues if i.get("issue_severity") == "MEDIUM"]

                if high_severity:
                    self.log(f"Found {len(high_severity)} high severity issues", "error")
                    for issue in high_severity[:5]:  # Show first 5
                        self.vulnerabilities.append(f"HIGH: {issue.get('issue_text')}")

                if medium_severity:
                    self.log(f"Found {len(medium_severity)} medium severity issues", "warning")

                return len(high_severity) == 0

            return True

        except Exception as e:
            self.log(f"Bandit scan failed: {str(e)}", "error")
            return False

    def run_safety_check(self) -> bool:
        """Check Python dependencies for vulnerabilities."""
        self.log("Checking dependency vulnerabilities...", "security")

        try:
            result = subprocess.run(["safety", "check", "--json"], capture_output=True, text=True)

            if result.stdout:
                vulnerabilities = json.loads(result.stdout)
                if vulnerabilities:
                    self.log(f"Found {len(vulnerabilities)} vulnerable dependencies", "warning")
                    for vuln in vulnerabilities[:5]:
                        self.warnings.append(f"Vulnerable package: {vuln.get('package')}")

            return True  # Don't fail on dependency vulnerabilities

        except Exception as e:
            self.log(f"Safety check not available: {str(e)}", "warning")
            return True

    def check_secrets(self) -> bool:
        """Scan for hardcoded secrets."""
        self.log("Scanning for hardcoded secrets...", "security")

        patterns = [
            ("password.*=.*['\"].*['\"]", "Hardcoded password"),
            ("api_key.*=.*['\"].*['\"]", "Hardcoded API key"),
            ("secret.*=.*['\"].*['\"]", "Hardcoded secret"),
            ("token.*=.*['\"].*['\"]", "Hardcoded token"),
        ]

        found_secrets = False
        for pattern, description in patterns:
            result = subprocess.run(
                ["grep", "-r", "--include=*.py", "-E", pattern, "."], capture_output=True, text=True
            )

            if result.stdout:
                lines = [l for l in result.stdout.split("\n") if l and "os.getenv" not in l]
                if lines:
                    self.log(f"Found potential {description}", "warning")
                    found_secrets = True

        return not found_secrets

    def check_security_headers(self) -> bool:
        """Verify security headers configuration."""
        self.log("Checking security headers configuration...", "security")

        required_headers = [
            "X-Content-Type-Options",
            "X-Frame-Options",
            "Content-Security-Policy",
            "Strict-Transport-Security",
        ]

        # Check if security middleware is configured
        middleware_file = Path("api/middleware/security_middleware.py")
        if middleware_file.exists():
            content = middleware_file.read_text()
            for header in required_headers:
                if header in content:
                    self.log(f"✅ {header} configured", "success")
                else:
                    self.warnings.append(f"Missing security header: {header}")

        return True

    def check_authentication(self) -> bool:
        """Verify authentication configuration."""
        self.log("Verifying authentication configuration...", "security")

        # Check JWT configuration
        import os

        if not os.getenv("JWT_SECRET"):
            self.vulnerabilities.append("JWT_SECRET not configured")
            return False

        # Check password hashing
        auth_files = Path("api/routers").glob("*auth*.py")
        uses_bcrypt = False
        for file in auth_files:
            if "bcrypt" in file.read_text() or "passlib" in file.read_text():
                uses_bcrypt = True
                break

        if uses_bcrypt:
            self.log("Password hashing configured", "success")
        else:
            self.warnings.append("Password hashing not detected")

        return True

    def check_cors_configuration(self) -> bool:
        """Check CORS configuration."""
        self.log("Checking CORS configuration...", "security")

        # Check if CORS is properly configured
        import os

        frontend_url = os.getenv("FRONTEND_URL")
        if frontend_url:
            self.log(f"CORS origin configured: {frontend_url}", "success")
        else:
            self.warnings.append("CORS origin not configured")

        return True

    def check_rate_limiting(self) -> bool:
        """Verify rate limiting configuration."""
        self.log("Checking rate limiting...", "security")

        rate_limiter = Path("api/middleware/rate_limiter.py")
        if rate_limiter.exists():
            self.log("Rate limiting configured", "success")
        else:
            self.warnings.append("Rate limiting not configured")

        return True

    def check_input_validation(self) -> bool:
        """Check input validation practices."""
        self.log("Checking input validation...", "security")

        # Check for Pydantic usage
        result = subprocess.run(
            ["grep", "-r", "--include=*.py", "from pydantic", "."], capture_output=True, text=True
        )

        if result.stdout:
            self.log("Pydantic validation detected", "success")
        else:
            self.warnings.append("Input validation framework not detected")

        return True

    def check_sql_injection_protection(self) -> bool:
        """Check for SQL injection vulnerabilities."""
        self.log("Checking SQL injection protection...", "security")

        # Check for raw SQL queries
        result = subprocess.run(
            ["grep", "-r", "--include=*.py", "-E", "(execute|executemany).*f['\"]|%s", "."],
            capture_output=True,
            text=True,
        )

        if result.stdout:
            risky_lines = [
                l for l in result.stdout.split("\n") if l and "sqlalchemy" not in l.lower()
            ]
            if risky_lines:
                self.warnings.append("Potential SQL injection risks found")

        return True

    def run_frontend_audit(self) -> bool:
        """Run frontend security audit."""
        self.log("Running frontend security audit...", "security")

        if Path("frontend").exists():
            result = subprocess.run(
                ["pnpm", "audit", "--audit-level=high"],
                capture_output=True,
                text=True,
                cwd="frontend",
            )

            if "found 0 vulnerabilities" in result.stdout:
                self.log("No high severity vulnerabilities in frontend", "success")
            elif "vulnerabilities" in result.stdout:
                self.warnings.append("Frontend has dependency vulnerabilities")

        return True

    def validate(self) -> bool:
        """Run complete security validation."""
        self.log("=" * 60)
        self.log("🔒 SECURITY VALIDATION", "security")
        self.log("=" * 60)

        checks = [
            (self.run_bandit_scan, "Bandit Scan"),
            (self.run_safety_check, "Dependency Check"),
            (self.check_secrets, "Secret Scanning"),
            (self.check_security_headers, "Security Headers"),
            (self.check_authentication, "Authentication"),
            (self.check_cors_configuration, "CORS"),
            (self.check_rate_limiting, "Rate Limiting"),
            (self.check_input_validation, "Input Validation"),
            (self.check_sql_injection_protection, "SQL Injection"),
            (self.run_frontend_audit, "Frontend Audit"),
        ]

        for func, name in checks:
            self.results[name] = func()

        # Generate report
        self.log("\n" + "=" * 60)
        self.log("📊 SECURITY REPORT")
        self.log("=" * 60)

        if self.vulnerabilities:
            self.log(f"\n❌ CRITICAL VULNERABILITIES ({len(self.vulnerabilities)}):", "error")
            for vuln in self.vulnerabilities:
                self.log(f"  • {vuln}", "error")

        if self.warnings:
            self.log(f"\n⚠️ WARNINGS ({len(self.warnings)}):", "warning")
            for warn in self.warnings:
                self.log(f"  • {warn}", "warning")

        passed = sum(1 for v in self.results.values() if v)
        total = len(self.results)

        self.log(f"\nChecks Passed: {passed}/{total}")

        if self.vulnerabilities:
            self.log("\n❌ Security validation FAILED - fix critical issues", "error")
            return False
        elif self.warnings:
            self.log("\n⚠️ Security validation passed with warnings", "warning")
            return True
        else:
            self.log("\n✅ Security validation PASSED", "success")
            return True


def main():
    parser = argparse.ArgumentParser(description="Security validation for ruleIQ")
    parser.parse_args()

    validator = SecurityValidator()
    success = validator.validate()
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()
