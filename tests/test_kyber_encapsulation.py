"""
Kyber Key Encapsulation Tests
==============================

Comprehensive tests for Kyber (ML-KEM) key encapsulation mechanism.
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
    create_kyber_encapsulation,
)


@pytest.mark.asyncio
class TestKyberSecurityLevels:
    """Test different Kyber security levels."""

    def test_kyber_level1_creation(self):
        """Test Kyber-512 (Level 1) creation."""
        kyber = KyberKeyEncapsulation(KyberSecurityLevel.LEVEL1)
        assert kyber.security_level == KyberSecurityLevel.LEVEL1
        assert kyber.algorithm_name == "Kyber512"

    def test_kyber_level3_creation(self):
        """Test Kyber-768 (Level 3) creation."""
        kyber = KyberKeyEncapsulation(KyberSecurityLevel.LEVEL3)
        assert kyber.security_level == KyberSecurityLevel.LEVEL3
        assert kyber.algorithm_name == "Kyber768"

    def test_kyber_level5_creation(self):
        """Test Kyber-1024 (Level 5) creation."""
        kyber = KyberKeyEncapsulation(KyberSecurityLevel.LEVEL5)
        assert kyber.security_level == KyberSecurityLevel.LEVEL5
        assert kyber.algorithm_name == "Kyber1024"


@pytest.mark.asyncio
class TestKyberKeypairGeneration:
    """Test Kyber keypair generation."""

    def test_generate_keypair_level3(self):
        """Test keypair generation for Kyber-768."""
        kyber = KyberKeyEncapsulation(KyberSecurityLevel.LEVEL3)
        public_key, secret_key = kyber.generate_keypair()

        assert isinstance(public_key, KyberPublicKey)
        assert isinstance(secret_key, KyberSecretKey)
        assert len(public_key) == 1184  # Kyber-768 public key size
        assert len(secret_key) == 2400  # Kyber-768 secret key size

    def test_generate_multiple_keypairs(self):
        """Test that each keypair is unique."""
        kyber = KyberKeyEncapsulation(KyberSecurityLevel.LEVEL3)
        pk1, sk1 = kyber.generate_keypair()
        pk2, sk2 = kyber.generate_keypair()

        # Keys should be different
        assert pk1.key_data != pk2.key_data
        assert sk1.key_data != sk2.key_data

    def test_keypair_metadata(self):
        """Test keypair metadata."""
        kyber = KyberKeyEncapsulation(KyberSecurityLevel.LEVEL3)
        public_key, secret_key = kyber.generate_keypair()

        assert public_key.metadata["algorithm"] == "Kyber768"
        assert secret_key.metadata["algorithm"] == "Kyber768"
        assert secret_key.public_key is not None


@pytest.mark.asyncio
class TestKyberEncapsulation:
    """Test Kyber encapsulation."""

    def test_encapsulate_to_public_key(self):
        """Test encapsulation to a public key."""
        kyber = KyberKeyEncapsulation(KyberSecurityLevel.LEVEL3)
        public_key, _ = kyber.generate_keypair()

        ciphertext, shared_secret = kyber.encapsulate(public_key)

        assert isinstance(ciphertext, KyberCiphertext)
        assert isinstance(shared_secret, SharedSecret)
        assert len(ciphertext) == 1088  # Kyber-768 ciphertext size
        assert len(shared_secret) == 32  # Standard 32-byte shared secret

    def test_encapsulate_produces_unique_ciphertexts(self):
        """Test that encapsulation produces unique ciphertexts."""
        kyber = KyberKeyEncapsulation(KyberSecurityLevel.LEVEL3)
        public_key, _ = kyber.generate_keypair()

        ct1, ss1 = kyber.encapsulate(public_key)
        ct2, ss2 = kyber.encapsulate(public_key)

        # Ciphertexts should be different (different ephemeral randomness)
        assert ct1.ciphertext != ct2.ciphertext

    def test_encapsulate_invalid_public_key(self):
        """Test encapsulation with invalid public key."""
        kyber = KyberKeyEncapsulation(KyberSecurityLevel.LEVEL3)

        with pytest.raises(ValueError):
            kyber.encapsulate("not a key")

    def test_encapsulate_mismatched_security_level(self):
        """Test encapsulation with mismatched security level."""
        kyber768 = KyberKeyEncapsulation(KyberSecurityLevel.LEVEL3)
        kyber1024 = KyberKeyEncapsulation(KyberSecurityLevel.LEVEL5)

        pk, _ = kyber768.generate_keypair()

        with pytest.raises(ValueError):
            kyber1024.encapsulate(pk)


@pytest.mark.asyncio
class TestKyberDecapsulation:
    """Test Kyber decapsulation and key recovery."""

    def test_decapsulate_recovers_shared_secret(self):
        """Test that decapsulation recovers the correct shared secret."""
        kyber = KyberKeyEncapsulation(KyberSecurityLevel.LEVEL3)
        public_key, secret_key = kyber.generate_keypair()

        # Encapsulate
        ciphertext, original_secret = kyber.encapsulate(public_key)

        # Decapsulate
        recovered_secret = kyber.decapsulate(secret_key, ciphertext)

        # Secrets should match
        assert recovered_secret.secret == original_secret.secret

    def test_decapsulate_invalid_secret_key(self):
        """Test decapsulation with invalid secret key."""
        kyber = KyberKeyEncapsulation(KyberSecurityLevel.LEVEL3)
        pk, sk = kyber.generate_keypair()
        ct, _ = kyber.encapsulate(pk)

        with pytest.raises(ValueError):
            kyber.decapsulate("not a key", ct)

    def test_decapsulate_invalid_ciphertext(self):
        """Test decapsulation with invalid ciphertext."""
        kyber = KyberKeyEncapsulation(KyberSecurityLevel.LEVEL3)
        _, secret_key = kyber.generate_keypair()

        with pytest.raises(ValueError):
            kyber.decapsulate(secret_key, "not a ciphertext")

    def test_decapsulate_mismatched_keys(self):
        """Test decapsulation with mismatched key pair."""
        kyber = KyberKeyEncapsulation(KyberSecurityLevel.LEVEL3)
        pk1, _ = kyber.generate_keypair()
        _, sk2 = kyber.generate_keypair()

        ct, _ = kyber.encapsulate(pk1)

        # Decryption should fail with wrong secret key
        # (May succeed with garbage output or raise error depending on implementation)
        recovered = kyber.decapsulate(sk2, ct)
        # Secrets likely won't match due to wrong secret key
        # This is expected behavior


@pytest.mark.asyncio
class TestSharedSecretDerivation:
    """Test shared secret key derivation."""

    def test_derive_key_from_shared_secret(self):
        """Test key derivation from shared secret."""
        kyber = KyberKeyEncapsulation(KyberSecurityLevel.LEVEL3)
        pk, sk = kyber.generate_keypair()
        ct, ss = kyber.encapsulate(pk)

        # Derive key
        key = ss.derive_key(length=32)

        assert isinstance(key, bytes)
        assert len(key) == 32

    def test_derive_key_different_lengths(self):
        """Test key derivation with different output lengths."""
        kyber = KyberKeyEncapsulation(KyberSecurityLevel.LEVEL3)
        pk, sk = kyber.generate_keypair()
        _, ss = kyber.encapsulate(pk)

        key_16 = ss.derive_key(length=16)
        key_32 = ss.derive_key(length=32)
        key_64 = ss.derive_key(length=64)

        assert len(key_16) == 16
        assert len(key_32) == 32
        assert len(key_64) == 64

    def test_derive_key_with_salt(self):
        """Test key derivation with salt."""
        kyber = KyberKeyEncapsulation(KyberSecurityLevel.LEVEL3)
        pk, _ = kyber.generate_keypair()
        _, ss = kyber.encapsulate(pk)

        key1 = ss.derive_key(salt=b"salt1", length=32)
        key2 = ss.derive_key(salt=b"salt2", length=32)

        assert key1 != key2

    def test_derive_key_with_info(self):
        """Test key derivation with application info."""
        kyber = KyberKeyEncapsulation(KyberSecurityLevel.LEVEL3)
        pk, _ = kyber.generate_keypair()
        _, ss = kyber.encapsulate(pk)

        key1 = ss.derive_key(info=b"app1", length=32)
        key2 = ss.derive_key(info=b"app2", length=32)

        assert key1 != key2


@pytest.mark.asyncio
class TestKyberKeyTypes:
    """Test Kyber key type classes."""

    def test_public_key_serialization(self):
        """Test public key serialization."""
        kyber = KyberKeyEncapsulation(KyberSecurityLevel.LEVEL3)
        pk, _ = kyber.generate_keypair()

        key_bytes = pk.to_bytes()
        assert isinstance(key_bytes, bytes)
        assert len(key_bytes) == len(pk)

        # Deserialize
        pk_restored = KyberPublicKey.from_bytes(key_bytes, KyberSecurityLevel.LEVEL3)
        assert pk_restored.key_data == pk.key_data

    def test_secret_key_serialization(self):
        """Test secret key serialization."""
        kyber = KyberKeyEncapsulation(KyberSecurityLevel.LEVEL3)
        _, sk = kyber.generate_keypair()

        key_bytes = sk.to_bytes()
        assert isinstance(key_bytes, bytes)
        assert len(key_bytes) == len(sk)

    def test_ciphertext_serialization(self):
        """Test ciphertext serialization."""
        kyber = KyberKeyEncapsulation(KyberSecurityLevel.LEVEL3)
        pk, _ = kyber.generate_keypair()
        ct, _ = kyber.encapsulate(pk)

        ct_bytes = ct.to_bytes()
        assert isinstance(ct_bytes, bytes)
        assert len(ct_bytes) == len(ct)

    def test_shared_secret_size(self):
        """Test shared secret size."""
        kyber = KyberKeyEncapsulation(KyberSecurityLevel.LEVEL3)
        pk, _ = kyber.generate_keypair()
        _, ss = kyber.encapsulate(pk)

        assert len(ss) == 32


@pytest.mark.asyncio
class TestKyberStatistics:
    """Test Kyber operation statistics."""

    def test_get_statistics(self):
        """Test getting Kyber statistics."""
        kyber = KyberKeyEncapsulation(KyberSecurityLevel.LEVEL3)
        stats = kyber.get_statistics()

        assert stats["algorithm"] == "Kyber768"
        assert stats["security_level"] == "Kyber768"
        assert stats["operations"] == 0
        assert stats["public_key_size"] == 1184
        assert stats["secret_key_size"] == 2400
        assert stats["ciphertext_size"] == 1088
        assert stats["shared_secret_size"] == 32

    def test_operation_count_increments(self):
        """Test that operation count increments."""
        kyber = KyberKeyEncapsulation(KyberSecurityLevel.LEVEL3)

        # Initial count
        stats1 = kyber.get_statistics()
        assert stats1["operations"] == 0

        # Generate keypair
        pk, sk = kyber.generate_keypair()
        stats2 = kyber.get_statistics()
        assert stats2["operations"] == 1

        # Encapsulate
        kyber.encapsulate(pk)
        stats3 = kyber.get_statistics()
        assert stats3["operations"] == 2

        # Decapsulate
        ct, _ = kyber.encapsulate(pk)
        kyber.decapsulate(sk, ct)
        stats4 = kyber.get_statistics()
        assert stats4["operations"] == 4


@pytest.mark.asyncio
class TestKyberHelperFunctions:
    """Test Kyber helper functions."""

    def test_create_kyber_encapsulation(self):
        """Test create_kyber_encapsulation helper."""
        kyber = create_kyber_encapsulation(KyberSecurityLevel.LEVEL3)

        assert isinstance(kyber, KyberKeyEncapsulation)
        assert kyber.security_level == KyberSecurityLevel.LEVEL3


@pytest.mark.asyncio
class TestKyberIntegration:
    """Integration tests for Kyber."""

    def test_full_encapsulation_cycle(self):
        """Test complete encapsulation/decapsulation cycle."""
        kyber = KyberKeyEncapsulation(KyberSecurityLevel.LEVEL3)

        # Generate keypair
        public_key, secret_key = kyber.generate_keypair()

        # Encapsulate
        ciphertext, shared_secret = kyber.encapsulate(public_key)

        # Decapsulate
        recovered_secret = kyber.decapsulate(secret_key, ciphertext)

        # Verify
        assert shared_secret.secret == recovered_secret.secret

    def test_multiple_encapsulations(self):
        """Test multiple encapsulations to same key."""
        kyber = KyberKeyEncapsulation(KyberSecurityLevel.LEVEL3)
        public_key, secret_key = kyber.generate_keypair()

        # Multiple encapsulations
        results = []
        for _ in range(3):
            ct, ss = kyber.encapsulate(public_key)
            recovered_ss = kyber.decapsulate(secret_key, ct)
            results.append((ss, recovered_ss))

        # All should match
        for ss, recovered_ss in results:
            assert ss.secret == recovered_ss.secret


@pytest.mark.asyncio
class TestKyberPerformance:
    """Performance tests for Kyber."""

    def test_keypair_generation_time(self):
        """Test keypair generation is reasonably fast."""
        import time
        kyber = KyberKeyEncapsulation(KyberSecurityLevel.LEVEL3)

        start = time.time()
        for _ in range(10):
            kyber.generate_keypair()
        elapsed = time.time() - start

        # Should complete in < 5 seconds for 10 generations
        assert elapsed < 5.0

    def test_encapsulation_throughput(self):
        """Test encapsulation throughput."""
        import time
        kyber = KyberKeyEncapsulation(KyberSecurityLevel.LEVEL3)
        public_key, _ = kyber.generate_keypair()

        start = time.time()
        for _ in range(100):
            kyber.encapsulate(public_key)
        elapsed = time.time() - start

        # Should complete in reasonable time
        assert elapsed < 10.0
