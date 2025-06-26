#!/usr/bin/env python3
"""
Test script demonstrating how to specify custom images in the execute API
"""

import requests
import json

def test_custom_image_api():
    """Test the execute API with custom image specification"""
    
    base_url = "http://localhost:8080"
    
    print("🧪 Testing Custom Image API")
    print("=" * 40)
    
    # Test cases with different images
    test_cases = [
        {
            "name": "Default Alpine (no image specified)",
            "payload": {
                "script": "cat /etc/os-release | grep PRETTY_NAME\necho 'Available commands:'\nwhich python3 || echo 'Python3 not available'\nwhich node || echo 'Node not available'"
            }
        },
        {
            "name": "Python Scientific Image",
            "payload": {
                "script": "python3 -c 'import numpy, pandas; print(f\"NumPy: {numpy.__version__}, Pandas: {pandas.__version__}\")'",
                "image": "python-scientific-executor"
            }
        },
        {
            "name": "Node.js Runtime Image",
            "payload": {
                "script": "node -e 'const _ = require(\"lodash\"); console.log(\"Lodash version:\", _.VERSION);'",
                "image": "nodejs-executor"
            }
        },
        {
            "name": "Multi-language Image - Python",
            "payload": {
                "script": "python3 -c 'import requests; print(f\"Python requests: {requests.__version__}\")'",
                "image": "multi-language-executor"
            }
        },
        {
            "name": "Multi-language Image - Node.js",
            "payload": {
                "script": "node -e 'console.log(\"Node.js version:\", process.version);'",
                "image": "multi-language-executor"
            }
        },
        {
            "name": "Multi-language Image - Java",
            "payload": {
                "script": "java -version 2>&1 | head -1",
                "image": "multi-language-executor"
            }
        }
    ]
    
    # Check server health first
    try:
        health_response = requests.get(f"{base_url}/health", timeout=5)
        if not health_response.json().get("status") == "healthy":
            print("❌ Server is not healthy!")
            return False
    except Exception as e:
        print(f"❌ Cannot connect to server: {e}")
        return False
    
    print("✅ Server is healthy, running tests...\n")
    
    # Run test cases
    for i, test_case in enumerate(test_cases, 1):
        print(f"Test {i}: {test_case['name']}")
        print("-" * 40)
        
        try:
            response = requests.post(
                f"{base_url}/execute",
                json=test_case["payload"],
                timeout=60  # Longer timeout for image pulling
            )
            
            result = response.json()
            
            if result.get("success"):
                print("✅ SUCCESS")
                print(f"Execution Time: {result.get('execution_time', 0):.3f}s")
                stdout = result.get('stdout', '').strip()
                if stdout:
                    # Show first few lines of output
                    lines = stdout.split('\n')[:3]
                    for line in lines:
                        print(f"Output: {line}")
                    if len(stdout.split('\n')) > 3:
                        print("... (truncated)")
            else:
                print("❌ FAILED")
                print(f"Error: {result.get('stderr') or result.get('error', 'Unknown error')}")
                
        except Exception as e:
            print(f"❌ REQUEST FAILED: {e}")
        
        print()
    
    print("=" * 40)
    print("📋 API Usage Examples:")
    print()
    
    # Show usage examples
    examples = [
        {
            "description": "Basic execution (uses default pool image)",
            "curl": '''curl -X POST http://localhost:8080/execute \\
  -H "Content-Type: application/json" \\
  -d '{"script": "echo \\"Hello World\\""}'
'''
        },
        {
            "description": "Python scientific computing",
            "curl": '''curl -X POST http://localhost:8080/execute \\
  -H "Content-Type: application/json" \\
  -d '{
    "script": "python3 -c \\"import numpy; print(numpy.array([1,2,3]).sum())\\"",
    "image": "python-scientific-executor"
  }'
'''
        },
        {
            "description": "Node.js execution",
            "curl": '''curl -X POST http://localhost:8080/execute \\
  -H "Content-Type: application/json" \\
  -d '{
    "script": "node -e \\"console.log(process.version)\\"",
    "image": "nodejs-executor"
  }'
'''
        },
        {
            "description": "Custom registry image",
            "curl": '''curl -X POST http://localhost:8080/execute \\
  -H "Content-Type: application/json" \\
  -d '{
    "script": "your-custom-command",
    "image": "my-registry.com/my-custom-executor:v1.0"
  }'
'''
        }
    ]
    
    for example in examples:
        print(f"• {example['description']}:")
        print(example['curl'])
    
    print("📝 Notes:")
    print("- If 'image' is not specified, the default pool image is used")
    print("- Custom images are pulled automatically if not available locally")
    print("- Custom images create temporary containers (not from the pool)")
    print("- Registry prefix is added automatically if CUSTOM_IMAGE_REGISTRY is set")
    print("- Image names are validated before use")

if __name__ == "__main__":
    test_custom_image_api()