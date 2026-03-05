# MeshML API Gateway - Changelog

All notable changes to the API Gateway service will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/).

---

## [Unreleased]

### TASK-3.2: Group Management Endpoints (2024-01-XX)

#### Added
- **Database Models** (SQLAlchemy ORM):
  - `User` model with authentication fields and relationships
  - `Group` model with settings and statistics
  - `GroupMember` model with role-based access control
  - `GroupInvitation` model with token-based invitations
  - `Job`, `Worker`, `Model` placeholder models
  - `TimestampMixin` for consistent created_at/updated_at fields
  - Enums: `GroupRole`, `InvitationStatus`, `MemberStatus`, `JobStatus`, `WorkerType`, `WorkerStatus`, `ModelStatus`, `ModelArchitecture`

- **Pydantic Schemas** (Request/Response Validation):
  - User schemas: `UserCreate`, `UserUpdate`, `UserResponse`, `UserPublicResponse`
  - Group schemas: `GroupCreate`, `GroupUpdate`, `GroupResponse`, `GroupDetailResponse`
  - Member schemas: `GroupMemberCreate`, `GroupMemberUpdateRole`, `GroupMemberResponse`
  - Invitation schemas: `InvitationCreate`, `InvitationResponse`, `InvitationAcceptRequest`
  - Pagination schemas: `GroupListResponse`, `MemberListResponse`, `InvitationListResponse`

- **CRUD Operations** (`app/crud/group.py`):
  - Group management: `create_group`, `get_group`, `get_user_groups`, `update_group`, `delete_group`
  - Member management: `get_group_member`, `get_group_members`, `add_group_member`, `update_member_role`, `remove_group_member`
  - Invitation management: `create_invitation`, `get_invitation_by_token`, `accept_invitation`, `decline_invitation`, `cancel_invitation`
  - Permission helpers: `check_member_permission`, `is_group_owner`

- **API Endpoints** (`app/api/v1/groups.py`):
  - `POST /api/v1/groups` - Create group
  - `GET /api/v1/groups` - List user's groups
  - `GET /api/v1/groups/{id}` - Get group details
  - `PATCH /api/v1/groups/{id}` - Update group
  - `DELETE /api/v1/groups/{id}` - Delete group
  - `GET /api/v1/groups/{id}/members` - List members
  - `PUT /api/v1/groups/{id}/members/{user_id}/role` - Update member role
  - `DELETE /api/v1/groups/{id}/members/{user_id}` - Remove member
  - `POST /api/v1/groups/{id}/invitations` - Send invitation
  - `GET /api/v1/groups/{id}/invitations` - List invitations
  - `POST /api/v1/groups/invitations/accept` - Accept invitation
  - `POST /api/v1/groups/invitations/{token}/decline` - Decline invitation
  - `DELETE /api/v1/invitations/{id}` - Cancel invitation

- **Tests** (`tests/test_groups.py`):
  - 14 comprehensive test cases covering groups, members, and invitations
  - Test fixtures: `db`, `client`, `test_user`, `test_group`
  - Authorization test placeholders (pending TASK-3.5)

- **Documentation**:
  - `docs/task-3.2-summary.md` - Complete implementation summary
  - `docs/api-groups-reference.md` - Quick reference guide

#### Features
- **Role-Based Access Control**: 3-tier hierarchy (OWNER > ADMIN > MEMBER)
- **Invitation System**: Token-based with 7-day expiry
- **Member Statistics**: Track compute contributions, jobs, workers
- **Group Settings**: Configurable max members, approval requirements, job limits
- **Soft Deletes**: Preserve historical data for groups and members
- **Pagination**: All list endpoints support skip/limit
- **Filtering**: Filter by status, include inactive groups

#### Security
- Cryptographically secure invitation tokens (`secrets.token_urlsafe`)
- Permission checks at API and CRUD layers
- SQL injection prevention (SQLAlchemy ORM)
- Input validation (Pydantic schemas)
- UUID primary keys (no sequential IDs)

---

## [0.1.0] - TASK-3.1: FastAPI Application Scaffold (2024-01-XX)

### Added
- **Application Setup**:
  - FastAPI application with lifespan management
  - CORS middleware configuration
  - Custom exception handlers
  - Environment-based configuration

- **Core Components**:
  - `app/config.py` - Configuration management
  - `app/dependencies.py` - Database and Redis dependency injection
  - `app/core/exceptions.py` - Custom exception hierarchy
  - `app/api/v1/system.py` - System health and metrics endpoints

- **Endpoints**:
  - `GET /` - API information
  - `GET /health` - Health check with database and Redis status
  - `GET /api/v1/system/metrics` - System resource metrics
  - `GET /api/v1/system/version` - API version information

- **Infrastructure**:
  - Docker support with health checks
  - Requirements.txt with 30+ dependencies
  - Pytest configuration and test infrastructure
  - Auto-generated OpenAPI documentation

- **Documentation**:
  - `README.md` - Comprehensive setup guide
  - `docs/task-3.1-summary.md` - Implementation summary

---

## Project Initialization

### Phase 0: Infrastructure Setup
- Project structure created
- Git repository initialized
- Development environment configured

### Phase 1: Database Layer (5/5 tasks)
- SQLAlchemy models and migrations
- 14/17 tests passing

### Phase 2: API Contracts (3/3 tasks)
- TASK-2.1: gRPC proto files
- TASK-2.2: OpenAPI REST contracts
- TASK-2.3: GraphQL schema

---

## Upcoming

### TASK-3.3: Job Management Endpoints
- Complete Job model implementation
- Job creation and monitoring endpoints
- Job status management
- Group-based job access control

### TASK-3.4: Worker Registration Endpoints
- Complete Worker model implementation
- Worker registration and heartbeat endpoints
- Worker health checks
- Job-worker assignment

### TASK-3.5: Authentication & Authorization
- JWT-based authentication
- User registration and login
- Password hashing
- Rate limiting
- Replace temporary auth mock

### TASK-3.6: Monitoring Endpoints
- Extended system metrics
- Performance tracking
- Prometheus metrics export
- Structured logging

---

## Notes

### Breaking Changes
None yet - initial implementation.

### Deprecated
- `get_current_user_temp()` - Temporary mock user function (will be removed in TASK-3.5)

### Known Issues
- Authentication is mocked (TASK-3.5 dependency)
- Email invitations not sent (requires SMTP integration)
- No rate limiting (pending TASK-3.5)
- Type warnings from SQLAlchemy (cosmetic, not functional)

---

## Contributors
- Development Team

## License
Proprietary - MeshML Project
