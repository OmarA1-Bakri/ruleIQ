"""Dataset quality metrics."""

from typing import Any, Dict, List
from pydantic import BaseModel


def dataset_quality_summary(dataset: List[BaseModel]) -> Dict[str, Any]:
    """Calculate quality metrics for dataset.

    Returns:
        Dictionary with completeness, uniqueness, and overall score
    """
    if not dataset:
        return {
            "completeness": 0.0,
            "uniqueness": 0.0,
            "overall_score": 0.0,
            "total_items": 0,
        }

    # Completeness per type
    completeness_scores = []
    for item in dataset:
        score = 1.0

        # Check required fields
        if hasattr(item, "id") and not item.id:
            score *= 0.8
        if hasattr(item, "version") and not item.version:
            score *= 0.9
        if hasattr(item, "source") and not item.source:
            score *= 0.9
        if hasattr(item, "regulation_refs") and not item.regulation_refs:
            score *= 0.7

        completeness_scores.append(score)

    # ID uniqueness
    ids = [item.id for item in dataset if hasattr(item, "id")]
    uniqueness = len(set(ids)) / len(ids) if ids else 0.0

    # Overall score
    avg_completeness = sum(completeness_scores) / len(completeness_scores)
    overall_score = (avg_completeness + uniqueness) / 2

    return {
        "completeness": avg_completeness,
        "uniqueness": uniqueness,
        "overall_score": overall_score,
        "total_items": len(dataset),
        "unique_ids": len(set(ids)),
        "duplicate_ids": len(ids) - len(set(ids)),
    }
