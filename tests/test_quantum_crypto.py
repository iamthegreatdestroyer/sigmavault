"""
Phase 6 Quantum Cryptography Tests
====================================

Covers Sprint 1 (Kyber-1024 KEM) and Sprint 2 (Dilithium-3 signatures)
and Sprint 3 (hybrid KDF).
"""

import pytest
import os

from sigmavault.crypto.kyber_key_encapsulation import (
    KyberKeyEncapsulation,
    KyberSecurityLevel,
    KyberPublicKey,
    KyberSecretKey,
    KyberCiphertext,
    SharedSecret,
)
from sigmavault.crypto.dilithium_signatures import (
    DilithiumSignatureScheme,
    DilithiumSecurityLevel,
    DilithiumPublicKey,
    DilithiumSecretKey,
    DilithiumSignature,
)
from sigmavault.crypto import SignatureMode
from sigmavault.crypto.hybrid_kdf import (
    derive_key,
    recover_key,
    derive_key_v5,
    detect_vault_version,
    HybridKDFResult,
    VAULT_MAGIC_V5,
    VAULT_MAGIC_V6,
)


# ---------------------------------------------------------------------------
# Sprint 1 — Kyber-1024 KEM
# ---------------------------------------------------------------------------

class TestKyberKeygen:
    def test_kyber_keygen_level5(self):
        kyber = KyberKeyEncapsulation(KyberSecurityLevel.LEVEL5)
        pk, sk = kyber.generate_keypair()
        assert isinstance(pk, KyberPublicKey)
        assert isinstance(sk, KyberSecretKey)
        assert len(pk) > 0
        assert len(sk) > 0

    def test_kyber_keygen_produces_unique_pairs(self):
        kyber = KyberKeyEncapsulation(KyberSecurityLevel.LEVEL5)
        pk1, sk1 = kyber.generate_keypair()
        pk2, sk2 = kyber.generate_keypair()
        assert pk1.key_data != pk2.key_data
        assert sk1.key_data != sk2.key_data

    def test_kyber_default_is_level3(self):
        kyber = KyberKeyEncapsulation()
        assert kyber.security_level == KyberSecurityLevel.LEVEL3

    def test_kyber_level5_algorithm_name(self):
        kyber = KyberKeyEncapsulation(KyberSecurityLevel.LEVEL5)
        assert kyber.algorithm_name == "Kyber1024"


class TestKyberEncapDecap:
    def test_encap_decap_roundtrip_level5(self):
        kyber = KyberKeyEncapsulation(KyberSecurityLevel.LEVEL5)
        pk, sk = kyber.generate_keypair()
        ct, ss_enc = kyber.encapsulate(pk)
        ss_dec = kyber.decapsulate(sk, ct)
        assert ss_enc.secret == ss_dec.secret

    def test_encap_produces_shared_secret_32_bytes(self):
        kyber = KyberKeyEncapsulation(KyberSecurityLevel.LEVEL5)
        pk, _ = kyber.generate_keypair()
        _, ss = kyber.encapsulate(pk)
        assert len(ss.secret) == 32

    def test_encap_ciphertext_not_reusable(self):
        """Two encapsulations to the same key produce different ciphertexts."""
        kyber = KyberKeyEncapsulation(KyberSecurityLevel.LEVEL5)
        pk, sk = kyber.generate_keypair()
        ct1, ss1 = kyber.encapsulate(pk)
        ct2, ss2 = kyber.encapsulate(pk)
        assert ct1.ciphertext != ct2.ciphertext

    def test_wrong_secret_key_does_not_match(self):
        kyber = KyberKeyEncapsulation(KyberSecurityLevel.LEVEL5)
        pk1, _ = kyber.generate_keypair()
        _, sk2 = kyber.generate_keypair()
        ct, ss_enc = kyber.encapsulate(pk1)
        ss_dec = kyber.decapsulate(sk2, ct)
        assert ss_enc.secret != ss_dec.secret

    def test_invalid_public_key_raises(self):
        kyber = KyberKeyEncapsulation(KyberSecurityLevel.LEVEL5)
        with pytest.raises(ValueError):
            kyber.encapsulate("not-a-key")

    def test_invalid_secret_key_raises(self):
        kyber = KyberKeyEncapsulation(KyberSecurityLevel.LEVEL5)
        pk, _ = kyber.generate_keypair()
        ct, _ = kyber.encapsulate(pk)
        with pytest.raises(ValueError):
            kyber.decapsulate("not-a-key", ct)

    def test_invalid_ciphertext_raises(self):
        kyber = KyberKeyEncapsulation(KyberSecurityLevel.LEVEL5)
        _, sk = kyber.generate_keypair()
        with pytest.raises(ValueError):
            kyber.decapsulate(sk, "not-a-ciphertext")

    def test_security_level_mismatch_encap_raises(self):
        k3 = KyberKeyEncapsulation(KyberSecurityLevel.LEVEL3)
        k5 = KyberKeyEncapsulation(KyberSecurityLevel.LEVEL5)
        pk, _ = k3.generate_keypair()
        with pytest.raises(ValueError):
            k5.encapsulate(pk)

    def test_multiple_roundtrips(self):
        kyber = KyberKeyEncapsulation(KyberSecurityLevel.LEVEL5)
        pk, sk = kyber.generate_keypair()
        for _ in range(3):
            ct, ss_enc = kyber.encapsulate(pk)
            ss_dec = kyber.decapsulate(sk, ct)
            assert ss_enc.secret == ss_dec.secret


class TestKyberSharedSecretDerivation:
    def test_derive_key_from_shared_secret(self):
        kyber = KyberKeyEncapsulation(KyberSecurityLevel.LEVEL5)
        pk, sk = kyber.generate_keypair()
        ct, ss = kyber.encapsulate(pk)
        key = ss.derive_key(length=32)
        assert len(key) == 32

    def test_derived_keys_match_after_roundtrip(self):
        kyber = KyberKeyEncapsulation(KyberSecurityLevel.LEVEL5)
        pk, sk = kyber.generate_keypair()
        ct, ss_enc = kyber.encapsulate(pk)
        ss_dec = kyber.decapsulate(sk, ct)
        k1 = ss_enc.derive_key(salt=b"test", length=32)
        k2 = ss_dec.derive_key(salt=b"test", length=32)
        assert k1 == k2

    def test_different_salts_produce_different_keys(self):
        kyber = KyberKeyEncapsulation(KyberSecurityLevel.LEVEL5)
        pk, _ = kyber.generate_keypair()
        _, ss = kyber.encapsulate(pk)
        k1 = ss.derive_key(salt=b"salt-A", length=32)
        k2 = ss.derive_key(salt=b"salt-B", length=32)
        assert k1 != k2


# ---------------------------------------------------------------------------
# Sprint 2 — Dilithium-3 signatures
# ---------------------------------------------------------------------------

class TestDilithiumKeygen:
    def test_dilithium_keygen_level3(self):
        d = DilithiumSignatureScheme(DilithiumSecurityLevel.LEVEL3)
        pk, sk = d.generate_keypair()
        assert isinstance(pk, DilithiumPublicKey)
        assert isinstance(sk, DilithiumSecretKey)
        assert len(pk) > 0
        assert len(sk) > 0

    def test_dilithium_keygen_unique_pairs(self):
        d = DilithiumSignatureScheme(DilithiumSecurityLevel.LEVEL3)
        pk1, _ = d.generate_keypair()
        pk2, _ = d.generate_keypair()
        assert pk1.key_data != pk2.key_data


class TestDilithiumSignVerify:
    def test_sign_verify_roundtrip(self):
        d = DilithiumSignatureScheme(DilithiumSecurityLevel.LEVEL3)
        pk, sk = d.generate_keypair()
        msg = b"manifold coordinate vector [1.0, 2.0, 3.0]"
        sig = d.sign(msg, sk)
        assert d.verify(msg, sig, pk) is True

    def test_tamper_detection_raises_or_returns_false(self):
        d = DilithiumSignatureScheme(DilithiumSecurityLevel.LEVEL3)
        pk, sk = d.generate_keypair()
        msg = b"original coordinate"
        sig = d.sign(msg, sk)
        assert d.verify(b"tampered coordinate", sig, pk) is False

    def test_signature_mode_switching(self):
        from sigmavault.crypto import SignatureMode
        assert SignatureMode.CLASSIC.value == "classic"
        assert SignatureMode.QUANTUM.value == "quantum"
        assert SignatureMode.HYBRID.value == "hybrid"

    def test_wrong_public_key_fails_verification(self):
        d = DilithiumSignatureScheme(DilithiumSecurityLevel.LEVEL3)
        pk1, sk1 = d.generate_keypair()
        pk2, _ = d.generate_keypair()
        msg = b"hello"
        sig = d.sign(msg, sk1)
        assert d.verify(msg, sig, pk2) is False

    def test_empty_message_signs_and_verifies(self):
        d = DilithiumSignatureScheme(DilithiumSecurityLevel.LEVEL3)
        pk, sk = d.generate_keypair()
        sig = d.sign(b"", sk)
        assert d.verify(b"", sig, pk) is True

    def test_large_message(self):
        d = DilithiumSignatureScheme(DilithiumSecurityLevel.LEVEL3)
        pk, sk = d.generate_keypair()
        msg = os.urandom(65536)
        sig = d.sign(msg, sk)
        assert d.verify(msg, sig, pk) is True

    def test_sign_invalid_key_raises(self):
        d = DilithiumSignatureScheme(DilithiumSecurityLevel.LEVEL3)
        with pytest.raises(ValueError):
            d.sign(b"msg", "not-a-key")

    def test_verify_invalid_public_key_raises(self):
        d = DilithiumSignatureScheme(DilithiumSecurityLevel.LEVEL3)
        _, sk = d.generate_keypair()
        sig = d.sign(b"msg", sk)
        with pytest.raises(ValueError):
            d.verify(b"msg", sig, "not-a-key")


# ---------------------------------------------------------------------------
# Sprint 3 — Hybrid KDF
# ---------------------------------------------------------------------------

class TestHybridKDF:
    def _make_kyber_keypair(self):
        from sigmavault.crypto.kyber_key_encapsulation import KyberKeyEncapsulation, KyberSecurityLevel
        kem = KyberKeyEncapsulation(KyberSecurityLevel.LEVEL5)
        return kem.generate_keypair()

    def test_derive_key_returns_32_bytes(self):
        pk, _ = self._make_kyber_keypair()
        result = derive_key("password", pk)
        assert isinstance(result, HybridKDFResult)
        assert len(result.derived_key) == 32

    def test_derive_recover_roundtrip(self):
        pk, sk = self._make_kyber_keypair()
        result = derive_key("correct-password", pk)
        recovered = recover_key("correct-password", result.salt, result.kyber_ciphertext, sk)
        assert result.derived_key == recovered

    def test_wrong_password_produces_different_key(self):
        pk, sk = self._make_kyber_keypair()
        result = derive_key("password-A", pk)
        recovered = recover_key("password-B", result.salt, result.kyber_ciphertext, sk)
        assert result.derived_key != recovered

    def test_different_salts_produce_different_keys(self):
        pk, sk = self._make_kyber_keypair()
        salt1 = os.urandom(32)
        salt2 = os.urandom(32)
        r1 = derive_key("same-password", pk, salt=salt1)
        r2 = derive_key("same-password", pk, salt=salt2)
        assert r1.derived_key != r2.derived_key

    def test_derived_key_is_not_password(self):
        pk, _ = self._make_kyber_keypair()
        result = derive_key("my-secret-password", pk)
        assert b"my-secret-password" not in result.derived_key

    def test_invalid_password_raises(self):
        pk, _ = self._make_kyber_keypair()
        with pytest.raises(ValueError):
            derive_key("", pk)
        with pytest.raises(ValueError):
            derive_key(123, pk)

    def test_invalid_public_key_raises(self):
        with pytest.raises(ValueError):
            derive_key("password", "not-a-key")

    def test_v5_backward_compat_derive(self):
        salt = os.urandom(32)
        key = derive_key_v5("legacy-password", salt)
        assert len(key) == 32

    def test_detect_vault_version_v6(self):
        assert detect_vault_version(VAULT_MAGIC_V6 + b"\x00" * 16) == 6

    def test_detect_vault_version_v5(self):
        assert detect_vault_version(VAULT_MAGIC_V5 + b"\x00" * 16) == 5

    def test_detect_vault_version_unknown(self):
        assert detect_vault_version(b"\xff" * 32) == 0


# ---------------------------------------------------------------------------
# Sprint 1+2 — Crypto module imports
# ---------------------------------------------------------------------------

class TestCryptoModuleImports:
    def test_signature_mode_enum_importable(self):
        from sigmavault.crypto import SignatureMode
        assert hasattr(SignatureMode, "CLASSIC")
        assert hasattr(SignatureMode, "QUANTUM")
        assert hasattr(SignatureMode, "HYBRID")

    def test_kyber_importable_from_crypto(self):
        from sigmavault.crypto import KyberKeyEncapsulation, KyberSecurityLevel
        assert KyberKeyEncapsulation is not None

    def test_dilithium_importable_from_crypto(self):
        from sigmavault.crypto import DilithiumSignatureScheme, DilithiumSecurityLevel
        assert DilithiumSignatureScheme is not None

    def test_hybrid_key_derivation_importable(self):
        from sigmavault.crypto import HybridKeyDerivation
        assert HybridKeyDerivation is not None
