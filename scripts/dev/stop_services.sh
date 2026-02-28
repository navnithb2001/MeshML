#!/bin/bash
# Stop all MeshML development services

set -e

echo "⏹️  Stopping MeshML Services"
echo "==========================="

cd "$(dirname "$0")/../../infrastructure/docker"

docker compose down

echo ""
echo "✅ All services stopped!"
echo ""
echo "ℹ️  To remove volumes (⚠️ destroys data): docker compose down -v"
echo "🔄 To restart: ./scripts/dev/start_services.sh"
