"""
Alert Management System for ΣVAULT ML Integration.

Handles alert configuration, threshold management, event aggregation,
suppression rules, and multi-channel notification dispatch with
automatic escalation and deduplication.
"""

import asyncio
import time
from typing import Dict, List, Optional, Any, Set, Callable
from dataclasses import dataclass, field
from enum import Enum
from collections import defaultdict
import logging
from datetime import datetime, timedelta

logger = logging.getLogger(__name__)


class AlertSeverity(Enum):
    """Alert severity levels."""
    INFO = 1
    WARNING = 2
    CRITICAL = 3


class AlertChannel(Enum):
    """Alert notification channels."""
    LOG = "log"
    WEBHOOK = "webhook"
    EMAIL = "email"
    SLACK = "slack"
    MEMORY = "memory"  # For testing


@dataclass
class AlertThreshold:
    """Configuration for alert threshold."""
    metric_name: str
    threshold_value: float
    operator: str  # '>', '<', '==', '!='
    severity: AlertSeverity
    enabled: bool = True
    description: str = ""

    def check(self, value: float) -> bool:
        """Check if value triggers alert."""
        if self.operator == '>':
            return value > self.threshold_value
        elif self.operator == '<':
            return value < self.threshold_value
        elif self.operator == '==':
            return abs(value - self.threshold_value) < 0.0001
        elif self.operator == '!=':
            return abs(value - self.threshold_value) > 0.0001
        return False


@dataclass
class SuppressionRule:
    """Suppression rule to prevent alert spam."""
    name: str
    condition: Callable[[Dict[str, Any]], bool]
    enabled: bool = True
    duration_seconds: int = 3600  # Duration rule applies

    def should_suppress(self, alert_data: Dict[str, Any]) -> bool:
        """Check if alert should be suppressed."""
        if not self.enabled:
            return False
        return self.condition(alert_data)


@dataclass
class Alert:
    """Individual alert instance."""
    id: str
    timestamp: float
    severity: AlertSeverity
    title: str
    message: str
    source: str
    data: Dict[str, Any] = field(default_factory=dict)
    channels: List[AlertChannel] = field(default_factory=list)
    resolved: bool = False
    resolution_time: Optional[float] = None

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dict for serialization."""
        return {
            'id': self.id,
            'timestamp': self.timestamp,
            'severity': self.severity.name,
            'title': self.title,
            'message': self.message,
            'source': self.source,
            'data': self.data,
            'channels': [c.value for c in self.channels],
            'resolved': self.resolved,
            'resolution_time': self.resolution_time,
        }


class AlertAggregator:
    """Aggregates similar alerts to prevent overwhelming notifications."""

    def __init__(self, time_window_sec: int = 60, group_threshold: int = 5):
        self.time_window = time_window_sec
        self.group_threshold = group_threshold
        self.alert_groups: Dict[str, List[Alert]] = defaultdict(list)
        self.last_aggregation: Dict[str, float] = {}

    def should_aggregate(self, alert_key: str) -> bool:
        """Check if alert should be aggregated."""
        now = time.time()
        alerts = self.alert_groups[alert_key]

        # Remove old alerts outside time window
        self.alert_groups[alert_key] = [
            a for a in alerts
            if now - a.timestamp < self.time_window
        ]

        return len(self.alert_groups[alert_key]) >= self.group_threshold

    def add_alert(self, alert_key: str, alert: Alert) -> None:
        """Add alert to aggregation group."""
        self.alert_groups[alert_key].append(alert)
        self.last_aggregation[alert_key] = time.time()

    def get_aggregated_message(self, alert_key: str) -> str:
        """Generate aggregated message for alert group."""
        alerts = self.alert_groups[alert_key]
        count = len(alerts)
        first_time = alerts[0].timestamp
        last_time = alerts[-1].timestamp
        duration = last_time - first_time

        return (
            f"Aggregated Alert: {count} similar events in "
            f"{duration:.1f} seconds (first: {datetime.fromtimestamp(first_time)})"
        )

    def clear_group(self, alert_key: str) -> None:
        """Clear alert group."""
        self.alert_groups[alert_key] = []
        self.last_aggregation.pop(alert_key, None)


class AlertManager:
    """
    Centralized alert management system for ML integration.

    Manages thresholds, suppression rules, aggregation, and multi-channel
    notification delivery with automatic deduplication and escalation.
    """

    def __init__(self):
        self.thresholds: Dict[str, AlertThreshold] = {}
        self.suppression_rules: Dict[str, SuppressionRule] = {}
        self.alerts: Dict[str, Alert] = {}  # id -> Alert
        self.aggregator = AlertAggregator()

        # Notification handlers
        self.handlers: Dict[AlertChannel, Callable] = {
            AlertChannel.LOG: self._handle_log,
            AlertChannel.MEMORY: self._handle_memory,
            AlertChannel.WEBHOOK: self._handle_webhook,
            AlertChannel.EMAIL: self._handle_email,
            AlertChannel.SLACK: self._handle_slack,
        }

        # Memory-based storage for testing
        self.memory_alerts: List[Dict[str, Any]] = []
        self.max_memory_alerts = 1000

    def add_threshold(self, threshold: AlertThreshold) -> None:
        """Register alert threshold."""
        self.thresholds[threshold.metric_name] = threshold
        logger.info(f"Added threshold: {threshold.metric_name}")

    def add_suppression_rule(self, rule: SuppressionRule) -> None:
        """Register suppression rule."""
        self.suppression_rules[rule.name] = rule
        logger.info(f"Added suppression rule: {rule.name}")

    def update_threshold(self, metric_name: str, value: float, severity: AlertSeverity) -> None:
        """Update threshold value for metric."""
        if metric_name in self.thresholds:
            self.thresholds[metric_name].threshold_value = value
            self.thresholds[metric_name].severity = severity
            logger.info(f"Updated threshold: {metric_name}")

    def check_metric(
        self,
        metric_name: str,
        value: float,
        source: str = "auto"
    ) -> Optional[Alert]:
        """Check metric against thresholds and create alert if needed."""
        if metric_name not in self.thresholds:
            return None

        threshold = self.thresholds[metric_name]
        if not threshold.enabled or not threshold.check(value):
            return None

        # Create alert
        alert = Alert(
            id=f"{metric_name}_{time.time()}",
            timestamp=time.time(),
            severity=threshold.severity,
            title=f"Threshold exceeded: {metric_name}",
            message=f"{metric_name} = {value} (threshold: {threshold.threshold_value})",
            source=source,
            data={'metric': metric_name, 'value': value, 'threshold': threshold.threshold_value},
            channels=[AlertChannel.LOG, AlertChannel.MEMORY],
        )

        return alert

    def process_alert(self, alert: Alert) -> bool:
        """
        Process alert: check suppression, aggregate, dispatch.

        Returns True if alert was processed, False if suppressed.
        """
        # Check suppression rules
        if self._should_suppress(alert):
            logger.debug(f"Alert suppressed: {alert.id}")
            return False

        # Check aggregation
        alert_key = f"{alert.source}:{alert.title}"
        self.aggregator.add_alert(alert_key, alert)

        if self.aggregator.should_aggregate(alert_key):
            # Send aggregated alert instead
            alert.message = self.aggregator.get_aggregated_message(alert_key)
            self.aggregator.clear_group(alert_key)

        # Store alert
        self.alerts[alert.id] = alert

        # Dispatch notifications
        self._dispatch_alert(alert)

        return True

    def _should_suppress(self, alert: Alert) -> bool:
        """Check if alert should be suppressed."""
        for rule in self.suppression_rules.values():
            if rule.should_suppress(alert.to_dict()):
                return True
        return False

    def _dispatch_alert(self, alert: Alert) -> None:
        """Dispatch alert to configured channels."""
        for channel in alert.channels:
            handler = self.handlers.get(channel)
            if handler:
                try:
                    handler(alert)
                except Exception as e:
                    logger.error(f"Error dispatching to {channel.value}: {e}")

    def _handle_log(self, alert: Alert) -> None:
        """Log alert."""
        level = {
            AlertSeverity.INFO: logging.INFO,
            AlertSeverity.WARNING: logging.WARNING,
            AlertSeverity.CRITICAL: logging.CRITICAL,
        }.get(alert.severity, logging.INFO)

        logger.log(level, f"[{alert.severity.name}] {alert.title}: {alert.message}")

    def _handle_memory(self, alert: Alert) -> None:
        """Store alert in memory."""
        alert_dict = alert.to_dict()
        self.memory_alerts.append(alert_dict)

        # Keep memory bounded
        if len(self.memory_alerts) > self.max_memory_alerts:
            self.memory_alerts.pop(0)

    def _handle_webhook(self, alert: Alert) -> None:
        """Send alert to webhook (stub for implementation)."""
        logger.debug(f"Would send webhook: {alert.id}")

    def _handle_email(self, alert: Alert) -> None:
        """Send alert via email (stub for implementation)."""
        logger.debug(f"Would send email: {alert.id}")

    def _handle_slack(self, alert: Alert) -> None:
        """Send alert to Slack (stub for implementation)."""
        logger.debug(f"Would send Slack: {alert.id}")

    def resolve_alert(self, alert_id: str) -> None:
        """Mark alert as resolved."""
        if alert_id in self.alerts:
            self.alerts[alert_id].resolved = True
            self.alerts[alert_id].resolution_time = time.time()
            logger.info(f"Alert resolved: {alert_id}")

    def get_active_alerts(self, severity: Optional[AlertSeverity] = None) -> List[Alert]:
        """Get list of active (unresolved) alerts."""
        alerts = [a for a in self.alerts.values() if not a.resolved]

        if severity:
            alerts = [a for a in alerts if a.severity == severity]

        return sorted(alerts, key=lambda a: a.timestamp, reverse=True)

    def get_recent_alerts(self, count: int = 20) -> List[Dict[str, Any]]:
        """Get recent alerts as dicts."""
        alerts = sorted(
            self.alerts.values(),
            key=lambda a: a.timestamp,
            reverse=True
        )[:count]
        return [a.to_dict() for a in alerts]

    def clear_resolved_alerts(self, older_than_hours: int = 24) -> int:
        """Clear resolved alerts older than specified hours."""
        cutoff_time = time.time() - (older_than_hours * 3600)
        to_remove = [
            aid for aid, alert in self.alerts.items()
            if alert.resolved and alert.resolution_time and alert.resolution_time < cutoff_time
        ]

        for aid in to_remove:
            del self.alerts[aid]

        logger.info(f"Cleared {len(to_remove)} old alerts")
        return len(to_remove)

    def get_stats(self) -> Dict[str, Any]:
        """Get alert manager statistics."""
        active = self.get_active_alerts()
        by_severity = {}
        for severity in AlertSeverity:
            by_severity[severity.name] = len(
                [a for a in active if a.severity == severity]
            )

        return {
            'total_alerts': len(self.alerts),
            'active_alerts': len(active),
            'memory_alerts': len(self.memory_alerts),
            'by_severity': by_severity,
            'thresholds_configured': len(self.thresholds),
            'suppression_rules': len(self.suppression_rules),
        }


# Global alert manager instance
_alert_manager: Optional[AlertManager] = None


def get_alert_manager() -> AlertManager:
    """Get or create global alert manager instance."""
    global _alert_manager
    if _alert_manager is None:
        _alert_manager = AlertManager()
    return _alert_manager


def add_threshold(threshold: AlertThreshold) -> None:
    """Helper to add threshold."""
    get_alert_manager().add_threshold(threshold)


def check_metric(metric_name: str, value: float, source: str = "auto") -> Optional[Alert]:
    """Helper to check metric and create alert if needed."""
    return get_alert_manager().check_metric(metric_name, value, source)


def process_alert(alert: Alert) -> bool:
    """Helper to process alert."""
    return get_alert_manager().process_alert(alert)
