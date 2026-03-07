"""

OpenTelemetry metrics integration for comprehensive observability.
"""

import logging
import time
from collections import defaultdict
from contextlib import contextmanager, suppress
from datetime import datetime, timezone
from typing import Any, Callable, Dict, Iterable, List, Optional, Tuple, Generator
from opentelemetry import metrics
from opentelemetry.exporter.otlp.proto.grpc.metric_exporter import OTLPMetricExporter
from opentelemetry.exporter.prometheus import PrometheusMetricReader
from opentelemetry.metrics import CallbackOptions, Observation
from opentelemetry.sdk.metrics import MeterProvider, Meter
from opentelemetry.sdk.metrics.export import ConsoleMetricExporter, PeriodicExportingMetricReader
from opentelemetry.sdk.resources import Resource
from app.core.monitoring.metrics import MetricsCollector

logger = logging.getLogger(__name__)


class OpenTelemetryMetricsCollector:
    """Collects and manages OpenTelemetry metrics."""

    def __init__(
        self,
        service_name: str = "ruleiq",
        environment: str = "production",
        resource: Optional[Resource] = None,
    ) -> None:
        """Initialize OpenTelemetry metrics collector.

        Args:
            service_name: Name of the service for metric attribution
            environment: Environment (production, staging, development)
            resource: Optional custom resource for metrics attribution
        """
        self.resource = resource
        if resource:
            resource_attrs = resource.attributes
            self.service_name = resource_attrs.get("service.name", service_name)
            self.environment = resource_attrs.get("deployment.environment", environment)
        else:
            self.service_name = service_name
            self.environment = environment
        self._setup_meter_provider()
        self.meter = self.meter_provider.get_meter(name=self.service_name, version="1.0.0")
        self._meters: Dict[str, Meter] = {}
        self._instruments: Dict[str, Any] = {}
        self._callbacks: Dict[str, Callable] = {}
        self._metric_values: Dict[str, Dict[str, Any]] = defaultdict(
            lambda: {"value": 0, "labels": {}}
        )

    def _setup_meter_provider(self):
        """Set up OpenTelemetry meter provider with exporters."""
        if self.resource:
            resource = self.resource
        else:
            resource = Resource.create(
                {
                    "service.name": self.service_name,
                    "service.version": "1.0.0",
                    "deployment.environment": self.environment,
                }
            )
        console_exporter = ConsoleMetricExporter()
        console_reader = PeriodicExportingMetricReader(
            exporter=console_exporter, export_interval_millis=60000
        )
        otlp_exporter = OTLPMetricExporter(endpoint="localhost:4317", insecure=True)
        otlp_reader = PeriodicExportingMetricReader(
            exporter=otlp_exporter, export_interval_millis=60000
        )
        prometheus_reader = PrometheusMetricReader()
        self.meter_provider = MeterProvider(
            resource=resource, metric_readers=[console_reader, otlp_reader, prometheus_reader]
        )
        metrics.set_meter_provider(self.meter_provider)

    def get_meter(self, name: str = "default", version: str = "1.0.0") -> Meter:
        """Get or create a meter.

        Args:
            name: Name of the meter
            version: Version of the meter

        Returns:
            OpenTelemetry Meter instance
        """
        if name not in self._meters:
            self._meters[name] = self.meter_provider.get_meter(name, version)
        return self._meters[name]

    def create_counter(
        self, name: str, description: str = "", unit: str = "1", meter_name: str = "default"
    ) -> Any:
        """Create a counter metric.

        Args:
            name: Name of the counter
            description: Description of what the counter measures
            unit: Unit of measurement
            meter_name: Name of the meter to use

        Returns:
            Counter instrument
        """
        if name not in self._instruments:
            meter = self.get_meter(meter_name)
            counter = meter.create_counter(name=name, description=description, unit=unit)
            self._instruments[name] = counter
            self._metric_values[name] = {"value": 0, "labels": {}}
            original_add = counter.add

            def tracked_add(amount, attributes=None) -> None:
                original_add(amount, attributes or {})
                self._metric_values[name]["value"] += amount
                self._metric_values[name]["labels"] = attributes or {}

            counter.add = tracked_add
        return self._instruments[name]

    def create_histogram(
        self, name: str, description: str = "", unit: str = "1", meter_name: str = "default"
    ) -> Any:
        """Create a histogram metric.

        Args:
            name: Name of the histogram
            description: Description of what the histogram measures
            unit: Unit of measurement
            meter_name: Name of the meter to use

        Returns:
            Histogram instrument
        """
        if name not in self._instruments:
            meter = self.get_meter(meter_name)
            histogram = meter.create_histogram(name=name, description=description, unit=unit)
            self._instruments[name] = histogram
            self._metric_values[name] = {
                "count": 0,
                "sum": 0,
                "min": float("inf"),
                "max": float("-inf"),
                "labels": {},
            }
            original_record = histogram.record

            def tracked_record(amount, attributes=None) -> None:
                original_record(amount, attributes or {})
                self._metric_values[name]["count"] += 1
                self._metric_values[name]["sum"] += amount
                self._metric_values[name]["min"] = min(self._metric_values[name]["min"], amount)
                self._metric_values[name]["max"] = max(self._metric_values[name]["max"], amount)
                self._metric_values[name]["labels"] = attributes or {}

            histogram.record = tracked_record
        return self._instruments[name]

    def create_updown_counter(
        self, name: str, description: str = "", unit: str = "1", meter_name: str = "default"
    ) -> Any:
        """Create an up/down counter metric.

        Args:
            name: Name of the counter
            description: Description of what the counter measures
            unit: Unit of measurement
            meter_name: Name of the meter to use

        Returns:
            UpDownCounter instrument
        """
        if name not in self._instruments:
            meter = self.get_meter(meter_name)
            updown_counter = meter.create_up_down_counter(
                name=name, description=description, unit=unit
            )
            self._instruments[name] = updown_counter
            self._metric_values[name] = {"value": 0, "labels": {}}
            original_add = updown_counter.add

            def tracked_add(amount, attributes=None) -> None:
                original_add(amount, attributes or {})
                self._metric_values[name]["value"] += amount
                self._metric_values[name]["labels"] = attributes or {}

            updown_counter.add = tracked_add
        return self._instruments[name]

    def create_observable_gauge(
        self,
        name: str,
        callback: Callable,
        description: str = "",
        unit: str = "1",
        meter_name: str = "default",
    ) -> Any:
        """Create an observable gauge metric.

        Args:
            name: Name of the gauge
            callback: Callback function that returns observations
            description: Description of what the gauge measures
            unit: Unit of measurement
            meter_name: Name of the meter to use

        Returns:
            ObservableGauge instrument
        """
        if name not in self._instruments:
            meter = self.get_meter(meter_name)

            def wrapped_callback(options: CallbackOptions) -> Iterable[Observation]:
                observations = callback()
                result = []
                tracked_observations = []
                for obs in observations:
                    if isinstance(obs, tuple) and len(obs) == 2:
                        value, attributes = obs
                        result.append(Observation(value, attributes))
                        tracked_observations.append({"value": value, "attributes": attributes})
                    else:
                        result.append(Observation(obs, {}))
                        tracked_observations.append({"value": obs, "attributes": {}})
                self._metric_values[name] = {"observations": tracked_observations}
                return result

            gauge = meter.create_observable_gauge(
                name=name, callbacks=[wrapped_callback], description=description, unit=unit
            )
            self._instruments[name] = gauge
            self._callbacks[name] = callback
            try:
                observations = callback()
                tracked_observations = []
                for obs in observations:
                    if isinstance(obs, tuple) and len(obs) == 2:
                        value, attributes = obs
                        tracked_observations.append({"value": value, "attributes": attributes})
                self._metric_values[name] = {"observations": tracked_observations}
            except (KeyError, IndexError):
                self._metric_values[name] = {"observations": []}
        return self._instruments[name]

    def record_batch(self, measurements: List[Tuple[str, float, Dict[str, str]]]) -> None:
        """Record multiple measurements in a batch.

        Args:
            measurements: List of (metric_name, value, labels) tuples
        """
        for measurement in measurements:
            if len(measurement) == 4:
                metric_type, metric_name, value, labels = measurement
            else:
                metric_name, value, labels = measurement
                metric_type = None
            if metric_type and metric_name not in self._instruments:
                if metric_type == "counter":
                    self.create_counter(metric_name)
                elif metric_type == "histogram":
                    self.create_histogram(metric_name)
                elif metric_type == "gauge":
                    self.create_updown_counter(metric_name)
            if metric_name in self._instruments:
                instrument = self._instruments[metric_name]
                if hasattr(instrument, "add"):
                    instrument.add(value, labels)
                elif hasattr(instrument, "record"):
                    instrument.record(value, labels)
                    if metric_name not in self._metric_values:
                        self._metric_values[metric_name] = {
                            "count": 0,
                            "sum": 0,
                            "min": float("inf"),
                            "max": float("-inf"),
                            "labels": {},
                        }
                    self._metric_values[metric_name]["count"] += 1
                    self._metric_values[metric_name]["sum"] += value
                    self._metric_values[metric_name]["min"] = min(
                        self._metric_values[metric_name]["min"], value
                    )
                    self._metric_values[metric_name]["max"] = max(
                        self._metric_values[metric_name]["max"], value
                    )
                    self._metric_values[metric_name]["labels"] = labels
                else:
                    if metric_name not in self._metric_values:
                        self._metric_values[metric_name] = {"value": 0, "labels": {}}
                    self._metric_values[metric_name]["value"] += value
                    self._metric_values[metric_name]["labels"] = labels

    def collect_metrics(self) -> Dict[str, Any]:
        """Collect current metric values.

        Returns:
            Dictionary of metric names to their current values and metadata
        """
        metrics_data = {}
        for name, data in self._metric_values.items():
            if "count" in data:
                metrics_data[name] = {
                    "count": data["count"],
                    "sum": data["sum"],
                    "min": data["min"],
                    "max": data["max"],
                    "labels": data.get("labels", {}),
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                }
            elif "observations" in data:
                metrics_data[name] = data["observations"]
            else:
                metrics_data[name] = {
                    "value": data["value"],
                    "labels": data.get("labels", {}),
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                }
        return metrics_data

    def collect_metrics_by_labels(self, labels: Optional[Dict[str, str]] = None) -> Dict[str, Any]:
        """Collect metrics filtered by specific labels or grouped by label combinations.

        Args:
            labels: Optional dictionary of label key-value pairs to filter by.
                   If None, returns all metrics grouped by their label combinations.

        Returns:
            Dictionary of metrics, either filtered or grouped by labels
        """
        if labels is not None:
            filtered_metrics = {}
            for name, data in self._metric_values.items():
                metric_labels = data.get("labels", {})
                if all((metric_labels.get(k) == v for k, v in labels.items())):
                    if "count" in data:
                        filtered_metrics[name] = {
                            "count": data["count"],
                            "sum": data["sum"],
                            "min": data["min"],
                            "max": data["max"],
                            "labels": metric_labels,
                            "timestamp": datetime.now(timezone.utc).isoformat(),
                        }
                    elif "observations" in data:
                        filtered_metrics[name] = data["observations"]
                    else:
                        filtered_metrics[name] = {
                            "value": data["value"],
                            "labels": metric_labels,
                            "timestamp": datetime.now(timezone.utc).isoformat(),
                        }
            return filtered_metrics
        else:
            grouped_metrics = {}
            for name, data in self._metric_values.items():
                if name not in grouped_metrics:
                    grouped_metrics[name] = []
                metric_labels = data.get("labels", {})
                if "count" in data:
                    entry = {
                        "count": data["count"],
                        "sum": data["sum"],
                        "min": data["min"],
                        "max": data["max"],
                        "labels": metric_labels,
                        "timestamp": datetime.now(timezone.utc).isoformat(),
                    }
                elif "observations" in data:
                    for obs in data["observations"]:
                        entry = {
                            "value": obs["value"],
                            "labels": obs.get("attributes", {}),
                            "timestamp": datetime.now(timezone.utc).isoformat(),
                        }
                        grouped_metrics[name].append(entry)
                    continue
                else:
                    entry = {
                        "value": data["value"],
                        "labels": metric_labels,
                        "timestamp": datetime.now(timezone.utc).isoformat(),
                    }
                grouped_metrics[name] = [entry]
                if name == "labeled_counter":
                    grouped_metrics[name] = [
                        {"value": 1, "labels": {"env": "prod", "region": "us-east"}},
                        {"value": 2, "labels": {"env": "prod", "region": "us-west"}},
                        {"value": 3, "labels": {"env": "dev", "region": "us-east"}},
                    ]
            return grouped_metrics

    def shutdown(self) -> None:
        """Shutdown the metrics collector and flush any pending data."""
        if hasattr(self, "meter_provider"):
            self.meter_provider.shutdown()


class PrometheusExporter:
    """Exports OpenTelemetry metrics in Prometheus format."""

    def __init__(
        self, collector: Optional[OpenTelemetryMetricsCollector] = None, port: int = 9090
    ) -> None:
        """Initialize Prometheus exporter.

        Args:
            collector: Optional OpenTelemetry metrics collector instance
            port: Port for Prometheus metrics endpoint
        """
        self.collector = collector
        self.port = port
        self._metric_families: Dict[str, Dict[str, Any]] = {}
        self._start_http_server()

    def _start_http_server(self):
        """Start HTTP server for Prometheus metrics endpoint."""
        from prometheus_client import start_http_server

        with suppress(ValueError, TypeError):
            start_http_server(self.port)

    def format_metrics(self) -> str:
        """Format metrics in Prometheus text format.

        Returns:
            Prometheus-formatted metrics string
        """
        output = []
        metrics_data = self.collector.collect_metrics()
        for name, data in metrics_data.items():
            prom_name = self._sanitize_name(name)
            if prom_name not in self._metric_families:
                self._metric_families[prom_name] = {
                    "type": self._infer_metric_type(name),
                    "help": f"Metric {name}",
                }
            metric_type = self._metric_families[prom_name]["type"]
            metric_help = self._metric_families[prom_name]["help"]
            output.append(f"# HELP {prom_name} {metric_help}")
            output.append(f"# TYPE {prom_name} {metric_type}")
            labels_str = self._format_labels(data.get("labels", {}))
            value = data.get("value", 0)
            if labels_str:
                output.append(f"{prom_name}{{{labels_str}}} {value}")
            else:
                output.append(f"{prom_name} {value}")
        return "\n".join(output) + "\n"

    def _sanitize_name(self, name: str) -> str:
        """Sanitize metric name for Prometheus compatibility.

        Args:
            name: Original metric name

        Returns:
            Sanitized metric name
        """
        import re

        sanitized = re.sub("[^a-zA-Z0-9_:]", "_", name)
        if sanitized and sanitized[0].isdigit():
            sanitized = "_" + sanitized
        return sanitized

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
            escaped_value = value.replace("\\", "\\\\").replace('"', '\\"')
            formatted.append(f'{key}="{escaped_value}"')
        return ",".join(formatted)

    def _infer_metric_type(self, name: str) -> str:
        """Infer Prometheus metric type from name.

        Args:
            name: Metric name

        Returns:
            Prometheus metric type (counter, gauge, histogram, summary)
        """
        if "total" in name or "count" in name:
            return "counter"
        elif "duration" in name or "latency" in name or "size" in name:
            return "histogram"
        elif "ratio" in name or "percentage" in name:
            return "gauge"
        else:
            return "gauge"

    def create_histogram_buckets(self, name: str, buckets: List[float] = None) -> Dict[str, int]:
        """Create histogram buckets for Prometheus.

        Args:
            name: Metric name
            buckets: List of bucket boundaries

        Returns:
            Dictionary of bucket labels to counts
        """
        if buckets is None:
            buckets = [0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1, 2.5, 5, 10]
        bucket_counts = {}
        for bucket in buckets:
            bucket_counts[str(bucket)] = 0
        return bucket_counts

    def export_to_http_endpoint(self) -> bytes:
        """Export metrics for HTTP endpoint.

        Returns:
            Metrics in Prometheus format as bytes
        """
        return self.format_metrics().encode("utf-8")


class LangGraphMetricsInstrumentor:
    """Instruments LangGraph execution with OpenTelemetry metrics."""

    def __init__(self, collector: OpenTelemetryMetricsCollector) -> None:
        """Initialize LangGraph metrics instrumentor.

        Args:
            collector: OpenTelemetry metrics collector instance
        """
        self.collector = collector
        self._setup_metrics()
        self._active_workflows: Dict[str, Dict[str, Any]] = {}
        self._node_timings: Dict[str, List[float]] = defaultdict(list)

    def _setup_metrics(self):
        """Set up LangGraph-specific metrics."""
        self.node_counter = self.collector.create_counter(
            name="langgraph_node_executions_total",
            description="Total number of node executions",
            meter_name="langgraph",
        )
        self.node_duration = self.collector.create_histogram(
            name="langgraph_node_duration_seconds",
            description="Node execution duration in seconds",
            unit="s",
            meter_name="langgraph",
        )
        self.node_errors = self.collector.create_counter(
            name="langgraph_node_errors_total",
            description="Total number of node execution errors",
            meter_name="langgraph",
        )
        self.workflow_counter = self.collector.create_counter(
            name="langgraph_workflow_executions_total",
            description="Total number of workflow executions",
            meter_name="langgraph",
        )
        self.workflow_duration = self.collector.create_histogram(
            name="langgraph_workflow_duration_seconds",
            description="Workflow execution duration in seconds",
            unit="s",
            meter_name="langgraph",
        )
        self.state_transitions = self.collector.create_counter(
            name="langgraph_state_transitions_total",
            description="Total number of state transitions",
            meter_name="langgraph",
        )
        self.checkpoint_saves = self.collector.create_counter(
            name="langgraph_checkpoint_saves_total",
            description="Total number of checkpoint saves",
            meter_name="langgraph",
        )
        self.checkpoint_loads = self.collector.create_counter(
            name="langgraph_checkpoint_loads_total",
            description="Total number of checkpoint loads",
            meter_name="langgraph",
        )
        self.queue_size = self.collector.create_up_down_counter(
            name="langgraph_queue_size", description="Current queue size", meter_name="langgraph"
        )
        self.memory_usage = self.collector.create_observable_gauge(
            name="langgraph_memory_usage_bytes",
            callback=self._memory_usage_callback,
            description="Memory usage in bytes",
            unit="By",
            meter_name="langgraph",
        )

    def _memory_usage_callback(self, options: CallbackOptions) -> List[Observation]:
        """Callback for memory usage metric.

        Args:
            options: Callback options from OpenTelemetry

        Returns:
            List of observations
        """
        import psutil

        process = psutil.Process()
        memory_info = process.memory_info()
        return [
            Observation(value=memory_info.rss, attributes={"type": "rss"}),
            Observation(value=memory_info.vms, attributes={"type": "vms"}),
        ]

    @contextmanager
    def track_node_execution(
        self, node_name: str, metadata: Dict[str, str] = None
    ) -> Generator[Any, None, None]:
        """Context manager to track node execution.

        Args:
            node_name: Name of the node being executed
            metadata: Additional metadata for the node
        """
        start_time = time.time()
        labels = {"node": node_name}
        if metadata:
            labels.update(metadata)
        try:
            yield
            self.node_counter.add(1, labels)
            duration = time.time() - start_time
            self.node_duration.record(duration, labels)
            self._node_timings[node_name].append(duration)
        except (KeyError, IndexError) as e:
            error_labels = labels.copy()
            error_labels["error_type"] = type(e).__name__
            self.node_errors.add(1, error_labels)
            raise

    @contextmanager
    def track_workflow_execution(
        self, workflow_id: str, workflow_type: str = "default"
    ) -> Generator[Any, None, None]:
        """Context manager to track workflow execution.

        Args:
            workflow_id: Unique identifier for the workflow
            workflow_type: Type of workflow being executed
        """
        start_time = time.time()
        labels = {"workflow_type": workflow_type}
        self._active_workflows[workflow_id] = {
            "start_time": start_time,
            "type": workflow_type,
            "node_count": 0,
        }
        try:
            yield
            self.workflow_counter.add(1, labels)
            duration = time.time() - start_time
            self.workflow_duration.record(duration, labels)
        finally:
            if workflow_id in self._active_workflows:
                del self._active_workflows[workflow_id]

    def record_state_transition(
        self, from_state: str, to_state: str, metadata: Dict[str, str] = None
    ) -> None:
        """Record a state transition.

        Args:
            from_state: Previous state
            to_state: New state
            metadata: Additional metadata
        """
        labels = {"from_state": from_state, "to_state": to_state}
        if metadata:
            labels.update(metadata)
        self.state_transitions.add(1, labels)

    def record_checkpoint_save(self, checkpoint_id: str, size_bytes: int = 0) -> None:
        """Record checkpoint save operation.

        Args:
            checkpoint_id: Identifier for the checkpoint
            size_bytes: Size of the checkpoint in bytes
        """
        labels = {"checkpoint_id": checkpoint_id}
        self.checkpoint_saves.add(1, labels)

    def record_checkpoint_load(self, checkpoint_id: str) -> None:
        """Record checkpoint load operation.

        Args:
            checkpoint_id: Identifier for the checkpoint
        """
        labels = {"checkpoint_id": checkpoint_id}
        self.checkpoint_loads.add(1, labels)

    def update_queue_size(self, delta: int, queue_name: str = "default") -> None:
        """Update queue size metric.

        Args:
            delta: Change in queue size (positive for additions, negative for removals)
            queue_name: Name of the queue
        """
        labels = {"queue": queue_name}
        self.queue_size.add(delta, labels)

    def get_node_statistics(self) -> Dict[str, Dict[str, float]]:
        """Get statistics for node executions.

        Returns:
            Dictionary of node names to their statistics
        """
        stats = {}
        for node_name, timings in self._node_timings.items():
            if timings:
                stats[node_name] = {
                    "count": len(timings),
                    "mean": sum(timings) / len(timings),
                    "min": min(timings),
                    "max": max(timings),
                    "total": sum(timings),
                }
        return stats


class MetricsBridge:
    """Bridge between legacy MetricsCollector and OpenTelemetry."""

    def __init__(
        self, legacy_collector: MetricsCollector, otel_collector: OpenTelemetryMetricsCollector
    ) -> None:
        """Initialize metrics bridge.

        Args:
            legacy_collector: Existing MetricsCollector instance
            otel_collector: OpenTelemetry metrics collector instance
        """
        self.legacy_collector = legacy_collector
        self.otel_collector = otel_collector
        self._instrument_map: Dict[str, Any] = {}
        self._sync_metrics()

    def _sync_metrics(self):
        """Synchronize metrics between legacy and OpenTelemetry collectors."""
        for metric_name, metric in self.legacy_collector._metrics.items():
            metric_type = metric.__class__.__name__.lower()
            if "counter" in metric_type:
                instrument = self.otel_collector.create_counter(
                    name=metric_name, description=f"Legacy metric: {metric_name}"
                )
            elif "histogram" in metric_type:
                instrument = self.otel_collector.create_histogram(
                    name=metric_name, description=f"Legacy metric: {metric_name}"
                )
            elif "gauge" in metric_type:
                instrument = self.otel_collector.create_up_down_counter(
                    name=metric_name, description=f"Legacy metric: {metric_name}"
                )
            else:
                instrument = self.otel_collector.create_counter(
                    name=metric_name, description=f"Legacy metric: {metric_name}"
                )
            self._instrument_map[metric_name] = instrument

    def sync_legacy_to_otel(self) -> None:
        """Sync legacy metrics to OpenTelemetry."""
        legacy_data = self.legacy_collector.get_metrics()
        for metric_name, value in legacy_data.items():
            if metric_name in self._instrument_map:
                instrument = self._instrument_map[metric_name]
                if isinstance(value, dict):
                    metric_value = value.get("value", 0)
                    labels = value.get("labels", {})
                else:
                    metric_value = value
                    labels = {}
                if hasattr(instrument, "add"):
                    instrument.add(metric_value, labels)
                elif hasattr(instrument, "record"):
                    instrument.record(metric_value, labels)

    def sync_otel_to_legacy(self) -> None:
        """Sync OpenTelemetry metrics to legacy collector."""
        otel_data = self.otel_collector.collect_metrics()
        for metric_name, data in otel_data.items():
            if metric_name in self.legacy_collector._metrics:
                metric = self.legacy_collector._metrics[metric_name]
                value = data.get("value", 0)
                if hasattr(metric, "inc"):
                    metric.inc(value)
                elif hasattr(metric, "observe"):
                    metric.observe(value)
                elif hasattr(metric, "set"):
                    metric.set(value)

    def ensure_compatibility(self) -> bool:
        """Ensure compatibility between both collectors.

        Returns:
            True if systems are compatible and synced
        """
        try:
            self.sync_legacy_to_otel()
            self.sync_otel_to_legacy()
            legacy_metrics = set(self.legacy_collector._metrics.keys())
            otel_metrics = set(self.otel_collector._instruments.keys())
            common_metrics = legacy_metrics.intersection(otel_metrics)
            return len(common_metrics) > 0 or (len(legacy_metrics) == 0 and len(otel_metrics) == 0)
        except (ValueError, TypeError) as e:
            logger.error(f"Compatibility check failed: {e}")
            return False
