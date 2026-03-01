# MeshML Data Flow Diagrams

**Last Updated:** March 1, 2026

Visual diagrams showing how data flows through the MeshML system across heterogeneous devices.

---

## 1. Complete System Overview

```
┌─────────────────────────────────────────────────────────────────────┐
│                         INSTRUCTOR/ADMIN                            │
│                                                                     │
│  ┌──────────────────────────────────────────────────────────────┐  │
│  │  Dashboard (React)                                           │  │
│  │  • Upload datasets                                           │  │
│  │  • Create training jobs                                      │  │
│  │  • Monitor progress                                          │  │
│  └──────────────────────┬───────────────────────────────────────┘  │
└─────────────────────────┼───────────────────────────────────────────┘
                          │ HTTP/GraphQL
                          ↓
┌─────────────────────────────────────────────────────────────────────┐
│                   CENTRAL SERVICES (Docker)                         │
│                                                                     │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────────────────┐ │
│  │ API Gateway  │  │   Dataset    │  │   Task Orchestrator      │ │
│  │   (FastAPI)  │─▶│   Sharder    │─▶│   (Celery)              │ │
│  └──────────────┘  └──────────────┘  └──────────┬───────────────┘ │
│         │                  │                     │                 │
│         │                  ↓                     ↓                 │
│         │           ┌──────────────┐      ┌─────────────────────┐ │
│         │           │    MinIO     │      │  Parameter Server   │ │
│         │           │ (S3 Storage) │      │    (PyTorch)        │ │
│         │           └──────────────┘      └─────────────────────┘ │
│         │                                          │               │
│         ↓                                          │               │
│  ┌─────────────────────────────────────────────┐  │               │
│  │  PostgreSQL + Redis                         │  │               │
│  │  • Jobs, workers, batches metadata          │  │               │
│  │  • Model weights cache                      │  │               │
│  └─────────────────────────────────────────────┘  │               │
│                                                    │               │
└────────────────────────────────────────────────────┼───────────────┘
                          │                         │
                          │ gRPC                    │ gRPC
                          ↓                         ↓
┌─────────────────────────────────────────────────────────────────────┐
│                           WORKERS                                   │
│                                                                     │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐  ┌───────────┐ │
│  │   Python    │  │     C++     │  │  JavaScript │  │  Python   │ │
│  │   Worker    │  │   Worker    │  │   Worker    │  │  Worker   │ │
│  │             │  │             │  │  (Browser)  │  │           │ │
│  │  macOS      │  │  Windows    │  │  Android    │  │  Linux    │ │
│  │  M2 GPU     │  │  RTX 3080   │  │  WebGPU     │  │  CPU Only │ │
│  └─────────────┘  └─────────────┘  └─────────────┘  └───────────┘ │
│        │                 │                 │               │       │
│        └─────────────────┴─────────────────┴───────────────┘       │
│                          │                                         │
│                          ↓ Fetch batches from MinIO                │
│                   http://minio:9000/datasets/...                   │
└─────────────────────────────────────────────────────────────────────┘
```

---

## 2. Dataset Upload & Sharding Flow

```
┌───────────────────┐
│  User uploads     │
│  dataset via      │
│  Dashboard        │
│  (10GB CIFAR-100) │
└─────────┬─────────┘
          │ POST /api/v1/datasets
          ↓
┌─────────────────────────────────────────────────────────────┐
│  API Gateway                                                 │
│  • Validates authentication                                 │
│  • Creates temporary upload directory                       │
│  • Streams multipart upload                                 │
└─────────┬───────────────────────────────────────────────────┘
          │
          ↓
┌─────────────────────────────────────────────────────────────┐
│  Dataset Sharder Service                                     │
│                                                              │
│  Step 1: Validate Format                                    │
│  ┌────────────────────────────────────────────────────┐    │
│  │ Check structure:                                   │    │
│  │ ├── train/                                         │    │
│  │ │   ├── class1/ (1000 images)                     │    │
│  │ │   ├── class2/ (1000 images)                     │    │
│  │ │   └── ...                                        │    │
│  │ └── test/                                          │    │
│  └────────────────────────────────────────────────────┘    │
│                                                              │
│  Step 2: Calculate Sharding Strategy                        │
│  ┌────────────────────────────────────────────────────┐    │
│  │ Total samples: 50,000                              │    │
│  │ Target batch size: 500 samples                     │    │
│  │ Number of batches: 100                             │    │
│  │ Each batch: ~100MB compressed                      │    │
│  └────────────────────────────────────────────────────┘    │
│                                                              │
│  Step 3: Create Batches                                     │
│  ┌────────────────────────────────────────────────────┐    │
│  │ For each batch:                                    │    │
│  │   1. Select 500 random samples                     │    │
│  │   2. Create tar.gz archive                         │    │
│  │   3. Compute SHA256 checksum                       │    │
│  │   4. Upload to MinIO                               │    │
│  │   5. Store metadata in PostgreSQL                  │    │
│  └────────────────────────────────────────────────────┘    │
└─────────┬───────────────────────────────────────────────────┘
          │
          ↓
┌─────────────────────────────────────────────────────────────┐
│  MinIO (S3-Compatible Storage)                               │
│                                                              │
│  /datasets/job_abc123/                                       │
│    ├── batch_001.tar.gz (100MB)                             │
│    ├── batch_002.tar.gz (100MB)                             │
│    ├── batch_003.tar.gz (100MB)                             │
│    ├── ...                                                   │
│    └── batch_100.tar.gz (100MB)                             │
│                                                              │
│  /models/job_abc123/                                         │
│    └── initial_weights.pt                                    │
└──────────────────────────────────────────────────────────────┘
          │
          ↓
┌─────────────────────────────────────────────────────────────┐
│  PostgreSQL - data_batches table                             │
│                                                              │
│  ┌──────┬──────────┬────────┬────────┬──────────────────┐  │
│  │ id   │ job_id   │batch_id│ status │ download_url     │  │
│  ├──────┼──────────┼────────┼────────┼──────────────────┤  │
│  │ 1    │ abc123   │ 001    │pending │ s3://...001.tar  │  │
│  │ 2    │ abc123   │ 002    │pending │ s3://...002.tar  │  │
│  │ ...  │ ...      │ ...    │ ...    │ ...              │  │
│  └──────┴──────────┴────────┴────────┴──────────────────┘  │
└──────────────────────────────────────────────────────────────┘
```

---

## 3. Worker Registration & Task Assignment

```
┌─────────────────────────────────────────────────────────────────────┐
│  WORKER LIFECYCLE                                                   │
└─────────────────────────────────────────────────────────────────────┘

Step 1: Worker Starts
━━━━━━━━━━━━━━━━━━━━━
┌──────────────────┐
│  Student Laptop  │
│  (macOS M2)      │
│                  │
│  $ python worker.py --server http://server:8000 --token ABC123
└─────────┬────────┘
          │
          ↓
┌─────────────────────────────────────────────────────────────┐
│  Worker Initialization                                       │
│  1. Detect hardware capabilities                            │
│  2. Check installed frameworks                              │
│  3. Test GPU availability                                   │
│  4. Generate capabilities report                            │
└─────────┬───────────────────────────────────────────────────┘
          │
          ↓ gRPC: RegisterWorker(capabilities)
┌─────────────────────────────────────────────────────────────┐
│  Task Orchestrator - Worker Registry                         │
│                                                              │
│  Receives:                                                   │
│  {                                                           │
│    "worker_type": "python",                                 │
│    "os": "darwin",                                          │
│    "os_version": "14.2",                                    │
│    "arch": "arm64",                                         │
│    "frameworks": {"pytorch": "2.2.0"},                      │
│    "cpu_cores": 8,                                          │
│    "ram_bytes": 17179869184,  # 16GB                        │
│    "gpus": [{                                               │
│      "name": "Apple M2",                                    │
│      "type": "metal",                                       │
│      "memory_bytes": 8589934592  # 8GB                      │
│    }],                                                       │
│    "supported_ops": ["training", "inference"]               │
│  }                                                           │
│                                                              │
│  Orchestrator assigns worker_id: "worker_001"               │
└─────────┬───────────────────────────────────────────────────┘
          │
          ↓
┌─────────────────────────────────────────────────────────────┐
│  PostgreSQL - workers table                                  │
│                                                              │
│  INSERT worker:                                              │
│  • worker_id: worker_001                                    │
│  • type: python                                             │
│  • status: idle                                             │
│  • capabilities: {json}                                     │
│  • last_heartbeat: 2026-03-01 10:30:00                      │
└─────────┬───────────────────────────────────────────────────┘
          │
          ↓
┌─────────────────────────────────────────────────────────────┐
│  Redis - worker pool                                         │
│                                                              │
│  ZADD workers:idle worker_001 <timestamp>                   │
│  SET worker:worker_001:status "idle"                        │
│  SETEX worker:worker_001:heartbeat 60 "alive"  # TTL: 60s  │
└──────────────────────────────────────────────────────────────┘


Step 2: Task Assignment
━━━━━━━━━━━━━━━━━━━━━━
┌─────────────────────────────────────────────────────────────┐
│  Job Created by Instructor                                   │
│  • 100 batches need processing                              │
│  • 20 workers available                                     │
└─────────┬───────────────────────────────────────────────────┘
          │
          ↓
┌─────────────────────────────────────────────────────────────┐
│  Task Orchestrator - Assignment Logic                        │
│                                                              │
│  FOR each idle worker:                                       │
│    1. Check compatibility (GPU needed? Framework?)          │
│    2. Estimate processing speed based on past performance   │
│    3. Assign appropriate number of batches                  │
│                                                              │
│  Assignment Strategy:                                        │
│  • M2 GPU workers (10): 7 batches each (70 total)          │
│  • RTX 3080 workers (5): 4 batches each (20 total)         │
│  • CPU-only workers (5): 2 batches each (10 total)         │
└─────────┬───────────────────────────────────────────────────┘
          │
          ↓ gRPC: AssignTask(worker_001, batches)
┌─────────────────────────────────────────────────────────────┐
│  Worker Receives Task Assignment                             │
│                                                              │
│  {                                                           │
│    "job_id": "job_abc123",                                  │
│    "assigned_batches": [                                    │
│      {                                                       │
│        "batch_id": "batch_001",                             │
│        "download_url": "http://minio:9000/.../001.tar.gz", │
│        "checksum": "sha256:abc123...",                      │
│        "size_bytes": 104857600                              │
│      },                                                      │
│      ... (6 more batches)                                   │
│    ],                                                        │
│    "model_url": "http://minio:9000/.../initial.pt",        │
│    "training_config": {                                     │
│      "epochs": 5,                                           │
│      "learning_rate": 0.001,                                │
│      "batch_size": 64                                       │
│    }                                                         │
│  }                                                           │
└──────────────────────────────────────────────────────────────┘
```

---

## 4. Training Loop Data Flow

```
┌─────────────────────────────────────────────────────────────────────┐
│  SINGLE WORKER TRAINING ITERATION                                   │
└─────────────────────────────────────────────────────────────────────┘

┌──────────────────┐
│  Worker receives │
│  task assignment │
└─────────┬────────┘
          │
          ↓
┌─────────────────────────────────────────────────────────────┐
│  1. Download Batch from MinIO                                │
│     GET http://minio:9000/datasets/job_abc123/batch_001.tar │
│     ↓                                                        │
│     Save to: /tmp/meshml/batch_001/                         │
│     Extract: 500 images + labels                            │
└─────────┬───────────────────────────────────────────────────┘
          │
          ↓
┌─────────────────────────────────────────────────────────────┐
│  2. Download Model Weights from Parameter Server             │
│     gRPC: GetModelWeights(job_id, version)                  │
│     ↓                                                        │
│     Receive: model_state_dict (tensor bytes)                │
│     Load into local PyTorch model                           │
└─────────┬───────────────────────────────────────────────────┘
          │
          ↓
┌─────────────────────────────────────────────────────────────┐
│  3. Local Training                                           │
│                                                              │
│  model.train()                                              │
│  for epoch in range(5):                                     │
│      for images, labels in data_loader:                     │
│          # Forward pass                                     │
│          outputs = model(images)                            │
│          loss = criterion(outputs, labels)                  │
│                                                              │
│          # Backward pass                                    │
│          loss.backward()                                    │
│          optimizer.step()                                   │
│          optimizer.zero_grad()                              │
│                                                              │
│      # Report progress every epoch                          │
│      report_progress(epoch, loss, accuracy)                 │
└─────────┬───────────────────────────────────────────────────┘
          │
          ↓
┌─────────────────────────────────────────────────────────────┐
│  4. Extract Gradients                                        │
│     gradients = {}                                          │
│     for name, param in model.named_parameters():            │
│         gradients[name] = param.grad.cpu().numpy()          │
│                                                              │
│     Serialize and compress:                                 │
│     compressed_grads = compress(pickle.dumps(gradients))    │
└─────────┬───────────────────────────────────────────────────┘
          │
          ↓
┌─────────────────────────────────────────────────────────────┐
│  5. Send Gradients to Parameter Server                       │
│     gRPC: UpdateGradients(job_id, worker_id, gradients)     │
│     ↓                                                        │
│     Parameter Server aggregates:                            │
│     • Receives gradients from all workers                   │
│     • Averages: avg_grad = sum(grads) / num_workers        │
│     • Updates global model: model -= lr * avg_grad         │
└─────────┬───────────────────────────────────────────────────┘
          │
          ↓
┌─────────────────────────────────────────────────────────────┐
│  6. Fetch Updated Weights                                    │
│     gRPC: GetModelWeights(job_id, version=next)             │
│     ↓                                                        │
│     Load new weights into local model                       │
│     Continue to next batch                                  │
└──────────────────────────────────────────────────────────────┘
          │
          │ Repeat for all assigned batches
          ↓
┌─────────────────────────────────────────────────────────────┐
│  7. Report Completion                                        │
│     gRPC: ReportCompletion(job_id, worker_id, metrics)      │
│     ↓                                                        │
│     Orchestrator marks batches complete                     │
│     Worker returns to idle pool                             │
└──────────────────────────────────────────────────────────────┘
```

---

## 5. Cross-Platform Communication Flow

```
┌─────────────────────────────────────────────────────────────────────┐
│  HOW DIFFERENT OS DEVICES COMMUNICATE                               │
└─────────────────────────────────────────────────────────────────────┘

Device 1: macOS Laptop                   Device 2: Windows Desktop
┌──────────────────────┐                 ┌──────────────────────┐
│  Python Worker       │                 │  C++ Worker          │
│  PyTorch + Metal GPU │                 │  LibTorch + CUDA GPU │
└──────────┬───────────┘                 └──────────┬───────────┘
           │                                        │
           │ gRPC (HTTP/2)                          │ gRPC (HTTP/2)
           │ Protobuf serialization                 │ Protobuf
           │                                        │
           └────────────────┬───────────────────────┘
                            ↓
           ┌────────────────────────────────────────┐
           │   Task Orchestrator (Linux Docker)    │
           │   • Platform-agnostic gRPC server     │
           │   • Protobuf decodes messages         │
           │   • Stores in PostgreSQL              │
           └────────────────┬───────────────────────┘
                            │
                            ↓
           ┌────────────────────────────────────────┐
           │   Parameter Server (Linux Docker)      │
           │   • Receives gradients (binary)        │
           │   • Framework: PyTorch (any OS)        │
           │   • Updates weights                    │
           └────────────────┬───────────────────────┘
                            │
                            │
           ┌────────────────┼────────────────┐
           │                │                │
           ↓                ↓                ↓
┌──────────────────┐  ┌──────────────┐  ┌──────────────┐
│  Python Worker   │  │  JS Worker   │  │  C++ Worker  │
│  Linux Server    │  │  Browser     │  │  Windows     │
│  CPU only        │  │  Android     │  │  RTX 3080    │
└──────────────────┘  └──────────────┘  └──────────────┘

KEY POINTS:
• Workers never communicate directly
• All communication through central services
• gRPC works identically on all platforms
• Binary format (Protobuf) is OS-agnostic
• Services run in Docker (OS doesn't matter)
```

---

## 6. Fault Tolerance & Dynamic Worker Pool

```
┌─────────────────────────────────────────────────────────────────────┐
│  WORKER JOIN/LEAVE HANDLING                                         │
└─────────────────────────────────────────────────────────────────────┘

Scenario: Training job with 100 batches, 10 workers

Time T0: Training Starts
━━━━━━━━━━━━━━━━━━━━━━━━
┌────────────────────────────────────────────────────────┐
│  10 workers active                                     │
│  Each assigned 10 batches                             │
│                                                        │
│  Worker 1: [batch 1-10]    ✓ Processing               │
│  Worker 2: [batch 11-20]   ✓ Processing               │
│  ...                                                   │
│  Worker 10: [batch 91-100] ✓ Processing               │
└────────────────────────────────────────────────────────┘


Time T1: Worker 5 Disconnects
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
┌────────────────────────────────────────────────────────┐
│  Worker 5 missed 3 heartbeats (90 seconds)            │
│  Orchestrator marks Worker 5 as "failed"              │
│                                                        │
│  Orphaned batches: [batch 41-50]                      │
│  Completed: batch 41, 42, 43 ✓                        │
│  In-progress: batch 44 (lost)                         │
│  Pending: batch 45-50                                 │
└─────────────┬──────────────────────────────────────────┘
              │
              ↓
┌────────────────────────────────────────────────────────┐
│  Orchestrator Reassignment                             │
│  • Mark batch 44 as "retry_needed"                    │
│  • Redistribute [batch 44-50] to idle workers         │
│  • Update PostgreSQL:                                 │
│    UPDATE data_batches SET worker_id = 'worker_3'    │
│    WHERE batch_id IN (44, 45, ...)                    │
└────────────────────────────────────────────────────────┘


Time T2: New Worker Joins
━━━━━━━━━━━━━━━━━━━━━━━━━━
┌────────────────────────────────────────────────────────┐
│  Worker 11 registers                                   │
│  Orchestrator assigns pending batches                 │
│                                                        │
│  Current status:                                       │
│  • Workers 1-4, 6-10: Still processing                │
│  • Worker 11: Assigned orphaned batches               │
│  • Worker 5: Removed from pool                        │
└────────────────────────────────────────────────────────┘


Time T3: Training Completes
━━━━━━━━━━━━━━━━━━━━━━━━━━━
┌────────────────────────────────────────────────────────┐
│  All 100 batches processed                             │
│  Final model saved to MinIO                           │
│  All workers return to idle pool                      │
└────────────────────────────────────────────────────────┘
```

---

## 7. Data Security & Privacy

```
┌─────────────────────────────────────────────────────────────────────┐
│  PRIVACY-PRESERVING DESIGN                                          │
└─────────────────────────────────────────────────────────────────────┘

Option 1: Standard Distributed Training
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
┌──────────────────┐
│  Central Server  │
│  Has full dataset│
└─────────┬────────┘
          │ Shards data
          ↓
   Workers get different batches
   (Privacy: Medium - server sees all data)


Option 2: Federated Learning (Future Enhancement)
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
┌──────────────────┐
│  Worker          │
│  Keeps own data  │  ◄── Data never leaves device
└─────────┬────────┘
          │
          │ Only sends gradients/model updates
          ↓
┌──────────────────────┐
│  Parameter Server    │
│  Never sees raw data │
└──────────────────────┘

   (Privacy: High - data stays on device)
```

---

## Summary

These diagrams illustrate:

1. ✅ **OS-agnostic communication** via gRPC/Protobuf
2. ✅ **Flexible dataset input** (upload, URL, built-in)
3. ✅ **Smart distribution** (batches fetched on-demand)
4. ✅ **Multi-tier workers** (Python, C++, JavaScript)
5. ✅ **Fault tolerance** (workers can join/leave)
6. ✅ **Capability-based assignment** (automatic matching)

The architecture ensures any device with any OS can participate in training as long as it can:
- Make HTTP/gRPC connections
- Run one of the worker types (Python/C++/JavaScript)
- Download batches from MinIO

**Next:** Implement Phase 1 database schema to support this architecture.
