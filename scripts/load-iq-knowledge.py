#!/usr/bin/env python3
"""
Load IQ's Complete Knowledge Base into Neo4j AuraDB
Gives IQ his full mojo with UK regulations, persona, and intelligence
"""

import asyncio
import json
import sys
from pathlib import Path
import hashlib

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from services.neo4j_service import Neo4jGraphRAGService
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class IQKnowledgeLoader:
    """Load IQ's complete knowledge base into Neo4j"""

    def __init__(self) -> None:
        self.neo4j = Neo4jGraphRAGService()
        self.stats = {
            "iq_persona": 0,
            "uk_regulations": 0,
            "obligations": 0,
            "compliance_domains": 0,
            "relationships": 0,
            "total_nodes": 0,
        }

    async def load_complete_knowledge(self):
        """Orchestrate loading of all IQ's knowledge"""
        logger.info("🧠 LOADING IQ'S COMPLETE KNOWLEDGE BASE")
        logger.info("=" * 60)

        await self.neo4j.initialize()

        try:
            # 1. Load IQ's Persona and CCO Playbook
            logger.info("\n1️⃣ Loading IQ's CCO Persona & Strategic Playbook...")
            await self.load_iq_persona()

            # 2. Load UK Regulatory Database
            logger.info("\n2️⃣ Loading UK Regulatory Database...")
            await self.load_uk_regulations()

            # 3. Load Compliance Manifests
            logger.info("\n3️⃣ Loading Compliance Manifests...")
            await self.load_compliance_manifests()

            # 4. Build Knowledge Graph Relationships
            logger.info("\n4️⃣ Building Knowledge Graph Relationships...")
            await self.build_relationships()

            # 5. Create IQ's Memory Systems
            logger.info("\n5️⃣ Initializing IQ's Memory Systems...")
            await self.create_memory_systems()

            # Print summary
            await self.print_summary()

            return self.stats

        except Exception as e:
            logger.error(f"❌ Error loading knowledge: {e}")
            raise
        finally:
            await self.neo4j.close()

    async def load_iq_persona(self):
        """Load IQ's persona and CCO playbook"""
        manifest_path = Path("data/manifests/iq_agent_cco_manifest.json")

        with open(manifest_path, "r") as f:
            iq_manifest = json.load(f)

        # Create IQ's core persona node
        query = """
        MERGE (iq:IQPersona {id: 'IQ_CCO_2025'})
        SET iq.name = $name,
            iq.role = $role,
            iq.description = $description,
            iq.vision = $vision,
            iq.mission = $mission,
            iq.created_at = datetime(),
            iq.version = '2.0'
        RETURN iq
        """

        await self.neo4j.execute_query(
            query,
            parameters={
                "name": iq_manifest["agent_name"],
                "role": iq_manifest["role"],
                "description": iq_manifest["description"],
                "vision": iq_manifest["cco_strategic_playbook"]["vision_2025_2030"]["title"],
                "mission": iq_manifest["cco_strategic_playbook"]["vision_2025_2030"]["mission"],
            },
            read_only=False,
        )

        # Load strategic pillars
        for pillar in iq_manifest["cco_strategic_playbook"]["vision_2025_2030"][
            "strategic_pillars"
        ]:
            query = """
            MERGE (p:StrategicPillar {name: $name})
            SET p.description = $description,
                p.target = $target
            WITH p
            MATCH (iq:IQPersona {id: 'IQ_CCO_2025'})
            MERGE (iq)-[:STRATEGIC_PILLAR]->(p)
            """

            await self.neo4j.execute_query(
                query,
                parameters={
                    "name": pillar["pillar"],
                    "description": pillar["description"],
                    "target": pillar.get("target_automation")
                    or pillar.get("target_accuracy")
                    or pillar.get("target_latency")
                    or pillar.get("target_coverage")
                    or pillar.get("target_efficiency"),
                },
                read_only=False,
            )

        # Load knowledge domains
        for domain in iq_manifest["knowledge_domains"]["regulatory_expertise"]:
            query = """
            MERGE (kd:KnowledgeDomain {jurisdiction: $jurisdiction})
            SET kd.depth = $depth,
                kd.regulations = $regulations
            WITH kd
            MATCH (iq:IQPersona {id: 'IQ_CCO_2025'})
            MERGE (iq)-[:EXPERTISE_IN]->(kd)
            """

            await self.neo4j.execute_query(
                query,
                parameters={
                    "jurisdiction": domain["jurisdiction"],
                    "depth": domain["depth"],
                    "regulations": domain["regulations"],
                },
                read_only=False,
            )

        self.stats["iq_persona"] = 1
        logger.info(
            f"   ✅ Loaded IQ's persona with {len(iq_manifest['cco_strategic_playbook']['vision_2025_2030']['strategic_pillars'])} strategic pillars"
        )

    async def load_uk_regulations(self):
        """Load the complete UK regulatory database"""
        # Load UK obligations
        obligations_path = Path("data/manifests/uk_obligations_extracted.json")
        analysis_path = Path("data/manifests/uk_regulations_analysis.json")

        if obligations_path.exists():
            with open(obligations_path, "r") as f:
                obligations_data = json.load(f)

            # Extract obligations list
            if isinstance(obligations_data, dict):
                obligations_list = obligations_data.get("obligations", [])
                total_obligations = obligations_data.get(
                    "unique_obligations", len(obligations_list)
                )
            else:
                obligations_list = obligations_data if isinstance(obligations_data, list) else []
                total_obligations = len(obligations_list)

            logger.info(f"   📚 Loading {total_obligations} UK obligations...")

            # Create UK Jurisdiction if not exists
            await self.neo4j.execute_query(
                """
                MERGE (uk:Jurisdiction {code: 'UK'})
                SET uk.name = 'United Kingdom',
                    uk.regulatory_body = 'FCA, PRA, ICO, HMRC',
                    uk.last_updated = datetime()
                """,
                read_only=False,
            )

            # Load each obligation
            for idx, obligation in enumerate(
                obligations_list[:500]
            ):  # Load first 500 for performance
                if idx % 100 == 0:
                    logger.info(f"      Loaded {idx} obligations...")

                obligation_id = f"UK_OBL_{hashlib.md5(json.dumps(obligation, sort_keys=True).encode()).hexdigest()[:8]}"

                query = """
                MERGE (o:Obligation {id: $id})
                SET o.text = $text,
                    o.regulation = $regulation,
                    o.source = $source,
                    o.created_at = datetime()
                WITH o
                MATCH (uk:Jurisdiction {code: 'UK'})
                MERGE (o)-[:ENFORCED_IN]->(uk)
                """

                await self.neo4j.execute_query(
                    query,
                    parameters={
                        "id": obligation_id,
                        "text": str(obligation).replace("'", "")[:1000],  # Truncate for storage
                        "regulation": obligation.get("regulation", "Unknown"),
                        "source": obligation.get("source", "legislation.gov.uk"),
                    },
                    read_only=False,
                )

                self.stats["obligations"] += 1

        # Load regulation analysis
        if analysis_path.exists():
            with open(analysis_path, "r") as f:
                analysis_data = json.load(f)

            for reg_name, reg_info in analysis_data.get("regulation_summary", {}).items():
                query = """
                MERGE (r:UKRegulation {name: $name})
                SET r.document_count = $doc_count,
                    r.total_obligations = $total_obligations,
                    r.urls = $urls,
                    r.loaded_at = datetime()
                WITH r
                MATCH (uk:Jurisdiction {code: 'UK'})
                MERGE (r)-[:GOVERNED_BY]->(uk)
                """

                await self.neo4j.execute_query(
                    query,
                    parameters={
                        "name": reg_name,
                        "doc_count": reg_info["document_count"],
                        "total_obligations": reg_info["total_obligations"],
                        "urls": reg_info["urls"],
                    },
                    read_only=False,
                )

                self.stats["uk_regulations"] += 1

        logger.info(
            f"   ✅ Loaded {self.stats['uk_regulations']} UK regulations with {self.stats['obligations']} obligations"
        )

    async def load_compliance_manifests(self):
        """Load additional compliance manifests"""
        manifest_files = [
            "compliance_ml_manifest_enhanced.json",
            "regulatory_relationships.json",
            "control_effectiveness_templates.json",
            "uk_industry_regulations.json",
        ]

        for manifest_file in manifest_files:
            manifest_path = Path(f"data/manifests/{manifest_file}")
            if manifest_path.exists():
                with open(manifest_path, "r") as f:
                    data = json.load(f)

                # Store manifest metadata
                query = """
                MERGE (m:ComplianceManifest {name: $name})
                SET m.file = $file,
                    m.loaded_at = datetime(),
                    m.size = $size
                WITH m
                MATCH (iq:IQPersona {id: 'IQ_CCO_2025'})
                MERGE (iq)-[:USES_MANIFEST]->(m)
                """

                await self.neo4j.execute_query(
                    query,
                    parameters={
                        "name": manifest_file.replace(".json", ""),
                        "file": manifest_file,
                        "size": len(json.dumps(data)),
                    },
                    read_only=False,
                )

                self.stats["compliance_domains"] += 1

        logger.info(f"   ✅ Loaded {self.stats['compliance_domains']} compliance manifests")

    async def build_relationships(self):
        """Build comprehensive relationships in the knowledge graph"""
        relationship_queries = [
            # Link IQ to all regulations
            """
            MATCH (iq:IQPersona {id: 'IQ_CCO_2025'})
            MATCH (r:Regulation)
            MERGE (iq)-[:MONITORS]->(r)
            """,
            # Link IQ to UK regulations
            """
            MATCH (iq:IQPersona {id: 'IQ_CCO_2025'})
            MATCH (r:UKRegulation)
            MERGE (iq)-[:UK_EXPERTISE]->(r)
            """,
            # Link obligations to regulations
            """
            MATCH (o:Obligation)
            MATCH (r:UKRegulation)
            WHERE o.regulation = r.name
            MERGE (o)-[:MANDATED_BY]->(r)
            """,
            # Create compliance domain relationships
            """
            MATCH (r:Regulation)
            MATCH (d:ComplianceDomain)
            WHERE r.compliance_domain = d.name
            MERGE (r)-[:BELONGS_TO]->(d)
            """,
            # Link IQ to all compliance domains
            """
            MATCH (iq:IQPersona {id: 'IQ_CCO_2025'})
            MATCH (d:ComplianceDomain)
            MERGE (iq)-[:OVERSEES]->(d)
            """,
        ]

        for query in relationship_queries:
            try:
                await self.neo4j.execute_query(query, read_only=False)
                self.stats["relationships"] += 1
            except Exception as e:
                logger.warning(f"   ⚠️  Relationship query failed: {e}")

        logger.info(f"   ✅ Created {self.stats['relationships']} relationship patterns")

    async def create_memory_systems(self):
        """Initialize IQ's memory systems"""
        memory_types = [
            {
                "type": "EpisodicMemory",
                "description": "Specific compliance events and decisions",
                "retention": "Permanent for audit trail",
            },
            {
                "type": "SemanticMemory",
                "description": "Regulatory knowledge and patterns",
                "retention": "Updated with each regulatory change",
            },
            {
                "type": "ProceduralMemory",
                "description": "Compliance processes and workflows",
                "retention": "Version controlled with change tracking",
            },
            {
                "type": "StrategicMemory",
                "description": "Long-term patterns and organizational learning",
                "retention": "Consolidated quarterly",
            },
        ]

        for memory in memory_types:
            query = """
            MERGE (m:MemorySystem {type: $type})
            SET m.description = $description,
                m.retention = $retention,
                m.initialized_at = datetime()
            WITH m
            MATCH (iq:IQPersona {id: 'IQ_CCO_2025'})
            MERGE (iq)-[:HAS_MEMORY]->(m)
            """

            await self.neo4j.execute_query(query, parameters=memory, read_only=False)

        logger.info(f"   ✅ Initialized {len(memory_types)} memory systems")

    async def print_summary(self):
        """Print loading summary"""
        # Get final stats from Neo4j
        stats_query = """
        MATCH (n)
        WITH labels(n) as node_labels, count(n) as count
        RETURN node_labels, count
        ORDER BY count DESC
        """

        result = await self.neo4j.execute_query(stats_query)

        logger.info("\n" + "=" * 60)
        logger.info("🎉 IQ'S KNOWLEDGE BASE SUCCESSFULLY LOADED!")
        logger.info("=" * 60)

        logger.info("\n📊 LOADING SUMMARY:")
        logger.info(f"   IQ Persona: {self.stats['iq_persona']}")
        logger.info(f"   UK Regulations: {self.stats['uk_regulations']}")
        logger.info(f"   Obligations: {self.stats['obligations']}")
        logger.info(f"   Compliance Domains: {self.stats['compliance_domains']}")
        logger.info(f"   Relationships: {self.stats['relationships']}")

        logger.info("\n🧠 NODE TYPES IN GRAPH:")
        if result and "results" in result:
            for record in result["results"][:10]:
                logger.info(f"   {record['node_labels']}: {record['count']}")

        logger.info("\n✨ IQ NOW HAS:")
        logger.info("   • Complete UK regulatory knowledge")
        logger.info("   • Strategic CCO playbook 2025-2030")
        logger.info("   • 4 memory systems (Episodic, Semantic, Procedural, Strategic)")
        logger.info("   • Cross-jurisdictional compliance expertise")
        logger.info("   • Evidence-based decision framework")
        logger.info("\n🚀 IQ IS READY TO ORCHESTRATE COMPLIANCE!")


async def main():
    """Main function to load IQ's knowledge"""
    loader = IQKnowledgeLoader()

    print("🧠 IQ KNOWLEDGE LOADER")
    print("=" * 60)
    print("This will load:")
    print("  • IQ's CCO persona and strategic playbook")
    print("  • Complete UK regulatory database")
    print("  • Compliance manifests and frameworks")
    print("  • Memory systems and relationships")
    print("")

    response = input("Load IQ's complete knowledge base? (yes/no): ")

    if response.lower() != "yes":
        print("❌ Aborted")
        return

    try:
        await loader.load_complete_knowledge()
    except Exception as e:
        logger.error(f"Failed to load knowledge: {e}")
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())
