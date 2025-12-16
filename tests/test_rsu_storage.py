"""
RSU Storage Tests
=================
"""

import pytest
from sigmavault.rsu import RSUStorage, RSURetriever, RSUStorageConfig


class TestRSUStorage:
    """Test RSU storage."""
    
    @pytest.fixture
    def storage(self):
        """Create storage for testing."""
        return RSUStorage()
    
    def test_store_retrieve(self, storage):
        """Test basic store and retrieve."""
        glyph_data = b"\x00\x01\x00\x02\x00\x03"
        semantic_hash = 0x123456789ABCDEF0
        
        entry = storage.store(
            glyph_data=glyph_data,
            semantic_hash=semantic_hash,
            original_token_count=100,
        )
        
        assert entry.rsu_id is not None
        assert entry.semantic_hash == semantic_hash
        
        retrieved = storage.retrieve(entry.rsu_id)
        assert retrieved is not None
        assert retrieved.glyph_data == glyph_data
    
    def test_store_with_kv_cache(self, storage):
        """Test storing with KV cache."""
        glyph_data = b"\x00\x01"
        kv_data = b"\x00" * 1000
        
        entry = storage.store(
            glyph_data=glyph_data,
            semantic_hash=0x1234,
            original_token_count=50,
            kv_cache_data=kv_data,
        )
        
        assert entry.has_kv_cache
        assert entry.kv_cache_size_bytes == 1000
        
        retrieved = storage.retrieve(entry.rsu_id)
        assert retrieved.kv_cache_data == kv_data
    
    def test_find_similar(self, storage):
        """Test semantic similarity search."""
        # Store multiple RSUs
        for i in range(5):
            storage.store(
                glyph_data=b"\x00\x01",
                semantic_hash=0x1000 + i,
                original_token_count=10,
            )
        
        matches = storage.find_similar(0x1002, threshold=0.9)
        assert len(matches) > 0
    
    def test_conversation_chain(self, storage):
        """Test conversation chaining."""
        conv_id = "conv_test_123"
        
        # Store chain of RSUs
        parent_id = None
        for i in range(3):
            entry = storage.store(
                glyph_data=f"data_{i}".encode(),
                semantic_hash=0x1000 + i,
                original_token_count=10,
                conversation_id=conv_id,
                parent_rsu_id=parent_id,
            )
            parent_id = entry.rsu_id
        
        chain = storage.get_conversation_chain(conv_id)
        assert len(chain) == 3
    
    def test_archive(self, storage):
        """Test archiving RSUs."""
        entry = storage.store(
            glyph_data=b"\x00\x01",
            semantic_hash=0x5678,
            original_token_count=10,
        )
        
        assert storage.archive(entry.rsu_id)
        
        # Archived RSUs can't be retrieved
        assert storage.retrieve(entry.rsu_id) is None
    
    def test_statistics(self, storage):
        """Test statistics retrieval."""
        storage.store(
            glyph_data=b"\x00\x01",
            semantic_hash=0x1111,
            original_token_count=100,
        )
        
        stats = storage.get_statistics()
        assert stats["total_rsus"] == 1
        assert stats["active_rsus"] == 1
        assert stats["total_original_tokens"] == 100


def test_rsu_storage_standalone():
    """Quick standalone test."""
    storage = RSUStorage()
    
    entry = storage.store(
        glyph_data=b"\x00\x01\x00\x02\x00\x03\x00\x04",
        semantic_hash=0xDEADBEEF12345678,
        original_token_count=100,
        kv_cache_data=b"\x00" * 500,
    )
    
    print(f"\nStored RSU: {entry.rsu_id}")
    print(f"Compression ratio: {entry.compression_ratio:.1f}x")
    print(f"8D coordinates: {entry.vault_coordinates}")
    
    retrieved = storage.retrieve(entry.rsu_id)
    print(f"Retrieved: {len(retrieved.glyph_data)} bytes glyphs")
    print(f"KV cache: {len(retrieved.kv_cache_data)} bytes")
    
    # Test retriever
    retriever = RSURetriever(storage)
    result = retriever.retrieve_best_match(0xDEADBEEF12345678)
    assert result is not None
    print(f"Retriever similarity: {result.similarity:.2f}")
    
    # Test statistics
    stats = storage.get_statistics()
    print(f"Total RSUs: {stats['total_rsus']}")
    print(f"Average compression: {stats['average_compression_ratio']:.1f}x")
    
    print("\n✓ RSU storage test passed")


if __name__ == "__main__":
    test_rsu_storage_standalone()
