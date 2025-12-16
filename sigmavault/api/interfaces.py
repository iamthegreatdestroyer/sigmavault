"""ΣVAULT Core Interface Protocols"""

from __future__ import annotations
from abc import abstractmethod
from typing import Any, Dict, List, Optional, Protocol, runtime_checkable

from .types import (
    DeviceFingerprint, GatherResult, IntegrityStatus, KeyBindingMode,
    KeyDerivationParams, LockResult, RetrieveResult, ScatterDimension,
    StorageEntry, StorageTier, StoreResult, VaultInfo, VaultKey,
    VaultState, VaultStatistics,
)


@runtime_checkable
class SecureStorage(Protocol):
    """
    Core secure storage protocol.
    
    PRIMARY integration point for all components.
    """
    
    @abstractmethod
    def store(
        self,
        key: str,
        data: bytes,
        metadata: Optional[Dict[str, Any]] = None,
        tier: StorageTier = StorageTier.PERSISTED,
    ) -> StoreResult:
        """Store data with dimensional scattering."""
        ...
    
    @abstractmethod
    def retrieve(
        self,
        key: str,
        verify_integrity: bool = True,
    ) -> RetrieveResult:
        """Retrieve data by gathering scattered shards."""
        ...
    
    @abstractmethod
    def delete(
        self,
        key: str,
        secure_wipe: bool = True,
    ) -> bool:
        """Delete data and optionally secure-wipe."""
        ...
    
    @abstractmethod
    def exists(self, key: str) -> bool:
        """Check if key exists."""
        ...
    
    @abstractmethod
    def list_keys(
        self,
        prefix: Optional[str] = None,
        include_locked: bool = False,
    ) -> List[str]:
        """List all keys with optional prefix filter."""
        ...
    
    @abstractmethod
    def get_entry(self, key: str) -> Optional[StorageEntry]:
        """Get entry metadata without retrieving data."""
        ...
    
    @abstractmethod
    def get_statistics(self) -> VaultStatistics:
        """Get storage statistics."""
        ...


@runtime_checkable
class VaultManager(Protocol):
    """Vault lifecycle and security management."""
    
    @abstractmethod
    def create_vault(
        self,
        path: str,
        passphrase: str,
        binding_mode: KeyBindingMode = KeyBindingMode.HYBRID,
        dimensions: Optional[List[ScatterDimension]] = None,
    ) -> VaultInfo:
        """Create a new ΣVAULT instance."""
        ...
    
    @abstractmethod
    def open_vault(
        self,
        path: str,
        passphrase: str,
    ) -> SecureStorage:
        """Open an existing vault."""
        ...
    
    @abstractmethod
    def close_vault(self, path: str) -> bool:
        """Close a vault and clear cached keys."""
        ...
    
    @abstractmethod
    def lock_entry(
        self,
        storage: SecureStorage,
        key: str,
        additional_passphrase: Optional[str] = None,
    ) -> LockResult:
        """Apply additional lock to an entry."""
        ...
    
    @abstractmethod
    def unlock_entry(
        self,
        storage: SecureStorage,
        key: str,
        passphrase: str,
    ) -> LockResult:
        """Unlock a locked entry."""
        ...
    
    @abstractmethod
    def change_passphrase(
        self,
        path: str,
        old_passphrase: str,
        new_passphrase: str,
    ) -> bool:
        """Change vault master passphrase."""
        ...
    
    @abstractmethod
    def get_vault_info(self, path: str) -> Optional[VaultInfo]:
        """Get vault information without opening."""
        ...
    
    @abstractmethod
    def verify_integrity(
        self,
        storage: SecureStorage,
        key: Optional[str] = None,
    ) -> IntegrityStatus:
        """Verify data integrity."""
        ...


@runtime_checkable
class VaultFilesystem(Protocol):
    """FUSE filesystem interface for transparent access."""
    
    @abstractmethod
    def mount(
        self,
        vault_path: str,
        mount_point: str,
        passphrase: str,
        foreground: bool = False,
    ) -> bool:
        """Mount vault as filesystem."""
        ...
    
    @abstractmethod
    def unmount(self, mount_point: str) -> bool:
        """Unmount vault filesystem."""
        ...
    
    @abstractmethod
    def is_mounted(self, mount_point: str) -> bool:
        """Check if mount point is active."""
        ...


@runtime_checkable
class VaultFactory(Protocol):
    """Factory for creating ΣVAULT components."""
    
    @abstractmethod
    def create_storage(
        self,
        vault_path: str,
        passphrase: str,
        binding_mode: KeyBindingMode = KeyBindingMode.HYBRID,
    ) -> SecureStorage:
        """Create or open vault storage."""
        ...
    
    @abstractmethod
    def create_vault_manager(self) -> VaultManager:
        """Create vault manager instance."""
        ...
    
    @abstractmethod
    def create_filesystem(self) -> VaultFilesystem:
        """Create FUSE filesystem interface."""
        ...
