# Device Optimization Utilities

This module provides comprehensive tools for optimizing training performance across different devices (CUDA, MPS, CPU).

## Features

### 1. Memory Profiling (`MemoryProfiler`)

Track memory usage during training to identify memory bottlenecks and optimize resource usage.

**Usage:**
```python
from meshml_worker.utils.optimization import MemoryProfiler

profiler = MemoryProfiler(device="cuda:0")

# Profile a training step
with profiler.profile("forward_pass"):
    output = model(input)

# Get statistics
stats = profiler.get_stats("forward_pass")
print(f"Memory used: {stats['memory_diff']['allocated_diff'] / 1024**2:.2f} MB")

# Print summary
profiler.print_summary()
```

**Supported Devices:**
- **CUDA**: Tracks `allocated`, `reserved`, `max_allocated`, `max_reserved`
- **MPS**: Tracks `allocated`, `driver_allocated` (limited API)
- **CPU**: Tracks RSS and VMS using psutil

### 2. Performance Benchmarking (`PerformanceBenchmark`)

Measure training throughput, latency, and other performance metrics.

**Usage:**
```python
from meshml_worker.utils.optimization import PerformanceBenchmark

benchmark = PerformanceBenchmark()

# Benchmark epochs
benchmark.start_epoch()
for batch in dataloader:
    benchmark.start_batch()
    # Training code
    benchmark.end_batch(batch_size=32)
benchmark.end_epoch()

# Get statistics
stats = benchmark.get_stats()
print(f"Samples/sec: {stats['samples_per_second']:.2f}")
print(f"Avg batch time: {stats['avg_batch_time']:.4f}s")

# Print summary
benchmark.print_summary()
```

**Metrics:**
- Average epoch time
- Average batch time
- Samples per second
- Batches per second
- Total samples processed

### 3. Optimized DataLoader (`OptimizedDataLoader`)

Automatically configures DataLoader settings for optimal performance based on device and dataset characteristics.

**Usage:**
```python
from meshml_worker.utils.optimization import OptimizedDataLoader

loader = OptimizedDataLoader(
    dataset=train_dataset,
    batch_size=32,
    device="cuda:0",
    shuffle=True
)

for batch in loader:
    # Training code
    pass
```

**Automatic Optimizations:**

| Device | pin_memory | num_workers | persistent_workers |
|--------|-----------|-------------|-------------------|
| CUDA   | ✅ True   | 4 (or CPU-1) | ✅ True          |
| MPS    | ❌ False  | 4 (or CPU-1) | ✅ True          |
| CPU    | ❌ False  | CPU/2       | ✅ True          |

For small datasets (<10 batches), automatically uses `num_workers=0` to avoid overhead.

### 4. DataLoader Settings Optimizer

Get recommended DataLoader settings without creating a DataLoader.

**Usage:**
```python
from meshml_worker.utils.optimization import optimize_dataloader_settings

settings = optimize_dataloader_settings(
    device="cuda:0",
    batch_size=32,
    dataset_size=10000
)

print(f"Recommended num_workers: {settings['num_workers']}")
print(f"Use pin_memory: {settings['pin_memory']}")
```

### 5. Device Performance Benchmarking

Benchmark model inference performance on a device.

**Usage:**
```python
from meshml_worker.utils.optimization import benchmark_device_performance

results = benchmark_device_performance(
    device="cuda:0",
    model=my_model,
    input_shape=(32, 3, 224, 224)  # (batch_size, channels, height, width)
)

print(f"Throughput: {results['samples_per_second']:.2f} samples/sec")
print(f"Latency: {results['ms_per_batch']:.2f} ms/batch")
```

## Integration with Trainer

The `Trainer` class automatically integrates these optimization tools:

```python
# Memory profiling every 10th batch
with profiler.profile(f"epoch_{epoch}_batch_{batch_idx}"):
    loss, predictions = self._train_batch(data, target, batch_idx, epoch)

# Performance benchmarking for all batches
benchmark.start_batch()
# ... training code ...
benchmark.end_batch(batch_size=data.size(0))

# Print performance summary every 5 epochs
if epoch % 5 == 0:
    performance_benchmark.print_summary()
```

## Performance Tips

### Memory Optimization
1. **Use mixed precision** (FP16) on CUDA devices to reduce memory usage
2. **Profile memory usage** to identify memory-hungry operations
3. **Use gradient checkpointing** for large models
4. **Clear cache** periodically with `clear_device_cache(device)`

### Throughput Optimization
1. **Enable pin_memory** for CUDA devices (automatic with `OptimizedDataLoader`)
2. **Use multiple workers** for data loading (automatic optimization)
3. **Enable persistent workers** to avoid subprocess overhead
4. **Set prefetch_factor=2** for better pipelining (automatic)

### Device-Specific
- **CUDA**: Use mixed precision, pin_memory, multiple workers
- **MPS** (Apple Silicon): Use multiple workers, but pin_memory is not beneficial
- **CPU**: Fewer workers to avoid overhead, no pin_memory needed

## Example: Full Training with Optimization

```python
from meshml_worker.utils.optimization import (
    MemoryProfiler,
    PerformanceBenchmark,
    OptimizedDataLoader
)

# Setup
device = "cuda:0"
profiler = MemoryProfiler(device=device)
benchmark = PerformanceBenchmark()

loader = OptimizedDataLoader(
    dataset=train_dataset,
    batch_size=32,
    device=device,
    shuffle=True
)

# Training loop
for epoch in range(num_epochs):
    benchmark.start_epoch()
    
    for batch_idx, (data, target) in enumerate(loader):
        benchmark.start_batch()
        
        # Profile periodically
        if batch_idx % 10 == 0:
            with profiler.profile(f"epoch_{epoch}_batch_{batch_idx}"):
                loss = train_step(data, target)
        else:
            loss = train_step(data, target)
        
        benchmark.end_batch(batch_size=len(data))
    
    benchmark.end_epoch()
    
    # Print summaries every 5 epochs
    if epoch % 5 == 0:
        benchmark.print_summary()
        profiler.print_summary()
```

## Testing

The module includes 42 comprehensive tests covering:
- Memory profiling for CUDA, MPS, and CPU
- Performance benchmarking
- DataLoader optimization
- Device performance benchmarking
- Integration tests

Run tests:
```bash
pytest tests/test_optimization.py -v
```

Note: Some tests require PyTorch to be installed. Without PyTorch, 21/42 tests will pass (non-PyTorch functionality).

## Dependencies

- **Required**: `psutil` (for CPU memory tracking)
- **Optional**: `torch` (for CUDA/MPS memory tracking and DataLoader optimization)

Install:
```bash
pip install psutil
pip install torch  # Optional, for GPU support
```
