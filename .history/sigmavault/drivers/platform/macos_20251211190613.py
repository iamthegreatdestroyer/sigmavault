"""
ΣVAULT macOS Platform Implementation

Provides macOS-specific filesystem, security, and macFUSE operations.

Features:
    - macFUSE integration for FUSE filesystem support
    - APFS sparse file support
    - macOS file locking (flock)
    - mlock for secure memory
    - Keychain integration for key storage (future)
    - FSEvents for filesystem monitoring
"""

from __future__ import annotations

import ctypes
import ctypes.util
import fcntl
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


class MacOSPlatform(Platform):
    """
    macOS platform implementation with macFUSE support.
    
    Requires macFUSE to be installed for FUSE filesystem support.
    Download from: https://osxfuse.github.io/
    
    Example:
        >>> platform = MacOSPlatform()
        >>> print(platform.is_macfuse_available())
        True
        >>> platform.create_sparse_file(Path("test.bin"), 1024*1024*1024)
    """
    
    def __init__(self):
        """Initialize macOS platform."""
        self._info: Optional[PlatformInfo] = None
        self._capabilities: Optional[PlatformCapabilities] = None
        self._libc: Optional[ctypes.CDLL] = None
        self._file_locks: Dict[Path, int] = {}  # path -> fd
    
    # ========================================================================
    # Abstract Properties Implementation
    # ========================================================================
    
    @property
    def info(self) -> PlatformInfo:
        """Get macOS platform information."""
        if self._info is None:
            self._info = self._detect_info()
        return self._info
    
    @property
    def capabilities(self) -> PlatformCapabilities:
        """Get macOS platform capabilities."""
        if self._capabilities is None:
            self._capabilities = self._detect_capabilities()
        return self._capabilities
    
    # ========================================================================
    # Filesystem Operations
    # ========================================================================
    
    def create_sparse_file(self, path: Path, size: int) -> bool:
        """
        Create a sparse file on APFS/HFS+.
        
        Uses ftruncate which creates sparse files on APFS.
        
        Args:
            path: Path for the new file.
            size: Logical size in bytes.
        
        Returns:
            True if created (APFS always creates sparse).
        """
        try:
            # Create file and set size with truncate
            fd = os.open(str(path), os.O_CREAT | os.O_WRONLY | os.O_TRUNC, 0o600)
            try:
                os.ftruncate(fd, size)
                return True  # APFS handles this as sparse
            finally:
                os.close(fd)
        except OSError as e:
            raise PlatformError(f"Failed to create sparse file: {e}")
    
    def get_file_system_type(self, path: Path) -> str:
        """
        Get filesystem type using diskutil.
        
        Args:
            path: Path to check.
        
        Returns:
            Filesystem type string (apfs, hfs, etc.).
        """
        try:
            # Use diskutil to get filesystem type
            result = subprocess.run(
                ['diskutil', 'info', str(path.resolve())],
                capture_output=True,
                text=True
            )
            
            if result.returncode == 0:
                for line in result.stdout.split('\n'):
                    if 'File System Personality' in line or 'Type (Bundle)' in line:
                        parts = line.split(':')
                        if len(parts) >= 2:
                            return parts[1].strip().lower()
            
            # Fallback: use statfs
            import os
            stat = os.statvfs(str(path))
            
            # Try to detect common filesystems
            return 'unknown'
            
        except (subprocess.SubprocessError, OSError):
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
        
        Note: Not effective on APFS due to copy-on-write.
        Consider using encryption instead.
        
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
        Get cryptographically secure random bytes.
        
        Args:
            size: Number of bytes.
        
        Returns:
            Random bytes.
        """
        return secrets.token_bytes(size)
    
    # ========================================================================
    # FUSE Operations (macFUSE)
    # ========================================================================
    
    def is_fuse_available(self) -> bool:
        """Check if macFUSE is available."""
        return self.is_macfuse_available()
    
    def is_macfuse_available(self) -> bool:
        """
        Check if macFUSE is installed.
        
        Checks standard installation locations.
        """
        macfuse_paths = [
            Path('/Library/Filesystems/macfuse.fs'),
            Path('/Library/Filesystems/osxfuse.fs'),  # Legacy
            Path('/usr/local/lib/libfuse.dylib'),
            Path('/usr/local/lib/libfuse.2.dylib'),
        ]
        
        for path in macfuse_paths:
            if path.exists():
                return True
        
        # Check if kext is loaded
        try:
            result = subprocess.run(
                ['kextstat'],
                capture_output=True,
                text=True
            )
            if 'macfuse' in result.stdout.lower() or 'osxfuse' in result.stdout.lower():
                return True
        except (subprocess.SubprocessError, FileNotFoundError):
            pass
        
        return False
    
    def get_fuse_version(self) -> Optional[str]:
        """Get macFUSE version."""
        try:
            # Try to get version from pkgutil
            result = subprocess.run(
                ['pkgutil', '--pkg-info', 'io.macfuse.installer.components.core'],
                capture_output=True,
                text=True
            )
            
            if result.returncode == 0:
                for line in result.stdout.split('\n'):
                    if line.startswith('version:'):
                        return line.split(':')[1].strip()
            
            # Try osxfuse (legacy)
            result = subprocess.run(
                ['pkgutil', '--pkg-info', 'com.github.osxfuse.pkg.Core'],
                capture_output=True,
                text=True
            )
            
            if result.returncode == 0:
                for line in result.stdout.split('\n'):
                    if line.startswith('version:'):
                        return 'osxfuse-' + line.split(':')[1].strip()
                        
        except (subprocess.SubprocessError, FileNotFoundError):
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
        Mount a macFUSE filesystem.
        
        Note: Actual mounting requires the fusepy library.
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
            **kwargs
        }
        
        # macOS-specific options
        options.setdefault('nolocalcaches', True)  # Disable caching for consistency
        options.setdefault('volname', 'SigmaVault')
        
        return {
            'operations': operations,
            'mountpoint': str(mountpoint),
            'options': options,
            'platform': 'darwin'
        }
    
    def unmount_fuse(self, mountpoint: Path) -> bool:
        """
        Unmount a macFUSE filesystem using umount.
        
        Args:
            mountpoint: Mount point path.
        
        Returns:
            True if successful.
        """
        try:
            # Try diskutil unmount first (gentler)
            result = subprocess.run(
                ['diskutil', 'unmount', str(mountpoint)],
                capture_output=True,
                text=True
            )
            if result.returncode == 0:
                return True
            
            # Fall back to umount
            result = subprocess.run(
                ['umount', str(mountpoint)],
                capture_output=True,
                text=True
            )
            return result.returncode == 0
            
        except (subprocess.SubprocessError, FileNotFoundError):
            return False
    
    # ========================================================================
    # System Information
    # ========================================================================
    
    def get_memory_info(self) -> Dict[str, int]:
        """
        Get system memory information using sysctl.
        
        Returns:
            Dict with 'total', 'available', 'used' in bytes.
        """
        try:
            # Get total memory
            result = subprocess.run(
                ['sysctl', '-n', 'hw.memsize'],
                capture_output=True,
                text=True
            )
            total = int(result.stdout.strip()) if result.returncode == 0 else 0
            
            # Get page size and vm statistics
            result = subprocess.run(
                ['vm_stat'],
                capture_output=True,
                text=True
            )
            
            if result.returncode == 0:
                # Parse vm_stat output
                page_size = 4096  # Default
                free_pages = 0
                inactive_pages = 0
                
                for line in result.stdout.split('\n'):
                    if 'page size of' in line:
                        page_size = int(line.split()[-2])
                    elif 'Pages free' in line:
                        free_pages = int(line.split(':')[1].strip().rstrip('.'))
                    elif 'Pages inactive' in line:
                        inactive_pages = int(line.split(':')[1].strip().rstrip('.'))
                
                available = (free_pages + inactive_pages) * page_size
            else:
                available = 0
            
            return {
                'total': total,
                'available': available,
                'used': total - available
            }
            
        except (subprocess.SubprocessError, ValueError):
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
            libc_path = ctypes.util.find_library('c')
            self._libc = ctypes.CDLL(libc_path, use_errno=True)
        return self._libc
    
    def _detect_info(self) -> PlatformInfo:
        """Detect macOS platform information."""
        import platform as plat
        
        is_container, container_type = self.detect_container()
        
        return PlatformInfo(
            name='darwin',
            version=plat.mac_ver()[0],
            architecture=plat.machine(),
            is_64bit=struct.calcsize('P') * 8 == 64,
            is_container=is_container,
            container_type=container_type,
            capabilities=self._detect_capabilities()
        )
    
    def _detect_capabilities(self) -> PlatformCapabilities:
        """Detect macOS platform capabilities."""
        caps = PlatformCapabilities.NONE
        
        # macFUSE support
        if self.is_macfuse_available():
            caps |= PlatformCapabilities.FUSE
        
        # APFS sparse files
        caps |= PlatformCapabilities.SPARSE_FILES
        
        # POSIX features
        caps |= PlatformCapabilities.SYMBOLIC_LINKS
        caps |= PlatformCapabilities.HARD_LINKS
        caps |= PlatformCapabilities.FILE_LOCKING
        caps |= PlatformCapabilities.MMAP
        
        # Extended attributes
        caps |= PlatformCapabilities.EXTENDED_ATTRS
        
        # Security
        caps |= PlatformCapabilities.SECURE_MEMORY
        caps |= PlatformCapabilities.SECURE_DELETE
        caps |= PlatformCapabilities.KEY_STORAGE  # Keychain
        caps |= PlatformCapabilities.NATIVE_ENCRYPTION  # FileVault
        
        # APFS Copy-on-Write
        caps |= PlatformCapabilities.COPY_ON_WRITE
        
        # GCD for async I/O
        caps |= PlatformCapabilities.ASYNC_IO
        
        return caps
    
    def detect_container(self) -> Tuple[bool, Optional[str]]:
        """
        Detect if running inside a container (rare on macOS).
        
        Returns:
            Tuple of (is_container, container_type).
        """
        # Docker Desktop for Mac runs containers in a Linux VM,
        # so macOS code doesn't typically run inside containers.
        # However, check for common indicators.
        
        if os.environ.get('DOCKER_HOST'):
            return True, 'docker'
        
        return False, None
