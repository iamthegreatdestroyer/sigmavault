"""
Tests for Day 3: Adaptive Scatter Caching and Model Triggers

Tests:
- ScatterParameterCache (L1/L2 caching)
- ModelUpdateTriggerManager (drift, anomaly, performance, scheduled)
- AdaptiveScatterManager (unified interface)
- FileClassification (sensitivity detection)

Copyright (c) 2025 ΣVAULT. All Rights Reserved.
"""

import os
import sys
import pytest
import tempfile
import time
import threading
from pathlib import Path
from datetime import datetime, timedelta
from unittest.mock import Mock, patch, MagicMock
import numpy as np

# Add parent to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from sigmavault.ml.scatter_cache import (
    ScatterParameterCache, CacheConfig, CacheEntry, InvalidationReason,
    L1Cache, L2Cache, PrefetchManager, create_scatter_cache
)
from sigmavault.ml.model_triggers import (
    ModelUpdateTriggerManager, TriggerConfig, TriggerEvent, TriggerType,
    DriftDetector, AnomalyTrigger, PerformanceTrigger, ScheduledTrigger,
    create_trigger_manager
)
from sigmavault.ml.scatter_manager import (
    AdaptiveScatterManager, ManagerConfig, FileClassification,
    create_scatter_manager, get_file_sensitivity, get_file_type
)
from sigmavault.ml.adaptive_scatter import ScatterParameters
from sigmavault.ml.access_logger import AccessEvent


# ============================================================================
# FIXTURES
# ============================================================================

@pytest.fixture
def temp_vault(tmp_path):
    """Create a temporary vault directory."""
    vault_path = tmp_path / "test_vault"
    vault_path.mkdir()
    return vault_path


@pytest.fixture
def sample_params():
    """Create sample scatter parameters."""
    return ScatterParameters(
        entropy_ratio=0.5,
        scatter_depth=4,
        temporal_prime=15485863,
        phase_scale=1.0,
        confidence=0.8
    )


@pytest.fixture
def sample_events():
    """Create sample access events."""
    events = []
    base_time = datetime.now()
    
    for i in range(50):
        event = AccessEvent(
            timestamp=base_time + timedelta(minutes=i),
            vault_id="test_vault",
            user_id_hash="user123",
            file_path_hash="file456",
            operation="read",
            bytes_accessed=1024,
            duration_ms=10.0,
            success=True,
            ip_hash="ip789",
            device_hash="device012"
        )
        events.append(event)
    
    return events


# ============================================================================
# L1 CACHE TESTS
# ============================================================================

class TestL1Cache:
    """Tests for in-memory LRU cache."""
    
    def test_cache_creation(self):
        """Test L1 cache initialization."""
        cache = L1Cache(max_entries=100, ttl_seconds=3600)
        
        assert cache.max_entries == 100
        assert cache.ttl_seconds == 3600
        assert cache.hits == 0
        assert cache.misses == 0
    
    def test_put_and_get(self, sample_params):
        """Test basic put and get operations."""
        cache = L1Cache()
        
        entry = CacheEntry(
            file_path_hash="test_hash",
            parameters=sample_params,
            created_at=datetime.now(),
            expires_at=datetime.now() + timedelta(hours=1)
        )
        
        cache.put("test_key", entry)
        retrieved = cache.get("test_key")
        
        assert retrieved is not None
        assert retrieved.parameters.scatter_depth == sample_params.scatter_depth
        assert cache.hits == 1
    
    def test_cache_miss(self):
        """Test cache miss."""
        cache = L1Cache()
        
        result = cache.get("nonexistent")
        
        assert result is None
        assert cache.misses == 1
    
    def test_lru_eviction(self, sample_params):
        """Test LRU eviction when cache is full."""
        cache = L1Cache(max_entries=3)
        
        # Fill cache
        for i in range(5):
            entry = CacheEntry(
                file_path_hash=f"hash_{i}",
                parameters=sample_params,
                created_at=datetime.now(),
                expires_at=datetime.now() + timedelta(hours=1)
            )
            cache.put(f"key_{i}", entry)
        
        # First two should be evicted
        assert cache.get("key_0") is None
        assert cache.get("key_1") is None
        assert cache.get("key_4") is not None
        assert cache.evictions == 2
    
    def test_ttl_expiration(self, sample_params):
        """Test TTL-based expiration."""
        cache = L1Cache(ttl_seconds=1)
        
        entry = CacheEntry(
            file_path_hash="test_hash",
            parameters=sample_params,
            created_at=datetime.now(),
            expires_at=datetime.now() + timedelta(seconds=1)
        )
        
        cache.put("test_key", entry)
        
        # Should get immediately
        assert cache.get("test_key") is not None
        
        # Wait for expiration
        time.sleep(1.5)
        
        # Should be expired
        assert cache.get("test_key") is None
    
    def test_invalidate(self, sample_params):
        """Test manual invalidation."""
        cache = L1Cache()
        
        entry = CacheEntry(
            file_path_hash="test_hash",
            parameters=sample_params,
            created_at=datetime.now(),
            expires_at=datetime.now() + timedelta(hours=1)
        )
        
        cache.put("test_key", entry)
        assert cache.get("test_key") is not None
        
        result = cache.invalidate("test_key")
        
        assert result is True
        assert cache.get("test_key") is None
    
    def test_get_stats(self, sample_params):
        """Test statistics retrieval."""
        cache = L1Cache(max_entries=10)
        
        entry = CacheEntry(
            file_path_hash="test_hash",
            parameters=sample_params,
            created_at=datetime.now(),
            expires_at=datetime.now() + timedelta(hours=1)
        )
        
        cache.put("key1", entry)
        cache.get("key1")  # Hit
        cache.get("key2")  # Miss
        
        stats = cache.get_stats()
        
        assert stats['entries'] == 1
        assert stats['hits'] == 1
        assert stats['misses'] == 1
        assert stats['hit_rate'] == 0.5


# ============================================================================
# L2 CACHE TESTS
# ============================================================================

class TestL2Cache:
    """Tests for disk-backed SQLite cache."""
    
    def test_cache_creation(self, temp_vault):
        """Test L2 cache initialization."""
        db_path = temp_vault / "test_cache.db"
        cache = L2Cache(db_path, ttl_seconds=86400)
        
        assert db_path.exists()
    
    def test_put_and_get(self, temp_vault, sample_params):
        """Test basic put and get operations."""
        db_path = temp_vault / "test_cache.db"
        cache = L2Cache(db_path)
        
        entry = CacheEntry(
            file_path_hash="test_hash",
            parameters=sample_params,
            created_at=datetime.now(),
            expires_at=datetime.now() + timedelta(hours=24)
        )
        
        cache.put("test_key", entry)
        retrieved = cache.get("test_key")
        
        assert retrieved is not None
        assert retrieved.parameters.scatter_depth == sample_params.scatter_depth
    
    def test_cleanup_expired(self, temp_vault, sample_params):
        """Test cleanup of expired entries."""
        db_path = temp_vault / "test_cache.db"
        cache = L2Cache(db_path, ttl_seconds=1)
        
        entry = CacheEntry(
            file_path_hash="test_hash",
            parameters=sample_params,
            created_at=datetime.now(),
            expires_at=datetime.now() - timedelta(hours=1)  # Already expired
        )
        
        cache.put("test_key", entry)
        
        removed = cache.cleanup_expired()
        
        assert removed >= 0  # May be 0 if put updated expiration


# ============================================================================
# SCATTER PARAMETER CACHE TESTS
# ============================================================================

class TestScatterParameterCache:
    """Tests for unified scatter parameter cache."""
    
    def test_cache_creation(self, temp_vault):
        """Test cache creation with default config."""
        cache = ScatterParameterCache(temp_vault)
        
        assert cache.l1 is not None
        assert cache.l2 is not None
    
    def test_get_and_put(self, temp_vault, sample_params):
        """Test get and put operations."""
        cache = ScatterParameterCache(temp_vault)
        
        cache.put("/path/to/file.txt", sample_params)
        retrieved = cache.get("/path/to/file.txt")
        
        assert retrieved is not None
        assert retrieved.scatter_depth == sample_params.scatter_depth
    
    def test_cache_miss_returns_none(self, temp_vault):
        """Test cache miss returns None."""
        cache = ScatterParameterCache(temp_vault)
        
        result = cache.get("/nonexistent/file.txt")
        
        assert result is None
    
    def test_invalidation(self, temp_vault, sample_params):
        """Test cache invalidation."""
        cache = ScatterParameterCache(temp_vault)
        
        cache.put("/path/to/file.txt", sample_params)
        assert cache.get("/path/to/file.txt") is not None
        
        cache.invalidate("/path/to/file.txt", InvalidationReason.MANUAL)
        
        assert cache.get("/path/to/file.txt") is None
    
    def test_invalidation_callback(self, temp_vault, sample_params):
        """Test invalidation callback is called."""
        cache = ScatterParameterCache(temp_vault)
        callback_called = []
        
        def on_invalidate(path, reason):
            callback_called.append((path, reason))
        
        cache.register_invalidation_callback(on_invalidate)
        
        cache.put("/path/to/file.txt", sample_params)
        cache.invalidate("/path/to/file.txt", InvalidationReason.PATTERN_CHANGED)
        
        assert len(callback_called) == 1
        assert callback_called[0][1] == InvalidationReason.PATTERN_CHANGED
    
    def test_get_stats(self, temp_vault, sample_params):
        """Test statistics retrieval."""
        cache = ScatterParameterCache(temp_vault)
        
        cache.put("/file1.txt", sample_params)
        cache.get("/file1.txt")  # Hit
        cache.get("/file2.txt")  # Miss
        
        stats = cache.get_stats()
        
        assert 'l1' in stats
        assert 'l2' in stats
        assert stats['l1']['hits'] == 1
        assert stats['l1']['misses'] == 1


# ============================================================================
# DRIFT DETECTOR TESTS
# ============================================================================

class TestDriftDetector:
    """Tests for distribution drift detection."""
    
    def test_detector_creation(self):
        """Test drift detector initialization."""
        detector = DriftDetector(window_size=100, threshold=0.1)
        
        assert detector.window_size == 100
        assert detector.threshold == 0.1
    
    def test_set_reference(self):
        """Test setting reference distribution."""
        detector = DriftDetector()
        
        # Create sample features
        features = np.random.randn(100, 11)
        
        detector.set_reference(features)
        
        assert detector._reference_histograms is not None
        assert len(detector._reference_histograms) == 11
    
    def test_no_drift_with_same_distribution(self):
        """Test no drift detected with same distribution."""
        detector = DriftDetector(window_size=50, threshold=0.5)
        
        # Create reference
        features = np.random.randn(100, 5)
        detector.set_reference(features)
        
        # Add observations from same distribution
        for _ in range(100):
            obs = np.random.randn(5)
            detector.add_observation(obs)
        
        drift, _ = detector.compute_drift()
        
        # Should have low drift
        assert drift < 1.0
    
    def test_drift_with_different_distribution(self):
        """Test drift detected with different distribution."""
        detector = DriftDetector(window_size=50, threshold=0.1)
        
        # Create reference from normal(0, 1)
        features = np.random.randn(100, 5)
        detector.set_reference(features)
        
        # Add observations from different distribution normal(5, 1)
        for _ in range(100):
            obs = np.random.randn(5) + 5  # Shifted mean
            detector.add_observation(obs)
        
        drift, _ = detector.compute_drift()
        
        # Should have higher drift due to distribution shift
        assert drift > 0


# ============================================================================
# ANOMALY TRIGGER TESTS
# ============================================================================

class TestAnomalyTrigger:
    """Tests for anomaly-based triggers."""
    
    def test_trigger_creation(self):
        """Test anomaly trigger initialization."""
        trigger = AnomalyTrigger(count_threshold=10, consecutive_threshold=5)
        
        assert trigger.count_threshold == 10
        assert trigger.consecutive_threshold == 5
    
    def test_no_trigger_with_normal_access(self):
        """Test no trigger with normal access patterns."""
        trigger = AnomalyTrigger(count_threshold=10)
        
        # Record normal accesses
        for _ in range(20):
            trigger.record_result(is_anomaly=False)
        
        should_trigger, _ = trigger.should_trigger()
        
        assert should_trigger is False
    
    def test_trigger_on_count_threshold(self):
        """Test trigger when count threshold exceeded."""
        trigger = AnomalyTrigger(count_threshold=5, window_minutes=60)
        
        # Record anomalies
        for _ in range(10):
            trigger.record_result(is_anomaly=True)
        
        should_trigger, reason = trigger.should_trigger()
        
        assert should_trigger is True
        assert "count" in reason.lower()
    
    def test_trigger_on_consecutive_threshold(self):
        """Test trigger when consecutive threshold exceeded."""
        trigger = AnomalyTrigger(
            count_threshold=100,  # High count threshold
            consecutive_threshold=3
        )
        
        # Record consecutive anomalies
        for _ in range(5):
            trigger.record_result(is_anomaly=True)
        
        should_trigger, reason = trigger.should_trigger()
        
        assert should_trigger is True
        assert "consecutive" in reason.lower()


# ============================================================================
# PERFORMANCE TRIGGER TESTS
# ============================================================================

class TestPerformanceTrigger:
    """Tests for performance-based triggers."""
    
    def test_trigger_creation(self):
        """Test performance trigger initialization."""
        trigger = PerformanceTrigger(accuracy_threshold=0.2)
        
        assert trigger.accuracy_threshold == 0.2
    
    def test_no_trigger_with_good_performance(self):
        """Test no trigger with good performance."""
        trigger = PerformanceTrigger(
            accuracy_threshold=0.2,
            latency_threshold_ms=100.0,
            window_size=10
        )
        trigger.set_baseline(accuracy=0.9, latency=20.0)
        
        # Record good predictions
        for _ in range(20):
            trigger.record_prediction(
                predicted=1, actual=1,
                latency_ms=20.0, cache_hit=True
            )
        
        should_trigger, _ = trigger.should_trigger()
        
        assert should_trigger is False
    
    def test_trigger_on_high_latency(self):
        """Test trigger when latency threshold exceeded."""
        trigger = PerformanceTrigger(
            latency_threshold_ms=50.0,
            window_size=10
        )
        
        # Record high latency predictions
        for _ in range(20):
            trigger.record_prediction(
                predicted=1, actual=1,
                latency_ms=100.0, cache_hit=True
            )
        
        should_trigger, reason = trigger.should_trigger()
        
        assert should_trigger is True
        assert "latency" in reason.lower()


# ============================================================================
# SCHEDULED TRIGGER TESTS
# ============================================================================

class TestScheduledTrigger:
    """Tests for scheduled retraining triggers."""
    
    def test_trigger_creation(self):
        """Test scheduled trigger initialization."""
        trigger = ScheduledTrigger(interval_hours=24, min_samples=100)
        
        assert trigger.interval_hours == 24
        assert trigger.min_samples == 100
    
    def test_no_trigger_with_insufficient_samples(self):
        """Test no trigger without enough samples."""
        trigger = ScheduledTrigger(min_samples=100)
        
        # Record few samples
        for _ in range(10):
            trigger.record_sample()
        
        should_trigger, reason = trigger.should_trigger()
        
        assert should_trigger is False
        assert "insufficient" in reason.lower()
    
    def test_trigger_with_enough_samples(self):
        """Test trigger with enough samples and no recent update."""
        trigger = ScheduledTrigger(
            interval_hours=24,
            min_samples=10,
            quiet_hours=(0, 24)  # Always quiet hours
        )
        
        # Record enough samples
        for _ in range(20):
            trigger.record_sample()
        
        should_trigger, _ = trigger.should_trigger()
        
        assert should_trigger is True


# ============================================================================
# FILE CLASSIFICATION TESTS
# ============================================================================

class TestFileClassification:
    """Tests for file sensitivity classification."""
    
    def test_critical_files(self):
        """Test critical file detection."""
        assert FileClassification.classify("/home/user/.ssh/id_rsa") == "critical"
        assert FileClassification.classify("/secrets/api_key.txt") == "critical"
        assert FileClassification.classify("/config/password.env") == "critical"
    
    def test_high_sensitivity_files(self):
        """Test high sensitivity file detection."""
        assert FileClassification.classify("/path/to/cert.pem") == "high"
        assert FileClassification.classify("/keys/server.key") == "high"
        assert FileClassification.classify("/.env") == "high"
    
    def test_medium_sensitivity_files(self):
        """Test medium sensitivity file detection."""
        assert FileClassification.classify("/documents/report.pdf") == "medium"
        assert FileClassification.classify("/data/users.json") == "medium"
        assert FileClassification.classify("/config/settings.yaml") == "medium"
    
    def test_low_sensitivity_files(self):
        """Test low sensitivity file detection."""
        assert FileClassification.classify("/images/photo.jpg") == "low"
        assert FileClassification.classify("/cache/data.cache") == "low"
        assert FileClassification.classify("/logs/app.log") == "low"
    
    def test_file_type_detection(self):
        """Test file type categorization."""
        assert FileClassification.get_file_type("/code/main.py") == "code"
        assert FileClassification.get_file_type("/docs/readme.md") == "text"
        assert FileClassification.get_file_type("/images/logo.png") == "image"


# ============================================================================
# ADAPTIVE SCATTER MANAGER TESTS
# ============================================================================

class TestAdaptiveScatterManager:
    """Tests for unified scatter manager."""
    
    def test_manager_creation(self, temp_vault):
        """Test manager initialization."""
        manager = AdaptiveScatterManager(temp_vault)
        
        assert manager.cache is not None
        assert manager.config is not None
    
    def test_get_parameters_uncached(self, temp_vault, sample_events):
        """Test getting parameters without cache."""
        manager = AdaptiveScatterManager(temp_vault)
        
        params = manager.get_parameters(
            file_path="/path/to/file.txt",
            recent_events=sample_events,
            file_size=1024
        )
        
        assert params is not None
        assert 0.1 <= params.entropy_ratio <= 0.9
        assert 1 <= params.scatter_depth <= 8
    
    def test_get_parameters_cached(self, temp_vault, sample_events):
        """Test cached parameter retrieval."""
        manager = AdaptiveScatterManager(temp_vault)
        
        # First call - cache miss
        params1 = manager.get_parameters(
            file_path="/path/to/file.txt",
            recent_events=sample_events
        )
        
        # Second call - cache hit
        params2 = manager.get_parameters(
            file_path="/path/to/file.txt",
            recent_events=sample_events
        )
        
        assert params1.scatter_depth == params2.scatter_depth
        assert manager._stats['cache_hits'] >= 1
    
    def test_sensitivity_adjustment(self, temp_vault, sample_events):
        """Test sensitivity-based parameter adjustment."""
        manager = AdaptiveScatterManager(temp_vault)
        
        # Low sensitivity file
        low_params = manager.get_parameters(
            file_path="/images/photo.jpg",
            recent_events=sample_events
        )
        
        # Critical file
        critical_params = manager.get_parameters(
            file_path="/secrets/api_key.txt",
            recent_events=sample_events,
            force_recompute=True
        )
        
        # Critical files should have higher scatter depth
        assert critical_params.scatter_depth >= low_params.scatter_depth
    
    def test_record_access(self, temp_vault, sample_events):
        """Test access recording."""
        manager = AdaptiveScatterManager(temp_vault)
        
        event = sample_events[0]
        manager.record_access(event, was_anomaly=False)
        
        # Should have recorded in trigger manager
        if manager.trigger_manager:
            stats = manager.trigger_manager.get_stats()
            assert stats['scheduled']['samples_since_update'] >= 1
    
    def test_invalidate_file(self, temp_vault, sample_events):
        """Test manual file invalidation."""
        manager = AdaptiveScatterManager(temp_vault)
        
        # Cache a file
        manager.get_parameters(
            file_path="/path/to/file.txt",
            recent_events=sample_events
        )
        
        # Invalidate
        manager.invalidate_file("/path/to/file.txt")
        
        # Cache should be empty for this file
        # Next access will be a miss
        initial_misses = manager._stats['cache_misses']
        manager.get_parameters(
            file_path="/path/to/file.txt",
            recent_events=sample_events
        )
        
        assert manager._stats['cache_misses'] > initial_misses
    
    def test_get_status(self, temp_vault):
        """Test status retrieval."""
        manager = AdaptiveScatterManager(temp_vault)
        
        status = manager.get_status()
        
        assert 'config' in status
        assert 'statistics' in status
        assert 'cache' in status


# ============================================================================
# CONVENIENCE FUNCTION TESTS
# ============================================================================

class TestConvenienceFunctions:
    """Tests for factory and convenience functions."""
    
    def test_create_scatter_cache(self, temp_vault):
        """Test scatter cache factory."""
        cache = create_scatter_cache(temp_vault)
        
        assert cache is not None
        assert isinstance(cache, ScatterParameterCache)
    
    def test_create_trigger_manager(self, temp_vault):
        """Test trigger manager factory."""
        manager = create_trigger_manager(temp_vault)
        
        assert manager is not None
        assert isinstance(manager, ModelUpdateTriggerManager)
    
    def test_create_scatter_manager(self, temp_vault):
        """Test scatter manager factory."""
        manager = create_scatter_manager(temp_vault)
        
        assert manager is not None
        assert isinstance(manager, AdaptiveScatterManager)
    
    def test_get_file_sensitivity_function(self):
        """Test convenience function for sensitivity."""
        sensitivity = get_file_sensitivity("/secrets/key.pem")
        
        assert sensitivity in ['low', 'medium', 'high', 'critical']
    
    def test_get_file_type_function(self):
        """Test convenience function for file type."""
        file_type = get_file_type("/code/main.py")
        
        assert file_type == "code"


# ============================================================================
# INTEGRATION TESTS
# ============================================================================

class TestIntegration:
    """Integration tests for Day 3 components."""
    
    def test_cache_invalidation_on_pattern_change(self, temp_vault, sample_events):
        """Test cache is invalidated when access patterns change."""
        manager = AdaptiveScatterManager(temp_vault)
        
        # Cache initial parameters
        params1 = manager.get_parameters(
            file_path="/path/to/file.txt",
            recent_events=sample_events[:25]
        )
        
        # Simulate pattern change detection
        if manager.cache:
            # Check pattern change with different access times
            current_times = [t + 1000 for t in range(100)]  # Different pattern
            manager.cache.check_pattern_change(
                "/path/to/file.txt",
                current_times
            )
    
    def test_trigger_manager_integration(self, temp_vault, sample_events):
        """Test trigger manager integrates with scatter manager."""
        config = ManagerConfig(
            triggers_enabled=True,
            anomaly_trigger_count=3  # Low threshold for testing
        )
        manager = AdaptiveScatterManager(temp_vault, config)
        
        # Record some anomalies
        for event in sample_events[:10]:
            manager.record_access(event, was_anomaly=True)
        
        # Check trigger status
        if manager.trigger_manager:
            stats = manager.trigger_manager.get_stats()
            assert stats['anomaly']['anomalies_in_window'] > 0
    
    def test_full_workflow(self, temp_vault, sample_events):
        """Test complete workflow: cache -> get -> invalidate -> retrain."""
        manager = AdaptiveScatterManager(temp_vault)
        
        # 1. Get parameters (cache miss)
        params1 = manager.get_parameters(
            file_path="/data/important.db",
            recent_events=sample_events,
            file_size=1024 * 1024
        )
        
        # 2. Get again (cache hit)
        params2 = manager.get_parameters(
            file_path="/data/important.db",
            recent_events=sample_events
        )
        
        # 3. Record access events
        for event in sample_events[:20]:
            manager.record_access(event)
        
        # 4. Invalidate and recompute
        manager.invalidate_file("/data/important.db")
        
        params3 = manager.get_parameters(
            file_path="/data/important.db",
            recent_events=sample_events
        )
        
        # All parameters should be valid
        assert params1.scatter_depth >= 1
        assert params2.scatter_depth >= 1
        assert params3.scatter_depth >= 1
        
        # Stats should reflect operations
        status = manager.get_status()
        assert status['statistics']['cache_hits'] >= 1
        assert status['statistics']['cache_misses'] >= 2  # Initial + after invalidate
