"""User CRUD operations for authentication."""

from typing import Optional
from sqlalchemy.orm import Session
from sqlalchemy import or_

from app.models.user import User
from app.schemas.auth import UserRegister, PasswordChange
from app.core.security import get_password_hash, verify_password


def create_user(db: Session, user_data: UserRegister) -> User:
    """
    Create a new user with hashed password.
    
    Args:
        db: Database session
        user_data: User registration data
        
    Returns:
        Created user
    """
    hashed_password = get_password_hash(user_data.password)
    
    user = User(
        email=user_data.email,
        username=user_data.username,
        full_name=user_data.full_name,
        password_hash=hashed_password,
        is_active=True,
        is_verified=False,  # Requires email verification
        is_superuser=False,
    )
    
    db.add(user)
    db.commit()
    db.refresh(user)
    
    return user


def get_user_by_id(db: Session, user_id: str) -> Optional[User]:
    """
    Get user by ID.
    
    Args:
        db: Database session
        user_id: User ID
        
    Returns:
        User if found, None otherwise
    """
    return db.query(User).filter(User.id == user_id).first()


def get_user_by_email(db: Session, email: str) -> Optional[User]:
    """
    Get user by email address.
    
    Args:
        db: Database session
        email: Email address
        
    Returns:
        User if found, None otherwise
    """
    return db.query(User).filter(User.email == email).first()


def get_user_by_username(db: Session, username: str) -> Optional[User]:
    """
    Get user by username.
    
    Args:
        db: Database session
        username: Username
        
    Returns:
        User if found, None otherwise
    """
    return db.query(User).filter(User.username == username).first()


def get_user_by_email_or_username(db: Session, identifier: str) -> Optional[User]:
    """
    Get user by email or username.
    
    Args:
        db: Database session
        identifier: Email or username
        
    Returns:
        User if found, None otherwise
    """
    return db.query(User).filter(
        or_(User.email == identifier, User.username == identifier)
    ).first()


def authenticate_user(db: Session, email: str, password: str) -> Optional[User]:
    """
    Authenticate a user with email and password.
    
    Args:
        db: Database session
        email: User email
        password: Plain text password
        
    Returns:
        User if authentication successful, None otherwise
    """
    user = get_user_by_email(db, email)
    
    if not user:
        return None
    
    if not verify_password(password, user.password_hash):
        return None
    
    if not user.is_active:
        return None
    
    return user


def update_user_password(
    db: Session,
    user: User,
    password_change: PasswordChange
) -> bool:
    """
    Update user password after verifying current password.
    
    Args:
        db: Database session
        user: User object
        password_change: Password change data
        
    Returns:
        True if successful, False otherwise
    """
    # Verify current password
    if not verify_password(password_change.current_password, user.password_hash):
        return False
    
    # Update password
    user.password_hash = get_password_hash(password_change.new_password)
    db.commit()
    
    return True


def reset_user_password(db: Session, user: User, new_password: str) -> None:
    """
    Reset user password (for password reset flow).
    
    Args:
        db: Database session
        user: User object
        new_password: New plain text password
    """
    user.password_hash = get_password_hash(new_password)
    db.commit()


def verify_user_email(db: Session, user: User) -> None:
    """
    Mark user email as verified.
    
    Args:
        db: Database session
        user: User object
    """
    user.is_verified = True
    db.commit()


def update_user_profile(db: Session, user: User, **kwargs) -> User:
    """
    Update user profile fields.
    
    Args:
        db: Database session
        user: User object
        **kwargs: Fields to update
        
    Returns:
        Updated user
    """
    for key, value in kwargs.items():
        if hasattr(user, key) and value is not None:
            setattr(user, key, value)
    
    db.commit()
    db.refresh(user)
    
    return user


def deactivate_user(db: Session, user: User) -> None:
    """
    Deactivate a user account.
    
    Args:
        db: Database session
        user: User object
    """
    user.is_active = False
    db.commit()


def activate_user(db: Session, user: User) -> None:
    """
    Activate a user account.
    
    Args:
        db: Database session
        user: User object
    """
    user.is_active = True
    db.commit()


def delete_user(db: Session, user: User) -> None:
    """
    Permanently delete a user.
    
    Args:
        db: Database session
        user: User object
    """
    db.delete(user)
    db.commit()
