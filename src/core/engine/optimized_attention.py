"""
Optimized Attention with Flash Attention Pattern
=================================================

O(N) memory complexity attention implementation with KV caching.
"""

import math
from dataclasses import dataclass
from typing import Optional, Tuple, List, Any


@dataclass
class AttentionConfig:
    """Configuration for optimized attention."""
    
    num_heads: int = 32
    head_dim: int = 128
    use_flash_attention: bool = True
    chunk_size: int = 1024
    dropout: float = 0.0
    causal: bool = True


class MockTensor:
    """Mock tensor for testing without PyTorch dependency."""
    
    def __init__(self, data: List = None, shape: Tuple = None):
        self.data = data or []
        self.shape = shape or (1, 1, 1)
    
    def __matmul__(self, other):
        return MockTensor(shape=(self.shape[0], self.shape[1], other.shape[-1]))
    
    def transpose(self, dim1: int, dim2: int):
        new_shape = list(self.shape)
        new_shape[dim1], new_shape[dim2] = new_shape[dim2], new_shape[dim1]
        return MockTensor(shape=tuple(new_shape))
    
    def __add__(self, other):
        return MockTensor(shape=self.shape)
    
    def __getitem__(self, key):
        return MockTensor(shape=self.shape)


def concat(tensors: List[MockTensor], dim: int = 0) -> MockTensor:
    """Concatenate mock tensors."""
    if not tensors:
        return MockTensor()
    
    new_shape = list(tensors[0].shape)
    for t in tensors[1:]:
        new_shape[dim] += t.shape[dim]
    return MockTensor(shape=tuple(new_shape))


class OptimizedAttention:
    """
    Flash Attention with O(N) memory complexity.
    
    Features:
    - Chunked attention for memory efficiency
    - KV cache for autoregressive generation
    - Optional causal masking
    - Configurable chunk size
    """
    
    def __init__(self, config: AttentionConfig = None):
        self.config = config or AttentionConfig()
        self._cache_k: Optional[MockTensor] = None
        self._cache_v: Optional[MockTensor] = None
        self._stats = {
            "forward_calls": 0,
            "cache_hits": 0,
            "flash_chunks": 0,
        }
    
    def forward(
        self,
        query: MockTensor,
        key: MockTensor,
        value: MockTensor,
        mask: Optional[MockTensor] = None,
        use_cache: bool = True,
    ) -> MockTensor:
        """
        Forward pass with optional caching.
        
        Args:
            query: Query tensor [batch, seq_len, hidden]
            key: Key tensor [batch, seq_len, hidden]
            value: Value tensor [batch, seq_len, hidden]
            mask: Optional attention mask
            use_cache: Whether to use KV caching
        
        Returns:
            Attention output tensor
        """
        self._stats["forward_calls"] += 1
        
        if use_cache:
            key, value = self._update_cache(key, value)
            self._stats["cache_hits"] += 1
        
        if self.config.use_flash_attention:
            return self._flash_attention(query, key, value, mask)
        return self._standard_attention(query, key, value, mask)
    
    def _flash_attention(
        self,
        q: MockTensor,
        k: MockTensor,
        v: MockTensor,
        mask: Optional[MockTensor],
    ) -> MockTensor:
        """
        Chunked attention for memory efficiency.
        
        Processes attention in chunks to reduce peak memory usage
        from O(N^2) to O(N * chunk_size).
        """
        chunk_size = self.config.chunk_size
        seq_len = q.shape[1] if hasattr(q, 'shape') else 1
        
        output_chunks = []
        for i in range(0, seq_len, chunk_size):
            end_idx = min(i + chunk_size, seq_len)
            # Process chunk
            q_chunk = MockTensor(shape=(q.shape[0], end_idx - i, q.shape[2]))
            chunk_output = self._standard_attention(q_chunk, k, v, mask)
            output_chunks.append(chunk_output)
            self._stats["flash_chunks"] += 1
        
        # Concatenate chunks
        if len(output_chunks) == 1:
            return output_chunks[0]
        return concat(output_chunks, dim=1)
    
    def _standard_attention(
        self,
        q: MockTensor,
        k: MockTensor,
        v: MockTensor,
        mask: Optional[MockTensor],
    ) -> MockTensor:
        """
        Standard scaled dot-product attention.
        
        Attention(Q, K, V) = softmax(QK^T / sqrt(d_k)) V
        """
        scale = 1.0 / math.sqrt(self.config.head_dim)
        
        # Compute attention scores
        scores = q @ k.transpose(-2, -1)
        # Scale
        scores = MockTensor(shape=scores.shape)  # Simulate scaling
        
        # Apply mask if provided
        if mask is not None:
            scores = scores + mask
        
        # Softmax (simulated)
        # In real implementation: scores = softmax(scores, dim=-1)
        
        # Apply to values
        output = scores @ v
        return output
    
    def _update_cache(
        self,
        k: MockTensor,
        v: MockTensor,
    ) -> Tuple[MockTensor, MockTensor]:
        """Update KV cache for autoregressive generation."""
        if self._cache_k is None:
            self._cache_k = k
            self._cache_v = v
        else:
            self._cache_k = concat([self._cache_k, k], dim=1)
            self._cache_v = concat([self._cache_v, v], dim=1)
        
        return self._cache_k, self._cache_v
    
    def clear_cache(self) -> None:
        """Clear KV cache."""
        self._cache_k = None
        self._cache_v = None
    
    def get_cache_size(self) -> int:
        """Get current cache size in elements."""
        if self._cache_k is None:
            return 0
        return self._cache_k.shape[1]
    
    def get_stats(self) -> dict:
        """Get attention statistics."""
        return {
            **self._stats,
            "cache_size": self.get_cache_size(),
        }


# Convenience factory
def create_attention(
    num_heads: int = 32,
    head_dim: int = 128,
    use_flash: bool = True,
) -> OptimizedAttention:
    """Create optimized attention with specified configuration."""
    config = AttentionConfig(
        num_heads=num_heads,
        head_dim=head_dim,
        use_flash_attention=use_flash,
    )
    return OptimizedAttention(config)
