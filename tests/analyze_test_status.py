#!/usr/bin/env python3
"""Analyze actual test status and coverage"""

import subprocess
import os
import sys

# Set test environment
os.environ["DATABASE_URL"] = "postgresql://postgres:postgres@localhost:5433/compliance_test"
os.environ["REDIS_URL"] = "redis://localhost:6380/0"
os.environ["ENVIRONMENT"] = "testing"

test_dirs = [
    "tests/unit/test_credential_encryption.py",
    "tests/unit/test_integration_service.py",
    "tests/models",
    "tests/ai",
    "tests/database",
    "tests/monitoring",
    "tests/fixtures",
    "tests/utils",
]

print("=" * 60)
print("ACTUAL TEST STATUS ANALYSIS")
print("=" * 60)

total_collected = 0
total_passed = 0
total_failed = 0
total_skipped = 0
total_errors = 0

for test_dir in test_dirs:
    if not os.path.exists(test_dir):
        continue

    print(f"\n📁 Testing: {test_dir}")
    try:
        result = subprocess.run(
            ["pytest", test_dir, "--tb=no", "-q"],
            capture_output=True,
            text=True,
            timeout=30,
        )

        output = result.stdout + result.stderr

        # Parse results
        for line in output.split("\n"):
            if "passed" in line:
                parts = line.split()
                for i, part in enumerate(parts):
                    if "passed" in part and i > 0:
                        try:
                            passed = int(parts[i - 1])
                            total_passed += passed
                            print(f"  ✅ Passed: {passed}")
                        except (ValueError, KeyError, IndexError):
                            pass
            if "failed" in line:
                parts = line.split()
                for i, part in enumerate(parts):
                    if "failed" in part and i > 0:
                        try:
                            failed = int(parts[i - 1])
                            total_failed += failed
                            print(f"  ❌ Failed: {failed}")
                        except (ValueError, KeyError, IndexError):
                            pass
            if "skipped" in line:
                parts = line.split()
                for i, part in enumerate(parts):
                    if "skipped" in part and i > 0:
                        try:
                            skipped = int(parts[i - 1])
                            total_skipped += skipped
                            print(f"  ⏭️  Skipped: {skipped}")
                        except (ValueError, KeyError, IndexError):
                            pass
            if "error" in line.lower() and "ERROR" in line and " error" in line:
                parts = line.split()
                for i, part in enumerate(parts):
                    if "error" in part.lower() and i > 0:
                        try:
                            errors = int(parts[i - 1])
                            total_errors += errors
                            print(f"  🔥 Errors: {errors}")
                            break
                        except (ValueError, KeyError, IndexError):
                            pass

    except subprocess.TimeoutExpired:
        print("  ⏱️  Timeout - tests took too long")
    except (ValueError, KeyError, IndexError) as e:
        print(f"  ⚠️  Error: {e}")

print("\n" + "=" * 60)
print("SUMMARY")
print("=" * 60)
print(f"✅ Total Passed:  {total_passed}")
print(f"❌ Total Failed:  {total_failed}")
print(f"⏭️  Total Skipped: {total_skipped}")
print(f"🔥 Total Errors:  {total_errors}")
print(f"📊 Total Run:     {total_passed + total_failed + total_skipped + total_errors}")

# Now run coverage on working tests
print("\n" + "=" * 60)
print("RUNNING COVERAGE ON WORKING TESTS")
print("=" * 60)

working_tests = [
    "tests/unit/test_credential_encryption.py",
    "tests/unit/test_integration_service.py",
    "tests/models",
]

result = subprocess.run(
    ["pytest"] + working_tests + ["--cov=.", "--cov-report=term", "--tb=no", "-q"],
    capture_output=True,
    text=True,
)

# Extract coverage percentage
for line in result.stdout.split("\n"):
    if "TOTAL" in line:
        print(f"\n{line}")
        parts = line.split()
        if len(parts) >= 4:
            print(f"\n📊 ACTUAL COVERAGE: {parts[-1]}")
