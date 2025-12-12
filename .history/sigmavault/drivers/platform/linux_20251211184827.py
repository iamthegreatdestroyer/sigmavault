"""
ΣVAULT Linux Platform Implementation

Provides Linux-specific filesystem, security, and FUSE operations.
This is the primary development platform for SigmaVault.

Features:
    - Native FUSE support via libfuse3
    - Sparse file support on ext4, xfs, btrfs
    - mlock for secure memory
    - Linux-specific file locking (flock/fcntl)
    - cgroups and namespace detection for containers
"""

from __future__ import annotations

import ctypes
import fcntl
import mmap
import os
import secrets
import struct
import subprocess
from pathlib import Path
from typing import Optional, Dict, Any, Tuple, TYPE_CHECKING

from .base import (
    Platform,
    PlatformCapabilities,
    PlatformInfo,
    PlatformError,
    PlatformNotSupportedError,
)


class LinuxPlatform(Platform):
    """
    Linux platform implementation.
    
    Supports ext4, xfs, btrfs filesystems with full FUSE support.
    
    Example:
        >>> platform = LinuxPlatform()
        >>> print(platform.capabilities)
        PlatformCapabilities.FULL_POSIX | PlatformCapabilities.FUSE
    """
    
    def __init__(self):
        """Initialize Linux platform."""
        self._info: Optional[PlatformInfo] = None
        self._capabilities: Optional[PlatformCapabilities] = None
        self._libc: Optional[ctypes.CDLL] = None
        self._file_locks: Dict[Path, int] = {}  # path -> fd
    
    # ========================================================================
    # Abstract Properties Implementation
    # ========================================================================
    
    @property
    def info(self) -> PlatformInfo:
        """Get Linux platform information."""
        if self._info is None:
            self._info = self._detect_info()
        return self._info
    
    @property
    def capabilities(self) -> PlatformCapabilities:
        """Get Linux platform capabilities."""
        if self._capabilities is None:
            self._capabilities = self._detect_capabilities()
        return self._capabilities
    
    # ========================================================================
    # Filesystem Operations
    # ========================================================================
    
    def create_sparse_file(self, path: Path, size: int) -> bool:
        """
        Create a sparse file on Linux.
        
        Uses fallocate with FALLOC_FL_KEEP_SIZE for efficient sparse creation.
        Falls back to truncate if fallocate isn't available.
        
        Args:
            path: Path for the new file.
            size: Logical size in bytes.
        
        Returns:
            True if created as sparse.
        """
        try:
            # Create file
            fd = os.open(str(path), os.O_CREAT | os.O_WRONLY | os.O_TRUNC, 0o600)
            try:
                # Use truncate to set size without allocating
                os.ftruncate(fd, size)
                return True
            finally:
                os.close(fd)
        except OSError as e:
            raise PlatformError(f"Failed to create sparse file: {e}")
    
    def get_file_system_type(self, path: Path) -> str:
        """
        Get filesystem type using statfs.
        
        Args:
            path: Path to check.
        
        Returns:
            Filesystem type string.
        """
        # Magic numbers for Linux filesystems
        FS_MAGIC = {
            0xEF53: 'ext4',      # Also ext2, ext3
            0x58465342: 'xfs',
            0x9123683E: 'btrfs',
            0x65735546: 'fuse',
            0x01021994: 'tmpfs',
            0x2FC12FC1: 'zfs',
            0x6969: 'nfs',
            0xFF534D42: 'cifs',
            0x137F: 'minix',
            0x52654973: 'reiserfs',
        }
        
        try:
            # Use os.statvfs to get filesystem info
            stat = os.statvfs(str(path))
            
            # Try to read from /proc/mounts for type
            real_path = path.resolve()
            with open('/proc/mounts', 'r') as f:
                for line in f:
                    parts = line.split()
                    if len(parts) >= 3:
                        mount_point = parts[1]
                        if str(real_path).startswith(mount_point):
                            return parts[2]
            
            return 'unknown'
        except OSError:
            return 'unknown'
    
    def get_available_space(self, path: Path) -> int:
        """
        Get available disk space.
        
        Args:
            path: Path to check.
        
        Returns:
            Available space in bytes.
        """
        try:
            stat = os.statvfs(str(path))
            return stat.f_bavail * stat.f_frsize
        except OSError as e:
            raise PlatformError(f"Failed to get available space: {e}")
    
    def lock_file(self, path: Path, exclusive: bool = True) -> int:
        """
        Acquire advisory lock using flock.
        
        Args:
            path: Path to file.
            exclusive: Whether to acquire exclusive lock.
        
        Returns:
            File descriptor (used as lock handle).
        """
        try:
            fd = os.open(str(path), os.O_RDWR | os.O_CREAT, 0o600)
            operation = fcntl.LOCK_EX if exclusive else fcntl.LOCK_SH
            fcntl.flock(fd, operation)
            self._file_locks[path] = fd
            return fd
        except OSError as e:
            raise PlatformError(f"Failed to lock file: {e}")
    
    def unlock_file(self, lock_handle: int) -> None:
        """
        Release file lock.
        
        Args:
            lock_handle: File descriptor from lock_file().
        """
        try:
            fcntl.flock(lock_handle, fcntl.LOCK_UN)
            os.close(lock_handle)
            
            # Remove from tracking
            for path, fd in list(self._file_locks.items()):
                if fd == lock_handle:
                    del self._file_locks[path]
                    break
        except OSError as e:
            raise PlatformError(f"Failed to unlock file: {e}")
    
    # ========================================================================
    # Security Operations
    # ========================================================================
    
    def secure_delete(self, path: Path, passes: int = 3) -> None:
        """
        Securely delete file by overwriting.
        
        Uses multiple passes with random data, then unlinks.
        Note: May not be effective on SSDs, journaling filesystems, or CoW filesystems.
        
        Args:
            path: Path to file.
            passes: Number of overwrite passes.
        """
        if not path.exists():
            return
        
        try:
            size = path.stat().st_size
            
            with open(path, 'r+b') as f:
                for pass_num in range(passes):
                    f.seek(0)
                    
                    if pass_num == passes - 1:
                        # Final pass: zeros
                        f.write(b'\x00' * size)
                    else:
                        # Random data
                        f.write(secrets.token_bytes(size))
                    
                    f.flush()
                    os.fsync(f.fileno())
            
            # Unlink the file
            path.unlink()
            
        except OSError as e:
            raise PlatformError(f"Failed to secure delete: {e}")
    
    def lock_memory(self, address: int, size: int) -> bool:
        """
        Lock memory pages using mlock.
        
        Args:
            address: Memory address.
            size: Size in bytes.
        
        Returns:
            True if successful.
        """
        try:
            libc = self._get_libc()
            result = libc.mlock(ctypes.c_void_p(address), ctypes.c_size_t(size))
            return result == 0
        except (OSError, AttributeError):
            return False
    
    def unlock_memory(self, address: int, size: int) -> bool:
        """
        Unlock memory pages using munlock.
        
        Args:
            address: Memory address.
            size: Size in bytes.
        
        Returns:
            True if successful.
        """
        try:
            libc = self._get_libc()
            result = libc.munlock(ctypes.c_void_p(address), ctypes.c_size_t(size))
            return result == 0
        except (OSError, AttributeError):
            return False
    
    def get_secure_random(self, size: int) -> bytes:
        """
        Get cryptographically secure random bytes from /dev/urandom.
        
        Args:
            size: Number of bytes.
        
        Returns:
            Random bytes.
        """
        return secrets.token_bytes(size)
    
    # ========================================================================
    # FUSE Operations
    # ========================================================================
    
    def is_fuse_available(self) -> bool:
        """Check if FUSE is available."""
        # Check for /dev/fuse
        if not Path('/dev/fuse').exists():
            return False
        
        # Check for fusermount or fusermount3
        try:
            result = subprocess.run(
                ['which', 'fusermount3'],
                capture_output=True,
                text=True
            )
            if result.returncode == 0:
                return True
            
            result = subprocess.run(
                ['which', 'fusermount'],
                capture_output=True,
                text=True
            )
            return result.returncode == 0
        except FileNotFoundError:
            return False
    
    def get_fuse_version(self) -> Optional[str]:
        """Get FUSE version."""
        try:
            # Try fusermount3 first (FUSE 3.x)
            result = subprocess.run(
                ['fusermount3', '--version'],
                capture_output=True,
                text=True
            )
            if result.returncode == 0:
                return result.stdout.strip()
            
            # Fall back to fusermount
            result = subprocess.run(
                ['fusermount', '--version'],
                capture_output=True,
                text=True
            )
            if result.returncode == 0:
                return result.stdout.strip()
        except FileNotFoundError:
            pass
        
        return None
    
    def mount_fuse(
        self,
        operations: Any,
        mountpoint: Path,
        foreground: bool = False,
        allow_other: bool = False,
        **kwargs
    ) -> Any:
        """
        Mount a FUSE filesystem.
        
        Note: Actual mounting requires the pyfuse3 or fusepy library.
        This method provides the platform-specific configuration.
        
        Args:
            operations: FUSE operations object.
            mountpoint: Mount point path.
            foreground: Run in foreground.
            allow_other: Allow other users access.
            **kwargs: Additional mount options.
        
        Returns:
            Mount configuration dict.
        """
        options = {
            'foreground': foreground,
            'allow_other': allow_other,
            'auto_unmount': True,
            **kwargs
        }
        
        # Linux-specific options
        options.setdefault('nonempty', False)
        options.setdefault('default_permissions', True)
        
        return {
            'operations': operations,
            'mountpoint': str(mountpoint),
            'options': options,
            'platform': 'linux'
        }
    
    def unmount_fuse(self, mountpoint: Path) -> bool:
        """
        Unmount a FUSE filesystem using fusermount.
        
        Args:
            mountpoint: Mount point path.
        
        Returns:
            True if successful.
        """
        try:
            # Try fusermount3 first
            result = subprocess.run(
                ['fusermount3', '-u', str(mountpoint)],
                capture_output=True,
                text=True
            )
            if result.returncode == 0:
                return True
            
            # Fall back to fusermount
            result = subprocess.run(
                ['fusermount', '-u', str(mountpoint)],
                capture_output=True,
                text=True
            )
            return result.returncode == 0
            
        except FileNotFoundError:
            # Try umount as fallback
            try:
                result = subprocess.run(
                    ['umount', str(mountpoint)],
                    capture_output=True,
                    text=True
                )
                return result.returncode == 0
            except FileNotFoundError:
                return False
    
    # ========================================================================
    # System Information
    # ========================================================================
    
    def get_memory_info(self) -> Dict[str, int]:
        """
        Get system memory information from /proc/meminfo.
        
        Returns:
            Dict with 'total', 'available', 'used' in bytes.
        """
        try:
            with open('/proc/meminfo', 'r') as f:
                meminfo = {}
                for line in f:
                    parts = line.split(':')
                    if len(parts) == 2:
                        key = parts[0].strip()
                        value = parts[1].strip().split()[0]
                        meminfo[key] = int(value) * 1024  # Convert KB to bytes
            
            total = meminfo.get('MemTotal', 0)
            available = meminfo.get('MemAvailable', meminfo.get('MemFree', 0))
            
            return {
                'total': total,
                'available': available,
                'used': total - available
            }
        except (FileNotFoundError, ValueError):
            return {'total': 0, 'available': 0, 'used': 0}
    
    def get_cpu_count(self) -> int:
        """Get number of CPU cores."""
        return os.cpu_count() or 1
    
    def is_admin(self) -> bool:
        """Check if running as root."""
        return os.geteuid() == 0
    
    # ========================================================================
    # Internal Methods
    # ========================================================================
    
    def _get_libc(self) -> ctypes.CDLL:
        """Get or load libc."""
        if self._libc is None:
            self._libc = ctypes.CDLL('libc.so.6', use_errno=True)
        return self._libc
    
    def _detect_info(self) -> PlatformInfo:
        """Detect Linux platform information."""
        import platform as plat
        
        is_container, container_type = self.detect_container()
        
        return PlatformInfo(
            name='linux',
            version=plat.release(),
            architecture=plat.machine(),
            is_64bit=struct.calcsize('P') * 8 == 64,
            is_container=is_container,
            container_type=container_type,
            capabilities=self._detect_capabilities()
        )
    
    def _detect_capabilities(self) -> PlatformCapabilities:
        """Detect Linux platform capabilities."""
        caps = PlatformCapabilities.NONE
        
        # FUSE support
        if self.is_fuse_available():
            caps |= PlatformCapabilities.FUSE
        
        # Sparse files (almost always available on Linux)
        caps |= PlatformCapabilities.SPARSE_FILES
        
        # POSIX features
        caps |= PlatformCapabilities.SYMBOLIC_LINKS
        caps |= PlatformCapabilities.HARD_LINKS
        caps |= PlatformCapabilities.FILE_LOCKING
        caps |= PlatformCapabilities.MMAP
        
        # Extended attributes (check if xattr module is available)
        try:
            import xattr
            caps |= PlatformCapabilities.EXTENDED_ATTRS
        except ImportError:
            pass
        
        # Security
        caps |= PlatformCapabilities.SECURE_MEMORY
        caps |= PlatformCapabilities.SECURE_DELETE
        
        # Check for io_uring (Linux 5.1+)
        try:
            version = tuple(int(x) for x in os.uname().release.split('.')[:2])
            if version >= (5, 1):
                caps |= PlatformCapabilities.ASYNC_IO
        except (ValueError, AttributeError):
            pass
        
        # Direct I/O
        caps |= PlatformCapabilities.DIRECT_IO
        
        # Container detection
        is_container, _ = self.detect_container()
        if is_container:
            caps |= PlatformCapabilities.CONTAINER_AWARE
        
        # cgroups
        if Path('/sys/fs/cgroup').exists():
            caps |= PlatformCapabilities.CGROUPS
        
        # Namespaces
        if Path('/proc/self/ns').exists():
            caps |= PlatformCapabilities.NAMESPACES
        
        return caps
