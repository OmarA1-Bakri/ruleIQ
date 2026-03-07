"""
import requests

Reducer functions for LangGraph state management.

These reducers are used with Annotated types to provide intelligent
state accumulation and merging logic.
"""

from typing import Dict, List, Any, Union
from datetime import datetime
import copy


def accumulate_evidence(
    existing: List[Dict[str, Any]], new: List[Dict[str, Any]]
) -> List[Dict[str, Any]]:
    """
    Accumulate evidence items without duplication.

    Args:
        existing: Current evidence list
        new: New evidence to add

    Returns:
        Combined evidence list with deduplication by ID
    """
    if not existing:
        return new if new else []

    if not new:
        return existing

    # Create a dict keyed by ID for deduplication
    evidence_dict = {}

    # Add existing evidence
    for item in existing:
        if isinstance(item, dict) and "id" in item:
            evidence_dict[item["id"]] = item

    # Add/update with new evidence
    for item in new:
        if isinstance(item, dict) and "id" in item:
            evidence_dict[item["id"]] = item

    # Return as list maintaining order
    return list(evidence_dict.values())


def merge_decisions(
    existing: List[Dict[str, Any]], new: List[Dict[str, Any]]
) -> List[Dict[str, Any]]:
    """
    Merge decision lists maintaining chronological order.

    Args:
        existing: Current decisions
        new: New decisions to add

    Returns:
        Combined decision list in chronological order
    """
    if not existing:
        return new if new else []

    if not new:
        return existing

    # Combine all decisions
    all_decisions = existing + new

    # Remove duplicates by ID while preserving order
    seen_ids = set()
    unique_decisions = []

    for decision in all_decisions:
        if isinstance(decision, dict) and "id" in decision:
            if decision["id"] not in seen_ids:
                seen_ids.add(decision["id"])
                unique_decisions.append(decision)

    # Sort by timestamp if available
    try:
        sorted_decisions = sorted(
            unique_decisions, key=lambda d: d.get("timestamp", ""), reverse=False
        )
        return sorted_decisions
    except requests.RequestException:
        # If sorting fails, return as-is
        return unique_decisions


def update_cost_tracker(
    existing: Union[Dict[str, Any], Any], new: Union[Dict[str, Any], Any]
) -> Union[Dict[str, Any], Any]:
    """
    Update cost tracking by accumulating values.

    Args:
        existing: Current cost snapshot (dict or CostSnapshot)
        new: New costs to add (dict or CostSnapshot)

    Returns:
        Updated cost snapshot with accumulated values
    """
    from langgraph_agent.models.compliance_state import CostSnapshot

    # Convert CostSnapshot objects to dicts if needed
    if isinstance(existing, CostSnapshot):
        existing = existing.model_dump()
    if isinstance(new, CostSnapshot):
        new = new.model_dump()

    if not existing:
        return (
            new
            if new
            else {
                "total_tokens": 0,
                "prompt_tokens": 0,
                "completion_tokens": 0,
                "estimated_cost": 0.0,
                "model": "gpt-4",
                "timestamp": datetime.now().isoformat(),
            }
        )

    if not new:
        return existing

    # Create a copy to avoid mutation
    result = copy.deepcopy(existing)

    # Accumulate token counts
    if "total_tokens" in new:
        result["total_tokens"] = result.get("total_tokens", 0) + new["total_tokens"]

    if "prompt_tokens" in new:
        result["prompt_tokens"] = result.get("prompt_tokens", 0) + new["prompt_tokens"]

    if "completion_tokens" in new:
        result["completion_tokens"] = result.get("completion_tokens", 0) + new["completion_tokens"]

    if "estimated_cost" in new:
        result["estimated_cost"] = result.get("estimated_cost", 0.0) + new["estimated_cost"]

    # Update model if provided
    if "model" in new:
        result["model"] = new["model"]

    # Update timestamp
    result["timestamp"] = datetime.now().isoformat()

    # Return as CostSnapshot object if we're dealing with CostSnapshot inputs
    # Check if we had CostSnapshot input by looking for the import
    try:
        return CostSnapshot(**result)
    except (ValueError, TypeError):
        return result


def append_to_memory(existing: Dict[str, Any], new: Dict[str, Any]) -> Dict[str, Any]:
    """
    Append to memory store (episodic and semantic).

    Args:
        existing: Current memory store
        new: New memory items to add

    Returns:
        Updated memory store with appended items
    """
    if not existing:
        existing = {"episodic": [], "semantic": {}}

    if not new:
        return existing

    # Create a copy to avoid mutation
    result = copy.deepcopy(existing)

    # Ensure structure exists
    if "episodic" not in result:
        result["episodic"] = []
    if "semantic" not in result:
        result["semantic"] = {}

    # Append episodic memories
    if "episodic" in new and isinstance(new["episodic"], list):
        for item in new["episodic"]:
            if item not in result["episodic"]:
                result["episodic"].append(item)

    # Merge semantic memories
    if "semantic" in new and isinstance(new["semantic"], dict):
        for key, values in new["semantic"].items():
            if key not in result["semantic"]:
                result["semantic"][key] = []

            if isinstance(values, list):
                for value in values:
                    if value not in result["semantic"][key]:
                        result["semantic"][key].append(value)
            elif values not in result["semantic"][key]:
                result["semantic"][key].append(values)

    return result


def merge_node_execution_times(
    existing: Dict[str, float], new: Dict[str, float]
) -> Dict[str, float]:
    """
    Merge node execution times, keeping the latest values.

    Args:
        existing: Current execution times
        new: New execution times to merge

    Returns:
        Merged execution times
    """
    if not existing:
        return new if new else {}

    if not new:
        return existing

    # Merge, with new values overwriting existing
    result = copy.deepcopy(existing)
    result.update(new)

    return result


def increment_counter(existing: int, new: int) -> int:
    """
    Increment counter reducer.

    Args:
        existing: Current counter value
        new: Value to add

    Returns:
        Incremented counter
    """
    if existing is None:
        existing = 0
    if new is None:
        new = 0

    return existing + new


def accumulate_errors(
    existing: List[Dict[str, Any]],
    new: Union[List[Dict[str, Any]], Dict[str, Any]],
    max_errors: int = 10,
) -> List[Dict[str, Any]]:
    """
    Accumulate errors with a maximum limit.

    Args:
        existing: Current error list
        new: New error(s) to add
        max_errors: Maximum errors to keep

    Returns:
        Combined error list with limit applied
    """
    if not existing:
        existing = []

    if not new:
        return existing

    # Normalize new to list
    if isinstance(new, dict):
        new = [new]
    elif not isinstance(new, list):
        return existing

    # Combine and limit
    combined = existing + new

    # Keep only the most recent errors
    if len(combined) > max_errors:
        combined = combined[-max_errors:]

    return combined


def update_metadata(existing: Dict[str, Any], new: Dict[str, Any]) -> Dict[str, Any]:
    """
    Update metadata with intelligent merging.

    Args:
        existing: Current metadata
        new: New metadata to merge

    Returns:
        Merged metadata with versioning
    """
    if not existing:
        result = new if new else {}
        result["version"] = 1
        result["updated_at"] = datetime.now().isoformat()
        return result

    if not new:
        return existing

    # Deep copy to avoid mutation
    result = copy.deepcopy(existing)

    # Increment version
    result["version"] = result.get("version", 1) + 1

    # Merge new metadata
    for key, value in new.items():
        if key == "version":
            continue  # Don't overwrite version

        if key in result and isinstance(result[key], dict) and isinstance(value, dict):
            # Recursive merge for nested dicts
            result[key] = update_metadata(result[key], value)
        else:
            # Direct update
            result[key] = value

    # Update timestamp
    result["updated_at"] = datetime.now().isoformat()

    return result


def merge_context(existing: Dict[str, Any], new: Dict[str, Any]) -> Dict[str, Any]:
    """
    Merge context dictionaries intelligently.

    Args:
        existing: Current context
        new: New context to merge

    Returns:
        Merged context
    """
    if not existing:
        return new if new else {}

    if not new:
        return existing

    result = copy.deepcopy(existing)

    # Handle org_profile
    if "org_profile" in new:
        if "org_profile" not in result:
            result["org_profile"] = {}
        result["org_profile"].update(new["org_profile"])

    # Update framework (latest wins)
    if "framework" in new:
        result["framework"] = new["framework"]

    # Merge obligations (accumulate unique)
    if "obligations" in new:
        if "obligations" not in result:
            result["obligations"] = []

        existing_obligations = set(result["obligations"])
        for obligation in new["obligations"]:
            if obligation not in existing_obligations:
                result["obligations"].append(obligation)

    # Merge metadata
    if "metadata" in new:
        if "metadata" not in result:
            result["metadata"] = {}
        result["metadata"] = update_metadata(result["metadata"], new["metadata"])

    return result


# Export all reducers
__all__ = [
    "accumulate_evidence",
    "merge_decisions",
    "update_cost_tracker",
    "append_to_memory",
    "merge_node_execution_times",
    "increment_counter",
    "accumulate_errors",
    "update_metadata",
    "merge_context",
]
