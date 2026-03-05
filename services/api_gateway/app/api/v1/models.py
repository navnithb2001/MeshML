"""API endpoints for custom model management."""

from fastapi import APIRouter, Depends, HTTPException, status, Query, BackgroundTasks
from sqlalchemy.orm import Session
from typing import Optional, List
import logging

from app.dependencies import get_db, get_current_user, get_current_verified_user
from app.models.user import User
from app.models.model import ModelStatus
from app.schemas.model import (
    ModelUploadRequest,
    ModelUploadResponse,
    ModelResponse,
    ModelListResponse,
    ModelUpdate,
    ModelValidationStatus,
    ModelDeprecateRequest
)
from app.crud import model as crud_model
from app.crud import group as crud_group
from app.services.validation_tasks import trigger_model_validation

logger = logging.getLogger(__name__)
router = APIRouter()


@router.post(
    "/upload",
    response_model=ModelUploadResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Upload custom model",
    description="Initialize model upload and get presigned URL for uploading model.py file"
)
async def upload_model(
    model_data: ModelUploadRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_verified_user)
):
    """
    Upload a custom PyTorch model.
    
    Process:
    1. Create model entry in database with UPLOADING status
    2. Generate presigned URL for uploading model.py file
    3. User uploads file to presigned URL using PUT request
    4. Validation service automatically validates uploaded file
    
    Required in model.py:
    - create_model() function
    - create_dataloader() function  
    - MODEL_METADATA dict
    """
    # Verify user belongs to group
    group = await crud_group.get_group_by_id(db, model_data.group_id)
    if not group:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Group not found"
        )
    
    # Check if user is member of group
    member = await crud_group.get_group_member(db, model_data.group_id, current_user.id)
    if not member:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You are not a member of this group"
        )
    
    # Verify parent model if provided
    if model_data.parent_model_id:
        parent = await crud_model.get_model_by_id(db, model_data.parent_model_id)
        if not parent:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Parent model not found"
            )
        if parent.group_id != model_data.group_id:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Parent model must belong to the same group"
            )
    
    # Create model entry and generate upload URL
    model, upload_url = await crud_model.create_model_entry(
        db=db,
        model_data=model_data,
        uploaded_by_id=current_user.id
    )
    
    return ModelUploadResponse(
        model_id=model.id,
        upload_url=upload_url,
        expires_in=3600,  # 1 hour
    )


@router.get(
    "/{model_id}",
    response_model=ModelResponse,
    summary="Get model details",
    description="Retrieve details of a specific model"
)
async def get_model(
    model_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Get model by ID."""
    model = await crud_model.get_model_by_id(db, model_id)
    
    if not model:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Model not found"
        )
    
    # Verify user has access to group
    member = await crud_group.get_group_member(db, model.group_id, current_user.id)
    if not member:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You don't have access to this model"
        )
    
    return model


@router.get(
    "/",
    response_model=ModelListResponse,
    summary="List models",
    description="List models with optional filters"
)
async def list_models(
    group_id: Optional[int] = Query(None, description="Filter by group ID"),
    status: Optional[ModelStatus] = Query(None, description="Filter by status"),
    search: Optional[str] = Query(None, description="Search in name/description"),
    page: int = Query(1, ge=1, description="Page number"),
    page_size: int = Query(50, ge=1, le=100, description="Items per page"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    List models with pagination and filters.
    
    - If group_id provided: list models from that group (requires membership)
    - If no group_id: list all models from user's groups
    """
    skip = (page - 1) * page_size
    
    if search:
        # Search mode
        models, total = await crud_model.search_models(
            db=db,
            query=search,
            group_id=group_id,
            skip=skip,
            limit=page_size
        )
    elif group_id:
        # Verify user has access
        member = await crud_group.get_group_member(db, group_id, current_user.id)
        if not member:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="You don't have access to this group"
            )
        
        models, total = await crud_model.get_models_by_group(
            db=db,
            group_id=group_id,
            status=status,
            skip=skip,
            limit=page_size
        )
    else:
        # List user's models
        models, total = await crud_model.get_models_by_user(
            db=db,
            user_id=current_user.id,
            skip=skip,
            limit=page_size
        )
    
    total_pages = (total + page_size - 1) // page_size
    
    return ModelListResponse(
        models=models,
        total=total,
        page=page,
        page_size=page_size,
        total_pages=total_pages
    )


@router.get(
    "/{model_id}/status",
    response_model=ModelValidationStatus,
    summary="Get model validation status",
    description="Check validation status of uploaded model"
)
async def get_model_status(
    model_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Get model validation status."""
    model = await crud_model.get_model_by_id(db, model_id)
    
    if not model:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Model not found"
        )
    
    # Verify access
    member = await crud_group.get_group_member(db, model.group_id, current_user.id)
    if not member:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You don't have access to this model"
        )
    
    # Extract validation details from metadata if available
    validation_details = None
    if model.model_metadata and "validation" in model.model_metadata:
        validation_details = model.model_metadata["validation"]
    
    return ModelValidationStatus(
        model_id=model.id,
        status=model.status,
        validation_error=model.validation_error,
        validation_details=validation_details
    )


@router.patch(
    "/{model_id}",
    response_model=ModelResponse,
    summary="Update model metadata",
    description="Update model description, version, or status"
)
async def update_model(
    model_id: int,
    update_data: ModelUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_verified_user)
):
    """Update model metadata."""
    model = await crud_model.get_model_by_id(db, model_id)
    
    if not model:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Model not found"
        )
    
    # Only owner or group admin can update
    member = await crud_group.get_group_member(db, model.group_id, current_user.id)
    if not member:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You don't have access to this model"
        )
    
    if model.uploaded_by_id != current_user.id and member.role != "admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only model owner or group admin can update"
        )
    
    updated_model = await crud_model.update_model(
        db=db,
        model_id=model_id,
        update_data=update_data
    )
    
    return updated_model


@router.post(
    "/{model_id}/deprecate",
    response_model=ModelResponse,
    summary="Deprecate model",
    description="Mark model as deprecated"
)
async def deprecate_model(
    model_id: int,
    deprecate_data: ModelDeprecateRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_verified_user)
):
    """Deprecate a model."""
    model = await crud_model.get_model_by_id(db, model_id)
    
    if not model:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Model not found"
        )
    
    # Only owner or group admin can deprecate
    member = await crud_group.get_group_member(db, model.group_id, current_user.id)
    if not member:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You don't have access to this model"
        )
    
    if model.uploaded_by_id != current_user.id and member.role != "admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only model owner or group admin can deprecate"
        )
    
    deprecated_model = await crud_model.deprecate_model(
        db=db,
        model_id=model_id,
        reason=deprecate_data.reason
    )
    
    return deprecated_model


@router.delete(
    "/{model_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete model",
    description="Permanently delete model and its file from storage"
)
async def delete_model(
    model_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_verified_user)
):
    """Delete model."""
    model = await crud_model.get_model_by_id(db, model_id)
    
    if not model:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Model not found"
        )
    
    # Only owner or group admin can delete
    member = await crud_group.get_group_member(db, model.group_id, current_user.id)
    if not member:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You don't have access to this model"
        )
    
    if model.uploaded_by_id != current_user.id and member.role != "admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only model owner or group admin can delete"
        )
    
    # Check if model is used by any active jobs
    if model.jobs:
        active_jobs = [j for j in model.jobs if j.status not in ["completed", "failed", "cancelled"]]
        if active_jobs:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Cannot delete model: {len(active_jobs)} active jobs are using it"
            )
    
    await crud_model.delete_model(db, model_id)
    
    return None


@router.post(
    "/{model_id}/validate",
    response_model=ModelValidationStatus,
    summary="Trigger model validation",
    description="Manually trigger validation for an uploaded model"
)
async def validate_model(
    model_id: int,
    background_tasks: BackgroundTasks,
    skip_instantiation: bool = Query(False, description="Skip model instantiation test"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_verified_user)
):
    """
    Manually trigger model validation.
    
    This endpoint is useful for:
    - Re-validating a model after fixing errors
    - Forcing validation if automatic validation failed
    - Testing validation logic
    
    Validation runs in the background and updates model status.
    """
    model = await crud_model.get_model_by_id(db, model_id)
    
    if not model:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Model not found"
        )
    
    # Verify user has access
    member = await crud_group.get_group_member(db, model.group_id, current_user.id)
    if not member:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You don't have access to this model"
        )
    
    # Only owner or admin can trigger validation
    if model.uploaded_by_id != current_user.id and member.role != "admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only model owner or group admin can trigger validation"
        )
    
    # Check if model has a file uploaded
    if model.status == ModelStatus.UPLOADING:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Model file not uploaded yet. Upload file first using the presigned URL."
        )
    
    # Trigger validation in background
    background_tasks.add_task(
        trigger_model_validation,
        db=db,
        model_id=model_id,
        gcs_path=model.gcs_path,
        skip_instantiation=skip_instantiation
    )
    
    return ModelValidationStatus(
        model_id=model.id,
        status=ModelStatus.VALIDATING,
        validation_error=None,
        validation_details={"message": "Validation started in background"}
    )

