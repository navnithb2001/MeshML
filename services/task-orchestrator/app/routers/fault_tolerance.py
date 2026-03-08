"""
Fault Tolerance API Router

Provides HTTP endpoints for fault tolerance management:
- Failure detection and recovery
- Circuit breaker management
- Checkpoint operations
- Dead letter queue management
"""

from fastapi import APIRouter, HTTPException, Query, status
from pydantic import BaseModel, Field
from typing import List, Optional, Dict, Any
from datetime import datetime

from app.services.fault_tolerance import (
    FaultToleranceService,
    FailureType,
    RecoveryStrategy,
    CircuitState,
    RetryPolicy,
    CircuitBreakerConfig
)


router = APIRouter(prefix="/fault-tolerance", tags=["fault-tolerance"])

# Dependency injection (will be set by main app)
fault_tolerance_service: Optional[FaultToleranceService] = None


def get_fault_tolerance_service() -> FaultToleranceService:
    """Get fault tolerance service instance"""
    if fault_tolerance_service is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Fault tolerance service not initialized"
        )
    return fault_tolerance_service


# ==================== Request/Response Models ====================

class FailureRecordResponse(BaseModel):
    """Failure record response"""
    failure_id: str
    job_id: str
    worker_id: Optional[str]
    failure_type: str
    error_message: str
    occurred_at: str
    retry_count: int
    max_retries: int
    recovery_strategy: str
    next_retry_at: Optional[str]
    resolved: bool
    resolved_at: Optional[str]
    metadata: Dict[str, Any]


class CircuitBreakerResponse(BaseModel):
    """Circuit breaker status response"""
    resource_id: str
    state: str
    failure_count: int
    success_count: int
    last_failure_time: Optional[str]
    opened_at: Optional[str]


class CheckpointInfoResponse(BaseModel):
    """Checkpoint information response"""
    checkpoint_id: str
    job_id: str
    epoch: int
    step: int
    gcs_path: str
    created_at: str
    model_state_size_mb: float
    optimizer_state_size_mb: float
    metadata: Dict[str, Any]


class RegisterCheckpointRequest(BaseModel):
    """Request to register a checkpoint"""
    job_id: str = Field(..., description="Job ID")
    checkpoint_id: str = Field(..., description="Unique checkpoint ID")
    epoch: int = Field(..., ge=0, description="Training epoch")
    step: int = Field(..., ge=0, description="Training step")
    gcs_path: str = Field(..., description="GCS path to checkpoint files")
    model_state_size_mb: float = Field(..., ge=0, description="Model state size in MB")
    optimizer_state_size_mb: float = Field(..., ge=0, description="Optimizer state size in MB")
    metadata: Optional[Dict[str, Any]] = Field(None, description="Additional metadata")


class RecoverFromFailureRequest(BaseModel):
    """Request to recover from a failure"""
    failure_id: str = Field(..., description="Failure ID to recover from")
    checkpoint_id: Optional[str] = Field(None, description="Optional checkpoint to restore from")


class FaultToleranceStatsResponse(BaseModel):
    """Fault tolerance statistics response"""
    total_failures: int
    resolved_failures: int
    pending_failures: int
    dead_letter_queue_size: int
    failure_by_type: Dict[str, int]
    circuit_breakers_total: int
    circuit_breakers_open: int
    total_checkpoints: int
    timestamp: str


# ==================== Endpoints ====================

@router.post("/failures/detect")
async def detect_failures():
    """
    Manually trigger failure detection.
    
    Scans all workers and jobs for failures:
    - Worker offline/degraded
    - Job timeouts
    - Resource exhaustion
    
    **Returns**: List of detected failures
    """
    service = get_fault_tolerance_service()
    
    failures = await service.detect_failures()
    
    return {
        "detected_failures": len(failures),
        "failures": [
            FailureRecordResponse(
                failure_id=f.failure_id,
                job_id=f.job_id,
                worker_id=f.worker_id,
                failure_type=f.failure_type.value,
                error_message=f.error_message,
                occurred_at=f.occurred_at.isoformat(),
                retry_count=f.retry_count,
                max_retries=f.max_retries,
                recovery_strategy=f.recovery_strategy.value,
                next_retry_at=f.next_retry_at.isoformat() if f.next_retry_at else None,
                resolved=f.resolved,
                resolved_at=f.resolved_at.isoformat() if f.resolved_at else None,
                metadata=f.metadata
            )
            for f in failures
        ]
    }


@router.post("/failures/{failure_id}/recover")
async def recover_from_failure(request: RecoverFromFailureRequest):
    """
    Manually trigger recovery for a specific failure.
    
    **Recovery Strategies**:
    - `immediate_reassign`: Reassign job to different worker
    - `exponential_backoff`: Retry with exponential backoff
    - `circuit_breaker`: Use circuit breaker pattern
    - `checkpoint_recovery`: Restore from checkpoint
    - `degraded_mode`: Continue with reduced resources
    
    **Returns**: Recovery result
    """
    service = get_fault_tolerance_service()
    
    # Get failure record
    failure = service.failure_records.get(request.failure_id)
    if not failure:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Failure {request.failure_id} not found"
        )
    
    # Attempt recovery
    success = await service.recover_from_failure(failure, request.checkpoint_id)
    
    return {
        "failure_id": request.failure_id,
        "job_id": failure.job_id,
        "recovery_success": success,
        "recovery_strategy": failure.recovery_strategy.value,
        "message": "Recovery successful" if success else "Recovery failed"
    }


@router.get("/failures", response_model=List[FailureRecordResponse])
async def list_failures(
    resolved: Optional[bool] = Query(None, description="Filter by resolved status"),
    job_id: Optional[str] = Query(None, description="Filter by job ID"),
    worker_id: Optional[str] = Query(None, description="Filter by worker ID")
):
    """
    List all failure records with optional filters.
    
    **Filters**:
    - `resolved`: Show only resolved or unresolved failures
    - `job_id`: Filter by specific job
    - `worker_id`: Filter by specific worker
    
    **Returns**: List of failure records
    """
    service = get_fault_tolerance_service()
    
    failures = list(service.failure_records.values())
    
    # Apply filters
    if resolved is not None:
        failures = [f for f in failures if f.resolved == resolved]
    
    if job_id:
        failures = [f for f in failures if f.job_id == job_id]
    
    if worker_id:
        failures = [f for f in failures if f.worker_id == worker_id]
    
    return [
        FailureRecordResponse(
            failure_id=f.failure_id,
            job_id=f.job_id,
            worker_id=f.worker_id,
            failure_type=f.failure_type.value,
            error_message=f.error_message,
            occurred_at=f.occurred_at.isoformat(),
            retry_count=f.retry_count,
            max_retries=f.max_retries,
            recovery_strategy=f.recovery_strategy.value,
            next_retry_at=f.next_retry_at.isoformat() if f.next_retry_at else None,
            resolved=f.resolved,
            resolved_at=f.resolved_at.isoformat() if f.resolved_at else None,
            metadata=f.metadata
        )
        for f in failures
    ]


@router.get("/circuit-breakers/{resource_id}", response_model=CircuitBreakerResponse)
async def get_circuit_breaker_status(resource_id: str):
    """
    Get circuit breaker status for a specific resource (worker).
    
    **Circuit States**:
    - `closed`: Normal operation
    - `open`: Failures detected, blocking requests
    - `half_open`: Testing if resource recovered
    
    **Returns**: Circuit breaker status
    """
    service = get_fault_tolerance_service()
    
    status_dict = service.get_circuit_breaker_status(resource_id)
    
    return CircuitBreakerResponse(
        resource_id=status_dict["resource_id"],
        state=status_dict["state"],
        failure_count=status_dict["failure_count"],
        success_count=status_dict["success_count"],
        last_failure_time=status_dict["last_failure_time"],
        opened_at=status_dict["opened_at"]
    )


@router.get("/circuit-breakers", response_model=List[CircuitBreakerResponse])
async def list_circuit_breakers(
    state: Optional[str] = Query(None, description="Filter by state (closed, open, half_open)")
):
    """
    List all circuit breakers.
    
    **Parameters**:
    - `state`: Filter by circuit state
    
    **Returns**: List of circuit breakers
    """
    service = get_fault_tolerance_service()
    
    breakers = service.circuit_breakers.values()
    
    # Apply filter
    if state:
        breakers = [b for b in breakers if b.state.value == state]
    
    return [
        CircuitBreakerResponse(
            resource_id=b.resource_id,
            state=b.state.value,
            failure_count=b.failure_count,
            success_count=b.success_count,
            last_failure_time=b.last_failure_time.isoformat() if b.last_failure_time else None,
            opened_at=b.opened_at.isoformat() if b.opened_at else None
        )
        for b in breakers
    ]


@router.post("/circuit-breakers/{resource_id}/reset")
async def reset_circuit_breaker(resource_id: str):
    """
    Manually reset circuit breaker for a resource.
    
    Forces circuit breaker to CLOSED state, allowing requests to resume.
    Use when you know the resource has recovered.
    
    **Returns**: Confirmation message
    """
    service = get_fault_tolerance_service()
    
    service.reset_circuit_breaker(resource_id)
    
    return {
        "message": f"Circuit breaker reset for {resource_id}",
        "resource_id": resource_id,
        "state": "closed"
    }


@router.post("/checkpoints", response_model=CheckpointInfoResponse, status_code=status.HTTP_201_CREATED)
async def register_checkpoint(request: RegisterCheckpointRequest):
    """
    Register a checkpoint for a job.
    
    Checkpoints are used for recovery in case of worker failures.
    Training jobs should periodically save checkpoints and register them here.
    
    **Returns**: Checkpoint information
    """
    service = get_fault_tolerance_service()
    
    checkpoint = service.register_checkpoint(
        job_id=request.job_id,
        checkpoint_id=request.checkpoint_id,
        epoch=request.epoch,
        step=request.step,
        gcs_path=request.gcs_path,
        model_state_size_mb=request.model_state_size_mb,
        optimizer_state_size_mb=request.optimizer_state_size_mb,
        metadata=request.metadata
    )
    
    return CheckpointInfoResponse(
        checkpoint_id=checkpoint.checkpoint_id,
        job_id=checkpoint.job_id,
        epoch=checkpoint.epoch,
        step=checkpoint.step,
        gcs_path=checkpoint.gcs_path,
        created_at=checkpoint.created_at.isoformat(),
        model_state_size_mb=checkpoint.model_state_size_mb,
        optimizer_state_size_mb=checkpoint.optimizer_state_size_mb,
        metadata=checkpoint.metadata
    )


@router.get("/checkpoints/{job_id}", response_model=List[CheckpointInfoResponse])
async def get_job_checkpoints(job_id: str):
    """
    Get all checkpoints for a job.
    
    **Returns**: List of checkpoints sorted by creation time
    """
    service = get_fault_tolerance_service()
    
    checkpoints = service.get_checkpoints(job_id)
    
    return [
        CheckpointInfoResponse(
            checkpoint_id=cp.checkpoint_id,
            job_id=cp.job_id,
            epoch=cp.epoch,
            step=cp.step,
            gcs_path=cp.gcs_path,
            created_at=cp.created_at.isoformat(),
            model_state_size_mb=cp.model_state_size_mb,
            optimizer_state_size_mb=cp.optimizer_state_size_mb,
            metadata=cp.metadata
        )
        for cp in sorted(checkpoints, key=lambda c: c.created_at, reverse=True)
    ]


@router.get("/checkpoints/{job_id}/latest", response_model=CheckpointInfoResponse)
async def get_latest_checkpoint(job_id: str):
    """
    Get the latest checkpoint for a job.
    
    **Returns**: Latest checkpoint information
    """
    service = get_fault_tolerance_service()
    
    checkpoint = service.get_latest_checkpoint(job_id)
    
    if not checkpoint:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"No checkpoints found for job {job_id}"
        )
    
    return CheckpointInfoResponse(
        checkpoint_id=checkpoint.checkpoint_id,
        job_id=checkpoint.job_id,
        epoch=checkpoint.epoch,
        step=checkpoint.step,
        gcs_path=checkpoint.gcs_path,
        created_at=checkpoint.created_at.isoformat(),
        model_state_size_mb=checkpoint.model_state_size_mb,
        optimizer_state_size_mb=checkpoint.optimizer_state_size_mb,
        metadata=checkpoint.metadata
    )


@router.get("/dead-letter", response_model=List[FailureRecordResponse])
async def get_dead_letter_queue():
    """
    Get all entries in the dead letter queue.
    
    Dead letter queue contains jobs that have exhausted all retry attempts.
    
    **Returns**: List of failed jobs
    """
    service = get_fault_tolerance_service()
    
    failures = service.get_dead_letter_queue()
    
    return [
        FailureRecordResponse(
            failure_id=f.failure_id,
            job_id=f.job_id,
            worker_id=f.worker_id,
            failure_type=f.failure_type.value,
            error_message=f.error_message,
            occurred_at=f.occurred_at.isoformat(),
            retry_count=f.retry_count,
            max_retries=f.max_retries,
            recovery_strategy=f.recovery_strategy.value,
            next_retry_at=f.next_retry_at.isoformat() if f.next_retry_at else None,
            resolved=f.resolved,
            resolved_at=f.resolved_at.isoformat() if f.resolved_at else None,
            metadata=f.metadata
        )
        for f in failures
    ]


@router.post("/dead-letter/{failure_id}/retry")
async def retry_from_dead_letter(failure_id: str):
    """
    Retry a job from the dead letter queue.
    
    Moves the job back to active processing and attempts recovery.
    
    **Returns**: Retry result
    """
    service = get_fault_tolerance_service()
    
    success = service.retry_from_dead_letter(failure_id)
    
    if not success:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Failure {failure_id} not found in dead letter queue"
        )
    
    return {
        "message": f"Job retry initiated from dead letter queue",
        "failure_id": failure_id,
        "success": success
    }


@router.delete("/dead-letter/purge")
async def purge_dead_letter_queue(
    max_age_hours: Optional[int] = Query(None, ge=1, description="Max age in hours (default: 168 = 1 week)")
):
    """
    Purge old entries from dead letter queue.
    
    Removes entries older than the specified age.
    
    **Parameters**:
    - `max_age_hours`: Maximum age in hours (default: 168 = 1 week)
    
    **Returns**: Number of entries purged
    """
    service = get_fault_tolerance_service()
    
    purged = service.purge_dead_letter_queue(max_age_hours)
    
    return {
        "message": f"Purged {purged} entries from dead letter queue",
        "purged_count": purged,
        "max_age_hours": max_age_hours or service.config.dead_letter_max_age_hours
    }


@router.post("/monitoring/start")
async def start_health_monitoring():
    """
    Start automatic health monitoring.
    
    Periodically checks for failures and attempts automatic recovery.
    
    **Returns**: Confirmation message
    """
    service = get_fault_tolerance_service()
    
    await service.start_health_monitoring()
    
    return {
        "message": "Health monitoring started",
        "check_interval_seconds": service.config.health_check_interval_seconds
    }


@router.post("/monitoring/stop")
async def stop_health_monitoring():
    """
    Stop automatic health monitoring.
    
    **Returns**: Confirmation message
    """
    service = get_fault_tolerance_service()
    
    await service.stop_health_monitoring()
    
    return {"message": "Health monitoring stopped"}


@router.post("/retry-scheduler/start")
async def start_retry_scheduler():
    """
    Start automatic retry scheduler.
    
    Schedules retries for failed jobs based on exponential backoff.
    
    **Returns**: Confirmation message
    """
    service = get_fault_tolerance_service()
    
    await service.start_retry_scheduler()
    
    return {"message": "Retry scheduler started"}


@router.post("/retry-scheduler/stop")
async def stop_retry_scheduler():
    """
    Stop automatic retry scheduler.
    
    **Returns**: Confirmation message
    """
    service = get_fault_tolerance_service()
    
    await service.stop_retry_scheduler()
    
    return {"message": "Retry scheduler stopped"}


@router.get("/stats", response_model=FaultToleranceStatsResponse)
async def get_fault_tolerance_stats():
    """
    Get fault tolerance statistics.
    
    **Returns**:
    - Total failures
    - Resolved/pending failures
    - Dead letter queue size
    - Failures by type
    - Circuit breaker statistics
    - Checkpoint count
    """
    service = get_fault_tolerance_service()
    
    stats = service.get_fault_tolerance_stats()
    
    return FaultToleranceStatsResponse(
        total_failures=stats["total_failures"],
        resolved_failures=stats["resolved_failures"],
        pending_failures=stats["pending_failures"],
        dead_letter_queue_size=stats["dead_letter_queue_size"],
        failure_by_type=stats["failure_by_type"],
        circuit_breakers_total=stats["circuit_breakers_total"],
        circuit_breakers_open=stats["circuit_breakers_open"],
        total_checkpoints=stats["total_checkpoints"],
        timestamp=stats["timestamp"]
    )


@router.get("/health")
async def health_check():
    """
    Health check endpoint.
    
    **Returns**: Service status and configuration
    """
    service = get_fault_tolerance_service()
    
    return {
        "status": "healthy",
        "auto_reassignment_enabled": service.config.enable_auto_reassignment,
        "circuit_breaker_enabled": service.config.enable_circuit_breaker,
        "checkpoint_recovery_enabled": service.config.enable_checkpoint_recovery,
        "health_monitoring_active": service.health_check_task is not None,
        "retry_scheduler_active": service.retry_task is not None,
        "max_concurrent_recoveries": service.config.max_concurrent_recoveries
    }
