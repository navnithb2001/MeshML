# Python Worker Dockerfile

FROM python:3.11-slim

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    gcc \
    g++ \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Copy project files
COPY pyproject.toml .
COPY README.md .

# Install Python dependencies
RUN pip install --no-cache-dir torch torchvision --index-url https://download.pytorch.org/whl/cpu && \
    pip install --no-cache-dir grpcio grpcio-tools protobuf pydantic pyyaml

# Copy application code
COPY . .

# Install meshml_worker package
RUN pip install -e .

# Create non-root user
RUN useradd -m -u 1000 meshml && \
    chown -R meshml:meshml /app

USER meshml

# Run worker
CMD ["python", "-m", "meshml_worker.worker"]
