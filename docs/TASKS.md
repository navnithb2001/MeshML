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

## Phase 6: Task Orchestrator Service
- [ ] **TASK-6.1**: Worker health monitoring
  - Heartbeat receiver (gRPC server)
  - TTL-based worker status tracking
  - Worker failure detection and alerts
  
- [ ] **TASK-6.2**: Job queue management
  - Redis-based job queue
  - Priority scheduling
  - Job state machine (pending → running → completed/failed)
  - Job acceptance only after model & dataset validation passes (Phase 4)
  
- [ ] **TASK-6.3**: Worker discovery & registration
  - Worker capability reporting (GPU, RAM, network speed)
  - Worker pool management
  - Group-based worker access control
  
- [ ] **TASK-6.4**: Task assignment logic
  - Match workers to job requirements
  - Load balancing across workers
  - Batch assignment to workers
  
- [ ] **TASK-6.5**: Fault tolerance mechanisms
  - Automatic task reassignment on worker failure
  - Exponential backoff for retries
  - Dead letter queue for permanently failed tasks

---

## Phase 7: Parameter Server Service (Core ML Engine)
- [ ] **TASK-7.1**: Model initialization
  - Load custom model from GCS using create_model() function
  - Support for PyTorch models (primary focus)
  - Random weight initialization or pre-trained model loading
  
- [ ] **TASK-7.2**: Parameter storage
  - In-memory parameter tensors (NumPy/PyTorch)
  - Version control for model checkpoints
  - Redis-backed persistence
  
- [ ] **TASK-7.3**: Gradient aggregation logic
  - Federated Averaging (FedAvg) implementation
  - Asynchronous gradient averaging
  - Staleness-aware weighting (version ID-based)
  - Gradient clipping and normalization
  
- [ ] **TASK-7.4**: Synchronization strategies
  - Synchronous updates (wait for all workers)
  - Asynchronous updates (process gradients immediately)
  - Semi-synchronous (configurable staleness threshold)
  
- [ ] **TASK-7.5**: Parameter distribution
  - Broadcast updated parameters to workers
  - Delta compression (send only changed parameters)
  - HTTP/gRPC endpoints for parameter push/pull
  
- [ ] **TASK-7.6**: Convergence detection
  - Loss monitoring
  - Early stopping logic
  - Target accuracy validation

---

## Phase 8: Python Worker (PyTorch)
- [ ] **TASK-8.1**: Worker setup script
  - CLI tool for worker initialization (`meshml-worker init`)
  - Dependency installation (PyTorch, gRPC)
  - Configuration file generation (.meshml/config.yaml)
  
- [ ] **TASK-8.2**: Custom model loading
  - Download custom model.py from GCS
  - Dynamic import of create_model() and create_dataloader()
  - Model instantiation with error handling
  - Validate MODEL_METADATA
  
- [ ] **TASK-8.3**: gRPC client implementation
  - Connect to Parameter Server
  - Heartbeat sender
  - Gradient push/parameter pull
  
- [ ] **TASK-8.4**: Training loop implementation
  - Download data shard from Dataset Sharder
  - Load dataset using create_dataloader()
  - Local training on assigned data
  - Gradient computation and upload
  
- [ ] **TASK-8.5**: Device optimization
  - Auto-detect CUDA/Metal/CPU
  - Mixed precision training (FP16)
  - Memory-efficient DataLoader
  
- [ ] **TASK-8.6**: Error handling & recovery
  - Checkpoint saving/loading
  - Retry logic for network failures
  - Graceful shutdown on errors

---

## Phase 9: C++ Worker (LibTorch)
- [ ] **TASK-9.1**: Build system setup
  - CMake configuration
  - LibTorch integration
  - Cross-compilation for Linux/macOS/Windows
  
- [ ] **TASK-9.2**: gRPC client implementation
  - Async communication with Parameter Server
  - Heartbeat sender
  - Gradient/parameter transfer
  
- [ ] **TASK-9.3**: C++ training loop
  - Torch tensor operations
  - Autograd for gradient computation
  - Optimized memory management
  
- [ ] **TASK-9.4**: Performance optimizations
  - Multi-threading for data loading
  - SIMD operations (AVX/NEON)
  - CUDA support for NVIDIA GPUs
  - Profiling with perf/gprof

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
