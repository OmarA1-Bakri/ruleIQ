"""

Latency smoke tests for LangGraph compliance agent.
Validates P95 ≤ 2.5s SLO compliance and performance benchmarks.
"""

import pytest
import asyncio
import time
import statistics
from typing import List, Dict, Any, Callable
from unittest.mock import AsyncMock
from uuid import uuid4

from langgraph_agent.graph.app import invoke_graph, stream_graph
from langgraph_agent.agents.tool_manager import ToolManager
from langgraph_agent.core.constants import SLO_P95_LATENCY_MS
from langgraph_agent.evals.metrics import (
    LatencyEvaluator,
    LatencyMetrics,
    run_latency_smoke_test,
)


class LatencyTestHelper:
    """Helper class for latency testing utilities."""

    @staticmethod
    def time_async_function(func: Callable) -> Callable:
        """Decorator to time async function execution."""

        async def wrapper(*args, **kwargs):
            start_time = time.time()
            result = await func(*args, **kwargs)
            end_time = time.time()
            execution_time_ms = (end_time - start_time) * 1000

            # Add timing to result if it's a dict
            if isinstance(result, dict):
                result["_execution_time_ms"] = execution_time_ms

            return result, execution_time_ms

        return wrapper

    @staticmethod
    def calculate_percentiles(latencies: List[float]) -> Dict[str, float]:
        """Calculate latency percentiles."""
        if not latencies:
            return {}

        sorted_latencies = sorted(latencies)
        return {
            "p50": statistics.median(sorted_latencies),
            "p95": sorted_latencies[int(0.95 * len(sorted_latencies))],
            "p99": sorted_latencies[int(0.99 * len(sorted_latencies))],
            "mean": statistics.mean(sorted_latencies),
            "max": max(sorted_latencies),
            "min": min(sorted_latencies),
        }

    @staticmethod
    def generate_test_inputs() -> List[Dict[str, Any]]:
        """Generate varied test inputs for latency testing."""
        test_inputs = [
            # Simple GDPR question
            {
                "company_id": uuid4(),
                "user_input": "What GDPR obligations apply to my business?",
                "autonomy_level": 2,
            },
            # Complex multi-framework question
            {
                "company_id": uuid4(),
                "user_input": "I need a comprehensive compliance analysis for my fintech startup covering GDPR, PCI DSS, and UK financial regulations.",
                "autonomy_level": 3,
            },
            # Evidence collection request
            {
                "company_id": uuid4(),
                "user_input": "Help me collect and organize compliance evidence for a regulatory audit.",
                "autonomy_level": 2,
            },
            # Legal review request
            {
                "company_id": uuid4(),
                "user_input": "I need legal review of my privacy policy and data processing agreements.",
                "autonomy_level": 1,
            },
            # Short simple question
            {
                "company_id": uuid4(),
                "user_input": "Do I need a DPO?",
                "autonomy_level": 2,
            },
        ]
        return test_inputs


@pytest.mark.asyncio
class TestGraphLatency:
    """Test graph execution latency."""

    async def test_graph_invocation_latency_single(self):
        """Test single graph invocation latency."""
        # Mock compiled graph with realistic delay
        mock_graph = AsyncMock()

        async def mock_invoke(state, config=None):
            # Simulate realistic processing time (100-300ms)
            await asyncio.sleep(0.15)  # 150ms
            state["current_node"] = "compliance_analyzer"
            state["next_node"] = "END"
            return state

        mock_graph.ainvoke.side_effect = mock_invoke

        company_id = uuid4()
        start_time = time.time()

        result = await invoke_graph(
            compiled_graph=mock_graph,
            company_id=company_id,
            user_input="Test GDPR question",
        )

        end_time = time.time()
        latency_ms = (end_time - start_time) * 1000

        # Should complete within SLO
        assert latency_ms < SLO_P95_LATENCY_MS
        assert "latency_ms" in result
        assert result["latency_ms"] > 0

        # Should be reasonably fast for simple operations
        assert latency_ms < 1000  # Under 1 second for mock

    async def test_graph_invocation_latency_batch(self):
        """Test batch graph invocations for P95 measurement."""
        mock_graph = AsyncMock()

        # Simulate variable latency (100-500ms)
        latency_variations = [0.1, 0.15, 0.2, 0.25, 0.3, 0.35, 0.4, 0.45, 0.5]
        call_count = 0

        async def mock_invoke_variable(state, config=None):
            nonlocal call_count
            delay = latency_variations[call_count % len(latency_variations)]
            call_count += 1
            await asyncio.sleep(delay)
            state["current_node"] = "compliance_analyzer"
            return state

        mock_graph.ainvoke.side_effect = mock_invoke_variable

        # Run multiple invocations
        latencies = []
        test_inputs = LatencyTestHelper.generate_test_inputs()[:5]  # First 5 inputs

        for test_input in test_inputs:
            start_time = time.time()

            await invoke_graph(compiled_graph=mock_graph, **test_input)

            end_time = time.time()
            latency_ms = (end_time - start_time) * 1000
            latencies.append(latency_ms)

        # Calculate percentiles
        percentiles = LatencyTestHelper.calculate_percentiles(latencies)

        # P95 should meet SLO
        assert percentiles["p95"] < SLO_P95_LATENCY_MS
        assert percentiles["mean"] < SLO_P95_LATENCY_MS * 0.5  # Mean should be much lower

        print(f"Latency results: P50={percentiles['p50']:.1f}ms, P95={percentiles['p95']:.1f}ms")

    async def test_streaming_latency_first_token(self):
        """Test streaming latency for first token (time to first byte)."""
        mock_graph = AsyncMock()

        # Mock streaming with delays
        async def mock_stream(state, config=None):
            # First chunk should come quickly
            await asyncio.sleep(0.05)  # 50ms to first token
            yield {"chunk": 1, "type": "start"}

            # Subsequent chunks
            await asyncio.sleep(0.1)
            yield {"chunk": 2, "type": "processing"}

            await asyncio.sleep(0.1)
            yield {"chunk": 3, "type": "complete"}

        mock_graph.astream.side_effect = mock_stream

        company_id = uuid4()
        start_time = time.time()
        first_token_time = None

        chunk_count = 0
        async for _chunk in stream_graph(
            compiled_graph=mock_graph,
            company_id=company_id,
            user_input="Test streaming",
        ):
            if first_token_time is None:
                first_token_time = time.time()
            chunk_count += 1

        # Time to first token should be very fast
        ttft_ms = (first_token_time - start_time) * 1000
        assert ttft_ms < 200  # First token within 200ms
        assert chunk_count == 3

        print(f"Time to first token: {ttft_ms:.1f}ms")

    async def test_concurrent_graph_executions(self):
        """Test latency under concurrent load."""
        mock_graph = AsyncMock()

        async def mock_invoke_concurrent(state, config=None):
            # Simulate realistic processing with some variability
            await asyncio.sleep(0.1 + (hash(config.configurable["company_id"]) % 100) / 1000)
            state["current_node"] = "compliance_analyzer"
            return state

        mock_graph.ainvoke.side_effect = mock_invoke_concurrent

        # Create multiple concurrent invocations
        test_inputs = LatencyTestHelper.generate_test_inputs()

        start_time = time.time()

        # Run all invocations concurrently
        tasks = [
            invoke_graph(compiled_graph=mock_graph, **test_input) for test_input in test_inputs
        ]

        results = await asyncio.gather(*tasks)
        end_time = time.time()

        # Total time for all concurrent requests
        total_time_ms = (end_time - start_time) * 1000

        # Should complete all within reasonable time (not SLO * count)
        assert total_time_ms < 1000  # All 5 concurrent requests under 1s
        assert len(results) == len(test_inputs)

        # All individual latencies should be reasonable
        for result in results:
            assert result["latency_ms"] < SLO_P95_LATENCY_MS

        print(f"Concurrent execution time: {total_time_ms:.1f}ms for {len(test_inputs)} requests")


@pytest.mark.asyncio
class TestToolLatency:
    """Test tool execution latency."""

    async def test_tool_manager_latency(self):
        """Test individual tool execution latency."""
        manager = ToolManager("test_secret")
        company_id = uuid4()
        thread_id = "latency_test"

        # Test different tools
        tool_tests = [
            {
                "tool_name": "compliance_analysis",
                "kwargs": {
                    "business_profile": {"industry": "tech"},
                    "frameworks": ["GDPR"],
                },
            },
            {
                "tool_name": "document_retrieval",
                "kwargs": {
                    "query": "GDPR template",
                    "framework": "GDPR",
                    "doc_type": "template",
                },
            },
            {"tool_name": "evidence_collection", "kwargs": {"frameworks": ["GDPR"]}},
        ]

        latencies = []

        for tool_test in tool_tests:
            start_time = time.time()

            result = await manager.execute_tool(
                company_id=company_id, thread_id=thread_id, **tool_test
            )

            end_time = time.time()
            latency_ms = (end_time - start_time) * 1000
            latencies.append(latency_ms)

            assert result.success
            assert result.execution_time_ms > 0

            # Individual tool should be fast
            assert latency_ms < 500  # Under 500ms per tool

        # Average tool latency should be reasonable
        avg_latency = statistics.mean(latencies)
        assert avg_latency < 200  # Average under 200ms

        print(f"Tool latencies: {[f'{l:.1f}ms' for l in latencies]}, avg: {avg_latency:.1f}ms")

    async def test_parallel_tool_execution_latency(self):
        """Test parallel tool execution latency."""
        manager = ToolManager("test_secret")
        company_id = uuid4()
        thread_id = "parallel_test"

        tool_configs = [
            {
                "tool": "compliance_analysis",
                "kwargs": {
                    "business_profile": {"industry": "tech"},
                    "frameworks": ["GDPR"],
                },
            },
            {
                "tool": "document_retrieval",
                "kwargs": {
                    "query": "GDPR",
                    "framework": "GDPR",
                    "doc_type": "template",
                },
            },
            {"tool": "evidence_collection", "kwargs": {"frameworks": ["GDPR"]}},
        ]

        start_time = time.time()

        results = await manager.execute_parallel_tools(
            tool_configs=tool_configs, company_id=company_id, thread_id=thread_id
        )

        end_time = time.time()
        parallel_latency_ms = (end_time - start_time) * 1000

        # Parallel execution should be faster than sequential
        assert len(results) == 3
        assert all(r.success for r in results)

        # Should complete much faster than sum of individual times
        assert parallel_latency_ms < 300  # Under 300ms for 3 parallel tools

        print(f"Parallel tool execution: {parallel_latency_ms:.1f}ms for {len(tool_configs)} tools")

    async def test_tool_chain_latency(self):
        """Test tool chain execution latency."""
        manager = ToolManager("test_secret")
        company_id = uuid4()
        thread_id = "chain_test"

        tool_sequence = [
            {
                "tool": "compliance_analysis",
                "kwargs": {
                    "business_profile": {"industry": "retail"},
                    "frameworks": ["GDPR"],
                },
            },
            {"tool": "evidence_collection", "kwargs": {"frameworks": ["GDPR"]}},
            {
                "tool": "report_generation",
                "kwargs": {
                    "report_type": "compliance_assessment",
                    "frameworks": ["GDPR"],
                },
            },
        ]

        start_time = time.time()

        results = await manager.execute_tool_chain(
            tool_sequence=tool_sequence, company_id=company_id, thread_id=thread_id
        )

        end_time = time.time()
        chain_latency_ms = (end_time - start_time) * 1000

        # Chain execution should complete within reasonable time
        assert len(results) == 3
        assert all(r.success for r in results)
        assert chain_latency_ms < 1000  # Under 1s for 3-tool chain

        print(f"Tool chain execution: {chain_latency_ms:.1f}ms for {len(tool_sequence)} tools")


@pytest.mark.asyncio
class TestLatencyEvaluator:
    """Test the LatencyEvaluator utility."""

    def test_latency_evaluator_basic(self):
        """Test basic LatencyEvaluator functionality."""
        evaluator = LatencyEvaluator(slo_p95_ms=2000)

        # Add sample latencies
        sample_latencies = [100, 150, 200, 250, 300, 350, 400, 450, 500, 1000]
        for latency in sample_latencies:
            evaluator.add_sample(latency)

        # Calculate metrics
        metrics = evaluator.calculate_percentiles()

        assert metrics.samples == 10
        assert metrics.p50_ms == 275.0  # Median of sample
        assert metrics.p95_ms <= 950.0  # 95th percentile
        assert metrics.mean_ms == 370.0  # Mean of samples
        assert metrics.max_ms == 1000.0
        assert metrics.min_ms == 100.0

        # Should meet SLO
        assert metrics.meets_slo(2000)

    def test_latency_evaluator_slo_violation(self):
        """Test SLO violation detection."""
        evaluator = LatencyEvaluator(slo_p95_ms=500)

        # Add latencies that violate SLO
        violation_latencies = [100, 200, 300, 400, 500, 600, 700, 800, 900, 1000]
        for latency in violation_latencies:
            evaluator.add_sample(latency)

        metrics = evaluator.calculate_percentiles()

        # Should not meet SLO
        assert not metrics.meets_slo(500)
        assert metrics.p95_ms > 500

        # Evaluate result
        result = evaluator.evaluate()
        assert result.metric_name == "latency_slo"
        assert result.score < 1.0  # Score should be degraded
        assert not result.details["meets_slo"]
        assert result.details["slo_violation_ratio"] > 0

    def test_latency_evaluator_evaluation_result(self):
        """Test LatencyEvaluator evaluation result format."""
        evaluator = LatencyEvaluator(slo_p95_ms=2500)

        # Add good latencies
        good_latencies = [50, 100, 150, 200, 250, 300, 350, 400, 450, 500]
        for latency in good_latencies:
            evaluator.add_sample(latency)

        result = evaluator.evaluate()

        # Check result structure
        assert result.metric_name == "latency_slo"
        assert 0.0 <= result.score <= 1.0
        assert isinstance(result.details, dict)

        # Check required details
        required_keys = [
            "p50_ms",
            "p95_ms",
            "p99_ms",
            "mean_ms",
            "max_ms",
            "min_ms",
            "samples",
            "slo_p95_ms",
            "meets_slo",
            "slo_violation_ratio",
        ]
        for key in required_keys:
            assert key in result.details

        # Should meet SLO with good latencies
        assert result.score == 1.0
        assert result.details["meets_slo"]


@pytest.mark.asyncio
class TestSmokeTestRunner:
    """Test the smoke test runner utility."""

    async def test_run_latency_smoke_test(self):
        """Test the latency smoke test runner."""

        # Mock graph function with realistic behavior
        async def mock_graph_function(company_id, user_input, **kwargs):
            # Simulate variable processing time
            base_delay = 0.05  # 50ms base
            complexity_factor = len(user_input) / 1000  # More complex = slower
            await asyncio.sleep(base_delay + complexity_factor)

            return {
                "company_id": company_id,
                "result": f"Processed: {user_input[:20]}...",
                "success": True,
            }

        test_inputs = [
            {"company_id": uuid4(), "user_input": "Simple GDPR question"},
            {
                "company_id": uuid4(),
                "user_input": "More complex compliance analysis request",
            },
            {"company_id": uuid4(), "user_input": "Short query"},
        ]

        # Run smoke test
        metrics = await run_latency_smoke_test(
            graph_function=mock_graph_function,
            test_inputs=test_inputs,
            target_p95_ms=1000,  # 1s target for test
            num_iterations=5,
        )

        # Verify metrics
        assert isinstance(metrics, LatencyMetrics)
        assert metrics.samples == 15  # 3 inputs * 5 iterations
        assert metrics.p95_ms > 0
        assert metrics.mean_ms > 0
        assert metrics.max_ms >= metrics.p95_ms
        assert metrics.min_ms <= metrics.mean_ms

        # Should meet test SLO
        assert metrics.meets_slo(1000)

        print(f"Smoke test results: P95={metrics.p95_ms:.1f}ms, Mean={metrics.mean_ms:.1f}ms")

    async def test_smoke_test_with_failures(self):
        """Test smoke test handling of failures."""
        call_count = 0

        async def failing_graph_function(company_id, user_input, **kwargs):
            nonlocal call_count
            call_count += 1

            # Fail every 3rd call
            if call_count % 3 == 0:
                await asyncio.sleep(0.02)  # Still takes time
                raise Exception("Simulated failure")

            await asyncio.sleep(0.05)
            return {"result": "success"}

        test_inputs = [{"company_id": uuid4(), "user_input": "test"}]

        # Should handle failures gracefully
        metrics = await run_latency_smoke_test(
            graph_function=failing_graph_function,
            test_inputs=test_inputs,
            target_p95_ms=1000,
            num_iterations=6,  # Will have 2 failures
        )

        # Should still collect timing data
        assert metrics.samples == 6  # All attempts recorded
        assert metrics.p95_ms > 0


@pytest.mark.slow
@pytest.mark.asyncio
class TestRealisticLatencyBenchmarks:
    """Realistic latency benchmarks (marked slow for optional execution)."""

    async def test_end_to_end_latency_benchmark(self):
        """End-to-end latency benchmark with realistic graph."""
        # This test would use a real compiled graph
        # For now, we'll mock but with realistic delays

        mock_graph = AsyncMock()

        async def realistic_invoke(state, config=None):
            user_input = state["messages"][0].content

            # Simulate realistic processing times based on complexity
            if "simple" in user_input.lower():
                await asyncio.sleep(0.3)  # 300ms
            elif "complex" in user_input.lower():
                await asyncio.sleep(0.8)  # 800ms
            else:
                await asyncio.sleep(0.5)  # 500ms default

            state["current_node"] = "compliance_analyzer"
            return state

        mock_graph.ainvoke.side_effect = realistic_invoke

        # Realistic test cases
        test_cases = [
            "Simple GDPR question",
            "Complex multi-framework compliance analysis",
            "Standard evidence collection request",
            "Legal review requirement",
            "Quick compliance check",
        ]

        latencies = []

        for _i, test_case in enumerate(test_cases * 4):  # 20 total tests
            start_time = time.time()

            await invoke_graph(compiled_graph=mock_graph, company_id=uuid4(), user_input=test_case)

            end_time = time.time()
            latency_ms = (end_time - start_time) * 1000
            latencies.append(latency_ms)

        # Calculate realistic benchmarks
        percentiles = LatencyTestHelper.calculate_percentiles(latencies)

        print("\nRealistic Latency Benchmark Results:")
        print(f"  P50: {percentiles['p50']:.1f}ms")
        print(f"  P95: {percentiles['p95']:.1f}ms")
        print(f"  P99: {percentiles['p99']:.1f}ms")
        print(f"  Mean: {percentiles['mean']:.1f}ms")
        print(f"  Max: {percentiles['max']:.1f}ms")
        print(f"  SLO Target: {SLO_P95_LATENCY_MS}ms")
        print(f"  SLO Compliance: {'✅' if percentiles['p95'] <= SLO_P95_LATENCY_MS else '❌'}")

        # Assert SLO compliance
        assert percentiles["p95"] <= SLO_P95_LATENCY_MS, (
            f"P95 latency {percentiles['p95']:.1f}ms exceeds SLO {SLO_P95_LATENCY_MS}ms"
        )

        # Additional performance assertions
        assert percentiles["mean"] <= SLO_P95_LATENCY_MS * 0.6, (
            "Mean latency should be well below P95 SLO"
        )
        assert percentiles["p50"] <= SLO_P95_LATENCY_MS * 0.4, (
            "P50 latency should be much lower than SLO"
        )


# Performance test configuration
pytestmark = [pytest.mark.asyncio, pytest.mark.performance]


def test_slo_constants_reasonable():
    """Test that SLO constants are reasonable for user experience."""
    # P95 ≤ 2.5s is reasonable for complex AI operations
    assert SLO_P95_LATENCY_MS == 2500
    assert SLO_P95_LATENCY_MS <= 3000  # Not too slow
    assert SLO_P95_LATENCY_MS >= 1000  # Not unrealistically fast


if __name__ == "__main__":
    # Run latency tests directly
    pytest.main([__file__, "-v", "--tb=short"])
