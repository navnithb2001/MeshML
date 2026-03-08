#pragma once

#ifdef USE_CUDA

#include <cuda_runtime.h>
#include <torch/torch.h>
#include <vector>
#include <string>

namespace meshml {
namespace cuda {

/**
 * @brief CUDA kernel error checking utility
 */
#define CUDA_CHECK(call) \
    do { \
        cudaError_t error = call; \
        if (error != cudaSuccess) { \
            throw std::runtime_error(std::string("CUDA error: ") + \
                                   cudaGetErrorString(error) + \
                                   " at " + __FILE__ + ":" + std::to_string(__LINE__)); \
        } \
    } while(0)

/**
 * @brief Custom CUDA kernels for optimized operations
 */
class CudaKernels {
public:
    /**
     * @brief Fused element-wise operations: out = alpha * a + beta * b
     * @param a First input tensor
     * @param b Second input tensor
     * @param alpha Scale for first tensor
     * @param beta Scale for second tensor
     * @return Output tensor
     * 
     * Faster than separate mul + add operations
     */
    static torch::Tensor fused_linear_combination(
        const torch::Tensor& a,
        const torch::Tensor& b,
        float alpha,
        float beta
    );
    
    /**
     * @brief Fused ReLU and gradient clipping
     * @param input Input tensor
     * @param clip_value Maximum absolute value
     * @return Clipped and ReLU activated tensor
     */
    static torch::Tensor fused_relu_clip(
        const torch::Tensor& input,
        float clip_value
    );
    
    /**
     * @brief Optimized gradient accumulation with momentum
     * @param gradients Current gradients
     * @param momentum_buffer Momentum buffer (modified in-place)
     * @param momentum Momentum coefficient
     * @return Accumulated gradients
     */
    static torch::Tensor gradient_accumulation_momentum(
        const torch::Tensor& gradients,
        torch::Tensor& momentum_buffer,
        float momentum
    );
    
    /**
     * @brief Fast L2 norm computation for gradient clipping
     * @param tensor Input tensor
     * @return L2 norm value
     */
    static float fast_l2_norm(const torch::Tensor& tensor);
    
    /**
     * @brief Batch normalization inference (optimized)
     * @param input Input tensor [N, C, H, W]
     * @param mean Running mean [C]
     * @param var Running variance [C]
     * @param weight Gamma [C]
     * @param bias Beta [C]
     * @param eps Epsilon for numerical stability
     * @return Normalized output
     */
    static torch::Tensor batch_norm_inference(
        const torch::Tensor& input,
        const torch::Tensor& mean,
        const torch::Tensor& var,
        const torch::Tensor& weight,
        const torch::Tensor& bias,
        float eps = 1e-5
    );
    
    /**
     * @brief Optimized softmax with temperature scaling
     * @param logits Input logits
     * @param temperature Temperature parameter
     * @param dim Dimension to apply softmax
     * @return Softmax probabilities
     */
    static torch::Tensor softmax_with_temperature(
        const torch::Tensor& logits,
        float temperature,
        int64_t dim = -1
    );
    
    /**
     * @brief Cross-entropy loss with label smoothing (fused kernel)
     * @param logits Input logits [N, C]
     * @param targets Target labels [N]
     * @param smoothing Label smoothing factor
     * @return Loss value
     */
    static torch::Tensor cross_entropy_label_smoothing(
        const torch::Tensor& logits,
        const torch::Tensor& targets,
        float smoothing = 0.1
    );
    
    /**
     * @brief Gradient clipping by global norm (optimized)
     * @param gradients Vector of gradient tensors
     * @param max_norm Maximum norm
     * @return Clipped gradients
     */
    static std::vector<torch::Tensor> clip_gradients_by_norm(
        const std::vector<torch::Tensor>& gradients,
        float max_norm
    );
    
    /**
     * @brief Fused Adam optimizer step
     * @param param Parameter tensor (modified in-place)
     * @param grad Gradient tensor
     * @param exp_avg First moment estimate (modified in-place)
     * @param exp_avg_sq Second moment estimate (modified in-place)
     * @param step Step number
     * @param lr Learning rate
     * @param beta1 Beta1 parameter
     * @param beta2 Beta2 parameter
     * @param eps Epsilon for numerical stability
     * @param weight_decay Weight decay coefficient
     */
    static void fused_adam_step(
        torch::Tensor& param,
        const torch::Tensor& grad,
        torch::Tensor& exp_avg,
        torch::Tensor& exp_avg_sq,
        int64_t step,
        float lr,
        float beta1 = 0.9,
        float beta2 = 0.999,
        float eps = 1e-8,
        float weight_decay = 0.0
    );
    
    /**
     * @brief Mixed precision gradient scaling
     * @param gradients Gradients in FP16
     * @param scale Scale factor
     * @return Scaled gradients in FP32
     */
    static torch::Tensor gradient_unscaling(
        const torch::Tensor& gradients,
        float scale
    );
    
    /**
     * @brief Check if CUDA is available and get device info
     * @return Device information string
     */
    static std::string get_device_info();
    
    /**
     * @brief Get optimal block size for kernel launch
     * @param n Problem size
     * @return Optimal block size
     */
    static int get_optimal_block_size(int64_t n);
    
    /**
     * @brief Warmup CUDA kernels (reduces first-run overhead)
     */
    static void warmup_kernels();
};

/**
 * @brief CUDA memory utilities
 */
class CudaMemoryManager {
public:
    /**
     * @brief Allocate pinned memory for faster CPU-GPU transfers
     * @param size Size in bytes
     * @return Pointer to pinned memory
     */
    static void* allocate_pinned(size_t size);
    
    /**
     * @brief Free pinned memory
     * @param ptr Pointer to free
     */
    static void free_pinned(void* ptr);
    
    /**
     * @brief Get current GPU memory usage
     * @param device_id Device ID
     * @return Memory usage in bytes
     */
    static size_t get_memory_usage(int device_id = 0);
    
    /**
     * @brief Get available GPU memory
     * @param device_id Device ID
     * @return Available memory in bytes
     */
    static size_t get_available_memory(int device_id = 0);
    
    /**
     * @brief Clear CUDA cache
     */
    static void clear_cache();
};

/**
 * @brief CUDA stream manager for concurrent kernel execution
 */
class CudaStreamManager {
public:
    CudaStreamManager(int num_streams = 4);
    ~CudaStreamManager();
    
    /**
     * @brief Get a stream for concurrent execution
     * @param index Stream index
     * @return CUDA stream
     */
    cudaStream_t get_stream(int index);
    
    /**
     * @brief Synchronize all streams
     */
    void synchronize_all();
    
    /**
     * @brief Get number of streams
     */
    int num_streams() const { return num_streams_; }

private:
    std::vector<cudaStream_t> streams_;
    int num_streams_;
};

} // namespace cuda
} // namespace meshml

#endif // USE_CUDA
