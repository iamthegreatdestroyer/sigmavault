"""
Kyber Key Encapsulation Mechanism (ML-KEM)
===========================================

NIST-standardized post-quantum key encapsulation mechanism for hybrid encryption.

Kyber is a lattice-based key encapsulation mechanism selected by NIST as the
standardized post-quantum algorithm for key establishment. It provides security
against attacks by large-scale quantum computers while maintaining classical
computational efficiency.

Architecture:
┌──────────────────────────────────────────────┐
│         KYBER KEY ENCAPSULATION              │
├──────────────────────────────────────────────┤
│                                              │
│  Key Generation                              │
│  ├─ Secret key generation (s, e)             │
│  ├─ Public key computation (A·s + e)         │
│  └─ CPA-secure public key                    │
│                                              │
│  Encapsulation (Public Key → Shared Secret)  │
│  ├─ Generate ephemeral (m)                   │
│  ├─ Encrypt to public key                    │
│  ├─ Derive shared secret (K)                 │
│  └─ Return ciphertext (c) + shared secret    │
│                                              │
│  Decapsulation (Ciphertext → Shared Secret)  │
│  ├─ Decrypt ciphertext with secret key       │
│  ├─ Verify correctness                       │
│  ├─ Derive shared secret (K)                 │
│  └─ Handle failure gracefully                │
│                                              │
└──────────────────────────────────────────────┘

Security Levels:
├─ Kyber-512:  ≈ NIST PQC Level 1 (AES-128)
├─ Kyber-768:  ≈ NIST PQC Level 3 (AES-192)  [Default]
└─ Kyber-1024: ≈ NIST PQC Level 5 (AES-256)

Cryptographic Properties:
├─ IND-CCA2 secure
├─ Resistant to quantum attacks
├─ Lattice-based hardness assumption (LWE)
└─ Deterministic decryption (no decryption failures)

Copyright (c) 2026 ΣVAULT. All Rights Reserved.
Agents: @TENSOR @FORTRESS @NEURAL
"""

import os
import hashlib
import hmac
from dataclasses import dataclass, field
from typing import Tuple, Optional, Dict, Any
from enum import Enum
import threading

try:
    from liboqs.oqs import OQS_STATUS, KeyEncapsulation
    HAS_LIBOQS = True
except (ImportError, RuntimeError):
    HAS_LIBOQS = False
    KeyEncapsulation = None

try:
    from pqcrypto.kem import ml_kem_512, ml_kem_768, ml_kem_1024
    HAS_PQCRYPTO = True
except ImportError:
    HAS_PQCRYPTO = False
    ml_kem_512 = None
    ml_kem_768 = None
    ml_kem_1024 = None

_PQCRYPTO_KEM_MAP = {}
if HAS_PQCRYPTO:
    _PQCRYPTO_KEM_MAP = {
        "Kyber512": ml_kem_512,
        "Kyber768": ml_kem_768,
        "Kyber1024": ml_kem_1024,
    }


class KyberSecurityLevel(Enum):
    """Kyber security levels matching NIST PQC categories."""
    LEVEL1 = "Kyber512"    # ≈ AES-128 (smallest, fastest)
    LEVEL3 = "Kyber768"    # ≈ AES-192 (balanced, default)
    LEVEL5 = "Kyber1024"   # ≈ AES-256 (largest, slowest)


class KyberStatus(Enum):
    """Operation status indicators."""
    SUCCESS = "success"
    FAILURE = "failure"
    INVALID_KEY = "invalid_key"
    DECRYPTION_FAILURE = "decryption_failure"


@dataclass
class KyberPublicKey:
    """
    Kyber public key for encapsulation.

    Attributes:
        algorithm: Algorithm identifier
        security_level: Kyber security level
        key_data: Raw public key bytes
        timestamp: When key was generated
        metadata: Additional key metadata
    """
    algorithm: str = "Kyber"
    security_level: KyberSecurityLevel = KyberSecurityLevel.LEVEL3
    key_data: bytes = field(default_factory=bytes)
    timestamp: float = field(default_factory=lambda: __import__('time').time())
    metadata: Dict[str, Any] = field(default_factory=dict)

    def __len__(self) -> int:
        """Get key size in bytes."""
        return len(self.key_data)

    def to_bytes(self) -> bytes:
        """Serialize public key to bytes."""
        return self.key_data

    @classmethod
    def from_bytes(cls, data: bytes, security_level: KyberSecurityLevel) -> 'KyberPublicKey':
        """Deserialize public key from bytes."""
        return cls(key_data=data, security_level=security_level)


@dataclass
class KyberSecretKey:
    """
    Kyber secret key for decapsulation.

    Attributes:
        algorithm: Algorithm identifier
        security_level: Kyber security level
        key_data: Raw secret key bytes
        public_key: Associated public key
        timestamp: When key was generated
        metadata: Additional key metadata
    """
    algorithm: str = "Kyber"
    security_level: KyberSecurityLevel = KyberSecurityLevel.LEVEL3
    key_data: bytes = field(default_factory=bytes)
    public_key: Optional[KyberPublicKey] = None
    timestamp: float = field(default_factory=lambda: __import__('time').time())
    metadata: Dict[str, Any] = field(default_factory=dict)

    def __len__(self) -> int:
        """Get key size in bytes."""
        return len(self.key_data)

    def to_bytes(self) -> bytes:
        """Serialize secret key to bytes."""
        return self.key_data


@dataclass
class KyberCiphertext:
    """
    Kyber encapsulation ciphertext.

    Attributes:
        ciphertext: Raw ciphertext bytes
        security_level: Kyber security level used
        timestamp: When ciphertext was generated
    """
    ciphertext: bytes = field(default_factory=bytes)
    security_level: KyberSecurityLevel = KyberSecurityLevel.LEVEL3
    timestamp: float = field(default_factory=lambda: __import__('time').time())

    def __len__(self) -> int:
        """Get ciphertext size in bytes."""
        return len(self.ciphertext)

    def to_bytes(self) -> bytes:
        """Serialize to bytes."""
        return self.ciphertext


@dataclass
class SharedSecret:
    """
    Shared secret generated from encapsulation/decapsulation.

    Attributes:
        secret: Raw shared secret bytes (typically 32 bytes)
        timestamp: When secret was generated
        metadata: Additional metadata
    """
    secret: bytes = field(default_factory=bytes)
    timestamp: float = field(default_factory=lambda: __import__('time').time())
    metadata: Dict[str, Any] = field(default_factory=dict)

    def __len__(self) -> int:
        """Get secret size in bytes."""
        return len(self.secret)

    def to_bytes(self) -> bytes:
        """Get secret as bytes."""
        return self.secret

    def derive_key(self, salt: bytes = b'', info: bytes = b'', length: int = 32) -> bytes:
        """
        Derive key material from shared secret using HKDF-like approach.

        Args:
            salt: Optional salt for KDF
            info: Optional application info
            length: Desired key length

        Returns:
            Derived key bytes of specified length
        """
        # Use HMAC as KDF (similar to HKDF extract-expand)
        if salt:
            extract = hmac.new(salt, self.secret, hashlib.sha256).digest()
        else:
            extract = hmac.new(self.secret, digestmod=hashlib.sha256).digest()

        # Expand to desired length
        output = b''
        counter = 1
        while len(output) < length:
            output += hmac.new(
                extract,
                output[-32:] + bytes([counter]) + info,
                hashlib.sha256
            ).digest()
            counter += 1

        return output[:length]


class KyberKeyEncapsulation:
    """
    Kyber Key Encapsulation Mechanism (ML-KEM).

    Provides NIST-standardized post-quantum key establishment.

    Example:
        >>> kyber = KyberKeyEncapsulation(security_level=KyberSecurityLevel.LEVEL3)
        >>>
        >>> # Generate keypair
        >>> public_key, secret_key = kyber.generate_keypair()
        >>> print(f"Public key size: {len(public_key)} bytes")
        >>>
        >>> # Encapsulate to public key
        >>> ciphertext, shared_secret = kyber.encapsulate(public_key)
        >>> print(f"Ciphertext size: {len(ciphertext)} bytes")
        >>>
        >>> # Decapsulate with secret key
        >>> recovered_secret = kyber.decapsulate(secret_key, ciphertext)
        >>> assert shared_secret.to_bytes() == recovered_secret.to_bytes()
        >>>
        >>> # Derive key material
        >>> key = shared_secret.derive_key(length=32)
        >>> print(f"Derived key: {key.hex()}")
    """

    # Key/ciphertext sizes for each security level
    KYBER_SIZES = {
        KyberSecurityLevel.LEVEL1: {"pk": 800, "sk": 1632, "ct": 768, "ss": 32},
        KyberSecurityLevel.LEVEL3: {"pk": 1184, "sk": 2400, "ct": 1088, "ss": 32},
        KyberSecurityLevel.LEVEL5: {"pk": 1568, "sk": 3168, "ct": 1568, "ss": 32},
    }

    def __init__(self, security_level: KyberSecurityLevel = KyberSecurityLevel.LEVEL3):
        """
        Initialize Kyber Key Encapsulation.

        Args:
            security_level: Kyber security level (LEVEL1, LEVEL3, LEVEL5)

        Raises:
            ImportError: If neither liboqs nor pqcrypto is installed
            ValueError: If security level is invalid
        """
        if not HAS_LIBOQS and not HAS_PQCRYPTO:
            raise ImportError(
                "Either liboqs-python or pqcrypto is required for Kyber. "
                "Install with: pip install pqcrypto"
            )

        if not isinstance(security_level, KyberSecurityLevel):
            raise ValueError(f"Invalid security level: {security_level}")

        self.security_level = security_level
        self.algorithm_name = security_level.value
        self._lock = threading.RLock()
        self._operations_count = 0

    def generate_keypair(self) -> Tuple[KyberPublicKey, KyberSecretKey]:
        """
        Generate a new Kyber keypair.

        Returns:
            Tuple of (public_key, secret_key)

        Raises:
            RuntimeError: If key generation fails
        """
        with self._lock:
            try:
                if HAS_LIBOQS:
                    kekem = KeyEncapsulation(self.algorithm_name)
                    public_key_bytes = kekem.generate_keyencap()
                    secret_key_bytes = kekem.secret_key
                else:
                    kem_mod = _PQCRYPTO_KEM_MAP[self.algorithm_name]
                    public_key_bytes, secret_key_bytes = kem_mod.generate_keypair()

                if not public_key_bytes or not secret_key_bytes:
                    raise RuntimeError("Key generation produced empty keys")

                public_key = KyberPublicKey(
                    security_level=self.security_level,
                    key_data=bytes(public_key_bytes),
                    metadata={"algorithm": self.algorithm_name}
                )

                secret_key = KyberSecretKey(
                    security_level=self.security_level,
                    key_data=bytes(secret_key_bytes),
                    public_key=public_key,
                    metadata={"algorithm": self.algorithm_name}
                )

                self._operations_count += 1
                return public_key, secret_key

            except Exception as e:
                raise RuntimeError(f"Kyber key generation failed: {e}")

    def encapsulate(self, public_key: KyberPublicKey) -> Tuple[KyberCiphertext, SharedSecret]:
        """
        Encapsulate to a public key, generating a shared secret.

        Args:
            public_key: Kyber public key to encapsulate to

        Returns:
            Tuple of (ciphertext, shared_secret)

        Raises:
            ValueError: If public key is invalid
            RuntimeError: If encapsulation fails
        """
        with self._lock:
            if not isinstance(public_key, KyberPublicKey):
                raise ValueError("Invalid public key type")

            if public_key.security_level != self.security_level:
                raise ValueError(
                    f"Public key security level {public_key.security_level} "
                    f"does not match {self.security_level}"
                )

            try:
                if HAS_LIBOQS:
                    kekem = KeyEncapsulation(self.algorithm_name)
                    kekem.load_public_key(public_key.key_data)
                    ciphertext_bytes = kekem.encap_secret()
                    shared_secret_bytes = kekem.shared_secret
                else:
                    kem_mod = _PQCRYPTO_KEM_MAP[self.algorithm_name]
                    ciphertext_bytes, shared_secret_bytes = kem_mod.encrypt(public_key.key_data)

                if not ciphertext_bytes or not shared_secret_bytes:
                    raise RuntimeError("Encapsulation produced empty outputs")

                ciphertext = KyberCiphertext(
                    ciphertext=bytes(ciphertext_bytes),
                    security_level=self.security_level
                )

                shared_secret = SharedSecret(
                    secret=bytes(shared_secret_bytes),
                    metadata={
                        "algorithm": self.algorithm_name,
                        "ciphertext_size": len(ciphertext_bytes)
                    }
                )

                self._operations_count += 1
                return ciphertext, shared_secret

            except Exception as e:
                raise RuntimeError(f"Kyber encapsulation failed: {e}")

    def decapsulate(
        self,
        secret_key: KyberSecretKey,
        ciphertext: KyberCiphertext
    ) -> SharedSecret:
        """
        Decapsulate a ciphertext with a secret key to recover shared secret.

        Args:
            secret_key: Kyber secret key
            ciphertext: Ciphertext to decapsulate

        Returns:
            Recovered shared secret

        Raises:
            ValueError: If keys/ciphertext are invalid
            RuntimeError: If decapsulation fails
        """
        with self._lock:
            if not isinstance(secret_key, KyberSecretKey):
                raise ValueError("Invalid secret key type")

            if not isinstance(ciphertext, KyberCiphertext):
                raise ValueError("Invalid ciphertext type")

            if secret_key.security_level != self.security_level:
                raise ValueError(
                    f"Secret key security level {secret_key.security_level} "
                    f"does not match {self.security_level}"
                )

            try:
                if HAS_LIBOQS:
                    kekem = KeyEncapsulation(self.algorithm_name)
                    kekem.load_secret_key(secret_key.key_data)
                    shared_secret_bytes = kekem.decap_secret(ciphertext.ciphertext)
                else:
                    kem_mod = _PQCRYPTO_KEM_MAP[self.algorithm_name]
                    shared_secret_bytes = kem_mod.decrypt(secret_key.key_data, ciphertext.ciphertext)

                if not shared_secret_bytes:
                    raise RuntimeError("Decapsulation produced empty shared secret")

                shared_secret = SharedSecret(
                    secret=bytes(shared_secret_bytes),
                    metadata={
                        "algorithm": self.algorithm_name,
                        "decapsulation_success": True
                    }
                )

                self._operations_count += 1
                return shared_secret

            except Exception as e:
                raise RuntimeError(f"Kyber decapsulation failed: {e}")

    def get_statistics(self) -> Dict[str, Any]:
        """
        Get encapsulation statistics.

        Returns:
            Dictionary with operation counts and sizes
        """
        with self._lock:
            sizes = self.KYBER_SIZES[self.security_level]
            return {
                "algorithm": self.algorithm_name,
                "security_level": self.security_level.value,
                "operations": self._operations_count,
                "public_key_size": sizes["pk"],
                "secret_key_size": sizes["sk"],
                "ciphertext_size": sizes["ct"],
                "shared_secret_size": sizes["ss"],
                "total_key_size": sizes["pk"] + sizes["sk"],
            }


def create_kyber_encapsulation(
    security_level: KyberSecurityLevel = KyberSecurityLevel.LEVEL3,
) -> KyberKeyEncapsulation:
    """
    Create a Kyber encapsulation instance with recommended settings.

    Args:
        security_level: Desired security level (default LEVEL3)

    Returns:
        Configured KyberKeyEncapsulation instance
    """
    return KyberKeyEncapsulation(security_level=security_level)
