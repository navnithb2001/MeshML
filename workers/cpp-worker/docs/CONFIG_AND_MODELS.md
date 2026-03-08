# Configuration and Model Loading Guide

## Overview

This guide covers the newly implemented configuration loading and model loading features in the MeshML C++ Worker.

## Table of Contents

1. [Configuration Loading](#configuration-loading)
2. [Model Loading](#model-loading)
3. [Protobuf Integration](#protobuf-integration)
4. [Integration Examples](#integration-examples)

---

## Configuration Loading

### Features

The configuration system provides:
- ✅ YAML and JSON file loading
- ✅ Type-safe configuration structures
- ✅ Validation with detailed error messages
- ✅ Configuration merging
- ✅ Default values
- ✅ Programmatic configuration creation

### Configuration Structure

```cpp
struct WorkerConfig {
    // Worker identity
    std::string worker_id;
    std::string worker_name;
    std::string worker_type;  // "cpp"
    
    // Resource limits
    int64_t max_memory_mb;
    int64_t max_cpu_cores;
    
    // Performance settings
    bool enable_simd;
    bool enable_memory_pool;
    bool enable_profiling;
    
    // Training configuration
    TrainingConfig training;
};

struct TrainingConfig {
    // Model
    std::string model_name;
    double learning_rate;
    int64_t batch_size;
    int64_t num_epochs;
    
    // Device
    std::string device;  // "cpu", "cuda", "mps"
    bool mixed_precision;
    
    // Data
    std::string data_path;
    int64_t num_workers;
    
    // Checkpointing
    std::string checkpoint_dir;
    int64_t checkpoint_interval;
    
    // Parameter Server
    std::string ps_host;
    int64_t ps_port;
    int64_t heartbeat_interval;
};
```

### Example YAML Configuration

```yaml
# config.yaml
worker:
  worker_id: worker-001
  worker_name: "Desktop Worker"
  worker_type: cpp
  max_memory_mb: 8192
  max_cpu_cores: 8
  enable_simd: true
  enable_memory_pool: true
  enable_profiling: false

training:
  model_name: "mnist_cnn"
  learning_rate: 0.001
  batch_size: 64
  num_epochs: 20
  optimizer: adam
  
  device: cuda
  mixed_precision: true
  
  data_path: "/data/mnist"
  num_workers: 4
  
  checkpoint_dir: "./checkpoints"
  checkpoint_interval: 100
  
  ps_host: localhost
  ps_port: 50051
  heartbeat_interval: 5
```

### Usage Examples

#### 1. Load from YAML File

```cpp
#include "meshml/config/config_loader.h"

using namespace meshml::config;

// Load configuration
auto config = ConfigLoader::from_yaml("config.yaml");

// Access values
std::cout << "Worker: " << config.worker_id << std::endl;
std::cout << "Learning rate: " << config.training.learning_rate << std::endl;
std::cout << "Device: " << config.training.device << std::endl;
```

#### 2. Validate Configuration

```cpp
auto errors = ConfigLoader::validate(config);

if (!errors.empty()) {
    std::cerr << "Configuration errors:" << std::endl;
    for (const auto& error : errors) {
        std::cerr << "  - " << error << std::endl;
    }
    return 1;
}

std::cout << "✓ Configuration is valid" << std::endl;
```

#### 3. Merge Configurations

```cpp
// Load base configuration
auto base_config = ConfigLoader::from_yaml("base_config.yaml");

// Load override configuration
auto override_config = ConfigLoader::from_yaml("override.yaml");

// Merge (override takes precedence)
auto final_config = ConfigLoader::merge(base_config, override_config);
```

#### 4. Create and Save Configuration

```cpp
WorkerConfig config;
config.worker_id = "worker-001";
config.training.learning_rate = 0.001;
config.training.batch_size = 64;
config.training.device = "cuda";

// Save as YAML
ConfigLoader::to_yaml(config, "output.yaml");

// Save as JSON
ConfigLoader::to_json(config, "output.json");
```

#### 5. Load from String

```cpp
const char* yaml_str = R"(
worker:
  worker_id: worker-002
training:
  learning_rate: 0.01
  device: cpu
)";

auto config = ConfigLoader::from_yaml_string(yaml_str);
```

### Validation Rules

The validator checks:
- ✅ `worker_id` is not empty
- ✅ `learning_rate > 0`
- ✅ `batch_size > 0`
- ✅ `num_epochs > 0`
- ✅ `num_workers >= 0`
- ✅ `device` is one of: "cpu", "cuda", "mps"
- ✅ `optimizer` is one of: "sgd", "adam", "adamw", "rmsprop"
- ✅ `ps_port` is in range [1, 65535]

---

## Model Loading

### Features

The model loading system provides:
- ✅ Model registry with factory pattern
- ✅ Built-in models (MLP, MNIST CNN, ResNet18)
- ✅ Dynamic model creation by name
- ✅ TorchScript model loading
- ✅ Checkpoint save/load
- ✅ Custom model registration

### Built-in Models

#### 1. MLP (Multi-Layer Perceptron)

```cpp
#include "meshml/models/model_loader.h"

using namespace meshml::models;

// Create MLP with custom layers
auto mlp = std::make_shared<MLPModel>(
    std::vector<int64_t>{784, 512, 256, 10}
);

// Use model
auto input = torch::randn({32, 784});
auto output = mlp->forward(input);
```

#### 2. MNIST CNN

```cpp
// Create from registry
auto model = ModelFactory::create("mnist_cnn");

// Forward pass
auto input = torch::randn({1, 1, 28, 28});
auto output = model->forward(input);  // Shape: [1, 10]
```

#### 3. ResNet18

```cpp
// Create ResNet18 for 10 classes
auto resnet = std::make_shared<ResNet18Model>(10);

// Or from registry (default 10 classes)
auto resnet = ModelFactory::create("resnet18");

// Forward pass
auto input = torch::randn({1, 3, 224, 224});
auto output = resnet->forward(input);  // Shape: [1, 10]
```

### Usage Examples

#### 1. List Available Models

```cpp
auto model_names = ModelFactory::list_models();

std::cout << "Available models:" << std::endl;
for (const auto& name : model_names) {
    std::cout << "  - " << name << std::endl;
}
```

#### 2. Create Model from Registry

```cpp
// Check if model exists
if (ModelFactory::is_registered("mnist_cnn")) {
    auto model = ModelFactory::create("mnist_cnn");
    
    // Print summary
    model->summary();
    
    // Get info
    std::cout << "Model: " << model->name() << std::endl;
    std::cout << "Parameters: " << model->num_parameters() << std::endl;
}
```

#### 3. Save and Load Weights

```cpp
// Create and train model
auto model = ModelFactory::create("mnist_cnn");
// ... train model ...

// Save weights
torch::save(model, "model_weights.pt");

// Later: load weights into new model
auto loaded_model = ModelFactory::create("mnist_cnn");
ModelLoader::load_weights(loaded_model, "model_weights.pt");
```

#### 4. Load TorchScript Model

```cpp
// Load pre-exported TorchScript model
auto device = torch::kCUDA;
auto module = ModelLoader::load_torchscript("model.pt", device);

// Use it
auto input = torch::randn({1, 3, 224, 224}).to(device);
auto output = module.forward({input}).toTensor();
```

#### 5. Load from Registry with Checkpoint

```cpp
// Load model and weights in one step
auto model = ModelLoader::from_registry(
    "mnist_cnn",                    // model name
    "checkpoints/best_model.pt",    // checkpoint path
    torch::kCUDA                    // device
);

// Model is ready to use
auto input = torch::randn({1, 1, 28, 28}).to(torch::kCUDA);
auto output = model->forward(input);
```

#### 6. Register Custom Model

```cpp
// Define custom model
class MyCustomModel : public ModelBase {
public:
    MyCustomModel() {
        fc1 = register_module("fc1", torch::nn::Linear(100, 50));
        fc2 = register_module("fc2", torch::nn::Linear(50, 10));
    }
    
    torch::Tensor forward(torch::Tensor input) override {
        auto x = torch::relu(fc1->forward(input));
        return fc2->forward(x);
    }
    
    std::string name() const override { return "my_custom_model"; }

private:
    torch::nn::Linear fc1{nullptr};
    torch::nn::Linear fc2{nullptr};
};

// Register model
ModelFactory::register_model("my_custom_model", []() {
    return std::make_shared<MyCustomModel>();
});

// Use it
auto model = ModelFactory::create("my_custom_model");
```

#### 7. Using REGISTER_MODEL Macro

```cpp
// In your .cpp file
class ResNet50Model : public ModelBase {
    // ... implementation ...
};

// Register using macro
REGISTER_MODEL("resnet50", []() {
    return std::make_shared<ResNet50Model>();
});

// Now available globally
auto model = ModelFactory::create("resnet50");
```

---

## Protobuf Integration

### Protocol Buffer Definitions

The system uses Protocol Buffers for communication with the Parameter Server:

```protobuf
// worker.proto
message WorkerInfo {
  string worker_id = 1;
  string worker_type = 2;
  string device = 3;
  int64 memory_mb = 4;
  int32 cpu_cores = 5;
}

message HeartbeatRequest {
  WorkerInfo worker = 1;
  JobInfo job = 2;
  int64 iteration = 3;
  double current_loss = 4;
  double current_accuracy = 5;
}

message TensorData {
  repeated int64 shape = 1;
  bytes data = 2;
  string dtype = 3;
  bool compressed = 4;
}

message GradientUpdate {
  string worker_id = 1;
  string job_id = 2;
  map<string, TensorData> gradients = 3;
}
```

### Generating Protocol Buffers

```bash
# In cpp-worker directory
protoc --proto_path=proto \
       --cpp_out=src/grpc/generated \
       --grpc_out=src/grpc/generated \
       --plugin=protoc-gen-grpc=$(which grpc_cpp_plugin) \
       proto/parameter_server.proto
```

### Usage with gRPC Client

```cpp
#include "meshml/grpc/proto_utils.h"
#include "meshml/grpc/client.h"

using namespace meshml::grpc;

// Create worker info
auto worker_info = ProtobufConverter::create_worker_info(
    "worker-001",  // worker_id
    "cpp",         // worker_type
    "cuda",        // device
    8192,          // memory_mb
    8              // cpu_cores
);

// Create heartbeat request
auto heartbeat = ProtobufConverter::create_heartbeat_request(
    *worker_info,
    *job_info,
    iteration,
    loss,
    accuracy
);

// Send via gRPC client
auto client = create_grpc_client("localhost:50051", "worker-001");
auto response = client->send_heartbeat(std::move(heartbeat));
```

### Tensor Conversion

```cpp
// Convert torch::Tensor to protobuf
torch::Tensor gradients = model->gradients();
auto tensor_proto = ProtobufConverter::tensor_to_proto(gradients, true);  // compress

// Convert protobuf to torch::Tensor
auto params_map = ProtobufConverter::proto_to_parameters(response);
for (const auto& [name, tensor] : params_map) {
    // Apply parameters to model
    model->set_parameter(name, tensor);
}
```

---

## Integration Examples

### Complete Training with Configuration

```cpp
#include "meshml/config/config_loader.h"
#include "meshml/models/model_loader.h"
#include "meshml/training/trainer.h"
#include "meshml/grpc/client.h"

using namespace meshml;

int main() {
    // 1. Load configuration
    auto config = config::ConfigLoader::from_yaml("config.yaml");
    
    // Validate
    auto errors = config::ConfigLoader::validate(config);
    if (!errors.empty()) {
        std::cerr << "Config errors!" << std::endl;
        return 1;
    }
    
    // 2. Create model from registry
    auto device = torch::Device(config.training.device);
    auto model = models::ModelLoader::from_registry(
        config.training.model_name,
        "",  // no checkpoint yet
        device
    );
    
    std::cout << "Model: " << model->name() << std::endl;
    std::cout << "Parameters: " << model->num_parameters() << std::endl;
    
    // 3. Create data loader
    auto data_loader = training::DataLoaderBuilder()
        .batch_size(config.training.batch_size)
        .num_workers(config.training.num_workers)
        .shuffle(config.training.shuffle)
        .pin_memory(config.training.pin_memory)
        .build();
    
    // 4. Create gRPC client
    std::string ps_address = config.training.ps_host + ":" + 
                            std::to_string(config.training.ps_port);
    auto grpc_client = grpc::create_grpc_client(
        ps_address,
        config.worker_id
    );
    
    // 5. Create trainer
    auto trainer = training::create_trainer(
        model,
        device,
        config.training.learning_rate
    );
    
    // Configure trainer
    trainer->set_checkpoint_dir(config.training.checkpoint_dir);
    trainer->set_checkpoint_interval(config.training.checkpoint_interval);
    trainer->set_log_interval(config.training.log_interval);
    
    if (config.training.mixed_precision) {
        trainer->enable_mixed_precision();
    }
    
    // 6. Train
    trainer->train(
        data_loader,
        config.training.num_epochs,
        grpc_client.get()
    );
    
    std::cout << "Training complete!" << std::endl;
    return 0;
}
```

### Command-line Tool with Config Override

```cpp
#include <cxxopts.hpp>  // Command-line parsing library

int main(int argc, char** argv) {
    // Parse command-line arguments
    cxxopts::Options options("meshml-worker", "MeshML C++ Worker");
    options.add_options()
        ("c,config", "Config file", cxxopts::value<std::string>()->default_value("config.yaml"))
        ("l,learning-rate", "Learning rate", cxxopts::value<double>())
        ("b,batch-size", "Batch size", cxxopts::value<int>())
        ("d,device", "Device (cpu/cuda/mps)", cxxopts::value<std::string>())
        ("h,help", "Print help");
    
    auto result = options.parse(argc, argv);
    
    if (result.count("help")) {
        std::cout << options.help() << std::endl;
        return 0;
    }
    
    // Load base config from file
    auto config = config::ConfigLoader::from_yaml(result["config"].as<std::string>());
    
    // Override with command-line arguments
    if (result.count("learning-rate")) {
        config.training.learning_rate = result["learning-rate"].as<double>();
    }
    if (result.count("batch-size")) {
        config.training.batch_size = result["batch-size"].as<int>();
    }
    if (result.count("device")) {
        config.training.device = result["device"].as<std::string>();
    }
    
    // Validate final config
    auto errors = config::ConfigLoader::validate(config);
    if (!errors.empty()) {
        for (const auto& error : errors) {
            std::cerr << "Error: " << error << std::endl;
        }
        return 1;
    }
    
    // Continue with training...
    return 0;
}
```

### Model Selection at Runtime

```cpp
// List available models
auto models = models::ModelFactory::list_models();

std::cout << "Available models:" << std::endl;
for (size_t i = 0; i < models.size(); ++i) {
    std::cout << "  " << (i+1) << ". " << models[i] << std::endl;
}

// Let user choose
int choice;
std::cout << "Select model: ";
std::cin >> choice;

if (choice < 1 || choice > models.size()) {
    std::cerr << "Invalid choice" << std::endl;
    return 1;
}

// Create selected model
std::string model_name = models[choice - 1];
auto model = models::ModelFactory::create(model_name);

std::cout << "Created model: " << model->name() << std::endl;
model->summary();
```

---

## Best Practices

### Configuration

1. **Use YAML for human-readable configs**: Easier to edit than JSON
2. **Validate early**: Check config before starting training
3. **Use defaults wisely**: Provide sensible defaults for optional params
4. **Version your configs**: Track config files in version control
5. **Merge configs**: Use base config + environment-specific overrides

### Model Loading

1. **Register models at startup**: Use static initialization or main()
2. **Use factory pattern**: Don't create models directly, use `ModelFactory::create()`
3. **Save checkpoints regularly**: Use trainer's checkpoint functionality
4. **Version model files**: Include version/date in checkpoint filenames
5. **Test model loading**: Verify loaded models produce correct output

### Protobuf

1. **Define schemas carefully**: Proto changes require recompilation
2. **Use compression for large tensors**: Enable for gradients >100KB
3. **Version proto files**: Backwards compatibility is important
4. **Handle errors gracefully**: Network can fail, have retry logic

---

## Troubleshooting

### Config Loading

**Error: "Cannot open file"**
- Check file path is correct
- Use absolute paths or ensure working directory is correct

**Error: "Validation failed"**
- Review validation error messages
- Check data types (int vs float, etc.)
- Ensure required fields are set

### Model Loading

**Error: "Model 'xxx' not found"**
- Check model is registered (use `ModelFactory::list_models()`)
- Ensure registration code runs before factory use

**Error: "Failed to load weights"**
- Verify checkpoint file exists and is readable
- Ensure model architecture matches checkpoint
- Check for LibTorch version compatibility

### Protobuf

**Error: "protobuf version mismatch"**
- Ensure protoc version matches libprotobuf version
- Regenerate .pb.cc files with correct protoc

**Error: "Tensor deserialization failed"**
- Check tensor data types match
- Verify compression/decompression works correctly

---

## Performance Tips

1. **Enable SIMD**: Set `enable_simd: true` in config
2. **Use memory pooling**: Set `enable_memory_pool: true`
3. **Pin memory for CUDA**: Set `pin_memory: true` for faster transfers
4. **Multi-threaded data loading**: Use `num_workers: 4` or more
5. **Mixed precision**: Enable for 30-50% speedup on GPU
6. **Compress gradients**: Enable for >10% reduction in network traffic

---

## See Also

- [Training Guide](TRAINING_GUIDE.md) - Complete training loop documentation
- [Performance Guide](PERFORMANCE_GUIDE.md) - Optimization techniques
- [gRPC Examples](GRPC_EXAMPLES.md) - Parameter Server communication
- [API Reference](API_REFERENCE.md) - Complete API documentation
