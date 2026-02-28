#!/bin/bash
# MeshML Development Environment Setup Script

set -e  # Exit on error

echo "🚀 MeshML Development Environment Setup"
echo "========================================"

# Color codes
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m' # No Color

# Check if running on macOS
if [[ "$OSTYPE" == "darwin"* ]]; then
    echo -e "${GREEN}✓${NC} Detected macOS"
    PACKAGE_MANAGER="brew"
else
    echo -e "${GREEN}✓${NC} Detected Linux"
    PACKAGE_MANAGER="apt-get"
fi

# Function to check if command exists
command_exists() {
    command -v "$1" >/dev/null 2>&1
}

# Check prerequisites
echo ""
echo "📋 Checking prerequisites..."

# Docker
if command_exists docker; then
    echo -e "${GREEN}✓${NC} Docker is installed ($(docker --version))"
else
    echo -e "${RED}✗${NC} Docker is not installed"
    echo "   Install from: https://docs.docker.com/get-docker/"
    exit 1
fi

# Docker Compose
if command_exists docker-compose || docker compose version >/dev/null 2>&1; then
    echo -e "${GREEN}✓${NC} Docker Compose is installed"
else
    echo -e "${RED}✗${NC} Docker Compose is not installed"
    exit 1
fi

# Python
if command_exists python3; then
    PYTHON_VERSION=$(python3 --version | awk '{print $2}')
    echo -e "${GREEN}✓${NC} Python is installed (${PYTHON_VERSION})"
else
    echo -e "${RED}✗${NC} Python 3 is not installed"
    exit 1
fi

# Node.js
if command_exists node; then
    NODE_VERSION=$(node --version)
    echo -e "${GREEN}✓${NC} Node.js is installed (${NODE_VERSION})"
else
    echo -e "${YELLOW}⚠${NC} Node.js is not installed (optional for development)"
fi

# CMake
if command_exists cmake; then
    CMAKE_VERSION=$(cmake --version | head -n1)
    echo -e "${GREEN}✓${NC} CMake is installed (${CMAKE_VERSION})"
else
    echo -e "${YELLOW}⚠${NC} CMake is not installed (needed for C++ worker)"
fi

echo ""
echo "🐳 Starting Docker services..."
cd "$(dirname "$0")/../../infrastructure/docker"

# Start core services
echo "Starting PostgreSQL, Redis, and MinIO..."
docker compose up -d postgres redis minio

# Wait for services to be healthy
echo "⏳ Waiting for services to be ready..."
sleep 5

# Check service health
echo ""
echo "🏥 Checking service health..."

if docker compose ps | grep -q "postgres.*healthy"; then
    echo -e "${GREEN}✓${NC} PostgreSQL is healthy"
else
    echo -e "${YELLOW}⚠${NC} PostgreSQL is still starting..."
fi

if docker compose ps | grep -q "redis.*healthy"; then
    echo -e "${GREEN}✓${NC} Redis is healthy"
else
    echo -e "${YELLOW}⚠${NC} Redis is still starting..."
fi

if docker compose ps | grep -q "minio.*healthy"; then
    echo -e "${GREEN}✓${NC} MinIO is healthy"
else
    echo -e "${YELLOW}⚠${NC} MinIO is still starting..."
fi

echo ""
echo "📦 Installing Python dependencies..."
cd "$(dirname "$0")/../.."

# Create virtual environment for each service
for service in services/*/; do
    if [ -f "${service}requirements.txt" ]; then
        service_name=$(basename "$service")
        echo "  → Installing dependencies for ${service_name}..."
        
        cd "$service"
        if [ ! -d "venv" ]; then
            python3 -m venv venv
        fi
        source venv/bin/activate
        pip install --upgrade pip -q
        pip install -r requirements.txt -q
        deactivate
        cd ../..
    fi
done

echo ""
echo "✅ Setup complete!"
echo ""
echo "📚 Next steps:"
echo "   1. Start monitoring stack: cd infrastructure/docker && docker compose up -d prometheus grafana"
echo "   2. Run database migrations: ./scripts/setup/init_db.sh"
echo "   3. Start a service: cd services/api-gateway && source venv/bin/activate && python -m app.main"
echo ""
echo "🌐 Service URLs:"
echo "   PostgreSQL:  localhost:5432"
echo "   Redis:       localhost:6379"
echo "   MinIO:       http://localhost:9001 (admin/admin123)"
echo "   Prometheus:  http://localhost:9090"
echo "   Grafana:     http://localhost:3000 (admin/admin123)"
echo ""
echo "📖 Documentation: README.md"
