"""
Worker model - student devices.
"""

from sqlalchemy import Column, String, ForeignKey, Integer, Enum as SQLEnum, JSON, DateTime
from sqlalchemy.orm import relationship
import uuid
import enum

from app.models.base import Base, TimestampMixin


class WorkerType(str, enum.Enum):
    """Worker type enumeration."""
    PYTHON = "python"
    CPP = "cpp"
    JAVASCRIPT = "javascript"
    MOBILE = "mobile"


class WorkerStatus(str, enum.Enum):
    """Worker status enumeration."""
    IDLE = "idle"
    BUSY = "busy"
    OFFLINE = "offline"
    FAILED = "failed"
    DRAINING = "draining"


class Worker(Base, TimestampMixin):
    """Worker model for student devices."""
    
    __tablename__ = "workers"
    
    id = Column(String(255), primary_key=True)  # Worker provides its own ID
    user_id = Column(String(36), ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    
    type = Column(SQLEnum(WorkerType), nullable=False)
    version = Column(String(50), nullable=False)
    status = Column(SQLEnum(WorkerStatus), default=WorkerStatus.IDLE, nullable=False)
    
    # Capabilities (stored as JSON)
    capabilities = Column(JSON, nullable=False)
    
    # Current assignment
    current_job_id = Column(String(36), ForeignKey("jobs.id", ondelete="SET NULL"), nullable=True)
    current_batch_id = Column(String(100), nullable=True)
    
    # Statistics
    batches_completed = Column(Integer, default=0, nullable=False)
    total_compute_time = Column(Integer, default=0, nullable=False)  # in seconds
    consecutive_failures = Column(Integer, default=0, nullable=False)
    
    # Health
    last_heartbeat = Column(DateTime, nullable=True)
    
    # Relationships
    user = relationship("User", back_populates="workers")
    
    def __repr__(self):
        return f"<Worker(id={self.id}, type={self.type}, status={self.status})>"
