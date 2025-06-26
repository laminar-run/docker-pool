#!/usr/bin/env python3
"""
Test script demonstrating multi-pool functionality with pre-warmed custom containers
"""

import requests
import json
import time

def test_multi_pools():
    """Test the multi-pool functionality"""
    
    base_url = "http://localhost:8080"
    
    print("🏊 Testing Multi-Pool Container Management")
    print("=" * 50)
    
    # Check server health first
    try:
        health_response = requests.get(f"{base_url}/health", timeout=5)
        if not health_response.json().get("status") == "healthy":
            print("❌ Server is not healthy!")
            return False
    except Exception as e:
        print(f"❌ Cannot connect to server: {e}")
        return False
    
    print("✅ Server is healthy, checking pool metrics...\n")
    
    # Get initial metrics to see pool configuration
    try:
        metrics_response = requests.get(f"{base_url}/metrics", timeout=5)
        metrics = metrics_response.json()
        
        print("📊 Pool Configuration:")
        print("-" * 30)
        print(f"Total Pools Active: {metrics.get('pools_active', 0)}")
        print(f"Total Available Containers: {metrics.get('total_available_containers', 0)}")
        
        pool_metrics = metrics.get('pool_metrics', {})
        for image, pool_stats in pool_metrics.items():
            print(f"\n🏊 Pool: {image}")
            print(f"  Pool Size: {pool_stats.get('pool_size', 0)}")
            print(f"  Available: {pool_stats.get('available_containers', 0)}")
            print(f"  Created: {pool_stats.get('containers_created', 0)}")
            print(f"  Destroyed: {pool_stats.get('containers_destroyed', 0)}")
        
        print("\n" + "=" * 50)
        
    except Exception as e:
        print(f"❌ Failed to get metrics: {e}")
        return False
    
    # Test cases to demonstrate pool usage
    test_cases = [
        {
            "name": "Default Pool (Alpine)",
            "payload": {
                "script": "echo 'Using default pool'\ncat /etc/os-release | grep PRETTY_NAME\necho 'Container ID:'\nhostname"
            },
            "expected_pool": "default"
        },
        {
            "name": "Python Pool (if configured)",
            "payload": {
                "script": "echo 'Using Python pool'\npython3 -c 'import sys; print(f\"Python {sys.version}\")'",
                "image": "python-scientific-executor"
            },
            "expected_pool": "python-scientific-executor"
        },
        {
            "name": "Node.js Pool (if configured)",
            "payload": {
                "script": "echo 'Using Node.js pool'\nnode -e 'console.log(\"Node.js\", process.version)'",
                "image": "nodejs-executor"
            },
            "expected_pool": "nodejs-executor"
        },
        {
            "name": "Multi-language Pool (if configured)",
            "payload": {
                "script": "echo 'Using multi-language pool'\npython3 --version\nnode --version 2>/dev/null || echo 'Node.js not available'",
                "image": "multi-language-executor"
            },
            "expected_pool": "multi-language-executor"
        },
        {
            "name": "Custom Image (temporary container)",
            "payload": {
                "script": "echo 'Using temporary container'\ncat /etc/os-release | grep PRETTY_NAME",
                "image": "ubuntu:22.04"
            },
            "expected_pool": "temporary"
        }
    ]
    
    print("🧪 Running Pool Tests:")
    print("=" * 50)
    
    for i, test_case in enumerate(test_cases, 1):
        print(f"\nTest {i}: {test_case['name']}")
        print("-" * 40)
        
        start_time = time.time()
        
        try:
            response = requests.post(
                f"{base_url}/execute",
                json=test_case["payload"],
                timeout=60
            )
            
            result = response.json()
            execution_time = time.time() - start_time
            
            if result.get("success"):
                print("✅ SUCCESS")
                print(f"Total Time: {execution_time:.3f}s (includes network + execution)")
                print(f"Execution Time: {result.get('execution_time', 0):.3f}s")
                
                # Show first few lines of output
                stdout = result.get('stdout', '').strip()
                if stdout:
                    lines = stdout.split('\n')[:3]
                    for line in lines:
                        print(f"Output: {line}")
                    if len(stdout.split('\n')) > 3:
                        print("... (truncated)")
                
                # Indicate if this used a pool or temporary container
                image = test_case["payload"].get("image")
                if image and image in pool_metrics:
                    print(f"🏊 Used pre-warmed pool for {image}")
                elif image:
                    print(f"🔧 Created temporary container for {image}")
                else:
                    print("🏊 Used default pool")
                    
            else:
                print("❌ FAILED")
                error = result.get('stderr') or result.get('error', 'Unknown error')
                print(f"Error: {error}")
                
        except Exception as e:
            print(f"❌ REQUEST FAILED: {e}")
    
    # Get final metrics
    print("\n" + "=" * 50)
    print("📊 Final Pool Metrics:")
    print("=" * 50)
    
    try:
        final_metrics_response = requests.get(f"{base_url}/metrics", timeout=5)
        final_metrics = final_metrics_response.json()
        
        print(f"Total Executions: {final_metrics.get('total_executions', 0)}")
        print(f"Successful: {final_metrics.get('successful_executions', 0)}")
        print(f"Failed: {final_metrics.get('failed_executions', 0)}")
        print(f"Average Execution Time: {final_metrics.get('average_execution_time', 0):.3f}s")
        
        final_pool_metrics = final_metrics.get('pool_metrics', {})
        for image, pool_stats in final_pool_metrics.items():
            print(f"\n🏊 Pool: {image}")
            print(f"  Executions: {pool_stats.get('total_executions', 0)}")
            print(f"  Available: {pool_stats.get('available_containers', 0)}")
            print(f"  Created: {pool_stats.get('containers_created', 0)}")
            print(f"  Destroyed: {pool_stats.get('containers_destroyed', 0)}")
        
    except Exception as e:
        print(f"❌ Failed to get final metrics: {e}")
    
    print("\n" + "=" * 50)
    print("💡 Multi-Pool Benefits:")
    print("=" * 50)
    print("✅ Fast execution for pre-configured images (no container creation delay)")
    print("✅ Automatic fallback to temporary containers for unknown images")
    print("✅ Resource isolation between different execution environments")
    print("✅ Configurable pool sizes per image type")
    print("✅ Combined metrics across all pools")
    
    print("\n📝 Configuration Examples:")
    print("-" * 30)
    print("# Configure custom pools via environment variable:")
    print("CUSTOM_POOLS=python-scientific-executor:3,nodejs-executor:2,multi-language-executor:1")
    print("")
    print("# Or via docker-compose:")
    print("environment:")
    print("  - CUSTOM_POOLS=python-scientific-executor:3,nodejs-executor:2")

if __name__ == "__main__":
    test_multi_pools()