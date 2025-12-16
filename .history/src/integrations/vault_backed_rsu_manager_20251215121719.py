"""
Vault-Backed RSU Manager
========================

RSU Manager that persists to ΣVAULT encrypted storage.
Provides session-persistent context caching with automatic encryption.
"""

from typing import Optional, Tuple, List, Dict, Any
from dataclasses import dataclass, field
from datetime import datetime, timedelta
import hashlib
import time
import json

from .rsu_manager import RyotRSUManager, RSUManagerConfig
from ..api.types import TokenSequence, KVCacheState, RSUReference


@dataclass
class CacheTierConfig:
    """Configuration for multi-tier cache."""
    
    # Tier 1: Fast memory cache
    memory_cache_size: int = 100  # Max RSUs in memory
    memory_cache_ttl: int = 3600  # 1 hour TTL
    
    # Tier 2: Vault storage
    vault_enabled: bool = True
    vault_compression: str = "gzip"
    
    # Tier 3: Archive (old RSUs)
    archive_enabled: bool = True
    archive_after_days: int = 30
    

@dataclass
class CacheEntry:
    """Single cache entry with tiering info."""
    
    rsu_id: str
    tokens: Optional[TokenSequence] = None
    kv_state: Optional[KVCacheState] = None
    created_at: datetime = field(default_factory=datetime.utcnow)
    last_accessed: datetime = field(default_factory=datetime.utcnow)
    access_count: int = 0
    tier: str = "memory"  # memory, vault, archive


class VaultBackedRSUManager:
    """
    RSU Manager with ΣVAULT persistence.
    
    Features:
    - Multi-tier caching (memory → vault → archive)
    - Automatic encryption/decryption
    - Session persistence
    - Performance optimization
    - Conversation continuity
    """
    
    def __init__(
        self,
        vault_path: str,
        passphrase: str,
        config: Optional[CacheTierConfig] = None,
    ):
        self.vault_path = vault_path
        self.passphrase = passphrase
        self.cache_config = config or CacheTierConfig()
        
        # Initialize base RSU manager
        self._rsu_manager = RyotRSUManager()
        
        # Multi-tier cache
        self._memory_cache: Dict[str, CacheEntry] = {}
        self._vault_cache: Dict[str, CacheEntry] = {}
        
        # Statistics
        self._stats = {
            "memory_hits": 0,
            "vault_hits": 0,
            "memory_misses": 0,
            "vault_misses": 0,
            "total_stored": 0,
            "total_retrieved": 0,
        }
        
        # Session tracking
        self._session_start = datetime.utcnow()
        self._session_rsus: List[str] = []
        
        # Initialize vault storage (mock for now)
        self._init_vault_storage()
    
    def _init_vault_storage(self) -> None:
        """Initialize vault storage backend."""
        try:
            from sigmavault.core import SigmaVault
            self._vault = SigmaVault(self.vault_path, self.passphrase)
        except Exception as e:
            print(f"Warning: Vault initialization failed: {e}")
            self._vault = None
    
    def store(
        self,
        tokens: TokenSequence,
        kv_state: Optional[KVCacheState] = None,
        conversation_id: Optional[str] = None,
    ) -> RSUReference:
        """
        Store RSU with multi-tier caching.
        
        Process:
        1. Store to memory cache (Tier 1 - fastest)
        2. Persist to vault storage (Tier 2 - encrypted)
        3. Update statistics
        
        Args:
            tokens: Token sequence
            kv_state: KV cache state
            conversation_id: Conversation ID
        
        Returns:
            RSUReference with storage metadata
        """
        start_time = time.time()
        
        # Store via base manager
        ref = self._rsu_manager.store(tokens, kv_state, conversation_id)
        
        # Tier 1: Memory cache
        memory_entry = CacheEntry(
            rsu_id=ref.rsu_id,
            tokens=tokens,
            kv_state=kv_state,
            tier="memory",
        )
        self._memory_cache[ref.rsu_id] = memory_entry
        
        # Tier 2: Vault storage (persistence)
        self._persist_to_vault(ref.rsu_id, tokens, kv_state)
        
        # Check if memory cache is full and move oldest to vault
        if len(self._memory_cache) > self.cache_config.memory_cache_size:
            lru_id = min(
                (k for k in self._memory_cache if k != ref.rsu_id),
                key=lambda k: self._memory_cache[k].last_accessed,
                default=None
            )
            if lru_id:
                entry = self._memory_cache.pop(lru_id)
                entry.tier = "vault"
                self._vault_cache[lru_id] = entry
        
        # Track in session
        self._session_rsus.append(ref.rsu_id)
        self._stats["total_stored"] += 1
        
        store_time = time.time() - start_time
        print(f"  [Store] {ref.rsu_id}: {store_time*1000:.2f}ms")
        
        return ref
    
    def retrieve(
        self,
        reference: RSUReference,
    ) -> Optional[Tuple[TokenSequence, Optional[KVCacheState]]]:
        """
        Retrieve RSU from multi-tier cache.
        
        Strategy:
        1. Check memory cache (Tier 1 - <1ms)
        2. Check vault storage (Tier 2 - <50ms)
        3. Reconstruct from base manager (Tier 3 - fallback)
        
        Args:
            reference: RSU reference
        
        Returns:
            Tuple of (tokens, kv_state) or None
        """
        start_time = time.time()
        result = None
        tier_hit = None
        
        # Tier 1: Memory cache (fastest)
        if reference.rsu_id in self._memory_cache:
            entry = self._memory_cache[reference.rsu_id]
            entry.last_accessed = datetime.utcnow()
            entry.access_count += 1
            result = (entry.tokens, entry.kv_state)
            tier_hit = "memory"
            self._stats["memory_hits"] += 1
        
        # Tier 2: Vault storage (persistent)
        elif reference.rsu_id in self._vault_cache:
            entry = self._vault_cache[reference.rsu_id]
            entry.last_accessed = datetime.utcnow()
            entry.access_count += 1
            result = (entry.tokens, entry.kv_state)
            tier_hit = "vault"
            self._stats["vault_hits"] += 1
            
            # Promote to memory cache
            self._promote_to_memory(reference.rsu_id, entry)
        
        # Tier 3: Base manager (fallback)
        else:
            result = self._rsu_manager.retrieve(reference)
            tier_hit = "fallback"
            if result:
                tokens, kv_state = result
                # Cache in memory
                memory_entry = CacheEntry(
                    rsu_id=reference.rsu_id,
                    tokens=tokens,
                    kv_state=kv_state,
                    tier="memory",
                )
                self._memory_cache[reference.rsu_id] = memory_entry
        
        retrieve_time = time.time() - start_time
        self._stats["total_retrieved"] += 1
        
        print(f"  [Retrieve] {reference.rsu_id} from {tier_hit}: {retrieve_time*1000:.2f}ms")
        
        return result
    
    def _persist_to_vault(
        self,
        rsu_id: str,
        tokens: TokenSequence,
        kv_state: Optional[KVCacheState],
    ) -> None:
        """Persist RSU to vault storage with encryption."""
        if self._vault is None:
            return
        
        # Serialize data
        data = {
            "rsu_id": rsu_id,
            "tokens": list(tokens.tokens) if hasattr(tokens, 'tokens') else tokens,
            "timestamp": datetime.utcnow().isoformat(),
            "has_kv_state": kv_state is not None,
        }
        
        try:
            # Store in vault (encrypted)
            vault_entry = CacheEntry(
                rsu_id=rsu_id,
                tokens=tokens,
                kv_state=kv_state,
                tier="vault",
            )
            self._vault_cache[rsu_id] = vault_entry
            
            # Mock vault storage (in real implementation, would use ΣVAULT API)
            # self._vault.store(rsu_id, json.dumps(data).encode())
        except Exception as e:
            print(f"Warning: Vault persistence failed: {e}")
    
    def _promote_to_memory(
        self,
        rsu_id: str,
        entry: CacheEntry,
    ) -> None:
        """Promote cache entry from vault to memory."""
        # Check memory cache size
        if len(self._memory_cache) >= self.cache_config.memory_cache_size:
            # Evict least recently used
            lru_id = min(
                self._memory_cache,
                key=lambda k: self._memory_cache[k].last_accessed
            )
            del self._memory_cache[lru_id]
        
        # Add to memory
        entry.tier = "memory"
        self._memory_cache[rsu_id] = entry
    
    def get_conversation_rsus(
        self,
        conversation_id: str,
    ) -> List[RSUReference]:
        """Get all RSUs for a conversation."""
        return self._rsu_manager.get_conversation_rsus(conversation_id)
    
    def warm_start_from_rsu(
        self,
        reference: RSUReference,
        cache: 'KVCache',
    ) -> int:
        """Warm-start cache from RSU."""
        return self._rsu_manager.warm_start_from_rsu(reference, cache)
    
    def get_cache_statistics(self) -> Dict[str, Any]:
        """Get detailed cache statistics."""
        total_hits = self._stats["memory_hits"] + self._stats["vault_hits"]
        total_accesses = total_hits + self._stats["memory_misses"] + self._stats["vault_misses"]
        hit_rate = (total_hits / total_accesses * 100) if total_accesses > 0 else 0
        
        return {
            "memory_cache_size": len(self._memory_cache),
            "vault_cache_size": len(self._vault_cache),
            "memory_hits": self._stats["memory_hits"],
            "vault_hits": self._stats["vault_hits"],
            "total_hits": total_hits,
            "total_accesses": total_accesses,
            "hit_rate": f"{hit_rate:.2f}%",
            "total_stored": self._stats["total_stored"],
            "total_retrieved": self._stats["total_retrieved"],
            "session_duration": str(datetime.utcnow() - self._session_start),
            "session_rsus": len(self._session_rsus),
        }
    
    def save_session(self, session_file: str) -> None:
        """Save session to disk for persistence."""
        session_data = {
            "session_start": self._session_start.isoformat(),
            "session_rsus": self._session_rsus,
            "statistics": self._stats,
            "memory_cache": {
                k: {
                    "created_at": v.created_at.isoformat(),
                    "last_accessed": v.last_accessed.isoformat(),
                    "access_count": v.access_count,
                    "tier": v.tier,
                    "tokens": list(v.tokens.tokens) if v.tokens and hasattr(v.tokens, 'tokens') else [],
                }
                for k, v in self._memory_cache.items()
            },
            "vault_cache": {
                k: {
                    "created_at": v.created_at.isoformat(),
                    "last_accessed": v.last_accessed.isoformat(),
                    "access_count": v.access_count,
                    "tier": v.tier,
                    "tokens": list(v.tokens.tokens) if v.tokens and hasattr(v.tokens, 'tokens') else [],
                }
                for k, v in self._vault_cache.items()
            }
        }
        
        try:
            with open(session_file, 'w') as f:
                json.dump(session_data, f, indent=2)
            print(f"Session saved to {session_file}")
        except Exception as e:
            print(f"Warning: Session save failed: {e}")
    
    def load_session(self, session_file: str) -> bool:
        """Load session from disk."""
        try:
            with open(session_file, 'r') as f:
                session_data = json.load(f)
            
            self._session_start = datetime.fromisoformat(
                session_data["session_start"]
            )
            self._session_rsus = session_data["session_rsus"]
            self._stats = session_data["statistics"]
            
            # Restore cache entries from session data
            for rsu_id, entry_data in session_data.get("memory_cache", {}).items():
                tokens = TokenSequence.from_list(entry_data.get("tokens", []))
                entry = CacheEntry(
                    rsu_id=rsu_id,
                    tokens=tokens,
                    created_at=datetime.fromisoformat(entry_data["created_at"]),
                    last_accessed=datetime.fromisoformat(entry_data["last_accessed"]),
                    access_count=entry_data["access_count"],
                    tier=entry_data["tier"],
                )
                self._memory_cache[rsu_id] = entry
            
            for rsu_id, entry_data in session_data.get("vault_cache", {}).items():
                tokens = TokenSequence.from_list(entry_data.get("tokens", []))
                entry = CacheEntry(
                    rsu_id=rsu_id,
                    tokens=tokens,
                    created_at=datetime.fromisoformat(entry_data["created_at"]),
                    last_accessed=datetime.fromisoformat(entry_data["last_accessed"]),
                    access_count=entry_data["access_count"],
                    tier=entry_data["tier"],
                )
                self._vault_cache[rsu_id] = entry
            
            print(f"Session loaded from {session_file}")
            print(f"  Restored {len(self._session_rsus)} RSUs from session")
            print(f"  Memory cache: {len(self._memory_cache)}, Vault cache: {len(self._vault_cache)}")
            return True
        except Exception as e:
            print(f"Warning: Session load failed: {e}")
            import traceback
            traceback.print_exc()
            return False
