"""
ΣVAULT Post-Quantum Cryptography Module
========================================

Phase 6: Quantum-Safe Cryptography Implementation

This module provides NIST-standardized post-quantum cryptographic algorithms
integrated with classical algorithms for hybrid encryption.

Components:

1. Kyber Key Encapsulation (ML-KEM)
   - Key establishment mechanism
   - IND-CCA2 secure
   - Lattice-based hardness

2. Dilithium Digital Signatures (ML-DSA)
   - Digital signatures and authentication
   - EUF-CMA secure
   - Lattice-based hardness

3. Hybrid Key Derivation
   - Combines PBKDF2 (classical) + Kyber (post-quantum)
   - Belt-and-suspenders security model
   - Protected against both classical and quantum threats

4. Hybrid Encryption
   - Dual-layer encryption pipeline
   - Classical AES-256-GCM + Post-quantum ChaCha20
   - Automatic format versioning

Security Model:

Hybrid Encryption combines:
├─ Classical Path: PBKDF2 → AES-256-GCM
├─ Post-Quantum Path: Kyber-768 → ChaCha20
└─ Both paths provide independent security guarantees

If one path is compromised, the other still provides security.

Agents: @TENSOR @FORTRESS @NEURAL @SENTRY
Status: PHASE 6 - DAY 1 ACTIVE
"""

from .kyber_key_encapsulation import (
    KyberKeyEncapsulation,
    KyberSecurityLevel,
    KyberPublicKey,
    KyberSecretKey,
    KyberCiphertext,
    SharedSecret,
    create_kyber_encapsulation,
)

from .dilithium_signatures import (
    DilithiumSignatureScheme,
    DilithiumSecurityLevel,
    DilithiumPublicKey,
    DilithiumSecretKey,
    DilithiumSignature,
    create_dilithium_signer,
)

from .hybrid_key_derivation import (
    HybridKeyDerivation,
    HybridKeySet,
    ClassicalKeySet,
    PostQuantumKeySet,
    KeyDerivationStrength,
    create_hybrid_key_derivation,
)

__all__ = [
    # Kyber exports
    "KyberKeyEncapsulation",
    "KyberSecurityLevel",
    "KyberPublicKey",
    "KyberSecretKey",
    "KyberCiphertext",
    "SharedSecret",
    "create_kyber_encapsulation",
    # Dilithium exports
    "DilithiumSignatureScheme",
    "DilithiumSecurityLevel",
    "DilithiumPublicKey",
    "DilithiumSecretKey",
    "DilithiumSignature",
    "create_dilithium_signer",
    # Hybrid exports
    "HybridKeyDerivation",
    "HybridKeySet",
    "ClassicalKeySet",
    "PostQuantumKeySet",
    "KeyDerivationStrength",
    "create_hybrid_key_derivation",
]
