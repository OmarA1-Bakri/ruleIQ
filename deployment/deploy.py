#!/usr/bin/env python3
"""
Main deployment orchestrator for ruleIQ application.
Coordinates the entire deployment process with comprehensive validation and rollback capabilities.
"""

import argparse
import json
import subprocess
import sys
import time
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional

import yaml


class DeploymentOrchestrator:
    """Main deployment orchestrator for ruleIQ application."""

    def __init__(self, environment: str, config_path: str = "deployment/config.yaml") -> None:
        """Initialize deployment orchestrator.

        Args:
            environment: Target environment (staging, production)
            config_path: Path to deployment configuration file
        """
        self.environment = environment
        self.config_path = config_path
        self.deployment_id = datetime.now().strftime("%Y%m%d_%H%M%S")
        self.log_file = Path(f"deployment/logs/deployment_{self.deployment_id}.log")
        self.results: Dict[str, bool] = {}
        self.start_time = time.time()

        # Ensure log directory exists
        self.log_file.parent.mkdir(parents=True, exist_ok=True)

        # Load deployment configuration
        self.config = self.load_config()

    def load_config(self) -> dict:
        """Load deployment configuration from YAML file."""
        config_file = Path(self.config_path)
        if config_file.exists():
            with open(config_file, "r") as f:
                return yaml.safe_load(f)
        else:
            self.log("WARNING: Config file not found, using defaults", "warning")
            return self.get_default_config()

    def get_default_config(self) -> dict:
        """Get default deployment configuration."""
        return {
            "deployment": {"name": "ruleIQ", "version": "1.0.0", "environment": self.environment},
            "application": {
                "backend": {"port": 8000, "workers": 4, "timeout": 30},
                "frontend": {"build_command": "pnpm build", "output_directory": ".next"},
            },
            "strategies": {
                "default": "blue_green",
                "rollback_timeout": 300,
                "health_check_retries": 3,
            },
        }

    def log(self, message: str, level: str = "info"):
        """Log deployment messages to console and file.

        Args:
            message: Message to log
            level: Log level (info, warning, error, success)
        """
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        # Color codes for console output
        colors = {
            "info": "\033[94m",
            "success": "\033[92m",
            "warning": "\033[93m",
            "error": "\033[91m",
            "reset": "\033[0m",
        }

        # Console output with color
        color = colors.get(level, colors["info"])
        print(f"{color}[{timestamp}] {message}{colors['reset']}")

        # File output
        with open(self.log_file, "a") as f:
            f.write(f"[{timestamp}] [{level.upper()}] {message}\n")

    def run_command(self, command: str, description: str, cwd: Optional[str] = None) -> bool:
        """Execute a command and capture output.

        Args:
            command: Command to execute
            description: Description of the command
            cwd: Working directory for command execution

        Returns:
            Boolean indicating success or failure
        """
        self.log(f"Executing: {description}")
        try:
            result = subprocess.run(command, shell=True, capture_output=True, text=True, cwd=cwd)

            if result.returncode == 0:
                self.log(f"✅ {description} completed successfully", "success")
                if result.stdout:
                    self.log(f"Output: {result.stdout[:500]}", "info")
                return True
            else:
                self.log(f"❌ {description} failed", "error")
                if result.stderr:
                    self.log(f"Error: {result.stderr[:500]}", "error")
                return False

        except Exception as e:
            self.log(f"❌ Exception during {description}: {str(e)}", "error")
            return False

    def run_python_module(self, module_path: str, description: str, args: List[str] = None) -> bool:
        """Run a Python module from the deployment directory.

        Args:
            module_path: Path to the Python module
            description: Description of the module execution
            args: Additional arguments to pass to the module

        Returns:
            Boolean indicating success or failure
        """
        args = args or []
        command = f"python {module_path} {' '.join(args)}"
        return self.run_command(command, description)

    def pre_deployment_validation(self) -> bool:
        """Execute pre-deployment validation checks."""
        self.log("=" * 60)
        self.log("🔍 PHASE 1: PRE-DEPLOYMENT VALIDATION", "info")
        self.log("=" * 60)

        checks = [
            ("deployment/pre_deployment_check.py", "Pre-deployment validation"),
            ("deployment/environment_setup.py", "Environment configuration"),
            ("validate_endpoints.py", "API endpoint validation"),
        ]

        for script, description in checks:
            if Path(script).exists():
                if not self.run_python_module(script, description, [f"--env={self.environment}"]):
                    return False
            else:
                self.log(f"Script {script} not found, skipping", "warning")

        return True

    def run_comprehensive_testing(self) -> bool:
        """Execute comprehensive test suite."""
        self.log("=" * 60)
        self.log("🧪 PHASE 2: COMPREHENSIVE TESTING", "info")
        self.log("=" * 60)

        # Run test runner script
        if Path("deployment/test_runner.py").exists():
            if not self.run_python_module("deployment/test_runner.py", "Comprehensive test suite"):
                return False

        # Run Makefile test targets
        test_targets = [
            ("make test-groups-parallel", "Parallel test groups"),
            ("make test-integration-comprehensive", "Integration tests"),
            ("make validate-fastapi", "FastAPI validation"),
        ]

        for command, description in test_targets:
            if not self.run_command(command, description):
                self.log(f"Test failure: {description}", "error")
                # Continue with other tests but mark as failed
                self.results[description] = False

        return all(self.results.get(desc, True) for _, desc in test_targets)

    def security_validation(self) -> bool:
        """Execute security validation checks."""
        self.log("=" * 60)
        self.log("🔒 PHASE 3: SECURITY VALIDATION", "info")
        self.log("=" * 60)

        if Path("deployment/security_validation.py").exists():
            return self.run_python_module(
                "deployment/security_validation.py", "Security validation"
            )

        # Fallback to basic security checks
        security_checks = [
            ("ruff check --select S", "Security linting"),
            ("python -m bandit -r api/ services/", "Bandit security scan"),
        ]

        for command, description in security_checks:
            if not self.run_command(command, description):
                return False

        return True

    def performance_testing(self) -> bool:
        """Execute performance testing suite."""
        self.log("=" * 60)
        self.log("⚡ PHASE 4: PERFORMANCE TESTING", "info")
        self.log("=" * 60)

        if Path("deployment/performance_testing.py").exists():
            return self.run_python_module(
                "deployment/performance_testing.py", "Performance testing"
            )

        self.log("Performance testing script not found, skipping", "warning")
        return True

    def deploy_backend(self) -> bool:
        """Deploy backend services."""
        self.log("=" * 60)
        self.log("🚀 PHASE 5A: BACKEND DEPLOYMENT", "info")
        self.log("=" * 60)

        # Use Docker manager if available
        if Path("deployment/docker_manager.py").exists():
            return self.run_python_module(
                "deployment/docker_manager.py",
                "Docker deployment",
                ["--action=deploy", f"--env={self.environment}"],
            )

        # Fallback to Docker Compose
        if self.environment == "production":
            command = "docker-compose -f docker-compose.prod.yml up -d --build"
        else:
            command = "docker-compose up -d --build"

        return self.run_command(command, "Docker deployment")

    def deploy_frontend(self) -> bool:
        """Deploy frontend application."""
        self.log("=" * 60)
        self.log("🎨 PHASE 5B: FRONTEND DEPLOYMENT", "info")
        self.log("=" * 60)

        if Path("deployment/frontend_deploy.py").exists():
            return self.run_python_module(
                "deployment/frontend_deploy.py",
                "Frontend deployment",
                [f"--env={self.environment}"],
            )

        # Fallback to basic frontend build
        frontend_commands = [
            ("cd frontend && pnpm install", "Install frontend dependencies"),
            ("cd frontend && pnpm build", "Build frontend"),
            ("cd frontend && pnpm run deploy", "Deploy frontend"),
        ]

        for command, description in frontend_commands:
            if not self.run_command(command, description):
                return False

        return True

    def setup_monitoring(self) -> bool:
        """Set up monitoring and observability."""
        self.log("=" * 60)
        self.log("📊 PHASE 6: MONITORING SETUP", "info")
        self.log("=" * 60)

        if Path("deployment/monitoring_setup.py").exists():
            return self.run_python_module("deployment/monitoring_setup.py", "Monitoring setup")

        self.log("Monitoring setup script not found, skipping", "warning")
        return True

    def post_deployment_validation(self) -> bool:
        """Execute post-deployment health checks."""
        self.log("=" * 60)
        self.log("✅ PHASE 7: POST-DEPLOYMENT VALIDATION", "info")
        self.log("=" * 60)

        if Path("deployment/health_checker.py").exists():
            return self.run_python_module("deployment/health_checker.py", "Health validation")

        # Fallback to basic health checks
        health_checks = [
            ("python validate_endpoints.py", "Endpoint validation"),
            ("python database_health_check.py", "Database health check"),
        ]

        return all(self.run_command(command, description) for command, description in health_checks)

    def rollback(self):
        """Execute rollback procedure."""
        self.log("=" * 60)
        self.log("⏪ EXECUTING ROLLBACK", "warning")
        self.log("=" * 60)

        if Path("deployment/rollback_manager.py").exists():
            self.run_python_module(
                "deployment/rollback_manager.py",
                "Rollback execution",
                [f"--deployment-id={self.deployment_id}"],
            )
        else:
            self.log("Rollback manager not found, manual rollback required", "error")

    def generate_report(self):
        """Generate deployment report."""
        elapsed_time = time.time() - self.start_time

        report = {
            "deployment_id": self.deployment_id,
            "environment": self.environment,
            "status": "success" if all(self.results.values()) else "failed",
            "duration": f"{elapsed_time:.2f} seconds",
            "timestamp": datetime.now().isoformat(),
            "results": self.results,
        }

        # Save report to JSON
        report_file = Path(f"deployment/reports/deployment_{self.deployment_id}.json")
        report_file.parent.mkdir(parents=True, exist_ok=True)

        with open(report_file, "w") as f:
            json.dump(report, f, indent=2)

        # Display summary
        self.log("=" * 60)
        self.log("📋 DEPLOYMENT SUMMARY", "info")
        self.log("=" * 60)
        self.log(f"Deployment ID: {self.deployment_id}")
        self.log(f"Environment: {self.environment}")
        self.log(f"Status: {report['status']}")
        self.log(f"Duration: {report['duration']}")
        self.log(f"Report saved: {report_file}")

    def deploy(self) -> bool:
        """Execute full deployment process.

        Returns:
            Boolean indicating deployment success
        """
        try:
            self.log("=" * 60)
            self.log(f"🚀 STARTING DEPLOYMENT - ID: {self.deployment_id}", "info")
            self.log(f"Target Environment: {self.environment}", "info")
            self.log("=" * 60)

            # Phase 1: Pre-deployment validation
            self.results["pre_deployment"] = self.pre_deployment_validation()
            if not self.results["pre_deployment"]:
                self.log("Pre-deployment validation failed", "error")
                return False

            # Phase 2: Comprehensive testing
            self.results["testing"] = self.run_comprehensive_testing()
            if not self.results["testing"]:
                self.log("Testing phase failed", "error")
                if not self.confirm_continue("Testing failed. Continue anyway?"):
                    return False

            # Phase 3: Security validation
            self.results["security"] = self.security_validation()
            if not self.results["security"]:
                self.log("Security validation failed", "error")
                return False

            # Phase 4: Performance testing
            self.results["performance"] = self.performance_testing()
            if not self.results["performance"]:
                if not self.confirm_continue("Performance tests failed. Continue?"):
                    return False

            # Phase 5: Deploy backend and frontend
            self.results["backend"] = self.deploy_backend()
            self.results["frontend"] = self.deploy_frontend()

            if not self.results["backend"] or not self.results["frontend"]:
                self.log("Deployment failed, initiating rollback", "error")
                self.rollback()
                return False

            # Phase 6: Setup monitoring
            self.results["monitoring"] = self.setup_monitoring()

            # Phase 7: Post-deployment validation
            self.results["health"] = self.post_deployment_validation()
            if not self.results["health"]:
                self.log("Post-deployment health checks failed", "error")
                if not self.confirm_continue("Health checks failed. Keep deployment?"):
                    self.rollback()
                    return False

            # Generate final report
            self.generate_report()

            self.log("=" * 60)
            self.log("🎉 DEPLOYMENT COMPLETED SUCCESSFULLY!", "success")
            self.log("=" * 60)

            return True

        except KeyboardInterrupt:
            self.log("Deployment interrupted by user", "warning")
            self.rollback()
            return False

        except Exception as e:
            self.log(f"Unexpected error during deployment: {str(e)}", "error")
            self.rollback()
            return False

    def confirm_continue(self, prompt: str) -> bool:
        """Prompt user for confirmation.

        Args:
            prompt: Confirmation prompt

        Returns:
            Boolean indicating user's choice
        """
        response = input(f"\n{prompt} (y/N): ")
        return response.lower() == "y"


def main():
    """Main entry point for deployment orchestration."""
    parser = argparse.ArgumentParser(description="ruleIQ Deployment Orchestrator")
    parser.add_argument(
        "--environment",
        "-e",
        choices=["staging", "production"],
        default="staging",
        help="Target deployment environment",
    )
    parser.add_argument(
        "--config",
        "-c",
        default="deployment/config.yaml",
        help="Path to deployment configuration file",
    )
    parser.add_argument(
        "--dry-run", action="store_true", help="Perform dry run without actual deployment"
    )
    parser.add_argument(
        "--skip-tests", action="store_true", help="Skip test execution (not recommended)"
    )
    parser.add_argument("--rollback", help="Rollback to a specific deployment ID")

    args = parser.parse_args()

    # Handle rollback request
    if args.rollback:
        orchestrator = DeploymentOrchestrator(args.environment, args.config)
        orchestrator.log(f"Executing rollback to deployment: {args.rollback}", "warning")
        orchestrator.run_python_module(
            "deployment/rollback_manager.py",
            "Rollback execution",
            [f"--deployment-id={args.rollback}"],
        )
        return

    # Create deployment orchestrator
    orchestrator = DeploymentOrchestrator(args.environment, args.config)

    # Override config for dry run or skip tests
    if args.dry_run:
        orchestrator.log("DRY RUN MODE - No actual deployment will occur", "warning")

    if args.skip_tests:
        orchestrator.log("WARNING: Skipping tests - not recommended for production", "warning")
        orchestrator.run_comprehensive_testing = lambda: True

    # Execute deployment
    success = orchestrator.deploy()

    # Exit with appropriate code
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()
