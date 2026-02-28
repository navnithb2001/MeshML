#!/bin/bash
# Reset MeshML database (⚠️ destroys all data)

set -e

RED='\033[0;31m'
YELLOW='\033[1;33m'
GREEN='\033[0;32m'
NC='\033[0m'

echo -e "${RED}⚠️  WARNING: Database Reset${NC}"
echo "=============================="
echo "This will destroy all data in the database!"
echo ""
read -p "Are you sure? (type 'yes' to continue): " confirmation

if [ "$confirmation" != "yes" ]; then
    echo "Aborted."
    exit 0
fi

cd "$(dirname "$0")/../../infrastructure/docker"

echo ""
echo "🗑️  Stopping and removing PostgreSQL container..."
docker compose down postgres
docker volume rm meshml_postgres_data 2>/dev/null || true

echo ""
echo "🔄 Restarting PostgreSQL..."
docker compose up -d postgres

echo ""
echo "⏳ Waiting for PostgreSQL to be ready..."
sleep 5

echo ""
echo "📊 Re-initializing database..."
cd ../..
./scripts/setup/init_db.sh

echo ""
echo -e "${GREEN}✅ Database reset complete!${NC}"
