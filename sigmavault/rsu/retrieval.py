"""
RSU Retrieval System
====================

Efficient retrieval of RSUs by semantic similarity.
"""

from typing import Optional, List
from dataclasses import dataclass

from .storage import RSUStorage, StoredRSU
from .manifest import RSUEntry


@dataclass
class RetrievalResult:
    """Result of RSU retrieval."""
    
    entry: RSUEntry
    similarity: float
    glyph_data: Optional[bytes] = None
    kv_cache_data: Optional[bytes] = None


class RSURetriever:
    """
    Retrieves RSUs optimized for inference reuse.
    
    Features:
    - Semantic similarity matching
    - KV cache warm-start
    - Conversation chain loading
    """
    
    def __init__(self, storage: RSUStorage):
        self._storage = storage
    
    def retrieve_best_match(
        self,
        semantic_hash: int,
        min_similarity: float = 0.85,
        require_kv_cache: bool = False,
    ) -> Optional[RetrievalResult]:
        """
        Retrieve best matching RSU.
        
        Args:
            semantic_hash: Target semantic hash
            min_similarity: Minimum similarity threshold
            require_kv_cache: Only return RSUs with KV cache
        
        Returns:
            Best matching RSU, or None
        """
        matches = self._storage.find_similar(
            semantic_hash,
            threshold=min_similarity,
            max_results=10
        )
        
        if require_kv_cache:
            matches = [m for m in matches if m.has_kv_cache]
        
        if not matches:
            return None
        
        # Get best match
        best = matches[0]
        similarity = self._compute_similarity(semantic_hash, best.semantic_hash)
        
        # Load full data
        stored = self._storage.retrieve(best.rsu_id)
        if stored is None:
            return None
        
        return RetrievalResult(
            entry=stored.entry,
            similarity=similarity,
            glyph_data=stored.glyph_data,
            kv_cache_data=stored.kv_cache_data,
        )
    
    def retrieve_conversation(
        self,
        conversation_id: str,
        load_data: bool = False,
    ) -> List[RetrievalResult]:
        """
        Retrieve all RSUs for a conversation.
        
        Args:
            conversation_id: Conversation ID
            load_data: Whether to load full data
        
        Returns:
            List of RSUs in chronological order
        """
        entries = self._storage.get_conversation_chain(conversation_id)
        
        results = []
        for entry in entries:
            if load_data:
                stored = self._storage.retrieve(entry.rsu_id)
                if stored:
                    results.append(RetrievalResult(
                        entry=stored.entry,
                        similarity=1.0,
                        glyph_data=stored.glyph_data,
                        kv_cache_data=stored.kv_cache_data,
                    ))
            else:
                results.append(RetrievalResult(
                    entry=entry,
                    similarity=1.0,
                ))
        
        return results
    
    def retrieve_chain(
        self,
        rsu_id: str,
        depth: int = 10,
    ) -> List[RetrievalResult]:
        """
        Retrieve RSU chain following parent links.
        
        Args:
            rsu_id: Starting RSU ID
            depth: Maximum chain depth
        
        Returns:
            List from oldest ancestor to specified RSU
        """
        chain = []
        current_id = rsu_id
        
        for _ in range(depth):
            stored = self._storage.retrieve(current_id)
            if stored is None:
                break
            
            chain.append(RetrievalResult(
                entry=stored.entry,
                similarity=1.0,
                glyph_data=stored.glyph_data,
                kv_cache_data=stored.kv_cache_data,
            ))
            
            if stored.entry.parent_rsu_id is None:
                break
            
            current_id = stored.entry.parent_rsu_id
        
        # Return from oldest to newest
        chain.reverse()
        return chain
    
    def _compute_similarity(self, hash1: int, hash2: int) -> float:
        """Compute similarity between hashes."""
        xor = hash1 ^ hash2
        distance = bin(xor).count('1')
        return 1.0 - (distance / 64.0)
