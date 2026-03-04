# Database Seeding

**TASK-1.4**: Database seeding utilities for development and testing.

---

## 📖 Overview

This module provides comprehensive database seeding capabilities:

- **Realistic Test Data**: Pre-configured users, groups, models, workers, jobs, and batches
- **Idempotent Seeding**: Can run multiple times safely (checks for existing data)
- **Configurable Parameters**: Control number of users, groups, and workers
- **CLI Interface**: Simple command-line tool for seeding operations
- **Transaction Safety**: All seeding operations wrapped in transactions

---

## 🚀 Quick Start

### Seed with Default Values

```bash
cd /Users/navnithbharadwaj/Desktop/autoapply/MeshML
source mesh.venv/bin/activate
python services/database/seed_cli.py seed
```

**Default Values:**
- 5 users (Alice, Bob, Charlie, Diana, Eve)
- 3 groups (AI Research Lab, ML Study Group, Computer Vision Team)
- 10 workers (laptops, mobiles, desktops)
- 4 models (ResNet50, VGG16, MobileNet, Custom CNN)
- 3 jobs (1 running, 1 pending, 1 completed)
- 100 data batches for the running job

### Custom Seed Parameters

```bash
python services/database/seed_cli.py seed --users 10 --groups 5 --workers 20
```

### Check Database Status

```bash
python services/database/seed_cli.py status
```

Output:
```
============================================================
📊 Database Status
============================================================
Total users:         5
Total groups:        3
Total models:        4
Total workers:       10
Total jobs:          3
Total batches:       100
============================================================
```

### Clear All Data

**⚠️ WARNING: This deletes ALL data from the database!**

```bash
# With confirmation prompt
python services/database/seed_cli.py clear

# Skip confirmation (for scripts)
python services/database/seed_cli.py clear --force
```

---

## 📚 Programmatic Usage

### Basic Seeding

```python
from database.session import get_db_context
from database.seed import seed_database

with get_db_context() as db:
    stats = seed_database(db)
    print(f"Created {stats['users']} users, {stats['groups']} groups")
```

### Custom Seeder

```python
from database.session import get_db_context
from database.seed import DatabaseSeeder

with get_db_context() as db:
    seeder = DatabaseSeeder(db)
    
    # Seed individual components
    seeder.seed_users(count=10)
    seeder.seed_groups(count=5)
    seeder.seed_workers(count=20)
    
    # Access created entities
    for user in seeder.users:
        print(f"User: {user.username} ({user.email})")
    
    for group in seeder.groups:
        print(f"Group: {group.name} (Owner: {group.owner_id})")
```

### Clear Database

```python
from database.session import get_db_context
from database.seed import clear_database

with get_db_context() as db:
    stats = clear_database(db)
    print(f"Deleted {stats['users']} users, {stats['groups']} groups")
```

---

## 🧪 Seed Data Details

### Users (5 default)

| Username | Email | Full Name | Verified | Active |
|----------|-------|-----------|----------|--------|
| alice | alice@university.edu | Alice Johnson | ✅ | ✅ |
| bob | bob@university.edu | Bob Smith | ✅ | ✅ |
| charlie | charlie@university.edu | Charlie Davis | ✅ | ✅ |
| diana | diana@university.edu | Diana Martinez | ❌ | ✅ |
| eve | eve@university.edu | Eve Wilson | ✅ | ❌ |

**Password**: All users have `hashed_password_123` (in production, use proper hashing)

### Groups (3 default)

| Group Name | Description | Owner | Members |
|------------|-------------|-------|---------|
| AI Research Lab | Deep learning and computer vision | Alice | Alice (owner), Bob (admin), Charlie (member) |
| ML Study Group | Collaborative ML learning | Bob | Bob (owner), Alice (admin), Diana (member) |
| Computer Vision Team | Image classification | Charlie | Charlie (owner), Alice (member) |

### Group Invitations (2 default)

- **Pending**: newstudent@university.edu invited to AI Research Lab (expires in 7 days)
- **Expired**: expired@university.edu invited to ML Study Group (expired yesterday)

### Models (4 default)

| Name | Architecture | Group | Status | Uploader |
|------|--------------|-------|--------|----------|
| resnet50-custom | ResNet-50 | AI Research Lab | READY ✅ | Alice |
| vgg16-transfer | VGG16 | AI Research Lab | VALIDATING 🔄 | Bob |
| mobilenet-v2 | MobileNetV2 | ML Study Group | READY ✅ | Bob |
| custom-cnn | Custom CNN | Computer Vision Team | FAILED ❌ | Charlie |

### Workers (10 default)

| Worker ID | Name | Type | Status | Capabilities |
|-----------|------|------|--------|--------------|
| worker-laptop-001 | Alice Laptop | Python | ONLINE 🟢 | RTX 3080, 32GB RAM, 16 cores |
| worker-laptop-002 | Bob Laptop | Python | BUSY 🟡 | GTX 1660, 16GB RAM, 8 cores |
| worker-mobile-001 | Charlie Phone | JavaScript | ONLINE 🟢 | 6GB RAM, 8 cores |
| worker-desktop-001 | Lab Desktop | C++ | ONLINE 🟢 | RTX 4090, 64GB RAM, 32 cores |
| worker-offline-001 | Offline Device | Python | OFFLINE 🔴 | 8GB RAM, 4 cores |
| worker-auto-005 to worker-auto-009 | Auto Worker 5-9 | Python | Mixed | Various |

### Jobs (3 default)

| Name | Model | Group | Status | Progress | Epochs |
|------|-------|-------|--------|----------|--------|
| ImageNet Training - ResNet50 | resnet50-custom | AI Research Lab | RUNNING 🔄 | 25% | 25/100 |
| CIFAR-10 Transfer Learning | mobilenet-v2 | ML Study Group | PENDING ⏳ | 0% | 0/50 |
| Completed Training Run | resnet50-custom | AI Research Lab | COMPLETED ✅ | 100% | 10/10 |

### Data Batches (100 for running job)

- **Completed**: 10 batches
- **Processing**: 10 batches
- **Assigned**: 10 batches
- **Pending**: 70 batches
- **Total Size**: ~1GB (100 shards × ~10MB each)

---

## 🔧 DatabaseSeeder Class

### Methods

#### `seed_all(num_users, num_groups, num_workers)`
Seed all database tables with test data in dependency order.

```python
stats = seeder.seed_all(num_users=5, num_groups=3, num_workers=10)
# Returns: {'users': 5, 'groups': 3, 'models': 4, 'workers': 10, 'jobs': 3, 'batches': 100}
```

#### `seed_users(count)`
Create test users (Alice, Bob, Charlie, Diana, Eve, ...).

```python
users = seeder.seed_users(count=10)
# Returns: List[User]
```

#### `seed_groups(count)`
Create test groups (AI Research Lab, ML Study Group, Computer Vision Team).

```python
groups = seeder.seed_groups(count=3)
# Returns: List[Group]
```

#### `seed_group_members()`
Add members to groups with appropriate roles (owner, admin, member).

```python
members = seeder.seed_group_members()
# Returns: List[GroupMember]
```

#### `seed_group_invitations()`
Create pending and expired invitations.

```python
invitations = seeder.seed_group_invitations()
# Returns: List[GroupInvitation]
```

#### `seed_models()`
Create models with various statuses (ready, validating, failed).

```python
models = seeder.seed_models()
# Returns: List[Model]
```

#### `seed_workers(count)`
Create worker devices (laptops, mobiles, desktops) with various statuses.

```python
workers = seeder.seed_workers(count=20)
# Returns: List[Worker]
```

#### `seed_jobs()`
Create training jobs (running, pending, completed).

```python
jobs = seeder.seed_jobs()
# Returns: List[Job]
```

#### `seed_data_batches()`
Create data batches for running jobs with various statuses.

```python
batches = seeder.seed_data_batches()
# Returns: List[DataBatch]
```

#### `clear_all()`
Delete all data from database (⚠️ USE WITH CAUTION).

```python
stats = seeder.clear_all()
# Returns: {'users': 5, 'groups': 3, 'models': 4, 'workers': 10, 'jobs': 3, 'batches': 100}
```

---

## 📝 CLI Commands

### `seed` - Seed Database

```bash
python services/database/seed_cli.py seed [OPTIONS]

Options:
  --users INTEGER    Number of users to create (default: 5)
  --groups INTEGER   Number of groups to create (default: 3)
  --workers INTEGER  Number of workers to create (default: 10)
```

**Examples:**
```bash
# Default seeding
python services/database/seed_cli.py seed

# Custom counts
python services/database/seed_cli.py seed --users 10 --groups 5 --workers 20

# Minimal seeding
python services/database/seed_cli.py seed --users 2 --groups 1 --workers 3
```

### `status` - Show Database Statistics

```bash
python services/database/seed_cli.py status
```

Shows current counts of all entities in the database.

### `clear` - Clear All Data

```bash
python services/database/seed_cli.py clear [OPTIONS]

Options:
  --force  Skip confirmation prompt
```

**Examples:**
```bash
# With confirmation
python services/database/seed_cli.py clear

# Skip confirmation (for scripts)
python services/database/seed_cli.py clear --force
```

---

## 🔄 Idempotent Seeding

The seeder checks for existing data before creating:

```python
# If user already exists, reuse it
existing = self.user_repo.get_by_email(user_data['email'])
if not existing:
    user = self.user_repo.create(**user_data)
    self.users.append(user)
else:
    self.users.append(existing)
    logger.debug(f"User already exists: {existing.username}")
```

This allows you to run seeding multiple times without creating duplicates.

---

## 🎯 Use Cases

### Development Setup

```bash
# Fresh database setup
alembic upgrade head
python services/database/seed_cli.py seed
```

### Testing

```python
import pytest
from database.session import get_db_context
from database.seed import DatabaseSeeder

@pytest.fixture
def seeded_db():
    with get_db_context() as db:
        seeder = DatabaseSeeder(db)
        seeder.seed_all(num_users=5, num_groups=2, num_workers=5)
        yield db
        seeder.clear_all()  # Cleanup after tests

def test_job_creation(seeded_db):
    # Test with pre-seeded data
    jobs = seeded_db.query(Job).all()
    assert len(jobs) == 3
```

### Demo/Presentation

```bash
# Set up realistic demo data
python services/database/seed_cli.py seed --users 10 --groups 5 --workers 30

# Show current state
python services/database/seed_cli.py status

# Clean up after demo
python services/database/seed_cli.py clear --force
```

---

## 🚨 Important Notes

1. **Password Security**: The seeder uses placeholder passwords (`hashed_password_123`). In production, use proper password hashing (bcrypt, argon2, etc.).

2. **GCS Paths**: Seed data uses example GCS paths (`gs://meshml-models/...`). These are placeholders and won't work without actual Google Cloud Storage setup.

3. **Transaction Safety**: All seeding operations are wrapped in transactions, so failures roll back completely.

4. **Idempotency**: Running seed multiple times won't create duplicates (checks email/username).

5. **Cleanup**: Use `clear` command with caution - it deletes ALL data from all tables!

---

## 📚 Related Documentation

- **Database Models**: `services/database/models/README.md`
- **Repositories**: `services/database/repositories/README.md`
- **Session Management**: `services/database/session.py`
- **Progress Tracking**: `docs/PROGRESS.md` (TASK-1.4)

---

## 🔜 Next Steps

- TASK-1.5: Integration tests using seeded data
- Phase 2: API layer (REST, gRPC, GraphQL)
- Phase 3: API Gateway with authentication
