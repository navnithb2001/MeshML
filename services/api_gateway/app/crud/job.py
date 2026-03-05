"""CRUD operations for job management."""

from datetime import datetime
from typing import Optional, List
from uuid import UUID

from sqlalchemy import and_, or_
from sqlalchemy.orm import Session, joinedload

from app.models.job import Job, JobStatus
from app.schemas.job import JobCreate, JobUpdate, JobMetricsUpdate


# ============================================================================
# Job CRUD
# ============================================================================

def create_job(db: Session, job_data: JobCreate, creator_id: UUID) -> Job:
    """Create a new training job."""
    # Convert config to dict
    config_dict = job_data.config.model_dump()
    
    job = Job(
        name=job_data.name,
        description=job_data.description,
        group_id=job_data.group_id,
        model_id=job_data.model_id,
        created_by=creator_id,
        dataset_url=job_data.dataset_url,
        total_epochs=job_data.total_epochs,
        config=config_dict,
        status=JobStatus.PENDING,
    )
    
    db.add(job)
    db.commit()
    db.refresh(job)
    
    return job


def get_job(db: Session, job_id: UUID) -> Optional[Job]:
    """Get job by ID."""
    return db.query(Job).filter(Job.id == job_id).first()


def get_job_with_relations(db: Session, job_id: UUID) -> Optional[Job]:
    """Get job with creator and group relationships loaded."""
    return (
        db.query(Job)
        .options(
            joinedload(Job.created_by_user),
            joinedload(Job.group),
            joinedload(Job.model),
        )
        .filter(Job.id == job_id)
        .first()
    )


def get_group_jobs(
    db: Session,
    group_id: UUID,
    skip: int = 0,
    limit: int = 100,
    status: Optional[JobStatus] = None,
) -> tuple[List[Job], int]:
    """Get all jobs for a group."""
    query = db.query(Job).filter(Job.group_id == group_id)
    
    if status:
        query = query.filter(Job.status == status)
    
    # Get total count
    total = query.count()
    
    # Get paginated results
    jobs = query.order_by(Job.created_at.desc()).offset(skip).limit(limit).all()
    
    return jobs, total


def get_user_jobs(
    db: Session,
    user_id: UUID,
    skip: int = 0,
    limit: int = 100,
    status: Optional[JobStatus] = None,
) -> tuple[List[Job], int]:
    """Get all jobs created by a user."""
    query = db.query(Job).filter(Job.created_by == user_id)
    
    if status:
        query = query.filter(Job.status == status)
    
    total = query.count()
    jobs = query.order_by(Job.created_at.desc()).offset(skip).limit(limit).all()
    
    return jobs, total


def update_job(db: Session, job_id: UUID, job_data: JobUpdate) -> Optional[Job]:
    """Update job information."""
    job = get_job(db, job_id)
    if not job:
        return None
    
    # Only allow updates for jobs that haven't started
    if job.status not in [JobStatus.PENDING, JobStatus.READY]:
        return None
    
    # Update basic fields
    if job_data.name is not None:
        job.name = job_data.name
    if job_data.description is not None:
        job.description = job_data.description
    
    # Update config
    if job_data.config:
        job.config = job_data.config.model_dump()
    
    db.commit()
    db.refresh(job)
    return job


def update_job_status(db: Session, job_id: UUID, status: JobStatus) -> Optional[Job]:
    """Update job status."""
    job = get_job(db, job_id)
    if not job:
        return None
    
    job.status = status
    db.commit()
    db.refresh(job)
    return job


def update_job_metrics(
    db: Session,
    job_id: UUID,
    metrics: JobMetricsUpdate,
) -> Optional[Job]:
    """Update job progress and metrics during training."""
    job = get_job(db, job_id)
    if not job:
        return None
    
    # Update progress
    job.current_epoch = metrics.current_epoch
    job.completed_batches = metrics.completed_batches
    job.failed_batches = metrics.failed_batches
    
    # Update current metrics
    if metrics.current_loss is not None:
        job.current_loss = metrics.current_loss
        
        # Update best loss if better
        if job.best_loss is None or metrics.current_loss < job.best_loss:
            job.best_loss = metrics.current_loss
    
    if metrics.current_accuracy is not None:
        job.current_accuracy = metrics.current_accuracy
        
        # Update best accuracy if better
        if job.best_accuracy is None or metrics.current_accuracy > job.best_accuracy:
            job.best_accuracy = metrics.current_accuracy
    
    db.commit()
    db.refresh(job)
    return job


def set_job_sharding_complete(
    db: Session,
    job_id: UUID,
    total_batches: int,
) -> Optional[Job]:
    """Mark job as sharded and set total batches."""
    job = get_job(db, job_id)
    if not job:
        return None
    
    job.status = JobStatus.READY
    job.total_batches = total_batches
    
    db.commit()
    db.refresh(job)
    return job


def start_job(db: Session, job_id: UUID) -> Optional[Job]:
    """Start a job (transition from READY to RUNNING)."""
    job = get_job(db, job_id)
    if not job:
        return None
    
    if job.status != JobStatus.READY:
        return None
    
    job.status = JobStatus.RUNNING
    db.commit()
    db.refresh(job)
    return job


def pause_job(db: Session, job_id: UUID) -> Optional[Job]:
    """Pause a running job."""
    job = get_job(db, job_id)
    if not job:
        return None
    
    if job.status != JobStatus.RUNNING:
        return None
    
    job.status = JobStatus.PAUSED
    db.commit()
    db.refresh(job)
    return job


def resume_job(db: Session, job_id: UUID) -> Optional[Job]:
    """Resume a paused job."""
    job = get_job(db, job_id)
    if not job:
        return None
    
    if job.status != JobStatus.PAUSED:
        return None
    
    job.status = JobStatus.RUNNING
    db.commit()
    db.refresh(job)
    return job


def cancel_job(db: Session, job_id: UUID) -> Optional[Job]:
    """Cancel a job."""
    job = get_job(db, job_id)
    if not job:
        return None
    
    # Can only cancel jobs that are not already completed or failed
    if job.status in [JobStatus.COMPLETED, JobStatus.FAILED, JobStatus.CANCELLED]:
        return None
    
    job.status = JobStatus.CANCELLED
    db.commit()
    db.refresh(job)
    return job


def complete_job(
    db: Session,
    job_id: UUID,
    final_loss: Optional[float] = None,
    final_accuracy: Optional[float] = None,
) -> Optional[Job]:
    """Mark job as completed."""
    job = get_job(db, job_id)
    if not job:
        return None
    
    job.status = JobStatus.COMPLETED
    
    if final_loss is not None:
        job.final_loss = final_loss
    if final_accuracy is not None:
        job.final_accuracy = final_accuracy
    
    db.commit()
    db.refresh(job)
    return job


def fail_job(db: Session, job_id: UUID, error_message: Optional[str] = None) -> Optional[Job]:
    """Mark job as failed."""
    job = get_job(db, job_id)
    if not job:
        return None
    
    job.status = JobStatus.FAILED
    
    # Could store error message in config or separate field
    if error_message and job.config:
        job.config["error"] = error_message
    
    db.commit()
    db.refresh(job)
    return job


def delete_job(db: Session, job_id: UUID) -> bool:
    """Delete a job (hard delete)."""
    job = get_job(db, job_id)
    if not job:
        return False
    
    # Only allow deletion of completed, failed, or cancelled jobs
    if job.status not in [JobStatus.COMPLETED, JobStatus.FAILED, JobStatus.CANCELLED]:
        return False
    
    db.delete(job)
    db.commit()
    return True
