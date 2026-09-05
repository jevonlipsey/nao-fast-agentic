import socket
import json
import os
import sys
from rich.console import Console

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from lib.file_utils import get_env_var

console = Console()
DAEMON_PORT = int(get_env_var("DAEMON_PORT", "5005"))

def main():
    console.print(f"[dim white][[Starting Mock Daemon on port {DAEMON_PORT}...]][/]")
    
    # in-memory mock almemory storage
    mock_memory = {}

    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    s.bind(('127.0.0.1', DAEMON_PORT))
    s.listen(5)
    console.print("[dim white][[Mock Daemon Listening for TCP commands...]][/]")

    try:
        while True:
            conn, addr = s.accept()
            try:
                data = conn.recv(4096)
                if not data:
                    continue
                
                payload = json.loads(data.decode('utf-8'))
                command = payload.get("command")
                args = payload.get("args", {})
                
                console.print(f"[dim white][[Mock Daemon Received: {command} with args: {args}]][/]")
                
                if command == "saveName":
                    pid = args.get("id")
                    name = args.get("name")
                    mock_memory[str(pid)] = name
                    console.print(f"[dim white][[Mock ALMemory: Stored {name} under ID {pid}]][/]")

                response = json.dumps({"status": "success", "message": f"Mock executed: {command}"})
                conn.sendall(response.encode('utf-8'))
            except Exception as e:
                console.print(f"[bold red][[Mock Daemon Error]]: {e}[/]")
                response = json.dumps({"status": "error", "message": str(e)})
                conn.sendall(response.encode('utf-8'))
            finally:
                conn.close()
    except KeyboardInterrupt:
        pass

if __name__ == "__main__":
    main()