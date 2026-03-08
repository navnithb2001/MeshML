"""Tests for worker health monitoring and registry."""

import pytest
import asyncio
import time
from datetime import datetime, timedelta

from app.services.worker_registry import (
    WorkerRegistry,
    WorkerInfo,
    WorkerStatus,
    WorkerCapabilities,
    WorkerMetrics
)


@pytest.fixture
def registry():
    """Create WorkerRegistry instance."""
    return WorkerRegistry(
        heartbeat_timeout_seconds=5,  # Short timeout for testing
        heartbeat_check_interval=1,
        auto_cleanup=True
    )


@pytest.fixture
def sample_capabilities():
    """Create sample worker capabilities."""
    return WorkerCapabilities(
        gpu_count=2,
        gpu_memory_gb=16.0,
        gpu_type="NVIDIA RTX 3090",
        cpu_count=8,
        ram_gb=32.0,
        network_speed_mbps=1000.0,
        storage_gb=500.0,
        supports_cuda=True,
        supports_mps=False,
        pytorch_version="2.0.0",
        python_version="3.10.0"
    )


@pytest.fixture
def sample_metrics():
    """Create sample worker metrics."""
    return WorkerMetrics(
        cpu_usage_percent=45.0,
        memory_usage_percent=60.0,
        gpu_usage_percent=80.0,
        gpu_memory_usage_percent=70.0,
        network_rx_mbps=100.0,
        network_tx_mbps=50.0,
        disk_usage_percent=30.0,
        active_tasks=2,
        completed_tasks=10,
        failed_tasks=1
    )


class TestWorkerCapabilities:
    """Test WorkerCapabilities dataclass."""
    
    def test_creation(self):
        """Test creating capabilities."""
        caps = WorkerCapabilities(
            gpu_count=4,
            gpu_memory_gb=24.0,
            cpu_count=16,
            ram_gb=64.0
        )
        
        assert caps.gpu_count == 4
        assert caps.gpu_memory_gb == 24.0
        assert caps.cpu_count == 16
        assert caps.ram_gb == 64.0
    
    def test_compute_score(self):
        """Test compute score calculation."""
        # High-end GPU worker
        gpu_worker = WorkerCapabilities(
            gpu_count=4,
            gpu_memory_gb=24.0,
            cpu_count=16,
            ram_gb=64.0
        )
        
        # CPU-only worker
        cpu_worker = WorkerCapabilities(
            gpu_count=0,
            gpu_memory_gb=0.0,
            cpu_count=32,
            ram_gb=128.0
        )
        
        gpu_score = gpu_worker.get_compute_score()
        cpu_score = cpu_worker.get_compute_score()
        
        # GPU worker should have much higher score
        assert gpu_score > cpu_score
        assert gpu_score > 900  # 4 * 24 * 10 = 960
    
    def test_serialization(self, sample_capabilities):
        """Test to_dict and from_dict."""
        data = sample_capabilities.to_dict()
        
        assert data["gpu_count"] == 2
        assert data["supports_cuda"] is True
        
        restored = WorkerCapabilities.from_dict(data)
        assert restored.gpu_count == 2
        assert restored.supports_cuda is True


class TestWorkerMetrics:
    """Test WorkerMetrics dataclass."""
    
    def test_is_healthy(self):
        """Test health check."""
        healthy = WorkerMetrics(
            cpu_usage_percent=50.0,
            memory_usage_percent=60.0,
            gpu_memory_usage_percent=70.0
        )
        
        assert healthy.is_healthy() is True
        
        unhealthy = WorkerMetrics(
            cpu_usage_percent=96.0,
            memory_usage_percent=60.0
        )
        
        assert unhealthy.is_healthy() is False
    
    def test_is_overloaded(self):
        """Test overload detection."""
        normal = WorkerMetrics(
            cpu_usage_percent=70.0,
            memory_usage_percent=75.0
        )
        
        assert normal.is_overloaded() is False
        
        overloaded = WorkerMetrics(
            cpu_usage_percent=92.0,
            memory_usage_percent=80.0
        )
        
        assert overloaded.is_overloaded() is True
    
    def test_serialization(self, sample_metrics):
        """Test serialization."""
        data = sample_metrics.to_dict()
        
        assert data["cpu_usage_percent"] == 45.0
        assert data["active_tasks"] == 2
        
        restored = WorkerMetrics.from_dict(data)
        assert restored.cpu_usage_percent == 45.0
        assert restored.active_tasks == 2


class TestWorkerInfo:
    """Test WorkerInfo dataclass."""
    
    def test_creation(self, sample_capabilities):
        """Test creating worker info."""
        worker = WorkerInfo(
            worker_id="worker1",
            hostname="worker-node-1",
            ip_address="192.168.1.100",
            port=8080,
            status=WorkerStatus.IDLE,
            capabilities=sample_capabilities
        )
        
        assert worker.worker_id == "worker1"
        assert worker.status == WorkerStatus.IDLE
        assert worker.capabilities.gpu_count == 2
    
    def test_is_alive(self, sample_capabilities):
        """Test alive check based on heartbeat."""
        worker = WorkerInfo(
            worker_id="worker1",
            hostname="worker-node-1",
            ip_address="192.168.1.100",
            port=8080,
            status=WorkerStatus.IDLE,
            capabilities=sample_capabilities
        )
        
        # Just created, should be alive
        assert worker.is_alive(heartbeat_timeout_seconds=5) is True
        
        # Simulate old heartbeat
        old_time = (datetime.utcnow() - timedelta(seconds=10)).isoformat()
        worker.last_heartbeat = old_time
        
        assert worker.is_alive(heartbeat_timeout_seconds=5) is False
    
    def test_uptime_calculation(self, sample_capabilities):
        """Test uptime calculation."""
        worker = WorkerInfo(
            worker_id="worker1",
            hostname="worker-node-1",
            ip_address="192.168.1.100",
            port=8080,
            status=WorkerStatus.IDLE,
            capabilities=sample_capabilities
        )
        
        time.sleep(0.1)
        
        uptime = worker.get_uptime_seconds()
        assert uptime >= 0.1
        assert uptime < 1.0
    
    def test_serialization(self, sample_capabilities):
        """Test worker info serialization."""
        worker = WorkerInfo(
            worker_id="worker1",
            hostname="worker-node-1",
            ip_address="192.168.1.100",
            port=8080,
            status=WorkerStatus.BUSY,
            capabilities=sample_capabilities,
            group_id="group1"
        )
        
        data = worker.to_dict()
        
        assert data["worker_id"] == "worker1"
        assert data["status"] == "busy"
        assert data["group_id"] == "group1"
        
        restored = WorkerInfo.from_dict(data)
        assert restored.worker_id == "worker1"
        assert restored.status == WorkerStatus.BUSY
        assert restored.capabilities.gpu_count == 2


class TestWorkerRegistry:
    """Test WorkerRegistry functionality."""
    
    def test_initialization(self):
        """Test registry initialization."""
        registry = WorkerRegistry(
            heartbeat_timeout_seconds=30,
            heartbeat_check_interval=10
        )
        
        assert registry.heartbeat_timeout == 30
        assert registry.check_interval == 10
        assert len(registry.workers) == 0
    
    def test_register_worker(self, registry, sample_capabilities):
        """Test worker registration."""
        worker = registry.register_worker(
            worker_id="worker1",
            hostname="node1",
            ip_address="192.168.1.100",
            port=8080,
            capabilities=sample_capabilities,
            group_id="group1",
            version="1.0.0"
        )
        
        assert worker.worker_id == "worker1"
        assert worker.status == WorkerStatus.IDLE
        assert worker.group_id == "group1"
        
        # Verify in registry
        assert "worker1" in registry.workers
        assert "worker1" in registry.workers_by_status[WorkerStatus.IDLE]
        assert "worker1" in registry.workers_by_group["group1"]
    
    def test_re_register_worker(self, registry, sample_capabilities):
        """Test re-registering an existing worker."""
        # Initial registration
        registry.register_worker(
            worker_id="worker1",
            hostname="node1",
            ip_address="192.168.1.100",
            port=8080,
            capabilities=sample_capabilities
        )
        
        # Mark offline
        registry.mark_offline("worker1")
        
        # Re-register
        worker = registry.register_worker(
            worker_id="worker1",
            hostname="node1-updated",
            ip_address="192.168.1.101",
            port=8081,
            capabilities=sample_capabilities
        )
        
        assert worker.hostname == "node1-updated"
        assert worker.ip_address == "192.168.1.101"
        assert worker.status == WorkerStatus.IDLE  # Should recover from OFFLINE
    
    def test_update_heartbeat(self, registry, sample_capabilities, sample_metrics):
        """Test heartbeat update."""
        registry.register_worker(
            worker_id="worker1",
            hostname="node1",
            ip_address="192.168.1.100",
            port=8080,
            capabilities=sample_capabilities
        )
        
        time.sleep(0.1)
        
        # Update heartbeat with metrics
        success = registry.update_heartbeat("worker1", metrics=sample_metrics)
        
        assert success is True
        
        worker = registry.get_worker("worker1")
        assert worker.metrics.cpu_usage_percent == 45.0
        assert worker.metrics.active_tasks == 2
    
    def test_heartbeat_unknown_worker(self, registry):
        """Test heartbeat from unknown worker."""
        success = registry.update_heartbeat("unknown_worker")
        
        assert success is False
    
    def test_list_workers(self, registry, sample_capabilities):
        """Test listing workers with filters."""
        # Register multiple workers
        for i in range(5):
            caps = WorkerCapabilities(
                gpu_count=i % 3,  # 0, 1, 2, 0, 1
                cpu_count=4,
                ram_gb=16.0
            )
            
            registry.register_worker(
                worker_id=f"worker{i}",
                hostname=f"node{i}",
                ip_address=f"192.168.1.{100+i}",
                port=8080,
                capabilities=caps,
                group_id=f"group{i % 2}"  # group0 or group1
            )
        
        # List all workers
        all_workers = registry.list_workers()
        assert len(all_workers) == 5
        
        # Filter by status
        idle_workers = registry.list_workers(status=WorkerStatus.IDLE)
        assert len(idle_workers) == 5
        
        # Filter by group
        group0_workers = registry.list_workers(group_id="group0")
        assert len(group0_workers) == 3  # workers 0, 2, 4
        
        # Filter by GPU count
        gpu_workers = registry.list_workers(min_gpu_count=1)
        assert len(gpu_workers) == 3  # workers 1, 2, 4
    
    def test_get_available_workers(self, registry, sample_capabilities):
        """Test getting available workers."""
        # Register workers with different statuses
        for i in range(4):
            registry.register_worker(
                worker_id=f"worker{i}",
                hostname=f"node{i}",
                ip_address=f"192.168.1.{100+i}",
                port=8080,
                capabilities=sample_capabilities
            )
        
        # Mark some workers as busy or offline
        registry.assign_job("worker1", "job1")  # -> BUSY
        registry.mark_offline("worker2")  # -> OFFLINE
        
        # Get available workers (should be worker0 and worker3)
        available = registry.get_available_workers()
        
        assert len(available) == 2
        assert all(w.status in {WorkerStatus.IDLE, WorkerStatus.ONLINE} for w in available)
    
    def test_assign_job(self, registry, sample_capabilities):
        """Test job assignment."""
        registry.register_worker(
            worker_id="worker1",
            hostname="node1",
            ip_address="192.168.1.100",
            port=8080,
            capabilities=sample_capabilities
        )
        
        success = registry.assign_job("worker1", "job1", shard_id=0)
        
        assert success is True
        
        worker = registry.get_worker("worker1")
        assert worker.status == WorkerStatus.BUSY
        assert worker.assigned_job_id == "job1"
        assert worker.assigned_shard_id == 0
    
    def test_assign_job_to_busy_worker(self, registry, sample_capabilities):
        """Test assigning job to already busy worker."""
        registry.register_worker(
            worker_id="worker1",
            hostname="node1",
            ip_address="192.168.1.100",
            port=8080,
            capabilities=sample_capabilities
        )
        
        # First assignment
        registry.assign_job("worker1", "job1")
        
        # Try second assignment (should fail)
        success = registry.assign_job("worker1", "job2")
        
        assert success is False
    
    def test_release_job(self, registry, sample_capabilities):
        """Test releasing job from worker."""
        registry.register_worker(
            worker_id="worker1",
            hostname="node1",
            ip_address="192.168.1.100",
            port=8080,
            capabilities=sample_capabilities
        )
        
        registry.assign_job("worker1", "job1")
        
        success = registry.release_job("worker1")
        
        assert success is True
        
        worker = registry.get_worker("worker1")
        assert worker.status == WorkerStatus.IDLE
        assert worker.assigned_job_id is None
        assert worker.assigned_shard_id is None
    
    def test_mark_offline(self, registry, sample_capabilities):
        """Test marking worker offline."""
        registry.register_worker(
            worker_id="worker1",
            hostname="node1",
            ip_address="192.168.1.100",
            port=8080,
            capabilities=sample_capabilities
        )
        
        success = registry.mark_offline("worker1", "Manual test")
        
        assert success is True
        
        worker = registry.get_worker("worker1")
        assert worker.status == WorkerStatus.OFFLINE
    
    def test_remove_worker(self, registry, sample_capabilities):
        """Test removing worker from registry."""
        registry.register_worker(
            worker_id="worker1",
            hostname="node1",
            ip_address="192.168.1.100",
            port=8080,
            capabilities=sample_capabilities,
            group_id="group1"
        )
        
        success = registry.remove_worker("worker1")
        
        assert success is True
        assert "worker1" not in registry.workers
        assert "worker1" not in registry.workers_by_status[WorkerStatus.IDLE]
        assert "group1" not in registry.workers_by_group


class TestHealthMonitoring:
    """Test health monitoring functionality."""
    
    def test_check_worker_health_timeout(self, registry, sample_capabilities):
        """Test health check detects timeout."""
        registry.register_worker(
            worker_id="worker1",
            hostname="node1",
            ip_address="192.168.1.100",
            port=8080,
            capabilities=sample_capabilities
        )
        
        # Simulate old heartbeat
        worker = registry.get_worker("worker1")
        old_time = (datetime.utcnow() - timedelta(seconds=10)).isoformat()
        worker.last_heartbeat = old_time
        
        # Run health check
        health_report = registry.check_worker_health()
        
        assert "worker1" in health_report["offline"]
        assert registry.get_worker("worker1").status == WorkerStatus.OFFLINE
    
    def test_check_worker_health_degraded(self, registry, sample_capabilities):
        """Test health check detects degraded performance."""
        registry.register_worker(
            worker_id="worker1",
            hostname="node1",
            ip_address="192.168.1.100",
            port=8080,
            capabilities=sample_capabilities
        )
        
        # Update with overloaded metrics
        overloaded_metrics = WorkerMetrics(
            cpu_usage_percent=95.0,
            memory_usage_percent=92.0
        )
        
        registry.update_heartbeat("worker1", metrics=overloaded_metrics)
        
        # Run health check
        health_report = registry.check_worker_health()
        
        assert "worker1" in health_report["degraded"]
        assert registry.get_worker("worker1").status == WorkerStatus.DEGRADED
    
    def test_auto_recovery_from_degraded(self, registry, sample_capabilities):
        """Test auto-recovery when metrics improve."""
        registry.register_worker(
            worker_id="worker1",
            hostname="node1",
            ip_address="192.168.1.100",
            port=8080,
            capabilities=sample_capabilities
        )
        
        # Mark as degraded
        overloaded = WorkerMetrics(cpu_usage_percent=95.0)
        registry.update_heartbeat("worker1", metrics=overloaded)
        
        assert registry.get_worker("worker1").status == WorkerStatus.DEGRADED
        
        # Update with normal metrics
        normal = WorkerMetrics(cpu_usage_percent=50.0)
        registry.update_heartbeat("worker1", metrics=normal)
        
        # Should recover to IDLE
        assert registry.get_worker("worker1").status == WorkerStatus.IDLE


class TestRegistryStats:
    """Test registry statistics."""
    
    def test_get_registry_stats(self, registry, sample_capabilities):
        """Test getting registry statistics."""
        # Register multiple workers
        for i in range(3):
            registry.register_worker(
                worker_id=f"worker{i}",
                hostname=f"node{i}",
                ip_address=f"192.168.1.{100+i}",
                port=8080,
                capabilities=sample_capabilities,
                group_id=f"group{i % 2}"
            )
        
        # Assign job to one worker
        registry.assign_job("worker0", "job1")
        
        stats = registry.get_registry_stats()
        
        assert stats["total_workers"] == 3
        assert stats["status_counts"]["idle"] == 2
        assert stats["status_counts"]["busy"] == 1
        assert stats["total_gpus"] == 6  # 2 GPUs * 3 workers
        assert stats["total_ram_gb"] == 96.0  # 32GB * 3 workers
        assert len(stats["group_counts"]) == 2


class TestThreadSafety:
    """Test thread-safe operations."""
    
    def test_concurrent_heartbeats(self, registry, sample_capabilities):
        """Test concurrent heartbeat updates are thread-safe."""
        import threading
        
        # Register workers
        for i in range(5):
            registry.register_worker(
                worker_id=f"worker{i}",
                hostname=f"node{i}",
                ip_address=f"192.168.1.{100+i}",
                port=8080,
                capabilities=sample_capabilities
            )
        
        def send_heartbeats(worker_id):
            for _ in range(10):
                metrics = WorkerMetrics(cpu_usage_percent=50.0)
                registry.update_heartbeat(worker_id, metrics=metrics)
                time.sleep(0.01)
        
        # Create threads for concurrent heartbeats
        threads = []
        for i in range(5):
            t = threading.Thread(target=send_heartbeats, args=(f"worker{i}",))
            threads.append(t)
        
        # Start all threads
        for t in threads:
            t.start()
        
        # Wait for completion
        for t in threads:
            t.join()
        
        # All workers should still be registered and healthy
        assert len(registry.workers) == 5
        for i in range(5):
            worker = registry.get_worker(f"worker{i}")
            assert worker is not None
            assert worker.metrics.cpu_usage_percent == 50.0


@pytest.mark.asyncio
async def test_background_monitoring(sample_capabilities):
    """Test background monitoring task."""
    registry = WorkerRegistry(
        heartbeat_timeout_seconds=1,
        heartbeat_check_interval=0.5
    )
    
    # Register worker
    registry.register_worker(
        worker_id="worker1",
        hostname="node1",
        ip_address="192.168.1.100",
        port=8080,
        capabilities=sample_capabilities
    )
    
    # Start monitoring in background
    monitor_task = asyncio.create_task(registry.start_monitoring())
    
    # Wait for monitoring to detect timeout
    await asyncio.sleep(2)
    
    # Worker should be marked offline
    worker = registry.get_worker("worker1")
    assert worker.status == WorkerStatus.OFFLINE
    
    # Stop monitoring
    registry.stop_monitoring()
    await asyncio.sleep(0.1)
    
    monitor_task.cancel()
    try:
        await monitor_task
    except asyncio.CancelledError:
        pass
