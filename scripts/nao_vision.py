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
CAM_INDEX_FILE = os.path.join(STATE_DIR, "camera_index.txt")

def main():
    print("[[Connecting to NAOqi ALVideoDevice...]]")
    try:
        video_proxy = ALProxy("ALVideoDevice", IP, PORT)
    except Exception as e:
        print("[[Error connecting to camera. Is the robot IP correct?]]")
        print("Details: ", e)
        return

    # default to camera 0 (top), resolution 2 (vga 640x480), colorspace 11 (rgb), fps 10
    current_cam = 0
    sub_id = video_proxy.subscribeCamera("py_vision", current_cam, 2, 11, 10)
    print("[[Camera Polling Layer Ready (Top Camera)]]")

    try:
        while True:
            # check if an mcp tool requested switching camera (0 = top, 1 = bottom)
            if os.path.exists(CAM_INDEX_FILE):
                try:
                    with open(CAM_INDEX_FILE, "r") as f:
                        req_cam = int(f.read().strip())
                    if req_cam in (0, 1) and req_cam != current_cam:
                        video_proxy.unsubscribe(sub_id)
                        current_cam = req_cam
                        sub_id = video_proxy.subscribeCamera("py_vision", current_cam, 2, 11, 10)
                        cam_name = "Bottom Camera (Desk/Table)" if current_cam == 1 else "Top Camera (Eyes/Room)"
                        print("[[Switched to: {}]]".format(cam_name))
                except Exception:
                    pass

            nao_image = video_proxy.getImageRemote(sub_id)
            if nao_image:
                width, height = nao_image[0], nao_image[1]
                image_data = nao_image[6]
                
                # convert raw bytes to a compressed jpeg
                im = Image.frombytes("RGB", (width, height), image_data)
                im.save(FRAME_FILE, "JPEG", quality=80)
            
            time.sleep(0.25)  # 4 fps for fresh frames without overloading i/o
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