"""Job schemas for request/response validation."""

from datetime import datetime
from typing import Optional, Dict, Any
from uuid import UUID

from pydantic import BaseModel, Field, ConfigDict

from app.models.job import JobStatus


# ============================================================================
# Job Configuration Schemas
# ============================================================================

class JobConfig(BaseModel):
    """Job configuration schema."""
    
    batch_size: int = Field(default=32, ge=1, le=1024, description="Training batch size")
    learning_rate: float = Field(default=0.001, gt=0, le=1.0, description="Learning rate")
    optimizer: str = Field(default="adam", description="Optimizer type (adam, sgd, rmsprop)")
    loss_function: str = Field(default="cross_entropy", description="Loss function")
    num_workers: int = Field(default=4, ge=1, le=100, description="Number of workers to use")
    gradient_accumulation_steps: int = Field(default=1, ge=1, description="Gradient accumulation steps")
    early_stopping_patience: int = Field(default=5, ge=1, description="Early stopping patience (epochs)")
    target_accuracy: Optional[float] = Field(None, ge=0, le=1.0, description="Target accuracy to achieve")
    

class JobMetrics(BaseModel):
    """Job metrics schema."""
    
    model_config = ConfigDict(from_attributes=True)
    
    current_loss: Optional[float] = None
    current_accuracy: Optional[float] = None
    best_loss: Optional[float] = None
    best_accuracy: Optional[float] = None
    final_loss: Optional[float] = None
    final_accuracy: Optional[float] = None


class JobProgress(BaseModel):
    """Job progress schema."""
    
    model_config = ConfigDict(from_attributes=True)
    
    current_epoch: int = 0
    total_epochs: int
    completed_batches: int = 0
    total_batches: int = 0
    failed_batches: int = 0
    progress_percentage: float = 0.0


# ============================================================================
# Job CRUD Schemas
# ============================================================================

class JobBase(BaseModel):
    """Base job schema with common fields."""
    
    name: str = Field(..., min_length=3, max_length=100, description="Job name")
    description: Optional[str] = Field(None, max_length=1000, description="Job description")


class JobCreate(JobBase):
    """Schema for creating a new job."""
    
    group_id: UUID = Field(..., description="Group ID this job belongs to")
    model_id: Optional[UUID] = Field(None, description="Model ID to use for training")
    dataset_url: str = Field(..., min_length=1, max_length=512, description="Dataset storage URL")
    total_epochs: int = Field(..., ge=1, le=1000, description="Total training epochs")
    config: JobConfig = Field(..., description="Job configuration")


class JobUpdate(BaseModel):
    """Schema for updating a job."""
    
    name: Optional[str] = Field(None, min_length=3, max_length=100)
    description: Optional[str] = Field(None, max_length=1000)
    config: Optional[JobConfig] = None


class JobResponse(JobBase):
    """Schema for job responses."""
    
    model_config = ConfigDict(from_attributes=True)
    
    id: UUID
    group_id: UUID
    model_id: Optional[UUID] = None
    created_by: Optional[UUID] = None
    dataset_url: str
    status: JobStatus
    config: Dict[str, Any]
    total_epochs: int
    current_epoch: int
    total_batches: int
    completed_batches: int
    failed_batches: int
    current_loss: Optional[float] = None
    current_accuracy: Optional[float] = None
    best_loss: Optional[float] = None
    best_accuracy: Optional[float] = None
    created_at: datetime
    updated_at: datetime


class JobDetailResponse(JobResponse):
    """Schema for detailed job responses with creator info."""
    
    from app.schemas.user import UserPublicResponse
    from app.schemas.group import GroupResponse
    
    creator: Optional[UserPublicResponse] = None
    group: Optional[GroupResponse] = None
    progress_percentage: float = 0.0


class JobStatusUpdate(BaseModel):
    """Schema for job status updates."""
    
    status: JobStatus


class JobMetricsUpdate(BaseModel):
    """Schema for updating job metrics during training."""
    
    current_epoch: int = Field(..., ge=0)
    current_loss: Optional[float] = Field(None, gt=0)
    current_accuracy: Optional[float] = Field(None, ge=0, le=1.0)
    completed_batches: int = Field(default=0, ge=0)
    failed_batches: int = Field(default=0, ge=0)


# ============================================================================
# Pagination Schemas
# ============================================================================

class JobListResponse(BaseModel):
    """Schema for paginated job list."""
    
    jobs: list[JobResponse]
    total: int
    page: int
    page_size: int
