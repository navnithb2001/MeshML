# Cloud Deployment & Group Collaboration Architecture

**Last Updated:** March 1, 2026

Complete architecture for deploying MeshML orchestration services on Google Cloud Platform with group-based device collaboration.

---

## Table of Contents

1. [Architecture Overview](#architecture-overview)
2. [Google Cloud Deployment](#google-cloud-deployment)
3. [Group-Based Collaboration](#group-based-collaboration)
4. [Complete User Flow](#complete-user-flow)
5. [Infrastructure Setup](#infrastructure-setup)
6. [Security & Access Control](#security--access-control)

---

## Architecture Overview

### Deployment Model

```
┌──────────────────────────────────────────────────────────────────────┐
│                      GOOGLE CLOUD PLATFORM                           │
│                                                                      │
│  ┌────────────────────────────────────────────────────────────────┐ │
│  │  Google Kubernetes Engine (GKE)                                │ │
│  │                                                                │ │
│  │  ┌──────────────┐  ┌──────────────┐  ┌──────────────────┐   │ │
│  │  │ API Gateway  │  │   Dataset    │  │      Task        │   │ │
│  │  │  (FastAPI)   │  │   Sharder    │  │  Orchestrator    │   │ │
│  │  └──────┬───────┘  └──────┬───────┘  └────────┬─────────┘   │ │
│  │         │                 │                    │             │ │
│  │  ┌──────▼─────────────────▼────────────────────▼─────────┐   │ │
│  │  │          PostgreSQL (Cloud SQL)                       │   │ │
│  │  │          Redis (Memorystore)                          │   │ │
│  │  └───────────────────────────────────────────────────────┘   │ │
│  │                                                                │ │
│  │  ┌──────────────┐  ┌──────────────┐  ┌──────────────────┐   │ │
│  │  │ Parameter    │  │   Metrics    │  │     Model        │   │ │
│  │  │   Server     │  │   Service    │  │    Registry      │   │ │
│  │  └──────────────┘  └──────────────┘  └──────────────────┘   │ │
│  │                                                                │ │
│  └────────────────────────────────────────────────────────────────┘ │
│                                                                      │
│  ┌────────────────────────────────────────────────────────────────┐ │
│  │  Google Cloud Storage (GCS)                                    │ │
│  │  • Datasets (sharded batches)                                 │ │
│  │  • Model files (custom Python files)                          │ │
│  │  • Trained models                                             │ │
│  │  • Training artifacts                                         │ │
│  └────────────────────────────────────────────────────────────────┘ │
│                                                                      │
│  ┌────────────────────────────────────────────────────────────────┐ │
│  │  Cloud Load Balancer                                           │ │
│  │  • HTTPS termination                                           │ │
│  │  • Global distribution                                         │ │
│  └──────────────────────────┬─────────────────────────────────────┘ │
└─────────────────────────────┼───────────────────────────────────────┘
                              │
                              │ HTTPS/gRPC
                              │
        ┌─────────────────────┼─────────────────────┐
        │                     │                     │
        ↓                     ↓                     ↓
┌───────────────┐    ┌───────────────┐    ┌───────────────┐
│ Student Group │    │ Student Group │    │ Student Group │
│  "CS 4375"    │    │  "ML Club"    │    │  "Research"   │
│               │    │               │    │               │
│ 20 devices    │    │ 15 devices    │    │ 8 devices     │
│ (laptops +    │    │ (laptops +    │    │ (servers +    │
│  phones)      │    │  phones)      │    │  laptops)     │
└───────────────┘    └───────────────┘    └───────────────┘
```

### Key Design Decisions

✅ **Centralized Services** - All orchestration on Google Cloud  
✅ **Distributed Workers** - Student devices anywhere (home, campus, coffee shop)  
✅ **Group-Based** - Students form groups, invite members  
✅ **Internet-Based** - No local WiFi requirement, works globally  
✅ **Auto-Scaling** - GKE scales services based on load  
✅ **Managed Storage** - Cloud SQL, Memorystore, GCS

---

## Google Cloud Deployment

### Infrastructure Components

#### 1. Google Kubernetes Engine (GKE)

**Purpose:** Run all microservices  
**Configuration:**
```yaml
# GKE Cluster
cluster:
  name: meshml-production
  region: us-central1
  node_pools:
    - name: services
      machine_type: n2-standard-4
      min_nodes: 2
      max_nodes: 10
      autoscaling: true
    - name: parameter-server
      machine_type: n2-highmem-8  # High memory for model weights
      accelerator: nvidia-tesla-t4  # Optional GPU
      min_nodes: 1
      max_nodes: 5
```

**Services Deployed:**
- API Gateway (3+ replicas)
- Dataset Sharder (2+ replicas)
- Task Orchestrator (2+ replicas)
- Parameter Server (2+ replicas, stateful)
- Metrics Service (2+ replicas)
- Model Registry (2+ replicas)
- Dashboard (3+ replicas)

---

#### 2. Cloud SQL (PostgreSQL)

**Purpose:** Relational database for metadata  
**Configuration:**
```yaml
database:
  instance_type: db-n1-highmem-4
  version: POSTGRES_15
  storage:
    type: SSD
    size: 100GB
    auto_increase: true
  high_availability: true
  region: us-central1
  backups:
    enabled: true
    retention_days: 30
    point_in_time_recovery: true
```

**Tables:**
- `groups` - Group metadata, owner, settings
- `group_members` - Users in groups, roles
- `group_invitations` - Pending invites
- `workers` - Connected devices, capabilities
- `jobs` - Training jobs
- `data_batches` - Dataset shards
- `models` - Uploaded custom models

---

#### 3. Memorystore (Redis)

**Purpose:** Caching, pub/sub, worker heartbeats  
**Configuration:**
```yaml
redis:
  tier: STANDARD_HA  # High availability
  memory_size_gb: 16
  region: us-central1
  read_replicas: 2
  version: redis_7_0
```

**Usage:**
- Worker heartbeats (TTL keys)
- Model weight cache
- Real-time metrics
- Group membership cache
- WebSocket connections

---

#### 4. Google Cloud Storage (GCS)

**Purpose:** Object storage for datasets, models, artifacts  
**Buckets:**

```yaml
buckets:
  # User-uploaded datasets
  - name: meshml-datasets
    location: US-CENTRAL1
    storage_class: STANDARD
    lifecycle:
      - action: DELETE
        condition: age_days > 90  # Delete after 90 days
  
  # Custom model files
  - name: meshml-models
    location: US-CENTRAL1
    storage_class: STANDARD
  
  # Trained model artifacts
  - name: meshml-artifacts
    location: US-CENTRAL1
    storage_class: NEARLINE  # Cheaper for infrequent access
    lifecycle:
      - action: transition_to_ARCHIVE
        condition: age_days > 180
```

---

#### 5. Cloud Load Balancer

**Purpose:** Global HTTPS entry point  
**Configuration:**
```yaml
load_balancer:
  type: GLOBAL_EXTERNAL
  ip: static  # Fixed IP for DNS
  ssl:
    certificate: managed  # Auto-renewal
    domains:
      - meshml.yourschool.edu
      - api.meshml.yourschool.edu
  backends:
    - name: api-gateway
      protocol: HTTPS
      port: 443
    - name: dashboard
      protocol: HTTPS
      port: 443
    - name: grpc-services
      protocol: gRPC
      port: 443
```

---

### Deployment Diagram

```
Internet
   ↓
Cloud Load Balancer (HTTPS/gRPC)
   ↓
┌─────────────────────────────────────────────────────────────┐
│  GKE Cluster                                                 │
│                                                              │
│  Ingress Controller                                         │
│     ↓                    ↓                    ↓             │
│  ┌────────┐        ┌──────────┐        ┌──────────┐       │
│  │Dashboard│        │ API      │        │ gRPC     │       │
│  │Service  │        │ Gateway  │        │ Services │       │
│  │(HTTP)   │        │(HTTP)    │        │          │       │
│  └────────┘        └──────────┘        └──────────┘       │
│                          │                    │             │
│                          ↓                    ↓             │
│     ┌────────────────────────────────────────────────┐     │
│     │  Internal Services (ClusterIP)                 │     │
│     │  • Dataset Sharder                             │     │
│     │  • Task Orchestrator                           │     │
│     │  • Parameter Server                            │     │
│     │  • Metrics Service                             │     │
│     │  • Model Registry                              │     │
│     └────────────────────────────────────────────────┘     │
│                          │                                  │
└──────────────────────────┼──────────────────────────────────┘
                           │
         ┌─────────────────┼─────────────────┐
         ↓                 ↓                 ↓
   Cloud SQL        Memorystore          GCS
   (PostgreSQL)        (Redis)      (Object Storage)
```

---

## Group-Based Collaboration

### Group Model

Instead of open WiFi mesh, students create **private groups** with invited members.

#### Group Structure

```python
# PostgreSQL schema

CREATE TABLE groups (
    id UUID PRIMARY KEY,
    name VARCHAR(255) NOT NULL,
    description TEXT,
    owner_id UUID NOT NULL REFERENCES users(id),
    created_at TIMESTAMP DEFAULT NOW(),
    settings JSONB DEFAULT '{
        "max_members": 100,
        "allow_auto_join": false,
        "require_approval": true,
        "compute_sharing_enabled": true
    }'::jsonb,
    status VARCHAR(50) DEFAULT 'active'
);

CREATE TABLE group_members (
    id UUID PRIMARY KEY,
    group_id UUID NOT NULL REFERENCES groups(id),
    user_id UUID NOT NULL REFERENCES users(id),
    role VARCHAR(50) DEFAULT 'member',  -- 'owner', 'admin', 'member'
    status VARCHAR(50) DEFAULT 'active',  -- 'active', 'inactive', 'banned'
    joined_at TIMESTAMP DEFAULT NOW(),
    compute_contributed_hours DECIMAL DEFAULT 0,
    UNIQUE(group_id, user_id)
);

CREATE TABLE group_invitations (
    id UUID PRIMARY KEY,
    group_id UUID NOT NULL REFERENCES groups(id),
    inviter_id UUID NOT NULL REFERENCES users(id),
    invitee_email VARCHAR(255) NOT NULL,
    status VARCHAR(50) DEFAULT 'pending',  -- 'pending', 'accepted', 'declined', 'expired'
    created_at TIMESTAMP DEFAULT NOW(),
    expires_at TIMESTAMP DEFAULT NOW() + INTERVAL '7 days',
    invitation_code VARCHAR(100) UNIQUE
);
```

---

## Complete User Flow

### Phase 1: Group Creation

**Student A (Group Owner):**

```
1. Opens MeshML Dashboard (https://meshml.yourschool.edu)
   ↓
2. Clicks "Create Group"
   ↓
3. Fills form:
   ┌─────────────────────────────────────────────────┐
   │ Create Training Group                           │
   ├─────────────────────────────────────────────────┤
   │ Group Name: [CS 4375 - Spring 2026________]    │
   │                                                 │
   │ Description:                                    │
   │ ┌─────────────────────────────────────────────┐ │
   │ │ Study group for Deep Learning course.       │ │
   │ │ Let's train models together!                │ │
   │ └─────────────────────────────────────────────┘ │
   │                                                 │
   │ Max Members: [50____] ▼                        │
   │                                                 │
   │ Settings:                                       │
   │ ☑ Require approval for new members             │
   │ ☐ Allow auto-join with link                    │
   │ ☑ Enable compute sharing                       │
   │                                                 │
   │ [Cancel]                    [Create Group →]   │
   └─────────────────────────────────────────────────┘
   ↓
4. Group created!
   • Group ID: grp_abc123
   • Invitation link: https://meshml.yourschool.edu/join/grp_abc123
```

**Backend:**
```python
# API Gateway endpoint
POST /api/v1/groups

{
  "name": "CS 4375 - Spring 2026",
  "description": "Study group for Deep Learning course",
  "max_members": 50,
  "settings": {
    "require_approval": true,
    "allow_auto_join": false,
    "compute_sharing_enabled": true
  }
}

# Response
{
  "group_id": "grp_abc123",
  "invitation_link": "https://meshml.yourschool.edu/join/grp_abc123",
  "invitation_code": "CS4375-SPRING-2026"
}
```

---

### Phase 2: Inviting Members

**Student A invites classmates:**

```
Option 1: Email Invitations
┌─────────────────────────────────────────────────┐
│ Invite Members to "CS 4375 - Spring 2026"      │
├─────────────────────────────────────────────────┤
│ Enter email addresses (one per line):          │
│ ┌─────────────────────────────────────────────┐ │
│ │ bob@university.edu                          │ │
│ │ sarah@university.edu                        │ │
│ │ alex@university.edu                         │ │
│ └─────────────────────────────────────────────┘ │
│                                                 │
│ Personal message (optional):                    │
│ ┌─────────────────────────────────────────────┐ │
│ │ Hey! Join our study group for ML class!    │ │
│ └─────────────────────────────────────────────┘ │
│                                                 │
│ [Cancel]              [Send Invitations →]     │
└─────────────────────────────────────────────────┘

Option 2: Share Invitation Link
┌─────────────────────────────────────────────────┐
│ Share Invitation Link                           │
├─────────────────────────────────────────────────┤
│ Invitation Link:                                │
│ ┌─────────────────────────────────────────────┐ │
│ │ https://meshml.yourschool.edu/join/grp_...  │ │
│ └─────────────────────────────────────────────┘ │
│                              [Copy Link 📋]     │
│                                                 │
│ Or share this code:                             │
│      CS4375-SPRING-2026                        │
│                                                 │
│ [Close]                                         │
└─────────────────────────────────────────────────┘
```

**Backend:**
```python
# Email invitation
POST /api/v1/groups/{group_id}/invitations

{
  "emails": [
    "bob@university.edu",
    "sarah@university.edu",
    "alex@university.edu"
  ],
  "message": "Hey! Join our study group for ML class!"
}

# System sends emails
Subject: You've been invited to join "CS 4375 - Spring 2026" on MeshML

Hi Bob,

Alice Smith has invited you to join their training group "CS 4375 - Spring 2026" on MeshML.

Description: Study group for Deep Learning course. Let's train models together!

Click here to accept: https://meshml.yourschool.edu/invitations/inv_xyz789

This invitation expires in 7 days.

---

# Creates invitation records
INSERT INTO group_invitations (
  group_id, inviter_id, invitee_email, invitation_code
) VALUES (
  'grp_abc123', 'usr_alice', 'bob@university.edu', 'CS4375-SPRING-2026'
);
```

---

### Phase 3: Accepting Invitations

**Student B (Bob) receives invitation:**

```
1. Clicks link in email or enters code
   ↓
2. Views invitation details:
   ┌─────────────────────────────────────────────────┐
   │ Group Invitation                                │
   ├─────────────────────────────────────────────────┤
   │ You've been invited to join:                    │
   │                                                 │
   │ 📚 CS 4375 - Spring 2026                       │
   │    Study group for Deep Learning course.        │
   │    Let's train models together!                 │
   │                                                 │
   │ Group Owner: Alice Smith                        │
   │ Current Members: 1                              │
   │ Max Members: 50                                 │
   │                                                 │
   │ By joining, you agree to:                       │
   │ • Share your device's compute power for group   │
   │   training jobs (when available)                │
   │ • Follow the group's usage policies             │
   │                                                 │
   │ [Decline]                     [Accept & Join →]│
   └─────────────────────────────────────────────────┘
   ↓
3. Clicks "Accept & Join"
   ↓
4. Now a member! Can see group dashboard
```

**Backend:**
```python
# Accept invitation
POST /api/v1/invitations/{invitation_id}/accept

# System:
# 1. Update invitation status
UPDATE group_invitations
SET status = 'accepted'
WHERE id = 'inv_xyz789';

# 2. Add member to group
INSERT INTO group_members (group_id, user_id, role, status)
VALUES ('grp_abc123', 'usr_bob', 'member', 'active');

# 3. Send notification to group owner
NOTIFY group_owner: "Bob joined CS 4375 - Spring 2026"
```

---

### Phase 4: Starting Worker on Device

**Student B wants to contribute compute:**

```
1. Opens MeshML Dashboard
   ↓
2. Goes to "My Groups" → "CS 4375 - Spring 2026"
   ↓
3. Sees group dashboard:
   ┌─────────────────────────────────────────────────┐
   │ CS 4375 - Spring 2026                           │
   ├─────────────────────────────────────────────────┤
   │ Members: 18/50                                  │
   │ Active Workers: 12                              │
   │ Running Jobs: 2                                 │
   │                                                 │
   │ Your Contribution:                              │
   │ • Compute hours: 8.5 hrs                        │
   │ • Worker status: Offline                        │
   │                                                 │
   │ [Start Worker on This Device]                   │
   └─────────────────────────────────────────────────┘
   ↓
4. Clicks "Start Worker on This Device"
   ↓
5. Download options:
   ┌─────────────────────────────────────────────────┐
   │ Start Worker                                    │
   ├─────────────────────────────────────────────────┤
   │ Select worker type:                             │
   │                                                 │
   │ ◉ Python Worker (Recommended)                   │
   │   For: Laptops, desktops                        │
   │   Requirements: Python 3.11+                    │
   │   [Download for macOS/Windows/Linux]            │
   │                                                 │
   │ ○ C++ Worker (High Performance)                 │
   │   For: High-end workstations                    │
   │   [Download Binary]                             │
   │                                                 │
   │ ○ Browser Worker (No Installation)              │
   │   For: Any device with browser                  │
   │   [Launch in Browser →]                         │
   └─────────────────────────────────────────────────┘
   ↓
6. Downloads Python worker:
   File: meshml-worker-macos.zip (15 MB)
   ↓
7. Unzips and runs:
   $ unzip meshml-worker-macos.zip
   $ cd meshml-worker
   $ ./start-worker.sh
   
   MeshML Worker Starting...
   • Detected: macOS 14.2, Apple M2, 16GB RAM
   • Connecting to: https://api.meshml.yourschool.edu
   • Authenticating...
   
   [Enter your access token or login URL]:
   > https://meshml.yourschool.edu/worker-auth?code=ABC123
   
   ✓ Authenticated as: Bob Johnson
   ✓ Registered with groups: CS 4375 - Spring 2026
   ✓ Worker ID: worker_def456
   ✓ Status: Idle, waiting for tasks
   
   Worker is running! Leave this terminal open.
   Press Ctrl+C to stop.
```

**Backend:**
```python
# Worker connects via gRPC
worker_stub.RegisterWorker({
  "user_id": "usr_bob",
  "capabilities": {
    "os": "darwin",
    "arch": "arm64",
    "cpu_cores": 8,
    "ram_bytes": 17179869184,
    "gpu": {"name": "Apple M2", "type": "metal", "memory_bytes": 8589934592},
    "frameworks": {"pytorch": "2.2.0"}
  }
})

# Task Orchestrator:
# 1. Creates worker record
INSERT INTO workers (id, user_id, type, capabilities, status, last_heartbeat)
VALUES ('worker_def456', 'usr_bob', 'python', {...}, 'idle', NOW());

# 2. Associates worker with user's groups
# Worker can now receive tasks from any group Bob is in

# 3. Adds to Redis worker pool
ZADD workers:idle worker_def456 <timestamp>
SET worker:worker_def456:status "idle"
SETEX worker:worker_def456:heartbeat 60 "alive"

# 4. Notifies group members
PUBLISH group:grp_abc123:workers "Bob's device joined (M2 GPU, 16GB RAM)"
```

---

### Phase 5: Creating Training Job (Group-Scoped)

**Student A (group owner) creates training job:**

```
1. In group dashboard, clicks "Create Training Job"
   ↓
2. Fills job form:
   ┌─────────────────────────────────────────────────┐
   │ Create Training Job (CS 4375 - Spring 2026)    │
   ├─────────────────────────────────────────────────┤
   │ Job Name: [MNIST Classification Experiment___] │
   │                                                 │
   │ Model:                                          │
   │ ◉ Upload Custom Python File                    │
   │   [Choose File] mnist_model.py ✓                │
   │                                                 │
   │ Dataset:                                        │
   │ ◉ Upload Folder                                 │
   │   [Choose Folder] ~/datasets/mnist/ ✓           │
   │   60,000 images detected                        │
   │                                                 │
   │ Configuration:                                  │
   │ • Batch size: [64____]                          │
   │ • Epochs: [10___]                               │
   │ • Learning rate: [0.001__]                      │
   │                                                 │
   │ Worker Selection:                               │
   │ ◉ Use all available group workers (12 online)  │
   │ ○ Select specific workers                       │
   │                                                 │
   │ [Cancel]              [Start Training →]       │
   └─────────────────────────────────────────────────┘
   ↓
3. Clicks "Start Training"
   ↓
4. Job created! All group members' workers start training
```

**Backend Flow:**

```python
# 1. Upload model and dataset to GCS
POST /api/v1/groups/{group_id}/jobs

# API Gateway:
gcs_client.upload_file('mnist_model.py', 'meshml-models/job_xyz123/model.py')
gcs_client.upload_folder('./mnist/', 'meshml-datasets/job_xyz123/raw/')

# 2. Dataset Sharder processes
dataset_sharder.shard_dataset(
    source='gs://meshml-datasets/job_xyz123/raw/',
    output='gs://meshml-datasets/job_xyz123/batches/',
    num_batches=100
)

# Creates: batch_001.tar.gz, batch_002.tar.gz, ..., batch_100.tar.gz

# 3. Task Orchestrator assigns tasks
orchestrator.assign_tasks(
    job_id='job_xyz123',
    group_id='grp_abc123',
    batches=100
)

# Queries available workers in group
SELECT w.*
FROM workers w
JOIN group_members gm ON gm.user_id = w.user_id
WHERE gm.group_id = 'grp_abc123'
  AND w.status = 'idle'
  AND w.last_heartbeat > NOW() - INTERVAL '1 minute';

# Result: 12 workers available
# Assignment: 8-9 batches per worker

# 4. Send task assignments via gRPC
for worker in available_workers:
    worker_stub.AssignTask({
        "job_id": "job_xyz123",
        "batches": [
            {
                "batch_id": "batch_001",
                "download_url": "https://storage.googleapis.com/meshml-datasets/job_xyz123/batches/batch_001.tar.gz",
                "checksum": "sha256:abc..."
            },
            # ... more batches
        ],
        "model_url": "https://storage.googleapis.com/meshml-models/job_xyz123/model.py",
        "config": {
            "num_classes": 10,
            "batch_size": 64,
            "learning_rate": 0.001,
            "epochs": 10
        }
    })
```

---

### Phase 6: Distributed Training Execution

**On each worker device:**

```
Worker receives task assignment
   ↓
1. Download model file from GCS
   GET https://storage.googleapis.com/meshml-models/job_xyz123/model.py
   ↓
2. Import model
   from model import create_model, create_dataloader
   ↓
3. Download assigned batches from GCS
   GET https://storage.googleapis.com/meshml-datasets/job_xyz123/batches/batch_001.tar.gz
   ↓
4. Create model and dataloader
   model = create_model(config)
   dataloader = create_dataloader(batch_path, config)
   ↓
5. Training loop
   for epoch in range(10):
       for images, labels in dataloader:
           # Forward pass
           outputs = model(images)
           loss = criterion(outputs, labels)
           
           # Backward pass
           loss.backward()
           optimizer.step()
       
       # Send gradients to Parameter Server (GKE)
       send_gradients_via_grpc(model.state_dict(), epoch)
       
       # Receive updated global weights
       updated_weights = receive_weights_via_grpc()
       model.load_state_dict(updated_weights)
   ↓
6. Report completion
   worker_stub.ReportCompletion({
       "job_id": "job_xyz123",
       "batches_completed": ["batch_001", ...],
       "metrics": {"final_loss": 0.23, "accuracy": 0.96}
   })
```

**Parameter Server (running in GKE):**

```python
# Receives gradients from all 12 workers
gradients_received = []

for worker_gradients in worker_gradients_stream:
    gradients_received.append(worker_gradients)
    
    if len(gradients_received) == 12:  # All workers reported
        # Aggregate (average) gradients
        avg_gradients = {}
        for param_name in gradients_received[0].keys():
            avg_gradients[param_name] = sum(
                g[param_name] for g in gradients_received
            ) / 12
        
        # Update global model
        global_model.load_state_dict(avg_gradients)
        
        # Send updated weights back to all workers
        for worker in workers:
            worker_stub.SendWeights(global_model.state_dict())
        
        # Clear for next iteration
        gradients_received = []
```

---

### Phase 7: Real-Time Monitoring

**All group members can watch progress:**

```
Dashboard (WebSocket updates every 2 seconds)

┌─────────────────────────────────────────────────────────────┐
│ Job: MNIST Classification Experiment                        │
│ Group: CS 4375 - Spring 2026                                │
│ Status: Training 🟢  [██████████░░] 83% Complete           │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│ 📊 Training Metrics                                         │
│                                                             │
│    Loss                            Accuracy                │
│ 2.0┤                           100%┤        ╭───────       │
│ 1.5┤╮                           75%┤    ╭───╯              │
│ 1.0┤ ╲                          50%┤  ╭─╯                  │
│ 0.5┤  ╰─╮                       25%┤╭─╯                    │
│ 0.0┤    ╰────                    0%┼─────────────          │
│    └──────────                     └──────────────         │
│     Epoch 1  5  10                  Epoch 1  5  10         │
│                                                             │
│ Current: Epoch 8/10  Loss: 0.28  Accuracy: 95.3%          │
│                                                             │
│ 👥 Active Workers: 12/12                                   │
│ ┌─────────────────────────────────────────────────────────┐│
│ │ • Alice (M2 Max, macOS)      ▓▓▓▓▓▓▓▓░ 85% [8/8 done]  ││
│ │ • Bob (M2, macOS)            ▓▓▓▓▓▓▓░░ 75% [6/8 done]  ││
│ │ • Sarah (RTX 3080, Windows)  ▓▓▓▓▓▓▓▓▓ 95% [9/9 done]  ││
│ │ • Alex (Browser, Android)    ▓▓▓░░░░░░ 35% [3/8 done]  ││
│ │ • ... (8 more workers)                                  ││
│ └─────────────────────────────────────────────────────────┘│
│                                                             │
│ 📈 Progress                                                 │
│ • Batches: 83/100 (83%)                                    │
│ • Estimated completion: 4 minutes                          │
│ • Total compute hours: 2.1 hrs (saved you ~20 hrs solo!)  │
│                                                             │
│ [Stop Training]  [Download Current Model]  [View Logs]    │
└─────────────────────────────────────────────────────────────┘
```

**WebSocket updates from backend:**

```python
# Metrics Service publishes to Redis Pub/Sub
redis.publish(f'job:{job_id}:metrics', json.dumps({
    "epoch": 8,
    "loss": 0.28,
    "accuracy": 0.953,
    "workers_active": 12,
    "batches_complete": 83,
    "eta_seconds": 240
}))

# Dashboard subscribers receive real-time updates
# React dashboard re-renders charts automatically
```

---

### Phase 8: Training Completion

```
✅ Training Complete!

Job: MNIST Classification Experiment
Group: CS 4375 - Spring 2026
Duration: 23 minutes

Final Results:
• Accuracy: 96.7%
• Loss: 0.19
• Total batches: 100
• Participating workers: 12
• Total compute hours: 4.6 hrs

Top Contributors:
1. Sarah (RTX 3080) - 0.8 hrs
2. Alice (M2 Max) - 0.6 hrs
3. Bob (M2) - 0.4 hrs

[📥 Download Trained Model (.pt)]
[📊 Download Training Report (PDF)]
[📈 Download Metrics (CSV)]
[🔄 Start New Training]
```

**Backend saves results to GCS:**

```python
# Save trained model
final_model = parameter_server.get_final_model()
torch.save(final_model.state_dict(), '/tmp/final_model.pt')
gcs_client.upload_file(
    '/tmp/final_model.pt',
    'meshml-artifacts/job_xyz123/final_model.pt'
)

# Generate training report
report = generate_pdf_report(job_metrics)
gcs_client.upload_file(
    report,
    'meshml-artifacts/job_xyz123/training_report.pdf'
)

# Update job status
UPDATE jobs
SET status = 'completed',
    completed_at = NOW(),
    final_accuracy = 0.967,
    final_loss = 0.19
WHERE id = 'job_xyz123';

# Update worker contribution stats
UPDATE group_members
SET compute_contributed_hours = compute_contributed_hours + 0.4
WHERE user_id = 'usr_bob' AND group_id = 'grp_abc123';

# Notify group members
for member in group_members:
    send_notification(
        member.user_id,
        "Training job 'MNIST Classification Experiment' completed! 96.7% accuracy achieved."
    )
```

---

## Infrastructure Setup

### Google Cloud Setup Steps

#### 1. Enable Required APIs

```bash
# Enable Google Cloud APIs
gcloud services enable \
    container.googleapis.com \
    sqladmin.googleapis.com \
    redis.googleapis.com \
    storage-api.googleapis.com \
    compute.googleapis.com \
    dns.googleapis.com
```

#### 2. Create GKE Cluster

```bash
# Create production cluster
gcloud container clusters create meshml-production \
    --region us-central1 \
    --num-nodes 3 \
    --machine-type n2-standard-4 \
    --enable-autoscaling \
    --min-nodes 2 \
    --max-nodes 10 \
    --enable-autorepair \
    --enable-autoupgrade \
    --addons HttpLoadBalancing,HorizontalPodAutoscaling
```

#### 3. Create Cloud SQL Instance

```bash
# Create PostgreSQL instance
gcloud sql instances create meshml-db \
    --database-version POSTGRES_15 \
    --tier db-n1-highmem-4 \
    --region us-central1 \
    --storage-type SSD \
    --storage-size 100GB \
    --storage-auto-increase \
    --availability-type REGIONAL \
    --backup-start-time 03:00 \
    --enable-bin-log

# Create database
gcloud sql databases create meshml --instance meshml-db
```

#### 4. Create Redis (Memorystore)

```bash
# Create Redis instance
gcloud redis instances create meshml-redis \
    --size 16 \
    --region us-central1 \
    --tier standard \
    --replica-count 2 \
    --redis-version redis_7_0
```

#### 5. Create GCS Buckets

```bash
# Create storage buckets
gsutil mb -c STANDARD -l US-CENTRAL1 gs://meshml-datasets
gsutil mb -c STANDARD -l US-CENTRAL1 gs://meshml-models
gsutil mb -c NEARLINE -l US-CENTRAL1 gs://meshml-artifacts

# Set lifecycle policies
gsutil lifecycle set lifecycle-datasets.json gs://meshml-datasets
```

#### 6. Deploy Services to GKE

```bash
# Apply Kubernetes manifests
kubectl apply -f infrastructure/kubernetes/namespaces.yaml
kubectl apply -f infrastructure/kubernetes/secrets.yaml
kubectl apply -f infrastructure/kubernetes/configmaps.yaml
kubectl apply -f infrastructure/kubernetes/services/
kubectl apply -f infrastructure/kubernetes/deployments/
kubectl apply -f infrastructure/kubernetes/ingress.yaml
```

#### 7. Configure Load Balancer

```bash
# Reserve static IP
gcloud compute addresses create meshml-ip \
    --global \
    --ip-version IPV4

# Get IP address
gcloud compute addresses describe meshml-ip --global

# Configure DNS (at your DNS provider)
# A record: meshml.yourschool.edu -> [IP address]
# A record: api.meshml.yourschool.edu -> [IP address]
```

---

## Security & Access Control

### Authentication & Authorization

#### User Authentication

```python
# JWT-based authentication
# Users log in with university credentials (OAuth 2.0)

# Login flow
POST /api/v1/auth/login
{
  "email": "bob@university.edu",
  "password": "...",  # Or OAuth provider
  "provider": "google"  # Optional: SSO
}

# Response
{
  "access_token": "eyJ...",  # Valid for 1 hour
  "refresh_token": "...",     # Valid for 30 days
  "user": {
    "id": "usr_bob",
    "email": "bob@university.edu",
    "name": "Bob Johnson"
  }
}
```

#### Group Access Control

```python
# Role-Based Access Control (RBAC) per group

ROLES = {
    "owner": {
        "can_delete_group": True,
        "can_manage_members": True,
        "can_create_jobs": True,
        "can_view_jobs": True,
        "can_manage_settings": True
    },
    "admin": {
        "can_delete_group": False,
        "can_manage_members": True,
        "can_create_jobs": True,
        "can_view_jobs": True,
        "can_manage_settings": False
    },
    "member": {
        "can_delete_group": False,
        "can_manage_members": False,
        "can_create_jobs": True,
        "can_view_jobs": True,
        "can_manage_settings": False
    }
}

# Check permission
def check_permission(user_id, group_id, action):
    member = db.query(
        "SELECT role FROM group_members WHERE user_id = ? AND group_id = ?",
        user_id, group_id
    )
    return ROLES[member.role].get(action, False)
```

#### Worker Authentication

```python
# Workers authenticate with user tokens
# Workers can only join jobs from groups user belongs to

# Worker registration
worker_stub.RegisterWorker({
    "user_token": "eyJ...",  # User's JWT
    "capabilities": {...}
})

# Task Orchestrator validates:
# 1. Token is valid
# 2. User belongs to group that created job
# 3. Worker meets job requirements
```

### Network Security

```yaml
# GKE Network Policies
apiVersion: networking.k8s.io/v1
kind: NetworkPolicy
metadata:
  name: meshml-network-policy
spec:
  podSelector:
    matchLabels:
      app: meshml
  policyTypes:
  - Ingress
  - Egress
  ingress:
  # Only allow ingress from load balancer
  - from:
    - namespaceSelector:
        matchLabels:
          name: kube-system
  egress:
  # Allow egress to Cloud SQL, Redis, GCS
  - to:
    - podSelector:
        matchLabels:
          app: cloud-sql-proxy
  - to:
    - namespaceSelector:
        matchLabels:
          name: kube-system
```

### Data Privacy

```python
# User data isolation
# Workers only download batches assigned to their jobs
# No worker can access another group's data

# GCS permissions per group
def get_batch_signed_url(batch_id, user_id):
    # Verify user is in group that owns this batch
    batch = db.get_batch(batch_id)
    if not user_in_group(user_id, batch.group_id):
        raise PermissionDenied()
    
    # Generate time-limited signed URL (1 hour)
    url = gcs_client.generate_signed_url(
        f"meshml-datasets/{batch.job_id}/{batch_id}.tar.gz",
        expiration=3600
    )
    return url
```

---

## Summary

### Architecture Benefits

✅ **Scalable** - Google Cloud auto-scales services based on demand  
✅ **Global** - Students anywhere can join (not limited to local WiFi)  
✅ **Secure** - Group-based access control, encrypted communication  
✅ **Managed** - No infrastructure for students/professors to maintain  
✅ **Reliable** - High availability, automatic backups  
✅ **Observable** - Real-time monitoring, logging, tracing

### Cost Optimization

- **GKE**: Auto-scaling reduces costs during low usage
- **Cloud SQL**: Right-sized instance with auto-storage
- **GCS**: Lifecycle policies archive old data
- **Spot VMs**: Use preemptible nodes for parameter server (30-60% cheaper)

### Next Steps

1. ✅ Deploy infrastructure to Google Cloud
2. ✅ Implement Phase 1 (Database schema for groups)
3. ✅ Build group management UI
4. ✅ Create worker authentication system
5. ✅ Test with pilot group of students

**Ready to build this! 🚀**
