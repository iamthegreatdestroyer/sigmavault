"""
ΣVAULT Memory Storage Backend

In-memory storage backend implementation for testing and ephemeral vaults.

Features:
    - Zero-copy reads when possible
    - Automatic expansion up to max_size
    - No persistence (data lost on process exit)
    - Thread-safe operations
    - Useful for unit testing and development
"""

import threading
from typing import Optional

from .base import (
    StorageBackend,
    StorageCapabilities,
    StorageError,
    StorageReadError,
    StorageWriteError,
    StorageCapacityError,
)


class MemoryStorageBackend(StorageBackend):
    """
    In-memory storage backend using a bytearray.
    
    Stores all data in RAM - useful for testing, development,
    and temporary vaults that don't need persistence.
    
    Thread Safety:
        All operations are protected by a reentrant lock.
    
    Performance:
        - Read: O(size) - copy required
        - Write: O(size) - copy required  
        - Very fast for small/medium data
        - Memory-limited for large vaults
    
    Example:
        >>> backend = MemoryStorageBackend(size=1024*1024)  # 1 MB
        >>> backend.write(0, b"Hello")
        5
        >>> backend.read(0, 5)
        b'Hello'
    
    Args:
        size: Initial size of storage in bytes.
        max_size: Maximum size (for auto-expansion). Default: same as size.
        zero_fill: Whether to zero-fill on creation (default False).
    """
    
    def __init__(
        self,
        size: int = 10 * 1024 * 1024,  # 10 MB default
        max_size: Optional[int] = None,
        zero_fill: bool = False,
    ):
        super().__init__(enable_stats=True)
        
        if size < 0:
            raise ValueError(f"Size cannot be negative: {size}")
        
        self._max_size = max_size or size
        self._data_lock = threading.RLock()
        
        # Pre-allocate the buffer
        if zero_fill:
            self._data = bytearray(size)
        else:
            # Sparse allocation - only allocate what's needed
            self._data = bytearray()
            self._logical_size = size
    
    # ========================================================================
    # StorageBackend Interface Implementation
    # ========================================================================
    
    def read(self, offset: int, size: int) -> bytes:
        """
        Read bytes from memory at given offset.
        
        Args:
            offset: Byte offset from start.
            size: Number of bytes to read.
        
        Returns:
            Bytes read. Unwritten regions return zeros.
        
        Raises:
            ValueError: If offset is negative.
        """
        if offset < 0:
            raise ValueError(f"Offset cannot be negative: {offset}")
        
        if size <= 0:
            return b''
        
        with self._data_lock:
            logical_size = self._get_logical_size()
            
            # Clamp to actual data bounds
            if offset >= logical_size:
                # Reading past end - return zeros
                self._record_read(size)
                return bytes(size)
            
            end = min(offset + size, logical_size)
            actual_size = end - offset
            
            # Ensure buffer is large enough
            self._ensure_capacity(end)
            
            data = bytes(self._data[offset:end])
            
            # Pad with zeros if reading past actual data
            if len(data) < size:
                data += bytes(size - len(data))
            
            self._record_read(len(data))
            return data
    
    def write(self, offset: int, data: bytes) -> int:
        """
        Write bytes to memory at given offset.
        
        Args:
            offset: Byte offset from start.
            data: Bytes to write.
        
        Returns:
            Number of bytes written.
        
        Raises:
            StorageCapacityError: If write exceeds max_size.
            ValueError: If offset is negative.
        """
        if offset < 0:
            raise ValueError(f"Offset cannot be negative: {offset}")
        
        if not data:
            return 0
        
        end_offset = offset + len(data)
        
        with self._data_lock:
            # Check against max size
            if end_offset > self._max_size:
                raise StorageCapacityError(
                    f"Write would exceed max capacity: {end_offset} > {self._max_size}"
                )
            
            # Ensure buffer is large enough
            self._ensure_capacity(end_offset)
            
            # Update logical size if needed
            if hasattr(self, '_logical_size'):
                self._logical_size = max(self._logical_size, end_offset)
            
            # Write the data
            self._data[offset:end_offset] = data
            
            self._record_write(len(data))
            return len(data)
    
    def size(self) -> int:
        """Return the logical size of storage."""
        return self._get_logical_size()
    
    def sync(self) -> None:
        """No-op for memory backend (no persistence)."""
        pass  # Memory is always "synced"
    
    @property
    def capabilities(self) -> StorageCapabilities:
        """Return capabilities of memory storage backend."""
        return (
            StorageCapabilities.SPARSE |
            StorageCapabilities.TRUNCATE |
            StorageCapabilities.RANGE_READ |
            StorageCapabilities.CONCURRENT |
            StorageCapabilities.SEEKABLE
            # Note: NOT PERSISTENT - data is lost on exit
        )
    
    # ========================================================================
    # Optional Methods
    # ========================================================================
    
    def truncate(self, size: int) -> None:
        """
        Resize the storage.
        
        Args:
            size: New size in bytes.
        
        Raises:
            StorageCapacityError: If size exceeds max_size.
        """
        if size > self._max_size:
            raise StorageCapacityError(
                f"Cannot truncate beyond max size: {size} > {self._max_size}"
            )
        
        with self._data_lock:
            if hasattr(self, '_logical_size'):
                self._logical_size = size
            
            if size < len(self._data):
                # Shrink
                del self._data[size:]
            elif size > len(self._data):
                # Expand with zeros
                self._data.extend(bytes(size - len(self._data)))
    
    def clear(self) -> None:
        """Clear all data (zero-fill)."""
        with self._data_lock:
            for i in range(len(self._data)):
                self._data[i] = 0
    
    def get_data(self) -> bytes:
        """
        Return a copy of all data (for testing).
        
        Returns:
            Copy of internal buffer as bytes.
        """
        with self._data_lock:
            return bytes(self._data)
    
    # ========================================================================
    # Internal Helpers
    # ========================================================================
    
    def _get_logical_size(self) -> int:
        """Get the logical size of storage."""
        if hasattr(self, '_logical_size'):
            return self._logical_size
        return len(self._data)
    
    def _ensure_capacity(self, required: int) -> None:
        """Ensure the buffer has at least required capacity."""
        if required > len(self._data):
            # Extend with zeros
            self._data.extend(bytes(required - len(self._data)))
    
    # ========================================================================
    # Properties
    # ========================================================================
    
    @property
    def max_size(self) -> int:
        """Return maximum allowed size."""
        return self._max_size
    
    @property
    def actual_size(self) -> int:
        """Return actual memory used."""
        return len(self._data)
    
    @property
    def is_persistent(self) -> bool:
        """Memory backend is NOT persistent."""
        return False
    
    # ========================================================================
    # String Representation
    # ========================================================================
    
    def __repr__(self) -> str:
        """Return string representation."""
        return (
            f"MemoryStorageBackend("
            f"size={self.size()}, "
            f"actual={self.actual_size}, "
            f"max={self._max_size})"
        )
