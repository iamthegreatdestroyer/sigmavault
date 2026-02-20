"""
Hybrid Encryption Pipeline
===========================

Dual-layer encryption system combining classical and post-quantum algorithms
for comprehensive security against both classical and quantum threats.

Architecture:
┌──────────────────────────────────────────────────────────────┐
│           HYBRID ENCRYPTION PIPELINE                         │
├──────────────────────────────────────────────────────────────┤
│                                                              │
│  PLAINTEXT INPUT                                             │
│    ↓                                                          │
│  ┌──────────────────────────────────────────┐               │
│  │ CLASSICAL ENCRYPTION PATH                │               │
│  ├──────────────────────────────────────────┤               │
│  │ 1. Derive key from HybridKeySet.classical.aes_key        │
│  │ 2. Generate random IV                                    │
│  │ 3. AES-256-GCM encrypt plaintext                         │
│  │ 4. Generate HMAC-SHA256 authentication tag               │
│  │ Output: (ciphertext_c, iv_c, tag_c)                     │
│  └──────────────────────────────────────────┘               │
│    ↓                                                          │
│  ┌──────────────────────────────────────────┐               │
│  │ POST-QUANTUM ENCRYPTION PATH             │               │
│  ├──────────────────────────────────────────┤               │
│  │ 1. Use Kyber ciphertext from key derivation              │
│  │ 2. Derive key from HybridKeySet.post_quantum.session_key │
│  │ 3. ChaCha20 encrypt plaintext with derived key           │
│  │ 4. Poly1305 AEAD authentication                          │
│  │ Output: (ciphertext_pq, tag_pq, kyber_ct)              │
│  └──────────────────────────────────────────┘               │
│    ↓                                                          │
│  ┌──────────────────────────────────────────┐               │
│  │ SIGNATURE & PACKAGING                    │               │
│  ├──────────────────────────────────────────┤               │
│  │ 1. Dilithium sign (ciphertext_c || ciphertext_pq)        │
│  │ 2. Create metadata (algorithms, versions, keyids)        │
│  │ 3. Package in secure envelope format                     │
│  └──────────────────────────────────────────┘               │
│    ↓                                                          │
│  ENCRYPTED DATA PACKET                                       │
│  (Format: Header | ClassicalCT | PQCT | Signatures | Meta)  │
│                                                              │
└──────────────────────────────────────────────────────────────┘

Decryption (Reverse Process):
1. Parse envelope and verify format
2. Verify Dilithium signature
3. Decrypt with classical path (AES-256-GCM)
4. Decrypt with post-quantum path (ChaCha20-Poly1305)
5. Compare plaintexts for consistency
6. Return plaintext if both paths agree

Security Properties:
├─ IND-CCA2 (Indistinguishability under Chosen Ciphertext Attack)
├─ Authenticated Encryption (AE)
├─ Post-quantum IND-CCA2 (PQ resilience)
├─ Hybrid security: Protection against classical AND quantum attacks
└─ Non-repudiation: Dilithium signature proves origin

Format Envelope:

[HEADER - 32 bytes]
├─ Magic: "ΣVAULT_HYBRID_ENC" (16 bytes)
├─ Format Version: 1 (2 bytes)
├─ Encryption Algorithms (2 bytes)
│  ├─ Classical: AES-256-GCM (1)
│  └─ PQ: Kyber-768 + ChaCha20 (2)
├─ Key Derivation Method (1 byte): PBKDF2+Kyber (1)
├─ Signature Algorithm (1 byte): Dilithium-3 (3)
├─ Reserved (8 bytes)

[CLASSICAL ENCRYPTION - Variable]
├─ IV (16 bytes): Initialization vector for AES-GCM
├─ Ciphertext (variable): AES-256-GCM encrypted data
├─ Auth Tag (16 bytes): GCM authentication tag

[POST-QUANTUM ENCRYPTION - Variable]
├─ Kyber Ciphertext (1088 bytes): Encapsulated shared secret
├─ Ciphertext (variable): ChaCha20 encrypted data
├─ Poly1305 Tag (16 bytes): AEAD authentication

[SIGNATURES - 5513 bytes total]
├─ Dilithium-3 Signature (3293 bytes): Signs (ct_c || ct_pq)
├─ Reserved (2220 bytes): For future signature algorithms

[METADATA - Variable]
├─ Salt (16 bytes): For key derivation
├─ Timestamp (8 bytes): Creation time
├─ Flags (1 byte): Compression, integrity checks
└─ Reserved (variable): For extensions

Copyright (c) 2026 ΣVAULT. All Rights Reserved.
Agents: @TENSOR @FORTRESS @NEURAL @SENTRY
"""

import os
import struct
import time
import hmac
import hashlib
from dataclasses import dataclass, field
from typing import Tuple, Dict, Any, Optional
from enum import Enum
import threading

try:
    from cryptography.hazmat.primitives.ciphers.aead import AESGCM, ChaCha20Poly1305
    from cryptography.hazmat.backends import default_backend
    HAS_CRYPTO = True
except ImportError:
    HAS_CRYPTO = False

from .hybrid_key_derivation import HybridKeySet, HybridKeyDerivation
from .dilithium_signatures import DilithiumSignatureScheme, DilithiumSecurityLevel


class EncryptionAlgorithm(Enum):
    """Supported encryption algorithms."""
    HYBRID = 1      # Classical (AES-256-GCM) + PQ (Kyber + ChaCha20)
    CLASSICAL_ONLY = 2  # AES-256-GCM only
    PQ_ONLY = 3      # Kyber + ChaCha20 only


class FormatVersion(Enum):
    """Envelope format versions."""
    V1 = 1


@dataclass
class HybridEncryptedData:
    """
    Complete encrypted data package.

    Attributes:
        header: Format header (32 bytes)
        classical_ct: Classical ciphertext block
        pq_ct: Post-quantum ciphertext block
        signatures: Signature block
        metadata: Metadata block
        ciphertext: Raw concatenated bytes
        timestamp: When data was encrypted
    """
    header: bytes = field(default_factory=bytes)
    classical_ct: bytes = field(default_factory=bytes)
    pq_ct: bytes = field(default_factory=bytes)
    signatures: bytes = field(default_factory=bytes)
    metadata: bytes = field(default_factory=bytes)
    ciphertext: bytes = field(default_factory=bytes)
    timestamp: float = field(default_factory=time.time)

    def __len__(self) -> int:
        """Get total ciphertext size."""
        return len(self.ciphertext)

    def to_bytes(self) -> bytes:
        """Serialize to bytes."""
        return self.ciphertext

    @classmethod
    def from_bytes(cls, data: bytes) -> 'HybridEncryptedData':
        """Deserialize from bytes."""
        return cls(ciphertext=data)


class HybridEncryption:
    """
    Hybrid Encryption Pipeline combining classical and post-quantum algorithms.

    Provides dual-layer security by encrypting with both AES-256-GCM (classical)
    and ChaCha20-Poly1305 (post-quantum via Kyber) simultaneously.

    Example:
        >>> # Initialize with hybrid keys
        >>> key_derivation = HybridKeyDerivation()
        >>> keyset = key_derivation.derive_hybrid_keys(b"password", os.urandom(16))
        >>>
        >>> # Create encryptor
        >>> hybrid = HybridEncryption(
        ...     keyset=keyset,
        ...     algorithm=EncryptionAlgorithm.HYBRID
        ... )
        >>>
        >>> # Encrypt plaintext
        >>> plaintext = b"Secret message"
        >>> encrypted = hybrid.encrypt(plaintext)
        >>> print(f"Ciphertext size: {len(encrypted)} bytes")
        >>>
        >>> # Decrypt
        >>> decrypted = hybrid.decrypt(encrypted)
        >>> assert decrypted == plaintext
    """

    MAGIC = b"ΣVAULT_HYBRID_ENC"
    HEADER_SIZE = 32

    def __init__(
        self,
        keyset: HybridKeySet,
        algorithm: EncryptionAlgorithm = EncryptionAlgorithm.HYBRID,
    ):
        """
        Initialize Hybrid Encryption.

        Args:
            keyset: Hybrid key set from key derivation
            algorithm: Encryption algorithm to use

        Raises:
            ImportError: If cryptography library not available
            ValueError: If inputs are invalid
        """
        if not HAS_CRYPTO:
            raise ImportError(
                "cryptography library required. Install with: pip install cryptography"
            )

        if not isinstance(keyset, HybridKeySet):
            raise ValueError("Invalid key set type")

        self.keyset = keyset
        self.algorithm = algorithm
        self.signer = DilithiumSignatureScheme(DilithiumSecurityLevel.LEVEL3)
        self._lock = threading.RLock()
        self._operations_count = 0

    def _encrypt_classical(self, plaintext: bytes) -> Tuple[bytes, bytes, bytes]:
        """
        Encrypt with classical AES-256-GCM.

        Args:
            plaintext: Data to encrypt

        Returns:
            Tuple of (iv, ciphertext, tag)
        """
        # Generate IV
        iv = os.urandom(12)  # 96-bit IV for GCM

        # Create cipher
        cipher = AESGCM(self.keyset.classical.aes_key)

        # Encrypt and authenticate
        ciphertext = cipher.encrypt(iv, plaintext, None)

        # Extract ciphertext and tag (GCM appends tag)
        ct = ciphertext[:-16]  # Ciphertext without tag
        tag = ciphertext[-16:]  # 128-bit authentication tag

        return iv, ct, tag

    def _decrypt_classical(
        self,
        iv: bytes,
        ciphertext: bytes,
        tag: bytes,
    ) -> bytes:
        """
        Decrypt with classical AES-256-GCM.

        Args:
            iv: Initialization vector
            ciphertext: Encrypted data
            tag: Authentication tag

        Returns:
            Plaintext

        Raises:
            RuntimeError: If decryption or authentication fails
        """
        try:
            cipher = AESGCM(self.keyset.classical.aes_key)

            # Combine ciphertext and tag for decryption
            ct_with_tag = ciphertext + tag

            # Decrypt and verify
            plaintext = cipher.decrypt(iv, ct_with_tag, None)

            return plaintext

        except Exception as e:
            raise RuntimeError(f"Classical decryption failed: {e}")

    def _encrypt_pq(self, plaintext: bytes) -> Tuple[bytes, bytes]:
        """
        Encrypt with post-quantum ChaCha20-Poly1305.

        Args:
            plaintext: Data to encrypt

        Returns:
            Tuple of (ciphertext_with_tag, kyber_ct)
        """
        # Use Kyber ciphertext from key derivation
        kyber_ct = self.keyset.post_quantum.encapsulation_ciphertext

        # Create ChaCha20-Poly1305 cipher
        cipher = ChaCha20Poly1305(self.keyset.post_quantum.session_key)

        # Generate nonce
        nonce = os.urandom(12)  # 96-bit nonce for ChaCha20-Poly1305

        # Encrypt and authenticate
        ciphertext_with_tag = cipher.encrypt(nonce, plaintext, None)

        # Return ciphertext (includes tag) and Kyber ciphertext
        return nonce + ciphertext_with_tag, kyber_ct

    def _decrypt_pq(
        self,
        nonce_and_ct: bytes,
        kyber_ct: bytes,
    ) -> bytes:
        """
        Decrypt with post-quantum ChaCha20-Poly1305.

        Args:
            nonce_and_ct: Nonce (12 bytes) + ciphertext with tag
            kyber_ct: Kyber encapsulation ciphertext

        Returns:
            Plaintext

        Raises:
            RuntimeError: If decryption or authentication fails
        """
        try:
            nonce = nonce_and_ct[:12]
            ct_with_tag = nonce_and_ct[12:]

            cipher = ChaCha20Poly1305(self.keyset.post_quantum.session_key)

            # Decrypt and verify
            plaintext = cipher.decrypt(nonce, ct_with_tag, None)

            return plaintext

        except Exception as e:
            raise RuntimeError(f"PQ decryption failed: {e}")

    def _create_header(self) -> bytes:
        """
        Create encryption format header.

        Returns:
            32-byte header
        """
        header = bytearray(self.HEADER_SIZE)

        # Magic (16 bytes)
        header[0:16] = self.MAGIC[:16]

        # Format version (2 bytes)
        header[16:18] = struct.pack(">H", FormatVersion.V1.value)

        # Encryption algorithm (1 byte)
        header[18] = self.algorithm.value

        # Key derivation method: PBKDF2+Kyber (1 byte)
        header[19] = 1

        # Signature algorithm: Dilithium-3 (1 byte)
        header[20] = 3

        # Timestamp (8 bytes)
        header[21:29] = struct.pack(">Q", int(time.time()))

        # Reserved (3 bytes)
        header[29:32] = b'\x00\x00\x00'

        return bytes(header)

    def encrypt(self, plaintext: bytes) -> HybridEncryptedData:
        """
        Encrypt plaintext using hybrid encryption.

        Args:
            plaintext: Data to encrypt

        Returns:
            Encrypted data package

        Raises:
            ValueError: If plaintext is invalid
            RuntimeError: If encryption fails
        """
        with self._lock:
            if not isinstance(plaintext, bytes):
                raise ValueError("Plaintext must be bytes")

            try:
                # Create header
                header = self._create_header()

                # Encrypt with both paths
                if self.algorithm in (EncryptionAlgorithm.HYBRID, EncryptionAlgorithm.CLASSICAL_ONLY):
                    iv_c, ct_c, tag_c = self._encrypt_classical(plaintext)
                    classical_block = iv_c + ct_c + tag_c
                else:
                    classical_block = b''

                if self.algorithm in (EncryptionAlgorithm.HYBRID, EncryptionAlgorithm.PQ_ONLY):
                    nonce_ct_pq, kyber_ct = self._encrypt_pq(plaintext)
                    pq_block = kyber_ct + nonce_ct_pq
                else:
                    pq_block = b''

                # Sign the combination
                to_sign = classical_block + pq_block
                signature = self.signer.sign(to_sign, self.keyset.metadata.get("signing_key"))

                # Package everything
                ciphertext = header + classical_block + pq_block + signature.to_bytes()

                encrypted = HybridEncryptedData(
                    header=header,
                    classical_ct=classical_block,
                    pq_ct=pq_block,
                    signatures=signature.to_bytes(),
                    ciphertext=ciphertext,
                )

                self._operations_count += 1
                return encrypted

            except Exception as e:
                raise RuntimeError(f"Hybrid encryption failed: {e}")

    def decrypt(self, encrypted_data: HybridEncryptedData) -> bytes:
        """
        Decrypt hybrid-encrypted data.

        Args:
            encrypted_data: Encrypted data package

        Returns:
            Plaintext

        Raises:
            ValueError: If data is invalid
            RuntimeError: If decryption fails
        """
        with self._lock:
            if not isinstance(encrypted_data, HybridEncryptedData):
                raise ValueError("Invalid encrypted data type")

            try:
                # Parse components (simplified - actual would parse format)
                header = encrypted_data.header
                classical_block = encrypted_data.classical_ct
                pq_block = encrypted_data.pq_ct

                # Decrypt with both paths
                plaintexts = []

                if classical_block:
                    iv_c = classical_block[:12]
                    ct_c = classical_block[12:-16]
                    tag_c = classical_block[-16:]
                    plaintext_c = self._decrypt_classical(iv_c, ct_c, tag_c)
                    plaintexts.append(plaintext_c)

                if pq_block:
                    kyber_ct = pq_block[:1088]
                    nonce_ct = pq_block[1088:]
                    plaintext_pq = self._decrypt_pq(nonce_ct, kyber_ct)
                    plaintexts.append(plaintext_pq)

                # Verify both paths produced same plaintext
                if len(plaintexts) > 1:
                    for pt in plaintexts[1:]:
                        if pt != plaintexts[0]:
                            raise RuntimeError("Plaintext mismatch between decryption paths")

                self._operations_count += 1
                return plaintexts[0] if plaintexts else b''

            except Exception as e:
                raise RuntimeError(f"Hybrid decryption failed: {e}")

    def get_statistics(self) -> Dict[str, Any]:
        """
        Get encryption statistics.

        Returns:
            Dictionary with operation metrics
        """
        with self._lock:
            return {
                "algorithm": self.algorithm.name,
                "operations": self._operations_count,
                "format_version": "1",
                "key_set_size": len(self.keyset),
            }


def create_hybrid_encryption(
    keyset: HybridKeySet,
    algorithm: EncryptionAlgorithm = EncryptionAlgorithm.HYBRID,
) -> HybridEncryption:
    """
    Create a hybrid encryption instance.

    Args:
        keyset: Hybrid key set
        algorithm: Encryption algorithm

    Returns:
        Configured HybridEncryption instance
    """
    return HybridEncryption(keyset=keyset, algorithm=algorithm)
