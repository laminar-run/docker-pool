#!/usr/bin/env python3
import docker
import os

def test_docker_execution():
    try:
        # Connect to Docker
        socket_paths = [
            "unix:///var/run/docker.sock",
            f"unix://{os.path.expanduser('~')}/.docker/run/docker.sock",
            "unix:///Users/saheedakinbile/.docker/run/docker.sock"
        ]
        
        client = None
        for socket_path in socket_paths:
            try:
                client = docker.DockerClient(base_url=socket_path)
                client.ping()
                print(f"✅ Connected to Docker using {socket_path}")
                break
            except Exception:
                continue
        
        if not client:
            print("❌ Could not connect to Docker")
            return
        
        # Create and start a container
        container = client.containers.create(
            "alpine:latest",
            command="/bin/sh",
            stdin_open=True,
            tty=True,
            tmpfs={'/tmp': 'size=100M'},
        )
        container.start()
        print(f"✅ Created container {container.short_id}")
        
        # Test simple command
        result = container.exec_run("echo 'Hello World'")
        print(f"Exit code: {result.exit_code}")
        
        output = result.output
        if isinstance(output, bytes):
            output = output.decode('utf-8', errors='replace')
        print(f"Output: {repr(output)}")
        
        # Test script execution with stdin
        script = "echo 'Testing script execution'\necho 'Current directory:'\npwd"
        result = container.exec_run(
            "/bin/sh",
            stdin=script.encode(),
            stdout=True,
            stderr=True,
            demux=True
        )
        
        print(f"Script exit code: {result.exit_code}")
        
        if isinstance(result.output, tuple):
            stdout, stderr = result.output
            stdout = stdout.decode('utf-8', errors='replace') if stdout else ""
            stderr = stderr.decode('utf-8', errors='replace') if stderr else ""
            print(f"Script stdout: {repr(stdout)}")
            print(f"Script stderr: {repr(stderr)}")
        else:
            output = result.output
            if isinstance(output, bytes):
                output = output.decode('utf-8', errors='replace')
            print(f"Script output: {repr(output)}")
        
        # Clean up
        container.stop(timeout=5)
        container.remove(force=True)
        print("✅ Container cleaned up")
        
    except Exception as e:
        print(f"❌ Error: {e}")
        print(f"Error type: {type(e)}")
        if hasattr(e, 'args'):
            print(f"Error args: {e.args}")

if __name__ == "__main__":
    test_docker_execution()