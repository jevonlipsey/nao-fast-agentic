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
from lib.file_utils import safe_read, safe_write, get_env_var

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
                text = safe_read(RESPONSE_FILE)
                if text:
                    # clear response file immediately so the LLM can write the final response 
                    # while the robot is still physically speaking this one
                    safe_write(RESPONSE_FILE, "")

                    text = text.replace("\n", " ")

                    is_intermediate = text.startswith("[INTERMEDIATE] ")
                    if is_intermediate:
                        text = text[len("[INTERMEDIATE] ") :]

                    text_utf8 = text.encode("utf-8")
                    animated_speech.say(text_utf8)

                    if not is_intermediate:
                        time.sleep(0.8) # Let physical room echo die down
                        safe_write(LISTEN_FILE, "yes")

                time.sleep(0.1)
            except Exception as e:
                err_str = str(e)
                if "Session closed" in err_str or "module destroyed" in err_str:
                    print("\n[[ FATAL: Connection to robot lost (WiFi dropped). Please restart main.py ]]")
                    sys.exit(1)
                print("[[Actuation Loop Error: ", err_str, " ]]")
                time.sleep(0.1)
    except KeyboardInterrupt:
        pass


if __name__ == "__main__":
    main()
