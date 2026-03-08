# gRPC Client Examples

## Basic Usage

### Initialize and Connect

```cpp
#include "meshml/grpc/client.h"
#include "meshml/grpc/heartbeat.h"
#include <iostream>

using namespace meshml;

int main() {
    // Create gRPC client
    GRPCClient client("localhost:50051", 30);
    
    // Connect to Parameter Server
    if (!client.connect()) {
        std::cerr << "Failed to connect to Parameter Server" << std::endl;
        return 1;
    }
    
    std::cout << "Connected successfully!" << std::endl;
    
    // Use client...
    
    // Disconnect
    client.disconnect();
    return 0;
}
```

### Fetch Weights

```cpp
// Get initial weights from Parameter Server
auto [weights, version] = client.get_weights(
    "job-123",      // job_id
    "worker-001",   // worker_id
    0               // epoch
);

std::cout << "Received weights version: " << version << std::endl;
std::cout << "Number of parameter tensors: " << weights.size() << std::endl;

// Apply weights to model
for (const auto& [name, data] : weights) {
    std::cout << "Parameter: " << name 
              << ", size: " << data.size() << std::endl;
    // Load into model...
}
```

### Push Gradients

```cpp
// Compute gradients (from training loop)
std::map<std::string, std::vector<float>> gradients;
gradients["layer1.weight"] = {/* gradient values */};
gradients["layer1.bias"] = {/* gradient values */};

// Prepare metadata
std::map<std::string, float> metadata;
metadata["loss"] = 0.523f;
metadata["gradient_norm"] = 1.234f;
metadata["computation_time_ms"] = 150.0f;

// Push gradients to Parameter Server
auto response = client.push_gradients(
    "job-123",          // job_id
    "worker-001",       // worker_id
    gradients,          // gradient tensors
    42,                 // batch_id
    5,                  // epoch
    32,                 // batch_size
    0.001f,             // learning_rate
    metadata            // additional metadata
);

if (response["success"] == "true") {
    std::cout << "Gradients pushed successfully!" << std::endl;
    std::cout << "New version: " << response["new_version"] << std::endl;
}
```

### Check Model Version

```cpp
auto version_info = client.get_model_version("job-123");

std::cout << "Current version: " << version_info["current_version"] << std::endl;
std::cout << "Total updates: " << version_info["total_updates"] << std::endl;
std::cout << "Last update: " << version_info["last_update_timestamp"] << std::endl;
```

## Heartbeat Usage

### Basic Heartbeat

```cpp
// Create heartbeat sender
auto heartbeat = create_heartbeat_sender("worker-001", 30);

// Set callback for sending heartbeat
heartbeat->set_heartbeat_callback([](const auto& data) {
    // Send heartbeat via HTTP, gRPC, or any other method
    std::cout << "Sending heartbeat:" << std::endl;
    for (const auto& [key, value] : data) {
        std::cout << "  " << key << ": " << value << std::endl;
    }
    return true; // Return true if sent successfully
});

// Start heartbeat
heartbeat->start();

// Do work...
std::this_thread::sleep_for(std::chrono::seconds(10));

// Stop heartbeat
heartbeat->stop();
```

### Update Worker Status

```cpp
auto heartbeat = create_heartbeat_sender("worker-001", 30);

// Set callback
heartbeat->set_heartbeat_callback([](const auto& data) {
    // Send to server...
    return true;
});

heartbeat->start();

// Update status during training
heartbeat->update_status("state", "training");
heartbeat->update_status("current_epoch", "5");
heartbeat->update_status("loss", "0.523");

// Update multiple fields at once
std::map<std::string, std::string> status_update = {
    {"state", "training"},
    {"current_epoch", "10"},
    {"current_batch", "250"},
    {"loss", "0.234"}
};
heartbeat->update_status(status_update);

// Check health
if (heartbeat->is_healthy()) {
    std::cout << "Worker is healthy" << std::endl;
}

// Get last heartbeat time
auto last_time = heartbeat->get_last_heartbeat_time();
std::cout << "Last heartbeat: " << last_time << std::endl;
```

## Complete Training Example

```cpp
#include "meshml/grpc/client.h"
#include "meshml/grpc/heartbeat.h"
#include <torch/torch.h>
#include <iostream>

int main() {
    // 1. Initialize gRPC client
    GRPCClient client("localhost:50051", 30);
    if (!client.connect()) {
        return 1;
    }
    
    // 2. Start heartbeat
    auto heartbeat = create_heartbeat_sender("worker-001", 30);
    heartbeat->set_heartbeat_callback([&client](const auto& data) {
        // In production, send via gRPC
        std::cout << "Heartbeat sent" << std::endl;
        return true;
    });
    heartbeat->start();
    
    // 3. Fetch initial weights
    auto [weights, version] = client.get_weights("job-123", "worker-001", 0);
    std::cout << "Fetched weights version: " << version << std::endl;
    
    // 4. Training loop
    const int num_epochs = 10;
    for (int epoch = 0; epoch < num_epochs; ++epoch) {
        heartbeat->update_status("state", "training");
        heartbeat->update_status("current_epoch", std::to_string(epoch));
        
        // Simulate training
        std::map<std::string, std::vector<float>> gradients;
        // ... compute gradients ...
        
        // Push gradients
        std::map<std::string, float> metadata;
        metadata["loss"] = 0.5f - (epoch * 0.02f); // Simulated decreasing loss
        metadata["gradient_norm"] = 1.0f;
        
        auto response = client.push_gradients(
            "job-123",
            "worker-001",
            gradients,
            epoch * 100,  // batch_id
            epoch,
            32,
            0.001f,
            metadata
        );
        
        std::cout << "Epoch " << epoch << " completed, "
                  << "new version: " << response["new_version"] << std::endl;
    }
    
    // 5. Cleanup
    heartbeat->update_status("state", "idle");
    heartbeat->stop();
    client.disconnect();
    
    return 0;
}
```

## Error Handling

### Connection Errors

```cpp
GRPCClient client("localhost:50051", 30);

try {
    if (!client.connect()) {
        std::cerr << "Connection failed" << std::endl;
        // Handle connection failure
        return 1;
    }
} catch (const std::exception& e) {
    std::cerr << "Exception during connection: " << e.what() << std::endl;
    return 1;
}
```

### Operation Errors

```cpp
try {
    auto [weights, version] = client.get_weights("job-123", "worker-001", 0);
    // Use weights...
} catch (const std::runtime_error& e) {
    std::cerr << "Failed to fetch weights: " << e.what() << std::endl;
    // Handle error - maybe retry?
}

try {
    auto response = client.push_gradients(/*...*/);
    // Check response...
} catch (const std::runtime_error& e) {
    std::cerr << "Failed to push gradients: " << e.what() << std::endl;
    // Handle error - queue for retry?
}
```

### Heartbeat Health Monitoring

```cpp
auto heartbeat = create_heartbeat_sender("worker-001", 30);
heartbeat->set_heartbeat_callback([](const auto& data) {
    // Send heartbeat...
    return true;
});
heartbeat->start();

// Periodically check health
while (training) {
    // ... training code ...
    
    if (!heartbeat->is_healthy()) {
        std::cerr << "WARNING: Heartbeat unhealthy!" << std::endl;
        // Take action - reconnect, alert, etc.
    }
    
    std::this_thread::sleep_for(std::chrono::seconds(5));
}
```

## Advanced Usage

### Custom Compression

```cpp
// The client automatically handles compression
// Compression is only used if it reduces size by >10%

// Example: Large gradient tensor
std::vector<float> large_gradient(1000000, 0.001f);
std::map<std::string, std::vector<float>> gradients;
gradients["large_layer.weight"] = large_gradient;

// Client will compress before sending
auto response = client.push_gradients(/*...*/);
// Output will show compression ratio
```

### Concurrent Operations

```cpp
#include <future>

GRPCClient client("localhost:50051", 30);
client.connect();

// Fetch weights asynchronously
auto weights_future = std::async(std::launch::async, [&client]() {
    return client.get_weights("job-123", "worker-001", 0);
});

// Push gradients asynchronously
auto push_future = std::async(std::launch::async, [&client]() {
    std::map<std::string, std::vector<float>> gradients;
    // ... fill gradients ...
    return client.push_gradients("job-123", "worker-001", gradients,
                                0, 0, 32, 0.001f);
});

// Wait for both to complete
auto [weights, version] = weights_future.get();
auto response = push_future.get();
```

### RAII Pattern with Heartbeat

```cpp
class TrainingSession {
public:
    TrainingSession(const std::string& worker_id)
        : heartbeat_(create_heartbeat_sender(worker_id, 30))
    {
        heartbeat_->set_heartbeat_callback([](const auto& data) {
            // Send heartbeat...
            return true;
        });
        heartbeat_->start();
    }
    
    ~TrainingSession() {
        heartbeat_->stop();
    }
    
    void update_status(const std::string& key, const std::string& value) {
        heartbeat_->update_status(key, value);
    }
    
private:
    std::unique_ptr<HeartbeatSender> heartbeat_;
};

// Usage
{
    TrainingSession session("worker-001");
    session.update_status("state", "training");
    
    // Do training...
    
} // Heartbeat automatically stops when session goes out of scope
```

## Performance Considerations

### Gradient Batching

```cpp
// Instead of pushing gradients every batch:
std::vector<std::map<std::string, std::vector<float>>> gradient_queue;

for (int batch = 0; batch < num_batches; ++batch) {
    // Compute gradients
    auto gradients = train_batch(batch);
    gradient_queue.push_back(gradients);
    
    // Push every N batches
    if ((batch + 1) % 10 == 0) {
        // Accumulate gradients
        std::map<std::string, std::vector<float>> accumulated;
        for (const auto& grad_set : gradient_queue) {
            // Accumulate...
        }
        
        client.push_gradients(/*...*/);
        gradient_queue.clear();
    }
}
```

### Connection Pooling

```cpp
// For multiple workers in same process
class ConnectionPool {
public:
    GRPCClient& get_client(const std::string& worker_id) {
        std::lock_guard<std::mutex> lock(mutex_);
        
        if (clients_.find(worker_id) == clients_.end()) {
            clients_[worker_id] = std::make_unique<GRPCClient>(
                "localhost:50051", 30
            );
            clients_[worker_id]->connect();
        }
        
        return *clients_[worker_id];
    }
    
private:
    std::map<std::string, std::unique_ptr<GRPCClient>> clients_;
    std::mutex mutex_;
};
```

## Troubleshooting

### Connection Timeout

```cpp
// Increase timeout for slow networks
GRPCClient client("remote-server:50051", 60); // 60 second timeout

if (!client.connect()) {
    std::cerr << "Connection timeout" << std::endl;
}
```

### Heartbeat Not Sending

```cpp
auto heartbeat = create_heartbeat_sender("worker-001", 30);

// Make sure to set callback BEFORE starting
heartbeat->set_heartbeat_callback([](const auto& data) {
    std::cout << "Heartbeat callback called" << std::endl;
    return true;
});

heartbeat->start();

// Check if running
if (!heartbeat->is_running()) {
    std::cerr << "Heartbeat failed to start" << std::endl;
}
```

### Compression Issues

```cpp
// If compression is causing problems, you can disable it
// by modifying the compress_data function to always return
// the original data, or implement a flag:

// In production code:
class GRPCClient {
public:
    void set_compression_enabled(bool enabled) {
        compression_enabled_ = enabled;
    }
    
private:
    bool compression_enabled_ = true;
};
```
