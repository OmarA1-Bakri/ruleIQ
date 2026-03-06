"""

Mock services for testing compliance and reporting nodes.
Provides mock implementations of external dependencies.
"""

from typing import Dict, Any, List, Optional
from datetime import datetime
from unittest.mock import AsyncMock, MagicMock
import json


class MockNeo4jSession:
    """Mock Neo4j session for testing."""

    def __init__(self, mock_data: Dict[str, Any] = None):
        """Initialize with optional mock data."""
        self.mock_data = mock_data or {}
        self.queries_executed = []

    async def run(self, query: str, **params):
        """Mock run method that returns predefined data."""
        self.queries_executed.append(
            {"query": query, "params": params, "timestamp": datetime.now().isoformat()},
        )

        # Return mock result based on query type
        if "MATCH (c:Company" in query:
            return MockNeo4jResult(self.mock_data.get("company_data", []))
        elif "MATCH (r:Regulation" in query:
            return MockNeo4jResult(self.mock_data.get("regulation_data", []))
        elif "MATCH" in query and "Obligation" in query:
            return MockNeo4jResult(self.mock_data.get("obligation_data", []))
        else:
            return MockNeo4jResult([])

    async def __aenter__(self):
        """Async context manager entry."""
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit."""
        pass


class MockNeo4jResult:
    """Mock Neo4j query result."""

    def __init__(self, records: List[Dict[str, Any]]):
        """Initialize with mock records."""
        self.records = records

    def __aiter__(self):
        """Return async iterator."""
        return self._async_generator()

    async def _async_generator(self):
        """Generate records asynchronously."""
        for record in self.records:
            yield record


class MockSecretsVault:
    """Mock SecretsVault for testing."""

    def __init__(self, secrets: Dict[str, str] = None):
        """Initialize with mock secrets."""
        self.secrets = secrets or {
            "SMTP_HOST": "smtp.example.com",
            "SMTP_PORT": "587",
            "SMTP_USER": "compliance@example.com",
            "SMTP_PASSWORD": "mock_password",
            "NEO4J_URI": "bolt://localhost:7687",
            "NEO4J_USERNAME": "neo4j",
            "NEO4J_PASSWORD": "mock_neo4j_pass",
        }

    def get_secret(self, secret_name: str) -> Optional[str]:
        """Get mock secret value."""
        return self.secrets.get(secret_name)

    def health_check(self) -> Dict[str, Any]:
        """Mock health check."""
        return {
            "status": "healthy",
            "secrets_available": len(self.secrets),
            "timestamp": datetime.now().isoformat(),
        }


class MockEmailService:
    """Mock email service for testing."""

    def __init__(self, should_fail: bool = False):
        """Initialize with optional failure mode."""
        self.should_fail = should_fail
        self.sent_emails = []

    async def send_email(
        self,
        recipients: List[str],
        subject: str,
        body: str,
        attachment_path: Optional[str] = None,
    ) -> bool:
        """Mock email sending."""
        if self.should_fail:
            raise Exception("Mock email service failure")

        self.sent_emails.append(
            {
                "recipients": recipients,
                "subject": subject,
                "body": body,
                "attachment": attachment_path,
                "sent_at": datetime.now().isoformat(),
            },
        )

        return True


class MockFileSystem:
    """Mock file system operations for testing."""

    def __init__(self):
        """Initialize mock file system."""
        self.files = {}
        self.directories = set(["/tmp/reports"])

    def write_file(self, path: str, content: bytes) -> str:
        """Mock file write."""
        self.files[path] = content
        return path

    def read_file(self, path: str) -> bytes:
        """Mock file read."""
        if path not in self.files:
            raise FileNotFoundError(f"Mock file not found: {path}")
        return self.files[path]

    def delete_file(self, path: str) -> bool:
        """Mock file deletion."""
        if path in self.files:
            del self.files[path]
            return True
        return False

    def list_files(self, directory: str) -> List[str]:
        """Mock directory listing."""
        return [path for path in self.files if path.startswith(directory)]

    def file_exists(self, path: str) -> bool:
        """Check if mock file exists."""
        return path in self.files

    def create_directory(self, path: str):
        """Mock directory creation."""
        self.directories.add(path)

    def directory_exists(self, path: str) -> bool:
        """Check if mock directory exists."""
        return path in self.directories


class MockRegulatoryAPI:
    """Mock regulatory API for testing compliance checks."""

    def __init__(self, regulations: Dict[str, Any] = None):
        """Initialize with mock regulations."""
        self.regulations = regulations or {
            "GDPR": {
                "obligations": [
                    {
                        "id": "gdpr-1",
                        "title": "Data Protection Officer",
                        "description": "Appoint a Data Protection Officer",
                        "category": "governance",
                    },
                    {
                        "id": "gdpr-2",
                        "title": "Data Encryption",
                        "description": "Implement appropriate data encryption",
                        "category": "security",
                    },
                    {
                        "id": "gdpr-3",
                        "title": "Privacy Policy",
                        "description": "Maintain updated privacy policy",
                        "category": "transparency",
                    },
                ],
            },
            "SOC2": {
                "obligations": [
                    {
                        "id": "soc2-1",
                        "title": "Access Controls",
                        "description": "Implement logical access controls",
                        "category": "security",
                    },
                    {
                        "id": "soc2-2",
                        "title": "Change Management",
                        "description": "Document change management process",
                        "category": "availability",
                    },
                ],
            },
        }

    async def get_obligations(self, regulation: str) -> List[Dict[str, Any]]:
        """Get obligations for a regulation."""
        return self.regulations.get(regulation, {}).get("obligations", [])

    async def check_compliance(self, company_id: str, regulation: str) -> Dict[str, Any]:
        """Mock compliance check."""
        obligations = await self.get_obligations(regulation)

        # Mock some obligations as satisfied
        satisfied = len(obligations) // 2 if obligations else 0

        return {
            "company_id": company_id,
            "regulation": regulation,
            "total_obligations": len(obligations),
            "satisfied_obligations": satisfied,
            "compliance_score": ((satisfied / len(obligations) * 100) if obligations else 100,),
            "timestamp": datetime.now().isoformat(),
        }


class MockRAGService:
    """Mock RAG service for testing document retrieval."""

    def __init__(self, documents: List[Dict[str, Any]] = None):
        """Initialize with mock documents."""
        self.documents = documents or [
            {
                "content": "The organization must implement appropriate technical measures.",
                "metadata": {
                    "source": "GDPR Article 32",
                    "category": "security",
                    "relevance_score": 0.95,
                },
            },
            {
                "content": "Data retention requirements specify 7 years for financial records.",
                "metadata": {
                    "source": "SOX Compliance",
                    "category": "retention",
                    "relevance_score": 0.88,
                },
            },
        ]

    async def search(self, query: str, limit: int = 5) -> List[Dict[str, Any]]:
        """Mock document search."""
        # Return mock documents filtered by query keywords
        results = []
        for doc in self.documents:
            if any(word.lower() in doc["content"].lower() for word in query.split()):
                results.append(doc)
                if len(results) >= limit:
                    break
        return results


def get_mock_neo4j_session(mock_data: Dict[str, Any] = None) -> MockNeo4jSession:
    """Factory function to create mock Neo4j session."""
    default_data = {
        "company_data": [{"c": {"id": "company-123", "name": "Test Company"}}],
        "regulation_data": [{"r": {"id": "reg-1", "name": "GDPR"}}],
        "obligation_data": [
            {
                "o": {
                    "id": "ob1",
                    "title": "Data Protection",
                    "description": "Protect data",
                },
                "evidence": [{"id": "ev1", "type": "policy"}],
            },
            {
                "o": {
                    "id": "ob2",
                    "title": "Data Retention",
                    "description": "Retain data",
                },
                "evidence": [],
            },
        ],
    }

    if mock_data:
        default_data.update(mock_data)

    return MockNeo4jSession(default_data)


def get_mock_compliance_state() -> Dict[str, Any]:
    """Get a standard mock compliance state for testing."""
    return {
        "workflow_id": "test-workflow-123",
        "company_id": "company-456",
        "metadata": {
            "regulation": "GDPR",
            "report_type": "compliance_summary",
            "report_format": "pdf",
            "recipient_emails": ["compliance@example.com"],
        },
        "relevant_documents": [
            {
                "content": "The company must implement data protection requirements.",
                "metadata": {"source": "GDPR Article 32", "category": "security"},
            },
        ],
        "compliance_data": {
            "check_results": {
                "compliance_score": 85.0,
                "total_obligations": 20,
                "satisfied_obligations": 17,
                "violations": [
                    {"id": "v1", "title": "Missing DPO appointment"},
                    {"id": "v2", "title": "Incomplete privacy policy"},
                    {"id": "v3", "title": "Audit logs not retained"},
                ],
            },
            "risk_assessment": {"level": "MEDIUM", "score": 45, "violation_count": 3},
        },
        "report_data": {},
        "cleanup_data": {},
        "obligations": [],
        "errors": [],
        "error_count": 0,
        "history": [],
    }
