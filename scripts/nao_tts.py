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
from lib.file_utils import safe_read, safe_write

IP = "10.1.65.214"
PORT = 9559

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
STATE_DIR = os.path.join(BASE_DIR, "state")

RESPONSE_FILE = os.path.join(STATE_DIR, "response.txt")
LISTEN_FILE = os.path.join(STATE_DIR, "listen.txt")


def main():
    print("[[Connecting to NAOqi Proxies...]]")
    try:
        tts = ALProxy("ALTextToSpeech", IP, PORT)
        animated_speech = ALProxy("ALAnimatedSpeech", IP, PORT)
        posture_proxy = ALProxy("ALRobotPosture", IP, PORT)
        awareness_proxy = ALProxy("ALBasicAwareness", IP, PORT)
    except Exception as e:
        print("[[Error connecting to NAOqi. Is the robot IP correct?]]")
        print("Details: ", e)
        return

    print("[[Setting Posture to StandInit...]]")
    if posture_proxy.getPosture() != "Stand":
        posture_proxy.goToPosture("StandInit", 1.0)

    print("[[Enabling Basic Awareness...]]")
    try:
        # track faces
        awareness_proxy.setEngagementMode("FullyEngaged")
        awareness_proxy.startAwareness()
    except Exception as e:
        print("[[Basic Awareness Warning: ", e, " ]]")

    safe_write(LISTEN_FILE, "no")
    safe_write(RESPONSE_FILE, "")

    print("[[Robot Actuation Layer Ready]]")

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

                print("[[ACTUATING]]: {}".format(text))

                animated_speech.say(text.encode("utf-8"))

                if not is_intermediate:
                    safe_write(LISTEN_FILE, "yes")
                    print("[[DONE]]")

            time.sleep(0.1)
        except Exception as e:
            print("[[Actuation Loop Error: ", e, " ]]")
            time.sleep(0.1)


if __name__ == "__main__":
    main()
