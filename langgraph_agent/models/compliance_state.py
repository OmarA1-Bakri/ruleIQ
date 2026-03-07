"""

ComplianceState Pydantic model for LangGraph state management.

This model provides a strongly-typed, validated state structure for
compliance workflows, compatible with LangGraph's TypedDict requirements.
"""

from datetime import datetime
from enum import Enum
from typing import Dict, List, Optional, Any, Literal, Union
from uuid import UUID
from pydantic import BaseModel, Field, field_validator, ConfigDict


class WorkflowStatus(str, Enum):
    """Workflow status enumeration."""

    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class ActorType(str, Enum):
    """Valid actor types for compliance workflows."""

    POLICY_AUTHOR = "PolicyAuthor"
    EVIDENCE_COLLECTOR = "EvidenceCollector"
    REG_WATCH = "RegWatch"
    FILING_SCHEDULER = "FilingScheduler"


class EvidenceItem(BaseModel):
    """Evidence item structure."""

    id: str
    type: str
    content: Union[str, Dict[str, Any]]
    source: Optional[str] = None
    timestamp: Optional[datetime] = Field(default_factory=datetime.now)
    metadata: Optional[Dict[str, Any]] = Field(default_factory=dict)

    model_config = ConfigDict(json_encoders={datetime: lambda v: v.isoformat()})


class Decision(BaseModel):
    """Decision tracking structure."""

    id: str
    timestamp: datetime = Field(default_factory=datetime.now)
    actor: str
    action: str
    reasoning: Optional[str] = None
    confidence: Optional[float] = Field(None, ge=0.0, le=1.0)
    alternatives: Optional[List[str]] = Field(default_factory=list)
    metadata: Optional[Dict[str, Any]] = Field(default_factory=dict)

    model_config = ConfigDict(json_encoders={datetime: lambda v: v.isoformat()})


class CostSnapshot(BaseModel):
    """Cost tracking snapshot."""

    total_tokens: int = 0
    prompt_tokens: int = 0
    completion_tokens: int = 0
    estimated_cost: float = 0.0
    model: str = "gpt-4"
    timestamp: datetime = Field(default_factory=datetime.now)

    model_config = ConfigDict(json_encoders={datetime: lambda v: v.isoformat()})

    def accumulate(self, other: "CostSnapshot") -> "CostSnapshot":
        """Accumulate costs from another snapshot."""
        self.total_tokens += other.total_tokens
        self.prompt_tokens += other.prompt_tokens
        self.completion_tokens += other.completion_tokens
        self.estimated_cost += other.estimated_cost
        self.timestamp = datetime.now()
        return self


class MemoryStore(BaseModel):
    """Memory storage structure."""

    episodic: List[str] = Field(default_factory=list)
    semantic: Dict[str, List[str]] = Field(default_factory=dict)

    def append_episodic(self, event: str) -> None:
        """Append to episodic memory."""
        if event not in self.episodic:
            self.episodic.append(event)

    def update_semantic(self, key: str, values: List[str]) -> None:
        """Update semantic memory."""
        if key not in self.semantic:
            self.semantic[key] = []
        for value in values:
            if value not in self.semantic[key]:
                self.semantic[key].append(value)


class Context(BaseModel):
    """Workflow context structure."""

    org_profile: Optional[Dict[str, Any]] = Field(default_factory=dict)
    framework: Optional[str] = None
    obligations: Optional[List[str]] = Field(default_factory=list)
    metadata: Optional[Dict[str, Any]] = Field(default_factory=dict)

    @field_validator("framework")
    @classmethod
    def validate_framework(cls, v: Optional[str]) -> Optional[str]:
        """Validate framework against known compliance frameworks."""
        if v is None:
            return v

        # Known frameworks (can be extended)
        known_frameworks = [
            "ISO 27001",
            "ISO 27017",
            "ISO 27018",
            "ISO 27701",
            "SOC 2",
            "GDPR",
            "CCPA",
            "HIPAA",
            "PCI DSS",
            "NIST CSF",
            "CIS Controls",
            "COBIT",
        ]

        # Allow known frameworks or custom ones (log warning for unknown)
        if v not in known_frameworks:
            # In production, we might log a warning here
            pass

        return v


class ComplianceState(BaseModel):
    """
    Core state model for compliance workflows using LangGraph.

    This model provides:
    - Strong typing with Pydantic validation
    - Compatibility with LangGraph's TypedDict requirements
    - Built-in reducers for state accumulation
    - Serialization support for checkpointing
    """

    # Required fields
    case_id: str = Field(..., min_length=1, description="Unique case identifier")
    actor: Literal["PolicyAuthor", "EvidenceCollector", "RegWatch", "FilingScheduler"]
    objective: str = Field(..., min_length=1, description="Workflow objective")
    trace_id: str = Field(..., description="UUID for request tracing")

    # Optional with defaults
    context: Context = Field(default_factory=Context)
    memory: MemoryStore = Field(default_factory=MemoryStore)
    evidence: List[EvidenceItem] = Field(default_factory=list)
    decisions: List[Decision] = Field(default_factory=list)
    cost_tracker: CostSnapshot = Field(default_factory=CostSnapshot)

    # Workflow tracking
    workflow_status: WorkflowStatus = WorkflowStatus.PENDING
    node_execution_times: Dict[str, float] = Field(default_factory=dict)
    retry_count: int = Field(default=0, ge=0)
    error_count: int = Field(default=0, ge=0)

    # State history tracking
    state_history: List[Dict[str, Any]] = Field(default_factory=list)

    # Timestamps
    created_at: datetime = Field(default_factory=datetime.now)
    updated_at: Optional[datetime] = None

    model_config = ConfigDict(
        json_encoders={datetime: lambda v: v.isoformat(), UUID: lambda v: str(v)},
        validate_assignment=True,
        use_enum_values=True,
    )

    @field_validator("trace_id")
    @classmethod
    def validate_trace_id(cls, v: str) -> str:
        """Validate trace_id is a valid UUID format."""
        try:
            # Try to parse as UUID to validate format
            UUID(v)
            return v
        except ValueError:
            raise ValueError("trace_id must be a valid UUID string")

    @field_validator("case_id", "objective")
    @classmethod
    def validate_non_empty(cls, v: str) -> str:
        """Validate string fields are not empty."""
        if not v or not v.strip():
            raise ValueError("Field cannot be empty")
        return v

    @field_validator("evidence", mode="before")
    @classmethod
    def validate_evidence(cls, v: List[Any]) -> List[Any]:
        """Validate evidence items have required fields."""
        if not isinstance(v, list):
            return []

        validated = []
        for item in v:
            if isinstance(item, dict):
                # Ensure required fields
                if "id" not in item or "type" not in item:
                    raise ValueError("Evidence items must have 'id' and 'type' fields")
                if "content" not in item:
                    item["content"] = ""
                validated.append(item)
            elif isinstance(item, EvidenceItem):
                validated.append(item)
            else:
                raise ValueError(f"Invalid evidence item type: {type(item)}")

        return validated

    @field_validator("decisions", mode="before")
    @classmethod
    def validate_decisions(cls, v: List[Any]) -> List[Any]:
        """Validate decision items."""
        if not isinstance(v, list):
            return []

        validated = []
        for item in v:
            if isinstance(item, dict):
                # Ensure required fields
                if "id" not in item or "action" not in item:
                    raise ValueError("Decision items must have 'id' and 'action' fields")
                if "actor" not in item:
                    item["actor"] = "System"
                if "timestamp" not in item:
                    item["timestamp"] = datetime.now().isoformat()
                validated.append(item)
            elif isinstance(item, Decision):
                validated.append(item)
            else:
                raise ValueError(f"Invalid decision item type: {type(item)}")

        return validated

    def add_evidence(self, evidence_item: Union[EvidenceItem, Dict[str, Any]]) -> None:
        """Add evidence item with deduplication."""
        if isinstance(evidence_item, dict):
            evidence_item = EvidenceItem(**evidence_item)

        # Check for duplicates by ID
        existing_ids = {e.id for e in self.evidence}
        if evidence_item.id not in existing_ids:
            self.evidence.append(evidence_item)
            self.updated_at = datetime.now()

    def add_decision(self, decision: Union[Decision, Dict[str, Any]]) -> None:
        """Add decision to audit trail."""
        if isinstance(decision, dict):
            if "actor" not in decision:
                decision["actor"] = self.actor
            decision = Decision(**decision)

        self.decisions.append(decision)
        self.updated_at = datetime.now()

    def update_cost(self, tokens: Dict[str, int], cost: float) -> None:
        """Update cost tracking."""
        if "total_tokens" in tokens:
            self.cost_tracker.total_tokens += tokens["total_tokens"]
        if "prompt_tokens" in tokens:
            self.cost_tracker.prompt_tokens += tokens["prompt_tokens"]
        if "completion_tokens" in tokens:
            self.cost_tracker.completion_tokens += tokens["completion_tokens"]

        self.cost_tracker.estimated_cost += cost
        self.cost_tracker.timestamp = datetime.now()
        self.updated_at = datetime.now()

    def transition_status(self, new_status: Union[WorkflowStatus, str]) -> None:
        """Transition workflow status with history tracking."""
        if isinstance(new_status, str):
            new_status = WorkflowStatus(new_status)

        old_status = self.workflow_status

        # Validate transition
        valid_transitions = {
            WorkflowStatus.PENDING: [
                WorkflowStatus.IN_PROGRESS,
                WorkflowStatus.CANCELLED,
            ],
            WorkflowStatus.IN_PROGRESS: [
                WorkflowStatus.COMPLETED,
                WorkflowStatus.FAILED,
                WorkflowStatus.CANCELLED,
            ],
            WorkflowStatus.COMPLETED: [],
            WorkflowStatus.FAILED: [WorkflowStatus.PENDING],  # Can retry
            WorkflowStatus.CANCELLED: [],
        }

        if new_status not in valid_transitions.get(old_status, []) and new_status != old_status:
            raise ValueError(f"Invalid transition from {old_status} to {new_status}")

        # Track transition
        if new_status != old_status:
            self.state_history.append(
                {
                    "from": old_status.value,
                    "to": new_status.value,
                    "timestamp": datetime.now().isoformat(),
                    "actor": self.actor,
                }
            )
            self.workflow_status = new_status
            self.updated_at = datetime.now()

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for LangGraph compatibility."""
        return self.model_dump(mode="json")

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "ComplianceState":
        """Create from dictionary."""
        return cls.model_validate(data)

    def __repr__(self) -> str:
        """String representation."""
        return f"ComplianceState(case_id={self.case_id}, actor={self.actor}, status={self.workflow_status})"
