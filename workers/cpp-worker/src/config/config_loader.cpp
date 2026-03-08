#include "meshml/config/config_loader.h"
#include <fstream>
#include <sstream>
#include <regex>
#include <algorithm>

namespace meshml {
namespace config {

// Simple YAML/JSON parser (simplified implementation)
// For production, consider using yaml-cpp or nlohmann/json libraries

namespace {

// Trim whitespace from string
std::string trim(const std::string& str) {
    size_t start = str.find_first_not_of(" \t\n\r");
    if (start == std::string::npos) return "";
    size_t end = str.find_last_not_of(" \t\n\r");
    return str.substr(start, end - start + 1);
}

// Parse a simple YAML/JSON value
ConfigValue parse_value(const std::string& value) {
    std::string trimmed = trim(value);
    
    // Boolean
    if (trimmed == "true" || trimmed == "True" || trimmed == "TRUE") {
        return ConfigValue(true);
    }
    if (trimmed == "false" || trimmed == "False" || trimmed == "FALSE") {
        return ConfigValue(false);
    }
    
    // Integer
    if (std::regex_match(trimmed, std::regex("^-?[0-9]+$"))) {
        return ConfigValue(std::stoll(trimmed));
    }
    
    // Float
    if (std::regex_match(trimmed, std::regex("^-?[0-9]+\\.[0-9]+([eE][+-]?[0-9]+)?$"))) {
        return ConfigValue(std::stod(trimmed));
    }
    
    // String (remove quotes if present)
    if ((trimmed.front() == '"' && trimmed.back() == '"') ||
        (trimmed.front() == '\'' && trimmed.back() == '\'')) {
        return ConfigValue(trimmed.substr(1, trimmed.length() - 2));
    }
    
    // Default to string
    return ConfigValue(trimmed);
}

// Simple YAML parser
std::unordered_map<std::string, ConfigValue> parse_yaml_simple(const std::string& content) {
    std::unordered_map<std::string, ConfigValue> result;
    std::istringstream stream(content);
    std::string line;
    std::string current_section;
    
    while (std::getline(stream, line)) {
        // Skip comments and empty lines
        if (line.empty() || line[0] == '#') continue;
        
        // Check for section (indentation level 0)
        if (line[0] != ' ' && line.find(':') != std::string::npos) {
            size_t colon = line.find(':');
            current_section = trim(line.substr(0, colon));
            
            // Check if section has inline value
            if (colon + 1 < line.length()) {
                std::string value = line.substr(colon + 1);
                if (!trim(value).empty()) {
                    result[current_section] = parse_value(value);
                }
            }
            continue;
        }
        
        // Parse key-value pair (indented)
        if (line[0] == ' ' && line.find(':') != std::string::npos) {
            size_t colon = line.find(':');
            std::string key = trim(line.substr(0, colon));
            std::string value = line.substr(colon + 1);
            
            if (!current_section.empty()) {
                key = current_section + "." + key;
            }
            
            result[key] = parse_value(value);
        }
    }
    
    return result;
}

// Helper to get value with default
template<typename T>
T get_or_default(const std::unordered_map<std::string, ConfigValue>& map, 
                  const std::string& key, 
                  const T& default_value) {
    auto it = map.find(key);
    if (it == map.end()) return default_value;
    
    if constexpr (std::is_same_v<T, std::string>) {
        return it->second.try_string().value_or(default_value);
    } else if constexpr (std::is_same_v<T, int64_t>) {
        return it->second.try_int().value_or(default_value);
    } else if constexpr (std::is_same_v<T, double>) {
        return it->second.try_float().value_or(default_value);
    } else if constexpr (std::is_same_v<T, bool>) {
        return it->second.try_bool().value_or(default_value);
    }
    return default_value;
}

} // anonymous namespace

// WorkerConfig implementation
bool WorkerConfig::validate() const {
    // Validate worker identity
    if (worker.worker_id.empty()) {
        return false;
    }
    
    // Validate training config
    if (training.learning_rate <= 0.0) {
        return false;
    }
    if (training.batch_size <= 0) {
        return false;
    }
    if (training.num_epochs <= 0) {
        return false;
    }
    if (training.num_workers < 0) {
        return false;
    }
    
    // Validate device
    std::vector<std::string> valid_devices = {"cpu", "cuda", "mps"};
    if (std::find(valid_devices.begin(), valid_devices.end(), training.device) == valid_devices.end()) {
        return false;
    }
    
    // Validate optimizer
    std::vector<std::string> valid_optimizers = {"sgd", "adam", "adamw", "rmsprop"};
    if (std::find(valid_optimizers.begin(), valid_optimizers.end(), training.optimizer) == valid_optimizers.end()) {
        return false;
    }
    
    // Validate port
    if (training.server_port <= 0 || training.server_port > 65535) {
        return false;
    }
    
    return true;
}

void WorkerConfig::to_yaml(const std::string& filepath) const {
    std::ofstream file(filepath);
    if (!file.is_open()) {
        throw ConfigurationError("Cannot create file: " + filepath);
    }
    
    file << "# MeshML C++ Worker Configuration\n\n";
    file << "worker:\n";
    file << "  worker_id: " << worker.worker_id << "\n";
    file << "  group_id: " << worker.group_id << "\n";
    file << "  num_workers: " << worker.num_workers << "\n";
    file << "  num_threads: " << worker.num_threads << "\n";
    file << "\n";
    file << "training:\n";
    file << "  model_name: \"" << training.model_name << "\"\n";
    file << "  model_type: \"" << training.model_type << "\"\n";
    file << "  learning_rate: " << training.learning_rate << "\n";
    file << "  batch_size: " << training.batch_size << "\n";
    file << "  num_epochs: " << training.num_epochs << "\n";
    file << "  optimizer: " << training.optimizer << "\n";
    file << "  device: " << training.device << "\n";
    file << "  server_port: " << training.server_port << "\n";
}

void WorkerConfig::to_json(const std::string& filepath) const {
    std::ofstream file(filepath);
    if (!file.is_open()) {
        throw ConfigurationError("Cannot create file: " + filepath);
    }
    
    file << "{\n";
    file << "  \"worker\": {\n";
    file << "    \"worker_id\": \"" << worker.worker_id << "\",\n";
    file << "    \"group_id\": \"" << worker.group_id << "\",\n";
    file << "    \"num_workers\": " << worker.num_workers << ",\n";
    file << "    \"num_threads\": " << worker.num_threads << "\n";
    file << "  },\n";
    file << "  \"training\": {\n";
    file << "    \"model_name\": \"" << training.model_name << "\",\n";
    file << "    \"model_type\": \"" << training.model_type << "\",\n";
    file << "    \"learning_rate\": " << training.learning_rate << ",\n";
    file << "    \"batch_size\": " << training.batch_size << ",\n";
    file << "    \"num_epochs\": " << training.num_epochs << ",\n";
    file << "    \"optimizer\": \"" << training.optimizer << "\",\n";
    file << "    \"device\": \"" << training.device << "\",\n";
    file << "    \"server_port\": " << training.server_port << "\n";
    file << "  }\n";
    file << "}\n";
}

// ConfigValue implementation
std::string ConfigValue::as_string() const {
    if (type_ != Type::STRING) {
        throw ConfigurationError("Value is not a string");
    }
    return string_value_;
}

int64_t ConfigValue::as_int() const {
    if (type_ != Type::INTEGER) {
        throw ConfigurationError("Value is not an integer");
    }
    return int_value_;
}

double ConfigValue::as_float() const {
    if (type_ != Type::FLOAT) {
        throw ConfigurationError("Value is not a float");
    }
    return float_value_;
}

bool ConfigValue::as_bool() const {
    if (type_ != Type::BOOLEAN) {
        throw ConfigurationError("Value is not a boolean");
    }
    return bool_value_;
}

std::vector<ConfigValue> ConfigValue::as_array() const {
    if (type_ != Type::ARRAY) {
        throw ConfigurationError("Value is not an array");
    }
    return array_value_;
}

std::unordered_map<std::string, ConfigValue> ConfigValue::as_object() const {
    if (type_ != Type::OBJECT) {
        throw ConfigurationError("Value is not an object");
    }
    return object_value_;
}

std::optional<std::string> ConfigValue::try_string() const {
    if (type_ == Type::STRING) return string_value_;
    return std::nullopt;
}

std::optional<int64_t> ConfigValue::try_int() const {
    if (type_ == Type::INTEGER) return int_value_;
    return std::nullopt;
}

std::optional<double> ConfigValue::try_float() const {
    if (type_ == Type::FLOAT) return float_value_;
    return std::nullopt;
}

std::optional<bool> ConfigValue::try_bool() const {
    if (type_ == Type::BOOLEAN) return bool_value_;
    return std::nullopt;
}

// ConfigLoader implementation
WorkerConfig ConfigLoader::from_yaml(const std::string& filepath) {
    std::ifstream file(filepath);
    if (!file.is_open()) {
        throw ConfigurationError("Cannot open file: " + filepath);
    }
    
    std::stringstream buffer;
    buffer << file.rdbuf();
    return from_yaml_string(buffer.str());
}

WorkerConfig ConfigLoader::from_json(const std::string& filepath) {
    std::ifstream file(filepath);
    if (!file.is_open()) {
        throw ConfigurationError("Cannot open file: " + filepath);
    }
    
    std::stringstream buffer;
    buffer << file.rdbuf();
    return from_json_string(buffer.str());
}

WorkerConfig ConfigLoader::from_yaml_string(const std::string& yaml_content) {
    return parse_yaml_content(yaml_content);
}

WorkerConfig ConfigLoader::from_json_string(const std::string& json_content) {
    return parse_json_content(json_content);
}

WorkerConfig ConfigLoader::merge(const WorkerConfig& base, const WorkerConfig& override) {
    WorkerConfig result = base;
    
    // Merge worker info
    if (!override.worker.worker_id.empty()) result.worker.worker_id = override.worker.worker_id;
    if (!override.worker.group_id.empty()) result.worker.group_id = override.worker.group_id;
    if (override.worker.num_workers > 0) result.worker.num_workers = override.worker.num_workers;
    if (override.worker.num_threads > 0) result.worker.num_threads = override.worker.num_threads;
    
    // Merge training config
    if (!override.training.model_name.empty()) result.training.model_name = override.training.model_name;
    if (override.training.learning_rate > 0) result.training.learning_rate = override.training.learning_rate;
    if (override.training.batch_size > 0) result.training.batch_size = override.training.batch_size;
    if (override.training.num_epochs > 0) result.training.num_epochs = override.training.num_epochs;
    if (!override.training.optimizer.empty()) result.training.optimizer = override.training.optimizer;
    if (!override.training.device.empty()) result.training.device = override.training.device;
    
    return result;
}

std::string ConfigLoader::to_yaml(const WorkerConfig& config) {
    std::ostringstream yaml;
    
    yaml << "# MeshML C++ Worker Configuration\n\n";
    yaml << "worker:\n";
    yaml << "  worker_id: " << config.worker.worker_id << "\n";
    yaml << "  group_id: " << config.worker.group_id << "\n";
    yaml << "  num_workers: " << config.worker.num_workers << "\n";
    yaml << "  num_threads: " << config.worker.num_threads << "\n";
    yaml << "\n";
    yaml << "training:\n";
    yaml << "  model_name: " << config.training.model_name << "\n";
    yaml << "  model_type: " << config.training.model_type << "\n";
    yaml << "  learning_rate: " << config.training.learning_rate << "\n";
    yaml << "  batch_size: " << config.training.batch_size << "\n";
    yaml << "  num_epochs: " << config.training.num_epochs << "\n";
    yaml << "  optimizer: " << config.training.optimizer << "\n";
    yaml << "  device: " << config.training.device << "\n";
    yaml << "  server_port: " << config.training.server_port << "\n";
    
    return yaml.str();
}

std::string ConfigLoader::to_json(const WorkerConfig& config) {
    std::ostringstream json;
    
    json << "{\n";
    json << "  \"worker\": {\n";
    json << "    \"worker_id\": \"" << config.worker.worker_id << "\",\n";
    json << "    \"group_id\": \"" << config.worker.group_id << "\",\n";
    json << "    \"num_workers\": " << config.worker.num_workers << ",\n";
    json << "    \"num_threads\": " << config.worker.num_threads << "\n";
    json << "  },\n";
    json << "  \"training\": {\n";
    json << "    \"model_name\": \"" << config.training.model_name << "\",\n";
    json << "    \"model_type\": \"" << config.training.model_type << "\",\n";
    json << "    \"learning_rate\": " << config.training.learning_rate << ",\n";
    json << "    \"batch_size\": " << config.training.batch_size << ",\n";
    json << "    \"num_epochs\": " << config.training.num_epochs << ",\n";
    json << "    \"optimizer\": \"" << config.training.optimizer << "\",\n";
    json << "    \"device\": \"" << config.training.device << "\",\n";
    json << "    \"server_port\": " << config.training.server_port << "\n";
    json << "  }\n";
    json << "}\n";
    
    return json.str();
}

WorkerConfig ConfigLoader::parse_yaml_content(const std::string& content) {
    auto parsed = parse_yaml_simple(content);
    
    WorkerConfig config;
    
    // Worker config
    config.worker.worker_id = get_or_default(parsed, "worker.worker_id", std::string(""));
    config.worker.group_id = get_or_default(parsed, "worker.group_id", std::string(""));
    config.worker.num_workers = get_or_default(parsed, "worker.num_workers", int64_t(1));
    config.worker.num_threads = get_or_default(parsed, "worker.num_threads", int64_t(0));
    
    // Training config
    config.training.model_name = get_or_default(parsed, "training.model_name", std::string(""));
    config.training.model_type = get_or_default(parsed, "training.model_type", std::string(""));
    config.training.learning_rate = get_or_default(parsed, "training.learning_rate", 0.001);
    config.training.batch_size = get_or_default(parsed, "training.batch_size", int64_t(32));
    config.training.num_epochs = get_or_default(parsed, "training.num_epochs", int64_t(10));
    config.training.optimizer = get_or_default(parsed, "training.optimizer", std::string("adam"));
    config.training.weight_decay = get_or_default(parsed, "training.weight_decay", 0.0);
    config.training.momentum = get_or_default(parsed, "training.momentum", 0.9);
    
    // Data config
    config.training.data_path = get_or_default(parsed, "training.data_path", std::string(""));
    config.training.num_workers = get_or_default(parsed, "training.num_workers", int64_t(4));
    config.training.shuffle = get_or_default(parsed, "training.shuffle", true);
    config.training.pin_memory = get_or_default(parsed, "training.pin_memory", true);
    
    // Device config
    config.training.device = get_or_default(parsed, "training.device", std::string("cpu"));
    config.training.mixed_precision = get_or_default(parsed, "training.mixed_precision", false);
    
    // Checkpoint config
    config.training.checkpoint_dir = get_or_default(parsed, "training.checkpoint_dir", std::string("./checkpoints"));
    config.training.checkpoint_interval = get_or_default(parsed, "training.checkpoint_interval", int64_t(100));
    config.training.save_best_only = get_or_default(parsed, "training.save_best_only", true);
    
    // Logging config
    config.training.log_interval = get_or_default(parsed, "training.log_interval", int64_t(10));
    config.training.verbose = get_or_default(parsed, "training.verbose", true);
    
    // Parameter Server config
    config.training.ps_host = get_or_default(parsed, "training.ps_host", std::string("localhost"));
    config.training.ps_port = get_or_default(parsed, "training.ps_port", int64_t(50051));
    config.training.server_port = get_or_default(parsed, "training.server_port", int64_t(50051));
    config.training.heartbeat_interval = get_or_default(parsed, "training.heartbeat_interval", int64_t(5));
    config.training.compression_enabled = get_or_default(parsed, "training.compression_enabled", true);
    config.training.compression_threshold = get_or_default(parsed, "training.compression_threshold", 0.1);
    
    return config;
}

WorkerConfig ConfigLoader::parse_json_content(const std::string& content) {
    // For simplicity, JSON parsing uses same logic as YAML
    return parse_yaml_content(content);
}

} // namespace config
} // namespace meshml
