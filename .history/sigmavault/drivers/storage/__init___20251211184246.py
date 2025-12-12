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
    from .s3_backend import S3StorageBackend
    __all__.append("S3StorageBackend")
except ImportError:
    pass  # boto3 not installed

try:
    from .azure_backend import AzureBlobStorageBackend
    __all__.append("AzureBlobStorageBackend")
except ImportError:
    pass  # azure-storage-blob not installed
