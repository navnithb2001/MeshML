"""
Complete End-to-End Integration Example

This example demonstrates how a worker uses all three integrated services:
1. Task Orchestrator - for registration, task assignment, heartbeat
2. Dataset Sharder - for downloading training data shards
3. Model Registry - for fetching model metadata and files
4. Parameter Server - for gradient sync (already working)
"""

import asyncio
import logging
from pathlib import Path

from meshml_worker.config import WorkerConfig, WorkerIdentityConfig
from meshml_worker.communication import (
    DatasetSharderClient,
    TaskOrchestratorClient,
    ModelRegistryClient
)
from meshml_worker.training.trainer import DistributedTrainer

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


async def main():
    """
    Complete distributed training workflow with all services
    """
    
    # ======================================================================
    # STEP 1: Initialize Configuration
    # ======================================================================
    
    logger.info("🔧 Initializing worker configuration...")
    
    config = WorkerConfig(
        worker=WorkerIdentityConfig(
            name="Production Worker 1",
            tags={"environment": "production", "region": "us-central1"}
        ),
        parameter_server={"url": "http://34.61.230.151:8003"},
        dataset_sharder={"url": "http://dataset-sharder-service:8001"},
        task_orchestrator={
            "grpc_url": "task-orchestrator-service:50051",
            "user_id": "user-123"  # Replace with actual user ID
        },
        model_registry={"url": "http://model-registry-service:8004"},
    )
    
    # Create storage directories
    config.storage.create_directories()
    
    logger.info("✅ Configuration initialized")
    
    # ======================================================================
    # STEP 2: Register with Task Orchestrator
    # ======================================================================
    
    logger.info("🤝 Registering with Task Orchestrator...")
    
    orchestrator_client = TaskOrchestratorClient(
        grpc_url=config.task_orchestrator.grpc_url,
        user_id=config.task_orchestrator.user_id,
        worker_name=config.worker.name,
        max_retries=config.task_orchestrator.max_retries,
        retry_delay=config.task_orchestrator.retry_delay
    )
    
    try:
        # Connect and register
        await orchestrator_client.connect()
        registration = await orchestrator_client.register()
        
        worker_id = registration["worker_id"]
        groups = registration["groups"]
        heartbeat_interval = registration["heartbeat_interval"]
        
        logger.info(f"✅ Worker registered successfully!")
        logger.info(f"   Worker ID: {worker_id}")
        logger.info(f"   Groups: {groups}")
        logger.info(f"   Heartbeat interval: {heartbeat_interval}s")
        
        # Note: Heartbeat loop started automatically by register()
        
    except Exception as e:
        logger.error(f"❌ Failed to register with orchestrator: {e}")
        return
    
    # ======================================================================
    # STEP 3: Main Training Loop
    # ======================================================================
    
    logger.info("🔄 Starting main training loop...")
    
    try:
        while True:
            # ==============================================================
            # STEP 3.1: Request Task Assignment
            # ==============================================================
            
            logger.info("📋 Requesting task assignment...")
            
            try:
                task = await orchestrator_client.request_task()
                
                if not task:
                    logger.info("⏸️  No tasks available, waiting 30 seconds...")
                    await asyncio.sleep(30)
                    continue
                
                job_id = task["job_id"]
                batch_id = task["batch_id"]
                current_epoch = task["current_epoch"]
                hyperparameters = task["hyperparameters"]
                
                logger.info(f"✅ Task assigned:")
                logger.info(f"   Job ID: {job_id}")
                logger.info(f"   Batch ID: {batch_id}")
                logger.info(f"   Epoch: {current_epoch}")
                logger.info(f"   Hyperparameters: {hyperparameters}")
                
            except Exception as e:
                logger.error(f"❌ Failed to request task: {e}")
                await asyncio.sleep(10)
                continue
            
            # ==============================================================
            # STEP 3.2: Download Model from Model Registry
            # ==============================================================
            
            logger.info("📦 Downloading model from Model Registry...")
            
            try:
                async with ModelRegistryClient(
                    registry_url=config.model_registry.url,
                    timeout=config.model_registry.timeout,
                    max_retries=config.model_registry.max_retries,
                    retry_delay=config.model_registry.retry_delay
                ) as model_client:
                    
                    # Get model metadata
                    model_id = hyperparameters.get("model_id", 1)
                    model_data = await model_client.get_model(model_id)
                    
                    logger.info(f"   Model: {model_data['name']} v{model_data['version']}")
                    logger.info(f"   Architecture: {model_data['architecture_type']}")
                    
                    # Download model file
                    model_path = await model_client.download_model(
                        model_id=model_id,
                        local_path=config.storage.models_dir / f"model_{job_id}.py"
                    )
                    
                    logger.info(f"✅ Model downloaded to {model_path}")
                    
            except Exception as e:
                logger.error(f"❌ Failed to download model: {e}")
                
                # Report failure to orchestrator
                await orchestrator_client.report_batch_failed(
                    job_id=job_id,
                    batch_id=batch_id,
                    epoch=current_epoch,
                    error_message=f"Model download failed: {e}"
                )
                continue
            
            # ==============================================================
            # STEP 3.3: Download Data Shards from Dataset Sharder
            # ==============================================================
            
            logger.info("💾 Downloading data shards from Dataset Sharder...")
            
            try:
                async with DatasetSharderClient(
                    sharder_url=config.dataset_sharder.url,
                    timeout=config.dataset_sharder.timeout,
                    max_retries=config.dataset_sharder.max_retries,
                    retry_delay=config.dataset_sharder.retry_delay
                ) as sharder_client:
                    
                    # Get worker's batch assignment
                    assignment = await sharder_client.get_worker_assignment(
                        worker_id=worker_id,
                        job_id=job_id
                    )
                    
                    logger.info(f"   Assigned {len(assignment['assigned_batches'])} batches")
                    logger.info(f"   Shard ID: {assignment['shard_id']}")
                    logger.info(f"   Total samples: {assignment['total_samples']}")
                    logger.info(f"   Progress: {assignment['progress']:.1%}")
                    
                    # Download all assigned batches
                    batch_paths = await sharder_client.download_all_assigned_batches(
                        worker_id=worker_id,
                        local_base_path=config.storage.data_dir / f"job_{job_id}",
                        job_id=job_id
                    )
                    
                    logger.info(f"✅ Downloaded {len(batch_paths)} data batches")
                    
            except Exception as e:
                logger.error(f"❌ Failed to download data shards: {e}")
                
                # Report failure to orchestrator
                await orchestrator_client.report_batch_failed(
                    job_id=job_id,
                    batch_id=batch_id,
                    epoch=current_epoch,
                    error_message=f"Data download failed: {e}"
                )
                continue
            
            # ==============================================================
            # STEP 3.4: Execute Training
            # ==============================================================
            
            logger.info("🏋️ Starting training...")
            
            try:
                # Initialize trainer
                trainer = DistributedTrainer(
                    config=config,
                    job_id=job_id,
                    worker_id=worker_id
                )
                
                # Train for the assigned epoch
                start_time = asyncio.get_event_loop().time()
                
                metrics = await trainer.train_epoch(
                    epoch=current_epoch,
                    model_path=model_path,
                    data_paths=batch_paths
                )
                
                processing_time_ms = int(
                    (asyncio.get_event_loop().time() - start_time) * 1000
                )
                
                loss = metrics.get("loss", 0.0)
                accuracy = metrics.get("accuracy", 0.0)
                
                logger.info(f"✅ Training completed:")
                logger.info(f"   Loss: {loss:.4f}")
                logger.info(f"   Accuracy: {accuracy:.4f}")
                logger.info(f"   Time: {processing_time_ms}ms")
                
                # ==============================================================
                # STEP 3.5: Report Completion to Task Orchestrator
                # ==============================================================
                
                logger.info("📊 Reporting batch completion...")
                
                success = await orchestrator_client.report_batch_complete(
                    job_id=job_id,
                    batch_id=batch_id,
                    epoch=current_epoch,
                    loss=loss,
                    accuracy=accuracy,
                    processing_time_ms=processing_time_ms,
                    metrics=metrics
                )
                
                if success:
                    logger.info("✅ Batch completion reported successfully")
                else:
                    logger.warning("⚠️ Batch completion report not acknowledged")
                
            except Exception as e:
                logger.error(f"❌ Training failed: {e}")
                
                # Report failure to orchestrator
                await orchestrator_client.report_batch_failed(
                    job_id=job_id,
                    batch_id=batch_id,
                    epoch=current_epoch,
                    error_message=f"Training failed: {e}"
                )
                continue
            
            # ==============================================================
            # STEP 3.6: Cleanup
            # ==============================================================
            
            logger.info("🧹 Cleaning up temporary files...")
            
            try:
                # Remove downloaded data to save space
                import shutil
                data_dir = config.storage.data_dir / f"job_{job_id}"
                if data_dir.exists():
                    shutil.rmtree(data_dir)
                    logger.info(f"   Removed {data_dir}")
                
                # Keep model file for potential reuse
                logger.info(f"   Kept model file: {model_path}")
                
            except Exception as e:
                logger.warning(f"⚠️ Cleanup warning: {e}")
            
            logger.info("✅ Task completed, requesting next task...\n")
    
    except KeyboardInterrupt:
        logger.info("\n🛑 Shutting down worker...")
    
    except Exception as e:
        logger.error(f"❌ Fatal error: {e}")
    
    finally:
        # ======================================================================
        # STEP 4: Cleanup and Shutdown
        # ======================================================================
        
        logger.info("🧹 Performing final cleanup...")
        
        try:
            # Close Task Orchestrator connection (stops heartbeat)
            await orchestrator_client.close()
            logger.info("✅ Disconnected from Task Orchestrator")
            
        except Exception as e:
            logger.warning(f"⚠️ Cleanup warning: {e}")
        
        logger.info("👋 Worker shutdown complete")


if __name__ == "__main__":
    """
    Run the complete integration example
    
    Environment variables needed:
    - TASK_ORCHESTRATOR_GRPC_URL (default: task-orchestrator-service:50051)
    - USER_ID (required)
    - DATASET_SHARDER_URL (default: http://dataset-sharder-service:8001)
    - MODEL_REGISTRY_URL (default: http://model-registry-service:8004)
    - PARAMETER_SERVER_URL (default: http://34.61.230.151:8003)
    """
    
    import os
    
    # Override defaults from environment
    os.environ.setdefault("TASK_ORCHESTRATOR_GRPC_URL", "task-orchestrator-service:50051")
    os.environ.setdefault("DATASET_SHARDER_URL", "http://dataset-sharder-service:8001")
    os.environ.setdefault("MODEL_REGISTRY_URL", "http://model-registry-service:8004")
    os.environ.setdefault("PARAMETER_SERVER_URL", "http://34.61.230.151:8003")
    
    # User ID must be provided
    if not os.getenv("USER_ID"):
        print("ERROR: USER_ID environment variable is required")
        print("Example: export USER_ID=user-123")
        exit(1)
    
    # Run the main loop
    asyncio.run(main())
