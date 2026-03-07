#!/usr/bin/env python3
"""Frontend deployment script for Next.js application."""

import argparse
import subprocess
import sys
from pathlib import Path
from typing import Tuple


class FrontendDeployer:
    """Deploy Next.js frontend application."""

    def __init__(self, environment: str = "staging") -> None:
        self.environment = environment
        self.frontend_dir = Path("frontend")

    def log(self, message: str, level: str = "info"):
        symbols = {"info": "ℹ️", "success": "✅", "warning": "⚠️", "error": "❌"}
        colors = {
            "info": "\033[94m",
            "success": "\033[92m",
            "warning": "\033[93m",
            "error": "\033[91m",
            "reset": "\033[0m",
        }
        print(
            f"{colors.get(level, colors['info'])}{symbols.get(level, 'ℹ️')} {message}{colors['reset']}"
        )

    def run_command(self, command: str, description: str, cwd=None) -> Tuple[bool, str]:
        self.log(f"Running: {description}")
        try:
            result = subprocess.run(command, shell=True, capture_output=True, text=True, cwd=cwd)
            if result.returncode == 0:
                self.log(f"✅ {description} completed", "success")
                return True, result.stdout
            else:
                self.log(f"❌ {description} failed", "error")
                return False, result.stderr
        except Exception as e:
            self.log(f"Exception: {str(e)}", "error")
            return False, str(e)

    def check_dependencies(self) -> bool:
        """Check and install frontend dependencies."""
        if not self.frontend_dir.exists():
            self.log("Frontend directory not found", "error")
            return False

        self.log("Installing frontend dependencies...")
        success, _ = self.run_command(
            "pnpm install", "Dependency installation", cwd=self.frontend_dir
        )
        return success

    def run_linting(self) -> bool:
        """Run ESLint and Prettier checks."""
        self.log("Running linting checks...")

        commands = [("pnpm run lint", "ESLint check"), ("pnpm run format:check", "Prettier check")]

        for cmd, desc in commands:
            success, _ = self.run_command(cmd, desc, cwd=self.frontend_dir)
            if not success:
                self.log(f"{desc} failed - continuing anyway", "warning")

        return True

    def run_type_checking(self) -> bool:
        """Run TypeScript type checking."""
        self.log("Running TypeScript type checking...")
        success, _ = self.run_command(
            "pnpm run type-check", "TypeScript validation", cwd=self.frontend_dir
        )
        return success

    def run_tests(self) -> bool:
        """Run frontend tests."""
        self.log("Running frontend tests...")
        success, _ = self.run_command("pnpm test", "Frontend tests", cwd=self.frontend_dir)
        if not success:
            self.log("Frontend tests failed - continuing deployment", "warning")
        return True

    def build_production(self) -> bool:
        """Build production-optimized frontend."""
        self.log("Building production frontend...")

        # Set environment variables for build
        env_vars = f"NEXT_PUBLIC_API_URL={os.getenv('BACKEND_URL', 'http://localhost:8000')}"
        command = f"{env_vars} pnpm build"

        success, _ = self.run_command(command, "Production build", cwd=self.frontend_dir)

        if success:
            # Check build output
            build_dir = self.frontend_dir / ".next"
            if build_dir.exists():
                self.log("Build output verified", "success")
            else:
                self.log("Build output not found", "error")
                return False

        return success

    def run_lighthouse_audit(self) -> bool:
        """Run Lighthouse performance audit."""
        self.log("Running Lighthouse audit...")

        if (self.frontend_dir / "lighthouserc.js").exists():
            success, _ = self.run_command(
                "npx lighthouse-ci autorun", "Lighthouse audit", cwd=self.frontend_dir
            )
            if not success:
                self.log("Lighthouse audit failed - non-critical", "warning")

        return True

    def deploy_to_vercel(self) -> bool:
        """Deploy to Vercel."""
        if self.environment != "production":
            self.log("Skipping Vercel deployment for non-production", "info")
            return True

        self.log("Deploying to Vercel...")

        if (self.frontend_dir.parent / "vercel.json").exists():
            command = "vercel --prod" if self.environment == "production" else "vercel"
            success, output = self.run_command(command, "Vercel deployment", cwd=self.frontend_dir)

            if success and "https://" in output:
                self.log(f"Deployment URL: {output}", "success")

            return success

        self.log("Vercel configuration not found", "warning")
        return True

    def deploy(self) -> bool:
        """Execute frontend deployment."""
        self.log("=" * 60)
        self.log("🎨 FRONTEND DEPLOYMENT")
        self.log(f"Environment: {self.environment}")
        self.log("=" * 60)

        steps = [
            (self.check_dependencies, "Dependencies"),
            (self.run_linting, "Linting"),
            (self.run_type_checking, "Type Checking"),
            (self.run_tests, "Tests"),
            (self.build_production, "Production Build"),
            (self.run_lighthouse_audit, "Performance Audit"),
            (self.deploy_to_vercel, "Vercel Deployment"),
        ]

        for func, name in steps:
            if not func():
                self.log(f"{name} failed", "error")
                return False

        self.log("✅ Frontend deployment completed!", "success")
        return True


def main():
    parser = argparse.ArgumentParser(description="Frontend deployment for ruleIQ")
    parser.add_argument("--env", choices=["staging", "production"], default="staging")
    args = parser.parse_args()

    deployer = FrontendDeployer(environment=args.env)
    success = deployer.deploy()
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()
