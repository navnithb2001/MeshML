/**
 * @file simd_ops.h
 * @brief SIMD-optimized operations for vector computations
 * 
 * Features:
 * - AVX/AVX2 optimizations for x86_64
 * - NEON optimizations for ARM/Apple Silicon
 * - Automatic fallback to scalar operations
 * - Vector operations (dot product, add, multiply, etc.)
 */

#pragma once

#include <vector>
#include <cstddef>
#include <string>

namespace meshml {
namespace utils {
namespace simd {

/**
 * @brief Check if AVX is available
 */
bool is_avx_available();

/**
 * @brief Check if AVX2 is available
 */
bool is_avx2_available();

/**
 * @brief Check if NEON is available (ARM)
 */
bool is_neon_available();

/**
 * @brief SIMD-optimized vector addition
 * 
 * result[i] = a[i] + b[i]
 * 
 * @param a First vector
 * @param b Second vector
 * @param result Output vector
 * @param size Vector size
 */
void vector_add(
    const float* a,
    const float* b,
    float* result,
    size_t size
);

/**
 * @brief SIMD-optimized vector subtraction
 * 
 * result[i] = a[i] - b[i]
 */
void vector_sub(
    const float* a,
    const float* b,
    float* result,
    size_t size
);

/**
 * @brief SIMD-optimized vector multiplication
 * 
 * result[i] = a[i] * b[i]
 */
void vector_mul(
    const float* a,
    const float* b,
    float* result,
    size_t size
);

/**
 * @brief SIMD-optimized dot product
 * 
 * result = sum(a[i] * b[i])
 */
float vector_dot(
    const float* a,
    const float* b,
    size_t size
);

/**
 * @brief SIMD-optimized scalar multiplication
 * 
 * result[i] = a[i] * scalar
 */
void vector_scale(
    const float* a,
    float scalar,
    float* result,
    size_t size
);

/**
 * @brief SIMD-optimized vector norm (L2)
 * 
 * result = sqrt(sum(a[i]^2))
 */
float vector_norm(
    const float* a,
    size_t size
);

/**
 * @brief SIMD-optimized vector sum
 * 
 * result = sum(a[i])
 */
float vector_sum(
    const float* a,
    size_t size
);

/**
 * @brief SIMD-optimized ReLU activation
 * 
 * result[i] = max(0, a[i])
 */
void vector_relu(
    const float* a,
    float* result,
    size_t size
);

/**
 * @brief SIMD-optimized matrix-vector multiplication
 * 
 * result = matrix * vector
 * 
 * @param matrix Matrix in row-major order (rows x cols)
 * @param vector Input vector (cols)
 * @param result Output vector (rows)
 * @param rows Number of rows
 * @param cols Number of columns
 */
void matrix_vector_mul(
    const float* matrix,
    const float* vector,
    float* result,
    size_t rows,
    size_t cols
);

/**
 * @brief SIMD-optimized gradient clipping
 * 
 * Clips gradients to [-threshold, threshold]
 */
void gradient_clip(
    float* gradients,
    size_t size,
    float threshold
);

/**
 * @brief SIMD-optimized softmax
 * 
 * result[i] = exp(a[i]) / sum(exp(a[j]))
 */
void vector_softmax(
    const float* a,
    float* result,
    size_t size
);

/**
 * @brief Benchmark SIMD operations
 * 
 * Compares SIMD vs scalar performance
 */
void benchmark_simd_operations();

/**
 * @brief Get SIMD capabilities string
 * 
 * @return String describing available SIMD instructions
 */
std::string get_simd_capabilities();

// ============================================================================
// Convenience aliases (short names for tests)
// ============================================================================

/**
 * @brief Scalar multiplication (convenience alias)
 * result[i] = a[i] * scalar
 */
void scalar_mul(const float* a, float scalar, float* result, size_t size);

/**
 * @brief ReLU activation (convenience alias)
 * result[i] = max(0, a[i])
 */
void relu(const float* a, float* result, size_t size);

/**
 * @brief Sum reduction (convenience alias)
 * result = sum(a[i])
 */
float sum(const float* a, size_t size);

// ============================================================================
// Implementation Selection (Internal)
// ============================================================================

namespace internal {

// Scalar fallback implementations
void vector_add_scalar(const float* a, const float* b, float* result, size_t size);
void vector_mul_scalar(const float* a, const float* b, float* result, size_t size);
float vector_dot_scalar(const float* a, const float* b, size_t size);

#ifdef __AVX2__
// AVX2 implementations
void vector_add_avx2(const float* a, const float* b, float* result, size_t size);
void vector_mul_avx2(const float* a, const float* b, float* result, size_t size);
float vector_dot_avx2(const float* a, const float* b, size_t size);
#endif

#ifdef __ARM_NEON
// NEON implementations
void vector_add_neon(const float* a, const float* b, float* result, size_t size);
void vector_mul_neon(const float* a, const float* b, float* result, size_t size);
float vector_dot_neon(const float* a, const float* b, size_t size);
#endif

} // namespace internal

} // namespace simd
} // namespace utils
} // namespace meshml
