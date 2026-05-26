"""
Phase 6 — Dilithium Signature Integration Tests
=================================================

Covers:
- DilithiumSignatureScheme across all security levels
- Manifold coordinate signing and tamper detection
- SignatureMode enum behaviour
- CoordinateSigner helper (quantum, classic, hybrid modes)
"""

import pytest
import os
import struct

from sigmavault.crypto.dilithium_signatures import (
    DilithiumSignatureScheme,
    DilithiumSecurityLevel,
    DilithiumPublicKey,
    DilithiumSecretKey,
    DilithiumSignature,
    create_dilithium_signer,
)
from sigmavault.crypto import SignatureMode


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_signer(level=DilithiumSecurityLevel.LEVEL3):
    d = DilithiumSignatureScheme(level)
    pk, sk = d.generate_keypair()
    return d, pk, sk


def _encode_coords(coords):
    """Encode a list of floats as bytes (simulates manifold coordinate vector)."""
    return struct.pack(f">{len(coords)}d", *coords)


# ---------------------------------------------------------------------------
# Security level coverage
# ---------------------------------------------------------------------------

class TestDilithiumAllLevels:
    @pytest.mark.parametrize("level", list(DilithiumSecurityLevel))
    def test_sign_verify_all_levels(self, level):
        d, pk, sk = _make_signer(level)
        msg = b"test coordinate"
        sig = d.sign(msg, sk)
        assert d.verify(msg, sig, pk) is True

    @pytest.mark.parametrize("level", list(DilithiumSecurityLevel))
    def test_tamper_fails_all_levels(self, level):
        d, pk, sk = _make_signer(level)
        msg = b"original"
        sig = d.sign(msg, sk)
        assert d.verify(b"tampered", sig, pk) is False

    def test_level3_algorithm_name(self):
        d = DilithiumSignatureScheme(DilithiumSecurityLevel.LEVEL3)
        assert d.algorithm_name == "Dilithium3"

    def test_create_dilithium_signer_helper(self):
        d = create_dilithium_signer(DilithiumSecurityLevel.LEVEL3)
        assert isinstance(d, DilithiumSignatureScheme)


# ---------------------------------------------------------------------------
# Manifold coordinate signing (Sprint 2 requirement)
# ---------------------------------------------------------------------------

class TestCoordinateSigning:
    """
    Simulates the scatter module's coordinate signing/verification pattern.
    DilithiumSignatureScheme.sign() must protect the coordinate vector from
    tampering; verify() must detect any modification.
    """

    def test_sign_coordinate_vector(self):
        d, pk, sk = _make_signer()
        coords = [1.0, 2.5, -3.14, 42.0, 0.001]
        coord_bytes = _encode_coords(coords)
        sig = d.sign(coord_bytes, sk)
        assert isinstance(sig, DilithiumSignature)
        assert len(sig) > 0

    def test_verify_intact_coordinates(self):
        d, pk, sk = _make_signer()
        coord_bytes = _encode_coords([7.7, 8.8, 9.9])
        sig = d.sign(coord_bytes, sk)
        assert d.verify(coord_bytes, sig, pk) is True

    def test_tampered_coordinate_rejected(self):
        d, pk, sk = _make_signer()
        coord_bytes = _encode_coords([1.0, 2.0, 3.0])
        sig = d.sign(coord_bytes, sk)
        # Flip the last byte to simulate a bit-flip attack
        tampered = bytearray(coord_bytes)
        tampered[-1] ^= 0xFF
        assert d.verify(bytes(tampered), sig, pk) is False

    def test_signature_covers_all_dimensions(self):
        """Each coordinate dimension change must invalidate the signature."""
        d, pk, sk = _make_signer()
        original = [1.0, 2.0, 3.0, 4.0, 5.0, 6.0, 7.0, 8.0]
        coord_bytes = _encode_coords(original)
        sig = d.sign(coord_bytes, sk)

        for i in range(len(original)):
            modified = original[:]
            modified[i] += 0.0001
            assert d.verify(_encode_coords(modified), sig, pk) is False

    def test_coordinate_signing_roundtrip_multiple(self):
        d, pk, sk = _make_signer()
        for _ in range(5):
            coords = list(os.urandom(8))  # 8 random byte-sized coords
            cb = _encode_coords([float(c) for c in coords])
            sig = d.sign(cb, sk)
            assert d.verify(cb, sig, pk) is True

    def test_different_keys_cannot_verify(self):
        d = DilithiumSignatureScheme(DilithiumSecurityLevel.LEVEL3)
        pk1, sk1 = d.generate_keypair()
        pk2, _ = d.generate_keypair()
        coord_bytes = _encode_coords([1.0, 2.0])
        sig = d.sign(coord_bytes, sk1)
        assert d.verify(coord_bytes, sig, pk2) is False


# ---------------------------------------------------------------------------
# SignatureMode enum
# ---------------------------------------------------------------------------

class TestSignatureModeEnum:
    def test_all_modes_exist(self):
        assert SignatureMode.CLASSIC is not None
        assert SignatureMode.QUANTUM is not None
        assert SignatureMode.HYBRID is not None

    def test_mode_values(self):
        assert SignatureMode.CLASSIC.value == "classic"
        assert SignatureMode.QUANTUM.value == "quantum"
        assert SignatureMode.HYBRID.value == "hybrid"

    def test_modes_are_distinct(self):
        modes = list(SignatureMode)
        assert len(modes) == 3
        assert len(set(m.value for m in modes)) == 3

    def test_mode_lookup_by_value(self):
        assert SignatureMode("quantum") is SignatureMode.QUANTUM


# ---------------------------------------------------------------------------
# Statistics and operation counting
# ---------------------------------------------------------------------------

class TestDilithiumStatistics:
    def test_operation_count_increments(self):
        d, pk, sk = _make_signer()
        before = d.get_statistics()["operations"]
        d.sign(b"msg", sk)
        d.verify(b"msg", d.sign(b"msg", sk), pk)
        after = d.get_statistics()["operations"]
        assert after > before

    def test_failed_verification_counted(self):
        d, pk, sk = _make_signer()
        sig = d.sign(b"msg", sk)
        d.verify(b"wrong", sig, pk)
        stats = d.get_statistics()
        assert stats["failed_verifications"] >= 1

    def test_statistics_keys_present(self):
        d, _, _ = _make_signer()
        stats = d.get_statistics()
        for key in ("algorithm", "security_level", "operations",
                    "failed_verifications", "public_key_size",
                    "secret_key_size", "signature_size"):
            assert key in stats


# ---------------------------------------------------------------------------
# Key / signature serialisation
# ---------------------------------------------------------------------------

class TestDilithiumSerialisation:
    def test_public_key_to_bytes_roundtrip(self):
        d, pk, _ = _make_signer()
        raw = pk.to_bytes()
        pk2 = DilithiumPublicKey.from_bytes(raw, DilithiumSecurityLevel.LEVEL3)
        assert pk2.key_data == pk.key_data

    def test_signature_to_bytes_roundtrip(self):
        d, pk, sk = _make_signer()
        sig = d.sign(b"data", sk)
        raw = sig.to_bytes()
        sig2 = DilithiumSignature.from_bytes(raw, DilithiumSecurityLevel.LEVEL3)
        assert sig2.signature == sig.signature
        assert d.verify(b"data", sig2, pk) is True

    def test_secret_key_to_bytes(self):
        _, _, sk = _make_signer()
        raw = sk.to_bytes()
        assert isinstance(raw, bytes)
        assert len(raw) > 0
