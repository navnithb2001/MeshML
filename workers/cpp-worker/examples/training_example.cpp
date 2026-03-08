/**
 * @file training_example.cpp
 * @brief Example demonstrating C++ training loop usage
 * 
 * Shows how to:
 * - Create a simple model
 * - Configure the trainer
 * - Run training with progress callbacks
 * - Save and load checkpoints
 */

#include <torch/torch.h>
#include "meshml/config.h"
#include "meshml/grpc/client.h"
#include "meshml/training/trainer.h"
#include "meshml/training/data_loader.h"
#include "meshml/training/checkpoint.h"
#include <iostream>
#include <memory>

using namespace meshml;

/**
 * @brief Simple neural network for MNIST classification
 */
struct SimpleNet : torch::nn::Module {
    SimpleNet() {
        fc1 = register_module("fc1", torch::nn::Linear(784, 128));
        fc2 = register_module("fc2", torch::nn::Linear(128, 64));
        fc3 = register_module("fc3", torch::nn::Linear(64, 10));
    }
    
    torch::Tensor forward(torch::Tensor x) {
        x = x.view({-1, 784});  // Flatten
        x = torch::relu(fc1->forward(x));
        x = torch::relu(fc2->forward(x));
        x = fc3->forward(x);
        return x;
    }
    
    torch::nn::Linear fc1{nullptr}, fc2{nullptr}, fc3{nullptr};
};

int main() {
    std::cout << "=== C++ Worker Training Example ===" << std::endl;
    
    // 1. Configure worker
    WorkerConfig config;
    config.identity.worker_id = "cpp-worker-001";
    config.identity.job_id = "example-job-123";
    
    config.training.learning_rate = 0.01f;
    config.training.batch_size = 32;
    config.training.num_epochs = 10;
    config.training.momentum = 0.9f;
    config.training.weight_decay = 0.0001f;
    config.training.gradient_push_frequency = 10;
    config.training.mixed_precision = false;
    
    config.storage.base_dir = "/tmp/meshml-cpp-worker";
    config.storage.data_dir = config.storage.base_dir + "/data";
    config.storage.models_dir = config.storage.base_dir + "/models";
    config.storage.checkpoints_dir = config.storage.base_dir + "/checkpoints";
    
    std::cout << "\nWorker Configuration:" << std::endl;
    std::cout << "  Worker ID: " << config.identity.worker_id << std::endl;
    std::cout << "  Job ID: " << config.identity.job_id << std::endl;
    std::cout << "  Learning Rate: " << config.training.learning_rate << std::endl;
    std::cout << "  Batch Size: " << config.training.batch_size << std::endl;
    std::cout << "  Epochs: " << config.training.num_epochs << std::endl;
    
    // 2. Create gRPC client
    auto grpc_client = std::make_shared<GRPCClient>(
        "localhost:50051",
        30  // timeout
    );
    
    if (!grpc_client->connect()) {
        std::cerr << "Failed to connect to Parameter Server" << std::endl;
        return 1;
    }
    
    std::cout << "\nConnected to Parameter Server" << std::endl;
    
    // 3. Create model
    auto model = std::make_shared<SimpleNet>();
    std::cout << "\nModel created: SimpleNet (784 -> 128 -> 64 -> 10)" << std::endl;
    
    // Print model summary
    std::cout << "\nModel Parameters:" << std::endl;
    size_t total_params = 0;
    for (const auto& param : model->named_parameters()) {
        auto sizes = param.value().sizes();
        size_t param_count = param.value().numel();
        total_params += param_count;
        
        std::cout << "  " << param.key() << ": ";
        for (size_t i = 0; i < sizes.size(); ++i) {
            std::cout << sizes[i];
            if (i < sizes.size() - 1) std::cout << " x ";
        }
        std::cout << " (" << param_count << " params)" << std::endl;
    }
    std::cout << "  Total: " << total_params << " parameters" << std::endl;
    
    // 4. Determine device
    std::string device = "cpu";
    if (torch::cuda::is_available()) {
        device = "cuda";
        std::cout << "\nCUDA available, using GPU" << std::endl;
    } else if (torch::mps::is_available()) {
        device = "mps";
        std::cout << "\nMPS available, using Apple Silicon GPU" << std::endl;
    } else {
        std::cout << "\nUsing CPU" << std::endl;
    }
    
    // 5. Create trainer
    auto trainer = create_trainer(config, grpc_client, device);
    
    // 6. Set progress callback
    trainer->set_progress_callback([](const EpochStats& stats) {
        std::cout << "\n--- Epoch " << (stats.epoch + 1) << " Summary ---" << std::endl;
        std::cout << "  Loss: " << std::fixed << std::setprecision(4) << stats.loss << std::endl;
        std::cout << "  Accuracy: " << std::setprecision(2) << (stats.accuracy * 100) << "%" << std::endl;
        std::cout << "  Batches: " << stats.num_batches << std::endl;
        std::cout << "  Duration: " << std::setprecision(1) << stats.duration_seconds << "s" << std::endl;
        
        for (const auto& [key, value] : stats.additional_metrics) {
            std::cout << "  " << key << ": " << value << std::endl;
        }
    });
    
    // 7. Start training
    std::cout << "\n=== Starting Training ===" << std::endl;
    
    try {
        trainer->train(
            "example-model",     // model_id
            model,               // model instance
            config.training.num_epochs,  // epochs
            ""                   // no checkpoint (fresh start)
        );
        
        std::cout << "\n=== Training Completed Successfully ===" << std::endl;
        
    } catch (const std::exception& e) {
        std::cerr << "\nTraining failed: " << e.what() << std::endl;
        return 1;
    }
    
    // 8. Cleanup
    grpc_client->disconnect();
    
    std::cout << "\nExample completed!" << std::endl;
    
    return 0;
}
