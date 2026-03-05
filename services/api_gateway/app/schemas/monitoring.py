"""Monitoring schemas for metrics and progress tracking."""

from typing import Optional, List, Dict, Any
from datetime import datetime
from pydantic import BaseModel, Field


# ============================================================================
# System Metrics Schemas
# ============================================================================

class DatabaseMetrics(BaseModel):
    """Database connection metrics."""
    
    total_connections: int = Field(..., description="Total database connections")
    active_connections: int = Field(..., description="Active connections")
    idle_connections: int = Field(..., description="Idle connections")


class RedisMetrics(BaseModel):
    """Redis cache metrics."""
    
    connected: bool = Field(..., description="Redis connection status")
    used_memory: Optional[int] = Field(None, description="Used memory in bytes")
    keys: Optional[int] = Field(None, description="Total number of keys")


class WorkerMetrics(BaseModel):
    """Worker fleet metrics."""
    
    total_workers: int = Field(..., description="Total registered workers")
    idle_workers: int = Field(..., description="Workers in IDLE state")
    busy_workers: int = Field(..., description="Workers in BUSY state")
    offline_workers: int = Field(..., description="Workers in OFFLINE state")
    failed_workers: int = Field(..., description="Workers in FAILED state")


class JobMetrics(BaseModel):
    """Job system metrics."""
    
    total_jobs: int = Field(..., description="Total jobs")
    pending_jobs: int = Field(..., description="Jobs in PENDING state")
    ready_jobs: int = Field(..., description="Jobs in READY state")
    running_jobs: int = Field(..., description="Jobs in RUNNING state")
    completed_jobs: int = Field(..., description="Completed jobs")
    failed_jobs: int = Field(..., description="Failed jobs")
    cancelled_jobs: int = Field(..., description="Cancelled jobs")


class SystemMetrics(BaseModel):
    """Overall system metrics."""
    
    timestamp: datetime = Field(..., description="Metrics timestamp")
    uptime_seconds: int = Field(..., description="System uptime in seconds")
    total_users: int = Field(..., description="Total registered users")
    total_groups: int = Field(..., description="Total groups")
    database: DatabaseMetrics
    redis: RedisMetrics
    workers: WorkerMetrics
    jobs: JobMetrics


# ============================================================================
# Job Progress Schemas
# ============================================================================

class JobProgressDetail(BaseModel):
    """Detailed job progress information."""
    
    job_id: str
    job_name: str
    status: str
    
    # Progress
    total_batches: int = Field(..., description="Total batches to process")
    completed_batches: int = Field(..., description="Batches completed")
    progress_percentage: float = Field(..., ge=0, le=100, description="Overall progress percentage")
    
    # Training metrics
    current_epoch: Optional[int] = Field(None, description="Current training epoch")
    total_epochs: Optional[int] = Field(None, description="Total epochs")
    current_loss: Optional[float] = Field(None, description="Current loss value")
    current_accuracy: Optional[float] = Field(None, description="Current accuracy")
    best_loss: Optional[float] = Field(None, description="Best loss achieved")
    best_accuracy: Optional[float] = Field(None, description="Best accuracy achieved")
    
    # Timing
    started_at: Optional[datetime] = Field(None, description="Job start time")
    estimated_completion: Optional[datetime] = Field(None, description="Estimated completion time")
    elapsed_seconds: Optional[int] = Field(None, description="Elapsed time in seconds")
    
    # Resources
    assigned_workers: int = Field(default=0, description="Number of workers assigned")
    active_workers: int = Field(default=0, description="Number of active workers")


class WorkerProgress(BaseModel):
    """Worker progress on specific batch."""
    
    worker_id: str
    batch_id: str
    status: str
    progress_percentage: float = Field(..., ge=0, le=100)
    cpu_usage: Optional[float] = Field(None, description="CPU usage percentage")
    memory_usage: Optional[float] = Field(None, description="Memory usage percentage")
    gpu_usage: Optional[float] = Field(None, description="GPU usage percentage")


class JobProgressWithWorkers(JobProgressDetail):
    """Job progress with worker details."""
    
    workers: List[WorkerProgress] = Field(default_factory=list, description="Worker progress details")


# ============================================================================
# Live Update Schemas (WebSocket)
# ============================================================================

class MetricsUpdate(BaseModel):
    """Real-time metrics update."""
    
    type: str = Field(default="metrics", description="Update type")
    timestamp: datetime
    metrics: SystemMetrics


class JobProgressUpdate(BaseModel):
    """Real-time job progress update."""
    
    type: str = Field(default="job_progress", description="Update type")
    timestamp: datetime
    job_id: str
    progress: JobProgressDetail


class WorkerStatusUpdate(BaseModel):
    """Real-time worker status update."""
    
    type: str = Field(default="worker_status", description="Update type")
    timestamp: datetime
    worker_id: str
    status: str
    current_job_id: Optional[str] = None


class SystemAlert(BaseModel):
    """System alert/notification."""
    
    type: str = Field(default="alert", description="Update type")
    timestamp: datetime
    severity: str = Field(..., description="Alert severity: info, warning, error, critical")
    category: str = Field(..., description="Alert category: worker, job, system, database")
    message: str
    details: Optional[Dict[str, Any]] = None


# ============================================================================
# Statistics Schemas
# ============================================================================

class GroupStatistics(BaseModel):
    """Statistics for a specific group."""
    
    group_id: str
    group_name: str
    total_members: int
    total_jobs: int
    running_jobs: int
    completed_jobs: int
    total_compute_time: int = Field(..., description="Total compute time in seconds")
    total_batches_completed: int


class UserStatistics(BaseModel):
    """Statistics for current user."""
    
    user_id: str
    username: str
    total_groups: int
    total_jobs_created: int
    total_workers_registered: int
    total_compute_contributed: int = Field(..., description="Total compute time contributed in seconds")
    jobs_completed: int
    jobs_running: int
