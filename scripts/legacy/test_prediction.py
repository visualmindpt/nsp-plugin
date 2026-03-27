#!/usr/bin/env python3
"""Quick test of NSP inference server prediction endpoint."""

import requests
import json

# Test data (simulated)
test_request = {
    "image_path": "/path/to/test/image.ARW",
    "exif": {
        "iso": 800,
        "width": 6000,
        "height": 4000
    },
    "model": "lightgbm"
}

print("Testing NSP Inference Server...")
print(f"URL: http://127.0.0.1:5678/predict")
print(f"Request: {json.dumps(test_request, indent=2)}")
print("\n" + "="*60 + "\n")

try:
    response = requests.post(
        "http://127.0.0.1:5678/predict",
        json=test_request,
        timeout=30
    )

    print(f"Status Code: {response.status_code}")

    if response.status_code == 200:
        result = response.json()
        print("\n✅ SUCCESS! Prediction returned:")
        print(json.dumps(result, indent=2))

        if "develop_vector" in result:
            print(f"\n📊 Develop vector length: {len(result['develop_vector'])}")
            print(f"Sample values: {result['develop_vector'][:5]}...")
    else:
        print(f"\n❌ ERROR: {response.status_code}")
        print(response.text)

except requests.exceptions.RequestException as e:
    print(f"\n❌ CONNECTION ERROR: {e}")
except Exception as e:
    print(f"\n❌ UNEXPECTED ERROR: {e}")
