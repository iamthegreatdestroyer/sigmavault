"""
ΣVAULT Storage Backend - Abstract Base Interface

Defines the abstract interface that all storage backends must implement.
This enables ΣVAULT to operate on local files, cloud storage, or any
custom storage medium while maintaining consistent behavior.

Design Philosophy:
    - Storage backends are byte-addressable (like a block device)
    - Supports random access reads and writes
    - Backends declare their capabilities via StorageCapabilities
    - All operations are synchronous (async wrapper available)
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass
from enum import Flag, auto
from typing import Optional, Iterator
import threading


class StorageError(Exception):
    """Base exception for all storage backend errors."""
    pass


class StorageReadError(StorageError):
    """Raised when a read operation fails."""
    pass


class StorageWriteError(StorageError):
    """Raised when a write operation fails."""
    pass


class StorageCapacityError(StorageError):
    """Raised when storage capacity is exceeded."""
    pass


class StorageNotFoundError(StorageError):
    """Raised when storage medium doesn't exist."""
    pass


class StorageCapabilities(Flag):
    """Capabilities that a storage backend may support."""
    
    NONE = 0
    SPARSE = auto()          # Supports sparse allocation (holes)
    TRUNCATE = auto()        # Supports resize/truncate operations
    ATOMIC_WRITE = auto()    # Writes are atomic (all-or-nothing)
    RANGE_READ = auto()      # Efficient range/partial reads
    CONCURRENT = auto()      # Thread-safe operations
    PERSISTENT = auto()      # Data survives process restart
    SEEKABLE = auto()        # Random access without sequential read


@dataclass
class StorageStats:
    """Statistics about storage usage and performance."""
    
    total_size: int          # Total capacity in bytes
    used_size: int           # Bytes currently used
    read_count: int          # Number of read operations
    write_count: int         # Number of write operations
    bytes_read: int          # Total bytes read
    bytes_written: int       # Total bytes written
    
    @property
    def utilization(self) -> float:
        """Return storage utilization as fraction (0.0-1.0)."""
        if self.total_size == 0:
            return 0.0
        return self.used_size / self.total_size


class StorageBackend(ABC):
    """
    Abstract base class for ΣVAULT storage backends.
    
    All storage backends must implement this interface to be compatible
    with the dimensional scattering engine. The interface treats storage
    as a byte-addressable medium, similar to a block device.
    
    Thread Safety:
        Implementations should be thread-safe if they set CONCURRENT
        capability. The base class provides optional locking via
        _with_lock() context manager.
    
    Example:
        >>> backend = FileStorageBackend("/path/to/vault.dat", size=1_000_000_000)
        >>> backend.write(0, b"Hello ΣVAULT")
        >>> backend.read(0, 12)
        b'Hello ΣVAULT'
        >>> backend.sync()
    """
    
    def __init__(self, enable_stats: bool = True):
        """
        Initialize the storage backend.
        
        Args:
            enable_stats: Whether to track read/write statistics.
        """
        self._lock = threading.RLock()
        self._enable_stats = enable_stats
        self._stats = StorageStats(
            total_size=0,
            used_size=0,
            read_count=0,
            write_count=0,
            bytes_read=0,
            bytes_written=0,
        )
    
    # ========================================================================
    # Abstract Methods (Must Implement)
    # ========================================================================
    
    @abstractmethod
    def read(self, offset: int, size: int) -> bytes:
        """
        Read bytes from storage at the given offset.
        
        Args:
            offset: Byte offset from start of storage (0-indexed).
            size: Number of bytes to read.
        
        Returns:
            Bytes read from storage. May be shorter than requested
            if reading past end of storage.
        
        Raises:
            StorageReadError: If read operation fails.
            ValueError: If offset is negative.
        
        Note:
            Implementations should update stats via _record_read().
        """
        pass
    
    @abstractmethod
    def write(self, offset: int, data: bytes) -> int:
        """
        Write bytes to storage at the given offset.
        
        Args:
            offset: Byte offset from start of storage (0-indexed).
            data: Bytes to write.
        
        Returns:
            Number of bytes written.
        
        Raises:
            StorageWriteError: If write operation fails.
            StorageCapacityError: If write would exceed capacity.
            ValueError: If offset is negative.
        
        Note:
            Implementations should update stats via _record_write().
        """
        pass
    
    @abstractmethod
    def size(self) -> int:
        """
        Return the total size of the storage medium in bytes.
        
        Returns:
            Total capacity in bytes.
        """
        pass
    
    @abstractmethod
    def sync(self) -> None:
        """
        Ensure all pending writes are persisted to storage.
        
        For local filesystems, this calls fsync().
        For cloud storage, this ensures all uploads are complete.
        
        Raises:
            StorageError: If sync operation fails.
        """
        pass
    
    @property
    @abstractmethod
    def capabilities(self) -> StorageCapabilities:
        """
        Return the capabilities of this storage backend.
        
        Returns:
            Bitflags indicating supported features.
        """
        pass
    
    # ========================================================================
    # Optional Methods (Override if Supported)
    # ========================================================================
    
    def truncate(self, size: int) -> None:
        """
        Resize the storage medium.
        
        Args:
            size: New size in bytes.
        
        Raises:
            StorageError: If truncate is not supported.
            StorageCapacityError: If size exceeds maximum.
        """
        if not (self.capabilities & StorageCapabilities.TRUNCATE):
            raise StorageError(
                f"{self.__class__.__name__} does not support truncate"
            )
        raise NotImplementedError("Subclass must implement truncate()")
    
    def read_chunks(
        self,
        offset: int,
        size: int,
        chunk_size: int = 64 * 1024
    ) -> Iterator[bytes]:
        """
        Read data in chunks (for memory-efficient large reads).
        
        Args:
            offset: Starting byte offset.
            size: Total bytes to read.
            chunk_size: Size of each chunk (default 64KB).
        
        Yields:
            Chunks of data up to chunk_size bytes.
        """
        remaining = size
        current_offset = offset
        
        while remaining > 0:
            read_size = min(remaining, chunk_size)
            chunk = self.read(current_offset, read_size)
            if not chunk:
                break
            yield chunk
            current_offset += len(chunk)
            remaining -= len(chunk)
    
    def write_chunks(
        self,
        offset: int,
        data_iterator: Iterator[bytes]
    ) -> int:
        """
        Write data from an iterator in chunks.
        
        Args:
            offset: Starting byte offset.
            data_iterator: Iterator yielding bytes chunks.
        
        Returns:
            Total bytes written.
        """
        total_written = 0
        current_offset = offset
        
        for chunk in data_iterator:
            written = self.write(current_offset, chunk)
            total_written += written
            current_offset += written
        
        return total_written
    
    def fill(self, offset: int, size: int, value: int = 0) -> int:
        """
        Fill a region with a repeated byte value.
        
        Args:
            offset: Starting byte offset.
            size: Number of bytes to fill.
            value: Byte value to fill with (0-255).
        
        Returns:
            Number of bytes written.
        """
        chunk_size = 64 * 1024
        fill_byte = bytes([value & 0xFF])
        chunk = fill_byte * chunk_size
        
        total_written = 0
        remaining = size
        current_offset = offset
        
        while remaining > 0:
            write_size = min(remaining, chunk_size)
            written = self.write(current_offset, chunk[:write_size])
            total_written += written
            current_offset += written
            remaining -= written
        
        return total_written
    
    def copy_range(
        self,
        src_offset: int,
        dst_offset: int,
        size: int,
        chunk_size: int = 64 * 1024
    ) -> int:
        """
        Copy a range of bytes within the storage.
        
        Args:
            src_offset: Source byte offset.
            dst_offset: Destination byte offset.
            size: Number of bytes to copy.
            chunk_size: Size of copy chunks.
        
        Returns:
            Number of bytes copied.
        """
        # Handle overlapping regions
        if src_offset < dst_offset < src_offset + size:
            # Copy backwards to avoid overwriting source
            return self._copy_range_backward(
                src_offset, dst_offset, size, chunk_size
            )
        
        total_copied = 0
        remaining = size
        src_pos = src_offset
        dst_pos = dst_offset
        
        while remaining > 0:
            copy_size = min(remaining, chunk_size)
            data = self.read(src_pos, copy_size)
            if not data:
                break
            written = self.write(dst_pos, data)
            total_copied += written
            src_pos += written
            dst_pos += written
            remaining -= written
        
        return total_copied
    
    def _copy_range_backward(
        self,
        src_offset: int,
        dst_offset: int,
        size: int,
        chunk_size: int
    ) -> int:
        """Copy range backwards for overlapping regions."""
        total_copied = 0
        remaining = size
        
        while remaining > 0:
            copy_size = min(remaining, chunk_size)
            src_pos = src_offset + remaining - copy_size
            dst_pos = dst_offset + remaining - copy_size
            
            data = self.read(src_pos, copy_size)
            if not data:
                break
            written = self.write(dst_pos, data)
            total_copied += written
            remaining -= copy_size
        
        return total_copied
    
    # ========================================================================
    # Convenience Properties
    # ========================================================================
    
    @property
    def supports_sparse(self) -> bool:
        """Whether backend supports sparse allocation."""
        return bool(self.capabilities & StorageCapabilities.SPARSE)
    
    @property
    def supports_truncate(self) -> bool:
        """Whether backend supports resize operations."""
        return bool(self.capabilities & StorageCapabilities.TRUNCATE)
    
    @property
    def is_persistent(self) -> bool:
        """Whether data survives process restart."""
        return bool(self.capabilities & StorageCapabilities.PERSISTENT)
    
    @property
    def is_concurrent(self) -> bool:
        """Whether operations are thread-safe."""
        return bool(self.capabilities & StorageCapabilities.CONCURRENT)
    
    @property
    def stats(self) -> StorageStats:
        """Return current storage statistics."""
        stats = self._stats
        stats.total_size = self.size()
        return stats
    
    # ========================================================================
    # Statistics Helpers
    # ========================================================================
    
    def _record_read(self, bytes_read: int) -> None:
        """Record a read operation in statistics."""
        if self._enable_stats:
            with self._lock:
                self._stats.read_count += 1
                self._stats.bytes_read += bytes_read
    
    def _record_write(self, bytes_written: int) -> None:
        """Record a write operation in statistics."""
        if self._enable_stats:
            with self._lock:
                self._stats.write_count += 1
                self._stats.bytes_written += bytes_written
    
    # ========================================================================
    # Context Manager Support
    # ========================================================================
    
    def __enter__(self) -> "StorageBackend":
        """Enter context manager."""
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb) -> None:
        """Exit context manager, syncing data."""
        self.sync()
    
    # ========================================================================
    # String Representation
    # ========================================================================
    
    def __repr__(self) -> str:
        """Return string representation."""
        return (
            f"{self.__class__.__name__}("
            f"size={self.size()}, "
            f"capabilities={self.capabilities})"
        )
