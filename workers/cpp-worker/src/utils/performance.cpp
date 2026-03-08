/**
 * @file performance.cpp
 * @brief Performance monitoring implementation
 */

#include "meshml/utils/performance.h"
#include <iostream>
#include <iomanip>
#include <sstream>
#include <numeric>
#include <algorithm>

// Stub implementations for CUDA functions (CUDA not available on macOS)
namespace torch {
namespace cuda {
    bool is_available() { return false; }
    size_t memory_allocated(int device) { return 0; }
    size_t memory_reserved(int device) { return 0; }
    void reset_peak_memory_stats(int device) {}
}
}

namespace meshml {
namespace utils {

// PerformanceMetrics implementation

std::string PerformanceMetrics::to_string() const {
    std::ostringstream oss;
    oss << std::fixed << std::setprecision(2);
    oss << "Performance Metrics:\n";
    oss << "  Throughput:\n";
    oss << "    Samples/sec: " << samples_per_second << "\n";
    oss << "    Batches/sec: " << batches_per_second << "\n";
    oss << "  Timing Breakdown:\n";
    oss << "    Data Loading: " << data_loading_ms << " ms\n";
    oss << "    Forward Pass:  " << forward_pass_ms << " ms\n";
    oss << "    Backward Pass: " << backward_pass_ms << " ms\n";
    oss << "    Optimizer:     " << optimizer_step_ms << " ms\n";
    oss << "    Gradient Push: " << gradient_push_ms << " ms\n";
    oss << "    Total/Batch:   " << total_batch_time_ms() << " ms\n";
    oss << "  Memory:\n";
    oss << "    GPU Used:      " << gpu_memory_used_mb << " MB\n";
    oss << "    GPU Allocated: " << gpu_memory_allocated_mb << " MB\n";
    oss << "    CPU Used:      " << cpu_memory_used_mb << " MB\n";
    oss << "  Utilization:\n";
    oss << "    GPU: " << gpu_utilization_percent << "%\n";
    oss << "    CPU: " << cpu_utilization_percent << "%\n";
    return oss.str();
}

// PerformanceProfiler implementation

PerformanceProfiler::PerformanceProfiler() {
    overall_timer_.reset();
}

void PerformanceProfiler::start_section(const std::string& name) {
    if (!enabled_) return;
    
    section_starts_[name] = std::chrono::high_resolution_clock::now();
}

void PerformanceProfiler::end_section(const std::string& name) {
    if (!enabled_) return;
    
    auto it = section_starts_.find(name);
    if (it == section_starts_.end()) {
        return;  // Section not started
    }
    
    auto now = std::chrono::high_resolution_clock::now();
    auto duration = std::chrono::duration_cast<std::chrono::microseconds>(
        now - it->second
    );
    
    double elapsed_ms = duration.count() / 1000.0;
    section_times_[name].push_back(elapsed_ms);
    
    section_starts_.erase(it);
}

void PerformanceProfiler::record_metric(const std::string& name, double value) {
    if (!enabled_) return;
    
    metrics_[name].push_back(value);
}

double PerformanceProfiler::get_average_time(const std::string& name) const {
    auto it = section_times_.find(name);
    if (it == section_times_.end() || it->second.empty()) {
        return 0.0;
    }
    
    double sum = std::accumulate(it->second.begin(), it->second.end(), 0.0);
    return sum / it->second.size();
}

PerformanceMetrics PerformanceProfiler::get_metrics() const {
    PerformanceMetrics metrics;
    
    // Calculate throughput
    double elapsed_s = overall_timer_.elapsed_s();
    if (elapsed_s > 0) {
        metrics.samples_per_second = total_samples_.load() / elapsed_s;
        metrics.batches_per_second = total_batches_.load() / elapsed_s;
    }
    
    // Get timing breakdown
    metrics.data_loading_ms = get_average_time("data_loading");
    metrics.forward_pass_ms = get_average_time("forward_pass");
    metrics.backward_pass_ms = get_average_time("backward_pass");
    metrics.optimizer_step_ms = get_average_time("optimizer_step");
    metrics.gradient_push_ms = get_average_time("gradient_push");
    
    // Get memory stats (if CUDA available)
    if (torch::cuda::is_available()) {
        metrics.gpu_memory_used_mb = torch::cuda::memory_reserved(0) / (1024 * 1024);
        metrics.gpu_memory_allocated_mb = torch::cuda::memory_allocated(0) / (1024 * 1024);
    }
    
    return metrics;
}

void PerformanceProfiler::reset() {
    section_times_.clear();
    metrics_.clear();
    section_starts_.clear();
    total_samples_ = 0;
    total_batches_ = 0;
    overall_timer_.reset();
}

void PerformanceProfiler::print_summary() const {
    auto metrics = get_metrics();
    std::cout << "\n" << metrics.to_string() << std::endl;
    
    // Print detailed section timings
    if (!section_times_.empty()) {
        std::cout << "\nDetailed Timings:" << std::endl;
        std::cout << std::fixed << std::setprecision(2);
        
        for (const auto& [name, times] : section_times_) {
            if (times.empty()) continue;
            
            double avg = std::accumulate(times.begin(), times.end(), 0.0) / times.size();
            double min = *std::min_element(times.begin(), times.end());
            double max = *std::max_element(times.begin(), times.end());
            
            std::cout << "  " << std::setw(20) << std::left << name << ": "
                      << "avg=" << std::setw(8) << avg << "ms, "
                      << "min=" << std::setw(8) << min << "ms, "
                      << "max=" << std::setw(8) << max << "ms, "
                      << "count=" << times.size() << std::endl;
        }
    }
}

std::string PerformanceProfiler::report() const {
    std::ostringstream oss;
    auto metrics = get_metrics();
    oss << metrics.to_string() << "\n";
    
    // Add detailed section timings
    if (!section_times_.empty()) {
        oss << "\nDetailed Timings:\n";
        oss << std::fixed << std::setprecision(2);
        
        for (const auto& [name, times] : section_times_) {
            if (times.empty()) continue;
            
            double avg = std::accumulate(times.begin(), times.end(), 0.0) / times.size();
            double min = *std::min_element(times.begin(), times.end());
            double max = *std::max_element(times.begin(), times.end());
            
            oss << "  " << std::setw(20) << std::left << name << ": "
                << "avg=" << std::setw(8) << avg << "ms, "
                << "min=" << std::setw(8) << min << "ms, "
                << "max=" << std::setw(8) << max << "ms, "
                << "count=" << times.size() << "\n";
        }
    }
    
    return oss.str();
}

// MemoryProfiler implementation

MemoryProfiler::MemoryProfiler(const std::string& device) : device_(device) {}

size_t MemoryProfiler::get_memory_usage() const {
    if (device_ == "cuda" && torch::cuda::is_available()) {
        size_t current = torch::cuda::memory_allocated(0) / (1024 * 1024);
        peak_memory_ = std::max(peak_memory_, current);
        return current;
    }
    // TODO: Implement CPU memory tracking
    return 0;
}

size_t MemoryProfiler::get_allocated_memory() const {
    if (device_ == "cuda" && torch::cuda::is_available()) {
        return torch::cuda::memory_reserved(0) / (1024 * 1024);
    }
    return 0;
}

size_t MemoryProfiler::get_peak_memory() const {
    get_memory_usage();  // Update peak
    return peak_memory_;
}

void MemoryProfiler::reset_peak_memory() {
    peak_memory_ = 0;
    if (device_ == "cuda" && torch::cuda::is_available()) {
        torch::cuda::reset_peak_memory_stats(0);
    }
}

std::map<std::string, size_t> MemoryProfiler::get_memory_stats() const {
    std::map<std::string, size_t> stats;
    
    if (device_ == "cuda" && torch::cuda::is_available()) {
        stats["allocated_mb"] = torch::cuda::memory_allocated(0) / (1024 * 1024);
        stats["reserved_mb"] = torch::cuda::memory_reserved(0) / (1024 * 1024);
        stats["peak_allocated_mb"] = peak_memory_;
    } else {
        stats["allocated_mb"] = 0;
        stats["reserved_mb"] = 0;
        stats["peak_allocated_mb"] = 0;
    }
    
    return stats;
}

void MemoryProfiler::print_summary() const {
    auto stats = get_memory_stats();
    
    std::cout << "\nMemory Summary (" << device_ << "):" << std::endl;
    std::cout << "  Allocated:     " << stats["allocated_mb"] << " MB" << std::endl;
    std::cout << "  Reserved:      " << stats["reserved_mb"] << " MB" << std::endl;
    std::cout << "  Peak Allocated:" << stats["peak_allocated_mb"] << " MB" << std::endl;
}

// ThroughputMonitor implementation

ThroughputMonitor::ThroughputMonitor() {
    timer_.reset();
}

void ThroughputMonitor::record_batch(size_t batch_size) {
    total_samples_ += batch_size;
    total_batches_++;
}

double ThroughputMonitor::get_samples_per_second() const {
    double elapsed = timer_.elapsed_s();
    if (elapsed > 0) {
        return total_samples_.load() / elapsed;
    }
    return 0.0;
}

double ThroughputMonitor::get_batches_per_second() const {
    double elapsed = timer_.elapsed_s();
    if (elapsed > 0) {
        return total_batches_.load() / elapsed;
    }
    return 0.0;
}

void ThroughputMonitor::reset() {
    timer_.reset();
    total_samples_ = 0;
    total_batches_ = 0;
}

// Factory functions

std::unique_ptr<PerformanceProfiler> create_performance_profiler() {
    return std::make_unique<PerformanceProfiler>();
}

std::unique_ptr<MemoryProfiler> create_memory_profiler(const std::string& device) {
    return std::make_unique<MemoryProfiler>(device);
}

} // namespace utils
} // namespace meshml
