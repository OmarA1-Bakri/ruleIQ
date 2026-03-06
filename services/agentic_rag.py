"""

# Constants
DEFAULT_LIMIT = 100


Custom Agentic RAG System for ruleIQ
Integrates LangGraph and Pydantic AI documentation with knowledge graph capabilities
"""

import os
import json
import logging
from typing import Dict, Any, List, Optional
from pathlib import Path
from datetime import datetime
import openai
from mistralai import Mistral
from pydantic import BaseModel
from sqlalchemy import create_engine, text
import redis
from neo4j import GraphDatabase
from supabase import create_client, Client

logger = logging.getLogger(__name__)


class DocumentChunk(BaseModel):
    """Document chunk for vector storage"""

    id: str
    content: str
    metadata: Dict[str, Any]
    embedding: Optional[List[float]] = None
    source: str
    chunk_type: str = "documentation"


class AgenticRAGResponse(BaseModel):
    """Response from RAG query"""

    answer: str
    sources: List[Dict[str, Any]]
    confidence: float
    chunks_used: List[str]
    query_type: str
    processing_time: float


class AgenticRAGSystem:
    """
    Custom Agentic RAG System for ruleIQ

    Features:
    - LangGraph documentation processing
    - Pydantic AI documentation integration
    - Knowledge graph for code understanding
    - Multi-modal RAG (text + code)
    - Context-aware embeddings
    - Hybrid search capabilities
    """

    def __init__(self) -> None:
        supabase_url = os.getenv("SUPABASE_URL")
        supabase_key = os.getenv("SUPABASE_SERVICE_KEY")
        if not supabase_url or not supabase_key:
            raise ValueError(
                "SUPABASE_URL and SUPABASE_SERVICE_KEY environment variables must be set"
            )
        self.supabase: Client = create_client(supabase_url, supabase_key)
        postgres_password = os.getenv("POSTGRES_PASSWORD")
        if postgres_password:
            postgres_url = (
                f"postgresql://postgres:{postgres_password}@db.gaqkmdexddnmwzenrjrv.supabase.co:5432/postgres",
            )
        else:
            raise ValueError(
                "POSTGRES_PASSWORD environment variable must be set for Supabase connection"
            )
        self.engine = create_engine(postgres_url)
        self.redis_client = redis.Redis(
            host=os.getenv("REDIS_HOST", "localhost"),
            port=int(os.getenv("REDIS_PORT", 6379)),
            decode_responses=True,
        )
        self.neo4j_driver = None
        if os.getenv("NEO4J_URI"):
            neo4j_uri = os.getenv("NEO4J_URI")
            neo4j_user = os.getenv("NEO4J_USER")
            neo4j_password = os.getenv("NEO4J_PASSWORD")

            if not neo4j_uri or not neo4j_user or not neo4j_password:
                logger.warning("Neo4j credentials not configured. Neo4j features disabled.")
                self.neo4j_driver = None
            else:
                self.neo4j_driver = GraphDatabase.driver(
                    neo4j_uri, auth=(neo4j_user, neo4j_password)
                )
        mistral_api_key = os.getenv("MISTRAL_API_KEY")
        if mistral_api_key:
            self.mistral_client = Mistral(api_key=mistral_api_key)
            self.use_mistral_embeddings = True
        else:
            self.mistral_client = None
            self.use_mistral_embeddings = False
        openai_api_key = os.getenv("OPENAI_API_KEY")
        if openai_api_key:
            self.openai_client = openai.OpenAI(api_key=openai_api_key)
        else:
            self.openai_client = None
        self.embedding_model = (
            "mistral-embed" if self.use_mistral_embeddings else "text-embedding-3-small"
        )
        self.llm_model = "gpt-4o-mini"
        self.use_contextual_embeddings = (
            os.getenv("USE_CONTEXTUAL_EMBEDDINGS", "true").lower() == "true"
        )
        self.use_hybrid_search = os.getenv("USE_HYBRID_SEARCH", "true").lower() == "true"
        self.use_agentic_rag = os.getenv("USE_AGENTIC_RAG", "true").lower() == "true"
        self.use_knowledge_graph = os.getenv("USE_KNOWLEDGE_GRAPH", "false").lower() == "true"
        self._initialize_database()

    def _initialize_database(self) -> None:
        """Initialize the vector database schema"""
        try:
            with self.engine.connect() as conn:
                conn.execute(text("CREATE EXTENSION IF NOT EXISTS vector"))
                embedding_dim = 1024 if self.use_mistral_embeddings else 1536
                try:
                    result = conn.execute(
                        text(
                            """
                        SELECT column_name, data_type
                        FROM information_schema.columns
                        WHERE table_name = 'documentation_chunks' AND column_name = 'embedding'
                    """
                        )
                    )
                    existing_table = result.fetchone()
                    if existing_table:
                        logger.info("Found existing table with embedding column")
                        conn.execute(text("DROP TABLE IF EXISTS documentation_chunks CASCADE"))
                        conn.execute(text("DROP TABLE IF EXISTS code_examples CASCADE"))
                        logger.info("Recreating tables for %s dimensions" % embedding_dim)
                except Exception as e:
                    logger.info("Table check info: %s" % e)
                conn.execute(
                    text(
                        f"""
                    CREATE TABLE IF NOT EXISTS documentation_chunks (
                        id TEXT PRIMARY KEY,
                        content TEXT NOT NULL,
                        embedding vector({embedding_dim}),
                        metadata JSONB,
                        source TEXT NOT NULL,
                        chunk_type TEXT DEFAULT 'documentation',
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    )
                """
                    )
                )
                conn.execute(
                    text(
                        """
                    CREATE INDEX IF NOT EXISTS documentation_chunks_embedding_idx
                    ON documentation_chunks USING ivfflat (embedding vector_cosine_ops)
                    WITH (lists = 100)
                """
                    )
                )
                conn.execute(
                    text(
                        f"""
                    CREATE TABLE IF NOT EXISTS code_examples (
                        id TEXT PRIMARY KEY,
                        code_content TEXT NOT NULL,
                        summary TEXT NOT NULL,
                        embedding vector({embedding_dim}),
                        metadata JSONB,
                        source TEXT NOT NULL,
                        framework TEXT NOT NULL, -- 'langgraph' or 'pydantic_ai'
                        example_type TEXT, -- 'function', 'class', 'workflow', 'agent'
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    )
                """
                    )
                )
                conn.execute(
                    text(
                        """
                    CREATE INDEX IF NOT EXISTS code_examples_embedding_idx
                    ON code_examples USING ivfflat (embedding vector_cosine_ops)
                    WITH (lists = 100)
                """
                    )
                )
                conn.commit()
                logger.info("Database schema initialized successfully")
        except Exception as e:
            logger.error("Failed to initialize database schema: %s" % e)
            raise

    async def process_documentation_files(self) -> None:
        """Process LangGraph and Pydantic AI documentation files"""
        docs_path = Path("/home/omar/Documents/ruleIQ/docs/DEPENDENCY_DOCUMENTATION")
        langgraph_file = docs_path / "langgraph.md"
        if langgraph_file.exists():
            await self._process_markdown_file(langgraph_file, "langgraph")
        pydantic_file = docs_path / "pydantic.md"
        if pydantic_file.exists():
            await self._process_markdown_file(pydantic_file, "pydantic_ai")

    async def _process_markdown_file(self, file_path: Path, framework: str) -> None:
        """Process a markdown documentation file"""
        try:
            content = file_path.read_text(encoding="utf-8")
            chunks = self._split_markdown_content(content, framework)
            for i, chunk in enumerate(chunks):
                chunk_id = f"{framework}_{file_path.stem}_{i}"
                if self.use_contextual_embeddings:
                    contextual_content = await self._add_contextual_information(
                        chunk["content"], content, framework
                    )
                    embedding = await self._generate_embedding(contextual_content)
                else:
                    embedding = await self._generate_embedding(chunk["content"])
                await self._store_documentation_chunk(
                    chunk_id=chunk_id,
                    content=chunk["content"],
                    embedding=embedding,
                    metadata=chunk["metadata"],
                    source=framework,
                    chunk_type=chunk.get("type", "documentation"),
                )
                if self.use_agentic_rag and "code" in chunk["content"].lower():
                    await self._extract_and_store_code_examples(
                        chunk["content"], framework, chunk_id
                    )
            logger.info("Processed %s chunks from %s" % (len(chunks), file_path))
        except Exception as e:
            logger.error("Failed to process %s: %s" % (file_path, e))
            raise

    def _split_markdown_content(self, content: str, framework: str) -> List[Dict[str, Any]]:
        """Split markdown content into logical chunks"""
        chunks = []
        lines = content.split("\n")
        current_chunk = []
        current_metadata = {"framework": framework, "section": "introduction"}
        for line in lines:
            if line.startswith("#"):
                if current_chunk:
                    chunk_content = "\n".join(current_chunk).strip()
                    if len(chunk_content) > DEFAULT_LIMIT:
                        chunks.append(
                            {
                                "content": chunk_content,
                                "metadata": current_metadata.copy(),
                                "type": self._classify_chunk_type(chunk_content),
                            }
                        )
                current_chunk = [line]
                current_metadata["section"] = line.strip("#").strip().lower()
            else:
                current_chunk.append(line)
            if len("\n".join(current_chunk)) > 2000:
                chunk_content = "\n".join(current_chunk).strip()
                chunks.append(
                    {
                        "content": chunk_content,
                        "metadata": current_metadata.copy(),
                        "type": self._classify_chunk_type(chunk_content),
                    }
                )
                current_chunk = []
        if current_chunk:
            chunk_content = "\n".join(current_chunk).strip()
            if len(chunk_content) > DEFAULT_LIMIT:
                chunks.append(
                    {
                        "content": chunk_content,
                        "metadata": current_metadata.copy(),
                        "type": self._classify_chunk_type(chunk_content),
                    }
                )
        return chunks

    def _classify_chunk_type(self, content: str) -> str:
        """Classify the type of content chunk"""
        content_lower = content.lower()
        if "```" in content and any(
            keyword in content_lower for keyword in ["def ", "class ", "import ", "from "]
        ):
            return "code_example"
        elif "api" in content_lower or "reference" in content_lower:
            return "api_reference"
        elif "example" in content_lower or "tutorial" in content_lower:
            return "tutorial"
        else:
            return "documentation"

    async def _add_contextual_information(
        self, chunk: str, full_document: str, framework: str
    ) -> str:
        """Add contextual information to chunk for better embeddings"""
        try:
            prompt = f"""
            You are analyzing a chunk from {framework} documentation.

            Full document context (first 1000 chars):
            {full_document[:1000]}...

            Current chunk:
            {chunk}

            Provide enriched context for this chunk that would help with semantic search.
            Include relevant technical terms, concepts, and relationships to other parts of the documentation.
            Keep it concise but informative.
            """
            response = await self.openai_client.chat.completions.create(
                model=self.llm_model, messages=[{"role": "user", "content": prompt}], max_tokens=200
            )
            context = response.choices[0].message.content
            return f"{chunk}\n\nContext: {context}"
        except Exception as e:
            logger.warning("Failed to add contextual information: %s" % e)
            return chunk

    async def _generate_embedding(self, text: str) -> List[float]:
        """Generate embedding for text using Mistral or OpenAI"""
        try:
            if self.use_mistral_embeddings and self.mistral_client:
                response = self.mistral_client.embeddings.create(
                    model=self.embedding_model, inputs=[text]
                )
                return response.data[0].embedding
            elif self.openai_client:
                response = await self.openai_client.embeddings.create(
                    model="text-embedding-3-small", input=text
                )
                return response.data[0].embedding
            else:
                raise ValueError(
                    "No embedding service available. Set MISTRAL_API_KEY or OPENAI_API_KEY"
                )
        except Exception as e:
            logger.error("Failed to generate embedding: %s" % e)
            raise

    async def _store_documentation_chunk(
        self,
        chunk_id: str,
        content: str,
        embedding: List[float],
        metadata: Dict[str, Any],
        source: str,
        chunk_type: str,
    ) -> None:
        """Store documentation chunk in database"""
        try:
            data = {
                "id": chunk_id,
                "content": content,
                "embedding": embedding,
                "metadata": metadata,
                "source": source,
                "chunk_type": chunk_type,
            }
            result = self.supabase.table("documentation_chunks").upsert(data).execute()
            if result.data:
                logger.info("Successfully stored chunk %s" % chunk_id)
            else:
                logger.warning("No data returned when storing chunk %s" % chunk_id)
        except Exception as e:
            logger.error("Failed to store chunk %s: %s" % (chunk_id, e))
            try:
                with self.engine.connect() as conn:
                    conn.execute(
                        text(
                            """
                        INSERT INTO documentation_chunks
                        (id, content, embedding, metadata, source, chunk_type)
                        VALUES (:id, :content, :embedding, :metadata, :source, :chunk_type)
                        ON CONFLICT (id) DO UPDATE SET
                            content = EXCLUDED.content,
                            embedding = EXCLUDED.embedding,
                            metadata = EXCLUDED.metadata,
                            updated_at = CURRENT_TIMESTAMP
                    """
                        ),
                        {
                            "id": chunk_id,
                            "content": content,
                            "embedding": embedding,
                            "metadata": json.dumps(metadata),
                            "source": source,
                            "chunk_type": chunk_type,
                        },
                    )
                    conn.commit()
            except Exception as fallback_error:
                logger.error("Fallback also failed for chunk %s: %s" % (chunk_id, fallback_error))
                raise

    async def _extract_and_store_code_examples(
        self, content: str, framework: str, parent_chunk_id: str
    ) -> None:
        """Extract and store code examples for agentic RAG"""
        try:
            code_blocks = []
            lines = content.split("\n")
            in_code_block = False
            current_code = []
            current_language = None
            for line in lines:
                if line.startswith("```"):
                    if in_code_block:
                        if current_code and len("\n".join(current_code)) >= DEFAULT_LIMIT:
                            code_blocks.append(
                                {
                                    "code": "\n".join(current_code),
                                    "language": current_language or "python",
                                }
                            )
                        current_code = []
                        current_language = None
                        in_code_block = False
                    else:
                        current_language = line[3:].strip() or "python"
                        in_code_block = True
                elif in_code_block:
                    current_code.append(line)
            for i, code_block in enumerate(code_blocks):
                summary = await self._generate_code_summary(code_block["code"], framework)
                code_with_summary = f"{code_block['code']}\n\nSummary: {summary}"
                embedding = await self._generate_embedding(code_with_summary)
                example_type = self._classify_code_example(code_block["code"])
                example_id = f"{parent_chunk_id}_code_{i}"
                await self._store_code_example(
                    example_id=example_id,
                    code_content=code_block["code"],
                    summary=summary,
                    embedding=embedding,
                    framework=framework,
                    example_type=example_type,
                    metadata={"parent_chunk": parent_chunk_id, "language": code_block["language"]},
                )
        except Exception as e:
            logger.error("Failed to extract code examples: %s" % e)

    async def _generate_code_summary(self, code: str, framework: str) -> str:
        """Generate summary for code example"""
        try:
            prompt = f"""
            Summarize this {framework} code example in 2-3 sentences.
            Focus on what it does, key concepts used, and when you'd use it.

            Code:
            {code}
            """
            response = await self.openai_client.chat.completions.create(
                model=self.llm_model, messages=[{"role": "user", "content": prompt}], max_tokens=150
            )
            return response.choices[0].message.content.strip()
        except Exception as e:
            logger.warning("Failed to generate code summary: %s" % e)
            return "Code example for " + framework

    def _classify_code_example(self, code: str) -> str:
        """Classify the type of code example"""
        code_lower = code.lower()
        if "class " in code_lower and "agent" in code_lower:
            return "agent"
        elif "class " in code_lower:
            return "class"
        elif "def " in code_lower and "workflow" in code_lower:
            return "workflow"
        elif "def " in code_lower:
            return "function"
        elif "graph" in code_lower or "stategraph" in code_lower:
            return "workflow"
        else:
            return "example"

    async def _store_code_example(
        self,
        example_id: str,
        code_content: str,
        summary: str,
        embedding: List[float],
        framework: str,
        example_type: str,
        metadata: Dict[str, Any],
    ) -> None:
        """Store code example in database"""
        try:
            data = {
                "id": example_id,
                "code_content": code_content,
                "summary": summary,
                "embedding": embedding,
                "metadata": metadata,
                "source": framework,
                "framework": framework,
                "example_type": example_type,
            }
            result = self.supabase.table("code_examples").upsert(data).execute()
            if result.data:
                logger.info("Successfully stored code example %s" % example_id)
            else:
                logger.warning("No data returned when storing code example %s" % example_id)
        except Exception as e:
            logger.error("Failed to store code example %s: %s" % (example_id, e))
            try:
                with self.engine.connect() as conn:
                    conn.execute(
                        text(
                            """
                        INSERT INTO code_examples
                        (id, code_content, summary, embedding, metadata, source, framework, example_type)
                        VALUES (:id, :code_content, :summary, :embedding, :metadata, :source, :framework, :example_type)
                        ON CONFLICT (id) DO UPDATE SET
                            code_content = EXCLUDED.code_content,
                            summary = EXCLUDED.summary,
                            embedding = EXCLUDED.embedding,
                            metadata = EXCLUDED.metadata
                    """
                        ),
                        {
                            "id": example_id,
                            "code_content": code_content,
                            "summary": summary,
                            "embedding": embedding,
                            "metadata": json.dumps(metadata),
                            "source": framework,
                            "framework": framework,
                            "example_type": example_type,
                        },
                    )
                    conn.commit()
            except Exception as fallback_error:
                logger.error(
                    "Fallback also failed for code example %s: %s" % (example_id, fallback_error)
                )
                raise

    async def query_documentation(
        self,
        query: str,
        source_filter: Optional[str] = None,
        query_type: str = "documentation",
        max_results: int = 5,
    ) -> AgenticRAGResponse:
        """
        Query the RAG system for documentation

        Args:
            query: User's question
            source_filter: Filter by source ('langgraph', 'pydantic_ai', etc.)
            query_type: Type of query ('documentation', 'code_examples', 'hybrid')
            max_results: Maximum number of results to return
        """
        start_time = datetime.now()
        try:
            query_embedding = await self._generate_embedding(query)
            if query_type == "code_examples" and self.use_agentic_rag:
                results = await self._search_code_examples(
                    query_embedding, query, source_filter, max_results
                )
            elif query_type == "hybrid" and self.use_hybrid_search:
                results = await self._hybrid_search(
                    query_embedding, query, source_filter, max_results
                )
            else:
                results = await self._search_documentation(
                    query_embedding, query, source_filter, max_results
                )
            answer = await self._generate_answer(query, results)
            confidence = self._calculate_confidence(results)
            processing_time = (datetime.now() - start_time).total_seconds()
            return AgenticRAGResponse(
                answer=answer,
                sources=[
                    {
                        "id": r["id"],
                        "source": r["source"],
                        "similarity": r["similarity"],
                        "content_preview": r["content"][:200] + "...",
                    }
                    for r in results
                ],
                confidence=confidence,
                chunks_used=[r["id"] for r in results],
                query_type=query_type,
                processing_time=processing_time,
            )
        except Exception as e:
            logger.error("Failed to query documentation: %s" % e)
            raise

    async def _search_documentation(
        self,
        query_embedding: List[float],
        query: str,
        source_filter: Optional[str],
        max_results: int,
    ) -> List[Dict[str, Any]]:
        """Search documentation chunks"""
        try:
            with self.engine.connect() as conn:
                sql = """
                    SELECT id, content, metadata, source, chunk_type,
                           1 - (embedding <=> :query_embedding) as similarity
                    FROM documentation_chunks
                """
                params = {"query_embedding": query_embedding}
                if source_filter:
                    sql += " WHERE source = :source_filter"
                    params["source_filter"] = source_filter
                sql += " ORDER BY similarity DESC LIMIT :max_results"
                params["max_results"] = max_results
                result = conn.execute(text(sql), params)
                return [
                    {
                        "id": row[0],
                        "content": row[1],
                        "metadata": json.loads(row[2]) if row[2] else {},
                        "source": row[3],
                        "chunk_type": row[4],
                        "similarity": float(row[5]),
                    }
                    for row in result.fetchall()
                ]
        except Exception as e:
            logger.error("Failed to search documentation: %s" % e)
            return []

    async def _search_code_examples(
        self,
        query_embedding: List[float],
        query: str,
        source_filter: Optional[str],
        max_results: int,
    ) -> List[Dict[str, Any]]:
        """Search code examples"""
        try:
            with self.engine.connect() as conn:
                sql = """
                    SELECT id, code_content, summary, metadata, source, framework, example_type,
                           1 - (embedding <=> :query_embedding) as similarity
                    FROM code_examples
                """
                params = {"query_embedding": query_embedding}
                if source_filter:
                    sql += " WHERE framework = :source_filter"
                    params["source_filter"] = source_filter
                sql += " ORDER BY similarity DESC LIMIT :max_results"
                params["max_results"] = max_results
                result = conn.execute(text(sql), params)
                return [
                    {
                        "id": row[0],
                        "content": f"```python\n{row[1]}\n```\n\n{row[2]}",
                        "metadata": json.loads(row[3]) if row[3] else {},
                        "source": row[4],
                        "framework": row[5],
                        "example_type": row[6],
                        "similarity": float(row[7]),
                    }
                    for row in result.fetchall()
                ]
        except Exception as e:
            logger.error("Failed to search code examples: %s" % e)
            return []

    async def _hybrid_search(
        self,
        query_embedding: List[float],
        query: str,
        source_filter: Optional[str],
        max_results: int,
    ) -> List[Dict[str, Any]]:
        """Perform hybrid search combining vector and keyword search"""
        try:
            vector_results = await self._search_documentation(
                query_embedding, query, source_filter, max_results * 2
            )
            keyword_results = await self._keyword_search(query, source_filter, max_results * 2)
            combined_results = self._combine_search_results(vector_results, keyword_results)
            return combined_results[:max_results]
        except Exception as e:
            logger.error("Failed to perform hybrid search: %s" % e)
            return await self._search_documentation(
                query_embedding, query, source_filter, max_results
            )

    async def _keyword_search(
        self, query: str, source_filter: Optional[str], max_results: int
    ) -> List[Dict[str, Any]]:
        """Perform keyword-based search"""
        try:
            with self.engine.connect() as conn:
                sql = """
                    SELECT id, content, metadata, source, chunk_type,
                           ts_rank(to_tsvector('english', content), plainto_tsquery('english', :query)) as rank
                    FROM documentation_chunks
                    WHERE to_tsvector('english', content) @@ plainto_tsquery('english', :query)
                """
                params = {"query": query}
                if source_filter:
                    sql += " AND source = :source_filter"
                    params["source_filter"] = source_filter
                sql += " ORDER BY rank DESC LIMIT :max_results"
                params["max_results"] = max_results
                result = conn.execute(text(sql), params)
                return [
                    {
                        "id": row[0],
                        "content": row[1],
                        "metadata": json.loads(row[2]) if row[2] else {},
                        "source": row[3],
                        "chunk_type": row[4],
                        "similarity": float(row[5]),
                    }
                    for row in result.fetchall()
                ]
        except Exception as e:
            logger.error("Failed to perform keyword search: %s" % e)
            return []

    def _combine_search_results(
        self, vector_results: List[Dict[str, Any]], keyword_results: List[Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        """Combine vector and keyword search results"""
        result_dict = {}
        for i, result in enumerate(vector_results):
            result_id = result["id"]
            vector_score = result["similarity"]
            vector_rank = len(vector_results) - i
            result_dict[result_id] = {
                **result,
                "vector_score": vector_score,
                "vector_rank": vector_rank,
                "keyword_score": 0,
                "keyword_rank": 0,
            }
        for i, result in enumerate(keyword_results):
            result_id = result["id"]
            keyword_score = result["similarity"]
            keyword_rank = len(keyword_results) - i
            if result_id in result_dict:
                result_dict[result_id]["keyword_score"] = keyword_score
                result_dict[result_id]["keyword_rank"] = keyword_rank
            else:
                result_dict[result_id] = {
                    **result,
                    "vector_score": 0,
                    "vector_rank": 0,
                    "keyword_score": keyword_score,
                    "keyword_rank": keyword_rank,
                }
        for result in result_dict.values():
            combined_score = (
                0.7 * result["vector_score"]
                + 0.3 * result["keyword_score"]
                + 0.1 * (result["vector_rank"] + result["keyword_rank"]) / 100
            )
            result["similarity"] = combined_score
        combined_results = sorted(result_dict.values(), key=lambda x: x["similarity"], reverse=True)
        return combined_results

    async def _generate_answer(self, query: str, results: List[Dict[str, Any]]) -> str:
        """Generate answer using retrieved context"""
        try:
            context_parts = []
            for i, result in enumerate(results[:3]):
                context_parts.append(f"Source {i + 1} ({result['source']}):\n{result['content']}")
            context = "\n\n".join(context_parts)
            prompt = f"""
            You are an expert assistant helping with LangGraph and Pydantic AI implementation.

            User Question: {query}

            Relevant Documentation:
            {context}

            Provide a comprehensive answer based on the documentation provided.
            Include code examples when relevant and cite specific sources.
            Focus on practical implementation guidance.
            If the question involves both LangGraph and Pydantic AI, explain how they work together.
            """
            response = await self.openai_client.chat.completions.create(
                model=self.llm_model,
                messages=[{"role": "user", "content": prompt}],
                max_tokens=1000,
                temperature=0.1,
            )
            return response.choices[0].message.content.strip()
        except Exception as e:
            logger.error("Failed to generate answer: %s" % e)
            return (
                "I apologize, but I encountered an error while generating the answer. Please try again.",
            )

    def _calculate_confidence(self, results: List[Dict[str, Any]]) -> float:
        """Calculate confidence score based on search results"""
        if not results:
            return 0.0
        top_similarities = [r["similarity"] for r in results[:3]]
        avg_similarity = sum(top_similarities) / len(top_similarities)
        confidence = min(1.0, avg_similarity * 1.2)
        return round(confidence, 3)

    async def get_available_sources(self) -> List[str]:
        """Get list of available documentation sources"""
        try:
            with self.engine.connect() as conn:
                result = conn.execute(
                    text(
                        """
                    SELECT DISTINCT source FROM documentation_chunks
                    UNION
                    SELECT DISTINCT framework FROM code_examples
                    ORDER BY source
                """
                    )
                )
                return [row[0] for row in result.fetchall()]
        except Exception as e:
            logger.error("Failed to get available sources: %s" % e)
            return []

    async def get_framework_statistics(self) -> Dict[str, Any]:
        """Get statistics about indexed documentation"""
        try:
            with self.engine.connect() as conn:
                doc_result = conn.execute(
                    text(
                        """
                    SELECT source, chunk_type, COUNT(*) as count
                    FROM documentation_chunks
                    GROUP BY source, chunk_type
                """
                    )
                )
                code_result = conn.execute(
                    text(
                        """
                    SELECT framework, example_type, COUNT(*) as count
                    FROM code_examples
                    GROUP BY framework, example_type
                """
                    )
                )
                stats = {
                    "documentation_chunks": {},
                    "code_examples": {},
                    "total_chunks": 0,
                    "total_code_examples": 0,
                }
                for row in doc_result.fetchall():
                    source, chunk_type, count = row
                    if source not in stats["documentation_chunks"]:
                        stats["documentation_chunks"][source] = {}
                    stats["documentation_chunks"][source][chunk_type] = count
                    stats["total_chunks"] += count
                for row in code_result.fetchall():
                    framework, example_type, count = row
                    if framework not in stats["code_examples"]:
                        stats["code_examples"][framework] = {}
                    stats["code_examples"][framework][example_type] = count
                    stats["total_code_examples"] += count
                return stats
        except Exception as e:
            logger.error("Failed to get framework statistics: %s" % e)
            return {}

    def close(self) -> None:
        """Close database connections"""
        if self.neo4j_driver:
            self.neo4j_driver.close()
