"""
Tests for Parameter Distribution Service

Comprehensive tests covering:
- Pull mode (workers request parameters)
- Push mode (server broadcasts parameters)
- Delta compression
- Multiple formats (PyTorch, NumPy)
- Compression (gzip)
- Worker subscriptions
- Distribution history
"""

import pytest
import torch
import numpy as np
from typing import Dict

from app.services.parameter_distribution import (
    ParameterDistributionService,
    DistributionRequest,
    DistributionConfig,
    DistributionMode,
    CompressionType,
    ParameterFormat
)
from app.services.parameter_storage import ParameterStorageService


# ==================== Fixtures ====================

@pytest.fixture
def parameter_storage():
    """Create parameter storage service"""
    return ParameterStorageService()


@pytest.fixture
def distribution_service(parameter_storage):
    """Create parameter distribution service"""
    return ParameterDistributionService(parameter_storage)


@pytest.fixture
def sample_parameters():
    """Create sample parameters"""
    return {
        "layer1.weight": torch.randn(10, 5),
        "layer1.bias": torch.randn(10),
        "layer2.weight": torch.randn(3, 10),
        "layer2.bias": torch.randn(3)
    }


def setup_model_with_versions(
    parameter_storage: ParameterStorageService,
    model_id: str,
    base_params: Dict[str, torch.Tensor],
    num_versions: int = 3
) -> None:
    """Helper to set up model with multiple versions"""
    for i in range(num_versions):
        # Modify parameters slightly
        params = {
            k: v.clone() + torch.randn_like(v) * 0.1
            for k, v in base_params.items()
        }
        
        parameter_storage.store_parameters(
            model_id=model_id,
            parameters=params,
            metadata={"iteration": i}
        )


# ==================== Test Pull Mode ====================

class TestPullMode:
    """Test pull mode (workers request parameters)"""
    
    def test_pull_latest_parameters(
        self,
        distribution_service,
        parameter_storage,
        sample_parameters
    ):
        """Test pulling latest parameters"""
        model_id = "model-pull"
        
        # Store parameters
        parameter_storage.store_parameters(model_id, sample_parameters)
        
        # Pull parameters
        request = DistributionRequest(
            model_id=model_id,
            worker_id="worker-1"
        )
        
        package = distribution_service.distribute_to_worker("worker-1", request)
        
        assert package.model_id == model_id
        assert package.version_id == 1
        assert len(package.parameters) == len(sample_parameters)
        assert package.is_delta is False
    
    def test_pull_specific_version(
        self,
        distribution_service,
        parameter_storage,
        sample_parameters
    ):
        """Test pulling specific version"""
        model_id = "model-versioned"
        
        # Store multiple versions
        setup_model_with_versions(parameter_storage, model_id, sample_parameters, 3)
        
        # Pull version 2
        request = DistributionRequest(
            model_id=model_id,
            worker_id="worker-1",
            requested_version=2
        )
        
        package = distribution_service.distribute_to_worker("worker-1", request)
        
        assert package.version_id == 2
    
    def test_pull_specific_parameters(
        self,
        distribution_service,
        parameter_storage,
        sample_parameters
    ):
        """Test pulling specific parameters only"""
        model_id = "model-partial"
        
        parameter_storage.store_parameters(model_id, sample_parameters)
        
        # Request only specific parameters
        request = DistributionRequest(
            model_id=model_id,
            worker_id="worker-1",
            parameter_names=["layer1.weight", "layer1.bias"]
        )
        
        package = distribution_service.distribute_to_worker("worker-1", request)
        
        assert len(package.parameters) == 2
        assert "layer1.weight" in package.parameters
        assert "layer1.bias" in package.parameters
        assert "layer2.weight" not in package.parameters


# ==================== Test Delta Compression ====================

class TestDeltaCompression:
    """Test delta compression for efficient transfers"""
    
    def test_delta_compression_enabled(
        self,
        distribution_service,
        parameter_storage,
        sample_parameters
    ):
        """Test delta compression when beneficial"""
        model_id = "model-delta"
        
        # Store version 1
        parameter_storage.store_parameters(model_id, sample_parameters)
        
        # Store version 2 with only one parameter changed
        updated_params = sample_parameters.copy()
        updated_params["layer1.weight"] = torch.randn(10, 5)
        parameter_storage.store_parameters(model_id, updated_params)
        
        # Request with delta compression
        config = DistributionConfig(
            enable_delta_compression=True,
            delta_threshold=0.5  # Send delta if < 50% changed
        )
        
        request = DistributionRequest(
            model_id=model_id,
            worker_id="worker-1",
            current_version=1,
            requested_version=2,
            delta_only=True
        )
        
        package = distribution_service.prepare_parameters(request, config)
        
        # Should use delta (only 1 out of 4 parameters changed = 25%)
        assert package.is_delta is True
        assert package.base_version == 1
        assert len(package.parameters) < len(sample_parameters)
    
    def test_delta_compression_disabled_when_many_changes(
        self,
        distribution_service,
        parameter_storage,
        sample_parameters
    ):
        """Test full transfer when many parameters changed"""
        model_id = "model-full"
        
        # Store version 1
        parameter_storage.store_parameters(model_id, sample_parameters)
        
        # Store version 2 with all parameters changed
        updated_params = {k: torch.randn_like(v) for k, v in sample_parameters.items()}
        parameter_storage.store_parameters(model_id, updated_params)
        
        # Request with delta compression
        config = DistributionConfig(
            enable_delta_compression=True,
            delta_threshold=0.5  # Send delta if < 50% changed
        )
        
        request = DistributionRequest(
            model_id=model_id,
            worker_id="worker-1",
            current_version=1,
            requested_version=2,
            delta_only=True
        )
        
        package = distribution_service.prepare_parameters(request, config)
        
        # Should use full transfer (100% changed > 50% threshold)
        assert package.is_delta is False
        assert len(package.parameters) == len(sample_parameters)


# ==================== Test Format Conversion ====================

class TestFormatConversion:
    """Test parameter format conversion"""
    
    def test_numpy_format(
        self,
        distribution_service,
        parameter_storage,
        sample_parameters
    ):
        """Test NumPy format conversion"""
        model_id = "model-numpy"
        
        parameter_storage.store_parameters(model_id, sample_parameters)
        
        request = DistributionRequest(
            model_id=model_id,
            worker_id="worker-1",
            format_type=ParameterFormat.NUMPY
        )
        
        package = distribution_service.distribute_to_worker("worker-1", request)
        
        assert package.format_type == ParameterFormat.NUMPY
        
        # Check parameters are NumPy arrays
        for param in package.parameters.values():
            assert isinstance(param, np.ndarray)
    
    def test_pytorch_format(
        self,
        distribution_service,
        parameter_storage,
        sample_parameters
    ):
        """Test PyTorch format (default)"""
        model_id = "model-pytorch"
        
        parameter_storage.store_parameters(model_id, sample_parameters)
        
        request = DistributionRequest(
            model_id=model_id,
            worker_id="worker-1",
            format_type=ParameterFormat.PYTORCH
        )
        
        package = distribution_service.distribute_to_worker("worker-1", request)
        
        assert package.format_type == ParameterFormat.PYTORCH
        
        # Check parameters are PyTorch tensors
        for param in package.parameters.values():
            assert isinstance(param, torch.Tensor)


# ==================== Test Compression ====================

class TestCompression:
    """Test parameter compression"""
    
    def test_gzip_compression(
        self,
        distribution_service,
        parameter_storage,
        sample_parameters
    ):
        """Test gzip compression"""
        model_id = "model-gzip"
        
        parameter_storage.store_parameters(model_id, sample_parameters)
        
        request = DistributionRequest(
            model_id=model_id,
            worker_id="worker-1",
            compression=CompressionType.GZIP
        )
        
        package = distribution_service.distribute_to_worker("worker-1", request)
        
        assert package.compressed is True
        assert package.compression_type == CompressionType.GZIP
        assert "compressed_data" in package.metadata
        assert "original_size" in package.metadata
    
    def test_decompression(
        self,
        distribution_service,
        parameter_storage,
        sample_parameters
    ):
        """Test decompressing a package"""
        model_id = "model-decompress"
        
        parameter_storage.store_parameters(model_id, sample_parameters)
        
        request = DistributionRequest(
            model_id=model_id,
            worker_id="worker-1",
            compression=CompressionType.GZIP
        )
        
        package = distribution_service.distribute_to_worker("worker-1", request)
        assert package.compressed is True
        
        # Decompress
        decompressed = distribution_service.decompress_package(package)
        
        assert decompressed.compressed is False
        assert len(decompressed.parameters) == len(sample_parameters)
    
    def test_no_compression(
        self,
        distribution_service,
        parameter_storage,
        sample_parameters
    ):
        """Test no compression"""
        model_id = "model-nocomp"
        
        parameter_storage.store_parameters(model_id, sample_parameters)
        
        request = DistributionRequest(
            model_id=model_id,
            worker_id="worker-1",
            compression=CompressionType.NONE
        )
        
        package = distribution_service.distribute_to_worker("worker-1", request)
        
        assert package.compressed is False
        assert package.compression_type is None


# ==================== Test Broadcast Mode ====================

class TestBroadcastMode:
    """Test broadcasting parameters to multiple workers"""
    
    def test_broadcast_to_multiple_workers(
        self,
        distribution_service,
        parameter_storage,
        sample_parameters
    ):
        """Test broadcasting to multiple workers"""
        model_id = "model-broadcast"
        
        parameter_storage.store_parameters(model_id, sample_parameters)
        
        worker_ids = ["worker-1", "worker-2", "worker-3"]
        
        packages = distribution_service.broadcast_to_workers(
            model_id=model_id,
            worker_ids=worker_ids
        )
        
        assert len(packages) == 3
        assert all(wid in packages for wid in worker_ids)
        
        # All packages should have same version
        versions = {p.version_id for p in packages.values()}
        assert len(versions) == 1
    
    def test_broadcast_specific_version(
        self,
        distribution_service,
        parameter_storage,
        sample_parameters
    ):
        """Test broadcasting specific version"""
        model_id = "model-broadcast-ver"
        
        # Store multiple versions
        setup_model_with_versions(parameter_storage, model_id, sample_parameters, 3)
        
        worker_ids = ["worker-1", "worker-2"]
        
        packages = distribution_service.broadcast_to_workers(
            model_id=model_id,
            worker_ids=worker_ids,
            version_id=2
        )
        
        # All packages should have version 2
        for package in packages.values():
            assert package.version_id == 2


# ==================== Test Subscriptions ====================

class TestSubscriptions:
    """Test worker subscriptions for push mode"""
    
    def test_subscribe_worker(self, distribution_service):
        """Test subscribing a worker"""
        newly_subscribed = distribution_service.subscribe_worker(
            model_id="model-sub",
            worker_id="worker-1"
        )
        
        assert newly_subscribed is True
        
        workers = distribution_service.get_subscribed_workers("model-sub")
        assert "worker-1" in workers
    
    def test_subscribe_already_subscribed(self, distribution_service):
        """Test subscribing already subscribed worker"""
        distribution_service.subscribe_worker("model-sub", "worker-1")
        
        newly_subscribed = distribution_service.subscribe_worker(
            "model-sub",
            "worker-1"
        )
        
        assert newly_subscribed is False
    
    def test_unsubscribe_worker(self, distribution_service):
        """Test unsubscribing a worker"""
        distribution_service.subscribe_worker("model-sub", "worker-1")
        
        was_subscribed = distribution_service.unsubscribe_worker(
            "model-sub",
            "worker-1"
        )
        
        assert was_subscribed is True
        
        workers = distribution_service.get_subscribed_workers("model-sub")
        assert "worker-1" not in workers
    
    def test_unsubscribe_not_subscribed(self, distribution_service):
        """Test unsubscribing non-subscribed worker"""
        was_subscribed = distribution_service.unsubscribe_worker(
            "model-sub",
            "worker-unknown"
        )
        
        assert was_subscribed is False
    
    def test_multiple_subscriptions(self, distribution_service):
        """Test multiple workers subscribing"""
        for i in range(5):
            distribution_service.subscribe_worker(
                "model-sub",
                f"worker-{i}"
            )
        
        workers = distribution_service.get_subscribed_workers("model-sub")
        assert len(workers) == 5


# ==================== Test Checksums ====================

class TestChecksums:
    """Test checksum calculation"""
    
    def test_checksum_enabled(
        self,
        distribution_service,
        parameter_storage,
        sample_parameters
    ):
        """Test checksum calculation"""
        model_id = "model-checksum"
        
        parameter_storage.store_parameters(model_id, sample_parameters)
        
        config = DistributionConfig(enable_checksum=True)
        
        request = DistributionRequest(
            model_id=model_id,
            worker_id="worker-1"
        )
        
        package = distribution_service.prepare_parameters(request, config)
        
        assert package.checksum != ""
        assert len(package.checksum) == 64  # SHA256 hex digest
    
    def test_checksum_consistency(
        self,
        distribution_service,
        parameter_storage,
        sample_parameters
    ):
        """Test checksum is consistent for same parameters"""
        model_id = "model-checksum2"
        
        parameter_storage.store_parameters(model_id, sample_parameters)
        
        config = DistributionConfig(enable_checksum=True)
        
        request = DistributionRequest(
            model_id=model_id,
            worker_id="worker-1"
        )
        
        package1 = distribution_service.prepare_parameters(request, config)
        package2 = distribution_service.prepare_parameters(request, config)
        
        assert package1.checksum == package2.checksum


# ==================== Test Distribution History ====================

class TestDistributionHistory:
    """Test distribution history tracking"""
    
    def test_record_distribution(
        self,
        distribution_service,
        parameter_storage,
        sample_parameters
    ):
        """Test recording distribution in history"""
        model_id = "model-history"
        
        parameter_storage.store_parameters(model_id, sample_parameters)
        
        request = DistributionRequest(
            model_id=model_id,
            worker_id="worker-1"
        )
        
        distribution_service.distribute_to_worker("worker-1", request)
        
        history = distribution_service.get_distribution_history()
        assert len(history) == 1
        assert history[0].model_id == model_id
        assert history[0].worker_ids == ["worker-1"]
    
    def test_filter_history_by_model(
        self,
        distribution_service,
        parameter_storage,
        sample_parameters
    ):
        """Test filtering history by model"""
        # Distribute to different models
        for model_id in ["model-a", "model-b"]:
            parameter_storage.store_parameters(model_id, sample_parameters)
            
            request = DistributionRequest(
                model_id=model_id,
                worker_id="worker-1"
            )
            distribution_service.distribute_to_worker("worker-1", request)
        
        history_a = distribution_service.get_distribution_history(model_id="model-a")
        history_b = distribution_service.get_distribution_history(model_id="model-b")
        
        assert len(history_a) == 1
        assert len(history_b) == 1
        assert history_a[0].model_id == "model-a"
        assert history_b[0].model_id == "model-b"
    
    def test_filter_history_by_worker(
        self,
        distribution_service,
        parameter_storage,
        sample_parameters
    ):
        """Test filtering history by worker"""
        model_id = "model-worker-filter"
        
        parameter_storage.store_parameters(model_id, sample_parameters)
        
        # Distribute to multiple workers
        for worker_id in ["worker-1", "worker-2"]:
            request = DistributionRequest(
                model_id=model_id,
                worker_id=worker_id
            )
            distribution_service.distribute_to_worker(worker_id, request)
        
        history_w1 = distribution_service.get_distribution_history(worker_id="worker-1")
        history_w2 = distribution_service.get_distribution_history(worker_id="worker-2")
        
        assert len(history_w1) == 1
        assert len(history_w2) == 1
        assert "worker-1" in history_w1[0].worker_ids
        assert "worker-2" in history_w2[0].worker_ids
    
    def test_limit_history(
        self,
        distribution_service,
        parameter_storage,
        sample_parameters
    ):
        """Test limiting history results"""
        model_id = "model-limit"
        
        parameter_storage.store_parameters(model_id, sample_parameters)
        
        # Make multiple distributions
        for i in range(10):
            request = DistributionRequest(
                model_id=model_id,
                worker_id=f"worker-{i}"
            )
            distribution_service.distribute_to_worker(f"worker-{i}", request)
        
        history = distribution_service.get_distribution_history(limit=5)
        assert len(history) == 5


# ==================== Test Statistics ====================

class TestStatistics:
    """Test distribution statistics"""
    
    def test_service_statistics(
        self,
        distribution_service,
        parameter_storage,
        sample_parameters
    ):
        """Test comprehensive statistics"""
        model_id = "model-stats"
        
        parameter_storage.store_parameters(model_id, sample_parameters)
        
        # Make distributions
        for i in range(3):
            request = DistributionRequest(
                model_id=model_id,
                worker_id=f"worker-{i}"
            )
            distribution_service.distribute_to_worker(f"worker-{i}", request)
        
        # Subscribe workers
        for i in range(2):
            distribution_service.subscribe_worker(model_id, f"worker-{i}")
        
        stats = distribution_service.get_statistics()
        
        assert stats["total_distributions"] == 3
        assert stats["unique_workers"] == 3
        assert stats["total_subscriptions"] == 2
        assert stats["total_bytes_transferred"] > 0


# ==================== Integration Tests ====================

class TestIntegration:
    """Integration tests for complete workflows"""
    
    def test_complete_pull_workflow(
        self,
        distribution_service,
        parameter_storage,
        sample_parameters
    ):
        """Test complete pull workflow"""
        model_id = "model-pull-workflow"
        
        # 1. Store initial parameters
        parameter_storage.store_parameters(model_id, sample_parameters)
        
        # 2. Worker pulls parameters (version 1)
        request1 = DistributionRequest(
            model_id=model_id,
            worker_id="worker-1",
            compression=CompressionType.GZIP,
            format_type=ParameterFormat.PYTORCH
        )
        
        package1 = distribution_service.distribute_to_worker("worker-1", request1)
        assert package1.version_id == 1
        assert package1.compressed is True
        
        # 3. Update parameters (version 2)
        updated_params = {k: torch.randn_like(v) for k, v in sample_parameters.items()}
        parameter_storage.store_parameters(model_id, updated_params)
        
        # 4. Worker pulls delta update
        request2 = DistributionRequest(
            model_id=model_id,
            worker_id="worker-1",
            current_version=1,
            delta_only=True,
            compression=CompressionType.GZIP
        )
        
        config = DistributionConfig(enable_delta_compression=True)
        package2 = distribution_service.prepare_parameters(request2, config)
        
        assert package2.version_id == 2
        
        # 5. Check history
        history = distribution_service.get_distribution_history(model_id=model_id)
        assert len(history) >= 1
    
    def test_complete_push_workflow(
        self,
        distribution_service,
        parameter_storage,
        sample_parameters
    ):
        """Test complete push workflow"""
        model_id = "model-push-workflow"
        
        # 1. Workers subscribe
        workers = ["worker-1", "worker-2", "worker-3"]
        for worker_id in workers:
            distribution_service.subscribe_worker(model_id, worker_id)
        
        # 2. Store parameters
        parameter_storage.store_parameters(model_id, sample_parameters)
        
        # 3. Broadcast to subscribed workers
        subscribed_workers = distribution_service.get_subscribed_workers(model_id)
        
        packages = distribution_service.broadcast_to_workers(
            model_id=model_id,
            worker_ids=subscribed_workers,
            version_id=1
        )
        
        assert len(packages) == 3
        
        # 4. Check statistics
        stats = distribution_service.get_statistics()
        assert stats["total_subscriptions"] == 3
        assert stats["total_distributions"] > 0
