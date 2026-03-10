"""
Group management endpoints

Endpoints:
- POST /api/groups - Create new group
- GET /api/groups - List user's groups
- GET /api/groups/public - List public groups
- GET /api/groups/{group_id} - Get group details
- POST /api/groups/{group_id}/join - Join public group
- GET /api/groups/{group_id}/members - List group members
- PUT /api/groups/{group_id}/members/{user_id}/role - Update member role
- DELETE /api/groups/{group_id}/members/{user_id} - Remove member
"""

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from datetime import datetime
from typing import List
import logging

from app.utils.database import get_db
from app.models.group import Group, GroupMember
from app.models.user import User
from app.routers.auth import get_current_user
from app.schemas.group import (
    GroupCreateRequest,
    GroupResponse,
    GroupMemberResponse,
    JoinGroupRequest,
    UpdateMemberRoleRequest
)

logger = logging.getLogger(__name__)
router = APIRouter()


@router.post("", response_model=GroupResponse, status_code=status.HTTP_201_CREATED)
async def create_group(
    request: GroupCreateRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Create new training group
    
    Args:
        request: Group creation data
        current_user: Authenticated user
        db: Database session
        
    Returns:
        Created group information
    """
    logger.info(f"Creating group: {request.name} by user {current_user.id}")
    
    # Create group
    group = Group(
        name=request.name,
        description=request.description,
        is_public=request.is_public,
        owner_id=current_user.id
    )
    
    db.add(group)
    await db.flush()  # Get group ID
    
    # Add creator as owner
    owner_member = GroupMember(
        group_id=group.id,
        user_id=current_user.id,
        role="owner"
    )
    
    db.add(owner_member)
    await db.commit()
    await db.refresh(group)
    
    logger.info(f"Group created: {group.id}")
    return group


@router.get("", response_model=dict)
async def list_user_groups(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    List all groups where the current user is a member
    
    Args:
        current_user: Authenticated user
        db: Database session
        
    Returns:
        Dictionary with list of groups
    """
    # Get all group memberships for current user
    result = await db.execute(
        select(GroupMember)
        .where(GroupMember.user_id == current_user.id)
    )
    memberships = result.scalars().all()
    
    # Fetch group details for each membership
    groups_data = []
    for membership in memberships:
        group_result = await db.execute(
            select(Group).where(Group.id == membership.group_id)
        )
        group = group_result.scalar_one_or_none()
        
        if group:
            groups_data.append({
                "id": str(group.id),
                "name": group.name,
                "description": group.description,
                "is_public": group.is_public,
                "role": membership.role,
                "created_at": group.created_at.isoformat() if group.created_at else None
            })
    
    logger.info(f"Retrieved {len(groups_data)} groups for user {current_user.id}")
    return {"groups": groups_data}


@router.get("/public", response_model=dict)
async def list_public_groups(
    db: AsyncSession = Depends(get_db)
):
    """
    List all public groups
    
    Args:
        db: Database session
        
    Returns:
        List of public groups with metadata
    """
    result = await db.execute(
        select(Group).where(Group.is_public == True)
    )
    groups = result.scalars().all()
    
    # Get member counts
    groups_data = []
    for group in groups:
        member_count_result = await db.execute(
            select(GroupMember).where(GroupMember.group_id == group.id)
        )
        member_count = len(member_count_result.scalars().all())
        
        groups_data.append({
            "id": group.id,
            "name": group.name,
            "description": group.description,
            "worker_count": member_count,
            "created_at": group.created_at.isoformat()
        })
    
    logger.info(f"Retrieved {len(groups_data)} public groups")
    return {"groups": groups_data}


@router.get("/{group_id}", response_model=GroupResponse)
async def get_group(
    group_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Get group details
    
    Args:
        group_id: Group ID
        db: Database session
        current_user: Authenticated user
        
    Returns:
        Group information
        
    Raises:
        404: Group not found
        403: User not member of private group
    """
    result = await db.execute(
        select(Group).where(Group.id == group_id)
    )
    group = result.scalar_one_or_none()
    
    if not group:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Group not found"
        )
    
    # Check access for private groups
    if not group.is_public:
        member_result = await db.execute(
            select(GroupMember).where(
                GroupMember.group_id == group_id,
                GroupMember.user_id == current_user.id
            )
        )
        member = member_result.scalar_one_or_none()
        
        if not member:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Access denied to private group"
            )
    
    return group


@router.post("/{group_id}/join", response_model=dict)
async def join_public_group(
    group_id: str,
    request: JoinGroupRequest,
    db: AsyncSession = Depends(get_db)
):
    """
    Join a public group
    
    Args:
        group_id: Group ID
        request: Join request with worker_id
        db: Database session
        
    Returns:
        Group information
        
    Raises:
        404: Group not found
        403: Group is private
        400: Already a member
    """
    logger.info(f"Worker {request.worker_id} joining group {group_id}")
    
    # Get group
    result = await db.execute(
        select(Group).where(Group.id == group_id)
    )
    group = result.scalar_one_or_none()
    
    if not group:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Group not found"
        )
    
    if not group.is_public:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Group is private. Use invitation to join."
        )
    
    # Check if already member (using worker_id as temporary user mapping)
    # TODO: Proper user-worker mapping
    member_result = await db.execute(
        select(GroupMember).where(
            GroupMember.group_id == group_id,
            GroupMember.worker_id == request.worker_id
        )
    )
    existing_member = member_result.scalar_one_or_none()
    
    if existing_member:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Already a member of this group"
        )
    
    # Add as member
    member = GroupMember(
        group_id=group_id,
        worker_id=request.worker_id,
        role="worker"
    )
    
    db.add(member)
    await db.commit()
    
    logger.info(f"Worker {request.worker_id} joined group {group_id}")
    
    return {
        "group_id": group_id,
        "group_name": group.name,
        "role": "worker",
        "joined_at": datetime.utcnow().isoformat()
    }


@router.get("/{group_id}/members", response_model=List[GroupMemberResponse])
async def list_group_members(
    group_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    List all members of a group
    
    Args:
        group_id: Group ID
        db: Database session
        current_user: Authenticated user
        
    Returns:
        List of group members
        
    Raises:
        404: Group not found
        403: Not a member
    """
    # Check membership
    member_result = await db.execute(
        select(GroupMember).where(
            GroupMember.group_id == group_id,
            GroupMember.user_id == current_user.id
        )
    )
    member = member_result.scalar_one_or_none()
    
    if not member:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not a member of this group"
        )
    
    # Get all members
    result = await db.execute(
        select(GroupMember).where(GroupMember.group_id == group_id)
    )
    members = result.scalars().all()
    
    logger.info(f"Retrieved {len(members)} members for group {group_id}")
    return members


@router.put("/{group_id}/members/{user_id}/role", response_model=GroupMemberResponse)
async def update_member_role(
    group_id: str,
    user_id: str,
    request: UpdateMemberRoleRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Update member role (owner/admin/member)
    
    Args:
        group_id: Group ID
        user_id: User ID to update
        request: New role
        db: Database session
        current_user: Authenticated user
        
    Returns:
        Updated member information
        
    Raises:
        403: Not authorized (only owner/admin)
        404: Member not found
    """
    # Check if current user is owner/admin
    current_member_result = await db.execute(
        select(GroupMember).where(
            GroupMember.group_id == group_id,
            GroupMember.user_id == current_user.id
        )
    )
    current_member = current_member_result.scalar_one_or_none()
    
    if not current_member or current_member.role not in ["owner", "admin"]:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only owners and admins can update roles"
        )
    
    # Get target member
    target_result = await db.execute(
        select(GroupMember).where(
            GroupMember.group_id == group_id,
            GroupMember.user_id == user_id
        )
    )
    target_member = target_result.scalar_one_or_none()
    
    if not target_member:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Member not found"
        )
    
    # Update role
    target_member.role = request.role
    await db.commit()
    await db.refresh(target_member)
    
    logger.info(f"Updated role for user {user_id} in group {group_id}")
    return target_member


@router.delete("/{group_id}/members/{user_id}", status_code=status.HTTP_204_NO_CONTENT)
async def remove_member(
    group_id: str,
    user_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Remove member from group
    
    Args:
        group_id: Group ID
        user_id: User ID to remove
        db: Database session
        current_user: Authenticated user
        
    Raises:
        403: Not authorized
        404: Member not found
        400: Cannot remove owner
    """
    # Check if current user is owner/admin or removing self
    current_member_result = await db.execute(
        select(GroupMember).where(
            GroupMember.group_id == group_id,
            GroupMember.user_id == current_user.id
        )
    )
    current_member = current_member_result.scalar_one_or_none()
    
    is_self = str(current_user.id) == user_id
    is_admin = current_member and current_member.role in ["owner", "admin"]
    
    if not is_self and not is_admin:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not authorized to remove members"
        )
    
    # Get target member
    target_result = await db.execute(
        select(GroupMember).where(
            GroupMember.group_id == group_id,
            GroupMember.user_id == user_id
        )
    )
    target_member = target_result.scalar_one_or_none()
    
    if not target_member:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Member not found"
        )
    
    if target_member.role == "owner":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cannot remove group owner"
        )
    
    await db.delete(target_member)
    await db.commit()
    
    logger.info(f"Removed user {user_id} from group {group_id}")
