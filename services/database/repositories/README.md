# Database Access Layer - Repository Pattern

**TASK-1.3**: Complete database access layer with CRUD operations and transaction management.

---

## 📖 Overview

This module implements the **Repository Pattern** for clean separation of data access logic from business logic. It provides:

- **Generic Base Repository**: Type-safe CRUD operations for all models
- **Model-Specific Repositories**: Domain-specific queries for each entity
- **Transaction Management**: Context managers, retry logic, savepoints
- **Type Safety**: Full type hints using `TypeVar[T]` and `Mapped[]`

---

## 🏗️ Architecture

```
repositories/
├── __init__.py           # Exports all repositories and utilities
├── base.py               # BaseRepository<T> - Generic CRUD operations
├── user.py               # UserRepository - User management
├── group.py              # Group, Member, Invitation repositories
├── model.py              # ModelRepository - Model lifecycle
├── job.py                # Worker, Job, DataBatch repositories
└── transactions.py       # Transaction utilities and exceptions
```

---

## 🔧 Base Repository

**File**: `base.py`

Generic repository providing full CRUD operations for any SQLAlchemy model.

### Type Safety

```python
from typing import TypeVar, Generic
from database.models.base import Base

T = TypeVar('T', bound=Base)

class BaseRepository(Generic[T]):
    def __init__(self, db: Session, model: Type[T]):
        self.db = db
        self.model = model
```

### Create Operations

```python
# Create single record
user = user_repo.create(
    email='student@ex.com',
    username='student1',
    hashed_password='hashed_pw'
)
# Returns: User object with ID

# Create multiple records
users = user_repo.create_many([
    {'email': 'user1@ex.com', 'username': 'user1', ...},
    {'email': 'user2@ex.com', 'username': 'user2', ...}
])
# Returns: List[User]
```

### Read Operations

```python
# Get by ID
user = user_repo.get_by_id(42)
# Returns: User | None

# Get by field
user = user_repo.get_by_field('email', 'student@ex.com')
# Returns: User | None

# Get all with filters
active_users = user_repo.get_all(
    filters={'is_active': True},
    order_by='created_at',
    descending=True,
    limit=100,
    offset=0
)
# Returns: List[User]

# Count
total = user_repo.count(filters={'is_active': True})
# Returns: int

# Check existence
exists = user_repo.exists(email='test@ex.com')
# Returns: bool

# Pagination
page = user_repo.paginate(page=2, per_page=20)
# Returns: List[User]
```

### Update Operations

```python
# Update single record
updated_user = user_repo.update(
    user_id,
    full_name='Updated Name',
    is_verified=True
)
# Returns: User | None

# Update multiple records
count = user_repo.update_many(
    filters={'is_active': False},
    is_verified=False
)
# Returns: int (number of updated records)
```

### Delete Operations

```python
# Delete single record
user_repo.delete(user_id)
# Returns: None

# Delete multiple records
count = user_repo.delete_many(filters={'is_active': False})
# Returns: int (number of deleted records)
```

---

## 👤 User Repository

**File**: `user.py`

Specialized repository for user management and authentication.

### Methods

```python
user_repo = UserRepository(db)

# Email/Username queries
user = user_repo.get_by_email('student@ex.com')
user = user_repo.get_by_username('student1')
exists = user_repo.email_exists('test@ex.com')
exists = user_repo.username_exists('testuser')

# Status queries
active_users = user_repo.get_active_users()
verified_users = user_repo.get_verified_users()

# User management
user_repo.activate_user(user_id)
user_repo.deactivate_user(user_id)
user_repo.verify_user(user_id)
user_repo.update_password(user_id, new_hashed_password)
```

---

## 👥 Group Repositories

**File**: `group.py`

Three repositories for group collaboration with RBAC:

### 1. GroupRepository

```python
group_repo = GroupRepository(db)

# Owner queries
groups = group_repo.get_by_owner(user_id)

# User membership
user_groups = group_repo.get_user_groups(user_id)

# Deactivation
group_repo.deactivate_group(group_id)
```

### 2. GroupMemberRepository

```python
member_repo = GroupMemberRepository(db)

# Membership queries
members = member_repo.get_group_members(group_id)
role = member_repo.get_member_role(group_id, user_id)

# Permission checks
is_member = member_repo.is_member(group_id, user_id)
is_owner = member_repo.is_owner(group_id, user_id)
is_admin = member_repo.is_admin(group_id, user_id)

# Membership management
member_repo.add_member(group_id, user_id, GroupRole.MEMBER)
member_repo.update_role(group_id, user_id, GroupRole.ADMIN)
member_repo.remove_member(group_id, user_id)
```

### 3. GroupInvitationRepository

```python
invitation_repo = GroupInvitationRepository(db)

# Invitation queries
invitation = invitation_repo.get_by_token('unique-token')
pending = invitation_repo.get_pending_invitations(group_id)

# Invitation actions
invitation_repo.accept_invitation(invitation_id)
invitation_repo.reject_invitation(invitation_id)
invitation_repo.expire_invitation(invitation_id)

# Cleanup
invitation_repo.expire_old_invitations(hours=48)
```

---

## 🤖 Model Repository

**File**: `model.py`

Manages custom PyTorch model lifecycle (uploading → validating → ready/failed → deprecated).

### Methods

```python
model_repo = ModelRepository(db)

# Queries
models = model_repo.get_by_group(group_id)
ready_models = model_repo.get_ready_models()
user_models = model_repo.get_by_uploader(user_id)

# Lifecycle management
model_repo.set_uploading(model_id)
model_repo.set_validating(model_id)
model_repo.set_ready(model_id, metadata={'size_bytes': 1024})
model_repo.set_failed(model_id, error='Validation error')
model_repo.set_deprecated(model_id)

# Versioning
versions = model_repo.get_model_versions(parent_model_id)
latest = model_repo.get_latest_version(name='resnet', group_id=1)
```

---

## 💼 Job Repositories

**File**: `job.py`

Three repositories for distributed training workflow:

### 1. WorkerRepository

```python
worker_repo = WorkerRepository(db)

# Worker queries
worker = worker_repo.get_by_worker_id('worker-001')
online = worker_repo.get_online_workers()

# Heartbeat management
worker_repo.update_heartbeat(worker_id)
worker_repo.set_status(worker_id, WorkerStatus.BUSY)

# Stale worker cleanup
worker_repo.mark_stale_workers_offline(threshold_minutes=5)
```

### 2. JobRepository

```python
job_repo = JobRepository(db)

# Job queries
group_jobs = job_repo.get_by_group(group_id)
active = job_repo.get_active_jobs()

# Status management
job_repo.set_status(job_id, JobStatus.RUNNING)
job_repo.update_progress(job_id, progress=75.0, current_epoch=7)

# Job completion
job_repo.mark_as_completed(job_id)
job_repo.mark_as_failed(job_id, error='Worker timeout')

# Job control
job_repo.pause_job(job_id)
job_repo.resume_job(job_id)
job_repo.cancel_job(job_id)
```

### 3. DataBatchRepository

```python
batch_repo = DataBatchRepository(db)

# Batch queries
batches = batch_repo.get_by_job(job_id)
pending = batch_repo.get_pending_batches(job_id)

# Batch assignment
batch_repo.assign_to_worker(batch_id, worker_id)
batch_repo.mark_processing(batch_id)
batch_repo.mark_completed(batch_id)
batch_repo.mark_failed(batch_id)

# Progress tracking
completion = batch_repo.get_job_completion_percentage(job_id)
# Returns: float (0.0 to 100.0)
```

---

## 🔄 Transaction Management

**File**: `transactions.py`

Utilities for safe transaction handling with automatic commit/rollback.

### 1. Transaction Context Manager

```python
from database.repositories.transactions import transaction

with get_db_context() as db:
    with transaction(db) as tx:
        user = user_repo.create(email='test@ex.com', ...)
        group = group_repo.create(name='Team', owner_id=user.id)
        # Auto-commit on success
        # Auto-rollback on exception
```

### 2. Execute in Transaction

Wrap any function to run in a transaction:

```python
from database.repositories.transactions import execute_in_transaction

def create_group_with_members(db, group_data, member_ids):
    group_repo = GroupRepository(db)
    member_repo = GroupMemberRepository(db)
    
    group = group_repo.create(**group_data)
    for user_id in member_ids:
        member_repo.add_member(group.id, user_id, GroupRole.MEMBER)
    return group

with get_db_context() as db:
    group = execute_in_transaction(
        create_group_with_members,
        db=db,
        group_data={'name': 'Research', 'owner_id': 1},
        member_ids=[2, 3, 4]
    )
```

### 3. Batch Insert

Bulk insert with automatic batching for performance:

```python
from database.repositories.transactions import batch_insert
from database.models.data_batch import DataBatch, BatchStatus

batches = [
    DataBatch(
        job_id=42,
        batch_index=i,
        shard_path=f'gs://meshml-data/batch-{i}.pt',
        size_bytes=1024000,
        checksum=f'checksum{i}',
        status=BatchStatus.PENDING
    )
    for i in range(10000)
]

with get_db_context() as db:
    batch_insert(db, batches, batch_size=500)
    # Inserts in chunks of 500 for efficiency
```

### 4. Retry Transaction

Automatically retry failed transactions (useful for transient errors):

```python
from database.repositories.transactions import retry_transaction

def update_model_status(db, model_id):
    model_repo = ModelRepository(db)
    model_repo.set_ready(model_id, metadata={'validated': True})

with get_db_context() as db:
    retry_transaction(
        update_model_status,
        max_retries=5,
        db=db,
        model_id=123
    )
    # Retries up to 5 times on failure
```

### 5. Savepoints (Nested Transactions)

Use savepoints for complex multi-step operations:

```python
from database.repositories.transactions import transaction, savepoint

with get_db_context() as db:
    with transaction(db):
        user = user_repo.create(email='test@ex.com', ...)
        
        with savepoint(db, "group_creation"):
            try:
                group = group_repo.create(name='Team', owner_id=user.id)
                member_repo.add_member(group.id, user.id, GroupRole.OWNER)
            except Exception as e:
                # Rollback to savepoint
                # User creation is preserved
                logger.error(f"Group creation failed: {e}")
```

---

## ⚠️ Custom Exceptions

```python
from database.repositories.transactions import TransactionError, DuplicateRecordError

try:
    with transaction(db):
        user = user_repo.create(email='duplicate@ex.com', ...)
except DuplicateRecordError as e:
    # Handle integrity constraint violation (unique email)
    logger.error(f"User already exists: {e}")
except TransactionError as e:
    # Handle general transaction failures
    logger.error(f"Transaction failed: {e}")
```

---

## 📝 Complete Usage Example

```python
from database.session import get_db_context
from database.repositories import (
    UserRepository, GroupRepository, GroupMemberRepository,
    ModelRepository, JobRepository, DataBatchRepository
)
from database.repositories.transactions import transaction, execute_in_transaction
from database.models.group import GroupRole
from database.models.model import ModelStatus
from database.models.job import JobStatus
from database.models.data_batch import BatchStatus

# Create a complete training job workflow
with get_db_context() as db:
    with transaction(db):
        # 1. Create user
        user_repo = UserRepository(db)
        user = user_repo.create(
            email='researcher@university.edu',
            username='researcher1',
            hashed_password='hashed_pw',
            full_name='Dr. Researcher'
        )
        user_repo.verify_user(user.id)
        
        # 2. Create group
        group_repo = GroupRepository(db)
        group = group_repo.create(
            name='AI Research Lab',
            owner_id=user.id
        )
        
        # 3. Add group members
        member_repo = GroupMemberRepository(db)
        member_repo.add_member(group.id, user.id, GroupRole.OWNER)
        
        # 4. Upload model
        model_repo = ModelRepository(db)
        model = model_repo.create(
            name='custom-resnet',
            group_id=group.id,
            uploaded_by_id=user.id,
            gcs_path='gs://meshml-models/resnet/model.py',
            status=ModelStatus.UPLOADING
        )
        model_repo.set_validating(model.id)
        model_repo.set_ready(model.id, metadata={
            'architecture': 'ResNet-50',
            'params': 25557032,
            'size_bytes': 97781760
        })
        
        # 5. Create training job
        job_repo = JobRepository(db)
        job = job_repo.create(
            name='ImageNet Training',
            group_id=group.id,
            model_id=model.id,
            config={'learning_rate': 0.001, 'batch_size': 64},
            dataset_path='gs://meshml-data/imagenet/train',
            total_epochs=100,
            status=JobStatus.PENDING
        )
        
        # 6. Create data batches
        batch_repo = DataBatchRepository(db)
        for i in range(100):
            batch_repo.create(
                job_id=job.id,
                batch_index=i,
                shard_path=f'gs://meshml-data/imagenet/train/shard-{i:04d}.pt',
                size_bytes=1024000,
                checksum=f'sha256_{i}',
                status=BatchStatus.PENDING
            )
        
        # 7. Start job
        job_repo.set_status(job.id, JobStatus.RUNNING)
        
        print(f"✅ Created complete training workflow:")
        print(f"   User: {user.username}")
        print(f"   Group: {group.name}")
        print(f"   Model: {model.name} ({model.status})")
        print(f"   Job: {job.name} ({job.status})")
        print(f"   Batches: 100 shards created")
```

---

## 🧪 Testing

All CRUD operations validated:

```bash
$ python -c "import sys; sys.path.insert(0, 'services'); ..."

Testing Database Access Layer (TASK-1.3)
============================================================

📦 UserRepository
  ✅ Create: testuser (ID: 8)
  ✅ Get by email: test@meshml.com
  ✅ Verify: is_verified=True

📦 GroupRepository
  ✅ Create: Test Group (ID: 8)

📦 ModelRepository
  ✅ Create: test-model (Status: ModelStatus.UPLOADING)
  ✅ Set ready: status=ModelStatus.READY

📦 WorkerRepository
  ✅ Create: worker-001 (WorkerStatus.ONLINE)
  ✅ Update heartbeat

📦 JobRepository
  ✅ Create: Test Job (Status: JobStatus.PENDING)
  ✅ Update progress: 75% (epoch 7/10)

📦 DataBatchRepository
  ✅ Create: batch index 0
  ✅ Assign to worker: status=BatchStatus.ASSIGNED

🧹 Cleanup
  ✅ All test data deleted

============================================================
✅ All CRUD operations validated!
============================================================
```

---

## 🚀 FastAPI Integration

```python
from fastapi import FastAPI, Depends, HTTPException
from database.session import get_db
from database.repositories import UserRepository, GroupRepository

app = FastAPI()

@app.post("/users/")
def create_user(
    email: str,
    username: str,
    password: str,
    db: Session = Depends(get_db)
):
    user_repo = UserRepository(db)
    
    # Check duplicates
    if user_repo.email_exists(email):
        raise HTTPException(400, "Email already exists")
    if user_repo.username_exists(username):
        raise HTTPException(400, "Username already exists")
    
    # Create user
    user = user_repo.create(
        email=email,
        username=username,
        hashed_password=hash_password(password)
    )
    return {"id": user.id, "email": user.email}

@app.get("/groups/{group_id}/members")
def list_group_members(
    group_id: int,
    db: Session = Depends(get_db)
):
    member_repo = GroupMemberRepository(db)
    members = member_repo.get_group_members(group_id)
    return [
        {
            "user_id": m.user_id,
            "role": m.role,
            "joined_at": m.created_at
        }
        for m in members
    ]
```

---

## 📊 Design Benefits

1. **Type Safety**: Full type hints with `TypeVar[T]` and `Mapped[]`
2. **Code Reuse**: Generic base repository eliminates duplication
3. **Separation of Concerns**: Data access isolated from business logic
4. **Transaction Safety**: Automatic commit/rollback with context managers
5. **Performance**: Bulk operations with batch insert
6. **Reliability**: Retry logic for transient failures
7. **Testability**: Easy to mock repositories for unit tests
8. **Maintainability**: Clean, organized code structure

---

## 📚 Related Documentation

- **Database Models**: `services/database/models/README.md`
- **Session Management**: `services/database/session.py`
- **Configuration**: `services/database/config.py`
- **Progress Tracking**: `docs/PROGRESS.md` (TASK-1.3)

---

## 🔜 Next Steps

- TASK-1.4: Database migrations and seeding
- TASK-1.5: Integration tests for repositories
- Phase 2: API layer (REST, gRPC, GraphQL)
