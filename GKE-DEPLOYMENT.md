# MeshML Google Kubernetes Engine (GKE) Deployment Guide

This document details the configuration requirements and scripts necessary to deploy the MeshML platform directly to Google Kubernetes Engine (GKE) with zero local-to-prod code changes.

## Prerequisites

Before running the deployment script, ensure you have completed the following Pre-Flight changes:

### 1. Internal Services (gRPC Headless)
Your internal service manifests (like `k8s/base/parameter-server.yaml`, `task-orchestrator.yaml`, `dataset-sharder.yaml`, etc.) are configured as headless services to allow round-robin gRPC load balancing:
```yaml
spec:
  clusterIP: None
```

### 2. Configure Local vs. Production Storage Parity 

**Development (`docker-compose.yml`)**
Specify the explicit MinIO emulator URL for local testing:
```yaml
environment:
  - STORAGE_EMULATOR_URL=http://minio:9000
```

**Production (`k8s/base/configmap.yaml`)**
Omit the emulator. Provide the real Google Cloud Storage bucket name:
```yaml
data:
  GCS_BUCKET_NAME: "your-prod-bucket"
  # STORAGE_EMULATOR_URL is intentionally omitted
```

**Python Storage Client Update (`gcs_client.py`)**
The internal storage client is updated to default dynamically:
```python
import os
from google.cloud import storage

def get_storage_client():
    emulator = os.getenv("STORAGE_EMULATOR_URL")
    if emulator:
        return storage.Client(client_options={"api_endpoint": emulator}, project="local")
    return storage.Client()
```

### 3. Environment Secrets
The `k8s/base/secrets.yaml` file contains placeholders for your actual managed database credentials (Cloud SQL / MemoryStore) which you must fill in before deploying:
```yaml
stringData:
  DATABASE_URL: "postgresql+asyncpg://user:password@<CLOUD_SQL_IP>/meshml"
  REDIS_URL: "redis://<MEMORYSTORE_IP>:6379/0"
```

### 4. API Gateway Configuration
The `k8s/base/api-gateway.yaml` file exposes the gateway via a `LoadBalancer` service without explicitly requiring a pre-allocated static IP. GKE will automatically provision and attach an ephemeral public external IP to serve traffic.

---

## Deployment Process

The deployment process is entirely automated by the `scripts/deploy-gke.sh` script.

To deploy your infrastructure:

1. Allow execution mode:
```bash
chmod +x scripts/deploy-gke.sh
```

2. Run the deployment script:
```bash
./scripts/deploy-gke.sh
```

### What the script does:
1. **Cluster Provisioning:** Verifies if the GKE cluster exists, and if not, provisions a new cluster with 50GB node boot disks and `cloud-platform` OAuth scopes (required for GCS write access).
2. **GCS Bucket Creation & Credentials:** Creates the `meshml-models` GCS bucket if it doesn't exist. It provisions a dedicated service account (`meshml-gcs-signer`) with the `storage.admin` role (granting `storage.buckets.get` and `storage.objects.*` permissions), generates a private JSON key needed for generating GCS Signed URLs, and injects it into the cluster as a Kubernetes secret (`gcs-credentials`).
3. **Build & Push:** Loops through all microservices, automatically enforcing `linux/amd64` builds (resolving Apple Silicon cross-compilation errors), and pushes to Artifact Registry.
4. **Manifest Application:** Applies resources in rigid dependency order (ConfigMaps/Secrets → Stateful DBs → Microservices → Gateway).
5. **LoadBalancer IP Resolution:** Waits for GKE to dynamically assign an external IP to the API Gateway service.
6. **HTTPS Proxy Deployment:** Builds and deploys an Nginx reverse proxy container to Google Cloud Run. The GKE LoadBalancer IP is injected as an environment variable (`GATEWAY_IP`) which Nginx resolves at startup via its built-in `envsubst` template engine. Cloud Run provides a free, globally-trusted HTTPS endpoint (e.g., `https://meshml-proxy-xxx-uc.a.run.app`) that bridges traffic from the Firebase-hosted UI into the HTTP-only GKE cluster.
7. **Dashboard Auto-Configuration:** Writes the Cloud Run HTTPS URL into `dashboard/.env.production` so the next `deploy-dashboard.sh` run will bake the correct endpoints into the compiled frontend.

---

## HTTPS Proxy Architecture

Because the Firebase-hosted dashboard is served over `https://`, browsers enforce **Mixed Content Policy** and block any `fetch()` calls to plain `http://` endpoints. Since the GKE LoadBalancer only exposes HTTP (no SSL certificate without a custom domain), a lightweight Nginx container on **Google Cloud Run** acts as an HTTPS-to-HTTP bridge:

```
Browser (HTTPS) → Cloud Run Proxy (HTTPS, free cert) → GKE LoadBalancer (HTTP)
```

The proxy configuration lives in `docker/proxy/`:
- `nginx.conf.template` — Nginx config with `${GATEWAY_IP}` placeholder
- `nginx-main.conf` — Minimal main config that includes the generated server block
- `Dockerfile` — Uses `nginx:alpine`'s native template support to resolve env vars at startup

Key proxy settings:
- `client_max_body_size 0` — No upload size limits (ML models can be large)
- `proxy_request_buffering off` — Streams uploads directly without disk buffering
- `proxy_read_timeout 300s` — 5-minute timeout for long-running inference requests
- WebSocket `Upgrade` headers for real-time metrics streaming

## Architectural Optimizations & Notes

During deployment testing, several hard constraints were encountered and permanently optimized:
- **GCS Signed URLs & Credentials:** Default GKE Compute Engine credentials only provide workload access tokens, not the private keys required to encode and generate GCS Signed URLs via `blob.generate_signed_url()`. To enable direct frontend-to-GCS uploads, the deployment script natively spawns a dedicated service account (`meshml-gcs-signer`), attaches `storage.admin` (which encompasses `storage.buckets.get` mapping & object access), creates a permanent JSON key, and statically wires it into the Model Registry namespace via a Kubernetes secret (`gcs-credentials`).
- **Cloud Run HTTP/2 Proxy Upgrades:** Google Cloud Run has a legacy limit capping HTTP/1.1 request bodies at exactly 32 MB. Since `api/datasets/upload` relies on continuous raw multi-part binary streaming natively passed through to the GKE cluster, the proxy deploys with the `--use-http2` flag. The Nginx reverse proxy actively terminates the `http2 on;` connections directly bridging unlimited chunks back down the channel into the cluster without 32MB payload drops!
- **GCS OAuth Scopes:** GKE's default node pool uses `devstorage.read_only` scopes, which prevents the Model Registry from writing model artifacts to GCS. The deploy script creates clusters with `--scopes "cloud-platform"` to grant full API access.
- **Disk Pressure Evictions:** The `deploy-gke.sh` script enforces `--disk-size 50GB` on the cluster builder because GKE's default small boot disks often filled up immediately with the heavy 500MB+ Machine Learning container images, causing cascading `DiskPressure` pod evictions.
- **Python ML Dependencies OOMing:** The Python microservices (FastAPI/PyTorch/TensorFlow) naturally spike their hardware usage while eagerly importing libraries on startup. These configurations retain low baseline requests (`requests: cpu: 20m`) to securely fit onto heavily-packed small nodes without stalling out Kubernetes scheduler constraints. Crucially, they lack a hard CPU limit allowing them to "burst" at startup, and their memory limits were natively elevated from `128Mi` to `512Mi` to universally intercept `OOMKilled` (Exit 137) spikes.
- **Probe Assassinations:** Because startup was deeply bottlenecked, Kubelet was aggressively running `livenessProbes` and killing containers under the false assumption that they were dead. The `initialDelaySeconds` on all Python applications is explicitly augmented to `120s`, buying them 2 undisturbed minutes to cleanly invoke their ASGI servers and connect to Postgres.
