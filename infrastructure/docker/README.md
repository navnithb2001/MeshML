# MeshML Development Environment

This directory contains Docker Compose configurations for local development.

## Quick Start

```bash
# Start core services (PostgreSQL, Redis, MinIO)
docker-compose up -d postgres redis minio

# Start all services including monitoring
docker-compose up -d

# Start with optional management tools (pgAdmin, Redis Commander)
docker-compose --profile tools up -d

# View logs
docker-compose logs -f

# Stop all services
docker-compose down

# Stop and remove volumes (⚠️ destroys data)
docker-compose down -v
```

## Services

### Core Services

| Service | Port | Credentials | Purpose |
|---------|------|-------------|---------|
| **PostgreSQL** | 5432 | `meshml_user` / `meshml_dev_password` | Primary database |
| **Redis** | 6379 | Password: `meshml_redis_password` | Cache & pub/sub |
| **MinIO** | 9000 (API), 9001 (Console) | `minioadmin` / `minioadmin123` | Object storage |

### Monitoring Services

| Service | Port | Credentials | Purpose |
|---------|------|-------------|---------|
| **Prometheus** | 9090 | None | Metrics collection |
| **Grafana** | 3000 | `admin` / `admin123` | Metrics visualization |
| **Jaeger** | 16686 | None | Distributed tracing |

### Optional Management Tools (--profile tools)

| Service | Port | Credentials | Purpose |
|---------|------|-------------|---------|
| **pgAdmin** | 5050 | `admin@meshml.local` / `admin123` | PostgreSQL GUI |
| **Redis Commander** | 8081 | None | Redis GUI |

## Configuration

### Environment Variables

Create a `.env` file in this directory to override defaults:

```bash
# PostgreSQL
POSTGRES_DB=meshml
POSTGRES_USER=meshml_user
POSTGRES_PASSWORD=your_secure_password

# Redis
REDIS_PASSWORD=your_redis_password

# MinIO
MINIO_ROOT_USER=your_minio_user
MINIO_ROOT_PASSWORD=your_minio_password
```

### Connection Strings

Use these in your application config:

```python
# PostgreSQL
DATABASE_URL = "postgresql://meshml_user:meshml_dev_password@localhost:5432/meshml"

# Redis
REDIS_URL = "redis://:meshml_redis_password@localhost:6379/0"

# MinIO (S3-compatible)
S3_ENDPOINT = "http://localhost:9000"
S3_ACCESS_KEY = "minioadmin"
S3_SECRET_KEY = "minioadmin123"
```

## Database Initialization

The PostgreSQL container will automatically run SQL scripts from `../../database/schema/` on first startup.

To manually initialize or reset:

```bash
# Stop and remove the database
docker-compose down -v postgres

# Restart (will re-run init scripts)
docker-compose up -d postgres
```

## Accessing Services

### MinIO Console
- URL: http://localhost:9001
- Create a bucket named `meshml-datasets` for dataset storage

### Grafana Dashboards
- URL: http://localhost:3000
- Pre-configured dashboards will be loaded from `monitoring/grafana/dashboards/`

### Jaeger UI
- URL: http://localhost:16686
- View distributed traces from services

### pgAdmin (Optional)
- URL: http://localhost:5050
- Add server: Host=`postgres`, Port=`5432`, User=`meshml_user`

## Health Checks

All services include health checks. View status:

```bash
docker-compose ps
```

## Troubleshooting

### Port Conflicts

If ports are already in use, edit `docker-compose.yml` to change mappings:

```yaml
ports:
  - "5433:5432"  # Change host port
```

### Permission Errors

On Linux, you may need to fix volume permissions:

```bash
sudo chown -R $USER:$USER postgres_data redis_data
```

### Clear All Data

```bash
docker-compose down -v
docker volume prune
```

## Production Configuration

For production, use `docker-compose.prod.yml`:

```bash
docker-compose -f docker-compose.prod.yml up -d
```

Key differences:
- Stronger passwords (from secrets)
- No management tools
- Resource limits configured
- Logging to external collectors
