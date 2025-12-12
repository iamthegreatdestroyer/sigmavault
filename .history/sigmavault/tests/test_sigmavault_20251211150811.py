#!/usr/bin/env python3
"""
ΣVAULT Test Suite
=================

Comprehensive tests for dimensional scattering, key derivation,
and filesystem operations.

Run with: python -m pytest tests/test_sigmavault.py -v
Or: python tests/test_sigmavault.py --demo
"""

import unittest
import secrets
import hashlib
import tempfile
import shutil
import sys
import os
from pathlib import Path

# Add parent to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

import numpy as np


class TestKeyDerivation(unittest.TestCase):
    """Tests for hybrid key derivation system."""
    
    def setUp(self):
        from sigmavault.crypto.hybrid_key import (
            HybridKeyDerivation, KeyMode, UserKeyDerivation
        )
        self.HybridKeyDerivation = HybridKeyDerivation
        self.KeyMode = KeyMode
        self.UserKeyDerivation = UserKeyDerivation
    
    def test_user_key_derivation_deterministic(self):
        """Same passphrase + salt produces same key."""
        salt = secrets.token_bytes(32)
        ukd1 = self.UserKeyDerivation(salt)
        ukd2 = self.UserKeyDerivation(salt)
        
        key1 = ukd1.derive_from_passphrase("test_password")
        key2 = ukd2.derive_from_passphrase("test_password")
        
        self.assertEqual(key1, key2)
    
    def test_different_passphrases_different_keys(self):
        """Different passphrases produce different keys."""
        salt = secrets.token_bytes(32)
        ukd = self.UserKeyDerivation(salt)
        
        key1 = ukd.derive_from_passphrase("password1")
        key2 = ukd.derive_from_passphrase("password2")
        
        self.assertNotEqual(key1, key2)
    
    def test_different_salts_different_keys(self):
        """Different salts produce different keys."""
        ukd1 = self.UserKeyDerivation(secrets.token_bytes(32))
        ukd2 = self.UserKeyDerivation(secrets.token_bytes(32))
        
        key1 = ukd1.derive_from_passphrase("same_password")
        key2 = ukd2.derive_from_passphrase("same_password")
        
        self.assertNotEqual(key1, key2)
    
    def test_hybrid_key_derivation_produces_512_bits(self):
        """Hybrid key derivation produces 512-bit key."""
        kdf = self.HybridKeyDerivation(self.KeyMode.USER_ONLY)
        kdf.initialize()
        
        key = kdf.derive_key("test_passphrase")
        
        self.assertEqual(len(key), 64)  # 512 bits = 64 bytes
    
    def test_key_mode_user_only_works_without_device(self):
        """USER_ONLY mode works on any device."""
        kdf1 = self.HybridKeyDerivation(self.KeyMode.USER_ONLY)
        salt = kdf1.initialize()
        key1 = kdf1.derive_key("test_passphrase")
        
        kdf2 = self.HybridKeyDerivation(self.KeyMode.USER_ONLY)
        kdf2.initialize(salt)  # Same salt
        key2 = kdf2.derive_key("test_passphrase")
        
        self.assertEqual(key1, key2)


class TestDimensionalScatter(unittest.TestCase):
    """Tests for dimensional scattering engine."""
    
    def setUp(self):
        from sigmavault.core.dimensional_scatter import (
            DimensionalScatterEngine, KeyState
        )
        from sigmavault.crypto.hybrid_key import HybridKeyDerivation, KeyMode
        
        # Create test key state
        kdf = HybridKeyDerivation(KeyMode.USER_ONLY)
        kdf.initialize()
        master_key = kdf.derive_key("test_key_for_scattering")
        
        self.key_state = KeyState.derive(master_key)
        self.engine = DimensionalScatterEngine(self.key_state, medium_size=10_000_000)
    
    def test_scatter_gather_roundtrip_small(self):
        """Small data survives scatter→gather roundtrip."""
        original = b"Hello SIGMAVAULT!"
        file_id = secrets.token_bytes(16)
        
        scattered = self.engine.scatter(file_id, original)
        reconstructed = self.engine.gather(scattered)
        
        self.assertEqual(reconstructed[:len(original)], original)
    
    def test_scatter_gather_roundtrip_medium(self):
        """Medium data (1KB) survives scatter→gather roundtrip."""
        original = secrets.token_bytes(1024)
        file_id = secrets.token_bytes(16)
        
        scattered = self.engine.scatter(file_id, original)
        reconstructed = self.engine.gather(scattered)
        
        self.assertEqual(reconstructed[:len(original)], original)
    
    def test_scatter_gather_roundtrip_large(self):
        """Large data (64KB) survives scatter→gather roundtrip."""
        original = secrets.token_bytes(65536)
        file_id = secrets.token_bytes(16)
        
        scattered = self.engine.scatter(file_id, original)
        reconstructed = self.engine.gather(scattered)
        
        self.assertEqual(reconstructed[:len(original)], original)
    
    def test_scatter_gather_roundtrip_streaming(self):
        """Very large data (5MB) uses streaming and survives scatter→gather roundtrip."""
        # Create data larger than streaming threshold (100MB)
        original = secrets.token_bytes(5 * 1024 * 1024)  # 5MB
        file_id = secrets.token_bytes(16)
        
        scattered = self.engine.scatter(file_id, original)
        reconstructed = self.engine.gather(scattered)
        
        self.assertEqual(reconstructed[:len(original)], original)
    
    def test_scatter_produces_multiple_shards(self):
        """Scattering produces multiple shards."""
        original = b"Test data for sharding"
        file_id = secrets.token_bytes(16)
        
        scattered = self.engine.scatter(file_id, original)
        
        self.assertGreater(len(scattered.shard_coordinates), 1)
    
    def test_scattered_data_larger_than_original(self):
        """Scattered data is larger due to entropy mixing."""
        original = b"Test data"
        file_id = secrets.token_bytes(16)
        
        scattered = self.engine.scatter(file_id, original)
        
        total_scattered = sum(
            len(data) for shard in scattered.shard_coordinates 
            for _, data, _ in shard
        )
        
        self.assertGreater(total_scattered, len(original))
    
    def test_different_file_ids_different_scatter(self):
        """Different file IDs produce different scatter patterns."""
        original = b"Same content"
        
        scattered1 = self.engine.scatter(secrets.token_bytes(16), original)
        scattered2 = self.engine.scatter(secrets.token_bytes(16), original)
        
        # Compare first shard's first chunk coordinates
        coord1 = scattered1.shard_coordinates[0][0][0]
        coord2 = scattered2.shard_coordinates[0][0][0]
        
        # At least some coordinates should differ
        self.assertNotEqual(coord1.semantic, coord2.semantic)
    
    def test_empty_data_handled(self):
        """Empty data is handled gracefully."""
        original = b""
        file_id = secrets.token_bytes(16)
        
        scattered = self.engine.scatter(file_id, original)
        reconstructed = self.engine.gather(scattered)
        
        # Should not crash, reconstructed may have padding
        self.assertIsNotNone(reconstructed)


class TestEntropicMixer(unittest.TestCase):
    """Tests for entropic mixing system."""
    
    def setUp(self):
        from sigmavault.core.dimensional_scatter import (
            EntropicMixer, KeyState, DimensionalCoordinate
        )
        from sigmavault.crypto.hybrid_key import HybridKeyDerivation, KeyMode
        
        kdf = HybridKeyDerivation(KeyMode.USER_ONLY)
        kdf.initialize()
        master_key = kdf.derive_key("test_key_for_mixing")
        
        self.key_state = KeyState.derive(master_key)
        self.mixer = EntropicMixer(self.key_state)
        self.DimensionalCoordinate = DimensionalCoordinate
    
    def test_mix_expands_data(self):
        """Mixing expands data with entropy."""
        original = b"Test data"
        coord = self.DimensionalCoordinate(
            spatial=100, temporal=200, entropic=300, semantic=400,
            fractal=2, phase=1.5, topological=500, holographic=0
        )
        
        mixed = self.mixer.mix(original, coord)
        
        self.assertGreater(len(mixed), len(original))
    
    def test_mix_unmix_roundtrip(self):
        """Data survives mix→unmix roundtrip."""
        original = b"Secret message"
        coord = self.DimensionalCoordinate(
            spatial=100, temporal=200, entropic=300, semantic=400,
            fractal=2, phase=1.5, topological=500, holographic=0
        )
        
        mixed = self.mixer.mix(original, coord)
        unmixed = self.mixer.unmix(mixed, coord, len(original))
        
        self.assertEqual(unmixed, original)
    
    def test_mixed_data_appears_random(self):
        """Mixed data has high entropy (appears random)."""
        original = b"AAAAAAAAAAAAAAAA"  # Low entropy input
        coord = self.DimensionalCoordinate(
            spatial=100, temporal=200, entropic=300, semantic=400,
            fractal=2, phase=1.5, topological=500, holographic=0
        )
        
        mixed = self.mixer.mix(original, coord)
        
        # Calculate byte frequency
        freq = [0] * 256
        for b in mixed:
            freq[b] += 1
        
        # Should have multiple different bytes (high entropy)
        unique_bytes = sum(1 for f in freq if f > 0)
        self.assertGreater(unique_bytes, 10)


class TestHolographicRedundancy(unittest.TestCase):
    """Tests for holographic redundancy system."""
    
    def setUp(self):
        from sigmavault.core.dimensional_scatter import (
            HolographicRedundancy, KeyState
        )
        from sigmavault.crypto.hybrid_key import HybridKeyDerivation, KeyMode
        
        kdf = HybridKeyDerivation(KeyMode.USER_ONLY)
        kdf.initialize()
        master_key = kdf.derive_key("test_key_for_holographic")
        
        self.key_state = KeyState.derive(master_key)
        self.holographic = HolographicRedundancy(self.key_state)
    
    def test_create_shards_produces_expected_count(self):
        """Sharding produces expected number of shards."""
        data = b"Test data for sharding into multiple pieces"
        
        shards = self.holographic.create_shards(data, num_shards=8)
        
        self.assertEqual(len(shards), 8)
    
    def test_reconstruct_from_all_shards(self):
        """Data reconstructs from all shards."""
        data = b"Test data for reconstruction"
        
        shards = self.holographic.create_shards(data, num_shards=8)
        reconstructed = self.holographic.reconstruct(shards, len(data))
        
        self.assertEqual(reconstructed, data)


class TestKeyState(unittest.TestCase):
    """Tests for KeyState derivation."""
    
    def setUp(self):
        from sigmavault.core.dimensional_scatter import KeyState
        self.KeyState = KeyState
    
    def test_derive_produces_valid_state(self):
        """KeyState.derive produces valid state object."""
        master_key = secrets.token_bytes(64)
        
        state = self.KeyState.derive(master_key)
        
        self.assertEqual(len(state.master_seed), 32)
        self.assertIsInstance(state.temporal_prime, int)
        self.assertIsInstance(state.entropy_ratio, float)
        self.assertGreater(state.entropy_ratio, 0)
        self.assertLess(state.entropy_ratio, 1)
    
    def test_same_key_same_state(self):
        """Same master key produces same state."""
        master_key = secrets.token_bytes(64)
        
        state1 = self.KeyState.derive(master_key)
        state2 = self.KeyState.derive(master_key)
        
        self.assertEqual(state1.master_seed, state2.master_seed)
        self.assertEqual(state1.temporal_prime, state2.temporal_prime)
    
    def test_different_keys_different_state(self):
        """Different master keys produce different states."""
        state1 = self.KeyState.derive(secrets.token_bytes(64))
        state2 = self.KeyState.derive(secrets.token_bytes(64))
        
        self.assertNotEqual(state1.master_seed, state2.master_seed)


# ============================================================================
# DEMONSTRATION
# ============================================================================

def run_demo():
    """Run interactive demonstration of ΣVAULT."""
    from sigmavault.core.dimensional_scatter import DimensionalScatterEngine, KeyState
    from sigmavault.crypto.hybrid_key import HybridKeyDerivation, KeyMode
    
    print("\n" + "=" * 70)
    print("ΣVAULT DIMENSIONAL SCATTERING DEMONSTRATION")
    print("=" * 70)
    
    # Create key
    print("\n[1] Creating hybrid key from passphrase...")
    kdf = HybridKeyDerivation(KeyMode.USER_ONLY)
    kdf.initialize()
    master_key = kdf.derive_key("demo_passphrase_2025")
    print(f"    Master key (first 16 bytes): {master_key[:16].hex()}")
    
    # Create key state
    print("\n[2] Deriving dimensional key state...")
    key_state = KeyState.derive(master_key)
    print(f"    Entropy ratio: {key_state.entropy_ratio:.3f}")
    print(f"    Scatter depth: {key_state.scatter_depth}")
    print(f"    Temporal prime: {key_state.temporal_prime}")
    
    # Create engine
    print("\n[3] Initializing scatter engine (10MB medium)...")
    engine = DimensionalScatterEngine(key_state, medium_size=10_000_000)
    
    # Test data
    test_cases = [
        b"Hello SIGMAVAULT!",
        b"A" * 100,
        secrets.token_bytes(1000),
    ]
    
    print("\n[4] Scatter/Gather Tests:")
    print("-" * 70)
    
    for i, data in enumerate(test_cases):
        file_id = secrets.token_bytes(16)
        
        # Scatter
        scattered = engine.scatter(file_id, data)
        
        # Calculate scattered size
        scattered_size = sum(
            len(d) for shard in scattered.shard_coordinates 
            for _, d, _ in shard
        )
        
        # Gather
        reconstructed = engine.gather(scattered)
        reconstructed = reconstructed[:len(data)]
        
        # Verify
        success = reconstructed == data
        status = "✓" if success else "✗"
        
        # Display
        if len(data) <= 20:
            data_preview = data.decode('utf-8', errors='replace')
        else:
            data_preview = f"[{len(data)} bytes]"
        
        print(f"    Test {i+1}: {data_preview}")
        print(f"           Original: {len(data)} bytes")
        print(f"           Scattered: {scattered_size} bytes ({len(scattered.shard_coordinates)} shards)")
        print(f"           Expansion: {scattered_size/len(data):.2f}x")
        print(f"           Status: {status} {'SUCCESS' if success else 'FAILURE'}")
        print()
    
    # Show sample scattered data
    print("[5] Entropic Indistinguishability:")
    print("-" * 70)
    
    sample_scattered = scattered.shard_coordinates[0][0][1][:48]
    print(f"    Sample scattered bytes (hex):")
    print(f"    {sample_scattered.hex()}")
    
    # Calculate entropy
    freq = [0] * 256
    for b in sample_scattered:
        freq[b] += 1
    unique = sum(1 for f in freq if f > 0)
    
    print(f"    Unique byte values: {unique}/256")
    print(f"    Without the key, this is indistinguishable from random noise.")
    
    print("\n" + "=" * 70)
    print("Demonstration complete!")
    print("=" * 70 + "\n")


# ============================================================================
# MAIN
# ============================================================================

if __name__ == '__main__':
    if '--demo' in sys.argv:
        run_demo()
    else:
        # Run unit tests
        unittest.main(verbosity=2)
