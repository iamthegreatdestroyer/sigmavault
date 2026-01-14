"""
ML Security Bridge for ΣVAULT Filesystem
==========================================

Integrates machine learning-based anomaly detection with filesystem operations.
Provides real-time threat detection, alerting, and automated responses.

ARCHITECTURE:

    ┌─────────────────────────────────────────────────────────────┐
    │                    FUSE OPERATIONS                          │
    │              (open, read, write, etc.)                      │
    └────────────────────────┬────────────────────────────────────┘
                             │
                    AccessEvent logged
                             │
                             ▼
    ┌─────────────────────────────────────────────────────────────┐
    │                  ML SECURITY BRIDGE                         │
    │  ┌──────────────┐  ┌──────────────┐  ┌──────────────────┐  │
    │  │ Event Buffer │→ │  Anomaly     │→ │ Response Engine │  │
    │  │ (sliding     │  │  Detector    │  │ (throttle/block │  │
    │  │  window)     │  │  (ML model)  │  │  /alert)        │  │
    │  └──────────────┘  └──────────────┘  └──────────────────┘  │
    │         │                 │                   │             │
    │         └────────────────┼───────────────────┘             │
    │                          │                                  │
    │                    Alert Handlers                           │
    │  ┌──────────────┐  ┌──────────────┐  ┌──────────────────┐  │
    │  │   Console    │  │   Webhook    │  │      File        │  │
    │  │   Alert      │  │   Notifier   │  │      Log         │  │
    │  └──────────────┘  └──────────────┘  └──────────────────┘  │
    └─────────────────────────────────────────────────────────────┘

THREAT RESPONSE LEVELS:

    NORMAL     → No action, continue operation
    SUSPICIOUS → Log warning, continue with monitoring
    WARNING    → Throttle operations, send alert
    CRITICAL   → Block operations, emergency alert, trigger re-scatter

Copyright (c) 2026 ΣVAULT. All Rights Reserved.
Agents: @TENSOR @FORTRESS @SENTRY
"""

import os
import json
import hashlib
import threading
import queue
import time
import logging
from pathlib import Path
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Callable, Any, Tuple
from dataclasses import dataclass, field
from enum import Enum, auto
from collections import deque
import traceback

from ..ml.access_logger import AccessLogger, AccessEvent
from ..ml.anomaly_detector import AnomalyDetector, AlertLevel

# Optional imports
try:
    import requests
    HAS_REQUESTS = True
except ImportError:
    HAS_REQUESTS = False


# ============================================================================
# ENUMS AND DATA CLASSES
# ============================================================================

class ThreatAction(Enum):
    """Actions to take in response to detected threats."""
    ALLOW = auto()           # Allow operation
    LOG = auto()             # Log and allow
    THROTTLE = auto()        # Slow down operations
    BLOCK = auto()           # Block operation
    LOCKDOWN = auto()        # Emergency lockdown
    RESCATTER = auto()       # Trigger re-scattering


class AlertChannel(Enum):
    """Notification channels for alerts."""
    CONSOLE = auto()         # Print to console
    FILE = auto()            # Write to log file
    WEBHOOK = auto()         # HTTP webhook
    CALLBACK = auto()        # Custom callback function


@dataclass
class ThreatResponse:
    """Response configuration for each alert level."""
    action: ThreatAction
    throttle_delay_ms: int = 0       # Delay in milliseconds
    block_duration_s: int = 0        # Block duration in seconds
    alert_channels: List[AlertChannel] = field(default_factory=list)
    escalate_after: int = 0          # Escalate after N occurrences
    

@dataclass
class SecurityAlert:
    """A security alert to be dispatched."""
    timestamp: datetime
    level: AlertLevel
    score: float
    message: str
    details: Dict[str, Any]
    source_ip: Optional[str] = None
    user_id: Optional[str] = None
    file_path: Optional[str] = None
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            'timestamp': self.timestamp.isoformat(),
            'level': self.level.name,
            'score': self.score,
            'message': self.message,
            'details': self.details,
            'source_ip': self.source_ip,
            'user_id': self.user_id,
            'file_path': self.file_path
        }
    
    def to_json(self) -> str:
        return json.dumps(self.to_dict(), indent=2)


@dataclass
class MLSecurityConfig:
    """Configuration for ML security bridge."""
    # Detection settings
    detection_window_minutes: int = 60       # Events window for analysis
    detection_interval_seconds: int = 30     # How often to run detection
    min_events_for_detection: int = 10       # Minimum events to analyze
    
    # Response configuration
    responses: Dict[AlertLevel, ThreatResponse] = None
    
    # Alert settings
    alert_log_path: Optional[Path] = None
    webhook_url: Optional[str] = None
    alert_cooldown_seconds: int = 60         # Minimum time between alerts
    
    # Throttle settings
    max_ops_per_second: int = 100            # Rate limit when throttled
    block_list_ttl_seconds: int = 300        # How long to keep blocks
    
    def __post_init__(self):
        if self.responses is None:
            self.responses = {
                AlertLevel.NORMAL: ThreatResponse(
                    action=ThreatAction.ALLOW
                ),
                AlertLevel.SUSPICIOUS: ThreatResponse(
                    action=ThreatAction.LOG,
                    alert_channels=[AlertChannel.CONSOLE, AlertChannel.FILE],
                    escalate_after=5
                ),
                AlertLevel.WARNING: ThreatResponse(
                    action=ThreatAction.THROTTLE,
                    throttle_delay_ms=100,
                    alert_channels=[AlertChannel.CONSOLE, AlertChannel.FILE, AlertChannel.WEBHOOK],
                    escalate_after=3
                ),
                AlertLevel.CRITICAL: ThreatResponse(
                    action=ThreatAction.BLOCK,
                    block_duration_s=300,
                    alert_channels=[AlertChannel.CONSOLE, AlertChannel.FILE, AlertChannel.WEBHOOK],
                    escalate_after=0
                )
            }


# ============================================================================
# ALERT HANDLERS
# ============================================================================

class AlertHandler:
    """Base class for alert handlers."""
    
    def handle(self, alert: SecurityAlert) -> bool:
        """Handle alert. Returns True on success."""
        raise NotImplementedError


class ConsoleAlertHandler(AlertHandler):
    """Prints alerts to console."""
    
    COLORS = {
        AlertLevel.NORMAL: '\033[92m',      # Green
        AlertLevel.SUSPICIOUS: '\033[93m',  # Yellow
        AlertLevel.WARNING: '\033[91m',     # Red
        AlertLevel.CRITICAL: '\033[95m',    # Magenta
    }
    RESET = '\033[0m'
    
    def handle(self, alert: SecurityAlert) -> bool:
        color = self.COLORS.get(alert.level, '')
        print(f"\n{color}{'='*60}")
        print(f"⚠️  ΣVAULT SECURITY ALERT - {alert.level.name}")
        print(f"{'='*60}{self.RESET}")
        print(f"Time:    {alert.timestamp.strftime('%Y-%m-%d %H:%M:%S')}")
        print(f"Score:   {alert.score:.4f}")
        print(f"Message: {alert.message}")
        if alert.file_path:
            print(f"File:    {alert.file_path}")
        if alert.user_id:
            print(f"User:    {alert.user_id}")
        if alert.source_ip:
            print(f"IP:      {alert.source_ip}")
        print(f"{color}{'='*60}{self.RESET}\n")
        return True


class FileAlertHandler(AlertHandler):
    """Writes alerts to a log file."""
    
    def __init__(self, log_path: Path):
        self.log_path = Path(log_path)
        self.log_path.parent.mkdir(parents=True, exist_ok=True)
        self._lock = threading.Lock()
    
    def handle(self, alert: SecurityAlert) -> bool:
        try:
            with self._lock:
                with open(self.log_path, 'a') as f:
                    f.write(alert.to_json())
                    f.write('\n---\n')
            return True
        except Exception as e:
            print(f"Failed to write alert to file: {e}")
            return False


class WebhookAlertHandler(AlertHandler):
    """Sends alerts to a webhook URL."""
    
    def __init__(self, webhook_url: str, timeout: int = 10):
        if not HAS_REQUESTS:
            raise ImportError("requests library required for webhook alerts")
        self.webhook_url = webhook_url
        self.timeout = timeout
    
    def handle(self, alert: SecurityAlert) -> bool:
        try:
            response = requests.post(
                self.webhook_url,
                json=alert.to_dict(),
                timeout=self.timeout,
                headers={'Content-Type': 'application/json'}
            )
            return response.status_code == 200
        except Exception as e:
            print(f"Webhook alert failed: {e}")
            return False


class CallbackAlertHandler(AlertHandler):
    """Calls a custom callback function."""
    
    def __init__(self, callback: Callable[[SecurityAlert], bool]):
        self.callback = callback
    
    def handle(self, alert: SecurityAlert) -> bool:
        try:
            return self.callback(alert)
        except Exception as e:
            print(f"Callback alert failed: {e}")
            return False


# ============================================================================
# RATE LIMITER
# ============================================================================

class TokenBucketRateLimiter:
    """Token bucket rate limiter for throttling operations."""
    
    def __init__(self, rate: float, capacity: float):
        """
        Args:
            rate: Tokens added per second
            capacity: Maximum tokens in bucket
        """
        self.rate = rate
        self.capacity = capacity
        self.tokens = capacity
        self.last_update = time.time()
        self._lock = threading.Lock()
    
    def acquire(self, tokens: int = 1, blocking: bool = True) -> bool:
        """
        Acquire tokens. Returns True if tokens acquired.
        
        Args:
            tokens: Number of tokens to acquire
            blocking: If True, wait until tokens available
        """
        with self._lock:
            while True:
                # Refill tokens
                now = time.time()
                elapsed = now - self.last_update
                self.tokens = min(self.capacity, self.tokens + elapsed * self.rate)
                self.last_update = now
                
                if self.tokens >= tokens:
                    self.tokens -= tokens
                    return True
                
                if not blocking:
                    return False
                
                # Calculate wait time
                wait_time = (tokens - self.tokens) / self.rate
                time.sleep(min(wait_time, 0.1))  # Max 100ms sleep


# ============================================================================
# ML SECURITY BRIDGE
# ============================================================================

class MLSecurityBridge:
    """
    Bridge between filesystem operations and ML anomaly detection.
    
    Provides:
    - Real-time anomaly detection on access patterns
    - Configurable threat responses (log/throttle/block)
    - Multi-channel alerting (console/file/webhook)
    - Automatic threat escalation
    - Operation rate limiting
    
    Example:
        >>> bridge = MLSecurityBridge(vault_path="/secure/vault")
        >>> 
        >>> # Check if operation should be allowed
        >>> action = bridge.check_access(path="/secrets/key.pem", operation="read")
        >>> if action == ThreatAction.BLOCK:
        ...     raise PermissionError("Access blocked due to suspicious activity")
        >>> elif action == ThreatAction.THROTTLE:
        ...     bridge.apply_throttle()
        >>> 
        >>> # Log the access (for future detection)
        >>> bridge.log_access(path="/secrets/key.pem", operation="read", ...)
    """
    
    def __init__(
        self,
        vault_path: Path,
        config: Optional[MLSecurityConfig] = None,
        auto_train: bool = False
    ):
        """
        Initialize ML Security Bridge.
        
        Args:
            vault_path: Path to vault directory
            config: Security configuration (uses defaults if None)
            auto_train: Whether to auto-train anomaly detector
        """
        self.vault_path = Path(vault_path)
        self.config = config or MLSecurityConfig()
        
        # Initialize ML components
        self.access_logger = AccessLogger(vault_path)
        self.anomaly_detector = AnomalyDetector(vault_path)
        
        # Alert handlers
        self.alert_handlers: Dict[AlertChannel, AlertHandler] = {
            AlertChannel.CONSOLE: ConsoleAlertHandler()
        }
        
        # Set up file alert handler
        if self.config.alert_log_path:
            self.alert_handlers[AlertChannel.FILE] = FileAlertHandler(
                self.config.alert_log_path
            )
        else:
            default_log = self.vault_path / '.ml' / 'security_alerts.log'
            self.alert_handlers[AlertChannel.FILE] = FileAlertHandler(default_log)
        
        # Set up webhook handler
        if self.config.webhook_url and HAS_REQUESTS:
            self.alert_handlers[AlertChannel.WEBHOOK] = WebhookAlertHandler(
                self.config.webhook_url
            )
        
        # Rate limiter for throttling
        self.rate_limiter = TokenBucketRateLimiter(
            rate=self.config.max_ops_per_second,
            capacity=self.config.max_ops_per_second * 2
        )
        
        # Block list (IP/user -> unblock time)
        self.block_list: Dict[str, float] = {}
        self._block_lock = threading.Lock()
        
        # Recent events buffer for detection
        self.event_buffer: deque = deque(maxlen=1000)
        self._buffer_lock = threading.Lock()
        
        # Alert cooldown tracking
        self.last_alert_time: Dict[AlertLevel, float] = {}
        self._alert_lock = threading.Lock()
        
        # Threat escalation counter
        self.threat_counts: Dict[str, int] = {}
        self._threat_lock = threading.Lock()
        
        # Detection state
        self.is_detection_running = False
        self._detection_thread: Optional[threading.Thread] = None
        self._stop_detection = threading.Event()
        
        # Auto-train if requested and model doesn't exist
        if auto_train and not self.anomaly_detector.model_path.exists():
            self._try_auto_train()
    
    def _try_auto_train(self):
        """Try to auto-train the anomaly detector with existing data."""
        try:
            self.anomaly_detector.train(training_days=30)
            print("✅ Anomaly detector auto-trained successfully")
        except ValueError as e:
            print(f"⚠️  Insufficient data for auto-training: {e}")
        except Exception as e:
            print(f"⚠️  Auto-training failed: {e}")
    
    def start_detection(self):
        """Start background anomaly detection thread."""
        if self.is_detection_running:
            return
        
        self._stop_detection.clear()
        self._detection_thread = threading.Thread(
            target=self._detection_worker,
            daemon=True,
            name="MLSecurityDetection"
        )
        self._detection_thread.start()
        self.is_detection_running = True
        print("🔒 ML Security Detection started")
    
    def stop_detection(self):
        """Stop background anomaly detection."""
        if not self.is_detection_running:
            return
        
        self._stop_detection.set()
        if self._detection_thread:
            self._detection_thread.join(timeout=5)
        self.is_detection_running = False
        print("🔓 ML Security Detection stopped")
    
    def _detection_worker(self):
        """Background worker for anomaly detection."""
        while not self._stop_detection.is_set():
            try:
                self._run_detection_cycle()
            except Exception as e:
                print(f"Detection cycle error: {e}")
                traceback.print_exc()
            
            # Wait for next cycle
            self._stop_detection.wait(self.config.detection_interval_seconds)
    
    def _run_detection_cycle(self):
        """Run a single anomaly detection cycle."""
        # Get recent events from buffer
        with self._buffer_lock:
            events = list(self.event_buffer)
        
        if len(events) < self.config.min_events_for_detection:
            return  # Not enough events
        
        # Filter to detection window
        window = timedelta(minutes=self.config.detection_window_minutes)
        cutoff = datetime.now() - window
        recent_events = [e for e in events if e.timestamp >= cutoff]
        
        if len(recent_events) < self.config.min_events_for_detection:
            return
        
        # Run anomaly detection
        if self.anomaly_detector.model is None:
            return  # Model not trained
        
        try:
            is_anomaly, score, level = self.anomaly_detector.detect(recent_events)
            
            if is_anomaly:
                self._handle_anomaly(score, level, recent_events)
                
        except Exception as e:
            print(f"Anomaly detection failed: {e}")
    
    def _handle_anomaly(
        self,
        score: float,
        level: AlertLevel,
        events: List[AccessEvent]
    ):
        """Handle detected anomaly."""
        # Get response configuration
        response = self.config.responses.get(level)
        if not response:
            return
        
        # Check escalation
        threat_key = f"anomaly_{level.name}"
        with self._threat_lock:
            self.threat_counts[threat_key] = self.threat_counts.get(threat_key, 0) + 1
            count = self.threat_counts[threat_key]
        
        # Escalate if threshold reached
        if response.escalate_after > 0 and count >= response.escalate_after:
            # Escalate to next level
            if level == AlertLevel.SUSPICIOUS:
                level = AlertLevel.WARNING
                response = self.config.responses.get(level)
            elif level == AlertLevel.WARNING:
                level = AlertLevel.CRITICAL
                response = self.config.responses.get(level)
            
            with self._threat_lock:
                self.threat_counts[threat_key] = 0  # Reset counter
        
        # Create alert
        alert = self._create_alert(score, level, events)
        
        # Dispatch alert (with cooldown)
        self._dispatch_alert(alert, response.alert_channels)
        
        # Apply response action
        self._apply_response(response, events)
    
    def _create_alert(
        self,
        score: float,
        level: AlertLevel,
        events: List[AccessEvent]
    ) -> SecurityAlert:
        """Create a security alert from detection results."""
        # Get explanation if available
        try:
            explanation = self.anomaly_detector.explain_anomaly(events)
        except:
            explanation = {}
        
        # Extract details from events
        unique_files = len(set(e.file_path_hash for e in events))
        unique_ips = len(set(e.ip_hash for e in events if e.ip_hash))
        operations = {}
        for e in events:
            operations[e.operation] = operations.get(e.operation, 0) + 1
        
        details = {
            'event_count': len(events),
            'unique_files': unique_files,
            'unique_ips': unique_ips,
            'operations': operations,
            'explanation': explanation,
            'time_span_minutes': (
                (events[-1].timestamp - events[0].timestamp).total_seconds() / 60
                if len(events) > 1 else 0
            )
        }
        
        # Determine message based on level
        messages = {
            AlertLevel.SUSPICIOUS: "Unusual access pattern detected",
            AlertLevel.WARNING: "Potentially malicious activity detected",
            AlertLevel.CRITICAL: "Critical security threat detected - immediate action required"
        }
        
        return SecurityAlert(
            timestamp=datetime.now(),
            level=level,
            score=score,
            message=messages.get(level, "Security anomaly detected"),
            details=details,
            source_ip=events[-1].ip_hash if events else None,
            user_id=events[-1].user_id_hash if events else None,
            file_path=None  # Multiple files typically involved
        )
    
    def _dispatch_alert(
        self,
        alert: SecurityAlert,
        channels: List[AlertChannel]
    ):
        """Dispatch alert to specified channels."""
        # Check cooldown
        with self._alert_lock:
            last_time = self.last_alert_time.get(alert.level, 0)
            if time.time() - last_time < self.config.alert_cooldown_seconds:
                return  # In cooldown period
            self.last_alert_time[alert.level] = time.time()
        
        # Dispatch to each channel
        for channel in channels:
            handler = self.alert_handlers.get(channel)
            if handler:
                try:
                    handler.handle(alert)
                except Exception as e:
                    print(f"Alert dispatch failed for {channel.name}: {e}")
    
    def _apply_response(
        self,
        response: ThreatResponse,
        events: List[AccessEvent]
    ):
        """Apply threat response action."""
        if response.action == ThreatAction.THROTTLE:
            # Reduce rate limit temporarily
            self.rate_limiter.rate = max(1, self.rate_limiter.rate / 2)
            print(f"⚡ Throttling enabled: {self.rate_limiter.rate} ops/sec")
            
        elif response.action == ThreatAction.BLOCK:
            # Block the source
            if events and events[-1].ip_hash:
                self._add_to_block_list(
                    events[-1].ip_hash,
                    response.block_duration_s
                )
                print(f"🚫 Blocked IP hash: {events[-1].ip_hash[:16]}...")
                
        elif response.action == ThreatAction.LOCKDOWN:
            # Emergency lockdown
            print("🔒 EMERGENCY LOCKDOWN TRIGGERED")
            # This would integrate with vault lock mechanism
    
    def _add_to_block_list(self, identifier: str, duration_s: int):
        """Add identifier to block list."""
        with self._block_lock:
            unblock_time = time.time() + duration_s
            self.block_list[identifier] = unblock_time
    
    def _is_blocked(self, identifier: str) -> bool:
        """Check if identifier is blocked."""
        with self._block_lock:
            unblock_time = self.block_list.get(identifier)
            if unblock_time is None:
                return False
            
            if time.time() >= unblock_time:
                # Block expired
                del self.block_list[identifier]
                return False
            
            return True
    
    def log_access(
        self,
        path: str,
        operation: str,
        bytes_accessed: int,
        duration_ms: float,
        success: bool,
        error_code: Optional[str] = None,
        user_id: Optional[str] = None,
        ip_address: Optional[str] = None,
        device_fingerprint: Optional[str] = None
    ):
        """
        Log an access event for ML analysis.
        
        Called by FUSE operations to track access patterns.
        """
        # Hash identifiers for privacy
        path_hash = hashlib.sha256(path.encode()).hexdigest()
        user_hash = hashlib.sha256(user_id.encode()).hexdigest() if user_id else None
        ip_hash = hashlib.sha256(ip_address.encode()).hexdigest() if ip_address else None
        
        event = AccessEvent(
            timestamp=datetime.now(),
            vault_id=hashlib.sha256(str(self.vault_path).encode()).hexdigest()[:16],
            file_path_hash=path_hash,
            operation=operation,
            bytes_accessed=bytes_accessed,
            duration_ms=duration_ms,
            user_id_hash=user_hash,
            device_fingerprint=device_fingerprint,
            ip_hash=ip_hash,
            success=success,
            error_code=error_code
        )
        
        # Add to buffer for detection
        with self._buffer_lock:
            self.event_buffer.append(event)
        
        # Log to persistent storage
        self.access_logger.log_event(event)
    
    def check_access(
        self,
        path: str,
        operation: str,
        user_id: Optional[str] = None,
        ip_address: Optional[str] = None
    ) -> ThreatAction:
        """
        Check if an access should be allowed.
        
        Returns the recommended action (ALLOW, LOG, THROTTLE, BLOCK).
        Called before FUSE operations to determine access control.
        
        Args:
            path: File path being accessed
            operation: Operation type (read, write, etc.)
            user_id: User identifier (optional)
            ip_address: Source IP address (optional)
            
        Returns:
            ThreatAction indicating what to do
        """
        # Check block list
        identifiers_to_check = []
        if ip_address:
            ip_hash = hashlib.sha256(ip_address.encode()).hexdigest()
            identifiers_to_check.append(ip_hash)
        if user_id:
            user_hash = hashlib.sha256(user_id.encode()).hexdigest()
            identifiers_to_check.append(user_hash)
        
        for identifier in identifiers_to_check:
            if self._is_blocked(identifier):
                return ThreatAction.BLOCK
        
        # If detection is running, check recent analysis
        # For now, allow but future versions could do real-time checks
        return ThreatAction.ALLOW
    
    def apply_throttle(self) -> float:
        """
        Apply throttling if enabled.
        
        Returns the time waited in seconds.
        """
        start = time.time()
        self.rate_limiter.acquire(blocking=True)
        return time.time() - start
    
    def register_alert_callback(self, callback: Callable[[SecurityAlert], bool]):
        """Register a custom callback for alerts."""
        self.alert_handlers[AlertChannel.CALLBACK] = CallbackAlertHandler(callback)
    
    def get_security_status(self) -> Dict[str, Any]:
        """Get current security status."""
        with self._buffer_lock:
            event_count = len(self.event_buffer)
        
        with self._block_lock:
            blocked_count = len(self.block_list)
        
        with self._threat_lock:
            threat_counts = dict(self.threat_counts)
        
        return {
            'detection_running': self.is_detection_running,
            'model_trained': self.anomaly_detector.model is not None,
            'events_buffered': event_count,
            'blocked_identifiers': blocked_count,
            'threat_counts': threat_counts,
            'rate_limit': self.rate_limiter.rate,
            'timestamp': datetime.now().isoformat()
        }
    
    def reset_threat_counters(self):
        """Reset threat escalation counters."""
        with self._threat_lock:
            self.threat_counts.clear()
    
    def clear_block_list(self):
        """Clear all blocks."""
        with self._block_lock:
            self.block_list.clear()
    
    def train_detector(self, training_days: int = 30) -> Dict[str, Any]:
        """Train the anomaly detector on historical data."""
        return self.anomaly_detector.train(
            training_days=training_days,
            access_logger=self.access_logger
        )


# ============================================================================
# CONVENIENCE FUNCTIONS
# ============================================================================

def create_security_bridge(
    vault_path: Path,
    webhook_url: Optional[str] = None,
    auto_start: bool = True
) -> MLSecurityBridge:
    """
    Create a configured ML Security Bridge.
    
    Args:
        vault_path: Path to vault directory
        webhook_url: Optional webhook for alerts
        auto_start: Whether to start detection automatically
        
    Returns:
        Configured MLSecurityBridge instance
    """
    config = MLSecurityConfig(
        detection_interval_seconds=30,
        webhook_url=webhook_url
    )
    
    bridge = MLSecurityBridge(vault_path, config, auto_train=True)
    
    if auto_start:
        bridge.start_detection()
    
    return bridge


if __name__ == '__main__':
    print("ML Security Bridge for ΣVAULT")
    print("=" * 40)
    print("Use create_security_bridge() to initialize")
    print("Call bridge.start_detection() to begin monitoring")
