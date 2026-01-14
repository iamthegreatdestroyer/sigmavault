"""
Pattern Obfuscation VAE (Variational Autoencoder)
==================================================

Generates realistic decoy access patterns to obfuscate real user behavior.

When an attacker observes access patterns, they should be unable to
distinguish real activity from AI-generated decoy patterns. This provides
a powerful layer of protection through plausible deniability.

Architecture:
┌─────────────────────────────────────────────────────────────┐
│                  PATTERN OBFUSCATION VAE                    │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│  ENCODER                        DECODER                     │
│  ────────                       ────────                    │
│  Input (11 features)            Latent Space (z)            │
│       ↓                              ↓                      │
│  Dense(64) + BN                 Dense(64) + BN              │
│       ↓                              ↓                      │
│  Dense(32) + BN                 Dense(32) + BN              │
│       ↓                              ↓                      │
│  μ + log(σ²)                    Reconstructed Features      │
│       ↓                                                     │
│  Reparameterization:                                        │
│  z = μ + σ · ε                                              │
│                                                             │
├─────────────────────────────────────────────────────────────┤
│  LOSS = Reconstruction Loss + β * KL Divergence             │
│                                                             │
│  Reconstruction: MSE between input and output               │
│  KL: Force latent space to follow N(0,1)                   │
│  β: Weight for disentanglement (default: 0.1)               │
└─────────────────────────────────────────────────────────────┘

USE CASES:

1. DECOY GENERATION
   Generate realistic fake access patterns that are statistically
   indistinguishable from real user behavior.

2. PATTERN AUGMENTATION
   Create variations of real patterns for training other ML models.

3. PRIVACY PROTECTION
   Mix real access logs with generated decoys to obscure actual
   behavior patterns.

4. ANOMALY BASELINE
   Understand the distribution of "normal" patterns to better
   identify anomalies.

Copyright (c) 2026 ΣVAULT. All Rights Reserved.
Agents: @TENSOR @NEURAL @NEXUS
"""

import os
import json
import pickle
import numpy as np
from pathlib import Path
from datetime import datetime, timedelta
from typing import List, Dict, Optional, Tuple, Any
from dataclasses import dataclass
import threading

# Conditional TensorFlow import
try:
    import tensorflow as tf
    from tensorflow import keras
    from tensorflow.keras import layers, Model, backend as K
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
class VAEConfig:
    """Configuration for the Pattern Obfuscation VAE."""
    latent_dim: int = 8            # Latent space dimensionality
    encoder_units: List[int] = None  # Encoder layer sizes
    decoder_units: List[int] = None  # Decoder layer sizes
    beta: float = 0.1              # KL divergence weight (β-VAE)
    learning_rate: float = 0.001
    batch_size: int = 32
    epochs: int = 100
    dropout_rate: float = 0.2
    
    def __post_init__(self):
        if self.encoder_units is None:
            self.encoder_units = [64, 32]
        if self.decoder_units is None:
            self.decoder_units = [32, 64]


@dataclass
class GeneratedPattern:
    """A generated decoy access pattern."""
    features: Dict[str, float]     # Feature dictionary
    latent_code: np.ndarray        # Latent space representation
    reconstruction_loss: float     # How well it matches training data
    timestamp: datetime
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            'features': self.features,
            'latent_code': self.latent_code.tolist(),
            'reconstruction_loss': self.reconstruction_loss,
            'timestamp': self.timestamp.isoformat()
        }


# ============================================================================
# SAMPLING LAYER (Reparameterization Trick)
# ============================================================================

class Sampling(layers.Layer):
    """
    Sampling layer using the reparameterization trick.
    
    z = μ + σ · ε, where ε ~ N(0, I)
    
    This allows gradients to flow through the sampling operation.
    """
    
    def call(self, inputs):
        z_mean, z_log_var = inputs
        batch = tf.shape(z_mean)[0]
        dim = tf.shape(z_mean)[1]
        
        # Sample epsilon from standard normal
        epsilon = tf.random.normal(shape=(batch, dim))
        
        # Reparameterization: z = μ + σ * ε
        return z_mean + tf.exp(0.5 * z_log_var) * epsilon


# ============================================================================
# PATTERN OBFUSCATION VAE
# ============================================================================

class PatternObfuscationVAE:
    """
    Variational Autoencoder for generating realistic access pattern decoys.
    
    This model learns the distribution of normal access patterns and can
    generate new patterns that are statistically indistinguishable from
    real user behavior.
    
    Example:
        >>> vae = PatternObfuscationVAE(vault_path="/secure/vault")
        >>> vae.train(training_data)
        >>> 
        >>> # Generate decoy patterns
        >>> decoys = vae.generate_decoys(n=100)
        >>> for decoy in decoys:
        ...     print(f"Generated pattern: {decoy.features}")
        
        >>> # Interpolate between two patterns
        >>> interpolated = vae.interpolate(pattern_a, pattern_b, steps=10)
    """
    
    # Feature names (from FeatureExtractor)
    FEATURE_NAMES = [
        'access_frequency',
        'unique_files',
        'read_write_ratio',
        'avg_file_size',
        'access_entropy',
        'time_of_day_mean',
        'time_of_day_std',
        'session_duration',
        'error_rate',
        'ip_diversity',
        'operation_diversity',
    ]
    
    def __init__(
        self,
        vault_path: Path,
        config: Optional[VAEConfig] = None
    ):
        """
        Initialize Pattern Obfuscation VAE.
        
        Args:
            vault_path: Path to vault directory (for model storage)
            config: VAE configuration (uses defaults if None)
        """
        if not HAS_TENSORFLOW:
            raise ImportError(
                "TensorFlow is required for Pattern Obfuscation VAE. "
                "Install with: pip install tensorflow"
            )
        
        self.vault_path = Path(vault_path)
        self.config = config or VAEConfig()
        
        # Model paths
        self.model_dir = self.vault_path / ".ml" / "models" / "vae"
        self.model_dir.mkdir(parents=True, exist_ok=True)
        self.encoder_path = self.model_dir / "encoder.keras"
        self.decoder_path = self.model_dir / "decoder.keras"
        self.config_path = self.model_dir / "config.json"
        self.scaler_path = self.model_dir / "scaler.pkl"
        
        # Feature extraction
        self.feature_extractor = FeatureExtractor()
        self.n_features = len(self.FEATURE_NAMES)
        
        # Model components
        self.encoder: Optional[Model] = None
        self.decoder: Optional[Model] = None
        self.vae: Optional[Model] = None
        self.scaler: Optional[Any] = None
        
        # Training state
        self.is_trained = False
        self._lock = threading.RLock()
        
        # Load existing model if available
        if self.encoder_path.exists() and self.decoder_path.exists():
            self.load()
    
    def _build_encoder(self) -> Model:
        """Build the encoder network."""
        inputs = keras.Input(shape=(self.n_features,), name='encoder_input')
        
        x = inputs
        for i, units in enumerate(self.config.encoder_units):
            x = layers.Dense(units, name=f'encoder_dense_{i}')(x)
            x = layers.BatchNormalization(name=f'encoder_bn_{i}')(x)
            x = layers.ReLU(name=f'encoder_relu_{i}')(x)
            x = layers.Dropout(self.config.dropout_rate, name=f'encoder_dropout_{i}')(x)
        
        # Latent space parameters
        z_mean = layers.Dense(self.config.latent_dim, name='z_mean')(x)
        z_log_var = layers.Dense(self.config.latent_dim, name='z_log_var')(x)
        
        # Sampling layer
        z = Sampling(name='sampling')([z_mean, z_log_var])
        
        encoder = Model(inputs, [z_mean, z_log_var, z], name='encoder')
        return encoder
    
    def _build_decoder(self) -> Model:
        """Build the decoder network."""
        latent_inputs = keras.Input(shape=(self.config.latent_dim,), name='decoder_input')
        
        x = latent_inputs
        for i, units in enumerate(self.config.decoder_units):
            x = layers.Dense(units, name=f'decoder_dense_{i}')(x)
            x = layers.BatchNormalization(name=f'decoder_bn_{i}')(x)
            x = layers.ReLU(name=f'decoder_relu_{i}')(x)
            x = layers.Dropout(self.config.dropout_rate, name=f'decoder_dropout_{i}')(x)
        
        # Output layer (reconstruct original features)
        outputs = layers.Dense(self.n_features, activation='sigmoid', name='decoder_output')(x)
        
        decoder = Model(latent_inputs, outputs, name='decoder')
        return decoder
    
    def _build_vae(self) -> Model:
        """Build the complete VAE model using Keras 3 compatible approach."""
        # Build encoder and decoder
        self.encoder = self._build_encoder()
        self.decoder = self._build_decoder()
        
        # Create VAE as a custom model class for Keras 3 compatibility
        class VAEModel(Model):
            def __init__(vae_self, encoder, decoder, beta, **kwargs):
                super().__init__(**kwargs)
                vae_self.encoder = encoder
                vae_self.decoder = decoder
                vae_self.beta = beta
                vae_self.total_loss_tracker = keras.metrics.Mean(name="total_loss")
                vae_self.reconstruction_loss_tracker = keras.metrics.Mean(name="reconstruction_loss")
                vae_self.kl_loss_tracker = keras.metrics.Mean(name="kl_loss")

            @property
            def metrics(vae_self):
                return [
                    vae_self.total_loss_tracker,
                    vae_self.reconstruction_loss_tracker,
                    vae_self.kl_loss_tracker,
                ]

            def train_step(vae_self, data):
                # Handle both (x,) and (x, y) cases from fit()
                if isinstance(data, tuple):
                    x = data[0]  # For VAE, input and target are the same
                else:
                    x = data
                    
                with tf.GradientTape() as tape:
                    z_mean, z_log_var, z = vae_self.encoder(x)
                    reconstruction = vae_self.decoder(z)
                    
                    # Use keras.ops for compatibility
                    reconstruction_loss = keras.ops.mean(
                        keras.ops.sum(
                            keras.ops.square(x - reconstruction),
                            axis=1
                        )
                    )
                    
                    kl_loss = -0.5 * keras.ops.mean(
                        keras.ops.sum(
                            1 + z_log_var - keras.ops.square(z_mean) - keras.ops.exp(z_log_var),
                            axis=1
                        )
                    )
                    
                    total_loss = reconstruction_loss + vae_self.beta * kl_loss
                
                grads = tape.gradient(total_loss, vae_self.trainable_weights)
                vae_self.optimizer.apply_gradients(zip(grads, vae_self.trainable_weights))
                
                vae_self.total_loss_tracker.update_state(total_loss)
                vae_self.reconstruction_loss_tracker.update_state(reconstruction_loss)
                vae_self.kl_loss_tracker.update_state(kl_loss)
                
                return {
                    "loss": vae_self.total_loss_tracker.result(),
                    "reconstruction_loss": vae_self.reconstruction_loss_tracker.result(),
                    "kl_loss": vae_self.kl_loss_tracker.result(),
                }
            
            def test_step(vae_self, data):
                # Handle both (x,) and (x, y) cases from fit()
                if isinstance(data, tuple):
                    x = data[0]
                else:
                    x = data
                    
                z_mean, z_log_var, z = vae_self.encoder(x)
                reconstruction = vae_self.decoder(z)
                
                reconstruction_loss = keras.ops.mean(
                    keras.ops.sum(
                        keras.ops.square(x - reconstruction),
                        axis=1
                    )
                )
                
                kl_loss = -0.5 * keras.ops.mean(
                    keras.ops.sum(
                        1 + z_log_var - keras.ops.square(z_mean) - keras.ops.exp(z_log_var),
                        axis=1
                    )
                )
                
                total_loss = reconstruction_loss + vae_self.beta * kl_loss
                
                return {
                    "loss": total_loss,
                    "reconstruction_loss": reconstruction_loss,
                    "kl_loss": kl_loss,
                }
            
            def call(vae_self, inputs):
                z_mean, z_log_var, z = vae_self.encoder(inputs)
                return vae_self.decoder(z)
        
        vae = VAEModel(self.encoder, self.decoder, self.config.beta, name='pattern_vae')
        vae.compile(optimizer=Adam(learning_rate=self.config.learning_rate))
        
        return vae
    
    def train(
        self,
        events_list: List[List[AccessEvent]],
        validation_split: float = 0.2,
        verbose: int = 1
    ) -> Dict[str, Any]:
        """
        Train the VAE on access pattern data.
        
        Args:
            events_list: List of event sequences (each sequence is a time window)
            validation_split: Fraction of data for validation
            verbose: Verbosity level (0=silent, 1=progress, 2=full)
            
        Returns:
            Training history and metrics
        """
        with self._lock:
            # Extract features from event sequences
            X = self.feature_extractor.extract_batch(events_list)
            
            if len(X) < 50:
                raise ValueError(
                    f"Insufficient training data: {len(X)} sequences "
                    "(need at least 50)"
                )
            
            # Normalize features to [0, 1] for sigmoid output
            from sklearn.preprocessing import MinMaxScaler
            self.scaler = MinMaxScaler()
            X_scaled = self.scaler.fit_transform(X)
            
            # Build model
            self.vae = self._build_vae()
            
            # Callbacks
            callbacks = [
                EarlyStopping(
                    monitor='val_loss',
                    patience=10,
                    restore_best_weights=True
                ),
                ReduceLROnPlateau(
                    monitor='val_loss',
                    factor=0.5,
                    patience=5,
                    min_lr=1e-6
                )
            ]
            
            # Train
            history = self.vae.fit(
                X_scaled, X_scaled,
                epochs=self.config.epochs,
                batch_size=self.config.batch_size,
                validation_split=validation_split,
                callbacks=callbacks,
                verbose=verbose
            )
            
            self.is_trained = True
            
            # Save model
            self.save()
            
            # Compute metrics
            predictions = self.vae.predict(X_scaled, verbose=0)
            reconstruction_error = np.mean((X_scaled - predictions) ** 2)
            
            return {
                'n_samples': len(X),
                'n_features': self.n_features,
                'latent_dim': self.config.latent_dim,
                'final_loss': float(history.history['loss'][-1]),
                'final_val_loss': float(history.history['val_loss'][-1]),
                'reconstruction_error': float(reconstruction_error),
                'epochs_trained': len(history.history['loss']),
                'timestamp': datetime.now().isoformat()
            }
    
    def generate_decoys(
        self,
        n: int = 10,
        noise_scale: float = 1.0
    ) -> List[GeneratedPattern]:
        """
        Generate realistic decoy access patterns.
        
        Args:
            n: Number of decoys to generate
            noise_scale: Scale of noise (higher = more variation)
            
        Returns:
            List of GeneratedPattern objects
        """
        if not self.is_trained:
            raise RuntimeError("Model not trained. Call train() first.")
        
        with self._lock:
            # Sample from latent space (standard normal)
            z_samples = np.random.randn(n, self.config.latent_dim) * noise_scale
            
            # Decode to feature space
            decoded = self.decoder.predict(z_samples, verbose=0)
            
            # Inverse transform to original scale
            features_scaled = self.scaler.inverse_transform(decoded)
            
            # Create GeneratedPattern objects
            decoys = []
            for i in range(n):
                feature_dict = {
                    name: float(features_scaled[i, j])
                    for j, name in enumerate(self.FEATURE_NAMES)
                }
                
                # Compute reconstruction loss
                encoded = self.encoder.predict(decoded[i:i+1], verbose=0)
                z_mean, z_log_var, z = encoded
                re_decoded = self.decoder.predict(z, verbose=0)
                recon_loss = float(np.mean((decoded[i] - re_decoded[0]) ** 2))
                
                decoys.append(GeneratedPattern(
                    features=feature_dict,
                    latent_code=z_samples[i],
                    reconstruction_loss=recon_loss,
                    timestamp=datetime.now()
                ))
            
            return decoys
    
    def generate_similar(
        self,
        events: List[AccessEvent],
        n: int = 5,
        noise_scale: float = 0.5
    ) -> List[GeneratedPattern]:
        """
        Generate patterns similar to a given real pattern.
        
        Args:
            events: Real access events to mimic
            n: Number of similar patterns to generate
            noise_scale: How different from original (lower = more similar)
            
        Returns:
            List of GeneratedPattern objects similar to input
        """
        if not self.is_trained:
            raise RuntimeError("Model not trained. Call train() first.")
        
        with self._lock:
            # Extract features from real events
            features = self.feature_extractor.extract(events)
            feature_array = np.array([features[name] for name in self.FEATURE_NAMES])
            feature_array = feature_array.reshape(1, -1)
            
            # Scale
            feature_scaled = self.scaler.transform(feature_array)
            
            # Encode to latent space
            z_mean, z_log_var, z = self.encoder.predict(feature_scaled, verbose=0)
            
            # Generate variations in latent space
            variations = []
            for _ in range(n):
                # Add noise to latent representation
                noise = np.random.randn(1, self.config.latent_dim) * noise_scale
                z_varied = z + noise
                
                # Decode
                decoded = self.decoder.predict(z_varied, verbose=0)
                features_unscaled = self.scaler.inverse_transform(decoded)
                
                feature_dict = {
                    name: float(features_unscaled[0, j])
                    for j, name in enumerate(self.FEATURE_NAMES)
                }
                
                # Compute reconstruction loss vs original
                recon_loss = float(np.mean((feature_scaled - decoded) ** 2))
                
                variations.append(GeneratedPattern(
                    features=feature_dict,
                    latent_code=z_varied[0],
                    reconstruction_loss=recon_loss,
                    timestamp=datetime.now()
                ))
            
            return variations
    
    def interpolate(
        self,
        events_a: List[AccessEvent],
        events_b: List[AccessEvent],
        steps: int = 10
    ) -> List[GeneratedPattern]:
        """
        Generate patterns interpolating between two real patterns.
        
        Useful for understanding the latent space and generating
        transitions between different access behaviors.
        
        Args:
            events_a: First access pattern
            events_b: Second access pattern
            steps: Number of interpolation steps
            
        Returns:
            List of GeneratedPattern objects from A to B
        """
        if not self.is_trained:
            raise RuntimeError("Model not trained. Call train() first.")
        
        with self._lock:
            # Encode both patterns
            features_a = self.feature_extractor.extract(events_a)
            features_b = self.feature_extractor.extract(events_b)
            
            array_a = np.array([features_a[name] for name in self.FEATURE_NAMES]).reshape(1, -1)
            array_b = np.array([features_b[name] for name in self.FEATURE_NAMES]).reshape(1, -1)
            
            scaled_a = self.scaler.transform(array_a)
            scaled_b = self.scaler.transform(array_b)
            
            _, _, z_a = self.encoder.predict(scaled_a, verbose=0)
            _, _, z_b = self.encoder.predict(scaled_b, verbose=0)
            
            # Linear interpolation in latent space
            interpolations = []
            for i in range(steps):
                t = i / (steps - 1)  # 0 to 1
                z_interp = (1 - t) * z_a + t * z_b
                
                # Decode
                decoded = self.decoder.predict(z_interp, verbose=0)
                features_unscaled = self.scaler.inverse_transform(decoded)
                
                feature_dict = {
                    name: float(features_unscaled[0, j])
                    for j, name in enumerate(self.FEATURE_NAMES)
                }
                
                interpolations.append(GeneratedPattern(
                    features=feature_dict,
                    latent_code=z_interp[0],
                    reconstruction_loss=0.0,  # N/A for interpolation
                    timestamp=datetime.now()
                ))
            
            return interpolations
    
    def anomaly_score(self, events: List[AccessEvent]) -> float:
        """
        Compute anomaly score based on reconstruction error.
        
        Higher score = more anomalous (pattern not well represented
        by the learned distribution).
        
        Args:
            events: Access events to score
            
        Returns:
            Anomaly score (reconstruction error)
        """
        if not self.is_trained:
            raise RuntimeError("Model not trained. Call train() first.")
        
        with self._lock:
            features = self.feature_extractor.extract(events)
            feature_array = np.array([features[name] for name in self.FEATURE_NAMES])
            feature_array = feature_array.reshape(1, -1)
            
            # Scale and reconstruct
            feature_scaled = self.scaler.transform(feature_array)
            reconstructed = self.vae.predict(feature_scaled, verbose=0)
            
            # Reconstruction error as anomaly score
            error = float(np.mean((feature_scaled - reconstructed) ** 2))
            
            return error
    
    def get_latent_representation(self, events: List[AccessEvent]) -> np.ndarray:
        """
        Get latent space representation of access pattern.
        
        Useful for:
        - Clustering patterns
        - Visualization (t-SNE, UMAP)
        - Pattern comparison
        
        Args:
            events: Access events
            
        Returns:
            Latent code (numpy array of shape (latent_dim,))
        """
        if not self.is_trained:
            raise RuntimeError("Model not trained. Call train() first.")
        
        with self._lock:
            features = self.feature_extractor.extract(events)
            feature_array = np.array([features[name] for name in self.FEATURE_NAMES])
            feature_array = feature_array.reshape(1, -1)
            
            feature_scaled = self.scaler.transform(feature_array)
            _, _, z = self.encoder.predict(feature_scaled, verbose=0)
            
            return z[0]
    
    def save(self):
        """Save model to disk."""
        with self._lock:
            if self.encoder is not None:
                self.encoder.save(self.encoder_path)
            if self.decoder is not None:
                self.decoder.save(self.decoder_path)
            
            # Save config
            config_dict = {
                'latent_dim': self.config.latent_dim,
                'encoder_units': self.config.encoder_units,
                'decoder_units': self.config.decoder_units,
                'beta': self.config.beta,
                'learning_rate': self.config.learning_rate,
                'is_trained': self.is_trained,
            }
            with open(self.config_path, 'w') as f:
                json.dump(config_dict, f, indent=2)
            
            # Save scaler
            if self.scaler is not None:
                with open(self.scaler_path, 'wb') as f:
                    pickle.dump(self.scaler, f)
    
    def load(self):
        """Load model from disk."""
        with self._lock:
            # Load config
            if self.config_path.exists():
                with open(self.config_path, 'r') as f:
                    config_dict = json.load(f)
                self.config.latent_dim = config_dict.get('latent_dim', 8)
                self.config.encoder_units = config_dict.get('encoder_units', [64, 32])
                self.config.decoder_units = config_dict.get('decoder_units', [32, 64])
                self.config.beta = config_dict.get('beta', 0.1)
                self.is_trained = config_dict.get('is_trained', False)
            
            # Load models
            if self.encoder_path.exists():
                self.encoder = keras.models.load_model(
                    self.encoder_path, 
                    custom_objects={'Sampling': Sampling}
                )
            if self.decoder_path.exists():
                self.decoder = keras.models.load_model(self.decoder_path)
            
            # Load scaler
            if self.scaler_path.exists():
                with open(self.scaler_path, 'rb') as f:
                    self.scaler = pickle.load(f)
    
    def summary(self) -> str:
        """Get model summary string."""
        lines = [
            "=" * 60,
            "PATTERN OBFUSCATION VAE SUMMARY",
            "=" * 60,
            f"Trained: {self.is_trained}",
            f"Latent Dimensions: {self.config.latent_dim}",
            f"Encoder Units: {self.config.encoder_units}",
            f"Decoder Units: {self.config.decoder_units}",
            f"β (KL weight): {self.config.beta}",
            f"Model Directory: {self.model_dir}",
            "=" * 60,
        ]
        
        if self.encoder is not None:
            lines.append("\nENCODER:")
            self.encoder.summary(print_fn=lambda x: lines.append(x))
        
        if self.decoder is not None:
            lines.append("\nDECODER:")
            self.decoder.summary(print_fn=lambda x: lines.append(x))
        
        return '\n'.join(lines)


# ============================================================================
# CONVENIENCE FUNCTIONS
# ============================================================================

def create_pattern_vae(
    vault_path: Path,
    latent_dim: int = 8,
    beta: float = 0.1
) -> PatternObfuscationVAE:
    """
    Create a Pattern Obfuscation VAE with recommended settings.
    
    Args:
        vault_path: Path to vault directory
        latent_dim: Latent space dimensionality (default: 8)
        beta: KL divergence weight (default: 0.1)
        
    Returns:
        Configured PatternObfuscationVAE instance
    """
    config = VAEConfig(
        latent_dim=latent_dim,
        beta=beta,
        encoder_units=[64, 32],
        decoder_units=[32, 64],
        learning_rate=0.001,
        epochs=100,
        dropout_rate=0.2
    )
    
    return PatternObfuscationVAE(vault_path, config)


def generate_decoy_events(
    vae: PatternObfuscationVAE,
    base_events: List[AccessEvent],
    n_decoys: int = 50
) -> List[List[Dict[str, float]]]:
    """
    Generate decoy event patterns to mix with real events.
    
    Args:
        vae: Trained PatternObfuscationVAE
        base_events: Real events to base decoys on
        n_decoys: Number of decoy patterns to generate
        
    Returns:
        List of decoy feature dictionaries
    """
    # Generate some similar to base, some random
    similar_count = n_decoys // 2
    random_count = n_decoys - similar_count
    
    similar_decoys = vae.generate_similar(base_events, n=similar_count, noise_scale=0.3)
    random_decoys = vae.generate_decoys(n=random_count, noise_scale=1.0)
    
    all_decoys = similar_decoys + random_decoys
    
    return [decoy.features for decoy in all_decoys]


if __name__ == '__main__':
    print("Pattern Obfuscation VAE Module")
    print("=" * 40)
    print("Use create_pattern_vae() to create a new VAE")
    print("Train with vae.train(events_list)")
    print("Generate decoys with vae.generate_decoys(n)")
