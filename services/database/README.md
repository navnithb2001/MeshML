# MeshML Database Layer

PostgreSQL database schema and migrations for the MeshML distributed training system.

## Overview

This service manages the core database schema with **8 tables** supporting:
- **User authentication** and management
- **Group-based collaboration** with RBAC (owner/admin/member)
- **Custom model registry** with lifecycle states
- **Worker registration** and tracking
- **Training job** management
- **Dataset sharding** and distribution

## Database Schema

### Tables

1. **`users`** - User authentication and profiles
2. **`groups`** - Collaboration groups
3. **`group_members`** - Group membership with roles
4. **`group_invitations`** - Invitation system
5. **`models`** - Custom PyTorch model registry with lifecycle
6. **`workers`** - Device/worker registration
7. **`jobs`** - Training jobs
8. **`data_batches`** - Dataset shards

### Entity Relationships

```
users (1) ----< (N) groups [owner]
users (1) ----< (N) group_members
groups (1) ----< (N) group_members
groups (1) ----< (N) group_invitations
groups (1) ----< (N) models
groups (1) ----< (N) jobs
users (1) ----< (N) models [uploader]
models (1) ----< (N) jobs
models (0..1) ----< (N) models [versioning]
jobs (1) ----< (N) data_batches
workers (0..1) ----< (N) data_batches
```

## Setup

### Prerequisites

- Python 3.10+
- PostgreSQL 15+ (running via Docker or locally)
- Virtual environment (`mesh.venv`)

### Installation

```bash
# Activate virtual environment
source ../../mesh.venv/bin/activate

# Install dependencies
pip install -r requirements.txt

# Copy environment template
cp .env.example .env

# Edit .env with your database credentials
# DATABASE_URL=postgresql://meshml_user:meshml_dev_password@localhost:5432/meshml
```

### Running Migrations

```bash
# Generate a new migration (after model changes)
alembic revision --autogenerate -m "Description of changes"

# Apply migrations
alembic upgrade head

# Rollback one migration
alembic downgrade -1

# Show current migration version
alembic current

# Show migration history
alembic history
```

## Usage

### Using with FastAPI

```python
from fastapi import Depends
from sqlalchemy.orm import Session
from database.session import get_db
from database.models import User

@app.get("/users")
def list_users(db: Session = Depends(get_db)):
    return db.query(User).all()
```

### Using with Context Manager

```python
from database.session import get_db_context
from database.models import Group

with get_db_context() as db:
    group = db.query(Group).filter_by(id=1).first()
    print(group.name)
```

### Creating Records

```python
from database.session import get_db_context
from database.models import User, Group, GroupMember, GroupRole

with get_db_context() as db:
    # Create user
    user = User(
        email="student@example.com",
        username="student1",
        hashed_password="hashed_pw_here",
        full_name="Student One"
    )
    db.add(user)
    db.flush()  # Get user.id
    
    # Create group
    group = Group(
        name="ML Research Team",
        description="Collaborative ML experiments",
        owner_id=user.id
    )
    db.add(group)
    db.flush()
    
    # Add member
    member = GroupMember(
        group_id=group.id,
        user_id=user.id,
        role=GroupRole.OWNER
    )
    db.add(member)
    # Commit happens automatically on context exit
```

## Model Lifecycle States

### Model Status Flow
```
UPLOADING → VALIDATING → READY | FAILED
READY → DEPRECATED
```

- **UPLOADING**: File being uploaded to GCS
- **VALIDATING**: Running validation (syntax, structure, instantiation)
- **READY**: Validated and ready for use in jobs
- **FAILED**: Validation failed (check `validation_error` field)
- **DEPRECATED**: Superseded by newer version

### Job Status Flow
```
PENDING → VALIDATING → RUNNING → COMPLETED | FAILED | CANCELLED
RUNNING → PAUSED → RUNNING
```

## Configuration

### Environment Variables

| Variable | Description | Default |
|----------|-------------|---------|
| `DATABASE_URL` | PostgreSQL connection string | Required |
| `DATABASE_ECHO` | Log SQL queries | `False` |
| `pool_size` | Connection pool size | `5` |
| `max_overflow` | Max additional connections | `10` |
| `pool_timeout` | Connection timeout (seconds) | `30` |
| `pool_recycle` | Recycle connections after (seconds) | `3600` |

### Production (Google Cloud SQL)

```bash
# For Cloud SQL with Unix socket
DATABASE_URL=postgresql://user:password@/meshml?host=/cloudsql/project:region:instance

# For Cloud SQL with TCP
DATABASE_URL=postgresql://user:password@CLOUD_SQL_IP:5432/meshml
```

## Testing

```bash
# Run database tests
pytest tests/

# Check migration can upgrade/downgrade
alembic upgrade head
alembic downgrade base
alembic upgrade head
```

## Enums

### GroupRole
- `owner` - Full control, can delete group
- `admin` - Can manage members and settings
- `member` - Can view and participate

### InvitationStatus
- `pending` - Invitation sent, awaiting response
- `accepted` - Invitation accepted
- `rejected` - Invitation declined
- `expired` - Invitation timeout reached

### ModelStatus
- `uploading` - Upload in progress
- `validating` - Validation in progress
- `ready` - Ready for use
- `failed` - Validation failed
- `deprecated` - No longer active

### WorkerType
- `python` - PyTorch Python worker
- `cpp` - LibTorch C++ worker
- `javascript` - ONNX Runtime Web worker

### WorkerStatus
- `online` - Connected and available
- `offline` - Disconnected
- `busy` - Processing task
- `error` - Error state

### JobStatus
- `pending` - Queued
- `validating` - Model/dataset validation
- `running` - Training in progress
- `paused` - Temporarily stopped
- `completed` - Successfully finished
- `failed` - Error occurred
- `cancelled` - User cancelled

### BatchStatus
- `pending` - Not assigned
- `assigned` - Assigned to worker
- `processing` - Worker processing
- `completed` - Successfully processed
- `failed` - Processing failed

## Files

```
database/
├── alembic/              # Migration scripts
│   ├── versions/         # Generated migrations
│   ├── env.py           # Alembic environment
│   └── script.py.mako   # Migration template
├── models/               # SQLAlchemy ORM models
│   ├── __init__.py
│   ├── base.py          # Base class + TimestampMixin
│   ├── user.py          # User model
│   ├── group.py         # Group, GroupMember, GroupInvitation
│   ├── model.py         # Model registry
│   ├── worker.py        # Worker tracking
│   ├── job.py           # Training jobs
│   └── data_batch.py    # Dataset shards
├── config.py             # Pydantic settings
├── session.py            # Database session management
├── alembic.ini           # Alembic configuration
├── .env                  # Local credentials (git-ignored)
├── .env.example          # Environment template
├── requirements.txt      # Python dependencies
└── README.md             # This file
```

## Troubleshooting

### Connection Refused
```bash
# Check if PostgreSQL is running
docker ps | grep postgres

# Start Docker services
cd ../../infrastructure/docker
docker-compose up -d
```

### Authentication Failed
```bash
# Verify credentials in .env match docker-compose.yml
cat .env
cat ../../infrastructure/docker/docker-compose.yml | grep POSTGRES
```

### Migration Conflicts
```bash
# Check current state
alembic current

# See pending migrations
alembic heads

# Stamp database to specific revision
alembic stamp head
```

## Next Steps

After database setup:
1. **TASK-1.2**: Redis cache structure for real-time data
2. **TASK-1.3**: Database access layer (CRUD operations, utilities)
3. **Phase 2**: gRPC/REST API communication protocols

---

**Architecture**: See `docs/architecture/ARCHITECTURE.md`  
**Tasks**: See `docs/TASKS.md` (Phase 1)  
**Progress**: See `docs/PROGRESS.md`
