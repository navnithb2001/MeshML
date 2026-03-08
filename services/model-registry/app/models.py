"""
Database models for Model Registry
Extends the existing database models from Phase 1
"""

from sqlalchemy import Column, Integer, String, Text, DateTime, ForeignKey, JSON, Enum as SQLEnum
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import relationship
from datetime import datetime
import enum

Base = declarative_base()


class ModelState(str, enum.Enum):
    """Model lifecycle states"""
    UPLOADING = "uploading"
    VALIDATING = "validating"
    READY = "ready"
    FAILED = "failed"
    DEPRECATED = "deprecated"


class Model(Base):
    """Model registry table - extends Phase 1 model"""
    __tablename__ = "models"
    
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(255), nullable=False, index=True)
    description = Column(Text, nullable=True)
    
    # Ownership
    group_id = Column(Integer, ForeignKey("groups.id"), nullable=False, index=True)
    created_by_user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    
    # Storage
    gcs_path = Column(String(512), nullable=True)  # gs://meshml-models/models/{model_id}/model.py
    file_size_bytes = Column(Integer, nullable=True)
    file_hash = Column(String(64), nullable=True)  # SHA-256 hash
    
    # State & Lifecycle
    state = Column(SQLEnum(ModelState), default=ModelState.UPLOADING, index=True)
    validation_message = Column(Text, nullable=True)  # Error message if validation fails
    
    # Metadata
    architecture_type = Column(String(100), nullable=True, index=True)  # e.g., "CNN", "Transformer"
    dataset_type = Column(String(100), nullable=True, index=True)  # e.g., "ImageNet", "CIFAR-10"
    framework = Column(String(50), default="PyTorch")
    metadata = Column(JSON, nullable=True)  # MODEL_METADATA from uploaded file
    
    # Versioning
    version = Column(String(50), default="1.0.0")
    parent_model_id = Column(Integer, ForeignKey("models.id"), nullable=True, index=True)
    
    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False, index=True)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)
    deprecated_at = Column(DateTime, nullable=True)
    
    # Usage tracking
    usage_count = Column(Integer, default=0)  # How many jobs use this model
    download_count = Column(Integer, default=0)  # Download statistics
    
    # Relationships
    parent_model = relationship("Model", remote_side=[id], backref="child_models")


class ModelUsage(Base):
    """Track which jobs use which models"""
    __tablename__ = "model_usage"
    
    id = Column(Integer, primary_key=True, index=True)
    model_id = Column(Integer, ForeignKey("models.id"), nullable=False, index=True)
    job_id = Column(Integer, ForeignKey("jobs.id"), nullable=False, index=True)
    started_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    completed_at = Column(DateTime, nullable=True)
