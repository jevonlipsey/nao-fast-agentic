import cv2
import time
import os

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
STATE_DIR = os.path.join(BASE_DIR, "state")
FRAME_FILE = os.path.join(STATE_DIR, "latest_frame.jpg")


def main():
    print("[[Starting Mock Vision (Mac Webcam)...]]")

    # 0 is usually the default built-in webcam, my default is 1
    cap = cv2.VideoCapture(1)

    if not cap.isOpened():
        print("[[Error: Could not open webcam.]]")
        return

    print("[[Mock Camera Polling Layer Ready]]")

    try:
        while True:
            ret, frame = cap.read()
            if ret:
                # Resize to roughly 640x480 to mimic the Nao's camera resolution
                frame = cv2.resize(frame, (640, 480))
                # Save as JPEG with 80% quality
                cv2.imwrite(FRAME_FILE, frame, [int(cv2.IMWRITE_JPEG_QUALITY), 80])

            # Write a frame every 1 second, matching the physical robot
            time.sleep(1.0)

    except KeyboardInterrupt:
        pass
    except Exception as e:
        print(f"[[Mock Vision Error: {e}]]")
    finally:
        cap.release()


if __name__ == "__main__":
    main()
