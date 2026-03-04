# gRPC Protocol Buffer Definitions

This directory contains Protocol Buffer (`.proto`) files that define the gRPC services and message types for the MeshML distributed training system.

## 📁 Structure

```
proto/
├── common.proto                  # Shared types, enums, and messages
├── task_orchestrator.proto       # Worker lifecycle and task management
├── parameter_server.proto        # Gradient aggregation and weight distribution
├── dataset_sharder.proto         # Dataset partitioning and batch management
├── metrics.proto                 # Real-time metrics collection
└── generated/                    # Generated code (Python, C++, JavaScript)
    ├── python/
    ├── cpp/
    └── javascript/
```

## 🎯 Service Definitions

### 1. Task Orchestrator (`task_orchestrator.proto`)
**Purpose**: Manages worker lifecycle, task assignment, and progress tracking

**Key RPCs**:
- `RegisterWorker`: Worker registers with capabilities (CPU, RAM, GPU, frameworks)
- `SendHeartbeat`: Worker sends periodic health updates
- `RequestTask`: Worker requests batches to process
- `ReportBatchComplete`: Worker reports successful batch completion
- `ReportBatchFailed`: Worker reports batch failure

**Used by**: Python Worker, C++ Worker, JavaScript Worker, Task Orchestrator Service

---

### 2. Parameter Server (`parameter_server.proto`)
**Purpose**: Handles gradient aggregation and model weight synchronization

**Key RPCs**:
- `GetWeights`: Worker fetches latest model weights
- `UpdateGradients`: Worker sends computed gradients
- `GetOptimizerState`: Worker fetches optimizer state (Adam momentum, etc.)
- `GetModelVersion`: Check current model version

**Features**:
- Staleness-aware gradient aggregation
- Compression support (gzip, zstd)
- Version tracking for distributed synchronization
- Per-layer gradient norm tracking

**Used by**: Python Worker, C++ Worker, Parameter Server Service

---

### 3. Dataset Sharder (`dataset_sharder.proto`)
**Purpose**: Dataset partitioning and shard management

**Key RPCs**:
- `CreateShards`: Partition dataset into worker-sized chunks
- `GetShardInfo`: Get details about a specific shard
- `ListShards`: List all shards for a job
- `ValidateDataset`: Validate dataset before sharding

**Features**:
- Configurable sharding strategies
- Checksum verification
- Dataset statistics
- GCS path management

**Used by**: API Gateway, Dataset Sharder Service, Task Orchestrator

---

### 4. Metrics Service (`metrics.proto`)
**Purpose**: Real-time metrics collection and streaming

**Key RPCs**:
- `ReportMetrics`: Services/workers report metrics
- `StreamMetrics`: Subscribe to real-time metrics stream
- `GetJobMetrics`: Get aggregated job metrics
- `GetWorkerMetrics`: Get worker-specific metrics
- `GetSystemMetrics`: Get system-wide metrics

**Features**:
- Training metrics (loss, accuracy, learning rate)
- System metrics (CPU, RAM, GPU, network)
- Time-series data
- Real-time streaming via server-side streaming

**Used by**: All workers, Parameter Server, Task Orchestrator, Dashboard

---

### 5. Common Types (`common.proto`)
**Purpose**: Shared types, enums, and utility messages

**Includes**:
- Status enums (`JobStatus`, `WorkerStatus`, `ModelStatus`, `BatchStatus`)
- Type enums (`WorkerType`, `DatasetType`, `ModelArchitecture`)
- Common messages (`Error`, `Pagination`, `HealthStatus`, `Config`)

**Used by**: All services

---

## 🛠️ Generating Code

### Prerequisites
```bash
# Install Protocol Buffer compiler
brew install protobuf  # macOS
# OR
sudo apt-get install protobuf-compiler  # Linux

# Install gRPC tools
pip install grpcio-tools  # Python
npm install -g grpc-tools  # JavaScript
```

### Generate Python Code
```bash
# From project root
python -m grpc_tools.protoc \
  --proto_path=proto \
  --python_out=proto/generated/python \
  --grpc_python_out=proto/generated/python \
  proto/*.proto
```

**Generated files**:
- `*_pb2.py` - Message classes
- `*_pb2_grpc.py` - Service stubs and servers

### Generate C++ Code
```bash
# From project root
protoc \
  --proto_path=proto \
  --cpp_out=proto/generated/cpp \
  --grpc_out=proto/generated/cpp \
  --plugin=protoc-gen-grpc=`which grpc_cpp_plugin` \
  proto/*.proto
```

**Generated files**:
- `*.pb.h`, `*.pb.cc` - Message classes
- `*.grpc.pb.h`, `*.grpc.pb.cc` - Service stubs

### Generate JavaScript Code
```bash
# From project root
grpc_tools_node_protoc \
  --proto_path=proto \
  --js_out=import_style=commonjs:proto/generated/javascript \
  --grpc_out=grpc_js:proto/generated/javascript \
  proto/*.proto
```

**Generated files**:
- `*_pb.js` - Message classes
- `*_grpc_pb.js` - Service stubs

---

## 📝 Usage Examples

### Python Worker - Sending Heartbeat
```python
import grpc
from proto.generated.python import task_orchestrator_pb2, task_orchestrator_pb2_grpc

# Create gRPC channel
channel = grpc.insecure_channel('localhost:50051')
stub = task_orchestrator_pb2_grpc.TaskOrchestratorStub(channel)

# Send heartbeat
heartbeat = task_orchestrator_pb2.Heartbeat(
    worker_id='worker-123',
    status='online',
    active_tasks=2,
    cpu_usage_percent=45.2,
    ram_usage_percent=60.5
)
response = stub.SendHeartbeat(heartbeat)
print(f"Heartbeat acknowledged: {response.success}")
```

### Python Worker - Fetching Weights
```python
from proto.generated.python import parameter_server_pb2, parameter_server_pb2_grpc

channel = grpc.insecure_channel('localhost:50052')
stub = parameter_server_pb2_grpc.ParameterServerStub(channel)

# Fetch weights
request = parameter_server_pb2.WeightsRequest(
    job_id='job-456',
    worker_id='worker-123',
    current_version=5,
    epoch=2
)
response = stub.GetWeights(request)
if response.is_updated:
    # Deserialize and load weights
    model_state = pickle.loads(response.model_state_dict)
```

### Python Worker - Submitting Gradients
```python
import pickle

# Compute gradients...
gradients = compute_gradients(batch_data)

# Serialize gradients
gradient_bytes = pickle.dumps(gradients)

# Send to parameter server
update = parameter_server_pb2.GradientsUpdate(
    job_id='job-456',
    worker_id='worker-123',
    batch_id=789,
    version=5,
    epoch=2,
    gradients=gradient_bytes,
    batch_size=32,
    learning_rate=0.001,
    metadata=parameter_server_pb2.GradientMetadata(
        loss=0.234,
        gradient_norm=1.23
    )
)
response = stub.UpdateGradients(update)
print(f"New version: {response.new_version}")
```

### Dashboard - Streaming Metrics
```python
from proto.generated.python import metrics_pb2, metrics_pb2_grpc

channel = grpc.insecure_channel('localhost:50053')
stub = metrics_pb2_grpc.MetricsServiceStub(channel)

# Subscribe to metrics stream
request = metrics_pb2.MetricsStreamRequest(
    job_id='job-456',
    interval_seconds=5
)

for update in stub.StreamMetrics(request):
    print(f"Epoch: {update.training.epoch}, Loss: {update.training.loss:.4f}")
    print(f"Progress: {update.progress.progress_percent:.1f}%")
    print(f"Active workers: {len(update.workers)}")
```

---

## 🔄 Message Serialization

### Binary Serialization
Protocol Buffers use compact binary serialization for efficiency:
- **Model weights**: PyTorch state_dict → pickle → bytes
- **Gradients**: Tensor dict → pickle → bytes
- **Compression**: Optional gzip/zstd for large payloads

### Compression Example
```python
import gzip
import pickle

# Serialize and compress gradients
gradients_bytes = pickle.dumps(gradients)
compressed = gzip.compress(gradients_bytes)

# Send with compression metadata
update = parameter_server_pb2.GradientsUpdate(
    gradients=compressed,
    compression_type='gzip',
    uncompressed_size=len(gradients_bytes),
    # ... other fields
)
```

---

## 📊 Performance Considerations

### Streaming vs Unary
- **Unary RPC**: Single request → single response (GetWeights, UpdateGradients)
- **Server Streaming**: Single request → stream of responses (StreamMetrics)
- **Bidirectional Streaming**: Not currently used (future: continuous heartbeat stream)

### Payload Sizes
- **Weights**: ~100MB for ResNet-50 (uncompressed)
- **Gradients**: ~100MB (same size as weights)
- **Heartbeat**: <1KB
- **Metrics**: <10KB per report

**Optimization**:
- Use compression for weights/gradients (50-70% reduction)
- Send metrics in batches (every 5 seconds)
- Use TCP keepalive for long-lived connections

---

## 🧪 Testing

### Testing gRPC Services
```python
import pytest
from unittest.mock import Mock

def test_heartbeat():
    # Mock gRPC stub
    stub = Mock()
    stub.SendHeartbeat.return_value = task_orchestrator_pb2.HeartbeatAck(
        success=True,
        message='Heartbeat received'
    )
    
    # Test heartbeat
    heartbeat = task_orchestrator_pb2.Heartbeat(
        worker_id='test-worker',
        status='online'
    )
    response = stub.SendHeartbeat(heartbeat)
    assert response.success
```

---

## 📚 References

- [Protocol Buffers Documentation](https://protobuf.dev/)
- [gRPC Python Documentation](https://grpc.io/docs/languages/python/)
- [gRPC C++ Documentation](https://grpc.io/docs/languages/cpp/)
- [gRPC Node.js Documentation](https://grpc.io/docs/languages/node/)

---

## 🔜 Next Steps

- **TASK-2.2**: REST API contracts (OpenAPI/Swagger)
- **TASK-2.3**: GraphQL schema for metrics
- **Phase 3**: API Gateway implementation
