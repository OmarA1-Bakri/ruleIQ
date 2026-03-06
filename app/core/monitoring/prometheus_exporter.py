"""

Prometheus metrics exporter with HTTP server and formatting.
"""

import asyncio
import logging
import re
import time
from collections import defaultdict
import http.server
from http.server import HTTPServer
import threading
from threading import Thread
from typing import Any, Dict, List, Optional, Generator

logger = logging.getLogger(__name__)
CONTENT_TYPE_LATEST = "text/plain; version=0.0.4; charset=utf-8"


class CollectorRegistry:
    """Mock Prometheus CollectorRegistry for compatibility."""

    def __init__(self) -> None:
        """Initialize registry."""
        self.collectors = []

    def register(self, collector) -> None:
        """Register a collector."""
        self.collectors.append(collector)

    def unregister(self, collector) -> None:
        """Unregister a collector."""
        if collector in self.collectors:
            self.collectors.remove(collector)

    def collect(self) -> Generator[Any, None, None]:
        """Collect metrics from all collectors."""
        for collector in self.collectors:
            yield from collector.collect()


class PrometheusFormatter:
    """Formats metrics in Prometheus text format."""

    def __init__(self) -> None:
        """Initialize Prometheus formatter."""
        self.metric_families: Dict[str, Dict[str, Any]] = {}
        self._type_map = {
            "counter": "counter",
            "gauge": "gauge",
            "histogram": "histogram",
            "summary": "summary",
            "untyped": "untyped",
        }

    def format_counter(self, metric_data: Dict[str, Any]) -> str:
        """Format counter metric.

        Args:
            metric_data: Metric data with name, value, labels, etc.

        Returns:
            Formatted counter string
        """
        name = metric_data["name"]
        value = metric_data.get("value", 0)
        labels = metric_data.get("labels", {})
        help_text = metric_data.get("description", metric_data.get("help", f"Counter {name}"))
        output = []
        output.append(f"# HELP {name} {help_text}")
        output.append(f"# TYPE {name} counter")
        if labels:
            label_str = self._format_labels(labels)
            output.append(f"{name}{{{label_str}}} {value}")
        else:
            output.append(f"{name} {value}")
        return "\n".join(output)

    def format_gauge(self, metric_data: Dict[str, Any]) -> str:
        """Format gauge metric.

        Args:
            metric_data: Metric data with name, value, labels, etc.

        Returns:
            Formatted gauge string
        """
        name = metric_data["name"]
        value = metric_data.get("value", 0)
        labels = metric_data.get("labels", {})
        help_text = metric_data.get("description", metric_data.get("help", f"Gauge {name}"))
        output = []
        output.append(f"# HELP {name} {help_text}")
        output.append(f"# TYPE {name} gauge")
        if labels:
            label_str = self._format_labels(labels)
            output.append(f"{name}{{{label_str}}} {value}")
        else:
            output.append(f"{name} {value}")
        return "\n".join(output)

    def format_histogram(self, metric_data: Dict[str, Any]) -> str:
        """Format histogram metric.

        Args:
            metric_data: Metric data with name, buckets, sum, count, labels, etc.

        Returns:
            Formatted histogram string
        """
        name = metric_data["name"]
        buckets = metric_data.get("buckets", {})
        sum_value = metric_data.get("sum", 0)
        count_value = metric_data.get("count", 0)
        labels = metric_data.get("labels", {})
        help_text = metric_data.get("description", metric_data.get("help", f"Histogram {name}"))
        output = []
        output.append(f"# HELP {name} {help_text}")
        output.append(f"# TYPE {name} histogram")
        base_labels = self._format_labels(labels) if labels else ""
        sorted_buckets = sorted(
            buckets.items(),
            key=lambda x: (
                float(x[0]) if x[0] not in ("+Inf", "inf", float("inf")) else float("inf")
            ),
        )
        for boundary, count in sorted_buckets:
            if boundary == float("inf") or boundary == "inf":
                boundary = "+Inf"
            if base_labels:
                output.append(f'{name}_bucket{{{base_labels},le="{boundary}"}} {count}')
            else:
                output.append(f'{name}_bucket{{le="{boundary}"}} {count}')
        if "+Inf" not in [str(b) if b != float("inf") else "+Inf" for b, _ in buckets.items()]:
            if base_labels:
                output.append(f'{name}_bucket{{{base_labels},le="+Inf"}} {count_value}')
            else:
                output.append(f'{name}_bucket{{le="+Inf"}} {count_value}')
        if base_labels:
            output.append(f"{name}_sum{{{base_labels}}} {sum_value}")
            output.append(f"{name}_count{{{base_labels}}} {count_value}")
        else:
            output.append(f"{name}_sum {sum_value}")
            output.append(f"{name}_count {count_value}")
        return "\n".join(output)

    def format_summary(self, metric_data: Dict[str, Any]) -> str:
        """Format summary metric.

        Args:
            metric_data: Metric data with name, quantiles, sum, count, labels, etc.

        Returns:
            Formatted summary string
        """
        name = metric_data["name"]
        quantiles = metric_data.get("quantiles", {})
        sum_value = metric_data.get("sum", 0)
        count_value = metric_data.get("count", 0)
        labels = metric_data.get("labels", {})
        help_text = metric_data.get("description", metric_data.get("help", f"Summary {name}"))
        output = []
        output.append(f"# HELP {name} {help_text}")
        output.append(f"# TYPE {name} summary")
        base_labels = self._format_labels(labels) if labels else ""
        for quantile, value in sorted(quantiles.items()):
            if base_labels:
                output.append(f'{name}{{{base_labels},quantile="{quantile}"}} {value}')
            else:
                output.append(f'{name}{{quantile="{quantile}"}} {value}')
        if base_labels:
            output.append(f"{name}_sum{{{base_labels}}} {sum_value}")
            output.append(f"{name}_count{{{base_labels}}} {count_value}")
        else:
            output.append(f"{name}_sum {sum_value}")
            output.append(f"{name}_count {count_value}")
        return "\n".join(output)

    def _format_labels(self, labels: Dict[str, str]) -> str:
        """Format labels for Prometheus.

        Args:
            labels: Dictionary of label key-value pairs

        Returns:
            Formatted label string
        """
        if not labels:
            return ""
        formatted = []
        for key, value in labels.items():
            escaped_value = self._escape_label_value(str(value))
            formatted.append(f'{key}="{escaped_value}"')
        return ",".join(formatted)

    def _escape_label_value(self, value: str) -> str:
        """Escape special characters in label values.

        Args:
            value: Label value to escape

        Returns:
            Escaped label value
        """
        value = value.replace("\\", "\\\\")
        value = value.replace('"', '\\"')
        value = value.replace("\n", "\\n")
        return value

    def format_metric(self, metric_data: Dict[str, Any]) -> str:
        """Format a metric based on its type.

        Args:
            metric_data: Metric data including type, name, value, labels, etc.

        Returns:
            Formatted metric string
        """
        metric_type = metric_data.get("type", "untyped")
        if metric_type == "counter":
            return self.format_counter(metric_data)
        elif metric_type == "gauge":
            return self.format_gauge(metric_data)
        elif metric_type == "histogram":
            return self.format_histogram(metric_data)
        elif metric_type == "summary":
            return self.format_summary(metric_data)
        else:
            return self.format_gauge(metric_data)

    def is_valid_metric_name(self, name: str) -> bool:
        """Check if a metric name is valid according to Prometheus naming rules.

        Args:
            name: Metric name to validate

        Returns:
            True if valid, False otherwise
        """
        import re

        pattern = "^[a-zA-Z_:][a-zA-Z0-9_:]*$"
        return bool(re.match(pattern, name))

    def sanitize_metric_name(self, name: str) -> str:
        """Sanitize metric name to be Prometheus-compliant.

        Args:
            name: Metric name to sanitize

        Returns:
            Sanitized metric name
        """
        import re

        sanitized = re.sub("[^a-zA-Z0-9_:]", "_", name)
        if sanitized and sanitized[0].isdigit():
            sanitized = "_" + sanitized
        return sanitized


class LabelSanitizer:
    """Sanitizes metric and label names for Prometheus compatibility."""

    def __init__(self) -> None:
        """Initialize label sanitizer."""
        self.metric_name_re = re.compile("^[a-zA-Z_:][a-zA-Z0-9_:]*$")
        self.label_name_re = re.compile("^[a-zA-Z_][a-zA-Z0-9_]*$")

    def sanitize_metric_name(self, name: str) -> str:
        """Sanitize metric name for Prometheus.

        Args:
            name: Original metric name

        Returns:
            Sanitized metric name
        """
        sanitized = re.sub("[^a-zA-Z0-9_:]", "_", name)
        if sanitized and (not re.match("^[a-zA-Z_:]", sanitized)):
            sanitized = "_" + sanitized
        sanitized = re.sub("_{2,}", "_", sanitized)
        if not self.metric_name_re.match(sanitized):
            sanitized = f"metric_{hash(name) % 1000000}"
        return sanitized

    def sanitize_label_name(self, name: str) -> str:
        """Sanitize label name for Prometheus.

        Args:
            name: Original label name

        Returns:
            Sanitized label name
        """
        original_name = name
        if name.startswith("__"):
            name = name[2:]
        if name.endswith("__"):
            name = name[:-2]
        sanitized = re.sub("[^a-zA-Z0-9_]", "_", name)
        if sanitized and (not re.match("^[a-zA-Z_]", sanitized)):
            sanitized = "_" + sanitized
        sanitized = re.sub("_{2,}", "_", sanitized)
        reserved = {"__name__", "job", "instance", "reserved"}
        if sanitized in reserved and original_name.endswith("__"):
            sanitized = f"{sanitized}_"
        if not self.label_name_re.match(sanitized):
            sanitized = f"label_{hash(name) % 1000000}"
        return sanitized

    def sanitize_label_value(self, value: Any) -> str:
        """Sanitize label value for Prometheus.

        Args:
            value: Original label value

        Returns:
            Sanitized label value as string
        """
        str_value = str(value)
        str_value = str_value.replace("\\", "\\\\")
        str_value = str_value.replace('"', '\\"')
        str_value = str_value.replace("\n", "\\n")
        str_value = str_value.replace("\r", "\\r")
        str_value = str_value.replace("\t", "\\t")
        if len(str_value) > 128:
            str_value = str_value[:125] + "..."
        return str_value

    def sanitize_labels(self, labels: Dict[str, Any]) -> Dict[str, str]:
        """Sanitize all labels in a dictionary.

        Args:
            labels: Original labels dictionary

        Returns:
            Sanitized labels dictionary
        """
        sanitized = {}
        for key, value in labels.items():
            sanitized_key = self.sanitize_label_name(key)
            sanitized_value = self.sanitize_label_value(value)
            sanitized[sanitized_key] = sanitized_value
        return sanitized

    def batch_sanitize(self, metrics: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Batch sanitize multiple metrics.

        Args:
            metrics: List of metric dictionaries

        Returns:
            List of sanitized metric dictionaries
        """
        sanitized_metrics = []
        for metric in metrics:
            sanitized_metric = metric.copy()
            if "name" in sanitized_metric:
                sanitized_metric["name"] = self.sanitize_metric_name(sanitized_metric["name"])
            if "labels" in sanitized_metric:
                sanitized_metric["labels"] = self.sanitize_labels(sanitized_metric["labels"])
            sanitized_metrics.append(sanitized_metric)
        return sanitized_metrics


class MetricTypeMapper:
    """Maps between different metric type systems."""

    def __init__(self) -> None:
        """Initialize metric type mapper."""
        self.otel_to_prometheus_map = {
            "Counter": "counter",
            "UpDownCounter": "gauge",
            "Histogram": "histogram",
            "ObservableCounter": "counter",
            "ObservableUpDownCounter": "gauge",
            "ObservableGauge": "gauge",
        }
        self.prometheus_to_otel = {
            "counter": "Counter",
            "gauge": "ObservableGauge",
            "histogram": "Histogram",
            "summary": "Histogram",
        }

    def map_otel_to_prometheus(self, otel_type: str) -> str:
        """Map OpenTelemetry metric type to Prometheus.

        Args:
            otel_type: OpenTelemetry metric type

        Returns:
            Prometheus metric type
        """
        return self.otel_to_prometheus_map.get(otel_type, "untyped")

    def map_prometheus_to_otel(self, prom_type: str) -> str:
        """Map Prometheus metric type to OpenTelemetry.

        Args:
            prom_type: Prometheus metric type

        Returns:
            OpenTelemetry metric type
        """
        return self.prometheus_to_otel.get(prom_type, "Counter")

    def validate_type(self, metric_type: str, system: str = "prometheus") -> bool:
        """Validate if metric type is valid for the system.

        Args:
            metric_type: Metric type to validate
            system: Metric system (prometheus or opentelemetry)

        Returns:
            True if valid, False otherwise
        """
        if system == "prometheus":
            valid_types = {"counter", "gauge", "histogram", "summary", "untyped"}
            return metric_type in valid_types
        elif system == "opentelemetry":
            valid_types = set(self.otel_to_prometheus.keys())
            return metric_type in valid_types
        else:
            return False

    def otel_to_prometheus(self, otel_type: str) -> str:
        """Wrapper for map_otel_to_prometheus for backward compatibility."""
        return self.map_otel_to_prometheus(otel_type)

    def custom_to_prometheus(self, custom_type: str) -> str:
        """Map custom metric types to Prometheus types.

        Args:
            custom_type: Custom metric type name

        Returns:
            Prometheus metric type
        """
        custom_mappings = {
            "incrementing_counter": "counter",
            "current_value": "gauge",
            "distribution": "histogram",
            "percentiles": "summary",
        }
        return custom_mappings.get(custom_type, "untyped")

    def is_valid_prometheus_type(self, metric_type: str) -> bool:
        """Check if a metric type is valid for Prometheus.

        Args:
            metric_type: Metric type to validate

        Returns:
            True if valid, False otherwise
        """
        return self.validate_type(metric_type, "prometheus")


class MetricsHTTPServer:
    """HTTP server for Prometheus metrics endpoint."""

    def __init__(self, port: int = 9090, path: str = "/metrics") -> None:
        """Initialize metrics HTTP server.

        Args:
            port: Port to listen on
            path: Path for metrics endpoint
        """
        self.port = port
        self.path = path
        self.server: Optional[HTTPServer] = None
        self.thread: Optional[Thread] = None
        self.metrics_callback: Optional[callable] = None
        self._is_running = False

    def set_metrics_callback(self, callback: callable) -> None:
        """Set callback function to get metrics.

        Args:
            callback: Function that returns metrics in Prometheus format
        """
        self.metrics_callback = callback

    async def start(self) -> None:
        """Start the metrics HTTP server asynchronously.

        This method is async for compatibility with test expectations.
        The actual server runs in a background thread.
        """
        if self._is_running:
            return

        class MetricsHandler(http.server.BaseHTTPRequestHandler):
            def do_GET(handler_self) -> None:
                if handler_self.path == self.path:
                    if self.metrics_callback:
                        try:
                            metrics = self.metrics_callback()
                            handler_self.send_response(200)
                            handler_self.send_header("Content-Type", CONTENT_TYPE_LATEST)
                            handler_self.end_headers()
                            handler_self.wfile.write(metrics.encode())
                        except Exception as e:
                            handler_self.send_response(500)
                            handler_self.end_headers()
                            handler_self.wfile.write(f"Error: {str(e)}".encode())
                    else:
                        handler_self.send_response(503)
                        handler_self.end_headers()
                        handler_self.wfile.write(b"No metrics callback registered")
                elif handler_self.path == "/health":
                    handler_self.send_response(200)
                    handler_self.send_header("Content-Type", CONTENT_TYPE_LATEST)
                    handler_self.end_headers()
                    handler_self.wfile.write(b"OK")
                else:
                    handler_self.send_response(404)
                    handler_self.end_headers()

            def log_message(self, format, *args) -> None:
                pass

        self.server = http.server.HTTPServer(("", self.port), MetricsHandler)
        self.thread = threading.Thread(target=self._run_server)
        self.thread.daemon = True
        self.thread.start()
        self._is_running = True
        await asyncio.sleep(0.1)

    def _run_server(self):
        """Run the HTTP server."""
        self.server.serve_forever()

    async def stop(self) -> None:
        """Stop the metrics HTTP server."""
        if self.server:
            self.server.shutdown()
            self.server = None
        if self.thread:
            self.thread.join(timeout=1)
            self.thread = None
        self._is_running = False

    async def shutdown(self) -> None:
        """Shutdown the metrics HTTP server (alias for stop)."""
        await self.stop()

    def is_running(self) -> bool:
        """Check if server is running.

        Returns:
            True if server is running
        """
        return self._is_running


class PrometheusMetricsExporter:
    """Main Prometheus metrics exporter."""

    def __init__(self, port: int = 9090, path: str = "/metrics", registry=None) -> None:
        """Initialize Prometheus metrics exporter.

        Args:
            port: Port for HTTP server
            path: Path for metrics endpoint
            registry: Optional prometheus_client CollectorRegistry for compatibility
        """
        self.formatter = PrometheusFormatter()
        self.sanitizer = LabelSanitizer()
        self.type_mapper = MetricTypeMapper()
        self.http_server = MetricsHTTPServer(port, path)
        self.registry = registry
        self._metrics_registry: Dict[str, Dict[str, Any]] = {}
        self._metric_families: Dict[str, str] = {}
        self._custom_collectors: List[callable] = []
        self._metrics: Dict[str, Any] = {}
        self.http_server.set_metrics_callback(self.export)

    def register_metric(
        self, name: str, metric_type: str, help_text: str = "", labels: List[str] = None
    ) -> None:
        """Register a metric with the exporter.

        Args:
            name: Metric name
            metric_type: Type of metric (counter, gauge, histogram, summary)
            help_text: Help text for the metric
            labels: List of label names
        """
        sanitized_name = self.sanitizer.sanitize_metric_name(name)
        if not self.type_mapper.validate_type(metric_type, "prometheus"):
            raise ValueError(f"Invalid metric type: {metric_type}")
        self._metric_families[sanitized_name] = metric_type
        self._metrics_registry[sanitized_name] = {
            "type": metric_type,
            "help": help_text or f"{metric_type} {name}",
            "labels": labels or [],
            "values": defaultdict(lambda: {"value": 0}),
        }

    def update_metric(
        self, name: str, value: float, labels: Dict[str, str] = None, operation: str = "set"
    ) -> None:
        """Update a metric value.

        Args:
            name: Metric name
            value: New value
            labels: Label values
            operation: Operation (set, inc, dec)
        """
        sanitized_name = self.sanitizer.sanitize_metric_name(name)
        if sanitized_name not in self._metrics_registry:
            self.register_metric(sanitized_name, "gauge")
        metric = self._metrics_registry[sanitized_name]
        sanitized_labels = self.sanitizer.sanitize_labels(labels or {})
        label_key = frozenset(sanitized_labels.items())
        if operation == "set":
            metric["values"][label_key]["value"] = value
        elif operation == "inc":
            metric["values"][label_key]["value"] += value
        elif operation == "dec":
            metric["values"][label_key]["value"] -= value
        metric["values"][label_key]["labels"] = sanitized_labels
        metric["values"][label_key]["timestamp"] = time.time()

    def bulk_update(self, updates: List[Dict[str, Any]]) -> None:
        """Bulk update multiple metrics.

        Args:
            updates: List of metric updates
        """
        for update in updates:
            name = update["name"]
            metric_type = update.get("type", "gauge")
            labels = update.get("labels", {})
            if name not in self._metrics:
                if metric_type == "counter":
                    metric = self.register_counter(name, f"{name} metric", list(labels.keys()))
                elif metric_type == "gauge":
                    metric = self.register_gauge(name, f"{name} metric", list(labels.keys()))
                elif metric_type == "histogram":
                    metric = self.register_histogram(name, f"{name} metric", list(labels.keys()))
                else:
                    metric = self.register_gauge(name, f"{name} metric", list(labels.keys()))
                self._metrics[name] = metric
            else:
                metric = self._metrics[name]
            if metric_type == "histogram":
                values = update.get("values", [])
                if hasattr(metric, "labels"):
                    labeled_metric = metric.labels(**labels) if labels else metric
                else:
                    labeled_metric = metric
                for value in values:
                    if hasattr(labeled_metric, "observe"):
                        labeled_metric.observe(value)
            else:
                value = update.get("value", 0)
                if hasattr(metric, "labels"):
                    labeled_metric = metric.labels(**labels) if labels else metric
                else:
                    labeled_metric = metric
                if metric_type == "counter":
                    if hasattr(labeled_metric, "inc"):
                        labeled_metric.inc(value)
                elif hasattr(labeled_metric, "set"):
                    labeled_metric.set(value)

    def add_custom_collector(self, collector: callable) -> None:
        """Add a custom metrics collector.

        Args:
            collector: Function that returns metrics in dict format
        """
        self._custom_collectors.append(collector)

    def export(self) -> str:
        """Export all metrics in Prometheus format.

        Returns:
            Prometheus-formatted metrics string
        """
        if self.registry and hasattr(self.registry, "__module__"):
            from prometheus_client import generate_latest

            return generate_latest(self.registry).decode("utf-8")
        output = []
        for name, metric in self._metrics_registry.items():
            metric_type = metric["type"]
            help_text = metric["help"]
            output.append(f"# HELP {name} {help_text}")
            output.append(f"# TYPE {name} {metric_type}")
            for _label_set, value_data in metric["values"].items():
                value = value_data["value"]
                labels = value_data.get("labels", {})
                if labels:
                    label_str = self.formatter._format_labels(labels)
                    output.append(f"{name}{{{label_str}}} {value}")
                else:
                    output.append(f"{name} {value}")
        for collector in self._custom_collectors:
            try:
                custom_metrics = collector()
                if custom_metrics:
                    output.append("")
                    output.append(custom_metrics)
            except Exception as e:
                logger.error(f"Error in custom collector: {e}")
        return "\n".join(output) + "\n"

    async def start_http_server(self) -> None:
        """Start the HTTP server for metrics endpoint."""
        await self.http_server.start()

    async def stop_http_server(self) -> None:
        """Stop the HTTP server."""
        await self.http_server.stop()

    def get_metric_families(self) -> Dict[str, str]:
        """Get all registered metric families.

        Returns:
            Dictionary of metric names to types
        """
        return self._metric_families.copy()

    def register_counter(self, name: str, description: str = "", labels: List[str] = None) -> Any:
        """Register a counter metric with prometheus_client compatibility.

        Args:
            name: Metric name
            description: Metric description
            labels: List of label names

        Returns:
            Counter-like object from prometheus_client
        """
        if self.registry and hasattr(self.registry, "__module__"):
            from prometheus_client import Counter

            return Counter(name, description, labels or [], registry=self.registry)
        self.register_metric(name, "counter", description, labels=labels or [])

        class MockCounter:
            def __init__(self, name) -> None:
                self.name = name
                self._labels = {}

            def labels(self, **kwargs) -> Any:
                key = str(kwargs)
                if key not in self._labels:
                    self._labels[key] = MockMetric()
                return self._labels[key]

        class MockMetric:
            def __init__(self) -> None:
                self.value = 0

            def inc(self, amount=1) -> None:
                self.value += amount

        return MockCounter(name)

    def register_gauge(self, name: str, description: str = "", labels: List[str] = None) -> Any:
        """Register a gauge metric with prometheus_client compatibility.

        Args:
            name: Metric name
            description: Metric description
            labels: List of label names

        Returns:
            Gauge-like object from prometheus_client
        """
        if self.registry and hasattr(self.registry, "__module__"):
            from prometheus_client import Gauge

            return Gauge(name, description, labels or [], registry=self.registry)
        self.register_metric(name, "gauge", description, labels=labels or [])

        class MockGauge:
            def __init__(self, name) -> None:
                self.name = name
                self._labels = {}

            def labels(self, **kwargs) -> Any:
                key = str(kwargs)
                if key not in self._labels:
                    self._labels[key] = MockMetric()
                return self._labels[key]

        class MockMetric:
            def __init__(self) -> None:
                self.value = 0

            def set(self, value) -> None:
                self.value = value

            def inc(self, amount=1) -> None:
                self.value += amount

            def dec(self, amount=1) -> None:
                self.value -= amount

        return MockGauge(name)

    def register_histogram(
        self, name: str, description: str = "", labels: List[str] = None, buckets=None
    ) -> Any:
        """Register a histogram metric with prometheus_client compatibility."""
        if self.registry and hasattr(self.registry, "__module__"):
            from prometheus_client import Histogram

            if buckets is None:
                return Histogram(name, description, labels or [], registry=self.registry)
            else:
                return Histogram(
                    name, description, labels or [], registry=self.registry, buckets=buckets
                )
        else:

            class MockHistogram:
                def __init__(self, name, description, labels) -> None:
                    self.name = name
                    self.description = description
                    self.label_names = labels
                    self._metrics = {}

                def labels(self, **kwargs) -> Any:
                    key = tuple(sorted(kwargs.items()))
                    if key not in self._metrics:
                        self._metrics[key] = MockHistogram(self.name, self.description, [])
                    return self._metrics[key]

                def observe(self, value) -> None:
                    pass

            return MockHistogram(name, description, labels or [])

    def update_metrics(self, metrics: Dict[str, Any]) -> None:
        """Update multiple metrics at once.

        Args:
            metrics: Dictionary of metric updates
        """
        self.bulk_update(metrics)

    async def start(self) -> None:
        """Start the HTTP server (async version)."""
        await self.http_server.start()

    async def shutdown(self) -> None:
        """Shutdown the exporter and HTTP server."""
        await self.http_server.shutdown()

    def push_metric(
        self, name: str, value: float, labels: Dict[str, str] = None, timestamp: int = None
    ) -> None:
        """Push a metric with an optional timestamp (for push gateway).

        Args:
            name: Metric name
            value: Metric value
            labels: Optional labels
            timestamp: Optional timestamp in milliseconds
        """
        if not hasattr(self, "_timestamped_metrics"):
            self._timestamped_metrics = {}
        metric_key = (name, tuple(sorted((labels or {}).items())))
        self._timestamped_metrics[metric_key] = {
            "name": name,
            "value": value,
            "labels": labels or {},
            "timestamp": timestamp,
        }
        self.update_metric(name, value, labels)

    def get_metrics_with_timestamps(self) -> Dict[str, Any]:
        """Get metrics with timestamps for push gateway.

        Returns:
            Dictionary containing metrics with timestamps
        """
        if not hasattr(self, "_timestamped_metrics"):
            return {}
        result = {}
        for _metric_key, metric_data in self._timestamped_metrics.items():
            name = metric_data["name"]
            result[name] = {
                "value": metric_data["value"],
                "labels": metric_data["labels"],
                "timestamp": metric_data.get("timestamp"),
            }
        return result

    def start_http_server_sync(self) -> None:
        """Start the HTTP server synchronously."""
        import asyncio

        asyncio.run(self.start())
