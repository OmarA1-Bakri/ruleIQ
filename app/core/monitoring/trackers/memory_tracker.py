"""
Memory usage tracking for LangGraph components.
"""

import time
from collections import defaultdict, deque
from typing import Any, Deque, Dict, List

import psutil


class MemoryUsageTracker:
    """Tracks memory usage for LangGraph components."""

    def __init__(self, sample_interval: int = 60) -> None:
        """Initialize memory usage tracker.

        Args:
            sample_interval: Sampling interval in seconds
        """
        self.sample_interval = sample_interval
        self._samples: Deque[Dict[str, Any]] = deque(maxlen=1000)
        self._component_memory: Dict[str, List[Dict[str, Any]]] = defaultdict(list)
        self._process = psutil.Process()
        self._last_sample_time = 0
        self._memory_limits: Dict[str, int] = {}

    def sample_memory(self) -> Dict[str, Any]:
        """Sample current memory usage.

        Returns:
            Memory usage statistics
        """
        current_time = time.time()
        if current_time - self._last_sample_time < self.sample_interval:
            return {}

        memory_info = self._process.memory_info()
        memory_percent = self._process.memory_percent()

        sample = {
            'timestamp': current_time,
            'rss_bytes': memory_info.rss,
            'vms_bytes': memory_info.vms,
            'memory_percent': memory_percent,
            'available_mb': psutil.virtual_memory().available / (1024 * 1024)
        }

        self._samples.append(sample)
        self._last_sample_time = current_time

        return sample

    def track_component(self, component_name: str, size_bytes: int) -> None:
        """Track memory usage for a specific component.

        Args:
            component_name: Name of the component
            size_bytes: Memory usage in bytes
        """
        entry = {
            'timestamp': time.time(),
            'bytes_used': size_bytes
        }
        self._component_memory[component_name].append(entry)

        # Keep only last 100 entries per component
        if len(self._component_memory[component_name]) > 100:
            self._component_memory[component_name] = self._component_memory[component_name][-100:]

    def get_memory_trends(self) -> Dict[str, Any]:
        """Get memory usage trends.

        Returns:
            Memory trend analysis
        """
        if not self._samples:
            return {}

        recent_samples = list(self._samples)[-10:]
        older_samples = list(self._samples)[:-10] if len(self._samples) > 10 else []

        trends = {}

        if recent_samples:
            recent_avg = sum(s['rss_bytes'] for s in recent_samples) / len(recent_samples)
            trends['current_rss_mb'] = recent_avg / (1024 * 1024)

        if older_samples:
            older_avg = sum(s['rss_bytes'] for s in older_samples) / len(older_samples)
            trends['previous_rss_mb'] = older_avg / (1024 * 1024)
            trends['growth_rate'] = (recent_avg - older_avg) / older_avg if older_avg > 0 else 0

        return trends

    def detect_memory_leak(self, threshold_mb: float = 100) -> bool:
        """Detect potential memory leaks.

        Args:
            threshold_mb: Threshold for leak detection in MB

        Returns:
            True if potential leak detected
        """
        if len(self._samples) < 10:
            return False

        samples = list(self._samples)[-10:]
        rss_values = [s['rss_bytes'] for s in samples]

        # Check if memory is consistently growing
        is_growing = all(rss_values[i] > rss_values[i - 1] for i in range(1, len(rss_values)))
        total_growth = (rss_values[-1] - rss_values[0]) / (1024 * 1024)

        return is_growing and total_growth > threshold_mb

    def detect_memory_leaks(
        self,
        growth_threshold_mb_per_hour: float = 10.0
    ) -> Dict[str, Dict[str, Any]]:
        """Detect potential memory leaks across all components.

        Args:
            growth_threshold_mb_per_hour: Memory growth threshold in MB/hour to consider a leak

        Returns:
            Dictionary mapping component names to leak detection results
        """
        leaks = {}

        for component, entries in self._component_memory.items():
            if len(entries) < 2:
                continue

            first = entries[0]
            last = entries[-1]

            time_diff_seconds = last['timestamp'] - first['timestamp']
            if time_diff_seconds <= 0:
                continue

            time_diff_hours = time_diff_seconds / 3600.0
            growth_bytes = last['bytes_used'] - first['bytes_used']
            growth_mb = growth_bytes / (1024 * 1024)
            growth_rate_mb_per_hour = growth_mb / time_diff_hours if time_diff_hours > 0 else 0

            suspected_leak = growth_rate_mb_per_hour >= growth_threshold_mb_per_hour

            if suspected_leak or growth_mb > 0:
                leaks[component] = {
                    'suspected_leak': suspected_leak,
                    'growth_rate_mb_per_hour': growth_rate_mb_per_hour,
                    'total_growth_mb': growth_mb,
                    'time_window_hours': time_diff_hours,
                    'initial_mb': first['bytes_used'] / (1024 * 1024),
                    'current_mb': last['bytes_used'] / (1024 * 1024)
                }

        return leaks

    def get_component_stats(self, component: str = None) -> Dict[str, Any]:
        """Get memory statistics for a specific component or all components.

        Args:
            component: Component name to get stats for, or None for all

        Returns:
            Dictionary with memory statistics
        """
        if component:
            if component not in self._component_memory:
                return {
                    'current_bytes': 0,
                    'allocated_bytes': 0,
                    'usage_ratio': 0.0,
                    'current_mb': 0.0,
                    'average_mb': 0.0,
                    'peak_mb': 0.0,
                    'min_mb': 0.0
                }

            entries = self._component_memory[component]
            if not entries:
                return {
                    'current_bytes': 0,
                    'allocated_bytes': 0,
                    'usage_ratio': 0.0,
                    'current_mb': 0.0,
                    'average_mb': 0.0,
                    'peak_mb': 0.0,
                    'min_mb': 0.0
                }

            latest = entries[-1]
            current_bytes = latest['bytes_used']
            allocated_bytes = latest.get('bytes_allocated', current_bytes)
            bytes_used_values = [e['bytes_used'] for e in entries]

            return {
                'current_bytes': current_bytes,
                'allocated_bytes': allocated_bytes,
                'usage_ratio': current_bytes / allocated_bytes if allocated_bytes > 0 else 0.0,
                'current_mb': current_bytes / (1024 * 1024),
                'average_mb': sum(bytes_used_values) / len(bytes_used_values) / (1024 * 1024),
                'peak_mb': max(bytes_used_values) / (1024 * 1024),
                'min_mb': min(bytes_used_values) / (1024 * 1024)
            }
        else:
            all_stats = {}
            for comp_name in self._component_memory:
                all_stats[comp_name] = self.get_component_stats(comp_name)
            return all_stats

    def get_total_memory_usage(self) -> Dict[str, Any]:
        """Get total memory usage across all components.

        Returns:
            Dictionary with total memory statistics
        """
        total_used = 0
        total_allocated = 0

        for _component, entries in self._component_memory.items():
            if entries:
                latest = entries[-1]
                total_used += latest['bytes_used']
                total_allocated += latest.get('bytes_allocated', latest['bytes_used'])

        return {
            'total_used_bytes': total_used,
            'total_allocated_bytes': total_allocated,
            'usage_ratio': total_used / total_allocated if total_allocated > 0 else 0.0,
            'total_used_mb': total_used / (1024 * 1024),
            'total_allocated_mb': total_allocated / (1024 * 1024)
        }

    def analyze_memory_growth(self, component: str) -> Dict[str, Any]:
        """Analyze memory growth patterns for a component.

        Args:
            component: Component name to analyze

        Returns:
            Dictionary with growth analysis
        """
        if component not in self._component_memory or len(self._component_memory[component]) < 1:
            return {
                'initial_bytes': 0,
                'current_bytes': 0,
                'growth_bytes': 0,
                'growth_rate_bytes_per_second': 0.0,
                'growth_rate_mb_per_sec': 0.0,
                'total_growth_mb': 0.0,
                'growth_percentage': 0.0,
                'is_growing': False
            }

        entries = self._component_memory[component]
        first_entry = entries[0]
        last_entry = entries[-1]

        first_bytes = first_entry['bytes_used']
        last_bytes = last_entry['bytes_used']

        if len(entries) > 1:
            time_diff = last_entry['timestamp'] - first_entry['timestamp']
            if time_diff <= 0:
                time_diff = 1
        else:
            time_diff = 1

        growth_bytes = last_bytes - first_bytes
        growth_mb = growth_bytes / (1024 * 1024)
        growth_rate_bytes = growth_bytes / time_diff if time_diff > 0 else 0
        growth_rate_mb = growth_mb / time_diff if time_diff > 0 else 0
        growth_percentage = (last_bytes - first_bytes) / first_bytes * 100 if first_bytes > 0 else 0

        return {
            'initial_bytes': first_bytes,
            'current_bytes': last_bytes,
            'growth_bytes': growth_bytes,
            'growth_rate_bytes_per_second': growth_rate_bytes,
            'growth_rate_mb_per_sec': growth_rate_mb,
            'total_growth_mb': growth_mb,
            'growth_percentage': growth_percentage,
            'is_growing': growth_bytes > 0
        }

    def set_memory_limit(self, component: str, max_bytes: int) -> None:
        """Set memory limit for a component.

        Args:
            component: Component name
            max_bytes: Maximum allowed memory in bytes
        """
        self._memory_limits[component] = max_bytes

    def check_memory_limit(
        self,
        component: str,
        current_bytes: int = None
    ) -> bool:
        """Check if a component is within its memory limit.

        Args:
            component: Component name to check
            current_bytes: Current memory usage in bytes (if not provided, uses latest recorded)

        Returns:
            True if within limit or no limit set, False if over limit
        """
        if component not in self._memory_limits:
            return True

        limit = self._memory_limits[component]

        if current_bytes is None:
            if component in self._component_memory and self._component_memory[component]:
                current_bytes = self._component_memory[component][-1]['bytes_used']
            else:
                current_bytes = 0

        return current_bytes <= limit

    def get_limit_violations(self) -> Dict[str, Dict[str, Any]]:
        """Get components that have violated their memory limits.

        Returns:
            Dictionary mapping component names to violation details
        """
        violations = {}

        for component, limit in self._memory_limits.items():
            current_bytes = 0
            if component in self._component_memory and self._component_memory[component]:
                current_bytes = self._component_memory[component][-1]['bytes_used']

            if current_bytes > limit:
                violations[component] = {
                    'current_bytes': current_bytes,
                    'limit_bytes': limit,
                    'over_limit_bytes': current_bytes - limit,
                    'usage_ratio': current_bytes / limit if limit > 0 else 0
                }

        return violations

    def record_memory_usage(
        self,
        component: str,
        bytes_used: int,
        bytes_allocated: int = None
    ) -> None:
        """Record memory usage for a component.

        Args:
            component: Name of the component
            bytes_used: Bytes currently used
            bytes_allocated: Bytes allocated (optional)
        """
        if component not in self._component_memory:
            self._component_memory[component] = []

        entry = {
            'timestamp': time.time(),
            'bytes_used': bytes_used,
            'bytes_allocated': bytes_allocated or bytes_used
        }

        self._component_memory[component].append(entry)
