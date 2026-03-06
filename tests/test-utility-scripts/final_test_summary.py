#!/usr/bin/env python
"""Final test summary excluding streaming tests."""

import subprocess
import re

# Run pytest excluding streaming tests
result = subprocess.run(
    ["python", "-m", "pytest", "-v", "--tb=no", "-k", "not streaming"],
    capture_output=True,
    text=True,
    timeout=300,
)

# Parse output
output = result.stdout + result.stderr
lines = output.split("\n")

# Count results
passed = sum(1 for line in lines if "PASSED" in line and "::" in line)
failed = sum(1 for line in lines if "FAILED" in line and "::" in line)
errors = sum(1 for line in lines if "ERROR" in line and "::" in line and "log" not in line)
skipped = sum(1 for line in lines if "SKIPPED" in line and "::" in line)

print("Test Summary (excluding streaming tests):")
print(f"PASSED: {passed}")
print(f"FAILED: {failed}")
print(f"ERRORS: {errors}")
print(f"SKIPPED: {skipped}")
print(f"TOTAL: {passed + failed + errors + skipped}")

if failed > 0:
    print("\nFailed tests:")
    for line in lines:
        if "FAILED" in line and "::" in line:
            print(f"  - {line.strip()}")

if errors > 0:
    print("\nError tests:")
    for line in lines:
        if "ERROR" in line and "::" in line and "log" not in line:
            print(f"  - {line.strip()}")

# Get summary line
for line in reversed(lines):
    if "passed" in line and ("failed" in line or "error" in line):
        print(f"\nPytest summary: {line.strip()}")
        break

# Calculate success rate
total = passed + failed + errors
if total > 0:
    success_rate = (passed / total) * 100
    print(f"\nSuccess rate: {success_rate:.1f}%")
