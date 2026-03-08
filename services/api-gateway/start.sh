#!/bin/bash
# MeshML API Gateway Startup Script

set -e

echo "🚀 Starting MeshML API Gateway..."

# Colors for output
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m' # No Color

# Check Python version
echo -n "Checking Python version... "
PYTHON_VERSION=$(python3 --version 2>&1 | awk '{print $2}')
REQUIRED_VERSION="3.10"
if [ "$(printf '%s\n' "$REQUIRED_VERSION" "$PYTHON_VERSION" | sort -V | head -n1)" != "$REQUIRED_VERSION" ]; then 
    echo -e "${RED}✗${NC}"
    echo "Python 3.10+ required. Found: $PYTHON_VERSION"
    exit 1
fi
echo -e "${GREEN}✓${NC} ($PYTHON_VERSION)"

# Check if .env exists
if [ ! -f .env ]; then
    echo -e "${YELLOW}⚠${NC}  .env file not found. Creating from example..."
    cp .env.example .env
    echo -e "${YELLOW}⚠${NC}  Please edit .env with your configuration"
    exit 1
fi

# Check PostgreSQL connection
echo -n "Checking PostgreSQL connection... "
if command -v psql &> /dev/null; then
    # Extract DB credentials from .env
    DB_URL=$(grep DATABASE_URL .env | cut -d '=' -f2)
    if pg_isready -q 2>/dev/null; then
        echo -e "${GREEN}✓${NC}"
    else
        echo -e "${YELLOW}⚠${NC}  Cannot connect to PostgreSQL"
        echo "  Start PostgreSQL or update DATABASE_URL in .env"
    fi
else
    echo -e "${YELLOW}⚠${NC}  psql not installed, skipping check"
fi

# Check Redis connection
echo -n "Checking Redis connection... "
if command -v redis-cli &> /dev/null; then
    if redis-cli ping &> /dev/null; then
        echo -e "${GREEN}✓${NC}"
    else
        echo -e "${YELLOW}⚠${NC}  Cannot connect to Redis"
        echo "  Start Redis or update REDIS_URL in .env"
    fi
else
    echo -e "${YELLOW}⚠${NC}  redis-cli not installed, skipping check"
fi

# Install dependencies
echo -n "Installing dependencies... "
pip install -q -r requirements.txt
echo -e "${GREEN}✓${NC}"

# Run mode
MODE=${1:-dev}

if [ "$MODE" = "prod" ]; then
    echo ""
    echo "Starting in PRODUCTION mode..."
    WORKERS=${2:-4}
    uvicorn app.main:app \
        --host 0.0.0.0 \
        --port 8000 \
        --workers $WORKERS \
        --log-level info
elif [ "$MODE" = "test" ]; then
    echo ""
    echo "Running tests..."
    pytest tests/ -v
else
    echo ""
    echo "Starting in DEVELOPMENT mode..."
    echo "  API:  http://localhost:8000"
    echo "  Docs: http://localhost:8000/docs"
    echo ""
    uvicorn app.main:app \
        --reload \
        --host 0.0.0.0 \
        --port 8000 \
        --log-level debug
fi
