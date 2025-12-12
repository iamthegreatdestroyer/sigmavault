"""
ΣVAULT Cloud Storage Backend Tests

Unit tests for S3 and Azure Blob storage backends.
Uses mocking to test without actual cloud connections.
"""

import pytest
from unittest.mock import Mock, MagicMock, patch, PropertyMock
from dataclasses import asdict


# ============================================================================
# S3 Backend Tests
# ============================================================================

class TestS3Config:
    """Tests for S3Config dataclass."""
    
    def test_default_values(self):
        """Test S3Config default values."""
        # Import locally to handle missing boto3
        try:
            from sigmavault.drivers.storage.s3_backend import S3Config
        except ImportError:
            pytest.skip("boto3 not installed")
        
        config = S3Config(bucket="test-bucket")
        
        assert config.bucket == "test-bucket"
        assert config.key_prefix == ""
        assert config.region == "us-east-1"
        assert config.endpoint_url is None
        assert config.multipart_threshold == 8 * 1024 * 1024
        assert config.storage_class == "STANDARD"
    
    def test_custom_endpoint(self):
        """Test S3Config with custom endpoint for MinIO."""
        try:
            from sigmavault.drivers.storage.s3_backend import S3Config
        except ImportError:
            pytest.skip("boto3 not installed")
        
        config = S3Config(
            bucket="my-bucket",
            endpoint_url="http://localhost:9000",
            access_key_id="minio",
            secret_access_key="minio123"
        )
        
        assert config.endpoint_url == "http://localhost:9000"
        assert config.access_key_id == "minio"


class TestS3StorageBackend:
    """Tests for S3StorageBackend with mocked boto3."""
    
    @pytest.fixture
    def mock_boto3(self):
        """Mock boto3 module."""
        with patch.dict('sys.modules', {'boto3': MagicMock()}):
            # Also need to mock botocore
            with patch.dict('sys.modules', {
                'botocore': MagicMock(),
                'botocore.config': MagicMock(),
                'botocore.exceptions': MagicMock(),
            }):
                yield
    
    @pytest.fixture
    def mock_s3_client(self):
        """Create a mock S3 client."""
        client = MagicMock()
        client.head_bucket.return_value = {}
        client.head_object.return_value = {'ContentLength': 0}
        client.put_object.return_value = {}
        client.get_object.return_value = {
            'Body': MagicMock(read=lambda: b'')
        }
        return client
    
    def test_import_check(self):
        """Test that HAS_BOTO3 flag is set correctly."""
        from sigmavault.drivers.storage.s3_backend import HAS_BOTO3
        # HAS_BOTO3 will be True if boto3 is installed, False otherwise
        assert isinstance(HAS_BOTO3, bool)
    
    @pytest.mark.skipif(
        not pytest.importorskip("boto3", reason="boto3 not installed"),
        reason="boto3 not installed"
    )
    def test_backend_requires_boto3(self):
        """Test that backend raises ImportError without boto3."""
        # This test verifies the import check mechanism
        from sigmavault.drivers.storage.s3_backend import HAS_BOTO3
        if not HAS_BOTO3:
            with pytest.raises(ImportError):
                from sigmavault.drivers.storage.s3_backend import S3StorageBackend
                S3StorageBackend(S3Config(bucket="test"))


class TestS3StorageBackendWithMocks:
    """Tests for S3StorageBackend using comprehensive mocks."""
    
    @pytest.fixture
    def s3_backend_mocked(self):
        """Create S3StorageBackend with all boto3 calls mocked."""
        try:
            from sigmavault.drivers.storage.s3_backend import S3StorageBackend, S3Config
        except ImportError:
            pytest.skip("boto3 not installed")
        
        # Mock the entire boto3 client
        with patch('sigmavault.drivers.storage.s3_backend.boto3') as mock_boto:
            mock_client = MagicMock()
            mock_boto.client.return_value = mock_client
            
            # Setup mock responses
            mock_client.head_bucket.return_value = {}
            mock_client.head_object.return_value = {'ContentLength': 0}
            mock_client.put_object.return_value = {}
            
            config = S3Config(bucket="test-bucket")
            backend = S3StorageBackend(config, create=True)
            backend._client = mock_client  # Ensure we're using our mock
            
            yield backend, mock_client
    
    def test_read_empty(self, s3_backend_mocked):
        """Test reading from empty backend."""
        backend, mock_client = s3_backend_mocked
        
        # Empty backend
        result = backend.read(0, 100)
        assert result == b''
    
    def test_read_with_data(self, s3_backend_mocked):
        """Test reading data from backend."""
        backend, mock_client = s3_backend_mocked
        
        # Setup mock to return data
        backend._size = 100
        mock_body = MagicMock()
        mock_body.read.return_value = b'Hello S3!'
        mock_client.get_object.return_value = {'Body': mock_body}
        
        result = backend.read(0, 9)
        assert result == b'Hello S3!'
    
    def test_read_negative_offset_raises(self, s3_backend_mocked):
        """Test that negative offset raises ValueError."""
        backend, _ = s3_backend_mocked
        
        with pytest.raises(ValueError):
            backend.read(-1, 10)
    
    def test_write_creates_object(self, s3_backend_mocked):
        """Test writing creates/updates object."""
        backend, mock_client = s3_backend_mocked
        
        # Write to empty backend
        written = backend.write(0, b'test data')
        
        assert written == 9
        assert backend._size == 9
        mock_client.put_object.assert_called()
    
    def test_write_negative_offset_raises(self, s3_backend_mocked):
        """Test that negative offset raises ValueError."""
        backend, _ = s3_backend_mocked
        
        with pytest.raises(ValueError):
            backend.write(-1, b'test')
    
    def test_size_property(self, s3_backend_mocked):
        """Test size() returns correct size."""
        backend, _ = s3_backend_mocked
        
        assert backend.size() == 0
        
        backend._size = 1024
        assert backend.size() == 1024
    
    def test_capabilities(self, s3_backend_mocked):
        """Test capabilities returns correct flags."""
        backend, _ = s3_backend_mocked
        
        from sigmavault.drivers.storage.base import StorageCapabilities
        
        caps = backend.capabilities
        assert StorageCapabilities.RANGE_READ in caps
        assert StorageCapabilities.PERSISTENT in caps
    
    def test_sync_is_noop(self, s3_backend_mocked):
        """Test sync is a no-op for S3."""
        backend, _ = s3_backend_mocked
        
        # Should not raise
        backend.sync()
    
    def test_truncate(self, s3_backend_mocked):
        """Test truncate operations."""
        backend, mock_client = s3_backend_mocked
        
        # Truncate to zero
        backend.truncate(0)
        assert backend._size == 0
    
    def test_delete(self, s3_backend_mocked):
        """Test delete removes object."""
        backend, mock_client = s3_backend_mocked
        
        backend.delete()
        
        mock_client.delete_object.assert_called_once()
        assert backend._size == 0
    
    def test_exists(self, s3_backend_mocked):
        """Test exists check."""
        backend, mock_client = s3_backend_mocked
        
        mock_client.head_object.return_value = {'ContentLength': 100}
        assert backend.exists() is True
    
    def test_bucket_property(self, s3_backend_mocked):
        """Test bucket property."""
        backend, _ = s3_backend_mocked
        assert backend.bucket == "test-bucket"
    
    def test_key_property(self, s3_backend_mocked):
        """Test key property."""
        backend, _ = s3_backend_mocked
        assert backend.key == "vault.dat"
    
    def test_repr(self, s3_backend_mocked):
        """Test string representation."""
        backend, _ = s3_backend_mocked
        
        repr_str = repr(backend)
        assert "S3StorageBackend" in repr_str
        assert "test-bucket" in repr_str


# ============================================================================
# Azure Blob Backend Tests
# ============================================================================

class TestAzureBlobConfig:
    """Tests for AzureBlobConfig dataclass."""
    
    def test_default_values(self):
        """Test AzureBlobConfig default values."""
        try:
            from sigmavault.drivers.storage.azure_blob_backend import AzureBlobConfig
        except ImportError:
            pytest.skip("azure-storage-blob not installed")
        
        config = AzureBlobConfig()
        
        assert config.container_name == "sigmavault"
        assert config.blob_prefix == ""
        assert config.max_block_size == 4 * 1024 * 1024
        assert config.access_tier == "Hot"
    
    def test_connection_string_config(self):
        """Test AzureBlobConfig with connection string."""
        try:
            from sigmavault.drivers.storage.azure_blob_backend import AzureBlobConfig
        except ImportError:
            pytest.skip("azure-storage-blob not installed")
        
        config = AzureBlobConfig(
            connection_string="DefaultEndpointsProtocol=https;AccountName=test;..."
        )
        
        assert config.connection_string is not None


class TestAzureBlobStorageBackend:
    """Tests for AzureBlobStorageBackend with mocked Azure SDK."""
    
    def test_import_check(self):
        """Test that HAS_AZURE_STORAGE flag is set correctly."""
        from sigmavault.drivers.storage.azure_blob_backend import HAS_AZURE_STORAGE
        assert isinstance(HAS_AZURE_STORAGE, bool)


class TestAzureBlobStorageBackendWithMocks:
    """Tests for AzureBlobStorageBackend using comprehensive mocks."""
    
    @pytest.fixture
    def azure_backend_mocked(self):
        """Create AzureBlobStorageBackend with all Azure calls mocked."""
        try:
            from sigmavault.drivers.storage.azure_blob_backend import (
                AzureBlobStorageBackend,
                AzureBlobConfig,
            )
        except ImportError:
            pytest.skip("azure-storage-blob not installed")
        
        # Mock Azure SDK
        with patch('sigmavault.drivers.storage.azure_blob_backend.BlobServiceClient') as mock_service:
            mock_container = MagicMock()
            mock_blob = MagicMock()
            
            # Setup property mocks
            mock_props = MagicMock()
            mock_props.size = 0
            mock_blob.get_blob_properties.return_value = mock_props
            mock_blob.upload_blob.return_value = None
            mock_blob.url = "https://test.blob.core.windows.net/sigmavault/vault.dat"
            
            mock_container.get_container_properties.return_value = {}
            mock_container.get_blob_client.return_value = mock_blob
            
            mock_service.from_connection_string.return_value.get_container_client.return_value = mock_container
            
            config = AzureBlobConfig(
                connection_string="DefaultEndpointsProtocol=https;AccountName=test"
            )
            backend = AzureBlobStorageBackend(config, create=True)
            backend._blob_client = mock_blob
            
            yield backend, mock_blob
    
    def test_read_empty(self, azure_backend_mocked):
        """Test reading from empty backend."""
        backend, mock_blob = azure_backend_mocked
        
        result = backend.read(0, 100)
        assert result == b''
    
    def test_read_with_data(self, azure_backend_mocked):
        """Test reading data from backend."""
        backend, mock_blob = azure_backend_mocked
        
        # Setup mock to return data
        backend._size = 100
        mock_stream = MagicMock()
        mock_stream.readall.return_value = b'Hello Azure!'
        mock_blob.download_blob.return_value = mock_stream
        
        result = backend.read(0, 12)
        assert result == b'Hello Azure!'
    
    def test_read_negative_offset_raises(self, azure_backend_mocked):
        """Test that negative offset raises ValueError."""
        backend, _ = azure_backend_mocked
        
        with pytest.raises(ValueError):
            backend.read(-1, 10)
    
    def test_write_creates_blob(self, azure_backend_mocked):
        """Test writing creates/updates blob."""
        backend, mock_blob = azure_backend_mocked
        
        # Write to empty backend
        written = backend.write(0, b'test data')
        
        assert written == 9
        assert backend._size == 9
        mock_blob.upload_blob.assert_called()
    
    def test_write_negative_offset_raises(self, azure_backend_mocked):
        """Test that negative offset raises ValueError."""
        backend, _ = azure_backend_mocked
        
        with pytest.raises(ValueError):
            backend.write(-1, b'test')
    
    def test_size_property(self, azure_backend_mocked):
        """Test size() returns correct size."""
        backend, _ = azure_backend_mocked
        
        assert backend.size() == 0
        
        backend._size = 2048
        assert backend.size() == 2048
    
    def test_capabilities(self, azure_backend_mocked):
        """Test capabilities returns correct flags."""
        backend, _ = azure_backend_mocked
        
        from sigmavault.drivers.storage.base import StorageCapabilities
        
        caps = backend.capabilities
        assert StorageCapabilities.RANGE_READ in caps
        assert StorageCapabilities.PERSISTENT in caps
    
    def test_sync_is_noop(self, azure_backend_mocked):
        """Test sync is a no-op for Azure."""
        backend, _ = azure_backend_mocked
        
        # Should not raise
        backend.sync()
    
    def test_truncate(self, azure_backend_mocked):
        """Test truncate operations."""
        backend, mock_blob = azure_backend_mocked
        
        # Truncate to zero
        backend.truncate(0)
        assert backend._size == 0
    
    def test_delete(self, azure_backend_mocked):
        """Test delete removes blob."""
        backend, mock_blob = azure_backend_mocked
        
        backend.delete()
        
        mock_blob.delete_blob.assert_called_once()
        assert backend._size == 0
    
    def test_container_name_property(self, azure_backend_mocked):
        """Test container_name property."""
        backend, _ = azure_backend_mocked
        assert backend.container_name == "sigmavault"
    
    def test_blob_name_property(self, azure_backend_mocked):
        """Test blob_name property."""
        backend, _ = azure_backend_mocked
        assert backend.blob_name == "vault.dat"
    
    def test_url_property(self, azure_backend_mocked):
        """Test url property."""
        backend, _ = azure_backend_mocked
        assert "blob.core.windows.net" in backend.url
    
    def test_repr(self, azure_backend_mocked):
        """Test string representation."""
        backend, _ = azure_backend_mocked
        
        repr_str = repr(backend)
        assert "AzureBlobStorageBackend" in repr_str
        assert "sigmavault" in repr_str


# ============================================================================
# Cross-Backend Tests
# ============================================================================

class TestCloudBackendInterface:
    """Tests to verify cloud backends implement StorageBackend correctly."""
    
    def test_s3_is_storage_backend(self):
        """Test S3StorageBackend inherits from StorageBackend."""
        try:
            from sigmavault.drivers.storage.s3_backend import S3StorageBackend
            from sigmavault.drivers.storage.base import StorageBackend
            assert issubclass(S3StorageBackend, StorageBackend)
        except ImportError:
            pytest.skip("boto3 not installed")
    
    def test_azure_is_storage_backend(self):
        """Test AzureBlobStorageBackend inherits from StorageBackend."""
        try:
            from sigmavault.drivers.storage.azure_blob_backend import AzureBlobStorageBackend
            from sigmavault.drivers.storage.base import StorageBackend
            assert issubclass(AzureBlobStorageBackend, StorageBackend)
        except ImportError:
            pytest.skip("azure-storage-blob not installed")


# ============================================================================
# Integration Test Stubs (Require Real Cloud Access)
# ============================================================================

@pytest.mark.skip(reason="Requires real S3 bucket")
class TestS3Integration:
    """Integration tests for S3 backend - requires real S3 access."""
    
    def test_real_s3_roundtrip(self):
        """Test actual S3 read/write cycle."""
        pass


@pytest.mark.skip(reason="Requires real Azure Storage")
class TestAzureBlobIntegration:
    """Integration tests for Azure backend - requires real Azure access."""
    
    def test_real_azure_roundtrip(self):
        """Test actual Azure Blob read/write cycle."""
        pass


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
