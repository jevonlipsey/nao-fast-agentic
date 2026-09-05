import time
import os
import sys
import qi

# allow importing from lib
sys.path.append(os.path.dirname(os.path.abspath(__file__)))
from lib.file_utils import safe_write, get_env_var

IP = get_env_var("NAO_IP", "10.1.65.214")
PORT = int(get_env_var("NAO_PORT", "9559"))

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
STATE_DIR = os.path.join(BASE_DIR, "state")
EVENTS_FILE = os.path.join(STATE_DIR, "events.txt")


class HumanEventTracker(object):
    def __init__(self, app):
        app.start()
        session = app.session
        self.memory = session.service("ALMemory")
        self.face_detection = session.service("ALFaceDetection")
        self.people_perception = session.service("ALPeoplePerception")

        # multi-person tracking state:
        # active_people: dict mapping person_id -> {"last_seen": timestamp, "name": str or None}
        self.active_people = {}
        self.departure_grace_period = 4.0  # seconds absent before confirming departure
        self.arrival_cooldown = 15.0  # seconds before same id can re-arrive
        self.recently_left = {}  # person_id -> timestamp when left

        # subscribe to force the robot to actively look for faces and people
        self.face_detection.subscribe("HumanEventTracker")
        self.people_perception.subscribe("HumanEventTracker")

    def trigger_arrival(self, person_id):
        # check if this person is already known in almemory
        try:
            stored_name = self.memory.getData("KnownHumans/" + str(person_id))
        except Exception:
            stored_name = None

        if stored_name:
            msg = "[SYSTEM EVENT] A person you already know (ID: {}, name: {}) just arrived. Welcome them back warmly by name. DO NOT use any tools. DO NOT say their ID out loud. Respond with exactly one short sentence.".format(
                person_id, stored_name
            )
        else:
            msg = "[SYSTEM EVENT] A new human (ID: {}) just arrived. Greet them warmly and ask for their name. When they reply, use your 'save_name' tool to save it. DO NOT use your save_name tool yet. DO NOT say their ID out loud. Respond with exactly one short sentence.".format(
                person_id
            )
        print("[[Event Triggered: Arrived -> ID: {} (Known: {})]]".format(person_id, stored_name))
        safe_write(EVENTS_FILE, msg)

    def trigger_departure(self, person_id):
        # extremely fast 0-latency almemory lookup
        try:
            name = self.memory.getData("KnownHumans/" + str(person_id))
        except Exception:
            name = None

        # count how many people remain in the room
        remaining = len(self.active_people)

        if name:
            if remaining > 0:
                msg = "[SYSTEM EVENT] {} (ID: {}) just left. There are still {} other person(s) in the room with you. Say goodbye to {} warmly by name without saying goodbye to the whole room. DO NOT use any tools. Respond with exactly one short sentence.".format(
                    name, person_id, remaining, name
                )
            else:
                msg = "[SYSTEM EVENT] The last human in the room, {} (ID: {}), just left. The room is now empty. Say goodbye to {} warmly by name. DO NOT use any tools. Respond with exactly one short sentence.".format(
                    name, person_id, name
                )
        else:
            if remaining > 0:
                msg = "[SYSTEM EVENT] A human (ID: {}) just left. There are still {} other person(s) in the room with you. Say a brief polite goodbye to the person leaving. DO NOT say their ID out loud. DO NOT use any tools. Respond with exactly one short sentence.".format(
                    person_id, remaining
                )
            else:
                msg = "[SYSTEM EVENT] The human (ID: {}) just left and the room is now empty. Say a generic warm goodbye. DO NOT say their ID out loud. DO NOT use any tools. Respond with exactly one short sentence.".format(
                    person_id
                )

        print("[[Event Triggered: Departed -> ID: {} (Known Name: {}, Remaining: {})]]".format(person_id, name, remaining))
        safe_write(EVENTS_FILE, msg)

    def run(self):
        print("[[Event Polling Layer Ready (Multi-Person Tracking Active)]]")
        try:
            while True:
                now = time.time()
                try:
                    visible = self.memory.getData("PeoplePerception/VisiblePeopleList")
                except Exception:
                    visible = []

                if not isinstance(visible, list):
                    visible = []

                current_visible_ids = set(visible)

                # 1. update last_seen for all currently visible people
                for pid in current_visible_ids:
                    if pid not in self.active_people:
                        # only trigger arrival if not recently departed (sensor flicker)
                        last_departed = self.recently_left.get(pid, 0)
                        if (now - last_departed) >= self.arrival_cooldown:
                            self.active_people[pid] = {"first_seen": now, "last_seen": now}
                            self.trigger_arrival(pid)
                        else:
                            # re-register without spamming greeting
                            self.active_people[pid] = {"first_seen": now, "last_seen": now}
                    else:
                        self.active_people[pid]["last_seen"] = now

                # 2. check for people who have been missing longer than grace period
                departed_ids = []
                for pid, info in list(self.active_people.items()):
                    if pid not in current_visible_ids:
                        time_missing = now - info["last_seen"]
                        if time_missing >= self.departure_grace_period:
                            departed_ids.append(pid)

                # 3. process departures
                for pid in departed_ids:
                    del self.active_people[pid]
                    self.recently_left[pid] = now
                    self.trigger_departure(pid)

                # 4. cleanup old entries from recently_left (older than 60s)
                for pid, left_time in list(self.recently_left.items()):
                    if (now - left_time) > 60.0:
                        del self.recently_left[pid]

                time.sleep(1.0)
        except KeyboardInterrupt:
            self.face_detection.unsubscribe("HumanEventTracker")
            self.people_perception.unsubscribe("HumanEventTracker")


def main():
    connection_url = "tcp://{}:{}".format(IP, PORT)
    try:
        app = qi.Application(["HumanEventTracker", "--qi-url=" + connection_url])
    except RuntimeError:
        print("[[Event Loop Error: Cannot connect to Naoqi at IP {}]]".format(IP))
        sys.exit(1)

    tracker = HumanEventTracker(app)
    tracker.run()


if __name__ == "__main__":
    main()
