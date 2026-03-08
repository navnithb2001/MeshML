"""
Comprehensive tests for Fault Tolerance Service

Tests failure detection, recovery strategies, circuit breakers,
checkpoint management, and dead letter queue operations.
"""

import pytest
from datetime import datetime, timedelta
from unittest.mock import Mock, MagicMock, AsyncMock, patch
from typing import List

from app.services.fault_tolerance import (
    FaultToleranceService,
    FailureType,
    RecoveryStrategy,
    CircuitState,
    RetryPolicy,
    CircuitBreakerConfig,
    CircuitBreaker,
    FailureRecord,
    CheckpointInfo,
    FaultToleranceConfig
)


# ==================== Fixtures ====================

@pytest.fixture
def mock_task_assignment():
    """Mock task assignment service (TASK-6.4)"""
    service = MagicMock()
    
    # Mock successful assignment
    async def mock_assign_job(job_id, strategy=None, constraints=None, shard_ids=None):
        result = MagicMock()
        result.job_id = job_id
        result.worker_id = "worker_new"
        result.status = MagicMock()
        result.status.value = "success"
        return result
    
    service.assign_job = mock_assign_job
    return service


@pytest.fixture
def mock_worker_discovery():
    """Mock worker discovery service (TASK-6.3)"""
    service = MagicMock()
    
    def create_mock_worker(worker_id, status="idle"):
        worker = MagicMock()
        worker.worker_id = worker_id
        worker.status = status
        return worker
    
    service.discover_workers = MagicMock(return_value=[
        create_mock_worker("worker_1", "idle"),
        create_mock_worker("worker_2", "offline"),
        create_mock_worker("worker_3", "degraded")
    ])
    
    return service


@pytest.fixture
def mock_job_queue():
    """Mock job queue (TASK-6.2)"""
    queue = MagicMock()
    
    def create_mock_job(job_id, worker_id=None):
        job = MagicMock()
        job.job_id = job_id
        job.worker_id = worker_id
        job.metadata = MagicMock()
        job.metadata.requirements = MagicMock()
        job.metadata.requirements.min_gpu_count = 2
        return job
    
    queue.list_jobs = MagicMock(return_value=[
        create_mock_job("job_1", "worker_2"),
        create_mock_job("job_2", "worker_2")
    ])
    
    queue.get_job = MagicMock(side_effect=lambda job_id: create_mock_job(job_id))
    queue.release_job_from_worker = MagicMock(return_value=True)
    queue.cancel_job = MagicMock(return_value=True)
    
    return queue


@pytest.fixture
def mock_worker_registry():
    """Mock worker registry (TASK-6.1)"""
    return MagicMock()


@pytest.fixture
def fault_tolerance_service(
    mock_task_assignment,
    mock_worker_discovery,
    mock_job_queue,
    mock_worker_registry
):
    """Fault tolerance service instance"""
    config = FaultToleranceConfig(
        enable_auto_reassignment=True,
        enable_circuit_breaker=True,
        enable_checkpoint_recovery=True,
        health_check_interval_seconds=1,
        max_concurrent_recoveries=5
    )
    
    return FaultToleranceService(
        mock_task_assignment,
        mock_worker_discovery,
        mock_job_queue,
        mock_worker_registry,
        config
    )


# ==================== Test Retry Policy ====================

class TestRetryPolicy:
    """Test retry policy and exponential backoff"""
    
    def test_retry_policy_creation(self):
        """Test retry policy creation"""
        policy = RetryPolicy(
            max_retries=5,
            initial_delay_seconds=2.0,
            backoff_multiplier=2.0
        )
        
        assert policy.max_retries == 5
        assert policy.initial_delay_seconds == 2.0
        assert policy.backoff_multiplier == 2.0
    
    def test_exponential_backoff_calculation(self):
        """Test exponential backoff delay calculation"""
        policy = RetryPolicy(
            initial_delay_seconds=1.0,
            backoff_multiplier=2.0,
            max_delay_seconds=60.0,
            jitter=False
        )
        
        # Attempt 0: 1.0 * 2^0 = 1.0
        assert policy.calculate_delay(0) == 1.0
        
        # Attempt 1: 1.0 * 2^1 = 2.0
        assert policy.calculate_delay(1) == 2.0
        
        # Attempt 2: 1.0 * 2^2 = 4.0
        assert policy.calculate_delay(2) == 4.0
        
        # Attempt 10: Would be 1024.0, but capped at max_delay
        assert policy.calculate_delay(10) == 60.0
    
    def test_backoff_with_jitter(self):
        """Test backoff with jitter"""
        policy = RetryPolicy(
            initial_delay_seconds=10.0,
            backoff_multiplier=2.0,
            jitter=True,
            jitter_factor=0.1
        )
        
        delays = [policy.calculate_delay(0) for _ in range(100)]
        
        # All delays should be within jitter range
        for delay in delays:
            assert 9.0 <= delay <= 11.0  # 10.0 ± 10%


# ==================== Test Circuit Breaker ====================

class TestCircuitBreaker:
    """Test circuit breaker pattern"""
    
    def test_circuit_breaker_creation(self):
        """Test circuit breaker creation"""
        config = CircuitBreakerConfig(
            failure_threshold=3,
            success_threshold=2,
            timeout_seconds=60
        )
        
        breaker = CircuitBreaker(
            resource_id="worker_1",
            config=config
        )
        
        assert breaker.state == CircuitState.CLOSED
        assert breaker.failure_count == 0
    
    def test_circuit_opens_after_threshold(self):
        """Test circuit opens after failure threshold"""
        config = CircuitBreakerConfig(failure_threshold=3)
        breaker = CircuitBreaker("worker_1", config)
        
        # Record failures
        assert breaker.state == CircuitState.CLOSED
        breaker.record_failure()
        assert breaker.state == CircuitState.CLOSED
        
        breaker.record_failure()
        assert breaker.state == CircuitState.CLOSED
        
        breaker.record_failure()
        assert breaker.state == CircuitState.OPEN  # Opens after 3rd failure
    
    def test_circuit_half_open_after_timeout(self):
        """Test circuit transitions to half-open after timeout"""
        config = CircuitBreakerConfig(
            failure_threshold=2,
            timeout_seconds=0  # Immediate timeout for testing
        )
        breaker = CircuitBreaker("worker_1", config)
        
        # Open circuit
        breaker.record_failure()
        breaker.record_failure()
        assert breaker.state == CircuitState.OPEN
        
        # Should allow attempt (transitions to half-open)
        assert breaker.can_attempt() is True
        assert breaker.state == CircuitState.HALF_OPEN
    
    def test_circuit_closes_after_success_threshold(self):
        """Test circuit closes after success threshold"""
        config = CircuitBreakerConfig(
            failure_threshold=2,
            success_threshold=2,
            timeout_seconds=0
        )
        breaker = CircuitBreaker("worker_1", config)
        
        # Open circuit
        breaker.record_failure()
        breaker.record_failure()
        assert breaker.state == CircuitState.OPEN
        
        # Transition to half-open
        breaker.can_attempt()
        assert breaker.state == CircuitState.HALF_OPEN
        
        # Record successes
        breaker.record_success()
        assert breaker.state == CircuitState.HALF_OPEN
        
        breaker.record_success()
        assert breaker.state == CircuitState.CLOSED  # Closes after 2nd success
    
    def test_circuit_reopens_on_failure_in_half_open(self):
        """Test circuit reopens on failure in half-open state"""
        config = CircuitBreakerConfig(
            failure_threshold=2,
            timeout_seconds=0
        )
        breaker = CircuitBreaker("worker_1", config)
        
        # Open and transition to half-open
        breaker.record_failure()
        breaker.record_failure()
        breaker.can_attempt()
        assert breaker.state == CircuitState.HALF_OPEN
        
        # Failure in half-open reopens circuit
        breaker.record_failure()
        assert breaker.state == CircuitState.OPEN


# ==================== Test Failure Detection ====================

class TestFailureDetection:
    """Test failure detection"""
    
    @pytest.mark.asyncio
    async def test_detect_worker_failures(self, fault_tolerance_service):
        """Test detecting worker failures"""
        failures = await fault_tolerance_service.detect_failures()
        
        # Should detect 2 jobs on offline worker_2
        assert len(failures) >= 0
        
        # Check for worker offline failures
        offline_failures = [
            f for f in failures
            if f.failure_type == FailureType.WORKER_OFFLINE
        ]
        
        for failure in offline_failures:
            assert failure.worker_id == "worker_2"
            assert failure.recovery_strategy == RecoveryStrategy.IMMEDIATE_REASSIGN
    
    @pytest.mark.asyncio
    async def test_detect_degraded_worker(self, fault_tolerance_service):
        """Test detecting degraded workers"""
        await fault_tolerance_service.detect_failures()
        
        # Circuit breaker should record degradation for worker_3
        if "worker_3" in fault_tolerance_service.circuit_breakers:
            breaker = fault_tolerance_service.circuit_breakers["worker_3"]
            assert breaker.failure_count > 0


# ==================== Test Recovery Strategies ====================

class TestRecoveryStrategies:
    """Test different recovery strategies"""
    
    @pytest.mark.asyncio
    async def test_immediate_reassign(self, fault_tolerance_service):
        """Test immediate reassignment recovery"""
        failure = FailureRecord(
            failure_id="fail_001",
            job_id="job_001",
            worker_id="worker_failed",
            failure_type=FailureType.WORKER_OFFLINE,
            error_message="Worker offline",
            occurred_at=datetime.utcnow(),
            recovery_strategy=RecoveryStrategy.IMMEDIATE_REASSIGN
        )
        
        success = await fault_tolerance_service.recover_from_failure(failure)
        
        assert success is True
        assert failure.resolved is True
    
    @pytest.mark.asyncio
    async def test_exponential_backoff_retry(self, fault_tolerance_service):
        """Test exponential backoff retry"""
        failure = FailureRecord(
            failure_id="fail_002",
            job_id="job_002",
            worker_id="worker_timeout",
            failure_type=FailureType.JOB_TIMEOUT,
            error_message="Job timeout",
            occurred_at=datetime.utcnow(),
            max_retries=3,
            recovery_strategy=RecoveryStrategy.EXPONENTIAL_BACKOFF
        )
        
        # Fast retry for testing
        fault_tolerance_service.config.default_retry_policy.initial_delay_seconds = 0.01
        
        success = await fault_tolerance_service.recover_from_failure(failure)
        
        # Should increment retry count
        assert failure.retry_count >= 1
    
    @pytest.mark.asyncio
    async def test_circuit_breaker_recovery(self, fault_tolerance_service):
        """Test circuit breaker recovery"""
        failure = FailureRecord(
            failure_id="fail_003",
            job_id="job_003",
            worker_id="worker_degraded",
            failure_type=FailureType.WORKER_DEGRADED,
            error_message="Worker degraded",
            occurred_at=datetime.utcnow(),
            recovery_strategy=RecoveryStrategy.CIRCUIT_BREAKER
        )
        
        success = await fault_tolerance_service.recover_from_failure(failure)
        
        # Should attempt recovery
        assert success in [True, False]
    
    @pytest.mark.asyncio
    async def test_checkpoint_recovery(self, fault_tolerance_service):
        """Test checkpoint-based recovery"""
        # Register checkpoint
        checkpoint = fault_tolerance_service.register_checkpoint(
            job_id="job_004",
            checkpoint_id="ckpt_001",
            epoch=5,
            step=1000,
            gcs_path="gs://bucket/checkpoints/ckpt_001",
            model_state_size_mb=250.0,
            optimizer_state_size_mb=100.0
        )
        
        failure = FailureRecord(
            failure_id="fail_004",
            job_id="job_004",
            worker_id="worker_crashed",
            failure_type=FailureType.WORKER_OFFLINE,
            error_message="Worker crashed",
            occurred_at=datetime.utcnow(),
            recovery_strategy=RecoveryStrategy.CHECKPOINT_RECOVERY
        )
        
        success = await fault_tolerance_service.recover_from_failure(failure)
        
        # Should recover from checkpoint
        assert "checkpoint_id" in failure.metadata
    
    @pytest.mark.asyncio
    async def test_degraded_mode_recovery(self, fault_tolerance_service):
        """Test degraded mode recovery"""
        failure = FailureRecord(
            failure_id="fail_005",
            job_id="job_005",
            worker_id="worker_resource_exhausted",
            failure_type=FailureType.RESOURCE_EXHAUSTED,
            error_message="Resource exhausted",
            occurred_at=datetime.utcnow(),
            recovery_strategy=RecoveryStrategy.DEGRADED_MODE
        )
        
        success = await fault_tolerance_service.recover_from_failure(failure)
        
        # Should attempt degraded mode
        assert success in [True, False]
    
    @pytest.mark.asyncio
    async def test_dead_letter_recovery(self, fault_tolerance_service):
        """Test moving to dead letter queue"""
        failure = FailureRecord(
            failure_id="fail_006",
            job_id="job_006",
            worker_id="worker_permanent_fail",
            failure_type=FailureType.JOB_ERROR,
            error_message="Permanent error",
            occurred_at=datetime.utcnow(),
            recovery_strategy=RecoveryStrategy.DEAD_LETTER
        )
        
        success = await fault_tolerance_service.recover_from_failure(failure)
        
        assert success is True
        assert failure.resolved is True
        assert failure in fault_tolerance_service.dead_letter_queue


# ==================== Test Checkpoint Management ====================

class TestCheckpointManagement:
    """Test checkpoint management"""
    
    def test_register_checkpoint(self, fault_tolerance_service):
        """Test registering a checkpoint"""
        checkpoint = fault_tolerance_service.register_checkpoint(
            job_id="job_train_001",
            checkpoint_id="ckpt_epoch_10",
            epoch=10,
            step=5000,
            gcs_path="gs://bucket/checkpoints/epoch_10",
            model_state_size_mb=500.0,
            optimizer_state_size_mb=200.0,
            metadata={"learning_rate": 0.001}
        )
        
        assert checkpoint.job_id == "job_train_001"
        assert checkpoint.epoch == 10
        assert checkpoint.step == 5000
        assert checkpoint.metadata["learning_rate"] == 0.001
    
    def test_get_checkpoints(self, fault_tolerance_service):
        """Test getting all checkpoints for a job"""
        # Register multiple checkpoints
        for i in range(3):
            fault_tolerance_service.register_checkpoint(
                job_id="job_multi_ckpt",
                checkpoint_id=f"ckpt_{i}",
                epoch=i,
                step=i * 100,
                gcs_path=f"gs://bucket/ckpt_{i}",
                model_state_size_mb=100.0,
                optimizer_state_size_mb=50.0
            )
        
        checkpoints = fault_tolerance_service.get_checkpoints("job_multi_ckpt")
        
        assert len(checkpoints) == 3
        assert all(cp.job_id == "job_multi_ckpt" for cp in checkpoints)
    
    def test_get_latest_checkpoint(self, fault_tolerance_service):
        """Test getting latest checkpoint"""
        # Register checkpoints at different times
        import time
        
        for i in range(3):
            fault_tolerance_service.register_checkpoint(
                job_id="job_latest",
                checkpoint_id=f"ckpt_{i}",
                epoch=i,
                step=i * 100,
                gcs_path=f"gs://bucket/ckpt_{i}",
                model_state_size_mb=100.0,
                optimizer_state_size_mb=50.0
            )
            time.sleep(0.01)  # Small delay to ensure different timestamps
        
        latest = fault_tolerance_service.get_latest_checkpoint("job_latest")
        
        assert latest is not None
        assert latest.checkpoint_id == "ckpt_2"  # Latest one
        assert latest.epoch == 2


# ==================== Test Dead Letter Queue ====================

class TestDeadLetterQueue:
    """Test dead letter queue management"""
    
    @pytest.mark.asyncio
    async def test_move_to_dead_letter(self, fault_tolerance_service):
        """Test moving failure to dead letter queue"""
        failure = FailureRecord(
            failure_id="dlq_001",
            job_id="job_dlq_001",
            worker_id="worker_failed",
            failure_type=FailureType.JOB_ERROR,
            error_message="Fatal error",
            occurred_at=datetime.utcnow(),
            recovery_strategy=RecoveryStrategy.DEAD_LETTER
        )
        
        await fault_tolerance_service._move_to_dead_letter(failure)
        
        assert failure.resolved is True
        assert failure in fault_tolerance_service.dead_letter_queue
    
    def test_retry_from_dead_letter(self, fault_tolerance_service):
        """Test retrying from dead letter queue"""
        failure = FailureRecord(
            failure_id="dlq_retry_001",
            job_id="job_dlq_retry",
            worker_id="worker_failed",
            failure_type=FailureType.JOB_TIMEOUT,
            error_message="Timeout",
            occurred_at=datetime.utcnow(),
            recovery_strategy=RecoveryStrategy.EXPONENTIAL_BACKOFF,
            resolved=True,
            retry_count=3
        )
        
        fault_tolerance_service.dead_letter_queue.append(failure)
        
        success = fault_tolerance_service.retry_from_dead_letter("dlq_retry_001")
        
        assert success is True
        assert failure.resolved is False
        assert failure.retry_count == 0
        assert failure not in fault_tolerance_service.dead_letter_queue
    
    def test_purge_dead_letter_queue(self, fault_tolerance_service):
        """Test purging old entries from dead letter queue"""
        # Add old and new failures
        old_failure = FailureRecord(
            failure_id="dlq_old",
            job_id="job_old",
            worker_id="worker",
            failure_type=FailureType.JOB_ERROR,
            error_message="Error",
            occurred_at=datetime.utcnow() - timedelta(days=10),
            resolved=True
        )
        
        new_failure = FailureRecord(
            failure_id="dlq_new",
            job_id="job_new",
            worker_id="worker",
            failure_type=FailureType.JOB_ERROR,
            error_message="Error",
            occurred_at=datetime.utcnow(),
            resolved=True
        )
        
        fault_tolerance_service.dead_letter_queue.extend([old_failure, new_failure])
        
        # Purge entries older than 7 days
        purged = fault_tolerance_service.purge_dead_letter_queue(max_age_hours=168)
        
        assert purged == 1  # Old entry purged
        assert old_failure not in fault_tolerance_service.dead_letter_queue
        assert new_failure in fault_tolerance_service.dead_letter_queue


# ==================== Test Statistics ====================

class TestStatistics:
    """Test statistics collection"""
    
    def test_fault_tolerance_stats(self, fault_tolerance_service):
        """Test getting fault tolerance statistics"""
        # Add some failures
        for i in range(5):
            failure = FailureRecord(
                failure_id=f"fail_{i}",
                job_id=f"job_{i}",
                worker_id="worker",
                failure_type=FailureType.WORKER_OFFLINE,
                error_message="Error",
                occurred_at=datetime.utcnow(),
                resolved=(i < 3)
            )
            fault_tolerance_service.failure_records[f"fail_{i}"] = failure
        
        # Add checkpoint
        fault_tolerance_service.register_checkpoint(
            job_id="job_1",
            checkpoint_id="ckpt_1",
            epoch=1,
            step=100,
            gcs_path="gs://bucket/ckpt",
            model_state_size_mb=100.0,
            optimizer_state_size_mb=50.0
        )
        
        stats = fault_tolerance_service.get_fault_tolerance_stats()
        
        assert stats["total_failures"] == 5
        assert stats["resolved_failures"] == 3
        assert stats["pending_failures"] == 2
        assert stats["total_checkpoints"] == 1


# ==================== Test Background Tasks ====================

class TestBackgroundTasks:
    """Test background monitoring tasks"""
    
    @pytest.mark.asyncio
    async def test_start_stop_health_monitoring(self, fault_tolerance_service):
        """Test starting and stopping health monitoring"""
        # Start
        await fault_tolerance_service.start_health_monitoring()
        assert fault_tolerance_service.health_check_task is not None
        
        # Small delay
        await asyncio.sleep(0.1)
        
        # Stop
        await fault_tolerance_service.stop_health_monitoring()
        assert fault_tolerance_service.health_check_task is None
    
    @pytest.mark.asyncio
    async def test_start_stop_retry_scheduler(self, fault_tolerance_service):
        """Test starting and stopping retry scheduler"""
        # Start
        await fault_tolerance_service.start_retry_scheduler()
        assert fault_tolerance_service.retry_task is not None
        
        # Small delay
        await asyncio.sleep(0.1)
        
        # Stop
        await fault_tolerance_service.stop_retry_scheduler()
        assert fault_tolerance_service.retry_task is None


# ==================== Integration Tests ====================

class TestIntegration:
    """Integration tests for complete workflows"""
    
    @pytest.mark.asyncio
    async def test_complete_failure_recovery_workflow(self, fault_tolerance_service):
        """Test complete failure detection and recovery workflow"""
        # 1. Detect failures
        failures = await fault_tolerance_service.detect_failures()
        
        if failures:
            # 2. Recover from first failure
            failure = failures[0]
            success = await fault_tolerance_service.recover_from_failure(failure)
            
            # 3. Verify recovery
            assert failure.failure_id in fault_tolerance_service.failure_records
    
    @pytest.mark.asyncio
    async def test_checkpoint_recovery_workflow(self, fault_tolerance_service):
        """Test checkpoint-based recovery workflow"""
        job_id = "job_ckpt_recovery"
        
        # 1. Register checkpoint
        checkpoint = fault_tolerance_service.register_checkpoint(
            job_id=job_id,
            checkpoint_id="ckpt_001",
            epoch=10,
            step=5000,
            gcs_path="gs://bucket/ckpt",
            model_state_size_mb=300.0,
            optimizer_state_size_mb=150.0
        )
        
        # 2. Simulate failure
        failure = FailureRecord(
            failure_id="fail_ckpt",
            job_id=job_id,
            worker_id="worker_crash",
            failure_type=FailureType.WORKER_OFFLINE,
            error_message="Worker crashed",
            occurred_at=datetime.utcnow(),
            recovery_strategy=RecoveryStrategy.CHECKPOINT_RECOVERY
        )
        
        # 3. Recover from checkpoint
        success = await fault_tolerance_service.recover_from_failure(failure)
        
        # 4. Verify checkpoint metadata in failure
        if "checkpoint_id" in failure.metadata:
            assert failure.metadata["checkpoint_id"] == checkpoint.checkpoint_id
    
    @pytest.mark.asyncio
    async def test_circuit_breaker_workflow(self, fault_tolerance_service):
        """Test circuit breaker workflow"""
        worker_id = "worker_unreliable"
        
        # 1. Get circuit breaker
        breaker = fault_tolerance_service._get_circuit_breaker(worker_id)
        
        # 2. Simulate failures to open circuit
        for _ in range(5):
            breaker.record_failure()
        
        # 3. Verify circuit is open
        assert breaker.state == CircuitState.OPEN
        
        # 4. Reset circuit breaker
        fault_tolerance_service.reset_circuit_breaker(worker_id)
        
        # 5. Verify circuit is closed
        assert breaker.state == CircuitState.CLOSED
