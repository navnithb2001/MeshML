# REST API Contracts (OpenAPI/Swagger)

This directory contains OpenAPI 3.0 specifications for the MeshML REST API.

## 📁 Structure

```
api/
├── openapi.yaml          # Main OpenAPI specification
└── README.md             # This file
```

## 📖 API Documentation

### Overview

The MeshML REST API provides HTTP endpoints for:
- **Authentication**: User registration, login, JWT tokens
- **Groups**: Collaboration, RBAC, invitations
- **Models**: Custom PyTorch model upload and validation
- **Jobs**: Training job submission and monitoring
- **Workers**: Worker registration and health tracking
- **Metrics**: Training metrics and statistics

### Base URLs

- **Local**: `http://localhost:8000/api/v1`
- **Production**: `https://api.meshml.dev/api/v1`

### Authentication

All endpoints (except `/auth/*`) require JWT authentication:

```http
Authorization: Bearer <jwt_token>
```

**Token Lifecycle**:
1. Register: `POST /auth/register`
2. Login: `POST /auth/login` → Receive `access_token` + `refresh_token`
3. Use: Include `access_token` in `Authorization` header
4. Refresh: `POST /auth/refresh` with `refresh_token` → New `access_token`

**Token Expiry**:
- Access token: 1 hour
- Refresh token: 30 days

---

## 🚀 Quick Start

### View Interactive Documentation

```bash
# Install Swagger UI
npm install -g swagger-ui-watcher

# Serve interactive docs
swagger-ui-watcher api/openapi.yaml

# Open browser to http://localhost:8000
```

### Generate Client SDK

```bash
# Python client
openapi-generator-cli generate \
  -i api/openapi.yaml \
  -g python \
  -o sdk/python

# JavaScript/TypeScript client
openapi-generator-cli generate \
  -i api/openapi.yaml \
  -g typescript-axios \
  -o sdk/typescript

# Go client
openapi-generator-cli generate \
  -i api/openapi.yaml \
  -g go \
  -o sdk/go
```

### Validate Specification

```bash
# Install validator
npm install -g @apidevtools/swagger-cli

# Validate
swagger-cli validate api/openapi.yaml
```

---

## 📝 API Endpoints

### Authentication

| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/auth/register` | Register new user |
| POST | `/auth/login` | Login and get JWT |
| POST | `/auth/refresh` | Refresh access token |
| POST | `/auth/verify-email` | Verify email address |

### Users

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/users/me` | Get current user profile |
| PATCH | `/users/me` | Update current user profile |
| GET | `/users/{user_id}` | Get user by ID |

### Groups

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/groups` | List user's groups |
| POST | `/groups` | Create new group |
| GET | `/groups/{group_id}` | Get group details |
| PATCH | `/groups/{group_id}` | Update group |
| DELETE | `/groups/{group_id}` | Delete group |
| GET | `/groups/{group_id}/members` | List members |
| PUT | `/groups/{group_id}/members/{user_id}/role` | Update member role |
| DELETE | `/groups/{group_id}/members/{user_id}` | Remove member |
| GET | `/groups/{group_id}/invitations` | List invitations |
| POST | `/groups/{group_id}/invitations` | Create invitation |
| POST | `/invitations/{token}/accept` | Accept invitation |
| POST | `/invitations/{token}/reject` | Reject invitation |

### Models

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/models` | List models |
| POST | `/models` | Upload model file |
| GET | `/models/{model_id}` | Get model details |
| DELETE | `/models/{model_id}` | Delete model |
| GET | `/models/{model_id}/download` | Download model file |

### Jobs

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/jobs` | List jobs |
| POST | `/jobs` | Create new job |
| GET | `/jobs/{job_id}` | Get job details |
| DELETE | `/jobs/{job_id}` | Delete job |
| POST | `/jobs/{job_id}/stop` | Stop job |
| POST | `/jobs/{job_id}/pause` | Pause job |
| POST | `/jobs/{job_id}/resume` | Resume job |
| GET | `/jobs/{job_id}/metrics` | Get job metrics |
| GET | `/jobs/{job_id}/download/model` | Download trained model |
| GET | `/jobs/{job_id}/download/report` | Download training report |

### Workers

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/workers` | List workers |
| GET | `/workers/{worker_id}` | Get worker details |
| DELETE | `/workers/{worker_id}` | Unregister worker |
| PUT | `/workers/{worker_id}/heartbeat` | Manual heartbeat |

### System

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/health` | Health check |
| GET | `/metrics` | System metrics (Prometheus) |

---

## 💡 Usage Examples

### Register and Login

```bash
# Register
curl -X POST http://localhost:8000/api/v1/auth/register \
  -H "Content-Type: application/json" \
  -d '{
    "email": "alice@university.edu",
    "username": "alice",
    "password": "SecurePass123!",
    "full_name": "Alice Johnson"
  }'

# Login
curl -X POST http://localhost:8000/api/v1/auth/login \
  -H "Content-Type: application/json" \
  -d '{
    "email": "alice@university.edu",
    "password": "SecurePass123!"
  }'

# Response:
{
  "access_token": "eyJhbGciOiJIUzI1NiIs...",
  "refresh_token": "eyJhbGciOiJIUzI1NiIs...",
  "token_type": "bearer",
  "expires_in": 3600,
  "user": {
    "id": 1,
    "email": "alice@university.edu",
    "username": "alice",
    "is_verified": false
  }
}
```

### Create Group

```bash
curl -X POST http://localhost:8000/api/v1/groups \
  -H "Authorization: Bearer <token>" \
  -H "Content-Type: application/json" \
  -d '{
    "name": "AI Research Lab",
    "description": "Deep learning research group"
  }'
```

### Upload Model

```bash
curl -X POST http://localhost:8000/api/v1/models \
  -H "Authorization: Bearer <token>" \
  -F "group_id=1" \
  -F "name=resnet50-custom" \
  -F "description=Custom ResNet-50 for ImageNet" \
  -F "architecture=CNN" \
  -F "model_file=@/path/to/model.py"
```

### Create Training Job

```bash
curl -X POST http://localhost:8000/api/v1/jobs \
  -H "Authorization: Bearer <token>" \
  -H "Content-Type: application/json" \
  -d '{
    "name": "ImageNet Training",
    "group_id": 1,
    "model_id": 5,
    "dataset_path": "gs://meshml-datasets/imagenet",
    "total_epochs": 100,
    "config": {
      "learning_rate": 0.001,
      "batch_size": 32,
      "optimizer": "adam"
    }
  }'
```

### Monitor Job Progress

```bash
# Get job details
curl -X GET http://localhost:8000/api/v1/jobs/1 \
  -H "Authorization: Bearer <token>"

# Get metrics
curl -X GET http://localhost:8000/api/v1/jobs/1/metrics \
  -H "Authorization: Bearer <token>"
```

### Invite Group Member

```bash
curl -X POST http://localhost:8000/api/v1/groups/1/invitations \
  -H "Authorization: Bearer <token>" \
  -H "Content-Type: application/json" \
  -d '{
    "email": "bob@university.edu",
    "role": "member"
  }'
```

---

## 📊 Response Codes

| Code | Meaning |
|------|---------|
| 200 | Success |
| 201 | Created |
| 204 | No Content (success with no response body) |
| 400 | Bad Request (validation error) |
| 401 | Unauthorized (invalid/expired token) |
| 403 | Forbidden (insufficient permissions) |
| 404 | Not Found |
| 409 | Conflict (duplicate resource) |
| 413 | Payload Too Large |
| 429 | Too Many Requests (rate limit) |
| 500 | Internal Server Error |

---

## 🔒 Security

### Rate Limiting

- **Authenticated users**: 1000 requests/hour
- **Unauthenticated**: 100 requests/hour

Rate limit info in response headers:
```
X-RateLimit-Limit: 1000
X-RateLimit-Remaining: 987
X-RateLimit-Reset: 1709567890
```

### CORS

CORS is enabled for:
- `http://localhost:3000` (local development)
- `https://app.meshml.dev` (production frontend)

### File Upload Limits

- **Model files**: Max 100 MB
- **Dataset files**: Max 10 GB (with chunked upload)

---

## 🧪 Testing

### Using HTTPie

```bash
# Install
pip install httpie

# Register
http POST localhost:8000/api/v1/auth/register \
  email=alice@edu.com \
  username=alice \
  password=pass123

# Login and save token
http POST localhost:8000/api/v1/auth/login \
  email=alice@edu.com \
  password=pass123 \
  | jq -r .access_token > token.txt

# Use token
http GET localhost:8000/api/v1/users/me \
  "Authorization: Bearer $(cat token.txt)"
```

### Using Postman

1. Import `api/openapi.yaml` into Postman
2. Configure environment variables:
   - `base_url`: `http://localhost:8000/api/v1`
   - `token`: (set after login)
3. Use collection with pre-configured requests

---

## 📚 Schema Documentation

### Key Data Models

**User**:
```json
{
  "id": 1,
  "email": "alice@university.edu",
  "username": "alice",
  "full_name": "Alice Johnson",
  "is_active": true,
  "is_verified": true,
  "created_at": "2026-03-04T10:00:00Z"
}
```

**Group**:
```json
{
  "id": 1,
  "name": "AI Research Lab",
  "description": "Deep learning research",
  "owner_id": 1,
  "is_active": true,
  "created_at": "2026-03-04T10:00:00Z"
}
```

**Job**:
```json
{
  "id": 1,
  "name": "ImageNet Training",
  "group_id": 1,
  "model_id": 5,
  "status": "running",
  "progress": 45.5,
  "current_epoch": 45,
  "total_epochs": 100,
  "started_at": "2026-03-04T10:00:00Z"
}
```

---

## 🔜 Next Steps

- **TASK-2.3**: GraphQL schema for metrics
- **Phase 3**: API Gateway implementation with FastAPI
- **Phase 4**: Model validation service

---

## 📖 References

- [OpenAPI Specification](https://swagger.io/specification/)
- [Swagger Editor](https://editor.swagger.io/)
- [OpenAPI Generator](https://openapi-generator.tech/)
