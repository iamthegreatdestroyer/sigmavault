"""
Dilithium Digital Signature Scheme (ML-DSA)
============================================

NIST-standardized post-quantum digital signature algorithm for authentication.

Dilithium is a lattice-based digital signature algorithm selected by NIST as
the standardized post-quantum algorithm for digital signatures. It provides
security against attacks by large-scale quantum computers while maintaining
classical computational efficiency.

Architecture:
┌──────────────────────────────────────────────┐
│        DILITHIUM DIGITAL SIGNATURE            │
├──────────────────────────────────────────────┤
│                                              │
│  Key Generation                              │
│  ├─ Seed generation                          │
│  ├─ Expand to secret key (s₁, s₂)            │
│  ├─ Compute public key (t)                   │
│  └─ Return (sk, pk) pair                     │
│                                              │
│  Signing (Message + Secret Key → Signature)  │
│  ├─ Compute challenge                        │
│  ├─ Rejection sampling loop                  │
│  ├─ Generate z (commitment)                  │
│  ├─ Compute response c·s₁ + y                │
│  └─ Return signature σ                       │
│                                              │
│  Verification (Message + Public Key → Bool)  │
│  ├─ Decompose signature                      │
│  ├─ Compute w = [A^T · z - c·t]₂            │
│  ├─ Check signature bounds                   │
│  └─ Return True if valid, False otherwise    │
│                                              │
└──────────────────────────────────────────────┘

Security Levels:
├─ Dilithium2:  ≈ NIST PQC Level 2 (SHA-256)
├─ Dilithium3:  ≈ NIST PQC Level 3 (SHA-256)  [Default]
└─ Dilithium5:  ≈ NIST PQC Level 5 (SHA-256)

Cryptographic Properties:
├─ EUF-CMA secure (Existentially Unforgeable)
├─ Resistant to quantum attacks
├─ Lattice-based hardness assumption (MLWE/MSIS)
├─ Deterministic signing (with seed)
└─ No randomness required (security from rejection sampling)

Copyright (c) 2026 ΣVAULT. All Rights Reserved.
Agents: @FORTRESS @TENSOR @SENTRY
"""

import os
import time
from dataclasses import dataclass, field
from typing import Tuple, Optional, Dict, Any
from enum import Enum
import threading

try:
    from liboqs.oqs import Signature
    HAS_LIBOQS = True
except (ImportError, RuntimeError):
    HAS_LIBOQS = False
    Signature = None

try:
    from pqcrypto.sign import ml_dsa_44, ml_dsa_65, ml_dsa_87
    HAS_PQCRYPTO = True
except ImportError:
    HAS_PQCRYPTO = False
    ml_dsa_44 = None
    ml_dsa_65 = None
    ml_dsa_87 = None

_PQCRYPTO_DSA_MAP = {}
if HAS_PQCRYPTO:
    _PQCRYPTO_DSA_MAP = {
        "Dilithium2": ml_dsa_44,
        "Dilithium3": ml_dsa_65,
        "Dilithium5": ml_dsa_87,
    }


class DilithiumSecurityLevel(Enum):
    """Dilithium security levels matching NIST PQC categories."""
    LEVEL2 = "Dilithium2"    # ≈ SHA-256 (smaller, faster)
    LEVEL3 = "Dilithium3"    # ≈ SHA-256 (balanced, default)
    LEVEL5 = "Dilithium5"    # ≈ SHA-256 (larger, slower)


class SignatureStatus(Enum):
    """Signature operation status."""
    VALID = "valid"
    INVALID = "invalid"
    VERIFICATION_FAILED = "verification_failed"
    INVALID_KEY = "invalid_key"


@dataclass
class DilithiumPublicKey:
    """
    Dilithium public key for signature verification.

    Attributes:
        algorithm: Algorithm identifier
        security_level: Dilithium security level
        key_data: Raw public key bytes
        timestamp: When key was generated
        metadata: Additional key metadata
    """
    algorithm: str = "Dilithium"
    security_level: DilithiumSecurityLevel = DilithiumSecurityLevel.LEVEL3
    key_data: bytes = field(default_factory=bytes)
    timestamp: float = field(default_factory=time.time)
    metadata: Dict[str, Any] = field(default_factory=dict)

    def __len__(self) -> int:
        """Get key size in bytes."""
        return len(self.key_data)

    def to_bytes(self) -> bytes:
        """Serialize public key to bytes."""
        return self.key_data

    @classmethod
    def from_bytes(cls, data: bytes, security_level: DilithiumSecurityLevel) -> 'DilithiumPublicKey':
        """Deserialize public key from bytes."""
        return cls(key_data=data, security_level=security_level)


@dataclass
class DilithiumSecretKey:
    """
    Dilithium secret key for signing.

    Attributes:
        algorithm: Algorithm identifier
        security_level: Dilithium security level
        key_data: Raw secret key bytes
        public_key: Associated public key
        timestamp: When key was generated
        metadata: Additional key metadata
    """
    algorithm: str = "Dilithium"
    security_level: DilithiumSecurityLevel = DilithiumSecurityLevel.LEVEL3
    key_data: bytes = field(default_factory=bytes)
    public_key: Optional[DilithiumPublicKey] = None
    timestamp: float = field(default_factory=time.time)
    metadata: Dict[str, Any] = field(default_factory=dict)

    def __len__(self) -> int:
        """Get key size in bytes."""
        return len(self.key_data)

    def to_bytes(self) -> bytes:
        """Serialize secret key to bytes."""
        return self.key_data


@dataclass
class DilithiumSignature:
    """
    Dilithium digital signature.

    Attributes:
        signature: Raw signature bytes
        security_level: Dilithium security level used
        algorithm: Algorithm identifier
        timestamp: When signature was created
        metadata: Additional metadata
    """
    signature: bytes = field(default_factory=bytes)
    security_level: DilithiumSecurityLevel = DilithiumSecurityLevel.LEVEL3
    algorithm: str = "Dilithium"
    timestamp: float = field(default_factory=time.time)
    metadata: Dict[str, Any] = field(default_factory=dict)

    def __len__(self) -> int:
        """Get signature size in bytes."""
        return len(self.signature)

    def to_bytes(self) -> bytes:
        """Serialize to bytes."""
        return self.signature

    @classmethod
    def from_bytes(cls, data: bytes, security_level: DilithiumSecurityLevel) -> 'DilithiumSignature':
        """Deserialize signature from bytes."""
        return cls(signature=data, security_level=security_level)


class DilithiumSignatureScheme:
    """
    Dilithium Digital Signature Scheme (ML-DSA).

    Provides NIST-standardized post-quantum digital signatures for authentication
    and non-repudiation.

    Example:
        >>> dil = DilithiumSignatureScheme(security_level=DilithiumSecurityLevel.LEVEL3)
        >>>
        >>> # Generate keypair
        >>> public_key, secret_key = dil.generate_keypair()
        >>> print(f"Public key size: {len(public_key)} bytes")
        >>>
        >>> # Sign message
        >>> message = b"Important message to authenticate"
        >>> signature = dil.sign(message, secret_key)
        >>> print(f"Signature size: {len(signature)} bytes")
        >>>
        >>> # Verify signature
        >>> is_valid = dil.verify(message, signature, public_key)
        >>> assert is_valid
        >>>
        >>> # Attempt forgery (should fail)
        >>> forged_message = b"Forged message"
        >>> is_valid = dil.verify(forged_message, signature, public_key)
        >>> assert not is_valid
    """

    # Signature/key sizes for each security level
    DILITHIUM_SIZES = {
        DilithiumSecurityLevel.LEVEL2: {"pk": 1312, "sk": 2544, "sig": 2420},
        DilithiumSecurityLevel.LEVEL3: {"pk": 1952, "sk": 4000, "sig": 3293},
        DilithiumSecurityLevel.LEVEL5: {"pk": 2592, "sk": 4864, "sig": 4595},
    }

    def __init__(self, security_level: DilithiumSecurityLevel = DilithiumSecurityLevel.LEVEL3):
        """
        Initialize Dilithium Signature Scheme.

        Args:
            security_level: Dilithium security level (LEVEL2, LEVEL3, LEVEL5)

        Raises:
            ImportError: If liboqs is not installed
            ValueError: If security level is invalid
        """
        if not HAS_LIBOQS and not HAS_PQCRYPTO:
            raise ImportError(
                "Either liboqs-python or pqcrypto is required for Dilithium. "
                "Install with: pip install pqcrypto"
            )

        if not isinstance(security_level, DilithiumSecurityLevel):
            raise ValueError(f"Invalid security level: {security_level}")

        self.security_level = security_level
        self.algorithm_name = security_level.value
        self._lock = threading.RLock()
        self._operations_count = 0
        self._failed_verifications = 0

    def generate_keypair(self) -> Tuple[DilithiumPublicKey, DilithiumSecretKey]:
        """
        Generate a new Dilithium keypair.

        Returns:
            Tuple of (public_key, secret_key)

        Raises:
            RuntimeError: If key generation fails
        """
        with self._lock:
            try:
                if HAS_LIBOQS:
                    sig = Signature(self.algorithm_name)
                    public_key_bytes = sig.generate_keys()
                    secret_key_bytes = sig.export_secret_key()
                else:
                    dsa_mod = _PQCRYPTO_DSA_MAP[self.algorithm_name]
                    public_key_bytes, secret_key_bytes = dsa_mod.generate_keypair()

                if not public_key_bytes or not secret_key_bytes:
                    raise RuntimeError("Key generation produced empty keys")

                public_key = DilithiumPublicKey(
                    security_level=self.security_level,
                    key_data=bytes(public_key_bytes),
                    metadata={"algorithm": self.algorithm_name}
                )

                secret_key = DilithiumSecretKey(
                    security_level=self.security_level,
                    key_data=bytes(secret_key_bytes),
                    public_key=public_key,
                    metadata={"algorithm": self.algorithm_name}
                )

                self._operations_count += 1
                return public_key, secret_key

            except Exception as e:
                raise RuntimeError(f"Dilithium key generation failed: {e}")

    def sign(self, message: bytes, secret_key: DilithiumSecretKey) -> DilithiumSignature:
        """
        Sign a message with the secret key.

        Args:
            message: Message to sign
            secret_key: Dilithium secret key

        Returns:
            Digital signature

        Raises:
            ValueError: If secret key is invalid
            RuntimeError: If signing fails
        """
        with self._lock:
            if not isinstance(secret_key, DilithiumSecretKey):
                raise ValueError("Invalid secret key type")

            if secret_key.security_level != self.security_level:
                raise ValueError(
                    f"Secret key security level {secret_key.security_level} "
                    f"does not match {self.security_level}"
                )

            if not isinstance(message, bytes):
                raise ValueError("Message must be bytes")

            try:
                if HAS_LIBOQS:
                    sig = Signature(self.algorithm_name)
                    sig.import_secret_key(secret_key.key_data)
                    signature_bytes = sig.sign(message)
                else:
                    dsa_mod = _PQCRYPTO_DSA_MAP[self.algorithm_name]
                    signature_bytes = dsa_mod.sign(secret_key.key_data, message)

                if not signature_bytes:
                    raise RuntimeError("Signature operation produced empty signature")

                signature = DilithiumSignature(
                    signature=bytes(signature_bytes),
                    security_level=self.security_level,
                    metadata={
                        "algorithm": self.algorithm_name,
                        "message_length": len(message),
                        "timestamp": time.time()
                    }
                )

                self._operations_count += 1
                return signature

            except Exception as e:
                raise RuntimeError(f"Dilithium signing failed: {e}")

    def verify(
        self,
        message: bytes,
        signature: DilithiumSignature,
        public_key: DilithiumPublicKey
    ) -> bool:
        """
        Verify a signature on a message with the public key.

        Args:
            message: Original message
            signature: Signature to verify
            public_key: Dilithium public key

        Returns:
            True if signature is valid, False otherwise

        Raises:
            ValueError: If inputs are invalid
        """
        with self._lock:
            if not isinstance(public_key, DilithiumPublicKey):
                raise ValueError("Invalid public key type")

            if not isinstance(signature, DilithiumSignature):
                raise ValueError("Invalid signature type")

            if not isinstance(message, bytes):
                raise ValueError("Message must be bytes")

            if public_key.security_level != self.security_level:
                raise ValueError(
                    f"Public key security level {public_key.security_level} "
                    f"does not match {self.security_level}"
                )

            try:
                if HAS_LIBOQS:
                    sig = Signature(self.algorithm_name)
                    sig.import_public_key(public_key.key_data)
                    is_valid = sig.verify(message, signature.signature)
                else:
                    dsa_mod = _PQCRYPTO_DSA_MAP[self.algorithm_name]
                    try:
                        result = dsa_mod.verify(
                            public_key.key_data, message, signature.signature
                        )
                        is_valid = bool(result)
                    except Exception:
                        is_valid = False

                if not is_valid:
                    self._failed_verifications += 1

                self._operations_count += 1
                return bool(is_valid)

            except Exception:
                self._failed_verifications += 1
                self._operations_count += 1
                return False

    def get_statistics(self) -> Dict[str, Any]:
        """
        Get signature scheme statistics.

        Returns:
            Dictionary with operation counts and sizes
        """
        with self._lock:
            sizes = self.DILITHIUM_SIZES[self.security_level]
            return {
                "algorithm": self.algorithm_name,
                "security_level": self.security_level.value,
                "operations": self._operations_count,
                "failed_verifications": self._failed_verifications,
                "public_key_size": sizes["pk"],
                "secret_key_size": sizes["sk"],
                "signature_size": sizes["sig"],
                "total_key_size": sizes["pk"] + sizes["sk"],
            }


def create_dilithium_signer(
    security_level: DilithiumSecurityLevel = DilithiumSecurityLevel.LEVEL3,
) -> DilithiumSignatureScheme:
    """
    Create a Dilithium signature scheme instance with recommended settings.

    Args:
        security_level: Desired security level (default LEVEL3)

    Returns:
        Configured DilithiumSignatureScheme instance
    """
    return DilithiumSignatureScheme(security_level=security_level)
