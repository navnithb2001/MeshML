"""
Main MeshML Worker Implementation

Coordinates training, communication, and checkpoint management.
"""

import logging
import asyncio
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
    
    async def run(
        self,
        user_id: str,
        preferred_job_ids: Optional[list] = None
    ) -> None:
        """Run worker with full Task Orchestrator integration
        
        This is the production-ready entry point that:
        1. Registers with Task Orchestrator
        2. Requests task assignments
        3. Downloads model from Model Registry
        4. Downloads data from Dataset Sharder
        5. Trains and reports progress
        
        Args:
            user_id: User ID for authentication
            preferred_job_ids: Optional list of preferred job IDs
        """
        from meshml_worker.communication import (
            TaskOrchestratorClient,
            ModelRegistryClient,
            DatasetSharderClient
        )
        from meshml_worker.training.trainer import Trainer
        from meshml_worker.communication.http_client import HTTPClient
        from meshml_worker.utils.device import get_device
        
        self.running = True
        logger.info("=" * 60)
        logger.info("Starting MeshML Worker with Task Orchestrator Integration")
        logger.info("=" * 60)
        logger.info(f"Worker ID: {self.worker_id}")
        logger.info(f"User ID: {user_id}")
        
        try:
            # Initialize Task Orchestrator client
            orchestrator = TaskOrchestratorClient(
                grpc_url=self.config.task_orchestrator.grpc_url,
                user_id=user_id,
                worker_id=self.worker_id,
                max_retries=self.config.task_orchestrator.max_retries,
                retry_delay=self.config.task_orchestrator.retry_delay
            )
            
            # Step 1: Register with Task Orchestrator
            logger.info("\n[1/5] Registering with Task Orchestrator...")
            registration_result = await orchestrator.register()
            logger.info(f"✓ Registration successful!")
            logger.info(f"  Capabilities: CPU={registration_result.get('cpu_cores', 0)} cores, "
                       f"RAM={registration_result.get('ram_gb', 0):.1f} GB, "
                       f"GPU={registration_result.get('has_gpu', False)}")
            
            # Step 2: Request task assignment
            logger.info("\n[2/5] Requesting task assignment...")
            task = await orchestrator.request_task(preferred_job_ids=preferred_job_ids or [])
            
            if not task:
                logger.warning("No tasks available at this time")
                return
            
            job_id = task.get("job_id")
            model_id = task.get("model_id")
            batch_assignments = task.get("batch_ids", [])
            
            logger.info(f"✓ Task assigned!")
            logger.info(f"  Job ID: {job_id}")
            logger.info(f"  Model ID: {model_id}")
            logger.info(f"  Assigned batches: {len(batch_assignments)}")
            
            # Step 3: Download model from Model Registry
            logger.info(f"\n[3/5] Downloading model from Model Registry...")
            async with ModelRegistryClient(
                registry_url=self.config.model_registry.url,
                timeout=self.config.model_registry.timeout
            ) as model_client:
                
                # Get model metadata
                model_info = await model_client.get_model(model_id)
                logger.info(f"  Model: {model_info.get('name', 'Unknown')}")
                logger.info(f"  Architecture: {model_info.get('architecture_type', 'Unknown')}")
                
                # Download model file
                model_path = self.config.storage.models_dir / f"{model_id}.py"
                downloaded_path = await model_client.download_model(
                    model_id=model_id,
                    local_path=model_path
                )
                logger.info(f"✓ Model downloaded to: {downloaded_path}")
            
            # Step 4: Download data from Dataset Sharder
            logger.info(f"\n[4/5] Downloading data from Dataset Sharder...")
            async with DatasetSharderClient(
                sharder_url=self.config.dataset_sharder.url,
                timeout=self.config.dataset_sharder.timeout
            ) as sharder_client:
                
                batch_paths = await sharder_client.download_all_assigned_batches(
                    worker_id=self.worker_id,
                    local_base_path=self.config.storage.data_dir,
                    job_id=job_id
                )
                logger.info(f"✓ Downloaded {len(batch_paths)} data batches")
            
            # Step 5: Train the model
            logger.info(f"\n[5/5] Starting training...")
            
            # Detect device
            device = get_device(self.config.training.device)
            logger.info(f"  Device: {device}")
            
            # Initialize Parameter Server client
            http_client = HTTPClient(self.config.parameter_server.url)
            if not http_client.connect():
                raise RuntimeError("Failed to connect to Parameter Server")
            logger.info("  Connected to Parameter Server")
            
            # Initialize trainer with orchestrator
            trainer = Trainer(
                config=self.config,
                grpc_client=http_client,
                device=device,
                orchestrator_client=orchestrator,  # Pass orchestrator for reporting
                job_id=job_id,
                model_path=model_path,
                data_paths=batch_paths
            )
            
            # Start training loop
            await trainer.train_with_orchestrator(
                model_id=model_id,
                job_id=job_id,
                batch_ids=batch_assignments
            )
            
            logger.info("\n" + "=" * 60)
            logger.info("Training completed successfully!")
            logger.info("=" * 60)
            
        except KeyboardInterrupt:
            logger.info("\n\nTraining interrupted by user")
            raise
        except Exception as e:
            logger.error(f"\n\nTraining failed: {e}", exc_info=True)
            raise
        finally:
            self.running = False
            # Cleanup
            if 'orchestrator' in locals():
                await orchestrator.close()
    
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


if __name__ == "__main__":
    """Entry point for running worker directly."""
    import asyncio
    import sys
    import os
    from meshml_worker.config import WorkerConfig, WorkerIdentityConfig, ParameterServerConfig
    
    # Create configuration from environment variables
    config = WorkerConfig(
        worker=WorkerIdentityConfig(
            id=os.getenv("WORKER_ID", "python-worker-1"),
            name=os.getenv("WORKER_NAME", "MeshML Python Worker"),
        ),
        parameter_server=ParameterServerConfig(
            url=os.getenv("PARAMETER_SERVER_URL", "http://parameter-server:8003"),
            grpc_url=os.getenv("ORCHESTRATOR_URL", "task-orchestrator:50051"),
        ),
    )
    
    # Create worker
    worker = MeshMLWorker(config)
    logger.info(f"Worker initialized: {config.worker.id}")
    
    # Validate setup
    validation = worker.validate_setup()
    logger.info(f"Setup validation: {validation}")
    
    # Keep worker running
    try:
        logger.info(f"Worker {config.worker.id} is ready and waiting for tasks...")
        # Keep the process alive indefinitely
        while True:
            asyncio.run(asyncio.sleep(3600))  # Sleep for 1 hour at a time
    except KeyboardInterrupt:
        logger.info("Worker stopped by user")
        sys.exit(0)
    except Exception as e:
        logger.error(f"Worker failed: {e}", exc_info=True)
        sys.exit(1)
