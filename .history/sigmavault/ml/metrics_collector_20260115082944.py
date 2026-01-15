"""
Prometheus-compatible metrics collection for ML pipeline monitoring.

Collects and aggregates time-series metrics from all ML components:
- Anomaly detection performance
- Cache hit rates
- Model inference latency
- Feature extraction statistics
- Alert frequency and severity

Exports metrics in Prometheus format for visualization.
"""

from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from pathlib import Path
from typing import Dict, List, Optional, Tuple, Any
import json
import threading
import time


class MetricType(Enum):
    """Types of metrics collected."""
    COUNTER = "counter"  # Monotonically increasing
    GAUGE = "gauge"      # Can go up or down
    HISTOGRAM = "histogram"  # Distribution of values
    SUMMARY = "summary"  # Percentiles over sliding window


@dataclass
class Metric:
    """
    Individual metric with metadata.
    
    Attributes:
        name: Metric identifier (e.g., 'anomaly_detections_total')
        type: Type of metric (counter, gauge, histogram, summary)
        value: Current metric value
        labels: Key-value pairs for metric dimensions
        timestamp: When metric was recorded
        help_text: Human-readable description
    """
    name: str
    type: MetricType
    value: float
    labels: Dict[str, str] = field(default_factory=dict)
    timestamp: datetime = field(default_factory=datetime.now)
    help_text: str = ""


@dataclass
class HistogramBucket:
    """Histogram bucket for distribution tracking."""
    le: float  # Less than or equal to this value
    count: int = 0


class TimeSeriesBuffer:
    """
    Thread-safe time-series data buffer with automatic expiration.
    
    Maintains sliding window of metric values for aggregation.
    """
    
    def __init__(self, window_seconds: int = 300, max_size: int = 10000):
        """
        Initialize time-series buffer.
        
        Args:
            window_seconds: Sliding window duration (default: 5 minutes)
            max_size: Maximum buffer size before eviction
        """
        self.window = timedelta(seconds=window_seconds)
        self.max_size = max_size
        self.data: List[Tuple[datetime, float]] = []
        self.lock = threading.Lock()
    
    def add(self, value: float, timestamp: Optional[datetime] = None):
        """
        Add value to buffer with automatic expiration.
        
        Args:
            value: Metric value to add
            timestamp: Optional timestamp (default: now)
        """
        if timestamp is None:
            timestamp = datetime.now()
        
        with self.lock:
            self.data.append((timestamp, value))
            
            # Evict expired data
            cutoff = datetime.now() - self.window
            self.data = [(ts, val) for ts, val in self.data if ts > cutoff]
            
            # Enforce max size (evict oldest)
            if len(self.data) > self.max_size:
                self.data = self.data[-self.max_size:]
    
    def get_stats(self) -> Dict[str, float]:
        """
        Calculate statistics over sliding window.
        
        Returns:
            Dictionary with count, sum, mean, min, max, p50, p95, p99
        """
        with self.lock:
            if not self.data:
                return {
                    'count': 0, 'sum': 0.0, 'mean': 0.0,
                    'min': 0.0, 'max': 0.0,
                    'p50': 0.0, 'p95': 0.0, 'p99': 0.0
                }
            
            values = [val for _, val in self.data]
            values_sorted = sorted(values)
            count = len(values)
            
            return {
                'count': count,
                'sum': sum(values),
                'mean': sum(values) / count,
                'min': min(values),
                'max': max(values),
                'p50': self._percentile(values_sorted, 50),
                'p95': self._percentile(values_sorted, 95),
                'p99': self._percentile(values_sorted, 99)
            }
    
    def _percentile(self, sorted_values: List[float], percentile: int) -> float:
        """Calculate percentile from sorted values."""
        if not sorted_values:
            return 0.0
        idx = int(len(sorted_values) * percentile / 100)
        return sorted_values[min(idx, len(sorted_values) - 1)]


class MetricsCollector:
    """
    Central metrics collection and aggregation system.
    
    Provides thread-safe metric registration, updates, and export
    in Prometheus format. Supports all metric types with automatic
    time-series aggregation.
    
    Example:
        >>> collector = MetricsCollector()
        >>> collector.counter('anomalies_detected', 1, labels={'severity': 'high'})
        >>> collector.gauge('cache_hit_rate', 0.87)
        >>> collector.histogram('inference_latency_ms', 12.5)
        >>> metrics = collector.export_prometheus()
    """
    
    def __init__(self, window_seconds: int = 300):
        """
        Initialize metrics collector.
        
        Args:
            window_seconds: Sliding window for aggregations (default: 5 min)
        """
        self.window_seconds = window_seconds
        self.counters: Dict[str, float] = {}
        self.gauges: Dict[str, float] = {}
        self.histograms: Dict[str, TimeSeriesBuffer] = {}
        self.summaries: Dict[str, TimeSeriesBuffer] = {}
        self.metric_metadata: Dict[str, Tuple[MetricType, str]] = {}
        self.lock = threading.Lock()
        
        # Initialize standard ML metrics
        self._init_standard_metrics()
    
    def _init_standard_metrics(self):
        """Initialize standard ML pipeline metrics."""
        # Anomaly detection metrics
        self.register_counter(
            'anomaly_detections_total',
            'Total number of anomaly detections'
        )
        self.register_counter(
            'anomaly_alerts_total',
            'Total number of anomaly alerts triggered'
        )
        self.register_histogram(
            'anomaly_detection_latency_ms',
            'Anomaly detection latency in milliseconds'
        )
        self.register_gauge(
            'anomaly_detection_score',
            'Current anomaly detection score (-1 to 1)'
        )
        
        # Cache metrics
        self.register_counter(
            'cache_hits_total',
            'Total number of cache hits'
        )
        self.register_counter(
            'cache_misses_total',
            'Total number of cache misses'
        )
        self.register_gauge(
            'cache_hit_rate',
            'Current cache hit rate (0 to 1)'
        )
        
        # Model performance metrics
        self.register_histogram(
            'model_inference_latency_ms',
            'Model inference latency in milliseconds'
        )
        self.register_gauge(
            'model_accuracy',
            'Current model accuracy (0 to 1)'
        )
        self.register_counter(
            'model_updates_total',
            'Total number of model updates'
        )
        
        # Feature extraction metrics
        self.register_histogram(
            'feature_extraction_latency_ms',
            'Feature extraction latency in milliseconds'
        )
        self.register_gauge(
            'feature_vector_size',
            'Size of feature vector'
        )
        
        # System health metrics
        self.register_gauge(
            'ml_pipeline_healthy',
            'ML pipeline health status (1=healthy, 0=unhealthy)'
        )
        self.register_counter(
            'ml_pipeline_errors_total',
            'Total number of ML pipeline errors'
        )
    
    def register_counter(self, name: str, help_text: str):
        """Register a counter metric."""
        with self.lock:
            self.counters[name] = 0.0
            self.metric_metadata[name] = (MetricType.COUNTER, help_text)
    
    def register_gauge(self, name: str, help_text: str):
        """Register a gauge metric."""
        with self.lock:
            self.gauges[name] = 0.0
            self.metric_metadata[name] = (MetricType.GAUGE, help_text)
    
    def register_histogram(self, name: str, help_text: str):
        """Register a histogram metric."""
        with self.lock:
            self.histograms[name] = TimeSeriesBuffer(self.window_seconds)
            self.metric_metadata[name] = (MetricType.HISTOGRAM, help_text)
    
    def register_summary(self, name: str, help_text: str):
        """Register a summary metric."""
        with self.lock:
            self.summaries[name] = TimeSeriesBuffer(self.window_seconds)
            self.metric_metadata[name] = (MetricType.SUMMARY, help_text)
    
    def record_counter(self, name: str, value: float = 1.0, labels: Optional[Dict[str, str]] = None):
        """
        Increment counter metric.
        
        Args:
            name: Metric name
            value: Amount to increment (default: 1)
            labels: Optional metric labels
        """
        with self.lock:
            if name not in self.counters:
                self.register_counter(name, f"Counter: {name}")
            self.counters[name] += value
    
    def gauge(self, name: str, value: float, labels: Optional[Dict[str, str]] = None):
        """
        Set gauge metric value.
        
        Args:
            name: Metric name
            value: New gauge value
            labels: Optional metric labels
        """
        with self.lock:
            if name not in self.gauges:
                self.register_gauge(name, f"Gauge: {name}")
            self.gauges[name] = value
    
    def histogram(self, name: str, value: float, labels: Optional[Dict[str, str]] = None):
        """
        Observe value in histogram.
        
        Args:
            name: Metric name
            value: Observed value
            labels: Optional metric labels
        """
        with self.lock:
            if name not in self.histograms:
                self.register_histogram(name, f"Histogram: {name}")
            self.histograms[name].add(value)
    
    def summary(self, name: str, value: float, labels: Optional[Dict[str, str]] = None):
        """
        Observe value in summary.
        
        Args:
            name: Metric name
            value: Observed value
            labels: Optional metric labels
        """
        with self.lock:
            if name not in self.summaries:
                self.register_summary(name, f"Summary: {name}")
            self.summaries[name].add(value)
    
    def get_metric(self, name: str) -> Optional[float]:
        """
        Get current value of a counter or gauge.
        
        Args:
            name: Metric name
            
        Returns:
            Current metric value or None if not found
        """
        with self.lock:
            if name in self.counters:
                return self.counters[name]
            elif name in self.gauges:
                return self.gauges[name]
            return None
    
    def get_histogram_stats(self, name: str) -> Dict[str, float]:
        """
        Get statistics for histogram metric.
        
        Args:
            name: Metric name
            
        Returns:
            Dictionary with statistical summary
        """
        with self.lock:
            if name in self.histograms:
                return self.histograms[name].get_stats()
            return {}
    
    def export_prometheus(self) -> str:
        """
        Export all metrics in Prometheus text format.
        
        Returns:
            Prometheus-formatted metric string
        """
        lines = []
        
        with self.lock:
            # Export counters
            for name, value in self.counters.items():
                metric_type, help_text = self.metric_metadata.get(
                    name, (MetricType.COUNTER, "")
                )
                lines.append(f"# HELP {name} {help_text}")
                lines.append(f"# TYPE {name} counter")
                lines.append(f"{name} {value}")
                lines.append("")
            
            # Export gauges
            for name, value in self.gauges.items():
                metric_type, help_text = self.metric_metadata.get(
                    name, (MetricType.GAUGE, "")
                )
                lines.append(f"# HELP {name} {help_text}")
                lines.append(f"# TYPE {name} gauge")
                lines.append(f"{name} {value}")
                lines.append("")
            
            # Export histograms
            for name, buffer in self.histograms.items():
                metric_type, help_text = self.metric_metadata.get(
                    name, (MetricType.HISTOGRAM, "")
                )
                stats = buffer.get_stats()
                
                lines.append(f"# HELP {name} {help_text}")
                lines.append(f"# TYPE {name} histogram")
                lines.append(f"{name}_count {stats['count']}")
                lines.append(f"{name}_sum {stats['sum']}")
                
                # Add quantiles
                for quantile, key in [(0.5, 'p50'), (0.95, 'p95'), (0.99, 'p99')]:
                    lines.append(f'{name}{{quantile="{quantile}"}} {stats[key]}')
                lines.append("")
            
            # Export summaries
            for name, buffer in self.summaries.items():
                metric_type, help_text = self.metric_metadata.get(
                    name, (MetricType.SUMMARY, "")
                )
                stats = buffer.get_stats()
                
                lines.append(f"# HELP {name} {help_text}")
                lines.append(f"# TYPE {name} summary")
                lines.append(f"{name}_count {stats['count']}")
                lines.append(f"{name}_sum {stats['sum']}")
                
                # Add quantiles
                for quantile, key in [(0.5, 'p50'), (0.95, 'p95'), (0.99, 'p99')]:
                    lines.append(f'{name}{{quantile="{quantile}"}} {stats[key]}')
                lines.append("")
        
        return "\n".join(lines)
    
    def export_json(self) -> Dict[str, Any]:
        """
        Export all metrics as JSON.
        
        Returns:
            Dictionary with all metric values and statistics
        """
        with self.lock:
            result = {
                'timestamp': datetime.now().isoformat(),
                'counters': dict(self.counters),
                'gauges': dict(self.gauges),
                'histograms': {
                    name: buffer.get_stats()
                    for name, buffer in self.histograms.items()
                },
                'summaries': {
                    name: buffer.get_stats()
                    for name, buffer in self.summaries.items()
                }
            }
            return result
    
    def reset(self):
        """Reset all metrics to initial state."""
        with self.lock:
            for name in self.counters:
                self.counters[name] = 0.0
            for name in self.gauges:
                self.gauges[name] = 0.0
            for name in self.histograms:
                self.histograms[name] = TimeSeriesBuffer(self.window_seconds)
            for name in self.summaries:
                self.summaries[name] = TimeSeriesBuffer(self.window_seconds)


# Global singleton metrics collector
_global_metrics_collector: Optional[MetricsCollector] = None


def get_metrics_collector() -> MetricsCollector:
    """
    Get global metrics collector singleton.
    
    Returns:
        Global MetricsCollector instance
    """
    global _global_metrics_collector
    if _global_metrics_collector is None:
        _global_metrics_collector = MetricsCollector()
    return _global_metrics_collector
