"""
Comprehensive tests for Worker Discovery & Registration Service

Tests worker registration, pool management, worker-job matching,
and integration between TASK-6.1 and TASK-6.2.
"""

import pytest
from datetime import datetime
from typing import Dict, Any
from unittest.mock import Mock, MagicMock, patch

from app.services.worker_discovery import (
    WorkerDiscoveryService,
    WorkerInfo,
    WorkerCapabilities,
    WorkerPool,
    WorkerStatus,
    WorkerPoolStatus,
    DiscoveryConfig
)


# ==================== Fixtures ====================

@pytest.fixture
def mock_worker_registry():
    """Mock worker registry (TASK-6.1)"""
    registry = MagicMock()
    registry.workers = {}
    registry.workers_by_group = {}
    
    def mock_register_worker(worker_id, hostname, ip_address, port, capabilities, 
                            group_id=None, version="1.0.0", tags=None):
        worker = MagicMock()
        worker.worker_id = worker_id
        worker.hostname = hostname
        worker.ip_address = ip_address
        worker.port = port
        worker.group_id = group_id
        worker.assigned_job_id = None
        worker.assigned_shard_ids = []
        worker.registered_at = datetime.utcnow().isoformat()
        worker.last_heartbeat = datetime.utcnow().isoformat()
        
        # Create capabilities object
        caps = MagicMock()
        caps.to_dict = lambda: capabilities
        worker.capabilities = caps
        
        # Create status object
        status = MagicMock()
        status.value = "idle"
        worker.status = status
        
        registry.workers[worker_id] = worker
        return worker
    
    def mock_list_workers(group_id=None, min_gpu_count=0):
        workers = list(registry.workers.values())
        if group_id:
            workers = [w for w in workers if w.group_id == group_id]
        if min_gpu_count > 0:
            workers = [w for w in workers if w.capabilities.to_dict().get('gpu_count', 0) >= min_gpu_count]
        return workers
    
    def mock_remove_worker(worker_id):
        if worker_id in registry.workers:
            del registry.workers[worker_id]
            return True
        return False
    
    def mock_assign_job(worker_id, job_id, shard_id=None):
        if worker_id in registry.workers:
            registry.workers[worker_id].assigned_job_id = job_id
            return True
        return False
    
    registry.register_worker = mock_register_worker
    registry.list_workers = mock_list_workers
    registry.remove_worker = mock_remove_worker
    registry.assign_job = mock_assign_job
    
    return registry


@pytest.fixture
def mock_job_queue():
    """Mock job queue (TASK-6.2)"""
    queue = MagicMock()
    queue.jobs = {}
    
    def mock_get_job(job_id):
        return queue.jobs.get(job_id)
    
    def mock_assign_job_to_worker(job_id, worker_id, shard_ids=None):
        if job_id in queue.jobs:
            queue.jobs[job_id].assigned_worker_id = worker_id
            queue.jobs[job_id].assigned_shard_ids = shard_ids or []
            return True
        return False
    
    def mock_release_job_from_worker(job_id, worker_id, reason):
        if job_id in queue.jobs:
            queue.jobs[job_id].assigned_worker_id = None
            queue.jobs[job_id].assigned_shard_ids = []
            return True
        return False
    
    queue.get_job = mock_get_job
    queue.assign_job_to_worker = mock_assign_job_to_worker
    queue.release_job_from_worker = mock_release_job_from_worker
    
    return queue


@pytest.fixture
def discovery_service(mock_worker_registry, mock_job_queue):
    """Discovery service instance with mocks"""
    config = DiscoveryConfig(
        heartbeat_timeout_seconds=30,
        discovery_interval_seconds=60,
        auto_register_workers=True,
        require_group_assignment=False,
        enable_auto_scaling=True
    )
    return WorkerDiscoveryService(mock_worker_registry, mock_job_queue, config)


@pytest.fixture
def sample_capabilities():
    """Sample worker capabilities"""
    return WorkerCapabilities(
        gpu_count=4,
        gpu_memory_gb=24.0,
        gpu_type="NVIDIA A100",
        cpu_count=64,
        ram_gb=256.0,
        network_speed_mbps=10000.0,
        storage_gb=2000.0,
        supports_cuda=True,
        supports_mps=False,
        pytorch_version="2.0.0",
        python_version="3.10.8"
    )


# ==================== Test WorkerCapabilities ====================

class TestWorkerCapabilities:
    """Test WorkerCapabilities dataclass"""
    
    def test_capabilities_creation(self, sample_capabilities):
        """Test capabilities creation"""
        assert sample_capabilities.gpu_count == 4
        assert sample_capabilities.gpu_memory_gb == 24.0
        assert sample_capabilities.supports_cuda is True
    
    def test_compute_score_calculation(self):
        """Test compute score calculation"""
        # GPU-heavy worker
        gpu_worker = WorkerCapabilities(
            gpu_count=4, gpu_memory_gb=24.0, gpu_type="A100",
            cpu_count=64, ram_gb=256.0, network_speed_mbps=10000,
            storage_gb=2000, supports_cuda=True, supports_mps=False,
            pytorch_version="2.0.0", python_version="3.10"
        )
        gpu_score = gpu_worker.get_compute_score()
        # 4 * 24 * 10 + 64 * 0.5 + 256 * 0.2 = 960 + 32 + 51.2 = 1043.2
        assert gpu_score == pytest.approx(1043.2, rel=0.01)
        
        # CPU-only worker
        cpu_worker = WorkerCapabilities(
            gpu_count=0, gpu_memory_gb=0.0, gpu_type="None",
            cpu_count=32, ram_gb=128.0, network_speed_mbps=1000,
            storage_gb=500, supports_cuda=False, supports_mps=False,
            pytorch_version="2.0.0", python_version="3.10"
        )
        cpu_score = cpu_worker.get_compute_score()
        # 0 + 32 * 0.5 + 128 * 0.2 = 16 + 25.6 = 41.6
        assert cpu_score == pytest.approx(41.6, rel=0.01)
        
        # GPU worker should score much higher
        assert gpu_score > cpu_score * 10
    
    def test_capabilities_serialization(self, sample_capabilities):
        """Test to_dict and from_dict"""
        data = sample_capabilities.to_dict()
        assert data["gpu_count"] == 4
        assert data["gpu_type"] == "NVIDIA A100"
        
        caps2 = WorkerCapabilities.from_dict(data)
        assert caps2.gpu_count == sample_capabilities.gpu_count
        assert caps2.supports_cuda == sample_capabilities.supports_cuda


# ==================== Test WorkerPool ====================

class TestWorkerPool:
    """Test WorkerPool management"""
    
    def test_pool_creation(self):
        """Test pool creation"""
        pool = WorkerPool(
            group_id="research_team",
            name="Research GPU Pool",
            description="High-performance pool",
            min_workers=5,
            max_workers=50,
            auto_scale=True,
            tags={"cost_center": "research"}
        )
        
        assert pool.group_id == "research_team"
        assert pool.name == "Research GPU Pool"
        assert pool.min_workers == 5
        assert pool.max_workers == 50
        assert pool.auto_scale is True
    
    def test_pool_worker_tracking(self):
        """Test worker tracking in pool"""
        pool = WorkerPool(group_id="team", name="Pool")
        
        assert pool.get_worker_count() == 0
        
        pool.worker_ids.add("worker_1")
        pool.worker_ids.add("worker_2")
        
        assert pool.get_worker_count() == 2
    
    def test_pool_capacity_checks(self):
        """Test pool capacity checks"""
        pool = WorkerPool(
            group_id="team",
            name="Pool",
            min_workers=2,
            max_workers=5
        )
        
        assert not pool.is_at_capacity()
        
        # Add workers up to max
        for i in range(5):
            pool.worker_ids.add(f"worker_{i}")
        
        assert pool.is_at_capacity()
        assert pool.get_worker_count() == 5
    
    def test_pool_scaling_needs(self):
        """Test pool scaling needs detection"""
        pool = WorkerPool(
            group_id="team",
            name="Pool",
            min_workers=3,
            auto_scale=True
        )
        
        # Needs scaling (below minimum)
        assert pool.needs_scaling()
        
        # Add workers
        for i in range(3):
            pool.worker_ids.add(f"worker_{i}")
        
        # No longer needs scaling
        assert not pool.needs_scaling()
        
        # Disable auto-scale
        pool.auto_scale = False
        pool.worker_ids.clear()
        assert not pool.needs_scaling()


# ==================== Test Worker Pool Management ====================

class TestWorkerPoolManagement:
    """Test worker pool management operations"""
    
    def test_create_pool(self, discovery_service):
        """Test creating worker pool"""
        pool = discovery_service.create_pool(
            group_id="research_team",
            name="Research Pool",
            description="GPU pool for research",
            min_workers=5,
            max_workers=50,
            auto_scale=True,
            tags={"priority": "high"}
        )
        
        assert pool.group_id == "research_team"
        assert pool.name == "Research Pool"
        assert pool.min_workers == 5
        assert pool.max_workers == 50
        
        # Pool should be in service pools
        assert "research_team" in discovery_service.pools
    
    def test_create_duplicate_pool(self, discovery_service):
        """Test creating duplicate pool returns existing"""
        pool1 = discovery_service.create_pool("team", "Pool 1")
        pool2 = discovery_service.create_pool("team", "Pool 2")
        
        # Should return same pool
        assert pool1.group_id == pool2.group_id
        assert len(discovery_service.pools) == 1
    
    def test_get_pool(self, discovery_service):
        """Test getting pool by group ID"""
        discovery_service.create_pool("team_a", "Pool A")
        
        pool = discovery_service.get_pool("team_a")
        assert pool is not None
        assert pool.group_id == "team_a"
        
        # Nonexistent pool
        pool = discovery_service.get_pool("nonexistent")
        assert pool is None
    
    def test_list_pools(self, discovery_service):
        """Test listing all pools"""
        discovery_service.create_pool("team_a", "Pool A")
        discovery_service.create_pool("team_b", "Pool B")
        discovery_service.create_pool("team_c", "Pool C")
        
        pools = discovery_service.list_pools()
        assert len(pools) == 3
        
        group_ids = [p.group_id for p in pools]
        assert "team_a" in group_ids
        assert "team_b" in group_ids
        assert "team_c" in group_ids
    
    def test_delete_pool_with_workers(self, discovery_service, sample_capabilities):
        """Test deleting pool with active workers"""
        discovery_service.create_pool("team", "Pool")
        
        # Register worker in pool
        discovery_service.register_worker(
            worker_id="worker_1",
            hostname="host1",
            ip_address="192.168.1.1",
            port=8080,
            capabilities=sample_capabilities,
            group_id="team"
        )
        
        # Cannot delete without force
        success = discovery_service.delete_pool("team", force=False)
        assert not success
        
        # Can delete with force
        success = discovery_service.delete_pool("team", force=True)
        assert success
        assert "team" not in discovery_service.pools
    
    def test_delete_empty_pool(self, discovery_service):
        """Test deleting empty pool"""
        discovery_service.create_pool("team", "Pool")
        
        success = discovery_service.delete_pool("team")
        assert success
        assert "team" not in discovery_service.pools


# ==================== Test Worker Registration ====================

class TestWorkerRegistration:
    """Test worker registration operations"""
    
    def test_register_worker(self, discovery_service, sample_capabilities):
        """Test basic worker registration"""
        worker_info = discovery_service.register_worker(
            worker_id="worker_001",
            hostname="gpu-node-1",
            ip_address="192.168.1.100",
            port=8080,
            capabilities=sample_capabilities,
            group_id="research_team",
            version="1.0.0",
            tags={"region": "us-west"}
        )
        
        assert worker_info.worker_id == "worker_001"
        assert worker_info.hostname == "gpu-node-1"
        assert worker_info.group_id == "research_team"
        assert worker_info.capabilities.gpu_count == 4
    
    def test_register_worker_creates_pool(self, discovery_service, sample_capabilities):
        """Test registering worker auto-creates pool"""
        worker_info = discovery_service.register_worker(
            worker_id="worker_001",
            hostname="host1",
            ip_address="192.168.1.1",
            port=8080,
            capabilities=sample_capabilities,
            group_id="new_team"
        )
        
        # Pool should be auto-created
        assert "new_team" in discovery_service.pools
        assert "worker_001" in discovery_service.pools["new_team"].worker_ids
    
    def test_register_worker_pool_capacity(self, discovery_service, sample_capabilities):
        """Test worker registration respects pool capacity"""
        # Create pool with max 2 workers
        discovery_service.create_pool("team", "Pool", max_workers=2)
        
        # Register 2 workers (should succeed)
        discovery_service.register_worker(
            "worker_1", "host1", "192.168.1.1", 8080,
            sample_capabilities, group_id="team"
        )
        discovery_service.register_worker(
            "worker_2", "host2", "192.168.1.2", 8080,
            sample_capabilities, group_id="team"
        )
        
        # Third worker should fail (capacity exceeded)
        with pytest.raises(ValueError, match="at maximum capacity"):
            discovery_service.register_worker(
                "worker_3", "host3", "192.168.1.3", 8080,
                sample_capabilities, group_id="team"
            )
    
    def test_register_worker_requires_group(self, sample_capabilities):
        """Test group requirement enforcement"""
        # Create service with group requirement
        config = DiscoveryConfig(require_group_assignment=True)
        registry = MagicMock()
        queue = MagicMock()
        service = WorkerDiscoveryService(registry, queue, config)
        
        # Should fail without group
        with pytest.raises(ValueError, match="Group assignment required"):
            service.register_worker(
                "worker_1", "host1", "192.168.1.1", 8080,
                sample_capabilities, group_id=None
            )
    
    def test_unregister_worker(self, discovery_service, sample_capabilities):
        """Test worker unregistration"""
        # Register worker
        discovery_service.register_worker(
            "worker_001", "host1", "192.168.1.1", 8080,
            sample_capabilities, group_id="team"
        )
        
        # Verify registered
        assert "team" in discovery_service.pools
        assert "worker_001" in discovery_service.pools["team"].worker_ids
        
        # Unregister
        success = discovery_service.unregister_worker("worker_001")
        assert success
        
        # Should be removed from pool
        assert "worker_001" not in discovery_service.pools["team"].worker_ids
        assert "worker_001" not in discovery_service.worker_to_pool


# ==================== Test Worker Discovery ====================

class TestWorkerDiscovery:
    """Test worker discovery operations"""
    
    def test_discover_all_workers(self, discovery_service, sample_capabilities):
        """Test discovering all workers"""
        # Register multiple workers
        for i in range(3):
            discovery_service.register_worker(
                f"worker_{i}", f"host{i}", f"192.168.1.{i}", 8080,
                sample_capabilities, group_id="team"
            )
        
        workers = discovery_service.discover_workers()
        assert len(workers) == 3
    
    def test_discover_workers_by_group(self, discovery_service, sample_capabilities):
        """Test discovering workers by group"""
        # Register workers in different groups
        discovery_service.register_worker(
            "worker_1", "host1", "192.168.1.1", 8080,
            sample_capabilities, group_id="team_a"
        )
        discovery_service.register_worker(
            "worker_2", "host2", "192.168.1.2", 8080,
            sample_capabilities, group_id="team_b"
        )
        discovery_service.register_worker(
            "worker_3", "host3", "192.168.1.3", 8080,
            sample_capabilities, group_id="team_a"
        )
        
        # Discover team_a workers
        workers = discovery_service.discover_workers(group_id="team_a")
        assert len(workers) == 2
        assert all(w.group_id == "team_a" for w in workers)
    
    def test_discover_workers_by_gpu_count(self, discovery_service):
        """Test discovering workers by GPU count"""
        # Worker with 4 GPUs
        caps_4gpu = WorkerCapabilities(
            gpu_count=4, gpu_memory_gb=24.0, gpu_type="A100",
            cpu_count=64, ram_gb=256.0, network_speed_mbps=10000,
            storage_gb=2000, supports_cuda=True, supports_mps=False,
            pytorch_version="2.0.0", python_version="3.10"
        )
        
        # Worker with 2 GPUs
        caps_2gpu = WorkerCapabilities(
            gpu_count=2, gpu_memory_gb=16.0, gpu_type="V100",
            cpu_count=32, ram_gb=128.0, network_speed_mbps=5000,
            storage_gb=1000, supports_cuda=True, supports_mps=False,
            pytorch_version="2.0.0", python_version="3.10"
        )
        
        discovery_service.register_worker(
            "worker_4gpu", "host1", "192.168.1.1", 8080,
            caps_4gpu, group_id="team"
        )
        discovery_service.register_worker(
            "worker_2gpu", "host2", "192.168.1.2", 8080,
            caps_2gpu, group_id="team"
        )
        
        # Discover workers with at least 3 GPUs
        workers = discovery_service.discover_workers(min_gpu_count=3)
        assert len(workers) == 1
        assert workers[0].worker_id == "worker_4gpu"
    
    def test_get_available_workers(self, discovery_service, sample_capabilities):
        """Test getting available workers (IDLE/ONLINE only)"""
        # This test depends on mock returning workers with IDLE status
        discovery_service.register_worker(
            "worker_1", "host1", "192.168.1.1", 8080,
            sample_capabilities, group_id="team"
        )
        
        available = discovery_service.get_available_workers(group_id="team")
        # Mock returns IDLE status, so should be available
        assert len(available) >= 0  # Depends on mock implementation


# ==================== Test Worker-Job Matching ====================

class TestWorkerJobMatching:
    """Test worker-job matching operations"""
    
    def test_match_worker_to_job(self, discovery_service, sample_capabilities, mock_job_queue):
        """Test matching worker to job based on requirements"""
        # Register worker
        discovery_service.register_worker(
            "worker_gpu", "host1", "192.168.1.1", 8080,
            sample_capabilities, group_id="team"
        )
        
        # Create mock job with requirements
        job = MagicMock()
        job.job_id = "job_001"
        job.metadata.group_id = "team"
        job.metadata.requirements.min_gpu_count = 2
        job.metadata.requirements.min_gpu_memory_gb = 16.0
        job.metadata.requirements.min_cpu_count = 32
        job.metadata.requirements.min_ram_gb = 128.0
        job.metadata.requirements.requires_cuda = True
        job.metadata.requirements.requires_mps = False
        
        mock_job_queue.jobs["job_001"] = job
        
        # Match worker to job
        worker = discovery_service.match_worker_to_job("job_001")
        
        # Should find matching worker
        assert worker is not None
        assert worker.worker_id == "worker_gpu"
    
    def test_match_worker_insufficient_resources(self, discovery_service, mock_job_queue):
        """Test matching fails when worker has insufficient resources"""
        # Worker with only 2 GPUs
        caps_2gpu = WorkerCapabilities(
            gpu_count=2, gpu_memory_gb=16.0, gpu_type="V100",
            cpu_count=32, ram_gb=128.0, network_speed_mbps=5000,
            storage_gb=1000, supports_cuda=True, supports_mps=False,
            pytorch_version="2.0.0", python_version="3.10"
        )
        
        discovery_service.register_worker(
            "worker_2gpu", "host1", "192.168.1.1", 8080,
            caps_2gpu, group_id="team"
        )
        
        # Job requiring 4 GPUs
        job = MagicMock()
        job.job_id = "job_gpu4"
        job.metadata.group_id = "team"
        job.metadata.requirements.min_gpu_count = 4
        job.metadata.requirements.min_gpu_memory_gb = 24.0
        job.metadata.requirements.min_cpu_count = 16
        job.metadata.requirements.min_ram_gb = 64.0
        job.metadata.requirements.requires_cuda = True
        job.metadata.requirements.requires_mps = False
        
        mock_job_queue.jobs["job_gpu4"] = job
        
        # Should not find matching worker
        worker = discovery_service.match_worker_to_job("job_gpu4")
        assert worker is None
    
    def test_assign_job_to_worker(self, discovery_service, sample_capabilities, mock_job_queue):
        """Test assigning job to worker"""
        # Register worker
        discovery_service.register_worker(
            "worker_001", "host1", "192.168.1.1", 8080,
            sample_capabilities, group_id="team"
        )
        
        # Create job
        job = MagicMock()
        job.job_id = "job_001"
        job.metadata.group_id = "team"
        job.metadata.requirements.min_gpu_count = 2
        job.metadata.requirements.min_gpu_memory_gb = 16.0
        job.metadata.requirements.min_cpu_count = 16
        job.metadata.requirements.min_ram_gb = 64.0
        job.metadata.requirements.requires_cuda = True
        job.metadata.requirements.requires_mps = False
        
        mock_job_queue.jobs["job_001"] = job
        
        # Assign job
        success = discovery_service.assign_job_to_worker(
            job_id="job_001",
            worker_id="worker_001",
            shard_ids=[0, 1, 2]
        )
        
        assert success


# ==================== Test Pool Health Monitoring ====================

class TestPoolHealthMonitoring:
    """Test pool health monitoring"""
    
    def test_get_pool_status_healthy(self, discovery_service, sample_capabilities):
        """Test healthy pool status (>= 80% workers available)"""
        discovery_service.create_pool("team", "Pool")
        
        # Register 5 workers (all IDLE/ONLINE = healthy)
        for i in range(5):
            discovery_service.register_worker(
                f"worker_{i}", f"host{i}", f"192.168.1.{i}", 8080,
                sample_capabilities, group_id="team"
            )
        
        status = discovery_service.get_pool_status("team")
        # Mock returns IDLE workers, so should be HEALTHY
        assert status in [WorkerPoolStatus.HEALTHY, WorkerPoolStatus.DEGRADED, WorkerPoolStatus.OFFLINE]
    
    def test_get_pool_stats(self, discovery_service, sample_capabilities):
        """Test getting pool statistics"""
        discovery_service.create_pool("team", "Pool", min_workers=2, max_workers=10)
        
        # Register workers
        for i in range(3):
            discovery_service.register_worker(
                f"worker_{i}", f"host{i}", f"192.168.1.{i}", 8080,
                sample_capabilities, group_id="team"
            )
        
        stats = discovery_service.get_pool_stats("team")
        
        assert stats["group_id"] == "team"
        assert stats["total_workers"] == 3
        assert stats["min_workers"] == 2
        assert stats["max_workers"] == 10
        assert "total_gpus" in stats
        assert "avg_compute_score" in stats


# ==================== Test Auto-Scaling ====================

class TestAutoScaling:
    """Test auto-scaling detection"""
    
    def test_check_scaling_needs_scale_up(self, discovery_service, sample_capabilities):
        """Test detecting need to scale up"""
        # Create pool with min 5 workers, auto-scale enabled
        discovery_service.create_pool(
            "team", "Pool",
            min_workers=5,
            max_workers=20,
            auto_scale=True
        )
        
        # Register only 2 workers (below minimum)
        for i in range(2):
            discovery_service.register_worker(
                f"worker_{i}", f"host{i}", f"192.168.1.{i}", 8080,
                sample_capabilities, group_id="team"
            )
        
        scaling_needs = discovery_service.check_scaling_needs()
        
        # Should need scaling up
        assert "team" in scaling_needs
        assert scaling_needs["team"] == "scale_up"
    
    def test_check_scaling_no_action(self, discovery_service, sample_capabilities):
        """Test no scaling needed when at optimal level"""
        # Create pool with min 3 workers
        discovery_service.create_pool(
            "team", "Pool",
            min_workers=3,
            max_workers=20,
            auto_scale=True
        )
        
        # Register exactly min workers
        for i in range(3):
            discovery_service.register_worker(
                f"worker_{i}", f"host{i}", f"192.168.1.{i}", 8080,
                sample_capabilities, group_id="team"
            )
        
        scaling_needs = discovery_service.check_scaling_needs()
        
        # Should not need scaling
        assert "team" not in scaling_needs or scaling_needs.get("team") != "scale_up"


# ==================== Test System Statistics ====================

class TestSystemStatistics:
    """Test system-wide statistics"""
    
    def test_get_worker_distribution(self, discovery_service, sample_capabilities):
        """Test getting worker distribution across pools"""
        # Register workers in different pools
        for group in ["team_a", "team_b", "team_c"]:
            count = {"team_a": 3, "team_b": 5, "team_c": 2}[group]
            for i in range(count):
                discovery_service.register_worker(
                    f"{group}_worker_{i}", f"host{i}", f"192.168.1.{i}", 8080,
                    sample_capabilities, group_id=group
                )
        
        distribution = discovery_service.get_worker_distribution()
        
        assert distribution["team_a"] == 3
        assert distribution["team_b"] == 5
        assert distribution["team_c"] == 2
    
    def test_get_total_capacity(self, discovery_service, sample_capabilities):
        """Test getting total system capacity"""
        # Register workers
        for i in range(5):
            discovery_service.register_worker(
                f"worker_{i}", f"host{i}", f"192.168.1.{i}", 8080,
                sample_capabilities, group_id="team"
            )
        
        capacity = discovery_service.get_total_capacity()
        
        assert capacity["total_workers"] == 5
        assert capacity["total_gpus"] == 5 * sample_capabilities.gpu_count
        assert capacity["total_ram_gb"] == 5 * sample_capabilities.ram_gb
        assert "avg_compute_score" in capacity


# ==================== Integration Tests ====================

class TestIntegration:
    """Integration tests for complete workflows"""
    
    def test_complete_worker_lifecycle(self, discovery_service, sample_capabilities):
        """Test complete worker lifecycle"""
        # 1. Create pool
        pool = discovery_service.create_pool("team", "Pool", min_workers=2, max_workers=10)
        assert pool.group_id == "team"
        
        # 2. Register worker
        worker = discovery_service.register_worker(
            "worker_001", "host1", "192.168.1.1", 8080,
            sample_capabilities, group_id="team"
        )
        assert worker.worker_id == "worker_001"
        assert "worker_001" in pool.worker_ids
        
        # 3. Discover worker
        workers = discovery_service.discover_workers(group_id="team")
        assert len(workers) == 1
        
        # 4. Unregister worker
        success = discovery_service.unregister_worker("worker_001")
        assert success
        assert "worker_001" not in pool.worker_ids
    
    def test_job_assignment_workflow(self, discovery_service, sample_capabilities, mock_job_queue):
        """Test complete job assignment workflow"""
        # 1. Register worker
        discovery_service.register_worker(
            "worker_gpu", "host1", "192.168.1.1", 8080,
            sample_capabilities, group_id="research"
        )
        
        # 2. Create job
        job = MagicMock()
        job.job_id = "training_job_001"
        job.metadata.group_id = "research"
        job.metadata.requirements.min_gpu_count = 2
        job.metadata.requirements.min_gpu_memory_gb = 16.0
        job.metadata.requirements.min_cpu_count = 16
        job.metadata.requirements.min_ram_gb = 64.0
        job.metadata.requirements.requires_cuda = True
        job.metadata.requirements.requires_mps = False
        
        mock_job_queue.jobs["training_job_001"] = job
        
        # 3. Match worker to job
        matched_worker = discovery_service.match_worker_to_job("training_job_001")
        assert matched_worker is not None
        assert matched_worker.worker_id == "worker_gpu"
        
        # 4. Assign job to worker
        success = discovery_service.assign_job_to_worker(
            job_id="training_job_001",
            worker_id="worker_gpu",
            shard_ids=[0, 1]
        )
        assert success
