# 🌐 MeshML - Student-Mesh Distributed ML Trainer

> Transform a network of student devices into a powerful distributed GPU for machine learning training

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Python 3.11+](https://img.shields.io/badge/python-3.11+-blue.svg)](https://www.python.org/downloads/)
[![C++17](https://img.shields.io/badge/c++-17-blue.svg)](https://isocpp.org/)
[![TypeScript](https://img.shields.io/badge/typescript-5.0+-blue.svg)](https://www.typescriptlang.org/)

## 📖 Overview

**MeshML** is a high-performance distributed systems infrastructure that parallelizes Machine Learning training across heterogeneous consumer devices (laptops and mobile phones). By treating individual devices as "cores," it mimics GPU architecture at the software level.

### Key Features

- 🚀 **Distributed Training**: Partition datasets and distribute workloads across WiFi mesh networks
- ⚡ **Asynchronous Gradient Aggregation**: Handle slow devices ("stragglers") gracefully
- 🛡️ **Fault Tolerant**: Continue training even when devices disconnect
- 📱 **Cross-Platform Workers**: Native C++ for laptops, JavaScript/WASM for mobile browsers
- 📊 **Real-Time Monitoring**: Live dashboard with training metrics and worker health
- 🔒 **Secure**: RBAC, JWT authentication, TLS encryption

## 🏗️ Architecture

```
┌─────────────┐
│  Dashboard  │ ← GraphQL Subscriptions
└──────┬──────┘
       │
┌──────▼──────────────────────────────────────────┐
│              API Gateway (FastAPI)              │
│         Job Management · RBAC · Monitoring       │
└──────┬──────────────────────────────────────────┘
       │
   ┌───┴───┬─────────────┬──────────────┐
   │       │             │              │
┌──▼───┐ ┌─▼────┐ ┌─────▼─────┐ ┌──────▼──────┐
│Dataset│ │ Task │ │Parameter  │ │   Metrics   │
│Sharder│ │Orch. │ │  Server   │ │   Service   │
└───────┘ └──────┘ └─────┬─────┘ └─────────────┘
                         │
              ┌──────────┴──────────┐
              │                     │
         ┌────▼─────┐        ┌─────▼────┐
         │C++ Worker│        │JS Worker │
         │ (Laptop) │        │ (Mobile) │
         └──────────┘        └──────────┘
```

### Component Overview

- **API Gateway**: REST API for job submission and worker registration
- **Dataset Sharder**: Intelligent data partitioning with stratified sampling
- **Task Orchestrator**: Heartbeat monitoring, task scheduling, straggler mitigation
- **Parameter Server**: Staleness-aware gradient aggregation and model synchronization
- **Metrics Service**: Real-time accuracy, F1-score, and AUC computation
- **Workers**: High-performance (C++/LibTorch) and lightweight (JS/ONNX Runtime)

## 🚀 Quick Start

### Prerequisites

- **Python**: 3.11+
- **Node.js**: 18+
- **C++ Compiler**: GCC 11+, Clang 14+, or MSVC 2022
- **Docker**: 24.0+ (for local development)
- **PostgreSQL**: 15+
- **Redis**: 7.2+

### Local Development Setup

```bash
# Clone the repository
git clone https://github.com/yourusername/meshml.git
cd meshml

# Start infrastructure services
cd infrastructure/docker
docker-compose up -d postgres redis

# Initialize database
cd ../../scripts/setup
./init_db.sh

# Install Python dependencies for a service (e.g., API Gateway)
cd ../../services/api-gateway
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
pip install -r requirements.txt

# Run the API Gateway
python -m app.main
```

### Run a Training Job

```bash
# Submit a job via API
curl -X POST http://localhost:8000/api/v1/jobs \
  -H "Content-Type: application/json" \
  -d '{
    "model_type": "resnet18",
    "dataset": "cifar10",
    "target_accuracy": 0.85
  }'
```

## 📚 Documentation

- [Getting Started Guide](docs/guides/getting-started.md)
- [Architecture Overview](docs/architecture/)
- [API Reference](docs/api/openapi.yaml)
- [Worker Setup - Laptop](docs/guides/worker-setup-laptop.md)
- [Worker Setup - Mobile](docs/guides/worker-setup-mobile.md)
- [Development Guide](docs/development/local-setup.md)
- [Contributing](CONTRIBUTING.md)

## 🛠️ Technology Stack

| Layer | Technology |
|-------|------------|
| **Backend** | Python (FastAPI, gRPC), C++17, JavaScript |
| **ML Framework** | PyTorch 2.1+, LibTorch, ONNX Runtime |
| **Databases** | PostgreSQL 15, Redis 7.2, TimescaleDB |
| **Communication** | gRPC, REST, GraphQL, WebSockets |
| **Frontend** | React 18, TypeScript, Tailwind CSS |
| **Infrastructure** | Docker, Kubernetes, Helm |
| **Monitoring** | Prometheus, Grafana, Jaeger |

See [tech-stack.md](tech-stack.md) for detailed decisions.

## 🧪 Testing

```bash
# Run unit tests for Python services
cd services/api-gateway
pytest tests/ -v

# Run C++ tests
cd workers/cpp-worker/build
ctest --verbose

# Run JavaScript tests
cd workers/js-worker
npm test
```

## 📊 Project Status

**Current Phase**: Phase 0 - Infrastructure Setup

- [x] Project structure initialized
- [ ] Docker Compose setup
- [ ] CI/CD pipeline
- [ ] Database migrations
- [ ] gRPC protocol definitions

See [TASKS.md](TASKS.md) for full roadmap.

## 🤝 Contributing

We welcome contributions! Please see [CONTRIBUTING.md](CONTRIBUTING.md) for guidelines.

### Development Workflow

1. Pick a task from [TASKS.md](TASKS.md)
2. Create a feature branch: `git checkout -b feature/TASK-X.Y`
3. Make changes following our [code standards](docs/development/code-standards.md)
4. Write tests (min. 80% coverage)
5. Submit a PR with clear description

## 📝 License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

## 🙏 Acknowledgments

- Inspired by distributed training systems at Meta (PyTorch) and Google (TensorFlow)
- Built for educational purposes to teach distributed systems concepts
- Special thanks to student contributors

## 📬 Contact

- **Issues**: [GitHub Issues](https://github.com/yourusername/meshml/issues)
- **Discussions**: [GitHub Discussions](https://github.com/yourusername/meshml/discussions)
- **Email**: meshml-dev@example.com

---

**Built with ❤️ for the student ML community**
