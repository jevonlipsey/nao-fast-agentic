#!/usr/bin/env python3
"""
interactive terminal helper to simulate human arrival and departure events
supporting multiple people simultaneously while testing in mock mode.

run this in a separate terminal while main.py (use_mock_nao=true) is running:
  python scripts/simulation/trigger_event.py
"""

import os
import sys
import time
import random
from rich.console import Console

console = Console()

# root project directory is 3 levels up from this file
BASE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
STATE_DIR = os.path.join(BASE_DIR, "state")
TRIGGER_FILE = os.path.join(STATE_DIR, "trigger_event.txt")

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from lib.file_utils import safe_write


def print_menu(people_in_room):
    console.print("\n[bold cyan]--- Mock Multi-Person Event Controller ---[/]")
    if people_in_room:
        ids_str = ", ".join(f"[bold yellow]{pid}[/]" for pid in people_in_room)
        console.print(f"People Currently in Room ({len(people_in_room)}): {ids_str}")
    else:
        console.print("People Currently in Room: [dim italic]Nobody (Room is empty)[/]")

    console.print("  [bold green](a)[/] : Add / Arrive new person (generates random ID)")
    console.print("  [bold green](a <id>)[/] : Arrive specific person ID")
    console.print("  [bold magenta](l)[/] : Leave last person who arrived")
    console.print("  [bold magenta](l <id>)[/] : Leave specific person ID")
    console.print("  [bold red](q)[/] : Quit")
    console.print("[dim]Select action and press enter: [/dim]", end="")


def main():
    # keep track of active people in simulation
    people = []

    try:
        while True:
            print_menu(people)
            raw = input().strip()
            parts = raw.split()
            cmd = parts[0].lower() if parts else ""

            if cmd in ("a", "arrive"):
                if len(parts) > 1:
                    new_id = parts[1]
                else:
                    new_id = str(random.randint(1000, 9999))
                if new_id not in people:
                    people.append(new_id)
                safe_write(TRIGGER_FILE, f"arrive {new_id}")
                console.print(f"\n[green]-> Sent Arrival Event for Person ID {new_id}![/]")

            elif cmd in ("l", "leave", "d", "depart"):
                if len(parts) > 1:
                    target_id = parts[1]
                elif people:
                    target_id = people[-1]
                else:
                    target_id = "1001"

                if target_id in people:
                    people.remove(target_id)

                safe_write(TRIGGER_FILE, f"leave {target_id}")
                console.print(f"\n[magenta]-> Sent Departure Event for Person ID {target_id}![/]")

            elif cmd in ("q", "quit", "exit"):
                console.print("\n[dim]Exiting Mock Event Controller.[/]")
                break
            elif not raw:
                # default enter key: add new person
                new_id = str(random.randint(1000, 9999))
                people.append(new_id)
                safe_write(TRIGGER_FILE, f"arrive {new_id}")
                console.print(f"\n[green]-> Sent Arrival Event for Person ID {new_id}![/]")
            else:
                console.print(f"[red]Unknown option: {raw}[/]")

            time.sleep(0.2)
    except (KeyboardInterrupt, EOFError):
        console.print("\n[dim]Exiting.[/]")


if __name__ == "__main__":
    main()
