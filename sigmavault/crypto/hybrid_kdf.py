"""
Hybrid Key Derivation — Phase 6 (Argon2id + Kyber + HKDF)
===========================================================

Combines a classical memory-hard KDF with post-quantum key encapsulation
for a belt-and-suspenders key derivation scheme.

Construction:
    classical_key = Argon2id(password, salt, m=65536, t=3, p=4)
    kyber_ct, shared_secret = Kyber1024.encapsulate(kyber_public_key)
    xor_material = classical_key XOR shared_secret[:32]
    final_key = HKDF(ikm=xor_material, salt=b"sigmavault-v6", info=b"", length=32)

Backward compatibility:
    v5 vaults use a VAULT_MAGIC_V5 header. derive_key_v5 handles the
    classical-only path so existing vaults remain readable.

SECURITY: Never log password, salt, classical_key, shared_secret, or derived_key.
"""

import hashlib
import secrets
from typing import Optional
from dataclasses import dataclass

from cryptography.hazmat.primitives.kdf.hkdf import HKDF
from cryptography.hazmat.primitives import hashes as crypto_hashes

from .kyber_key_encapsulation import (
    KyberKeyEncapsulation,
    KyberSecurityLevel,
    KyberPublicKey,
    KyberSecretKey,
)

try:
    from argon2.low_level import hash_secret_raw, Type as Argon2Type
    HAS_ARGON2 = True
except ImportError:
    HAS_ARGON2 = False

VAULT_MAGIC_V5 = b"SIGMAVAULT_V5\x00"
VAULT_MAGIC_V6 = b"SIGMAVAULT_V6\x00"

_ARGON2_MEMORY = 65536   # 64 MiB
_ARGON2_TIME = 3
_ARGON2_PARALLELISM = 4
_ARGON2_LEN = 32
_HKDF_SALT = b"sigmavault-v6"


def _argon2id(password: str, salt: bytes) -> bytes:
    if HAS_ARGON2:
        return hash_secret_raw(
            secret=password.encode("utf-8"),
            salt=salt,
            time_cost=_ARGON2_TIME,
            memory_cost=_ARGON2_MEMORY,
            parallelism=_ARGON2_PARALLELISM,
            hash_len=_ARGON2_LEN,
            type=Argon2Type.ID,
        )
    return hashlib.pbkdf2_hmac(
        "sha256",
        password.encode("utf-8"),
        salt,
        iterations=600_000,
        dklen=_ARGON2_LEN,
    )


def _xor32(a: bytes, b: bytes) -> bytes:
    return bytes(x ^ y for x, y in zip(a[:32], b[:32]))


def _hkdf_expand(ikm: bytes) -> bytes:
    return HKDF(
        algorithm=crypto_hashes.SHA256(),
        length=32,
        salt=_HKDF_SALT,
        info=b"",
    ).derive(ikm)


@dataclass
class HybridKDFResult:
    """Output of a v6 hybrid key derivation."""
    derived_key: bytes          # 32-byte AES-256-GCM key
    kyber_ciphertext: bytes     # Kyber-1024 ciphertext; store with vault header
    salt: bytes                 # Argon2id salt; store with vault header


def derive_key(
    password: str,
    kyber_public_key: KyberPublicKey,
    salt: Optional[bytes] = None,
) -> HybridKDFResult:
    """
    Derive a 32-byte vault key using Argon2id + Kyber-1024 + HKDF.

    Args:
        password: User passphrase.
        kyber_public_key: Kyber-1024 public key for encapsulation.
        salt: 32-byte Argon2id salt. Generated randomly if not provided.

    Returns:
        HybridKDFResult with derived_key, kyber_ciphertext, and salt.
    """
    if not isinstance(password, str) or not password:
        raise ValueError("password must be a non-empty string")
    if not isinstance(kyber_public_key, KyberPublicKey):
        raise ValueError("kyber_public_key must be a KyberPublicKey instance")

    if salt is None:
        salt = secrets.token_bytes(32)
    if len(salt) < 16:
        raise ValueError("salt must be at least 16 bytes")

    kem = KyberKeyEncapsulation(KyberSecurityLevel.LEVEL5)  # Kyber-1024

    classical_key = _argon2id(password, salt)
    kyber_ct, shared_secret = kem.encapsulate(kyber_public_key)

    xor_material = _xor32(classical_key, shared_secret.secret)
    derived_key = _hkdf_expand(xor_material)

    return HybridKDFResult(
        derived_key=derived_key,
        kyber_ciphertext=kyber_ct.to_bytes(),
        salt=salt,
    )


def recover_key(
    password: str,
    salt: bytes,
    kyber_ciphertext: bytes,
    kyber_secret_key: KyberSecretKey,
) -> bytes:
    """
    Recover the vault key given the stored kyber_ciphertext.

    Args:
        password: User passphrase.
        salt: Argon2id salt stored with the vault.
        kyber_ciphertext: Kyber-1024 ciphertext stored with the vault.
        kyber_secret_key: Kyber-1024 secret key.

    Returns:
        32-byte derived key.
    """
    from .kyber_key_encapsulation import KyberCiphertext

    if not isinstance(password, str) or not password:
        raise ValueError("password must be a non-empty string")

    kem = KyberKeyEncapsulation(KyberSecurityLevel.LEVEL5)

    ct_obj = KyberCiphertext(
        ciphertext=kyber_ciphertext,
        security_level=KyberSecurityLevel.LEVEL5,
    )

    classical_key = _argon2id(password, salt)
    shared_secret = kem.decapsulate(kyber_secret_key, ct_obj)

    xor_material = _xor32(classical_key, shared_secret.secret)
    return _hkdf_expand(xor_material)


def derive_key_v5(password: str, salt: bytes) -> bytes:
    """
    Classical-only key derivation for v5 vault backward compatibility.

    Returns the same key that v5 would have derived using PBKDF2/Argon2id
    without the Kyber layer.
    """
    return _argon2id(password, salt)


def detect_vault_version(header_bytes: bytes) -> int:
    """
    Detect vault format version from the header magic bytes.

    Returns:
        6 for v6, 5 for v5, 0 if unknown.
    """
    n6 = len(VAULT_MAGIC_V6)
    n5 = len(VAULT_MAGIC_V5)
    if header_bytes[:n6] == VAULT_MAGIC_V6:
        return 6
    if header_bytes[:n5] == VAULT_MAGIC_V5:
        return 5
    return 0
