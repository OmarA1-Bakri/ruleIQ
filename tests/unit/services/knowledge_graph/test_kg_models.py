"""Tests for services/knowledge_graph/models.py - Knowledge graph data models."""

from datetime import datetime
from services.knowledge_graph.models import (
    NodeType,
    RelationshipType,
    GraphNode,
    GraphRelationship,
    GraphQuery,
    GraphPath,
    GraphSnapshot,
)


# --- Enums ---
class TestNodeType:
    def test_all_values(self):
        expected = {"REGULATION", "OBLIGATION", "CONTROL", "EVIDENCE", "ENTITY", "RISK", "AUDIT"}
        assert {nt.name for nt in NodeType} == expected


class TestRelationshipType:
    def test_all_values(self):
        expected = {
            "REQUIRES",
            "IMPLEMENTS",
            "EVIDENCES",
            "RELATES_TO",
            "DERIVED_FROM",
            "CONFLICTS_WITH",
            "SUPERSEDES",
            "REFERENCES",
        }
        assert {rt.name for rt in RelationshipType} == expected


# --- GraphNode ---
class TestGraphNode:
    def test_default_creation(self):
        node = GraphNode()
        assert node.type == NodeType.REGULATION
        assert isinstance(node.id, str)
        assert len(node.id) > 0
        assert isinstance(node.properties, dict)

    def test_metadata_initialized(self):
        node = GraphNode()
        assert "created_at" in node.metadata
        assert "updated_at" in node.metadata
        assert node.metadata.get("version") == 1

    def test_custom_type(self):
        node = GraphNode(type=NodeType.CONTROL)
        assert node.type == NodeType.CONTROL

    def test_custom_properties(self):
        node = GraphNode(properties={"name": "GDPR"})
        assert node.properties["name"] == "GDPR"

    def test_to_dict(self):
        node = GraphNode(type=NodeType.EVIDENCE)
        d = node.to_dict()
        assert "id" in d
        assert "type" in d
        assert "properties" in d
        assert "metadata" in d

    def test_update_version(self):
        node = GraphNode()
        original_version = node.metadata.get("version", 1)
        node.update_version()
        assert node.metadata["version"] == original_version + 1
        assert "updated_at" in node.metadata


# --- GraphRelationship ---
class TestGraphRelationship:
    def test_default_creation(self):
        rel = GraphRelationship()
        assert rel.type == RelationshipType.RELATES_TO
        assert rel.source_id == ""
        assert rel.target_id == ""
        assert isinstance(rel.id, str)

    def test_default_properties(self):
        rel = GraphRelationship()
        assert rel.properties.get("strength") == 1.0
        assert rel.properties.get("confidence") == 1.0
        assert rel.properties.get("evidence_count") == 0

    def test_custom_source_target(self):
        rel = GraphRelationship(
            type=RelationshipType.REQUIRES,
            source_id="node_a",
            target_id="node_b",
        )
        assert rel.source_id == "node_a"
        assert rel.target_id == "node_b"
        assert rel.type == RelationshipType.REQUIRES

    def test_to_dict(self):
        rel = GraphRelationship(source_id="a", target_id="b")
        d = rel.to_dict()
        assert d["source_id"] == "a"
        assert d["target_id"] == "b"
        assert "type" in d

    def test_update_strength(self):
        rel = GraphRelationship()
        initial = rel.properties.get("strength", 1.0)
        rel.update_strength(0.5)
        assert rel.properties["strength"] == min(1.0, initial + 0.5)


# --- GraphQuery ---
class TestGraphQuery:
    def test_node_query(self):
        q = GraphQuery(query_type="node")
        assert q.query_type == "node"
        assert q.limit == 100
        assert q.offset == 0
        assert q.include_metadata is True
        assert q.depth == 1

    def test_relationship_query(self):
        q = GraphQuery(query_type="relationship", limit=50, depth=3)
        assert q.limit == 50
        assert q.depth == 3

    def test_with_filters(self):
        q = GraphQuery(query_type="node", filters={"type": "REGULATION"})
        assert q.filters["type"] == "REGULATION"

    def test_to_cypher(self):
        q = GraphQuery(query_type="node")
        cypher = q.to_cypher()
        assert isinstance(cypher, str)
        assert len(cypher) > 0

    def test_path_query_type(self):
        q = GraphQuery(query_type="path")
        assert q.query_type == "path"

    def test_subgraph_query_type(self):
        q = GraphQuery(query_type="subgraph")
        assert q.query_type == "subgraph"

    def test_pattern_query_type(self):
        q = GraphQuery(query_type="pattern")
        assert q.query_type == "pattern"


# --- GraphPath ---
class TestGraphPath:
    def test_empty_path(self):
        p = GraphPath()
        assert p.nodes == []
        assert p.relationships == []
        assert p.total_weight == 0.0

    def test_add_step_first_node(self):
        p = GraphPath()
        node = GraphNode(type=NodeType.REGULATION)
        p.add_step(node, None)
        assert len(p.nodes) == 1
        assert len(p.relationships) == 0

    def test_add_step_with_relationship(self):
        p = GraphPath()
        n1 = GraphNode(type=NodeType.REGULATION)
        n2 = GraphNode(type=NodeType.CONTROL)
        rel = GraphRelationship(source_id=n1.id, target_id=n2.id)
        p.add_step(n1, None)
        p.add_step(n2, rel)
        assert len(p.nodes) == 2
        assert len(p.relationships) == 1

    def test_to_dict(self):
        p = GraphPath()
        node = GraphNode()
        p.add_step(node, None)
        d = p.to_dict()
        assert "nodes" in d
        assert "relationships" in d
        assert "total_weight" in d


# --- GraphSnapshot ---
class TestGraphSnapshot:
    def test_default_creation(self):
        s = GraphSnapshot()
        assert isinstance(s.id, str)
        assert isinstance(s.timestamp, datetime)
        assert s.nodes == []
        assert s.relationships == []

    def test_with_data(self):
        nodes = [GraphNode(), GraphNode(type=NodeType.CONTROL)]
        rels = [GraphRelationship(source_id=nodes[0].id, target_id=nodes[1].id)]
        s = GraphSnapshot(nodes=nodes, relationships=rels)
        assert len(s.nodes) == 2
        assert len(s.relationships) == 1

    def test_to_dict(self):
        s = GraphSnapshot()
        d = s.to_dict()
        assert "id" in d
        assert "timestamp" in d
        assert "nodes" in d
        assert "relationships" in d
        assert "metadata" in d
