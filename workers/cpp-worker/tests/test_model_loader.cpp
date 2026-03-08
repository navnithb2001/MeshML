/**
 * @file test_model_loader.cpp
 * @brief Unit tests for model loader and factory
 */

#include <gtest/gtest.h>
#include "meshml/models/model_loader.h"
#include <torch/torch.h>
#include <filesystem>

namespace fs = std::filesystem;

class ModelLoaderTest : public ::testing::Test {
protected:
    void SetUp() override {
        temp_dir_ = fs::temp_directory_path() / "meshml_model_test";
        fs::create_directories(temp_dir_);
    }

    void TearDown() override {
        if (fs::exists(temp_dir_)) {
            fs::remove_all(temp_dir_);
        }
    }

    fs::path temp_dir_;
};

// Test: Model registration and listing
TEST_F(ModelLoaderTest, ListRegisteredModels) {
    auto& factory = meshml::models::ModelFactory::instance();
    auto models = factory.list_models();

    // Should have at least the built-in models
    EXPECT_TRUE(std::find(models.begin(), models.end(), "MLP") != models.end());
    EXPECT_TRUE(std::find(models.begin(), models.end(), "MNIST_CNN") != models.end());
    EXPECT_TRUE(std::find(models.begin(), models.end(), "ResNet18") != models.end());
}

// Test: Check if model is registered
TEST_F(ModelLoaderTest, IsModelRegistered) {
    auto& factory = meshml::models::ModelFactory::instance();

    EXPECT_TRUE(factory.is_registered("MLP"));
    EXPECT_TRUE(factory.is_registered("MNIST_CNN"));
    EXPECT_TRUE(factory.is_registered("ResNet18"));
    EXPECT_FALSE(factory.is_registered("NonExistentModel"));
}

// Test: Create MLP model
TEST_F(ModelLoaderTest, CreateMLPModel) {
    auto& factory = meshml::models::ModelFactory::instance();
    auto model = factory.create("MLP");

    ASSERT_NE(model, nullptr);
    EXPECT_EQ(model->name(), "MLP");
    
    // Test forward pass
    auto input = torch::randn({2, 784});  // Batch size 2, 784 features
    auto output = model->forward(input);
    
    EXPECT_EQ(output.sizes(), torch::IntArrayRef({2, 10}));  // Batch size 2, 10 classes
}

// Test: Create MNIST CNN model
TEST_F(ModelLoaderTest, CreateMNISTCNNModel) {
    auto& factory = meshml::models::ModelFactory::instance();
    auto model = factory.create("MNIST_CNN");

    ASSERT_NE(model, nullptr);
    EXPECT_EQ(model->name(), "MNIST_CNN");
    
    // Test forward pass
    auto input = torch::randn({2, 1, 28, 28});  // Batch size 2, 1 channel, 28x28
    auto output = model->forward(input);
    
    EXPECT_EQ(output.sizes(), torch::IntArrayRef({2, 10}));  // Batch size 2, 10 classes
}

// Test: Create ResNet18 model
TEST_F(ModelLoaderTest, CreateResNet18Model) {
    auto& factory = meshml::models::ModelFactory::instance();
    auto model = factory.create("ResNet18");

    ASSERT_NE(model, nullptr);
    EXPECT_EQ(model->name(), "ResNet18");
    
    // Test forward pass
    auto input = torch::randn({2, 3, 224, 224});  // Batch size 2, 3 channels, 224x224
    auto output = model->forward(input);
    
    EXPECT_EQ(output.sizes(), torch::IntArrayRef({2, 1000}));  // Batch size 2, 1000 classes
}

// Test: Model parameter counting
TEST_F(ModelLoaderTest, CountParameters) {
    auto& factory = meshml::models::ModelFactory::instance();
    
    auto mlp = factory.create("MLP");
    EXPECT_GT(mlp->num_parameters(), 0);
    
    auto cnn = factory.create("MNIST_CNN");
    EXPECT_GT(cnn->num_parameters(), 0);
    
    auto resnet = factory.create("ResNet18");
    EXPECT_GT(resnet->num_parameters(), 0);
    
    // ResNet18 should have more parameters than MNIST CNN
    EXPECT_GT(resnet->num_parameters(), cnn->num_parameters());
}

// Test: Model summary
TEST_F(ModelLoaderTest, ModelSummary) {
    auto& factory = meshml::models::ModelFactory::instance();
    auto model = factory.create("MLP");

    auto summary = model->summary();
    
    EXPECT_TRUE(summary.find("MLP") != std::string::npos);
    EXPECT_TRUE(summary.find("parameters") != std::string::npos);
}

// Test: Save and load TorchScript model
// DISABLED: TorchScript not fully supported in PyTorch 2.5.1 C++ API
TEST_F(ModelLoaderTest, DISABLED_SaveLoadTorchScript) {
    auto& factory = meshml::models::ModelFactory::instance();
    auto original_model = factory.create("MLP");
    
    auto model_path = temp_dir_ / "mlp_model.pt";
    
    // Save model
    meshml::models::ModelLoader loader;
    EXPECT_THROW(loader.save_torchscript(original_model, model_path.string()), std::runtime_error);
}

// Test: Save and load checkpoint
TEST_F(ModelLoaderTest, SaveLoadCheckpoint) {
    auto& factory = meshml::models::ModelFactory::instance();
    auto original_model = factory.create("MLP");
    
    auto checkpoint_path = temp_dir_ / "checkpoint.pt";
    
    // Save checkpoint with metadata
    meshml::models::ModelLoader loader;
    std::unordered_map<std::string, std::string> metadata = {
        {"epoch", "10"},
        {"loss", "0.5"}
    };
    loader.save_checkpoint(original_model, checkpoint_path.string(), metadata);
    
    EXPECT_TRUE(fs::exists(checkpoint_path));
    
    // Create new model and load weights
    auto new_model = factory.create("MLP");
    auto loaded_metadata = loader.load_checkpoint(new_model, checkpoint_path.string());
    
    EXPECT_EQ(loaded_metadata.at("epoch"), "10");
    EXPECT_EQ(loaded_metadata.at("loss"), "0.5");
    
    // Test that loaded model produces same output
    auto input = torch::randn({2, 784});
    
    torch::NoGradGuard no_grad;
    original_model->eval();
    new_model->eval();
    
    auto original_output = original_model->forward(input);
    auto loaded_output = new_model->forward(input);
    
    EXPECT_TRUE(torch::allclose(original_output, loaded_output, 1e-5));
}

// Test: Load from registry
TEST_F(ModelLoaderTest, LoadFromRegistry) {
    meshml::models::ModelLoader loader;
    
    auto model = loader.from_registry("MNIST_CNN");
    ASSERT_NE(model, nullptr);
    EXPECT_EQ(model->name(), "MNIST_CNN");
}

// Test: Custom model registration
TEST_F(ModelLoaderTest, RegisterCustomModel) {
    // Define a simple custom model
    struct CustomModel : public meshml::models::ModelBase {
        CustomModel() {
            fc = register_module("fc", torch::nn::Linear(10, 5));
        }
        
        torch::Tensor forward(torch::Tensor x) override {
            return fc->forward(x);
        }
        
        std::string name() const override { return "CustomModel"; }
        
        torch::nn::Linear fc{nullptr};
    };
    
    // Register the custom model
    auto& factory = meshml::models::ModelFactory::instance();
    factory.register_model("CustomModel", []() {
        return std::make_shared<CustomModel>();
    });
    
    EXPECT_TRUE(factory.is_registered("CustomModel"));
    
    // Create and test the custom model
    auto model = factory.create("CustomModel");
    ASSERT_NE(model, nullptr);
    EXPECT_EQ(model->name(), "CustomModel");
    
    auto input = torch::randn({2, 10});
    auto output = model->forward(input);
    EXPECT_EQ(output.sizes(), torch::IntArrayRef({2, 5}));
}

// Test: Error handling - unknown model
TEST_F(ModelLoaderTest, UnknownModel) {
    auto& factory = meshml::models::ModelFactory::instance();
    
    EXPECT_THROW({
        factory.create("UnknownModel");
    }, std::runtime_error);
}

// Test: Error handling - load non-existent file
TEST_F(ModelLoaderTest, LoadNonExistentFile) {
    meshml::models::ModelLoader loader;
    
    EXPECT_THROW({
        loader.load_torchscript("/nonexistent/model.pt");
    }, std::runtime_error);
}

// Test: Model gradients
TEST_F(ModelLoaderTest, ModelGradients) {
    auto& factory = meshml::models::ModelFactory::instance();
    auto model = factory.create("MLP");
    
    // Forward pass
    auto input = torch::randn({4, 784}, torch::requires_grad(true));
    auto output = model->forward(input);
    
    // Backward pass
    auto loss = output.sum();
    loss.backward();
    
    // Check that gradients exist
    for (const auto& param : model->parameters()) {
        EXPECT_TRUE(param.grad().defined());
    }
}

// Test: Model to different device (CPU/CUDA)
TEST_F(ModelLoaderTest, ModelToDevice) {
    auto& factory = meshml::models::ModelFactory::instance();
    auto model = factory.create("MLP");
    
    // Should default to CPU
    auto cpu_device = torch::kCPU;
    model->to(cpu_device);
    
    auto input = torch::randn({2, 784});
    auto output = model->forward(input);
    EXPECT_TRUE(output.device().is_cpu());
    
    // Test CUDA if available
    if (torch::cuda::is_available()) {
        auto cuda_device = torch::kCUDA;
        model->to(cuda_device);
        
        auto cuda_input = torch::randn({2, 784}, torch::device(cuda_device));
        auto cuda_output = model->forward(cuda_input);
        EXPECT_TRUE(cuda_output.device().is_cuda());
    }
}

// Test: Model training mode
TEST_F(ModelLoaderTest, TrainingMode) {
    auto& factory = meshml::models::ModelFactory::instance();
    auto model = factory.create("MNIST_CNN");
    
    // Set to training mode
    model->train();
    EXPECT_TRUE(model->is_training());
    
    // Set to eval mode
    model->eval();
    EXPECT_FALSE(model->is_training());
}

// Test: Zero gradients
TEST_F(ModelLoaderTest, ZeroGradients) {
    auto& factory = meshml::models::ModelFactory::instance();
    auto model = factory.create("MLP");
    
    // Forward and backward
    auto input = torch::randn({2, 784});
    auto output = model->forward(input);
    output.sum().backward();
    
    // Check gradients exist
    for (const auto& param : model->parameters()) {
        ASSERT_TRUE(param.grad().defined());
    }
    
    // Zero gradients
    model->zero_grad();
    
    // Check gradients are zero
    for (const auto& param : model->parameters()) {
        if (param.grad().defined()) {
            EXPECT_TRUE(torch::allclose(param.grad(), torch::zeros_like(param.grad())));
        }
    }
}
