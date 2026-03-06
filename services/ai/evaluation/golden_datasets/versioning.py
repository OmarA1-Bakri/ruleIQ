#!/usr/bin/env python3
"""Dataset versioning utilities for Golden Dataset system."""

import json
import re
from datetime import datetime
from pathlib import Path
from typing import Optional, List, Dict, Any
from dataclasses import dataclass, asdict


def is_semver(v: str) -> bool:
    """Check if string is valid semantic version (strict X.Y.Z format).

    Args:
        v: Version string to validate

    Returns:
        True if valid semver, False otherwise
    """
    # Strict semantic versioning pattern: X.Y.Z
    # where X, Y, Z are non-negative integers without leading zeros
    # (except for 0 itself)
    # Use \A and \Z for absolute string boundaries (no whitespace allowed)
    pattern = r"\A(0|[1-9]\d*)\.(0|[1-9]\d*)\.(0|[1-9]\d*)\Z"
    return bool(re.match(pattern, v))


class DatasetVersion:
    """Semantic version for datasets."""

    def __init__(self, version: str) -> None:
        """Initialize version from string.

        Args:
            version: Version string in X.Y.Z format

        Raises:
            ValueError: If version format is invalid
        """
        if not is_semver(version):
            raise ValueError(f"Invalid version format: {version}. Must be X.Y.Z")

        parts = version.split(".")
        self.major = int(parts[0])
        self.minor = int(parts[1])
        self.patch = int(parts[2])
        self._version_str = version

    def __str__(self) -> str:
        """String representation."""
        return self._version_str

    def __repr__(self) -> str:
        """Debug representation."""
        return f"DatasetVersion('{self._version_str}')"

    def __eq__(self, other: object) -> bool:
        """Check equality."""
        if not isinstance(other, DatasetVersion):
            return NotImplemented
        return (self.major, self.minor, self.patch) == (
            other.major,
            other.minor,
            other.patch,
        )

    def __lt__(self, other: "DatasetVersion") -> bool:
        """Check if less than other version."""
        return (self.major, self.minor, self.patch) < (
            other.major,
            other.minor,
            other.patch,
        )

    def __le__(self, other: "DatasetVersion") -> bool:
        """Check if less than or equal."""
        return self < other or self == other

    def __gt__(self, other: "DatasetVersion") -> bool:
        """Check if greater than other version."""
        return (self.major, self.minor, self.patch) > (
            other.major,
            other.minor,
            other.patch,
        )

    def __ge__(self, other: "DatasetVersion") -> bool:
        """Check if greater than or equal."""
        return self > other or self == other

    def increment_patch(self) -> "DatasetVersion":
        """Create new version with incremented patch number."""
        return DatasetVersion(f"{self.major}.{self.minor}.{self.patch + 1}")

    def increment_minor(self) -> "DatasetVersion":
        """Create new version with incremented minor number (resets patch)."""
        return DatasetVersion(f"{self.major}.{self.minor + 1}.0")

    def increment_major(self) -> "DatasetVersion":
        """Create new version with incremented major number (resets minor and patch)."""
        return DatasetVersion(f"{self.major + 1}.0.0")


@dataclass
class VersionMetadata:
    """Metadata for a dataset version."""

    version: str
    created_at: datetime
    created_by: str
    description: str
    changes: List[str]
    dataset_counts: Dict[str, int]

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        data = asdict(self)
        data["created_at"] = self.created_at.isoformat()
        return data

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "VersionMetadata":
        """Create from dictionary."""
        data = data.copy()
        data["created_at"] = datetime.fromisoformat(data["created_at"])
        return cls(**data)


class VersionManager:
    """Manage dataset versions."""

    def __init__(self, base_path: Path) -> None:
        """Initialize version manager.

        Args:
            base_path: Base directory for dataset versions
        """
        self.base_path = Path(base_path)
        self.versions_file = self.base_path / "versions.json"
        self.base_path.mkdir(parents=True, exist_ok=True)

    def create_version(
        self,
        version: str,
        created_by: str,
        description: str,
        changes: Optional[List[str]] = None,
        dataset_counts: Optional[Dict[str, int]] = None,
    ) -> Path:
        """Create a new version directory.

        Args:
            version: Version string (X.Y.Z)
            created_by: User who created the version
            description: Version description
            changes: List of changes in this version
            dataset_counts: Count of items per dataset type

        Returns:
            Path to the created version directory
        """
        # Validate version
        DatasetVersion(version)

        # Create version directory
        version_dir = self.base_path / f"v{version}"
        version_dir.mkdir(exist_ok=True)

        # Create empty dataset file
        dataset_file = version_dir / "dataset.jsonl"
        dataset_file.touch()

        # Save version metadata
        metadata = VersionMetadata(
            version=version,
            created_at=datetime.now(),
            created_by=created_by,
            description=description,
            changes=changes or [],
            dataset_counts=dataset_counts or {},
        )

        self._update_versions_metadata(metadata)

        return version_dir

    def list_versions(self) -> List[str]:
        """List all available versions.

        Returns:
            List of version strings
        """
        versions = []
        for path in self.base_path.iterdir():
            if path.is_dir() and path.name.startswith("v"):
                version = path.name[1:]  # Remove 'v' prefix
                if is_semver(version):
                    versions.append(version)
        return sorted(versions, key=lambda v: DatasetVersion(v))

    def get_latest_version(self) -> Optional[str]:
        """Get the latest version.

        Returns:
            Latest version string or None if no versions exist
        """
        versions = self.list_versions()
        return versions[-1] if versions else None

    def get_version_metadata(self, version: str) -> Optional[VersionMetadata]:
        """Get metadata for a specific version.

        Args:
            version: Version string

        Returns:
            Version metadata or None if not found
        """
        if not self.versions_file.exists():
            return None

        with open(self.versions_file, "r") as f:
            all_metadata = json.load(f)

        if version in all_metadata:
            return VersionMetadata.from_dict(all_metadata[version])

        return None

    def _update_versions_metadata(self, metadata: VersionMetadata):
        """Update the versions metadata file.

        Args:
            metadata: Version metadata to add/update
        """
        all_metadata = {}
        if self.versions_file.exists():
            with open(self.versions_file, "r") as f:
                all_metadata = json.load(f)

        all_metadata[metadata.version] = metadata.to_dict()

        with open(self.versions_file, "w") as f:
            json.dump(all_metadata, f, indent=2)
