"""
handles text-to-speech and actuation for NAO robot.
polls llm's state/response.txt to give speech output and actuate the robot.
updates state/listen.txt to signal readiness for the next input.

layer 3: nao_tts -> actuation
"""

from __future__ import print_function
import time
import os
import random
import sys
from naoqi import ALProxy

# allow importing from lib
sys.path.append(os.path.dirname(os.path.abspath(__file__)))
from lib.file_utils import safe_read, safe_write, queue_pop, get_env_var

IP = get_env_var("NAO_IP", "10.1.65.214")
PORT = int(get_env_var("NAO_PORT", "9559"))

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
STATE_DIR = os.path.join(BASE_DIR, "state")

RESPONSE_FILE = os.path.join(STATE_DIR, "response.txt")
LISTEN_FILE = os.path.join(STATE_DIR, "listen.txt")


def main():
    print("[[Connecting to NAOqi Proxies...]]")
    try:
        tts = ALProxy("ALTextToSpeech", IP, PORT)
        animated_speech = ALProxy("ALAnimatedSpeech", IP, PORT)
    except Exception as e:
        print("[[Error connecting to NAOqi. Is the robot IP correct?]]")
        print("Details: ", e)
        return

    safe_write(LISTEN_FILE, "no")
    safe_write(RESPONSE_FILE, "")

    print("[[Robot Actuation Layer Ready]]")

    try:
        while True:
            try:
                line = queue_pop(RESPONSE_FILE)
                if line:
                    if line == "[END_OF_TURN]":
                        time.sleep(0.15) # brief buffer before enabling mic
                        safe_write(LISTEN_FILE, "yes")
                        continue

                    is_intermediate = line.startswith("[INTERMEDIATE] ")
                    if is_intermediate:
                        line = line[len("[INTERMEDIATE] ") :]

                    # strip markdown artifacts that mess up alanimatedspeech
                    clean_text = line.replace("**", "").replace("*", "").replace("`", "")
                    clean_text = " ".join(clean_text.split())

                    if clean_text:
                        text_utf8 = clean_text.encode("utf-8")
                        animated_speech.say(text_utf8)

                time.sleep(0.02)
            except Exception as e:
                err_str = str(e)
                if "Session closed" in err_str or "module destroyed" in err_str:
                    print("\n[[ FATAL: Connection to robot lost (WiFi dropped). Please restart main.py ]]")
                    sys.exit(1)
                print("[[Actuation Loop Error: ", err_str, " ]]")
                time.sleep(0.05)
    except KeyboardInterrupt:
        pass


if __name__ == "__main__":
    main()
