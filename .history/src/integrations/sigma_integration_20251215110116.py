"""
ΣLANG Integration with RSU Support
===================================

Enhanced ΣLANG compression engine with RSU storage integration.
Automatically stores compressed contexts for warm-start retrieval.
"""

from typing import Optional, Tuple
from dataclasses import dataclass

from .rsu_manager import RyotRSUManager, RSUManagerConfig
from ..api.interfaces import RSUManagerProtocol
from ..api.types import (
    TokenSequence, SigmaEncodedContext, CompressionResult,
)


@dataclass
class SigmaConfig:
    """Configuration for ΣLANG integration."""
    
    enable_rsu: bool = True
    rsu_similarity_threshold: float = 0.85
    max_rsu_chain_depth: int = 10
    auto_store_rsu: bool = True
    compression_level: int = 3


@dataclass
class CompressionResult:
    """Result of context compression."""
    
    compressed_size: int
    original_size: int
    compression_ratio: float
    semantic_hash: int
    rsu_reference: Optional[str] = None


class SigmaIntegration:
    """
    ΣLANG Integration for Ryot LLM.
    
    Features:
    - Context compression to glyphs
    - Automatic RSU storage
    - KV cache warm-start
    - Conversation continuity
    """
    
    def __init__(
        self,
        compression_engine: Optional[object] = None,
        rsu_manager: Optional[RSUManagerProtocol] = None,
        config: Optional[SigmaConfig] = None,
    ):
        self.config = config or SigmaConfig()
        self._compression_engine = compression_engine
        
        # Initialize RSU manager
        if rsu_manager is None and self.config.enable_rsu:
            rsu_config = RSUManagerConfig(
                enabled=True,
                similarity_threshold=self.config.rsu_similarity_threshold,
                max_chain_depth=self.config.max_rsu_chain_depth,
                auto_store=self.config.auto_store_rsu,
            )
            try:
                rsu_manager = RyotRSUManager(config=rsu_config)
            except Exception as e:
                print(f"Warning: RSU manager initialization failed: {e}")
                rsu_manager = None
        
        self._rsu_manager = rsu_manager
    
    def compress_context(
        self,
        tokens: TokenSequence,
        conversation_id: Optional[str] = None,
        auto_store_rsu: bool = True,
    ) -> Tuple[SigmaEncodedContext, CompressionResult]:
        """
        Compress context with optional RSU storage.
        
        Args:
            tokens: Token sequence to compress
            conversation_id: Optional conversation ID
            auto_store_rsu: Whether to auto-store RSU
        
        Returns:
            Tuple of (encoded_context, compression_result)
        """
        # Compute semantic hash
        semantic_hash = self._compute_semantic_hash(tokens)
        
        # Simulate compression (replace with actual compression engine)
        original_size = len(tokens.tokens) * 2 if hasattr(tokens, 'tokens') else len(tokens) * 2
        compressed_size = max(original_size // 10, 100)  # Mock 10x compression
        compression_ratio = original_size / compressed_size if compressed_size > 0 else 1.0
        
        # Create encoding
        encoded = SigmaEncodedContext(
            glyphs=b"compressed_glyphs",
            semantic_hash=semantic_hash,
            timestamp=0,
            compression_ratio=compression_ratio,
        )
        
        # Auto-store RSU if enabled
        rsu_reference = None
        if auto_store_rsu and self.config.enable_rsu and self._rsu_manager:
            try:
                ref = self._rsu_manager.store(
                    tokens,
                    kv_state=None,
                    conversation_id=conversation_id,
                )
                rsu_reference = ref.rsu_id
            except Exception as e:
                print(f"Warning: RSU storage failed: {e}")
        
        result = CompressionResult(
            compressed_size=compressed_size,
            original_size=original_size,
            compression_ratio=compression_ratio,
            semantic_hash=semantic_hash,
            rsu_reference=rsu_reference,
        )
        
        return encoded, result
    
    def warm_start_inference(
        self,
        semantic_hash: int,
        cache: Optional[object] = None,
    ) -> Tuple[Optional[TokenSequence], int]:
        """
        Warm-start inference from matching RSU.
        
        Args:
            semantic_hash: Semantic hash to match
            cache: Optional KV cache to warm
        
        Returns:
            Tuple of (tokens, cache_position) or (None, 0) if no match
        """
        if not self.config.enable_rsu or self._rsu_manager is None:
            return None, 0
        
        # Find matching RSU
        ref = self._rsu_manager.find_matching_rsu(
            semantic_hash,
            self.config.rsu_similarity_threshold
        )
        
        if ref is None:
            return None, 0
        
        # Load into cache if provided
        position = 0
        if cache is not None:
            position = self._rsu_manager.warm_start_from_rsu(ref, cache)
        
        # Retrieve tokens
        if position > 0:
            result = self._rsu_manager.retrieve(ref)
            if result:
                tokens, kv_state = result
                return tokens, position
        
        return None, 0
    
    def get_conversation_context(
        self,
        conversation_id: str,
    ) -> list:
        """
        Get full conversation context from RSU chain.
        
        Args:
            conversation_id: Conversation ID
        
        Returns:
            List of RSU references in order
        """
        if not self.config.enable_rsu or self._rsu_manager is None:
            return []
        
        return self._rsu_manager.get_conversation_rsus(conversation_id)
    
    def is_available(self) -> bool:
        """Check if ΣLANG compression is available."""
        return self._rsu_manager is not None and self._rsu_manager.is_available()
    
    def get_statistics(self) -> dict:
        """Get ΣLANG integration statistics."""
        stats = {
            "config": {
                "enable_rsu": self.config.enable_rsu,
                "rsu_similarity_threshold": self.config.rsu_similarity_threshold,
                "max_rsu_chain_depth": self.config.max_rsu_chain_depth,
                "auto_store_rsu": self.config.auto_store_rsu,
            },
            "available": self.is_available(),
        }
        
        if self._rsu_manager:
            stats["rsu_manager"] = self._rsu_manager.get_statistics()
        
        return stats
    
    def _compute_semantic_hash(self, tokens: TokenSequence) -> int:
        """Compute semantic hash for tokens."""
        import hashlib
        
        if hasattr(tokens, 'tokens'):
            token_bytes = bytes(t % 256 for t in tokens.tokens[:128])
        elif isinstance(tokens, (list, tuple)):
            token_bytes = bytes(t % 256 for t in tokens[:128])
        else:
            token_bytes = str(tokens).encode()
        
        hash_bytes = hashlib.sha256(token_bytes).digest()
        return int.from_bytes(hash_bytes[:8], 'little')
