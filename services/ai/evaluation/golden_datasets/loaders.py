"""Dataset loaders for Golden Dataset system."""

import json
from pathlib import Path
from typing import List, Dict, Any, Optional
from services.ai.evaluation.schemas import ComplianceScenario, EvidenceCase, RegulatoryQAPair
from services.ai.evaluation.golden_datasets.versioning import VersionManager


class JSONLLoader:
    """Load and save JSONL datasets."""

    def __init__(self, file_path: str) -> None:
        """Initialize loader with file path.

        Args:
            file_path: Path to JSONL file
        """
        self.file_path = Path(file_path)

    def load(self) -> List[Dict[str, Any]]:
        """Load data from JSONL file.

        Returns:
            List of parsed JSON objects
        """
        if not self.file_path.exists():
            return []
        data = []
        with open(self.file_path, "r") as f:
            for line in f:
                line = line.strip()
                if line:
                    data.append(json.loads(line))
        return data

    def save(self, data: List[Dict[str, Any]]) -> None:
        """Save data to JSONL file.

        Args:
            data: List of objects to save
        """
        self.file_path.parent.mkdir(parents=True, exist_ok=True)
        with open(self.file_path, "w") as f:
            for item in data:
                f.write(json.dumps(item) + "\n")


class GoldenDatasetLoader:
    """Main loader for golden datasets."""

    def __init__(self, root_path: str) -> None:
        """Initialize loader with root path.

        Args:
            root_path: Root directory containing dataset versions
        """
        self.root_path = Path(root_path)
        self.version_manager = VersionManager(self.root_path)

    def load_version(self, version: str) -> List[Dict[str, Any]]:
        """Load a specific version of the dataset.

        Args:
            version: Version string (X.Y.Z)

        Returns:
            List of dataset items
        """
        version_dir = self.root_path / f"v{version}"
        dataset_file = version_dir / "dataset.jsonl"
        if not dataset_file.exists():
            return []
        loader = JSONLLoader(str(dataset_file))
        return loader.load()

    def load_latest(self) -> List[Dict[str, Any]]:
        """Load the latest version of the dataset.

        Returns:
            List of dataset items
        """
        latest_version = self.version_manager.get_latest_version()
        if not latest_version:
            return []
        return self.load_version(latest_version)

    def parse_dataset(self, data: List[Dict[str, Any]]) -> Dict[str, List[Any]]:
        """Parse raw dataset into typed objects.

        Args:
            data: Raw dataset items

        Returns:
            Dictionary with lists of typed objects by category
        """
        parsed = {"compliance_scenarios": [], "evidence_cases": [], "regulatory_qa": []}
        for item in data:
            if item.get("type") == "compliance_scenario":
                scenario = ComplianceScenario(**item["data"])
                parsed["compliance_scenarios"].append(scenario)
            elif item.get("type") == "evidence_case":
                case = EvidenceCase(**item["data"])
                parsed["evidence_cases"].append(case)
            elif item.get("type") == "regulatory_qa":
                qa = RegulatoryQAPair(**item["data"])
                parsed["regulatory_qa"].append(qa)
        return parsed

    def save_version(
        self,
        data: List[Dict[str, Any]],
        version: str,
        created_by: str,
        description: str,
        changes: Optional[List[str]] = None,
    ) -> Path:
        """Save a new version of the dataset.

        Args:
            data: Dataset items to save
            version: Version string (X.Y.Z)
            created_by: User creating the version
            description: Version description
            changes: List of changes in this version

        Returns:
            Path to the created version directory
        """
        dataset_counts = {
            "compliance_scenarios": sum(
                (1 for item in data if item.get("type") == "compliance_scenario")
            ),
            "evidence_cases": sum((1 for item in data if item.get("type") == "evidence_case")),
            "regulatory_qa": sum((1 for item in data if item.get("type") == "regulatory_qa")),
        }
        version_dir = self.version_manager.create_version(
            version=version,
            created_by=created_by,
            description=description,
            changes=changes,
            dataset_counts=dataset_counts,
        )
        dataset_file = version_dir / "dataset.jsonl"
        loader = JSONLLoader(str(dataset_file))
        loader.save(data)
        return version_dir


class DatasetRegistry:
    """Registry for managing multiple datasets."""

    def __init__(self) -> None:
        """Initialize empty registry."""
        self.datasets: Dict[str, Dict[str, Any]] = {}
        self.loaders: Dict[str, GoldenDatasetLoader] = {}

    def register_dataset(self, name: str, path: str, version: Optional[str] = None) -> None:
        """Register a new dataset.

        Args:
            name: Dataset name
            path: Path to dataset root
            version: Optional specific version to use
        """
        self.datasets[name] = {"path": path, "version": version}
        self.loaders[name] = GoldenDatasetLoader(path)

    def get_dataset(self, name: str) -> Dict[str, Any]:
        """Get dataset information.

        Args:
            name: Dataset name

        Returns:
            Dataset information dictionary
        """
        return self.datasets.get(name, {})

    def load_dataset(self, name: str) -> List[Dict[str, Any]]:
        """Load a registered dataset.

        Args:
            name: Dataset name

        Returns:
            List of dataset items
        """
        if name not in self.loaders:
            return []
        loader = self.loaders[name]
        version = self.datasets[name].get("version")
        if version:
            return loader.load_version(version)
        else:
            return loader.load_latest()

    def list_datasets(self) -> List[str]:
        """List all registered datasets.

        Returns:
            List of dataset names
        """
        return list(self.datasets.keys())
