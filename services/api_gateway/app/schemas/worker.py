"""Worker schemas for request/response validation."""

from datetime import datetime
from typing import Optional, Dict, Any
from uuid import UUID

from pydantic import BaseModel, Field, ConfigDict

from app.models.worker import WorkerType, WorkerStatus


# ============================================================================
# Worker Capabilities Schema
# ============================================================================

class WorkerCapabilities(BaseModel):
    """Worker capabilities schema."""
    
    cpu_cores: int = Field(..., ge=1, le=128, description="Number of CPU cores")
    ram_gb: float = Field(..., gt=0, le=1024, description="RAM in GB")
    gpu_available: bool = Field(default=False, description="GPU available")
    gpu_name: Optional[str] = Field(None, max_length=100, description="GPU model name")
    gpu_memory_gb: Optional[float] = Field(None, gt=0, le=512, description="GPU memory in GB")
    storage_gb: float = Field(..., gt=0, description="Available storage in GB")
    network_speed_mbps: Optional[float] = Field(None, gt=0, description="Network speed in Mbps")
    framework_versions: Dict[str, str] = Field(
        default_factory=dict,
        description="Framework versions (e.g., {'pytorch': '2.0.0', 'tensorflow': '2.12.0'})"
    )


# ============================================================================
# Worker CRUD Schemas
# ============================================================================

class WorkerBase(BaseModel):
    """Base worker schema."""
    
    type: WorkerType = Field(..., description="Worker type (python, cpp, javascript, mobile)")
    version: str = Field(..., min_length=1, max_length=50, description="Worker client version")


class WorkerRegister(WorkerBase):
    """Schema for registering a new worker."""
    
    worker_id: str = Field(..., min_length=1, max_length=255, description="Unique worker ID (provided by client)")
    capabilities: WorkerCapabilities = Field(..., description="Worker hardware/software capabilities")


class WorkerUpdate(BaseModel):
    """Schema for updating worker information."""
    
    capabilities: Optional[WorkerCapabilities] = None
    version: Optional[str] = Field(None, min_length=1, max_length=50)


class WorkerResponse(WorkerBase):
    """Schema for worker responses."""
    
    model_config = ConfigDict(from_attributes=True)
    
    id: str
    user_id: UUID
    status: WorkerStatus
    capabilities: Dict[str, Any]
    current_job_id: Optional[UUID] = None
    current_batch_id: Optional[str] = None
    batches_completed: int
    total_compute_time: int
    consecutive_failures: int
    last_heartbeat: Optional[datetime] = None
    created_at: datetime
    updated_at: datetime


class WorkerDetailResponse(WorkerResponse):
    """Schema for detailed worker responses with user info."""
    
    from app.schemas.user import UserPublicResponse
    
    user: Optional[UserPublicResponse] = None


# ============================================================================
# Heartbeat Schemas
# ============================================================================

class WorkerHeartbeat(BaseModel):
    """Schema for worker heartbeat."""
    
    status: WorkerStatus = Field(..., description="Current worker status")
    current_job_id: Optional[UUID] = Field(None, description="Currently assigned job ID")
    current_batch_id: Optional[str] = Field(None, description="Currently processing batch ID")
    cpu_usage: Optional[float] = Field(None, ge=0, le=100, description="CPU usage percentage")
    memory_usage: Optional[float] = Field(None, ge=0, le=100, description="Memory usage percentage")
    gpu_usage: Optional[float] = Field(None, ge=0, le=100, description="GPU usage percentage")


class HeartbeatResponse(BaseModel):
    """Schema for heartbeat response."""
    
    acknowledged: bool = True
    server_time: datetime
    should_terminate: bool = False
    new_assignment: Optional[Dict[str, Any]] = None


# ============================================================================
# Worker Assignment Schemas
# ============================================================================

class WorkerAssignment(BaseModel):
    """Schema for assigning work to a worker."""
    
    job_id: UUID
    batch_id: str
    batch_data_url: str
    model_weights_url: str
    config: Dict[str, Any]


# ============================================================================
# Worker Statistics Schemas
# ============================================================================

class WorkerStats(BaseModel):
    """Worker statistics schema."""
    
    model_config = ConfigDict(from_attributes=True)
    
    batches_completed: int
    total_compute_time: int
    consecutive_failures: int
    average_batch_time: Optional[float] = None
    success_rate: Optional[float] = None


class WorkerBatchUpdate(BaseModel):
    """Schema for worker batch completion update."""
    
    batch_id: str
    success: bool
    compute_time: int = Field(..., ge=0, description="Compute time in seconds")
    loss: Optional[float] = Field(None, description="Batch loss")
    accuracy: Optional[float] = Field(None, ge=0, le=1.0, description="Batch accuracy")
    error_message: Optional[str] = Field(None, max_length=1000, description="Error message if failed")


# ============================================================================
# Pagination Schemas
# ============================================================================

class WorkerListResponse(BaseModel):
    """Schema for paginated worker list."""
    
    workers: list[WorkerResponse]
    total: int
    page: int
    page_size: int
