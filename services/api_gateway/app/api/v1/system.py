"""
System endpoints - health, metrics, status.
"""

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from redis import Redis
from datetime import datetime
import psutil

from app.dependencies import get_db, get_redis
from app.config import settings


router = APIRouter()


@router.get("/health")
async def health_check(db: Session = Depends(get_db), redis: Redis = Depends(get_redis)):
    """
    Comprehensive health check endpoint.
    Returns status of all system components.
    """
    health_status = {
        "status": "healthy",
        "timestamp": datetime.utcnow().isoformat(),
        "version": settings.VERSION,
        "environment": settings.ENVIRONMENT,
        "services": {},
    }
    
    # Check database
    try:
        db.execute("SELECT 1")
        health_status["services"]["database"] = {
            "status": "healthy",
            "url": settings.DATABASE_URL.split("@")[-1],  # Hide credentials
        }
    except Exception as e:
        health_status["services"]["database"] = {
            "status": "unhealthy",
            "error": str(e),
        }
        health_status["status"] = "degraded"
    
    # Check Redis
    try:
        redis.ping()
        health_status["services"]["redis"] = {
            "status": "healthy",
            "url": settings.REDIS_URL.split("@")[-1],  # Hide credentials
        }
    except Exception as e:
        health_status["services"]["redis"] = {
            "status": "unhealthy",
            "error": str(e),
        }
        health_status["status"] = "degraded"
    
    return health_status


@router.get("/metrics")
async def get_metrics():
    """
    System metrics endpoint (Prometheus-compatible).
    Returns current system resource usage.
    """
    metrics = {
        "timestamp": datetime.utcnow().isoformat(),
        "system": {
            "cpu_percent": psutil.cpu_percent(interval=0.1),
            "memory_percent": psutil.virtual_memory().percent,
            "disk_percent": psutil.disk_usage('/').percent,
        },
    }
    
    return metrics


@router.get("/version")
async def get_version():
    """
    Get API version information.
    """
    return {
        "version": settings.VERSION,
        "project_name": settings.PROJECT_NAME,
        "environment": settings.ENVIRONMENT,
        "api_prefix": settings.API_V1_PREFIX,
    }
