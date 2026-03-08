/**
 * @file test_cuda_kernels.cpp
 * @brief Unit tests for CUDA kernels
 */

#include <gtest/gtest.h>

#ifdef USE_CUDA

#include "meshml/cuda/cuda_kernels.h"
#include <torch/torch.h>
#include <cmath>

class CudaKernelsTest : public ::testing::Test {
protected:
    void SetUp() override {
        if (!torch::cuda::is_available()) {
            GTEST_SKIP() << "CUDA not available, skipping CUDA tests";
        }
        device_ = torch::kCUDA;
    }

    torch::Device device_{torch::kCUDA};
    const float tolerance_ = 1e-4f;
};

// Test: Fused linear combination
TEST_F(CudaKernelsTest, FusedLinearCombination) {
    auto a = torch::randn({1024, 1024}, torch::device(device_));
    auto b = torch::randn({1024, 1024}, torch::device(device_));
    float alpha = 2.5f;
    float beta = 1.5f;

    // CUDA kernel result
    auto result = meshml::cuda::CudaKernels::fused_linear_combination(a, b, alpha, beta);

    // PyTorch reference
    auto expected = alpha * a + beta * b;

    EXPECT_TRUE(torch::allclose(result, expected, tolerance_, tolerance_));
}

// Test: Fused ReLU + clipping
TEST_F(CudaKernelsTest, FusedReLUClip) {
    auto input = torch::randn({1024, 1024}, torch::device(device_)) * 10.0f;
    float clip_value = 5.0f;

    // CUDA kernel result
    auto result = meshml::cuda::CudaKernels::fused_relu_clip(input, clip_value);

    // PyTorch reference
    auto expected = torch::clamp(torch::relu(input), -clip_value, clip_value);

    EXPECT_TRUE(torch::allclose(result, expected, tolerance_, tolerance_));
}

// Test: Fast L2 norm
TEST_F(CudaKernelsTest, FastL2Norm) {
    auto input = torch::randn({1024, 1024}, torch::device(device_));

    // CUDA kernel result
    float result = meshml::cuda::CudaKernels::fast_l2_norm(input);

    // PyTorch reference
    float expected = torch::norm(input, 2).item<float>();

    EXPECT_NEAR(result, expected, expected * tolerance_);
}

// Test: Batch normalization inference
TEST_F(CudaKernelsTest, BatchNormInference) {
    int64_t num_features = 128;
    auto input = torch::randn({32, num_features}, torch::device(device_));
    auto mean = torch::randn({num_features}, torch::device(device_));
    auto variance = torch::abs(torch::randn({num_features}, torch::device(device_))) + 0.1f;
    auto gamma = torch::randn({num_features}, torch::device(device_));
    auto beta = torch::randn({num_features}, torch::device(device_));
    float epsilon = 1e-5f;

    // CUDA kernel result
    auto result = meshml::cuda::CudaKernels::batch_norm_inference(
        input, mean, variance, gamma, beta, epsilon
    );

    // PyTorch reference
    auto normalized = (input - mean) / torch::sqrt(variance + epsilon);
    auto expected = normalized * gamma + beta;

    EXPECT_TRUE(torch::allclose(result, expected, tolerance_, tolerance_));
}

// Test: Softmax with temperature
TEST_F(CudaKernelsTest, SoftmaxWithTemperature) {
    auto input = torch::randn({32, 1000}, torch::device(device_));
    float temperature = 2.0f;

    // CUDA kernel result
    auto result = meshml::cuda::CudaKernels::softmax_with_temperature(input, temperature);

    // PyTorch reference
    auto expected = torch::softmax(input / temperature, /*dim=*/1);

    EXPECT_TRUE(torch::allclose(result, expected, tolerance_, tolerance_));
}

// Test: Cross-entropy with label smoothing
TEST_F(CudaKernelsTest, CrossEntropyLabelSmoothing) {
    auto logits = torch::randn({32, 10}, torch::device(device_));
    auto targets = torch::randint(0, 10, {32}, torch::device(device_));
    float smoothing = 0.1f;

    // CUDA kernel result
    float result = meshml::cuda::CudaKernels::cross_entropy_label_smoothing(
        logits, targets, smoothing
    );

    // PyTorch reference (simplified)
    auto log_probs = torch::log_softmax(logits, /*dim=*/1);
    int64_t num_classes = logits.size(1);
    
    // Create smoothed labels
    auto one_hot = torch::zeros_like(logits);
    one_hot.scatter_(1, targets.unsqueeze(1), 1.0f);
    auto smooth_labels = one_hot * (1.0f - smoothing) + smoothing / num_classes;
    
    auto loss = -(smooth_labels * log_probs).sum(1).mean();
    float expected = loss.item<float>();

    EXPECT_NEAR(result, expected, std::abs(expected) * tolerance_ + tolerance_);
}

// Test: Gradient clipping by norm
TEST_F(CudaKernelsTest, GradientClippingByNorm) {
    auto gradients = torch::randn({1024, 1024}, torch::device(device_)) * 10.0f;
    float max_norm = 1.0f;

    // CUDA kernel result
    auto result = meshml::cuda::CudaKernels::clip_gradients_by_norm(gradients, max_norm);

    // PyTorch reference
    auto grad_norm = torch::norm(gradients, 2);
    auto expected = gradients;
    if (grad_norm.item<float>() > max_norm) {
        expected = gradients * (max_norm / grad_norm);
    }

    EXPECT_TRUE(torch::allclose(result, expected, tolerance_, tolerance_));
}

// Test: Gradient accumulation with momentum
TEST_F(CudaKernelsTest, GradientAccumulationMomentum) {
    auto gradients = torch::randn({512, 512}, torch::device(device_));
    auto accumulated = torch::randn({512, 512}, torch::device(device_));
    float momentum = 0.9f;

    // CUDA kernel result
    auto result = meshml::cuda::CudaKernels::gradient_accumulation_momentum(
        gradients, accumulated, momentum
    );

    // PyTorch reference
    auto expected = momentum * accumulated + gradients;

    EXPECT_TRUE(torch::allclose(result, expected, tolerance_, tolerance_));
}

// Test: Fused Adam optimizer step
TEST_F(CudaKernelsTest, FusedAdamStep) {
    auto param = torch::randn({512, 512}, torch::device(device_));
    auto grad = torch::randn({512, 512}, torch::device(device_));
    auto m = torch::zeros({512, 512}, torch::device(device_));
    auto v = torch::zeros({512, 512}, torch::device(device_));
    float lr = 0.001f;
    float beta1 = 0.9f;
    float beta2 = 0.999f;
    float epsilon = 1e-8f;
    int step = 1;

    // CUDA kernel result
    auto result = meshml::cuda::CudaKernels::fused_adam_step(
        param, grad, m, v, lr, beta1, beta2, epsilon, step
    );

    // PyTorch reference
    auto m_new = beta1 * m + (1.0f - beta1) * grad;
    auto v_new = beta2 * v + (1.0f - beta2) * grad * grad;
    
    auto m_hat = m_new / (1.0f - std::pow(beta1, step));
    auto v_hat = v_new / (1.0f - std::pow(beta2, step));
    
    auto expected = param - lr * m_hat / (torch::sqrt(v_hat) + epsilon);

    EXPECT_TRUE(torch::allclose(result, expected, tolerance_, tolerance_));
}

// Test: Gradient unscaling for mixed precision
TEST_F(CudaKernelsTest, GradientUnscaling) {
    auto gradients = torch::randn({512, 512}, torch::device(device_)) * 1000.0f;
    float scale = 1024.0f;

    // CUDA kernel result
    auto result = meshml::cuda::CudaKernels::gradient_unscaling(gradients, scale);

    // PyTorch reference
    auto expected = gradients / scale;

    EXPECT_TRUE(torch::allclose(result, expected, tolerance_, tolerance_));
}

// Test: CudaMemoryManager - pinned memory allocation
TEST_F(CudaKernelsTest, PinnedMemoryAllocation) {
    meshml::cuda::CudaMemoryManager mem_manager;
    
    size_t size = 1024 * 1024 * sizeof(float);
    void* ptr = mem_manager.allocate_pinned(size);
    
    ASSERT_NE(ptr, nullptr);
    
    // Try to use the memory
    float* float_ptr = static_cast<float*>(ptr);
    float_ptr[0] = 42.0f;
    EXPECT_FLOAT_EQ(float_ptr[0], 42.0f);
    
    mem_manager.free_pinned(ptr);
}

// Test: CudaMemoryManager - memory usage tracking
TEST_F(CudaKernelsTest, MemoryUsageTracking) {
    meshml::cuda::CudaMemoryManager mem_manager;
    
    size_t initial_usage = mem_manager.get_memory_usage();
    
    size_t size = 1024 * 1024 * sizeof(float);
    void* ptr = mem_manager.allocate_pinned(size);
    
    size_t after_alloc = mem_manager.get_memory_usage();
    EXPECT_GT(after_alloc, initial_usage);
    
    mem_manager.free_pinned(ptr);
    
    size_t after_free = mem_manager.get_memory_usage();
    EXPECT_EQ(after_free, initial_usage);
}

// Test: CudaStreamManager - stream creation
TEST_F(CudaKernelsTest, StreamCreation) {
    meshml::cuda::CudaStreamManager stream_manager;
    
    int stream_id = stream_manager.create_stream();
    EXPECT_GE(stream_id, 0);
    
    cudaStream_t stream = stream_manager.get_stream(stream_id);
    EXPECT_NE(stream, nullptr);
}

// Test: CudaStreamManager - concurrent execution
TEST_F(CudaKernelsTest, ConcurrentExecution) {
    meshml::cuda::CudaStreamManager stream_manager;
    
    int stream1 = stream_manager.create_stream();
    int stream2 = stream_manager.create_stream();
    
    // Launch operations on different streams
    auto a1 = torch::randn({512, 512}, torch::device(device_));
    auto b1 = torch::randn({512, 512}, torch::device(device_));
    
    auto a2 = torch::randn({512, 512}, torch::device(device_));
    auto b2 = torch::randn({512, 512}, torch::device(device_));
    
    // Operations should execute concurrently
    auto result1 = meshml::cuda::CudaKernels::fused_linear_combination(a1, b1, 1.0f, 1.0f);
    auto result2 = meshml::cuda::CudaKernels::fused_linear_combination(a2, b2, 1.0f, 1.0f);
    
    stream_manager.synchronize(stream1);
    stream_manager.synchronize(stream2);
    
    EXPECT_TRUE(result1.defined());
    EXPECT_TRUE(result2.defined());
}

// Test: Device information
TEST_F(CudaKernelsTest, DeviceInformation) {
    int device_count = meshml::cuda::CudaKernels::get_device_count();
    EXPECT_GT(device_count, 0);
    
    auto device_name = meshml::cuda::CudaKernels::get_device_name(0);
    EXPECT_FALSE(device_name.empty());
    
    size_t total_memory = meshml::cuda::CudaKernels::get_total_memory(0);
    EXPECT_GT(total_memory, 0);
    
    size_t free_memory = meshml::cuda::CudaKernels::get_free_memory(0);
    EXPECT_GT(free_memory, 0);
    EXPECT_LE(free_memory, total_memory);
}

// Test: Optimal block size calculation
TEST_F(CudaKernelsTest, OptimalBlockSize) {
    int block_size = meshml::cuda::CudaKernels::get_optimal_block_size(1024);
    EXPECT_GT(block_size, 0);
    EXPECT_LE(block_size, 1024);
    
    // Should be a multiple of 32 (warp size)
    EXPECT_EQ(block_size % 32, 0);
}

// Test: Kernel warmup
TEST_F(CudaKernelsTest, KernelWarmup) {
    // Warmup should not throw
    EXPECT_NO_THROW({
        meshml::cuda::CudaKernels::warmup_kernels();
    });
}

// Performance test: Compare CUDA kernel vs PyTorch
TEST_F(CudaKernelsTest, DISABLED_PerformanceComparison) {
    const int iterations = 100;
    auto a = torch::randn({1024, 1024}, torch::device(device_));
    auto b = torch::randn({1024, 1024}, torch::device(device_));

    // Warmup
    meshml::cuda::CudaKernels::warmup_kernels();

    // Benchmark CUDA kernel
    cudaEvent_t start, stop;
    cudaEventCreate(&start);
    cudaEventCreate(&stop);

    cudaEventRecord(start);
    for (int i = 0; i < iterations; ++i) {
        auto result = meshml::cuda::CudaKernels::fused_linear_combination(a, b, 2.0f, 3.0f);
    }
    cudaEventRecord(stop);
    cudaEventSynchronize(stop);

    float cuda_time;
    cudaEventElapsedTime(&cuda_time, start, stop);

    // Benchmark PyTorch
    cudaEventRecord(start);
    for (int i = 0; i < iterations; ++i) {
        auto result = 2.0f * a + 3.0f * b;
    }
    cudaEventRecord(stop);
    cudaEventSynchronize(stop);

    float pytorch_time;
    cudaEventElapsedTime(&pytorch_time, start, stop);

    cudaEventDestroy(start);
    cudaEventDestroy(stop);

    std::cout << "CUDA kernel time: " << cuda_time << " ms\n";
    std::cout << "PyTorch time: " << pytorch_time << " ms\n";
    std::cout << "Speedup: " << pytorch_time / cuda_time << "x\n";

    // CUDA kernel should be faster or comparable
    EXPECT_LE(cuda_time, pytorch_time * 1.5);  // Allow 50% tolerance
}

#else

// Dummy test when CUDA is not available
TEST(CudaKernelsTest, CudaNotAvailable) {
    GTEST_SKIP() << "CUDA support not enabled (USE_CUDA=OFF)";
}

#endif  // USE_CUDA
