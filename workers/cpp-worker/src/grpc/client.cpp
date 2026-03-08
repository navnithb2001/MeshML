#include "meshml/grpc/client.h"
#include <iostream>
#include <sstream>
#include <zlib.h>
#include <cstring>

namespace meshml {

GRPCClient::GRPCClient(const std::string& server_url, int timeout_seconds)
    : server_url_(server_url)
    , timeout_seconds_(timeout_seconds)
{
    std::cout << "GRPCClient initialized: " << server_url_ << std::endl;
}

GRPCClient::~GRPCClient() {
    disconnect();
}

bool GRPCClient::connect() {
    std::lock_guard<std::mutex> lock(channel_mutex_);
    
    try {
        // Create gRPC channel
        grpc::ChannelArguments args;
        args.SetInt(GRPC_ARG_KEEPALIVE_TIME_MS, 30000);
        args.SetInt(GRPC_ARG_KEEPALIVE_TIMEOUT_MS, 10000);
        args.SetInt(GRPC_ARG_KEEPALIVE_PERMIT_WITHOUT_CALLS, 1);
        
        channel_ = grpc::CreateCustomChannel(
            server_url_,
            grpc::InsecureChannelCredentials(),
            args
        );
        
        if (!channel_) {
            std::cerr << "Failed to create gRPC channel" << std::endl;
            return false;
        }
        
        // Wait for channel to be ready (with timeout)
        auto deadline = std::chrono::system_clock::now() + 
                       std::chrono::seconds(timeout_seconds_);
        
        if (!channel_->WaitForConnected(deadline)) {
            std::cerr << "Failed to connect to gRPC server: " << server_url_ << std::endl;
            return false;
        }
        
        connected_.store(true);
        std::cout << "Connected to Parameter Server: " << server_url_ << std::endl;
        return true;
        
    } catch (const std::exception& e) {
        std::cerr << "Exception during gRPC connection: " << e.what() << std::endl;
        return false;
    }
}

void GRPCClient::disconnect() {
    std::lock_guard<std::mutex> lock(channel_mutex_);
    
    if (connected_.load()) {
        channel_.reset();
        connected_.store(false);
        std::cout << "Disconnected from Parameter Server" << std::endl;
    }
}

std::pair<std::map<std::string, std::vector<float>>, int> 
GRPCClient::get_weights(const std::string& job_id,
                        const std::string& worker_id,
                        int epoch)
{
    if (!connected_.load()) {
        throw std::runtime_error("Not connected to Parameter Server");
    }
    
    // TODO: Replace with actual gRPC call once .proto is defined
    // For now, return mock data
    std::cout << "Fetching weights: job_id=" << job_id 
              << ", worker_id=" << worker_id 
              << ", epoch=" << epoch << std::endl;
    
    // Mock state dict (in production, this would come from gRPC response)
    std::map<std::string, std::vector<float>> state_dict;
    
    // Simulate receiving weights
    // In production: Parse protobuf response, decompress, deserialize
    int new_version = current_version_.load() + 1;
    current_version_.store(new_version);
    
    std::cout << "Fetched weights: version=" << new_version << std::endl;
    
    return {state_dict, new_version};
}

std::map<std::string, std::string> 
GRPCClient::push_gradients(const std::string& job_id,
                          const std::string& worker_id,
                          const std::map<std::string, std::vector<float>>& gradients,
                          int batch_id,
                          int epoch,
                          int batch_size,
                          float learning_rate,
                          const std::map<std::string, float>& metadata)
{
    if (!connected_.load()) {
        throw std::runtime_error("Not connected to Parameter Server");
    }
    
    // TODO: Replace with actual gRPC call once .proto is defined
    std::cout << "Pushing gradients: job_id=" << job_id 
              << ", worker_id=" << worker_id
              << ", batch_id=" << batch_id
              << ", epoch=" << epoch
              << ", batch_size=" << batch_size
              << ", lr=" << learning_rate << std::endl;
    
    // Print metadata
    for (const auto& [key, value] : metadata) {
        std::cout << "  metadata." << key << "=" << value << std::endl;
    }
    
    // Serialize and compress gradients
    auto serialized = serialize_gradients(gradients);
    auto compressed = compress_data(serialized);
    
    float compression_ratio = serialized.empty() ? 1.0f : 
                             static_cast<float>(compressed.size()) / serialized.size();
    
    std::cout << "Gradient data: " << serialized.size() << " bytes, "
              << "compressed to " << compressed.size() << " bytes "
              << "(ratio: " << compression_ratio << ")" << std::endl;
    
    // TODO: Send via gRPC
    // In production: Create protobuf request, send, parse response
    
    // Mock response
    std::map<std::string, std::string> response;
    response["success"] = "true";
    response["new_version"] = std::to_string(current_version_.load() + 1);
    response["acknowledged_gradients"] = std::to_string(gradients.size());
    
    return response;
}

std::map<std::string, std::string> 
GRPCClient::get_model_version(const std::string& job_id)
{
    if (!connected_.load()) {
        throw std::runtime_error("Not connected to Parameter Server");
    }
    
    // TODO: Replace with actual gRPC call
    std::map<std::string, std::string> version_info;
    version_info["current_version"] = std::to_string(current_version_.load());
    version_info["job_id"] = job_id;
    version_info["total_updates"] = "0";
    version_info["last_update_timestamp"] = std::to_string(
        std::chrono::system_clock::now().time_since_epoch().count()
    );
    
    return version_info;
}

std::vector<uint8_t> GRPCClient::compress_data(const std::vector<uint8_t>& data) {
    if (data.empty()) {
        return data;
    }
    
    // Estimate output size (compressBound)
    uLongf compressed_size = compressBound(data.size());
    std::vector<uint8_t> compressed(compressed_size);
    
    // Compress
    int result = compress(
        compressed.data(),
        &compressed_size,
        data.data(),
        data.size()
    );
    
    if (result != Z_OK) {
        std::cerr << "Compression failed: " << result << std::endl;
        return data; // Return uncompressed on failure
    }
    
    compressed.resize(compressed_size);
    
    // Only use compression if it actually reduces size
    if (compressed.size() < data.size() * 0.9) {
        return compressed;
    } else {
        return data; // Not worth compressing
    }
}

std::vector<uint8_t> GRPCClient::decompress_data(const std::vector<uint8_t>& data) {
    if (data.empty()) {
        return data;
    }
    
    // For decompression, we need to know the original size
    // In production, this would be in the protobuf message
    // For now, estimate a reasonable size
    uLongf decompressed_size = data.size() * 10; // Assume max 10x compression
    std::vector<uint8_t> decompressed(decompressed_size);
    
    int result = uncompress(
        decompressed.data(),
        &decompressed_size,
        data.data(),
        data.size()
    );
    
    if (result != Z_OK) {
        std::cerr << "Decompression failed: " << result << std::endl;
        return data; // Return as-is on failure
    }
    
    decompressed.resize(decompressed_size);
    return decompressed;
}

std::vector<uint8_t> GRPCClient::serialize_gradients(
    const std::map<std::string, std::vector<float>>& gradients)
{
    // Simple serialization format:
    // [num_tensors (4 bytes)]
    // For each tensor:
    //   [name_length (4 bytes)] [name (variable)] [data_length (4 bytes)] [data (variable)]
    
    std::vector<uint8_t> result;
    
    // Write number of tensors
    uint32_t num_tensors = gradients.size();
    result.insert(result.end(), 
                  reinterpret_cast<uint8_t*>(&num_tensors),
                  reinterpret_cast<uint8_t*>(&num_tensors) + sizeof(num_tensors));
    
    // Write each tensor
    for (const auto& [name, data] : gradients) {
        // Write name length and name
        uint32_t name_length = name.size();
        result.insert(result.end(),
                     reinterpret_cast<uint8_t*>(&name_length),
                     reinterpret_cast<uint8_t*>(&name_length) + sizeof(name_length));
        result.insert(result.end(), name.begin(), name.end());
        
        // Write data length and data
        uint32_t data_length = data.size() * sizeof(float);
        result.insert(result.end(),
                     reinterpret_cast<uint8_t*>(&data_length),
                     reinterpret_cast<uint8_t*>(&data_length) + sizeof(data_length));
        result.insert(result.end(),
                     reinterpret_cast<const uint8_t*>(data.data()),
                     reinterpret_cast<const uint8_t*>(data.data()) + data_length);
    }
    
    return result;
}

std::map<std::string, std::vector<float>> GRPCClient::deserialize_weights(
    const std::vector<uint8_t>& data)
{
    std::map<std::string, std::vector<float>> result;
    
    if (data.size() < sizeof(uint32_t)) {
        return result;
    }
    
    size_t offset = 0;
    
    // Read number of tensors
    uint32_t num_tensors;
    std::memcpy(&num_tensors, data.data() + offset, sizeof(num_tensors));
    offset += sizeof(num_tensors);
    
    // Read each tensor
    for (uint32_t i = 0; i < num_tensors && offset < data.size(); ++i) {
        // Read name length
        uint32_t name_length;
        std::memcpy(&name_length, data.data() + offset, sizeof(name_length));
        offset += sizeof(name_length);
        
        // Read name
        std::string name(
            reinterpret_cast<const char*>(data.data() + offset),
            name_length
        );
        offset += name_length;
        
        // Read data length
        uint32_t data_length;
        std::memcpy(&data_length, data.data() + offset, sizeof(data_length));
        offset += sizeof(data_length);
        
        // Read data
        size_t num_floats = data_length / sizeof(float);
        std::vector<float> tensor_data(num_floats);
        std::memcpy(tensor_data.data(), data.data() + offset, data_length);
        offset += data_length;
        
        result[name] = std::move(tensor_data);
    }
    
    return result;
}

} // namespace meshml
