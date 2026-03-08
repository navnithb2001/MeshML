#pragma once

#include <string>
#include <memory>
#include <functional>
#include <map>
#include <vector>
#include <atomic>
#include <mutex>
#include <grpcpp/grpcpp.h>

namespace meshml {

// Forward declarations
struct WorkerConfig;

/**
 * @brief gRPC client for communicating with Parameter Server
 * 
 * Handles:
 * - Fetching model weights
 * - Pushing gradients
 * - Version tracking
 * - Compression/decompression
 * - Connection management
 */
class GRPCClient {
public:
    /**
     * @brief Construct gRPC client
     * @param server_url gRPC server URL (e.g., "localhost:50051")
     * @param timeout_seconds Connection timeout
     */
    explicit GRPCClient(const std::string& server_url, int timeout_seconds = 30);
    
    /**
     * @brief Destructor
     */
    ~GRPCClient();
    
    // Disable copy
    GRPCClient(const GRPCClient&) = delete;
    GRPCClient& operator=(const GRPCClient&) = delete;
    
    /**
     * @brief Connect to Parameter Server
     * @return true if connected successfully
     */
    bool connect();
    
    /**
     * @brief Disconnect from Parameter Server
     */
    void disconnect();
    
    /**
     * @brief Check if connected
     */
    bool is_connected() const { return connected_.load(); }
    
    /**
     * @brief Get model weights from Parameter Server
     * @param job_id Job identifier
     * @param worker_id Worker identifier
     * @param epoch Current epoch
     * @return Pair of (state_dict, version)
     */
    std::pair<std::map<std::string, std::vector<float>>, int> 
    get_weights(const std::string& job_id, 
                const std::string& worker_id,
                int epoch = 0);
    
    /**
     * @brief Push gradients to Parameter Server
     * @param job_id Job identifier
     * @param worker_id Worker identifier
     * @param gradients Gradient tensors
     * @param batch_id Current batch ID
     * @param epoch Current epoch
     * @param batch_size Batch size used
     * @param learning_rate Learning rate
     * @param metadata Additional metadata (loss, gradient_norm, etc.)
     * @return Response with success status and new version
     */
    std::map<std::string, std::string> 
    push_gradients(const std::string& job_id,
                   const std::string& worker_id,
                   const std::map<std::string, std::vector<float>>& gradients,
                   int batch_id,
                   int epoch,
                   int batch_size,
                   float learning_rate,
                   const std::map<std::string, float>& metadata = {});
    
    /**
     * @brief Get current model version
     * @param job_id Job identifier
     * @return Version information
     */
    std::map<std::string, std::string> get_model_version(const std::string& job_id);
    
    /**
     * @brief Get current version number
     */
    int get_current_version() const { return current_version_.load(); }
    
private:
    /**
     * @brief Compress data using gzip
     * @param data Input data
     * @return Compressed data
     */
    std::vector<uint8_t> compress_data(const std::vector<uint8_t>& data);
    
    /**
     * @brief Decompress gzip data
     * @param data Compressed data
     * @return Decompressed data
     */
    std::vector<uint8_t> decompress_data(const std::vector<uint8_t>& data);
    
    /**
     * @brief Serialize gradients to bytes
     */
    std::vector<uint8_t> serialize_gradients(
        const std::map<std::string, std::vector<float>>& gradients);
    
    /**
     * @brief Deserialize weights from bytes
     */
    std::map<std::string, std::vector<float>> deserialize_weights(
        const std::vector<uint8_t>& data);
    
    std::string server_url_;
    int timeout_seconds_;
    std::atomic<bool> connected_{false};
    std::atomic<int> current_version_{0};
    
    // gRPC channel and stub
    std::shared_ptr<grpc::Channel> channel_;
    std::mutex channel_mutex_;
    
    // Note: Actual stub would be generated from .proto files
    // For now, we'll use a placeholder that will be replaced
    // with the generated stub class
};

} // namespace meshml
