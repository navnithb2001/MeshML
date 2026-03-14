#!/bin/bash
# MeshML GKE Deployment Script with Health Checks and Rollback
# Complete deployment automation: Build → Push → Deploy → Verify → Rollback on failure

set -e

# Color output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Deployment tracking
DEPLOYMENT_START_TIME=$(date +%s)
DEPLOYMENT_REVISION=""
ROLLBACK_NEEDED=false

# Cleanup function for rollback
cleanup_on_failure() {
    local exit_code=$?
    if [ $exit_code -ne 0 ]; then
        echo ""
        echo -e "${RED}╔═══════════════════════════════════════════════════════════════╗${NC}"
        echo -e "${RED}║                  DEPLOYMENT FAILED! ✗                         ║${NC}"
        echo -e "${RED}╚═══════════════════════════════════════════════════════════════╝${NC}"
        echo ""
        
        if [ "$ROLLBACK_NEEDED" = true ] && [ ! -z "$DEPLOYMENT_REVISION" ]; then
            echo -e "${YELLOW}Initiating automatic rollback...${NC}"
            rollback_deployment
        fi
        
        echo -e "${RED}Deployment failed at: $(date)${NC}"
        echo -e "${YELLOW}Check logs above for error details${NC}"
        exit $exit_code
    fi
}

trap cleanup_on_failure EXIT

# Rollback function
rollback_deployment() {
    echo -e "${YELLOW}Rolling back all deployments to previous version...${NC}"
    
    # Only platform services (no workers!)
    DEPLOYMENTS=("api-gateway" "dataset-sharder" "task-orchestrator" "parameter-server" "model-registry" "metrics-service")
    
    for deployment in "${DEPLOYMENTS[@]}"; do
        echo -e "${YELLOW}Rolling back $deployment...${NC}"
        kubectl rollout undo deployment/$deployment -n meshml || true
    done
    
    echo -e "${YELLOW}Waiting for rollback to complete...${NC}"
    sleep 10
    
    for deployment in "${DEPLOYMENTS[@]}"; do
        kubectl rollout status deployment/$deployment -n meshml --timeout=300s || true
    done
    
    echo -e "${GREEN}✓ Rollback completed${NC}"
}

# Health check function
check_service_health() {
    local service_url=$1
    local service_name=$2
    local max_attempts=30
    local attempt=1
    
    echo -e "${YELLOW}Checking health of $service_name...${NC}"
    
    while [ $attempt -le $max_attempts ]; do
        if curl -f -s "$service_url/health" > /dev/null 2>&1; then
            echo -e "${GREEN}✓ $service_name is healthy${NC}"
            return 0
        fi
        
        echo -n "."
        sleep 2
        attempt=$((attempt + 1))
    done
    
    echo ""
    echo -e "${RED}✗ $service_name health check failed${NC}"
    return 1
}

# Verify deployment function
verify_deployment() {
    local deployment_name=$1
    local namespace=$2
    
    echo -e "${YELLOW}Verifying deployment: $deployment_name${NC}"
    
    # Check if deployment exists
    if ! kubectl get deployment $deployment_name -n $namespace > /dev/null 2>&1; then
        echo -e "${RED}✗ Deployment $deployment_name not found${NC}"
        return 1
    fi
    
    # Check if pods are running
    local ready_replicas=$(kubectl get deployment $deployment_name -n $namespace -o jsonpath='{.status.readyReplicas}')
    local desired_replicas=$(kubectl get deployment $deployment_name -n $namespace -o jsonpath='{.spec.replicas}')
    
    if [ "$ready_replicas" != "$desired_replicas" ]; then
        echo -e "${RED}✗ $deployment_name: $ready_replicas/$desired_replicas pods ready${NC}"
        return 1
    fi
    
    echo -e "${GREEN}✓ $deployment_name: $ready_replicas/$desired_replicas pods ready${NC}"
    return 0
}

echo -e "${GREEN}╔═══════════════════════════════════════════════════════════════╗${NC}"
echo -e "${GREEN}║          MeshML GKE Deployment Script v2.0                   ║${NC}"
echo -e "${GREEN}║     Build → Push → Deploy → Verify → Rollback on Failure     ║${NC}"
echo -e "${GREEN}╚═══════════════════════════════════════════════════════════════╝${NC}"
echo ""

# Step 1: Check prerequisites
echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo -e "${YELLOW}Step 1: Checking prerequisites...${NC}"
echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"

command -v gcloud >/dev/null 2>&1 || { echo -e "${RED}Error: gcloud CLI not installed${NC}" >&2; exit 1; }
command -v kubectl >/dev/null 2>&1 || { echo -e "${RED}Error: kubectl not installed${NC}" >&2; exit 1; }
command -v docker >/dev/null 2>&1 || { echo -e "${RED}Error: Docker not installed${NC}" >&2; exit 1; }
command -v curl >/dev/null 2>&1 || { echo -e "${RED}Error: curl not installed${NC}" >&2; exit 1; }

echo -e "${GREEN}✓ gcloud CLI installed${NC}"
echo -e "${GREEN}✓ kubectl installed${NC}"
echo -e "${GREEN}✓ Docker installed${NC}"
echo -e "${GREEN}✓ curl installed${NC}"
echo ""

# Step 2: Configuration
echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo -e "${YELLOW}Step 2: Configuration${NC}"
echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"

read -p "Enter your GCP Project ID: " PROJECT_ID
read -p "Enter GCP Region (default: us-central1): " REGION
REGION=${REGION:-us-central1}
read -p "Enter GCP Zone (default: us-central1-a): " ZONE
ZONE=${ZONE:-us-central1-a}
read -p "Enter GKE Cluster Name (default: meshml-cluster): " CLUSTER_NAME
CLUSTER_NAME=${CLUSTER_NAME:-meshml-cluster}

echo ""
echo -e "${YELLOW}Configuration Summary:${NC}"
echo "  Project ID: $PROJECT_ID"
echo "  Region: $REGION"
echo "  Zone: $ZONE"
echo "  Cluster: $CLUSTER_NAME"
echo ""
read -p "Continue with deployment? (y/n) " -n 1 -r
echo
if [[ ! $REPLY =~ ^[Yy]$ ]]; then
    echo -e "${YELLOW}Deployment cancelled${NC}"
    exit 0
fi
echo ""

# Step 3: Set GCP project
echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo -e "${YELLOW}Step 3: Setting GCP project...${NC}"
echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"

gcloud config set project $PROJECT_ID
echo -e "${GREEN}✓ Project set to $PROJECT_ID${NC}"
echo ""

# Step 4: Enable required APIs
echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo -e "${YELLOW}Step 4: Enabling required GCP APIs...${NC}"
echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"

gcloud services enable \
    container.googleapis.com \
    containerregistry.googleapis.com \
    cloudbuild.googleapis.com \
    compute.googleapis.com

echo -e "${GREEN}✓ All required APIs enabled${NC}"
echo ""

# Step 5: Create or verify GKE cluster
echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo -e "${YELLOW}Step 5: Setting up GKE cluster...${NC}"
echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"

if gcloud container clusters describe $CLUSTER_NAME --zone=$ZONE >/dev/null 2>&1; then
    echo -e "${YELLOW}Cluster '$CLUSTER_NAME' already exists${NC}"
    read -p "Use existing cluster? (y/n) " -n 1 -r
    echo
    if [[ ! $REPLY =~ ^[Yy]$ ]]; then
        echo -e "${YELLOW}Deployment cancelled${NC}"
        exit 0
    fi
    echo -e "${GREEN}✓ Using existing cluster${NC}"
else
    echo -e "${YELLOW}Creating new GKE cluster (this may take 5-10 minutes)...${NC}"
    gcloud container clusters create $CLUSTER_NAME \
        --zone=$ZONE \
        --num-nodes=3 \
        --machine-type=n1-standard-4 \
        --disk-size=50GB \
        --enable-autoscaling \
        --min-nodes=3 \
        --max-nodes=10 \
        --enable-autorepair \
        --enable-autoupgrade \
        --addons=HorizontalPodAutoscaling,HttpLoadBalancing \
        --workload-pool=$PROJECT_ID.svc.id.goog
    echo -e "${GREEN}✓ GKE cluster created${NC}"
fi
echo ""

# Step 6: Get cluster credentials
echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo -e "${YELLOW}Step 6: Configuring kubectl credentials...${NC}"
echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"

gcloud container clusters get-credentials $CLUSTER_NAME --zone=$ZONE
echo -e "${GREEN}✓ kubectl configured${NC}"
echo ""

# Step 7: Build and push Docker images
echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo -e "${YELLOW}Step 7: Building and pushing Docker images to GCR...${NC}"
echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"

gcloud auth configure-docker

# Get current directory
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"

cd "$PROJECT_ROOT"

# Only build microservices (NO workers - those run on student devices!)
SERVICES=("api-gateway" "dataset-sharder" "task-orchestrator" "parameter-server" "model-registry" "metrics-service")
BUILD_VERSION=$(date +%Y%m%d-%H%M%S)

echo -e "${YELLOW}Building multi-platform images for linux/amd64 (GKE nodes)...${NC}"

for service in "${SERVICES[@]}"; do
    echo -e "${YELLOW}Building $service...${NC}"
    docker buildx build --platform linux/amd64 \
        -t gcr.io/$PROJECT_ID/meshml-$service:latest \
        -t gcr.io/$PROJECT_ID/meshml-$service:$BUILD_VERSION \
        -f services/$service/Dockerfile \
        services/$service/ \
        --push
    
    echo -e "${GREEN}✓ $service (latest, $BUILD_VERSION) pushed${NC}"
done

echo -e "${GREEN}✓ All platform services built and pushed${NC}"
echo -e "${YELLOW}Note: Workers run on student devices, not in GKE${NC}"
echo ""

# Step 8: Update Kubernetes manifests
echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo -e "${YELLOW}Step 8: Updating Kubernetes manifests...${NC}"
echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"

# Create temporary manifest directory
TEMP_MANIFEST_DIR=$(mktemp -d)
cp -r k8s/base/* $TEMP_MANIFEST_DIR/

# Replace PROJECT_ID in manifests
find $TEMP_MANIFEST_DIR -name "*.yaml" -type f -exec sed -i '' "s/PROJECT_ID/$PROJECT_ID/g" {} \;
echo -e "${GREEN}✓ Manifests updated with project ID${NC}"
echo ""

# Step 9: Deploy to Kubernetes
echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo -e "${YELLOW}Step 9: Deploying to Kubernetes...${NC}"
echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"

# Store current revision for potential rollback
DEPLOYMENT_REVISION=$(kubectl get deployment -n meshml -o jsonpath='{.items[0].metadata.annotations.deployment\.kubernetes\.io/revision}' 2>/dev/null || echo "")
ROLLBACK_NEEDED=true

# Create namespace
echo -e "${YELLOW}Creating namespace...${NC}"
kubectl apply -f $TEMP_MANIFEST_DIR/namespace.yaml
echo -e "${GREEN}✓ Namespace created${NC}"

# Create secrets
echo -e "${YELLOW}Creating secrets...${NC}"
echo -e "${RED}⚠️  WARNING: Using default passwords! Change them in k8s/base/secrets.yaml before production!${NC}"
kubectl apply -f $TEMP_MANIFEST_DIR/secrets.yaml
echo -e "${GREEN}✓ Secrets created${NC}"

# Create ConfigMap
echo -e "${YELLOW}Creating ConfigMap...${NC}"
kubectl apply -f $TEMP_MANIFEST_DIR/configmap.yaml
echo -e "${GREEN}✓ ConfigMap created${NC}"

# Deploy infrastructure (PostgreSQL, Redis)
echo -e "${YELLOW}Deploying infrastructure (PostgreSQL, Redis)...${NC}"
kubectl apply -f $TEMP_MANIFEST_DIR/postgres.yaml
kubectl apply -f $TEMP_MANIFEST_DIR/redis.yaml

# Wait for infrastructure
echo -e "${YELLOW}Waiting for infrastructure to be ready (max 5 minutes)...${NC}"
kubectl wait --for=condition=ready pod -l app=postgres -n meshml --timeout=300s || {
    echo -e "${RED}PostgreSQL failed to start${NC}"
    exit 1
}
kubectl wait --for=condition=ready pod -l app=redis -n meshml --timeout=300s || {
    echo -e "${RED}Redis failed to start${NC}"
    exit 1
}
echo -e "${GREEN}✓ Infrastructure ready${NC}"

# Deploy microservices
echo -e "${YELLOW}Deploying platform services...${NC}"
kubectl apply -f $TEMP_MANIFEST_DIR/api-gateway.yaml
kubectl apply -f $TEMP_MANIFEST_DIR/dataset-sharder.yaml
kubectl apply -f $TEMP_MANIFEST_DIR/task-orchestrator.yaml
kubectl apply -f $TEMP_MANIFEST_DIR/parameter-server.yaml
kubectl apply -f $TEMP_MANIFEST_DIR/model-registry.yaml
kubectl apply -f $TEMP_MANIFEST_DIR/metrics-service.yaml
echo -e "${GREEN}✓ Platform services deployed${NC}"
echo -e "${YELLOW}Note: Workers are NOT deployed to GKE - they run on student devices${NC}"
echo ""

# Step 10: Wait for deployments
echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo -e "${YELLOW}Step 10: Waiting for all deployments to be ready...${NC}"
echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"

kubectl wait --for=condition=available deployment --all -n meshml --timeout=600s || {
    echo -e "${RED}Some deployments failed to become ready${NC}"
    exit 1
}
echo -e "${GREEN}✓ All deployments ready${NC}"
echo ""

# Step 11: Verify deployments
echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo -e "${YELLOW}Step 11: Verifying deployments...${NC}"
echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"

# Only platform services (workers run on student devices)
DEPLOYMENTS=("api-gateway" "dataset-sharder" "task-orchestrator" "parameter-server" "model-registry" "metrics-service")

for deployment in "${DEPLOYMENTS[@]}"; do
    verify_deployment "$deployment" "meshml" || {
        echo -e "${RED}Deployment verification failed for $deployment${NC}"
        exit 1
    }
done
echo ""

# Step 12: Get LoadBalancer IP
echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo -e "${YELLOW}Step 12: Getting LoadBalancer IP...${NC}"
echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"

echo -e "${YELLOW}Waiting for LoadBalancer IP (this may take 1-2 minutes)...${NC}"
EXTERNAL_IP=""
for i in {1..60}; do
    EXTERNAL_IP=$(kubectl get service api-gateway-service -n meshml -o jsonpath='{.status.loadBalancer.ingress[0].ip}' 2>/dev/null)
    if [ ! -z "$EXTERNAL_IP" ]; then
        break
    fi
    echo -n "."
    sleep 2
done

if [ -z "$EXTERNAL_IP" ]; then
    echo ""
    echo -e "${RED}Failed to get LoadBalancer IP${NC}"
    exit 1
fi

echo ""
echo -e "${GREEN}✓ LoadBalancer IP: $EXTERNAL_IP${NC}"
echo ""

# Step 13: Health checks
echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo -e "${YELLOW}Step 13: Running health checks...${NC}"
echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"

echo -e "${YELLOW}Waiting for services to be fully ready...${NC}"
sleep 10

check_service_health "http://$EXTERNAL_IP" "API Gateway" || {
    echo -e "${RED}API Gateway health check failed${NC}"
    exit 1
}
echo ""

# Step 14: Pod status summary
echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo -e "${YELLOW}Step 14: Deployment Status Summary${NC}"
echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo ""
kubectl get pods -n meshml
echo ""
kubectl get services -n meshml
echo ""

# Calculate deployment time
DEPLOYMENT_END_TIME=$(date +%s)
DEPLOYMENT_DURATION=$((DEPLOYMENT_END_TIME - DEPLOYMENT_START_TIME))
DEPLOYMENT_MINUTES=$((DEPLOYMENT_DURATION / 60))
DEPLOYMENT_SECONDS=$((DEPLOYMENT_DURATION % 60))

# Success!
ROLLBACK_NEEDED=false

echo -e "${GREEN}╔═══════════════════════════════════════════════════════════════╗${NC}"
echo -e "${GREEN}║            DEPLOYMENT SUCCESSFUL! ✓                           ║${NC}"
echo -e "${GREEN}╚═══════════════════════════════════════════════════════════════╝${NC}"
echo ""
echo -e "${GREEN}🎉 MeshML is now running on GKE!${NC}"
echo ""
echo -e "${YELLOW}Deployment Information:${NC}"
echo "  Build Version: $BUILD_VERSION"
echo "  Deployment Time: ${DEPLOYMENT_MINUTES}m ${DEPLOYMENT_SECONDS}s"
echo "  Cluster: $CLUSTER_NAME"
echo "  Zone: $ZONE"
echo ""
echo -e "${YELLOW}Access Information:${NC}"
echo "  API Gateway: http://$EXTERNAL_IP"
echo "  Health Check: http://$EXTERNAL_IP/health"
echo ""
echo -e "${YELLOW}Quick Test:${NC}"
echo "  curl http://$EXTERNAL_IP/health"
echo ""
echo -e "${YELLOW}Useful Commands:${NC}"
echo "  View pods:        kubectl get pods -n meshml"
echo "  View services:    kubectl get services -n meshml"
echo "  View logs:        kubectl logs -f deployment/api-gateway -n meshml"
echo "  Scale workers:    kubectl scale deployment python-worker --replicas=5 -n meshml"
echo "  Port forward:     kubectl port-forward -n meshml svc/api-gateway-service 8000:80"
echo "  Rollback:         kubectl rollout undo deployment/api-gateway -n meshml"
echo ""
echo -e "${RED}⚠️  SECURITY REMINDER:${NC}"
echo "  1. Change default passwords in k8s/base/secrets.yaml"
echo "  2. Apply updated secrets: kubectl apply -f k8s/base/secrets.yaml"
echo "  3. Restart pods: kubectl rollout restart deployment -n meshml"
echo ""
echo -e "${YELLOW}Next Steps:${NC}"
echo "  1. Configure monitoring and alerts"
echo "  2. Set up backup strategies"
echo "  3. Configure custom domain and SSL"
echo "  4. Review and adjust autoscaling settings"
echo ""

# Cleanup temp files
rm -rf $TEMP_MANIFEST_DIR

exit 0
