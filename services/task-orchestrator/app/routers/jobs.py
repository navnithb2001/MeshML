"""
Job Management API Router

Provides HTTP endpoints for job submission, status tracking, assignment,
and management. Integrates with job queue service and worker registry.
"""

from fastapi import APIRouter, HTTPException, Query, Depends
from pydantic import BaseModel, Field
from typing import List, Optional, Dict, Any
from datetime import datetime
import logging

from ..services.job_queue import (
    JobQueue,
    JobInfo,
    JobMetadata,
    JobRequirements,
    JobStatus,
    JobPriority
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/jobs", tags=["jobs"])

# Dependency injection (to be replaced with actual Redis client)
def get_job_queue() -> JobQueue:
    """Get job queue instance (dependency injection)"""
    # TODO: Replace with actual Redis client from app state
    from redis import Redis
    redis_client = Redis(host="localhost", port=6379, decode_responses=False)
    return JobQueue(redis_client)


# ==================== Pydantic Models ====================

class JobRequirementsRequest(BaseModel):
    """Job resource requirements"""
    min_gpu_count: int = Field(0, ge=0, description="Minimum number of GPUs required")
    min_gpu_memory_gb: float = Field(0.0, ge=0.0, description="Minimum GPU memory in GB")
    min_cpu_count: int = Field(1, ge=1, description="Minimum number of CPU cores")
    min_ram_gb: float = Field(1.0, ge=0.1, description="Minimum RAM in GB")
    requires_cuda: bool = Field(False, description="Requires CUDA support")
    requires_mps: bool = Field(False, description="Requires Apple Metal Performance Shaders")
    max_execution_time_seconds: int = Field(3600, ge=60, description="Maximum execution time in seconds")
    
    class Config:
        json_schema_extra = {
            "example": {
                "min_gpu_count": 2,
                "min_gpu_memory_gb": 16.0,
                "min_cpu_count": 8,
                "min_ram_gb": 32.0,
                "requires_cuda": True,
                "max_execution_time_seconds": 7200
            }
        }


class SubmitJobRequest(BaseModel):
    """Job submission request"""
    job_id: str = Field(..., min_length=1, description="Unique job identifier")
    group_id: str = Field(..., min_length=1, description="Group/team identifier")
    model_id: str = Field(..., min_length=1, description="Model identifier (Phase 4 validated)")
    dataset_id: str = Field(..., min_length=1, description="Dataset identifier (Phase 4 validated)")
    user_id: str = Field(..., min_length=1, description="User identifier")
    
    # Training configuration
    batch_size: int = Field(32, ge=1, description="Training batch size")
    num_epochs: int = Field(10, ge=1, description="Number of training epochs")
    learning_rate: float = Field(0.001, gt=0, description="Learning rate")
    optimizer: str = Field("adam", description="Optimizer type (adam, sgd, etc.)")
    
    # Resource requirements
    requirements: JobRequirementsRequest = Field(default_factory=JobRequirementsRequest)
    
    # Priority
    priority: str = Field("MEDIUM", description="Job priority: LOW, MEDIUM, HIGH, CRITICAL")
    
    # Metadata
    tags: Dict[str, str] = Field(default_factory=dict, description="Custom tags")
    description: str = Field("", description="Job description")
    
    class Config:
        json_schema_extra = {
            "example": {
                "job_id": "job_12345",
                "group_id": "research_team",
                "model_id": "resnet18_custom",
                "dataset_id": "cifar10_subset",
                "user_id": "user_123",
                "batch_size": 64,
                "num_epochs": 50,
                "learning_rate": 0.01,
                "optimizer": "adam",
                "priority": "HIGH",
                "requirements": {
                    "min_gpu_count": 2,
                    "min_gpu_memory_gb": 16.0,
                    "requires_cuda": True
                },
                "tags": {"experiment": "baseline", "version": "v1"},
                "description": "Baseline training run for ResNet-18"
            }
        }


class UpdateJobProgressRequest(BaseModel):
    """Job progress update"""
    progress_percent: float = Field(..., ge=0.0, le=100.0, description="Progress percentage")
    current_epoch: int = Field(..., ge=0, description="Current epoch number")
    current_loss: Optional[float] = Field(None, description="Current training loss")
    current_accuracy: Optional[float] = Field(None, ge=0.0, le=1.0, description="Current accuracy")
    
    class Config:
        json_schema_extra = {
            "example": {
                "progress_percent": 45.5,
                "current_epoch": 23,
                "current_loss": 0.342,
                "current_accuracy": 0.891
            }
        }


class AssignJobRequest(BaseModel):
    """Job assignment to worker"""
    worker_id: str = Field(..., min_length=1, description="Worker identifier")
    shard_ids: List[int] = Field(default_factory=list, description="Assigned data shard IDs")
    
    class Config:
        json_schema_extra = {
            "example": {
                "worker_id": "worker_001",
                "shard_ids": [0, 1, 2]
            }
        }


class ValidationResultRequest(BaseModel):
    """Validation result from Phase 4"""
    model_validation_passed: bool = Field(..., description="Model validation status")
    dataset_validation_passed: bool = Field(..., description="Dataset validation status")
    validation_errors: List[str] = Field(default_factory=list, description="Validation error messages")
    
    class Config:
        json_schema_extra = {
            "example": {
                "model_validation_passed": True,
                "dataset_validation_passed": True,
                "validation_errors": []
            }
        }


class JobResponse(BaseModel):
    """Job information response"""
    job_id: str
    group_id: str
    model_id: str
    dataset_id: str
    user_id: str
    status: str
    priority: str
    
    # Timestamps
    created_at: str
    updated_at: str
    started_at: Optional[str] = None
    completed_at: Optional[str] = None
    
    # Assignment
    assigned_worker_id: Optional[str] = None
    assigned_shard_ids: List[int] = Field(default_factory=list)
    
    # Validation
    model_validation_status: str
    dataset_validation_status: str
    validation_errors: List[str] = Field(default_factory=list)
    
    # Progress
    progress_percent: float
    current_epoch: int
    current_loss: Optional[float] = None
    current_accuracy: Optional[float] = None
    
    # Error handling
    error_message: Optional[str] = None
    retry_count: int
    max_retries: int
    
    # Results
    result_path: Optional[str] = None
    metrics_summary: Dict[str, Any] = Field(default_factory=dict)
    
    # Computed fields
    execution_time_seconds: Optional[float] = None
    is_terminal: bool
    can_retry: bool
    
    @classmethod
    def from_job_info(cls, job_info: JobInfo) -> "JobResponse":
        """Convert JobInfo to response model"""
        return cls(
            job_id=job_info.job_id,
            group_id=job_info.metadata.group_id,
            model_id=job_info.metadata.model_id,
            dataset_id=job_info.metadata.dataset_id,
            user_id=job_info.metadata.user_id,
            status=job_info.status.value,
            priority=job_info.priority.name,
            created_at=job_info.created_at,
            updated_at=job_info.updated_at,
            started_at=job_info.started_at,
            completed_at=job_info.completed_at,
            assigned_worker_id=job_info.assigned_worker_id,
            assigned_shard_ids=job_info.assigned_shard_ids,
            model_validation_status=job_info.model_validation_status,
            dataset_validation_status=job_info.dataset_validation_status,
            validation_errors=job_info.validation_errors,
            progress_percent=job_info.progress_percent,
            current_epoch=job_info.current_epoch,
            current_loss=job_info.current_loss,
            current_accuracy=job_info.current_accuracy,
            error_message=job_info.error_message,
            retry_count=job_info.retry_count,
            max_retries=job_info.max_retries,
            result_path=job_info.result_path,
            metrics_summary=job_info.metrics_summary,
            execution_time_seconds=job_info.get_execution_time_seconds(),
            is_terminal=job_info.is_terminal_state(),
            can_retry=job_info.can_retry()
        )


class QueueStatsResponse(BaseModel):
    """Queue statistics response"""
    total_jobs: int
    by_status: Dict[str, int]
    by_priority: Dict[str, int]
    validation_pending: int
    dead_letter_count: int
    timestamp: str = Field(default_factory=lambda: datetime.utcnow().isoformat())


# ==================== Job Submission Endpoints ====================

@router.post("/submit", response_model=JobResponse, status_code=201)
async def submit_job(
    request: SubmitJobRequest,
    queue: JobQueue = Depends(get_job_queue)
):
    """
    Submit new training job.
    
    The job will be added to the queue with PENDING status.
    It will transition through validation (Phase 4) before being assigned to a worker.
    
    State Flow:
    1. PENDING → VALIDATING (Phase 4 validates model & dataset)
    2. VALIDATING → WAITING (validation passed) or FAILED (validation failed)
    3. WAITING → RUNNING (assigned to worker)
    4. RUNNING → COMPLETED or FAILED
    """
    try:
        # Parse priority
        try:
            priority = JobPriority[request.priority.upper()]
        except KeyError:
            raise HTTPException(
                status_code=400,
                detail=f"Invalid priority: {request.priority}. Must be one of: LOW, MEDIUM, HIGH, CRITICAL"
            )
        
        # Create job metadata
        metadata = JobMetadata(
            job_id=request.job_id,
            group_id=request.group_id,
            model_id=request.model_id,
            dataset_id=request.dataset_id,
            user_id=request.user_id,
            batch_size=request.batch_size,
            num_epochs=request.num_epochs,
            learning_rate=request.learning_rate,
            optimizer=request.optimizer,
            requirements=JobRequirements(**request.requirements.model_dump()),
            tags=request.tags,
            description=request.description
        )
        
        # Submit to queue
        job_info = queue.submit_job(metadata, priority)
        
        logger.info(f"Job {request.job_id} submitted by user {request.user_id}")
        return JobResponse.from_job_info(job_info)
        
    except Exception as e:
        logger.error(f"Failed to submit job {request.job_id}: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to submit job: {str(e)}")


# ==================== Job Status & Retrieval Endpoints ====================

@router.get("/{job_id}", response_model=JobResponse)
async def get_job(
    job_id: str,
    queue: JobQueue = Depends(get_job_queue)
):
    """Get job information by ID"""
    job_info = queue.get_job(job_id)
    if not job_info:
        raise HTTPException(status_code=404, detail=f"Job {job_id} not found")
    
    return JobResponse.from_job_info(job_info)


@router.get("/", response_model=List[JobResponse])
async def list_jobs(
    status: Optional[str] = Query(None, description="Filter by status"),
    group_id: Optional[str] = Query(None, description="Filter by group ID"),
    worker_id: Optional[str] = Query(None, description="Filter by worker ID"),
    limit: int = Query(100, ge=1, le=1000, description="Maximum number of results"),
    queue: JobQueue = Depends(get_job_queue)
):
    """
    List jobs with optional filters.
    
    Query Parameters:
    - status: Filter by job status (pending, waiting, running, completed, failed, etc.)
    - group_id: Filter by group ID
    - worker_id: Filter by assigned worker ID
    - limit: Maximum number of results (default: 100, max: 1000)
    """
    try:
        # Parse status if provided
        status_enum = None
        if status:
            try:
                status_enum = JobStatus(status.lower())
            except ValueError:
                raise HTTPException(
                    status_code=400,
                    detail=f"Invalid status: {status}. Must be one of: {', '.join(s.value for s in JobStatus)}"
                )
        
        jobs = queue.list_jobs(
            status=status_enum,
            group_id=group_id,
            worker_id=worker_id,
            limit=limit
        )
        
        return [JobResponse.from_job_info(job) for job in jobs]
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to list jobs: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to list jobs: {str(e)}")


@router.get("/next/available", response_model=Optional[JobResponse])
async def get_next_job(
    min_gpu_count: int = Query(0, ge=0, description="Worker's GPU count"),
    min_gpu_memory_gb: float = Query(0.0, ge=0.0, description="Worker's GPU memory"),
    min_cpu_count: int = Query(1, ge=1, description="Worker's CPU count"),
    min_ram_gb: float = Query(1.0, ge=0.1, description="Worker's RAM"),
    requires_cuda: bool = Query(False, description="Worker supports CUDA"),
    requires_mps: bool = Query(False, description="Worker supports MPS"),
    queue: JobQueue = Depends(get_job_queue)
):
    """
    Get next available job matching worker requirements.
    
    Returns the highest priority job that the worker can execute.
    Returns null if no matching jobs are available.
    """
    try:
        requirements = JobRequirements(
            min_gpu_count=min_gpu_count,
            min_gpu_memory_gb=min_gpu_memory_gb,
            min_cpu_count=min_cpu_count,
            min_ram_gb=min_ram_gb,
            requires_cuda=requires_cuda,
            requires_mps=requires_mps
        )
        
        job_info = queue.get_next_job(requirements)
        if not job_info:
            return None
        
        return JobResponse.from_job_info(job_info)
        
    except Exception as e:
        logger.error(f"Failed to get next job: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to get next job: {str(e)}")


# ==================== Job Assignment Endpoints ====================

@router.post("/{job_id}/assign", response_model=JobResponse)
async def assign_job(
    job_id: str,
    request: AssignJobRequest,
    queue: JobQueue = Depends(get_job_queue)
):
    """
    Assign job to worker.
    
    Transitions job from WAITING → RUNNING and assigns worker_id and shard_ids.
    """
    success = queue.assign_job_to_worker(
        job_id=job_id,
        worker_id=request.worker_id,
        shard_ids=request.shard_ids
    )
    
    if not success:
        job_info = queue.get_job(job_id)
        if not job_info:
            raise HTTPException(status_code=404, detail=f"Job {job_id} not found")
        raise HTTPException(
            status_code=400,
            detail=f"Cannot assign job {job_id} (current status: {job_info.status.value})"
        )
    
    job_info = queue.get_job(job_id)
    return JobResponse.from_job_info(job_info)


@router.post("/{job_id}/release", response_model=JobResponse)
async def release_job(
    job_id: str,
    worker_id: str = Query(..., description="Worker ID releasing the job"),
    reason: str = Query("worker_failure", description="Reason for release"),
    queue: JobQueue = Depends(get_job_queue)
):
    """
    Release job from worker (for reassignment after failure).
    
    Increments retry count and re-queues if retries available,
    otherwise marks as permanently failed.
    """
    success = queue.release_job_from_worker(job_id, worker_id, reason)
    
    if not success:
        job_info = queue.get_job(job_id)
        if not job_info:
            raise HTTPException(status_code=404, detail=f"Job {job_id} not found")
        raise HTTPException(
            status_code=400,
            detail=f"Cannot release job {job_id} from worker {worker_id}"
        )
    
    job_info = queue.get_job(job_id)
    return JobResponse.from_job_info(job_info)


# ==================== Job Progress Endpoints ====================

@router.put("/{job_id}/progress", response_model=JobResponse)
async def update_job_progress(
    job_id: str,
    request: UpdateJobProgressRequest,
    queue: JobQueue = Depends(get_job_queue)
):
    """Update job training progress (called by workers)"""
    job_info = queue.get_job(job_id)
    if not job_info:
        raise HTTPException(status_code=404, detail=f"Job {job_id} not found")
    
    if job_info.status != JobStatus.RUNNING:
        raise HTTPException(
            status_code=400,
            detail=f"Cannot update progress for job in {job_info.status.value} status"
        )
    
    try:
        # Update progress fields
        job_info.progress_percent = request.progress_percent
        job_info.current_epoch = request.current_epoch
        job_info.current_loss = request.current_loss
        job_info.current_accuracy = request.current_accuracy
        job_info.updated_at = datetime.utcnow().isoformat()
        
        # Save to Redis
        import json
        job_key = queue.JOB_KEY.format(job_id=job_id)
        queue.redis.set(job_key, json.dumps(job_info.to_dict()))
        
        logger.info(f"Job {job_id} progress updated: {request.progress_percent}%")
        return JobResponse.from_job_info(job_info)
        
    except Exception as e:
        logger.error(f"Failed to update job {job_id} progress: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to update progress: {str(e)}")


@router.post("/{job_id}/complete", response_model=JobResponse)
async def complete_job(
    job_id: str,
    result_path: str = Query(..., description="GCS path to trained model"),
    metrics_summary: Dict[str, Any] = Query(default_factory=dict, description="Final metrics"),
    queue: JobQueue = Depends(get_job_queue)
):
    """Mark job as completed (called by workers)"""
    job_info = queue.get_job(job_id)
    if not job_info:
        raise HTTPException(status_code=404, detail=f"Job {job_id} not found")
    
    try:
        # Update result info
        job_info.result_path = result_path
        job_info.metrics_summary = metrics_summary
        job_info.progress_percent = 100.0
        
        # Save before status change
        import json
        job_key = queue.JOB_KEY.format(job_id=job_id)
        queue.redis.set(job_key, json.dumps(job_info.to_dict()))
        
        # Update status
        success = queue.update_job_status(job_id, JobStatus.COMPLETED)
        if not success:
            raise HTTPException(status_code=400, detail="Failed to mark job as completed")
        
        logger.info(f"Job {job_id} completed successfully")
        job_info = queue.get_job(job_id)
        return JobResponse.from_job_info(job_info)
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to complete job {job_id}: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to complete job: {str(e)}")


@router.post("/{job_id}/fail", response_model=JobResponse)
async def fail_job(
    job_id: str,
    error_message: str = Query(..., description="Error message"),
    queue: JobQueue = Depends(get_job_queue)
):
    """Mark job as failed (called by workers or system)"""
    success = queue.update_job_status(job_id, JobStatus.FAILED, error_message=error_message)
    
    if not success:
        job_info = queue.get_job(job_id)
        if not job_info:
            raise HTTPException(status_code=404, detail=f"Job {job_id} not found")
        raise HTTPException(status_code=400, detail="Failed to mark job as failed")
    
    logger.warning(f"Job {job_id} marked as failed: {error_message}")
    job_info = queue.get_job(job_id)
    return JobResponse.from_job_info(job_info)


# ==================== Validation Integration (Phase 4) ====================

@router.post("/{job_id}/validation-result", response_model=JobResponse)
async def update_validation_result(
    job_id: str,
    request: ValidationResultRequest,
    queue: JobQueue = Depends(get_job_queue)
):
    """
    Update job validation result (called by Phase 4 validation service).
    
    Transitions job from VALIDATING → WAITING (if passed) or FAILED (if failed).
    """
    success = queue.mark_validation_complete(
        job_id=job_id,
        model_validation_passed=request.model_validation_passed,
        dataset_validation_passed=request.dataset_validation_passed,
        validation_errors=request.validation_errors
    )
    
    if not success:
        raise HTTPException(status_code=404, detail=f"Job {job_id} not found")
    
    job_info = queue.get_job(job_id)
    logger.info(f"Job {job_id} validation result updated")
    return JobResponse.from_job_info(job_info)


# ==================== Job Cancellation ====================

@router.delete("/{job_id}", response_model=JobResponse)
async def cancel_job(
    job_id: str,
    reason: str = Query("user_requested", description="Cancellation reason"),
    queue: JobQueue = Depends(get_job_queue)
):
    """Cancel job (removes from queue, stops execution if running)"""
    success = queue.cancel_job(job_id, reason)
    
    if not success:
        job_info = queue.get_job(job_id)
        if not job_info:
            raise HTTPException(status_code=404, detail=f"Job {job_id} not found")
        
        if job_info.is_terminal_state():
            raise HTTPException(
                status_code=400,
                detail=f"Cannot cancel job in terminal state: {job_info.status.value}"
            )
        
        raise HTTPException(status_code=400, detail="Failed to cancel job")
    
    job_info = queue.get_job(job_id)
    logger.info(f"Job {job_id} cancelled: {reason}")
    return JobResponse.from_job_info(job_info)


# ==================== Queue Statistics ====================

@router.get("/stats/summary", response_model=QueueStatsResponse)
async def get_queue_stats(queue: JobQueue = Depends(get_job_queue)):
    """Get queue statistics"""
    stats = queue.get_queue_stats()
    return QueueStatsResponse(**stats)


@router.post("/maintenance/cleanup", response_model=Dict[str, Any])
async def cleanup_expired_jobs(queue: JobQueue = Depends(get_job_queue)):
    """
    Manually trigger cleanup of expired jobs.
    
    Cleans up:
    - Jobs stuck in VALIDATING for > validation_timeout
    - Jobs in RUNNING for > max_execution_time
    """
    cleaned = queue.cleanup_expired_jobs()
    
    return {
        "success": True,
        "message": "Cleanup completed",
        "jobs_cleaned": cleaned,
        "timestamp": datetime.utcnow().isoformat()
    }


# ==================== Health Check ====================

@router.get("/health", response_model=Dict[str, Any])
async def health_check(queue: JobQueue = Depends(get_job_queue)):
    """Health check for job queue service"""
    try:
        # Test Redis connection
        queue.redis.ping()
        
        stats = queue.get_queue_stats()
        
        return {
            "status": "healthy",
            "redis_connected": True,
            "total_jobs": stats.get("total_jobs", 0),
            "timestamp": datetime.utcnow().isoformat()
        }
    except Exception as e:
        logger.error(f"Health check failed: {e}")
        return {
            "status": "unhealthy",
            "redis_connected": False,
            "error": str(e),
            "timestamp": datetime.utcnow().isoformat()
        }
