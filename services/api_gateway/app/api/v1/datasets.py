"""API endpoints for dataset validation."""

from fastapi import APIRouter, Depends, HTTPException, status, BackgroundTasks
from sqlalchemy.orm import Session
import logging

from app.dependencies import get_db, get_current_verified_user
from app.models.user import User
from app.schemas.dataset import (
    DatasetValidationRequest,
    DatasetValidationStatus,
    DatasetMetadata
)
from app.services.dataset_validator import validate_dataset

logger = logging.getLogger(__name__)
router = APIRouter()


@router.post(
    "/validate",
    response_model=DatasetValidationStatus,
    summary="Validate dataset",
    description="Validate dataset format and structure from GCS path"
)
async def validate_dataset_endpoint(
    request: DatasetValidationRequest,
    current_user: User = Depends(get_current_verified_user)
):
    """
    Validate a dataset stored in GCS.
    
    Supported formats:
    - ImageFolder (class subdirectories)
    - COCO (annotations JSON + images)
    - CSV (image_path, label columns)
    
    Validation checks:
    - Format detection
    - Structure validation
    - File type validation
    - Size limits
    - Class distribution
    """
    logger.info(f"Validating dataset: {request.gcs_path}")
    
    # Verify GCS path format
    if not request.gcs_path.startswith("gs://"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid GCS path. Must start with gs://"
        )
    
    # Run validation
    expected_format = request.expected_format.value if request.expected_format and request.expected_format != "auto" else None
    
    is_valid, metadata, error_message, validation_details = await validate_dataset(
        gcs_path=request.gcs_path,
        expected_format=expected_format
    )
    
    return DatasetValidationStatus(
        is_valid=is_valid,
        format=metadata.get("format") if metadata else None,
        error_message=error_message,
        validation_details=validation_details
    )


@router.get(
    "/formats",
    response_model=dict,
    summary="List supported dataset formats",
    description="Get list of supported dataset formats and their requirements"
)
async def list_supported_formats():
    """
    List all supported dataset formats with descriptions.
    """
    return {
        "supported_formats": [
            {
                "name": "imagefolder",
                "description": "PyTorch ImageFolder format with class subdirectories",
                "structure": "dataset/class1/img1.jpg, dataset/class2/img2.jpg, ...",
                "requirements": [
                    "Top-level directories represent classes",
                    "Images must be in standard formats (jpg, png, etc.)",
                    "Minimum 1 sample per class"
                ]
            },
            {
                "name": "coco",
                "description": "COCO dataset format with annotations JSON",
                "structure": "dataset/annotations.json, dataset/images/*.jpg",
                "requirements": [
                    "Annotations JSON with 'images', 'annotations', 'categories' keys",
                    "Images directory with corresponding image files",
                    "Valid COCO JSON structure"
                ]
            },
            {
                "name": "csv",
                "description": "CSV file with image paths and labels",
                "structure": "dataset/data.csv with columns: image_path, label",
                "requirements": [
                    "CSV file with header row",
                    "'label' column for classifications",
                    "Optional 'image_path' column for image locations"
                ]
            }
        ],
        "limits": {
            "max_dataset_size_gb": 100,
            "max_files_per_dataset": 1_000_000,
            "max_classes": 10_000,
            "min_samples_per_class": 1
        }
    }
