#!/usr/bin/env python3
import docker
import os
import json
from flask import Flask, request, jsonify

app = Flask(__name__)

# Custom JSON serializer to handle bytes
def safe_jsonify(data):
    """Safely convert data to JSON, handling bytes objects"""
    def convert_bytes(obj):
        if isinstance(obj, bytes):
            return obj.decode('utf-8', errors='replace')
        elif isinstance(obj, dict):
            return {k: convert_bytes(v) for k, v in obj.items()}
        elif isinstance(obj, list):
            return [convert_bytes(item) for item in obj]
        elif isinstance(obj, tuple):
            return tuple(convert_bytes(item) for item in obj)
        else:
            return obj
    
    safe_data = convert_bytes(data)
    return jsonify(safe_data)

# Global Docker client
client = None

def init_docker():
    global client
    socket_paths = [
        "unix:///var/run/docker.sock",
        f"unix://{os.path.expanduser('~')}/.docker/run/docker.sock",
        "unix:///Users/saheedakinbile/.docker/run/docker.sock"
    ]
    
    for socket_path in socket_paths:
        try:
            client = docker.DockerClient(base_url=socket_path)
            client.ping()
            print(f"✅ Connected to Docker using {socket_path}")
            return True
        except Exception:
            continue
    return False

@app.route('/execute', methods=['POST'])
def execute_script():
    try:
        data = request.get_json()
        if not data or 'script' not in data:
            return jsonify({"success": False, "error": "No script provided"}), 400
        
        script = data['script']
        
        # Create container
        container = client.containers.create(
            "alpine:latest",
            command="/bin/sh",
            stdin_open=True,
            tty=True,
            tmpfs={'/tmp': 'size=100M'},
        )
        container.start()
        
        try:
            print(f"Executing script: {script[:50]}...")
            
            # Use a simpler approach - execute each line separately
            lines = script.strip().split('\n')
            all_output = []
            final_exit_code = 0
            
            for line in lines:
                if line.strip():  # Skip empty lines
                    result = container.exec_run(f"/bin/sh -c '{line}'")
                    if result.output:
                        output = result.output
                        if isinstance(output, bytes):
                            output = output.decode('utf-8', errors='replace')
                        all_output.append(output.rstrip())
                    
                    if result.exit_code != 0:
                        final_exit_code = result.exit_code
            
            # Combine all outputs
            combined_output = '\n'.join(all_output)
            
            # Create a mock result object
            class MockResult:
                def __init__(self, exit_code, output):
                    self.exit_code = exit_code
                    self.output = output
            
            result = MockResult(final_exit_code, combined_output)
            
            print(f"Execution completed. Exit code: {result.exit_code}")
            print(f"Output type: {type(result.output)}")
            
            # Handle output
            output = ""
            if result.output:
                if isinstance(result.output, bytes):
                    output = result.output.decode('utf-8', errors='replace')
                    print(f"Decoded output: {output[:100]}...")
                else:
                    output = str(result.output)
                    print(f"String output: {output[:100]}...")
            
            response = {
                "success": result.exit_code == 0,
                "stdout": output,
                "stderr": "",
                "exit_code": result.exit_code,
                "error": None
            }
            
            print(f"Response prepared: {response}")
            return safe_jsonify(response)
            
        finally:
            container.stop(timeout=5)
            container.remove(force=True)
            
    except Exception as e:
        # Handle bytes in exception more carefully
        try:
            error_msg = str(e)
        except:
            error_msg = "Unknown error occurred"
        
        # If the error message still contains bytes, handle it
        if isinstance(e, Exception) and hasattr(e, 'args'):
            try:
                clean_args = []
                for arg in e.args:
                    if isinstance(arg, bytes):
                        clean_args.append(arg.decode('utf-8', errors='replace'))
                    else:
                        clean_args.append(str(arg))
                error_msg = ' '.join(clean_args)
            except:
                error_msg = "Error processing exception"
        
        print(f"Error: {error_msg}")
        print(f"Error type: {type(e)}")
        
        return safe_jsonify({
            "success": False,
            "stdout": "",
            "stderr": error_msg,
            "exit_code": -1,
            "error": error_msg
        }), 500

@app.route('/health', methods=['GET'])
def health():
    return jsonify({"status": "healthy"})

if __name__ == '__main__':
    if not init_docker():
        print("❌ Could not connect to Docker")
        exit(1)
    
    print("Starting simple server on port 8086")
    app.run(host='0.0.0.0', port=8086, debug=True)