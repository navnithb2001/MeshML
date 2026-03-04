"""
Job model for training job management.
"""
from sqlalchemy import String, Integer, ForeignKey, Enum as SQLEnum, Text, JSON, Float
from sqlalchemy.orm import Mapped, mapped_column, relationship
from typing import Optional, Dict, Any
from enum import Enum
from .base import Base, TimestampMixin


class JobStatus(str, Enum):
    """Status of a training job."""
    PENDING = "pending"
    VALIDATING = "validating"  # Model & dataset validation in progress
    RUNNING = "running"
    PAUSED = "paused"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class Job(Base, TimestampMixin):
    """Training job with group association."""
    
    __tablename__ = "jobs"
    
    # Primary key
    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    
    # Job identity
    name: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    
    # Ownership
    group_id: Mapped[int] = mapped_column(
        ForeignKey("groups.id", ondelete="CASCADE"),
        nullable=False,
        index=True
    )
    
    # Model reference
    model_id: Mapped[int] = mapped_column(
        ForeignKey("models.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
        comment="Custom model to train"
    )
    
    # Status
    status: Mapped[JobStatus] = mapped_column(
        SQLEnum(JobStatus, name="job_status", create_type=True),
        nullable=False,
        default=JobStatus.PENDING,
        index=True
    )
    
    # Configuration
    config: Mapped[Dict[str, Any]] = mapped_column(
        JSON,
        nullable=False,
        comment="Training hyperparameters, epochs, batch size, etc."
    )
    
    # Dataset info
    dataset_path: Mapped[str] = mapped_column(
        String(512),
        nullable=False,
        comment="GCS path to dataset"
    )
    
    # Progress tracking
    progress: Mapped[float] = mapped_column(
        Float,
        default=0.0,
        nullable=False,
        comment="Progress percentage (0-100)"
    )
    
    current_epoch: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    total_epochs: Mapped[int] = mapped_column(Integer, nullable=False)
    
    # Results
    metrics: Mapped[Optional[Dict[str, Any]]] = mapped_column(
        JSON,
        nullable=True,
        comment="Final training metrics (loss, accuracy, etc.)"
    )
    
    error_message: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    
    # Relationships
    group: Mapped["Group"] = relationship(
        "Group",
        back_populates="jobs"
    )
    
    model: Mapped["Model"] = relationship(
        "Model",
        back_populates="jobs"
    )
    
    data_batches: Mapped[list["DataBatch"]] = relationship(
        "DataBatch",
        back_populates="job",
        cascade="all, delete-orphan"
    )
    
    def __repr__(self) -> str:
        return f"<Job(id={self.id}, name='{self.name}', status='{self.status}', progress={self.progress}%)>"
