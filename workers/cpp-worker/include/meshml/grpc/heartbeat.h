#pragma once

#include <string>
#include <functional>
#include <thread>
#include <atomic>
#include <mutex>
#include <map>
#include <chrono>

namespace meshml {

/**
 * @brief Heartbeat sender for monitoring worker health
 * 
 * Sends periodic heartbeats to Parameter Server to indicate
 * the worker is alive and processing.
 */
class HeartbeatSender {
public:
    using HeartbeatCallback = std::function<bool(const std::map<std::string, std::string>&)>;
    
    /**
     * @brief Construct heartbeat sender
     * @param worker_id Worker identifier
     * @param interval_seconds Heartbeat interval in seconds
     */
    HeartbeatSender(const std::string& worker_id, int interval_seconds = 30);
    
    /**
     * @brief Destructor - stops heartbeat thread
     */
    ~HeartbeatSender();
    
    // Disable copy
    HeartbeatSender(const HeartbeatSender&) = delete;
    HeartbeatSender& operator=(const HeartbeatSender&) = delete;
    
    /**
     * @brief Start sending heartbeats
     */
    void start();
    
    /**
     * @brief Stop sending heartbeats
     */
    void stop();
    
    /**
     * @brief Check if heartbeat is running
     */
    bool is_running() const { return running_.load(); }
    
    /**
     * @brief Set callback function for sending heartbeats
     * @param callback Function that sends heartbeat data
     */
    void set_heartbeat_callback(HeartbeatCallback callback);
    
    /**
     * @brief Update worker status
     * @param key Status key
     * @param value Status value
     */
    void update_status(const std::string& key, const std::string& value);
    
    /**
     * @brief Update multiple status fields
     * @param status Status map
     */
    void update_status(const std::map<std::string, std::string>& status);
    
    /**
     * @brief Get current status
     */
    std::map<std::string, std::string> get_status() const;
    
    /**
     * @brief Check if worker is healthy
     * @return true if heartbeats are being sent successfully
     */
    bool is_healthy() const;
    
    /**
     * @brief Get last heartbeat timestamp
     * @return Timestamp of last successful heartbeat (epoch seconds)
     */
    int64_t get_last_heartbeat_time() const;
    
private:
    /**
     * @brief Heartbeat loop (runs in separate thread)
     */
    void heartbeat_loop();
    
    /**
     * @brief Send a single heartbeat
     * @return true if successful
     */
    bool send_heartbeat();
    
    std::string worker_id_;
    int interval_seconds_;
    std::atomic<bool> running_{false};
    std::atomic<int64_t> last_heartbeat_time_{0};
    
    std::map<std::string, std::string> status_;
    mutable std::mutex status_mutex_;
    
    HeartbeatCallback callback_;
    std::thread heartbeat_thread_;
    
    static constexpr int MAX_RETRIES = 3;
    static constexpr int RETRY_DELAY_MS = 1000;
};

/**
 * @brief Create heartbeat sender
 * @param worker_id Worker identifier
 * @param interval_seconds Heartbeat interval
 * @return Unique pointer to heartbeat sender
 */
std::unique_ptr<HeartbeatSender> create_heartbeat_sender(
    const std::string& worker_id,
    int interval_seconds = 30
);

} // namespace meshml
