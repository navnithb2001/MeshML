"""
Group models - collaboration groups, members, and invitations.
"""

from sqlalchemy import Column, String, Boolean, ForeignKey, DateTime, Integer, Enum as SQLEnum
from sqlalchemy.orm import relationship
from datetime import datetime, timedelta
import uuid
import secrets
import enum

from app.models.base import Base, TimestampMixin


class GroupRole(str, enum.Enum):
    """Group member roles."""
    OWNER = "owner"
    ADMIN = "admin"
    MEMBER = "member"


class InvitationStatus(str, enum.Enum):
    """Group invitation status."""
    PENDING = "pending"
    ACCEPTED = "accepted"
    DECLINED = "declined"
    EXPIRED = "expired"
    CANCELLED = "cancelled"


class MemberStatus(str, enum.Enum):
    """Group member status."""
    ACTIVE = "active"
    SUSPENDED = "suspended"
    LEFT = "left"


class Group(Base, TimestampMixin):
    """Group model for collaboration."""
    
    __tablename__ = "groups"
    
    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    name = Column(String(255), nullable=False)
    description = Column(String(1000), nullable=True)
    owner_id = Column(String(36), ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    
    # Status
    is_active = Column(Boolean, default=True, nullable=False)
    
    # Settings (stored as individual columns for easier querying)
    max_members = Column(Integer, default=100, nullable=False)
    require_approval = Column(Boolean, default=True, nullable=False)
    compute_sharing_enabled = Column(Boolean, default=True, nullable=False)
    allow_public_join = Column(Boolean, default=False, nullable=False)
    max_concurrent_jobs = Column(Integer, default=10, nullable=False)
    
    # Statistics
    total_compute_hours = Column(Integer, default=0, nullable=False)
    total_jobs_completed = Column(Integer, default=0, nullable=False)
    
    # Relationships
    owner = relationship("User", back_populates="owned_groups", foreign_keys=[owner_id])
    members = relationship("GroupMember", back_populates="group", cascade="all, delete-orphan")
    invitations = relationship("GroupInvitation", back_populates="group", cascade="all, delete-orphan")
    jobs = relationship("Job", back_populates="group", cascade="all, delete-orphan")
    models = relationship("Model", back_populates="group", cascade="all, delete-orphan")
    
    def __repr__(self):
        return f"<Group(id={self.id}, name={self.name}, owner_id={self.owner_id})>"


class GroupMember(Base, TimestampMixin):
    """Group membership model."""
    
    __tablename__ = "group_members"
    
    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    group_id = Column(String(36), ForeignKey("groups.id", ondelete="CASCADE"), nullable=False)
    user_id = Column(String(36), ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    
    role = Column(SQLEnum(GroupRole), default=GroupRole.MEMBER, nullable=False)
    status = Column(SQLEnum(MemberStatus), default=MemberStatus.ACTIVE, nullable=False)
    
    # Statistics
    compute_contributed = Column(Integer, default=0, nullable=False)  # in seconds
    jobs_created = Column(Integer, default=0, nullable=False)
    workers_registered = Column(Integer, default=0, nullable=False)
    
    # Timestamps
    joined_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    last_active_at = Column(DateTime, nullable=True)
    
    # Relationships
    group = relationship("Group", back_populates="members")
    user = relationship("User", back_populates="group_memberships")
    
    def __repr__(self):
        return f"<GroupMember(group_id={self.group_id}, user_id={self.user_id}, role={self.role})>"


class GroupInvitation(Base, TimestampMixin):
    """Group invitation model."""
    
    __tablename__ = "group_invitations"
    
    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    group_id = Column(String(36), ForeignKey("groups.id", ondelete="CASCADE"), nullable=False)
    inviter_id = Column(String(36), ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    
    invitee_email = Column(String(255), nullable=False, index=True)
    role = Column(SQLEnum(GroupRole), default=GroupRole.MEMBER, nullable=False)
    status = Column(SQLEnum(InvitationStatus), default=InvitationStatus.PENDING, nullable=False)
    
    # Token for accepting/declining
    token = Column(String(100), unique=True, nullable=False, default=lambda: secrets.token_urlsafe(32))
    
    # Timestamps
    expires_at = Column(DateTime, default=lambda: datetime.utcnow() + timedelta(days=7), nullable=False)
    accepted_at = Column(DateTime, nullable=True)
    
    # Relationships
    group = relationship("Group", back_populates="invitations")
    inviter = relationship("User", foreign_keys=[inviter_id])
    
    def __repr__(self):
        return f"<GroupInvitation(id={self.id}, group_id={self.group_id}, email={self.invitee_email}, status={self.status})>"
    
    @property
    def is_expired(self) -> bool:
        """Check if invitation has expired."""
        return datetime.utcnow() > self.expires_at
