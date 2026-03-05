"""Worker registration and management API endpoints."""

from datetime import datetime
from typing import Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.orm import Session

from app.core.exceptions import (
    NotFoundError,
    AuthorizationError,
    ConflictError,
    ValidationError,
)
from app.dependencies import get_db, get_current_user
from app.models.worker import WorkerStatus
from app.models.user import User
from app.schemas.worker import (
    WorkerRegister,
    WorkerUpdate,
    WorkerResponse,
    WorkerDetailResponse,
    WorkerListResponse,
    WorkerHeartbeat,
    HeartbeatResponse,
    WorkerBatchUpdate,
)
from app.crud import worker as worker_crud

# TODO: Import current_user dependency once auth is implemented
# from app.dependencies import get_current_user
# from app.models.user import User


router = APIRouter(prefix="/workers", tags=["workers"])


# ============================================================================
# Worker Registration & Management Endpoints
# ============================================================================

@router.post(
    "/register",
    response_model=WorkerResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Register a new worker",
    description="Register a new worker device. The worker provides its own unique ID.",
)
async def register_worker(
    worker_data: WorkerRegister,
    db: Session = Depends(get_db),
    current_user = Depends(get_current_user),
):
    """Register a new worker."""
    # Check if worker ID already exists
    existing_worker = worker_crud.get_worker(db, worker_data.worker_id)
    if existing_worker:
        raise ConflictError(f"Worker with ID {worker_data.worker_id} already exists")
    
    # Register the worker
    worker = worker_crud.register_worker(db, worker_data, current_user.id)
    return worker


@router.get(
    "",
    response_model=WorkerListResponse,
    summary="List user's workers",
    description="Get all workers registered by the current user.",
)
async def list_user_workers(
    skip: int = Query(0, ge=0, description="Number of records to skip"),
    limit: int = Query(100, ge=1, le=500, description="Maximum records to return"),
    status: Optional[WorkerStatus] = Query(None, description="Filter by worker status"),
    db: Session = Depends(get_db),
    current_user = Depends(get_current_user),
):
    """List all workers for current user."""
    workers, total = worker_crud.get_user_workers(
        db,
        current_user.id,
        skip=skip,
        limit=limit,
        status=status,
    )
    
    return WorkerListResponse(
        workers=workers,
        total=total,
        page=skip // limit + 1,
        page_size=limit,
    )


@router.get(
    "/available",
    response_model=WorkerListResponse,
    summary="List available workers",
    description="Get all available (IDLE) workers with recent heartbeats.",
)
async def list_available_workers(
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=500),
    worker_type: Optional[str] = Query(None, description="Filter by worker type"),
    db: Session = Depends(get_db),
    current_user = Depends(get_current_user),
):
    """List all available workers."""
    # TODO: In production, this should be restricted to orchestrator/admin
    workers, total = worker_crud.get_available_workers(
        db,
        skip=skip,
        limit=limit,
        worker_type=worker_type,
    )
    
    return WorkerListResponse(
        workers=workers,
        total=total,
        page=skip // limit + 1,
        page_size=limit,
    )


@router.get(
    "/{worker_id}",
    response_model=WorkerDetailResponse,
    summary="Get worker details",
    description="Get detailed information about a specific worker.",
)
async def get_worker(
    worker_id: str,
    db: Session = Depends(get_db),
    current_user = Depends(get_current_user),
):
    """Get worker by ID."""
    worker = worker_crud.get_worker_with_user(db, worker_id)
    if not worker:
        raise NotFoundError(f"Worker {worker_id} not found")
    
    # Check if user owns this worker
    if worker.user_id != current_user.id:
        # TODO: In production, also allow admin access
        raise AuthorizationError("You don't own this worker")
    
    return WorkerDetailResponse(
        **worker.__dict__,
        user=worker.user,
    )


@router.patch(
    "/{worker_id}",
    response_model=WorkerResponse,
    summary="Update worker",
    description="Update worker information (capabilities, version).",
)
async def update_worker(
    worker_id: str,
    worker_data: WorkerUpdate,
    db: Session = Depends(get_db),
    current_user = Depends(get_current_user),
):
    """Update worker information."""
    worker = worker_crud.get_worker(db, worker_id)
    if not worker:
        raise NotFoundError(f"Worker {worker_id} not found")
    
    # Check if user owns this worker
    if worker.user_id != current_user.id:
        raise AuthorizationError("You don't own this worker")
    
    updated_worker = worker_crud.update_worker(db, worker_id, worker_data)
    if not updated_worker:
        raise NotFoundError(f"Worker {worker_id} not found")
    
    return updated_worker


@router.delete(
    "/{worker_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete worker",
    description="Delete a worker. Only offline or failed workers can be deleted.",
)
async def delete_worker(
    worker_id: str,
    db: Session = Depends(get_db),
    current_user = Depends(get_current_user),
):
    """Delete a worker."""
    worker = worker_crud.get_worker(db, worker_id)
    if not worker:
        raise NotFoundError(f"Worker {worker_id} not found")
    
    # Check if user owns this worker
    if worker.user_id != current_user.id:
        raise AuthorizationError("You don't own this worker")
    
    success = worker_crud.delete_worker(db, worker_id)
    if not success:
        raise ValidationError("Cannot delete worker. Worker must be OFFLINE or FAILED status.")
    
    return None


# ============================================================================
# Worker Heartbeat Endpoint
# ============================================================================

@router.post(
    "/{worker_id}/heartbeat",
    response_model=HeartbeatResponse,
    summary="Send worker heartbeat",
    description="Workers send periodic heartbeats to indicate they're alive and report status.",
)
async def worker_heartbeat(
    worker_id: str,
    heartbeat: WorkerHeartbeat,
    db: Session = Depends(get_db),
    current_user = Depends(get_current_user),
):
    """Process worker heartbeat."""
    worker = worker_crud.get_worker(db, worker_id)
    if not worker:
        raise NotFoundError(f"Worker {worker_id} not found")
    
    # Check if user owns this worker
    if worker.user_id != current_user.id:
        raise AuthorizationError("You don't own this worker")
    
    # Update heartbeat
    updated_worker = worker_crud.update_worker_heartbeat(db, worker_id, heartbeat)
    if not updated_worker:
        raise NotFoundError(f"Worker {worker_id} not found")
    
    # Return response
    # TODO: Implement logic to assign new work, signal termination, etc.
    return HeartbeatResponse(
        acknowledged=True,
        server_time=datetime.utcnow(),
        should_terminate=False,
        new_assignment=None,
    )


# ============================================================================
# Worker Control Endpoints
# ============================================================================

@router.post(
    "/{worker_id}/offline",
    response_model=WorkerResponse,
    summary="Set worker offline",
    description="Manually set a worker to offline status.",
)
async def set_worker_offline(
    worker_id: str,
    db: Session = Depends(get_db),
    current_user = Depends(get_current_user),
):
    """Set worker to offline."""
    worker = worker_crud.get_worker(db, worker_id)
    if not worker:
        raise NotFoundError(f"Worker {worker_id} not found")
    
    # Check if user owns this worker
    if worker.user_id != current_user.id:
        raise AuthorizationError("You don't own this worker")
    
    offline_worker = worker_crud.set_worker_offline(db, worker_id)
    if not offline_worker:
        raise NotFoundError(f"Worker {worker_id} not found")
    
    return offline_worker


@router.post(
    "/{worker_id}/drain",
    response_model=WorkerResponse,
    summary="Set worker to draining",
    description="Set worker to draining status (finish current work, no new assignments).",
)
async def set_worker_draining(
    worker_id: str,
    db: Session = Depends(get_db),
    current_user = Depends(get_current_user),
):
    """Set worker to draining."""
    worker = worker_crud.get_worker(db, worker_id)
    if not worker:
        raise NotFoundError(f"Worker {worker_id} not found")
    
    # Check if user owns this worker
    if worker.user_id != current_user.id:
        raise AuthorizationError("You don't own this worker")
    
    draining_worker = worker_crud.set_worker_draining(db, worker_id)
    if not draining_worker:
        raise NotFoundError(f"Worker {worker_id} not found")
    
    return draining_worker


# ============================================================================
# Worker Batch Completion Endpoint
# ============================================================================

@router.post(
    "/{worker_id}/batch/complete",
    response_model=WorkerResponse,
    summary="Report batch completion",
    description="Worker reports completion of a training batch (success or failure).",
)
async def complete_batch(
    worker_id: str,
    batch_update: WorkerBatchUpdate,
    db: Session = Depends(get_db),
    current_user = Depends(get_current_user),
):
    """Worker reports batch completion."""
    worker = worker_crud.get_worker(db, worker_id)
    if not worker:
        raise NotFoundError(f"Worker {worker_id} not found")
    
    # Check if user owns this worker
    if worker.user_id != current_user.id:
        raise AuthorizationError("You don't own this worker")
    
    # Update worker statistics
    updated_worker = worker_crud.complete_worker_batch(db, worker_id, batch_update)
    if not updated_worker:
        raise NotFoundError(f"Worker {worker_id} not found")
    
    # TODO: Update job metrics based on batch results
    # TODO: Assign next batch if available
    
    return updated_worker
