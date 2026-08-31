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
from rich.console import Console

console = Console()

sys.path.append(os.path.dirname(os.path.abspath(__file__)))
from lib.file_utils import safe_read, safe_write, get_env_var


### config
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
STATE_DIR = os.path.join(BASE_DIR, "state")

LISTEN_FILE = os.path.join(STATE_DIR, "listen.txt")
TRANSCRIPTION_FILE = os.path.join(STATE_DIR, "transcription.txt")

_mic_env = get_env_var("MICROPHONE_INDEX", "")
MICROPHONE_INDEX = int(_mic_env) if _mic_env.strip() else None


def _filter_stderr(proc, ready_event):
    for line in proc.stderr:
        if "[[STT_WORKER]]" in line:
            if "[[STT_WORKER]]: ready" in line:
                console.print(f"[dim white]{line.strip()}[/]")
                ready_event.set()
            else:
                console.print(f"[dim white]{line.strip()}[/]")


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
        console.print("[dim white][[STT_WORKER]]: python whisper fallback ready[/]")

    r = sr.Recognizer()
    r.pause_threshold = 2.5

    with sr.Microphone(device_index=MICROPHONE_INDEX) as source:
        if getattr(source, "stream", None) is None:
            # Monkey-patch to prevent __exit__ crash in speech_recognition
            source.stream = type('DummyStream', (), {'close': lambda self: None})()
            console.print(f"[bold red][[ FATAL: Could not open microphone index {MICROPHONE_INDEX}. Is it a valid input device? ]][/]")
            console.print("[bold red][[ Check your .env file or run the enumeration script to find the correct index. ]][/]")
            sys.exit(1)
            
        # run once for room ambience
        r.adjust_for_ambient_noise(source, duration=2.0)

        was_listening = False
        while True:
            state = safe_read(LISTEN_FILE)
            if state == "no":
                was_listening = False
                time.sleep(0.1)
                continue

            if not was_listening:
                # Flush the PyAudio buffer so we don't accidentally transcribe the end of the robot's speech
                try:
                    if getattr(source, "stream", None) and hasattr(source.stream, "pyaudio_stream"):
                        frames_avail = source.stream.pyaudio_stream.get_read_available()
                        if frames_avail > 0:
                            source.stream.pyaudio_stream.read(frames_avail, exception_on_overflow=False)
                except Exception:
                    pass
                
                console.print("[bold dark_orange][[LISTENING]][/]")
                was_listening = True

            try:
                # blocks briefly. if no speech is heard, raises WaitTimeoutError and breaks.
                # phrase_time_limit caps runaway recording if ambient noise stays high
                audio = r.listen(source, timeout=1, phrase_time_limit=15)
            except sr.WaitTimeoutError:
                # expected timeout, lets us loop back and re-check listen.txt frequently
                continue
            except Exception as e:
                console.print(f"[bold red][[ Error capturing audio: {e} ]][/]")
                continue

            text = ""
            if IS_MAC:
                # revive worker if it crashed
                if swift_proc is None or swift_proc.poll() is not None:
                    console.print("[dim white][[ SYSTEM: Reviving crashed STT worker... ]][/]")
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
                    console.print("[dim white][[ SYSTEM: STT worker pipe broke. Restarting... ]][/]")
                    swift_proc = start_swift_worker()
                    text = ""

                # cleanup temp file
                try:
                    os.unlink(temp_wav.name)
                except Exception as e:
                    console.print(f"[bold red][[ Cleanup Error: {e} ]][/]")
            else:
                # fallback to standard python whisper
                try:
                    text = r.recognize_whisper(audio, model="base.en").strip()
                except sr.UnknownValueError:
                    text = ""
                except Exception as e:
                    console.print(f"[bold red][[ Whisper Fallback Error: {e} ]][/]")

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
                safe_write(LISTEN_FILE, "no")
                was_listening = False

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        pass