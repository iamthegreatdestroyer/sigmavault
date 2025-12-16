# COPILOT DIRECTIVE: ΣVAULT Interface Contracts

## Mission Objective

You are implementing **Phase 0: Interface Contracts** for the ΣVAULT project. This establishes the APIs that Ryot LLM, ΣLANG, and Neurectomy will use for secure storage.

**CRITICAL:** ΣVAULT provides trans-dimensional encrypted storage. These interfaces enable secure storage transparently.

---

## Project Context

**ΣVAULT** is a revolutionary storage system featuring:
- 8-dimensional scatter manifold
- Entropic indistinguishability (signal/noise mixing)
- Hybrid key binding (device + user)
- Transparent FUSE filesystem access

**Integration Role:** ΣVAULT provides secure storage backend for all components.

---

## Task Specification

### Task 1: Create Directory Structure

```
sigmavault/
├── api/
│   ├── __init__.py
│   ├── interfaces.py
│   ├── types.py
│   └── exceptions.py
└── stubs/
    ├── __init__.py
    └── mock_vault.py
```

### Task 2: Create Core Types

**File: `sigmavault/api/types.py`**

```python
"""ΣVAULT Core Type Definitions"""

from __future__ import annotations
from dataclasses import dataclass, field
from enum import Enum, auto
from typing import Any, Dict, List, Optional, Tuple


class ScatterDimension(Enum):
    """The 8 dimensions of ΣVAULT scattering."""
    SPATIAL = auto()
    TEMPORAL = auto()
    ENTROPIC = auto()
    SEMANTIC = auto()
    FRACTAL = auto()
    PHASE = auto()
    TOPOLOGICAL = auto()
    HOLOGRAPHIC = auto()


class KeyBindingMode(Enum):
    """How encryption keys are bound."""
    USER_ONLY = auto()
    DEVICE_ONLY = auto()
    HYBRID = auto()
    PORTABLE = auto()


class VaultState(Enum):
    """State of a vault or entry."""
    UNLOCKED = auto()
    LOCKED = auto()
    SEALED = auto()
    SCATTERED = auto()
    GATHERED = auto()


class StorageTier(Enum):
    """Storage tiers for data lifecycle."""
    ACTIVE = auto()
    CACHED = auto()
    PERSISTED = auto()
    ARCHIVED = auto()


class IntegrityStatus(Enum):
    """Data integrity verification status."""
    VERIFIED = auto()
    PARTIAL = auto()
    CORRUPTED = auto()
    UNKNOWN = auto()


@dataclass(frozen=True)
class DeviceFingerprint:
    """Hardware-derived device identifier."""
    cpu_id: str
    disk_serial: str
    mac_addresses: Tuple[str, ...]
    tpm_endorsement: Optional[str] = None
    
    def to_bytes(self) -> bytes:
        components = [self.cpu_id.encode(), self.disk_serial.encode()]
        return b'\x00'.join(components)


@dataclass
class VaultKey:
    """Encryption key for vault operations."""
    key_id: str
    binding_mode: KeyBindingMode
    key_material: bytes = field(repr=False)
    device_fingerprint: Optional[DeviceFingerprint] = None
    salt: bytes = field(default=b'', repr=False)
    created_timestamp: float = 0.0


@dataclass
class KeyDerivationParams:
    """Parameters for key derivation."""
    algorithm: str = "argon2id"
    memory_cost: int = 65536
    time_cost: int = 3
    parallelism: int = 4
    key_length: int = 32


@dataclass
class StorageEntry:
    """A stored item in ΣVAULT."""
    entry_id: str
    key: str
    state: VaultState
    storage_tier: StorageTier
    manifest_id: str
    metadata: Dict[str, Any] = field(default_factory=dict)
    original_size: int = 0
    scattered_size: int = 0
    created_timestamp: float = 0.0
    modified_timestamp: float = 0.0
    accessed_timestamp: float = 0.0
    is_locked: bool = False
    lock_level: int = 0
    
    @property
    def expansion_ratio(self) -> float:
        if self.original_size == 0:
            return 0.0
        return self.scattered_size / self.original_size


@dataclass
class VaultInfo:
    """Information about a ΣVAULT instance."""
    vault_id: str
    vault_path: str
    binding_mode: KeyBindingMode
    device_bound: bool
    total_entries: int
    total_size_bytes: int
    scattered_size_bytes: int
    integrity_status: IntegrityStatus
    last_integrity_check: float
    dimensions_active: List[ScatterDimension]
    default_entropy_ratio: float
    temporal_reshuffle_interval: int


@dataclass
class GatherResult:
    """Result of gathering scattered data."""
    data: bytes
    integrity_status: IntegrityStatus
    shards_retrieved: int
    shards_total: int
    gather_time_ms: float
    missing_shards: Optional[List[str]] = None
    reconstruction_used: bool = False


@dataclass
class StoreResult:
    """Result of storing data."""
    success: bool
    entry_id: str
    key: str
    original_size: int
    scattered_size: int
    expansion_ratio: float
    scatter_time_ms: float
    num_shards: int
    dimensions_used: List[ScatterDimension]


@dataclass
class RetrieveResult:
    """Result of retrieving data."""
    success: bool
    data: Optional[bytes]
    gather_time_ms: float
    integrity_status: IntegrityStatus
    error_message: Optional[str] = None


@dataclass
class LockResult:
    """Result of lock/unlock operation."""
    success: bool
    new_state: VaultState
    lock_level: int = 0
    error_message: Optional[str] = None


@dataclass
class VaultStatistics:
    """Comprehensive vault statistics."""
    total_entries: int
    locked_entries: int
    active_entries: int
    total_logical_bytes: int
    total_physical_bytes: int
    average_expansion_ratio: float
    total_stores: int
    total_retrieves: int
    average_store_time_ms: float
    average_retrieve_time_ms: float
    integrity_checks_passed: int
    integrity_checks_failed: int
    last_full_check_timestamp: float
    reshuffles_performed: int
    last_reshuffle_timestamp: float
```

### Task 3: Create Interface Protocols

**File: `sigmavault/api/interfaces.py`**

```python
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
```

### Task 4: Create Exceptions

**File: `sigmavault/api/exceptions.py`**

```python
"""ΣVAULT Custom Exceptions"""

from typing import Optional


class VaultError(Exception):
    """Base exception for all ΣVAULT errors."""
    
    def __init__(self, message: str, error_code: str = "VAULT_ERROR", is_retryable: bool = False):
        super().__init__(message)
        self.error_code = error_code
        self.is_retryable = is_retryable


class VaultNotFoundError(VaultError):
    def __init__(self, path: str):
        super().__init__(f"Vault not found: {path}", "VAULT_NOT_FOUND")
        self.path = path


class VaultLockedError(VaultError):
    def __init__(self, message: str = "Vault or entry is locked"):
        super().__init__(message, "VAULT_LOCKED")


class InvalidPassphraseError(VaultError):
    def __init__(self):
        super().__init__("Invalid passphrase", "INVALID_PASSPHRASE")


class DeviceBindingError(VaultError):
    def __init__(self, message: str = "Key not valid on this device"):
        super().__init__(message, "DEVICE_BINDING_ERROR")


class KeyNotFoundError(VaultError):
    def __init__(self, key: str):
        super().__init__(f"Key not found: {key}", "KEY_NOT_FOUND")
        self.key = key


class IntegrityError(VaultError):
    def __init__(self, key: Optional[str] = None):
        message = f"Integrity check failed for: {key}" if key else "Data integrity check failed"
        super().__init__(message, "INTEGRITY_ERROR")
        self.key = key


class ScatterError(VaultError):
    def __init__(self, message: str):
        super().__init__(message, "SCATTER_ERROR", is_retryable=True)


class GatherError(VaultError):
    def __init__(self, message: str, missing_shards: int = 0):
        super().__init__(message, "GATHER_ERROR", is_retryable=True)
        self.missing_shards = missing_shards


class MountError(VaultError):
    def __init__(self, mount_point: str, reason: str):
        super().__init__(f"Failed to mount at {mount_point}: {reason}", "MOUNT_ERROR")
        self.mount_point = mount_point
```

### Task 5: Create Mock Implementation

**File: `sigmavault/stubs/mock_vault.py`**

```python
"""Mock ΣVAULT Implementation for Integration Testing"""

import hashlib
import time
from typing import Any, Dict, List, Optional

from ..api.types import (
    IntegrityStatus, KeyBindingMode, LockResult, RetrieveResult,
    ScatterDimension, StorageEntry, StorageTier, StoreResult,
    VaultInfo, VaultState, VaultStatistics,
)
from ..api.interfaces import SecureStorage, VaultManager


class MockSecureStorage(SecureStorage):
    """Mock secure storage for integration testing."""
    
    def __init__(self, vault_path: str = "/mock/vault"):
        self._vault_path = vault_path
        self._storage: Dict[str, bytes] = {}
        self._metadata: Dict[str, Dict[str, Any]] = {}
        self._entries: Dict[str, StorageEntry] = {}
        self._locked: Dict[str, bool] = {}
        self._stats = {"stores": 0, "retrieves": 0, "store_time": 0.0, "retrieve_time": 0.0}
    
    def store(
        self,
        key: str,
        data: bytes,
        metadata: Optional[Dict[str, Any]] = None,
        tier: StorageTier = StorageTier.PERSISTED,
    ) -> StoreResult:
        start_time = time.time()
        scattered_size = int(len(data) * 2.5)
        
        self._storage[key] = data
        self._metadata[key] = metadata or {}
        self._locked[key] = False
        
        entry = StorageEntry(
            entry_id=f"entry_{hashlib.md5(key.encode()).hexdigest()[:8]}",
            key=key,
            state=VaultState.SCATTERED,
            storage_tier=tier,
            manifest_id=f"manifest_{int(time.time())}",
            metadata=metadata or {},
            original_size=len(data),
            scattered_size=scattered_size,
            created_timestamp=time.time(),
            modified_timestamp=time.time(),
            accessed_timestamp=time.time(),
        )
        self._entries[key] = entry
        
        elapsed = (time.time() - start_time) * 1000
        self._stats["stores"] += 1
        self._stats["store_time"] += elapsed
        
        return StoreResult(
            success=True,
            entry_id=entry.entry_id,
            key=key,
            original_size=len(data),
            scattered_size=scattered_size,
            expansion_ratio=scattered_size / len(data) if data else 0,
            scatter_time_ms=elapsed,
            num_shards=8,
            dimensions_used=[ScatterDimension.SPATIAL, ScatterDimension.ENTROPIC],
        )
    
    def retrieve(self, key: str, verify_integrity: bool = True) -> RetrieveResult:
        start_time = time.time()
        
        if key not in self._storage:
            return RetrieveResult(
                success=False, data=None,
                gather_time_ms=(time.time() - start_time) * 1000,
                integrity_status=IntegrityStatus.UNKNOWN,
                error_message=f"Key not found: {key}",
            )
        
        if self._locked.get(key, False):
            return RetrieveResult(
                success=False, data=None,
                gather_time_ms=(time.time() - start_time) * 1000,
                integrity_status=IntegrityStatus.UNKNOWN,
                error_message="Entry is locked",
            )
        
        data = self._storage[key]
        if key in self._entries:
            self._entries[key].accessed_timestamp = time.time()
        
        elapsed = (time.time() - start_time) * 1000
        self._stats["retrieves"] += 1
        self._stats["retrieve_time"] += elapsed
        
        return RetrieveResult(
            success=True, data=data, gather_time_ms=elapsed,
            integrity_status=IntegrityStatus.VERIFIED if verify_integrity else IntegrityStatus.UNKNOWN,
        )
    
    def delete(self, key: str, secure_wipe: bool = True) -> bool:
        if key in self._storage:
            del self._storage[key]
            self._metadata.pop(key, None)
            self._entries.pop(key, None)
            self._locked.pop(key, None)
            return True
        return False
    
    def exists(self, key: str) -> bool:
        return key in self._storage
    
    def list_keys(self, prefix: Optional[str] = None, include_locked: bool = False) -> List[str]:
        keys = list(self._storage.keys())
        if prefix:
            keys = [k for k in keys if k.startswith(prefix)]
        if not include_locked:
            keys = [k for k in keys if not self._locked.get(k, False)]
        return keys
    
    def get_entry(self, key: str) -> Optional[StorageEntry]:
        return self._entries.get(key)
    
    def get_statistics(self) -> VaultStatistics:
        total_logical = sum(len(d) for d in self._storage.values())
        return VaultStatistics(
            total_entries=len(self._storage),
            locked_entries=sum(1 for v in self._locked.values() if v),
            active_entries=len(self._storage),
            total_logical_bytes=total_logical,
            total_physical_bytes=int(total_logical * 2.5),
            average_expansion_ratio=2.5,
            total_stores=self._stats["stores"],
            total_retrieves=self._stats["retrieves"],
            average_store_time_ms=self._stats["store_time"] / max(1, self._stats["stores"]),
            average_retrieve_time_ms=self._stats["retrieve_time"] / max(1, self._stats["retrieves"]),
            integrity_checks_passed=self._stats["retrieves"],
            integrity_checks_failed=0,
            last_full_check_timestamp=time.time(),
            reshuffles_performed=0,
            last_reshuffle_timestamp=0.0,
        )


class MockVaultManager(VaultManager):
    """Mock vault manager for integration testing."""
    
    def __init__(self):
        self._vaults: Dict[str, MockSecureStorage] = {}
        self._vault_info: Dict[str, VaultInfo] = {}
    
    def create_vault(
        self,
        path: str,
        passphrase: str,
        binding_mode: KeyBindingMode = KeyBindingMode.HYBRID,
        dimensions: Optional[List[ScatterDimension]] = None,
    ) -> VaultInfo:
        storage = MockSecureStorage(path)
        self._vaults[path] = storage
        
        info = VaultInfo(
            vault_id=f"vault_{hashlib.md5(path.encode()).hexdigest()[:8]}",
            vault_path=path,
            binding_mode=binding_mode,
            device_bound=binding_mode in (KeyBindingMode.DEVICE_ONLY, KeyBindingMode.HYBRID),
            total_entries=0,
            total_size_bytes=0,
            scattered_size_bytes=0,
            integrity_status=IntegrityStatus.VERIFIED,
            last_integrity_check=time.time(),
            dimensions_active=dimensions or list(ScatterDimension),
            default_entropy_ratio=0.3,
            temporal_reshuffle_interval=3600,
        )
        self._vault_info[path] = info
        return info
    
    def open_vault(self, path: str, passphrase: str) -> SecureStorage:
        if path not in self._vaults:
            self.create_vault(path, passphrase)
        return self._vaults[path]
    
    def close_vault(self, path: str) -> bool:
        return self._vaults.pop(path, None) is not None
    
    def lock_entry(
        self,
        storage: SecureStorage,
        key: str,
        additional_passphrase: Optional[str] = None,
    ) -> LockResult:
        if isinstance(storage, MockSecureStorage) and key in storage._storage:
            storage._locked[key] = True
            if key in storage._entries:
                storage._entries[key].is_locked = True
                storage._entries[key].state = VaultState.LOCKED
            return LockResult(success=True, new_state=VaultState.LOCKED, lock_level=1)
        return LockResult(success=False, new_state=VaultState.UNLOCKED, error_message="Key not found")
    
    def unlock_entry(self, storage: SecureStorage, key: str, passphrase: str) -> LockResult:
        if isinstance(storage, MockSecureStorage) and key in storage._storage:
            storage._locked[key] = False
            if key in storage._entries:
                storage._entries[key].is_locked = False
                storage._entries[key].state = VaultState.SCATTERED
            return LockResult(success=True, new_state=VaultState.SCATTERED, lock_level=0)
        return LockResult(success=False, new_state=VaultState.LOCKED, error_message="Key not found")
    
    def change_passphrase(self, path: str, old_passphrase: str, new_passphrase: str) -> bool:
        return path in self._vaults
    
    def get_vault_info(self, path: str) -> Optional[VaultInfo]:
        return self._vault_info.get(path)
    
    def verify_integrity(self, storage: SecureStorage, key: Optional[str] = None) -> IntegrityStatus:
        return IntegrityStatus.VERIFIED
```

### Task 6: Create Package Init Files

**File: `sigmavault/api/__init__.py`**

```python
"""ΣVAULT Public API"""

from .interfaces import SecureStorage, VaultManager, VaultFilesystem, VaultFactory
from .types import (
    ScatterDimension, KeyBindingMode, VaultState, StorageTier, IntegrityStatus,
    DeviceFingerprint, VaultKey, KeyDerivationParams, StorageEntry, VaultInfo,
    GatherResult, StoreResult, RetrieveResult, LockResult, VaultStatistics,
)
from .exceptions import (
    VaultError, VaultNotFoundError, VaultLockedError, InvalidPassphraseError,
    DeviceBindingError, KeyNotFoundError, IntegrityError, ScatterError, GatherError, MountError,
)

__all__ = [
    "SecureStorage", "VaultManager", "VaultFilesystem", "VaultFactory",
    "ScatterDimension", "KeyBindingMode", "VaultState", "StorageTier", "IntegrityStatus",
    "DeviceFingerprint", "VaultKey", "KeyDerivationParams", "StorageEntry", "VaultInfo",
    "GatherResult", "StoreResult", "RetrieveResult", "LockResult", "VaultStatistics",
    "VaultError", "VaultNotFoundError", "VaultLockedError", "InvalidPassphraseError",
    "DeviceBindingError", "KeyNotFoundError", "IntegrityError", "ScatterError", "GatherError", "MountError",
]

__version__ = "0.1.0"
```

**File: `sigmavault/stubs/__init__.py`**

```python
"""ΣVAULT Stubs for Integration Testing"""
from .mock_vault import MockSecureStorage, MockVaultManager
__all__ = ["MockSecureStorage", "MockVaultManager"]
```

---

## Verification

```python
from sigmavault.api import SecureStorage, VaultManager, KeyBindingMode
from sigmavault.stubs import MockSecureStorage, MockVaultManager

vault: SecureStorage = MockSecureStorage("/test/vault")
result = vault.store("test/key", b"Hello SIGMAVAULT!")
assert result.success
assert result.expansion_ratio > 1.0

retrieved = vault.retrieve("test/key")
assert retrieved.success
assert retrieved.data == b"Hello SIGMAVAULT!"

print("✓ ΣVAULT interface contracts verified")
```

---

**END OF DIRECTIVE**
