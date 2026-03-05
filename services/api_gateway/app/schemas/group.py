"""Group schemas for request/response validation."""

from datetime import datetime
from typing import Optional, Dict, Any
from uuid import UUID

from pydantic import BaseModel, EmailStr, Field, ConfigDict

from app.models.group import GroupRole, InvitationStatus, MemberStatus
from app.schemas.user import UserPublicResponse


# ============================================================================
# Group Schemas
# ============================================================================

class GroupBase(BaseModel):
    """Base group schema with common fields."""
    
    name: str = Field(..., min_length=3, max_length=100)
    description: Optional[str] = Field(None, max_length=1000)


class GroupSettings(BaseModel):
    """Group settings schema."""
    
    max_members: int = Field(default=100, ge=2, le=1000)
    require_approval: bool = False
    compute_sharing_enabled: bool = True
    allow_public_join: bool = False
    max_concurrent_jobs: int = Field(default=10, ge=1, le=100)


class GroupCreate(GroupBase):
    """Schema for creating a new group."""
    
    settings: Optional[GroupSettings] = None


class GroupUpdate(BaseModel):
    """Schema for updating a group."""
    
    name: Optional[str] = Field(None, min_length=3, max_length=100)
    description: Optional[str] = Field(None, max_length=1000)
    settings: Optional[GroupSettings] = None


class GroupStatistics(BaseModel):
    """Group statistics schema."""
    
    model_config = ConfigDict(from_attributes=True)
    
    total_compute_hours: float = 0.0
    total_jobs_completed: int = 0
    member_count: int = 0


class GroupResponse(GroupBase):
    """Schema for group responses."""
    
    model_config = ConfigDict(from_attributes=True)
    
    id: UUID
    owner_id: UUID
    is_active: bool
    settings: Dict[str, Any]
    statistics: Dict[str, Any]
    created_at: datetime
    updated_at: datetime


class GroupDetailResponse(GroupResponse):
    """Schema for detailed group responses with owner info."""
    
    owner: UserPublicResponse
    member_count: int = 0


# ============================================================================
# Group Member Schemas
# ============================================================================

class GroupMemberBase(BaseModel):
    """Base group member schema."""
    
    role: GroupRole


class GroupMemberCreate(GroupMemberBase):
    """Schema for adding a member to a group."""
    
    user_id: UUID


class GroupMemberUpdateRole(BaseModel):
    """Schema for updating member role."""
    
    role: GroupRole


class GroupMemberStatistics(BaseModel):
    """Member statistics schema."""
    
    model_config = ConfigDict(from_attributes=True)
    
    compute_contributed: int = 0
    jobs_created: int = 0
    workers_registered: int = 0


class GroupMemberResponse(BaseModel):
    """Schema for group member responses."""
    
    model_config = ConfigDict(from_attributes=True)
    
    id: UUID
    group_id: UUID
    user_id: UUID
    role: GroupRole
    status: MemberStatus
    statistics: Dict[str, Any]
    joined_at: datetime
    last_active_at: Optional[datetime] = None
    user: UserPublicResponse


# ============================================================================
# Group Invitation Schemas
# ============================================================================

class InvitationBase(BaseModel):
    """Base invitation schema."""
    
    invitee_email: EmailStr
    role: GroupRole = GroupRole.MEMBER


class InvitationCreate(InvitationBase):
    """Schema for creating a group invitation."""
    
    pass


class InvitationResponse(BaseModel):
    """Schema for invitation responses."""
    
    model_config = ConfigDict(from_attributes=True)
    
    id: UUID
    group_id: UUID
    inviter_id: UUID
    invitee_email: str
    role: GroupRole
    status: InvitationStatus
    token: str
    expires_at: datetime
    accepted_at: Optional[datetime] = None
    created_at: datetime


class InvitationDetailResponse(InvitationResponse):
    """Schema for detailed invitation with group and inviter info."""
    
    inviter: UserPublicResponse
    group_name: str


class InvitationAcceptRequest(BaseModel):
    """Schema for accepting an invitation."""
    
    token: str


# ============================================================================
# Bulk Operations
# ============================================================================

class GroupListResponse(BaseModel):
    """Schema for paginated group list."""
    
    groups: list[GroupResponse]
    total: int
    page: int
    page_size: int


class MemberListResponse(BaseModel):
    """Schema for paginated member list."""
    
    members: list[GroupMemberResponse]
    total: int
    page: int
    page_size: int


class InvitationListResponse(BaseModel):
    """Schema for paginated invitation list."""
    
    invitations: list[InvitationResponse]
    total: int
    page: int
    page_size: int
