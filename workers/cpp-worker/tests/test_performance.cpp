/**
 * @file test_performance.cpp
 * @brief Unit tests for performance utilities (SIMD, memory pool, profiling)
 */

#include <gtest/gtest.h>
#include "meshml/utils/performance.h"
#include "meshml/utils/simd_ops.h"
#include "meshml/utils/memory_pool.h"
#include <torch/torch.h>
#include <chrono>
#include <thread>

// Test: PerformanceProfiler basic timing
TEST(PerformanceTest, ProfilerBasicTiming) {
    meshml::utils::PerformanceProfiler profiler;
    
    profiler.start("test_operation");
    std::this_thread::sleep_for(std::chrono::milliseconds(100));
    profiler.stop("test_operation");
    
    auto elapsed = profiler.get_elapsed("test_operation");
    EXPECT_GE(elapsed, 100.0);  // At least 100ms
    EXPECT_LT(elapsed, 150.0);  // Less than 150ms (with tolerance)
}

// Test: PerformanceProfiler multiple operations
TEST(PerformanceTest, ProfilerMultipleOperations) {
    meshml::utils::PerformanceProfiler profiler;
    
    profiler.start("op1");
    std::this_thread::sleep_for(std::chrono::milliseconds(50));
    profiler.stop("op1");
    
    profiler.start("op2");
    std::this_thread::sleep_for(std::chrono::milliseconds(30));
    profiler.stop("op2");
    
    EXPECT_GT(profiler.get_elapsed("op1"), profiler.get_elapsed("op2"));
}

// Test: PerformanceProfiler nested operations
TEST(PerformanceTest, ProfilerNestedOperations) {
    meshml::utils::PerformanceProfiler profiler;
    
    profiler.start("outer");
    profiler.start("inner");
    std::this_thread::sleep_for(std::chrono::milliseconds(50));
    profiler.stop("inner");
    profiler.stop("outer");
    
    EXPECT_GT(profiler.get_elapsed("outer"), profiler.get_elapsed("inner"));
}

// Test: PerformanceProfiler reset
TEST(PerformanceTest, ProfilerReset) {
    meshml::utils::PerformanceProfiler profiler;
    
    profiler.start("test");
    profiler.stop("test");
    
    EXPECT_GT(profiler.get_elapsed("test"), 0.0);
    
    profiler.reset();
    EXPECT_EQ(profiler.get_elapsed("test"), 0.0);
}

// Test: PerformanceProfiler report
TEST(PerformanceTest, ProfilerReport) {
    meshml::utils::PerformanceProfiler profiler;
    
    profiler.start("op1");
    std::this_thread::sleep_for(std::chrono::milliseconds(10));
    profiler.stop("op1");
    
    auto report = profiler.report();
    EXPECT_TRUE(report.find("op1") != std::string::npos);
}

// Test: SIMD vector addition
TEST(SIMDTest, VectorAddition) {
    const int size = 1024;
    std::vector<float> a(size, 1.0f);
    std::vector<float> b(size, 2.0f);
    std::vector<float> result(size);
    
    meshml::utils::simd::vector_add(a.data(), b.data(), result.data(), size);
    
    for (int i = 0; i < size; ++i) {
        EXPECT_FLOAT_EQ(result[i], 3.0f);
    }
}

// Test: SIMD vector multiplication
TEST(SIMDTest, VectorMultiplication) {
    const int size = 1024;
    std::vector<float> a(size, 2.0f);
    std::vector<float> b(size, 3.0f);
    std::vector<float> result(size);
    
    meshml::utils::simd::vector_mul(a.data(), b.data(), result.data(), size);
    
    for (int i = 0; i < size; ++i) {
        EXPECT_FLOAT_EQ(result[i], 6.0f);
    }
}

// Test: SIMD scalar multiplication
TEST(SIMDTest, ScalarMultiplication) {
    const int size = 1024;
    std::vector<float> a(size, 2.0f);
    std::vector<float> result(size);
    float scalar = 3.5f;
    
    meshml::utils::simd::scalar_mul(a.data(), scalar, result.data(), size);
    
    for (int i = 0; i < size; ++i) {
        EXPECT_FLOAT_EQ(result[i], 7.0f);
    }
}

// Test: SIMD dot product
TEST(SIMDTest, DotProduct) {
    const int size = 1024;
    std::vector<float> a(size, 2.0f);
    std::vector<float> b(size, 3.0f);
    
    float result = meshml::utils::simd::dot_product(a.data(), b.data(), size);
    
    EXPECT_FLOAT_EQ(result, 2.0f * 3.0f * size);
}

// Test: SIMD ReLU activation
TEST(SIMDTest, ReLUActivation) {
    const int size = 8;
    std::vector<float> input = {-2.0f, -1.0f, 0.0f, 1.0f, 2.0f, 3.0f, -0.5f, 0.5f};
    std::vector<float> result(size);
    
    meshml::utils::simd::relu(input.data(), result.data(), size);
    
    EXPECT_FLOAT_EQ(result[0], 0.0f);
    EXPECT_FLOAT_EQ(result[1], 0.0f);
    EXPECT_FLOAT_EQ(result[2], 0.0f);
    EXPECT_FLOAT_EQ(result[3], 1.0f);
    EXPECT_FLOAT_EQ(result[4], 2.0f);
    EXPECT_FLOAT_EQ(result[5], 3.0f);
    EXPECT_FLOAT_EQ(result[6], 0.0f);
    EXPECT_FLOAT_EQ(result[7], 0.5f);
}

// Test: SIMD sum reduction
TEST(SIMDTest, SumReduction) {
    const int size = 1024;
    std::vector<float> a(size, 1.0f);
    
    float result = meshml::utils::simd::sum(a.data(), size);
    
    EXPECT_FLOAT_EQ(result, static_cast<float>(size));
}

// Test: Memory pool allocation
TEST(MemoryPoolTest, BasicAllocation) {
    meshml::utils::MemoryPool pool(1024 * 1024);  // 1 MB pool
    
    void* ptr1 = pool.allocate(100);
    ASSERT_NE(ptr1, nullptr);
    
    void* ptr2 = pool.allocate(200);
    ASSERT_NE(ptr2, nullptr);
    EXPECT_NE(ptr1, ptr2);
}

// Test: Memory pool deallocation
TEST(MemoryPoolTest, Deallocation) {
    meshml::utils::MemoryPool pool(1024 * 1024);
    
    void* ptr = pool.allocate(100);
    ASSERT_NE(ptr, nullptr);
    
    pool.deallocate(ptr, 100);
    
    // Should be able to allocate again
    void* ptr2 = pool.allocate(100);
    EXPECT_NE(ptr2, nullptr);
}

// Test: Memory pool reuse
TEST(MemoryPoolTest, MemoryReuse) {
    meshml::utils::MemoryPool pool(1024);
    
    void* ptr1 = pool.allocate(100);
    pool.deallocate(ptr1, 100);
    
    void* ptr2 = pool.allocate(100);
    
    // Should reuse the same memory
    EXPECT_EQ(ptr1, ptr2);
}

// Test: Memory pool multiple sizes
TEST(MemoryPoolTest, MultipleSizes) {
    meshml::utils::MemoryPool pool(1024 * 1024);
    
    void* small = pool.allocate(64);
    void* medium = pool.allocate(256);
    void* large = pool.allocate(1024);
    
    ASSERT_NE(small, nullptr);
    ASSERT_NE(medium, nullptr);
    ASSERT_NE(large, nullptr);
}

// Test: Memory pool out of memory
TEST(MemoryPoolTest, OutOfMemory) {
    meshml::utils::MemoryPool pool(100);  // Small pool
    
    void* ptr = pool.allocate(200);  // Request more than available
    EXPECT_EQ(ptr, nullptr);  // Should return nullptr
}

// Test: Memory pool reset
TEST(MemoryPoolTest, Reset) {
    meshml::utils::MemoryPool pool(1024);
    
    void* ptr1 = pool.allocate(100);
    ASSERT_NE(ptr1, nullptr);
    
    pool.reset();
    
    // After reset, should be able to allocate full size again
    void* ptr2 = pool.allocate(1024);
    EXPECT_NE(ptr2, nullptr);
}

// Test: Memory pool statistics
TEST(MemoryPoolTest, Statistics) {
    meshml::utils::MemoryPool pool(1024);
    
    size_t initial_free = pool.get_free_memory();
    EXPECT_EQ(initial_free, 1024);
    
    void* ptr = pool.allocate(100);
    
    size_t after_alloc = pool.get_free_memory();
    EXPECT_LT(after_alloc, initial_free);
    
    pool.deallocate(ptr, 100);
    
    size_t after_dealloc = pool.get_free_memory();
    EXPECT_EQ(after_dealloc, initial_free);
}

// Test: Memory pool thread safety (basic)
TEST(MemoryPoolTest, ThreadSafety) {
    meshml::utils::MemoryPool pool(1024 * 1024);
    
    const int num_threads = 4;
    const int allocs_per_thread = 100;
    std::vector<std::thread> threads;
    
    for (int t = 0; t < num_threads; ++t) {
        threads.emplace_back([&pool, allocs_per_thread]() {
            for (int i = 0; i < allocs_per_thread; ++i) {
                void* ptr = pool.allocate(64);
                if (ptr != nullptr) {
                    std::this_thread::sleep_for(std::chrono::microseconds(1));
                    pool.deallocate(ptr, 64);
                }
            }
        });
    }
    
    for (auto& thread : threads) {
        thread.join();
    }
    
    // Should not crash
    SUCCEED();
}

// Performance test: SIMD vs scalar
TEST(PerformanceTest, DISABLED_SIMDvsScalar) {
    const int size = 1024 * 1024;
    std::vector<float> a(size, 2.0f);
    std::vector<float> b(size, 3.0f);
    std::vector<float> result(size);
    
    // SIMD version
    auto start = std::chrono::high_resolution_clock::now();
    meshml::utils::simd::vector_add(a.data(), b.data(), result.data(), size);
    auto end = std::chrono::high_resolution_clock::now();
    auto simd_time = std::chrono::duration_cast<std::chrono::microseconds>(end - start).count();
    
    // Scalar version
    start = std::chrono::high_resolution_clock::now();
    for (int i = 0; i < size; ++i) {
        result[i] = a[i] + b[i];
    }
    end = std::chrono::high_resolution_clock::now();
    auto scalar_time = std::chrono::duration_cast<std::chrono::microseconds>(end - start).count();
    
    std::cout << "SIMD time: " << simd_time << " μs\n";
    std::cout << "Scalar time: " << scalar_time << " μs\n";
    std::cout << "Speedup: " << static_cast<float>(scalar_time) / simd_time << "x\n";
    
    EXPECT_LT(simd_time, scalar_time);
}

// Performance test: Memory pool vs malloc
TEST(PerformanceTest, DISABLED_MemoryPoolVsMalloc) {
    const int iterations = 10000;
    const int alloc_size = 64;
    
    // Memory pool version
    meshml::utils::MemoryPool pool(alloc_size * iterations * 2);
    auto start = std::chrono::high_resolution_clock::now();
    for (int i = 0; i < iterations; ++i) {
        void* ptr = pool.allocate(alloc_size);
        pool.deallocate(ptr, alloc_size);
    }
    auto end = std::chrono::high_resolution_clock::now();
    auto pool_time = std::chrono::duration_cast<std::chrono::microseconds>(end - start).count();
    
    // Malloc version
    start = std::chrono::high_resolution_clock::now();
    for (int i = 0; i < iterations; ++i) {
        void* ptr = malloc(alloc_size);
        free(ptr);
    }
    end = std::chrono::high_resolution_clock::now();
    auto malloc_time = std::chrono::duration_cast<std::chrono::microseconds>(end - start).count();
    
    std::cout << "Memory pool time: " << pool_time << " μs\n";
    std::cout << "Malloc time: " << malloc_time << " μs\n";
    std::cout << "Speedup: " << static_cast<float>(malloc_time) / pool_time << "x\n";
    
    EXPECT_LT(pool_time, malloc_time);
}

// Test: Profiler overhead
TEST(PerformanceTest, ProfilerOverhead) {
    const int iterations = 1000;
    
    // Without profiler
    auto start = std::chrono::high_resolution_clock::now();
    for (int i = 0; i < iterations; ++i) {
        std::this_thread::sleep_for(std::chrono::microseconds(100));
    }
    auto end = std::chrono::high_resolution_clock::now();
    auto without_profiler = std::chrono::duration_cast<std::chrono::milliseconds>(end - start).count();
    
    // With profiler
    meshml::utils::PerformanceProfiler profiler;
    start = std::chrono::high_resolution_clock::now();
    for (int i = 0; i < iterations; ++i) {
        profiler.start("test");
        std::this_thread::sleep_for(std::chrono::microseconds(100));
        profiler.stop("test");
    }
    end = std::chrono::high_resolution_clock::now();
    auto with_profiler = std::chrono::duration_cast<std::chrono::milliseconds>(end - start).count();
    
    // Overhead should be minimal (< 10%)
    double overhead = (static_cast<double>(with_profiler) / without_profiler - 1.0) * 100.0;
    std::cout << "Profiler overhead: " << overhead << "%\n";
    
    EXPECT_LT(overhead, 10.0);
}
