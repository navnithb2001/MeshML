"""
Worker, Job, and DataBatch repositories.
"""
from typing import Optional, List
from datetime import datetime, timedelta
from sqlalchemy.orm import Session
from services.database.models.worker import Worker, WorkerStatus, WorkerType
from services.database.models.job import Job, JobStatus
from services.database.models.data_batch import DataBatch, BatchStatus
from .base import BaseRepository


class WorkerRepository(BaseRepository[Worker]):
    """Repository for Worker model."""
    
    def __init__(self, db: Session):
        super().__init__(Worker, db)
    
    def get_by_worker_id(self, worker_id: str) -> Optional[Worker]:
        """Get worker by worker_id (UUID)."""
        return self.get_by_field('worker_id', worker_id)
    
    def get_online_workers(self, worker_type: Optional[WorkerType] = None) -> List[Worker]:
        """Get all online workers, optionally filtered by type."""
        filters = {'status': WorkerStatus.ONLINE}
        if worker_type:
            filters['worker_type'] = worker_type
        return self.get_all(filters=filters)
    
    def get_available_workers(self, worker_type: Optional[WorkerType] = None) -> List[Worker]:
        """Get all online and not busy workers."""
        query = self.db.query(Worker).filter(
            Worker.status.in_([WorkerStatus.ONLINE])
        )
        if worker_type:
            query = query.filter(Worker.worker_type == worker_type)
        return query.all()
    
    def update_heartbeat(self, worker_id: str) -> Optional[Worker]:
        """Update worker's last heartbeat timestamp."""
        worker = self.get_by_worker_id(worker_id)
        if worker:
            worker.last_heartbeat = datetime.utcnow()
            worker.status = WorkerStatus.ONLINE
            self.db.flush()
            self.db.refresh(worker)
        return worker
    
    def set_status(self, worker_id: str, status: WorkerStatus) -> Optional[Worker]:
        """Update worker status."""
        worker = self.get_by_worker_id(worker_id)
        if worker:
            worker.status = status
            self.db.flush()
            self.db.refresh(worker)
        return worker
    
    def mark_stale_workers_offline(self, timeout_seconds: int = 60) -> int:
        """
        Mark workers as offline if no heartbeat within timeout.
        
        Args:
            timeout_seconds: Heartbeat timeout in seconds
            
        Returns:
            Number of workers marked offline
        """
        cutoff = datetime.utcnow() - timedelta(seconds=timeout_seconds)
        
        count = self.db.query(Worker).filter(
            Worker.status == WorkerStatus.ONLINE,
            Worker.last_heartbeat < cutoff
        ).update({'status': WorkerStatus.OFFLINE})
        
        self.db.flush()
        return count


class JobRepository(BaseRepository[Job]):
    """Repository for Job model."""
    
    def __init__(self, db: Session):
        super().__init__(Job, db)
    
    def get_by_group(self, group_id: int, status: Optional[JobStatus] = None) -> List[Job]:
        """Get all jobs for a group, optionally filtered by status."""
        filters = {'group_id': group_id}
        if status:
            filters['status'] = status
        return self.get_all(
            filters=filters,
            order_by='created_at',
            descending=True
        )
    
    def get_active_jobs(self) -> List[Job]:
        """Get all jobs that are currently running or pending."""
        return self.db.query(Job).filter(
            Job.status.in_([JobStatus.PENDING, JobStatus.VALIDATING, JobStatus.RUNNING])
        ).all()
    
    def get_running_jobs(self) -> List[Job]:
        """Get all currently running jobs."""
        return self.get_all(filters={'status': JobStatus.RUNNING})
    
    def set_status(self, job_id: int, status: JobStatus, error: Optional[str] = None) -> Optional[Job]:
        """Update job status and optionally set error message."""
        updates = {'status': status}
        if error:
            updates['error_message'] = error
        return self.update(job_id, **updates)
    
    def update_progress(
        self,
        job_id: int,
        progress: float,
        current_epoch: int,
        metrics: Optional[dict] = None
    ) -> Optional[Job]:
        """Update job training progress."""
        updates = {
            'progress': progress,
            'current_epoch': current_epoch
        }
        if metrics:
            updates['metrics'] = metrics
        return self.update(job_id, **updates)
    
    def mark_as_completed(self, job_id: int, final_metrics: dict) -> Optional[Job]:
        """Mark job as completed with final metrics."""
        return self.update(
            job_id,
            status=JobStatus.COMPLETED,
            progress=100.0,
            metrics=final_metrics
        )
    
    def mark_as_failed(self, job_id: int, error_message: str) -> Optional[Job]:
        """Mark job as failed with error message."""
        return self.update(
            job_id,
            status=JobStatus.FAILED,
            error_message=error_message
        )
    
    def pause_job(self, job_id: int) -> Optional[Job]:
        """Pause a running job."""
        return self.update(job_id, status=JobStatus.PAUSED)
    
    def resume_job(self, job_id: int) -> Optional[Job]:
        """Resume a paused job."""
        return self.update(job_id, status=JobStatus.RUNNING)
    
    def cancel_job(self, job_id: int) -> Optional[Job]:
        """Cancel a job."""
        return self.update(job_id, status=JobStatus.CANCELLED)


class DataBatchRepository(BaseRepository[DataBatch]):
    """Repository for DataBatch model."""
    
    def __init__(self, db: Session):
        super().__init__(DataBatch, db)
    
    def get_by_job(self, job_id: int, status: Optional[BatchStatus] = None) -> List[DataBatch]:
        """Get all batches for a job, optionally filtered by status."""
        filters = {'job_id': job_id}
        if status:
            filters['status'] = status
        return self.get_all(
            filters=filters,
            order_by='batch_index'
        )
    
    def get_pending_batches(self, job_id: int, limit: int = 10) -> List[DataBatch]:
        """Get pending batches for assignment."""
        return self.get_all(
            filters={'job_id': job_id, 'status': BatchStatus.PENDING},
            limit=limit,
            order_by='batch_index'
        )
    
    def get_worker_batches(self, worker_id: int) -> List[DataBatch]:
        """Get all batches assigned to a worker."""
        return self.get_all(
            filters={'worker_id': worker_id},
            order_by='batch_index'
        )
    
    def assign_to_worker(self, batch_id: int, worker_id: int) -> Optional[DataBatch]:
        """Assign batch to a worker."""
        return self.update(
            batch_id,
            worker_id=worker_id,
            status=BatchStatus.ASSIGNED
        )
    
    def mark_processing(self, batch_id: int) -> Optional[DataBatch]:
        """Mark batch as being processed."""
        return self.update(batch_id, status=BatchStatus.PROCESSING)
    
    def mark_completed(self, batch_id: int) -> Optional[DataBatch]:
        """Mark batch as completed."""
        return self.update(batch_id, status=BatchStatus.COMPLETED)
    
    def mark_failed(self, batch_id: int, increment_retry: bool = True) -> Optional[DataBatch]:
        """
        Mark batch as failed and optionally increment retry count.
        
        Args:
            batch_id: Batch identifier
            increment_retry: Whether to increment retry count
            
        Returns:
            Updated batch or None
        """
        batch = self.get_by_id(batch_id)
        if batch:
            batch.status = BatchStatus.FAILED
            if increment_retry:
                batch.retry_count += 1
                # If max retries exceeded, keep as failed
                # Otherwise, reset to pending for retry
                if batch.retry_count < batch.max_retries:
                    batch.status = BatchStatus.PENDING
                    batch.worker_id = None  # Unassign worker
            self.db.flush()
            self.db.refresh(batch)
        return batch
    
    def get_job_completion_percentage(self, job_id: int) -> float:
        """
        Calculate job completion percentage based on batch completion.
        
        Args:
            job_id: Job identifier
            
        Returns:
            Completion percentage (0-100)
        """
        total = self.count({'job_id': job_id})
        if total == 0:
            return 0.0
        
        completed = self.count({
            'job_id': job_id,
            'status': BatchStatus.COMPLETED
        })
        
        return (completed / total) * 100.0
