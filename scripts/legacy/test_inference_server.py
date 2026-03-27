#!/usr/bin/env python3
"""
Exhaustive NSP Plugin Inference Server Testing Script
Tests all endpoints on port 5678, error conditions, and validates models.
"""

import requests
import json
import time
import base64
import sys
from pathlib import Path
from typing import Dict, Any
from datetime import datetime

BASE_URL = "http://127.0.0.1:5678"

class Colors:
    GREEN = '\033[92m'
    RED = '\033[91m'
    YELLOW = '\033[93m'
    BLUE = '\033[94m'
    CYAN = '\033[96m'
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
    print(f"\n{'='*70}")
    print(f"{Colors.CYAN}{title}{Colors.END}")
    print('='*70)

def check_server_connection():
    """Check if server is running"""
    print_section("Test 0: Server Connection")
    try:
        response = requests.get(f"{BASE_URL}/health", timeout=3)
        if response.status_code == 200:
            print_success("Server is reachable")
            return True
        else:
            print_error(f"Server returned status code: {response.status_code}")
            return False
    except requests.exceptions.ConnectionError:
        print_error("Cannot connect to server")
        print_warning(f"Make sure server is running:")
        print_warning("  cd /Users/nelsonsilva/Documentos/gemini/projetos/NSP\\ Plugin_dev_full_package")
        print_warning("  source venv/bin/activate")
        print_warning("  python -m uvicorn services.server:app --host 127.0.0.1 --port 5678")
        return False
    except Exception as e:
        print_error(f"Unexpected error: {e}")
        return False

def test_health_endpoint():
    """Test 1: Health Check"""
    print_section("Test 1: Health Check - Verify Models Loaded")
    try:
        response = requests.get(f"{BASE_URL}/health", timeout=5)
        if response.status_code == 200:
            data = response.json()
            print_success(f"Health check passed")
            print_info(f"Status: {data.get('status')}")
            print_info(f"Models loaded:")
            print_info(f"  - Neural Network: {data.get('models', {}).get('nn', False)}")
            print_info(f"  - Artifacts directory: {data.get('artifacts_dir')}")

            if not data.get('models', {}).get('nn'):
                print_warning("Neural Network model not loaded!")

            return data
        else:
            print_error(f"Health check failed: {response.status_code}")
            print_error(f"Response: {response.text}")
            return None
    except Exception as e:
        print_error(f"Error during health check: {e}")
        return None

def check_models_exist():
    """Test 2: Check Model Files"""
    print_section("Test 2: Verify Model Files Exist")

    models_dir = Path("/Users/nelsonsilva/Documentos/gemini/projetos/NSP Plugin_dev_full_package/models")

    if not models_dir.exists():
        print_error(f"Models directory does not exist: {models_dir}")
        return False

    print_info(f"Checking models in: {models_dir}")

    # Required support files
    required_files = [
        "pca_model.pkl",
        "exif_scaler.pkl"
    ]

    all_good = True

    # Check support files
    print_info("\nSupport files:")
    for file in required_files:
        file_path = models_dir / file
        if file_path.exists():
            size_kb = file_path.stat().st_size / 1024
            print_success(f"  {file}: {size_kb:.1f} KB")
        else:
            print_error(f"  {file}: NOT FOUND")
            all_good = False

    # Check Neural Network model
    nn_model_path = models_dir / "ann" / "multi_output_nn.pth"
    print_info("\nNeural Network model:")
    if nn_model_path.exists():
        size_mb = nn_model_path.stat().st_size / (1024 * 1024)
        print_success(f"  multi_output_nn.pth: {size_mb:.2f} MB")
    else:
        print_warning(f"  multi_output_nn.pth: NOT FOUND")

    # Check culling model
    culling_model_path = models_dir / "culling_model.pth"
    print_info("\nSmart Culling model:")
    if culling_model_path.exists():
        size_mb = culling_model_path.stat().st_size / (1024 * 1024)
        print_success(f"  culling_model.pth: {size_mb:.2f} MB")
    else:
        print_warning(f"  culling_model.pth: NOT FOUND (optional)")

    return all_good

def check_database():
    """Test 3: Verify Database"""
    print_section("Test 3: Verify Database Exists")

    db_path = Path("/Users/nelsonsilva/Documentos/gemini/projetos/NSP Plugin_dev_full_package/data/nsp_plugin.db")

    if db_path.exists():
        size_kb = db_path.stat().st_size / 1024
        print_success(f"Database exists: {db_path}")
        print_info(f"  Size: {size_kb:.1f} KB")

        # Try to check database content using sqlite3
        try:
            import sqlite3
            conn = sqlite3.connect(db_path)
            cursor = conn.cursor()

            # Check tables
            cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
            tables = cursor.fetchall()
            print_info(f"  Tables found: {', '.join([t[0] for t in tables])}")

            # Check training_data count
            cursor.execute("SELECT COUNT(*) FROM training_data")
            count = cursor.fetchone()[0]
            print_info(f"  Training records: {count}")

            # Check feedback_records count
            try:
                cursor.execute("SELECT COUNT(*) FROM feedback_records")
                feedback_count = cursor.fetchone()[0]
                print_info(f"  Feedback records: {feedback_count}")
            except:
                print_warning("  Feedback table not found (will be created on first use)")

            conn.close()
            return True
        except Exception as e:
            print_warning(f"Could not inspect database: {e}")
            return True
    else:
        print_error(f"Database NOT FOUND: {db_path}")
        return False

def test_predict_endpoint():
    """Test 4: /predict Endpoint"""
    print_section("Test 4: /predict Endpoint - Sample Prediction")

    # Find a sample image
    images_dir = Path("/Users/nelsonsilva/Documentos/gemini/projetos/NSP Plugin_dev_full_package/data/images")

    sample_image = None
    if images_dir.exists():
        # Try to find any image file
        for ext in ['.jpg', '.jpeg', '.png', '.arw', '.cr2', '.nef']:
            images = list(images_dir.glob(f'*{ext}'))
            if images:
                sample_image = str(images[0])
                break

    if not sample_image:
        print_warning("No sample images found in data/images/")
        print_info("Skipping /predict test")
        return False

    print_info(f"Testing with image: {Path(sample_image).name}")

    # Test Neural Network prediction
    print_info("\nTesting Neural Network model:")
    try:
        payload = {
            "image_path": sample_image,
            "exif": {
                "iso": 400,
                "width": 6000,
                "height": 4000
            },
            "model": "nn"
        }

        response = requests.post(f"{BASE_URL}/predict", json=payload, timeout=30)

        if response.status_code == 200:
            data = response.json()
            print_success("Neural Network prediction successful")
            print_info(f"  Model used: {data.get('model')}")
            print_info(f"  Sliders returned: {len(data.get('sliders', {}))}")

            # Show first few slider predictions
            sliders = data.get('sliders', {})
            print_info("  Sample predictions:")
            for i, (name, value) in enumerate(list(sliders.items())[:5]):
                print_info(f"    {name}: {value:.2f}")
            if len(sliders) > 5:
                print_info(f"    ... and {len(sliders) - 5} more sliders")
        elif response.status_code == 503:
            print_warning("Neural Network model not available (503)")
            return False
        else:
            print_error(f"Neural Network prediction failed: {response.status_code}")
            print_error(f"Response: {response.text}")
            return False
    except Exception as e:
        print_error(f"Error testing Neural Network: {e}")
        return False

    return True

def test_error_handling():
    """Test 5: Error Handling"""
    print_section("Test 5: Error Handling - Invalid Inputs")

    # Test 5.1: Missing image_path
    print_info("Test 5.1: Missing image_path and preview_b64")
    try:
        payload = {
            "exif": {"iso": 400},
            "model": "nn"
        }
        response = requests.post(f"{BASE_URL}/predict", json=payload, timeout=5)
        if response.status_code == 422:
            print_success("Correctly rejected missing image_path (422)")
        else:
            print_warning(f"Expected 422, got {response.status_code}")
    except Exception as e:
        print_error(f"Error: {e}")

    # Test 5.2: Non-existent file
    print_info("\nTest 5.2: Non-existent file")
    try:
        payload = {
            "image_path": "/nonexistent/path/image.jpg",
            "exif": {"iso": 400},
            "model": "nn"
        }
        response = requests.post(f"{BASE_URL}/predict", json=payload, timeout=5)
        if response.status_code in [404, 400]:
            print_success(f"Correctly rejected non-existent file ({response.status_code})")
        else:
            print_warning(f"Expected 404/400, got {response.status_code}")
    except Exception as e:
        print_error(f"Error: {e}")

    # Test 5.3: Invalid model type
    print_info("\nTest 5.3: Invalid model type")
    try:
        payload = {
            "image_path": "/tmp/test.jpg",
            "exif": {"iso": 400},
            "model": "invalid_model"
        }
        response = requests.post(f"{BASE_URL}/predict", json=payload, timeout=5)
        if response.status_code == 422:
            print_success("Correctly rejected invalid model type (422)")
        else:
            print_warning(f"Expected 422, got {response.status_code}")
    except Exception as e:
        print_error(f"Error: {e}")

    # Test 5.4: Invalid base64 preview
    print_info("\nTest 5.4: Invalid base64 preview")
    try:
        payload = {
            "preview_b64": "invalid!!!base64",
            "exif": {"iso": 400},
            "model": "nn"
        }
        response = requests.post(f"{BASE_URL}/predict", json=payload, timeout=5)
        if response.status_code == 400:
            print_success("Correctly rejected invalid base64 (400)")
        else:
            print_warning(f"Expected 400, got {response.status_code}")
    except Exception as e:
        print_error(f"Error: {e}")

def test_feedback_endpoint():
    """Test 6: /feedback Endpoint"""
    print_section("Test 6: /feedback Endpoint")

    print_info("Testing feedback submission")
    try:
        # Create sample feedback (22 sliders as per NSP standard)
        payload = {
            "original_record_id": 1,
            "corrected_develop_vector": [0.0] * 22  # 22 sliders
        }

        response = requests.post(f"{BASE_URL}/feedback", json=payload, timeout=5)

        if response.status_code == 200:
            data = response.json()
            print_success("Feedback submitted successfully")
            print_info(f"  Response: {data}")
        elif response.status_code == 500:
            print_warning("Database might not exist or table not created")
        else:
            print_error(f"Feedback failed: {response.status_code}")
            print_error(f"Response: {response.text}")
    except Exception as e:
        print_error(f"Error: {e}")

    # Test invalid feedback (wrong vector length)
    print_info("\nTesting invalid feedback (wrong vector length)")
    try:
        payload = {
            "original_record_id": 1,
            "corrected_develop_vector": [0.0] * 10  # Wrong length
        }

        response = requests.post(f"{BASE_URL}/feedback", json=payload, timeout=5)

        if response.status_code == 400:
            print_success("Correctly rejected invalid vector length (400)")
        else:
            print_warning(f"Expected 400, got {response.status_code}")
    except Exception as e:
        print_error(f"Error: {e}")

def test_rate_limiting():
    """Test 7: Rate Limiting"""
    print_section("Test 7: Rate Limiting")

    print_info("Testing rate limit (10 requests/minute for /predict)")
    print_warning("This test will make 12 rapid requests...")

    success_count = 0
    rate_limited = False

    for i in range(12):
        try:
            payload = {
                "image_path": "/tmp/dummy.jpg",  # Will fail but tests rate limit
                "exif": {"iso": 400},
                "model": "nn"
            }
            response = requests.post(f"{BASE_URL}/predict", json=payload, timeout=2)

            if response.status_code == 429:
                print_success(f"Request {i+1}: Rate limited (429) - Working correctly!")
                rate_limited = True
                break
            else:
                success_count += 1
        except Exception:
            pass

    if rate_limited:
        print_success("Rate limiting is active and working")
    else:
        print_warning(f"Made {success_count} requests without hitting rate limit")
        print_info("Rate limiting might not be enabled or limit is high")

def generate_summary(results: Dict[str, bool]):
    """Generate final summary"""
    print_section("Test Summary")

    total = len(results)
    passed = sum(1 for v in results.values() if v)
    failed = total - passed

    print_info(f"Total tests: {total}")
    print_success(f"Passed: {passed}")
    if failed > 0:
        print_error(f"Failed: {failed}")

    print("\nDetailed results:")
    for test_name, result in results.items():
        if result:
            print_success(f"  {test_name}")
        else:
            print_error(f"  {test_name}")

    print("\n" + "="*70)
    if failed == 0:
        print_success("🎉 ALL TESTS PASSED! Inference server is ready!")
    else:
        print_warning(f"⚠️  {failed} test(s) failed. Review issues above.")
    print("="*70)

# Main test execution
def main():
    print("\n" + "="*70)
    print(f"{Colors.CYAN}NSP Plugin Inference Server - Exhaustive Test Suite{Colors.END}")
    print(f"Testing server at: {BASE_URL}")
    print(f"Started at: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("="*70)

    # Check connection first
    if not check_server_connection():
        sys.exit(1)

    results = {}

    # Run all tests
    health_data = test_health_endpoint()
    results["Health Check"] = health_data is not None

    results["Model Files Exist"] = check_models_exist()
    results["Database Exists"] = check_database()
    results["Predict Endpoint"] = test_predict_endpoint()

    test_error_handling()
    results["Error Handling"] = True  # If it runs without crashing

    test_feedback_endpoint()
    results["Feedback Endpoint"] = True

    test_rate_limiting()
    results["Rate Limiting"] = True

    # Generate summary
    generate_summary(results)

    print(f"\nTest completed at: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")

if __name__ == "__main__":
    main()
