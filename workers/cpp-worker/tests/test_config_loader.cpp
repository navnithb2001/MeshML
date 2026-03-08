/**
 * @file test_config_loader.cpp
 * @brief Unit tests for configuration loader
 */

#include <gtest/gtest.h>
#include "meshml/config/config_loader.h"
#include <fstream>
#include <filesystem>

namespace fs = std::filesystem;

class ConfigLoaderTest : public ::testing::Test {
protected:
    void SetUp() override {
        // Create temp directory for test files
        temp_dir_ = fs::temp_directory_path() / "meshml_test";
        fs::create_directories(temp_dir_);
    }

    void TearDown() override {
        // Clean up temp files
        if (fs::exists(temp_dir_)) {
            fs::remove_all(temp_dir_);
        }
    }

    void WriteTestYaml(const std::string& filename, const std::string& content) {
        auto path = temp_dir_ / filename;
        std::ofstream file(path);
        file << content;
        file.close();
    }

    fs::path temp_dir_;
};

// Test: Load valid YAML configuration
TEST_F(ConfigLoaderTest, LoadValidYaml) {
    const std::string yaml_content = R"(
worker:
  worker_id: test-worker-001
  group_id: test-group
  num_workers: 4
  num_threads: 8
  
training:
  model_name: ResNet18
  batch_size: 32
  learning_rate: 0.001
  num_epochs: 10
  device: cuda
  optimizer: adam
)";

    WriteTestYaml("valid_config.yaml", yaml_content);
    auto config_path = temp_dir_ / "valid_config.yaml";

    meshml::config::ConfigLoader loader;
    auto config = loader.from_yaml(config_path.string());

    EXPECT_TRUE(config.validate());
    EXPECT_EQ(config.worker.worker_id, "test-worker-001");
    EXPECT_EQ(config.worker.group_id, "test-group");
    EXPECT_EQ(config.worker.num_workers, 4);
    EXPECT_EQ(config.training.model_name, "ResNet18");
    EXPECT_EQ(config.training.batch_size, 32);
    EXPECT_FLOAT_EQ(config.training.learning_rate, 0.001f);
}

// Test: Load minimal configuration with defaults
TEST_F(ConfigLoaderTest, LoadMinimalConfig) {
    const std::string yaml_content = R"(
worker:
  worker_id: minimal-worker
  
training:
  model_name: MLP
)";

    WriteTestYaml("minimal_config.yaml", yaml_content);
    auto config_path = temp_dir_ / "minimal_config.yaml";

    meshml::config::ConfigLoader loader;
    auto config = loader.from_yaml(config_path.string());

    // Should have defaults
    EXPECT_EQ(config.worker.num_threads, 0);  // Auto-detect
    EXPECT_EQ(config.training.batch_size, 32);  // Default
    EXPECT_EQ(config.training.device, "cpu");  // Default
}

// Test: Validation - missing required field
TEST_F(ConfigLoaderTest, ValidationMissingWorkerID) {
    meshml::config::WorkerConfig config;
    config.worker.worker_id = "";  // Missing
    config.training.model_name = "MLP";

    EXPECT_FALSE(config.validate());
}

// Test: Validation - invalid learning rate
TEST_F(ConfigLoaderTest, ValidationInvalidLearningRate) {
    meshml::config::WorkerConfig config;
    config.worker.worker_id = "test-worker";
    config.training.model_name = "MLP";
    config.training.learning_rate = -0.1f;  // Invalid

    EXPECT_FALSE(config.validate());
}

// Test: Validation - invalid batch size
TEST_F(ConfigLoaderTest, ValidationInvalidBatchSize) {
    meshml::config::WorkerConfig config;
    config.worker.worker_id = "test-worker";
    config.training.model_name = "MLP";
    config.training.batch_size = 0;  // Invalid

    EXPECT_FALSE(config.validate());
}

// Test: Validation - invalid device
TEST_F(ConfigLoaderTest, ValidationInvalidDevice) {
    meshml::config::WorkerConfig config;
    config.worker.worker_id = "test-worker";
    config.training.model_name = "MLP";
    config.training.device = "invalid_device";  // Invalid

    EXPECT_FALSE(config.validate());
}

// Test: Validation - invalid optimizer
TEST_F(ConfigLoaderTest, ValidationInvalidOptimizer) {
    meshml::config::WorkerConfig config;
    config.worker.worker_id = "test-worker";
    config.training.model_name = "MLP";
    config.training.optimizer = "invalid_opt";  // Invalid

    EXPECT_FALSE(config.validate());
}

// Test: Validation - invalid port
TEST_F(ConfigLoaderTest, ValidationInvalidPort) {
    meshml::config::WorkerConfig config;
    config.worker.worker_id = "test-worker";
    config.training.model_name = "MLP";
    config.training.server_port = 70000;  // Invalid (> 65535)

    EXPECT_FALSE(config.validate());
}

// Test: Configuration merging
TEST_F(ConfigLoaderTest, MergeConfigurations) {
    meshml::config::WorkerConfig base;
    base.worker.worker_id = "worker-1";
    base.training.model_name = "MLP";
    base.training.batch_size = 32;
    base.training.learning_rate = 0.001f;

    meshml::config::WorkerConfig override;
    override.training.batch_size = 64;  // Override
    override.training.num_epochs = 20;  // New value

    meshml::config::ConfigLoader loader;
    auto merged = loader.merge(base, override);

    EXPECT_EQ(merged.worker.worker_id, "worker-1");  // From base
    EXPECT_EQ(merged.training.model_name, "MLP");     // From base
    EXPECT_EQ(merged.training.batch_size, 64);        // Overridden
    EXPECT_EQ(merged.training.num_epochs, 20);        // From override
}

// Test: YAML export
TEST_F(ConfigLoaderTest, ExportToYaml) {
    meshml::config::WorkerConfig config;
    config.worker.worker_id = "export-test";
    config.worker.group_id = "test-group";
    config.training.model_name = "ResNet18";
    config.training.batch_size = 64;

    meshml::config::ConfigLoader loader;
    auto yaml_str = loader.to_yaml(config);

    EXPECT_TRUE(yaml_str.find("worker_id: export-test") != std::string::npos);
    EXPECT_TRUE(yaml_str.find("group_id: test-group") != std::string::npos);
    EXPECT_TRUE(yaml_str.find("model_name: ResNet18") != std::string::npos);
    EXPECT_TRUE(yaml_str.find("batch_size: 64") != std::string::npos);
}

// Test: JSON export
TEST_F(ConfigLoaderTest, ExportToJson) {
    meshml::config::WorkerConfig config;
    config.worker.worker_id = "json-test";
    config.training.model_name = "MLP";

    meshml::config::ConfigLoader loader;
    auto json_str = loader.to_json(config);

    EXPECT_TRUE(json_str.find("\"worker_id\": \"json-test\"") != std::string::npos);
    EXPECT_TRUE(json_str.find("\"model_name\": \"MLP\"") != std::string::npos);
}

// Test: Round-trip YAML conversion
TEST_F(ConfigLoaderTest, RoundTripYaml) {
    meshml::config::WorkerConfig original;
    original.worker.worker_id = "roundtrip-test";
    original.training.model_name = "ResNet18";
    original.training.batch_size = 128;
    original.training.learning_rate = 0.01f;

    meshml::config::ConfigLoader loader;
    
    // Export to YAML
    auto yaml_str = loader.to_yaml(original);
    
    // Save and reload
    WriteTestYaml("roundtrip.yaml", yaml_str);
    auto config_path = temp_dir_ / "roundtrip.yaml";
    auto loaded = loader.from_yaml(config_path.string());

    EXPECT_EQ(loaded.worker.worker_id, original.worker.worker_id);
    EXPECT_EQ(loaded.training.model_name, original.training.model_name);
    EXPECT_EQ(loaded.training.batch_size, original.training.batch_size);
    EXPECT_FLOAT_EQ(loaded.training.learning_rate, original.training.learning_rate);
}

// Test: Load from string
TEST_F(ConfigLoaderTest, LoadFromString) {
    const std::string yaml_content = R"(
worker:
  worker_id: string-test
training:
  model_name: MLP
  batch_size: 16
)";

    meshml::config::ConfigLoader loader;
    auto config = loader.from_yaml_string(yaml_content);

    EXPECT_EQ(config.worker.worker_id, "string-test");
    EXPECT_EQ(config.training.batch_size, 16);
}

// Test: Error handling - file not found
TEST_F(ConfigLoaderTest, FileNotFound) {
    meshml::config::ConfigLoader loader;
    
    EXPECT_THROW({
        loader.from_yaml("/nonexistent/path/config.yaml");
    }, std::runtime_error);
}

// Test: Error handling - malformed YAML
TEST_F(ConfigLoaderTest, MalformedYaml) {
    const std::string bad_yaml = R"(
worker:
  worker_id: test
  invalid syntax here!!!
    random: nested
)";

    WriteTestYaml("malformed.yaml", bad_yaml);
    auto config_path = temp_dir_ / "malformed.yaml";

    meshml::config::ConfigLoader loader;
    
    EXPECT_THROW({
        loader.from_yaml(config_path.string());
    }, std::runtime_error);
}
