/**
 * @file performance_example.cpp
 * @brief Example demonstrating performance optimization features
 */

#include "meshml/utils/performance.h"
#include "meshml/utils/simd_ops.h"
#include "meshml/utils/memory_pool.h"
#include <torch/torch.h>
#include <iostream>
#include <vector>

using namespace meshml;

void demo_performance_profiling() {
    std::cout << "\n=== Performance Profiling Demo ===" << std::endl;
    
    auto profiler = create_performance_profiler();
    
    // Simulate training loop
    for (int epoch = 0; epoch < 3; ++epoch) {
        for (int batch = 0; batch < 10; ++batch) {
            // Profile data loading
            {
                ProfileScope scope(*profiler, "data_loading");
                // Simulate data loading
                std::this_thread::sleep_for(std::chrono::milliseconds(5));
            }
            
            // Profile forward pass
            {
                ProfileScope scope(*profiler, "forward_pass");
                auto input = torch::randn({32, 784});
                auto output = torch::relu(input);
                std::this_thread::sleep_for(std::chrono::milliseconds(10));
            }
            
            // Profile backward pass
            {
                ProfileScope scope(*profiler, "backward_pass");
                auto input = torch::randn({32, 784}, torch::requires_grad());
                auto output = torch::relu(input);
                auto loss = output.sum();
                loss.backward();
                std::this_thread::sleep_for(std::chrono::milliseconds(12));
            }
            
            // Profile optimizer step
            {
                ProfileScope scope(*profiler, "optimizer_step");
                std::this_thread::sleep_for(std::chrono::milliseconds(3));
            }
        }
    }
    
    // Print summary
    profiler->print_summary();
}

void demo_memory_profiling() {
    std::cout << "\n=== Memory Profiling Demo ===" << std::endl;
    
    std::string device = torch::cuda::is_available() ? "cuda" : "cpu";
    auto memory_profiler = create_memory_profiler(device);
    
    std::cout << "Device: " << device << std::endl;
    std::cout << "Initial memory: " << memory_profiler->get_memory_usage() << " MB" << std::endl;
    
    // Allocate some tensors
    std::vector<torch::Tensor> tensors;
    for (int i = 0; i < 5; ++i) {
        auto tensor = torch::randn({1024, 1024});
        if (device == "cuda") {
            tensor = tensor.cuda();
        }
        tensors.push_back(tensor);
        
        std::cout << "After allocation " << (i + 1) << ": " 
                  << memory_profiler->get_memory_usage() << " MB" << std::endl;
    }
    
    std::cout << "Peak memory: " << memory_profiler->get_peak_memory() << " MB" << std::endl;
    
    // Clear tensors
    tensors.clear();
    
    std::cout << "After clearing: " << memory_profiler->get_memory_usage() << " MB" << std::endl;
    
    memory_profiler->print_summary();
}

void demo_simd_operations() {
    std::cout << "\n=== SIMD Operations Demo ===" << std::endl;
    
    // Show capabilities
    std::cout << simd::get_simd_capabilities() << std::endl;
    
    const size_t size = 1000000;
    std::vector<float> a(size);
    std::vector<float> b(size);
    std::vector<float> result(size);
    
    // Initialize
    for (size_t i = 0; i < size; ++i) {
        a[i] = static_cast<float>(i) / size;
        b[i] = static_cast<float>(size - i) / size;
    }
    
    // Vector addition
    {
        Timer timer;
        simd::vector_add(a.data(), b.data(), result.data(), size);
        std::cout << "\nVector Add (" << size << " elements): " 
                  << timer.elapsed_ms() << " ms" << std::endl;
    }
    
    // Dot product
    {
        Timer timer;
        float dot = simd::vector_dot(a.data(), b.data(), size);
        std::cout << "Dot Product: " << dot 
                  << " (computed in " << timer.elapsed_ms() << " ms)" << std::endl;
    }
    
    // Vector norm
    {
        Timer timer;
        float norm = simd::vector_norm(a.data(), size);
        std::cout << "Vector Norm: " << norm 
                  << " (computed in " << timer.elapsed_ms() << " ms)" << std::endl;
    }
    
    // Run benchmark
    simd::benchmark_simd_operations();
}

void demo_memory_pool() {
    std::cout << "\n=== Memory Pool Demo ===" << std::endl;
    
    // Create memory pool (10 MB)
    auto pool = create_memory_pool(10 * 1024 * 1024, "cpu");
    
    std::cout << "Initial state:" << std::endl;
    pool->print_stats();
    
    // Allocate some memory
    std::vector<void*> allocations;
    for (int i = 0; i < 10; ++i) {
        size_t size = (i + 1) * 100 * 1024;  // 100 KB, 200 KB, ...
        void* ptr = pool->allocate(size);
        
        if (ptr) {
            allocations.push_back(ptr);
            std::cout << "\nAllocated " << (size / 1024) << " KB" << std::endl;
        } else {
            std::cout << "\nFailed to allocate " << (size / 1024) << " KB" << std::endl;
            break;
        }
    }
    
    std::cout << "\nAfter allocations:" << std::endl;
    pool->print_stats();
    
    // Deallocate half
    for (size_t i = 0; i < allocations.size() / 2; ++i) {
        pool->deallocate(allocations[i]);
    }
    
    std::cout << "\nAfter partial deallocation:" << std::endl;
    pool->print_stats();
    
    // Deallocate rest
    for (size_t i = allocations.size() / 2; i < allocations.size(); ++i) {
        pool->deallocate(allocations[i]);
    }
    
    std::cout << "\nAfter full deallocation:" << std::endl;
    pool->print_stats();
}

void demo_tensor_memory_pool() {
    std::cout << "\n=== Tensor Memory Pool Demo ===" << std::endl;
    
    auto tensor_pool = create_tensor_memory_pool(50 * 1024 * 1024, "cpu");
    
    // Allocate tensors
    std::vector<float*> tensors;
    for (int i = 0; i < 5; ++i) {
        size_t num_elements = 100000 * (i + 1);
        float* tensor = tensor_pool->allocate_tensor(num_elements);
        
        if (tensor) {
            // Initialize tensor
            for (size_t j = 0; j < num_elements; ++j) {
                tensor[j] = static_cast<float>(j) / num_elements;
            }
            
            tensors.push_back(tensor);
            std::cout << "Allocated tensor with " << num_elements << " elements" << std::endl;
        }
    }
    
    tensor_pool->get_pool().print_stats();
    
    // Deallocate
    for (auto* tensor : tensors) {
        tensor_pool->deallocate_tensor(tensor);
    }
    
    std::cout << "\nAfter deallocation:" << std::endl;
    tensor_pool->get_pool().print_stats();
}

void demo_throughput_monitoring() {
    std::cout << "\n=== Throughput Monitoring Demo ===" << std::endl;
    
    ThroughputMonitor monitor;
    
    // Simulate training
    const int num_batches = 100;
    const int batch_size = 32;
    
    for (int i = 0; i < num_batches; ++i) {
        // Simulate batch processing
        std::this_thread::sleep_for(std::chrono::milliseconds(10));
        
        monitor.record_batch(batch_size);
        
        // Print progress every 20 batches
        if ((i + 1) % 20 == 0) {
            std::cout << "Batch " << (i + 1) << "/" << num_batches << ": "
                      << monitor.get_samples_per_second() << " samples/sec, "
                      << monitor.get_batches_per_second() << " batches/sec"
                      << std::endl;
        }
    }
    
    std::cout << "\nFinal Throughput:" << std::endl;
    std::cout << "  Samples/sec: " << monitor.get_samples_per_second() << std::endl;
    std::cout << "  Batches/sec: " << monitor.get_batches_per_second() << std::endl;
}

int main() {
    std::cout << "=== C++ Worker Performance Optimization Examples ===" << std::endl;
    
    try {
        // Demo 1: Performance Profiling
        demo_performance_profiling();
        
        // Demo 2: Memory Profiling
        demo_memory_profiling();
        
        // Demo 3: SIMD Operations
        demo_simd_operations();
        
        // Demo 4: Memory Pool
        demo_memory_pool();
        
        // Demo 5: Tensor Memory Pool
        demo_tensor_memory_pool();
        
        // Demo 6: Throughput Monitoring
        demo_throughput_monitoring();
        
        std::cout << "\n=== All Demos Completed ===" << std::endl;
        
    } catch (const std::exception& e) {
        std::cerr << "Error: " << e.what() << std::endl;
        return 1;
    }
    
    return 0;
}
