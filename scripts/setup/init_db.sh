#!/bin/bash
# Initialize MeshML Database Schema

set -e

echo "🗄️  Initializing MeshML Database"
echo "================================"

# Color codes
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m'

# Database connection details
DB_HOST=${DB_HOST:-localhost}
DB_PORT=${DB_PORT:-5432}
DB_NAME=${DB_NAME:-meshml}
DB_USER=${DB_USER:-meshml_user}
DB_PASSWORD=${DB_PASSWORD:-meshml_dev_password}

# Check if PostgreSQL is running
if ! docker ps | grep -q meshml-postgres; then
    echo -e "${RED}✗${NC} PostgreSQL container is not running"
    echo "   Start it with: cd infrastructure/docker && docker compose up -d postgres"
    exit 1
fi

echo -e "${GREEN}✓${NC} PostgreSQL is running"

# Wait for PostgreSQL to be ready
echo "⏳ Waiting for PostgreSQL to be ready..."
until docker exec meshml-postgres pg_isready -U $DB_USER -d $DB_NAME >/dev/null 2>&1; do
    sleep 1
done

echo -e "${GREEN}✓${NC} PostgreSQL is ready"

# Create database if it doesn't exist
echo "📊 Creating database if needed..."
docker exec -i meshml-postgres psql -U $DB_USER -d postgres << EOF
SELECT 'CREATE DATABASE $DB_NAME'
WHERE NOT EXISTS (SELECT FROM pg_database WHERE datname = '$DB_NAME')\gexec
EOF

# Enable TimescaleDB extension
echo "⏰ Enabling TimescaleDB extension..."
docker exec -i meshml-postgres psql -U $DB_USER -d $DB_NAME << EOF
CREATE EXTENSION IF NOT EXISTS timescaledb CASCADE;
EOF

# Run schema initialization scripts
echo "📝 Running schema scripts..."
SCHEMA_DIR="$(dirname "$0")/../../database/schema"

if [ -d "$SCHEMA_DIR" ]; then
    for sql_file in "$SCHEMA_DIR"/*.sql; do
        if [ -f "$sql_file" ]; then
            filename=$(basename "$sql_file")
            echo "  → Executing $filename..."
            docker exec -i meshml-postgres psql -U $DB_USER -d $DB_NAME < "$sql_file"
        fi
    done
else
    echo -e "${YELLOW}⚠${NC} No schema files found in $SCHEMA_DIR"
fi

# Run Alembic migrations if available
MIGRATIONS_DIR="$(dirname "$0")/../../database/migrations"
if [ -f "$MIGRATIONS_DIR/alembic.ini" ]; then
    echo "🔄 Running Alembic migrations..."
    cd "$MIGRATIONS_DIR"
    if [ -d "venv" ]; then
        source venv/bin/activate
    fi
    # alembic upgrade head
    echo -e "${YELLOW}⚠${NC} Alembic migrations will be run when implemented"
fi

echo ""
echo -e "${GREEN}✅ Database initialization complete!${NC}"
echo ""
echo "📊 Database connection info:"
echo "   Host:     $DB_HOST"
echo "   Port:     $DB_PORT"
echo "   Database: $DB_NAME"
echo "   User:     $DB_USER"
echo ""
echo "🔗 Connection string:"
echo "   postgresql://$DB_USER:$DB_PASSWORD@$DB_HOST:$DB_PORT/$DB_NAME"
