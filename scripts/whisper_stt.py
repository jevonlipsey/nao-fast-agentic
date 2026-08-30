"""
handles local speech-to-text. automatically detects the operating system:
if on a mac, boots an ultra-low-latency swift coreml worker (pktv3).
if on windows/linux, falls back to the standard python whisper wrapper.
outputs transcriptions to be picked up by the cognitive layer.

layer 1: microphone -> whisper_stt -> openai_response
"""

import speech_recognition as sr
import time
import os
import random
import subprocess
import tempfile
import threading
import platform
import sys

sys.path.append(os.path.dirname(os.path.abspath(__file__)))
from lib.file_utils import safe_read, safe_write


### config
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
STATE_DIR = os.path.join(BASE_DIR, "state")

LISTEN_FILE = os.path.join(STATE_DIR, "listen.txt")
TRANSCRIPTION_FILE = os.path.join(STATE_DIR, "transcription.txt")
MICROPHONE_INDEX = 3


def _filter_stderr(proc, ready_event):
    for line in proc.stderr:
        if "[[STT_WORKER]]" in line:
            print(line, end="", flush=True)
            if "[[STT_WORKER]]: ready" in line:
                ready_event.set()


## main loop
def main():
    # to set microphone index, uncomment and run
    """
    print("[[ Enumerating Audio Devices... ]]")
    mics = sr.Microphone.list_microphone_names()
    for index, name in enumerate(mics):
        print(f"  [{index}] {name}")
    print(
        f"[[ Using Microphone Index: {MICROPHONE_INDEX if MICROPHONE_INDEX is not None else 'System Default'} ]]\n"
    )
    """

    # check operating system for stt backend
    IS_MAC = platform.system() == "Darwin"
    swift_proc = None

    def start_swift_worker():
        stt_worker_dir = os.path.join(BASE_DIR, "stt-coreml", "stt_worker")
        proc = subprocess.Popen(
            ["swift", "run", "-c", "release"],
            cwd=stt_worker_dir,
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            bufsize=1,
        )
        ready_event = threading.Event()
        t = threading.Thread(target=_filter_stderr, args=(proc, ready_event), daemon=True)
        t.start()
        # block until worker says it's ready
        ready_event.wait()
        return proc

    if IS_MAC:
        swift_proc = start_swift_worker()
    else:
        print("[[STT_WORKER]]: python whisper fallback ready")

    r = sr.Recognizer()
    r.pause_threshold = 1.5

    with sr.Microphone(device_index=MICROPHONE_INDEX) as source:
        # run once for room ambience
        r.adjust_for_ambient_noise(source, duration=2.0)

    was_listening = False
    with sr.Microphone(device_index=MICROPHONE_INDEX) as source:
        while True:
            state = safe_read(LISTEN_FILE)
            if state == "no":
                was_listening = False
                time.sleep(0.1)
                continue

            if not was_listening:
                print("[[LISTENING]]")
                was_listening = True

            try:
                # blocks briefly. if no speech is heard, raises WaitTimeoutError and breaks.
                # phrase_time_limit caps runaway recording if ambient noise stays high
                audio = r.listen(source, timeout=1, phrase_time_limit=15)
            except sr.WaitTimeoutError:
                # expected timeout, lets us loop back and re-check listen.txt frequently
                continue
            except Exception as e:
                print(f"[[ Error capturing audio: {e} ]]")
                continue

            text = ""
            if IS_MAC:
                # revive worker if it crashed
                if swift_proc is None or swift_proc.poll() is not None:
                    print("[[ SYSTEM: Reviving crashed STT worker... ]]")
                    swift_proc = start_swift_worker()

                # convert audio to .wav bytes and write to temp file
                wav_data = audio.get_wav_data(convert_rate=16000, convert_width=2)

                temp_wav = tempfile.NamedTemporaryFile(suffix=".wav", delete=False)
                temp_wav.write(wav_data)
                temp_wav.close()

                # pipe the temporary file path to the swift worker
                try:
                    swift_proc.stdin.write(temp_wav.name + "\n")
                    swift_proc.stdin.flush()

                    # wait for the CoreML transcription
                    text = swift_proc.stdout.readline().strip()
                except BrokenPipeError:
                    print("[[ SYSTEM: STT worker pipe broke. Restarting... ]]")
                    swift_proc = start_swift_worker()
                    text = ""

                # cleanup temp file
                try:
                    os.unlink(temp_wav.name)
                except Exception as e:
                    print(f"[[ Cleanup Error: {e} ]]")
            else:
                # fallback to standard python whisper
                try:
                    text = r.recognize_whisper(audio, model="base.en").strip()
                except sr.UnknownValueError:
                    text = ""
                except Exception as e:
                    print(f"[[ Whisper Fallback Error: {e} ]]")

            # minimal hallucinations filter
            hallucinations = [
                "...",
                "you",
                "now",
                "you.",
                "now.",
            ]

            if text and text.lower() not in hallucinations:
                # pass to openai speech
                safe_write(TRANSCRIPTION_FILE, text)


if __name__ == "__main__":
    main()
