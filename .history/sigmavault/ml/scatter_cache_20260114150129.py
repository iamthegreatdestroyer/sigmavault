"""
Scatter Parameter Cache
========================

High-performance caching layer for scatter parameters with:
- File-specific parameter caching (O(1) lookup)
- TTL-based expiration
- LRU eviction for memory management
- Cache warming and prefetching
- Invalidation triggers based on access patterns

Architecture:
┌─────────────────────────────────────────────────────────────┐
│                  SCATTER PARAMETER CACHE                    │
├─────────────────────────────────────────────────────────────┤
│  L1 CACHE (In-Memory LRU)                                  │
│  ─────────────────────────                                  │
│  • O(1) lookup for hot files                               │
│  • Configurable size limit (default 1000 entries)          │
│  • Thread-safe with RLock                                   │
│                                                             │
│  L2 CACHE (Disk-Backed)                                    │
│  ─────────────────────────                                  │
│  • Persistent across restarts                               │
│  • SQLite for durability                                    │
│  • Lazy loading on miss                                     │
│                                                             │
│  INVALIDATION ENGINE                                        │
│  ─────────────────────────                                  │
│  • Access pattern change detection                          │
│  • Time-based expiration                                    │
│  • Manual invalidation API                                  │
│  • Batch invalidation for directories                       │
└─────────────────────────────────────────────────────────────┘

Copyright (c) 2025 ΣVAULT. All Rights Reserved.
Agents: @TENSOR @VELOCITY @APEX
"""

import os
import json
import hashlib
import sqlite3
import threading
import time
from pathlib import Path
from datetime import datetime, timedelta
from typing import Dict, Optional, List, Tuple, Any, Callable
from dataclasses import dataclass, field
from collections import OrderedDict
from enum import Enum
import pickle

from .adaptive_scatter import ScatterParameters


# ============================================================================
# CACHE CONFIGURATION
# ============================================================================

@dataclass
class CacheConfig:
    """Configuration for scatter parameter cache."""
    
    # L1 cache settings
    l1_max_entries: int = 1000
    l1_ttl_seconds: int = 3600  # 1 hour default
    
    # L2 cache settings
    l2_enabled: bool = True
    l2_ttl_seconds: int = 86400  # 24 hours default
    l2_vacuum_interval: int = 3600  # Vacuum every hour
    
    # Prefetch settings
    prefetch_enabled: bool = True
    prefetch_threshold: int = 3  # Prefetch after N accesses
    prefetch_count: int = 5  # Number of related files to prefetch
    
    # Invalidation settings
    pattern_change_threshold: float = 0.3  # Invalidate if pattern changes >30%
    access_velocity_threshold: float = 2.0  # Invalidate if access rate doubles
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            'l1_max_entries': self.l1_max_entries,
            'l1_ttl_seconds': self.l1_ttl_seconds,
            'l2_enabled': self.l2_enabled,
            'l2_ttl_seconds': self.l2_ttl_seconds,
            'prefetch_enabled': self.prefetch_enabled,
            'pattern_change_threshold': self.pattern_change_threshold
        }


class InvalidationReason(Enum):
    """Reasons for cache invalidation."""
    TTL_EXPIRED = "ttl_expired"
    PATTERN_CHANGED = "pattern_changed"
    ACCESS_VELOCITY_CHANGED = "access_velocity_changed"
    MANUAL = "manual"
    DIRECTORY_INVALIDATION = "directory_invalidation"
    MODEL_RETRAINED = "model_retrained"


@dataclass
class CacheEntry:
    """A cached scatter parameter entry."""
    file_path_hash: str
    parameters: ScatterParameters
    created_at: datetime
    expires_at: datetime
    access_count: int = 0
    last_accessed: datetime = field(default_factory=datetime.now)
    pattern_signature: Optional[str] = None
    
    def is_expired(self) -> bool:
        """Check if entry has expired."""
        return datetime.now() > self.expires_at
    
    def touch(self):
        """Update access time and count."""
        self.last_accessed = datetime.now()
        self.access_count += 1
    
    def to_dict(self) -> Dict[str, Any]:
        """Serialize to dictionary."""
        return {
            'file_path_hash': self.file_path_hash,
            'parameters': self.parameters.to_dict(),
            'created_at': self.created_at.isoformat(),
            'expires_at': self.expires_at.isoformat(),
            'access_count': self.access_count,
            'last_accessed': self.last_accessed.isoformat(),
            'pattern_signature': self.pattern_signature
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'CacheEntry':
        """Deserialize from dictionary."""
        return cls(
            file_path_hash=data['file_path_hash'],
            parameters=ScatterParameters(**data['parameters']),
            created_at=datetime.fromisoformat(data['created_at']),
            expires_at=datetime.fromisoformat(data['expires_at']),
            access_count=data.get('access_count', 0),
            last_accessed=datetime.fromisoformat(data.get('last_accessed', data['created_at'])),
            pattern_signature=data.get('pattern_signature')
        )


# ============================================================================
# L1 CACHE (In-Memory LRU)
# ============================================================================

class L1Cache:
    """
    In-memory LRU cache for hot scatter parameters.
    
    Features:
    - O(1) lookup via OrderedDict
    - Automatic LRU eviction
    - TTL-based expiration
    - Thread-safe operations
    """
    
    def __init__(self, max_entries: int = 1000, ttl_seconds: int = 3600):
        self.max_entries = max_entries
        self.ttl_seconds = ttl_seconds
        self._cache: OrderedDict[str, CacheEntry] = OrderedDict()
        self._lock = threading.RLock()
        
        # Statistics
        self.hits = 0
        self.misses = 0
        self.evictions = 0
    
    def get(self, key: str) -> Optional[CacheEntry]:
        """Get entry from cache (O(1))."""
        with self._lock:
            if key not in self._cache:
                self.misses += 1
                return None
            
            entry = self._cache[key]
            
            # Check expiration
            if entry.is_expired():
                del self._cache[key]
                self.misses += 1
                return None
            
            # Move to end (most recently used)
            self._cache.move_to_end(key)
            entry.touch()
            self.hits += 1
            return entry
    
    def put(self, key: str, entry: CacheEntry):
        """Add entry to cache with LRU eviction."""
        with self._lock:
            # Update expiration
            entry.expires_at = datetime.now() + timedelta(seconds=self.ttl_seconds)
            
            # Remove oldest if at capacity
            while len(self._cache) >= self.max_entries:
                oldest_key = next(iter(self._cache))
                del self._cache[oldest_key]
                self.evictions += 1
            
            self._cache[key] = entry
            self._cache.move_to_end(key)
    
    def invalidate(self, key: str) -> bool:
        """Remove entry from cache."""
        with self._lock:
            if key in self._cache:
                del self._cache[key]
                return True
            return False
    
    def invalidate_prefix(self, prefix: str) -> int:
        """Invalidate all entries matching prefix (directory invalidation)."""
        with self._lock:
            to_remove = [k for k in self._cache.keys() if k.startswith(prefix)]
            for key in to_remove:
                del self._cache[key]
            return len(to_remove)
    
    def clear(self):
        """Clear all entries."""
        with self._lock:
            self._cache.clear()
    
    def get_stats(self) -> Dict[str, Any]:
        """Get cache statistics."""
        with self._lock:
            total = self.hits + self.misses
            return {
                'entries': len(self._cache),
                'max_entries': self.max_entries,
                'hits': self.hits,
                'misses': self.misses,
                'hit_rate': self.hits / total if total > 0 else 0.0,
                'evictions': self.evictions
            }


# ============================================================================
# L2 CACHE (Disk-Backed SQLite)
# ============================================================================

class L2Cache:
    """
    Disk-backed cache using SQLite for persistence.
    
    Features:
    - Survives process restarts
    - Automatic cleanup of expired entries
    - Efficient indexing for fast lookups
    """
    
    def __init__(self, db_path: Path, ttl_seconds: int = 86400):
        self.db_path = db_path
        self.ttl_seconds = ttl_seconds
        self._lock = threading.RLock()
        self._init_db()
    
    def _init_db(self):
        """Initialize SQLite database."""
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        
        with sqlite3.connect(str(self.db_path)) as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS scatter_cache (
                    file_path_hash TEXT PRIMARY KEY,
                    parameters TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    expires_at TEXT NOT NULL,
                    access_count INTEGER DEFAULT 0,
                    last_accessed TEXT,
                    pattern_signature TEXT
                )
            """)
            
            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_expires 
                ON scatter_cache(expires_at)
            """)
            
            conn.commit()
    
    def get(self, key: str) -> Optional[CacheEntry]:
        """Get entry from disk cache."""
        with self._lock:
            with sqlite3.connect(str(self.db_path)) as conn:
                conn.row_factory = sqlite3.Row
                cursor = conn.execute(
                    "SELECT * FROM scatter_cache WHERE file_path_hash = ?",
                    (key,)
                )
                row = cursor.fetchone()
                
                if not row:
                    return None
                
                # Check expiration
                expires_at = datetime.fromisoformat(row['expires_at'])
                if datetime.now() > expires_at:
                    conn.execute(
                        "DELETE FROM scatter_cache WHERE file_path_hash = ?",
                        (key,)
                    )
                    conn.commit()
                    return None
                
                # Update access stats
                conn.execute("""
                    UPDATE scatter_cache 
                    SET access_count = access_count + 1, last_accessed = ?
                    WHERE file_path_hash = ?
                """, (datetime.now().isoformat(), key))
                conn.commit()
                
                # Reconstruct entry
                return CacheEntry(
                    file_path_hash=row['file_path_hash'],
                    parameters=ScatterParameters(**json.loads(row['parameters'])),
                    created_at=datetime.fromisoformat(row['created_at']),
                    expires_at=expires_at,
                    access_count=row['access_count'] + 1,
                    last_accessed=datetime.now(),
                    pattern_signature=row['pattern_signature']
                )
    
    def put(self, key: str, entry: CacheEntry):
        """Store entry in disk cache."""
        with self._lock:
            # Update expiration for L2 TTL
            entry.expires_at = datetime.now() + timedelta(seconds=self.ttl_seconds)
            
            with sqlite3.connect(str(self.db_path)) as conn:
                conn.execute("""
                    INSERT OR REPLACE INTO scatter_cache 
                    (file_path_hash, parameters, created_at, expires_at, 
                     access_count, last_accessed, pattern_signature)
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                """, (
                    entry.file_path_hash,
                    json.dumps(entry.parameters.to_dict()),
                    entry.created_at.isoformat(),
                    entry.expires_at.isoformat(),
                    entry.access_count,
                    entry.last_accessed.isoformat(),
                    entry.pattern_signature
                ))
                conn.commit()
    
    def invalidate(self, key: str) -> bool:
        """Remove entry from disk cache."""
        with self._lock:
            with sqlite3.connect(str(self.db_path)) as conn:
                cursor = conn.execute(
                    "DELETE FROM scatter_cache WHERE file_path_hash = ?",
                    (key,)
                )
                conn.commit()
                return cursor.rowcount > 0
    
    def cleanup_expired(self) -> int:
        """Remove all expired entries."""
        with self._lock:
            with sqlite3.connect(str(self.db_path)) as conn:
                cursor = conn.execute(
                    "DELETE FROM scatter_cache WHERE expires_at < ?",
                    (datetime.now().isoformat(),)
                )
                conn.commit()
                return cursor.rowcount
    
    def vacuum(self):
        """Compact database."""
        with self._lock:
            with sqlite3.connect(str(self.db_path)) as conn:
                conn.execute("VACUUM")
    
    def get_stats(self) -> Dict[str, Any]:
        """Get cache statistics."""
        with self._lock:
            with sqlite3.connect(str(self.db_path)) as conn:
                cursor = conn.execute("SELECT COUNT(*) FROM scatter_cache")
                count = cursor.fetchone()[0]
                
                cursor = conn.execute(
                    "SELECT SUM(access_count) FROM scatter_cache"
                )
                total_accesses = cursor.fetchone()[0] or 0
                
                return {
                    'entries': count,
                    'total_accesses': total_accesses,
                    'db_path': str(self.db_path)
                }


# ============================================================================
# MAIN SCATTER PARAMETER CACHE
# ============================================================================

class ScatterParameterCache:
    """
    Two-level cache for scatter parameters with intelligent invalidation.
    
    Features:
    - L1: Fast in-memory LRU cache
    - L2: Persistent disk-backed cache
    - Automatic invalidation based on access patterns
    - Prefetching for related files
    - Thread-safe operations
    
    Example:
        >>> cache = ScatterParameterCache(vault_path)
        >>> 
        >>> # Try to get cached parameters
        >>> params = cache.get("/path/to/file.txt")
        >>> if params is None:
        >>>     # Compute and cache
        >>>     params = compute_parameters(file_path)
        >>>     cache.put("/path/to/file.txt", params)
    """
    
    def __init__(
        self,
        vault_path: Path,
        config: Optional[CacheConfig] = None
    ):
        self.vault_path = Path(vault_path)
        self.config = config or CacheConfig()
        
        # Initialize caches
        self.l1 = L1Cache(
            max_entries=self.config.l1_max_entries,
            ttl_seconds=self.config.l1_ttl_seconds
        )
        
        if self.config.l2_enabled:
            self.l2 = L2Cache(
                db_path=self.vault_path / '.ml' / 'scatter_cache.db',
                ttl_seconds=self.config.l2_ttl_seconds
            )
        else:
            self.l2 = None
        
        # Access pattern tracking for invalidation
        self._access_patterns: Dict[str, List[float]] = {}
        self._pattern_lock = threading.RLock()
        
        # Callbacks for cache events
        self._invalidation_callbacks: List[Callable[[str, InvalidationReason], None]] = []
        
        # Background cleanup
        self._start_cleanup_thread()
    
    def _hash_path(self, file_path: str) -> str:
        """Hash file path for cache key."""
        return hashlib.sha256(file_path.encode()).hexdigest()
    
    def _compute_pattern_signature(self, access_times: List[float]) -> str:
        """Compute signature of access pattern for change detection."""
        if not access_times:
            return "empty"
        
        import numpy as np
        
        times = np.array(access_times[-100:])  # Last 100 accesses
        
        # Compute pattern features
        if len(times) < 2:
            return hashlib.md5(str(times[0]).encode()).hexdigest()[:8]
        
        intervals = np.diff(times)
        mean_interval = np.mean(intervals)
        std_interval = np.std(intervals)
        
        # Create signature from pattern characteristics
        sig_data = f"{mean_interval:.2f}_{std_interval:.2f}_{len(times)}"
        return hashlib.md5(sig_data.encode()).hexdigest()[:8]
    
    def get(self, file_path: str) -> Optional[ScatterParameters]:
        """
        Get cached parameters for a file.
        
        Checks L1 first, then L2. Returns None if not found or expired.
        """
        key = self._hash_path(file_path)
        
        # Try L1 cache
        entry = self.l1.get(key)
        if entry:
            return entry.parameters
        
        # Try L2 cache
        if self.l2:
            entry = self.l2.get(key)
            if entry:
                # Promote to L1
                self.l1.put(key, entry)
                return entry.parameters
        
        return None
    
    def put(
        self,
        file_path: str,
        parameters: ScatterParameters,
        access_times: Optional[List[float]] = None
    ):
        """
        Cache parameters for a file.
        
        Args:
            file_path: File path
            parameters: Scatter parameters to cache
            access_times: Optional access timestamps for pattern tracking
        """
        key = self._hash_path(file_path)
        
        # Compute pattern signature if available
        pattern_sig = None
        if access_times:
            pattern_sig = self._compute_pattern_signature(access_times)
            with self._pattern_lock:
                self._access_patterns[key] = access_times[-100:]
        
        entry = CacheEntry(
            file_path_hash=key,
            parameters=parameters,
            created_at=datetime.now(),
            expires_at=datetime.now() + timedelta(seconds=self.config.l1_ttl_seconds),
            pattern_signature=pattern_sig
        )
        
        # Store in L1
        self.l1.put(key, entry)
        
        # Store in L2 asynchronously
        if self.l2:
            self.l2.put(key, entry)
    
    def invalidate(
        self,
        file_path: str,
        reason: InvalidationReason = InvalidationReason.MANUAL
    ) -> bool:
        """
        Invalidate cached parameters for a file.
        
        Returns True if entry was found and removed.
        """
        key = self._hash_path(file_path)
        
        l1_removed = self.l1.invalidate(key)
        l2_removed = self.l2.invalidate(key) if self.l2 else False
        
        # Notify callbacks
        if l1_removed or l2_removed:
            for callback in self._invalidation_callbacks:
                try:
                    callback(file_path, reason)
                except Exception:
                    pass
        
        return l1_removed or l2_removed
    
    def invalidate_directory(
        self,
        directory_path: str,
        reason: InvalidationReason = InvalidationReason.DIRECTORY_INVALIDATION
    ) -> int:
        """Invalidate all entries under a directory."""
        prefix = self._hash_path(directory_path)[:16]  # Use partial hash as prefix
        
        # This is a simple implementation - in production you'd want
        # to track directory membership explicitly
        count = self.l1.invalidate_prefix(prefix)
        
        return count
    
    def check_pattern_change(
        self,
        file_path: str,
        current_access_times: List[float]
    ) -> bool:
        """
        Check if access pattern has changed significantly.
        
        Returns True if pattern changed beyond threshold, invalidating cache.
        """
        key = self._hash_path(file_path)
        
        with self._pattern_lock:
            old_pattern = self._access_patterns.get(key, [])
        
        if not old_pattern:
            return False
        
        # Compute pattern similarity
        old_sig = self._compute_pattern_signature(old_pattern)
        new_sig = self._compute_pattern_signature(current_access_times)
        
        # Simple check - signatures should match for stable patterns
        if old_sig != new_sig:
            # Compute actual change magnitude
            import numpy as np
            
            old_intervals = np.diff(old_pattern[-50:]) if len(old_pattern) > 1 else [0]
            new_intervals = np.diff(current_access_times[-50:]) if len(current_access_times) > 1 else [0]
            
            old_mean = np.mean(old_intervals) if len(old_intervals) > 0 else 0
            new_mean = np.mean(new_intervals) if len(new_intervals) > 0 else 0
            
            if old_mean > 0:
                change = abs(new_mean - old_mean) / old_mean
                if change > self.config.pattern_change_threshold:
                    self.invalidate(file_path, InvalidationReason.PATTERN_CHANGED)
                    return True
        
        return False
    
    def check_access_velocity(
        self,
        file_path: str,
        recent_accesses: int,
        time_window_seconds: float
    ) -> bool:
        """
        Check if access velocity has changed significantly.
        
        Returns True if velocity changed beyond threshold.
        """
        key = self._hash_path(file_path)
        
        with self._pattern_lock:
            old_times = self._access_patterns.get(key, [])
        
        if len(old_times) < 10:
            return False
        
        import numpy as np
        
        # Calculate old velocity (accesses per second)
        old_window = old_times[-1] - old_times[0] if len(old_times) > 1 else 1
        old_velocity = len(old_times) / max(old_window, 1)
        
        # Calculate current velocity
        current_velocity = recent_accesses / max(time_window_seconds, 1)
        
        # Check for significant change
        if old_velocity > 0:
            change_ratio = current_velocity / old_velocity
            if change_ratio > self.config.access_velocity_threshold:
                self.invalidate(file_path, InvalidationReason.ACCESS_VELOCITY_CHANGED)
                return True
        
        return False
    
    def invalidate_on_model_retrain(self):
        """Invalidate all cache entries when model is retrained."""
        self.l1.clear()
        if self.l2:
            self.l2.cleanup_expired()  # Don't clear L2 completely, just expired
        
        for callback in self._invalidation_callbacks:
            try:
                callback("*", InvalidationReason.MODEL_RETRAINED)
            except Exception:
                pass
    
    def register_invalidation_callback(
        self,
        callback: Callable[[str, InvalidationReason], None]
    ):
        """Register callback for invalidation events."""
        self._invalidation_callbacks.append(callback)
    
    def get_stats(self) -> Dict[str, Any]:
        """Get comprehensive cache statistics."""
        stats = {
            'l1': self.l1.get_stats(),
            'config': self.config.to_dict(),
            'tracked_patterns': len(self._access_patterns)
        }
        
        if self.l2:
            stats['l2'] = self.l2.get_stats()
        
        return stats
    
    def _start_cleanup_thread(self):
        """Start background thread for periodic cleanup."""
        def cleanup_worker():
            while True:
                try:
                    time.sleep(self.config.l2_vacuum_interval)
                    if self.l2:
                        removed = self.l2.cleanup_expired()
                        if removed > 0:
                            print(f"Cache cleanup: removed {removed} expired entries")
                except Exception as e:
                    print(f"Cache cleanup error: {e}")
        
        thread = threading.Thread(target=cleanup_worker, daemon=True)
        thread.start()


# ============================================================================
# PREFETCH MANAGER
# ============================================================================

class PrefetchManager:
    """
    Intelligent prefetching for related files.
    
    Learns file access patterns and prefetches likely-to-be-accessed files.
    """
    
    def __init__(
        self,
        cache: ScatterParameterCache,
        threshold: int = 3,
        prefetch_count: int = 5
    ):
        self.cache = cache
        self.threshold = threshold
        self.prefetch_count = prefetch_count
        
        # Access co-occurrence tracking
        self._cooccurrence: Dict[str, Dict[str, int]] = {}
        self._lock = threading.RLock()
    
    def record_access(self, file_path: str, session_files: List[str]):
        """
        Record file access and update co-occurrence data.
        
        Args:
            file_path: Currently accessed file
            session_files: Other files accessed in same session
        """
        key = hashlib.sha256(file_path.encode()).hexdigest()[:16]
        
        with self._lock:
            if key not in self._cooccurrence:
                self._cooccurrence[key] = {}
            
            for other in session_files:
                if other != file_path:
                    other_key = hashlib.sha256(other.encode()).hexdigest()[:16]
                    self._cooccurrence[key][other_key] = (
                        self._cooccurrence[key].get(other_key, 0) + 1
                    )
    
    def get_prefetch_candidates(self, file_path: str) -> List[str]:
        """
        Get files that should be prefetched based on co-occurrence.
        
        Returns list of file path hashes to prefetch.
        """
        key = hashlib.sha256(file_path.encode()).hexdigest()[:16]
        
        with self._lock:
            cooccur = self._cooccurrence.get(key, {})
            
            # Sort by co-occurrence count
            sorted_files = sorted(
                cooccur.items(),
                key=lambda x: x[1],
                reverse=True
            )
            
            # Return top candidates above threshold
            candidates = [
                f for f, count in sorted_files[:self.prefetch_count]
                if count >= self.threshold
            ]
            
            return candidates


# ============================================================================
# CONVENIENCE FUNCTIONS
# ============================================================================

def create_scatter_cache(
    vault_path: Path,
    config: Optional[CacheConfig] = None
) -> ScatterParameterCache:
    """Factory function to create a scatter parameter cache."""
    return ScatterParameterCache(vault_path, config)
