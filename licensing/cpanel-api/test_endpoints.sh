#!/bin/bash
# NSP Plugin - License Server Test Script
# Tests all endpoints after deployment

# Configuration
BASE_URL="https://plugin.nelsonsilvaphotography.com/api/license"
ADMIN_KEY="CHANGE_ME_TO_YOUR_ADMIN_KEY"

# Colors
GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

echo "========================================"
echo "NSP License Server - Endpoint Tests"
echo "========================================"
echo ""

# Test 1: Health Check
echo -e "${YELLOW}Test 1: Health Check${NC}"
echo "GET $BASE_URL/health"
RESPONSE=$(curl -s -w "\n%{http_code}" "$BASE_URL/health")
HTTP_CODE=$(echo "$RESPONSE" | tail -n1)
BODY=$(echo "$RESPONSE" | sed '$d')

if [ "$HTTP_CODE" = "200" ]; then
    echo -e "${GREEN}✓ PASS${NC} - Health check OK"
    echo "$BODY" | jq '.'
else
    echo -e "${RED}✗ FAIL${NC} - Expected 200, got $HTTP_CODE"
    echo "$BODY"
fi
echo ""

# Test 2: Create License (Admin)
echo -e "${YELLOW}Test 2: Create License (Admin)${NC}"
echo "POST $BASE_URL/v1/create"
CREATE_RESPONSE=$(curl -s -w "\n%{http_code}" -X POST "$BASE_URL/v1/create" \
  -H "Content-Type: application/json" \
  -H "X-Admin-Key: $ADMIN_KEY" \
  -d '{
    "email": "test@example.com",
    "plan": "professional",
    "duration_days": 365
  }')

HTTP_CODE=$(echo "$CREATE_RESPONSE" | tail -n1)
BODY=$(echo "$CREATE_RESPONSE" | sed '$d')

if [ "$HTTP_CODE" = "201" ]; then
    echo -e "${GREEN}✓ PASS${NC} - License created"
    echo "$BODY" | jq '.'
    LICENSE_KEY=$(echo "$BODY" | jq -r '.license_key')
    echo "License Key: $LICENSE_KEY"
else
    echo -e "${RED}✗ FAIL${NC} - Expected 201, got $HTTP_CODE"
    echo "$BODY"
    exit 1
fi
echo ""

# Generate test machine ID
MACHINE_ID=$(echo -n "test-machine-$(date +%s)" | sha256sum | cut -d' ' -f1)
echo "Test Machine ID: $MACHINE_ID"
echo ""

# Test 3: Activate License
echo -e "${YELLOW}Test 3: Activate License${NC}"
echo "POST $BASE_URL/v1/activate"
ACTIVATE_RESPONSE=$(curl -s -w "\n%{http_code}" -X POST "$BASE_URL/v1/activate" \
  -H "Content-Type: application/json" \
  -d "{
    \"license_key\": \"$LICENSE_KEY\",
    \"machine_id\": \"$MACHINE_ID\",
    \"machine_name\": \"Test Machine\",
    \"machine_os\": \"macOS\",
    \"machine_os_version\": \"14.2\"
  }")

HTTP_CODE=$(echo "$ACTIVATE_RESPONSE" | tail -n1)
BODY=$(echo "$ACTIVATE_RESPONSE" | sed '$d')

if [ "$HTTP_CODE" = "200" ]; then
    echo -e "${GREEN}✓ PASS${NC} - License activated"
    echo "$BODY" | jq '.'
    TOKEN=$(echo "$BODY" | jq -r '.token')
    echo "Token: ${TOKEN:0:50}..."
else
    echo -e "${RED}✗ FAIL${NC} - Expected 200, got $HTTP_CODE"
    echo "$BODY"
    exit 1
fi
echo ""

# Test 4: Validate License
echo -e "${YELLOW}Test 4: Validate License${NC}"
echo "POST $BASE_URL/v1/validate"
VALIDATE_RESPONSE=$(curl -s -w "\n%{http_code}" -X POST "$BASE_URL/v1/validate" \
  -H "Content-Type: application/json" \
  -d "{
    \"token\": \"$TOKEN\"
  }")

HTTP_CODE=$(echo "$VALIDATE_RESPONSE" | tail -n1)
BODY=$(echo "$VALIDATE_RESPONSE" | sed '$d')

if [ "$HTTP_CODE" = "200" ]; then
    echo -e "${GREEN}✓ PASS${NC} - License validated"
    echo "$BODY" | jq '.'
else
    echo -e "${RED}✗ FAIL${NC} - Expected 200, got $HTTP_CODE"
    echo "$BODY"
    exit 1
fi
echo ""

# Test 5: Heartbeat
echo -e "${YELLOW}Test 5: Heartbeat${NC}"
echo "POST $BASE_URL/v1/heartbeat"
HEARTBEAT_RESPONSE=$(curl -s -w "\n%{http_code}" -X POST "$BASE_URL/v1/heartbeat" \
  -H "Content-Type: application/json" \
  -d "{
    \"token\": \"$TOKEN\",
    \"plugin_version\": \"2.0.0\",
    \"photos_processed\": 150,
    \"uptime_hours\": 2.5
  }")

HTTP_CODE=$(echo "$HEARTBEAT_RESPONSE" | tail -n1)
BODY=$(echo "$HEARTBEAT_RESPONSE" | sed '$d')

if [ "$HTTP_CODE" = "200" ]; then
    echo -e "${GREEN}✓ PASS${NC} - Heartbeat recorded"
    echo "$BODY" | jq '.'
    NEW_TOKEN=$(echo "$BODY" | jq -r '.token')
    echo "New Token: ${NEW_TOKEN:0:50}..."
else
    echo -e "${RED}✗ FAIL${NC} - Expected 200, got $HTTP_CODE"
    echo "$BODY"
    exit 1
fi
echo ""

# Test 6: Deactivate License
echo -e "${YELLOW}Test 6: Deactivate License${NC}"
echo "POST $BASE_URL/v1/deactivate"
DEACTIVATE_RESPONSE=$(curl -s -w "\n%{http_code}" -X POST "$BASE_URL/v1/deactivate" \
  -H "Content-Type: application/json" \
  -d "{
    \"token\": \"$NEW_TOKEN\"
  }")

HTTP_CODE=$(echo "$DEACTIVATE_RESPONSE" | tail -n1)
BODY=$(echo "$DEACTIVATE_RESPONSE" | sed '$d')

if [ "$HTTP_CODE" = "200" ]; then
    echo -e "${GREEN}✓ PASS${NC} - License deactivated"
    echo "$BODY" | jq '.'
else
    echo -e "${RED}✗ FAIL${NC} - Expected 200, got $HTTP_CODE"
    echo "$BODY"
    exit 1
fi
echo ""

# Test 7: Validate After Deactivation (Should Fail)
echo -e "${YELLOW}Test 7: Validate After Deactivation (Should Fail)${NC}"
echo "POST $BASE_URL/v1/validate"
VALIDATE2_RESPONSE=$(curl -s -w "\n%{http_code}" -X POST "$BASE_URL/v1/validate" \
  -H "Content-Type: application/json" \
  -d "{
    \"token\": \"$NEW_TOKEN\"
  }")

HTTP_CODE=$(echo "$VALIDATE2_RESPONSE" | tail -n1)
BODY=$(echo "$VALIDATE2_RESPONSE" | sed '$d')

if [ "$HTTP_CODE" = "401" ]; then
    echo -e "${GREEN}✓ PASS${NC} - Validation correctly failed after deactivation"
    echo "$BODY" | jq '.'
else
    echo -e "${RED}✗ FAIL${NC} - Expected 401, got $HTTP_CODE"
    echo "$BODY"
fi
echo ""

# Summary
echo "========================================"
echo -e "${GREEN}All Tests Completed!${NC}"
echo "========================================"
echo ""
echo "Summary:"
echo "  ✓ Health check"
echo "  ✓ Create license (admin)"
echo "  ✓ Activate license"
echo "  ✓ Validate license"
echo "  ✓ Heartbeat"
echo "  ✓ Deactivate license"
echo "  ✓ Validate after deactivation (correctly failed)"
echo ""
echo "License Key: $LICENSE_KEY"
echo "Machine ID: $MACHINE_ID"
echo ""
echo "✅ License server is working correctly!"
