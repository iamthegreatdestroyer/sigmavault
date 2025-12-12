"""
ΣVAULT Abstract Platform Interface

Defines the abstract interface for platform-specific operations.
Concrete implementations exist for each supported platform:
    - LinuxPlatform (linux.py)
    - WindowsPlatform (windows.py)
    - MacOSPlatform (macos.py)
    - ContainerPlatform (container.py)
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from enum import Flag, auto
from pathlib import Path
from typing import Optional, List, Dict, Any, Tuple, TYPE_CHECKING
import os
import sys
import platform as py_platform
import struct


class PlatformCapabilities(Flag):
    """
    Capabilities supported by a platform.
    
    Used to determine available features and make runtime decisions.
    """
    NONE = 0
    
    # Filesystem capabilities
    FUSE = auto()           # Native FUSE support
    SPARSE_FILES = auto()   # Sparse file support
    SYMBOLIC_LINKS = auto() # Symlink support
    HARD_LINKS = auto()     # Hard link support
    EXTENDED_ATTRS = auto() # xattr support
    FILE_LOCKING = auto()   # Advisory file locking
    MMAP = auto()           # Memory-mapped I/O
    
    # Security capabilities
    NATIVE_ENCRYPTION = auto()  # OS-level encryption (BitLocker, FileVault, LUKS)
    SECURE_MEMORY = auto()      # mlock/VirtualLock support
    KEY_STORAGE = auto()        # Secure key storage (Keychain, DPAPI, etc.)
    SECURE_DELETE = auto()      # Secure file deletion
    
    # Performance capabilities
    ASYNC_IO = auto()       # Native async I/O (io_uring, IOCP)
    DIRECT_IO = auto()      # O_DIRECT / unbuffered I/O
    COPY_ON_WRITE = auto()  # CoW support (btrfs, APFS)
    
    # Container capabilities
    CONTAINER_AWARE = auto()  # Running in container
    CGROUPS = auto()          # cgroups support
    NAMESPACES = auto()       # Linux namespaces
    
    # Combined capability sets
    FULL_POSIX = FUSE | SPARSE_FILES | SYMBOLIC_LINKS | HARD_LINKS | EXTENDED_ATTRS | FILE_LOCKING | MMAP
    FULL_SECURITY = NATIVE_ENCRYPTION | SECURE_MEMORY | KEY_STORAGE | SECURE_DELETE
    FULL_PERFORMANCE = ASYNC_IO | DIRECT_IO | COPY_ON_WRITE


@dataclass
class PlatformInfo:
    """
    Information about the current platform.
    
    Attributes:
        name: Platform name (linux, windows, darwin).
        version: OS version string.
        architecture: CPU architecture (x86_64, arm64, etc.).
        is_64bit: Whether running on 64-bit system.
        is_container: Whether running in a container.
        container_type: Container type if applicable (docker, podman, etc.).
        python_version: Python version tuple.
        hostname: System hostname.
        capabilities: Detected platform capabilities.
    """
    name: str
    version: str
    architecture: str
    is_64bit: bool
    is_container: bool
    container_type: Optional[str] = None
    python_version: Tuple[int, int, int] = field(default_factory=lambda: sys.version_info[:3])
    hostname: str = field(default_factory=lambda: py_platform.node())
    capabilities: PlatformCapabilities = PlatformCapabilities.NONE


class PlatformError(Exception):
    """Base exception for platform-related errors."""
    pass


class PlatformNotSupportedError(PlatformError):
    """Raised when a feature isn't supported on current platform."""
    def __init__(self, feature: str, platform: str):
        self.feature = feature
        self.platform = platform
        super().__init__(f"{feature} is not supported on {platform}")


class Platform(ABC):
    """
    Abstract base class for platform-specific operations.
    
    Provides a unified interface for filesystem, security, and system
    operations across different operating systems.
    
    Subclasses must implement all abstract methods to support a new platform.
    
    Example:
        >>> platform = get_current_platform()
        >>> print(platform.info.name)
        'linux'
        >>> platform.secure_delete(Path("/tmp/secret.txt"))
    """
    
    # ========================================================================
    # Abstract Properties
    # ========================================================================
    
    @property
    @abstractmethod
    def info(self) -> PlatformInfo:
        """Get platform information."""
        pass
    
    @property
    @abstractmethod
    def capabilities(self) -> PlatformCapabilities:
        """Get platform capabilities."""
        pass
    
    # ========================================================================
    # Filesystem Operations
    # ========================================================================
    
    @abstractmethod
    def create_sparse_file(self, path: Path, size: int) -> bool:
        """
        Create a sparse file of given size.
        
        Args:
            path: Path for the new file.
            size: Logical size in bytes.
        
        Returns:
            True if created as sparse, False if fallback to regular file.
        """
        pass
    
    @abstractmethod
    def get_file_system_type(self, path: Path) -> str:
        """
        Get filesystem type for path.
        
        Args:
            path: Path to check.
        
        Returns:
            Filesystem type string (ext4, ntfs, apfs, etc.).
        """
        pass
    
    @abstractmethod
    def get_available_space(self, path: Path) -> int:
        """
        Get available disk space at path.
        
        Args:
            path: Path to check.
        
        Returns:
            Available space in bytes.
        """
        pass
    
    @abstractmethod
    def lock_file(self, path: Path, exclusive: bool = True) -> Any:
        """
        Acquire advisory lock on file.
        
        Args:
            path: Path to file.
            exclusive: Whether to acquire exclusive lock.
        
        Returns:
            Lock handle (platform-specific).
        """
        pass
    
    @abstractmethod
    def unlock_file(self, lock_handle: Any) -> None:
        """
        Release file lock.
        
        Args:
            lock_handle: Lock handle from lock_file().
        """
        pass
    
    # ========================================================================
    # Security Operations
    # ========================================================================
    
    @abstractmethod
    def secure_delete(self, path: Path, passes: int = 3) -> None:
        """
        Securely delete a file by overwriting before unlinking.
        
        Args:
            path: Path to file.
            passes: Number of overwrite passes.
        """
        pass
    
    @abstractmethod
    def lock_memory(self, address: int, size: int) -> bool:
        """
        Lock memory pages to prevent swapping (mlock).
        
        Args:
            address: Memory address.
            size: Size in bytes.
        
        Returns:
            True if successful.
        """
        pass
    
    @abstractmethod
    def unlock_memory(self, address: int, size: int) -> bool:
        """
        Unlock previously locked memory.
        
        Args:
            address: Memory address.
            size: Size in bytes.
        
        Returns:
            True if successful.
        """
        pass
    
    @abstractmethod
    def get_secure_random(self, size: int) -> bytes:
        """
        Get cryptographically secure random bytes.
        
        Args:
            size: Number of bytes.
        
        Returns:
            Random bytes.
        """
        pass
    
    # ========================================================================
    # FUSE Operations
    # ========================================================================
    
    @abstractmethod
    def is_fuse_available(self) -> bool:
        """Check if FUSE is available on this platform."""
        pass
    
    @abstractmethod
    def get_fuse_version(self) -> Optional[str]:
        """Get FUSE version if available."""
        pass
    
    @abstractmethod
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
        
        Args:
            operations: FUSE operations object.
            mountpoint: Mount point path.
            foreground: Run in foreground.
            allow_other: Allow other users access.
            **kwargs: Additional mount options.
        
        Returns:
            Mount handle or None.
        """
        pass
    
    @abstractmethod
    def unmount_fuse(self, mountpoint: Path) -> bool:
        """
        Unmount a FUSE filesystem.
        
        Args:
            mountpoint: Mount point path.
        
        Returns:
            True if successful.
        """
        pass
    
    # ========================================================================
    # System Information
    # ========================================================================
    
    @abstractmethod
    def get_memory_info(self) -> Dict[str, int]:
        """
        Get system memory information.
        
        Returns:
            Dict with 'total', 'available', 'used' in bytes.
        """
        pass
    
    @abstractmethod
    def get_cpu_count(self) -> int:
        """Get number of CPU cores."""
        pass
    
    @abstractmethod
    def is_admin(self) -> bool:
        """Check if running with administrator/root privileges."""
        pass
    
    # ========================================================================
    # Container Detection
    # ========================================================================
    
    def detect_container(self) -> Tuple[bool, Optional[str]]:
        """
        Detect if running inside a container.
        
        Returns:
            Tuple of (is_container, container_type).
        """
        # Check for Docker
        if Path('/.dockerenv').exists():
            return True, 'docker'
        
        # Check cgroup for docker
        try:
            with open('/proc/1/cgroup', 'r') as f:
                content = f.read()
                if 'docker' in content:
                    return True, 'docker'
                if 'kubepods' in content:
                    return True, 'kubernetes'
                if 'lxc' in content:
                    return True, 'lxc'
        except (FileNotFoundError, PermissionError):
            pass
        
        # Check for Podman
        if os.environ.get('container') == 'podman':
            return True, 'podman'
        
        # Check for generic container env
        if os.environ.get('container'):
            return True, os.environ.get('container')
        
        return False, None
    
    # ========================================================================
    # Utility Methods
    # ========================================================================
    
    def require_capability(self, capability: PlatformCapabilities) -> None:
        """
        Raise if platform doesn't have required capability.
        
        Args:
            capability: Required capability.
        
        Raises:
            PlatformNotSupportedError: If capability not available.
        """
        if capability not in self.capabilities:
            raise PlatformNotSupportedError(
                capability.name,
                self.info.name
            )
    
    def has_capability(self, capability: PlatformCapabilities) -> bool:
        """
        Check if platform has capability.
        
        Args:
            capability: Capability to check.
        
        Returns:
            True if capability is available.
        """
        return capability in self.capabilities
    
    def __repr__(self) -> str:
        """String representation."""
        return f"{self.__class__.__name__}(platform={self.info.name})"


# ============================================================================
# Platform Detection and Factory
# ============================================================================

def detect_platform() -> str:
    """
    Detect the current platform.
    
    Returns:
        Platform name: 'linux', 'windows', or 'darwin'.
    """
    return sys.platform if sys.platform in ('linux', 'darwin') else 'windows'


def get_current_platform() -> Platform:
    """
    Get the Platform instance for the current OS.
    
    Returns:
        Platform instance appropriate for current OS.
    
    Raises:
        PlatformNotSupportedError: If platform isn't supported.
    """
    platform_name = detect_platform()
    
    if platform_name == 'linux':
        from .linux import LinuxPlatform
        return LinuxPlatform()
    
    elif platform_name == 'darwin':
        from .macos import MacOSPlatform
        return MacOSPlatform()
    
    elif platform_name == 'windows' or sys.platform == 'win32':
        from .windows import WindowsPlatform
        return WindowsPlatform()
    
    else:
        raise PlatformNotSupportedError(
            'Platform',
            platform_name
        )


def is_supported_platform() -> bool:
    """Check if current platform is supported."""
    return detect_platform() in ('linux', 'darwin', 'windows')
