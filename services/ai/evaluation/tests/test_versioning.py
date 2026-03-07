"""Test versioning utilities."""

from typing import Any
from ..golden_datasets.versioning import is_semver

# Constants
MAX_RETRIES = 3


class TestSemanticVersioning:
    """Test semantic versioning validation."""

    def test_valid_semver(self) -> Any:
        """Test valid semantic versions."""
        valid_versions = [
            "0.0.0",
            "1.0.0",
            "0.1.0",
            "0.0.1",
            "1.2.3",
            "10.20.30",
            "99.99.99",
            "2.0.0",
            "1.10.0",
            "1.0.10",
        ]
        for version in valid_versions:
            assert is_semver(version), f"Version {version} should be valid"

    def test_invalid_semver(self) -> Any:
        """Test invalid semantic versions."""
        invalid_versions = [
            "1",
            "1.0",
            "v1.0.0",
            "1.0.0-alpha",
            "1.0.0+build",
            "1.0.0-alpha.1",
            "1.0.0-rc.1+build.123",
            "01.0.0",
            "1.01.0",
            "1.0.01",
            "1.0.0.0",
            "1.2",
            "a.b.c",
            "1.2.3.4",
            "1.-2.3",
            "1.2.-3",
            "-1.2.3",
            "1.2.3 ",
            " 1.2.3",
            "1. 2.3",
            "1..3",
            ".1.2",
            "1.2.",
            "١.٢.٣",
        ]
        for version in invalid_versions:
            assert not is_semver(version), f"Version {version} should be invalid"

    def test_edge_cases(self) -> Any:
        """Test edge cases for version validation."""
        assert not is_semver("")
        assert not is_semver("...")
        assert not is_semver("..")
        assert not is_semver(".")
        assert is_semver("0.0.0")
        assert is_semver("999.999.999")
        assert is_semver("1000.0.0")
        assert not is_semver("0")
        assert not is_semver("0.0")

    def test_leading_zeros_rejected(self) -> Any:
        """Test that leading zeros are properly rejected."""
        assert not is_semver("01.0.0")
        assert not is_semver("001.0.0")
        assert not is_semver("1.01.0")
        assert not is_semver("1.001.0")
        assert not is_semver("1.0.01")
        assert not is_semver("1.0.001")
        assert is_semver("0.0.0")
        assert is_semver("1.0.0")
        assert is_semver("0.1.0")
        assert is_semver("0.0.1")
        assert is_semver("10.0.0")
        assert is_semver("0.10.0")
        assert is_semver("0.0.10")

    def test_version_comparison_ready(self) -> Any:
        """Test versions that can be compared numerically."""
        versions = [
            "0.0.1",
            "0.1.0",
            "1.0.0",
            "1.0.1",
            "1.1.0",
            "2.0.0",
            "10.0.0",
            "10.1.0",
            "10.10.10",
        ]
        for version in versions:
            assert is_semver(version)
            parts = version.split(".")
            assert len(parts) == MAX_RETRIES
            assert all(part.isdigit() for part in parts)

    def test_unicode_and_special_chars(self) -> Any:
        """Test handling of unicode and special characters."""
        invalid_with_special = [
            "1→2→3",
            "1•2•3",
            "1×2×3",
            "1·2·3",
            "1‚2‚3",
            "1、2、3",
            "①.②.③",
            "1️⃣.2️⃣.3️⃣",
        ]
        for version in invalid_with_special:
            assert not is_semver(version), f"Version with special chars {version} should be invalid"

    def test_whitespace_handling(self) -> Any:
        """Test handling of various whitespace."""
        invalid_with_whitespace = [
            "1.2.3\n",
            "1.2.3\t",
            "1.2.3\r",
            "1\t.2.3",
            "1.2\n.3",
            "\n1.2.3",
            "1.2.3 ",
            " 1.2.3",
            "1 .2.3",
            "1. 2.3",
        ]
        for version in invalid_with_whitespace:
            assert not is_semver(version), f"Version with whitespace {version} should be invalid"
