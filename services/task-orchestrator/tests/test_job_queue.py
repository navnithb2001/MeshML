"""
Comprehensive tests for Job Queue Management Service

Tests job submission, state transitions, priority scheduling,
validation integration, and error handling.
"""

import pytest
import json
import time
from datetime import datetime, timedelta
from typing import Dict, Any
from unittest.mock import Mock, MagicMock

from app.services.job_queue import (
    JobQueue,
    JobInfo,
    JobMetadata,
    JobRequirements,
    JobStatus,
    JobPriority
)


# ==================== Fixtures ====================

@pytest.fixture
def mock_redis():
    """Mock Redis client"""
    redis = MagicMock()
    
    # In-memory storage for testing
    redis._data = {}
    redis._sets = {}
    redis._zsets = {}
    redis._lists = {}
    
    # Mock Redis methods
    def mock_set(key, value):
        redis._data[key] = value
        return True
    
    def mock_get(key):
        return redis._data.get(key)
    
    def mock_sadd(key, *values):
        if key not in redis._sets:
            redis._sets[key] = set()
        redis._sets[key].update(values)
        return len(values)
    
    def mock_srem(key, *values):
        if key in redis._sets:
            redis._sets[key].discard(*values)
        return 1
    
    def mock_smembers(key):
        return redis._sets.get(key, set())
    
    def mock_scard(key):
        return len(redis._sets.get(key, set()))
    
    def mock_zadd(key, mapping):
        if key not in redis._zsets:
            redis._zsets[key] = {}
        redis._zsets[key].update(mapping)
        return len(mapping)
    
    def mock_zrem(key, *members):
        if key in redis._zsets:
            for member in members:
                redis._zsets[key].pop(member, None)
        return 1
    
    def mock_zrange(key, start, end):
        if key not in redis._zsets:
            return []
        items = sorted(redis._zsets[key].items(), key=lambda x: x[1])
        return [k for k, v in items[start:end+1]]
    
    def mock_zcard(key):
        return len(redis._zsets.get(key, {}))
    
    def mock_lpush(key, *values):
        if key not in redis._lists:
            redis._lists[key] = []
        redis._lists[key].extend(reversed(values))
        return len(redis._lists[key])
    
    def mock_llen(key):
        return len(redis._lists.get(key, []))
    
    def mock_ping():
        return True
    
    redis.set = mock_set
    redis.get = mock_get
    redis.sadd = mock_sadd
    redis.srem = mock_srem
    redis.smembers = mock_smembers
    redis.scard = mock_scard
    redis.zadd = mock_zadd
    redis.zrem = mock_zrem
    redis.zrange = mock_zrange
    redis.zcard = mock_zcard
    redis.lpush = mock_lpush
    redis.llen = mock_llen
    redis.ping = mock_ping
    
    return redis


@pytest.fixture
def job_queue(mock_redis):
    """Job queue instance with mock Redis"""
    return JobQueue(mock_redis)


@pytest.fixture
def sample_metadata():
    """Sample job metadata"""
    return JobMetadata(
        job_id="job_001",
        group_id="research_team",
        model_id="resnet18",
        dataset_id="cifar10",
        user_id="user_123",
        batch_size=32,
        num_epochs=10,
        learning_rate=0.001,
        optimizer="adam",
        requirements=JobRequirements(
            min_gpu_count=2,
            min_gpu_memory_gb=16.0,
            min_cpu_count=8,
            min_ram_gb=32.0,
            requires_cuda=True
        ),
        tags={"experiment": "baseline"},
        description="Baseline training run"
    )


# ==================== Test JobRequirements ====================

class TestJobRequirements:
    """Test JobRequirements dataclass"""
    
    def test_requirements_creation(self):
        """Test requirements creation with defaults"""
        req = JobRequirements()
        assert req.min_gpu_count == 0
        assert req.min_cpu_count == 1
        assert req.min_ram_gb == 1.0
        assert req.requires_cuda is False
    
    def test_requirements_serialization(self):
        """Test requirements to_dict and from_dict"""
        req = JobRequirements(
            min_gpu_count=4,
            min_gpu_memory_gb=24.0,
            requires_cuda=True,
            max_execution_time_seconds=7200
        )
        
        data = req.to_dict()
        assert data["min_gpu_count"] == 4
        assert data["min_gpu_memory_gb"] == 24.0
        
        req2 = JobRequirements.from_dict(data)
        assert req2.min_gpu_count == req.min_gpu_count
        assert req2.requires_cuda == req.requires_cuda


# ==================== Test JobMetadata ====================

class TestJobMetadata:
    """Test JobMetadata dataclass"""
    
    def test_metadata_creation(self, sample_metadata):
        """Test metadata creation"""
        assert sample_metadata.job_id == "job_001"
        assert sample_metadata.group_id == "research_team"
        assert sample_metadata.batch_size == 32
        assert sample_metadata.requirements.min_gpu_count == 2
    
    def test_metadata_serialization(self, sample_metadata):
        """Test metadata to_dict and from_dict"""
        data = sample_metadata.to_dict()
        assert data["job_id"] == "job_001"
        assert isinstance(data["requirements"], dict)
        assert data["requirements"]["min_gpu_count"] == 2
        
        meta2 = JobMetadata.from_dict(data)
        assert meta2.job_id == sample_metadata.job_id
        assert meta2.requirements.min_gpu_count == sample_metadata.requirements.min_gpu_count


# ==================== Test JobInfo ====================

class TestJobInfo:
    """Test JobInfo dataclass"""
    
    def test_job_info_creation(self, sample_metadata):
        """Test job info creation"""
        now = datetime.utcnow().isoformat()
        
        job_info = JobInfo(
            job_id="job_001",
            metadata=sample_metadata,
            status=JobStatus.PENDING,
            priority=JobPriority.HIGH,
            created_at=now,
            updated_at=now
        )
        
        assert job_info.job_id == "job_001"
        assert job_info.status == JobStatus.PENDING
        assert job_info.priority == JobPriority.HIGH
        assert job_info.retry_count == 0
    
    def test_is_terminal_state(self, sample_metadata):
        """Test terminal state detection"""
        now = datetime.utcnow().isoformat()
        
        # Non-terminal states
        for status in [JobStatus.PENDING, JobStatus.WAITING, JobStatus.RUNNING]:
            job = JobInfo(
                job_id="test",
                metadata=sample_metadata,
                status=status,
                priority=JobPriority.MEDIUM,
                created_at=now,
                updated_at=now
            )
            assert not job.is_terminal_state()
        
        # Terminal states
        for status in [JobStatus.COMPLETED, JobStatus.FAILED, JobStatus.CANCELLED, JobStatus.TIMEOUT]:
            job = JobInfo(
                job_id="test",
                metadata=sample_metadata,
                status=status,
                priority=JobPriority.MEDIUM,
                created_at=now,
                updated_at=now
            )
            assert job.is_terminal_state()
    
    def test_can_retry(self, sample_metadata):
        """Test retry eligibility"""
        now = datetime.utcnow().isoformat()
        
        # Can retry (retry_count < max_retries)
        job = JobInfo(
            job_id="test",
            metadata=sample_metadata,
            status=JobStatus.FAILED,
            priority=JobPriority.MEDIUM,
            created_at=now,
            updated_at=now,
            retry_count=1,
            max_retries=3
        )
        assert job.can_retry()
        
        # Cannot retry (max retries reached)
        job.retry_count = 3
        assert not job.can_retry()
        
        # Cannot retry (not in FAILED status)
        job.status = JobStatus.COMPLETED
        assert not job.can_retry()
    
    def test_execution_time_calculation(self, sample_metadata):
        """Test execution time calculation"""
        now = datetime.utcnow()
        
        job = JobInfo(
            job_id="test",
            metadata=sample_metadata,
            status=JobStatus.RUNNING,
            priority=JobPriority.MEDIUM,
            created_at=now.isoformat(),
            updated_at=now.isoformat(),
            started_at=(now - timedelta(seconds=300)).isoformat()
        )
        
        exec_time = job.get_execution_time_seconds()
        assert exec_time is not None
        assert exec_time >= 299 and exec_time <= 301  # ~300 seconds
        
        # No execution time if not started
        job.started_at = None
        assert job.get_execution_time_seconds() is None
    
    def test_job_info_serialization(self, sample_metadata):
        """Test job info serialization"""
        now = datetime.utcnow().isoformat()
        
        job = JobInfo(
            job_id="job_001",
            metadata=sample_metadata,
            status=JobStatus.RUNNING,
            priority=JobPriority.HIGH,
            created_at=now,
            updated_at=now,
            assigned_worker_id="worker_001",
            assigned_shard_ids=[0, 1, 2]
        )
        
        data = job.to_dict()
        assert data["job_id"] == "job_001"
        assert data["status"] == "running"
        assert data["priority"] == 2  # HIGH = 2
        assert data["assigned_worker_id"] == "worker_001"
        
        job2 = JobInfo.from_dict(data)
        assert job2.job_id == job.job_id
        assert job2.status == job.status
        assert job2.priority == job.priority


# ==================== Test Job Submission ====================

class TestJobSubmission:
    """Test job submission"""
    
    def test_submit_job(self, job_queue, sample_metadata):
        """Test basic job submission"""
        job_info = job_queue.submit_job(sample_metadata, JobPriority.HIGH)
        
        assert job_info.job_id == sample_metadata.job_id
        assert job_info.status == JobStatus.PENDING
        assert job_info.priority == JobPriority.HIGH
        assert job_info.metadata.job_id == sample_metadata.job_id
    
    def test_submit_job_creates_indices(self, job_queue, sample_metadata):
        """Test job submission creates proper indices"""
        job_queue.submit_job(sample_metadata, JobPriority.MEDIUM)
        
        # Check validation pending set
        assert sample_metadata.job_id in job_queue.redis.smembers(job_queue.VALIDATION_PENDING_KEY)
        
        # Check status index
        status_key = job_queue.STATUS_KEY.format(status=JobStatus.PENDING.value)
        assert sample_metadata.job_id in job_queue.redis.smembers(status_key)
        
        # Check group index
        group_key = job_queue.GROUP_KEY.format(group_id=sample_metadata.group_id)
        assert sample_metadata.job_id in job_queue.redis.smembers(group_key)
        
        # Check priority queue
        queue_key = job_queue.QUEUE_KEY.format(priority=JobPriority.MEDIUM.value)
        assert sample_metadata.job_id in job_queue.redis.zrange(queue_key, 0, -1)
    
    def test_submit_multiple_jobs_with_priorities(self, job_queue):
        """Test submitting multiple jobs with different priorities"""
        jobs = []
        for i, priority in enumerate([JobPriority.LOW, JobPriority.MEDIUM, JobPriority.HIGH]):
            meta = JobMetadata(
                job_id=f"job_{i}",
                group_id="team",
                model_id="model",
                dataset_id="dataset",
                user_id="user"
            )
            job = job_queue.submit_job(meta, priority)
            jobs.append(job)
        
        assert len(jobs) == 3
        assert jobs[0].priority == JobPriority.LOW
        assert jobs[2].priority == JobPriority.HIGH


# ==================== Test Job State Transitions ====================

class TestJobStateTransitions:
    """Test job state machine transitions"""
    
    def test_valid_transition_pending_to_validating(self, job_queue, sample_metadata):
        """Test PENDING → VALIDATING transition"""
        job_info = job_queue.submit_job(sample_metadata, JobPriority.MEDIUM)
        
        success = job_queue.update_job_status(
            sample_metadata.job_id,
            JobStatus.VALIDATING
        )
        assert success
        
        updated_job = job_queue.get_job(sample_metadata.job_id)
        assert updated_job.status == JobStatus.VALIDATING
    
    def test_valid_transition_validating_to_waiting(self, job_queue, sample_metadata):
        """Test VALIDATING → WAITING transition"""
        job_queue.submit_job(sample_metadata, JobPriority.MEDIUM)
        job_queue.update_job_status(sample_metadata.job_id, JobStatus.VALIDATING)
        
        success = job_queue.update_job_status(
            sample_metadata.job_id,
            JobStatus.WAITING
        )
        assert success
        
        updated_job = job_queue.get_job(sample_metadata.job_id)
        assert updated_job.status == JobStatus.WAITING
    
    def test_valid_transition_waiting_to_running(self, job_queue, sample_metadata):
        """Test WAITING → RUNNING transition"""
        job_queue.submit_job(sample_metadata, JobPriority.MEDIUM)
        job_queue.update_job_status(sample_metadata.job_id, JobStatus.VALIDATING)
        job_queue.update_job_status(sample_metadata.job_id, JobStatus.WAITING)
        
        success = job_queue.update_job_status(
            sample_metadata.job_id,
            JobStatus.RUNNING,
            worker_id="worker_001"
        )
        assert success
        
        updated_job = job_queue.get_job(sample_metadata.job_id)
        assert updated_job.status == JobStatus.RUNNING
        assert updated_job.started_at is not None
        assert updated_job.assigned_worker_id == "worker_001"
    
    def test_valid_transition_running_to_completed(self, job_queue, sample_metadata):
        """Test RUNNING → COMPLETED transition"""
        job_queue.submit_job(sample_metadata, JobPriority.MEDIUM)
        job_queue.update_job_status(sample_metadata.job_id, JobStatus.VALIDATING)
        job_queue.update_job_status(sample_metadata.job_id, JobStatus.WAITING)
        job_queue.update_job_status(sample_metadata.job_id, JobStatus.RUNNING)
        
        success = job_queue.update_job_status(
            sample_metadata.job_id,
            JobStatus.COMPLETED
        )
        assert success
        
        updated_job = job_queue.get_job(sample_metadata.job_id)
        assert updated_job.status == JobStatus.COMPLETED
        assert updated_job.completed_at is not None
    
    def test_invalid_transition_completed_to_running(self, job_queue, sample_metadata):
        """Test invalid transition from terminal state"""
        job_queue.submit_job(sample_metadata, JobPriority.MEDIUM)
        job_queue.update_job_status(sample_metadata.job_id, JobStatus.VALIDATING)
        job_queue.update_job_status(sample_metadata.job_id, JobStatus.WAITING)
        job_queue.update_job_status(sample_metadata.job_id, JobStatus.RUNNING)
        job_queue.update_job_status(sample_metadata.job_id, JobStatus.COMPLETED)
        
        # Cannot transition from COMPLETED
        success = job_queue.update_job_status(
            sample_metadata.job_id,
            JobStatus.RUNNING
        )
        assert not success
    
    def test_transition_to_failed_from_any_state(self, job_queue, sample_metadata):
        """Test can transition to FAILED from any state"""
        job_queue.submit_job(sample_metadata, JobPriority.MEDIUM)
        
        success = job_queue.update_job_status(
            sample_metadata.job_id,
            JobStatus.FAILED,
            error_message="Test error"
        )
        assert success
        
        updated_job = job_queue.get_job(sample_metadata.job_id)
        assert updated_job.status == JobStatus.FAILED
        assert updated_job.error_message == "Test error"
    
    def test_retry_transition_failed_to_pending(self, job_queue, sample_metadata):
        """Test retry: FAILED → PENDING transition"""
        job_queue.submit_job(sample_metadata, JobPriority.MEDIUM)
        job_queue.update_job_status(sample_metadata.job_id, JobStatus.FAILED)
        
        success = job_queue.update_job_status(
            sample_metadata.job_id,
            JobStatus.PENDING
        )
        assert success
        
        updated_job = job_queue.get_job(sample_metadata.job_id)
        assert updated_job.status == JobStatus.PENDING


# ==================== Test Job Assignment ====================

class TestJobAssignment:
    """Test job assignment to workers"""
    
    def test_assign_job_to_worker(self, job_queue, sample_metadata):
        """Test assigning job to worker"""
        # Submit and prepare job for assignment
        job_queue.submit_job(sample_metadata, JobPriority.MEDIUM)
        job_queue.update_job_status(sample_metadata.job_id, JobStatus.VALIDATING)
        job_queue.update_job_status(sample_metadata.job_id, JobStatus.WAITING)
        
        success = job_queue.assign_job_to_worker(
            job_id=sample_metadata.job_id,
            worker_id="worker_001",
            shard_ids=[0, 1, 2]
        )
        assert success
        
        job_info = job_queue.get_job(sample_metadata.job_id)
        assert job_info.status == JobStatus.RUNNING
        assert job_info.assigned_worker_id == "worker_001"
        assert job_info.assigned_shard_ids == [0, 1, 2]
        
        # Check worker index
        worker_key = job_queue.WORKER_KEY.format(worker_id="worker_001")
        assert sample_metadata.job_id in job_queue.redis.smembers(worker_key)
    
    def test_cannot_assign_non_waiting_job(self, job_queue, sample_metadata):
        """Test cannot assign job not in WAITING status"""
        job_queue.submit_job(sample_metadata, JobPriority.MEDIUM)
        
        # Try to assign job in PENDING status
        success = job_queue.assign_job_to_worker(
            job_id=sample_metadata.job_id,
            worker_id="worker_001"
        )
        assert not success
    
    def test_release_job_from_worker_with_retry(self, job_queue, sample_metadata):
        """Test releasing job from worker for retry"""
        # Assign job
        job_queue.submit_job(sample_metadata, JobPriority.MEDIUM)
        job_queue.update_job_status(sample_metadata.job_id, JobStatus.VALIDATING)
        job_queue.update_job_status(sample_metadata.job_id, JobStatus.WAITING)
        job_queue.assign_job_to_worker(sample_metadata.job_id, "worker_001", [0])
        
        # Release for retry
        success = job_queue.release_job_from_worker(
            job_id=sample_metadata.job_id,
            worker_id="worker_001",
            reason="worker_failure"
        )
        assert success
        
        job_info = job_queue.get_job(sample_metadata.job_id)
        assert job_info.status == JobStatus.WAITING
        assert job_info.retry_count == 1
        assert job_info.assigned_worker_id is None
        assert "worker_failure" in job_info.error_message
    
    def test_release_job_max_retries_exceeded(self, job_queue, sample_metadata):
        """Test releasing job when max retries exceeded"""
        # Assign job and set retry count to max
        job_queue.submit_job(sample_metadata, JobPriority.MEDIUM)
        job_queue.update_job_status(sample_metadata.job_id, JobStatus.VALIDATING)
        job_queue.update_job_status(sample_metadata.job_id, JobStatus.WAITING)
        job_queue.assign_job_to_worker(sample_metadata.job_id, "worker_001")
        
        # Manually set retry count
        job_info = job_queue.get_job(sample_metadata.job_id)
        job_info.retry_count = 2  # One more will hit max (3)
        job_queue.redis.set(
            job_queue.JOB_KEY.format(job_id=sample_metadata.job_id),
            json.dumps(job_info.to_dict())
        )
        
        # Release should mark as failed
        success = job_queue.release_job_from_worker(
            sample_metadata.job_id,
            "worker_001",
            "worker_failure"
        )
        assert success
        
        job_info = job_queue.get_job(sample_metadata.job_id)
        assert job_info.status == JobStatus.FAILED
        assert job_info.retry_count == 3


# ==================== Test Job Retrieval ====================

class TestJobRetrieval:
    """Test job retrieval and listing"""
    
    def test_get_job_by_id(self, job_queue, sample_metadata):
        """Test retrieving job by ID"""
        job_queue.submit_job(sample_metadata, JobPriority.HIGH)
        
        job_info = job_queue.get_job(sample_metadata.job_id)
        assert job_info is not None
        assert job_info.job_id == sample_metadata.job_id
        assert job_info.priority == JobPriority.HIGH
    
    def test_get_nonexistent_job(self, job_queue):
        """Test retrieving nonexistent job"""
        job_info = job_queue.get_job("nonexistent")
        assert job_info is None
    
    def test_list_jobs_by_status(self, job_queue):
        """Test listing jobs by status"""
        # Create jobs with different statuses
        for i in range(3):
            meta = JobMetadata(
                job_id=f"job_{i}",
                group_id="team",
                model_id="model",
                dataset_id="dataset",
                user_id="user"
            )
            job_queue.submit_job(meta, JobPriority.MEDIUM)
        
        # Update some to different statuses
        job_queue.update_job_status("job_1", JobStatus.VALIDATING)
        job_queue.update_job_status("job_2", JobStatus.VALIDATING)
        job_queue.update_job_status("job_2", JobStatus.WAITING)
        
        # List by status
        pending_jobs = job_queue.list_jobs(status=JobStatus.PENDING)
        assert len(pending_jobs) == 1
        assert pending_jobs[0].job_id == "job_0"
        
        validating_jobs = job_queue.list_jobs(status=JobStatus.VALIDATING)
        assert len(validating_jobs) == 1
        assert validating_jobs[0].job_id == "job_1"
    
    def test_list_jobs_by_group(self, job_queue):
        """Test listing jobs by group ID"""
        # Create jobs in different groups
        for i, group in enumerate(["team_a", "team_b", "team_a"]):
            meta = JobMetadata(
                job_id=f"job_{i}",
                group_id=group,
                model_id="model",
                dataset_id="dataset",
                user_id="user"
            )
            job_queue.submit_job(meta, JobPriority.MEDIUM)
        
        # List by group
        team_a_jobs = job_queue.list_jobs(group_id="team_a")
        assert len(team_a_jobs) == 2
        
        team_b_jobs = job_queue.list_jobs(group_id="team_b")
        assert len(team_b_jobs) == 1
    
    def test_get_next_job_by_priority(self, job_queue):
        """Test getting next job respects priority"""
        # Submit jobs with different priorities
        for i, priority in enumerate([JobPriority.LOW, JobPriority.HIGH, JobPriority.MEDIUM]):
            meta = JobMetadata(
                job_id=f"job_{i}",
                group_id="team",
                model_id="model",
                dataset_id="dataset",
                user_id="user"
            )
            job_queue.submit_job(meta, priority)
            # Move to WAITING status
            job_queue.update_job_status(f"job_{i}", JobStatus.VALIDATING)
            job_queue.update_job_status(f"job_{i}", JobStatus.WAITING)
        
        # Get next job (should be HIGH priority)
        next_job = job_queue.get_next_job()
        assert next_job is not None
        assert next_job.priority == JobPriority.HIGH
        assert next_job.job_id == "job_1"
    
    def test_get_next_job_with_requirements(self, job_queue):
        """Test getting next job with requirement matching"""
        # Job requiring 4 GPUs
        meta_high_req = JobMetadata(
            job_id="gpu_job",
            group_id="team",
            model_id="model",
            dataset_id="dataset",
            user_id="user",
            requirements=JobRequirements(min_gpu_count=4, min_gpu_memory_gb=24.0)
        )
        
        # Job requiring 1 GPU
        meta_low_req = JobMetadata(
            job_id="cpu_job",
            group_id="team",
            model_id="model",
            dataset_id="dataset",
            user_id="user",
            requirements=JobRequirements(min_gpu_count=1, min_gpu_memory_gb=8.0)
        )
        
        job_queue.submit_job(meta_high_req, JobPriority.HIGH)
        job_queue.submit_job(meta_low_req, JobPriority.HIGH)
        
        # Move to WAITING
        for job_id in ["gpu_job", "cpu_job"]:
            job_queue.update_job_status(job_id, JobStatus.VALIDATING)
            job_queue.update_job_status(job_id, JobStatus.WAITING)
        
        # Worker with 2 GPUs (can only handle low requirement job)
        worker_req = JobRequirements(min_gpu_count=2, min_gpu_memory_gb=16.0)
        next_job = job_queue.get_next_job(worker_req)
        
        assert next_job is not None
        assert next_job.job_id == "cpu_job"  # Only this one matches


# ==================== Test Validation Integration ====================

class TestValidationIntegration:
    """Test Phase 4 validation integration"""
    
    def test_mark_validation_passed(self, job_queue, sample_metadata):
        """Test marking validation as passed"""
        job_queue.submit_job(sample_metadata, JobPriority.MEDIUM)
        job_queue.update_job_status(sample_metadata.job_id, JobStatus.VALIDATING)
        
        success = job_queue.mark_validation_complete(
            job_id=sample_metadata.job_id,
            model_validation_passed=True,
            dataset_validation_passed=True
        )
        assert success
        
        job_info = job_queue.get_job(sample_metadata.job_id)
        assert job_info.status == JobStatus.WAITING
        assert job_info.model_validation_status == "passed"
        assert job_info.dataset_validation_status == "passed"
        
        # Should be removed from validation pending
        assert sample_metadata.job_id not in job_queue.redis.smembers(job_queue.VALIDATION_PENDING_KEY)
    
    def test_mark_validation_failed(self, job_queue, sample_metadata):
        """Test marking validation as failed"""
        job_queue.submit_job(sample_metadata, JobPriority.MEDIUM)
        job_queue.update_job_status(sample_metadata.job_id, JobStatus.VALIDATING)
        
        success = job_queue.mark_validation_complete(
            job_id=sample_metadata.job_id,
            model_validation_passed=False,
            dataset_validation_passed=True,
            validation_errors=["Invalid model structure"]
        )
        assert success
        
        job_info = job_queue.get_job(sample_metadata.job_id)
        assert job_info.status == JobStatus.FAILED
        assert job_info.model_validation_status == "failed"
        assert "Invalid model structure" in job_info.validation_errors


# ==================== Test Job Cancellation ====================

class TestJobCancellation:
    """Test job cancellation"""
    
    def test_cancel_pending_job(self, job_queue, sample_metadata):
        """Test cancelling pending job"""
        job_queue.submit_job(sample_metadata, JobPriority.MEDIUM)
        
        success = job_queue.cancel_job(sample_metadata.job_id, "user_requested")
        assert success
        
        job_info = job_queue.get_job(sample_metadata.job_id)
        assert job_info.status == JobStatus.CANCELLED
        assert "user_requested" in job_info.error_message
    
    def test_cancel_running_job(self, job_queue, sample_metadata):
        """Test cancelling running job"""
        job_queue.submit_job(sample_metadata, JobPriority.MEDIUM)
        job_queue.update_job_status(sample_metadata.job_id, JobStatus.VALIDATING)
        job_queue.update_job_status(sample_metadata.job_id, JobStatus.WAITING)
        job_queue.assign_job_to_worker(sample_metadata.job_id, "worker_001")
        
        success = job_queue.cancel_job(sample_metadata.job_id)
        assert success
        
        job_info = job_queue.get_job(sample_metadata.job_id)
        assert job_info.status == JobStatus.CANCELLED
        
        # Should be removed from worker index
        worker_key = job_queue.WORKER_KEY.format(worker_id="worker_001")
        assert sample_metadata.job_id not in job_queue.redis.smembers(worker_key)
    
    def test_cannot_cancel_completed_job(self, job_queue, sample_metadata):
        """Test cannot cancel completed job"""
        job_queue.submit_job(sample_metadata, JobPriority.MEDIUM)
        job_queue.update_job_status(sample_metadata.job_id, JobStatus.VALIDATING)
        job_queue.update_job_status(sample_metadata.job_id, JobStatus.WAITING)
        job_queue.update_job_status(sample_metadata.job_id, JobStatus.RUNNING)
        job_queue.update_job_status(sample_metadata.job_id, JobStatus.COMPLETED)
        
        success = job_queue.cancel_job(sample_metadata.job_id)
        assert not success


# ==================== Test Statistics ====================

class TestQueueStatistics:
    """Test queue statistics"""
    
    def test_get_queue_stats(self, job_queue):
        """Test getting queue statistics"""
        # Create jobs with different statuses
        for i in range(5):
            meta = JobMetadata(
                job_id=f"job_{i}",
                group_id="team",
                model_id="model",
                dataset_id="dataset",
                user_id="user"
            )
            priority = JobPriority.HIGH if i < 2 else JobPriority.MEDIUM
            job_queue.submit_job(meta, priority)
        
        # Update statuses
        job_queue.update_job_status("job_0", JobStatus.VALIDATING)
        job_queue.update_job_status("job_1", JobStatus.VALIDATING)
        job_queue.update_job_status("job_1", JobStatus.WAITING)
        
        stats = job_queue.get_queue_stats()
        
        assert stats["total_jobs"] == 5
        assert stats["by_status"]["pending"] == 3
        assert stats["by_status"]["validating"] == 1
        assert stats["by_status"]["waiting"] == 1
        assert stats["by_priority"]["HIGH"] == 2
        assert stats["by_priority"]["MEDIUM"] == 3


# ==================== Test Cleanup ====================

class TestJobCleanup:
    """Test job cleanup and expiration"""
    
    def test_cleanup_expired_validation(self, job_queue, sample_metadata):
        """Test cleanup of jobs stuck in validation"""
        job_queue.validation_timeout = 1  # 1 second timeout
        
        job_queue.submit_job(sample_metadata, JobPriority.MEDIUM)
        job_queue.update_job_status(sample_metadata.job_id, JobStatus.VALIDATING)
        
        # Wait for timeout
        time.sleep(1.5)
        
        cleaned = job_queue.cleanup_expired_jobs()
        assert cleaned == 1
        
        job_info = job_queue.get_job(sample_metadata.job_id)
        assert job_info.status == JobStatus.FAILED
        assert "timeout" in job_info.error_message.lower()
    
    def test_cleanup_expired_running_job(self, job_queue, sample_metadata):
        """Test cleanup of jobs exceeding execution time"""
        # Set short max execution time
        sample_metadata.requirements.max_execution_time_seconds = 1
        
        job_queue.submit_job(sample_metadata, JobPriority.MEDIUM)
        job_queue.update_job_status(sample_metadata.job_id, JobStatus.VALIDATING)
        job_queue.update_job_status(sample_metadata.job_id, JobStatus.WAITING)
        job_queue.assign_job_to_worker(sample_metadata.job_id, "worker_001")
        
        # Wait for timeout
        time.sleep(1.5)
        
        cleaned = job_queue.cleanup_expired_jobs()
        assert cleaned == 1
        
        job_info = job_queue.get_job(sample_metadata.job_id)
        assert job_info.status == JobStatus.TIMEOUT


# ==================== Test Priority Ordering ====================

class TestPriorityOrdering:
    """Test job priority ordering"""
    
    def test_priority_comparison(self):
        """Test priority enum comparison"""
        assert JobPriority.CRITICAL > JobPriority.HIGH
        assert JobPriority.HIGH > JobPriority.MEDIUM
        assert JobPriority.MEDIUM > JobPriority.LOW
        assert JobPriority.LOW < JobPriority.CRITICAL
    
    def test_fifo_within_priority(self, job_queue):
        """Test FIFO ordering within same priority"""
        # Submit 3 jobs with same priority
        for i in range(3):
            meta = JobMetadata(
                job_id=f"job_{i}",
                group_id="team",
                model_id="model",
                dataset_id="dataset",
                user_id="user"
            )
            job_queue.submit_job(meta, JobPriority.HIGH)
            job_queue.update_job_status(f"job_{i}", JobStatus.VALIDATING)
            job_queue.update_job_status(f"job_{i}", JobStatus.WAITING)
            time.sleep(0.01)  # Small delay to ensure different timestamps
        
        # Should get jobs in submission order
        for i in range(3):
            next_job = job_queue.get_next_job()
            assert next_job.job_id == f"job_{i}"
            job_queue.assign_job_to_worker(next_job.job_id, "worker_001")


# ==================== Integration Tests ====================

class TestIntegration:
    """Integration tests for complete workflows"""
    
    def test_complete_job_lifecycle(self, job_queue, sample_metadata):
        """Test complete job lifecycle from submission to completion"""
        # 1. Submit job
        job_info = job_queue.submit_job(sample_metadata, JobPriority.HIGH)
        assert job_info.status == JobStatus.PENDING
        
        # 2. Start validation
        job_queue.update_job_status(sample_metadata.job_id, JobStatus.VALIDATING)
        
        # 3. Validation passes
        job_queue.mark_validation_complete(
            sample_metadata.job_id,
            model_validation_passed=True,
            dataset_validation_passed=True
        )
        job_info = job_queue.get_job(sample_metadata.job_id)
        assert job_info.status == JobStatus.WAITING
        
        # 4. Assign to worker
        job_queue.assign_job_to_worker(sample_metadata.job_id, "worker_001", [0, 1])
        job_info = job_queue.get_job(sample_metadata.job_id)
        assert job_info.status == JobStatus.RUNNING
        assert job_info.assigned_worker_id == "worker_001"
        
        # 5. Complete job
        job_queue.update_job_status(sample_metadata.job_id, JobStatus.COMPLETED)
        job_info = job_queue.get_job(sample_metadata.job_id)
        assert job_info.status == JobStatus.COMPLETED
        assert job_info.is_terminal_state()
    
    def test_job_retry_workflow(self, job_queue, sample_metadata):
        """Test job retry workflow after worker failure"""
        # Submit and assign job
        job_queue.submit_job(sample_metadata, JobPriority.HIGH)
        job_queue.update_job_status(sample_metadata.job_id, JobStatus.VALIDATING)
        job_queue.mark_validation_complete(sample_metadata.job_id, True, True)
        job_queue.assign_job_to_worker(sample_metadata.job_id, "worker_001")
        
        # Worker fails, release job
        job_queue.release_job_from_worker(sample_metadata.job_id, "worker_001", "worker_crashed")
        
        job_info = job_queue.get_job(sample_metadata.job_id)
        assert job_info.status == JobStatus.WAITING
        assert job_info.retry_count == 1
        assert job_info.assigned_worker_id is None
        
        # Reassign to different worker
        job_queue.assign_job_to_worker(sample_metadata.job_id, "worker_002", [0])
        job_info = job_queue.get_job(sample_metadata.job_id)
        assert job_info.assigned_worker_id == "worker_002"
        assert job_info.status == JobStatus.RUNNING
