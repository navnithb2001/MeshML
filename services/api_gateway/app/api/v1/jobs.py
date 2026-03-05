"""Job management API endpoints."""

from typing import Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.orm import Session

from app.core.exceptions import (
    NotFoundError,
    AuthorizationError,
    ValidationError,
)
from app.dependencies import get_db
from app.models.job import JobStatus
from app.models.group import GroupRole
from app.schemas.job import (
    JobCreate,
    JobUpdate,
    JobResponse,
    JobDetailResponse,
    JobListResponse,
    JobStatusUpdate,
    JobMetricsUpdate,
)
from app.crud import job as job_crud, group as group_crud

# TODO: Import current_user dependency once auth is implemented
# from app.dependencies import get_current_user
# from app.models.user import User


router = APIRouter(prefix="/jobs", tags=["jobs"])


# Temporary mock for current user - will be replaced with real auth in TASK-3.5
async def get_current_user_temp():
    """Temporary mock user - REMOVE THIS when auth is implemented."""
    from app.models.user import User
    from uuid import uuid4
    
    user = User(
        id=uuid4(),
        email="test@example.com",
        username="testuser",
        password_hash="mock",
    )
    return user


# ============================================================================
# Job Management Endpoints
# ============================================================================

@router.post(
    "",
    response_model=JobResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create a new training job",
    description="Create a new ML training job. Requires membership in the specified group.",
)
async def create_job(
    job_data: JobCreate,
    db: Session = Depends(get_db),
    current_user = Depends(get_current_user_temp),
):
    """Create a new training job."""
    # Check if user is a member of the group
    if not group_crud.check_member_permission(db, job_data.group_id, current_user.id):
        raise AuthorizationError("Not a member of this group")
    
    # Create the job
    job = job_crud.create_job(db, job_data, current_user.id)
    return job


@router.get(
    "",
    response_model=JobListResponse,
    summary="List user's jobs",
    description="Get all jobs created by the current user.",
)
async def list_user_jobs(
    skip: int = Query(0, ge=0, description="Number of records to skip"),
    limit: int = Query(100, ge=1, le=500, description="Maximum records to return"),
    status: Optional[JobStatus] = Query(None, description="Filter by job status"),
    db: Session = Depends(get_db),
    current_user = Depends(get_current_user_temp),
):
    """List all jobs created by current user."""
    jobs, total = job_crud.get_user_jobs(
        db,
        current_user.id,
        skip=skip,
        limit=limit,
        status=status,
    )
    
    return JobListResponse(
        jobs=jobs,
        total=total,
        page=skip // limit + 1,
        page_size=limit,
    )


@router.get(
    "/group/{group_id}",
    response_model=JobListResponse,
    summary="List group's jobs",
    description="Get all jobs for a specific group.",
)
async def list_group_jobs(
    group_id: UUID,
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=500),
    status: Optional[JobStatus] = Query(None, description="Filter by job status"),
    db: Session = Depends(get_db),
    current_user = Depends(get_current_user_temp),
):
    """List all jobs for a group."""
    # Check if user is a member of the group
    if not group_crud.check_member_permission(db, group_id, current_user.id):
        raise AuthorizationError("Not a member of this group")
    
    jobs, total = job_crud.get_group_jobs(
        db,
        group_id,
        skip=skip,
        limit=limit,
        status=status,
    )
    
    return JobListResponse(
        jobs=jobs,
        total=total,
        page=skip // limit + 1,
        page_size=limit,
    )


@router.get(
    "/{job_id}",
    response_model=JobDetailResponse,
    summary="Get job details",
    description="Get detailed information about a specific job.",
)
async def get_job(
    job_id: UUID,
    db: Session = Depends(get_db),
    current_user = Depends(get_current_user_temp),
):
    """Get job by ID."""
    job = job_crud.get_job_with_relations(db, job_id)
    if not job:
        raise NotFoundError(f"Job {job_id} not found")
    
    # Check if user is a member of the job's group
    if not group_crud.check_member_permission(db, job.group_id, current_user.id):
        raise AuthorizationError("Not a member of this job's group")
    
    # Calculate progress percentage
    if job.total_batches > 0:
        progress_percentage = (job.completed_batches / job.total_batches) * 100
    else:
        progress_percentage = 0.0
    
    return JobDetailResponse(
        **job.__dict__,
        creator=job.created_by_user,
        group=job.group,
        progress_percentage=progress_percentage,
    )


@router.patch(
    "/{job_id}",
    response_model=JobResponse,
    summary="Update job",
    description="Update job information. Only allowed for pending/ready jobs.",
)
async def update_job(
    job_id: UUID,
    job_data: JobUpdate,
    db: Session = Depends(get_db),
    current_user = Depends(get_current_user_temp),
):
    """Update job information."""
    job = job_crud.get_job(db, job_id)
    if not job:
        raise NotFoundError(f"Job {job_id} not found")
    
    # Check if user is the creator
    if job.created_by != current_user.id:
        raise AuthorizationError("Only the job creator can update the job")
    
    updated_job = job_crud.update_job(db, job_id, job_data)
    if not updated_job:
        raise ValidationError("Cannot update job in current status")
    
    return updated_job


@router.delete(
    "/{job_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete job",
    description="Delete a completed, failed, or cancelled job.",
)
async def delete_job(
    job_id: UUID,
    db: Session = Depends(get_db),
    current_user = Depends(get_current_user_temp),
):
    """Delete a job."""
    job = job_crud.get_job(db, job_id)
    if not job:
        raise NotFoundError(f"Job {job_id} not found")
    
    # Check if user is the creator or group admin
    is_creator = job.created_by == current_user.id
    is_admin = group_crud.check_member_permission(db, job.group_id, current_user.id, GroupRole.ADMIN)
    
    if not (is_creator or is_admin):
        raise AuthorizationError("Only the job creator or group admin can delete the job")
    
    success = job_crud.delete_job(db, job_id)
    if not success:
        raise ValidationError("Cannot delete job in current status. Only completed, failed, or cancelled jobs can be deleted.")
    
    return None


# ============================================================================
# Job Control Endpoints
# ============================================================================

@router.post(
    "/{job_id}/start",
    response_model=JobResponse,
    summary="Start job",
    description="Start a ready job (transition from READY to RUNNING).",
)
async def start_job(
    job_id: UUID,
    db: Session = Depends(get_db),
    current_user = Depends(get_current_user_temp),
):
    """Start a job."""
    job = job_crud.get_job(db, job_id)
    if not job:
        raise NotFoundError(f"Job {job_id} not found")
    
    # Check if user is the creator or group admin
    is_creator = job.created_by == current_user.id
    is_admin = group_crud.check_member_permission(db, job.group_id, current_user.id, GroupRole.ADMIN)
    
    if not (is_creator or is_admin):
        raise AuthorizationError("Only the job creator or group admin can start the job")
    
    started_job = job_crud.start_job(db, job_id)
    if not started_job:
        raise ValidationError("Cannot start job. Job must be in READY status.")
    
    return started_job


@router.post(
    "/{job_id}/pause",
    response_model=JobResponse,
    summary="Pause job",
    description="Pause a running job.",
)
async def pause_job(
    job_id: UUID,
    db: Session = Depends(get_db),
    current_user = Depends(get_current_user_temp),
):
    """Pause a running job."""
    job = job_crud.get_job(db, job_id)
    if not job:
        raise NotFoundError(f"Job {job_id} not found")
    
    # Check permissions
    is_creator = job.created_by == current_user.id
    is_admin = group_crud.check_member_permission(db, job.group_id, current_user.id, GroupRole.ADMIN)
    
    if not (is_creator or is_admin):
        raise AuthorizationError("Only the job creator or group admin can pause the job")
    
    paused_job = job_crud.pause_job(db, job_id)
    if not paused_job:
        raise ValidationError("Cannot pause job. Job must be in RUNNING status.")
    
    return paused_job


@router.post(
    "/{job_id}/resume",
    response_model=JobResponse,
    summary="Resume job",
    description="Resume a paused job.",
)
async def resume_job(
    job_id: UUID,
    db: Session = Depends(get_db),
    current_user = Depends(get_current_user_temp),
):
    """Resume a paused job."""
    job = job_crud.get_job(db, job_id)
    if not job:
        raise NotFoundError(f"Job {job_id} not found")
    
    # Check permissions
    is_creator = job.created_by == current_user.id
    is_admin = group_crud.check_member_permission(db, job.group_id, current_user.id, GroupRole.ADMIN)
    
    if not (is_creator or is_admin):
        raise AuthorizationError("Only the job creator or group admin can resume the job")
    
    resumed_job = job_crud.resume_job(db, job_id)
    if not resumed_job:
        raise ValidationError("Cannot resume job. Job must be in PAUSED status.")
    
    return resumed_job


@router.post(
    "/{job_id}/cancel",
    response_model=JobResponse,
    summary="Cancel job",
    description="Cancel a job.",
)
async def cancel_job(
    job_id: UUID,
    db: Session = Depends(get_db),
    current_user = Depends(get_current_user_temp),
):
    """Cancel a job."""
    job = job_crud.get_job(db, job_id)
    if not job:
        raise NotFoundError(f"Job {job_id} not found")
    
    # Check permissions
    is_creator = job.created_by == current_user.id
    is_admin = group_crud.check_member_permission(db, job.group_id, current_user.id, GroupRole.ADMIN)
    
    if not (is_creator or is_admin):
        raise AuthorizationError("Only the job creator or group admin can cancel the job")
    
    cancelled_job = job_crud.cancel_job(db, job_id)
    if not cancelled_job:
        raise ValidationError("Cannot cancel job. Job is already completed, failed, or cancelled.")
    
    return cancelled_job


# ============================================================================
# Job Progress & Metrics Endpoints
# ============================================================================

@router.get(
    "/{job_id}/progress",
    summary="Get job progress",
    description="Get current progress of a job.",
)
async def get_job_progress(
    job_id: UUID,
    db: Session = Depends(get_db),
    current_user = Depends(get_current_user_temp),
):
    """Get job progress."""
    job = job_crud.get_job(db, job_id)
    if not job:
        raise NotFoundError(f"Job {job_id} not found")
    
    # Check if user is a member of the job's group
    if not group_crud.check_member_permission(db, job.group_id, current_user.id):
        raise AuthorizationError("Not a member of this job's group")
    
    # Calculate progress percentage
    if job.total_batches > 0:
        progress_percentage = (job.completed_batches / job.total_batches) * 100
    else:
        progress_percentage = 0.0
    
    return {
        "job_id": str(job.id),
        "status": job.status,
        "current_epoch": job.current_epoch,
        "total_epochs": job.total_epochs,
        "completed_batches": job.completed_batches,
        "total_batches": job.total_batches,
        "failed_batches": job.failed_batches,
        "progress_percentage": progress_percentage,
    }


@router.get(
    "/{job_id}/metrics",
    summary="Get job metrics",
    description="Get training metrics for a job.",
)
async def get_job_metrics(
    job_id: UUID,
    db: Session = Depends(get_db),
    current_user = Depends(get_current_user_temp),
):
    """Get job metrics."""
    job = job_crud.get_job(db, job_id)
    if not job:
        raise NotFoundError(f"Job {job_id} not found")
    
    # Check if user is a member of the job's group
    if not group_crud.check_member_permission(db, job.group_id, current_user.id):
        raise AuthorizationError("Not a member of this job's group")
    
    return {
        "job_id": str(job.id),
        "status": job.status,
        "current_loss": job.current_loss,
        "current_accuracy": job.current_accuracy,
        "best_loss": job.best_loss,
        "best_accuracy": job.best_accuracy,
        "final_loss": job.final_loss,
        "final_accuracy": job.final_accuracy,
    }


@router.post(
    "/{job_id}/metrics",
    response_model=JobResponse,
    summary="Update job metrics",
    description="Update job progress and metrics. Used by workers during training.",
)
async def update_job_metrics(
    job_id: UUID,
    metrics: JobMetricsUpdate,
    db: Session = Depends(get_db),
    current_user = Depends(get_current_user_temp),
):
    """Update job metrics (used by workers)."""
    job = job_crud.get_job(db, job_id)
    if not job:
        raise NotFoundError(f"Job {job_id} not found")
    
    # TODO: In production, this should be restricted to workers or the orchestrator
    # For now, allow group members
    if not group_crud.check_member_permission(db, job.group_id, current_user.id):
        raise AuthorizationError("Not a member of this job's group")
    
    updated_job = job_crud.update_job_metrics(db, job_id, metrics)
    if not updated_job:
        raise NotFoundError(f"Job {job_id} not found")
    
    return updated_job
