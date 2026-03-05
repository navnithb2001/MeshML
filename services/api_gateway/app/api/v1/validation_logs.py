"""API endpoints for validation logs."""

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from typing import List, Optional
from datetime import datetime, timedelta

from app.core.database import get_db
from app.core.auth import get_current_user
from app.schemas.user import User
from app.crud import validation_log as crud
from services.database.models.validation_log import ValidationType
from app.services.error_reporting import ValidationReport

router = APIRouter(prefix="/validation-logs", tags=["validation-logs"])


@router.get("/{log_id}")
async def get_validation_log(
    log_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Get a specific validation log by ID."""
    log = await crud.get_validation_log_by_id(db, log_id)
    
    if not log:
        raise HTTPException(status_code=404, detail="Validation log not found")
    
    return {
        "id": log.id,
        "validation_type": log.validation_type.value,
        "resource_id": log.resource_id,
        "status": log.status.value,
        "is_valid": log.is_valid,
        "error_count": log.error_count,
        "warning_count": log.warning_count,
        "created_at": log.created_at.isoformat(),
        "summary": log.summary,
        "validation_report": log.validation_report
    }


@router.get("/")
async def get_validation_history(
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=100),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Get validation history for the current user."""
    logs, total = await crud.get_user_validation_history(
        db=db,
        user_id=current_user.id,
        skip=skip,
        limit=limit
    )
    
    return {
        "logs": [
            {
                "id": log.id,
                "validation_type": log.validation_type.value,
                "resource_id": log.resource_id,
                "status": log.status.value,
                "is_valid": log.is_valid,
                "error_count": log.error_count,
                "warning_count": log.warning_count,
                "created_at": log.created_at.isoformat(),
                "summary": log.summary
            }
            for log in logs
        ],
        "total": total,
        "skip": skip,
        "limit": limit
    }


@router.get("/models/{model_id}")
async def get_model_validation_logs(
    model_id: int,
    limit: int = Query(10, ge=1, le=50),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Get validation logs for a specific model."""
    logs = await crud.get_validation_logs_for_resource(
        db=db,
        resource_id=str(model_id),
        validation_type=ValidationType.MODEL,
        limit=limit
    )
    
    return {
        "model_id": model_id,
        "logs": [
            {
                "id": log.id,
                "status": log.status.value,
                "is_valid": log.is_valid,
                "error_count": log.error_count,
                "warning_count": log.warning_count,
                "created_at": log.created_at.isoformat(),
                "summary": log.summary,
                "validation_report": log.validation_report
            }
            for log in logs
        ]
    }


@router.get("/datasets/by-path")
async def get_dataset_validation_logs(
    dataset_path: str = Query(..., description="GCS path to the dataset"),
    limit: int = Query(10, ge=1, le=50),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Get validation logs for a specific dataset."""
    logs = await crud.get_validation_logs_for_resource(
        db=db,
        resource_id=dataset_path,
        validation_type=ValidationType.DATASET,
        limit=limit
    )
    
    return {
        "dataset_path": dataset_path,
        "logs": [
            {
                "id": log.id,
                "status": log.status.value,
                "is_valid": log.is_valid,
                "error_count": log.error_count,
                "warning_count": log.warning_count,
                "created_at": log.created_at.isoformat(),
                "summary": log.summary,
                "validation_report": log.validation_report
            }
            for log in logs
        ]
    }


@router.get("/stats")
async def get_validation_statistics(
    days: int = Query(30, ge=1, le=365, description="Number of days to look back"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Get validation statistics for the specified time period."""
    since = datetime.utcnow() - timedelta(days=days)
    stats = await crud.get_validation_stats(db=db, since=since)
    
    return stats


@router.get("/failed")
async def get_recent_failures(
    limit: int = Query(50, ge=1, le=100),
    days: Optional[int] = Query(None, ge=1, le=90, description="Filter by days"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Get recent failed validations."""
    since = None
    if days:
        since = datetime.utcnow() - timedelta(days=days)
    
    logs = await crud.get_failed_validations(
        db=db,
        since=since,
        limit=limit
    )
    
    return {
        "failures": [
            {
                "id": log.id,
                "validation_type": log.validation_type.value,
                "resource_id": log.resource_id,
                "error_count": log.error_count,
                "created_at": log.created_at.isoformat(),
                "summary": log.summary
            }
            for log in logs
        ],
        "total": len(logs)
    }
