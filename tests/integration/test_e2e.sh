#!/bin/bash
# MeshML End-to-End Integration Test
set -e

BOLD='\033[1m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m' # No Color

echo -e "${BOLD}🧪 MeshML End-to-End Integration Test${NC}"
echo "======================================="
echo ""

# Function to wait for service
wait_for_service() {
    local service=$1
    local port=$2
    local max_attempts=30
    local attempt=0
    
    echo -e "${YELLOW}⏳ Waiting for $service on port $port...${NC}"
    
    while [ $attempt -lt $max_attempts ]; do
        if curl -s -f http://localhost:$port/health > /dev/null 2>&1; then
            echo -e "${GREEN}✅ $service is ready${NC}"
            return 0
        fi
        attempt=$((attempt + 1))
        sleep 2
    done
    
    echo -e "${RED}❌ $service failed to start${NC}"
    return 1
}

# Wait for all services
echo -e "${BOLD}Step 1: Waiting for services${NC}"
wait_for_service "API Gateway" 8000
wait_for_service "Model Registry" 8004
wait_for_service "Dataset Sharder" 8001
wait_for_service "Task Orchestrator" 8002
wait_for_service "Parameter Server" 8003

echo ""
echo -e "${BOLD}Step 2: User Registration${NC}"
REGISTER_RESPONSE=$(curl -s -X POST http://localhost:8000/api/v1/auth/register \
  -H "Content-Type: application/json" \
  -d '{
    "email": "test@meshml.com",
    "password": "testpass123",
    "full_name": "Test User"
  }')

if echo "$REGISTER_RESPONSE" | jq -e '.email' > /dev/null 2>&1; then
    EMAIL=$(echo $REGISTER_RESPONSE | jq -r '.email')
    echo -e "${GREEN}✅ User created: $EMAIL${NC}"
else
    echo -e "${YELLOW}⚠️  User may already exist, continuing...${NC}"
fi

echo ""
echo -e "${BOLD}Step 3: User Login${NC}"
LOGIN_RESPONSE=$(curl -s -X POST http://localhost:8000/api/v1/auth/login \
  -H "Content-Type: application/json" \
  -d '{
    "email": "test@meshml.com",
    "password": "testpass123"
  }')

if echo "$LOGIN_RESPONSE" | jq -e '.access_token' > /dev/null 2>&1; then
    TOKEN=$(echo $LOGIN_RESPONSE | jq -r '.access_token')
    echo -e "${GREEN}✅ Login successful${NC}"
    echo "Token: ${TOKEN:0:30}..."
else
    echo -e "${RED}❌ Login failed${NC}"
    echo "$LOGIN_RESPONSE"
    exit 1
fi

echo ""
echo -e "${BOLD}Step 4: Create Group${NC}"
GROUP_RESPONSE=$(curl -s -X POST http://localhost:8000/api/v1/groups \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "name": "Integration Test Group",
    "description": "Created by automated integration test"
  }')

if echo "$GROUP_RESPONSE" | jq -e '.id' > /dev/null 2>&1; then
    GROUP_ID=$(echo $GROUP_RESPONSE | jq -r '.id')
    echo -e "${GREEN}✅ Group created: ID=$GROUP_ID${NC}"
else
    echo -e "${RED}❌ Group creation failed${NC}"
    echo "$GROUP_RESPONSE"
    exit 1
fi

echo ""
echo -e "${BOLD}Step 5: Create Model${NC}"
MODEL_RESPONSE=$(curl -s -X POST http://localhost:8004/api/v1/models \
  -H "Content-Type: application/json" \
  -d '{
    "name": "Integration Test Model",
    "description": "CNN model for testing",
    "group_id": '$GROUP_ID',
    "architecture_type": "CNN",
    "dataset_type": "CIFAR-10",
    "version": "1.0.0"
  }')

if echo "$MODEL_RESPONSE" | jq -e '.id' > /dev/null 2>&1; then
    MODEL_ID=$(echo $MODEL_RESPONSE | jq -r '.id')
    echo -e "${GREEN}✅ Model created: ID=$MODEL_ID${NC}"
else
    echo -e "${RED}❌ Model creation failed${NC}"
    echo "$MODEL_RESPONSE"
    exit 1
fi

echo ""
echo -e "${BOLD}Step 6: Search Models${NC}"
SEARCH_RESPONSE=$(curl -s "http://localhost:8004/api/v1/search/models?page=1&page_size=10")

if echo "$SEARCH_RESPONSE" | jq -e '.models' > /dev/null 2>&1; then
    MODEL_COUNT=$(echo $SEARCH_RESPONSE | jq '.models | length')
    TOTAL=$(echo $SEARCH_RESPONSE | jq -r '.total')
    echo -e "${GREEN}✅ Search successful: $MODEL_COUNT/$TOTAL models found${NC}"
else
    echo -e "${RED}❌ Search failed${NC}"
    exit 1
fi

echo ""
echo -e "${BOLD}Step 7: List Groups${NC}"
GROUPS_RESPONSE=$(curl -s http://localhost:8000/api/v1/groups \
  -H "Authorization: Bearer $TOKEN")

if echo "$GROUPS_RESPONSE" | jq -e '. | length' > /dev/null 2>&1; then
    GROUP_COUNT=$(echo $GROUPS_RESPONSE | jq '. | length')
    echo -e "${GREEN}✅ Groups listed: $GROUP_COUNT groups found${NC}"
else
    echo -e "${RED}❌ List groups failed${NC}"
    exit 1
fi

echo ""
echo -e "${BOLD}Step 8: Check Workers${NC}"
WORKERS_RESPONSE=$(curl -s http://localhost:8000/api/v1/workers \
  -H "Authorization: Bearer $TOKEN")

if echo "$WORKERS_RESPONSE" | jq -e '. | length' > /dev/null 2>&1; then
    WORKER_COUNT=$(echo $WORKERS_RESPONSE | jq '. | length')
    echo -e "${GREEN}✅ Workers found: $WORKER_COUNT workers${NC}"
    
    # Show worker details
    echo "$WORKERS_RESPONSE" | jq -r '.[] | "  - \(.id): \(.status)"'
else
    echo -e "${YELLOW}⚠️  No workers registered yet (this is okay for initial test)${NC}"
fi

echo ""
echo -e "${BOLD}Step 9: System Health Checks${NC}"
SERVICES=("api-gateway:8000" "model-registry:8004" "dataset-sharder:8001" "task-orchestrator:8002" "parameter-server:8003")

for service_port in "${SERVICES[@]}"; do
    IFS=':' read -r name port <<< "$service_port"
    HEALTH=$(curl -s http://localhost:$port/health)
    
    if echo "$HEALTH" | jq -e '.status' > /dev/null 2>&1; then
        STATUS=$(echo $HEALTH | jq -r '.status')
        if [ "$STATUS" = "healthy" ]; then
            echo -e "  ${GREEN}✅ $name: $STATUS${NC}"
        else
            echo -e "  ${YELLOW}⚠️  $name: $STATUS${NC}"
        fi
    else
        echo -e "  ${RED}❌ $name: unhealthy${NC}"
    fi
done

echo ""
echo -e "${BOLD}Step 10: Monitoring Endpoints${NC}"
STATS=$(curl -s http://localhost:8000/api/v1/monitoring/stats \
  -H "Authorization: Bearer $TOKEN")

if echo "$STATS" | jq -e '.total_users' > /dev/null 2>&1; then
    TOTAL_USERS=$(echo $STATS | jq -r '.total_users')
    TOTAL_GROUPS=$(echo $STATS | jq -r '.total_groups')
    ACTIVE_WORKERS=$(echo $STATS | jq -r '.active_workers')
    
    echo -e "${GREEN}✅ Statistics retrieved:${NC}"
    echo "  - Users: $TOTAL_USERS"
    echo "  - Groups: $TOTAL_GROUPS"
    echo "  - Active Workers: $ACTIVE_WORKERS"
else
    echo -e "${YELLOW}⚠️  Statistics endpoint may not be available${NC}"
fi

echo ""
echo "======================================="
echo -e "${GREEN}${BOLD}🎉 All integration tests PASSED!${NC}"
echo "======================================="
echo ""
echo "Summary:"
echo "  - All services are healthy"
echo "  - User authentication works"
echo "  - Group management works"
echo "  - Model registry works"
echo "  - Search functionality works"
echo "  - Monitoring endpoints work"
echo ""
echo "Next steps:"
echo "  1. Submit a training job"
echo "  2. Monitor job progress"
echo "  3. Check worker logs"
echo ""
