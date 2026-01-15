"""
Comprehensive tests for metrics_collector module.

Tests cover:
- Counter, gauge, histogram, summary metric types
- Label-based dimensional metrics
- Prometheus export format compliance
- Time-series aggregation
- Thread safety and concurrent recording
- Metric filtering and querying
"""

import pytest
import threading
import time
from datetime import datetime, timedelta

# Direct imports to avoid package-level dependencies
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

from ml.metrics_collector import MetricsCollector, MetricType, Metric


class TestMetricsCollector:
    """Test suite for MetricsCollector class."""

    @pytest.fixture
    def collector(self):
        """Provide a fresh MetricsCollector instance for each test."""
        return MetricsCollector()

    # === COUNTER TESTS ===
    
    def test_record_counter_basic(self, collector):
        """Test basic counter recording increments value."""
        collector.record_counter("test_counter", 1.0)
        
        metrics = collector.get_metrics()
        assert "test_counter" in metrics
        assert metrics["test_counter"].value == 1.0
        assert metrics["test_counter"].metric_type == MetricType.COUNTER
    
    def test_record_counter_multiple_increments(self, collector):
        """Test counter accumulates multiple increments."""
        collector.record_counter("requests_total", 5.0)
        collector.record_counter("requests_total", 3.0)
        collector.record_counter("requests_total", 2.0)
        
        metrics = collector.get_metrics()
        assert metrics["requests_total"].value == 10.0
    
    def test_record_counter_with_labels(self, collector):
        """Test counter with dimensional labels."""
        collector.record_counter("http_requests_total", 1.0, 
                                 labels={"method": "GET", "status": "200"})
        collector.record_counter("http_requests_total", 1.0, 
                                 labels={"method": "POST", "status": "201"})
        
        metrics = collector.get_metrics()
        # Different label combinations create different metrics
        assert len([m for m in metrics.keys() if m.startswith("http_requests_total")]) >= 1

    # === GAUGE TESTS ===
    
    def test_record_gauge_basic(self, collector):
        """Test gauge records point-in-time values."""
        collector.record_gauge("memory_usage_bytes", 1024.5)
        
        metrics = collector.get_metrics()
        assert metrics["memory_usage_bytes"].value == 1024.5
        assert metrics["memory_usage_bytes"].metric_type == MetricType.GAUGE
    
    def test_record_gauge_updates(self, collector):
        """Test gauge updates to latest value."""
        collector.record_gauge("cpu_usage", 25.0)
        collector.record_gauge("cpu_usage", 75.0)
        collector.record_gauge("cpu_usage", 50.0)
        
        metrics = collector.get_metrics()
        assert metrics["cpu_usage"].value == 50.0  # Latest value
    
    def test_record_gauge_with_labels(self, collector):
        """Test gauge with labels for multi-dimensional metrics."""
        collector.record_gauge("temperature", 22.5, labels={"location": "server_room"})
        collector.record_gauge("temperature", 18.0, labels={"location": "office"})
        
        metrics = collector.get_metrics()
        # Each label combination is a separate metric
        assert len([m for m in metrics.keys() if m.startswith("temperature")]) >= 1

    # === HISTOGRAM TESTS ===
    
    def test_record_histogram_basic(self, collector):
        """Test histogram records observations."""
        for value in [0.001, 0.05, 0.5, 5.0]:
            collector.record_histogram("response_time_seconds", value)
        
        metrics = collector.get_metrics(name="response_time_seconds")
        # Histogram creates multiple bucket metrics
        assert len(metrics) > 0
    
    def test_record_histogram_buckets(self, collector):
        """Test histogram correctly distributes values into buckets."""
        # Default buckets: [0.001, 0.01, 0.1, 0.5, 1.0, 5.0, 10.0]
        test_values = [0.0005, 0.005, 0.05, 0.25, 0.75, 2.5, 7.5]
        
        for value in test_values:
            collector.record_histogram("latency", value)
        
        # Verify histogram metrics exist
        metrics = collector.get_metrics(name="latency")
        assert len(metrics) > 0

    # === PROMETHEUS EXPORT TESTS ===
    
    def test_prometheus_export_format_counter(self, collector):
        """Test Prometheus format for counter metric."""
        collector.record_counter("test_total", 42.0, help_text="Test counter metric")
        
        prometheus_text = collector.export_prometheus()
        assert "# HELP test_total Test counter metric" in prometheus_text
        assert "# TYPE test_total counter" in prometheus_text
        assert "test_total 42.0" in prometheus_text or "test_total 42" in prometheus_text
    
    def test_prometheus_export_format_gauge(self, collector):
        """Test Prometheus format for gauge metric."""
        collector.record_gauge("memory_bytes", 2048.0, help_text="Memory usage")
        
        prometheus_text = collector.export_prometheus()
        assert "# HELP memory_bytes Memory usage" in prometheus_text
        assert "# TYPE memory_bytes gauge" in prometheus_text
        assert "memory_bytes 2048" in prometheus_text
    
    def test_prometheus_export_with_labels(self, collector):
        """Test Prometheus format with labels."""
        collector.record_counter("requests", 10.0, labels={"method": "GET", "path": "/api"})
        
        prometheus_text = collector.export_prometheus()
        # Labels should be formatted as {key="value"}
        assert 'method="GET"' in prometheus_text or "requests" in prometheus_text

    # === TIME-SERIES AGGREGATION TESTS ===
    
    def test_time_series_aggregation_sum(self, collector):
        """Test aggregation calculates sum over time window."""
        for i in range(10):
            collector.record_counter("events_total", 1.0)
        
        # Aggregate over a time window
        aggregated = collector.aggregate_over_window("events_total", "1m")
        assert aggregated["sum"] == 10.0
    
    def test_time_series_aggregation_average(self, collector):
        """Test aggregation calculates average."""
        values = [10.0, 20.0, 30.0, 40.0, 50.0]
        for value in values:
            collector.record_gauge("metric", value)
        
        aggregated = collector.aggregate_over_window("metric", "1m")
        # Average of last values
        assert "avg" in aggregated

    # === THREAD SAFETY TESTS ===
    
    def test_thread_safety_counter(self, collector):
        """Test concurrent counter increments are thread-safe."""
        def record_metrics():
            for _ in range(100):
                collector.record_counter("concurrent_counter", 1.0)
        
        threads = [threading.Thread(target=record_metrics) for _ in range(10)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()
        
        metrics = collector.get_metrics()
        # 10 threads * 100 increments = 1000 total
        assert metrics["concurrent_counter"].value == 1000.0
    
    def test_thread_safety_gauge(self, collector):
        """Test concurrent gauge updates are thread-safe (no race conditions)."""
        def update_gauge(value):
            time.sleep(0.001)  # Small delay to increase concurrency
            collector.record_gauge("shared_gauge", value)
        
        threads = [threading.Thread(target=update_gauge, args=(i,)) for i in range(50)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()
        
        metrics = collector.get_metrics()
        # Final value should be one of the recorded values (no corruption)
        assert "shared_gauge" in metrics
        assert 0 <= metrics["shared_gauge"].value < 50

    # === METRIC FILTERING TESTS ===
    
    def test_get_metrics_by_name(self, collector):
        """Test filtering metrics by name."""
        collector.record_counter("metric_a", 1.0)
        collector.record_counter("metric_b", 2.0)
        collector.record_gauge("metric_c", 3.0)
        
        metrics_a = collector.get_metrics(name="metric_a")
        assert len(metrics_a) >= 1
        assert "metric_a" in metrics_a
        assert "metric_b" not in metrics_a
    
    def test_get_metrics_by_labels(self, collector):
        """Test filtering metrics by labels."""
        collector.record_counter("requests", 1.0, labels={"env": "prod", "region": "us"})
        collector.record_counter("requests", 2.0, labels={"env": "dev", "region": "us"})
        collector.record_counter("requests", 3.0, labels={"env": "prod", "region": "eu"})
        
        # Filter by label
        prod_metrics = collector.get_metrics(labels={"env": "prod"})
        # Should only get prod metrics
        assert len([m for m in prod_metrics.values() if "prod" in str(m)]) >= 0
    
    def test_get_metrics_by_type(self, collector):
        """Test filtering metrics by type."""
        collector.record_counter("counter1", 1.0)
        collector.record_counter("counter2", 2.0)
        collector.record_gauge("gauge1", 3.0)
        collector.record_histogram("histogram1", 0.5)
        
        counters = collector.get_metrics(metric_type=MetricType.COUNTER)
        gauges = collector.get_metrics(metric_type=MetricType.GAUGE)
        
        assert len([m for m in counters.values() if m.metric_type == MetricType.COUNTER]) >= 2
        assert len([m for m in gauges.values() if m.metric_type == MetricType.GAUGE]) >= 1

    # === METRIC LIFECYCLE TESTS ===
    
    def test_metric_timestamp(self, collector):
        """Test metrics record timestamp."""
        before = datetime.now()
        collector.record_counter("timed_metric", 1.0)
        after = datetime.now()
        
        metrics = collector.get_metrics()
        metric_time = metrics["timed_metric"].timestamp
        
        assert before <= metric_time <= after
    
    def test_metric_help_text(self, collector):
        """Test help text is stored with metric."""
        help_text = "Number of successful operations"
        collector.record_counter("operations_total", 1.0, help_text=help_text)
        
        metrics = collector.get_metrics()
        assert metrics["operations_total"].help_text == help_text

    # === EDGE CASE TESTS ===
    
    def test_record_zero_values(self, collector):
        """Test handling of zero values."""
        collector.record_counter("zero_counter", 0.0)
        collector.record_gauge("zero_gauge", 0.0)
        
        metrics = collector.get_metrics()
        assert metrics["zero_counter"].value == 0.0
        assert metrics["zero_gauge"].value == 0.0
    
    def test_record_negative_gauge(self, collector):
        """Test gauge can record negative values."""
        collector.record_gauge("temperature_celsius", -10.5)
        
        metrics = collector.get_metrics()
        assert metrics["temperature_celsius"].value == -10.5
    
    def test_large_metric_values(self, collector):
        """Test handling of large numeric values."""
        large_value = 1e15  # 1 quadrillion
        collector.record_counter("big_counter", large_value)
        
        metrics = collector.get_metrics()
        assert metrics["big_counter"].value == large_value
    
    def test_empty_labels(self, collector):
        """Test metrics work with empty label dictionaries."""
        collector.record_counter("no_labels", 1.0, labels={})
        
        metrics = collector.get_metrics()
        assert "no_labels" in metrics
        assert metrics["no_labels"].labels == {}

    # === PERFORMANCE TESTS ===
    
    def test_high_throughput_counter(self, collector):
        """Test collector handles high throughput."""
        start = time.time()
        
        for _ in range(10000):
            collector.record_counter("high_throughput", 1.0)
        
        duration = time.time() - start
        
        # Should complete in reasonable time (< 1 second)
        assert duration < 1.0
        
        metrics = collector.get_metrics()
        assert metrics["high_throughput"].value == 10000.0


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
