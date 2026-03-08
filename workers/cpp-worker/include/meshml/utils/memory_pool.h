/**
 * @file memory_pool.h
 * @brief Memory pool for efficient tensor allocation
 * 
 * Features:
 * - Pre-allocated memory pool
 * - Fast allocation/deallocation
 * - Reduces memory fragmentation
 * - Supports CPU and GPU memory
 */

#pragma once

#include <cstddef>
#include <memory>
#include <vector>
#include <mutex>
#include <atomic>

namespace meshml {
namespace utils {

/**
 * @brief Memory block metadata
 */
struct MemoryBlock {
    void* ptr;
    size_t size;
    bool is_free;
    
    MemoryBlock(void* p = nullptr, size_t s = 0, bool free = true)
        : ptr(p), size(s), is_free(free) {}
};

/**
 * @brief Thread-safe memory pool
 */
class MemoryPool {
public:
    /**
     * @brief Constructor
     * @param total_size Total size of memory pool in bytes
     * @param use_gpu Whether to use GPU memory
     */
    explicit MemoryPool(size_t total_size, bool use_gpu = false);
    
    /**
     * @brief Destructor
     */
    ~MemoryPool();
    
    /**
     * @brief Allocate memory from pool
     * @param size Number of bytes to allocate
     * @return Pointer to allocated memory, or nullptr if allocation fails
     */
    void* allocate(size_t size);
    
    /**
     * @brief Deallocate memory back to pool
     * @param ptr Pointer to memory to deallocate
     */
    void deallocate(void* ptr);
    
    /**
     * @brief Reset pool (deallocate all blocks)
     */
    void reset();
    
    /**
     * @brief Get total pool size
     */
    size_t total_size() const { return total_size_; }
    
    /**
     * @brief Get used memory size
     */
    size_t used_size() const { return used_size_.load(); }
    
    /**
     * @brief Get free memory size
     */
    size_t free_size() const { return total_size_ - used_size_.load(); }
    
    /**
     * @brief Check if using GPU memory
     */
    bool is_gpu() const { return use_gpu_; }

private:
    void* pool_ptr_;                      // Base pointer to pool
    size_t total_size_;                   // Total pool size
    std::atomic<size_t> used_size_;       // Currently used size
    bool use_gpu_;                        // Whether using GPU memory
    
    std::vector<MemoryBlock> blocks_;     // List of memory blocks
    std::mutex mutex_;                    // Thread safety
    
    // Find free block of at least size bytes
    MemoryBlock* find_free_block(size_t size);
    
    // Merge adjacent free blocks
    void merge_free_blocks();
};

} // namespace utils
} // namespace meshml
