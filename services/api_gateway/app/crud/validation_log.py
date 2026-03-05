"""CRUD operations for validation logs."""

from sqlalchemy.orm import Session
from sqlalchemy import select, and_, desc
from typing import Optional, List
from datetime import datetime, timedelta
import logging

from services.database.models.validation_log import ValidationLog, ValidationType, ValidationLogStatus
from app.services.error_reporting import ValidationReport

logger = logging.getLogger(__name__)


async def create_validation_log(
    db: Session,
    validation_report: ValidationReport,
    user_id: Optional[int] = None
) -> ValidationLog:
    """
    Create a validation log entry from a validation report.
    
    Args:
        db: Database session
        validation_report: ValidationReport instance
        user_id: Optional user ID who triggered validation
        
    Returns:
        Created ValidationLog instance
    """
    # Determine status
    if not validation_report.is_valid:
        status = ValidationLogStatus.FAILED
    elif validation_report.warnings:
        status = ValidationLogStatus.WARNING
    else:
        status = ValidationLogStatus.PASSED
    
    log_entry = ValidationLog(
        validation_type=ValidationType(validation_report.validation_type),
        resource_id=validation_report.resource_id or "unknown",
        user_id=user_id,
        status=status,
        is_valid=validation_report.is_valid,
        error_count=len(validation_report.errors),
        warning_count=len(validation_report.warnings),
        validation_report=validation_report.dict(),
        summary=validation_report.get_summary_text()
    )
    
    db.add(log_entry)
    db.commit()
    db.refresh(log_entry)
    
    logger.info(f"Created validation log {log_entry.id} for {validation_report.validation_type} {validation_report.resource_id}")
    return log_entry


async def get_validation_log_by_id(db: Session, log_id: int) -> Optional[ValidationLog]:
    """Get validation log by ID."""
    stmt = select(ValidationLog).where(ValidationLog.id == log_id)
    result = db.execute(stmt)
    return result.scalar_one_or_none()


async def get_validation_logs_for_resource(
    db: Session,
    resource_id: str,
    validation_type: ValidationType,
    limit: int = 10
) -> List[ValidationLog]:
    """
    Get validation logs for a specific resource.
    
    Args:
        db: Database session
        resource_id: Model ID or dataset path
        validation_type: Type of validation
        limit: Maximum number of logs to return
        
    Returns:
        List of ValidationLog instances
    """
    stmt = (
        select(ValidationLog)
        .where(
            and_(
                ValidationLog.resource_id == resource_id,
                ValidationLog.validation_type == validation_type
            )
        )
        .order_by(desc(ValidationLog.created_at))
        .limit(limit)
    )
    
    result = db.execute(stmt)
    return list(result.scalars().all())


async def get_latest_validation_log(
    db: Session,
    resource_id: str,
    validation_type: ValidationType
) -> Optional[ValidationLog]:
    """
    Get the most recent validation log for a resource.
    
    Args:
        db: Database session
        resource_id: Model ID or dataset path
        validation_type: Type of validation
        
    Returns:
        Latest ValidationLog or None
    """
    logs = await get_validation_logs_for_resource(
        db=db,
        resource_id=resource_id,
        validation_type=validation_type,
        limit=1
    )
    return logs[0] if logs else None


async def get_failed_validations(
    db: Session,
    since: Optional[datetime] = None,
    limit: int = 100
) -> List[ValidationLog]:
    """
    Get failed validations, optionally filtered by time.
    
    Args:
        db: Database session
        since: Optional datetime to filter from
        limit: Maximum number of logs
        
    Returns:
        List of failed ValidationLog instances
    """
    stmt = (
        select(ValidationLog)
        .where(ValidationLog.status == ValidationLogStatus.FAILED)
    )
    
    if since:
        stmt = stmt.where(ValidationLog.created_at >= since)
    
    stmt = stmt.order_by(desc(ValidationLog.created_at)).limit(limit)
    
    result = db.execute(stmt)
    return list(result.scalars().all())


async def get_user_validation_history(
    db: Session,
    user_id: int,
    skip: int = 0,
    limit: int = 50
) -> tuple[List[ValidationLog], int]:
    """
    Get validation history for a user.
    
    Args:
        db: Database session
        user_id: User ID
        skip: Pagination offset
        limit: Page size
        
    Returns:
        Tuple of (list of logs, total count)
    """
    # Count query
    count_stmt = select(ValidationLog.id).where(ValidationLog.user_id == user_id)
    total = len(db.execute(count_stmt).scalars().all())
    
    # Data query
    stmt = (
        select(ValidationLog)
        .where(ValidationLog.user_id == user_id)
        .order_by(desc(ValidationLog.created_at))
        .offset(skip)
        .limit(limit)
    )
    
    result = db.execute(stmt)
    logs = list(result.scalars().all())
    
    return logs, total


async def get_validation_stats(
    db: Session,
    since: Optional[datetime] = None
) -> dict:
    """
    Get validation statistics.
    
    Args:
        db: Database session
        since: Optional datetime to filter from (default: last 30 days)
        
    Returns:
        Dictionary with statistics
    """
    if since is None:
        since = datetime.utcnow() - timedelta(days=30)
    
    # Get all logs since the specified time
    stmt = select(ValidationLog).where(ValidationLog.created_at >= since)
    result = db.execute(stmt)
    logs = list(result.scalars().all())
    
    # Calculate stats
    stats = {
        "total_validations": len(logs),
        "passed": sum(1 for log in logs if log.status == ValidationLogStatus.PASSED),
        "failed": sum(1 for log in logs if log.status == ValidationLogStatus.FAILED),
        "warnings": sum(1 for log in logs if log.status == ValidationLogStatus.WARNING),
        "by_type": {
            "model": sum(1 for log in logs if log.validation_type == ValidationType.MODEL),
            "dataset": sum(1 for log in logs if log.validation_type == ValidationType.DATASET),
        },
        "total_errors": sum(log.error_count for log in logs),
        "total_warnings": sum(log.warning_count for log in logs),
        "since": since.isoformat(),
    }
    
    return stats


async def delete_old_validation_logs(
    db: Session,
    days_to_keep: int = 90
) -> int:
    """
    Delete validation logs older than specified days.
    
    Args:
        db: Database session
        days_to_keep: Number of days to retain logs
        
    Returns:
        Number of logs deleted
    """
    cutoff_date = datetime.utcnow() - timedelta(days=days_to_keep)
    
    stmt = select(ValidationLog).where(ValidationLog.created_at < cutoff_date)
    result = db.execute(stmt)
    old_logs = list(result.scalars().all())
    
    for log in old_logs:
        db.delete(log)
    
    db.commit()
    
    logger.info(f"Deleted {len(old_logs)} validation logs older than {days_to_keep} days")
    return len(old_logs)
