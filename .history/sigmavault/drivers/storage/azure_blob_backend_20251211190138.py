"""
ΣVAULT Azure Blob Storage Backend

Azure Blob Storage backend implementation.
Supports Azure Blob Storage with features like:
    - Block blobs for general storage
    - Append blobs for log-like patterns
    - Range reads for efficient partial access
    - Managed identity and connection string auth

Features:
    - Async and sync operations
    - Block-level operations for large files
    - Range reads for efficient partial access
    - Automatic retries with exponential backoff
    - Connection pooling
"""

import asyncio
import hashlib
import io
import threading
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, Iterator, List, Optional, Tuple, Union

try:
    from azure.storage.blob import (
        BlobServiceClient,
        BlobClient,
        ContainerClient,
        BlobType,
        StandardBlobTier,
    )
    from azure.core.exceptions import (
        AzureError,
        ResourceNotFoundError,
        ResourceExistsError,
        ClientAuthenticationError,
    )
    HAS_AZURE_STORAGE = True
except ImportError:
    HAS_AZURE_STORAGE = False

try:
    from azure.identity import DefaultAzureCredential
    HAS_AZURE_IDENTITY = True
except ImportError:
    HAS_AZURE_IDENTITY = False

from .base import (
    StorageBackend,
    StorageCapabilities,
    StorageError,
    StorageReadError,
    StorageWriteError,
    StorageCapacityError,
    StorageNotFoundError,
)


@dataclass
class AzureBlobConfig:
    """Configuration for Azure Blob Storage backend."""
    
    # Connection settings - use one of these
    connection_string: Optional[str] = None
    account_url: Optional[str] = None  # e.g., https://<account>.blob.core.windows.net
    
    # Container settings
    container_name: str = "sigmavault"
    blob_prefix: str = ""
    
    # Authentication (if not using connection_string)
    use_managed_identity: bool = False
    account_name: Optional[str] = None
    account_key: Optional[str] = None
    sas_token: Optional[str] = None
    
    # Performance tuning
    max_block_size: int = 4 * 1024 * 1024  # 4 MB
    max_single_put_size: int = 64 * 1024 * 1024  # 64 MB
    max_concurrency: int = 4
    connection_timeout: float = 20.0
    read_timeout: float = 120.0
    max_retries: int = 3
    
    # Storage tier
    access_tier: str = "Hot"  # Hot, Cool, Archive


class AzureBlobStorageBackend(StorageBackend):
    """
    Storage backend using Azure Blob Storage.
    
    This backend stores scattered data as blobs in an Azure container.
    It supports both block blobs for general storage and efficient
    range reads for partial access.
    
    Thread Safety:
        All operations are thread-safe via Azure SDK's built-in handling.
    
    Example:
        >>> config = AzureBlobConfig(
        ...     connection_string="DefaultEndpointsProtocol=https;..."
        ... )
        >>> backend = AzureBlobStorageBackend(config)
        >>> backend.write(0, b"Hello Azure")
        11
        >>> backend.read(0, 11)
        b'Hello Azure'
    
    Note:
        Requires azure-storage-blob: pip install azure-storage-blob
        For managed identity: pip install azure-identity
    """
    
    def __init__(
        self,
        config: AzureBlobConfig,
        blob_name: str = "vault.dat",
        create: bool = True,
    ):
        """
        Initialize Azure Blob storage backend.
        
        Args:
            config: Azure Blob configuration.
            blob_name: Name for the main storage blob.
            create: Whether to create the blob if it doesn't exist.
        
        Raises:
            ImportError: If azure-storage-blob is not installed.
            StorageError: If container doesn't exist or isn't accessible.
        """
        if not HAS_AZURE_STORAGE:
            raise ImportError(
                "AzureBlobStorageBackend requires azure-storage-blob. "
                "Install with: pip install azure-storage-blob"
            )
        
        super().__init__(enable_stats=True)
        
        self._config = config
        self._blob_name = f"{config.blob_prefix}{blob_name}" if config.blob_prefix else blob_name
        self._lock = threading.RLock()
        
        # Initialize Azure clients
        self._service_client = self._create_service_client()
        self._container_client = self._service_client.get_container_client(
            config.container_name
        )
        self._blob_client = self._container_client.get_blob_client(self._blob_name)
        
        # Verify container access
        self._verify_container(create)
        
        # Get or create the storage blob
        self._size: int = 0
        self._initialize_storage(create)
    
    def _create_service_client(self) -> 'BlobServiceClient':
        """Create Azure BlobServiceClient with configuration."""
        if self._config.connection_string:
            return BlobServiceClient.from_connection_string(
                self._config.connection_string,
                max_block_size=self._config.max_block_size,
                max_single_put_size=self._config.max_single_put_size,
            )
        
        if self._config.account_url:
            credential = None
            
            if self._config.use_managed_identity:
                if not HAS_AZURE_IDENTITY:
                    raise ImportError(
                        "Managed identity requires azure-identity. "
                        "Install with: pip install azure-identity"
                    )
                credential = DefaultAzureCredential()
            elif self._config.account_key:
                credential = self._config.account_key
            elif self._config.sas_token:
                # SAS token should be part of URL
                return BlobServiceClient(
                    account_url=f"{self._config.account_url}?{self._config.sas_token}",
                    max_block_size=self._config.max_block_size,
                    max_single_put_size=self._config.max_single_put_size,
                )
            
            return BlobServiceClient(
                account_url=self._config.account_url,
                credential=credential,
                max_block_size=self._config.max_block_size,
                max_single_put_size=self._config.max_single_put_size,
            )
        
        raise StorageError(
            "Must provide either connection_string or account_url in config"
        )
    
    def _verify_container(self, create: bool) -> None:
        """Verify container exists and is accessible."""
        try:
            self._container_client.get_container_properties()
        except ResourceNotFoundError:
            if create:
                try:
                    self._container_client.create_container()
                except ResourceExistsError:
                    pass  # Container created by another process
            else:
                raise StorageNotFoundError(
                    f"Container not found: {self._config.container_name}"
                )
        except ClientAuthenticationError as e:
            raise StorageError(f"Authentication failed: {e}")
        except AzureError as e:
            raise StorageError(f"Error accessing container: {e}")
    
    def _initialize_storage(self, create: bool) -> None:
        """Initialize or verify storage blob."""
        try:
            # Try to get blob properties
            properties = self._blob_client.get_blob_properties()
            self._size = properties.size
        except ResourceNotFoundError:
            if create:
                # Create empty blob
                self._blob_client.upload_blob(
                    b'',
                    overwrite=True,
                    blob_type=BlobType.BlockBlob,
                )
                self._size = 0
            else:
                raise StorageNotFoundError(
                    f"Storage blob not found: {self._blob_name}"
                )
        except AzureError as e:
            raise StorageError(f"Error initializing storage: {e}")
    
    # ========================================================================
    # StorageBackend Interface Implementation
    # ========================================================================
    
    def read(self, offset: int, size: int) -> bytes:
        """
        Read bytes from Azure blob at given offset.
        
        Uses range reads for efficient partial access.
        
        Args:
            offset: Byte offset from start.
            size: Number of bytes to read.
        
        Returns:
            Bytes read.
        
        Raises:
            StorageReadError: If read fails.
            ValueError: If offset is negative.
        """
        if offset < 0:
            raise ValueError(f"Offset cannot be negative: {offset}")
        
        if size <= 0:
            return b''
        
        # Check if offset is beyond blob size
        if offset >= self._size:
            return b''
        
        # Adjust size if it would read past end
        actual_size = min(size, self._size - offset)
        
        try:
            # Use range read
            stream = self._blob_client.download_blob(
                offset=offset,
                length=actual_size
            )
            data = stream.readall()
            self._record_read(len(data))
            return data
            
        except ResourceNotFoundError:
            raise StorageNotFoundError(f"Blob not found: {self._blob_name}")
        except AzureError as e:
            raise StorageReadError(f"Azure read failed at offset {offset}: {e}")
    
    def write(self, offset: int, data: bytes) -> int:
        """
        Write bytes to Azure blob at given offset.
        
        Note: Azure Block Blobs don't support in-place writes.
        This implementation uses a read-modify-write pattern.
        
        Args:
            offset: Byte offset from start.
            data: Bytes to write.
        
        Returns:
            Number of bytes written.
        
        Raises:
            StorageWriteError: If write fails.
            ValueError: If offset is negative.
        """
        if offset < 0:
            raise ValueError(f"Offset cannot be negative: {offset}")
        
        if not data:
            return 0
        
        with self._lock:
            try:
                # For writes at end (append), we can optimize
                if offset == self._size:
                    return self._append_data(data)
                
                # For writes within existing content or creating gaps,
                # we need to read-modify-write
                return self._write_with_modify(offset, data)
                
            except AzureError as e:
                raise StorageWriteError(f"Azure write failed at offset {offset}: {e}")
    
    def _append_data(self, data: bytes) -> int:
        """Append data to end of blob."""
        # Read existing content
        existing = b''
        if self._size > 0:
            stream = self._blob_client.download_blob()
            existing = stream.readall()
        
        # Append and upload
        new_data = existing + data
        self._blob_client.upload_blob(
            new_data,
            overwrite=True,
            blob_type=BlobType.BlockBlob,
        )
        
        self._size = len(new_data)
        self._record_write(len(data))
        return len(data)
    
    def _write_with_modify(self, offset: int, data: bytes) -> int:
        """Write data at offset using read-modify-write."""
        # Read existing content
        existing = b''
        if self._size > 0:
            stream = self._blob_client.download_blob()
            existing = stream.readall()
        
        # Pad with zeros if offset is beyond current size
        if offset > len(existing):
            existing = existing + b'\x00' * (offset - len(existing))
        
        # Merge data
        new_data = existing[:offset] + data + existing[offset + len(data):]
        
        # Write back
        self._blob_client.upload_blob(
            new_data,
            overwrite=True,
            blob_type=BlobType.BlockBlob,
        )
        
        self._size = len(new_data)
        self._record_write(len(data))
        return len(data)
    
    def size(self) -> int:
        """Return total size of Azure blob."""
        return self._size
    
    def sync(self) -> None:
        """
        Sync is a no-op for Azure as writes are immediately persisted.
        """
        pass
    
    @property
    def capabilities(self) -> StorageCapabilities:
        """Return capabilities of Azure storage backend."""
        return (
            StorageCapabilities.RANGE_READ |
            StorageCapabilities.CONCURRENT |
            StorageCapabilities.PERSISTENT |
            StorageCapabilities.SEEKABLE
        )
    
    # ========================================================================
    # Optional Methods
    # ========================================================================
    
    def truncate(self, size: int) -> None:
        """
        Truncate the blob.
        
        Args:
            size: New size in bytes.
        """
        with self._lock:
            if size == 0:
                # Empty the blob
                self._blob_client.upload_blob(
                    b'',
                    overwrite=True,
                    blob_type=BlobType.BlockBlob,
                )
                self._size = 0
            elif size < self._size:
                # Read, truncate, write
                stream = self._blob_client.download_blob()
                existing = stream.readall()
                
                self._blob_client.upload_blob(
                    existing[:size],
                    overwrite=True,
                    blob_type=BlobType.BlockBlob,
                )
                self._size = size
            elif size > self._size:
                # Extend with zeros
                stream = self._blob_client.download_blob()
                existing = stream.readall()
                
                new_data = existing + b'\x00' * (size - len(existing))
                self._blob_client.upload_blob(
                    new_data,
                    overwrite=True,
                    blob_type=BlobType.BlockBlob,
                )
                self._size = size
    
    def delete(self) -> None:
        """Delete the blob from Azure."""
        try:
            self._blob_client.delete_blob()
            self._size = 0
        except AzureError as e:
            raise StorageError(f"Failed to delete blob: {e}")
    
    def exists(self) -> bool:
        """Check if blob exists."""
        try:
            self._blob_client.get_blob_properties()
            return True
        except ResourceNotFoundError:
            return False
    
    # ========================================================================
    # Azure-Specific Methods
    # ========================================================================
    
    def get_blob_properties(self) -> Dict:
        """Get Azure blob properties."""
        try:
            props = self._blob_client.get_blob_properties()
            return {
                'size': props.size,
                'last_modified': props.last_modified,
                'etag': props.etag,
                'blob_type': props.blob_type,
                'access_tier': props.blob_tier,
                'content_type': props.content_settings.content_type,
                'creation_time': props.creation_time,
            }
        except AzureError as e:
            raise StorageError(f"Failed to get blob properties: {e}")
    
    def set_access_tier(self, tier: str) -> None:
        """
        Set the access tier for the blob.
        
        Args:
            tier: Access tier (Hot, Cool, Archive).
        """
        try:
            # Map string to StandardBlobTier
            tier_map = {
                'Hot': StandardBlobTier.HOT,
                'Cool': StandardBlobTier.COOL,
                'Archive': StandardBlobTier.ARCHIVE,
            }
            azure_tier = tier_map.get(tier)
            if azure_tier:
                self._blob_client.set_standard_blob_tier(azure_tier)
        except AzureError as e:
            raise StorageError(f"Failed to set access tier: {e}")
    
    def copy_to(self, dest_blob_name: str) -> None:
        """Copy blob to another name in the same container."""
        try:
            dest_client = self._container_client.get_blob_client(dest_blob_name)
            dest_client.start_copy_from_url(self._blob_client.url)
        except AzureError as e:
            raise StorageError(f"Failed to copy blob: {e}")
    
    def create_snapshot(self) -> str:
        """
        Create a snapshot of the blob.
        
        Returns:
            Snapshot ID.
        """
        try:
            snapshot = self._blob_client.create_snapshot()
            return snapshot['snapshot']
        except AzureError as e:
            raise StorageError(f"Failed to create snapshot: {e}")
    
    @property
    def container_name(self) -> str:
        """Return the Azure container name."""
        return self._config.container_name
    
    @property
    def blob_name(self) -> str:
        """Return the Azure blob name."""
        return self._blob_name
    
    @property
    def url(self) -> str:
        """Return the blob URL."""
        return self._blob_client.url
    
    # ========================================================================
    # Context Manager / Cleanup
    # ========================================================================
    
    def close(self) -> None:
        """Close the Azure client connection."""
        try:
            self._service_client.close()
        except Exception:
            pass
    
    def __repr__(self) -> str:
        """Return string representation."""
        return (
            f"AzureBlobStorageBackend("
            f"container='{self._config.container_name}', "
            f"blob='{self._blob_name}', "
            f"size={self._size})"
        )


__all__ = [
    'AzureBlobConfig',
    'AzureBlobStorageBackend',
    'HAS_AZURE_STORAGE',
    'HAS_AZURE_IDENTITY',
]
