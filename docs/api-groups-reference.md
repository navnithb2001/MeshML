# Group Management API - Quick Reference

## Authentication
All endpoints require authentication (except invitation decline).  
**Header**: `Authorization: Bearer <jwt_token>` (to be implemented in TASK-3.5)

---

## Group Endpoints

### Create Group
```http
POST /api/v1/groups
Content-Type: application/json

{
  "name": "ML Research Lab",
  "description": "Collaborative ML research group",
  "settings": {
    "max_members": 100,
    "require_approval": false,
    "compute_sharing_enabled": true,
    "allow_public_join": false,
    "max_concurrent_jobs": 10
  }
}
```

**Response** (201 Created):
```json
{
  "id": "uuid",
  "name": "ML Research Lab",
  "description": "Collaborative ML research group",
  "owner_id": "uuid",
  "is_active": true,
  "settings": { ... },
  "statistics": { ... },
  "created_at": "2024-01-01T00:00:00Z",
  "updated_at": "2024-01-01T00:00:00Z"
}
```

---

### List Groups
```http
GET /api/v1/groups?skip=0&limit=10&include_inactive=false
```

**Response** (200 OK):
```json
{
  "groups": [...],
  "total": 5,
  "page": 1,
  "page_size": 10
}
```

---

### Get Group Details
```http
GET /api/v1/groups/{group_id}
```

**Response** (200 OK):
```json
{
  "id": "uuid",
  "name": "ML Research Lab",
  "description": "...",
  "owner_id": "uuid",
  "owner": {
    "id": "uuid",
    "username": "professor",
    "full_name": "Dr. Jane Smith",
    ...
  },
  "member_count": 15,
  "is_active": true,
  "settings": { ... },
  "statistics": { ... },
  "created_at": "...",
  "updated_at": "..."
}
```

---

### Update Group
```http
PATCH /api/v1/groups/{group_id}
Content-Type: application/json

{
  "name": "Updated Name",
  "description": "Updated description",
  "settings": {
    "max_members": 50
  }
}
```

**Permissions**: Admin or Owner  
**Response** (200 OK): Updated group object

---

### Delete Group
```http
DELETE /api/v1/groups/{group_id}
```

**Permissions**: Owner only  
**Response** (204 No Content)

---

## Member Endpoints

### List Members
```http
GET /api/v1/groups/{group_id}/members?skip=0&limit=100&status=ACTIVE
```

**Status Filter**: `ACTIVE`, `SUSPENDED`, `LEFT` (optional)

**Response** (200 OK):
```json
{
  "members": [
    {
      "id": "uuid",
      "group_id": "uuid",
      "user_id": "uuid",
      "role": "OWNER",
      "status": "ACTIVE",
      "statistics": {
        "compute_contributed": 3600,
        "jobs_created": 10,
        "workers_registered": 2
      },
      "joined_at": "...",
      "last_active_at": "...",
      "user": {
        "id": "uuid",
        "username": "professor",
        "full_name": "Dr. Jane Smith",
        ...
      }
    }
  ],
  "total": 15,
  "page": 1,
  "page_size": 100
}
```

---

### Update Member Role
```http
PUT /api/v1/groups/{group_id}/members/{user_id}/role
Content-Type: application/json

{
  "role": "ADMIN"
}
```

**Roles**: `MEMBER`, `ADMIN` (cannot assign `OWNER`)  
**Permissions**: Admin or Owner  
**Response** (200 OK): Updated member object

---

### Remove Member
```http
DELETE /api/v1/groups/{group_id}/members/{user_id}
```

**Permissions**: 
- Admins can remove anyone (except owner)
- Members can remove themselves

**Response** (204 No Content)

---

## Invitation Endpoints

### Send Invitation
```http
POST /api/v1/groups/{group_id}/invitations
Content-Type: application/json

{
  "invitee_email": "student@university.edu",
  "role": "MEMBER"
}
```

**Permissions**: Admin or Owner  
**Response** (201 Created):
```json
{
  "id": "uuid",
  "group_id": "uuid",
  "inviter_id": "uuid",
  "invitee_email": "student@university.edu",
  "role": "MEMBER",
  "status": "PENDING",
  "token": "abc123...",
  "expires_at": "2024-01-08T00:00:00Z",
  "accepted_at": null,
  "created_at": "2024-01-01T00:00:00Z"
}
```

---

### List Invitations
```http
GET /api/v1/groups/{group_id}/invitations?skip=0&limit=100&status=PENDING
```

**Status Filter**: `PENDING`, `ACCEPTED`, `DECLINED`, `EXPIRED`, `CANCELLED`  
**Permissions**: Admin or Owner  
**Response** (200 OK): Paginated invitation list

---

### Accept Invitation
```http
POST /api/v1/groups/invitations/accept
Content-Type: application/json

{
  "token": "abc123..."
}
```

**Response** (200 OK): Member object

---

### Decline Invitation
```http
POST /api/v1/groups/invitations/{token}/decline
```

**Response** (204 No Content)

---

### Cancel Invitation
```http
DELETE /api/v1/invitations/{invitation_id}
```

**Permissions**: Admin, Owner, or Inviter  
**Response** (204 No Content)

---

## Error Responses

### 400 Bad Request
```json
{
  "error": "Validation error",
  "details": "Invalid role: SUPER_ADMIN"
}
```

### 401 Unauthorized
```json
{
  "error": "Authentication required",
  "details": "Missing or invalid token"
}
```

### 403 Forbidden
```json
{
  "error": "Authorization error",
  "details": "Only admins can update group settings"
}
```

### 404 Not Found
```json
{
  "error": "Resource not found",
  "details": "Group uuid not found"
}
```

### 409 Conflict
```json
{
  "error": "Conflict",
  "details": "User is already a member"
}
```

---

## Role Hierarchy

```
OWNER (Level 3)
  ├─ Full control over group
  ├─ Can delete group
  ├─ Can assign/remove admins
  ├─ Can update all settings
  └─ Cannot be removed

ADMIN (Level 2)
  ├─ Manage members (add/remove/update roles)
  ├─ Send invitations
  ├─ Update group settings
  └─ Cannot change owner role or delete group

MEMBER (Level 1)
  ├─ View group information
  ├─ View member list
  ├─ Contribute compute resources
  └─ Limited to read-only operations
```

---

## Invitation Workflow

1. **Admin sends invitation**  
   → POST `/api/v1/groups/{id}/invitations`

2. **System generates secure token**  
   → 32-character URL-safe random string  
   → 7-day expiry (configurable)

3. **Email sent to invitee** (TODO)  
   → Link: `https://meshml.app/invitations/{token}`

4. **Invitee accepts**  
   → POST `/api/v1/groups/invitations/accept` with token  
   → Membership created with specified role  
   → Invitation status → ACCEPTED

5. **Invitee declines**  
   → POST `/api/v1/groups/invitations/{token}/decline`  
   → Invitation status → DECLINED

6. **Admin cancels**  
   → DELETE `/api/v1/invitations/{id}`  
   → Invitation status → CANCELLED

7. **Token expires**  
   → Automatic after 7 days  
   → Invitation status → EXPIRED

---

## Pagination

All list endpoints support pagination:

**Query Parameters**:
- `skip`: Number of records to skip (default: 0)
- `limit`: Maximum records to return (default: 100, max: 500)

**Response Format**:
```json
{
  "items": [...],
  "total": 150,
  "page": 2,
  "page_size": 100
}
```

**Example**:
```http
GET /api/v1/groups?skip=0&limit=10   # First page (1-10)
GET /api/v1/groups?skip=10&limit=10  # Second page (11-20)
GET /api/v1/groups?skip=20&limit=10  # Third page (21-30)
```

---

## Filtering

### Members by Status
```http
GET /api/v1/groups/{id}/members?status=ACTIVE
GET /api/v1/groups/{id}/members?status=SUSPENDED
```

### Invitations by Status
```http
GET /api/v1/groups/{id}/invitations?status=PENDING
GET /api/v1/groups/{id}/invitations?status=ACCEPTED
```

### Groups (Include Inactive)
```http
GET /api/v1/groups?include_inactive=true
```

---

## Statistics

### Group Statistics
Tracked automatically:
- `total_compute_hours`: Sum of all member contributions
- `total_jobs_completed`: Number of completed jobs

### Member Statistics
Tracked per member:
- `compute_contributed`: Total compute time (seconds)
- `jobs_created`: Number of jobs created
- `workers_registered`: Number of workers registered
- `last_active_at`: Last activity timestamp

**Example**:
```json
{
  "statistics": {
    "compute_contributed": 7200,
    "jobs_created": 5,
    "workers_registered": 2
  }
}
```

---

## Best Practices

### Group Creation
- Choose descriptive names
- Set appropriate `max_members` limit
- Enable `require_approval` for sensitive groups
- Use `allow_public_join` for open communities

### Member Management
- Assign `ADMIN` role to trusted members
- Regularly review member list
- Remove inactive members
- Monitor `last_active_at` timestamps

### Invitations
- Use short expiry for sensitive groups
- Track invitation status
- Cancel unused invitations
- Limit invitation sends (rate limiting - TODO)

### Permissions
- Principle of least privilege
- Regular role audits
- Protect owner role
- Use ADMIN for delegation

---

## Rate Limits (TODO - TASK-3.5)

Planned rate limits:
- Invitation sends: 10/hour per user
- Group creation: 5/hour per user
- Member updates: 20/minute per user

---

## Webhooks (TODO - Future)

Planned webhook events:
- `group.created`
- `group.updated`
- `group.deleted`
- `member.added`
- `member.removed`
- `member.role_updated`
- `invitation.sent`
- `invitation.accepted`
- `invitation.declined`

---

## Interactive Documentation

**Swagger UI**: http://localhost:8000/docs  
**ReDoc**: http://localhost:8000/redoc  
**OpenAPI Spec**: http://localhost:8000/openapi.json
