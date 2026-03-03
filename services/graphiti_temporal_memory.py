"""
Graphiti Temporal Memory Framework for ruleIQ
Implements time-aware knowledge graphs for regulatory tracking
"""

from typing import Dict, List, Optional, Any
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
import json
import logging
from neo4j import GraphDatabase
from collections import defaultdict

logger = logging.getLogger(__name__)


class TemporalGranularity(Enum):
    """Time granularity levels for regulatory changes"""

    REAL_TIME = "real_time"  # Immediate changes
    DAILY = "daily"  # Daily consolidation
    WEEKLY = "weekly"  # Weekly summaries
    MONTHLY = "monthly"  # Monthly reports
    QUARTERLY = "quarterly"  # Quarterly reviews
    ANNUAL = "annual"  # Annual compliance


class ChangeType(Enum):
    """Types of regulatory changes"""

    NEW_REGULATION = "new_regulation"
    AMENDMENT = "amendment"
    REPEAL = "repeal"
    GUIDANCE_UPDATE = "guidance_update"
    ENFORCEMENT_ACTION = "enforcement_action"
    CONSULTATION = "consultation"
    EFFECTIVE_DATE = "effective_date"


@dataclass
class TemporalNode:
    """Represents a time-aware knowledge node"""

    node_id: str
    entity_type: str
    content: Dict[str, Any]
    valid_from: datetime
    valid_to: Optional[datetime] = None
    confidence: float = 1.0
    source_ids: List[str] = field(default_factory=list)
    change_type: Optional[ChangeType] = None
    jurisdiction: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class TemporalEdge:
    """Represents a time-aware relationship"""

    edge_id: str
    source_id: str
    target_id: str
    relationship_type: str
    valid_from: datetime
    valid_to: Optional[datetime] = None
    confidence: float = 1.0
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class RegulatoryClock:
    """Tracks regulatory timelines and deadlines"""

    regulation_id: str
    jurisdiction: str
    published_date: datetime
    effective_date: datetime
    consultation_end: Optional[datetime] = None
    grace_period_end: Optional[datetime] = None
    review_date: Optional[datetime] = None
    sunset_date: Optional[datetime] = None


class GraphitiTemporalMemory:
    """
    Temporal memory system for regulatory compliance tracking
    Integrates with Neo4j for persistent storage
    """

    def __init__(self, neo4j_uri: str, neo4j_user: str, neo4j_password: str):
        self.driver = GraphDatabase.driver(neo4j_uri, auth=(neo4j_user, neo4j_password))
        self.temporal_index: Dict[str, List[TemporalNode]] = defaultdict(list)
        self.regulatory_clocks: Dict[str, RegulatoryClock] = {}
        self.change_history: List[Dict[str, Any]] = []

    async def add_temporal_node(self, node: TemporalNode) -> str:
        """Add a time-aware node to the graph"""
        with self.driver.session() as session:
            query = """
            CREATE (n:TemporalEntity {
                node_id: $node_id,
                entity_type: $entity_type,
                content: $content,
                valid_from: datetime($valid_from),
                valid_to: $valid_to,
                confidence: $confidence,
                source_ids: $source_ids,
                change_type: $change_type,
                jurisdiction: $jurisdiction,
                metadata: $metadata
            })
            RETURN n.node_id as node_id
            """

            result = session.run(
                query,
                node_id=node.node_id,
                entity_type=node.entity_type,
                content=json.dumps(node.content),
                valid_from=node.valid_from.isoformat(),
                valid_to=node.valid_to.isoformat() if node.valid_to else None,
                confidence=node.confidence,
                source_ids=node.source_ids,
                change_type=node.change_type.value if node.change_type else None,
                jurisdiction=node.jurisdiction,
                metadata=json.dumps(node.metadata),
            )

            # Update temporal index
            self.temporal_index[node.entity_type].append(node)

            # Track regulatory change
            if node.change_type:
                self._track_change(node)

            return result.single()["node_id"]

    async def add_temporal_edge(self, edge: TemporalEdge) -> str:
        """Add a time-aware relationship to the graph"""
        with self.driver.session() as session:
            query = """
            MATCH (s:TemporalEntity {node_id: $source_id})
            MATCH (t:TemporalEntity {node_id: $target_id})
            CREATE (s)-[r:TEMPORAL_RELATION {
                edge_id: $edge_id,
                relationship_type: $relationship_type,
                valid_from: datetime($valid_from),
                valid_to: $valid_to,
                confidence: $confidence,
                metadata: $metadata
            }]->(t)
            RETURN r.edge_id as edge_id
            """

            result = session.run(
                query,
                edge_id=edge.edge_id,
                source_id=edge.source_id,
                target_id=edge.target_id,
                relationship_type=edge.relationship_type,
                valid_from=edge.valid_from.isoformat(),
                valid_to=edge.valid_to.isoformat() if edge.valid_to else None,
                confidence=edge.confidence,
                metadata=json.dumps(edge.metadata),
            )

            return result.single()["edge_id"]

    async def query_at_time(
        self, timestamp: datetime, entity_type: Optional[str] = None
    ) -> List[TemporalNode]:
        """Query the graph state at a specific point in time"""
        with self.driver.session() as session:
            query = """
            MATCH (n:TemporalEntity)
            WHERE datetime($timestamp) >= n.valid_from
            AND (n.valid_to IS NULL OR datetime($timestamp) <= n.valid_to)
            """

            if entity_type:
                query += " AND n.entity_type = $entity_type"

            query += " RETURN n"

            params = {"timestamp": timestamp.isoformat()}
            if entity_type:
                params["entity_type"] = entity_type

            result = session.run(query, params)

            nodes = []
            for record in result:
                node_data = record["n"]
                nodes.append(self._dict_to_temporal_node(node_data))

            return nodes

    async def track_regulatory_change(
        self,
        regulation_id: str,
        change_type: ChangeType,
        jurisdiction: str,
        effective_date: datetime,
        description: str,
        sources: List[str],
    ) -> str:
        """Track a regulatory change with temporal awareness"""

        # Create temporal node for the change
        node = TemporalNode(
            node_id=f"change_{regulation_id}_{datetime.now().timestamp()}",
            entity_type="regulatory_change",
            content={
                "regulation_id": regulation_id,
                "description": description,
                "jurisdiction": jurisdiction,
            },
            valid_from=datetime.now(),
            valid_to=None,
            confidence=1.0,
            source_ids=sources,
            change_type=change_type,
            jurisdiction=jurisdiction,
            metadata={
                "effective_date": effective_date.isoformat(),
                "tracked_at": datetime.now().isoformat(),
            },
        )

        node_id = await self.add_temporal_node(node)

        # Update regulatory clock if needed
        if regulation_id not in self.regulatory_clocks:
            self.regulatory_clocks[regulation_id] = RegulatoryClock(
                regulation_id=regulation_id,
                jurisdiction=jurisdiction,
                published_date=datetime.now(),
                effective_date=effective_date,
            )

        return node_id

    async def get_regulatory_timeline(
        self,
        jurisdiction: Optional[str] = None,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
    ) -> List[Dict[str, Any]]:
        """Get timeline of regulatory changes"""
        with self.driver.session() as session:
            query = """
            MATCH (n:TemporalEntity {entity_type: 'regulatory_change'})
            WHERE 1=1
            """

            params = {}

            if jurisdiction:
                query += " AND n.jurisdiction = $jurisdiction"
                params["jurisdiction"] = jurisdiction

            if start_date:
                query += " AND n.valid_from >= datetime($start_date)"
                params["start_date"] = start_date.isoformat()

            if end_date:
                query += " AND n.valid_from <= datetime($end_date)"
                params["end_date"] = end_date.isoformat()

            query += " RETURN n ORDER BY n.valid_from DESC"

            result = session.run(query, params)

            timeline = []
            for record in result:
                node_data = record["n"]
                timeline.append(
                    {
                        "node_id": node_data["node_id"],
                        "regulation_id": json.loads(node_data["content"])[
                            "regulation_id",
                        ],
                        "description": json.loads(node_data["content"])["description"],
                        "jurisdiction": node_data["jurisdiction"],
                        "change_type": node_data["change_type"],
                        "valid_from": node_data["valid_from"],
                        "metadata": json.loads(node_data["metadata"]),
                    },
                )

            return timeline

    async def predict_future_state(
        self, future_date: datetime, entity_type: Optional[str] = None
    ) -> Dict[str, Any]:
        """Predict compliance state at a future date based on known changes"""

        # Get current state
        current_state = await self.query_at_time(datetime.now(), entity_type)

        # Get scheduled changes
        with self.driver.session() as session:
            query = """
            MATCH (n:TemporalEntity)
            WHERE n.metadata CONTAINS 'effective_date'
            AND datetime($future_date) >= datetime(n.metadata.effective_date)
            AND datetime($future_date) >= n.valid_from
            """

            if entity_type:
                query += " AND n.entity_type = $entity_type"

            query += " RETURN n"

            params = {"future_date": future_date.isoformat()}
            if entity_type:
                params["entity_type"] = entity_type

            result = session.run(query, params)

            scheduled_changes = []
            for record in result:
                scheduled_changes.append(self._dict_to_temporal_node(record["n"]))

        return {
            "prediction_date": future_date.isoformat(),
            "current_state_count": len(current_state),
            "scheduled_changes_count": len(scheduled_changes),
            "predicted_entities": len(current_state) + len(scheduled_changes),
            "confidence": self._calculate_prediction_confidence(future_date),
            "scheduled_changes": scheduled_changes,
        }

    async def consolidate_temporal_knowledge(
        self, granularity: TemporalGranularity, jurisdiction: Optional[str] = None
    ) -> Dict[str, Any]:
        """Consolidate temporal knowledge at specified granularity"""

        consolidation_window = self._get_consolidation_window(granularity)
        start_date = datetime.now() - consolidation_window

        # Get changes in window
        timeline = await self.get_regulatory_timeline(
            jurisdiction=jurisdiction, start_date=start_date, end_date=datetime.now(),
        )

        # Group by change type
        changes_by_type = defaultdict(list)
        for change in timeline:
            changes_by_type[change["change_type"]].append(change)

        # Calculate statistics
        stats = {
            "granularity": granularity.value,
            "period": {
                "start": start_date.isoformat(),
                "end": datetime.now().isoformat(),
            },
            "total_changes": len(timeline),
            "by_type": {
                change_type: len(changes)
                for change_type, changes in changes_by_type.items()
            },
            "recent_changes": timeline[:10] if timeline else [],
        }

        return stats

    async def detect_temporal_patterns(
        self, lookback_days: int = 90
    ) -> List[Dict[str, Any]]:
        """Detect patterns in regulatory changes over time"""

        start_date = datetime.now() - timedelta(days=lookback_days)
        timeline = await self.get_regulatory_timeline(start_date=start_date)

        patterns = []

        # Detect acceleration in changes
        if len(timeline) > 10:
            recent_rate = len(
                [
                    c
                    for c in timeline
                    if datetime.fromisoformat(c["valid_from"])
                    > datetime.now() - timedelta(days=30)
                ],
            )
            older_rate = len(
                [
                    c
                    for c in timeline
                    if datetime.fromisoformat(c["valid_from"])
                    <= datetime.now() - timedelta(days=30)
                ],
            )

            if recent_rate > older_rate * 1.5:
                patterns.append(
                    {
                        "pattern": "acceleration",
                        "description": "Regulatory change rate increasing",
                        "recent_monthly_rate": recent_rate,
                        "previous_rate": older_rate / 2,
                    },
                )

        # Detect jurisdiction hotspots
        jurisdiction_counts = defaultdict(int)
        for change in timeline:
            if change.get("jurisdiction"):
                jurisdiction_counts[change["jurisdiction"]] += 1

        if jurisdiction_counts:
            hotspot = max(jurisdiction_counts, key=jurisdiction_counts.get)
            patterns.append(
                {
                    "pattern": "jurisdiction_hotspot",
                    "description": f"High activity in {hotspot}",
                    "jurisdiction": hotspot,
                    "change_count": jurisdiction_counts[hotspot],
                },
            )

        return patterns

    def _track_change(self, node: TemporalNode):
        """Track change in history"""
        self.change_history.append(
            {
                "timestamp": datetime.now().isoformat(),
                "node_id": node.node_id,
                "change_type": node.change_type.value if node.change_type else None,
                "jurisdiction": node.jurisdiction,
                "content": node.content,
            },
        )

    def _dict_to_temporal_node(self, data: Dict) -> TemporalNode:
        """Convert Neo4j result to TemporalNode"""
        return TemporalNode(
            node_id=data["node_id"],
            entity_type=data["entity_type"],
            content=(
                json.loads(data["content"])
                if isinstance(data["content"], str)
                else data["content"],
            ),
            valid_from=(
                datetime.fromisoformat(data["valid_from"])
                if isinstance(data["valid_from"], str)
                else data["valid_from"],
            ),
            valid_to=(
                datetime.fromisoformat(data["valid_to"])
                if data.get("valid_to") and isinstance(data["valid_to"], str)
                else data.get("valid_to"),
            ),
            confidence=data.get("confidence", 1.0),
            source_ids=data.get("source_ids", []),
            change_type=(
                ChangeType(data["change_type"]) if data.get("change_type") else None,
            ),
            jurisdiction=data.get("jurisdiction"),
            metadata=(
                json.loads(data["metadata"])
                if isinstance(data.get("metadata", {}), str)
                else data.get("metadata", {}),
            ),
        )

    def _get_consolidation_window(self, granularity: TemporalGranularity) -> timedelta:
        """Get time window for consolidation"""
        windows = {
            TemporalGranularity.REAL_TIME: timedelta(hours=1),
            TemporalGranularity.DAILY: timedelta(days=1),
            TemporalGranularity.WEEKLY: timedelta(weeks=1),
            TemporalGranularity.MONTHLY: timedelta(days=30),
            TemporalGranularity.QUARTERLY: timedelta(days=90),
            TemporalGranularity.ANNUAL: timedelta(days=365),
        }
        return windows.get(granularity, timedelta(days=1))

    def _calculate_prediction_confidence(self, future_date: datetime) -> float:
        """Calculate confidence for future predictions"""
        days_ahead = (future_date - datetime.now()).days

        if days_ahead <= 30:
            return 0.95
        elif days_ahead <= 90:
            return 0.85
        elif days_ahead <= 180:
            return 0.70
        elif days_ahead <= 365:
            return 0.50
        else:
            return 0.30

    async def close(self):
        """Close database connection"""
        self.driver.close()


class TemporalMemoryIntegration:
    """
    Integration layer between Graphiti temporal memory and IQ agent
    """

    def __init__(self, temporal_memory: GraphitiTemporalMemory):
        self.memory = temporal_memory

    async def process_regulatory_update(
        self, update_text: str, sources: List[str], jurisdiction: str = "UK"
    ) -> Dict[str, Any]:
        """Process a regulatory update and store in temporal memory"""

        # Extract key information (simplified - would use NLP in production)
        change_type = self._classify_change(update_text)
        effective_date = self._extract_effective_date(update_text)
        regulation_id = self._extract_regulation_id(update_text)

        # Track the change
        node_id = await self.memory.track_regulatory_change(
            regulation_id=regulation_id,
            change_type=change_type,
            jurisdiction=jurisdiction,
            effective_date=effective_date,
            description=update_text[:500],  # First 500 chars
            sources=sources,
        )

        # Check for patterns
        patterns = await self.memory.detect_temporal_patterns()

        return {
            "node_id": node_id,
            "regulation_id": regulation_id,
            "change_type": change_type.value,
            "effective_date": effective_date.isoformat(),
            "patterns_detected": patterns,
        }

    async def get_compliance_forecast(self, months_ahead: int = 3) -> Dict[str, Any]:
        """Get compliance forecast for coming months"""

        future_date = datetime.now() + timedelta(days=months_ahead * 30)
        prediction = await self.memory.predict_future_state(future_date)

        # Get upcoming deadlines
        timeline = await self.memory.get_regulatory_timeline(
            start_date=datetime.now(), end_date=future_date,
        )

        upcoming_deadlines = [
            change
            for change in timeline
            if change.get("metadata", {}).get("effective_date")
        ]

        return {
            "forecast_period": {
                "start": datetime.now().isoformat(),
                "end": future_date.isoformat(),
            },
            "prediction": prediction,
            "upcoming_deadlines": upcoming_deadlines,
            "risk_assessment": self._assess_compliance_risk(upcoming_deadlines),
        }

    def _classify_change(self, text: str) -> ChangeType:
        """Classify the type of regulatory change"""
        text_lower = text.lower()

        if "new regulation" in text_lower or "introduces" in text_lower:
            return ChangeType.NEW_REGULATION
        elif "amendment" in text_lower or "modifies" in text_lower:
            return ChangeType.AMENDMENT
        elif "repeal" in text_lower or "removes" in text_lower:
            return ChangeType.REPEAL
        elif "guidance" in text_lower:
            return ChangeType.GUIDANCE_UPDATE
        elif "enforcement" in text_lower:
            return ChangeType.ENFORCEMENT_ACTION
        elif "consultation" in text_lower:
            return ChangeType.CONSULTATION
        else:
            return ChangeType.EFFECTIVE_DATE

    def _extract_effective_date(self, text: str) -> datetime:
        """Extract effective date from text (simplified)"""
        # In production, would use proper date extraction
        return datetime.now() + timedelta(days=30)

    def _extract_regulation_id(self, text: str) -> str:
        """Extract regulation identifier (simplified)"""
        # In production, would use NER or pattern matching
        import hashlib

        return f"REG_{hashlib.md5(text.encode()).hexdigest()[:8]}"

    def _assess_compliance_risk(self, upcoming_changes: List[Dict]) -> str:
        """Assess compliance risk based on upcoming changes"""
        if len(upcoming_changes) == 0:
            return "LOW"
        elif len(upcoming_changes) <= 3:
            return "MEDIUM"
        else:
            return "HIGH"
