"""
Group models for collaboration system.
"""
from sqlalchemy import String, Integer, ForeignKey, Enum as SQLEnum, Boolean, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship
from typing import List, Optional
from datetime import datetime
from enum import Enum
from .base import Base, TimestampMixin


class GroupRole(str, Enum):
    """Roles within a group."""
    OWNER = "owner"
    ADMIN = "admin"
    MEMBER = "member"


class InvitationStatus(str, Enum):
    """Status of group invitation."""
    PENDING = "pending"
    ACCEPTED = "accepted"
    REJECTED = "rejected"
    EXPIRED = "expired"


class Group(Base, TimestampMixin):
    """Group table for collaboration."""
    
    __tablename__ = "groups"
    
    # Primary key
    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    
    # Group details
    name: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    
    # Owner
    owner_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True
    )
    
    # Settings
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    
    # Relationships
    owner: Mapped["User"] = relationship(
        "User",
        back_populates="owned_groups",
        foreign_keys=[owner_id]
    )
    
    members: Mapped[List["GroupMember"]] = relationship(
        "GroupMember",
        back_populates="group",
        cascade="all, delete-orphan"
    )
    
    invitations: Mapped[List["GroupInvitation"]] = relationship(
        "GroupInvitation",
        back_populates="group",
        cascade="all, delete-orphan"
    )
    
    jobs: Mapped[List["Job"]] = relationship(
        "Job",
        back_populates="group"
    )
    
    models: Mapped[List["Model"]] = relationship(
        "Model",
        back_populates="group"
    )
    
    def __repr__(self) -> str:
        return f"<Group(id={self.id}, name='{self.name}', owner_id={self.owner_id})>"


class GroupMember(Base, TimestampMixin):
    """Group membership with roles."""
    
    __tablename__ = "group_members"
    
    # Primary key
    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    
    # Foreign keys
    group_id: Mapped[int] = mapped_column(
        ForeignKey("groups.id", ondelete="CASCADE"),
        nullable=False,
        index=True
    )
    
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True
    )
    
    # Role
    role: Mapped[GroupRole] = mapped_column(
        SQLEnum(GroupRole, name="group_role", create_type=True),
        nullable=False,
        default=GroupRole.MEMBER
    )
    
    # Relationships
    group: Mapped["Group"] = relationship(
        "Group",
        back_populates="members"
    )
    
    user: Mapped["User"] = relationship(
        "User",
        back_populates="group_memberships"
    )
    
    def __repr__(self) -> str:
        return f"<GroupMember(group_id={self.group_id}, user_id={self.user_id}, role='{self.role}')>"


class GroupInvitation(Base, TimestampMixin):
    """Group invitation system."""
    
    __tablename__ = "group_invitations"
    
    # Primary key
    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    
    # Foreign keys
    group_id: Mapped[int] = mapped_column(
        ForeignKey("groups.id", ondelete="CASCADE"),
        nullable=False,
        index=True
    )
    
    invited_by_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False
    )
    
    # Invitation details
    email: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    token: Mapped[str] = mapped_column(String(255), unique=True, nullable=False, index=True)
    
    role: Mapped[GroupRole] = mapped_column(
        SQLEnum(GroupRole, name="group_role_invitation", create_type=False),
        nullable=False,
        default=GroupRole.MEMBER
    )
    
    status: Mapped[InvitationStatus] = mapped_column(
        SQLEnum(InvitationStatus, name="invitation_status", create_type=True),
        nullable=False,
        default=InvitationStatus.PENDING
    )
    
    expires_at: Mapped[datetime] = mapped_column(nullable=False)
    
    # Relationships
    group: Mapped["Group"] = relationship(
        "Group",
        back_populates="invitations"
    )
    
    invited_by_user: Mapped["User"] = relationship(
        "User",
        back_populates="invitations_sent",
        foreign_keys=[invited_by_id]
    )
    
    def __repr__(self) -> str:
        return f"<GroupInvitation(group_id={self.group_id}, email='{self.email}', status='{self.status}')>"
