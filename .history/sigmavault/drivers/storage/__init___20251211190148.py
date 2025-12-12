"""
ΣVAULT Storage Backend Package

Abstract storage interface and implementations for different storage mediums.

Backends:
    FileStorageBackend: Local filesystem storage
    MemoryStorageBackend: In-memory storage (testing/ephemeral)
    S3StorageBackend: AWS S3 / MinIO compatible storage
    AzureBlobStorageBackend: Azure Blob Storage
"""

from .base import StorageBackend, StorageError, StorageCapabilities
from .file_backend import FileStorageBackend
from .memory_backend import MemoryStorageBackend

__all__ = [
    "StorageBackend",
    "StorageError",
    "StorageCapabilities",
    "FileStorageBackend",
    "MemoryStorageBackend",
]

# Cloud backends are optional - import if available
try:
    from .s3_backend import S3StorageBackend, S3Config, HAS_BOTO3
    __all__.extend(["S3StorageBackend", "S3Config", "HAS_BOTO3"])
except ImportError:
    HAS_BOTO3 = False

try:
    from .azure_blob_backend import (
        AzureBlobStorageBackend,
        AzureBlobConfig,
        HAS_AZURE_STORAGE,
    )
    __all__.extend(["AzureBlobStorageBackend", "AzureBlobConfig", "HAS_AZURE_STORAGE"])
except ImportError:
    HAS_AZURE_STORAGE = False
