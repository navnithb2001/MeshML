"""
Main MeshML Worker Implementation

Coordinates training, communication, and checkpoint management.
"""

import logging
import asyncio
from pathlib import Path
from typing import Optional, Dict, Any, Tuple, Callable
import signal
import sys
import json
import hashlib
import psutil

from meshml_worker.config import WorkerConfig


logger = logging.getLogger(__name__)


class BlobCache:
    """Simple file hash cache used to avoid unnecessary re-downloads."""

    def __init__(self, cache_path: Path):
        self.cache_path = cache_path

    async def _read_cache(self) -> Dict[str, Any]:
        if not self.cache_path.exists():
            return {}
        try:
            return json.loads(self.cache_path.read_text())
        except Exception:
            return {}

    async def _write_cache(self, cache: Dict[str, Any]) -> None:
        self.cache_path.parent.mkdir(parents=True, exist_ok=True)
        self.cache_path.write_text(json.dumps(cache, indent=2))

    async def hash_file(self, path: Path) -> str:
        def _compute() -> str:
            sha = hashlib.sha256()
            with open(path, "rb") as file_obj:
                for chunk in iter(lambda: file_obj.read(8192), b""):
                    sha.update(chunk)
            return sha.hexdigest()

        return await asyncio.to_thread(_compute)

    async def should_use_cached(
        self,
        cache_key: str,
        file_path: Path,
        expected_sha256: Optional[str]
    ) -> bool:
        if not expected_sha256 or not file_path.exists():
            return False

        cache = await self._read_cache()
        cache_entry = cache.get(cache_key, {})
        if cache_entry.get("sha256") != expected_sha256:
            return False

        return (await self.hash_file(file_path)) == expected_sha256

    async def record_download(
        self,
        cache_key: str,
        source_url: str,
        file_path: Path
    ) -> str:
        file_hash = await self.hash_file(file_path)
        cache = await self._read_cache()
        cache[cache_key] = {"url": source_url, "sha256": file_hash}
        await self._write_cache(cache)
        return file_hash


class ResourceMonitor:
    """Monitors local host resources and toggles pause event for training."""

    def __init__(
        self,
        pause_event: asyncio.Event,
        cpu_threshold: float = 80.0,
        memory_threshold: float = 80.0,
    ):
        self.pause_event = pause_event
        self.cpu_threshold = cpu_threshold
        self.memory_threshold = memory_threshold

    async def check_once(self) -> Tuple[float, float]:
        cpu_usage = psutil.cpu_percent(interval=0.1)
        memory_usage = psutil.virtual_memory().percent
        if cpu_usage > self.cpu_threshold or memory_usage > self.memory_threshold:
            if not self.pause_event.is_set():
                logger.warning("High system usage detected; pausing training")
            self.pause_event.set()
        else:
            if self.pause_event.is_set():
                logger.info("Resources available; resuming training")
            self.pause_event.clear()
        return cpu_usage, memory_usage

    async def run(self, is_running: Callable[[], bool]) -> None:
        while is_running():
            await self.check_once()
            await asyncio.sleep(10)


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
        self._shutdown_event: Optional[asyncio.Event] = None
        self._pause_event: Optional[asyncio.Event] = None
        self._loop: Optional[asyncio.AbstractEventLoop] = None
        
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
            if self._loop and self._shutdown_event:
                self._loop.call_soon_threadsafe(self._shutdown_event.set)
        
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
            DatasetSharderClient,
            MetricsClient
        )
        from meshml_worker.training.trainer import Trainer
        from meshml_worker.communication.http_client import HTTPClient
        from meshml_worker.utils.device import get_device
        
        self.running = True
        self._loop = asyncio.get_running_loop()
        self._shutdown_event = asyncio.Event()
        self._pause_event = asyncio.Event()
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
            
            cache = BlobCache(self.config.storage.models_dir / ".model_cache.json")

            async def _download(url: str, dest_path: Path, cache_key: str, expected_sha: Optional[str]) -> None:
                import httpx
                if await cache.should_use_cached(cache_key, dest_path, expected_sha):
                    logger.info(f"Using cached model: {dest_path}")
                    return

                async with httpx.AsyncClient(timeout=60) as http_client:
                    resp = await http_client.get(url)
                    resp.raise_for_status()
                    dest_path.parent.mkdir(parents=True, exist_ok=True)
                    dest_path.write_bytes(resp.content)
                await cache.record_download(cache_key, url, dest_path)

            monitor = ResourceMonitor(self._pause_event)
            monitor_task = asyncio.create_task(monitor.run(lambda: bool(self.running and self._pause_event)))
            job_progress: Dict[str, Dict[str, int]] = {}

            async def _handle_assignment(assignment, hyperparameters):
                try:
                    job_id = assignment.job_id
                    model_id = hyperparameters.get("model_id") or "unknown"
                    model_sha = hyperparameters.get("model_sha256")
                    total_batches = int(hyperparameters.get("total_batches") or 0)

                    model_path = self.config.storage.models_dir / f"{model_id}.py"
                    if assignment.model_url:
                        await _download(assignment.model_url, model_path, f"model:{model_id}", model_sha)

                    data_dir = self.config.storage.data_dir / f"{assignment.batch_id}"
                    data_dir.mkdir(parents=True, exist_ok=True)
                    data_path = data_dir / "batch.data"
                    if assignment.data_url:
                        await _download(assignment.data_url, data_path, f"batch:{assignment.batch_id}", None)

                    # Detect device
                    device = get_device(self.config.training.device)

                    # Initialize Parameter Server client
                    http_client = HTTPClient(self.config.parameter_server.url)
                    if not http_client.connect():
                        raise RuntimeError("Failed to connect to Parameter Server")

                    trainer = Trainer(
                        config=self.config,
                        grpc_client=http_client,
                        device=device,
                        orchestrator_client=orchestrator,
                        metrics_client=MetricsClient(self.config.metrics_service.grpc_url),
                        job_id=job_id,
                        model_path=model_path,
                        data_paths=[data_dir],
                        pause_event=self._pause_event
                    )

                    await trainer.train(
                        model_id=str(model_id),
                        job_id=job_id,
                        batch_ids=[assignment.batch_id],
                        epochs=1
                    )

                    if total_batches > 0:
                        progress = job_progress.setdefault(
                            job_id,
                            {"completed": 0, "total": total_batches}
                        )
                        progress["completed"] += 1
                        if progress["completed"] >= progress["total"]:
                            logger.info(f"Job {job_id} completed all batches; closing stream")
                            if self._shutdown_event:
                                self._shutdown_event.set()

                    return {"success": True}
                except Exception as e:
                    return {"success": False, "error_message": str(e)}

            logger.info("\n[2/5] Waiting for streamed assignments...")
            await orchestrator.run_assignment_stream(_handle_assignment, self._shutdown_event)
            monitor_task.cancel()
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
