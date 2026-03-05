"""CRUD operations for monitoring and metrics."""

from datetime import datetime, timedelta
from typing import Optional, List, Dict, Any
from sqlalchemy.orm import Session
from sqlalchemy import func, and_

from app.models.user import User
from app.models.group import Group
from app.models.job import Job, JobStatus
from app.models.worker import Worker, WorkerStatus
from app.schemas.monitoring import (
    DatabaseMetrics,
    RedisMetrics,
    WorkerMetrics,
    JobMetrics,
    SystemMetrics,
    JobProgressDetail,
    WorkerProgress,
    GroupStatistics,
    UserStatistics,
)


def get_database_metrics(db: Session) -> DatabaseMetrics:
    """
    Get database connection pool metrics.
    
    Args:
        db: Database session
        
    Returns:
        Database metrics
    """
    # Note: These are simplified metrics
    # In production, you'd query actual connection pool stats
    return DatabaseMetrics(
        total_connections=10,
        active_connections=2,
        idle_connections=8,
    )


def get_redis_metrics(redis_client) -> RedisMetrics:
    """
    Get Redis cache metrics.
    
    Args:
        redis_client: Redis client instance
        
    Returns:
        Redis metrics
    """
    try:
        redis_client.ping()
        connected = True
        
        # Get Redis INFO
        info = redis_client.info("memory")
        used_memory = info.get("used_memory", 0)
        
        # Get total keys
        keys = redis_client.dbsize()
        
        return RedisMetrics(
            connected=connected,
            used_memory=used_memory,
            keys=keys,
        )
    except Exception:
        return RedisMetrics(
            connected=False,
            used_memory=None,
            keys=None,
        )


def get_worker_metrics(db: Session) -> WorkerMetrics:
    """
    Get worker fleet metrics.
    
    Args:
        db: Database session
        
    Returns:
        Worker metrics
    """
    total_workers = db.query(Worker).count()
    
    idle_workers = db.query(Worker).filter(
        Worker.status == WorkerStatus.IDLE
    ).count()
    
    busy_workers = db.query(Worker).filter(
        Worker.status == WorkerStatus.BUSY
    ).count()
    
    offline_workers = db.query(Worker).filter(
        Worker.status == WorkerStatus.OFFLINE
    ).count()
    
    failed_workers = db.query(Worker).filter(
        Worker.status == WorkerStatus.FAILED
    ).count()
    
    return WorkerMetrics(
        total_workers=total_workers,
        idle_workers=idle_workers,
        busy_workers=busy_workers,
        offline_workers=offline_workers,
        failed_workers=failed_workers,
    )


def get_job_metrics(db: Session) -> JobMetrics:
    """
    Get job system metrics.
    
    Args:
        db: Database session
        
    Returns:
        Job metrics
    """
    total_jobs = db.query(Job).count()
    
    pending_jobs = db.query(Job).filter(
        Job.status == JobStatus.PENDING
    ).count()
    
    ready_jobs = db.query(Job).filter(
        Job.status == JobStatus.READY
    ).count()
    
    running_jobs = db.query(Job).filter(
        Job.status == JobStatus.RUNNING
    ).count()
    
    completed_jobs = db.query(Job).filter(
        Job.status == JobStatus.COMPLETED
    ).count()
    
    failed_jobs = db.query(Job).filter(
        Job.status == JobStatus.FAILED
    ).count()
    
    cancelled_jobs = db.query(Job).filter(
        Job.status == JobStatus.CANCELLED
    ).count()
    
    return JobMetrics(
        total_jobs=total_jobs,
        pending_jobs=pending_jobs,
        ready_jobs=ready_jobs,
        running_jobs=running_jobs,
        completed_jobs=completed_jobs,
        failed_jobs=failed_jobs,
        cancelled_jobs=cancelled_jobs,
    )


def get_system_metrics(db: Session, redis_client, start_time: datetime) -> SystemMetrics:
    """
    Get overall system metrics.
    
    Args:
        db: Database session
        redis_client: Redis client
        start_time: Application start time
        
    Returns:
        System metrics
    """
    now = datetime.utcnow()
    uptime = (now - start_time).total_seconds()
    
    total_users = db.query(User).count()
    total_groups = db.query(Group).count()
    
    return SystemMetrics(
        timestamp=now,
        uptime_seconds=int(uptime),
        total_users=total_users,
        total_groups=total_groups,
        database=get_database_metrics(db),
        redis=get_redis_metrics(redis_client),
        workers=get_worker_metrics(db),
        jobs=get_job_metrics(db),
    )


def get_job_progress(db: Session, job_id: str) -> Optional[JobProgressDetail]:
    """
    Get detailed job progress.
    
    Args:
        db: Database session
        job_id: Job ID
        
    Returns:
        Job progress details or None if not found
    """
    job = db.query(Job).filter(Job.id == job_id).first()
    
    if not job:
        return None
    
    # Calculate elapsed time
    elapsed_seconds = None
    if job.started_at:
        elapsed = datetime.utcnow() - job.started_at
        elapsed_seconds = int(elapsed.total_seconds())
    
    # Estimate completion time (simple linear estimation)
    estimated_completion = None
    if job.started_at and job.progress_percentage > 0 and job.progress_percentage < 100:
        elapsed = datetime.utcnow() - job.started_at
        total_estimated = elapsed.total_seconds() / (job.progress_percentage / 100)
        remaining = total_estimated - elapsed.total_seconds()
        estimated_completion = datetime.utcnow() + timedelta(seconds=remaining)
    
    # Count assigned and active workers
    # Note: This would require tracking worker assignments in a separate table
    # For now, we'll return 0
    assigned_workers = 0
    active_workers = 0
    
    return JobProgressDetail(
        job_id=job.id,
        job_name=job.job_name,
        status=job.status.value,
        total_batches=job.total_batches,
        completed_batches=job.completed_batches,
        progress_percentage=job.progress_percentage,
        current_epoch=job.current_epoch,
        total_epochs=job.config.get("epochs") if job.config else None,
        current_loss=job.current_loss,
        current_accuracy=job.current_accuracy,
        best_loss=job.best_loss,
        best_accuracy=job.best_accuracy,
        started_at=job.started_at,
        estimated_completion=estimated_completion,
        elapsed_seconds=elapsed_seconds,
        assigned_workers=assigned_workers,
        active_workers=active_workers,
    )


def get_group_statistics(db: Session, group_id: str) -> Optional[GroupStatistics]:
    """
    Get statistics for a specific group.
    
    Args:
        db: Database session
        group_id: Group ID
        
    Returns:
        Group statistics or None if not found
    """
    group = db.query(Group).filter(Group.id == group_id).first()
    
    if not group:
        return None
    
    # Count members
    from app.models.group import GroupMember
    total_members = db.query(GroupMember).filter(
        GroupMember.group_id == group_id
    ).count()
    
    # Count jobs
    total_jobs = db.query(Job).filter(Job.group_id == group_id).count()
    running_jobs = db.query(Job).filter(
        and_(Job.group_id == group_id, Job.status == JobStatus.RUNNING)
    ).count()
    completed_jobs = db.query(Job).filter(
        and_(Job.group_id == group_id, Job.status == JobStatus.COMPLETED)
    ).count()
    
    # Sum compute time and batches
    # Note: These fields don't exist in current Job model
    # This is placeholder for future implementation
    total_compute_time = 0
    total_batches_completed = db.query(func.sum(Job.completed_batches)).filter(
        Job.group_id == group_id
    ).scalar() or 0
    
    return GroupStatistics(
        group_id=group.id,
        group_name=group.name,
        total_members=total_members,
        total_jobs=total_jobs,
        running_jobs=running_jobs,
        completed_jobs=completed_jobs,
        total_compute_time=total_compute_time,
        total_batches_completed=total_batches_completed,
    )


def get_user_statistics(db: Session, user_id: str) -> Optional[UserStatistics]:
    """
    Get statistics for a specific user.
    
    Args:
        db: Database session
        user_id: User ID
        
    Returns:
        User statistics or None if not found
    """
    user = db.query(User).filter(User.id == user_id).first()
    
    if not user:
        return None
    
    # Count groups (where user is member)
    from app.models.group import GroupMember
    total_groups = db.query(GroupMember).filter(
        GroupMember.user_id == user_id
    ).count()
    
    # Count jobs created by user
    total_jobs_created = db.query(Job).filter(
        Job.created_by == user_id
    ).count()
    
    # Count workers registered by user
    total_workers_registered = db.query(Worker).filter(
        Worker.user_id == user_id
    ).count()
    
    # Count completed and running jobs
    jobs_completed = db.query(Job).filter(
        and_(Job.created_by == user_id, Job.status == JobStatus.COMPLETED)
    ).count()
    
    jobs_running = db.query(Job).filter(
        and_(Job.created_by == user_id, Job.status == JobStatus.RUNNING)
    ).count()
    
    return UserStatistics(
        user_id=user.id,
        username=user.username,
        total_groups=total_groups,
        total_jobs_created=total_jobs_created,
        total_workers_registered=total_workers_registered,
        total_compute_contributed=user.total_compute_contributed,
        jobs_completed=jobs_completed,
        jobs_running=jobs_running,
    )
