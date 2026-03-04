"""
Model registry for custom PyTorch models.
"""
from sqlalchemy import String, Integer, ForeignKey, Enum as SQLEnum, Text, JSON
from sqlalchemy.orm import Mapped, mapped_column, relationship
from typing import Optional, Dict, Any
from enum import Enum
from .base import Base, TimestampMixin


class ModelStatus(str, Enum):
    """Lifecycle states for custom models."""
    UPLOADING = "uploading"
    VALIDATING = "validating"
    READY = "ready"
    FAILED = "failed"
    DEPRECATED = "deprecated"


class Model(Base, TimestampMixin):
    """Custom model registry with lifecycle management."""
    
    __tablename__ = "models"
    
    # Primary key
    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    
    # Model identity
    name: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    
    # Ownership
    uploaded_by_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True
    )
    
    group_id: Mapped[int] = mapped_column(
        ForeignKey("groups.id", ondelete="CASCADE"),
        nullable=False,
        index=True
    )
    
    # Storage
    gcs_path: Mapped[str] = mapped_column(
        String(512),
        nullable=False,
        comment="GCS path: gs://meshml-models/{model_id}/model.py"
    )
    
    # Lifecycle
    status: Mapped[ModelStatus] = mapped_column(
        SQLEnum(ModelStatus, name="model_status", create_type=True),
        nullable=False,
        default=ModelStatus.UPLOADING,
        index=True
    )
    
    # Validation
    validation_error: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    
    # Metadata from MODEL_METADATA dict (use model_metadata to avoid conflict with Base.metadata)
    model_metadata: Mapped[Optional[Dict[str, Any]]] = mapped_column(
        JSON,
        nullable=True,
        comment="MODEL_METADATA from custom model file"
    )
    
    # Versioning
    version: Mapped[str] = mapped_column(String(50), nullable=False, default="1.0.0")
    parent_model_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("models.id", ondelete="SET NULL"),
        nullable=True,
        index=True
    )
    
    # Relationships
    uploaded_by_user: Mapped["User"] = relationship(
        "User",
        back_populates="models"
    )
    
    group: Mapped["Group"] = relationship(
        "Group",
        back_populates="models"
    )
    
    parent_model: Mapped[Optional["Model"]] = relationship(
        "Model",
        remote_side=[id],
        foreign_keys=[parent_model_id]
    )
    
    jobs: Mapped[list["Job"]] = relationship(
        "Job",
        back_populates="model"
    )
    
    def __repr__(self) -> str:
        return f"<Model(id={self.id}, name='{self.name}', status='{self.status}', version='{self.version}')>"
