#!/bin/bash
# =============================================================================
# Legal Events Production - Staging Test Suite
# =============================================================================
#
# PURPOSE: Comprehensive testing of staging environment before production
#
# USAGE:
#   1. Deploy staging environment first
#   2. Update configuration in "Configuration" section below
#   3. Run: ./scripts/test_staging.sh
#
# REQUIREMENTS:
#   - curl (for API requests)
#   - jq (for JSON parsing)
#   - docker and docker compose (for service checks)
#
# EXIT CODES:
#   0 = All tests passed
#   1 = One or more tests failed
#
# =============================================================================

set -e  # Exit on error (disabled for test framework)
set -u  # Exit on undefined variable

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Test counters
TESTS_RUN=0
TESTS_PASSED=0
TESTS_FAILED=0

# =============================================================================
# Configuration (MODIFY THESE FOR YOUR ENVIRONMENT)
# =============================================================================

# API endpoint (change to your staging URL)
API_URL="${API_URL:-http://localhost:8010}"

# Test credentials
TEST_EMAIL="${TEST_EMAIL:-admin@legalevents.local}"
TEST_PASSWORD="${TEST_PASSWORD:-admin}"

# Docker compose file for staging
COMPOSE_FILE="${COMPOSE_FILE:-docker-compose.staging.yml}"

# Test document (should exist in repo)
TEST_DOCUMENT="${TEST_DOCUMENT:-docs/DEPLOYMENT_READINESS.md}"

# LLM Provider to test (should be configured in staging)
TEST_PROVIDER="${TEST_PROVIDER:-langextract}"
TEST_MODEL="${TEST_MODEL:-gemini-1.5-flash}"

# =============================================================================
# Helper Functions
# =============================================================================

log_info() {
    echo -e "${BLUE}[INFO]${NC} $1"
}

log_success() {
    echo -e "${GREEN}[✓]${NC} $1"
}

log_warning() {
    echo -e "${YELLOW}[⚠]${NC} $1"
}

log_error() {
    echo -e "${RED}[✗]${NC} $1"
}

# Test framework functions
start_test() {
    local test_name="$1"
    TESTS_RUN=$((TESTS_RUN + 1))
    echo ""
    log_info "Test #${TESTS_RUN}: ${test_name}"
}

pass_test() {
    local message="$1"
    TESTS_PASSED=$((TESTS_PASSED + 1))
    log_success "${message}"
}

fail_test() {
    local message="$1"
    TESTS_FAILED=$((TESTS_FAILED + 1))
    log_error "${message}"
}

# HTTP request helper
api_request() {
    local method="$1"
    local endpoint="$2"
    local data="${3:-}"
    local token="${4:-}"

    local headers=(-H "Content-Type: application/json")
    if [[ -n "$token" ]]; then
        headers+=(-H "Authorization: Bearer $token")
    fi

    if [[ -n "$data" ]]; then
        curl -s -X "$method" "${API_URL}${endpoint}" "${headers[@]}" -d "$data"
    else
        curl -s -X "$method" "${API_URL}${endpoint}" "${headers[@]}"
    fi
}

# =============================================================================
# Test Suite
# =============================================================================

print_banner() {
    echo "============================================================================="
    echo "  Legal Events Production - Staging Test Suite"
    echo "============================================================================="
    echo ""
    echo "Configuration:"
    echo "  API URL:       ${API_URL}"
    echo "  Test Email:    ${TEST_EMAIL}"
    echo "  Test Provider: ${TEST_PROVIDER}"
    echo "  Test Model:    ${TEST_MODEL}"
    echo ""
    echo "============================================================================="
}

# Test 1: Check prerequisites
test_prerequisites() {
    start_test "Prerequisites check"

    # Check curl
    if command -v curl &> /dev/null; then
        pass_test "curl is installed"
    else
        fail_test "curl is not installed"
        return 1
    fi

    # Check jq
    if command -v jq &> /dev/null; then
        pass_test "jq is installed"
    else
        fail_test "jq is not installed (optional but recommended)"
    fi

    # Check docker
    if command -v docker &> /dev/null; then
        pass_test "docker is installed"
    else
        log_warning "docker is not installed (needed for service checks)"
    fi

    # Check test document exists
    if [[ -f "$TEST_DOCUMENT" ]]; then
        pass_test "Test document exists: $TEST_DOCUMENT"
    else
        fail_test "Test document not found: $TEST_DOCUMENT"
        return 1
    fi
}

# Test 2: Docker services health
test_docker_services() {
    start_test "Docker services health"

    if ! command -v docker &> /dev/null; then
        log_warning "Skipping (docker not installed)"
        return 0
    fi

    # Check if services are running
    local services=("api" "worker" "postgres" "redis" "minio")
    for service in "${services[@]}"; do
        local container_status=$(docker compose -f "$COMPOSE_FILE" ps "$service" --format json 2>/dev/null | jq -r '.State' 2>/dev/null || echo "unknown")

        if [[ "$container_status" == "running" ]]; then
            pass_test "Service ${service} is running"
        else
            fail_test "Service ${service} is not running (status: ${container_status})"
        fi
    done
}

# Test 3: API health endpoint
test_api_health() {
    start_test "API health endpoint"

    local response=$(curl -s -w "\n%{http_code}" "${API_URL}/health" || echo "000")
    local body=$(echo "$response" | head -n -1)
    local status=$(echo "$response" | tail -n 1)

    if [[ "$status" == "200" ]]; then
        pass_test "API health check returned 200 OK"

        # Parse JSON response
        local status_field=$(echo "$body" | jq -r '.status' 2>/dev/null || echo "")
        if [[ "$status_field" == "healthy" ]]; then
            pass_test "API reports healthy status"
        else
            fail_test "API health status is not 'healthy': $status_field"
        fi
    else
        fail_test "API health check failed (HTTP $status)"
        log_error "Response: $body"
    fi
}

# Test 4: User authentication (login)
test_authentication() {
    start_test "User authentication (JWT)"

    local login_data=$(cat <<EOF
{
  "username": "$TEST_EMAIL",
  "password": "$TEST_PASSWORD"
}
EOF
)

    local response=$(api_request POST "/v1/auth/login" "$login_data")

    # Extract token
    JWT_TOKEN=$(echo "$response" | jq -r '.access_token' 2>/dev/null || echo "")

    if [[ -n "$JWT_TOKEN" && "$JWT_TOKEN" != "null" ]]; then
        pass_test "Login successful, received JWT token"
        log_info "Token preview: ${JWT_TOKEN:0:50}..."
    else
        fail_test "Login failed, no JWT token received"
        log_error "Response: $response"
        JWT_TOKEN=""
        return 1
    fi
}

# Test 5: Create client
test_create_client() {
    start_test "Create client"

    if [[ -z "$JWT_TOKEN" ]]; then
        fail_test "Skipping (no JWT token from previous test)"
        return 1
    fi

    local client_data=$(cat <<EOF
{
  "name": "Test Client $(date +%s)",
  "email": "test-client-$(date +%s)@example.com",
  "status": "active"
}
EOF
)

    local response=$(api_request POST "/v1/clients" "$client_data" "$JWT_TOKEN")

    CLIENT_ID=$(echo "$response" | jq -r '.id' 2>/dev/null || echo "")

    if [[ -n "$CLIENT_ID" && "$CLIENT_ID" != "null" ]]; then
        pass_test "Client created successfully (ID: $CLIENT_ID)"
    else
        fail_test "Failed to create client"
        log_error "Response: $response"
        return 1
    fi
}

# Test 6: Create case
test_create_case() {
    start_test "Create case"

    if [[ -z "$JWT_TOKEN" || -z "$CLIENT_ID" ]]; then
        fail_test "Skipping (missing JWT token or client ID)"
        return 1
    fi

    local case_data=$(cat <<EOF
{
  "client_id": $CLIENT_ID,
  "title": "Test Case $(date +%s)",
  "description": "Automated test case",
  "status": "open"
}
EOF
)

    local response=$(api_request POST "/v1/cases" "$case_data" "$JWT_TOKEN")

    CASE_ID=$(echo "$response" | jq -r '.id' 2>/dev/null || echo "")

    if [[ -n "$CASE_ID" && "$CASE_ID" != "null" ]]; then
        pass_test "Case created successfully (ID: $CASE_ID)"
    else
        fail_test "Failed to create case"
        log_error "Response: $response"
        return 1
    fi
}

# Test 7: Get presigned upload URL
test_presigned_upload_url() {
    start_test "Generate presigned upload URL"

    if [[ -z "$JWT_TOKEN" || -z "$CLIENT_ID" || -z "$CASE_ID" ]]; then
        fail_test "Skipping (missing prerequisites)"
        return 1
    fi

    local response=$(api_request GET "/v1/documents/upload-url?client_id=${CLIENT_ID}&case_id=${CASE_ID}&run_id=1&filename=test.pdf" "" "$JWT_TOKEN")

    UPLOAD_URL=$(echo "$response" | jq -r '.upload_url' 2>/dev/null || echo "")

    if [[ -n "$UPLOAD_URL" && "$UPLOAD_URL" != "null" ]]; then
        pass_test "Presigned upload URL generated"
        log_info "URL preview: ${UPLOAD_URL:0:80}..."
    else
        fail_test "Failed to generate presigned upload URL"
        log_error "Response: $response"
        return 1
    fi
}

# Test 8: Provider discovery API
test_provider_discovery() {
    start_test "Provider discovery API"

    if [[ -z "$JWT_TOKEN" ]]; then
        fail_test "Skipping (no JWT token)"
        return 1
    fi

    local response=$(api_request GET "/v1/providers?enabled=true" "" "$JWT_TOKEN")

    local provider_count=$(echo "$response" | jq -r '.providers | length' 2>/dev/null || echo "0")

    if [[ "$provider_count" -gt 0 ]]; then
        pass_test "Provider discovery returned $provider_count providers"

        # Check if test provider is available
        local test_provider_found=$(echo "$response" | jq -r ".providers[] | select(.provider_id == \"$TEST_PROVIDER\") | .provider_id" 2>/dev/null || echo "")

        if [[ "$test_provider_found" == "$TEST_PROVIDER" ]]; then
            pass_test "Test provider '$TEST_PROVIDER' is available"
        else
            fail_test "Test provider '$TEST_PROVIDER' not found in available providers"
        fi
    else
        fail_test "No providers available"
        log_error "Response: $response"
        return 1
    fi
}

# Test 9: Create run
test_create_run() {
    start_test "Create processing run"

    if [[ -z "$JWT_TOKEN" || -z "$CASE_ID" ]]; then
        fail_test "Skipping (missing prerequisites)"
        return 1
    fi

    local run_data=$(cat <<EOF
{
  "case_id": $CASE_ID,
  "provider": "$TEST_PROVIDER",
  "model": "$TEST_MODEL"
}
EOF
)

    local response=$(api_request POST "/v1/runs" "$run_data" "$JWT_TOKEN")

    RUN_ID=$(echo "$response" | jq -r '.id' 2>/dev/null || echo "")

    if [[ -n "$RUN_ID" && "$RUN_ID" != "null" ]]; then
        pass_test "Run created successfully (ID: $RUN_ID)"
    else
        fail_test "Failed to create run"
        log_error "Response: $response"
        return 1
    fi
}

# Test 10: Database connectivity (via API)
test_database_connectivity() {
    start_test "Database connectivity"

    if [[ -z "$JWT_TOKEN" ]]; then
        fail_test "Skipping (no JWT token)"
        return 1
    fi

    # Try to list clients (requires DB access)
    local response=$(api_request GET "/v1/clients" "" "$JWT_TOKEN")

    # Check if response is a valid array
    local is_array=$(echo "$response" | jq -r 'type' 2>/dev/null || echo "")

    if [[ "$is_array" == "array" ]]; then
        pass_test "Database connectivity working (API can query database)"
    else
        fail_test "Database connectivity issue"
        log_error "Response: $response"
        return 1
    fi
}

# Test 11: Redis connectivity (queue check)
test_redis_connectivity() {
    start_test "Redis connectivity"

    if ! command -v docker &> /dev/null; then
        log_warning "Skipping (docker not available)"
        return 0
    fi

    # Try to ping Redis
    local redis_ping=$(docker compose -f "$COMPOSE_FILE" exec -T redis redis-cli ping 2>/dev/null || echo "FAILED")

    if [[ "$redis_ping" == "PONG" ]]; then
        pass_test "Redis connectivity working"
    else
        fail_test "Redis connectivity failed"
        return 1
    fi
}

# Test 12: MinIO connectivity
test_minio_connectivity() {
    start_test "MinIO connectivity"

    # Extract MinIO endpoint from environment or use default
    local minio_url="${MINIO_URL:-http://localhost:9010}"

    local response=$(curl -s -o /dev/null -w "%{http_code}" "${minio_url}/minio/health/live" || echo "000")

    if [[ "$response" == "200" ]]; then
        pass_test "MinIO connectivity working"
    else
        fail_test "MinIO connectivity failed (HTTP $response)"
        return 1
    fi
}

# Test 13: Worker registration
test_worker_registration() {
    start_test "Worker registration in Redis"

    if ! command -v docker &> /dev/null; then
        log_warning "Skipping (docker not available)"
        return 0
    fi

    # Check for registered workers
    local worker_count=$(docker compose -f "$COMPOSE_FILE" exec -T redis redis-cli SCARD rq:workers 2>/dev/null || echo "0")

    if [[ "$worker_count" -gt 0 ]]; then
        pass_test "Worker(s) registered in Redis (count: $worker_count)"
    else
        log_warning "No workers registered in Redis (worker might be starting)"
    fi
}

# Test 14: API response time
test_api_response_time() {
    start_test "API response time (performance)"

    local start_time=$(date +%s%N)
    local response=$(curl -s "${API_URL}/health" || echo "")
    local end_time=$(date +%s%N)

    local response_time_ms=$(( (end_time - start_time) / 1000000 ))

    log_info "Response time: ${response_time_ms}ms"

    if [[ "$response_time_ms" -lt 200 ]]; then
        pass_test "API response time excellent (<200ms)"
    elif [[ "$response_time_ms" -lt 500 ]]; then
        pass_test "API response time good (<500ms)"
    elif [[ "$response_time_ms" -lt 1000 ]]; then
        log_warning "API response time acceptable but slow (${response_time_ms}ms)"
    else
        fail_test "API response time too slow (${response_time_ms}ms)"
    fi
}

# Test 15: Security headers
test_security_headers() {
    start_test "Security headers"

    local headers=$(curl -s -I "${API_URL}/health" || echo "")

    # Check for important security headers
    if echo "$headers" | grep -qi "x-frame-options"; then
        pass_test "X-Frame-Options header present"
    else
        log_warning "X-Frame-Options header missing"
    fi

    if echo "$headers" | grep -qi "x-content-type-options"; then
        pass_test "X-Content-Type-Options header present"
    else
        log_warning "X-Content-Type-Options header missing"
    fi

    # Note: HSTS only applies to HTTPS
    if [[ "$API_URL" == https://* ]]; then
        if echo "$headers" | grep -qi "strict-transport-security"; then
            pass_test "Strict-Transport-Security header present (HSTS)"
        else
            log_warning "Strict-Transport-Security header missing (HSTS)"
        fi
    fi
}

# =============================================================================
# Main Test Runner
# =============================================================================

run_all_tests() {
    print_banner

    log_info "Starting test suite execution..."
    echo ""

    # Run all tests
    test_prerequisites || true
    test_docker_services || true
    test_api_health || true
    test_authentication || true
    test_create_client || true
    test_create_case || true
    test_presigned_upload_url || true
    test_provider_discovery || true
    test_create_run || true
    test_database_connectivity || true
    test_redis_connectivity || true
    test_minio_connectivity || true
    test_worker_registration || true
    test_api_response_time || true
    test_security_headers || true

    # Print summary
    echo ""
    echo "============================================================================="
    echo "  Test Summary"
    echo "============================================================================="
    echo ""
    echo "  Tests Run:    $TESTS_RUN"
    echo "  Tests Passed: ${GREEN}$TESTS_PASSED${NC}"
    echo "  Tests Failed: ${RED}$TESTS_FAILED${NC}"
    echo ""

    if [[ "$TESTS_FAILED" -eq 0 ]]; then
        echo -e "${GREEN}✓ All tests passed!${NC}"
        echo ""
        echo "🚀 Staging environment is ready for production deployment."
        echo ""
        return 0
    else
        echo -e "${RED}✗ Some tests failed.${NC}"
        echo ""
        echo "⚠️  Fix failing tests before deploying to production."
        echo ""
        return 1
    fi
}

# Run tests
run_all_tests
exit $?
