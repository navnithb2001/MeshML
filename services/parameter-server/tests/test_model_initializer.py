"""
Comprehensive tests for Model Initializer Service

Tests model initialization, weight strategies, GCS integration,
validation, and error handling.
"""

import pytest
import torch
import torch.nn as nn
from unittest.mock import Mock, MagicMock, AsyncMock, patch
from typing import Dict, Any
import tempfile
import os

from app.services.model_initializer import (
    ModelInitializerService,
    ModelConfig,
    ModelMetadata,
    InitializedModel,
    InitializationStrategy,
    ModelStatus
)


# ==================== Fixtures ====================

@pytest.fixture
def temp_dir():
    """Temporary directory for tests"""
    with tempfile.TemporaryDirectory() as tmp_dir:
        yield tmp_dir


@pytest.fixture
def sample_model_code():
    """Sample model.py code"""
    return '''
import torch
import torch.nn as nn

MODEL_METADATA = {
    "name": "SimpleNet",
    "version": "1.0.0",
    "framework": "pytorch",
    "input_shape": (3, 32, 32),
    "output_shape": (10,),
    "description": "Simple convolutional neural network",
    "author": "Test Author",
    "tags": ["cnn", "classification"]
}

def create_model(num_classes=10, **kwargs):
    """Create a simple CNN model"""
    return nn.Sequential(
        nn.Conv2d(3, 16, kernel_size=3, padding=1),
        nn.ReLU(),
        nn.MaxPool2d(2),
        nn.Conv2d(16, 32, kernel_size=3, padding=1),
        nn.ReLU(),
        nn.MaxPool2d(2),
        nn.Flatten(),
        nn.Linear(32 * 8 * 8, num_classes)
    )
'''


@pytest.fixture
def sample_model_path(temp_dir, sample_model_code):
    """Create sample model.py file"""
    model_path = os.path.join(temp_dir, "model.py")
    with open(model_path, "w") as f:
        f.write(sample_model_code)
    return model_path


@pytest.fixture
def mock_gcs_client():
    """Mock GCS client"""
    client = MagicMock()
    bucket = MagicMock()
    blob = MagicMock()
    
    client.bucket.return_value = bucket
    bucket.blob.return_value = blob
    
    return client


@pytest.fixture
def model_initializer_service(temp_dir):
    """Model initializer service instance"""
    return ModelInitializerService(
        default_device="cpu",
        temp_dir=temp_dir
    )


# ==================== Test Model Validation ====================

class TestModelValidation:
    """Test model import and validation"""
    
    def test_import_and_validate_model(self, model_initializer_service, sample_model_path):
        """Test importing and validating a model"""
        create_model_fn, metadata = model_initializer_service._import_and_validate_model(
            sample_model_path
        )
        
        # Check function
        assert callable(create_model_fn)
        
        # Check metadata
        assert metadata.name == "SimpleNet"
        assert metadata.version == "1.0.0"
        assert metadata.framework == "pytorch"
        assert metadata.input_shape == (3, 32, 32)
        assert metadata.output_shape == (10,)
        assert "cnn" in metadata.tags
    
    def test_missing_create_model_function(self, model_initializer_service, temp_dir):
        """Test validation fails for missing create_model()"""
        # Create invalid model.py
        invalid_path = os.path.join(temp_dir, "invalid.py")
        with open(invalid_path, "w") as f:
            f.write("# No create_model() function\n")
        
        with pytest.raises(ValueError, match="must define create_model"):
            model_initializer_service._import_and_validate_model(invalid_path)
    
    def test_missing_model_metadata(self, model_initializer_service, temp_dir):
        """Test validation fails for missing MODEL_METADATA"""
        invalid_path = os.path.join(temp_dir, "invalid.py")
        with open(invalid_path, "w") as f:
            f.write("def create_model():\n    pass\n")
        
        with pytest.raises(ValueError, match="must define MODEL_METADATA"):
            model_initializer_service._import_and_validate_model(invalid_path)
    
    def test_invalid_framework(self, model_initializer_service, temp_dir):
        """Test validation fails for non-PyTorch framework"""
        invalid_path = os.path.join(temp_dir, "invalid.py")
        with open(invalid_path, "w") as f:
            f.write('''
MODEL_METADATA = {
    "name": "Test",
    "version": "1.0",
    "framework": "tensorflow"
}

def create_model():
    pass
''')
        
        with pytest.raises(ValueError, match="Only PyTorch models supported"):
            model_initializer_service._import_and_validate_model(invalid_path)


# ==================== Test Weight Initialization ====================

class TestWeightInitialization:
    """Test different weight initialization strategies"""
    
    def test_random_initialization(self, model_initializer_service):
        """Test random initialization"""
        model = nn.Linear(10, 5)
        config = ModelConfig(
            model_id="test",
            gcs_model_path="gs://bucket/model.py",
            initialization_strategy=InitializationStrategy.RANDOM,
            seed=42
        )
        
        # Initialize
        model_initializer_service._initialize_weights(model, config)
        
        # Check weights are not zero
        assert not torch.allclose(model.weight, torch.zeros_like(model.weight))
    
    def test_zero_initialization(self, model_initializer_service):
        """Test zero initialization"""
        model = nn.Linear(10, 5)
        config = ModelConfig(
            model_id="test",
            gcs_model_path="gs://bucket/model.py",
            initialization_strategy=InitializationStrategy.ZEROS
        )
        
        model_initializer_service._initialize_weights(model, config)
        
        # Check all weights are zero
        assert torch.allclose(model.weight, torch.zeros_like(model.weight))
        assert torch.allclose(model.bias, torch.zeros_like(model.bias))
    
    def test_ones_initialization(self, model_initializer_service):
        """Test ones initialization"""
        model = nn.Linear(10, 5)
        config = ModelConfig(
            model_id="test",
            gcs_model_path="gs://bucket/model.py",
            initialization_strategy=InitializationStrategy.ONES
        )
        
        model_initializer_service._initialize_weights(model, config)
        
        # Check all weights are one
        assert torch.allclose(model.weight, torch.ones_like(model.weight))
    
    def test_xavier_initialization(self, model_initializer_service):
        """Test Xavier uniform initialization"""
        model = nn.Sequential(
            nn.Linear(10, 5),
            nn.ReLU(),
            nn.Linear(5, 2)
        )
        config = ModelConfig(
            model_id="test",
            gcs_model_path="gs://bucket/model.py",
            initialization_strategy=InitializationStrategy.XAVIER
        )
        
        model_initializer_service._initialize_weights(model, config)
        
        # Xavier initialization should produce values in reasonable range
        for module in model.modules():
            if isinstance(module, nn.Linear):
                assert module.weight.std() < 1.0  # Reasonable variance
    
    def test_kaiming_initialization(self, model_initializer_service):
        """Test Kaiming normal initialization"""
        model = nn.Sequential(
            nn.Linear(10, 5),
            nn.ReLU(),
            nn.Linear(5, 2)
        )
        config = ModelConfig(
            model_id="test",
            gcs_model_path="gs://bucket/model.py",
            initialization_strategy=InitializationStrategy.KAIMING
        )
        
        model_initializer_service._initialize_weights(model, config)
        
        # Kaiming initialization should produce values in reasonable range
        for module in model.modules():
            if isinstance(module, nn.Linear):
                assert module.weight.std() < 1.0  # Reasonable variance


# ==================== Test Model Initialization ====================

class TestModelInitialization:
    """Test full model initialization workflow"""
    
    @pytest.mark.asyncio
    async def test_initialize_model_success(
        self,
        model_initializer_service,
        sample_model_path,
        temp_dir
    ):
        """Test successful model initialization"""
        # Mock GCS download to return local file
        async def mock_download(gcs_path):
            return sample_model_path
        
        model_initializer_service._download_model_from_gcs = mock_download
        
        # Initialize model
        config = ModelConfig(
            model_id="test_model",
            gcs_model_path="gs://bucket/model.py",
            initialization_strategy=InitializationStrategy.RANDOM,
            device="cpu",
            seed=42,
            model_kwargs={"num_classes": 10}
        )
        
        initialized_model = await model_initializer_service.initialize_model(config)
        
        # Verify
        assert initialized_model.status == ModelStatus.READY
        assert initialized_model.model is not None
        assert isinstance(initialized_model.model, nn.Module)
        assert initialized_model.metadata.name == "SimpleNet"
        assert initialized_model.num_parameters > 0
        assert initialized_model.checksum is not None
    
    @pytest.mark.asyncio
    async def test_initialize_model_with_different_kwargs(
        self,
        model_initializer_service,
        sample_model_path
    ):
        """Test model initialization with custom kwargs"""
        async def mock_download(gcs_path):
            return sample_model_path
        
        model_initializer_service._download_model_from_gcs = mock_download
        
        config = ModelConfig(
            model_id="test_model_20",
            gcs_model_path="gs://bucket/model.py",
            model_kwargs={"num_classes": 20}  # Different number of classes
        )
        
        initialized_model = await model_initializer_service.initialize_model(config)
        
        assert initialized_model.status == ModelStatus.READY
        # Model should have different architecture with 20 classes
    
    @pytest.mark.asyncio
    async def test_initialize_model_failure(self, model_initializer_service, temp_dir):
        """Test model initialization failure"""
        # Create invalid model file
        invalid_path = os.path.join(temp_dir, "invalid.py")
        with open(invalid_path, "w") as f:
            f.write("# Invalid model\n")
        
        async def mock_download(gcs_path):
            return invalid_path
        
        model_initializer_service._download_model_from_gcs = mock_download
        
        config = ModelConfig(
            model_id="invalid_model",
            gcs_model_path="gs://bucket/invalid.py"
        )
        
        with pytest.raises(RuntimeError):
            await model_initializer_service.initialize_model(config)
        
        # Model should be in failed state
        failed_model = model_initializer_service.get_model("invalid_model")
        assert failed_model.status == ModelStatus.FAILED
        assert failed_model.error_message is not None


# ==================== Test Model Management ====================

class TestModelManagement:
    """Test model registry management"""
    
    @pytest.mark.asyncio
    async def test_get_model(self, model_initializer_service, sample_model_path):
        """Test getting a model by ID"""
        async def mock_download(gcs_path):
            return sample_model_path
        
        model_initializer_service._download_model_from_gcs = mock_download
        
        config = ModelConfig(
            model_id="test_model",
            gcs_model_path="gs://bucket/model.py"
        )
        
        await model_initializer_service.initialize_model(config)
        
        # Get model
        model = model_initializer_service.get_model("test_model")
        
        assert model is not None
        assert model.model_id == "test_model"
        assert model.status == ModelStatus.READY
    
    @pytest.mark.asyncio
    async def test_list_models(self, model_initializer_service, sample_model_path):
        """Test listing all models"""
        async def mock_download(gcs_path):
            return sample_model_path
        
        model_initializer_service._download_model_from_gcs = mock_download
        
        # Initialize multiple models
        for i in range(3):
            config = ModelConfig(
                model_id=f"model_{i}",
                gcs_model_path="gs://bucket/model.py"
            )
            await model_initializer_service.initialize_model(config)
        
        # List models
        models = model_initializer_service.list_models()
        
        assert len(models) == 3
        assert "model_0" in models
        assert "model_1" in models
        assert "model_2" in models
    
    @pytest.mark.asyncio
    async def test_delete_model(self, model_initializer_service, sample_model_path):
        """Test deleting a model"""
        async def mock_download(gcs_path):
            return sample_model_path
        
        model_initializer_service._download_model_from_gcs = mock_download
        
        config = ModelConfig(
            model_id="test_model",
            gcs_model_path="gs://bucket/model.py"
        )
        
        await model_initializer_service.initialize_model(config)
        
        # Delete model
        deleted = model_initializer_service.delete_model("test_model")
        
        assert deleted is True
        assert model_initializer_service.get_model("test_model") is None
    
    @pytest.mark.asyncio
    async def test_get_model_info(self, model_initializer_service, sample_model_path):
        """Test getting model info without weights"""
        async def mock_download(gcs_path):
            return sample_model_path
        
        model_initializer_service._download_model_from_gcs = mock_download
        
        config = ModelConfig(
            model_id="test_model",
            gcs_model_path="gs://bucket/model.py"
        )
        
        await model_initializer_service.initialize_model(config)
        
        # Get info
        info = model_initializer_service.get_model_info("test_model")
        
        assert info is not None
        assert info["model_id"] == "test_model"
        assert info["status"] == "ready"
        assert info["metadata"]["name"] == "SimpleNet"
        assert info["num_parameters"] > 0
        assert "model" not in info  # Should not include model weights


# ==================== Test Reinitialization ====================

class TestReinitialization:
    """Test model weight reinitialization"""
    
    @pytest.mark.asyncio
    async def test_reinitialize_model(self, model_initializer_service, sample_model_path):
        """Test reinitializing model weights"""
        async def mock_download(gcs_path):
            return sample_model_path
        
        model_initializer_service._download_model_from_gcs = mock_download
        
        # Initialize with random
        config = ModelConfig(
            model_id="test_model",
            gcs_model_path="gs://bucket/model.py",
            initialization_strategy=InitializationStrategy.RANDOM
        )
        
        await model_initializer_service.initialize_model(config)
        
        original_checksum = model_initializer_service.get_model("test_model").checksum
        
        # Reinitialize with zeros
        await model_initializer_service.reinitialize_model(
            "test_model",
            InitializationStrategy.ZEROS
        )
        
        new_checksum = model_initializer_service.get_model("test_model").checksum
        
        # Checksum should change
        assert original_checksum != new_checksum


# ==================== Test Statistics ====================

class TestStatistics:
    """Test service statistics"""
    
    @pytest.mark.asyncio
    async def test_get_statistics(self, model_initializer_service, sample_model_path):
        """Test getting service statistics"""
        async def mock_download(gcs_path):
            return sample_model_path
        
        model_initializer_service._download_model_from_gcs = mock_download
        
        # Initialize models
        for i in range(3):
            config = ModelConfig(
                model_id=f"model_{i}",
                gcs_model_path="gs://bucket/model.py"
            )
            await model_initializer_service.initialize_model(config)
        
        # Get stats
        stats = model_initializer_service.get_statistics()
        
        assert stats["total_models"] == 3
        assert stats["status_counts"]["ready"] == 3
        assert stats["total_parameters"] > 0
        assert stats["default_device"] == "cpu"


# ==================== Test Checksum ====================

class TestChecksum:
    """Test model checksum calculation"""
    
    def test_calculate_checksum(self, model_initializer_service):
        """Test calculating model checksum"""
        model1 = nn.Linear(10, 5)
        model2 = nn.Linear(10, 5)
        
        # Same initialization should produce same checksum
        nn.init.zeros_(model1.weight)
        nn.init.zeros_(model1.bias)
        nn.init.zeros_(model2.weight)
        nn.init.zeros_(model2.bias)
        
        checksum1 = model_initializer_service._calculate_checksum(model1)
        checksum2 = model_initializer_service._calculate_checksum(model2)
        
        assert checksum1 == checksum2
        
        # Different weights should produce different checksum
        nn.init.ones_(model2.weight)
        checksum3 = model_initializer_service._calculate_checksum(model2)
        
        assert checksum1 != checksum3


# ==================== Integration Tests ====================

class TestIntegration:
    """Integration tests for complete workflows"""
    
    @pytest.mark.asyncio
    async def test_complete_initialization_workflow(
        self,
        model_initializer_service,
        sample_model_path
    ):
        """Test complete model initialization workflow"""
        async def mock_download(gcs_path):
            return sample_model_path
        
        model_initializer_service._download_model_from_gcs = mock_download
        
        # 1. Initialize model
        config = ModelConfig(
            model_id="workflow_model",
            gcs_model_path="gs://bucket/model.py",
            initialization_strategy=InitializationStrategy.XAVIER,
            device="cpu",
            seed=42,
            model_kwargs={"num_classes": 10}
        )
        
        initialized_model = await model_initializer_service.initialize_model(config)
        
        # 2. Verify model is ready
        assert initialized_model.status == ModelStatus.READY
        
        # 3. Get model info
        info = model_initializer_service.get_model_info("workflow_model")
        assert info["status"] == "ready"
        
        # 4. Reinitialize with different strategy
        await model_initializer_service.reinitialize_model(
            "workflow_model",
            InitializationStrategy.KAIMING
        )
        
        # 5. Verify checksum changed
        new_info = model_initializer_service.get_model_info("workflow_model")
        assert new_info["checksum"] != info["checksum"]
        
        # 6. Delete model
        deleted = model_initializer_service.delete_model("workflow_model")
        assert deleted is True
        
        # 7. Verify model is gone
        assert model_initializer_service.get_model("workflow_model") is None
