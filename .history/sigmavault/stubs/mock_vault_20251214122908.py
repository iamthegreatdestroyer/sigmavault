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
