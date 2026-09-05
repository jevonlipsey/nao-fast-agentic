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

        self.is_someone_here = False
        self.empty_frames = 0
        self.active_id = None

        # subscribe to force the robot to actively look for faces and people
        self.face_detection.subscribe("HumanEventTracker")
        self.people_perception.subscribe("HumanEventTracker")

    def trigger_arrival(self, value):
        msg = "[SYSTEM EVENT] A new human (ID: {}) just arrived. Greet them warmly and ask for their name. When they reply, use your 'save_name' tool to save it. DO NOT use your save_name tool yet. DO NOT say their ID out loud. Respond with exactly one short sentence.".format(
            value
        )
        print("[[Event Triggered: Arrived -> ID: {}]]".format(value))
        safe_write(EVENTS_FILE, msg)

    def trigger_departure(self, value):
        # extremely fast 0-latency almemory lookup!
        try:
            name = self.memory.getData("KnownHumans/" + str(value))
        except Exception:
            name = None

        if name:
            msg = "[SYSTEM EVENT] The human just left. Their name is {}. Say goodbye to them warmly by name. DO NOT use any tools. Respond instantly with exactly one short sentence.".format(name)
        else:
            msg = "[SYSTEM EVENT] The human just left. You don't know their name, so just say a generic warm goodbye. DO NOT use any tools. Respond instantly with exactly one short sentence."

        print("[[Event Triggered: Departed -> ID: {} (Known Name: {})]]".format(value, name))
        safe_write(EVENTS_FILE, msg)

    def run(self):
        print("[[Event Polling Layer Ready]]")
        try:
            while True:
                try:
                    visible = self.memory.getData("PeoplePerception/VisiblePeopleList")
                except Exception:
                    visible = []

                if visible and len(visible) > 0:
                    self.empty_frames = 0
                    if not self.is_someone_here:
                        self.is_someone_here = True
                        self.active_id = visible[0]
                        self.trigger_arrival(self.active_id)
                else:
                    self.empty_frames += 1
                    # if empty for ~4 seconds (polling at 1hz)
                    if self.empty_frames >= 4 and self.is_someone_here:
                        self.is_someone_here = False
                        self.trigger_departure(self.active_id)
                        self.active_id = None
                
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
