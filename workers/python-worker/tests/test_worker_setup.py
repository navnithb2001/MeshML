"""
Tests for Worker Setup (TASK-8.1)

Tests:
- Configuration creation and validation
- CLI initialization
- Device detection
- Checkpoint management
- Logger setup
"""

import pytest
from pathlib import Path
import tempfile
import shutil

from meshml_worker.config import (
    WorkerConfig,
    ParameterServerConfig,
    WorkerIdentityConfig,
    TrainingConfig,
    StorageConfig,
    LoggingConfig
)
from meshml_worker.utils.device import get_device, get_device_info
from meshml_worker.utils.checkpoint import CheckpointManager
from meshml_worker.utils.logger import setup_logger, TrainingLogger


# ==================== Fixtures ====================

@pytest.fixture
def temp_dir():
    """Create temporary directory"""
    temp_path = Path(tempfile.mkdtemp())
    yield temp_path
    shutil.rmtree(temp_path, ignore_errors=True)


@pytest.fixture
def basic_config():
    """Create basic worker configuration"""
    return WorkerConfig()


# ==================== Test Configuration ====================

class TestConfiguration:
    """Test configuration management"""
    
    def test_default_config_creation(self):
        """Test creating default configuration"""
        config = WorkerConfig()
        
        assert config.worker.name == "MeshML Worker"
        assert config.parameter_server.url == "http://localhost:8003"
        assert config.training.batch_size == 32
        assert config.training.device == "auto"
    
    def test_config_validation(self):
        """Test configuration validation"""
        # Valid config
        config = WorkerConfig(
            training=TrainingConfig(batch_size=64)
        )
        assert config.training.batch_size == 64
        
        # Invalid batch size
        with pytest.raises(ValueError):
            WorkerConfig(
                training=TrainingConfig(batch_size=-1)
            )
    
    def test_config_save_and_load(self, temp_dir):
        """Test saving and loading configuration"""
        config_path = temp_dir / "config.yaml"
        
        # Create and save config
        config = WorkerConfig()
        config.worker.id = "test-worker"
        config.worker.name = "Test Worker"
        config.training.batch_size = 64
        config.storage.base_dir = temp_dir
        
        config.save_to_file(config_path)
        
        # Load config
        loaded_config = WorkerConfig.from_file(config_path)
        
        assert loaded_config.worker.id == "test-worker"
        assert loaded_config.worker.name == "Test Worker"
        assert loaded_config.training.batch_size == 64
    
    def test_storage_directory_creation(self, temp_dir):
        """Test storage directory creation"""
        config = WorkerConfig()
        config.storage.base_dir = temp_dir / "storage"
        
        config.setup()
        
        assert config.storage.checkpoints_dir.exists()
        assert config.storage.models_dir.exists()
        assert config.storage.data_dir.exists()
    
    def test_worker_id_generation(self):
        """Test automatic worker ID generation"""
        config = WorkerConfig()
        config.setup()
        
        assert config.worker.id is not None
        assert config.worker.id.startswith("worker-")


# ==================== Test Device Detection ====================

class TestDeviceDetection:
    """Test device detection and management"""
    
    def test_device_detection(self):
        """Test automatic device detection"""
        device = get_device("auto")
        
        # Should return one of the valid devices
        assert device in ["cuda:0", "mps", "cpu"]
    
    def test_cpu_device(self):
        """Test CPU device selection"""
        device = get_device("cpu")
        assert device == "cpu"
    
    def test_device_info(self):
        """Test getting device information"""
        info = get_device_info()
        
        assert "cuda_available" in info
        assert "mps_available" in info
        assert "cpu_count" in info
        assert info["cpu_count"] > 0


# ==================== Test Checkpoint Management ====================

class TestCheckpointManagement:
    """Test checkpoint saving and loading"""
    
    def test_checkpoint_manager_creation(self, temp_dir):
        """Test creating checkpoint manager"""
        manager = CheckpointManager(
            checkpoint_dir=temp_dir,
            model_id="test-model"
        )
        
        assert manager.model_checkpoint_dir.exists()
        assert manager.model_id == "test-model"
    
    def test_save_checkpoint(self, temp_dir):
        """Test saving checkpoint"""
        pytest.importorskip("torch")
        import torch
        
        manager = CheckpointManager(
            checkpoint_dir=temp_dir,
            model_id="test-model"
        )
        
        # Create dummy model state
        model_state = {"layer1.weight": torch.randn(10, 10)}
        optimizer_state = {"state": {}}
        
        # Save checkpoint
        checkpoint_path = manager.save_checkpoint(
            model_state=model_state,
            optimizer_state=optimizer_state,
            epoch=1,
            iteration=100,
            loss=0.5,
            metrics={"accuracy": 0.9}
        )
        
        assert checkpoint_path.exists()
        assert manager.metadata["best_loss"] == 0.5
    
    def test_load_checkpoint(self, temp_dir):
        """Test loading checkpoint"""
        pytest.importorskip("torch")
        import torch
        
        manager = CheckpointManager(
            checkpoint_dir=temp_dir,
            model_id="test-model"
        )
        
        # Save checkpoint
        model_state = {"layer1.weight": torch.randn(10, 10)}
        manager.save_checkpoint(
            model_state=model_state,
            optimizer_state={},
            epoch=1,
            iteration=100,
            loss=0.5
        )
        
        # Load checkpoint
        checkpoint_data = manager.load_checkpoint()
        
        assert checkpoint_data["epoch"] == 1
        assert checkpoint_data["iteration"] == 100
        assert checkpoint_data["loss"] == 0.5
        assert "model_state_dict" in checkpoint_data
    
    def test_best_checkpoint_tracking(self, temp_dir):
        """Test tracking best checkpoint"""
        pytest.importorskip("torch")
        import torch
        
        manager = CheckpointManager(
            checkpoint_dir=temp_dir,
            model_id="test-model",
            keep_best_n=2
        )
        
        # Save checkpoints with different losses
        for i, loss in enumerate([0.8, 0.5, 0.9, 0.3]):
            manager.save_checkpoint(
                model_state={"weight": torch.randn(5, 5)},
                optimizer_state={},
                epoch=i,
                iteration=i * 100,
                loss=loss
            )
        
        # Best checkpoint should have loss 0.3
        assert manager.metadata["best_loss"] == 0.3
        
        # Should keep only 2 best checkpoints
        assert len(manager.metadata["checkpoints"]) == 2


# ==================== Test Logging ====================

class TestLogging:
    """Test logging utilities"""
    
    def test_logger_setup(self, temp_dir):
        """Test setting up logger"""
        log_file = temp_dir / "test.log"
        
        logger = setup_logger(
            name="test_logger",
            level="INFO",
            log_file=log_file,
            colored=False
        )
        
        logger.info("Test message")
        
        assert log_file.exists()
        assert "Test message" in log_file.read_text()
    
    def test_training_logger(self, temp_dir):
        """Test training logger"""
        logger = TrainingLogger(
            log_dir=temp_dir,
            model_id="test-model"
        )
        
        logger.log_epoch(
            epoch=1,
            loss=0.5,
            accuracy=0.9,
            other_metrics={"f1": 0.85}
        )
        
        # Check log file was created
        log_files = list(temp_dir.glob("training_*.log"))
        assert len(log_files) > 0


# ==================== Test CLI Integration ====================

class TestCLI:
    """Test CLI commands"""
    
    def test_init_command(self, temp_dir):
        """Test worker initialization via CLI"""
        from click.testing import CliRunner
        from meshml_worker.cli import init
        
        runner = CliRunner()
        
        with runner.isolated_filesystem(temp_dir=temp_dir):
            result = runner.invoke(init, [
                "--worker-id", "test-worker",
                "--parameter-server-url", "http://localhost:8000",
                "--device", "cpu",
                "--batch-size", "64"
            ])
            
            assert result.exit_code == 0
            assert "Worker initialized successfully" in result.output
            
            # Check config file was created
            config_path = Path(".meshml") / "config.yaml"
            assert config_path.exists()
    
    def test_status_command(self, temp_dir):
        """Test status command"""
        from click.testing import CliRunner
        from meshml_worker.cli import init, status
        
        runner = CliRunner()
        
        with runner.isolated_filesystem(temp_dir=temp_dir):
            # Initialize first
            result_init = runner.invoke(init, ["--worker-id", "test-worker"])
            assert result_init.exit_code == 0
            
            # Check status
            result = runner.invoke(status)
            
            assert result.exit_code == 0
            assert "Worker Status" in result.output
            assert "ID:" in result.output  # Just check that ID is shown


# ==================== Integration Tests ====================

class TestIntegration:
    """Integration tests for worker setup"""
    
    def test_complete_initialization(self, temp_dir):
        """Test complete worker initialization flow"""
        # Create configuration
        config = WorkerConfig()
        config.worker.id = "integration-test-worker"
        config.storage.base_dir = temp_dir
        config.setup()
        
        # Save configuration
        config_path = config.get_config_path()
        config.save_to_file(config_path)
        
        # Verify directories
        assert config.storage.checkpoints_dir.exists()
        assert config.storage.models_dir.exists()
        assert config.storage.data_dir.exists()
        
        # Verify config file
        assert config_path.exists()
        
        # Load and verify
        loaded_config = WorkerConfig.from_file(config_path)
        assert loaded_config.worker.id == "integration-test-worker"
