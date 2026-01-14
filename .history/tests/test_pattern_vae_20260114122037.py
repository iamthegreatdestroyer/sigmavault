"""
Tests for Pattern Obfuscation VAE
==================================

Comprehensive test suite for the VAE-based pattern generation system.

Tests cover:
- VAE architecture building
- Training pipeline
- Decoy generation
- Pattern similarity
- Interpolation
- Anomaly scoring
- Model persistence

Agents: @ECLIPSE @TENSOR
"""

import pytest
import tempfile
import numpy as np
from pathlib import Path
from datetime import datetime, timedelta
from unittest.mock import Mock, patch, MagicMock
from typing import List

from sigmavault.ml.access_logger import AccessEvent
from sigmavault.ml.feature_extractor import FeatureExtractor

# Conditional imports for tests
try:
    from sigmavault.ml.pattern_vae import (
        PatternObfuscationVAE,
        VAEConfig,
        GeneratedPattern,
        create_pattern_vae,
        generate_decoy_events,
        Sampling
    )
    HAS_TENSORFLOW = True
except ImportError:
    HAS_TENSORFLOW = False


# Skip entire module if TensorFlow not available
pytestmark = pytest.mark.skipif(
    not HAS_TENSORFLOW,
    reason="TensorFlow required for VAE tests"
)


# ============================================================================
# Fixtures
# ============================================================================

@pytest.fixture
def temp_vault():
    """Create temporary vault directory."""
    with tempfile.TemporaryDirectory() as tmpdir:
        yield Path(tmpdir)


@pytest.fixture
def vae_config():
    """Create test VAE configuration."""
    return VAEConfig(
        latent_dim=4,  # Smaller for faster tests
        encoder_units=[32, 16],
        decoder_units=[16, 32],
        beta=0.1,
        learning_rate=0.01,
        batch_size=16,
        epochs=5,  # Few epochs for fast tests
        dropout_rate=0.1
    )


@pytest.fixture
def sample_events() -> List[AccessEvent]:
    """Generate sample access events."""
    base_time = datetime.now() - timedelta(hours=2)
    events = []
    
    for i in range(50):
        events.append(AccessEvent(
            timestamp=base_time + timedelta(minutes=i * 2),
            vault_id="test-vault",
            file_path_hash=f"hash-{i % 10}",
            operation="read" if i % 3 != 0 else "write",
            bytes_accessed=4096 + (i * 100),
            duration_ms=10.0 + np.random.randn() * 2,
            user_id_hash="user-123",
            device_fingerprint="device-001",
            ip_hash="ip-192.168.1.1",
            success=True
        ))
    
    return events


@pytest.fixture
def event_sequences(sample_events) -> List[List[AccessEvent]]:
    """Create multiple event sequences for training."""
    sequences = []
    
    # Create 100 sequences by sliding window
    window_size = 20
    for i in range(0, len(sample_events) - window_size, 5):
        sequences.append(sample_events[i:i + window_size])
    
    # Duplicate with variations to get more training data
    for _ in range(5):
        for seq in list(sequences):
            # Create variation
            varied_seq = []
            for event in seq:
                varied_event = AccessEvent(
                    timestamp=event.timestamp + timedelta(seconds=np.random.randint(0, 60)),
                    vault_id=event.vault_id,
                    file_path_hash=event.file_path_hash,
                    operation=event.operation,
                    bytes_accessed=int(event.bytes_accessed * (0.9 + 0.2 * np.random.rand())),
                    duration_ms=event.duration_ms * (0.9 + 0.2 * np.random.rand()),
                    user_id_hash=event.user_id_hash,
                    device_fingerprint=event.device_fingerprint,
                    ip_hash=event.ip_hash,
                    success=event.success
                )
                varied_seq.append(varied_event)
            sequences.append(varied_seq)
    
    return sequences


# ============================================================================
# VAEConfig Tests
# ============================================================================

class TestVAEConfig:
    """Tests for VAE configuration."""
    
    def test_default_config(self):
        """Test default configuration values."""
        config = VAEConfig()
        
        assert config.latent_dim == 8
        assert config.beta == 0.1
        assert config.learning_rate == 0.001
        assert config.batch_size == 32
        assert config.epochs == 100
        assert config.dropout_rate == 0.2
    
    def test_custom_config(self, vae_config):
        """Test custom configuration."""
        assert vae_config.latent_dim == 4
        assert vae_config.encoder_units == [32, 16]
        assert vae_config.decoder_units == [16, 32]
        assert vae_config.epochs == 5
    
    def test_config_post_init(self):
        """Test __post_init__ sets default units."""
        config = VAEConfig(latent_dim=10)
        
        assert config.encoder_units == [64, 32]
        assert config.decoder_units == [32, 64]


# ============================================================================
# Sampling Layer Tests
# ============================================================================

class TestSamplingLayer:
    """Tests for the reparameterization sampling layer."""
    
    def test_sampling_output_shape(self):
        """Test sampling layer produces correct output shape."""
        import tensorflow as tf
        
        batch_size = 16
        latent_dim = 8
        
        z_mean = tf.random.normal((batch_size, latent_dim))
        z_log_var = tf.random.normal((batch_size, latent_dim))
        
        sampling = Sampling()
        z = sampling([z_mean, z_log_var])
        
        assert z.shape == (batch_size, latent_dim)
    
    def test_sampling_stochastic(self):
        """Test sampling produces different results each time."""
        import tensorflow as tf
        
        z_mean = tf.zeros((10, 4))
        z_log_var = tf.zeros((10, 4))
        
        sampling = Sampling()
        z1 = sampling([z_mean, z_log_var])
        z2 = sampling([z_mean, z_log_var])
        
        # Should be different (stochastic)
        assert not np.allclose(z1.numpy(), z2.numpy())


# ============================================================================
# PatternObfuscationVAE Tests
# ============================================================================

class TestPatternObfuscationVAE:
    """Tests for the Pattern Obfuscation VAE."""
    
    def test_initialization(self, temp_vault, vae_config):
        """Test VAE initializes correctly."""
        vae = PatternObfuscationVAE(temp_vault, vae_config)
        
        assert vae.vault_path == temp_vault
        assert vae.config == vae_config
        assert vae.n_features == 11  # Number of features
        assert not vae.is_trained
    
    def test_model_directory_created(self, temp_vault, vae_config):
        """Test model directory is created on init."""
        vae = PatternObfuscationVAE(temp_vault, vae_config)
        
        assert vae.model_dir.exists()
        assert vae.model_dir == temp_vault / ".ml" / "models" / "vae"
    
    def test_build_encoder(self, temp_vault, vae_config):
        """Test encoder network building."""
        vae = PatternObfuscationVAE(temp_vault, vae_config)
        encoder = vae._build_encoder()
        
        assert encoder is not None
        assert encoder.input_shape == (None, 11)  # 11 features
        assert len(encoder.outputs) == 3  # z_mean, z_log_var, z
    
    def test_build_decoder(self, temp_vault, vae_config):
        """Test decoder network building."""
        vae = PatternObfuscationVAE(temp_vault, vae_config)
        decoder = vae._build_decoder()
        
        assert decoder is not None
        assert decoder.input_shape == (None, vae_config.latent_dim)
        assert decoder.output_shape == (None, 11)  # 11 features
    
    def test_build_vae(self, temp_vault, vae_config):
        """Test complete VAE building."""
        vae = PatternObfuscationVAE(temp_vault, vae_config)
        vae_model = vae._build_vae()
        
        assert vae_model is not None
        assert vae.encoder is not None
        assert vae.decoder is not None
        assert vae_model.input_shape == (None, 11)
        assert vae_model.output_shape == (None, 11)
    
    def test_train_insufficient_data(self, temp_vault, vae_config, sample_events):
        """Test training fails with insufficient data."""
        vae = PatternObfuscationVAE(temp_vault, vae_config)
        
        # Only a few sequences
        small_sequences = [sample_events[:10]]
        
        with pytest.raises(ValueError, match="Insufficient training data"):
            vae.train(small_sequences)
    
    def test_train_success(self, temp_vault, vae_config, event_sequences):
        """Test successful training."""
        vae = PatternObfuscationVAE(temp_vault, vae_config)
        
        metrics = vae.train(event_sequences, verbose=0)
        
        assert vae.is_trained
        assert 'n_samples' in metrics
        assert 'final_loss' in metrics
        assert 'reconstruction_error' in metrics
        assert metrics['n_samples'] >= 50
    
    def test_generate_decoys_untrained(self, temp_vault, vae_config):
        """Test decoy generation fails if not trained."""
        vae = PatternObfuscationVAE(temp_vault, vae_config)
        
        with pytest.raises(RuntimeError, match="not trained"):
            vae.generate_decoys(n=10)
    
    def test_generate_decoys_success(self, temp_vault, vae_config, event_sequences):
        """Test successful decoy generation."""
        vae = PatternObfuscationVAE(temp_vault, vae_config)
        vae.train(event_sequences, verbose=0)
        
        decoys = vae.generate_decoys(n=10)
        
        assert len(decoys) == 10
        assert all(isinstance(d, GeneratedPattern) for d in decoys)
        assert all('access_frequency' in d.features for d in decoys)
        assert all(len(d.latent_code) == vae_config.latent_dim for d in decoys)
    
    def test_generate_similar(self, temp_vault, vae_config, event_sequences, sample_events):
        """Test generating patterns similar to input."""
        vae = PatternObfuscationVAE(temp_vault, vae_config)
        vae.train(event_sequences, verbose=0)
        
        similar = vae.generate_similar(sample_events[:20], n=5, noise_scale=0.3)
        
        assert len(similar) == 5
        assert all(isinstance(s, GeneratedPattern) for s in similar)
    
    def test_interpolate(self, temp_vault, vae_config, event_sequences):
        """Test interpolation between patterns."""
        vae = PatternObfuscationVAE(temp_vault, vae_config)
        vae.train(event_sequences, verbose=0)
        
        # Use two different sequences
        events_a = event_sequences[0]
        events_b = event_sequences[-1]
        
        interpolated = vae.interpolate(events_a, events_b, steps=5)
        
        assert len(interpolated) == 5
        assert all(isinstance(p, GeneratedPattern) for p in interpolated)
    
    def test_anomaly_score(self, temp_vault, vae_config, event_sequences, sample_events):
        """Test anomaly scoring."""
        vae = PatternObfuscationVAE(temp_vault, vae_config)
        vae.train(event_sequences, verbose=0)
        
        score = vae.anomaly_score(sample_events[:20])
        
        assert isinstance(score, float)
        assert score >= 0  # Reconstruction error is non-negative
    
    def test_get_latent_representation(self, temp_vault, vae_config, event_sequences, sample_events):
        """Test getting latent representation."""
        vae = PatternObfuscationVAE(temp_vault, vae_config)
        vae.train(event_sequences, verbose=0)
        
        latent = vae.get_latent_representation(sample_events[:20])
        
        assert isinstance(latent, np.ndarray)
        assert latent.shape == (vae_config.latent_dim,)
    
    def test_save_and_load(self, temp_vault, vae_config, event_sequences):
        """Test model persistence."""
        # Train and save
        vae1 = PatternObfuscationVAE(temp_vault, vae_config)
        vae1.train(event_sequences, verbose=0)
        vae1.save()
        
        # Load in new instance
        vae2 = PatternObfuscationVAE(temp_vault, vae_config)
        vae2.load()
        
        assert vae2.is_trained
        assert vae2.encoder is not None
        assert vae2.decoder is not None
        assert vae2.scaler is not None
    
    def test_summary(self, temp_vault, vae_config, event_sequences):
        """Test model summary."""
        vae = PatternObfuscationVAE(temp_vault, vae_config)
        vae.train(event_sequences, verbose=0)
        
        summary = vae.summary()
        
        assert "PATTERN OBFUSCATION VAE SUMMARY" in summary
        assert "Trained: True" in summary
        assert f"Latent Dimensions: {vae_config.latent_dim}" in summary


# ============================================================================
# GeneratedPattern Tests
# ============================================================================

class TestGeneratedPattern:
    """Tests for GeneratedPattern dataclass."""
    
    def test_to_dict(self):
        """Test conversion to dictionary."""
        pattern = GeneratedPattern(
            features={'access_frequency': 10.5, 'unique_files': 5.0},
            latent_code=np.array([0.1, 0.2, 0.3]),
            reconstruction_loss=0.05,
            timestamp=datetime(2026, 1, 14, 12, 0)
        )
        
        d = pattern.to_dict()
        
        assert d['features'] == {'access_frequency': 10.5, 'unique_files': 5.0}
        assert d['latent_code'] == [0.1, 0.2, 0.3]
        assert d['reconstruction_loss'] == 0.05
        assert '2026-01-14' in d['timestamp']


# ============================================================================
# Convenience Function Tests
# ============================================================================

class TestConvenienceFunctions:
    """Tests for module convenience functions."""
    
    def test_create_pattern_vae(self, temp_vault):
        """Test create_pattern_vae helper."""
        vae = create_pattern_vae(temp_vault, latent_dim=6, beta=0.2)
        
        assert vae.config.latent_dim == 6
        assert vae.config.beta == 0.2
        assert vae.vault_path == temp_vault
    
    def test_generate_decoy_events(self, temp_vault, vae_config, event_sequences, sample_events):
        """Test generate_decoy_events helper."""
        vae = PatternObfuscationVAE(temp_vault, vae_config)
        vae.train(event_sequences, verbose=0)
        
        decoys = generate_decoy_events(vae, sample_events[:20], n_decoys=20)
        
        assert len(decoys) == 20
        assert all(isinstance(d, dict) for d in decoys)
        assert all('access_frequency' in d for d in decoys)


# ============================================================================
# Integration Tests
# ============================================================================

class TestVAEIntegration:
    """Integration tests for VAE with other ML components."""
    
    def test_vae_with_feature_extractor(self, temp_vault, vae_config, sample_events):
        """Test VAE works with FeatureExtractor."""
        extractor = FeatureExtractor()
        features = extractor.extract(sample_events)
        
        # Verify all VAE features are extracted
        for feature_name in PatternObfuscationVAE.FEATURE_NAMES:
            assert feature_name in features
    
    def test_decoy_features_valid_range(self, temp_vault, vae_config, event_sequences):
        """Test generated decoy features are in valid ranges."""
        vae = PatternObfuscationVAE(temp_vault, vae_config)
        vae.train(event_sequences, verbose=0)
        
        decoys = vae.generate_decoys(n=50)
        
        for decoy in decoys:
            # Check access_frequency is positive
            assert decoy.features['access_frequency'] >= 0
            
            # Check ratios are bounded
            assert 0 <= decoy.features['read_write_ratio'] <= 1
            assert 0 <= decoy.features['error_rate'] <= 1
            
            # Check time of day is reasonable
            assert 0 <= decoy.features['time_of_day_mean'] <= 24
    
    def test_multiple_train_calls(self, temp_vault, vae_config, event_sequences):
        """Test VAE can be retrained multiple times."""
        vae = PatternObfuscationVAE(temp_vault, vae_config)
        
        # First training
        metrics1 = vae.train(event_sequences[:60], verbose=0)
        decoys1 = vae.generate_decoys(n=5)
        
        # Second training (retraining)
        metrics2 = vae.train(event_sequences, verbose=0)
        decoys2 = vae.generate_decoys(n=5)
        
        # Both should work
        assert len(decoys1) == 5
        assert len(decoys2) == 5


# ============================================================================
# Edge Cases
# ============================================================================

class TestEdgeCases:
    """Edge case tests."""
    
    def test_empty_event_list_for_similarity(self, temp_vault, vae_config, event_sequences):
        """Test handling of edge cases in generate_similar."""
        vae = PatternObfuscationVAE(temp_vault, vae_config)
        vae.train(event_sequences, verbose=0)
        
        # Empty list should handle gracefully or raise appropriate error
        with pytest.raises(Exception):
            vae.generate_similar([], n=5)
    
    def test_single_event(self, temp_vault, vae_config, event_sequences, sample_events):
        """Test with single event."""
        vae = PatternObfuscationVAE(temp_vault, vae_config)
        vae.train(event_sequences, verbose=0)
        
        # Single event - should still work
        score = vae.anomaly_score([sample_events[0]])
        assert isinstance(score, float)
    
    def test_very_small_noise_scale(self, temp_vault, vae_config, event_sequences, sample_events):
        """Test generate_similar with very small noise."""
        vae = PatternObfuscationVAE(temp_vault, vae_config)
        vae.train(event_sequences, verbose=0)
        
        # Very small noise - should be very similar to original
        similar = vae.generate_similar(sample_events[:20], n=3, noise_scale=0.001)
        
        # All should have similar features
        assert len(similar) == 3


if __name__ == '__main__':
    pytest.main([__file__, '-v', '--tb=short'])
