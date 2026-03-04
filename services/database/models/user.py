"""
User model for authentication and user management.
"""
from sqlalchemy import String, Boolean
from sqlalchemy.orm import Mapped, mapped_column, relationship
from typing import List
from .base import Base, TimestampMixin


class User(Base, TimestampMixin):
    """User table for authentication."""
    
    __tablename__ = "users"
    
    # Primary key
    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    
    # User credentials
    email: Mapped[str] = mapped_column(String(255), unique=True, nullable=False, index=True)
    username: Mapped[str] = mapped_column(String(100), unique=True, nullable=False, index=True)
    hashed_password: Mapped[str] = mapped_column(String(255), nullable=False)
    
    # User profile
    full_name: Mapped[str] = mapped_column(String(255), nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    is_verified: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    
    # Relationships
    owned_groups: Mapped[List["Group"]] = relationship(
        "Group",
        back_populates="owner",
        foreign_keys="Group.owner_id"
    )
    
    group_memberships: Mapped[List["GroupMember"]] = relationship(
        "GroupMember",
        back_populates="user",
        cascade="all, delete-orphan"
    )
    
    invitations_sent: Mapped[List["GroupInvitation"]] = relationship(
        "GroupInvitation",
        back_populates="invited_by_user",
        foreign_keys="GroupInvitation.invited_by_id"
    )
    
    models: Mapped[List["Model"]] = relationship(
        "Model",
        back_populates="uploaded_by_user"
    )
    
    def __repr__(self) -> str:
        return f"<User(id={self.id}, email='{self.email}', username='{self.username}')>"
