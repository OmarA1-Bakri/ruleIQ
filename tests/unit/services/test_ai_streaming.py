"""

# Constants


Unit tests for AI Streaming Implementation.

Tests the streaming functionality including async generators,
model selection integration, and error handling in streaming operations.
"""

import asyncio
from typing import Optional
from unittest.mock import Mock, patch
from uuid import uuid4
import pytest
import requests
from services.ai.assistant import ComplianceAssistant
from services.ai.exceptions import ModelUnavailableException

from tests.test_constants import DEFAULT_LIMIT, MAX_RETRIES


class MockStreamingResponse:
    """Mock streaming response for testing."""

    def __init__(self, chunks: list, fail_at: int = -1):
        self.chunks = chunks
        self.fail_at = fail_at
        self.current = 0

    def __iter__(self):
        return self

    def __next__(self):
        if self.current == self.fail_at:
            raise Exception("Simulated streaming failure")
        if self.current >= len(self.chunks):
            raise StopIteration
        chunk = self.chunks[self.current]
        self.current += 1
        return chunk


class MockChunk:
    """Mock chunk object for streaming responses."""

    def __init__(self, text: Optional[str] = None, candidates: Optional[list] = None):
        self.text = text
        self.candidates = candidates or []


class MockCandidate:
    """Mock candidate object for streaming responses."""

    def __init__(self, content=None):
        self.content = content


class MockContent:
    """Mock content object for streaming responses."""

    def __init__(self, parts: list):
        self.parts = parts


class MockPart:
    """Mock part object for streaming responses."""

    def __init__(self, text: str):
        self.text = text


@pytest.fixture
def compliance_assistant():
    """Compliance assistant instance for testing."""
    from sqlalchemy.ext.asyncio import AsyncSession

    mock_db = Mock(spec=AsyncSession)
    assistant = ComplianceAssistant(mock_db)
    return assistant


@pytest.fixture
def mock_streaming_chunks():
    """Mock streaming chunks for testing."""
    return [
        MockChunk(text="This is "),
        MockChunk(text="a streaming "),
        MockChunk(text="response "),
        MockChunk(text="for testing."),
    ]


@pytest.fixture
def mock_complex_chunks():
    """Mock complex streaming chunks with candidates structure."""
    return [
        MockChunk(
            candidates=[MockCandidate(content=MockContent(parts=[MockPart(text="Complex ")]))]
        ),
        MockChunk(
            candidates=[MockCandidate(content=MockContent(parts=[MockPart(text="streaming ")]))]
        ),
        MockChunk(text="response."),
    ]


class TestAIStreaming:
    """Test suite for AI streaming functionality."""

    @pytest.mark.asyncio
    async def test_stream_response_basic(self, compliance_assistant, mock_streaming_chunks):
        """Test basic streaming response functionality."""
        with patch.object(compliance_assistant, "_get_task_appropriate_model") as mock_get_model:
            mock_model = Mock()
            mock_model.generate_content_stream.return_value = MockStreamingResponse(
                mock_streaming_chunks
            )
            mock_get_model.return_value = mock_model, "test_instruction_id"
            with patch.object(
                compliance_assistant.circuit_breaker, "is_model_available", return_value=True
            ):
                chunks = []
                async for chunk in compliance_assistant._stream_response(
                    "System prompt", "User prompt", "test"
                ):
                    chunks.append(chunk)
                assert len(chunks) == 4
                assert "".join(chunks) == "This is a streaming response for testing."

    @pytest.mark.asyncio
    async def test_stream_response_with_complex_structure(
        self, compliance_assistant, mock_complex_chunks
    ):
        """Test streaming response with complex candidate structure."""
        with patch.object(compliance_assistant, "_get_task_appropriate_model") as mock_get_model:
            mock_model = Mock()
            mock_model.generate_content_stream.return_value = MockStreamingResponse(
                mock_complex_chunks
            )
            mock_get_model.return_value = mock_model, "test_instruction_id"
            with patch.object(
                compliance_assistant.circuit_breaker, "is_model_available", return_value=True
            ):
                chunks = []
                async for chunk in compliance_assistant._stream_response(
                    "System prompt", "User prompt", "test"
                ):
                    chunks.append(chunk)
                assert len(chunks) == MAX_RETRIES
                assert "".join(chunks) == "Complex streaming response."

    @pytest.mark.asyncio
    async def test_stream_response_circuit_breaker_open(self, compliance_assistant):
        """Test streaming response when circuit breaker is open."""
        with patch.object(compliance_assistant, "_get_task_appropriate_model") as mock_get_model:
            mock_model = Mock()
            mock_model.model_name = "test-model"
            mock_get_model.return_value = mock_model, "test_instruction_id"
            with patch.object(
                compliance_assistant.circuit_breaker, "is_model_available", return_value=False
            ):
                chunks = []
                async for chunk in compliance_assistant._stream_response(
                    "System prompt", "User prompt", "test"
                ):
                    chunks.append(chunk)
                assert len(chunks) == 1
                assert "temporarily unavailable" in chunks[0]

    @pytest.mark.asyncio
    async def test_stream_response_model_error(self, compliance_assistant):
        """Test streaming response with model error."""
        with patch.object(compliance_assistant, "_get_task_appropriate_model") as mock_get_model:
            mock_model = Mock()
            mock_model.generate_content_stream.side_effect = Exception("Model error")
            mock_get_model.return_value = mock_model, "test_instruction_id"
            with patch.object(
                compliance_assistant.circuit_breaker, "is_model_available", return_value=True
            ):
                chunks = []
                async for chunk in compliance_assistant._stream_response(
                    "System prompt", "User prompt", "test"
                ):
                    chunks.append(chunk)
                assert len(chunks) == 1
                assert "unable to provide a response" in chunks[0]

    @pytest.mark.asyncio
    async def test_stream_response_task_context(self, compliance_assistant, mock_streaming_chunks):
        """Test streaming response with task context."""
        context = {
            "framework": "gdpr",
            "business_context": {"industry": "tech"},
            "prompt_length": 500,
        }
        with patch.object(compliance_assistant, "_get_task_appropriate_model") as mock_get_model:
            mock_model = Mock()
            mock_model.generate_content_stream.return_value = MockStreamingResponse(
                mock_streaming_chunks
            )
            mock_get_model.return_value = mock_model, "test_instruction_id"
            with patch.object(
                compliance_assistant.circuit_breaker, "is_model_available", return_value=True
            ):
                chunks = []
                async for chunk in compliance_assistant._stream_response(
                    "System prompt", "User prompt", "analysis", context
                ):
                    chunks.append(chunk)
                mock_get_model.assert_called_once()
                assert len(chunks) == 4

    @pytest.mark.asyncio
    async def test_analyze_assessment_results_stream(self, compliance_assistant):
        """Test assessment analysis streaming."""
        assessment_responses = [
            {"question_id": "q1", "answer": "yes"},
            {"question_id": "q2", "answer": "no"},
        ]
        with patch.object(
            compliance_assistant.context_manager, "get_conversation_context"
        ) as mock_context:
            mock_context.return_value = {"business_profile": {"industry": "tech"}}
            with patch.object(
                compliance_assistant.prompt_templates, "get_assessment_analysis_prompt"
            ) as mock_prompt:
                mock_prompt.return_value = {"user": "Analysis prompt"}
                with patch.object(compliance_assistant, "_stream_response") as mock_stream:
                    mock_stream.return_value = async_generator_from_list(["Analysis ", "result"])
                    chunks = []
                    async for chunk in compliance_assistant.analyze_assessment_results_stream(
                        assessment_responses, "gdpr", uuid4()
                    ):
                        chunks.append(chunk)
                    assert len(chunks) == 2
                    assert "".join(chunks) == "Analysis result"

    @pytest.mark.asyncio
    async def test_get_assessment_recommendations_stream(self, compliance_assistant):
        """Test assessment recommendations streaming."""
        assessment_gaps = [
            {"section": "data_protection", "severity": "high"},
            {"section": "consent", "severity": "medium"},
        ]
        with patch.object(
            compliance_assistant.context_manager, "get_conversation_context"
        ) as mock_context:
            mock_context.return_value = {"business_profile": {"industry": "tech"}}
            with patch.object(
                compliance_assistant.prompt_templates, "get_assessment_recommendations_prompt"
            ) as mock_prompt:
                mock_prompt.return_value = {"user": "Recommendations prompt"}
                with patch.object(compliance_assistant, "_stream_response") as mock_stream:
                    mock_stream.return_value = async_generator_from_list(
                        ["Recommendation ", "content"]
                    )
                    chunks = []
                    async for chunk in compliance_assistant.get_assessment_recommendations_stream(
                        assessment_gaps, "gdpr", uuid4()
                    ):
                        chunks.append(chunk)
                    assert len(chunks) == 2
                    assert "".join(chunks) == "Recommendation content"

    @pytest.mark.asyncio
    async def test_get_assessment_help_stream(self, compliance_assistant):
        """Test assessment help streaming."""
        with patch.object(
            compliance_assistant.context_manager, "get_conversation_context"
        ) as mock_context:
            mock_context.return_value = {"business_profile": {"industry": "tech"}}
            with patch.object(
                compliance_assistant.prompt_templates, "get_assessment_help_prompt"
            ) as mock_prompt:
                mock_prompt.return_value = {"user": "Help prompt"}
                with patch.object(compliance_assistant, "_stream_response") as mock_stream:
                    mock_stream.return_value = async_generator_from_list(["Help ", "content"])
                    chunks = []
                    async for chunk in compliance_assistant.get_assessment_help_stream(
                        "q1", "What is GDPR?", "gdpr", uuid4()
                    ):
                        chunks.append(chunk)
                    assert len(chunks) == 2
                    assert "".join(chunks) == "Help content"

    @pytest.mark.asyncio
    async def test_streaming_error_handling(self, compliance_assistant):
        """Test error handling in streaming methods."""
        with patch.object(
            compliance_assistant.context_manager, "get_conversation_context"
        ) as mock_context:
            mock_context.side_effect = Exception("Context error")
            chunks = []
            async for chunk in compliance_assistant.analyze_assessment_results_stream(
                [], "gdpr", uuid4()
            ):
                chunks.append(chunk)
            assert len(chunks) == 1
            assert "Unable to analyze" in chunks[0]

    @pytest.mark.asyncio
    async def test_streaming_circuit_breaker_integration(self, compliance_assistant):
        """Test circuit breaker integration in streaming."""
        with patch.object(compliance_assistant, "_get_task_appropriate_model") as mock_get_model:
            mock_get_model.side_effect = ModelUnavailableException("test-model", "Circuit open")
            chunks = []
            async for chunk in compliance_assistant._stream_response(
                "System prompt", "User prompt", "test"
            ):
                chunks.append(chunk)
            assert len(chunks) == 1
            assert "temporarily unavailable" in chunks[0]

    @pytest.mark.asyncio
    async def test_streaming_success_recording(self, compliance_assistant, mock_streaming_chunks):
        """Test that streaming successes are recorded in circuit breaker."""
        with patch.object(compliance_assistant, "_get_task_appropriate_model") as mock_get_model:
            mock_model = Mock()
            mock_model.model_name = "test-model"
            mock_model.generate_content_stream.return_value = MockStreamingResponse(
                mock_streaming_chunks
            )
            mock_get_model.return_value = mock_model, "test_instruction_id"
            with patch.object(
                compliance_assistant.circuit_breaker, "is_model_available", return_value=True
            ):
                with patch.object(
                    compliance_assistant.circuit_breaker, "record_success"
                ) as mock_record:
                    chunks = []
                    async for chunk in compliance_assistant._stream_response(
                        "System prompt", "User prompt", "test"
                    ):
                        chunks.append(chunk)
                    assert mock_record.call_count == len(mock_streaming_chunks)

    @pytest.mark.asyncio
    async def test_streaming_failure_recording(self, compliance_assistant):
        """Test that streaming failures are recorded in circuit breaker."""
        with patch.object(compliance_assistant, "_get_task_appropriate_model") as mock_get_model:
            mock_model = Mock()
            mock_model.model_name = "test-model"
            error = Exception("Streaming error")
            mock_model.generate_content_stream.side_effect = error
            mock_get_model.return_value = mock_model, "test_instruction_id"
            with patch.object(
                compliance_assistant.circuit_breaker, "is_model_available", return_value=True
            ):
                with patch.object(
                    compliance_assistant.circuit_breaker, "record_failure"
                ) as mock_record:
                    chunks = []
                    async for chunk in compliance_assistant._stream_response(
                        "System prompt", "User prompt", "test"
                    ):
                        chunks.append(chunk)
                    mock_record.assert_called_once_with("test-model", error)


async def async_generator_from_list(items):
    """Convert a list to an async generator for testing."""
    for item in items:
        yield item


class TestStreamingPerformance:
    """Test suite for streaming performance characteristics."""

    @pytest.mark.asyncio
    async def test_streaming_latency(self, compliance_assistant, mock_streaming_chunks):
        """Test streaming response latency."""
        import time

        with patch.object(compliance_assistant, "_get_task_appropriate_model") as mock_get_model:
            mock_model = Mock()
            mock_model.generate_content_stream.return_value = MockStreamingResponse(
                mock_streaming_chunks
            )
            mock_get_model.return_value = mock_model, "test_instruction_id"
            with patch.object(
                compliance_assistant.circuit_breaker, "is_model_available", return_value=True
            ):
                start_time = time.time()
                chunks = []
                async for chunk in compliance_assistant._stream_response(
                    "System prompt", "User prompt", "test"
                ):
                    chunks.append(chunk)
                    await asyncio.sleep(0.001)
                total_time = time.time() - start_time
                assert total_time < 1.0
                assert len(chunks) == len(mock_streaming_chunks)

    @pytest.mark.asyncio
    async def test_streaming_memory_efficiency(self, compliance_assistant):
        """Test streaming memory efficiency with large responses."""
        large_chunks = [MockChunk(text=f"Chunk {i} ") for i in range(DEFAULT_LIMIT)]
        with patch.object(compliance_assistant, "_get_task_appropriate_model") as mock_get_model:
            mock_model = Mock()
            mock_model.generate_content_stream.return_value = MockStreamingResponse(large_chunks)
            mock_get_model.return_value = mock_model, "test_instruction_id"
            with patch.object(
                compliance_assistant.circuit_breaker, "is_model_available", return_value=True
            ):
                chunk_count = 0
                async for _chunk in compliance_assistant._stream_response(
                    "System prompt", "User prompt", "test"
                ):
                    chunk_count += 1
                assert chunk_count == DEFAULT_LIMIT

    @pytest.mark.asyncio
    async def test_streaming_concurrent_requests(self, compliance_assistant, mock_streaming_chunks):
        """Test handling multiple concurrent streaming requests."""

        async def single_stream_request():
            with patch.object(
                compliance_assistant, "_get_task_appropriate_model"
            ) as mock_get_model:
                mock_model = Mock()
                mock_model.generate_content_stream.return_value = MockStreamingResponse(
                    mock_streaming_chunks
                )
                mock_get_model.return_value = mock_model, "test_instruction_id"
                with patch.object(
                    compliance_assistant.circuit_breaker, "is_model_available", return_value=True
                ):
                    chunks = []
                    async for chunk in compliance_assistant._stream_response(
                        "System prompt", "User prompt", "test"
                    ):
                        chunks.append(chunk)
                    return len(chunks)

        tasks = [single_stream_request() for _ in range(5)]
        results = await asyncio.gather(*tasks)
        assert all(result == len(mock_streaming_chunks) for result in results)
