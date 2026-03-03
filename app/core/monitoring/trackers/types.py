"""
Shared enums and dataclasses for LangGraph metrics tracking.
"""

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional


class NodeStatus(Enum):
    """Status of node execution."""
    STARTED = 'started'
    SUCCESS = 'success'
    FAILED = 'failed'
    TIMEOUT = 'timeout'
    SKIPPED = 'skipped'
    RETRYING = 'retrying'
    CANCELLED = 'cancelled'


class WorkflowStatus(Enum):
    """Status of workflow execution."""
    STARTED = 'started'
    COMPLETED = 'completed'
    FAILED = 'failed'
    CANCELLED = 'cancelled'
    TIMEOUT = 'timeout'


@dataclass
class NodeExecution:
    """Data class for node execution details."""
    node_name: str
    start_time: float
    end_time: Optional[float] = None
    status: NodeStatus = NodeStatus.STARTED
    error: Optional[str] = None
    retry_count: int = 0
    metadata: Dict[str, Any] = field(default_factory=dict)
    timeout_seconds: Optional[float] = None


@dataclass
class WorkflowExecution:
    """Data class for workflow execution details."""
    workflow_id: str
    workflow_type: str
    start_time: float
    end_time: Optional[float] = None
    status: WorkflowStatus = WorkflowStatus.STARTED
    nodes: List[NodeExecution] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)
