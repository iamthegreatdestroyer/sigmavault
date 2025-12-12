"""
ΣVAULT Platform Driver Package

Provides cross-platform abstractions for filesystem, security,
and system operations. Enables SigmaVault to run on:
    - Linux (primary target)
    - Windows (via WinFsp)
    - macOS (via macFUSE)
    - Containers (Docker, Podman, Kubernetes)
"""

from .base import (
    Platform,
    PlatformCapabilities,
    PlatformError,
    PlatformNotSupportedError,
    get_current_platform,
    detect_platform,
)

from .container import (
    ContainerRuntime,
    ContainerInfo,
    ContainerDetector,
    detect_container,
    is_containerized,
    get_container_runtime,
    is_fuse_available_in_container,
)

__all__ = [
    # Core classes
    'Platform',
    'PlatformCapabilities',
    
    # Errors
    'PlatformError',
    'PlatformNotSupportedError',
    
    # Platform utilities
    'get_current_platform',
    'detect_platform',
    
    # Container utilities
    'ContainerRuntime',
    'ContainerInfo',
    'ContainerDetector',
    'detect_container',
    'is_containerized',
    'get_container_runtime',
    'is_fuse_available_in_container',
]
