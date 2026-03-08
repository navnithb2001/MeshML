#pragma once

#include <string>
#include <memory>
#include <vector>
#include <unordered_map>
#include <optional>
#include <stdexcept>

namespace meshml {
namespace config {

/**
 * @brief Configuration value that can be of different types
 */
class ConfigValue {
public:
    enum class Type {
        STRING,
        INTEGER,
        FLOAT,
        BOOLEAN,
        ARRAY,
        OBJECT
    };

    ConfigValue() : type_(Type::STRING), string_value_("") {}
    explicit ConfigValue(const std::string& value) : type_(Type::STRING), string_value_(value) {}
    explicit ConfigValue(int64_t value) : type_(Type::INTEGER), int_value_(value) {}
    explicit ConfigValue(double value) : type_(Type::FLOAT), float_value_(value) {}
    explicit ConfigValue(bool value) : type_(Type::BOOLEAN), bool_value_(value) {}

    Type get_type() const { return type_; }

    // Type-safe getters
    std::string as_string() const;
    int64_t as_int() const;
    double as_float() const;
    bool as_bool() const;
    std::vector<ConfigValue> as_array() const;
    std::unordered_map<std::string, ConfigValue> as_object() const;

    // Optional getters (return nullopt if type mismatch)
    std::optional<std::string> try_string() const;
    std::optional<int64_t> try_int() const;
    std::optional<double> try_float() const;
    std::optional<bool> try_bool() const;

    // Array/Object builders
    static ConfigValue from_array(const std::vector<ConfigValue>& array);
    static ConfigValue from_object(const std::unordered_map<std::string, ConfigValue>& object);

private:
    Type type_;
    std::string string_value_;
    int64_t int_value_{0};
    double float_value_{0.0};
    bool bool_value_{false};
    std::vector<ConfigValue> array_value_;
    std::unordered_map<std::string, ConfigValue> object_value_;
};

/**
 * @brief Worker identity and resource configuration
 */
struct WorkerInfo {
    std::string worker_id;
    std::string group_id;
    int64_t num_workers{1};
    int64_t num_threads{0};  // 0 = auto-detect
};

/**
 * @brief Training configuration structure
 */
struct TrainingConfig {
    // Model configuration
    std::string model_name;
    std::string model_type;
    std::vector<int64_t> model_layers;
    
    // Training hyperparameters
    double learning_rate{0.001};
    int64_t batch_size{32};
    int64_t num_epochs{10};
    std::string optimizer{"adam"};
    double weight_decay{0.0};
    double momentum{0.9};
    
    // Data configuration
    std::string data_path;
    int64_t num_workers{4};
    bool shuffle{true};
    bool pin_memory{true};
    
    // Device configuration
    std::string device{"cpu"};
    bool mixed_precision{false};
    
    // Checkpoint configuration
    std::string checkpoint_dir{"./checkpoints"};
    int64_t checkpoint_interval{100};
    bool save_best_only{true};
    
    // Logging configuration
    int64_t log_interval{10};
    bool verbose{true};
    
    // Parameter Server configuration
    std::string ps_host{"localhost"};
    int64_t ps_port{50051};
    int64_t server_port{50051};  // Alias for ps_port
    int64_t heartbeat_interval{5};
    bool compression_enabled{true};
    double compression_threshold{0.1};
};

/**
 * @brief Worker configuration structure
 */
struct WorkerConfig {
    // Worker configuration (nested)
    WorkerInfo worker;
    
    // Training configuration
    TrainingConfig training;
    
    // Performance settings (top-level for backwards compatibility)
    bool enable_simd{true};
    bool enable_memory_pool{true};
    bool enable_profiling{false};
    int64_t max_memory_mb{4096};
    int64_t max_cpu_cores{0};
    
    /**
     * @brief Validate configuration
     * @return True if configuration is valid
     */
    bool validate() const;
    
    /**
     * @brief Export configuration to YAML file
     */
    void to_yaml(const std::string& filepath) const;
    
    /**
     * @brief Export configuration to JSON file
     */
    void to_json(const std::string& filepath) const;
};

/**
 * @brief Configuration loader for YAML/JSON files
 * 
 * Example usage:
 * ```cpp
 * ConfigLoader loader;
 * auto config = loader.from_yaml("config.yaml");
 * if (config.validate()) {
 *     config.to_yaml("output.yaml");
 * }
 * ```
 */
class ConfigLoader {
public:
    /**
     * @brief Load configuration from YAML file
     * @param filepath Path to YAML configuration file
     * @return Loaded worker configuration
     * @throws std::runtime_error if file cannot be read or parsed
     */
    WorkerConfig from_yaml(const std::string& filepath);
    
    /**
     * @brief Load configuration from JSON file
     * @param filepath Path to JSON configuration file
     * @return Loaded worker configuration
     * @throws std::runtime_error if file cannot be read or parsed
     */
    WorkerConfig from_json(const std::string& filepath);
    
    /**
     * @brief Load configuration from YAML string
     * @param yaml_content YAML content as string
     * @return Loaded worker configuration
     * @throws std::runtime_error if parsing fails
     */
    WorkerConfig from_yaml_string(const std::string& yaml_content);
    
    /**
     * @brief Load configuration from JSON string
     * @param json_content JSON content as string
     * @return Loaded worker configuration
     * @throws std::runtime_error if parsing fails
     */
    WorkerConfig from_json_string(const std::string& json_content);
    
    /**
     * @brief Export configuration to YAML string
     * @param config Configuration to export
     * @return YAML string
     */
    std::string to_yaml(const WorkerConfig& config);
    
    /**
     * @brief Export configuration to JSON string
     * @param config Configuration to export
     * @return JSON string
     */
    std::string to_json(const WorkerConfig& config);
    
    /**
     * @brief Merge two configurations (second overrides first)
     * @param base Base configuration
     * @param override Override configuration
     * @return Merged configuration
     */
    WorkerConfig merge(const WorkerConfig& base, const WorkerConfig& override);

private:
    // Internal parsing helpers
    WorkerConfig parse_yaml_content(const std::string& content);
    WorkerConfig parse_json_content(const std::string& content);
};

/**
 * @brief Exception thrown when configuration is invalid
 */
class ConfigurationError : public std::runtime_error {
public:
    explicit ConfigurationError(const std::string& message)
        : std::runtime_error("Configuration error: " + message) {}
};

} // namespace config
} // namespace meshml
