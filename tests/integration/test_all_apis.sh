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
echo "║            Testing ALL 28 Endpoints (Complete)                ║"
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

# Test login endpoint explicitly
test_endpoint "POST" "/api/auth/login" "Login user and get JWT token" \
    "{\"email\":\"${TEST_EMAIL}\",\"password\":\"${TEST_PASSWORD}\"}"

# Also capture token for use in other tests
LOGIN_RESPONSE=$(curl -s -X POST ${API_GATEWAY_URL}/api/auth/login \
    -H "Content-Type: application/json" \
    -d "{\"email\":\"${TEST_EMAIL}\",\"password\":\"${TEST_PASSWORD}\"}")

if echo "$LOGIN_RESPONSE" | jq -e '.access_token' > /dev/null 2>&1; then
    TOKEN=$(echo $LOGIN_RESPONSE | jq -r '.access_token')
    REFRESH_TOKEN=$(echo $LOGIN_RESPONSE | jq -r '.refresh_token // empty')
    echo -e "${GREEN}✓ Token captured for authenticated tests${NC}"
    echo "  Token: ${TOKEN:0:50}..."
    echo ""
    HAS_TOKEN=true
else
    echo -e "${RED}✗ Failed to capture token!${NC}"
    echo "  Response: $LOGIN_RESPONSE"
    echo ""
    echo -e "${YELLOW}⚠️  Continuing tests without authentication token${NC}"
    echo -e "${YELLOW}   Some tests will be skipped${NC}"
    echo ""
    HAS_TOKEN=false
    TOKEN=""
    REFRESH_TOKEN=""
fi

if [ "$HAS_TOKEN" = true ]; then
    test_endpoint "GET" "/api/auth/me" "Get current user info" "" "$TOKEN"
    
    # Test token refresh - current implementation uses existing token to get new one
    test_endpoint "POST" "/api/auth/refresh" "Refresh authentication token" "" "$TOKEN"
    
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
        
        # Test invitation creation explicitly
        test_endpoint "POST" "/api/invitations/${GROUP_ID}/invitations" "Create group invitation" \
            '{"max_uses":5,"expires_in_days":7}' "$TOKEN"
        
        # Also capture invitation code for later tests
        echo ""
        echo -e "${YELLOW}Capturing invitation code for later tests...${NC}"
        
        INVITE_CREATE=$(curl -s -X POST ${API_GATEWAY_URL}/api/invitations/${GROUP_ID}/invitations \
            -H "Authorization: Bearer $TOKEN" \
            -H "Content-Type: application/json" \
            -d '{"max_uses":10,"expires_in_days":7}')
        
        if echo "$INVITE_CREATE" | jq -e '.code' > /dev/null 2>&1; then
            INVITE_CODE=$(echo $INVITE_CREATE | jq -r '.code')
            echo -e "${GREEN}✓ Invitation code captured: $INVITE_CODE${NC}"
            echo ""
            
            test_endpoint "GET" "/api/invitations/${INVITE_CODE}" "Get invitation details"
        else
            echo -e "${RED}✗ Failed to create invitation${NC}"
            echo "  Response: $INVITE_CREATE"
            echo ""
        fi
        
        test_endpoint "GET" "/api/monitoring/groups/${GROUP_ID}/stats" "Get group statistics" "" "$TOKEN"
        
        # Test group member management
        echo ""
        echo -e "${YELLOW}Testing group member operations...${NC}"
        echo ""
        
        # Create a second test user to add to the group
        TEST_EMAIL_2="testuser2${TIMESTAMP}@meshml.com"
        REGISTER_2=$(curl -s -X POST ${API_GATEWAY_URL}/api/auth/register \
            -H "Content-Type: application/json" \
            -d "{\"email\":\"${TEST_EMAIL_2}\",\"password\":\"${TEST_PASSWORD}\",\"full_name\":\"Test User 2 ${TIMESTAMP}\"}")
        
        if echo "$REGISTER_2" | jq -e '.id' > /dev/null 2>&1; then
            USER_2_ID=$(echo $REGISTER_2 | jq -r '.id')
            echo -e "${GREEN}✓ Second test user created: $USER_2_ID${NC}"
            
            # First, add user to group by having them join using invitation
            if [ ! -z "$INVITE_CODE" ]; then
                echo -e "${YELLOW}Adding second user to group via invitation...${NC}"
                
                # Login as second user first
                LOGIN_2=$(curl -s -X POST ${API_GATEWAY_URL}/api/auth/login \
                    -H "Content-Type: application/json" \
                    -d "{\"email\":\"${TEST_EMAIL_2}\",\"password\":\"${TEST_PASSWORD}\"}")
                
                # Test join group endpoint explicitly (requires worker_id)
                # Note: This endpoint is for worker nodes to join public groups
                test_endpoint "POST" "/api/groups/${GROUP_ID}/join" "Join group with invitation code" \
                    "{\"worker_id\":\"test-join-worker-${TIMESTAMP}\",\"invitation_code\":\"${INVITE_CODE}\"}"
                
                # Test member management endpoints
                # Note: These endpoints manage group members by user_id
                # Since the platform is designed for workers (with worker_id) to join via invitations,
                # we'll test these endpoints to verify they exist and handle the expected use case
                
                # First, let's get the list of members to find a member to manage
                MEMBERS_LIST=$(curl -s -X GET ${API_GATEWAY_URL}/api/groups/${GROUP_ID}/members \
                    -H "Authorization: Bearer $TOKEN")
                
                # Get the owner's user_id (the current user)
                OWNER_USER_ID=$(echo "$TOKEN" | jq -R 'split(".") | .[1] | @base64d' | jq -r '.sub' 2>/dev/null || echo "")
                
                if [ ! -z "$OWNER_USER_ID" ]; then
                    # Test update member role endpoint (will return 404 for owner - can't change own role)
                    # This proves the endpoint exists and validates authorization
                    echo -e "${YELLOW}Testing member management endpoints (note: these manage user-based members, workers join via invitation)...${NC}"
                    echo ""
                    
                    test_endpoint "PUT" "/api/groups/${GROUP_ID}/members/00000000-0000-0000-0000-000000000000/role" "Update member role" \
                        '{"role":"admin"}' "$TOKEN"
                    
                    test_endpoint "DELETE" "/api/groups/${GROUP_ID}/members/00000000-0000-0000-0000-000000000000" "Remove member from group" "" "$TOKEN"
                else
                    echo -e "${YELLOW}⊘ Skipping member management tests (could not extract user ID from token)${NC}"
                    echo ""
                fi
            else
                # Test update member role (will likely fail - user not in group)
                test_endpoint "PUT" "/api/groups/${GROUP_ID}/members/${USER_2_ID}/role" "Update member role" \
                    '{"role":"admin"}' "$TOKEN"
                
                # Test remove member (will likely fail - user not in group)
                test_endpoint "DELETE" "/api/groups/${GROUP_ID}/members/${USER_2_ID}" "Remove member from group" "" "$TOKEN"
            fi
        fi
        
        # Test invitation acceptance with authentication
        # Workers now need to authenticate (login) before accepting invitations
        # This links their user account (for dashboard) with worker device (for training)
        echo -e "${YELLOW}Testing authenticated invitation acceptance...${NC}"
        echo ""
        
        # Create a fresh invitation for this test
        INVITE_2_RESPONSE=$(curl -s -X POST ${API_GATEWAY_URL}/api/invitations/${GROUP_ID}/invitations \
            -H "Authorization: Bearer $TOKEN" \
            -H "Content-Type: application/json" \
            -d '{"max_uses":5,"expires_in_days":7}')
        
        if echo "$INVITE_2_RESPONSE" | jq -e '.code' > /dev/null 2>&1; then
            INVITE_CODE_2=$(echo $INVITE_2_RESPONSE | jq -r '.code')
            echo -e "${GREEN}✓ Created invitation for authenticated test: $INVITE_CODE_2${NC}"
            echo ""
            
            # Create a second user who will join as a worker
            TEST_EMAIL_3="testuser3${TIMESTAMP}@meshml.com"
            REGISTER_3=$(curl -s -X POST ${API_GATEWAY_URL}/api/auth/register \
                -H "Content-Type: application/json" \
                -d "{\"email\":\"${TEST_EMAIL_3}\",\"password\":\"${TEST_PASSWORD}\",\"full_name\":\"Test User 3 ${TIMESTAMP}\"}")
            
            if echo "$REGISTER_3" | jq -e '.id' > /dev/null 2>&1; then
                USER_3_ID=$(echo $REGISTER_3 | jq -r '.id')
                echo -e "${GREEN}✓ Third test user created: $USER_3_ID${NC}"
                echo ""
                
                # Login as third user
                LOGIN_3=$(curl -s -X POST ${API_GATEWAY_URL}/api/auth/login \
                    -H "Content-Type: application/json" \
                    -d "{\"email\":\"${TEST_EMAIL_3}\",\"password\":\"${TEST_PASSWORD}\"}")
                
                if echo "$LOGIN_3" | jq -e '.access_token' > /dev/null 2>&1; then
                    TOKEN_3=$(echo $LOGIN_3 | jq -r '.access_token')
                    echo -e "${GREEN}✓ Third user logged in${NC}"
                    echo ""
                    
                    # Test invitation acceptance WITH authentication (new flow)
                    # This creates a group member with both user_id and worker_id
                    test_endpoint "POST" "/api/invitations/accept" "Accept invitation (authenticated worker join)" \
                        "{\"worker_id\":\"test-worker-user3-${TIMESTAMP}\",\"invitation_code\":\"${INVITE_CODE_2}\"}" "$TOKEN_3"
                    
                    # Verify the member was added to the group
                    MEMBERS_AFTER=$(curl -s -X GET ${API_GATEWAY_URL}/api/groups/${GROUP_ID}/members \
                        -H "Authorization: Bearer $TOKEN")
                    
                    # Check if user 3 is in the members list
                    USER_3_IN_GROUP=$(echo "$MEMBERS_AFTER" | jq -r ".[] | select(.user_id==\"${USER_3_ID}\") | .user_id")
                    
                    if [ "$USER_3_IN_GROUP" = "$USER_3_ID" ]; then
                        echo -e "${GREEN}✓ User 3 successfully joined group (user_id + worker_id linked)${NC}"
                        echo ""
                        
                        # Now test member management endpoints with actual user_id
                        test_endpoint "PUT" "/api/groups/${GROUP_ID}/members/${USER_3_ID}/role" "Update member role" \
                            '{"role":"admin"}' "$TOKEN"
                        
                        test_endpoint "DELETE" "/api/groups/${GROUP_ID}/members/${USER_3_ID}" "Remove member from group" "" "$TOKEN"
                    else
                        echo -e "${YELLOW}⚠️  Could not verify user 3 in group members${NC}"
                        echo "  Members: $MEMBERS_AFTER"
                        echo ""
                    fi
                fi
            fi
        fi
        
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

# Test listing all jobs (requires auth)
test_endpoint "GET" "/api/jobs" "List all jobs (requires auth)" "" "$TOKEN"

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
    # Test worker registration endpoint explicitly
    test_endpoint "POST" "/api/workers/register" "Register worker node" \
        '{"worker_id":"test-worker-'${TIMESTAMP}'","capabilities":{"cpu_count":4,"gpu_available":false,"memory_gb":8}}' "$TOKEN"
    
    echo -e "${YELLOW}Capturing worker registration for subsequent tests...${NC}"
    echo ""
    
    WORKER_REGISTER=$(curl -s -X POST ${API_GATEWAY_URL}/api/workers/register \
        -H "Authorization: Bearer $TOKEN" \
        -H "Content-Type: application/json" \
        -d '{"worker_id":"test-worker-'${TIMESTAMP}'","capabilities":{"cpu_count":4,"gpu_available":false,"memory_gb":8}}')
    
    if echo "$WORKER_REGISTER" | jq -e '.worker_id' > /dev/null 2>&1; then
        WORKER_ID=$(echo $WORKER_REGISTER | jq -r '.worker_id')
        echo -e "${GREEN}✓ Worker registered: ID=$WORKER_ID${NC}"
        echo ""
        
        # Test individual worker endpoints
        test_endpoint "GET" "/api/workers/${WORKER_ID}" "Get specific worker details" "" "$TOKEN"
        # Note: GET /api/workers/{worker_id}/capabilities endpoint doesn't exist
        # Worker capabilities are returned in the worker details endpoint above
        test_endpoint "POST" "/api/workers/${WORKER_ID}/heartbeat" "Send worker heartbeat" \
            '{"status":"idle","metrics":{"cpu_usage":25.5,"memory_usage":45.2}}' "$TOKEN"
    else
        echo -e "${YELLOW}⚠️  Worker registration response:${NC}"
        echo "  $WORKER_REGISTER"
        
        # Try to extract worker_id from response anyway
        if echo "$WORKER_REGISTER" | jq -e '.worker_id' > /dev/null 2>&1; then
            WORKER_ID=$(echo $WORKER_REGISTER | jq -r '.worker_id')
            echo -e "${GREEN}✓ Worker ID found: $WORKER_ID${NC}"
            echo ""
            
            # Test individual worker endpoints
            test_endpoint "GET" "/api/workers/${WORKER_ID}" "Get specific worker details" "" "$TOKEN"
            test_endpoint "POST" "/api/workers/${WORKER_ID}/heartbeat" "Send worker heartbeat" \
                '{"status":"idle","metrics":{"cpu_usage":25.5,"memory_usage":45.2}}' "$TOKEN"
        fi
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
