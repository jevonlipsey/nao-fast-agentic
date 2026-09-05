import cv2
import time
import os
import sys
from rich.console import Console

console = Console()

# root project directory is 3 levels up from this file
BASE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
STATE_DIR = os.path.join(BASE_DIR, "state")
FRAME_FILE = os.path.join(STATE_DIR, "latest_frame.jpg")

# allow importing from lib
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from lib.file_utils import get_env_var


def main():
    console.print("[dim white][[Starting Mock Vision (Webcam)...]][/]")

    # check .env for WEBCAM_INDEX or auto-detect webcam index (try 0 then 1)
    env_idx = get_env_var("WEBCAM_INDEX", "").strip()
    if env_idx.isdigit():
        cam_indices = [int(env_idx)]
    else:
        cam_indices = [0, 1]

    cap = None
    for idx in cam_indices:
        test_cap = cv2.VideoCapture(idx)
        if test_cap.isOpened():
            ret, _ = test_cap.read()
            if ret:
                cap = test_cap
                console.print(f"[dim white][[Mock Vision: Connected to webcam index {idx}]][/]")
                break
            test_cap.release()

    if cap is None or not cap.isOpened():
        console.print("[bold red][[Error: Could not open any webcam (tried indices 0, 1).]][/]")
        return

    console.print("[dim white][[Mock Camera Polling Layer Ready]][/]")

    try:
        while True:
            ret, frame = cap.read()
            if ret:
                # resize to roughly 640x480 to mimic the nao's camera resolution
                frame = cv2.resize(frame, (640, 480))
                # save as jpeg with 80% quality
                cv2.imwrite(FRAME_FILE, frame, [int(cv2.IMWRITE_JPEG_QUALITY), 80])

            # write a frame every 0.25 seconds, matching the physical robot
            time.sleep(0.25)

    except KeyboardInterrupt:
        pass
    except Exception as e:
        console.print(f"[bold red][[Mock Vision Error: {e}]][/]")
    finally:
        cap.release()


if __name__ == "__main__":
    main()
