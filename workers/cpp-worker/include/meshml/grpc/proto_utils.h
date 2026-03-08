#pragma once

#include <torch/torch.h>
#include <string>
#include <vector>
#include <unordered_map>
#include <memory>

// Forward declarations of protobuf types
// These will be generated from parameter_server.proto
namespace meshml {
namespace proto {
    class WorkerInfo;
    class JobInfo;
    class HeartbeatRequest;
    class HeartbeatResponse;
    class TensorData;
    class GradientUpdate;
    class GradientUpdateResponse;
    class ParameterRequest;
    class ParameterResponse;
    class RegisterRequest;
    class RegisterResponse;
}
}

namespace meshml {
namespace grpc {

/**
 * @brief Utility class for converting between LibTorch tensors and Protobuf messages
 */
class ProtobufConverter {
public:
    /**
     * @brief Convert torch::Tensor to TensorData protobuf message
     * @param tensor Input tensor
     * @param compress Whether to compress the tensor data
     * @return TensorData protobuf message
     */
    static std::unique_ptr<proto::TensorData> tensor_to_proto(
        const torch::Tensor& tensor,
        bool compress = false
    );
    
    /**
     * @brief Convert TensorData protobuf message to torch::Tensor
     * @param tensor_data Input protobuf message
     * @return Reconstructed torch::Tensor
     */
    static torch::Tensor proto_to_tensor(const proto::TensorData& tensor_data);
    
    /**
     * @brief Convert map of tensors to protobuf GradientUpdate
     * @param worker_id Worker identifier
     * @param job_id Job identifier
     * @param iteration Current iteration number
     * @param gradients Map of parameter names to gradient tensors
     * @param batch_size Batch size used
     * @param compress Whether to compress gradient data
     * @return GradientUpdate protobuf message
     */
    static std::unique_ptr<proto::GradientUpdate> gradients_to_proto(
        const std::string& worker_id,
        const std::string& job_id,
        int64_t iteration,
        const std::unordered_map<std::string, torch::Tensor>& gradients,
        int32_t batch_size,
        bool compress = false
    );
    
    /**
     * @brief Convert ParameterResponse to map of tensors
     * @param response Protobuf response message
     * @return Map of parameter names to tensors
     */
    static std::unordered_map<std::string, torch::Tensor> proto_to_parameters(
        const proto::ParameterResponse& response
    );
    
    /**
     * @brief Create WorkerInfo protobuf message
     * @param worker_id Worker identifier
     * @param worker_type Worker type ("cpp" or "python")
     * @param device Device type ("cpu", "cuda", "mps")
     * @param memory_mb Available memory in MB
     * @param cpu_cores Number of CPU cores
     * @return WorkerInfo protobuf message
     */
    static std::unique_ptr<proto::WorkerInfo> create_worker_info(
        const std::string& worker_id,
        const std::string& worker_type,
        const std::string& device,
        int64_t memory_mb,
        int32_t cpu_cores
    );
    
    /**
     * @brief Create JobInfo protobuf message
     * @param job_id Job identifier
     * @param model_name Model name
     * @param total_samples Total number of samples
     * @param batch_size Batch size
     * @param num_epochs Number of epochs
     * @return JobInfo protobuf message
     */
    static std::unique_ptr<proto::JobInfo> create_job_info(
        const std::string& job_id,
        const std::string& model_name,
        int64_t total_samples,
        int32_t batch_size,
        int32_t num_epochs
    );
    
    /**
     * @brief Create HeartbeatRequest protobuf message
     * @param worker Worker information
     * @param job Job information
     * @param iteration Current iteration
     * @param loss Current loss value
     * @param accuracy Current accuracy value
     * @return HeartbeatRequest protobuf message
     */
    static std::unique_ptr<proto::HeartbeatRequest> create_heartbeat_request(
        const proto::WorkerInfo& worker,
        const proto::JobInfo& job,
        int64_t iteration,
        double loss,
        double accuracy
    );

private:
    // Internal helper methods
    static std::string dtype_to_string(torch::ScalarType dtype);
    static torch::ScalarType string_to_dtype(const std::string& dtype_str);
    static std::vector<uint8_t> compress_data(const std::vector<uint8_t>& data);
    static std::vector<uint8_t> decompress_data(const std::vector<uint8_t>& data);
};

/**
 * @brief Helper class for building protobuf messages
 */
class ProtoMessageBuilder {
public:
    /**
     * @brief Build a RegisterRequest message
     */
    static std::unique_ptr<proto::RegisterRequest> build_register_request(
        const std::string& worker_id,
        const std::string& worker_type = "cpp",
        const std::string& device = "cpu",
        int64_t memory_mb = 4096,
        int32_t cpu_cores = 4
    );
    
    /**
     * @brief Build a ParameterRequest message
     */
    static std::unique_ptr<proto::ParameterRequest> build_parameter_request(
        const std::string& worker_id,
        const std::string& job_id,
        const std::vector<std::string>& parameter_names = {}
    );
};

} // namespace grpc
} // namespace meshml
