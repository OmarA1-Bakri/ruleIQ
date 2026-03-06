"""CLI for golden dataset validation and reporting."""

import logging
import argparse

# Constants
MAX_DISPLAYED_ERRORS = 5

logger = logging.getLogger(__name__)
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict
from ..schemas import ComplianceScenario, EvidenceCase, RegulatoryQAPair
from .loaders import load_jsonl
from .versioning import is_semver
from .validators import DeepValidator, ExternalDataValidator
from ..metrics import dataset_quality_summary, coverage_summary
import sys


def validate_and_report(root: Path, version: str, outdir: Path) -> None:
    """Validate golden datasets and generate reports.

    Args:
        root: Root directory for golden datasets
        version: Dataset version to validate
        outdir: Output directory for reports
    """
    clean_version = version.lstrip("v")
    if not is_semver(clean_version):
        raise ValueError(f"Invalid semantic version: {version}")
    outdir.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    datasets = {"compliance_scenarios": [], "evidence_cases": [], "regulatory_qa": []}
    errors = []
    scenario_path = root / "compliance_scenarios" / f"v{clean_version}" / "dataset.jsonl"
    if scenario_path.exists():
        try:
            datasets["compliance_scenarios"] = list(load_jsonl(scenario_path, ComplianceScenario))
        except Exception as e:
            errors.append(f"Failed to load compliance scenarios: {e}")
    else:
        errors.append(f"Compliance scenarios not found: {scenario_path}")
    evidence_path = root / "evidence_cases" / f"v{clean_version}" / "dataset.jsonl"
    if evidence_path.exists():
        try:
            datasets["evidence_cases"] = list(load_jsonl(evidence_path, EvidenceCase))
        except Exception as e:
            errors.append(f"Failed to load evidence cases: {e}")
    else:
        errors.append(f"Evidence cases not found: {evidence_path}")
    qa_path = root / "regulatory_qa" / f"v{clean_version}" / "dataset.jsonl"
    if qa_path.exists():
        try:
            datasets["regulatory_qa"] = list(load_jsonl(qa_path, RegulatoryQAPair))
        except Exception as e:
            errors.append(f"Failed to load regulatory Q&A: {e}")
    else:
        errors.append(f"Regulatory Q&A not found: {qa_path}")
    deep_validator = DeepValidator()
    external_validator = ExternalDataValidator()
    validation_results = {}
    quality_metrics = {}
    coverage_metrics = {}
    trust_scores = {}
    for dataset_type, data in datasets.items():
        if data:
            validation_results[dataset_type] = deep_validator.validate(data)
            quality_metrics[dataset_type] = dataset_quality_summary(data)
            coverage_metrics[dataset_type] = coverage_summary(data)
            if data and hasattr(data[0], "source"):
                source_meta = {
                    "domain": data[0].source.domain,
                    "fetched_at": data[0].source.fetched_at,
                }
                trust_scores[dataset_type] = external_validator.score_trustworthiness(
                    data, source_meta
                )
    report = {
        "metadata": {
            "version": clean_version,
            "timestamp": timestamp,
            "root_path": str(root),
            "total_items": sum(len(d) for d in datasets.values()),
        },
        "datasets": {
            "compliance_scenarios": len(datasets["compliance_scenarios"]),
            "evidence_cases": len(datasets["evidence_cases"]),
            "regulatory_qa": len(datasets["regulatory_qa"]),
        },
        "validation": validation_results,
        "quality_metrics": quality_metrics,
        "coverage_metrics": coverage_metrics,
        "trust_scores": trust_scores,
        "errors": errors,
    }
    json_path = outdir / f"golden_report_{timestamp}.json"
    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(report, f, indent=2, default=str)
    md_path = outdir / f"golden_report_{timestamp}.md"
    write_markdown_report(md_path, report)
    logger.info("Reports generated:")
    logger.info("  JSON: %s" % json_path)
    logger.info("  Markdown: %s" % md_path)
    logger.info("\nSummary:")
    logger.info("  Total items: %s" % report["metadata"]["total_items"])
    logger.error(
        "  Validation: %s"
        % (
            "PASSED"
            if all(v.get("overall_valid", False) for v in validation_results.values())
            else "FAILED"
        )
    )
    if errors:
        logger.info("\nErrors encountered:")
        for error in errors:
            logger.info("  - %s" % error)


def write_markdown_report(path: Path, report: Dict[str, Any]) -> None:
    """Write markdown format report."""
    lines = []
    lines.append("# Golden Dataset Validation Report")
    lines.append(f"\nGenerated: {report['metadata']['timestamp']}")
    lines.append(f"Version: {report['metadata']['version']}")
    lines.append("")
    lines.append("## Dataset Summary")
    lines.append("")
    for dataset_type, count in report["datasets"].items():
        lines.append(f"- **{dataset_type.replace('_', ' ').title()}**: {count} items")
    lines.append(f"- **Total**: {report['metadata']['total_items']} items")
    lines.append("")
    lines.append("## Validation Results")
    lines.append("")
    for dataset_type, validation in report["validation"].items():
        lines.append(f"### {dataset_type.replace('_', ' ').title()}")
        lines.append("")
        if validation.get("overall_valid"):
            lines.append("✅ **PASSED**")
        else:
            lines.append("❌ **FAILED**")
        for layer in ["semantic", "cross_ref", "regulatory", "temporal"]:
            if layer in validation:
                status = "✓" if validation[layer]["valid"] else "✗"
                lines.append(f"- {layer.replace('_', ' ').title()}: {status}")
                if validation[layer].get("errors"):
                    for error in validation[layer]["errors"][:MAX_DISPLAYED_ERRORS]:
                        lines.append(f"  - {error}")
                    if len(validation[layer]["errors"]) > MAX_DISPLAYED_ERRORS:
                        lines.append(
                            f"  - ... and {len(validation[layer]['errors']) - MAX_DISPLAYED_ERRORS} more"
                        )
        lines.append("")
    lines.append("## Quality Metrics")
    lines.append("")
    for dataset_type, metrics in report["quality_metrics"].items():
        lines.append(f"### {dataset_type.replace('_', ' ').title()}")
        lines.append(f"- Completeness: {metrics['completeness']:.2%}")
        lines.append(f"- Uniqueness: {metrics['uniqueness']:.2%}")
        lines.append(f"- Overall Score: {metrics['overall_score']:.2%}")
        lines.append("")
    lines.append("## Coverage Analysis")
    lines.append("")
    for dataset_type, metrics in report["coverage_metrics"].items():
        lines.append(f"### {dataset_type.replace('_', ' ').title()}")
        lines.append(f"- Frameworks covered: {metrics.get('framework_count', 0)}")
        lines.append(f"- Jurisdictions covered: {metrics.get('jurisdiction_count', 0)}")
        if metrics.get("most_common_framework"):
            lines.append(
                f"- Most common framework: {metrics['most_common_framework'][0]} ({metrics['most_common_framework'][1]} items)"
            )
        lines.append("")
    if report["trust_scores"]:
        lines.append("## Trust Scores")
        lines.append("")
        for dataset_type, scores in report["trust_scores"].items():
            lines.append(f"### {dataset_type.replace('_', ' ').title()}")
            lines.append(f"- Overall Trust: {scores.get('overall', 0):.2%}")
            for key in ["source_reputation", "data_freshness", "regulatory_alignment"]:
                if key in scores:
                    lines.append(f"- {key.replace('_', ' ').title()}: {scores[key]:.2%}")
            lines.append("")
    if report["errors"]:
        lines.append("## Errors")
        lines.append("")
        for error in report["errors"]:
            lines.append(f"- {error}")
        lines.append("")
    with open(path, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))


def main() -> None:
    """CLI entry point."""
    parser = argparse.ArgumentParser(description="Validate golden datasets and generate reports")
    parser.add_argument(
        "--root",
        type=Path,
        default=Path("data/golden_datasets"),
        help="Root directory for golden datasets",
    )
    parser.add_argument(
        "--version", type=str, required=True, help="Dataset version (e.g., 0.1.0 or v0.1.0)"
    )
    parser.add_argument(
        "--outdir", type=Path, default=Path("artifacts"), help="Output directory for reports"
    )
    args = parser.parse_args()
    try:
        validate_and_report(args.root, args.version, args.outdir)
    except Exception as e:
        logger.info("Error: %s" % e)
        sys.exit(1)


if __name__ == "__main__":
    main()
