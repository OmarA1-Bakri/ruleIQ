#!/usr/bin/env python3
"""
Test type annotations validation.

This test ensures that the type annotation validation script works correctly
and that our target files pass the validation.
"""

import subprocess
import sys
from pathlib import Path
import pytest


def test_validation_script_exists():
    """Test that the validation script exists."""
    script_path = Path("scripts/validate_type_annotations.py")
    assert script_path.exists(), "Type annotation validation script not found"
    assert script_path.is_file(), "Type annotation validation script is not a file"


def test_validation_script_runs():
    """Test that the validation script runs without errors."""
    result = subprocess.run(
        [sys.executable, "scripts/validate_type_annotations.py"], capture_output=True, text=True
    )

    # The script should run (regardless of validation results)
    assert result.returncode in [0, 1], f"Script failed with unexpected error: {result.stderr}"


def test_target_files_pass_validation():
    """Test that target files pass type annotation validation."""
    target_files = [
        "api/clients/base_api_client.py",
        "api/clients/aws_client.py",
        "api/clients/google_workspace_client.py",
        "services/caching/cache_manager.py",
    ]

    # Run validation on target files
    result = subprocess.run(
        [sys.executable, "scripts/validate_type_annotations.py"] + target_files,
        capture_output=True,
        text=True,
    )

    # Check if validation passed
    if result.returncode != 0:
        print(f"Validation output:\n{result.stdout}")
        print(f"Validation errors:\n{result.stderr}")

    assert result.returncode == 0, f"Type annotation validation failed. Output:\n{result.stdout}"


def test_validation_detects_missing_annotations():
    """Test that the validation script detects missing annotations."""
    # Create a temporary test file with missing annotations
    test_file = Path("test_missing_annotations_temp.py")

    try:
        # Write a file with intentionally missing annotations
        test_file.write_text("""
class TestClass:
    def __init__(self):  # Missing return annotation
        pass

    @classmethod
    def class_method(cls):  # Missing return annotation
        pass

    @staticmethod
    def static_method():  # Missing return annotation
        pass

    def method_with_varargs(self, *args, **kwargs):  # Untyped varargs
        pass
""")

        # Run validation on the test file
        result = subprocess.run(
            [sys.executable, "scripts/validate_type_annotations.py", str(test_file)],
            capture_output=True,
            text=True,
        )

        # Should detect violations
        assert result.returncode == 1, "Script should have detected violations"
        assert "missing return annotation" in result.stdout.lower(), (
            "Should detect missing return annotations"
        )
        assert "untyped" in result.stdout.lower(), "Should detect untyped varargs"

    finally:
        # Clean up
        if test_file.exists():
            test_file.unlink()


def test_validation_passes_correct_annotations():
    """Test that the validation script passes files with correct annotations."""
    # Create a temporary test file with correct annotations
    test_file = Path("test_correct_annotations_temp.py")

    try:
        # Write a file with correct annotations
        test_file.write_text("""from typing import Any, Optional

class TestClass:
    def __init__(self) -> None:
        pass

    @classmethod
    def class_method(cls) -> str:
        return "test"

    @staticmethod
    def static_method() -> int:
        return 42

    def method_with_varargs(self, *args: Any, **kwargs: Any) -> Optional[str]:
        return None
""")

        # Run validation on the test file
        result = subprocess.run(
            [sys.executable, "scripts/validate_type_annotations.py", str(test_file)],
            capture_output=True,
            text=True,
        )

        # Should pass without violations
        assert result.returncode == 0, f"Script should have passed. Output:\n{result.stdout}"
        assert (
            "No violations" in result.stdout or "All type annotations are correct" in result.stdout
        )

    finally:
        # Clean up
        if test_file.exists():
            test_file.unlink()


if __name__ == "__main__":
    # Run tests
    pytest.main([__file__, "-v"])
