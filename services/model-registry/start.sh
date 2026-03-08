#!/bin/bash
# Start Model Registry Service

echo "🚀 Starting MeshML Model Registry Service..."

# Activate virtual environment if it exists
if [ -d "../../mesh.venv" ]; then
    source ../../mesh.venv/bin/activate
    echo "✅ Activated mesh.venv"
fi

# Check if .env exists
if [ ! -f ".env" ]; then
    echo "⚠️  No .env file found, copying from .env.example..."
    cp .env.example .env
    echo "⚠️  Please update .env with your configuration"
fi

# Run the service
echo "🌐 Starting server on http://0.0.0.0:8004"
python -m app.main
