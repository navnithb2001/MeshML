"""
Main MeshML Worker Implementation

Coordinates training, communication, and checkpoint management.
"""

import logging
from pathlib import Path
from typing import Optional, Dict, Any
import signal
import sys

from meshml_worker.config import WorkerConfig


logger = logging.getLogger(__name__)


class MeshMLWorker:
    """MeshML Worker for Federated Learning
    
    Handles:
    - Communication with Parameter Server
    - Local training on data shards
    - Gradient computation and upload
    - Checkpoint management
    - Error recovery
    """
    
    def __init__(self, config: WorkerConfig):
        """Initialize worker
        
        Args:
            config: Worker configuration
        """
        self.config = config
        self.worker_id = config.worker.id
        self.running = False
        
        # Setup logging
        self._setup_logging()
        
        # Setup signal handlers
        self._setup_signal_handlers()
        
        logger.info(f"Worker initialized: {self.worker_id}")
    
    def _setup_logging(self) -> None:
        """Setup logging configuration"""
        logging.basicConfig(
            level=self.config.logging.level,
            format=self.config.logging.format
        )
        
        if self.config.logging.file:
            file_handler = logging.FileHandler(self.config.logging.file)
            file_handler.setFormatter(logging.Formatter(self.config.logging.format))
            logging.getLogger().addHandler(file_handler)
    
    def _setup_signal_handlers(self) -> None:
        """Setup signal handlers for graceful shutdown"""
        def signal_handler(signum: int, frame: Any) -> None:
            logger.info(f"Received signal {signum}, shutting down gracefully...")
            self.running = False
        
        signal.signal(signal.SIGINT, signal_handler)
        signal.signal(signal.SIGTERM, signal_handler)
    
    def train(
        self,
        model_id: str,
        epochs: Optional[int] = None,
        checkpoint_path: Optional[Path] = None
    ) -> None:
        """Start training on a model
        
        Args:
            model_id: Model ID to train
            epochs: Number of epochs (None = train until convergence)
            checkpoint_path: Path to resume from checkpoint
        """
        self.running = True
        
        logger.info(f"Starting training on model: {model_id}")
        logger.info(f"  Worker ID: {self.worker_id}")
        logger.info(f"  Device: {self.config.training.device}")
        logger.info(f"  Batch size: {self.config.training.batch_size}")
        
        if checkpoint_path:
            logger.info(f"  Resuming from: {checkpoint_path}")
        
        try:
            # Import training components (lazy import for faster CLI)
            from meshml_worker.training.trainer import Trainer
            from meshml_worker.communication.grpc_client import GRPCClient
            from meshml_worker.utils.device import get_device
            
            # Detect device
            device = get_device(self.config.training.device)
            logger.info(f"Using device: {device}")
            
            # Initialize gRPC client
            grpc_client = GRPCClient(self.config.parameter_server)
            logger.info("Connected to Parameter Server")
            
            # Initialize trainer
            trainer = Trainer(
                config=self.config,
                grpc_client=grpc_client,
                device=device
            )
            
            # Start training
            trainer.train(
                model_id=model_id,
                epochs=epochs,
                checkpoint_path=checkpoint_path
            )
            
            logger.info("Training completed successfully")
            
        except KeyboardInterrupt:
            logger.info("Training interrupted by user")
            raise
        except Exception as e:
            logger.error(f"Training failed: {e}", exc_info=True)
            raise
        finally:
            self.running = False
    
    def validate_setup(self) -> Dict[str, Any]:
        """Validate worker setup
        
        Returns:
            Validation results
        """
        results: Dict[str, Any] = {
            "valid": True,
            "checks": {}
        }
        
        # Check PyTorch installation
        try:
            import torch
            results["checks"]["pytorch"] = {
                "installed": True,
                "version": torch.__version__
            }
        except ImportError:
            results["checks"]["pytorch"] = {
                "installed": False,
                "error": "PyTorch not installed"
            }
            results["valid"] = False
        
        # Check storage directories
        try:
            self.config.storage.create_directories()
            results["checks"]["storage"] = {"created": True}
        except Exception as e:
            results["checks"]["storage"] = {
                "created": False,
                "error": str(e)
            }
            results["valid"] = False
        
        # Check Parameter Server connectivity
        try:
            import requests
            response = requests.get(
                f"{self.config.parameter_server.url}/health",
                timeout=self.config.parameter_server.timeout
            )
            results["checks"]["parameter_server"] = {
                "reachable": response.status_code == 200
            }
        except Exception as e:
            results["checks"]["parameter_server"] = {
                "reachable": False,
                "error": str(e)
            }
            # Don't mark as invalid - server might not be running yet
        
        return results
