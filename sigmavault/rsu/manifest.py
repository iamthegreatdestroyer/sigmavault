"""
RSU Manifest and Entry Types
============================

Manages metadata for stored RSUs.
"""

from dataclasses import dataclass, field
from typing import Optional, List, Dict, Any
from datetime import datetime
from enum import Enum
import json


class RSUStatus(Enum):
    """RSU lifecycle status."""
    ACTIVE = "active"
    ARCHIVED = "archived"
    EXPIRED = "expired"
    CORRUPTED = "corrupted"


@dataclass
class RSUEntry:
    """
    Single RSU entry in the manifest.
    
    Tracks metadata for one reusable semantic unit.
    """
    
    # Identity
    rsu_id: str
    semantic_hash: int
    
    # Content info
    original_token_count: int
    compressed_glyph_count: int
    compression_ratio: float
    
    # Storage location (8D coordinates)
    vault_coordinates: tuple  # 8-dimensional location
    chunk_ids: List[str] = field(default_factory=list)
    
    # KV cache info
    has_kv_cache: bool = False
    kv_cache_layers: int = 0
    kv_cache_size_bytes: int = 0
    
    # Metadata
    created_at: datetime = field(default_factory=datetime.utcnow)
    last_accessed: datetime = field(default_factory=datetime.utcnow)
    access_count: int = 0
    status: RSUStatus = RSUStatus.ACTIVE
    
    # Relationships
    parent_rsu_id: Optional[str] = None
    child_rsu_ids: List[str] = field(default_factory=list)
    conversation_id: Optional[str] = None
    
    # Similarity tracking
    similar_rsu_ids: List[str] = field(default_factory=list)
    similarity_scores: Dict[str, float] = field(default_factory=dict)
    
    def to_dict(self) -> Dict[str, Any]:
        """Serialize to dictionary."""
        return {
            "rsu_id": self.rsu_id,
            "semantic_hash": self.semantic_hash,
            "original_token_count": self.original_token_count,
            "compressed_glyph_count": self.compressed_glyph_count,
            "compression_ratio": self.compression_ratio,
            "vault_coordinates": list(self.vault_coordinates),
            "chunk_ids": self.chunk_ids,
            "has_kv_cache": self.has_kv_cache,
            "kv_cache_layers": self.kv_cache_layers,
            "kv_cache_size_bytes": self.kv_cache_size_bytes,
            "created_at": self.created_at.isoformat(),
            "last_accessed": self.last_accessed.isoformat(),
            "access_count": self.access_count,
            "status": self.status.value,
            "parent_rsu_id": self.parent_rsu_id,
            "child_rsu_ids": self.child_rsu_ids,
            "conversation_id": self.conversation_id,
            "similar_rsu_ids": self.similar_rsu_ids,
            "similarity_scores": self.similarity_scores,
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'RSUEntry':
        """Deserialize from dictionary."""
        return cls(
            rsu_id=data["rsu_id"],
            semantic_hash=data["semantic_hash"],
            original_token_count=data["original_token_count"],
            compressed_glyph_count=data["compressed_glyph_count"],
            compression_ratio=data["compression_ratio"],
            vault_coordinates=tuple(data["vault_coordinates"]),
            chunk_ids=data.get("chunk_ids", []),
            has_kv_cache=data.get("has_kv_cache", False),
            kv_cache_layers=data.get("kv_cache_layers", 0),
            kv_cache_size_bytes=data.get("kv_cache_size_bytes", 0),
            created_at=datetime.fromisoformat(data["created_at"]),
            last_accessed=datetime.fromisoformat(data["last_accessed"]),
            access_count=data.get("access_count", 0),
            status=RSUStatus(data.get("status", "active")),
            parent_rsu_id=data.get("parent_rsu_id"),
            child_rsu_ids=data.get("child_rsu_ids", []),
            conversation_id=data.get("conversation_id"),
            similar_rsu_ids=data.get("similar_rsu_ids", []),
            similarity_scores=data.get("similarity_scores", {}),
        )


@dataclass
class RSUManifest:
    """
    Manifest tracking all RSUs in the vault.
    
    Provides indexing and lookup capabilities.
    """
    
    entries: Dict[str, RSUEntry] = field(default_factory=dict)
    semantic_index: Dict[int, List[str]] = field(default_factory=dict)
    conversation_index: Dict[str, List[str]] = field(default_factory=dict)
    
    # Statistics
    total_original_tokens: int = 0
    total_compressed_glyphs: int = 0
    total_kv_cache_bytes: int = 0
    
    def add_entry(self, entry: RSUEntry) -> None:
        """Add RSU entry to manifest."""
        self.entries[entry.rsu_id] = entry
        
        # Update semantic index
        hash_key = entry.semantic_hash
        if hash_key not in self.semantic_index:
            self.semantic_index[hash_key] = []
        self.semantic_index[hash_key].append(entry.rsu_id)
        
        # Update conversation index
        if entry.conversation_id:
            if entry.conversation_id not in self.conversation_index:
                self.conversation_index[entry.conversation_id] = []
            self.conversation_index[entry.conversation_id].append(entry.rsu_id)
        
        # Update statistics
        self.total_original_tokens += entry.original_token_count
        self.total_compressed_glyphs += entry.compressed_glyph_count
        self.total_kv_cache_bytes += entry.kv_cache_size_bytes
    
    def get_entry(self, rsu_id: str) -> Optional[RSUEntry]:
        """Get RSU entry by ID."""
        return self.entries.get(rsu_id)
    
    def find_by_semantic_hash(
        self,
        semantic_hash: int,
        tolerance: float = 0.0,
    ) -> List[RSUEntry]:
        """
        Find RSUs by semantic hash.
        
        Args:
            semantic_hash: Hash to search for
            tolerance: Hamming distance tolerance (0.0 = exact match)
        
        Returns:
            List of matching entries
        """
        if tolerance == 0.0:
            # Exact match
            rsu_ids = self.semantic_index.get(semantic_hash, [])
            return [self.entries[rid] for rid in rsu_ids if rid in self.entries]
        
        # Fuzzy match using Hamming distance
        matches = []
        for hash_key, rsu_ids in self.semantic_index.items():
            distance = bin(semantic_hash ^ hash_key).count('1')
            max_bits = 64  # Assuming 64-bit hash
            similarity = 1.0 - (distance / max_bits)
            
            if similarity >= (1.0 - tolerance):
                for rid in rsu_ids:
                    if rid in self.entries:
                        matches.append(self.entries[rid])
        
        return matches
    
    def find_by_conversation(self, conversation_id: str) -> List[RSUEntry]:
        """Find all RSUs for a conversation."""
        rsu_ids = self.conversation_index.get(conversation_id, [])
        return [self.entries[rid] for rid in rsu_ids if rid in self.entries]
    
    def mark_accessed(self, rsu_id: str) -> None:
        """Mark RSU as accessed."""
        if rsu_id in self.entries:
            entry = self.entries[rsu_id]
            entry.last_accessed = datetime.utcnow()
            entry.access_count += 1
    
    def get_statistics(self) -> Dict[str, Any]:
        """Get manifest statistics."""
        active_count = sum(
            1 for e in self.entries.values()
            if e.status == RSUStatus.ACTIVE
        )
        
        avg_ratio = (
            self.total_original_tokens / self.total_compressed_glyphs
            if self.total_compressed_glyphs > 0 else 1.0
        )
        
        return {
            "total_rsus": len(self.entries),
            "active_rsus": active_count,
            "total_original_tokens": self.total_original_tokens,
            "total_compressed_glyphs": self.total_compressed_glyphs,
            "average_compression_ratio": avg_ratio,
            "total_kv_cache_bytes": self.total_kv_cache_bytes,
            "unique_conversations": len(self.conversation_index),
        }
    
    def to_json(self) -> str:
        """Serialize manifest to JSON."""
        return json.dumps({
            "entries": {k: v.to_dict() for k, v in self.entries.items()},
            "statistics": self.get_statistics(),
        }, indent=2)
    
    @classmethod
    def from_json(cls, json_str: str) -> 'RSUManifest':
        """Deserialize manifest from JSON."""
        data = json.loads(json_str)
        manifest = cls()
        
        for rsu_id, entry_data in data.get("entries", {}).items():
            entry = RSUEntry.from_dict(entry_data)
            manifest.add_entry(entry)
        
        return manifest
