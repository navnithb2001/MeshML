# 🚀 MeshML Quick Start Guide

Get your distributed ML training platform running in 5 minutes!

## Prerequisites

- Docker Desktop installed and running
- 8GB+ RAM available
- curl and jq installed

## Step 1: Start Services (1 minute)

```bash
cd /Users/navnithbharadwaj/Desktop/autoapply/MeshML

# Start all services
make docker-up

# Or manually:
docker-compose up -d
```

## Step 2: Wait for Services (30 seconds)

```bash
# Check if services are healthy
make docker-health

# Expected output:
# API Gateway:        healthy
# Model Registry:     healthy
# Dataset Sharder:    healthy
# Task Orchestrator:  healthy
# Parameter Server:   healthy
```

## Step 3: Run Integration Tests (2 minutes)

```bash
# Run automated end-to-end test
make test-integration

# Or manually:
./tests/integration/test_e2e.sh
```

Expected result: All 10 steps should pass ✅

## Step 4: Manual Testing (2 minutes)

### Test 1: Register User
```bash
curl -X POST http://localhost:8000/api/v1/auth/register \
  -H "Content-Type: application/json" \
  -d '{
    "email": "demo@meshml.com",
    "password": "demo123",
    "full_name": "Demo User"
  }'
```

### Test 2: Login
```bash
curl -X POST http://localhost:8000/api/v1/auth/login \
  -H "Content-Type: application/json" \
  -d '{
    "email": "demo@meshml.com",
    "password": "demo123"
  }'
```

Save the `access_token` from response.

### Test 3: Create Group
```bash
export TOKEN="your_access_token_here"

curl -X POST http://localhost:8000/api/v1/groups \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "name": "ML Team",
    "description": "My first group"
  }'
```

### Test 4: Upload Model
```bash
curl -X POST http://localhost:8004/api/v1/models \
  -H "Content-Type: application/json" \
  -d '{
    "name": "My First Model",
    "group_id": 1,
    "architecture_type": "CNN"
  }'
```

## What's Running?

| Service | Port | URL |
|---------|------|-----|
| API Gateway | 8000 | http://localhost:8000 |
| API Docs | 8000 | http://localhost:8000/docs |
| Model Registry | 8004 | http://localhost:8004 |
| Dataset Sharder | 8001 | http://localhost:8001 |
| Task Orchestrator | 8002 | http://localhost:8002 |
| Parameter Server | 8003 | http://localhost:8003 |
| PostgreSQL | 5432 | localhost:5432 |
| Redis | 6379 | localhost:6379 |

## Useful Commands

```bash
# View logs
make docker-logs

# Check status
make docker-status

# Stop services
make docker-down

# Restart services
make docker-restart

# Clean everything
make docker-clean
```

## Next Steps

1. ✅ Explore API documentation: http://localhost:8000/docs
2. ✅ Submit a training job
3. ✅ Monitor worker progress
4. ✅ Try model versioning
5. ✅ Test group collaboration

## Troubleshooting

**Services won't start?**
```bash
docker-compose logs
docker-compose down -v
docker-compose up -d
```

**Port conflicts?**
```bash
# Check what's using the ports
lsof -i :8000
lsof -i :5432
```

**Database issues?**
```bash
# Reset database
docker-compose down -v
docker-compose up -d
```

## Full Documentation

See `docs/DOCKER_TESTING_GUIDE.md` for comprehensive testing guide.

**Happy ML Training!** 🎉
