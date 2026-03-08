"""
Worker Discovery & Registration API Router

Provides HTTP endpoints for worker discovery, registration,
pool management, and worker-job matching.
"""

from fastapi import APIRouter, HTTPException, Query, Depends
from pydantic import BaseModel, Field
from typing import List, Optional, Dict, Any
from datetime import datetime
import logging

from ..services.worker_discovery import (
    WorkerDiscoveryService,
    WorkerInfo,
    WorkerCapabilities,
    WorkerPool,
    WorkerStatus,
    WorkerPoolStatus,
    DiscoveryConfig
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/discovery", tags=["worker-discovery"])

# Dependency injection (to be replaced with actual instances)
def get_discovery_service() -> WorkerDiscoveryService:
    """Get worker discovery service instance (dependency injection)"""
    # TODO: Replace with actual service from app state
    from ..services.worker_registry import WorkerRegistry
    from ..services.job_queue import JobQueue
    from redis import Redis
    
    redis_client = Redis(host="localhost", port=6379, decode_responses=False)
    worker_registry = WorkerRegistry()
    job_queue = JobQueue(redis_client)
    
    return WorkerDiscoveryService(worker_registry, job_queue)


# ==================== Pydantic Models ====================

class WorkerCapabilitiesRequest(BaseModel):
    """Worker capabilities"""
    gpu_count: int = Field(..., ge=0, description="Number of GPUs")
    gpu_memory_gb: float = Field(..., ge=0.0, description="GPU memory in GB")
    gpu_type: str = Field(..., description="GPU type (e.g., NVIDIA A100)")
    cpu_count: int = Field(..., ge=1, description="Number of CPU cores")
    ram_gb: float = Field(..., ge=0.1, description="RAM in GB")
    network_speed_mbps: float = Field(..., ge=0.0, description="Network speed in Mbps")
    storage_gb: float = Field(..., ge=0.0, description="Storage in GB")
    supports_cuda: bool = Field(..., description="CUDA support")
    supports_mps: bool = Field(..., description="Apple MPS support")
    pytorch_version: str = Field(..., description="PyTorch version")
    python_version: str = Field(..., description="Python version")
    
    class Config:
        json_schema_extra = {
            "example": {
                "gpu_count": 4,
                "gpu_memory_gb": 24.0,
                "gpu_type": "NVIDIA A100",
                "cpu_count": 64,
                "ram_gb": 256.0,
                "network_speed_mbps": 10000.0,
                "storage_gb": 2000.0,
                "supports_cuda": True,
                "supports_mps": False,
                "pytorch_version": "2.0.0",
                "python_version": "3.10.8"
            }
        }


class RegisterWorkerRequest(BaseModel):
    """Worker registration request"""
    worker_id: str = Field(..., min_length=1, description="Unique worker identifier")
    hostname: str = Field(..., min_length=1, description="Worker hostname")
    ip_address: str = Field(..., description="Worker IP address")
    port: int = Field(..., ge=1, le=65535, description="Worker port")
    capabilities: WorkerCapabilitiesRequest
    group_id: Optional[str] = Field(None, description="Group assignment")
    version: str = Field("1.0.0", description="Worker software version")
    tags: Dict[str, str] = Field(default_factory=dict, description="Custom tags")
    
    class Config:
        json_schema_extra = {
            "example": {
                "worker_id": "worker_001",
                "hostname": "gpu-node-1",
                "ip_address": "192.168.1.100",
                "port": 8080,
                "group_id": "research_team",
                "version": "1.0.0",
                "capabilities": {
                    "gpu_count": 4,
                    "gpu_memory_gb": 24.0,
                    "gpu_type": "NVIDIA A100",
                    "cpu_count": 64,
                    "ram_gb": 256.0,
                    "network_speed_mbps": 10000.0,
                    "storage_gb": 2000.0,
                    "supports_cuda": True,
                    "supports_mps": False,
                    "pytorch_version": "2.0.0",
                    "python_version": "3.10.8"
                },
                "tags": {"region": "us-west", "tier": "premium"}
            }
        }


class CreatePoolRequest(BaseModel):
    """Worker pool creation request"""
    group_id: str = Field(..., min_length=1, description="Group identifier")
    name: str = Field(..., min_length=1, description="Pool name")
    description: str = Field("", description="Pool description")
    min_workers: int = Field(1, ge=1, description="Minimum workers")
    max_workers: int = Field(100, ge=1, description="Maximum workers")
    auto_scale: bool = Field(False, description="Enable auto-scaling")
    tags: Dict[str, str] = Field(default_factory=dict, description="Custom tags")
    
    class Config:
        json_schema_extra = {
            "example": {
                "group_id": "research_team",
                "name": "Research GPU Pool",
                "description": "High-performance GPU pool for research team",
                "min_workers": 5,
                "max_workers": 50,
                "auto_scale": True,
                "tags": {"cost_center": "research", "priority": "high"}
            }
        }


class AssignJobRequest(BaseModel):
    """Job assignment request"""
    job_id: str = Field(..., min_length=1, description="Job identifier")
    worker_id: Optional[str] = Field(None, description="Worker ID (auto-match if None)")
    shard_ids: List[int] = Field(default_factory=list, description="Data shard IDs")
    
    class Config:
        json_schema_extra = {
            "example": {
                "job_id": "job_12345",
                "worker_id": "worker_001",
                "shard_ids": [0, 1, 2]
            }
        }


class WorkerInfoResponse(BaseModel):
    """Worker information response"""
    worker_id: str
    hostname: str
    ip_address: str
    port: int
    status: str
    group_id: Optional[str] = None
    assigned_job_id: Optional[str] = None
    assigned_shard_ids: List[int] = Field(default_factory=list)
    registered_at: str
    last_heartbeat: str
    capabilities: Dict[str, Any]
    compute_score: float
    
    @classmethod
    def from_worker_info(cls, worker: WorkerInfo) -> "WorkerInfoResponse":
        """Convert WorkerInfo to response model"""
        return cls(
            worker_id=worker.worker_id,
            hostname=worker.hostname,
            ip_address=worker.ip_address,
            port=worker.port,
            status=worker.status.value,
            group_id=worker.group_id,
            assigned_job_id=worker.assigned_job_id,
            assigned_shard_ids=worker.assigned_shard_ids,
            registered_at=worker.registered_at,
            last_heartbeat=worker.last_heartbeat,
            capabilities=worker.capabilities.to_dict(),
            compute_score=worker.capabilities.get_compute_score()
        )


class PoolResponse(BaseModel):
    """Worker pool response"""
    group_id: str
    name: str
    description: str
    worker_count: int
    min_workers: int
    max_workers: int
    auto_scale: bool
    created_at: str
    tags: Dict[str, str]
    
    @classmethod
    def from_pool(cls, pool: WorkerPool) -> "PoolResponse":
        """Convert WorkerPool to response model"""
        return cls(
            group_id=pool.group_id,
            name=pool.name,
            description=pool.description,
            worker_count=pool.get_worker_count(),
            min_workers=pool.min_workers,
            max_workers=pool.max_workers,
            auto_scale=pool.auto_scale,
            created_at=pool.created_at,
            tags=pool.tags
        )


class PoolStatsResponse(BaseModel):
    """Pool statistics response"""
    group_id: str
    pool_name: str
    total_workers: int
    status_counts: Dict[str, int]
    available_workers: int
    busy_workers: int
    offline_workers: int
    total_gpus: int
    total_ram_gb: float
    total_storage_gb: float
    avg_compute_score: float
    pool_status: str
    min_workers: int
    max_workers: int
    auto_scale: bool
    timestamp: str


# ==================== Worker Registration Endpoints ====================

@router.post("/workers/register", response_model=WorkerInfoResponse, status_code=201)
async def register_worker(
    request: RegisterWorkerRequest,
    service: WorkerDiscoveryService = Depends(get_discovery_service)
):
    """
    Register new worker with discovery service.
    
    Workflow:
    1. Validate group assignment (if required)
    2. Check pool capacity
    3. Register with worker registry
    4. Add to worker pool
    5. Return worker information
    """
    try:
        # Convert capabilities
        capabilities = WorkerCapabilities(**request.capabilities.model_dump())
        
        # Register worker
        worker_info = service.register_worker(
            worker_id=request.worker_id,
            hostname=request.hostname,
            ip_address=request.ip_address,
            port=request.port,
            capabilities=capabilities,
            group_id=request.group_id,
            version=request.version,
            tags=request.tags
        )
        
        logger.info(f"Registered worker {request.worker_id} in group {request.group_id}")
        return WorkerInfoResponse.from_worker_info(worker_info)
        
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Failed to register worker {request.worker_id}: {e}")
        raise HTTPException(status_code=500, detail=f"Registration failed: {str(e)}")


@router.delete("/workers/{worker_id}")
async def unregister_worker(
    worker_id: str,
    service: WorkerDiscoveryService = Depends(get_discovery_service)
):
    """Unregister worker from discovery service"""
    success = service.unregister_worker(worker_id)
    
    if not success:
        raise HTTPException(status_code=404, detail=f"Worker {worker_id} not found")
    
    return {
        "success": True,
        "message": f"Worker {worker_id} unregistered",
        "timestamp": datetime.utcnow().isoformat()
    }


# ==================== Worker Discovery Endpoints ====================

@router.get("/workers", response_model=List[WorkerInfoResponse])
async def discover_workers(
    group_id: Optional[str] = Query(None, description="Filter by group"),
    min_gpu_count: int = Query(0, ge=0, description="Minimum GPU count"),
    status: Optional[str] = Query(None, description="Filter by status"),
    service: WorkerDiscoveryService = Depends(get_discovery_service)
):
    """
    Discover workers with optional filters.
    
    Query Parameters:
    - group_id: Filter by group
    - min_gpu_count: Minimum GPU count
    - status: Filter by worker status (idle, online, busy, etc.)
    """
    try:
        # Parse status filter
        status_filter = None
        if status:
            try:
                status_filter = [WorkerStatus(status.lower())]
            except ValueError:
                raise HTTPException(
                    status_code=400,
                    detail=f"Invalid status: {status}. Must be one of: {', '.join(s.value for s in WorkerStatus)}"
                )
        
        workers = service.discover_workers(
            group_id=group_id,
            min_gpu_count=min_gpu_count,
            status_filter=status_filter
        )
        
        return [WorkerInfoResponse.from_worker_info(w) for w in workers]
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to discover workers: {e}")
        raise HTTPException(status_code=500, detail=f"Discovery failed: {str(e)}")


@router.get("/workers/available", response_model=List[WorkerInfoResponse])
async def get_available_workers(
    group_id: Optional[str] = Query(None, description="Filter by group"),
    min_gpu_count: int = Query(0, ge=0, description="Minimum GPU count"),
    service: WorkerDiscoveryService = Depends(get_discovery_service)
):
    """
    Get workers available for job assignment.
    
    Returns workers with IDLE or ONLINE status, sorted by compute capability.
    """
    try:
        workers = service.get_available_workers(
            group_id=group_id,
            min_gpu_count=min_gpu_count
        )
        
        # Sort by compute score (highest first)
        workers.sort(key=lambda w: w.capabilities.get_compute_score(), reverse=True)
        
        return [WorkerInfoResponse.from_worker_info(w) for w in workers]
        
    except Exception as e:
        logger.error(f"Failed to get available workers: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to get workers: {str(e)}")


# ==================== Worker Pool Management Endpoints ====================

@router.post("/pools", response_model=PoolResponse, status_code=201)
async def create_pool(
    request: CreatePoolRequest,
    service: WorkerDiscoveryService = Depends(get_discovery_service)
):
    """Create new worker pool for a group"""
    try:
        pool = service.create_pool(
            group_id=request.group_id,
            name=request.name,
            description=request.description,
            min_workers=request.min_workers,
            max_workers=request.max_workers,
            auto_scale=request.auto_scale,
            tags=request.tags
        )
        
        logger.info(f"Created pool for group {request.group_id}")
        return PoolResponse.from_pool(pool)
        
    except Exception as e:
        logger.error(f"Failed to create pool: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to create pool: {str(e)}")


@router.get("/pools/{group_id}", response_model=PoolResponse)
async def get_pool(
    group_id: str,
    service: WorkerDiscoveryService = Depends(get_discovery_service)
):
    """Get worker pool by group ID"""
    pool = service.get_pool(group_id)
    if not pool:
        raise HTTPException(status_code=404, detail=f"Pool for group {group_id} not found")
    
    return PoolResponse.from_pool(pool)


@router.get("/pools", response_model=List[PoolResponse])
async def list_pools(
    service: WorkerDiscoveryService = Depends(get_discovery_service)
):
    """List all worker pools"""
    pools = service.list_pools()
    return [PoolResponse.from_pool(p) for p in pools]


@router.delete("/pools/{group_id}")
async def delete_pool(
    group_id: str,
    force: bool = Query(False, description="Force delete even with active workers"),
    service: WorkerDiscoveryService = Depends(get_discovery_service)
):
    """Delete worker pool"""
    success = service.delete_pool(group_id, force=force)
    
    if not success:
        raise HTTPException(
            status_code=400,
            detail=f"Cannot delete pool {group_id}. Use force=true to delete pool with active workers"
        )
    
    return {
        "success": True,
        "message": f"Pool {group_id} deleted",
        "timestamp": datetime.utcnow().isoformat()
    }


@router.get("/pools/{group_id}/stats", response_model=PoolStatsResponse)
async def get_pool_stats(
    group_id: str,
    service: WorkerDiscoveryService = Depends(get_discovery_service)
):
    """
    Get detailed pool statistics.
    
    Includes:
    - Worker counts by status
    - Total resources (GPUs, RAM, storage)
    - Average compute score
    - Pool health status
    """
    stats = service.get_pool_stats(group_id)
    
    if not stats:
        raise HTTPException(status_code=404, detail=f"Pool {group_id} not found")
    
    return PoolStatsResponse(**stats)


# ==================== Worker-Job Matching Endpoints ====================

@router.get("/match/{job_id}", response_model=Optional[WorkerInfoResponse])
async def match_worker_to_job(
    job_id: str,
    group_id: Optional[str] = Query(None, description="Restrict to workers in this group"),
    service: WorkerDiscoveryService = Depends(get_discovery_service)
):
    """
    Find best worker for a job.
    
    Algorithm:
    1. Get job requirements
    2. Filter workers by requirements
    3. Sort by compute score
    4. Return best match
    
    Returns null if no matching worker found.
    """
    try:
        worker = service.match_worker_to_job(job_id, group_id)
        
        if not worker:
            return None
        
        return WorkerInfoResponse.from_worker_info(worker)
        
    except Exception as e:
        logger.error(f"Failed to match worker to job {job_id}: {e}")
        raise HTTPException(status_code=500, detail=f"Matching failed: {str(e)}")


@router.post("/assign", response_model=Dict[str, Any])
async def assign_job_to_worker(
    request: AssignJobRequest,
    service: WorkerDiscoveryService = Depends(get_discovery_service)
):
    """
    Assign job to worker.
    
    If worker_id is not provided, automatically finds best matching worker.
    
    Workflow:
    1. Find best worker (if not specified)
    2. Assign in job queue (TASK-6.2)
    3. Assign in worker registry (TASK-6.1)
    4. Return assignment details
    """
    try:
        success = service.assign_job_to_worker(
            job_id=request.job_id,
            worker_id=request.worker_id,
            shard_ids=request.shard_ids
        )
        
        if not success:
            raise HTTPException(
                status_code=400,
                detail=f"Failed to assign job {request.job_id}"
            )
        
        # Get final worker assignment
        job = service.job_queue.get_job(request.job_id)
        
        return {
            "success": True,
            "message": "Job assigned successfully",
            "job_id": request.job_id,
            "worker_id": job.assigned_worker_id if job else request.worker_id,
            "shard_ids": job.assigned_shard_ids if job else request.shard_ids,
            "timestamp": datetime.utcnow().isoformat()
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to assign job {request.job_id}: {e}")
        raise HTTPException(status_code=500, detail=f"Assignment failed: {str(e)}")


# ==================== System Statistics Endpoints ====================

@router.get("/stats/distribution", response_model=Dict[str, int])
async def get_worker_distribution(
    service: WorkerDiscoveryService = Depends(get_discovery_service)
):
    """
    Get worker distribution across pools.
    
    Returns mapping of group_id to worker count.
    """
    return service.get_worker_distribution()


@router.get("/stats/capacity", response_model=Dict[str, Any])
async def get_total_capacity(
    service: WorkerDiscoveryService = Depends(get_discovery_service)
):
    """
    Get total system capacity.
    
    Returns:
    - Total workers
    - Total GPUs, CPUs, RAM, storage
    - Average compute score
    """
    return service.get_total_capacity()


@router.get("/stats/scaling-needs", response_model=Dict[str, str])
async def check_scaling_needs(
    service: WorkerDiscoveryService = Depends(get_discovery_service)
):
    """
    Check which pools need scaling.
    
    Returns mapping of group_id to scaling action ("scale_up" or "scale_down").
    """
    return service.check_scaling_needs()


# ==================== Health Check ====================

@router.get("/health", response_model=Dict[str, Any])
async def health_check(
    service: WorkerDiscoveryService = Depends(get_discovery_service)
):
    """Health check for worker discovery service"""
    try:
        pools = service.list_pools()
        all_workers = service.discover_workers()
        available_workers = service.get_available_workers()
        
        return {
            "status": "healthy",
            "total_pools": len(pools),
            "total_workers": len(all_workers),
            "available_workers": len(available_workers),
            "timestamp": datetime.utcnow().isoformat()
        }
    except Exception as e:
        logger.error(f"Health check failed: {e}")
        return {
            "status": "unhealthy",
            "error": str(e),
            "timestamp": datetime.utcnow().isoformat()
        }
