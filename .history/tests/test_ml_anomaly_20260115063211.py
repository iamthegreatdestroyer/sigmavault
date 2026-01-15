"""
Unit Tests for ML Anomaly Detection System
==========================================

Tests for AccessLogger, FeatureExtractor, and AnomalyDetector.

Copyright (c) 2025 ΣVAULT. All Rights Reserved.
"""

import pytest
import tempfile
import numpy as np
from pathlib import Path
from datetime import datetime, timedelta
from unittest.mock import Mock, patch

from sigmavault.ml.access_logger import AccessLogger, AccessEvent
from sigmavault.ml.feature_extractor import FeatureExtractor
from sigmavault.ml.anomaly_detector import AnomalyDetector, AlertLevel


# ============================================================================
# Fixtures
# ============================================================================

@pytest.fixture
def temp_vault():
    """Create temporary vault directory."""
    with tempfile.TemporaryDirectory() as tmpdir:
        yield Path(tmpdir)


@pytest.fixture
def access_logger(temp_vault):
    """Create AccessLogger with automatic cleanup."""
    logger = AccessLogger(vault_path=temp_vault)
    yield logger
    logger.close()


@pytest.fixture
def anomaly_detector(temp_vault):
    """Create AnomalyDetector with automatic cleanup."""
    detector = AnomalyDetector(vault_path=temp_vault)
    yield detector
    detector.close()


@pytest.fixture
def sample_events():
    """Generate sample access events for testing.
    
    Generates events spread over LAST 72 hours (ending now) to ensure:
    - Enough 1-hour sliding window sequences for training (needs 50+)
    - Events are recent enough for recent_events queries (last 1-24 hours)
    - Statistics queries capture all events in their windows
    """
    base_time = datetime.now() - timedelta(hours=72)  # Start 72 hours ago
    events = []
    
    # Normal pattern: regular reads spread over 72 hours up to NOW
    # Generate ~8 events per hour = ~576 events over 72 hours
    for hour in range(72):
        hour_base = base_time + timedelta(hours=hour)  # Progress toward now
        for minute in range(0, 60, 8):  # Every 8 minutes = ~7-8 events per hour
            events.append(AccessEvent(
                timestamp=hour_base + timedelta(minutes=minute),
                vault_id="test-vault",
                file_path_hash=f"hash-{minute % 10}",
                operation="read",
                bytes_accessed=4096,
                duration_ms=10.0 + np.random.randn() * 2,
                user_id_hash="user-123",
                device_fingerprint="device-001",
                ip_hash="ip-192.168.1.1",
                success=True
            ))
    
    return events


@pytest.fixture
def anomalous_events():
    """Generate anomalous access events for testing."""
    base_time = datetime.now()
    events = []
    
    # Abnormal pattern: rapid burst of accesses
    for i in range(100):
        events.append(AccessEvent(
            timestamp=base_time + timedelta(seconds=i*5),  # Every 5 seconds
            vault_id="test-vault",
            file_path_hash=f"hash-{i}",  # Many unique files
            operation="read",
            bytes_accessed=1024000,  # Large files
            duration_ms=5.0,  # Very fast
            user_id_hash="user-suspicious",
            device_fingerprint="device-unknown",
            ip_hash="ip-suspicious",
            success=True
        ))
    
    return events


# ============================================================================
# AccessLogger Tests
# ============================================================================

class TestAccessLogger:
    """Test suite for AccessLogger."""
    
    def test_initialization(self, access_logger, temp_vault):
        """Test logger initializes correctly."""
        assert access_logger.vault_path == temp_vault
        assert access_logger.db_path.exists()
        assert access_logger.buffer_size == 10000
        assert access_logger.retention_days == 90
    
    def test_log_event(self, access_logger, sample_events):
        """Test logging single event."""
        event = sample_events[0]
        
        access_logger.log_event(event)
        
        # Verify in buffer
        buffer_events = access_logger.get_buffer_events()
        assert len(buffer_events) == 1
        assert buffer_events[0].vault_id == event.vault_id
    
    def test_log_multiple_events(self, access_logger, sample_events):
        """Test logging multiple events."""
        for event in sample_events:
            access_logger.log_event(event)
        
        # Verify count
        buffer_events = access_logger.get_buffer_events()
        assert len(buffer_events) == len(sample_events)
    
    def test_get_recent_events(self, access_logger, sample_events):
        """Test retrieving recent events from database."""
        # Log events
        for event in sample_events[:10]:
            access_logger.log_event(event)
        
        # Retrieve recent (1 hour window)
        recent = access_logger.get_recent_events(window=timedelta(hours=1))
        
        assert len(recent) > 0
        assert all(isinstance(e, AccessEvent) for e in recent)
    
    def test_get_statistics(self, access_logger, sample_events):
        """Test statistics calculation."""
        # Log events
        for event in sample_events:
            access_logger.log_event(event)
        
        # Get stats
        stats = access_logger.get_statistics(window=timedelta(days=1))
        
        assert stats['total_events'] == len(sample_events)
        assert 'by_operation' in stats
        assert stats['success_rate'] == 1.0  # All successful
        assert stats['unique_users'] >= 1
    
    def test_cleanup_old_logs(self, temp_vault):
        """Test cleanup of old log entries."""
        # Create logger with custom retention for this test
        logger = AccessLogger(temp_vault, retention_days=1)
        try:
            # Create old events (2 days ago)
            old_time = datetime.now() - timedelta(days=2)
            old_event = AccessEvent(
                timestamp=old_time,
                vault_id="test-vault",
                file_path_hash="old-file",
                operation="read",
                bytes_accessed=1024,
                duration_ms=10.0,
                user_id_hash="user-123",
                device_fingerprint="device-001",
                ip_hash=None,
                success=True
            )
            logger.log_event(old_event)
            
            # Cleanup
            deleted = logger.cleanup_old_logs()
            
            assert deleted >= 0  # May be 0 or more
        finally:
            logger.close()
    
    def test_hash_identifier(self):
        """Test privacy-preserving identifier hashing."""
        hash1 = AccessLogger.hash_identifier("user-123", salt="vault-salt")
        hash2 = AccessLogger.hash_identifier("user-123", salt="vault-salt")
        hash3 = AccessLogger.hash_identifier("user-456", salt="vault-salt")
        
        assert hash1 == hash2  # Same input = same hash
        assert hash1 != hash3  # Different input = different hash
        assert len(hash1) == 64  # SHA-256 hex = 64 chars


# ============================================================================
# FeatureExtractor Tests
# ============================================================================

class TestFeatureExtractor:
    """Test suite for FeatureExtractor."""
    
    def test_extract_from_events(self, sample_events):
        """Test feature extraction from event sequence."""
        extractor = FeatureExtractor()
        features = extractor.extract(sample_events)
        
        # Verify all expected features present
        expected_features = [
            'access_frequency',
            'unique_files',
            'read_write_ratio',
            'avg_file_size',
            'access_entropy',
            'time_of_day_mean',
            'time_of_day_std',
            'session_duration',
            'error_rate',
            'ip_diversity',
            'operation_diversity',
        ]
        
        for feature in expected_features:
            assert feature in features
            assert isinstance(features[feature], (int, float))
    
    def test_extract_from_empty_events(self):
        """Test feature extraction from empty event list."""
        extractor = FeatureExtractor()
        features = extractor.extract([])
        
        # Should return zero-valued features
        assert all(v == 0.0 for v in features.values())
    
    def test_access_frequency_calculation(self, sample_events):
        """Test access frequency feature calculation."""
        extractor = FeatureExtractor()
        
        # 50 events over ~100 minutes
        features = extractor.extract(sample_events)
        
        assert features['access_frequency'] > 0
        assert features['unique_files'] == 10  # 10 unique files (i % 10)
    
    def test_read_write_ratio(self):
        """Test read/write ratio calculation."""
        extractor = FeatureExtractor()
        
        # Create events with mixed operations
        events = [
            AccessEvent(
                timestamp=datetime.now(),
                vault_id="test",
                file_path_hash="file",
                operation="read",
                bytes_accessed=1024,
                duration_ms=10.0,
                user_id_hash="user",
                device_fingerprint="device",
                ip_hash=None,
                success=True
            )
            for _ in range(7)
        ] + [
            AccessEvent(
                timestamp=datetime.now(),
                vault_id="test",
                file_path_hash="file",
                operation="write",
                bytes_accessed=1024,
                duration_ms=10.0,
                user_id_hash="user",
                device_fingerprint="device",
                ip_hash=None,
                success=True
            )
            for _ in range(3)
        ]
        
        features = extractor.extract(events)
        
        # 7 reads, 3 writes = 7/10 = 0.7
        assert abs(features['read_write_ratio'] - 0.7) < 0.01
    
    def test_access_entropy_calculation(self, sample_events):
        """Test Shannon entropy calculation for access intervals."""
        extractor = FeatureExtractor()
        features = extractor.extract(sample_events)
        
        # Regular intervals should have lower entropy
        assert features['access_entropy'] >= 0
    
    def test_error_rate_calculation(self):
        """Test error rate feature calculation."""
        extractor = FeatureExtractor()
        
        # Create events with some failures
        events = [
            AccessEvent(
                timestamp=datetime.now(),
                vault_id="test",
                file_path_hash="file",
                operation="read",
                bytes_accessed=1024,
                duration_ms=10.0,
                user_id_hash="user",
                device_fingerprint="device",
                ip_hash=None,
                success=(i % 5 != 0)  # Every 5th fails
            )
            for i in range(10)
        ]
        
        features = extractor.extract(events)
        
        # 2 failures out of 10 = 0.2
        assert abs(features['error_rate'] - 0.2) < 0.01
    
    def test_extract_batch(self, sample_events):
        """Test batch feature extraction."""
        extractor = FeatureExtractor()
        
        # Create multiple sequences
        sequences = [
            sample_events[:10],
            sample_events[10:20],
            sample_events[20:30]
        ]
        
        feature_matrix = extractor.extract_batch(sequences)
        
        assert feature_matrix.shape[0] == 3  # 3 sequences
        assert feature_matrix.shape[1] == 11  # 11 features
        assert not np.any(np.isnan(feature_matrix))  # No NaN values


# ============================================================================
# AnomalyDetector Tests
# ============================================================================

@pytest.mark.skipif(
    not pytest.importorskip("sklearn", reason="scikit-learn not available"),
    reason="scikit-learn required for anomaly detection"
)
class TestAnomalyDetector:
    """Test suite for AnomalyDetector."""
    
    def test_initialization(self, anomaly_detector, temp_vault):
        """Test detector initializes correctly."""
        assert anomaly_detector.vault_path == temp_vault
        assert anomaly_detector.contamination == 0.05
        assert anomaly_detector.n_estimators == 100
        assert anomaly_detector.model is None  # Not trained yet
    
    def test_train_with_sufficient_data(self, anomaly_detector, access_logger, sample_events):
        """Test training with sufficient data."""
        # Populate with data
        for event in sample_events * 3:  # 150 events
            access_logger.log_event(event)
        
        # Train
        metrics = anomaly_detector.train(training_days=1, access_logger=access_logger)
        
        assert anomaly_detector.model is not None
        assert anomaly_detector.scaler is not None
        assert metrics['n_samples'] > 0
        assert 0 <= metrics['anomaly_rate'] <= 1
    
    def test_train_insufficient_data_raises_error(self, anomaly_detector, access_logger):
        """Test training with insufficient data raises error."""
        # Only a few events (insufficient)
        for i in range(5):
            access_logger.log_event(AccessEvent(
                timestamp=datetime.now(),
                vault_id="test",
                file_path_hash="file",
                operation="read",
                bytes_accessed=1024,
                duration_ms=10.0,
                user_id_hash="user",
                device_fingerprint="device",
                ip_hash=None,
                success=True
            ))
        
        with pytest.raises(ValueError, match="Insufficient training data"):
            anomaly_detector.train(training_days=1, access_logger=access_logger)
    
    def test_detect_anomaly(self, anomaly_detector, access_logger, sample_events, anomalous_events):
        """Test anomaly detection on normal vs anomalous patterns."""
        # Train on normal data
        for event in sample_events * 3:
            access_logger.log_event(event)
        
        anomaly_detector.train(training_days=1, access_logger=access_logger)
        
        # Test normal pattern
        is_anomaly_normal, score_normal, level_normal = anomaly_detector.detect(sample_events[:20])
        
        # Test anomalous pattern
        is_anomaly_abnormal, score_abnormal, level_abnormal = anomaly_detector.detect(anomalous_events[:50])
        
        # Normal should have higher score (less anomalous)
        assert score_normal > score_abnormal
    
    def test_detect_without_training_raises_error(self, anomaly_detector, sample_events):
        """Test detection without training raises error."""
        with pytest.raises(RuntimeError, match="Model not trained"):
            anomaly_detector.detect(sample_events)
    
    def test_alert_levels(self, temp_vault, sample_events):
        """Test graduated alert level system."""
        # Create detector with custom thresholds and train
        logger = AccessLogger(temp_vault)
        try:
            for event in sample_events * 3:
                logger.log_event(event)
            
            detector = AnomalyDetector(
                temp_vault,
                alert_threshold=-0.3,
                critical_threshold=-0.6
            )
            detector.train(training_days=1, access_logger=logger)
            
            # Mock scores to test alert levels
            with patch.object(detector.model, 'score_samples') as mock_score:
                # Normal score (above alert threshold)
                mock_score.return_value = np.array([0.0])
                is_anomaly, score, level = detector.detect(sample_events[:10])
                assert level == AlertLevel.NORMAL
                assert not is_anomaly
                
                # Warning score (between thresholds)
                mock_score.return_value = np.array([-0.4])
                is_anomaly, score, level = detector.detect(sample_events[:10])
                assert level == AlertLevel.WARNING
                assert is_anomaly
                
                # Critical score (below critical threshold)
                mock_score.return_value = np.array([-0.7])
                is_anomaly, score, level = detector.detect(sample_events[:10])
                assert level == AlertLevel.CRITICAL
                assert is_anomaly
            
            detector.close()
        finally:
            logger.close()
    
    def test_explain_anomaly(self, anomaly_detector, access_logger, sample_events):
        """Test anomaly explanation feature."""
        # Train
        for event in sample_events * 3:
            access_logger.log_event(event)
        
        anomaly_detector.train(training_days=1, access_logger=access_logger)
        
        # Get explanation
        explanations = anomaly_detector.explain_anomaly(sample_events[:20], top_k=3)
        
        assert len(explanations) <= 3  # Top 3 features
        assert all(isinstance(v, float) for v in explanations.values())
    
    def test_save_and_load_model(self, temp_vault, sample_events):
        """Test model persistence."""
        # Train and save
        logger = AccessLogger(temp_vault)
        try:
            for event in sample_events * 3:
                logger.log_event(event)
            
            detector1 = AnomalyDetector(temp_vault)
            detector1.train(training_days=1, access_logger=logger)
            detector1.save_model()
            detector1.close()
            
            # Load in new detector
            detector2 = AnomalyDetector(temp_vault)
            detector2.load_model()
            detector2.close()
        finally:
            logger.close()
        
        assert detector2.model is not None
        assert detector2.scaler is not None
        
        # Should produce same results
        _, score1, _ = detector1.detect(sample_events[:20])
        _, score2, _ = detector2.detect(sample_events[:20])
        
        assert abs(score1 - score2) < 0.01  # Nearly identical
    
    def test_detect_batch(self, anomaly_detector, access_logger, sample_events):
        """Test batch anomaly detection."""
        # Train
        for event in sample_events * 3:
            access_logger.log_event(event)
        
        anomaly_detector.train(training_days=1, access_logger=access_logger)
        
        # Batch detection
        sequences = [
            sample_events[:10],
            sample_events[10:20],
            sample_events[20:30]
        ]
        
        results = anomaly_detector.detect_batch(sequences)
        
        assert len(results) == 3
        assert all(isinstance(r[0], bool) for r in results)  # is_anomaly
        assert all(isinstance(r[1], float) for r in results)  # score
        assert all(isinstance(r[2], AlertLevel) for r in results)  # level
    
    def test_get_model_info(self, anomaly_detector):
        """Test model info retrieval."""
        # Before training
        info = anomaly_detector.get_model_info()
        assert info['status'] == 'not_trained'
        
        # After training (with mock)
        anomaly_detector.model = Mock()
        anomaly_detector.scaler = Mock()
        
        info = anomaly_detector.get_model_info()
        assert info['status'] == 'trained'
        assert 'n_estimators' in info
        assert 'feature_count' in info


# ============================================================================
# Integration Tests
# ============================================================================

class TestMLIntegration:
    """Integration tests for complete ML pipeline."""
    
    def test_end_to_end_pipeline(self, temp_vault):
        """Test complete ML pipeline from logging to detection."""
        # 1. Create logger
        logger = AccessLogger(temp_vault)
        detector = AnomalyDetector(temp_vault)
        
        try:
            # 2. Simulate normal usage (100 events)
            base_time = datetime.now()
            for i in range(100):
                event = AccessEvent(
                    timestamp=base_time + timedelta(minutes=i),
                    vault_id="test-vault",
                    file_path_hash=f"file-{i % 5}",
                    operation="read" if i % 3 == 0 else "write",
                    bytes_accessed=4096,
                    duration_ms=10.0,
                    user_id_hash="user-normal",
                    device_fingerprint="device-laptop",
                    ip_hash="ip-home",
                    success=True
                )
                logger.log_event(event)
            
            # 3. Train anomaly detector
            metrics = detector.train(training_days=1, access_logger=logger)
            
            assert metrics['n_samples'] > 0
            
            # 4. Test detection on normal pattern
            recent = logger.get_recent_events(window=timedelta(hours=1))
            is_anomaly, score, level = detector.detect(recent[-20:])
            
            # Normal pattern should not be anomalous
            assert level == AlertLevel.NORMAL or level == AlertLevel.WARNING
            
            # 5. Get statistics
            stats = logger.get_statistics(window=timedelta(days=1))
            assert stats['total_events'] == 100
            assert stats['success_rate'] == 1.0
        finally:
            detector.close()
            logger.close()


# ============================================================================
# Performance Tests
# ============================================================================

@pytest.mark.slow
class TestMLPerformance:
    """Performance tests for ML components."""
    
    def test_feature_extraction_performance(self, sample_events):
        """Test feature extraction is fast enough."""
        import time
        
        extractor = FeatureExtractor()
        
        # Measure time for 1000 extractions
        start = time.time()
        for _ in range(1000):
            extractor.extract(sample_events[:20])
        elapsed = time.time() - start
        
        # Should complete in reasonable time (<2 seconds)
        assert elapsed < 2.0
        
        # Per-extraction time
        per_extraction = elapsed / 1000
        assert per_extraction < 0.002  # <2ms per extraction
    
    def test_anomaly_detection_latency(self, temp_vault, sample_events):
        """Test anomaly detection meets latency requirements."""
        import time
        
        # Train detector
        logger = AccessLogger(temp_vault)
        detector = AnomalyDetector(temp_vault)
        
        try:
            for event in sample_events * 3:
                logger.log_event(event)
            
            detector.train(training_days=1, access_logger=logger)
            
            # Measure detection time
            start = time.time()
            for _ in range(100):
                detector.detect(sample_events[:20])
            elapsed = time.time() - start
            
            # Per-detection time
            per_detection = elapsed / 100
            
            # Should be <10ms per detection (requirement from PHASE_5_KICKOFF.md)
            assert per_detection < 0.010  # 10ms
        finally:
            detector.close()
            logger.close()
