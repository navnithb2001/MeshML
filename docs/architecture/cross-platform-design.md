# Cross-Platform Architecture Design

**Last Updated:** March 1, 2026

This document addresses how MeshML handles heterogeneous devices, datasets, and dependencies across different operating systems.

---

## Table of Contents

1. [Cross-Platform Communication](#1-cross-platform-communication)
2. [Dataset Input & Management](#2-dataset-input--management)
3. [Dataset Distribution](#3-dataset-distribution)
4. [Library Compatibility](#4-library-compatibility)
5. [Worker Registration Protocol](#5-worker-registration-protocol)
6. [Example User Workflow](#6-example-user-workflow)

---

## 1. Cross-Platform Communication

### Protocol Stack

MeshML uses **platform-agnostic protocols** for all communication:

```
┌─────────────────────────────────────────────────────────────┐
│  Application Layer                                          │
│  • gRPC (HTTP/2 based RPC)                                 │
│  • Protocol Buffers (binary serialization)                 │
│  • REST API (JSON for dashboard)                           │
└─────────────────────────────────────────────────────────────┘
           ↓                    ↓                    ↓
┌──────────────┐    ┌──────────────┐    ┌──────────────┐
│ Python Worker│    │  C++ Worker  │    │  JS Worker   │
│ (any OS)     │    │ (Win/Mac/Lin)│    │  (Browser)   │
└──────────────┘    └──────────────┘    └──────────────┘
```

### Why This Works

- **gRPC**: Official libraries for Python, C++, JavaScript, Go, Java, etc.
- **Protocol Buffers**: Language-neutral, platform-neutral binary format
- **HTTP/2**: Works through firewalls, NAT, proxies
- **TLS**: Encrypted communication (optional but recommended)

### Architecture Pattern

**Workers DO NOT communicate directly** - all communication flows through central services:

```
Worker A (macOS)  ──┐
                    ├──► Parameter Server ◄──┐
Worker B (Windows)──┘          ↕              ├── Worker C (Android)
                         Task Orchestrator ◄──┘
                               ↕
                         PostgreSQL + Redis
```

**Benefits:**
- No peer-to-peer NAT traversal issues
- Centralized coordination and monitoring
- OS differences isolated within each worker

---

## 2. Dataset Input & Management

### Input Methods

#### Method 1: Dashboard Upload (Recommended)

**User Interface:**
```
┌─────────────────────────────────────────────────────────┐
│  MeshML Dashboard - Create Training Job                 │
├─────────────────────────────────────────────────────────┤
│  Job Name: [CIFAR-10 Experiment                      ] │
│                                                         │
│  Dataset Source:                                        │
│  ○ Upload Files    ● Upload Folder    ○ S3/MinIO URL  │
│                                                         │
│  [ Browse... ]  Selected: /Users/john/datasets/cifar   │
│                                                         │
│  Dataset Format:                                        │
│  ⌄ Image Classification (folder per class)             │
│                                                         │
│  Batch Size: [64      ]  Workers: [Auto-detect ▼]     │
│                                                         │
│  [ Upload & Start Training ]                           │
└─────────────────────────────────────────────────────────┘
```

**Supported Formats:**
- **Image Classification**: ImageFolder structure (class name = folder name)
- **Object Detection**: COCO JSON, YOLO format
- **Tabular Data**: CSV, Parquet files
- **Text**: JSON lines, TXT files
- **Custom**: User-provided data loader script

**Backend Processing:**
1. User uploads via dashboard
2. API Gateway receives files
3. Dataset Sharder validates format
4. Files stored in MinIO (S3-compatible)
5. Metadata stored in PostgreSQL

#### Method 2: Remote URL

**User provides URL:**
```json
{
  "job_name": "ImageNet Training",
  "dataset_source": {
    "type": "s3",
    "url": "s3://my-bucket/imagenet/",
    "credentials": {
      "access_key": "...",
      "secret_key": "..."
    }
  }
}
```

#### Method 3: Pre-Configured Datasets

**Built-in datasets (downloaded on-demand):**
```python
# In job configuration
{
  "dataset": "torchvision.datasets.CIFAR10",
  "download": true
}
```

---

## 3. Dataset Distribution

### Architecture

```
┌─────────────────────────────────────────────────────────────┐
│  1. DATASET UPLOAD                                          │
│  User uploads 10GB dataset via Dashboard                   │
└─────────────────────┬───────────────────────────────────────┘
                      ↓
┌─────────────────────────────────────────────────────────────┐
│  2. DATASET SHARDING                                        │
│  Dataset Sharder Service:                                   │
│  • Validates format                                         │
│  • Splits into N batches (e.g., 100 batches × 100MB)       │
│  • Stores batches in MinIO                                  │
│  • Creates batch metadata in PostgreSQL                     │
└─────────────────────┬───────────────────────────────────────┘
                      ↓
┌─────────────────────────────────────────────────────────────┐
│  3. TASK ASSIGNMENT                                         │
│  Task Orchestrator:                                         │
│  • Detects 5 workers available                             │
│  • Assigns 20 batches per worker                           │
│  • Sends batch URLs (not data)                             │
└─────────────────────┬───────────────────────────────────────┘
                      ↓
        ┌─────────────┼─────────────┬─────────────┐
        ↓             ↓             ↓             ↓
  Worker 1      Worker 2      Worker 3      Worker 4
  (macOS)       (Windows)     (Linux)       (Android)
  Batches       Batches       Batches       Batches
  1-20          21-40         41-60         61-80
        │             │             │             │
        └─────────────┴─────────────┴─────────────┘
                      │
                      ↓
          Fetch batches on-demand from MinIO:
          GET /datasets/job123/batch_001.tar.gz
```

### Distribution Protocol

**Step 1: Worker receives task assignment**

```json
// gRPC message from Task Orchestrator → Worker
{
  "job_id": "job_550e8400",
  "assigned_batches": [
    {
      "batch_id": "batch_001",
      "download_url": "http://minio:9000/datasets/job_550e8400/batch_001.tar.gz",
      "checksum": "sha256:abc123...",
      "size_bytes": 104857600
    },
    {
      "batch_id": "batch_002",
      "download_url": "http://minio:9000/datasets/job_550e8400/batch_002.tar.gz",
      "checksum": "sha256:def456...",
      "size_bytes": 104857600
    }
  ],
  "model_config": { ... },
  "training_params": { ... }
}
```

**Step 2: Worker fetches batch**

```python
# Worker-side code (Python example)
def fetch_batch(batch_info):
    """
    Download batch from MinIO to local temp directory.
    Works on any OS - just HTTP download.
    """
    import requests
    import tempfile
    import tarfile
    
    # Download to temp file
    temp_dir = tempfile.mkdtemp()
    batch_path = os.path.join(temp_dir, f"{batch_info['batch_id']}.tar.gz")
    
    # Stream download (memory efficient)
    with requests.get(batch_info['download_url'], stream=True) as r:
        r.raise_for_status()
        with open(batch_path, 'wb') as f:
            for chunk in r.iter_content(chunk_size=8192):
                f.write(chunk)
    
    # Verify checksum
    assert compute_checksum(batch_path) == batch_info['checksum']
    
    # Extract
    with tarfile.open(batch_path, 'r:gz') as tar:
        tar.extractall(temp_dir)
    
    return temp_dir  # Return path to extracted data
```

**Step 3: Worker trains on batch**

```python
# Load data and train
data_loader = create_data_loader(batch_path)
for epoch in range(num_epochs):
    for images, labels in data_loader:
        # Training happens here
        loss = train_step(images, labels)
        
    # Report progress
    send_progress_update(job_id, batch_id, epoch, loss)
```

**Step 4: Worker reports completion**

```json
// Worker → Task Orchestrator
{
  "job_id": "job_550e8400",
  "batch_id": "batch_001",
  "status": "completed",
  "metrics": {
    "loss": 0.342,
    "accuracy": 0.89,
    "samples_processed": 1024,
    "duration_seconds": 127.5
  },
  "gradients": "http://minio:9000/gradients/job_550e8400/worker1/batch_001.pt"
}
```

### Batch Caching Strategy

Workers can cache batches locally to avoid re-downloading:

```python
# Worker configuration
CACHE_CONFIG = {
    "enabled": True,
    "max_size_gb": 10,  # Max cache size
    "eviction_policy": "LRU"  # Least Recently Used
}
```

---

## 4. Library Compatibility

### Multi-Tier Worker Strategy

MeshML supports **three worker types** to handle different environments:

#### Tier 1: Python Worker (Broadest Compatibility)

**Target Platforms:** Windows 10+, macOS 11+, Linux (Ubuntu 20.04+)

**Requirements:**
```txt
Python >= 3.11
PyTorch >= 2.2.0
numpy >= 1.24.0
grpcio >= 1.60.0
```

**Installation:**
```bash
# Works on all platforms
pip install -r workers/python-worker/requirements.txt
```

**Hardware Auto-Detection:**
```python
import torch

def detect_device():
    """Automatically detect best available device"""
    if torch.cuda.is_available():
        return "cuda", torch.cuda.get_device_name(0)
    elif torch.backends.mps.is_available():
        return "mps", "Apple Silicon GPU"
    else:
        return "cpu", "CPU"

device, device_name = detect_device()
print(f"Using {device_name}")
```

**OS-Specific Optimizations:**
```python
# macOS: Use Metal Performance Shaders
if sys.platform == "darwin":
    os.environ["PYTORCH_ENABLE_MPS_FALLBACK"] = "1"

# Windows: CUDA optimizations
elif sys.platform == "win32":
    torch.backends.cudnn.benchmark = True

# Linux: Check for ROCm (AMD GPUs)
elif sys.platform == "linux":
    if "rocm" in torch.__config__.show():
        device = "cuda"  # ROCm uses CUDA API
```

---

#### Tier 2: C++ Worker (High Performance)

**Target Platforms:** Windows 10+, macOS 11+, Linux (Ubuntu 20.04+)

**Requirements:**
```txt
CMake >= 3.20
C++17 compiler (GCC 9+, Clang 12+, MSVC 2019+)
LibTorch >= 2.2.0
gRPC >= 1.60.0
```

**Cross-Platform Build:**
```cmake
# CMakeLists.txt handles platform differences
cmake_minimum_required(VERSION 3.20)
project(MeshMLWorker CXX)

set(CMAKE_CXX_STANDARD 17)

# Find LibTorch
find_package(Torch REQUIRED)

# Platform-specific GPU support
if(APPLE)
    # macOS Metal
    find_library(METAL_LIBRARY Metal)
    find_library(FOUNDATION_LIBRARY Foundation)
    target_link_libraries(worker ${METAL_LIBRARY} ${FOUNDATION_LIBRARY})
    
elseif(UNIX AND NOT APPLE)
    # Linux CUDA
    find_package(CUDA)
    if(CUDA_FOUND)
        target_compile_definitions(worker PRIVATE USE_CUDA)
        target_link_libraries(worker ${CUDA_LIBRARIES})
    endif()
    
elseif(WIN32)
    # Windows CUDA
    find_package(CUDA)
    if(CUDA_FOUND)
        target_compile_definitions(worker PRIVATE USE_CUDA)
        target_link_libraries(worker ${CUDA_LIBRARIES})
    endif()
endif()
```

**Installation Per OS:**
```bash
# macOS
brew install cmake libtorch grpc

# Ubuntu/Debian
sudo apt install cmake libgrpc-dev
wget https://download.pytorch.org/libtorch/cpu/libtorch-cxx11-abi-shared-with-deps-2.2.0%2Bcpu.zip

# Windows
choco install cmake
# Download LibTorch from pytorch.org
```

---

#### Tier 3: JavaScript Worker (Maximum Reach)

**Target Platforms:** Any device with modern browser (Chrome 90+, Safari 14+, Firefox 88+)

**Requirements:**
```json
{
  "dependencies": {
    "onnxruntime-web": "^1.16.0",
    "@grpc/grpc-js": "^1.9.0",
    "@grpc/proto-loader": "^0.7.10"
  }
}
```

**Why JavaScript Worker?**
- ✅ **Zero installation** - runs in browser
- ✅ **Mobile support** - Android, iOS browsers
- ✅ **WebGPU acceleration** - uses GPU even on phones
- ✅ **Cross-platform** - same code on all devices

**Usage:**
```javascript
// Browser-based training with ONNX Runtime Web
import * as ort from 'onnxruntime-web';

// Auto-detect execution provider
const session = await ort.InferenceSession.create(modelPath, {
    executionProviders: [
        'webgpu',  // Modern GPUs (Chrome 113+)
        'webgl',   // Fallback for older browsers
        'wasm'     // CPU fallback
    ]
});

// Works on ANY device with a browser
```

---

### Worker Capability Registration

Each worker reports its capabilities on startup:

```protobuf
// worker.proto
message WorkerCapabilities {
    string worker_id = 1;
    string worker_type = 2;  // "python", "cpp", "javascript"
    
    // Operating System
    string os = 3;           // "darwin", "linux", "windows", "android", "ios"
    string os_version = 4;   // "14.2.1"
    string arch = 5;         // "arm64", "x86_64"
    
    // Software Environment
    map<string, string> frameworks = 6;  // {"pytorch": "2.2.0", "onnx": "1.16.0"}
    string python_version = 7;           // "3.11.5" (if applicable)
    
    // Hardware
    int32 cpu_cores = 8;
    int64 ram_bytes = 9;
    repeated GPU gpus = 10;
    
    // Capabilities
    repeated string supported_ops = 11;  // ["training", "inference", "quantization"]
    bool supports_mixed_precision = 12;
    int64 max_batch_size = 13;
}

message GPU {
    string name = 1;          // "NVIDIA RTX 3080", "Apple M2"
    string type = 2;          // "cuda", "metal", "opencl", "webgpu"
    int64 memory_bytes = 3;
    int32 compute_capability = 4;  // CUDA compute capability
}
```

**Registration Flow:**

```python
# Worker startup code
def register_worker():
    capabilities = detect_capabilities()
    
    # Send to Task Orchestrator
    response = orchestrator_stub.RegisterWorker(capabilities)
    
    return response.worker_id

def detect_capabilities():
    import platform
    import psutil
    
    return WorkerCapabilities(
        worker_type="python",
        os=platform.system().lower(),
        os_version=platform.release(),
        arch=platform.machine(),
        frameworks={
            "pytorch": torch.__version__,
            "numpy": np.__version__
        },
        python_version=platform.python_version(),
        cpu_cores=psutil.cpu_count(logical=False),
        ram_bytes=psutil.virtual_memory().total,
        gpus=detect_gpus(),
        supported_ops=["training", "inference"],
        supports_mixed_precision=torch.cuda.is_bf16_supported()
    )
```

**Task Orchestrator uses this to assign compatible tasks:**

```python
# Orchestrator logic
def assign_batch(job, workers):
    """Assign batches based on worker capabilities"""
    
    for worker in workers:
        # Match requirements
        if job.requires_gpu and not worker.gpus:
            continue
            
        if job.framework == "pytorch" and "pytorch" not in worker.frameworks:
            continue
            
        if worker.ram_bytes < job.min_memory_bytes:
            continue
        
        # Compatible - assign batch
        assign_batch_to_worker(worker, next_batch)
```

---

## 5. Worker Registration Protocol

### Full Registration Flow

```
┌─────────────────┐
│  Worker Starts  │
│  (any OS/type)  │
└────────┬────────┘
         │
         ↓
┌──────────────────────────────────────────────────────────┐
│  1. Detect Capabilities                                  │
│  • OS, version, architecture                            │
│  • Installed frameworks                                 │
│  • Available hardware (CPU, GPU, RAM)                   │
│  • Supported operations                                 │
└────────┬─────────────────────────────────────────────────┘
         │
         ↓
┌──────────────────────────────────────────────────────────┐
│  2. Connect to Task Orchestrator                         │
│  gRPC call: RegisterWorker(capabilities)                │
└────────┬─────────────────────────────────────────────────┘
         │
         ↓
┌──────────────────────────────────────────────────────────┐
│  3. Task Orchestrator validates & stores                 │
│  • Check authentication token                           │
│  • Validate capabilities                                │
│  • Store in PostgreSQL                                  │
│  • Add to Redis worker pool                            │
│  • Return worker_id                                     │
└────────┬─────────────────────────────────────────────────┘
         │
         ↓
┌──────────────────────────────────────────────────────────┐
│  4. Worker enters heartbeat loop                         │
│  Every 30s: SendHeartbeat(worker_id, current_status)    │
└────────┬─────────────────────────────────────────────────┘
         │
         ↓
┌──────────────────────────────────────────────────────────┐
│  5. Wait for task assignment                             │
│  Orchestrator: AssignTask(worker_id, batch_info)        │
└──────────────────────────────────────────────────────────┘
```

---

## 6. Example User Workflow

### Scenario: University ML Class

**Setup:**
- **Instructor** hosts MeshML services (Docker on cloud/laptop)
- **20 students** with mixed devices:
  - 10 students: macOS laptops
  - 5 students: Windows laptops
  - 3 students: Linux laptops
  - 2 students: Only have Android phones

### Step-by-Step Workflow

#### Step 1: Instructor uploads dataset

```bash
# Instructor opens dashboard at http://localhost:3000
# Uploads CIFAR-10 dataset (160MB)
# System automatically:
# - Validates format
# - Splits into 40 batches (4MB each)
# - Stores in MinIO
```

#### Step 2: Students install workers

**macOS/Windows/Linux students:**
```bash
# Clone worker repo
git clone https://github.com/meshml/python-worker.git
cd python-worker

# Install dependencies
pip install -r requirements.txt

# Start worker (auto-connects to instructor's server)
python worker.py --server http://instructor-ip:8000 --token ABC123
```

**Android students:**
```
1. Open browser on phone
2. Navigate to http://instructor-ip:3000/worker
3. Click "Start Training" button
4. JavaScript worker runs in browser (no installation!)
```

#### Step 3: Workers auto-register

```
System detects:
- 18 workers with PyTorch (laptops)
- 2 workers with ONNX Runtime Web (phones)

Task Orchestrator assigns:
- Laptops: 2 batches each (heavier workload)
- Phones: 1 batch each (lighter workload)
```

#### Step 4: Training starts

```
Each worker:
1. Downloads assigned batches from MinIO
2. Trains model on local data
3. Sends gradients to Parameter Server
4. Repeats for multiple epochs

Parameter Server:
- Aggregates gradients from all workers
- Updates global model
- Sends updated weights back to workers
```

#### Step 5: Monitor progress

```
Dashboard shows:
- Real-time training loss/accuracy
- Worker status (18 active, 2 idle)
- Network utilization
- Estimated time to completion
```

#### Step 6: Training completes

```
Final model saved to MinIO
Students can download model or deploy to inference
```

---

## Summary

### Key Design Principles

1. **OS-Agnostic Protocols**
   - gRPC + Protocol Buffers for all communication
   - No direct worker-to-worker communication
   - All coordination through central services

2. **Flexible Dataset Input**
   - Dashboard upload (drag & drop)
   - Remote URLs (S3, HTTP)
   - Built-in datasets (CIFAR, ImageNet, etc.)

3. **Smart Distribution**
   - Dataset split into batches server-side
   - Workers fetch batches on-demand
   - Caching to avoid re-downloads

4. **Multi-Tier Workers**
   - Python: Broadest compatibility
   - C++: High performance
   - JavaScript: Maximum reach (even mobile!)

5. **Capability-Based Assignment**
   - Workers report their capabilities
   - Orchestrator assigns compatible tasks
   - Automatic handling of OS/library differences

### Benefits

✅ **Zero configuration** - Workers auto-detect hardware  
✅ **Heterogeneous** - Mix Windows, Mac, Linux, mobile  
✅ **Fault tolerant** - Workers can join/leave anytime  
✅ **Efficient** - Data fetched on-demand, cached locally  
✅ **Scalable** - Add more workers = faster training

---

**Next Steps:** Implement Phase 1 (Database schema) with these design decisions in mind.
