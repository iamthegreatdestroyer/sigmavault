"""
ΣVAULT File Storage Backend

Local filesystem-based storage backend implementation.
Uses standard file I/O with optional sparse file support.

Features:
    - Random access reads/writes
    - Sparse file support (platform-dependent)
    - Automatic file creation
    - fsync for durability
    - Thread-safe operations
"""

import os
import threading
from pathlib import Path
from typing import Optional, Union

from .base import (
    StorageBackend,
    StorageCapabilities,
    StorageError,
    StorageReadError,
    StorageWriteError,
    StorageCapacityError,
    StorageNotFoundError,
)


class FileStorageBackend(StorageBackend):
    """
    Storage backend using local filesystem.
    
    This backend stores scattered data in a single large file,
    treating it as a byte-addressable block device. Supports
    sparse files on filesystems that allow them (ext4, NTFS, APFS).
    
    Thread Safety:
        All operations are protected by a reentrant lock.
        Multiple threads can safely read/write concurrently.
    
    Example:
        >>> backend = FileStorageBackend("vault.dat", size=1_000_000_000)
        >>> backend.write(0, b"Hello")
        5
        >>> backend.read(0, 5)
        b'Hello'
        >>> backend.sync()
    
    Args:
        path: Path to the storage file.
        size: Total size of storage medium in bytes.
               If file exists and is larger, size is ignored.
               If file doesn't exist, creates sparse file of this size.
        create: Whether to create file if it doesn't exist (default True).
        sparse: Whether to create as sparse file (default True).
    """
    
    def __init__(
        self,
        path: Union[str, Path],
        size: int = 10 * 1024 * 1024 * 1024,  # 10 GB default
        create: bool = True,
        sparse: bool = True,
    ):
        super().__init__(enable_stats=True)
        
        self._path = Path(path)
        self._requested_size = size
        self._sparse = sparse
        self._file: Optional[object] = None
        self._file_lock = threading.RLock()
        
        # Initialize file
        if self._path.exists():
            self._open_existing()
        elif create:
            self._create_new(size, sparse)
        else:
            raise StorageNotFoundError(f"Storage file not found: {path}")
    
    def _open_existing(self) -> None:
        """Open an existing storage file."""
        try:
            self._file = open(self._path, "r+b")
            # Get actual size
            self._file.seek(0, os.SEEK_END)
            self._actual_size = self._file.tell()
            self._file.seek(0)
        except OSError as e:
            raise StorageError(f"Failed to open storage file: {e}")
    
    def _create_new(self, size: int, sparse: bool) -> None:
        """Create a new storage file."""
        try:
            # Ensure parent directory exists
            self._path.parent.mkdir(parents=True, exist_ok=True)
            
            # Create the file
            self._file = open(self._path, "w+b")
            
            if sparse:
                # Create sparse file by seeking to end and writing one byte
                self._file.seek(size - 1)
                self._file.write(b'\x00')
            else:
                # Allocate full size (slow but guaranteed space)
                self._allocate_full(size)
            
            self._actual_size = size
            self._file.seek(0)
            self._file.flush()
            
        except OSError as e:
            raise StorageError(f"Failed to create storage file: {e}")
    
    def _allocate_full(self, size: int, chunk_size: int = 64 * 1024 * 1024) -> None:
        """Allocate full size by writing zeros (non-sparse)."""
        zeros = b'\x00' * chunk_size
        remaining = size
        
        while remaining > 0:
            write_size = min(remaining, chunk_size)
            self._file.write(zeros[:write_size])
            remaining -= write_size
    
    # ========================================================================
    # StorageBackend Interface Implementation
    # ========================================================================
    
    def read(self, offset: int, size: int) -> bytes:
        """
        Read bytes from storage file at given offset.
        
        Args:
            offset: Byte offset from start.
            size: Number of bytes to read.
        
        Returns:
            Bytes read (may be shorter if near end of file).
        
        Raises:
            StorageReadError: If read fails.
            ValueError: If offset is negative.
        """
        if offset < 0:
            raise ValueError(f"Offset cannot be negative: {offset}")
        
        if size <= 0:
            return b''
        
        with self._file_lock:
            try:
                self._file.seek(offset)
                data = self._file.read(size)
                self._record_read(len(data))
                return data
            except OSError as e:
                raise StorageReadError(f"Read failed at offset {offset}: {e}")
    
    def write(self, offset: int, data: bytes) -> int:
        """
        Write bytes to storage file at given offset.
        
        Args:
            offset: Byte offset from start.
            data: Bytes to write.
        
        Returns:
            Number of bytes written.
        
        Raises:
            StorageWriteError: If write fails.
            StorageCapacityError: If write exceeds capacity.
            ValueError: If offset is negative.
        """
        if offset < 0:
            raise ValueError(f"Offset cannot be negative: {offset}")
        
        if not data:
            return 0
        
        # Check capacity
        end_offset = offset + len(data)
        if end_offset > self._actual_size:
            raise StorageCapacityError(
                f"Write would exceed capacity: {end_offset} > {self._actual_size}"
            )
        
        with self._file_lock:
            try:
                self._file.seek(offset)
                written = self._file.write(data)
                self._record_write(written)
                return written
            except OSError as e:
                raise StorageWriteError(f"Write failed at offset {offset}: {e}")
    
    def size(self) -> int:
        """Return total size of storage file."""
        return self._actual_size
    
    def sync(self) -> None:
        """Flush and fsync the storage file."""
        with self._file_lock:
            try:
                self._file.flush()
                os.fsync(self._file.fileno())
            except OSError as e:
                raise StorageError(f"Sync failed: {e}")
    
    @property
    def capabilities(self) -> StorageCapabilities:
        """Return capabilities of file storage backend."""
        caps = (
            StorageCapabilities.TRUNCATE |
            StorageCapabilities.RANGE_READ |
            StorageCapabilities.CONCURRENT |
            StorageCapabilities.PERSISTENT |
            StorageCapabilities.SEEKABLE
        )
        
        if self._sparse:
            caps |= StorageCapabilities.SPARSE
        
        return caps
    
    # ========================================================================
    # Optional Methods
    # ========================================================================
    
    def truncate(self, size: int) -> None:
        """
        Resize the storage file.
        
        Args:
            size: New size in bytes.
        """
        with self._file_lock:
            try:
                self._file.truncate(size)
                self._actual_size = size
            except OSError as e:
                raise StorageError(f"Truncate failed: {e}")
    
    def close(self) -> None:
        """Close the storage file."""
        with self._file_lock:
            if self._file:
                try:
                    self._file.close()
                except OSError:
                    pass
                self._file = None
    
    # ========================================================================
    # Properties
    # ========================================================================
    
    @property
    def path(self) -> Path:
        """Return the storage file path."""
        return self._path
    
    @property
    def is_sparse(self) -> bool:
        """Whether the file was created as sparse."""
        return self._sparse
    
    # ========================================================================
    # Context Manager / Cleanup
    # ========================================================================
    
    def __exit__(self, exc_type, exc_val, exc_tb) -> None:
        """Exit context, sync and close."""
        try:
            self.sync()
        finally:
            self.close()
    
    def __del__(self):
        """Destructor - ensure file is closed."""
        self.close()
    
    def __repr__(self) -> str:
        """Return string representation."""
        return (
            f"FileStorageBackend("
            f"path='{self._path}', "
            f"size={self._actual_size}, "
            f"sparse={self._sparse})"
        )
