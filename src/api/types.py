"""
Ryot LLM Type Definitions
==========================

Core types for the Ryot LLM pipeline with ΣLANG and RSU support.
"""

from dataclasses import dataclass, field
from typing import Optional, List, Tuple, Any, Dict
from enum import Enum


class StopReason(Enum):
    """Reasons for generation stop."""
    EOS = "eos"
    MAX_TOKENS = "max_tokens"
    STOP_SEQUENCE = "stop_sequence"
    ERROR = "error"


@dataclass
class TokenSequence:
    """Sequence of tokens."""
    
    tokens: Tuple[int, ...] = field(default_factory=tuple)
    sigma_encoded: bool = False
    semantic_hash: Optional[int] = None
    
    def __len__(self):
        return len(self.tokens)
    
    @classmethod
    def from_list(cls, tokens: List[int]) -> 'TokenSequence':
        """Create from list of tokens."""
        return cls(tokens=tuple(tokens))


@dataclass
class KVCacheState:
    """KV cache state for inference."""
    
    key_states: Optional[Any] = None
    value_states: Optional[Any] = None
    sequence_length: int = 0
    
    def export(self) -> bytes:
        """Export cache state to bytes."""
        import pickle
        return pickle.dumps(self)
    
    @classmethod
    def import_from(cls, data: bytes) -> 'KVCacheState':
        """Import cache state from bytes."""
        import pickle
        return pickle.loads(data)


@dataclass
class RSUReference:
    """Reference to a stored RSU."""
    
    rsu_id: str
    semantic_hash: int
    token_count: int
    has_kv_state: bool = False
    similarity: float = 1.0


@dataclass
class SigmaEncodedContext:
    """ΣLANG encoded context."""
    
    glyphs: bytes
    semantic_hash: int
    timestamp: int
    compression_ratio: float


@dataclass
class GenerationConfig:
    """Configuration for text generation with RSU support."""
    
    # Basic generation parameters
    max_tokens: int = 256
    temperature: float = 1.0
    top_p: float = 1.0
    top_k: int = 50
    repetition_penalty: float = 1.0
    stop_sequences: List[str] = field(default_factory=list)
    
    # ΣLANG compression settings
    use_sigma_compression: bool = False
    
    # RSU (Reusable Semantic Unit) settings
    use_rsu_warmstart: bool = True
    store_rsu: bool = True
    conversation_id: Optional[str] = None
    rsu_similarity_threshold: float = 0.85


@dataclass
class GenerationResult:
    """Result of text generation."""
    
    # Generation output
    generated_text: str
    completion_tokens: int
    prompt_tokens: int
    stop_reason: StopReason
    
    # ΣLANG/RSU metadata
    compression_ratio: float = 1.0
    rsu_reference: Optional[RSUReference] = None
    cache_warm_start_position: int = 0
    
    # Timing information
    generation_time: float = 0.0
    preprocessing_time: float = 0.0
    total_time: float = 0.0
    
    @property
    def total_tokens(self) -> int:
        """Total tokens (prompt + completion)."""
        return self.prompt_tokens + self.completion_tokens


@dataclass
class CompressionResult:
    """Result of context compression."""
    
    compressed_size: int
    original_size: int
    compression_ratio: float
    semantic_hash: int
    rsu_reference: Optional[str] = None


@dataclass
class ConversationTurn:
    """Single turn in a conversation."""
    
    role: str  # "user" or "assistant"
    content: str
    tokens: Optional[TokenSequence] = None
    rsu_reference: Optional[RSUReference] = None
    timestamp: Optional[int] = None


@dataclass
class ConversationContext:
    """Full conversation context."""
    
    conversation_id: str
    turns: List[ConversationTurn] = field(default_factory=list)
    rsu_chain: List[RSUReference] = field(default_factory=list)
    total_tokens: int = 0
    creation_time: Optional[int] = None
    last_updated: Optional[int] = None


# Agent types
@dataclass
class AgentRequest:
    """Request to an agent."""
    
    agent_id: str
    task: str
    context: Optional[Dict[str, Any]] = None
    parameters: Optional[Dict[str, Any]] = None


@dataclass
class AgentResponse:
    """Response from an agent."""
    
    agent_id: str
    result: Any
    success: bool = True
    error: Optional[str] = None


# Exception types
class RSUError(Exception):
    """RSU-related error."""
    
    def __init__(self, message: str, context: str = ""):
        self.message = message
        self.context = context
        super().__init__(f"{context}: {message}" if context else message)


# Cache strategy types
class CacheStrategy(Enum):
    """KV cache strategy."""
    NONE = "none"
    FULL = "full"
    STANDARD = "standard"
    SLIDING = "sliding"
    COMPRESSED = "compressed"
    BITNET = "bitnet"


@dataclass
class KVCache:
    """KV cache interface."""
    
    key_states: Optional[Any] = None
    value_states: Optional[Any] = None
    sequence_length: int = 0
    max_length: int = 1024
    
    def load_state(self, state: 'KVCacheState') -> None:
        """Load cache state."""
        self.key_states = state.key_states
        self.value_states = state.value_states
        self.sequence_length = state.sequence_length


@dataclass
class ModelInfo:
    """Model information."""
    
    model_id: str
    model_name: str
    version: str
    context_window: int = 8192
    parameters: int = 0
    type: str = "transformer"


@dataclass
class ChunkRequest:
    """Request to chunk content."""
    
    content: bytes
    chunk_size: int = 1024
    overlap: int = 0


@dataclass  
class CompressionTask:
    """Task for compression engine."""
    
    task_id: str
    content: bytes
    compression_level: int = 3
    method: str = "glyph"


class ModelType(Enum):
    """Type of model."""
    LLM = "llm"
    ENCODER = "encoder"
    DECODER = "decoder"
    RERANKER = "reranker"
    BITNET = "bitnet"


@dataclass
class StreamChunk:
    """Chunk of streaming data."""
    
    content: str
    index: int = 0
    final: bool = False
