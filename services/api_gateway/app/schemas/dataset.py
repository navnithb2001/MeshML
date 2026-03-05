"""Pydantic schemas for dataset validation."""

from pydantic import BaseModel, Field
from typing import Optional, Dict, Any
from enum import Enum


class DatasetFormat(str, Enum):
    """Supported dataset formats."""
    IMAGEFOLDER = "imagefolder"
    COCO = "coco"
    CSV = "csv"
    JSON = "json"
    AUTO = "auto"  # Auto-detect format


class DatasetValidationRequest(BaseModel):
    """Request schema for dataset validation."""
    gcs_path: str = Field(..., description="GCS path to dataset (gs://bucket/path/to/dataset)")
    expected_format: Optional[DatasetFormat] = Field(
        None,
        description="Expected dataset format (auto-detect if not specified)"
    )


class DatasetValidationStatus(BaseModel):
    """Dataset validation status response."""
    is_valid: bool
    format: Optional[str] = None
    error_message: Optional[str] = None
    validation_details: Dict[str, Any] = Field(default_factory=dict)


class DatasetMetadata(BaseModel):
    """Dataset metadata extracted from validation."""
    format: str = Field(..., description="Dataset format")
    num_classes: int = Field(..., description="Number of classes/categories")
    total_samples: int = Field(..., description="Total number of samples")
    class_distribution: Dict[str, int] = Field(
        default_factory=dict,
        description="Distribution of samples per class"
    )
    size_bytes: int = Field(..., description="Dataset size in bytes")
    size_gb: float = Field(..., description="Dataset size in GB")
    
    class Config:
        extra = "allow"


class DatasetInfo(BaseModel):
    """General dataset information."""
    gcs_path: str
    format: Optional[str] = None
    metadata: Optional[DatasetMetadata] = None
    validated: bool = False
    validation_error: Optional[str] = None
