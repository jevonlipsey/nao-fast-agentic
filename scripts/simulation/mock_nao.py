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
from lib.file_utils import safe_read, safe_write, queue_pop

# root project directory is 3 levels up from this file
BASE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
STATE_DIR = os.path.join(BASE_DIR, "state")

RESPONSE_FILE = os.path.join(STATE_DIR, "response.txt")
LISTEN_FILE = os.path.join(STATE_DIR, "listen.txt")

try:
    while True:
        try:
            line = queue_pop(RESPONSE_FILE)

            if line:
                if line == "[END_OF_TURN]":
                    time.sleep(0.15) # match physical robot's quick buffer flush
                    safe_write(LISTEN_FILE, "yes")
                    continue

                is_intermediate = line.startswith("[INTERMEDIATE] ")

                if is_intermediate:
                    time.sleep(0.35)
                else:
                    # estimate reading time: ~14 chars/sec
                    spoken_time = max(0.4, min(2.0, len(line) / 14.0))
                    time.sleep(spoken_time)
        except Exception:
            pass

        time.sleep(0.02)
except KeyboardInterrupt:
    pass
