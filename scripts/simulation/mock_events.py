import time
import os
import sys
import socket
import json
from rich.console import Console

console = Console()

# root project directory is 3 levels up from this file
BASE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
STATE_DIR = os.path.join(BASE_DIR, "state")
EVENTS_FILE = os.path.join(STATE_DIR, "events.txt")
TRIGGER_FILE = os.path.join(STATE_DIR, "trigger_event.txt")

# allow importing from lib
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from lib.file_utils import safe_read, safe_write, get_env_var

DAEMON_PORT = int(get_env_var("DAEMON_PORT", "5005"))


def query_mock_daemon_name(person_id):
    # query mock_daemon to see if a name was saved in mock almemory
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        s.settimeout(0.5)
        s.connect(('127.0.0.1', DAEMON_PORT))
        payload = {"command": "getName", "args": {"id": person_id}}
        s.sendall(json.dumps(payload).encode('utf-8'))
        resp_data = s.recv(1024)
        s.close()
        if resp_data:
            res = json.loads(resp_data.decode('utf-8'))
            return res.get("name")
    except Exception:
        pass
    return None


class MockMultiPersonTracker(object):
    def __init__(self):
        # set of currently present person IDs in simulation
        self.present_people = set()

    def handle_arrival(self, person_id):
        self.present_people.add(person_id)
        name = query_mock_daemon_name(person_id)
        if name:
            msg = f"[SYSTEM EVENT] A person you already know (ID: {person_id}, name: {name}) just arrived. Welcome them back warmly by name. DO NOT use any tools. DO NOT say their ID out loud. Respond with exactly one short sentence."
        else:
            msg = f"[SYSTEM EVENT] A new human (ID: {person_id}) just arrived. Greet them warmly and ask for their name. When they reply, use your 'save_name' tool to save it. DO NOT use your save_name tool yet. DO NOT say their ID out loud. Respond with exactly one short sentence."
        
        console.print(f"[bold cyan][[Mock Event Triggered: Arrived -> ID: {person_id} | Total Present: {len(self.present_people)}]][/]")
        safe_write(EVENTS_FILE, msg)

    def handle_departure(self, person_id, name_override=None):
        if person_id in self.present_people:
            self.present_people.remove(person_id)

        name = name_override or query_mock_daemon_name(person_id)
        remaining = len(self.present_people)

        if name:
            if remaining > 0:
                msg = f"[SYSTEM EVENT] {name} (ID: {person_id}) just left. There are still {remaining} other person(s) in the room with you. Say goodbye to {name} warmly by name without saying goodbye to the whole room. DO NOT use any tools. Respond with exactly one short sentence."
            else:
                msg = f"[SYSTEM EVENT] The last human in the room, {name} (ID: {person_id}), just left. The room is now empty. Say goodbye to {name} warmly by name. DO NOT use any tools. Respond with exactly one short sentence."
        else:
            if remaining > 0:
                msg = f"[SYSTEM EVENT] A human (ID: {person_id}) just left. There are still {remaining} other person(s) in the room with you. Say a brief polite goodbye to the person leaving. DO NOT say their ID out loud. DO NOT use any tools. Respond with exactly one short sentence."
            else:
                msg = f"[SYSTEM EVENT] The human (ID: {person_id}) just left and the room is now empty. Say a generic warm goodbye. DO NOT say their ID out loud. DO NOT use any tools. Respond with exactly one short sentence."

        console.print(f"[bold magenta][[Mock Event Triggered: Departed -> ID: {person_id} (Name: {name}) | Remaining: {remaining}]][/]")
        safe_write(EVENTS_FILE, msg)


def main():
    console.print("[dim white][[Mock Event Polling Layer Ready (Multi-Person Support Active)]][/]")
    safe_write(TRIGGER_FILE, "")

    tracker = MockMultiPersonTracker()

    try:
        while True:
            trigger_cmd = safe_read(TRIGGER_FILE)
            if trigger_cmd:
                safe_write(TRIGGER_FILE, "")
                parts = trigger_cmd.split()
                action = parts[0].lower() if parts else ""

                if action in ("arrive", "arrived", "a"):
                    pid = parts[1] if len(parts) > 1 else str(int(time.time()) % 10000)
                    tracker.handle_arrival(pid)

                elif action in ("leave", "depart", "left", "l", "d"):
                    # if no id given, pop an active person or use default
                    if len(parts) > 1:
                        pid = parts[1]
                    elif tracker.present_people:
                        pid = next(iter(tracker.present_people))
                    else:
                        pid = "1001"
                    name_override = parts[2] if len(parts) > 2 else None
                    tracker.handle_departure(pid, name_override)

            time.sleep(0.05)
    except KeyboardInterrupt:
        pass


if __name__ == "__main__":
    main()
