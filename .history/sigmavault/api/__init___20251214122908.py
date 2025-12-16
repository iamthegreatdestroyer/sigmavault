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
