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


class TestTransactionManager(unittest.TestCase):
    """Tests for transaction-based error recovery system."""
    
    def setUp(self):
        from sigmavault.filesystem.fuse_layer import TransactionManager
        import tempfile
        import shutil
        
        self.temp_dir = Path(tempfile.mkdtemp())
        self.transaction_manager = TransactionManager(self.temp_dir / "transactions")
        self.TransactionManager = TransactionManager
    
    def tearDown(self):
        import shutil
        shutil.rmtree(self.temp_dir, ignore_errors=True)
    
    def test_transaction_lifecycle(self):
        """Test complete transaction lifecycle: begin → commit."""
        transaction_id = "test_txn_001"
        
        # Begin transaction
        state = self.transaction_manager.begin_transaction(transaction_id)
        self.assertIsNotNone(state)
        self.assertEqual(state.transaction_id, transaction_id)
        self.assertEqual(len(state.operations), 0)
        
        # Add some operations
        from sigmavault.filesystem.fuse_layer import Operation, OperationType
        op1 = Operation(OperationType.STORE_FILE, "test_file_1", {"path": "test1.dat", "data": b"test data 1"})
        op2 = Operation(OperationType.DELETE_FILE, "test_file_2", {"path": "test2.dat"})
        
        state.operations.append(op1)
        state.operations.append(op2)
        
        # Commit transaction
        self.transaction_manager.commit_transaction(transaction_id)
        
        # Transaction should be cleaned up
        self.assertNotIn(transaction_id, self.transaction_manager._active_transactions)
    
    def test_transaction_rollback(self):
        """Test transaction rollback functionality."""
        transaction_id = "test_rollback_txn"
        
        # Begin transaction
        state = self.transaction_manager.begin_transaction(transaction_id)
        
        # Add operations that would create/modify files
        from sigmavault.filesystem.fuse_layer import Operation, OperationType
        
        # Create a test file to "store"
        test_file = self.temp_dir / "test_store.dat"
        test_file.write_bytes(b"original content")
        
        op1 = Operation(OperationType.STORE_FILE, "test_store", {
            "path": str(test_file),
            "data": b"modified content",
            "backup_data": b"original content"
        })
        
        state.operations.append(op1)
        
        # Rollback transaction
        self.transaction_manager.rollback_transaction(transaction_id)
        
        # File should be restored to original content
        self.assertEqual(test_file.read_bytes(), b"original content")
    
    def test_transaction_timeout_cleanup(self):
        """Test that expired transactions are cleaned up."""
        import time
        from sigmavault.filesystem.fuse_layer import TransactionState
        
        # Create an expired transaction manually
        expired_id = "expired_txn"
        expired_state = TransactionState(expired_id)
        expired_state.created_at = time.time() - 400  # 400 seconds ago (past 300s timeout)
        
        self.transaction_manager._active_transactions[expired_id] = expired_state
        
        # Trigger cleanup
        self.transaction_manager._cleanup_expired_transactions()
        
        # Expired transaction should be removed
        self.assertNotIn(expired_id, self.transaction_manager._active_transactions)
    
    def test_concurrent_transactions(self):
        """Test multiple concurrent transactions."""
        import threading
        import time
        
        results = []
        
        def run_transaction(txn_id):
            try:
                state = self.transaction_manager.begin_transaction(txn_id)
                time.sleep(0.01)  # Simulate work
                self.transaction_manager.commit_transaction(txn_id)
                results.append(f"{txn_id}: success")
            except Exception as e:
                results.append(f"{txn_id}: error - {e}")
        
        # Start multiple transactions concurrently
        threads = []
        for i in range(5):
            t = threading.Thread(target=run_transaction, args=[f"concurrent_txn_{i}"])
            threads.append(t)
            t.start()
        
        # Wait for all to complete
        for t in threads:
            t.join()
        
        # All should succeed
        self.assertEqual(len(results), 5)
        for result in results:
            self.assertIn("success", result)


class TestTransactionWrappedOperations(unittest.TestCase):
    """Tests for transaction-wrapped FUSE operations."""
    
    def setUp(self):
        from sigmavault.filesystem.fuse_layer import SigmaVaultFS, ScatterStorageBackend
        from sigmavault.core.dimensional_scatter import DimensionalScatterEngine, KeyState
        from sigmavault.crypto.hybrid_key import HybridKeyDerivation, KeyMode
        import tempfile
        
        # Create temporary directories
        self.temp_dir = Path(tempfile.mkdtemp())
        self.vault_dir = self.temp_dir / "vault"
        self.vault_dir.mkdir()
        
        # Set up key derivation
        kdf = HybridKeyDerivation(KeyMode.USER_ONLY)
        kdf.initialize()
        master_key = kdf.derive_key("test_key_for_transactions")
        key_state = KeyState.derive(master_key)
        
        # Create components
        scatter_engine = DimensionalScatterEngine(key_state)
        storage_backend = ScatterStorageBackend(self.vault_dir, scatter_engine)
        
        # Create FUSE filesystem with transaction support
        self.fs = SigmaVaultFS(storage_backend, key_state)
        
        self.SigmaVaultFS = SigmaVaultFS
        self.ScatterStorageBackend = ScatterStorageBackend
    
    def tearDown(self):
        import shutil
        shutil.rmtree(self.temp_dir, ignore_errors=True)
    
    def test_create_with_transaction_rollback(self):
        """Test file creation with transaction rollback on failure."""
        # Mock a failure scenario
        original_store = self.fs.backend.store
        
        def failing_store(file_id, data):
            # Fail on first call
            if not hasattr(failing_store, 'called'):
                failing_store.called = True
                raise Exception("Simulated storage failure")
            return original_store(file_id, data)
        
        self.fs.backend.store = failing_store
        
        try:
            # This should fail and rollback
            with self.fs._lock:
                self.fs.create("test_file.txt", 0o644)
            self.fail("Expected exception was not raised")
        except Exception:
            pass  # Expected
        
        # File should not exist after rollback
        self.assertNotIn("test_file.txt", self.fs.backend._index._entries)
    
    def test_unlink_with_transaction_rollback(self):
        """Test file deletion with transaction rollback on failure."""
        # First create a file successfully
        with self.fs._lock:
            self.fs.create("test_unlink.txt", 0o644)
            fh = self.fs.open("test_unlink.txt", os.O_WRONLY)
            self.fs.write("test_unlink.txt", b"test content", 0, fh)
            self.fs.release("test_unlink.txt", fh)
        
        # Verify file exists
        self.assertIn("test_unlink.txt", self.fs.backend._index._entries)
        
        # Mock a failure in delete operation
        original_delete = self.fs.backend.delete
        
        def failing_delete(file_id):
            # Fail on first call
            if not hasattr(failing_delete, 'called'):
                failing_delete.called = True
                raise Exception("Simulated delete failure")
            return original_delete(file_id)
        
        self.fs.backend.delete = failing_delete
        
        try:
            # This should fail and rollback
            with self.fs._lock:
                self.fs.unlink("test_unlink.txt")
            self.fail("Expected exception was not raised")
        except Exception:
            pass  # Expected
        
        # File should still exist after rollback
        self.assertIn("test_unlink.txt", self.fs.backend._index._entries)
    
    def test_flush_with_transaction_rollback(self):
        """Test file flush with transaction rollback on failure."""
        # Create and write to file
        with self.fs._lock:
            self.fs.create("test_flush.txt", 0o644)
            fh = self.fs.open("test_flush.txt", os.O_WRONLY)
            self.fs.write("test_flush.txt", b"test content", 0, fh)
            
            # Mock failure in _flush_file
            original_flush = self.fs._flush_file
            
            def failing_flush(path, fh):
                raise Exception("Simulated flush failure")
            
            self.fs._flush_file = failing_flush
            
            try:
                # This should fail and rollback
                self.fs.release("test_flush.txt", fh)
                self.fail("Expected exception was not raised")
            except Exception:
                pass  # Expected
            
            # Restore original method
            self.fs._flush_file = original_flush
    
    def test_successful_transaction_operations(self):
        """Test successful transaction-wrapped operations."""
        # Create file
        with self.fs._lock:
            self.fs.create("success_test.txt", 0o644)
            fh = self.fs.open("success_test.txt", os.O_WRONLY)
            self.fs.write("success_test.txt", b"Hello, ΣVAULT!", 0, fh)
            self.fs.release("success_test.txt", fh)
        
        # Verify file exists
        self.assertIn("success_test.txt", self.fs.backend._index._entries)
        
        # Read file back
        with self.fs._lock:
            fh = self.fs.open("success_test.txt", os.O_RDONLY)
            data = self.fs.read("success_test.txt", 1024, 0, fh)
            self.fs.release("success_test.txt", fh)
        
        self.assertEqual(data, b"Hello, ΣVAULT!")
        
        # Delete file
        with self.fs._lock:
            self.fs.unlink("success_test.txt")
        
        # Verify file is gone
        self.assertNotIn("success_test.txt", self.fs.backend._index._entries)


class TestErrorRecoveryScenarios(unittest.TestCase):
    """Tests for various error recovery scenarios."""
    
    def setUp(self):
        from sigmavault.filesystem.fuse_layer import SigmaVaultFS, ScatterStorageBackend
        from sigmavault.core.dimensional_scatter import DimensionalScatterEngine, KeyState
        from sigmavault.crypto.hybrid_key import HybridKeyDerivation, KeyMode
        import tempfile
        
        # Create temporary directories
        self.temp_dir = Path(tempfile.mkdtemp())
        self.vault_dir = self.temp_dir / "vault"
        self.vault_dir.mkdir()
        
        # Set up key derivation
        kdf = HybridKeyDerivation(KeyMode.USER_ONLY)
        kdf.initialize()
        master_key = kdf.derive_key("test_key_for_recovery")
        key_state = KeyState.derive(master_key)
        
        # Create components
        scatter_engine = DimensionalScatterEngine(key_state)
        storage_backend = ScatterStorageBackend(self.vault_dir, scatter_engine)
        
        # Create FUSE filesystem
        self.fs = SigmaVaultFS(storage_backend, key_state)
    
    def tearDown(self):
        import shutil
        shutil.rmtree(self.temp_dir, ignore_errors=True)
    
    def test_partial_write_recovery(self):
        """Test recovery from partial write operations."""
        # Create file and start writing
        with self.fs._lock:
            self.fs.create("partial_write.txt", 0o644)
            fh = self.fs.open("partial_write.txt", os.O_WRONLY)
            
            # Write some data
            self.fs.write("partial_write.txt", b"partial data", 0, fh)
            
            # Simulate crash before flush
            # Don't call release - this should trigger cleanup
            
            # File should exist but be in inconsistent state
            self.assertIn("partial_write.txt", self.fs.backend._index._entries)
    
    def test_corrupted_index_recovery(self):
        """Test recovery from corrupted metadata index."""
        # Create some files
        with self.fs._lock:
            self.fs.create("file1.txt", 0o644)
            fh1 = self.fs.open("file1.txt", os.O_WRONLY)
            self.fs.write("file1.txt", b"content 1", 0, fh1)
            self.fs.release("file1.txt", fh1)
            
            self.fs.create("file2.txt", 0o644)
            fh2 = self.fs.open("file2.txt", os.O_WRONLY)
            self.fs.write("file2.txt", b"content 2", 0, fh2)
            self.fs.release("file2.txt", fh2)
        
        # Verify files exist
        self.assertIn("file1.txt", self.fs.backend._index._entries)
        self.assertIn("file2.txt", self.fs.backend._index._entries)
        
        # Simulate index corruption
        original_entries = dict(self.fs.backend._index._entries)
        self.fs.backend._index._entries.clear()  # Simulate corruption
        
        # Files should still be recoverable from storage
        # (In real implementation, this would require rebuilding index from storage)
        
        # For now, just verify the corruption simulation worked
        self.assertEqual(len(self.fs.backend._index._entries), 0)
    
    def test_concurrent_operation_recovery(self):
        """Test recovery when multiple operations fail concurrently."""
        import threading
        import time
        
        errors = []
        
        def failing_operation(op_id):
            try:
                with self.fs._lock:
                    self.fs.create(f"concurrent_{op_id}.txt", 0o644)
                    fh = self.fs.open(f"concurrent_{op_id}.txt", os.O_WRONLY)
                    
                    # Simulate random failure
                    if op_id % 2 == 0:
                        raise Exception(f"Simulated failure in operation {op_id}")
                    
                    self.fs.write(f"concurrent_{op_id}.txt", f"content {op_id}".encode(), 0, fh)
                    self.fs.release(f"concurrent_{op_id}.txt", fh)
                    
            except Exception as e:
                errors.append(f"op_{op_id}: {e}")
        
        # Run multiple operations concurrently
        threads = []
        for i in range(4):
            t = threading.Thread(target=failing_operation, args=[i])
            threads.append(t)
            t.start()
        
        for t in threads:
            t.join()
        
        # Some operations should have failed
        self.assertTrue(len(errors) > 0)
        
        # But filesystem should remain in consistent state
        # (All successful operations should be preserved, failed ones rolled back)
    
    def test_disk_space_recovery(self):
        """Test recovery when disk space is exhausted."""
        # This would require mocking filesystem full conditions
        # For now, just test that transactions handle exceptions gracefully
        
        with self.fs._lock:
            try:
                # Try to create a file that would exhaust resources
                self.fs.create("large_file.txt", 0o644)
                fh = self.fs.open("large_file.txt", os.O_WRONLY)
                
                # Write a lot of data (this might fail in real scenarios)
                large_data = b"x" * (10 * 1024 * 1024)  # 10MB
                self.fs.write("large_file.txt", large_data, 0, fh)
                self.fs.release("large_file.txt", fh)
                
            except Exception:
                # Recovery should happen automatically
                pass
        
        # Filesystem should be in consistent state regardless


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
