# MeshML Python Worker

Federated learning worker implementation using PyTorch.

## Installation

```bash
# Install with pip
pip install -e .

# Or with poetry
poetry install
```

## Quick Start

### Initialize Worker

```bash
# Initialize worker with default configuration
meshml-worker init

# Initialize with custom config
meshml-worker init --parameter-server-url http://localhost:8000 --worker-id my-worker
```

### Start Training

```bash
# Start training on a model
meshml-worker train --model-id my-model

# With custom configuration
meshml-worker train \
  --model-id my-model \
  --batch-size 32 \
  --epochs 10 \
  --device cuda
```

## Configuration

Worker configuration is stored in `.meshml/config.yaml`:

```yaml
worker:
  id: worker-1
  name: "My Worker"
  
parameter_server:
  url: http://localhost:8000
  timeout: 30
  
training:
  device: auto  # auto, cuda, cpu, mps
  batch_size: 32
  num_workers: 4
  mixed_precision: true
  
storage:
  checkpoints_dir: .meshml/checkpoints
  models_dir: .meshml/models
  data_dir: .meshml/data
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
