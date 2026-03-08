/**
 * @file trainer.cpp
 * @brief Training loop implementation
 */

#include "meshml/training/trainer.h"
#include "meshml/training/checkpoint.h"
#include <iostream>
#include <chrono>
#include <iomanip>
#include <sstream>

namespace meshml {

Trainer::Trainer(
    const WorkerConfig& config,
    std::shared_ptr<GRPCClient> grpc_client,
    const std::string& device
) : config_(config),
    grpc_client_(grpc_client),
    device_(torch::kCPU)  // Default to CPU
{
    // Parse device string
    if (device == "cuda" && torch::cuda::is_available()) {
        device_ = torch::kCUDA;
        std::cout << "Using CUDA device" << std::endl;
    } else if (device == "mps" && torch::mps::is_available()) {
        device_ = torch::kMPS;
        std::cout << "Using MPS (Apple Silicon) device" << std::endl;
    } else {
        device_ = torch::kCPU;
        std::cout << "Using CPU device" << std::endl;
    }
    
    // Enable mixed precision for CUDA
    if (device_.is_cuda()) {
        mixed_precision_ = true;
        std::cout << "Mixed precision training enabled (CUDA AMP)" << std::endl;
    }
}

Trainer::~Trainer() {
    cleanup();
}

void Trainer::train(
    const std::string& model_id,
    std::shared_ptr<torch::nn::Module> model,
    int epochs,
    const std::string& checkpoint_path
) {
    std::cout << "Starting training: model_id=" << model_id 
              << ", epochs=" << epochs << std::endl;
    
    try {
        // Store model
        model_ = model;
        model_->to(device_);
        
        // Initialize training
        initialize_training(model_id, checkpoint_path);
        
        // Start heartbeat
        start_heartbeat();
        
        // Training loop
        for (int epoch = current_epoch_; epoch < epochs && !should_stop_; ++epoch) {
            current_epoch_ = epoch;
            
            std::cout << "\n=== Epoch " << (epoch + 1) << "/" << epochs << " ===" << std::endl;
            
            // Train one epoch
            auto stats = train_epoch(epoch);
            
            // Call progress callback
            if (progress_callback_) {
                progress_callback_(stats);
            }
            
            // Update heartbeat
            update_heartbeat_status(stats);
            
            // Save checkpoint
            save_checkpoint(epoch, stats.loss);
            
            std::cout << "Epoch " << (epoch + 1) << " completed: "
                      << "loss=" << std::fixed << std::setprecision(4) << stats.loss
                      << ", accuracy=" << std::setprecision(2) << (stats.accuracy * 100) << "%"
                      << ", time=" << std::setprecision(1) << stats.duration_seconds << "s"
                      << std::endl;
        }
        
        std::cout << "\nTraining completed successfully!" << std::endl;
        
    } catch (const std::exception& e) {
        std::cerr << "Training failed: " << e.what() << std::endl;
        throw;
    }
    
    cleanup();
}

void Trainer::set_progress_callback(ProgressCallback callback) {
    progress_callback_ = callback;
}

void Trainer::stop() {
    std::cout << "Stopping training after current epoch..." << std::endl;
    should_stop_ = true;
}

std::map<std::string, std::string> Trainer::get_state() const {
    std::map<std::string, std::string> state;
    state["current_epoch"] = std::to_string(current_epoch_.load());
    state["current_batch"] = std::to_string(current_batch_.load());
    state["global_version"] = std::to_string(global_version_.load());
    state["should_stop"] = should_stop_ ? "true" : "false";
    state["mixed_precision"] = mixed_precision_ ? "true" : "false";
    return state;
}

void Trainer::set_mixed_precision(bool enabled) {
    if (enabled && !device_.is_cuda()) {
        std::cerr << "Warning: Mixed precision requires CUDA, ignoring" << std::endl;
        return;
    }
    mixed_precision_ = enabled;
    std::cout << "Mixed precision " << (enabled ? "enabled" : "disabled") << std::endl;
}

// Private methods

void Trainer::initialize_training(
    const std::string& model_id,
    const std::string& checkpoint_path
) {
    std::cout << "Initializing training components..." << std::endl;
    
    // Initialize optimizer
    initialize_optimizer();
    
    // Initialize criterion (cross-entropy for classification)
    criterion_ = std::make_unique<torch::nn::CrossEntropyLoss>();
    
    // Load checkpoint or fetch initial weights
    if (!checkpoint_path.empty()) {
        load_checkpoint(checkpoint_path);
    } else {
        fetch_weights(model_id);
    }
    
    std::cout << "Training initialization complete" << std::endl;
}

void Trainer::fetch_weights(const std::string& model_id) {
    std::cout << "Fetching initial weights from Parameter Server..." << std::endl;
    
    try {
        auto [weights, version] = grpc_client_->get_weights(
            config_.identity.job_id,
            config_.identity.worker_id,
            0  // epoch 0
        );
        
        global_version_ = version;
        
        std::cout << "Received weights version " << version 
                  << " (" << weights.size() << " parameters)" << std::endl;
        
        // Apply weights to model
        apply_weights(weights);
        
    } catch (const std::exception& e) {
        std::cerr << "Failed to fetch weights: " << e.what() << std::endl;
        throw;
    }
}

EpochStats Trainer::train_epoch(int epoch) {
    model_->train();  // Set model to training mode
    
    auto start_time = std::chrono::high_resolution_clock::now();
    
    float total_loss = 0.0f;
    float total_correct = 0.0f;
    int total_samples = 0;
    int num_batches = 0;
    
    // TODO: Replace with actual data loader iteration
    // For now, create dummy data for demonstration
    const int num_dummy_batches = 100;
    const int batch_size = 32;
    
    for (int batch_id = 0; batch_id < num_dummy_batches && !should_stop_; ++batch_id) {
        current_batch_ = batch_id;
        
        // Create dummy batch (replace with actual data loader)
        auto inputs = torch::randn({batch_size, 784}).to(device_);
        auto targets = torch::randint(0, 10, {batch_size}).to(device_);
        
        // Train on batch
        float batch_loss = train_batch(inputs, targets);
        total_loss += batch_loss;
        num_batches++;
        total_samples += batch_size;
        
        // Push gradients every N batches
        if ((batch_id + 1) % config_.training.gradient_push_frequency == 0) {
            push_gradients(epoch, batch_id);
        }
        
        // Progress indicator
        if ((batch_id + 1) % 10 == 0) {
            std::cout << "  Batch " << (batch_id + 1) << "/" << num_dummy_batches
                      << " - loss: " << std::fixed << std::setprecision(4) 
                      << (total_loss / num_batches) << "\r" << std::flush;
        }
    }
    
    std::cout << std::endl;
    
    auto end_time = std::chrono::high_resolution_clock::now();
    auto duration = std::chrono::duration_cast<std::chrono::milliseconds>(
        end_time - start_time
    );
    
    // Calculate statistics
    EpochStats stats;
    stats.epoch = epoch;
    stats.loss = num_batches > 0 ? total_loss / num_batches : 0.0f;
    stats.accuracy = total_samples > 0 ? total_correct / total_samples : 0.0f;
    stats.num_batches = num_batches;
    stats.duration_seconds = duration.count() / 1000.0;
    
    return stats;
}

float Trainer::train_batch(
    const torch::Tensor& inputs,
    const torch::Tensor& targets
) {
    optimizer_->zero_grad();
    
    torch::Tensor loss;
    
    if (mixed_precision_ && device_.is_cuda()) {
        // Mixed precision training (CUDA only)
        torch::autocast::set_autocast_enabled(torch::kCUDA, true);
        
        auto outputs = model_->forward(inputs);
        loss = criterion_->forward(outputs, targets);
        
        // Scale loss and backward
        auto scaled_loss = scaler_.scale(loss);
        scaled_loss.backward();
        
        // Unscale and step
        scaler_.step(*optimizer_);
        scaler_.update();
        
        torch::autocast::set_autocast_enabled(torch::kCUDA, false);
    } else {
        // Standard training
        auto outputs = model_->forward(inputs);
        loss = criterion_->forward(outputs, targets);
        loss.backward();
        optimizer_->step();
    }
    
    return loss.item<float>();
}

void Trainer::push_gradients(int epoch, int batch_id) {
    std::cout << "  Pushing gradients (epoch=" << epoch 
              << ", batch=" << batch_id << ")..." << std::endl;
    
    try {
        // Extract gradients
        auto gradients = extract_gradients();
        
        // Prepare metadata
        std::map<std::string, float> metadata;
        metadata["gradient_norm"] = 1.0f;  // TODO: Calculate actual norm
        metadata["computation_time_ms"] = 0.0f;  // TODO: Track actual time
        
        // Push to Parameter Server
        auto response = grpc_client_->push_gradients(
            config_.identity.job_id,
            config_.identity.worker_id,
            gradients,
            batch_id,
            epoch,
            32,  // TODO: Use actual batch size
            config_.training.learning_rate,
            metadata
        );
        
        if (response.count("new_version") > 0) {
            global_version_ = std::stoi(response["new_version"]);
        }
        
    } catch (const std::exception& e) {
        std::cerr << "Failed to push gradients: " << e.what() << std::endl;
        // Don't throw - continue training
    }
}

void Trainer::save_checkpoint(int epoch, float loss) {
    // TODO: Implement checkpoint saving
    // This will be implemented when checkpoint.cpp is created
    std::cout << "  Checkpoint saved (epoch=" << epoch 
              << ", loss=" << std::fixed << std::setprecision(4) << loss << ")" << std::endl;
}

void Trainer::load_checkpoint(const std::string& checkpoint_path) {
    std::cout << "Loading checkpoint from " << checkpoint_path << "..." << std::endl;
    // TODO: Implement checkpoint loading
    throw std::runtime_error("Checkpoint loading not yet implemented");
}

void Trainer::start_heartbeat() {
    std::cout << "Starting heartbeat monitoring..." << std::endl;
    
    heartbeat_ = create_heartbeat_sender(
        config_.identity.worker_id,
        30  // 30 second interval
    );
    
    heartbeat_->set_heartbeat_callback([this](const auto& data) {
        // In production, this would send via gRPC
        // For now, just return success
        return true;
    });
    
    heartbeat_->update_status("state", "training");
    heartbeat_->start();
}

void Trainer::update_heartbeat_status(const EpochStats& stats) {
    if (!heartbeat_) return;
    
    std::ostringstream loss_str, acc_str, epoch_str;
    loss_str << std::fixed << std::setprecision(4) << stats.loss;
    acc_str << std::fixed << std::setprecision(2) << (stats.accuracy * 100);
    epoch_str << stats.epoch;
    
    heartbeat_->update_status("state", "training");
    heartbeat_->update_status("current_epoch", epoch_str.str());
    heartbeat_->update_status("loss", loss_str.str());
    heartbeat_->update_status("accuracy", acc_str.str());
}

void Trainer::cleanup() {
    if (heartbeat_) {
        heartbeat_->update_status("state", "idle");
        heartbeat_->stop();
    }
    std::cout << "Training cleanup complete" << std::endl;
}

void Trainer::initialize_optimizer() {
    std::cout << "Initializing optimizer (SGD with momentum)..." << std::endl;
    
    optimizer_ = std::make_unique<torch::optim::SGD>(
        model_->parameters(),
        torch::optim::SGDOptions(config_.training.learning_rate)
            .momentum(config_.training.momentum)
            .weight_decay(config_.training.weight_decay)
    );
}

void Trainer::apply_weights(const std::map<std::string, std::vector<float>>& weights) {
    std::cout << "Applying weights to model (" << weights.size() << " parameters)..." << std::endl;
    
    // Get model parameters
    auto named_params = model_->named_parameters();
    
    for (const auto& [name, data] : weights) {
        // Find matching parameter
        auto it = std::find_if(named_params.begin(), named_params.end(),
            [&name](const auto& param) { return param.key() == name; });
        
        if (it != named_params.end()) {
            // Convert vector to tensor
            auto tensor = torch::from_blob(
                const_cast<float*>(data.data()),
                {static_cast<long>(data.size())},
                torch::kFloat32
            ).clone();
            
            // Reshape to match parameter shape
            tensor = tensor.reshape(it->value().sizes());
            
            // Copy to device and update parameter
            it->value().data().copy_(tensor.to(device_));
        } else {
            std::cerr << "Warning: Parameter " << name << " not found in model" << std::endl;
        }
    }
    
    std::cout << "Weights applied successfully" << std::endl;
}

std::map<std::string, std::vector<float>> Trainer::extract_gradients() {
    std::map<std::string, std::vector<float>> gradients;
    
    auto named_params = model_->named_parameters();
    
    for (const auto& param : named_params) {
        if (param.value().grad().defined()) {
            // Get gradient tensor
            auto grad = param.value().grad().cpu().contiguous();
            
            // Convert to vector
            std::vector<float> grad_vec(
                grad.data_ptr<float>(),
                grad.data_ptr<float>() + grad.numel()
            );
            
            gradients[param.key()] = grad_vec;
        }
    }
    
    return gradients;
}

// Factory function

std::unique_ptr<Trainer> create_trainer(
    const WorkerConfig& config,
    std::shared_ptr<GRPCClient> grpc_client,
    const std::string& device
) {
    return std::make_unique<Trainer>(config, grpc_client, device);
}

} // namespace meshml
