"""Tests for alert_manager module."""

import pytest
import time
from sigma_vault.ml.alert_manager import (
    AlertSeverity,
    AlertChannel,
    AlertThreshold,
    SuppressionRule,
    Alert,
    AlertAggregator,
    AlertManager,
)


class TestAlertSeverity:
    """Test AlertSeverity enum."""

    def test_severity_levels(self):
        """Test severity level values."""
        assert AlertSeverity.INFO.value == 1
        assert AlertSeverity.WARNING.value == 2
        assert AlertSeverity.CRITICAL.value == 3

    def test_severity_comparison(self):
        """Test severity comparison."""
        assert AlertSeverity.CRITICAL.value > AlertSeverity.WARNING.value


class TestAlertChannel:
    """Test AlertChannel enum."""

    def test_channel_values(self):
        """Test channel values."""
        assert AlertChannel.LOG.value == "log"
        assert AlertChannel.WEBHOOK.value == "webhook"
        assert AlertChannel.EMAIL.value == "email"
        assert AlertChannel.SLACK.value == "slack"


class TestAlertThreshold:
    """Test AlertThreshold configuration."""

    def test_threshold_creation(self):
        """Test creating threshold."""
        threshold = AlertThreshold(
            metric_name="cpu_usage",
            threshold_value=80.0,
            operator=">",
            severity=AlertSeverity.CRITICAL,
            description="High CPU usage alert"
        )
        assert threshold.metric_name == "cpu_usage"
        assert threshold.threshold_value == 80.0

    def test_threshold_check_greater_than(self):
        """Test threshold check with > operator."""
        threshold = AlertThreshold(
            metric_name="cpu",
            threshold_value=80.0,
            operator=">",
            severity=AlertSeverity.CRITICAL,
        )
        assert threshold.check(85.0) is True
        assert threshold.check(75.0) is False

    def test_threshold_check_less_than(self):
        """Test threshold check with < operator."""
        threshold = AlertThreshold(
            metric_name="memory",
            threshold_value=10.0,
            operator="<",
            severity=AlertSeverity.WARNING,
        )
        assert threshold.check(5.0) is True
        assert threshold.check(15.0) is False

    def test_threshold_check_equal(self):
        """Test threshold check with == operator."""
        threshold = AlertThreshold(
            metric_name="status",
            threshold_value=0.0,
            operator="==",
            severity=AlertSeverity.CRITICAL,
        )
        assert threshold.check(0.0) is True
        assert threshold.check(1.0) is False

    def test_threshold_check_not_equal(self):
        """Test threshold check with != operator."""
        threshold = AlertThreshold(
            metric_name="status",
            threshold_value=0.0,
            operator="!=",
            severity=AlertSeverity.WARNING,
        )
        assert threshold.check(1.0) is True
        assert threshold.check(0.0) is False

    def test_threshold_disabled(self):
        """Test disabled threshold."""
        threshold = AlertThreshold(
            metric_name="cpu",
            threshold_value=80.0,
            operator=">",
            severity=AlertSeverity.CRITICAL,
            enabled=False,
        )
        # Disabled thresholds shouldn't match
        assert threshold.enabled is False


class TestSuppressionRule:
    """Test SuppressionRule."""

    def test_suppression_rule_creation(self):
        """Test creating suppression rule."""
        rule = SuppressionRule(
            name="test_rule",
            condition=lambda x: x.get('severity') == 'INFO',
            enabled=True,
        )
        assert rule.name == "test_rule"
        assert rule.enabled is True

    def test_suppression_rule_check(self):
        """Test suppression rule evaluation."""
        rule = SuppressionRule(
            name="info_suppression",
            condition=lambda x: x.get('severity') == 'INFO',
        )

        assert rule.should_suppress({'severity': 'INFO'}) is True
        assert rule.should_suppress({'severity': 'CRITICAL'}) is False

    def test_suppression_rule_disabled(self):
        """Test disabled suppression rule."""
        rule = SuppressionRule(
            name="test_rule",
            condition=lambda x: True,
            enabled=False,
        )
        assert rule.should_suppress({}) is False


class TestAlert:
    """Test Alert data class."""

    def test_alert_creation(self):
        """Test creating alert."""
        alert = Alert(
            id="alert_123",
            timestamp=time.time(),
            severity=AlertSeverity.CRITICAL,
            title="High CPU Usage",
            message="CPU usage exceeded threshold",
            source="system",
        )
        assert alert.id == "alert_123"
        assert alert.severity == AlertSeverity.CRITICAL
        assert alert.resolved is False

    def test_alert_to_dict(self):
        """Test converting alert to dict."""
        alert = Alert(
            id="alert_123",
            timestamp=1000.0,
            severity=AlertSeverity.WARNING,
            title="Test Alert",
            message="This is a test",
            source="test",
        )
        data = alert.to_dict()
        assert data['id'] == "alert_123"
        assert data['severity'] == "WARNING"
        assert data['resolved'] is False

    def test_alert_resolution(self):
        """Test alert resolution."""
        alert = Alert(
            id="alert_123",
            timestamp=time.time(),
            severity=AlertSeverity.CRITICAL,
            title="Test",
            message="Test alert",
            source="test",
        )
        assert alert.resolved is False

        alert.resolved = True
        alert.resolution_time = time.time()
        assert alert.resolved is True
        assert alert.resolution_time is not None


class TestAlertAggregator:
    """Test AlertAggregator for alert grouping."""

    def test_aggregator_creation(self):
        """Test creating aggregator."""
        agg = AlertAggregator(time_window_sec=60, group_threshold=5)
        assert agg.time_window == 60
        assert agg.group_threshold == 5

    def test_aggregator_add_alert(self):
        """Test adding alerts to aggregator."""
        agg = AlertAggregator(group_threshold=3)

        for i in range(3):
            alert = Alert(
                id=f"alert_{i}",
                timestamp=time.time(),
                severity=AlertSeverity.WARNING,
                title="Test Alert",
                message=f"Alert {i}",
                source="test",
            )
            agg.add_alert("test_key", alert)

        assert len(agg.alert_groups["test_key"]) == 3

    def test_aggregator_should_aggregate(self):
        """Test aggregation threshold."""
        agg = AlertAggregator(group_threshold=3)

        assert agg.should_aggregate("key_1") is False

        for i in range(3):
            alert = Alert(
                id=f"alert_{i}",
                timestamp=time.time() + i,
                severity=AlertSeverity.WARNING,
                title="Test",
                message="Test",
                source="test",
            )
            agg.add_alert("key_1", alert)

        assert agg.should_aggregate("key_1") is True

    def test_aggregator_get_message(self):
        """Test aggregated message generation."""
        agg = AlertAggregator()

        for i in range(2):
            alert = Alert(
                id=f"alert_{i}",
                timestamp=time.time() + i,
                severity=AlertSeverity.WARNING,
                title="Test",
                message="Test",
                source="test",
            )
            agg.add_alert("test_key", alert)

        msg = agg.get_aggregated_message("test_key")
        assert "Aggregated Alert" in msg
        assert "2 similar events" in msg

    def test_aggregator_clear(self):
        """Test clearing alert group."""
        agg = AlertAggregator()

        alert = Alert(
            id="alert_1",
            timestamp=time.time(),
            severity=AlertSeverity.WARNING,
            title="Test",
            message="Test",
            source="test",
        )
        agg.add_alert("test_key", alert)
        assert len(agg.alert_groups["test_key"]) == 1

        agg.clear_group("test_key")
        assert len(agg.alert_groups["test_key"]) == 0


class TestAlertManager:
    """Test AlertManager central management."""

    def test_alert_manager_creation(self):
        """Test creating alert manager."""
        manager = AlertManager()
        assert len(manager.thresholds) == 0
        assert len(manager.suppression_rules) == 0
        assert len(manager.alerts) == 0

    def test_add_threshold(self):
        """Test adding threshold."""
        manager = AlertManager()
        threshold = AlertThreshold(
            metric_name="cpu",
            threshold_value=80.0,
            operator=">",
            severity=AlertSeverity.CRITICAL,
        )
        manager.add_threshold(threshold)
        assert "cpu" in manager.thresholds

    def test_check_metric_no_alert(self):
        """Test metric check without threshold."""
        manager = AlertManager()
        alert = manager.check_metric("unknown_metric", 50.0)
        assert alert is None

    def test_check_metric_with_alert(self):
        """Test metric check that triggers alert."""
        manager = AlertManager()
        threshold = AlertThreshold(
            metric_name="cpu",
            threshold_value=80.0,
            operator=">",
            severity=AlertSeverity.CRITICAL,
        )
        manager.add_threshold(threshold)

        alert = manager.check_metric("cpu", 85.0)
        assert alert is not None
        assert alert.severity == AlertSeverity.CRITICAL

    def test_check_metric_no_trigger(self):
        """Test metric check below threshold."""
        manager = AlertManager()
        threshold = AlertThreshold(
            metric_name="cpu",
            threshold_value=80.0,
            operator=">",
            severity=AlertSeverity.CRITICAL,
        )
        manager.add_threshold(threshold)

        alert = manager.check_metric("cpu", 50.0)
        assert alert is None

    def test_process_alert(self):
        """Test processing alert."""
        manager = AlertManager()

        alert = Alert(
            id="test_alert",
            timestamp=time.time(),
            severity=AlertSeverity.CRITICAL,
            title="Test Alert",
            message="This is a test",
            source="test",
            channels=[AlertChannel.MEMORY],
        )

        result = manager.process_alert(alert)
        assert result is True
        assert "test_alert" in manager.alerts

    def test_suppression_rule(self):
        """Test alert suppression."""
        manager = AlertManager()

        rule = SuppressionRule(
            name="test_suppression",
            condition=lambda x: AlertSeverity[x.get('severity')].value < AlertSeverity.CRITICAL.value,
        )
        manager.add_suppression_rule(rule)

        # Create warning alert (should be suppressed)
        alert = Alert(
            id="test_alert",
            timestamp=time.time(),
            severity=AlertSeverity.WARNING,
            title="Test",
            message="Test",
            source="test",
            channels=[AlertChannel.MEMORY],
        )

        result = manager.process_alert(alert)
        # Should be suppressed
        assert "test_alert" not in manager.alerts

    def test_resolve_alert(self):
        """Test resolving alert."""
        manager = AlertManager()

        alert = Alert(
            id="test_alert",
            timestamp=time.time(),
            severity=AlertSeverity.CRITICAL,
            title="Test",
            message="Test",
            source="test",
            channels=[AlertChannel.MEMORY],
        )

        manager.process_alert(alert)
        assert manager.alerts["test_alert"].resolved is False

        manager.resolve_alert("test_alert")
        assert manager.alerts["test_alert"].resolved is True
        assert manager.alerts["test_alert"].resolution_time is not None

    def test_get_active_alerts(self):
        """Test getting active alerts."""
        manager = AlertManager()

        # Add unresolved alerts
        for i in range(3):
            alert = Alert(
                id=f"alert_{i}",
                timestamp=time.time(),
                severity=AlertSeverity.CRITICAL if i == 0 else AlertSeverity.WARNING,
                title=f"Alert {i}",
                message="Test",
                source="test",
                channels=[AlertChannel.MEMORY],
            )
            manager.process_alert(alert)

        # Get all active
        active = manager.get_active_alerts()
        assert len(active) == 3

        # Get critical only
        critical = manager.get_active_alerts(AlertSeverity.CRITICAL)
        assert len(critical) == 1

    def test_get_stats(self):
        """Test getting manager statistics."""
        manager = AlertManager()

        # Add alerts
        alert = Alert(
            id="test_alert",
            timestamp=time.time(),
            severity=AlertSeverity.CRITICAL,
            title="Test",
            message="Test",
            source="test",
            channels=[AlertChannel.MEMORY],
        )
        manager.process_alert(alert)

        stats = manager.get_stats()
        assert stats['total_alerts'] >= 1
        assert stats['active_alerts'] >= 1
        assert 'CRITICAL' in stats['by_severity']

    def test_clear_resolved_alerts(self):
        """Test clearing old resolved alerts."""
        manager = AlertManager()

        # Add alert and resolve it
        alert = Alert(
            id="test_alert",
            timestamp=time.time() - 86400,  # 1 day ago
            severity=AlertSeverity.WARNING,
            title="Old Alert",
            message="Test",
            source="test",
        )
        manager.alerts["test_alert"] = alert
        manager.resolve_alert("test_alert")

        # Clear old alerts
        cleared = manager.clear_resolved_alerts(older_than_hours=1)
        assert cleared >= 1

    def test_update_threshold(self):
        """Test updating threshold."""
        manager = AlertManager()

        threshold = AlertThreshold(
            metric_name="cpu",
            threshold_value=80.0,
            operator=">",
            severity=AlertSeverity.CRITICAL,
        )
        manager.add_threshold(threshold)

        manager.update_threshold("cpu", 90.0, AlertSeverity.WARNING)
        assert manager.thresholds["cpu"].threshold_value == 90.0
        assert manager.thresholds["cpu"].severity == AlertSeverity.WARNING


class TestAlertManagerMemoryChannel:
    """Test memory channel for alert storage."""

    def test_memory_channel_storage(self):
        """Test alerts stored in memory."""
        manager = AlertManager()

        alert = Alert(
            id="test_alert",
            timestamp=time.time(),
            severity=AlertSeverity.CRITICAL,
            title="Test",
            message="Test message",
            source="test",
            channels=[AlertChannel.MEMORY],
        )

        manager.process_alert(alert)
        assert len(manager.memory_alerts) >= 1
        assert manager.memory_alerts[-1]['id'] == "test_alert"

    def test_memory_channel_capacity(self):
        """Test memory capacity limit."""
        manager = AlertManager()
        manager.max_memory_alerts = 10

        for i in range(20):
            alert = Alert(
                id=f"alert_{i}",
                timestamp=time.time(),
                severity=AlertSeverity.WARNING,
                title="Test",
                message="Test",
                source="test",
                channels=[AlertChannel.MEMORY],
            )
            manager.process_alert(alert)

        # Should not exceed max
        assert len(manager.memory_alerts) <= 10
