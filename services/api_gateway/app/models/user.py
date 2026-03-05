"""
User model - represents registered users.
"""

from sqlalchemy import Column, String, Boolean, Integer
from sqlalchemy.orm import relationship
import uuid

from app.models.base import Base, TimestampMixin


class User(Base, TimestampMixin):
    """User model for authentication and profile."""
    
    __tablename__ = "users"
    
    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    email = Column(String(255), unique=True, nullable=False, index=True)
    username = Column(String(255), unique=True, nullable=False, index=True)
    full_name = Column(String(255), nullable=True)
    password_hash = Column(String(255), nullable=False)
    
    # Status
    is_active = Column(Boolean, default=True, nullable=False)
    is_verified = Column(Boolean, default=False, nullable=False)
    is_superuser = Column(Boolean, default=False, nullable=False)
    
    # Profile
    avatar_url = Column(String(512), nullable=True)
    bio = Column(String(1000), nullable=True)
    
    # Statistics
    total_compute_contributed = Column(Integer, default=0, nullable=False)  # in seconds
    
    # Relationships
    owned_groups = relationship("Group", back_populates="owner", foreign_keys="Group.owner_id")
    group_memberships = relationship("GroupMember", back_populates="user", cascade="all, delete-orphan")
    workers = relationship("Worker", back_populates="user", cascade="all, delete-orphan")
    jobs_created = relationship("Job", back_populates="created_by_user", foreign_keys="Job.created_by")
    
    def __repr__(self):
        return f"<User(id={self.id}, email={self.email}, username={self.username})>"
