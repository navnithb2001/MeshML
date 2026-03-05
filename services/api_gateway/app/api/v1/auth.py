"""Authentication and user management API endpoints."""

from datetime import timedelta
from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.orm import Session

from app.core.exceptions import ConflictError, NotFoundError, AuthorizationError
from app.dependencies import get_db, get_current_user, get_current_superuser
from app.schemas.auth import (
    UserRegister,
    UserLogin,
    Token,
    TokenRefresh,
    WorkerToken,
    UserResponse,
    UserDetailResponse,
    PasswordChange,
)
from app.crud import auth as auth_crud
from app.core.security import (
    create_access_token,
    create_refresh_token,
    create_worker_token,
    decode_token,
)
from app.models.user import User
from app.config import settings


router = APIRouter(prefix="/auth", tags=["authentication"])


# ============================================================================
# Registration & Login Endpoints
# ============================================================================

@router.post(
    "/register",
    response_model=UserResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Register new user",
    description="Create a new user account. Email verification required before full access.",
)
async def register(
    user_data: UserRegister,
    db: Session = Depends(get_db),
):
    """Register a new user."""
    # Check if email already exists
    existing_user = auth_crud.get_user_by_email(db, user_data.email)
    if existing_user:
        raise ConflictError(f"Email {user_data.email} is already registered")
    
    # Check if username already exists
    existing_username = auth_crud.get_user_by_username(db, user_data.username)
    if existing_username:
        raise ConflictError(f"Username {user_data.username} is already taken")
    
    # Create user
    user = auth_crud.create_user(db, user_data)
    
    # TODO: Send verification email
    
    return user


@router.post(
    "/login",
    response_model=Token,
    summary="Login user",
    description="Authenticate and receive JWT tokens.",
)
async def login(
    form_data: OAuth2PasswordRequestForm = Depends(),
    db: Session = Depends(get_db),
):
    """Login with email/password and get JWT tokens."""
    # Authenticate user (form_data.username can be email)
    user = auth_crud.authenticate_user(db, form_data.username, form_data.password)
    
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect email or password",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    # Create access and refresh tokens
    access_token = create_access_token(data={"sub": user.id})
    refresh_token = create_refresh_token(data={"sub": user.id})
    
    return Token(
        access_token=access_token,
        refresh_token=refresh_token,
        token_type="bearer",
        expires_in=settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60,
    )


@router.post(
    "/refresh",
    response_model=Token,
    summary="Refresh access token",
    description="Get a new access token using a refresh token.",
)
async def refresh_token(
    token_data: TokenRefresh,
    db: Session = Depends(get_db),
):
    """Refresh access token using refresh token."""
    try:
        payload = decode_token(token_data.refresh_token)
        user_id: str = payload.get("sub")
        token_type: str = payload.get("type")
        
        if user_id is None or token_type != "refresh":
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid refresh token",
                headers={"WWW-Authenticate": "Bearer"},
            )
            
    except Exception:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid refresh token",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    # Verify user exists
    user = auth_crud.get_user_by_id(db, user_id)
    if not user or not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not found or inactive",
        )
    
    # Create new tokens
    access_token = create_access_token(data={"sub": user.id})
    new_refresh_token = create_refresh_token(data={"sub": user.id})
    
    return Token(
        access_token=access_token,
        refresh_token=new_refresh_token,
        token_type="bearer",
        expires_in=settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60,
    )


# ============================================================================
# User Profile Endpoints
# ============================================================================

@router.get(
    "/me",
    response_model=UserDetailResponse,
    summary="Get current user",
    description="Get profile of currently authenticated user.",
)
async def get_current_user_profile(
    current_user: User = Depends(get_current_user),
):
    """Get current user profile."""
    return current_user


@router.post(
    "/me/change-password",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Change password",
    description="Change current user's password.",
)
async def change_password(
    password_data: PasswordChange,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Change user password."""
    success = auth_crud.update_user_password(db, current_user, password_data)
    
    if not success:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Current password is incorrect",
        )
    
    return None


@router.delete(
    "/me",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete account",
    description="Delete current user's account (irreversible).",
)
async def delete_account(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Delete user account."""
    auth_crud.delete_user(db, current_user)
    return None


# ============================================================================
# Worker Token Endpoint
# ============================================================================

@router.post(
    "/worker-token",
    response_model=WorkerToken,
    summary="Generate worker token",
    description="Generate a long-lived JWT token for worker authentication.",
)
async def generate_worker_token(
    worker_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Generate a worker authentication token.
    
    Workers use this long-lived token (1 year) for API access.
    """
    # TODO: Verify worker belongs to user
    from app.crud import worker as worker_crud
    
    worker = worker_crud.get_worker(db, worker_id)
    if not worker:
        raise NotFoundError(f"Worker {worker_id} not found")
    
    if worker.user_id != current_user.id:
        raise AuthorizationError("You don't own this worker")
    
    token = create_worker_token(worker_id, current_user.id)
    
    return WorkerToken(
        worker_token=token,
        worker_id=worker_id,
        expires_in=365 * 24 * 60 * 60,  # 1 year in seconds
    )


# ============================================================================
# Admin Endpoints
# ============================================================================

@router.get(
    "/users/{user_id}",
    response_model=UserDetailResponse,
    summary="Get user by ID (admin)",
    description="Admin endpoint to get any user's profile.",
)
async def get_user_by_id(
    user_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_superuser),
):
    """Get user by ID (admin only)."""
    user = auth_crud.get_user_by_id(db, user_id)
    
    if not user:
        raise NotFoundError(f"User {user_id} not found")
    
    return user


@router.post(
    "/users/{user_id}/deactivate",
    response_model=UserDetailResponse,
    summary="Deactivate user (admin)",
    description="Admin endpoint to deactivate a user account.",
)
async def deactivate_user(
    user_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_superuser),
):
    """Deactivate user account (admin only)."""
    user = auth_crud.get_user_by_id(db, user_id)
    
    if not user:
        raise NotFoundError(f"User {user_id} not found")
    
    auth_crud.deactivate_user(db, user)
    db.refresh(user)
    
    return user


@router.post(
    "/users/{user_id}/activate",
    response_model=UserDetailResponse,
    summary="Activate user (admin)",
    description="Admin endpoint to activate a user account.",
)
async def activate_user(
    user_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_superuser),
):
    """Activate user account (admin only)."""
    user = auth_crud.get_user_by_id(db, user_id)
    
    if not user:
        raise NotFoundError(f"User {user_id} not found")
    
    auth_crud.activate_user(db, user)
    db.refresh(user)
    
    return user
