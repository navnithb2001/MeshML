# MeshML Model Registry Service

Complete model lifecycle management, storage, and discovery service for MeshML distributed training platform.

## Features

### ✅ TASK-11.1: Model Storage Infrastructure
- **GCS Integration**: Models stored in Google Cloud Storage (`gs://meshml-models/`)
- **Directory Structure**: `models/{model_id}/model.py`
- **Metadata Storage**: PostgreSQL models table with full metadata
- **File Management**: Upload, download, delete operations with signed URLs
- **Hash Verification**: SHA-256 hash for file integrity

### ✅ TASK-11.2: Model Lifecycle Management
- **State Machine**: 5 states with validated transitions
  - `UPLOADING` → `VALIDATING` → `READY`
  - `UPLOADING`/`VALIDATING` → `FAILED`
  - `READY` → `DEPRECATED`
- **Versioning**: Semantic versioning with parent-child relationships
- **Version History**: Track all model versions
- **Automatic Validation**: Integration points for validation service

### ✅ TASK-11.3: Model Search & Discovery
- **Text Search**: Search in name and description
- **Advanced Filters**: Group, state, architecture type, dataset type, creator
- **Pagination**: Configurable page sizes (1-100 items)
- **Group Models**: List all models in a group
- **Popular Models**: Sort by usage and download count
- **Recent Models**: Latest uploads
- **Usage Tracking**: Job usage statistics per model

## API Endpoints

### Model Management (9 endpoints)
```
POST   /api/v1/models                    - Create model entry
GET    /api/v1/models/{id}               - Get model details
PUT    /api/v1/models/{id}               - Update metadata
DELETE /api/v1/models/{id}               - Delete model (deprecate)
POST   /api/v1/models/{id}/upload-url    - Get signed upload URL
POST   /api/v1/models/{id}/upload        - Direct file upload
GET    /api/v1/models/{id}/download      - Get download URL
POST   /api/v1/models/{id}/state         - Update model state
```

### Search & Discovery (9 endpoints)
```
GET    /api/v1/search/models              - Search with filters
GET    /api/v1/search/groups/{id}/models  - List group models
GET    /api/v1/search/users/{id}/models   - List user models
GET    /api/v1/search/architecture-types  - List architectures
GET    /api/v1/search/dataset-types       - List dataset types
GET    /api/v1/search/models/{id}/usage   - Model usage stats
GET    /api/v1/search/popular             - Popular models
GET    /api/v1/search/recent              - Recent models
```

### Lifecycle Management (7 endpoints)
```
GET    /api/v1/lifecycle/states                        - Available states
GET    /api/v1/lifecycle/state/{state}                 - Models by state
POST   /api/v1/lifecycle/{id}/validate                 - Start validation
POST   /api/v1/lifecycle/{id}/mark-ready               - Mark ready
POST   /api/v1/lifecycle/{id}/mark-failed              - Mark failed
POST   /api/v1/lifecycle/{id}/deprecate                - Deprecate
GET    /api/v1/lifecycle/{id}/can-transition/{state}   - Check transition
```

### Version Management (6 endpoints)
```
POST   /api/v1/versions                       - Create new version
GET    /api/v1/versions/{parent_id}           - Get all versions
GET    /api/v1/versions/{parent_id}/latest    - Get latest version
GET    /api/v1/versions/{id}/history          - Version history
GET    /api/v1/versions/{parent_id}/count     - Version count
GET    /api/v1/versions/{parent_id}/suggest-next - Suggest next version
POST   /api/v1/versions/increment             - Increment version utility
```

**Total: 32 HTTP endpoints**

## Architecture

### Database Schema
```sql
-- Extends Phase 1 models table
CREATE TABLE models (
    id SERIAL PRIMARY KEY,
    name VARCHAR(255) NOT NULL,
    description TEXT,
    group_id INTEGER REFERENCES groups(id),
    created_by_user_id INTEGER REFERENCES users(id),
    
    -- Storage
    gcs_path VARCHAR(512),
    file_size_bytes INTEGER,
    file_hash VARCHAR(64),
    
    -- Lifecycle
    state VARCHAR(20) DEFAULT 'uploading',
    validation_message TEXT,
    
    -- Metadata
    architecture_type VARCHAR(100),
    dataset_type VARCHAR(100),
    framework VARCHAR(50) DEFAULT 'PyTorch',
    metadata JSONB,
    
    -- Versioning
    version VARCHAR(50) DEFAULT '1.0.0',
    parent_model_id INTEGER REFERENCES models(id),
    
    -- Statistics
    usage_count INTEGER DEFAULT 0,
    download_count INTEGER DEFAULT 0,
    
    -- Timestamps
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW(),
    deprecated_at TIMESTAMP
);

CREATE TABLE model_usage (
    id SERIAL PRIMARY KEY,
    model_id INTEGER REFERENCES models(id),
    job_id INTEGER REFERENCES jobs(id),
    started_at TIMESTAMP DEFAULT NOW(),
    completed_at TIMESTAMP
);
```

### State Machine
```
UPLOADING ──────► VALIDATING ──────► READY ──────► DEPRECATED
    │                  │
    │                  │
    └──────────────────┴──────► FAILED
```

### Storage Structure
```
gs://meshml-models/
└── models/
    ├── 1/
    │   └── model.py
    ├── 2/
    │   └── model.py
    └── 3/
        └── model.py
```

## Setup

### 1. Install Dependencies
```bash
cd services/model-registry
pip install -r requirements.txt
```

### 2. Configure Environment
```bash
cp .env.example .env
# Edit .env with your settings
```

### 3. Setup Database
```bash
# Run from services/database
alembic upgrade head
```

### 4. Setup GCS Bucket
```bash
# Option 1: Using gcloud CLI
gcloud storage buckets create gs://meshml-models --location=US

# Option 2: Automatic creation
# The service will create the bucket if it doesn't exist
```

### 5. Run Service
```bash
# Development
python -m app.main

# Production
uvicorn app.main:app --host 0.0.0.0 --port 8004
```

## Usage Examples

### 1. Create Model
```python
import requests

response = requests.post("http://localhost:8004/api/v1/models", json={
    "name": "ResNet-50 CIFAR-10",
    "description": "ResNet-50 trained on CIFAR-10 dataset",
    "group_id": 1,
    "architecture_type": "CNN",
    "dataset_type": "CIFAR-10",
    "metadata": {
        "num_parameters": 25557032,
        "input_shape": [3, 32, 32],
        "output_shape": [10]
    }
})

model_id = response.json()["id"]
```

### 2. Upload Model File
```python
# Option A: Direct upload
with open("model.py", "rb") as f:
    files = {"file": f}
    response = requests.post(
        f"http://localhost:8004/api/v1/models/{model_id}/upload",
        files=files
    )

# Option B: Signed URL (for large files)
response = requests.post(
    f"http://localhost:8004/api/v1/models/{model_id}/upload-url"
)
upload_url = response.json()["upload_url"]

# Upload directly to GCS
with open("model.py", "rb") as f:
    requests.put(upload_url, data=f, headers={"Content-Type": "text/x-python"})
```

### 3. Search Models
```python
# Text search
response = requests.get(
    "http://localhost:8004/api/v1/search/models",
    params={
        "query": "resnet",
        "architecture_type": "CNN",
        "state": "ready",
        "page": 1,
        "page_size": 20
    }
)

models = response.json()["models"]
```

### 4. Create Version
```python
response = requests.post("http://localhost:8004/api/v1/versions", json={
    "name": "ResNet-50 CIFAR-10 v2",
    "parent_model_id": model_id,
    "version": "2.0.0",
    "description": "Improved accuracy with data augmentation"
})
```

### 5. Download Model
```python
response = requests.get(
    f"http://localhost:8004/api/v1/models/{model_id}/download"
)
download_url = response.json()["download_url"]

# Download from GCS
model_code = requests.get(download_url).text
```

## Testing

```bash
# Run all tests
pytest tests/

# With coverage
pytest tests/ --cov=app --cov-report=html

# Specific test file
pytest tests/test_models.py -v
```

## Integration with Other Services

### API Gateway
- Provides user authentication
- Forwards model requests to registry

### Validation Service (Phase 4)
- Receives model upload notifications
- Validates model code
- Calls `/lifecycle/{id}/mark-ready` or `/lifecycle/{id}/mark-failed`

### Task Orchestrator (Phase 6)
- Queries models by group for job submission
- Tracks model usage via ModelUsage table

### Python Worker (Phase 8)
- Downloads models from GCS for training
- Uses signed download URLs

## Performance Considerations

- **Signed URLs**: Client uploads/downloads directly to/from GCS (no proxy)
- **Pagination**: Default 20 items, max 100
- **Indexing**: Indexes on group_id, state, created_at, architecture_type
- **Async Operations**: All I/O operations are async

## Security

- **Access Control**: Model access controlled by group membership
- **Signed URLs**: Time-limited (1 hour) signed URLs for GCS
- **Input Validation**: Pydantic schemas validate all inputs
- **File Size Limits**: Max 100MB per model file
- **File Type Validation**: Only .py files accepted

## Monitoring

- **Health Check**: `GET /health`
- **Metrics**: Model count by state, upload/download rates
- **Logs**: Structured logging with correlation IDs

## Environment Variables

See `.env.example` for all configuration options.

## Port

**Default Port: 8004**

## Dependencies

- PostgreSQL 15+ (from Phase 1)
- Google Cloud Storage
- Python 3.11+
- FastAPI 0.109.2

## Phase 11 Completion

✅ **TASK-11.1**: Model storage infrastructure (GCS, directory structure, metadata)  
✅ **TASK-11.2**: Model lifecycle management (state machine, versioning, retrieval)  
✅ **TASK-11.3**: Model search & discovery (filters, group models, usage tracking)

**Status**: Phase 11 Complete! 🎉
