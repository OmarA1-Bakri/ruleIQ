"""Unit tests for A/B testing factory and storage helpers."""

from datetime import datetime

from services.ai.ab_testing.factory import (
    create_ai_model_experiment,
    create_prompt_optimization_experiment,
    get_ab_testing_framework,
)
from services.ai.ab_testing.models import (
    ExperimentConfig,
    ExperimentData,
    ExperimentMetricType,
    ExperimentType,
)
from services.ai.ab_testing.storage import InMemoryStorageBackend


class DummyFramework:
    def __init__(self) -> None:
        self.created_configs: list[ExperimentConfig] = []

    def create_experiment(self, config: ExperimentConfig) -> dict[str, str]:
        self.created_configs.append(config)
        return {"experiment_id": "exp-123", "name": config.name}


class TestFactoryHelpers:
    def test_get_ab_testing_framework_returns_singleton(self):
        import services.ai.ab_testing.factory as factory_module

        factory_module._ab_testing_framework = None
        first = get_ab_testing_framework()
        second = get_ab_testing_framework()

        assert first is second

    def test_create_ai_model_experiment_builds_expected_config(self, monkeypatch):
        framework = DummyFramework()
        monkeypatch.setattr(
            "services.ai.ab_testing.factory.get_ab_testing_framework",
            lambda: framework,
        )

        result = create_ai_model_experiment("gemini-pro", "gpt-4o", min_effect_size=0.2)

        assert result == {"experiment_id": "exp-123", "name": "AI Model Comparison: gemini-pro vs gpt-4o"}
        config = framework.created_configs[0]
        assert config.experiment_type is ExperimentType.AI_MODEL_COMPARISON
        assert config.metric_type is ExperimentMetricType.CONTINUOUS
        assert config.primary_metric == "response_quality"
        assert config.min_effect_size == 0.2
        assert config.traffic_split == {"control": 0.5, "treatment": 0.5}
        assert config.tags == ["ai_model", "performance", "gemini-pro", "gpt-4o"]

    def test_create_prompt_optimization_experiment_builds_expected_config(self, monkeypatch):
        framework = DummyFramework()
        monkeypatch.setattr(
            "services.ai.ab_testing.factory.get_ab_testing_framework",
            lambda: framework,
        )

        result = create_prompt_optimization_experiment("old", "new", metric="completion_rate")

        assert result == {"experiment_id": "exp-123", "name": "Prompt Optimization Experiment"}
        config = framework.created_configs[0]
        assert config.experiment_type is ExperimentType.PROMPT_OPTIMIZATION
        assert config.metric_type is ExperimentMetricType.BINARY
        assert config.primary_metric == "completion_rate"
        assert config.secondary_metrics == ["user_satisfaction", "response_relevance"]
        assert config.min_sample_size == 500
        assert config.tags == ["prompt", "optimization", "completion_rate"]


class TestInMemoryStorageBackend:
    def test_append_initializes_storage_and_count_tracks_items(self):
        backend = InMemoryStorageBackend()
        data = ExperimentData(
            experiment_id="exp-1",
            variant="control",
            user_id="user-1",
            session_id="session-1",
            timestamp=datetime(2025, 1, 1, 12, 0, 0),
            primary_metric_value=1.0,
        )

        backend.append("exp-1", data)

        assert backend.count("exp-1") == 1
        assert backend.query("exp-1") == [data]

    def test_query_returns_empty_list_for_unknown_experiment(self):
        backend = InMemoryStorageBackend()

        assert backend.query("missing") == []
        assert backend.count("missing") == 0

    def test_query_ignores_filters_and_returns_all_data(self):
        backend = InMemoryStorageBackend()
        first = ExperimentData(
            experiment_id="exp-2",
            variant="control",
            user_id="user-1",
            session_id=None,
            timestamp=datetime(2025, 1, 1, 12, 0, 0),
            primary_metric_value=True,
        )
        second = ExperimentData(
            experiment_id="exp-2",
            variant="treatment",
            user_id="user-2",
            session_id=None,
            timestamp=datetime(2025, 1, 1, 13, 0, 0),
            primary_metric_value=False,
        )

        backend.append("exp-2", first)
        backend.append("exp-2", second)

        assert backend.query("exp-2", filters={"variant": "control"}) == [first, second]
        assert backend.count("exp-2") == 2
