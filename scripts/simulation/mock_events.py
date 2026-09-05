import time
from rich.console import Console

console = Console()

def main():
    console.print("[dim white][[Mock Event Polling Layer Ready]][/]")
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        pass

if __name__ == "__main__":
    main()