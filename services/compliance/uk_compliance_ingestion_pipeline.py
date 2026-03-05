"""
from __future__ import annotations

UK Compliance Data Ingestion Pipeline for Neo4j Knowledge Graph
Ingests all 108 UK regulatory documents and compliance manifest into graph
"""
import asyncio
import json
import logging
from typing import Dict, List, Optional, Any
from pathlib import Path
import hashlib
from neo4j import AsyncGraphDatabase
import PyPDF2
from langchain.text_splitter import RecursiveCharacterTextSplitter
logger = logging.getLogger(__name__)


class UKComplianceGraphIngestion:
    """
    Ingests UK compliance data into Neo4j knowledge graph
    Handles all 108 regulatory documents + manifest structure
    """

    def __init__(self, neo4j_uri: str, neo4j_auth: tuple, embedding_model=None
        ) -> None:
        self.driver = AsyncGraphDatabase.driver(neo4j_uri, auth=neo4j_auth)
        self.embedding_model = embedding_model
        self.text_splitter = RecursiveCharacterTextSplitter(chunk_size=1000,
            chunk_overlap=200, separators=['\n\n', '\n', '. ', ' ', ''])
        self.ingestion_stats = {'regulations_processed': 0,
            'obligations_created': 0, 'controls_created': 0,
            'relationships_created': 0, 'documents_processed': 0,
            'chunks_created': 0}

    async def ingest_complete_uk_compliance(self) ->Any:
        """
        Main ingestion pipeline for all UK compliance data
        """
        logger.info('Starting UK compliance graph ingestion...')
        try:
            await self._create_graph_schema()
            await self._ingest_compliance_manifest()
            await self._ingest_api_documents()
            await self._ingest_data_protection_act()
            await self._create_cross_regulation_relationships()
            await self._generate_embeddings()
            await self._create_graph_indexes()
            logger.info('Ingestion complete. Stats: %s' % self.ingestion_stats)
            return self.ingestion_stats
        except Exception as e:
            logger.error('Ingestion failed: %s' % str(e))
            raise

    async def _create_graph_schema(self):
        """Create Neo4j schema and constraints"""
        async with self.driver.session() as session:
            constraints = [
                'CREATE CONSTRAINT regulation_id IF NOT EXISTS FOR (r:Regulation) REQUIRE r.id IS UNIQUE'
                ,
                'CREATE CONSTRAINT obligation_id IF NOT EXISTS FOR (o:Obligation) REQUIRE o.id IS UNIQUE'
                ,
                'CREATE CONSTRAINT control_id IF NOT EXISTS FOR (c:Control) REQUIRE c.id IS UNIQUE'
                ,
                'CREATE CONSTRAINT document_id IF NOT EXISTS FOR (d:Document) REQUIRE d.id IS UNIQUE'
                ,
                'CREATE CONSTRAINT organization_id IF NOT EXISTS FOR (org:Organization) REQUIRE org.id IS UNIQUE'
                ,
                'CREATE CONSTRAINT enforcement_id IF NOT EXISTS FOR (e:Enforcement) REQUIRE e.id IS UNIQUE'
                ,
                'CREATE CONSTRAINT risk_id IF NOT EXISTS FOR (r:Risk) REQUIRE r.id IS UNIQUE',
                ]
            for constraint in constraints:
                try:
                    await session.run(constraint)
                    logger.info('Created constraint: %s...' % constraint[:50])
                except Exception as e:
                    logger.warning('Constraint may already exist: %s' % e)

    async def _ingest_compliance_manifest(self):
        """Ingest the UK compliance manifest structure"""
        manifest_path = Path('data/manifests/uk_compliance_manifest.json')
        with open(manifest_path, 'r') as f:
            manifest = json.load(f)
        async with self.driver.session() as session:
            await session.run(
                """
                MERGE (j:Jurisdiction {id: 'UK'})
                SET j.name = 'United Kingdom',
                    j.iso_code = 'GB',
                    j.updated = datetime(),
                    j.total_regulations = $total_regs
            """
                , total_regs=len(manifest['regulations']))
            for reg_id, regulation in manifest['regulations'].items():
                await self._ingest_regulation(session, reg_id, regulation)
            for mapping in manifest.get('cross_regulation_mappings', []):
                await self._create_mapping_relationship(session, mapping)

    async def _ingest_regulation(self, session, reg_id: str, regulation: Dict):
        """Ingest a single regulation with all its components"""
        await session.run(
            """
            MERGE (r:Regulation {id: $reg_id})
            SET r.title = $title,
                r.short_name = $short_name,
                r.effective_date = $effective_date,
                r.authority = $authority,
                r.jurisdiction = 'UK',
                r.updated = datetime()
            WITH r
            MATCH (j:Jurisdiction {id: 'UK'})
            MERGE (j)-[:GOVERNS]->(r)
        """
            , reg_id=reg_id, title=regulation.get('title'), short_name=
            regulation.get('short_name'), effective_date=regulation.get(
            'effective_date'), authority=regulation.get('authority'))
        self.ingestion_stats['regulations_processed'] += 1
        if 'chapters' in regulation:
            await self._process_chapters(session, reg_id, regulation[
                'chapters'])
        elif 'components' in regulation:
            await self._process_components(session, reg_id, regulation[
                'components'])
        elif 'parts' in regulation:
            await self._process_parts(session, reg_id, regulation['parts'])
        elif 'obligations' in regulation:
            await self._process_obligations(session, reg_id, regulation[
                'obligations'])

    async def _process_chapters(self, session, reg_id: str, chapters: List[
        Dict]):
        """Process GDPR-style chapters and articles"""
        for chapter in chapters:
            chapter_id = f"{reg_id}_{chapter['chapter_id']}"
            await session.run(
                """
                MERGE (ch:Chapter {id: $chapter_id})
                SET ch.title = $title,
                    ch.regulation_id = $reg_id
                WITH ch
                MATCH (r:Regulation {id: $reg_id})
                MERGE (r)-[:CONTAINS]->(ch)
            """
                , chapter_id=chapter_id, title=chapter['title'], reg_id=reg_id)
            for article in chapter.get('articles', []):
                article_id = f"{chapter_id}_{article['article_id']}"
                await session.run(
                    """
                    MERGE (a:Article {id: $article_id})
                    SET a.title = $title,
                        a.number = $number
                    WITH a
                    MATCH (ch:Chapter {id: $chapter_id})
                    MERGE (ch)-[:CONTAINS]->(a)
                """
                    , article_id=article_id, title=article['title'], number
                    =article['article_id'], chapter_id=chapter_id)
                for obligation in article.get('obligations', []):
                    await self._create_obligation_node(session, obligation,
                        article_id)

    async def _process_components(self, session, reg_id: str, components: Dict
        ):
        """Process FCA-style components"""
        for comp_id, component in components.items():
            component_full_id = f'{reg_id}_{comp_id}'
            await session.run(
                """
                MERGE (c:Component {id: $comp_id})
                SET c.title = $title,
                    c.effective_date = $effective_date,
                    c.regulation_id = $reg_id
                WITH c
                MATCH (r:Regulation {id: $reg_id})
                MERGE (r)-[:CONTAINS]->(c)
            """
                , comp_id=component_full_id, title=component.get('title'),
                effective_date=component.get('effective_date'), reg_id=reg_id)
            for obligation in component.get('obligations', []):
                await self._create_obligation_node(session, obligation,
                    component_full_id)

    async def _process_parts(self, session, reg_id: str, parts: List[Dict]):
        """Process DPA-style parts"""
        for part in parts:
            part_id = f"{reg_id}_{part['part_id']}"
            await session.run(
                """
                MERGE (p:Part {id: $part_id})
                SET p.title = $title,
                    p.regulation_id = $reg_id
                WITH p
                MATCH (r:Regulation {id: $reg_id})
                MERGE (r)-[:CONTAINS]->(p)
            """
                , part_id=part_id, title=part['title'], reg_id=reg_id)
            for obligation in part.get('obligations', []):
                await self._create_obligation_node(session, obligation, part_id,
                    )

    async def _process_obligations(self, session, reg_id: str, obligations:
        List[Dict]):
        """Process direct obligations"""
        for obligation in obligations:
            await self._create_obligation_node(session, obligation, reg_id)

    async def _create_obligation_node(self, session, obligation: Dict,
        parent_id: str):
        """Create an Obligation node with all its relationships"""
        ob_id = obligation['obligation_id']
        await session.run(
            """
            MERGE (o:Obligation {id: $ob_id})
            SET o.description = $description,
                o.requirement_type = $req_type,
                o.timeline = $timeline,
                o.applicable_to = $applicable_to,
                o.verification_criteria = $verification,
                o.created = datetime()
        """
            , ob_id=ob_id, description=obligation.get('description'),
            req_type=obligation.get('requirement_type', 'mandatory'),
            timeline=obligation.get('timeline'), applicable_to=obligation.
            get('applicable_to', []), verification=obligation.get(
            'verification_criteria', []))
        await session.run(
            """
            MATCH (o:Obligation {id: $ob_id})
            MATCH (p) WHERE p.id = $parent_id
            MERGE (p)-[:CONTAINS]->(o)
        """
            , ob_id=ob_id, parent_id=parent_id)
        self.ingestion_stats['obligations_created'] += 1
        for control in obligation.get('controls', []):
            await self._create_control_node(session, control, ob_id)
        if 'penalties' in obligation:
            await self._create_penalty_node(session, obligation['penalties'
                ], ob_id)

    async def _create_control_node(self, session, control: str,
        obligation_id: str):
        """Create a Control node and link to obligation"""
        control_id = f'CTRL_{hashlib.md5(control.encode(), usedforsecurity=False).hexdigest()[:8]}'
        await session.run(
            """
            MERGE (c:Control {id: $control_id})
            SET c.description = $description,
                c.type = $control_type,
                c.created = datetime()
            WITH c
            MATCH (o:Obligation {id: $ob_id})
            MERGE (o)-[:REQUIRES]->(c)
        """
            , control_id=control_id, description=control, control_type=
            'preventive', ob_id=obligation_id)
        self.ingestion_stats['controls_created'] += 1

    async def _create_penalty_node(self, session, penalties: Dict,
        obligation_id: str):
        """Create Penalty node for non-compliance"""
        penalty_id = f'PEN_{obligation_id}'
        await session.run(
            """
            MERGE (p:Penalty {id: $penalty_id})
            SET p.description = $description,
                p.max_amount = $max_amount,
                p.calculation_method = $method,
                p.created = datetime()
            WITH p
            MATCH (o:Obligation {id: $ob_id})
            MERGE (o)-[:HAS_PENALTY]->(p)
        """
            , penalty_id=penalty_id, description=penalties.get(
            'description'), max_amount=penalties.get('max_amount'), method=
            penalties.get('calculation_method'), ob_id=obligation_id)

    async def _ingest_api_documents(self):
        """Ingest 108 API-sourced regulatory documents"""
        api_docs_path = Path('data/api_documents')
        for doc_path in api_docs_path.glob('*.json'):
            try:
                with open(doc_path, 'r') as f:
                    doc_data = json.load(f)
                await self._ingest_document(doc_data, source='API')
                self.ingestion_stats['documents_processed'] += 1
            except Exception as e:
                logger.error('Failed to ingest %s: %s' % (doc_path, e))

    async def _ingest_data_protection_act(self):
        """Ingest UK Data Protection Act PDF"""
        pdf_path = Path(
            '/media/omar/1234-5678/Regulation/UK Data Protection/UKdataprotectionact.pdf',
            )
        if not pdf_path.exists():
            logger.warning('PDF not found at %s' % pdf_path)
            return
        try:
            text_content = self._extract_pdf_text(pdf_path)
            chunks = self.text_splitter.split_text(text_content)
            async with self.driver.session() as session:
                doc_id = 'UK_DPA_2018_FULL'
                await session.run(
                    """
                    MERGE (d:Document {id: $doc_id})
                    SET d.title = 'UK Data Protection Act 2018',
                        d.source = $source,
                        d.path = $path,
                        d.type = 'primary_legislation',
                        d.chunk_count = $chunks,
                        d.created = datetime()
                    WITH d
                    MATCH (r:Regulation {id: 'DATA_PROTECTION_ACT'})
                    MERGE (r)-[:DOCUMENTED_IN]->(d)
                """
                    , doc_id=doc_id, source='PDF', path=str(pdf_path),
                    chunks=len(chunks))
                for i, chunk in enumerate(chunks):
                    chunk_id = f'{doc_id}_chunk_{i}'
                    embedding = None
                    if self.embedding_model:
                        embedding = await self._generate_embedding(chunk)
                    await session.run(
                        """
                        MERGE (ch:Chunk {id: $chunk_id})
                        SET ch.content = $content,
                            ch.sequence = $seq,
                            ch.embedding = $embedding,
                            ch.created = datetime()
                        WITH ch
                        MATCH (d:Document {id: $doc_id})
                        MERGE (d)-[:CONTAINS_CHUNK]->(ch)
                    """
                        , chunk_id=chunk_id, content=chunk, seq=i,
                        embedding=embedding, doc_id=doc_id)
                    self.ingestion_stats['chunks_created'] += 1
            self.ingestion_stats['documents_processed'] += 1
            logger.info('Ingested UK DPA PDF with %s chunks' % len(chunks))
        except Exception as e:
            logger.error('Failed to ingest PDF: %s' % e)

    def _extract_pdf_text(self, pdf_path: Path) ->str:
        """Extract text from PDF file"""
        text = ''
        try:
            with open(pdf_path, 'rb') as file:
                pdf_reader = PyPDF2.PdfReader(file)
                for page in pdf_reader.pages:
                    text += page.extract_text()
        except Exception as e:
            logger.error('PDF extraction error: %s' % e)
        return text

    async def _ingest_document(self, doc_data: Dict, source: str):
        """Ingest a single document into the graph"""
        async with self.driver.session() as session:
            doc_id = doc_data.get('id', hashlib.md5(json.dumps(doc_data).
                encode(), usedforsecurity=False).hexdigest())
            await session.run(
                """
                MERGE (d:Document {id: $doc_id})
                SET d.title = $title,
                    d.source = $source,
                    d.url = $url,
                    d.content = $content,
                    d.regulation_ref = $reg_ref,
                    d.created = datetime()
            """
                , doc_id=doc_id, title=doc_data.get('title'), source=source,
                url=doc_data.get('url'), content=doc_data.get('content', ''
                )[:5000], reg_ref=doc_data.get('regulation'))
            if doc_data.get('regulation'):
                await session.run(
                    """
                    MATCH (d:Document {id: $doc_id})
                    MATCH (r:Regulation {id: $reg_id})
                    MERGE (r)-[:DOCUMENTED_IN]->(d)
                """
                    , doc_id=doc_id, reg_id=doc_data['regulation'])

    async def _create_cross_regulation_relationships(self):
        """Create relationships between related regulations"""
        async with self.driver.session() as session:
            await session.run(
                """
                MATCH (gdpr:Regulation {id: 'UK_GDPR'})
                MATCH (dpa:Regulation {id: 'DATA_PROTECTION_ACT'})
                MERGE (gdpr)-[:COMPLEMENTED_BY]->(dpa)
                MERGE (dpa)-[:COMPLEMENTS]->(gdpr)
            """,
                )
            await session.run(
                """
                MATCH (gdpr:Regulation {id: 'UK_GDPR'})
                MATCH (pecr:Regulation {id: 'PECR'})
                MERGE (gdpr)-[:OVERLAPS_WITH]->(pecr)
                MERGE (pecr)-[:OVERLAPS_WITH]->(gdpr)
            """,
                )
            await session.run(
                """
                MATCH (fca:Regulation {id: 'FCA_REGULATIONS'})
                MATCH (mlr:Regulation {id: 'MONEY_LAUNDERING_REGULATIONS'})
                MERGE (fca)-[:ALIGNED_WITH]->(mlr)
                MERGE (mlr)-[:ALIGNED_WITH]->(fca)
            """,
                )
            self.ingestion_stats['relationships_created'] += 3

    async def _generate_embedding(self, text: str) ->Optional[List[float]]:
        """Generate embedding for text using embedding model"""
        if not self.embedding_model:
            return None
        try:
            embedding = await self.embedding_model.aembed_query(text)
            return embedding
        except Exception as e:
            logger.error('Embedding generation failed: %s' % e)
            return None

    async def _generate_embeddings(self):
        """Generate embeddings for all obligations and controls"""
        if not self.embedding_model:
            logger.info('No embedding model configured, skipping embeddings')
            return
        async with self.driver.session() as session:
            result = await session.run(
                """
                MATCH (o:Obligation)
                WHERE o.embedding IS NULL
                RETURN o.id as id, o.description as text
                LIMIT 1000
            """,
                )
            obligations = await result.values()
            for ob_id, text in obligations:
                if text:
                    embedding = await self._generate_embedding(text)
                    if embedding:
                        await session.run(
                            """
                            MATCH (o:Obligation {id: $id})
                            SET o.embedding = $embedding
                        """
                            , id=ob_id, embedding=embedding)
            logger.info('Generated embeddings for %s obligations' % len(
                obligations))

    async def _create_graph_indexes(self):
        """Create indexes for query performance"""
        async with self.driver.session() as session:
            indexes = [
                'CREATE INDEX regulation_title IF NOT EXISTS FOR (r:Regulation) ON (r.title)'
                ,
                'CREATE INDEX obligation_desc IF NOT EXISTS FOR (o:Obligation) ON (o.description)'
                ,
                'CREATE INDEX control_desc IF NOT EXISTS FOR (c:Control) ON (c.description)'
                ,
                'CREATE INDEX document_title IF NOT EXISTS FOR (d:Document) ON (d.title)'
                ,
                'CREATE INDEX chunk_content IF NOT EXISTS FOR (ch:Chunk) ON (ch.content)'
                ,
                "CREATE VECTOR INDEX obligation_embedding IF NOT EXISTS FOR (o:Obligation) ON (o.embedding) OPTIONS {indexConfig: {`vector.dimensions`: 1536, `vector.similarity_function`: 'cosine'}}",
                ]
            for index in indexes:
                try:
                    await session.run(index)
                    logger.info('Created index: %s...' % index[:50])
                except Exception as e:
                    logger.warning('Index may already exist: %s' % e)

    async def verify_ingestion(self) ->Dict[str, Any]:
        """Verify the ingestion was successful"""
        async with self.driver.session() as session:
            node_counts = {}
            node_types = ['Regulation', 'Obligation', 'Control', 'Document',
                'Chunk', 'Penalty']
            for node_type in node_types:
                result = await session.run(
                    f'MATCH (n:{node_type}) RETURN count(n) as count')
                count = await result.single()
                node_counts[node_type] = count['count']
            result = await session.run(
                'MATCH ()-[r]->() RETURN count(r) as count')
            rel_count = await result.single()
            result = await session.run(
                """
                MATCH path = (j:Jurisdiction)-[:GOVERNS]->(r:Regulation)-[:CONTAINS]->(o:Obligation)
                RETURN count(path) as paths
                LIMIT 10
            """,
                )
            path_count = await result.single()
            return {'node_counts': node_counts, 'total_relationships':
                rel_count['count'], 'sample_paths': path_count['paths'],
                'ingestion_stats': self.ingestion_stats}

    async def close(self) ->None:
        """Close Neo4j driver connection"""
        await self.driver.close()


class UKComplianceGraphQuery:
    """Query helper for UK compliance graph"""

    def __init__(self, neo4j_uri: str, neo4j_auth: tuple) -> None:
        self.driver = AsyncGraphDatabase.driver(neo4j_uri, auth=neo4j_auth)

    async def find_obligations_by_regulation(self, regulation_id: str) ->List[
        Dict]:
        """Find all obligations for a regulation"""
        async with self.driver.session() as session:
            result = await session.run(
                """
                MATCH (r:Regulation {id: $reg_id})-[:CONTAINS*]->(o:Obligation)
                OPTIONAL MATCH (o)-[:REQUIRES]->(c:Control)
                RETURN o, collect(c) as controls
            """
                , reg_id=regulation_id)
            records = []
            async for record in result:
                records.append({'obligation': dict(record['o']), 'controls':
                    [dict(c) for c in record['controls']]})
            return records

    async def find_cross_regulation_obligations(self, topic: str) ->List[Dict]:
        """Find obligations across regulations for a topic"""
        async with self.driver.session() as session:
            result = await session.run(
                """
                MATCH (o:Obligation)
                WHERE o.description CONTAINS $topic
                MATCH (r:Regulation)-[:CONTAINS*]->(o)
                OPTIONAL MATCH (o)-[:REQUIRES]->(c:Control)
                RETURN r.id as regulation, o, collect(c) as controls
                ORDER BY r.id
            """
                , topic=topic)
            records = []
            async for record in result:
                records.append({'regulation': record['regulation'],
                    'obligation': dict(record['o']), 'controls': [dict(c) for
                    c in record['controls']]})
            return records

    async def find_similar_obligations(self, obligation_id: str, limit: int=5
        ) ->List[Dict]:
        """Find similar obligations using vector similarity (if embeddings exist)"""
        async with self.driver.session() as session:
            result = await session.run(
                """
                MATCH (o1:Obligation {id: $ob_id})
                WHERE o1.embedding IS NOT NULL
                MATCH (o2:Obligation)
                WHERE o2.id <> o1.id AND o2.embedding IS NOT NULL
                WITH o1, o2,
                     gds.similarity.cosine(o1.embedding, o2.embedding) as similarity
                WHERE similarity > 0.7
                RETURN o2, similarity
                ORDER BY similarity DESC
                LIMIT $limit
            """
                , ob_id=obligation_id, limit=limit)
            records = []
            async for record in result:
                records.append({'obligation': dict(record['o2']),
                    'similarity': record['similarity']})
            if not records:
                result = await session.run(
                    """
                    MATCH (o1:Obligation {id: $ob_id})
                    MATCH (o2:Obligation)
                    WHERE o2.id <> o1.id
                    AND o2.description CONTAINS substring(o1.description, 0, 20)
                    RETURN o2, 0.5 as similarity
                    LIMIT $limit
                """
                    , ob_id=obligation_id, limit=limit)
                async for record in result:
                    records.append({'obligation': dict(record['o2']),
                        'similarity': record['similarity']})
            return records

    async def close(self) ->None:
        """Close driver connection"""
        await self.driver.close()


async def main() ->None:
    """Execute the UK compliance ingestion pipeline"""
    NEO4J_URI = 'bolt://localhost:7687'
    NEO4J_AUTH = 'neo4j', 'your_password'
    ingestion = UKComplianceGraphIngestion(NEO4J_URI, NEO4J_AUTH)
    try:
        stats = await ingestion.ingest_complete_uk_compliance()
        logger.info('Ingestion completed successfully: %s' % stats)
        verification = await ingestion.verify_ingestion()
        logger.info('Verification results: %s' % verification)
    finally:
        await ingestion.close()


if __name__ == '__main__':
    asyncio.run(main())
