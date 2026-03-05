"""CRUD operations for worker management."""

from datetime import datetime, timedelta
from typing import Optional, List
from uuid import UUID

from sqlalchemy import and_, or_
from sqlalchemy.orm import Session, joinedload

from app.models.worker import Worker, WorkerStatus
from app.schemas.worker import WorkerRegister, WorkerUpdate, WorkerHeartbeat, WorkerBatchUpdate


# ============================================================================
# Worker CRUD
# ============================================================================

def register_worker(db: Session, worker_data: WorkerRegister, user_id: UUID) -> Worker:
    """Register a new worker."""
    # Convert capabilities to dict
    capabilities_dict = worker_data.capabilities.model_dump()
    
    worker = Worker(
        id=worker_data.worker_id,
        user_id=user_id,
        type=worker_data.type,
        version=worker_data.version,
        capabilities=capabilities_dict,
        status=WorkerStatus.IDLE,
        last_heartbeat=datetime.utcnow(),
    )
    
    db.add(worker)
    db.commit()
    db.refresh(worker)
    
    return worker


def get_worker(db: Session, worker_id: str) -> Optional[Worker]:
    """Get worker by ID."""
    return db.query(Worker).filter(Worker.id == worker_id).first()


def get_worker_with_user(db: Session, worker_id: str) -> Optional[Worker]:
    """Get worker with user relationship loaded."""
    return (
        db.query(Worker)
        .options(joinedload(Worker.user))
        .filter(Worker.id == worker_id)
        .first()
    )


def get_user_workers(
    db: Session,
    user_id: UUID,
    skip: int = 0,
    limit: int = 100,
    status: Optional[WorkerStatus] = None,
) -> tuple[List[Worker], int]:
    """Get all workers for a user."""
    query = db.query(Worker).filter(Worker.user_id == user_id)
    
    if status:
        query = query.filter(Worker.status == status)
    
    # Get total count
    total = query.count()
    
    # Get paginated results
    workers = query.order_by(Worker.created_at.desc()).offset(skip).limit(limit).all()
    
    return workers, total


def get_available_workers(
    db: Session,
    skip: int = 0,
    limit: int = 100,
    worker_type: Optional[str] = None,
) -> tuple[List[Worker], int]:
    """Get all available (IDLE) workers."""
    query = db.query(Worker).filter(Worker.status == WorkerStatus.IDLE)
    
    if worker_type:
        query = query.filter(Worker.type == worker_type)
    
    # Only workers with recent heartbeat (last 60 seconds)
    cutoff_time = datetime.utcnow() - timedelta(seconds=60)
    query = query.filter(Worker.last_heartbeat >= cutoff_time)
    
    total = query.count()
    workers = query.order_by(Worker.last_heartbeat.desc()).offset(skip).limit(limit).all()
    
    return workers, total


def update_worker(db: Session, worker_id: str, worker_data: WorkerUpdate) -> Optional[Worker]:
    """Update worker information."""
    worker = get_worker(db, worker_id)
    if not worker:
        return None
    
    # Update version
    if worker_data.version is not None:
        worker.version = worker_data.version
    
    # Update capabilities
    if worker_data.capabilities:
        worker.capabilities = worker_data.capabilities.model_dump()
    
    db.commit()
    db.refresh(worker)
    return worker


def update_worker_heartbeat(
    db: Session,
    worker_id: str,
    heartbeat: WorkerHeartbeat,
) -> Optional[Worker]:
    """Update worker heartbeat and status."""
    worker = get_worker(db, worker_id)
    if not worker:
        return None
    
    # Update heartbeat timestamp
    worker.last_heartbeat = datetime.utcnow()
    
    # Update status
    worker.status = heartbeat.status
    
    # Update current assignment
    if heartbeat.current_job_id is not None:
        worker.current_job_id = heartbeat.current_job_id
    if heartbeat.current_batch_id is not None:
        worker.current_batch_id = heartbeat.current_batch_id
    
    db.commit()
    db.refresh(worker)
    return worker


def assign_work_to_worker(
    db: Session,
    worker_id: str,
    job_id: UUID,
    batch_id: str,
) -> Optional[Worker]:
    """Assign work to a worker."""
    worker = get_worker(db, worker_id)
    if not worker:
        return None
    
    if worker.status != WorkerStatus.IDLE:
        return None
    
    worker.status = WorkerStatus.BUSY
    worker.current_job_id = job_id
    worker.current_batch_id = batch_id
    
    db.commit()
    db.refresh(worker)
    return worker


def complete_worker_batch(
    db: Session,
    worker_id: str,
    batch_update: WorkerBatchUpdate,
) -> Optional[Worker]:
    """Mark batch as completed and update worker statistics."""
    worker = get_worker(db, worker_id)
    if not worker:
        return None
    
    if batch_update.success:
        worker.batches_completed += 1
        worker.consecutive_failures = 0
        worker.status = WorkerStatus.IDLE
    else:
        worker.consecutive_failures += 1
        # Mark as failed if too many consecutive failures
        if worker.consecutive_failures >= 3:
            worker.status = WorkerStatus.FAILED
        else:
            worker.status = WorkerStatus.IDLE
    
    # Update compute time
    worker.total_compute_time += batch_update.compute_time
    
    # Clear current assignment
    worker.current_job_id = None
    worker.current_batch_id = None
    
    db.commit()
    db.refresh(worker)
    return worker


def set_worker_offline(db: Session, worker_id: str) -> Optional[Worker]:
    """Set worker status to offline."""
    worker = get_worker(db, worker_id)
    if not worker:
        return None
    
    worker.status = WorkerStatus.OFFLINE
    worker.current_job_id = None
    worker.current_batch_id = None
    
    db.commit()
    db.refresh(worker)
    return worker


def set_worker_draining(db: Session, worker_id: str) -> Optional[Worker]:
    """Set worker to draining status (finish current work, no new assignments)."""
    worker = get_worker(db, worker_id)
    if not worker:
        return None
    
    worker.status = WorkerStatus.DRAINING
    
    db.commit()
    db.refresh(worker)
    return worker


def delete_worker(db: Session, worker_id: str) -> bool:
    """Delete a worker (hard delete)."""
    worker = get_worker(db, worker_id)
    if not worker:
        return False
    
    # Only allow deletion of offline workers
    if worker.status not in [WorkerStatus.OFFLINE, WorkerStatus.FAILED]:
        return False
    
    db.delete(worker)
    db.commit()
    return True


def mark_stale_workers_offline(db: Session, timeout_seconds: int = 120) -> int:
    """Mark workers as offline if no heartbeat received within timeout."""
    cutoff_time = datetime.utcnow() - timedelta(seconds=timeout_seconds)
    
    result = db.query(Worker).filter(
        Worker.status.in_([WorkerStatus.IDLE, WorkerStatus.BUSY, WorkerStatus.DRAINING]),
        or_(
            Worker.last_heartbeat < cutoff_time,
            Worker.last_heartbeat.is_(None)
        )
    ).update(
        {
            Worker.status: WorkerStatus.OFFLINE,
            Worker.current_job_id: None,
            Worker.current_batch_id: None,
        },
        synchronize_session=False
    )
    
    db.commit()
    return result
