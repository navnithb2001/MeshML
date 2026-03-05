"""Group management API endpoints."""

from typing import Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.orm import Session

from app.core.exceptions import (
    NotFoundError,
    AuthorizationError,
    ConflictError,
    ValidationError,
)
from app.dependencies import get_db
from app.models.group import GroupRole, InvitationStatus, MemberStatus
from app.schemas.group import (
    GroupCreate,
    GroupUpdate,
    GroupResponse,
    GroupDetailResponse,
    GroupListResponse,
    GroupMemberUpdateRole,
    GroupMemberResponse,
    MemberListResponse,
    InvitationCreate,
    InvitationResponse,
    InvitationListResponse,
    InvitationAcceptRequest,
)
from app.crud import group as group_crud

# TODO: Import current_user dependency once auth is implemented
# from app.dependencies import get_current_user
# from app.models.user import User


router = APIRouter(prefix="/groups", tags=["groups"])


# Temporary mock for current user - will be replaced with real auth in TASK-3.5
async def get_current_user_temp():
    """Temporary mock user - REMOVE THIS when auth is implemented."""
    from app.models.user import User
    from uuid import uuid4
    
    user = User(
        id=uuid4(),
        email="test@example.com",
        username="testuser",
        password_hash="mock",
    )
    return user


# ============================================================================
# Group Management Endpoints
# ============================================================================

@router.post(
    "",
    response_model=GroupResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create a new group",
    description="Create a new group. The creator becomes the owner automatically.",
)
async def create_group(
    group_data: GroupCreate,
    db: Session = Depends(get_db),
    current_user = Depends(get_current_user_temp),
):
    """Create a new group."""
    group = group_crud.create_group(db, group_data, current_user.id)
    return group


@router.get(
    "",
    response_model=GroupListResponse,
    summary="List user's groups",
    description="Get all groups where the current user is a member.",
)
async def list_groups(
    skip: int = Query(0, ge=0, description="Number of records to skip"),
    limit: int = Query(100, ge=1, le=500, description="Maximum records to return"),
    include_inactive: bool = Query(False, description="Include inactive groups"),
    db: Session = Depends(get_db),
    current_user = Depends(get_current_user_temp),
):
    """List all groups for current user."""
    groups, total = group_crud.get_user_groups(
        db,
        current_user.id,
        skip=skip,
        limit=limit,
        include_inactive=include_inactive,
    )
    
    return GroupListResponse(
        groups=groups,
        total=total,
        page=skip // limit + 1,
        page_size=limit,
    )


@router.get(
    "/{group_id}",
    response_model=GroupDetailResponse,
    summary="Get group details",
    description="Get detailed information about a specific group.",
)
async def get_group(
    group_id: UUID,
    db: Session = Depends(get_db),
    current_user = Depends(get_current_user_temp),
):
    """Get group by ID."""
    # Check if user is a member
    if not group_crud.check_member_permission(db, group_id, current_user.id):
        raise AuthorizationError("Not a member of this group")
    
    group = group_crud.get_group_with_owner(db, group_id)
    if not group:
        raise NotFoundError(f"Group {group_id} not found")
    
    # Get member count
    _, member_count = group_crud.get_group_members(db, group_id, limit=0)
    
    return GroupDetailResponse(
        **group.__dict__,
        owner=group.owner,
        member_count=member_count,
    )


@router.patch(
    "/{group_id}",
    response_model=GroupResponse,
    summary="Update group",
    description="Update group information. Only admins and owners can update.",
)
async def update_group(
    group_id: UUID,
    group_data: GroupUpdate,
    db: Session = Depends(get_db),
    current_user = Depends(get_current_user_temp),
):
    """Update group information."""
    # Check if user has admin permission
    if not group_crud.check_member_permission(db, group_id, current_user.id, GroupRole.ADMIN):
        raise AuthorizationError("Only admins can update group settings")
    
    group = group_crud.update_group(db, group_id, group_data)
    if not group:
        raise NotFoundError(f"Group {group_id} not found")
    
    return group


@router.delete(
    "/{group_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete group",
    description="Delete a group. Only the owner can delete a group.",
)
async def delete_group(
    group_id: UUID,
    db: Session = Depends(get_db),
    current_user = Depends(get_current_user_temp),
):
    """Delete a group (soft delete)."""
    # Check if user is the owner
    if not group_crud.is_group_owner(db, group_id, current_user.id):
        raise AuthorizationError("Only the owner can delete a group")
    
    success = group_crud.delete_group(db, group_id)
    if not success:
        raise NotFoundError(f"Group {group_id} not found")
    
    return None


# ============================================================================
# Group Member Management Endpoints
# ============================================================================

@router.get(
    "/{group_id}/members",
    response_model=MemberListResponse,
    summary="List group members",
    description="Get all members of a group.",
)
async def list_members(
    group_id: UUID,
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=500),
    status: Optional[MemberStatus] = Query(None, description="Filter by member status"),
    db: Session = Depends(get_db),
    current_user = Depends(get_current_user_temp),
):
    """List all members of a group."""
    # Check if user is a member
    if not group_crud.check_member_permission(db, group_id, current_user.id):
        raise AuthorizationError("Not a member of this group")
    
    members, total = group_crud.get_group_members(
        db,
        group_id,
        skip=skip,
        limit=limit,
        status=status,
    )
    
    return MemberListResponse(
        members=members,
        total=total,
        page=skip // limit + 1,
        page_size=limit,
    )


@router.put(
    "/{group_id}/members/{user_id}/role",
    response_model=GroupMemberResponse,
    summary="Update member role",
    description="Update a member's role. Only owners and admins can update roles.",
)
async def update_member_role(
    group_id: UUID,
    user_id: UUID,
    role_data: GroupMemberUpdateRole,
    db: Session = Depends(get_db),
    current_user = Depends(get_current_user_temp),
):
    """Update a member's role in the group."""
    # Check if user has admin permission
    if not group_crud.check_member_permission(db, group_id, current_user.id, GroupRole.ADMIN):
        raise AuthorizationError("Only admins can update member roles")
    
    # Prevent changing owner role (except by the owner themselves)
    target_member = group_crud.get_group_member(db, group_id, user_id)
    if target_member and target_member.role == GroupRole.OWNER:
        if not group_crud.is_group_owner(db, group_id, current_user.id):
            raise AuthorizationError("Cannot change the owner's role")
    
    # Prevent assigning owner role (use transfer ownership endpoint instead)
    if role_data.role == GroupRole.OWNER:
        raise ValidationError("Use transfer ownership endpoint to assign owner role")
    
    member = group_crud.update_member_role(db, group_id, user_id, role_data.role)
    if not member:
        raise NotFoundError(f"Member {user_id} not found in group {group_id}")
    
    return member


@router.delete(
    "/{group_id}/members/{user_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Remove member",
    description="Remove a member from the group. Admins can remove members, users can remove themselves.",
)
async def remove_member(
    group_id: UUID,
    user_id: UUID,
    db: Session = Depends(get_db),
    current_user = Depends(get_current_user_temp),
):
    """Remove a member from the group."""
    # Check permissions: admins can remove anyone, users can remove themselves
    is_admin = group_crud.check_member_permission(db, group_id, current_user.id, GroupRole.ADMIN)
    is_self = user_id == current_user.id
    
    if not (is_admin or is_self):
        raise AuthorizationError("You don't have permission to remove this member")
    
    # Prevent removing the owner
    if group_crud.is_group_owner(db, group_id, user_id):
        raise ValidationError("Cannot remove the group owner. Transfer ownership first.")
    
    success = group_crud.remove_group_member(db, group_id, user_id)
    if not success:
        raise NotFoundError(f"Member {user_id} not found in group {group_id}")
    
    return None


# ============================================================================
# Group Invitation Endpoints
# ============================================================================

@router.post(
    "/{group_id}/invitations",
    response_model=InvitationResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Send group invitation",
    description="Send an invitation to join the group. Only admins can send invitations.",
)
async def create_invitation(
    group_id: UUID,
    invitation_data: InvitationCreate,
    db: Session = Depends(get_db),
    current_user = Depends(get_current_user_temp),
):
    """Create a new group invitation."""
    # Check if user has admin permission
    if not group_crud.check_member_permission(db, group_id, current_user.id, GroupRole.ADMIN):
        raise AuthorizationError("Only admins can send invitations")
    
    # Check if group exists
    group = group_crud.get_group(db, group_id)
    if not group:
        raise NotFoundError(f"Group {group_id} not found")
    
    # TODO: Check if invitee is already a member
    # TODO: Send email notification
    
    invitation = group_crud.create_invitation(
        db,
        group_id,
        current_user.id,
        invitation_data,
    )
    
    return invitation


@router.get(
    "/{group_id}/invitations",
    response_model=InvitationListResponse,
    summary="List group invitations",
    description="Get all invitations for a group. Only admins can view invitations.",
)
async def list_invitations(
    group_id: UUID,
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=500),
    status: Optional[InvitationStatus] = Query(None, description="Filter by invitation status"),
    db: Session = Depends(get_db),
    current_user = Depends(get_current_user_temp),
):
    """List all invitations for a group."""
    # Check if user has admin permission
    if not group_crud.check_member_permission(db, group_id, current_user.id, GroupRole.ADMIN):
        raise AuthorizationError("Only admins can view invitations")
    
    invitations, total = group_crud.get_group_invitations(
        db,
        group_id,
        skip=skip,
        limit=limit,
        status=status,
    )
    
    return InvitationListResponse(
        invitations=invitations,
        total=total,
        page=skip // limit + 1,
        page_size=limit,
    )


@router.post(
    "/invitations/accept",
    response_model=GroupMemberResponse,
    summary="Accept invitation",
    description="Accept a group invitation using the invitation token.",
)
async def accept_invitation(
    request: InvitationAcceptRequest,
    db: Session = Depends(get_db),
    current_user = Depends(get_current_user_temp),
):
    """Accept a group invitation."""
    # TODO: Verify invitation email matches current user email
    
    member = group_crud.accept_invitation(db, request.token, current_user.id)
    
    if not member:
        raise ValidationError("Invalid or expired invitation token")
    
    return member


@router.post(
    "/invitations/{token}/decline",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Decline invitation",
    description="Decline a group invitation.",
)
async def decline_invitation(
    token: str,
    db: Session = Depends(get_db),
):
    """Decline a group invitation."""
    success = group_crud.decline_invitation(db, token)
    
    if not success:
        raise ValidationError("Invalid or expired invitation token")
    
    return None


@router.delete(
    "/invitations/{invitation_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Cancel invitation",
    description="Cancel a pending invitation. Only the inviter or admins can cancel.",
)
async def cancel_invitation(
    invitation_id: UUID,
    db: Session = Depends(get_db),
    current_user = Depends(get_current_user_temp),
):
    """Cancel a pending invitation."""
    # TODO: Check if user is the inviter or an admin
    
    success = group_crud.cancel_invitation(db, invitation_id)
    
    if not success:
        raise ValidationError("Cannot cancel this invitation")
    
    return None
