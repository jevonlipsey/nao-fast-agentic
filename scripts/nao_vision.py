from __future__ import print_function
import time
import os
import sys
from naoqi import ALProxy
from PIL import Image

sys.path.append(os.path.dirname(os.path.abspath(__file__)))
from lib.file_utils import get_env_var

IP = get_env_var("NAO_IP", "10.1.65.214")
PORT = int(get_env_var("NAO_PORT", "9559"))

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
STATE_DIR = os.path.join(BASE_DIR, "state")
FRAME_FILE = os.path.join(STATE_DIR, "latest_frame.jpg")

def main():
    print("[[Connecting to NAOqi ALVideoDevice...]]")
    try:
        video_proxy = ALProxy("ALVideoDevice", IP, PORT)
    except Exception as e:
        print("[[Error connecting to camera. Is the robot IP correct?]]")
        print("Details: ", e)
        return

    # Camera 0 (Top), Resolution 2 (VGA 640x480), ColorSpace 11 (RGB), FPS 10
    sub_id = video_proxy.subscribeCamera("py_vision", 0, 2, 11, 10)
    print("[[Camera Polling Layer Ready]]")

    try:
        while True:
            nao_image = video_proxy.getImageRemote(sub_id)
            if nao_image:
                width, height = nao_image[0], nao_image[1]
                image_data = nao_image[6]
                
                # Convert raw bytes to a compressed JPEG
                im = Image.frombytes("RGB", (width, height), image_data)
                im.save(FRAME_FILE, "JPEG", quality=80)
            
            time.sleep(0.25)  # 4 FPS for fresh frames without overloading I/O
    except KeyboardInterrupt:
        pass
    except Exception as e:
        print("[[Vision Loop Error: ", e, " ]]")
    finally:
        try:
            video_proxy.unsubscribe(sub_id)
        except Exception:
            pass

if __name__ == "__main__":
    main()