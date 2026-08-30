"""
simulates nao_tts.py setting listen state and processing responses.
use if not near the NAO robot. variable for using this file is at the top
of main.py
"""

import time
import os
import sys

# allow importing from lib
sys.path.append(os.path.dirname(os.path.abspath(__file__)))
from lib.file_utils import safe_read, safe_write

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
STATE_DIR = os.path.join(BASE_DIR, "state")

RESPONSE_FILE = os.path.join(STATE_DIR, "response.txt")
LISTEN_FILE = os.path.join(STATE_DIR, "listen.txt")

while True:
    try:
        text = safe_read(RESPONSE_FILE)

        if text:
            is_intermediate = text.startswith("[INTERMEDIATE] ")

            if is_intermediate:
                text = text[len("[INTERMEDIATE] ") :]
                print(f"[[NAO]]: {text}")
                time.sleep(1.0)
            else:
                time.sleep(2.0)

            # clear response file
            safe_write(RESPONSE_FILE, "")

            # signal ready to listen after final response
            if not is_intermediate:
                safe_write(LISTEN_FILE, "yes")
    except Exception:
        pass

    time.sleep(0.2)
