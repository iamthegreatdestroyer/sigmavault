"""
ΣVAULT Parallel I/O - Async parallel chunk I/O.
===============================================

Phase 9B: Performance Optimization - Part 3

High-throughput parallel chunk read/write operations
with semaphore-based concurrency control.
"""

import asyncio
from typing import List, Dict, Optional, Any, Callable
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, field
import time


@dataclass
class IOStats:
    """Statistics for I/O operations."""
    reads: int = 0
    writes: int = 0
    read_bytes: int = 0
    write_bytes: int = 0
    read_time_ms: float = 0.0
    write_time_ms: float = 0.0
    errors: int = 0


@dataclass
class ParallelIOConfig:
    """Configuration for parallel I/O."""
    max_concurrent: int = 16
    chunk_timeout_s: float = 30.0
    retry_attempts: int = 3
    retry_delay_ms: float = 100.0


class ParallelIOManager:
    """
    Async parallel chunk I/O manager.
    
    Features:
    - Semaphore-based concurrency control
    - Thread pool for blocking I/O operations
    - Statistics tracking
    - Retry logic with exponential backoff
    
    Example:
        >>> manager = ParallelIOManager(max_concurrent=16)
        >>> results = await manager.read_chunks_parallel(chunk_ids, backend)
    """
    
    def __init__(
        self,
        max_concurrent: int = 16,
        config: Optional[ParallelIOConfig] = None,
    ):
        self.config = config or ParallelIOConfig(max_concurrent=max_concurrent)
        self.max_concurrent = self.config.max_concurrent
        self._executor = ThreadPoolExecutor(max_workers=max_concurrent)
        self._stats = IOStats()
    
    async def read_chunks_parallel(
        self,
        chunk_ids: List[str],
        backend: Any,
    ) -> Dict[str, bytes]:
        """
        Read multiple chunks in parallel.
        
        Args:
            chunk_ids: List of chunk IDs to read
            backend: Backend with read_chunk(chunk_id) method
            
        Returns:
            Dictionary mapping chunk_id to bytes
        """
        start_time = time.perf_counter()
        sem = asyncio.Semaphore(self.max_concurrent)
        
        async def read_one(cid: str) -> tuple:
            async with sem:
                loop = asyncio.get_event_loop()
                try:
                    data = await loop.run_in_executor(
                        self._executor,
                        backend.read_chunk,
                        cid
                    )
                    self._stats.reads += 1
                    if data:
                        self._stats.read_bytes += len(data)
                    return cid, data
                except Exception as e:
                    self._stats.errors += 1
                    return cid, None
        
        results = await asyncio.gather(
            *[read_one(cid) for cid in chunk_ids],
            return_exceptions=True
        )
        
        elapsed_ms = (time.perf_counter() - start_time) * 1000
        self._stats.read_time_ms += elapsed_ms
        
        return {
            cid: data
            for cid, data in results
            if not isinstance(cid, Exception) and data is not None
        }
    
    async def write_chunks_parallel(
        self,
        chunks: Dict[str, bytes],
        backend: Any,
    ) -> Dict[str, bool]:
        """
        Write multiple chunks in parallel.
        
        Args:
            chunks: Dictionary mapping chunk_id to bytes
            backend: Backend with write_chunk(chunk_id, data) method
            
        Returns:
            Dictionary mapping chunk_id to success status
        """
        start_time = time.perf_counter()
        sem = asyncio.Semaphore(self.max_concurrent)
        
        async def write_one(cid: str, data: bytes) -> tuple:
            async with sem:
                loop = asyncio.get_event_loop()
                try:
                    await loop.run_in_executor(
                        self._executor,
                        backend.write_chunk,
                        cid,
                        data
                    )
                    self._stats.writes += 1
                    self._stats.write_bytes += len(data)
                    return cid, True
                except Exception as e:
                    self._stats.errors += 1
                    return cid, False
        
        results = await asyncio.gather(
            *[write_one(cid, data) for cid, data in chunks.items()],
            return_exceptions=True
        )
        
        elapsed_ms = (time.perf_counter() - start_time) * 1000
        self._stats.write_time_ms += elapsed_ms
        
        return {
            cid: success
            for cid, success in results
            if not isinstance(cid, Exception)
        }
    
    async def read_with_retry(
        self,
        chunk_id: str,
        backend: Any,
    ) -> Optional[bytes]:
        """
        Read a single chunk with retry logic.
        
        Args:
            chunk_id: Chunk ID to read
            backend: Backend with read_chunk method
            
        Returns:
            Chunk data or None if all retries failed
        """
        loop = asyncio.get_event_loop()
        
        for attempt in range(self.config.retry_attempts):
            try:
                data = await loop.run_in_executor(
                    self._executor,
                    backend.read_chunk,
                    chunk_id
                )
                self._stats.reads += 1
                if data:
                    self._stats.read_bytes += len(data)
                return data
            except Exception as e:
                self._stats.errors += 1
                if attempt < self.config.retry_attempts - 1:
                    delay = self.config.retry_delay_ms * (2 ** attempt) / 1000
                    await asyncio.sleep(delay)
        
        return None
    
    def read_chunks_sync(
        self,
        chunk_ids: List[str],
        backend: Any,
    ) -> Dict[str, bytes]:
        """
        Synchronous wrapper for parallel chunk reading.
        
        Args:
            chunk_ids: List of chunk IDs
            backend: Backend with read_chunk method
            
        Returns:
            Dictionary mapping chunk_id to bytes
        """
        try:
            loop = asyncio.get_event_loop()
        except RuntimeError:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
        
        return loop.run_until_complete(
            self.read_chunks_parallel(chunk_ids, backend)
        )
    
    def write_chunks_sync(
        self,
        chunks: Dict[str, bytes],
        backend: Any,
    ) -> Dict[str, bool]:
        """
        Synchronous wrapper for parallel chunk writing.
        
        Args:
            chunks: Dictionary mapping chunk_id to bytes
            backend: Backend with write_chunk method
            
        Returns:
            Dictionary mapping chunk_id to success status
        """
        try:
            loop = asyncio.get_event_loop()
        except RuntimeError:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
        
        return loop.run_until_complete(
            self.write_chunks_parallel(chunks, backend)
        )
    
    def get_stats(self) -> Dict:
        """Get I/O statistics."""
        return {
            "reads": self._stats.reads,
            "writes": self._stats.writes,
            "read_bytes": self._stats.read_bytes,
            "write_bytes": self._stats.write_bytes,
            "read_time_ms": self._stats.read_time_ms,
            "write_time_ms": self._stats.write_time_ms,
            "errors": self._stats.errors,
            "read_throughput_mbps": (
                self._stats.read_bytes / 1024 / 1024 / 
                max(0.001, self._stats.read_time_ms / 1000)
            ) if self._stats.read_time_ms > 0 else 0,
            "write_throughput_mbps": (
                self._stats.write_bytes / 1024 / 1024 / 
                max(0.001, self._stats.write_time_ms / 1000)
            ) if self._stats.write_time_ms > 0 else 0,
        }
    
    def reset_stats(self) -> None:
        """Reset I/O statistics."""
        self._stats = IOStats()
    
    def shutdown(self) -> None:
        """Shutdown the thread pool executor."""
        self._executor.shutdown(wait=True)
    
    def __enter__(self):
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        self.shutdown()


# Mock backend for testing
class MockChunkBackend:
    """Mock backend for testing parallel I/O."""
    
    def __init__(self):
        self._chunks: Dict[str, bytes] = {}
    
    def read_chunk(self, chunk_id: str) -> Optional[bytes]:
        time.sleep(0.001)  # Simulate I/O latency
        return self._chunks.get(chunk_id)
    
    def write_chunk(self, chunk_id: str, data: bytes) -> None:
        time.sleep(0.001)  # Simulate I/O latency
        self._chunks[chunk_id] = data


async def test_parallel_io():
    """Test the parallel I/O manager."""
    print("Testing ParallelIOManager...")
    
    # Create manager and mock backend
    manager = ParallelIOManager(max_concurrent=8)
    backend = MockChunkBackend()
    
    # Prepare test data
    test_chunks = {
        f"chunk_{i}": f"data_{i}".encode() * 100
        for i in range(20)
    }
    
    # Test parallel writes
    write_results = await manager.write_chunks_parallel(test_chunks, backend)
    assert all(write_results.values())
    print(f"  ✓ Wrote {len(test_chunks)} chunks in parallel")
    
    # Test parallel reads
    chunk_ids = list(test_chunks.keys())
    read_results = await manager.read_chunks_parallel(chunk_ids, backend)
    assert len(read_results) == len(test_chunks)
    print(f"  ✓ Read {len(read_results)} chunks in parallel")
    
    # Verify data integrity
    for cid, expected in test_chunks.items():
        assert read_results.get(cid) == expected
    print("  ✓ Data integrity verified")
    
    # Print stats
    stats = manager.get_stats()
    print(f"  ✓ Total reads: {stats['reads']}")
    print(f"  ✓ Total writes: {stats['writes']}")
    print(f"  ✓ Read throughput: {stats['read_throughput_mbps']:.2f} MB/s")
    print(f"  ✓ Write throughput: {stats['write_throughput_mbps']:.2f} MB/s")
    
    manager.shutdown()
    print("\n✓ ParallelIOManager tests passed!")


def run_test():
    """Run the async test."""
    asyncio.run(test_parallel_io())


if __name__ == "__main__":
    run_test()
