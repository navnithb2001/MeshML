"""
Validation log model for storing validation history.
"""
from sqlalchemy import String, Integer, ForeignKey, Enum as SQLEnum, Text, JSON, Boolean
from sqlalchemy.orm import Mapped, mapped_column, relationship
from typing import Optional, Dict, Any
from enum import Enum
from .base import Base, TimestampMixin


class ValidationType(str, Enum):
    """Type of validation."""
    MODEL = "model"
    DATASET = "dataset"


class ValidationLogStatus(str, Enum):
    """Validation result status."""
    PASSED = "passed"
    FAILED = "failed"
    WARNING = "warning"


class ValidationLog(Base, TimestampMixin):
    """Log entry for model/dataset validations."""
    
    __tablename__ = "validation_logs"
    
    # Primary key
    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    
    # Validation type and resource
    validation_type: Mapped[ValidationType] = mapped_column(
        SQLEnum(ValidationType, name="validation_type", create_type=True),
        nullable=False,
        index=True
    )
    
    # Resource reference (model_id or dataset path)
    resource_id: Mapped[str] = mapped_column(
        String(512),
        nullable=False,
        index=True,
        comment="Model ID or dataset GCS path"
    )
    
    # User who triggered validation
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
        index=True
    )
    
    # Validation result
    status: Mapped[ValidationLogStatus] = mapped_column(
        SQLEnum(ValidationLogStatus, name="validation_log_status", create_type=True),
        nullable=False,
        index=True
    )
    
    is_valid: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    
    # Error details
    error_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    warning_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    
    # Full validation report (JSON)
    validation_report: Mapped[Dict[str, Any]] = mapped_column(
        JSON,
        nullable=False,
        comment="Complete ValidationReport as JSON"
    )
    
    # Summary message
    summary: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    
    # Relationships
    user: Mapped[Optional["User"]] = relationship(
        "User",
        backref="validation_logs"
    )
    
    def __repr__(self) -> str:
        return f"<ValidationLog(id={self.id}, type={self.validation_type}, status={self.status}, resource={self.resource_id})>"
