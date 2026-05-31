# MeshML

**A distributed, federated machine-learning training platform.** MeshML lets a group of people pool their machines ("workers") to collaboratively train a single PyTorch model. A parameter server holds the authoritative global weights; workers pull those weights, compute gradients on their assigned data shard, and push the gradients back, where they are aggregated into the shared model in real time.

The system is built as a set of asynchronous microservices with a deliberate **protocol split**: gRPC for the high-frequency control/math plane and HTTP for user-facing APIs and large blob transfers.

---

## Table of Contents

- [Key Features](#key-features)
- [Architecture](#architecture)
- [How Weights Evolve — The Update Rule](#how-weights-evolve--the-update-rule)
- [Distributed Training Lifecycle](#distributed-training-lifecycle)
- [The Protocol Split](#the-protocol-split)
- [Model & Dataset Contracts](#model--dataset-contracts)
- [Quickstart (Local)](#quickstart-local)
- [Configuration Reference](#configuration-reference)
- [Service Endpoints](#service-endpoints)
- [Dashboard](#dashboard)
- [Deployment](#deployment)
- [Repository Layout](#repository-layout)

---

## Key Features

- **True data-parallel async SGD.** Every gradient is computed against the latest global weights and applied centrally, so all workers train *one shared model* instead of diverging on private copies.
- **Staleness-aware aggregation.** Gradients from slow workers are damped exponentially by how out-of-date they are, keeping asynchronous training stable.
- **Momentum, weight decay, and an LR schedule** applied server-side — workers stay thin; the optimizer lives in one place.
- **Epoch-driven orchestration.** A job trains the full dataset a configurable number of times (your convergence target) and then finalizes automatically.
- **Pluggable models & datasets.** Users upload a plain `model.py` (with a small metadata contract) and a dataset archive; the platform shards, distributes, trains, checkpoints, and serves the final artifact.
- **Live observability.** Loss/accuracy and epoch progress stream to a React dashboard over WebSockets.
- **Fault tolerance.** Global weights and momentum are persisted to Redis; checkpoints and the final model are pushed to object storage so a completed model is always downloadable.

---

## Architecture

MeshML is composed of six stateless services plus shared infrastructure (PostgreSQL, Redis, MinIO/GCS).

| Service | HTTP | gRPC | Responsibility |
|---|---|---|---|
| **API Gateway** | `8000` | — | User-facing REST + auth, job creation, WebSocket metrics, signed-URL proxying |
| **Model Registry** | `8004` | `50052` | Stores `model.py`, checkpoints, and final `.pt` artifacts in object storage |
| **Dataset Sharder** | `8001` | `50053` | Splits datasets into shards, persists `data_batches`, serves shard download URLs |
| **Task Orchestrator** | `8002` | `50051` | Bidirectional worker stream, shard assignment, **epoch loop**, job lifecycle |
| **Parameter Server** | `8003` | `50054` | Holds global weights; applies the central optimizer step; persists checkpoints |
| **Metrics Service** | `8005` | `50055` | Ingests streamed training metrics; aggregates job progress |
| **Worker** (client) | — | — | Pulls weights, computes gradients, pushes them; runs natively on contributor machines |

```
                 ┌─────────────┐   REST / WebSocket
   Browser  ◄───►│ API Gateway │◄──────────────────────────► User
                 └──────┬──────┘
              gRPC ┌────┴───────────────┬───────────────┐
                   ▼                    ▼               ▼
          ┌────────────────┐   ┌────────────────┐  ┌──────────────┐
          │ Task           │   │ Model Registry │  │ Dataset      │
          │ Orchestrator   │   └───────┬────────┘  │ Sharder      │
          └───────┬────────┘           │           └──────┬───────┘
        gRPC bidi │ (StreamTasks)      │ artifacts        │ shards
                  ▼                     ▼                  ▼
          ┌────────────────┐     ┌──────────────────────────────┐
          │     WORKER     │◄───►│        Object Storage        │
          │ (pull/compute/ │ HTTP│         (MinIO / GCS)        │
          │   push grads)  │     └──────────────────────────────┘
          └───────┬────────┘
             grpc │ PullWeights / PushGradients
                  ▼
          ┌────────────────┐  background persistence loop   ┌────────────────┐
          │ Parameter      │ ─────────────────────────────► │ Model Registry │
          │ Server (Redis) │      checkpoints / final.pt    └────────────────┘
          └────────────────┘
```

---

## How Weights Evolve — The Update Rule

This is the heart of MeshML. The global model lives in the **Parameter Server**; workers never own the source of truth, they only borrow it.

### The worker's tight loop

For every minibatch, each worker runs:

1. **Pull** the global weights at the current version: `θ_V ← PullWeights()`
2. **Compute** a gradient on its local minibatch: `g = ∇θ L(θ_V; batch)`
3. **Push** `(g, V)` to the Parameter Server (binary tensor buffers over gRPC).
4. The PS **applies** the update centrally and bumps the version to `V+1`.
5. **Pull** `θ_{V+1}` and repeat.

Because the gradient is always computed at the latest global weights and applied to the shared model, workers *complement* each other (async data-parallel SGD) instead of training divergent local copies. If the Parameter Server is briefly unreachable, the worker falls back to a local optimizer step so training degrades gracefully instead of stalling.

### The central update (executed per push, under a per-model Redis lock)

Let `θ` be the current global weights, `m` the momentum buffer, `V` the current global version, `g` the pushed gradient, and `V_w` the version the worker computed it against.

**1 — Staleness damping.** How many updates landed since the worker pulled:

```
s   = max(0, V − V_w)
w_s = exp(−λ · s)                    # λ = STALENESS_LAMBDA (default 0.3)
```

A gradient that is `s` versions out of date is trusted exponentially less. Fresh gradients (`s = 0`) get full weight `w_s = 1`.

**2 — Learning rate (base × step schedule × staleness).**

```
lr_t = max( lr_min , lr_base · γ^⌊V / step⌋ )      # step LR schedule
η    = lr_t · w_s                                  # effective learning rate
```

`lr_base` is supplied by the worker (default `0.01`). The schedule multiplies it by `γ` (default `0.5`) every `step` versions (`LR_DECAY_STEP`), floored at `lr_min` — so the model takes large steps early and fine, careful steps late. Set `LR_DECAY_STEP=0` to disable the schedule.

**3 — Weight decay (L2), applied to weight tensors only.**

```
ĝ = g + wd · θ        # only for tensors with ndim ≥ 2 (conv kernels, linear weights)
```

Biases and normalization parameters (`ndim == 1`) are **excluded**, the standard practice. `wd = WEIGHT_DECAY` (default `0`, i.e. off unless configured).

**4 — Momentum (heavy-ball).**

```
m ← μ · m + ĝ          # μ = SGD_MOMENTUM (default 0.9)
```

**5 — Parameter update.**

```
θ ← θ − η · m
```

**6 — Versioning & persistence.** The new weights are stored as version `V+1` in Redis. To bound memory, only the most recent `REDIS_PARAM_VERSION_HISTORY` (default 3) snapshots are kept — older ones are pruned on write, since only the latest is ever read.

> **In one line:** MeshML performs classic **SGD with momentum and weight decay**, extended with **exponential staleness damping** for the asynchronous multi-worker setting and a **step learning-rate schedule** for late-training refinement — all executed centrally on the parameter server so the global model stays coherent across every contributor.

### Checkpointing & finalization

A background **persistence loop** in the Parameter Server independently:

- uploads a **checkpoint** to the Model Registry every `CHECKPOINT_INTERVAL` versions (default 50), and
- uploads the **final model** once the global version reaches `FINAL_MODEL_VERSION` (default 500).

The download endpoint serves the final model if present, otherwise falls back to the most recent checkpoint — so a trained model is downloadable throughout the run, not just at the very end.

---

## Distributed Training Lifecycle

### Phase A — Ingestion
1. **User → API Gateway (REST):** uploads `model.py` and a dataset archive.
2. **API Gateway → Model Registry (gRPC):** `RegisterNewModel()` stores the code in object storage and records it in the `models` table.
3. **API Gateway / Orchestrator → Dataset Sharder (gRPC):** the dataset is split into shards (default **256 samples each**), written to object storage, and registered in the `data_batches` table as the available unit of work.

### Phase B — Orchestration
1. **User → API Gateway (REST):** starts a job, choosing a model, dataset, and a **convergence target** (number of full-dataset epochs).
2. **API Gateway → Task Orchestrator (gRPC):** `InitiateTraining(...)`.
3. **Task Orchestrator → Model Registry (gRPC):** `GetModelArtifact()` returns short-lived **signed URLs** embedded into worker assignments.

### Phase C — Training Loop
1. **Worker ↔ Task Orchestrator (gRPC, bidirectional `StreamTasks`):** the orchestrator pushes shard assignments; the worker streams back heartbeats and `TaskResult`s.
2. **Worker → Object Storage (HTTP signed URLs):** downloads `model.py` and its data shard directly.
3. **Worker ↔ Parameter Server (gRPC):** the pull → compute → push → pull cycle described above.
4. **Worker → Metrics Service (gRPC stream):** loss/accuracy per step.

### Phase D — Epochs & Completion
- The **orchestrator owns epochs.** When every shard has been completed once (one full pass), it either re-marks all shards `AVAILABLE` for the next pass (if the epoch count is below the target) or **finalizes** the job. The current epoch is published to the dashboard as `Epoch X / N`.
- On the final epoch the job is marked `completed`; the latest checkpoint / final model becomes downloadable via the REST API.

> Note: epoch progress is *driven by the orchestrator re-assigning work*, not by the parameter server. The parameter server is purely the optimizer and weight store.

---

## The Protocol Split

MeshML uses gRPC for the live training plane and HTTP for human interaction and bulk transfer.

### gRPC plane — high-performance control & math
- **Worker ↔ Orchestrator:** a single persistent bidirectional stream instead of polling.
- **Worker ↔ Parameter Server:** gradients/weights serialized as flat NumPy byte buffers (gzip-compressed) — no JSON overhead on the hot path.
- **Worker → Metrics Service:** streamed metrics for high-frequency dashboard updates.
- **Service ↔ Service:** strongly-typed internal commands (`RegisterNewModel`, `InitiateTraining`, `GetModelArtifact`, …).

### HTTP plane — universal access & blob transfer
- **Worker → Object Storage (signed URLs):** datasets and model code download directly from MinIO/GCS, which are OS-optimized for large static blobs.
- **User ↔ API Gateway (REST):** auth, groups, uploads, job control — consumable by any browser/CLI.
- **Observability (WebSockets):** the gateway upgrades to WebSockets to push live metrics to the browser.

### Hyper-concurrency (non-blocking backend)
- Async SQLAlchemy 2.0 (`AsyncSession`) throughout.
- CPU-bound work (`torch.save`, serialization) and blocking SDKs run in thread pools via `asyncio.to_thread`, keeping the event loop responsive under load.

---

## Model & Dataset Contracts

### Model upload (`/api/models/upload`)

A user-supplied `model.py` must contain:
- a `create_model()` function returning an `nn.Module`, and
- a `MODEL_METADATA` dict literal.

`MODEL_METADATA` required fields:

| Field | Notes |
|---|---|
| `name`, `version`, `framework` | identity |
| `input_shape`, `output_shape` | tensor shapes |
| `task_type` | `classification` \| `regression` \| `binary` |
| `loss` | `cross_entropy` \| `mse` \| `mae` \| `bce_with_logits` \| `bce` |
| `metrics` | non-empty list, e.g. `["accuracy"]` |

Validation enforces UTF-8 source, valid Python syntax, and the presence of both the function and the metadata dict.

### Dataset upload (`/api/datasets/upload`)

Supported formats (auto-detected; unknown formats rejected with `400`): `imagefolder`, `csv`, `coco`.

### Example model (CIFAR-10 CNN)

```python
MODEL_METADATA = {
    "name": "cifar10-cnn", "version": "1.0", "framework": "pytorch",
    "input_shape": [3, 32, 32], "output_shape": [10],
    "task_type": "classification", "loss": "cross_entropy", "metrics": ["accuracy"],
}

class CIFAR10Net(nn.Module):
    ...  # standard 3-block conv net

def create_model():
    return CIFAR10Net()
```

---

## Quickstart (Local)

### 1) Start the backend stack

```bash
docker compose -f docker/docker-compose.yml up -d
```

The database schema (`scripts/init-db.sql`) is applied automatically on a fresh Postgres volume. To re-apply manually:

```bash
docker exec -i meshml-postgres psql -U meshml -d meshml < scripts/init-db.sql
```

### 2) Run the dashboard

```bash
cd dashboard && npm install && npm run dev   # http://localhost:5173
```

Register an account, create a group, upload a model + dataset, and start a training run (choosing the convergence target = number of epochs).

### 3) Run a worker

The worker is a native client (it runs on the contributor's own machine and can use CPU / CUDA / Apple-Silicon MPS):

```bash
pip install -e workers/python-worker
meshml-worker init --dev-mode --device cpu --force   # wires all service URLs to localhost
meshml-worker login --email you@example.com --password '...'
meshml-worker run --batch-size 256                   # match the 256-sample shard size
```

> Keep `--batch-size 256` in sync with the dataset shard size so each assignment is a single clean minibatch step.

Useful worker env vars:
- `MESHML_DISABLE_RESOURCE_THROTTLE=true` — disable the CPU/RAM pause monitor.
- `MESHML_EXIT_ON_JOB_COMPLETE=true` — exit after a job finishes.

---

## Configuration Reference

Key environment variables (set in `docker/docker-compose.yml`):

### Parameter Server (optimizer & persistence)

| Variable | Default | Meaning |
|---|---|---|
| `SGD_MOMENTUM` | `0.9` | Momentum coefficient `μ` |
| `STALENESS_LAMBDA` | `0.3` | Staleness damping `λ` in `exp(−λ·s)` |
| `WEIGHT_DECAY` | `5e-4`* | L2 decay on weight tensors (`0` = off) |
| `LR_DECAY_GAMMA` | `0.5` | Step-schedule multiplier `γ` |
| `LR_DECAY_STEP` | `1500`* | Versions between LR decays (`0` = no schedule) |
| `LR_MIN` | `1e-4` | Learning-rate floor |
| `CHECKPOINT_INTERVAL` | `50` | Versions between checkpoint uploads |
| `FINAL_MODEL_VERSION` | `500` | Version at which the final model is uploaded |
| `REDIS_PARAM_VERSION_HISTORY` | `3` | Weight snapshots retained in Redis |
| `COORDINATION_REDIS_DB` | `0` | Redis DB where the `job→model` mapping lives |
| `MODEL_REGISTRY_GRPC_URL` | `model-registry:50052` | Upload target for checkpoints |

\* Code defaults are conservative (decay/schedule off); the compose file enables them.

### Gateway / Sharder

| Variable / config | Default | Meaning |
|---|---|---|
| job `batch_size` | `256` | Samples per shard (one minibatch per assignment) |
| job `final_version` | — | **Convergence target = number of full-dataset epochs** |

---

## Service Endpoints

| Service | HTTP | gRPC |
|---|---|---|
| API Gateway | `http://localhost:8000` | — |
| Dataset Sharder | `http://localhost:8001` | `localhost:50053` |
| Task Orchestrator | `http://localhost:8002` | `localhost:50051` |
| Parameter Server | `http://localhost:8003` | `localhost:50054` |
| Model Registry | `http://localhost:8004` | `localhost:50052` |
| Metrics Service | `http://localhost:8005` | `localhost:50055` |
| MinIO | `http://localhost:9000` | console `http://localhost:9001` |

---

## Dashboard

Lives under `dashboard/` (React + Vite + Tailwind). The live job view shows status, **epoch (X / N)**, batch progress, current loss, training accuracy, and a model-download action. See [FIREBASE-DEPLOYMENT.md](FIREBASE-DEPLOYMENT.md) for hosting.

---

## Deployment

- **Backend → Google Kubernetes Engine:** [GKE-DEPLOYMENT.md](GKE-DEPLOYMENT.md)
- **Dashboard → Firebase Hosting:** [FIREBASE-DEPLOYMENT.md](FIREBASE-DEPLOYMENT.md)

---

## Repository Layout

```
services/                 # six FastAPI + gRPC microservices
  api-gateway/            # REST, auth, WebSockets, signed-URL proxy
  model-registry/         # artifact storage
  dataset-sharder/        # sharding + data_batches
  task-orchestrator/      # worker stream, assignment, epoch loop
  parameter-server/       # global weights + optimizer + persistence loop
  metrics-service/        # metric ingestion + progress aggregation
workers/python-worker/    # worker runtime + `meshml-worker` CLI
dashboard/                # React/Vite UI
docker/docker-compose.yml # local stack
k8s/                      # Kubernetes manifests
scripts/init-db.sql       # DB bootstrap (auto-applied on fresh volume)
tests/                    # integration + E2E
```

---

## E2E Validation

```bash
E2E_USER_EMAIL=you@example.com \
E2E_USER_PASSWORD='StrongPass123!' \
E2E_GROUP_ID='<group-id>' \
E2E_WORKER_ID='my-laptop1' \
python tests/e2e_validation.py
```

Validates auth, model upload, dataset upload/availability, job creation, the worker heartbeat path, and the parameter-server signal.
