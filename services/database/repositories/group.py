"""
Group repository with specific query methods.
"""
from typing import Optional, List
from sqlalchemy.orm import Session
from services.database.models.group import Group, GroupMember, GroupInvitation, GroupRole, InvitationStatus
from services.database.models.user import User
from .base import BaseRepository


class GroupRepository(BaseRepository[Group]):
    """Repository for Group model."""
    
    def __init__(self, db: Session):
        super().__init__(Group, db)
    
    def get_by_owner(self, owner_id: int) -> List[Group]:
        """Get all groups owned by a user."""
        return self.get_all(filters={'owner_id': owner_id, 'is_active': True})
    
    def get_user_groups(self, user_id: int) -> List[Group]:
        """
        Get all groups where user is a member.
        
        Args:
            user_id: User identifier
            
        Returns:
            List of groups user belongs to
        """
        # Query through group_members relationship
        members = self.db.query(GroupMember).filter(
            GroupMember.user_id == user_id
        ).all()
        
        group_ids = [m.group_id for m in members]
        return self.db.query(Group).filter(
            Group.id.in_(group_ids),
            Group.is_active == True
        ).all()
    
    def deactivate_group(self, group_id: int) -> Optional[Group]:
        """Deactivate a group."""
        return self.update(group_id, is_active=False)


class GroupMemberRepository(BaseRepository[GroupMember]):
    """Repository for GroupMember model."""
    
    def __init__(self, db: Session):
        super().__init__(GroupMember, db)
    
    def get_group_members(self, group_id: int) -> List[GroupMember]:
        """Get all members of a group."""
        return self.get_all(filters={'group_id': group_id})
    
    def get_user_memberships(self, user_id: int) -> List[GroupMember]:
        """Get all group memberships for a user."""
        return self.get_all(filters={'user_id': user_id})
    
    def get_member_role(self, group_id: int, user_id: int) -> Optional[GroupRole]:
        """
        Get user's role in a group.
        
        Args:
            group_id: Group identifier
            user_id: User identifier
            
        Returns:
            GroupRole or None if not a member
        """
        member = self.db.query(GroupMember).filter(
            GroupMember.group_id == group_id,
            GroupMember.user_id == user_id
        ).first()
        return member.role if member else None
    
    def is_member(self, group_id: int, user_id: int) -> bool:
        """Check if user is a member of group."""
        return self.exists(group_id=group_id, user_id=user_id)
    
    def is_owner(self, group_id: int, user_id: int) -> bool:
        """Check if user is owner of group."""
        member = self.db.query(GroupMember).filter(
            GroupMember.group_id == group_id,
            GroupMember.user_id == user_id,
            GroupMember.role == GroupRole.OWNER
        ).first()
        return member is not None
    
    def is_admin(self, group_id: int, user_id: int) -> bool:
        """Check if user is admin or owner of group."""
        member = self.db.query(GroupMember).filter(
            GroupMember.group_id == group_id,
            GroupMember.user_id == user_id,
            GroupMember.role.in_([GroupRole.OWNER, GroupRole.ADMIN])
        ).first()
        return member is not None
    
    def add_member(
        self,
        group_id: int,
        user_id: int,
        role: GroupRole = GroupRole.MEMBER
    ) -> GroupMember:
        """Add a user to a group."""
        return self.create(group_id=group_id, user_id=user_id, role=role)
    
    def update_role(
        self,
        group_id: int,
        user_id: int,
        new_role: GroupRole
    ) -> Optional[GroupMember]:
        """Update member's role in group."""
        member = self.db.query(GroupMember).filter(
            GroupMember.group_id == group_id,
            GroupMember.user_id == user_id
        ).first()
        
        if member:
            member.role = new_role
            self.db.flush()
            self.db.refresh(member)
        return member
    
    def remove_member(self, group_id: int, user_id: int) -> bool:
        """Remove a user from a group."""
        member = self.db.query(GroupMember).filter(
            GroupMember.group_id == group_id,
            GroupMember.user_id == user_id
        ).first()
        
        if member:
            self.db.delete(member)
            self.db.flush()
            return True
        return False


class GroupInvitationRepository(BaseRepository[GroupInvitation]):
    """Repository for GroupInvitation model."""
    
    def __init__(self, db: Session):
        super().__init__(GroupInvitation, db)
    
    def get_by_token(self, token: str) -> Optional[GroupInvitation]:
        """Get invitation by token."""
        return self.get_by_field('token', token)
    
    def get_pending_invitations(self, group_id: int) -> List[GroupInvitation]:
        """Get all pending invitations for a group."""
        return self.get_all(filters={
            'group_id': group_id,
            'status': InvitationStatus.PENDING
        })
    
    def get_user_invitations(self, email: str) -> List[GroupInvitation]:
        """Get all pending invitations for an email."""
        return self.get_all(filters={
            'email': email,
            'status': InvitationStatus.PENDING
        })
    
    def accept_invitation(self, invitation_id: int) -> Optional[GroupInvitation]:
        """Mark invitation as accepted."""
        return self.update(invitation_id, status=InvitationStatus.ACCEPTED)
    
    def reject_invitation(self, invitation_id: int) -> Optional[GroupInvitation]:
        """Mark invitation as rejected."""
        return self.update(invitation_id, status=InvitationStatus.REJECTED)
    
    def expire_invitation(self, invitation_id: int) -> Optional[GroupInvitation]:
        """Mark invitation as expired."""
        return self.update(invitation_id, status=InvitationStatus.EXPIRED)
    
    def expire_old_invitations(self) -> int:
        """
        Expire all invitations past their expiry date.
        
        Returns:
            Number of expired invitations
        """
        from datetime import datetime
        
        count = self.db.query(GroupInvitation).filter(
            GroupInvitation.status == InvitationStatus.PENDING,
            GroupInvitation.expires_at < datetime.utcnow()
        ).update({'status': InvitationStatus.EXPIRED})
        
        self.db.flush()
        return count
