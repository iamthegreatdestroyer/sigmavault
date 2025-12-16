#!/usr/bin/env python3
"""
PHASE 9B: Performance Optimization - Verification Script
=========================================================

Verifies all optimization components are operational:
- Part 1: Ryot LLM (Optimized Attention, Batch Inference, Tiered KV Cache)
- Part 2: ΣLANG (Fast Encoder)
- Part 3: ΣVAULT (Parallel I/O)
"""

import sys
import time
from pathlib import Path

# Add parent to path
sys.path.insert(0, str(Path(__file__).parent.parent))


def test_optimized_attention():
    """Test 1: Optimized Attention with Flash Attention."""
    print("\n[TEST 1] Optimized Attention")
    print("-" * 60)
    
    from src.core.engine.optimized_attention import (
        OptimizedAttention, AttentionConfig, MockTensor
    )
    
    config = AttentionConfig(
        num_heads=32,
        head_dim=128,
        use_flash_attention=True,
        chunk_size=512,
    )
    attn = OptimizedAttention(config)
    
    # Create mock tensors
    q = MockTensor(shape=(1, 2048, 4096))
    k = MockTensor(shape=(1, 2048, 4096))
    v = MockTensor(shape=(1, 2048, 4096))
    
    # Forward pass
    start = time.time()
    output = attn.forward(q, k, v, use_cache=True)
    elapsed = (time.time() - start) * 1000
    
    stats = attn.get_stats()
    print(f"  Flash Attention: {config.use_flash_attention}")
    print(f"  Chunk Size: {config.chunk_size}")
    print(f"  Forward Time: {elapsed:.2f}ms")
    print(f"  Cache Size: {stats['cache_size']}")
    print(f"  Flash Chunks: {stats['flash_chunks']}")
    
    # Verify
    assert output is not None, "Output should not be None"
    assert stats['forward_calls'] == 1, "Should have 1 forward call"
    assert stats['cache_hits'] == 1, "Should have cache hit"
    
    print("  [PASS] Optimized Attention operational")
    return True


def test_batch_inference():
    """Test 2: Batch Inference Engine."""
    print("\n[TEST 2] Batch Inference Engine")
    print("-" * 60)
    
    from src.core.engine.batch_inference import (
        BatchInferenceEngine, BatchConfig, BatchRequest
    )
    
    config = BatchConfig(
        max_batch_size=4,
        max_wait_time_ms=50.0,
        max_batch_tokens=8192,
    )
    engine = BatchInferenceEngine(config=config)
    engine.start()
    
    # Submit requests
    requests = []
    for i in range(3):
        req = BatchRequest(
            prompt=f"Test prompt {i}",
            max_tokens=100,
        )
        engine.submit(req)
        requests.append(req)
    
    print(f"  Submitted: {len(requests)} requests")
    print(f"  Max Batch Size: {config.max_batch_size}")
    print(f"  Max Wait Time: {config.max_wait_time_ms}ms")
    
    # Wait for results
    time.sleep(0.2)
    
    stats = engine.get_stats()
    print(f"  Total Requests: {stats.total_requests}")
    print(f"  Total Batches: {stats.total_batches}")
    
    engine.stop()
    
    # Verify
    assert stats.total_requests >= 3, "Should have 3+ requests"
    
    print("  [PASS] Batch Inference operational")
    return True


def test_tiered_kv_cache():
    """Test 3: Tiered KV Cache."""
    print("\n[TEST 3] Tiered KV Cache")
    print("-" * 60)
    
    from src.core.cache.tiered_kv_cache import (
        TieredKVCache, TieredCacheConfig
    )
    
    config = TieredCacheConfig(
        l1_max_entries=5,
        l2_max_entries=10,
        l3_enabled=True,
    )
    cache = TieredKVCache(config)
    
    # Store entries (will trigger tiering)
    for i in range(15):
        cache.put(f"key_{i}", f"value_{i}")
    
    dist = cache.get_tier_distribution()
    print(f"  L1 Entries: {dist['l1']}")
    print(f"  L2 Entries: {dist['l2']}")
    print(f"  L3 Entries: {dist['l3']}")
    
    # Retrieve and check promotion
    result = cache.get("key_0")
    
    stats = cache.get_stats()
    print(f"  Hit Rate: {stats['hit_rate']:.2%}")
    print(f"  Demotions: {stats['demotions']}")
    
    # Verify
    assert dist['l1'] == 5, "L1 should be at capacity"
    assert dist['l2'] == 10, "L2 should be at capacity"
    assert stats['demotions'] > 0, "Should have demotions"
    
    print("  [PASS] Tiered KV Cache operational")
    return True


def test_fast_encoder():
    """Test 4: Fast Glyph Encoder."""
    print("\n[TEST 4] Fast Glyph Encoder")
    print("-" * 60)
    
    from sigmalang.core.fast_encoder import (
        FastGlyphEncoder, EncoderConfig
    )
    
    config = EncoderConfig(
        chunk_size=512,
        max_workers=4,
        enable_cache=True,
    )
    encoder = FastGlyphEncoder(config)
    
    # Encode text
    test_text = "Hello, World! " * 100
    
    start = time.time()
    encoded = encoder.encode_fast(test_text)
    first_time = (time.time() - start) * 1000
    
    # Encode again (should be cached)
    start = time.time()
    cached = encoder.encode_fast(test_text)
    cached_time = (time.time() - start) * 1000
    
    stats = encoder.get_stats()
    print(f"  First Encode: {first_time:.2f}ms")
    print(f"  Cached Encode: {cached_time:.2f}ms")
    print(f"  Cache Hits: {stats.cache_hits}")
    print(f"  Cache Misses: {stats.cache_misses}")
    print(f"  Total Bytes: {stats.total_bytes_encoded}")
    
    # Verify
    assert encoded == cached, "Cached should match"
    assert stats.cache_hits >= 1, "Should have cache hit"
    
    print("  [PASS] Fast Encoder operational")
    return True


def test_parallel_io():
    """Test 5: Parallel I/O Manager."""
    print("\n[TEST 5] Parallel I/O Manager")
    print("-" * 60)
    
    from sigmavault.core.parallel_io import ParallelIOManager
    
    manager = ParallelIOManager(max_concurrent=8)
    
    # Create mock backend
    class MockBackend:
        def __init__(self):
            self._data = {}
        
        def read_chunk(self, chunk_id: str) -> bytes:
            time.sleep(0.001)
            return self._data.get(chunk_id, b"")
        
        def write_chunk(self, chunk_id: str, data: bytes) -> bool:
            time.sleep(0.001)
            self._data[chunk_id] = data
            return True
    
    backend = MockBackend()
    
    # Write chunks
    chunks = {f"chunk_{i}": f"data_{i}".encode() for i in range(10)}
    results = manager.write_chunks_sync(chunks, backend)
    
    print(f"  Wrote: {sum(results.values())}/{len(chunks)} chunks")
    
    # Read chunks
    chunk_ids = list(chunks.keys())
    read_results = manager.read_chunks_sync(chunk_ids, backend)
    
    print(f"  Read: {len(read_results)}/{len(chunk_ids)} chunks")
    
    stats = manager.get_stats()
    print(f"  Total Reads: {stats['reads']}")
    print(f"  Total Writes: {stats['writes']}")
    print(f"  Read Time: {stats['read_time_ms']:.2f}ms")
    print(f"  Write Time: {stats['write_time_ms']:.2f}ms")
    
    # Verify
    assert sum(results.values()) == 10, "All writes should succeed"
    assert len(read_results) == 10, "All reads should succeed"
    
    print("  [PASS] Parallel I/O operational")
    return True


def main():
    """Run all Phase 9B verification tests."""
    print("=" * 70)
    print("  PHASE 9B: PERFORMANCE OPTIMIZATION - VERIFICATION")
    print("=" * 70)
    
    tests = [
        ("Optimized Attention", test_optimized_attention),
        ("Batch Inference", test_batch_inference),
        ("Tiered KV Cache", test_tiered_kv_cache),
        ("Fast Encoder", test_fast_encoder),
        ("Parallel I/O", test_parallel_io),
    ]
    
    results = []
    for name, test_fn in tests:
        try:
            success = test_fn()
            results.append((name, success, None))
        except Exception as e:
            print(f"  [FAIL] {name}: {e}")
            results.append((name, False, str(e)))
    
    # Summary
    print("\n" + "=" * 70)
    print("  TEST SUMMARY")
    print("=" * 70)
    
    passed = sum(1 for _, s, _ in results if s)
    total = len(results)
    
    for name, success, error in results:
        status = "[PASS]" if success else "[FAIL]"
        print(f"  {status} {name}")
        if error:
            print(f"         Error: {error}")
    
    print("\n" + "=" * 70)
    print(f"  RESULTS: {passed}/{total} TESTS PASSED")
    
    if passed == total:
        print("  STATUS: PHASE 9B COMPLETE - ALL OPTIMIZATIONS OPERATIONAL")
    else:
        print(f"  STATUS: {total - passed} FAILURES")
    print("=" * 70 + "\n")
    
    return 0 if passed == total else 1


if __name__ == "__main__":
    exit(main())
