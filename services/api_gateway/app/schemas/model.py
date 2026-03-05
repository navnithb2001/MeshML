"""Pydantic schemas for custom model management."""

from pydantic import BaseModel, Field, field_validator
from datetime import datetime
from typing import Optional, Dict, Any
from enum import Enum


class ModelStatus(str, Enum):
    """Model lifecycle states."""
    UPLOADING = "uploading"
    VALIDATING = "validating"
    READY = "ready"
    FAILED = "failed"
    DEPRECATED = "deprecated"


class ModelBase(BaseModel):
    """Base model schema with common fields."""
    name: str = Field(..., min_length=1, max_length=255, description="Model name")
    description: Optional[str] = Field(None, description="Model description")
    version: str = Field(default="1.0.0", pattern=r"^\d+\.\d+\.\d+$", description="Semantic version")


class ModelUploadRequest(ModelBase):
    """Request schema for model upload."""
    group_id: int = Field(..., gt=0, description="Group ID that owns this model")
    parent_model_id: Optional[int] = Field(None, gt=0, description="Parent model ID for versioning")
    
    @field_validator("name")
    @classmethod
    def validate_name(cls, v: str) -> str:
        """Validate model name format."""
        if not v.replace("_", "").replace("-", "").isalnum():
            raise ValueError("Model name can only contain alphanumeric characters, hyphens, and underscores")
        return v


class ModelUploadResponse(BaseModel):
    """Response schema after model upload initiation."""
    model_id: int = Field(..., description="Created model ID")
    upload_url: str = Field(..., description="Presigned URL for uploading model.py file")
    expires_in: int = Field(..., description="URL expiration time in seconds")
    instructions: str = Field(
        default="Upload your model.py file using PUT request to upload_url. "
                "File must contain: create_model(), create_dataloader(), and MODEL_METADATA dict.",
        description="Upload instructions"
    )


class ModelMetadata(BaseModel):
    """Schema for MODEL_METADATA dict that must be present in model.py."""
    task_type: str = Field(..., description="Task type: classification, regression, segmentation, etc.")
    input_shape: list[int] = Field(..., description="Expected input tensor shape, e.g., [3, 224, 224]")
    output_shape: list[int] = Field(..., description="Output tensor shape, e.g., [1000]")
    framework: str = Field(default="pytorch", description="ML framework: pytorch, tensorflow, etc.")
    num_classes: Optional[int] = Field(None, gt=0, description="Number of classes for classification")
    loss_function: Optional[str] = Field(None, description="Loss function name")
    optimizer: Optional[str] = Field(None, description="Optimizer name")
    learning_rate: Optional[float] = Field(None, gt=0, description="Default learning rate")
    
    class Config:
        extra = "allow"  # Allow additional custom metadata fields


class ModelValidationStatus(BaseModel):
    """Validation status response."""
    model_id: int
    status: ModelStatus
    validation_error: Optional[str] = None
    validation_details: Optional[Dict[str, Any]] = Field(
        None,
        description="Detailed validation results: syntax_ok, has_create_model, has_create_dataloader, etc."
    )


class ModelResponse(ModelBase):
    """Response schema for model details."""
    id: int
    group_id: int
    uploaded_by_id: int
    gcs_path: str
    status: ModelStatus
    validation_error: Optional[str] = None
    model_metadata: Optional[Dict[str, Any]] = None
    parent_model_id: Optional[int] = None
    created_at: datetime
    updated_at: datetime
    
    class Config:
        from_attributes = True


class ModelListResponse(BaseModel):
    """Response schema for paginated model list."""
    models: list[ModelResponse]
    total: int
    page: int
    page_size: int
    total_pages: int


class ModelUpdate(BaseModel):
    """Schema for updating model metadata."""
    description: Optional[str] = None
    status: Optional[ModelStatus] = None
    version: Optional[str] = Field(None, pattern=r"^\d+\.\d+\.\d+$")


class ModelDeprecateRequest(BaseModel):
    """Request to deprecate a model."""
    reason: str = Field(..., min_length=1, max_length=500, description="Reason for deprecation")
