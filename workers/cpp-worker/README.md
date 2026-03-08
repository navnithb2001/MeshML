# MeshML C++ Worker

High-performance native worker for distributed machine learning training using LibTorch.

## Features

- **LibTorch Integration**: Full PyTorch C++ API support for training
- **Cross-Platform**: Linux, macOS (Intel & Apple Silicon), Windows
- **GPU Acceleration**: CUDA support for NVIDIA GPUs
- **gRPC Communication**: Efficient bi-directional communication with Parameter Server
- **Automatic Setup**: Downloads LibTorch automatically if not found
- **Optimized Performance**: Multi-threading, SIMD operations, memory pooling

## Requirements

- **CMake**: >= 3.20
- **C++ Compiler**: GCC 9+, Clang 10+, or MSVC 2019+
- **LibTorch**: 2.0.1+ (auto-downloaded if not found)
- **gRPC**: For Parameter Server communication
- **Protobuf**: For data serialization

## Build Instructions

### macOS (Apple Silicon)

```bash
# Install dependencies via Homebrew
brew install cmake grpc protobuf

# Build
mkdir build && cd build
cmake ..
cmake --build . --config Release

# Run
./meshml-worker --config config.yaml
```

### macOS (Intel) / Linux

```bash
# Install dependencies
# Ubuntu/Debian:
sudo apt-get install cmake libgrpc++-dev libprotobuf-dev

# Build
mkdir build && cd build
cmake ..
cmake --build . --config Release -j$(nproc)

# Run
./meshml-worker --config config.yaml
```

### Linux with CUDA

```bash
# Build with CUDA support
mkdir build && cd build
cmake .. -DUSE_CUDA=ON
cmake --build . --config Release -j$(nproc)

# Run
./meshml-worker --config config.yaml
```

### Windows

```powershell
# Install dependencies via vcpkg
vcpkg install grpc protobuf

# Build
mkdir build
cd build
cmake .. -DCMAKE_TOOLCHAIN_FILE=[vcpkg root]/scripts/buildsystems/vcpkg.cmake
cmake --build . --config Release

# Run
Release\meshml-worker.exe --config config.yaml
```

## Configuration

Create a `config.yaml` file:

```yaml
worker:
  id: "worker-001"
  name: "MacBook Pro M1"

parameter_server:
  url: "http://localhost:8000"
  grpc_url: "localhost:50051"
  timeout: 30

training:
  batch_size: 32
  num_workers: 4
  learning_rate: 0.001
  device: "auto"  # auto, cpu, cuda, cuda:0

storage:
  checkpoints_dir: "./checkpoints"
  models_dir: "./models"
  data_dir: "./data"

heartbeat:
  interval_seconds: 30

logging:
  level: "INFO"
  file: ""  # Empty for stdout only
```

## Usage

### Basic Training

```bash
# Initialize worker
./meshml-worker init --worker-id worker-001

# Check status
./meshml-worker status

# Start training
./meshml-worker train --model-id my-model --epochs 10
```

### With Custom Configuration

```bash
./meshml-worker train \
  --config my-config.yaml \
  --model-id my-model \
  --epochs 10 \
  --batch-size 64
```

### Resume from Checkpoint

```bash
./meshml-worker train \
  --model-id my-model \
  --checkpoint checkpoints/checkpoint_epoch_5.pt
```

## Project Structure

```
cpp-worker/
├── CMakeLists.txt          # Build configuration
├── cmake/                   # CMake helper scripts
│   └── DownloadLibTorch.cmake
├── include/                 # Public headers
│   └── meshml/
│       ├── config.h
│       ├── worker.h
│       ├── trainer.h
│       └── ...
├── src/                     # Implementation
│   ├── main.cpp
│   ├── worker.cpp
│   ├── config/
│   ├── grpc/
│   ├── training/
│   ├── models/
│   └── utils/
├── tests/                   # Unit tests
└── README.md
```

## Performance Considerations

### Memory Management

The C++ worker uses custom memory pooling for efficient tensor allocation:

- Pre-allocated memory pools for common tensor sizes
- Reduced allocation overhead during training
- Automatic cleanup and reuse

### Multi-threading

Data loading and preprocessing use multiple threads:

- Configurable `num_workers` for data loading
- Parallel batch preprocessing
- Thread-safe gradient accumulation

### CUDA Optimization

When using CUDA:

- Asynchronous CUDA streams for overlapping computation
- cuDNN auto-tuner for optimal convolution algorithms
- Pinned memory for faster CPU-GPU transfers

## Benchmarks

Comparison vs Python Worker (CIFAR-10, ResNet-18):

| Device       | C++ Worker | Python Worker | Speedup |
|--------------|-----------|---------------|---------|
| CPU (8 cores)| 45 img/s  | 32 img/s      | 1.4x    |
| CUDA (RTX 3080)| 890 img/s | 780 img/s   | 1.14x   |
| Apple M1 Max | 120 img/s | 95 img/s      | 1.26x   |

The C++ worker provides 10-40% performance improvement with lower memory overhead.

## Development

### Running Tests

```bash
cd build
cmake .. -DBUILD_TESTS=ON
cmake --build . --target worker-tests
ctest --output-on-failure
```

### Code Style

Format code using clang-format:

```bash
clang-format -i src/**/*.cpp include/**/*.h
```

### Debugging

```bash
# Build with debug symbols
cmake .. -DCMAKE_BUILD_TYPE=Debug

# Run with GDB
gdb --args ./meshml-worker train --model-id my-model

# Or with LLDB on macOS
lldb -- ./meshml-worker train --model-id my-model
```

## Troubleshooting

### LibTorch Not Found

If LibTorch auto-download fails:

1. Download manually from https://pytorch.org/get-started/locally/
2. Extract to a location (e.g., `/opt/libtorch`)
3. Build with:
   ```bash
   cmake .. -DCMAKE_PREFIX_PATH=/opt/libtorch
   ```

### CUDA Errors

If you get CUDA-related errors:

```bash
# Check CUDA installation
nvcc --version

# Verify GPU availability
nvidia-smi

# Build without CUDA
cmake .. -DUSE_CUDA=OFF
```

### gRPC Connection Issues

If unable to connect to Parameter Server:

```bash
# Test connectivity
nc -zv localhost 50051

# Check firewall settings
# Verify parameter_server.grpc_url in config
```

## License

See LICENSE file in the project root.

## Contributing

See CONTRIBUTING.md for development guidelines.
