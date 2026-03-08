#ifdef USE_CUDA

#include "meshml/cuda/cuda_kernels.h"
#include <cuda_runtime.h>
#include <device_launch_parameters.h>
#include <cmath>
#include <algorithm>

namespace meshml {
namespace cuda {

// Kernel implementations

/**
 * @brief Fused linear combination kernel: out = alpha * a + beta * b
 */
__global__ void fused_linear_combination_kernel(
    const float* a,
    const float* b,
    float* out,
    float alpha,
    float beta,
    int64_t n
) {
    int64_t idx = blockIdx.x * blockDim.x + threadIdx.x;
    if (idx < n) {
        out[idx] = alpha * a[idx] + beta * b[idx];
    }
}

/**
 * @brief Fused ReLU and clipping kernel
 */
__global__ void fused_relu_clip_kernel(
    const float* input,
    float* output,
    float clip_value,
    int64_t n
) {
    int64_t idx = blockIdx.x * blockDim.x + threadIdx.x;
    if (idx < n) {
        float val = fmaxf(0.0f, input[idx]);  // ReLU
        output[idx] = fminf(fmaxf(val, -clip_value), clip_value);  // Clip
    }
}

/**
 * @brief Gradient accumulation with momentum kernel
 */
__global__ void gradient_momentum_kernel(
    const float* gradients,
    float* momentum_buffer,
    float* output,
    float momentum,
    int64_t n
) {
    int64_t idx = blockIdx.x * blockDim.x + threadIdx.x;
    if (idx < n) {
        momentum_buffer[idx] = momentum * momentum_buffer[idx] + gradients[idx];
        output[idx] = momentum_buffer[idx];
    }
}

/**
 * @brief L2 norm squared reduction kernel (first pass)
 */
__global__ void l2_norm_squared_kernel(
    const float* input,
    float* partial_sums,
    int64_t n
) {
    extern __shared__ float shared_data[];
    
    int64_t idx = blockIdx.x * blockDim.x + threadIdx.x;
    int tid = threadIdx.x;
    
    // Load and square
    float sum = 0.0f;
    if (idx < n) {
        float val = input[idx];
        sum = val * val;
    }
    shared_data[tid] = sum;
    __syncthreads();
    
    // Reduction in shared memory
    for (unsigned int s = blockDim.x / 2; s > 0; s >>= 1) {
        if (tid < s) {
            shared_data[tid] += shared_data[tid + s];
        }
        __syncthreads();
    }
    
    // Write result for this block
    if (tid == 0) {
        partial_sums[blockIdx.x] = shared_data[0];
    }
}

/**
 * @brief Batch normalization inference kernel
 */
__global__ void batch_norm_inference_kernel(
    const float* input,
    const float* mean,
    const float* var,
    const float* weight,
    const float* bias,
    float* output,
    float eps,
    int64_t n,
    int64_t c,
    int64_t spatial_size
) {
    int64_t idx = blockIdx.x * blockDim.x + threadIdx.x;
    if (idx < n * c * spatial_size) {
        int64_t channel = (idx / spatial_size) % c;
        
        float normalized = (input[idx] - mean[channel]) / sqrtf(var[channel] + eps);
        output[idx] = weight[channel] * normalized + bias[channel];
    }
}

/**
 * @brief Softmax with temperature kernel
 */
__global__ void softmax_temperature_kernel(
    const float* logits,
    float* output,
    float temperature,
    int64_t batch_size,
    int64_t num_classes
) {
    int64_t batch_idx = blockIdx.x;
    int tid = threadIdx.x;
    
    if (batch_idx < batch_size) {
        extern __shared__ float shared_mem[];
        float* max_val = shared_mem;
        float* sum_exp = shared_mem + 1;
        
        const float* batch_logits = logits + batch_idx * num_classes;
        float* batch_output = output + batch_idx * num_classes;
        
        // Find max (for numerical stability)
        float local_max = -INFINITY;
        for (int i = tid; i < num_classes; i += blockDim.x) {
            local_max = fmaxf(local_max, batch_logits[i] / temperature);
        }
        
        // Reduce to get global max
        atomicMax((int*)max_val, __float_as_int(local_max));
        __syncthreads();
        
        // Compute exp and sum
        float local_sum = 0.0f;
        for (int i = tid; i < num_classes; i += blockDim.x) {
            float exp_val = expf((batch_logits[i] / temperature) - *max_val);
            batch_output[i] = exp_val;
            local_sum += exp_val;
        }
        
        // Reduce to get total sum
        atomicAdd(sum_exp, local_sum);
        __syncthreads();
        
        // Normalize
        for (int i = tid; i < num_classes; i += blockDim.x) {
            batch_output[i] /= *sum_exp;
        }
    }
}

/**
 * @brief Fused Adam optimizer step kernel
 */
__global__ void fused_adam_kernel(
    float* param,
    const float* grad,
    float* exp_avg,
    float* exp_avg_sq,
    int64_t step,
    float lr,
    float beta1,
    float beta2,
    float eps,
    float weight_decay,
    int64_t n
) {
    int64_t idx = blockIdx.x * blockDim.x + threadIdx.x;
    if (idx < n) {
        float g = grad[idx];
        
        // Weight decay
        if (weight_decay != 0.0f) {
            g += weight_decay * param[idx];
        }
        
        // Update biased first moment estimate
        exp_avg[idx] = beta1 * exp_avg[idx] + (1.0f - beta1) * g;
        
        // Update biased second raw moment estimate
        exp_avg_sq[idx] = beta2 * exp_avg_sq[idx] + (1.0f - beta2) * g * g;
        
        // Bias correction
        float bias_correction1 = 1.0f - powf(beta1, (float)step);
        float bias_correction2 = 1.0f - powf(beta2, (float)step);
        
        float corrected_exp_avg = exp_avg[idx] / bias_correction1;
        float corrected_exp_avg_sq = exp_avg_sq[idx] / bias_correction2;
        
        // Update parameters
        param[idx] -= lr * corrected_exp_avg / (sqrtf(corrected_exp_avg_sq) + eps);
    }
}

/**
 * @brief Gradient unscaling kernel (for mixed precision)
 */
__global__ void gradient_unscaling_kernel(
    const __half* grad_fp16,
    float* grad_fp32,
    float scale,
    int64_t n
) {
    int64_t idx = blockIdx.x * blockDim.x + threadIdx.x;
    if (idx < n) {
        grad_fp32[idx] = __half2float(grad_fp16[idx]) / scale;
    }
}

// CudaKernels implementation

torch::Tensor CudaKernels::fused_linear_combination(
    const torch::Tensor& a,
    const torch::Tensor& b,
    float alpha,
    float beta
) {
    TORCH_CHECK(a.is_cuda(), "Tensor a must be on CUDA");
    TORCH_CHECK(b.is_cuda(), "Tensor b must be on CUDA");
    TORCH_CHECK(a.sizes() == b.sizes(), "Tensors must have same size");
    
    auto output = torch::empty_like(a);
    int64_t n = a.numel();
    
    int block_size = get_optimal_block_size(n);
    int num_blocks = (n + block_size - 1) / block_size;
    
    fused_linear_combination_kernel<<<num_blocks, block_size>>>(
        a.data_ptr<float>(),
        b.data_ptr<float>(),
        output.data_ptr<float>(),
        alpha,
        beta,
        n
    );
    
    CUDA_CHECK(cudaGetLastError());
    return output;
}

torch::Tensor CudaKernels::fused_relu_clip(
    const torch::Tensor& input,
    float clip_value
) {
    TORCH_CHECK(input.is_cuda(), "Input must be on CUDA");
    
    auto output = torch::empty_like(input);
    int64_t n = input.numel();
    
    int block_size = get_optimal_block_size(n);
    int num_blocks = (n + block_size - 1) / block_size;
    
    fused_relu_clip_kernel<<<num_blocks, block_size>>>(
        input.data_ptr<float>(),
        output.data_ptr<float>(),
        clip_value,
        n
    );
    
    CUDA_CHECK(cudaGetLastError());
    return output;
}

torch::Tensor CudaKernels::gradient_accumulation_momentum(
    const torch::Tensor& gradients,
    torch::Tensor& momentum_buffer,
    float momentum
) {
    TORCH_CHECK(gradients.is_cuda(), "Gradients must be on CUDA");
    TORCH_CHECK(momentum_buffer.is_cuda(), "Momentum buffer must be on CUDA");
    
    auto output = torch::empty_like(gradients);
    int64_t n = gradients.numel();
    
    int block_size = get_optimal_block_size(n);
    int num_blocks = (n + block_size - 1) / block_size;
    
    gradient_momentum_kernel<<<num_blocks, block_size>>>(
        gradients.data_ptr<float>(),
        momentum_buffer.data_ptr<float>(),
        output.data_ptr<float>(),
        momentum,
        n
    );
    
    CUDA_CHECK(cudaGetLastError());
    return output;
}

float CudaKernels::fast_l2_norm(const torch::Tensor& tensor) {
    TORCH_CHECK(tensor.is_cuda(), "Tensor must be on CUDA");
    
    int64_t n = tensor.numel();
    int block_size = 256;
    int num_blocks = std::min((n + block_size - 1) / block_size, (int64_t)1024);
    
    // Allocate temporary buffer for partial sums
    auto partial_sums = torch::zeros({num_blocks}, tensor.options());
    
    size_t shared_mem_size = block_size * sizeof(float);
    l2_norm_squared_kernel<<<num_blocks, block_size, shared_mem_size>>>(
        tensor.data_ptr<float>(),
        partial_sums.data_ptr<float>(),
        n
    );
    
    CUDA_CHECK(cudaGetLastError());
    
    // Sum partial results on CPU (small array)
    auto partial_sums_cpu = partial_sums.cpu();
    float sum = partial_sums_cpu.sum().item<float>();
    
    return std::sqrt(sum);
}

torch::Tensor CudaKernels::batch_norm_inference(
    const torch::Tensor& input,
    const torch::Tensor& mean,
    const torch::Tensor& var,
    const torch::Tensor& weight,
    const torch::Tensor& bias,
    float eps
) {
    TORCH_CHECK(input.is_cuda(), "Input must be on CUDA");
    TORCH_CHECK(input.dim() == 4, "Input must be 4D [N, C, H, W]");
    
    int64_t n = input.size(0);
    int64_t c = input.size(1);
    int64_t spatial_size = input.size(2) * input.size(3);
    int64_t total_size = n * c * spatial_size;
    
    auto output = torch::empty_like(input);
    
    int block_size = get_optimal_block_size(total_size);
    int num_blocks = (total_size + block_size - 1) / block_size;
    
    batch_norm_inference_kernel<<<num_blocks, block_size>>>(
        input.data_ptr<float>(),
        mean.data_ptr<float>(),
        var.data_ptr<float>(),
        weight.data_ptr<float>(),
        bias.data_ptr<float>(),
        output.data_ptr<float>(),
        eps,
        n, c, spatial_size
    );
    
    CUDA_CHECK(cudaGetLastError());
    return output;
}

void CudaKernels::fused_adam_step(
    torch::Tensor& param,
    const torch::Tensor& grad,
    torch::Tensor& exp_avg,
    torch::Tensor& exp_avg_sq,
    int64_t step,
    float lr,
    float beta1,
    float beta2,
    float eps,
    float weight_decay
) {
    TORCH_CHECK(param.is_cuda(), "Parameters must be on CUDA");
    
    int64_t n = param.numel();
    int block_size = get_optimal_block_size(n);
    int num_blocks = (n + block_size - 1) / block_size;
    
    fused_adam_kernel<<<num_blocks, block_size>>>(
        param.data_ptr<float>(),
        grad.data_ptr<float>(),
        exp_avg.data_ptr<float>(),
        exp_avg_sq.data_ptr<float>(),
        step,
        lr,
        beta1,
        beta2,
        eps,
        weight_decay,
        n
    );
    
    CUDA_CHECK(cudaGetLastError());
}

std::string CudaKernels::get_device_info() {
    int device_count;
    CUDA_CHECK(cudaGetDeviceCount(&device_count));
    
    if (device_count == 0) {
        return "No CUDA devices found";
    }
    
    cudaDeviceProp prop;
    CUDA_CHECK(cudaGetDeviceProperties(&prop, 0));
    
    std::ostringstream info;
    info << "CUDA Device: " << prop.name << "\n";
    info << "Compute Capability: " << prop.major << "." << prop.minor << "\n";
    info << "Total Memory: " << (prop.totalGlobalMem / (1024 * 1024)) << " MB\n";
    info << "Multiprocessors: " << prop.multiProcessorCount << "\n";
    info << "Max Threads per Block: " << prop.maxThreadsPerBlock;
    
    return info.str();
}

int CudaKernels::get_optimal_block_size(int64_t n) {
    // Common block sizes: 128, 256, 512, 1024
    // Choose based on problem size
    if (n < 1024) return 128;
    if (n < 10000) return 256;
    if (n < 100000) return 512;
    return 1024;
}

void CudaKernels::warmup_kernels() {
    // Create small dummy tensors and run kernels
    auto a = torch::randn({1000}, torch::device(torch::kCUDA));
    auto b = torch::randn({1000}, torch::device(torch::kCUDA));
    
    // Warmup various kernels
    fused_linear_combination(a, b, 1.0f, 1.0f);
    fused_relu_clip(a, 1.0f);
    fast_l2_norm(a);
    
    CUDA_CHECK(cudaDeviceSynchronize());
}

// CudaMemoryManager implementation

void* CudaMemoryManager::allocate_pinned(size_t size) {
    void* ptr;
    CUDA_CHECK(cudaMallocHost(&ptr, size));
    return ptr;
}

void CudaMemoryManager::free_pinned(void* ptr) {
    CUDA_CHECK(cudaFreeHost(ptr));
}

size_t CudaMemoryManager::get_memory_usage(int device_id) {
    size_t free_mem, total_mem;
    CUDA_CHECK(cudaSetDevice(device_id));
    CUDA_CHECK(cudaMemGetInfo(&free_mem, &total_mem));
    return total_mem - free_mem;
}

size_t CudaMemoryManager::get_available_memory(int device_id) {
    size_t free_mem, total_mem;
    CUDA_CHECK(cudaSetDevice(device_id));
    CUDA_CHECK(cudaMemGetInfo(&free_mem, &total_mem));
    return free_mem;
}

void CudaMemoryManager::clear_cache() {
    CUDA_CHECK(cudaDeviceSynchronize());
    // PyTorch will handle cache clearing through C10
}

// CudaStreamManager implementation

CudaStreamManager::CudaStreamManager(int num_streams)
    : num_streams_(num_streams) {
    streams_.resize(num_streams);
    for (int i = 0; i < num_streams; ++i) {
        CUDA_CHECK(cudaStreamCreate(&streams_[i]));
    }
}

CudaStreamManager::~CudaStreamManager() {
    for (auto stream : streams_) {
        cudaStreamDestroy(stream);
    }
}

cudaStream_t CudaStreamManager::get_stream(int index) {
    if (index < 0 || index >= num_streams_) {
        throw std::out_of_range("Stream index out of range");
    }
    return streams_[index];
}

void CudaStreamManager::synchronize_all() {
    for (auto stream : streams_) {
        CUDA_CHECK(cudaStreamSynchronize(stream));
    }
}

} // namespace cuda
} // namespace meshml

#endif // USE_CUDA
