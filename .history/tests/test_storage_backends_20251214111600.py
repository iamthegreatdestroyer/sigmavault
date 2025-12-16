"""
ΣVAULT Storage Backend Unit Tests

Comprehensive tests for FileStorageBackend and MemoryStorageBackend.
"""

import os
import pytest
import tempfile
import threading
from pathlib import Path
from unittest.mock import patch, MagicMock

from sigmavault.drivers.storage.base import (
    StorageBackend,
    StorageCapabilities,
    StorageStats,
    StorageError,
    StorageReadError,
    StorageWriteError,
    StorageCapacityError,
)
from drivers.storage.file_backend import FileStorageBackend
from drivers.storage.memory_backend import MemoryStorageBackend


class TestStorageCapabilities:
    """Test StorageCapabilities flag enum."""
    
    def test_capability_flags_are_distinct(self):
        """Each capability should have a unique bit."""
        caps = [
            StorageCapabilities.SPARSE,
            StorageCapabilities.TRUNCATE,
            StorageCapabilities.ATOMIC_WRITE,
            StorageCapabilities.RANGE_READ,
            StorageCapabilities.CONCURRENT,
            StorageCapabilities.PERSISTENT,
            StorageCapabilities.SEEKABLE,
        ]
        
        # Each flag should be a power of 2
        values = [c.value for c in caps]
        assert len(values) == len(set(values)), "Capability flags must be unique"
    
    def test_capability_combination(self):
        """Test combining capabilities."""
        caps = StorageCapabilities.SPARSE | StorageCapabilities.TRUNCATE
        
        assert StorageCapabilities.SPARSE in caps
        assert StorageCapabilities.TRUNCATE in caps
        assert StorageCapabilities.ATOMIC_WRITE not in caps
    
    def test_capability_none(self):
        """Test NONE capability."""
        assert StorageCapabilities.NONE.value == 0


class TestMemoryStorageBackend:
    """Test MemoryStorageBackend implementation."""
    
    @pytest.fixture
    def memory_backend(self):
        """Create a memory backend for testing."""
        backend = MemoryStorageBackend(size=1024)  # 1 KB
        yield backend
    
    @pytest.fixture
    def large_memory_backend(self):
        """Create a larger memory backend."""
        backend = MemoryStorageBackend(size=1024 * 1024, max_size=10 * 1024 * 1024)
        yield backend
    
    def test_creation(self, memory_backend):
        """Test backend creation."""
        assert memory_backend.size() == 1024
        assert memory_backend.max_size == 1024
    
    def test_creation_with_max_size(self):
        """Test backend creation with max_size."""
        backend = MemoryStorageBackend(size=1024, max_size=4096)
        assert backend.size() == 1024
        assert backend.max_size == 4096
    
    def test_write_and_read(self, memory_backend):
        """Test basic write and read."""
        data = b"Hello, World!"
        
        written = memory_backend.write(0, data)
        assert written == len(data)
        
        read_data = memory_backend.read(0, len(data))
        assert read_data == data
    
    def test_write_at_offset(self, memory_backend):
        """Test writing at different offsets."""
        memory_backend.write(0, b"AAAA")
        memory_backend.write(4, b"BBBB")
        memory_backend.write(8, b"CCCC")
        
        assert memory_backend.read(0, 4) == b"AAAA"
        assert memory_backend.read(4, 4) == b"BBBB"
        assert memory_backend.read(8, 4) == b"CCCC"
        assert memory_backend.read(0, 12) == b"AAAABBBBCCCC"
    
    def test_read_unwritten_region(self, memory_backend):
        """Reading unwritten regions should return zeros."""
        # Write at offset 100
        memory_backend.write(100, b"data")
        
        # Read from offset 0 (unwritten)
        data = memory_backend.read(0, 50)
        assert data == b'\x00' * 50
    
    def test_read_past_logical_size(self, memory_backend):
        """Reading past logical size should return zeros."""
        data = memory_backend.read(2000, 100)  # Beyond 1024 size
        assert data == b'\x00' * 100
    
    def test_write_expands_capacity(self, large_memory_backend):
        """Writing beyond initial size should expand buffer."""
        # Write beyond initial size
        offset = 512 * 1024  # 512 KB
        data = b"expanded"
        
        large_memory_backend.write(offset, data)
        
        assert large_memory_backend.actual_size >= offset + len(data)
        assert large_memory_backend.read(offset, len(data)) == data
    
    def test_write_exceeds_max_size(self):
        """Writing beyond max_size should raise error."""
        backend = MemoryStorageBackend(size=100, max_size=200)
        
        with pytest.raises(StorageCapacityError):
            backend.write(150, b"X" * 100)  # Would exceed 200
    
    def test_truncate(self, memory_backend):
        """Test truncate operation."""
        memory_backend.write(0, b"Hello, World!")
        memory_backend.truncate(5)
        
        assert memory_backend.size() == 5
    
    def test_truncate_exceeds_max(self):
        """Truncate beyond max_size should raise error."""
        backend = MemoryStorageBackend(size=100, max_size=200)
        
        with pytest.raises(StorageCapacityError):
            backend.truncate(300)
    
    def test_clear(self, memory_backend):
        """Test clear operation."""
        memory_backend.write(0, b"secret data")
        memory_backend.clear()
        
        # Data should be zeroed
        data = memory_backend.get_data()
        assert all(b == 0 for b in data)
    
    def test_capabilities(self, memory_backend):
        """Test capability flags."""
        caps = memory_backend.capabilities
        
        assert StorageCapabilities.SPARSE in caps
        assert StorageCapabilities.TRUNCATE in caps
        assert StorageCapabilities.RANGE_READ in caps
        assert StorageCapabilities.CONCURRENT in caps
        assert StorageCapabilities.SEEKABLE in caps
        # Memory is NOT persistent
        assert StorageCapabilities.PERSISTENT not in caps
    
    def test_is_not_persistent(self, memory_backend):
        """Memory backend should not be persistent."""
        assert memory_backend.is_persistent is False
    
    def test_sync_is_noop(self, memory_backend):
        """Sync should be a no-op for memory backend."""
        # Should not raise
        memory_backend.sync()
    
    def test_negative_offset_raises(self, memory_backend):
        """Negative offset should raise ValueError."""
        with pytest.raises(ValueError):
            memory_backend.read(-1, 10)
        
        with pytest.raises(ValueError):
            memory_backend.write(-1, b"data")
    
    def test_stats_tracking(self, memory_backend):
        """Test that stats are tracked."""
        memory_backend.write(0, b"test")
        memory_backend.read(0, 4)
        
        stats = memory_backend.stats
        assert stats.read_count >= 1
        assert stats.write_count >= 1
        assert stats.bytes_read >= 4
        assert stats.bytes_written >= 4
    
    def test_thread_safety(self, large_memory_backend):
        """Test concurrent read/write operations."""
        errors = []
        
        def writer(offset, data, count):
            try:
                for _ in range(count):
                    large_memory_backend.write(offset, data)
            except Exception as e:
                errors.append(e)
        
        def reader(offset, size, count):
            try:
                for _ in range(count):
                    large_memory_backend.read(offset, size)
            except Exception as e:
                errors.append(e)
        
        threads = [
            threading.Thread(target=writer, args=(0, b"A" * 100, 100)),
            threading.Thread(target=writer, args=(200, b"B" * 100, 100)),
            threading.Thread(target=reader, args=(0, 50, 100)),
            threading.Thread(target=reader, args=(100, 50, 100)),
        ]
        
        for t in threads:
            t.start()
        
        for t in threads:
            t.join()
        
        assert len(errors) == 0, f"Thread errors: {errors}"
    
    def test_repr(self, memory_backend):
        """Test string representation."""
        repr_str = repr(memory_backend)
        assert "MemoryStorageBackend" in repr_str
        assert "size=1024" in repr_str


class TestFileStorageBackend:
    """Test FileStorageBackend implementation."""
    
    @pytest.fixture
    def temp_file(self):
        """Create a temporary file path (not existing) for testing."""
        fd, path = tempfile.mkstemp(suffix='.vault')
        os.close(fd)
        # Remove the file so backend creates fresh
        os.unlink(path)
        yield Path(path)
        # Cleanup - may not exist if test cleaned up
        try:
            if Path(path).exists():
                os.unlink(path)
        except (OSError, PermissionError):
            pass  # Windows file locking issue
    
    @pytest.fixture
    def file_backend(self, temp_file):
        """Create a file backend for testing."""
        backend = FileStorageBackend(temp_file, size=1024 * 1024, create=True)  # 1 MB
        yield backend
        backend.close()
    
    def test_creation(self, file_backend, temp_file):
        """Test backend creation."""
        assert file_backend.size() == 1024 * 1024
        assert temp_file.exists()
    
    def test_write_and_read(self, file_backend):
        """Test basic write and read."""
        data = b"Hello, World!"
        
        written = file_backend.write(0, data)
        assert written == len(data)
        
        read_data = file_backend.read(0, len(data))
        assert read_data == data
    
    def test_write_at_offset(self, file_backend):
        """Test writing at different offsets."""
        file_backend.write(0, b"AAAA")
        file_backend.write(1000, b"BBBB")
        file_backend.write(10000, b"CCCC")
        
        assert file_backend.read(0, 4) == b"AAAA"
        assert file_backend.read(1000, 4) == b"BBBB"
        assert file_backend.read(10000, 4) == b"CCCC"
    
    def test_sparse_file_holes(self, file_backend):
        """Test that unwritten regions are zeros (sparse)."""
        # Write only at far offset
        file_backend.write(500000, b"data")
        
        # Read from beginning (unwritten)
        data = file_backend.read(0, 100)
        assert data == b'\x00' * 100
    
    def test_sync(self, file_backend):
        """Test sync flushes to disk."""
        file_backend.write(0, b"important data")
        file_backend.sync()  # Should not raise
    
    def test_truncate(self, file_backend):
        """Test truncate operation."""
        original_size = file_backend.size()
        file_backend.truncate(original_size // 2)
        
        assert file_backend.size() == original_size // 2
    
    def test_capabilities(self, file_backend):
        """Test capability flags."""
        caps = file_backend.capabilities
        
        assert StorageCapabilities.SPARSE in caps
        assert StorageCapabilities.TRUNCATE in caps
        assert StorageCapabilities.RANGE_READ in caps
        assert StorageCapabilities.CONCURRENT in caps
        assert StorageCapabilities.PERSISTENT in caps
        assert StorageCapabilities.SEEKABLE in caps
    
    def test_is_persistent(self, file_backend):
        """File backend should be persistent."""
        # Persistence is indicated by PERSISTENT capability
        assert StorageCapabilities.PERSISTENT in file_backend.capabilities
    
    def test_stats_tracking(self, file_backend):
        """Test that stats are tracked."""
        file_backend.write(0, b"test")
        file_backend.read(0, 4)
        
        stats = file_backend.stats
        assert stats.read_count >= 1
        assert stats.write_count >= 1
    
    def test_negative_offset_raises(self, file_backend):
        """Negative offset should raise ValueError."""
        with pytest.raises(ValueError):
            file_backend.read(-1, 10)
        
        with pytest.raises(ValueError):
            file_backend.write(-1, b"data")
    
    def test_persistence_across_reopen(self, temp_file):
        """Test that data persists when reopening."""
        # Write data with fresh file
        backend1 = FileStorageBackend(temp_file, size=1024, create=True)
        backend1.write(0, b"persistent data")
        backend1.sync()
        backend1.close()
        
        # Reopen and read
        backend2 = FileStorageBackend(temp_file, create=False)
        try:
            data = backend2.read(0, 15)
            assert data == b"persistent data"
        finally:
            backend2.close()
    
    def test_thread_safety(self, file_backend):
        """Test concurrent operations."""
        errors = []
        
        def writer(offset, data, count):
            try:
                for _ in range(count):
                    file_backend.write(offset, data)
            except Exception as e:
                errors.append(e)
        
        def reader(offset, size, count):
            try:
                for _ in range(count):
                    file_backend.read(offset, size)
            except Exception as e:
                errors.append(e)
        
        threads = [
            threading.Thread(target=writer, args=(0, b"A" * 100, 50)),
            threading.Thread(target=writer, args=(1000, b"B" * 100, 50)),
            threading.Thread(target=reader, args=(0, 50, 50)),
            threading.Thread(target=reader, args=(500, 50, 50)),
        ]
        
        for t in threads:
            t.start()
        
        for t in threads:
            t.join()
        
        assert len(errors) == 0, f"Thread errors: {errors}"


class TestStorageBackendInterface:
    """Test StorageBackend ABC interface compliance."""
    
    def test_memory_backend_is_storage_backend(self):
        """MemoryStorageBackend should be a StorageBackend."""
        backend = MemoryStorageBackend(size=100)
        assert isinstance(backend, StorageBackend)
    
    def test_file_backend_is_storage_backend(self):
        """FileStorageBackend should be a StorageBackend."""
        fd, path = tempfile.mkstemp()
        os.close(fd)
        
        try:
            backend = FileStorageBackend(Path(path), size=100)
            assert isinstance(backend, StorageBackend)
            backend.close()
        finally:
            os.unlink(path)
    
    def test_backend_interface_methods(self):
        """Test that all interface methods exist."""
        backend = MemoryStorageBackend(size=100)
        
        # Core methods
        assert hasattr(backend, 'read')
        assert hasattr(backend, 'write')
        assert hasattr(backend, 'size')
        assert hasattr(backend, 'sync')
        assert hasattr(backend, 'capabilities')
        
        # Optional methods
        assert hasattr(backend, 'truncate')
        assert hasattr(backend, 'read_chunks')
        assert hasattr(backend, 'write_chunks')


class TestStorageStats:
    """Test StorageStats dataclass."""
    
    def test_default_values(self):
        """Test default stat values from a fresh backend."""
        backend = MemoryStorageBackend(size=1000)
        stats = backend.stats
        
        assert stats.read_count == 0
        assert stats.write_count == 0
        assert stats.bytes_read == 0
        assert stats.bytes_written == 0
        assert stats.total_size == 1000
        assert stats.used_size >= 0
    
    def test_stats_update(self):
        """Test that stats update correctly."""
        backend = MemoryStorageBackend(size=1000)
        
        backend.write(0, b"test")
        backend.write(10, b"data")
        backend.read(0, 20)
        
        stats = backend.stats
        assert stats.write_count == 2
        assert stats.read_count == 1
        assert stats.bytes_written == 8
        assert stats.bytes_read == 20


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
