# MeshML Python Worker

[![PyPI version](https://badge.fury.io/py/meshml-worker.svg)](https://badge.fury.io/py/meshml-worker)
[![Python 3.9+](https://img.shields.io/badge/python-3.9+-blue.svg)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

**Contribute your device to distributed machine learning training!**

MeshML Worker is a Python library that enables you to participate in federated learning networks by contributing your device's computing power to train machine learning models collaboratively.

## ✨ Features

- 🚀 **Easy Setup**: Install and start contributing in minutes
- 🔐 **Secure**: Authentication-based access control and encrypted communication
- 🎯 **Flexible**: Support for PyTorch models and custom training configurations
- 📊 **Monitored**: Real-time metrics and progress tracking
- ⚡ **Efficient**: Optimized for both CPU and GPU training
- 🌐 **Distributed**: Join global training groups and collaborate

## 🚀 Quick Start

### Installation

```bash
# Basic installation
pip install meshml-worker

# With all optional features
pip install meshml-worker[all]

# Or install specific extras
pip install meshml-worker[vision]  # For computer vision tasks
pip install meshml-worker[grpc]    # For gRPC communication
pip install meshml-worker[cloud]   # For cloud storage support
```

### Join a Training Group

1. **Register an account** on the MeshML platform (first time only):
   ```bash
   # Visit your MeshML platform URL (provided by your organization)
   # OR use API to create account
   ```

2. **Login** with your credentials:
   ```bash
   meshml-worker login --email your@email.com
   # You'll be prompted for your password
   ```

3. **Get an invitation code** from a group owner

4. **Join the group** by accepting the invitation:
   ```bash
   meshml-worker join --invitation-code inv_abc123... --worker-id my-laptop
   ```

5. **Start training**:
   ```bash
   meshml-worker start
   ```

4. **Start training**:
   ```bash
   meshml-worker start
   ```

That's it! Your device is now contributing to distributed ML training! 🎉

## 📖 Usage

### Command Line Interface

```bash
# Register a new account
meshml-worker register --email your@email.com --name "Your Name"

# Login to your account
meshml-worker login --email your@email.com

# Join a training group with invitation code
meshml-worker join --invitation-code inv_xyz789 --worker-id my-device

# Start the worker (begin training)
meshml-worker start

# Check worker status
meshml-worker status

# View training metrics
meshml-worker metrics

# Stop the worker
meshml-worker stop
```

### Python API

```python
from meshml_worker import MeshMLWorker

# Initialize worker
worker = MeshMLWorker(
    api_url="http://meshml.example.com",
    email="your@email.com",
    password="your-password",
    worker_id="my-device"
)

# Authenticate
worker.login()

# Join a group
worker.join_group(invitation_code="inv_abc123...")

# Start training
worker.start()

# Monitor progress
while worker.is_training():
    metrics = worker.get_metrics()
    print(f"Loss: {metrics['loss']}, Accuracy: {metrics['accuracy']}")
    
# Stop worker
worker.stop()
```

## 🔧 Configuration

Worker configuration is stored in `~/.meshml/config.yaml`:

```yaml
worker:
  id: "my-device"
  name: "My Worker"
  device: "cpu"  # or "cuda" for GPU
  
api:
  gateway_url: "https://api.meshml.example.com"  # Your MeshML platform URL
  
training:
  batch_size: 32
  epochs: 10
  learning_rate: 0.001
```

## 💡 How It Works

1. **Register & Login**: Create your account on the MeshML platform
2. **Join a Group**: Use an invitation code to join a training group
3. **Receive Tasks**: Your worker automatically receives training tasks from the coordinator
4. **Train Locally**: Models are trained on your local data (data never leaves your device)
5. **Share Updates**: Only model updates are sent back to the parameter server
6. **Aggregate**: Updates from all workers are combined to improve the global model

## 🔐 Security & Privacy

- **Data Privacy**: Your training data never leaves your device
- **Authentication**: Secure JWT-based authentication
- **Encrypted Communication**: All API communication over HTTPS
- **Access Control**: Role-based permissions for group management

## 📊 Monitoring

Monitor your worker's performance:

```bash
# View current status
meshml-worker status

# View detailed metrics
meshml-worker metrics --watch

# View training logs
meshml-worker logs
```

## 🛠️ Advanced Usage

### Custom Training Configuration

```python
from meshml_worker import MeshMLWorker, TrainingConfig

config = TrainingConfig(
    batch_size=64,
    epochs=20,
    learning_rate=0.01,
    device="cuda",
    num_workers=4
)

worker = MeshMLWorker(config=config)
worker.start()
```

### GPU Support

```bash
# Use GPU for training
meshml-worker start --device cuda

# Specify GPU device
meshml-worker start --device cuda:0
```

## 🤝 Contributing

We welcome contributions! Please see our [Contributing Guide](CONTRIBUTING.md) for details.

## 📝 License

This project is licensed under the MIT License - see the [LICENSE](../../LICENSE) file for details.

## 🔗 Links

- **Documentation**: https://meshml.readthedocs.io
- **GitHub**: https://github.com/navnithb2001/MeshML
- **Issues**: https://github.com/navnithb2001/MeshML/issues

## 💬 Support

- 📧 Email: bharadwajnavnith5@gmail.com
- 💬 Discord: [Join our community](https://discord.gg/meshml)
- 🐛 Issues: [GitHub Issues](https://github.com/navnithb2001/MeshML/issues)

## ⚡ Examples

Check out our [examples directory](examples/) for more use cases:

- [Computer Vision Training](examples/vision_training.py)
- [Custom Model Training](examples/custom_model.py)
- [Multi-GPU Setup](examples/multi_gpu.py)

---

Made with ❤️ by the MeshML Team
```

## Features

- **PyTorch Integration**: Full PyTorch support with automatic device detection
- **gRPC Communication**: Efficient communication with Parameter Server
- **Automatic Checkpointing**: Save and resume training automatically
- **Mixed Precision Training**: FP16 training for faster computation
- **Error Recovery**: Automatic retry and graceful error handling
- **Custom Models**: Load custom model definitions from GCS
- **Progress Tracking**: Real-time training progress with tqdm

## Architecture

```
meshml_worker/
├── cli.py              # CLI entry point
├── config.py           # Configuration management
├── worker.py           # Main worker implementation
├── training/
│   ├── trainer.py      # Training loop
│   ├── model_loader.py # Custom model loading
│   └── dataloader.py   # Data loading utilities
├── communication/
│   ├── grpc_client.py  # gRPC client
│   └── heartbeat.py    # Heartbeat sender
└── utils/
    ├── device.py       # Device detection
    ├── checkpoint.py   # Checkpoint management
    └── logger.py       # Logging utilities
```

## Development

```bash
# Run tests
poetry run pytest

# Format code
poetry run black .
poetry run isort .

# Type checking
poetry run mypy meshml_worker
```

## License

See LICENSE file.
