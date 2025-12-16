"""
RSU Manager for Ryot LLM
========================

Implements RSUManagerProtocol using ΣVAULT storage.
Bridges Ryot's inference context management to persistent RSU storage.
"""

from typing import Optional, Tuple, List
from dataclasses import dataclass
import hashlib
import pickle

from ..api.interfaces import RSUManagerProtocol
from ..api.types import (
    TokenSequence, KVCacheState, RSUReference,
    SigmaEncodedContext,
)
from ..api.exceptions import RSUError


@dataclass
class RSUManagerConfig:
    """Configuration for RSU manager."""
    
    enabled: bool = True
    similarity_threshold: float = 0.85
    max_chain_depth: int = 10
    auto_store: bool = True
    store_kv_cache: bool = True
    max_stored_rsus: int = 10000


class RyotRSUManager:
    """
    RSU Manager implementation for Ryot LLM.
    
    Bridges Ryot's RSUManagerProtocol to ΣVAULT storage.
    Features:
    - Store token sequences with optional KV cache
    - Retrieve by semantic similarity
    - Support conversation chaining
    - Warm-start from cached state
    """
    
    def __init__(
        self,
        config: Optional[RSUManagerConfig] = None,
    ):
        self.config = config or RSUManagerConfig()
        
        # Initialize ΣVAULT storage
        self._storage = None
        self._retriever = None
        
        if self.config.enabled:
            self._init_storage()
        
        # Active conversation tracking
        self._active_conversations: dict = {}
        self._rsu_count = 0
    
    def _init_storage(self) -> None:
        """Initialize ΣVAULT RSU storage."""
        try:
            from sigmavault.rsu import RSUStorage, RSURetriever, RSUStorageConfig
            
            storage_config = RSUStorageConfig(
                max_rsu_age_days=90,
                auto_archive_days=30,
                chunk_size_bytes=64 * 1024,
                parallel_writes=4,
            )
            
            self._storage = RSUStorage(config=storage_config)
            self._retriever = RSURetriever(self._storage)
        except ImportError as e:
            # ΣVAULT not available
            self.config.enabled = False
            raise RSUError(f"ΣVAULT import failed: {e}", "init")
    
    def store(
        self,
        tokens: TokenSequence,
        kv_state: Optional[KVCacheState] = None,
        conversation_id: Optional[str] = None,
    ) -> RSUReference:
        """
        Store tokens and KV state as RSU.
        
        Implements RSUManagerProtocol.store()
        
        Args:
            tokens: Token sequence to store
            kv_state: Optional KV cache state
            conversation_id: Optional conversation ID for chaining
        
        Returns:
            RSUReference with storage metadata
        
        Raises:
            RSUError: If storage is not available
        """
        if not self.config.enabled or self._storage is None:
            raise RSUError("RSU storage not available", "store")
        
        # Get semantic hash from tokens
        if tokens.sigma_encoded and hasattr(tokens, 'semantic_hash'):
            semantic_hash = tokens.semantic_hash
        else:
            semantic_hash = self._compute_hash(tokens)
        
        # Serialize glyph data
        glyph_data = self._serialize_tokens(tokens)
        
        # Serialize KV cache if enabled
        kv_data = None
        if self.config.store_kv_cache and kv_state is not None:
            kv_data = self._serialize_kv_state(kv_state)
        
        # Get parent RSU for chaining
        parent_id = None
        if conversation_id and conversation_id in self._active_conversations:
            parent_id = self._active_conversations[conversation_id]
        
        # Store in ΣVAULT
        entry = self._storage.store(
            glyph_data=glyph_data,
            semantic_hash=semantic_hash,
            original_token_count=len(tokens.tokens) if hasattr(tokens, 'tokens') else len(tokens),
            kv_cache_data=kv_data,
            conversation_id=conversation_id,
            parent_rsu_id=parent_id,
        )
        
        # Update conversation tracking
        if conversation_id:
            self._active_conversations[conversation_id] = entry.rsu_id
        
        self._rsu_count += 1
        
        return RSUReference(
            rsu_id=entry.rsu_id,
            semantic_hash=entry.semantic_hash,
            token_count=entry.original_token_count,
            has_kv_state=entry.has_kv_cache,
        )
    
    def retrieve(
        self,
        reference: RSUReference,
    ) -> Optional[Tuple[TokenSequence, Optional[KVCacheState]]]:
        """
        Retrieve RSU by reference.
        
        Implements RSUManagerProtocol.retrieve()
        
        Args:
            reference: RSU reference to retrieve
        
        Returns:
            Tuple of (tokens, kv_state) or None if not found
        """
        if not self.config.enabled or self._storage is None:
            return None
        
        stored = self._storage.retrieve(reference.rsu_id)
        if stored is None:
            return None
        
        # Deserialize tokens
        tokens = self._deserialize_tokens(stored.glyph_data)
        
        # Deserialize KV state if present
        kv_state = None
        if stored.kv_cache_data:
            kv_state = self._deserialize_kv_state(stored.kv_cache_data)
        
        return tokens, kv_state
    
    def find_matching_rsu(
        self,
        semantic_hash: int,
        similarity_threshold: Optional[float] = None,
    ) -> Optional[RSUReference]:
        """
        Find RSU by semantic similarity.
        
        Implements RSUManagerProtocol.find_matching_rsu()
        
        Args:
            semantic_hash: Hash to match
            similarity_threshold: Minimum similarity (0.0-1.0)
        
        Returns:
            Best matching RSUReference or None
        """
        if not self.config.enabled or self._retriever is None:
            return None
        
        threshold = similarity_threshold or self.config.similarity_threshold
        
        result = self._retriever.retrieve_best_match(
            semantic_hash,
            min_similarity=threshold,
            require_kv_cache=self.config.store_kv_cache,
        )
        
        if result is None:
            return None
        
        return RSUReference(
            rsu_id=result.entry.rsu_id,
            semantic_hash=result.entry.semantic_hash,
            token_count=result.entry.original_token_count,
            has_kv_state=result.entry.has_kv_cache,
            similarity=result.similarity,
        )
    
    def get_conversation_rsus(
        self,
        conversation_id: str,
    ) -> List[RSUReference]:
        """
        Get all RSUs for a conversation.
        
        Args:
            conversation_id: Conversation ID
        
        Returns:
            List of RSU references in chronological order
        """
        if not self.config.enabled or self._storage is None:
            return []
        
        entries = self._storage.get_conversation_chain(conversation_id)
        
        return [
            RSUReference(
                rsu_id=e.rsu_id,
                semantic_hash=e.semantic_hash,
                token_count=e.original_token_count,
                has_kv_state=e.has_kv_cache,
            )
            for e in entries
        ]
    
    def warm_start_from_rsu(
        self,
        reference: RSUReference,
        cache: 'KVCache',
    ) -> int:
        """
        Warm-start KV cache from RSU.
        
        Args:
            reference: RSU reference
            cache: KV cache to warm
        
        Returns:
            Number of tokens loaded (position in cache)
        """
        if not self.config.enabled or self._storage is None:
            return 0
        
        result = self.retrieve(reference)
        if result is None:
            return 0
        
        tokens, kv_state = result
        
        if kv_state is None:
            return 0
        
        # Load KV state into cache
        if hasattr(cache, 'load_state'):
            cache.load_state(kv_state)
        
        token_count = len(tokens.tokens) if hasattr(tokens, 'tokens') else len(tokens)
        return token_count
    
    def is_available(self) -> bool:
        """Check if RSU storage is available."""
        return self.config.enabled and self._storage is not None
    
    def get_statistics(self) -> dict:
        """Get RSU manager statistics."""
        stats = {
            "enabled": self.config.enabled,
            "available": self.is_available(),
            "active_conversations": len(self._active_conversations),
            "total_rsus_stored": self._rsu_count,
        }
        
        if self._storage:
            stats["storage"] = self._storage.get_statistics()
        
        return stats
    
    def _compute_hash(self, tokens: TokenSequence) -> int:
        """Compute semantic hash for tokens."""
        import hashlib
        
        # Extract bytes from tokens
        if hasattr(tokens, 'tokens'):
            token_bytes = bytes(t % 256 for t in tokens.tokens[:128])
        else:
            token_bytes = bytes(tokens[:128]) if isinstance(tokens, (list, tuple)) else str(tokens).encode()
        
        hash_bytes = hashlib.sha256(token_bytes).digest()
        
        return int.from_bytes(hash_bytes[:8], 'little')
    
    def _serialize_tokens(self, tokens: TokenSequence) -> bytes:
        """Serialize tokens to bytes."""
        import struct
        
        result = bytearray()
        
        if hasattr(tokens, 'tokens'):
            token_seq = tokens.tokens
        elif isinstance(tokens, (list, tuple)):
            token_seq = tokens
        else:
            token_seq = [tokens]
        
        for token in token_seq:
            result.extend(struct.pack('<I', int(token) & 0xFFFFFFFF))
        
        return bytes(result)
    
    def _deserialize_tokens(self, data: bytes) -> TokenSequence:
        """Deserialize tokens from bytes."""
        import struct
        
        tokens = []
        for i in range(0, len(data), 4):
            if i + 4 <= len(data):
                token = struct.unpack('<I', data[i:i+4])[0]
                tokens.append(token)
        
        return TokenSequence(tokens=tuple(tokens))
    
    def _serialize_kv_state(self, state: KVCacheState) -> bytes:
        """Serialize KV cache state."""
        return pickle.dumps(state)
    
    def _deserialize_kv_state(self, data: bytes) -> KVCacheState:
        """Deserialize KV cache state."""
        return pickle.loads(data)
