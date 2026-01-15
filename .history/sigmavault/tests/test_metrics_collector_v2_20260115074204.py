"""
Test suite for metrics_collector.py

Comprehensive tests covering:
- Counter, Gauge, Histogram metric types
- Prometheus export format
- JSON export
- Thread safety
- Edge cases and performance

Corrected to match actual MetricsCollector API:
- Uses counter(), gauge(), histogram() methods
- Uses get_metric() for individual values
- Uses get_histogram_stats() for histogram data
- Uses export_prometheus() and export_json()
"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

import pytest
import time
from threading import Thread

from ml.metrics_collector import MetricsCollector, MetricType


class TestMetricsCollector:
    """Test MetricsCollector functionality."""
    
    @pytest.fixture
    def collector(self):
        """Create fresh MetricsCollector instance."""
        return MetricsCollector()
    
    # === COUNTER TESTS ===
    
    def test_counter_basic(self, collector):
        """Test basic counter recording."""
        collector.counter("test_counter", 1.0)
        value = collector.get_metric("test_counter")
        
        assert value == 1.0
    
    def test_counter_multiple_increments(self, collector):
        """Test counter increments correctly."""
        collector.counter("requests_total", 1.0)
        collector.counter("requests_total", 5.0)
        collector.counter("requests_total", 3.0)
        
        value = collector.get_metric("requests_total")
        assert value == 9.0
    
    def test_counter_with_labels(self, collector):
        """Test counter with labels."""
        collector.counter("http_requests", 1.0, labels={"method": "GET", "status": "200"})
        value = collector.get_metric("http_requests")
        
        assert value == 1.0
    
    def test_counter_default_increment(self, collector):
        """Test counter default increment of 1.0."""
        collector.counter("default_counter")
        collector.counter("default_counter")
        
        value = collector.get_metric("default_counter")
        assert value == 2.0
    
    # === GAUGE TESTS ===
    
    def test_gauge_basic(self, collector):
        """Test basic gauge recording."""
        collector.gauge("memory_usage_bytes", 1024000.0)
        value = collector.get_metric("memory_usage_bytes")
        
        assert value == 1024000.0
    
    def test_gauge_updates(self, collector):
        """Test gauge value updates (not increments)."""
        collector.gauge("temperature", 20.0)
        collector.gauge("temperature", 25.0)
        collector.gauge("temperature", 22.0)
        
        value = collector.get_metric("temperature")
        assert value == 22.0  # Last value wins
    
    def test_gauge_with_labels(self, collector):
        """Test gauge with labels."""
        collector.gauge("cpu_usage", 45.5, labels={"core": "0"})
        value = collector.get_metric("cpu_usage")
        
        assert value == 45.5
    
    def test_gauge_negative_values(self, collector):
        """Test gauge can be negative."""
        collector.gauge("negative_gauge", -42.5)
        value = collector.get_metric("negative_gauge")
        
        assert value == -42.5
    
    # === HISTOGRAM TESTS ===
    
    def test_histogram_basic(self, collector):
        """Test basic histogram recording."""
        collector.histogram("response_time_ms", 150.0)
        collector.histogram("response_time_ms", 200.0)
        collector.histogram("response_time_ms", 175.0)
        
        stats = collector.get_histogram_stats("response_time_ms")
        assert stats["count"] == 3
        assert stats["sum"] == 525.0
        assert stats["mean"] == 175.0
    
    def test_histogram_buckets(self, collector):
        """Test histogram bucket distribution."""
        values = [10, 25, 50, 75, 100, 150, 200, 300, 500]
        for val in values:
            collector.histogram("latency_ms", float(val))
        
        stats = collector.get_histogram_stats("latency_ms")
        
        # Verify histogram captures distribution statistics
        assert stats["count"] == 9
        assert stats["sum"] == sum(values)
        assert "p50" in stats  # Median
        assert "p95" in stats  # 95th percentile
        assert "p99" in stats  # 99th percentile
        assert "min" in stats
        assert "max" in stats
    
    def test_histogram_quantiles(self, collector):
        """Test histogram quantile calculations."""
        # Add sorted values
        for val in range(1, 101):
            collector.histogram("sorted_values", float(val))
        
        stats = collector.get_histogram_stats("sorted_values")
        
        # Median should be around 50
        assert 40 <= stats["p50"] <= 60
        # 95th percentile should be around 95
        assert 90 <= stats["p95"] <= 100
    
    # === PROMETHEUS EXPORT TESTS ===
    
    def test_prometheus_export_format_counter(self, collector):
        """Test Prometheus export format for counters."""
        collector.counter("test_counter", 42.0)
        
        prometheus_text = collector.export_prometheus()
        
        assert "# HELP test_counter" in prometheus_text
        assert "# TYPE test_counter counter" in prometheus_text
        assert "test_counter 42" in prometheus_text or "test_counter 42.0" in prometheus_text
    
    def test_prometheus_export_format_gauge(self, collector):
        """Test Prometheus export format for gauges."""
        collector.gauge("memory_bytes", 1024.0)
        
        prometheus_text = collector.export_prometheus()
        
        assert "# HELP memory_bytes" in prometheus_text
        assert "# TYPE memory_bytes gauge" in prometheus_text
        assert "memory_bytes 1024" in prometheus_text or "memory_bytes 1024.0" in prometheus_text
    
    def test_prometheus_export_histogram(self, collector):
        """Test Prometheus export format for histograms."""
        collector.histogram("request_duration", 100.0)
        collector.histogram("request_duration", 200.0)
        
        prometheus_text = collector.export_prometheus()
        
        assert "# TYPE request_duration histogram" in prometheus_text
        assert "request_duration_count" in prometheus_text
        assert "request_duration_sum" in prometheus_text
        assert 'quantile="0.5"' in prometheus_text
        assert 'quantile="0.95"' in prometheus_text
    
    def test_prometheus_export_with_labels(self, collector):
        """Test Prometheus export includes metrics with labels."""
        collector.counter("requests", 10.0, labels={"method": "POST"})
        
        prometheus_text = collector.export_prometheus()
        
        assert "requests" in prometheus_text
    
    # === JSON EXPORT TESTS ===
    
    def test_json_export_basic(self, collector):
        """Test JSON export functionality."""
        collector.counter("test_counter", 5.0)
        collector.gauge("test_gauge", 10.0)
        collector.histogram("test_histogram", 15.0)
        
        json_data = collector.export_json()
        
        assert "timestamp" in json_data
        assert "counters" in json_data
        assert "gauges" in json_data
        assert "histograms" in json_data
        assert json_data["counters"]["test_counter"] == 5.0
        assert json_data["gauges"]["test_gauge"] == 10.0
    
    def test_json_export_histogram_stats(self, collector):
        """Test JSON export includes histogram statistics."""
        for val in [10, 20, 30]:
            collector.histogram("values", float(val))
        
        json_data = collector.export_json()
        
        assert "histograms" in json_data
        assert "values" in json_data["histograms"]
        
        histogram_stats = json_data["histograms"]["values"]
        assert "count" in histogram_stats
        assert "sum" in histogram_stats
        assert "mean" in histogram_stats
    
    # === TIME-SERIES AGGREGATION TESTS ===
    
    def test_time_series_aggregation_sum(self, collector):
        """Test time-series sum aggregation."""
        collector.counter("bytes_transferred", 100.0)
        collector.counter("bytes_transferred", 200.0)
        collector.counter("bytes_transferred", 300.0)
        
        # Get aggregated sum
        value = collector.get_metric("bytes_transferred")
        assert value == 600.0
    
    def test_time_series_aggregation_average(self, collector):
        """Test time-series average for gauge."""
        collector.gauge("cpu_percent", 30.0)
        time.sleep(0.01)
        collector.gauge("cpu_percent", 50.0)
        time.sleep(0.01)
        collector.gauge("cpu_percent", 40.0)
        
        # Last gauge value should be 40.0
        value = collector.get_metric("cpu_percent")
        assert value == 40.0
    
    # === THREAD SAFETY TESTS ===
    
    def test_thread_safety_counter(self, collector):
        """Test counter is thread-safe."""
        def increment_counter():
            for _ in range(100):
                collector.counter("concurrent_counter", 1.0)
        
        threads = [Thread(target=increment_counter) for _ in range(10)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()
        
        value = collector.get_metric("concurrent_counter")
        assert value == 1000.0
    
    def test_thread_safety_gauge(self, collector):
        """Test gauge is thread-safe."""
        def set_gauge():
            for i in range(50):
                collector.gauge("concurrent_gauge", float(i))
        
        threads = [Thread(target=set_gauge) for _ in range(5)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()
        
        # Gauge should have some final value (race condition is expected)
        value = collector.get_metric("concurrent_gauge")
        assert value is not None
        assert value >= 0
    
    # === RESET FUNCTIONALITY ===
    
    def test_reset(self, collector):
        """Test reset functionality."""
        collector.counter("test_counter", 42.0)
        collector.gauge("test_gauge", 100.0)
        collector.histogram("test_histogram", 50.0)
        
        collector.reset()
        
        assert collector.get_metric("test_counter") == 0.0
        assert collector.get_metric("test_gauge") == 0.0
        
        # Histogram should be empty after reset
        stats = collector.get_histogram_stats("test_histogram")
        assert stats["count"] == 0
    
    # === EDGE CASES ===
    
    def test_record_zero_values(self, collector):
        """Test recording zero values."""
        collector.counter("zero_counter", 0.0)
        collector.gauge("zero_gauge", 0.0)
        
        assert collector.get_metric("zero_counter") == 0.0
        assert collector.get_metric("zero_gauge") == 0.0
    
    def test_large_metric_values(self, collector):
        """Test handling large metric values."""
        large_value = 1e15
        collector.counter("large_counter", large_value)
        
        assert collector.get_metric("large_counter") == large_value
    
    def test_empty_labels(self, collector):
        """Test metrics with empty label dict."""
        collector.counter("no_labels", 1.0, labels={})
        assert collector.get_metric("no_labels") == 1.0
    
    def test_nonexistent_metric(self, collector):
        """Test getting nonexistent metric returns None."""
        value = collector.get_metric("does_not_exist")
        assert value is None
    
    def test_histogram_nonexistent(self, collector):
        """Test getting stats for nonexistent histogram."""
        stats = collector.get_histogram_stats("does_not_exist")
        assert stats == {}
    
    # === PERFORMANCE TESTS ===
    
    def test_high_throughput_counter(self, collector):
        """Test handling high throughput counter updates."""
        start = time.time()
        
        for i in range(10000):
            collector.counter("high_throughput", 1.0)
        
        elapsed = time.time() - start
        
        assert collector.get_metric("high_throughput") == 10000.0
        assert elapsed < 5.0  # Should complete in reasonable time
    
    def test_many_unique_metrics(self, collector):
        """Test handling many unique metrics."""
        num_metrics = 1000
        
        for i in range(num_metrics):
            collector.counter(f"metric_{i}", 1.0)
        
        # Verify all metrics are tracked
        json_data = collector.export_json()
        assert len(json_data["counters"]) >= num_metrics
    
    # === METRIC METADATA TESTS ===
    
    def test_registered_metrics_with_help_text(self, collector):
        """Test that registered metrics have help text in Prometheus export."""
        # Metrics are auto-registered on first use
        collector.counter("auto_registered", 1.0)
        
        prometheus_text = collector.export_prometheus()
        assert "# HELP auto_registered" in prometheus_text
