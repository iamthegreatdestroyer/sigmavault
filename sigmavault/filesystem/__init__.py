"""ΣVAULT Filesystem - Transparent FUSE Layer"""

from .fuse_layer import (
    SigmaVaultFS,
    VirtualMetadataIndex,
    VirtualFileEntry,
    FileContentCache,
    VaultLockManager,
    ScatterStorageBackend,
    mount_sigmavault,
)
