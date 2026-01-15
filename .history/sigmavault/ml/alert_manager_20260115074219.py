"""
Multi-channel alert management system for ML pipeline monitoring.

Handles alert generation, deduplication, routing, and delivery across
multiple channels (email, webhook, logs). Supports escalation policies
based on alert severity and custom routing rules.
"""

from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from pathlib import Path
from typing import Dict, List, Optional, Set, Callable
import hashlib
import json
import logging
import smtplib
import threading
import time
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
import urllib.request
import urllib.error


logger = logging.getLogger(__name__)


class AlertSeverity(Enum):
    """Alert severity levels."""
    INFO = 0
    LOW = 1
    MEDIUM = 2
    HIGH = 3
    CRITICAL = 4


class AlertChannel(Enum):
    """Alert delivery channels."""
    EMAIL = "email"
    WEBHOOK = "webhook"
    LOG = "log"
    SMS = "sms"  # Future support
    SLACK = "slack"  # Future support


@dataclass
class Alert:
    """
    Alert with metadata and routing information.
    
    Attributes:
        id: Unique alert identifier (auto-generated)
        title: Short alert title
        message: Detailed alert message
        severity: Alert severity level
        source: Component that generated alert
        timestamp: When alert was created
        metadata: Additional alert context
        channels: Delivery channels for this alert
        resolved: Whether alert has been resolved
    """
    title: str
    message: str
    severity: AlertSeverity
    source: str
    timestamp: datetime = field(default_factory=datetime.now)
    metadata: Dict[str, any] = field(default_factory=dict)
    channels: List[AlertChannel] = field(default_factory=list)
    resolved: bool = False
    id: str = field(default="")
    
    def __post_init__(self):
        """Generate unique alert ID from content hash."""
        if not self.id:
            content = f"{self.title}:{self.source}:{self.severity.name}"
            self.id = hashlib.sha256(content.encode()).hexdigest()[:16]
    
    def to_dict(self) -> Dict:
        """Convert alert to dictionary."""
        return {
            'id': self.id,
            'title': self.title,
            'message': self.message,
            'severity': self.severity.name,
            'source': self.source,
            'timestamp': self.timestamp.isoformat(),
            'metadata': self.metadata,
            'channels': [ch.value for ch in self.channels],
            'resolved': self.resolved
        }


class BaseAlertChannel:
    """Base class for alert delivery channels."""
    
    def send(self, alert: Alert) -> bool:
        """
        Send alert through this channel.
        
        Args:
            alert: Alert to send
            
        Returns:
            True if successful, False otherwise
        """
        raise NotImplementedError


class LogAlertChannel(BaseAlertChannel):
    """Delivers alerts through structured logging."""
    
    def __init__(self, logger_name: str = "alerts"):
        """
        Initialize log alert channel.
        
        Args:
            logger_name: Name of logger to use
        """
        self.logger = logging.getLogger(logger_name)
    
    def send(self, alert: Alert) -> bool:
        """Log alert with appropriate severity."""
        log_level = {
            AlertSeverity.INFO: logging.INFO,
            AlertSeverity.LOW: logging.INFO,
            AlertSeverity.MEDIUM: logging.WARNING,
            AlertSeverity.HIGH: logging.ERROR,
            AlertSeverity.CRITICAL: logging.CRITICAL
        }.get(alert.severity, logging.WARNING)
        
        self.logger.log(
            log_level,
            f"[{alert.severity.name}] {alert.title}: {alert.message}",
            extra={
                'alert_id': alert.id,
                'source': alert.source,
                'metadata': alert.metadata
            }
        )
        return True


class EmailAlertChannel(BaseAlertChannel):
    """Delivers alerts via email using SMTP."""
    
    def __init__(
        self,
        smtp_host: str,
        smtp_port: int,
        from_addr: str,
        to_addrs: List[str],
        username: Optional[str] = None,
        password: Optional[str] = None,
        use_tls: bool = True
    ):
        """
        Initialize email alert channel.
        
        Args:
            smtp_host: SMTP server hostname
            smtp_port: SMTP server port
            from_addr: Sender email address
            to_addrs: List of recipient email addresses
            username: SMTP authentication username
            password: SMTP authentication password
            use_tls: Whether to use TLS encryption
        """
        self.smtp_host = smtp_host
        self.smtp_port = smtp_port
        self.from_addr = from_addr
        self.to_addrs = to_addrs
        self.username = username
        self.password = password
        self.use_tls = use_tls
    
    def send(self, alert: Alert) -> bool:
        """Send alert via email."""
        try:
            msg = MIMEMultipart('alternative')
            msg['Subject'] = f"[{alert.severity.name}] {alert.title}"
            msg['From'] = self.from_addr
            msg['To'] = ', '.join(self.to_addrs)
            
            # Create HTML body
            html = f"""
            <html>
              <body>
                <h2 style="color: {self._severity_color(alert.severity)};">
                  {alert.title}
                </h2>
                <p><strong>Severity:</strong> {alert.severity.name}</p>
                <p><strong>Source:</strong> {alert.source}</p>
                <p><strong>Time:</strong> {alert.timestamp.isoformat()}</p>
                <hr>
                <p>{alert.message}</p>
                {self._format_metadata_html(alert.metadata)}
              </body>
            </html>
            """
            
            msg.attach(MIMEText(html, 'html'))
            
            # Send email
            with smtplib.SMTP(self.smtp_host, self.smtp_port) as server:
                if self.use_tls:
                    server.starttls()
                if self.username and self.password:
                    server.login(self.username, self.password)
                server.sendmail(self.from_addr, self.to_addrs, msg.as_string())
            
            return True
        except Exception as e:
            logger.error(f"Failed to send email alert: {e}")
            return False
    
    def _severity_color(self, severity: AlertSeverity) -> str:
        """Get HTML color for severity level."""
        return {
            AlertSeverity.INFO: '#17a2b8',
            AlertSeverity.LOW: '#28a745',
            AlertSeverity.MEDIUM: '#ffc107',
            AlertSeverity.HIGH: '#fd7e14',
            AlertSeverity.CRITICAL: '#dc3545'
        }.get(severity, '#6c757d')
    
    def _format_metadata_html(self, metadata: Dict) -> str:
        """Format metadata as HTML table."""
        if not metadata:
            return ""
        
        rows = "".join([
            f"<tr><td><strong>{key}:</strong></td><td>{value}</td></tr>"
            for key, value in metadata.items()
        ])
        return f"<h3>Additional Details</h3><table>{rows}</table>"


class WebhookAlertChannel(BaseAlertChannel):
    """Delivers alerts via HTTP webhook POST."""
    
    def __init__(
        self,
        webhook_url: str,
        headers: Optional[Dict[str, str]] = None,
        timeout: int = 10
    ):
        """
        Initialize webhook alert channel.
        
        Args:
            webhook_url: URL to POST alerts to
            headers: Optional HTTP headers
            timeout: Request timeout in seconds
        """
        self.webhook_url = webhook_url
        self.headers = headers or {'Content-Type': 'application/json'}
        self.timeout = timeout
    
    def send(self, alert: Alert) -> bool:
        """Send alert via webhook POST."""
        try:
            payload = json.dumps(alert.to_dict()).encode('utf-8')
            request = urllib.request.Request(
                self.webhook_url,
                data=payload,
                headers=self.headers,
                method='POST'
            )
            
            with urllib.request.urlopen(request, timeout=self.timeout) as response:
                if response.status >= 200 and response.status < 300:
                    return True
                else:
                    logger.warning(f"Webhook returned status {response.status}")
                    return False
        except Exception as e:
            logger.error(f"Failed to send webhook alert: {e}")
            return False


class AlertManager:
    """
    Central alert management system with deduplication and routing.
    
    Handles alert lifecycle:
    1. Alert creation and validation
    2. Deduplication (suppress duplicate alerts within time window)
    3. Routing (select channels based on severity and rules)
    4. Delivery (send through all selected channels)
    5. Tracking (maintain alert history)
    
    Example:
        >>> manager = AlertManager()
        >>> manager.add_channel(LogAlertChannel())
        >>> manager.send_alert(Alert(
        ...     title="High anomaly score detected",
        ...     message="Score: 0.95, threshold: 0.8",
        ...     severity=AlertSeverity.HIGH,
        ...     source="AnomalyDetector"
        ... ))
    """
    
    def __init__(
        self,
        dedup_window_minutes: int = 5,
        max_history: int = 1000
    ):
        """
        Initialize alert manager.
        
        Args:
            dedup_window_minutes: Deduplication window duration
            max_history: Maximum alert history size
        """
        self.dedup_window = timedelta(minutes=dedup_window_minutes)
        self.max_history = max_history
        
        self.channels: Dict[AlertChannel, BaseAlertChannel] = {}
        self.routing_rules: List[Callable[[Alert], List[AlertChannel]]] = []
        self.alert_history: List[Alert] = []
        self.recent_alerts: Dict[str, datetime] = {}  # For deduplication
        self.lock = threading.Lock()
        
        # Default routing: all channels for all alerts
        self.add_routing_rule(lambda alert: list(self.channels.keys()))
    
    def add_channel(self, channel: BaseAlertChannel, channel_type: AlertChannel):
        """
        Register alert delivery channel.
        
        Args:
            channel: Channel implementation
            channel_type: Channel type identifier
        """
        with self.lock:
            self.channels[channel_type] = channel
            logger.info(f"Added alert channel: {channel_type.value}")
    
    def remove_channel(self, channel_type: AlertChannel):
        """Remove alert delivery channel."""
        with self.lock:
            if channel_type in self.channels:
                del self.channels[channel_type]
                logger.info(f"Removed alert channel: {channel_type.value}")
    
    def add_routing_rule(self, rule: Callable[[Alert], List[AlertChannel]]):
        """
        Add alert routing rule.
        
        Args:
            rule: Function that takes Alert and returns list of channels
        """
        with self.lock:
            self.routing_rules.append(rule)
    
    def send_alert(self, alert: Alert) -> bool:
        """
        Send alert with deduplication and routing.
        
        Args:
            alert: Alert to send
            
        Returns:
            True if at least one channel succeeded, False otherwise
        """
        with self.lock:
            # Check deduplication
            if self._is_duplicate(alert):
                logger.debug(f"Suppressed duplicate alert: {alert.id}")
                return False
            
            # Determine channels
            channels_to_use = self._route_alert(alert)
            if not channels_to_use:
                logger.warning(f"No channels available for alert: {alert.id}")
                return False
            
            # Send through channels
            success = False
            for channel_type in channels_to_use:
                if channel_type in self.channels:
                    try:
                        if self.channels[channel_type].send(alert):
                            success = True
                            logger.info(
                                f"Alert {alert.id} sent via {channel_type.value}"
                            )
                    except Exception as e:
                        logger.error(
                            f"Error sending alert via {channel_type.value}: {e}"
                        )
            
            # Update history
            self._add_to_history(alert)
            
            return success
    
    def _is_duplicate(self, alert: Alert) -> bool:
        """Check if alert is duplicate within dedup window."""
        if alert.id in self.recent_alerts:
            last_sent = self.recent_alerts[alert.id]
            if datetime.now() - last_sent < self.dedup_window:
                return True
        
        self.recent_alerts[alert.id] = datetime.now()
        return False
    
    def _route_alert(self, alert: Alert) -> List[AlertChannel]:
        """Determine channels for alert based on routing rules."""
        channels = set()
        
        # Apply routing rules
        for rule in self.routing_rules:
            try:
                rule_channels = rule(alert)
                channels.update(rule_channels)
            except Exception as e:
                logger.error(f"Error in routing rule: {e}")
        
        # Use alert's specified channels if provided
        if alert.channels:
            channels.update(alert.channels)
        
        return list(channels)
    
    def _add_to_history(self, alert: Alert):
        """Add alert to history with size limit."""
        self.alert_history.append(alert)
        
        # Enforce max history size
        if len(self.alert_history) > self.max_history:
            self.alert_history = self.alert_history[-self.max_history:]
    
    def get_recent_alerts(self, minutes: int = 60) -> List[Alert]:
        """
        Get alerts from recent time window.
        
        Args:
            minutes: Time window duration
            
        Returns:
            List of alerts within window
        """
        cutoff = datetime.now() - timedelta(minutes=minutes)
        with self.lock:
            return [
                alert for alert in self.alert_history
                if alert.timestamp > cutoff
            ]
    
    def get_alerts_by_severity(self, severity: AlertSeverity) -> List[Alert]:
        """Get all alerts matching severity."""
        with self.lock:
            return [
                alert for alert in self.alert_history
                if alert.severity == severity
            ]
    
    def resolve_alert(self, alert_id: str):
        """Mark alert as resolved."""
        with self.lock:
            for alert in self.alert_history:
                if alert.id == alert_id:
                    alert.resolved = True
                    logger.info(f"Resolved alert: {alert_id}")
                    break
    
    def get_statistics(self) -> Dict:
        """
        Get alert statistics.
        
        Returns:
            Dictionary with counts by severity and channel
        """
        with self.lock:
            total = len(self.alert_history)
            by_severity = {
                severity.name: sum(
                    1 for alert in self.alert_history
                    if alert.severity == severity
                )
                for severity in AlertSeverity
            }
            resolved_count = sum(
                1 for alert in self.alert_history if alert.resolved
            )
            
            return {
                'total_alerts': total,
                'by_severity': by_severity,
                'resolved': resolved_count,
                'unresolved': total - resolved_count,
                'active_channels': list(self.channels.keys())
            }
    
    def clear_history(self):
        """Clear alert history."""
        with self.lock:
            self.alert_history.clear()
            self.recent_alerts.clear()
            logger.info("Cleared alert history")


# Severity-based routing rule
def route_by_severity(alert: Alert) -> List[AlertChannel]:
    """Route alerts based on severity level."""
    if alert.severity == AlertSeverity.CRITICAL:
        return [AlertChannel.EMAIL, AlertChannel.WEBHOOK, AlertChannel.LOG]
    elif alert.severity >= AlertSeverity.HIGH:
        return [AlertChannel.WEBHOOK, AlertChannel.LOG]
    elif alert.severity >= AlertSeverity.MEDIUM:
        return [AlertChannel.LOG]
    else:
        return [AlertChannel.LOG]
