"""Report generation for evaluation results."""

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, Any, List
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from jinja2 import Environment, select_autoescape
import logging

logger = logging.getLogger(__name__)


class ReportGenerator:
    """Generates evaluation reports in various formats."""

    def __init__(self, output_dir: Path = None) -> None:
        self.output_dir = output_dir or Path("evaluation_reports")
        self.output_dir.mkdir(parents=True, exist_ok=True)
        # Create secure Jinja2 environment with autoescape enabled
        self.jinja_env = Environment(
            autoescape=select_autoescape(["html", "xml"]), enable_async=False
        )

    def generate_report(
        self, evaluation_result: Dict[str, Any], format: str = "html", include_charts: bool = True
    ) -> Path:
        """Generate evaluation report in specified format."""
        timestamp = evaluation_result.get("timestamp", datetime.now(timezone.utc).isoformat())
        report_name = f"evaluation_report_{timestamp.replace(':', '-')}"
        if format == "html":
            return self._generate_html_report(evaluation_result, report_name, include_charts)
        elif format == "json":
            return self._generate_json_report(evaluation_result, report_name)
        elif format == "markdown":
            return self._generate_markdown_report(evaluation_result, report_name)
        else:
            raise ValueError(f"Unsupported format: {format}")

    def _generate_html_report(
        self, result: Dict[str, Any], name: str, include_charts: bool
    ) -> Path:
        """Generate HTML report securely with XSS protection."""
        # Use secure template from environment with autoescape
        template = self.jinja_env.from_string(self._get_html_template())
        charts = {}
        if include_charts and "metrics" in result:
            charts = self._generate_charts(result["metrics"], name)
        html_content = template.render(
            result=result, charts=charts, timestamp=datetime.now(timezone.utc).isoformat()
        )
        report_path = self.output_dir / f"{name}.html"
        report_path.write_text(html_content)
        logger.info("HTML report generated: %s" % report_path)
        return report_path

    def _generate_json_report(self, result: Dict[str, Any], name: str) -> Path:
        """Generate JSON report."""
        clean_result = self._clean_for_json(result)
        report_path = self.output_dir / f"{name}.json"
        with open(report_path, "w") as f:
            json.dump(clean_result, f, indent=2, default=str)
        logger.info("JSON report generated: %s" % report_path)
        return report_path

    def _generate_markdown_report(self, result: Dict[str, Any], name: str) -> Path:
        """Generate Markdown report."""
        md_lines = []
        md_lines.append("# Evaluation Report")
        md_lines.append(f"\n**Generated:** {result.get('timestamp', 'N/A')}\n")
        if "summary" in result:
            md_lines.append("## Summary\n")
            summary = result["summary"]
            md_lines.append(f"- **Total Tasks:** {summary.get('total_tasks', 0)}")
            md_lines.append(f"- **Successful:** {summary.get('successful_tasks', 0)}")
            md_lines.append(f"- **Failed:** {summary.get('failed_tasks', 0)}")
            md_lines.append(f"- **Duration:** {summary.get('duration', 0):.2f}s\n")
        if "metrics" in result:
            md_lines.append("## Metrics\n")
            md_lines.append("| Metric | Mean | Std | Min | Max |")
            md_lines.append("|--------|------|-----|-----|-----|")
            for metric, stats in result["metrics"].items():
                if isinstance(stats, dict) and "mean" in stats:
                    md_lines.append(
                        f"| {metric} | {stats['mean']:.4f} | {stats.get('std', 0):.4f} | {stats.get('min', 0):.4f} | {stats.get('max', 0):.4f} |",
                    )
            md_lines.append("")
        if "regressions" in result and result["regressions"]:
            md_lines.append("## ⚠️ Regressions Detected\n")
            for reg in result["regressions"]:
                md_lines.append(
                    f"- **{reg['metric']}**: {reg['baseline']:.4f} → {reg['current']:.4f} ({reg['change'] * 100:.1f}% change)",
                )
            md_lines.append("")
        if "comparison" in result:
            md_lines.append("## Baseline Comparison\n")
            md_lines.append(
                "| Metric | Baseline | Current | Change | Status |",
            )
            md_lines.append(
                "|--------|----------|---------|--------|--------|",
            )
            for metric, comp in result["comparison"].items():
                status = "✅" if comp.get("improved", False) else "❌"
                md_lines.append(
                    f"| {metric} | {comp['baseline']:.4f} | {comp['current']:.4f} | {comp['change_pct']:.1f}% | {status} |",
                )
        report_path = self.output_dir / f"{name}.md"
        report_path.write_text("\n".join(md_lines))
        logger.info("Markdown report generated: %s" % report_path)
        return report_path

    def _generate_charts(self, metrics: Dict[str, Any], name: str) -> Dict[str, str]:
        """Generate charts for metrics."""
        charts = {}
        if any(isinstance(v, dict) and "mean" in v for v in metrics.values()):
            chart_path = self._create_metrics_chart(metrics, name)
            charts["metrics_chart"] = str(chart_path)
        return charts

    def _create_metrics_chart(self, metrics: Dict[str, Any], name: str) -> Path:
        """Create bar chart for metrics."""
        fig, ax = plt.subplots(figsize=(10, 6))
        metric_names = []
        means = []
        stds = []
        for metric, stats in metrics.items():
            if isinstance(stats, dict) and "mean" in stats:
                metric_names.append(metric)
                means.append(stats["mean"])
                stds.append(stats.get("std", 0))
        x = np.arange(len(metric_names))
        bars = ax.bar(x, means, yerr=stds, capsize=5)
        ax.set_xlabel("Metrics")
        ax.set_ylabel("Value")
        ax.set_title("Evaluation Metrics")
        ax.set_xticks(x)
        ax.set_xticklabels(metric_names, rotation=45, ha="right")
        for i, bar in enumerate(bars):
            if means[i] >= 0.9:
                bar.set_color("green")
            elif means[i] >= 0.7:
                bar.set_color("yellow")
            else:
                bar.set_color("red")
        plt.tight_layout()
        chart_path = self.output_dir / f"{name}_metrics.png"
        plt.savefig(chart_path, dpi=100)
        plt.close()
        return chart_path

    def _clean_for_json(self, obj: Any) -> Any:
        """Clean object for JSON serialization."""
        if isinstance(obj, dict):
            return {k: self._clean_for_json(v) for k, v in obj.items()}
        elif isinstance(obj, list):
            return [self._clean_for_json(item) for item in obj]
        elif isinstance(obj, (datetime, pd.Timestamp)):
            return obj.isoformat()
        elif isinstance(obj, np.ndarray):
            return obj.tolist()
        elif isinstance(obj, (np.integer, np.floating)):
            return float(obj)
        else:
            return obj

    def _get_html_template(self) -> str:
        """Get HTML report template."""
        return """
<!DOCTYPE html>
<html>
<head>
    <title>Evaluation Report</title>
    <style>
        body {
            font-family: Arial, sans-serif;
            max-width: 1200px;
            margin: 0 auto;
            padding: 20px;
            background-color: #f5f5f5;,
        }
        h1, h2 {
            color: #333;,
        }
        .summary {
            background: white;
            padding: 20px;
            border-radius: 8px;
            margin-bottom: 20px;
            box-shadow: 0 2px 4px rgba(0,0,0,0.1);,
        }
        .metrics-table {
            width: 100%;
            border-collapse: collapse;
            background: white;
            margin-bottom: 20px;,
        }
        .metrics-table th, .metrics-table td {
            padding: 12px;
            text-align: left;
            border-bottom: 1px solid #ddd;,
        }
        .metrics-table th {
            background-color: #4CAF50;
            color: white;,
        }
        .metrics-table tr:hover {
            background-color: #f5f5f5;,
        }
        .regression {
            background-color: #fff3cd;
            border: 1px solid #ffc107;
            padding: 15px;
            border-radius: 4px;
            margin-bottom: 20px;,
        }
        .regression h3 {
            color: #856404;
            margin-top: 0;,
        }
        .chart {
            background: white;
            padding: 20px;
            border-radius: 8px;
            margin-bottom: 20px;
            text-align: center;,
        }
        .status-good { color: green; }
        .status-bad { color: red; }
        .footer {
            text-align: center;
            color: #666;
            margin-top: 40px;
            padding-top: 20px;
            border-top: 1px solid #ddd;,
        }
    </style>
</head>
<body>
    <h1>Evaluation Report</h1>
    <p><strong>Generated:</strong> {{ timestamp }}</p>

    {% if result.summary %}
    <div class="summary">
        <h2>Summary</h2>
        <ul>
            <li><strong>Total Tasks:</strong> {{ result.summary.total_tasks }}</li>
            <li><strong>Successful:</strong> {{ result.summary.successful_tasks }}</li>
            <li><strong>Failed:</strong> {{ result.summary.failed_tasks }}</li>
            <li><strong>Duration:</strong> {{ "%.2f"|format(result.summary.duration) }}s</li>
        </ul>
    </div>
    {% endif %}

    {% if result.metrics %}
    <h2>Metrics</h2>
    <table class="metrics-table">
        <thead>
            <tr>
                <th>Metric</th>
                <th>Mean</th>
                <th>Std Dev</th>
                <th>Min</th>
                <th>Max</th>
                <th>Count</th>
            </tr>
        </thead>
        <tbody>
            {% for metric, stats in result.metrics.items() %}
            {% if stats is mapping and 'mean' in stats %}
            <tr>
                <td>{{ metric }}</td>
                <td>{{ "%.4f"|format(stats.mean) }}</td>
                <td>{{ "%.4f"|format(stats.std|default(0)) }}</td>
                <td>{{ "%.4f"|format(stats.min|default(0)) }}</td>
                <td>{{ "%.4f"|format(stats.max|default(0)) }}</td>
                <td>{{ stats.count|default(0) }}</td>
            </tr>
            {% endif %}
            {% endfor %}
        </tbody>
    </table>
    {% endif %}

    {% if result.regressions and result.regressions|length > 0 %}
    <div class="regression">
        <h3>⚠️ Regressions Detected</h3>
        <ul>
            {% for reg in result.regressions %}
            <li>
                <strong>{{ reg.metric }}:</strong>
                {{ "%.4f"|format(reg.baseline) }} → {{ "%.4f"|format(reg.current) }}
                ({{ "%.1f"|format(reg.change * 100) }}% change)
            </li>
            {% endfor %}
        </ul>
    </div>
    {% endif %}

    {% if result.comparison %}
    <h2>Baseline Comparison</h2>
    <table class="metrics-table">
        <thead>
            <tr>
                <th>Metric</th>
                <th>Baseline</th>
                <th>Current</th>
                <th>Change %</th>
                <th>Status</th>
            </tr>
        </thead>
        <tbody>
            {% for metric, comp in result.comparison.items() %}
            <tr>
                <td>{{ metric }}</td>
                <td>{{ "%.4f"|format(comp.baseline) }}</td>
                <td>{{ "%.4f"|format(comp.current) }}</td>
                <td>{{ "%.1f"|format(comp.change_pct) }}%</td>
                <td>
                    {% if comp.improved %}
                    <span class="status-good">✅ Improved</span>
                    {% else %}
                    <span class="status-bad">❌ Degraded</span>
                    {% endif %}
                </td>
            </tr>
            {% endfor %}
        </tbody>
    </table>
    {% endif %}

    {% if charts.metrics_chart %}
    <div class="chart">
        <h2>Metrics Visualization</h2>
        <img src="{{ charts.metrics_chart }}" alt="Metrics Chart" style="max-width: 100%;">
    </div>
    {% endif %}

    <div class="footer">
        <p>Generated by AI Evaluation Pipeline</p>
    </div>
</body>
</html>
"""


class TrendAnalyzer:
    """Analyzes trends in evaluation metrics over time."""

    def __init__(self, history_dir: Path = None) -> None:
        self.history_dir = history_dir or Path("evaluation_history")
        self.history_dir.mkdir(parents=True, exist_ok=True)

    def save_evaluation(self, result: Dict[str, Any]) -> None:
        """Save evaluation result to history."""
        timestamp = result.get("timestamp", datetime.now(timezone.utc).isoformat())
        filename = f"eval_{timestamp.replace(':', '-')}.json"
        filepath = self.history_dir / filename
        with open(filepath, "w") as f:
            json.dump(result, f, indent=2, default=str)

    def load_history(self, days_back: int = 30) -> List[Dict[str, Any]]:
        """Load evaluation history."""
        cutoff = datetime.now(timezone.utc) - pd.Timedelta(days=days_back)
        history = []
        for filepath in self.history_dir.glob("eval_*.json"):
            try:
                with open(filepath) as f:
                    data = json.load(f)
                timestamp = pd.to_datetime(data.get("timestamp"))
                if timestamp >= cutoff:
                    history.append(data)
            except Exception as e:
                logger.warning("Failed to load %s: %s" % (filepath, e))
        history.sort(key=lambda x: x.get("timestamp", ""))
        return history

    def analyze_trends(self, metric_name: str, days_back: int = 30) -> Dict[str, Any]:
        """Analyze trends for a specific metric."""
        history = self.load_history(days_back)
        if not history:
            return {"error": "No history available"}
        timestamps = []
        values = []
        for entry in history:
            if "metrics" in entry and metric_name in entry["metrics"]:
                metric_data = entry["metrics"][metric_name]
                if isinstance(metric_data, dict) and "mean" in metric_data:
                    timestamps.append(pd.to_datetime(entry["timestamp"]))
                    values.append(metric_data["mean"])
        if len(values) < 2:
            return {"error": "Insufficient data for trend analysis"}
        df = pd.DataFrame({"timestamp": timestamps, "value": values})
        df["rolling_mean"] = df["value"].rolling(window=3, min_periods=1).mean()
        df["rolling_std"] = df["value"].rolling(window=3, min_periods=1).std()
        x = np.arange(len(df))
        slope, intercept = np.polyfit(x, df["value"], 1)
        mean = df["value"].mean()
        std = df["value"].std()
        anomalies = df[np.abs(df["value"] - mean) > 2 * std]
        return {
            "metric": metric_name,
            "period": f"{days_back} days",
            "data_points": len(df),
            "current_value": float(df["value"].iloc[-1]),
            "mean": float(mean),
            "std": float(std),
            "trend_slope": float(slope),
            "trend_direction": "improving" if slope > 0 else "declining",
            "anomalies": anomalies.to_dict("records") if not anomalies.empty else [],
            "history": df.to_dict("records"),
        }

    def generate_trend_report(self, metrics: List[str], days_back: int = 30) -> Dict[str, Any]:
        """Generate trend report for multiple metrics."""
        report = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "period": f"{days_back} days",
            "metrics": {},
        }
        for metric in metrics:
            report["metrics"][metric] = self.analyze_trends(metric, days_back)
        return report
