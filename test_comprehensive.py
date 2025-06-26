#!/usr/bin/env python3
import requests
import json

# Test the server with various scripts
test_cases = [
    {
        "name": "Basic commands",
        "script": "echo 'Hello World'\nwhoami\npwd\ndate"
    },
    {
        "name": "File operations",
        "script": "echo 'test content' > /tmp/test.txt\ncat /tmp/test.txt\nls -la /tmp/test.txt"
    },
    {
        "name": "Math operations",
        "script": "expr 5 + 3\necho $((10 * 2))"
    },
    {
        "name": "Environment",
        "script": "env | head -5\necho $PATH"
    }
]

url = "http://localhost:8085/execute"

for test_case in test_cases:
    print(f"\n{'='*50}")
    print(f"Testing: {test_case['name']}")
    print(f"{'='*50}")
    
    payload = {"script": test_case['script']}
    
    try:
        response = requests.post(url, json=payload)
        result = response.json()
        
        if result.get("success"):
            print("✅ SUCCESS")
            print(f"Exit Code: {result.get('exit_code')}")
            print(f"Execution Time: {result.get('execution_time', 0):.3f}s")
            print(f"Output:\n{result.get('stdout', '')}")
        else:
            print("❌ FAILED")
            print(f"Exit Code: {result.get('exit_code')}")
            print(f"Error: {result.get('stderr', '')}")
            
    except Exception as e:
        print(f"❌ REQUEST FAILED: {e}")

# Test health endpoint
print(f"\n{'='*50}")
print("Testing Health Endpoint")
print(f"{'='*50}")

try:
    response = requests.get("http://localhost:8085/health")
    result = response.json()
    print(f"Health Status: {result}")
except Exception as e:
    print(f"Health check failed: {e}")

# Test metrics endpoint
print(f"\n{'='*50}")
print("Testing Metrics Endpoint")
print(f"{'='*50}")

try:
    response = requests.get("http://localhost:8085/metrics")
    result = response.json()
    print("Metrics:")
    print(json.dumps(result, indent=2))
except Exception as e:
    print(f"Metrics check failed: {e}")