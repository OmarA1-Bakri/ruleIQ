"""
Context Manager Service - Manages context storage and merging.

Handles context validation, merging strategies, and recovery.
"""

from typing import Dict, List, Optional, Any, Set
from uuid import UUID
from datetime import datetime
from dataclasses import dataclass, field
import logging
import json
from copy import deepcopy

logger = logging.getLogger(__name__)


@dataclass
class ContextNode:
    """Represents a node in the context tree."""

    key: str
    value: Any
    metadata: Dict[str, Any] = field(default_factory=dict)
    children: Dict[str, "ContextNode"] = field(default_factory=dict)
    created_at: datetime = field(default_factory=datetime.utcnow)
    updated_at: datetime = field(default_factory=datetime.utcnow)
    version: int = 1


class ContextManager:
    """Manages context storage, validation, and merging."""

    def __init__(self, max_context_size: int = 100000) -> None:
        """Initialize context manager."""
        self.max_context_size = max_context_size
        self.context_trees: Dict[UUID, ContextNode] = {}
        self.merge_strategies = {
            "overwrite": self._merge_overwrite,
            "append": self._merge_append,
            "deep": self._merge_deep,
            "smart": self._merge_smart,
        }

    def create_context(
        self, session_id: UUID, initial_data: Optional[Dict[str, Any]] = None
    ) -> ContextNode:
        """Create a new context tree."""
        root = ContextNode(
            key="root", value=initial_data or {}, metadata={"session_id": str(session_id)}
        )

        self.context_trees[session_id] = root
        logger.info(f"Created context for session {session_id}")
        return root

    def validate_context(self, context_data: Dict[str, Any]) -> tuple[bool, List[str]]:
        """Validate context data structure and content."""
        errors = []

        # Check size
        context_str = json.dumps(context_data)
        if len(context_str) > self.max_context_size:
            errors.append(f"Context too large: {len(context_str)} bytes")

        # Check for required fields
        required_fields = ["agent_id", "session_id"]
        for field in required_fields:
            if field not in context_data:
                errors.append(f"Missing required field: {field}")

        # Check for invalid data types
        if not self._validate_types(context_data, errors):
            errors.append("Invalid data types in context")

        # Check for circular references
        if self._has_circular_reference(context_data):
            errors.append("Circular reference detected in context")

        return len(errors) == 0, errors

    def _validate_types(self, data: Any, errors: List[str], path: str = "") -> bool:
        """Recursively validate data types."""
        valid = True

        if isinstance(data, dict):
            for key, value in data.items():
                current_path = f"{path}.{key}" if path else key
                if not isinstance(key, str):
                    errors.append(f"Non-string key at {current_path}")
                    valid = False
                valid = valid and self._validate_types(value, errors, current_path)

        elif isinstance(data, list):
            for i, item in enumerate(data):
                current_path = f"{path}[{i}]"
                valid = valid and self._validate_types(item, errors, current_path)

        elif not isinstance(data, (str, int, float, bool, type(None))):
            errors.append(f"Invalid type at {path}: {type(data)}")
            valid = False

        return valid

    def _has_circular_reference(self, data: Any, seen: Optional[Set[id]] = None) -> bool:
        """Check for circular references in data structure."""
        if seen is None:
            seen = set()

        if isinstance(data, (dict, list)):
            if id(data) in seen:
                return True
            seen.add(id(data))

            if isinstance(data, dict):
                for value in data.values():
                    if self._has_circular_reference(value, seen):
                        return True
            else:
                for item in data:
                    if self._has_circular_reference(item, seen):
                        return True

        return False

    def merge_context(
        self, session_id: UUID, new_data: Dict[str, Any], strategy: str = "smart"
    ) -> Dict[str, Any]:
        """Merge new data into existing context."""
        if session_id not in self.context_trees:
            self.create_context(session_id, new_data)
            return new_data

        if strategy not in self.merge_strategies:
            logger.warning(f"Unknown merge strategy: {strategy}, using 'smart'")
            strategy = "smart"

        root = self.context_trees[session_id]
        merge_func = self.merge_strategies[strategy]

        merged_value = merge_func(root.value, new_data)
        root.value = merged_value
        root.updated_at = datetime.utcnow()
        root.version += 1

        logger.info(f"Merged context for session {session_id} using {strategy} strategy")
        return merged_value

    def _merge_overwrite(self, existing: Dict[str, Any], new: Dict[str, Any]) -> Dict[str, Any]:
        """Overwrite existing with new data."""
        return new

    def _merge_append(self, existing: Dict[str, Any], new: Dict[str, Any]) -> Dict[str, Any]:
        """Append new data to existing (for list values)."""
        merged = existing.copy()

        for key, value in new.items():
            if key in merged and isinstance(merged[key], list) and isinstance(value, list):
                merged[key].extend(value)
            else:
                merged[key] = value

        return merged

    def _merge_deep(self, existing: Dict[str, Any], new: Dict[str, Any]) -> Dict[str, Any]:
        """Deep merge of nested dictionaries."""
        merged = deepcopy(existing)

        for key, value in new.items():
            if key in merged:
                if isinstance(merged[key], dict) and isinstance(value, dict):
                    merged[key] = self._merge_deep(merged[key], value)
                else:
                    merged[key] = value
            else:
                merged[key] = value

        return merged

    def _merge_smart(self, existing: Dict[str, Any], new: Dict[str, Any]) -> Dict[str, Any]:
        """Smart merge based on data types and context."""
        merged = deepcopy(existing)

        for key, value in new.items():
            if key not in merged:
                merged[key] = value
            elif key == "messages" and isinstance(merged[key], list):
                # Append messages
                if isinstance(value, list):
                    merged[key].extend(value)
                else:
                    merged[key].append(value)
            elif key == "metadata" and isinstance(merged[key], dict):
                # Deep merge metadata
                if isinstance(value, dict):
                    merged[key] = self._merge_deep(merged[key], value)
                else:
                    merged[key] = value
            elif isinstance(merged[key], dict) and isinstance(value, dict):
                # Deep merge dicts
                merged[key] = self._merge_deep(merged[key], value)
            elif isinstance(merged[key], list) and isinstance(value, list):
                # Extend lists
                merged[key].extend(value)
            else:
                # Overwrite for other types
                merged[key] = value

        return merged

    def get_context(self, session_id: UUID, path: Optional[str] = None) -> Optional[Any]:
        """Get context or specific path within context."""
        if session_id not in self.context_trees:
            return None

        root = self.context_trees[session_id]

        if not path:
            return root.value

        # Navigate path
        parts = path.split(".")
        current = root.value

        for part in parts:
            if isinstance(current, dict) and part in current:
                current = current[part]
            else:
                return None

        return current

    def set_context(self, session_id: UUID, path: str, value: Any) -> bool:
        """Set a specific value in the context."""
        if session_id not in self.context_trees:
            self.create_context(session_id)

        root = self.context_trees[session_id]
        parts = path.split(".")

        # Navigate to parent
        current = root.value
        for part in parts[:-1]:
            if part not in current:
                current[part] = {}
            current = current[part]

        # Set value
        current[parts[-1]] = value
        root.updated_at = datetime.utcnow()
        root.version += 1

        logger.info(f"Set context value at {path} for session {session_id}")
        return True

    def delete_context(self, session_id: UUID, path: Optional[str] = None) -> bool:
        """Delete context or specific path within context."""
        if session_id not in self.context_trees:
            return False

        if not path:
            # Delete entire context
            del self.context_trees[session_id]
            logger.info(f"Deleted context for session {session_id}")
            return True

        root = self.context_trees[session_id]
        parts = path.split(".")

        # Navigate to parent
        current = root.value
        for part in parts[:-1]:
            if isinstance(current, dict) and part in current:
                current = current[part]
            else:
                return False

        # Delete value
        if isinstance(current, dict) and parts[-1] in current:
            del current[parts[-1]]
            root.updated_at = datetime.utcnow()
            root.version += 1
            logger.info(f"Deleted context value at {path} for session {session_id}")
            return True

        return False

    def create_recovery_point(self, session_id: UUID) -> Dict[str, Any]:
        """Create a recovery point for context."""
        if session_id not in self.context_trees:
            return {}

        root = self.context_trees[session_id]
        recovery_point = {
            "session_id": str(session_id),
            "timestamp": datetime.utcnow().isoformat(),
            "version": root.version,
            "context": deepcopy(root.value),
            "metadata": root.metadata,
        }

        logger.info(f"Created recovery point for session {session_id}")
        return recovery_point

    def restore_from_recovery(self, session_id: UUID, recovery_point: Dict[str, Any]) -> bool:
        """Restore context from a recovery point."""
        try:
            if session_id not in self.context_trees:
                self.create_context(session_id)

            root = self.context_trees[session_id]
            root.value = deepcopy(recovery_point["context"])
            root.metadata = recovery_point.get("metadata", {})
            root.version = recovery_point.get("version", 1)
            root.updated_at = datetime.utcnow()

            logger.info(f"Restored context for session {session_id} from recovery point")
            return True

        except (KeyError, TypeError) as e:
            logger.error(f"Failed to restore from recovery point: {e}")
            return False

    def get_context_size(self, session_id: UUID) -> int:
        """Get the size of context in bytes."""
        if session_id not in self.context_trees:
            return 0

        root = self.context_trees[session_id]
        return len(json.dumps(root.value))

    def get_context_stats(self, session_id: UUID) -> Dict[str, Any]:
        """Get statistics about the context."""
        if session_id not in self.context_trees:
            return {}

        root = self.context_trees[session_id]

        def count_nodes(data: Any) -> tuple[int, int]:
            """Count nodes and depth in data structure."""
            if isinstance(data, dict):
                if not data:
                    return 1, 1
                counts = [count_nodes(v) for v in data.values()]
                nodes = sum(c[0] for c in counts) + 1
                depth = max(c[1] for c in counts) + 1
                return nodes, depth
            elif isinstance(data, list):
                if not data:
                    return 1, 1
                counts = [count_nodes(item) for item in data]
                nodes = sum(c[0] for c in counts) + 1
                depth = max(c[1] for c in counts) + 1
                return nodes, depth
            else:
                return 1, 1

        nodes, depth = count_nodes(root.value)

        return {
            "session_id": str(session_id),
            "version": root.version,
            "size_bytes": self.get_context_size(session_id),
            "node_count": nodes,
            "max_depth": depth,
            "created_at": root.created_at.isoformat(),
            "updated_at": root.updated_at.isoformat(),
        }
