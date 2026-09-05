from __future__ import print_function
import socket
import json
import traceback
import os
import sys
from naoqi import ALProxy

sys.path.append(os.path.dirname(os.path.abspath(__file__)))
from lib.file_utils import get_env_var

IP = get_env_var("NAO_IP", "10.1.65.214")
PORT = int(get_env_var("NAO_PORT", "9559"))
DAEMON_PORT = int(get_env_var("DAEMON_PORT", "5005"))

def main():
    print("[[Starting NAO Daemon on port {}...]]".format(DAEMON_PORT))
    
    try:
        motion = ALProxy("ALMotion", IP, PORT)
        posture = ALProxy("ALRobotPosture", IP, PORT)
        leds = ALProxy("ALLeds", IP, PORT)
        awareness = ALProxy("ALBasicAwareness", IP, PORT)
        memory = ALProxy("ALMemory", IP, PORT)
        try:
            life = ALProxy("ALAutonomousLife", IP, PORT)
        except Exception:
            life = None
    except Exception as e:
        print("[[Error connecting to NAOqi. Is the robot IP correct?]]")
        print("Details: ", e)
        return

    # initialize to a sane default
    print("[[Setting Posture to StandInit...]]")
    if posture.getPosture() != "Stand":
        posture.goToPosture("StandInit", 1.0)
    
    print("[[Enabling Basic Awareness...]]")
    try:
        awareness.setEngagementMode("FullyEngaged")
        awareness.setTrackingMode("Head")
        awareness.startAwareness()
    except Exception as e:
        print("[[Basic Awareness Warning: ", e, " ]]")

    # create tcp socket
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    s.bind(('127.0.0.1', DAEMON_PORT))
    s.listen(5)
    print("[[NAO Daemon Listening for TCP commands...]]")

    try:
        while True:
            conn, addr = s.accept()
            try:
                data = conn.recv(4096)
                if not data:
                    continue
                
                payload = json.loads(data.decode('utf-8'))
                command = payload.get("command")
                args = payload.get("args", {})
                
                print("[[Daemon Executing: {}]]".format(command))
                
                if command == "goToPosture":
                    posture_name = args.get("posture", "StandInit")
                    if isinstance(posture_name, unicode):
                        posture_name = posture_name.encode("utf-8")
                    posture.goToPosture(posture_name, 1.0)
                elif command == "setAngles":
                    # args: pitch, yaw
                    names = ["HeadPitch", "HeadYaw"]
                    angles = [args.get("pitch", 0.0), args.get("yaw", 0.0)]
                    
                    # ensure awareness is stopped so it doesn't fight the head movement
                    try:
                        if awareness.isAwarenessRunning():
                            awareness.stopAwareness()
                    except Exception:
                        pass
                        
                    # ensure head motors are powered on
                    motion.setStiffnesses("Head", 1.0)
                    
                    # use brisk 0.35 fractionmaxspeed so head reaches target before photo
                    motion.angleInterpolationWithSpeed(names, angles, 0.35)
                elif command == "setAwareness":
                    state = args.get("state", True)
                    if state:
                        awareness.startAwareness()
                    else:
                        awareness.stopAwareness()
                elif command == "fadeRGB":
                    # args: name (e.g. "faceleds"), r, g, b, duration
                    name = args.get("name", "FaceLeds")
                    if isinstance(name, unicode):
                        name = name.encode("utf-8")
                    r = float(args.get("r", 1.0))
                    g = float(args.get("g", 1.0))
                    b = float(args.get("b", 1.0))
                    duration = float(args.get("duration", 0.5))

                    # temporarily disable autonomous blinking if life proxy exists so leds don't get overwritten immediately
                    if life:
                        try:
                            life.setAutonomousAbilityEnabled("AutonomousBlinking", False)
                        except Exception:
                            pass

                    leds.fadeRGB(name, r, g, b, duration)
                elif command == "saveName":
                    person_id = args.get("id")
                    name = args.get("name")
                    if isinstance(name, unicode):
                        name = name.encode("utf-8")
                    # store in almemory
                    memory.insertData("KnownHumans/" + str(person_id), name)
                    print("[[ALMemory Saved: KnownHumans/{} = {}]]".format(person_id, name))
                else:
                    raise ValueError("Unknown command: " + str(command))
                
                response = json.dumps({"status": "success", "message": "Command executed successfully"})
                conn.sendall(response.encode('utf-8'))
            except Exception as e:
                err = traceback.format_exc()
                print("[[Daemon Error]]: ", err)
                response = json.dumps({"status": "error", "message": str(e)})
                conn.sendall(response.encode('utf-8'))
            finally:
                conn.close()
    except KeyboardInterrupt:
        print("\n[[NAO Daemon Shutting Down...]]")
        s.close()

if __name__ == "__main__":
    main()