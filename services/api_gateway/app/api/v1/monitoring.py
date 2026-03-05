"""Monitoring and metrics API endpoints."""

from datetime import datetime
from typing import Optional
from fastapi import APIRouter, Depends, WebSocket, WebSocketDisconnect, Query
from sqlalchemy.orm import Session
import asyncio
import json

from app.dependencies import get_db, get_redis, get_current_user, get_optional_current_user
from app.core.exceptions import NotFoundError, AuthorizationError
from app.schemas.monitoring import (
    SystemMetrics,
    JobProgressDetail,
    GroupStatistics,
    UserStatistics,
)
from app.crud import monitoring as monitoring_crud, job as job_crud, group as group_crud
from app.models.user import User


router = APIRouter(prefix="/monitoring", tags=["monitoring"])


# Application start time for uptime calculation
app_start_time = datetime.utcnow()


# ============================================================================
# System Metrics Endpoints
# ============================================================================

@router.get(
    "/metrics/realtime",
    response_model=SystemMetrics,
    summary="Get real-time system metrics",
    description="Get current system statistics including workers, jobs, database, and Redis.",
)
async def get_realtime_metrics(
    db: Session = Depends(get_db),
    redis = Depends(get_redis),
    current_user: User = Depends(get_current_user),
):
    """Get real-time system metrics."""
    # Get system metrics
    metrics = monitoring_crud.get_system_metrics(db, redis, app_start_time)
    
    return metrics


@router.get(
    "/stats/me",
    response_model=UserStatistics,
    summary="Get current user statistics",
    description="Get statistics for the currently authenticated user.",
)
async def get_my_statistics(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Get current user statistics."""
    stats = monitoring_crud.get_user_statistics(db, current_user.id)
    
    if not stats:
        raise NotFoundError("User statistics not found")
    
    return stats


@router.get(
    "/stats/group/{group_id}",
    response_model=GroupStatistics,
    summary="Get group statistics",
    description="Get statistics for a specific group. Requires group membership.",
)
async def get_group_statistics(
    group_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Get group statistics."""
    # Check if user is member of group
    if not group_crud.check_member_permission(db, group_id, current_user.id):
        raise AuthorizationError("You are not a member of this group")
    
    stats = monitoring_crud.get_group_statistics(db, group_id)
    
    if not stats:
        raise NotFoundError(f"Group {group_id} not found")
    
    return stats


# ============================================================================
# Job Progress Endpoint
# ============================================================================

@router.get(
    "/jobs/{job_id}/progress",
    response_model=JobProgressDetail,
    summary="Get job training progress",
    description="Get detailed progress information for a specific training job.",
)
async def get_job_progress(
    job_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Get job progress."""
    # Get job
    job = job_crud.get_job(db, job_id)
    
    if not job:
        raise NotFoundError(f"Job {job_id} not found")
    
    # Check if user has access (must be in the job's group)
    if not group_crud.check_member_permission(db, job.group_id, current_user.id):
        raise AuthorizationError("You don't have access to this job")
    
    # Get progress
    progress = monitoring_crud.get_job_progress(db, job_id)
    
    if not progress:
        raise NotFoundError(f"Progress information for job {job_id} not found")
    
    return progress


# ============================================================================
# WebSocket Endpoint for Live Updates
# ============================================================================

class ConnectionManager:
    """Manage WebSocket connections."""
    
    def __init__(self):
        self.active_connections: list[WebSocket] = []
    
    async def connect(self, websocket: WebSocket):
        """Accept and store a new WebSocket connection."""
        await websocket.accept()
        self.active_connections.append(websocket)
    
    def disconnect(self, websocket: WebSocket):
        """Remove a WebSocket connection."""
        self.active_connections.remove(websocket)
    
    async def send_personal_message(self, message: str, websocket: WebSocket):
        """Send a message to a specific connection."""
        await websocket.send_text(message)
    
    async def broadcast(self, message: str):
        """Send a message to all connected clients."""
        for connection in self.active_connections:
            try:
                await connection.send_text(message)
            except Exception:
                # Connection might be closed
                pass


manager = ConnectionManager()


@router.websocket("/ws/live")
async def websocket_live_updates(
    websocket: WebSocket,
    token: Optional[str] = Query(None),
):
    """
    WebSocket endpoint for live system updates.
    
    Sends real-time updates for:
    - System metrics (every 5 seconds)
    - Job progress updates
    - Worker status changes
    - System alerts
    
    Query params:
        token: Optional JWT access token for authentication
    
    Message format:
        {
            "type": "metrics|job_progress|worker_status|alert",
            "timestamp": "2026-03-04T12:00:00",
            "data": {...}
        }
    """
    await manager.connect(websocket)
    
    try:
        # TODO: Implement token authentication for WebSocket
        # For now, allow unauthenticated connections
        
        # Send initial connection message
        await websocket.send_json({
            "type": "connected",
            "timestamp": datetime.utcnow().isoformat(),
            "message": "Connected to MeshML live updates"
        })
        
        # Keep connection alive and send periodic updates
        while True:
            try:
                # Wait for client message (ping/pong or subscriptions)
                data = await asyncio.wait_for(websocket.receive_text(), timeout=5.0)
                
                # Handle client messages
                try:
                    message = json.loads(data)
                    
                    if message.get("type") == "ping":
                        await websocket.send_json({
                            "type": "pong",
                            "timestamp": datetime.utcnow().isoformat()
                        })
                    
                    elif message.get("type") == "subscribe":
                        # Handle subscription requests
                        # TODO: Implement subscription logic
                        await websocket.send_json({
                            "type": "subscribed",
                            "timestamp": datetime.utcnow().isoformat(),
                            "subscription": message.get("topic")
                        })
                        
                except json.JSONDecodeError:
                    pass
                    
            except asyncio.TimeoutError:
                # No message received, send heartbeat
                await websocket.send_json({
                    "type": "heartbeat",
                    "timestamp": datetime.utcnow().isoformat()
                })
                
    except WebSocketDisconnect:
        manager.disconnect(websocket)
    except Exception as e:
        manager.disconnect(websocket)
        # Log error in production
        pass


# ============================================================================
# Health Check with Details
# ============================================================================

@router.get(
    "/health/detailed",
    summary="Detailed health check",
    description="Get detailed health status of all system components.",
)
async def detailed_health_check(
    db: Session = Depends(get_db),
    redis = Depends(get_redis),
):
    """Detailed health check with component status."""
    health_status = {
        "status": "healthy",
        "timestamp": datetime.utcnow().isoformat(),
        "components": {}
    }
    
    # Check database
    try:
        db.execute("SELECT 1")
        health_status["components"]["database"] = {
            "status": "healthy",
            "message": "Database connection OK"
        }
    except Exception as e:
        health_status["components"]["database"] = {
            "status": "unhealthy",
            "message": f"Database error: {str(e)}"
        }
        health_status["status"] = "degraded"
    
    # Check Redis
    try:
        redis.ping()
        health_status["components"]["redis"] = {
            "status": "healthy",
            "message": "Redis connection OK"
        }
    except Exception as e:
        health_status["components"]["redis"] = {
            "status": "unhealthy",
            "message": f"Redis error: {str(e)}"
        }
        health_status["status"] = "degraded"
    
    # Check worker availability
    try:
        worker_metrics = monitoring_crud.get_worker_metrics(db)
        health_status["components"]["workers"] = {
            "status": "healthy" if worker_metrics.idle_workers > 0 else "warning",
            "message": f"{worker_metrics.idle_workers} idle workers available",
            "total": worker_metrics.total_workers,
            "idle": worker_metrics.idle_workers,
            "busy": worker_metrics.busy_workers
        }
        
        if worker_metrics.idle_workers == 0 and worker_metrics.busy_workers > 0:
            health_status["status"] = "degraded"
            
    except Exception as e:
        health_status["components"]["workers"] = {
            "status": "unhealthy",
            "message": f"Worker metrics error: {str(e)}"
        }
        health_status["status"] = "degraded"
    
    return health_status
