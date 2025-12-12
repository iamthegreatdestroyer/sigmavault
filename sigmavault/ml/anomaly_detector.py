"""
Anomaly Detector for Access Pattern Analysis
============================================

Isolation Forest-based anomaly detection for suspicious access patterns.

Copyright (c) 2025 ΣVAULT. All Rights Reserved.
Agents: @TENSOR @NEURAL
"""

import pickle
import numpy as np
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional, List, Dict, Tuple
from enum import Enum

try:
    from sklearn.ensemble import IsolationForest
    from sklearn.preprocessing import StandardScaler
    SKLEARN_AVAILABLE = True
except ImportError:
    SKLEARN_AVAILABLE = False

from .access_logger import AccessLogger, AccessEvent
from .feature_extractor import FeatureExtractor


class AlertLevel(Enum):
    """Alert severity levels."""
    NORMAL = 0
    SUSPICIOUS = 1
    WARNING = 2
    CRITICAL = 3


class AnomalyDetector:
    """
    ML-powered anomaly detector for file access patterns.
    
    Uses Isolation Forest algorithm to detect abnormal access behavior
    that may indicate:
    - Brute force attacks
    - Credential stuffing
    - Data exfiltration attempts
    - Malware behavior
    - Insider threats
    
    Features:
    - Real-time scoring of access patterns
    - Graduated alert system (suspicious → warning → critical)
    - Automatic model retraining
    - Explainable anomaly scores
    
    Example:
        >>> detector = AnomalyDetector(vault_path="/secure/vault")
        >>> detector.train(training_days=30)
        >>> 
        >>> # Later, check new access pattern
        >>> events = logger.get_recent_events(window=timedelta(hours=1))
        >>> is_anomaly, score, level = detector.detect(events)
        >>> if is_anomaly:
        ...     print(f"ALERT: Anomaly detected (score={score}, level={level})")
    """
    
    def __init__(
        self,
        vault_path: Path,
        contamination: float = 0.05,
        n_estimators: int = 100,
        alert_threshold: float = -0.5,
        critical_threshold: float = -0.8
    ):
        """
        Initialize anomaly detector.
        
        Args:
            vault_path: Path to vault directory
            contamination: Expected proportion of anomalies (0.01-0.1)
            n_estimators: Number of isolation trees
            alert_threshold: Score below which to alert (default: -0.5)
            critical_threshold: Score for critical alerts (default: -0.8)
        """
        if not SKLEARN_AVAILABLE:
            raise ImportError(
                "scikit-learn is required for anomaly detection. "
                "Install with: pip install scikit-learn"
            )
        
        self.vault_path = Path(vault_path)
        self.model_path = self.vault_path / ".ml" / "models" / "anomaly_detector.pkl"
        self.scaler_path = self.vault_path / ".ml" / "models" / "anomaly_scaler.pkl"
        self.model_path.parent.mkdir(parents=True, exist_ok=True)
        
        self.contamination = contamination
        self.n_estimators = n_estimators
        self.alert_threshold = alert_threshold
        self.critical_threshold = critical_threshold
        
        self.model: Optional[IsolationForest] = None
        self.scaler: Optional[StandardScaler] = None
        self.feature_extractor = FeatureExtractor()
        
        # Load existing model if available
        if self.model_path.exists():
            self.load_model()
    
    def train(
        self,
        training_days: int = 30,
        access_logger: Optional[AccessLogger] = None
    ) -> Dict[str, float]:
        """
        Train anomaly detector on historical access patterns.
        
        Args:
            training_days: Number of days of historical data to use
            access_logger: Optional AccessLogger instance (created if None)
            
        Returns:
            Training metrics dictionary
        """
        # Get training data
        if access_logger is None:
            access_logger = AccessLogger(self.vault_path)
        
        window = timedelta(days=training_days)
        all_events = access_logger.get_recent_events(window=window)
        
        if len(all_events) < 100:
            raise ValueError(
                f"Insufficient training data: {len(all_events)} events "
                f"(need at least 100). Run system for {training_days} days first."
            )
        
        # Create training sequences (sliding window of 1 hour)
        sequences = self._create_sequences(all_events, window_hours=1)
        
        # Extract features
        X = self.feature_extractor.extract_batch(sequences)
        
        if len(X) < 50:
            raise ValueError(
                f"Insufficient training sequences: {len(X)} "
                "(need at least 50)"
            )
        
        # Normalize features
        self.scaler = StandardScaler()
        X_scaled = self.scaler.fit_transform(X)
        
        # Train Isolation Forest
        self.model = IsolationForest(
            contamination=self.contamination,
            n_estimators=self.n_estimators,
            random_state=42,
            n_jobs=-1,  # Use all CPU cores
            warm_start=False
        )
        
        self.model.fit(X_scaled)
        
        # Save model
        self.save_model()
        
        # Calculate training metrics
        scores = self.model.score_samples(X_scaled)
        predictions = self.model.predict(X_scaled)
        
        metrics = {
            'n_samples': len(X),
            'n_anomalies': np.sum(predictions == -1),
            'anomaly_rate': np.mean(predictions == -1),
            'mean_score': np.mean(scores),
            'min_score': np.min(scores),
            'max_score': np.max(scores),
            'training_days': training_days,
            'timestamp': datetime.now().isoformat()
        }
        
        return metrics
    
    def detect(
        self,
        events: List[AccessEvent],
        return_score: bool = True
    ) -> Tuple[bool, float, AlertLevel]:
        """
        Detect if access pattern is anomalous.
        
        Args:
            events: Recent access events (recommend 1 hour window)
            return_score: Whether to return anomaly score
            
        Returns:
            Tuple of (is_anomaly, anomaly_score, alert_level)
        """
        if self.model is None:
            raise RuntimeError(
                "Model not trained. Call train() first or load existing model."
            )
        
        if not events:
            return False, 0.0, AlertLevel.NORMAL
        
        # Extract features
        features = self.feature_extractor.extract(events)
        X = np.array([list(features.values())])
        
        # Normalize
        X_scaled = self.scaler.transform(X)
        
        # Get anomaly score
        score = self.model.score_samples(X_scaled)[0]
        
        # Determine alert level
        if score >= self.alert_threshold:
            alert_level = AlertLevel.NORMAL
            is_anomaly = False
        elif score >= self.critical_threshold:
            alert_level = AlertLevel.WARNING
            is_anomaly = True
        else:
            alert_level = AlertLevel.CRITICAL
            is_anomaly = True
        
        return is_anomaly, score, alert_level
    
    def detect_batch(
        self,
        event_sequences: List[List[AccessEvent]]
    ) -> List[Tuple[bool, float, AlertLevel]]:
        """
        Detect anomalies in batch of event sequences.
        
        Args:
            event_sequences: List of event lists
            
        Returns:
            List of (is_anomaly, score, alert_level) tuples
        """
        if self.model is None:
            raise RuntimeError("Model not trained")
        
        # Extract features
        X = self.feature_extractor.extract_batch(event_sequences)
        
        if len(X) == 0:
            return []
        
        # Normalize
        X_scaled = self.scaler.transform(X)
        
        # Get scores
        scores = self.model.score_samples(X_scaled)
        
        # Determine alert levels
        results = []
        for score in scores:
            if score >= self.alert_threshold:
                alert_level = AlertLevel.NORMAL
                is_anomaly = False
            elif score >= self.critical_threshold:
                alert_level = AlertLevel.WARNING
                is_anomaly = True
            else:
                alert_level = AlertLevel.CRITICAL
                is_anomaly = True
            
            results.append((is_anomaly, score, alert_level))
        
        return results
    
    def explain_anomaly(
        self,
        events: List[AccessEvent],
        top_k: int = 5
    ) -> Dict[str, float]:
        """
        Explain which features contributed most to anomaly detection.
        
        Uses feature importance from decision path analysis.
        
        Args:
            events: Access events to explain
            top_k: Number of top contributing features to return
            
        Returns:
            Dictionary of feature_name -> contribution_score
        """
        if not events:
            return {}
        
        # Extract features
        features = self.feature_extractor.extract(events)
        feature_names = self.feature_extractor.get_feature_names()
        X = np.array([list(features.values())])
        
        # Normalize
        X_scaled = self.scaler.transform(X)
        
        # Get decision path (tree-based analysis)
        # For Isolation Forest: shorter path = more anomalous
        
        # Calculate feature contributions (simplified)
        # In production: use SHAP values for better explanations
        feature_values_scaled = X_scaled[0]
        
        # Calculate deviation from training mean
        training_mean = self.scaler.mean_
        training_std = self.scaler.scale_
        
        deviations = np.abs((X[0] - training_mean) / training_std)
        
        # Get top contributors
        top_indices = np.argsort(deviations)[-top_k:][::-1]
        
        explanations = {
            feature_names[i]: float(deviations[i])
            for i in top_indices
        }
        
        return explanations
    
    def save_model(self):
        """Save trained model and scaler to disk."""
        if self.model is None or self.scaler is None:
            raise RuntimeError("No model to save")
        
        with open(self.model_path, 'wb') as f:
            pickle.dump(self.model, f)
        
        with open(self.scaler_path, 'wb') as f:
            pickle.dump(self.scaler, f)
    
    def load_model(self):
        """Load trained model and scaler from disk."""
        if not self.model_path.exists() or not self.scaler_path.exists():
            raise FileNotFoundError("Model files not found")
        
        with open(self.model_path, 'rb') as f:
            self.model = pickle.load(f)
        
        with open(self.scaler_path, 'rb') as f:
            self.scaler = pickle.load(f)
    
    def _create_sequences(
        self,
        events: List[AccessEvent],
        window_hours: int = 1
    ) -> List[List[AccessEvent]]:
        """
        Create sliding window sequences from events.
        
        Args:
            events: Sorted list of events
            window_hours: Size of sliding window
            
        Returns:
            List of event sequences
        """
        if not events:
            return []
        
        # Sort by timestamp
        events = sorted(events, key=lambda e: e.timestamp)
        
        window = timedelta(hours=window_hours)
        sequences = []
        
        # Slide window with 50% overlap
        step = window / 2
        current_start = events[0].timestamp
        
        while current_start <= events[-1].timestamp:
            current_end = current_start + window
            
            # Get events in window
            window_events = [
                e for e in events
                if current_start <= e.timestamp < current_end
            ]
            
            if len(window_events) >= 3:  # Minimum events for features
                sequences.append(window_events)
            
            current_start += step
        
        return sequences
    
    def get_model_info(self) -> Dict:
        """Get information about trained model."""
        if self.model is None:
            return {'status': 'not_trained'}
        
        return {
            'status': 'trained',
            'n_estimators': self.n_estimators,
            'contamination': self.contamination,
            'alert_threshold': self.alert_threshold,
            'critical_threshold': self.critical_threshold,
            'model_path': str(self.model_path),
            'feature_count': len(self.feature_extractor.get_feature_names())
        }
