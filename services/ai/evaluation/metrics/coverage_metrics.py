"""Dataset coverage metrics."""

from collections import Counter
from typing import Any, Dict, List
from pydantic import BaseModel


def coverage_summary(dataset: List[BaseModel]) -> Dict[str, Any]:
    """Calculate coverage metrics by framework, jurisdiction, and trigger.

    Returns:
        Dictionary with coverage counts and percentages
    """
    if not dataset:
        return {"frameworks": {}, "jurisdictions": {}, "triggers": {}, "total_items": 0}

    frameworks = Counter()
    jurisdictions = Counter()
    triggers = Counter()

    for item in dataset:
        # Count frameworks
        if hasattr(item, "regulation_refs"):
            for ref in item.regulation_refs:
                frameworks[ref.framework] += 1

                # Infer jurisdiction from framework
                if "UK" in ref.framework:
                    jurisdictions["UK"] += 1
                elif "GDPR" in ref.framework or "EU" in ref.framework:
                    jurisdictions["EU"] += 1
                elif any(us in ref.framework for us in ["HIPAA", "SOX", "CCPA", "NIST"]):
                    jurisdictions["US"] += 1
                elif "ISO" in ref.framework or "SOC" in ref.framework:
                    jurisdictions["International"] += 1

        # Count triggers
        if hasattr(item, "triggers"):
            for trigger in item.triggers:
                triggers[trigger] += 1

    # Calculate coverage percentages
    total = len(dataset)

    return {
        "frameworks": dict(frameworks),
        "jurisdictions": dict(jurisdictions),
        "triggers": dict(triggers),
        "total_items": total,
        "framework_count": len(frameworks),
        "jurisdiction_count": len(jurisdictions),
        "trigger_count": len(triggers),
        "avg_frameworks_per_item": sum(frameworks.values()) / total if total > 0 else 0,
        "most_common_framework": frameworks.most_common(1)[0] if frameworks else None,
        "most_common_jurisdiction": (jurisdictions.most_common(1)[0] if jurisdictions else None,),
        "most_common_trigger": triggers.most_common(1)[0] if triggers else None,
    }
