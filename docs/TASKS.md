# Student-Mesh Distributed ML Trainer - Task Breakdown

## Phase 0: Project Setup & Infrastructure
- [x] **TASK-0.1**: Initialize project repository structure
  - Create directory hierarchy for microservices
  - Set up monorepo vs multi-repo decision
  - Initialize Git with .gitignore for Python, C++, Node.js
  
- [x] **TASK-0.2**: Development environment setup
  - Docker Compose for local development
  - PostgreSQL container configuration
  - Redis container configuration
  - Development dependency management (requirements.txt, package.json, CMakeLists.txt)
  
- [x] **TASK-0.3**: CI/CD pipeline foundation
  - GitHub Actions / GitLab CI setup
  - Linting and formatting configs (Black, ESLint, clang-format)
  - Unit test infrastructure

---

## Phase 1: Database & Storage Layer
- [ ] **TASK-1.1**: PostgreSQL schema implementation
  - Create `users`, `groups`, `group_members`, `group_invitations` tables (group collaboration system)
  - Create `models` table (custom model registry with lifecycle states: uploading → validating → ready → failed → deprecated)
  - Create `workers` table with indexes
  - Create `jobs` table with status tracking and group_id foreign key
  - Create `data_batches` table with retry mechanism
  - Write migration scripts (Alembic/Flyway)
  
- [ ] **TASK-1.2**: Redis cache structure
  - Design key naming conventions
  - Implement global weights binary serialization format
  - Set up heartbeat TTL logic
  - Create version map data structure
  
- [ ] **TASK-1.3**: Database access layer (DAL)
  - ORM models (SQLAlchemy)
  - Redis client wrapper with connection pooling
  - CRUD operations with error handling
  - Transaction management utilities

---

## Phase 2: Core Communication Protocols
- [ ] **TASK-2.1**: gRPC service definitions
  - Define .proto files for Worker-Leader heartbeat
  - Define .proto files for gradient transfer
  - Define .proto files for task assignment
  - Generate stubs for Python and C++
  
- [ ] **TASK-2.2**: REST API contracts
  - OpenAPI/Swagger specification
  - Request/Response schemas (Pydantic models)
  - Authentication/Authorization contracts
  
- [ ] **TASK-2.3**: GraphQL schema for metrics
  - Define types for real-time metrics
  - Query resolvers for dashboard
  - Subscription setup for live updates

---

## Phase 3: API Gateway Service
- [ ] **TASK-3.1**: FastAPI application scaffold
  - Project structure (routers, dependencies, middleware)
  - Health check endpoint
  - CORS and security headers
  
- [ ] **TASK-3.2**: Group management endpoints
  - POST /groups - Create new group
  - POST /groups/{group_id}/invitations - Send invitation (email or link)
  - POST /invitations/{token}/accept - Accept invitation
  - GET /groups/{group_id}/members - List group members
  - PUT /groups/{group_id}/members/{user_id}/role - Update member role
  - DELETE /groups/{group_id}/members/{user_id} - Remove member
  - RBAC implementation (owner/admin/member roles)
  
- [ ] **TASK-3.3**: Job management endpoints
  - POST /jobs - Submit new training job (with group_id and model_id)
  - GET /jobs/{job_id} - Query job status
  - DELETE /jobs/{job_id} - Cancel job
  - Group-based access control (only group members can view/manage jobs)
  
- [ ] **TASK-3.4**: Worker registration endpoints
  - POST /workers/register - Device registration
  - GET /workers - List active workers
  - PUT /workers/{worker_id}/heartbeat - Manual heartbeat
  
- [ ] **TASK-3.5**: Authentication & authorization
  - JWT token generation and validation
  - User registration & login endpoints
  - Role-based permission decorators
  
- [ ] **TASK-3.6**: Monitoring endpoints
  - GET /metrics/realtime - Current system stats
  - GET /jobs/{job_id}/progress - Training progress
  - WebSocket endpoint for live updates

---

## Phase 4: Model & Dataset Validation Service
- [x] **TASK-4.1**: Custom model upload endpoint
  - POST /models/upload (upload Python file with create_model(), create_dataloader(), MODEL_METADATA)
  - Store in GCS bucket (gs://meshml-models/{model_id}/model.py)
  - Update models table with 'uploading' state
  
- [x] **TASK-4.2**: Model validation functions
  - Python syntax validation (ast.parse)
  - Structure validation (check for required functions)
  - Model instantiation test (import and call create_model())
  - Metadata validation (MODEL_METADATA dict completeness)
  - Update model state: 'uploading' → 'validating' → 'ready' or 'failed'
  
- [x] **TASK-4.3**: Dataset validation functions
  - Format validation (ImageFolder/COCO/CSV structure)
  - Content validation (file types, image dimensions)
  - Size limit checks (prevent excessive datasets)
  - Dataset metadata extraction
  
- [x] **TASK-4.4**: Validation error reporting
  - Error categorization system (severity levels, error categories)
  - Structured ValidationReport with actionable suggestions
  - ValidationLog database model for audit trail
  - API endpoints for validation history and statistics
  - Integration with model and dataset validators

---

## Phase 5: Dataset Sharder Service
- [x] **TASK-5.1**: Dataset loading utilities
  - Multi-format support (ImageFolder, COCO, CSV)
  - Memory-efficient streaming to avoid OOM
  - GCS and local filesystem support
  - Integration with Phase 4 validation
  
- [x] **TASK-5.2**: Sharding algorithms
  - Random split (IID distribution)
  - Stratified sampling for imbalanced datasets
  - Non-IID partitioning with Dirichlet distribution
  - Sequential sharding for debugging
  - Configurable batch size calculation
  
- [x] **TASK-5.3**: Storage management
  - Local filesystem batch storage with BatchMetadata
  - GCS cloud storage integration
  - Batch metadata generation (size, SHA256 checksum, class distribution)
  - BatchManager for high-level batch operations
  - Automatic cleanup of old batches
  
- [x] **TASK-5.4**: Data distribution service
  - HTTP endpoints for worker batch discovery and download (12 RESTful endpoints)
  - Multiple distribution strategies (shard-per-worker, round-robin, load-balanced)
  - Download status tracking with lifecycle (pending → downloading → completed/failed)
  - Automatic failure recovery with reassignment and retry logic
  - Worker progress tracking and distribution statistics
  - Streaming batch downloads with chunked transfer

---

## Phase 6: Task Orchestrator Service ✅ **COMPLETE**
- [x] **TASK-6.1**: Worker health monitoring
  - Worker registration with capability tracking (GPU, CPU, RAM, network)
  - HTTP heartbeat receiver with metrics updates
  - TTL-based worker status tracking with 6-state lifecycle (ONLINE, IDLE, BUSY, DEGRADED, OFFLINE, UNKNOWN)
  - Automatic worker failure detection and degraded state detection
  - Background health monitoring task with configurable intervals
  - Compute score-based worker ranking for optimal task assignment
  - Thread-safe registry operations with concurrent heartbeat support
  - 14 RESTful HTTP endpoints for worker management
  - Group-based worker organization and filtering
  - Comprehensive test suite with 40+ tests (see docs/completed/TASK-6.1-worker-health-monitoring.md)
  
- [x] **TASK-6.2**: Job queue management
  - Redis-based job queue with priority scheduling (4 levels: LOW, MEDIUM, HIGH, CRITICAL)
  - 8-state job lifecycle: pending → validating → waiting → running → completed/failed/cancelled/timeout
  - Strict state machine validation with retry support (max_retries=3)
  - Phase 4 validation integration (validation-gated job acceptance)
  - Resource requirements matching (GPU, CPU, RAM, CUDA/MPS)
  - Automatic retry logic with exponential backoff support
  - Dead letter queue for permanently failed jobs
  - Timeout detection (validation timeout: 5 min, execution timeout: configurable)
  - Job progress tracking (epoch, loss, accuracy)
  - 17 RESTful HTTP endpoints for complete job management
  - Worker assignment and release with shard_id tracking
  - Comprehensive test suite with 60+ tests (see docs/completed/TASK-6.2-job-queue-management.md)
  
- [x] **TASK-6.3**: Worker discovery & registration ✅
  - Worker capability reporting with compute score calculation (GPU, RAM, CPU, storage, network)
  - Worker pool management with capacity constraints (min/max workers)
  - Group-based worker access control (RBAC)
  - Capability-based worker-job matching algorithm
  - Pool health monitoring (4-tier: HEALTHY/DEGRADED/CRITICAL/OFFLINE)
  - Auto-scaling detection (scale-up/scale-down needs)
  - Transactional job assignment (coordinates JobQueue + WorkerRegistry)
  - 14 RESTful HTTP endpoints for orchestration
  - Comprehensive test suite with 50+ tests (see docs/completed/TASK-6.3-worker-discovery-registration.md)
  
- [x] **TASK-6.4**: Task assignment logic ✅
  - 7 assignment strategies (GREEDY, BALANCED, BEST_FIT, COMPUTE_OPTIMIZED, AFFINITY, ANTI_AFFINITY)
  - 5 load balancing policies (ROUND_ROBIN, LEAST_LOADED, WEIGHTED_ROUND_ROBIN, PRIORITY_BASED)
  - Batch assignment with optimization
  - Real-time load monitoring (worker & cluster level)
  - Automatic load rebalancing with configurable threshold
  - Flexible constraint system (group, GPU, affinity, capacity limits)
  - 11 RESTful HTTP endpoints for orchestration
  - Comprehensive test suite with 50+ tests (see docs/completed/TASK-6.4-task-assignment-logic.md)
  
- [x] **TASK-6.5**: Fault tolerance mechanisms ✅ **COMPLETE**
  - 6 recovery strategies (IMMEDIATE_REASSIGN, EXPONENTIAL_BACKOFF, CIRCUIT_BREAKER, CHECKPOINT_RECOVERY, DEGRADED_MODE, DEAD_LETTER)
  - Circuit breaker pattern with 3-state machine (CLOSED → OPEN → HALF_OPEN → CLOSED)
  - Exponential backoff with jitter (delay = min(initial × multiplier^attempt, max) ± jitter)
  - Checkpoint-based recovery with GCS storage
  - Dead letter queue for permanent failures
  - 9 failure types (worker offline/timeout/degraded, job timeout/error, validation failed, resource exhausted, network error, checkpoint corruption)
  - Background monitoring (60s interval) and retry scheduler (10s checks)
  - 17 RESTful HTTP endpoints for fault tolerance management
  - Comprehensive test suite with 50+ tests (see docs/completed/TASK-6.5-fault-tolerance-mechanisms.md)

**🎉 Phase 6 Complete! All distributed training coordination tasks implemented.**

---

## Phase 7: Parameter Server Service (Core ML Engine)
- [x] **TASK-7.1**: Model initialization ✅ **COMPLETE**
  - GCS model loading with dynamic import of custom model.py files
  - PyTorch models with nn.Module validation (primary focus)
  - 6 initialization strategies (RANDOM, PRETRAINED, ZEROS, ONES, XAVIER, KAIMING)
  - MODEL_METADATA validation (name, version, framework required)
  - create_model() function validation and instantiation
  - Multi-device support (CPU, CUDA, MPS)
  - Model registry with SHA256 checksum tracking
  - Weight reinitialization support
  - 7 RESTful HTTP endpoints for model management
  - Comprehensive test suite with 60+ tests (see docs/completed/TASK-7.1-model-initialization.md)
  
- [x] **TASK-7.2**: Parameter storage ✅ **COMPLETE**
  - In-memory parameter storage (PyTorch tensors with deep copy)
  - Automatic version control (incremental version IDs)
  - Version history tracking with metadata
  - 4 checkpoint types (MANUAL, AUTO, BEST, FINAL)
  - Checkpoint retention policy (protects BEST/FINAL, keeps N recent)
  - Redis-backed persistence for durability
  - Delta compression (track changed parameters between versions)
  - Parameter-level updates with versioning
  - NumPy format conversion support
  - 11 RESTful HTTP endpoints for parameter management
  - Comprehensive test suite with 70+ tests
  
- [x] **TASK-7.3**: Gradient aggregation logic ✅ **COMPLETE**
  - 5 aggregation strategies (FedAvg, simple average, weighted, momentum, adaptive)
  - Federated Averaging (FedAvg) with sample-weighted aggregation
  - Asynchronous gradient buffering and immediate processing
  - Staleness-aware weighting (exponential decay based on version difference)
  - Gradient clipping (value and L2 norm based)
  - Gradient normalization by L2 norm
  - Configurable max staleness threshold (filter old gradients)
  - Momentum-based aggregation for stable convergence
  - Adaptive aggregation weighted by loss quality
  - Aggregation history tracking with model filtering
  - 9 RESTful HTTP endpoints for gradient management
  - Comprehensive test suite with 80+ tests covering all strategies
  
- [x] **TASK-7.4**: Synchronization strategies ✅ **COMPLETE**
  - 3 synchronization modes (sync, async, semi-sync)
  - Synchronous mode: Wait for all workers before aggregating
  - Asynchronous mode: Immediate or batch-based aggregation
  - Semi-synchronous mode: Quorum-based with staleness filtering
  - Worker registration and state tracking (active, idle, timed out, excluded)
  - Round-based coordination for sync mode
  - Configurable worker quorum (fraction of workers required)
  - Timeout detection for workers and rounds
  - Auto-exclusion of timed out workers
  - Aggregation callbacks for event notification
  - Round history tracking with filtering
  - 10 RESTful HTTP endpoints for sync management
  - Comprehensive test suite with 70+ tests covering all modes
  
- [x] **TASK-7.5**: Parameter distribution ✅ **COMPLETE**
  - 3 distribution modes (pull, push, hybrid)
  - Pull mode: Workers request parameters from server
  - Push mode: Server broadcasts to workers (subscription-based)
  - Delta compression: Send only changed parameters
  - Automatic delta detection (configurable threshold)
  - Multiple parameter formats (PyTorch, NumPy, pickle)
  - Compression support (gzip, zstd)
  - Version-based synchronization
  - Selective parameter distribution (request specific params)
  - Checksum validation (SHA256)
  - Worker subscription management
  - Distribution history tracking
  - Broadcast to multiple workers
  - 9 RESTful HTTP endpoints for distribution
  - Comprehensive test suite with 80+ tests
  
- [x] **TASK-7.6**: Convergence detection
  - Loss monitoring with sliding window analysis
  - 7 convergence criteria (loss threshold, metric threshold, plateau, patience, max iterations, gradient norm)
  - 5 training phases (NOT_STARTED, WARMUP, TRAINING, PLATEAUED, CONVERGED, STOPPED)
  - Early stopping logic with configurable patience
  - Multi-metric tracking with direction (MINIMIZE/MAXIMIZE)
  - Plateau detection using variance analysis
  - Best metrics preservation with min_delta
  - Per-model state management
  - Target accuracy validation
  - 7 HTTP endpoints for monitoring and control
  - Comprehensive tests (60+ tests)

---

## Phase 8: Python Worker (PyTorch)
- [x] **TASK-8.1**: Worker setup script
  - CLI tool with 4 commands (init, train, status, config)
  - Complete configuration management with Pydantic validation
  - Automatic worker ID generation
  - Device detection (CUDA/MPS/CPU)
  - Checkpoint management system
  - Training logger with colored output
  - Storage directory management
  - Poetry-based dependency management
  - 40+ tests covering setup, config, device, checkpoints, logging
  
- [x] **TASK-8.2**: Custom model loading
  - Dynamic model loading from multiple sources (HTTP/HTTPS, GCS, local files)
  - MODEL_METADATA validation (required fields: name, version, framework, input/output shapes)
  - Extract create_model() and create_dataloader() functions
  - Module caching and cache management
  - Data shard downloading (HTTP/HTTPS, GCS)
  - Progress tracking for downloads
  - Example model with SimpleCNN for MNIST
  - 50+ tests covering metadata, loading, downloads, error handling
  
- [x] **TASK-8.3**: gRPC client implementation
  - Complete gRPC client for Parameter Server communication
  - Connect/disconnect with connection management
  - Get weights with compression support (gzip)
  - Push gradients with metadata (loss, gradient_norm, layer_norms)
  - Model version tracking and synchronization
  - Compression/decompression utilities
  - Heartbeat sender with periodic status updates
  - Worker status reporting (state, epoch, batch, metrics)
  - Thread-safe heartbeat with retry logic
  - Context manager support for both client and heartbeat
  - 50+ tests covering connection, weights, gradients, compression, heartbeat
  
- [x] **TASK-8.4**: Training loop implementation
  - Complete PyTorch training loop with epoch and batch handling
  - Data shard downloading and loading
  - Dynamic model loading using create_model() and create_dataloader()
  - Local training on assigned data with progress tracking (tqdm)
  - Gradient computation and automatic upload to Parameter Server
  - Mixed precision training support (FP16 with GradScaler)
  - Gradient clipping with configurable max norm
  - Gradient accumulation with configurable steps
  - Checkpoint management (save/load/resume)
  - Training logger with epoch and batch metrics
  - Heartbeat integration with status updates
  - Fetch initial weights from Parameter Server
  - Push gradients with metadata (loss, gradient_norm)
  - 50+ tests covering initialization, training, checkpoints, heartbeat
  
- [x] **TASK-8.5**: Device optimization ✅
  - MemoryProfiler for tracking memory usage during training
  - PerformanceBenchmark for measuring throughput and latency
  - OptimizedDataLoader with automatic pin_memory, num_workers tuning
  - optimize_dataloader_settings() function for device-specific optimization
  - benchmark_device_performance() for device benchmarking
  - Memory profiling integrated into Trainer (profiles every 10th batch)
  - Performance benchmarking integrated into Trainer (per-epoch summaries)
  - Support for CUDA, MPS, and CPU devices
  - 42 tests (21 passing without PyTorch, all pass with PyTorch installed)
  - ~1,135 lines total implementation + tests
  
- [ ] **TASK-8.6**: Error handling & recovery
  - Checkpoint saving/loading
  - Retry logic for network failures
  - Graceful shutdown on errors

---

## Phase 9: C++ Worker (LibTorch) ✅ **COMPLETE**
- [x] **TASK-9.1**: Build system setup ✅
  - ✅ CMake configuration
  - ✅ LibTorch integration with auto-download
  - ✅ Cross-compilation for Linux/macOS/Windows
  - ✅ Config loader implementation (YAML/JSON)
  
- [x] **TASK-9.2**: gRPC client implementation ✅
  - ✅ Async communication with Parameter Server
  - ✅ Heartbeat sender
  - ✅ Gradient/parameter transfer
  - ✅ Protobuf schema definitions
  
- [x] **TASK-9.3**: C++ training loop ✅
  - ✅ Torch tensor operations
  - ✅ Autograd for gradient computation
  - ✅ Optimized memory management
  - ✅ Data loading and batching
  - ✅ Checkpoint management
  - ✅ Model loader with factory pattern
  
- [x] **TASK-9.4**: Performance optimizations ✅
  - ✅ Multi-threading for data loading
  - ✅ SIMD operations (AVX/NEON)
  - ✅ Memory pooling
  - ✅ Performance profiling
  - ✅ Compiler optimizations
  - ✅ Custom CUDA kernels (10 optimized kernels, 1.5-3x speedup)
  - ⏳ External profiler integration (external tools, not required)
  
- [x] **TASK-9.5**: Testing & Quality Assurance ✅
  - ✅ Unit tests (83 tests, 4 test suites)
  - ✅ Config loader tests (17 tests, 90%+ coverage)
  - ✅ Model loader tests (19 tests, 85%+ coverage)
  - ✅ CUDA kernel tests (24 tests, 80%+ coverage)
  - ✅ Performance tests (23 tests, 85%+ coverage)
  - ✅ CI/CD pipeline (GitHub Actions)
  - ✅ Code coverage reporting
  - ✅ Test documentation

**🎉 Phase 9 Complete! All implementation and testing done.**

---

## Phase 10: Metrics & Logging Service
- [ ] **TASK-10.1**: Prometheus metrics exporter
  - Worker count, active jobs
  - Gradient update frequency
  - Training loss/accuracy per epoch/iteration
  
- [ ] **TASK-10.2**: Grafana dashboard templates
  - System overview dashboard
  - Worker performance metrics
  - Training progress visualization
  
- [ ] **TASK-10.3**: Distributed tracing
  - Jaeger integration (already in Phase 0)
  - Trace gradient flow from worker → parameter server
  - Latency analysis
  
- [ ] **TASK-10.4**: Centralized logging
  - ELK stack / Loki setup
  - Log aggregation from all services
  - Log level filtering
  
- [ ] **TASK-10.5**: Basic alerting
  - Threshold-based alerts (e.g., loss divergence)
  - Worker unavailability notifications
  - Email/Slack integration (simple)

---

## Phase 11: Model Registry Service
- [ ] **TASK-11.1**: Model storage infrastructure
  - GCS bucket setup (gs://meshml-models/)
  - Directory structure: {model_id}/model.py
  - Metadata storage in PostgreSQL models table (from Phase 1)
  
- [ ] **TASK-11.2**: Model lifecycle management
  - State transitions: uploading → validating → ready → failed → deprecated
  - Model versioning with parent_model_id
  - Model retrieval endpoints (GET /models/:id, GET /models/:id/download)
  
- [ ] **TASK-11.3**: Model search & discovery
  - List models by group (GET /groups/:id/models)
  - Model metadata filtering (architecture type, dataset type)
  - Model usage tracking (which jobs use which models)

---

## Phase 12: Dashboard & Monitoring UI
- [ ] **TASK-12.1**: Frontend framework setup
  - React/Vue/Svelte project initialization
  - Tailwind CSS / Material-UI
  - GraphQL client (Apollo/Relay)
  
- [ ] **TASK-12.2**: Group management UI
  - Group creation form
  - Member invitation interface
  - Member list with role management
  
- [ ] **TASK-12.3**: Model upload UI
  - Python file upload form
  - Validation status display
  - Model metadata input (MODEL_METADATA)
  
- [ ] **TASK-12.4**: Job management UI
  - Job submission form (select group, model, dataset)
  - Job list with status indicators
  - Job detail view with logs
  
- [ ] **TASK-12.5**: Real-time monitoring dashboard
  - Live training metrics graphs (Chart.js/D3.js)
  - Worker status visualization
  - System health indicators

---

## Phase 13: Testing & Quality Assurance
- [ ] **TASK-13.1**: Unit tests (70% effort)
  - API Gateway endpoint tests (pytest) - Target: 70% coverage
  - Parameter Server logic tests - Target: 75% coverage
  - Model validation functions tests (100% coverage for critical path)
  - Database model tests (SQLAlchemy)
  
- [ ] **TASK-13.2**: Integration tests (25% effort)
  - End-to-end job submission flow (model upload → validation → job creation → training)
  - Multi-worker training simulation (2-3 workers)
  - Group collaboration flow (create group → invite → accept → submit job)
  - Database transaction tests
  
- [ ] **TASK-13.3**: Manual E2E testing (5% effort)
  - Full system demo with real devices (laptop + phone/browser)
  - User acceptance testing (group creation, model upload, job monitoring)
  - Performance validation (not automated stress tests)

---

## Phase 14: Documentation & Deployment
- [ ] **TASK-14.1**: User documentation
  - Getting started guide
  - Custom model upload tutorial (create_model(), create_dataloader(), MODEL_METADATA)
  - Group collaboration guide
  - Worker setup tutorials
  
- [ ] **TASK-14.2**: Developer documentation
  - Architecture decision records (ADRs)
  - Code contribution guidelines (CONTRIBUTING.md)
  - Local development setup guide
  
- [ ] **TASK-14.3**: Local deployment (Docker Compose)
  - docker-compose.yml with all services
  - Environment variable templates (.env.example)
  - Quick start scripts (make dev, make stop)
  
- [ ] **TASK-14.4**: Production deployment (GKE)
  - Kubernetes manifests (Deployments, Services, ConfigMaps)
  - K8s secrets setup for production credentials
  - Rolling update configuration (simple strategy, no blue-green)
  - Rollback procedures (kubectl rollout undo)
  
- [ ] **TASK-14.5**: Observability stack (already in Phase 0)
  - Verify Prometheus/Grafana/Jaeger integration
  - Production-ready dashboards
  - Log aggregation setup

---

## Phase 15: Security & Compliance
- [ ] **TASK-15.1**: Secrets management (student-friendly)
  - .env files for local development (NOT committed to git)
  - .env.example template with placeholder values
  - K8s secrets for production (GCP credentials, DB passwords, JWT secret)
  - Secret generation scripts (generate_secrets.sh)
  
- [ ] **TASK-15.2**: Security hardening
  - TLS/SSL for all communications (GKE ingress with Let's Encrypt)
  - Input validation and sanitization (Pydantic models)
  - GCS signed URLs for model downloads (time-limited access)
  
- [ ] **TASK-15.3**: Access control
  - API rate limiting (Redis-based)
  - Worker authentication tokens (JWT)
  - Group-based RBAC enforcement
  - Audit logging (basic - who did what when)

---

## Estimated Timeline (Student Project)
- **Phase 0-2**: 2 weeks (Infrastructure & Foundations)
- **Phase 3-4**: 3 weeks (API Gateway + Validation Services)
- **Phase 5-6**: 3 weeks (Dataset Sharder + Orchestrator)
- **Phase 7**: 4 weeks (Parameter Server - most complex)
- **Phase 8-9**: 5 weeks (Python & C++ Workers)
- **Phase 10-11**: 2 weeks (Metrics + Model Registry)
- **Phase 12**: 3 weeks (Dashboard UI)
- **Phase 13**: 3 weeks (Testing - 70% unit, 25% integration, 5% manual)
- **Phase 14-15**: 2 weeks (Deployment + Security)

**Total**: ~27 weeks (~6-7 months) for full system with 1-2 student developers

**Minimum Viable Product (MVP)**: Phases 0-8 + basic Phase 13 = ~20 weeks (5 months)

---

## Dependencies & Prerequisites
- **Development**: Python 3.10+, Node.js 18+, C++17 compiler (optional)
- **Local Testing**: Docker & Docker Compose
- **Databases**: PostgreSQL 15+, Redis 7+
- **Build Tools**: gRPC, Protobuf compilers
- **Cloud**: Google Cloud Platform account (GKE, Cloud SQL, Memorystore, GCS)
- **Optional**: CUDA Toolkit for GPU workers

---

## Key Challenges (Student Project Context)
1. **Asynchronous gradient aggregation** - May require research into FedAvg algorithm
2. **Custom model validation** - Python AST parsing and dynamic imports need careful handling
3. **Group-based access control** - RBAC implementation across all services
4. **Distributed debugging** - Logs and traces are essential for troubleshooting
5. **GCP cost management** - Use free tier wisely, shut down resources when not testing

---

## Success Criteria
- [ ] Successfully train a simple model (ResNet-18 on CIFAR-10) with 2+ workers
- [ ] Group collaboration works (create, invite, accept, submit job)
- [ ] Custom model upload validates and runs successfully
- [ ] Dashboard displays real-time training metrics
- [ ] System handles worker disconnection gracefully
- [ ] Basic security implemented (JWT auth, TLS, RBAC)
