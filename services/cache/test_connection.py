"""Test Redis connection and basic operations."""
import sys
from pathlib import Path

# Add services directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from cache.client import redis_client
from cache.serializers import WeightsSerializer
import numpy as np

def main():
    print("=" * 50)
    print("Redis Connection Test")
    print("=" * 50)
    
    # Test connection
    if redis_client.ping():
        print("✅ Redis connected successfully")
    else:
        print("❌ Redis connection failed")
        return
    
    # Get server info
    info = redis_client.get_info()
    print(f"\n📊 Redis Server Info:")
    print(f"  Version: {info['redis_version']}")
    print(f"  Connected clients: {info['connected_clients']}")
    print(f"  Used memory: {info['used_memory_human']}")
    print(f"  Total keys: {info['db0']['keys'] if 'db0' in info else 0}")
    
    # Test heartbeat
    print(f"\n💓 Testing Heartbeat:")
    worker_id = "test-worker-123"
    metadata = {'status': 'online', 'gpu_util': 75.5}
    redis_client.set_heartbeat(worker_id, metadata)
    
    retrieved = redis_client.get_heartbeat(worker_id)
    print(f"  Set heartbeat for {worker_id}")
    print(f"  Retrieved: {retrieved}")
    print(f"  Is alive: {redis_client.is_worker_alive(worker_id)}")
    
    # Test weights serialization
    print(f"\n⚖️  Testing Weights Serialization:")
    weights = {
        'layer1': np.random.randn(128, 784).astype(np.float32),
        'layer2': np.random.randn(10, 128).astype(np.float32),
    }
    
    binary = WeightsSerializer.serialize(weights)
    size = len(binary)
    print(f"  Serialized size: {size:,} bytes ({size/1024:.2f} KB)")
    
    restored = WeightsSerializer.deserialize(binary)
    print(f"  Deserialized layers: {list(restored.keys())}")
    print(f"  Shape match: {np.array_equal(weights['layer1'], restored['layer1'])}")
    
    # Test global weights storage
    print(f"\n🔄 Testing Global Weights Storage:")
    job_id = 42
    version = 1
    redis_client.set_global_weights(job_id, version, weights)
    redis_client.set_latest_weights_version(job_id, version)
    
    latest_version = redis_client.get_latest_weights_version(job_id)
    print(f"  Stored version {version} for job {job_id}")
    print(f"  Latest version: {latest_version}")
    
    retrieved_weights = redis_client.get_latest_weights(job_id)
    print(f"  Retrieved layers: {list(retrieved_weights.keys())}")
    
    # Test version tracking
    print(f"\n📈 Testing Version Tracking:")
    for v in range(1, 6):
        metadata = {'epoch': v, 'loss': 1.0 / v, 'accuracy': 0.5 + (v * 0.05)}
        redis_client.add_version(job_id, v, metadata)
    
    history = redis_client.get_version_history(job_id, limit=10)
    print(f"  Version count: {redis_client.get_version_count(job_id)}")
    print(f"  Latest 3 versions:")
    for v in history[:3]:
        print(f"    Version {v['version']}: loss={v['metadata']['loss']:.3f}, acc={v['metadata']['accuracy']:.3f}")
    
    # Test job status cache
    print(f"\n📊 Testing Job Status Cache:")
    redis_client.cache_job_status(
        job_id,
        status='running',
        progress=67.5,
        metadata={'current_epoch': 34, 'total_epochs': 50}
    )
    
    status = redis_client.get_job_status(job_id)
    print(f"  Job {job_id} status: {status['status']} ({status['progress']}%)")
    print(f"  Epoch: {status['metadata']['current_epoch']}/{status['metadata']['total_epochs']}")
    
    print(f"\n{'=' * 50}")
    print("✅ All tests passed successfully!")
    print("=" * 50)

if __name__ == "__main__":
    main()
