#!/usr/bin/env python3
"""
Comprehensive test suite for custom container images
Tests various custom images with their specific capabilities
"""

import requests
import json
import time
import sys
import os
from typing import Dict, List, Tuple

class CustomImageTester:
    def __init__(self, base_url: str = "http://localhost:8080"):
        self.base_url = base_url
        self.results = []
    
    def execute_script(self, script: str, description: str = "") -> Dict:
        """Execute a script and return the result"""
        try:
            response = requests.post(
                f"{self.base_url}/execute",
                json={"script": script},
                timeout=30
            )
            result = response.json()
            result["description"] = description
            return result
        except Exception as e:
            return {
                "success": False,
                "error": str(e),
                "description": description
            }
    
    def test_python_scientific(self) -> List[Dict]:
        """Test Python scientific computing capabilities"""
        print("🐍 Testing Python Scientific Image...")
        
        tests = [
            {
                "script": "python3 -c 'import sys; print(f\"Python version: {sys.version}\")'",
                "description": "Python version check"
            },
            {
                "script": "python3 -c 'import numpy as np; print(f\"NumPy version: {np.__version__}\"); print(f\"Array sum: {np.sum([1,2,3,4,5])}\")''",
                "description": "NumPy functionality"
            },
            {
                "script": "python3 -c 'import pandas as pd; df = pd.DataFrame({\"a\": [1,2,3], \"b\": [4,5,6]}); print(f\"Pandas version: {pd.__version__}\"); print(df.sum())'",
                "description": "Pandas DataFrame operations"
            },
            {
                "script": "python3 -c 'import scipy; from scipy import stats; print(f\"SciPy version: {scipy.__version__}\"); print(f\"Normal distribution mean: {stats.norm.mean()}\")'",
                "description": "SciPy statistical functions"
            },
            {
                "script": "python3 -c 'import matplotlib; print(f\"Matplotlib version: {matplotlib.__version__}\")'",
                "description": "Matplotlib availability"
            },
            {
                "script": "python3 -c 'import sklearn; from sklearn.datasets import make_classification; X, y = make_classification(n_samples=10, n_features=4); print(f\"Scikit-learn version: {sklearn.__version__}\"); print(f\"Generated dataset shape: {X.shape}\")'",
                "description": "Scikit-learn machine learning"
            }
        ]
        
        results = []
        for test in tests:
            result = self.execute_script(test["script"], test["description"])
            results.append(result)
            self.print_test_result(result)
        
        return results
    
    def test_nodejs_runtime(self) -> List[Dict]:
        """Test Node.js runtime capabilities"""
        print("🟢 Testing Node.js Runtime Image...")
        
        tests = [
            {
                "script": "node --version",
                "description": "Node.js version check"
            },
            {
                "script": "npm --version",
                "description": "NPM version check"
            },
            {
                "script": "node -e 'const _ = require(\"lodash\"); console.log(\"Lodash version:\", _.VERSION); console.log(\"Array chunk:\", _.chunk([1,2,3,4,5,6], 2));'",
                "description": "Lodash functionality"
            },
            {
                "script": "node -e 'const axios = require(\"axios\"); console.log(\"Axios available:\", typeof axios);'",
                "description": "Axios HTTP client"
            },
            {
                "script": "node -e 'const moment = require(\"moment\"); console.log(\"Moment.js version:\", moment.version); console.log(\"Current time:\", moment().format());'",
                "description": "Moment.js date handling"
            },
            {
                "script": "node -e 'const { v4: uuidv4 } = require(\"uuid\"); console.log(\"Generated UUID:\", uuidv4());'",
                "description": "UUID generation"
            },
            {
                "script": "node -e 'const chalk = require(\"chalk\"); console.log(\"Chalk available:\", typeof chalk);'",
                "description": "Chalk terminal styling"
            }
        ]
        
        results = []
        for test in tests:
            result = self.execute_script(test["script"], test["description"])
            results.append(result)
            self.print_test_result(result)
        
        return results
    
    def test_multi_language(self) -> List[Dict]:
        """Test multi-language environment capabilities"""
        print("🌐 Testing Multi-Language Image...")
        
        tests = [
            {
                "script": "python3 --version",
                "description": "Python availability"
            },
            {
                "script": "node --version",
                "description": "Node.js availability"
            },
            {
                "script": "java -version 2>&1 | head -1",
                "description": "Java availability"
            },
            {
                "script": "go version",
                "description": "Go availability"
            },
            {
                "script": "ruby --version",
                "description": "Ruby availability"
            },
            {
                "script": "python3 -c 'import requests; print(f\"Python requests available: {requests.__version__}\")'",
                "description": "Python packages"
            },
            {
                "script": "node -e 'const _ = require(\"lodash\"); console.log(\"Node.js lodash available:\", _.VERSION);'",
                "description": "Node.js packages"
            },
            {
                "script": "ruby -e 'require \"json\"; puts \"Ruby JSON available: #{JSON::VERSION}\"'",
                "description": "Ruby gems"
            },
            {
                "script": "echo 'package main; import \"fmt\"; func main() { fmt.Println(\"Go Hello World\") }' > /tmp/hello.go && cd /tmp && go run hello.go",
                "description": "Go program execution"
            }
        ]
        
        results = []
        for test in tests:
            result = self.execute_script(test["script"], test["description"])
            results.append(result)
            self.print_test_result(result)
        
        return results
    
    def test_alpine_basic(self) -> List[Dict]:
        """Test basic Alpine Linux capabilities"""
        print("🏔️ Testing Alpine Basic Image...")
        
        tests = [
            {
                "script": "cat /etc/os-release | grep PRETTY_NAME",
                "description": "OS identification"
            },
            {
                "script": "whoami",
                "description": "User context"
            },
            {
                "script": "pwd",
                "description": "Working directory"
            },
            {
                "script": "echo 'Hello World' > /tmp/test.txt && cat /tmp/test.txt",
                "description": "File operations"
            },
            {
                "script": "ls -la /tmp/",
                "description": "Directory listing"
            },
            {
                "script": "date",
                "description": "System date"
            },
            {
                "script": "expr 5 + 3",
                "description": "Basic arithmetic"
            }
        ]
        
        results = []
        for test in tests:
            result = self.execute_script(test["script"], test["description"])
            results.append(result)
            self.print_test_result(result)
        
        return results
    
    def print_test_result(self, result: Dict):
        """Print formatted test result"""
        description = result.get("description", "Unknown test")
        if result.get("success", False):
            print(f"  ✅ {description}")
            if result.get("stdout"):
                # Print first line of output for brevity
                first_line = result["stdout"].split('\n')[0]
                print(f"     Output: {first_line}")
        else:
            print(f"  ❌ {description}")
            error = result.get("stderr") or result.get("error", "Unknown error")
            print(f"     Error: {error}")
    
    def run_comprehensive_test(self, image_type: str = "auto"):
        """Run comprehensive tests based on image type"""
        print(f"🧪 Starting Comprehensive Custom Image Tests")
        print("=" * 50)
        
        # Check server health first
        try:
            health_response = requests.get(f"{self.base_url}/health", timeout=5)
            if not health_response.json().get("status") == "healthy":
                print("❌ Server is not healthy!")
                return False
        except Exception as e:
            print(f"❌ Cannot connect to server: {e}")
            return False
        
        print("✅ Server is healthy, starting tests...\n")
        
        # Determine image type if auto
        if image_type == "auto":
            # Try to detect image type by testing capabilities
            python_test = self.execute_script("python3 -c 'import numpy'", "Python NumPy detection")
            node_test = self.execute_script("node -e 'require(\"lodash\")'", "Node.js Lodash detection")
            java_test = self.execute_script("java -version", "Java detection")
            
            if python_test.get("success") and "numpy" not in python_test.get("stderr", "").lower():
                image_type = "python-scientific"
            elif node_test.get("success"):
                image_type = "nodejs"
            elif java_test.get("success"):
                image_type = "multi-language"
            else:
                image_type = "alpine"
        
        print(f"🔍 Detected/Selected image type: {image_type}\n")
        
        # Run appropriate tests
        all_results = []
        
        if image_type == "python-scientific":
            all_results.extend(self.test_python_scientific())
        elif image_type == "nodejs":
            all_results.extend(self.test_nodejs_runtime())
        elif image_type == "multi-language":
            all_results.extend(self.test_multi_language())
        elif image_type == "alpine":
            all_results.extend(self.test_alpine_basic())
        elif image_type == "all":
            # Test all capabilities (useful for multi-language image)
            all_results.extend(self.test_alpine_basic())
            all_results.extend(self.test_python_scientific())
            all_results.extend(self.test_nodejs_runtime())
            all_results.extend(self.test_multi_language())
        
        # Print summary
        self.print_summary(all_results)
        
        return all(result.get("success", False) for result in all_results)
    
    def print_summary(self, results: List[Dict]):
        """Print test summary"""
        print("\n" + "=" * 50)
        print("📊 Test Summary")
        print("=" * 50)
        
        total_tests = len(results)
        passed_tests = sum(1 for result in results if result.get("success", False))
        failed_tests = total_tests - passed_tests
        
        print(f"Total Tests: {total_tests}")
        print(f"Passed: {passed_tests} ✅")
        print(f"Failed: {failed_tests} ❌")
        print(f"Success Rate: {(passed_tests/total_tests)*100:.1f}%")
        
        if failed_tests > 0:
            print("\nFailed Tests:")
            for result in results:
                if not result.get("success", False):
                    description = result.get("description", "Unknown")
                    error = result.get("stderr") or result.get("error", "Unknown error")
                    print(f"  ❌ {description}: {error}")

def main():
    import argparse
    
    parser = argparse.ArgumentParser(description="Test custom container images")
    parser.add_argument("--url", default="http://localhost:8080", help="Server URL")
    parser.add_argument("--image-type", choices=["auto", "alpine", "python-scientific", "nodejs", "multi-language", "all"], 
                       default="auto", help="Image type to test")
    parser.add_argument("--port", type=int, help="Server port (overrides URL port)")
    
    args = parser.parse_args()
    
    # Override port if specified
    if args.port:
        args.url = f"http://localhost:{args.port}"
    
    tester = CustomImageTester(args.url)
    
    try:
        success = tester.run_comprehensive_test(args.image_type)
        sys.exit(0 if success else 1)
    except KeyboardInterrupt:
        print("\n🛑 Tests interrupted by user")
        sys.exit(1)
    except Exception as e:
        print(f"\n💥 Test execution failed: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()