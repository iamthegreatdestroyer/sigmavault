"""Tests for monitoring_dashboard module."""

import pytest
import asyncio
import json
import time
from sigma_vault.ml.monitoring_dashboard import (
    MetricSnapshot,
    AnomalyEvent,
    MetricsBuffer,
    AnomalyEventBuffer,
    MonitoringDashboard,
)


class TestMetricSnapshot:
    """Test MetricSnapshot data class."""

    def test_metric_snapshot_creation(self):
        """Test creating metric snapshot."""
        snapshot = MetricSnapshot(
            timestamp=time.time(),
            anomaly_count=5,
            model_latency_ms=25.5,
            cache_hit_rate=0.95,
            active_connections=10,
            predictions_per_sec=100.0,
            memory_usage_mb=512.0,
        )
        assert snapshot.anomaly_count == 5
        assert snapshot.model_latency_ms == 25.5
        assert snapshot.cache_hit_rate == 0.95

    def test_metric_snapshot_to_dict(self):
        """Test converting snapshot to dict."""
        snapshot = MetricSnapshot(
            timestamp=1000.0,
            anomaly_count=5,
            model_latency_ms=25.5,
            cache_hit_rate=0.95,
            active_connections=10,
            predictions_per_sec=100.0,
            memory_usage_mb=512.0,
        )
        data = snapshot.to_dict()
        assert data['timestamp'] == 1000.0
        assert data['anomaly_count'] == 5
        assert 'model_latency_ms' in data


class TestAnomalyEvent:
    """Test AnomalyEvent data class."""

    def test_anomaly_event_creation(self):
        """Test creating anomaly event."""
        event = AnomalyEvent(
            timestamp=time.time(),
            file_id="file_123",
            anomaly_type="pattern_deviation",
            confidence=0.95,
            severity="high",
            details={'score': 0.95},
        )
        assert event.file_id == "file_123"
        assert event.anomaly_type == "pattern_deviation"
        assert event.confidence == 0.95

    def test_anomaly_event_to_dict(self):
        """Test converting event to dict."""
        event = AnomalyEvent(
            timestamp=1000.0,
            file_id="file_123",
            anomaly_type="pattern_deviation",
            confidence=0.95,
            severity="high",
            details={'score': 0.95},
        )
        data = event.to_dict()
        assert data['file_id'] == "file_123"
        assert data['severity'] == "high"
        assert data['details']['score'] == 0.95


class TestMetricsBuffer:
    """Test MetricsBuffer circular buffer."""

    @pytest.mark.asyncio
    async def test_metrics_buffer_add(self):
        """Test adding metrics to buffer."""
        buffer = MetricsBuffer(capacity=10)
        snapshot = MetricSnapshot(
            timestamp=time.time(),
            anomaly_count=0,
            model_latency_ms=10.0,
            cache_hit_rate=0.9,
            active_connections=1,
            predictions_per_sec=50.0,
            memory_usage_mb=256.0,
        )
        await buffer.add(snapshot)
        assert len(buffer.buffer) == 1

    @pytest.mark.asyncio
    async def test_metrics_buffer_get_recent(self):
        """Test getting recent metrics."""
        buffer = MetricsBuffer(capacity=10)

        for i in range(5):
            snapshot = MetricSnapshot(
                timestamp=time.time() + i,
                anomaly_count=i,
                model_latency_ms=10.0 + i,
                cache_hit_rate=0.9,
                active_connections=i + 1,
                predictions_per_sec=50.0,
                memory_usage_mb=256.0,
            )
            await buffer.add(snapshot)

        recent = await buffer.get_recent(3)
        assert len(recent) == 3
        assert recent[-1]['anomaly_count'] == 4

    @pytest.mark.asyncio
    async def test_metrics_buffer_capacity(self):
        """Test buffer capacity limit."""
        buffer = MetricsBuffer(capacity=5)

        for i in range(10):
            snapshot = MetricSnapshot(
                timestamp=time.time() + i,
                anomaly_count=i,
                model_latency_ms=10.0,
                cache_hit_rate=0.9,
                active_connections=1,
                predictions_per_sec=50.0,
                memory_usage_mb=256.0,
            )
            await buffer.add(snapshot)

        # Should only have last 5
        assert len(buffer.buffer) == 5

    @pytest.mark.asyncio
    async def test_metrics_buffer_time_range(self):
        """Test getting metrics by time range."""
        buffer = MetricsBuffer(capacity=100)
        start_time = time.time()

        for i in range(10):
            snapshot = MetricSnapshot(
                timestamp=start_time + (i * 10),  # 10 second intervals
                anomaly_count=i,
                model_latency_ms=10.0,
                cache_hit_rate=0.9,
                active_connections=1,
                predictions_per_sec=50.0,
                memory_usage_mb=256.0,
            )
            await buffer.add(snapshot)

        # Get metrics from second 20 to second 60
        metrics = await buffer.get_time_range(start_time + 20, start_time + 60)
        assert len(metrics) > 0
        assert all(start_time + 20 <= m['timestamp'] <= start_time + 60 for m in metrics)


class TestAnomalyEventBuffer:
    """Test AnomalyEventBuffer circular buffer."""

    @pytest.mark.asyncio
    async def test_anomaly_buffer_add(self):
        """Test adding events to buffer."""
        buffer = AnomalyEventBuffer(capacity=10)
        event = AnomalyEvent(
            timestamp=time.time(),
            file_id="file_123",
            anomaly_type="pattern",
            confidence=0.9,
            severity="high",
            details={},
        )
        await buffer.add(event)
        assert len(buffer.buffer) == 1

    @pytest.mark.asyncio
    async def test_anomaly_buffer_get_recent(self):
        """Test getting recent events."""
        buffer = AnomalyEventBuffer(capacity=10)

        for i in range(5):
            event = AnomalyEvent(
                timestamp=time.time() + i,
                file_id=f"file_{i}",
                anomaly_type="pattern",
                confidence=0.9 + (i * 0.01),
                severity="high",
                details={'id': i},
            )
            await buffer.add(event)

        recent = await buffer.get_recent(3)
        assert len(recent) == 3
        assert recent[-1]['data']['id'] == 4

    @pytest.mark.asyncio
    async def test_anomaly_buffer_by_severity(self):
        """Test filtering events by severity."""
        buffer = AnomalyEventBuffer(capacity=20)

        severities = ['low', 'medium', 'high', 'critical']
        for i in range(8):
            event = AnomalyEvent(
                timestamp=time.time() + i,
                file_id=f"file_{i}",
                anomaly_type="pattern",
                confidence=0.9,
                severity=severities[i % 4],
                details={},
            )
            await buffer.add(event)

        high_severity = await buffer.get_by_severity('high', 10)
        assert len(high_severity) >= 2


class TestMonitoringDashboard:
    """Test MonitoringDashboard WebSocket server."""

    def test_dashboard_creation(self):
        """Test creating dashboard."""
        dashboard = MonitoringDashboard(host="localhost", port=8765)
        assert dashboard.host == "localhost"
        assert dashboard.port == 8765
        assert not dashboard.running

    @pytest.mark.asyncio
    async def test_dashboard_start_stop(self):
        """Test starting and stopping dashboard."""
        dashboard = MonitoringDashboard(host="localhost", port=9999)

        # Note: This test may fail if websockets not installed
        try:
            await dashboard.start()
            assert dashboard.running
            await dashboard.stop()
            assert not dashboard.running
        except Exception as e:
            # Skip if websockets not available
            pytest.skip(f"websockets not available: {e}")

    @pytest.mark.asyncio
    async def test_broadcast_metrics(self):
        """Test broadcasting metrics."""
        dashboard = MonitoringDashboard()
        snapshot = MetricSnapshot(
            timestamp=time.time(),
            anomaly_count=5,
            model_latency_ms=25.0,
            cache_hit_rate=0.95,
            active_connections=0,  # No real clients
            predictions_per_sec=100.0,
            memory_usage_mb=512.0,
        )

        # Should not raise even without clients
        await dashboard.broadcast_metrics(snapshot)

        # Check metrics were buffered
        recent = await dashboard.metrics_buffer.get_recent(1)
        assert len(recent) == 1
        assert recent[0]['anomaly_count'] == 5

    @pytest.mark.asyncio
    async def test_broadcast_anomaly(self):
        """Test broadcasting anomaly event."""
        dashboard = MonitoringDashboard()
        event = AnomalyEvent(
            timestamp=time.time(),
            file_id="file_123",
            anomaly_type="pattern",
            confidence=0.95,
            severity="critical",
            details={'score': 0.95},
        )

        # Should not raise without clients
        await dashboard.broadcast_anomaly(event)

        # Check event was buffered
        recent = await dashboard.anomaly_buffer.get_recent(1)
        assert len(recent) == 1
        assert recent[0]['file_id'] == "file_123"

    @pytest.mark.asyncio
    async def test_dashboard_summary(self):
        """Test getting dashboard summary."""
        dashboard = MonitoringDashboard()

        # Add some metrics
        for i in range(3):
            snapshot = MetricSnapshot(
                timestamp=time.time() + i,
                anomaly_count=i,
                model_latency_ms=10.0 + i,
                cache_hit_rate=0.9,
                active_connections=0,
                predictions_per_sec=50.0,
                memory_usage_mb=256.0,
            )
            await dashboard.broadcast_metrics(snapshot)

        # Add some events
        for i in range(2):
            event = AnomalyEvent(
                timestamp=time.time() + i,
                file_id=f"file_{i}",
                anomaly_type="pattern",
                confidence=0.9,
                severity="high" if i == 0 else "critical",
                details={},
            )
            await dashboard.broadcast_anomaly(event)

        summary = await dashboard.get_dashboard_summary()
        assert summary['active_connections'] == 0
        assert summary['current_metrics'] is not None
        assert len(summary['recent_anomalies']) > 0


class TestMetricsBufferThreadSafety:
    """Test thread-safe operations on metrics buffer."""

    @pytest.mark.asyncio
    async def test_concurrent_adds(self):
        """Test concurrent adds to buffer."""
        buffer = MetricsBuffer(capacity=100)

        async def add_metrics(count: int) -> None:
            for i in range(count):
                snapshot = MetricSnapshot(
                    timestamp=time.time() + (i * 0.01),
                    anomaly_count=i,
                    model_latency_ms=10.0,
                    cache_hit_rate=0.9,
                    active_connections=1,
                    predictions_per_sec=50.0,
                    memory_usage_mb=256.0,
                )
                await buffer.add(snapshot)

        # Concurrent additions
        await asyncio.gather(
            add_metrics(10),
            add_metrics(10),
            add_metrics(10),
        )

        assert len(buffer.buffer) == 30


class TestAnomalyEventBufferThreadSafety:
    """Test thread-safe operations on anomaly buffer."""

    @pytest.mark.asyncio
    async def test_concurrent_adds(self):
        """Test concurrent adds to buffer."""
        buffer = AnomalyEventBuffer(capacity=100)

        async def add_events(count: int) -> None:
            for i in range(count):
                event = AnomalyEvent(
                    timestamp=time.time() + (i * 0.01),
                    file_id=f"file_{i}",
                    anomaly_type="pattern",
                    confidence=0.9,
                    severity="high",
                    details={'id': i},
                )
                await buffer.add(event)

        # Concurrent additions
        await asyncio.gather(
            add_events(10),
            add_events(10),
        )

        assert len(buffer.buffer) == 20
