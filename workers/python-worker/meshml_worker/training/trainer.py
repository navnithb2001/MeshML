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
from typing import Optional, Dict, Any, Callable, List
import torch
import torch.nn as nn
from torch.cuda.amp import autocast, GradScaler
from tqdm import tqdm

from meshml_worker.config import WorkerConfig
from meshml_worker.training.model_loader import ModelLoader
from meshml_worker.training.dataloader import download_data_shard
from meshml_worker.communication.http_client import HTTPClient
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
        grpc_client: HTTPClient,
        device: str,
        orchestrator_client: Optional[Any] = None,
        job_id: Optional[str] = None,
        model_path: Optional[Path] = None,
        data_paths: Optional[List[Path]] = None
    ):
        """Initialize trainer
        
        Args:
            config: Worker configuration
            grpc_client: HTTP client for communication (previously gRPC, now HTTP)
            device: Training device
            orchestrator_client: Optional Task Orchestrator client for reporting
            job_id: Optional job ID (for orchestrated training)
            model_path: Optional path to model file (overrides default model)
            data_paths: Optional list of data shard paths (overrides data loading)
        """
        self.config = config
        self.grpc_client = grpc_client  # Note: keeping name for backwards compatibility
        self.device = device
        
        # Orchestrator integration
        self.orchestrator_client = orchestrator_client
        self.job_id = job_id
        self.model_path = model_path
        self.data_paths = data_paths
        
        # Components
        self.model: Optional[nn.Module] = None
        self.optimizer: Optional[torch.optim.Optimizer] = None
        self.criterion: Optional[nn.Module] = None
        self.scaler: Optional[GradScaler] = None
        
        # Data
        self.train_loader: Optional[Any] = None
        self.val_loader: Optional[Any] = None
        
        # State
        self.model_id: Optional[str] = None  # Current training model ID
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
    
    async def train(
        self,
        model_id: str,
        job_id: str,
        batch_ids: List[str],
        epochs: Optional[int] = None
    ) -> None:
        """Training loop with Task Orchestrator integration
        
        This method:
        1. Loads data from pre-downloaded shards
        2. Trains the model
        3. Reports progress to Task Orchestrator after each batch
        
        Args:
            model_id: Model ID
            job_id: Job ID from Task Orchestrator
            batch_ids: List of batch IDs assigned to this worker
            epochs: Number of epochs (None = train until convergence)
        """
        logger.info(f"Starting orchestrated training: model_id={model_id}, job_id={job_id}")
        logger.info(f"Assigned batches: {len(batch_ids)}")
        
        try:
            # Initialize components (without data loading and checkpoint)
            self._initialize_training_minimal(model_id)
            
            # Load data - use pre-downloaded shards
            if self.data_paths:
                logger.info(f"Using {len(self.data_paths)} pre-downloaded data shards")
                self.train_loader = self._create_dataloader_from_shards(
                    shard_paths=self.data_paths,
                    batch_size=self.config.training.batch_size,
                    num_workers=self.config.training.num_workers
                )
            else:
                logger.warning("No pre-downloaded data paths, cannot train")
                raise ValueError("Orchestrated mode requires pre-downloaded data_paths")
            
            # Training loop
            max_epochs = epochs or 100
            
            for epoch in range(self.current_epoch, max_epochs):
                self.current_epoch = epoch
                
                logger.info(f"Epoch {epoch + 1}/{max_epochs}")
                
                # Train one epoch with batch-level reporting
                epoch_loss, epoch_metrics = await self._train_epoch_with_reporting(
                    epoch=epoch,
                    job_id=job_id,
                    batch_ids=batch_ids
                )
                
                # Log epoch results
                self.training_logger.log_epoch(
                    epoch=epoch,
                    loss=epoch_loss,
                    accuracy=epoch_metrics.get("accuracy"),
                    other_metrics=epoch_metrics
                )
                
                # Save checkpoint
                self._save_checkpoint(epoch, epoch_loss, epoch_metrics)
                
                logger.info(
                    f"Epoch {epoch + 1} completed: loss={epoch_loss:.4f}, "
                    f"accuracy={epoch_metrics.get('accuracy', 'N/A')}"
                )
            
            logger.info("Orchestrated training completed successfully")
            
        except KeyboardInterrupt:
            logger.info("Training interrupted by user")
            # Report failure to orchestrator
            if self.orchestrator_client:
                for batch_id in batch_ids:
                    try:
                        await self.orchestrator_client.report_batch_failed(
                            job_id=job_id,
                            batch_id=batch_id,
                            epoch=self.current_epoch,
                            error_message="Training interrupted by user"
                        )
                    except Exception as e:
                        logger.error(f"Failed to report failure for batch {batch_id}: {e}")
            raise
        except Exception as e:
            logger.error(f"Orchestrated training failed: {e}", exc_info=True)
            # Report failure to orchestrator
            if self.orchestrator_client:
                for batch_id in batch_ids:
                    try:
                        await self.orchestrator_client.report_batch_failed(
                            job_id=job_id,
                            batch_id=batch_id,
                            epoch=self.current_epoch,
                            error_message=str(e)
                        )
                    except Exception as report_err:
                        logger.error(f"Failed to report failure for batch {batch_id}: {report_err}")
            raise
        finally:
            self._cleanup()
    
    async def _train_epoch_with_reporting(
        self,
        epoch: int,
        job_id: str,
        batch_ids: List[str]
    ) -> tuple:
        """Train one epoch with batch-level progress reporting to Task Orchestrator
        
        Args:
            epoch: Current epoch number
            job_id: Job ID
            batch_ids: List of batch IDs assigned to this worker
            
        Returns:
            Tuple of (average_loss, metrics_dict)
        """
        if self.model is None or self.train_loader is None:
            raise RuntimeError("Model or data not loaded")
        
        self.model.train()
        epoch_loss = 0.0
        correct = 0
        total = 0
        batch_count = 0
        
        # Track which batch ID we're processing
        current_batch_idx = 0
        batches_per_shard = len(self.train_loader) // len(batch_ids) if batch_ids else len(self.train_loader)
        
        pbar = tqdm(self.train_loader, desc=f"Epoch {epoch + 1}")
        
        for batch_idx, (data, target) in enumerate(pbar):
            # Move data to device
            data = data.to(self.device)
            target = target.to(self.device)
            
            # Zero gradients
            self.optimizer.zero_grad()
            
            # Forward pass
            if self.scaler:
                # Mixed precision training
                with autocast():
                    output = self.model(data)
                    loss = self.criterion(output, target)
                
                self.scaler.scale(loss).backward()
                self.scaler.step(self.optimizer)
                self.scaler.update()
            else:
                # Regular training
                output = self.model(data)
                loss = self.criterion(output, target)
                loss.backward()
                self.optimizer.step()
            
            # Update metrics
            epoch_loss += loss.item()
            _, predicted = torch.max(output.data, 1)
            total += target.size(0)
            correct += (predicted == target).sum().item()
            batch_count += 1
            
            # Update progress bar
            avg_loss = epoch_loss / batch_count
            accuracy = 100.0 * correct / total
            pbar.set_postfix({
                "loss": f"{avg_loss:.4f}",
                "acc": f"{accuracy:.2f}%"
            })
            
            # Report to orchestrator every N batches or at the end of a shard
            if self.orchestrator_client and batch_ids and (batch_idx + 1) % batches_per_shard == 0:
                if current_batch_idx < len(batch_ids):
                    batch_id = batch_ids[current_batch_idx]
                    try:
                        await self.orchestrator_client.report_batch_complete(
                            job_id=job_id,
                            batch_id=batch_id,
                            epoch=epoch,
                            loss=avg_loss,
                            accuracy=accuracy,
                            samples_processed=total,
                            training_time=0.0  # Could add timer here
                        )
                        logger.debug(f"Reported completion for batch {batch_id}")
                    except Exception as e:
                        logger.warning(f"Failed to report batch completion: {e}")
                    
                    current_batch_idx += 1
        
        # Calculate final metrics
        avg_loss = epoch_loss / batch_count if batch_count > 0 else 0
        accuracy = 100.0 * correct / total if total > 0 else 0
        
        metrics = {
            "accuracy": accuracy,
            "correct": correct,
            "total": total
        }
        
        return avg_loss, metrics
    
    def _initialize_training_minimal(
        self,
        model_id: str
    ) -> None:
        """Initialize training components for orchestrated mode (minimal version)
        
        This skips data loading since data_paths are provided externally.
        
        Args:
            model_id: Model ID
        """
        logger.info("Initializing training components (minimal for orchestrated mode)...")
        
        # Store model ID
        self.model_id = model_id
        
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
        
        # Register worker with Parameter Server
        try:
            self.grpc_client.register_worker(
                worker_id=self.config.worker.id or "unknown",
                model_id=model_id,
                metadata={"device": self.device}
            )
            logger.info(f"Worker registered with Parameter Server for model {model_id}")
        except Exception as e:
            logger.warning(f"Failed to register worker: {e}")
        
        # Load model definition
        self._load_model(model_id)
        
        # Initialize optimizer
        self._initialize_optimizer()
        
        # Fetch initial weights from Parameter Server
        self._fetch_weights(model_id)
        
        logger.info("Training initialization complete (orchestrated mode)")
    
    def _load_model(self, model_id: str) -> None:
        """Load model definition
        
        Args:
            model_id: Model ID
        """
        logger.info(f"Loading model definition for {model_id}")
        
        # Require model path from Model Registry (orchestrated mode only)
        if not self.model_path or not self.model_path.exists():
            raise ValueError(
                f"Model path not provided or does not exist. "
                f"Models must be downloaded from Model Registry. "
                f"Expected path: {self.model_path}"
            )
        
        logger.info(f"Using model from Model Registry: {self.model_path}")
        model_source = str(self.model_path)
        
        # Load model
        model_loader = ModelLoader(models_dir=self.config.storage.models_dir)
        create_model, create_dataloader, metadata = model_loader.load_model(
            model_source=model_source,
            model_id=model_id
        )
        
        # Create model instance
        self.model = create_model(device=self.device)
        self.model = self.model.to(self.device)  # Ensure model is on correct device
        self.create_dataloader_fn = create_dataloader
        
        # Initialize criterion (cross-entropy for classification)
        self.criterion = nn.CrossEntropyLoss()
        
        logger.info(f"Model loaded: {metadata['name']} v{metadata['version']}")
    
    def _create_dataloader_from_shards(
        self,
        shard_paths: List[Path],
        batch_size: int,
        num_workers: int
    ) -> torch.utils.data.DataLoader:
        """
        Create DataLoader from downloaded shard paths
        
        Args:
            shard_paths: List of paths to extracted shard directories
            batch_size: Batch size for DataLoader
            num_workers: Number of worker processes
            
        Returns:
            DataLoader instance
        """
        from torch.utils.data import DataLoader, ConcatDataset
        from torchvision import datasets, transforms
        
        logger.info(f"Creating DataLoader from {len(shard_paths)} shards")
        
        # Default transform (can be customized per model)
        transform = transforms.Compose([
            transforms.ToTensor(),
            transforms.Normalize((0.5,), (0.5,))
        ])
        
        # Load each shard as a dataset
        shard_datasets = []
        for shard_path in shard_paths:
            try:
                # Assume ImageFolder format for now
                # TODO: Support other formats based on metadata
                dataset = datasets.ImageFolder(
                    root=str(shard_path),
                    transform=transform
                )
                shard_datasets.append(dataset)
                logger.debug(f"Loaded shard from {shard_path}: {len(dataset)} samples")
                
            except Exception as e:
                logger.warning(f"Failed to load shard from {shard_path}: {e}")
                continue
        
        if not shard_datasets:
            raise ValueError("No valid shards could be loaded")
        
        # Combine all shards into one dataset
        combined_dataset = ConcatDataset(shard_datasets)
        
        logger.info(f"Combined dataset: {len(combined_dataset)} total samples")
        
        # Create DataLoader
        dataloader = DataLoader(
            combined_dataset,
            batch_size=batch_size,
            shuffle=True,
            num_workers=num_workers,
            pin_memory=torch.cuda.is_available()
        )
        
        return dataloader

    
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
            # Get current model version
            version = self.grpc_client.get_model_version(model_id)
            self.global_version = version
            logger.info(f"Current Parameter Server version: {version}")
            
            # Get weights (if available)
            state_dict = self.grpc_client.get_weights(model_id, version)
            
            # Load state dict into model if we got weights
            if state_dict and self.model is not None:
                try:
                    self.model.load_state_dict(state_dict)
                    logger.info(f"Loaded weights from Parameter Server: version={version}")
                except Exception as e:
                    logger.warning(f"Failed to load state dict: {e}, using current weights")
            
            logger.info(f"Synced with Parameter Server: version={version}")
            
        except Exception as e:
            # It's okay if weights don't exist yet (new model)
            logger.info(f"No weights available from Parameter Server (new model): {e}")
            logger.info("Using randomly initialized weights")
            self.global_version = 0
    
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
            
            # Calculate accuracy (only for classification tasks)
            # Check if target is categorical (1D) or continuous (multi-dimensional)
            if len(target.shape) == 1 or (len(target.shape) == 2 and target.shape[1] == 1):
                # Classification task
                _, predicted = torch.max(predictions, 1)
                total += target.size(0)
                if len(target.shape) == 2:
                    target = target.squeeze(1)
                correct += (predicted == target).sum().item()
            else:
                # Regression task - skip accuracy calculation
                total += target.size(0)
            
            # End batch benchmark
            if self.performance_benchmark:
                self.performance_benchmark.end_batch(batch_size=data.size(0))
            
            # Update progress bar
            current_loss = epoch_loss / num_batches
            if correct > 0 and total > 0:
                current_acc = 100.0 * correct / total
                pbar.set_postfix({
                    "loss": f"{current_loss:.4f}",
                    "acc": f"{current_acc:.2f}%"
                })
            else:
                pbar.set_postfix({
                    "loss": f"{current_loss:.4f}"
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
                    gradients[name] = param.grad.cpu()  # Keep as tensor for HTTP serialization
                    gradient_norm += param.grad.norm().item() ** 2
            
            gradient_norm = gradient_norm ** 0.5
            
            # Prepare metadata
            metadata = {
                "gradient_norm": gradient_norm,
                "computation_time_ms": 0
            }
            
            # Push to Parameter Server via HTTP
            response = self.grpc_client.push_gradients(
                worker_id=self.config.worker.id or "unknown",
                model_id=self.model_id or "unknown",
                version_id=self.global_version,
                gradients=gradients,
                num_samples=self.config.training.batch_size,
                loss=loss,
                metrics=metadata
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
