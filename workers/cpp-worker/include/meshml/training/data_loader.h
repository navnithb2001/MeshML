/**
 * @file data_loader.h
 * @brief Data loading and batching utilities
 * 
 * Features:
 * - Multi-threaded data loading
 * - Custom dataset support
 * - Batch preprocessing
 * - Data augmentation hooks
 * - Efficient memory management
 */

#pragma once

#include <torch/torch.h>
#include <string>
#include <vector>
#include <memory>
#include <functional>

namespace meshml {

/**
 * @brief Custom dataset interface
 * 
 * Users should inherit from this to implement their own datasets
 */
class CustomDataset : public torch::data::Dataset<CustomDataset> {
public:
    /**
     * @brief Get a single data sample
     * 
     * @param index Sample index
     * @return Tensor pair (input, target)
     */
    virtual torch::data::Example<> get(size_t index) override = 0;
    
    /**
     * @brief Get dataset size
     * 
     * @return Number of samples
     */
    virtual torch::optional<size_t> size() const override = 0;
    
    virtual ~CustomDataset() = default;
};

/**
 * @brief Simple tensor dataset
 * 
 * Wraps pre-loaded tensors for training
 */
class TensorDataset : public CustomDataset {
public:
    /**
     * @brief Construct from tensors
     * 
     * @param inputs Input tensor [N, ...]
     * @param targets Target tensor [N, ...]
     */
    TensorDataset(torch::Tensor inputs, torch::Tensor targets);
    
    torch::data::Example<> get(size_t index) override;
    torch::optional<size_t> size() const override;
    
private:
    torch::Tensor inputs_;
    torch::Tensor targets_;
};

/**
 * @brief MNIST dataset loader
 * 
 * Example implementation for demonstration
 */
class MNISTDataset : public CustomDataset {
public:
    /**
     * @brief Construct MNIST dataset
     * 
     * @param data_dir Directory containing MNIST data files
     * @param train True for training set, false for test set
     */
    MNISTDataset(const std::string& data_dir, bool train = true);
    
    torch::data::Example<> get(size_t index) override;
    torch::optional<size_t> size() const override;
    
private:
    std::vector<torch::Tensor> images_;
    std::vector<int64_t> labels_;
    
    void load_mnist_data(const std::string& data_dir, bool train);
};

/**
 * @brief CSV dataset loader
 * 
 * Loads tabular data from CSV files
 */
class CSVDataset : public CustomDataset {
public:
    /**
     * @brief Construct CSV dataset
     * 
     * @param csv_path Path to CSV file
     * @param target_column Name of target column
     * @param skip_header True to skip first row
     */
    CSVDataset(
        const std::string& csv_path,
        const std::string& target_column,
        bool skip_header = true
    );
    
    torch::data::Example<> get(size_t index) override;
    torch::optional<size_t> size() const override;
    
private:
    torch::Tensor features_;
    torch::Tensor targets_;
    size_t num_samples_;
    
    void load_csv(
        const std::string& csv_path,
        const std::string& target_column,
        bool skip_header
    );
};

/**
 * @brief Data augmentation callback
 * 
 * Applied to each batch before training
 */
using AugmentationCallback = std::function<torch::Tensor(const torch::Tensor&)>;

/**
 * @brief Data loader builder
 * 
 * Fluent API for creating optimized data loaders
 */
class DataLoaderBuilder {
public:
    DataLoaderBuilder();
    
    /**
     * @brief Set dataset
     */
    DataLoaderBuilder& dataset(std::shared_ptr<CustomDataset> dataset);
    
    /**
     * @brief Set batch size
     */
    DataLoaderBuilder& batch_size(size_t batch_size);
    
    /**
     * @brief Enable shuffling
     */
    DataLoaderBuilder& shuffle(bool shuffle = true);
    
    /**
     * @brief Set number of worker threads
     */
    DataLoaderBuilder& num_workers(size_t num_workers);
    
    /**
     * @brief Drop last incomplete batch
     */
    DataLoaderBuilder& drop_last(bool drop_last = true);
    
    /**
     * @brief Set pin memory (for CUDA)
     */
    DataLoaderBuilder& pin_memory(bool pin_memory = true);
    
    /**
     * @brief Add data augmentation
     */
    DataLoaderBuilder& augmentation(AugmentationCallback callback);
    
    /**
     * @brief Build the data loader
     * 
     * @return Unique pointer to data loader
     */
    std::unique_ptr<torch::data::DataLoader<>> build();
    
private:
    std::shared_ptr<CustomDataset> dataset_;
    size_t batch_size_{32};
    bool shuffle_{true};
    size_t num_workers_{4};
    bool drop_last_{false};
    bool pin_memory_{false};
    AugmentationCallback augmentation_;
};

/**
 * @brief Download data shard from storage
 * 
 * Downloads a specific data shard for this worker
 * 
 * @param shard_id Shard identifier
 * @param job_id Job identifier
 * @param storage_url Storage service URL
 * @param output_path Where to save the shard
 * @return True if successful
 */
bool download_data_shard(
    const std::string& shard_id,
    const std::string& job_id,
    const std::string& storage_url,
    const std::string& output_path
);

/**
 * @brief Load data shard into dataset
 * 
 * Loads a downloaded shard file into a dataset
 * 
 * @param shard_path Path to shard file
 * @return Dataset pointer
 */
std::shared_ptr<CustomDataset> load_data_shard(
    const std::string& shard_path
);

/**
 * @brief Common data augmentations
 */
namespace augmentations {
    /**
     * @brief Random horizontal flip
     */
    AugmentationCallback random_horizontal_flip(float p = 0.5);
    
    /**
     * @brief Random crop
     */
    AugmentationCallback random_crop(int height, int width, int padding = 4);
    
    /**
     * @brief Normalize with mean and std
     */
    AugmentationCallback normalize(
        const std::vector<float>& mean,
        const std::vector<float>& std
    );
    
    /**
     * @brief Random rotation
     */
    AugmentationCallback random_rotation(float degrees);
}

} // namespace meshml
