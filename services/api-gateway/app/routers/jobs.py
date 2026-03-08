"""
Job management endpoints

Endpoints:
- POST /api/jobs - Submit new training job
- GET /api/jobs - List jobs
- GET /api/jobs/{job_id} - Get job details
- DELETE /api/jobs/{job_id} - Cancel job
- GET /api/jobs/{job_id}/progress - Get training progress
"""

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from typing import List, Optional
import logging
import uuid

from app.utils.database import get_db
from app.models.job import Job
from app.models.group import GroupMember
from app.models.user import User
from app.routers.auth import get_current_user
from app.schemas.job import (
    JobCreateRequest,
    JobResponse,
    JobProgressResponse
)

logger = logging.getLogger(__name__)
router = APIRouter()


@router.post("", response_model=JobResponse, status_code=status.HTTP_201_CREATED)
async def create_job(
    request: JobCreateRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Submit new training job
    
    Args:
        request: Job configuration
        current_user: Authenticated user
        db: Database session
        
    Returns:
        Created job information
        
    Raises:
        403: Not member of group
    """
    logger.info(f"Creating job for group {request.group_id}")
    
    # Verify user is member of group
    member_result = await db.execute(
        select(GroupMember).where(
            GroupMember.group_id == request.group_id,
            GroupMember.user_id == current_user.id
        )
    )
    member = member_result.scalar_one_or_none()
    
    if not member:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not a member of this group"
        )
    
    # Create job
    job = Job(
        id=str(uuid.uuid4()),
        group_id=request.group_id,
        model_id=request.model_id,
        dataset_id=request.dataset_id,
        config=request.config,
        created_by=current_user.id,
        status="pending"
    )
    
    db.add(job)
    await db.commit()
    await db.refresh(job)
    
    logger.info(f"Job created: {job.id}")
    return job


@router.get("", response_model=List[JobResponse])
async def list_jobs(
    group_id: Optional[str] = None,
    status: Optional[str] = None,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    List jobs (filtered by group and/or status)
    
    Args:
        group_id: Filter by group
        status: Filter by status
        current_user: Authenticated user
        db: Database session
        
    Returns:
        List of jobs
    """
    query = select(Job)
    
    if group_id:
        # Verify membership
        member_result = await db.execute(
            select(GroupMember).where(
                GroupMember.group_id == group_id,
                GroupMember.user_id == current_user.id
            )
        )
        if not member_result.scalar_one_or_none():
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Not a member of this group"
            )
        query = query.where(Job.group_id == group_id)
    
    if status:
        query = query.where(Job.status == status)
    
    result = await db.execute(query)
    jobs = result.scalars().all()
    
    logger.info(f"Retrieved {len(jobs)} jobs")
    return jobs


@router.get("/{job_id}", response_model=JobResponse)
async def get_job(
    job_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Get job details
    
    Args:
        job_id: Job ID
        current_user: Authenticated user
        db: Database session
        
    Returns:
        Job information
        
    Raises:
        404: Job not found
        403: Not authorized
    """
    result = await db.execute(
        select(Job).where(Job.id == job_id)
    )
    job = result.scalar_one_or_none()
    
    if not job:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Job not found"
        )
    
    # Verify membership
    member_result = await db.execute(
        select(GroupMember).where(
            GroupMember.group_id == job.group_id,
            GroupMember.user_id == current_user.id
        )
    )
    if not member_result.scalar_one_or_none():
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not authorized to view this job"
        )
    
    return job


@router.delete("/{job_id}", status_code=status.HTTP_204_NO_CONTENT)
async def cancel_job(
    job_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Cancel running job
    
    Args:
        job_id: Job ID
        current_user: Authenticated user
        db: Database session
        
    Raises:
        404: Job not found
        403: Not authorized
    """
    result = await db.execute(
        select(Job).where(Job.id == job_id)
    )
    job = result.scalar_one_or_none()
    
    if not job:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Job not found"
        )
    
    # Only creator can cancel
    if str(job.created_by) != str(current_user.id):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only job creator can cancel"
        )
    
    job.status = "cancelled"
    await db.commit()
    
    logger.info(f"Job cancelled: {job_id}")


@router.get("/{job_id}/progress", response_model=JobProgressResponse)
async def get_job_progress(
    job_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Get training progress for job
    
    Args:
        job_id: Job ID
        current_user: Authenticated user
        db: Database session
        
    Returns:
        Progress metrics
        
    Raises:
        404: Job not found
        403: Not authorized
    """
    result = await db.execute(
        select(Job).where(Job.id == job_id)
    )
    job = result.scalar_one_or_none()
    
    if not job:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Job not found"
        )
    
    # Verify membership
    member_result = await db.execute(
        select(GroupMember).where(
            GroupMember.group_id == job.group_id,
            GroupMember.user_id == current_user.id
        )
    )
    if not member_result.scalar_one_or_none():
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not authorized to view this job"
        )
    
    # TODO: Get actual progress from Redis/metrics service
    progress = job.progress or {}
    
    return JobProgressResponse(
        job_id=job_id,
        status=job.status,
        current_epoch=progress.get("current_epoch", 0),
        total_epochs=progress.get("total_epochs", 0),
        current_batch=progress.get("current_batch", 0),
        total_batches=progress.get("total_batches", 0),
        loss=progress.get("loss", 0.0),
        accuracy=progress.get("accuracy", 0.0),
        worker_count=progress.get("worker_count", 0)
    )
