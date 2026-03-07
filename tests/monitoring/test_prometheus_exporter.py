"""

# Constants

Test suite specifically for Prometheus metrics exporter.
"""

import asyncio
import re
from typing import Dict, List
from unittest.mock import AsyncMock, MagicMock, Mock, patch
import pytest
import aiohttp
from prometheus_client import (
    CollectorRegistry,
    Counter,
    Gauge,
    Histogram,
    Summary,
    generate_latest,
    CONTENT_TYPE_LATEST,
)
from app.core.monitoring.prometheus_exporter import (
    PrometheusMetricsExporter,
    MetricsHTTPServer,
    PrometheusFormatter,
    MetricTypeMapper,
    LabelSanitizer,
)

from tests.test_constants import HTTP_INTERNAL_SERVER_ERROR, HTTP_NOT_FOUND, HTTP_OK


class TestPrometheusFormatter:
    """Test Prometheus metrics formatting."""

    def setup_method(self):
        """Set up test fixtures."""
        self.formatter = PrometheusFormatter()

    def test_counter_formatting(self):
        """Test formatting counter metrics to Prometheus format."""
        metric_data = {
            "name": "http_requests_total",
            "type": "counter",
            "description": "Total HTTP requests",
            "value": 1234,
            "labels": {"method": "GET", "status": "200"},
        }
        output = self.formatter.format_metric(metric_data)
        assert "# HELP http_requests_total Total HTTP requests" in output
        assert "# TYPE http_requests_total counter" in output
        assert 'http_requests_total{method="GET",status="200"} 1234' in output

    def test_gauge_formatting(self):
        """Test formatting gauge metrics to Prometheus format."""
        metric_data = {
            "name": "memory_usage_bytes",
            "type": "gauge",
            "description": "Memory usage in bytes",
            "value": 104857600,
            "labels": {"process": "api_server"},
        }
        output = self.formatter.format_metric(metric_data)
        assert "# HELP memory_usage_bytes Memory usage in bytes" in output
        assert "# TYPE memory_usage_bytes gauge" in output
        assert 'memory_usage_bytes{process="api_server"} 104857600' in output

    def test_histogram_formatting(self):
        """Test formatting histogram metrics to Prometheus format."""
        metric_data = {
            "name": "request_duration_seconds",
            "type": "histogram",
            "description": "Request duration in seconds",
            "buckets": {
                (0.005): 24,
                (0.01): 33,
                (0.025): 47,
                (0.05): 58,
                (0.1): 68,
                (0.25): 78,
                (0.5): 88,
                (1.0): 94,
                (2.5): 98,
                (5.0): 99,
                float("inf"): 100,
            },
            "sum": 12.5,
            "count": 100,
            "labels": {"endpoint": "/api/users"},
        }
        output = self.formatter.format_histogram(metric_data)
        assert "# HELP request_duration_seconds Request duration in seconds" in output
        assert "# TYPE request_duration_seconds histogram" in output
        assert ('request_duration_seconds_bucket{endpoint="/api/users",le="0.005"} 24' in output,)
        assert ('request_duration_seconds_bucket{endpoint="/api/users",le="0.01"} 33' in output,)
        assert ('request_duration_seconds_bucket{endpoint="/api/users",le="+Inf"} 100' in output,)
        assert 'request_duration_seconds_sum{endpoint="/api/users"} 12.5' in output
        assert 'request_duration_seconds_count{endpoint="/api/users"} 100' in output

    def test_summary_formatting(self):
        """Test formatting summary metrics to Prometheus format."""
        metric_data = {
            "name": "response_size_bytes",
            "type": "summary",
            "description": "Response size in bytes",
            "quantiles": {(0.5): 512, (0.9): 1024, (0.99): 2048},
            "sum": 51200,
            "count": 100,
            "labels": {"service": "api"},
        }
        output = self.formatter.format_summary(metric_data)
        assert "# HELP response_size_bytes Response size in bytes" in output
        assert "# TYPE response_size_bytes summary" in output
        assert 'response_size_bytes{service="api",quantile="0.5"} 512' in output
        assert 'response_size_bytes{service="api",quantile="0.9"} 1024' in output
        assert 'response_size_bytes{service="api",quantile="0.99"} 2048' in output
        assert 'response_size_bytes_sum{service="api"} 51200' in output
        assert 'response_size_bytes_count{service="api"} 100' in output

    def test_label_escaping(self):
        """Test that labels are properly escaped."""
        metric_data = {
            "name": "test_metric",
            "type": "counter",
            "value": 1,
            "labels": {
                "path": '/api/users/"test"',
                "query": "key=value\\nline2",
                "special": 'quote"and\\backslash',
            },
        }
        output = self.formatter.format_metric(metric_data)
        assert 'path="/api/users/\\"test\\""' in output
        assert 'query="key=value\\\\nline2"' in output
        assert 'special="quote\\"and\\\\backslash"' in output

    def test_metric_name_validation(self):
        """Test metric name validation and sanitization."""
        assert self.formatter.is_valid_metric_name("http_requests_total")
        assert self.formatter.is_valid_metric_name("_private_metric")
        assert self.formatter.is_valid_metric_name("metric123")
        assert not self.formatter.is_valid_metric_name("123metric")
        assert not self.formatter.is_valid_metric_name("metric-name")
        assert not self.formatter.is_valid_metric_name("metric.name")
        assert self.formatter.sanitize_metric_name("metric-name") == "metric_name"
        assert self.formatter.sanitize_metric_name("metric.name") == "metric_name"
        assert self.formatter.sanitize_metric_name("123metric") == "_123metric"


class TestLabelSanitizer:
    """Test label sanitization for Prometheus compliance."""

    def setup_method(self):
        """Set up test fixtures."""
        self.sanitizer = LabelSanitizer()

    def test_label_name_sanitization(self):
        """Test that label names are properly sanitized."""
        assert self.sanitizer.sanitize_label_name("label-name") == "label_name"
        assert self.sanitizer.sanitize_label_name("label.name") == "label_name"
        assert self.sanitizer.sanitize_label_name("label/name") == "label_name"
        assert self.sanitizer.sanitize_label_name("label:name") == "label_name"
        assert self.sanitizer.sanitize_label_name("123label") == "_123label"
        assert self.sanitizer.sanitize_label_name("__reserved__") == "reserved_"

    def test_label_value_sanitization(self):
        """Test that label values are properly sanitized."""
        assert self.sanitizer.sanitize_label_value("line1\nline2") == "line1\\nline2"
        assert self.sanitizer.sanitize_label_value("tab\there") == "tab\\there"
        assert self.sanitizer.sanitize_label_value('quote"here') == 'quote\\"here'
        assert self.sanitizer.sanitize_label_value("back\\slash") == "back\\\\slash"

    def test_batch_label_sanitization(self):
        """Test sanitizing a batch of labels."""
        labels = {
            "env-name": "production",
            "123metric": "value\nwith\nnewlines",
            "__reserved": "test",
            "valid_label": "valid_value",
        }
        sanitized = self.sanitizer.sanitize_labels(labels)
        assert "env_name" in sanitized
        assert "_123metric" in sanitized
        assert "reserved" in sanitized
        assert "valid_label" in sanitized
        assert sanitized["_123metric"] == "value\\nwith\\nnewlines"


class TestMetricTypeMapper:
    """Test mapping between different metric type systems."""

    def setup_method(self):
        """Set up test fixtures."""
        self.mapper = MetricTypeMapper()

    def test_opentelemetry_to_prometheus_mapping(self):
        """Test mapping OpenTelemetry metric types to Prometheus."""
        assert self.mapper.otel_to_prometheus("Counter") == "counter"
        assert self.mapper.otel_to_prometheus("UpDownCounter") == "gauge"
        assert self.mapper.otel_to_prometheus("Histogram") == "histogram"
        assert self.mapper.otel_to_prometheus("ObservableGauge") == "gauge"

    def test_custom_to_prometheus_mapping(self):
        """Test mapping custom metric types to Prometheus."""
        assert self.mapper.custom_to_prometheus("incrementing_counter") == "counter"
        assert self.mapper.custom_to_prometheus("current_value") == "gauge"
        assert self.mapper.custom_to_prometheus("distribution") == "histogram"
        assert self.mapper.custom_to_prometheus("percentiles") == "summary"

    def test_prometheus_type_validation(self):
        """Test validation of Prometheus metric types."""
        valid_types = ["counter", "gauge", "histogram", "summary"]
        for metric_type in valid_types:
            assert self.mapper.is_valid_prometheus_type(metric_type)
        invalid_types = ["meter", "timer", "custom", "unknown"]
        for metric_type in invalid_types:
            assert not self.mapper.is_valid_prometheus_type(metric_type)


class TestMetricsHTTPServer:
    """Test the HTTP server for serving Prometheus metrics."""

    @pytest.mark.asyncio
    async def test_server_startup_and_shutdown(self):
        """Test that the HTTP server starts and shuts down cleanly."""
        server = MetricsHTTPServer(port=9092)
        await server.start()
        assert server.is_running()
        async with aiohttp.ClientSession() as session:
            async with session.get("http://localhost:9092/health") as response:
                assert response.status == HTTP_OK
        await server.shutdown()
        assert not server.is_running()

    @pytest.mark.asyncio
    async def test_metrics_endpoint(self):
        """Test the /metrics endpoint serves Prometheus metrics."""
        server = MetricsHTTPServer(port=9093)
        test_metrics = """
        # HELP test_counter Test counter metric
        # TYPE test_counter counter
        test_counter{env="test"} 42
        """
        server.set_metrics_callback(lambda: test_metrics)
        await server.start()
        async with aiohttp.ClientSession() as session:
            async with session.get("http://localhost:9093/metrics") as response:
                assert response.status == HTTP_OK
                assert response.headers.get("Content-Type") == CONTENT_TYPE_LATEST
                content = await response.text()
                assert "test_counter" in content
                assert "42" in content
        await server.shutdown()

    @pytest.mark.asyncio
    async def test_custom_endpoint_path(self):
        """Test configuring a custom metrics endpoint path."""
        server = MetricsHTTPServer(port=9094, path="/custom/metrics")
        server.set_metrics_callback(lambda: "custom_metric 1")
        await server.start()
        async with aiohttp.ClientSession() as session:
            async with session.get("http://localhost:9094/custom/metrics") as response:
                assert response.status == HTTP_OK
                content = await response.text()
                assert "custom_metric" in content
            async with session.get("http://localhost:9094/metrics") as response:
                assert response.status == HTTP_NOT_FOUND
        await server.shutdown()

    @pytest.mark.asyncio
    async def test_concurrent_requests(self):
        """Test that the server handles concurrent requests properly."""
        server = MetricsHTTPServer(port=9095)
        request_count = 0

        def metrics_callback():
            nonlocal request_count
            request_count += 1
            return f"request_count {request_count}"

        server.set_metrics_callback(metrics_callback)
        await server.start()
        async with aiohttp.ClientSession() as session:
            tasks = []
            for _ in range(10):
                task = session.get("http://localhost:9095/metrics")
                tasks.append(task)
            responses = await asyncio.gather(*[task.__aenter__() for task in tasks])
            for response in responses:
                assert response.status == HTTP_OK
        assert request_count == 10
        await server.shutdown()

    @pytest.mark.asyncio
    async def test_error_handling(self):
        """Test that the server handles errors gracefully."""
        server = MetricsHTTPServer(port=9096)

        def failing_callback():
            raise ValueError("Metrics generation failed")

        server.set_metrics_callback(failing_callback)
        await server.start()
        async with aiohttp.ClientSession() as session:
            async with session.get("http://localhost:9096/metrics") as response:
                assert response.status == HTTP_INTERNAL_SERVER_ERROR
                content = await response.text()
                assert "error" in content.lower()
        await server.shutdown()


class TestPrometheusMetricsExporter:
    """Test the main Prometheus metrics exporter."""

    def setup_method(self):
        """Set up test fixtures."""
        self.registry = CollectorRegistry()
        self.exporter = PrometheusMetricsExporter(port=9097, registry=self.registry)

    def teardown_method(self):
        """Clean up after tests."""
        if hasattr(self, "exporter"):
            asyncio.run(self.exporter.shutdown())

    def test_metric_registration(self):
        """Test registering metrics with the exporter."""
        counter = self.exporter.register_counter(
            name="test_counter", description="Test counter", labels=["method", "status"]
        )
        gauge = self.exporter.register_gauge(
            name="test_gauge", description="Test gauge", labels=["instance"]
        )
        histogram = self.exporter.register_histogram(
            name="test_histogram",
            description="Test histogram",
            labels=["endpoint"],
            buckets=[0.1, 0.5, 1.0, 5.0],
        )
        assert counter is not None
        assert gauge is not None
        assert histogram is not None
        counter.labels(method="GET", status="200").inc()
        gauge.labels(instance="server1").set(42)
        histogram.labels(endpoint="/api").observe(0.25)
        output = generate_latest(self.registry).decode("utf-8")
        assert "test_counter" in output
        assert "test_gauge" in output
        assert "test_histogram" in output

    def test_bulk_metric_update(self):
        """Test updating multiple metrics in bulk."""
        metrics_data = [
            {"name": "bulk_counter", "type": "counter", "value": 100, "labels": {"env": "prod"}},
            {"name": "bulk_gauge", "type": "gauge", "value": 75.5, "labels": {"server": "api1"}},
            {
                "name": "bulk_histogram",
                "type": "histogram",
                "values": [0.1, 0.2, 0.3, 0.5, 1.0],
                "labels": {"method": "POST"},
            },
        ]
        self.exporter.update_metrics(metrics_data)
        output = generate_latest(self.registry).decode("utf-8")
        assert "bulk_counter" in output
        assert "100" in output
        assert "bulk_gauge" in output
        assert "75.5" in output
        assert "bulk_histogram" in output

    @pytest.mark.asyncio
    async def test_integration_with_http_server(self):
        """Test integration between exporter and HTTP server."""
        await self.exporter.start_http_server()
        counter = self.exporter.register_counter("integration_counter")
        counter.inc()
        async with aiohttp.ClientSession() as session:
            async with session.get("http://localhost:9097/metrics") as response:
                assert response.status == HTTP_OK
                content = await response.text()
                assert "integration_counter" in content

    def test_metric_families_generation(self):
        """Test generating metric families for Prometheus."""
        counter = self.exporter.register_counter(
            name="requests_total", labels=["method", "endpoint"]
        )
        counter.labels(method="GET", endpoint="/users").inc(10)
        counter.labels(method="POST", endpoint="/users").inc(5)
        counter.labels(method="GET", endpoint="/products").inc(20)
        output = generate_latest(self.registry).decode("utf-8")
        assert output.count("# HELP requests_total") == 1
        assert output.count("# TYPE requests_total") == 1
        assert 'endpoint="/users",method="GET"' in output
        assert 'endpoint="/users",method="POST"' in output
        assert 'endpoint="/products",method="GET"' in output

    def test_custom_collector_integration(self):
        """Test integrating custom collectors with the exporter."""
        from prometheus_client.core import CounterMetricFamily

        class CustomCollector:
            def collect(self):
                counter = CounterMetricFamily("custom_total", "Custom metric")
                counter.add_metric([], 42)
                yield counter

        custom_collector = CustomCollector()
        self.registry.register(custom_collector)
        output = generate_latest(self.registry).decode("utf-8")
        assert "custom_total" in output
        assert "42" in output

    def test_metric_timestamp_support(self):
        """Test adding timestamps to metrics (for push gateway)."""
        import time

        timestamp = int(time.time() * 1000)
        self.exporter.push_metric(
            name="timestamped_metric", value=123, labels={"test": "true"}, timestamp=timestamp
        )
        metrics = self.exporter.get_metrics_with_timestamps()
        assert "timestamped_metric" in metrics
        assert metrics["timestamped_metric"]["timestamp"] == timestamp
