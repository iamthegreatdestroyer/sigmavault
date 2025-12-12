"""
ΣVAULT Drivers Package

Platform and storage abstraction layers for cross-platform support.

Subpackages:
    storage: Storage backend implementations (file, memory, S3, Azure)
    platform: Platform-specific drivers (Linux, Windows, macOS)
"""

from .storage import (
    StorageBackend,
    FileStorageBackend,
    MemoryStorageBackend,
)
from .platform import (
    Platform,
    get_current_platform,
    PlatformError,
)

__all__ = [
    # Storage backends
    "StorageBackend",
    "FileStorageBackend",
    "MemoryStorageBackend",
    # Platform abstraction
    "Platform",
    "get_current_platform",
    "PlatformError",
]
