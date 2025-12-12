"""
ΣVAULT Windows Platform Implementation

Provides Windows-specific filesystem, security, and WinFsp operations.

Features:
    - WinFsp integration for FUSE-like filesystem support
    - NTFS sparse file support
    - Windows file locking (LockFileEx)
    - VirtualLock for secure memory
    - DPAPI for key storage (future)
"""

from __future__ import annotations

import ctypes
import os
import secrets
import struct
import subprocess
import sys
from pathlib import Path
from typing import Optional, Dict, Any, Tuple, TYPE_CHECKING

from .base import (
    Platform,
    PlatformCapabilities,
    PlatformInfo,
    PlatformError,
    PlatformNotSupportedError,
)


# Windows API constants
GENERIC_READ = 0x80000000
GENERIC_WRITE = 0x40000000
FILE_SHARE_READ = 0x00000001
FILE_SHARE_WRITE = 0x00000002
OPEN_EXISTING = 3
FILE_FLAG_BACKUP_SEMANTICS = 0x02000000
LOCKFILE_EXCLUSIVE_LOCK = 0x00000002
LOCKFILE_FAIL_IMMEDIATELY = 0x00000001

# FSCTL codes for sparse files
FSCTL_SET_SPARSE = 0x000900C4
FSCTL_SET_ZERO_DATA = 0x000980C8


class WindowsPlatform(Platform):
    """
    Windows platform implementation with WinFsp support.
    
    Provides FUSE-like functionality via WinFsp, which must be installed
    separately from https://winfsp.dev/
    
    Example:
        >>> platform = WindowsPlatform()
        >>> print(platform.is_winfsp_available())
        True
        >>> platform.create_sparse_file(Path("test.bin"), 1024*1024*1024)
    """
    
    def __init__(self):
        """Initialize Windows platform."""
        self._info: Optional[PlatformInfo] = None
        self._capabilities: Optional[PlatformCapabilities] = None
        self._kernel32: Optional[ctypes.WinDLL] = None
        self._file_locks: Dict[Path, Any] = {}  # path -> handle
    
    # ========================================================================
    # Abstract Properties Implementation
    # ========================================================================
    
    @property
    def info(self) -> PlatformInfo:
        """Get Windows platform information."""
        if self._info is None:
            self._info = self._detect_info()
        return self._info
    
    @property
    def capabilities(self) -> PlatformCapabilities:
        """Get Windows platform capabilities."""
        if self._capabilities is None:
            self._capabilities = self._detect_capabilities()
        return self._capabilities
    
    # ========================================================================
    # Filesystem Operations
    # ========================================================================
    
    def create_sparse_file(self, path: Path, size: int) -> bool:
        """
        Create a sparse file on NTFS.
        
        Uses DeviceIoControl with FSCTL_SET_SPARSE to enable sparse attribute.
        
        Args:
            path: Path for the new file.
            size: Logical size in bytes.
        
        Returns:
            True if created as sparse.
        """
        try:
            kernel32 = self._get_kernel32()
            
            # Create file
            GENERIC_ALL = GENERIC_READ | GENERIC_WRITE
            CREATE_ALWAYS = 2
            FILE_ATTRIBUTE_NORMAL = 0x80
            
            handle = kernel32.CreateFileW(
                str(path),
                GENERIC_ALL,
                0,
                None,
                CREATE_ALWAYS,
                FILE_ATTRIBUTE_NORMAL,
                None
            )
            
            if handle == -1:
                raise PlatformError(f"Failed to create file: {ctypes.get_last_error()}")
            
            try:
                # Set sparse attribute
                bytes_returned = ctypes.c_ulong(0)
                result = kernel32.DeviceIoControl(
                    handle,
                    FSCTL_SET_SPARSE,
                    None,
                    0,
                    None,
                    0,
                    ctypes.byref(bytes_returned),
                    None
                )
                
                is_sparse = result != 0
                
                # Set file size using SetFilePointerEx + SetEndOfFile
                distance = ctypes.c_longlong(size)
                new_pos = ctypes.c_longlong()
                FILE_BEGIN = 0
                
                kernel32.SetFilePointerEx(handle, distance, ctypes.byref(new_pos), FILE_BEGIN)
                kernel32.SetEndOfFile(handle)
                
                return is_sparse
                
            finally:
                kernel32.CloseHandle(handle)
                
        except OSError as e:
            # Fallback: create regular file with truncate
            with open(path, 'wb') as f:
                f.truncate(size)
            return False
    
    def get_file_system_type(self, path: Path) -> str:
        """
        Get filesystem type using GetVolumeInformation.
        
        Args:
            path: Path to check.
        
        Returns:
            Filesystem type string (ntfs, fat32, refs, etc.).
        """
        try:
            kernel32 = self._get_kernel32()
            
            # Get root path (e.g., C:\)
            root = str(path.resolve().drive) + '\\'
            
            volume_name = ctypes.create_unicode_buffer(261)
            fs_name = ctypes.create_unicode_buffer(261)
            serial_number = ctypes.c_ulong()
            max_component = ctypes.c_ulong()
            flags = ctypes.c_ulong()
            
            result = kernel32.GetVolumeInformationW(
                root,
                volume_name,
                261,
                ctypes.byref(serial_number),
                ctypes.byref(max_component),
                ctypes.byref(flags),
                fs_name,
                261
            )
            
            if result:
                return fs_name.value.lower()
            
            return 'unknown'
            
        except Exception:
            return 'unknown'
    
    def get_available_space(self, path: Path) -> int:
        """
        Get available disk space using GetDiskFreeSpaceEx.
        
        Args:
            path: Path to check.
        
        Returns:
            Available space in bytes.
        """
        try:
            kernel32 = self._get_kernel32()
            
            free_bytes_available = ctypes.c_ulonglong()
            total_bytes = ctypes.c_ulonglong()
            total_free_bytes = ctypes.c_ulonglong()
            
            result = kernel32.GetDiskFreeSpaceExW(
                str(path.resolve().drive) + '\\',
                ctypes.byref(free_bytes_available),
                ctypes.byref(total_bytes),
                ctypes.byref(total_free_bytes)
            )
            
            if result:
                return free_bytes_available.value
            
            return 0
            
        except Exception:
            return 0
    
    def lock_file(self, path: Path, exclusive: bool = True) -> Any:
        """
        Acquire file lock using LockFileEx.
        
        Args:
            path: Path to file.
            exclusive: Whether to acquire exclusive lock.
        
        Returns:
            File handle (used as lock handle).
        """
        try:
            kernel32 = self._get_kernel32()
            
            # Open file
            handle = kernel32.CreateFileW(
                str(path),
                GENERIC_READ | GENERIC_WRITE,
                FILE_SHARE_READ | FILE_SHARE_WRITE,
                None,
                OPEN_EXISTING,
                0,
                None
            )
            
            if handle == -1:
                raise PlatformError(f"Failed to open file for locking")
            
            # Lock file
            flags = LOCKFILE_EXCLUSIVE_LOCK if exclusive else 0
            
            class OVERLAPPED(ctypes.Structure):
                _fields_ = [
                    ("Internal", ctypes.c_void_p),
                    ("InternalHigh", ctypes.c_void_p),
                    ("Offset", ctypes.c_ulong),
                    ("OffsetHigh", ctypes.c_ulong),
                    ("hEvent", ctypes.c_void_p),
                ]
            
            overlapped = OVERLAPPED()
            
            result = kernel32.LockFileEx(
                handle,
                flags,
                0,
                0xFFFFFFFF,  # Lock entire file
                0xFFFFFFFF,
                ctypes.byref(overlapped)
            )
            
            if not result:
                kernel32.CloseHandle(handle)
                raise PlatformError(f"Failed to lock file")
            
            self._file_locks[path] = handle
            return handle
            
        except OSError as e:
            raise PlatformError(f"Failed to lock file: {e}")
    
    def unlock_file(self, lock_handle: Any) -> None:
        """
        Release file lock using UnlockFileEx.
        
        Args:
            lock_handle: File handle from lock_file().
        """
        try:
            kernel32 = self._get_kernel32()
            
            class OVERLAPPED(ctypes.Structure):
                _fields_ = [
                    ("Internal", ctypes.c_void_p),
                    ("InternalHigh", ctypes.c_void_p),
                    ("Offset", ctypes.c_ulong),
                    ("OffsetHigh", ctypes.c_ulong),
                    ("hEvent", ctypes.c_void_p),
                ]
            
            overlapped = OVERLAPPED()
            
            kernel32.UnlockFileEx(
                lock_handle,
                0,
                0xFFFFFFFF,
                0xFFFFFFFF,
                ctypes.byref(overlapped)
            )
            
            kernel32.CloseHandle(lock_handle)
            
            # Remove from tracking
            for path, handle in list(self._file_locks.items()):
                if handle == lock_handle:
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
        
        Note: Less effective on SSDs and NTFS with journaling.
        
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
        Lock memory pages using VirtualLock.
        
        Args:
            address: Memory address.
            size: Size in bytes.
        
        Returns:
            True if successful.
        """
        try:
            kernel32 = self._get_kernel32()
            result = kernel32.VirtualLock(ctypes.c_void_p(address), ctypes.c_size_t(size))
            return result != 0
        except Exception:
            return False
    
    def unlock_memory(self, address: int, size: int) -> bool:
        """
        Unlock memory pages using VirtualUnlock.
        
        Args:
            address: Memory address.
            size: Size in bytes.
        
        Returns:
            True if successful.
        """
        try:
            kernel32 = self._get_kernel32()
            result = kernel32.VirtualUnlock(ctypes.c_void_p(address), ctypes.c_size_t(size))
            return result != 0
        except Exception:
            return False
    
    def get_secure_random(self, size: int) -> bytes:
        """
        Get cryptographically secure random bytes.
        
        Uses CryptGenRandom or secrets module.
        
        Args:
            size: Number of bytes.
        
        Returns:
            Random bytes.
        """
        return secrets.token_bytes(size)
    
    # ========================================================================
    # FUSE Operations (WinFsp)
    # ========================================================================
    
    def is_fuse_available(self) -> bool:
        """Check if WinFsp is available."""
        return self.is_winfsp_available()
    
    def is_winfsp_available(self) -> bool:
        """
        Check if WinFsp is installed.
        
        Checks for WinFsp installation in standard locations.
        """
        winfsp_paths = [
            Path(os.environ.get('ProgramFiles', 'C:\\Program Files')) / 'WinFsp',
            Path(os.environ.get('ProgramFiles(x86)', 'C:\\Program Files (x86)')) / 'WinFsp',
        ]
        
        for winfsp_path in winfsp_paths:
            if winfsp_path.exists():
                return True
        
        # Check registry
        try:
            import winreg
            key = winreg.OpenKey(
                winreg.HKEY_LOCAL_MACHINE,
                r'SOFTWARE\WinFsp',
                0,
                winreg.KEY_READ
            )
            winreg.CloseKey(key)
            return True
        except (FileNotFoundError, ImportError, OSError):
            pass
        
        return False
    
    def get_fuse_version(self) -> Optional[str]:
        """Get WinFsp version."""
        try:
            winfsp_path = self._get_winfsp_path()
            if winfsp_path:
                # Try to read version from file
                launcher = winfsp_path / 'bin' / 'launchctl-x64.exe'
                if launcher.exists():
                    result = subprocess.run(
                        [str(launcher), 'version'],
                        capture_output=True,
                        text=True
                    )
                    if result.returncode == 0:
                        return result.stdout.strip()
        except Exception:
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
        Mount a WinFsp filesystem.
        
        Note: Actual mounting requires the winfspy library.
        This method provides the platform-specific configuration.
        
        Args:
            operations: WinFsp operations object.
            mountpoint: Mount point (drive letter or path).
            foreground: Run in foreground.
            allow_other: Allow other users access.
            **kwargs: Additional mount options.
        
        Returns:
            Mount configuration dict.
        """
        options = {
            'foreground': foreground,
            **kwargs
        }
        
        # Windows-specific options
        options.setdefault('debug', False)
        options.setdefault('umask', 0)
        
        return {
            'operations': operations,
            'mountpoint': str(mountpoint),
            'options': options,
            'platform': 'windows'
        }
    
    def unmount_fuse(self, mountpoint: Path) -> bool:
        """
        Unmount a WinFsp filesystem.
        
        Args:
            mountpoint: Mount point (drive letter or path).
        
        Returns:
            True if successful.
        """
        try:
            winfsp_path = self._get_winfsp_path()
            if winfsp_path:
                launcher = winfsp_path / 'bin' / 'launchctl-x64.exe'
                if launcher.exists():
                    result = subprocess.run(
                        [str(launcher), 'stop', str(mountpoint)],
                        capture_output=True,
                        text=True
                    )
                    return result.returncode == 0
        except Exception:
            pass
        
        return False
    
    def _get_winfsp_path(self) -> Optional[Path]:
        """Get WinFsp installation path."""
        winfsp_paths = [
            Path(os.environ.get('ProgramFiles', 'C:\\Program Files')) / 'WinFsp',
            Path(os.environ.get('ProgramFiles(x86)', 'C:\\Program Files (x86)')) / 'WinFsp',
        ]
        
        for winfsp_path in winfsp_paths:
            if winfsp_path.exists():
                return winfsp_path
        
        return None
    
    # ========================================================================
    # System Information
    # ========================================================================
    
    def get_memory_info(self) -> Dict[str, int]:
        """
        Get system memory information using GlobalMemoryStatusEx.
        
        Returns:
            Dict with 'total', 'available', 'used' in bytes.
        """
        try:
            kernel32 = self._get_kernel32()
            
            class MEMORYSTATUSEX(ctypes.Structure):
                _fields_ = [
                    ("dwLength", ctypes.c_ulong),
                    ("dwMemoryLoad", ctypes.c_ulong),
                    ("ullTotalPhys", ctypes.c_ulonglong),
                    ("ullAvailPhys", ctypes.c_ulonglong),
                    ("ullTotalPageFile", ctypes.c_ulonglong),
                    ("ullAvailPageFile", ctypes.c_ulonglong),
                    ("ullTotalVirtual", ctypes.c_ulonglong),
                    ("ullAvailVirtual", ctypes.c_ulonglong),
                    ("ullAvailExtendedVirtual", ctypes.c_ulonglong),
                ]
            
            status = MEMORYSTATUSEX()
            status.dwLength = ctypes.sizeof(MEMORYSTATUSEX)
            
            kernel32.GlobalMemoryStatusEx(ctypes.byref(status))
            
            return {
                'total': status.ullTotalPhys,
                'available': status.ullAvailPhys,
                'used': status.ullTotalPhys - status.ullAvailPhys
            }
            
        except Exception:
            return {'total': 0, 'available': 0, 'used': 0}
    
    def get_cpu_count(self) -> int:
        """Get number of CPU cores."""
        return os.cpu_count() or 1
    
    def is_admin(self) -> bool:
        """Check if running with Administrator privileges."""
        try:
            return ctypes.windll.shell32.IsUserAnAdmin() != 0
        except Exception:
            return False
    
    # ========================================================================
    # Internal Methods
    # ========================================================================
    
    def _get_kernel32(self) -> ctypes.WinDLL:
        """Get or load kernel32.dll."""
        if self._kernel32 is None:
            self._kernel32 = ctypes.WinDLL('kernel32', use_last_error=True)
        return self._kernel32
    
    def _detect_info(self) -> PlatformInfo:
        """Detect Windows platform information."""
        import platform as plat
        
        is_container, container_type = self.detect_container()
        
        return PlatformInfo(
            name='windows',
            version=plat.version(),
            architecture=plat.machine(),
            is_64bit=struct.calcsize('P') * 8 == 64,
            is_container=is_container,
            container_type=container_type,
            capabilities=self._detect_capabilities()
        )
    
    def _detect_capabilities(self) -> PlatformCapabilities:
        """Detect Windows platform capabilities."""
        caps = PlatformCapabilities.NONE
        
        # WinFsp support (FUSE-like)
        if self.is_winfsp_available():
            caps |= PlatformCapabilities.FUSE
        
        # NTFS sparse files
        caps |= PlatformCapabilities.SPARSE_FILES
        
        # Windows symbolic links (requires admin or developer mode)
        caps |= PlatformCapabilities.SYMBOLIC_LINKS
        caps |= PlatformCapabilities.HARD_LINKS
        
        # File locking
        caps |= PlatformCapabilities.FILE_LOCKING
        
        # Memory mapping
        caps |= PlatformCapabilities.MMAP
        
        # Security
        caps |= PlatformCapabilities.SECURE_MEMORY  # VirtualLock
        caps |= PlatformCapabilities.SECURE_DELETE
        caps |= PlatformCapabilities.KEY_STORAGE    # DPAPI
        
        # Native encryption
        caps |= PlatformCapabilities.NATIVE_ENCRYPTION  # BitLocker
        
        # Async I/O (IOCP)
        caps |= PlatformCapabilities.ASYNC_IO
        
        return caps
    
    def detect_container(self) -> Tuple[bool, Optional[str]]:
        """
        Detect if running inside a Windows container.
        
        Returns:
            Tuple of (is_container, container_type).
        """
        # Check for Docker Desktop
        if os.environ.get('DOCKER_HOST'):
            return True, 'docker'
        
        # Check for Windows containers
        if os.environ.get('ComSpec', '').lower().startswith('c:\\windows\\system32'):
            # Check for container-specific markers
            if Path('C:\\ContainerAdministrator').exists():
                return True, 'windows_container'
        
        return False, None
