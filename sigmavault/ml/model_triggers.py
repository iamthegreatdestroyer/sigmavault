"""
Model Update Triggers
======================

Intelligent triggers for model retraining and parameter recalculation.

Monitors access patterns and triggers model updates when:
- Access patterns deviate significantly from training distribution
- New file types are introduced
- Security anomalies are detected
- Performance metrics degrade
- Periodic scheduled updates

Architecture:
┌─────────────────────────────────────────────────────────────┐
│                  MODEL UPDATE TRIGGERS                      │
├─────────────────────────────────────────────────────────────┤
│  DRIFT DETECTOR                                            │
│  ─────────────────                                          │
│  • Statistical tests for distribution shift                 │
│  • Sliding window comparison                                │
│  • KL divergence monitoring                                 │
│                                                             │
│  ANOMALY TRIGGER                                           │
│  ─────────────────                                          │
│  • Consecutive anomaly detection                            │
│  • High-severity event counting                             │
│  • Pattern deviation tracking                               │
│                                                             │
│  PERFORMANCE TRIGGER                                       │
│  ─────────────────                                          │
│  • Prediction accuracy monitoring                           │
│  • Latency threshold violations                             │
│  • Cache miss rate tracking                                 │
│                                                             │
│  SCHEDULED TRIGGER                                         │
│  ─────────────────                                          │
│  • Periodic retraining (daily/weekly)                       │
│  • Minimum data accumulation                                │
│  • Quiet period detection                                   │
└─────────────────────────────────────────────────────────────┘

Copyright (c) 2025 ΣVAULT. All Rights Reserved.
Agents: @TENSOR @NEURAL @SENTRY
"""

import os
import json
import hashlib
import threading
import time
from pathlib import Path
from datetime import datetime, timedelta
from typing import Dict, Optional, List, Tuple, Any, Callable
from dataclasses import dataclass, field
from collections import deque
from enum import Enum, auto
import numpy as np

from .access_logger import AccessEvent
from .feature_extractor import FeatureExtractor


# ============================================================================
# TRIGGER TYPES AND CONFIGURATION
# ============================================================================

class TriggerType(Enum):
    """Types of model update triggers."""
    DRIFT = auto()
    ANOMALY = auto()
    PERFORMANCE = auto()
    SCHEDULED = auto()
    MANUAL = auto()
    NEW_PATTERN = auto()


class TriggerPriority(Enum):
    """Priority levels for triggers."""
    LOW = 1
    MEDIUM = 2
    HIGH = 3
    CRITICAL = 4


@dataclass
class TriggerEvent:
    """A triggered model update event."""
    trigger_type: TriggerType
    priority: TriggerPriority
    timestamp: datetime
    reason: str
    metrics: Dict[str, Any]
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            'trigger_type': self.trigger_type.name,
            'priority': self.priority.name,
            'timestamp': self.timestamp.isoformat(),
            'reason': self.reason,
            'metrics': self.metrics
        }


@dataclass
class TriggerConfig:
    """Configuration for model update triggers."""
    
    # Drift detection
    drift_window_size: int = 1000
    drift_threshold: float = 0.1  # KL divergence threshold
    drift_check_interval: int = 300  # Seconds between checks
    
    # Anomaly trigger
    anomaly_count_threshold: int = 10
    anomaly_window_minutes: int = 60
    consecutive_anomaly_threshold: int = 5
    
    # Performance trigger
    accuracy_degradation_threshold: float = 0.2
    latency_threshold_ms: float = 100.0
    cache_miss_rate_threshold: float = 0.5
    
    # Scheduled trigger
    scheduled_interval_hours: int = 24
    min_samples_for_retrain: int = 100
    quiet_hours: Tuple[int, int] = (2, 5)  # Prefer retraining 2-5 AM
    
    # General settings
    cooldown_minutes: int = 30  # Min time between triggers
    max_triggers_per_day: int = 10
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            'drift_threshold': self.drift_threshold,
            'anomaly_count_threshold': self.anomaly_count_threshold,
            'scheduled_interval_hours': self.scheduled_interval_hours,
            'cooldown_minutes': self.cooldown_minutes
        }


# ============================================================================
# DRIFT DETECTOR
# ============================================================================

class DriftDetector:
    """
    Detects distribution drift in access patterns.
    
    Uses KL divergence to compare current feature distribution
    with training distribution.
    """
    
    def __init__(
        self,
        window_size: int = 1000,
        threshold: float = 0.1,
        n_bins: int = 20
    ):
        self.window_size = window_size
        self.threshold = threshold
        self.n_bins = n_bins
        
        # Reference distribution (from training)
        self._reference_histograms: Optional[List[np.ndarray]] = None
        self._feature_ranges: Optional[List[Tuple[float, float]]] = None
        
        # Current window
        self._current_window: deque = deque(maxlen=window_size)
        self._lock = threading.RLock()
    
    def set_reference(self, features: np.ndarray):
        """
        Set reference distribution from training data.
        
        Args:
            features: Shape (n_samples, n_features)
        """
        with self._lock:
            self._reference_histograms = []
            self._feature_ranges = []
            
            n_features = features.shape[1]
            
            for i in range(n_features):
                col = features[:, i]
                
                # Compute range and histogram
                min_val, max_val = col.min(), col.max()
                # Add small epsilon to avoid division by zero
                if min_val == max_val:
                    max_val = min_val + 1e-6
                
                self._feature_ranges.append((min_val, max_val))
                
                hist, _ = np.histogram(
                    col, bins=self.n_bins,
                    range=(min_val, max_val),
                    density=True
                )
                # Add small epsilon to avoid log(0)
                hist = hist + 1e-10
                hist = hist / hist.sum()
                
                self._reference_histograms.append(hist)
    
    def add_observation(self, features: np.ndarray):
        """Add a feature vector to the current window."""
        with self._lock:
            self._current_window.append(features)
    
    def compute_drift(self) -> Tuple[float, Dict[str, float]]:
        """
        Compute drift between current and reference distributions.
        
        Returns:
            (overall_drift, per_feature_drift)
        """
        with self._lock:
            if (self._reference_histograms is None or 
                len(self._current_window) < self.window_size // 2):
                return 0.0, {}
            
            current_features = np.array(list(self._current_window))
            n_features = current_features.shape[1]
            
            drift_scores = {}
            total_drift = 0.0
            
            for i in range(n_features):
                col = current_features[:, i]
                min_val, max_val = self._feature_ranges[i]
                
                # Compute current histogram
                current_hist, _ = np.histogram(
                    col, bins=self.n_bins,
                    range=(min_val, max_val),
                    density=True
                )
                current_hist = current_hist + 1e-10
                current_hist = current_hist / current_hist.sum()
                
                # Compute KL divergence
                kl_div = np.sum(
                    self._reference_histograms[i] * 
                    np.log(self._reference_histograms[i] / current_hist)
                )
                
                drift_scores[f'feature_{i}'] = float(kl_div)
                total_drift += kl_div
            
            avg_drift = total_drift / n_features if n_features > 0 else 0.0
            
            return avg_drift, drift_scores
    
    def is_drifted(self) -> bool:
        """Check if drift exceeds threshold."""
        drift, _ = self.compute_drift()
        return drift > self.threshold


# ============================================================================
# ANOMALY TRIGGER
# ============================================================================

class AnomalyTrigger:
    """
    Triggers model update based on anomaly detection patterns.
    
    Tracks anomaly counts and triggers when threshold exceeded.
    """
    
    def __init__(
        self,
        count_threshold: int = 10,
        window_minutes: int = 60,
        consecutive_threshold: int = 5
    ):
        self.count_threshold = count_threshold
        self.window_minutes = window_minutes
        self.consecutive_threshold = consecutive_threshold
        
        # Anomaly tracking
        self._anomaly_times: deque = deque()
        self._consecutive_count: int = 0
        self._last_was_anomaly: bool = False
        self._lock = threading.RLock()
    
    def record_result(self, is_anomaly: bool, score: float = 0.0):
        """
        Record an anomaly detection result.
        
        Args:
            is_anomaly: Whether the access was flagged as anomalous
            score: Anomaly score (negative = more anomalous)
        """
        with self._lock:
            now = datetime.now()
            
            if is_anomaly:
                self._anomaly_times.append(now)
                
                if self._last_was_anomaly:
                    self._consecutive_count += 1
                else:
                    self._consecutive_count = 1
            else:
                self._consecutive_count = 0
            
            self._last_was_anomaly = is_anomaly
            
            # Cleanup old entries
            cutoff = now - timedelta(minutes=self.window_minutes)
            while self._anomaly_times and self._anomaly_times[0] < cutoff:
                self._anomaly_times.popleft()
    
    def should_trigger(self) -> Tuple[bool, str]:
        """
        Check if model update should be triggered.
        
        Returns:
            (should_trigger, reason)
        """
        with self._lock:
            # Check consecutive threshold
            if self._consecutive_count >= self.consecutive_threshold:
                return True, f"Consecutive anomalies: {self._consecutive_count}"
            
            # Check window count threshold
            count = len(self._anomaly_times)
            if count >= self.count_threshold:
                return True, f"Anomaly count in window: {count}"
            
            return False, ""
    
    def get_stats(self) -> Dict[str, Any]:
        """Get anomaly trigger statistics."""
        with self._lock:
            return {
                'anomalies_in_window': len(self._anomaly_times),
                'consecutive_count': self._consecutive_count,
                'count_threshold': self.count_threshold,
                'consecutive_threshold': self.consecutive_threshold
            }


# ============================================================================
# PERFORMANCE TRIGGER
# ============================================================================

class PerformanceTrigger:
    """
    Triggers model update based on performance degradation.
    
    Monitors prediction accuracy, latency, and cache performance.
    """
    
    def __init__(
        self,
        accuracy_threshold: float = 0.2,
        latency_threshold_ms: float = 100.0,
        cache_miss_threshold: float = 0.5,
        window_size: int = 100
    ):
        self.accuracy_threshold = accuracy_threshold
        self.latency_threshold_ms = latency_threshold_ms
        self.cache_miss_threshold = cache_miss_threshold
        self.window_size = window_size
        
        # Performance tracking
        self._predictions: deque = deque(maxlen=window_size)
        self._latencies: deque = deque(maxlen=window_size)
        self._cache_hits: deque = deque(maxlen=window_size)
        
        # Baseline metrics
        self._baseline_accuracy: Optional[float] = None
        self._baseline_latency: Optional[float] = None
        
        self._lock = threading.RLock()
    
    def set_baseline(self, accuracy: float, latency: float):
        """Set baseline performance metrics."""
        with self._lock:
            self._baseline_accuracy = accuracy
            self._baseline_latency = latency
    
    def record_prediction(
        self,
        predicted: Any,
        actual: Any,
        latency_ms: float,
        cache_hit: bool
    ):
        """Record a prediction result."""
        with self._lock:
            # Record accuracy (1.0 if correct, 0.0 otherwise)
            is_correct = predicted == actual if actual is not None else 0.5
            self._predictions.append(float(is_correct) if isinstance(is_correct, bool) else is_correct)
            
            self._latencies.append(latency_ms)
            self._cache_hits.append(1.0 if cache_hit else 0.0)
    
    def should_trigger(self) -> Tuple[bool, str]:
        """Check if performance has degraded enough to trigger update."""
        with self._lock:
            if len(self._predictions) < self.window_size // 2:
                return False, "Insufficient data"
            
            # Calculate current metrics
            current_accuracy = np.mean(list(self._predictions))
            current_latency = np.mean(list(self._latencies))
            cache_miss_rate = 1.0 - np.mean(list(self._cache_hits))
            
            reasons = []
            
            # Check accuracy degradation
            if self._baseline_accuracy is not None:
                degradation = self._baseline_accuracy - current_accuracy
                if degradation > self.accuracy_threshold:
                    reasons.append(f"Accuracy degraded: {degradation:.2%}")
            
            # Check latency
            if current_latency > self.latency_threshold_ms:
                reasons.append(f"High latency: {current_latency:.1f}ms")
            
            # Check cache miss rate
            if cache_miss_rate > self.cache_miss_threshold:
                reasons.append(f"High cache miss rate: {cache_miss_rate:.2%}")
            
            if reasons:
                return True, "; ".join(reasons)
            
            return False, ""
    
    def get_stats(self) -> Dict[str, Any]:
        """Get performance statistics."""
        with self._lock:
            return {
                'current_accuracy': np.mean(list(self._predictions)) if self._predictions else None,
                'current_latency': np.mean(list(self._latencies)) if self._latencies else None,
                'cache_miss_rate': 1.0 - np.mean(list(self._cache_hits)) if self._cache_hits else None,
                'baseline_accuracy': self._baseline_accuracy,
                'sample_count': len(self._predictions)
            }


# ============================================================================
# SCHEDULED TRIGGER
# ============================================================================

class ScheduledTrigger:
    """
    Time-based model update trigger.
    
    Supports periodic updates with quiet hour preference.
    """
    
    def __init__(
        self,
        interval_hours: int = 24,
        min_samples: int = 100,
        quiet_hours: Tuple[int, int] = (2, 5)
    ):
        self.interval_hours = interval_hours
        self.min_samples = min_samples
        self.quiet_hours = quiet_hours
        
        self._last_update: Optional[datetime] = None
        self._samples_since_update: int = 0
        self._lock = threading.RLock()
    
    def record_sample(self):
        """Record a new training sample."""
        with self._lock:
            self._samples_since_update += 1
    
    def record_update(self):
        """Record that model was updated."""
        with self._lock:
            self._last_update = datetime.now()
            self._samples_since_update = 0
    
    def should_trigger(self) -> Tuple[bool, str]:
        """Check if scheduled update should trigger."""
        with self._lock:
            now = datetime.now()
            
            # Check if enough samples accumulated
            if self._samples_since_update < self.min_samples:
                return False, f"Insufficient samples: {self._samples_since_update}"
            
            # Check if interval has passed
            if self._last_update is not None:
                elapsed = now - self._last_update
                if elapsed < timedelta(hours=self.interval_hours):
                    return False, f"Interval not reached: {elapsed}"
            
            # Prefer quiet hours if possible
            current_hour = now.hour
            start_quiet, end_quiet = self.quiet_hours
            
            # In quiet hours - trigger immediately
            if start_quiet <= current_hour < end_quiet:
                return True, "Scheduled update (quiet hours)"
            
            # Not in quiet hours but interval exceeded by 50% - trigger anyway
            if self._last_update is not None:
                elapsed = now - self._last_update
                if elapsed > timedelta(hours=self.interval_hours * 1.5):
                    return True, "Scheduled update (overdue)"
            
            # First run without last_update
            if self._last_update is None:
                return True, "Initial scheduled update"
            
            return False, "Waiting for quiet hours"
    
    def get_stats(self) -> Dict[str, Any]:
        """Get scheduled trigger statistics."""
        with self._lock:
            return {
                'last_update': self._last_update.isoformat() if self._last_update else None,
                'samples_since_update': self._samples_since_update,
                'min_samples': self.min_samples,
                'interval_hours': self.interval_hours
            }


# ============================================================================
# MAIN TRIGGER MANAGER
# ============================================================================

class ModelUpdateTriggerManager:
    """
    Central manager for all model update triggers.
    
    Coordinates multiple trigger types and manages update cooldowns.
    
    Example:
        >>> manager = ModelUpdateTriggerManager(vault_path)
        >>> manager.on_update_triggered(lambda e: retrain_model())
        >>> 
        >>> # Record events
        >>> manager.record_access(features, is_anomaly=False)
        >>> manager.record_prediction(pred, actual, latency, cache_hit)
        >>> 
        >>> # Check if update needed
        >>> if manager.should_update():
        >>>     manager.execute_update()
    """
    
    def __init__(
        self,
        vault_path: Path,
        config: Optional[TriggerConfig] = None
    ):
        self.vault_path = Path(vault_path)
        self.config = config or TriggerConfig()
        
        # Initialize triggers
        self.drift_detector = DriftDetector(
            window_size=self.config.drift_window_size,
            threshold=self.config.drift_threshold
        )
        
        self.anomaly_trigger = AnomalyTrigger(
            count_threshold=self.config.anomaly_count_threshold,
            window_minutes=self.config.anomaly_window_minutes,
            consecutive_threshold=self.config.consecutive_anomaly_threshold
        )
        
        self.performance_trigger = PerformanceTrigger(
            accuracy_threshold=self.config.accuracy_degradation_threshold,
            latency_threshold_ms=self.config.latency_threshold_ms,
            cache_miss_threshold=self.config.cache_miss_rate_threshold
        )
        
        self.scheduled_trigger = ScheduledTrigger(
            interval_hours=self.config.scheduled_interval_hours,
            min_samples=self.config.min_samples_for_retrain,
            quiet_hours=self.config.quiet_hours
        )
        
        # Feature extractor for drift detection
        self.feature_extractor = FeatureExtractor()
        
        # Update tracking
        self._last_trigger_time: Optional[datetime] = None
        self._triggers_today: int = 0
        self._last_trigger_date: Optional[datetime] = None
        self._trigger_history: deque = deque(maxlen=100)
        
        # Callbacks
        self._update_callbacks: List[Callable[[TriggerEvent], None]] = []
        
        # Thread safety
        self._lock = threading.RLock()
        
        # Start monitoring thread
        self._start_monitoring()
    
    def set_reference_distribution(self, events: List[AccessEvent]):
        """Set reference distribution for drift detection."""
        if len(events) < 100:
            print("Warning: Insufficient events for reference distribution")
            return
        
        features = []
        for event in events:
            feat = self.feature_extractor.extract([event])
            features.append(feat)
        
        features_array = np.array(features)
        self.drift_detector.set_reference(features_array)
    
    def record_access(
        self,
        events: List[AccessEvent],
        is_anomaly: bool = False,
        anomaly_score: float = 0.0
    ):
        """
        Record an access event for trigger monitoring.
        
        Args:
            events: Access events (can be single event in list)
            is_anomaly: Whether access was flagged as anomalous
            anomaly_score: Anomaly score from detector
        """
        # Extract features
        features = self.feature_extractor.extract(events)
        features_array = np.array(features)
        
        # Update drift detector
        self.drift_detector.add_observation(features_array)
        
        # Update anomaly trigger
        self.anomaly_trigger.record_result(is_anomaly, anomaly_score)
        
        # Update scheduled trigger
        self.scheduled_trigger.record_sample()
    
    def record_prediction(
        self,
        predicted: Any,
        actual: Any,
        latency_ms: float,
        cache_hit: bool
    ):
        """Record a scatter parameter prediction result."""
        self.performance_trigger.record_prediction(
            predicted, actual, latency_ms, cache_hit
        )
    
    def should_update(self) -> Tuple[bool, Optional[TriggerEvent]]:
        """
        Check if model update should be triggered.
        
        Returns:
            (should_update, trigger_event)
        """
        with self._lock:
            now = datetime.now()
            
            # Check cooldown
            if self._last_trigger_time is not None:
                elapsed = now - self._last_trigger_time
                if elapsed < timedelta(minutes=self.config.cooldown_minutes):
                    return False, None
            
            # Check daily limit
            if self._last_trigger_date is not None:
                if self._last_trigger_date.date() == now.date():
                    if self._triggers_today >= self.config.max_triggers_per_day:
                        return False, None
            
            # Check each trigger in priority order
            
            # 1. Anomaly trigger (HIGH priority)
            should_trigger, reason = self.anomaly_trigger.should_trigger()
            if should_trigger:
                return True, TriggerEvent(
                    trigger_type=TriggerType.ANOMALY,
                    priority=TriggerPriority.HIGH,
                    timestamp=now,
                    reason=reason,
                    metrics=self.anomaly_trigger.get_stats()
                )
            
            # 2. Drift trigger (HIGH priority)
            if self.drift_detector.is_drifted():
                drift, per_feature = self.drift_detector.compute_drift()
                return True, TriggerEvent(
                    trigger_type=TriggerType.DRIFT,
                    priority=TriggerPriority.HIGH,
                    timestamp=now,
                    reason=f"Distribution drift detected: {drift:.4f}",
                    metrics={'drift': drift, 'per_feature': per_feature}
                )
            
            # 3. Performance trigger (MEDIUM priority)
            should_trigger, reason = self.performance_trigger.should_trigger()
            if should_trigger:
                return True, TriggerEvent(
                    trigger_type=TriggerType.PERFORMANCE,
                    priority=TriggerPriority.MEDIUM,
                    timestamp=now,
                    reason=reason,
                    metrics=self.performance_trigger.get_stats()
                )
            
            # 4. Scheduled trigger (LOW priority)
            should_trigger, reason = self.scheduled_trigger.should_trigger()
            if should_trigger:
                return True, TriggerEvent(
                    trigger_type=TriggerType.SCHEDULED,
                    priority=TriggerPriority.LOW,
                    timestamp=now,
                    reason=reason,
                    metrics=self.scheduled_trigger.get_stats()
                )
            
            return False, None
    
    def execute_update(self, event: TriggerEvent):
        """Execute model update and notify callbacks."""
        with self._lock:
            now = datetime.now()
            
            # Update tracking
            self._last_trigger_time = now
            
            if (self._last_trigger_date is None or 
                self._last_trigger_date.date() != now.date()):
                self._triggers_today = 1
                self._last_trigger_date = now
            else:
                self._triggers_today += 1
            
            self._trigger_history.append(event)
            
            # Update scheduled trigger
            self.scheduled_trigger.record_update()
        
        # Notify callbacks
        for callback in self._update_callbacks:
            try:
                callback(event)
            except Exception as e:
                print(f"Trigger callback error: {e}")
    
    def force_update(self, reason: str = "Manual trigger"):
        """Force immediate model update."""
        event = TriggerEvent(
            trigger_type=TriggerType.MANUAL,
            priority=TriggerPriority.CRITICAL,
            timestamp=datetime.now(),
            reason=reason,
            metrics={'forced': True}
        )
        self.execute_update(event)
    
    def on_update_triggered(self, callback: Callable[[TriggerEvent], None]):
        """Register callback for update triggers."""
        self._update_callbacks.append(callback)
    
    def get_stats(self) -> Dict[str, Any]:
        """Get comprehensive trigger statistics."""
        with self._lock:
            return {
                'drift': {
                    'current_drift': self.drift_detector.compute_drift()[0],
                    'is_drifted': self.drift_detector.is_drifted()
                },
                'anomaly': self.anomaly_trigger.get_stats(),
                'performance': self.performance_trigger.get_stats(),
                'scheduled': self.scheduled_trigger.get_stats(),
                'last_trigger': self._last_trigger_time.isoformat() if self._last_trigger_time else None,
                'triggers_today': self._triggers_today,
                'trigger_history_count': len(self._trigger_history)
            }
    
    def get_trigger_history(self) -> List[Dict[str, Any]]:
        """Get recent trigger history."""
        with self._lock:
            return [e.to_dict() for e in self._trigger_history]
    
    def _start_monitoring(self):
        """Start background monitoring thread."""
        def monitor_worker():
            while True:
                try:
                    time.sleep(self.config.drift_check_interval)
                    
                    should_update, event = self.should_update()
                    if should_update and event:
                        print(f"🔄 Model update triggered: {event.reason}")
                        self.execute_update(event)
                        
                except Exception as e:
                    print(f"Trigger monitoring error: {e}")
        
        thread = threading.Thread(target=monitor_worker, daemon=True)
        thread.start()


# ============================================================================
# CONVENIENCE FUNCTIONS
# ============================================================================

def create_trigger_manager(
    vault_path: Path,
    config: Optional[TriggerConfig] = None
) -> ModelUpdateTriggerManager:
    """Factory function to create a trigger manager."""
    return ModelUpdateTriggerManager(vault_path, config)
