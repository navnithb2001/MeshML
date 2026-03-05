"""User authentication schemas."""

from typing import Optional
from pydantic import BaseModel, EmailStr, Field, validator


# ============================================================================
# User Registration & Authentication Schemas
# ============================================================================

class UserRegister(BaseModel):
    """Schema for user registration."""
    
    email: EmailStr = Field(..., description="User email address")
    username: str = Field(..., min_length=3, max_length=50, description="Unique username")
    password: str = Field(..., min_length=8, max_length=100, description="Password (min 8 characters)")
    full_name: Optional[str] = Field(None, max_length=255, description="User's full name")
    
    @validator("username")
    def username_alphanumeric(cls, v):
        """Validate username is alphanumeric with underscores/dashes."""
        if not v.replace("_", "").replace("-", "").isalnum():
            raise ValueError("Username must be alphanumeric (underscores and dashes allowed)")
        return v
    
    @validator("password")
    def password_strength(cls, v):
        """Validate password strength."""
        if len(v) < 8:
            raise ValueError("Password must be at least 8 characters")
        if not any(c.isupper() for c in v):
            raise ValueError("Password must contain at least one uppercase letter")
        if not any(c.islower() for c in v):
            raise ValueError("Password must contain at least one lowercase letter")
        if not any(c.isdigit() for c in v):
            raise ValueError("Password must contain at least one digit")
        return v


class UserLogin(BaseModel):
    """Schema for user login."""
    
    email: EmailStr = Field(..., description="User email address")
    password: str = Field(..., description="User password")


class Token(BaseModel):
    """Schema for JWT token response."""
    
    access_token: str = Field(..., description="JWT access token")
    refresh_token: str = Field(..., description="JWT refresh token")
    token_type: str = Field(default="bearer", description="Token type")
    expires_in: int = Field(..., description="Token expiration in seconds")


class TokenRefresh(BaseModel):
    """Schema for token refresh request."""
    
    refresh_token: str = Field(..., description="Refresh token")


class WorkerToken(BaseModel):
    """Schema for worker authentication token."""
    
    worker_token: str = Field(..., description="Long-lived JWT token for worker")
    worker_id: str = Field(..., description="Worker ID")
    expires_in: int = Field(..., description="Token expiration in seconds")


# ============================================================================
# User Profile Schemas
# ============================================================================

class UserBase(BaseModel):
    """Base user schema with common fields."""
    
    email: EmailStr
    username: str
    full_name: Optional[str] = None
    bio: Optional[str] = None
    avatar_url: Optional[str] = None


class UserResponse(UserBase):
    """User response schema (public profile)."""
    
    id: str
    is_active: bool
    is_verified: bool
    total_compute_contributed: int
    created_at: str
    
    class Config:
        from_attributes = True


class UserDetailResponse(UserResponse):
    """Detailed user response (includes private info)."""
    
    is_superuser: bool
    updated_at: str
    
    class Config:
        from_attributes = True


class UserUpdate(BaseModel):
    """Schema for updating user profile."""
    
    full_name: Optional[str] = Field(None, max_length=255)
    bio: Optional[str] = Field(None, max_length=1000)
    avatar_url: Optional[str] = Field(None, max_length=512)


class PasswordChange(BaseModel):
    """Schema for password change."""
    
    current_password: str = Field(..., description="Current password")
    new_password: str = Field(..., min_length=8, max_length=100, description="New password")
    
    @validator("new_password")
    def password_strength(cls, v):
        """Validate password strength."""
        if len(v) < 8:
            raise ValueError("Password must be at least 8 characters")
        if not any(c.isupper() for c in v):
            raise ValueError("Password must contain at least one uppercase letter")
        if not any(c.islower() for c in v):
            raise ValueError("Password must contain at least one lowercase letter")
        if not any(c.isdigit() for c in v):
            raise ValueError("Password must contain at least one digit")
        return v


class EmailVerification(BaseModel):
    """Schema for email verification."""
    
    token: str = Field(..., description="Verification token")


class PasswordResetRequest(BaseModel):
    """Schema for password reset request."""
    
    email: EmailStr = Field(..., description="User email address")


class PasswordReset(BaseModel):
    """Schema for password reset."""
    
    token: str = Field(..., description="Reset token")
    new_password: str = Field(..., min_length=8, max_length=100, description="New password")
    
    @validator("new_password")
    def password_strength(cls, v):
        """Validate password strength."""
        if len(v) < 8:
            raise ValueError("Password must be at least 8 characters")
        if not any(c.isupper() for c in v):
            raise ValueError("Password must contain at least one uppercase letter")
        if not any(c.islower() for c in v):
            raise ValueError("Password must contain at least one lowercase letter")
        if not any(c.isdigit() for c in v):
            raise ValueError("Password must contain at least one digit")
        return v
