"""
ΣVAULT Machine Learning Integration
====================================

Phase 5: Adaptive Intelligence Layer

This module provides machine learning capabilities for ΣVAULT:
- Anomaly detection in access patterns
- Adaptive scattering parameter optimization
- Predictive re-scattering timing
- Pattern obfuscation via ML models
- Synthetic data generation for testing

Agents: @TENSOR @NEURAL @NEXUS
"""

from .access_logger import AccessLogger, AccessEvent
from .anomaly_detector import AnomalyDetector
from .feature_extractor import FeatureExtractor
from .synthetic_data_generator import (
    SyntheticDataGenerator,
    PatternType,
    UserProfile,
    generate_test_data
)
from .adaptive_scatter import (
    AdaptiveScatterEngine,
    LSTMScatterModel,
    ScatterParameters,
    ScatterParameterOptimizer,
    create_adaptive_engine
)

__all__ = [
    # Access Logging
    "AccessLogger",
    "AccessEvent",
    # Anomaly Detection
    "AnomalyDetector",
    # Feature Extraction
    "FeatureExtractor",
    # Synthetic Data
    "SyntheticDataGenerator",
    "PatternType",
    "UserProfile",
    "generate_test_data",
    # Adaptive Scatter
    "AdaptiveScatterEngine",
    "LSTMScatterModel",
    "ScatterParameters",
    "ScatterParameterOptimizer",
    "create_adaptive_engine",
]

__version__ = "0.5.0-alpha"
__phase__ = 5
__status__ = "ACTIVE"
