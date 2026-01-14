"""
ΣVAULT Machine Learning Integration
====================================

Phase 5: Adaptive Intelligence Layer

This module provides machine learning capabilities for ΣVAULT:
- Anomaly detection in access patterns
- Real-time threat detection and response (ML Security Bridge)
- Adaptive scattering parameter optimization
- Predictive re-scattering timing
- Pattern obfuscation via VAE models
- Decoy pattern generation
- Synthetic data generation for testing

Agents: @TENSOR @NEURAL @FORTRESS @SENTRY
Status: PHASE 5 - DAY 2 ACTIVE
"""

from .access_logger import AccessLogger, AccessEvent
from .anomaly_detector import AnomalyDetector, AlertLevel
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
from .pattern_vae import (
    PatternObfuscationVAE,
    VAEConfig,
    GeneratedPattern,
    create_pattern_vae,
    generate_decoy_events
)
from .security_bridge import (
    MLSecurityBridge,
    MLSecurityConfig,
    ThreatAction,
    ThreatResponse,
    AlertChannel,
    SecurityAlert,
    create_security_bridge
)

__all__ = [
    # Access Logging
    "AccessLogger",
    "AccessEvent",
    # Anomaly Detection
    "AnomalyDetector",
    "AlertLevel",
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
    # Pattern Obfuscation VAE
    "PatternObfuscationVAE",
    "VAEConfig",
    "GeneratedPattern",
    "create_pattern_vae",
    "generate_decoy_events",
    # ML Security Bridge (Day 2)
    "MLSecurityBridge",
    "MLSecurityConfig",
    "ThreatAction",
    "ThreatResponse",
    "AlertChannel",
    "SecurityAlert",
    "create_security_bridge",
]

__version__ = "0.5.1"
__phase__ = 5
__status__ = "DAY 2 ACTIVE"
