"""

# Constants

Simple integration tests for AI Policy streaming functionality.
Tests the actual streaming implementation with minimal mocking.
"""

import pytest
import asyncio
import json
from unittest.mock import Mock, AsyncMock, patch, MagicMock
from typing import AsyncGenerator
from api.schemas.ai_policy import (
    PolicyGenerationRequest,
    PolicyType,
    CustomizationLevel,
    TargetAudience,
    BusinessContext,
)
from services.ai.policy_generator import PolicyGenerator
from database.compliance_framework import ComplianceFramework

from tests.test_constants import HTTP_OK


class TestPolicyStreamingSimple:
    """Simple tests for the policy streaming functionality."""

    @pytest.fixture
    def sample_request(self):
        """Create a sample policy generation request."""
        return PolicyGenerationRequest(
            framework_id="gdpr",
            business_context=BusinessContext(
                organization_name="Test Company",
                industry="Technology",
                processes_personal_data=True,
                data_types=["customer_data", "employee_data"],
            ),
            policy_type=PolicyType.PRIVACY_POLICY,
            customization_level=CustomizationLevel.STANDARD,
            target_audience=TargetAudience.GENERAL_PUBLIC,
        )

    @pytest.fixture
    def sample_framework(self):
        """Create a sample compliance framework."""
        framework = Mock(spec=ComplianceFramework)
        framework.id = "gdpr"
        framework.name = "GDPR"
        framework.display_name = "GDPR"
        framework.description = "General Data Protection Regulation"
        framework.key_requirement = [
            "Lawful basis for processing",
            "Consent management",
            "Data subject rights",
            "Privacy by design",
        ]
        return framework

    @pytest.mark.asyncio
    async def test_generate_policy_stream_basic(self, sample_request, sample_framework):
        """Test basic streaming functionality."""
        generator = PolicyGenerator()

        async def mock_stream(*args, **kwargs):
            yield {
                "type": "content",
                "content": "Privacy Policy\n",
                "chunk_id": "1",
                "progress": 0.3,
            }
            yield {
                "type": "content",
                "content": "This policy describes how we handle data.\n",
                "chunk_id": "2",
                "progress": 0.6,
            }
            yield {"type": "complete", "content": "", "chunk_id": "3", "progress": 1.0}

        generator._stream_with_google = mock_stream
        generator.google_client = Mock()
        generator.primary_provider = "google"
        chunks = []
        async for chunk in generator.generate_policy_stream(sample_request, sample_framework):
            chunks.append(chunk)
        assert len(chunks) > 0
        metadata_chunk = chunks[0]
        assert metadata_chunk["type"] == "metadata"
        if "content" in metadata_chunk:
            metadata = json.loads(metadata_chunk["content"])
            assert metadata["organization_name"] == "Test Company"
            assert metadata["policy_type"] == "privacy_policy"
            assert metadata["framework_id"] == "gdpr"
        content_chunks = [c for c in chunks if c["type"] == "content"]
        assert len(content_chunks) > 0
        full_content = "".join(c["content"] for c in content_chunks)
        assert "Privacy Policy" in full_content
        assert "data" in full_content.lower()

    @pytest.mark.asyncio
    async def test_streaming_error_handling(self, sample_request, sample_framework):
        """Test error handling during streaming."""
        generator = PolicyGenerator()

        async def mock_error_stream(*args, **kwargs):
            yield {
                "type": "content",
                "content": "Partial content",
                "chunk_id": "1",
                "progress": 0.2,
            }
            raise Exception("Test error during streaming")

        generator._stream_with_google = mock_error_stream
        generator.google_client = Mock()
        generator.primary_provider = "google"
        generator._stream_with_openai = mock_error_stream
        generator.openai_client = Mock()
        chunks = []
        async for chunk in generator.generate_policy_stream(sample_request, sample_framework):
            chunks.append(chunk)
        assert any(c["type"] == "metadata" for c in chunks)
        assert any(c["type"] == "error" for c in chunks)
        error_chunks = [c for c in chunks if c["type"] == "error"]
        assert len(error_chunks) > 0
        assert "error" in error_chunks[0] or "content" in error_chunks[0]
        error_message = error_chunks[0].get("error", error_chunks[0].get("content", ""))
        assert "error" in str(error_message).lower()

    @pytest.mark.asyncio
    async def test_streaming_with_fallback(self, sample_request, sample_framework):
        """Test fallback to OpenAI when Google fails."""
        generator = PolicyGenerator()

        async def mock_google_fail(*args, **kwargs):
            raise Exception("Google API failed")
            yield

        async def mock_openai_success(*args, **kwargs):
            yield {
                "type": "content",
                "content": "Fallback policy content from OpenAI",
                "chunk_id": "openai-1",
                "progress": 0.5,
            }
            yield {"type": "complete", "content": "", "chunk_id": "openai-2", "progress": 1.0}

        generator._stream_with_google = mock_google_fail
        generator._stream_with_openai = mock_openai_success
        generator.google_client = Mock()
        generator.openai_client = Mock()
        generator.primary_provider = "google"
        chunks = []
        async for chunk in generator.generate_policy_stream(sample_request, sample_framework):
            chunks.append(chunk)
        content_chunks = [c for c in chunks if c["type"] == "content"]
        assert len(content_chunks) > 0
        full_content = "".join(c["content"] for c in content_chunks)
        assert "OpenAI" in full_content

    @pytest.mark.asyncio
    async def test_streaming_progress_tracking(self, sample_request, sample_framework):
        """Test that progress is tracked correctly during streaming."""
        generator = PolicyGenerator()

        async def mock_progress_stream(*args, **kwargs):
            progress_values = [0.1, 0.3, 0.5, 0.7, 0.9, 1.0]
            for i, progress in enumerate(progress_values[:-1]):
                yield {
                    "type": "content",
                    "content": f"Section {i + 1}\n",
                    "chunk_id": f"chunk-{i}",
                    "progress": progress,
                }
            yield {
                "type": "complete",
                "content": "",
                "chunk_id": "final",
                "progress": progress_values[-1],
            }

        generator._stream_with_google = mock_progress_stream
        generator.google_client = Mock()
        generator.primary_provider = "google"
        chunks = []
        progress_values = []
        async for chunk in generator.generate_policy_stream(sample_request, sample_framework):
            chunks.append(chunk)
            if "progress" in chunk:
                progress_values.append(chunk["progress"])
        for i in range(1, len(progress_values)):
            if progress_values[i - 1] is not None and progress_values[i] is not None:
                assert progress_values[i] >= progress_values[i - 1]
        final_chunks = [c for c in chunks if c["type"] == "complete"]
        if final_chunks:
            assert final_chunks[0].get("progress") == 1.0


class TestPolicyStreamingAPI:
    """Test the streaming API endpoint."""

    @pytest.mark.asyncio
    async def test_stream_endpoint_format(self):
        """Test that the streaming endpoint returns proper format."""
        import sys

        sys.modules["services.redis_client"] = MagicMock()
        sys.modules["services.redis_client"].get_redis_client = MagicMock(return_value=None)
        from fastapi.testclient import TestClient
        from main import app

        with TestClient(app) as client:
            with patch("api.dependencies.auth.get_current_user") as mock_auth:
                mock_auth.return_value = Mock(id="test_user", email="test@example.com")
                with patch("api.routers.ai_policy.PolicyGenerator") as MockGenerator:
                    mock_generator = MockGenerator.return_value

                    async def mock_stream(*args, **kwargs):
                        yield {
                            "type": "metadata",
                            "content": json.dumps(
                                {"session_id": "test-session", "policy_type": "privacy_policy"}
                            ),
                            "chunk_id": "metadata",
                        }
                        yield {"type": "content", "content": "Test content", "chunk_id": "1"}
                        yield {"type": "complete", "content": "", "chunk_id": "2"}

                    mock_generator.generate_policy_stream = mock_stream
                    response = client.post(
                        "/api/ai-policy/generate-policy/stream",
                        json={
                            "framework_id": "gdpr",
                            "business_context": {
                                "organization_name": "Test Co",
                                "industry": "Tech",
                                "processes_personal_data": True,
                            },
                            "policy_type": "privacy_policy",
                        },
                        headers={"Authorization": "Bearer test_token"},
                    )
                    assert response.status_code == HTTP_OK
                    content = response.content.decode("utf-8")
                    assert "data:" in content
