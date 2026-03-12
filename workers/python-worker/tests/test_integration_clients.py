"""
Quick Integration Test Script

Tests all three new clients against deployed GCP services:
1. Dataset Sharder Client
2. Task Orchestrator Client  
3. Model Registry Client
"""

import asyncio
import logging

from meshml_worker.communication import (
    DatasetSharderClient,
    TaskOrchestratorClient,
    ModelRegistryClient
)

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


async def test_dataset_sharder():
    """Test Dataset Sharder client"""
    logger.info("\n" + "="*60)
    logger.info("TESTING DATASET SHARDER CLIENT")
    logger.info("="*60)
    
    try:
        async with DatasetSharderClient(
            sharder_url="http://34.118.236.23:8001"
        ) as client:
            
            # Test health check
            logger.info("1. Testing health check...")
            healthy = await client.health_check()
            logger.info(f"   Health status: {'✅ Healthy' if healthy else '❌ Unhealthy'}")
            
            # Test get stats
            logger.info("2. Getting distribution stats...")
            stats = await client.get_distribution_stats()
            logger.info(f"   Stats: {stats}")
            
            logger.info("✅ Dataset Sharder client test PASSED")
            
    except Exception as e:
        logger.error(f"❌ Dataset Sharder client test FAILED: {e}")


async def test_task_orchestrator():
    """Test Task Orchestrator client"""
    logger.info("\n" + "="*60)
    logger.info("TESTING TASK ORCHESTRATOR CLIENT")
    logger.info("="*60)
    
    try:
        client = TaskOrchestratorClient(
            grpc_url="task-orchestrator-service:50051",
            user_id="test-user-123",
            worker_name="Test Worker"
        )
        
        # Test connection
        logger.info("1. Testing gRPC connection...")
        await client.connect()
        logger.info("   ✅ Connected")
        
        # Test registration
        logger.info("2. Testing worker registration...")
        registration = await client.register()
        logger.info(f"   Worker ID: {registration['worker_id']}")
        logger.info(f"   Groups: {registration['groups']}")
        logger.info(f"   ✅ Registered")
        
        # Test single heartbeat
        logger.info("3. Testing heartbeat...")
        success = await client.send_heartbeat(status="idle")
        logger.info(f"   Heartbeat: {'✅ Acknowledged' if success else '❌ Failed'}")
        
        # Test task request
        logger.info("4. Testing task request...")
        task = await client.request_task()
        if task:
            logger.info(f"   Task assigned: {task['job_id']}")
        else:
            logger.info("   No tasks available (expected)")
        
        # Cleanup
        await client.close()
        logger.info("✅ Task Orchestrator client test PASSED")
        
    except Exception as e:
        logger.error(f"❌ Task Orchestrator client test FAILED: {e}")


async def test_model_registry():
    """Test Model Registry client"""
    logger.info("\n" + "="*60)
    logger.info("TESTING MODEL REGISTRY CLIENT")
    logger.info("="*60)
    
    try:
        async with ModelRegistryClient(
            registry_url="http://34.118.234.37:8004"
        ) as client:
            
            # Test health check
            logger.info("1. Testing health check...")
            healthy = await client.health_check()
            logger.info(f"   Health status: {'✅ Healthy' if healthy else '❌ Unhealthy'}")
            
            # Test search models
            logger.info("2. Searching for models...")
            results = await client.search_models(limit=5)
            logger.info(f"   Found {results.get('total', 0)} models")
            
            # Test get architecture types
            logger.info("3. Getting architecture types...")
            arch_types = await client.get_architecture_types()
            logger.info(f"   Architecture types: {arch_types}")
            
            # Test get recent models
            logger.info("4. Getting recent models...")
            recent = await client.get_recent_models(limit=3)
            logger.info(f"   Recent models: {len(recent)}")
            
            logger.info("✅ Model Registry client test PASSED")
            
    except Exception as e:
        logger.error(f"❌ Model Registry client test FAILED: {e}")


async def main():
    """Run all integration tests"""
    logger.info("\n" + "="*60)
    logger.info("MESHML INTEGRATION TESTS")
    logger.info("="*60)
    logger.info("Testing all three new service clients...")
    logger.info("")
    
    # Test each client
    await test_dataset_sharder()
    await test_model_registry()
    
    # Note: Task Orchestrator requires internal cluster access
    logger.info("\n⚠️  Task Orchestrator test requires cluster access")
    logger.info("   Run this from inside a pod: kubectl run test-pod --image=python:3.11 -it")
    
    logger.info("\n" + "="*60)
    logger.info("TESTS COMPLETE")
    logger.info("="*60)


if __name__ == "__main__":
    asyncio.run(main())
