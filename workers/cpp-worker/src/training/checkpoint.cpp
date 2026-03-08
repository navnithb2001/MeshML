/**
 * @file checkpoint.cpp
 * @brief Checkpoint management implementation
 */

#include "meshml/training/checkpoint.h"
#include <torch/torch.h>
#include <iostream>
#include <fstream>
#include <filesystem>
#include <algorithm>
#include <chrono>
#include <iomanip>
#include <sstream>

namespace fs = std::filesystem;

namespace meshml {

// CheckpointManager implementation

CheckpointManager::CheckpointManager(
    const std::string& checkpoint_dir,
    const std::string& model_id,
    int max_checkpoints
) : checkpoint_dir_(checkpoint_dir),
    model_id_(model_id),
    max_checkpoints_(max_checkpoints)
{
    // Create checkpoint directory if it doesn't exist
    fs::create_directories(checkpoint_dir_);
    
    std::cout << "CheckpointManager initialized: dir=" << checkpoint_dir_
              << ", model=" << model_id
              << ", max_checkpoints=" << max_checkpoints << std::endl;
}

std::string CheckpointManager::save_checkpoint(
    const torch::nn::Module& model,
    const torch::optim::Optimizer* optimizer,
    int epoch,
    float loss,
    float accuracy,
    int global_version
) {
    std::string filename = generate_checkpoint_filename(epoch);
    std::string filepath = checkpoint_dir_ + "/" + filename;
    
    std::cout << "Saving checkpoint to " << filepath << "..." << std::endl;
    
    try {
        // Create checkpoint dict
        torch::serialize::OutputArchive archive;
        
        // Save model state
        model.save(archive);
        
        // Save optimizer state if provided
        if (optimizer) {
            torch::serialize::OutputArchive optimizer_archive;
            optimizer->save(optimizer_archive);
            archive.write("optimizer_state", optimizer_archive);
        }
        
        // Save metadata
        archive.write("epoch", torch::tensor(epoch));
        archive.write("loss", torch::tensor(loss));
        archive.write("accuracy", torch::tensor(accuracy));
        archive.write("global_version", torch::tensor(global_version));
        
        // Get timestamp
        auto now = std::chrono::system_clock::now();
        auto time_t = std::chrono::system_clock::to_time_t(now);
        std::stringstream timestamp;
        timestamp << std::put_time(std::localtime(&time_t), "%Y-%m-%d %H:%M:%S");
        
        // Save timestamp as string (convert to tensor of chars)
        std::string ts_str = timestamp.str();
        std::vector<int64_t> ts_chars(ts_str.begin(), ts_str.end());
        archive.write("timestamp", torch::tensor(ts_chars));
        
        // Write to file
        archive.save_to(filepath);
        
        std::cout << "Checkpoint saved: epoch=" << epoch 
                  << ", loss=" << std::fixed << std::setprecision(4) << loss
                  << ", accuracy=" << std::setprecision(2) << (accuracy * 100) << "%"
                  << std::endl;
        
        // Cleanup old checkpoints
        cleanup_old_checkpoints();
        
        return filepath;
        
    } catch (const std::exception& e) {
        std::cerr << "Failed to save checkpoint: " << e.what() << std::endl;
        throw;
    }
}

CheckpointMetadata CheckpointManager::load_checkpoint(
    const std::string& checkpoint_path,
    torch::nn::Module& model,
    torch::optim::Optimizer* optimizer
) {
    std::cout << "Loading checkpoint from " << checkpoint_path << "..." << std::endl;
    
    if (!checkpoint_exists(checkpoint_path)) {
        throw std::runtime_error("Checkpoint file not found: " + checkpoint_path);
    }
    
    try {
        torch::serialize::InputArchive archive;
        archive.load_from(checkpoint_path);
        
        // Load model state
        model.load(archive);
        
        // Load optimizer state if provided
        if (optimizer) {
            torch::serialize::InputArchive optimizer_archive;
            archive.read("optimizer_state", optimizer_archive);
            optimizer->load(optimizer_archive);
        }
        
        // Load metadata
        torch::Tensor epoch_tensor, loss_tensor, accuracy_tensor, version_tensor;
        archive.read("epoch", epoch_tensor);
        archive.read("loss", loss_tensor);
        archive.read("accuracy", accuracy_tensor);
        archive.read("global_version", version_tensor);
        
        // Load timestamp
        torch::Tensor timestamp_tensor;
        archive.read("timestamp", timestamp_tensor);
        
        std::vector<char> ts_chars;
        for (int i = 0; i < timestamp_tensor.numel(); ++i) {
            ts_chars.push_back(static_cast<char>(timestamp_tensor[i].item<int64_t>()));
        }
        std::string timestamp(ts_chars.begin(), ts_chars.end());
        
        // Create metadata
        CheckpointMetadata metadata;
        metadata.model_id = model_id_;
        metadata.epoch = epoch_tensor.item<int>();
        metadata.loss = loss_tensor.item<float>();
        metadata.accuracy = accuracy_tensor.item<float>();
        metadata.global_version = version_tensor.item<int>();
        metadata.timestamp = timestamp;
        
        std::cout << "Checkpoint loaded: epoch=" << metadata.epoch
                  << ", loss=" << std::fixed << std::setprecision(4) << metadata.loss
                  << ", accuracy=" << std::setprecision(2) << (metadata.accuracy * 100) << "%"
                  << std::endl;
        
        return metadata;
        
    } catch (const std::exception& e) {
        std::cerr << "Failed to load checkpoint: " << e.what() << std::endl;
        throw;
    }
}

std::string CheckpointManager::get_latest_checkpoint() const {
    auto checkpoints = list_checkpoints();
    
    if (checkpoints.empty()) {
        return "";
    }
    
    return checkpoints[0];  // Already sorted by epoch (newest first)
}

std::vector<std::string> CheckpointManager::list_checkpoints() const {
    std::vector<std::string> checkpoints;
    
    if (!fs::exists(checkpoint_dir_)) {
        return checkpoints;
    }
    
    // Iterate through checkpoint directory
    for (const auto& entry : fs::directory_iterator(checkpoint_dir_)) {
        if (entry.is_regular_file()) {
            std::string filename = entry.path().filename().string();
            
            // Check if filename matches pattern
            if (filename.find(model_id_) != std::string::npos &&
                filename.find("_epoch_") != std::string::npos &&
                filename.find(".pt") != std::string::npos) {
                
                checkpoints.push_back(entry.path().string());
            }
        }
    }
    
    // Sort by epoch (newest first)
    std::sort(checkpoints.begin(), checkpoints.end(),
        [this](const std::string& a, const std::string& b) {
            int epoch_a = parse_epoch_from_filename(fs::path(a).filename().string());
            int epoch_b = parse_epoch_from_filename(fs::path(b).filename().string());
            return epoch_a > epoch_b;
        });
    
    return checkpoints;
}

void CheckpointManager::cleanup_old_checkpoints() {
    if (max_checkpoints_ <= 0) {
        return;  // Unlimited checkpoints
    }
    
    auto checkpoints = list_checkpoints();
    
    // Delete checkpoints beyond max_checkpoints_
    for (size_t i = max_checkpoints_; i < checkpoints.size(); ++i) {
        std::cout << "Deleting old checkpoint: " << checkpoints[i] << std::endl;
        
        try {
            fs::remove(checkpoints[i]);
        } catch (const std::exception& e) {
            std::cerr << "Failed to delete checkpoint: " << e.what() << std::endl;
        }
    }
}

void CheckpointManager::delete_all_checkpoints() {
    auto checkpoints = list_checkpoints();
    
    std::cout << "Deleting all checkpoints (" << checkpoints.size() << ")..." << std::endl;
    
    for (const auto& checkpoint : checkpoints) {
        try {
            fs::remove(checkpoint);
        } catch (const std::exception& e) {
            std::cerr << "Failed to delete checkpoint: " << e.what() << std::endl;
        }
    }
}

bool CheckpointManager::checkpoint_exists(const std::string& checkpoint_path) const {
    return fs::exists(checkpoint_path) && fs::is_regular_file(checkpoint_path);
}

CheckpointMetadata CheckpointManager::get_checkpoint_metadata(
    const std::string& checkpoint_path
) const {
    if (!checkpoint_exists(checkpoint_path)) {
        throw std::runtime_error("Checkpoint file not found: " + checkpoint_path);
    }
    
    try {
        torch::serialize::InputArchive archive;
        archive.load_from(checkpoint_path);
        
        // Load metadata only
        torch::Tensor epoch_tensor, loss_tensor, accuracy_tensor, version_tensor;
        archive.read("epoch", epoch_tensor);
        archive.read("loss", loss_tensor);
        archive.read("accuracy", accuracy_tensor);
        archive.read("global_version", version_tensor);
        
        // Load timestamp
        torch::Tensor timestamp_tensor;
        archive.read("timestamp", timestamp_tensor);
        
        std::vector<char> ts_chars;
        for (int i = 0; i < timestamp_tensor.numel(); ++i) {
            ts_chars.push_back(static_cast<char>(timestamp_tensor[i].item<int64_t>()));
        }
        std::string timestamp(ts_chars.begin(), ts_chars.end());
        
        // Create metadata
        CheckpointMetadata metadata;
        metadata.model_id = model_id_;
        metadata.epoch = epoch_tensor.item<int>();
        metadata.loss = loss_tensor.item<float>();
        metadata.accuracy = accuracy_tensor.item<float>();
        metadata.global_version = version_tensor.item<int>();
        metadata.timestamp = timestamp;
        
        return metadata;
        
    } catch (const std::exception& e) {
        std::cerr << "Failed to read checkpoint metadata: " << e.what() << std::endl;
        throw;
    }
}

std::string CheckpointManager::generate_checkpoint_filename(int epoch) const {
    std::ostringstream oss;
    oss << model_id_ << "_epoch_" << std::setw(4) << std::setfill('0') << epoch << ".pt";
    return oss.str();
}

int CheckpointManager::parse_epoch_from_filename(const std::string& filename) const {
    // Extract epoch from filename like "model_epoch_0042.pt"
    size_t pos = filename.find("_epoch_");
    
    if (pos == std::string::npos) {
        return -1;
    }
    
    pos += 7;  // Length of "_epoch_"
    
    // Find end of epoch number
    size_t end_pos = filename.find(".pt", pos);
    
    if (end_pos == std::string::npos) {
        return -1;
    }
    
    try {
        std::string epoch_str = filename.substr(pos, end_pos - pos);
        return std::stoi(epoch_str);
    } catch (...) {
        return -1;
    }
}

// AutoCheckpoint implementation

AutoCheckpoint::AutoCheckpoint(
    std::shared_ptr<CheckpointManager> manager,
    int save_every_n_epochs,
    bool save_on_improvement
) : manager_(manager),
    save_every_n_epochs_(save_every_n_epochs),
    save_on_improvement_(save_on_improvement)
{
    std::cout << "AutoCheckpoint initialized: save_every=" << save_every_n_epochs
              << ", save_on_improvement=" << save_on_improvement << std::endl;
}

bool AutoCheckpoint::should_save(int epoch, float loss) {
    // Check if should save based on epoch frequency
    bool epoch_trigger = (epoch + 1) % save_every_n_epochs_ == 0;
    
    // Check if should save based on improvement
    bool improvement_trigger = save_on_improvement_ && (loss < best_loss_);
    
    return epoch_trigger || improvement_trigger;
}

void AutoCheckpoint::record_save(int epoch, float loss) {
    last_saved_epoch_ = epoch;
    
    if (loss < best_loss_) {
        best_loss_ = loss;
        std::cout << "New best loss: " << std::fixed << std::setprecision(4) 
                  << best_loss_ << std::endl;
    }
}

// Factory function

std::shared_ptr<CheckpointManager> create_checkpoint_manager(
    const std::string& checkpoint_dir,
    const std::string& model_id,
    int max_checkpoints
) {
    return std::make_shared<CheckpointManager>(
        checkpoint_dir,
        model_id,
        max_checkpoints
    );
}

} // namespace meshml
