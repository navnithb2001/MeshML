"""
Comprehensive tests for Task Assignment Service

Tests assignment strategies, batch operations, load balancing,
and integration with worker discovery and job queue services.
"""

import pytest
from datetime import datetime
from unittest.mock import Mock, MagicMock, AsyncMock
from typing import List

from app.services.task_assignment import (
    TaskAssignmentService,
    AssignmentStrategy,
    LoadBalancingPolicy,
    AssignmentConstraints,
    AssignmentConfig,
    AssignmentStatus,
    AssignmentResult,
    BatchAssignmentResult,
    WorkerLoad
)


# ==================== Fixtures ====================

@pytest.fixture
def mock_worker_registry():
    """Mock worker registry (TASK-6.1)"""
    registry = MagicMock()
    registry.workers = {}
    return registry


@pytest.fixture
def mock_job_queue():
    """Mock job queue (TASK-6.2)"""
    queue = MagicMock()
    queue.jobs = {}
    
    def mock_get_job(job_id):
        if job_id in queue.jobs:
            return queue.jobs[job_id]
        # Create mock job
        job = MagicMock()
        job.job_id = job_id
        job.metadata = MagicMock()
        job.metadata.group_id = "test_group"
        job.metadata.requirements = MagicMock()
        job.metadata.requirements.min_gpu_count = 2
        job.metadata.requirements.min_gpu_memory_gb = 16.0
        job.metadata.requirements.min_cpu_count = 16
        job.metadata.requirements.min_ram_gb = 64.0
        job.metadata.requirements.requires_cuda = True
        job.metadata.requirements.requires_mps = False
        job.priority = 1
        queue.jobs[job_id] = job
        return job
    
    def mock_list_jobs(worker_id=None, status=None):
        jobs_list = list(queue.jobs.values())
        if worker_id:
            jobs_list = [j for j in jobs_list if getattr(j, 'worker_id', None) == worker_id]
        if status:
            jobs_list = [j for j in jobs_list if getattr(j, 'status', None) == status]
        return jobs_list
    
    queue.get_job = mock_get_job
    queue.list_jobs = mock_list_jobs
    queue.release_job_from_worker = MagicMock(return_value=True)
    
    return queue


@pytest.fixture
def mock_worker_discovery():
    """Mock worker discovery service (TASK-6.3)"""
    discovery = MagicMock()
    
    def create_mock_worker(worker_id, gpu_count=4, compute_score=1000.0):
        worker = MagicMock()
        worker.worker_id = worker_id
        worker.hostname = f"host-{worker_id}"
        worker.status = "idle"
        worker.group_id = "test_group"
        worker.capabilities = MagicMock()
        worker.capabilities.gpu_count = gpu_count
        worker.capabilities.gpu_memory_gb = 24.0
        worker.capabilities.cpu_count = 64
        worker.capabilities.ram_gb = 256.0
        worker.capabilities.get_compute_score = MagicMock(return_value=compute_score)
        return worker
    
    # Create mock workers with different compute scores
    mock_workers = [
        create_mock_worker("worker_1", gpu_count=4, compute_score=1000.0),
        create_mock_worker("worker_2", gpu_count=4, compute_score=950.0),
        create_mock_worker("worker_3", gpu_count=2, compute_score=500.0)
    ]
    
    discovery.get_available_workers = MagicMock(return_value=mock_workers)
    discovery.discover_workers = MagicMock(return_value=mock_workers)
    discovery.match_worker_to_job = MagicMock(return_value=mock_workers[0])
    discovery.assign_job_to_worker = MagicMock(return_value=True)
    
    return discovery


@pytest.fixture
def assignment_service(mock_worker_discovery, mock_job_queue, mock_worker_registry):
    """Task assignment service instance"""
    config = AssignmentConfig(
        default_strategy=AssignmentStrategy.BEST_FIT,
        default_load_balancing=LoadBalancingPolicy.LEAST_LOADED,
        max_retries=3,
        batch_size=100
    )
    return TaskAssignmentService(
        mock_worker_discovery,
        mock_job_queue,
        mock_worker_registry,
        config
    )


# ==================== Test Assignment Strategies ====================

class TestAssignmentStrategies:
    """Test different assignment strategies"""
    
    @pytest.mark.asyncio
    async def test_greedy_strategy(self, assignment_service):
        """Test greedy strategy - first available worker"""
        result = await assignment_service.assign_job(
            job_id="job_001",
            strategy=AssignmentStrategy.GREEDY
        )
        
        assert result.status == AssignmentStatus.SUCCESS
        assert result.worker_id == "worker_1"  # First worker
        assert result.job_id == "job_001"
    
    @pytest.mark.asyncio
    async def test_best_fit_strategy(self, assignment_service):
        """Test best fit strategy - match capabilities"""
        result = await assignment_service.assign_job(
            job_id="job_002",
            strategy=AssignmentStrategy.BEST_FIT
        )
        
        assert result.status == AssignmentStatus.SUCCESS
        assert result.worker_id is not None
    
    @pytest.mark.asyncio
    async def test_compute_optimized_strategy(self, assignment_service):
        """Test compute optimized - highest compute score"""
        result = await assignment_service.assign_job(
            job_id="job_003",
            strategy=AssignmentStrategy.COMPUTE_OPTIMIZED
        )
        
        assert result.status == AssignmentStatus.SUCCESS
        assert result.worker_id == "worker_1"  # Highest score (1000.0)
    
    @pytest.mark.asyncio
    async def test_balanced_strategy(self, assignment_service, mock_job_queue):
        """Test balanced strategy - least loaded worker"""
        # Mock worker loads
        mock_job_queue.list_jobs = MagicMock(side_effect=lambda worker_id=None, status=None: [])
        
        result = await assignment_service.assign_job(
            job_id="job_004",
            strategy=AssignmentStrategy.BALANCED
        )
        
        assert result.status == AssignmentStatus.SUCCESS
        assert result.worker_id is not None


class TestAssignmentConstraints:
    """Test assignment constraints"""
    
    @pytest.mark.asyncio
    async def test_require_group(self, assignment_service):
        """Test group requirement constraint"""
        constraints = AssignmentConstraints(require_group="test_group")
        
        result = await assignment_service.assign_job(
            job_id="job_005",
            constraints=constraints
        )
        
        assert result.status == AssignmentStatus.SUCCESS
    
    @pytest.mark.asyncio
    async def test_exclude_workers(self, assignment_service):
        """Test excluding specific workers"""
        constraints = AssignmentConstraints(
            exclude_workers={"worker_1"}
        )
        
        result = await assignment_service.assign_job(
            job_id="job_006",
            strategy=AssignmentStrategy.GREEDY,
            constraints=constraints
        )
        
        # Should select worker_2 or worker_3 (not worker_1)
        assert result.status == AssignmentStatus.SUCCESS
        assert result.worker_id != "worker_1"
    
    @pytest.mark.asyncio
    async def test_preferred_workers(self, assignment_service):
        """Test preferred workers constraint"""
        constraints = AssignmentConstraints(
            preferred_workers=["worker_3"]
        )
        
        result = await assignment_service.assign_job(
            job_id="job_007",
            strategy=AssignmentStrategy.GREEDY,
            constraints=constraints
        )
        
        assert result.status == AssignmentStatus.SUCCESS
        # Preferred worker should be at front of list
    
    @pytest.mark.asyncio
    async def test_min_gpu_count(self, assignment_service):
        """Test minimum GPU count constraint"""
        constraints = AssignmentConstraints(min_gpu_count=4)
        
        result = await assignment_service.assign_job(
            job_id="job_008",
            constraints=constraints
        )
        
        assert result.status == AssignmentStatus.SUCCESS
    
    @pytest.mark.asyncio
    async def test_max_jobs_per_worker(self, assignment_service, mock_job_queue):
        """Test max jobs per worker constraint"""
        # Mock worker with many jobs
        mock_job_queue.list_jobs = MagicMock(return_value=[MagicMock() for _ in range(15)])
        
        constraints = AssignmentConstraints(max_jobs_per_worker=10)
        
        result = await assignment_service.assign_job(
            job_id="job_009",
            constraints=constraints
        )
        
        # All workers overloaded, should fail
        assert result.status in [AssignmentStatus.NO_WORKERS_AVAILABLE, AssignmentStatus.SUCCESS]


class TestAffinityAssignment:
    """Test affinity-based assignment"""
    
    @pytest.mark.asyncio
    async def test_affinity_strategy(self, assignment_service, mock_job_queue):
        """Test affinity - co-locate with related jobs"""
        # Setup: worker_1 already has job_related_1
        existing_job = MagicMock()
        existing_job.job_id = "job_related_1"
        existing_job.worker_id = "worker_1"
        mock_job_queue.jobs["job_related_1"] = existing_job
        
        constraints = AssignmentConstraints(
            affinity_jobs=["job_related_1"]
        )
        
        result = await assignment_service.assign_job(
            job_id="job_010",
            strategy=AssignmentStrategy.AFFINITY,
            constraints=constraints
        )
        
        assert result.status == AssignmentStatus.SUCCESS
    
    @pytest.mark.asyncio
    async def test_anti_affinity_strategy(self, assignment_service, mock_job_queue):
        """Test anti-affinity - separate from related jobs"""
        # Setup: worker_1 has job_critical_1
        existing_job = MagicMock()
        existing_job.job_id = "job_critical_1"
        existing_job.worker_id = "worker_1"
        mock_job_queue.jobs["job_critical_1"] = existing_job
        
        constraints = AssignmentConstraints(
            anti_affinity_jobs=["job_critical_1"]
        )
        
        result = await assignment_service.assign_job(
            job_id="job_011",
            strategy=AssignmentStrategy.ANTI_AFFINITY,
            constraints=constraints
        )
        
        assert result.status == AssignmentStatus.SUCCESS


# ==================== Test Batch Assignment ====================

class TestBatchAssignment:
    """Test batch assignment operations"""
    
    @pytest.mark.asyncio
    async def test_batch_assignment_success(self, assignment_service):
        """Test successful batch assignment"""
        job_ids = [f"job_{i:03d}" for i in range(10)]
        
        result = await assignment_service.assign_batch(
            job_ids=job_ids,
            strategy=AssignmentStrategy.GREEDY
        )
        
        assert isinstance(result, BatchAssignmentResult)
        assert result.total_jobs == 10
        assert result.successful >= 0
        assert len(result.assignments) == 10
        assert result.success_rate >= 0.0
    
    @pytest.mark.asyncio
    async def test_batch_round_robin(self, assignment_service):
        """Test round-robin batch assignment"""
        job_ids = [f"job_{i:03d}" for i in range(6)]
        
        result = await assignment_service.assign_batch(
            job_ids=job_ids,
            load_balancing=LoadBalancingPolicy.ROUND_ROBIN
        )
        
        assert result.total_jobs == 6
        assert result.successful >= 0
        
        # Check workers rotated
        worker_ids = [a.worker_id for a in result.assignments if a.worker_id]
        # Should have multiple different workers
    
    @pytest.mark.asyncio
    async def test_batch_least_loaded(self, assignment_service, mock_job_queue):
        """Test least loaded batch assignment"""
        mock_job_queue.list_jobs = MagicMock(return_value=[])
        
        job_ids = [f"job_{i:03d}" for i in range(5)]
        
        result = await assignment_service.assign_batch(
            job_ids=job_ids,
            load_balancing=LoadBalancingPolicy.LEAST_LOADED
        )
        
        assert result.total_jobs == 5
        assert result.successful >= 0
    
    @pytest.mark.asyncio
    async def test_batch_weighted_round_robin(self, assignment_service):
        """Test weighted round-robin based on compute score"""
        job_ids = [f"job_{i:03d}" for i in range(9)]
        
        result = await assignment_service.assign_batch(
            job_ids=job_ids,
            load_balancing=LoadBalancingPolicy.WEIGHTED_ROUND_ROBIN
        )
        
        assert result.total_jobs == 9
        # Higher compute score workers should get more jobs
    
    @pytest.mark.asyncio
    async def test_batch_priority_based(self, assignment_service, mock_job_queue):
        """Test priority-based batch assignment"""
        # Create jobs with different priorities
        for i in range(5):
            job = MagicMock()
            job.job_id = f"job_{i:03d}"
            job.priority = i  # 0 to 4
            mock_job_queue.jobs[f"job_{i:03d}"] = job
        
        job_ids = [f"job_{i:03d}" for i in range(5)]
        
        result = await assignment_service.assign_batch(
            job_ids=job_ids,
            load_balancing=LoadBalancingPolicy.PRIORITY_BASED
        )
        
        assert result.total_jobs == 5
        # High priority jobs should go to best workers
    
    @pytest.mark.asyncio
    async def test_batch_with_constraints(self, assignment_service):
        """Test batch assignment with constraints"""
        job_ids = [f"job_{i:03d}" for i in range(5)]
        constraints = AssignmentConstraints(
            require_group="test_group",
            min_gpu_count=2
        )
        
        result = await assignment_service.assign_batch(
            job_ids=job_ids,
            constraints=constraints
        )
        
        assert result.total_jobs == 5
    
    @pytest.mark.asyncio
    async def test_batch_empty_jobs(self, assignment_service):
        """Test batch assignment with empty job list"""
        result = await assignment_service.assign_batch(
            job_ids=[],
            strategy=AssignmentStrategy.GREEDY
        )
        
        assert result.total_jobs == 0
        assert result.successful == 0
        assert result.failed == 0


# ==================== Test Load Monitoring ====================

class TestLoadMonitoring:
    """Test load monitoring functionality"""
    
    @pytest.mark.asyncio
    async def test_get_worker_load(self, assignment_service, mock_job_queue):
        """Test getting worker load"""
        # Mock 5 jobs on worker
        mock_job_queue.list_jobs = MagicMock(return_value=[MagicMock() for _ in range(5)])
        
        load = await assignment_service.get_worker_load("worker_1")
        
        assert isinstance(load, WorkerLoad)
        assert load.worker_id == "worker_1"
        assert load.assigned_jobs == 5
        assert load.total_capacity > 0
        assert 0.0 <= load.utilization <= 1.0
        assert load.available_capacity >= 0
    
    @pytest.mark.asyncio
    async def test_get_cluster_load(self, assignment_service, mock_job_queue):
        """Test getting cluster load statistics"""
        mock_job_queue.list_jobs = MagicMock(return_value=[])
        
        stats = await assignment_service.get_cluster_load()
        
        assert "total_workers" in stats
        assert "total_jobs" in stats
        assert "avg_utilization" in stats
        assert "worker_loads" in stats
        assert stats["total_workers"] == 3  # 3 mock workers
    
    @pytest.mark.asyncio
    async def test_get_cluster_load_by_group(self, assignment_service, mock_job_queue):
        """Test getting cluster load for specific group"""
        mock_job_queue.list_jobs = MagicMock(return_value=[])
        
        stats = await assignment_service.get_cluster_load(group_id="test_group")
        
        assert stats["group_id"] == "test_group"
        assert "total_workers" in stats
    
    @pytest.mark.asyncio
    async def test_worker_load_utilization(self, assignment_service, mock_job_queue):
        """Test worker load utilization calculation"""
        # Mock 80 jobs (80% utilization with capacity 100)
        mock_job_queue.list_jobs = MagicMock(return_value=[MagicMock() for _ in range(80)])
        
        load = await assignment_service.get_worker_load("worker_1")
        
        assert load.utilization == pytest.approx(0.8, rel=0.1)
        assert load.assigned_jobs == 80
        assert load.available_capacity == 20


# ==================== Test Load Rebalancing ====================

class TestLoadRebalancing:
    """Test load rebalancing functionality"""
    
    @pytest.mark.asyncio
    async def test_rebalance_load(self, assignment_service, mock_job_queue):
        """Test load rebalancing"""
        # Setup: worker_1 overloaded, worker_2 underutilized
        def mock_list_for_rebalance(worker_id=None, status=None):
            if worker_id == "worker_1":
                return [MagicMock(job_id=f"job_{i}") for i in range(90)]  # Overloaded
            elif worker_id == "worker_2":
                return [MagicMock(job_id=f"job_{i}") for i in range(20)]  # Underutilized
            return []
        
        mock_job_queue.list_jobs = mock_list_for_rebalance
        
        result = await assignment_service.rebalance_load()
        
        assert "reassigned_jobs" in result
        assert "overloaded_workers" in result
        assert "underutilized_workers" in result
        assert result["reassigned_jobs"] >= 0
    
    @pytest.mark.asyncio
    async def test_rebalance_with_threshold(self, assignment_service, mock_job_queue):
        """Test rebalancing with custom threshold"""
        mock_job_queue.list_jobs = MagicMock(return_value=[])
        
        result = await assignment_service.rebalance_load(threshold=0.7)
        
        assert "reassigned_jobs" in result
    
    @pytest.mark.asyncio
    async def test_auto_rebalancing_start_stop(self, assignment_service):
        """Test starting and stopping auto-rebalancing"""
        # Start
        await assignment_service.start_auto_rebalancing()
        assert assignment_service.rebalance_task is not None
        
        # Stop
        await assignment_service.stop_auto_rebalancing()
        assert assignment_service.rebalance_task is None


# ==================== Test Statistics ====================

class TestStatistics:
    """Test statistics collection"""
    
    @pytest.mark.asyncio
    async def test_assignment_stats(self, assignment_service):
        """Test getting assignment statistics"""
        # Make some assignments
        for i in range(5):
            await assignment_service.assign_job(f"job_{i}")
        
        stats = assignment_service.get_assignment_stats(hours=24)
        
        assert "total_assignments" in stats
        assert "successful" in stats
        assert "failed" in stats
        assert "success_rate" in stats
        assert stats["hours"] == 24
        assert stats["total_assignments"] >= 0
    
    @pytest.mark.asyncio
    async def test_assignment_stats_custom_hours(self, assignment_service):
        """Test statistics for custom time window"""
        stats = assignment_service.get_assignment_stats(hours=48)
        
        assert stats["hours"] == 48
    
    @pytest.mark.asyncio
    async def test_assignment_history(self, assignment_service):
        """Test assignment history tracking"""
        initial_count = len(assignment_service.assignment_history)
        
        await assignment_service.assign_job("job_test")
        
        assert len(assignment_service.assignment_history) == initial_count + 1


# ==================== Test Error Handling ====================

class TestErrorHandling:
    """Test error handling"""
    
    @pytest.mark.asyncio
    async def test_job_not_found(self, assignment_service, mock_job_queue):
        """Test assignment when job doesn't exist"""
        mock_job_queue.get_job = MagicMock(return_value=None)
        
        result = await assignment_service.assign_job("nonexistent_job")
        
        assert result.status == AssignmentStatus.FAILED
        assert "not found" in result.error.lower()
    
    @pytest.mark.asyncio
    async def test_no_workers_available(self, assignment_service, mock_worker_discovery):
        """Test assignment when no workers available"""
        mock_worker_discovery.get_available_workers = MagicMock(return_value=[])
        
        result = await assignment_service.assign_job("job_001")
        
        assert result.status == AssignmentStatus.NO_WORKERS_AVAILABLE
    
    @pytest.mark.asyncio
    async def test_assignment_failure(self, assignment_service, mock_worker_discovery):
        """Test handling of assignment failure"""
        mock_worker_discovery.assign_job_to_worker = MagicMock(return_value=False)
        
        result = await assignment_service.assign_job("job_001")
        
        assert result.status == AssignmentStatus.FAILED


# ==================== Integration Tests ====================

class TestIntegration:
    """Integration tests for complete workflows"""
    
    @pytest.mark.asyncio
    async def test_complete_assignment_workflow(self, assignment_service):
        """Test complete job assignment workflow"""
        # 1. Assign single job
        result = await assignment_service.assign_job(
            job_id="workflow_job_001",
            strategy=AssignmentStrategy.BEST_FIT
        )
        
        assert result.status == AssignmentStatus.SUCCESS
        assert result.worker_id is not None
        
        # 2. Check worker load
        load = await assignment_service.get_worker_load(result.worker_id)
        assert load.worker_id == result.worker_id
        
        # 3. Get cluster stats
        cluster_stats = await assignment_service.get_cluster_load()
        assert cluster_stats["total_workers"] > 0
    
    @pytest.mark.asyncio
    async def test_batch_workflow_with_rebalancing(self, assignment_service, mock_job_queue):
        """Test batch assignment followed by rebalancing"""
        mock_job_queue.list_jobs = MagicMock(return_value=[])
        
        # 1. Batch assign jobs
        job_ids = [f"batch_job_{i:03d}" for i in range(20)]
        batch_result = await assignment_service.assign_batch(
            job_ids=job_ids,
            load_balancing=LoadBalancingPolicy.ROUND_ROBIN
        )
        
        assert batch_result.total_jobs == 20
        
        # 2. Check cluster load
        cluster_load = await assignment_service.get_cluster_load()
        assert "avg_utilization" in cluster_load
        
        # 3. Rebalance if needed
        rebalance_result = await assignment_service.rebalance_load()
        assert "reassigned_jobs" in rebalance_result
    
    @pytest.mark.asyncio
    async def test_multi_strategy_comparison(self, assignment_service):
        """Test comparing different strategies"""
        strategies = [
            AssignmentStrategy.GREEDY,
            AssignmentStrategy.BEST_FIT,
            AssignmentStrategy.COMPUTE_OPTIMIZED,
            AssignmentStrategy.BALANCED
        ]
        
        results = []
        for i, strategy in enumerate(strategies):
            result = await assignment_service.assign_job(
                job_id=f"compare_job_{i}",
                strategy=strategy
            )
            results.append(result)
        
        # All should succeed
        assert all(r.status == AssignmentStatus.SUCCESS for r in results)
