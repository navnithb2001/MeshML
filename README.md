# MeshML

# MeshML: Distributed Machine Learning Platform

MeshML is a high-performance, distributed machine learning ecosystem designed to bridge the gap between local development and large-scale cloud training. The architecture utilizes a **microservices model**, leveraging a hybrid of **REST/WebSockets** for user interaction and **gRPC** for high-speed, internal data synchronization.

---

## 🏗️ System Architecture

The system is organized into four functional planes to ensure separation of concerns and high availability:

* **Ingestion Plane:** Manages the entry of raw training scripts (`model.py`) and datasets.
* **Control Plane:** Manages job scheduling, worker orchestration, and model versioning.
* **Data Plane:** Optimized for high-throughput binary data movement (weights and shards).
* **Observability Plane:** Provides real-time feedback and historical tracking of training performance.

---

## 🛠️ Core Components

### 1. API Gateway (The Entry Point)
Acts as the central router for all external traffic. It provides a RESTful interface for job submission and serves as a protocol bridge, translating external HTTP requests into internal gRPC calls.

### 2. Dataset Sharder & Model Registry
* **Sharder:** Automatically partitions large datasets into optimized binary shards. It maintains the `data_batches` table to track task availability.
* **Registry:** Manages versioned checkpoints and final model artifacts. It handles SHA-256 integrity hashing and generates Signed URLs for secure data access.

### 3. Task Orchestrator (The Brain)
Maintains bidirectional gRPC streams with all active workers. It uses a **Push Model** to assign tasks: the moment a data batch is ready, the Orchestrator pushes a packet to an idle worker containing Signed URLs for both the code and the data.

### 4. Parameter Server (The Math Engine)
Implements an **Asynchronous SGD** strategy. It manages global model weights in a high-speed Redis store and applies an **Exponential Staleness Penalty** ($e^{-\lambda \cdot \Delta v}$) to ensure slow workers do not corrupt the global model state.

---

## 📡 Protocol Split & Communication

MeshML uses a "Hybrid Protocol" strategy to optimize for both compatibility and performance:

| Connection Path | Protocol | Purpose |
| :--- | :--- | :--- |
| **User ↔ Gateway** | **HTTP / REST** | Browser compatibility and CLI tool support. |
| **Worker ↔ Storage** | **HTTP Signed URLs** | High-speed file transfers bypassing application logic. |
| **Internal Mesh** | **gRPC (Binary)** | Low-latency, strongly-typed internal service communication. |
| **Live Dashboard** | **WebSockets** | Real-time streaming of loss and accuracy metrics. |

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
- `proto/` – source .proto definitions
- `docker/` – local compose
- `k8s/` – Kubernetes manifests
- `scripts/init-db.sql` – database bootstrap
