#!/usr/bin/env python3
"""
Comprehensive test runner for deployment validation.
Executes all test suites and generates deployment confidence scores.
"""

import argparse
import json
import subprocess
import sys
import time
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Tuple


class TestRunner:
    """Comprehensive test execution for deployment validation."""

    def __init__(self, verbose: bool = False, parallel: bool = True) -> None:
        """Initialize test runner.

        Args:
            verbose: Enable verbose output
            parallel: Run tests in parallel where possible
        """
        self.verbose = verbose
        self.parallel = parallel
        self.results: Dict[str, Dict] = {}
        self.start_time = time.time()
        self.total_tests = 0
        self.passed_tests = 0
        self.failed_tests = 0
        self.skipped_tests = 0

    def log(self, message: str, level: str = "info"):
        """Log messages with formatting.

        Args:
            message: Message to log
            level: Log level (info, success, warning, error)
        """
        symbols = {"info": "ℹ️", "success": "✅", "warning": "⚠️", "error": "❌", "test": "🧪"}

        colors = {
            "info": "\033[94m",
            "success": "\033[92m",
            "warning": "\033[93m",
            "error": "\033[91m",
            "test": "\033[95m",
            "reset": "\033[0m",
        }

        symbol = symbols.get(level, "ℹ️")
        color = colors.get(level, colors["info"])
        print(f"{color}{symbol} {message}{colors['reset']}")

    def run_command(
        self, command: str, description: str, timeout: int = 300
    ) -> Tuple[bool, str, float]:
        """Execute a test command and capture results.

        Args:
            command: Command to execute
            description: Test description
            timeout: Command timeout in seconds

        Returns:
            Tuple of (success, output, duration)
        """
        self.log(f"Running: {description}", "test")
        start = time.time()

        try:
            result = subprocess.run(
                command, shell=True, capture_output=True, text=True, timeout=timeout
            )

            duration = time.time() - start
            success = result.returncode == 0

            # Parse test output for statistics
            output = result.stdout + result.stderr
            self.parse_test_output(output)

            if success:
                self.log(f"✅ {description} passed ({duration:.2f}s)", "success")
            else:
                self.log(f"❌ {description} failed ({duration:.2f}s)", "error")
                if self.verbose and result.stderr:
                    print(f"Error output:\n{result.stderr[:1000]}")

            return success, output, duration

        except subprocess.TimeoutExpired:
            duration = time.time() - start
            self.log(f"⏱️ {description} timed out after {timeout}s", "error")
            return False, "Test timed out", duration

        except Exception as e:
            duration = time.time() - start
            self.log(f"💥 {description} failed with exception: {str(e)}", "error")
            return False, str(e), duration

    def parse_test_output(self, output: str):
        """Parse test output for statistics.

        Args:
            output: Test command output
        """
        # Parse pytest output
        if "passed" in output or "failed" in output:
            import re

            # Look for pytest summary
            pattern = r"(\d+) passed.*?(\d+) failed.*?(\d+) skipped"
            match = re.search(pattern, output)
            if match:
                self.passed_tests += int(match.group(1))
                self.failed_tests += int(match.group(2))
                self.skipped_tests += int(match.group(3))
                self.total_tests += sum([int(match.group(i)) for i in range(1, 4)])
            else:
                # Try simpler pattern
                passed = re.findall(r"(\d+) passed", output)
                failed = re.findall(r"(\d+) failed", output)
                if passed:
                    self.passed_tests += int(passed[0])
                    self.total_tests += int(passed[0])
                if failed:
                    self.failed_tests += int(failed[0])
                    self.total_tests += int(failed[0])

    def run_unit_tests(self) -> bool:
        """Run unit tests using optimized test groups."""
        self.log("=" * 60)
        self.log("🧪 UNIT TESTS", "info")
        self.log("=" * 60)

        test_commands = []

        # Use Makefile's optimized test groups if available
        if Path("Makefile").exists():
            if self.parallel:
                test_commands.append(("make test-groups-parallel", "Parallel test groups"))
            else:
                test_commands.extend(
                    [
                        ("make test-core", "Core tests"),
                        ("make test-api", "API tests"),
                        ("make test-services", "Service tests"),
                        ("make test-models", "Model tests"),
                    ]
                )
        else:
            # Fallback to direct pytest
            test_commands.append(("pytest tests/unit -v", "Unit tests"))

        all_passed = True
        for command, description in test_commands:
            success, output, duration = self.run_command(command, description)
            self.results[f"unit_{description.lower().replace(' ', '_')}"] = {
                "status": success,
                "duration": duration,
                "command": command,
            }
            if not success:
                all_passed = False

        return all_passed

    def run_integration_tests(self) -> bool:
        """Run integration tests."""
        self.log("=" * 60)
        self.log("🔗 INTEGRATION TESTS", "info")
        self.log("=" * 60)

        test_commands = []

        # Use Makefile integration test targets
        if Path("Makefile").exists():
            test_commands.append(
                ("make test-integration-comprehensive", "Comprehensive integration tests")
            )
        else:
            # Fallback to direct pytest
            test_commands.extend(
                [
                    ("pytest tests/integration -v", "Integration tests"),
                    ("pytest tests/test_database_integration.py -v", "Database integration"),
                    (
                        "pytest tests/test_agentic_system_integration.py -v",
                        "Agent system integration",
                    ),
                ]
            )

        all_passed = True
        for command, description in test_commands:
            success, output, duration = self.run_command(command, description)
            self.results[f"integration_{description.lower().replace(' ', '_')}"] = {
                "status": success,
                "duration": duration,
                "command": command,
            }
            if not success:
                all_passed = False

        return all_passed

    def run_security_tests(self) -> bool:
        """Run security tests and scans."""
        self.log("=" * 60)
        self.log("🔒 SECURITY TESTS", "info")
        self.log("=" * 60)

        test_commands = [
            ("pytest tests/test_security_validation.py -v", "Security validation tests"),
            ("pytest tests/test_cache_security.py -v", "Cache security tests"),
            ("pytest tests/test_security_regression.py -v", "Security regression tests"),
            ("bandit -r api/ services/ -f json -o security_report.json", "Bandit security scan"),
            ("ruff check --select S", "Security linting"),
        ]

        all_passed = True
        for command, description in test_commands:
            # Check if test file exists before running
            if "pytest" in command:
                test_file = command.split()[1]
                if not Path(test_file).exists():
                    self.log(f"Test file {test_file} not found, skipping", "warning")
                    continue

            success, output, duration = self.run_command(command, description)
            self.results[f"security_{description.lower().replace(' ', '_')}"] = {
                "status": success,
                "duration": duration,
                "command": command,
            }
            if not success:
                all_passed = False

        return all_passed

    def run_performance_tests(self) -> bool:
        """Run performance and load tests."""
        self.log("=" * 60)
        self.log("⚡ PERFORMANCE TESTS", "info")
        self.log("=" * 60)

        test_commands = [
            (
                "pytest tests/test_database_performance_optimization.py -v",
                "Database performance tests",
            ),
            ("pytest tests/test_load_balancing_scaling.py -v", "Load balancing tests"),
            ("pytest tests/test_caching_system.py -v", "Caching system tests"),
            ("pytest tests/test_connection_pool_manager.py -v", "Connection pool tests"),
        ]

        # Add performance directory tests if it exists
        if Path("tests/performance").exists():
            test_commands.append(("pytest tests/performance -v", "Performance test suite"))

        all_passed = True
        for command, description in test_commands:
            # Check if test file exists
            if "pytest" in command:
                test_path = command.split()[1]
                if not Path(test_path).exists():
                    self.log(f"Test path {test_path} not found, skipping", "warning")
                    continue

            success, output, duration = self.run_command(command, description, timeout=600)
            self.results[f"performance_{description.lower().replace(' ', '_')}"] = {
                "status": success,
                "duration": duration,
                "command": command,
            }
            if not success:
                all_passed = False

        return all_passed

    def run_api_tests(self) -> bool:
        """Run API validation and contract tests."""
        self.log("=" * 60)
        self.log("🌐 API TESTS", "info")
        self.log("=" * 60)

        test_commands = [
            ("python validate_endpoints.py", "API endpoint validation"),
            ("make validate-fastapi", "FastAPI validation"),
            ("pytest tests/test_auth_service.py -v", "Authentication tests"),
        ]

        all_passed = True
        for command, description in test_commands:
            # Check if script/file exists
            if "python" in command:
                script = command.split()[1]
                if not Path(script).exists():
                    self.log(f"Script {script} not found, skipping", "warning")
                    continue
            elif "pytest" in command:
                test_file = command.split()[1]
                if not Path(test_file).exists():
                    self.log(f"Test file {test_file} not found, skipping", "warning")
                    continue

            success, output, duration = self.run_command(command, description)
            self.results[f"api_{description.lower().replace(' ', '_')}"] = {
                "status": success,
                "duration": duration,
                "command": command,
            }
            if not success:
                all_passed = False

        return all_passed

    def run_frontend_tests(self) -> bool:
        """Run frontend tests."""
        self.log("=" * 60)
        self.log("🎨 FRONTEND TESTS", "info")
        self.log("=" * 60)

        if not Path("frontend").exists():
            self.log("Frontend directory not found, skipping frontend tests", "warning")
            return True

        test_commands = [
            ("cd frontend && pnpm test", "Frontend unit tests"),
            ("cd frontend && pnpm run lint", "Frontend linting"),
            ("cd frontend && pnpm run type-check", "TypeScript validation"),
        ]

        all_passed = True
        for command, description in test_commands:
            success, output, duration = self.run_command(command, description)
            self.results[f"frontend_{description.lower().replace(' ', '_')}"] = {
                "status": success,
                "duration": duration,
                "command": command,
            }
            if not success:
                all_passed = False

        return all_passed

    def run_database_tests(self) -> bool:
        """Run database migration and integrity tests."""
        self.log("=" * 60)
        self.log("🗄️ DATABASE TESTS", "info")
        self.log("=" * 60)

        test_commands = [
            ("python database_health_check.py", "Database health check"),
            ("pytest tests/test_database_health.py -v", "Database health tests"),
            ("pytest tests/test_database_providers.py -v", "Database provider tests"),
            ("pytest tests/test_database_dependencies.py -v", "Database dependency tests"),
            (
                "pytest tests/test_database_backward_compatibility.py -v",
                "Database compatibility tests",
            ),
        ]

        all_passed = True
        for command, description in test_commands:
            # Check if test file exists
            if "python" in command:
                script = command.split()[1]
                if not Path(script).exists():
                    self.log(f"Script {script} not found, skipping", "warning")
                    continue
            elif "pytest" in command:
                test_file = command.split()[1]
                if not Path(test_file).exists():
                    self.log(f"Test file {test_file} not found, skipping", "warning")
                    continue

            success, output, duration = self.run_command(command, description)
            self.results[f"database_{description.lower().replace(' ', '_')}"] = {
                "status": success,
                "duration": duration,
                "command": command,
            }
            if not success:
                all_passed = False

        return all_passed

    def run_code_quality_tests(self) -> bool:
        """Run code quality and static analysis tests."""
        self.log("=" * 60)
        self.log("📝 CODE QUALITY TESTS", "info")
        self.log("=" * 60)

        test_commands = [
            ("ruff check .", "Ruff linting"),
            ("ruff format --check .", "Code formatting check"),
            ("pytest tests/test_import_cleanup.py -v", "Import cleanup tests"),
            ("pytest tests/test_syntax_validation.py -v", "Syntax validation tests"),
            ("pytest tests/test_type_annotations.py -v", "Type annotation tests"),
        ]

        all_passed = True
        for command, description in test_commands:
            # Check if test file exists for pytest commands
            if "pytest" in command:
                test_file = command.split()[1]
                if not Path(test_file).exists():
                    self.log(f"Test file {test_file} not found, skipping", "warning")
                    continue

            success, output, duration = self.run_command(command, description)
            self.results[f"quality_{description.lower().replace(' ', '_')}"] = {
                "status": success,
                "duration": duration,
                "command": command,
            }
            if not success:
                all_passed = False

        return all_passed

    def calculate_confidence_score(self) -> float:
        """Calculate deployment confidence score based on test results.

        Returns:
            Confidence score as percentage (0-100)
        """
        if not self.results:
            return 0.0

        # Weight different test categories
        weights = {
            "unit": 0.25,
            "integration": 0.20,
            "security": 0.15,
            "performance": 0.10,
            "api": 0.15,
            "database": 0.10,
            "quality": 0.05,
            "frontend": 0.05,
        }

        weighted_score = 0.0
        total_weight = 0.0

        for test_name, result in self.results.items():
            # Determine category from test name
            category = test_name.split("_")[0]
            weight = weights.get(category, 0.05)

            if result.get("status", False):
                weighted_score += weight
            total_weight += weight

        if total_weight == 0:
            return 0.0

        return (weighted_score / total_weight) * 100

    def generate_report(self) -> Dict:
        """Generate comprehensive test report.

        Returns:
            Test report dictionary
        """
        elapsed_time = time.time() - self.start_time
        confidence_score = self.calculate_confidence_score()

        # Count results
        passed = sum(1 for r in self.results.values() if r.get("status", False))
        failed = len(self.results) - passed

        report = {
            "timestamp": datetime.now().isoformat(),
            "duration": f"{elapsed_time:.2f} seconds",
            "total_tests_run": len(self.results),
            "passed": passed,
            "failed": failed,
            "test_statistics": {
                "total": self.total_tests,
                "passed": self.passed_tests,
                "failed": self.failed_tests,
                "skipped": self.skipped_tests,
            },
            "confidence_score": f"{confidence_score:.1f}%",
            "deployment_ready": confidence_score >= 80.0,
            "results": self.results,
            "recommendations": self.get_recommendations(confidence_score),
        }

        return report

    def get_recommendations(self, confidence_score: float) -> List[str]:
        """Get recommendations based on test results.

        Args:
            confidence_score: Calculated confidence score

        Returns:
            List of recommendations
        """
        recommendations = []

        if confidence_score >= 95:
            recommendations.append("✅ Excellent test coverage - ready for production deployment")
        elif confidence_score >= 80:
            recommendations.append("✅ Good test coverage - deployment can proceed with caution")
        elif confidence_score >= 60:
            recommendations.append("⚠️ Moderate test coverage - review failures before deployment")
        else:
            recommendations.append("❌ Insufficient test coverage - fix failures before deployment")

        # Specific recommendations based on failures
        for test_name, result in self.results.items():
            if not result.get("status", False):
                if "security" in test_name:
                    recommendations.append(f"🔒 Fix security test: {test_name}")
                elif "integration" in test_name:
                    recommendations.append(f"🔗 Fix integration test: {test_name}")
                elif "database" in test_name:
                    recommendations.append(f"🗄️ Fix database test: {test_name}")

        # Performance recommendations
        slow_tests = [
            (name, result["duration"])
            for name, result in self.results.items()
            if result.get("duration", 0) > 60
        ]
        if slow_tests:
            recommendations.append(
                f"⏱️ Optimize slow tests: {', '.join([t[0] for t in slow_tests])}"
            )

        return recommendations

    def run_all_tests(self) -> bool:
        """Execute all test suites.

        Returns:
            Boolean indicating overall success
        """
        print("\n" + "=" * 60)
        print("🚀 COMPREHENSIVE TEST EXECUTION")
        print(f"Parallel: {self.parallel}")
        print(f"Verbose: {self.verbose}")
        print("=" * 60)

        # Run test suites in order of importance
        test_suites = [
            (self.run_unit_tests, "Unit Tests"),
            (self.run_integration_tests, "Integration Tests"),
            (self.run_security_tests, "Security Tests"),
            (self.run_api_tests, "API Tests"),
            (self.run_database_tests, "Database Tests"),
            (self.run_performance_tests, "Performance Tests"),
            (self.run_code_quality_tests, "Code Quality"),
            (self.run_frontend_tests, "Frontend Tests"),
        ]

        overall_success = True
        for test_func, suite_name in test_suites:
            try:
                success = test_func()
                if not success:
                    overall_success = False
                    self.log(f"{suite_name} had failures", "warning")
            except Exception as e:
                self.log(f"{suite_name} failed with exception: {str(e)}", "error")
                overall_success = False

        return overall_success

    def display_summary(self, report: Dict):
        """Display test execution summary.

        Args:
            report: Test report dictionary
        """
        print("\n" + "=" * 60)
        print("📊 TEST EXECUTION SUMMARY")
        print("=" * 60)
        print(f"Duration: {report['duration']}")
        print(f"Tests Run: {report['total_tests_run']}")
        print(f"Passed: {report['passed']} ✅")
        print(f"Failed: {report['failed']} ❌")

        if report["test_statistics"]["total"] > 0:
            print("\nDetailed Statistics:")
            print(f"  Total Test Cases: {report['test_statistics']['total']}")
            print(f"  Passed: {report['test_statistics']['passed']}")
            print(f"  Failed: {report['test_statistics']['failed']}")
            print(f"  Skipped: {report['test_statistics']['skipped']}")

        print(f"\n🎯 Deployment Confidence Score: {report['confidence_score']}")

        status = (
            "✅ READY FOR DEPLOYMENT"
            if report["deployment_ready"]
            else "❌ NOT READY FOR DEPLOYMENT"
        )
        print(f"\nDeployment Status: {status}")

        print("\n📝 RECOMMENDATIONS:")
        for rec in report["recommendations"]:
            print(f"  {rec}")

        # Show failed tests
        failed_tests = [
            name for name, result in report["results"].items() if not result.get("status", False)
        ]
        if failed_tests:
            print("\n❌ FAILED TESTS:")
            for test in failed_tests:
                print(f"  • {test}")


def main():
    """Main entry point for test runner."""
    parser = argparse.ArgumentParser(description="Comprehensive test runner for ruleIQ deployment")
    parser.add_argument("--verbose", "-v", action="store_true", help="Enable verbose output")
    parser.add_argument("--sequential", "-s", action="store_true", help="Run tests sequentially")
    parser.add_argument(
        "--suite",
        choices=["unit", "integration", "security", "performance", "all"],
        default="all",
        help="Test suite to run",
    )
    parser.add_argument("--report", "-r", help="Output report file path")
    parser.add_argument("--timeout", "-t", type=int, default=300, help="Test timeout in seconds")

    args = parser.parse_args()

    # Create test runner
    runner = TestRunner(verbose=args.verbose, parallel=not args.sequential)

    # Run tests based on suite selection
    if args.suite == "all":
        success = runner.run_all_tests()
    elif args.suite == "unit":
        success = runner.run_unit_tests()
    elif args.suite == "integration":
        success = runner.run_integration_tests()
    elif args.suite == "security":
        success = runner.run_security_tests()
    elif args.suite == "performance":
        success = runner.run_performance_tests()
    else:
        success = runner.run_all_tests()

    # Generate and display report
    report = runner.generate_report()
    runner.display_summary(report)

    # Save report if requested
    if args.report:
        report_path = Path(args.report)
        report_path.parent.mkdir(parents=True, exist_ok=True)
        with open(report_path, "w") as f:
            json.dump(report, f, indent=2)
        print(f"\n📁 Report saved to: {report_path}")
    else:
        # Save to default location
        report_path = Path("deployment/reports/test_report.json")
        report_path.parent.mkdir(parents=True, exist_ok=True)
        with open(report_path, "w") as f:
            json.dump(report, f, indent=2)

    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()
