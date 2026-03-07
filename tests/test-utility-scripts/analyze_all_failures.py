"""Analyze all test failures in the codebase."""

import logging

logger = logging.getLogger(__name__)
import subprocess
import json
import sys
from pathlib import Path


def run_tests_and_analyze():
    """Run tests and capture failures."""
    logger.info("Running all tests to identify failures...")
    cmd = [
        sys.executable,
        "-m",
        "pytest",
        "--tb=short",
        "--json-report",
        "--json-report-file=test_failure_report.json",
        "-v",
    ]
    subprocess.run(cmd, capture_output=True, text=True)
    report_path = Path("test_failure_report.json")
    if not report_path.exists():
        logger.info("No test report generated. Running with basic output...")
        result = subprocess.run(
            [sys.executable, "-m", "pytest", "-v", "--tb=short"], capture_output=True, text=True
        )
        failures = []
        for line in result.stdout.split("\n"):
            if "FAILED" in line:
                failures.append(line.strip())
        logger.info("\nFound %s test failures:" % len(failures))
        for i, failure in enumerate(failures[:20], 1):
            logger.info("%s. %s" % (i, failure))
        if len(failures) > 20:
            logger.info("... and %s more failures" % (len(failures) - 20))
        return failures
    with open(report_path, "r") as f:
        report = json.load(f)
    failures = []
    for test in report.get("tests", []):
        if test["outcome"] == "failed":
            failures.append(
                {
                    "nodeid": test["nodeid"],
                    "error": test.get("call", {}).get("longrepr", "Unknown error"),
                }
            )
    logger.info("\nTotal test failures: %s" % len(failures))
    by_file = {}
    for failure in failures:
        file_path = failure["nodeid"].split("::")[0]
        if file_path not in by_file:
            by_file[file_path] = []
        by_file[file_path].append(failure)
    logger.info("\nFailures by file:")
    for file_path, file_failures in sorted(by_file.items()):
        logger.info("\n%s: %s failures" % (file_path, len(file_failures)))
        for f in file_failures[:3]:
            logger.info("  - %s" % f["nodeid"].split("::")[-1])
    return failures


if __name__ == "__main__":
    run_tests_and_analyze()
