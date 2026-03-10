# MeshML Deployment Architecture

## Overview

MeshML is a **federated learning platform**, not a compute provider. The architecture is split into two distinct parts:

1. **Platform Services** (GKE) - You host and manage
2. **Worker Nodes** (Student Devices) - Students contribute compute voluntarily

---

## 🏢 Platform Services (GKE Deployment)

### What Gets Deployed to Your Cloud

```
┌─────────────────────────────────────────────────────────┐
│  Google Kubernetes Engine (GKE)                         │
│                                                          │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐ │
│  │  API Gateway │  │   Dataset    │  │     Task     │ │
│  │              │  │   Sharder    │  │ Orchestrator │ │
│  │ Port: 80     │  │ Port: 8001   │  │ Port: 8002   │ │
│  │ (LoadBalancer│  │ (ClusterIP)  │  │ (ClusterIP)  │ │
│  │  External)   │  │              │  │  gRPC: 50051 │ │
│  └──────────────┘  └──────────────┘  └──────────────┘ │
│                                                          │
│  ┌──────────────┐  ┌──────────────┐                    │
│  │  Parameter   │  │    Model     │                    │
│  │   Server     │  │   Registry   │                    │
│  │ Port: 8003   │  │ Port: 8004   │                    │
│  │ gRPC: 50052  │  │ (ClusterIP)  │                    │
│  └──────────────┘  └──────────────┘                    │
│                                                          │
│  ┌──────────────┐  ┌──────────────┐                    │
│  │  PostgreSQL  │  │    Redis     │                    │
│  │  Port: 5432  │  │  Port: 6379  │                    │
│  │  (20Gi PVC)  │  │  (10Gi PVC)  │                    │
│  └──────────────┘  └──────────────┘                    │
│                                                          │
└─────────────────────────────────────────────────────────┘
```

**Responsibilities:**
- ✅ User authentication (JWT)
- ✅ Job management (create, track, cancel)
- ✅ Data sharding and distribution
- ✅ Task assignment to workers
- ✅ Gradient aggregation
- ✅ Model versioning
- ✅ Database and caching

**Cost:** ~$200-230/month
**Always On:** Yes (24/7)
**You Control:** 100%

---

## 💻 Worker Nodes (Student Devices)

### What Students Run on Their Devices

```
┌─────────────────────────────────────────────────────────┐
│  Student Device (Bob's MacBook M2)                      │
│                                                          │
│  $ pip install meshml-worker                            │
│  $ meshml-worker init                                   │
│  $ meshml-worker join --invitation inv_abc123          │
│  $ meshml-worker start                                  │
│                                                          │
│  ┌──────────────────────────────────────┐              │
│  │  MeshML Python Worker                │              │
│  │                                       │              │
│  │  • Registers with API Gateway        │              │
│  │  • Joins training group              │              │
│  │  • Waits for task assignment         │              │
│  │  • Downloads model.py                │              │
│  │  • Downloads data batches            │              │
│  │  • Trains locally                    │              │
│  │  • Sends gradients to Parameter      │              │
│  │    Server                            │              │
│  │  • Receives updated weights          │              │
│  └──────────────────────────────────────┘              │
│                                                          │
│  Hardware Auto-Detected:                                │
│  • CPU: Apple M2 (8 cores)                             │
│  • RAM: 16GB                                            │
│  • GPU: Metal (8GB)                                     │
│  • PyTorch: 2.2.0                                       │
└─────────────────────────────────────────────────────────┘
```

**Responsibilities:**
- ✅ Execute training workloads
- ✅ Compute gradients
- ✅ Report progress
- ✅ Handle failures gracefully

**Cost:** FREE (students volunteer)
**Always On:** No (only when student is available)
**You Control:** 0% (students can disconnect anytime)

---

## 🔄 Communication Flow

```
┌──────────────┐                    ┌──────────────┐
│   Student    │                    │   Platform   │
│   Device     │                    │   (GKE)      │
│              │                    │              │
│              │  1. Register       │              │
│              │ ─────────────────> │              │
│              │    Worker Info     │              │
│              │    (GPU, RAM, CPU) │              │
│              │                    │              │
│              │  2. Join Group     │              │
│              │ ─────────────────> │              │
│              │    Invitation Code │              │
│              │                    │              │
│              │  3. Poll for Jobs  │              │
│              │ <───────────────── │              │
│              │    (every 10s)     │              │
│              │                    │              │
│              │  4. Task Assigned  │              │
│              │ <───────────────── │              │
│              │    model_url       │              │
│              │    batch_ids       │              │
│              │    config          │              │
│              │                    │              │
│              │  5. Download Model │              │
│              │ <───────────────── │              │
│              │    model.py        │              │
│              │                    │              │
│              │  6. Download Data  │              │
│              │ <───────────────── │              │
│              │    batch_22.pkl    │              │
│              │                    │              │
│              │  7. Train Locally  │              │
│              │    (on device)     │              │
│              │                    │              │
│              │  8. Send Gradients │              │
│              │ ─────────────────> │              │
│              │                    │              │
│              │  9. Get New Weights│              │
│              │ <───────────────── │              │
│              │                    │              │
│              │  10. Report        │              │
│              │ ─────────────────> │              │
│              │     Complete       │              │
│              │                    │              │
└──────────────┘                    └──────────────┘
```

---

## 📦 Deployment Responsibilities

### Your Responsibilities (Platform Owner)

1. **Deploy Platform to GKE:**
   ```bash
   ./scripts/deploy-gke.sh
   ```

2. **Manage Infrastructure:**
   - Monitor service health
   - Scale cluster nodes as needed
   - Update service versions
   - Backup database
   - Rotate secrets

3. **Provide Worker Installation:**
   - Publish `meshml-worker` to PyPI
   - Host installation scripts
   - Provide documentation
   - Generate invitation codes

4. **Monitor Platform:**
   - Service availability
   - API response times
   - Database performance
   - Network traffic

### Student Responsibilities

1. **Install Worker:**
   ```bash
   pip install meshml-worker
   ```

2. **Register and Join:**
   ```bash
   meshml-worker init
   meshml-worker join --invitation inv_abc123
   ```

3. **Run Worker:**
   ```bash
   meshml-worker start
   ```

4. **Keep Worker Running:**
   - Optional: Run as background service
   - Optional: Start on login
   - Can pause/stop anytime

---

## 🎯 Key Principles

### ✅ What This Architecture Provides

1. **Decentralized Compute** - No centralized GPU costs
2. **Student Ownership** - Students own their hardware
3. **Voluntary Participation** - Students join/leave freely
4. **Scalability** - Add workers without infrastructure costs
5. **Privacy** - Data never leaves student devices
6. **Federated Learning** - True distributed training

### ❌ What This Architecture Does NOT Provide

1. **Guaranteed Compute** - Workers can disconnect
2. **Predictable Performance** - Different hardware capabilities
3. **24/7 Availability** - Workers online when students are
4. **Centralized Storage** - No cloud data storage
5. **Worker Control** - Can't force workers to train

---

## 📊 Scaling Comparison

### Traditional Cloud Training (Not MeshML)

```
Cost for 100 GPUs × 10 hours:
100 × $2.50/hour × 10 hours = $2,500
```

### MeshML Federated Training

```
Platform Cost (GKE): $200/month
Worker Cost: $0 (100 students volunteer)
Total: $200/month for unlimited workers
```

**Savings: >90% cost reduction** 🎉

---

## 🚀 Getting Started

### 1. Deploy Platform (You)

```bash
cd MeshML
./scripts/deploy-gke.sh
```

### 2. Students Install Worker

```bash
# Option 1: PyPI (when published)
pip install meshml-worker

# Option 2: Install script
curl -fsSL https://install.meshml.io | bash

# Option 3: Manual
git clone https://github.com/yourorg/MeshML.git
cd MeshML/workers/python-worker
./install.sh
```

### 3. Students Join Training

```bash
meshml-worker join --invitation inv_abc123
meshml-worker start
```

### 4. Submit Training Job

```bash
curl -X POST http://YOUR_EXTERNAL_IP/api/jobs/create \
  -H "Authorization: Bearer $TOKEN" \
  -d '{
    "group_id": "group_cs101",
    "model_url": "https://storage.../model.py",
    "dataset_url": "https://storage.../data.zip",
    "config": {"epochs": 10, "batch_size": 64}
  }'
```

### 5. Monitor Progress

```bash
# Check registered workers
curl http://YOUR_EXTERNAL_IP/api/workers

# Check job status
curl http://YOUR_EXTERNAL_IP/api/jobs/{job_id}
```

---

## 🔒 Security Considerations

### Platform Security

- ✅ HTTPS/TLS for all API communication
- ✅ JWT authentication for users
- ✅ Worker authentication tokens
- ✅ Database encryption at rest
- ✅ Network policies in Kubernetes
- ✅ Secret management (Google Secret Manager)

### Worker Security

- ✅ Code execution sandboxing (planned)
- ✅ Resource limits (CPU/RAM/disk)
- ✅ Model code validation
- ✅ Encrypted gradient transmission
- ✅ No data exfiltration (data stays on device)

---

## 📚 Additional Resources

- [GKE Deployment Guide](../k8s/README.md)
- [Worker Installation Guide](../workers/python-worker/README.md)
- [Worker Registration Guide](./WORKER_REGISTRATION.md)
- [Custom Model Upload Guide](./user-guide/custom-model-upload.md)
- [Architecture Specification](./architecture/ARCHITECTURE.md)

---

## 💡 FAQ

**Q: Do I need to run workers in GKE?**  
A: No! Workers run on student devices. GKE only runs the platform services.

**Q: What if no students join?**  
A: You can run local workers for testing, but production relies on student participation.

**Q: Can I run some workers in the cloud?**  
A: Not recommended. The whole point is decentralized, student-provided compute.

**Q: How do I ensure workers stay online?**  
A: You don't! That's the nature of federated learning. The system handles worker churn.

**Q: What about data privacy?**  
A: Data never leaves student devices. Only gradients are sent to the parameter server.

**Q: Can students see each other's data?**  
A: No. Each worker trains only on their assigned data shard locally.

---

**MeshML: Federated Learning Platform - Not a Compute Provider** 🚀
