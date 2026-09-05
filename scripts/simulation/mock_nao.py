"""
simulates nao_tts.py setting listen state and processing responses.
use if not near the NAO robot. variable for using this file is at the top
of main.py
"""

import time
import os
import sys

# allow importing from lib (one level up)
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from lib.file_utils import safe_read, safe_write

# root project directory is 3 levels up from this file
BASE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
STATE_DIR = os.path.join(BASE_DIR, "state")

RESPONSE_FILE = os.path.join(STATE_DIR, "response.txt")
LISTEN_FILE = os.path.join(STATE_DIR, "listen.txt")

try:
    while True:
        try:
            text = safe_read(RESPONSE_FILE)

            if text:
                # clear response file immediately so the llm can write the final response 
                # while the robot is still "speaking" this one
                safe_write(RESPONSE_FILE, "")

                is_intermediate = text.startswith("[INTERMEDIATE] ")

                if is_intermediate:
                    text = text[len("[INTERMEDIATE] ") :]
                    time.sleep(0.4)
                else:
                    # estimate reading time: ~12 chars/sec or at least 0.5s
                    spoken_time = max(0.6, min(2.5, len(text) / 15.0))
                    time.sleep(spoken_time)

                # signal ready to listen after final response
                if not is_intermediate:
                    time.sleep(0.15) # match physical robot's quick buffer flush
                    safe_write(LISTEN_FILE, "yes")
        except Exception:
            pass

        time.sleep(0.03)
except KeyboardInterrupt:
    pass
