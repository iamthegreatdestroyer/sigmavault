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
