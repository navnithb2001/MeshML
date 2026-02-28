# MeshML Technology Stack - Decision Matrix

## Core Languages

| Component | Language | Justification | Alternatives Considered |
|-----------|----------|---------------|------------------------|
| API Gateway | Python 3.11 | Fast development, rich ML ecosystem, FastAPI performance | Go (harder ML integration) |
| Dataset Sharder | Python 3.11 | Native data science libraries (pandas, numpy) | Scala (steeper learning curve) |
| Task Orchestrator | Python 3.11 | Celery/RQ integration, async support | Java (verbose for this use case) |
| Parameter Server | Python 3.11 | PyTorch/TensorFlow native, rapid prototyping | C++ (harder debugging) |
| Metrics Service | Python 3.11 | Scientific computing libraries | Node.js (weaker ML support) |
| High-Perf Worker | C++17 | Maximum performance, hardware access | Rust (smaller ecosystem for ML) |
| Lightweight Worker | JavaScript ES2022 | Browser compatibility, WebAssembly support | Python (no browser support) |
| Dashboard | TypeScript 5.0 | Type safety for complex UI state | JavaScript (less type safety) |

---

## Web Frameworks

### Backend Services
| Service | Framework | Version | Reason |
|---------|-----------|---------|--------|
| API Gateway | FastAPI | 0.109+ | Async support, auto OpenAPI docs, Pydantic validation |
| Metrics (GraphQL) | Strawberry | 0.219+ | Python-native GraphQL, subscriptions support |
| Worker (gRPC) | grpcio | 1.60+ | High-performance RPC, Protobuf serialization |

**Why FastAPI over Flask/Django?**
- Native async/await for concurrent request handling
- Automatic request validation via Pydantic
- Built-in OpenAPI/Swagger documentation
- Superior performance benchmarks (comparable to Go/Node.js)

### Frontend
| Component | Framework | Version | Reason |
|-----------|-----------|---------|--------|
| Dashboard UI | React | 18.2+ | Component reusability, rich ecosystem |
| State Management | Zustand | 4.5+ | Lightweight, no boilerplate vs Redux |
| GraphQL Client | Apollo Client | 3.8+ | Caching, subscriptions, devtools |
| UI Components | shadcn/ui | Latest | Accessible, customizable, Tailwind-based |
| Charts | Recharts | 2.10+ | React-native, declarative API |

**Why React over Vue/Svelte?**
- Largest ecosystem for data visualization libraries
- Better TypeScript support
- More job market familiarity for student contributors

---

## Databases & Caching

### Primary Storage
| Type | Technology | Version | Use Case |
|------|------------|---------|----------|
| Relational DB | PostgreSQL | 15+ | Worker metadata, job state, batch assignments |
| In-Memory Cache | Redis | 7.2+ | Global weights, heartbeat TTL, version map |
| Time-Series DB | TimescaleDB | 2.13+ | Training metrics, loss history (PostgreSQL extension) |
| Object Storage | MinIO | RELEASE.2024-01+ | Dataset batches, model checkpoints (S3-compatible) |

**PostgreSQL Justification:**
- ACID compliance for critical job state
- Rich indexing (B-tree, GIN for JSON)
- Native JSON support for flexible metadata
- Strong Python ecosystem (SQLAlchemy, asyncpg)

**Redis Justification:**
- Sub-millisecond latency for weight retrieval
- Native TTL for heartbeat expiration
- Pub/Sub for real-time coordination
- Atomic operations for version counters

**Why TimescaleDB over InfluxDB?**
- PostgreSQL compatibility (single DB cluster)
- SQL familiarity for students
- Better compression for long-term storage

---

## Communication Protocols

| Layer | Protocol | Library/Tool | Use Case |
|-------|----------|--------------|----------|
| User ↔ API | REST (HTTP/2) | FastAPI | Job management, CRUD operations |
| Leader ↔ Worker (Control) | gRPC | grpcio, protobuf | Heartbeats, task assignment |
| Worker ↔ PS (Data) | gRPC | grpcio + custom serialization | Gradient transfer (large tensors) |
| Dashboard ↔ Metrics | GraphQL | Apollo Server, Strawberry | Real-time metrics subscriptions |
| Inter-Service | gRPC | grpcio | Internal microservice communication |

**gRPC Benefits:**
- 7x faster than REST for binary payloads
- Bi-directional streaming for gradients
- Strong typing via Protobuf
- Built-in load balancing

**GraphQL Benefits:**
- Client controls data shape (avoid overfetching)
- Real-time subscriptions via WebSockets
- Single endpoint for complex queries

---

## Machine Learning Libraries

### Python (Parameter Server)
| Library | Version | Purpose |
|---------|---------|---------|
| PyTorch | 2.1+ | Primary ML framework (most student-friendly) |
| NumPy | 1.26+ | Numerical operations |
| scikit-learn | 1.4+ | Metrics computation (F1, AUC) |
| Transformers | 4.36+ (optional) | Pre-trained model support |

### C++ (High-Performance Worker)
| Library | Version | Purpose |
|---------|---------|---------|
| LibTorch | 2.1+ | PyTorch C++ frontend |
| Eigen | 3.4+ | Linear algebra (CPU fallback) |
| CUDA Toolkit | 12.0+ | NVIDIA GPU acceleration |
| oneDNN | 3.3+ | Intel CPU optimization |

### JavaScript (Lightweight Worker)
| Library | Version | Purpose |
|---------|---------|---------|
| ONNX Runtime Web | 1.16+ | Cross-platform inference/training |
| TensorFlow.js | 4.15+ | Alternative ML runtime |
| WebGL | 2.0 | GPU acceleration in browser |

**Why PyTorch over TensorFlow?**
- More Pythonic API (easier for students)
- Better debugging (eager execution by default)
- Growing industry adoption
- Simpler distributed training APIs

---

## DevOps & Infrastructure

### Containerization
| Tool | Version | Purpose |
|------|---------|---------|
| Docker | 24.0+ | Service containerization |
| Docker Compose | 2.23+ | Local development orchestration |

### Orchestration
| Tool | Version | Purpose |
|------|---------|---------|
| Kubernetes | 1.28+ | Production container orchestration |
| Helm | 3.13+ | Kubernetes package management |
| Minikube | 1.32+ | Local K8s testing |

### CI/CD
| Tool | Purpose |
|------|---------|
| GitHub Actions | Primary CI/CD pipeline |
| Pre-commit | Local git hooks (linting, formatting) |
| Docker BuildKit | Multi-stage builds, caching |

### Monitoring
| Tool | Purpose |
|------|---------|
| Prometheus | Metrics collection and storage |
| Grafana | Metrics visualization dashboards |
| Jaeger | Distributed tracing |
| Loki | Log aggregation |
| cAdvisor | Container resource monitoring |

**Why Prometheus/Grafana?**
- Industry standard (easy to find examples)
- Pull-based model (better for dynamic workers)
- PromQL for flexible queries
- Native Kubernetes integration

---

## Build Tools & Package Management

### Python
| Tool | Purpose |
|------|---------|
| Poetry | Dependency management, packaging |
| pip-tools | Lock file generation |
| Black | Code formatting |
| Ruff | Ultra-fast linting (replaces Flake8, isort) |
| mypy | Static type checking |
| pytest | Unit/integration testing |

### C++
| Tool | Purpose |
|------|---------|
| CMake | Cross-platform build system |
| Conan | Dependency management |
| vcpkg | Alternative package manager (Windows-friendly) |
| clang-format | Code formatting |
| Google Test | Unit testing framework |

### JavaScript/TypeScript
| Tool | Purpose |
|------|---------|
| npm | Package management |
| Vite | Frontend build tool (faster than Webpack) |
| ESLint | Linting |
| Prettier | Code formatting |
| Jest | Unit testing |
| Playwright | E2E testing |

---

## Security & Authentication

| Component | Technology | Purpose |
|-----------|------------|---------|
| Authentication | JWT (HS256) | Stateless token-based auth |
| Secrets Management | HashiCorp Vault | API keys, DB credentials |
| TLS/SSL | Let's Encrypt | Certificate management |
| API Rate Limiting | slowapi | Request throttling |
| Input Validation | Pydantic | Schema validation |

**JWT Justification:**
- Stateless (no server-side sessions)
- Works across microservices
- Standard industry practice

---

## Development Tools

### IDEs/Editors
- **Recommended**: VS Code with extensions
  - Python, C++, ESLint, Prettier
  - Docker, Kubernetes
  - Remote - SSH (for cluster debugging)

### Version Control
- **Git**: Version control
- **Git LFS**: Large file storage (model checkpoints)
- **Conventional Commits**: Commit message standard

### Documentation
| Tool | Purpose |
|------|---------|
| Sphinx | Python API documentation |
| Doxygen | C++ API documentation |
| TypeDoc | TypeScript documentation |
| MkDocs | User-facing documentation |

---

## Performance Considerations

### Optimization Priorities
1. **Network**: Use gRPC for tensor transfer (7x faster than REST)
2. **Memory**: Redis for low-latency weight access
3. **Compute**: C++ workers with SIMD/GPU for heavy lifting
4. **I/O**: Async Python for concurrent request handling

### Scalability Targets
- **Workers**: Support 100+ concurrent devices
- **Throughput**: 10,000 gradient updates/second
- **Latency**: <100ms for weight synchronization
- **Storage**: Handle datasets up to 100GB

---

## Risk Mitigation

### Technology Risks
| Risk | Mitigation |
|------|------------|
| Python GIL bottleneck | Use multiprocessing for CPU-bound tasks |
| gRPC learning curve | Provide comprehensive examples |
| Mobile worker unreliability | Implement aggressive retry logic |
| CUDA compatibility issues | Fallback to CPU-only mode |

### Dependency Management
- **Pin exact versions** in production
- **Use lock files** (poetry.lock, package-lock.json)
- **Regular security audits** (Dependabot, Snyk)

---

## Optional/Future Technologies

| Technology | Purpose | Priority |
|------------|---------|----------|
| Ray | Distributed computing framework | Medium |
| Horovod | Advanced distributed training | Low |
| WebAssembly | Faster JS worker compute | Medium |
| Kubernetes Operators | Custom CRDs for ML jobs | Low |
| Differential Privacy | Gradient privacy | High (Security) |

---

## Decision Rationale Summary

### Why This Stack?
1. **Student-Friendly**: Python/JavaScript are most common in CS curricula
2. **Performance**: C++ for critical path, Python for flexibility
3. **Modern**: Latest stable versions with active communities
4. **Open Source**: No vendor lock-in, free for educational use
5. **Industry-Relevant**: Technologies used in real ML infrastructure (Meta, Google)

### Learning Outcomes for Students
- Microservices architecture
- Distributed systems design
- Performance optimization (CPU, GPU, Network)
- DevOps practices (Docker, K8s, CI/CD)
- Production ML systems (beyond Jupyter notebooks)
