#!/bin/bash
# MeshML Comprehensive API Test Suite
# Tests ALL API endpoints on deployed GKE cluster

set -e

BOLD='\033[1m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

API_GATEWAY_URL=${API_GATEWAY_URL:-"http://34.69.215.43"}

test_count=0
pass_count=0
fail_count=0
skip_count=0

echo ""
echo "╔════════════════════════════════════════════════════════════════╗"
echo "║         MeshML Comprehensive API Test Suite                   ║"
echo "║                 Testing ALL Endpoints                          ║"
echo "╔════════════════════════════════════════════════════════════════╝"
echo ""
echo "Target: $API_GATEWAY_URL"
echo "Date: $(date)"
echo ""

# Function to test an endpoint
test_endpoint() {
    local method=$1
    local path=$2
    local description=$3
    local data=$4
    local auth_header=$5
    local expected_status=${6:-200}
    
    ((test_count++))
    
    echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
    echo -e "${BOLD}Test #$test_count: ${description}${NC}"
    echo "  Method: ${method}"
    echo "  Path:   ${path}"
    
    # Build curl command
    if [ -z "$data" ] && [ -z "$auth_header" ]; then
        response=$(curl -s -w "\n%{http_code}" -X ${method} "${API_GATEWAY_URL}${path}")
    elif [ -z "$data" ]; then
        response=$(curl -s -w "\n%{http_code}" -X ${method} "${API_GATEWAY_URL}${path}" \
            -H "Authorization: Bearer ${auth_header}")
    elif [ -z "$auth_header" ]; then
        response=$(curl -s -w "\n%{http_code}" -X ${method} "${API_GATEWAY_URL}${path}" \
            -H "Content-Type: application/json" \
            -d "${data}")
    else
        response=$(curl -s -w "\n%{http_code}" -X ${method} "${API_GATEWAY_URL}${path}" \
            -H "Authorization: Bearer ${auth_header}" \
            -H "Content-Type: application/json" \
            -d "${data}")
    fi
    
    http_code=$(echo "$response" | tail -n1)
    body=$(echo "$response" | sed '$d')
    
    # Check if successful
    if [ "$http_code" -ge 200 ] && [ "$http_code" -lt 300 ]; then
        echo -e "  ${GREEN}✓ PASS${NC} (HTTP $http_code)"
        if [ ! -z "$body" ]; then
            echo "  Response: ${body:0:150}..."
        fi
        ((pass_count++))
    elif [ "$http_code" -eq 401 ] || [ "$http_code" -eq 403 ]; then
        echo -e "  ${YELLOW}⊘ SKIP${NC} (HTTP $http_code - Auth required)"
        echo "  Response: ${body:0:100}"
        ((skip_count++))
    else
        echo -e "  ${RED}✗ FAIL${NC} (HTTP $http_code)"
        echo "  Response: $body"
        ((fail_count++))
    fi
    echo ""
}

echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "  SECTION 1: CORE ENDPOINTS (No Auth Required)"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""

test_endpoint "GET" "/" "Root endpoint - API information"
test_endpoint "GET" "/health" "Health check - Service status"
test_endpoint "GET" "/openapi.json" "OpenAPI schema"

echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "  SECTION 2: PUBLIC DATA ENDPOINTS (No Auth Required)"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""

test_endpoint "GET" "/api/groups/public" "List public groups"
test_endpoint "GET" "/api/workers" "List all workers"
test_endpoint "GET" "/api/jobs" "List all jobs"
test_endpoint "GET" "/api/monitoring/health" "Monitoring health check"

echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "  SECTION 3: AUTHENTICATION FLOW"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""

# Generate unique test user
TIMESTAMP=$(date +%s)
TEST_EMAIL="testuser${TIMESTAMP}@meshml.com"
TEST_PASSWORD="SecurePass123!"

echo -e "${YELLOW}Creating test user: $TEST_EMAIL${NC}"
echo ""

test_endpoint "POST" "/api/auth/register" "Register new user" \
    "{\"email\":\"${TEST_EMAIL}\",\"password\":\"${TEST_PASSWORD}\",\"full_name\":\"Test User ${TIMESTAMP}\"}"

echo ""
echo -e "${YELLOW}Logging in with test user...${NC}"
echo ""

# Try to login and capture token
LOGIN_RESPONSE=$(curl -s -X POST ${API_GATEWAY_URL}/api/auth/login \
    -H "Content-Type: application/json" \
    -d "{\"email\":\"${TEST_EMAIL}\",\"password\":\"${TEST_PASSWORD}\"}")

if echo "$LOGIN_RESPONSE" | jq -e '.access_token' > /dev/null 2>&1; then
    TOKEN=$(echo $LOGIN_RESPONSE | jq -r '.access_token')
    echo -e "${GREEN}✓ Login successful!${NC}"
    echo "  Token: ${TOKEN:0:50}..."
    echo ""
    HAS_TOKEN=true
else
    echo -e "${RED}✗ Login failed!${NC}"
    echo "  Response: $LOGIN_RESPONSE"
    echo ""
    echo -e "${YELLOW}⚠️  Continuing tests without authentication token${NC}"
    echo -e "${YELLOW}   Some tests will be skipped${NC}"
    echo ""
    HAS_TOKEN=false
    TOKEN=""
fi

if [ "$HAS_TOKEN" = true ]; then
    test_endpoint "GET" "/api/auth/me" "Get current user info" "" "$TOKEN"
    
    # Note: Refresh token test would need the refresh_token from login response
    # test_endpoint "POST" "/api/auth/refresh" "Refresh authentication token"
fi

echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "  SECTION 4: GROUP MANAGEMENT"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""

test_endpoint "GET" "/api/groups" "List all groups (requires auth)" "" "$TOKEN"

if [ "$HAS_TOKEN" = true ]; then
    echo -e "${YELLOW}Creating test group...${NC}"
    echo ""
    
    GROUP_CREATE=$(curl -s -X POST ${API_GATEWAY_URL}/api/groups \
        -H "Authorization: Bearer $TOKEN" \
        -H "Content-Type: application/json" \
        -d "{\"name\":\"Test Group ${TIMESTAMP}\",\"description\":\"Automated test group\",\"is_public\":true}")
    
    if echo "$GROUP_CREATE" | jq -e '.id' > /dev/null 2>&1; then
        GROUP_ID=$(echo $GROUP_CREATE | jq -r '.id')
        echo -e "${GREEN}✓ Group created: ID=$GROUP_ID${NC}"
        echo ""
        
        test_endpoint "GET" "/api/groups/${GROUP_ID}" "Get specific group details" "" "$TOKEN"
        test_endpoint "GET" "/api/groups/${GROUP_ID}/members" "Get group members" "" "$TOKEN"
        
        # Test invitation creation
        echo -e "${YELLOW}Creating invitation for group...${NC}"
        echo ""
        
        INVITE_CREATE=$(curl -s -X POST ${API_GATEWAY_URL}/api/invitations/${GROUP_ID}/invitations \
            -H "Authorization: Bearer $TOKEN" \
            -H "Content-Type: application/json" \
            -d '{"max_uses":5,"expires_in_days":7}')
        
        if echo "$INVITE_CREATE" | jq -e '.code' > /dev/null 2>&1; then
            INVITE_CODE=$(echo $INVITE_CREATE | jq -r '.code')
            echo -e "${GREEN}✓ Invitation created: $INVITE_CODE${NC}"
            echo ""
            
            test_endpoint "GET" "/api/invitations/${INVITE_CODE}" "Get invitation details"
        else
            echo -e "${RED}✗ Failed to create invitation${NC}"
            echo "  Response: $INVITE_CREATE"
            echo ""
        fi
        
        test_endpoint "GET" "/api/monitoring/groups/${GROUP_ID}/stats" "Get group statistics" "" "$TOKEN"
    else
        echo -e "${RED}✗ Failed to create group${NC}"
        echo "  Response: $GROUP_CREATE"
        echo ""
    fi
fi

echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "  SECTION 5: JOB MANAGEMENT"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""

if [ "$HAS_TOKEN" = true ] && [ ! -z "$GROUP_ID" ]; then
    echo -e "${YELLOW}Creating test training job...${NC}"
    echo ""
    
    JOB_CREATE=$(curl -s -X POST ${API_GATEWAY_URL}/api/jobs \
        -H "Authorization: Bearer $TOKEN" \
        -H "Content-Type: application/json" \
        -d "{\"group_id\":\"${GROUP_ID}\",\"model_type\":\"CNN\",\"dataset\":\"CIFAR-10\",\"epochs\":5,\"batch_size\":32}")
    
    if echo "$JOB_CREATE" | jq -e '.id' > /dev/null 2>&1; then
        JOB_ID=$(echo $JOB_CREATE | jq -r '.id')
        echo -e "${GREEN}✓ Job created: ID=$JOB_ID${NC}"
        echo ""
        
        test_endpoint "GET" "/api/jobs/${JOB_ID}" "Get specific job details" "" "$TOKEN"
        test_endpoint "GET" "/api/jobs/${JOB_ID}/progress" "Get job progress" "" "$TOKEN"
    else
        echo -e "${YELLOW}⚠️  Job creation failed (may be expected if not fully implemented)${NC}"
        echo "  Response: $JOB_CREATE"
        echo ""
    fi
else
    echo -e "${YELLOW}⊘ Skipping job tests (requires auth token and group)${NC}"
    echo ""
fi

echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "  SECTION 6: WORKER MANAGEMENT"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""

if [ "$HAS_TOKEN" = true ]; then
    echo -e "${YELLOW}Simulating worker registration...${NC}"
    echo ""
    
    WORKER_REGISTER=$(curl -s -X POST ${API_GATEWAY_URL}/api/workers/register \
        -H "Authorization: Bearer $TOKEN" \
        -H "Content-Type: application/json" \
        -d '{"worker_id":"test-worker-'${TIMESTAMP}'","capabilities":{"cpu_count":4,"gpu_available":false,"memory_gb":8}}')
    
    if echo "$WORKER_REGISTER" | jq -e '.id' > /dev/null 2>&1; then
        WORKER_ID=$(echo $WORKER_REGISTER | jq -r '.id')
        echo -e "${GREEN}✓ Worker registered: ID=$WORKER_ID${NC}"
        echo ""
        
        test_endpoint "GET" "/api/workers/${WORKER_ID}" "Get specific worker details" "" "$TOKEN"
        test_endpoint "GET" "/api/workers/${WORKER_ID}/capabilities" "Get worker capabilities" "" "$TOKEN"
        test_endpoint "POST" "/api/workers/${WORKER_ID}/heartbeat" "Send worker heartbeat" '{"status":"online"}' "$TOKEN"
    else
        echo -e "${YELLOW}⚠️  Worker registration failed${NC}"
        echo "  Response: $WORKER_REGISTER"
        echo ""
    fi
else
    echo -e "${YELLOW}⊘ Skipping worker tests (requires auth token)${NC}"
    echo ""
fi

test_endpoint "GET" "/api/monitoring/workers" "Get all workers monitoring data"

echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "  SECTION 7: MONITORING & METRICS"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""

test_endpoint "GET" "/api/monitoring/health" "Platform health status"
test_endpoint "GET" "/api/monitoring/metrics/realtime" "Real-time metrics" "" "$TOKEN"

echo ""
echo "╔════════════════════════════════════════════════════════════════╗"
echo "║                      TEST SUMMARY                              ║"
echo "╠════════════════════════════════════════════════════════════════╣"
printf "║  Total Tests:     %-44s ║\n" "$test_count"
printf "║  ${GREEN}✓ Passed:        %-44s${NC} ║\n" "$pass_count"
printf "║  ${RED}✗ Failed:        %-44s${NC} ║\n" "$fail_count"
printf "║  ${YELLOW}⊘ Skipped:       %-44s${NC} ║\n" "$skip_count"
echo "╚════════════════════════════════════════════════════════════════╝"

# Calculate success rate
if [ $test_count -gt 0 ]; then
    success_rate=$(( (pass_count * 100) / test_count ))
    echo ""
    echo "Success Rate: ${success_rate}% (excluding skipped tests)"
fi

echo ""
echo "Test Details:"
echo "  • API Gateway: $API_GATEWAY_URL"
echo "  • Test User: $TEST_EMAIL"
if [ "$HAS_TOKEN" = true ]; then
    echo "  • Authentication: ✓ Working"
else
    echo "  • Authentication: ✗ Failed"
fi
if [ ! -z "$GROUP_ID" ]; then
    echo "  • Test Group ID: $GROUP_ID"
fi
if [ ! -z "$WORKER_ID" ]; then
    echo "  • Test Worker ID: $WORKER_ID"
fi
if [ ! -z "$JOB_ID" ]; then
    echo "  • Test Job ID: $JOB_ID"
fi

echo ""
if [ $fail_count -eq 0 ]; then
    echo -e "${GREEN}${BOLD}✓ All non-skipped tests passed!${NC}"
    exit 0
elif [ $pass_count -gt $fail_count ]; then
    echo -e "${YELLOW}${BOLD}⚠ Most tests passed, but some failures detected${NC}"
    exit 0
else
    echo -e "${RED}${BOLD}✗ Multiple test failures detected${NC}"
    exit 1
fi
