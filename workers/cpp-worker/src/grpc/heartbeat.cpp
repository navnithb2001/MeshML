#include "meshml/grpc/heartbeat.h"
#include <iostream>
#include <chrono>
#include <thread>

namespace meshml {

HeartbeatSender::HeartbeatSender(const std::string& worker_id, int interval_seconds)
    : worker_id_(worker_id)
    , interval_seconds_(interval_seconds)
{
    // Initialize default status
    status_["worker_id"] = worker_id;
    status_["state"] = "idle";
    
    std::cout << "HeartbeatSender created: worker_id=" << worker_id 
              << ", interval=" << interval_seconds << "s" << std::endl;
}

HeartbeatSender::~HeartbeatSender() {
    stop();
}

void HeartbeatSender::start() {
    if (running_.load()) {
        std::cout << "Heartbeat already running" << std::endl;
        return;
    }
    
    if (!callback_) {
        std::cerr << "Warning: No heartbeat callback set" << std::endl;
        return;
    }
    
    running_.store(true);
    
    // Start heartbeat thread
    heartbeat_thread_ = std::thread([this]() {
        heartbeat_loop();
    });
    
    std::cout << "Heartbeat started" << std::endl;
}

void HeartbeatSender::stop() {
    if (!running_.load()) {
        return;
    }
    
    running_.store(false);
    
    // Wait for thread to finish
    if (heartbeat_thread_.joinable()) {
        heartbeat_thread_.join();
    }
    
    std::cout << "Heartbeat stopped" << std::endl;
}

void HeartbeatSender::set_heartbeat_callback(HeartbeatCallback callback) {
    callback_ = callback;
}

void HeartbeatSender::update_status(const std::string& key, const std::string& value) {
    std::lock_guard<std::mutex> lock(status_mutex_);
    status_[key] = value;
}

void HeartbeatSender::update_status(const std::map<std::string, std::string>& status) {
    std::lock_guard<std::mutex> lock(status_mutex_);
    for (const auto& [key, value] : status) {
        status_[key] = value;
    }
}

std::map<std::string, std::string> HeartbeatSender::get_status() const {
    std::lock_guard<std::mutex> lock(status_mutex_);
    return status_;
}

bool HeartbeatSender::is_healthy() const {
    if (!running_.load()) {
        return false;
    }
    
    // Check if last heartbeat was recent
    auto now = std::chrono::system_clock::now().time_since_epoch().count();
    auto last = last_heartbeat_time_.load();
    
    // Consider unhealthy if no heartbeat in 2x interval
    int64_t threshold = interval_seconds_ * 2 * 1000000000LL; // Convert to nanoseconds
    
    return (now - last) < threshold;
}

int64_t HeartbeatSender::get_last_heartbeat_time() const {
    return last_heartbeat_time_.load();
}

void HeartbeatSender::heartbeat_loop() {
    std::cout << "Heartbeat loop started" << std::endl;
    
    while (running_.load()) {
        // Send heartbeat
        bool success = send_heartbeat();
        
        if (success) {
            // Update last heartbeat time
            auto now = std::chrono::system_clock::now().time_since_epoch().count();
            last_heartbeat_time_.store(now);
        }
        
        // Sleep for interval
        for (int i = 0; i < interval_seconds_ && running_.load(); ++i) {
            std::this_thread::sleep_for(std::chrono::seconds(1));
        }
    }
    
    std::cout << "Heartbeat loop ended" << std::endl;
}

bool HeartbeatSender::send_heartbeat() {
    if (!callback_) {
        std::cerr << "No heartbeat callback set" << std::endl;
        return false;
    }
    
    // Get current status
    std::map<std::string, std::string> heartbeat_data;
    {
        std::lock_guard<std::mutex> lock(status_mutex_);
        heartbeat_data = status_;
    }
    
    // Add timestamp
    auto now = std::chrono::system_clock::now();
    auto timestamp = std::chrono::duration_cast<std::chrono::seconds>(
        now.time_since_epoch()
    ).count();
    heartbeat_data["timestamp"] = std::to_string(timestamp);
    
    // Try sending with retries
    for (int attempt = 0; attempt < MAX_RETRIES; ++attempt) {
        try {
            bool success = callback_(heartbeat_data);
            
            if (success) {
                // Only log on first attempt or after retry
                if (attempt > 0) {
                    std::cout << "Heartbeat sent successfully (after " 
                             << attempt << " retries)" << std::endl;
                }
                return true;
            }
            
        } catch (const std::exception& e) {
            std::cerr << "Heartbeat callback exception: " << e.what() << std::endl;
        }
        
        // Wait before retry
        if (attempt < MAX_RETRIES - 1) {
            std::this_thread::sleep_for(std::chrono::milliseconds(RETRY_DELAY_MS));
        }
    }
    
    std::cerr << "Failed to send heartbeat after " << MAX_RETRIES << " attempts" << std::endl;
    return false;
}

std::unique_ptr<HeartbeatSender> create_heartbeat_sender(
    const std::string& worker_id,
    int interval_seconds)
{
    return std::make_unique<HeartbeatSender>(worker_id, interval_seconds);
}

} // namespace meshml
