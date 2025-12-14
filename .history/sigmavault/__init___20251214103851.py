"""
ΣVAULT - Sub-Linear Encrypted Abstraction of Underlying Linear Technology
==========================================================================

A revolutionary filesystem where data doesn't exist in recognizable form.
Files are dimensionally scattered, entropically interleaved, and
temporally variant. The storage medium contains pure noise until
observed through the correct key.

Core Innovations:
- Dimensional Scattering: N-dimensional addressing manifold
- Entropic Indistinguishability: Signal/noise separation requires key
- Self-Referential Topology: Content determines its own storage layout
- Temporal Variance: Same file, different physical representation over time
- Holographic Redundancy: Partial data loss recoverable

Copyright 2025 - ΣVAULT Project
"""

__version__ = "1.0.0"
__author__ = "ΣVAULT Project"

# Import core components
from .core.dimensional_scatter import (
    DimensionalScatterEngine,
    DimensionalCoordinate,
    KeyState,
    ScatteredFile,
)

# Import crypto components
from .crypto.hybrid_key import HybridKeyDerivation

__all__ = [
    "DimensionalScatterEngine",
    "DimensionalCoordinate",
    "KeyState",
    "ScatteredFile",
    "HybridKeyDerivation",
]
