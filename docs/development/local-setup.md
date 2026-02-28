# Local Development Setup Guide

This guide walks you through setting up the MeshML development environment on your local machine.

## Prerequisites

### Required Software

- **Python**: 3.11 or higher
- **Docker**: 24.0 or higher
- **Docker Compose**: 2.20 or higher
- **Git**: 2.30 or higher

### Optional (for specific components)

- **Node.js**: 18+ (for Dashboard and JS Worker)
- **CMake**: 3.20+ (for C++ Worker)
- **C++ Compiler**: GCC 11+, Clang 14+, or MSVC 2022
- **CUDA Toolkit**: 12.0+ (for GPU acceleration)

## Quick Start (5 minutes)

```bash
# 1. Clone the repository
git clone https://github.com/yourusername/meshml.git
cd meshml

# 2. Run the automated setup
./scripts/setup/install_deps.sh

# 3. Initialize the database
./scripts/setup/init_db.sh

# Done! Services are ready to develop
```

## Detailed Setup

### 1. Clone and Navigate

```bash
git clone https://github.com/yourusername/meshml.git
cd meshml
```

### 2. Install Pre-commit Hooks

```bash
pip install pre-commit
pre-commit install
```

This ensures code quality checks run automatically before each commit.

### 3. Start Infrastructure Services

```bash
cd infrastructure/docker
docker-compose up -d postgres redis minio
```

**Verify services:**
```bash
docker-compose ps
```

All services should show status as "healthy".

### 4. Initialize Database

```bash
cd ../..
./scripts/setup/init_db.sh
```

This creates tables and enables TimescaleDB.

### 5. Set Up Python Services

For each service you want to work on:

```bash
cd services/api-gateway  # or any other service

# Create virtual environment
python3 -m venv venv

# Activate it
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# Install development tools
pip install pytest pytest-cov black ruff mypy
```

### 6. Set Up JavaScript/TypeScript Components (Optional)

**Dashboard:**
```bash
cd dashboard
npm install
```

**JS Worker:**
```bash
cd workers/js-worker
npm install
```

### 7. Set Up C++ Worker (Optional)

**Install dependencies (macOS):**
```bash
brew install cmake ninja protobuf grpc
```

**Install dependencies (Ubuntu):**
```bash
sudo apt-get update
sudo apt-get install -y cmake ninja-build libprotobuf-dev protobuf-compiler
```

**Download LibTorch:**
```bash
cd workers/cpp-worker
# Download from https://pytorch.org/get-started/locally/
# Choose: C++/LibTorch, CPU or CUDA version
```

**Build:**
```bash
mkdir build && cd build
cmake -G Ninja ..
ninja
```

## Environment Variables

Create `.env` files for local configuration:

**services/api-gateway/.env:**
```bash
DATABASE_URL=postgresql://meshml_user:meshml_dev_password@localhost:5432/meshml
REDIS_URL=redis://:meshml_redis_password@localhost:6379/0
SECRET_KEY=your-secret-key-for-jwt
DEBUG=true
```

**services/parameter-server/.env:**
```bash
DATABASE_URL=postgresql://meshml_user:meshml_dev_password@localhost:5432/meshml
REDIS_URL=redis://:meshml_redis_password@localhost:6379/0
GRPC_PORT=50051
```

## Running Services

### API Gateway
```bash
cd services/api-gateway
source venv/bin/activate
uvicorn app.main:app --reload --port 8000
```

Visit: http://localhost:8000/docs for API documentation

### Dashboard
```bash
cd dashboard
npm run dev
```

Visit: http://localhost:5173

### C++ Worker
```bash
cd workers/cpp-worker/build
./meshml-worker --server-addr localhost:50051
```

## Development Workflow

### Make Changes

1. Create a feature branch:
   ```bash
   git checkout -b feature/your-feature-name
   ```

2. Make your changes

3. Pre-commit hooks will run automatically:
   ```bash
   git commit -m "feat: your feature description"
   ```

4. If hooks fail, fix issues and commit again

### Run Tests

**Python:**
```bash
cd services/api-gateway
pytest tests/ -v --cov=app
```

**JavaScript:**
```bash
cd dashboard
npm test
```

**C++:**
```bash
cd workers/cpp-worker/build
ctest --verbose
```

### Code Quality Checks

**Manual formatting:**
```bash
# Python
black services/
isort services/

# JavaScript
cd dashboard && npm run format

# C++
clang-format -i workers/cpp-worker/src/*.cpp
```

**Manual linting:**
```bash
# Python
ruff check services/

# JavaScript
cd dashboard && npm run lint
```

### Using the Makefile

We provide a Makefile for common tasks:

```bash
make help          # Show all commands
make install       # Install dependencies
make lint          # Run all linters
make format        # Format all code
make test          # Run all tests
make docker-up     # Start services
make docker-down   # Stop services
make clean         # Clean build artifacts
```

## Accessing Services

| Service | URL | Credentials |
|---------|-----|-------------|
| API Gateway | http://localhost:8000 | - |
| Dashboard | http://localhost:5173 | - |
| PostgreSQL | localhost:5432 | meshml_user / meshml_dev_password |
| Redis | localhost:6379 | Password: meshml_redis_password |
| MinIO Console | http://localhost:9001 | minioadmin / minioadmin123 |
| Prometheus | http://localhost:9090 | - |
| Grafana | http://localhost:3000 | admin / admin123 |
| Jaeger UI | http://localhost:16686 | - |

## Troubleshooting

### Docker Issues

**Port conflicts:**
```bash
# Check what's using the port
lsof -i :5432

# Change port in docker-compose.yml
ports:
  - "5433:5432"  # Use different host port
```

**Services not starting:**
```bash
# Check logs
docker-compose logs postgres

# Restart services
docker-compose restart
```

### Python Import Errors

```bash
# Ensure you're in the virtual environment
which python  # Should show venv path

# Reinstall dependencies
pip install -r requirements.txt
```

### Database Connection Issues

```bash
# Test connection
docker exec -it meshml-postgres psql -U meshml_user -d meshml

# Reset database
./scripts/dev/reset_db.sh
```

### Permission Errors (Linux)

```bash
# Fix Docker volume permissions
sudo chown -R $USER:$USER .
```

## IDE Setup

### VS Code

Recommended extensions:
- Python
- Pylance
- ESLint
- Prettier
- C/C++
- Docker
- GitLens

**settings.json:**
```json
{
  "python.defaultInterpreterPath": "${workspaceFolder}/services/api-gateway/venv/bin/python",
  "python.formatting.provider": "black",
  "python.linting.enabled": true,
  "python.linting.ruffEnabled": true,
  "editor.formatOnSave": true
}
```

### PyCharm

1. Mark `services/*/app` as source roots
2. Set Python interpreter to virtual environment
3. Enable Black formatter
4. Enable Ruff linter

## Next Steps

- Read [Code Standards](./code-standards.md)
- Review [Contributing Guide](../../CONTRIBUTING.md)
- Check [Architecture Documentation](../architecture/)
- Browse open issues for "Good First Issue" label

## Getting Help

- **GitHub Discussions**: Ask questions
- **Discord**: Join our server
- **Documentation**: Check `/docs`
- **Issues**: Report bugs or request features
