# MeshML Project Directory Structure

```
MeshML/
├── .github/
│   ├── workflows/
│   │   ├── ci-python.yml
│   │   ├── ci-cpp.yml
│   │   ├── ci-javascript.yml
│   │   └── deploy.yml
│   └── ISSUE_TEMPLATE/
│       ├── bug_report.md
│       └── feature_request.md
│
├── docs/
│   ├── architecture/
│   │   ├── ADR-001-parameter-server-design.md
│   │   ├── ADR-002-gradient-staleness.md
│   │   └── system-diagram.png
│   ├── api/
│   │   ├── openapi.yaml
│   │   └── graphql-schema.graphql
│   ├── guides/
│   │   ├── getting-started.md
│   │   ├── worker-setup-laptop.md
│   │   └── worker-setup-mobile.md
│   └── development/
│       ├── local-setup.md
│       ├── contributing.md
│       └── code-standards.md
│
├── infrastructure/
│   ├── docker/
│   │   ├── docker-compose.yml
│   │   ├── docker-compose.prod.yml
│   │   ├── Dockerfile.api-gateway
│   │   ├── Dockerfile.parameter-server
│   │   ├── Dockerfile.orchestrator
│   │   └── Dockerfile.metrics
│   ├── kubernetes/
│   │   ├── namespaces/
│   │   ├── deployments/
│   │   │   ├── api-gateway.yaml
│   │   │   ├── parameter-server.yaml
│   │   │   ├── orchestrator.yaml
│   │   │   └── metrics.yaml
│   │   ├── services/
│   │   ├── configmaps/
│   │   ├── secrets/
│   │   └── ingress.yaml
│   ├── helm/
│   │   └── meshml/
│   │       ├── Chart.yaml
│   │       ├── values.yaml
│   │       └── templates/
│   └── terraform/
│       ├── aws/
│       ├── gcp/
│       └── azure/
│
├── database/
│   ├── migrations/
│   │   ├── alembic.ini
│   │   └── versions/
│   │       ├── 001_initial_schema.py
│   │       ├── 002_add_workers_table.py
│   │       └── 003_add_jobs_table.py
│   ├── seeds/
│   │   └── dev_data.sql
│   └── schema/
│       ├── workers.sql
│       ├── jobs.sql
│       └── data_batches.sql
│
├── proto/
│   ├── common/
│   │   └── tensor.proto
│   ├── worker.proto
│   ├── parameter_server.proto
│   ├── orchestrator.proto
│   └── BUILD
│
├── services/
│   ├── api-gateway/
│   │   ├── Dockerfile
│   │   ├── requirements.txt
│   │   ├── pyproject.toml
│   │   ├── app/
│   │   │   ├── __init__.py
│   │   │   ├── main.py
│   │   │   ├── config.py
│   │   │   ├── dependencies.py
│   │   │   ├── routers/
│   │   │   │   ├── __init__.py
│   │   │   │   ├── jobs.py
│   │   │   │   ├── workers.py
│   │   │   │   └── metrics.py
│   │   │   ├── models/
│   │   │   │   ├── __init__.py
│   │   │   │   ├── job.py
│   │   │   │   └── worker.py
│   │   │   ├── schemas/
│   │   │   │   ├── __init__.py
│   │   │   │   ├── requests.py
│   │   │   │   └── responses.py
│   │   │   ├── middleware/
│   │   │   │   ├── __init__.py
│   │   │   │   ├── auth.py
│   │   │   │   └── cors.py
│   │   │   └── utils/
│   │   │       ├── __init__.py
│   │   │       └── jwt.py
│   │   └── tests/
│   │       ├── __init__.py
│   │       ├── test_jobs.py
│   │       └── test_workers.py
│   │
│   ├── dataset-sharder/
│   │   ├── Dockerfile
│   │   ├── requirements.txt
│   │   ├── app/
│   │   │   ├── __init__.py
│   │   │   ├── main.py
│   │   │   ├── sharder/
│   │   │   │   ├── __init__.py
│   │   │   │   ├── base.py
│   │   │   │   ├── image_sharder.py
│   │   │   │   └── csv_sharder.py
│   │   │   ├── storage/
│   │   │   │   ├── __init__.py
│   │   │   │   ├── local.py
│   │   │   │   └── s3.py
│   │   │   └── strategies/
│   │   │       ├── __init__.py
│   │   │       ├── even_distribution.py
│   │   │       └── stratified.py
│   │   └── tests/
│   │       └── test_sharder.py
│   │
│   ├── task-orchestrator/
│   │   ├── Dockerfile
│   │   ├── requirements.txt
│   │   ├── app/
│   │   │   ├── __init__.py
│   │   │   ├── main.py
│   │   │   ├── scheduler/
│   │   │   │   ├── __init__.py
│   │   │   │   ├── task_queue.py
│   │   │   │   └── load_balancer.py
│   │   │   ├── health/
│   │   │   │   ├── __init__.py
│   │   │   │   ├── heartbeat_monitor.py
│   │   │   │   └── failure_detector.py
│   │   │   ├── lifecycle/
│   │   │   │   ├── __init__.py
│   │   │   │   ├── job_manager.py
│   │   │   │   └── batch_assigner.py
│   │   │   └── fault_tolerance/
│   │   │       ├── __init__.py
│   │   │       ├── retry_handler.py
│   │   │       └── straggler_mitigation.py
│   │   └── tests/
│   │       ├── test_scheduler.py
│   │       └── test_health.py
│   │
│   ├── parameter-server/
│   │   ├── Dockerfile
│   │   ├── requirements.txt
│   │   ├── app/
│   │   │   ├── __init__.py
│   │   │   ├── main.py
│   │   │   ├── server/
│   │   │   │   ├── __init__.py
│   │   │   │   └── grpc_server.py
│   │   │   ├── aggregation/
│   │   │   │   ├── __init__.py
│   │   │   │   ├── gradient_aggregator.py
│   │   │   │   └── staleness_handler.py
│   │   │   ├── models/
│   │   │   │   ├── __init__.py
│   │   │   │   ├── model_manager.py
│   │   │   │   └── weight_store.py
│   │   │   ├── versioning/
│   │   │   │   ├── __init__.py
│   │   │   │   └── version_tracker.py
│   │   │   ├── optimizers/
│   │   │   │   ├── __init__.py
│   │   │   │   ├── sgd.py
│   │   │   │   └── adam.py
│   │   │   └── convergence/
│   │   │       ├── __init__.py
│   │   │       └── detector.py
│   │   └── tests/
│   │       ├── test_aggregation.py
│   │       └── test_versioning.py
│   │
│   ├── metrics-service/
│   │   ├── Dockerfile
│   │   ├── requirements.txt
│   │   ├── package.json
│   │   ├── app/
│   │   │   ├── __init__.py
│   │   │   ├── main.py
│   │   │   ├── graphql/
│   │   │   │   ├── __init__.py
│   │   │   │   ├── schema.py
│   │   │   │   ├── resolvers/
│   │   │   │   │   ├── __init__.py
│   │   │   │   │   ├── metrics.py
│   │   │   │   │   └── jobs.py
│   │   │   │   └── subscriptions.py
│   │   │   ├── computation/
│   │   │   │   ├── __init__.py
│   │   │   │   ├── accuracy.py
│   │   │   │   ├── f1_score.py
│   │   │   │   └── auc.py
│   │   │   ├── collectors/
│   │   │   │   ├── __init__.py
│   │   │   │   └── timeseries_collector.py
│   │   │   └── alerts/
│   │   │       ├── __init__.py
│   │   │       └── alert_manager.py
│   │   └── tests/
│   │       └── test_metrics.py
│   │
│   └── model-registry/
│       ├── Dockerfile
│       ├── requirements.txt
│       ├── app/
│       │   ├── __init__.py
│       │   ├── main.py
│       │   ├── serializers/
│       │   │   ├── __init__.py
│       │   │   ├── pytorch.py
│       │   │   ├── tensorflow.py
│       │   │   └── onnx.py
│       │   ├── storage/
│       │   │   ├── __init__.py
│       │   │   └── artifact_store.py
│       │   └── versioning/
│       │       ├── __init__.py
│       │       └── version_manager.py
│       └── tests/
│           └── test_serializers.py
│
├── workers/
│   ├── cpp-worker/
│   │   ├── CMakeLists.txt
│   │   ├── conanfile.txt
│   │   ├── vcpkg.json
│   │   ├── src/
│   │   │   ├── main.cpp
│   │   │   ├── worker.h
│   │   │   ├── worker.cpp
│   │   │   ├── grpc/
│   │   │   │   ├── client.h
│   │   │   │   └── client.cpp
│   │   │   ├── compute/
│   │   │   │   ├── tensor_ops.h
│   │   │   │   ├── tensor_ops.cpp
│   │   │   │   ├── forward_pass.cpp
│   │   │   │   └── backward_pass.cpp
│   │   │   ├── acceleration/
│   │   │   │   ├── cpu_simd.h
│   │   │   │   ├── cuda_kernel.cu
│   │   │   │   └── metal_kernel.metal
│   │   │   └── memory/
│   │   │       ├── pool_allocator.h
│   │   │       └── pool_allocator.cpp
│   │   ├── tests/
│   │   │   ├── test_tensor_ops.cpp
│   │   │   └── test_grpc_client.cpp
│   │   └── build/
│   │
│   └── js-worker/
│       ├── package.json
│       ├── webpack.config.js
│       ├── public/
│       │   ├── index.html
│       │   ├── manifest.json
│       │   └── service-worker.js
│       ├── src/
│       │   ├── index.js
│       │   ├── worker.js
│       │   ├── grpc/
│       │   │   └── client.js
│       │   ├── compute/
│       │   │   ├── onnx_runtime.js
│       │   │   └── tensor_ops.js
│       │   ├── utils/
│       │   │   ├── battery_monitor.js
│       │   │   └── network_checker.js
│       │   └── wasm/
│       │       └── tensor_ops.wasm
│       ├── tests/
│       │   └── worker.test.js
│       └── dist/
│
├── dashboard/
│   ├── package.json
│   ├── vite.config.js
│   ├── tailwind.config.js
│   ├── public/
│   │   └── favicon.ico
│   ├── src/
│   │   ├── main.jsx
│   │   ├── App.jsx
│   │   ├── components/
│   │   │   ├── JobList.jsx
│   │   │   ├── JobDetail.jsx
│   │   │   ├── WorkerMesh.jsx
│   │   │   ├── MetricsChart.jsx
│   │   │   └── HealthIndicator.jsx
│   │   ├── pages/
│   │   │   ├── Dashboard.jsx
│   │   │   ├── Jobs.jsx
│   │   │   └── Workers.jsx
│   │   ├── graphql/
│   │   │   ├── client.js
│   │   │   ├── queries.js
│   │   │   └── subscriptions.js
│   │   ├── hooks/
│   │   │   ├── useMetrics.js
│   │   │   └── useJobs.js
│   │   └── utils/
│   │       └── formatters.js
│   └── dist/
│
├── shared/
│   ├── python/
│   │   ├── meshml_common/
│   │   │   ├── __init__.py
│   │   │   ├── database/
│   │   │   │   ├── __init__.py
│   │   │   │   ├── postgres.py
│   │   │   │   └── redis.py
│   │   │   ├── models/
│   │   │   │   ├── __init__.py
│   │   │   │   ├── worker.py
│   │   │   │   ├── job.py
│   │   │   │   └── batch.py
│   │   │   ├── grpc/
│   │   │   │   └── generated/
│   │   │   └── utils/
│   │   │       ├── __init__.py
│   │   │       ├── logging.py
│   │   │       └── config.py
│   │   └── setup.py
│   │
│   └── proto-generated/
│       ├── python/
│       ├── cpp/
│       └── javascript/
│
├── scripts/
│   ├── setup/
│   │   ├── install_deps.sh
│   │   └── init_db.sh
│   ├── deploy/
│   │   ├── deploy_k8s.sh
│   │   └── rollback.sh
│   ├── dev/
│   │   ├── start_services.sh
│   │   ├── stop_services.sh
│   │   └── reset_db.sh
│   └── generate/
│       ├── proto_compile.sh
│       └── api_docs.sh
│
├── monitoring/
│   ├── prometheus/
│   │   └── prometheus.yml
│   ├── grafana/
│   │   ├── dashboards/
│   │   │   ├── system_overview.json
│   │   │   ├── training_metrics.json
│   │   │   └── worker_health.json
│   │   └── datasources/
│   └── jaeger/
│       └── jaeger-config.yaml
│
├── .gitignore
├── .editorconfig
├── .pre-commit-config.yaml
├── README.md
├── LICENSE
├── CONTRIBUTING.md
├── TASKS.md
├── desc.txt
└── tech-stack.md
```

## Key Design Decisions

### Monorepo Structure
- **Advantages**: Shared dependencies, atomic commits across services, easier refactoring
- **Microservices**: Each service is independently deployable via Docker
- **Shared Code**: Common Python library in `shared/python/meshml_common`

### Service Organization
- Each service follows a standard structure: `app/`, `tests/`, `Dockerfile`, `requirements.txt`
- Separation of concerns: routers, models, schemas, middleware
- Proto definitions centralized for consistency

### Build Artifacts
- Python: Virtual environments (`.venv/` in `.gitignore`)
- C++: `build/` directories excluded
- JavaScript: `node_modules/`, `dist/` excluded

### Infrastructure as Code
- Kubernetes manifests for production
- Helm charts for easy deployment
- Terraform for cloud resources (optional)

### Development Experience
- Docker Compose for local full-stack development
- Proto compilation scripts for code generation
- Pre-commit hooks for code quality

### Testing Strategy
- Unit tests alongside each service
- Integration tests in dedicated directories
- E2E tests simulate full training workflows
