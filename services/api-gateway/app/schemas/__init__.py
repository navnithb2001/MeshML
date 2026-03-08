"""Pydantic schemas package"""

from .auth import (
    UserRegisterRequest,
    UserLoginRequest,
    UserResponse,
    TokenResponse
)
from .group import (
    GroupCreateRequest,
    GroupResponse,
    GroupMemberResponse,
    JoinGroupRequest,
    UpdateMemberRoleRequest
)
from .invitation import (
    CreateInvitationRequest,
    InvitationResponse,
    AcceptInvitationRequest
)
from .worker import (
    WorkerRegisterRequest,
    WorkerResponse,
    WorkerUpdateCapabilitiesRequest
)
from .job import (
    JobCreateRequest,
    JobResponse,
    JobProgressResponse
)

__all__ = [
    # Auth
    "UserRegisterRequest",
    "UserLoginRequest",
    "UserResponse",
    "TokenResponse",
    # Group
    "GroupCreateRequest",
    "GroupResponse",
    "GroupMemberResponse",
    "JoinGroupRequest",
    "UpdateMemberRoleRequest",
    # Invitation
    "CreateInvitationRequest",
    "InvitationResponse",
    "AcceptInvitationRequest",
    # Worker
    "WorkerRegisterRequest",
    "WorkerResponse",
    "WorkerUpdateCapabilitiesRequest",
    # Job
    "JobCreateRequest",
    "JobResponse",
    "JobProgressResponse",
]
