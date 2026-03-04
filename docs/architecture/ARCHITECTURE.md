# MeshML Complete Architecture Specification

**Version:** 1.0  
**Last Updated:** March 1, 2026  
**Status:** Design Complete - Ready for Implementation

---

## Table of Contents

1. [System Overview](#system-overview)
2. [Architecture Components](#architecture-components)
3. [Complete Data Flow](#complete-data-flow)
4. [Infrastructure Details](#infrastructure-details)
5. [Security & Access Control](#security--access-control)
6. [Custom Model System](#custom-model-system)
7. [Scalability & Performance](#scalability--performance)
8. [Failure Handling](#failure-handling)
9. [API Specifications](#api-specifications)
10. [Deployment Guide](#deployment-guide)

---

## 1. System Overview

### 1.1 What is MeshML?

MeshML is a **distributed machine learning training platform** where students pool their devices (laptops, phones) to train PyTorch models collaboratively. Instead of running locally, all orchestration runs on **Google Cloud Platform**, and students form **private groups** for secure collaboration.

### 1.2 Key Design Principles

✅ **Cloud-Native**: All services on Google Cloud (GKE, Cloud SQL, Memorystore, GCS)  
✅ **Group-Based**: Invitation-only groups, not open WiFi mesh  
✅ **Model-Agnostic**: Any PyTorch model via custom Python file upload  
✅ **Cross-Platform**: Workers on macOS, Windows, Linux, Android, iOS  
✅ **Internet-Based**: Workers connect globally, not just local network  
✅ **Fault-Tolerant**: Workers can join/leave, batches auto-reassigned  
✅ **Real-Time**: Live monitoring via WebSocket subscriptions

### 1.3 Use Case: Student Assignment

**Scenario:** 20 students in ML class need to train a CNN on MNIST.

**Without MeshML:**
- Each student trains on own laptop: 2 hours
- Total compute waste: 20 × 2 = 40 hours wasted waiting

**With MeshML:**
- Students form group, pool 20 devices
- Training completes in 6 minutes (20× speedup)
- Each student contributes ~6 minutes of compute
- Total wall-clock time saved: 1h 54m per student

---

## 2. Architecture Components

### 2.1 High-Level Architecture

```
┌──────────────────────────────────────────────────────────────────┐
│                     GOOGLE CLOUD PLATFORM                        │
│                                                                  │
│  ┌────────────────────────────────────────────────────────────┐ │
│  │  GKE Cluster (Kubernetes)                                  │ │
│  │                                                            │ │
│  │  Microservices:                                           │ │
│  │  • API Gateway (FastAPI)                                  │ │
│  │  • Dataset Sharder (Python)                               │ │
│  │  • Task Orchestrator (Celery)                             │ │
│  │  • Parameter Server (PyTorch)                             │ │
│  │  • Metrics Service (GraphQL)                              │ │
│  │  • Model Registry (FastAPI)                               │ │
│  │  • Dashboard Backend (GraphQL)                            │ │
│  └────────────────────────────────────────────────────────────┘ │
│                                                                  │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────────────┐ │
│  │  Cloud SQL   │  │ Memorystore  │  │  Cloud Storage (GCS) │ │
│  │ (PostgreSQL) │  │   (Redis)    │  │  • Datasets          │ │
│  │              │  │              │  │  • Models            │ │
│  │ • groups     │  │ • heartbeats │  │  • Artifacts         │ │
│  │ • workers    │  │ • weights    │  └──────────────────────┘ │
│  │ • jobs       │  │ • pub/sub    │                           │
│  │ • batches    │  └──────────────┘                           │
│  └──────────────┘                                              │
│                                                                  │
│  ┌────────────────────────────────────────────────────────────┐ │
│  │  Cloud Load Balancer (Global HTTPS)                        │ │
│  └──────────────────────┬─────────────────────────────────────┘ │
└─────────────────────────┼───────────────────────────────────────┘
                          │
                          │ Internet (HTTPS/gRPC)
                          │
        ┌─────────────────┼─────────────────┬─────────────────┐
        │                 │                 │                 │
        ↓                 ↓                 ↓                 ↓
  ┌──────────┐      ┌──────────┐     ┌──────────┐     ┌──────────┐
  │  Worker  │      │  Worker  │     │  Worker  │     │Dashboard │
  │  Python  │      │   C++    │     │JavaScript│     │  React   │
  │  (macOS) │      │(Windows) │     │(Browser) │     │  (Web)   │
  └──────────┘      └──────────┘     └──────────┘     └──────────┘
   Student's         Student's       Student's        Student's
   Laptop           Desktop          Phone            Browser
```

### 2.2 Component Details

#### 2.2.1 API Gateway (FastAPI)

**Responsibility:** Single entry point for all HTTP/REST requests

**Endpoints:**
- `POST /api/v1/auth/login` - User authentication
- `POST /api/v1/groups` - Create group
- `POST /api/v1/groups/{id}/invitations` - Invite members
- `POST /api/v1/groups/{id}/jobs` - Create training job
- `POST /api/v1/uploads/model` - Upload custom Python model
- `POST /api/v1/uploads/dataset` - Upload dataset
- `GET /api/v1/jobs/{id}/status` - Job status
- `GET /api/v1/jobs/{id}/download` - Download trained model

**Technologies:**
- FastAPI 0.109+
- Pydantic for validation
- SQLAlchemy for database ORM
- JWT for authentication
- Multipart file upload handling

**Scaling:** 3-10 replicas (auto-scaled by GKE)

---

#### 2.2.2 Dataset Sharder

**Responsibility:** Split uploaded datasets into batches for distribution

**Process:**
1. Receives dataset upload notification
2. Downloads from GCS
3. Detects format (ImageFolder, COCO, CSV, etc.)
4. Validates structure
5. Splits into N batches (configurable, default: 500 samples/batch)
6. Creates tar.gz archives
7. Computes SHA256 checksums
8. Uploads batches to GCS
9. Stores metadata in PostgreSQL

**Supported Formats:**
- ImageFolder (class folders)
- COCO JSON
- CSV (tabular)
- JSON Lines (text)
- Custom (user-defined handler)

**Technologies:**
- Python 3.11+
- Pandas, NumPy, Pillow
- tarfile, hashlib
- Google Cloud Storage client

**Scaling:** 2-5 replicas

---

#### 2.2.3 Task Orchestrator (Celery)

**Responsibility:** Assign batches to workers, monitor progress, handle failures

**Key Functions:**

**Worker Registration:**
```python
def register_worker(worker_id, user_id, capabilities):
    # Store in PostgreSQL
    # Add to Redis idle pool
    # Associate with user's groups
```

**Task Assignment:**
```python
def assign_tasks(job_id, group_id):
    # Query available workers in group
    # Calculate batch distribution based on capabilities
    # Send gRPC assignments
    # Update batch status
```

**Failure Handling:**
```python
def handle_worker_failure(worker_id):
    # Mark worker as failed
    # Find orphaned batches
    # Reassign to other workers
```

**Heartbeat Monitoring:**
```python
# Redis-based heartbeat with TTL
@celery.task(run_every=timedelta(seconds=30))
def check_heartbeats():
    # Check Redis TTL keys
    # Mark expired workers as offline
    # Trigger failure handling
```

**Technologies:**
- Celery 5.3+ (task queue)
- Redis as broker
- APScheduler for cron jobs
- gRPC client for worker communication

**Scaling:** 2-5 replicas

---

#### 2.2.4 Parameter Server (PyTorch)

**Responsibility:** Aggregate gradients, maintain global model, serve weights

**Algorithm:** Federated Averaging

**Process per Epoch:**
```python
def aggregate_gradients(job_id, epoch):
    # Collect gradients from all workers
    gradients_buffer = []
    
    while len(gradients_buffer) < num_workers:
        grad = receive_gradient_via_grpc()
        gradients_buffer.append(grad)
    
    # Average gradients
    avg_grad = {}
    for param_name in gradients_buffer[0].keys():
        avg_grad[param_name] = np.mean([
            g[param_name] for g in gradients_buffer
        ], axis=0)
    
    # Update global model
    for param_name, grad in avg_grad.items():
        global_model.state_dict()[param_name] -= lr * grad
    
    # Cache in Redis
    redis.set(f'model:{job_id}:epoch_{epoch}', 
              serialize(global_model.state_dict()))
    
    # Persist checkpoint to GCS
    save_checkpoint(global_model, epoch)
    
    return global_model.state_dict()
```

**Optimizations:**
- Gradient compression (quantization, sparsification)
- Asynchronous updates (don't wait for slow workers)
- Model weight caching in Redis
- Periodic checkpointing to GCS

**Technologies:**
- PyTorch 2.2+
- gRPC server
- Redis for caching
- NumPy for aggregation

**Scaling:** 2-5 replicas (stateful, needs careful handling)

---

#### 2.2.5 Metrics Service (GraphQL)

**Responsibility:** Collect, aggregate, and serve real-time metrics

**GraphQL Schema:**
```graphql
type Job {
  id: ID!
  name: String!
  status: JobStatus!
  metrics: JobMetrics!
  workers: [Worker!]!
}

type JobMetrics {
  epoch: Int!
  loss: Float!
  accuracy: Float!
  batchesComplete: Int!
  batchesTotal: Int!
  etaSeconds: Int!
  workersActive: Int!
}

type Subscription {
  jobMetrics(jobId: ID!): JobMetrics!
  workerStatus(jobId: ID!): [WorkerStatus!]!
}
```

**Data Flow:**
```
Workers → gRPC → Metrics Service → Redis Pub/Sub → WebSocket → Dashboard
```

**Technologies:**
- Strawberry GraphQL 0.219+
- Redis Pub/Sub
- WebSocket support
- PostgreSQL for historical data

**Scaling:** 2-5 replicas

---

#### 2.2.6 Dashboard (React)

**Responsibility:** User interface for all interactions

**Pages:**
- Login / Registration
- My Groups
- Create Group
- Group Dashboard
- Create Job
- Job Monitoring (real-time charts)
- Worker Management
- Download Results

**Technologies:**
- React 18.2
- TypeScript 5.0
- Zustand (state management)
- Apollo Client (GraphQL)
- Recharts (visualization)
- TailwindCSS (styling)

**Features:**
- Real-time updates via GraphQL subscriptions
- Live training charts (loss, accuracy)
- Worker status visualization
- Drag-drop file uploads
- Responsive design (mobile-friendly)

**Scaling:** 3-10 replicas (static assets on CDN)

---

#### 2.2.7 Workers (Python/C++/JavaScript)

**Responsibility:** Execute training on student devices

**Common Interface:**
```
1. Register with Task Orchestrator
2. Receive task assignment
3. Download model file from GCS
4. Download assigned batches from GCS
5. Execute training loop:
   - Load data
   - Forward pass
   - Backward pass
   - Send gradients to Parameter Server
   - Receive updated weights
6. Report completion
7. Return to idle state
```

**Python Worker:**
- Target: Laptops (macOS, Windows, Linux)
- Framework: PyTorch 2.2+
- GPU: CUDA, Metal (MPS), ROCm
- Installation: pip install meshml-worker

**C++ Worker:**
- Target: High-performance workstations
- Framework: LibTorch
- GPU: CUDA, Metal
- Installation: CMake build

**JavaScript Worker:**
- Target: Browsers (phones, tablets, laptops)
- Framework: ONNX Runtime Web
- GPU: WebGPU, WebGL
- Installation: None (runs in browser)

---

### 2.3 Data Storage

#### 2.3.1 PostgreSQL (Cloud SQL)

**Tables:**

```sql
-- Users
CREATE TABLE users (
    id UUID PRIMARY KEY,
    email VARCHAR(255) UNIQUE NOT NULL,
    name VARCHAR(255),
    password_hash VARCHAR(255),
    created_at TIMESTAMP DEFAULT NOW()
);

-- Groups
CREATE TABLE groups (
    id UUID PRIMARY KEY,
    name VARCHAR(255) NOT NULL,
    description TEXT,
    owner_id UUID REFERENCES users(id),
    created_at TIMESTAMP DEFAULT NOW(),
    settings JSONB DEFAULT '{
        "max_members": 100,
        "require_approval": true,
        "compute_sharing_enabled": true
    }'::jsonb,
    status VARCHAR(50) DEFAULT 'active'
);

-- Group Members
CREATE TABLE group_members (
    id UUID PRIMARY KEY,
    group_id UUID REFERENCES groups(id) ON DELETE CASCADE,
    user_id UUID REFERENCES users(id),
    role VARCHAR(50) DEFAULT 'member',  -- owner, admin, member
    status VARCHAR(50) DEFAULT 'active',
    joined_at TIMESTAMP DEFAULT NOW(),
    compute_contributed_hours DECIMAL DEFAULT 0,
    UNIQUE(group_id, user_id)
);

-- Group Invitations
CREATE TABLE group_invitations (
    id UUID PRIMARY KEY,
    group_id UUID REFERENCES groups(id) ON DELETE CASCADE,
    inviter_id UUID REFERENCES users(id),
    invitee_email VARCHAR(255) NOT NULL,
    invitation_code VARCHAR(100) UNIQUE,
    status VARCHAR(50) DEFAULT 'pending',  -- pending, accepted, declined, expired
    created_at TIMESTAMP DEFAULT NOW(),
    expires_at TIMESTAMP DEFAULT NOW() + INTERVAL '7 days'
);

-- Workers
CREATE TABLE workers (
    id VARCHAR(255) PRIMARY KEY,
    user_id UUID REFERENCES users(id),
    type VARCHAR(50) NOT NULL,  -- python, cpp, javascript
    capabilities JSONB NOT NULL,
    status VARCHAR(50) DEFAULT 'idle',  -- idle, busy, offline, failed
    current_job_id UUID,
    last_heartbeat TIMESTAMP DEFAULT NOW(),
    created_at TIMESTAMP DEFAULT NOW()
);

-- Jobs
CREATE TABLE jobs (
    id UUID PRIMARY KEY,
    group_id UUID REFERENCES groups(id),
    name VARCHAR(255) NOT NULL,
    description TEXT,
    model_url TEXT NOT NULL,  -- GCS path to custom model file
    dataset_url TEXT NOT NULL,  -- GCS path to dataset
    status VARCHAR(50) DEFAULT 'pending',  -- pending, sharding, ready, running, completed, failed
    config JSONB NOT NULL,  -- Training configuration
    created_by UUID REFERENCES users(id),
    created_at TIMESTAMP DEFAULT NOW(),
    started_at TIMESTAMP,
    completed_at TIMESTAMP,
    final_accuracy DECIMAL,
    final_loss DECIMAL
);

-- Data Batches
CREATE TABLE data_batches (
    id UUID PRIMARY KEY,
    job_id UUID REFERENCES jobs(id) ON DELETE CASCADE,
    batch_id VARCHAR(100) NOT NULL,
    download_url TEXT NOT NULL,  -- GCS signed URL
    checksum VARCHAR(128) NOT NULL,  -- SHA256
    size_bytes BIGINT,
    status VARCHAR(50) DEFAULT 'pending',  -- pending, assigned, processing, completed, failed
    worker_id VARCHAR(255) REFERENCES workers(id),
    assigned_at TIMESTAMP,
    completed_at TIMESTAMP,
    retry_count INT DEFAULT 0,
    UNIQUE(job_id, batch_id)
);

-- Training Metrics (TimescaleDB hypertable)
CREATE TABLE training_metrics (
    time TIMESTAMPTZ NOT NULL,
    job_id UUID NOT NULL,
    worker_id VARCHAR(255),
    batch_id VARCHAR(100),
    epoch INT,
    loss DECIMAL,
    accuracy DECIMAL,
    samples_processed INT,
    PRIMARY KEY (time, job_id)
);

-- Convert to TimescaleDB hypertable
SELECT create_hypertable('training_metrics', 'time');
```

**Indexes:**
```sql
CREATE INDEX idx_group_members_group ON group_members(group_id);
CREATE INDEX idx_group_members_user ON group_members(user_id);
CREATE INDEX idx_workers_status ON workers(status);
CREATE INDEX idx_workers_user ON workers(user_id);
CREATE INDEX idx_jobs_group ON jobs(group_id);
CREATE INDEX idx_jobs_status ON jobs(status);
CREATE INDEX idx_batches_job ON data_batches(job_id);
CREATE INDEX idx_batches_worker ON data_batches(worker_id);
CREATE INDEX idx_batches_status ON data_batches(status);
CREATE INDEX idx_metrics_job ON training_metrics(job_id, time DESC);
```

---

#### 2.3.2 Redis (Memorystore)

**Usage:**

**1. Worker Heartbeats (TTL keys):**
```
SETEX worker:{worker_id}:heartbeat 60 "alive"
# Auto-expires if worker doesn't ping within 60s
```

**2. Worker Status:**
```
SET worker:{worker_id}:status "idle"
ZADD workers:idle {worker_id} {timestamp}
ZADD workers:busy {worker_id} {timestamp}
```

**3. Model Weight Cache:**
```
SET model:{job_id}:epoch_{n} {serialized_state_dict}
EXPIRE model:{job_id}:epoch_{n} 3600  # 1 hour TTL
```

**4. Real-Time Metrics Pub/Sub:**
```
PUBLISH job:{job_id}:metrics {json_data}
SUBSCRIBE job:{job_id}:metrics
```

**5. Group Member Cache:**
```
SMEMBERS group:{group_id}:members  # Set of user IDs
EXPIRE group:{group_id}:members 300  # 5 min TTL
```

---

#### 2.3.3 Google Cloud Storage (GCS)

**Buckets:**

**1. meshml-datasets**
```
gs://meshml-datasets/
  └── {job_id}/
      ├── raw/  (original upload)
      └── batches/
          ├── batch_001.tar.gz
          ├── batch_002.tar.gz
          └── ...
```

**2. meshml-models**
```
gs://meshml-models/
  └── {job_id}/
      ├── model.py  (custom model file)
      └── checkpoints/
          ├── epoch_1.pt
          ├── epoch_2.pt
          └── ...
```

**3. meshml-artifacts**
```
gs://meshml-artifacts/
  └── {job_id}/
      ├── final_model.pt
      ├── training_report.pdf
      ├── metrics.csv
      └── logs.txt
```

**Access Control:**
- Signed URLs with 1-hour expiration
- User must be in group to access job artifacts
- Workers authenticate with user JWT

---

## 3. Complete Data Flow

### 3.1 Group Creation Flow

```
User (Alice) → Browser → Dashboard
       ↓
POST /api/v1/groups
{
  "name": "CS 4375 Study Group",
  "description": "Deep Learning class",
  "max_members": 50,
  "settings": {"require_approval": true}
}
       ↓
API Gateway:
  1. Validate JWT token
  2. Extract user_id from token
  3. Insert into PostgreSQL:
     INSERT INTO groups (id, name, owner_id, ...) VALUES (...)
     INSERT INTO group_members (group_id, user_id, role) VALUES (..., ..., 'owner')
  4. Generate invitation code
     INSERT INTO group_invitations (group_id, invitation_code, ...) VALUES (...)
       ↓
Response:
{
  "group_id": "grp_abc123",
  "invitation_link": "https://meshml.edu/join/grp_abc123",
  "invitation_code": "CS4375-STUDY-2026"
}
```

---

### 3.2 Invitation & Joining Flow

```
Inviter (Alice) → POST /api/v1/groups/{id}/invitations
{
  "emails": ["bob@university.edu", "sarah@university.edu"]
}
       ↓
API Gateway:
  1. Check Alice has permission (is owner/admin)
  2. For each email:
     INSERT INTO group_invitations (group_id, invitee_email, ...) VALUES (...)
     Send email with invitation link
       ↓
Invitee (Bob) receives email, clicks link
       ↓
GET /api/v1/invitations/{invitation_id}
       ↓
Browser shows invitation details
       ↓
POST /api/v1/invitations/{invitation_id}/accept
       ↓
API Gateway:
  1. Validate invitation not expired
  2. Update invitation:
     UPDATE group_invitations SET status = 'accepted' WHERE id = ...
  3. Add to group:
     INSERT INTO group_members (group_id, user_id, role) VALUES (..., 'usr_bob', 'member')
  4. Clear cache:
     DEL group:{group_id}:members
  5. Notify group:
     PUBLISH group:{group_id}:events "Bob joined"
       ↓
Alice's dashboard receives WebSocket notification: "Bob joined the group"
```

---

### 3.3 Worker Registration Flow

```
Student (Bob) downloads worker, runs: ./start-worker.sh
       ↓
Worker process starts:
  1. Detect hardware:
     - OS: macOS 14.2
     - CPU: Apple M2 (8 cores)
     - RAM: 16GB
     - GPU: Apple M2 (Metal, 8GB VRAM)
     - Frameworks: PyTorch 2.2.0
  
  2. Authenticate:
     - Read token from config or prompt login URL
     - Validate JWT with API Gateway
  
  3. Connect to Task Orchestrator via gRPC
       ↓
gRPC: RegisterWorker({
  "user_id": "usr_bob",
  "capabilities": {
    "os": "darwin", "arch": "arm64",
    "cpu_cores": 8, "ram_bytes": 17179869184,
    "gpu": {"name": "Apple M2", "type": "metal", "memory_bytes": 8589934592},
    "frameworks": {"pytorch": "2.2.0"}
  }
})
       ↓
Task Orchestrator:
  1. Generate worker_id: "worker_bob_m2_001"
  
  2. Store in PostgreSQL:
     INSERT INTO workers (id, user_id, type, capabilities, status, last_heartbeat)
     VALUES ('worker_bob_m2_001', 'usr_bob', 'python', {...}, 'idle', NOW())
  
  3. Add to Redis:
     ZADD workers:idle worker_bob_m2_001 {timestamp}
     SET worker:worker_bob_m2_001:status "idle"
     SETEX worker:worker_bob_m2_001:heartbeat 60 "alive"
  
  4. Fetch user's groups:
     SELECT group_id FROM group_members WHERE user_id = 'usr_bob'
     Associate worker with groups: Bob is in "grp_abc123"
       ↓
Response: {
  "worker_id": "worker_bob_m2_001",
  "status": "registered",
  "groups": ["grp_abc123"]
}
       ↓
Worker enters idle loop:
  - Every 30s: Send heartbeat (SETEX worker:{id}:heartbeat 60 "alive")
  - Listen for task assignments on gRPC stream
```

---

### 3.4 Job Creation & Dataset Sharding Flow

```
User (Alice) → Dashboard → Create Job Form
       ↓
1. Upload custom model file: my_cnn.py (5KB)
   POST /api/v1/uploads/model
       ↓
   API Gateway:
     - Validate Python syntax
     - Check has create_model(), create_dataloader(), MODEL_METADATA
     - Upload to GCS: gs://meshml-models/job_xyz789/model.py
       ↓
2. Upload dataset: ~/datasets/mnist/ (150MB, 60,000 images)
   POST /api/v1/uploads/dataset (multipart upload)
       ↓
   API Gateway:
     - Stream upload to GCS: gs://meshml-datasets/job_xyz789/raw/
     - Trigger Dataset Sharder
       ↓
Dataset Sharder (Celery task):
  1. Download from GCS
  2. Detect format: ImageFolder ✓
  3. Validate structure: 10 class folders ✓
  4. Count samples: 60,000
  5. Calculate batches: 60,000 / 600 = 100 batches
  6. For batch_id in range(100):
       - Select 600 random samples (stratified by class)
       - Create tar.gz archive
       - Compute SHA256 checksum
       - Upload to GCS: gs://meshml-datasets/job_xyz789/batches/batch_{id:03d}.tar.gz
       - Store metadata:
         INSERT INTO data_batches (job_id, batch_id, download_url, checksum, size_bytes, status)
         VALUES ('job_xyz789', 'batch_001', 'gs://...', 'sha256:abc...', 104857600, 'pending')
       ↓
3. Create job
   POST /api/v1/groups/{group_id}/jobs
   {
     "name": "MNIST Experiment",
     "model_url": "gs://meshml-models/job_xyz789/model.py",
     "dataset_url": "gs://meshml-datasets/job_xyz789/batches/",
     "config": {
       "num_classes": 10,
       "batch_size": 64,
       "learning_rate": 0.001,
       "epochs": 10
     }
   }
       ↓
   API Gateway:
     INSERT INTO jobs (id, group_id, name, model_url, status, config, created_by)
     VALUES ('job_xyz789', 'grp_abc123', 'MNIST Experiment', 'gs://...', 'ready', {...}, 'usr_alice')
       ↓
   Task Orchestrator notified: "New job ready for assignment"
```

---

### 3.5 Task Assignment Flow

```
Task Orchestrator detects new job: job_xyz789
       ↓
1. Query available workers in group:
   
   SELECT w.id, w.capabilities, w.status
   FROM workers w
   JOIN group_members gm ON gm.user_id = w.user_id
   WHERE gm.group_id = 'grp_abc123'
     AND w.status = 'idle'
     AND w.last_heartbeat > NOW() - INTERVAL '1 minute'
   
   Result: 12 workers available
     - worker_alice_m2max (M2 Max, 32GB)
     - worker_bob_m2 (M2, 16GB)
     - worker_sarah_rtx3080 (RTX 3080, 32GB)
     - worker_alex_browser (Browser, 4GB)
     - ... 8 more
       ↓
2. Calculate batch distribution (based on capabilities):
   
   Total batches: 100
   Workers: 12
   
   Strategy: Assign more batches to more powerful workers
   - High-end GPU (RTX 3080): 12 batches
   - Mid-range GPU (M2 Max, M2): 9 batches
   - Low-end (Browser): 5 batches
   
   worker_sarah_rtx3080: batch_001 to batch_012
   worker_alice_m2max: batch_013 to batch_021
   worker_bob_m2: batch_022 to batch_030
   worker_alex_browser: batch_031 to batch_035
   ...
       ↓
3. Update database:
   
   UPDATE data_batches
   SET worker_id = 'worker_bob_m2', status = 'assigned', assigned_at = NOW()
   WHERE batch_id IN ('batch_022', 'batch_023', ..., 'batch_030')
   
   UPDATE workers
   SET status = 'busy', current_job_id = 'job_xyz789'
   WHERE id = 'worker_bob_m2'
       ↓
4. Send gRPC task assignments to each worker:
   
   worker_stub.AssignTask({
     "job_id": "job_xyz789",
     "assigned_batches": [
       {
         "batch_id": "batch_022",
         "download_url": "https://storage.googleapis.com/meshml-datasets/job_xyz789/batches/batch_022.tar.gz",
         "checksum": "sha256:def456...",
         "size_bytes": 104857600
       },
       ... (8 more batches)
     ],
     "model_url": "https://storage.googleapis.com/meshml-models/job_xyz789/model.py",
     "config": {
       "num_classes": 10,
       "batch_size": 64,
       "learning_rate": 0.001,
       "epochs": 10
     }
   })
       ↓
Workers receive assignments and start training
```

---

### 3.6 Worker Training Execution Flow

```
Worker (Bob's MacBook) receives task assignment
       ↓
1. Download model file:
   curl https://storage.googleapis.com/meshml-models/job_xyz789/model.py
   Save to: /tmp/meshml/model.py
   Verify checksum ✓
       ↓
2. Import model functions:
   import sys
   sys.path.insert(0, '/tmp/meshml')
   from model import create_model, create_dataloader, MODEL_METADATA
       ↓
3. Create model instance:
   config = {"num_classes": 10, "batch_size": 64, ...}
   model = create_model(config)
   
   # Detect device
   device = "mps"  # Apple Metal
   model = model.to(device)
       ↓
4. Download first batch:
   curl https://storage.googleapis.com/.../batch_022.tar.gz
   Extract to: /tmp/meshml/batches/batch_022/
   Verify checksum: sha256sum == "def456..." ✓
       ↓
5. Create dataloader:
   dataloader = create_dataloader('/tmp/meshml/batches/batch_022/', config)
   # Returns DataLoader with 600 samples, batch_size=64 → ~10 batches per epoch
       ↓
6. Fetch initial weights from Parameter Server:
   
   gRPC: parameter_server.GetWeights(job_id='job_xyz789', epoch=0)
   Response: initial_weights (randomly initialized or pretrained)
   model.load_state_dict(initial_weights)
       ↓
7. Training loop (10 epochs):
   
   criterion = nn.CrossEntropyLoss()
   optimizer = torch.optim.Adam(model.parameters(), lr=0.001)
   
   for epoch in range(10):
       model.train()
       epoch_loss = 0.0
       correct = 0
       total = 0
       
       for batch_idx, (images, labels) in enumerate(dataloader):
           # Move to GPU
           images = images.to(device)  # MPS
           labels = labels.to(device)
           
           # Forward pass
           outputs = model(images)
           loss = criterion(outputs, labels)
           
           # Backward pass
           optimizer.zero_grad()
           loss.backward()
           optimizer.step()
           
           # Track metrics
           epoch_loss += loss.item()
           _, predicted = outputs.max(1)
           total += labels.size(0)
           correct += predicted.eq(labels).sum().item()
       
       # Calculate epoch metrics
       avg_loss = epoch_loss / len(dataloader)
       accuracy = correct / total
       
       # Report metrics to Metrics Service
       metrics_stub.ReportMetrics({
           "job_id": "job_xyz789",
           "worker_id": "worker_bob_m2",
           "batch_id": "batch_022",
           "epoch": epoch,
           "loss": avg_loss,
           "accuracy": accuracy,
           "samples_processed": 600,
           "timestamp": datetime.now().isoformat()
       })
       
       # Extract gradients
       gradients = {}
       for name, param in model.named_parameters():
           if param.grad is not None:
               gradients[name] = param.grad.cpu().numpy()
       
       # Send gradients to Parameter Server
       parameter_server_stub.UpdateGradients({
           "job_id": "job_xyz789",
           "worker_id": "worker_bob_m2",
           "epoch": epoch,
           "batch_id": "batch_022",
           "gradients": serialize_compress(gradients)  # Pickle + gzip
       })
       
       # Wait for updated global weights
       updated_weights = parameter_server_stub.GetWeights(
           job_id='job_xyz789',
           epoch=epoch + 1
       )
       model.load_state_dict(updated_weights)
       
       print(f"Epoch {epoch+1}/10: Loss={avg_loss:.4f}, Acc={accuracy:.4f}")
       ↓
8. Batch complete! Report to Task Orchestrator:
   
   task_orchestrator_stub.ReportBatchComplete({
       "job_id": "job_xyz789",
       "worker_id": "worker_bob_m2",
       "batch_id": "batch_022",
       "status": "completed",
       "final_metrics": {
           "loss": 0.23,
           "accuracy": 0.96
       }
   })
       ↓
   Task Orchestrator:
     UPDATE data_batches
     SET status = 'completed', completed_at = NOW()
     WHERE batch_id = 'batch_022'
       ↓
9. Repeat for next batch (batch_023, ..., batch_030)
   Download → Train → Report → Next
       ↓
10. All batches done! Worker returns to idle:
    
    UPDATE workers
    SET status = 'idle', current_job_id = NULL
    WHERE id = 'worker_bob_m2'
    
    ZADD workers:idle worker_bob_m2 {timestamp}
```

**Meanwhile, all 12 workers are doing this in parallel!**

---

### 3.7 Parameter Server Gradient Aggregation Flow

```
Parameter Server receives gradients from workers for epoch 1
       ↓
Gradient buffer (in-memory):
  gradients_buffer = []
  expected_workers = 12
       ↓
For each worker's gradient submission:
  
  gRPC receive: UpdateGradients(job_id, worker_id, epoch, gradients)
       ↓
  Deserialize gradients
  Add to buffer: gradients_buffer.append((worker_id, gradients))
       ↓
  if len(gradients_buffer) == expected_workers:
      # All workers reported for this epoch!
      
      1. Aggregate gradients (Federated Averaging):
         
         avg_gradients = {}
         for param_name in gradients_buffer[0][1].keys():
             # Average across all workers
             avg_gradients[param_name] = np.mean([
                 worker_grads[param_name]
                 for _, worker_grads in gradients_buffer
             ], axis=0)
      
      2. Update global model:
         
         for param_name, avg_grad in avg_gradients.items():
             global_model.state_dict()[param_name] -= learning_rate * avg_grad
      
      3. Cache in Redis (fast access for workers):
         
         redis.set(
             f'model:job_xyz789:epoch_1',
             pickle.dumps(global_model.state_dict()),
             ex=3600  # 1 hour TTL
         )
      
      4. Save checkpoint to GCS (persistent):
         
         torch.save(
             global_model.state_dict(),
             '/tmp/checkpoint_epoch1.pt'
         )
         gcs_client.upload_file(
             '/tmp/checkpoint_epoch1.pt',
             'gs://meshml-models/job_xyz789/checkpoints/epoch_1.pt'
         )
      
      5. Clear buffer for next epoch:
         gradients_buffer = []
      
      6. Notify workers: "Epoch 1 weights ready"
         (Workers call GetWeights for epoch 1)
       ↓
Workers fetch updated weights and continue to epoch 2
       ↓
Repeat for epochs 2-10
```

**Optimization: Asynchronous Aggregation**
- Don't wait for slow workers (straggler handling)
- If 10/12 workers report within timeout, aggregate and proceed
- Slow workers contribute to next epoch

---

### 3.8 Real-Time Monitoring Flow

```
Dashboard (Alice's browser) opens job monitoring page
       ↓
1. GraphQL Subscription:
   
   subscription {
     jobMetrics(jobId: "job_xyz789") {
       epoch
       loss
       accuracy
       batchesComplete
       batchesTotal
       etaSeconds
       workersActive
     }
   }
       ↓
2. Backend establishes WebSocket connection
       ↓
3. Workers report metrics every epoch:
   
   Worker → gRPC → Metrics Service:
     ReportMetrics(job_id, worker_id, epoch, loss, accuracy)
       ↓
   Metrics Service:
     1. Store in PostgreSQL (historical):
        INSERT INTO training_metrics (time, job_id, worker_id, epoch, loss, accuracy)
        VALUES (NOW(), 'job_xyz789', 'worker_bob_m2', 3, 0.45, 0.89)
     
     2. Aggregate across all workers:
        SELECT AVG(loss), AVG(accuracy)
        FROM training_metrics
        WHERE job_id = 'job_xyz789' AND epoch = 3
        
        Result: avg_loss=0.42, avg_accuracy=0.91
     
     3. Publish to Redis Pub/Sub:
        redis.publish('job:job_xyz789:metrics', json.dumps({
            "epoch": 3,
            "loss": 0.42,
            "accuracy": 0.91,
            "batches_complete": 36,
            "batches_total": 100,
            "workers_active": 12,
            "eta_seconds": 420
        }))
       ↓
4. GraphQL backend subscribed to Redis:
   
   redis_sub.subscribe('job:job_xyz789:metrics')
       ↓
   On message: Send to WebSocket clients
       ↓
5. Dashboard receives update via WebSocket:
   
   {
     "data": {
       "jobMetrics": {
         "epoch": 3,
         "loss": 0.42,
         "accuracy": 0.91,
         ...
       }
     }
   }
       ↓
6. React component re-renders chart:
   
   <LineChart data={metricsHistory}>
     <Line dataKey="loss" stroke="red" />
     <Line dataKey="accuracy" stroke="green" />
   </LineChart>
       ↓
Alice sees live updating graph! Updates every ~2 seconds
```

---

### 3.9 Job Completion Flow

```
Task Orchestrator monitors batch completions:
  Every 10 seconds: Check if all batches done
       ↓
SELECT COUNT(*) FROM data_batches
WHERE job_id = 'job_xyz789' AND status = 'completed'

Result: 100 (all batches done!)
       ↓
1. Mark job as complete:
   
   UPDATE jobs
   SET status = 'completed', completed_at = NOW()
   WHERE id = 'job_xyz789'
       ↓
2. Retrieve final model from Parameter Server:
   
   final_weights = parameter_server.get_model('job_xyz789', epoch=10)
       ↓
3. Save final model to GCS:
   
   torch.save(final_weights, '/tmp/final_model.pt')
   gcs_client.upload_file(
       '/tmp/final_model.pt',
       'gs://meshml-artifacts/job_xyz789/final_model.pt'
   )
       ↓
4. Calculate final metrics:
   
   SELECT AVG(loss), AVG(accuracy)
   FROM training_metrics
   WHERE job_id = 'job_xyz789' AND epoch = 10
   
   UPDATE jobs
   SET final_loss = 0.19, final_accuracy = 0.967
   WHERE id = 'job_xyz789'
       ↓
5. Generate training report (PDF):
   
   report_generator.create_report({
       "job_name": "MNIST Experiment",
       "final_accuracy": 0.967,
       "final_loss": 0.19,
       "total_time": "23 minutes",
       "workers": 12,
       "batches": 100,
       "epochs": 10,
       "top_contributors": [
           {"name": "Sarah", "compute_hours": 0.8},
           {"name": "Alice", "compute_hours": 0.6},
           {"name": "Bob", "compute_hours": 0.4}
       ]
   })
   
   gcs_client.upload(report.pdf, 'gs://meshml-artifacts/job_xyz789/report.pdf')
       ↓
6. Update worker contribution stats:
   
   UPDATE group_members
   SET compute_contributed_hours = compute_contributed_hours + 0.4
   WHERE user_id = 'usr_bob' AND group_id = 'grp_abc123'
       ↓
7. Release workers back to idle:
   
   UPDATE workers
   SET status = 'idle', current_job_id = NULL
   WHERE current_job_id = 'job_xyz789'
   
   # Move to idle pool in Redis
   ZADD workers:idle worker_bob_m2 {timestamp}
   ZREM workers:busy worker_bob_m2
       ↓
8. Notify all group members:
   
   for member in group_members:
       notification_service.send({
           "user_id": member.user_id,
           "type": "job_complete",
           "message": "Training job 'MNIST Experiment' completed! 96.7% accuracy achieved.",
           "actions": [
               {"label": "Download Model", "url": "/jobs/job_xyz789/download"},
               {"label": "View Report", "url": "/jobs/job_xyz789/report"}
           ]
       })
   
   # Email notification
   send_email(member.email, subject="MeshML: Training Complete", ...)
   
   # Push notification (if mobile app)
   send_push_notification(member.device_token, "Training complete!")
   
   # WebSocket notification (if online)
   redis.publish(f'user:{member.user_id}:notifications', {...})
       ↓
9. Dashboard shows completion:
   
   ✅ Training Complete!
   
   Final Results:
   • Accuracy: 96.7%
   • Loss: 0.19
   • Duration: 23 minutes
   • Workers: 12
   • Total compute: 4.6 hours
   
   [📥 Download Model]  [📊 View Report]  [🔄 Start New Training]
```

---

## 4. Infrastructure Details

### 4.1 Google Cloud Resources

**GKE Cluster:**
```yaml
name: meshml-production
region: us-central1
zones: [us-central1-a, us-central1-b, us-central1-c]

node_pools:
  - name: services
    machine_type: n2-standard-4  # 4 vCPU, 16 GB RAM
    disk_size: 100GB
    disk_type: pd-ssd
    min_nodes: 2
    max_nodes: 10
    autoscaling: true
    
  - name: parameter-server
    machine_type: n2-highmem-8  # 8 vCPU, 64 GB RAM
    accelerator: nvidia-tesla-t4  # Optional GPU
    min_nodes: 1
    max_nodes: 5
    autoscaling: true
    
  - name: preemptible-workers  # Cost optimization
    machine_type: n2-standard-4
    preemptible: true  # 60-80% cheaper
    min_nodes: 0
    max_nodes: 20
```

**Cloud SQL:**
```yaml
instance: meshml-db
tier: db-n1-highmem-4  # 4 vCPU, 26 GB RAM
database_version: POSTGRES_15
storage_type: SSD
storage_size: 100GB
storage_auto_increase: true
high_availability: true  # Multi-zone replication
backup:
  enabled: true
  start_time: "03:00"
  retention_days: 30
  point_in_time_recovery: true
```

**Memorystore (Redis):**
```yaml
instance: meshml-redis
tier: STANDARD_HA  # High availability with replicas
memory_size: 16GB
region: us-central1
replicas: 2
version: redis_7_0
```

**Cloud Storage:**
```yaml
buckets:
  - name: meshml-datasets
    location: US-CENTRAL1
    storage_class: STANDARD
    lifecycle:
      - action: DELETE
        condition: age_days > 90
    
  - name: meshml-models
    location: US-CENTRAL1
    storage_class: STANDARD
    
  - name: meshml-artifacts
    location: US-CENTRAL1
    storage_class: NEARLINE  # Cheaper for infrequent access
    lifecycle:
      - action: TRANSITION_TO_ARCHIVE
        condition: age_days > 180
```

**Load Balancer:**
```yaml
type: GLOBAL_EXTERNAL_HTTPS
ip_address: static  # Reserve: 34.xxx.xxx.xxx
ssl_policy: MODERN
ssl_certificates: managed  # Auto-renewal
domains:
  - meshml.university.edu
  - api.meshml.university.edu
```

### 4.2 Estimated Costs (Monthly)

**GKE:**
- Services node pool (3 × n2-standard-4): ~$300
- Parameter server (2 × n2-highmem-8): ~$400
- Total GKE: **~$700/month**

**Cloud SQL:**
- db-n1-highmem-4 HA: **~$450/month**

**Memorystore:**
- 16GB Standard HA: **~$200/month**

**Cloud Storage:**
- 1TB total (datasets + models): **~$20/month**

**Networking:**
- Egress (workers downloading): **~$50/month**

**Total Estimated Cost: ~$1,420/month** for supporting 100 concurrent users

**Cost per Student:** $14.20/month (for 100 students)  
**Cost per Training Job:** ~$0.10-$1.00 depending on size

---

## 5. Security & Access Control

### 5.1 Authentication

**User Authentication (JWT):**
```python
# Login endpoint
POST /api/v1/auth/login
{
  "email": "student@university.edu",
  "password": "...",
  "provider": "google"  # Optional: OAuth SSO
}

# Response
{
  "access_token": "eyJhbGciOiJIUzI1NiIs...",  # Valid 1 hour
  "refresh_token": "eyJhbGciOiJIUzI1NiIs...",  # Valid 30 days
  "user": {
    "id": "usr_abc123",
    "email": "student@university.edu",
    "name": "Student Name"
  }
}

# JWT payload
{
  "sub": "usr_abc123",  # User ID
  "email": "student@university.edu",
  "iat": 1709251200,  # Issued at
  "exp": 1709254800,  # Expires at
  "groups": ["grp_123", "grp_456"]  # User's groups
}
```

**Worker Authentication:**
```python
# Workers authenticate with user JWT
# Embedded in gRPC metadata

metadata = [
    ('authorization', f'Bearer {user_jwt_token}')
]

worker_stub.RegisterWorker(capabilities, metadata=metadata)

# Server validates JWT and extracts user_id
```

### 5.2 Authorization (RBAC)

**Group Roles:**
```python
PERMISSIONS = {
    "owner": {
        "delete_group": True,
        "manage_members": True,
        "manage_settings": True,
        "create_jobs": True,
        "view_jobs": True,
        "invite_members": True
    },
    "admin": {
        "delete_group": False,
        "manage_members": True,
        "manage_settings": False,
        "create_jobs": True,
        "view_jobs": True,
        "invite_members": True
    },
    "member": {
        "delete_group": False,
        "manage_members": False,
        "manage_settings": False,
        "create_jobs": True,
        "view_jobs": True,
        "invite_members": False
    }
}

# Permission check
def check_permission(user_id, group_id, action):
    member = db.get_group_member(user_id, group_id)
    if not member:
        raise PermissionDenied("Not a member of this group")
    
    return PERMISSIONS[member.role].get(action, False)
```

### 5.3 Data Access Control

**GCS Signed URLs:**
```python
# Workers request signed URL for batch download
# Valid for 1 hour only

def get_batch_download_url(batch_id, user_id):
    # 1. Verify user is in group that owns this batch
    batch = db.get_batch(batch_id)
    job = db.get_job(batch.job_id)
    
    if not user_in_group(user_id, job.group_id):
        raise PermissionDenied()
    
    # 2. Generate time-limited signed URL
    gcs_path = f'meshml-datasets/{batch.job_id}/batches/{batch_id}.tar.gz'
    url = gcs_client.generate_signed_url(
        gcs_path,
        expiration=3600,  # 1 hour
        method='GET'
    )
    
    return url
```

### 5.4 Network Security

**GKE Network Policies:**
```yaml
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
  # Only allow from load balancer
  - from:
    - namespaceSelector:
        matchLabels:
          name: kube-system
  egress:
  # Allow to Cloud SQL, Redis, GCS
  - to:
    - podSelector:
        matchLabels:
          app: cloud-sql-proxy
```

**TLS Encryption:**
- All external traffic: HTTPS (TLS 1.3)
- gRPC: TLS encryption
- PostgreSQL: SSL required
- Redis: TLS enabled

---

## 6. Custom Model System

### 6.1 Model File Contract

**Required Structure:**
```python
# user_model.py

import torch.nn as nn
from typing import Dict, Any

# 1. Model class (user-defined)
class MyModel(nn.Module):
    def __init__(self, **kwargs):
        super().__init__()
        # User's architecture
    
    def forward(self, x):
        # User's forward pass
        return x

# 2. REQUIRED: create_model function
def create_model(config: Dict[str, Any]) -> nn.Module:
    """
    MeshML calls this to instantiate the model.
    
    Args:
        config: Job configuration dict
    
    Returns:
        Model instance
    """
    return MyModel(num_classes=config.get('num_classes', 10))

# 3. REQUIRED: create_dataloader function
def create_dataloader(batch_path: str, config: Dict[str, Any]):
    """
    MeshML calls this to load data batches.
    
    Args:
        batch_path: Path to downloaded batch
        config: Job configuration dict
    
    Returns:
        PyTorch DataLoader
    """
    from torch.utils.data import DataLoader
    # User's data loading logic
    return DataLoader(...)

# 4. REQUIRED: MODEL_METADATA
MODEL_METADATA = {
    "name": str,              # Model name
    "description": str,       # Description
    "input_type": str,        # "image" | "text" | "tabular" | "audio"
    "output_type": str,       # "classification" | "regression" | "detection"
    "dataset_format": str,    # "imagefolder" | "coco" | "csv" | "json"
    "requirements": List[str] # Extra pip packages
}

# 5. OPTIONAL: create_loss_fn (default: CrossEntropyLoss)
def create_loss_fn(config: Dict[str, Any]):
    return nn.CrossEntropyLoss()

# 6. OPTIONAL: create_optimizer (default: Adam)
def create_optimizer(model: nn.Module, config: Dict[str, Any]):
    return torch.optim.Adam(model.parameters(), lr=config['learning_rate'])
```

### 6.2 Validation Process

**Server-Side Validation:**
```python
def validate_model_file(file_path: str) -> bool:
    # 1. Check Python syntax
    try:
        compile(open(file_path).read(), file_path, 'exec')
    except SyntaxError as e:
        raise ValidationError(f"Syntax error: {e}")
    
    # 2. Import and check required functions
    import importlib.util
    spec = importlib.util.spec_from_file_location("user_model", file_path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    
    required_attrs = ['create_model', 'create_dataloader', 'MODEL_METADATA']
    for attr in required_attrs:
        if not hasattr(module, attr):
            raise ValidationError(f"Missing required: {attr}")
    
    # 3. Validate MODEL_METADATA
    metadata = module.MODEL_METADATA
    required_fields = ['name', 'input_type', 'output_type', 'dataset_format']
    for field in required_fields:
        if field not in metadata:
            raise ValidationError(f"MODEL_METADATA missing: {field}")
    
    # 4. Test instantiation
    try:
        model = module.create_model({'num_classes': 10})
        assert isinstance(model, nn.Module)
    except Exception as e:
        raise ValidationError(f"create_model() failed: {e}")
    
    return True
```

---

## 7. Scalability & Performance

### 7.1 Horizontal Scaling

**Auto-Scaling Rules:**
```yaml
api-gateway:
  min_replicas: 3
  max_replicas: 10
  target_cpu_utilization: 70%

dataset-sharder:
  min_replicas: 2
  max_replicas: 5
  target_cpu_utilization: 80%

task-orchestrator:
  min_replicas: 2
  max_replicas: 5
  target_memory_utilization: 75%

parameter-server:
  min_replicas: 2
  max_replicas: 5
  custom_metric: gradients_per_second > 100
```

### 7.2 Performance Optimizations

**1. Gradient Compression:**
```python
# Reduce network bandwidth by 10-50×
def compress_gradients(gradients):
    # Quantization: float32 → int8
    quantized = {k: quantize(v, bits=8) for k, v in gradients.items()}
    
    # Sparsification: Send only top-k values
    sparse = {k: top_k(v, k=0.1) for k, v in quantized.items()}
    
    # Compression: gzip
    compressed = gzip.compress(pickle.dumps(sparse))
    
    return compressed
```

**2. Model Weight Caching:**
```python
# Cache in Redis (fast) + GCS (persistent)
def get_model_weights(job_id, epoch):
    cache_key = f'model:{job_id}:epoch_{epoch}'
    
    # Try Redis first (< 1ms)
    cached = redis.get(cache_key)
    if cached:
        return pickle.loads(cached)
    
    # Fall back to GCS (< 100ms)
    gcs_path = f'gs://meshml-models/{job_id}/checkpoints/epoch_{epoch}.pt'
    weights = gcs_client.download(gcs_path)
    
    # Populate cache
    redis.set(cache_key, pickle.dumps(weights), ex=3600)
    
    return weights
```

**3. Batch Prefetching:**
```python
# Workers download next batch while training current batch
def prefetch_batches(assigned_batches):
    current_batch = assigned_batches[0]
    next_batch = assigned_batches[1] if len(assigned_batches) > 1 else None
    
    # Start downloading next batch in background thread
    if next_batch:
        threading.Thread(
            target=download_batch,
            args=(next_batch,)
        ).start()
    
    return load_batch(current_batch)
```

### 7.3 Database Optimizations

**1. Connection Pooling:**
```python
# PostgreSQL connection pool
engine = create_engine(
    DATABASE_URL,
    pool_size=20,
    max_overflow=40,
    pool_pre_ping=True  # Verify connections
)
```

**2. Indexes (already covered in section 2.3.1)**

**3. TimescaleDB for Metrics:**
```sql
-- Hypertable automatically partitions by time
-- Queries on recent data are very fast
SELECT AVG(loss), AVG(accuracy)
FROM training_metrics
WHERE job_id = 'job_xyz789'
  AND time > NOW() - INTERVAL '5 minutes'
```

---

## 8. Failure Handling

### 8.1 Worker Failures

**Detection:**
```python
# Heartbeat-based detection
@celery.task(run_every=timedelta(seconds=30))
def check_worker_heartbeats():
    # Query workers that haven't sent heartbeat
    SELECT id FROM workers
    WHERE last_heartbeat < NOW() - INTERVAL '2 minutes'
      AND status IN ('idle', 'busy')
    
    for failed_worker in failed_workers:
        handle_worker_failure(failed_worker.id)
```

**Recovery:**
```python
def handle_worker_failure(worker_id):
    # 1. Mark worker as failed
    UPDATE workers SET status = 'failed' WHERE id = worker_id
    
    # 2. Find orphaned batches
    orphaned_batches = db.query(
        "SELECT * FROM data_batches WHERE worker_id = ? AND status IN ('assigned', 'processing')",
        worker_id
    )
    
    # 3. Reset batches for reassignment
    for batch in orphaned_batches:
        UPDATE data_batches
        SET worker_id = NULL, status = 'pending', retry_count = retry_count + 1
        WHERE id = batch.id
    
    # 4. Reassign to available workers
    reassign_orphaned_batches(orphaned_batches)
    
    # 5. Notify group
    notify_group(f"Worker {worker_id} failed. Batches reassigned.")
```

### 8.2 Service Failures

**Kubernetes Health Checks:**
```yaml
livenessProbe:
  httpGet:
    path: /health
    port: 8000
  initialDelaySeconds: 30
  periodSeconds: 10
  failureThreshold: 3

readinessProbe:
  httpGet:
    path: /ready
    port: 8000
  initialDelaySeconds: 10
  periodSeconds: 5
  failureThreshold: 2
```

**Auto-Restart:**
- Kubernetes automatically restarts failed pods
- GKE auto-scales if needed
- Cloud SQL has automatic failover (HA mode)

### 8.3 Data Corruption

**Checksums:**
```python
# Every batch has SHA256 checksum
def verify_batch_integrity(batch_path, expected_checksum):
    actual = hashlib.sha256(open(batch_path, 'rb').read()).hexdigest()
    if actual != expected_checksum:
        raise CorruptionError("Checksum mismatch!")
```

**Backup & Recovery:**
- Cloud SQL: Daily backups, 30-day retention
- GCS: Object versioning enabled
- Point-in-time recovery available

---

## 9. API Specifications

### 9.1 REST API Endpoints

**Authentication:**
```
POST   /api/v1/auth/login
POST   /api/v1/auth/register
POST   /api/v1/auth/refresh
POST   /api/v1/auth/logout
```

**Groups:**
```
POST   /api/v1/groups                    # Create group
GET    /api/v1/groups                    # List user's groups
GET    /api/v1/groups/{id}               # Get group details
PUT    /api/v1/groups/{id}               # Update group
DELETE /api/v1/groups/{id}               # Delete group
GET    /api/v1/groups/{id}/members       # List members
POST   /api/v1/groups/{id}/invitations   # Send invitations
GET    /api/v1/invitations/{id}          # Get invitation
POST   /api/v1/invitations/{id}/accept   # Accept invitation
POST   /api/v1/invitations/{id}/decline  # Decline invitation
```

**Jobs:**
```
POST   /api/v1/groups/{gid}/jobs              # Create job
GET    /api/v1/groups/{gid}/jobs              # List jobs
GET    /api/v1/jobs/{id}                      # Get job details
GET    /api/v1/jobs/{id}/status               # Get status
GET    /api/v1/jobs/{id}/metrics              # Get metrics
POST   /api/v1/jobs/{id}/stop                 # Stop job
DELETE /api/v1/jobs/{id}                      # Delete job
GET    /api/v1/jobs/{id}/download/model       # Download model
GET    /api/v1/jobs/{id}/download/report      # Download report
```

**Uploads:**
```
POST   /api/v1/uploads/model     # Upload custom model file
POST   /api/v1/uploads/dataset   # Upload dataset
```

### 9.2 gRPC Service Definitions

**TaskOrchestrator.proto:**
```protobuf
service TaskOrchestrator {
  rpc RegisterWorker(WorkerCapabilities) returns (WorkerRegistration);
  rpc SendHeartbeat(Heartbeat) returns (HeartbeatAck);
  rpc ReportBatchComplete(BatchCompletion) returns (BatchAck);
}

message WorkerCapabilities {
  string user_id = 1;
  string os = 2;
  string arch = 3;
  int32 cpu_cores = 4;
  int64 ram_bytes = 5;
  repeated GPU gpus = 6;
  map<string, string> frameworks = 7;
}

message WorkerRegistration {
  string worker_id = 1;
  repeated string groups = 2;
}
```

**ParameterServer.proto:**
```protobuf
service ParameterServer {
  rpc GetWeights(WeightsRequest) returns (WeightsResponse);
  rpc UpdateGradients(GradientsUpdate) returns (GradientsAck);
}

message WeightsRequest {
  string job_id = 1;
  int32 epoch = 2;
}

message WeightsResponse {
  bytes model_state_dict = 1;  # Serialized PyTorch weights
  int32 version = 2;
}
```

### 9.3 GraphQL Schema

```graphql
type Query {
  me: User!
  group(id: ID!): Group
  myGroups: [Group!]!
  job(id: ID!): Job
}

type Mutation {
  createGroup(input: CreateGroupInput!): Group!
  inviteMembers(groupId: ID!, emails: [String!]!): [Invitation!]!
  acceptInvitation(invitationId: ID!): GroupMember!
  createJob(input: CreateJobInput!): Job!
  stopJob(jobId: ID!): Job!
}

type Subscription {
  jobMetrics(jobId: ID!): JobMetrics!
  workerStatus(jobId: ID!): [WorkerStatus!]!
  groupNotifications(groupId: ID!): Notification!
}
```

---

## 10. Deployment Guide

### 10.1 Prerequisites

```bash
# Install gcloud CLI
curl https://sdk.cloud.google.com | bash

# Authenticate
gcloud auth login

# Set project
gcloud config set project meshml-production
```

### 10.2 Infrastructure Setup

```bash
# 1. Enable APIs
gcloud services enable \
    container.googleapis.com \
    sqladmin.googleapis.com \
    redis.googleapis.com \
    storage.googleapis.com

# 2. Create GKE cluster
gcloud container clusters create meshml-production \
    --region us-central1 \
    --num-nodes 3 \
    --machine-type n2-standard-4 \
    --enable-autoscaling \
    --min-nodes 2 \
    --max-nodes 10

# 3. Create Cloud SQL
gcloud sql instances create meshml-db \
    --database-version POSTGRES_15 \
    --tier db-n1-highmem-4 \
    --region us-central1

# 4. Create Redis
gcloud redis instances create meshml-redis \
    --size 16 \
    --region us-central1 \
    --tier standard

# 5. Create GCS buckets
gsutil mb -c STANDARD -l US-CENTRAL1 gs://meshml-datasets
gsutil mb -c STANDARD -l US-CENTRAL1 gs://meshml-models
gsutil mb -c NEARLINE -l US-CENTRAL1 gs://meshml-artifacts
```

### 10.3 Deploy Services

```bash
# Get cluster credentials
gcloud container clusters get-credentials meshml-production --region us-central1

# Deploy Kubernetes manifests
kubectl apply -f infrastructure/kubernetes/namespaces.yaml
kubectl apply -f infrastructure/kubernetes/secrets.yaml
kubectl apply -f infrastructure/kubernetes/configmaps.yaml
kubectl apply -f infrastructure/kubernetes/services/
kubectl apply -f infrastructure/kubernetes/deployments/
kubectl apply -f infrastructure/kubernetes/ingress.yaml

# Verify deployments
kubectl get pods -n meshml
kubectl get services -n meshml
```

### 10.4 Configure DNS

```bash
# Get load balancer IP
kubectl get ingress -n meshml

# Add DNS records at your provider:
# A record: meshml.university.edu → [LB_IP]
# A record: api.meshml.university.edu → [LB_IP]
```

---

## 11. Model & Dataset Validation

### 11.1 Upload Validation Flow

**Before accepting any job, validate both model and dataset:**

```python
# API Gateway validation endpoint
@app.post("/api/v1/jobs/validate")
async def validate_job(model_file: UploadFile, dataset_info: DatasetInfo):
    """
    Validate model and dataset before job creation.
    Returns validation report or errors.
    """
    
    # 1. Model Validation
    model_validation = validate_model_file(model_file)
    if not model_validation.is_valid:
        raise HTTPException(400, detail=model_validation.errors)
    
    # 2. Dataset Validation  
    dataset_validation = validate_dataset(dataset_info)
    if not dataset_validation.is_valid:
        raise HTTPException(400, detail=dataset_validation.errors)
    
    return {
        "valid": True,
        "model_metadata": model_validation.metadata,
        "dataset_info": dataset_validation.info
    }
```

### 11.2 Model Validation

**Simple validation without complex sandboxing:**

```python
def validate_model_file(file_path: str) -> ValidationResult:
    """
    Validate uploaded model Python file.
    
    Checks:
    1. Python syntax is valid
    2. Required functions exist
    3. MODEL_METADATA is present
    4. Can instantiate model (no execution)
    5. File size < 10MB
    """
    
    # Size check
    if os.path.getsize(file_path) > 10 * 1024 * 1024:
        return ValidationResult(False, ["File too large (max 10MB)"])
    
    # Syntax check
    try:
        with open(file_path) as f:
            compile(f.read(), file_path, 'exec')
    except SyntaxError as e:
        return ValidationResult(False, [f"Syntax error: {e}"])
    
    # Import and check structure
    spec = importlib.util.spec_from_file_location("user_model", file_path)
    module = importlib.util.module_from_spec(spec)
    
    try:
        spec.loader.exec_module(module)
    except Exception as e:
        return ValidationResult(False, [f"Import error: {e}"])
    
    # Check required components
    errors = []
    if not hasattr(module, 'create_model'):
        errors.append("Missing create_model() function")
    if not hasattr(module, 'create_dataloader'):
        errors.append("Missing create_dataloader() function")
    if not hasattr(module, 'MODEL_METADATA'):
        errors.append("Missing MODEL_METADATA dict")
    
    if errors:
        return ValidationResult(False, errors)
    
    # Validate MODEL_METADATA structure
    metadata = module.MODEL_METADATA
    required_keys = ['name', 'input_type', 'output_type', 'dataset_format']
    for key in required_keys:
        if key not in metadata:
            errors.append(f"MODEL_METADATA missing '{key}'")
    
    if errors:
        return ValidationResult(False, errors)
    
    # Try to instantiate model (with timeout)
    try:
        with timeout(seconds=10):
            test_config = {'num_classes': 10, 'input_size': 28}
            model = module.create_model(test_config)
            
            # Check it's a PyTorch model
            if not isinstance(model, nn.Module):
                return ValidationResult(False, ["create_model() must return nn.Module"])
    
    except TimeoutError:
        return ValidationResult(False, ["Model instantiation timeout (>10s)"])
    except Exception as e:
        return ValidationResult(False, [f"Model instantiation failed: {e}"])
    
    return ValidationResult(True, [], metadata)
```

### 11.3 Dataset Validation

**Validate dataset before sharding:**

```python
def validate_dataset(dataset_path: str, format: str) -> ValidationResult:
    """
    Validate dataset structure and content.
    
    Supports:
    - ImageFolder (class directories)
    - COCO JSON
    - CSV files
    """
    
    if format == "imagefolder":
        return validate_imagefolder(dataset_path)
    elif format == "coco":
        return validate_coco(dataset_path)
    elif format == "csv":
        return validate_csv(dataset_path)
    else:
        return ValidationResult(False, [f"Unsupported format: {format}"])


def validate_imagefolder(path: str) -> ValidationResult:
    """
    Validate ImageFolder structure.
    
    Expected:
    dataset/
      ├── class1/
      │   ├── img1.jpg
      │   └── img2.jpg
      └── class2/
          └── img3.jpg
    """
    
    if not os.path.isdir(path):
        return ValidationResult(False, ["Path is not a directory"])
    
    # Check for class directories
    class_dirs = [d for d in os.listdir(path) 
                  if os.path.isdir(os.path.join(path, d))]
    
    if len(class_dirs) < 2:
        return ValidationResult(False, ["Need at least 2 class directories"])
    
    # Check each class has images
    total_images = 0
    for class_dir in class_dirs:
        class_path = os.path.join(path, class_dir)
        images = [f for f in os.listdir(class_path) 
                  if f.lower().endswith(('.jpg', '.jpeg', '.png'))]
        
        if len(images) == 0:
            return ValidationResult(False, [f"Class '{class_dir}' has no images"])
        
        total_images += len(images)
    
    if total_images < 100:
        return ValidationResult(False, ["Need at least 100 images total"])
    
    return ValidationResult(True, [], {
        'num_classes': len(class_dirs),
        'total_images': total_images,
        'classes': class_dirs
    })


def validate_coco(json_path: str) -> ValidationResult:
    """Validate COCO JSON format."""
    
    try:
        with open(json_path) as f:
            data = json.load(f)
    except Exception as e:
        return ValidationResult(False, [f"Invalid JSON: {e}"])
    
    # Check required keys
    required = ['images', 'annotations', 'categories']
    for key in required:
        if key not in data:
            return ValidationResult(False, [f"Missing '{key}' in COCO JSON"])
    
    if len(data['images']) == 0:
        return ValidationResult(False, ["No images in dataset"])
    
    return ValidationResult(True, [], {
        'num_images': len(data['images']),
        'num_annotations': len(data['annotations']),
        'num_categories': len(data['categories'])
    })
```

---

## 12. Model Registry

### 12.1 Model Storage Architecture

**Simple two-tier system:**

1. **GCS (Google Cloud Storage)** - Actual model files
2. **PostgreSQL** - Model metadata

```sql
CREATE TABLE models (
    id UUID PRIMARY KEY,
    user_id UUID REFERENCES users(id),
    name VARCHAR(255) NOT NULL,
    description TEXT,
    file_path TEXT NOT NULL,  -- GCS path: gs://meshml-models/{model_id}/model.py
    file_size_bytes BIGINT,
    checksum VARCHAR(128),  -- SHA256
    
    -- Metadata from MODEL_METADATA
    input_type VARCHAR(50),  -- image, text, tabular
    output_type VARCHAR(50),  -- classification, regression
    dataset_format VARCHAR(50),  -- imagefolder, coco, csv
    
    -- Lifecycle
    status VARCHAR(50) DEFAULT 'uploading',  -- uploading, validating, ready, failed, deprecated
    validation_errors JSONB,
    
    -- Versioning (simple)
    version INT DEFAULT 1,
    parent_model_id UUID REFERENCES models(id),  -- For tracking iterations
    
    -- Timestamps
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW(),
    validated_at TIMESTAMP,
    
    -- Usage tracking
    jobs_created INT DEFAULT 0,
    total_training_hours DECIMAL DEFAULT 0
);

CREATE INDEX idx_models_user ON models(user_id);
CREATE INDEX idx_models_status ON models(status);
CREATE INDEX idx_models_parent ON models(parent_model_id);
```

### 12.2 Model Lifecycle

```
┌─────────────┐
│  Uploading  │ ← User uploads model.py file
└──────┬──────┘
       │
       ↓ File saved to GCS
┌──────────────┐
│  Validating  │ ← Run validation checks
└──────┬───┬───┘
       │   │
  ✅   │   │  ❌
       ↓   ↓
┌─────────┐  ┌────────┐
│  Ready  │  │ Failed │
└────┬────┘  └────────┘
     │
     ↓ Used in jobs
┌──────────┐
│  Active  │
└────┬─────┘
     │
     ↓ User creates new version
┌────────────┐
│ Deprecated │ ← Old version still accessible but not recommended
└────────────┘
```

### 12.3 Model API Endpoints

```python
# Upload model
POST /api/v1/models
Content-Type: multipart/form-data
{
  "file": <model.py>,
  "name": "My CNN",
  "description": "Custom CNN for MNIST"
}

Response:
{
  "model_id": "mdl_abc123",
  "status": "validating",
  "validation_eta_seconds": 30
}

# Check validation status
GET /api/v1/models/{model_id}/validation

Response:
{
  "status": "ready",
  "validation_results": {
    "syntax_check": "✅ Pass",
    "structure_check": "✅ Pass",
    "instantiation_test": "✅ Pass"
  }
}

# List user's models
GET /api/v1/models?user_id={user_id}

Response:
{
  "models": [
    {
      "id": "mdl_abc123",
      "name": "My CNN",
      "status": "ready",
      "version": 2,
      "created_at": "2026-03-01T10:00:00Z",
      "jobs_created": 5
    }
  ]
}
```

---

## 13. Testing Strategy (Student-Friendly)

### 13.1 Testing Pyramid

```
           ┌────────────┐
           │   Manual   │  ← Demo testing (5%)
           │    E2E     │
           ├────────────┤
           │ Integration│  ← API tests (25%)
           │   Tests    │
           ├────────────┤
           │    Unit    │  ← Function tests (70%)
           │   Tests    │
           └────────────┘
```

### 13.2 Unit Tests (70% effort)

**Test individual functions in isolation:**

```python
# services/api-gateway/tests/test_validation.py
import pytest
from app.validation import validate_model_file

def test_validate_model_with_missing_function():
    """Test model validation fails when create_model is missing."""
    
    # Create temp file without create_model()
    with tempfile.NamedTemporaryFile(mode='w', suffix='.py', delete=False) as f:
        f.write("""
import torch.nn as nn

MODEL_METADATA = {
    'name': 'Test Model',
    'input_type': 'image'
}

def create_dataloader(path, config):
    pass
""")
        temp_path = f.name
    
    result = validate_model_file(temp_path)
    
    assert result.is_valid == False
    assert "Missing create_model()" in result.errors
    
    os.unlink(temp_path)


def test_validate_model_success():
    """Test model validation passes with correct structure."""
    
    with tempfile.NamedTemporaryFile(mode='w', suffix='.py', delete=False) as f:
        f.write("""
import torch.nn as nn

class MyModel(nn.Module):
    def __init__(self):
        super().__init__()
        self.fc = nn.Linear(10, 10)
    
    def forward(self, x):
        return self.fc(x)

def create_model(config):
    return MyModel()

def create_dataloader(path, config):
    pass

MODEL_METADATA = {
    'name': 'Test',
    'input_type': 'image',
    'output_type': 'classification',
    'dataset_format': 'imagefolder'
}
""")
        temp_path = f.name
    
    result = validate_model_file(temp_path)
    
    assert result.is_valid == True
    assert result.metadata['name'] == 'Test'
    
    os.unlink(temp_path)
```

**Run tests:**
```bash
# In each service directory
cd services/api-gateway
pytest tests/ -v --cov=app --cov-report=html

# Check coverage report
open htmlcov/index.html
```

### 13.3 Integration Tests (25% effort)

**Test services working together:**

```python
# services/api-gateway/tests/integration/test_job_creation.py
import pytest
from fastapi.testclient import TestClient
from app.main import app

@pytest.fixture
def client():
    return TestClient(app)

@pytest.fixture
def test_db():
    """Set up test database."""
    # Use separate test database
    pass

def test_create_job_end_to_end(client, test_db):
    """Test complete job creation flow."""
    
    # 1. Register user
    response = client.post("/api/v1/auth/register", json={
        "email": "test@example.com",
        "password": "testpass123"
    })
    assert response.status_code == 200
    token = response.json()['access_token']
    
    # 2. Create group
    response = client.post(
        "/api/v1/groups",
        json={"name": "Test Group"},
        headers={"Authorization": f"Bearer {token}"}
    )
    group_id = response.json()['group_id']
    
    # 3. Upload model
    with open("tests/fixtures/valid_model.py", "rb") as f:
        response = client.post(
            "/api/v1/models",
            files={"file": f},
            data={"name": "Test Model"},
            headers={"Authorization": f"Bearer {token}"}
        )
    model_id = response.json()['model_id']
    
    # 4. Create job
    response = client.post(
        f"/api/v1/groups/{group_id}/jobs",
        json={
            "name": "Test Job",
            "model_id": model_id,
            "dataset_url": "gs://test/dataset",
            "config": {"epochs": 5}
        },
        headers={"Authorization": f"Bearer {token}"}
    )
    
    assert response.status_code == 200
    job = response.json()
    assert job['status'] == 'pending'
```

### 13.4 Manual E2E Testing (5% effort)

**For student demo - test with real devices:**

```bash
# Test Checklist for Demo

□ 1. Start all services
   docker-compose up -d
   
□ 2. Register 3 test users (Alice, Bob, Charlie)
   curl -X POST http://localhost:8000/api/v1/auth/register ...
   
□ 3. Alice creates group "ML Class Demo"
   
□ 4. Alice invites Bob and Charlie
   
□ 5. Start workers on 3 different machines:
   - Alice's MacBook (Python worker)
   - Bob's Windows laptop (Python worker)  
   - Charlie's phone browser (JS worker)
   
□ 6. Alice uploads MNIST dataset (verify validation)
   
□ 7. Alice uploads CNN model (verify validation)
   
□ 8. Alice creates training job
   
□ 9. Verify Task Orchestrator assigns batches to 3 workers
   
□ 10. Monitor dashboard - watch real-time training metrics
   
□ 11. Training completes - verify accuracy ~96%
   
□ 12. Download final model
   
□ 13. Test with sample image

✅ Demo successful if training completes in <10 minutes
```

### 13.5 Test Coverage Goals

**Realistic for student project:**

```
Component              | Target Coverage | Priority
-----------------------|-----------------|----------
API Gateway            | 70%             | High
Dataset Sharder        | 60%             | Medium
Task Orchestrator      | 65%             | High
Parameter Server       | 75%             | Critical
Metrics Service        | 50%             | Low
Model Registry         | 60%             | Medium
Workers (Python)       | 65%             | High
Workers (C++)          | 40%             | Low
Workers (JavaScript)   | 40%             | Low
Dashboard              | 30%             | Low (manual testing)
```

---

## 14. Secrets Management (Simple Approach)

### 14.1 Local Development

**Use `.env` files (NOT committed to git):**

```bash
# .env.local (in root directory)
# DO NOT COMMIT THIS FILE

# Database
DATABASE_URL=postgresql://meshml_user:meshml_dev_password@localhost:5432/meshml
REDIS_URL=redis://:meshml_redis_password@localhost:6379/0

# MinIO (S3-compatible)
MINIO_ENDPOINT=localhost:9000
MINIO_ACCESS_KEY=minioadmin
MINIO_SECRET_KEY=minioadmin123

# JWT
JWT_SECRET_KEY=dev-secret-change-in-production-1234567890
JWT_ALGORITHM=HS256
JWT_EXPIRATION_MINUTES=60

# API Keys (for production features, optional for student project)
SENDGRID_API_KEY=optional
TWILIO_API_KEY=optional
```

**Load in services:**

```python
# services/api-gateway/app/config.py
from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    database_url: str
    redis_url: str
    jwt_secret_key: str
    jwt_algorithm: str = "HS256"
    jwt_expiration_minutes: int = 60
    
    class Config:
        env_file = ".env.local"
        env_file_encoding = 'utf-8'

settings = Settings()
```

### 14.2 Production Deployment (GCP)

**Use environment variables in Kubernetes:**

```yaml
# infrastructure/kubernetes/deployments/api-gateway.yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: api-gateway
spec:
  template:
    spec:
      containers:
      - name: api-gateway
        image: gcr.io/meshml/api-gateway:latest
        env:
        - name: DATABASE_URL
          valueFrom:
            secretKeyRef:
              name: meshml-secrets
              key: database-url
        - name: JWT_SECRET_KEY
          valueFrom:
            secretKeyRef:
              name: meshml-secrets
              key: jwt-secret
```

**Create secrets:**

```bash
# Create Kubernetes secret (one-time)
kubectl create secret generic meshml-secrets \
  --from-literal=database-url='postgresql://user:pass@cloud-sql-proxy:5432/meshml' \
  --from-literal=jwt-secret='CHANGE-THIS-TO-RANDOM-STRING' \
  --from-literal=redis-url='redis://:password@memorystore-ip:6379/0'
```

### 14.3 Secret Generation

**Generate secure secrets:**

```python
# scripts/generate_secrets.py
import secrets
import base64

def generate_jwt_secret():
    """Generate 256-bit secret for JWT."""
    return base64.b64encode(secrets.token_bytes(32)).decode()

def generate_api_key():
    """Generate API key for services."""
    return secrets.token_urlsafe(32)

if __name__ == "__main__":
    print("JWT_SECRET_KEY=" + generate_jwt_secret())
    print("API_KEY=" + generate_api_key())
```

```bash
# Run once before deployment
python scripts/generate_secrets.py

# Output:
# JWT_SECRET_KEY=h8K9mN3pQ5sT7vX2zA4cF6gJ9lM2oR5tY8wB1dE4hI7k=
# API_KEY=xK9mP3qS6tV9yB2dF5hJ8lN1oQ4rU7wZ0cE3gI6k
```

---

## 15. Deployment Strategy (Student-Friendly)

### 15.1 Local Development Deployment

**Simple Docker Compose (what you're using now):**

```bash
# Start everything
cd infrastructure/docker
docker-compose up -d

# Check status
docker-compose ps

# View logs
docker-compose logs -f api-gateway

# Stop everything
docker-compose down

# Reset (delete data)
docker-compose down -v
```

### 15.2 Production Deployment (Simplified)

**No blue-green, no canary - just simple rolling update:**

```bash
# 1. Build new Docker images
docker build -t gcr.io/meshml/api-gateway:v1.1 services/api-gateway/
docker build -t gcr.io/meshml/task-orchestrator:v1.1 services/task-orchestrator/
# ... for each service

# 2. Push to Google Container Registry
docker push gcr.io/meshml/api-gateway:v1.1
docker push gcr.io/meshml/task-orchestrator:v1.1

# 3. Update Kubernetes deployments
kubectl set image deployment/api-gateway api-gateway=gcr.io/meshml/api-gateway:v1.1
kubectl set image deployment/task-orchestrator task-orchestrator=gcr.io/meshml/task-orchestrator:v1.1

# 4. Watch rollout
kubectl rollout status deployment/api-gateway

# 5. If something breaks, rollback
kubectl rollout undo deployment/api-gateway
```

### 15.3 Deployment Checklist

**Before deploying to production:**

```
□ 1. All tests passing
   pytest services/*/tests/ -v
   
□ 2. Database migrations ready
   cd database/migrations
   alembic upgrade head
   
□ 3. Secrets configured
   kubectl get secret meshml-secrets
   
□ 4. Build all images
   make build-all
   
□ 5. Push to registry
   make push-all
   
□ 6. Apply Kubernetes configs
   kubectl apply -f infrastructure/kubernetes/
   
□ 7. Verify pods running
   kubectl get pods -n meshml
   
□ 8. Check logs for errors
   kubectl logs -f deployment/api-gateway -n meshml
   
□ 9. Test health endpoints
   curl https://api.meshml.edu/health
   
□ 10. Run smoke tests
   pytest tests/smoke/ --env=production
```

### 15.4 Simple CI/CD (GitHub Actions)

```yaml
# .github/workflows/deploy.yml
name: Deploy to Production

on:
  push:
    branches: [main]

jobs:
  deploy:
    runs-on: ubuntu-latest
    steps:
    - uses: actions/checkout@v3
    
    - name: Run tests
      run: |
        pip install pytest
        pytest services/*/tests/ -v
    
    - name: Build Docker images
      run: |
        docker build -t gcr.io/meshml/api-gateway:${{ github.sha }} services/api-gateway/
    
    - name: Push to GCR
      run: |
        echo ${{ secrets.GCP_SA_KEY }} | docker login -u _json_key --password-stdin https://gcr.io
        docker push gcr.io/meshml/api-gateway:${{ github.sha }}
    
    - name: Deploy to GKE
      run: |
        kubectl set image deployment/api-gateway api-gateway=gcr.io/meshml/api-gateway:${{ github.sha }}
```

---

## Summary

This architecture provides:

✅ **Complete distributed ML training** on heterogeneous devices  
✅ **Cloud-native** with Google Cloud Platform  
✅ **Group-based collaboration** with RBAC  
✅ **Custom model support** via Python file upload  
✅ **Model & dataset validation** before job acceptance  
✅ **Simple model registry** with versioning  
✅ **Cross-platform workers** (Python, C++, JavaScript)  
✅ **Real-time monitoring** via WebSocket  
✅ **Fault tolerance** with automatic recovery  
✅ **Scalability** with auto-scaling services  
✅ **Security** with JWT, TLS, signed URLs  
✅ **Testing strategy** (unit, integration, manual E2E)  
✅ **Simple secrets management** (env files + K8s secrets)  
✅ **Straightforward deployment** (Docker Compose + K8s rolling updates)

**Status:** Architecture is **complete and ready** for Phase 1 implementation.

**Next Steps:**
1. Implement database schema (PostgreSQL tables with model registry)
2. Set up Redis data structures
3. Create database access layer (DAL)
4. Begin API Gateway with validation endpoints

---

**End of Architecture Specification**
