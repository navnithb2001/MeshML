#pragma once

#include <torch/torch.h>
#include <string>
#include <memory>
#include <functional>
#include <unordered_map>

namespace meshml {
namespace models {

/**
 * @brief Base class for all models
 */
class ModelBase : public torch::nn::Module {
public:
    virtual ~ModelBase() = default;
    
    /**
     * @brief Forward pass
     * @param input Input tensor
     * @return Output tensor
     */
    virtual torch::Tensor forward(torch::Tensor input) = 0;
    
    /**
     * @brief Get model name
     */
    virtual std::string name() const = 0;
    
    /**
     * @brief Get number of parameters
     */
    int64_t num_parameters() const;
    
    /**
     * @brief Get model summary as string
     */
    std::string summary() const;
    
    /**
     * @brief Print model summary to console
     */
    void print_summary() const;
};

/**
 * @brief Model factory for creating models by name
 */
class ModelFactory {
public:
    using ModelCreator = std::function<std::shared_ptr<ModelBase>()>;
    
    /**
     * @brief Get singleton instance
     */
    static ModelFactory& instance();
    
    /**
     * @brief Register a model creator
     * @param name Model name
     * @param creator Function that creates the model
     */
    void register_model(const std::string& name, ModelCreator creator);
    
    /**
     * @brief Create a model by name
     * @param name Model name
     * @return Shared pointer to created model
     * @throws std::runtime_error if model name not found
     */
    std::shared_ptr<ModelBase> create(const std::string& name);
    
    /**
     * @brief Check if a model is registered
     * @param name Model name
     * @return True if model is registered
     */
    bool is_registered(const std::string& name);
    
    /**
     * @brief Get list of registered model names
     */
    std::vector<std::string> list_models();

private:
    ModelFactory() = default;
    ModelFactory(const ModelFactory&) = delete;
    ModelFactory& operator=(const ModelFactory&) = delete;
    
    std::unordered_map<std::string, ModelCreator> registry_;
};

/**
 * @brief Helper macro for registering models
 * 
 * Usage:
 * ```cpp
 * REGISTER_MODEL("my_model", []() { return std::make_shared<MyModel>(); });
 * ```
 */
#define REGISTER_MODEL(name, creator) \
    static bool _model_registered_##name = []() { \
        ModelFactory::instance().register_model(name, creator); \
        return true; \
    }();

/**
 * @brief Model loader for loading models from files
 */
class ModelLoader {
public:
    /**
     * @brief Load model from TorchScript file
     * @param filepath Path to .pt file
     * @param device Device to load model on
     * @return Loaded TorchScript module
     */
    torch::jit::script::Module load_torchscript(
        const std::string& filepath,
        const torch::Device& device = torch::kCPU
    );
    
    /**
     * @brief Load model weights from checkpoint
     * @param model Model to load weights into
     * @param filepath Path to checkpoint file
     * @param strict Whether to strictly enforce key matching
     * @return Metadata from checkpoint
     */
    std::unordered_map<std::string, std::string> load_checkpoint(
        std::shared_ptr<ModelBase> model,
        const std::string& filepath,
        bool strict = true
    );
    
    /**
     * @brief Save model checkpoint with metadata
     * @param model Model to save
     * @param filepath Path to output checkpoint file
     * @param metadata Optional metadata to save with checkpoint
     */
    void save_checkpoint(
        std::shared_ptr<ModelBase> model,
        const std::string& filepath,
        const std::unordered_map<std::string, std::string>& metadata = {}
    );
    
    /**
     * @brief Save model as TorchScript
     * @param model Model to save
     * @param filepath Path to output .pt file
     */
    void save_torchscript(
        std::shared_ptr<ModelBase> model,
        const std::string& filepath
    );
    
    /**
     * @brief Load model from model registry
     * @param model_name Name of the model in registry
     * @param checkpoint_path Optional path to checkpoint
     * @param device Device to load model on
     * @return Loaded model
     */
    std::shared_ptr<ModelBase> from_registry(
        const std::string& model_name,
        const std::string& checkpoint_path = "",
        const torch::Device& device = torch::kCPU
    );
};

// Built-in model implementations

/**
 * @brief Simple MLP model
 */
class MLPModel : public ModelBase {
public:
    MLPModel(const std::vector<int64_t>& layers);
    
    torch::Tensor forward(torch::Tensor input) override;
    std::string name() const override { return "mlp"; }

private:
    std::vector<torch::nn::Linear> layers_;
};

/**
 * @brief Simple CNN model for MNIST
 */
class MNISTCNNModel : public ModelBase {
public:
    MNISTCNNModel();
    
    torch::Tensor forward(torch::Tensor input) override;
    std::string name() const override { return "mnist_cnn"; }

private:
    torch::nn::Conv2d conv1{nullptr};
    torch::nn::Conv2d conv2{nullptr};
    torch::nn::Linear fc1{nullptr};
    torch::nn::Linear fc2{nullptr};
};

/**
 * @brief ResNet block
 */
class ResNetBlock : public torch::nn::Module {
public:
    ResNetBlock(int64_t in_channels, int64_t out_channels, int64_t stride = 1);
    
    torch::Tensor forward(torch::Tensor x);

private:
    torch::nn::Conv2d conv1{nullptr};
    torch::nn::BatchNorm2d bn1{nullptr};
    torch::nn::Conv2d conv2{nullptr};
    torch::nn::BatchNorm2d bn2{nullptr};
    torch::nn::Sequential downsample{nullptr};
};

/**
 * @brief ResNet18 model
 */
class ResNet18Model : public ModelBase {
public:
    ResNet18Model(int64_t num_classes = 10);
    
    torch::Tensor forward(torch::Tensor input) override;
    std::string name() const override { return "resnet18"; }

private:
    torch::nn::Conv2d conv1{nullptr};
    torch::nn::BatchNorm2d bn1{nullptr};
    torch::nn::Sequential layer1{nullptr};
    torch::nn::Sequential layer2{nullptr};
    torch::nn::Sequential layer3{nullptr};
    torch::nn::Sequential layer4{nullptr};
    torch::nn::Linear fc{nullptr};
    
    torch::nn::Sequential make_layer(int64_t out_channels, int64_t num_blocks, int64_t stride = 1);
    int64_t in_channels_ = 64;
};

} // namespace models
} // namespace meshml
