"""
Production-ready LangChain/LangGraph agent system.
Provides comprehensive agent architecture with tools, memory, and observability.
"""

# Core imports that should always work
from .agent_core import ComplianceAgent, AgentConfig, AgentMetrics
from .tool_manager import ToolManager, ToolResult, ToolError

# Conditional imports for optional dependencies
try:
    from .memory_manager import MemoryManager, MemoryType, ConversationSummary

    _memory_available = True
except ImportError:
    # Mock classes for when Graphiti is not available
    class MemoryManager:
        def __init__(self, *args, **kwargs) -> None:
            raise ImportError(f"MemoryManager requires graphiti_core: {e}")

    class MemoryType:
        pass

    class ConversationSummary:
        pass

    _memory_available = False

try:
    from .rag_system import RAGSystem, DocumentChunk, RetrievalStrategy

    _rag_available = True
except ImportError:
    # Mock classes for when dependencies are missing
    class RAGSystem:
        def __init__(self, *args, **kwargs) -> None:
            raise ImportError(f"RAGSystem requires additional dependencies: {e}")

    class DocumentChunk:
        pass

    class RetrievalStrategy:
        pass

    _rag_available = False

try:
    from .observability import ObservabilityManager, AgentCallback, PerformanceMetrics

    _observability_available = True
except ImportError:
    # Mock classes for when observability dependencies are missing
    class ObservabilityManager:
        def __init__(self, *args, **kwargs) -> None:
            raise ImportError(f"ObservabilityManager requires additional dependencies: {e}")

    class AgentCallback:
        pass

    class PerformanceMetrics:
        pass

    _observability_available = False

__all__ = [
    # Core agent (always available)
    "ComplianceAgent",
    "AgentConfig",
    "AgentMetrics",
    # Tool management (always available)
    "ToolManager",
    "ToolResult",
    "ToolError",
    # Memory systems (conditional)
    "MemoryManager",
    "MemoryType",
    "ConversationSummary",
    # RAG integration (conditional)
    "RAGSystem",
    "DocumentChunk",
    "RetrievalStrategy",
    # Observability (conditional)
    "ObservabilityManager",
    "AgentCallback",
    "PerformanceMetrics",
]

# Availability flags for runtime checks
FEATURES = {
    "memory": _memory_available,
    "rag": _rag_available,
    "observability": _observability_available,
}
