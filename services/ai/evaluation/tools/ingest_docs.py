"""Document ingestion tool for golden datasets.


This script handles the complete ingestion pipeline:
1. Load manifest via _load_manifest_clean
2. Fetch each URL → extract text
3. Chunk ≈1000 tokens
4. Embed via BAAI/bge-small-en-v1.5
5. Upsert to Neo4j
"""

import json
import hashlib
import argparse
import logging
from pathlib import Path
from typing import Dict, List, Any, Optional
from datetime import datetime, timezone
import sys

sys.path.append(str(Path(__file__).parent.parent.parent.parent))
from services.ai.evaluation.tools.ingestion import (
    DocumentProcessor,
    ChunkProcessor,
    EmbeddingGenerator,
    GraphIngestion,
)
from services.ai.evaluation.schemas.common import GoldenDoc, SourceMeta

logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


class ManifestProcessor:
    """Process manifest files for document ingestion."""

    def __init__(self, manifest_path: str) -> None:
        """Initialize with manifest path."""
        self.manifest_path = Path(manifest_path)
        self.manifest_data = None

    def _load_manifest_clean(self) -> Dict[str, Any]:
        """Load and clean manifest file."""
        logger.info("Loading manifest from %s" % self.manifest_path)
        with open(self.manifest_path, "r") as f:
            content = f.read()
            import re

            content = re.sub(",\\s*}", "}", content)
            content = re.sub(",\\s*]", "]", content)
            self.manifest_data = json.loads(content)
        docs = self.manifest_data.get("items", self.manifest_data.get("documents", []))
        logger.info("Loaded manifest with %s documents" % len(docs))
        return self.manifest_data

    def get_priority_documents(self, min_priority: int = 4) -> List[Dict[str, Any]]:
        """Get documents with priority >= min_priority."""
        if not self.manifest_data:
            self._load_manifest_clean()
        docs = self.manifest_data.get("items", self.manifest_data.get("documents", []))
        priority_docs = [doc for doc in docs if doc.get("priority", 0) >= min_priority]
        logger.info("Found %s documents with priority >= %s" % (len(priority_docs), min_priority))
        return priority_docs


class DocumentFetcher:
    """Fetch and extract text from URLs."""

    def __init__(self) -> None:
        """Initialize document fetcher."""
        self.session = None
        self._setup_session()

    def _setup_session(self):
        """Setup HTTP session with retries."""
        import requests
        from requests.adapters import HTTPAdapter
        from requests.packages.urllib3.util.retry import Retry

        self.session = requests.Session()
        self.session.headers.update(
            {
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"
            }
        )
        retry = Retry(total=3, backoff_factor=0.3, status_forcelist=[500, 502, 503, 504])
        adapter = HTTPAdapter(max_retries=retry)
        self.session.mount("http://", adapter)
        self.session.mount("https://", adapter)

    def fetch_document(self, url: str, doc_type: str = "html") -> Optional[str]:
        """Fetch document from URL and extract text."""
        logger.info("Fetching %s document from %s" % (doc_type, url))
        try:
            response = self.session.get(url, timeout=30)
            response.raise_for_status()
            if doc_type == "pdf":
                return self._extract_pdf_text(response.content)
            else:
                return self._extract_html_text(response.text)
        except Exception as e:
            logger.error("Error fetching %s: %s" % (url, e))
            return None

    def _extract_html_text(self, html: str) -> str:
        """Extract text from HTML using BeautifulSoup."""
        from bs4 import BeautifulSoup

        try:
            soup = BeautifulSoup(html, "html.parser")
            for script in soup(["script", "style"]):
                script.decompose()
            text = soup.get_text()
            lines = (line.strip() for line in text.splitlines())
            chunks = (phrase.strip() for line in lines for phrase in line.split("  "))
            text = " ".join(chunk for chunk in chunks if chunk)
            return text
        except Exception as e:
            logger.error("Error extracting HTML text: %s" % e)
            soup = BeautifulSoup(html, "html.parser")
            return soup.get_text()

    def _extract_pdf_text(self, pdf_content: bytes) -> str:
        """Extract text from PDF using pypdf."""
        import io
        from pypdf import PdfReader

        try:
            pdf_file = io.BytesIO(pdf_content)
            reader = PdfReader(pdf_file)
            text_parts = []
            for page_num, page in enumerate(reader.pages, 1):
                try:
                    text = page.extract_text()
                    if text:
                        text_parts.append(text)
                except Exception as e:
                    logger.warning("Error extracting page %s: %s" % (page_num, e))
            return " ".join(text_parts)
        except Exception as e:
            logger.error("Error extracting PDF text: %s" % e)
            return ""


class GoldenDatasetBuilder:
    """Build golden dataset from manifest documents."""

    def __init__(self) -> None:
        """Initialize builder components."""
        self.fetcher = DocumentFetcher()
        self.doc_processor = DocumentProcessor()
        self.chunk_processor = ChunkProcessor(chunk_size=1000, overlap=100)
        self.embedding_generator = EmbeddingGenerator()
        self.graph_ingestion = GraphIngestion()

    def process_manifest_document(self, doc_info: Dict[str, Any]) -> Optional[GoldenDoc]:
        """Process a single document from manifest."""
        url = doc_info.get("url", "")
        title = doc_info.get("title", "")
        doc_type = doc_info.get("type", "pdf" if url.endswith(".pdf") else "html")
        content = self.fetcher.fetch_document(url, doc_type)
        if not content:
            logger.warning("Failed to fetch content for %s" % title)
            return None
        source_meta = SourceMeta(
            origin=url,
            domain=self._extract_domain(url),
            trust_score=doc_info.get("priority", 3) / 5.0,
            sha256=hashlib.sha256(content.encode()).hexdigest(),
            fetched_at=datetime.now(timezone.utc),
        )
        doc_id = f"doc_{hashlib.md5(url.encode(), usedforsecurity=False).hexdigest()[:12]}"
        tags = doc_info.get("tags", [])
        category = tags[0] if tags else "general"
        golden_doc = GoldenDoc(
            doc_id=doc_id,
            content=self.doc_processor.preprocess_content(content),
            source_meta=source_meta,
            reg_citations=[category],
            expected_outcomes=[
                {"category": category, "confidence": doc_info.get("priority", 3) / 5.0}
            ],
        )
        return golden_doc

    def _extract_domain(self, url: str) -> str:
        """Extract domain from URL."""
        from urllib.parse import urlparse

        parsed = urlparse(url)
        return parsed.netloc

    def ingest_document(self, golden_doc: GoldenDoc) -> bool:
        """Ingest a golden document into Neo4j."""
        try:
            doc_embedding = self.embedding_generator.generate_embedding(golden_doc.content[:2000])
            if not self.graph_ingestion.ingest_document(golden_doc, doc_embedding):
                return False
            chunks = self.chunk_processor.chunk_document(golden_doc)
            logger.info("Created %s chunks for document %s" % (len(chunks), golden_doc.doc_id))
            chunk_texts = [chunk.content for chunk in chunks]
            chunk_embeddings = self.embedding_generator.generate_embeddings_batch(chunk_texts)
            success_count = 0
            for chunk, embedding in zip(chunks, chunk_embeddings):
                if self.graph_ingestion.ingest_chunk(chunk, embedding):
                    success_count += 1
            logger.info("Successfully ingested %s/%s chunks" % (success_count, len(chunks)))
            if chunks:
                self.graph_ingestion.create_chunk_relationships(chunks)
            return True
        except Exception as e:
            logger.error("Error ingesting document %s: %s" % (golden_doc.doc_id, e))
            return False


def main() -> Any:
    """Main ingestion pipeline."""
    parser = argparse.ArgumentParser(description="Ingest documents for golden dataset")
    parser.add_argument(
        "--manifest",
        type=str,
        default="/home/omar/Documents/ruleIQ/data/manifests/compliance_ml_manifest.json",
        help="Path to manifest file",
    )
    parser.add_argument(
        "--min-priority",
        type=int,
        default=4,
        help="Minimum priority for documents to ingest (default: 4)",
    )
    parser.add_argument(
        "--limit", type=int, default=None, help="Limit number of documents to process"
    )
    args = parser.parse_args()
    manifest_processor = ManifestProcessor(args.manifest)
    builder = GoldenDatasetBuilder()
    priority_docs = manifest_processor.get_priority_documents(
        args.min_priority,
    )
    if args.limit:
        priority_docs = priority_docs[: args.limit]
    logger.info("Processing %s documents" % len(priority_docs))
    success_count = 0
    failed_docs = []
    for idx, doc_info in enumerate(priority_docs, 1):
        logger.info(
            "Processing document %s/%s: %s"
            % (idx, len(priority_docs), doc_info.get("title", "Unknown"))
        )
        golden_doc = builder.process_manifest_document(doc_info)
        if not golden_doc:
            failed_docs.append(doc_info.get("title", "Unknown"))
            continue
        if builder.ingest_document(golden_doc):
            success_count += 1
        else:
            failed_docs.append(doc_info.get("title", "Unknown"))
    logger.info("=" * 50)
    logger.info("Ingestion complete!")
    logger.info("Successfully processed: %s/%s documents" % (success_count, len(priority_docs)))
    if failed_docs:
        logger.warning("Failed documents: %s" % ", ".join(failed_docs))
    return 0 if success_count > 0 else 1


if __name__ == "__main__":
    sys.exit(main())
