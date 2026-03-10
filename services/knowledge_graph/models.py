"""

Data models for RegWatch Knowledge Graph
"""

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Dict, List, Any, Optional, Literal
from enum import Enum
import uuid


class NodeType(str, Enum):
    """Types of nodes in the knowledge graph"""

    REGULATION = "regulation"
    OBLIGATION = "obligation"
    CONTROL = "control"
    EVIDENCE = "evidence"
    ENTITY = "entity"
    RISK = "risk"
    AUDIT = "audit"


class RelationshipType(str, Enum):
    """Types of relationships between nodes"""

    REQUIRES = "REQUIRES"
    IMPLEMENTS = "IMPLEMENTS"
    EVIDENCES = "EVIDENCES"
    RELATES_TO = "RELATES_TO"
    DERIVED_FROM = "DERIVED_FROM"
    CONFLICTS_WITH = "CONFLICTS_WITH"
    SUPERSEDES = "SUPERSEDES"
    REFERENCES = "REFERENCES"


@dataclass
class GraphNode:
    """Represents a node in the knowledge graph"""

    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    type: NodeType = NodeType.REGULATION
    properties: Dict[str, Any] = field(default_factory=dict)
    metadata: Dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        """Initialize metadata with timestamps"""
        if "created_at" not in self.metadata:
            self.metadata["created_at"] = datetime.now(timezone.utc).isoformat()
        if "updated_at" not in self.metadata:
            self.metadata["updated_at"] = datetime.now(timezone.utc).isoformat()
        if "version" not in self.metadata:
            self.metadata["version"] = 1

    def to_dict(self) -> Dict[str, Any]:
        """Convert node to dictionary"""
        return {
            "id": self.id,
            "type": self.type.value if isinstance(self.type, NodeType) else self.type,
            "properties": self.properties,
            "metadata": self.metadata,
        }

    def update_version(self) -> None:
        """Increment version and update timestamp"""
        self.metadata["version"] += 1
        self.metadata["updated_at"] = datetime.now(timezone.utc).isoformat()


@dataclass
class GraphRelationship:
    """Represents a relationship between nodes"""

    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    type: RelationshipType = RelationshipType.RELATES_TO
    source_id: str = ""
    target_id: str = ""
    properties: Dict[str, Any] = field(default_factory=dict)
    metadata: Dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        """Initialize relationship properties"""
        if "strength" not in self.properties:
            self.properties["strength"] = 1.0
        if "confidence" not in self.properties:
            self.properties["confidence"] = 1.0
        if "evidence_count" not in self.properties:
            self.properties["evidence_count"] = 0
        if "created_at" not in self.metadata:
            self.metadata["created_at"] = datetime.now(timezone.utc).isoformat()

    def to_dict(self) -> Dict[str, Any]:
        """Convert relationship to dictionary"""
        return {
            "id": self.id,
            "type": self.type.value if isinstance(self.type, RelationshipType) else self.type,
            "source_id": self.source_id,
            "target_id": self.target_id,
            "properties": self.properties,
            "metadata": self.metadata,
        }

    def update_strength(self, delta: float) -> None:
        """Update relationship strength"""
        self.properties["strength"] = max(0, min(1, self.properties["strength"] + delta))
        self.metadata["updated_at"] = datetime.now(timezone.utc).isoformat()


@dataclass
class GraphQuery:
    """Represents a query against the knowledge graph"""

    query_type: Literal["node", "relationship", "path", "subgraph", "pattern"]
    filters: Dict[str, Any] = field(default_factory=dict)
    limit: int = 100
    offset: int = 0
    include_metadata: bool = True
    depth: int = 1

    def to_cypher(self) -> str:
        """Convert query to Cypher query language (Neo4j)"""
        return (
            f"MATCH (n) WHERE n.type = '{self.filters.get('type', '')}' RETURN n LIMIT {self.limit}"
        )


@dataclass
class GraphPath:
    """Represents a path through the graph"""

    nodes: List[GraphNode] = field(default_factory=list)
    relationships: List[GraphRelationship] = field(default_factory=list)
    total_weight: float = 0.0

    def add_step(self, node: GraphNode, relationship: Optional[GraphRelationship] = None) -> None:
        """Add a step to the path"""
        self.nodes.append(node)
        if relationship:
            self.relationships.append(relationship)
            self.total_weight += relationship.properties.get("strength", 1.0)

    def to_dict(self) -> Dict[str, Any]:
        """Convert path to dictionary"""
        return {
            "nodes": [n.to_dict() for n in self.nodes],
            "relationships": [r.to_dict() for r in self.relationships],
            "total_weight": self.total_weight,
            "length": len(self.nodes),
        }


@dataclass
class GraphSnapshot:
    """Represents a snapshot of the graph state"""

    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    timestamp: datetime = field(default_factory=datetime.utcnow)
    nodes: List[GraphNode] = field(default_factory=list)
    relationships: List[GraphRelationship] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        """Convert snapshot to dictionary"""
        return {
            "id": self.id,
            "timestamp": self.timestamp.isoformat(),
            "nodes": [node.to_dict() for node in self.nodes],
            "relationships": [relationship.to_dict() for relationship in self.relationships],
            "node_count": len(self.nodes),
            "relationship_count": len(self.relationships),
            "metadata": self.metadata,
        }
