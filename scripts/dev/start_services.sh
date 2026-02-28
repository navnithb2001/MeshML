#!/bin/bash
# Start all MeshML development services

set -e

echo "🚀 Starting MeshML Services"
echo "=========================="

cd "$(dirname "$0")/../../infrastructure/docker"

# Start all services
docker compose up -d

echo ""
echo "⏳ Waiting for services to be healthy..."
sleep 10

# Display service status
echo ""
echo "📊 Service Status:"
docker compose ps

echo ""
echo "✅ All services started!"
echo ""
echo "🌐 Access URLs:"
echo "   PostgreSQL:       localhost:5432"
echo "   Redis:            localhost:6379"
echo "   MinIO Console:    http://localhost:9001"
echo "   Prometheus:       http://localhost:9090"
echo "   Grafana:          http://localhost:3000"
echo "   Jaeger UI:        http://localhost:16686"
echo ""
echo "📝 Logs: docker compose logs -f"
echo "⏹️  Stop: ./scripts/dev/stop_services.sh"
