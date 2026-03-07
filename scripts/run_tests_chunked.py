#!/usr/bin/env python3
"""
Test runner script for chunked test execution.
Optimizes test runs by grouping tests into logical chunks.
"""

import sys
import subprocess
import argparse
from pathlib import Path

# Test mode configurations
TEST_MODES = {
    "fast": {
        "description": "Fast unit tests only",
        "markers": "unit and not slow",
        "parallel": True,
        "workers": "auto",
    },
    "integration": {
        "description": "Integration tests",
        "markers": "integration",
        "parallel": True,
        "workers": 4,
    },
    "performance": {
        "description": "Performance tests",
        "markers": "performance or benchmark",
        "parallel": False,
        "workers": 1,
    },
    "ai": {
        "description": "AI and compliance tests",
        "markers": "ai or compliance or llm",
        "parallel": True,
        "workers": 2,
    },
    "security": {
        "description": "Security and auth tests",
        "markers": "security or auth",
        "parallel": True,
        "workers": 2,
    },
    "e2e": {
        "description": "End-to-end workflow tests",
        "markers": "e2e",
        "parallel": False,
        "workers": 1,
    },
    "full": {
        "description": "Complete test suite",
        "markers": "",
        "parallel": True,
        "workers": "auto",
    },
    "ci": {
        "description": "CI-optimized test run",
        "markers": "not slow and not performance",
        "parallel": True,
        "workers": 4,
    },
}


def run_pytest(mode_config, verbose=False):
    """Run pytest with specified configuration."""
    cmd = ["python", "-m", "pytest"]

    # Add markers if specified
    if mode_config["markers"]:
        cmd.extend(["-m", mode_config["markers"]])

    # Add parallelization
    if mode_config["parallel"]:
        workers = mode_config["workers"]
        if workers == "auto":
            cmd.extend(["-n", "auto", "--dist=worksteal"])
        else:
            cmd.extend(["-n", str(workers), "--dist=worksteal"])

    # Add common options
    cmd.extend(["--tb=short", "--maxfail=5"])

    if verbose:
        cmd.append("-v")

    # Run the command
    result = subprocess.run(cmd, cwd=Path(__file__).parent.parent)
    return result.returncode


def list_modes():
    """List all available test modes."""
    print("Available test modes:")
    print("-" * 50)
    for mode, config in TEST_MODES.items():
        print(f"  {mode:15} - {config['description']}")
    print("-" * 50)


def main():
    parser = argparse.ArgumentParser(description="Run tests in chunked mode")
    parser.add_argument("--mode", choices=list(TEST_MODES.keys()), help="Test mode to run")
    parser.add_argument("--list-modes", action="store_true", help="List all available test modes")
    parser.add_argument("--verbose", "-v", action="store_true", help="Verbose output")

    args = parser.parse_args()

    if args.list_modes:
        list_modes()
        return 0

    if not args.mode:
        print("Error: Please specify a test mode with --mode")
        list_modes()
        return 1

    mode_config = TEST_MODES[args.mode]
    print(f"Running {args.mode} tests: {mode_config['description']}")

    return run_pytest(mode_config, args.verbose)


if __name__ == "__main__":
    sys.exit(main())
