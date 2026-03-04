"""
User repository with specific query methods.
"""
from typing import Optional, List
from sqlalchemy.orm import Session
from database.models.user import User
from .base import BaseRepository


class UserRepository(BaseRepository[User]):
    """Repository for User model."""
    
    def __init__(self, db: Session):
        super().__init__(User, db)
    
    def get_by_email(self, email: str) -> Optional[User]:
        """Get user by email address."""
        return self.get_by_field('email', email)
    
    def get_by_username(self, username: str) -> Optional[User]:
        """Get user by username."""
        return self.get_by_field('username', username)
    
    def email_exists(self, email: str) -> bool:
        """Check if email is already registered."""
        return self.exists(email=email)
    
    def username_exists(self, username: str) -> bool:
        """Check if username is already taken."""
        return self.exists(username=username)
    
    def get_active_users(self, limit: int = 100) -> List[User]:
        """Get all active users."""
        return self.get_all(
            filters={'is_active': True},
            limit=limit,
            order_by='created_at',
            descending=True
        )
    
    def get_verified_users(self, limit: int = 100) -> List[User]:
        """Get all verified users."""
        return self.get_all(
            filters={'is_active': True, 'is_verified': True},
            limit=limit
        )
    
    def activate_user(self, user_id: int) -> Optional[User]:
        """Activate a user account."""
        return self.update(user_id, is_active=True)
    
    def deactivate_user(self, user_id: int) -> Optional[User]:
        """Deactivate a user account."""
        return self.update(user_id, is_active=False)
    
    def verify_user(self, user_id: int) -> Optional[User]:
        """Mark user as verified."""
        return self.update(user_id, is_verified=True)
    
    def update_password(self, user_id: int, hashed_password: str) -> Optional[User]:
        """Update user password."""
        return self.update(user_id, hashed_password=hashed_password)
