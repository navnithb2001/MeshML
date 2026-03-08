/**
 * @file simd_ops.cpp
 * @brief SIMD operations implementation
 */

#include "meshml/utils/simd_ops.h"
#include <cmath>
#include <iostream>
#include <sstream>
#include <chrono>

// Include platform-specific headers
#ifdef __AVX2__
#include <immintrin.h>
#endif

#ifdef __ARM_NEON
#include <arm_neon.h>
#endif

namespace meshml {
namespace utils {
namespace simd {

// Capability detection

bool is_avx_available() {
#ifdef __AVX__
    return true;
#else
    return false;
#endif
}

bool is_avx2_available() {
#ifdef __AVX2__
    return true;
#else
    return false;
#endif
}

bool is_neon_available() {
#ifdef __ARM_NEON
    return true;
#else
    return false;
#endif
}

std::string get_simd_capabilities() {
    std::ostringstream oss;
    oss << "SIMD Capabilities: ";
    
    if (is_avx2_available()) {
        oss << "AVX2 ";
    } else if (is_avx_available()) {
        oss << "AVX ";
    }
    
    if (is_neon_available()) {
        oss << "NEON ";
    }
    
    if (!is_avx_available() && !is_neon_available()) {
        oss << "Scalar only";
    }
    
    return oss.str();
}

// ============================================================================
// Scalar Implementations (Fallback)
// ============================================================================

namespace internal {

void vector_add_scalar(const float* a, const float* b, float* result, size_t size) {
    for (size_t i = 0; i < size; ++i) {
        result[i] = a[i] + b[i];
    }
}

void vector_mul_scalar(const float* a, const float* b, float* result, size_t size) {
    for (size_t i = 0; i < size; ++i) {
        result[i] = a[i] * b[i];
    }
}

float vector_dot_scalar(const float* a, const float* b, size_t size) {
    float sum = 0.0f;
    for (size_t i = 0; i < size; ++i) {
        sum += a[i] * b[i];
    }
    return sum;
}

// ============================================================================
// AVX2 Implementations
// ============================================================================

#ifdef __AVX2__

void vector_add_avx2(const float* a, const float* b, float* result, size_t size) {
    size_t i = 0;
    
    // Process 8 floats at a time with AVX2
    for (; i + 7 < size; i += 8) {
        __m256 va = _mm256_loadu_ps(&a[i]);
        __m256 vb = _mm256_loadu_ps(&b[i]);
        __m256 vr = _mm256_add_ps(va, vb);
        _mm256_storeu_ps(&result[i], vr);
    }
    
    // Handle remainder with scalar code
    for (; i < size; ++i) {
        result[i] = a[i] + b[i];
    }
}

void vector_mul_avx2(const float* a, const float* b, float* result, size_t size) {
    size_t i = 0;
    
    // Process 8 floats at a time
    for (; i + 7 < size; i += 8) {
        __m256 va = _mm256_loadu_ps(&a[i]);
        __m256 vb = _mm256_loadu_ps(&b[i]);
        __m256 vr = _mm256_mul_ps(va, vb);
        _mm256_storeu_ps(&result[i], vr);
    }
    
    // Handle remainder
    for (; i < size; ++i) {
        result[i] = a[i] * b[i];
    }
}

float vector_dot_avx2(const float* a, const float* b, size_t size) {
    __m256 sum_vec = _mm256_setzero_ps();
    size_t i = 0;
    
    // Process 8 floats at a time
    for (; i + 7 < size; i += 8) {
        __m256 va = _mm256_loadu_ps(&a[i]);
        __m256 vb = _mm256_loadu_ps(&b[i]);
        __m256 prod = _mm256_mul_ps(va, vb);
        sum_vec = _mm256_add_ps(sum_vec, prod);
    }
    
    // Horizontal sum of sum_vec
    float sum_array[8];
    _mm256_storeu_ps(sum_array, sum_vec);
    float sum = sum_array[0] + sum_array[1] + sum_array[2] + sum_array[3] +
                sum_array[4] + sum_array[5] + sum_array[6] + sum_array[7];
    
    // Handle remainder
    for (; i < size; ++i) {
        sum += a[i] * b[i];
    }
    
    return sum;
}

#endif // __AVX2__

// ============================================================================
// NEON Implementations
// ============================================================================

#ifdef __ARM_NEON

void vector_add_neon(const float* a, const float* b, float* result, size_t size) {
    size_t i = 0;
    
    // Process 4 floats at a time with NEON
    for (; i + 3 < size; i += 4) {
        float32x4_t va = vld1q_f32(&a[i]);
        float32x4_t vb = vld1q_f32(&b[i]);
        float32x4_t vr = vaddq_f32(va, vb);
        vst1q_f32(&result[i], vr);
    }
    
    // Handle remainder
    for (; i < size; ++i) {
        result[i] = a[i] + b[i];
    }
}

void vector_mul_neon(const float* a, const float* b, float* result, size_t size) {
    size_t i = 0;
    
    // Process 4 floats at a time
    for (; i + 3 < size; i += 4) {
        float32x4_t va = vld1q_f32(&a[i]);
        float32x4_t vb = vld1q_f32(&b[i]);
        float32x4_t vr = vmulq_f32(va, vb);
        vst1q_f32(&result[i], vr);
    }
    
    // Handle remainder
    for (; i < size; ++i) {
        result[i] = a[i] * b[i];
    }
}

float vector_dot_neon(const float* a, const float* b, size_t size) {
    float32x4_t sum_vec = vdupq_n_f32(0.0f);
    size_t i = 0;
    
    // Process 4 floats at a time
    for (; i + 3 < size; i += 4) {
        float32x4_t va = vld1q_f32(&a[i]);
        float32x4_t vb = vld1q_f32(&b[i]);
        sum_vec = vmlaq_f32(sum_vec, va, vb);  // Multiply-accumulate
    }
    
    // Horizontal sum
    float sum_array[4];
    vst1q_f32(sum_array, sum_vec);
    float sum = sum_array[0] + sum_array[1] + sum_array[2] + sum_array[3];
    
    // Handle remainder
    for (; i < size; ++i) {
        sum += a[i] * b[i];
    }
    
    return sum;
}

#endif // __ARM_NEON

} // namespace internal

// ============================================================================
// Public API with automatic dispatch
// ============================================================================

void vector_add(const float* a, const float* b, float* result, size_t size) {
#ifdef __AVX2__
    internal::vector_add_avx2(a, b, result, size);
#elif defined(__ARM_NEON)
    internal::vector_add_neon(a, b, result, size);
#else
    internal::vector_add_scalar(a, b, result, size);
#endif
}

void vector_sub(const float* a, const float* b, float* result, size_t size) {
    // No SIMD-specific implementation yet, use scalar
    for (size_t i = 0; i < size; ++i) {
        result[i] = a[i] - b[i];
    }
}

void vector_mul(const float* a, const float* b, float* result, size_t size) {
#ifdef __AVX2__
    internal::vector_mul_avx2(a, b, result, size);
#elif defined(__ARM_NEON)
    internal::vector_mul_neon(a, b, result, size);
#else
    internal::vector_mul_scalar(a, b, result, size);
#endif
}

float vector_dot(const float* a, const float* b, size_t size) {
#ifdef __AVX2__
    return internal::vector_dot_avx2(a, b, size);
#elif defined(__ARM_NEON)
    return internal::vector_dot_neon(a, b, size);
#else
    return internal::vector_dot_scalar(a, b, size);
#endif
}

void vector_scale(const float* a, float scalar, float* result, size_t size) {
    // TODO: Add SIMD implementation
    for (size_t i = 0; i < size; ++i) {
        result[i] = a[i] * scalar;
    }
}

float vector_norm(const float* a, size_t size) {
    float dot = vector_dot(a, a, size);
    return std::sqrt(dot);
}

float vector_sum(const float* a, size_t size) {
    // TODO: Add SIMD implementation
    float sum = 0.0f;
    for (size_t i = 0; i < size; ++i) {
        sum += a[i];
    }
    return sum;
}

void vector_relu(const float* a, float* result, size_t size) {
    // TODO: Add SIMD implementation
    for (size_t i = 0; i < size; ++i) {
        result[i] = std::max(0.0f, a[i]);
    }
}

void matrix_vector_mul(
    const float* matrix,
    const float* vector,
    float* result,
    size_t rows,
    size_t cols
) {
    // Simple implementation - could be optimized with SIMD
    for (size_t i = 0; i < rows; ++i) {
        result[i] = vector_dot(&matrix[i * cols], vector, cols);
    }
}

void gradient_clip(float* gradients, size_t size, float threshold) {
    // TODO: Add SIMD implementation
    for (size_t i = 0; i < size; ++i) {
        if (gradients[i] > threshold) {
            gradients[i] = threshold;
        } else if (gradients[i] < -threshold) {
            gradients[i] = -threshold;
        }
    }
}

void vector_softmax(const float* a, float* result, size_t size) {
    // Find max for numerical stability
    float max_val = a[0];
    for (size_t i = 1; i < size; ++i) {
        max_val = std::max(max_val, a[i]);
    }
    
    // Compute exp(a[i] - max)
    float sum = 0.0f;
    for (size_t i = 0; i < size; ++i) {
        result[i] = std::exp(a[i] - max_val);
        sum += result[i];
    }
    
    // Normalize
    for (size_t i = 0; i < size; ++i) {
        result[i] /= sum;
    }
}

void benchmark_simd_operations() {
    std::cout << "\n=== SIMD Operations Benchmark ===" << std::endl;
    std::cout << get_simd_capabilities() << std::endl;
    
    const size_t size = 1000000;  // 1M elements
    const int iterations = 100;
    
    std::vector<float> a(size);
    std::vector<float> b(size);
    std::vector<float> result(size);
    
    // Initialize with random values
    for (size_t i = 0; i < size; ++i) {
        a[i] = static_cast<float>(i) / size;
        b[i] = static_cast<float>(size - i) / size;
    }
    
    // Benchmark vector addition
    auto start = std::chrono::high_resolution_clock::now();
    for (int i = 0; i < iterations; ++i) {
        vector_add(a.data(), b.data(), result.data(), size);
    }
    auto end = std::chrono::high_resolution_clock::now();
    auto duration = std::chrono::duration_cast<std::chrono::microseconds>(end - start);
    double time_per_op = duration.count() / (1000.0 * iterations);
    
    std::cout << "\nVector Add (" << size << " elements):" << std::endl;
    std::cout << "  Time: " << time_per_op << " ms/operation" << std::endl;
    std::cout << "  Throughput: " << (size * iterations / (duration.count() / 1e6) / 1e9) 
              << " GFLOP/s" << std::endl;
    
    // Benchmark dot product
    start = std::chrono::high_resolution_clock::now();
    volatile float dot_result = 0.0f;  // Prevent optimization
    for (int i = 0; i < iterations; ++i) {
        dot_result = vector_dot(a.data(), b.data(), size);
    }
    end = std::chrono::high_resolution_clock::now();
    duration = std::chrono::duration_cast<std::chrono::microseconds>(end - start);
    time_per_op = duration.count() / (1000.0 * iterations);
    
    std::cout << "\nVector Dot Product (" << size << " elements):" << std::endl;
    std::cout << "  Time: " << time_per_op << " ms/operation" << std::endl;
    std::cout << "  Result: " << dot_result << " (sanity check)" << std::endl;
}

// ============================================================================
// Convenience aliases (short names)
// ============================================================================

void scalar_mul(const float* a, float scalar, float* result, size_t size) {
    for (size_t i = 0; i < size; ++i) {
        result[i] = a[i] * scalar;
    }
}

void relu(const float* a, float* result, size_t size) {
    vector_relu(a, result, size);
}

float sum(const float* a, size_t size) {
    return vector_sum(a, size);
}

} // namespace simd
} // namespace utils
} // namespace meshml
