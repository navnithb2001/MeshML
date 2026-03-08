"""
Tests for Training Loop (TASK-8.4)

Tests:
- Trainer initialization
- Model loading
- Data loading
- Training epoch
- Batch training
- Gradient computation
- Gradient pushing
- Checkpoint saving/loading
- Heartbeat integration
"""

import pytest
from pathlib import Path
import tempfile
import shutil
from unittest.mock import Mock, patch, MagicMock

from meshml_worker.training.trainer import Trainer
from meshml_worker.config import WorkerConfig
from meshml_worker.communication.grpc_client import GRPCClient


# ==================== Fixtures ====================

@pytest.fixture
def temp_dir():
    """Create temporary directory"""
    temp_path = Path(tempfile.mkdtemp())
    yield temp_path
    shutil.rmtree(temp_path, ignore_errors=True)


@pytest.fixture
def worker_config(temp_dir):
    """Create worker configuration"""
    config = WorkerConfig()
    config.worker.id = "test-worker"
    config.storage.base_dir = temp_dir
    config.training.batch_size = 4
    config.training.num_workers = 0
    config.training.mixed_precision = False
    config.setup()
    return config


@pytest.fixture
def mock_grpc_client():
    """Create mock gRPC client"""
    client = Mock(spec=GRPCClient)
    client.connected = True
    client.current_version = 1
    
    # Mock get_weights
    client.get_weights.return_value = ({"layer": [1.0]}, 1)
    
    # Mock push_gradients
    client.push_gradients.return_value = {
        "success": True,
        "new_version": 2
    }
    
    return client


@pytest.fixture
def trainer(worker_config, mock_grpc_client):
    """Create trainer instance"""
    return Trainer(
        config=worker_config,
        grpc_client=mock_grpc_client,
        device="cpu"
    )


# ==================== Test Initialization ====================

class TestTrainerInitialization:
    """Test trainer initialization"""
    
    def test_trainer_creation(self, trainer, worker_config):
        """Test creating trainer"""
        assert trainer.config == worker_config
        assert trainer.device == "cpu"
        assert trainer.model is None
        assert trainer.optimizer is None
        assert trainer.current_epoch == 0
    
    def test_mixed_precision_disabled_on_cpu(self, worker_config, mock_grpc_client):
        """Test mixed precision disabled on CPU"""
        trainer = Trainer(worker_config, mock_grpc_client, "cpu")
        assert trainer.scaler is None
    
    @pytest.mark.skipif(True, reason="CUDA not available in CI")
    def test_mixed_precision_enabled_on_cuda(self, worker_config, mock_grpc_client):
        """Test mixed precision enabled on CUDA"""
        worker_config.training.mixed_precision = True
        trainer = Trainer(worker_config, mock_grpc_client, "cuda")
        assert trainer.scaler is not None


# ==================== Test Model Loading ====================

class TestModelLoading:
    """Test model loading"""
    
    def test_load_model_success(self, trainer):
        """Test successful model loading"""
        pytest.importorskip("torch")
        
        # Need example model file
        example_model = Path(__file__).parent.parent / "examples" / "example_model.py"
        if not example_model.exists():
            pytest.skip("Example model not found")
        
        trainer._load_model("test-model")
        
        assert trainer.model is not None
        assert trainer.criterion is not None
        assert trainer.create_dataloader_fn is not None
    
    def test_load_model_file_not_found(self, trainer):
        """Test error when model file not found"""
        # Temporarily modify path to non-existent file
        with patch('meshml_worker.training.trainer.Path') as mock_path:
            mock_path.return_value.parent.parent.parent = Path("/nonexistent")
            
            with pytest.raises(FileNotFoundError):
                trainer._load_model("test-model")


# ==================== Test Data Loading ====================

class TestDataLoading:
    """Test data loading"""
    
    def test_load_data_success(self, trainer):
        """Test successful data loading"""
        pytest.importorskip("torch")
        
        # Mock create_dataloader function
        mock_loader = Mock()
        mock_loader.__len__ = Mock(return_value=10)
        trainer.create_dataloader_fn = Mock(return_value=mock_loader)
        
        trainer._load_data("test-model")
        
        assert trainer.train_loader is not None
        trainer.create_dataloader_fn.assert_called_once()
    
    def test_load_data_no_function(self, trainer):
        """Test error when no create_dataloader function"""
        trainer.create_dataloader_fn = None
        
        with pytest.raises(ValueError, match="No create_dataloader"):
            trainer._load_data("test-model")


# ==================== Test Optimizer Initialization ====================

class TestOptimizerInitialization:
    """Test optimizer initialization"""
    
    def test_initialize_optimizer(self, trainer):
        """Test optimizer initialization"""
        pytest.importorskip("torch")
        import torch.nn as nn
        
        # Create dummy model
        trainer.model = nn.Linear(10, 10)
        
        trainer._initialize_optimizer()
        
        assert trainer.optimizer is not None


# ==================== Test Fetch Weights ====================

class TestFetchWeights:
    """Test fetching weights from Parameter Server"""
    
    def test_fetch_weights_success(self, trainer, mock_grpc_client):
        """Test successful weight fetching"""
        trainer._fetch_weights("test-model")
        
        mock_grpc_client.get_weights.assert_called_once()
        assert trainer.global_version == 1
    
    def test_fetch_weights_failure_fallback(self, trainer, mock_grpc_client):
        """Test fallback when fetch fails"""
        mock_grpc_client.get_weights.side_effect = Exception("Network error")
        
        # Should not raise, just log warning
        trainer._fetch_weights("test-model")
        
        assert trainer.global_version == 0


# ==================== Test Training Batch ====================

class TestTrainingBatch:
    """Test training single batch"""
    
    def test_train_batch_basic(self, trainer):
        """Test basic batch training"""
        pytest.importorskip("torch")
        import torch
        import torch.nn as nn
        
        # Setup
        trainer.model = nn.Linear(10, 10)
        trainer.optimizer = torch.optim.SGD(trainer.model.parameters(), lr=0.01)
        trainer.criterion = nn.MSELoss()
        
        # Mock data
        data = torch.randn(4, 10)
        target = torch.randn(4, 10)
        
        # Train
        loss, output = trainer._train_batch(data, target, 0, 0)
        
        assert isinstance(loss, float)
        assert output.shape == (4, 10)
    
    def test_train_batch_with_gradient_clipping(self, trainer, worker_config):
        """Test batch training with gradient clipping"""
        pytest.importorskip("torch")
        import torch
        import torch.nn as nn
        
        worker_config.training.max_grad_norm = 1.0
        
        trainer.model = nn.Linear(10, 10)
        trainer.optimizer = torch.optim.SGD(trainer.model.parameters(), lr=0.01)
        trainer.criterion = nn.MSELoss()
        
        data = torch.randn(4, 10)
        target = torch.randn(4, 10)
        
        loss, output = trainer._train_batch(data, target, 0, 0)
        
        assert isinstance(loss, float)


# ==================== Test Push Gradients ====================

class TestPushGradients:
    """Test pushing gradients to Parameter Server"""
    
    def test_push_gradients_success(self, trainer, mock_grpc_client):
        """Test successful gradient push"""
        pytest.importorskip("torch")
        import torch.nn as nn
        
        # Setup model with gradients
        trainer.model = nn.Linear(10, 10)
        
        # Create fake gradients
        for param in trainer.model.parameters():
            param.grad = param.data.clone()
        
        trainer._push_gradients(batch_idx=0, epoch=0, loss=0.5)
        
        mock_grpc_client.push_gradients.assert_called_once()
        
        # Check call arguments
        call_kwargs = mock_grpc_client.push_gradients.call_args[1]
        assert "gradients" in call_kwargs
        assert "metadata" in call_kwargs
        assert call_kwargs["metadata"]["loss"] == 0.5
    
    def test_push_gradients_failure_handled(self, trainer, mock_grpc_client):
        """Test graceful handling of gradient push failure"""
        pytest.importorskip("torch")
        import torch.nn as nn
        
        trainer.model = nn.Linear(10, 10)
        for param in trainer.model.parameters():
            param.grad = param.data.clone()
        
        mock_grpc_client.push_gradients.side_effect = Exception("Network error")
        
        # Should not raise, just log warning
        trainer._push_gradients(batch_idx=0, epoch=0, loss=0.5)


# ==================== Test Checkpoint Management ====================

class TestCheckpointManagement:
    """Test checkpoint saving and loading"""
    
    def test_save_checkpoint(self, trainer, temp_dir):
        """Test saving checkpoint"""
        pytest.importorskip("torch")
        import torch.nn as nn
        
        # Setup
        trainer.model = nn.Linear(10, 10)
        trainer.optimizer = torch.optim.SGD(trainer.model.parameters(), lr=0.01)
        trainer.checkpoint_manager = Mock()
        
        # Save
        trainer._save_checkpoint(epoch=0, loss=0.5, metrics={"accuracy": 0.9})
        
        trainer.checkpoint_manager.save_checkpoint.assert_called_once()
    
    def test_load_checkpoint(self, trainer, temp_dir):
        """Test loading checkpoint"""
        pytest.importorskip("torch")
        import torch
        import torch.nn as nn
        
        # Setup
        trainer.model = nn.Linear(10, 10)
        trainer.optimizer = torch.optim.SGD(trainer.model.parameters(), lr=0.01)
        
        # Mock checkpoint data
        checkpoint_data = {
            "model_state_dict": trainer.model.state_dict(),
            "optimizer_state_dict": trainer.optimizer.state_dict(),
            "epoch": 5,
            "iteration": 100
        }
        
        trainer.checkpoint_manager = Mock()
        trainer.checkpoint_manager.load_checkpoint.return_value = checkpoint_data
        
        # Load
        trainer._load_checkpoint(Path("/fake/checkpoint.pt"))
        
        assert trainer.current_epoch == 6  # epoch + 1
        assert trainer.current_iteration == 100


# ==================== Test Heartbeat Integration ====================

class TestHeartbeatIntegration:
    """Test heartbeat integration"""
    
    def test_start_heartbeat(self, trainer):
        """Test starting heartbeat"""
        trainer._start_heartbeat()
        
        assert trainer.heartbeat is not None
        assert trainer.heartbeat._running is True
        
        # Cleanup
        trainer.heartbeat.stop()
    
    def test_update_heartbeat_status(self, trainer):
        """Test updating heartbeat status"""
        trainer._start_heartbeat()
        
        trainer._update_heartbeat_status(
            state="training",
            current_epoch=5,
            loss=0.5
        )
        
        assert trainer.heartbeat._status["state"] == "training"
        assert trainer.heartbeat._status["current_epoch"] == 5
        
        # Cleanup
        trainer.heartbeat.stop()


# ==================== Test Training Initialization ====================

class TestTrainingInitialization:
    """Test complete training initialization"""
    
    def test_initialize_training_components(self, trainer):
        """Test initializing all training components"""
        pytest.importorskip("torch")
        
        # Need example model
        example_model = Path(__file__).parent.parent / "examples" / "example_model.py"
        if not example_model.exists():
            pytest.skip("Example model not found")
        
        trainer._initialize_training("test-model", checkpoint_path=None)
        
        assert trainer.checkpoint_manager is not None
        assert trainer.training_logger is not None
        assert trainer.model is not None
        assert trainer.optimizer is not None


# ==================== Test Cleanup ====================

class TestCleanup:
    """Test cleanup"""
    
    def test_cleanup_stops_heartbeat(self, trainer):
        """Test cleanup stops heartbeat"""
        trainer._start_heartbeat()
        assert trainer.heartbeat._running is True
        
        trainer._cleanup()
        
        assert trainer.heartbeat._running is False


# ==================== Integration Tests ====================

class TestIntegration:
    """Integration tests for complete training workflow"""
    
    @pytest.mark.slow
    def test_single_epoch_training(self, trainer, temp_dir):
        """Test training for one epoch"""
        pytest.importorskip("torch")
        import torch
        import torch.nn as nn
        from torch.utils.data import DataLoader, TensorDataset
        
        # Setup model
        trainer.model = nn.Linear(10, 10)
        trainer.optimizer = torch.optim.SGD(trainer.model.parameters(), lr=0.01)
        trainer.criterion = nn.MSELoss()
        
        # Setup data
        dataset = TensorDataset(
            torch.randn(40, 10),
            torch.randn(40, 10)
        )
        trainer.train_loader = DataLoader(dataset, batch_size=4)
        
        # Setup managers
        from meshml_worker.utils.checkpoint import CheckpointManager
        from meshml_worker.utils.logger import TrainingLogger
        
        trainer.checkpoint_manager = CheckpointManager(temp_dir, "test-model")
        trainer.training_logger = TrainingLogger(temp_dir, "test-model")
        
        # Train one epoch
        loss, metrics = trainer._train_epoch(0)
        
        assert isinstance(loss, float)
        assert "accuracy" in metrics or "num_batches" in metrics
