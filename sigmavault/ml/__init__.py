"""
ΣVAULT Machine Learning Integration
====================================

Phase 5: Adaptive Intelligence Layer

This module provides machine learning capabilities for ΣVAULT:
- Anomaly detection in access patterns
- Adaptive scattering parameter optimization
- Predictive re-scattering timing
- Pattern obfuscation via ML models

Agents: @TENSOR @NEURAL @NEXUS
"""

from .access_logger import AccessLogger, AccessEvent
from .anomaly_detector import AnomalyDetector
from .feature_extractor import FeatureExtractor

__all__ = [
    "AccessLogger",
    "AccessEvent",
    "AnomalyDetector",
    "FeatureExtractor",
]

__version__ = "0.5.0-alpha"
__phase__ = 5
__status__ = "ACTIVE"
