"""
ΣVAULT Platform Driver Package

Provides cross-platform abstractions for filesystem, security,
and system operations. Enables SigmaVault to run on:
    - Linux (primary target)
    - Windows (via WinFsp)
    - macOS (via macFUSE)
    - Containers (Docker, Podman)
"""

from .base import (
    Platform,
    PlatformCapabilities,
    PlatformError,
    PlatformNotSupportedError,
    get_current_platform,
    detect_platform,
)

__all__ = [
    # Core classes
    'Platform',
    'PlatformCapabilities',
    
    # Errors
    'PlatformError',
    'PlatformNotSupportedError',
    
    # Utilities
    'get_current_platform',
    'detect_platform',
]
