"""
Adaptive Scatter Manager (Day 3 Integration)
==============================================

Unified manager that combines:
- Per-file scatter parameter optimization
- Parameter caching with intelligent invalidation
- Model update triggers based on access patterns
- FUSE filesystem integration

This is the main entry point for Day 3 ML integration, providing
a single interface for the FUSE layer to interact with.

Architecture:
┌─────────────────────────────────────────────────────────────┐
│                 ADAPTIVE SCATTER MANAGER                    │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│  ┌─────────────────┐   ┌─────────────────┐                │
│  │  SCATTER CACHE  │◄──│  TRIGGER MGR    │                │
│  │  (L1 + L2)      │   │  (Drift/Perf)   │                │
│  └────────┬────────┘   └────────┬────────┘                │
│           │                     │                          │
│           ▼                     ▼                          │
│  ┌─────────────────────────────────────────┐               │
│  │         ADAPTIVE SCATTER ENGINE         │               │
│  │         (LSTM Parameter Prediction)     │               │
│  └─────────────────────────────────────────┘               │
│           │                                                │
│           ▼                                                │
│  ┌─────────────────────────────────────────┐               │
│  │         FILE-SPECIFIC OPTIMIZER         │               │
│  │    (Sensitivity, Type, Access Pattern)  │               │
│  └─────────────────────────────────────────┘               │
│                                                             │
└─────────────────────────────────────────────────────────────┘

Copyright (c) 2025 ΣVAULT. All Rights Reserved.
Agents: @TENSOR @APEX @VELOCITY
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
import mimetypes

from .access_logger import AccessEvent, AccessLogger
from .adaptive_scatter import (
    AdaptiveScatterEngine, ScatterParameters, ScatterParameterOptimizer
)
from .scatter_cache import (
    ScatterParameterCache, CacheConfig, CacheEntry, InvalidationReason
)
from .model_triggers import (
    ModelUpdateTriggerManager, TriggerConfig, TriggerEvent, TriggerType
)
from .feature_extractor import FeatureExtractor
from .anomaly_detector import AnomalyDetector


# ============================================================================
# FILE CLASSIFICATION
# ============================================================================

class FileClassification:
    """
    Classifies files for sensitivity-based parameter selection.
    
    Determines scatter parameters based on:
    - File extension and MIME type
    - File location (system vs user)
    - Access patterns
    - Size characteristics
    """
    
    # Sensitivity levels by file type
    SENSITIVITY_MAP = {
        # High sensitivity - credentials, keys, configs
        'high': {
            '.key', '.pem', '.crt', '.cer', '.pfx', '.p12',
            '.env', '.credentials', '.secret', '.token',
            '.ssh', '.pgp', '.gpg', '.keystore',
            'id_rsa', 'id_ed25519', 'authorized_keys'
        },
        
        # Medium sensitivity - documents, databases
        'medium': {
            '.doc', '.docx', '.pdf', '.xls', '.xlsx', '.ppt', '.pptx',
            '.db', '.sqlite', '.sql', '.bak', '.dump',
            '.json', '.xml', '.yaml', '.yml', '.toml', '.ini'
        },
        
        # Low sensitivity - media, cache
        'low': {
            '.jpg', '.jpeg', '.png', '.gif', '.bmp', '.svg',
            '.mp3', '.mp4', '.avi', '.mov', '.wav',
            '.cache', '.tmp', '.log', '.swp'
        }
    }
    
    # Directory patterns for sensitivity
    SENSITIVE_PATHS = {
        'high': ['.ssh', '.gnupg', '.secrets', 'credentials', 'keys'],
        'medium': ['documents', 'data', 'backup', 'db'],
        'low': ['cache', 'temp', 'tmp', 'logs']
    }
    
    @classmethod
    def classify(cls, file_path: str, file_size: int = 0) -> str:
        """
        Classify file sensitivity level.
        
        Args:
            file_path: Path to file
            file_size: Optional file size for additional classification
            
        Returns:
            'low', 'medium', 'high', or 'critical'
        """
        path_lower = file_path.lower()
        ext = Path(file_path).suffix.lower()
        filename = Path(file_path).name.lower()
        
        # Check for critical indicators
        critical_indicators = ['private', 'secret', 'password', 'credential', 'api_key']
        if any(indicator in path_lower for indicator in critical_indicators):
            return 'critical'
        
        # Check extension-based sensitivity
        for level, extensions in cls.SENSITIVITY_MAP.items():
            if ext in extensions or filename in extensions:
                return level
        
        # Check path-based sensitivity
        path_parts = path_lower.split(os.sep)
        for level, patterns in cls.SENSITIVE_PATHS.items():
            if any(pattern in path_parts for pattern in patterns):
                return level
        
        # Size-based heuristic: very small files might be config/keys
        if file_size > 0 and file_size < 1024:  # < 1KB
            return 'medium'
        
        return 'medium'  # Default
    
    @classmethod
    def get_file_type(cls, file_path: str) -> str:
        """Get file type category."""
        mime_type, _ = mimetypes.guess_type(file_path)
        
        if mime_type:
            if mime_type.startswith('text'):
                return 'text'
            elif mime_type.startswith('image'):
                return 'image'
            elif mime_type.startswith('video'):
                return 'video'
            elif mime_type.startswith('audio'):
                return 'audio'
            elif 'application/json' in mime_type or 'application/xml' in mime_type:
                return 'data'
            elif 'application/octet-stream' in mime_type:
                return 'binary'
        
        ext = Path(file_path).suffix.lower()
        
        if ext in {'.py', '.js', '.ts', '.go', '.rs', '.java', '.c', '.cpp', '.h'}:
            return 'code'
        elif ext in {'.md', '.rst', '.txt'}:
            return 'text'
        elif ext in {'.db', '.sqlite', '.sql'}:
            return 'database'
        
        return 'unknown'


# ============================================================================
# ADAPTIVE SCATTER MANAGER
# ============================================================================

@dataclass
class ManagerConfig:
    """Configuration for Adaptive Scatter Manager."""
    
    # Cache settings
    cache_enabled: bool = True
    cache_l1_size: int = 1000
    cache_l1_ttl: int = 3600  # 1 hour
    cache_l2_enabled: bool = True
    cache_l2_ttl: int = 86400  # 24 hours
    
    # Model settings
    lstm_enabled: bool = True
    min_events_for_prediction: int = 5
    
    # Trigger settings
    triggers_enabled: bool = True
    drift_threshold: float = 0.1
    anomaly_trigger_count: int = 10
    scheduled_retrain_hours: int = 24
    
    # Optimization settings
    sensitivity_adjustment: bool = True
    system_load_adjustment: bool = True
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            'cache_enabled': self.cache_enabled,
            'lstm_enabled': self.lstm_enabled,
            'triggers_enabled': self.triggers_enabled,
            'sensitivity_adjustment': self.sensitivity_adjustment
        }


class AdaptiveScatterManager:
    """
    Unified manager for adaptive scatter parameter optimization.
    
    This is the main interface for FUSE integration, providing:
    - Get optimal parameters for a file (with caching)
    - Record access events for model training
    - Monitor for model retraining triggers
    - Manual training and status APIs
    
    Example:
        >>> manager = AdaptiveScatterManager(vault_path)
        >>> 
        >>> # Get parameters for a file
        >>> params = manager.get_parameters(
        ...     file_path="/secret/keys/api.key",
        ...     recent_events=events
        ... )
        >>> 
        >>> # Record access for learning
        >>> manager.record_access(event, was_anomaly=False)
        >>> 
        >>> # Check status
        >>> status = manager.get_status()
    """
    
    def __init__(
        self,
        vault_path: Path,
        config: Optional[ManagerConfig] = None
    ):
        self.vault_path = Path(vault_path)
        self.config = config or ManagerConfig()
        
        # Initialize components
        self._init_cache()
        self._init_engine()
        self._init_triggers()
        
        # Access logging for parameter optimization
        self.access_logger = AccessLogger(vault_path)
        self.feature_extractor = FeatureExtractor()
        
        # File access tracking for per-file optimization
        self._file_access_history: Dict[str, List[float]] = {}
        self._file_lock = threading.RLock()
        
        # Statistics
        self._stats = {
            'cache_hits': 0,
            'cache_misses': 0,
            'predictions_made': 0,
            'heuristics_used': 0,
            'triggers_fired': 0
        }
        
        # Register trigger callback
        if self.trigger_manager:
            self.trigger_manager.on_update_triggered(self._on_model_update)
    
    def _init_cache(self):
        """Initialize parameter cache."""
        if self.config.cache_enabled:
            cache_config = CacheConfig(
                l1_max_entries=self.config.cache_l1_size,
                l1_ttl_seconds=self.config.cache_l1_ttl,
                l2_enabled=self.config.cache_l2_enabled,
                l2_ttl_seconds=self.config.cache_l2_ttl
            )
            self.cache = ScatterParameterCache(self.vault_path, cache_config)
            
            # Register invalidation callback
            self.cache.register_invalidation_callback(self._on_cache_invalidation)
        else:
            self.cache = None
    
    def _init_engine(self):
        """Initialize scatter engine."""
        if self.config.lstm_enabled:
            self.engine = AdaptiveScatterEngine(self.vault_path)
            self.optimizer = ScatterParameterOptimizer(self.vault_path)
        else:
            self.engine = None
            self.optimizer = None
    
    def _init_triggers(self):
        """Initialize model update triggers."""
        if self.config.triggers_enabled:
            trigger_config = TriggerConfig(
                drift_threshold=self.config.drift_threshold,
                anomaly_count_threshold=self.config.anomaly_trigger_count,
                scheduled_interval_hours=self.config.scheduled_retrain_hours
            )
            self.trigger_manager = ModelUpdateTriggerManager(
                self.vault_path, trigger_config
            )
        else:
            self.trigger_manager = None
    
    def get_parameters(
        self,
        file_path: str,
        recent_events: Optional[List[AccessEvent]] = None,
        file_size: int = 0,
        system_load: float = 0.5,
        force_recompute: bool = False
    ) -> ScatterParameters:
        """
        Get optimal scatter parameters for a file.
        
        Checks cache first, then computes if needed using:
        1. LSTM model prediction (if trained)
        2. Heuristic fallback
        3. Sensitivity adjustments
        4. System load adjustments
        
        Args:
            file_path: Path to file
            recent_events: Recent access events for the file
            file_size: File size in bytes
            system_load: Current system load [0, 1]
            force_recompute: Skip cache and recompute
            
        Returns:
            Optimal ScatterParameters
        """
        start_time = time.time()
        
        # Check cache first (unless forced)
        if self.cache and not force_recompute:
            cached = self.cache.get(file_path)
            if cached:
                self._stats['cache_hits'] += 1
                return cached
        
        self._stats['cache_misses'] += 1
        
        # Get file classification
        sensitivity = FileClassification.classify(file_path, file_size)
        file_type = FileClassification.get_file_type(file_path)
        
        # Get events if not provided
        if recent_events is None:
            recent_events = self._get_file_events(file_path)
        
        # Compute parameters
        params = self._compute_parameters(
            file_path=file_path,
            events=recent_events,
            sensitivity=sensitivity,
            system_load=system_load
        )
        
        # Cache the result
        if self.cache:
            access_times = [e.timestamp.timestamp() for e in recent_events] if recent_events else None
            self.cache.put(file_path, params, access_times)
        
        # Record prediction for performance tracking
        if self.trigger_manager:
            latency_ms = (time.time() - start_time) * 1000
            cache_hit = False  # We missed the cache
            self.trigger_manager.record_prediction(
                params.scatter_depth, None, latency_ms, cache_hit
            )
        
        return params
    
    def _compute_parameters(
        self,
        file_path: str,
        events: List[AccessEvent],
        sensitivity: str,
        system_load: float
    ) -> ScatterParameters:
        """Compute scatter parameters using available methods."""
        
        # Try LSTM model first
        if self.optimizer and events and len(events) >= self.config.min_events_for_prediction:
            try:
                params = self.optimizer.optimize(
                    events=events,
                    file_sensitivity=sensitivity,
                    system_load=system_load if self.config.system_load_adjustment else 0.5
                )
                self._stats['predictions_made'] += 1
                return params
            except Exception as e:
                print(f"LSTM prediction failed: {e}")
        
        # Fall back to heuristics
        self._stats['heuristics_used'] += 1
        return self._heuristic_parameters(sensitivity, len(events), system_load)
    
    def _heuristic_parameters(
        self,
        sensitivity: str,
        event_count: int,
        system_load: float
    ) -> ScatterParameters:
        """Calculate parameters using heuristics."""
        
        # Base parameters by sensitivity
        base_params = {
            'critical': {'entropy': 0.8, 'scatter': 7, 'phase': 3.0},
            'high': {'entropy': 0.7, 'scatter': 6, 'phase': 2.0},
            'medium': {'entropy': 0.5, 'scatter': 4, 'phase': 1.0},
            'low': {'entropy': 0.3, 'scatter': 2, 'phase': 0.5}
        }
        
        base = base_params.get(sensitivity, base_params['medium'])
        
        # Adjust for access frequency
        if event_count > 100:
            # Frequently accessed - optimize for speed
            base['scatter'] = max(1, base['scatter'] - 1)
        elif event_count < 10:
            # Rarely accessed - optimize for security
            base['scatter'] = min(8, base['scatter'] + 1)
        
        # Adjust for system load
        if self.config.system_load_adjustment and system_load > 0.8:
            base['scatter'] = max(1, base['scatter'] - 2)
        
        return ScatterParameters(
            entropy_ratio=base['entropy'],
            scatter_depth=base['scatter'],
            temporal_prime=15485863,
            phase_scale=base['phase'],
            confidence=0.6  # Medium confidence for heuristics
        )
    
    def _get_file_events(self, file_path: str, limit: int = 50) -> List[AccessEvent]:
        """Get recent access events for a file."""
        path_hash = hashlib.sha256(file_path.encode()).hexdigest()
        
        try:
            all_events = self.access_logger.get_recent_events(
                window=timedelta(hours=24)
            )
            
            # Filter for this file
            file_events = [
                e for e in all_events
                if e.file_path_hash == path_hash
            ]
            
            return file_events[-limit:]
        except Exception:
            return []
    
    def record_access(
        self,
        event: AccessEvent,
        was_anomaly: bool = False,
        anomaly_score: float = 0.0
    ):
        """
        Record an access event for model training and trigger monitoring.
        
        Args:
            event: Access event to record
            was_anomaly: Whether the access was flagged as anomalous
            anomaly_score: Anomaly score from detector
        """
        # Track file access history for cache invalidation
        with self._file_lock:
            file_hash = event.file_path_hash
            if file_hash not in self._file_access_history:
                self._file_access_history[file_hash] = []
            
            self._file_access_history[file_hash].append(
                event.timestamp.timestamp()
            )
            
            # Keep only last 100 accesses
            self._file_access_history[file_hash] = \
                self._file_access_history[file_hash][-100:]
        
        # Record for triggers
        if self.trigger_manager:
            self.trigger_manager.record_access(
                [event],
                is_anomaly=was_anomaly,
                anomaly_score=anomaly_score
            )
        
        # Check for pattern changes that should invalidate cache
        if self.cache:
            current_times = self._file_access_history.get(event.file_path_hash, [])
            # Note: We don't have the original path, but cache uses hash internally
            # This is a simplified check - in production, maintain path mapping
    
    def train_model(
        self,
        events: Optional[List[AccessEvent]] = None,
        min_events: int = 100
    ) -> bool:
        """
        Train or retrain the scatter prediction model.
        
        Args:
            events: Events to train on (uses recent events if not provided)
            min_events: Minimum events required for training
            
        Returns:
            True if training succeeded
        """
        if not self.engine:
            return False
        
        # Get events if not provided
        if events is None:
            events = self.access_logger.get_recent_events(
                window=timedelta(days=7)
            )
        
        if len(events) < min_events:
            print(f"Insufficient events for training: {len(events)} < {min_events}")
            return False
        
        try:
            # Generate training samples with heuristic labels
            for i in range(0, len(events) - 50, 10):
                event_window = events[i:i+50]
                if len(event_window) < 50:
                    continue
                
                # Use heuristic parameters as labels (bootstrap training)
                avg_size = sum(e.bytes_accessed for e in event_window) / len(event_window)
                
                # Simple sensitivity heuristic
                sensitivity = 'medium'
                if avg_size < 1000:
                    sensitivity = 'high'
                elif avg_size > 100000:
                    sensitivity = 'low'
                
                optimal_params = self._heuristic_parameters(sensitivity, len(event_window), 0.5)
                self.engine.add_training_sample(event_window, optimal_params)
            
            # Force training
            self.engine.force_retrain()
            
            # Set reference distribution for triggers
            if self.trigger_manager:
                self.trigger_manager.set_reference_distribution(events)
            
            # Invalidate cache on model retrain
            if self.cache:
                self.cache.invalidate_on_model_retrain()
            
            return True
            
        except Exception as e:
            print(f"Model training failed: {e}")
            return False
    
    def _on_model_update(self, event: TriggerEvent):
        """Callback when model update is triggered."""
        self._stats['triggers_fired'] += 1
        print(f"📊 Model update triggered: {event.trigger_type.name} - {event.reason}")
        
        # Perform retraining
        success = self.train_model()
        
        if success:
            print("✅ Model retrained successfully")
        else:
            print("⚠️ Model retraining failed or skipped")
    
    def _on_cache_invalidation(self, file_path: str, reason: InvalidationReason):
        """Callback when cache entry is invalidated."""
        print(f"🗑️ Cache invalidated for {file_path[:20]}...: {reason.value}")
    
    def invalidate_file(self, file_path: str):
        """Manually invalidate cache for a file."""
        if self.cache:
            self.cache.invalidate(file_path, InvalidationReason.MANUAL)
    
    def get_status(self) -> Dict[str, Any]:
        """Get comprehensive manager status."""
        status = {
            'config': self.config.to_dict(),
            'statistics': self._stats.copy()
        }
        
        if self.cache:
            status['cache'] = self.cache.get_stats()
        
        if self.engine:
            status['engine'] = self.engine.get_model_stats()
        
        if self.trigger_manager:
            status['triggers'] = self.trigger_manager.get_stats()
        
        return status
    
    def get_cache_stats(self) -> Dict[str, Any]:
        """Get cache statistics."""
        if self.cache:
            return self.cache.get_stats()
        return {'enabled': False}
    
    def get_trigger_history(self) -> List[Dict[str, Any]]:
        """Get trigger event history."""
        if self.trigger_manager:
            return self.trigger_manager.get_trigger_history()
        return []


# ============================================================================
# CONVENIENCE FUNCTIONS
# ============================================================================

def create_scatter_manager(
    vault_path: Path,
    config: Optional[ManagerConfig] = None
) -> AdaptiveScatterManager:
    """Factory function to create an adaptive scatter manager."""
    return AdaptiveScatterManager(vault_path, config)


def get_file_sensitivity(file_path: str, file_size: int = 0) -> str:
    """Convenience function to get file sensitivity level."""
    return FileClassification.classify(file_path, file_size)


def get_file_type(file_path: str) -> str:
    """Convenience function to get file type."""
    return FileClassification.get_file_type(file_path)
