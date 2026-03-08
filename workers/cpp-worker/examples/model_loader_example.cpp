#include "meshml/models/model_loader.h"
#include <iostream>
#include <exception>

using namespace meshml::models;

int main() {
    std::cout << "=== MeshML Model Loader Example ===" << std::endl;
    
    // Example 1: List available models
    std::cout << "\n1. Available models in registry:" << std::endl;
    auto model_names = ModelFactory::list_models();
    for (const auto& name : model_names) {
        std::cout << "  - " << name << std::endl;
    }
    
    // Example 2: Create model from registry
    std::cout << "\n2. Creating MNIST CNN model..." << std::endl;
    try {
        auto mnist_model = ModelFactory::create("mnist_cnn");
        mnist_model->summary();
        
        // Test forward pass
        auto input = torch::randn({1, 1, 28, 28});
        auto output = mnist_model->forward(input);
        std::cout << "Input shape: " << input.sizes() << std::endl;
        std::cout << "Output shape: " << output.sizes() << std::endl;
    } catch (const std::exception& e) {
        std::cerr << "Error: " << e.what() << std::endl;
    }
    
    // Example 3: Create MLP model
    std::cout << "\n3. Creating MLP model..." << std::endl;
    try {
        auto mlp = std::make_shared<MLPModel>(std::vector<int64_t>{784, 512, 256, 10});
        mlp->summary();
        
        auto input = torch::randn({32, 784});
        auto output = mlp->forward(input);
        std::cout << "Batch size: " << input.size(0) << std::endl;
        std::cout << "Output shape: " << output.sizes() << std::endl;
    } catch (const std::exception& e) {
        std::cerr << "Error: " << e.what() << std::endl;
    }
    
    // Example 4: Create ResNet18 model
    std::cout << "\n4. Creating ResNet18 model..." << std::endl;
    try {
        auto resnet = ModelFactory::create("resnet18");
        std::cout << "Model name: " << resnet->name() << std::endl;
        std::cout << "Number of parameters: " << resnet->num_parameters() << std::endl;
        
        auto input = torch::randn({1, 3, 224, 224});
        auto output = resnet->forward(input);
        std::cout << "Input shape: " << input.sizes() << std::endl;
        std::cout << "Output shape: " << output.sizes() << std::endl;
    } catch (const std::exception& e) {
        std::cerr << "Error: " << e.what() << std::endl;
    }
    
    // Example 5: Save and load model
    std::cout << "\n5. Saving and loading model..." << std::endl;
    try {
        auto model = ModelFactory::create("mnist_cnn");
        
        // Save weights
        torch::save(model, "mnist_model.pt");
        std::cout << "✓ Model saved to mnist_model.pt" << std::endl;
        
        // Create new model and load weights
        auto loaded_model = ModelFactory::create("mnist_cnn");
        ModelLoader::load_weights(loaded_model, "mnist_model.pt");
        std::cout << "✓ Model loaded from mnist_model.pt" << std::endl;
        
        // Verify they produce same output
        auto input = torch::randn({1, 1, 28, 28});
        auto output1 = model->forward(input);
        auto output2 = loaded_model->forward(input);
        
        auto diff = (output1 - output2).abs().max().item<float>();
        std::cout << "Max difference: " << diff << std::endl;
        if (diff < 1e-6) {
            std::cout << "✓ Models produce identical outputs!" << std::endl;
        }
    } catch (const std::exception& e) {
        std::cerr << "Error: " << e.what() << std::endl;
    }
    
    // Example 6: Load from registry with checkpoint
    std::cout << "\n6. Loading from registry with checkpoint..." << std::endl;
    try {
        // This would load pre-trained weights if checkpoint exists
        // auto model = ModelLoader::from_registry("mnist_cnn", "checkpoints/best_model.pt");
        
        // For demo, just create without checkpoint
        auto device = torch::kCPU;
        if (torch::cuda::is_available()) {
            device = torch::kCUDA;
            std::cout << "CUDA is available!" << std::endl;
        }
        
        auto model = ModelLoader::from_registry("mnist_cnn", "", device);
        std::cout << "✓ Model loaded on device: " << device << std::endl;
        
        // Check model is on correct device
        auto params = model->parameters();
        if (!params.empty()) {
            std::cout << "First parameter device: " << params[0].device() << std::endl;
        }
    } catch (const std::exception& e) {
        std::cerr << "Error: " << e.what() << std::endl;
    }
    
    // Example 7: Register custom model
    std::cout << "\n7. Registering custom model..." << std::endl;
    
    // Define a simple custom model
    class CustomModel : public ModelBase {
    public:
        CustomModel() {
            fc = register_module("fc", torch::nn::Linear(10, 2));
        }
        
        torch::Tensor forward(torch::Tensor input) override {
            return fc->forward(input);
        }
        
        std::string name() const override { return "custom"; }
        
    private:
        torch::nn::Linear fc{nullptr};
    };
    
    // Register it
    ModelFactory::register_model("custom", []() {
        return std::make_shared<CustomModel>();
    });
    
    // Use it
    if (ModelFactory::is_registered("custom")) {
        auto custom = ModelFactory::create("custom");
        std::cout << "✓ Custom model registered and created" << std::endl;
        custom->summary();
    }
    
    std::cout << "\n=== Example Complete ===" << std::endl;
    return 0;
}
