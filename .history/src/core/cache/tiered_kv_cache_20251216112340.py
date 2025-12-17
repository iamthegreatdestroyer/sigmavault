"""
Tiered KV Cache
===============

Multi-level KV cache with L1/L2/L3 tiers for optimal memory management.
L1 (hot) -> L2 (warm) -> L3 (cold/ΣVAULT)
"""

from dataclasses import dataclass, field
from collections import OrderedDict
from typing import Optional, Dict, Any, Tuple
from datetime import datetime
import time


@dataclass
class CacheEntry:
    """Single cache entry with metadata."""
    
    key: str
    kv_state: Any
    size_bytes: int = 0
    access_count: int = 0
    created_at: datetime = field(default_factory=datetime.utcnow)
    last_accessed: datetime = field(default_factory=datetime.utcnow)
    tier: str = "l1"
    
    def touch(self) -> None:
        """Update access metadata."""
        self.last_accessed = datetime.utcnow()
        self.access_count += 1


@dataclass
class TieredCacheConfig:
    """Configuration for tiered cache."""
    
    # L1: Hot cache (fastest, smallest)
    l1_max_entries: int = 100
    l1_max_size_mb: int = 512
    
    # L2: Warm cache (medium)
    l2_max_entries: int = 1000
    l2_max_size_mb: int = 2048
    
    # L3: Cold cache (ΣVAULT backed)
    l3_enabled: bool = True
    l3_vault_path: str = ""
    
    # Eviction policy
    eviction_policy: str = "lru"  # lru, lfu, fifo


class TieredKVCache:
    """
    L1 (hot) -> L2 (warm) -> L3 (cold/ΣVAULT) cache.
    
    Features:
    - Multi-tier caching with automatic promotion/demotion
    - LRU eviction within each tier
    - Statistics tracking
    - Optional ΣVAULT integration for L3
    """
    
    def __init__(self, config: TieredCacheConfig = None):
        self.config = config or TieredCacheConfig()
        
        # L1: Hot cache (OrderedDict for LRU)
        self._l1: OrderedDict[str, CacheEntry] = OrderedDict()
        
        # L2: Warm cache
        self._l2: OrderedDict[str, CacheEntry] = OrderedDict()
        
        # L3: Cold cache keys (actual data in ΣVAULT)
        self._l3_keys: set = set()
        self._l3_backend: Optional[Any] = None
        
        # Statistics
        self._stats = {
            "l1_hits": 0,
            "l2_hits": 0,
            "l3_hits": 0,
            "misses": 0,
            "promotions": 0,
            "demotions": 0,
            "evictions": 0,
        }
        
        # Size tracking
        self._l1_size_bytes = 0
        self._l2_size_bytes = 0
    
    def get(self, key: str) -> Optional[Any]:
        """
        Get value from cache, checking all tiers.
        
        Promotes entries from lower tiers to higher tiers on access.
        """
        # L1: Hot cache (fastest)
        if key in self._l1:
            entry = self._l1[key]
            entry.touch()
            self._l1.move_to_end(key)  # LRU update
            self._stats["l1_hits"] += 1
            return entry.kv_state
        
        # L2: Warm cache
        if key in self._l2:
            entry = self._l2.pop(key)
            entry.touch()
            entry.tier = "l1"
            self._promote_to_l1(key, entry)
            self._stats["l2_hits"] += 1
            self._stats["promotions"] += 1
            return entry.kv_state
        
        # L3: Cold cache (ΣVAULT)
        if self.config.l3_enabled and key in self._l3_keys:
            kv_state = self._load_from_l3(key)
            if kv_state is not None:
                entry = CacheEntry(key=key, kv_state=kv_state, tier="l1")
                self._promote_to_l1(key, entry)
                self._l3_keys.remove(key)
                self._stats["l3_hits"] += 1
                self._stats["promotions"] += 1
                return kv_state
        
        self._stats["misses"] += 1
        return None
    
    def put(self, key: str, kv_state: Any, size_bytes: int = 0) -> None:
        """
        Put value into cache (always starts in L1).
        
        May trigger eviction and demotion cascade.
        """
        # Remove from lower tiers if exists
        if key in self._l2:
            old = self._l2.pop(key)
            self._l2_size_bytes -= old.size_bytes
        if key in self._l3_keys:
            self._l3_keys.remove(key)
        
        # Check L1 capacity
        self._ensure_l1_capacity()
        
        # Create entry
        entry = CacheEntry(
            key=key,
            kv_state=kv_state,
            size_bytes=size_bytes,
            tier="l1",
        )
        
        self._l1[key] = entry
        self._l1_size_bytes += size_bytes
    
    def _ensure_l1_capacity(self) -> None:
        """Ensure L1 has capacity, evicting if needed."""
        while len(self._l1) >= self.config.l1_max_entries:
            self._evict_from_l1()
    
    def _evict_from_l1(self) -> None:
        """Evict oldest entry from L1 to L2."""
        if not self._l1:
            return
        
        # Pop oldest (LRU)
        key, entry = self._l1.popitem(last=False)
        self._l1_size_bytes -= entry.size_bytes
        
        # Demote to L2
        entry.tier = "l2"
        self._ensure_l2_capacity()
        self._l2[key] = entry
        self._l2_size_bytes += entry.size_bytes
        
        self._stats["demotions"] += 1
    
    def _ensure_l2_capacity(self) -> None:
        """Ensure L2 has capacity, evicting if needed."""
        while len(self._l2) >= self.config.l2_max_entries:
            self._evict_from_l2()
    
    def _evict_from_l2(self) -> None:
        """Evict oldest entry from L2 to L3 or discard."""
        if not self._l2:
            return
        
        # Pop oldest (LRU)
        key, entry = self._l2.popitem(last=False)
        self._l2_size_bytes -= entry.size_bytes
        
        # Demote to L3 or evict
        if self.config.l3_enabled:
            self._store_to_l3(key, entry.kv_state)
            self._l3_keys.add(key)
            self._stats["demotions"] += 1
        else:
            self._stats["evictions"] += 1
    
    def _promote_to_l1(self, key: str, entry: CacheEntry) -> None:
        """Promote entry to L1."""
        self._ensure_l1_capacity()
        self._l1[key] = entry
        self._l1_size_bytes += entry.size_bytes
    
    def _store_to_l3(self, key: str, kv_state: Any) -> None:
        """Store entry to L3 (ΣVAULT)."""
        if self._l3_backend:
            try:
                self._l3_backend.store(key, kv_state)
            except Exception:
                pass  # Silently fail L3 writes
    
    def _load_from_l3(self, key: str) -> Optional[Any]:
        """Load entry from L3 (ΣVAULT)."""
        if self._l3_backend:
            try:
                return self._l3_backend.retrieve(key)
            except Exception:
                pass
        return None
    
    def set_l3_backend(self, backend: Any) -> None:
        """Set L3 backend (ΣVAULT integration)."""
        self._l3_backend = backend
    
    def contains(self, key: str) -> bool:
        """Check if key exists in any tier."""
        return key in self._l1 or key in self._l2 or key in self._l3_keys
    
    def remove(self, key: str) -> bool:
        """Remove key from all tiers."""
        removed = False
        
        if key in self._l1:
            entry = self._l1.pop(key)
            self._l1_size_bytes -= entry.size_bytes
            removed = True
        
        if key in self._l2:
            entry = self._l2.pop(key)
            self._l2_size_bytes -= entry.size_bytes
            removed = True
        
        if key in self._l3_keys:
            self._l3_keys.remove(key)
            removed = True
        
        return removed
    
    def clear(self) -> None:
        """Clear all tiers."""
        self._l1.clear()
        self._l2.clear()
        self._l3_keys.clear()
        self._l1_size_bytes = 0
        self._l2_size_bytes = 0
    
    def get_stats(self) -> Dict[str, Any]:
        """Get cache statistics."""
        total_hits = self._stats["l1_hits"] + self._stats["l2_hits"] + self._stats["l3_hits"]
        total_accesses = total_hits + self._stats["misses"]
        hit_rate = total_hits / max(1, total_accesses)
        
        return {
            **self._stats,
            "hit_rate": hit_rate,
            "l1_size": len(self._l1),
            "l2_size": len(self._l2),
            "l3_size": len(self._l3_keys),
            "l1_bytes": self._l1_size_bytes,
            "l2_bytes": self._l2_size_bytes,
            "total_entries": len(self._l1) + len(self._l2) + len(self._l3_keys),
        }
    
    def get_tier_distribution(self) -> Dict[str, int]:
        """Get entry count per tier."""
        return {
            "l1": len(self._l1),
            "l2": len(self._l2),
            "l3": len(self._l3_keys),
        }


# Factory function
def create_tiered_cache(
    l1_size: int = 100,
    l2_size: int = 1000,
    enable_l3: bool = True,
) -> TieredKVCache:
    """Create tiered cache with configuration."""
    config = TieredCacheConfig(
        l1_max_entries=l1_size,
        l2_max_entries=l2_size,
        l3_enabled=enable_l3,
    )
    return TieredKVCache(config)
