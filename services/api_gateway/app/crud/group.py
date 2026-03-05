"""CRUD operations for group management."""

import secrets
from datetime import datetime, timedelta
from typing import Optional, List
from uuid import UUID

from sqlalchemy import select, func, and_, or_
from sqlalchemy.orm import Session, joinedload

from app.models.group import (
    Group,
    GroupMember,
    GroupInvitation,
    GroupRole,
    InvitationStatus,
    MemberStatus,
)
from app.schemas.group import (
    GroupCreate,
    GroupUpdate,
    GroupMemberCreate,
    InvitationCreate,
)


# ============================================================================
# Group CRUD
# ============================================================================

def create_group(db: Session, group_data: GroupCreate, owner_id: UUID) -> Group:
    """Create a new group and add owner as member."""
    # Create group
    group = Group(
        name=group_data.name,
        description=group_data.description,
        owner_id=owner_id,
    )
    
    # Apply settings if provided
    if group_data.settings:
        group.max_members = group_data.settings.max_members
        group.require_approval = group_data.settings.require_approval
        group.compute_sharing_enabled = group_data.settings.compute_sharing_enabled
        group.allow_public_join = group_data.settings.allow_public_join
        group.max_concurrent_jobs = group_data.settings.max_concurrent_jobs
    
    db.add(group)
    db.flush()  # Get group.id
    
    # Add owner as member
    owner_member = GroupMember(
        group_id=group.id,
        user_id=owner_id,
        role=GroupRole.OWNER,
        status=MemberStatus.ACTIVE,
    )
    db.add(owner_member)
    db.commit()
    db.refresh(group)
    
    return group


def get_group(db: Session, group_id: UUID) -> Optional[Group]:
    """Get group by ID."""
    return db.query(Group).filter(Group.id == group_id).first()


def get_group_with_owner(db: Session, group_id: UUID) -> Optional[Group]:
    """Get group with owner relationship loaded."""
    return (
        db.query(Group)
        .options(joinedload(Group.owner))
        .filter(Group.id == group_id)
        .first()
    )


def get_user_groups(
    db: Session,
    user_id: UUID,
    skip: int = 0,
    limit: int = 100,
    include_inactive: bool = False,
) -> tuple[List[Group], int]:
    """Get all groups where user is a member."""
    query = (
        db.query(Group)
        .join(GroupMember, Group.id == GroupMember.group_id)
        .filter(
            GroupMember.user_id == user_id,
            GroupMember.status == MemberStatus.ACTIVE,
        )
    )
    
    if not include_inactive:
        query = query.filter(Group.is_active == True)
    
    # Get total count
    total = query.count()
    
    # Get paginated results
    groups = query.order_by(Group.created_at.desc()).offset(skip).limit(limit).all()
    
    return groups, total


def update_group(db: Session, group_id: UUID, group_data: GroupUpdate) -> Optional[Group]:
    """Update group information."""
    group = get_group(db, group_id)
    if not group:
        return None
    
    # Update basic fields
    if group_data.name is not None:
        group.name = group_data.name
    if group_data.description is not None:
        group.description = group_data.description
    
    # Update settings
    if group_data.settings:
        group.max_members = group_data.settings.max_members
        group.require_approval = group_data.settings.require_approval
        group.compute_sharing_enabled = group_data.settings.compute_sharing_enabled
        group.allow_public_join = group_data.settings.allow_public_join
        group.max_concurrent_jobs = group_data.settings.max_concurrent_jobs
    
    db.commit()
    db.refresh(group)
    return group


def delete_group(db: Session, group_id: UUID) -> bool:
    """Delete a group (soft delete by marking inactive)."""
    group = get_group(db, group_id)
    if not group:
        return False
    
    group.is_active = False
    db.commit()
    return True


# ============================================================================
# Group Member CRUD
# ============================================================================

def get_group_member(
    db: Session,
    group_id: UUID,
    user_id: UUID,
) -> Optional[GroupMember]:
    """Get specific group member."""
    return (
        db.query(GroupMember)
        .filter(
            GroupMember.group_id == group_id,
            GroupMember.user_id == user_id,
        )
        .first()
    )


def get_group_members(
    db: Session,
    group_id: UUID,
    skip: int = 0,
    limit: int = 100,
    status: Optional[MemberStatus] = None,
) -> tuple[List[GroupMember], int]:
    """Get all members of a group."""
    query = (
        db.query(GroupMember)
        .options(joinedload(GroupMember.user))
        .filter(GroupMember.group_id == group_id)
    )
    
    if status:
        query = query.filter(GroupMember.status == status)
    else:
        # Default to active members
        query = query.filter(GroupMember.status == MemberStatus.ACTIVE)
    
    total = query.count()
    members = query.order_by(GroupMember.joined_at).offset(skip).limit(limit).all()
    
    return members, total


def add_group_member(
    db: Session,
    group_id: UUID,
    member_data: GroupMemberCreate,
) -> GroupMember:
    """Add a member to a group."""
    member = GroupMember(
        group_id=group_id,
        user_id=member_data.user_id,
        role=member_data.role,
        status=MemberStatus.ACTIVE,
    )
    db.add(member)
    db.commit()
    db.refresh(member)
    return member


def update_member_role(
    db: Session,
    group_id: UUID,
    user_id: UUID,
    new_role: GroupRole,
) -> Optional[GroupMember]:
    """Update a member's role in a group."""
    member = get_group_member(db, group_id, user_id)
    if not member:
        return None
    
    member.role = new_role
    db.commit()
    db.refresh(member)
    return member


def remove_group_member(
    db: Session,
    group_id: UUID,
    user_id: UUID,
) -> bool:
    """Remove a member from a group."""
    member = get_group_member(db, group_id, user_id)
    if not member:
        return False
    
    member.status = MemberStatus.LEFT
    db.commit()
    return True


def update_member_last_active(
    db: Session,
    group_id: UUID,
    user_id: UUID,
) -> None:
    """Update member's last active timestamp."""
    member = get_group_member(db, group_id, user_id)
    if member:
        member.last_active_at = datetime.utcnow()
        db.commit()


# ============================================================================
# Group Invitation CRUD
# ============================================================================

def create_invitation(
    db: Session,
    group_id: UUID,
    inviter_id: UUID,
    invitation_data: InvitationCreate,
    expires_in_days: int = 7,
) -> GroupInvitation:
    """Create a new group invitation."""
    # Generate secure random token
    token = secrets.token_urlsafe(32)
    
    invitation = GroupInvitation(
        group_id=group_id,
        inviter_id=inviter_id,
        invitee_email=invitation_data.invitee_email,
        role=invitation_data.role,
        token=token,
        expires_at=datetime.utcnow() + timedelta(days=expires_in_days),
        status=InvitationStatus.PENDING,
    )
    
    db.add(invitation)
    db.commit()
    db.refresh(invitation)
    return invitation


def get_invitation_by_token(db: Session, token: str) -> Optional[GroupInvitation]:
    """Get invitation by token."""
    return (
        db.query(GroupInvitation)
        .options(
            joinedload(GroupInvitation.group),
            joinedload(GroupInvitation.inviter),
        )
        .filter(GroupInvitation.token == token)
        .first()
    )


def get_group_invitations(
    db: Session,
    group_id: UUID,
    skip: int = 0,
    limit: int = 100,
    status: Optional[InvitationStatus] = None,
) -> tuple[List[GroupInvitation], int]:
    """Get all invitations for a group."""
    query = (
        db.query(GroupInvitation)
        .options(joinedload(GroupInvitation.inviter))
        .filter(GroupInvitation.group_id == group_id)
    )
    
    if status:
        query = query.filter(GroupInvitation.status == status)
    
    total = query.count()
    invitations = (
        query.order_by(GroupInvitation.created_at.desc())
        .offset(skip)
        .limit(limit)
        .all()
    )
    
    return invitations, total


def accept_invitation(
    db: Session,
    token: str,
    user_id: UUID,
) -> Optional[GroupMember]:
    """Accept an invitation and create group membership."""
    invitation = get_invitation_by_token(db, token)
    
    if not invitation:
        return None
    
    # Check if invitation is valid
    if invitation.status != InvitationStatus.PENDING:
        return None
    
    if invitation.is_expired:
        invitation.status = InvitationStatus.EXPIRED
        db.commit()
        return None
    
    # Create group membership
    member = GroupMember(
        group_id=invitation.group_id,
        user_id=user_id,
        role=invitation.role,
        status=MemberStatus.ACTIVE,
    )
    
    # Update invitation
    invitation.status = InvitationStatus.ACCEPTED
    invitation.accepted_at = datetime.utcnow()
    
    db.add(member)
    db.commit()
    db.refresh(member)
    
    return member


def decline_invitation(db: Session, token: str) -> bool:
    """Decline an invitation."""
    invitation = get_invitation_by_token(db, token)
    
    if not invitation:
        return False
    
    if invitation.status != InvitationStatus.PENDING:
        return False
    
    invitation.status = InvitationStatus.DECLINED
    db.commit()
    return True


def cancel_invitation(db: Session, invitation_id: UUID) -> bool:
    """Cancel a pending invitation."""
    invitation = db.query(GroupInvitation).filter(GroupInvitation.id == invitation_id).first()
    
    if not invitation:
        return False
    
    if invitation.status != InvitationStatus.PENDING:
        return False
    
    invitation.status = InvitationStatus.CANCELLED
    db.commit()
    return True


# ============================================================================
# Permission Checks
# ============================================================================

def check_member_permission(
    db: Session,
    group_id: UUID,
    user_id: UUID,
    required_role: Optional[GroupRole] = None,
) -> bool:
    """Check if user has permission in group."""
    member = get_group_member(db, group_id, user_id)
    
    if not member or member.status != MemberStatus.ACTIVE:
        return False
    
    if not required_role:
        return True
    
    # Role hierarchy: OWNER > ADMIN > MEMBER
    role_hierarchy = {
        GroupRole.OWNER: 3,
        GroupRole.ADMIN: 2,
        GroupRole.MEMBER: 1,
    }
    
    return role_hierarchy[member.role] >= role_hierarchy[required_role]


def is_group_owner(db: Session, group_id: UUID, user_id: UUID) -> bool:
    """Check if user is the group owner."""
    group = get_group(db, group_id)
    return group and group.owner_id == user_id
