"""

# Constants
MAX_RETRIES = 3

Comprehensive test failure analysis script.
Analyzes all test failures and categorizes them for targeted fixing.
"""

import subprocess
import sys
import os
import json
from pathlib import Path
from collections import defaultdict


def run_tests_with_detailed_output():
    """Run tests and capture detailed output."""
    print("🔍 Running comprehensive test analysis...")
    env = os.environ.copy()
    env.update(
        {
            "ENV": "testing",
            "USE_MOCK_AI": "true",
            "PYTHONDONTWRITEBYTECODE": "1",
            "PYTEST_CURRENT_TEST": "",
        }
    )
    cmd = [
        sys.executable,
        "-m",
        "pytest",
        "--tb=short",
        "-v",
        "--disable-warnings",
        "--maxfail=50",
        "--tb=short",
    ]
    result = subprocess.run(cmd, capture_output=True, text=True, env=env)
    return result


def analyze_failures(test_output):
    """Analyze test failures and categorize them."""
    failures = defaultdict(list)
    current_test = None
    error_buffer = []
    lines = test_output.split("\n")
    for line in lines:
        if "::" in line and ("FAILED" in line or "ERROR" in line):
            current_test = line.split()[0]
            if "FAILED" in line:
                failures["FAILED"].append(current_test)
            else:
                failures["ERROR"].append(current_test)
        if any(
            keyword in line
            for keyword in [
                "ImportError",
                "ModuleNotFoundError",
                "AttributeError",
                "TypeError",
                "ValueError",
                "AssertionError",
                "RuntimeError",
                "asyncio",
                "sqlalchemy",
                "pytest",
                "fixture",
            ]
        ):
            error_buffer.append(line.strip())
    return failures, error_buffer


def categorize_test_issues(failures, errors):
    """Categorize test issues by type."""
    categories = {
        "database_issues": [],
        "async_issues": [],
        "import_issues": [],
        "fixture_issues": [],
        "ai_service_issues": [],
        "cache_issues": [],
        "authentication_issues": [],
        "other_issues": [],
    }
    all_failed_tests = failures.get("FAILED", []) + failures.get("ERROR", [])
    for test in all_failed_tests:
        if any(keyword in test.lower() for keyword in ["database", "db_", "sql"]):
            categories["database_issues"].append(test)
        elif any(keyword in test.lower() for keyword in ["async", "asyncio"]):
            categories["async_issues"].append(test)
        elif any(keyword in test.lower() for keyword in ["import", "module"]):
            categories["import_issues"].append(test)
        elif any(keyword in test.lower() for keyword in ["fixture", "conftest"]):
            categories["fixture_issues"].append(test)
        elif any(
            keyword in test.lower() for keyword in ["ai_", "cached_content", "cache_strategy"]
        ):
            categories["ai_service_issues"].append(test)
        elif any(keyword in test.lower() for keyword in ["cache", "redis"]):
            categories["cache_issues"].append(test)
        elif any(keyword in test.lower() for keyword in ["auth", "login", "user"]):
            categories["authentication_issues"].append(test)
        else:
            categories["other_issues"].append(test)
    return categories


def generate_fix_strategy(categories):
    """Generate a comprehensive fix strategy."""
    strategy = {"priority_order": [], "fix_approaches": {}, "agent_assignments": {}}
    if categories["fixture_issues"]:
        strategy["priority_order"].append("fixture_issues")
        strategy["fix_approaches"]["fixture_issues"] = "Fix test configuration and setup"
        strategy["agent_assignments"]["fixture_issues"] = "Test Infrastructure Specialist"
    if categories["database_issues"]:
        strategy["priority_order"].append("database_issues")
        strategy["fix_approaches"]["database_issues"] = (
            "Fix database connections and async handling"
        )
        strategy["agent_assignments"]["database_issues"] = "Database & Async Specialist"
    if categories["import_issues"]:
        strategy["priority_order"].append("import_issues")
        strategy["fix_approaches"]["import_issues"] = "Fix module imports and dependencies"
        strategy["agent_assignments"]["import_issues"] = "Import & Dependency Specialist"
    if categories["ai_service_issues"]:
        strategy["priority_order"].append("ai_service_issues")
        strategy["fix_approaches"]["ai_service_issues"] = "Fix AI service mocking and caching"
        strategy["agent_assignments"]["ai_service_issues"] = "AI Service Testing Specialist"
    if categories["cache_issues"]:
        strategy["priority_order"].append("cache_issues")
        strategy["fix_approaches"]["cache_issues"] = "Fix cache and Redis mocking"
        strategy["agent_assignments"]["cache_issues"] = "Cache & Redis Specialist"
    if categories["authentication_issues"]:
        strategy["priority_order"].append("authentication_issues")
        strategy["fix_approaches"]["authentication_issues"] = (
            "Fix authentication and user management"
        )
        strategy["agent_assignments"]["authentication_issues"] = "Auth & Security Specialist"
    if categories["async_issues"]:
        strategy["priority_order"].append("async_issues")
        strategy["fix_approaches"]["async_issues"] = "Fix async/await patterns and event loops"
        strategy["agent_assignments"]["async_issues"] = "Async & Concurrency Specialist"
    if categories["other_issues"]:
        strategy["priority_order"].append("other_issues")
        strategy["fix_approaches"]["other_issues"] = "Fix miscellaneous test issues"
        strategy["agent_assignments"]["other_issues"] = "General Testing Specialist"
    return strategy


def main():
    """Main analysis function."""
    print("🧪 Comprehensive Test Failure Analysis")
    print("=" * 60)
    result = run_tests_with_detailed_output()
    failures, errors = analyze_failures(result.stdout + result.stderr)
    categories = categorize_test_issues(failures, errors)
    strategy = generate_fix_strategy(categories)
    print("\n📊 TEST ANALYSIS RESULTS")
    print("=" * 40)
    total_failed = len(failures.get("FAILED", [])) + len(failures.get("ERROR", []))
    print(f"Total Failed/Error Tests: {total_failed}")
    print("\n📋 ISSUE CATEGORIES:")
    for category, tests in categories.items():
        if tests:
            print(f"  • {category.replace('_', ' ').title()}: {len(tests)} tests")
            for test in tests[:3]:
                print(f"    - {test}")
            if len(tests) > MAX_RETRIES:
                print(f"    ... and {len(tests) - 3} more")
    print("\n🎯 FIX STRATEGY:")
    for i, category in enumerate(strategy["priority_order"], 1):
        agent = strategy["agent_assignments"][category]
        approach = strategy["fix_approaches"][category]
        count = len(categories[category])
        print(f"  {i}. {agent}")
        print(f"     → {approach} ({count} tests)")
    results = {
        "failures": dict(failures),
        "categories": dict(categories),
        "strategy": strategy,
        "error_samples": errors[:20],
    }
    with open("test_failure_analysis.json", "w") as f:
        json.dump(results, f, indent=2)
    print("\n💾 Detailed analysis saved to: test_failure_analysis.json")
    print(f"📤 Return code: {result.returncode}")
    return result.returncode == 0


if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
