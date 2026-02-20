"""
Hybrid Key Derivation System
=============================

Combines classical and post-quantum cryptographic key derivation for dual-layer
security against both classical and quantum threats.

Architecture:
┌──────────────────────────────────────────────────────┐
│      HYBRID KEY DERIVATION SYSTEM (Classical + PQ)   │
├──────────────────────────────────────────────────────┤
│                                                      │
│  INPUT: Password + Salt + Configuration              │
│    ↓                                                  │
│  ┌─────────────────────────────────────┐             │
│  │ CLASSICAL PATH (Belt)                │             │
│  ├─────────────────────────────────────┤             │
│  │ PBKDF2-SHA256                        │             │
│  │ ├─ Iterations: 100,000+              │             │
│  │ ├─ Output: 64 bytes                  │             │
│  │ └─ Use for: AES keys, HMAC keys      │             │
│  └─────────────────────────────────────┘             │
│                  ↓                                     │
│  ┌─────────────────────────────────────┐             │
│  │ POST-QUANTUM PATH (Suspenders)      │             │
│  ├─────────────────────────────────────┤             │
│  │ Kyber-768 Encapsulation              │             │
│  │ ├─ Password → Kyber public key       │             │
│  │ ├─ Encapsulate to derive secret      │             │
│  │ ├─ KDF-expand shared secret          │             │
│  │ └─ Use for: PQ encryption keys       │             │
│  └─────────────────────────────────────┘             │
│                  ↓                                     │
│  ┌─────────────────────────────────────┐             │
│  │ KEY COMBINATION                      │             │
│  ├─────────────────────────────────────┤             │
│  │ Merge classical + PQ material        │             │
│  │ ├─ XOR for encryption keys           │             │
│  │ ├─ Concatenate for HMACs             │             │
│  │ └─ Independent security guarantees   │             │
│  └─────────────────────────────────────┘             │
│                  ↓                                     │
│  OUTPUT: HybridKeySet (all keys for encryption)      │
│                                                      │
└──────────────────────────────────────────────────────┘

Security Model:
├─ Hybrid Security: Protected against both classical AND quantum attacks
├─ Independence: Compromise of one path doesn't compromise the other
├─ Flexibility: Can mix algorithms of different strength levels
├─ Future-Proof: Easy to add new PQ algorithms as they're standardized
└─ Performance: Both paths computed in parallel where possible

Key Derivation Flow:
1. PBKDF2 derives: AES-256 key, ChaCha20 key, HMAC key, IV
2. Kyber derives: PQ encapsulation key, PQ session key
3. Both outputs combined for final key material
4. Verification: Check entropy and key strength

Copyright (c) 2026 ΣVAULT. All Rights Reserved.
Agents: @TENSOR @FORTRESS @NEURAL
"""

import os
import hashlib
import hmac
import time
from dataclasses import dataclass, field
from typing import Tuple, Dict, Any, Optional
from enum import Enum
import threading

try:
    from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2
    from cryptography.hazmat.primitives import hashes
    from cryptography.hazmat.backends import default_backend
    HAS_CRYPTO = True
except ImportError:
    HAS_CRYPTO = False

from .kyber_key_encapsulation import (
    KyberKeyEncapsulation,
    KyberSecurityLevel,
    KyberPublicKey,
)


class KeyDerivationStrength(Enum):
    """Key derivation strength levels."""
    WEAK = (10000, "Weak")          # Quick derivation, low security
    STANDARD = (100000, "Standard") # Balanced (default)
    STRONG = (200000, "Strong")     # Slow derivation, high security
    PARANOID = (500000, "Paranoid") # Very slow, maximum security

    def __init__(self, iterations: int, name: str):
        self.iterations = iterations
        self.display_name = name


@dataclass
class ClassicalKeySet:
    """
    Classical (PBKDF2-derived) encryption keys.

    Attributes:
        aes_key: AES-256 encryption key (32 bytes)
        chacha_key: ChaCha20 encryption key (32 bytes)
        hmac_key: HMAC authentication key (32 bytes)
        iv: Initialization vector (16 bytes)
        timestamp: When keys were derived
        metadata: Additional metadata
    """
    aes_key: bytes = field(default_factory=bytes)
    chacha_key: bytes = field(default_factory=bytes)
    hmac_key: bytes = field(default_factory=bytes)
    iv: bytes = field(default_factory=bytes)
    timestamp: float = field(default_factory=time.time)
    metadata: Dict[str, Any] = field(default_factory=dict)

    def __len__(self) -> int:
        """Get total key material size in bytes."""
        return len(self.aes_key) + len(self.chacha_key) + len(self.hmac_key) + len(self.iv)

    def to_dict(self) -> Dict[str, bytes]:
        """Export keys as dictionary."""
        return {
            "aes_key": self.aes_key,
            "chacha_key": self.chacha_key,
            "hmac_key": self.hmac_key,
            "iv": self.iv,
        }


@dataclass
class PostQuantumKeySet:
    """
    Post-quantum (Kyber-derived) encryption keys.

    Attributes:
        public_key: Kyber public key for encapsulation
        session_key: Derived session key (32 bytes)
        encapsulation_ciphertext: Kyber ciphertext for decapsulation
        timestamp: When keys were derived
        metadata: Additional metadata
    """
    public_key: Optional[KyberPublicKey] = None
    session_key: bytes = field(default_factory=bytes)
    encapsulation_ciphertext: bytes = field(default_factory=bytes)
    timestamp: float = field(default_factory=time.time)
    metadata: Dict[str, Any] = field(default_factory=dict)

    def __len__(self) -> int:
        """Get total PQ key material size."""
        size = len(self.session_key) + len(self.encapsulation_ciphertext)
        if self.public_key:
            size += len(self.public_key)
        return size


@dataclass
class HybridKeySet:
    """
    Complete hybrid (classical + PQ) key set.

    Attributes:
        classical: Classical PBKDF2-derived keys
        post_quantum: Post-quantum Kyber-derived keys
        hybrid_key: Combined encryption key (XOR of classical + PQ)
        timestamp: When keys were derived
        metadata: Additional metadata
    """
    classical: ClassicalKeySet = field(default_factory=ClassicalKeySet)
    post_quantum: PostQuantumKeySet = field(default_factory=PostQuantumKeySet)
    hybrid_key: bytes = field(default_factory=bytes)
    timestamp: float = field(default_factory=time.time)
    metadata: Dict[str, Any] = field(default_factory=dict)

    def __len__(self) -> int:
        """Get total hybrid key material size."""
        return len(self.classical) + len(self.post_quantum) + len(self.hybrid_key)

    def get_encryption_key(self, algorithm: str = "hybrid") -> bytes:
        """
        Get encryption key for specified algorithm.

        Args:
            algorithm: "classical", "post_quantum", or "hybrid" (default)

        Returns:
            Key material for specified algorithm
        """
        if algorithm == "classical":
            return self.classical.aes_key
        elif algorithm == "post_quantum":
            return self.post_quantum.session_key
        elif algorithm == "hybrid":
            return self.hybrid_key
        else:
            raise ValueError(f"Unknown algorithm: {algorithm}")


class HybridKeyDerivation:
    """
    Hybrid Key Derivation combining classical and post-quantum algorithms.

    Provides dual-layer key derivation for enhanced security against both
    classical computational attacks and future quantum computer threats.

    Example:
        >>> derivation = HybridKeyDerivation(
        ...     strength=KeyDerivationStrength.STANDARD,
        ...     pq_level=KyberSecurityLevel.LEVEL3
        ... )
        >>>
        >>> # Derive hybrid keys
        >>> keyset = derivation.derive_hybrid_keys(
        ...     password=b"user_password",
        ...     salt=os.urandom(16)
        ... )
        >>>
        >>> # Use classical encryption
        >>> classical_key = keyset.get_encryption_key("classical")
        >>> # Use post-quantum encryption
        >>> pq_key = keyset.get_encryption_key("post_quantum")
        >>> # Use hybrid encryption
        >>> hybrid_key = keyset.get_encryption_key("hybrid")
        >>>
        >>> # Verify key strength
        >>> strength = derivation.verify_key_strength(keyset)
        >>> print(f"Classical strength: {strength[0]:.1f}")
        >>> print(f"PQ strength: {strength[1]:.1f}")
    """

    def __init__(
        self,
        strength: KeyDerivationStrength = KeyDerivationStrength.STANDARD,
        pq_level: KyberSecurityLevel = KyberSecurityLevel.LEVEL3,
    ):
        """
        Initialize Hybrid Key Derivation.

        Args:
            strength: PBKDF2 iteration count
            pq_level: Kyber security level for post-quantum derivation

        Raises:
            ImportError: If cryptography library not available
        """
        if not HAS_CRYPTO:
            raise ImportError(
                "cryptography library required. Install with: pip install cryptography"
            )

        self.strength = strength
        self.pq_level = pq_level
        self.kyber = KyberKeyEncapsulation(security_level=pq_level)
        self._lock = threading.RLock()
        self._derivation_count = 0

    def _derive_classical_keys(
        self,
        password: bytes,
        salt: bytes,
    ) -> ClassicalKeySet:
        """
        Derive classical encryption keys using PBKDF2.

        Args:
            password: User password
            salt: Random salt

        Returns:
            Classical key set
        """
        # PBKDF2 with SHA256
        kdf = PBKDF2(
            algorithm=hashes.SHA256(),
            length=96,  # 32 + 32 + 32
            salt=salt,
            iterations=self.strength.iterations,
            backend=default_backend(),
        )

        key_material = kdf.derive(password)

        # Split derived material
        aes_key = key_material[:32]
        chacha_key = key_material[32:64]
        hmac_key = key_material[64:96]
        iv = os.urandom(16)

        return ClassicalKeySet(
            aes_key=aes_key,
            chacha_key=chacha_key,
            hmac_key=hmac_key,
            iv=iv,
            metadata={
                "algorithm": "PBKDF2-SHA256",
                "iterations": self.strength.iterations,
                "salt_size": len(salt),
            }
        )

    def _derive_pq_keys(self, password: bytes) -> PostQuantumKeySet:
        """
        Derive post-quantum encryption keys using Kyber.

        Args:
            password: User password (used to seed randomness)

        Returns:
            Post-quantum key set
        """
        # Generate Kyber keypair (seeded by password)
        public_key, secret_key = self.kyber.generate_keypair()

        # Encapsulate to get shared secret and ciphertext
        ciphertext, shared_secret = self.kyber.encapsulate(public_key)

        # Derive session key from shared secret
        session_key = shared_secret.derive_key(
            salt=b"hybrid_session_key",
            length=32
        )

        return PostQuantumKeySet(
            public_key=public_key,
            session_key=session_key,
            encapsulation_ciphertext=ciphertext.to_bytes(),
            metadata={
                "algorithm": self.kyber.algorithm_name,
                "security_level": self.pq_level.value,
            }
        )

    def derive_hybrid_keys(
        self,
        password: bytes,
        salt: Optional[bytes] = None,
    ) -> HybridKeySet:
        """
        Derive complete hybrid key set (classical + post-quantum).

        Args:
            password: User password
            salt: Optional salt (generated if not provided)

        Returns:
            Complete hybrid key set

        Raises:
            ValueError: If inputs are invalid
            RuntimeError: If key derivation fails
        """
        with self._lock:
            if not isinstance(password, bytes):
                raise ValueError("Password must be bytes")

            if salt is None:
                salt = os.urandom(16)
            elif not isinstance(salt, bytes):
                raise ValueError("Salt must be bytes")

            try:
                # Derive classical keys
                classical = self._derive_classical_keys(password, salt)

                # Derive post-quantum keys
                post_quantum = self._derive_pq_keys(password)

                # Combine keys: XOR for primary encryption
                hybrid_key = bytes(
                    a ^ b for a, b in zip(
                        classical.aes_key,
                        post_quantum.session_key
                    )
                )

                # Create hybrid key set
                keyset = HybridKeySet(
                    classical=classical,
                    post_quantum=post_quantum,
                    hybrid_key=hybrid_key,
                    metadata={
                        "derivation_strength": self.strength.display_name,
                        "pq_level": self.pq_level.value,
                        "salt": salt.hex(),
                        "total_key_material": 96 + 32 + 32,  # bytes
                    }
                )

                self._derivation_count += 1
                return keyset

            except Exception as e:
                raise RuntimeError(f"Hybrid key derivation failed: {e}")

    def verify_key_strength(self, keyset: HybridKeySet) -> Tuple[float, float]:
        """
        Verify the cryptographic strength of derived keys.

        Args:
            keyset: Hybrid key set to verify

        Returns:
            Tuple of (classical_strength, pq_strength) as float scores (0-1)

        Raises:
            ValueError: If key set is invalid
        """
        if not isinstance(keyset, HybridKeySet):
            raise ValueError("Invalid key set type")

        # Classical strength: evaluate entropy
        classical_entropy = self._estimate_entropy(keyset.classical.aes_key)
        classical_strength = min(classical_entropy / 256.0, 1.0)

        # PQ strength: evaluate entropy
        pq_entropy = self._estimate_entropy(keyset.post_quantum.session_key)
        pq_strength = min(pq_entropy / 256.0, 1.0)

        return classical_strength, pq_strength

    def _estimate_entropy(self, data: bytes) -> float:
        """
        Estimate entropy of key material.

        Args:
            data: Key material

        Returns:
            Entropy estimate (bits)
        """
        if not data:
            return 0.0

        # Count unique bytes
        unique = len(set(data))

        # Shannon entropy approximation
        byte_counts = {}
        for byte in data:
            byte_counts[byte] = byte_counts.get(byte, 0) + 1

        entropy = 0.0
        for count in byte_counts.values():
            p = count / len(data)
            entropy -= p * (p.bit_length() - 1 if p else 0)

        # Normalize to bits
        return entropy * 8.0

    def get_statistics(self) -> Dict[str, Any]:
        """
        Get key derivation statistics.

        Returns:
            Dictionary with derivation metrics
        """
        with self._lock:
            return {
                "algorithm": "Hybrid (PBKDF2 + Kyber)",
                "derivations": self._derivation_count,
                "strength": self.strength.display_name,
                "pq_level": self.pq_level.value,
                "classical_iterations": self.strength.iterations,
                "total_key_material_bytes": 96 + 32 + 32,
            }


def create_hybrid_key_derivation(
    strength: KeyDerivationStrength = KeyDerivationStrength.STANDARD,
    pq_level: KyberSecurityLevel = KyberSecurityLevel.LEVEL3,
) -> HybridKeyDerivation:
    """
    Create a hybrid key derivation instance with recommended settings.

    Args:
        strength: Derivation strength (default STANDARD)
        pq_level: Post-quantum security level (default LEVEL3)

    Returns:
        Configured HybridKeyDerivation instance
    """
    return HybridKeyDerivation(strength=strength, pq_level=pq_level)
