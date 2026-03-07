"""

# Constants

Integration Tests for Analytics and Performance API Endpoints

Tests the new analytics, caching, and performance monitoring endpoints
with real API interactions and response validation.
"""

from unittest.mock import AsyncMock, patch
import pytest
from tests.conftest import assert_api_response_security

from tests.test_constants import HTTP_INTERNAL_SERVER_ERROR, HTTP_NOT_FOUND, HTTP_OK


@pytest.mark.integration
@pytest.mark.api
class TestAnalyticsEndpoints:
    """Test analytics API endpoints integration"""

    def test_analytics_dashboard_success(self, client, authenticated_headers):
        """Test analytics dashboard endpoint"""
        print("DEBUG: Testing analytics dashboard endpoint")
        print(f"DEBUG: Authenticated headers: {authenticated_headers}")
        with patch("services.ai.analytics_monitor.get_analytics_monitor") as mock_monitor:
            mock_instance = AsyncMock()
            mock_instance.get_dashboard_data.return_value = {
                "real_time": {
                    "timestamp": "2024-01-01T00:00:00",
                    "period": "last_hour",
                    "metrics": {
                        "total_requests": 150,
                        "average_response_time_ms": 1200.5,
                        "error_rate_percent": 2.1,
                        "cache_hit_rate_percent": 78.5,
                        "active_sessions": 12,
                    },
                    "health_status": "excellent",
                    "active_alerts": 1,
                },
                "usage_analytics": {
                    "period": {
                        "start": "2024-01-01T00:00:00",
                        "end": "2024-01-08T00:00:00",
                        "days": 7,
                    },
                    "total_requests": 1250,
                    "framework_usage": {"ISO27001": 450, "GDPR": 380, "SOC2": 420},
                    "content_type_usage": {"recommendation": 500, "policy": 300, "workflow": 450},
                    "active_users": 45,
                },
                "cost_analytics": {
                    "period": {
                        "start": "2024-01-01T00:00:00",
                        "end": "2024-01-31T00:00:00",
                        "days": 30,
                    },
                    "cost_summary": {
                        "total_cost": 125.75,
                        "average_daily_cost": 4.19,
                        "total_tokens": 2500000,
                        "cost_per_token": 5e-05,
                    },
                    "optimization_opportunities": {
                        "cache_savings": 15.25,
                        "optimization_savings": 8.5,
                        "total_potential_savings": 23.75,
                    },
                },
                "quality_metrics": {
                    "overall_quality_score": 8.5,
                    "quality_trends": {"recommendations": 8.7, "policies": 8.9, "workflows": 8.3},
                    "feedback_summary": {"satisfaction_rate": 85.0},
                },
                "alerts": [],
                "system_health": {
                    "status": "excellent",
                    "uptime_hours": 24,
                    "last_updated": "2024-01-01T00:00:00",
                },
            }
            mock_monitor.return_value = mock_instance
            response = client.get("/api/chat/analytics/dashboard", headers=authenticated_headers)
            print(f"DEBUG: Response status code: {response.status_code}")
            print(f"DEBUG: Response content: {response.text[:500]}")
            assert response.status_code == HTTP_OK
            assert_api_response_security(response)
            data = response.json()
            assert "real_time" in data
            assert "usage_analytics" in data
            assert "cost_analytics" in data
            assert "quality_metrics" in data
            assert "system_health" in data
            real_time = data["real_time"]
            assert "metrics" in real_time
            assert real_time["metrics"]["total_requests"] == 150
            assert real_time["health_status"] == "excellent"
            usage = data["usage_analytics"]
            assert usage["total_requests"] == 1250
            assert "framework_usage" in usage
            assert "ISO27001" in usage["framework_usage"]
            cost = data["cost_analytics"]
            assert "cost_summary" in cost
            assert cost["cost_summary"]["total_cost"] == 125.75

    def test_usage_analytics_endpoint(self, client, authenticated_headers):
        """Test usage analytics endpoint with different time periods"""
        with patch("services.ai.analytics_monitor.get_analytics_monitor") as mock_monitor:
            mock_instance = AsyncMock()
            mock_instance.get_usage_analytics.return_value = {
                "period": {
                    "start": "2024-01-01T00:00:00",
                    "end": "2024-01-15T00:00:00",
                    "days": 14,
                },
                "total_requests": 2100,
                "framework_usage": {"ISO27001": 750, "GDPR": 650, "SOC2": 500, "HIPAA": 200},
                "content_type_usage": {
                    "recommendation": 800,
                    "policy": 600,
                    "workflow": 500,
                    "analysis": 200,
                },
                "daily_usage_trend": {"2024-01-01": 150, "2024-01-02": 145, "2024-01-03": 160},
                "active_users": 67,
                "top_users": {"user_123": 45, "user_456": 38, "user_789": 32},
            }
            mock_monitor.return_value = mock_instance
            response = client.get(
                "/api/chat/analytics/usage?days=14", headers=authenticated_headers
            )
            assert response.status_code == HTTP_OK
            assert_api_response_security(response)
            data = response.json()
            assert data["period"]["days"] == 14
            assert data["total_requests"] == 2100
            assert "framework_usage" in data
            assert "daily_usage_trend" in data
            assert data["active_users"] == 67

    def test_cost_analytics_endpoint(self, client, authenticated_headers):
        """Test cost analytics endpoint"""
        with patch("services.ai.analytics_monitor.get_analytics_monitor") as mock_monitor:
            mock_instance = AsyncMock()
            mock_instance.get_cost_analytics.return_value = {
                "period": {
                    "start": "2024-01-01T00:00:00",
                    "end": "2024-01-31T00:00:00",
                    "days": 30,
                },
                "cost_summary": {
                    "total_cost": 245.8,
                    "average_daily_cost": 8.19,
                    "total_tokens": 4900000,
                    "cost_per_token": 5e-05,
                },
                "daily_cost_trend": {"2024-01-01": 8.5, "2024-01-02": 7.25, "2024-01-03": 9.1},
                "cost_by_content_type": {
                    "recommendation": 98.32,
                    "policy": 73.74,
                    "workflow": 61.45,
                    "analysis": 12.29,
                },
                "optimization_opportunities": {
                    "cache_savings": 28.75,
                    "optimization_savings": 15.2,
                    "total_potential_savings": 43.95,
                },
            }
            mock_monitor.return_value = mock_instance
            response = client.get("/api/chat/analytics/cost?days=30", headers=authenticated_headers)
            assert response.status_code == HTTP_OK
            assert_api_response_security(response)
            data = response.json()
            assert data["cost_summary"]["total_cost"] == 245.8
            assert "daily_cost_trend" in data
            assert "optimization_opportunities" in data
            assert (data["optimization_opportunities"]["total_potential_savings"] == 43.95,)

    def test_system_alerts_endpoint(self, client, authenticated_headers):
        """Test system alerts endpoint"""
        with patch("services.ai.analytics_monitor.get_analytics_monitor") as mock_monitor:
            mock_instance = AsyncMock()
            mock_instance.get_alerts.return_value = [
                {
                    "id": "alert_001",
                    "level": "warning",
                    "title": "High Response Time",
                    "description": "AI response time exceeds threshold",
                    "timestamp": "2024-01-01T12:00:00",
                    "resolved": False,
                    "metadata": {"threshold": 5000, "actual": 6200},
                },
                {
                    "id": "alert_002",
                    "level": "info",
                    "title": "Cache Hit Rate Low",
                    "description": "Cache hit rate below optimal threshold",
                    "timestamp": "2024-01-01T11:30:00",
                    "resolved": True,
                    "metadata": {"threshold": 75, "actual": 68},
                },
            ]
            mock_monitor.return_value = mock_instance
            response = client.get("/api/chat/analytics/alerts", headers=authenticated_headers)
            assert response.status_code == HTTP_OK
            assert_api_response_security(response)
            data = response.json()
            assert "alerts" in data
            assert data["total_count"] == 2
            assert len(data["alerts"]) == 2
            alert = data["alerts"][0]
            assert "id" in alert
            assert "level" in alert
            assert "title" in alert
            assert "resolved" in alert

    def test_resolve_alert_endpoint(self, client, authenticated_headers):
        """Test alert resolution endpoint"""
        with patch("services.ai.analytics_monitor.get_analytics_monitor") as mock_monitor:
            mock_instance = AsyncMock()
            mock_instance.resolve_alert.return_value = True
            mock_monitor.return_value = mock_instance
            response = client.post(
                "/api/chat/analytics/alerts/alert_001/resolve", headers=authenticated_headers
            )
            assert response.status_code == HTTP_OK
            assert_api_response_security(response)
            data = response.json()
            assert data["alert_id"] == "alert_001"
            assert data["status"] == "resolved"
            assert "resolved_at" in data

    def test_resolve_nonexistent_alert(self, client, authenticated_headers):
        """Test resolving a non-existent alert"""
        with patch("services.ai.analytics_monitor.get_analytics_monitor") as mock_monitor:
            mock_instance = AsyncMock()
            mock_instance.resolve_alert.return_value = False
            mock_monitor.return_value = mock_instance
            response = client.post(
                "/api/chat/analytics/alerts/nonexistent_alert/resolve",
                headers=authenticated_headers,
            )
            assert response.status_code == HTTP_NOT_FOUND
            data = response.json()
            assert "Alert not found" in data["detail"]


@pytest.mark.integration
@pytest.mark.api
class TestPerformanceEndpoints:
    """Test performance monitoring API endpoints"""

    def test_performance_metrics_endpoint(self, client, authenticated_headers):
        """Test performance metrics endpoint"""
        with patch("services.ai.performance_optimizer.get_performance_optimizer") as mock_optimizer:
            with patch("services.ai.response_cache.get_ai_cache") as mock_cache:
                mock_perf_instance = AsyncMock()
                mock_perf_instance.get_performance_metrics.return_value = {
                    "request_statistics": {
                        "total_requests": 1500,
                        "average_response_time_ms": 1250.5,
                        "cache_hit_rate": 78.5,
                        "current_queue_size": 3,
                    },
                    "optimization_settings": {
                        "batching_enabled": True,
                        "compression_enabled": True,
                        "max_concurrent_requests": 10,
                    },
                    "cost_optimization": {
                        "estimated_token_usage": 3000000,
                        "estimated_cost": 150.0,
                        "optimization_savings": 25.5,
                    },
                    "system_health": {"available_capacity": 7, "queue_utilization": 60.0},
                }
                mock_optimizer.return_value = mock_perf_instance
                mock_cache_instance = AsyncMock()
                mock_cache_instance.get_cache_metrics.return_value = {
                    "hit_rate_percentage": 78.5,
                    "total_hits": 1178,
                    "total_misses": 322,
                    "estimated_cost_savings": 15.25,
                }
                mock_cache.return_value = mock_cache_instance
                response = client.get(
                    "/api/chat/performance/metrics", headers=authenticated_headers
                )
                assert response.status_code == HTTP_OK
                assert_api_response_security(response)
                data = response.json()
                assert "performance_metrics" in data
                assert "cache_metrics" in data
                assert data["system_status"] == "optimal"
                perf_metrics = data["performance_metrics"]
                assert "request_statistics" in perf_metrics
                assert "optimization_settings" in perf_metrics
                assert "cost_optimization" in perf_metrics

    def test_optimize_performance_endpoint(self, client, authenticated_headers):
        """Test performance optimization configuration endpoint"""
        with patch("services.ai.performance_optimizer.get_performance_optimizer") as mock_optimizer:
            mock_instance = AsyncMock()
            mock_instance.enable_batching = True
            mock_instance.enable_compression = True
            mock_instance.max_concurrent_requests = 15
            mock_instance.request_semaphore = AsyncMock()
            mock_instance.request_semaphore._value = 15
            mock_optimizer.return_value = mock_instance
            response = client.post(
                "/api/chat/performance/optimize?enable_batching=true&enable_compression=true&max_concurrent=15",
                headers=authenticated_headers,
            )
            assert response.status_code == HTTP_OK
            assert_api_response_security(response)
            data = response.json()
            assert data["status"] == "updated"
            assert "optimization_settings" in data
            settings = data["optimization_settings"]
            assert settings["batching_enabled"] is True
            assert settings["compression_enabled"] is True
            assert settings["max_concurrent_requests"] == 15


@pytest.mark.integration
@pytest.mark.api
class TestCacheEndpoints:
    """Test cache management API endpoints"""

    def test_cache_metrics_endpoint(self, client, authenticated_headers):
        """Test cache metrics endpoint"""
        with patch("services.ai.response_cache.get_ai_cache") as mock_cache:
            mock_instance = AsyncMock()
            mock_instance.get_cache_metrics.return_value = {
                "hit_rate_percentage": 82.3,
                "total_hits": 1647,
                "total_misses": 353,
                "total_requests": 2000,
                "estimated_cost_savings": 28.75,
                "cache_size_mb": 15.2,
                "ttl_config": {"recommendation": 7200, "policy": 86400, "workflow": 14400},
            }
            mock_cache.return_value = mock_instance
            response = client.get("/api/chat/cache/metrics", headers=authenticated_headers)
            assert response.status_code == HTTP_OK
            assert_api_response_security(response)
            data = response.json()
            assert "cache_performance" in data
            assert data["status"] == "active"
            cache_perf = data["cache_performance"]
            assert cache_perf["hit_rate_percentage"] == 82.3
            assert cache_perf["total_requests"] == 2000
            assert "ttl_config" in cache_perf

    def test_clear_cache_endpoint(self, client, authenticated_headers):
        """Test cache clearing endpoint"""
        with patch("services.ai.response_cache.get_ai_cache") as mock_cache:
            mock_instance = AsyncMock()
            mock_instance.clear_cache_pattern.return_value = 45
            mock_cache.return_value = mock_instance
            response = client.delete(
                "/api/chat/cache/clear?pattern=recommendation*", headers=authenticated_headers
            )
            assert response.status_code == HTTP_OK
            assert_api_response_security(response)
            data = response.json()
            assert data["cleared_entries"] == 45
            assert data["pattern"] == "recommendation*"
            assert "cleared_at" in data

    def test_analytics_error_handling(self, client, authenticated_headers):
        """Test error handling in analytics endpoints"""
        with patch("services.ai.analytics_monitor.get_analytics_monitor") as mock_monitor:
            mock_monitor.side_effect = Exception("Analytics service unavailable")
            response = client.get("/api/chat/analytics/dashboard", headers=authenticated_headers)
            assert response.status_code == HTTP_INTERNAL_SERVER_ERROR
            data = response.json()
            assert "Failed to get analytics dashboard" in data["detail"]
