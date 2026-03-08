/**
 * @file performance.h
 * @brief Performance monitoring and profiling utilities
 * 
 * Features:
 * - Training performance metrics
 * - Memory profiling
 * - Throughput measurement
 * - Bottleneck detection
 * - Performance logging
 */

#pragma once

#include <chrono>
#include <string>
#include <map>
#include <vector>
#include <memory>
#include <atomic>

namespace meshml {
namespace utils {

/**
 * @brief High-resolution timer for performance measurement
 */
class Timer {
public:
    Timer() : start_time_(std::chrono::high_resolution_clock::now()) {}
    
    /**
     * @brief Reset timer to current time
     */
    void reset() {
        start_time_ = std::chrono::high_resolution_clock::now();
    }
    
    /**
     * @brief Get elapsed time in milliseconds
     */
    double elapsed_ms() const {
        auto now = std::chrono::high_resolution_clock::now();
        auto duration = std::chrono::duration_cast<std::chrono::microseconds>(
            now - start_time_
        );
        return duration.count() / 1000.0;
    }
    
    /**
     * @brief Get elapsed time in seconds
     */
    double elapsed_s() const {
        return elapsed_ms() / 1000.0;
    }
    
private:
    std::chrono::high_resolution_clock::time_point start_time_;
};

/**
 * @brief Scoped timer that automatically logs duration
 */
class ScopedTimer {
public:
    ScopedTimer(const std::string& name, bool log_on_destroy = true)
        : name_(name), log_on_destroy_(log_on_destroy) {}
    
    ~ScopedTimer() {
        if (log_on_destroy_) {
            double elapsed = timer_.elapsed_ms();
            // TODO: Log to performance logger
            // For now, just store
        }
    }
    
    double elapsed_ms() const { return timer_.elapsed_ms(); }
    
private:
    std::string name_;
    bool log_on_destroy_;
    Timer timer_;
};

/**
 * @brief Performance metrics for training
 */
struct PerformanceMetrics {
    // Throughput
    double samples_per_second{0.0};
    double batches_per_second{0.0};
    
    // Timing breakdown
    double data_loading_ms{0.0};
    double forward_pass_ms{0.0};
    double backward_pass_ms{0.0};
    double optimizer_step_ms{0.0};
    double gradient_push_ms{0.0};
    
    // Memory
    size_t gpu_memory_used_mb{0};
    size_t gpu_memory_allocated_mb{0};
    size_t cpu_memory_used_mb{0};
    
    // Efficiency
    double gpu_utilization_percent{0.0};
    double cpu_utilization_percent{0.0};
    
    /**
     * @brief Calculate total time per batch
     */
    double total_batch_time_ms() const {
        return data_loading_ms + forward_pass_ms + backward_pass_ms + 
               optimizer_step_ms + gradient_push_ms;
    }
    
    /**
     * @brief Get formatted string representation
     */
    std::string to_string() const;
};

/**
 * @brief Performance profiler for training
 */
class PerformanceProfiler {
public:
    PerformanceProfiler();
    
    /**
     * @brief Start profiling a section
     */
    void start_section(const std::string& name);
    
    /**
     * @brief End profiling a section
     */
    void end_section(const std::string& name);
    
    /**
     * @brief Start profiling (alias for start_section)
     */
    void start(const std::string& name) { start_section(name); }
    
    /**
     * @brief Stop profiling (alias for end_section)
     */
    void stop(const std::string& name) { end_section(name); }
    
    /**
     * @brief Record a metric value
     */
    void record_metric(const std::string& name, double value);
    
    /**
     * @brief Get average time for a section
     */
    double get_average_time(const std::string& name) const;
    
    /**
     * @brief Get elapsed time (alias for get_average_time)
     */
    double get_elapsed(const std::string& name) const { return get_average_time(name); }
    
    /**
     * @brief Get current performance metrics
     */
    PerformanceMetrics get_metrics() const;
    
    /**
     * @brief Reset all statistics
     */
    void reset();
    
    /**
     * @brief Print performance summary
     */
    void print_summary() const;
    
    /**
     * @brief Get performance report as string
     */
    std::string report() const;
    
    /**
     * @brief Enable/disable profiling
     */
    void set_enabled(bool enabled) { enabled_ = enabled; }
    
private:
    bool enabled_{true};
    
    // Timing data
    std::map<std::string, std::chrono::high_resolution_clock::time_point> section_starts_;
    std::map<std::string, std::vector<double>> section_times_;
    std::map<std::string, std::vector<double>> metrics_;
    
    // Counters
    std::atomic<size_t> total_samples_{0};
    std::atomic<size_t> total_batches_{0};
    Timer overall_timer_;
};

/**
 * @brief Memory profiler
 */
class MemoryProfiler {
public:
    /**
     * @brief Construct memory profiler
     * 
     * @param device Device to profile ("cpu", "cuda", "mps")
     */
    explicit MemoryProfiler(const std::string& device);
    
    /**
     * @brief Get current memory usage
     * 
     * @return Memory usage in MB
     */
    size_t get_memory_usage() const;
    
    /**
     * @brief Get allocated memory
     * 
     * @return Allocated memory in MB
     */
    size_t get_allocated_memory() const;
    
    /**
     * @brief Get peak memory usage
     * 
     * @return Peak memory in MB
     */
    size_t get_peak_memory() const;
    
    /**
     * @brief Reset peak memory counter
     */
    void reset_peak_memory();
    
    /**
     * @brief Get detailed memory stats
     */
    std::map<std::string, size_t> get_memory_stats() const;
    
    /**
     * @brief Print memory summary
     */
    void print_summary() const;
    
private:
    std::string device_;
    mutable size_t peak_memory_{0};
};

/**
 * @brief Throughput monitor
 */
class ThroughputMonitor {
public:
    ThroughputMonitor();
    
    /**
     * @brief Record a batch processed
     * 
     * @param batch_size Number of samples in batch
     */
    void record_batch(size_t batch_size);
    
    /**
     * @brief Get current throughput
     * 
     * @return Samples per second
     */
    double get_samples_per_second() const;
    
    /**
     * @brief Get batches per second
     */
    double get_batches_per_second() const;
    
    /**
     * @brief Reset counters
     */
    void reset();
    
private:
    Timer timer_;
    std::atomic<size_t> total_samples_{0};
    std::atomic<size_t> total_batches_{0};
};

/**
 * @brief RAII-style profiling scope
 * 
 * Usage:
 * {
 *     ProfileScope scope(profiler, "forward_pass");
 *     // Code to profile
 * } // Automatically ends profiling
 */
class ProfileScope {
public:
    ProfileScope(PerformanceProfiler& profiler, const std::string& name)
        : profiler_(profiler), name_(name) {
        profiler_.start_section(name_);
    }
    
    ~ProfileScope() {
        profiler_.end_section(name_);
    }
    
private:
    PerformanceProfiler& profiler_;
    std::string name_;
};

/**
 * @brief Performance benchmark utility
 */
class PerformanceBenchmark {
public:
    /**
     * @brief Benchmark a function
     * 
     * @param name Benchmark name
     * @param iterations Number of iterations
     * @param func Function to benchmark
     * @return Average time in milliseconds
     */
    template<typename Func>
    static double benchmark(
        const std::string& name,
        size_t iterations,
        Func&& func
    ) {
        Timer timer;
        
        for (size_t i = 0; i < iterations; ++i) {
            func();
        }
        
        double total_time = timer.elapsed_ms();
        double avg_time = total_time / iterations;
        
        return avg_time;
    }
    
    /**
     * @brief Compare two implementations
     * 
     * @param name1 First implementation name
     * @param func1 First implementation
     * @param name2 Second implementation name
     * @param func2 Second implementation
     * @param iterations Number of iterations
     */
    template<typename Func1, typename Func2>
    static void compare(
        const std::string& name1, Func1&& func1,
        const std::string& name2, Func2&& func2,
        size_t iterations = 100
    );
};

/**
 * @brief Create a performance profiler
 */
std::unique_ptr<PerformanceProfiler> create_performance_profiler();

/**
 * @brief Create a memory profiler
 */
std::unique_ptr<MemoryProfiler> create_memory_profiler(const std::string& device);

} // namespace utils
} // namespace meshml
