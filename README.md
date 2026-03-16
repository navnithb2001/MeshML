# MeshML: Distributed Machine Learning Platform

MeshML is a high-performance, distributed machine learning ecosystem designed to bridge the gap between local development and large-scale cloud training. The architecture utilizes a **microservices model**, leveraging a hybrid of **REST/WebSockets** for user interaction and **gRPC** for high-speed, internal data synchronization.

---

## 🏗️ Full System Design: Who Calls What

### Phase A: Ingestion (The Setup)
1. **User → API Gateway (REST):** Uploads the `model.py` definition and the `dataset.tar.gz` archive via standard HTTP POST requests.
2. **API Gateway → Model Registry (gRPC):** Calls `RegisterNewModel()`. The Registry saves the Python file to Object Storage (MinIO/GCS) and creates a record in the `models` table with `version_1`.
3. **API Gateway → Dataset Sharder (gRPC):** Triggers the sharding process. The Sharder physically splits the uploaded data, saves chunks to Object Storage, and populates the `data_batches` table so available work is visible to the scheduler.

### Phase B: Orchestration (Starting the Job)
1. **User → API Gateway (REST):** Starts a job on a selected dataset/model version.
2. **API Gateway → Task Orchestrator (gRPC):** Calls `InitiateTraining(job_id, model_version)`.
3. **Task Orchestrator → Model Registry (gRPC):** Calls `GetModelArtifact()` to generate short-lived signed URLs for model code; those URLs are embedded into worker task assignments.

### Phase C: Training Loop (The Work)
1. **Worker ↔ Task Orchestrator (gRPC):** Uses bidirectional `StreamTasks`. The Orchestrator pushes assignments, and workers stream heartbeat + task status (`TaskResult`) back.
2. **Worker → Object Storage (HTTP):** Downloads `model.py` and assigned `data_batch` directly using signed URLs.
3. **Worker ↔ Parameter Server (gRPC):** Pulls global weights (`PullWeights`), computes local gradients, and pushes updates (`PushGradients`) using binary tensor payloads.
4. **Parameter Server → Model Registry (Internal):** A background persistence loop periodically saves checkpoints based on version intervals.

### Phase D: Completion (The Result)
1. **Parameter Server → Model Registry (gRPC):** When global version reaches `final_version`, uploads final `state_dict`.
2. **Model Registry:** Marks model `COMPLETED` and stores final `.pt`.
3. **API Gateway → User:** Exposes completed status and download endpoints through REST.

---

## 📡 Architectural Choice: The Protocol Split

MeshML uses a strict protocol split: high-frequency control/math over gRPC, user-facing and blob transfer over HTTP.

### 1. The gRPC Plane (High-Performance Control & Math)
- **Worker ↔ Task Orchestrator:** Bidirectional streaming (`StreamTasks`) for push assignments and live worker status.
- **Worker ↔ Parameter Server:** Binary gradient and weight transport over Protobuf for low latency and low CPU overhead.
- **Worker ↔ Metrics Service:** Streaming metrics updates for near-real-time observability.
- **Internal service-to-service:** API Gateway triggers internal commands (`RegisterNewModel`, `InitiateTraining`, sharding) via gRPC contracts.

### 2. The HTTP Plane (Universal Access & Blob Transfer)
- **Worker → Object Storage (Signed URLs):** Large model/data blob downloads use direct HTTP/HTTPS for throughput and resilience.
- **User ↔ API Gateway:** Authentication, group/project actions, uploads, and job triggers use REST/HTTP for browser/CLI compatibility.
- **Observability (WebSockets):** API Gateway upgrades HTTP to WebSockets to stream live training updates to dashboards.

---

## 🛡️ Lifecycle & Fault Tolerance

* **Self-Healing Workers:** If a gRPC stream is interrupted, the Orchestrator automatically reverts the assigned batch to `AVAILABLE` for re-assignment.
* **Resource Respect:** Workers include a background monitor (`psutil`) that pauses training if local CPU/RAM usage exceeds 80%.
* **Persistence:** The Parameter Server snapshots Redis weights into persistent object storage (GCS/MinIO) every $N$ versions to prevent data loss.
* **Cleanup:** Cascading delete logic ensures that when a dataset is removed, all associated cloud objects and database shards are purged.

---

## 🚀 Getting Started

### 1) Start the platform (local)

```bash
docker compose -f docker/docker-compose.yml up -d
```

### 2) Initialize the database

```bash
psql -h localhost -p 5432 -U meshml -d meshml -f scripts/init-db.sql
```

### 3) Use the API Gateway for ingestion

1. **Upload model and dataset** via API Gateway endpoints.
2. **Start a job** for a model version.

The API Gateway will trigger sharding and orchestration via gRPC internally.

### 4) Start workers

Use the Python worker:

```bash
pip install -e workers/python-worker
meshml-worker init --api-url http://localhost:8000
meshml-worker login --email you@example.com
meshml-worker join --invitation-code inv_abc123 --worker-id my-laptop
meshml-worker run
```

### 5) Monitor progress

- **WebSocket:** `GET /api/ws/jobs/{job_id}/stats` (live metrics + status changes)
- **Fallback:** `GET /api/jobs/{job_id}/status`

### 6) Download the final model

- **Final model:** `GET /api/models/{model_id}/download`
- **Checkpoint:** `GET /api/models/{model_id}/checkpoints/{version}`

## Services

- API Gateway (REST + WebSocket)
- Task Orchestrator (gRPC)
- Dataset Sharder (gRPC)
- Parameter Server (gRPC)
- Model Registry (REST + gRPC)
- Metrics Service (gRPC)

## Repo Layout (What Matters)

- `services/` – microservices
- `workers/python-worker/` – worker agent
- `services/*/proto/` – per-service `.proto` definitions used for local stub generation
- `docker/` – local compose
- `k8s/` – Kubernetes manifests
- `scripts/init-db.sql` – database bootstrap
