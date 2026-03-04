"""
Data batch model for dataset sharding and distribution.
"""
from sqlalchemy import String, Integer, ForeignKey, Enum as SQLEnum, Boolean
from sqlalchemy.orm import Mapped, mapped_column, relationship
from typing import Optional
from enum import Enum
from .base import Base, TimestampMixin


class BatchStatus(str, Enum):
    """Status of a data batch."""
    PENDING = "pending"
    ASSIGNED = "assigned"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"


class DataBatch(Base, TimestampMixin):
    """Data batch for sharding and worker assignment."""
    
    __tablename__ = "data_batches"
    
    # Primary key
    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    
    # Foreign keys
    job_id: Mapped[int] = mapped_column(
        ForeignKey("jobs.id", ondelete="CASCADE"),
        nullable=False,
        index=True
    )
    
    worker_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("workers.id", ondelete="SET NULL"),
        nullable=True,
        index=True
    )
    
    # Batch info
    batch_index: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        comment="Sequential batch number within job"
    )
    
    shard_path: Mapped[str] = mapped_column(
        String(512),
        nullable=False,
        comment="GCS path to data shard"
    )
    
    size_bytes: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        comment="Size of shard in bytes"
    )
    
    checksum: Mapped[str] = mapped_column(
        String(64),
        nullable=False,
        comment="SHA-256 checksum for integrity"
    )
    
    # Status
    status: Mapped[BatchStatus] = mapped_column(
        SQLEnum(BatchStatus, name="batch_status", create_type=True),
        nullable=False,
        default=BatchStatus.PENDING,
        index=True
    )
    
    # Retry mechanism
    retry_count: Mapped[int] = mapped_column(
        Integer,
        default=0,
        nullable=False
    )
    
    max_retries: Mapped[int] = mapped_column(
        Integer,
        default=3,
        nullable=False
    )
    
    # Relationships
    job: Mapped["Job"] = relationship(
        "Job",
        back_populates="data_batches"
    )
    
    worker: Mapped[Optional["Worker"]] = relationship(
        "Worker",
        back_populates="data_batches"
    )
    
    def __repr__(self) -> str:
        return f"<DataBatch(id={self.id}, job_id={self.job_id}, batch_index={self.batch_index}, status='{self.status}')>"
