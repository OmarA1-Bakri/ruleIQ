"""
Enterprise-grade Compliance Data Ingestion Pipeline for Neo4j GraphRAG
Handles ingestion of enhanced compliance manifests with full production safeguards
"""

import json
import asyncio
import hashlib
from typing import Dict, List, Any, Optional, Tuple, Set
from pathlib import Path
from datetime import datetime, timezone
from dataclasses import dataclass, field
from enum import Enum
import logging
import traceback

from neo4j import AsyncGraphDatabase, AsyncSession
from neo4j.exceptions import Neo4jError, ServiceUnavailable, SessionExpired
from pydantic import BaseModel, Field, validator, ValidationError
import numpy as np
from tenacity import (
    retry,
    stop_after_attempt,
    wait_exponential,
    retry_if_exception_type,
    before_sleep_log,
)

# Production logging configuration
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)


class IngestionStatus(Enum):
    """Ingestion status tracking"""

    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    FAILED = "failed"
    PARTIAL = "partial"
    RETRY = "retry"


class DataQuality(Enum):
    """Data quality indicators"""

    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"
    INVALID = "invalid"


@dataclass
class IngestionMetrics:
    """Track ingestion performance and quality metrics"""

    total_items: int = 0
    successful_items: int = 0
    failed_items: int = 0
    skipped_items: int = 0
    relationships_created: int = 0
    nodes_created: int = 0
    nodes_updated: int = 0
    start_time: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    end_time: Optional[datetime] = None
    errors: List[Dict[str, Any]] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)
    data_quality_scores: Dict[str, float] = field(default_factory=dict)

    @property
    def success_rate(self) -> float:
        """Calculate success rate"""
        if self.total_items == 0:
            return 0.0
        return self.successful_items / self.total_items

    @property
    def duration_seconds(self) -> Optional[float]:
        """Calculate processing duration"""
        if self.end_time:
            return (self.end_time - self.start_time).total_seconds()
        return None

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for logging/storage"""
        return {
            "total_items": self.total_items,
            "successful_items": self.successful_items,
            "failed_items": self.failed_items,
            "skipped_items": self.skipped_items,
            "relationships_created": self.relationships_created,
            "nodes_created": self.nodes_created,
            "nodes_updated": self.nodes_updated,
            "success_rate": self.success_rate,
            "duration_seconds": self.duration_seconds,
            "start_time": self.start_time.isoformat(),
            "end_time": self.end_time.isoformat() if self.end_time else None,
            "error_count": len(self.errors),
            "warning_count": len(self.warnings),
            "data_quality_avg": (
                np.mean(list(self.data_quality_scores.values())) if self.data_quality_scores else 0,
            ),
        }


class ComplianceDataValidator(BaseModel):
    """Enterprise-grade validation for compliance data"""

    id: str = Field(..., min_length=1, max_length=200)
    title: str = Field(..., min_length=1, max_length=500)
    url: Optional[str] = Field(None, pattern="^https?://")
    tags: List[str] = Field(default_factory=list)
    priority: int = Field(..., ge=1, le=5)

    # Enhanced metadata
    business_triggers: Optional[Dict[str, Any]] = None
    risk_metadata: Optional[Dict[str, Any]] = None
    automation_potential: Optional[float] = Field(None, ge=0.0, le=1.0)
    suggested_controls: Optional[List[str]] = None
    evidence_templates: Optional[List[str]] = None
    implementation_complexity: Optional[int] = Field(None, ge=1, le=10)

    @validator("business_triggers")
    def validate_business_triggers(cls, v):
        """Validate business trigger structure"""
        if v is not None:
            required_keys = {"industry", "data_types", "jurisdiction"}
            if not any(key in v for key in required_keys):
                logger.warning(f"Business triggers missing key fields: {v}")
        return v

    @validator("risk_metadata")
    def validate_risk_metadata(cls, v):
        """Validate risk metadata structure"""
        if v is not None and "base_risk_score" in v:
            score = v["base_risk_score"]
            if not (0 <= score <= 10):
                raise ValueError(f"Risk score {score} out of range [0, 10]")
        return v

    class Config:
        extra = "allow"  # Allow additional fields for flexibility


class Neo4jComplianceIngestion:
    """
    Production-grade Neo4j ingestion pipeline for compliance data
    Handles millions of nodes with proper error recovery and monitoring
    """

    def __init__(
        self,
        neo4j_uri: str,
        neo4j_user: str,
        neo4j_password: str,
        database: str = "neo4j",
        max_connection_pool_size: int = 50,
        connection_timeout: float = 30.0,
        batch_size: int = 100,
    ) -> None:
        """
        Initialize ingestion pipeline with production configurations

        Args:
            neo4j_uri: Neo4j connection URI
            neo4j_user: Neo4j username
            neo4j_password: Neo4j password
            database: Target database name
            max_connection_pool_size: Maximum connection pool size
            connection_timeout: Connection timeout in seconds
            batch_size: Batch size for bulk operations
        """
        self.uri = neo4j_uri
        self.user = neo4j_user
        self.password = neo4j_password
        self.database = database
        self.batch_size = batch_size

        # Initialize driver with production settings
        self.driver = AsyncGraphDatabase.driver(
            self.uri,
            auth=(self.user, self.password),
            max_connection_pool_size=max_connection_pool_size,
            connection_timeout=connection_timeout,
            max_transaction_retry_time=30.0,
            keep_alive=True,
        )

        self.metrics = IngestionMetrics()
        self._processed_ids: Set[str] = set()
        self._failed_ids: Set[str] = set()

    async def __aenter__(self):
        """Async context manager entry"""
        await self.verify_connection()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit with cleanup"""
        await self.close()

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=4, max=10),
        retry=retry_if_exception_type((ServiceUnavailable, SessionExpired)),
        before_sleep=before_sleep_log(logger, logging.WARNING),
    )
    async def verify_connection(self) -> bool:
        """
        Verify Neo4j connection with retry logic

        Returns:
            True if connection successful
        """
        try:
            async with self.driver.session(database=self.database) as session:
                result = await session.run("RETURN 1 as test")
                await result.single()
                logger.info(f"Successfully connected to Neo4j at {self.uri}")
                return True
        except Exception as e:
            logger.error(f"Failed to connect to Neo4j: {e}")
            raise

    async def create_indexes_and_constraints(self) -> None:
        """
        Create necessary indexes and constraints for optimal performance
        Production-critical for query performance at scale
        """
        index_queries = [
            # Unique constraints
            "CREATE CONSTRAINT regulation_id IF NOT EXISTS FOR (r:Regulation) REQUIRE r.id IS UNIQUE",
            "CREATE CONSTRAINT control_id IF NOT EXISTS FOR (c:Control) REQUIRE c.id IS UNIQUE",
            "CREATE CONSTRAINT enforcement_id IF NOT EXISTS FOR (e:Enforcement) REQUIRE e.id IS UNIQUE",
            # Performance indexes
            "CREATE INDEX regulation_title IF NOT EXISTS FOR (r:Regulation) ON (r.title)",
            "CREATE INDEX regulation_priority IF NOT EXISTS FOR (r:Regulation) ON (r.priority)",
            "CREATE INDEX regulation_risk IF NOT EXISTS FOR (r:Regulation) ON (r.base_risk_score)",
            "CREATE INDEX control_name IF NOT EXISTS FOR (c:Control) ON (c.name)",
            "CREATE INDEX control_effectiveness IF NOT EXISTS FOR (c:Control) ON (c.effectiveness_score)",
            # Composite indexes for common queries
            "CREATE INDEX regulation_industry_risk IF NOT EXISTS FOR (r:Regulation) ON (r.industry, r.base_risk_score)",
            "CREATE INDEX regulation_jurisdiction_priority IF NOT EXISTS FOR (r:Regulation) ON (r.jurisdiction, r.priority)",
            # Full-text search indexes
            "CREATE FULLTEXT INDEX regulation_search IF NOT EXISTS FOR (r:Regulation) ON EACH [r.title, r.description]",
            "CREATE FULLTEXT INDEX control_search IF NOT EXISTS FOR (c:Control) ON EACH [c.name, c.description]",
        ]

        async with self.driver.session(database=self.database) as session:
            for query in index_queries:
                try:
                    await session.run(query)
                    logger.info(f"Index/constraint created: {query[:50]}...")
                except Exception as e:
                    logger.warning(f"Index creation warning (may already exist): {e}")

    def _generate_node_hash(self, data: Dict[str, Any]) -> str:
        """
        Generate deterministic hash for deduplication

        Args:
            data: Node data

        Returns:
            SHA-256 hash of stable fields
        """
        stable_fields = {
            "id": data.get("id"),
            "title": data.get("title"),
            "url": data.get("url"),
        }
        stable_string = json.dumps(stable_fields, sort_keys=True)
        return hashlib.sha256(stable_string.encode()).hexdigest()

    def _assess_data_quality(self, item: Dict[str, Any]) -> Tuple[DataQuality, float]:
        """
        Assess data quality for monitoring and filtering

        Args:
            item: Data item to assess

        Returns:
            Tuple of (quality_level, quality_score)
        """
        score = 1.0

        # Check required fields
        required_fields = ["id", "title"]
        for field in required_fields:
            if not item.get(field):
                score -= 0.3

        # Check enhanced metadata
        if item.get("business_triggers"):
            score += 0.1
        else:
            score -= 0.1

        if item.get("risk_metadata"):
            score += 0.1
        else:
            score -= 0.1

        if item.get("suggested_controls"):
            score += 0.1

        if item.get("automation_potential") is not None:
            score += 0.05

        # Check data completeness
        total_fields = len(item)
        if total_fields < 5:
            score -= 0.2
        elif total_fields > 10:
            score += 0.1

        # Normalize score
        score = max(0.0, min(1.0, score))

        # Determine quality level
        if score >= 0.8:
            quality = DataQuality.HIGH
        elif score >= 0.6:
            quality = DataQuality.MEDIUM
        elif score >= 0.3:
            quality = DataQuality.LOW
        else:
            quality = DataQuality.INVALID

        return quality, score

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=2, max=10),
        retry=retry_if_exception_type(Neo4jError),
    )
    async def _ingest_regulation_batch(
        self, session: AsyncSession, batch: List[Dict[str, Any]]
    ) -> int:
        """
        Ingest a batch of regulations with transaction management

        Args:
            session: Neo4j session
            batch: Batch of regulation data

        Returns:
            Number of successfully ingested items
        """
        success_count = 0

        # Prepare batch data with validation
        validated_batch = []
        for item in batch:
            try:
                # Validate data
                validator = ComplianceDataValidator(**item)
                validated_item = validator.dict()

                # Add metadata
                validated_item["ingested_at"] = datetime.now(timezone.utc).isoformat()
                validated_item["data_hash"] = self._generate_node_hash(validated_item)

                # Assess quality
                quality, score = self._assess_data_quality(validated_item)
                validated_item["data_quality"] = quality.value
                validated_item["quality_score"] = score

                self.metrics.data_quality_scores[validated_item["id"]] = score

                if quality != DataQuality.INVALID:
                    validated_batch.append(validated_item)
                else:
                    logger.warning(f"Skipping invalid data: {validated_item.get('id')}")
                    self.metrics.skipped_items += 1

            except ValidationError as e:
                logger.error(f"Validation error for item {item.get('id')}: {e}")
                self.metrics.failed_items += 1
                self.metrics.errors.append(
                    {
                        "item_id": item.get("id"),
                        "error": str(e),
                        "timestamp": datetime.now(timezone.utc).isoformat(),
                    },
                )

        if not validated_batch:
            return 0

        # Cypher query for MERGE operation with proper updates
        merge_query = """
        UNWIND $batch AS item
        MERGE (r:Regulation {id: item.id})
        ON CREATE SET
            r.created_at = datetime(),
            r.nodes_created = true
        ON MATCH SET
            r.updated_at = datetime(),
            r.nodes_updated = true
        SET r += item,
            r.last_ingested = datetime()
        WITH r, item

        // Create industry relationships
        FOREACH (industry IN
            CASE
                WHEN item.business_triggers IS NOT NULL
                AND item.business_triggers.industry IS NOT NULL
                THEN [item.business_triggers.industry]
                ELSE []
            END |
            MERGE (i:Industry {name: industry})
            MERGE (r)-[:APPLIES_TO]->(i),
        )

        // Create jurisdiction relationships
        FOREACH (jurisdiction IN
            CASE
                WHEN item.business_triggers IS NOT NULL
                AND item.business_triggers.jurisdiction IS NOT NULL
                THEN [item.business_triggers.jurisdiction]
                ELSE []
            END |
            MERGE (j:Jurisdiction {name: jurisdiction})
            MERGE (r)-[:GOVERNED_BY]->(j),
        )

        // Create control relationships
        FOREACH (control IN
            CASE
                WHEN item.suggested_controls IS NOT NULL
                THEN item.suggested_controls
                ELSE []
            END |
            MERGE (c:Control {name: control})
            MERGE (r)-[:SUGGESTS_CONTROL]->(c),
        )

        // Create tag relationships
        FOREACH (tag IN item.tags |
            MERGE (t:Tag {name: tag})
            MERGE (r)-[:TAGGED_WITH]->(t),
        )

        RETURN r.id as id,
               r.nodes_created as created,
               r.nodes_updated as updated
        """

        try:
            result = await session.run(merge_query, batch=validated_batch)
            records = await result.fetch(1000)  # Fetch all records

            for record in records:
                if record["created"]:
                    self.metrics.nodes_created += 1
                elif record["updated"]:
                    self.metrics.nodes_updated += 1
                success_count += 1
                self._processed_ids.add(record["id"])

            # Count relationships created (approximate)
            self.metrics.relationships_created += (
                len(validated_batch) * 3
            )  # Avg relationships per node

            logger.info(f"Batch ingested: {success_count}/{len(batch)} items")

        except Exception as e:
            logger.error(f"Batch ingestion error: {e}")
            # Track failed items for retry
            for item in batch:
                self._failed_ids.add(item.get("id"))
            raise

        return success_count

    async def ingest_compliance_manifest(
        self, manifest_path: Path, validate_only: bool = False
    ) -> IngestionMetrics:
        """
        Main ingestion entry point with full production safeguards

        Args:
            manifest_path: Path to enhanced manifest JSON
            validate_only: If True, only validate without ingesting

        Returns:
            IngestionMetrics with complete statistics
        """
        logger.info(f"Starting ingestion from {manifest_path}")
        self.metrics = IngestionMetrics()

        try:
            # Load and validate manifest
            with open(manifest_path, "r") as f:
                manifest_data = json.load(f)

            items = manifest_data.get("items", [])
            self.metrics.total_items = len(items)

            if validate_only:
                # Validation-only mode
                for item in items:
                    try:
                        ComplianceDataValidator(**item)
                        quality, score = self._assess_data_quality(item)
                        self.metrics.data_quality_scores[item.get("id")] = score
                        if quality != DataQuality.INVALID:
                            self.metrics.successful_items += 1
                        else:
                            self.metrics.failed_items += 1
                    except ValidationError as e:
                        self.metrics.failed_items += 1
                        logger.error(f"Validation failed for {item.get('id')}: {e}")

                self.metrics.end_time = datetime.now(timezone.utc)
                logger.info(f"Validation complete: {self.metrics.to_dict()}")
                return self.metrics

            # Create indexes for optimal performance
            await self.create_indexes_and_constraints()

            # Process in batches for scalability
            async with self.driver.session(database=self.database) as session:
                for i in range(0, len(items), self.batch_size):
                    batch = items[i : i + self.batch_size]

                    # Use transaction for batch
                    async with session.begin_transaction() as tx:
                        try:
                            success_count = await self._ingest_regulation_batch(
                                session,
                                batch,
                            )
                            await tx.commit()
                            self.metrics.successful_items += success_count
                        except Exception as e:
                            await tx.rollback()
                            logger.error(f"Transaction rollback for batch {i}: {e}")
                            self.metrics.failed_items += len(batch)

                    # Progress logging
                    if (i + self.batch_size) % 500 == 0:
                        logger.info(
                            f"Progress: {i + self.batch_size}/{len(items)} items processed",
                        )

            # Retry failed items once
            if self._failed_ids:
                logger.info(f"Retrying {len(self._failed_ids)} failed items")
                retry_items = [item for item in items if item.get("id") in self._failed_ids]

                async with self.driver.session(database=self.database) as session:
                    for item in retry_items:
                        try:
                            success = await self._ingest_regulation_batch(
                                session,
                                [item],
                            )
                            if success:
                                self.metrics.successful_items += 1
                                self.metrics.failed_items -= 1
                                self._failed_ids.remove(item.get("id"))
                        except Exception as e:
                            logger.error(f"Retry failed for {item.get('id')}: {e}")

            self.metrics.end_time = datetime.now(timezone.utc)

            # Log final metrics
            logger.info(f"Ingestion complete: {self.metrics.to_dict()}")

            # Write metrics to file for monitoring
            metrics_path = (
                manifest_path.parent
                / f"ingestion_metrics_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json",
            )
            with open(metrics_path, "w") as f:
                json.dump(self.metrics.to_dict(), f, indent=2)

            return self.metrics

        except Exception as e:
            logger.error(f"Critical ingestion error: {e}")
            logger.error(traceback.format_exc())
            self.metrics.end_time = datetime.now(timezone.utc)
            self.metrics.errors.append(
                {
                    "error": str(e),
                    "traceback": traceback.format_exc(),
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                },
            )
            raise

    async def ingest_relationships(self, relationships_path: Path) -> IngestionMetrics:
        """
        Ingest regulatory relationships from relationships manifest

        Args:
            relationships_path: Path to relationships JSON

        Returns:
            IngestionMetrics for relationship ingestion
        """
        logger.info(f"Starting relationship ingestion from {relationships_path}")
        metrics = IngestionMetrics()

        try:
            with open(relationships_path, "r") as f:
                relationships_data = json.load(f)

            regulatory_relationships = relationships_data.get(
                "regulatory_relationships",
                {},
            )

            # Cypher query for creating relationships
            relationship_query = """
            UNWIND $relationships AS rel
            MATCH (source:Regulation {id: rel.source_id})
            MATCH (target:Regulation {id: rel.target_id})
            MERGE (source)-[r:RELATES_TO {
                type: rel.type,
                strength: rel.strength,
                control_overlap: rel.control_overlap
            }]->(target)
            SET r.description = rel.description,
                r.updated_at = datetime()
            RETURN source.id as source, target.id as target, type(r) as relationship
            """

            # Process relationships
            async with self.driver.session(database=self.database) as session:
                for source_id, source_data in regulatory_relationships.items():
                    relationships = source_data.get("relationships", [])

                    for rel in relationships:
                        try:
                            rel_data = {
                                "source_id": source_id,
                                "target_id": rel.get("target"),
                                "type": rel.get("type"),
                                "strength": rel.get("strength", 0.5),
                                "control_overlap": rel.get("control_overlap", 0.0),
                                "description": rel.get("description", ""),
                            }

                            result = await session.run(
                                relationship_query,
                                relationships=[rel_data],
                            )
                            await result.consume()
                            metrics.relationships_created += 1

                        except Exception as e:
                            logger.error(
                                f"Failed to create relationship {source_id} -> {rel.get('target')}: {e}",
                            )
                            metrics.failed_items += 1

            metrics.end_time = datetime.now(timezone.utc)
            logger.info(f"Relationship ingestion complete: {metrics.to_dict()}")
            return metrics

        except Exception as e:
            logger.error(f"Relationship ingestion error: {e}")
            metrics.errors.append({"error": str(e)})
            raise

    async def ingest_enforcement_data(self, enforcement_path: Path) -> IngestionMetrics:
        """
        Ingest enforcement database for evidence and patterns

        Args:
            enforcement_path: Path to enforcement JSON

        Returns:
            IngestionMetrics for enforcement ingestion
        """
        logger.info(f"Starting enforcement ingestion from {enforcement_path}")
        metrics = IngestionMetrics()

        try:
            with open(enforcement_path, "r") as f:
                enforcement_data = json.load(f)

            enforcement_actions = enforcement_data.get("enforcement_actions", [])

            # Cypher query for enforcement nodes
            enforcement_query = """
            UNWIND $actions AS action
            MERGE (e:Enforcement {id: action.id})
            SET e += action,
                e.updated_at = datetime()
            WITH e, action

            // Link to regulation
            MATCH (r:Regulation {id: action.regulation})
            MERGE (e)-[:ENFORCES]->(r)

            // Create organization node
            MERGE (o:Organization {name: action.organization})
            MERGE (e)-[:AGAINST]->(o)

            // Create regulator node
            MERGE (reg:Regulator {name: action.regulator})
            MERGE (reg)-[:ISSUED]->(e)

            RETURN e.id as id
            """

            async with self.driver.session(database=self.database) as session:
                for i in range(0, len(enforcement_actions), self.batch_size):
                    batch = enforcement_actions[i : i + self.batch_size]

                    try:
                        result = await session.run(enforcement_query, actions=batch)
                        records = await result.fetch(1000)
                        metrics.nodes_created += len(records)
                        metrics.successful_items += len(records)

                    except Exception as e:
                        logger.error(f"Enforcement batch error: {e}")
                        metrics.failed_items += len(batch)

            metrics.end_time = datetime.now(timezone.utc)
            logger.info(f"Enforcement ingestion complete: {metrics.to_dict()}")
            return metrics

        except Exception as e:
            logger.error(f"Enforcement ingestion error: {e}")
            metrics.errors.append({"error": str(e)})
            raise

    async def verify_ingestion(self) -> Dict[str, Any]:
        """
        Verify ingestion completeness and data integrity

        Returns:
            Verification report
        """
        verification_queries = {
            "regulation_count": "MATCH (r:Regulation) RETURN count(r) as count",
            "control_count": "MATCH (c:Control) RETURN count(c) as count",
            "enforcement_count": "MATCH (e:Enforcement) RETURN count(e) as count",
            "relationship_count": "MATCH ()-[r:RELATES_TO]->() RETURN count(r) as count",
            "industry_coverage": "MATCH (i:Industry) RETURN collect(i.name) as industries",
            "high_risk_regulations": """
                MATCH (r:Regulation)
                WHERE r.base_risk_score >= 8
                RETURN count(r) as count
            """,
            "automation_ready": """
                MATCH (r:Regulation)
                WHERE r.automation_potential >= 0.7
                RETURN count(r) as count
            """,
        }

        verification_report = {}

        async with self.driver.session(database=self.database) as session:
            for key, query in verification_queries.items():
                try:
                    result = await session.run(query)
                    record = await result.single()
                    verification_report[key] = record[0] if record else 0
                except Exception as e:
                    logger.error(f"Verification query failed for {key}: {e}")
                    verification_report[key] = f"Error: {str(e)}"

        logger.info(f"Verification report: {verification_report}")
        return verification_report

    async def close(self):
        """Close Neo4j driver connection"""
        await self.driver.close()
        logger.info("Neo4j connection closed")


# Integration with IQ Agent
class IQComplianceIntegration:
    """
    Integration layer between ingested compliance data and IQ agent
    Provides high-performance queries and intelligent filtering
    """

    def __init__(self, neo4j_driver) -> None:
        """
        Initialize integration with Neo4j driver

        Args:
            neo4j_driver: AsyncNeo4j driver instance
        """
        self.driver = neo4j_driver
        self.query_cache = {}  # Simple query cache

    async def get_applicable_regulations(
        self, business_profile: Dict[str, Any], risk_threshold: float = 5.0
    ) -> List[Dict[str, Any]]:
        """
        Get regulations applicable to a business profile

        Args:
            business_profile: Business context data
            risk_threshold: Minimum risk score to include

        Returns:
            List of applicable regulations with metadata
        """
        query = """
        MATCH (r:Regulation)
        WHERE r.base_risk_score >= $risk_threshold
        AND (
            r.business_triggers.industry = $industry
            OR r.business_triggers.jurisdiction = $jurisdiction
            OR $handles_personal_data = true AND r.id CONTAINS 'gdpr'
            OR $processes_payments = true AND r.id CONTAINS 'pci',
        )
        OPTIONAL MATCH (r)-[:SUGGESTS_CONTROL]->(c:Control)
        OPTIONAL MATCH (r)-[:RELATES_TO]->(related:Regulation)
        RETURN r {
            .*,
            controls: collect(DISTINCT c.name),
            related_regulations: collect(DISTINCT related.id),
            applicability_score:
                CASE
                    WHEN r.business_triggers.industry = $industry THEN 1.0
                    ELSE 0.5
                END * r.priority / 5.0
        } as regulation
        ORDER BY regulation.applicability_score DESC, r.base_risk_score DESC
        LIMIT 50
        """

        params = {
            "industry": business_profile.get("industry", ""),
            "jurisdiction": business_profile.get("jurisdiction", "UK"),
            "handles_personal_data": business_profile.get(
                "handles_personal_data",
                False,
            ),
            "processes_payments": business_profile.get("processes_payments", False),
            "risk_threshold": risk_threshold,
        }

        async with self.driver.session() as session:
            result = await session.run(query, params)
            regulations = await result.fetch(50)

        return [record["regulation"] for record in regulations]

    async def calculate_control_overlap(self, regulation_ids: List[str]) -> Dict[str, Any]:
        """
        Calculate control overlap between regulations

        Args:
            regulation_ids: List of regulation IDs to compare

        Returns:
            Control overlap analysis
        """
        query = """
        UNWIND $regulation_ids AS reg_id
        MATCH (r:Regulation {id: reg_id})-[:SUGGESTS_CONTROL]->(c:Control)
        WITH c, collect(DISTINCT r.id) as regulations
        WHERE size(regulations) > 1
        RETURN {
            control: c.name,
            shared_by: regulations,
            count: size(regulations)
        } as overlap
        ORDER BY overlap.count DESC
        """

        async with self.driver.session() as session:
            result = await session.run(query, regulation_ids=regulation_ids)
            overlaps = await result.fetch(100)

        return {
            "overlapping_controls": [record["overlap"] for record in overlaps],
            "deduplication_potential": len(overlaps) / max(len(regulation_ids), 1),
        }

    async def get_enforcement_evidence(
        self, regulation_id: str, limit: int = 3
    ) -> List[Dict[str, Any]]:
        """
        Get enforcement evidence for a regulation

        Args:
            regulation_id: Regulation ID
            limit: Maximum evidence items to return

        Returns:
            List of enforcement evidence
        """
        query = """
        MATCH (e:Enforcement)-[:ENFORCES]->(r:Regulation {id: $regulation_id})
        RETURN e {
            .*,
            url: 'https://enforcement.regulator.uk/' + e.id
        } as evidence
        ORDER BY e.penalty_amount DESC
        LIMIT $limit
        """

        async with self.driver.session() as session:
            result = await session.run(query, regulation_id=regulation_id, limit=limit)
            evidence = await result.fetch(limit)

        return [record["evidence"] for record in evidence]


if __name__ == "__main__":
    # Example usage for testing
    import os
    from dotenv import load_dotenv

    load_dotenv()

    async def test_ingestion():
        """Test the ingestion pipeline"""

        # Example usage - requires Neo4j credentials in environment
        # For production use, integrate with your application's config management
        neo4j_uri = os.getenv("NEO4J_URI")
        neo4j_user = os.getenv("NEO4J_USER")
        neo4j_password = os.getenv("NEO4J_PASSWORD")

        # Validate required environment variables
        if not neo4j_uri or not neo4j_user or not neo4j_password:
            raise ValueError(
                "Required environment variables missing: NEO4J_URI, NEO4J_USER, NEO4J_PASSWORD. \n"
                "Set them in your environment or use: doppler run -- python -m services.ai.compliance_ingestion_pipeline"
            )

        # Initialize pipeline
        async with Neo4jComplianceIngestion(
            neo4j_uri=neo4j_uri, neo4j_user=neo4j_user, neo4j_password=neo4j_password
        ) as pipeline:
            # Ingest enhanced manifest
            manifest_path = Path("data/manifests/compliance_ml_manifest_enhanced.json")
            if manifest_path.exists():
                metrics = await pipeline.ingest_compliance_manifest(manifest_path)
                print(f"Ingestion metrics: {metrics.to_dict()}")

            # Ingest relationships
            relationships_path = Path("data/manifests/regulatory_relationships.json")
            if relationships_path.exists():
                rel_metrics = await pipeline.ingest_relationships(relationships_path)
                print(f"Relationship metrics: {rel_metrics.to_dict()}")

            # Ingest enforcement data
            enforcement_path = Path("data/enforcement/uk_enforcement_database.json")
            if enforcement_path.exists():
                enf_metrics = await pipeline.ingest_enforcement_data(enforcement_path)
                print(f"Enforcement metrics: {enf_metrics.to_dict()}")

            # Verify ingestion
            verification = await pipeline.verify_ingestion()
            print(f"Verification: {verification}")

    # Run test
    asyncio.run(test_ingestion())
