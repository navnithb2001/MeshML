"""
Training Loop Implementation

Handles:
- Data shard downloading
- Local training on assigned data
- Gradient computation and upload
- Checkpoint management
- Progress tracking
"""

import logging
import time
from pathlib import Path
from typing import Optional, Dict, Any, Callable
import torch
import torch.nn as nn
from torch.cuda.amp import autocast, GradScaler
from tqdm import tqdm

from meshml_worker.config import WorkerConfig
from meshml_worker.training.model_loader import ModelLoader
from meshml_worker.training.dataloader import download_data_shard
from meshml_worker.communication.grpc_client import GRPCClient
from meshml_worker.communication.heartbeat import HeartbeatSender
from meshml_worker.utils.checkpoint import CheckpointManager
from meshml_worker.utils.logger import TrainingLogger
from meshml_worker.utils.optimization import (
    MemoryProfiler,
    PerformanceBenchmark,
    OptimizedDataLoader,
)

logger = logging.getLogger(__name__)


class Trainer:
    """Training loop implementation
    
    Features:
    - Download and use data shards
    - Local training with PyTorch
    - Gradient computation and upload
    - Mixed precision training
    - Checkpoint management
    - Progress tracking
    - Heartbeat monitoring
    - Memory profiling and optimization
    - Performance benchmarking
    """
    
    def __init__(
        self,
        config: WorkerConfig,
        grpc_client: GRPCClient,
        device: str
    ):
        """Initialize trainer
        
        Args:
            config: Worker configuration
            grpc_client: gRPC client for communication
            device: Training device
        """
        self.config = config
        self.grpc_client = grpc_client
        self.device = device
        
        # Components
        self.model: Optional[nn.Module] = None
        self.optimizer: Optional[torch.optim.Optimizer] = None
        self.criterion: Optional[nn.Module] = None
        self.scaler: Optional[GradScaler] = None
        
        # Data
        self.train_loader: Optional[Any] = None
        self.val_loader: Optional[Any] = None
        
        # State
        self.current_epoch = 0
        self.current_iteration = 0
        self.global_version = 0
        
        # Managers
        self.checkpoint_manager: Optional[CheckpointManager] = None
        self.training_logger: Optional[TrainingLogger] = None
        self.heartbeat: Optional[HeartbeatSender] = None
        
        # Optimization tools
        self.memory_profiler: Optional[MemoryProfiler] = None
        self.performance_benchmark: Optional[PerformanceBenchmark] = None
        
        # Mixed precision
        if config.training.mixed_precision and device.startswith("cuda"):
            self.scaler = GradScaler()
            logger.info("Mixed precision training enabled")
        
        logger.info(f"Trainer initialized: device={device}")
    
    def train(
        self,
        model_id: str,
        epochs: Optional[int] = None,
        checkpoint_path: Optional[Path] = None
    ) -> None:
        """Start training on a model
        
        Args:
            model_id: Model ID
            epochs: Number of epochs (None = train until convergence)
            checkpoint_path: Resume from checkpoint
        """
        logger.info(f"Starting training: model_id={model_id}")
        
        try:
            # Initialize components
            self._initialize_training(model_id, checkpoint_path)
            
            # Start heartbeat
            self._start_heartbeat()
            
            # Training loop
            max_epochs = epochs or 100  # Default max epochs
            
            for epoch in range(self.current_epoch, max_epochs):
                self.current_epoch = epoch
                
                logger.info(f"Starting epoch {epoch + 1}/{max_epochs}")
                
                # Train one epoch
                epoch_loss, epoch_metrics = self._train_epoch(epoch)
                
                # Log epoch results
                self.training_logger.log_epoch(
                    epoch=epoch,
                    loss=epoch_loss,
                    accuracy=epoch_metrics.get("accuracy"),
                    other_metrics=epoch_metrics
                )
                
                # Save checkpoint
                self._save_checkpoint(epoch, epoch_loss, epoch_metrics)
                
                # Update heartbeat
                self._update_heartbeat_status(
                    state="training",
                    current_epoch=epoch,
                    loss=epoch_loss,
                    metrics=epoch_metrics
                )
                
                logger.info(
                    f"Epoch {epoch + 1} completed: loss={epoch_loss:.4f}, "
                    f"metrics={epoch_metrics}"
                )
            
            logger.info("Training completed successfully")
            
        except KeyboardInterrupt:
            logger.info("Training interrupted by user")
            raise
        except Exception as e:
            logger.error(f"Training failed: {e}", exc_info=True)
            raise
        finally:
            self._cleanup()
    
    def _initialize_training(
        self,
        model_id: str,
        checkpoint_path: Optional[Path]
    ) -> None:
        """Initialize training components
        
        Args:
            model_id: Model ID
            checkpoint_path: Optional checkpoint to resume from
        """
        logger.info("Initializing training components...")
        
        # Initialize checkpoint manager
        self.checkpoint_manager = CheckpointManager(
            checkpoint_dir=self.config.storage.checkpoints_dir,
            model_id=model_id
        )
        
        # Initialize training logger
        self.training_logger = TrainingLogger(
            log_dir=self.config.storage.base_dir / "logs",
            model_id=model_id
        )
        
        # Initialize optimization tools
        self.memory_profiler = MemoryProfiler(device=self.device)
        self.performance_benchmark = PerformanceBenchmark()
        logger.info("Memory profiler and performance benchmark initialized")
        
        # Load model definition
        self._load_model(model_id)
        
        # Load data
        self._load_data(model_id)
        
        # Initialize optimizer
        self._initialize_optimizer()
        
        # Load checkpoint if provided
        if checkpoint_path:
            self._load_checkpoint(checkpoint_path)
        else:
            # Fetch initial weights from Parameter Server
            self._fetch_weights(model_id)
        
        logger.info("Training initialization complete")
    
    def _load_model(self, model_id: str) -> None:
        """Load model definition
        
        Args:
            model_id: Model ID
        """
        logger.info(f"Loading model definition for {model_id}")
        
        # In production, would get model source from API
        # For now, use example model
        example_model_path = Path(__file__).parent.parent.parent / "examples" / "example_model.py"
        
        if not example_model_path.exists():
            raise FileNotFoundError(f"Model file not found: {example_model_path}")
        
        # Load model
        model_loader = ModelLoader(models_dir=self.config.storage.models_dir)
        create_model, create_dataloader, metadata = model_loader.load_model(
            model_source=str(example_model_path),
            model_id=model_id
        )
        
        # Create model instance
        self.model = create_model(device=self.device)
        self.create_dataloader_fn = create_dataloader
        
        # Initialize criterion (cross-entropy for classification)
        self.criterion = nn.CrossEntropyLoss()
        
        logger.info(f"Model loaded: {metadata['name']} v{metadata['version']}")
    
    def _load_data(self, model_id: str) -> None:
        """Load training data with optimized settings
        
        Args:
            model_id: Model ID
        """
        logger.info("Loading training data...")
        
        # In production, would download data shard from Dataset Sharder
        # For now, use the create_dataloader function from model definition
        
        if self.create_dataloader_fn is None:
            raise ValueError("No create_dataloader function available")
        
        # Create training dataloader with optimized settings
        # The create_dataloader_fn from model definition returns a DataLoader
        # We use it directly since it may have model-specific settings
        self.train_loader = self.create_dataloader_fn(
            data_path=str(self.config.storage.data_dir),
            batch_size=self.config.training.batch_size,
            is_train=True,
            num_workers=self.config.training.num_workers
        )
        
        logger.info(f"Data loaded: {len(self.train_loader)} batches")
        logger.info(f"DataLoader settings: batch_size={self.config.training.batch_size}, "
                   f"num_workers={self.config.training.num_workers}")
    
    def _initialize_optimizer(self) -> None:
        """Initialize optimizer"""
        # Use Adam optimizer
        self.optimizer = torch.optim.Adam(
            self.model.parameters(),
            lr=0.001
        )
        
        logger.info("Optimizer initialized: Adam(lr=0.001)")
    
    def _fetch_weights(self, model_id: str) -> None:
        """Fetch initial weights from Parameter Server
        
        Args:
            model_id: Model ID
        """
        logger.info("Fetching initial weights from Parameter Server...")
        
        try:
            state_dict, version = self.grpc_client.get_weights(
                job_id=model_id,
                worker_id=self.config.worker.id,
                epoch=self.current_epoch
            )
            
            # Load state dict (if compatible)
            # In production, would handle state dict loading properly
            self.global_version = version
            
            logger.info(f"Fetched weights: version={version}")
            
        except Exception as e:
            logger.warning(f"Failed to fetch weights, using random initialization: {e}")
    
    def _train_epoch(self, epoch: int) -> tuple:
        """Train one epoch with profiling and benchmarking
        
        Args:
            epoch: Current epoch
            
        Returns:
            Tuple of (average_loss, metrics)
        """
        self.model.train()
        
        epoch_loss = 0.0
        num_batches = 0
        correct = 0
        total = 0
        
        # Start epoch benchmark
        if self.performance_benchmark:
            self.performance_benchmark.start_epoch()
        
        # Progress bar
        pbar = tqdm(
            self.train_loader,
            desc=f"Epoch {epoch + 1}",
            leave=False
        )
        
        for batch_idx, (data, target) in enumerate(pbar):
            # Start batch benchmark
            if self.performance_benchmark:
                self.performance_benchmark.start_batch()
            
            # Move to device
            data = data.to(self.device)
            target = target.to(self.device)
            
            # Forward pass with optional profiling
            if self.memory_profiler and batch_idx % 10 == 0:  # Profile every 10th batch
                with self.memory_profiler.profile(f"epoch_{epoch}_batch_{batch_idx}"):
                    loss, predictions = self._train_batch(data, target, batch_idx, epoch)
            else:
                loss, predictions = self._train_batch(data, target, batch_idx, epoch)
            
            # Update metrics
            epoch_loss += loss
            num_batches += 1
            
            # Calculate accuracy
            _, predicted = torch.max(predictions, 1)
            total += target.size(0)
            correct += (predicted == target).sum().item()
            
            # End batch benchmark
            if self.performance_benchmark:
                self.performance_benchmark.end_batch(batch_size=data.size(0))
            
            # Update progress bar
            current_loss = epoch_loss / num_batches
            current_acc = 100.0 * correct / total
            pbar.set_postfix({
                "loss": f"{current_loss:.4f}",
                "acc": f"{current_acc:.2f}%"
            })
            
            # Periodic checkpoint
            if (batch_idx + 1) % 100 == 0:
                self._update_heartbeat_status(
                    state="training",
                    current_epoch=epoch,
                    current_batch=batch_idx,
                    total_batches=len(self.train_loader),
                    loss=current_loss
                )
        
        # End epoch benchmark
        if self.performance_benchmark:
            self.performance_benchmark.end_epoch()
        
        avg_loss = epoch_loss / num_batches
        accuracy = 100.0 * correct / total
        
        metrics = {
            "accuracy": accuracy,
            "num_batches": num_batches,
            "num_samples": total
        }
        
        # Log performance stats every few epochs
        if self.performance_benchmark and epoch % 5 == 0:
            self.performance_benchmark.print_summary()
        
        return avg_loss, metrics
    
    def _train_batch(
        self,
        data: torch.Tensor,
        target: torch.Tensor,
        batch_idx: int,
        epoch: int
    ) -> tuple:
        """Train single batch
        
        Args:
            data: Input data
            target: Target labels
            batch_idx: Batch index
            epoch: Current epoch
            
        Returns:
            Tuple of (loss, predictions)
        """
        self.optimizer.zero_grad()
        
        # Mixed precision training
        if self.scaler is not None:
            with autocast():
                output = self.model(data)
                loss = self.criterion(output, target)
            
            self.scaler.scale(loss).backward()
            
            # Gradient clipping
            if self.config.training.max_grad_norm > 0:
                self.scaler.unscale_(self.optimizer)
                torch.nn.utils.clip_grad_norm_(
                    self.model.parameters(),
                    self.config.training.max_grad_norm
                )
            
            self.scaler.step(self.optimizer)
            self.scaler.update()
        else:
            # Standard training
            output = self.model(data)
            loss = self.criterion(output, target)
            loss.backward()
            
            # Gradient clipping
            if self.config.training.max_grad_norm > 0:
                torch.nn.utils.clip_grad_norm_(
                    self.model.parameters(),
                    self.config.training.max_grad_norm
                )
            
            self.optimizer.step()
        
        # Push gradients to Parameter Server (periodically)
        if (batch_idx + 1) % self.config.training.gradient_accumulation_steps == 0:
            self._push_gradients(batch_idx, epoch, loss.item())
        
        self.current_iteration += 1
        
        return loss.item(), output
    
    def _push_gradients(
        self,
        batch_idx: int,
        epoch: int,
        loss: float
    ) -> None:
        """Push gradients to Parameter Server
        
        Args:
            batch_idx: Batch index
            epoch: Current epoch
            loss: Current loss
        """
        try:
            # Extract gradients
            gradients = {}
            gradient_norm = 0.0
            
            for name, param in self.model.named_parameters():
                if param.grad is not None:
                    gradients[name] = param.grad.cpu().numpy().tolist()
                    gradient_norm += param.grad.norm().item() ** 2
            
            gradient_norm = gradient_norm ** 0.5
            
            # Prepare metadata
            metadata = {
                "loss": loss,
                "gradient_norm": gradient_norm,
                "computation_time_ms": 0
            }
            
            # Push to Parameter Server
            response = self.grpc_client.push_gradients(
                job_id="default",  # Would be actual job ID
                worker_id=self.config.worker.id,
                gradients=gradients,
                batch_id=batch_idx,
                epoch=epoch,
                batch_size=self.config.training.batch_size,
                learning_rate=0.001,
                metadata=metadata
            )
            
            logger.debug(f"Gradients pushed: batch={batch_idx}, response={response}")
            
        except Exception as e:
            logger.warning(f"Failed to push gradients: {e}")
    
    def _save_checkpoint(
        self,
        epoch: int,
        loss: float,
        metrics: Dict[str, Any]
    ) -> None:
        """Save training checkpoint
        
        Args:
            epoch: Current epoch
            loss: Current loss
            metrics: Training metrics
        """
        try:
            self.checkpoint_manager.save_checkpoint(
                model_state=self.model.state_dict(),
                optimizer_state=self.optimizer.state_dict(),
                epoch=epoch,
                iteration=self.current_iteration,
                loss=loss,
                metrics=metrics,
                is_best=(epoch == 0 or loss < getattr(self, '_best_loss', float('inf')))
            )
            
            self._best_loss = min(loss, getattr(self, '_best_loss', float('inf')))
            
        except Exception as e:
            logger.warning(f"Failed to save checkpoint: {e}")
    
    def _load_checkpoint(self, checkpoint_path: Path) -> None:
        """Load checkpoint
        
        Args:
            checkpoint_path: Path to checkpoint
        """
        logger.info(f"Loading checkpoint: {checkpoint_path}")
        
        try:
            checkpoint_data = self.checkpoint_manager.load_checkpoint(checkpoint_path)
            
            # Load model state
            self.model.load_state_dict(checkpoint_data["model_state_dict"])
            
            # Load optimizer state
            self.optimizer.load_state_dict(checkpoint_data["optimizer_state_dict"])
            
            # Load training state
            self.current_epoch = checkpoint_data["epoch"] + 1
            self.current_iteration = checkpoint_data["iteration"]
            
            logger.info(f"Checkpoint loaded: epoch={self.current_epoch}")
            
        except Exception as e:
            logger.error(f"Failed to load checkpoint: {e}")
            raise
    
    def _start_heartbeat(self) -> None:
        """Start heartbeat monitoring"""
        self.heartbeat = HeartbeatSender(
            worker_id=self.config.worker.id,
            heartbeat_interval=30
        )
        
        # Set heartbeat callback
        def heartbeat_callback(data):
            # In production, would send via HTTP or gRPC
            logger.debug(f"Heartbeat: {data}")
            return True
        
        self.heartbeat.set_heartbeat_callback(heartbeat_callback)
        self.heartbeat.start()
        
        logger.info("Heartbeat started")
    
    def _update_heartbeat_status(self, **kwargs) -> None:
        """Update heartbeat status
        
        Args:
            **kwargs: Status fields to update
        """
        if self.heartbeat:
            self.heartbeat.update_status(**kwargs)
    
    def _cleanup(self) -> None:
        """Cleanup resources"""
        logger.info("Cleaning up...")
        
        if self.heartbeat:
            self.heartbeat.stop()
        
        # Update final status
        self._update_heartbeat_status(state="idle")
        
        logger.info("Cleanup complete")
