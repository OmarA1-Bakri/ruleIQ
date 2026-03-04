"""
Compliance Query Engine for Neo4j GraphRAG.
Provides high-performance query interface for compliance data.
"""

import logging
from typing import Dict, Any, List, Optional
from neo4j import AsyncGraphDatabase

logger = logging.getLogger(__name__)


class ComplianceQueryEngine:
    """Query engine for compliance data in Neo4j."""

    def __init__(
        self,
        uri: str,
        user: str,
        password: str,
        database: Optional[str] = None,
    ) -> None:
        """Initialize query engine with Neo4j connection."""
        self.driver = AsyncGraphDatabase.driver(uri, auth=(user, password))
        self.database = database
        self.logger = logging.getLogger(self.__class__.__name__)

    async def close(self):
        """Close Neo4j driver connection."""
        await self.driver.close()

    async def get_applicable_regulations(
        self, business_profile: Dict[str, Any]
    ) -> List[Dict[str, Any]]:
        """
        Get regulations applicable to a business profile.

        Args:
            business_profile: Dictionary with business attributes

        Returns:
            List of applicable regulations with metadata
        """
        query = """
        MATCH (r:Regulation)
        WHERE
            (r.business_triggers.industry = $industry OR r.business_triggers.industry IS NULL) AND
            (r.business_triggers.processes_payments = $processes_payments OR r.business_triggers.processes_payments IS NULL) AND
            (r.business_triggers.stores_customer_data = $stores_customer_data OR r.business_triggers.stores_customer_data IS NULL) AND
            (r.business_triggers.country = $country OR r.business_triggers.country = 'Global' OR r.business_triggers.country IS NULL)
        RETURN r
        ORDER BY r.risk_metadata.base_risk_score DESC
        """

        async with self.driver.session(database=self.database) as session:
            result = await session.run(query, business_profile)
            regulations = []
            async for record in result:
                reg = dict(record["r"])
                regulations.append(reg)
            return regulations

    async def get_regulation_risk_analysis(self, regulation_id: str) -> Dict[str, Any]:
        """
        Get risk analysis for a specific regulation.

        Args:
            regulation_id: Regulation identifier

        Returns:
            Risk analysis with scores and enforcement data
        """
        query = """
        MATCH (r:Regulation {id: $reg_id})
        OPTIONAL MATCH (r)-[:HAS_ENFORCEMENT]->(e:Enforcement)
        RETURN r, collect(e) as enforcements
        """

        async with self.driver.session(database=self.database) as session:
            result = await session.run(query, reg_id=regulation_id)
            record = await result.single()
            if not record:
                return {}

            reg = dict(record["r"])
            enforcements = [dict(e) for e in record["enforcements"]]

            # Calculate adjusted risk based on enforcement
            base_risk = reg.get("risk_metadata", {}).get("base_risk_score", 5)
            enforcement_adjustment = min(
                len(enforcements) * 0.5, 3
            )  # Max 3 point adjustment

            return {
                "base_risk_score": base_risk,
                "adjusted_risk": min(base_risk + enforcement_adjustment, 10),
                "enforcement_frequency": reg.get("risk_metadata", {}).get(
                    "enforcement_frequency",
                ),
                "max_penalty": reg.get("risk_metadata", {}).get("max_penalty"),
                "enforcement_count": len(enforcements),
                "total_penalties": sum(
                    e.get("penalty_amount", 0) for e in enforcements
                ),
            }

    async def get_suggested_controls(self, regulation_id: str) -> List[str]:
        """
        Get suggested controls for a regulation.

        Args:
            regulation_id: Regulation identifier

        Returns:
            List of suggested control names
        """
        query = """
        MATCH (r:Regulation {id: $reg_id})
        RETURN r.suggested_controls as controls
        """

        async with self.driver.session(database=self.database) as session:
            result = await session.run(query, reg_id=regulation_id)
            record = await result.single()
            if record and record["controls"]:
                return record["controls"]
            return []

    async def get_automation_statistics(self) -> Dict[str, Any]:
        """
        Get automation potential statistics across all regulations.

        Returns:
            Statistics on automation potential
        """
        query = """
        MATCH (r:Regulation)
        WHERE r.automation_potential IS NOT NULL
        RETURN
            avg(r.automation_potential) as average_potential,
            min(r.automation_potential) as min_potential,
            max(r.automation_potential) as max_potential,
            count(r) as regulation_count,
            count(CASE WHEN r.automation_potential >= 0.7 THEN 1 END) as high_automation_count
        """

        async with self.driver.session(database=self.database) as session:
            result = await session.run(query)
            record = await result.single()
            return dict(record) if record else {}

    async def get_regulation_dependencies(
        self, regulation_id: str
    ) -> List[Dict[str, Any]]:
        """
        Get regulations that this regulation depends on.

        Args:
            regulation_id: Regulation identifier

        Returns:
            List of dependent regulations
        """
        query = """
        MATCH (r:Regulation {id: $reg_id})-[:DEPENDS_ON]->(dep:Regulation)
        RETURN dep
        """

        async with self.driver.session(database=self.database) as session:
            result = await session.run(query, reg_id=regulation_id)
            dependencies = []
            async for record in result:
                dependencies.append(dict(record["dep"]))
            return dependencies

    async def find_equivalent_regulations(
        self, regulation_id: str
    ) -> List[Dict[str, Any]]:
        """
        Find regulations equivalent to the given one.

        Args:
            regulation_id: Regulation identifier

        Returns:
            List of equivalent regulations
        """
        query = """
        MATCH (r:Regulation {id: $reg_id})-[:EQUIVALENT_TO]-(eq:Regulation)
        RETURN eq
        """

        async with self.driver.session(database=self.database) as session:
            result = await session.run(query, reg_id=regulation_id)
            equivalents = []
            async for record in result:
                equivalents.append(dict(record["eq"]))
            return equivalents

    async def find_conflicting_regulations(
        self, regulation_id: str
    ) -> List[Dict[str, Any]]:
        """
        Find regulations that conflict with the given one.

        Args:
            regulation_id: Regulation identifier

        Returns:
            List of conflicting regulations
        """
        query = """
        MATCH (r:Regulation {id: $reg_id})-[c:CONFLICTS_WITH]-(conf:Regulation)
        RETURN conf, c.conflict_type as conflict_type
        """

        async with self.driver.session(database=self.database) as session:
            result = await session.run(query, reg_id=regulation_id)
            conflicts = []
            async for record in result:
                conflict = dict(record["conf"])
                conflict["conflict_type"] = record["conflict_type"]
                conflicts.append(conflict)
            return conflicts
