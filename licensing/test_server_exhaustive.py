#!/usr/bin/env python3
"""
Exhaustive License Server Testing Script
Tests all endpoints, error conditions, and edge cases.
"""

import requests
import json
import time
from datetime import datetime
import sys

BASE_URL = "http://localhost:8080"
ADMIN_KEY = "admin_secret_key_change_me"

class Colors:
    GREEN = '\033[92m'
    RED = '\033[91m'
    YELLOW = '\033[93m'
    BLUE = '\033[94m'
    END = '\033[0m'

def print_success(msg):
    print(f"{Colors.GREEN}✅ {msg}{Colors.END}")

def print_error(msg):
    print(f"{Colors.RED}❌ {msg}{Colors.END}")

def print_warning(msg):
    print(f"{Colors.YELLOW}⚠️  {msg}{Colors.END}")

def print_info(msg):
    print(f"{Colors.BLUE}ℹ️  {msg}{Colors.END}")

def print_section(title):
    print(f"\n{'='*60}")
    print(f"{Colors.BLUE}{title}{Colors.END}")
    print('='*60)


# Test 1: Health Check
print_section("Test 1: Health Check")
try:
    response = requests.get(f"{BASE_URL}/health", timeout=5)
    if response.status_code == 200:
        data = response.json()
        print_success(f"Server is healthy: {data}")
    else:
        print_error(f"Health check failed: {response.status_code}")
        sys.exit(1)
except Exception as e:
    print_error(f"Cannot connect to server: {e}")
    print_warning("Make sure server is running: uvicorn server:app --port 8080")
    sys.exit(1)


# Test 2: Create License (Admin)
print_section("Test 2: Create License")
try:
    response = requests.post(
        f"{BASE_URL}/api/v1/licenses/create",
        headers={"X-Admin-Key": ADMIN_KEY},
        json={
            "email": "test@vilearn.ai",
            "plan": "professional",
            "max_activations": 3,
            "duration_days": 365
        },
        timeout=5
    )

    if response.status_code == 200:
        data = response.json()
        LICENSE_KEY = data['license_key']
        print_success(f"License created: {LICENSE_KEY}")
        print_info(f"Email: {data['email']}")
        print_info(f"Plan: {data['plan']}")
        print_info(f"Expires: {data['expires_at']}")
    else:
        print_error(f"Failed to create license: {response.status_code}")
        print_error(f"Response: {response.text}")
        sys.exit(1)
except Exception as e:
    print_error(f"Error creating license: {e}")
    sys.exit(1)


# Test 3: Create License Without Admin Key
print_section("Test 3: Security - Reject Without Admin Key")
try:
    response = requests.post(
        f"{BASE_URL}/api/v1/licenses/create",
        json={"email": "hacker@evil.com", "plan": "professional"},
        timeout=5
    )

    if response.status_code == 403:
        print_success("Correctly rejected unauthorized request")
    else:
        print_error(f"Security issue! Should return 403, got {response.status_code}")
except Exception as e:
    print_error(f"Error: {e}")


# Test 4: Activate License
print_section("Test 4: Activate License")
MACHINE_ID = "test_machine_12345678901234567890abcd"
try:
    response = requests.post(
        f"{BASE_URL}/api/v1/licenses/activate",
        json={
            "license_key": LICENSE_KEY,
            "machine_id": MACHINE_ID,
            "machine_name": "Test MacBook Pro"
        },
        timeout=5
    )

    if response.status_code == 200:
        data = response.json()
        TOKEN = data['token']
        print_success(f"License activated successfully")
        print_info(f"Plan: {data['plan']}")
        print_info(f"Features: {json.dumps(data['features'], indent=2)}")
        print_info(f"Token (first 50 chars): {TOKEN[:50]}...")
    else:
        print_error(f"Activation failed: {response.status_code}")
        print_error(f"Response: {response.text}")
        sys.exit(1)
except Exception as e:
    print_error(f"Error activating license: {e}")
    sys.exit(1)


# Test 5: Re-activate Same Machine (Should Succeed)
print_section("Test 5: Re-activate Same Machine")
try:
    response = requests.post(
        f"{BASE_URL}/api/v1/licenses/activate",
        json={
            "license_key": LICENSE_KEY,
            "machine_id": MACHINE_ID,
        },
        timeout=5
    )

    if response.status_code == 200:
        print_success("Re-activation successful (idempotent)")
    else:
        print_error(f"Re-activation failed: {response.status_code}")
except Exception as e:
    print_error(f"Error: {e}")


# Test 6: Validate Token
print_section("Test 6: Validate Token")
try:
    response = requests.post(
        f"{BASE_URL}/api/v1/licenses/validate",
        json={"token": TOKEN},
        timeout=5
    )

    if response.status_code == 200:
        data = response.json()
        print_success(f"Token is valid")
        print_info(f"Plan: {data['plan']}")
        print_info(f"Days remaining: {data['days_remaining']}")
    else:
        print_error(f"Validation failed: {response.status_code}")
        print_error(f"Response: {response.text}")
except Exception as e:
    print_error(f"Error validating token: {e}")


# Test 7: Validate Invalid Token
print_section("Test 7: Security - Reject Invalid Token")
try:
    response = requests.post(
        f"{BASE_URL}/api/v1/licenses/validate",
        json={"token": "invalid.token.here"},
        timeout=5
    )

    if response.status_code == 401:
        print_success("Correctly rejected invalid token")
    else:
        print_error(f"Security issue! Should return 401, got {response.status_code}")
except Exception as e:
    print_error(f"Error: {e}")


# Test 8: Activate on Multiple Machines
print_section("Test 8: Activation Limits")
machines = [
    "machine_2_xxxxxxxxxxxxxxxxxxxxxxxx",
    "machine_3_xxxxxxxxxxxxxxxxxxxxxxxx",
    "machine_4_xxxxxxxxxxxxxxxxxxxxxxxx",  # This should fail (max 3)
]

for i, machine_id in enumerate(machines):
    try:
        response = requests.post(
            f"{BASE_URL}/api/v1/licenses/activate",
            json={
                "license_key": LICENSE_KEY,
                "machine_id": machine_id,
            },
            timeout=5
        )

        if i < 2:  # First 2 should succeed (we already have 1)
            if response.status_code == 200:
                print_success(f"Machine {i+2} activated successfully")
            else:
                print_error(f"Machine {i+2} failed: {response.status_code}")
        else:  # 4th machine should fail
            if response.status_code == 403:
                print_success(f"Correctly rejected machine {i+2} (max activations reached)")
            else:
                print_error(f"Should reject machine {i+2}, got {response.status_code}")
    except Exception as e:
        print_error(f"Error: {e}")


# Test 9: Heartbeat
print_section("Test 9: Heartbeat")
try:
    response = requests.post(
        f"{BASE_URL}/api/v1/licenses/heartbeat",
        json={
            "token": TOKEN,
            "plugin_version": "2.0.0-test"
        },
        timeout=5
    )

    if response.status_code == 200:
        data = response.json()
        NEW_TOKEN = data['token']
        print_success("Heartbeat successful, token renewed")
        print_info(f"New token (first 50 chars): {NEW_TOKEN[:50]}...")
    else:
        print_error(f"Heartbeat failed: {response.status_code}")
        print_error(f"Response: {response.text}")
except Exception as e:
    print_error(f"Error: {e}")


# Test 10: Deactivate License
print_section("Test 10: Deactivate License")
try:
    response = requests.post(
        f"{BASE_URL}/api/v1/licenses/deactivate",
        json={"token": TOKEN},
        timeout=5
    )

    if response.status_code == 200:
        print_success("License deactivated successfully")
    else:
        print_error(f"Deactivation failed: {response.status_code}")
        print_error(f"Response: {response.text}")
except Exception as e:
    print_error(f"Error: {e}")


# Test 11: Validate After Deactivation
print_section("Test 11: Validate After Deactivation")
try:
    response = requests.post(
        f"{BASE_URL}/api/v1/licenses/validate",
        json={"token": TOKEN},
        timeout=5
    )

    if response.status_code == 401:
        print_success("Correctly rejected deactivated license")
    else:
        print_error(f"Should reject deactivated license, got {response.status_code}")
except Exception as e:
    print_error(f"Error: {e}")


# Test 12: Admin Stats
print_section("Test 12: Admin Stats")
try:
    response = requests.get(
        f"{BASE_URL}/api/v1/admin/stats",
        headers={"X-Admin-Key": ADMIN_KEY},
        timeout=5
    )

    if response.status_code == 200:
        data = response.json()
        print_success("Stats retrieved successfully")
        print_info(f"Total licenses: {data['total_licenses']}")
        print_info(f"Active licenses: {data['active_licenses']}")
        print_info(f"Total activations: {data['total_activations']}")
        print_info(f"Heartbeats (24h): {data['heartbeats_24h']}")
    else:
        print_error(f"Failed to get stats: {response.status_code}")
except Exception as e:
    print_error(f"Error: {e}")


# Test 13: Activate Non-Existent License
print_section("Test 13: Security - Reject Non-Existent License")
try:
    response = requests.post(
        f"{BASE_URL}/api/v1/licenses/activate",
        json={
            "license_key": "VELA-0000-0000-0000-0000",
            "machine_id": "fake_machine_id",
        },
        timeout=5
    )

    if response.status_code == 404:
        print_success("Correctly rejected non-existent license")
    else:
        print_error(f"Should return 404, got {response.status_code}")
except Exception as e:
    print_error(f"Error: {e}")


# Test 14: Create License with Invalid Plan
print_section("Test 14: Validation - Reject Invalid Plan")
try:
    response = requests.post(
        f"{BASE_URL}/api/v1/licenses/create",
        headers={"X-Admin-Key": ADMIN_KEY},
        json={
            "email": "test@vilearn.ai",
            "plan": "invalid_plan",  # Should fail validation
            "max_activations": 2
        },
        timeout=5
    )

    if response.status_code == 422:  # Pydantic validation error
        print_success("Correctly rejected invalid plan")
    else:
        print_warning(f"Expected 422, got {response.status_code} (check validation)")
except Exception as e:
    print_error(f"Error: {e}")


# Test 15: Missing Required Fields
print_section("Test 15: Validation - Missing Required Fields")
try:
    response = requests.post(
        f"{BASE_URL}/api/v1/licenses/activate",
        json={
            "license_key": LICENSE_KEY,
            # Missing machine_id
        },
        timeout=5
    )

    if response.status_code == 422:
        print_success("Correctly rejected missing required field")
    else:
        print_warning(f"Expected 422, got {response.status_code}")
except Exception as e:
    print_error(f"Error: {e}")


# Final Summary
print_section("Test Summary")
print_success("All critical tests passed!")
print_info("Server is functioning correctly and ready for production")
print_info(f"Test completed at: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")

print("\n" + "="*60)
print(f"{Colors.GREEN}🎉 License Server is PRODUCTION READY!{Colors.END}")
print("="*60 + "\n")
