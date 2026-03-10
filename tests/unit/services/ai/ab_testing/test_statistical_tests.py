"""Unit tests for services.ai.ab_testing.statistical_tests."""

# pyright: reportPrivateUsage=false, reportMissingImports=false

import os
from datetime import datetime
from unittest.mock import patch

import numpy as np
import pytest

os.environ.setdefault("TESTING", "true")
os.environ.setdefault("ENVIRONMENT", "testing")

from services.ai.ab_testing.models import (
    ExperimentConfig,
    ExperimentData,
    ExperimentMetricType,
    ExperimentType,
    InvalidExperimentConfig,
    StatisticalResult,
    StatisticalTest,
)
from services.ai.ab_testing.statistical_tests import (
    calculate_effect_size,
    calculate_power,
    calculate_sample_size,
    compute_confidence_interval,
    execute_statistical_test,
    generate_recommendation,
    get_category_counts,
    group_data_by_variant,
    prepare_data_for_test,
    run_chi_squared,
    run_mann_whitney,
    run_t_test,
    run_welch_t_test,
    select_statistical_test,
    validate_experiment_config,
    validate_metric_value,
)


def make_config(metric_type=ExperimentMetricType.CONTINUOUS, **overrides):
    config = ExperimentConfig(
        name="exp",
        description="desc",
        experiment_type=ExperimentType.AI_MODEL_COMPARISON,
        metric_type=metric_type,
        primary_metric="score",
    )
    for key, value in overrides.items():
        setattr(config, key, value)
    return config


class TestValidationHelpers:
    def test_validate_experiment_config_accepts_valid_config(self):
        validate_experiment_config(make_config())

    @pytest.mark.parametrize(
        ("field", "value", "message"),
        [
            ("significance_level", 1.5, "Significance level"),
            ("power", 0.0, "Power"),
            ("traffic_split", {"control": 0.4, "treatment": 0.4}, "Traffic split"),
            ("min_sample_size", 5, "Minimum sample size"),
        ],
    )
    def test_validate_experiment_config_rejects_invalid_values(self, field, value, message):
        config = make_config(**{field: value})

        with pytest.raises(ValueError, match=message):
            validate_experiment_config(config)

    def test_calculate_sample_size_respects_minimum_sample_size(self):
        config = make_config(min_effect_size=10.0, min_sample_size=75)

        assert calculate_sample_size(config) == 75

    @pytest.mark.parametrize(
        ("value", "metric_type", "expected"),
        [
            ("3.5", ExperimentMetricType.CONTINUOUS, 3.5),
            (1, ExperimentMetricType.BINARY, True),
            ("yes", ExperimentMetricType.BINARY, True),
            ("8", ExperimentMetricType.COUNT, 8),
            (42, ExperimentMetricType.CATEGORICAL, "42"),
        ],
    )
    def test_validate_metric_value_coerces_types(self, value, metric_type, expected):
        assert validate_metric_value(value, metric_type) == expected

    def test_validate_metric_value_raises_for_invalid_numeric_input(self):
        with pytest.raises(InvalidExperimentConfig, match="CONTINUOUS"):
            validate_metric_value("not-a-number", ExperimentMetricType.CONTINUOUS)


class TestGroupingAndSelection:
    def test_group_data_by_variant_groups_primary_metric_values(self):
        data = [
            ExperimentData("exp", "control", "u1", None, datetime.now(), 1.0),
            ExperimentData("exp", "treatment", "u2", None, datetime.now(), 2.0),
            ExperimentData("exp", "control", "u3", None, datetime.now(), 3.0),
        ]

        assert group_data_by_variant(data) == {"control": [1.0, 3.0], "treatment": [2.0]}

    def test_select_statistical_test_returns_chi_squared_for_binary(self):
        result = select_statistical_test(
            ExperimentMetricType.BINARY,
            {"control": [True, False], "treatment": [True, True]},
        )

        assert result == StatisticalTest.CHI_SQUARED

    def test_select_statistical_test_uses_mann_whitney_for_non_normal_data(self):
        with patch("services.ai.ab_testing.statistical_tests.stats.shapiro", side_effect=[(0.0, 0.01), (0.0, 0.5)]):
            result = select_statistical_test(
                ExperimentMetricType.CONTINUOUS,
                {"control": [1.0, 2.0, 3.0], "treatment": [4.0, 5.0, 6.0]},
            )

        assert result == StatisticalTest.MANN_WHITNEY

    def test_select_statistical_test_uses_welch_for_unequal_variances(self):
        with patch("services.ai.ab_testing.statistical_tests.stats.shapiro", side_effect=[(0.0, 0.5), (0.0, 0.5)]), patch(
            "services.ai.ab_testing.statistical_tests.stats.levene", return_value=(0.0, 0.01)
        ):
            result = select_statistical_test(
                ExperimentMetricType.CONTINUOUS,
                {"control": [1.0, 2.0, 3.0], "treatment": [4.0, 5.0, 8.0]},
            )

        assert result == StatisticalTest.WELCH_T_TEST

    def test_select_statistical_test_uses_t_test_for_equal_variances(self):
        with patch("services.ai.ab_testing.statistical_tests.stats.shapiro", side_effect=[(0.0, 0.5), (0.0, 0.5)]), patch(
            "services.ai.ab_testing.statistical_tests.stats.levene", return_value=(0.0, 0.5)
        ):
            result = select_statistical_test(
                ExperimentMetricType.CONTINUOUS,
                {"control": [1.0, 2.0, 3.0], "treatment": [4.0, 5.0, 6.0]},
            )

        assert result == StatisticalTest.T_TEST

    def test_prepare_data_for_test_returns_numpy_arrays_for_numeric_tests(self):
        variants, control, treatment = prepare_data_for_test(
            {"control": [1, 2], "treatment": [3, 4]},
            StatisticalTest.T_TEST,
        )

        assert variants == ["control", "treatment"]
        assert np.array_equal(control, np.array([1.0, 2.0]))
        assert np.array_equal(treatment, np.array([3.0, 4.0]))

    def test_prepare_data_for_test_raises_for_invalid_numeric_data(self):
        with pytest.raises(InvalidExperimentConfig, match="Failed to convert"):
            prepare_data_for_test(
                {"control": ["bad"], "treatment": [1]},
                StatisticalTest.T_TEST,
            )


class TestStatisticalCalculations:
    def test_get_category_counts_returns_string_keyed_counts(self):
        assert get_category_counts(["a", "a", 1]) == {"a": 2, "1": 1}

    def test_calculate_effect_size_for_continuous_data(self):
        effect = calculate_effect_size(
            ExperimentMetricType.CONTINUOUS,
            np.array([1.0, 2.0, 3.0]),
            np.array([2.0, 3.0, 4.0]),
            StatisticalTest.T_TEST,
        )

        assert effect > 0

    def test_calculate_effect_size_for_binary_data(self):
        effect = calculate_effect_size(
            ExperimentMetricType.BINARY,
            [False, False, True],
            [True, True, True],
            StatisticalTest.CHI_SQUARED,
        )

        assert effect == pytest.approx(2 / 3)

    def test_calculate_effect_size_for_categorical_data_uses_cramers_v(self):
        effect = calculate_effect_size(
            ExperimentMetricType.CATEGORICAL,
            ["a", "a", "b", "b"],
            ["a", "b", "b", "b"],
            StatisticalTest.CHI_SQUARED,
        )

        assert 0.0 <= effect <= 1.0

    def test_calculate_effect_size_returns_zero_for_zero_variance_count_data(self):
        effect = calculate_effect_size(
            ExperimentMetricType.COUNT,
            np.array([5.0, 5.0, 5.0]),
            np.array([5.0, 5.0, 5.0]),
            StatisticalTest.MANN_WHITNEY,
        )

        assert effect == 0.0

    def test_run_test_helpers_return_named_results(self):
        control = np.array([1.0, 2.0, 3.0, 4.0])
        treatment = np.array([2.0, 3.0, 4.0, 5.0])

        t_stat, t_p, t_name = run_t_test(control, treatment)
        welch_stat, welch_p, welch_name = run_welch_t_test(control, treatment)
        mw_stat, mw_p, mw_name = run_mann_whitney(control, treatment)
        chi_stat, chi_p, chi_name = run_chi_squared([True, False, True], [True, True, False])

        assert t_name.startswith("Two-sample")
        assert welch_name.startswith("Welch")
        assert mw_name.startswith("Mann-Whitney")
        assert chi_name.startswith("Chi-squared")
        for value in [t_p, welch_p, mw_p, chi_p]:
            assert 0.0 <= value <= 1.0
        assert all(np.isfinite(v) for v in [t_stat, welch_stat, mw_stat, chi_stat])

    def test_compute_confidence_interval_returns_none_for_chi_squared(self):
        assert (
            compute_confidence_interval(
                StatisticalTest.CHI_SQUARED,
                np.array([1.0, 2.0]),
                np.array([3.0, 4.0]),
                0.05,
            )
            is None
        )

    def test_compute_confidence_interval_returns_bounds_for_t_test(self):
        interval = compute_confidence_interval(
            StatisticalTest.T_TEST,
            np.array([1.0, 2.0, 3.0, 4.0]),
            np.array([2.0, 3.0, 4.0, 5.0]),
            0.05,
        )

        assert interval is not None
        assert interval[0] < interval[1]

    def test_calculate_power_clamps_between_zero_and_one(self):
        power = calculate_power(0.5, 100, 100, 0.05)

        assert 0.0 <= power <= 1.0


class TestRecommendationsAndExecution:
    @pytest.mark.parametrize(
        ("args", "expected_prefix"),
        [
            ((True, True, 0.4, 0.01, 0.9), "IMPLEMENT"),
            ((True, True, -0.4, 0.01, 0.9), "REJECT"),
            ((True, False, 0.01, 0.01, 0.9), "INCONCLUSIVE"),
            ((False, False, 0.01, 0.3, 0.6), "INSUFFICIENT DATA"),
            ((False, False, 0.01, 0.3, 0.9), "NO EFFECT"),
        ],
    )
    def test_generate_recommendation_covers_main_branches(self, args, expected_prefix):
        assert generate_recommendation(*args).startswith(expected_prefix)

    def test_execute_statistical_test_returns_result_for_t_test(self):
        config = make_config(metric_type=ExperimentMetricType.CONTINUOUS, min_effect_size=0.1)
        variant_data = {
            "control": [1.0, 2.0, 3.0, 4.0, 5.0],
            "treatment": [3.0, 4.0, 5.0, 6.0, 7.0],
        }

        result = execute_statistical_test(StatisticalTest.T_TEST, variant_data, config, 0.95)

        assert isinstance(result, StatisticalResult)
        assert result.metadata["test_type"] == StatisticalTest.T_TEST.value
        assert result.sample_sizes == {"control": 5, "treatment": 5}
        assert set(result.means) == {"control", "treatment"}

    def test_execute_statistical_test_uses_chi_squared_defaults(self):
        config = make_config(metric_type=ExperimentMetricType.CATEGORICAL, min_effect_size=0.1)
        variant_data = {
            "control": ["a", "a", "b", "b"],
            "treatment": ["a", "b", "b", "b"],
        }

        result = execute_statistical_test(
            StatisticalTest.CHI_SQUARED,
            variant_data,
            config,
            0.95,
        )

        assert result.power == 0.8
        assert result.means == {"control": 0.0, "treatment": 0.0}
        assert result.std_devs == {"control": 0.0, "treatment": 0.0}

    def test_execute_statistical_test_rejects_unsupported_test_type(self):
        config = make_config()
        variant_data = {"control": [1.0, 2.0], "treatment": [3.0, 4.0]}

        with pytest.raises(ValueError, match="Unsupported test type"):
            execute_statistical_test(StatisticalTest.FISHER_EXACT, variant_data, config, 0.95)

    def test_execute_statistical_test_requires_two_variants(self):
        config = make_config()
        variant_data = {"only": [1.0, 2.0]}

        with pytest.raises(ValueError, match="two-variant"):
            execute_statistical_test(StatisticalTest.T_TEST, variant_data, config, 0.95)