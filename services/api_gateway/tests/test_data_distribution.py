"""Tests for data distribution service."""

import tempfile
import shutil
from datetime import datetime, timedelta

import pytest
import numpy as np
from PIL import Image

from app.services.data_distribution import (
    DataDistributor,
    DistributionStrategy,
    BatchAssignment,
    WorkerAssignment,
    AssignmentStatus
)
from app.services.batch_storage import (
    BatchManager,
    LocalBatchStorage,
    BatchMetadata
)
from app.services.dataset_loader import DataSample


@pytest.fixture
def temp_storage_path():
    """Create temporary storage directory."""
    temp_dir = tempfile.mkdtemp()
    yield temp_dir
    shutil.rmtree(temp_dir)


@pytest.fixture
def batch_manager(temp_storage_path):
    """Create BatchManager with local storage."""
    storage = LocalBatchStorage(base_path=temp_storage_path)
    return BatchManager(storage_backend=storage)


@pytest.fixture
def sample_batches(batch_manager):
    """Create sample batches for testing."""
    batches_metadata = []
    
    # Create 6 batches across 3 shards (2 batches per shard)
    for shard_id in range(3):
        for batch_idx in range(2):
            # Create sample data
            samples = []
            for i in range(5):
                img = Image.new('RGB', (32, 32), color=(i * 25, 100, 150))
                sample = DataSample(
                    index=shard_id * 10 + batch_idx * 5 + i,
                    data=np.array(img),
                    label=i % 3,
                    metadata={"class_name": f"class_{i % 3}"}
                )
                samples.append(sample)
            
            # Create metadata
            batch_id = f"shard_{shard_id}_batch_{batch_idx}"
            metadata = BatchMetadata(
                batch_id=batch_id,
                shard_id=shard_id,
                batch_index=batch_idx,
                num_samples=len(samples),
                sample_indices=list(range(len(samples))),
                class_distribution={"0": 2, "1": 2, "2": 1},
                size_bytes=0,
                checksum="",
                storage_path="",
                format="pickle",
                created_at=datetime.utcnow().isoformat()
            )
            
            # Save batch
            batch_manager.storage.save_batch(samples, metadata)
            batches_metadata.append(metadata)
    
    return batches_metadata


class TestBatchAssignment:
    """Test BatchAssignment dataclass."""
    
    def test_creation(self):
        """Test creating batch assignment."""
        assignment = BatchAssignment(
            assignment_id="worker1_batch1",
            batch_id="batch1",
            worker_id="worker1",
            shard_id=0,
            batch_index=0,
            status=AssignmentStatus.PENDING,
            assigned_at=datetime.utcnow().isoformat()
        )
        
        assert assignment.batch_id == "batch1"
        assert assignment.worker_id == "worker1"
        assert assignment.status == AssignmentStatus.PENDING
        assert assignment.retry_count == 0
    
    def test_can_retry(self):
        """Test retry logic."""
        assignment = BatchAssignment(
            assignment_id="test",
            batch_id="batch1",
            worker_id="worker1",
            shard_id=0,
            batch_index=0,
            status=AssignmentStatus.FAILED,
            assigned_at=datetime.utcnow().isoformat(),
            retry_count=0,
            max_retries=3
        )
        
        assert assignment.can_retry() is True
        
        assignment.retry_count = 3
        assert assignment.can_retry() is False
    
    def test_serialization(self):
        """Test to_dict and from_dict."""
        assignment = BatchAssignment(
            assignment_id="test",
            batch_id="batch1",
            worker_id="worker1",
            shard_id=0,
            batch_index=0,
            status=AssignmentStatus.COMPLETED,
            assigned_at=datetime.utcnow().isoformat()
        )
        
        data = assignment.to_dict()
        assert data["status"] == "completed"
        
        restored = BatchAssignment.from_dict(data)
        assert restored.status == AssignmentStatus.COMPLETED
        assert restored.batch_id == "batch1"


class TestWorkerAssignment:
    """Test WorkerAssignment dataclass."""
    
    def test_creation(self):
        """Test creating worker assignment."""
        assignment = WorkerAssignment(
            worker_id="worker1",
            shard_id=0,
            assigned_batches=["batch1", "batch2", "batch3"],
            total_samples=15
        )
        
        assert assignment.worker_id == "worker1"
        assert len(assignment.assigned_batches) == 3
        assert assignment.total_samples == 15
    
    def test_progress_calculation(self):
        """Test progress calculation."""
        assignment = WorkerAssignment(
            worker_id="worker1",
            shard_id=0,
            assigned_batches=["batch1", "batch2", "batch3", "batch4"],
            completed_batches=["batch1", "batch2"]
        )
        
        progress = assignment.get_progress()
        assert progress == 0.5  # 2/4
    
    def test_is_complete(self):
        """Test completion check."""
        assignment = WorkerAssignment(
            worker_id="worker1",
            shard_id=0,
            assigned_batches=["batch1", "batch2"],
            completed_batches=["batch1"]
        )
        
        assert assignment.is_complete() is False
        
        assignment.completed_batches.append("batch2")
        assert assignment.is_complete() is True


class TestDataDistributor:
    """Test DataDistributor functionality."""
    
    def test_initialization(self, batch_manager):
        """Test distributor initialization."""
        distributor = DataDistributor(
            batch_manager=batch_manager,
            strategy=DistributionStrategy.SHARD_PER_WORKER
        )
        
        assert distributor.strategy == DistributionStrategy.SHARD_PER_WORKER
        assert len(distributor.assignments) == 0
        assert len(distributor.worker_assignments) == 0
    
    def test_shard_per_worker_assignment(self, batch_manager, sample_batches):
        """Test shard-per-worker distribution strategy."""
        distributor = DataDistributor(
            batch_manager=batch_manager,
            strategy=DistributionStrategy.SHARD_PER_WORKER
        )
        
        worker_ids = ["worker1", "worker2", "worker3"]
        assignments = distributor.assign_batches_to_workers(worker_ids)
        
        # Each worker should get one complete shard
        assert len(assignments) == 3
        
        for worker_id in worker_ids:
            assignment = assignments[worker_id]
            assert len(assignment.assigned_batches) == 2  # 2 batches per shard
            assert assignment.total_samples == 10  # 5 samples per batch * 2
        
        # Verify shard IDs are different
        shard_ids = [a.shard_id for a in assignments.values()]
        assert len(set(shard_ids)) == 3  # 3 unique shards
    
    def test_round_robin_assignment(self, batch_manager, sample_batches):
        """Test round-robin distribution strategy."""
        distributor = DataDistributor(
            batch_manager=batch_manager,
            strategy=DistributionStrategy.ROUND_ROBIN
        )
        
        worker_ids = ["worker1", "worker2"]
        assignments = distributor.assign_batches_to_workers(worker_ids)
        
        # 6 batches distributed to 2 workers = 3 each
        assert len(assignments[" worker1"].assigned_batches) == 3
        assert len(assignments["worker2"].assigned_batches) == 3
    
    def test_load_balanced_assignment(self, batch_manager, sample_batches):
        """Test load-balanced distribution strategy."""
        distributor = DataDistributor(
            batch_manager=batch_manager,
            strategy=DistributionStrategy.LOAD_BALANCED
        )
        
        worker_ids = ["worker1", "worker2", "worker3"]
        assignments = distributor.assign_batches_to_workers(worker_ids)
        
        # Each worker should get 2 batches (6 batches / 3 workers)
        for worker_id in worker_ids:
            assert len(assignments[worker_id].assigned_batches) == 2
            # Samples should be balanced (each batch has 5 samples)
            assert assignments[worker_id].total_samples == 10
    
    def test_get_worker_assignment(self, batch_manager, sample_batches):
        """Test retrieving worker assignment."""
        distributor = DataDistributor(batch_manager=batch_manager)
        
        worker_ids = ["worker1"]
        distributor.assign_batches_to_workers(worker_ids)
        
        assignment = distributor.get_worker_assignment("worker1")
        assert assignment is not None
        assert assignment.worker_id == "worker1"
        
        # Non-existent worker
        assert distributor.get_worker_assignment("worker999") is None
    
    def test_get_batch_assignment(self, batch_manager, sample_batches):
        """Test retrieving batch assignment."""
        distributor = DataDistributor(batch_manager=batch_manager)
        
        worker_ids = ["worker1"]
        distributor.assign_batches_to_workers(worker_ids)
        
        batch_id = "shard_0_batch_0"
        assignment = distributor.get_batch_assignment(batch_id)
        
        assert assignment is not None
        assert assignment.batch_id == batch_id
        assert assignment.worker_id == "worker1"
        assert assignment.status == AssignmentStatus.PENDING


class TestDownloadTracking:
    """Test download status tracking."""
    
    def test_mark_download_started(self, batch_manager, sample_batches):
        """Test marking download as started."""
        distributor = DataDistributor(batch_manager=batch_manager)
        distributor.assign_batches_to_workers(["worker1"])
        
        batch_id = "shard_0_batch_0"
        success = distributor.mark_download_started("worker1", batch_id)
        
        assert success is True
        
        assignment = distributor.get_batch_assignment(batch_id)
        assert assignment.status == AssignmentStatus.DOWNLOADING
    
    def test_mark_download_completed(self, batch_manager, sample_batches):
        """Test marking download as completed."""
        distributor = DataDistributor(batch_manager=batch_manager)
        distributor.assign_batches_to_workers(["worker1"])
        
        batch_id = "shard_0_batch_0"
        distributor.mark_download_started("worker1", batch_id)
        success = distributor.mark_download_completed("worker1", batch_id)
        
        assert success is True
        
        assignment = distributor.get_batch_assignment(batch_id)
        assert assignment.status == AssignmentStatus.COMPLETED
        assert assignment.downloaded_at is not None
        
        # Verify worker assignment updated
        worker_assignment = distributor.get_worker_assignment("worker1")
        assert batch_id in worker_assignment.completed_batches
    
    def test_mark_download_failed(self, batch_manager, sample_batches):
        """Test marking download as failed."""
        distributor = DataDistributor(batch_manager=batch_manager)
        distributor.assign_batches_to_workers(["worker1"])
        
        batch_id = "shard_0_batch_0"
        distributor.mark_download_started("worker1", batch_id)
        
        reason = "Network timeout"
        success = distributor.mark_download_failed("worker1", batch_id, reason)
        
        assert success is True
        
        assignment = distributor.get_batch_assignment(batch_id)
        assert assignment.status == AssignmentStatus.FAILED
        assert assignment.failure_reason == reason
        assert assignment.retry_count == 1
        
        # Verify worker assignment updated
        worker_assignment = distributor.get_worker_assignment("worker1")
        assert batch_id in worker_assignment.failed_batches


class TestReassignment:
    """Test batch reassignment functionality."""
    
    def test_reassign_failed_batch(self, batch_manager, sample_batches):
        """Test reassigning a failed batch."""
        distributor = DataDistributor(batch_manager=batch_manager)
        distributor.assign_batches_to_workers(["worker1", "worker2"])
        
        batch_id = "shard_0_batch_0"
        
        # Mark as failed
        distributor.mark_download_started("worker1", batch_id)
        distributor.mark_download_failed("worker1", batch_id, "Worker crashed")
        
        # Reassign to worker2
        new_assignment = distributor.reassign_failed_batch(batch_id, "worker2")
        
        assert new_assignment is not None
        assert new_assignment.worker_id == "worker2"
        assert new_assignment.batch_id == batch_id
        assert new_assignment.status == AssignmentStatus.PENDING
        assert new_assignment.retry_count == 1
        
        # Old assignment should be marked as reassigned
        old_assignment = distributor.assignments.get("worker1_" + batch_id)
        assert old_assignment.status == AssignmentStatus.REASSIGNED
    
    def test_reassign_max_retries_exceeded(self, batch_manager, sample_batches):
        """Test reassignment fails when max retries exceeded."""
        distributor = DataDistributor(batch_manager=batch_manager)
        distributor.assign_batches_to_workers(["worker1"])
        
        batch_id = "shard_0_batch_0"
        assignment_id = f"worker1_{batch_id}"
        
        # Exceed max retries
        distributor.assignments[assignment_id].retry_count = 3
        distributor.assignments[assignment_id].max_retries = 3
        
        # Try to reassign
        new_assignment = distributor.reassign_failed_batch(batch_id, "worker2")
        
        assert new_assignment is None
    
    def test_auto_reassign_failed_batches(self, batch_manager, sample_batches):
        """Test automatic reassignment of all failed batches."""
        distributor = DataDistributor(batch_manager=batch_manager)
        distributor.assign_batches_to_workers(["worker1"])
        
        # Mark multiple batches as failed
        failed_batches = ["shard_0_batch_0", "shard_0_batch_1"]
        for batch_id in failed_batches:
            distributor.mark_download_started("worker1", batch_id)
            distributor.mark_download_failed("worker1", batch_id, "Worker offline")
        
        # Auto-reassign to new workers
        available_workers = ["worker2", "worker3"]
        new_assignments = distributor.auto_reassign_failed_batches(available_workers)
        
        assert len(new_assignments) == 2
        
        # Verify reassignments
        for assignment in new_assignments:
            assert assignment.worker_id in available_workers
            assert assignment.status == AssignmentStatus.PENDING


class TestDistributionStats:
    """Test distribution statistics."""
    
    def test_get_distribution_stats(self, batch_manager, sample_batches):
        """Test getting distribution statistics."""
        distributor = DataDistributor(batch_manager=batch_manager)
        worker_ids = ["worker1", "worker2", "worker3"]
        distributor.assign_batches_to_workers(worker_ids)
        
        # Complete some downloads
        distributor.mark_download_started("worker1", "shard_0_batch_0")
        distributor.mark_download_completed("worker1", "shard_0_batch_0")
        
        # Fail some downloads
        distributor.mark_download_started("worker2", "shard_1_batch_0")
        distributor.mark_download_failed("worker2", "shard_1_batch_0", "Error")
        
        stats = distributor.get_distribution_stats()
        
        assert stats["total_workers"] == 3
        assert stats["total_assignments"] == 6  # 6 batches total
        assert stats["status_counts"]["completed"] == 1
        assert stats["status_counts"]["failed"] == 1
        assert stats["status_counts"]["pending"] == 4
        
        # Check worker stats
        assert "worker1" in stats["worker_stats"]
        worker1_stats = stats["worker_stats"]["worker1"]
        assert worker1_stats["completed_batches"] == 1
        assert worker1_stats["total_batches"] == 2
        assert worker1_stats["progress"] == 0.5
    
    def test_get_failed_batches(self, batch_manager, sample_batches):
        """Test getting list of failed batches."""
        distributor = DataDistributor(batch_manager=batch_manager)
        distributor.assign_batches_to_workers(["worker1"])
        
        # Mark some as failed
        batch_id = "shard_0_batch_0"
        distributor.mark_download_started("worker1", batch_id)
        distributor.mark_download_failed("worker1", batch_id, "Error")
        
        failed = distributor.get_failed_batches()
        
        assert len(failed) == 1
        assert failed[0].batch_id == batch_id
        assert failed[0].can_retry() is True


class TestErrorHandling:
    """Test error handling scenarios."""
    
    def test_assign_no_workers(self, batch_manager):
        """Test assignment with no workers."""
        distributor = DataDistributor(batch_manager=batch_manager)
        
        with pytest.raises(ValueError, match="No worker IDs provided"):
            distributor.assign_batches_to_workers([])
    
    def test_assign_no_batches(self, batch_manager):
        """Test assignment when no batches available."""
        distributor = DataDistributor(batch_manager=batch_manager)
        
        # No batches in storage
        assignments = distributor.assign_batches_to_workers(["worker1"])
        
        assert assignments == {}
    
    def test_mark_nonexistent_assignment(self, batch_manager):
        """Test marking status for non-existent assignment."""
        distributor = DataDistributor(batch_manager=batch_manager)
        
        success = distributor.mark_download_started("worker1", "nonexistent_batch")
        assert success is False
        
        success = distributor.mark_download_completed("worker1", "nonexistent_batch")
        assert success is False


class TestThreadSafety:
    """Test thread-safe operations."""
    
    def test_concurrent_status_updates(self, batch_manager, sample_batches):
        """Test concurrent status updates are thread-safe."""
        import threading
        
        distributor = DataDistributor(batch_manager=batch_manager)
        distributor.assign_batches_to_workers(["worker1", "worker2"])
        
        def update_status(worker_id, batch_id):
            distributor.mark_download_started(worker_id, batch_id)
            distributor.mark_download_completed(worker_id, batch_id)
        
        # Create threads for concurrent updates
        threads = []
        for i in range(2):
            batch_id = f"shard_{i}_batch_0"
            worker_id = f"worker{i+1}"
            t = threading.Thread(target=update_status, args=(worker_id, batch_id))
            threads.append(t)
        
        # Start all threads
        for t in threads:
            t.start()
        
        # Wait for completion
        for t in threads:
            t.join()
        
        # Verify both updates succeeded
        stats = distributor.get_distribution_stats()
        assert stats["status_counts"]["completed"] >= 2


class TestIntegration:
    """Integration tests with full workflow."""
    
    def test_complete_distribution_workflow(self, batch_manager, sample_batches):
        """Test complete distribution workflow."""
        distributor = DataDistributor(
            batch_manager=batch_manager,
            strategy=DistributionStrategy.SHARD_PER_WORKER
        )
        
        # Step 1: Assign batches
        worker_ids = ["worker1", "worker2", "worker3"]
        assignments = distributor.assign_batches_to_workers(worker_ids)
        
        assert len(assignments) == 3
        
        # Step 2: Workers download batches
        for worker_id in worker_ids:
            worker_assignment = distributor.get_worker_assignment(worker_id)
            
            for batch_id in worker_assignment.assigned_batches:
                # Mark download started
                distributor.mark_download_started(worker_id, batch_id)
                
                # Load batch (simulate download)
                samples, metadata = batch_manager.load_batch(batch_id)
                assert len(samples) == metadata.num_samples
                
                # Mark download completed
                distributor.mark_download_completed(worker_id, batch_id)
        
        # Step 3: Verify all downloads completed
        stats = distributor.get_distribution_stats()
        assert stats["status_counts"]["completed"] == 6
        assert stats["status_counts"]["pending"] == 0
        
        # All workers should be complete
        for worker_id in worker_ids:
            worker_assignment = distributor.get_worker_assignment(worker_id)
            assert worker_assignment.is_complete()
            assert worker_assignment.get_progress() == 1.0
