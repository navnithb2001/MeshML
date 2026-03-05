"""CRUD operations for custom model management."""

from sqlalchemy.orm import Session
from sqlalchemy import select, and_, or_
from typing import Optional, List
from datetime import datetime
import logging

from app.models.model import Model, ModelStatus
from app.schemas.model import (
    ModelUploadRequest,
    ModelUpdate,
    ModelMetadata
)
from app.core.storage import get_model_storage

logger = logging.getLogger(__name__)


async def create_model_entry(
    db: Session,
    model_data: ModelUploadRequest,
    uploaded_by_id: int
) -> tuple[Model, str]:
    """
    Create model entry in database and generate upload URL.
    
    Args:
        db: Database session
        model_data: Model upload request data
        uploaded_by_id: User ID of uploader
        
    Returns:
        Tuple of (Model instance, presigned upload URL)
    """
    # Create model entry
    model = Model(
        name=model_data.name,
        description=model_data.description,
        uploaded_by_id=uploaded_by_id,
        group_id=model_data.group_id,
        version=model_data.version,
        parent_model_id=model_data.parent_model_id,
        status=ModelStatus.UPLOADING,
        gcs_path="",  # Will be set after upload
    )
    
    db.add(model)
    db.flush()  # Get model.id without committing
    
    # Generate GCS path and presigned URL
    blob_path = f"{model.id}/model.py"
    gcs_path = f"gs://{get_model_storage().bucket_name}/{blob_path}"
    
    # Update GCS path
    model.gcs_path = gcs_path
    db.commit()
    db.refresh(model)
    
    # Generate presigned upload URL (1 hour expiration)
    upload_url = get_model_storage().generate_presigned_upload_url(
        blob_path=blob_path,
        content_type="text/x-python",
        expires_in=3600
    )
    
    logger.info(f"Created model entry {model.id} for user {uploaded_by_id}")
    return model, upload_url


async def get_model_by_id(db: Session, model_id: int) -> Optional[Model]:
    """Get model by ID."""
    stmt = select(Model).where(Model.id == model_id)
    result = db.execute(stmt)
    return result.scalar_one_or_none()


async def get_models_by_group(
    db: Session,
    group_id: int,
    status: Optional[ModelStatus] = None,
    skip: int = 0,
    limit: int = 100
) -> tuple[List[Model], int]:
    """
    Get models for a specific group with optional status filter.
    
    Args:
        db: Database session
        group_id: Group ID
        status: Optional status filter
        skip: Pagination offset
        limit: Page size
        
    Returns:
        Tuple of (list of models, total count)
    """
    # Build query
    stmt = select(Model).where(Model.group_id == group_id)
    
    if status:
        stmt = stmt.where(Model.status == status)
    
    # Get total count
    count_stmt = select(Model.id).where(Model.group_id == group_id)
    if status:
        count_stmt = count_stmt.where(Model.status == status)
    total = len(db.execute(count_stmt).scalars().all())
    
    # Apply pagination and ordering
    stmt = stmt.order_by(Model.created_at.desc()).offset(skip).limit(limit)
    
    result = db.execute(stmt)
    models = result.scalars().all()
    
    return list(models), total


async def get_models_by_user(
    db: Session,
    user_id: int,
    skip: int = 0,
    limit: int = 100
) -> tuple[List[Model], int]:
    """Get models uploaded by a specific user."""
    stmt = select(Model).where(Model.uploaded_by_id == user_id)
    
    # Get total count
    count_stmt = select(Model.id).where(Model.uploaded_by_id == user_id)
    total = len(db.execute(count_stmt).scalars().all())
    
    # Apply pagination
    stmt = stmt.order_by(Model.created_at.desc()).offset(skip).limit(limit)
    
    result = db.execute(stmt)
    models = result.scalars().all()
    
    return list(models), total


async def update_model_status(
    db: Session,
    model_id: int,
    status: ModelStatus,
    validation_error: Optional[str] = None,
    model_metadata: Optional[dict] = None
) -> Optional[Model]:
    """
    Update model validation status.
    
    Args:
        db: Database session
        model_id: Model ID
        status: New status
        validation_error: Error message if validation failed
        model_metadata: Extracted MODEL_METADATA dict
        
    Returns:
        Updated model or None
    """
    model = await get_model_by_id(db, model_id)
    
    if not model:
        return None
    
    model.status = status
    model.validation_error = validation_error
    
    if model_metadata:
        model.model_metadata = model_metadata
    
    db.commit()
    db.refresh(model)
    
    logger.info(f"Updated model {model_id} status to {status}")
    return model


async def update_model(
    db: Session,
    model_id: int,
    update_data: ModelUpdate
) -> Optional[Model]:
    """Update model metadata."""
    model = await get_model_by_id(db, model_id)
    
    if not model:
        return None
    
    # Update only provided fields
    update_dict = update_data.model_dump(exclude_unset=True)
    
    for field, value in update_dict.items():
        setattr(model, field, value)
    
    db.commit()
    db.refresh(model)
    
    logger.info(f"Updated model {model_id}")
    return model


async def deprecate_model(
    db: Session,
    model_id: int,
    reason: str
) -> Optional[Model]:
    """
    Deprecate a model.
    
    Args:
        db: Database session
        model_id: Model ID
        reason: Deprecation reason
        
    Returns:
        Updated model or None
    """
    model = await get_model_by_id(db, model_id)
    
    if not model:
        return None
    
    model.status = ModelStatus.DEPRECATED
    model.validation_error = f"DEPRECATED: {reason}"
    
    db.commit()
    db.refresh(model)
    
    logger.info(f"Deprecated model {model_id}: {reason}")
    return model


async def delete_model(db: Session, model_id: int) -> bool:
    """
    Delete model from database and GCS.
    
    Args:
        db: Database session
        model_id: Model ID
        
    Returns:
        True if deleted successfully
    """
    model = await get_model_by_id(db, model_id)
    
    if not model:
        return False
    
    # Extract blob path from gcs_path
    # Format: gs://bucket-name/path/to/file.py -> path/to/file.py
    blob_path = model.gcs_path.split(f"{get_model_storage().bucket_name}/", 1)[-1]
    
    # Delete from GCS
    try:
        get_model_storage().delete_file(blob_path)
    except Exception as e:
        logger.warning(f"Failed to delete GCS file for model {model_id}: {e}")
    
    # Delete from database
    db.delete(model)
    db.commit()
    
    logger.info(f"Deleted model {model_id}")
    return True


async def search_models(
    db: Session,
    query: str,
    group_id: Optional[int] = None,
    skip: int = 0,
    limit: int = 100
) -> tuple[List[Model], int]:
    """
    Search models by name or description.
    
    Args:
        db: Database session
        query: Search query
        group_id: Optional group filter
        skip: Pagination offset
        limit: Page size
        
    Returns:
        Tuple of (list of models, total count)
    """
    search_pattern = f"%{query}%"
    
    stmt = select(Model).where(
        or_(
            Model.name.ilike(search_pattern),
            Model.description.ilike(search_pattern)
        )
    )
    
    if group_id:
        stmt = stmt.where(Model.group_id == group_id)
    
    # Count
    count_stmt = select(Model.id).where(
        or_(
            Model.name.ilike(search_pattern),
            Model.description.ilike(search_pattern)
        )
    )
    if group_id:
        count_stmt = count_stmt.where(Model.group_id == group_id)
    
    total = len(db.execute(count_stmt).scalars().all())
    
    # Paginate
    stmt = stmt.order_by(Model.created_at.desc()).offset(skip).limit(limit)
    
    result = db.execute(stmt)
    models = result.scalars().all()
    
    return list(models), total
