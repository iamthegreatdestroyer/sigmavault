"""
ΣVAULT Filesystem Benchmarks
============================

Benchmarks for the FUSE filesystem layer:
- File creation and writing
- File reading and retrieval
- Directory operations
- Transaction management
- Concurrent access patterns

Copyright 2025 - ΣVAULT Project
"""

import os
import secrets
import tempfile
import shutil
from typing import Dict
from pathlib import Path

# Add parent to path for imports
import sys
sys.path.insert(0, str(Path(__file__).parent.parent))
sys.path.insert(0, str(Path(__file__).parent))

from benchmark_core import BenchmarkRunner, BenchmarkResult, BenchmarkConfig

try:
    from filesystem.fuse_layer import (
        SigmaVaultFS,
        VirtualMetadataIndex,
        TransactionManager,
    )
    from core.dimensional_scatter import (
        KeyState,
        DimensionalScatterEngine,
    )
    HAS_FILESYSTEM = True
except ImportError as e:
    print(f"Warning: Could not import filesystem module: {e}")
    HAS_FILESYSTEM = False


def run_filesystem_benchmarks() -> Dict[str, BenchmarkResult]:
    """
    Run all filesystem benchmarks.
    
    Returns:
        Dictionary mapping benchmark names to results
    """
    results = {}
    
    if not HAS_FILESYSTEM:
        print("⚠️ Filesystem module not available, skipping benchmarks")
        return results
    
    config = BenchmarkConfig(
        warmup_iterations=3,
        min_iterations=5,
        target_time_seconds=10.0,
    )
    runner = BenchmarkRunner(config)
    
    # ==================================================================
    # 1. VIRTUAL METADATA INDEX
    # ==================================================================
    
    print("\n📁 Virtual Metadata Index Operations")
    print("-" * 40)
    
    try:
        metadata_index = VirtualMetadataIndex()
        test_key = secrets.token_bytes(64)
        key_state = KeyState.derive(test_key)
        
        file_counter = [0]  # Use list to allow mutation in nested function
        
        def add_file_entry():
            file_counter[0] += 1
            path = f"/test_dir/file_{file_counter[0]}.txt"
            metadata_index.add_file(path, size=1024, scatter_id=f"scatter_{file_counter[0]}")
            return path
        
        # Add some initial files
        for i in range(100):
            metadata_index.add_file(f"/bench_dir/file_{i}.txt", size=1024, scatter_id=f"id_{i}")
        
        result = runner.run(add_file_entry, "Add File to Metadata Index")
        print(result)
        results["metadata_add"] = result
        
        # Lookup operations
        def lookup_file():
            idx = secrets.randbelow(100)
            return metadata_index.get_file(f"/bench_dir/file_{idx}.txt")
        
        result = runner.run(lookup_file, "Metadata Lookup (random file)")
        print(result)
        results["metadata_lookup"] = result
        
        # List directory
        def list_directory():
            return metadata_index.list_directory("/bench_dir")
        
        result = runner.run(list_directory, "List Directory (100 files)")
        print(result)
        results["metadata_listdir"] = result
        
    except Exception as e:
        print(f"⚠️ Metadata index benchmarks skipped: {e}")
    
    # ==================================================================
    # 2. TRANSACTION MANAGEMENT
    # ==================================================================
    
    print("\n🔄 Transaction Management Operations")
    print("-" * 40)
    
    try:
        tx_manager = TransactionManager()
        
        def begin_commit_transaction():
            tx_id = tx_manager.begin_transaction()
            tx_manager.commit_transaction(tx_id)
            return tx_id
        
        result = runner.run(begin_commit_transaction, "Transaction Begin + Commit")
        print(result)
        results["tx_begin_commit"] = result
        
        def begin_rollback_transaction():
            tx_id = tx_manager.begin_transaction()
            tx_manager.rollback_transaction(tx_id)
            return tx_id
        
        result = runner.run(begin_rollback_transaction, "Transaction Begin + Rollback")
        print(result)
        results["tx_begin_rollback"] = result
        
        # Transaction with operations
        def transaction_with_ops():
            tx_id = tx_manager.begin_transaction()
            tx_manager.record_operation(tx_id, "CREATE", {"path": "/test.txt", "data": b"x"*100})
            tx_manager.record_operation(tx_id, "WRITE", {"path": "/test.txt", "data": b"y"*100})
            tx_manager.commit_transaction(tx_id)
            return tx_id
        
        result = runner.run(transaction_with_ops, "Transaction with 2 Operations")
        print(result)
        results["tx_with_ops"] = result
        
    except Exception as e:
        print(f"⚠️ Transaction benchmarks skipped: {e}")
    
    # ==================================================================
    # 3. FULL FILESYSTEM OPERATIONS
    # ==================================================================
    
    print("\n📂 Full Filesystem Operations")
    print("-" * 40)
    
    try:
        # Create temporary storage
        temp_dir = tempfile.mkdtemp(prefix="sigmavault_fs_bench_")
        storage_path = Path(temp_dir) / "storage"
        storage_path.mkdir(parents=True, exist_ok=True)
        
        # Initialize filesystem
        test_key = secrets.token_bytes(64)
        key_state = KeyState.derive(test_key)
        backend = ScatterStorageBackend(storage_path, medium_size=100 * 1024 * 1024)
        engine = DimensionalScatterEngine(key_state, backend)
        
        fs = SigmaVaultFS(engine)
        
        # Test data
        data_1kb = secrets.token_bytes(1024)
        data_10kb = secrets.token_bytes(10 * 1024)
        
        file_counter = [0]
        
        def create_file_1kb():
            file_counter[0] += 1
            path = f"/benchmark/file_{file_counter[0]}.bin"
            fs.create(path, 0o644)
            fs.write(path, data_1kb, 0, None)
            return path
        
        result = runner.run(create_file_1kb, "Create + Write File (1 KB)", data_size=1024)
        print(result)
        results["fs_create_write_1kb"] = result
        
        def create_file_10kb():
            file_counter[0] += 1
            path = f"/benchmark/file_{file_counter[0]}.bin"
            fs.create(path, 0o644)
            fs.write(path, data_10kb, 0, None)
            return path
        
        result = runner.run(create_file_10kb, "Create + Write File (10 KB)", data_size=10*1024)
        print(result)
        results["fs_create_write_10kb"] = result
        
        # Read operations
        test_path = create_file_1kb()
        
        def read_file_1kb():
            return fs.read(test_path, 1024, 0, None)
        
        result = runner.run(read_file_1kb, "Read File (1 KB)", data_size=1024)
        print(result)
        results["fs_read_1kb"] = result
        
        # Getattr operations
        def getattr_op():
            return fs.getattr(test_path)
        
        result = runner.run(getattr_op, "Get File Attributes")
        print(result)
        results["fs_getattr"] = result
        
        # Directory operations
        def mkdir_op():
            file_counter[0] += 1
            dir_path = f"/benchmark/dir_{file_counter[0]}"
            fs.mkdir(dir_path, 0o755)
            return dir_path
        
        result = runner.run(mkdir_op, "Create Directory")
        print(result)
        results["fs_mkdir"] = result
        
        # Readdir operations
        def readdir_op():
            return list(fs.readdir("/benchmark", None))
        
        result = runner.run(readdir_op, "Read Directory")
        print(result)
        results["fs_readdir"] = result
        
        # Cleanup
        shutil.rmtree(temp_dir, ignore_errors=True)
        
    except Exception as e:
        print(f"⚠️ Full filesystem benchmarks skipped: {e}")
        import traceback
        traceback.print_exc()
    
    # ==================================================================
    # 4. CONCURRENT ACCESS PATTERNS (simulated)
    # ==================================================================
    
    print("\n🔀 Concurrent Access Patterns (Sequential Simulation)")
    print("-" * 40)
    
    try:
        # Simulate interleaved read/write operations
        temp_dir = tempfile.mkdtemp(prefix="sigmavault_concurrent_bench_")
        storage_path = Path(temp_dir) / "storage"
        storage_path.mkdir(parents=True, exist_ok=True)
        
        test_key = secrets.token_bytes(64)
        key_state = KeyState.derive(test_key)
        backend = ScatterStorageBackend(storage_path, medium_size=100 * 1024 * 1024)
        engine = DimensionalScatterEngine(key_state, backend)
        
        fs = SigmaVaultFS(engine)
        
        # Pre-create files for concurrent test
        for i in range(10):
            path = f"/concurrent/file_{i}.bin"
            fs.create(path, 0o644)
            fs.write(path, secrets.token_bytes(1024), 0, None)
        
        def mixed_operations():
            """Simulate mixed read/write workload."""
            # Random operation mix
            for _ in range(5):
                idx = secrets.randbelow(10)
                path = f"/concurrent/file_{idx}.bin"
                
                if secrets.randbelow(2) == 0:
                    # Read
                    fs.read(path, 1024, 0, None)
                else:
                    # Write
                    fs.write(path, secrets.token_bytes(512), 0, None)
        
        config_concurrent = BenchmarkConfig(
            warmup_iterations=2,
            min_iterations=5,
            target_time_seconds=10.0,
        )
        runner_concurrent = BenchmarkRunner(config_concurrent)
        
        result = runner_concurrent.run(mixed_operations, "Mixed Read/Write (5 ops)")
        print(result)
        results["fs_mixed_ops"] = result
        
        # Cleanup
        shutil.rmtree(temp_dir, ignore_errors=True)
        
    except Exception as e:
        print(f"⚠️ Concurrent access benchmarks skipped: {e}")
    
    return results


if __name__ == "__main__":
    run_filesystem_benchmarks()
