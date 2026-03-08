# Phase 9 Testing Guide

## Overview

This document describes the comprehensive test suite for Phase 9 (C++ Worker). The test suite covers all major components with unit tests, integration tests, and performance benchmarks.

## Test Coverage

### Component Test Coverage

| Component | Test File | Tests | Coverage Target |
|-----------|-----------|-------|-----------------|
| Config Loader | `test_config_loader.cpp` | 17 tests | 90%+ |
| Model Loader | `test_model_loader.cpp` | 19 tests | 85%+ |
| CUDA Kernels | `test_cuda_kernels.cpp` | 24 tests | 80%+ |
| Performance Utils | `test_performance.cpp` | 23 tests | 85%+ |
| **Total** | **4 files** | **83 tests** | **85%+** |

## Test Categories

### 1. Config Loader Tests (17 tests)

**Functionality Tests:**
- ✅ Load valid YAML configuration
- ✅ Load minimal configuration with defaults
- ✅ Configuration merging
- ✅ YAML export
- ✅ JSON export
- ✅ Round-trip YAML conversion
- ✅ Load from string

**Validation Tests:**
- ✅ Missing worker ID
- ✅ Invalid learning rate
- ✅ Invalid batch size
- ✅ Invalid device
- ✅ Invalid optimizer
- ✅ Invalid port

**Error Handling Tests:**
- ✅ File not found
- ✅ Malformed YAML
- ✅ Invalid JSON

### 2. Model Loader Tests (19 tests)

**Registry Tests:**
- ✅ List registered models
- ✅ Check if model is registered
- ✅ Register custom model

**Model Creation Tests:**
- ✅ Create MLP model
- ✅ Create MNIST CNN model
- ✅ Create ResNet18 model
- ✅ Test forward pass for all models

**Model Operations:**
- ✅ Count parameters
- ✅ Generate model summary
- ✅ Save/load TorchScript
- ✅ Save/load checkpoint
- ✅ Load from registry
- ✅ Model gradients
- ✅ Model to different device
- ✅ Training/eval mode
- ✅ Zero gradients

**Error Handling:**
- ✅ Unknown model
- ✅ Load non-existent file

### 3. CUDA Kernel Tests (24 tests)

**Correctness Tests:**
- ✅ Fused linear combination
- ✅ Fused ReLU + clipping
- ✅ Fast L2 norm
- ✅ Batch normalization inference
- ✅ Softmax with temperature
- ✅ Cross-entropy with label smoothing
- ✅ Gradient clipping by norm
- ✅ Gradient accumulation with momentum
- ✅ Fused Adam optimizer step
- ✅ Gradient unscaling

**Memory Management:**
- ✅ Pinned memory allocation
- ✅ Memory usage tracking
- ✅ Memory manager stats

**Stream Management:**
- ✅ Stream creation
- ✅ Concurrent execution
- ✅ Stream synchronization

**Device Information:**
- ✅ Get device count
- ✅ Get device name
- ✅ Get total memory
- ✅ Get free memory
- ✅ Optimal block size
- ✅ Kernel warmup

**Performance:**
- 🔄 Performance comparison (disabled by default)

### 4. Performance Tests (23 tests)

**Profiler Tests:**
- ✅ Basic timing
- ✅ Multiple operations
- ✅ Nested operations
- ✅ Reset functionality
- ✅ Report generation
- ✅ Profiler overhead

**SIMD Tests:**
- ✅ Vector addition
- ✅ Vector multiplication
- ✅ Scalar multiplication
- ✅ Dot product
- ✅ ReLU activation
- ✅ Sum reduction

**Memory Pool Tests:**
- ✅ Basic allocation
- ✅ Deallocation
- ✅ Memory reuse
- ✅ Multiple sizes
- ✅ Out of memory
- ✅ Reset
- ✅ Statistics
- ✅ Thread safety

**Performance Benchmarks:**
- 🔄 SIMD vs scalar (disabled by default)
- 🔄 Memory pool vs malloc (disabled by default)

## Running Tests

### Prerequisites

```bash
# Install Google Test
# On macOS:
brew install googletest

# On Ubuntu:
sudo apt-get install libgtest-dev

# On Windows:
vcpkg install gtest
```

### Build with Tests

```bash
cd workers/cpp-worker
mkdir build && cd build

# Standard build with tests
cmake -DCMAKE_BUILD_TYPE=Release -DBUILD_TESTS=ON ..
make -j$(nproc)

# With CUDA support
cmake -DCMAKE_BUILD_TYPE=Release -DBUILD_TESTS=ON -DUSE_CUDA=ON ..
make -j$(nproc)
```

### Run All Tests

```bash
# Run all tests
make run_tests

# Or using ctest directly
ctest --output-on-failure --verbose

# Run specific test
./tests/meshml_tests --gtest_filter=ConfigLoaderTest.*

# Run with specific patterns
./tests/meshml_tests --gtest_filter=*Model*
```

### Run Individual Test Suites

```bash
# Config loader tests only
./tests/meshml_tests --gtest_filter=ConfigLoaderTest.*

# Model loader tests only
./tests/meshml_tests --gtest_filter=ModelLoaderTest.*

# CUDA kernel tests only (requires CUDA)
./tests/meshml_tests --gtest_filter=CudaKernelsTest.*

# Performance tests only
./tests/meshml_tests --gtest_filter=*Test.*
```

### Run Performance Benchmarks

Performance benchmarks are disabled by default. To run them:

```bash
# Run all performance benchmarks
./tests/meshml_tests --gtest_also_run_disabled_tests --gtest_filter=*Performance*

# Run specific benchmark
./tests/meshml_tests --gtest_also_run_disabled_tests --gtest_filter=*SIMDvsScalar*
```

## Code Coverage

### Generate Coverage Report (Linux/macOS)

```bash
# Build with coverage flags
cmake -DCMAKE_BUILD_TYPE=Debug -DBUILD_TESTS=ON ..
make -j$(nproc)

# Generate coverage report
make coverage

# View report
open coverage/index.html  # macOS
xdg-open coverage/index.html  # Linux
```

### Coverage Targets

- **Overall**: 85%+ line coverage
- **Config Loader**: 90%+ (critical path)
- **Model Loader**: 85%+
- **CUDA Kernels**: 80%+ (platform-dependent)
- **Performance Utils**: 85%+

## Test Results

### Expected Output

```
[==========] Running 83 tests from 4 test suites.
[----------] Global test environment set-up.
[----------] 17 tests from ConfigLoaderTest
[ RUN      ] ConfigLoaderTest.LoadValidYaml
[       OK ] ConfigLoaderTest.LoadValidYaml (5 ms)
...
[----------] 17 tests from ConfigLoaderTest (85 ms total)

[----------] 19 tests from ModelLoaderTest
[ RUN      ] ModelLoaderTest.ListRegisteredModels
[       OK ] ModelLoaderTest.ListRegisteredModels (2 ms)
...
[----------] 19 tests from ModelLoaderTest (450 ms total)

[----------] 24 tests from CudaKernelsTest
[ RUN      ] CudaKernelsTest.FusedLinearCombination
[       OK ] CudaKernelsTest.FusedLinearCombination (15 ms)
...
[----------] 24 tests from CudaKernelsTest (780 ms total)

[----------] 23 tests from PerformanceTest
[ RUN      ] PerformanceTest.ProfilerBasicTiming
[       OK ] PerformanceTest.ProfilerBasicTiming (105 ms)
...
[----------] 23 tests from PerformanceTest (620 ms total)

[----------] Global test environment tear-down
[==========] 83 tests from 4 test suites ran. (1935 ms total)
[  PASSED  ] 83 tests.
```

## Continuous Integration

### GitHub Actions Workflow

```yaml
name: C++ Worker Tests

on: [push, pull_request]

jobs:
  test:
    runs-on: ${{ matrix.os }}
    strategy:
      matrix:
        os: [ubuntu-latest, macos-latest]
        build_type: [Debug, Release]
        
    steps:
      - uses: actions/checkout@v3
      
      - name: Install dependencies
        run: |
          if [ "$RUNNER_OS" == "Linux" ]; then
            sudo apt-get update
            sudo apt-get install -y libgtest-dev cmake
          elif [ "$RUNNER_OS" == "macOS" ]; then
            brew install googletest cmake
          fi
          
      - name: Build
        run: |
          cd workers/cpp-worker
          mkdir build && cd build
          cmake -DCMAKE_BUILD_TYPE=${{ matrix.build_type }} -DBUILD_TESTS=ON ..
          make -j$(nproc)
          
      - name: Run tests
        run: |
          cd workers/cpp-worker/build
          ctest --output-on-failure --verbose
```

## Troubleshooting

### Common Issues

**1. Google Test not found**
```bash
# Install Google Test
brew install googletest  # macOS
sudo apt-get install libgtest-dev  # Ubuntu
```

**2. CUDA tests fail**
- Ensure CUDA is installed and available
- Set correct CUDA architecture in CMakeLists.txt
- Skip CUDA tests with: `--gtest_filter=-CudaKernelsTest.*`

**3. LibTorch not found**
- Enable auto-download: `-DDOWNLOAD_LIBTORCH=ON`
- Or set manually: `-DCMAKE_PREFIX_PATH=/path/to/libtorch`

**4. Tests timeout**
- Increase timeout: `ctest --timeout 600`
- Run specific tests instead of all

**5. Memory errors**
- Run with address sanitizer:
  ```bash
  cmake -DCMAKE_BUILD_TYPE=Debug -DCMAKE_CXX_FLAGS="-fsanitize=address" ..
  make
  ```

## Performance Benchmarks

### Expected Performance

| Test | Speedup | Notes |
|------|---------|-------|
| SIMD vs Scalar | 4-8x | AVX2/NEON enabled |
| Memory Pool vs malloc | 10-340x | Depends on allocation size |
| CUDA fused ops | 1.5-2x | vs separate PyTorch ops |
| CUDA Adam | 2-3x | vs PyTorch Adam |

### Running Benchmarks

```bash
# All benchmarks
./tests/meshml_tests --gtest_also_run_disabled_tests --gtest_filter=*DISABLED_*

# Specific benchmark
./tests/meshml_tests --gtest_also_run_disabled_tests --gtest_filter=*SIMDvsScalar*
```

## Test Maintenance

### Adding New Tests

1. Create test file in `tests/` directory
2. Add to `TEST_SOURCES` in `tests/CMakeLists.txt`
3. Follow Google Test naming conventions
4. Document in this file

### Test Naming Convention

```cpp
TEST(TestSuiteName, TestName) {
    // Arrange
    // Act
    // Assert
}
```

### Test Fixtures

```cpp
class MyTest : public ::testing::Test {
protected:
    void SetUp() override { /* setup */ }
    void TearDown() override { /* cleanup */ }
};

TEST_F(MyTest, TestName) { /* test */ }
```

## Test Summary

**Total Tests**: 83
**Test Files**: 4
**Target Coverage**: 85%+
**Estimated Runtime**: < 2 minutes (CPU), < 5 minutes (with CUDA)

---

## Next Steps

After all tests pass:
1. ✅ Review coverage report
2. ✅ Add any missing edge cases
3. ✅ Document any platform-specific issues
4. ✅ Set up CI/CD pipeline
5. ✅ Mark Phase 9 as complete in TASKS.md

**Status**: Phase 9 testing suite complete! 🎉
