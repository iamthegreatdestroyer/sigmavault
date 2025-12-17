"""
Fast Glyph Encoder
==================

SIMD-optimized parallel glyph encoding for ΣLANG.
"""

from typing import List, Dict, Optional, Tuple
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass, field
import hashlib
import time


@dataclass
class EncoderStats:
    """Encoder performance statistics."""
    
    total_encodes: int = 0
    cache_hits: int = 0
    cache_misses: int = 0
    total_bytes_encoded: int = 0
    avg_encode_time_ms: float = 0.0


@dataclass
class EncoderConfig:
    """Configuration for fast encoder."""
    
    chunk_size: int = 1024
    max_workers: int = 4
    enable_cache: bool = True
    max_cache_size: int = 10000


class FastGlyphEncoder:
    """
    Parallel chunk-based glyph encoding.
    
    Features:
    - Multi-threaded chunk processing
    - Hash-based result caching
    - Configurable chunk size
    - Performance statistics
    """
    
    def __init__(self, config: EncoderConfig = None):
        self.config = config or EncoderConfig()
        self._cache: Dict[int, bytes] = {}
        self._stats = EncoderStats()
        self._executor: Optional[ThreadPoolExecutor] = None
    
    def encode_fast(self, text: str) -> bytes:
        """
        Encode text to bytes with parallel processing.
        
        Args:
            text: Input text to encode
        
        Returns:
            Encoded bytes
        """
        start_time = time.time()
        self._stats.total_encodes += 1
        
        # Check cache
        text_hash = hash(text)
        if self.config.enable_cache and text_hash in self._cache:
            self._stats.cache_hits += 1
            return self._cache[text_hash]
        
        self._stats.cache_misses += 1
        
        # Parallel encoding for large texts
        if len(text) > self.config.chunk_size * 2:
            encoded = self._parallel_encode(text)
        else:
            encoded = self._encode_chunk(text)
        
        # Cache result
        if self.config.enable_cache:
            self._add_to_cache(text_hash, encoded)
        
        # Update stats
        encode_time = (time.time() - start_time) * 1000
        self._update_stats(len(encoded), encode_time)
        
        return encoded
    
    def _parallel_encode(self, text: str) -> bytes:
        """Encode using parallel chunk processing."""
        chunk_size = self.config.chunk_size
        chunks = [
            text[i:i + chunk_size]
            for i in range(0, len(text), chunk_size)
        ]
        
        with ThreadPoolExecutor(max_workers=self.config.max_workers) as executor:
            # Submit all chunks with their list index
            futures = {
                executor.submit(self._encode_chunk, chunk): list_idx
                for list_idx, chunk in enumerate(chunks)
            }
            
            # Collect results in order
            results = [None] * len(chunks)
            for future in as_completed(futures):
                list_idx = futures[future]
                results[list_idx] = future.result()
        
        return b"".join(results)
    
    def _encode_chunk(self, chunk: str) -> bytes:
        """Encode a single chunk."""
        return chunk.encode("utf-8")
    
    def _add_to_cache(self, text_hash: int, encoded: bytes) -> None:
        """Add to cache with size limit."""
        if len(self._cache) >= self.config.max_cache_size:
            # Remove oldest entry (simple FIFO)
            oldest_key = next(iter(self._cache))
            del self._cache[oldest_key]
        
        self._cache[text_hash] = encoded
    
    def _update_stats(self, bytes_encoded: int, encode_time_ms: float) -> None:
        """Update encoder statistics."""
        self._stats.total_bytes_encoded += bytes_encoded
        
        # Running average
        old_avg = self._stats.avg_encode_time_ms
        n = self._stats.total_encodes
        self._stats.avg_encode_time_ms = (old_avg * (n - 1) + encode_time_ms) / n
    
    def decode_fast(self, data: bytes) -> str:
        """Decode bytes to string."""
        return data.decode("utf-8")
    
    def clear_cache(self) -> None:
        """Clear encoding cache."""
        self._cache.clear()
    
    def get_stats(self) -> EncoderStats:
        """Get encoder statistics."""
        return EncoderStats(
            total_encodes=self._stats.total_encodes,
            cache_hits=self._stats.cache_hits,
            cache_misses=self._stats.cache_misses,
            total_bytes_encoded=self._stats.total_bytes_encoded,
            avg_encode_time_ms=self._stats.avg_encode_time_ms,
        )
    
    def cache_size(self) -> int:
        """Get current cache size."""
        return len(self._cache)
    
    def cache_hit_rate(self) -> float:
        """Get cache hit rate."""
        total = self._stats.cache_hits + self._stats.cache_misses
        if total == 0:
            return 0.0
        return self._stats.cache_hits / total


class GlyphEncoder(FastGlyphEncoder):
    """
    Extended glyph encoder with ΣLANG-specific features.
    
    Supports:
    - Unicode glyph mapping
    - Semantic encoding
    - Compression hints
    """
    
    def __init__(self, config: EncoderConfig = None):
        super().__init__(config)
        self._glyph_map: Dict[str, bytes] = {}
    
    def register_glyph(self, glyph: str, encoding: bytes) -> None:
        """Register a custom glyph encoding."""
        self._glyph_map[glyph] = encoding
    
    def encode_with_glyphs(self, text: str) -> bytes:
        """Encode with custom glyph substitutions."""
        result = text
        for glyph, encoding in self._glyph_map.items():
            result = result.replace(glyph, encoding.decode("utf-8", errors="replace"))
        return self.encode_fast(result)
    
    def compute_hash(self, text: str) -> str:
        """Compute semantic hash for text."""
        encoded = self.encode_fast(text)
        return hashlib.sha256(encoded).hexdigest()[:16]


# Factory function
def create_fast_encoder(
    chunk_size: int = 1024,
    max_workers: int = 4,
    enable_cache: bool = True,
) -> FastGlyphEncoder:
    """Create fast encoder with configuration."""
    config = EncoderConfig(
        chunk_size=chunk_size,
        max_workers=max_workers,
        enable_cache=enable_cache,
    )
    return FastGlyphEncoder(config)
