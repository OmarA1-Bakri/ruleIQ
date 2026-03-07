"""Test Golden Dataset loaders and versioning."""

import pytest
import json
import tempfile
from pathlib import Path
from datetime import datetime
from services.ai.evaluation.golden_datasets.loaders import (
    GoldenDatasetLoader,
    JSONLLoader,
    DatasetRegistry,
)
from services.ai.evaluation.golden_datasets.versioning import (
    DatasetVersion,
    VersionManager,
    VersionMetadata,
)
from services.ai.evaluation.schemas.compliance_scenario import ComplianceScenario
from services.ai.evaluation.schemas.common import (
    RegCitation,
    SourceMeta,
    TemporalValidity,
    ExpectedOutcome,
)

from tests.test_constants import MAX_RETRIES

# Constants


class TestDatasetVersion:
    """Test dataset versioning."""

    def test_version_comparison(self):
        """Test version comparison operations."""
        v1 = DatasetVersion("1.0.0")
        v2 = DatasetVersion("1.0.1")
        v3 = DatasetVersion("2.0.0")
        assert v1 < v2
        assert v2 < v3
        assert v1 < v3
        assert v3 > v1
        assert v2 > v1
        assert v1 == DatasetVersion("1.0.0")

    def test_version_parsing(self):
        """Test version string parsing."""
        v = DatasetVersion("2.1.3")
        assert v.major == 2
        assert v.minor == 1
        assert v.patch == MAX_RETRIES
        assert str(v) == "2.1.3"

    def test_version_validation(self):
        """Test version string validation."""
        with pytest.raises(ValueError, match="Invalid version format"):
            DatasetVersion("invalid")
        with pytest.raises(ValueError, match="Invalid version format"):
            DatasetVersion("1.2")
        with pytest.raises(ValueError, match="Invalid version format"):
            DatasetVersion("1.2.3.4")

    def test_version_increment(self):
        """Test version increment methods."""
        v = DatasetVersion("1.2.3")
        v_patch = v.increment_patch()
        assert str(v_patch) == "1.2.4"
        v_minor = v.increment_minor()
        assert str(v_minor) == "1.3.0"
        v_major = v.increment_major()
        assert str(v_major) == "2.0.0"


class TestVersionManager:
    """Test version management."""

    def test_version_metadata(self):
        """Test version metadata creation."""
        meta = VersionMetadata(
            version="1.0.0",
            created_at=datetime.now(),
            created_by="test_user",
            description="Initial version",
            changes=["Added compliance scenarios", "Added evidence cases"],
            dataset_counts={"compliance_scenarios": 10, "evidence_cases": 5, "regulatory_qa": 20},
        )
        assert meta.version == "1.0.0"
        assert meta.created_by == "test_user"
        assert len(meta.changes) == 2
        assert meta.dataset_counts["compliance_scenarios"] == 10

    def test_version_manager_init(self):
        """Test version manager initialization."""
        with tempfile.TemporaryDirectory() as tmpdir:
            base_path = Path(tmpdir)
            manager = VersionManager(base_path)
            assert manager.base_path == base_path
            assert manager.versions_file == base_path / "versions.json"

    def test_create_version(self):
        """Test creating a new version."""
        with tempfile.TemporaryDirectory() as tmpdir:
            base_path = Path(tmpdir)
            manager = VersionManager(base_path)
            version_path = manager.create_version(
                version="1.0.0", created_by="test_user", description="Test version"
            )
            assert version_path.exists()
            assert version_path == base_path / "v1.0.0"
            assert (version_path / "dataset.jsonl").exists()

    def test_list_versions(self):
        """Test listing available versions."""
        with tempfile.TemporaryDirectory() as tmpdir:
            base_path = Path(tmpdir)
            manager = VersionManager(base_path)
            manager.create_version("1.0.0", "user1", "Version 1")
            manager.create_version("1.1.0", "user2", "Version 2")
            manager.create_version("2.0.0", "user3", "Version 3")
            versions = manager.list_versions()
            assert len(versions) == MAX_RETRIES
            assert "1.0.0" in versions
            assert "1.1.0" in versions
            assert "2.0.0" in versions

    def test_get_latest_version(self):
        """Test getting the latest version."""
        with tempfile.TemporaryDirectory() as tmpdir:
            base_path = Path(tmpdir)
            manager = VersionManager(base_path)
            manager.create_version("1.0.0", "user1", "Version 1")
            manager.create_version("1.1.0", "user2", "Version 2")
            manager.create_version("2.0.0", "user3", "Version 3")
            latest = manager.get_latest_version()
            assert latest == "2.0.0"


class TestJSONLLoader:
    """Test JSONL loader."""

    def test_load_empty_file(self):
        """Test loading an empty JSONL file."""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".jsonl") as f:
            loader = JSONLLoader(f.name)
            data = loader.load()
            assert data == []

    def test_load_compliance_scenarios(self):
        """Test loading compliance scenarios from JSONL."""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".jsonl") as f:
            scenario_data = {
                "type": "compliance_scenario",
                "data": {
                    "id": "CS001",
                    "title": "Test scenario",
                    "description": "Test description",
                    "obligation_id": "OBL001",
                    "triggers": ["trigger1"],
                    "expected_outcome": {"outcome_code": "COMPLIANT", "details": {}},
                    "temporal": {"effective_from": "2024-01-01T00:00:00"},
                    "version": "1.0.0",
                    "source": {
                        "source_kind": "manual",
                        "method": "test",
                        "created_by": "test",
                        "created_at": "2024-01-01T00:00:00",
                    },
                    "created_at": "2024-01-01T00:00:00",
                },
            }
            f.write(json.dumps(scenario_data) + "\n")
            f.flush()
            loader = JSONLLoader(f.name)
            data = loader.load()
            assert len(data) == 1
            assert data[0]["type"] == "compliance_scenario"

    def test_load_mixed_types(self):
        """Test loading mixed data types from JSONL."""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".jsonl") as f:
            scenario = {"type": "compliance_scenario", "data": {"id": "CS001"}}
            evidence = {"type": "evidence_case", "data": {"id": "EC001"}}
            qa = {"type": "regulatory_qa", "data": {"id": "QA001"}}
            f.write(json.dumps(scenario) + "\n")
            f.write(json.dumps(evidence) + "\n")
            f.write(json.dumps(qa) + "\n")
            f.flush()
            loader = JSONLLoader(f.name)
            data = loader.load()
            assert len(data) == MAX_RETRIES
            assert data[0]["type"] == "compliance_scenario"
            assert data[1]["type"] == "evidence_case"
            assert data[2]["type"] == "regulatory_qa"

    def test_save_to_jsonl(self):
        """Test saving data to JSONL format."""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".jsonl", delete=False) as f:
            temp_path = f.name
        try:
            data = [
                {"type": "compliance_scenario", "data": {"id": "CS001"}},
                {"type": "evidence_case", "data": {"id": "EC001"}},
            ]
            loader = JSONLLoader(temp_path)
            loader.save(data)
            loaded_data = loader.load()
            assert len(loaded_data) == 2
            assert loaded_data[0]["data"]["id"] == "CS001"
            assert loaded_data[1]["data"]["id"] == "EC001"
        finally:
            Path(temp_path).unlink()


class TestGoldenDatasetLoader:
    """Test main dataset loader."""

    def test_loader_initialization(self):
        """Test loader initialization."""
        with tempfile.TemporaryDirectory() as tmpdir:
            loader = GoldenDatasetLoader(tmpdir)
            assert loader.root_path == Path(tmpdir)

    def test_load_dataset_by_version(self):
        """Test loading a specific version of dataset."""
        with tempfile.TemporaryDirectory() as tmpdir:
            base_path = Path(tmpdir)
            version_dir = base_path / "v1.0.0"
            version_dir.mkdir()
            dataset_file = version_dir / "dataset.jsonl"
            data = [{"type": "compliance_scenario", "data": {"id": "CS001"}}]
            with open(dataset_file, "w") as f:
                for item in data:
                    f.write(json.dumps(item) + "\n")
            loader = GoldenDatasetLoader(base_path)
            loaded_data = loader.load_version("1.0.0")
            assert len(loaded_data) == 1
            assert loaded_data[0]["data"]["id"] == "CS001"

    def test_parse_dataset_types(self):
        """Test parsing dataset into typed objects."""
        with tempfile.TemporaryDirectory() as tmpdir:
            base_path = Path(tmpdir)
            scenario_data = {
                "type": "compliance_scenario",
                "data": {
                    "id": "CS001",
                    "title": "Test scenario",
                    "description": "Test description",
                    "obligation_id": "OBL001",
                    "triggers": ["trigger1"],
                    "expected_outcome": {"outcome_code": "COMPLIANT", "details": {}},
                    "temporal": {"effective_from": "2024-01-01T00:00:00"},
                    "version": "1.0.0",
                    "source": {
                        "source_kind": "manual",
                        "method": "test",
                        "created_by": "test",
                        "created_at": "2024-01-01T00:00:00",
                    },
                    "created_at": "2024-01-01T00:00:00",
                },
            }
            loader = GoldenDatasetLoader(base_path)
            parsed = loader.parse_dataset([scenario_data])
            assert "compliance_scenarios" in parsed
            assert len(parsed["compliance_scenarios"]) == 1
            assert parsed["compliance_scenarios"][0].id == "CS001"


class TestDatasetRegistry:
    """Test dataset registry."""

    def test_registry_initialization(self):
        """Test registry initialization."""
        registry = DatasetRegistry()
        assert registry.datasets == {}
        assert registry.loaders == {}

    def test_register_dataset(self):
        """Test registering a dataset."""
        registry = DatasetRegistry()
        with tempfile.TemporaryDirectory() as tmpdir:
            registry.register_dataset("test_dataset", tmpdir, "1.0.0")
            assert "test_dataset" in registry.datasets
            assert registry.datasets["test_dataset"]["path"] == tmpdir
            assert registry.datasets["test_dataset"]["version"] == "1.0.0"

    def test_get_dataset(self):
        """Test getting a registered dataset."""
        registry = DatasetRegistry()
        with tempfile.TemporaryDirectory() as tmpdir:
            registry.register_dataset("test_dataset", tmpdir, "1.0.0")
            dataset_info = registry.get_dataset("test_dataset")
            assert dataset_info["path"] == tmpdir
            assert dataset_info["version"] == "1.0.0"

    def test_list_datasets(self):
        """Test listing all registered datasets."""
        registry = DatasetRegistry()
        with tempfile.TemporaryDirectory() as tmpdir1, tempfile.TemporaryDirectory() as tmpdir2:
            registry.register_dataset("dataset1", tmpdir1, "1.0.0")
            registry.register_dataset("dataset2", tmpdir2, "2.0.0")
            datasets = registry.list_datasets()
            assert len(datasets) == 2
            assert "dataset1" in datasets
            assert "dataset2" in datasets
