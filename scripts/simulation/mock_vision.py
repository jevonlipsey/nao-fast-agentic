import cv2
import time
import os
from rich.console import Console

console = Console()

# Root project directory is 3 levels up from this file
BASE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
STATE_DIR = os.path.join(BASE_DIR, "state")
FRAME_FILE = os.path.join(STATE_DIR, "latest_frame.jpg")


def main():
    console.print("[dim white][[Starting Mock Vision (Mac Webcam)...]][/]")

    # 0 is usually the default built-in webcam, my default is 1
    cap = cv2.VideoCapture(1)

    if not cap.isOpened():
        console.print("[bold red][[Error: Could not open webcam.]][/]")
        return

    console.print("[dim white][[Mock Camera Polling Layer Ready]][/]")

    try:
        while True:
            ret, frame = cap.read()
            if ret:
                # Resize to roughly 640x480 to mimic the Nao's camera resolution
                frame = cv2.resize(frame, (640, 480))
                # Save as JPEG with 80% quality
                cv2.imwrite(FRAME_FILE, frame, [int(cv2.IMWRITE_JPEG_QUALITY), 80])

            # Write a frame every 0.25 seconds, matching the physical robot
            time.sleep(0.25)

    except KeyboardInterrupt:
        pass
    except Exception as e:
        console.print(f"[bold red][[Mock Vision Error: {e}]][/]")
    finally:
        cap.release()


if __name__ == "__main__":
    main()
