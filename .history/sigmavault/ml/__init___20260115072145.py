"""
ΣVAULT Machine Learning Integration
====================================

Phase 5: Adaptive Intelligence Layer

This module provides machine learning capabilities for ΣVAULT:
- Anomaly detection in access patterns
- Real-time threat detection and response (ML Security Bridge)
- Adaptive scattering parameter optimization
- Per-file scatter parameter caching with TTL
- Model update triggers based on pattern drift
- Predictive re-scattering timing
- Pattern obfuscation via VAE models
- Decoy pattern generation
- Synthetic data generation for testing

Agents: @TENSOR @NEURAL @FORTRESS @SENTRY
Status: PHASE 5 - DAY 3 ACTIVE
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
# Day 3: Adaptive Scatter Caching and Triggers
from .scatter_cache import (
    ScatterParameterCache,
    CacheConfig,
    CacheEntry,
    InvalidationReason,
    L1Cache,
    L2Cache,
    PrefetchManager,
    create_scatter_cache
)
from .model_triggers import (
    ModelUpdateTriggerManager,
    TriggerConfig,
    TriggerEvent,
    TriggerType,
    TriggerPriority,
    DriftDetector,
    AnomalyTrigger,
    PerformanceTrigger,
    ScheduledTrigger,
    create_trigger_manager
)
from .scatter_manager import (
    AdaptiveScatterManager,
    ManagerConfig,
    FileClassification,
    create_scatter_manager,
    get_file_sensitivity,
    get_file_type
)
# Day 4: Monitoring Dashboard
from .metrics_collector import (
    MetricsCollector,
    MetricType,
    Metric
)
from .alert_manager import (
    AlertManager,
    Alert,
    AlertSeverity,
    AlertChannel as AlertChannelProtocol,  # Renamed to avoid collision with security_bridge.AlertChannel
    EmailAlertChannel,
    WebhookAlertChannel,
    LogAlertChannel
)
from .monitoring_dashboard import (
    MonitoringDashboard,
    DashboardConfig
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
    # Scatter Cache (Day 3)
    "ScatterParameterCache",
    "CacheConfig",
    "CacheEntry",
    "InvalidationReason",
    "L1Cache",
    "L2Cache",
    "PrefetchManager",
    "create_scatter_cache",
    # Model Triggers (Day 3)
    "ModelUpdateTriggerManager",
    "TriggerConfig",
    "TriggerEvent",
    "TriggerType",
    "TriggerPriority",
    "DriftDetector",
    "AnomalyTrigger",
    "PerformanceTrigger",
    "ScheduledTrigger",
    "create_trigger_manager",
    # Scatter Manager (Day 3)
    "AdaptiveScatterManager",
    "ManagerConfig",
    "FileClassification",
    "create_scatter_manager",
    "get_file_sensitivity",
    "get_file_type",
    # Monitoring Dashboard (Day 4)
    "MetricsCollector",
    "MetricType",
    "Metric",
    "AlertManager",
    "Alert",
    "AlertSeverity",
    "AlertChannelProtocol",  # Renamed from AlertChannel to avoid collision
    "EmailAlertChannel",
    "WebhookAlertChannel",
    "LogAlertChannel",
    "MonitoringDashboard",
    "DashboardConfig",
]

__version__ = "0.5.4"
__phase__ = 5
__status__ = "DAY 4 ACTIVE"
