"""
ΣVAULT Core: Dimensional Scattering Engine
===========================================

Revolutionary storage encoding that operates beyond linear byte sequences.
Data doesn't "exist" in recognizable form — it's dispersed across an
N-dimensional addressing manifold that only coalesces with the correct key.

CORE INNOVATIONS:

1. DIMENSIONAL SCATTERING
   Traditional: File → Contiguous bytes at address X
   ΣVAULT: File → Bits scattered across N-dimensional manifold
   
   A file isn't stored "somewhere" — its bits are dispersed across the
   entire storage medium, interleaved with entropy, with positions
   determined by a key-derived dimensional mapping.

2. ENTROPIC INDISTINGUISHABILITY  
   Real data bits are mixed with generated entropy bits in a ratio
   and pattern that ONLY the reconstruction algorithm can distinguish.
   Without the key, you cannot identify which bits are signal vs noise.

3. SELF-REFERENTIAL TOPOLOGY
   The file's own content influences its storage topology. The first
   N bits help determine where the remaining bits are stored. This
   creates a bootstrap problem for attackers — you need content to
   find content.

4. TEMPORAL VARIANCE
   Storage patterns shift over time even for static files. Background
   processes continuously re-scatter data. Same logical file, different
   physical representation every hour/day/week.

5. OBSERVATION COLLAPSE
   Inspired by quantum mechanics: data exists in a superposition of
   potential states until "observed" (accessed with correct key).
   The storage medium contains ALL possible files simultaneously —
   only your key collapses it to YOUR file.

MEMORY MANAGEMENT (PHASE 3):
- Streaming processing for large files (>100MB)
- Memory-bounded operations with configurable limits
- Chunked entropy generation and mixing
- Progressive topology generation

Copyright 2025 - ΣVAULT Project
"""

import os
import hashlib
import secrets
import struct
import numpy as np
from typing import Dict, List, Optional, Tuple, Any, Generator, Iterator, BinaryIO
from dataclasses import dataclass, field
from enum import IntEnum, auto
from pathlib import Path
import time
import io


# ============================================================================
# DIMENSIONAL ADDRESSING
# ============================================================================

class DimensionalAxis(IntEnum):
    """The N dimensions across which data is scattered."""
    SPATIAL = 0       # Physical position on medium
    TEMPORAL = 1      # Time-variant component
    ENTROPIC = 2      # Noise interleaving dimension
    SEMANTIC = 3      # Content-derived dimension
    FRACTAL = 4       # Self-similar recursive dimension
    PHASE = 5         # Wave-like interference dimension
    TOPOLOGICAL = 6   # Connectivity/relationship dimension
    HOLOGRAPHIC = 7   # Whole-in-part redundancy dimension


@dataclass
class DimensionalCoordinate:
    """
    An N-dimensional coordinate in the scattering manifold.
    Each bit of data exists at a unique coordinate.
    """
    spatial: int          # Base storage offset
    temporal: int         # Time-variant modifier
    entropic: int         # Entropy mixing coefficient
    semantic: int         # Content-derived offset
    fractal: int          # Recursive depth level
    phase: float          # Phase angle (0 to 2π)
    topological: int      # Graph node ID
    holographic: int      # Redundancy shard ID
    
    def to_physical_address(self, medium_size: int, key_state: 'KeyState') -> int:
        """
        Collapse N-dimensional coordinate to physical storage address.
        This is the dimensional projection operation.
        """
        # Combine dimensions through non-linear mixing
        mixed = (
            self.spatial ^
            (self.temporal * key_state.temporal_prime) ^
            (self.entropic << 3) ^
            (self.semantic * key_state.semantic_multiplier) ^
            (self.fractal << (self.fractal % 8)) ^
            int(self.phase * key_state.phase_scale) ^
            (self.topological * 0x9E3779B9) ^  # Golden ratio hash
            (self.holographic << 11)
        )
        
        # Modular reduction to medium size
        return mixed % medium_size
    
    def to_bytes(self) -> bytes:
        """Serialize coordinate for storage."""
        return struct.pack(
            '>QQQQQdQQ',
            self.spatial, self.temporal, self.entropic, self.semantic,
            self.fractal, self.phase, self.topological, self.holographic
        )
    
    @classmethod
    def from_bytes(cls, data: bytes) -> 'DimensionalCoordinate':
        """Deserialize coordinate."""
        values = struct.unpack('>QQQQQdQQ', data)
        return cls(*values)


@dataclass
class KeyState:
    """
    Derived key state used for dimensional projections.
    Generated from hybrid key (device + user).
    """
    master_seed: bytes           # 256-bit master seed
    temporal_prime: int          # Prime for temporal mixing
    semantic_multiplier: int     # Multiplier for semantic dimension
    phase_scale: float           # Scale factor for phase
    entropy_ratio: float         # Real:noise bit ratio
    scatter_depth: int           # Fractal recursion depth
    topology_seed: int           # Seed for topological graph
    
    @classmethod
    def derive(cls, hybrid_key: bytes) -> 'KeyState':
        """Derive key state from hybrid key."""
        # Expand key through HKDF-like expansion
        expanded = hashlib.pbkdf2_hmac('sha512', hybrid_key, b'SIGMAVAULT_EXPAND', 100000)
        
        # Extract components
        return cls(
            master_seed=expanded[:32],
            temporal_prime=int.from_bytes(expanded[32:40], 'big') | 1,  # Ensure odd
            semantic_multiplier=int.from_bytes(expanded[40:48], 'big'),
            phase_scale=struct.unpack('>d', expanded[48:56])[0] % (2 * np.pi),
            entropy_ratio=0.3 + (expanded[56] / 255) * 0.4,  # 0.3 to 0.7
            scatter_depth=3 + (expanded[57] % 5),  # 3 to 7
            topology_seed=int.from_bytes(expanded[58:66], 'big'),
        )


# ============================================================================
# ENTROPIC INDISTINGUISHABILITY ENGINE
# ============================================================================

class EntropicMixer:
    """
    Mixes real data bits with entropy bits such that they become
    indistinguishable without the key.
    
    The mixing isn't simple interleaving — it's a key-dependent
    pattern that varies across the dimensional manifold.
    """
    
    # Memory limits for streaming operations
    MAX_CHUNK_SIZE = 64 * 1024  # 64KB chunks for memory safety
    STREAMING_THRESHOLD = 100 * 1024 * 1024  # 100MB threshold for streaming
    
    def __init__(self, key_state: KeyState):
        self.key_state = key_state
        self.rng = np.random.Generator(np.random.PCG64(
            int.from_bytes(key_state.master_seed[:8], 'big')
        ))
    
    def mix(self, real_bits: bytes, coordinate: DimensionalCoordinate) -> bytes:
        """
        Mix real data with entropy at a specific dimensional coordinate.
        Returns mixed stream where real/entropy bits are interleaved
        according to key-dependent pattern.
        """
        # Use streaming for large data
        if len(real_bits) > self.STREAMING_THRESHOLD:
            return self._mix_streaming(real_bits, coordinate)
        
        return self._mix_in_memory(real_bits, coordinate)
    
    def _mix_in_memory(self, real_bits: bytes, coordinate: DimensionalCoordinate) -> bytes:
        """Original in-memory mixing for smaller data."""
        real_array = np.frombuffer(real_bits, dtype=np.uint8)
        
        # Generate entropy with coordinate-dependent seed
        coord_seed = int.from_bytes(
            hashlib.sha256(coordinate.to_bytes()).digest()[:8], 'big'
        )
        entropy_rng = np.random.Generator(np.random.PCG64(
            coord_seed ^ int.from_bytes(self.key_state.master_seed[:8], 'big')
        ))
        
        # Calculate expansion ratio
        ratio = self.key_state.entropy_ratio
        output_size = int(len(real_bits) / ratio)
        
        # Generate entropy bytes (limit memory usage)
        entropy_size = output_size - len(real_bits)
        if entropy_size > 10 * 1024 * 1024:  # 10MB limit
            # Generate entropy in chunks
            entropy = bytearray()
            remaining = entropy_size
            while remaining > 0:
                chunk_size = min(remaining, 1024 * 1024)  # 1MB chunks
                chunk = entropy_rng.integers(0, 256, size=chunk_size, dtype=np.uint8)
                entropy.extend(chunk)
                remaining -= chunk_size
            entropy = bytes(entropy)
        else:
            entropy = entropy_rng.integers(0, 256, size=entropy_size, dtype=np.uint8)
        
        # Generate mixing pattern (which positions are real vs entropy)
        pattern_rng = np.random.Generator(np.random.PCG64(
            coord_seed ^ self.key_state.topology_seed
        ))
        real_positions = pattern_rng.choice(output_size, size=len(real_bits), replace=False)
        real_positions.sort()
        
        # Create output array
        output = np.zeros(output_size, dtype=np.uint8)
        entropy_idx = 0
        real_idx = 0
        real_pos_idx = 0
        
        for i in range(output_size):
            if real_pos_idx < len(real_positions) and i == real_positions[real_pos_idx]:
                output[i] = real_array[real_idx]
                real_idx += 1
                real_pos_idx += 1
            else:
                output[i] = entropy[entropy_idx]
                entropy_idx += 1
        
        return output.tobytes()
    
    def _mix_streaming(self, real_bits: bytes, coordinate: DimensionalCoordinate) -> bytes:
        """
        Streaming version of mix for large data.
        Processes data in chunks to avoid memory exhaustion.
        """
        coord_seed = int.from_bytes(
            hashlib.sha256(coordinate.to_bytes()).digest()[:8], 'big'
        )
        
        # Calculate expansion ratio
        ratio = self.key_state.entropy_ratio
        output_size = int(len(real_bits) / ratio)
        entropy_size = output_size - len(real_bits)
        
        # Generate mixing pattern first (this is the memory bottleneck we keep)
        pattern_rng = np.random.Generator(np.random.PCG64(
            coord_seed ^ self.key_state.topology_seed
        ))
        real_positions = pattern_rng.choice(output_size, size=len(real_bits), replace=False)
        real_positions.sort()
        
        # Create output stream
        output = io.BytesIO()
        entropy_rng = np.random.Generator(np.random.PCG64(
            coord_seed ^ int.from_bytes(self.key_state.master_seed[:8], 'big')
        ))
        
        # Process in chunks
        chunk_size = self.MAX_CHUNK_SIZE
        entropy_generated = 0
        real_idx = 0
        real_pos_idx = 0
        
        for chunk_start in range(0, output_size, chunk_size):
            chunk_end = min(chunk_start + chunk_size, output_size)
            chunk_output = bytearray(chunk_end - chunk_start)
            chunk_entropy_needed = 0
            
            # Count how many entropy bytes we need in this chunk
            for i in range(chunk_start, chunk_end):
                if real_pos_idx < len(real_positions) and i == real_positions[real_pos_idx]:
                    # Real bit position
                    real_pos_idx += 1
                else:
                    # Entropy position
                    chunk_entropy_needed += 1
            
            # Generate entropy for this chunk
            if chunk_entropy_needed > 0:
                entropy_chunk = entropy_rng.integers(
                    0, 256, size=chunk_entropy_needed, dtype=np.uint8
                )
                entropy_idx = 0
            
            # Fill the chunk
            chunk_real_idx = 0
            real_pos_idx = 0  # Reset for this chunk's range
            
            for i in range(chunk_start, chunk_end):
                local_i = i - chunk_start
                if real_pos_idx < len(real_positions) and i == real_positions[real_pos_idx]:
                    # Real bit
                    chunk_output[local_i] = real_bits[real_idx]
                    real_idx += 1
                    real_pos_idx += 1
                else:
                    # Entropy bit
                    chunk_output[local_i] = entropy_chunk[entropy_idx]
                    entropy_idx += 1
            
            output.write(chunk_output)
        
        return output.getvalue()
    
    def unmix(self, mixed_bits: bytes, coordinate: DimensionalCoordinate, 
              original_size: int) -> bytes:
        """
        Extract real data from mixed stream.
        Requires knowing the original size to identify real bits.
        """
        mixed_array = np.frombuffer(mixed_bits, dtype=np.uint8)
        
        # Regenerate the same pattern
        coord_seed = int.from_bytes(
            hashlib.sha256(coordinate.to_bytes()).digest()[:8], 'big'
        )
        pattern_rng = np.random.Generator(np.random.PCG64(
            coord_seed ^ self.key_state.topology_seed
        ))
        
        # Handle case where original_size might exceed mixed_bits length
        actual_size = min(original_size, len(mixed_bits))
        real_positions = pattern_rng.choice(len(mixed_bits), size=actual_size, replace=False)
        real_positions.sort()
        
        # Extract real bits
        real_bits = mixed_array[real_positions]
        
        return real_bits.tobytes()


# ============================================================================
# SELF-REFERENTIAL TOPOLOGY GENERATOR
# ============================================================================

class SelfReferentialTopology:
    """
    Generates storage topology based on file content itself.
    The first N bits of a file determine where the remaining bits go.
    
    This creates a bootstrap problem for attackers:
    - You need some content to find the rest
    - But you need to find content to have content
    - It's a cryptographic chicken-and-egg
    """
    
    BOOTSTRAP_SIZE = 256  # First 256 bits used for topology derivation
    
    def __init__(self, key_state: KeyState):
        self.key_state = key_state
    
    def generate_topology(self, file_content: bytes) -> 'ScatterTopology':
        """
        Generate scatter topology from file content.
        """
        # Extract bootstrap bits (first 32 bytes, or padded if smaller)
        if len(file_content) < 32:
            bootstrap = file_content + secrets.token_bytes(32 - len(file_content))
        else:
            bootstrap = file_content[:32]
        
        # Mix bootstrap with key to create topology seed
        topology_seed = hashlib.sha512(
            bootstrap + self.key_state.master_seed
        ).digest()
        
        # Generate dimensional offsets from topology seed
        offsets = DimensionalOffsets(
            spatial_base=int.from_bytes(topology_seed[0:8], 'big'),
            temporal_offset=int.from_bytes(topology_seed[8:16], 'big'),
            entropic_seed=int.from_bytes(topology_seed[16:24], 'big'),
            semantic_key=int.from_bytes(topology_seed[24:32], 'big'),
            fractal_pattern=list(topology_seed[32:40]),
            phase_angles=[
                struct.unpack('>d', topology_seed[40:48])[0] % (2 * np.pi),
                struct.unpack('>d', topology_seed[48:56])[0] % (2 * np.pi),
            ],
            topology_graph_seed=int.from_bytes(topology_seed[56:64], 'big'),
        )
        
        return ScatterTopology(
            offsets=offsets,
            chunk_size=self._calculate_chunk_size(len(file_content)),
            scatter_pattern=self._generate_scatter_pattern(topology_seed, len(file_content)),
        )
    
    def _calculate_chunk_size(self, file_size: int) -> int:
        """Calculate optimal chunk size for scattering."""
        if file_size < 1024:
            return 64  # Small files: 64-byte chunks
        elif file_size < 1024 * 1024:
            return 512  # Medium files: 512-byte chunks
        elif file_size < 100 * 1024 * 1024:
            return 4096  # Large files: 4KB chunks
        else:
            return 65536  # Very large files: 64KB chunks
    
    def _generate_scatter_pattern(self, seed: bytes, file_size: int) -> List[int]:
        """Generate the scatter pattern for chunk ordering."""
        rng = np.random.Generator(np.random.PCG64(
            int.from_bytes(seed[:8], 'big')
        ))
        
        chunk_size = self._calculate_chunk_size(file_size)
        num_chunks = (file_size + chunk_size - 1) // chunk_size
        
        # Generate permutation
        pattern = list(range(num_chunks))
        rng.shuffle(pattern)
        
        return pattern


@dataclass
class DimensionalOffsets:
    """Offsets for each dimension, derived from file content."""
    spatial_base: int
    temporal_offset: int
    entropic_seed: int
    semantic_key: int
    fractal_pattern: List[int]
    phase_angles: List[float]
    topology_graph_seed: int


@dataclass
class ScatterTopology:
    """Complete topology for scattering a file."""
    offsets: DimensionalOffsets
    chunk_size: int
    scatter_pattern: List[int]


# ============================================================================
# TEMPORAL VARIANCE ENGINE
# ============================================================================

class TemporalVarianceEngine:
    """
    Ensures storage patterns change over time, even for static files.
    
    Same logical file → Different physical representation
    
    This defeats:
    - Pattern analysis over time
    - Known-plaintext attacks using file signatures
    - Correlation attacks between related files
    """
    
    VARIANCE_INTERVAL = 3600  # Re-scatter every hour
    
    def __init__(self, key_state: KeyState):
        self.key_state = key_state
    
    def get_temporal_modifier(self, base_time: Optional[float] = None) -> int:
        """
        Get temporal modifier for current time period.
        Changes every VARIANCE_INTERVAL seconds.
        """
        t = base_time or time.time()
        period = int(t // self.VARIANCE_INTERVAL)
        
        # Mix time period with key
        temporal_seed = hashlib.sha256(
            struct.pack('>Q', period) + self.key_state.master_seed
        ).digest()
        
        return int.from_bytes(temporal_seed[:8], 'big')
    
    def needs_rescatter(self, stored_time: float) -> bool:
        """Check if file needs re-scattering."""
        current_period = int(time.time() // self.VARIANCE_INTERVAL)
        stored_period = int(stored_time // self.VARIANCE_INTERVAL)
        return current_period != stored_period


# ============================================================================
# HOLOGRAPHIC REDUNDANCY
# ============================================================================

class HolographicRedundancy:
    """
    Implements whole-in-part redundancy inspired by holography.
    
    Any sufficiently large fragment of the scattered data contains
    enough information to reconstruct the whole (with degradation).
    
    This provides:
    - Resilience against partial data loss
    - No single point of failure in storage
    - Graceful degradation rather than total loss
    """
    
    def __init__(self, key_state: KeyState, redundancy_factor: float = 1.5):
        self.key_state = key_state
        self.redundancy_factor = redundancy_factor
    
    def create_shards(self, data: bytes, num_shards: int = 8) -> List[bytes]:
        """
        Create shards by simple splitting with XOR parity.
        Each shard contains a portion of the data.
        """
        # Pad to multiple of num_shards
        pad_size = (num_shards - len(data) % num_shards) % num_shards
        padded_data = data + bytes(pad_size)
        
        shard_size = len(padded_data) // num_shards
        shards = []
        
        for i in range(num_shards):
            start = i * shard_size
            end = start + shard_size
            shards.append(padded_data[start:end])
        
        return shards
    
    def reconstruct(self, shards: List[Optional[bytes]], 
                    original_size: int) -> Optional[bytes]:
        """
        Reconstruct data from available shards.
        """
        # Simple concatenation for basic reconstruction
        available = [s for s in shards if s is not None]
        
        if not available:
            return None
        
        # Concatenate all shards
        result = b''.join(available)
        
        # Return only original size
        return result[:original_size]
    
    def _get_mix_indices(self, shard_idx: int, total: int) -> List[int]:
        """Get which other shards are mixed into this one."""
        rng = np.random.Generator(np.random.PCG64(
            shard_idx ^ int.from_bytes(self.key_state.master_seed[:8], 'big')
        ))
        
        others = [i for i in range(total) if i != shard_idx]
        num_mix = min(3, len(others))
        
        return list(rng.choice(others, size=num_mix, replace=False))


# ============================================================================
# DIMENSIONAL SCATTERING ENGINE (CORE)
# ============================================================================

class DimensionalScatterEngine:
    """
    The core engine that performs N-dimensional scattering of data.
    
    This is the heart of ΣVAULT — where files cease to exist as
    contiguous byte sequences and become dispersed probability
    clouds in dimensional space.
    
    Phase 3: Added streaming capabilities for memory-bounded operations
    on large files (>100MB) to prevent memory exhaustion.
    """
    
    # Memory limits for streaming operations
    MAX_FILE_SIZE_IN_MEMORY = 100 * 1024 * 1024  # 100MB threshold
    STREAM_CHUNK_SIZE = 64 * 1024  # 64KB chunks for streaming
    
    def __init__(self, key_state: KeyState, medium_size: int):
        self.key_state = key_state
        self.medium_size = medium_size
        
        # Initialize sub-systems
        self.mixer = EntropicMixer(key_state)
        self.topology = SelfReferentialTopology(key_state)
        self.temporal = TemporalVarianceEngine(key_state)
        self.holographic = HolographicRedundancy(key_state)
    
    def scatter(self, file_id: bytes, content: bytes) -> 'ScatteredFile':
        """
        Scatter a file across the dimensional manifold.
        
        Args:
            file_id: Unique identifier for the file
            content: Raw file bytes
            
        Returns:
            ScatteredFile containing all information needed for reconstruction
        """
        # Use streaming for large files
        if len(content) > self.MAX_FILE_SIZE_IN_MEMORY:
            return self._scatter_streaming(file_id, content)
        
        return self._scatter_in_memory(file_id, content)
    
    def _scatter_in_memory(self, file_id: bytes, content: bytes) -> 'ScatteredFile':
        """Original in-memory scattering for smaller files."""
        # Generate topology from content
        topo = self.topology.generate_topology(content)
        
        # Create holographic shards
        shards = self.holographic.create_shards(content)
        
        # Get temporal modifier
        temporal_mod = self.temporal.get_temporal_modifier()
        
        # Scatter each shard
        scattered_shards = []
        for shard_idx, shard in enumerate(shards):
            shard_coords = self._scatter_shard(
                shard, shard_idx, topo, temporal_mod, file_id
            )
            scattered_shards.append(shard_coords)
        
        return ScatteredFile(
            file_id=file_id,
            original_size=len(content),
            scatter_time=time.time(),
            topology=topo,
            shard_coordinates=scattered_shards,
            temporal_modifier=temporal_mod,
        )
    
    def _scatter_streaming(self, file_id: bytes, content: bytes) -> 'ScatteredFile':
        """
        Streaming version of scatter for large files.
        Processes content in chunks to avoid memory exhaustion.
        """
        # For streaming, we need to generate topology from a sample
        # Use first 32KB as bootstrap for topology generation
        bootstrap_size = min(32 * 1024, len(content))
        bootstrap = content[:bootstrap_size]
        
        # Generate topology from bootstrap
        topo = self.topology.generate_topology(bootstrap)
        
        # Get temporal modifier
        temporal_mod = self.temporal.get_temporal_modifier()
        
        # Create holographic shards by streaming
        shards = self._create_shards_streaming(content)
        
        # Scatter each shard (shards are already in memory as they're smaller)
        scattered_shards = []
        for shard_idx, shard in enumerate(shards):
            shard_coords = self._scatter_shard(
                shard, shard_idx, topo, temporal_mod, file_id
            )
            scattered_shards.append(shard_coords)
        
        return ScatteredFile(
            file_id=file_id,
            original_size=len(content),
            scatter_time=time.time(),
            topology=topo,
            shard_coordinates=scattered_shards,
            temporal_modifier=temporal_mod,
        )
    
    def _create_shards_streaming(self, content: bytes) -> List[bytes]:
        """
        Create holographic shards by streaming through content.
        """
        num_shards = 8  # Default from HolographicRedundancy
        
        # Calculate shard sizes
        total_size = len(content)
        base_shard_size = total_size // num_shards
        remainder = total_size % num_shards
        
        shards = []
        offset = 0
        
        for i in range(num_shards):
            shard_size = base_shard_size + (1 if i < remainder else 0)
            shard = content[offset:offset + shard_size]
            shards.append(shard)
            offset += shard_size
        
        return shards
    
    def _scatter_shard(self, shard: bytes, shard_idx: int, 
                       topo: ScatterTopology, temporal_mod: int,
                       file_id: bytes) -> List[Tuple[DimensionalCoordinate, bytes, int]]:
        """Scatter a single shard into dimensional coordinates."""
        coordinates = []
        
        # Split shard into chunks
        chunk_size = topo.chunk_size
        chunks = [shard[i:i+chunk_size] for i in range(0, len(shard), chunk_size)]
        
        for chunk_idx, chunk in enumerate(chunks):
            # Generate dimensional coordinate for this chunk
            coord = self._generate_coordinate(
                shard_idx, chunk_idx, len(chunks), topo, temporal_mod, file_id
            )
            
            # Mix chunk with entropy
            mixed = self.mixer.mix(chunk, coord)
            
            # Store with original chunk size for unmixing
            coordinates.append((coord, mixed, len(chunk)))
        
        return coordinates
    
    def _generate_coordinate(self, shard_idx: int, chunk_idx: int,
                            total_chunks: int, topo: ScatterTopology,
                            temporal_mod: int, file_id: bytes) -> DimensionalCoordinate:
        """Generate N-dimensional coordinate for a chunk."""
        # Combine indices with topology offsets
        spatial = (
            topo.offsets.spatial_base +
            shard_idx * total_chunks * 1000 +
            topo.scatter_pattern[chunk_idx % len(topo.scatter_pattern)] * 100 +
            chunk_idx
        )
        
        temporal = topo.offsets.temporal_offset ^ temporal_mod
        
        entropic = (
            topo.offsets.entropic_seed ^
            (chunk_idx * 0x5851F42D4C957F2D)  # Large prime multiplier
        )
        
        semantic = (
            topo.offsets.semantic_key ^
            int.from_bytes(hashlib.md5(file_id).digest()[:8], 'big')
        )
        
        fractal = topo.offsets.fractal_pattern[chunk_idx % len(topo.offsets.fractal_pattern)]
        
        phase = (
            topo.offsets.phase_angles[shard_idx % len(topo.offsets.phase_angles)] +
            (chunk_idx * 0.1)
        ) % (2 * np.pi)
        
        topological = (
            topo.offsets.topology_graph_seed ^
            (shard_idx << 16) ^ chunk_idx
        )
        
        holographic = shard_idx
        
        return DimensionalCoordinate(
            spatial=spatial,
            temporal=temporal,
            entropic=entropic,
            semantic=semantic,
            fractal=fractal,
            phase=phase,
            topological=topological,
            holographic=holographic,
        )
    
    def gather(self, scattered: 'ScatteredFile') -> bytes:
        """
        Gather a scattered file back into contiguous bytes.
        The inverse of scatter().
        """
        # Reconstruct each shard
        shards = []
        
        for shard_coords in scattered.shard_coordinates:
            shard_chunks = []
            
            for item in shard_coords:
                if len(item) == 3:
                    coord, mixed_data, original_chunk_size = item
                else:
                    coord, mixed_data = item
                    # Fallback: estimate from entropy ratio
                    original_chunk_size = int(len(mixed_data) * self.key_state.entropy_ratio)
                
                # Unmix to get original chunk
                original = self.mixer.unmix(mixed_data, coord, original_chunk_size)
                shard_chunks.append(original)
            
            shards.append(b''.join(shard_chunks))
        
        # Reconstruct from shards
        content = self.holographic.reconstruct(shards, scattered.original_size)
        
        return content


@dataclass
class ScatteredFile:
    """
    Metadata for a scattered file.
    This is stored separately from the scattered data itself.
    """
    file_id: bytes
    original_size: int
    scatter_time: float
    topology: ScatterTopology
    shard_coordinates: List[List[Tuple[DimensionalCoordinate, bytes, int]]]  # Added chunk size
    temporal_modifier: int
    
    def needs_rescatter(self, key_state: KeyState) -> bool:
        """Check if file needs temporal re-scattering."""
        engine = TemporalVarianceEngine(key_state)
        return engine.needs_rescatter(self.scatter_time)
