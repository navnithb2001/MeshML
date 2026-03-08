"""API router for worker registration and health monitoring.

Provides HTTP endpoints for workers to register, send heartbeats,
and report their status.
"""

import logging
from typing import List, Optional, Dict, Any
from fastapi import APIRouter, HTTPException, Depends, BackgroundTasks
from pydantic import BaseModel, Field

from app.services.worker_registry import (
    WorkerRegistry,
    WorkerInfo,
    WorkerStatus,
    WorkerCapabilities,
    WorkerMetrics
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/workers", tags=["workers"])

# Global registry instance (would be dependency-injected in production)
_registry = None


def get_registry() -> WorkerRegistry:
    """Dependency to get WorkerRegistry instance."""
    global _registry
    if _registry is None:
        _registry = WorkerRegistry(
            heartbeat_timeout_seconds=30,
            heartbeat_check_interval=10,
            auto_cleanup=True
        )
    return _registry


# Request/Response Models

class WorkerCapabilitiesRequest(BaseModel):
    """Worker capabilities for registration."""
    gpu_count: int = Field(0, ge=0)
    gpu_memory_gb: float = Field(0.0, ge=0.0)
    gpu_type: str = "none"
    cpu_count: int = Field(1, ge=1)
    ram_gb: float = Field(4.0, ge=0.1)
    network_speed_mbps: float = Field(100.0, ge=0.0)
    storage_gb: float = Field(100.0, ge=0.0)
    supports_cuda: bool = False
    supports_mps: bool = False
    pytorch_version: str = "unknown"
    python_version: str = "unknown"


class WorkerMetricsRequest(BaseModel):
    """Worker metrics for heartbeat."""
    cpu_usage_percent: float = Field(0.0, ge=0.0, le=100.0)
    memory_usage_percent: float = Field(0.0, ge=0.0, le=100.0)
    gpu_usage_percent: float = Field(0.0, ge=0.0, le=100.0)
    gpu_memory_usage_percent: float = Field(0.0, ge=0.0, le=100.0)
    network_rx_mbps: float = Field(0.0, ge=0.0)
    network_tx_mbps: float = Field(0.0, ge=0.0)
    disk_usage_percent: float = Field(0.0, ge=0.0, le=100.0)
    active_tasks: int = Field(0, ge=0)
    completed_tasks: int = Field(0, ge=0)
    failed_tasks: int = Field(0, ge=0)


class RegisterWorkerRequest(BaseModel):
    """Request to register a worker."""
    worker_id: str = Field(..., min_length=1, description="Unique worker identifier")
    hostname: str = Field(..., min_length=1)
    ip_address: str
    port: int = Field(..., ge=1, le=65535)
    capabilities: WorkerCapabilitiesRequest
    group_id: Optional[str] = None
    version: str = "unknown"
    tags: Dict[str, str] = Field(default_factory=dict)


class HeartbeatRequest(BaseModel):
    """Request to send heartbeat."""
    metrics: Optional[WorkerMetricsRequest] = None
    status: Optional[str] = None


class WorkerResponse(BaseModel):
    """Response containing worker information."""
    worker_id: str
    hostname: str
    ip_address: str
    port: int
    status: str
    capabilities: Dict[str, Any]
    metrics: Dict[str, Any]
    registered_at: str
    last_heartbeat: str
    last_status_change: str
    group_id: Optional[str]
    assigned_job_id: Optional[str]
    assigned_shard_id: Optional[int]
    version: str
    tags: Dict[str, str]


class RegistryStatsResponse(BaseModel):
    """Response containing registry statistics."""
    total_workers: int
    status_counts: Dict[str, int]
    total_gpus: int
    total_ram_gb: float
    group_counts: Dict[str, int]
    heartbeat_timeout_seconds: int


# Endpoints

@router.post("/register", response_model=WorkerResponse)
async def register_worker(
    request: RegisterWorkerRequest,
    registry: WorkerRegistry = Depends(get_registry)
):
    """
    Register a new worker or update existing registration.
    
    Workers should call this endpoint on startup to register
    their capabilities and availability.
    """
    try:
        # Convert request to capabilities
        capabilities = WorkerCapabilities(
            gpu_count=request.capabilities.gpu_count,
            gpu_memory_gb=request.capabilities.gpu_memory_gb,
            gpu_type=request.capabilities.gpu_type,
            cpu_count=request.capabilities.cpu_count,
            ram_gb=request.capabilities.ram_gb,
            network_speed_mbps=request.capabilities.network_speed_mbps,
            storage_gb=request.capabilities.storage_gb,
            supports_cuda=request.capabilities.supports_cuda,
            supports_mps=request.capabilities.supports_mps,
            pytorch_version=request.capabilities.pytorch_version,
            python_version=request.capabilities.python_version
        )
        
        # Register worker
        worker = registry.register_worker(
            worker_id=request.worker_id,
            hostname=request.hostname,
            ip_address=request.ip_address,
            port=request.port,
            capabilities=capabilities,
            group_id=request.group_id,
            version=request.version,
            tags=request.tags
        )
        
        return WorkerResponse(
            worker_id=worker.worker_id,
            hostname=worker.hostname,
            ip_address=worker.ip_address,
            port=worker.port,
            status=worker.status.value,
            capabilities=worker.capabilities.to_dict(),
            metrics=worker.metrics.to_dict(),
            registered_at=worker.registered_at,
            last_heartbeat=worker.last_heartbeat,
            last_status_change=worker.last_status_change,
            group_id=worker.group_id,
            assigned_job_id=worker.assigned_job_id,
            assigned_shard_id=worker.assigned_shard_id,
            version=worker.version,
            tags=worker.tags
        )
        
    except Exception as e:
        logger.error(f"Failed to register worker {request.worker_id}: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/{worker_id}/heartbeat")
async def send_heartbeat(
    worker_id: str,
    request: HeartbeatRequest,
    registry: WorkerRegistry = Depends(get_registry)
):
    """
    Send heartbeat from worker.
    
    Workers should call this endpoint periodically (e.g., every 10 seconds)
    to indicate they are alive and provide updated metrics.
    """
    # Convert metrics if provided
    metrics = None
    if request.metrics:
        metrics = WorkerMetrics(
            cpu_usage_percent=request.metrics.cpu_usage_percent,
            memory_usage_percent=request.metrics.memory_usage_percent,
            gpu_usage_percent=request.metrics.gpu_usage_percent,
            gpu_memory_usage_percent=request.metrics.gpu_memory_usage_percent,
            network_rx_mbps=request.metrics.network_rx_mbps,
            network_tx_mbps=request.metrics.network_tx_mbps,
            disk_usage_percent=request.metrics.disk_usage_percent,
            active_tasks=request.metrics.active_tasks,
            completed_tasks=request.metrics.completed_tasks,
            failed_tasks=request.metrics.failed_tasks
        )
    
    # Convert status if provided
    status = None
    if request.status:
        try:
            status = WorkerStatus(request.status)
        except ValueError:
            raise HTTPException(
                status_code=400,
                detail=f"Invalid status: {request.status}"
            )
    
    # Update heartbeat
    success = registry.update_heartbeat(worker_id, metrics=metrics, status=status)
    
    if not success:
        raise HTTPException(
            status_code=404,
            detail=f"Worker {worker_id} not found. Please register first."
        )
    
    worker = registry.get_worker(worker_id)
    
    return {
        "success": True,
        "message": "Heartbeat received",
        "worker_id": worker_id,
        "status": worker.status.value if worker else "unknown",
        "time_since_registration": worker.get_uptime_seconds() if worker else 0
    }


@router.get("/{worker_id}", response_model=WorkerResponse)
async def get_worker_info(
    worker_id: str,
    registry: WorkerRegistry = Depends(get_registry)
):
    """Get information about a specific worker."""
    worker = registry.get_worker(worker_id)
    
    if not worker:
        raise HTTPException(
            status_code=404,
            detail=f"Worker {worker_id} not found"
        )
    
    return WorkerResponse(
        worker_id=worker.worker_id,
        hostname=worker.hostname,
        ip_address=worker.ip_address,
        port=worker.port,
        status=worker.status.value,
        capabilities=worker.capabilities.to_dict(),
        metrics=worker.metrics.to_dict(),
        registered_at=worker.registered_at,
        last_heartbeat=worker.last_heartbeat,
        last_status_change=worker.last_status_change,
        group_id=worker.group_id,
        assigned_job_id=worker.assigned_job_id,
        assigned_shard_id=worker.assigned_shard_id,
        version=worker.version,
        tags=worker.tags
    )


@router.get("/", response_model=List[WorkerResponse])
async def list_workers(
    status: Optional[str] = None,
    group_id: Optional[str] = None,
    min_gpu_count: int = 0,
    registry: WorkerRegistry = Depends(get_registry)
):
    """
    List all workers with optional filtering.
    
    Query Parameters:
    - status: Filter by status (online, idle, busy, degraded, offline)
    - group_id: Filter by group ID
    - min_gpu_count: Filter by minimum GPU count
    """
    # Parse status if provided
    status_enum = None
    if status:
        try:
            status_enum = WorkerStatus(status)
        except ValueError:
            raise HTTPException(
                status_code=400,
                detail=f"Invalid status: {status}"
            )
    
    workers = registry.list_workers(
        status=status_enum,
        group_id=group_id,
        min_gpu_count=min_gpu_count
    )
    
    return [
        WorkerResponse(
            worker_id=w.worker_id,
            hostname=w.hostname,
            ip_address=w.ip_address,
            port=w.port,
            status=w.status.value,
            capabilities=w.capabilities.to_dict(),
            metrics=w.metrics.to_dict(),
            registered_at=w.registered_at,
            last_heartbeat=w.last_heartbeat,
            last_status_change=w.last_status_change,
            group_id=w.group_id,
            assigned_job_id=w.assigned_job_id,
            assigned_shard_id=w.assigned_shard_id,
            version=w.version,
            tags=w.tags
        )
        for w in workers
    ]


@router.get("/available/list", response_model=List[WorkerResponse])
async def list_available_workers(
    group_id: Optional[str] = None,
    min_gpu_count: int = 0,
    registry: WorkerRegistry = Depends(get_registry)
):
    """
    List workers available for task assignment.
    
    Returns workers with IDLE or ONLINE status, sorted by compute capability.
    """
    workers = registry.get_available_workers(
        group_id=group_id,
        min_gpu_count=min_gpu_count
    )
    
    return [
        WorkerResponse(
            worker_id=w.worker_id,
            hostname=w.hostname,
            ip_address=w.ip_address,
            port=w.port,
            status=w.status.value,
            capabilities=w.capabilities.to_dict(),
            metrics=w.metrics.to_dict(),
            registered_at=w.registered_at,
            last_heartbeat=w.last_heartbeat,
            last_status_change=w.last_status_change,
            group_id=w.group_id,
            assigned_job_id=w.assigned_job_id,
            assigned_shard_id=w.assigned_shard_id,
            version=w.version,
            tags=w.tags
        )
        for w in workers
    ]


@router.post("/{worker_id}/assign")
async def assign_job_to_worker(
    worker_id: str,
    job_id: str,
    shard_id: Optional[int] = None,
    registry: WorkerRegistry = Depends(get_registry)
):
    """Assign a job to a worker."""
    success = registry.assign_job(worker_id, job_id, shard_id)
    
    if not success:
        worker = registry.get_worker(worker_id)
        if not worker:
            raise HTTPException(
                status_code=404,
                detail=f"Worker {worker_id} not found"
            )
        else:
            raise HTTPException(
                status_code=400,
                detail=f"Cannot assign job: worker is {worker.status.value}"
            )
    
    return {
        "success": True,
        "message": f"Assigned job {job_id} to worker {worker_id}",
        "worker_id": worker_id,
        "job_id": job_id,
        "shard_id": shard_id
    }


@router.post("/{worker_id}/release")
async def release_job_from_worker(
    worker_id: str,
    registry: WorkerRegistry = Depends(get_registry)
):
    """Release job assignment from worker."""
    success = registry.release_job(worker_id)
    
    if not success:
        raise HTTPException(
            status_code=404,
            detail=f"Worker {worker_id} not found"
        )
    
    return {
        "success": True,
        "message": f"Released job from worker {worker_id}",
        "worker_id": worker_id
    }


@router.post("/{worker_id}/offline")
async def mark_worker_offline(
    worker_id: str,
    reason: str = "Manual",
    registry: WorkerRegistry = Depends(get_registry)
):
    """Manually mark worker as offline."""
    success = registry.mark_offline(worker_id, reason)
    
    if not success:
        raise HTTPException(
            status_code=404,
            detail=f"Worker {worker_id} not found"
        )
    
    return {
        "success": True,
        "message": f"Worker {worker_id} marked offline",
        "worker_id": worker_id,
        "reason": reason
    }


@router.delete("/{worker_id}")
async def remove_worker(
    worker_id: str,
    registry: WorkerRegistry = Depends(get_registry)
):
    """Remove worker from registry."""
    success = registry.remove_worker(worker_id)
    
    if not success:
        raise HTTPException(
            status_code=404,
            detail=f"Worker {worker_id} not found"
        )
    
    return {
        "success": True,
        "message": f"Worker {worker_id} removed from registry",
        "worker_id": worker_id
    }


@router.post("/health-check/run")
async def run_health_check(
    registry: WorkerRegistry = Depends(get_registry)
):
    """
    Manually trigger health check for all workers.
    
    Returns list of workers that changed status.
    """
    health_report = registry.check_worker_health()
    
    return {
        "success": True,
        "message": "Health check completed",
        "offline_workers": health_report["offline"],
        "degraded_workers": health_report["degraded"],
        "total_offline": len(health_report["offline"]),
        "total_degraded": len(health_report["degraded"])
    }


@router.get("/stats/summary", response_model=RegistryStatsResponse)
async def get_registry_stats(
    registry: WorkerRegistry = Depends(get_registry)
):
    """Get worker registry statistics."""
    stats = registry.get_registry_stats()
    
    return RegistryStatsResponse(
        total_workers=stats["total_workers"],
        status_counts=stats["status_counts"],
        total_gpus=stats["total_gpus"],
        total_ram_gb=stats["total_ram_gb"],
        group_counts=stats["group_counts"],
        heartbeat_timeout_seconds=stats["heartbeat_timeout_seconds"]
    )


@router.get("/health")
async def worker_registry_health(
    registry: WorkerRegistry = Depends(get_registry)
):
    """Health check endpoint for worker registry service."""
    stats = registry.get_registry_stats()
    
    return {
        "status": "healthy",
        "total_workers": stats["total_workers"],
        "online_workers": stats["status_counts"].get("online", 0) + 
                         stats["status_counts"].get("idle", 0) + 
                         stats["status_counts"].get("busy", 0),
        "offline_workers": stats["status_counts"].get("offline", 0)
    }
