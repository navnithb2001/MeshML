#include "meshml/config/config_loader.h"
#include <iostream>
#include <exception>

using namespace meshml::config;

int main() {
    std::cout << "=== MeshML Config Loader Example ===" << std::endl;
    
    // Example 1: Load from YAML file
    std::cout << "\n1. Loading from YAML file..." << std::endl;
    try {
        auto config = ConfigLoader::from_yaml("config.yaml");
        
        std::cout << "Worker ID: " << config.worker_id << std::endl;
        std::cout << "Worker Name: " << config.worker_name << std::endl;
        std::cout << "Model: " << config.training.model_name << std::endl;
        std::cout << "Learning Rate: " << config.training.learning_rate << std::endl;
        std::cout << "Batch Size: " << config.training.batch_size << std::endl;
        std::cout << "Device: " << config.training.device << std::endl;
        std::cout << "Mixed Precision: " << (config.training.mixed_precision ? "Yes" : "No") << std::endl;
        
        // Validate configuration
        auto errors = ConfigLoader::validate(config);
        if (errors.empty()) {
            std::cout << "✓ Configuration is valid!" << std::endl;
        } else {
            std::cout << "✗ Validation errors:" << std::endl;
            for (const auto& error : errors) {
                std::cout << "  - " << error << std::endl;
            }
        }
    } catch (const std::exception& e) {
        std::cerr << "Error loading config: " << e.what() << std::endl;
    }
    
    // Example 2: Load from YAML string
    std::cout << "\n2. Loading from YAML string..." << std::endl;
    const char* yaml_str = R"(
worker:
  worker_id: worker-002
  worker_name: "Laptop Worker"

training:
  learning_rate: 0.01
  batch_size: 32
  num_epochs: 10
  device: cpu
)";
    
    try {
        auto config = ConfigLoader::from_yaml_string(yaml_str);
        std::cout << "Worker ID: " << config.worker_id << std::endl;
        std::cout << "Learning Rate: " << config.training.learning_rate << std::endl;
        std::cout << "Device: " << config.training.device << std::endl;
    } catch (const std::exception& e) {
        std::cerr << "Error: " << e.what() << std::endl;
    }
    
    // Example 3: Create and save configuration
    std::cout << "\n3. Creating and saving configuration..." << std::endl;
    WorkerConfig custom_config;
    custom_config.worker_id = "worker-003";
    custom_config.worker_name = "Custom Worker";
    custom_config.training.learning_rate = 0.005;
    custom_config.training.batch_size = 128;
    custom_config.training.device = "cuda";
    custom_config.training.mixed_precision = true;
    
    try {
        ConfigLoader::to_yaml(custom_config, "custom_config.yaml");
        std::cout << "✓ Saved to custom_config.yaml" << std::endl;
        
        ConfigLoader::to_json(custom_config, "custom_config.json");
        std::cout << "✓ Saved to custom_config.json" << std::endl;
    } catch (const std::exception& e) {
        std::cerr << "Error: " << e.what() << std::endl;
    }
    
    // Example 4: Merge configurations
    std::cout << "\n4. Merging configurations..." << std::endl;
    WorkerConfig base;
    base.worker_id = "base-worker";
    base.training.learning_rate = 0.001;
    base.training.batch_size = 32;
    base.training.device = "cpu";
    
    WorkerConfig override;
    override.training.learning_rate = 0.01;
    override.training.device = "cuda";
    
    auto merged = ConfigLoader::merge(base, override);
    std::cout << "Base learning rate: " << base.training.learning_rate << std::endl;
    std::cout << "Override learning rate: " << override.training.learning_rate << std::endl;
    std::cout << "Merged learning rate: " << merged.training.learning_rate << std::endl;
    std::cout << "Merged device: " << merged.training.device << std::endl;
    std::cout << "Merged batch size (from base): " << merged.training.batch_size << std::endl;
    
    // Example 5: Validation
    std::cout << "\n5. Testing validation..." << std::endl;
    WorkerConfig invalid_config;
    invalid_config.worker_id = "";  // Invalid: empty
    invalid_config.training.learning_rate = -0.01;  // Invalid: negative
    invalid_config.training.batch_size = 0;  // Invalid: zero
    invalid_config.training.device = "invalid";  // Invalid: unknown device
    
    auto validation_errors = ConfigLoader::validate(invalid_config);
    std::cout << "Found " << validation_errors.size() << " validation errors:" << std::endl;
    for (const auto& error : validation_errors) {
        std::cout << "  ✗ " << error << std::endl;
    }
    
    std::cout << "\n=== Example Complete ===" << std::endl;
    return 0;
}
