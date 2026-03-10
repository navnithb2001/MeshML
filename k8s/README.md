# MeshML GKE Deployment Guide

This guide will help you deploy the **MeshML Platform** (control plane only) to Google Kubernetes Engine (GKE).

**Important**: This deployment includes only the **platform services** (API Gateway, Task Orchestrator, Parameter Server, etc.). **Workers run on student devices**, not in GKE - students install the worker software on their laptops/desktops to contribute compute.

## What Gets Deployed

### ✅ Platform Services (GKE)
- **API Gateway** - Authentication, job management
- **Dataset Sharder** - Data distribution to workers  
- **Task Orchestrator** - Job assignment and worker coordination
- **Parameter Server** - Gradient aggregation for federated learning
- **Model Registry** - Model versioning and storage
- **PostgreSQL** - Database for jobs, users, models
- **Redis** - Caching and task queues

### ❌ What Does NOT Get Deployed
- **Workers** - These run on student devices (installed via `pip install meshml-worker`)

## 📋 Prerequisites

Before deploying, ensure you have:

1. **Google Cloud Account** with billing enabled
2. **gcloud CLI** installed and configured
   ```bash
   # Install gcloud
   curl https://sdk.cloud.google.com | bash
   exec -l $SHELL
   gcloud init
   ```

3. **kubectl** installed
   ```bash
   gcloud components install kubectl
   ```

4. **Docker** installed and running

5. **GCP Project** created
   ```bash
   gcloud projects create YOUR-PROJECT-ID
   gcloud config set project YOUR-PROJECT-ID
   ```

## 🚀 Quick Deploy

### Option 1: Automated Deployment (Recommended)

Run the automated deployment script:

```bash
./scripts/deploy-gke.sh
```

The script will:
1. Check prerequisites
2. Create GKE cluster (3-10 nodes, autoscaling)
3. Build and push Docker images to Google Container Registry (5 services)
4. Deploy all platform services to Kubernetes
5. Configure load balancer
6. Display access information

**Estimated time:** 15-20 minutes

**Note:** This deploys the platform only. Students install workers separately on their devices.

### Option 2: Manual Deployment

If you prefer manual control:

#### Step 1: Create GKE Cluster

```bash
export PROJECT_ID=your-project-id
export REGION=us-central1
export ZONE=us-central1-a
export CLUSTER_NAME=meshml-cluster

gcloud container clusters create $CLUSTER_NAME \
  --zone=$ZONE \
  --num-nodes=3 \
  --machine-type=n1-standard-4 \
  --enable-autoscaling \
  --min-nodes=3 \
  --max-nodes=10
```

#### Step 2: Get Cluster Credentials

```bash
gcloud container clusters get-credentials $CLUSTER_NAME --zone=$ZONE
```

#### Step 3: Build and Push Docker Images

```bash
gcloud auth configure-docker

# Build and push each service
for service in api-gateway dataset-sharder task-orchestrator parameter-server model-registry; do
  docker build -t gcr.io/$PROJECT_ID/meshml-$service:latest \
    -f services/$service/Dockerfile services/$service/
  docker push gcr.io/$PROJECT_ID/meshml-$service:latest
done

# Note: Workers are NOT built/deployed to GKE
# Students install workers on their devices via: pip install meshml-worker
```

#### Step 4: Update Kubernetes Manifests

```bash
# Replace PROJECT_ID in manifests
find k8s/base -name "*.yaml" -type f -exec sed -i "s/PROJECT_ID/$PROJECT_ID/g" {} \;
```

#### Step 5: Deploy to Kubernetes

```bash
# Create namespace
kubectl apply -f k8s/base/namespace.yaml

# Deploy secrets and config
kubectl apply -f k8s/base/secrets.yaml
kubectl apply -f k8s/base/configmap.yaml

# Deploy infrastructure
kubectl apply -f k8s/base/postgres.yaml
kubectl apply -f k8s/base/redis.yaml

# Wait for infrastructure
kubectl wait --for=condition=ready pod -l app=postgres -n meshml --timeout=300s
kubectl wait --for=condition=ready pod -l app=redis -n meshml --timeout=300s

# Deploy microservices
kubectl apply -f k8s/base/api-gateway.yaml
kubectl apply -f k8s/base/dataset-sharder.yaml
kubectl apply -f k8s/base/task-orchestrator.yaml
kubectl apply -f k8s/base/parameter-server.yaml
kubectl apply -f k8s/base/model-registry.yaml

# Note: python-worker.yaml does NOT exist - workers run on student devices
```

#### Step 6: Get External IP

```bash
kubectl get service api-gateway-service -n meshml
```

## 🔒 Security Configuration

### ⚠️ IMPORTANT: Change Default Passwords

Before deploying to production, update `k8s/base/secrets.yaml`:

```yaml
stringData:
  POSTGRES_PASSWORD: "YOUR-STRONG-PASSWORD-HERE"
  REDIS_PASSWORD: "YOUR-STRONG-PASSWORD-HERE"
  JWT_SECRET: "YOUR-RANDOM-SECRET-HERE"
```

### Recommended: Use Google Secret Manager

For production, use Google Secret Manager instead of Kubernetes secrets:

```bash
# Create secrets in Secret Manager
echo -n "your-password" | gcloud secrets create postgres-password --data-file=-

# Reference in deployments
env:
  - name: POSTGRES_PASSWORD
    valueFrom:
      secretKeyRef:
        name: postgres-password
```

## 📊 Monitoring Deployment

### Check Pod Status

```bash
kubectl get pods -n meshml
```

### View Logs

```bash
# All pods
kubectl logs -f deployment/api-gateway -n meshml

# Specific service
kubectl logs -f -l app=python-worker -n meshml
```

### Check Services

```bash
kubectl get services -n meshml
```

### Describe Resources

```bash
kubectl describe deployment api-gateway -n meshml
```

## 🔧 Management Commands

### Scale Workers

**Workers do NOT run in GKE!** Students run workers on their devices:

```bash
# Students install worker on their laptop/desktop:
pip install meshml-worker

# Initialize and join training group
meshml-worker init
meshml-worker join --invitation inv_abc123

# Start worker (contributes compute)
meshml-worker start
```

To see connected workers:

```bash
# Query API Gateway for registered workers
curl http://$EXTERNAL_IP/api/workers
```

### Update Image

```bash
# Rebuild and push new image
docker build -t gcr.io/$PROJECT_ID/meshml-api-gateway:v2 services/api-gateway/
docker push gcr.io/$PROJECT_ID/meshml-api-gateway:v2

# Update deployment
kubectl set image deployment/api-gateway \
  api-gateway=gcr.io/$PROJECT_ID/meshml-api-gateway:v2 \
  -n meshml
```

### Rollback Deployment

```bash
kubectl rollout undo deployment/api-gateway -n meshml
```

### Port Forwarding (Local Access)

```bash
kubectl port-forward -n meshml svc/api-gateway-service 8000:80
# Access at http://localhost:8000
```

## 💰 Cost Estimation

### GKE Cluster Cost (us-central1)

**Platform Services Only** (no workers - they run on student devices):

- **3x n1-standard-2 nodes**: ~$150/month (can reduce to n1-standard-1)
- **LoadBalancer**: ~$18/month
- **Persistent Disks**: ~$10/month (30Gi total)
- **Network Egress**: Variable (~$20-50/month)

**Total: ~$200-230/month** 

### Cost Optimization Tips

1. **Use smaller nodes** - n1-standard-1 sufficient for platform services
   ```bash
   --machine-type=n1-standard-1  # Saves ~50%
   ```

2. **Use Preemptible Nodes** (70% cheaper, but can be terminated):
   ```bash
   --preemptible
   ```

3. **Reduce minimum nodes** to 2 during low usage

4. **Use Cloud SQL** (Postgres) instead of in-cluster for better HA

5. **No worker costs** - Students provide compute for free! 🎉

## 🧪 Testing Deployment

### Health Check

```bash
EXTERNAL_IP=$(kubectl get service api-gateway-service -n meshml -o jsonpath='{.status.loadBalancer.ingress[0].ip}')
curl http://$EXTERNAL_IP/health
```

### Create Test User

```bash
curl -X POST http://$EXTERNAL_IP/api/auth/register \
  -H "Content-Type: application/json" \
  -d '{
    "email": "test@meshml.com",
    "password": "testpass123",
    "full_name": "Test User"
  }'
```

## 🗑️ Cleanup

### Delete Deployments Only

```bash
kubectl delete namespace meshml
```

### Delete Everything (Cluster + Deployments)

```bash
gcloud container clusters delete $CLUSTER_NAME --zone=$ZONE
```

## 🐛 Troubleshooting

### Pods Not Starting

```bash
kubectl describe pod <pod-name> -n meshml
kubectl logs <pod-name> -n meshml
```

### LoadBalancer IP Pending

Wait up to 5 minutes for GCP to provision the LoadBalancer

### Database Connection Issues

Check if PostgreSQL is ready:
```bash
kubectl exec -it deployment/postgres -n meshml -- psql -U meshml_user -d meshml
```

### Worker Not Connecting

Check environment variables:
```bash
kubectl exec -it deployment/python-worker -n meshml -- env
```

## 📚 Additional Resources

- [GKE Documentation](https://cloud.google.com/kubernetes-engine/docs)
- [Kubernetes Best Practices](https://kubernetes.io/docs/concepts/configuration/overview/)
- [Google Container Registry](https://cloud.google.com/container-registry/docs)

## 🎯 Next Steps

After successful deployment:

1. Configure custom domain and SSL certificate
2. Set up Cloud Monitoring and Logging
3. Configure backup strategies
4. Implement CI/CD pipeline with Cloud Build
5. Set up staging environment

---

**Questions?** Check the logs or create an issue in the repository.
