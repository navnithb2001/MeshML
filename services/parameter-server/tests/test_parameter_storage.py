"""
Comprehensive tests for Parameter Storage Service

Tests parameter storage, versioning, checkpoints, Redis persistence,
and delta compression.
"""

import pytest
import torch
import torch.nn as nn
from unittest.mock import Mock, MagicMock, patch
from typing import Dict, Any
from datetime import datetime, timedelta

from app.services.parameter_storage import (
    ParameterStorageService,
    CheckpointType,
    ParameterFormat,
    ParameterVersion,
    Checkpoint,
    ParameterDelta
)


# ==================== Fixtures ====================

@pytest.fixture
def mock_redis():
    """Mock Redis client"""
    redis_client = MagicMock()
    redis_client.set = MagicMock(return_value=True)
    redis_client.get = MagicMock(return_value=None)
    redis_client.delete = MagicMock(return_value=True)
    return redis_client


@pytest.fixture
def storage_service_no_redis():
    """Parameter storage service without Redis"""
    return ParameterStorageService(enable_redis=False)


@pytest.fixture
def storage_service_with_redis(mock_redis):
    """Parameter storage service with mocked Redis"""
    service = ParameterStorageService(enable_redis=True)
    service.redis_client = mock_redis
    return service


@pytest.fixture
def sample_parameters():
    """Sample parameter dictionary"""
    return {
        "layer1.weight": torch.randn(10, 5),
        "layer1.bias": torch.randn(10),
        "layer2.weight": torch.randn(5, 2),
        "layer2.bias": torch.randn(5)
    }


# ==================== Test Parameter Storage ====================

class TestParameterStorage:
    """Test basic parameter storage operations"""
    
    def test_store_parameters(self, storage_service_no_redis, sample_parameters):
        """Test storing parameters"""
        version = storage_service_no_redis.store_parameters(
            model_id="model_1",
            parameters=sample_parameters
        )
        
        assert version.version_id == 1
        assert version.model_id == "model_1"
        assert version.num_parameters > 0
        assert version.total_size_bytes > 0
        assert version.checksum is not None
    
    def test_store_parameters_increments_version(
        self,
        storage_service_no_redis,
        sample_parameters
    ):
        """Test version increments on each store"""
        # First store
        v1 = storage_service_no_redis.store_parameters("model_1", sample_parameters)
        assert v1.version_id == 1
        
        # Second store
        v2 = storage_service_no_redis.store_parameters("model_1", sample_parameters)
        assert v2.version_id == 2
        
        # Third store
        v3 = storage_service_no_redis.store_parameters("model_1", sample_parameters)
        assert v3.version_id == 3
    
    def test_store_parameters_with_metadata(
        self,
        storage_service_no_redis,
        sample_parameters
    ):
        """Test storing parameters with metadata"""
        metadata = {
            "epoch": 10,
            "loss": 0.25,
            "accuracy": 0.95
        }
        
        version = storage_service_no_redis.store_parameters(
            model_id="model_1",
            parameters=sample_parameters,
            metadata=metadata
        )
        
        assert version.metadata == metadata
    
    def test_get_parameters(self, storage_service_no_redis, sample_parameters):
        """Test retrieving parameters"""
        storage_service_no_redis.store_parameters("model_1", sample_parameters)
        
        retrieved = storage_service_no_redis.get_parameters("model_1")
        
        assert retrieved is not None
        assert len(retrieved) == len(sample_parameters)
        assert "layer1.weight" in retrieved
    
    def test_get_parameters_nonexistent_model(self, storage_service_no_redis):
        """Test getting parameters for nonexistent model"""
        retrieved = storage_service_no_redis.get_parameters("nonexistent")
        
        assert retrieved is None
    
    def test_get_parameter_names(self, storage_service_no_redis, sample_parameters):
        """Test getting parameter names"""
        storage_service_no_redis.store_parameters("model_1", sample_parameters)
        
        names = storage_service_no_redis.get_parameter_names("model_1")
        
        assert names is not None
        assert len(names) == 4
        assert "layer1.weight" in names
        assert "layer2.bias" in names
    
    def test_get_specific_parameter(self, storage_service_no_redis, sample_parameters):
        """Test getting a specific parameter"""
        storage_service_no_redis.store_parameters("model_1", sample_parameters)
        
        param = storage_service_no_redis.get_parameter("model_1", "layer1.weight")
        
        assert param is not None
        assert param.shape == (10, 5)
    
    def test_update_parameter(self, storage_service_no_redis, sample_parameters):
        """Test updating a specific parameter"""
        storage_service_no_redis.store_parameters("model_1", sample_parameters)
        
        new_value = torch.zeros(10, 5)
        updated = storage_service_no_redis.update_parameter(
            "model_1",
            "layer1.weight",
            new_value,
            create_version=True
        )
        
        assert updated is True
        
        # Verify update
        param = storage_service_no_redis.get_parameter("model_1", "layer1.weight")
        assert torch.allclose(param, new_value)
        
        # Verify new version created
        current_version = storage_service_no_redis.get_current_version("model_1")
        assert current_version == 2


# ==================== Test Versioning ====================

class TestVersioning:
    """Test parameter versioning"""
    
    def test_get_current_version(self, storage_service_no_redis, sample_parameters):
        """Test getting current version"""
        storage_service_no_redis.store_parameters("model_1", sample_parameters)
        
        version = storage_service_no_redis.get_current_version("model_1")
        
        assert version == 1
    
    def test_get_version_history(self, storage_service_no_redis, sample_parameters):
        """Test getting version history"""
        # Store multiple versions
        for i in range(5):
            storage_service_no_redis.store_parameters(
                "model_1",
                sample_parameters,
                metadata={"iteration": i}
            )
        
        history = storage_service_no_redis.get_version_history("model_1")
        
        assert len(history) == 5
        assert history[0].version_id == 5  # Sorted descending
        assert history[4].version_id == 1
    
    def test_get_version_history_with_limit(
        self,
        storage_service_no_redis,
        sample_parameters
    ):
        """Test getting version history with limit"""
        # Store multiple versions
        for i in range(10):
            storage_service_no_redis.store_parameters("model_1", sample_parameters)
        
        history = storage_service_no_redis.get_version_history("model_1", limit=3)
        
        assert len(history) == 3
        assert history[0].version_id == 10  # Latest 3 versions


# ==================== Test Checkpoints ====================

class TestCheckpoints:
    """Test checkpoint management"""
    
    def test_create_checkpoint(self, storage_service_with_redis, sample_parameters):
        """Test creating a checkpoint"""
        # Store parameters first
        storage_service_with_redis.store_parameters("model_1", sample_parameters)
        
        # Create checkpoint
        checkpoint = storage_service_with_redis.create_checkpoint(
            model_id="model_1",
            checkpoint_type=CheckpointType.MANUAL,
            metrics={"loss": 0.25}
        )
        
        assert checkpoint.checkpoint_id is not None
        assert checkpoint.model_id == "model_1"
        assert checkpoint.version_id == 1
        assert checkpoint.checkpoint_type == CheckpointType.MANUAL
        assert checkpoint.metrics["loss"] == 0.25
    
    def test_create_checkpoint_with_custom_id(
        self,
        storage_service_with_redis,
        sample_parameters
    ):
        """Test creating checkpoint with custom ID"""
        storage_service_with_redis.store_parameters("model_1", sample_parameters)
        
        checkpoint = storage_service_with_redis.create_checkpoint(
            model_id="model_1",
            checkpoint_id="custom_checkpoint_1",
            checkpoint_type=CheckpointType.BEST
        )
        
        assert checkpoint.checkpoint_id == "custom_checkpoint_1"
    
    def test_list_checkpoints(self, storage_service_with_redis, sample_parameters):
        """Test listing checkpoints"""
        storage_service_with_redis.store_parameters("model_1", sample_parameters)
        
        # Create multiple checkpoints
        for i in range(3):
            storage_service_with_redis.create_checkpoint(
                model_id="model_1",
                checkpoint_type=CheckpointType.AUTO
            )
        
        checkpoints = storage_service_with_redis.list_checkpoints("model_1")
        
        assert len(checkpoints) == 3
    
    def test_list_checkpoints_by_type(
        self,
        storage_service_with_redis,
        sample_parameters
    ):
        """Test listing checkpoints filtered by type"""
        storage_service_with_redis.store_parameters("model_1", sample_parameters)
        
        # Create different types
        storage_service_with_redis.create_checkpoint(
            "model_1",
            CheckpointType.AUTO
        )
        storage_service_with_redis.create_checkpoint(
            "model_1",
            CheckpointType.BEST
        )
        storage_service_with_redis.create_checkpoint(
            "model_1",
            CheckpointType.AUTO
        )
        
        best_checkpoints = storage_service_with_redis.list_checkpoints(
            "model_1",
            CheckpointType.BEST
        )
        
        assert len(best_checkpoints) == 1
        assert best_checkpoints[0].checkpoint_type == CheckpointType.BEST
    
    def test_load_checkpoint(self, storage_service_with_redis, sample_parameters):
        """Test loading checkpoint"""
        # Store and checkpoint
        storage_service_with_redis.store_parameters("model_1", sample_parameters)
        checkpoint = storage_service_with_redis.create_checkpoint("model_1")
        
        # Mock Redis get
        import io
        buffer = io.BytesIO()
        torch.save({
            "parameters": sample_parameters,
            "checkpoint_info": {}
        }, buffer)
        buffer.seek(0)
        storage_service_with_redis.redis_client.get.return_value = buffer.read()
        
        # Load
        loaded = storage_service_with_redis.load_checkpoint(
            "model_1",
            checkpoint.checkpoint_id,
            restore_to_current=False
        )
        
        assert loaded is not None
        assert "layer1.weight" in loaded
    
    def test_delete_checkpoint(self, storage_service_with_redis, sample_parameters):
        """Test deleting a checkpoint"""
        storage_service_with_redis.store_parameters("model_1", sample_parameters)
        checkpoint = storage_service_with_redis.create_checkpoint("model_1")
        
        deleted = storage_service_with_redis.delete_checkpoint(
            "model_1",
            checkpoint.checkpoint_id
        )
        
        assert deleted is True
        
        # Verify deletion
        checkpoints = storage_service_with_redis.list_checkpoints("model_1")
        assert len(checkpoints) == 0
    
    def test_checkpoint_retention_policy(
        self,
        storage_service_with_redis,
        sample_parameters
    ):
        """Test checkpoint retention policy"""
        # Set retention to 3
        storage_service_with_redis.checkpoint_retention = 3
        
        storage_service_with_redis.store_parameters("model_1", sample_parameters)
        
        # Create 5 AUTO checkpoints
        for i in range(5):
            storage_service_with_redis.create_checkpoint(
                "model_1",
                CheckpointType.AUTO
            )
        
        # Should only keep 3 most recent
        checkpoints = storage_service_with_redis.list_checkpoints("model_1")
        assert len(checkpoints) == 3
    
    def test_checkpoint_retention_protects_best_final(
        self,
        storage_service_with_redis,
        sample_parameters
    ):
        """Test retention policy protects BEST and FINAL checkpoints"""
        storage_service_with_redis.checkpoint_retention = 2
        
        storage_service_with_redis.store_parameters("model_1", sample_parameters)
        
        # Create checkpoints
        storage_service_with_redis.create_checkpoint(
            "model_1",
            CheckpointType.BEST
        )
        storage_service_with_redis.create_checkpoint(
            "model_1",
            CheckpointType.FINAL
        )
        for i in range(5):
            storage_service_with_redis.create_checkpoint(
                "model_1",
                CheckpointType.AUTO
            )
        
        # BEST and FINAL should be protected, plus 2 AUTO
        checkpoints = storage_service_with_redis.list_checkpoints("model_1")
        assert len(checkpoints) == 4  # BEST + FINAL + 2 AUTO


# ==================== Test Delta Compression ====================

class TestDeltaCompression:
    """Test parameter delta calculation"""
    
    def test_calculate_delta(self, storage_service_no_redis):
        """Test calculating delta between versions"""
        # Version 1
        params_v1 = {
            "layer1.weight": torch.ones(10, 5),
            "layer1.bias": torch.ones(10),
            "layer2.weight": torch.ones(5, 2),
            "layer2.bias": torch.ones(5)
        }
        storage_service_no_redis.store_parameters("model_1", params_v1)
        
        # Version 2 (change only layer1.weight)
        params_v2 = params_v1.copy()
        params_v2["layer1.weight"] = torch.zeros(10, 5)
        storage_service_no_redis.store_parameters("model_1", params_v2)
        
        # Mock Redis for loading v1
        storage_service_no_redis.enable_redis = False
        
        # Calculate delta
        delta = storage_service_no_redis.calculate_delta("model_1", 1, 2)
        
        assert delta is not None
        # Only layer1.weight should have changed
        assert "layer1.weight" in delta.changed_keys
        assert delta.compression_ratio < 1.0  # Delta smaller than full params


# ==================== Test Redis Persistence ====================

class TestRedisPersistence:
    """Test Redis-backed persistence"""
    
    def test_persist_to_redis(self, storage_service_with_redis, sample_parameters):
        """Test persisting parameters to Redis"""
        storage_service_with_redis.store_parameters("model_1", sample_parameters)
        
        # Verify Redis set was called
        assert storage_service_with_redis.redis_client.set.called
    
    def test_checkpoint_saved_to_redis(
        self,
        storage_service_with_redis,
        sample_parameters
    ):
        """Test checkpoint is saved to Redis"""
        storage_service_with_redis.store_parameters("model_1", sample_parameters)
        checkpoint = storage_service_with_redis.create_checkpoint("model_1")
        
        # Verify Redis set was called for checkpoint
        assert storage_service_with_redis.redis_client.set.call_count >= 2


# ==================== Test Statistics ====================

class TestStatistics:
    """Test service statistics"""
    
    def test_get_statistics(self, storage_service_no_redis, sample_parameters):
        """Test getting statistics"""
        # Store parameters for multiple models
        for i in range(3):
            storage_service_no_redis.store_parameters(
                f"model_{i}",
                sample_parameters
            )
        
        stats = storage_service_no_redis.get_statistics()
        
        assert stats["total_models"] == 3
        assert stats["total_versions"] == 3
        assert stats["total_parameters"] > 0
        assert stats["total_size_bytes"] > 0
        assert stats["redis_enabled"] is False


# ==================== Test Format Conversion ====================

class TestFormatConversion:
    """Test format conversion (PyTorch <-> NumPy)"""
    
    def test_get_parameters_numpy_format(
        self,
        storage_service_no_redis,
        sample_parameters
    ):
        """Test getting parameters in NumPy format"""
        storage_service_no_redis.store_parameters("model_1", sample_parameters)
        
        params_numpy = storage_service_no_redis.get_parameters(
            "model_1",
            format=ParameterFormat.NUMPY
        )
        
        assert params_numpy is not None
        # Check it's numpy, not torch
        import numpy as np
        assert isinstance(params_numpy["layer1.weight"], np.ndarray)


# ==================== Integration Tests ====================

class TestIntegration:
    """Integration tests for complete workflows"""
    
    def test_complete_versioning_workflow(
        self,
        storage_service_with_redis,
        sample_parameters
    ):
        """Test complete versioning workflow"""
        # 1. Store initial parameters
        v1 = storage_service_with_redis.store_parameters(
            "model_1",
            sample_parameters,
            metadata={"epoch": 0}
        )
        assert v1.version_id == 1
        
        # 2. Update and create new version
        v2 = storage_service_with_redis.store_parameters(
            "model_1",
            sample_parameters,
            metadata={"epoch": 1},
            create_checkpoint=True,
            checkpoint_type=CheckpointType.AUTO
        )
        assert v2.version_id == 2
        
        # 3. Verify history
        history = storage_service_with_redis.get_version_history("model_1")
        assert len(history) == 2
        
        # 4. Verify checkpoint created
        checkpoints = storage_service_with_redis.list_checkpoints("model_1")
        assert len(checkpoints) == 1
        
        # 5. Get current version
        current = storage_service_with_redis.get_current_version("model_1")
        assert current == 2
    
    def test_checkpoint_restore_workflow(
        self,
        storage_service_with_redis,
        sample_parameters
    ):
        """Test checkpoint and restore workflow"""
        # 1. Store and checkpoint
        storage_service_with_redis.store_parameters("model_1", sample_parameters)
        checkpoint = storage_service_with_redis.create_checkpoint(
            "model_1",
            checkpoint_type=CheckpointType.BEST,
            metrics={"accuracy": 0.95}
        )
        
        # 2. Make more updates
        storage_service_with_redis.store_parameters("model_1", sample_parameters)
        storage_service_with_redis.store_parameters("model_1", sample_parameters)
        
        assert storage_service_with_redis.get_current_version("model_1") == 3
        
        # 3. Mock Redis for restore
        import io
        buffer = io.BytesIO()
        torch.save({
            "parameters": sample_parameters,
            "checkpoint_info": {}
        }, buffer)
        buffer.seek(0)
        storage_service_with_redis.redis_client.get.return_value = buffer.read()
        
        # 4. Restore from checkpoint
        loaded = storage_service_with_redis.load_checkpoint(
            "model_1",
            checkpoint.checkpoint_id,
            restore_to_current=True
        )
        
        assert loaded is not None
        assert storage_service_with_redis.get_current_version("model_1") == 4
