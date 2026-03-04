# API Gateway Service

FastAPI-based API Gateway for MeshML - implements REST API contracts defined in `/api/openapi.yaml`.

## 📁 Structure

```
api_gateway/
├── app/
│   ├── __init__.py
│   ├── main.py                 # FastAPI application entry point
│   ├── config.py               # Configuration management
│   ├── dependencies.py         # Dependency injection
│   │
│   ├── api/                    # API routes
│   │   ├── __init__.py
│   │   ├── v1/
│   │   │   ├── __init__.py
│   │   │   ├── auth.py         # Authentication endpoints
│   │   │   ├── users.py        # User management
│   │   │   ├── groups.py       # Group collaboration
│   │   │   ├── models.py       # Model upload/management
│   │   │   ├── jobs.py         # Training jobs
│   │   │   ├── workers.py      # Worker management
│   │   │   └── system.py       # Health, metrics
│   │
│   ├── core/                   # Core functionality
│   │   ├── __init__.py
│   │   ├── security.py         # JWT, password hashing
│   │   ├── permissions.py      # RBAC logic
│   │   └── exceptions.py       # Custom exceptions
│   │
│   ├── models/                 # SQLAlchemy models (from Phase 1)
│   │   ├── __init__.py
│   │   ├── user.py
│   │   ├── group.py
│   │   ├── job.py
│   │   ├── worker.py
│   │   └── model.py
│   │
│   ├── schemas/                # Pydantic schemas (request/response)
│   │   ├── __init__.py
│   │   ├── auth.py
│   │   ├── user.py
│   │   ├── group.py
│   │   ├── job.py
│   │   ├── worker.py
│   │   └── model.py
│   │
│   ├── crud/                   # CRUD operations
│   │   ├── __init__.py
│   │   ├── user.py
│   │   ├── group.py
│   │   ├── job.py
│   │   ├── worker.py
│   │   └── model.py
│   │
│   └── middleware/             # Custom middleware
│       ├── __init__.py
│       ├── error_handler.py
│       └── rate_limiter.py
│
├── tests/
│   ├── __init__.py
│   ├── conftest.py
│   ├── test_auth.py
│   ├── test_groups.py
│   ├── test_jobs.py
│   └── test_workers.py
│
├── requirements.txt
├── Dockerfile
└── README.md
```

## 🚀 Quick Start

### Development

```bash
# Install dependencies
pip install -r requirements.txt

# Set environment variables
export DATABASE_URL="postgresql://user:pass@localhost:5432/meshml"
export REDIS_URL="redis://localhost:6379/0"
export SECRET_KEY="your-secret-key"

# Run development server
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

### Docker

```bash
# Build image
docker build -t meshml-api-gateway .

# Run container
docker run -p 8000:8000 \
  -e DATABASE_URL="postgresql://..." \
  -e REDIS_URL="redis://..." \
  meshml-api-gateway
```

## 📖 API Documentation

Once running, visit:
- **Swagger UI**: http://localhost:8000/docs
- **ReDoc**: http://localhost:8000/redoc
- **OpenAPI JSON**: http://localhost:8000/openapi.json

## 🔐 Authentication

All endpoints (except `/auth/*`) require JWT authentication:

```bash
# Register
curl -X POST http://localhost:8000/api/v1/auth/register \
  -H "Content-Type: application/json" \
  -d '{"email": "user@example.com", "username": "user", "password": "pass123"}'

# Login
curl -X POST http://localhost:8000/api/v1/auth/login \
  -H "Content-Type: application/json" \
  -d '{"email": "user@example.com", "password": "pass123"}'

# Use token
curl -H "Authorization: Bearer <token>" \
  http://localhost:8000/api/v1/users/me
```

## 🧪 Testing

```bash
# Run all tests
pytest

# Run with coverage
pytest --cov=app tests/

# Run specific test file
pytest tests/test_auth.py -v
```

## 📦 Dependencies

- **FastAPI**: Web framework
- **SQLAlchemy**: ORM for PostgreSQL
- **Redis**: Caching and session storage
- **Pydantic**: Data validation
- **python-jose**: JWT tokens
- **passlib**: Password hashing
- **uvicorn**: ASGI server
- **pytest**: Testing framework

## 🔧 Configuration

Configuration is managed via environment variables (see `app/config.py`):

| Variable | Description | Default |
|----------|-------------|---------|
| `DATABASE_URL` | PostgreSQL connection string | Required |
| `REDIS_URL` | Redis connection string | Required |
| `SECRET_KEY` | JWT signing key | Required |
| `ACCESS_TOKEN_EXPIRE_MINUTES` | JWT expiry time | 60 |
| `CORS_ORIGINS` | Allowed CORS origins | `["*"]` |
| `ENVIRONMENT` | Deployment environment | `development` |

## 🛣️ API Routes

### Authentication
- `POST /api/v1/auth/register` - Register new user
- `POST /api/v1/auth/login` - Login
- `POST /api/v1/auth/refresh` - Refresh token
- `POST /api/v1/auth/verify-email` - Verify email

### Users
- `GET /api/v1/users/me` - Get current user
- `PATCH /api/v1/users/me` - Update profile
- `GET /api/v1/users/{user_id}` - Get user by ID

### Groups
- `GET /api/v1/groups` - List groups
- `POST /api/v1/groups` - Create group
- `GET /api/v1/groups/{group_id}` - Get group
- `PATCH /api/v1/groups/{group_id}` - Update group
- `DELETE /api/v1/groups/{group_id}` - Delete group
- `POST /api/v1/groups/{group_id}/invitations` - Invite member
- `POST /api/v1/invitations/{token}/accept` - Accept invitation

### Models
- `GET /api/v1/models` - List models
- `POST /api/v1/models` - Upload model
- `GET /api/v1/models/{model_id}` - Get model
- `DELETE /api/v1/models/{model_id}` - Delete model

### Jobs
- `GET /api/v1/jobs` - List jobs
- `POST /api/v1/jobs` - Create job
- `GET /api/v1/jobs/{job_id}` - Get job
- `DELETE /api/v1/jobs/{job_id}` - Delete job
- `POST /api/v1/jobs/{job_id}/stop` - Stop job

### Workers
- `GET /api/v1/workers` - List workers
- `GET /api/v1/workers/{worker_id}` - Get worker
- `DELETE /api/v1/workers/{worker_id}` - Unregister worker

### System
- `GET /api/v1/health` - Health check
- `GET /api/v1/metrics` - Prometheus metrics

## 🔒 Security

- **Password Hashing**: bcrypt with salt
- **JWT Tokens**: RS256 signing algorithm
- **CORS**: Configurable allowed origins
- **Rate Limiting**: 1000 req/hour (authenticated), 100 req/hour (unauthenticated)
- **Input Validation**: Pydantic schemas
- **SQL Injection Protection**: SQLAlchemy ORM
- **HTTPS**: Required in production

## 📊 Monitoring

- **Health Endpoint**: `/api/v1/health`
- **Prometheus Metrics**: `/api/v1/metrics`
- **Logging**: Structured JSON logs

## 🚧 Development

### Adding a New Endpoint

1. Define Pydantic schemas in `app/schemas/`
2. Create CRUD operations in `app/crud/`
3. Add route in `app/api/v1/`
4. Write tests in `tests/`

### Example:

```python
# app/schemas/example.py
from pydantic import BaseModel

class ExampleCreate(BaseModel):
    name: str
    value: int

# app/api/v1/example.py
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from app.dependencies import get_db

router = APIRouter()

@router.post("/examples")
async def create_example(
    data: ExampleCreate,
    db: Session = Depends(get_db)
):
    # Implementation
    return {"id": 1, "name": data.name}
```

## 📚 References

- [FastAPI Documentation](https://fastapi.tiangolo.com/)
- [SQLAlchemy Documentation](https://docs.sqlalchemy.org/)
- [Pydantic Documentation](https://docs.pydantic.dev/)
- [OpenAPI Specification](../../api/openapi.yaml)
