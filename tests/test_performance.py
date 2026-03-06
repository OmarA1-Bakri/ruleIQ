"""
import requests
import json

# Constants

KB_SIZE = 1024

CONFIDENCE_THRESHOLD = 0.8
DEFAULT_RETRIES = 5.0
HIGH_CONFIDENCE_THRESHOLD = 0.95


Performance Testing Suite for ComplianceGPT

This module tests system performance including API response times,
AI generation latency, database query optimization, concurrent user
simulation, and resource usage monitoring.
"""

import statistics
import threading
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from unittest.mock import Mock
import psutil
import pytest

from tests.test_constants import DEFAULT_LIMIT, HTTP_CREATED, HTTP_OK, MAX_RETRIES


@pytest.mark.performance
class TestAPIResponseTimes:
    """Test API endpoint response time benchmarks"""

    def test_core_endpoint_response_times(
        self, client, authenticated_headers, performance_test_data
    ):
        """Test that core API endpoints meet response time requirements"""
        endpoints = performance_test_data["request_types"]
        expected_times = performance_test_data["expected_response_times"]
        for endpoint_config in endpoints:
            endpoint = endpoint_config["endpoint"]
            method = endpoint_config["method"]
            response_times = []
            for _ in range(10):
                start_time = time.time()
                if method == "GET":
                    response = client.get(endpoint, headers=authenticated_headers)
                elif method == "POST":
                    test_data = self._get_test_data_for_endpoint(endpoint)
                    response = client.post(endpoint, headers=authenticated_headers, json=test_data)
                end_time = time.time()
                response_time = end_time - start_time
                if response.status_code in [200, 201]:
                    response_times.append(response_time)
            if response_times:
                avg_response_time = statistics.mean(response_times)
                p95_response_time = statistics.quantiles(response_times, n=20)[18]
                assert avg_response_time <= expected_times["api_calls"], (
                    f"Average response time for {endpoint} ({avg_response_time:.2f}s) exceeds limit"
                )
                assert p95_response_time <= expected_times["api_calls"] * 1.5, (
                    f"95th percentile response time for {endpoint} ({p95_response_time:.2f}s) too high"
                )

    def test_database_query_performance(
        self, client, authenticated_headers, db_session, performance_test_data
    ):
        """Test database query performance"""
        expected_db_time = performance_test_data["expected_response_times"]["database_queries",]
        complex_endpoints = [
            "/api/readiness/assessment",
            "/api/frameworks/recommend",
            "/api/audit/trail",
        ]
        for endpoint in complex_endpoints:
            query_times = []
            for _ in range(5):
                start_time = time.time()
                response = client.get(endpoint, headers=authenticated_headers)
                end_time = time.time()
                if response.status_code == HTTP_OK:
                    query_times.append(end_time - start_time)
            if query_times:
                avg_query_time = statistics.mean(query_times)
                assert avg_query_time <= expected_db_time * 3, (
                    f"Database query time for {endpoint} ({avg_query_time:.2f}s) too slow"
                )

    def _get_test_data_for_endpoint(self, endpoint: str) -> dict:
        """Get appropriate test data for POST endpoints"""
        test_data_map = {
            "/api/assessments": {"session_type": "compliance_scoping"},
            "/api/business-profiles": {
                "company_name": "Test Corp",
                "industry": "Technology",
                "employee_count": 25,
            },
            "/api/policies/generate": {"framework_id": "test-framework-id"},
        }
        return test_data_map.get(endpoint, {})


@pytest.mark.performance
class TestAIGenerationPerformance:
    """Test AI content generation performance and latency"""

    def test_ai_response_latency(
        self, client, authenticated_headers, mock_ai_client, performance_test_data
    ):
        """Test AI generation response times"""
        expected_ai_time = performance_test_data["expected_response_times"]["ai_generation",]

        def mock_ai_with_delay(*args, **kwargs):
            time.sleep(2)
            mock_response = Mock()
            mock_response.text = "Generated compliance content for performance testing"
            return mock_response

        mock_ai_client.generate_content.side_effect = mock_ai_with_delay
        ai_endpoints = [
            "/api/policies/generate",
            "/api/frameworks/recommend",
            "/api/compliance/query",
        ]
        for endpoint in ai_endpoints:
            ai_times = []
            for _ in range(3):
                start_time = time.time()
                test_data = self._get_ai_test_data(endpoint)
                response = client.post(endpoint, headers=authenticated_headers, json=test_data)
                end_time = time.time()
                if response.status_code in [200, 201]:
                    ai_times.append(end_time - start_time)
            if ai_times:
                avg_ai_time = statistics.mean(ai_times)
                assert avg_ai_time <= expected_ai_time, (
                    f"AI generation time for {endpoint} ({avg_ai_time:.2f}s) exceeds limit"
                )

    def test_ai_content_caching_performance(self, client, authenticated_headers, mock_ai_client):
        """Test AI content caching improves performance"""
        mock_ai_client.generate_content.return_value.text = "Cached content test"
        start_time = time.time()
        response_1 = client.post(
            "/api/policies/generate",
            headers=authenticated_headers,
            json={"framework_id": "test-framework"},
        )
        first_request_time = time.time() - start_time
        start_time = time.time()
        response_2 = client.post(
            "/api/policies/generate",
            headers=authenticated_headers,
            json={"framework_id": "test-framework"},
        )
        second_request_time = time.time() - start_time
        if response_1.status_code == HTTP_CREATED and response_2.status_code == HTTP_CREATED:
            speed_improvement = first_request_time / second_request_time
            assert speed_improvement >= 1.5, (
                f"Caching should improve performance, got {speed_improvement:.2f}x speedup"
            )

    def test_batch_ai_processing_efficiency(self, client, authenticated_headers, mock_ai_client):
        """Test batch processing of AI requests"""
        mock_ai_client.generate_content.return_value.text = "Batch processed content"
        single_times = []
        for _ in range(5):
            start_time = time.time()
            client.post(
                "/api/policies/generate",
                headers=authenticated_headers,
                json={"framework_id": f"framework-{_}"},
            )
            single_times.append(time.time() - start_time)
        statistics.mean(single_times)
        start_time = time.time()
        batch_response = client.post(
            "/api/policies/generate-batch",
            headers=authenticated_headers,
            json={"requests": [{"framework_id": f"framework-{i}"} for i in range(5)]},
        )
        batch_time = time.time() - start_time
        if batch_response.status_code == HTTP_CREATED:
            total_single_time = sum(single_times)
            efficiency_ratio = total_single_time / batch_time
            assert efficiency_ratio >= 1.2, (
                f"Batch processing should be more efficient, got {efficiency_ratio:.2f}x improvement"
            )

    def _get_ai_test_data(self, endpoint: str) -> dict:
        """Get test data for AI endpoints"""
        ai_test_data = {
            "/api/policies/generate": {"framework_id": "test-gdpr-framework"},
            "/api/frameworks/recommend": {
                "industry": "Technology",
                "company_size": "Small",
                "data_processing": True,
            },
            "/api/compliance/query": {
                "question": "What are GDPR requirements?",
                "framework": "GDPR",
            },
        }
        return ai_test_data.get(endpoint, {})


@pytest.mark.performance
class TestConcurrentUserLoad:
    """Test system performance under concurrent user load"""

    def test_concurrent_user_simulation(self, client, authenticated_headers, performance_test_data):
        """Test system behavior with multiple concurrent users"""
        concurrent_users = performance_test_data["concurrent_users"]
        for user_count in concurrent_users:
            if user_count <= 10:
                success_rates = self._simulate_concurrent_users(
                    client, authenticated_headers, user_count
                )
                assert success_rates["success_rate"] >= HIGH_CONFIDENCE_THRESHOLD, (
                    f"Success rate {success_rates['success_rate']:.2f} too low for {user_count} users"
                )
                assert success_rates["avg_response_time"] <= DEFAULT_RETRIES, (
                    f"Response time {success_rates['avg_response_time']:.2f}s too high under load"
                )

    def test_database_connection_pooling(self, client, authenticated_headers):
        """Test database connection pooling under load"""

        def make_db_request():
            response = client.get("/api/frameworks", headers=authenticated_headers)
            return response.status_code == HTTP_OK

        with ThreadPoolExecutor(max_workers=20) as executor:
            futures = [executor.submit(make_db_request) for _ in range(50)]
            results = [future.result() for future in as_completed(futures)]
        success_rate = sum(results) / len(results)
        assert success_rate >= 0.9, (
            f"Database connection pooling failed, success rate: {success_rate:.2f}"
        )

    def test_memory_usage_under_load(self, client, authenticated_headers):
        """Test memory usage doesn't grow excessively under load"""
        process = psutil.Process()
        initial_memory = process.memory_info().rss / 1024 / 1024
        for _ in range(50):
            client.get("/api/frameworks", headers=authenticated_headers)
            client.get("/api/business-profiles", headers=authenticated_headers)
        final_memory = process.memory_info().rss / 1024 / 1024
        memory_increase = final_memory - initial_memory
        assert memory_increase <= 50, f"Memory usage increased by {memory_increase:.2f}MB"

    def _simulate_concurrent_users(self, client, headers, user_count: int) -> dict:
        """Simulate concurrent users and return performance metrics"""
        results = []

        def user_session():
            start_time = time.time()
            try:
                responses = [
                    client.get("/api/frameworks", headers=headers),
                    client.get("/api/business-profiles", headers=headers),
                    client.get("/api/dashboard", headers=headers),
                ]
                success = all(r.status_code in [200, 404] for r in responses)
                response_time = time.time() - start_time
                return {"success": success, "response_time": response_time}
            except (OSError, requests.RequestException, KeyError):
                return {"success": False, "response_time": time.time() - start_time}

        with ThreadPoolExecutor(max_workers=user_count) as executor:
            futures = [executor.submit(user_session) for _ in range(user_count)]
            results = [future.result() for future in as_completed(futures)]
        success_count = sum(1 for r in results if r["success"])
        success_rate = success_count / len(results)
        avg_response_time = statistics.mean([r["response_time"] for r in results])
        return {
            "success_rate": success_rate,
            "avg_response_time": avg_response_time,
            "total_requests": len(results),
        }


@pytest.mark.performance
@pytest.mark.slow
class TestSoakTesting:
    """Test system stability under sustained load"""

    def test_extended_operation_stability(self, client, authenticated_headers):
        """Test system stability over extended period"""
        start_time = time.time()
        test_duration = 300
        error_count = 0
        request_count = 0
        response_times = []
        while time.time() - start_time < test_duration:
            try:
                request_start = time.time()
                response = client.get("/api/frameworks", headers=authenticated_headers)
                request_time = time.time() - request_start
                if response.status_code != HTTP_OK:
                    error_count += 1
                else:
                    response_times.append(request_time)
                request_count += 1
                time.sleep(1)
            except requests.RequestException:
                error_count += 1
                request_count += 1
        error_rate = error_count / request_count if request_count > 0 else 1
        assert error_rate <= 0.05, f"Error rate {error_rate:.2f} too high during soak test"
        if response_times:
            avg_response_time = statistics.mean(response_times)
            assert avg_response_time <= MAX_RETRIES, (
                f"Average response time degraded to {avg_response_time:.2f}s"
            )

    def test_memory_leak_detection(self, client, authenticated_headers):
        """Test for memory leaks during extended operation"""
        process = psutil.Process()
        memory_samples = []
        for _i in range(20):
            for _ in range(10):
                client.get("/api/frameworks", headers=authenticated_headers)
            memory_mb = process.memory_info().rss / 1024 / 1024
            memory_samples.append(memory_mb)
            time.sleep(2)
        if len(memory_samples) >= 10:
            first_half = memory_samples[:10]
            second_half = memory_samples[10:]
            avg_first_half = statistics.mean(first_half)
            avg_second_half = statistics.mean(second_half)
            memory_growth = avg_second_half - avg_first_half
            assert memory_growth <= 20, (
                f"Potential memory leak detected: {memory_growth:.2f}MB growth"
            )

    def test_connection_pool_exhaustion(self, client, authenticated_headers):
        """Test behavior when connection pool is exhausted"""

        def make_long_request():
            try:
                response = client.get("/api/readiness/assessment", headers=authenticated_headers)
                return response.status_code
            except requests.RequestException:
                return 500

        with ThreadPoolExecutor(max_workers=30) as executor:
            futures = [executor.submit(make_long_request) for _ in range(DEFAULT_LIMIT)]
            status_codes = [future.result() for future in as_completed(futures)]
        success_codes = [code for code in status_codes if code in [200, 429, 503]]
        success_rate = len(success_codes) / len(status_codes)
        assert success_rate >= CONFIDENCE_THRESHOLD, (
            f"System should handle connection exhaustion gracefully, got {success_rate:.2f}"
        )


@pytest.mark.performance
class TestResourceUtilization:
    """Test resource utilization and optimization"""

    def test_cpu_usage_under_load(self, client, authenticated_headers):
        """Test CPU usage remains reasonable under load"""
        process = psutil.Process()
        cpu_samples = []

        def generate_load():
            for _ in range(50):
                client.get("/api/frameworks", headers=authenticated_headers)
                client.post(
                    "/api/business-profiles",
                    headers=authenticated_headers,
                    json={"company_name": "Test", "industry": "Tech", "employee_count": 25},
                )

        load_thread = threading.Thread(target=generate_load)
        load_thread.start()
        for _ in range(10):
            cpu_percent = process.cpu_percent(interval=0.5)
            cpu_samples.append(cpu_percent)
        load_thread.join()
        if cpu_samples:
            avg_cpu = statistics.mean(cpu_samples)
            max_cpu = max(cpu_samples)
            assert avg_cpu <= 80, f"Average CPU usage {avg_cpu:.1f}% too high"
            assert max_cpu <= 95, f"Peak CPU usage {max_cpu:.1f}% too high"

    def test_disk_io_efficiency(self, client, authenticated_headers):
        """Test disk I/O efficiency during operations"""
        process = psutil.Process()
        initial_io = process.io_counters()
        for _ in range(20):
            client.get("/api/audit/trail", headers=authenticated_headers)
            client.post(
                "/api/readiness/reports",
                headers=authenticated_headers,
                json={"title": "Test Report", "report_type": "executive", "format": "pdf"},
            )
        final_io = process.io_counters()
        read_bytes = final_io.read_bytes - initial_io.read_bytes
        write_bytes = final_io.write_bytes - initial_io.write_bytes
        total_io_mb = (read_bytes + write_bytes) / 1024 / 1024
        assert total_io_mb <= DEFAULT_LIMIT, f"Excessive disk I/O: {total_io_mb:.2f}MB"

    def test_response_compression_efficiency(self, client, authenticated_headers):
        """Test response compression reduces bandwidth usage"""
        compressed_response = client.get(
            "/api/frameworks", headers={**authenticated_headers, "Accept-Encoding": "gzip"}
        )
        uncompressed_response = client.get(
            "/api/frameworks", headers={**authenticated_headers, "Accept-Encoding": "identity"}
        )
        if (
            compressed_response.status_code == HTTP_OK
            and uncompressed_response.status_code == HTTP_OK
        ):
            compressed_size = len(compressed_response.content)
            uncompressed_size = len(uncompressed_response.content)
            if uncompressed_size > KB_SIZE:
                compression_ratio = uncompressed_size / compressed_size
                assert compression_ratio >= 1.2, (
                    f"Compression should reduce size, got {compression_ratio:.2f}x ratio"
                )


@pytest.mark.performance
class TestScalabilityLimits:
    """Test system scalability limits and breaking points"""

    def test_maximum_concurrent_assessments(self, client, authenticated_headers):
        """Test maximum number of concurrent assessments"""

        def create_assessment():
            try:
                response = client.post(
                    "/api/assessments",
                    headers=authenticated_headers,
                    json={"session_type": "compliance_scoping"},
                )
                return response.status_code == HTTP_CREATED
            except (json.JSONDecodeError, requests.RequestException):
                return False

        with ThreadPoolExecutor(max_workers=20) as executor:
            futures = [executor.submit(create_assessment) for _ in range(50)]
            results = [future.result() for future in as_completed(futures)]
        success_rate = sum(results) / len(results)
        assert success_rate >= CONFIDENCE_THRESHOLD, (
            f"Assessment creation success rate {success_rate:.2f} too low"
        )

    def test_large_data_set_handling(self, client, authenticated_headers):
        """Test handling of large data sets"""
        large_profile = {
            "company_name": "Large Corp",
            "industry": "Technology",
            "employee_count": 10000,
            "cloud_providers": [f"Provider{i}" for i in range(10)],
            "saas_tools": [f"Tool{i}" for i in range(20)],
            "development_tools": [f"DevTool{i}" for i in range(10)],
            "existing_frameworks": [f"Framework{i}" for i in range(10)],
        }
        start_time = time.time()
        response = client.post(
            "/api/business-profiles", headers=authenticated_headers, json=large_profile
        )
        processing_time = time.time() - start_time
        assert response.status_code == HTTP_CREATED, "Should handle large data sets"
        assert processing_time <= DEFAULT_RETRIES, (
            f"Large data processing too slow: {processing_time:.2f}s"
        )

    def test_pagination_performance(self, client, authenticated_headers):
        """Test pagination performance with large result sets"""
        page_sizes = [10, 50, 100]
        for page_size in page_sizes:
            start_time = time.time()
            response = client.get(
                f"/api/audit/trail?page=1&size={page_size}", headers=authenticated_headers
            )
            response_time = time.time() - start_time
            if response.status_code == HTTP_OK:
                assert response_time <= MAX_RETRIES, (
                    f"Pagination with page_size={page_size} too slow: {response_time:.2f}s"
                )
                data = response.json()
                if "pagination" in data:
                    pagination = data["pagination"]
                    assert "page" in pagination
                    assert "size" in pagination
                    assert "total" in pagination
