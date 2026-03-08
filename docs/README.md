# MeshML Documentation Index

## Quick Links

- **[Main README](../README.md)** - Project overview and getting started
- **[Architecture](architecture/ARCHITECTURE.md)** - System design and components
- **[Tasks](TASKS.md)** - Development roadmap and task breakdown
- **[C++ Worker Status](CPP_WORKER_STATUS.md)** - Current implementation status

## Core Documentation

### Getting Started
- [Contributing Guide](CONTRIBUTING.md) - How to contribute to the project
- [Local Setup](development/local-setup.md) - Development environment setup
- [Code Standards](development/code-standards.md) - Coding conventions

### Implementation Status
- [Progress Tracker](PROGRESS.md) - Overall project progress
- [Implementation Status](IMPLEMENTATION_STATUS.md) - Feature completion status
- [C++ Worker Status](CPP_WORKER_STATUS.md) - Detailed C++ worker progress

### Component-Specific Guides

#### Workers
- [C++ Worker](../workers/cpp-worker/README.md)
  - [Config & Models](../workers/cpp-worker/docs/CONFIG_AND_MODELS.md)
  - [CUDA Kernels](../workers/cpp-worker/docs/CUDA_KERNELS_GUIDE.md)
  - [Performance Guide](../workers/cpp-worker/docs/PERFORMANCE_GUIDE.md)
  - [Testing Guide](../workers/cpp-worker/docs/TESTING_GUIDE.md)
  - [Training Guide](../workers/cpp-worker/docs/TRAINING_GUIDE.md)
  - [gRPC Examples](../workers/cpp-worker/docs/GRPC_EXAMPLES.md)
  
- [Python Worker](../workers/python-worker/README.md)
  - [Optimization](../workers/python-worker/docs/OPTIMIZATION.md)

#### Services
- [API Gateway](../services/api_gateway/README.md)
- [Database](../services/database/README.md)
  - [Seeding Guide](../services/database/SEEDING.md)
  - [Repositories](../services/database/repositories/README.md)
- [Cache](../services/cache/README.md)

#### APIs
- [GraphQL API](../graphql/README.md)
  - [Examples](../graphql/examples.md)
- [REST API](../api/README.md)
- [Protocol Buffers](../proto/README.md)

### User Guides
- [Custom Model Upload](user-guide/custom-model-upload.md)

### Infrastructure
- [Docker Setup](../infrastructure/docker/README.md)

## Documentation Structure

```
docs/
├── README.md (this file)           # Documentation index
├── ARCHITECTURE.md                 # System architecture
├── TASKS.md                        # Task breakdown
├── PROGRESS.md                     # Progress tracking
├── IMPLEMENTATION_STATUS.md        # Feature status
├── CPP_WORKER_STATUS.md           # C++ worker details
├── CONTRIBUTING.md                 # Contribution guide
│
├── architecture/                   # Architecture docs
│   └── ARCHITECTURE.md
│
├── development/                    # Developer guides
│   ├── local-setup.md
│   └── code-standards.md
│
└── user-guide/                     # End-user guides
    └── custom-model-upload.md
```

## Issue Templates
- [Bug Report](../.github/ISSUE_TEMPLATE/bug_report.md)
- [Feature Request](../.github/ISSUE_TEMPLATE/feature_request.md)
- [Task](../.github/ISSUE_TEMPLATE/task.md)
