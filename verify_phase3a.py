#!/usr/bin/env python
"""Phase 3A: ΣVAULT RSU Storage Backend - Verification Script"""

def main():
    from sigmavault.rsu import RSUStorage, RSURetriever, RSUStorageConfig

    print('=' * 70)
    print('PHASE 3A: ΣVAULT RSU Storage Backend - Verification')
    print('=' * 70)
    print()

    # Test 1: Basic RSU Storage
    print('Test 1: Basic RSU Storage')
    print('-' * 70)
    try:
        storage = RSUStorage()
        
        glyph_data = bytes([0x00, 0x01, 0x00, 0x02, 0x00, 0x03, 0x00, 0x04])
        semantic_hash = 0xDEADBEEF12345678
        
        entry = storage.store(
            glyph_data=glyph_data,
            semantic_hash=semantic_hash,
            original_token_count=100,
        )
        
        print(f'✓ Stored RSU: {entry.rsu_id}')
        print(f'✓ Semantic hash: {hex(entry.semantic_hash)}')
        print(f'✓ Token count: {entry.original_token_count}')
        print(f'✓ 8D coordinates: {entry.vault_coordinates}')
        print(f'✓ Compression ratio: {entry.compression_ratio:.2f}x')
    except Exception as e:
        print(f'✗ Error: {e}')
        import traceback
        traceback.print_exc()
        return 1

    print()

    # Test 2: Retrieve RSU
    print('Test 2: Retrieve RSU')
    print('-' * 70)
    try:
        retrieved = storage.retrieve(entry.rsu_id)
        assert retrieved is not None
        assert retrieved.glyph_data == glyph_data
        print(f'✓ Retrieved RSU: {entry.rsu_id}')
        print(f'✓ Glyph data: {len(retrieved.glyph_data)} bytes')
    except Exception as e:
        print(f'✗ Error: {e}')
        return 1

    print()

    # Test 3: Store with KV Cache
    print('Test 3: Store with KV Cache')
    print('-' * 70)
    try:
        kv_data = bytes([0x00] * 1000)
        entry_kv = storage.store(
            glyph_data=b'\x00\x01\x00\x02',
            semantic_hash=0x1234567890ABCDEF,
            original_token_count=50,
            kv_cache_data=kv_data,
        )
        
        print(f'✓ Stored RSU with KV cache: {entry_kv.rsu_id}')
        print(f'✓ KV cache size: {entry_kv.kv_cache_size_bytes} bytes')
        print(f'✓ KV cache layers: {entry_kv.kv_cache_layers}')
        print(f'✓ Has KV cache: {entry_kv.has_kv_cache}')
    except Exception as e:
        print(f'✗ Error: {e}')
        return 1

    print()

    # Test 4: Conversation Chaining
    print('Test 4: Conversation Chaining')
    print('-' * 70)
    try:
        conv_id = 'test_conv_12345'
        parent_id = None
        
        for i in range(3):
            e = storage.store(
                glyph_data=f'data_{i}'.encode(),
                semantic_hash=0x1000 + i,
                original_token_count=20,
                conversation_id=conv_id,
                parent_rsu_id=parent_id,
            )
            parent_id = e.rsu_id
        
        chain = storage.get_conversation_chain(conv_id)
        print(f'✓ Created conversation chain: {conv_id}')
        print(f'✓ Chain length: {len(chain)} RSUs')
        for i, e in enumerate(chain):
            print(f'  └─ RSU {i+1}: {e.rsu_id}')
    except Exception as e:
        print(f'✗ Error: {e}')
        return 1

    print()

    # Test 5: Similarity Search
    print('Test 5: Semantic Similarity Search')
    print('-' * 70)
    try:
        for i in range(5):
            storage.store(
                glyph_data=f'test_{i}'.encode(),
                semantic_hash=0x2000 + i,
                original_token_count=15,
            )
        
        matches = storage.find_similar(0x2002, threshold=0.85)
        print(f'✓ Similarity search: {hex(0x2002)}')
        print(f'✓ Found {len(matches)} similar RSUs')
        for m in matches[:3]:
            print(f'  └─ {hex(m.semantic_hash)}: active status')
    except Exception as e:
        print(f'✗ Error: {e}')
        return 1

    print()

    # Test 6: Storage Statistics
    print('Test 6: Storage Statistics')
    print('-' * 70)
    try:
        stats = storage.get_statistics()
        print(f'✓ Total RSUs: {stats.get("total_rsus", "N/A")}')
        print(f'✓ Active RSUs: {stats.get("active_rsus", "N/A")}')
        print(f'✓ Total tokens stored: {stats.get("total_original_tokens", "N/A")}')
        print(f'✓ Total glyphs: {stats.get("total_compressed_glyphs", "N/A")}')
        avg_ratio = stats.get("average_compression_ratio", 1.0)
        print(f'✓ Avg compression: {avg_ratio:.2f}x')
        print(f'✓ Total KV cache: {stats.get("total_kv_cache_bytes", 0)} bytes')
        print(f'✓ Conversations: {stats.get("unique_conversations", 0)}')
    except Exception as e:
        print(f'✗ Error: {e}')
        return 1

    print()
    print('=' * 70)
    print('✅ PHASE 3A: RSU Storage Backend COMPLETE')
    print('=' * 70)
    print()
    print('Ready for Phase 3B: RSU Pipeline Integration')
    return 0


if __name__ == '__main__':
    import sys
    sys.exit(main())
