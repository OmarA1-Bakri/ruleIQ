"""
A/B Testing Statistical Tests — Pure functions for statistical analysis.

All functions are stateless and extracted from the ABTestingFramework class
for better testability and separation of concerns.
"""

from collections import defaultdict
from typing import Any, Dict, List, Optional, Tuple, Union

import numpy as np
from scipy import stats
from scipy.stats import chi2_contingency, mannwhitneyu, ttest_ind

from config.logging_config import get_logger

from .models import (
    ExperimentConfig,
    ExperimentMetricType,
    InvalidExperimentConfig,
    StatisticalResult,
    StatisticalTest,
)

logger = get_logger(__name__)


def validate_experiment_config(config: ExperimentConfig) -> None:
    """Validate experiment configuration."""
    if config.significance_level <= 0 or config.significance_level >= 1:
        raise ValueError("Significance level must be between 0 and 1")

    if config.power <= 0 or config.power >= 1:
        raise ValueError("Power must be between 0 and 1")

    if abs(sum(config.traffic_split.values()) - 1.0) > 1e-6:
        raise ValueError("Traffic split probabilities must sum to 1.0")

    if config.min_sample_size < 10:
        raise ValueError("Minimum sample size should be at least 10")


def calculate_sample_size(config: ExperimentConfig) -> int:
    """Calculate required sample size for adequate statistical power."""
    alpha = config.significance_level
    beta = 1 - config.power
    effect_size = config.min_effect_size

    z_alpha = stats.norm.ppf(1 - alpha / 2)
    z_beta = stats.norm.ppf(1 - beta)

    n = 2 * ((z_alpha + z_beta) / effect_size) ** 2
    return max(int(np.ceil(n)), config.min_sample_size)


def validate_metric_value(
    value: Union[float, int, str, bool], metric_type: ExperimentMetricType
) -> Union[float, int, str, bool]:
    """Validate and coerce metric value to match expected type."""
    if metric_type == ExperimentMetricType.CONTINUOUS:
        try:
            return float(value)
        except (TypeError, ValueError):
            raise InvalidExperimentConfig(
                f"Cannot convert value '{value}' to float for CONTINUOUS metric"
            )
    elif metric_type == ExperimentMetricType.BINARY:
        if isinstance(value, bool):
            return value
        if isinstance(value, (int, float)):
            return bool(value)
        if isinstance(value, str):
            return value.lower() in ("true", "1", "yes")
        raise InvalidExperimentConfig(
            f"Cannot convert value '{value}' to bool for BINARY metric"
        )
    elif metric_type == ExperimentMetricType.COUNT:
        try:
            return int(value)
        except (TypeError, ValueError):
            raise InvalidExperimentConfig(
                f"Cannot convert value '{value}' to int for COUNT metric"
            )
    elif metric_type == ExperimentMetricType.CATEGORICAL:
        return str(value)
    else:
        return value


def group_data_by_variant(data: list) -> Dict[str, List[Union[float, int, str, bool]]]:
    """Group experiment data by variant."""
    variant_data: Dict[str, list] = defaultdict(list)
    for data_point in data:
        variant_data[data_point.variant].append(data_point.primary_metric_value)
    return dict(variant_data)


def select_statistical_test(
    metric_type: ExperimentMetricType, variant_data: Dict[str, List]
) -> StatisticalTest:
    """Select appropriate statistical test based on data characteristics."""
    if metric_type == ExperimentMetricType.CONTINUOUS:
        variants = list(variant_data.keys())
        if len(variants) == 2:
            control_data = np.array(variant_data[variants[0]], dtype=float)
            treatment_data = np.array(variant_data[variants[1]], dtype=float)

            if len(control_data) < 50 or len(treatment_data) < 50:
                _, p_control = stats.shapiro(control_data)
                _, p_treatment = stats.shapiro(treatment_data)
            else:
                _, p_control = stats.kstest(control_data, "norm")
                _, p_treatment = stats.kstest(treatment_data, "norm")

            if p_control < 0.05 or p_treatment < 0.05:
                return StatisticalTest.MANN_WHITNEY

            control_var = np.var(control_data)
            treatment_var = np.var(treatment_data)

            if control_var == 0 or treatment_var == 0:
                logger.info(
                    "Zero variance detected in one or both groups, using non-parametric test"
                )
                return StatisticalTest.MANN_WHITNEY

            _, p_var = stats.levene(control_data, treatment_data)

            if p_var < 0.05:
                return StatisticalTest.WELCH_T_TEST
            else:
                return StatisticalTest.T_TEST

        return StatisticalTest.T_TEST

    elif metric_type in (ExperimentMetricType.BINARY, ExperimentMetricType.CATEGORICAL):
        return StatisticalTest.CHI_SQUARED

    elif metric_type == ExperimentMetricType.COUNT:
        return StatisticalTest.MANN_WHITNEY

    return StatisticalTest.T_TEST


def prepare_data_for_test(
    variant_data: Dict[str, List], test_type: StatisticalTest
) -> Tuple:
    """Prepare data for statistical testing based on test type."""
    variants = list(variant_data.keys())

    if test_type == StatisticalTest.CHI_SQUARED:
        return variants, variant_data[variants[0]], variant_data[variants[1]]
    else:
        try:
            control_data = np.array(variant_data[variants[0]], dtype=float)
            treatment_data = np.array(variant_data[variants[1]], dtype=float)
        except (TypeError, ValueError) as e:
            raise InvalidExperimentConfig(
                f"Failed to convert data to numeric format for {test_type.value}: {e}"
            )
        return variants, control_data, treatment_data


def get_category_counts(data: List) -> Dict[str, int]:
    """Get counts for each category in categorical data."""
    counts: Dict[str, int] = defaultdict(int)
    for value in data:
        counts[str(value)] += 1
    return dict(counts)


def calculate_effect_size(
    metric_type: ExperimentMetricType,
    control_data: Any,
    treatment_data: Any,
    test_type: StatisticalTest,
) -> float:
    """Calculate effect size based on metric type."""
    if metric_type == ExperimentMetricType.CONTINUOUS:
        control_mean = np.mean(control_data)
        treatment_mean = np.mean(treatment_data)
        control_std = np.std(control_data, ddof=1)
        treatment_std = np.std(treatment_data, ddof=1)

        pooled_std = np.sqrt((control_std**2 + treatment_std**2) / 2)
        if pooled_std == 0:
            return 0.0
        return (treatment_mean - control_mean) / pooled_std

    elif metric_type == ExperimentMetricType.BINARY:
        control_prop = np.mean(control_data)
        treatment_prop = np.mean(treatment_data)
        return treatment_prop - control_prop

    elif metric_type == ExperimentMetricType.CATEGORICAL:
        if test_type == StatisticalTest.CHI_SQUARED:
            control_counts = get_category_counts(control_data)
            treatment_counts = get_category_counts(treatment_data)

            all_categories = set(control_counts.keys()) | set(treatment_counts.keys())
            contingency_table = []
            for category in all_categories:
                contingency_table.append(
                    [control_counts.get(category, 0), treatment_counts.get(category, 0)]
                )

            chi2, _, _, _ = chi2_contingency(contingency_table)
            n = len(control_data) + len(treatment_data)
            k = min(2, len(all_categories))
            cramers_v = np.sqrt(chi2 / (n * (k - 1)))
            return cramers_v
        return 0.0

    elif metric_type == ExperimentMetricType.COUNT:
        control_mean = np.mean(control_data)
        treatment_mean = np.mean(treatment_data)
        control_std = np.std(control_data, ddof=1)
        treatment_std = np.std(treatment_data, ddof=1)

        pooled_std = np.sqrt((control_std**2 + treatment_std**2) / 2)
        if pooled_std == 0:
            return 0.0
        return (treatment_mean - control_mean) / pooled_std

    return 0.0


def run_t_test(
    control_data: np.ndarray, treatment_data: np.ndarray
) -> Tuple[float, float, str]:
    """Run two-sample t-test."""
    statistic, p_value = ttest_ind(control_data, treatment_data, equal_var=True)
    return statistic, p_value, "Two-sample t-test (equal variances)"


def run_welch_t_test(
    control_data: np.ndarray, treatment_data: np.ndarray
) -> Tuple[float, float, str]:
    """Run Welch's t-test."""
    statistic, p_value = ttest_ind(control_data, treatment_data, equal_var=False)
    return statistic, p_value, "Welch's t-test (unequal variances)"


def run_mann_whitney(
    control_data: np.ndarray, treatment_data: np.ndarray
) -> Tuple[float, float, str]:
    """Run Mann-Whitney U test."""
    statistic, p_value = mannwhitneyu(control_data, treatment_data, alternative="two-sided")
    return statistic, p_value, "Mann-Whitney U test"


def run_chi_squared(
    control_data: List, treatment_data: List
) -> Tuple[float, float, str]:
    """Run chi-squared test."""
    control_counts = get_category_counts(control_data)
    treatment_counts = get_category_counts(treatment_data)

    all_categories = set(control_counts.keys()) | set(treatment_counts.keys())
    contingency_table = []
    for category in all_categories:
        contingency_table.append(
            [control_counts.get(category, 0), treatment_counts.get(category, 0)]
        )

    chi2, p_value, _, _ = chi2_contingency(contingency_table)
    return chi2, p_value, "Chi-squared test"


def compute_confidence_interval(
    test_type: StatisticalTest,
    control_data: np.ndarray,
    treatment_data: np.ndarray,
    alpha: float,
) -> Optional[Tuple[float, float]]:
    """Compute confidence interval for the test."""
    if test_type not in [StatisticalTest.T_TEST, StatisticalTest.WELCH_T_TEST]:
        return None

    control_mean = np.mean(control_data)
    treatment_mean = np.mean(treatment_data)
    control_std = np.std(control_data, ddof=1)
    treatment_std = np.std(treatment_data, ddof=1)

    mean_diff = treatment_mean - control_mean
    pooled_se = np.sqrt(
        control_std**2 / len(control_data) + treatment_std**2 / len(treatment_data)
    )

    if test_type == StatisticalTest.T_TEST:
        df = len(control_data) + len(treatment_data) - 2
    else:
        numerator = (
            control_std**2 / len(control_data) + treatment_std**2 / len(treatment_data)
        ) ** 2
        denominator = control_std**4 / (
            len(control_data) ** 2 * (len(control_data) - 1)
        ) + treatment_std**4 / (len(treatment_data) ** 2 * (len(treatment_data) - 1))

        if denominator == 0 or not np.isfinite(numerator / denominator):
            logger.warning("Welch df calculation unstable, using conservative df")
            df = min(len(control_data) - 1, len(treatment_data) - 1)
        else:
            df = numerator / denominator
            if df <= 0 or not np.isfinite(df):
                logger.warning("Invalid df calculated, using conservative estimate")
                df = min(len(control_data) - 1, len(treatment_data) - 1)

    t_critical = stats.t.ppf(1 - alpha / 2, df)
    margin_error = t_critical * pooled_se
    return (mean_diff - margin_error, mean_diff + margin_error)


def calculate_power(effect_size: float, n1: int, n2: int, alpha: float) -> float:
    """Calculate statistical power for the test."""
    pooled_n = 2 / (1 / n1 + 1 / n2)
    ncp = effect_size * np.sqrt(pooled_n / 2)

    t_critical = stats.t.ppf(1 - alpha / 2, n1 + n2 - 2)

    power = 1 - stats.nct.cdf(t_critical, n1 + n2 - 2, ncp) + stats.nct.cdf(
        -t_critical, n1 + n2 - 2, ncp
    )

    return max(0.0, min(1.0, power))


def generate_recommendation(
    is_significant: bool,
    practical_significance: bool,
    effect_size: float,
    p_value: float,
    power: float,
) -> str:
    """Generate actionable recommendation based on statistical results."""
    if is_significant and practical_significance:
        if effect_size > 0:
            return (
                f"IMPLEMENT: Treatment shows significant improvement "
                f"(p={p_value:.4f}, effect size={effect_size:.3f})"
            )
        else:
            return (
                f"REJECT: Treatment shows significant degradation "
                f"(p={p_value:.4f}, effect size={effect_size:.3f})"
            )

    if is_significant:
        return f"INCONCLUSIVE: Statistically significant but effect too small (effect size={effect_size:.3f})"

    if power < 0.8:
        return f"INSUFFICIENT DATA: Low power ({power:.2f}). Collect more data or increase effect size."

    return f"NO EFFECT: Well-powered test shows no significant difference (power={power:.2f})"


def execute_statistical_test(
    test_type: StatisticalTest,
    variant_data: Dict[str, List],
    config: ExperimentConfig,
    confidence_level: float,
) -> StatisticalResult:
    """Orchestrate statistical test execution.

    Args:
        test_type: Type of statistical test to perform
        variant_data: Data grouped by variant
        config: Experiment configuration
        confidence_level: Confidence level for the test

    Returns:
        Statistical test results
    """
    alpha = 1 - confidence_level
    variants_list = list(variant_data.keys())

    if len(variants_list) != 2:
        raise ValueError("Currently only supports two-variant experiments")

    variants, control_data, treatment_data = prepare_data_for_test(variant_data, test_type)

    if test_type == StatisticalTest.T_TEST:
        statistic, p_value, test_name = run_t_test(control_data, treatment_data)
    elif test_type == StatisticalTest.WELCH_T_TEST:
        statistic, p_value, test_name = run_welch_t_test(control_data, treatment_data)
    elif test_type == StatisticalTest.MANN_WHITNEY:
        statistic, p_value, test_name = run_mann_whitney(control_data, treatment_data)
    elif test_type == StatisticalTest.CHI_SQUARED:
        statistic, p_value, test_name = run_chi_squared(control_data, treatment_data)
    else:
        raise ValueError(f"Unsupported test type: {test_type}")

    effect_size_val = calculate_effect_size(
        config.metric_type, control_data, treatment_data, test_type
    )

    confidence_interval = compute_confidence_interval(
        test_type, control_data, treatment_data, alpha
    )

    if test_type != StatisticalTest.CHI_SQUARED:
        observed_effect_size = abs(effect_size_val)
        power = calculate_power(observed_effect_size, len(control_data), len(treatment_data), alpha)
    else:
        power = 0.8

    is_significant = p_value < alpha
    practical_significance = abs(effect_size_val) >= config.min_effect_size

    recommendation = generate_recommendation(
        is_significant, practical_significance, effect_size_val, p_value, power
    )

    if test_type != StatisticalTest.CHI_SQUARED:
        control_mean = np.mean(control_data)
        treatment_mean = np.mean(treatment_data)
        control_std = np.std(control_data, ddof=1)
        treatment_std = np.std(treatment_data, ddof=1)
    else:
        control_mean = 0.0
        treatment_mean = 0.0
        control_std = 0.0
        treatment_std = 0.0

    return StatisticalResult(
        test_name=test_name,
        statistic=statistic,
        p_value=p_value,
        confidence_interval=confidence_interval,
        effect_size=effect_size_val,
        power=power,
        is_significant=is_significant,
        practical_significance=practical_significance,
        recommendation=recommendation,
        sample_sizes={
            variants[0]: len(control_data),
            variants[1]: len(treatment_data),
        },
        means={variants[0]: control_mean, variants[1]: treatment_mean},
        std_devs={variants[0]: control_std, variants[1]: treatment_std},
        metadata={
            "confidence_level": confidence_level,
            "alpha": alpha,
            "test_type": test_type.value,
        },
    )
