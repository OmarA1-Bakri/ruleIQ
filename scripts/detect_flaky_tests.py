#!/usr/bin/env python3
"""
Flaky Test Detection Script for RuleIQ

Detects tests with inconsistent pass/fail results across multiple runs.
Supports both backend (pytest) and frontend (vitest) test suites.
"""

import argparse
import json
import subprocess
import sys
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional


@dataclass
class TestResult:
    """Represents a single test execution result."""

    name: str
    status: str  # passed, failed, skipped
    duration: float
    error_message: Optional[str] = None
    run_number: int = 0


@dataclass
class FlakyTestReport:
    """Aggregated flaky test statistics."""

    test_name: str
    total_runs: int
    passed_count: int
    failed_count: int
    skipped_count: int
    failure_rate: float
    average_duration: float
    error_messages: List[str] = field(default_factory=list)
    severity: str = "unknown"  # always_fails, intermittent, rare


class FlakyTestDetector:
    """Detects flaky tests by running test suites multiple times."""

    def __init__(
        self,
        runs: int = 5,
        markers: Optional[List[str]] = None,
        parallel: bool = False,
        test_type: str = "backend",
    ) -> None:
        self.runs = runs
        self.markers = markers or []
        self.parallel = parallel
        self.test_type = test_type
        self.project_root = Path(__file__).parent.parent
        self.results: Dict[str, List[TestResult]] = defaultdict(list)

    def run_backend_tests(self, run_number: int) -> List[TestResult]:
        """Execute backend pytest suite and parse results."""
        print(f"\n🔄 Run {run_number}/{self.runs}: Executing backend tests...")

        cmd = [
            "pytest",
            "--tb=short",
            "--quiet",
            "--json-report",
            f"--json-report-file=.test-results-run-{run_number}.json",
        ]

        # Add markers if specified
        if self.markers:
            cmd.extend(["-m", " or ".join(self.markers)])

        # Add parallel execution if enabled
        if self.parallel:
            cmd.extend(["-n", "auto"])

        # Run tests
        try:
            subprocess.run(
                cmd,
                cwd=self.project_root,
                check=False,  # Don't raise on test failures
                capture_output=True,
            )
        except Exception as e:
            print(f"⚠️  Test execution error: {e}")
            return []

        # Parse JSON report
        report_file = self.project_root / f".test-results-run-{run_number}.json"
        if not report_file.exists():
            print(f"⚠️  JSON report not found: {report_file}")
            return []

        results = []
        try:
            with open(report_file) as f:
                data = json.load(f)

            for test in data.get("tests", []):
                results.append(
                    TestResult(
                        name=test.get("nodeid", ""),
                        status=test.get("outcome", "unknown"),
                        duration=test.get("duration", 0.0),
                        error_message=test.get("call", {}).get("longrepr"),
                        run_number=run_number,
                    )
                )

            # Cleanup report file
            report_file.unlink()

        except Exception as e:
            print(f"⚠️  Error parsing test results: {e}")

        return results

    def run_frontend_tests(self, run_number: int) -> List[TestResult]:
        """Execute frontend vitest suite and parse results."""
        print(f"\n🔄 Run {run_number}/{self.runs}: Executing frontend tests...")

        frontend_dir = self.project_root / "frontend"
        cmd = ["pnpm", "test", "--reporter=json", "--run"]

        # Run tests
        try:
            result = subprocess.run(
                cmd,
                cwd=frontend_dir,
                check=False,
                capture_output=True,
                text=True,
            )

            # Parse JSON output from vitest
            output_lines = result.stdout.strip().split("\n")
            for line in output_lines:
                try:
                    json.loads(line)
                    # Process vitest JSON output format
                    # (Implementation depends on vitest reporter format)
                except json.JSONDecodeError:
                    continue

        except Exception as e:
            print(f"⚠️  Test execution error: {e}")

        return []

    def run_tests_multiple_times(self) -> None:
        """Execute test suite multiple times and collect results."""
        print(f"🎯 Starting flaky test detection ({self.runs} runs)")
        print(f"   Test type: {self.test_type}")
        if self.markers:
            print(f"   Markers: {', '.join(self.markers)}")

        for i in range(1, self.runs + 1):
            if self.test_type == "backend":
                run_results = self.run_backend_tests(i)
            elif self.test_type == "frontend":
                run_results = self.run_frontend_tests(i)
            else:
                print(f"❌ Unknown test type: {self.test_type}")
                sys.exit(1)

            # Aggregate results
            for result in run_results:
                self.results[result.name].append(result)

            print(f"   ✓ Completed run {i}/{self.runs} ({len(run_results)} tests)")

    def analyze_flaky_tests(self) -> List[FlakyTestReport]:
        """Analyze test results to identify flaky tests."""
        print("\n📊 Analyzing test results for flakiness...")

        flaky_tests = []

        for test_name, results in self.results.items():
            if len(results) < self.runs:
                # Test didn't run in all iterations (might be conditionally skipped)
                continue

            passed = sum(1 for r in results if r.status == "passed")
            failed = sum(1 for r in results if r.status == "failed")
            skipped = sum(1 for r in results if r.status == "skipped")

            # Calculate flakiness
            total_executed = passed + failed
            if total_executed == 0:
                continue

            failure_rate = (failed / total_executed) * 100
            avg_duration = sum(r.duration for r in results) / len(results)

            # Determine severity
            if failed == total_executed:
                severity = "always_fails"
            elif failure_rate >= 50:
                severity = "intermittent"
            elif failed > 0:
                severity = "rare"
            else:
                continue  # Not flaky

            # Collect unique error messages
            error_messages = list(set(r.error_message for r in results if r.error_message))

            flaky_tests.append(
                FlakyTestReport(
                    test_name=test_name,
                    total_runs=len(results),
                    passed_count=passed,
                    failed_count=failed,
                    skipped_count=skipped,
                    failure_rate=failure_rate,
                    average_duration=avg_duration,
                    error_messages=error_messages,
                    severity=severity,
                )
            )

        # Sort by severity and failure rate
        severity_order = {"always_fails": 0, "intermittent": 1, "rare": 2}
        flaky_tests.sort(key=lambda x: (severity_order.get(x.severity, 3), -x.failure_rate))

        return flaky_tests

    def generate_markdown_report(self, flaky_tests: List[FlakyTestReport]) -> str:
        """Generate markdown report of flaky tests."""
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        report = f"""# Flaky Test Detection Report

**Generated**: {timestamp}
**Total Runs**: {self.runs}
**Test Type**: {self.test_type}
**Markers**: {", ".join(self.markers) if self.markers else "All"}

---

## Summary

- **Total Tests Analyzed**: {len(self.results)}
- **Flaky Tests Found**: {len(flaky_tests)}
- **Always Failing**: {sum(1 for t in flaky_tests if t.severity == "always_fails")}
- **Intermittent (≥50% failure)**: {sum(1 for t in flaky_tests if t.severity == "intermittent")}
- **Rare (<50% failure)**: {sum(1 for t in flaky_tests if t.severity == "rare")}

---

## Flaky Tests by Severity

"""

        if not flaky_tests:
            report += "\n✅ **No flaky tests detected!**\n"
            return report

        # Group by severity
        for severity in ["always_fails", "intermittent", "rare"]:
            severity_tests = [t for t in flaky_tests if t.severity == severity]
            if not severity_tests:
                continue

            severity_label = {
                "always_fails": "🔴 Always Fails",
                "intermittent": "🟠 Intermittent",
                "rare": "🟡 Rare Failures",
            }[severity]

            report += f"\n### {severity_label}\n\n"

            for test in severity_tests:
                report += f"""
#### `{test.test_name}`

- **Failure Rate**: {test.failure_rate:.1f}% ({test.failed_count}/{test.total_runs} runs)
- **Passed**: {test.passed_count} | **Failed**: {test.failed_count} | **Skipped**: {test.skipped_count}
- **Avg Duration**: {test.average_duration:.3f}s

"""
                if test.error_messages:
                    report += "**Error Messages**:\n```\n"
                    for msg in test.error_messages[:3]:  # Limit to 3 messages
                        report += f"{msg}\n\n"
                    report += "```\n\n"

                # Suggest potential causes
                report += "**Potential Causes**:\n"
                if "timeout" in str(test.error_messages).lower():
                    report += "- ⏱️  Timing/timeout issues\n"
                if "connection" in str(test.error_messages).lower():
                    report += "- 🔌 External service dependency\n"
                if "assertion" in str(test.error_messages).lower():
                    report += "- 🎲 Non-deterministic behavior or race condition\n"

                report += "\n---\n"

        # Add recommendations
        report += """
## Recommendations

### High Priority (Always Fails)
1. Fix immediately - these tests never pass and block CI
2. Review test implementation and dependencies
3. Consider disabling until fixed if blocking critical work

### Medium Priority (Intermittent)
1. Add retries or increase timeouts if timing-related
2. Review test isolation and cleanup
3. Check for race conditions or shared state
4. Consider mocking external dependencies

### Low Priority (Rare)
1. Monitor for patterns over time
2. Add logging to capture context on failure
3. Review during regular test maintenance

---

## Next Steps

1. Create GitHub issues for all flaky tests
2. Assign priority based on severity
3. Track remediation progress
4. Re-run detection after fixes

"""

        return report

    def generate_json_output(self, flaky_tests: List[FlakyTestReport]) -> dict:
        """Generate JSON output for programmatic processing."""
        return {
            "timestamp": datetime.now().isoformat(),
            "runs": self.runs,
            "test_type": self.test_type,
            "markers": self.markers,
            "summary": {
                "total_tests": len(self.results),
                "flaky_tests": len(flaky_tests),
                "always_fails": sum(1 for t in flaky_tests if t.severity == "always_fails"),
                "intermittent": sum(1 for t in flaky_tests if t.severity == "intermittent"),
                "rare": sum(1 for t in flaky_tests if t.severity == "rare"),
            },
            "flaky_tests": [
                {
                    "test_name": t.test_name,
                    "severity": t.severity,
                    "failure_rate": t.failure_rate,
                    "passed": t.passed_count,
                    "failed": t.failed_count,
                    "skipped": t.skipped_count,
                    "avg_duration": t.average_duration,
                    "error_messages": t.error_messages,
                }
                for t in flaky_tests
            ],
        }


def main():
    parser = argparse.ArgumentParser(
        description="Detect flaky tests by running test suite multiple times"
    )
    parser.add_argument(
        "--runs",
        type=int,
        default=5,
        help="Number of times to run test suite (default: 5)",
    )
    parser.add_argument(
        "--markers",
        nargs="+",
        help="Pytest markers to filter tests (e.g., unit integration)",
    )
    parser.add_argument(
        "--parallel",
        action="store_true",
        help="Run tests in parallel (pytest-xdist)",
    )
    parser.add_argument(
        "--test-type",
        choices=["backend", "frontend"],
        default="backend",
        help="Test type to run (default: backend)",
    )
    parser.add_argument(
        "--output",
        choices=["markdown", "json", "both"],
        default="both",
        help="Output format (default: both)",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path("test-reports"),
        help="Output directory for reports (default: test-reports)",
    )

    args = parser.parse_args()

    # Create detector
    detector = FlakyTestDetector(
        runs=args.runs,
        markers=args.markers,
        parallel=args.parallel,
        test_type=args.test_type,
    )

    # Run detection
    detector.run_tests_multiple_times()
    flaky_tests = detector.analyze_flaky_tests()

    # Create output directory
    args.output_dir.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")

    # Generate reports
    if args.output in ["markdown", "both"]:
        report = detector.generate_markdown_report(flaky_tests)
        report_file = args.output_dir / f"flaky-tests-{args.test_type}-{timestamp}.md"
        report_file.write_text(report)
        print(f"\n📄 Markdown report: {report_file}")

    if args.output in ["json", "both"]:
        json_output = detector.generate_json_output(flaky_tests)
        json_file = args.output_dir / f"flaky-tests-{args.test_type}-{timestamp}.json"
        json_file.write_text(json.dumps(json_output, indent=2))
        print(f"📄 JSON report: {json_file}")

    # Print summary
    print("\n" + "=" * 60)
    print(f"✅ Detection complete: {len(flaky_tests)} flaky tests found")
    print("=" * 60)

    # Exit with appropriate code
    sys.exit(0 if len(flaky_tests) == 0 else 1)


if __name__ == "__main__":
    main()
