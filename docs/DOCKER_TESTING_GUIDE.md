# MeshML Docker Integration & Testing Guide

Complete guide for containerizing, deploying, and testing the MeshML distributed training platform.

## Table of Contents
1. [Prerequisites](#prerequisites)
2. [Quick Start](#quick-start)
3. [Service Architecture](#service-architecture)
4. [Manual Testing](#manual-testing)
5. [Integration Testing](#integration-testing)
6. [Monitoring](#monitoring)
7. [Troubleshooting](#troubleshooting)

---

## Prerequisites

### Required Software
- Docker Desktop 4.0+ (with Docker Compose V2)
- curl or HTTPie for API testing
- (Optional) Postman or Insomnia for GUI testing

### System Requirements
- **RAM**: 8GB minimum, 16GB recommended
- **Storage**: 10GB free space
- **CPU**: 4 cores recommended

### Installation Check
```bash
docker --version          # Should be 20.10+
docker-compose --version  # Should be 2.0+
```

---

## Quick Start

### 1. Clone and Navigate
```bash
cd /Users/navnithbharadwaj/Desktop/autoapply/MeshML
```

### 2. Start All Services
```bash
# Start core services only
docker-compose up -d

# Or start with monitoring
docker-compose --profile monitoring up -d
```

### 3. Check Service Health
```bash
# Wait for services to be healthy (30-60 seconds)
docker-compose ps

# Check logs
docker-compose logs -f
```

### 4. Verify All Services Running
```bash
# API Gateway
curl http://localhost:8000/health

# Model Registry
curl http://localhost:8004/health

# Dataset Sharder
curl http://localhost:8001/health

# Task Orchestrator
curl http://localhost:8002/health

# Parameter Server
curl http://localhost:8003/health
```

---

## Service Architecture

### Service Ports
| Service | HTTP Port | gRPC Port | Purpose |
|---------|-----------|-----------|---------|
| API Gateway | 8000 | - | User-facing REST API |
| Dataset Sharder | 8001 | - | Dataset distribution |
| Task Orchestrator | 8002 | 50051 | Job coordination |
| Parameter Server | 8003 | 50052 | Model aggregation |
| Model Registry | 8004 | - | Model storage |
| PostgreSQL | 5432 | - | Database |
| Redis | 6379 | - | Cache |
| Prometheus | 9090 | - | Metrics (optional) |
| Grafana | 3000 | - | Dashboards (optional) |

### Container Network
All services communicate via `meshml-network` (172.20.0.0/16)

---

## Manual Testing

### Test 1: User Registration & Authentication

```bash
# 1. Register a new user
curl -X POST http://localhost:8000/api/v1/auth/register \
  -H "Content-Type: application/json" \
  -d '{
    "email": "test@meshml.com",
    "password": "testpass123",
    "full_name": "Test User"
  }'

# Expected: 201 Created with user object

# 2. Login
curl -X POST http://localhost:8000/api/v1/auth/login \
  -H "Content-Type: application/json" \
  -d '{
    "email": "test@meshml.com",
    "password": "testpass123"
  }'

# Save the access_token from response
export TOKEN="<access_token_here>"

# 3. Get current user
curl http://localhost:8000/api/v1/auth/me \
  -H "Authorization: Bearer $TOKEN"
```

### Test 2: Group Creation

```bash
# 1. Create a group
curl -X POST http://localhost:8000/api/v1/groups \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "name": "ML Research Team",
    "description": "Testing distributed training"
  }'

# Save the group_id from response
export GROUP_ID="<group_id_here>"

# 2. List groups
curl http://localhost:8000/api/v1/groups \
  -H "Authorization: Bearer $TOKEN"
```

### Test 3: Model Upload

```bash
# 1. Create model entry
curl -X POST http://localhost:8004/api/v1/models \
  -H "Content-Type: application/json" \
  -d '{
    "name": "ResNet-18 CIFAR-10",
    "description": "ResNet-18 for CIFAR-10 classification",
    "group_id": 1,
    "architecture_type": "CNN",
    "dataset_type": "CIFAR-10",
    "version": "1.0.0"
  }'

# Save model_id
export MODEL_ID="<model_id_here>"

# 2. Create a sample model file
cat > /tmp/test_model.py << 'EOF'
import torch
import torch.nn as nn

MODEL_METADATA = {
    "name": "ResNet-18",
    "version": "1.0.0",
    "framework": "PyTorch",
    "architecture": "CNN"
}

def create_model():
    return torch.nn.Sequential(
        nn.Conv2d(3, 64, 3, padding=1),
        nn.ReLU(),
        nn.MaxPool2d(2),
        nn.Flatten(),
        nn.Linear(64 * 16 * 16, 10)
    )

def create_dataloader(batch_size=32):
    from torchvision import datasets, transforms
    transform = transforms.Compose([transforms.ToTensor()])
    dataset = datasets.CIFAR10(root='./data', train=True, download=True, transform=transform)
    return torch.utils.data.DataLoader(dataset, batch_size=batch_size, shuffle=True)
EOF

# 3. Upload model file
curl -X POST http://localhost:8004/api/v1/models/$MODEL_ID/upload \
  -F "file=@/tmp/test_model.py"

# 4. Check model status
curl http://localhost:8004/api/v1/models/$MODEL_ID
```

### Test 4: Search Models

```bash
# Search all models
curl "http://localhost:8004/api/v1/search/models?page=1&page_size=10"

# Search with filters
curl "http://localhost:8004/api/v1/search/models?architecture_type=CNN&state=ready"

# Get popular models
curl http://localhost:8004/api/v1/search/popular

# Get recent models
curl http://localhost:8004/api/v1/search/recent
```

### Test 5: Worker Registration

```bash
# Check running workers
curl http://localhost:8000/api/v1/workers \
  -H "Authorization: Bearer $TOKEN"

# Workers should auto-register on startup
# You should see python-worker-1 and python-worker-2
```

### Test 6: Job Submission

```bash
# Submit a training job
curl -X POST http://localhost:8000/api/v1/jobs \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "name": "CIFAR-10 Training",
    "group_id": '$GROUP_ID',
    "model_id": '$MODEL_ID',
    "dataset": "CIFAR-10",
    "num_workers": 2,
    "epochs": 5,
    "batch_size": 32,
    "learning_rate": 0.001
  }'

# Save job_id
export JOB_ID="<job_id_here>"

# Check job status
curl http://localhost:8000/api/v1/jobs/$JOB_ID \
  -H "Authorization: Bearer $TOKEN"

# Get job progress
curl http://localhost:8000/api/v1/jobs/$JOB_ID/progress \
  -H "Authorization: Bearer $TOKEN"
```

### Test 7: Monitor System

```bash
# System health
curl http://localhost:8000/api/v1/monitoring/health

# Active workers
curl http://localhost:8000/api/v1/monitoring/workers \
  -H "Authorization: Bearer $TOKEN"

# System metrics
curl http://localhost:8000/api/v1/monitoring/metrics \
  -H "Authorization: Bearer $TOKEN"

# Statistics
curl http://localhost:8000/api/v1/monitoring/stats \
  -H "Authorization: Bearer $TOKEN"
```

---

## Integration Testing

### End-to-End Test Script

Create `tests/integration/test_e2e.sh`:

```bash
#!/bin/bash
set -e

echo "🧪 MeshML End-to-End Integration Test"
echo "======================================="

# Wait for services
echo "⏳ Waiting for services to be healthy..."
sleep 30

# Test 1: User Registration
echo "✅ Test 1: User Registration"
REGISTER_RESPONSE=$(curl -s -X POST http://localhost:8000/api/v1/auth/register \
  -H "Content-Type: application/json" \
  -d '{
    "email": "test@meshml.com",
    "password": "testpass123",
    "full_name": "Test User"
  }')

echo "User created: $(echo $REGISTER_RESPONSE | jq -r '.email')"

# Test 2: Login
echo "✅ Test 2: Login"
LOGIN_RESPONSE=$(curl -s -X POST http://localhost:8000/api/v1/auth/login \
  -H "Content-Type: application/json" \
  -d '{
    "email": "test@meshml.com",
    "password": "testpass123"
  }')

TOKEN=$(echo $LOGIN_RESPONSE | jq -r '.access_token')
echo "Token obtained: ${TOKEN:0:20}..."

# Test 3: Create Group
echo "✅ Test 3: Create Group"
GROUP_RESPONSE=$(curl -s -X POST http://localhost:8000/api/v1/groups \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "name": "Test Group",
    "description": "Integration test group"
  }')

GROUP_ID=$(echo $GROUP_RESPONSE | jq -r '.id')
echo "Group created: ID=$GROUP_ID"

# Test 4: Create Model
echo "✅ Test 4: Create Model"
MODEL_RESPONSE=$(curl -s -X POST http://localhost:8004/api/v1/models \
  -H "Content-Type: application/json" \
  -d '{
    "name": "Test Model",
    "group_id": '$GROUP_ID',
    "architecture_type": "CNN"
  }')

MODEL_ID=$(echo $MODEL_RESPONSE | jq -r '.id')
echo "Model created: ID=$MODEL_ID"

# Test 5: Check Workers
echo "✅ Test 5: Check Workers"
WORKERS=$(curl -s http://localhost:8000/api/v1/workers \
  -H "Authorization: Bearer $TOKEN")

WORKER_COUNT=$(echo $WORKERS | jq '. | length')
echo "Workers registered: $WORKER_COUNT"

# Test 6: Health Checks
echo "✅ Test 6: Health Checks"
for service in api-gateway:8000 model-registry:8004 dataset-sharder:8001 task-orchestrator:8002 parameter-server:8003; do
  IFS=':' read -r name port <<< "$service"
  STATUS=$(curl -s http://localhost:$port/health | jq -r '.status')
  echo "  $name: $STATUS"
done

echo ""
echo "🎉 All integration tests passed!"
```

Run the test:
```bash
chmod +x tests/integration/test_e2e.sh
./tests/integration/test_e2e.sh
```

---

## Monitoring

### Access Monitoring Tools

If started with `--profile monitoring`:

```bash
# Prometheus (metrics)
open http://localhost:9090

# Grafana (dashboards)
open http://localhost:3000
# Login: admin/admin
```

### View Logs

```bash
# All services
docker-compose logs -f

# Specific service
docker-compose logs -f api-gateway
docker-compose logs -f python-worker-1

# Last 100 lines
docker-compose logs --tail=100 parameter-server
```

### Container Stats

```bash
# Resource usage
docker stats

# Service status
docker-compose ps
```

---

## Troubleshooting

### Services Won't Start

```bash
# Check logs
docker-compose logs

# Rebuild images
docker-compose build --no-cache

# Reset everything
docker-compose down -v
docker-compose up -d
```

### Database Connection Issues

```bash
# Check PostgreSQL
docker-compose exec postgres psql -U meshml -d meshml -c "SELECT 1"

# Run migrations manually
docker-compose exec api-gateway python -c "from app.utils.db_init import create_tables; create_tables()"
```

### Worker Not Connecting

```bash
# Check worker logs
docker-compose logs python-worker-1

# Check orchestrator
curl http://localhost:8002/health

# Restart workers
docker-compose restart python-worker-1 python-worker-2
```

### Port Conflicts

```bash
# Check what's using ports
lsof -i :8000
lsof -i :5432

# Change ports in docker-compose.yml if needed
```

### Clean Start

```bash
# Stop everything
docker-compose down

# Remove volumes (WARNING: deletes all data)
docker-compose down -v

# Remove images
docker-compose down --rmi all

# Start fresh
docker-compose up -d
```

---

## Production Deployment

For production, update `docker-compose.yml`:

1. **Change passwords** in environment variables
2. **Use production database** (managed PostgreSQL)
3. **Configure GCS** for model storage
4. **Enable TLS/SSL** for all services
5. **Set resource limits**:

```yaml
deploy:
  resources:
    limits:
      cpus: '2'
      memory: 4G
    reservations:
      cpus: '1'
      memory: 2G
```

---

## Scaling

### Add More Workers

```bash
# Scale python workers
docker-compose up -d --scale python-worker-1=5

# Or edit docker-compose.yml to add more worker services
```

### Horizontal Scaling

For production:
- Use Kubernetes (see Phase 14)
- Deploy to Google Kubernetes Engine (GKE)
- Use Helm charts for configuration

---

## Useful Commands

```bash
# Start services
docker-compose up -d

# Stop services
docker-compose down

# Restart service
docker-compose restart api-gateway

# View logs
docker-compose logs -f

# Execute command in container
docker-compose exec api-gateway bash

# Check service status
docker-compose ps

# Rebuild specific service
docker-compose build api-gateway

# Pull latest images
docker-compose pull
```

---

## Testing Checklist

- [ ] All services start successfully
- [ ] Health checks pass for all services
- [ ] User registration and login works
- [ ] Group creation works
- [ ] Model upload completes
- [ ] Model search returns results
- [ ] Workers register with orchestrator
- [ ] Job submission succeeds
- [ ] Training job runs (check logs)
- [ ] Monitoring endpoints respond

---

## Next Steps

After successful testing:

1. **Phase 12**: Build dashboard UI
2. **Phase 13**: Implement comprehensive test suite
3. **Phase 14**: Production deployment (Kubernetes)
4. **Phase 15**: Security hardening

---

**Happy Testing!** 🚀
