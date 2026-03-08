/**
 * @file trainer.h
 * @brief Training loop implementation for C++ Worker
 * 
 * Features:
 * - LibTorch tensor operations
 * - Autograd for gradient computation
 * - Data loading and batching
 * - Checkpoint management
 * - Progress tracking
 * - Integration with gRPC client
 * - Mixed precision training (AMP)
 * - Memory optimization
 */

#pragma once

#include <torch/torch.h>
#include <memory>
#include <string>
#include <vector>
#include <map>
#include <functional>
#include <atomic>

#include "meshml/config.h"
#include "meshml/grpc/client.h"
#include "meshml/grpc/heartbeat.h"

namespace meshml {

/**
 * @brief Training statistics for one epoch
 */
struct EpochStats {
    int epoch;
    float loss;
    float accuracy;
    int num_batches;
    double duration_seconds;
    std::map<std::string, float> additional_metrics;
};

/**
 * @brief Training progress callback
 * 
 * Called periodically during training with current statistics
 */
using ProgressCallback = std::function<void(const EpochStats&)>;

/**
 * @brief Main trainer class
 * 
 * Handles the complete training loop:
 * 1. Initialize model and data
 * 2. Fetch initial weights from Parameter Server
 * 3. Train for specified epochs
 * 4. Compute gradients and push to Parameter Server
 * 5. Save checkpoints periodically
 * 6. Monitor progress via heartbeat
 */
class Trainer {
public:
    /**
     * @brief Construct a new Trainer
     * 
     * @param config Worker configuration
     * @param grpc_client gRPC client for Parameter Server communication
     * @param device Training device (cpu, cuda, mps)
     */
    Trainer(
        const WorkerConfig& config,
        std::shared_ptr<GRPCClient> grpc_client,
        const std::string& device = "cpu"
    );
    
    ~Trainer();
    
    /**
     * @brief Start training on a model
     * 
     * @param model_id Model identifier
     * @param model Model instance (shared_ptr to allow moving)
     * @param epochs Number of epochs to train
     * @param checkpoint_path Optional checkpoint to resume from
     */
    void train(
        const std::string& model_id,
        std::shared_ptr<torch::nn::Module> model,
        int epochs,
        const std::string& checkpoint_path = ""
    );
    
    /**
     * @brief Set progress callback
     * 
     * @param callback Function to call with epoch statistics
     */
    void set_progress_callback(ProgressCallback callback);
    
    /**
     * @brief Stop training gracefully
     * 
     * Sets a flag to stop after current epoch completes
     */
    void stop();
    
    /**
     * @brief Get current training state
     * 
     * @return Map with state information
     */
    std::map<std::string, std::string> get_state() const;
    
    /**
     * @brief Enable/disable mixed precision training
     * 
     * @param enabled True to enable AMP
     */
    void set_mixed_precision(bool enabled);
    
private:
    // Configuration
    WorkerConfig config_;
    std::shared_ptr<GRPCClient> grpc_client_;
    torch::Device device_;
    
    // Model components
    std::shared_ptr<torch::nn::Module> model_;
    std::unique_ptr<torch::optim::Optimizer> optimizer_;
    std::unique_ptr<torch::nn::Module> criterion_;
    
    // Training state
    std::atomic<int> current_epoch_{0};
    std::atomic<int> current_batch_{0};
    std::atomic<int> global_version_{0};
    std::atomic<bool> should_stop_{false};
    
    // Data loaders
    std::unique_ptr<torch::data::DataLoader<>> train_loader_;
    
    // Heartbeat
    std::unique_ptr<HeartbeatSender> heartbeat_;
    
    // Progress tracking
    ProgressCallback progress_callback_;
    
    // Mixed precision
    bool mixed_precision_{false};
    torch::cuda::amp::GradScaler scaler_;
    
    // Helper methods
    
    /**
     * @brief Initialize training components
     */
    void initialize_training(
        const std::string& model_id,
        const std::string& checkpoint_path
    );
    
    /**
     * @brief Load model weights from Parameter Server
     */
    void fetch_weights(const std::string& model_id);
    
    /**
     * @brief Train one epoch
     * 
     * @return Epoch statistics
     */
    EpochStats train_epoch(int epoch);
    
    /**
     * @brief Train one batch
     * 
     * @param inputs Input tensors
     * @param targets Target tensors
     * @return Batch loss
     */
    float train_batch(
        const torch::Tensor& inputs,
        const torch::Tensor& targets
    );
    
    /**
     * @brief Compute and push gradients to Parameter Server
     * 
     * @param epoch Current epoch
     * @param batch_id Current batch ID
     */
    void push_gradients(int epoch, int batch_id);
    
    /**
     * @brief Save checkpoint
     * 
     * @param epoch Current epoch
     * @param loss Current loss
     */
    void save_checkpoint(int epoch, float loss);
    
    /**
     * @brief Load checkpoint
     * 
     * @param checkpoint_path Path to checkpoint file
     */
    void load_checkpoint(const std::string& checkpoint_path);
    
    /**
     * @brief Start heartbeat monitoring
     */
    void start_heartbeat();
    
    /**
     * @brief Update heartbeat status
     * 
     * @param stats Epoch statistics
     */
    void update_heartbeat_status(const EpochStats& stats);
    
    /**
     * @brief Cleanup resources
     */
    void cleanup();
    
    /**
     * @brief Initialize optimizer (SGD, Adam, etc.)
     */
    void initialize_optimizer();
    
    /**
     * @brief Apply weights to model
     * 
     * @param weights Map of parameter name to tensor data
     */
    void apply_weights(const std::map<std::string, std::vector<float>>& weights);
    
    /**
     * @brief Extract gradients from model
     * 
     * @return Map of parameter name to gradient data
     */
    std::map<std::string, std::vector<float>> extract_gradients();
};

/**
 * @brief Create a trainer instance
 * 
 * Helper function for RAII and smart pointer management
 * 
 * @param config Worker configuration
 * @param grpc_client gRPC client
 * @param device Training device
 * @return Unique pointer to trainer
 */
std::unique_ptr<Trainer> create_trainer(
    const WorkerConfig& config,
    std::shared_ptr<GRPCClient> grpc_client,
    const std::string& device = "cpu"
);

} // namespace meshml
