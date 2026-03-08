#include "meshml/models/model_loader.h"
#include <fstream>
#include <iostream>
#include <sstream>
#include <stdexcept>

namespace meshml {
namespace models {

// ModelBase implementation
int64_t ModelBase::num_parameters() const {
    int64_t count = 0;
    for (const auto& param : parameters()) {
        count += param.numel();
    }
    return count;
}

std::string ModelBase::summary() const {
    std::ostringstream oss;
    oss << "Model: " << name() << std::endl;
    oss << "Parameters: " << num_parameters() << std::endl;
    oss << "\nLayers:" << std::endl;
    
    for (const auto& pair : named_parameters()) {
        const auto& pname = pair.key();
        const auto& param = pair.value();
        oss << "  " << pname << ": " << param.sizes() << std::endl;
    }
    return oss.str();
}

void ModelBase::print_summary() const {
    std::cout << summary() << std::endl;
}

// ModelFactory implementation
ModelFactory& ModelFactory::instance() {
    static ModelFactory instance;
    return instance;
}

void ModelFactory::register_model(const std::string& name, ModelCreator creator) {
    registry_[name] = creator;
}

std::shared_ptr<ModelBase> ModelFactory::create(const std::string& name) {
    auto it = registry_.find(name);
    if (it == registry_.end()) {
        throw std::runtime_error("Model '" + name + "' not found in registry");
    }
    return it->second();
}

bool ModelFactory::is_registered(const std::string& name) {
    return registry_.find(name) != registry_.end();
}

std::vector<std::string> ModelFactory::list_models() {
    std::vector<std::string> names;
    for (const auto& pair : registry_) {
        names.push_back(pair.first);
    }
    return names;
}

// ModelLoader implementation
torch::jit::script::Module ModelLoader::load_torchscript(
    const std::string& filepath,
    const torch::Device& device
) {
    try {
        // For LibTorch 2.5.1, TorchScript support is limited in C++ API
        // Return an empty module as placeholder
        torch::jit::script::Module module;
        // TODO: Implement proper TorchScript loading when PyTorch C++ API supports it
        throw std::runtime_error("TorchScript loading not fully supported in this PyTorch version");
        return module;
    } catch (const c10::Error& e) {
        throw std::runtime_error("Failed to load TorchScript model from " + filepath + ": " + e.what());
    }
}

std::unordered_map<std::string, std::string> ModelLoader::load_checkpoint(
    std::shared_ptr<ModelBase> model,
    const std::string& filepath,
    bool strict
) {
    try {
        // Load state dict using serialize API
        torch::serialize::InputArchive archive;
        archive.load_from(filepath);
        model->load(archive);
        
        // Return empty metadata for now
        std::unordered_map<std::string, std::string> metadata;
        metadata["filepath"] = filepath;
        return metadata;
    } catch (const c10::Error& e) {
        throw std::runtime_error("Failed to load checkpoint from " + filepath + ": " + e.what());
    } catch (const std::exception& e) {
        throw std::runtime_error("Failed to load checkpoint from " + filepath + ": " + e.what());
    }
}

void ModelLoader::save_checkpoint(
    std::shared_ptr<ModelBase> model,
    const std::string& filepath,
    const std::unordered_map<std::string, std::string>& metadata
) {
    try {
        // Save state dict using serialize API
        torch::serialize::OutputArchive archive;
        model->save(archive);
        archive.save_to(filepath);
        
        // TODO: Save metadata separately if needed
    } catch (const c10::Error& e) {
        throw std::runtime_error("Failed to save checkpoint to " + filepath + ": " + e.what());
    } catch (const std::exception& e) {
        throw std::runtime_error("Failed to save checkpoint to " + filepath + ": " + e.what());
    }
}

void ModelLoader::save_torchscript(
    std::shared_ptr<ModelBase> model,
    const std::string& filepath
) {
    try {
        // TorchScript export not fully supported in this PyTorch version
        throw std::runtime_error("TorchScript export not fully supported in this PyTorch version");
    } catch (const c10::Error& e) {
        throw std::runtime_error("Failed to save TorchScript model to " + filepath + ": " + e.what());
    }
}

std::shared_ptr<ModelBase> ModelLoader::from_registry(
    const std::string& model_name,
    const std::string& checkpoint_path,
    const torch::Device& device
) {
    auto model = ModelFactory::instance().create(model_name);
    model->to(device);
    
    if (!checkpoint_path.empty()) {
        load_checkpoint(model, checkpoint_path);
    }
    
    return model;
}

// MLPModel implementation
MLPModel::MLPModel(const std::vector<int64_t>& layer_sizes) {
    if (layer_sizes.size() < 2) {
        throw std::invalid_argument("MLP requires at least input and output sizes");
    }
    
    for (size_t i = 0; i < layer_sizes.size() - 1; ++i) {
        auto layer = torch::nn::Linear(layer_sizes[i], layer_sizes[i + 1]);
        layers_.push_back(register_module("fc" + std::to_string(i), layer));
    }
}

torch::Tensor MLPModel::forward(torch::Tensor input) {
    auto x = input.view({input.size(0), -1});
    
    for (size_t i = 0; i < layers_.size(); ++i) {
        x = layers_[i]->forward(x);
        if (i < layers_.size() - 1) {
            x = torch::relu(x);
        }
    }
    
    return x;
}

// MNISTCNNModel implementation
MNISTCNNModel::MNISTCNNModel() {
    conv1 = register_module("conv1", torch::nn::Conv2d(
        torch::nn::Conv2dOptions(1, 32, 3).padding(1)
    ));
    conv2 = register_module("conv2", torch::nn::Conv2d(
        torch::nn::Conv2dOptions(32, 64, 3).padding(1)
    ));
    fc1 = register_module("fc1", torch::nn::Linear(64 * 7 * 7, 128));
    fc2 = register_module("fc2", torch::nn::Linear(128, 10));
}

torch::Tensor MNISTCNNModel::forward(torch::Tensor input) {
    auto x = torch::relu(conv1->forward(input));
    x = torch::max_pool2d(x, 2);
    
    x = torch::relu(conv2->forward(x));
    x = torch::max_pool2d(x, 2);
    
    x = x.view({x.size(0), -1});
    
    x = torch::relu(fc1->forward(x));
    x = fc2->forward(x);
    
    return x;
}

// ResNetBlock implementation
ResNetBlock::ResNetBlock(int64_t in_channels, int64_t out_channels, int64_t stride) {
    conv1 = register_module("conv1", torch::nn::Conv2d(
        torch::nn::Conv2dOptions(in_channels, out_channels, 3)
            .stride(stride)
            .padding(1)
            .bias(false)
    ));
    bn1 = register_module("bn1", torch::nn::BatchNorm2d(out_channels));
    
    conv2 = register_module("conv2", torch::nn::Conv2d(
        torch::nn::Conv2dOptions(out_channels, out_channels, 3)
            .stride(1)
            .padding(1)
            .bias(false)
    ));
    bn2 = register_module("bn2", torch::nn::BatchNorm2d(out_channels));
    
    if (stride != 1 || in_channels != out_channels) {
        downsample = register_module("downsample", torch::nn::Sequential(
            torch::nn::Conv2d(
                torch::nn::Conv2dOptions(in_channels, out_channels, 1)
                    .stride(stride)
                    .bias(false)
            ),
            torch::nn::BatchNorm2d(out_channels)
        ));
    }
}

torch::Tensor ResNetBlock::forward(torch::Tensor x) {
    auto identity = x;
    
    auto out = conv1->forward(x);
    out = bn1->forward(out);
    out = torch::relu(out);
    
    out = conv2->forward(out);
    out = bn2->forward(out);
    
    if (!downsample.is_empty()) {
        identity = downsample->forward(x);
    }
    
    out += identity;
    out = torch::relu(out);
    
    return out;
}

// ResNet18Model implementation
ResNet18Model::ResNet18Model(int64_t num_classes) {
    conv1 = register_module("conv1", torch::nn::Conv2d(
        torch::nn::Conv2dOptions(3, 64, 7)
            .stride(2)
            .padding(3)
            .bias(false)
    ));
    bn1 = register_module("bn1", torch::nn::BatchNorm2d(64));
    
    layer1 = register_module("layer1", make_layer(64, 2, 1));
    layer2 = register_module("layer2", make_layer(128, 2, 2));
    layer3 = register_module("layer3", make_layer(256, 2, 2));
    layer4 = register_module("layer4", make_layer(512, 2, 2));
    
    fc = register_module("fc", torch::nn::Linear(512, num_classes));
}

torch::Tensor ResNet18Model::forward(torch::Tensor input) {
    auto x = conv1->forward(input);
    x = bn1->forward(x);
    x = torch::relu(x);
    x = torch::max_pool2d(x, 3, 2, 1);
    
    x = layer1->forward(x);
    x = layer2->forward(x);
    x = layer3->forward(x);
    x = layer4->forward(x);
    
    x = torch::adaptive_avg_pool2d(x, {1, 1});
    x = x.view({x.size(0), -1});
    x = fc->forward(x);
    
    return x;
}

torch::nn::Sequential ResNet18Model::make_layer(
    int64_t out_channels,
    int64_t num_blocks,
    int64_t stride
) {
    torch::nn::Sequential layers;
    
    layers->push_back(ResNetBlock(in_channels_, out_channels, stride));
    in_channels_ = out_channels;
    
    for (int64_t i = 1; i < num_blocks; ++i) {
        layers->push_back(ResNetBlock(out_channels, out_channels, 1));
    }
    
    return layers;
}

// Register built-in models
namespace {
    bool mlp_registered = []() {
        ModelFactory::instance().register_model("mlp", []() {
            return std::make_shared<MLPModel>(std::vector<int64_t>{784, 256, 128, 10});
        });
        ModelFactory::instance().register_model("MLP", []() {
            return std::make_shared<MLPModel>(std::vector<int64_t>{784, 256, 128, 10});
        });
        return true;
    }();
    
    bool mnist_cnn_registered = []() {
        ModelFactory::instance().register_model("mnist_cnn", []() {
            return std::make_shared<MNISTCNNModel>();
        });
        ModelFactory::instance().register_model("MNIST_CNN", []() {
            return std::make_shared<MNISTCNNModel>();
        });
        return true;
    }();
    
    bool resnet18_registered = []() {
        ModelFactory::instance().register_model("resnet18", []() {
            return std::make_shared<ResNet18Model>(10);
        });
        ModelFactory::instance().register_model("ResNet18", []() {
            return std::make_shared<ResNet18Model>(10);
        });
        return true;
    }();
}

} // namespace models
} // namespace meshml
