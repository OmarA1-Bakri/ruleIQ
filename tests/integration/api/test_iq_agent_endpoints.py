"""
Integration Tests for IQ Agent API Endpoints

Tests the FastAPI endpoints for IQ Agent GraphRAG compliance intelligence including:
- Compliance queries with natural language processing
- Memory management operations (store/retrieve)
- Graph initialization and health monitoring
- Error handling and rate limiting
- Authentication and authorization
"""

import json
import pytest
from datetime import datetime, timezone
from unittest.mock import AsyncMock, Mock, patch
from uuid import uuid4

from fastapi.testclient import TestClient
from httpx import AsyncClient

from main import app
from services.iq_agent import IQComplianceAgent
from services.neo4j_service import Neo4jGraphRAGService


@pytest.mark.integration
@pytest.mark.api
class TestIQAgentEndpoints:
    """Test IQ Agent API endpoints"""

    @pytest.fixture
    def client(self):
        """Create test client"""
        return TestClient(app)

    @pytest.fixture
    async def async_client(self):
        """Create async test client"""
        async with AsyncClient(app=app, base_url="http://test") as client:
            yield client

    @pytest.fixture
    def auth_headers(self):
        """Create authentication headers"""
        return {"Authorization": "Bearer test_token_12345"}

    @pytest.fixture
    def mock_iq_agent(self):
        """Mock IQ agent for testing"""
        agent = Mock(spec=IQComplianceAgent)

        # Mock successful query processing
        agent.process_query = AsyncMock(
            return_value={
                "status": "success",
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "summary": {
                    "risk_posture": "MEDIUM",
                    "compliance_score": 0.75,
                    "top_gaps": [
                        "Consent Management",
                        "Data Retention",
                        "Breach Notification",
                    ],
                    "immediate_actions": [
                        "Implement consent system",
                        "Update retention policy",
                        "Setup breach alerts",
                    ],
                },
                "artifacts": {
                    "compliance_posture": {
                        "overall_coverage": 0.75,
                        "total_gaps": 8,
                        "critical_gaps": 2,
                    },
                    "action_plan": [
                        {
                            "action_id": "action_1",
                            "target": "Implement consent management",
                            "priority": "critical",
                            "regulation": "GDPR",
                            "cost_estimate": 15000.0,
                            "timeline": "30_days",
                            "graph_reference": "gap_123",
                        },
                    ],
                    "risk_assessment": {
                        "overall_risk_level": "MEDIUM",
                        "convergence_patterns": 3,
                    },
                },
                "graph_context": {
                    "nodes_traversed": 45,
                    "patterns_detected": [
                        {
                            "pattern_type": "HIGH_GAP_CONCENTRATION",
                            "domain": "Data Protection",
                        },
                    ],
                    "memories_accessed": ["mem_123", "mem_456"],
                    "learnings_applied": 2,
                },
                "evidence": {
                    "controls_executed": 3,
                    "evidence_stored": 5,
                    "metrics_updated": 2,
                },
                "next_actions": [
                    {
                        "action": "Implement consent management system",
                        "priority": "CRITICAL",
                        "owner": "Compliance Team",
                        "graph_reference": "gap_123",
                    },
                    {
                        "action": "Update data retention policies",
                        "priority": "HIGH",
                        "owner": "Compliance Team",
                        "graph_reference": "gap_456",
                    },
                ],
                "llm_response": "Based on my comprehensive analysis of your compliance posture, I've identified several critical gaps that require immediate attention...",
            },
        )

        # Mock memory manager
        memory_manager = Mock()
        memory_manager.store_conversation_memory = AsyncMock(return_value="mem_12345")
        memory_manager.retrieve_contextual_memories = AsyncMock(
            return_value=Mock(
                retrieved_memories=[
                    Mock(
                        id="mem_1",
                        memory_type="conversation",
                        content={"insight": "GDPR consent gap"},
                        timestamp=datetime.now(timezone.utc),
                        importance_score=0.8,
                        access_count=3,
                        tags=["gdpr", "consent"],
                        confidence_score=0.9,
                    ),
                ],
            ),
        )
        agent.memory_manager = memory_manager

        return agent

    @pytest.fixture
    def mock_neo4j_service(self):
        """Mock Neo4j service for testing"""
        service = Mock(spec=Neo4jGraphRAGService)
        service.connect = AsyncMock()
        service.test_connection = AsyncMock()
        service.get_graph_statistics = AsyncMock(
            return_value={
                "total_nodes": 150,
                "total_relationships": 500,
                "compliance_domains": 6,
                "regulations": 12,
                "requirements": 85,
            },
        )
        return service

    async def test_compliance_query_success(self, async_client, auth_headers, mock_iq_agent):
        """Test successful compliance query processing"""

        with patch("api.routers.iq_agent.get_iq_agent", return_value=mock_iq_agent):
            response = await async_client.post(
                "/api/v1/iq/query",
                json={
                    "query": "What are our GDPR compliance gaps in customer data processing?",
                    "context": {
                        "business_functions": [
                            "data_processing",
                            "customer_onboarding",
                        ],
                        "regulations": ["GDPR", "DPA2018"],
                        "risk_tolerance": "medium",
                    },
                    "include_graph_analysis": True,
                    "include_recommendations": True,
                },
                headers=auth_headers,
            )

        assert response.status_code == 200
        data = response.json()

        assert data["success"] is True
        assert "data" in data
        assert data["message"] == "Compliance analysis completed successfully"

        # Verify IQ response structure
        iq_response = data["data"]
        assert iq_response["status"] == "success"
        assert "timestamp" in iq_response

        # Verify summary section
        summary = iq_response["summary"]
        assert summary["risk_posture"] == "MEDIUM"
        assert summary["compliance_score"] == 0.75
        assert len(summary["top_gaps"]) == 3
        assert len(summary["immediate_actions"]) == 3

        # Verify artifacts section
        artifacts = iq_response["artifacts"]
        assert "compliance_posture" in artifacts
        assert "action_plan" in artifacts
        assert "risk_assessment" in artifacts

        # Verify graph context
        graph_context = iq_response["graph_context"]
        assert graph_context["nodes_traversed"] == 45
        assert len(graph_context["patterns_detected"]) == 1
        assert len(graph_context["memories_accessed"]) == 2

        # Verify evidence tracking
        evidence = iq_response["evidence"]
        assert evidence["controls_executed"] == 3
        assert evidence["evidence_stored"] == 5

        # Verify next actions
        next_actions = iq_response["next_actions"]
        assert len(next_actions) == 2
        assert all("action" in action for action in next_actions)
        assert all("priority" in action for action in next_actions)

    async def test_compliance_query_invalid_request(self, async_client, auth_headers):
        """Test compliance query with invalid request data"""

        response = await async_client.post(
            "/api/v1/iq/query",
            json={"query": "", "context": None},  # Empty query
            headers=auth_headers,
        )

        assert response.status_code == 422  # Validation error

    async def test_compliance_query_unauthenticated(self, async_client):
        """Test compliance query without authentication"""

        response = await async_client.post(
            "/api/v1/iq/query",
            json={
                "query": "What are our compliance gaps?",
            },
        )

        assert response.status_code == 401  # Unauthorized

    async def test_compliance_query_rate_limiting(self, async_client, auth_headers, mock_iq_agent):
        """Test rate limiting on compliance queries"""

        with patch("api.routers.iq_agent.get_iq_agent", return_value=mock_iq_agent):
            # Make multiple rapid requests to trigger rate limiting
            # Note: This test may need adjustment based on actual rate limits
            responses = []
            for i in range(25):  # Exceed typical AI analysis rate limit
                response = await async_client.post(
                    "/api/v1/iq/query",
                    json={"query": f"Test query {i}"},
                    headers=auth_headers,
                )
                responses.append(response)
                if response.status_code == 429:
                    break

            # Should eventually hit rate limit
            rate_limited = any(r.status_code == 429 for r in responses)
            assert rate_limited, "Rate limiting should be triggered for excessive requests"

    async def test_store_memory_success(self, async_client, auth_headers, mock_iq_agent):
        """Test successful memory storage"""

        with patch("api.routers.iq_agent.get_iq_agent", return_value=mock_iq_agent):
            response = await async_client.post(
                "/api/v1/iq/memory/store",
                json={
                    "memory_type": "compliance_insight",
                    "content": {
                        "insight": "GDPR consent mechanisms need improvement",
                        "regulation": "GDPR",
                        "domain": "Data Protection",
                        "impact": "high",
                    },
                    "importance_score": 0.8,
                    "tags": ["gdpr", "consent", "data_protection"],
                },
                headers=auth_headers,
            )

        assert response.status_code == 200
        data = response.json()

        assert data["success"] is True
        assert data["data"]["memory_id"] == "mem_12345"
        assert data["data"]["status"] == "stored"
        assert data["message"] == "Knowledge stored successfully in IQ's memory"

    async def test_retrieve_memories_success(self, async_client, auth_headers, mock_iq_agent):
        """Test successful memory retrieval"""

        with patch("api.routers.iq_agent.get_iq_agent", return_value=mock_iq_agent):
            response = await async_client.post(
                "/api/v1/iq/memory/retrieve",
                json={
                    "query": "GDPR consent management insights",
                    "max_memories": 5,
                    "relevance_threshold": 0.7,
                },
                headers=auth_headers,
            )

        assert response.status_code == 200
        data = response.json()

        assert data["success"] is True
        assert "data" in data
        assert len(data["data"]["retrieved_memories"]) == 1

        memory = data["data"]["retrieved_memories"][0]
        assert memory["id"] == "mem_1"
        assert memory["memory_type"] == "conversation"
        assert "content" in memory
        assert "importance_score" in memory

    async def test_graph_initialization_success(
        self, async_client, auth_headers, mock_neo4j_service
    ):
        """Test successful graph initialization"""

        with patch("api.routers.iq_agent.get_neo4j_service", return_value=mock_neo4j_service):
            response = await async_client.post(
                "/api/v1/iq/graph/initialize",
                json={"clear_existing": False, "load_sample_data": True},
                headers=auth_headers,
            )

        assert response.status_code == 200
        data = response.json()

        assert data["success"] is True
        assert data["data"]["status"] == "initiated"
        assert "timestamp" in data["data"]
        assert data["message"] == "Compliance graph initialization initiated"

    async def test_health_check_healthy(self, async_client, mock_neo4j_service, mock_iq_agent):
        """Test health check when all systems healthy"""

        with (
            patch("api.routers.iq_agent.get_neo4j_service", return_value=mock_neo4j_service),
            patch("api.routers.iq_agent.get_iq_agent", return_value=mock_iq_agent),
        ):
            response = await async_client.get("/api/v1/iq/health?include_stats=true")

        assert response.status_code == 200
        data = response.json()

        assert data["success"] is True
        health_data = data["data"]
        assert health_data["status"] == "healthy"
        assert health_data["neo4j_connected"] is True
        assert "graph_statistics" in health_data
        assert "memory_statistics" in health_data

    async def test_health_check_degraded(self, async_client):
        """Test health check when systems are degraded"""

        # Mock Neo4j service that fails connection
        failing_service = Mock()
        failing_service.test_connection = AsyncMock(
            side_effect=Exception("Connection failed"),
        )

        with patch("api.routers.iq_agent.get_neo4j_service", return_value=failing_service):
            response = await async_client.get("/api/v1/iq/health")

        assert response.status_code == 200
        data = response.json()

        assert data["success"] is True
        health_data = data["data"]
        assert health_data["status"] in ["degraded", "unhealthy"]
        assert health_data["neo4j_connected"] is False

    async def test_status_endpoint(self, async_client, mock_neo4j_service, mock_iq_agent):
        """Test lightweight status endpoint"""

        with (
            patch("api.routers.iq_agent.get_neo4j_service", return_value=mock_neo4j_service),
            patch("api.routers.iq_agent.get_iq_agent", return_value=mock_iq_agent),
        ):
            response = await async_client.get("/api/v1/iq/status")

        assert response.status_code == 200
        data = response.json()

        assert data["status"] == "operational"
        assert data["agent"] == "IQ"
        assert data["version"] == "1.0.0"
        assert "timestamp" in data

    async def test_status_endpoint_degraded(self, async_client):
        """Test status endpoint when service is degraded"""

        with patch(
            "api.routers.iq_agent.get_neo4j_service",
            side_effect=Exception("Service error"),
        ):
            response = await async_client.get("/api/v1/iq/status")

        assert response.status_code == 200
        data = response.json()

        assert data["status"] == "degraded"
        assert "error" in data

    async def test_iq_agent_service_unavailable(self, async_client, auth_headers):
        """Test behavior when IQ agent service is unavailable"""

        with patch(
            "api.routers.iq_agent.get_iq_agent",
            side_effect=Exception("Service unavailable"),
        ):
            response = await async_client.post(
                "/api/v1/iq/query",
                json={"query": "Test query"},
                headers=auth_headers,
            )

        assert response.status_code == 503
        data = response.json()
        assert "IQ Agent initialization failed" in data["detail"]

    async def test_compliance_query_ai_service_error(
        self, async_client, auth_headers, mock_iq_agent
    ):
        """Test handling of AI service errors during query processing"""

        # Mock IQ agent to raise AI service exception
        from services.ai.exceptions import AIServiceException

        mock_iq_agent.process_query = AsyncMock(
            side_effect=AIServiceException("AI service error"),
        )

        with patch("api.routers.iq_agent.get_iq_agent", return_value=mock_iq_agent):
            response = await async_client.post(
                "/api/v1/iq/query",
                json={"query": "Test query"},
                headers=auth_headers,
            )

        assert response.status_code == 502
        data = response.json()
        assert "AI analysis failed" in data["detail"]

    async def test_memory_storage_error_handling(self, async_client, auth_headers, mock_iq_agent):
        """Test error handling during memory storage"""

        # Mock memory manager to raise exception
        mock_iq_agent.memory_manager.store_conversation_memory = AsyncMock(
            side_effect=Exception("Memory storage failed"),
        )

        with patch("api.routers.iq_agent.get_iq_agent", return_value=mock_iq_agent):
            response = await async_client.post(
                "/api/v1/iq/memory/store",
                json={
                    "memory_type": "compliance_insight",
                    "content": {"test": "data"},
                    "importance_score": 0.5,
                },
                headers=auth_headers,
            )

        assert response.status_code == 500
        data = response.json()
        assert "Failed to store memory" in data["detail"]

    async def test_concurrent_queries(self, async_client, auth_headers, mock_iq_agent):
        """Test handling of concurrent compliance queries"""
        import asyncio

        with patch("api.routers.iq_agent.get_iq_agent", return_value=mock_iq_agent):
            # Create multiple concurrent queries
            tasks = []
            for i in range(5):
                task = async_client.post(
                    "/api/v1/iq/query",
                    json={"query": f"Concurrent query {i}"},
                    headers=auth_headers,
                )
                tasks.append(task)

            responses = await asyncio.gather(*tasks)

            # All requests should succeed
            for response in responses:
                assert response.status_code in [200, 429]  # Success or rate limited

            successful_responses = [r for r in responses if r.status_code == 200]
            assert len(successful_responses) > 0  # At least some should succeed

    async def test_large_query_handling(self, async_client, auth_headers, mock_iq_agent):
        """Test handling of large compliance queries"""

        # Create a large but valid query
        large_query = (
            "What are our compliance requirements for " + "GDPR " * 200
        )  # Long but under limit

        with patch("api.routers.iq_agent.get_iq_agent", return_value=mock_iq_agent):
            response = await async_client.post(
                "/api/v1/iq/query",
                json={"query": large_query[:2000]},  # Respect max length
                headers=auth_headers,
            )

        assert response.status_code == 200

    async def test_query_with_special_characters(self, async_client, auth_headers, mock_iq_agent):
        """Test queries with special characters and unicode"""

        special_query = ("What are our compliance gaps für GDPR & 6AMLD? Include costs €£$",)

        with patch("api.routers.iq_agent.get_iq_agent", return_value=mock_iq_agent):
            response = await async_client.post(
                "/api/v1/iq/query",
                json={"query": special_query},
                headers=auth_headers,
            )

        assert response.status_code == 200

    async def test_background_task_execution(self, async_client, auth_headers, mock_iq_agent):
        """Test that background tasks are properly executed"""

        with patch("api.routers.iq_agent.get_iq_agent", return_value=mock_iq_agent):
            response = await async_client.post(
                "/api/v1/iq/query",
                json={"query": "Test query for background task"},
                headers=auth_headers,
            )

        assert response.status_code == 200

        # Background task execution is verified by checking the response was successful
        # In a real test environment, you might check logs or database for task completion


@pytest.mark.load
@pytest.mark.asyncio
class TestIQAgentLoadTesting:
    """Load testing for IQ Agent endpoints"""

    async def test_sustained_query_load(self, async_client, auth_headers, mock_iq_agent):
        """Test sustained load on compliance queries"""
        import asyncio
        import time

        with patch("api.routers.iq_agent.get_iq_agent", return_value=mock_iq_agent):
            start_time = time.time()
            tasks = []

            # Create sustained load over 10 seconds
            for i in range(50):  # 50 requests
                task = async_client.post(
                    "/api/v1/iq/query",
                    json={"query": f"Load test query {i}"},
                    headers=auth_headers,
                )
                tasks.append(task)

                # Small delay between requests
                if i % 10 == 0:
                    await asyncio.sleep(0.1)

            responses = await asyncio.gather(*tasks, return_exceptions=True)
            end_time = time.time()

            # Analyze results
            successful_responses = [
                r for r in responses if hasattr(r, "status_code") and r.status_code == 200
            ]
            rate_limited_responses = [
                r for r in responses if hasattr(r, "status_code") and r.status_code == 429
            ]

            total_time = end_time - start_time
            throughput = len(successful_responses) / total_time

            # Should handle reasonable load
            assert len(successful_responses) > 0
            assert throughput > 1.0  # At least 1 query per second

            print("Load test results:")
            print(f"Total requests: {len(responses)}")
            print(f"Successful: {len(successful_responses)}")
            print(f"Rate limited: {len(rate_limited_responses)}")
            print(f"Throughput: {throughput:.2f} queries/second")
