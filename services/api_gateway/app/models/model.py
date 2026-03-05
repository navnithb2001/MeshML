"""
Model model - custom PyTorch models.
"""

from sqlalchemy import Column, String, ForeignKey, Integer, Enum as SQLEnum, JSON
from sqlalchemy.orm import relationship
import uuid
import enum

from app.models.base import Base, TimestampMixin


class ModelStatus(str, enum.Enum):
    """Model status enumeration."""
    VALIDATING = "validating"
    VALID = "valid"
    INVALID = "invalid"
    ARCHIVED = "archived"


class ModelArchitecture(str, enum.Enum):
    """Model architecture enumeration."""
    CNN = "cnn"
    RNN = "rnn"
    TRANSFORMER = "transformer"
    LSTM = "lstm"
    GAN = "gan"
    AUTOENCODER = "autoencoder"
    CUSTOM = "custom"


class Model(Base, TimestampMixin):
    """Model model for custom PyTorch models."""
    
    __tablename__ = "models"
    
    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    group_id = Column(String(36), ForeignKey("groups.id", ondelete="CASCADE"), nullable=False)
    uploaded_by = Column(String(36), ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    
    name = Column(String(255), nullable=False)
    description = Column(String(1000), nullable=True)
    
    architecture = Column(SQLEnum(ModelArchitecture), nullable=False)
    framework = Column(String(50), default="pytorch", nullable=False)
    version = Column(String(50), nullable=False)
    
    # File information
    file_url = Column(String(512), nullable=False)
    file_size = Column(Integer, nullable=False)  # in bytes
    checksum = Column(String(128), nullable=False)
    
    # Validation
    status = Column(SQLEnum(ModelStatus), default=ModelStatus.VALIDATING, nullable=False)
    validation_errors = Column(JSON, nullable=True)
    
    # Relationships
    group = relationship("Group", back_populates="models")
    uploader = relationship("User", foreign_keys=[uploaded_by])
    jobs = relationship("Job", back_populates="model")
    
    def __repr__(self):
        return f"<Model(id={self.id}, name={self.name}, status={self.status})>"
