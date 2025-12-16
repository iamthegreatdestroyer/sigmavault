"""
ΣVAULT Platform Driver Unit Tests

Comprehensive tests for platform abstraction layer.
"""

import os
import sys
import pytest
import tempfile
from pathlib import Path
from unittest.mock import patch, MagicMock

from sigmavault.drivers.platform.base import (
    Platform,
    PlatformCapabilities,
    PlatformInfo,
    PlatformError,
    PlatformNotSupportedError,
    detect_platform,
    get_current_platform,
    is_supported_platform,
)


class TestPlatformCapabilities:
    """Test PlatformCapabilities flag enum."""
    
    def test_capability_flags_are_distinct(self):
        """Each capability should have a unique bit."""
        caps = [
            PlatformCapabilities.FUSE,
            PlatformCapabilities.SPARSE_FILES,
            PlatformCapabilities.SYMBOLIC_LINKS,
            PlatformCapabilities.HARD_LINKS,
            PlatformCapabilities.EXTENDED_ATTRS,
            PlatformCapabilities.FILE_LOCKING,
            PlatformCapabilities.MMAP,
            PlatformCapabilities.NATIVE_ENCRYPTION,
            PlatformCapabilities.SECURE_MEMORY,
            PlatformCapabilities.KEY_STORAGE,
            PlatformCapabilities.SECURE_DELETE,
            PlatformCapabilities.ASYNC_IO,
            PlatformCapabilities.DIRECT_IO,
            PlatformCapabilities.COPY_ON_WRITE,
            PlatformCapabilities.CONTAINER_AWARE,
            PlatformCapabilities.CGROUPS,
            PlatformCapabilities.NAMESPACES,
        ]
        
        values = [c.value for c in caps if c.value != 0]
        assert len(values) == len(set(values)), "Capability flags must be unique"
    
    def test_capability_combination(self):
        """Test combining capabilities."""
        caps = PlatformCapabilities.FUSE | PlatformCapabilities.SPARSE_FILES
        
        assert PlatformCapabilities.FUSE in caps
        assert PlatformCapabilities.SPARSE_FILES in caps
        assert PlatformCapabilities.MMAP not in caps
    
    def test_full_posix_combination(self):
        """Test FULL_POSIX preset."""
        full_posix = PlatformCapabilities.FULL_POSIX
        
        assert PlatformCapabilities.FUSE in full_posix
        assert PlatformCapabilities.SPARSE_FILES in full_posix
        assert PlatformCapabilities.SYMBOLIC_LINKS in full_posix
        assert PlatformCapabilities.FILE_LOCKING in full_posix
        assert PlatformCapabilities.MMAP in full_posix
    
    def test_full_security_combination(self):
        """Test FULL_SECURITY preset."""
        full_security = PlatformCapabilities.FULL_SECURITY
        
        assert PlatformCapabilities.NATIVE_ENCRYPTION in full_security
        assert PlatformCapabilities.SECURE_MEMORY in full_security
        assert PlatformCapabilities.KEY_STORAGE in full_security
        assert PlatformCapabilities.SECURE_DELETE in full_security
    
    def test_capability_none(self):
        """Test NONE capability."""
        assert PlatformCapabilities.NONE.value == 0


class TestPlatformInfo:
    """Test PlatformInfo dataclass."""
    
    def test_creation(self):
        """Test creating platform info."""
        info = PlatformInfo(
            name='linux',
            version='5.15.0',
            architecture='x86_64',
            is_64bit=True,
            is_container=False,
        )
        
        assert info.name == 'linux'
        assert info.version == '5.15.0'
        assert info.architecture == 'x86_64'
        assert info.is_64bit is True
        assert info.is_container is False
    
    def test_container_info(self):
        """Test platform info with container."""
        info = PlatformInfo(
            name='linux',
            version='5.15.0',
            architecture='x86_64',
            is_64bit=True,
            is_container=True,
            container_type='docker',
        )
        
        assert info.is_container is True
        assert info.container_type == 'docker'
    
    def test_default_python_version(self):
        """Test default Python version is set."""
        info = PlatformInfo(
            name='linux',
            version='5.15.0',
            architecture='x86_64',
            is_64bit=True,
            is_container=False,
        )
        
        assert info.python_version == sys.version_info[:3]


class TestPlatformDetection:
    """Test platform detection functions."""
    
    def test_detect_platform(self):
        """Test detect_platform returns valid platform."""
        platform = detect_platform()
        assert platform in ('linux', 'darwin', 'windows')
    
    def test_is_supported_platform(self):
        """Test is_supported_platform returns True for current platform."""
        assert is_supported_platform() is True
    
    @pytest.mark.skipif(sys.platform != 'win32', reason="Windows only")
    def test_detect_platform_windows(self):
        """Test platform detection on Windows."""
        assert detect_platform() == 'windows'
    
    @pytest.mark.skipif(sys.platform != 'linux', reason="Linux only")
    def test_detect_platform_linux(self):
        """Test platform detection on Linux."""
        assert detect_platform() == 'linux'
    
    @pytest.mark.skipif(sys.platform != 'darwin', reason="macOS only")
    def test_detect_platform_macos(self):
        """Test platform detection on macOS."""
        assert detect_platform() == 'darwin'


class TestGetCurrentPlatform:
    """Test get_current_platform factory function."""
    
    def test_returns_platform_instance(self):
        """Test that function returns a Platform instance."""
        platform = get_current_platform()
        assert isinstance(platform, Platform)
    
    def test_platform_has_info(self):
        """Test platform has info property."""
        platform = get_current_platform()
        info = platform.info
        
        assert info.name in ('linux', 'darwin', 'windows')
        assert isinstance(info.is_64bit, bool)
        assert isinstance(info.is_container, bool)
    
    def test_platform_has_capabilities(self):
        """Test platform has capabilities property."""
        platform = get_current_platform()
        caps = platform.capabilities
        
        assert isinstance(caps, PlatformCapabilities)


class TestPlatformInterface:
    """Test Platform ABC interface."""
    
    @pytest.fixture
    def platform(self):
        """Get current platform instance."""
        return get_current_platform()
    
    def test_has_required_methods(self, platform):
        """Test platform has all required methods."""
        # Filesystem methods
        assert hasattr(platform, 'create_sparse_file')
        assert hasattr(platform, 'get_file_system_type')
        assert hasattr(platform, 'get_available_space')
        assert hasattr(platform, 'lock_file')
        assert hasattr(platform, 'unlock_file')
        
        # Security methods
        assert hasattr(platform, 'secure_delete')
        assert hasattr(platform, 'lock_memory')
        assert hasattr(platform, 'unlock_memory')
        assert hasattr(platform, 'get_secure_random')
        
        # FUSE methods
        assert hasattr(platform, 'is_fuse_available')
        assert hasattr(platform, 'get_fuse_version')
        assert hasattr(platform, 'mount_fuse')
        assert hasattr(platform, 'unmount_fuse')
        
        # System methods
        assert hasattr(platform, 'get_memory_info')
        assert hasattr(platform, 'get_cpu_count')
        assert hasattr(platform, 'is_admin')
    
    def test_has_capability_method(self, platform):
        """Test has_capability helper method."""
        # Every platform should have at least sparse files
        assert platform.has_capability(PlatformCapabilities.SPARSE_FILES)
    
    def test_require_capability_passes(self, platform):
        """Test require_capability doesn't raise for existing capability."""
        # Sparse files should be universal
        platform.require_capability(PlatformCapabilities.SPARSE_FILES)
    
    def test_require_capability_raises(self, platform):
        """Test require_capability raises for missing capability."""
        # Create a capability that likely doesn't exist
        fake_cap = PlatformCapabilities.NAMESPACES
        
        if fake_cap not in platform.capabilities:
            with pytest.raises(PlatformNotSupportedError):
                platform.require_capability(fake_cap)


class TestPlatformFilesystem:
    """Test platform filesystem operations."""
    
    @pytest.fixture
    def platform(self):
        """Get current platform instance."""
        return get_current_platform()
    
    @pytest.fixture
    def temp_dir(self):
        """Create temporary directory."""
        with tempfile.TemporaryDirectory() as td:
            yield Path(td)
    
    def test_create_sparse_file(self, platform, temp_dir):
        """Test sparse file creation."""
        sparse_path = temp_dir / 'sparse.bin'
        size = 1024 * 1024 * 10  # 10 MB
        
        result = platform.create_sparse_file(sparse_path, size)
        
        assert sparse_path.exists()
        assert sparse_path.stat().st_size == size
        # Result indicates if actually sparse
        assert isinstance(result, bool)
    
    def test_get_available_space(self, platform, temp_dir):
        """Test getting available space."""
        space = platform.get_available_space(temp_dir)
        
        assert isinstance(space, int)
        assert space > 0
    
    def test_get_file_system_type(self, platform, temp_dir):
        """Test getting filesystem type."""
        fs_type = platform.get_file_system_type(temp_dir)
        
        assert isinstance(fs_type, str)
        # Should return something, even if 'unknown'
        assert len(fs_type) > 0


class TestPlatformSecurity:
    """Test platform security operations."""
    
    @pytest.fixture
    def platform(self):
        """Get current platform instance."""
        return get_current_platform()
    
    @pytest.fixture
    def temp_file(self):
        """Create temporary file."""
        fd, path = tempfile.mkstemp()
        os.write(fd, b"secret data for testing")
        os.close(fd)
        yield Path(path)
        # Cleanup if still exists
        if Path(path).exists():
            os.unlink(path)
    
    def test_get_secure_random(self, platform):
        """Test secure random generation."""
        random_bytes = platform.get_secure_random(32)
        
        assert isinstance(random_bytes, bytes)
        assert len(random_bytes) == 32
        
        # Should be different each time
        random_bytes2 = platform.get_secure_random(32)
        assert random_bytes != random_bytes2
    
    def test_secure_delete(self, platform, temp_file):
        """Test secure file deletion."""
        assert temp_file.exists()
        
        platform.secure_delete(temp_file, passes=1)
        
        assert not temp_file.exists()
    
    def test_secure_delete_nonexistent(self, platform):
        """Test secure delete of nonexistent file doesn't raise."""
        nonexistent = Path('/tmp/definitely_does_not_exist_12345.tmp')
        
        # Should not raise
        platform.secure_delete(nonexistent)


class TestPlatformSystem:
    """Test platform system information."""
    
    @pytest.fixture
    def platform(self):
        """Get current platform instance."""
        return get_current_platform()
    
    def test_get_memory_info(self, platform):
        """Test getting memory info."""
        mem_info = platform.get_memory_info()
        
        assert isinstance(mem_info, dict)
        assert 'total' in mem_info
        assert 'available' in mem_info
        assert 'used' in mem_info
        
        # Values should be reasonable
        assert mem_info['total'] > 0
        assert mem_info['available'] >= 0
    
    def test_get_cpu_count(self, platform):
        """Test getting CPU count."""
        cpu_count = platform.get_cpu_count()
        
        assert isinstance(cpu_count, int)
        assert cpu_count >= 1
    
    def test_is_admin(self, platform):
        """Test admin check."""
        is_admin = platform.is_admin()
        
        assert isinstance(is_admin, bool)


class TestPlatformFuse:
    """Test platform FUSE operations."""
    
    @pytest.fixture
    def platform(self):
        """Get current platform instance."""
        return get_current_platform()
    
    def test_is_fuse_available(self, platform):
        """Test FUSE availability check."""
        available = platform.is_fuse_available()
        
        assert isinstance(available, bool)
    
    def test_get_fuse_version(self, platform):
        """Test getting FUSE version."""
        version = platform.get_fuse_version()
        
        # Can be None if FUSE not available
        assert version is None or isinstance(version, str)


class TestContainerDetection:
    """Test container detection functionality."""
    
    @pytest.fixture
    def platform(self):
        """Get current platform instance."""
        return get_current_platform()
    
    def test_detect_container_returns_tuple(self, platform):
        """Test container detection returns tuple."""
        result = platform.detect_container()
        
        assert isinstance(result, tuple)
        assert len(result) == 2
        
        is_container, container_type = result
        assert isinstance(is_container, bool)
        assert container_type is None or isinstance(container_type, str)
    
    def test_container_info_matches(self, platform):
        """Test container info matches detection."""
        is_container, container_type = platform.detect_container()
        info = platform.info
        
        assert info.is_container == is_container
        assert info.container_type == container_type


class TestPlatformNotSupportedError:
    """Test PlatformNotSupportedError exception."""
    
    def test_error_message(self):
        """Test error message format."""
        error = PlatformNotSupportedError('FUSE', 'windows')
        
        assert 'FUSE' in str(error)
        assert 'windows' in str(error)
        assert error.feature == 'FUSE'
        assert error.platform == 'windows'


class TestPlatformRepr:
    """Test Platform string representation."""
    
    def test_repr(self):
        """Test __repr__ output."""
        platform = get_current_platform()
        repr_str = repr(platform)
        
        assert 'Platform' in repr_str
        assert platform.info.name in repr_str.lower()


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
