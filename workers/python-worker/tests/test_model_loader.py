"""
Tests for Custom Model Loading (TASK-8.2)

Tests:
- Model metadata validation
- Dynamic module loading
- Download from URL
- Download from GCS (mocked)
- create_model() extraction
- create_dataloader() extraction
- Error handling
"""

import pytest
from pathlib import Path
import tempfile
import shutil
from unittest.mock import Mock, patch, MagicMock

from meshml_worker.training.model_loader import (
    ModelLoader,
    ModelMetadata,
    create_model_loader
)


# ==================== Fixtures ====================

@pytest.fixture
def temp_dir():
    """Create temporary directory"""
    temp_path = Path(tempfile.mkdtemp())
    yield temp_path
    shutil.rmtree(temp_path, ignore_errors=True)


@pytest.fixture
def model_loader(temp_dir):
    """Create model loader"""
    return ModelLoader(models_dir=temp_dir / "models")


@pytest.fixture
def example_model_file():
    """Get path to example model file"""
    # Use the example model we created
    example_path = Path(__file__).parent.parent / "examples" / "example_model.py"
    if example_path.exists():
        yield example_path
        return
    
    # Create a simple test model if example doesn't exist
    test_model_content = """
import torch
import torch.nn as nn

MODEL_METADATA = {
    "name": "TestModel",
    "version": "1.0.0",
    "framework": "pytorch",
    "input_shape": [3, 224, 224],
    "output_shape": [1000]
}

def create_model(device="cpu", **kwargs):
    model = nn.Linear(10, 10)
    return model.to(device)

def create_dataloader(data_path, batch_size=32, **kwargs):
    from torch.utils.data import DataLoader, TensorDataset
    dataset = TensorDataset(torch.randn(100, 10), torch.randint(0, 10, (100,)))
    return DataLoader(dataset, batch_size=batch_size)
"""
    
    temp_file = Path(tempfile.mktemp(suffix=".py"))
    temp_file.write_text(test_model_content)
    yield temp_file
    if temp_file.exists():
        temp_file.unlink()


# ==================== Test Model Metadata ====================

class TestModelMetadata:
    """Test model metadata validation"""
    
    def test_valid_metadata(self):
        """Test valid metadata"""
        metadata_dict = {
            "name": "TestModel",
            "version": "1.0.0",
            "framework": "pytorch",
            "input_shape": [3, 224, 224],
            "output_shape": [1000]
        }
        
        metadata = ModelMetadata(metadata_dict)
        
        assert metadata["name"] == "TestModel"
        assert metadata.get("version") == "1.0.0"
    
    def test_missing_required_field(self):
        """Test metadata with missing required field"""
        metadata_dict = {
            "name": "TestModel",
            "version": "1.0.0",
            # Missing framework, input_shape, output_shape
        }
        
        with pytest.raises(ValueError, match="missing required fields"):
            ModelMetadata(metadata_dict)
    
    def test_invalid_framework(self):
        """Test metadata with invalid framework"""
        metadata_dict = {
            "name": "TestModel",
            "version": "1.0.0",
            "framework": "invalid_framework",
            "input_shape": [3, 224, 224],
            "output_shape": [1000]
        }
        
        with pytest.raises(ValueError, match="Unsupported framework"):
            ModelMetadata(metadata_dict)
    
    def test_optional_fields(self):
        """Test metadata with optional fields"""
        metadata_dict = {
            "name": "TestModel",
            "version": "1.0.0",
            "framework": "pytorch",
            "input_shape": [3, 224, 224],
            "output_shape": [1000],
            "description": "Test model",
            "author": "Test Author",
            "tags": ["vision", "classification"]
        }
        
        metadata = ModelMetadata(metadata_dict)
        
        assert metadata["description"] == "Test model"
        assert metadata["author"] == "Test Author"
        assert "vision" in metadata["tags"]


# ==================== Test Model Loader ====================

class TestModelLoader:
    """Test model loader functionality"""
    
    def test_loader_initialization(self, temp_dir):
        """Test loader initialization"""
        loader = ModelLoader(models_dir=temp_dir / "models")
        
        assert loader.models_dir.exists()
        assert loader.use_cache is True
    
    def test_load_local_model(self, model_loader, example_model_file):
        """Test loading model from local file"""
        create_model, create_dataloader, metadata = model_loader.load_model(
            model_source=str(example_model_file),
            model_id="test-model"
        )
        
        assert callable(create_model)
        assert metadata["framework"] == "pytorch"
    
    def test_validate_module_with_metadata(self, model_loader, example_model_file):
        """Test module validation with MODEL_METADATA"""
        module = model_loader.load_model_module(example_model_file, "test-model")
        
        # Should not raise
        model_loader.validate_model_module(module)
    
    def test_validate_module_without_metadata(self, model_loader, temp_dir):
        """Test module validation without MODEL_METADATA"""
        # Create model file without metadata
        model_file = temp_dir / "bad_model.py"
        model_file.write_text("""
def create_model():
    return None
""")
        
        module = model_loader.load_model_module(model_file, "bad-model")
        
        with pytest.raises(ValueError, match="missing MODEL_METADATA"):
            model_loader.validate_model_module(module)
    
    def test_validate_module_without_create_model(self, model_loader, temp_dir):
        """Test module validation without create_model()"""
        # Create model file without create_model
        model_file = temp_dir / "bad_model.py"
        model_file.write_text("""
MODEL_METADATA = {
    "name": "Test",
    "version": "1.0",
    "framework": "pytorch",
    "input_shape": [1],
    "output_shape": [1]
}
""")
        
        module = model_loader.load_model_module(model_file, "bad-model")
        
        with pytest.raises(ValueError, match="missing create_model"):
            model_loader.validate_model_module(module)


# ==================== Test Download from URL ====================

class TestDownloadFromURL:
    """Test downloading models from HTTP/HTTPS URLs"""
    
    @patch('meshml_worker.training.model_loader.requests.get')
    def test_download_from_http(self, mock_get, model_loader):
        """Test downloading model from HTTP URL"""
        # Mock response
        mock_response = Mock()
        mock_response.content = b"# Test model code"
        mock_response.raise_for_status = Mock()
        mock_get.return_value = mock_response
        
        url = "http://example.com/model.py"
        model_file = model_loader.download_model_from_url(
            url=url,
            model_id="test-model"
        )
        
        assert model_file.exists()
        assert model_file.read_bytes() == b"# Test model code"
        mock_get.assert_called_once()
    
    @patch('meshml_worker.training.model_loader.requests.get')
    def test_download_from_https(self, mock_get, model_loader):
        """Test downloading model from HTTPS URL"""
        mock_response = Mock()
        mock_response.content = b"# Test model code"
        mock_response.raise_for_status = Mock()
        mock_get.return_value = mock_response
        
        url = "https://example.com/model.py"
        model_file = model_loader.download_model_from_url(
            url=url,
            model_id="test-model"
        )
        
        assert model_file.exists()
    
    @patch('meshml_worker.training.model_loader.requests.get')
    def test_download_with_cache(self, mock_get, model_loader):
        """Test using cached model file"""
        # First download
        mock_response = Mock()
        mock_response.content = b"# Test model code"
        mock_response.raise_for_status = Mock()
        mock_get.return_value = mock_response
        
        url = "http://example.com/model.py"
        model_file1 = model_loader.download_model_from_url(url, "test-model")
        
        # Second download (should use cache)
        model_file2 = model_loader.download_model_from_url(url, "test-model")
        
        assert model_file1 == model_file2
        # Should only call once (cached)
        assert mock_get.call_count == 1
    
    @patch('meshml_worker.training.model_loader.requests.get')
    def test_download_force_redownload(self, mock_get, model_loader):
        """Test forcing re-download"""
        mock_response = Mock()
        mock_response.content = b"# Test model code"
        mock_response.raise_for_status = Mock()
        mock_get.return_value = mock_response
        
        url = "http://example.com/model.py"
        
        # First download
        model_loader.download_model_from_url(url, "test-model")
        
        # Force re-download
        model_loader.download_model_from_url(url, "test-model", force_download=True)
        
        # Should call twice
        assert mock_get.call_count == 2
    
    @patch('meshml_worker.training.model_loader.requests.get')
    def test_download_failure(self, mock_get, model_loader):
        """Test download failure handling"""
        mock_get.side_effect = Exception("Network error")
        
        with pytest.raises(RuntimeError, match="Failed to download"):
            model_loader.download_model_from_url(
                url="http://example.com/model.py",
                model_id="test-model"
            )


# ==================== Test Download from GCS ====================

class TestDownloadFromGCS:
    """Test downloading models from Google Cloud Storage"""
    
    @patch('meshml_worker.training.model_loader.GCS_AVAILABLE', True)
    @patch('meshml_worker.training.model_loader.storage')
    def test_download_from_gcs(self, mock_storage, model_loader):
        """Test downloading model from GCS"""
        # Mock GCS client
        mock_client = MagicMock()
        mock_bucket = MagicMock()
        mock_blob = MagicMock()
        
        mock_storage.Client.return_value = mock_client
        mock_client.bucket.return_value = mock_bucket
        mock_bucket.blob.return_value = mock_blob
        
        # Mock download_to_filename to actually create the file
        def create_file(filename):
            Path(filename).write_text("# Downloaded model")
        mock_blob.download_to_filename.side_effect = create_file
        
        model_file = model_loader.download_model_from_gcs(
            bucket_name="my-bucket",
            blob_name="models/model.py",
            model_id="test-model"
        )
        
        assert model_file.exists()
        mock_blob.download_to_filename.assert_called_once()
    
    @patch('meshml_worker.training.model_loader.GCS_AVAILABLE', True)
    @patch('meshml_worker.training.model_loader.storage')
    def test_download_from_gcs_with_cache(self, mock_storage, model_loader):
        """Test GCS download with cache"""
        # Create cached file
        model_file = model_loader.models_dir / "test-model_model.py"
        model_file.write_text("# Cached")
        
        # Should use cache, not call GCS
        result = model_loader.download_model_from_gcs(
            bucket_name="my-bucket",
            blob_name="models/model.py",
            model_id="test-model"
        )
        
        assert result == model_file
        mock_storage.Client.assert_not_called()


# ==================== Test Load Model Integration ====================

class TestLoadModelIntegration:
    """Integration tests for loading models"""
    
    def test_load_from_local_file(self, model_loader, example_model_file):
        """Test complete flow: load from local file"""
        create_model, create_dataloader, metadata = model_loader.load_model(
            model_source=str(example_model_file),
            model_id="local-model"
        )
        
        # Test functions are callable
        assert callable(create_model)
        
        # Test metadata
        assert metadata["framework"] == "pytorch"
        assert "name" in metadata.metadata
    
    def test_create_model_execution(self, model_loader, example_model_file):
        """Test actually calling create_model()"""
        pytest.importorskip("torch")
        
        create_model, _, metadata = model_loader.load_model(
            model_source=str(example_model_file),
            model_id="exec-test"
        )
        
        # Create model instance
        model = create_model(device="cpu")
        
        # Should be a PyTorch module
        import torch.nn as nn
        assert isinstance(model, nn.Module)
    
    @patch('meshml_worker.training.model_loader.requests.get')
    def test_load_from_url(self, mock_get, model_loader, example_model_file):
        """Test loading from URL"""
        # Mock HTTP response with real model code
        mock_response = Mock()
        mock_response.content = example_model_file.read_bytes()
        mock_response.raise_for_status = Mock()
        mock_get.return_value = mock_response
        
        create_model, create_dataloader, metadata = model_loader.load_model(
            model_source="https://example.com/model.py",
            model_id="url-model"
        )
        
        assert callable(create_model)
        assert metadata["framework"] == "pytorch"
    
    def test_load_gcs_url_parsing(self, model_loader):
        """Test GCS URL parsing"""
        with patch.object(model_loader, 'download_model_from_gcs') as mock_download:
            with patch.object(model_loader, 'load_model_module'):
                with patch.object(model_loader, 'validate_model_module'):
                    with patch.object(model_loader, 'get_model_functions') as mock_get:
                        # Mock return value
                        mock_get.return_value = (lambda: None, None, Mock(metadata={}))
                        mock_download.return_value = Path("/tmp/model.py")
                        
                        try:
                            model_loader.load_model(
                                model_source="gs://my-bucket/path/to/model.py",
                                model_id="gcs-model"
                            )
                        except:
                            pass
                        
                        # Check GCS download was called with correct params
                        mock_download.assert_called_once()
                        call_args = mock_download.call_args
                        assert call_args[1]["bucket_name"] == "my-bucket"
                        assert call_args[1]["blob_name"] == "path/to/model.py"


# ==================== Test Error Handling ====================

class TestErrorHandling:
    """Test error handling"""
    
    def test_load_nonexistent_file(self, model_loader):
        """Test loading non-existent file"""
        with pytest.raises(FileNotFoundError):
            model_loader.load_model(
                model_source="/nonexistent/model.py",
                model_id="bad-model"
            )
    
    def test_invalid_gcs_url(self, model_loader):
        """Test invalid GCS URL"""
        with pytest.raises(ValueError, match="Invalid GCS URL"):
            model_loader.load_model(
                model_source="gs://invalid-url",
                model_id="bad-model"
            )
    
    def test_load_invalid_python_file(self, model_loader, temp_dir):
        """Test loading invalid Python file"""
        # Create invalid Python file
        bad_file = temp_dir / "bad.py"
        bad_file.write_text("this is not valid python }{")
        
        with pytest.raises(RuntimeError):
            model_loader.load_model(
                model_source=str(bad_file),
                model_id="bad-model"
            )


# ==================== Test Cache Management ====================

class TestCacheManagement:
    """Test cache management"""
    
    def test_clear_cache(self, model_loader, example_model_file):
        """Test clearing cache"""
        # Load a model
        model_loader.load_model(
            model_source=str(example_model_file),
            model_id="cached-model"
        )
        
        assert len(model_loader._loaded_modules) > 0
        
        # Clear cache
        model_loader.clear_cache()
        
        assert len(model_loader._loaded_modules) == 0
    
    def test_module_caching(self, model_loader, example_model_file):
        """Test module is cached after loading"""
        # Load twice
        model_loader.load_model(str(example_model_file), "test-1")
        model_loader.load_model(str(example_model_file), "test-2")
        
        # Different model IDs = different cached modules
        assert len(model_loader._loaded_modules) == 2


# ==================== Test Helper Function ====================

class TestHelperFunctions:
    """Test helper functions"""
    
    def test_create_model_loader(self, temp_dir):
        """Test create_model_loader helper"""
        loader = create_model_loader(temp_dir / "models")
        
        assert isinstance(loader, ModelLoader)
        assert loader.models_dir.exists()
