"""
ΣVAULT Scattering Benchmarks
============================

Benchmarks for the dimensional scattering engine:
- Dimensional coordinate generation
- Entropic mixing/unmixing
- Topology generation
- Full scatter/gather operations

Copyright 2025 - ΣVAULT Project
"""

import os
import secrets
import hashlib
import time
from typing import Dict

# Add parent to path for imports
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

from .benchmark_core import BenchmarkRunner, BenchmarkResult, BenchmarkConfig

try:
    from core.dimensional_scatter import (
        DimensionalCoordinate,
        KeyState,
        EntropicMixer,
        SelfReferentialTopology,
        DimensionalScatterEngine,
        ScatterStorageBackend,
    )
    HAS_SCATTER = True
except ImportError as e:
    print(f"Warning: Could not import scatter module: {e}")
    HAS_SCATTER = False


def run_scatter_benchmarks() -> Dict[str, BenchmarkResult]:
    """
    Run all scattering benchmarks.
    
    Returns:
        Dictionary mapping benchmark names to results
    """
    results = {}
    
    if not HAS_SCATTER:
        print("⚠️ Scattering module not available, skipping benchmarks")
        return results
    
    config = BenchmarkConfig(
        warmup_iterations=3,
        min_iterations=5,
        target_time_seconds=10.0,
    )
    runner = BenchmarkRunner(config)
    
    # Create test key state
    test_hybrid_key = secrets.token_bytes(64)
    key_state = KeyState.derive(test_hybrid_key)
    
    # ==================================================================
    # 1. DIMENSIONAL COORDINATE OPERATIONS
    # ==================================================================
    
    print("\n📐 Dimensional Coordinate Operations")
    print("-" * 40)
    
    def create_coordinate():
        return DimensionalCoordinate(
            spatial=secrets.randbelow(2**64),
            temporal=int(time.time() * 1000),
            entropic=secrets.randbelow(2**32),
            semantic=hash("test_content") & 0xFFFFFFFFFFFFFFFF,
            fractal=3,
            phase=1.5707963267948966,  # π/2
            topological=secrets.randbelow(2**32),
            holographic=0,
        )
    
    result = runner.run(create_coordinate, "Dimensional Coordinate Creation")
    print(result)
    results["coord_creation"] = result
    
    # Coordinate serialization
    test_coord = create_coordinate()
    
    def serialize_coordinate():
        return test_coord.to_bytes()
    
    def deserialize_coordinate():
        return DimensionalCoordinate.from_bytes(test_coord.to_bytes())
    
    result = runner.run(serialize_coordinate, "Coordinate Serialization")
    print(result)
    results["coord_serialize"] = result
    
    result = runner.run(deserialize_coordinate, "Coordinate Deserialization")
    print(result)
    results["coord_deserialize"] = result
    
    # Physical address projection
    def project_to_physical():
        return test_coord.to_physical_address(1024 * 1024 * 1024, key_state)
    
    result = runner.run(project_to_physical, "Physical Address Projection (1GB medium)")
    print(result)
    results["coord_projection"] = result
    
    # ==================================================================
    # 2. ENTROPIC MIXING
    # ==================================================================
    
    print("\n🔀 Entropic Mixing Operations")
    print("-" * 40)
    
    mixer = EntropicMixer(key_state)
    
    # Test data for various sizes
    data_1kb = secrets.token_bytes(1024)
    data_1mb = secrets.token_bytes(1024 * 1024)
    
    def mix_1kb():
        return mixer.mix(data_1kb, test_coord)
    
    def mix_1mb():
        return mixer.mix(data_1mb, test_coord)
    
    result = runner.run(mix_1kb, "Entropic Mix (1 KB)", data_size=1024)
    print(result)
    results["mix_1kb"] = result
    
    result = runner.run(mix_1mb, "Entropic Mix (1 MB)", data_size=1024*1024)
    print(result)
    results["mix_1mb"] = result
    
    # Unmixing
    mixed_1kb = mixer.mix(data_1kb, test_coord)
    mixed_1mb = mixer.mix(data_1mb, test_coord)
    
    def unmix_1kb():
        return mixer.unmix(mixed_1kb, test_coord, 1024)
    
    def unmix_1mb():
        return mixer.unmix(mixed_1mb, test_coord, 1024*1024)
    
    result = runner.run(unmix_1kb, "Entropic Unmix (1 KB)", data_size=1024)
    print(result)
    results["unmix_1kb"] = result
    
    result = runner.run(unmix_1mb, "Entropic Unmix (1 MB)", data_size=1024*1024)
    print(result)
    results["unmix_1mb"] = result
    
    # ==================================================================
    # 3. TOPOLOGY GENERATION
    # ==================================================================
    
    print("\n🗺️ Topology Generation")
    print("-" * 40)
    
    topology_gen = SelfReferentialTopology(key_state)
    
    def generate_topology_1kb():
        return topology_gen.generate_topology(data_1kb)
    
    def generate_topology_1mb():
        return topology_gen.generate_topology(data_1mb)
    
    result = runner.run(generate_topology_1kb, "Topology Generation (1 KB file)", data_size=1024)
    print(result)
    results["topology_1kb"] = result
    
    result = runner.run(generate_topology_1mb, "Topology Generation (1 MB file)", data_size=1024*1024)
    print(result)
    results["topology_1mb"] = result
    
    # ==================================================================
    # 4. FULL SCATTER/GATHER OPERATIONS
    # ==================================================================
    
    print("\n📊 Full Scatter/Gather Operations")
    print("-" * 40)
    
    try:
        # Create in-memory backend for testing
        import tempfile
        
        temp_dir = tempfile.mkdtemp(prefix="sigmavault_bench_")
        backend = ScatterStorageBackend(Path(temp_dir), medium_size=100 * 1024 * 1024)
        engine = DimensionalScatterEngine(key_state, backend)
        
        def scatter_1kb():
            return engine.scatter(data_1kb, "bench_1kb")
        
        def scatter_1mb():
            return engine.scatter(data_1mb, "bench_1mb")
        
        # Run scatter benchmarks
        result = runner.run(scatter_1kb, "Full Scatter (1 KB)", data_size=1024)
        print(result)
        results["scatter_full_1kb"] = result
        
        result = runner.run(scatter_1mb, "Full Scatter (1 MB)", data_size=1024*1024)
        print(result)
        results["scatter_full_1mb"] = result
        
        # Run gather benchmarks
        meta_1kb = engine.scatter(data_1kb, "bench_gather_1kb")
        meta_1mb = engine.scatter(data_1mb, "bench_gather_1mb")
        
        def gather_1kb():
            return engine.gather(meta_1kb)
        
        def gather_1mb():
            return engine.gather(meta_1mb)
        
        result = runner.run(gather_1kb, "Full Gather (1 KB)", data_size=1024)
        print(result)
        results["gather_full_1kb"] = result
        
        result = runner.run(gather_1mb, "Full Gather (1 MB)", data_size=1024*1024)
        print(result)
        results["gather_full_1mb"] = result
        
        # Cleanup
        import shutil
        shutil.rmtree(temp_dir, ignore_errors=True)
        
    except Exception as e:
        print(f"⚠️ Full scatter/gather benchmarks skipped: {e}")
    
    # ==================================================================
    # 5. LARGE FILE STREAMING (if time permits)
    # ==================================================================
    
    print("\n📦 Large File Operations (limited iterations)")
    print("-" * 40)
    
    try:
        # 10MB test for streaming
        data_10mb = secrets.token_bytes(10 * 1024 * 1024)
        
        config_large = BenchmarkConfig(
            warmup_iterations=1,
            min_iterations=3,
            max_iterations=5,
            target_time_seconds=30.0,
        )
        runner_large = BenchmarkRunner(config_large)
        
        def mix_10mb():
            return mixer.mix(data_10mb, test_coord)
        
        result = runner_large.run(mix_10mb, "Entropic Mix (10 MB)", data_size=10*1024*1024)
        print(result)
        results["mix_10mb"] = result
        
    except Exception as e:
        print(f"⚠️ Large file benchmarks skipped: {e}")
    
    return results


if __name__ == "__main__":
    run_scatter_benchmarks()
