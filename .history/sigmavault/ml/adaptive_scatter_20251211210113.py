"""
LSTM Adaptive Scattering Engine
================================

Machine learning model that predicts optimal dimensional scatter
parameters based on access patterns.

Uses LSTM (Long Short-Term Memory) networks to:
- Learn from historical access patterns
- Predict optimal entropy_ratio for each file
- Optimize scatter_depth based on file sensitivity
- Adapt temporal_prime based on usage frequency

Architecture:
┌─────────────────────────────────────────────────────────────┐
│                 ADAPTIVE SCATTER ENGINE                     │
├─────────────────────────────────────────────────────────────┤
│  Input Layer                                                │
│  ───────────                                                │
│  • Access frequency features (11 features from extractor)   │
│  • File metadata (size, type, age)                         │
│  • Historical access sequences                              │
│                                                             │
│  LSTM Layer (128 units)                                     │
│  ──────────────────────                                     │
│  • Learns temporal patterns in access behavior              │
│  • Captures long-term dependencies                          │
│                                                             │
│  Dense Layers (64, 32)                                      │
│  ─────────────────────                                      │
│  • Maps LSTM output to scatter parameters                   │
│                                                             │
│  Output Layer (4 units)                                     │
│  ──────────────────────                                     │
│  • entropy_ratio: [0.1, 0.9] - How much entropy to mix      │
│  • scatter_depth: [1, 8] - Number of scatter dimensions     │
│  • temporal_prime: Large prime for temporal scattering      │
│  • phase_scale: [0.1, 10.0] - Phase dimension scaling       │
└─────────────────────────────────────────────────────────────┘

Copyright (c) 2025 ΣVAULT. All Rights Reserved.
Agents: @TENSOR @NEURAL @NEXUS @VELOCITY
"""

import os
import json
import hashlib
import pickle
import numpy as np
from pathlib import Path
from datetime import datetime, timedelta
from typing import List, Dict, Optional, Tuple, Any
from dataclasses import dataclass, field
from collections import deque
import threading
import time

# Conditional TensorFlow import for environments without GPU
try:
    import tensorflow as tf
    from tensorflow import keras
    from tensorflow.keras import layers, Model
    from tensorflow.keras.optimizers import Adam
    from tensorflow.keras.callbacks import EarlyStopping, ReduceLROnPlateau
    HAS_TENSORFLOW = True
except ImportError:
    HAS_TENSORFLOW = False
    tf = None
    keras = None

from .access_logger import AccessEvent
from .feature_extractor import FeatureExtractor


# ============================================================================
# DATA CLASSES
# ============================================================================

@dataclass
class ScatterParameters:
    """
    Optimal scatter parameters predicted by the LSTM model.
    
    These parameters control how files are dimensionally scattered.
    """
    entropy_ratio: float       # [0.1, 0.9] - Entropy mixing ratio
    scatter_depth: int         # [1, 8] - Number of scatter dimensions
    temporal_prime: int        # Large prime for temporal dimension
    phase_scale: float         # [0.1, 10.0] - Phase dimension scaling
    confidence: float = 0.0    # Model confidence [0, 1]
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            'entropy_ratio': self.entropy_ratio,
            'scatter_depth': self.scatter_depth,
            'temporal_prime': self.temporal_prime,
            'phase_scale': self.phase_scale,
            'confidence': self.confidence
        }
    
    @classmethod
    def default(cls) -> 'ScatterParameters':
        """Return default parameters when model unavailable."""
        return cls(
            entropy_ratio=0.5,
            scatter_depth=4,
            temporal_prime=15485863,  # 1 millionth prime
            phase_scale=1.0,
            confidence=0.0
        )


@dataclass
class AccessSequence:
    """
    A sequence of access events for LSTM training/prediction.
    
    The LSTM model takes sequences of events to understand temporal patterns.
    """
    events: List[AccessEvent]
    file_path_hash: str
    label: Optional[ScatterParameters] = None  # For supervised learning
    
    def to_features(self, extractor: FeatureExtractor) -> np.ndarray:
        """Convert sequence to feature array."""
        # Extract statistical features from the sequence
        features = extractor.extract_features(self.events)
        return np.array(features)


# ============================================================================
# LSTM MODEL DEFINITION
# ============================================================================

class LSTMScatterModel:
    """
    LSTM model for predicting optimal scatter parameters.
    
    Architecture:
    - Input: Sequence of access feature vectors (seq_len, n_features)
    - LSTM: 128 units with dropout
    - Dense: 64 -> 32 -> 4 (output)
    
    Example:
        >>> model = LSTMScatterModel()
        >>> model.build(input_shape=(50, 11))  # 50 timesteps, 11 features
        >>> params = model.predict(access_sequence)
    """
    
    def __init__(
        self,
        lstm_units: int = 128,
        dense_units: List[int] = [64, 32],
        dropout_rate: float = 0.2,
        learning_rate: float = 0.001
    ):
        """
        Initialize LSTM model.
        
        Args:
            lstm_units: Number of LSTM units
            dense_units: List of dense layer sizes
            dropout_rate: Dropout rate for regularization
            learning_rate: Learning rate for Adam optimizer
        """
        self.lstm_units = lstm_units
        self.dense_units = dense_units
        self.dropout_rate = dropout_rate
        self.learning_rate = learning_rate
        self.model: Optional[Model] = None
        self.is_built = False
        
        # Output scaling parameters
        self.entropy_range = (0.1, 0.9)
        self.scatter_range = (1, 8)
        self.prime_range = (1000003, 15485863)  # Prime number range
        self.phase_range = (0.1, 10.0)
        
        # Prime number cache for temporal_prime
        self._prime_cache = self._generate_primes(15485863)
    
    def _generate_primes(self, max_val: int) -> List[int]:
        """Generate prime numbers up to max_val using Sieve of Eratosthenes."""
        # For efficiency, we'll use a subset of known large primes
        known_primes = [
            1000003, 1000033, 1000037, 1000039, 1000081,
            2000003, 2000029, 2000039, 2000083, 2000107,
            5000011, 5000077, 5000081, 5000101, 5000113,
            10000019, 10000079, 10000103, 10000121, 10000139,
            15485863  # 1 millionth prime
        ]
        return known_primes
    
    def build(self, input_shape: Tuple[int, int] = (50, 11)):
        """
        Build the LSTM model architecture.
        
        Args:
            input_shape: (sequence_length, num_features)
        """
        if not HAS_TENSORFLOW:
            raise ImportError(
                "TensorFlow is required for LSTM model. "
                "Install with: pip install tensorflow"
            )
        
        seq_len, n_features = input_shape
        
        # Input layer
        inputs = keras.Input(shape=(seq_len, n_features), name='access_sequence')
        
        # LSTM layer with return sequences for richer features
        x = layers.LSTM(
            self.lstm_units,
            return_sequences=True,
            dropout=self.dropout_rate,
            recurrent_dropout=self.dropout_rate,
            name='lstm_1'
        )(inputs)
        
        # Second LSTM layer
        x = layers.LSTM(
            self.lstm_units // 2,
            return_sequences=False,
            dropout=self.dropout_rate,
            name='lstm_2'
        )(x)
        
        # Dense layers
        for i, units in enumerate(self.dense_units):
            x = layers.Dense(units, activation='relu', name=f'dense_{i}')(x)
            x = layers.Dropout(self.dropout_rate)(x)
        
        # Output layer: 4 parameters (entropy_ratio, scatter_depth, temporal_prime_idx, phase_scale)
        # Using sigmoid for bounded outputs
        outputs = layers.Dense(4, activation='sigmoid', name='scatter_params')(x)
        
        self.model = Model(inputs, outputs, name='lstm_scatter_model')
        self.model.compile(
            optimizer=Adam(learning_rate=self.learning_rate),
            loss='mse',
            metrics=['mae']
        )
        
        self.is_built = True
        return self
    
    def _scale_outputs(self, raw_outputs: np.ndarray) -> ScatterParameters:
        """Scale model outputs to actual parameter ranges."""
        # raw_outputs shape: (4,) with values in [0, 1]
        entropy = self.entropy_range[0] + raw_outputs[0] * (self.entropy_range[1] - self.entropy_range[0])
        
        scatter_idx = int(raw_outputs[1] * (self.scatter_range[1] - self.scatter_range[0])) + self.scatter_range[0]
        
        prime_idx = int(raw_outputs[2] * (len(self._prime_cache) - 1))
        temporal_prime = self._prime_cache[prime_idx]
        
        phase = self.phase_range[0] + raw_outputs[3] * (self.phase_range[1] - self.phase_range[0])
        
        return ScatterParameters(
            entropy_ratio=float(entropy),
            scatter_depth=scatter_idx,
            temporal_prime=temporal_prime,
            phase_scale=float(phase),
            confidence=float(np.mean(raw_outputs))  # Simple confidence proxy
        )
    
    def predict(self, sequence: np.ndarray) -> ScatterParameters:
        """
        Predict scatter parameters for an access sequence.
        
        Args:
            sequence: Shape (seq_len, n_features) or (batch, seq_len, n_features)
            
        Returns:
            ScatterParameters with predicted values
        """
        if not self.is_built or self.model is None:
            return ScatterParameters.default()
        
        # Ensure batch dimension
        if len(sequence.shape) == 2:
            sequence = np.expand_dims(sequence, axis=0)
        
        # Get raw predictions
        raw_outputs = self.model.predict(sequence, verbose=0)
        
        # Scale to parameter ranges
        return self._scale_outputs(raw_outputs[0])
    
    def train(
        self,
        X_train: np.ndarray,
        y_train: np.ndarray,
        epochs: int = 50,
        batch_size: int = 32,
        validation_split: float = 0.2
    ) -> Dict[str, List[float]]:
        """
        Train the model on labeled data.
        
        Args:
            X_train: Training sequences shape (n_samples, seq_len, n_features)
            y_train: Target parameters shape (n_samples, 4)
            epochs: Number of training epochs
            batch_size: Batch size
            validation_split: Fraction of data for validation
            
        Returns:
            Training history
        """
        if not self.is_built:
            self.build(input_shape=X_train.shape[1:])
        
        callbacks = [
            EarlyStopping(patience=10, restore_best_weights=True),
            ReduceLROnPlateau(factor=0.5, patience=5)
        ]
        
        history = self.model.fit(
            X_train, y_train,
            epochs=epochs,
            batch_size=batch_size,
            validation_split=validation_split,
            callbacks=callbacks,
            verbose=1
        )
        
        return history.history
    
    def save(self, path: Path):
        """Save model to disk."""
        if self.model is not None:
            self.model.save(path / 'lstm_scatter_model.keras')
            
            # Save configuration
            config = {
                'lstm_units': self.lstm_units,
                'dense_units': self.dense_units,
                'dropout_rate': self.dropout_rate,
                'learning_rate': self.learning_rate,
                'is_built': self.is_built
            }
            with open(path / 'model_config.json', 'w') as f:
                json.dump(config, f)
    
    def load(self, path: Path) -> 'LSTMScatterModel':
        """Load model from disk."""
        if not HAS_TENSORFLOW:
            return self
        
        model_path = path / 'lstm_scatter_model.keras'
        config_path = path / 'model_config.json'
        
        if model_path.exists() and config_path.exists():
            self.model = keras.models.load_model(model_path)
            
            with open(config_path, 'r') as f:
                config = json.load(f)
            
            self.lstm_units = config['lstm_units']
            self.dense_units = config['dense_units']
            self.dropout_rate = config['dropout_rate']
            self.learning_rate = config['learning_rate']
            self.is_built = config['is_built']
        
        return self


# ============================================================================
# ADAPTIVE SCATTER ENGINE
# ============================================================================

class AdaptiveScatterEngine:
    """
    Main engine for adaptive scatter parameter optimization.
    
    Uses LSTM model to predict optimal scatter parameters based on:
    - Historical access patterns
    - File characteristics
    - Temporal patterns
    
    Features:
    - Automatic model retraining on new data
    - Fallback to default parameters when model unavailable
    - Thread-safe operation
    - Continuous learning from access logs
    
    Example:
        >>> engine = AdaptiveScatterEngine(storage_path)
        >>> 
        >>> # Get parameters for a file based on recent access patterns
        >>> events = access_logger.get_recent_events(file_path, n=50)
        >>> params = engine.get_optimal_parameters(events)
        >>> 
        >>> # Use params for scatter operation
        >>> key_state = KeyState(
        ...     entropy_ratio=params.entropy_ratio,
        ...     scatter_depth=params.scatter_depth,
        ...     ...
        ... )
    """
    
    def __init__(
        self,
        storage_path: Path,
        seq_length: int = 50,
        retrain_interval_hours: int = 24,
        min_samples_for_training: int = 100
    ):
        """
        Initialize adaptive scatter engine.
        
        Args:
            storage_path: Path to store model and data
            seq_length: Number of events per sequence for LSTM
            retrain_interval_hours: Hours between model retraining
            min_samples_for_training: Minimum samples needed for training
        """
        self.storage_path = Path(storage_path)
        self.model_path = self.storage_path / 'models' / 'adaptive_scatter'
        self.model_path.mkdir(parents=True, exist_ok=True)
        
        self.seq_length = seq_length
        self.retrain_interval = timedelta(hours=retrain_interval_hours)
        self.min_samples = min_samples_for_training
        
        # Initialize components
        self.model = LSTMScatterModel()
        self.feature_extractor = FeatureExtractor()
        
        # Training data buffer
        self.training_buffer: deque = deque(maxlen=10000)
        self.last_training_time: Optional[datetime] = None
        
        # Thread safety
        self._lock = threading.RLock()
        
        # Try to load existing model
        self._try_load_model()
    
    def _try_load_model(self):
        """Attempt to load existing trained model."""
        try:
            if (self.model_path / 'lstm_scatter_model.keras').exists():
                self.model.load(self.model_path)
                
                # Load last training time
                meta_path = self.model_path / 'training_meta.json'
                if meta_path.exists():
                    with open(meta_path, 'r') as f:
                        meta = json.load(f)
                    self.last_training_time = datetime.fromisoformat(meta['last_training'])
        except Exception as e:
            print(f"Warning: Could not load adaptive scatter model: {e}")
    
    def get_optimal_parameters(
        self,
        events: List[AccessEvent],
        file_path: Optional[str] = None
    ) -> ScatterParameters:
        """
        Get optimal scatter parameters based on access history.
        
        Args:
            events: Recent access events for the file/user
            file_path: Optional file path for path-specific optimization
            
        Returns:
            ScatterParameters with optimal values
        """
        with self._lock:
            # Fall back to defaults if insufficient data
            if len(events) < 5:
                return ScatterParameters.default()
            
            # Extract features from events
            features = self.feature_extractor.extract_features(events)
            
            # Pad or truncate to seq_length
            feature_sequence = self._prepare_sequence(events)
            
            # Predict if model is ready
            if self.model.is_built:
                return self.model.predict(feature_sequence)
            else:
                return self._heuristic_parameters(features)
    
    def _prepare_sequence(self, events: List[AccessEvent]) -> np.ndarray:
        """
        Prepare event sequence for LSTM input.
        
        Converts events to feature vectors and pads/truncates to seq_length.
        """
        # Convert each event to feature vector
        feature_vectors = []
        
        for event in events[-self.seq_length:]:
            # Simple event-level features (11 features to match FeatureExtractor)
            vec = np.array([
                event.timestamp.hour / 24.0,  # Normalized hour
                event.timestamp.weekday() / 6.0,  # Normalized day
                1.0 if event.operation == 'read' else 0.0,
                1.0 if event.operation == 'write' else 0.0,
                min(event.bytes_accessed / 1e6, 1.0),  # Normalized bytes
                min(event.duration_ms / 1000.0, 1.0),  # Normalized duration
                1.0 if event.success else 0.0,
                0.0,  # Placeholder for additional features
                0.0,
                0.0,
                0.0
            ])
            feature_vectors.append(vec)
        
        # Pad if necessary
        while len(feature_vectors) < self.seq_length:
            feature_vectors.insert(0, np.zeros(11))  # Pad at beginning
        
        return np.array(feature_vectors)
    
    def _heuristic_parameters(
        self,
        features: List[float]
    ) -> ScatterParameters:
        """
        Calculate scatter parameters using heuristics when model unavailable.
        
        Uses feature statistics to determine appropriate parameters.
        """
        # Unpack features (from FeatureExtractor)
        # [access_frequency, unique_files, read_write_ratio, avg_file_size,
        #  access_entropy, time_mean, time_std, session_duration, error_rate,
        #  ip_diversity, operation_diversity]
        
        access_freq = features[0] if features else 1.0
        read_write_ratio = features[2] if len(features) > 2 else 0.5
        entropy = features[4] if len(features) > 4 else 0.5
        error_rate = features[8] if len(features) > 8 else 0.0
        
        # Higher access frequency -> lower scatter depth (faster access)
        scatter_depth = max(1, min(8, int(8 - access_freq * 6)))
        
        # Higher entropy in access patterns -> higher entropy ratio (more mixing)
        entropy_ratio = 0.3 + entropy * 0.4  # Range: 0.3 to 0.7
        
        # Higher error rate -> higher scatter depth (more security)
        if error_rate > 0.1:
            scatter_depth = min(8, scatter_depth + 2)
        
        # Read-heavy -> lower phase scale, write-heavy -> higher phase scale
        phase_scale = 1.0 + (1.0 - read_write_ratio) * 2.0
        
        return ScatterParameters(
            entropy_ratio=entropy_ratio,
            scatter_depth=scatter_depth,
            temporal_prime=15485863,  # Default prime
            phase_scale=phase_scale,
            confidence=0.5  # Medium confidence for heuristics
        )
    
    def add_training_sample(
        self,
        events: List[AccessEvent],
        optimal_params: ScatterParameters
    ):
        """
        Add a training sample to the buffer.
        
        Called when we know good parameters (e.g., from user feedback or
        performance metrics).
        
        Args:
            events: Access event sequence
            optimal_params: Known-good parameters for this sequence
        """
        with self._lock:
            sequence = self._prepare_sequence(events)
            target = np.array([
                (optimal_params.entropy_ratio - 0.1) / 0.8,  # Normalize to [0,1]
                (optimal_params.scatter_depth - 1) / 7.0,
                0.5,  # Prime index (middle of range)
                (optimal_params.phase_scale - 0.1) / 9.9
            ])
            
            self.training_buffer.append((sequence, target))
            
            # Check if we should retrain
            self._maybe_retrain()
    
    def _maybe_retrain(self):
        """Retrain model if conditions are met."""
        now = datetime.now()
        
        # Check conditions
        should_retrain = (
            len(self.training_buffer) >= self.min_samples and
            (self.last_training_time is None or
             now - self.last_training_time >= self.retrain_interval) and
            HAS_TENSORFLOW
        )
        
        if should_retrain:
            self._retrain_model()
    
    def _retrain_model(self):
        """Retrain the LSTM model on accumulated data."""
        if not HAS_TENSORFLOW:
            return
        
        print("Retraining adaptive scatter model...")
        
        # Prepare training data
        X = np.array([sample[0] for sample in self.training_buffer])
        y = np.array([sample[1] for sample in self.training_buffer])
        
        # Build and train model
        if not self.model.is_built:
            self.model.build(input_shape=X.shape[1:])
        
        self.model.train(X, y, epochs=30, batch_size=16)
        
        # Save model
        self.model.save(self.model_path)
        
        # Update metadata
        self.last_training_time = datetime.now()
        meta = {'last_training': self.last_training_time.isoformat()}
        with open(self.model_path / 'training_meta.json', 'w') as f:
            json.dump(meta, f)
        
        print(f"Model retrained with {len(self.training_buffer)} samples")
    
    def force_retrain(self):
        """Force immediate model retraining."""
        with self._lock:
            if len(self.training_buffer) >= 10:
                self._retrain_model()
            else:
                print(f"Insufficient data for training: {len(self.training_buffer)} samples")
    
    def get_model_stats(self) -> Dict[str, Any]:
        """Get statistics about the model."""
        return {
            'model_built': self.model.is_built,
            'training_samples': len(self.training_buffer),
            'last_training': self.last_training_time.isoformat() if self.last_training_time else None,
            'has_tensorflow': HAS_TENSORFLOW,
            'seq_length': self.seq_length
        }


# ============================================================================
# PARAMETER OPTIMIZER
# ============================================================================

class ScatterParameterOptimizer:
    """
    High-level optimizer that combines multiple signals for parameter selection.
    
    Combines:
    - LSTM predictions from access patterns
    - File sensitivity classification
    - System load considerations
    - User preferences
    
    Example:
        >>> optimizer = ScatterParameterOptimizer(storage_path)
        >>> params = optimizer.optimize(
        ...     events=recent_events,
        ...     file_sensitivity='high',
        ...     system_load=0.7
        ... )
    """
    
    def __init__(self, storage_path: Path):
        self.engine = AdaptiveScatterEngine(storage_path)
        
        # Sensitivity multipliers
        self.sensitivity_multipliers = {
            'low': {'entropy': 0.8, 'scatter': 0.5},
            'medium': {'entropy': 1.0, 'scatter': 1.0},
            'high': {'entropy': 1.2, 'scatter': 1.5},
            'critical': {'entropy': 1.5, 'scatter': 2.0}
        }
    
    def optimize(
        self,
        events: List[AccessEvent],
        file_sensitivity: str = 'medium',
        system_load: float = 0.5,
        user_preferences: Optional[Dict[str, float]] = None
    ) -> ScatterParameters:
        """
        Get optimized scatter parameters considering multiple factors.
        
        Args:
            events: Recent access events
            file_sensitivity: 'low', 'medium', 'high', 'critical'
            system_load: Current system load [0, 1]
            user_preferences: Optional user-specified preferences
            
        Returns:
            Optimized ScatterParameters
        """
        # Get base parameters from LSTM
        base_params = self.engine.get_optimal_parameters(events)
        
        # Apply sensitivity multipliers
        multipliers = self.sensitivity_multipliers.get(file_sensitivity, {'entropy': 1.0, 'scatter': 1.0})
        
        adjusted_entropy = min(0.9, base_params.entropy_ratio * multipliers['entropy'])
        adjusted_scatter = min(8, int(base_params.scatter_depth * multipliers['scatter']))
        
        # Adjust for system load (high load -> lower scatter depth for performance)
        if system_load > 0.8:
            adjusted_scatter = max(1, adjusted_scatter - 2)
        
        # Apply user preferences if provided
        if user_preferences:
            if 'entropy_ratio' in user_preferences:
                adjusted_entropy = user_preferences['entropy_ratio']
            if 'scatter_depth' in user_preferences:
                adjusted_scatter = int(user_preferences['scatter_depth'])
        
        return ScatterParameters(
            entropy_ratio=adjusted_entropy,
            scatter_depth=adjusted_scatter,
            temporal_prime=base_params.temporal_prime,
            phase_scale=base_params.phase_scale,
            confidence=base_params.confidence * 0.9  # Slightly reduced due to adjustments
        )


def create_adaptive_engine(storage_path: Path) -> AdaptiveScatterEngine:
    """
    Factory function to create an AdaptiveScatterEngine.
    
    Convenience function for quick instantiation.
    """
    return AdaptiveScatterEngine(storage_path)
