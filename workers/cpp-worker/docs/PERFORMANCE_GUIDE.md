# Performance Optimization Guide

## Overview

The C++ Worker includes multiple performance optimization techniques to maximize training throughput and minimize resource usage.

## Features

1. **Performance Profiling** - Track and analyze training bottlenecks
2. **SIMD Operations** - Hardware-accelerated vector operations  
3. **Memory Pooling** - Reduce allocation overhead and fragmentation
4. **Multi-threading** - Parallel data loading and processing
5. **Mixed Precision** - CUDA AMP for 1.5-2x GPU speedup

## Performance Profiling

### Basic Usage

```cpp
#include "meshml/utils/performance.h"

auto profiler = create_performance_profiler();

// Profile specific sections
profiler->start_section("data_loading");
// ... load data ...
profiler->end_section("data_loading");

// Get metrics
auto metrics = profiler->get_metrics();
std::cout << "Throughput: " << metrics.samples_per_second << " samples/sec" << std::endl;

// Print summary
profiler->print_summary();
```

### RAII-Style Profiling

```cpp
{
    ProfileScope scope(*profiler, "forward_pass");
    // Code automatically profiled until end of scope
    auto output = model->forward(input);
}
```

### Performance Metrics

```cpp
PerformanceMetrics metrics = profiler->get_metrics();

// Throughput
std::cout << "Samples/sec: " << metrics.samples_per_second << std::endl;
std::cout << "Batches/sec: " << metrics.batches_per_second << std::endl;

// Timing breakdown
std::cout << "Data Loading: " << metrics.data_loading_ms << " ms" << std::endl;
std::cout << "Forward Pass: " << metrics.forward_pass_ms << " ms" << std::endl;
std::cout << "Backward Pass: " << metrics.backward_pass_ms << " ms" << std::endl;

// Memory usage
std::cout << "GPU Memory: " << metrics.gpu_memory_used_mb << " MB" << std::endl;
```

## Memory Profiling

### Track Memory Usage

```cpp
auto memory_profiler = create_memory_profiler("cuda");

// During training
size_t current = memory_profiler->get_memory_usage();
size_t peak = memory_profiler->get_peak_memory();

memory_profiler->print_summary();
```

### Memory Statistics

```cpp
auto stats = memory_profiler->get_memory_stats();

std::cout << "Allocated: " << stats["allocated_mb"] << " MB" << std::endl;
std::cout << "Reserved: " << stats["reserved_mb"] << " MB" << std::endl;
std::cout << "Peak: " << stats["peak_allocated_mb"] << " MB" << std::endl;
```

## SIMD Operations

### Automatic Hardware Detection

The SIMD library automatically detects and uses available hardware instructions:

- **x86_64**: AVX, AVX2, FMA
- **ARM**: NEON
- **Fallback**: Scalar implementation

```cpp
#include "meshml/utils/simd_ops.h"

// Check capabilities
std::cout << simd::get_simd_capabilities() << std::endl;
// Output: "SIMD Capabilities: AVX2" or "SIMD Capabilities: NEON"
```

### Vector Operations

```cpp
using namespace meshml::simd;

const size_t size = 1000000;
std::vector<float> a(size);
std::vector<float> b(size);
std::vector<float> result(size);

// Vector addition (SIMD-optimized)
vector_add(a.data(), b.data(), result.data(), size);

// Dot product (SIMD-optimized)
float dot = vector_dot(a.data(), b.data(), size);

// Vector norm
float norm = vector_norm(a.data(), size);

// Element-wise multiplication
vector_mul(a.data(), b.data(), result.data(), size);

// Scalar multiplication
vector_scale(a.data(), 2.0f, result.data(), size);
```

### Performance Comparison

```cpp
// Benchmark SIMD vs scalar
simd::benchmark_simd_operations();

// Output:
// Vector Add (1000000 elements):
//   Time: 0.85 ms/operation
//   Throughput: 4.7 GFLOP/s
```

**Typical Speedups:**
- AVX2: 4-8x faster than scalar
- NEON: 3-4x faster than scalar

### Advanced Operations

```cpp
// ReLU activation
vector_relu(input.data(), output.data(), size);

// Gradient clipping
gradient_clip(gradients.data(), size, 5.0f);  // Clip to [-5, 5]

// Softmax
vector_softmax(logits.data(), probabilities.data(), size);

// Matrix-vector multiplication
matrix_vector_mul(
    matrix.data(),   // Row-major matrix
    vector.data(),   // Input vector
    result.data(),   // Output vector
    rows, cols
);
```

## Memory Pooling

### Basic Memory Pool

```cpp
// Create 100 MB pool
auto pool = create_memory_pool(100 * 1024 * 1024, "cpu");

// Allocate memory
void* ptr1 = pool->allocate(1024 * 1024);  // 1 MB
void* ptr2 = pool->allocate(2 * 1024 * 1024);  // 2 MB

// Deallocate
pool->deallocate(ptr1);
pool->deallocate(ptr2);

// Reset pool (mark all as free)
pool->reset();

// Statistics
pool->print_stats();
```

### Tensor Memory Pool

```cpp
// Specialized pool for tensors
auto tensor_pool = create_tensor_memory_pool(500 * 1024 * 1024, "cpu");

// Allocate tensor (float array)
float* tensor1 = tensor_pool->allocate_tensor(100000);  // 100K floats

// Use tensor
for (size_t i = 0; i < 100000; ++i) {
    tensor1[i] = static_cast<float>(i);
}

// Deallocate
tensor_pool->deallocate_tensor(tensor1);
```

### Smart Pointers with Pool

```cpp
// RAII-style pool allocation
auto tensor = tensor_pool->make_tensor(50000);

// tensor automatically deallocated when out of scope
// No manual cleanup needed!
```

**Benefits:**
- **Faster allocation**: 10-100x faster than malloc/new
- **Reduced fragmentation**: Better memory locality
- **Lower overhead**: Fewer system calls
- **Predictable performance**: No unexpected allocation delays

## Throughput Monitoring

```cpp
ThroughputMonitor monitor;

// Training loop
for (int batch = 0; batch < num_batches; ++batch) {
    // ... process batch ...
    
    monitor.record_batch(batch_size);
    
    // Check progress
    double samples_per_sec = monitor.get_samples_per_second();
    double batches_per_sec = monitor.get_batches_per_second();
}
```

## Integrated Training Example

```cpp
#include "meshml/training/trainer.h"
#include "meshml/utils/performance.h"
#include "meshml/utils/memory_pool.h"

// Create profiler
auto profiler = create_performance_profiler();
auto memory_profiler = create_memory_profiler("cuda");

// Create memory pool for temporary allocations
auto temp_pool = create_memory_pool(100 * 1024 * 1024, "cpu");

// Training loop with profiling
for (int epoch = 0; epoch < num_epochs; ++epoch) {
    for (int batch = 0; batch < num_batches; ++batch) {
        // Profile data loading
        {
            ProfileScope scope(*profiler, "data_loading");
            // Load batch...
        }
        
        // Profile training step
        {
            ProfileScope scope(*profiler, "train_step");
            // Forward, backward, optimize...
        }
        
        // Monitor memory every 10 batches
        if (batch % 10 == 0) {
            std::cout << "GPU Memory: " 
                      << memory_profiler->get_memory_usage() << " MB" 
                      << std::endl;
        }
    }
    
    // Print epoch summary
    auto metrics = profiler->get_metrics();
    std::cout << "Epoch " << epoch << ": " 
              << metrics.samples_per_second << " samples/sec" 
              << std::endl;
}

// Final summary
profiler->print_summary();
memory_profiler->print_summary();
```

## Compiler Optimizations

### CMake Build Flags

```bash
# Release build with optimizations
cmake -DCMAKE_BUILD_TYPE=Release ..

# Enable AVX2 (automatically enabled if supported)
# No manual flags needed - detected automatically

# CUDA support
cmake -DUSE_CUDA=ON ..
```

### Manual Compiler Flags

For advanced users:

```cmake
# Additional optimizations (already included in Release build)
set(CMAKE_CXX_FLAGS_RELEASE "-O3 -march=native -DNDEBUG")

# Link-time optimization
set(CMAKE_INTERPROCEDURAL_OPTIMIZATION TRUE)
```

## Performance Best Practices

### 1. Use Appropriate Batch Size

```cpp
// Larger batch = better GPU utilization
// Start with 32, increase until memory limit
config.training.batch_size = 128;
```

### 2. Enable Mixed Precision (CUDA)

```cpp
trainer->set_mixed_precision(true);  // 1.5-2x speedup
```

### 3. Multi-threaded Data Loading

```cpp
auto loader = DataLoaderBuilder()
    .num_workers(4)  // 4 parallel workers
    .pin_memory(true)  // Fast GPU transfer
    .build();
```

### 4. Profile Regularly

```cpp
// Profile every 100 batches
if (batch % 100 == 0) {
    profiler->print_summary();
    profiler->reset();  // Reset for next interval
}
```

### 5. Use Memory Pools for Temporary Data

```cpp
// Instead of:
std::vector<float> temp(size);

// Use:
auto temp = temp_pool->make_tensor(size);
```

### 6. Minimize CPU-GPU Transfers

```cpp
// Bad: Transfer every batch
for (auto batch : loader) {
    auto gpu_batch = batch.to(torch::kCUDA);
    // ...
}

// Good: Pin memory and let loader handle it
auto loader = DataLoaderBuilder()
    .pin_memory(true)
    .build();
```

## Benchmarking

### Run Performance Example

```bash
cd build
./examples/performance_example
```

Expected output:
```
=== Performance Profiling Demo ===
Performance Metrics:
  Throughput:
    Samples/sec: 3200.0
    Batches/sec: 100.0
  Timing Breakdown:
    Data Loading: 5.2 ms
    Forward Pass:  10.3 ms
    Backward Pass: 12.1 ms
    Optimizer:     3.4 ms
...

=== SIMD Operations Demo ===
SIMD Capabilities: AVX2
Vector Add (1000000 elements): 0.85 ms
Dot Product: 333333.5 (computed in 1.2 ms)
...
```

## Performance Targets

| Metric | CPU | GPU (CUDA + AMP) |
|--------|-----|------------------|
| Samples/sec | 1000-3000 | 5000-15000 |
| Batch time | 30-50 ms | 10-20 ms |
| Memory usage | 500 MB - 2 GB | 2-8 GB |
| Throughput vs Python | 1.1-1.2x | 1.3-1.5x |

## Troubleshooting

### Low Throughput

1. **Check batch size**: Increase if memory allows
2. **Profile bottlenecks**: Use `profiler->print_summary()`
3. **Enable mixed precision**: CUDA only, free 1.5-2x speedup
4. **Increase data workers**: More parallel loading

### High Memory Usage

1. **Reduce batch size**
2. **Enable gradient accumulation**
3. **Use memory pools** for temporary allocations
4. **Monitor with**: `memory_profiler->print_summary()`

### SIMD Not Working

```cpp
// Check capabilities
std::cout << simd::get_simd_capabilities() << std::endl;

// If "Scalar only", verify:
// 1. Compiler flags: -mavx2 or -march=armv8-a+simd
// 2. CPU support: lscpu | grep avx2 (Linux)
```

## References

- Example code: `examples/performance_example.cpp`
- API documentation: `include/meshml/utils/`
- Training integration: `docs/TRAINING_GUIDE.md`
