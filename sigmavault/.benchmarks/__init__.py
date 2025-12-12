"""
ΣVAULT Performance Benchmarking Suite
=====================================

Comprehensive benchmarks for measuring the performance characteristics
of all ΣVAULT core components:

- Key Derivation (Argon2id hybrid)
- Dimensional Scattering (8D manifold)
- Entropic Mixing (signal/noise interleaving)
- File Operations (scatter/gather for various sizes)
- Filesystem Operations (FUSE layer)
- Transaction Management (atomic operations)

Usage:
    python -m benchmarks.run_benchmarks
    pytest benchmarks/ --benchmark-only
"""

from .benchmark_core import (
    BenchmarkRunner,
    BenchmarkResult,
    BenchmarkConfig,
    run_all_benchmarks,
)

__all__ = [
    'BenchmarkRunner',
    'BenchmarkResult', 
    'BenchmarkConfig',
    'run_all_benchmarks',
]
