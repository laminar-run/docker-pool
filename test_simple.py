#!/usr/bin/env python3
import requests
import json

# Test the simple server
url = "http://localhost:8086/execute"
payload = {
    "script": "echo 'Hello World'\necho 'Current directory:'\npwd\necho 'Files in /tmp:'\nls -la /tmp/"
}

try:
    response = requests.post(url, json=payload)
    result = response.json()
    
    print("Response:")
    print(json.dumps(result, indent=2))
    
    if result.get("success"):
        print("\n✅ Script executed successfully!")
        print(f"Output: {result.get('stdout', '')}")
    else:
        print("\n❌ Script execution failed!")
        print(f"Error: {result.get('stderr', '')}")
        
except Exception as e:
    print(f"Error testing server: {e}")