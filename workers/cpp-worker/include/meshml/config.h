#pragma once

#include <string>
#include <memory>

namespace meshml {

/**
 * @brief Worker configuration
 */
struct WorkerConfig {
    // Worker identity
    std::string worker_id;
    std::string worker_name;
    
    // Parameter Server connection
    std::string parameter_server_url;
    std::string grpc_url;
    int timeout_seconds = 30;
    
    // Training configuration
    int batch_size = 32;
    int num_workers = 4;
    float learning_rate = 0.001f;
    std::string device = "auto";  // auto, cpu, cuda, cuda:0, etc.
    
    // Storage paths
    std::string checkpoints_dir = "./checkpoints";
    std::string models_dir = "./models";
    std::string data_dir = "./data";
    
    // Heartbeat
    int heartbeat_interval_seconds = 30;
    
    // Logging
    std::string log_level = "INFO";
    std::string log_file = "";
    
    /**
     * @brief Load configuration from YAML file
     */
    static std::unique_ptr<WorkerConfig> load_from_file(const std::string& path);
    
    /**
     * @brief Save configuration to YAML file
     */
    void save_to_file(const std::string& path) const;
    
    /**
     * @brief Create default configuration
     */
    static std::unique_ptr<WorkerConfig> create_default();
};

} // namespace meshml
