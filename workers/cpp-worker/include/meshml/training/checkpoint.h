/**
 * @file checkpoint.h
 * @brief Checkpoint management for model state persistence
 * 
 * Features:
 * - Save/load model state
 * - Optimizer state persistence
 * - Training state tracking
 * - Versioned checkpoints
 * - Automatic cleanup of old checkpoints
 */

#pragma once

#include <torch/torch.h>
#include <string>
#include <vector>
#include <map>
#include <memory>

namespace meshml {

/**
 * @brief Checkpoint metadata
 */
struct CheckpointMetadata {
    std::string model_id;
    int epoch;
    float loss;
    float accuracy;
    int global_version;
    std::string timestamp;
    std::map<std::string, std::string> custom_fields;
};

/**
 * @brief Checkpoint manager
 * 
 * Handles saving and loading model checkpoints with state management
 */
class CheckpointManager {
public:
    /**
     * @brief Construct checkpoint manager
     * 
     * @param checkpoint_dir Directory to store checkpoints
     * @param model_id Model identifier
     * @param max_checkpoints Maximum number of checkpoints to keep (0 = unlimited)
     */
    CheckpointManager(
        const std::string& checkpoint_dir,
        const std::string& model_id,
        int max_checkpoints = 5
    );
    
    /**
     * @brief Save a checkpoint
     * 
     * @param model Model to save
     * @param optimizer Optimizer to save
     * @param epoch Current epoch
     * @param loss Current loss
     * @param accuracy Current accuracy
     * @param global_version Parameter Server version
     * @return Path to saved checkpoint
     */
    std::string save_checkpoint(
        const torch::nn::Module& model,
        const torch::optim::Optimizer* optimizer,
        int epoch,
        float loss,
        float accuracy = 0.0f,
        int global_version = 0
    );
    
    /**
     * @brief Load a checkpoint
     * 
     * @param checkpoint_path Path to checkpoint file
     * @param model Model to load state into
     * @param optimizer Optional optimizer to load state into
     * @return Checkpoint metadata
     */
    CheckpointMetadata load_checkpoint(
        const std::string& checkpoint_path,
        torch::nn::Module& model,
        torch::optim::Optimizer* optimizer = nullptr
    );
    
    /**
     * @brief Get latest checkpoint path
     * 
     * @return Path to most recent checkpoint, or empty string if none
     */
    std::string get_latest_checkpoint() const;
    
    /**
     * @brief List all checkpoints for this model
     * 
     * @return Vector of checkpoint paths, sorted by epoch (newest first)
     */
    std::vector<std::string> list_checkpoints() const;
    
    /**
     * @brief Delete old checkpoints beyond max_checkpoints
     */
    void cleanup_old_checkpoints();
    
    /**
     * @brief Delete all checkpoints for this model
     */
    void delete_all_checkpoints();
    
    /**
     * @brief Check if checkpoint exists
     * 
     * @param checkpoint_path Path to check
     * @return True if file exists and is valid
     */
    bool checkpoint_exists(const std::string& checkpoint_path) const;
    
    /**
     * @brief Get checkpoint metadata without loading full state
     * 
     * @param checkpoint_path Path to checkpoint
     * @return Metadata
     */
    CheckpointMetadata get_checkpoint_metadata(
        const std::string& checkpoint_path
    ) const;
    
private:
    std::string checkpoint_dir_;
    std::string model_id_;
    int max_checkpoints_;
    
    /**
     * @brief Generate checkpoint filename
     * 
     * @param epoch Epoch number
     * @return Filename (e.g., "model_epoch_42.pt")
     */
    std::string generate_checkpoint_filename(int epoch) const;
    
    /**
     * @brief Parse epoch from checkpoint filename
     * 
     * @param filename Checkpoint filename
     * @return Epoch number, or -1 if invalid
     */
    int parse_epoch_from_filename(const std::string& filename) const;
};

/**
 * @brief Auto-checkpoint saver
 * 
 * Automatically saves checkpoints based on conditions
 */
class AutoCheckpoint {
public:
    /**
     * @brief Construct auto-checkpoint
     * 
     * @param manager Checkpoint manager
     * @param save_every_n_epochs Save every N epochs
     * @param save_on_improvement Save when loss improves
     */
    AutoCheckpoint(
        std::shared_ptr<CheckpointManager> manager,
        int save_every_n_epochs = 1,
        bool save_on_improvement = true
    );
    
    /**
     * @brief Check if should save checkpoint
     * 
     * @param epoch Current epoch
     * @param loss Current loss
     * @return True if should save
     */
    bool should_save(int epoch, float loss);
    
    /**
     * @brief Record that checkpoint was saved
     * 
     * @param epoch Epoch that was saved
     * @param loss Loss value
     */
    void record_save(int epoch, float loss);
    
    /**
     * @brief Get best loss seen so far
     */
    float get_best_loss() const { return best_loss_; }
    
private:
    std::shared_ptr<CheckpointManager> manager_;
    int save_every_n_epochs_;
    bool save_on_improvement_;
    float best_loss_{std::numeric_limits<float>::max()};
    int last_saved_epoch_{-1};
};

/**
 * @brief Create a checkpoint manager
 * 
 * @param checkpoint_dir Directory for checkpoints
 * @param model_id Model identifier
 * @param max_checkpoints Maximum checkpoints to keep
 * @return Shared pointer to manager
 */
std::shared_ptr<CheckpointManager> create_checkpoint_manager(
    const std::string& checkpoint_dir,
    const std::string& model_id,
    int max_checkpoints = 5
);

} // namespace meshml
