# MeshML API Gateway

FastAPI-based REST API for MeshML distributed training platform.

## Features

- **Authentication**: JWT-based user authentication
- **Group Management**: Create and manage training groups with RBAC
- **Invitations**: Invite workers to groups with expiring codes
- **Job Management**: Submit and monitor training jobs
- **Worker Registration**: Register workers with capability detection
- **Monitoring**: Real-time metrics and system health

## Quick Start

### Prerequisites

- Python 3.10+
- PostgreSQL 14+
- Redis 6+

### Installation

```bash
# Install dependencies
pip install -r requirements.txt

# Copy environment file
cp .env.example .env

# Edit .env with your configuration
nano .env
```

### Database Setup

```bash
# Start PostgreSQL (Docker example)
docker run -d \
  --name meshml-postgres \
  -e POSTGRES_USER=meshml \
  -e POSTGRES_PASSWORD=meshml \
  -e POSTGRES_DB=meshml \
  -p 5432:5432 \
  postgres:14

# Start Redis
docker run -d \
  --name meshml-redis \
  -p 6379:6379 \
  redis:7-alpine
```

### Run Server

```bash
# Development mode
python -m app.main

# Or with uvicorn
uvicorn app.main:app --reload --port 8000

# Production mode
uvicorn app.main:app --host 0.0.0.0 --port 8000 --workers 4
```

### Verify Installation

```bash
# Health check
curl http://localhost:8000/health

# API documentation
open http://localhost:8000/docs
```

## API Endpoints

### Authentication
```
POST   /api/auth/register      - Register user
POST   /api/auth/login         - Login (get JWT)
GET    /api/auth/me            - Current user
POST   /api/auth/refresh       - Refresh token
```

### Groups
```
POST   /api/groups                             - Create group
GET    /api/groups/public                      - List public groups
GET    /api/groups/{id}                        - Group details
POST   /api/groups/{id}/join                   - Join public group
GET    /api/groups/{id}/members                - List members
PUT    /api/groups/{id}/members/{user_id}/role - Update role
DELETE /api/groups/{id}/members/{user_id}      - Remove member
```

### Invitations
```
POST   /api/groups/{id}/invitations  - Create invitation
POST   /api/invitations/accept       - Accept invitation
GET    /api/invitations/{code}       - Invitation details
DELETE /api/invitations/{code}       - Revoke invitation
```

### Jobs
```
POST   /api/jobs             - Submit job
GET    /api/jobs             - List jobs
GET    /api/jobs/{id}        - Job details
DELETE /api/jobs/{id}        - Cancel job
GET    /api/jobs/{id}/progress - Training progress
```

### Workers
```
POST   /api/workers/register                 - Register worker
GET    /api/workers                          - List workers
GET    /api/workers/{id}                     - Worker details
PUT    /api/workers/{id}/capabilities        - Update capabilities
POST   /api/workers/{id}/heartbeat           - Heartbeat
DELETE /api/workers/{id}                     - Deregister
```

### Monitoring
```
GET    /api/monitoring/health              - Health check
GET    /api/monitoring/metrics/realtime    - Real-time metrics
GET    /api/monitoring/workers             - Worker status
GET    /api/monitoring/groups/{id}/stats   - Group stats
```

## Authentication

All endpoints except `/health` and `/auth/*` require authentication.

### Get Token

```bash
# Register user
curl -X POST http://localhost:8000/api/auth/register \
  -H "Content-Type: application/json" \
  -d '{"email": "user@example.com", "password": "password123", "full_name": "Test User"}'

# Login
curl -X POST http://localhost:8000/api/auth/login \
  -H "Content-Type: application/json" \
  -d '{"email": "user@example.com", "password": "password123"}'
```

### Use Token

```bash
# Set token
export TOKEN="eyJ0eXAiOiJKV1QiLCJhbGc..."

# Make authenticated request
curl -H "Authorization: Bearer $TOKEN" \
  http://localhost:8000/api/auth/me
```

## Configuration

Environment variables (`.env`):

```bash
# Database
DATABASE_URL=postgresql+asyncpg://user:pass@host:port/db

# Redis
REDIS_URL=redis://localhost:6379/0

# JWT
JWT_SECRET_KEY=your-secret-key
JWT_EXPIRE_MINUTES=1440

# Server
HOST=0.0.0.0
PORT=8000
```

## Development

### Project Structure

```
app/
├── main.py              # FastAPI application
├── models/              # SQLAlchemy models
│   ├── user.py
│   ├── group.py
│   ├── worker.py
│   └── job.py
├── schemas/             # Pydantic schemas
│   ├── auth.py
│   ├── group.py
│   ├── invitation.py
│   ├── worker.py
│   └── job.py
├── routers/             # API endpoints
│   ├── auth.py
│   ├── groups.py
│   ├── invitations.py
│   ├── jobs.py
│   ├── workers.py
│   └── monitoring.py
├── middleware/          # Custom middleware
│   └── security.py
└── utils/               # Utilities
    ├── database.py
    ├── redis_client.py
    ├── security.py
    └── db_init.py
```

### Run Tests

```bash
# Install test dependencies
pip install pytest pytest-asyncio pytest-cov

# Run tests
pytest tests/ -v

# With coverage
pytest tests/ --cov=app --cov-report=html
```

## Docker Deployment

```bash
# Build image
docker build -t meshml-api-gateway .

# Run container
docker run -d \
  --name meshml-api \
  -p 8000:8000 \
  --env-file .env \
  meshml-api-gateway
```

## Documentation

- **Interactive API Docs**: http://localhost:8000/docs
- **ReDoc**: http://localhost:8000/redoc
- **OpenAPI JSON**: http://localhost:8000/openapi.json

## License

MIT
