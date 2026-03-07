"""
import logging

# Constants
DEFAULT_RETRIES = 5.0

logger = logging.getLogger(__name__)

Performance Test Runner

Utility script to run comprehensive performance tests with proper setup,
monitoring, and reporting. Includes options for different test scenarios
and load levels.
"""

import argparse
import json
import os
import subprocess
import sys
import time
from pathlib import Path
from typing import Any, Dict, List, Optional
import psutil

project_root = Path(__file__).parent.parent.parent
sys.path.append(str(project_root))


class PerformanceTestRunner:
    """Orchestrates performance test execution and reporting"""

    def __init__(self, config: Dict[str, Any]):
        self.config = config
        self.results = {}
        self.start_time = None
        self.system_monitor = SystemMonitor()

    def run_all_tests(self) -> Dict[str, Any]:
        """Run all performance test suites"""
        logger.info("🚀 Starting ComplianceGPT Performance Test Suite")
        logger.info("=" * 60)
        self.start_time = time.time()
        self.system_monitor.start_monitoring()
        test_suites = [
            ("API Performance", self.run_api_performance_tests),
            ("Database Performance", self.run_database_performance_tests),
            ("Load Testing", self.run_load_tests),
            ("Memory Testing", self.run_memory_tests),
            ("Concurrency Testing", self.run_concurrency_tests),
        ]
        for suite_name, test_function in test_suites:
            if self.should_run_suite(suite_name):
                logger.info("\n📊 Running %s Tests..." % suite_name)
                try:
                    suite_results = test_function()
                    self.results[suite_name] = suite_results
                    logger.info("✅ %s completed successfully" % suite_name)
                except Exception as e:
                    logger.info("❌ %s failed: %s" % (suite_name, e))
                    self.results[suite_name] = {"error": str(e)}
        self.system_monitor.stop_monitoring()
        return self.generate_final_report()

    def should_run_suite(self, suite_name: str) -> bool:
        """Check if test suite should be run based on configuration"""
        if "include_suites" in self.config:
            return suite_name in self.config["include_suites"]
        if "exclude_suites" in self.config:
            return suite_name not in self.config["exclude_suites"]
        return True

    def run_api_performance_tests(self) -> Dict[str, Any]:
        """Run API performance tests using pytest-benchmark"""
        cmd = [
            "python",
            "-m",
            "pytest",
            "tests/performance/test_api_performance.py",
            "-v",
            "--benchmark-only",
            "--benchmark-json=performance_api_results.json",
            "--benchmark-sort=mean",
            f"--benchmark-warmup={self.config.get('warmup_iterations', 3)}",
            f"--benchmark-rounds={self.config.get('benchmark_rounds', 10)}",
        ]
        if self.config.get("benchmark_compare"):
            cmd.extend(["--benchmark-compare", self.config["benchmark_compare"]])
        result = subprocess.run(cmd, capture_output=True, text=True, cwd=project_root)
        benchmark_file = project_root / "performance_api_results.json"
        if benchmark_file.exists():
            with open(benchmark_file) as f:
                benchmark_data = json.load(f)
            return self.parse_benchmark_results(benchmark_data)
        return {"status": "completed", "stdout": result.stdout, "stderr": result.stderr}

    def run_database_performance_tests(self) -> Dict[str, Any]:
        """Run database performance tests"""
        cmd = [
            "python",
            "-m",
            "pytest",
            "tests/performance/test_database_performance.py",
            "-v",
            "--benchmark-only",
            "--benchmark-json=performance_db_results.json",
        ]
        result = subprocess.run(cmd, capture_output=True, text=True, cwd=project_root)
        benchmark_file = project_root / "performance_db_results.json"
        if benchmark_file.exists():
            with open(benchmark_file) as f:
                benchmark_data = json.load(f)
            return self.parse_benchmark_results(benchmark_data)
        return {"status": "completed", "stdout": result.stdout, "stderr": result.stderr}

    def run_load_tests(self) -> Dict[str, Any]:
        """Run load tests using Locust"""
        if not self.config.get("run_load_tests", False):
            return {"status": "skipped", "reason": "Load tests disabled"}
        locust_config = self.config.get("locust", {})
        users = locust_config.get("users", 10)
        spawn_rate = locust_config.get("spawn_rate", 2)
        duration = locust_config.get("duration", "60s")
        host = locust_config.get("host", "http://localhost:8000")
        cmd = [
            "locust",
            "-f",
            "tests/performance/locustfile.py",
            "--host",
            host,
            "--users",
            str(users),
            "--spawn-rate",
            str(spawn_rate),
            "--run-time",
            duration,
            "--html",
            "locust_report.html",
            "--csv",
            "locust_results",
            "--headless",
        ]
        print(f"Running Locust with {users} users, spawn rate {spawn_rate}/s for {duration}")
        subprocess.run(cmd, capture_output=True, text=True, cwd=project_root)
        return self.parse_locust_results()

    def run_memory_tests(self) -> Dict[str, Any]:
        """Run memory usage tests"""
        cmd = ["python", "-m", "pytest", "tests/performance/", "-k", "memory", "-v", "--tb=short"]
        initial_memory = psutil.virtual_memory().percent
        result = subprocess.run(cmd, capture_output=True, text=True, cwd=project_root)
        final_memory = psutil.virtual_memory().percent
        return {
            "status": "completed",
            "initial_memory_percent": initial_memory,
            "final_memory_percent": final_memory,
            "memory_increase": final_memory - initial_memory,
            "stdout": result.stdout,
            "stderr": result.stderr,
        }

    def run_concurrency_tests(self) -> Dict[str, Any]:
        """Run concurrency tests"""
        cmd = [
            "python",
            "-m",
            "pytest",
            "tests/performance/",
            "-k",
            "concurrent",
            "-v",
            "--tb=short",
        ]
        result = subprocess.run(cmd, capture_output=True, text=True, cwd=project_root)
        return {
            "status": "completed",
            "stdout": result.stdout,
            "stderr": result.stderr,
            "return_code": result.returncode,
        }

    def parse_benchmark_results(self, benchmark_data: Dict[str, Any]) -> Dict[str, Any]:
        """Parse pytest-benchmark results"""
        benchmarks = benchmark_data.get("benchmarks", [])
        summary = {
            "total_benchmarks": len(benchmarks),
            "fastest_test": None,
            "slowest_test": None,
            "average_time": 0,
            "performance_issues": [],
        }
        if benchmarks:
            fastest = min(benchmarks, key=lambda x: x["stats"]["mean"])
            slowest = max(benchmarks, key=lambda x: x["stats"]["mean"])
            summary["fastest_test"] = {
                "name": fastest["name"],
                "mean_time": fastest["stats"]["mean"],
                "min_time": fastest["stats"]["min"],
            }
            summary["slowest_test"] = {
                "name": slowest["name"],
                "mean_time": slowest["stats"]["mean"],
                "max_time": slowest["stats"]["max"],
            }
            total_time = sum(b["stats"]["mean"] for b in benchmarks)
            summary["average_time"] = total_time / len(benchmarks)
            for benchmark in benchmarks:
                mean_time = benchmark["stats"]["mean"]
                max_time = benchmark["stats"]["max"]
                if mean_time > 2.0:
                    summary["performance_issues"].append(
                        {
                            "test": benchmark["name"],
                            "issue": "slow_mean_time",
                            "value": mean_time,
                            "threshold": 2.0,
                        }
                    )
                if max_time > DEFAULT_RETRIES:
                    summary["performance_issues"].append(
                        {
                            "test": benchmark["name"],
                            "issue": "slow_max_time",
                            "value": max_time,
                            "threshold": 5.0,
                        }
                    )
        return summary

    def parse_locust_results(self) -> Dict[str, Any]:
        """Parse Locust load test results"""
        results = {"status": "completed"}
        csv_file = project_root / "locust_results_stats.csv"
        if csv_file.exists():
            import pandas as pd

            try:
                df = pd.read_csv(csv_file)
                if not df.empty:
                    total_requests = df["Request Count"].sum()
                    total_failures = df["Failure Count"].sum()
                    avg_response_time = df["Average Response Time"].mean()
                    results.update(
                        {
                            "total_requests": int(total_requests),
                            "total_failures": int(total_failures),
                            "failure_rate": total_failures / total_requests
                            if total_requests > 0
                            else 0,
                            "average_response_time": avg_response_time,
                            "endpoints_tested": len(df),
                        }
                    )
                    slow_endpoints = df[df["Average Response Time"] > 2000]
                    if not slow_endpoints.empty:
                        results["slow_endpoints"] = slow_endpoints[
                            ["Name", "Average Response Time"]
                        ].to_dict("records")
            except Exception as e:
                results["csv_parse_error"] = str(e)
        return results

    def generate_final_report(self) -> Dict[str, Any]:
        """Generate comprehensive performance test report"""
        total_time = time.time() - self.start_time
        system_metrics = self.system_monitor.get_metrics()
        report = {
            "summary": {
                "test_start_time": self.start_time,
                "total_duration": total_time,
                "suites_run": len(self.results),
                "system_metrics": system_metrics,
            },
            "results": self.results,
            "recommendations": self.generate_recommendations(),
            "config": self.config,
        }
        report_file = project_root / f"performance_report_{int(time.time())}.json"
        with open(report_file, "w") as f:
            json.dump(report, f, indent=2, default=str)
        logger.info("\n📄 Performance report saved to: %s" % report_file)
        self.print_summary(report)
        return report

    def generate_recommendations(self) -> List[Dict[str, str]]:
        """Generate performance improvement recommendations"""
        recommendations = []
        for suite_name, suite_results in self.results.items():
            if isinstance(suite_results, dict) and "performance_issues" in suite_results:
                for issue in suite_results["performance_issues"]:
                    if issue["issue"] == "slow_mean_time":
                        recommendations.append(
                            {
                                "priority": "high",
                                "category": "response_time",
                                "description": f"Optimize {issue['test']} - mean response time {issue['value']:.2f}s exceeds threshold",
                                "suggestion": "Consider database query optimization, caching, or algorithm improvements",
                            }
                        )
            if suite_name == "Load Testing" and isinstance(suite_results, dict):
                failure_rate = suite_results.get("failure_rate", 0)
                if failure_rate > 0.05:
                    recommendations.append(
                        {
                            "priority": "critical",
                            "category": "reliability",
                            "description": f"High failure rate detected: {failure_rate:.1%}",
                            "suggestion": "Investigate error handling, resource limits, and system stability",
                        }
                    )
                avg_response_time = suite_results.get("average_response_time", 0)
                if avg_response_time > 2000:
                    recommendations.append(
                        {
                            "priority": "medium",
                            "category": "performance",
                            "description": f"Average response time under load: {avg_response_time:.0f}ms",
                            "suggestion": "Consider performance optimizations, load balancing, or scaling",
                        }
                    )
        system_metrics = self.system_monitor.get_metrics()
        if system_metrics.get("max_cpu_percent", 0) > 80:
            recommendations.append(
                {
                    "priority": "medium",
                    "category": "resources",
                    "description": f"High CPU usage detected: {system_metrics['max_cpu_percent']:.1f}%",
                    "suggestion": "Monitor CPU usage in production, consider optimization or scaling",
                }
            )
        if system_metrics.get("max_memory_percent", 0) > 85:
            recommendations.append(
                {
                    "priority": "medium",
                    "category": "resources",
                    "description": f"High memory usage detected: {system_metrics['max_memory_percent']:.1f}%",
                    "suggestion": "Review memory usage patterns and consider memory optimization",
                }
            )
        return recommendations

    def print_summary(self, report: Dict[str, Any]):
        """Print performance test summary"""
        logger.info("\n" + "=" * 60)
        logger.info("📊 PERFORMANCE TEST SUMMARY")
        logger.info("=" * 60)
        summary = report["summary"]
        logger.info("⏱️  Total Duration: %s seconds" % summary["total_duration"])
        logger.info("🧪 Test Suites Run: %s" % summary["suites_run"])
        system_metrics = summary["system_metrics"]
        logger.info("💻 Peak CPU Usage: %s%" % system_metrics.get("max_cpu_percent", 0))
        print(f"🧠 Peak Memory Usage: {system_metrics.get('max_memory_percent', 0):.1f}%")
        logger.info("\n📈 RESULTS BY SUITE:")
        for suite_name, results in report["results"].items():
            if isinstance(results, dict):
                if "error" in results:
                    logger.info("❌ %s: FAILED - %s" % (suite_name, results["error"]))
                elif "total_benchmarks" in results:
                    issues = len(results.get("performance_issues", []))
                    print(f"✅ {suite_name}: {results['total_benchmarks']} tests, {issues} issues")
                elif "total_requests" in results:
                    failure_rate = results.get("failure_rate", 0)
                    print(
                        f"✅ {suite_name}: {results['total_requests']} requests, {failure_rate:.1%} failure rate"
                    )
                else:
                    logger.info("✅ %s: Completed" % suite_name)
            else:
                logger.info("✅ %s: Completed" % suite_name)
        recommendations = report["recommendations"]
        if recommendations:
            logger.info("\n💡 RECOMMENDATIONS (%s):" % len(recommendations))
            for rec in recommendations[:5]:
                priority_emoji = {"critical": "🚨", "high": "⚠️", "medium": "💛", "low": "💚"}
                emoji = priority_emoji.get(rec["priority"], "📝")
                logger.info("%s %s: %s" % (emoji, rec["priority"].upper(), rec["description"]))
        else:
            logger.info("\n🎉 No performance issues detected!")


class SystemMonitor:
    """Monitor system resources during performance tests"""

    def __init__(self):
        self.monitoring = False
        self.metrics = {
            "cpu_samples": [],
            "memory_samples": [],
            "start_time": None,
            "end_time": None,
        }

    def start_monitoring(self):
        """Start monitoring system resources"""
        self.monitoring = True
        self.metrics["start_time"] = time.time()
        self.metrics["cpu_samples"].append(psutil.cpu_percent())
        self.metrics["memory_samples"].append(psutil.virtual_memory().percent)

    def stop_monitoring(self):
        """Stop monitoring and finalize metrics"""
        self.monitoring = False
        self.metrics["end_time"] = time.time()
        self.metrics["cpu_samples"].append(psutil.cpu_percent())
        self.metrics["memory_samples"].append(psutil.virtual_memory().percent)

    def get_metrics(self) -> Dict[str, Any]:
        """Get collected system metrics"""
        cpu_samples = self.metrics["cpu_samples"]
        memory_samples = self.metrics["memory_samples"]
        return {
            "duration": self.metrics.get("end_time", time.time())
            - self.metrics.get("start_time", time.time()),
            "avg_cpu_percent": sum(cpu_samples) / len(cpu_samples) if cpu_samples else 0,
            "max_cpu_percent": max(cpu_samples) if cpu_samples else 0,
            "avg_memory_percent": sum(memory_samples) / len(memory_samples)
            if memory_samples
            else 0,
            "max_memory_percent": max(memory_samples) if memory_samples else 0,
            "sample_count": len(cpu_samples),
        }


def load_config(config_file: Optional[str] = None) -> Dict[str, Any]:
    """Load performance test configuration"""
    default_config = {
        "warmup_iterations": 3,
        "benchmark_rounds": 10,
        "run_load_tests": False,
        "locust": {
            "users": 10,
            "spawn_rate": 2,
            "duration": "60s",
            "host": "http://localhost:8000",
        },
    }
    if config_file and os.path.exists(config_file):
        with open(config_file) as f:
            file_config = json.load(f)
        default_config.update(file_config)
    return default_config


def main():
    """Main entry point for performance test runner"""
    parser = argparse.ArgumentParser(description="ComplianceGPT Performance Test Runner")
    parser.add_argument("--config", "-c", help="Configuration file path")
    parser.add_argument("--include", nargs="+", help="Test suites to include")
    parser.add_argument("--exclude", nargs="+", help="Test suites to exclude")
    parser.add_argument("--load-tests", action="store_true", help="Run load tests")
    parser.add_argument(
        "--users", type=int, default=10, help="Number of concurrent users for load tests"
    )
    parser.add_argument("--duration", default="60s", help="Load test duration")
    parser.add_argument(
        "--host", default="http://localhost:8000", help="Target host for load tests"
    )
    parser.add_argument("--benchmark-compare", help="Compare with previous benchmark results")
    args = parser.parse_args()
    config = load_config(args.config)
    if args.include:
        config["include_suites"] = args.include
    if args.exclude:
        config["exclude_suites"] = args.exclude
    if args.load_tests:
        config["run_load_tests"] = True
    if args.benchmark_compare:
        config["benchmark_compare"] = args.benchmark_compare
    config["locust"].update({"users": args.users, "duration": args.duration, "host": args.host})
    runner = PerformanceTestRunner(config)
    results = runner.run_all_tests()
    has_errors = any("error" in r for r in results["results"].values() if isinstance(r, dict))
    critical_recommendations = any(r["priority"] == "critical" for r in results["recommendations"])
    if has_errors or critical_recommendations:
        sys.exit(1)
    else:
        sys.exit(0)


if __name__ == "__main__":
    main()
