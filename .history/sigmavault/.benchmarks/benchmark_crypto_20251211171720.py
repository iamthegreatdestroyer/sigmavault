"""
ΣVAULT Cryptographic Benchmarks
================================

Benchmarks for key derivation, hash operations, and hybrid key generation.

Components tested:
- Argon2id key derivation (with various parameters)
- Device fingerprint collection
- Hybrid key mixing
- Key state derivation

Copyright 2025 - ΣVAULT Project
"""

import os
import secrets
import hashlib
import time
from typing import Dict

# Add parent to path for imports
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))
sys.path.insert(0, str(Path(__file__).parent))

from benchmark_core import BenchmarkRunner, BenchmarkResult, BenchmarkConfig

try:
    from crypto.hybrid_key import (
        HybridKeyDerivation,
        DeviceFingerprint,
        KeyMode,
    )
    HAS_CRYPTO = True
except ImportError as e:
    print(f"Warning: Could not import crypto module: {e}")
    HAS_CRYPTO = False


def run_crypto_benchmarks() -> Dict[str, BenchmarkResult]:
    """
    Run all cryptographic benchmarks.
    
    Returns:
        Dictionary mapping benchmark names to results
    """
    results = {}
    config = BenchmarkConfig(
        warmup_iterations=2,
        min_iterations=3,
        target_time_seconds=10.0,  # Crypto ops can be slow
    )
    runner = BenchmarkRunner(config)
    
    # ==================================================================
    # 1. HASH OPERATIONS
    # ==================================================================
    
    # SHA-256 benchmark (baseline)
    test_data_1kb = secrets.token_bytes(1024)
    test_data_1mb = secrets.token_bytes(1024 * 1024)
    
    def hash_sha256_1kb():
        return hashlib.sha256(test_data_1kb).digest()
    
    def hash_sha256_1mb():
        return hashlib.sha256(test_data_1mb).digest()
    
    def hash_sha512_1kb():
        return hashlib.sha512(test_data_1kb).digest()
    
    def hash_sha512_1mb():
        return hashlib.sha512(test_data_1mb).digest()
    
    print("\n🔐 Hash Operations")
    print("-" * 40)
    
    result = runner.run(hash_sha256_1kb, "SHA-256 (1 KB)", data_size=1024)
    print(result)
    results["sha256_1kb"] = result
    
    result = runner.run(hash_sha256_1mb, "SHA-256 (1 MB)", data_size=1024*1024)
    print(result)
    results["sha256_1mb"] = result
    
    result = runner.run(hash_sha512_1kb, "SHA-512 (1 KB)", data_size=1024)
    print(result)
    results["sha512_1kb"] = result
    
    result = runner.run(hash_sha512_1mb, "SHA-512 (1 MB)", data_size=1024*1024)
    print(result)
    results["sha512_1mb"] = result
    
    # ==================================================================
    # 2. PBKDF2 BASELINE
    # ==================================================================
    
    print("\n🔑 PBKDF2 Key Derivation (baseline)")
    print("-" * 40)
    
    test_password = b"test_passphrase_for_benchmarking"
    test_salt = secrets.token_bytes(32)
    
    def pbkdf2_10k():
        return hashlib.pbkdf2_hmac('sha256', test_password, test_salt, 10000, dklen=32)
    
    def pbkdf2_100k():
        return hashlib.pbkdf2_hmac('sha256', test_password, test_salt, 100000, dklen=32)
    
    result = runner.run(pbkdf2_10k, "PBKDF2-SHA256 (10k iters)")
    print(result)
    results["pbkdf2_10k"] = result
    
    result = runner.run(pbkdf2_100k, "PBKDF2-SHA256 (100k iters)")
    print(result)
    results["pbkdf2_100k"] = result
    
    # ==================================================================
    # 3. ARGON2ID KEY DERIVATION
    # ==================================================================
    
    if HAS_CRYPTO:
        print("\n🔐 Argon2id Key Derivation")
        print("-" * 40)
        
        try:
            # Test with various memory costs
            deriver = HybridKeyDerivation()
            
            # Standard derivation
            def derive_key_standard():
                return deriver.derive_key(
                    passphrase="benchmark_passphrase",
                    mode=KeyMode.USER_ONLY,
                )
            
            # Low memory config for faster testing
            config_low = BenchmarkConfig(
                warmup_iterations=1,
                min_iterations=3,
                max_iterations=5,
                target_time_seconds=30.0,
            )
            runner_low = BenchmarkRunner(config_low)
            
            result = runner_low.run(derive_key_standard, "Argon2id Key Derivation (USER_ONLY)")
            print(result)
            results["argon2id_user_only"] = result
            
        except Exception as e:
            print(f"⚠️ Argon2id benchmark skipped: {e}")
    
    # ==================================================================
    # 4. DEVICE FINGERPRINT COLLECTION
    # ==================================================================
    
    if HAS_CRYPTO:
        print("\n🖥️ Device Fingerprint Collection")
        print("-" * 40)
        
        try:
            def collect_fingerprint():
                return DeviceFingerprint.collect()
            
            result = runner.run(collect_fingerprint, "Device Fingerprint Collection")
            print(result)
            results["device_fingerprint"] = result
            
        except Exception as e:
            print(f"⚠️ Device fingerprint benchmark skipped: {e}")
    
    # ==================================================================
    # 5. KEY STATE DERIVATION
    # ==================================================================
    
    print("\n🔄 Key State Derivation")
    print("-" * 40)
    
    try:
        from core.dimensional_scatter import KeyState
        
        test_hybrid_key = secrets.token_bytes(64)
        
        def derive_key_state():
            return KeyState.derive(test_hybrid_key)
        
        result = runner.run(derive_key_state, "KeyState Derivation from Hybrid Key")
        print(result)
        results["keystate_derivation"] = result
        
    except Exception as e:
        print(f"⚠️ KeyState derivation benchmark skipped: {e}")
    
    return results


if __name__ == "__main__":
    run_crypto_benchmarks()
