"""
Task Assignment API Router

Provides HTTP endpoints for intelligent task assignment,
batch operations, load balancing, and cluster monitoring.
"""

from fastapi import APIRouter, HTTPException, Query, status
from pydantic import BaseModel, Field
from typing import List, Optional, Dict, Any
from datetime import datetime

from app.services.task_assignment import (
    TaskAssignmentService,
    AssignmentStrategy,
    LoadBalancingPolicy,
    AssignmentConstraints,
    AssignmentConfig,
    AssignmentStatus
)


router = APIRouter(prefix="/assignment", tags=["task-assignment"])

# Dependency injection (will be set by main app)
assignment_service: Optional[TaskAssignmentService] = None


def get_assignment_service() -> TaskAssignmentService:
    """Get assignment service instance"""
    if assignment_service is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Task assignment service not initialized"
        )
    return assignment_service


# ==================== Request/Response Models ====================

class AssignJobRequest(BaseModel):
    """Request to assign a single job"""
    job_id: str = Field(..., description="Job ID to assign")
    strategy: Optional[AssignmentStrategy] = Field(None, description="Assignment strategy")
    shard_ids: Optional[List[int]] = Field(None, description="Shard IDs to assign")
    constraints: Optional[Dict[str, Any]] = Field(None, description="Assignment constraints")


class AssignmentConstraintsRequest(BaseModel):
    """Assignment constraints"""
    require_group: Optional[str] = None
    exclude_workers: List[str] = Field(default_factory=list)
    require_gpu: bool = False
    min_gpu_count: int = 0
    min_ram_gb: float = 0.0
    require_cuda: bool = False
    require_mps: bool = False
    max_jobs_per_worker: int = 10
    affinity_jobs: List[str] = Field(default_factory=list)
    anti_affinity_jobs: List[str] = Field(default_factory=list)
    preferred_workers: List[str] = Field(default_factory=list)


class BatchAssignRequest(BaseModel):
    """Request to assign multiple jobs"""
    job_ids: List[str] = Field(..., description="List of job IDs to assign")
    strategy: Optional[AssignmentStrategy] = Field(None, description="Assignment strategy")
    load_balancing: Optional[LoadBalancingPolicy] = Field(None, description="Load balancing policy")
    constraints: Optional[Dict[str, Any]] = Field(None, description="Assignment constraints")


class AssignmentResponse(BaseModel):
    """Response for single assignment"""
    job_id: str
    worker_id: Optional[str]
    status: str
    assigned_at: Optional[str]
    shard_ids: List[int]
    compute_score: float
    message: str
    error: Optional[str] = None


class BatchAssignmentResponse(BaseModel):
    """Response for batch assignment"""
    total_jobs: int
    successful: int
    failed: int
    success_rate: float
    assignments: List[AssignmentResponse]
    started_at: str
    completed_at: Optional[str]
    duration_seconds: float


class WorkerLoadResponse(BaseModel):
    """Worker load information"""
    worker_id: str
    assigned_jobs: int
    total_capacity: int
    utilization: float
    compute_score: float
    available_capacity: int
    is_available: bool


class ClusterLoadResponse(BaseModel):
    """Cluster load statistics"""
    group_id: Optional[str]
    total_workers: int
    total_jobs: int
    avg_utilization: float
    worker_loads: List[WorkerLoadResponse]
    timestamp: str


class RebalanceResponse(BaseModel):
    """Load rebalancing result"""
    group_id: Optional[str]
    reassigned_jobs: int
    overloaded_workers: int
    underutilized_workers: int
    timestamp: str


class AssignmentStatsResponse(BaseModel):
    """Assignment statistics"""
    hours: int
    total_assignments: int
    successful: int
    failed: int
    success_rate: float
    timestamp: str


# ==================== Endpoints ====================

@router.post("/jobs/assign", response_model=AssignmentResponse, status_code=status.HTTP_201_CREATED)
async def assign_job(request: AssignJobRequest):
    """
    Assign a single job to a worker.
    
    Uses the specified assignment strategy to select the best worker
    and assigns the job with optional shard IDs.
    
    **Strategies**:
    - `greedy`: First available worker
    - `balanced`: Least loaded worker
    - `best_fit`: Match capabilities to requirements
    - `compute_optimized`: Highest compute score worker
    - `affinity`: Co-locate with related jobs
    - `anti_affinity`: Separate from related jobs
    
    **Returns**: Assignment details with worker ID and status
    """
    service = get_assignment_service()
    
    # Convert constraints dict to AssignmentConstraints
    constraints = None
    if request.constraints:
        constraints = AssignmentConstraints(
            require_group=request.constraints.get("require_group"),
            exclude_workers=set(request.constraints.get("exclude_workers", [])),
            require_gpu=request.constraints.get("require_gpu", False),
            min_gpu_count=request.constraints.get("min_gpu_count", 0),
            min_ram_gb=request.constraints.get("min_ram_gb", 0.0),
            require_cuda=request.constraints.get("require_cuda", False),
            require_mps=request.constraints.get("require_mps", False),
            max_jobs_per_worker=request.constraints.get("max_jobs_per_worker", 10),
            affinity_jobs=request.constraints.get("affinity_jobs", []),
            anti_affinity_jobs=request.constraints.get("anti_affinity_jobs", []),
            preferred_workers=request.constraints.get("preferred_workers", [])
        )
    
    result = await service.assign_job(
        job_id=request.job_id,
        strategy=request.strategy,
        constraints=constraints,
        shard_ids=request.shard_ids
    )
    
    return AssignmentResponse(
        job_id=result.job_id,
        worker_id=result.worker_id,
        status=result.status.value,
        assigned_at=result.assigned_at.isoformat() if result.assigned_at else None,
        shard_ids=result.shard_ids,
        compute_score=result.compute_score,
        message=result.message,
        error=result.error
    )


@router.post("/jobs/assign/batch", response_model=BatchAssignmentResponse, status_code=status.HTTP_201_CREATED)
async def assign_batch(request: BatchAssignRequest):
    """
    Assign multiple jobs to workers using batch optimization.
    
    **Load Balancing Policies**:
    - `round_robin`: Rotate through available workers
    - `least_loaded`: Assign to workers with fewest jobs
    - `weighted_round_robin`: Weight by compute score
    - `priority_based`: High-priority jobs to best workers
    
    **Returns**: Batch assignment results with success rate
    """
    service = get_assignment_service()
    
    # Convert constraints
    constraints = None
    if request.constraints:
        constraints = AssignmentConstraints(
            require_group=request.constraints.get("require_group"),
            exclude_workers=set(request.constraints.get("exclude_workers", [])),
            require_gpu=request.constraints.get("require_gpu", False),
            min_gpu_count=request.constraints.get("min_gpu_count", 0),
            min_ram_gb=request.constraints.get("min_ram_gb", 0.0),
            require_cuda=request.constraints.get("require_cuda", False),
            require_mps=request.constraints.get("require_mps", False),
            max_jobs_per_worker=request.constraints.get("max_jobs_per_worker", 10),
            affinity_jobs=request.constraints.get("affinity_jobs", []),
            anti_affinity_jobs=request.constraints.get("anti_affinity_jobs", []),
            preferred_workers=request.constraints.get("preferred_workers", [])
        )
    
    result = await service.assign_batch(
        job_ids=request.job_ids,
        strategy=request.strategy,
        load_balancing=request.load_balancing,
        constraints=constraints
    )
    
    return BatchAssignmentResponse(
        total_jobs=result.total_jobs,
        successful=result.successful,
        failed=result.failed,
        success_rate=result.success_rate,
        assignments=[
            AssignmentResponse(
                job_id=a.job_id,
                worker_id=a.worker_id,
                status=a.status.value,
                assigned_at=a.assigned_at.isoformat() if a.assigned_at else None,
                shard_ids=a.shard_ids,
                compute_score=a.compute_score,
                message=a.message,
                error=a.error
            )
            for a in result.assignments
        ],
        started_at=result.started_at.isoformat(),
        completed_at=result.completed_at.isoformat() if result.completed_at else None,
        duration_seconds=result.duration_seconds
    )


@router.get("/load/worker/{worker_id}", response_model=WorkerLoadResponse)
async def get_worker_load(worker_id: str):
    """
    Get current load information for a specific worker.
    
    **Returns**:
    - Assigned jobs count
    - Total capacity
    - Utilization percentage
    - Available capacity
    - Compute score
    """
    service = get_assignment_service()
    
    load = await service.get_worker_load(worker_id)
    
    return WorkerLoadResponse(
        worker_id=load.worker_id,
        assigned_jobs=load.assigned_jobs,
        total_capacity=load.total_capacity,
        utilization=load.utilization,
        compute_score=load.compute_score,
        available_capacity=load.available_capacity,
        is_available=load.is_available
    )


@router.get("/load/cluster", response_model=ClusterLoadResponse)
async def get_cluster_load(
    group_id: Optional[str] = Query(None, description="Filter by group ID")
):
    """
    Get load statistics for entire cluster or specific group.
    
    **Returns**:
    - Total workers and jobs
    - Average utilization
    - Per-worker load details
    """
    service = get_assignment_service()
    
    stats = await service.get_cluster_load(group_id=group_id)
    
    return ClusterLoadResponse(
        group_id=stats["group_id"],
        total_workers=stats["total_workers"],
        total_jobs=stats["total_jobs"],
        avg_utilization=stats["avg_utilization"],
        worker_loads=[
            WorkerLoadResponse(**load)
            for load in stats["worker_loads"]
        ],
        timestamp=stats["timestamp"]
    )


@router.post("/load/rebalance", response_model=RebalanceResponse)
async def rebalance_load(
    group_id: Optional[str] = Query(None, description="Group to rebalance"),
    threshold: Optional[float] = Query(None, ge=0.0, le=1.0, description="Utilization threshold")
):
    """
    Rebalance load across workers by reassigning jobs.
    
    Moves jobs from overloaded workers (above threshold) to
    underutilized workers (below 50% utilization).
    
    **Parameters**:
    - `group_id`: Optional group to rebalance (default: all)
    - `threshold`: Utilization threshold (default: 0.8 = 80%)
    
    **Returns**: Number of jobs reassigned and worker statistics
    """
    service = get_assignment_service()
    
    result = await service.rebalance_load(
        group_id=group_id,
        threshold=threshold
    )
    
    return RebalanceResponse(
        group_id=result["group_id"],
        reassigned_jobs=result["reassigned_jobs"],
        overloaded_workers=result["overloaded_workers"],
        underutilized_workers=result["underutilized_workers"],
        timestamp=result["timestamp"]
    )


@router.post("/load/rebalance/start")
async def start_auto_rebalancing():
    """
    Start automatic load rebalancing.
    
    Periodically rebalances load across workers based on
    configured interval (default: 5 minutes).
    
    **Returns**: Confirmation message
    """
    service = get_assignment_service()
    
    await service.start_auto_rebalancing()
    
    return {
        "message": "Auto-rebalancing started",
        "interval_seconds": service.config.rebalance_interval_seconds
    }


@router.post("/load/rebalance/stop")
async def stop_auto_rebalancing():
    """
    Stop automatic load rebalancing.
    
    **Returns**: Confirmation message
    """
    service = get_assignment_service()
    
    await service.stop_auto_rebalancing()
    
    return {"message": "Auto-rebalancing stopped"}


@router.get("/stats", response_model=AssignmentStatsResponse)
async def get_assignment_stats(
    hours: int = Query(24, ge=1, le=168, description="Number of hours to analyze")
):
    """
    Get assignment statistics for the last N hours.
    
    **Parameters**:
    - `hours`: Number of hours to analyze (default: 24, max: 168 = 1 week)
    
    **Returns**:
    - Total assignments
    - Success/failure counts
    - Success rate percentage
    """
    service = get_assignment_service()
    
    stats = service.get_assignment_stats(hours=hours)
    
    return AssignmentStatsResponse(
        hours=stats["hours"],
        total_assignments=stats["total_assignments"],
        successful=stats["successful"],
        failed=stats["failed"],
        success_rate=stats["success_rate"],
        timestamp=stats["timestamp"]
    )


@router.get("/strategies")
async def list_strategies():
    """
    List available assignment strategies.
    
    **Returns**: Dictionary of strategies with descriptions
    """
    return {
        "strategies": {
            "greedy": "Assign to first available worker",
            "balanced": "Assign to least loaded worker",
            "best_fit": "Match worker capabilities to job requirements",
            "compute_optimized": "Prefer highest compute score workers",
            "cost_optimized": "Prefer lower-cost workers",
            "affinity": "Co-locate with related jobs",
            "anti_affinity": "Separate from related jobs for fault tolerance"
        },
        "load_balancing_policies": {
            "round_robin": "Rotate through available workers",
            "least_loaded": "Assign to workers with fewest jobs",
            "weighted_round_robin": "Weight assignments by compute score",
            "random": "Random assignment",
            "priority_based": "High-priority jobs to best workers"
        }
    }


@router.get("/health")
async def health_check():
    """
    Health check endpoint.
    
    **Returns**: Service status and configuration
    """
    service = get_assignment_service()
    
    return {
        "status": "healthy",
        "default_strategy": service.config.default_strategy.value,
        "default_load_balancing": service.config.default_load_balancing.value,
        "max_concurrent_assignments": service.config.max_concurrent_assignments,
        "auto_rebalancing_active": service.rebalance_task is not None,
        "rebalance_interval_seconds": service.config.rebalance_interval_seconds
    }
