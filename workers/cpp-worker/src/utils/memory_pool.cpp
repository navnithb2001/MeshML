/**
 * @file memory_pool.cpp
 * @brief Memory pool implementation
 */

#include "meshml/utils/memory_pool.h"
#include <torch/torch.h>
#include <iostream>
#include <algorithm>
#include <cstring>

namespace meshml {
namespace utils {

// MemoryPool implementation

MemoryPool::MemoryPool(size_t initial_size, const std::string& device)
    : device_(device), total_size_(initial_size)
{
    // Allocate initial pool
    pool_base_ = allocate_physical(initial_size);
    
    if (!pool_base_) {
        throw std::runtime_error("Failed to allocate memory pool");
    }
    
    // Create initial free block
    blocks_.emplace_back(pool_base_, initial_size);
    
    std::cout << "Memory pool created: " << (initial_size / (1024 * 1024)) 
              << " MB on " << device_ << std::endl;
}

MemoryPool::~MemoryPool() {
    if (pool_base_) {
        free_physical(pool_base_);
    }
}

void* MemoryPool::allocate(size_t size) {
    std::lock_guard<std::mutex> lock(mutex_);
    
    // Find free block
    auto block = find_free_block(size);
    
    if (!block) {
        // No suitable block found
        std::cerr << "Memory pool exhausted! Requested: " << size 
                  << " bytes, available: " << get_free_size() << " bytes" << std::endl;
        return nullptr;
    }
    
    // Mark block as in use
    block->in_use = true;
    
    // Update statistics
    stats_.total_allocations++;
    stats_.active_allocations++;
    stats_.current_memory_used += block->size;
    stats_.peak_memory_used = std::max(stats_.peak_memory_used, stats_.current_memory_used);
    
    return block->ptr;
}

void MemoryPool::deallocate(void* ptr) {
    if (!ptr) return;
    
    std::lock_guard<std::mutex> lock(mutex_);
    
    // Find block
    for (auto& block : blocks_) {
        if (block.ptr == ptr && block.in_use) {
            block.in_use = false;
            
            // Update statistics
            stats_.total_deallocations++;
            stats_.active_allocations--;
            stats_.current_memory_used -= block.size;
            
            // Merge adjacent free blocks
            merge_free_blocks();
            
            return;
        }
    }
    
    std::cerr << "Warning: Attempted to deallocate unknown pointer" << std::endl;
}

void MemoryPool::reset() {
    std::lock_guard<std::mutex> lock(mutex_);
    
    // Mark all blocks as free
    for (auto& block : blocks_) {
        block.in_use = false;
    }
    
    // Merge all blocks
    merge_free_blocks();
    
    // Reset statistics (but keep total allocations/deallocations)
    stats_.active_allocations = 0;
    stats_.current_memory_used = 0;
}

size_t MemoryPool::get_used_size() const {
    std::lock_guard<std::mutex> lock(mutex_);
    
    size_t used = 0;
    for (const auto& block : blocks_) {
        if (block.in_use) {
            used += block.size;
        }
    }
    return used;
}

size_t MemoryPool::get_free_size() const {
    return total_size_ - get_used_size();
}

MemoryPool::Stats MemoryPool::get_stats() const {
    std::lock_guard<std::mutex> lock(mutex_);
    return stats_;
}

void MemoryPool::print_stats() const {
    auto stats = get_stats();
    
    std::cout << "\nMemory Pool Statistics:" << std::endl;
    std::cout << "  Total Size:        " << (total_size_ / (1024 * 1024)) << " MB" << std::endl;
    std::cout << "  Used:              " << (stats.current_memory_used / (1024 * 1024)) << " MB" << std::endl;
    std::cout << "  Free:              " << (get_free_size() / (1024 * 1024)) << " MB" << std::endl;
    std::cout << "  Peak Used:         " << (stats.peak_memory_used / (1024 * 1024)) << " MB" << std::endl;
    std::cout << "  Total Allocations: " << stats.total_allocations << std::endl;
    std::cout << "  Active Allocations:" << stats.active_allocations << std::endl;
    std::cout << "  Total Deallocations:" << stats.total_deallocations << std::endl;
}

MemoryBlock* MemoryPool::find_free_block(size_t size) {
    // First-fit strategy
    for (auto& block : blocks_) {
        if (!block.in_use && block.size >= size) {
            // Split block if it's much larger
            if (block.size > size * 2) {
                // TODO: Implement block splitting
            }
            return &block;
        }
    }
    return nullptr;
}

void MemoryPool::split_block(size_t block_idx, size_t size) {
    // TODO: Implement block splitting for better memory utilization
}

void MemoryPool::merge_free_blocks() {
    // Sort blocks by address
    std::sort(blocks_.begin(), blocks_.end(),
        [](const MemoryBlock& a, const MemoryBlock& b) {
            return a.ptr < b.ptr;
        });
    
    // Merge adjacent free blocks
    for (size_t i = 0; i + 1 < blocks_.size(); ) {
        auto& current = blocks_[i];
        auto& next = blocks_[i + 1];
        
        // Check if adjacent and both free
        if (!current.in_use && !next.in_use) {
            char* current_end = static_cast<char*>(current.ptr) + current.size;
            if (current_end == next.ptr) {
                // Merge
                current.size += next.size;
                blocks_.erase(blocks_.begin() + i + 1);
                continue;  // Don't increment i, check again
            }
        }
        ++i;
    }
}

void* MemoryPool::allocate_physical(size_t size) {
    if (device_ == "cuda" && torch::cuda::is_available()) {
        // Allocate CUDA memory
        void* ptr = nullptr;
        // TODO: Use cudaMalloc for actual CUDA allocation
        // For now, use regular malloc as placeholder
        ptr = std::malloc(size);
        return ptr;
    } else {
        // Allocate CPU memory
        return std::malloc(size);
    }
}

void MemoryPool::free_physical(void* ptr) {
    if (device_ == "cuda" && torch::cuda::is_available()) {
        // Free CUDA memory
        // TODO: Use cudaFree for actual CUDA deallocation
        std::free(ptr);
    } else {
        std::free(ptr);
    }
}

// TensorMemoryPool implementation

TensorMemoryPool::TensorMemoryPool(size_t initial_size, const std::string& device)
    : pool_(initial_size, device)
{
}

float* TensorMemoryPool::allocate_tensor(size_t num_elements) {
    size_t bytes = num_elements * sizeof(float);
    return static_cast<float*>(pool_.allocate(bytes));
}

void TensorMemoryPool::deallocate_tensor(float* ptr) {
    pool_.deallocate(ptr);
}

PoolPtr<float> TensorMemoryPool::make_tensor(size_t num_elements) {
    float* ptr = allocate_tensor(num_elements);
    return PoolPtr<float>(ptr, &pool_);
}

// Factory functions

std::shared_ptr<MemoryPool> create_memory_pool(
    size_t initial_size,
    const std::string& device
) {
    return std::make_shared<MemoryPool>(initial_size, device);
}

std::shared_ptr<TensorMemoryPool> create_tensor_memory_pool(
    size_t initial_size,
    const std::string& device
) {
    return std::make_shared<TensorMemoryPool>(initial_size, device);
}

} // namespace utils
} // namespace meshml
