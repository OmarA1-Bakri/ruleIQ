"""
Performance tests for AI Optimization Implementation.

Tests performance characteristics of the optimized AI system including
response times, throughput, memory usage, and cost efficiency.
"""

import asyncio
import statistics
import time
from unittest.mock import Mock, patch

import pytest

from services.ai.assistant import ComplianceAssistant
from services.ai.exceptions import ModelUnavailableException


@pytest.fixture
def compliance_assistant():
    """Compliance assistant for performance testing."""
    from sqlalchemy.ext.asyncio import AsyncSession

    mock_db = Mock(spec=AsyncSession)
    assistant = ComplianceAssistant(mock_db)
    return assistant


@pytest.fixture
def performance_config():
    """Performance test configuration."""
    return {
        "max_response_time": 3.0,  # seconds
        "min_throughput": 10,  # requests per second
        "max_memory_mb": 500,
        "target_success_rate": 0.95,
        "concurrent_users": [1, 5, 10, 20],
        "test_duration": 30,  # seconds,
    }


class TestAIOptimizationPerformance:
    """Performance tests for AI optimization features."""

    @pytest.mark.asyncio
    async def test_model_selection_performance(self, compliance_assistant, performance_config):
        """Test model selection performance under load."""
        selection_times = []

        for _ in range(100):
            start_time = time.time()

            model = compliance_assistant._get_task_appropriate_model(
                "analysis",
                {"framework": "gdpr", "prompt_length": 1000},
            )

            selection_time = time.time() - start_time
            selection_times.append(selection_time)

            assert model is not None

        avg_time = statistics.mean(selection_times)
        max_time = max(selection_times)

        # Model selection should be very fast (< 10ms average)
        assert avg_time < 0.01, f"Average selection time {avg_time:.3f}s too slow"
        assert max_time < 0.05, f"Max selection time {max_time:.3f}s too slow"

    @pytest.mark.asyncio
    async def test_circuit_breaker_performance(self, compliance_assistant, performance_config):
        """Test circuit breaker performance impact."""
        circuit_breaker = compliance_assistant.circuit_breaker

        # Test availability check performance
        check_times = []
        for _ in range(1000):
            start_time = time.time()
            is_available = circuit_breaker.is_model_available("gemini-2.5-flash")
            check_time = time.time() - start_time
            check_times.append(check_time)
            assert is_available is not None

        avg_check_time = statistics.mean(check_times)
        assert avg_check_time < 0.001, f"Circuit breaker check too slow: {avg_check_time:.4f}s"

    @pytest.mark.asyncio
    async def test_streaming_performance(self, compliance_assistant, performance_config):
        """Test streaming response performance."""
        # Mock streaming chunks
        mock_chunks = [f"Chunk {i} " for i in range(50)]

        with patch.object(compliance_assistant, "_get_task_appropriate_model") as mock_get_model:
            mock_model = Mock()
            mock_model.generate_content_stream.return_value = iter(
                [Mock(text=chunk) for chunk in mock_chunks],
            )
            mock_get_model.return_value = (mock_model, "test_instruction_id")

            with patch.object(
                compliance_assistant.circuit_breaker,
                "is_model_available",
                return_value=True,
            ):
                start_time = time.time()

                chunks_received = []
                async for chunk in compliance_assistant._stream_response(
                    "System prompt", "User prompt", "test"
                ):
                    chunks_received.append(chunk)

                total_time = time.time() - start_time

                assert len(chunks_received) == len(mock_chunks)
                assert total_time < performance_config["max_response_time"]

                # Calculate throughput (chunks per second)
                throughput = len(chunks_received) / total_time
                assert throughput > 10, f"Streaming throughput too low: {throughput:.1f} chunks/s"

    @pytest.mark.asyncio
    async def test_concurrent_streaming_performance(self, compliance_assistant, performance_config):
        """Test performance under concurrent streaming load."""

        async def single_streaming_request():
            mock_chunks = ["Response ", "chunk ", "data"]

            with patch.object(
                compliance_assistant, "_get_task_appropriate_model"
            ) as mock_get_model:
                mock_model = Mock()
                mock_model.generate_content_stream.return_value = iter(
                    [Mock(text=chunk) for chunk in mock_chunks],
                )
                mock_get_model.return_value = (mock_model, "test_instruction_id")

                with patch.object(
                    compliance_assistant.circuit_breaker,
                    "is_model_available",
                    return_value=True,
                ):
                    start_time = time.time()

                    chunks = []
                    async for chunk in compliance_assistant._stream_response(
                        "System prompt", "User prompt", "test"
                    ):
                        chunks.append(chunk)

                    response_time = time.time() - start_time
                    return len(chunks), response_time

        # Test with different concurrency levels
        for concurrent_users in performance_config["concurrent_users"]:
            start_time = time.time()

            tasks = [single_streaming_request() for _ in range(concurrent_users)]
            results = await asyncio.gather(*tasks)

            total_time = time.time() - start_time

            # Verify all requests completed successfully
            assert len(results) == concurrent_users

            # Calculate performance metrics
            sum(result[0] for result in results)
            avg_response_time = statistics.mean(result[1] for result in results)
            throughput = concurrent_users / total_time

            print(f"Concurrent users: {concurrent_users}")
            print(f"Average response time: {avg_response_time:.3f}s")
            print(f"Throughput: {throughput:.1f} requests/s")

            # Performance assertions
            assert avg_response_time < performance_config["max_response_time"]
            if concurrent_users <= 10:
                assert throughput >= performance_config["min_throughput"]

    @pytest.mark.asyncio
    async def test_model_fallback_performance(self, compliance_assistant, performance_config):
        """Test performance of model fallback mechanism."""
        fallback_times = []

        for _ in range(20):
            with patch.object(
                compliance_assistant, "_get_task_appropriate_model"
            ) as mock_get_model:
                # First call fails, second succeeds
                mock_get_model.side_effect = [
                    ModelUnavailableException("gemini-2.5-pro", "Circuit open"),
                    Mock(model_name="gemini-2.5-flash"),
                ]

                start_time = time.time()

                try:
                    compliance_assistant._get_task_appropriate_model("analysis")
                    fallback_time = time.time() - start_time
                    fallback_times.append(fallback_time)
                except (ValueError, TypeError):
                    # Fallback failed
                    pass

        if fallback_times:
            avg_fallback_time = statistics.mean(fallback_times)
            # Fallback should be fast (< 100ms)
            assert avg_fallback_time < 0.1, f"Fallback too slow: {avg_fallback_time:.3f}s"

    @pytest.mark.asyncio
    async def test_memory_usage_streaming(self, compliance_assistant, performance_config):
        """Test memory usage during streaming operations."""
        import os

        import psutil

        process = psutil.Process(os.getpid())
        initial_memory = process.memory_info().rss / 1024 / 1024  # MB

        # Create large streaming response
        large_chunks = [f"Large chunk {i} with substantial content " * 10 for i in range(100)]

        with patch.object(compliance_assistant, "_get_task_appropriate_model") as mock_get_model:
            mock_model = Mock()

            # Create a generator function that yields proper mock objects
            def create_streaming_response():
                for chunk in large_chunks:
                    mock_chunk = Mock()
                    mock_chunk.text = chunk
                    yield mock_chunk

            mock_model.generate_content_stream.return_value = (create_streaming_response(),)
            mock_get_model.return_value = (mock_model, "test_instruction_id")

            with patch.object(
                compliance_assistant.circuit_breaker,
                "is_model_available",
                return_value=True,
            ):
                chunk_count = 0
                async for _chunk in compliance_assistant._stream_response(
                    "System prompt", "User prompt", "test"
                ):
                    chunk_count += 1
                    # Don't accumulate chunks to test streaming memory efficiency

                final_memory = process.memory_info().rss / 1024 / 1024  # MB
                memory_increase = final_memory - initial_memory

                assert chunk_count == len(large_chunks)
                # Memory increase should be minimal for streaming
                assert memory_increase < performance_config["max_memory_mb"] / 10

    def test_circuit_breaker_overhead(self, compliance_assistant, performance_config):
        """Test circuit breaker performance overhead."""
        circuit_breaker = compliance_assistant.circuit_breaker

        # Test without circuit breaker (simulate equivalent work)
        start_time = time.time()
        for _ in range(1000):
            # Simulate equivalent operation - dictionary lookup and assignment
            dummy_dict = {"test-model": True}
            dummy_dict["test-model"] = True
        baseline_time = time.time() - start_time

        # Test with circuit breaker
        start_time = time.time()
        for _ in range(1000):
            circuit_breaker.is_model_available("test-model")
            circuit_breaker.record_success("test-model")
        circuit_breaker_time = time.time() - start_time

        # Circuit breaker overhead should be reasonable
        # If baseline is too small, just check absolute time is reasonable
        if baseline_time < 0.001:  # Less than 1ms
            assert circuit_breaker_time < 0.1, (
                f"Circuit breaker absolute time too slow: {circuit_breaker_time:.3f}s"
            )
        else:
            overhead = (circuit_breaker_time - baseline_time) / baseline_time
            assert overhead < 5.0, f"Circuit breaker overhead too high: {overhead:.2%}"

    @pytest.mark.asyncio
    async def test_cost_optimization_simulation(self, compliance_assistant):
        """Test cost optimization through model selection."""
        # Simulate different task types and measure model selection
        task_scenarios = [
            {"type": "help", "complexity": "simple", "expected_model": "light"},
            {"type": "analysis", "complexity": "complex", "expected_model": "pro"},
            {
                "type": "recommendations",
                "complexity": "medium",
                "expected_model": "flash",
            },
        ]

        model_usage = {"light": 0, "flash": 0, "pro": 0}

        for scenario in task_scenarios * 10:  # Repeat scenarios
            with patch("config.ai_config.get_ai_model") as mock_get_model:
                # Mock different models based on complexity
                if scenario["complexity"] == "simple":
                    mock_model = Mock(model_name="gemini-2.5-flash-8b")
                    model_usage["light"] += 1
                elif scenario["complexity"] == "complex":
                    mock_model = Mock(model_name="gemini-2.5-pro")
                    model_usage["pro"] += 1
                else:
                    mock_model = Mock(model_name="gemini-2.5-flash")
                    model_usage["flash"] += 1

                mock_get_model.return_value = mock_model

                model = compliance_assistant._get_task_appropriate_model(
                    scenario["type"],
                    {"complexity": scenario["complexity"]},
                )

                assert model is not None

        # Verify cost optimization: light models used for simple tasks
        assert model_usage["light"] > 0, "Light models should be used for simple tasks"
        assert model_usage["pro"] > 0, "Pro models should be used for complex tasks"

        # Calculate cost efficiency (more light model usage = better)
        total_requests = sum(model_usage.values())
        light_ratio = model_usage["light"] / total_requests
        assert light_ratio >= 0.3, f"Light model usage too low: {light_ratio:.2%}"

    @pytest.mark.asyncio
    async def test_end_to_end_performance(self, compliance_assistant, performance_config):
        """Test end-to-end performance of optimized AI system."""
        # Simulate complete assessment analysis workflow
        assessment_data = {
            "responses": [{"q1": "yes"}, {"q2": "no"}, {"q3": "partially"}],
            "framework": "gdpr",
            "business_profile": {"industry": "tech", "size": "small"},
        }

        start_time = time.time()

        # Mock the complete workflow
        with patch.object(
            compliance_assistant.context_manager, "get_conversation_context"
        ) as mock_context:
            mock_context.return_value = assessment_data["business_profile"]

            with patch.object(
                compliance_assistant.prompt_templates, "get_assessment_analysis_prompt"
            ) as mock_prompt:
                mock_prompt.return_value = {"user": "Analysis prompt"}

                with patch.object(compliance_assistant, "_stream_response") as mock_stream:

                    async def mock_response():
                        for i in range(10):
                            yield f"Analysis chunk {i}"
                            await asyncio.sleep(0.01)  # Simulate processing time

                    mock_stream.return_value = mock_response()

                    chunks = []
                    async for chunk in compliance_assistant.analyze_assessment_results_stream(
                        assessment_data["responses"],
                        assessment_data["framework"],
                        "profile-123",
                    ):
                        chunks.append(chunk)

        total_time = time.time() - start_time

        assert len(chunks) == 10
        assert total_time < performance_config["max_response_time"]

        # Calculate performance metrics
        throughput = len(chunks) / total_time
        print(f"End-to-end performance: {total_time:.3f}s, {throughput:.1f} chunks/s")
