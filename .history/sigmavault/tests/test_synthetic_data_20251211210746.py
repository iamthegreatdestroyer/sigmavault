"""
Tests for Synthetic Data Generator
===================================

Comprehensive test suite for the ML synthetic data generation system.

Tests cover:
- Normal pattern generation
- Anomaly pattern generation
- Mixed dataset creation
- Training batch generation
- Statistical validity

Agents: @ECLIPSE @TENSOR
"""

import pytest
from datetime import datetime, timedelta
from typing import List
import hashlib

from sigmavault.ml.synthetic_data_generator import (
    SyntheticDataGenerator,
    PatternType,
    UserProfile,
    generate_test_data
)
from sigmavault.ml.access_logger import AccessEvent, AccessLogger


class TestSyntheticDataGenerator:
    """Test suite for SyntheticDataGenerator."""
    
    @pytest.fixture
    def generator(self) -> SyntheticDataGenerator:
        """Create a seeded generator for reproducible tests."""
        return SyntheticDataGenerator(seed=42)
    
    @pytest.fixture
    def custom_profile(self) -> UserProfile:
        """Create a custom user profile for testing."""
        return UserProfile(
            user_id="test-user-123",
            primary_device="test-device",
            typical_files=["/test/file1.txt", "/test/file2.txt", "/test/file3.txt"],
            work_hours=(8, 18),
            avg_files_per_day=10,
            avg_file_size=10000,
            error_rate=0.05,
            ip_pool=["10.0.0.1", "10.0.0.2"]
        )
    
    # =========== Normal Pattern Tests ===========
    
    def test_normal_workday_generation(self, generator: SyntheticDataGenerator):
        """Test generation of normal workday patterns."""
        events = generator.generate_normal_workday(
            vault_id="test-vault",
            start_date=datetime(2025, 1, 1),
            days=7
        )
        
        # Should generate events
        assert len(events) > 0
        
        # Events should be sorted by timestamp
        for i in range(1, len(events)):
            assert events[i].timestamp >= events[i-1].timestamp
        
        # All events should have the correct vault_id
        for event in events:
            assert event.vault_id == "test-vault"
    
    def test_normal_workday_respects_hours(self, generator: SyntheticDataGenerator):
        """Test that normal workday events fall within work hours."""
        events = generator.generate_normal_workday(
            vault_id="test-vault",
            start_date=datetime(2025, 1, 6),  # Monday
            days=1
        )
        
        # Most events should be within default work hours (9-17)
        work_hour_events = [e for e in events if 9 <= e.timestamp.hour < 17]
        assert len(work_hour_events) / len(events) > 0.8  # 80% within work hours
    
    def test_normal_workday_with_custom_profile(
        self,
        generator: SyntheticDataGenerator,
        custom_profile: UserProfile
    ):
        """Test normal generation with custom user profile."""
        events = generator.generate_normal_workday(
            vault_id="test-vault",
            start_date=datetime(2025, 1, 6),
            days=5,
            profile=custom_profile
        )
        
        # All events should use the profile's user_id (hashed)
        expected_hash = hashlib.sha256(custom_profile.user_id.encode()).hexdigest()
        for event in events:
            assert event.user_id_hash == expected_hash
    
    def test_reproducibility_with_seed(self):
        """Test that same seed produces same results."""
        gen1 = SyntheticDataGenerator(seed=12345)
        gen2 = SyntheticDataGenerator(seed=12345)
        
        events1 = gen1.generate_normal_workday("vault", datetime(2025, 1, 1), 5)
        events2 = gen2.generate_normal_workday("vault", datetime(2025, 1, 1), 5)
        
        assert len(events1) == len(events2)
        for e1, e2 in zip(events1, events2):
            assert e1.timestamp == e2.timestamp
            assert e1.operation == e2.operation
    
    # =========== Anomaly Pattern Tests ===========
    
    def test_exfiltration_anomaly(self, generator: SyntheticDataGenerator):
        """Test data exfiltration anomaly pattern."""
        events = generator.generate_anomaly(
            pattern=PatternType.ANOMALY_EXFILTRATION,
            vault_id="test-vault",
            start_time=datetime(2025, 1, 15, 3, 0)  # 3 AM
        )
        
        # Exfiltration should generate many events
        assert len(events) >= 40
        
        # All should be read operations
        read_events = [e for e in events if e.operation == "read"]
        assert len(read_events) == len(events)
        
        # Events should be rapid (short intervals)
        total_duration = (events[-1].timestamp - events[0].timestamp).total_seconds()
        avg_interval = total_duration / len(events)
        assert avg_interval < 5  # Less than 5 seconds average between reads
    
    def test_brute_force_anomaly(self, generator: SyntheticDataGenerator):
        """Test brute force attack pattern."""
        events = generator.generate_anomaly(
            pattern=PatternType.ANOMALY_BRUTE_FORCE,
            vault_id="test-vault",
            start_time=datetime(2025, 1, 15, 2, 0)
        )
        
        # Many events
        assert len(events) >= 80
        
        # High failure rate (95%)
        failed_events = [e for e in events if not e.success]
        failure_rate = len(failed_events) / len(events)
        assert failure_rate > 0.8  # At least 80% failures
        
        # Error codes should be EACCES (permission denied)
        for event in failed_events:
            assert event.error_code == "EACCES"
    
    def test_odd_hours_anomaly(self, generator: SyntheticDataGenerator):
        """Test odd hours access pattern."""
        events = generator.generate_anomaly(
            pattern=PatternType.ANOMALY_ODD_HOURS,
            vault_id="test-vault",
            start_time=datetime(2025, 1, 15)
        )
        
        assert len(events) > 0
        
        # All events should be in odd hours (around 3 AM start)
        for event in events:
            # Should be between midnight and 6 AM
            assert event.timestamp.hour < 6 or event.timestamp.hour >= 22
    
    def test_new_device_anomaly(self, generator: SyntheticDataGenerator):
        """Test unknown device access pattern."""
        events = generator.generate_anomaly(
            pattern=PatternType.ANOMALY_NEW_DEVICE,
            vault_id="test-vault",
            start_time=datetime(2025, 1, 15, 10, 0)
        )
        
        assert len(events) > 0
        
        # All events should have the same unknown device
        device_fingerprints = {e.device_fingerprint for e in events}
        assert len(device_fingerprints) == 1
        
        # Device should be unknown (start with "unknown-device-")
        device = list(device_fingerprints)[0]
        assert device.startswith("unknown-device-")
    
    def test_burst_anomaly(self, generator: SyntheticDataGenerator):
        """Test activity burst pattern."""
        events = generator.generate_anomaly(
            pattern=PatternType.ANOMALY_BURST,
            vault_id="test-vault",
            start_time=datetime(2025, 1, 15, 14, 0)
        )
        
        # Burst should generate many events in short time
        assert len(events) >= 150
        
        # Total duration should be very short (under 1 minute for 200 events)
        total_duration = (events[-1].timestamp - events[0].timestamp).total_seconds()
        assert total_duration < 60  # Under 1 minute
    
    def test_geographic_anomaly(self, generator: SyntheticDataGenerator):
        """Test geographic anomaly (unusual IPs)."""
        events = generator.generate_anomaly(
            pattern=PatternType.ANOMALY_GEOGRAPHIC,
            vault_id="test-vault",
            start_time=datetime(2025, 1, 15, 10, 0)
        )
        
        assert len(events) > 0
        
        # IPs should be from anomaly pool (hashed, so we check uniqueness)
        ip_hashes = {e.ip_hash for e in events}
        
        # Should use different IPs (anomaly pool has 3 IPs)
        assert len(ip_hashes) >= 1
    
    def test_anomaly_intensity_scaling(self, generator: SyntheticDataGenerator):
        """Test that intensity parameter affects event count."""
        low_intensity = generator.generate_anomaly(
            pattern=PatternType.ANOMALY_BURST,
            vault_id="test",
            start_time=datetime(2025, 1, 1),
            intensity=0.5
        )
        
        high_intensity = generator.generate_anomaly(
            pattern=PatternType.ANOMALY_BURST,
            vault_id="test",
            start_time=datetime(2025, 1, 1),
            intensity=2.0
        )
        
        # Higher intensity should produce more events
        assert len(high_intensity) > len(low_intensity)
    
    # =========== Mixed Dataset Tests ===========
    
    def test_mixed_dataset_generation(self, generator: SyntheticDataGenerator):
        """Test generation of mixed normal + anomaly dataset."""
        events, labels = generator.generate_mixed_dataset(
            vault_id="test-vault",
            start_date=datetime(2025, 1, 1),
            days=30
        )
        
        # Should have events
        assert len(events) > 0
        
        # Should have some anomaly labels
        assert len(labels) > 0
        
        # Labels should have valid format
        for start_idx, end_idx, pattern in labels:
            assert start_idx < end_idx
            assert isinstance(pattern, PatternType)
    
    def test_mixed_dataset_custom_anomalies(self, generator: SyntheticDataGenerator):
        """Test mixed dataset with specific anomaly days and types."""
        events, labels = generator.generate_mixed_dataset(
            vault_id="test-vault",
            start_date=datetime(2025, 1, 1),
            days=10,
            anomaly_days=[3, 7],
            anomaly_types=[PatternType.ANOMALY_EXFILTRATION]
        )
        
        # Should have exactly 2 anomaly labels (one per day)
        assert len(labels) == 2
        
        # All anomalies should be exfiltration type
        for _, _, pattern in labels:
            assert pattern == PatternType.ANOMALY_EXFILTRATION
    
    # =========== Training Batch Tests ===========
    
    def test_training_batch_generation(self, generator: SyntheticDataGenerator):
        """Test training batch generation for ML models."""
        sequences, labels = generator.generate_training_batch(
            vault_id="test-vault",
            normal_count=50,
            anomaly_count=10
        )
        
        # Should have sequences and labels
        assert len(sequences) > 0
        assert len(labels) == len(sequences)
        
        # Should have both normal and anomaly labels
        normal_count = sum(1 for l in labels if not l)
        anomaly_count = sum(1 for l in labels if l)
        
        assert normal_count > 0
        assert anomaly_count > 0
    
    def test_training_sequences_have_minimum_events(self, generator: SyntheticDataGenerator):
        """Test that training sequences have minimum required events."""
        sequences, labels = generator.generate_training_batch(
            vault_id="test-vault",
            normal_count=20,
            anomaly_count=5
        )
        
        # Each sequence should have at least 3 events
        for seq in sequences:
            assert len(seq) >= 3
    
    # =========== Helper Function Tests ===========
    
    def test_generate_test_data_convenience(self):
        """Test the convenience function for generating test data."""
        normal_events, anomaly_events = generate_test_data(seed=42)
        
        # Should return events
        assert len(normal_events) > 0
        assert len(anomaly_events) > 0
        
        # Normal events should mostly be successful
        success_rate = sum(1 for e in normal_events if e.success) / len(normal_events)
        assert success_rate > 0.9
    
    # =========== Event Property Tests ===========
    
    def test_event_properties(self, generator: SyntheticDataGenerator):
        """Test that generated events have all required properties."""
        events = generator.generate_normal_workday(
            vault_id="test-vault",
            start_date=datetime(2025, 1, 1),
            days=1
        )
        
        for event in events:
            # All required fields should be present
            assert event.timestamp is not None
            assert event.vault_id is not None
            assert event.file_path_hash is not None
            assert event.operation in ["read", "write", "stat", "delete"]
            assert event.bytes_accessed >= 0
            assert event.duration_ms >= 0
            assert event.user_id_hash is not None
            assert event.device_fingerprint is not None
            assert event.ip_hash is not None
            assert isinstance(event.success, bool)
    
    def test_file_path_hashing(self, generator: SyntheticDataGenerator):
        """Test that file paths are properly hashed."""
        events = generator.generate_normal_workday(
            vault_id="test-vault",
            start_date=datetime(2025, 1, 1),
            days=1
        )
        
        for event in events:
            # Hash should be 64 characters (SHA-256 hex)
            assert len(event.file_path_hash) == 64
            
            # Should be hexadecimal
            assert all(c in '0123456789abcdef' for c in event.file_path_hash)
    
    def test_operation_distribution(self, generator: SyntheticDataGenerator):
        """Test that operations follow expected distribution."""
        events = generator.generate_normal_workday(
            vault_id="test-vault",
            start_date=datetime(2025, 1, 1),
            days=30  # More data for better distribution
        )
        
        operations = [e.operation for e in events]
        
        # Count operations
        read_count = operations.count("read")
        write_count = operations.count("write")
        stat_count = operations.count("stat")
        
        # Reads should be most common (60% target)
        total = len(operations)
        read_ratio = read_count / total
        assert 0.4 < read_ratio < 0.8  # Between 40-80%
        
        # Writes should be present but less than reads
        write_ratio = write_count / total
        assert write_ratio > 0.1  # At least 10%


class TestPatternType:
    """Tests for PatternType enum."""
    
    def test_all_pattern_types_exist(self):
        """Test that all expected pattern types are defined."""
        expected_patterns = [
            "NORMAL_WORKDAY",
            "NORMAL_EVENING",
            "NORMAL_WEEKEND",
            "ANOMALY_EXFILTRATION",
            "ANOMALY_BRUTE_FORCE",
            "ANOMALY_ODD_HOURS",
            "ANOMALY_NEW_DEVICE",
            "ANOMALY_BURST",
            "ANOMALY_GEOGRAPHIC",
            "EDGE_LONG_IDLE",
            "EDGE_DEVICE_SWITCH"
        ]
        
        for pattern_name in expected_patterns:
            assert hasattr(PatternType, pattern_name)
    
    def test_anomaly_patterns_identifiable(self):
        """Test that anomaly patterns can be identified by name."""
        anomaly_patterns = [p for p in PatternType if "ANOMALY" in p.name]
        assert len(anomaly_patterns) == 6


class TestUserProfile:
    """Tests for UserProfile dataclass."""
    
    def test_user_profile_creation(self):
        """Test UserProfile creation."""
        profile = UserProfile(
            user_id="user-123",
            primary_device="laptop",
            typical_files=["/doc.txt"],
            work_hours=(9, 17),
            avg_files_per_day=20,
            avg_file_size=50000,
            error_rate=0.01,
            ip_pool=["192.168.1.1"]
        )
        
        assert profile.user_id == "user-123"
        assert profile.work_hours == (9, 17)
        assert profile.avg_files_per_day == 20


class TestIntegration:
    """Integration tests combining multiple components."""
    
    def test_synthetic_data_with_feature_extractor(self):
        """Test that synthetic data works with feature extractor."""
        from sigmavault.ml.feature_extractor import FeatureExtractor
        
        generator = SyntheticDataGenerator(seed=42)
        events = generator.generate_normal_workday(
            vault_id="test-vault",
            start_date=datetime(2025, 1, 1),
            days=7
        )
        
        extractor = FeatureExtractor()
        features = extractor.extract(events)  # Correct method name is 'extract'
        
        # Should extract 11 features
        assert len(features) == 11
        
        # Features should be reasonable values
        for f in features:
            assert not (f != f)  # Not NaN
    
    def test_synthetic_data_with_anomaly_detector(self, tmp_path):
        """Test that synthetic anomalies are detectable."""
        from sigmavault.ml.anomaly_detector import AnomalyDetector
        
        generator = SyntheticDataGenerator(seed=42)
        
        # Generate normal data for training
        normal_events = generator.generate_normal_workday(
            vault_id="test-vault",
            start_date=datetime(2025, 1, 1),
            days=30
        )
        
        # Generate anomalous data
        anomaly_events = generator.generate_anomaly(
            pattern=PatternType.ANOMALY_EXFILTRATION,
            vault_id="test-vault",
            start_time=datetime(2025, 1, 15, 3, 0)
        )
        
        # Create access logger and populate with normal events for training
        access_logger = AccessLogger(vault_path=tmp_path)
        for event in normal_events:
            access_logger.log_event(event)
        
        # Create detector and train using the populated AccessLogger
        detector = AnomalyDetector(vault_path=tmp_path)
        detector.train(training_days=30, access_logger=access_logger)
        
        # Detect on both normal and anomaly
        normal_result = detector.detect(normal_events[-50:])
        anomaly_result = detector.detect(anomaly_events[:50])
        
        # Anomaly should have higher anomaly score
        assert anomaly_result.anomaly_score > normal_result.anomaly_score


# ============================================================================
# PERFORMANCE TESTS
# ============================================================================

class TestPerformance:
    """Performance tests for synthetic data generation."""
    
    def test_large_dataset_generation_time(self):
        """Test that large datasets generate in reasonable time."""
        import time
        
        generator = SyntheticDataGenerator(seed=42)
        
        start = time.time()
        events = generator.generate_normal_workday(
            vault_id="test-vault",
            start_date=datetime(2025, 1, 1),
            days=365  # Full year
        )
        elapsed = time.time() - start
        
        # Should complete in under 10 seconds
        assert elapsed < 10
        
        # Should generate significant data
        assert len(events) > 5000
    
    def test_training_batch_generation_time(self):
        """Test training batch generation performance."""
        import time
        
        generator = SyntheticDataGenerator(seed=42)
        
        start = time.time()
        sequences, labels = generator.generate_training_batch(
            vault_id="test-vault",
            normal_count=500,
            anomaly_count=100
        )
        elapsed = time.time() - start
        
        # Should complete in under 30 seconds
        assert elapsed < 30


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
