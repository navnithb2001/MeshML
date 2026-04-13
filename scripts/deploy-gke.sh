#!/bin/bash
set -e

# ==========================================================
# MeshML GKE Deployment Script
# Fully automated: Cluster → GCS → Images → Manifests → Proxy
# ==========================================================

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
cd "$REPO_ROOT"

# ── Configuration ─────────────────────────────────────────
export GCP_PROJECT_ID="${GCP_PROJECT_ID:-meshml-platform}"
export CLUSTER_NAME="${CLUSTER_NAME:-meshml-cluster}"
export COMPUTE_REGION="${COMPUTE_REGION:-us-central1}"
export ARTIFACT_REGISTRY_URL="${ARTIFACT_REGISTRY_URL:-us-central1-docker.pkg.dev/$GCP_PROJECT_ID/meshml-repo}"
export NAMESPACE="${NAMESPACE:-meshml}"
export PROXY_SERVICE_NAME="${PROXY_SERVICE_NAME:-meshml-proxy}"
export PROJECT_ID="${PROJECT_ID:-$GCP_PROJECT_ID}"
export DATASETS_BUCKET="${DATASETS_BUCKET:-meshml-datasets}"
export MODELS_BUCKET="${MODELS_BUCKET:-meshml-models}"
export ARTIFACTS_BUCKET="${ARTIFACTS_BUCKET:-meshml-artifacts}"

echo "Have you filled out your production database URLs and GCS Bucket names in k8s/base/secrets.yaml and configmap.yaml? (y/n)"
read -r response
if [[ ! "$response" =~ ^[Yy]$ ]]; then
    echo "Please fill them out and re-run the script."
    exit 1
fi

# ── [1/7] Cluster Provisioning ────────────────────────────
echo "[1/7] Setting up GKE Cluster & Authenticating..."
if ! gcloud container clusters describe "$CLUSTER_NAME" --region "$COMPUTE_REGION" --project "$GCP_PROJECT_ID" &>/dev/null; then
    echo "Cluster '$CLUSTER_NAME' not found. Creating a new cluster with 50GB nodes..."
    gcloud container clusters create "$CLUSTER_NAME" \
        --region "$COMPUTE_REGION" \
        --project "$GCP_PROJECT_ID" \
        --machine-type e2-small \
        --disk-size 50GB \
        --num-nodes 1 \
        --scopes "cloud-platform"
else
    echo "Cluster '$CLUSTER_NAME' already exists."
fi

gcloud container clusters get-credentials "$CLUSTER_NAME" --region "$COMPUTE_REGION" --project "$GCP_PROJECT_ID"

# ── [2/7] GCS Bucket Provisioning ────────────────────────
echo "[2/7] Provisioning MeshML Storage Plane..."

ensure_bucket() {
    local bucket_name="$1"
    local bucket_uri="gs://${bucket_name}"

    if gcloud storage ls "$bucket_uri" --project "$GCP_PROJECT_ID" >/dev/null 2>&1; then
        echo "   $bucket_uri already exists."
    else
        echo "   Creating $bucket_uri..."
        gcloud storage buckets create "$bucket_uri" \
            --project="$GCP_PROJECT_ID" \
            --location="$COMPUTE_REGION" \
            --uniform-bucket-level-access
    fi
}

ensure_bucket "$DATASETS_BUCKET"
ensure_bucket "$MODELS_BUCKET"
ensure_bucket "$ARTIFACTS_BUCKET"

GCS_MODELS_BUCKET_URI="gs://${MODELS_BUCKET}"
GCS_DATASETS_BUCKET_URI="gs://${DATASETS_BUCKET}"
GCS_ARTIFACTS_BUCKET_URI="gs://${ARTIFACTS_BUCKET}"

# Grant the GKE node service account write access to the bucket
echo "-> Granting GKE nodes access to GCS bucket..."
PROJECT_NUM=$(gcloud projects describe "$GCP_PROJECT_ID" --format='value(projectNumber)')
NODE_SA="${PROJECT_NUM}-compute@developer.gserviceaccount.com"
gsutil iam ch "serviceAccount:${NODE_SA}:roles/storage.objectAdmin" "$GCS_DATASETS_BUCKET_URI" 2>/dev/null || true
gsutil iam ch "serviceAccount:${NODE_SA}:roles/storage.objectAdmin" "$GCS_MODELS_BUCKET_URI" 2>/dev/null || true
gsutil iam ch "serviceAccount:${NODE_SA}:roles/storage.objectAdmin" "$GCS_ARTIFACTS_BUCKET_URI" 2>/dev/null || true
echo "   GCS access granted to $NODE_SA"

# Create dedicated service account for GCS signing
SA_NAME="meshml-gcs-signer"
SA_EMAIL="${SA_NAME}@${GCP_PROJECT_ID}.iam.gserviceaccount.com"

echo "-> Setting up dedicated GCS signer service account ($SA_NAME)..."
if ! gcloud iam service-accounts describe "$SA_EMAIL" --project="$GCP_PROJECT_ID" &>/dev/null; then
    gcloud iam service-accounts create "$SA_NAME" \
        --display-name="MeshML GCS Signer" \
        --project="$GCP_PROJECT_ID"
else
    echo "   Service account $SA_NAME already exists."
fi

echo "-> Granting storage.admin role to $SA_EMAIL on buckets..."
gsutil iam ch "serviceAccount:${SA_EMAIL}:roles/storage.admin" "$GCS_MODELS_BUCKET_URI" 2>/dev/null || true
gsutil iam ch "serviceAccount:${SA_EMAIL}:roles/storage.admin" "$GCS_DATASETS_BUCKET_URI" 2>/dev/null || true
gsutil iam ch "serviceAccount:${SA_EMAIL}:roles/storage.admin" "$GCS_ARTIFACTS_BUCKET_URI" 2>/dev/null || true

echo "-> Generating JSON key for $SA_NAME..."
gcloud iam service-accounts keys create /tmp/gcs-key.json \
    --iam-account="$SA_EMAIL" \
    --project="$GCP_PROJECT_ID" \
    --quiet 2>/dev/null || echo "   Key creation skipped (might already exist locally)."

# ── [3/7] Build & Push Microservice Images ────────────────
echo "[3/7] Building and pushing Docker images..."
MICROSERVICES=("api-gateway" "dataset-sharder" "model-registry" "task-orchestrator" "parameter-server" "metrics-service" "proxy")

for service in "${MICROSERVICES[@]}"; do
    echo "--- Processing $service ---"
    case $service in
      "proxy") DOCKER_DIR="docker/proxy" ;;
      # Add custom paths here if your Dockerfiles are not at the root of the service directly
      *) DOCKER_DIR="services/$service" ;;
    esac

    # Handle proxy name variation
    if [ "$service" = "proxy" ]; then
      IMAGE_NAME="$ARTIFACT_REGISTRY_URL/meshml-proxy:latest"
    else
      IMAGE_NAME="$ARTIFACT_REGISTRY_URL/$service:latest"
    fi

    docker build --platform linux/amd64 -t "$IMAGE_NAME" "$DOCKER_DIR"
    docker push "$IMAGE_NAME"
done

# ── [4/7] Apply K8s Manifests in Dependency Order ─────────
echo "[4/7] Applying Kubernetes Manifests..."

echo "-> Applying foundational manifests..."
kubectl apply -f k8s/base/namespace.yaml || true

echo "-> Creating GCS credentials secret..."
if [ -f /tmp/gcs-key.json ]; then
    kubectl create secret generic gcs-credentials \
        --from-file=key.json=/tmp/gcs-key.json \
        --namespace="$NAMESPACE" \
        --dry-run=client -o yaml | kubectl apply -f -
    rm -f /tmp/gcs-key.json
    echo "   Created/updated secret gcs-credentials in namespace $NAMESPACE"
else
    echo "   /tmp/gcs-key.json not found, skipping secret creation."
fi

kubectl create configmap meshml-config \
    --namespace="$NAMESPACE" \
    --from-literal=POSTGRES_HOST=postgres-service \
    --from-literal=POSTGRES_PORT=5432 \
    --from-literal=POSTGRES_DB=meshml \
    --from-literal=REDIS_HOST=redis-service \
    --from-literal=REDIS_PORT=6379 \
    --from-literal=API_GATEWAY_URL=http://api-gateway-service:8000 \
    --from-literal=DATASET_SHARDER_URL=http://dataset-sharder-service:8001 \
    --from-literal=TASK_ORCHESTRATOR_URL=http://task-orchestrator-service:8002 \
    --from-literal=PARAMETER_SERVER_URL=http://parameter-server-service:8003 \
    --from-literal=MODEL_REGISTRY_URL=http://model-registry-service:8004 \
    --from-literal=METRICS_SERVICE_URL=http://metrics-service:8005 \
    --from-literal=ORCHESTRATOR_GRPC_URL=task-orchestrator-service:50051 \
    --from-literal=TASK_ORCHESTRATOR_GRPC_URL=task-orchestrator-service:50051 \
    --from-literal=PARAMETER_SERVER_GRPC_URL=parameter-server-service:50054 \
    --from-literal=DATASET_SHARDER_GRPC_URL=dataset-sharder-service:50053 \
    --from-literal=MODEL_REGISTRY_GRPC_URL=model-registry-service:50052 \
    --from-literal=METRICS_SERVICE_GRPC_URL=metrics-service:50055 \
    --from-literal=ENVIRONMENT=production \
    --from-literal=LOG_LEVEL=INFO \
    --from-literal=GCS_BUCKET_DATASETS="$DATASETS_BUCKET" \
    --from-literal=GCS_BUCKET_MODELS="$MODELS_BUCKET" \
    --from-literal=GCS_BUCKET_ARTIFACTS="$ARTIFACTS_BUCKET" \
    --from-literal=GCS_BUCKET_NAME="$MODELS_BUCKET" \
    --from-literal=GCS_PROJECT_ID="$GCP_PROJECT_ID" \
    --from-literal=USE_GCS=true \
    --from-literal=BATCH_STORAGE_TYPE=gcs \
    --dry-run=client -o yaml | kubectl apply -f -
kubectl apply -f k8s/base/secrets.yaml

echo "-> Applying stateful infrastructure..."
# Remove these if you're using managed Cloud SQL / MemoryStore (recommended for prod)
if [ -f "k8s/base/postgres.yaml" ]; then kubectl apply -f k8s/base/postgres.yaml; fi
if [ -f "k8s/base/redis.yaml" ]; then kubectl apply -f k8s/base/redis.yaml; fi

echo "-> Waiting for stateful services to be ready..."
sleep 15

echo "-> Running database migrations..."
POSTGRES_POD=$(kubectl get pod -l app=postgres -n "$NAMESPACE" -o jsonpath="{.items[0].metadata.name}" 2>/dev/null)
if [ -n "$POSTGRES_POD" ]; then
    kubectl wait --for=condition=ready pod/$POSTGRES_POD -n "$NAMESPACE" --timeout=60s
    kubectl exec -i -n "$NAMESPACE" deployment/postgres -- psql -U meshml_user -d meshml -a < ./scripts/init-db.sql || echo "   Migration failed or DB was already initialized."
else
    echo "   Postgres pod not found, skipping local migration."
fi

echo "-> Applying internal gRPC microservices..."
for service in dataset-sharder model-registry task-orchestrator parameter-server metrics-service; do
    if [ -f "k8s/base/$service.yaml" ]; then
      kubectl apply -f "k8s/base/$service.yaml"
    else
      echo "Warning: k8s/base/$service.yaml missing, skipping."
    fi
done

echo "-> Applying External REST Entrypoint (API Gateway)..."
kubectl apply -f k8s/base/api-gateway.yaml

echo "-> Applying Ingress Proxy..."
kubectl apply -f k8s/base/nginx-ingress.yaml

# ── [5/7] Wait for Proxy LoadBalancer ───────────────
echo "[5/7] Waiting for Proxy LoadBalancer external IP..."

while [ -z "$(kubectl -n "$NAMESPACE" get svc meshml-ingress-service -o jsonpath='{.status.loadBalancer.ingress[0].ip}' 2>/dev/null || true)" ]; do
    echo "  Waiting for external IP..."
    sleep 5
done

GATEWAY_IP=$(kubectl -n "$NAMESPACE" get svc meshml-ingress-service -o jsonpath='{.status.loadBalancer.ingress[0].ip}')
echo "   Proxy bound to: $GATEWAY_IP"
PROXY_URL="http://$GATEWAY_IP"

# ── [6/7] Deploy HTTPS Reverse Proxy on Cloud Run ────────
echo "[6/7] Deploying HTTPS reverse proxy to Cloud Run for UI..."

# Deploy to Cloud Run, injecting the GKE IP as the backend API
gcloud run deploy "$PROXY_SERVICE_NAME" \
    --image "$IMAGE_NAME" \
    --region "$COMPUTE_REGION" \
    --project "$GCP_PROJECT_ID" \
    --allow-unauthenticated \
    --port 8080 \
    --set-env-vars "API_GATEWAY_HOST=$GATEWAY_IP,DATASET_SHARDER_HOST=$GATEWAY_IP,TASK_ORCHESTRATOR_HOST=$GATEWAY_IP,PARAMETER_SERVER_HOST=$GATEWAY_IP,MODEL_REGISTRY_HOST=$GATEWAY_IP,METRICS_SERVICE_HOST=$GATEWAY_IP" \
    --quiet

CLOUD_RUN_URL=$(gcloud run services describe "$PROXY_SERVICE_NAME" \
    --region "$COMPUTE_REGION" \
    --project "$GCP_PROJECT_ID" \
    --format='value(status.url)')

echo "   HTTPS UI Proxy deployed at: $CLOUD_RUN_URL"

# ── [7/7] Update Dashboard .env.production ────────────────
echo "[7/7] Configuring dashboard to use Cloud Run proxy..."

cat > dashboard/.env.production <<EOF
VITE_API_BASE_URL=${CLOUD_RUN_URL}/api
VITE_WS_BASE_URL=${CLOUD_RUN_URL/https:/wss:}/api/ws
EOF

echo "   dashboard/.env.production updated with: $CLOUD_RUN_URL"

# ── Summary ───────────────────────────────────────────────
echo ""
echo "=========================================================="
echo "🚀 DEPLOYMENT COMPLETE!"
echo "=========================================================="
echo ""
echo "  GKE Cluster:     $CLUSTER_NAME ($COMPUTE_REGION)"
echo "  Datasets Bucket: $GCS_DATASETS_BUCKET_URI"
echo "  Models Bucket:   $GCS_MODELS_BUCKET_URI"
echo "  Artifacts Bucket:$GCS_ARTIFACTS_BUCKET_URI"
echo "  Proxy Gateway:   $PROXY_URL (Workers - public HTTP/gRPC)"
echo "  HTTPS Proxy:     $CLOUD_RUN_URL (UI - public HTTPS)"
echo ""
echo "  Dashboard .env:  VITE_API_BASE_URL=${CLOUD_RUN_URL}/api"
echo ""
echo "  Next step: Run ./scripts/deploy-dashboard.sh to push"
echo "  the UI to Firebase with the new HTTPS endpoint."
echo "=========================================================="
