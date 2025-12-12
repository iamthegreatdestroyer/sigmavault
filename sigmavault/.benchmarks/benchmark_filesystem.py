"""
ΣVAULT Filesystem Benchmarks
============================

Benchmarks for raw I/O and filesystem-related operations:
- Raw file I/O baseline
- In-memory metadata operations
- Transaction patterns

Note: Full FUSE layer benchmarks require package installation.
These benchmarks test foundational operations.

Copyright 2025 - ΣVAULT Project
"""

import os
import secrets
import tempfile
import shutil
import threading
import time
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Any
from pathlib import Path
from collections import defaultdict

# Add parent to path for imports
import sys
sys.path.insert(0, str(Path(__file__).parent.parent))
sys.path.insert(0, str(Path(__file__).parent))

from benchmark_core import BenchmarkRunner, BenchmarkResult, BenchmarkConfig

# Import core components (these use absolute-style imports that work)
try:
    from core.dimensional_scatter import KeyState, DimensionalScatterEngine
    HAS_CORE = True
except ImportError:
    try:
        # Try with parent path
        parent_path = str(Path(__file__).parent.parent)
        if parent_path not in sys.path:
            sys.path.insert(0, parent_path)
        from core.dimensional_scatter import KeyState, DimensionalScatterEngine
        HAS_CORE = True
    except ImportError as e:
        print(f"Note: Core module not available: {e}")
        HAS_CORE = False


# ============================================================================
# STANDALONE METADATA INDEX (for benchmarking without FUSE imports)
# ============================================================================

@dataclass
class BenchVirtualFileEntry:
    """Metadata for a virtual file (benchmark version)."""
    path: str
    size: int
    scatter_id: str
    mode: int = 0o644
    created: float = field(default_factory=time.time)
    modified: float = field(default_factory=time.time)
    accessed: float = field(default_factory=time.time)
    

class BenchMetadataIndex:
    """In-memory metadata index (benchmark version)."""
    
    def __init__(self):
        self._entries: Dict[str, BenchVirtualFileEntry] = {}
        self._directories: Dict[str, List[str]] = defaultdict(list)
        self._lock = threading.RLock()
        
    def add_file(self, path: str, size: int, scatter_id: str) -> BenchVirtualFileEntry:
        """Add a file entry."""
        with self._lock:
            entry = BenchVirtualFileEntry(path=path, size=size, scatter_id=scatter_id)
            self._entries[path] = entry
            parent = str(Path(path).parent)
            if path not in self._directories[parent]:
                self._directories[parent].append(path)
            return entry
    
    def get_file(self, path: str) -> Optional[BenchVirtualFileEntry]:
        """Get a file entry."""
        with self._lock:
            return self._entries.get(path)
    
    def list_directory(self, path: str) -> List[str]:
        """List files in a directory."""
        with self._lock:
            return self._directories.get(path, []).copy()
    
    def update_file(self, path: str, size: Optional[int] = None) -> Optional[BenchVirtualFileEntry]:
        """Update a file entry."""
        with self._lock:
            entry = self._entries.get(path)
            if entry:
                if size is not None:
                    entry.size = size
                entry.modified = time.time()
            return entry


class BenchTransactionManager:
    """Transaction manager for benchmarking."""
    
    def __init__(self):
        self._transactions: Dict[str, Dict[str, Any]] = {}
        self._lock = threading.Lock()
        self._counter = 0
    
    def begin_transaction(self) -> str:
        """Begin a new transaction."""
        with self._lock:
            self._counter += 1
            tx_id = f"tx_{self._counter}_{time.time_ns()}"
            self._transactions[tx_id] = {
                "started": time.time(),
                "operations": [],
                "status": "active"
            }
            return tx_id
    
    def record_operation(self, tx_id: str, op_type: str, data: Dict[str, Any]):
        """Record an operation in a transaction."""
        with self._lock:
            if tx_id in self._transactions:
                self._transactions[tx_id]["operations"].append({
                    "type": op_type,
                    "data": data,
                    "timestamp": time.time()
                })
    
    def commit_transaction(self, tx_id: str) -> bool:
        """Commit a transaction."""
        with self._lock:
            if tx_id in self._transactions:
                self._transactions[tx_id]["status"] = "committed"
                self._transactions[tx_id]["completed"] = time.time()
                return True
            return False
    
    def rollback_transaction(self, tx_id: str) -> bool:
        """Rollback a transaction."""
        with self._lock:
            if tx_id in self._transactions:
                self._transactions[tx_id]["status"] = "rolled_back"
                self._transactions[tx_id]["completed"] = time.time()
                return True
            return False


def run_filesystem_benchmarks() -> Dict[str, BenchmarkResult]:
    """
    Run all filesystem benchmarks.
    
    Returns:
        Dictionary mapping benchmark names to results
    """
    results = {}
    
    config = BenchmarkConfig(
        warmup_iterations=5,
        min_iterations=10,
        target_time_seconds=10.0,
    )
    runner = BenchmarkRunner(config)
    
    # ==================================================================
    # 1. RAW FILE I/O BASELINE
    # ==================================================================
    
    print("\n💾 Raw File I/O Baseline")
    print("-" * 40)
    
    temp_dir = tempfile.mkdtemp(prefix="sigmavault_io_bench_")
    
    try:
        # Write benchmarks
        data_1kb = secrets.token_bytes(1024)
        data_1mb = secrets.token_bytes(1024 * 1024)
        data_10mb = secrets.token_bytes(10 * 1024 * 1024)
        
        file_counter = [0]
        
        def write_1kb():
            file_counter[0] += 1
            path = os.path.join(temp_dir, f"file_{file_counter[0]}.bin")
            with open(path, 'wb') as f:
                f.write(data_1kb)
            return path
        
        result = runner.run(write_1kb, "Raw File Write (1 KB)", data_size=1024)
        print(result)
        results["raw_write_1kb"] = result
        
        def write_1mb():
            file_counter[0] += 1
            path = os.path.join(temp_dir, f"file_{file_counter[0]}.bin")
            with open(path, 'wb') as f:
                f.write(data_1mb)
            return path
        
        result = runner.run(write_1mb, "Raw File Write (1 MB)", data_size=1024*1024)
        print(result)
        results["raw_write_1mb"] = result
        
        config_large = BenchmarkConfig(
            warmup_iterations=2,
            min_iterations=5,
            target_time_seconds=10.0,
        )
        runner_large = BenchmarkRunner(config_large)
        
        def write_10mb():
            file_counter[0] += 1
            path = os.path.join(temp_dir, f"file_{file_counter[0]}.bin")
            with open(path, 'wb') as f:
                f.write(data_10mb)
            return path
        
        result = runner_large.run(write_10mb, "Raw File Write (10 MB)", data_size=10*1024*1024)
        print(result)
        results["raw_write_10mb"] = result
        
        # Read benchmarks - create files first
        test_file_1kb = os.path.join(temp_dir, "read_test_1kb.bin")
        test_file_1mb = os.path.join(temp_dir, "read_test_1mb.bin")
        test_file_10mb = os.path.join(temp_dir, "read_test_10mb.bin")
        
        with open(test_file_1kb, 'wb') as f:
            f.write(data_1kb)
        with open(test_file_1mb, 'wb') as f:
            f.write(data_1mb)
        with open(test_file_10mb, 'wb') as f:
            f.write(data_10mb)
        
        def read_1kb():
            with open(test_file_1kb, 'rb') as f:
                return f.read()
        
        result = runner.run(read_1kb, "Raw File Read (1 KB)", data_size=1024)
        print(result)
        results["raw_read_1kb"] = result
        
        def read_1mb():
            with open(test_file_1mb, 'rb') as f:
                return f.read()
        
        result = runner.run(read_1mb, "Raw File Read (1 MB)", data_size=1024*1024)
        print(result)
        results["raw_read_1mb"] = result
        
        def read_10mb():
            with open(test_file_10mb, 'rb') as f:
                return f.read()
        
        result = runner_large.run(read_10mb, "Raw File Read (10 MB)", data_size=10*1024*1024)
        print(result)
        results["raw_read_10mb"] = result
        
    finally:
        shutil.rmtree(temp_dir, ignore_errors=True)
    
    # ==================================================================
    # 2. VIRTUAL METADATA INDEX OPERATIONS
    # ==================================================================
    
    print("\n📁 Virtual Metadata Index Operations")
    print("-" * 40)
    
    metadata_index = BenchMetadataIndex()
    
    file_counter = [0]
    
    def add_file_entry():
        file_counter[0] += 1
        path = f"/test_dir/file_{file_counter[0]}.txt"
        return metadata_index.add_file(path, size=1024, scatter_id=f"scatter_{file_counter[0]}")
    
    # Pre-populate with some files
    for i in range(1000):
        metadata_index.add_file(f"/bench_dir/file_{i}.txt", size=1024, scatter_id=f"id_{i}")
    
    result = runner.run(add_file_entry, "Add File to Metadata Index")
    print(result)
    results["metadata_add"] = result
    
    def lookup_file():
        idx = secrets.randbelow(1000)
        return metadata_index.get_file(f"/bench_dir/file_{idx}.txt")
    
    result = runner.run(lookup_file, "Metadata Lookup (random, 1000 files)")
    print(result)
    results["metadata_lookup"] = result
    
    def list_directory():
        return metadata_index.list_directory("/bench_dir")
    
    result = runner.run(list_directory, "List Directory (1000 files)")
    print(result)
    results["metadata_listdir"] = result
    
    def update_file_entry():
        idx = secrets.randbelow(1000)
        return metadata_index.update_file(f"/bench_dir/file_{idx}.txt", size=2048)
    
    result = runner.run(update_file_entry, "Update File Metadata")
    print(result)
    results["metadata_update"] = result
    
    # ==================================================================
    # 3. TRANSACTION MANAGEMENT
    # ==================================================================
    
    print("\n🔄 Transaction Management Operations")
    print("-" * 40)
    
    tx_manager = BenchTransactionManager()
    
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
    
    def transaction_with_ops():
        tx_id = tx_manager.begin_transaction()
        tx_manager.record_operation(tx_id, "CREATE", {"path": "/test.txt", "data": b"x"*100})
        tx_manager.record_operation(tx_id, "WRITE", {"path": "/test.txt", "data": b"y"*100})
        tx_manager.commit_transaction(tx_id)
        return tx_id
    
    result = runner.run(transaction_with_ops, "Transaction with 2 Operations")
    print(result)
    results["tx_with_ops"] = result
    
    def transaction_with_many_ops():
        tx_id = tx_manager.begin_transaction()
        for i in range(10):
            tx_manager.record_operation(tx_id, "WRITE", {"path": f"/file_{i}.txt", "data": b"x"*100})
        tx_manager.commit_transaction(tx_id)
        return tx_id
    
    result = runner.run(transaction_with_many_ops, "Transaction with 10 Operations")
    print(result)
    results["tx_with_10_ops"] = result
    
    # ==================================================================
    # 4. SCATTER/GATHER WITH FILESYSTEM I/O
    # ==================================================================
    
    if HAS_CORE:
        print("\n📊 Scatter + File I/O Combined Operations")
        print("-" * 40)
        
        temp_dir = tempfile.mkdtemp(prefix="sigmavault_scatter_io_bench_")
        
        try:
            test_key = secrets.token_bytes(64)
            key_state = KeyState.derive(test_key)
            
            # Use 100MB medium for benchmarks
            engine = DimensionalScatterEngine(key_state, medium_size=100 * 1024 * 1024)
            
            data_1kb = secrets.token_bytes(1024)
            file_counter = [0]
            
            def scatter_and_write():
                """Scatter data and write metadata to disk."""
                file_counter[0] += 1
                file_id = f"bench_file_{file_counter[0]}".encode()
                
                # Scatter the data
                scattered = engine.scatter(file_id, data_1kb)
                
                # Write scatter metadata to file (simulating persistence)
                meta_path = os.path.join(temp_dir, f"bench_file_{file_counter[0]}.meta")
                with open(meta_path, 'wb') as f:
                    # Serialize basic info
                    f.write(file_id)
                
                return scattered
            
            result = runner.run(scatter_and_write, "Scatter + Write Metadata (1 KB)", data_size=1024)
            print(result)
            results["scatter_write_1kb"] = result
            
            # Pre-scatter some data for gather test
            pre_scattered = engine.scatter(b"pre_test", data_1kb)
            
            def gather_and_read():
                """Gather data (simulating read from scattered storage)."""
                return engine.gather(pre_scattered)
            
            result = runner.run(gather_and_read, "Gather + Read (1 KB)", data_size=1024)
            print(result)
            results["gather_read_1kb"] = result
            
        finally:
            shutil.rmtree(temp_dir, ignore_errors=True)
    else:
        print("\n⚠️ Core module not available, skipping Scatter+I/O benchmarks")
    
    # ==================================================================
    # 5. CONCURRENT ACCESS SIMULATION
    # ==================================================================
    
    print("\n🔀 Concurrent Access Simulation")
    print("-" * 40)
    
    # Create a fresh index and transaction manager
    concurrent_index = BenchMetadataIndex()
    concurrent_tx = BenchTransactionManager()
    
    # Pre-populate
    for i in range(100):
        concurrent_index.add_file(f"/concurrent/file_{i}.txt", size=1024, scatter_id=f"id_{i}")
    
    def mixed_metadata_ops():
        """Simulate mixed metadata workload."""
        for _ in range(10):
            op = secrets.randbelow(4)
            idx = secrets.randbelow(100)
            
            if op == 0:
                # Read
                concurrent_index.get_file(f"/concurrent/file_{idx}.txt")
            elif op == 1:
                # Update
                concurrent_index.update_file(f"/concurrent/file_{idx}.txt", size=secrets.randbelow(10000))
            elif op == 2:
                # List
                concurrent_index.list_directory("/concurrent")
            else:
                # Add new file
                concurrent_index.add_file(f"/concurrent/new_{secrets.token_hex(4)}.txt", 
                                         size=1024, scatter_id=secrets.token_hex(8))
    
    result = runner.run(mixed_metadata_ops, "Mixed Metadata Operations (10 ops)")
    print(result)
    results["mixed_metadata_ops"] = result
    
    def mixed_transaction_ops():
        """Simulate transactional workload."""
        tx_id = concurrent_tx.begin_transaction()
        for i in range(5):
            concurrent_tx.record_operation(tx_id, "UPDATE", {"idx": i, "data": secrets.token_bytes(50)})
        
        if secrets.randbelow(10) < 8:  # 80% commit
            concurrent_tx.commit_transaction(tx_id)
        else:
            concurrent_tx.rollback_transaction(tx_id)
    
    result = runner.run(mixed_transaction_ops, "Transactional Workload (5 ops, 80% commit)")
    print(result)
    results["mixed_transaction_ops"] = result
    
    return results


if __name__ == "__main__":
    run_filesystem_benchmarks()
