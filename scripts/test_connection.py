"""
tests the connection to the physical NAO robot.
runs in the python 2.7 'nao' conda environment.
"""

import sys

try:
    import naoqi
    from naoqi import ALProxy
except ImportError:
    print("[[ ERROR: Could not import naoqi. ]]")
    print("Ensure you are running this script inside the 'nao' Conda environment.")
    print("Command: conda activate nao && python scripts/test_connection.py")
    sys.exit(1)

# replace with your robot's IP address (press the chest button to hear it)
IP = "10.1.65.214"
PORT = 9559

def main():
    print("[[ Testing connection to NAO at {}:{} ]]".format(IP, PORT))
    try:
        tts = ALProxy("ALTextToSpeech", IP, PORT)
        print("[[ Connection successful. Making the robot speak... ]]")
        tts.say("Connection successful.")
        print("[[ Test complete. ]]")
    except Exception as e:
        print("[[ ERROR: Could not connect to the robot. ]]")
        print("Verify the IP address is correct and the robot is turned on.")
        print("Exception details:")
        print(e)

if __name__ == "__main__":
    main()