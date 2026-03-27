# MeshML

Distributed ML training platform using microservices, gRPC streaming for control/math, and HTTP for user APIs + object storage transfers.

## System design

### Phase A: Ingestion
1. User uploads `model.py` and dataset archive through API Gateway REST endpoints.
2. API Gateway calls Model Registry gRPC `RegisterNewModel`, then uploads code to object storage via signed URL.
3. API Gateway stores dataset metadata and triggers Dataset Sharder later during job start.

### Phase B: Orchestration
1. User starts a job from UI/API (`POST /api/jobs`).
2. API Gateway calls Task Orchestrator gRPC `InitiateTraining`.
3. Task Orchestrator requests model artifact signed URL from Model Registry and embeds it in streamed task assignments.

### Phase C: Training loop
1. Worker opens bidirectional `StreamTasks` with Task Orchestrator.
2. Worker downloads `model.py` and `batch.data` over HTTP signed URLs.
3. Worker pulls/pushes weights+gradients with Parameter Server over gRPC.
4. Worker streams step-level metrics (`loss`, `accuracy`, `timestamp`, `worker_id`) to Metrics Service over gRPC (`StreamMetrics`).
5. Metrics Service publishes/persists telemetry (Redis + PostgreSQL) for dashboard and monitoring consumers.
6. Parameter Server persists checkpoints to Model Registry on interval / version schedule.

### Phase D: Completion
1. Parameter Server uploads final state dict when `final_version` threshold is reached.
2. Model Registry marks model complete and stores final artifact.
3. API Gateway exposes status and download endpoints.

## Protocol split

- gRPC: worker orchestration stream, parameter sync, metrics stream, internal service calls.
- HTTP/REST: user auth/groups/jobs, file upload/download, signed object URL transfers.
- WebSocket: live job stats to dashboard.

## What is currently supported

### Model upload contract (`/api/models/upload`)

Model file validation currently enforces:
- UTF-8 Python source
- valid Python syntax
- `create_model()` function exists
- `MODEL_METADATA` exists and is a dict literal

`MODEL_METADATA` required fields:
- `name`
- `version`
- `framework`
- `input_shape`
- `output_shape`
- `task_type` (`classification`, `regression`, `binary`)
- `loss` (`cross_entropy`, `mse`, `mae`, `bce_with_logits`, `bce`)
- `metrics` (non-empty list of strings)

### Dataset upload formats (`/api/datasets/upload`)

Supported dataset formats:
- `imagefolder`
- `csv`
- `coco`

Format can be auto-detected from uploaded content. Unknown/unsupported formats are rejected with `400`.

### Worker trainer modes

Current Python worker trainer supports task configs from model metadata:
- `classification`
- `regression`
- `binary`

Loss and metric behavior are selected from metadata at runtime.

## Local run

### 1) Start stack

```bash
docker compose -f docker/docker-compose.yml up -d
```

### 2) Initialize database

```bash
psql -h localhost -p 5432 -U meshml -d meshml -f scripts/init-db.sql
```

### 3) Install and run Python worker

```bash
pip install -e workers/python-worker
meshml-worker init --api-url http://localhost:8000
meshml-worker login --email you@example.com
meshml-worker join --invitation-code <code> --worker-id my-laptop1
meshml-worker run
```

Useful worker env vars:
- `MESHML_DISABLE_RESOURCE_THROTTLE=true` disables CPU/RAM pause monitor.
- `MESHML_EXIT_ON_JOB_COMPLETE=true` exits worker after a job fully completes.
- `MESHML_CPU_PAUSE_THRESHOLD` / `MESHML_RAM_PAUSE_THRESHOLD` override pause thresholds.

## Dashboard

Dashboard lives under `dashboard/`.

Run locally:

```bash
cd dashboard
npm install
npm run dev
```

Current UI includes:
- Group dashboard tabs for jobs, workers, datasets, settings
- New Training Run modal with:
  - upload new or reuse existing dataset
  - model code upload
  - convergence target (`final_version > 0`)
- Toast notifications + error boundary for frontend failures

## E2E validation

Run:

```bash
E2E_USER_EMAIL=you1@example.com \
E2E_USER_PASSWORD='StrongPass123!' \
E2E_GROUP_ID='<group-id>' \
E2E_WORKER_ID='my-laptop1' \
python tests/e2e_validation.py
```

The script validates:
- auth/login
- model upload
- dataset upload + availability
- job creation
- worker heartbeat path
- job progress / parameter-server signal

## Service endpoints (docker compose defaults)

- API Gateway: `http://localhost:8000`
- Dataset Sharder: `http://localhost:8001` and gRPC `localhost:50053`
- Task Orchestrator: `http://localhost:8002` and gRPC `localhost:50051`
- Parameter Server: `http://localhost:8003` and gRPC `localhost:50052`
- Model Registry: `http://localhost:8004` and gRPC `localhost:50054` (host-mapped)
- Metrics Service: `http://localhost:8005` and gRPC `localhost:50055`
- MinIO: `http://localhost:9000` (console `http://localhost:9001`)

## Repository layout

- `services/` microservices
- `workers/python-worker/` worker runtime + CLI
- `dashboard/` React/Vite UI
- `tests/` integration + E2E scripts
- `docker/` local compose
- `k8s/` Kubernetes manifests
- `scripts/init-db.sql` DB bootstrap
