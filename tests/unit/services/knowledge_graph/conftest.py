"""Conftest for knowledge_graph tests — mock missing submodules before import."""

import sys
from unittest.mock import MagicMock

# The knowledge_graph __init__.py imports from modules that don't exist on disk.
# Mock them so importing services.knowledge_graph.models succeeds.
for mod_name in [
    "services.knowledge_graph.graph_manager",
    "services.knowledge_graph.obligation_mapper",
    "services.knowledge_graph.evidence_linker",
    "services.knowledge_graph.memory_integration",
]:
    if mod_name not in sys.modules:
        sys.modules[mod_name] = MagicMock()
