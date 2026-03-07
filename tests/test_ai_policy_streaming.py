"""
Comprehensive tests for AI Policy streaming functionality.
Tests SSE format, error handling, circuit breaker behavior, and provider integration.
"""

import pytest
import asyncio
import json
from unittest.mock import Mock, AsyncMock, patch, MagicMock
from datetime import datetime
from typing import AsyncGenerator, Dict, Any

from fastapi import HTTPException
from fastapi.testclient import TestClient
from httpx import AsyncClient
import httpx

from api.schemas.ai_policy import (
    PolicyGenerationRequest,
    PolicyType,
    CustomizationLevel,
    TargetAudience,
    BusinessContext,
    PolicyStreamingChunk,
    PolicyStreamingMetadata,
)
from services.ai.policy_generator import PolicyGenerator
from database.compliance_framework import ComplianceFramework


class TestPolicyStreamingService:
    """Test the PolicyGenerator streaming service implementation."""

    @pytest.fixture
    def policy_generator(self):
        """Create a PolicyGenerator instance with mocked dependencies."""
        with (
            patch("services.ai.google_client.GoogleAIClient"),
            patch("services.ai.openai_client.OpenAIClient"),
        ):
            generator = PolicyGenerator()
            generator.google_client = Mock()
            generator.openai_client = Mock()
            generator.circuit_breaker = Mock()
            generator.template_processor = Mock()
            return generator

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
        framework.description = "General Data Protection Regulation"
        return framework

    @pytest.mark.asyncio
    async def test_generate_policy_stream_metadata_chunk(
        self, policy_generator, sample_request, sample_framework
    ):
        """Test that streaming starts with a metadata chunk."""
        chunks = []

        # Mock the Google streaming response
        async def mock_google_stream(*args, **kwargs):
            yield {
                "type": "content",
                "content": "Test policy content",
                "chunk_id": "1",
                "progress": 0.5,
            }
            yield {"type": "complete", "content": "", "chunk_id": "2", "progress": 1.0}

        with patch.object(policy_generator, "_stream_with_google", side_effect=mock_google_stream):
            async for chunk in policy_generator.generate_policy_stream(
                sample_request, sample_framework
            ):
                chunks.append(chunk)

        # First chunk should be metadata
        assert len(chunks) >= 2
        assert chunks[0].chunk_type == "metadata"
        assert "organization_name" in chunks[0].content

        # Parse metadata JSON
        metadata = json.loads(chunks[0].content)
        assert metadata["organization_name"] == "Test Company"
        assert metadata["policy_type"] == "privacy_policy"
        assert metadata["framework_id"] == "gdpr"

    @pytest.mark.asyncio
    async def test_stream_with_google_success(self, policy_generator, sample_request):
        """Test successful streaming with Google AI."""
        # Mock Google's generate_content_async
        mock_response = Mock()
        mock_response.text = "Generated policy content"
        mock_response.__aiter__ = Mock(
            return_value=iter(
                [
                    Mock(text="Section 1: "),
                    Mock(text="Privacy Policy\n"),
                    Mock(text="This policy describes..."),
                ],
            ),
        )

        policy_generator.google_model.generate_content_async = AsyncMock(
            return_value=mock_response,
        )

        chunks = []
        async for chunk in policy_generator._stream_with_google("Test prompt", sample_request):
            chunks.append(chunk)

        # Verify chunks were generated
        assert len(chunks) > 0
        assert any(c.chunk_type == "content" for c in chunks)
        assert chunks[-1].chunk_type == "complete"

        # Verify content
        content = "".join(c.content for c in chunks if c.chunk_type == "content")
        assert "Privacy Policy" in content

    @pytest.mark.asyncio
    async def test_stream_with_openai_success(self, policy_generator, sample_request):
        """Test successful streaming with OpenAI."""
        # Mock OpenAI's streaming response
        mock_stream = AsyncMock()
        mock_chunks = [
            Mock(choices=[Mock(delta=Mock(content="Privacy "))]),
            Mock(choices=[Mock(delta=Mock(content="Policy "))]),
            Mock(choices=[Mock(delta=Mock(content="Content"))]),
            Mock(choices=[Mock(delta=Mock(content=None))]),  # End of stream,
        ]
        mock_stream.__aiter__ = Mock(return_value=iter(mock_chunks))

        policy_generator.openai_client.chat.completions.create = AsyncMock(
            return_value=mock_stream,
        )

        chunks = []
        async for chunk in policy_generator._stream_with_openai("Test prompt", sample_request):
            chunks.append(chunk)

        # Verify chunks were generated
        assert len(chunks) > 0
        assert any(c.chunk_type == "content" for c in chunks)
        assert chunks[-1].chunk_type == "complete"

        # Verify content
        content = "".join(c.content for c in chunks if c.chunk_type == "content")
        assert "Privacy Policy Content" in content

    @pytest.mark.asyncio
    async def test_stream_error_handling(self, policy_generator, sample_request, sample_framework):
        """Test error handling during streaming."""

        # Mock Google to raise an error
        async def mock_google_error(*args, **kwargs):
            yield PolicyStreamingChunk(
                chunk_id="1",
                content="Partial content",
                chunk_type="content",
            )
            raise Exception("Network error during streaming")

        with patch.object(policy_generator, "_stream_with_google", side_effect=mock_google_error):
            chunks = []
            async for chunk in policy_generator.generate_policy_stream(
                sample_request, sample_framework
            ):
                chunks.append(chunk)

            # Should have metadata, partial content, and error chunks
            assert any(c.chunk_type == "metadata" for c in chunks)
            assert any(c.chunk_type == "content" for c in chunks)
            assert any(c.chunk_type == "error" for c in chunks)

            # Check error message
            error_chunk = next(c for c in chunks if c.chunk_type == "error")
            assert "Network error" in error_chunk.content

    @pytest.mark.asyncio
    async def test_stream_with_circuit_breaker_open(
        self, policy_generator, sample_request, sample_framework
    ):
        """Test streaming behavior when circuit breaker is open."""
        # Mock circuit breaker as open for Google
        with patch("services.ai.policy_generator.google_breaker") as mock_breaker:
            mock_breaker.call = AsyncMock(
                side_effect=Exception("Circuit breaker is open"),
            )

            # Mock OpenAI as backup
            async def mock_openai_stream(*args, **kwargs):
                yield PolicyStreamingChunk(
                    chunk_id="1",
                    content="Fallback content from OpenAI",
                    chunk_type="content",
                )
                yield PolicyStreamingChunk(
                    chunk_id="2",
                    content="",
                    chunk_type="complete",
                )

            with patch.object(
                policy_generator, "_stream_with_openai", side_effect=mock_openai_stream
            ):
                chunks = []
                async for chunk in policy_generator.generate_policy_stream(
                    sample_request, sample_framework
                ):
                    chunks.append(chunk)

                # Should fall back to OpenAI
                content = "".join(c.content for c in chunks if c.chunk_type == "content")
                assert "Fallback content from OpenAI" in content

    @pytest.mark.asyncio
    async def test_stream_progress_updates(
        self, policy_generator, sample_request, sample_framework
    ):
        """Test that progress updates are included in streaming chunks."""

        async def mock_google_with_progress(*args, **kwargs):
            sections = [
                ("Introduction", 0.2),
                ("Data Collection", 0.4),
                ("Data Usage", 0.6),
                ("Data Protection", 0.8),
                ("Contact Information", 1.0),
            ]

            for section, progress in sections:
                yield PolicyStreamingChunk(
                    chunk_id=f"section_{section}",
                    content=f"{section}: Content here...\n",
                    chunk_type="content",
                    section_name=section,
                    progress=progress,
                )

            yield PolicyStreamingChunk(
                chunk_id="complete",
                content="",
                chunk_type="complete",
                progress=1.0,
            )

        with patch.object(
            policy_generator,
            "_stream_with_google",
            side_effect=mock_google_with_progress,
        ):
            chunks = []
            async for chunk in policy_generator.generate_policy_stream(
                sample_request, sample_framework
            ):
                chunks.append(chunk)

            # Check progress values
            progress_chunks = [c for c in chunks if c.progress is not None]
            assert len(progress_chunks) > 0
            assert progress_chunks[-1].progress == 1.0

            # Check section names
            section_chunks = [c for c in chunks if c.section_name is not None]
            assert len(section_chunks) == 5
            assert "Introduction" in [c.section_name for c in section_chunks]


class TestPolicyStreamingAPI:
    """Test the API endpoint for policy streaming."""

    @pytest.fixture
    def client(self):
        """Create a test client."""
        from main import app

        return TestClient(app)

    @pytest.fixture
    def auth_headers(self):
        """Create authentication headers."""
        return {"Authorization": "Bearer test_token"}

    @pytest.fixture
    def mock_auth(self):
        """Mock authentication dependency."""
        with patch("api.dependencies.auth.get_current_user") as mock:
            mock.return_value = Mock(id="test_user", email="test@example.com")
            yield mock

    @pytest.mark.asyncio
    async def test_stream_endpoint_sse_format(self, client, auth_headers, mock_auth):
        """Test that the streaming endpoint returns proper SSE format."""
        # Mock the PolicyGenerator
        with patch("api.routers.ai_policy.PolicyGenerator") as MockGenerator:
            mock_generator = MockGenerator.return_value

            async def mock_stream(*args, **kwargs):
                yield PolicyStreamingChunk(
                    chunk_id="1",
                    content='{"test": "metadata"}',
                    chunk_type="metadata",
                )
                yield PolicyStreamingChunk(
                    chunk_id="2",
                    content="Test content",
                    chunk_type="content",
                )
                yield PolicyStreamingChunk(
                    chunk_id="3",
                    content="",
                    chunk_type="complete",
                )

            mock_generator.generate_policy_stream = mock_stream

            # Make request
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
                headers=auth_headers,
                stream=True,
            )

            # Parse SSE events
            events = []
            for line in response.iter_lines():
                if line.startswith(b"data: "):
                    data = line[6:].decode("utf-8")
                    if data != "[DONE]":
                        events.append(json.loads(data))

            # Verify SSE format
            assert len(events) == 3
            assert events[0]["chunk_type"] == "metadata"
            assert events[1]["chunk_type"] == "content"
            assert events[2]["chunk_type"] == "complete"

    @pytest.mark.asyncio
    async def test_stream_endpoint_headers(self, client, auth_headers, mock_auth):
        """Test that streaming endpoint sets correct headers."""
        with patch("api.routers.ai_policy.PolicyGenerator") as MockGenerator:
            mock_generator = MockGenerator.return_value

            async def mock_stream(*args, **kwargs):
                yield PolicyStreamingChunk(
                    chunk_id="1",
                    content="Test",
                    chunk_type="content",
                )

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
                headers=auth_headers,
                stream=True,
            )

            # Check headers
            assert (response.headers["content-type"] == "text/event-stream; charset=utf-8",)
            assert response.headers["cache-control"] == "no-cache"
            assert response.headers["connection"] == "keep-alive"
            assert response.headers.get("x-accel-buffering") == "no"

    @pytest.mark.asyncio
    async def test_stream_endpoint_error_handling(self, client, auth_headers, mock_auth):
        """Test error handling in streaming endpoint."""
        with patch("api.routers.ai_policy.PolicyGenerator") as MockGenerator:
            mock_generator = MockGenerator.return_value

            async def mock_stream_with_error(*args, **kwargs):
                yield PolicyStreamingChunk(
                    chunk_id="1",
                    content="Partial content",
                    chunk_type="content",
                )
                raise Exception("Streaming error")

            mock_generator.generate_policy_stream = mock_stream_with_error

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
                headers=auth_headers,
                stream=True,
            )

            # Parse events
            events = []
            for line in response.iter_lines():
                if line.startswith(b"data: "):
                    data = line[6:].decode("utf-8")
                    if data != "[DONE]":
                        events.append(json.loads(data))

            # Should have content and error chunks
            assert any(e["chunk_type"] == "content" for e in events)
            assert any(e["chunk_type"] == "error" for e in events)

    @pytest.mark.asyncio
    async def test_stream_endpoint_authentication(self, client):
        """Test that streaming endpoint requires authentication."""
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
        )

        assert response.status_code == 401  # Unauthorized

    @pytest.mark.asyncio
    async def test_stream_endpoint_rate_limiting(self, client, auth_headers, mock_auth):
        """Test that streaming endpoint respects rate limits."""
        with patch("api.routers.ai_policy.RateLimiter") as MockRateLimiter:
            mock_limiter = MockRateLimiter.return_value
            mock_limiter.check_rate_limit = AsyncMock(
                side_effect=HTTPException(status_code=429, detail="Rate limit exceeded"),
            )

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
                headers=auth_headers,
            )

            assert response.status_code == 429


class TestPolicyStreamingIntegration:
    """Integration tests for the complete streaming pipeline."""

    @pytest.mark.asyncio
    @pytest.mark.integration
    async def test_end_to_end_streaming_google(self):
        """Test end-to-end streaming with real Google AI (requires API key)."""
        import os

        if not os.getenv("GOOGLE_API_KEY"):
            pytest.skip("Google API key not available")

        generator = PolicyGenerator()
        request = PolicyGenerationRequest(
            framework_id="gdpr",
            business_context=BusinessContext(
                organization_name="Integration Test Co",
                industry="Technology",
                processes_personal_data=True,
            ),
            policy_type=PolicyType.PRIVACY_POLICY,
        )

        framework = Mock()
        framework.id = "gdpr"
        framework.name = "GDPR"

        chunks = []
        async for chunk in generator.generate_policy_stream(request, framework):
            chunks.append(chunk)

        # Verify complete stream
        assert len(chunks) > 2
        assert chunks[0].chunk_type == "metadata"
        assert chunks[-1].chunk_type == "complete"

        # Verify content
        content = "".join(c.content for c in chunks if c.chunk_type == "content")
        assert len(content) > 100
        assert "privacy" in content.lower() or "data" in content.lower()

    @pytest.mark.asyncio
    @pytest.mark.integration
    async def test_end_to_end_streaming_openai(self):
        """Test end-to-end streaming with real OpenAI (requires API key)."""
        import os

        if not os.getenv("OPENAI_API_KEY"):
            pytest.skip("OpenAI API key not available")

        generator = PolicyGenerator()

        # Force OpenAI by making Google fail
        with patch("services.ai.policy_generator.google_breaker") as mock_breaker:
            mock_breaker.call = AsyncMock(side_effect=Exception("Force OpenAI"))

            request = PolicyGenerationRequest(
                framework_id="gdpr",
                business_context=BusinessContext(
                    organization_name="Integration Test Co",
                    industry="Technology",
                    processes_personal_data=True,
                ),
                policy_type=PolicyType.PRIVACY_POLICY,
            )

            framework = Mock()
            framework.id = "gdpr"
            framework.name = "GDPR"

            chunks = []
            async for chunk in generator.generate_policy_stream(request, framework):
                chunks.append(chunk)

            # Verify complete stream
            assert len(chunks) > 2
            assert chunks[0].chunk_type == "metadata"
            assert chunks[-1].chunk_type == "complete"

            # Verify content
            content = "".join(c.content for c in chunks if c.chunk_type == "content")
            assert len(content) > 100


class TestPolicyStreamingPerformance:
    """Performance tests for streaming functionality."""

    @pytest.mark.asyncio
    async def test_streaming_latency(self, policy_generator, sample_request, sample_framework):
        """Test that first chunk arrives quickly."""
        import time

        async def mock_slow_stream(*args, **kwargs):
            yield PolicyStreamingChunk(
                chunk_id="1",
                content="First chunk",
                chunk_type="content",
            )
            await asyncio.sleep(1)  # Simulate slow generation
            yield PolicyStreamingChunk(
                chunk_id="2",
                content="Second chunk",
                chunk_type="content",
            )
            yield PolicyStreamingChunk(chunk_id="3", content="", chunk_type="complete")

        with patch.object(policy_generator, "_stream_with_google", side_effect=mock_slow_stream):
            start_time = time.time()
            first_chunk_time = None

            async for chunk in policy_generator.generate_policy_stream(
                sample_request, sample_framework
            ):
                if chunk.chunk_type == "content" and first_chunk_time is None:
                    first_chunk_time = time.time()

            # First content chunk should arrive quickly (after metadata)
            assert first_chunk_time - start_time < 0.5

    @pytest.mark.asyncio
    async def test_streaming_memory_usage(self, policy_generator, sample_request, sample_framework):
        """Test that streaming doesn't accumulate large buffers."""
        import tracemalloc

        async def mock_large_stream(*args, **kwargs):
            # Generate many chunks
            for i in range(100):
                yield PolicyStreamingChunk(
                    chunk_id=str(i),
                    content="x" * 1000,  # 1KB per chunk
                    chunk_type="content",
                )
            yield PolicyStreamingChunk(
                chunk_id="complete",
                content="",
                chunk_type="complete",
            )

        with patch.object(policy_generator, "_stream_with_google", side_effect=mock_large_stream):
            tracemalloc.start()

            chunk_count = 0
            async for _chunk in policy_generator.generate_policy_stream(
                sample_request, sample_framework
            ):
                chunk_count += 1

            current, peak = tracemalloc.get_traced_memory()
            tracemalloc.stop()

            # Memory usage should be reasonable (not storing all chunks)
            assert peak < 10 * 1024 * 1024  # Less than 10MB
            assert chunk_count > 100  # All chunks processed
