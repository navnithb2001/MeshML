"""
Worker model for device registration and tracking.
"""
from sqlalchemy import String, Integer, Float, Enum as SQLEnum, JSON, DateTime
from sqlalchemy.orm import Mapped, mapped_column, relationship
from typing import Optional, Dict, Any
from datetime import datetime
from enum import Enum
from .base import Base, TimestampMixin


class WorkerType(str, Enum):
    """Type of worker."""
    PYTHON = "python"
    CPP = "cpp"
    JAVASCRIPT = "javascript"


class WorkerStatus(str, Enum):
    """Worker status."""
    ONLINE = "online"
    OFFLINE = "offline"
    BUSY = "busy"
    ERROR = "error"


class Worker(Base, TimestampMixin):
    """Worker/device registration and tracking."""
    
    __tablename__ = "workers"
    
    # Primary key
    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    
    # Worker identity
    worker_id: Mapped[str] = mapped_column(
        String(255),
        unique=True,
        nullable=False,
        index=True,
        comment="Unique worker identifier (e.g., UUID)"
    )
    
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    
    # Worker type
    worker_type: Mapped[WorkerType] = mapped_column(
        SQLEnum(WorkerType, name="worker_type", create_type=True),
        nullable=False,
        index=True
    )
    
    # Status
    status: Mapped[WorkerStatus] = mapped_column(
        SQLEnum(WorkerStatus, name="worker_status", create_type=True),
        nullable=False,
        default=WorkerStatus.OFFLINE,
        index=True
    )
    
    # Capabilities (JSON field)
    capabilities: Mapped[Dict[str, Any]] = mapped_column(
        JSON,
        nullable=False,
        comment="GPU model, RAM, CPU cores, network speed, etc."
    )
    
    # Connection info
    ip_address: Mapped[Optional[str]] = mapped_column(String(45), nullable=True)
    port: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    
    # Heartbeat
    last_heartbeat: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        index=True
    )
    
    # Relationships
    data_batches: Mapped[list["DataBatch"]] = relationship(
        "DataBatch",
        back_populates="worker"
    )
    
    def __repr__(self) -> str:
        return f"<Worker(id={self.id}, worker_id='{self.worker_id}', type='{self.worker_type}', status='{self.status}')>"
