"""
RSU Storage Implementation
==========================

Stores RSUs using ΣVAULT's 8-dimensional encrypted storage.
"""

from dataclasses import dataclass, field
from typing import Optional, Tuple, List, Any
from datetime import datetime
import hashlib
import uuid

from .manifest import RSUManifest, RSUEntry, RSUStatus


@dataclass
class RSUStorageConfig:
    """Configuration for RSU storage."""
    
    # Encryption
    encryption_level: str = "standard"
    
    # 8D manifold settings
    manifold_dimensions: int = 8
    scatter_entropy: float = 0.7
    
    # Storage limits
    max_rsu_size_bytes: int = 100 * 1024 * 1024  # 100MB
    max_kv_cache_size_bytes: int = 500 * 1024 * 1024  # 500MB
    
    # Retention
    max_rsu_age_days: int = 90
    auto_archive_days: int = 30
    
    # Performance
    chunk_size_bytes: int = 64 * 1024  # 64KB chunks
    parallel_writes: int = 4


@dataclass
class StoredRSU:
    """Complete stored RSU with data."""
    
    entry: RSUEntry
    glyph_data: bytes
    kv_cache_data: Optional[bytes] = None


class MockVault:
    """Mock vault for testing without external dependencies."""
    
    def __init__(self):
        self._chunks: dict = {}
    
    def store_chunk(self, chunk_id: str, data: bytes, coordinates: Tuple) -> None:
        """Store chunk."""
        self._chunks[chunk_id] = data
    
    def retrieve_chunk(self, chunk_id: str, coordinates: Tuple) -> Optional[bytes]:
        """Retrieve chunk."""
        return self._chunks.get(chunk_id)
    
    def delete_chunk(self, chunk_id: str, coordinates: Tuple) -> bool:
        """Delete chunk."""
        if chunk_id in self._chunks:
            del self._chunks[chunk_id]
            return True
        return False


class RSUStorage:
    """
    RSU storage using ΣVAULT.
    
    Stores compressed contexts and KV cache states
    in an 8-dimensional encrypted manifold.
    """
    
    def __init__(
        self,
        vault: Optional[Any] = None,
        config: Optional[RSUStorageConfig] = None,
    ):
        self.config = config or RSUStorageConfig()
        self._vault = vault or MockVault()
        self._manifest = RSUManifest()
    
    def store(
        self,
        glyph_data: bytes,
        semantic_hash: int,
        original_token_count: int,
        kv_cache_data: Optional[bytes] = None,
        conversation_id: Optional[str] = None,
        parent_rsu_id: Optional[str] = None,
    ) -> RSUEntry:
        """
        Store RSU in vault.
        
        Args:
            glyph_data: Compressed glyph sequence
            semantic_hash: Semantic hash for retrieval
            original_token_count: Original uncompressed token count
            kv_cache_data: Optional KV cache state
            conversation_id: Optional conversation ID
            parent_rsu_id: Optional parent RSU for chaining
        
        Returns:
            RSUEntry with storage metadata
        """
        # Generate RSU ID
        rsu_id = self._generate_rsu_id(semantic_hash)
        
        # Compute 8D coordinates
        coordinates = self._compute_coordinates(semantic_hash, glyph_data)
        
        # Chunk and store data
        chunk_ids = self._store_chunks(glyph_data, coordinates)
        
        # Store KV cache if provided
        kv_cache_size = 0
        kv_cache_layers = 0
        if kv_cache_data:
            kv_chunk_ids = self._store_chunks(kv_cache_data, coordinates, prefix="kv_")
            chunk_ids.extend(kv_chunk_ids)
            kv_cache_size = len(kv_cache_data)
            kv_cache_layers = self._infer_kv_layers(kv_cache_data)
        
        # Create entry
        entry = RSUEntry(
            rsu_id=rsu_id,
            semantic_hash=semantic_hash,
            original_token_count=original_token_count,
            compressed_glyph_count=len(glyph_data) // 2 if glyph_data else 0,
            compression_ratio=original_token_count / (len(glyph_data) // 2) if glyph_data and len(glyph_data) > 0 else 1.0,
            vault_coordinates=coordinates,
            chunk_ids=chunk_ids,
            has_kv_cache=kv_cache_data is not None,
            kv_cache_layers=kv_cache_layers,
            kv_cache_size_bytes=kv_cache_size,
            conversation_id=conversation_id,
            parent_rsu_id=parent_rsu_id,
        )
        
        # Add to manifest
        self._manifest.add_entry(entry)
        
        # Update parent if exists
        if parent_rsu_id:
            parent = self._manifest.get_entry(parent_rsu_id)
            if parent:
                parent.child_rsu_ids.append(rsu_id)
        
        return entry
    
    def retrieve(self, rsu_id: str) -> Optional[StoredRSU]:
        """
        Retrieve RSU from vault.
        
        Args:
            rsu_id: RSU ID to retrieve
        
        Returns:
            StoredRSU with data, or None if not found
        """
        entry = self._manifest.get_entry(rsu_id)
        if entry is None:
            return None
        
        if entry.status != RSUStatus.ACTIVE:
            return None
        
        # Retrieve chunks
        glyph_chunks = []
        kv_chunks = []
        
        for chunk_id in entry.chunk_ids:
            data = self._retrieve_chunk(chunk_id, entry.vault_coordinates)
            if data:
                if chunk_id.startswith("kv_"):
                    kv_chunks.append(data)
                else:
                    glyph_chunks.append(data)
        
        # Reassemble data
        glyph_data = b"".join(glyph_chunks)
        kv_cache_data = b"".join(kv_chunks) if kv_chunks else None
        
        # Mark accessed
        self._manifest.mark_accessed(rsu_id)
        
        return StoredRSU(
            entry=entry,
            glyph_data=glyph_data,
            kv_cache_data=kv_cache_data,
        )
    
    def find_similar(
        self,
        semantic_hash: int,
        threshold: float = 0.85,
        max_results: int = 10,
    ) -> List[RSUEntry]:
        """
        Find RSUs with similar semantic hash.
        
        Args:
            semantic_hash: Hash to match
            threshold: Minimum similarity (0.0-1.0)
            max_results: Maximum results to return
        
        Returns:
            List of similar RSU entries
        """
        tolerance = 1.0 - threshold
        matches = self._manifest.find_by_semantic_hash(semantic_hash, tolerance)
        
        # Sort by similarity and limit
        matches.sort(
            key=lambda e: -self._compute_similarity(semantic_hash, e.semantic_hash)
        )
        
        return matches[:max_results]
    
    def get_conversation_chain(self, conversation_id: str) -> List[RSUEntry]:
        """
        Get all RSUs in a conversation chain.
        
        Args:
            conversation_id: Conversation ID
        
        Returns:
            List of RSU entries in chronological order
        """
        entries = self._manifest.find_by_conversation(conversation_id)
        entries.sort(key=lambda e: e.created_at)
        return entries
    
    def archive(self, rsu_id: str) -> bool:
        """Archive an RSU (keeps data but marks inactive)."""
        entry = self._manifest.get_entry(rsu_id)
        if entry:
            entry.status = RSUStatus.ARCHIVED
            return True
        return False
    
    def delete(self, rsu_id: str) -> bool:
        """Permanently delete an RSU."""
        entry = self._manifest.get_entry(rsu_id)
        if entry is None:
            return False
        
        # Delete chunks from vault
        for chunk_id in entry.chunk_ids:
            self._delete_chunk(chunk_id, entry.vault_coordinates)
        
        # Remove from manifest
        del self._manifest.entries[rsu_id]
        
        return True
    
    def get_statistics(self) -> dict:
        """Get storage statistics."""
        manifest_stats = self._manifest.get_statistics()
        
        return {
            **manifest_stats,
            "config": {
                "encryption_level": self.config.encryption_level,
                "manifold_dimensions": self.config.manifold_dimensions,
                "scatter_entropy": self.config.scatter_entropy,
            },
        }
    
    def _compute_coordinates(
        self,
        semantic_hash: int,
        data: bytes,
    ) -> Tuple[float, ...]:
        """Compute 8D coordinates for data placement."""
        coords = []
        
        # Extract bits from semantic hash for first 4 dimensions
        for i in range(4):
            bits = (semantic_hash >> (i * 16)) & 0xFFFF
            coords.append(bits / 65535.0)
        
        # Compute remaining 4 dimensions from data
        data_hash = hashlib.sha256(data).digest()
        
        for i in range(4):
            byte_val = data_hash[i * 8] if i * 8 < len(data_hash) else 0
            coords.append(byte_val / 255.0)
        
        return tuple(coords)
    
    def _generate_rsu_id(self, semantic_hash: int) -> str:
        """Generate unique RSU ID."""
        timestamp = datetime.utcnow().strftime("%Y%m%d%H%M%S")
        unique = uuid.uuid4().hex[:8]
        hash_prefix = format(semantic_hash & 0xFFFF, '04x')
        
        return f"rsu_{timestamp}_{hash_prefix}_{unique}"
    
    def _store_chunks(
        self,
        data: bytes,
        coordinates: Tuple[float, ...],
        prefix: str = "",
    ) -> List[str]:
        """Store data in chunks."""
        chunk_ids = []
        chunk_size = self.config.chunk_size_bytes
        
        for i in range(0, len(data), chunk_size):
            chunk = data[i:i + chunk_size]
            chunk_id = f"{prefix}chunk_{i // chunk_size}_{uuid.uuid4().hex[:8]}"
            
            # Store via vault
            self._vault.store_chunk(chunk_id, chunk, coordinates)
            chunk_ids.append(chunk_id)
        
        return chunk_ids
    
    def _retrieve_chunk(
        self,
        chunk_id: str,
        coordinates: Tuple[float, ...],
    ) -> Optional[bytes]:
        """Retrieve a single chunk."""
        return self._vault.retrieve_chunk(chunk_id, coordinates)
    
    def _delete_chunk(
        self,
        chunk_id: str,
        coordinates: Tuple[float, ...],
    ) -> bool:
        """Delete a single chunk."""
        return self._vault.delete_chunk(chunk_id, coordinates)
    
    def _compute_similarity(self, hash1: int, hash2: int) -> float:
        """Compute similarity between two semantic hashes."""
        xor = hash1 ^ hash2
        distance = bin(xor).count('1')
        return 1.0 - (distance / 64.0)  # Assuming 64-bit hashes
    
    def _infer_kv_layers(self, kv_data: bytes) -> int:
        """Infer number of KV cache layers from data size."""
        # Rough estimate based on typical layer sizes
        layer_size = 32 * 128 * 4096 * 4  # heads * head_dim * seq_len * fp32
        return max(1, len(kv_data) // layer_size)
