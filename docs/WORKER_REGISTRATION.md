# Worker Registration and Group Joining

## Overview

Workers in MeshML need to:
1. **Register** with the Leader service
2. **Join a training group** to receive work assignments
3. **Request jobs** from the Orchestrator

This document explains how workers discover and join groups.

## Registration Flow

```
┌──────────┐      ┌─────────┐      ┌────────────┐      ┌──────────────┐
│  Worker  │─────▶│  Leader │─────▶│ Invitation │─────▶│ Training     │
│          │      │ Service │      │  System    │      │ Group        │
└──────────┘      └─────────┘      └────────────┘      └──────────────┘
     │                                                          │
     └──────────────────────────────────────────────────────────┘
              Worker receives job assignments
```

## How Workers Join Groups

### Method 1: Invitation Code (Recommended)

**For Private Groups:**

1. Group owner creates invitation via API Gateway:
   ```bash
   curl -X POST http://localhost:8000/api/groups/{group_id}/invitations \
     -H "Authorization: Bearer $TOKEN" \
     -d '{"max_uses": 10, "expires_in_hours": 24}'
   ```

2. Owner shares invitation code with worker operator

3. Worker accepts invitation during installation:
   ```bash
   ./install.sh
   # ... during interactive setup ...
   # Choose option 1: Enter invitation code
   # Paste: inv_abc123xyz789
   ```

4. Worker is automatically assigned to the group

**Programmatic:**
```python
from meshml_worker.registration import WorkerRegistration

registration = WorkerRegistration(config)
registration.register_worker()
registration.join_group_by_invitation("inv_abc123xyz789")
```

### Method 2: Public Groups

**For Open Groups:**

1. Worker discovers public groups:
   ```bash
   meshml-worker discover-groups
   ```

2. Output shows available groups:
   ```
   Available Public Groups:
   1. ImageNet Training - 47 workers, GPU recommended
   2. NLP Research - 12 workers, CPU ok
   3. Testing Group - 3 workers, All devices
   ```

3. Worker joins by ID:
   ```bash
   meshml-worker join-group group_abc123
   ```

**Programmatic:**
```python
registration = WorkerRegistration(config)
registration.register_worker()

# Discover groups
groups = registration.discover_public_groups()
for group in groups:
    print(f"{group['name']}: {group['description']}")

# Join specific group
registration.join_public_group(group_id="group_abc123")
```

### Method 3: Auto-Assignment (Future)

Workers can opt into automatic assignment based on capabilities:

```yaml
# config.yaml
worker:
  auto_join:
    enabled: true
    preferences:
      - type: "image_classification"
      - min_workers: 10
      - device: "gpu"
```

The Orchestrator matches workers to groups based on:
- Worker capabilities (GPU/CPU, RAM, bandwidth)
- Group requirements (minimum workers, device type)
- Current workload distribution

## Registration API

### Worker Registration

**Endpoint:** `POST /api/workers/register`

**Request:**
```json
{
  "worker_id": "worker_abc123",
  "user_email": "user@example.com",
  "capabilities": {
    "device": "cuda",
    "gpu_name": "NVIDIA RTX 3080",
    "gpu_memory_gb": 10.0,
    "cpu_cores": 8,
    "ram_gb": 32.0
  },
  "status": "idle"
}
```

**Response:**
```json
{
  "worker_id": "worker_abc123",
  "auth_token": "eyJ0eXAiOiJKV1QiLCJhbGc...",
  "registered_at": "2024-01-15T10:30:00Z"
}
```

### Accept Invitation

**Endpoint:** `POST /api/invitations/accept`

**Request:**
```json
{
  "worker_id": "worker_abc123",
  "invitation_code": "inv_abc123xyz789"
}
```

**Response:**
```json
{
  "group_id": "group_abc123",
  "group_name": "ImageNet Training",
  "role": "worker",
  "joined_at": "2024-01-15T10:31:00Z"
}
```

### Discover Public Groups

**Endpoint:** `GET /api/groups/public`

**Response:**
```json
{
  "groups": [
    {
      "id": "group_abc123",
      "name": "ImageNet Training",
      "description": "Open ImageNet training group",
      "worker_count": 47,
      "requirements": {
        "device": "gpu",
        "min_gpu_memory_gb": 8.0
      },
      "created_at": "2024-01-01T00:00:00Z"
    }
  ]
}
```

### Join Public Group

**Endpoint:** `POST /api/groups/{group_id}/join`

**Request:**
```json
{
  "worker_id": "worker_abc123"
}
```

**Response:**
```json
{
  "group_id": "group_abc123",
  "group_name": "ImageNet Training",
  "role": "worker",
  "joined_at": "2024-01-15T10:32:00Z"
}
```

## CLI Commands

### Register Worker
```bash
meshml-worker register
```

Interactive registration with capability detection.

### Join Group (Invitation)
```bash
meshml-worker join --invitation inv_abc123xyz789
```

### Discover Groups
```bash
meshml-worker discover-groups
```

Shows public groups with descriptions and requirements.

### Join Public Group
```bash
meshml-worker join-group group_abc123
```

### Show Current Group
```bash
meshml-worker status
```

Displays current group assignment and worker status.

## Group Info Storage

After joining, group information is saved:

**Location:** `~/.meshml/current_group.json`

**Contents:**
```json
{
  "group_id": "group_abc123",
  "group_name": "ImageNet Training",
  "role": "worker",
  "joined_at": "2024-01-15T10:32:00Z",
  "parameter_server": "ps.meshml.io:50051"
}
```

Workers automatically reconnect to saved groups on restart.

## Authentication

All API requests after registration require authentication:

```python
headers = {
    "Authorization": f"Bearer {auth_token}"
}
```

Auth tokens are stored securely in `~/.meshml/credentials.json` (permissions 600).

## Security Considerations

1. **Invitation Codes:**
   - Single-use or limited-use tokens
   - Expiration timestamps
   - Revocable by group owner

2. **Public Groups:**
   - Capability verification
   - Rate limiting on joins
   - Owner approval queue (optional)

3. **Auth Tokens:**
   - JWT with expiration
   - Refresh token mechanism
   - Stored with restricted permissions

## Troubleshooting

### "Registration failed: Connection refused"
- Check API Gateway is running: `http://localhost:8000/health`
- Verify `api_base_url` in config.yaml

### "Invalid invitation code"
- Code may be expired (check with group owner)
- Code may have reached max uses
- Verify code was copied correctly

### "Capability requirements not met"
- Group requires GPU, worker only has CPU
- Insufficient RAM or storage
- Check group requirements: `meshml-worker group-info group_abc123`

### "Worker already in group"
- Leave current group first: `meshml-worker leave-group`
- Or join with `--force` flag

## Examples

### Complete Registration Flow

```python
from meshml_worker.config import load_config
from meshml_worker.registration import WorkerRegistration

# Load configuration
config = load_config("config.yaml")

# Create registration manager
registration = WorkerRegistration(config)

# Register worker (auto-detects capabilities)
worker_info = registration.register_worker()
print(f"Registered: {worker_info['worker_id']}")

# Join via invitation
group = registration.join_group_by_invitation("inv_abc123xyz789")
print(f"Joined: {group['group_name']}")

# Request job assignment
job = registration.request_job_assignment()
if job:
    print(f"Assigned job: {job['job_id']}")
else:
    print("No jobs available")
```

### Interactive Setup

```bash
# Run installer
./install.sh

# Prompts:
# - Email: user@example.com
# - Worker name: my-gpu-worker
# - Server URL: http://localhost:8000
# - GPU detected: NVIDIA RTX 3080 (10GB)
#
# Would you like to register now? [Y/n]: y
#
# How would you like to join a group?
# 1. Enter invitation code
# 2. Browse public groups
# 3. Skip
#
# Choose: 1
# Enter invitation code: inv_abc123xyz789
#
# ✓ Joined group: ImageNet Training
```

### Capability Matching

Workers are matched to groups based on capabilities:

```python
# Worker capabilities (auto-detected)
capabilities = {
    "device": "cuda",
    "gpu_name": "NVIDIA RTX 3080",
    "gpu_memory_gb": 10.0,
    "cpu_cores": 8,
    "ram_gb": 32.0,
    "storage_gb": 500.0
}

# Group requirements
requirements = {
    "device": "gpu",
    "min_gpu_memory_gb": 8.0,
    "min_ram_gb": 16.0
}

# Match: Worker exceeds all requirements ✓
```

## Next Steps

- Implement API Gateway endpoints (see `TASKS.md` Phase 3)
- Add database models for invitations and group memberships
- Create CLI commands for registration
- Test invitation flow end-to-end
- Add metrics for group activity

## Related Documentation

- [API Gateway Setup](./API_GATEWAY.md)
- [Worker Configuration](./WORKER_CONFIG.md)
- [Group Management](./GROUP_MANAGEMENT.md)
- [Orchestration Flow](./ORCHESTRATION.md)
