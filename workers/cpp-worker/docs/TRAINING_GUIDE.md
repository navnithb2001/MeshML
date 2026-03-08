# Training Loop Usage Guide

## Overview

The C++ Worker's training loop provides high-performance model training with LibTorch, featuring:

- **LibTorch Integration**: Full PyTorch C++ API support
- **Autograd**: Automatic gradient computation
- **Mixed Precision**: CUDA AMP for faster training
- **Checkpointing**: Save/load training state
- **Progress Tracking**: Real-time training statistics
- **Parameter Server Integration**: Automatic gradient synchronization
- **Multi-threading**: Efficient data loading

## Quick Start

### 1. Basic Training

```cpp
#include "meshml/training/trainer.h"
#include "meshml/config.h"
#include <torch/torch.h>

// Create a simple model
struct MyModel : torch::nn::Module {
    MyModel() {
        fc1 = register_module("fc1", torch::nn::Linear(784, 128));
        fc2 = register_module("fc2", torch::nn::Linear(128, 10));
    }
    
    torch::Tensor forward(torch::Tensor x) {
        x = torch::relu(fc1->forward(x));
        return fc2->forward(x);
    }
    
    torch::nn::Linear fc1{nullptr}, fc2{nullptr};
};

int main() {
    // Configure worker
    WorkerConfig config;
    config.identity.worker_id = "worker-001";
    config.identity.job_id = "job-123";
    config.training.learning_rate = 0.01f;
    config.training.batch_size = 32;
    
    // Create gRPC client
    auto client = std::make_shared<GRPCClient>("localhost:50051", 30);
    client->connect();
    
    // Create trainer
    auto trainer = create_trainer(config, client, "cpu");
    
    // Create and train model
    auto model = std::make_shared<MyModel>();
    trainer->train("my-model", model, 10);  // 10 epochs
    
    return 0;
}
```

### 2. With Data Loading

```cpp
#include "meshml/training/data_loader.h"

// Create dataset
auto inputs = torch::randn({1000, 784});
auto targets = torch::randint(0, 10, {1000});
auto dataset = std::make_shared<TensorDataset>(inputs, targets);

// Build data loader
auto loader = DataLoaderBuilder()
    .dataset(dataset)
    .batch_size(32)
    .shuffle(true)
    .num_workers(4)
    .build();

// Use in training loop (integrated into Trainer)
```

### 3. With Checkpointing

```cpp
#include "meshml/training/checkpoint.h"

// Create checkpoint manager
auto checkpoint_mgr = create_checkpoint_manager(
    "/tmp/checkpoints",  // checkpoint directory
    "my-model",          // model ID
    5                    // keep last 5 checkpoints
);

// In training loop, checkpoints are saved automatically
// To resume from checkpoint:
trainer->train(
    "my-model",
    model,
    10,
    "/tmp/checkpoints/my-model_epoch_0005.pt"  // resume from epoch 5
);
```

## Training Configuration

### WorkerConfig Structure

```cpp
WorkerConfig config;

// Identity
config.identity.worker_id = "worker-001";
config.identity.job_id = "job-123";
config.identity.group_id = "group-1";

// Training parameters
config.training.learning_rate = 0.01f;
config.training.batch_size = 32;
config.training.num_epochs = 10;
config.training.momentum = 0.9f;
config.training.weight_decay = 0.0001f;
config.training.gradient_push_frequency = 10;  // Push every 10 batches
config.training.mixed_precision = true;  // Enable AMP (CUDA only)

// Storage paths
config.storage.base_dir = "/tmp/meshml-worker";
config.storage.data_dir = "/tmp/meshml-worker/data";
config.storage.models_dir = "/tmp/meshml-worker/models";
config.storage.checkpoints_dir = "/tmp/meshml-worker/checkpoints";

// Server endpoints
config.server.parameter_server_addr = "localhost:50051";
config.server.heartbeat_interval = 30;  // seconds
```

## Advanced Features

### 1. Progress Callbacks

```cpp
trainer->set_progress_callback([](const EpochStats& stats) {
    std::cout << "Epoch " << stats.epoch 
              << ": loss=" << stats.loss
              << ", accuracy=" << stats.accuracy
              << std::endl;
    
    // Log to file, send to monitoring service, etc.
});
```

### 2. Custom Datasets

```cpp
class MyDataset : public CustomDataset {
public:
    MyDataset(const std::string& data_path) {
        // Load your data
        load_data(data_path);
    }
    
    torch::data::Example<> get(size_t index) override {
        return {inputs_[index], targets_[index]};
    }
    
    torch::optional<size_t> size() const override {
        return inputs_.size();
    }
    
private:
    std::vector<torch::Tensor> inputs_;
    std::vector<torch::Tensor> targets_;
    
    void load_data(const std::string& path) {
        // Your data loading logic
    }
};

// Use in training
auto dataset = std::make_shared<MyDataset>("data.csv");
```

### 3. Data Augmentation

```cpp
using namespace meshml::augmentations;

auto loader = DataLoaderBuilder()
    .dataset(dataset)
    .batch_size(32)
    .augmentation(random_horizontal_flip(0.5))  // 50% flip chance
    .build();

// Chain multiple augmentations
auto normalize_aug = normalize({0.485, 0.456, 0.406}, {0.229, 0.224, 0.225});
auto crop_aug = random_crop(224, 224, 4);
```

### 4. Mixed Precision Training

```cpp
// Enable for CUDA (automatic speedup)
trainer->set_mixed_precision(true);

// Typically 1.5-2x faster on modern GPUs
// Uses less memory (can increase batch size)
```

### 5. Distributed Training

```cpp
// Configure gradient push frequency
config.training.gradient_push_frequency = 10;

// Lower = more communication, better convergence
// Higher = less communication, potentially stale gradients

// Trainer automatically:
// 1. Fetches initial weights from Parameter Server
// 2. Trains locally for N batches
// 3. Pushes gradients to Parameter Server
// 4. Continues training
```

### 6. Checkpoint Management

```cpp
auto checkpoint_mgr = create_checkpoint_manager(
    "/tmp/checkpoints",
    "my-model",
    5  // keep last 5
);

// Save manually
checkpoint_mgr->save_checkpoint(
    *model,
    optimizer.get(),
    epoch,
    loss,
    accuracy,
    global_version
);

// Load manually
auto metadata = checkpoint_mgr->load_checkpoint(
    "/tmp/checkpoints/my-model_epoch_0005.pt",
    *model,
    optimizer.get()
);

std::cout << "Loaded epoch " << metadata.epoch 
          << " with loss " << metadata.loss << std::endl;

// List all checkpoints
auto checkpoints = checkpoint_mgr->list_checkpoints();
for (const auto& cp : checkpoints) {
    std::cout << "Found: " << cp << std::endl;
}

// Get latest
auto latest = checkpoint_mgr->get_latest_checkpoint();

// Cleanup old checkpoints
checkpoint_mgr->cleanup_old_checkpoints();
```

### 7. Auto Checkpointing

```cpp
auto auto_checkpoint = std::make_shared<AutoCheckpoint>(
    checkpoint_mgr,
    1,      // save every 1 epoch
    true    // save on improvement
);

// In training loop
if (auto_checkpoint->should_save(epoch, loss)) {
    checkpoint_mgr->save_checkpoint(...);
    auto_checkpoint->record_save(epoch, loss);
}

// Get best loss seen
float best = auto_checkpoint->get_best_loss();
```

## Device Selection

### CPU

```cpp
auto trainer = create_trainer(config, client, "cpu");
```

### CUDA (NVIDIA GPU)

```cpp
if (torch::cuda::is_available()) {
    auto trainer = create_trainer(config, client, "cuda");
    trainer->set_mixed_precision(true);  // Enable AMP
}
```

### MPS (Apple Silicon)

```cpp
if (torch::mps::is_available()) {
    auto trainer = create_trainer(config, client, "mps");
    // Note: Mixed precision not supported on MPS
}
```

### Auto-detection

```cpp
std::string device = "cpu";
if (torch::cuda::is_available()) {
    device = "cuda";
} else if (torch::mps::is_available()) {
    device = "mps";
}
auto trainer = create_trainer(config, client, device);
```

## Model Definition

### Simple Feedforward Network

```cpp
struct SimpleNet : torch::nn::Module {
    SimpleNet() {
        fc1 = register_module("fc1", torch::nn::Linear(784, 128));
        fc2 = register_module("fc2", torch::nn::Linear(128, 10));
    }
    
    torch::Tensor forward(torch::Tensor x) {
        x = torch::relu(fc1->forward(x));
        return fc2->forward(x);
    }
    
    torch::nn::Linear fc1{nullptr}, fc2{nullptr};
};
```

### Convolutional Network

```cpp
struct ConvNet : torch::nn::Module {
    ConvNet() {
        conv1 = register_module("conv1", torch::nn::Conv2d(1, 32, 3));
        conv2 = register_module("conv2", torch::nn::Conv2d(32, 64, 3));
        fc1 = register_module("fc1", torch::nn::Linear(1600, 128));
        fc2 = register_module("fc2", torch::nn::Linear(128, 10));
    }
    
    torch::Tensor forward(torch::Tensor x) {
        x = torch::relu(torch::max_pool2d(conv1->forward(x), 2));
        x = torch::relu(torch::max_pool2d(conv2->forward(x), 2));
        x = x.view({-1, 1600});
        x = torch::relu(fc1->forward(x));
        return fc2->forward(x);
    }
    
    torch::nn::Conv2d conv1{nullptr}, conv2{nullptr};
    torch::nn::Linear fc1{nullptr}, fc2{nullptr};
};
```

### ResNet Block

```cpp
struct ResidualBlock : torch::nn::Module {
    ResidualBlock(int in_channels, int out_channels, int stride = 1) {
        conv1 = register_module("conv1", 
            torch::nn::Conv2d(torch::nn::Conv2dOptions(in_channels, out_channels, 3)
                .stride(stride).padding(1).bias(false)));
        bn1 = register_module("bn1", torch::nn::BatchNorm2d(out_channels));
        
        conv2 = register_module("conv2",
            torch::nn::Conv2d(torch::nn::Conv2dOptions(out_channels, out_channels, 3)
                .stride(1).padding(1).bias(false)));
        bn2 = register_module("bn2", torch::nn::BatchNorm2d(out_channels));
        
        if (stride != 1 || in_channels != out_channels) {
            downsample = register_module("downsample",
                torch::nn::Conv2d(torch::nn::Conv2dOptions(in_channels, out_channels, 1)
                    .stride(stride).bias(false)));
            bn_downsample = register_module("bn_downsample", 
                torch::nn::BatchNorm2d(out_channels));
        }
    }
    
    torch::Tensor forward(torch::Tensor x) {
        auto residual = x;
        
        auto out = conv1->forward(x);
        out = bn1->forward(out);
        out = torch::relu(out);
        
        out = conv2->forward(out);
        out = bn2->forward(out);
        
        if (!downsample.is_empty()) {
            residual = downsample->forward(x);
            residual = bn_downsample->forward(residual);
        }
        
        out += residual;
        out = torch::relu(out);
        
        return out;
    }
    
    torch::nn::Conv2d conv1{nullptr}, conv2{nullptr}, downsample{nullptr};
    torch::nn::BatchNorm2d bn1{nullptr}, bn2{nullptr}, bn_downsample{nullptr};
};
```

## Performance Tips

### 1. Batch Size

```cpp
// Larger batch size = better GPU utilization
// Limited by GPU memory
// Try powers of 2: 32, 64, 128, 256

config.training.batch_size = 128;  // Adjust based on GPU memory
```

### 2. Number of Workers

```cpp
// More workers = faster data loading
// Limited by CPU cores and I/O
// Typical: 4-8 workers

auto loader = DataLoaderBuilder()
    .num_workers(4)
    .build();
```

### 3. Pin Memory

```cpp
// Faster CPU-GPU transfer (CUDA only)
auto loader = DataLoaderBuilder()
    .pin_memory(true)  // Enable for CUDA
    .build();
```

### 4. Gradient Accumulation

```cpp
// Simulate larger batch size with limited memory
// Accumulate gradients over N batches before pushing

config.training.gradient_push_frequency = 4;
// Effective batch size = 32 * 4 = 128
```

### 5. Mixed Precision

```cpp
// 1.5-2x speedup on modern GPUs
// Reduces memory usage
// CUDA only

trainer->set_mixed_precision(true);
```

## Troubleshooting

### Out of Memory

```cpp
// Reduce batch size
config.training.batch_size = 16;

// Enable mixed precision (CUDA)
trainer->set_mixed_precision(true);

// Use gradient checkpointing (advanced)
```

### Slow Training

```cpp
// Increase batch size (if memory allows)
config.training.batch_size = 128;

// Use more data workers
DataLoaderBuilder().num_workers(8);

// Enable mixed precision
trainer->set_mixed_precision(true);

// Pin memory (CUDA)
DataLoaderBuilder().pin_memory(true);
```

### Gradient Synchronization Issues

```cpp
// Adjust push frequency
config.training.gradient_push_frequency = 10;

// Check Parameter Server connection
if (!grpc_client->connect()) {
    std::cerr << "Failed to connect" << std::endl;
}

// Monitor heartbeat
heartbeat->is_healthy();
```

## Complete Example

See `examples/training_example.cpp` for a full working example demonstrating:
- Model definition
- Configuration
- Data loading
- Training loop
- Progress tracking
- Checkpointing

Build and run:
```bash
cd workers/cpp-worker
mkdir build && cd build
cmake ..
make
./examples/training_example
```

## API Reference

### Trainer

- `train(model_id, model, epochs, checkpoint_path)` - Start training
- `set_progress_callback(callback)` - Set progress callback
- `stop()` - Stop training gracefully
- `get_state()` - Get current training state
- `set_mixed_precision(enabled)` - Enable/disable AMP

### CheckpointManager

- `save_checkpoint(model, optimizer, epoch, loss, accuracy, version)` - Save checkpoint
- `load_checkpoint(path, model, optimizer)` - Load checkpoint
- `get_latest_checkpoint()` - Get latest checkpoint path
- `list_checkpoints()` - List all checkpoints
- `cleanup_old_checkpoints()` - Delete old checkpoints

### DataLoaderBuilder

- `dataset(dataset)` - Set dataset
- `batch_size(size)` - Set batch size
- `shuffle(enabled)` - Enable shuffling
- `num_workers(count)` - Set worker threads
- `drop_last(enabled)` - Drop last incomplete batch
- `pin_memory(enabled)` - Pin memory for CUDA
- `build()` - Build data loader
