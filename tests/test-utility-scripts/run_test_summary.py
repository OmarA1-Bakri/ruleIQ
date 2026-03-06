#!/usr/bin/env python
"""Get a summary of test failures."""

import subprocess
import re

# Run pytest and capture output
result = subprocess.run(
    ["python", "-m", "pytest", "--tb=no", "-q"],
    capture_output=True,
    text=True,
)

# Parse output
output = result.stdout + result.stderr
lines = output.split("\n")

# Find failures
failures = []
errors = []

for line in lines:
    if "FAILED" in line:
        failures.append(line.strip())
    elif "ERROR" in line and "::" in line:
        errors.append(line.strip())

print(f"Total test failures: {len(failures)}")
print(f"Total test errors: {len(errors)}")

print("\nFailed tests:")
for f in failures[:20]:  # Show first 20
    print(f"  - {f}")

print("\nError tests:")
for e in errors[:20]:  # Show first 20
    print(f"  - {e}")

# Get final summary
for line in reversed(lines):
    if "failed" in line and "passed" in line:
        print(f"\nSummary: {line.strip()}")
        break
