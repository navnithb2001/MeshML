"""
Job model - training jobs.
"""

from sqlalchemy import Column, String, ForeignKey, Integer, Float, Enum as SQLEnum, JSON
from sqlalchemy.orm import relationship
import uuid
import enum

from app.models.base import Base, TimestampMixin


class JobStatus(str, enum.Enum):
    """Job status enumeration."""
    PENDING = "pending"
    SHARDING = "sharding"
    READY = "ready"
    RUNNING = "running"
    PAUSED = "paused"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class Job(Base, TimestampMixin):
    """Job model for training jobs."""
    
    __tablename__ = "jobs"
    
    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    group_id = Column(String(36), ForeignKey("groups.id", ondelete="CASCADE"), nullable=False)
    model_id = Column(String(36), ForeignKey("models.id", ondelete="SET NULL"), nullable=True)
    created_by = Column(String(36), ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    
    name = Column(String(255), nullable=False)
    description = Column(String(1000), nullable=True)
    
    # Dataset
    dataset_url = Column(String(512), nullable=False)
    
    # Status
    status = Column(SQLEnum(JobStatus), default=JobStatus.PENDING, nullable=False)
    
    # Configuration (stored as JSON)
    config = Column(JSON, nullable=False)
    
    # Progress
    total_epochs = Column(Integer, nullable=False)
    current_epoch = Column(Integer, default=0, nullable=False)
    total_batches = Column(Integer, default=0, nullable=False)
    completed_batches = Column(Integer, default=0, nullable=False)
    failed_batches = Column(Integer, default=0, nullable=False)
    
    # Metrics
    current_loss = Column(Float, nullable=True)
    current_accuracy = Column(Float, nullable=True)
    best_loss = Column(Float, nullable=True)
    best_accuracy = Column(Float, nullable=True)
    final_loss = Column(Float, nullable=True)
    final_accuracy = Column(Float, nullable=True)
    
    # Relationships
    group = relationship("Group", back_populates="jobs")
    model = relationship("Model", back_populates="jobs")
    created_by_user = relationship("User", back_populates="jobs_created", foreign_keys=[created_by])
    
    def __repr__(self):
        return f"<Job(id={self.id}, name={self.name}, status={self.status})>"
