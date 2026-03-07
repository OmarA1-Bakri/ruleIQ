"""
Test suite for OpenTelemetry metrics integration.
Tests metric collection, Prometheus exporters, and LangGraph custom metrics.
"""

import asyncio
import json
import time
from typing import Any, Dict, List
from unittest.mock import AsyncMock, MagicMock, Mock, patch

import pytest
from opentelemetry import metrics
from opentelemetry.exporter.prometheus import PrometheusMetricReader
from opentelemetry.metrics import Counter, Histogram, UpDownCounter
from opentelemetry.sdk.metrics import MeterProvider
from opentelemetry.sdk.metrics.export import (
    AggregationTemporality,
    MetricExporter,
    MetricExportResult,
    MetricsData,
)
from opentelemetry.sdk.resources import Resource, SERVICE_NAME

from app.core.monitoring.opentelemetry_metrics import (
    OpenTelemetryMetricsCollector,
    PrometheusExporter,
    LangGraphMetricsInstrumentor,
    MetricsBridge,
)


class TestOpenTelemetryMetricsCollector:
    """Test OpenTelemetry metrics collector functionality."""

    def setup_method(self):
        """Set up test fixtures."""
        self.resource = Resource.create({SERVICE_NAME: "test-service"})
        self.collector = OpenTelemetryMetricsCollector(resource=self.resource)

    def teardown_method(self):
        """Clean up after tests."""
        if hasattr(self, "collector"):
            self.collector.shutdown()

    def test_collector_initialization(self):
        """Test that collector initializes with proper configuration."""
        assert self.collector is not None
        assert self.collector.meter_provider is not None
        assert self.collector.meter is not None
        assert self.collector.service_name == "test-service"

    def test_counter_creation_and_increment(self):
        """Test creating and incrementing a counter metric."""
        counter = self.collector.create_counter(
            name="test_counter",
            description="Test counter metric",
            unit="1",
        )

        assert counter is not None
        counter.add(1, {"label": "test"})
        counter.add(5, {"label": "test"})

        # Verify counter value through export
        metrics_data = self.collector.collect_metrics()
        assert "test_counter" in metrics_data
        assert metrics_data["test_counter"]["value"] == 6
        assert metrics_data["test_counter"]["labels"] == {"label": "test"}

    def test_histogram_creation_and_recording(self):
        """Test creating and recording histogram metrics."""
        histogram = self.collector.create_histogram(
            name="test_histogram",
            description="Test histogram metric",
            unit="ms",
        )

        assert histogram is not None
        histogram.record(100, {"endpoint": "/api/test"})
        histogram.record(200, {"endpoint": "/api/test"})
        histogram.record(150, {"endpoint": "/api/test"})

        # Verify histogram statistics
        metrics_data = self.collector.collect_metrics()
        assert "test_histogram" in metrics_data
        stats = metrics_data["test_histogram"]
        assert stats["count"] == 3
        assert stats["sum"] == 450
        assert stats["min"] == 100
        assert stats["max"] == 200

    def test_updown_counter_creation(self):
        """Test creating and using an up-down counter."""
        gauge = self.collector.create_updown_counter(
            name="test_gauge",
            description="Test gauge metric",
            unit="1",
        )

        assert gauge is not None
        gauge.add(10, {"resource": "cpu"})
        gauge.add(-3, {"resource": "cpu"})
        gauge.add(5, {"resource": "cpu"})

        # Verify gauge value
        metrics_data = self.collector.collect_metrics()
        assert "test_gauge" in metrics_data
        assert metrics_data["test_gauge"]["value"] == 12

    def test_observable_gauge_creation(self):
        """Test creating and using an observable gauge."""

        def get_cpu_usage():
            return [(75.5, {"core": "0"}), (82.3, {"core": "1"})]

        observable_gauge = self.collector.create_observable_gauge(
            name="cpu_usage",
            callback=get_cpu_usage,
            description="CPU usage percentage",
            unit="%",
        )

        assert observable_gauge is not None

        # Force collection and verify values
        metrics_data = self.collector.collect_metrics()
        assert "cpu_usage" in metrics_data
        assert len(metrics_data["cpu_usage"]) == 2

    def test_batch_metric_recording(self):
        """Test recording multiple metrics in batch."""
        metrics_batch = [
            ("counter", "requests_total", 1, {"method": "GET"}),
            ("histogram", "request_duration", 250, {"method": "GET"}),
            ("gauge", "active_connections", 5, {"server": "web1"}),
        ]

        self.collector.record_batch(metrics_batch)

        metrics_data = self.collector.collect_metrics()
        assert "requests_total" in metrics_data
        assert "request_duration" in metrics_data
        assert "active_connections" in metrics_data

    def test_metric_labels_and_attributes(self):
        """Test that metrics properly handle labels/attributes."""
        counter = self.collector.create_counter("labeled_counter")

        # Record with different label sets
        counter.add(1, {"env": "prod", "region": "us-east"})
        counter.add(2, {"env": "prod", "region": "us-west"})
        counter.add(3, {"env": "dev", "region": "us-east"})

        metrics_data = self.collector.collect_metrics_by_labels()
        assert len(metrics_data["labeled_counter"]) == 3

        # Verify each label combination
        for metric in metrics_data["labeled_counter"]:
            if metric["labels"]["env"] == "prod" and metric["labels"]["region"] == "us-east":
                assert metric["value"] == 1
            elif metric["labels"]["env"] == "prod" and metric["labels"]["region"] == "us-west":
                assert metric["value"] == 2
            elif metric["labels"]["env"] == "dev":
                assert metric["value"] == 3


class TestPrometheusExporter:
    """Test Prometheus metrics exporter functionality."""

    def setup_method(self):
        """Set up test fixtures."""
        self.exporter = PrometheusExporter(port=9090)
        self.collector = OpenTelemetryMetricsCollector()

    def teardown_method(self):
        """Clean up after tests."""
        if hasattr(self, "exporter"):
            self.exporter.shutdown()

    def test_exporter_initialization(self):
        """Test that Prometheus exporter initializes correctly."""
        assert self.exporter is not None
        assert self.exporter.port == 9090
        assert self.exporter.endpoint == "/metrics"

    def test_prometheus_format_conversion(self):
        """Test conversion of metrics to Prometheus format."""
        # Create test metrics
        counter = self.collector.create_counter("http_requests_total")
        counter.add(100, {"method": "GET", "status": "200"})

        histogram = self.collector.create_histogram("http_request_duration_seconds")
        for value in [0.1, 0.2, 0.3, 0.5, 1.0]:
            histogram.record(value, {"method": "GET"})

        # Export to Prometheus format
        prometheus_output = self.exporter.export(self.collector)

        # Verify Prometheus format
        assert "# HELP http_requests_total" in prometheus_output
        assert "# TYPE http_requests_total counter" in prometheus_output
        assert 'http_requests_total{method="GET",status="200"} 100' in prometheus_output

        assert "# HELP http_request_duration_seconds" in prometheus_output
        assert "# TYPE http_request_duration_seconds histogram" in prometheus_output
        assert "http_request_duration_seconds_bucket" in prometheus_output
        assert "http_request_duration_seconds_sum" in prometheus_output
        assert "http_request_duration_seconds_count" in prometheus_output

    @pytest.mark.asyncio
    async def test_prometheus_http_endpoint(self):
        """Test that Prometheus HTTP endpoint serves metrics."""
        import aiohttp

        # Start the exporter HTTP server
        await self.exporter.start()

        # Create some test metrics
        counter = self.collector.create_counter("test_metric")
        counter.add(42, {"test": "true"})

        # Register collector with exporter
        self.exporter.register_collector(self.collector)

        # Make HTTP request to metrics endpoint
        async with aiohttp.ClientSession() as session:
            async with session.get("http://localhost:9090/metrics") as response:
                assert response.status == 200
                content = await response.text()
                assert "test_metric" in content
                assert 'test="true"' in content
                assert "42" in content

    def test_histogram_buckets_configuration(self):
        """Test configuring custom histogram buckets for Prometheus."""
        custom_buckets = [0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0]

        histogram = self.collector.create_histogram(
            name="custom_histogram",
            description="Histogram with custom buckets",
            unit="s",
            buckets=custom_buckets,
        )

        # Record values
        for value in [0.003, 0.015, 0.08, 0.3, 1.5, 3.0]:
            histogram.record(value)

        prometheus_output = self.exporter.export(self.collector)

        # Verify all buckets are present
        for bucket in custom_buckets:
            assert f'le="{bucket}"' in prometheus_output
        assert 'le="+Inf"' in prometheus_output

    def test_metric_name_sanitization(self):
        """Test that metric names are properly sanitized for Prometheus."""
        # Create metrics with non-Prometheus-compliant names
        counter = self.collector.create_counter("my-metric.with/special:chars")
        counter.add(1)

        prometheus_output = self.exporter.export(self.collector)

        # Verify name is sanitized
        assert "my_metric_with_special_chars" in prometheus_output
        assert "my-metric.with/special:chars" not in prometheus_output

    def test_multi_collector_aggregation(self):
        """Test aggregating metrics from multiple collectors."""
        collector1 = OpenTelemetryMetricsCollector()
        collector2 = OpenTelemetryMetricsCollector()

        # Create metrics in different collectors
        counter1 = collector1.create_counter("shared_counter")
        counter1.add(10, {"source": "collector1"})

        counter2 = collector2.create_counter("shared_counter")
        counter2.add(20, {"source": "collector2"})

        # Register both collectors
        self.exporter.register_collector(collector1)
        self.exporter.register_collector(collector2)

        prometheus_output = self.exporter.export_all()

        # Verify both metrics are present
        assert 'shared_counter{source="collector1"} 10' in prometheus_output
        assert 'shared_counter{source="collector2"} 20' in prometheus_output


class TestLangGraphMetricsInstrumentor:
    """Test LangGraph-specific metrics instrumentation."""

    def setup_method(self):
        """Set up test fixtures."""
        self.collector = OpenTelemetryMetricsCollector()
        self.instrumentor = LangGraphMetricsInstrumentor(self.collector)

    def test_node_execution_metrics(self):
        """Test metrics for LangGraph node execution."""
        # Simulate node execution
        with self.instrumentor.measure_node_execution("compliance_node") as ctx:
            time.sleep(0.1)  # Simulate work
            ctx.set_status("success")
            ctx.add_attribute("workflow_id", "test-123")

        metrics_data = self.collector.collect_metrics()

        # Verify node execution metrics
        assert "langgraph_node_duration_seconds" in metrics_data
        assert "langgraph_node_executions_total" in metrics_data

        # Check specific values
        node_metrics = metrics_data["langgraph_node_executions_total"]
        assert node_metrics["labels"]["node_name"] == "compliance_node"
        assert node_metrics["labels"]["status"] == "success"
        assert node_metrics["value"] == 1

    def test_workflow_metrics(self):
        """Test metrics for complete workflow execution."""
        # Start workflow
        workflow_ctx = self.instrumentor.start_workflow("assessment_workflow")
        workflow_ctx.add_attribute("user_id", "user-456")

        # Execute nodes
        with self.instrumentor.measure_node_execution("node1", workflow_ctx) as node_ctx:
            node_ctx.set_status("success")

        with self.instrumentor.measure_node_execution("node2", workflow_ctx) as node_ctx:
            node_ctx.set_status("success")

        # Complete workflow
        workflow_ctx.complete("success")

        metrics_data = self.collector.collect_metrics()

        # Verify workflow metrics
        assert "langgraph_workflow_duration_seconds" in metrics_data
        assert "langgraph_workflow_nodes_executed_total" in metrics_data
        assert metrics_data["langgraph_workflow_nodes_executed_total"]["value"] == 2

    def test_error_tracking_metrics(self):
        """Test metrics for error tracking in LangGraph."""
        # Simulate node with error
        try:
            with self.instrumentor.measure_node_execution("error_node") as ctx:
                ctx.add_attribute("error_type", "ValidationError")
                raise ValueError("Test error")
        except ValueError:
            pass  # Expected

        metrics_data = self.collector.collect_metrics()

        # Verify error metrics
        assert "langgraph_node_errors_total" in metrics_data
        error_metrics = metrics_data["langgraph_node_errors_total"]
        assert error_metrics["labels"]["node_name"] == "error_node"
        assert error_metrics["labels"]["error_type"] == "ValidationError"
        assert error_metrics["value"] == 1

    def test_state_transition_metrics(self):
        """Test metrics for state transitions in LangGraph."""
        # Record state transitions
        self.instrumentor.record_state_transition(
            from_state="pending",
            to_state="processing",
            workflow_id="test-workflow",
        )
        self.instrumentor.record_state_transition(
            from_state="processing",
            to_state="completed",
            workflow_id="test-workflow",
        )

        metrics_data = self.collector.collect_metrics()

        # Verify state transition metrics
        assert "langgraph_state_transitions_total" in metrics_data
        transitions = self.collector.collect_metrics_by_labels()[
            "langgraph_state_transitions_total",
        ]

        # Check both transitions recorded
        assert len(transitions) == 2
        assert any(
            t["labels"]["from_state"] == "pending" and t["labels"]["to_state"] == "processing"
            for t in transitions
        )
        assert any(
            t["labels"]["from_state"] == "processing" and t["labels"]["to_state"] == "completed"
            for t in transitions
        )

    def test_checkpoint_metrics(self):
        """Test metrics for LangGraph checkpointing."""
        # Record checkpoint operations
        with self.instrumentor.measure_checkpoint_operation("save", "postgres") as ctx:
            ctx.add_attribute("checkpoint_size_bytes", 1024)
            time.sleep(0.05)

        with self.instrumentor.measure_checkpoint_operation("load", "postgres") as ctx:
            ctx.add_attribute("checkpoint_size_bytes", 1024)
            time.sleep(0.02)

        metrics_data = self.collector.collect_metrics()

        # Verify checkpoint metrics
        assert "langgraph_checkpoint_operations_total" in metrics_data
        assert "langgraph_checkpoint_duration_seconds" in metrics_data
        assert "langgraph_checkpoint_size_bytes" in metrics_data

    def test_message_queue_metrics(self):
        """Test metrics for message queue in LangGraph."""
        # Record message queue metrics
        self.instrumentor.record_message_enqueued("compliance_queue", priority="high")
        self.instrumentor.record_message_enqueued("compliance_queue", priority="normal")
        self.instrumentor.record_message_processed(
            "compliance_queue",
            duration_ms=150,
            success=True,
        )

        metrics_data = self.collector.collect_metrics()

        # Verify queue metrics
        assert "langgraph_queue_messages_enqueued_total" in metrics_data
        assert "langgraph_queue_messages_processed_total" in metrics_data
        assert "langgraph_queue_processing_duration_milliseconds" in metrics_data

    def test_memory_usage_metrics(self):
        """Test memory usage metrics for LangGraph components."""
        # Record memory usage
        self.instrumentor.record_memory_usage(
            component="state_store",
            bytes_used=1024 * 1024,  # 1MB
            bytes_limit=10 * 1024 * 1024,  # 10MB,
        )

        metrics_data = self.collector.collect_metrics()

        # Verify memory metrics
        assert "langgraph_memory_usage_bytes" in metrics_data
        assert "langgraph_memory_limit_bytes" in metrics_data
        assert "langgraph_memory_usage_ratio" in metrics_data

        # Check calculated ratio
        ratio = metrics_data["langgraph_memory_usage_ratio"]["value"]
        assert abs(ratio - 0.1) < 0.01  # 10% usage


class TestMetricsBridge:
    """Test bridging between existing MetricsCollector and OpenTelemetry."""

    @patch("app.core.monitoring.metrics.MetricsCollector")
    def test_bridge_initialization(self, mock_metrics_collector):
        """Test that bridge properly connects both metric systems."""
        bridge = MetricsBridge(mock_metrics_collector)

        assert bridge is not None
        assert bridge.legacy_collector == mock_metrics_collector
        assert bridge.otel_collector is not None

    @patch("app.core.monitoring.metrics.MetricsCollector")
    def test_counter_synchronization(self, mock_metrics_collector):
        """Test that counters are synchronized between systems."""
        mock_counter = MagicMock()
        mock_metrics_collector.register_counter.return_value = mock_counter

        bridge = MetricsBridge(mock_metrics_collector)

        # Register counter through bridge
        counter = bridge.register_counter(
            name="test_counter",
            description="Test counter",
            labels={"env": "test"},
        )

        # Increment counter
        counter.increment(5)

        # Verify both systems updated
        mock_counter.increment.assert_called_with(5)

        metrics_data = bridge.otel_collector.collect_metrics()
        assert "test_counter" in metrics_data
        assert metrics_data["test_counter"]["value"] == 5

    @patch("app.core.monitoring.metrics.MetricsCollector")
    def test_histogram_synchronization(self, mock_metrics_collector):
        """Test that histograms are synchronized between systems."""
        mock_histogram = MagicMock()
        mock_metrics_collector.register_histogram.return_value = mock_histogram

        bridge = MetricsBridge(mock_metrics_collector)

        # Register histogram through bridge
        histogram = bridge.register_histogram(
            name="test_histogram",
            description="Test histogram",
            buckets=[0.1, 0.5, 1.0, 5.0],
        )

        # Record values
        histogram.observe(0.3)
        histogram.observe(0.7)
        histogram.observe(2.0)

        # Verify both systems updated
        assert mock_histogram.observe.call_count == 3

        metrics_data = bridge.otel_collector.collect_metrics()
        assert "test_histogram" in metrics_data
        assert metrics_data["test_histogram"]["count"] == 3

    @patch("app.core.monitoring.metrics.MetricsCollector")
    def test_gauge_synchronization(self, mock_metrics_collector):
        """Test that gauges are synchronized between systems."""
        mock_gauge = MagicMock()
        mock_metrics_collector.register_gauge.return_value = mock_gauge

        bridge = MetricsBridge(mock_metrics_collector)

        # Register gauge through bridge
        gauge = bridge.register_gauge(name="test_gauge", description="Test gauge")

        # Set gauge value
        gauge.set(42)

        # Verify both systems updated
        mock_gauge.set.assert_called_with(42)

        metrics_data = bridge.otel_collector.collect_metrics()
        assert "test_gauge" in metrics_data
        assert metrics_data["test_gauge"]["value"] == 42

    @patch("app.core.monitoring.metrics.MetricsCollector")
    def test_export_to_prometheus(self, mock_metrics_collector):
        """Test exporting bridged metrics to Prometheus format."""
        # Setup mock legacy metrics
        mock_metrics_collector.get_all_metrics.return_value = {
            "http_requests": {"type": "counter", "value": 100},
            "response_time": {"type": "histogram", "values": [0.1, 0.2, 0.3]},
            "active_users": {"type": "gauge", "value": 25},
        }

        bridge = MetricsBridge(mock_metrics_collector)
        exporter = PrometheusExporter()

        # Sync and export
        bridge.sync_all_metrics()
        prometheus_output = exporter.export(bridge.otel_collector)

        # Verify all metrics in Prometheus format
        assert "http_requests" in prometheus_output
        assert "response_time" in prometheus_output
        assert "active_users" in prometheus_output

    @patch("app.core.monitoring.metrics.MetricsCollector")
    def test_automatic_langgraph_instrumentation(self, mock_metrics_collector):
        """Test that LangGraph instrumentation is automatically added."""
        bridge = MetricsBridge(mock_metrics_collector, enable_langgraph=True)

        assert bridge.langgraph_instrumentor is not None

        # Test that LangGraph metrics work through bridge
        with bridge.langgraph_instrumentor.measure_node_execution("test_node") as ctx:
            ctx.set_status("success")

        metrics_data = bridge.otel_collector.collect_metrics()
        assert "langgraph_node_executions_total" in metrics_data


class TestIntegration:
    """Integration tests for the complete metrics pipeline."""

    @pytest.mark.asyncio
    async def test_end_to_end_metrics_pipeline(self):
        """Test complete metrics pipeline from collection to Prometheus export."""
        from app.core.monitoring.metrics import MetricsCollector

        # Initialize components
        legacy_collector = MetricsCollector()
        bridge = MetricsBridge(legacy_collector, enable_langgraph=True)
        exporter = PrometheusExporter(port=9091)

        # Start Prometheus exporter
        await exporter.start()
        exporter.register_collector(bridge.otel_collector)

        # Simulate application metrics
        http_counter = bridge.register_counter("http_requests_total")
        http_counter.increment(1, {"method": "GET", "status": "200"})

        response_histogram = bridge.register_histogram("http_response_time_seconds")
        response_histogram.observe(0.150, {"endpoint": "/api/health"})

        # Simulate LangGraph metrics
        with bridge.langgraph_instrumentor.measure_node_execution("compliance_check") as ctx:
            ctx.set_status("success")
            time.sleep(0.1)

        # Wait for metrics to propagate
        await asyncio.sleep(0.5)

        # Fetch metrics from Prometheus endpoint
        import aiohttp

        async with aiohttp.ClientSession() as session:
            async with session.get("http://localhost:9091/metrics") as response:
                assert response.status == 200
                content = await response.text()

                # Verify all metrics present
                assert "http_requests_total" in content
                assert "http_response_time_seconds" in content
                assert "langgraph_node_executions_total" in content
                assert "langgraph_node_duration_seconds" in content

        # Cleanup
        await exporter.shutdown()

    def test_backwards_compatibility(self):
        """Test that existing code using MetricsCollector still works."""
        from app.core.monitoring.metrics import MetricsCollector

        # Existing code pattern
        collector = MetricsCollector()
        counter = collector.register_counter("legacy_counter")
        counter.increment(1)

        # Bridge should handle this transparently
        bridge = MetricsBridge(collector)
        bridge.sync_all_metrics()

        metrics_data = bridge.otel_collector.collect_metrics()
        assert "legacy_counter" in metrics_data
        assert metrics_data["legacy_counter"]["value"] == 1

    def test_metrics_persistence_across_restarts(self):
        """Test that metrics can be persisted and restored."""
        collector = OpenTelemetryMetricsCollector()

        # Create and record metrics
        counter = collector.create_counter("persistent_counter")
        counter.add(100)

        # Export metrics state
        state = collector.export_state()

        # Create new collector and restore state
        new_collector = OpenTelemetryMetricsCollector()
        new_collector.restore_state(state)

        # Verify metrics restored
        metrics_data = new_collector.collect_metrics()
        assert "persistent_counter" in metrics_data
        assert metrics_data["persistent_counter"]["value"] == 100

    def test_performance_overhead(self):
        """Test that metrics collection has minimal performance overhead."""
        import timeit

        collector = OpenTelemetryMetricsCollector()
        counter = collector.create_counter("perf_test_counter")

        # Measure overhead of metric recording
        def record_metric():
            counter.add(1, {"test": "true"})

        # Time 10000 metric recordings
        elapsed = timeit.timeit(record_metric, number=10000)

        # Should complete in under 1 second (100 microseconds per recording)
        assert elapsed < 1.0

        # Verify all metrics recorded
        metrics_data = collector.collect_metrics()
        assert metrics_data["perf_test_counter"]["value"] == 10000
