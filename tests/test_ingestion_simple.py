"""

Simplified ingestion test for compliance data into Neo4j.
"""

import asyncio
import json
import os
from pathlib import Path
from neo4j import AsyncGraphDatabase
from dotenv import load_dotenv
import logging
import sys

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)
load_dotenv()


class SimpleIngestion:
    """Simplified Neo4j ingestion for testing."""

    def __init__(self):
        self.uri = "bolt://localhost:7688"
        self.user = os.getenv("NEO4J_USERNAME", "neo4j")
        self.password = os.getenv("NEO4J_PASSWORD", "ruleiq123")
        self.driver = AsyncGraphDatabase.driver(self.uri, auth=(self.user, self.password))

    async def close(self):
        await self.driver.close()

    async def clear_database(self):
        """Clear all nodes and relationships."""
        async with self.driver.session() as session:
            await session.run("MATCH (n) DETACH DELETE n")
            logger.info("Cleared database")

    async def create_indexes(self):
        """Create necessary indexes."""
        async with self.driver.session() as session:
            await session.run(
                """
                CREATE INDEX regulation_id IF NOT EXISTS
                FOR (r:Regulation) ON (r.id)
            """,
            )
            await session.run(
                """
                CREATE INDEX regulation_title IF NOT EXISTS
                FOR (r:Regulation) ON (r.title)
            """,
            )
            logger.info("Created indexes")

    async def ingest_regulations(self, manifest_path: Path) -> int:
        """
        Ingest regulations from manifest file.

        Returns:
            Number of regulations created
        """
        with open(manifest_path, "r") as f:
            data = json.load(f)
        items = data.get("items", [])
        created_count = 0
        async with self.driver.session() as session:
            for item in items[:10]:
                try:
                    query = """
                    CREATE (r:Regulation {
                        id: $id,
                        title: $title,
                        url: $url,
                        category: $category,
                        tags: $tags,
                        priority: $priority,
                        base_risk_score: $risk_score,
                        automation_potential: $automation,
                        enforcement_frequency: $enforcement_freq,
                        max_penalty: $max_penalty
                    })
                    RETURN r
                    """
                    params = {
                        "id": item.get("id"),
                        "title": item.get("title"),
                        "url": item.get("url"),
                        "category": item.get("category", "General"),
                        "tags": item.get("tags", []),
                        "priority": item.get("priority", 3),
                        "risk_score": item.get("risk_metadata", {}).get("base_risk_score", 5),
                        "automation": item.get("automation_potential", 0.5),
                        "enforcement_freq": item.get("risk_metadata", {}).get(
                            "enforcement_frequency", "medium"
                        ),
                        "max_penalty": item.get("risk_metadata", {}).get("max_penalty", "Unknown"),
                    }
                    result = await session.run(query, params)
                    await result.consume()
                    created_count += 1
                    if "business_triggers" in item:
                        trigger_query = """
                        MATCH (r:Regulation {id: $id})
                        SET r.business_triggers = $triggers
                        """
                        await session.run(
                            trigger_query,
                            {"id": item["id"], "triggers": json.dumps(item["business_triggers"])},
                        )
                    if "suggested_controls" in item:
                        control_query = """
                        MATCH (r:Regulation {id: $id})
                        SET r.suggested_controls = $controls
                        """
                        await session.run(
                            control_query,
                            {"id": item["id"], "controls": item["suggested_controls"]},
                        )
                except Exception as e:
                    logger.error("Failed to ingest %s: %s" % (item.get("id"), e))
        logger.info("Created %s regulations" % created_count)
        return created_count

    async def test_query(self):
        """Test querying the ingested data."""
        async with self.driver.session() as session:
            count_result = await session.run("MATCH (r:Regulation) RETURN count(r) as count")
            count_record = await count_result.single()
            logger.info("Total regulations: %s" % count_record["count"])
            high_risk_result = await session.run(
                """
                MATCH (r:Regulation)
                WHERE r.base_risk_score >= 8
                RETURN r.title as title, r.base_risk_score as risk
                ORDER BY risk DESC
                LIMIT 5
            """,
            )
            logger.info("High-risk regulations:")
            async for record in high_risk_result:
                logger.info("  - %s (risk: %s)" % (record["title"], record["risk"]))
            automation_result = await session.run(
                """
                MATCH (r:Regulation)
                WHERE r.automation_potential >= 0.7
                RETURN r.title as title, r.automation_potential as automation
                ORDER BY automation DESC
                LIMIT 5
            """,
            )
            logger.info("Highly automatable regulations:")
            async for record in automation_result:
                logger.info("  - %s (automation: %s)" % (record["title"], record["automation"]))


async def main():
    """Run the simplified ingestion test."""
    ingestion = SimpleIngestion()
    try:
        logger.info("Starting simplified ingestion test...")
        await ingestion.clear_database()
        await ingestion.create_indexes()
        manifest_path = Path("data/manifests/compliance_ml_manifest_enhanced.json")
        if not manifest_path.exists():
            manifest_path = Path("data/manifests/compliance_ml_manifest.json")
        count = await ingestion.ingest_regulations(manifest_path)
        await ingestion.test_query()
        logger.info("\n✅ Successfully ingested %s regulations into Neo4j!" % count)
    except Exception as e:
        logger.error("Test failed: %s" % e)
        return 1
    finally:
        await ingestion.close()
    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
